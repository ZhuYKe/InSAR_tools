#!/usr/bin/env python
import numpy as np
from osgeo import gdal
import sys

def read_dem(dem_file):
    # 打开DEM文件
    dem_dataset = gdal.Open(dem_file)

    # 读取DEM数据
    dem_array = np.array(dem_dataset.ReadAsArray())

    # 关闭DEM文件
    dem_dataset = None

    return dem_array


def get_pixel_index(lat, lon, header_file):
    with open(header_file, 'r') as f:
        lines = f.readlines()
    post_lon_line = None
    post_lat_line = None
    corner_lon_line = None
    corner_lat_line = None
    for line in lines:
        if 'corner_lat' in line:
            corner_lat_line = line.strip()
            break
    corner_lat = float(corner_lat_line.split(': ')[1].split(' ')[0])

    for line in lines:
        if 'corner_lon' in line:
            corner_lon_line = line.strip()
            break
    corner_lon = float(corner_lon_line.split(': ')[1].split(' ')[0])

    for line in lines:
        if 'post_lat' in line:
            post_lat_line = line.strip()
            break
    post_lat = float(post_lat_line.split(': ')[1].split(' ')[0])

    for line in lines:
        if 'post_lon' in line:
            post_lon_line = line.strip()
            break
    post_lon = float(post_lon_line.split(': ')[1].split(' ')[0])

    row_offset = int((corner_lat - float(lat)) / post_lat)  # -3200
    col_offset = int((float(lon) - corner_lon) / post_lon)  # 4000

    return abs(row_offset), col_offset


def get_elevation_at_latlon(dem_array, row_offset, col_offset):
    elevation = dem_array[row_offset, col_offset]
    return elevation


def get_pixel_index_tif(lat, lon, file):

    dataset = gdal.Open(file)
    geotransform = dataset.GetGeoTransform()
    corner_lon = float(geotransform[0])
    corner_lat = float(geotransform[3])
    post_lon = float(geotransform[1])
    post_lat = float(geotransform[5])
    
    row_offset = int((corner_lat - float(lat)) / post_lat)  # -3200
    col_offset = int((float(lon) - corner_lon) / post_lon)  # 4000

    return abs(row_offset), col_offset


if __name__ == "__main__":

    if len(sys.argv) < 3:
        print("请按格式输入")
        print("<script_name> <dem_file> <target_lat> <target_lon>")
        print("dem_file：DEM输入")
        print("target_lat：目标纬度")
        print("target_lon：目标经度")
        sys.exit(1)
    dem_file = sys.argv[1]
    target_lat = sys.argv[2]
    target_lon = sys.argv[3]

    dem_array = read_dem(dem_file)
    row_offset, col_offset = get_pixel_index_tif(target_lat, target_lon, dem_file)
    elevation = get_elevation_at_latlon(dem_array, row_offset, col_offset)
	
    print(f"Elevation at ({target_lat}, {target_lon}): {elevation}")  # 1392
