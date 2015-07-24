'''
Set of scripts for munging varios raster formats and datatypes.
'''
import numpy

try: import gdal, osr
except ImportError: from osgeo import gdal, osr

import math
import os
import shutil

def get_hdr_info(bsq_path):
    '''
    Given an ENVI header file (hdr associated with a bsq) this function will go through and remove relevant
    geotransformation data. Assumes the hdr is in the same directory with the same base file name.
    :param bsq_path: The path to the bsq file.
    :return: columns in raster array (int), rows in raster array (int), geotransform (list)
    '''

    hdr_path = os.path.splitext(bsq_path)[0] + '.hdr'
    hdr_file = open(hdr_path, 'r')
    metadata_lines = hdr_file.readlines()

    for line in metadata_lines:
        if 'samples' in line:
             columns = int(line.split('=')[1].strip())
        if 'lines' in line:
            rows = int(line.split('=')[1].strip())
        if 'map info =' in line:
            parsed_line = line.split(',')
            origin_x = float(parsed_line[3].strip())
            origin_y = float(parsed_line[4].strip())
            x_res = float(parsed_line[5].strip())
            y_res = float(parsed_line[6].strip())


    geotransform = [origin_x, x_res, 0.0, origin_y, 0.0, -y_res]

    return columns, rows, geotransform


def transform_with_rotation(geotransform, degrees):
    '''
    Redefines a geotransform to rotate a raster around an origin at whatever given degree.
    :param geotransform: List of 6 geotransform elements
    :param degrees: Float or Int degrees to rotate
    :return: Returns transformed geotransform
    '''

    radians = (float(degrees) * math.pi) / 180.0

    geotransform[1] = geotransform[1] * math.cos(radians)
    geotransform[2] = -geotransform[1] * math.sin(radians)
    geotransform[4] = geotransform[4] * math.sin(radians)
    geotransform[5] = geotransform[4] * math.cos(radians)

    return geotransform


def convert_to_tiff_float32(source_raster_path, target_raster_path, sr_epsg):
    '''
    Converts a 64bit integer bsq raster into a 32bit float geotiff. Truncates at lost values (can be changed but is not
    currently relevant).
    :param source_raster_path: Full path to .bsq source raster
    :param target_raster_path: Full path where .tif will be created
    :param sr_epsg: Spatial Reference EPSG code
    :return: Returns target_raster_path
    '''

    columns, rows, geotransform = get_hdr_info(source_raster_path)

    raster_values = numpy.fromfile(source_raster_path, numpy.int64)
    raster_values = raster_values.astype(numpy.float64)

    raster_values = (raster_values / 100) - 273.15
    raster_values.shape = rows, columns

    output_raster = gdal.GetDriverByName('GTiff').Create(target_raster_path, columns, rows, 1, gdal.GDT_Float32)
    output_raster.SetGeoTransform(geotransform)

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(sr_epsg)

    output_raster.SetProjection(srs.ExportToWkt())

    output_raster.GetRasterBand(1).WriteArray(raster_values)

    return target_raster_path


def change_hdr_dtype(hdr_path):
    '''
    Changes the data type in the raster header. Kind of hackish but I am left with no choice.
    :param hdr_path:
    :return:
    '''
    header_file = open(hdr_path, 'r+')
    lines = header_file.readlines()
    for idx, line in enumerate(lines):
        if 'data type = ' in line:
            lines[idx] = 'data type = 5 \n'
            break
    header_file.seek(0)
    header_file.truncate()
    header_file.write(''.join(lines))
    header_file.close()

def create_bsq_copy(path_source_raster, tag='_converted'):
    """
    Creates copies of bsq files and headers so we can totally mess up one of them up with crazy munging stuff. Should work
    with all ENVI types not just bsq.
    :param path_source_raster: Path the the raster of interest.
    :param tag: String tag to be injected into the file name.
    :return: Returns path string of freshly copied raster
    """
    base, ext = os.path.splitext(path_source_raster)
    path_target_raster = base + tag + ext
    path_source_header = base + '.hdr'
    path_target_header = base + tag + '.hdr'

    print 'Creating ' + path_target_raster
    shutil.copy(path_source_raster, path_target_raster)
    shutil.copy(path_source_header, path_target_header)
    change_hdr_dtype(path_target_header)
    print 'Done'

    return path_target_raster


def convert_to_envi_int32(path_source_raster):
    '''
    Will create a converted file in the same directory as the original. Converts annoying 64bit int [long] data
    into beautiful 64bit float. Renames to _converted (probably).
    :param path_source_raster: Path to raster you want to convert.
    :return:
    '''

    # Get relevant metadata
    path_target_raster = create_bsq_copy(path_source_raster)
    target_raster = gdal.Open(path_target_raster)
    bands = target_raster.RasterCount
    columns = target_raster.RasterXSize
    rows = target_raster.RasterYSize

    # Create memory maps of the copied files. Convert and rewrite in one fell swoop.
    source_memmap = numpy.memmap(path_source_raster, dtype=numpy.int64, mode='r+', shape=(rows, columns, bands))
    image_memmap = numpy.memmap(path_target_raster, dtype=numpy.float64, mode='r+', shape=(rows, columns, bands))
    image_memmap[:, :, :] = source_memmap.astype(numpy.float64)
    image_memmap.flush()

    return


path_source_raster = r"Your path here."
convert_to_envi_int32(path_source_raster)
