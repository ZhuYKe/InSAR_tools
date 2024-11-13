#!/usr/bin/env python
# import cv2
from PIL import Image, ImageDraw
from lxml import etree
from osgeo import gdal
import numpy as np
import sys
import os
from osgeo import ogr
from osgeo import osr


def shp_to_geotiff(shp, ref_geotiff, out_geotfif):
    # 打开Shapefile
    shp_ds = ogr.Open(shp_file)
    if shp_ds is None:
        print("Failed to open file: " + shp_file)
        sys.exit(1)

    layer = shp_ds.GetLayer()

    # 打开输入栅格文件以获取其大小和地理范围
    input_ds = gdal.Open(input_raster_file)
    if input_ds is None:
        print("Failed to open file: " + input_raster_file)
        sys.exit(1)

    # 获取输入栅格的地理范围和大小
    x_min, x_res, _, y_max, _, y_res = input_ds.GetGeoTransform()
    x_size = input_ds.RasterXSize
    y_size = input_ds.RasterYSize

    # 创建输出栅格
    target_ds = gdal.GetDriverByName('GTiff').Create(output_raster_file, x_size, y_size, 1, gdal.GDT_Byte)
    target_ds.SetGeoTransform((x_min, x_res, 0, y_max, 0, y_res))
    band = target_ds.GetRasterBand(1)
    band.SetNoDataValue(0)

    # 设置投影信息
    srs = osr.SpatialReference()
    srs.ImportFromWkt(input_ds.GetProjectionRef())
    target_ds.SetProjection(srs.ExportToWkt())

    # 栅格化整个图层
    gdal.RasterizeLayer(target_ds, [1], layer, burn_values=[255], options=["ALL_TOUCHED=TRUE"])

    # 关闭数据源
    target_ds = None
    shp_ds = None
    input_ds = None


def check_file_exists(file_path):
    if os.path.exists(file_path):
        print(f"输入文件存在：{file_path}")
    else:
        print(f"输入文件不存在：{file_path}")
        sys.exit(0)


if __name__ == "__main__":

    if len(sys.argv) < 3:
        print("请按格式输入")
        print("<script_name> <ROI_range_path> <geotiff_path> <output_path>")
        print("ROI_range_path: ROI区域shp文件")
        print("geotiff_path: 决定输出范围和行列数的geotiff输入")
        print("output_path: geotiff文件输出")
        sys.exit(1)

    geotiff_path = sys.argv[2]
    range_path = sys.argv[1]
    output_path = sys.argv[3]

    # 检查文件是否存在
    check_file_exists(geotiff_path)
    check_file_exists(range_path)

    # 获取文件扩展名
    _, file_extension = os.path.splitext(range_path)
    # 检查文件格式
    if file_extension.lower() != '.shp':
        print("输入矢量文件不是shp格式，请输入shp格式的面要素文件")
    elif file_extension.lower() == '.shp':
        shp_to_geotiff(shp=range_path, ref_geotiff=geotiff_path, out_geotfif=output_path)
