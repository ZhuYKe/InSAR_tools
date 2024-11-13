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


def shp_to_geotiff(shp, ref_geotiff, out_geotfif, flag):
    shp_ds = ogr.Open(shp)
    layer = shp_ds.GetLayer()
    input_ds = gdal.Open(ref_geotiff)
    x_min, x_res, _, y_max, _, y_res = input_ds.GetGeoTransform()
    x_size = input_ds.RasterXSize
    y_size = input_ds.RasterYSize
    target_ds = gdal.GetDriverByName('GTiff').Create(out_geotfif, x_size, y_size, 1, gdal.GDT_Byte)
    target_ds.SetGeoTransform((x_min, x_res, 0, y_max, 0, y_res))
    band = target_ds.GetRasterBand(1)
    if flag == '0':
        array = np.full((y_size, x_size), 255, dtype=np.uint8)
        band.WriteArray(array)
        srs = osr.SpatialReference()
        srs.ImportFromWkt(input_ds.GetProjectionRef())
        target_ds.SetProjection(srs.ExportToWkt())
        gdal.RasterizeLayer(target_ds, [1], layer, burn_values=[0], options=["ALL_TOUCHED=TRUE"])
    else:
        array = np.full((y_size, x_size), 0, dtype=np.uint8)
        band.WriteArray(array)
        srs = osr.SpatialReference()
        srs.ImportFromWkt(input_ds.GetProjectionRef())
        target_ds.SetProjection(srs.ExportToWkt())
        gdal.RasterizeLayer(target_ds, [1], layer, burn_values=[255], options=["ALL_TOUCHED=TRUE"])


def check_file_exists(file_path):
    if os.path.exists(file_path):
        print(f"输入文件存在：{file_path}")
    else:
        print(f"输入文件不存在：{file_path}")
        sys.exit(0)


if __name__ == "__main__":

    if len(sys.argv) < 3:
        print("请按格式输入")
        print("<script_name> <geotiff_path> <ROI_range_path> <output_path> <flag>")
        print("geotiff_path: 决定输出范围和行列数的geotiff输入")
        print("ROI_range_path: ROI区域shp文件")
        print("output_path: 无地理坐标的、与geotiff行列相同的8位灰度bmp文件输出")
        print("flag: 0：ROI范围为0 1：ROI范围为255")
        sys.exit(1)
		
    geotiff_path = sys.argv[1]
    range_path = sys.argv[2]
    output_path = sys.argv[3]
    flag = sys.argv[4]

    # 检查文件是否存在
    check_file_exists(geotiff_path)
    check_file_exists(range_path)

    # 获取文件扩展名
    _, file_extension = os.path.splitext(range_path)
    # 检查文件格式
    if file_extension.lower() != '.shp':
        print("输入矢量文件不是shp格式，请输入shp格式的面要素文件")
    elif file_extension.lower() == '.shp':
        shp_to_geotiff(shp=range_path, ref_geotiff=geotiff_path, out_geotfif=output_path, flag=flag)
