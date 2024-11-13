#!/usr/bin/env python
# coding=utf-8
import sys
import glob
import os

import xml.etree.ElementTree as ET
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, \
    QMessageBox, QComboBox, QTextEdit, QFileDialog
from PyQt5.QtGui import QFont, QTextCursor
from PIL import Image
from osgeo import gdal, gdalconst, ogr, osr
import numpy as np
from shapely.geometry import shape, Point
import fiona


#########################################################
# 2024.09.04  新增功能：裁剪参数选择时可以输入原始分辨率及目标分辨率对DEM切片进行分辨率重采样
# 2024.09.01  新增功能：输入DEM无法完全覆盖输入影像时将进行提示
# 2024.06.28  优化了遍历要素裁剪的切片速度
# 2024.05.07  原始版本

# Designed by ZhuYinke
# zhuyike1008@st.btbu.edu.cn
#########################################################

Source = ""
Resolution = ""
Sourece_time = ""
Data_type = ""
Data_depth = ""
Grade = ""

Province = ""
Municipal = ""
County = ""

Label_name = ""
Classification = ""
Spatial_reference = ""

Name = ""
Address = ""
Email = ""

Ori_Pixel_Stride = ''
Resampled_Pixel_Stride = ''


def get_dem_min_max(filename):
    # 打开DEM文件
    dataset = gdal.Open(filename, gdal.GA_ReadOnly)
    if dataset is None:
        print("无法打开文件：", filename)
        return None

    # 获取DEM的波段
    band = dataset.GetRasterBand(1)

    # 获取波段的最小值和最大值
    min_value = band.GetMinimum()
    max_value = band.GetMaximum()

    # 如果没有存储统计信息，则计算统计信息
    if min_value is None or max_value is None:
        min_value, max_value, _, _ = band.ComputeStatistics(False)

    # 关闭数据集
    dataset = None

    return min_value, max_value


def label_shp_to_geotiff(shp, geotiff, output_folder, stride_cut, center_flag, Four_neighborhoods_flag,
                         corner_neighborhoods_flag):
    # 打开Geotiff文件
    geotiff_dataset = gdal.Open(geotiff)
    # 获取地理转换信息和投影信息
    geotransform = geotiff_dataset.GetGeoTransform()
    projection = geotiff_dataset.GetProjection()
    # 获取地理坐标系和像素坐标系之间的转换参数
    x_origin = geotransform[0]
    y_origin = geotransform[3]
    pixel_width = geotransform[1]
    pixel_height = geotransform[5]

    # 计算GeoTIFF的范围
    width = geotiff_dataset.RasterXSize
    height = geotiff_dataset.RasterYSize

    # 计算左上角和右下角的地理坐标
    min_x = x_origin
    max_y = y_origin
    max_x = x_origin + width * pixel_width
    min_y = y_origin + height * pixel_height

    # 组装成一个范围元组
    tif_extent = (min_x, min_y, max_x, max_y)

    # 创建输出文件夹
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    sys.stdout.write("\rlabel切片处理")
    sys.stdout.flush()  # 强制刷新输出缓冲区

    # 打开Shapefile文件
    with fiona.open(shp, "r") as shapefiles:

        # 获取Shapefile的投影信息
        shp_projection = shapefiles.crs

        geometries = []

        # 获取各要素几何并保存在列表中
        for feature in shapefiles:
            geom = shape(feature["geometry"])

            # 检查要素的外接矩形是否在tif_extent内
            if geom.bounds[0] >= tif_extent[0] and geom.bounds[1] >= tif_extent[1] \
                    and geom.bounds[2] <= tif_extent[2] and geom.bounds[3] <= tif_extent[3]:
                geometries.append(geom)

        # 记录shp文件要素数量
        num_elements = len(geometries)

        # 计算输出label图片数量
        if center_flag == '1':
            picture_count_center = num_elements * 1
        else:
            picture_count_center = 0

        if corner_neighborhoods_flag == '1':
            picture_count_corner = num_elements * 4
        else:
            picture_count_corner = 0

        if Four_neighborhoods_flag == '1':
            picture_count_neighbor = num_elements * 4
        else:
            picture_count_neighbor = 0

        picture_count = picture_count_center + picture_count_corner + picture_count_neighbor

        count = 0
        for geom in geometries:
            # 获得当前要素中心坐标和四角坐标
            center_point = geom.centroid
            bbox = geom.bounds

            if center_flag == '1':
                # 中心
                center_x = int((center_point.x - x_origin) / pixel_width)
                center_y = int((center_point.y - y_origin) / pixel_height)
                # 创建一个256x256的空白图像
                image_data = np.zeros((stride_cut, stride_cut), dtype=np.uint8)
                count = count + 1
                for i in range(stride_cut):
                    for j in range(stride_cut):
                        # 将像素坐标转换为地理坐标
                        x_geo = x_origin + (center_x - (stride_cut / 2) + i) * pixel_width
                        y_geo = y_origin + (center_y - (stride_cut / 2) + j) * pixel_height
                        point = Point(x_geo, y_geo)

                        # 判断像素是否在要素范围内
                        if any(g.contains(point) for g in geometries):
                            image_data[j, i] = 255  # 白
                        else:
                            image_data[j, i] = 0  # 黑
                # 创建输出文件名
                output_filename = os.path.join(output_folder, f"{count}.tif")
                # 创建输出GeoTIFF文件
                driver = gdal.GetDriverByName("GTiff")
                output_dataset = driver.Create(output_filename, stride_cut, stride_cut, 1, gdal.GDT_Byte)
                output_dataset.SetGeoTransform((x_origin + (center_x - (stride_cut / 2)) * pixel_width, pixel_width, 0,
                                                y_origin + (center_y - (stride_cut / 2)) * pixel_height, 0,
                                                pixel_height))
                output_dataset.SetProjection(projection)
                output_band = output_dataset.GetRasterBand(1)
                output_band.WriteArray(image_data)
                output_band.FlushCache()
                output_dataset = None
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区

            if corner_neighborhoods_flag == '1':

                # 左上
                center_x = int((bbox[0] - x_origin) / pixel_width) + stride_cut / 2
                center_y = int((bbox[3] - y_origin) / pixel_height) + stride_cut / 2
                # 创建一个256x256的空白图像
                image_data = np.zeros((stride_cut, stride_cut), dtype=np.uint8)
                count = count + 1
                for i in range(stride_cut):
                    for j in range(stride_cut):
                        # 将像素坐标转换为地理坐标
                        x_geo = x_origin + (center_x - (stride_cut / 2) + i) * pixel_width
                        y_geo = y_origin + (center_y - (stride_cut / 2) + j) * pixel_height
                        point = Point(x_geo, y_geo)

                        # 判断像素是否在要素范围内
                        if any(g.contains(point) for g in geometries):
                            image_data[j, i] = 255  # 白
                        else:
                            image_data[j, i] = 0  # 黑
                # 创建输出文件名
                output_filename = os.path.join(output_folder, f"{count}.tif")
                # 创建输出GeoTIFF文件
                driver = gdal.GetDriverByName("GTiff")
                output_dataset = driver.Create(output_filename, stride_cut, stride_cut, 1, gdal.GDT_Byte)
                output_dataset.SetGeoTransform((x_origin + (center_x - (stride_cut / 2)) * pixel_width, pixel_width, 0,
                                                y_origin + (center_y - (stride_cut / 2)) * pixel_height, 0,
                                                pixel_height))
                output_dataset.SetProjection(projection)
                output_band = output_dataset.GetRasterBand(1)
                output_band.WriteArray(image_data)
                output_band.FlushCache()
                output_dataset = None
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区

                # 右上
                center_x = int((bbox[2] - x_origin) / pixel_width) - stride_cut / 2
                center_y = int((bbox[3] - y_origin) / pixel_height) + stride_cut / 2
                # 创建一个256x256的空白图像
                image_data = np.zeros((stride_cut, stride_cut), dtype=np.uint8)
                count = count + 1
                for i in range(stride_cut):
                    for j in range(stride_cut):
                        # 将像素坐标转换为地理坐标
                        x_geo = x_origin + (center_x - (stride_cut / 2) + i) * pixel_width
                        y_geo = y_origin + (center_y - (stride_cut / 2) + j) * pixel_height
                        point = Point(x_geo, y_geo)

                        # 判断像素是否在要素范围内
                        if any(g.contains(point) for g in geometries):
                            image_data[j, i] = 255  # 白
                        else:
                            image_data[j, i] = 0  # 黑
                # 创建输出文件名
                output_filename = os.path.join(output_folder, f"{count}.tif")
                # 创建输出GeoTIFF文件
                driver = gdal.GetDriverByName("GTiff")
                output_dataset = driver.Create(output_filename, stride_cut, stride_cut, 1, gdal.GDT_Byte)
                output_dataset.SetGeoTransform((x_origin + (center_x - (stride_cut / 2)) * pixel_width, pixel_width, 0,
                                                y_origin + (center_y - (stride_cut / 2)) * pixel_height, 0,
                                                pixel_height))
                output_dataset.SetProjection(projection)
                output_band = output_dataset.GetRasterBand(1)
                output_band.WriteArray(image_data)
                output_band.FlushCache()
                output_dataset = None
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区

                # 右下
                center_x = int((bbox[2] - x_origin) / pixel_width) - stride_cut / 2
                center_y = int((bbox[1] - y_origin) / pixel_height) - stride_cut / 2
                # 创建一个256x256的空白图像
                image_data = np.zeros((stride_cut, stride_cut), dtype=np.uint8)
                count = count + 1
                for i in range(stride_cut):
                    for j in range(stride_cut):
                        # 将像素坐标转换为地理坐标
                        x_geo = x_origin + (center_x - (stride_cut / 2) + i) * pixel_width
                        y_geo = y_origin + (center_y - (stride_cut / 2) + j) * pixel_height
                        point = Point(x_geo, y_geo)

                        # 判断像素是否在要素范围内
                        if any(g.contains(point) for g in geometries):
                            image_data[j, i] = 255  # 白
                        else:
                            image_data[j, i] = 0  # 黑
                # 创建输出文件名
                output_filename = os.path.join(output_folder, f"{count}.tif")
                # 创建输出GeoTIFF文件
                driver = gdal.GetDriverByName("GTiff")
                output_dataset = driver.Create(output_filename, stride_cut, stride_cut, 1, gdal.GDT_Byte)
                output_dataset.SetGeoTransform((x_origin + (center_x - (stride_cut / 2)) * pixel_width, pixel_width, 0,
                                                y_origin + (center_y - (stride_cut / 2)) * pixel_height, 0,
                                                pixel_height))
                output_dataset.SetProjection(projection)
                output_band = output_dataset.GetRasterBand(1)
                output_band.WriteArray(image_data)
                output_band.FlushCache()
                output_dataset = None
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区

                # 左下
                center_x = int((bbox[0] - x_origin) / pixel_width) + stride_cut / 2
                center_y = int((bbox[1] - y_origin) / pixel_height) - stride_cut / 2
                # 创建一个256x256的空白图像
                image_data = np.zeros((stride_cut, stride_cut), dtype=np.uint8)
                count = count + 1
                for i in range(stride_cut):
                    for j in range(stride_cut):
                        # 将像素坐标转换为地理坐标
                        x_geo = x_origin + (center_x - (stride_cut / 2) + i) * pixel_width
                        y_geo = y_origin + (center_y - (stride_cut / 2) + j) * pixel_height
                        point = Point(x_geo, y_geo)

                        # 判断像素是否在要素范围内
                        if any(g.contains(point) for g in geometries):
                            image_data[j, i] = 255  # 白
                        else:
                            image_data[j, i] = 0  # 黑
                # 创建输出文件名
                output_filename = os.path.join(output_folder, f"{count}.tif")
                # 创建输出GeoTIFF文件
                driver = gdal.GetDriverByName("GTiff")
                output_dataset = driver.Create(output_filename, stride_cut, stride_cut, 1, gdal.GDT_Byte)
                output_dataset.SetGeoTransform((x_origin + (center_x - (stride_cut / 2)) * pixel_width, pixel_width, 0,
                                                y_origin + (center_y - (stride_cut / 2)) * pixel_height, 0,
                                                pixel_height))
                output_dataset.SetProjection(projection)
                output_band = output_dataset.GetRasterBand(1)
                output_band.WriteArray(image_data)
                output_band.FlushCache()
                output_dataset = None
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区

            if Four_neighborhoods_flag == '1':
                # 下
                center_x = int((((bbox[0] + bbox[2]) / 2) - x_origin) / pixel_width)
                center_y = int((bbox[1] - y_origin) / pixel_height) - stride_cut / 2
                # 创建一个256x256的空白图像
                image_data = np.zeros((stride_cut, stride_cut), dtype=np.uint8)
                count = count + 1
                for i in range(stride_cut):
                    for j in range(stride_cut):
                        # 将像素坐标转换为地理坐标
                        x_geo = x_origin + (center_x - (stride_cut / 2) + i) * pixel_width
                        y_geo = y_origin + (center_y - (stride_cut / 2) + j) * pixel_height
                        point = Point(x_geo, y_geo)

                        # 判断像素是否在要素范围内
                        if any(g.contains(point) for g in geometries):
                            image_data[j, i] = 255  # 白
                        else:
                            image_data[j, i] = 0  # 黑
                # 创建输出文件名
                output_filename = os.path.join(output_folder, f"{count}.tif")
                # 创建输出GeoTIFF文件
                driver = gdal.GetDriverByName("GTiff")
                output_dataset = driver.Create(output_filename, stride_cut, stride_cut, 1, gdal.GDT_Byte)
                output_dataset.SetGeoTransform((x_origin + (center_x - (stride_cut / 2)) * pixel_width, pixel_width, 0,
                                                y_origin + (center_y - (stride_cut / 2)) * pixel_height, 0,
                                                pixel_height))
                output_dataset.SetProjection(projection)
                output_band = output_dataset.GetRasterBand(1)
                output_band.WriteArray(image_data)
                output_band.FlushCache()
                output_dataset = None
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区

                # 左
                center_x = int((bbox[0] - x_origin) / pixel_width) + stride_cut / 2
                center_y = int((((bbox[1] + bbox[3]) / 2) - y_origin) / pixel_height)
                # 创建一个256x256的空白图像
                image_data = np.zeros((stride_cut, stride_cut), dtype=np.uint8)
                count = count + 1
                for i in range(stride_cut):
                    for j in range(stride_cut):
                        # 将像素坐标转换为地理坐标
                        x_geo = x_origin + (center_x - (stride_cut / 2) + i) * pixel_width
                        y_geo = y_origin + (center_y - (stride_cut / 2) + j) * pixel_height
                        point = Point(x_geo, y_geo)

                        # 判断像素是否在要素范围内
                        if any(g.contains(point) for g in geometries):
                            image_data[j, i] = 255  # 白
                        else:
                            image_data[j, i] = 0  # 黑
                # 创建输出文件名
                output_filename = os.path.join(output_folder, f"{count}.tif")
                # 创建输出GeoTIFF文件
                driver = gdal.GetDriverByName("GTiff")
                output_dataset = driver.Create(output_filename, stride_cut, stride_cut, 1, gdal.GDT_Byte)
                output_dataset.SetGeoTransform((x_origin + (center_x - (stride_cut / 2)) * pixel_width, pixel_width, 0,
                                                y_origin + (center_y - (stride_cut / 2)) * pixel_height, 0,
                                                pixel_height))
                output_dataset.SetProjection(projection)
                output_band = output_dataset.GetRasterBand(1)
                output_band.WriteArray(image_data)
                output_band.FlushCache()
                output_dataset = None
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区

                # 上
                center_x = int((((bbox[0] + bbox[2]) / 2) - x_origin) / pixel_width)
                center_y = int((bbox[3] - y_origin) / pixel_height) + stride_cut / 2
                # 创建一个256x256的空白图像
                image_data = np.zeros((stride_cut, stride_cut), dtype=np.uint8)
                count = count + 1
                for i in range(stride_cut):
                    for j in range(stride_cut):
                        # 将像素坐标转换为地理坐标
                        x_geo = x_origin + (center_x - (stride_cut / 2) + i) * pixel_width
                        y_geo = y_origin + (center_y - (stride_cut / 2) + j) * pixel_height
                        point = Point(x_geo, y_geo)

                        # 判断像素是否在要素范围内
                        if any(g.contains(point) for g in geometries):
                            image_data[j, i] = 255  # 白
                        else:
                            image_data[j, i] = 0  # 黑
                # 创建输出文件名
                output_filename = os.path.join(output_folder, f"{count}.tif")
                # 创建输出GeoTIFF文件
                driver = gdal.GetDriverByName("GTiff")
                output_dataset = driver.Create(output_filename, stride_cut, stride_cut, 1, gdal.GDT_Byte)
                output_dataset.SetGeoTransform((x_origin + (center_x - (stride_cut / 2)) * pixel_width, pixel_width, 0,
                                                y_origin + (center_y - (stride_cut / 2)) * pixel_height, 0,
                                                pixel_height))
                output_dataset.SetProjection(projection)
                output_band = output_dataset.GetRasterBand(1)
                output_band.WriteArray(image_data)
                output_band.FlushCache()
                output_dataset = None
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区

                # 右
                center_x = int((bbox[2] - x_origin) / pixel_width) - stride_cut / 2
                center_y = int((((bbox[1] + bbox[3]) / 2) - y_origin) / pixel_height)
                # 创建一个256x256的空白图像
                image_data = np.zeros((stride_cut, stride_cut), dtype=np.uint8)
                count = count + 1
                for i in range(stride_cut):
                    for j in range(stride_cut):
                        # 将像素坐标转换为地理坐标
                        x_geo = x_origin + (center_x - (stride_cut / 2) + i) * pixel_width
                        y_geo = y_origin + (center_y - (stride_cut / 2) + j) * pixel_height
                        point = Point(x_geo, y_geo)

                        # 判断像素是否在要素范围内
                        if any(g.contains(point) for g in geometries):
                            image_data[j, i] = 255  # 白
                        else:
                            image_data[j, i] = 0  # 黑
                # 创建输出文件名
                output_filename = os.path.join(output_folder, f"{count}.tif")
                # 创建输出GeoTIFF文件
                driver = gdal.GetDriverByName("GTiff")
                output_dataset = driver.Create(output_filename, stride_cut, stride_cut, 1, gdal.GDT_Byte)
                output_dataset.SetGeoTransform((x_origin + (center_x - (stride_cut / 2)) * pixel_width, pixel_width, 0,
                                                y_origin + (center_y - (stride_cut / 2)) * pixel_height, 0,
                                                pixel_height))
                output_dataset.SetProjection(projection)
                output_band = output_dataset.GetRasterBand(1)
                output_band.WriteArray(image_data)
                output_band.FlushCache()
                output_dataset = None
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区


def label_shp_to_geotiff_new(shp, geotiff, output_folder, stride_cut, center_flag, Four_neighborhoods_flag,
                             corner_neighborhoods_flag):
    # 打开输入的 GeoTIFF 文件
    dataset = gdal.Open(geotiff, gdalconst.GA_ReadOnly)
    if dataset is None:
        sys.stdout.write("\r无法打开输入的 GeoTIFF 文件！")
        sys.stdout.flush()  # 强制刷新输出缓冲区
        return

    # 获取输入 GeoTIFF 文件的地理变换信息
    geo_transform = dataset.GetGeoTransform()
    projection = dataset.GetProjection()
    pixel_width = geo_transform[1]
    pixel_height = geo_transform[5]

    # 创建输出文件夹
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    sys.stdout.write("\rlabel切片处理")
    sys.stdout.flush()  # 强制刷新输出缓冲区

    # 打开Shapefile文件
    with fiona.open(shp, "r") as shapefiles:
        geometries = []
        # 获取各要素几何并保存在列表中
        for feature in shapefiles:
            geom = shape(feature["geometry"])
            geometries.append(geom)
        # 记录shp文件要素数量
        num_elements = len(geometries)

        # 计算输出label图片数量
        if center_flag == '1':
            picture_count_center = num_elements * 1
        else:
            picture_count_center = 0

        if corner_neighborhoods_flag == '1':
            picture_count_corner = num_elements * 4
        else:
            picture_count_corner = 0

        if Four_neighborhoods_flag == '1':
            picture_count_neighbor = num_elements * 4
        else:
            picture_count_neighbor = 0

        picture_count = picture_count_center + picture_count_corner + picture_count_neighbor

        count = 0
        for geom in geometries:
            # 获得当前要素中心坐标和四角坐标
            center_point = geom.centroid
            bbox = geom.bounds

            if center_flag == '1':
                count = count + 1

                # 计算裁剪窗口左上角点的地理坐标
                upper_left_x = center_point.x - ((stride_cut / 2) * pixel_width)  # 左上角地理x坐标
                upper_left_y = center_point.y - ((stride_cut / 2) * pixel_height)  # 左上角地理y坐标

                # 计算裁剪窗口的像素范围
                pixel_x = int((upper_left_x - geo_transform[0]) / pixel_width)  # 左上角像素x坐标
                pixel_y = int((upper_left_y - geo_transform[3]) / pixel_height)  # 左上角像素y坐标
                slice_width = stride_cut
                slice_height = stride_cut

                output_tif = output_folder + '/' + f"{count}.tif"

                ulx = geo_transform[0] + (pixel_x * pixel_width)  # 左上角地理x坐标
                uly = geo_transform[3] + (pixel_y * pixel_height)  # 左上角地理y坐标
                lrx = ulx + (slice_width * pixel_width)  # 右下角地理x坐标
                lry = uly + (slice_height * pixel_height)  # 右下角地理y坐标

                gdal.Translate(output_tif, dataset, projWin=[ulx, uly, lrx, lry])

                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区

            if corner_neighborhoods_flag == '1':
                # 左上
                # 计算裁剪窗口左上角点的地理坐标
                upper_left_x = bbox[0]  # 外接矩形左侧地理x坐标
                upper_left_y = bbox[3]  # 外接矩形上侧地理y坐标
                # 计算裁剪窗口的像素范围
                pixel_x = int((upper_left_x - geo_transform[0]) / pixel_width)  # 左上角像素x坐标
                pixel_y = int((upper_left_y - geo_transform[3]) / pixel_height)  # 左上角像素y坐标
                slice_width = stride_cut
                slice_height = stride_cut
                count = count + 1
                output_tif = output_folder + '/' + f"{count}.tif"
                ulx = geo_transform[0] + (pixel_x * pixel_width)  # 左上角地理x坐标
                uly = geo_transform[3] + (pixel_y * pixel_height)  # 左上角地理y坐标
                lrx = ulx + (slice_width * pixel_width)  # 右下角地理x坐标
                lry = uly + (slice_height * pixel_height)  # 右下角地理y坐标
                gdal.Translate(output_tif, dataset, projWin=[ulx, uly, lrx, lry])
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区

                # 右上
                upper_left_x = bbox[2] - (stride_cut * pixel_width)  # 外接矩形右侧地理x坐标 - 裁剪窗口步长*地理分辨率
                upper_left_y = bbox[3]  # 外接矩形上侧地理y坐标
                # 计算裁剪窗口的像素范围
                pixel_x = int((upper_left_x - geo_transform[0]) / pixel_width)  # 左上角像素x坐标
                pixel_y = int((upper_left_y - geo_transform[3]) / pixel_height)  # 左上角像素y坐标
                slice_width = stride_cut
                slice_height = stride_cut
                count = count + 1
                output_tif = output_folder + '/' + f"{count}.tif"
                ulx = geo_transform[0] + (pixel_x * pixel_width)  # 左上角地理x坐标
                uly = geo_transform[3] + (pixel_y * pixel_height)  # 左上角地理y坐标
                lrx = ulx + (slice_width * pixel_width)  # 右下角地理x坐标
                lry = uly + (slice_height * pixel_height)  # 右下角地理y坐标
                gdal.Translate(output_tif, dataset, projWin=[ulx, uly, lrx, lry])
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区

                # 右下
                upper_left_x = bbox[2] - (stride_cut * pixel_width)  # 外接矩形右侧地理x坐标 - 裁剪窗口步长*地理分辨率
                upper_left_y = bbox[1] - (stride_cut * pixel_height)  # 外接矩形下侧地理y坐标 - 裁剪窗口步长*地理分辨率
                # 计算裁剪窗口的像素范围
                pixel_x = int((upper_left_x - geo_transform[0]) / pixel_width)  # 左上角像素x坐标
                pixel_y = int((upper_left_y - geo_transform[3]) / pixel_height)  # 左上角像素y坐标
                slice_width = stride_cut
                slice_height = stride_cut
                count = count + 1
                output_tif = output_folder + '/' + f"{count}.tif"
                ulx = geo_transform[0] + (pixel_x * pixel_width)  # 左上角地理x坐标
                uly = geo_transform[3] + (pixel_y * pixel_height)  # 左上角地理y坐标
                lrx = ulx + (slice_width * pixel_width)  # 右下角地理x坐标
                lry = uly + (slice_height * pixel_height)  # 右下角地理y坐标
                gdal.Translate(output_tif, dataset, projWin=[ulx, uly, lrx, lry])
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区

                # 左下
                # 计算裁剪窗口左上角点的地理坐标
                upper_left_x = bbox[0]  # 外接矩形左侧地理x坐标
                upper_left_y = bbox[1] - (stride_cut * pixel_height)  # 外接矩形下侧地理y坐标 - 裁剪窗口步长*地理分辨率
                # 计算裁剪窗口的像素范围
                pixel_x = int((upper_left_x - geo_transform[0]) / pixel_width)  # 左上角像素x坐标
                pixel_y = int((upper_left_y - geo_transform[3]) / pixel_height)  # 左上角像素y坐标
                slice_width = stride_cut
                slice_height = stride_cut
                count = count + 1
                output_tif = output_folder + '/' + f"{count}.tif"
                ulx = geo_transform[0] + (pixel_x * pixel_width)  # 左上角地理x坐标
                uly = geo_transform[3] + (pixel_y * pixel_height)  # 左上角地理y坐标
                lrx = ulx + (slice_width * pixel_width)  # 右下角地理x坐标
                lry = uly + (slice_height * pixel_height)  # 右下角地理y坐标
                gdal.Translate(output_tif, dataset, projWin=[ulx, uly, lrx, lry])
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区

            if Four_neighborhoods_flag == '1':
                # 下
                # 计算裁剪窗口左上角点的地理坐标
                upper_left_x = center_point.x - ((stride_cut / 2) * pixel_width)  # 外接矩形中间地理x坐标 - （裁剪窗口步长*地理分辨率 / 2）
                upper_left_y = bbox[1] - (stride_cut * pixel_height)  # 外接矩形下侧地理y坐标 - 裁剪窗口步长*地理分辨率
                # 计算裁剪窗口的像素范围
                pixel_x = int((upper_left_x - geo_transform[0]) / pixel_width)  # 左上角像素x坐标
                pixel_y = int((upper_left_y - geo_transform[3]) / pixel_height)  # 左上角像素y坐标
                slice_width = stride_cut
                slice_height = stride_cut
                count = count + 1
                output_tif = output_folder + '/' + f"{count}.tif"
                ulx = geo_transform[0] + (pixel_x * pixel_width)  # 左上角地理x坐标
                uly = geo_transform[3] + (pixel_y * pixel_height)  # 左上角地理y坐标
                lrx = ulx + (slice_width * pixel_width)  # 右下角地理x坐标
                lry = uly + (slice_height * pixel_height)  # 右下角地理y坐标
                gdal.Translate(output_tif, dataset, projWin=[ulx, uly, lrx, lry])
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区

                # 左
                upper_left_x = bbox[0]  # 外接矩形左侧地理x坐标
                upper_left_y = center_point.y - ((stride_cut / 2) * pixel_height)  # 外接矩形中间地理y坐标 - （裁剪窗口步长*地理分辨率 / 2）
                # 计算裁剪窗口的像素范围
                pixel_x = int((upper_left_x - geo_transform[0]) / pixel_width)  # 左上角像素x坐标
                pixel_y = int((upper_left_y - geo_transform[3]) / pixel_height)  # 左上角像素y坐标
                slice_width = stride_cut
                slice_height = stride_cut
                count = count + 1
                output_tif = output_folder + '/' + f"{count}.tif"
                ulx = geo_transform[0] + (pixel_x * pixel_width)  # 左上角地理x坐标
                uly = geo_transform[3] + (pixel_y * pixel_height)  # 左上角地理y坐标
                lrx = ulx + (slice_width * pixel_width)  # 右下角地理x坐标
                lry = uly + (slice_height * pixel_height)  # 右下角地理y坐标
                gdal.Translate(output_tif, dataset, projWin=[ulx, uly, lrx, lry])
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区

                # 上
                upper_left_x = center_point.x - ((stride_cut / 2) * pixel_width)  # 外接矩形中间地理x坐标 - （裁剪窗口步长*地理分辨率 / 2）
                upper_left_y = bbox[3]  # 外接矩形上侧地理y坐标
                # 计算裁剪窗口的像素范围
                pixel_x = int((upper_left_x - geo_transform[0]) / pixel_width)  # 左上角像素x坐标
                pixel_y = int((upper_left_y - geo_transform[3]) / pixel_height)  # 左上角像素y坐标
                slice_width = stride_cut
                slice_height = stride_cut
                count = count + 1
                output_tif = output_folder + '/' + f"{count}.tif"
                ulx = geo_transform[0] + (pixel_x * pixel_width)  # 左上角地理x坐标
                uly = geo_transform[3] + (pixel_y * pixel_height)  # 左上角地理y坐标
                lrx = ulx + (slice_width * pixel_width)  # 右下角地理x坐标
                lry = uly + (slice_height * pixel_height)  # 右下角地理y坐标
                gdal.Translate(output_tif, dataset, projWin=[ulx, uly, lrx, lry])
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区

                # 右
                upper_left_x = bbox[2] - (stride_cut * pixel_width)  # 外接矩形右侧地理x坐标 - 裁剪窗口步长*地理分辨率
                upper_left_y = center_point.y - ((stride_cut / 2) * pixel_height)  # 外接矩形中间地理y坐标 - （裁剪窗口步长*地理分辨率 / 2）
                # 计算裁剪窗口的像素范围
                pixel_x = int((upper_left_x - geo_transform[0]) / pixel_width)  # 左上角像素x坐标
                pixel_y = int((upper_left_y - geo_transform[3]) / pixel_height)  # 左上角像素y坐标
                slice_width = stride_cut
                slice_height = stride_cut
                count = count + 1
                output_tif = output_folder + '/' + f"{count}.tif"
                ulx = geo_transform[0] + (pixel_x * pixel_width)  # 左上角地理x坐标
                uly = geo_transform[3] + (pixel_y * pixel_height)  # 左上角地理y坐标
                lrx = ulx + (slice_width * pixel_width)  # 右下角地理x坐标
                lry = uly + (slice_height * pixel_height)  # 右下角地理y坐标
                gdal.Translate(output_tif, dataset, projWin=[ulx, uly, lrx, lry])
                sys.stdout.write(f"\rlabel切片中 : {count}/{picture_count}")
                sys.stdout.flush()  # 强制刷新输出缓冲区


def numerical_sort(value):
    return int(''.join(filter(str.isdigit, value)))


def get_geotiff_corners(folder_path):
    # 存储左上角坐标的列表
    corners_list = []
    corners_list_1 = []
    corners_list2 = []

    # 获取文件夹中所有的GeoTIFF文件路径
    tiff_files = [f for f in os.listdir(folder_path) if f.endswith('.tif')]

    # 对文件列表进行排序
    tiff_files_sorted = sorted(tiff_files, key=numerical_sort)

    for tiff_file in tiff_files_sorted:
        tiff_path = os.path.join(folder_path, tiff_file)

        # 打开GeoTIFF文件
        dataset = gdal.Open(tiff_path, gdal.GA_ReadOnly)

        if dataset is None:
            sys.stdout.write(f"\r无法打开文件: {tiff_path}")
            sys.stdout.flush()  # 强制刷新输出缓冲区
            continue

        # 获取左上角地理坐标
        geotransform = dataset.GetGeoTransform()
        if geotransform is None:
            sys.stdout.write(f"\r无法获取地理坐标信息: {tiff_path}")
            sys.stdout.flush()  # 强制刷新输出缓冲区
            continue

        ulx = geotransform[0]
        uly = geotransform[3]

        pixel_width = geotransform[1]
        pixel_height = geotransform[5]
        width = dataset.RasterXSize
        height = dataset.RasterYSize

        # 计算右下角坐标
        lrx = ulx + (width * pixel_width)
        lry = uly + (height * pixel_height)

        # 将坐标添加到列表中
        corners_list.append((ulx, uly))
        corners_list_1.append((ulx, uly, lrx, lry))
        corners_list2.append((tiff_file, (ulx, uly), (lrx, lry)))
    # 关闭数据集
    dataset = None
    return corners_list, corners_list2, corners_list_1


def crop_geotiff(input_tiff, output_folder, coordinates_list, stride_cut):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 打开输入的 GeoTIFF 文件
    dataset = gdal.Open(input_tiff, gdalconst.GA_ReadOnly)
    if dataset is None:
        sys.stdout.write("\r无法打开输入的 GeoTIFF 文件！")
        sys.stdout.flush()  # 强制刷新输出缓冲区
        return

    # 获取输入 GeoTIFF 文件的地理变换信息
    geo_transform = dataset.GetGeoTransform()
    projection = dataset.GetProjection()
    pixel_width = geo_transform[1]
    pixel_height = geo_transform[5]

    sys.stdout.write("\rImage切片处理")
    sys.stdout.flush()  # 强制刷新输出缓冲区

    image_count = len(coordinates_list)
    # 循环裁剪每个坐标点
    for i, (upper_left_x, upper_left_y) in enumerate(coordinates_list):
        # 计算裁剪窗口的像素范围
        pixel_x = int((upper_left_x - geo_transform[0]) / pixel_width)  # 左上角像素x坐标
        pixel_y = int((upper_left_y - geo_transform[3]) / pixel_height)  # 左上角像素y坐标
        width = stride_cut
        height = stride_cut

        output_tif = output_folder + '/' + f"{i + 1}.tif"

        ulx = geo_transform[0] + (pixel_x * geo_transform[1])
        uly = geo_transform[3] + (pixel_y * geo_transform[5])
        lrx = ulx + (width * geo_transform[1])
        lry = uly + (height * geo_transform[5])

        # gdal.Translate(output_tif, dataset, projWin=[ulx, uly, lrx, lry])
        gdal.Translate(output_tif, dataset, projWin=[ulx, uly, lrx, lry])

        sys.stdout.write(f"\rImage切片中 : {i + 1}/{image_count}")
        sys.stdout.flush()  # 强制刷新输出缓冲区

    # 关闭输入 GeoTIFF 文件
    dataset = None


def crop_dem(input_tiff, output_folder, coordinates_list):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 打开输入的 GeoTIFF 文件
    dataset = gdal.Open(input_tiff, gdalconst.GA_ReadOnly)
    if dataset is None:
        sys.stdout.write("\r无法打开输入的 GeoTIFF 文件！")
        sys.stdout.flush()  # 强制刷新输出缓冲区
        return

    # 获取输入 GeoTIFF 文件的地理变换信息
    geo_transform = dataset.GetGeoTransform()
    projection = dataset.GetProjection()
    pixel_width = geo_transform[1]
    pixel_height = geo_transform[5]

    sys.stdout.write("\rDEM切片处理")
    sys.stdout.flush()  # 强制刷新输出缓冲区

    image_count = len(coordinates_list)
    # 循环裁剪每个坐标点
    for i, (upper_left_x, upper_left_y, down_right_x, down_right_y) in enumerate(coordinates_list):
        # 计算裁剪窗口的像素范围
        pixel_x = int((upper_left_x - geo_transform[0]) / pixel_width)  # 左上角像素x坐标
        pixel_y = int((upper_left_y - geo_transform[3]) / pixel_height)  # 左上角像素y坐标
        right_pixel_x = int((down_right_x - geo_transform[0]) / pixel_width)  # 右下角像素x坐标
        right_pixel_y = int((down_right_y - geo_transform[3]) / pixel_height)  # 右下角像素y坐标

        output_tif = output_folder + '/' + f"{i + 1}.tif"

        ulx = geo_transform[0] + ((pixel_x - 1) * geo_transform[1])
        uly = geo_transform[3] + ((pixel_y - 1) * geo_transform[5])
        lrx = geo_transform[0] + ((right_pixel_x + 1) * geo_transform[1])
        lry = geo_transform[3] + ((right_pixel_y + 1) * geo_transform[5])

        # gdal.Translate(output_tif, dataset, projWin=[ulx, uly, lrx, lry])
        gdal.Translate(output_tif, dataset, projWin=[ulx, uly, lrx, lry], format='GTiff',
                       creationOptions=['COMPRESS=NONE', 'PHOTOMETRIC=MINISBLACK', 'INTERLEAVE=PIXEL', 'TILED=YES',
                                        'NBITS=32'],
                       outputType=gdal.GDT_Float32)

        sys.stdout.write(f"\rDEM切片中 : {i + 1}/{image_count}")
        sys.stdout.flush()  # 强制刷新输出缓冲区

    # 关闭输入 GeoTIFF 文件
    dataset = None


def crop_dem_fine(input_tiff, output_tif, upper_left_x, upper_left_y, down_right_x, down_right_y):

    # 打开输入的 GeoTIFF 文件
    dataset = gdal.Open(input_tiff, gdalconst.GA_ReadOnly)
    if dataset is None:
        sys.stdout.write("\r无法打开输入的 GeoTIFF 文件！")
        sys.stdout.flush()  # 强制刷新输出缓冲区
        return

    # 获取输入 GeoTIFF 文件的地理变换信息
    geo_transform = dataset.GetGeoTransform()
    projection = dataset.GetProjection()
    pixel_width = geo_transform[1]
    pixel_height = geo_transform[5]

    # 计算裁剪窗口的像素范围
    pixel_x = int((upper_left_x - geo_transform[0]) / pixel_width)  # 左上角像素x坐标
    pixel_y = int((upper_left_y - geo_transform[3]) / pixel_height)  # 左上角像素y坐标
    right_pixel_x = int((down_right_x - geo_transform[0]) / pixel_width)  # 右下角像素x坐标
    right_pixel_y = int((down_right_y - geo_transform[3]) / pixel_height)  # 右下角像素y坐标


    ulx = geo_transform[0] + (pixel_x * geo_transform[1])
    uly = geo_transform[3] + (pixel_y * geo_transform[5])
    lrx = geo_transform[0] + (right_pixel_x * geo_transform[1])
    lry = geo_transform[3] + (right_pixel_y * geo_transform[5])

    # gdal.Translate(output_tif, dataset, projWin=[ulx, uly, lrx, lry])
    gdal.Translate(output_tif, dataset, projWin=[ulx, uly, lrx, lry], format='GTiff',
                    creationOptions=['COMPRESS=NONE', 'PHOTOMETRIC=MINISBLACK', 'INTERLEAVE=PIXEL', 'TILED=YES',
                                    'NBITS=32'],
                    outputType=gdal.GDT_Float32)

    # 关闭输入 GeoTIFF 文件
    dataset = None


def resampled_dem(input_path, output_path, input_pixel_stride, output_pixel_stride):
    # 打开输入文件
    ds = gdal.Open(input_path)
    if ds is None:
        raise FileNotFoundError(f"Unable to open {input_path}")

    # 获取输入的元数据
    geotransform = ds.GetGeoTransform()
    projection = ds.GetProjection()

    scale_factor = input_pixel_stride / output_pixel_stride

    # 更新地理变换
    new_geotransform = (
        geotransform[0],
        geotransform[1] / scale_factor,  # 新的像素大小
        geotransform[2],
        geotransform[3],
        geotransform[4],
        geotransform[5] / scale_factor  # 新的像素大小
    )

    # 计算新的图像尺寸
    new_width = int(ds.RasterXSize * scale_factor)
    new_height = int(ds.RasterYSize * scale_factor)

    # 创建输出文件
    driver = gdal.GetDriverByName('GTiff')
    out_ds = driver.Create(output_path, new_width, new_height, 1, gdal.GDT_Float32)

    # 设置新的地理变换和投影
    out_ds.SetGeoTransform(new_geotransform)
    out_ds.SetProjection(projection)

    # 读取输入波段的数据
    band = ds.GetRasterBand(1)
    data = band.ReadAsArray()

    # 进行重采样
    resampled_data = band.ReadAsArray(buf_xsize=new_width, buf_ysize=new_height, resample_alg=gdal.GRA_Bilinear)

    # 将重采样后的数据写入输出文件
    out_band = out_ds.GetRasterBand(1)
    out_band.WriteArray(resampled_data)

    # 关闭数据集
    ds = None
    out_ds = None


def tiff_to_png(input_folder, output_folder, slice_number):
    # 创建输出文件夹
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    count = 0
    # 遍历输入文件夹中的所有文件
    for filename in os.listdir(input_folder):
        if filename.endswith('.tif'):
            # 构建输入文件的完整路径
            input_path = os.path.join(input_folder, filename)
            count = count + 1

            # 打开GeoTIFF文件
            dataset = gdal.Open(input_path)
            if dataset is None:
                sys.stdout.write(f"\r无法打开文件：{input_path}")
                sys.stdout.flush()  # 强制刷新输出缓冲区
                continue

            # 生成输出文件的完整路径
            output_filename = os.path.splitext(filename)[0] + '.jpg'
            output_path = os.path.join(output_folder, output_filename)

            # 设置转换选项
            options = gdal.TranslateOptions(format='JPEG', outputType=gdal.GDT_Byte)
            # 执行转换
            gdal.Translate(output_path, dataset, options=options)
            sys.stdout.write(f"\r图像格式转换中 : {count}/{slice_number}")
            sys.stdout.flush()  # 强制刷新输出缓冲区

    count = 0
    delete_xml_files(output_folder)
    for file in os.listdir(output_folder):
        if file.endswith('.jpg'):
            count = count + 1
            # 构造输入文件的完整路径
            input_path = os.path.join(output_folder, file)
            # 构造输出文件的完整路径，并将后缀改为.png
            output_path = os.path.join(output_folder, os.path.splitext(file)[0] + '.png')
            img = Image.open(input_path)
            # 保存为png格式
            img.save(output_path, 'PNG')
            os.remove(input_path)
            sys.stdout.write(f"\rpng图像生成 : {count}/{slice_number}")
            sys.stdout.flush()  # 强制刷新输出缓冲区


def delete_xml_files(folder_path):
    # 使用glob.glob查找文件夹中的所有xml文件
    xml_files = glob.glob(os.path.join(folder_path, '*.xml'))
    # 删除找到的每个xml文件
    for file in xml_files:
        os.remove(file)


def process_dem_folder(folder_path, dem_png_out):
    # 创建输出文件夹
    output_folder = dem_png_out
    os.makedirs(output_folder, exist_ok=True)

    # 获取文件夹中所有的DEM文件路径
    dem_files = [file for file in os.listdir(folder_path) if file.endswith(".tif")]

    for dem_file in dem_files:
        # 读取DEM文件
        dem_path = os.path.join(folder_path, dem_file)
        dataset = gdal.Open(dem_path)
        band = dataset.GetRasterBand(1)
        dem_array = band.ReadAsArray()

        # 获取最大和最小高程值
        max_elevation = dem_array.max()
        min_elevation = dem_array.min()

        # 将DEM数据映射到0到255的灰度范围
        scaled_array = ((dem_array - min_elevation) / (max_elevation - min_elevation)) * 255
        scaled_array = scaled_array.clip(0, 255)  # 确保灰度值在0到255之间

        # 创建灰度图像
        img = Image.fromarray(scaled_array.astype('uint8'), 'L')

        # 保存灰度图像
        output_filename = os.path.splitext(dem_file)[0] + ".png"
        output_path = os.path.join(output_folder, output_filename)
        img.save(output_path)


def cut_slice(input_dem, input_geotiff, input_shp, workspace, stride, center, Four_neighborhoods, corner_neighborhoods, ori_pixel, resampled_pixel):
    output_raster_file = workspace + r'\temp_output.tif'

    output_folder_image = workspace + '/' + "slice_image_tif"
    output_folder_label = workspace + '/' + "slice_label_tif"

    output_image_png = workspace + '/' + "slice_image_png"
    output_label_png = workspace + '/' + "slice_label_png"

    temp_dem = workspace + '/' + "original_DEM_tif"
    resampled_folder_dem = workspace + '/' + "resampled_slice_DEM_tif"
    folder_dem = workspace + '/' + "slice_DEM_tif"
    dem_out_png = workspace + '/' + "slice_DEM_png"

    output_xml_dir = workspace + '/' + "xml"

    shp_to_geotiff(input_shp, input_geotiff, output_raster_file)
    # # 根据shp输出tif格式的label切片
    label_shp_to_geotiff_new(input_shp, output_raster_file, output_folder_label, int(stride), center,
                             Four_neighborhoods,
                             corner_neighborhoods)
    os.remove(output_raster_file)
    # 获取每个tif格式的label切片的左上角坐标
    coords_list = get_geotiff_corners(output_folder_label)[0]
    # 根据左上角坐标在tif格式的image大图中裁剪输出image切片
    crop_geotiff(input_geotiff, output_folder_image, coords_list, int(stride))

    picture_num = len(coords_list)

    if input_dem != '':
        coords_list_1 = get_geotiff_corners(output_folder_label)[2]

        if ori_pixel != '' and resampled_pixel != '':
            # 根据左上角、右下角坐标在dem中裁剪切片
            crop_dem(input_dem, temp_dem, coords_list_1)
            # 重采样
            if not os.path.exists(resampled_folder_dem):
                os.makedirs(resampled_folder_dem)
            count = 0
            for filename in os.listdir(temp_dem):
                input_path = os.path.join(temp_dem, filename)
                output_path = os.path.join(resampled_folder_dem, filename)
                count += 1
                sys.stdout.write(f"\rDEM重采样{count}/{picture_num}")
                sys.stdout.flush()  # 强制刷新输出缓冲区
                resampled_dem(input_path, output_path, float(ori_pixel), float(resampled_pixel))
        else:
            # 根据左上角、右下角坐标在dem中裁剪切片
            crop_dem(input_dem, resampled_folder_dem, coords_list_1)

        count = 0
        if not os.path.exists(folder_dem):
            os.makedirs(folder_dem)
        # 根据左上角、右下角坐标在重采样后的dem中裁剪准确大小切片
        for i, (upper_left_x, upper_left_y, down_right_x, down_right_y) in enumerate(coords_list_1):
            count += 1
            sys.stdout.write(f"\rDEM精确切片 {count}/{picture_num}")
            sys.stdout.flush()  # 强制刷新输出缓冲区

            input_path = resampled_folder_dem + f'/{count}.tif'
            output_path = folder_dem + f'/{count}.tif'
            crop_dem_fine(input_path, output_path, upper_left_x, upper_left_y, down_right_x, down_right_y)

        process_dem_folder(folder_dem, dem_out_png)

    # 将tif格式的切片转换为png图像切片
    sys.stdout.write("\r===========影像格式转换===========")
    sys.stdout.flush()  # 强制刷新输出缓冲区
    tiff_to_png(output_folder_image, output_image_png, picture_num)
    sys.stdout.write("\r===========切片格式转换===========")
    sys.stdout.flush()  # 强制刷新输出缓冲区
    tiff_to_png(output_folder_label, output_label_png, picture_num)

    coords_list_xml = get_geotiff_corners(output_folder_label)[1]
    if not os.path.exists(output_xml_dir):
        os.mkdir(output_xml_dir)
    for item in coords_list_xml:
        Filename = item[0]
        upper_left = item[1]
        lower_right = item[2]

        upper_left_x, upper_left_y = upper_left
        lower_right_x, lower_right_y = lower_right

        upper_left_x_str = str(upper_left_x)
        upper_left_y_str = str(upper_left_y)
        lower_right_x_str = str(lower_right_x)
        lower_right_y_str = str(lower_right_y)

        output_xml = output_xml_dir + '/' + Filename[:-4] + '.xml'

        # 创建 XML 树
        root = ET.Element("Document")
        filename = ET.SubElement(root, "filename")
        filename.text = f"{Filename}"
        source = ET.SubElement(root, "source")
        source.text = f"{Source}"
        resolution = ET.SubElement(root, "resolution")
        resolution.text = f"{Resolution}"
        image_phase = ET.SubElement(root, "Image_phase")
        image_phase.text = f"{Sourece_time}"
        data_type = ET.SubElement(root, "data_type")
        data_type.text = f"{Data_type}"
        data_depth = ET.SubElement(root, "data_depth")
        data_depth.text = f"{Data_depth}"
        grade = ET.SubElement(root, "grade")
        grade.text = f"{Grade}"

        district = ET.SubElement(root, "district")
        province = ET.SubElement(district, "province")
        province.text = f"{Province}"
        municipal = ET.SubElement(district, "Municipal")
        municipal.text = f"{Municipal}"
        county = ET.SubElement(district, "county")
        county.text = f"{County}"

        size = ET.SubElement(root, "size")
        simple_width = ET.SubElement(size, "SimpleWidth")
        simple_width.text = f"{stride}"
        simple_height = ET.SubElement(size, "SimpleHeight")
        simple_height.text = f"{stride}"

        spatial_reference = ET.SubElement(root, "Spatial_reference")
        spatial_reference.text = f"{Spatial_reference}"

        bnd_box = ET.SubElement(root, "bndBox")
        Xmin = ET.SubElement(bnd_box, "xmin")
        Xmin.text = str(upper_left_x_str)
        Ymin = ET.SubElement(bnd_box, "ymin")
        Ymin.text = str(upper_left_y_str)
        Xmax = ET.SubElement(bnd_box, "xmax")
        Xmax.text = str(lower_right_x_str)
        Ymax = ET.SubElement(bnd_box, "ymax")
        Ymax.text = str(lower_right_y_str)

        label_information = ET.SubElement(root, "label_Information")
        class_name = ET.SubElement(label_information, "class_name")
        class_name.text = f"{Label_name}"
        classification = ET.SubElement(label_information, "classification")
        classification.text = f"{Classification}"

        organization_information = ET.SubElement(root, "Organization_Information")
        company_name = ET.SubElement(organization_information, "Compony_name")
        company_name.text = f"{Name}"
        address = ET.SubElement(organization_information, "address")
        address.text = f"{Address}"
        telephone = ET.SubElement(organization_information, "Telephone")
        telephone.text = f"{Email}"

        tree = ET.ElementTree(root)
        tree.write(output_xml, encoding="utf-8", xml_declaration=True)


def shp_to_geotiff(shp_file, input_raster_file, output_raster_file):
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


def clip_geotiff(input_file, output_folder, window_size, stride):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 打开Geotiff图像
    dataset = gdal.Open(input_file)
    if dataset is None:
        print("无法打开输入文件")
        return

    sys.stdout.write("\rlabel切片处理")
    sys.stdout.flush()  # 强制刷新输出缓冲区

    width = dataset.RasterXSize
    height = dataset.RasterYSize
    count = 0
    for y in range(0, height - window_size + 1, stride):
        for x in range(0, width - window_size + 1, stride):
            # 读取窗口内的像素值
            window_data = dataset.ReadAsArray(x, y, window_size, window_size)
            # 检查窗口内是否有白色像素
            if np.any(window_data == 255):
                # 记录窗口左上角和右下角的像素坐标
                count = count + 1
                upper_left_pixel = (x, y)
                lower_right_pixel = (x + window_size - 1, y + window_size - 1)

                # 根据像素坐标获取地理坐标
                gt = dataset.GetGeoTransform()
                upper_left_geo = (gt[0] + upper_left_pixel[0] * gt[1], gt[3] + upper_left_pixel[1] * gt[5])
                # lower_right_geo = (gt[0] + lower_right_pixel[0] * gt[1], gt[3] + lower_right_pixel[1] * gt[5])

                # 输出裁剪后的切片图像
                output_filename = f"{count}.tif"
                sys.stdout.write(f"\rlabel切片中 : {count}/UnKnown")
                sys.stdout.flush()  # 强制刷新输出缓冲区
                output_path = os.path.join(output_folder, output_filename)
                driver = gdal.GetDriverByName('GTiff')
                out_dataset = driver.Create(output_path, window_size, window_size, 1, gdal.GDT_Byte)
                out_dataset.SetGeoTransform((upper_left_geo[0], gt[1], gt[2], upper_left_geo[1], gt[4], gt[5]))
                out_dataset.GetRasterBand(1).WriteArray(window_data)
                out_dataset = None

    dataset = None


def cut_slice_stride(input_dem, input_geotiff, input_shp, workspace, size, stride, ori_pixel, resampled_pixel):
    output_raster_file = workspace + r'\temp_output.tif'

    output_folder_image = workspace + '/' + "slice_image_tif"
    output_folder_label = workspace + '/' + "slice_label_tif"

    output_image_png = workspace + '/' + "slice_image_png"
    output_label_png = workspace + '/' + "slice_label_png"

    temp_dem = workspace + '/' + "original_DEM_tif"
    resampled_folder_dem = workspace + '/' + "resampled_slice_DEM_tif"
    folder_dem = workspace + '/' + "slice_DEM_tif"
    dem_out_png = workspace + '/' + "slice_DEM_png"

    output_xml_dir = workspace + '/' + "xml"

    shp_to_geotiff(input_shp, input_geotiff, output_raster_file)
    clip_geotiff(output_raster_file, output_folder_label, int(size), int(stride))
    os.remove(output_raster_file)

    coords_list = get_geotiff_corners(output_folder_label)[0]

    picture_num = len(coords_list)

    crop_geotiff(input_geotiff, output_folder_image, coords_list, int(size))

    if input_dem != '':
        coords_list_1 = get_geotiff_corners(output_folder_label)[2]

        if ori_pixel != '' and resampled_pixel != '':
            # 根据左上角、右下角坐标在dem中裁剪切片
            crop_dem(input_dem, temp_dem, coords_list_1)
            # 重采样
            if not os.path.exists(resampled_folder_dem):
                os.makedirs(resampled_folder_dem)
            count = 0
            for filename in os.listdir(temp_dem):
                input_path = os.path.join(temp_dem, filename)
                output_path = os.path.join(resampled_folder_dem, filename)
                count += 1
                sys.stdout.write(f"\rDEM重采样{count}/{picture_num}")
                sys.stdout.flush()  # 强制刷新输出缓冲区
                resampled_dem(input_path, output_path, float(ori_pixel), float(resampled_pixel))
        else:
            # 根据左上角、右下角坐标在dem中裁剪切片
            crop_dem(input_dem, resampled_folder_dem, coords_list_1)

        # os.rmdir(temp_dem)
        count = 0
        if not os.path.exists(folder_dem):
            os.makedirs(folder_dem)
        # 根据左上角、右下角坐标在重采样后的dem中裁剪准确大小切片
        for i, (upper_left_x, upper_left_y, down_right_x, down_right_y) in enumerate(coords_list_1):
            count += 1
            sys.stdout.write(f"\rDEM精确切片 {count}/{picture_num}")
            sys.stdout.flush()  # 强制刷新输出缓冲区

            input_path = resampled_folder_dem + f'/{count}.tif'
            output_path = folder_dem + f'/{count}.tif'
            crop_dem_fine(input_path, output_path, upper_left_x, upper_left_y, down_right_x, down_right_y)

        process_dem_folder(folder_dem, dem_out_png)

    # 将tif格式的切片转换为png图像切片
    sys.stdout.write("\r===========影像格式转换===========")
    sys.stdout.flush()  # 强制刷新输出缓冲区
    tiff_to_png(output_folder_image, output_image_png, picture_num)
    sys.stdout.write("\r===========切片格式转换===========")
    sys.stdout.flush()  # 强制刷新输出缓冲区
    tiff_to_png(output_folder_label, output_label_png, picture_num)

    coords_list_xml = get_geotiff_corners(output_folder_label)[1]

    if not os.path.exists(output_xml_dir):
        os.mkdir(output_xml_dir)
    for item in coords_list_xml:
        Filename = item[0]
        upper_left = item[1]
        lower_right = item[2]

        upper_left_x, upper_left_y = upper_left
        lower_right_x, lower_right_y = lower_right

        upper_left_x_str = str(upper_left_x)
        upper_left_y_str = str(upper_left_y)
        lower_right_x_str = str(lower_right_x)
        lower_right_y_str = str(lower_right_y)

        output_xml = output_xml_dir + '/' + Filename[:-4] + '.xml'

        # 创建 XML 树
        root = ET.Element("Document")
        filename = ET.SubElement(root, "filename")
        filename.text = f"{Filename}"
        source = ET.SubElement(root, "source")
        source.text = f"{Source}"
        resolution = ET.SubElement(root, "resolution")
        resolution.text = f"{Resolution}"
        image_phase = ET.SubElement(root, "Image_phase")
        image_phase.text = f"{Sourece_time}"
        data_type = ET.SubElement(root, "data_type")
        data_type.text = f"{Data_type}"
        data_depth = ET.SubElement(root, "data_depth")
        data_depth.text = f"{Data_depth}"
        grade = ET.SubElement(root, "grade")
        grade.text = f"{Grade}"

        district = ET.SubElement(root, "district")
        province = ET.SubElement(district, "province")
        province.text = f"{Province}"
        municipal = ET.SubElement(district, "Municipal")
        municipal.text = f"{Municipal}"
        county = ET.SubElement(district, "county")
        county.text = f"{County}"

        Size = ET.SubElement(root, "size")
        simple_width = ET.SubElement(Size, "SimpleWidth")
        simple_width.text = f"{size}"
        simple_height = ET.SubElement(Size, "SimpleHeight")
        simple_height.text = f"{size}"

        spatial_reference = ET.SubElement(root, "Spatial_reference")
        spatial_reference.text = f"{Spatial_reference}"

        bnd_box = ET.SubElement(root, "bndBox")
        Xmin = ET.SubElement(bnd_box, "xmin")
        Xmin.text = str(upper_left_x_str)
        Ymin = ET.SubElement(bnd_box, "ymin")
        Ymin.text = str(upper_left_y_str)
        Xmax = ET.SubElement(bnd_box, "xmax")
        Xmax.text = str(lower_right_x_str)
        Ymax = ET.SubElement(bnd_box, "ymax")
        Ymax.text = str(lower_right_y_str)

        label_information = ET.SubElement(root, "label_Information")
        class_name = ET.SubElement(label_information, "class_name")
        class_name.text = f"{Label_name}"
        classification = ET.SubElement(label_information, "classification")
        classification.text = f"{Classification}"

        organization_information = ET.SubElement(root, "Organization_Information")
        company_name = ET.SubElement(organization_information, "Compony_name")
        company_name.text = f"{Name}"
        address = ET.SubElement(organization_information, "address")
        address.text = f"{Address}"
        telephone = ET.SubElement(organization_information, "Telephone")
        telephone.text = f"{Email}"

        tree = ET.ElementTree(root)
        tree.write(output_xml, encoding="utf-8", xml_declaration=True)


def get_corners(dataset):
    geotransform = dataset.GetGeoTransform()
    top_left = (geotransform[0], geotransform[3])
    bottom_right = (geotransform[0] + geotransform[1] * dataset.RasterXSize,
                    geotransform[3] + geotransform[5] * dataset.RasterYSize)
    return top_left, bottom_right


def check_containment(file_a, file_b):
    dataset_a = gdal.Open(file_a)
    dataset_b = gdal.Open(file_b)

    a_top_left, a_bottom_right = get_corners(dataset_a)
    b_top_left, b_bottom_right = get_corners(dataset_b)

    if not (a_top_left[0] <= b_top_left[0] and a_top_left[1] >= b_top_left[1] and
            a_bottom_right[0] >= b_bottom_right[0] and a_bottom_right[1] <= b_bottom_right[1]):
        return 1


class ConsoleRedirector:
    def __init__(self, text_edit):
        self.text_edit = text_edit

    def write(self, message):
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(message)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()  # 确保光标可见

        # 实时刷新界面
        QApplication.processEvents()

    def flush(self):
        pass


class Resample_windows(QWidget):

    def __init__(self):
        super().__init__()
        self.input_stride = None
        self.output_stride = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle("DEM重采样")

        input_pixel_stride = QLabel("原始像素大小 : ")
        input_pixel_stride.setFont(QFont("Times New Roman", 12))
        self.input_stride = QLineEdit()
        self.input_stride.setFixedSize(80, 30)

        onput_pixel_stride = QLabel("目标像素大小 : ")
        onput_pixel_stride.setFont(QFont("Times New Roman", 12))
        self.output_stride = QLineEdit()
        self.output_stride.setFixedSize(80, 30)

        run_button = QPushButton("确认")
        run_button.clicked.connect(self.runClicked)
        run_button.setFixedSize(200, 50)

        hbox1 = QHBoxLayout()
        hbox1.addWidget(input_pixel_stride)
        hbox1.addWidget(self.input_stride)
        hbox1.addWidget(onput_pixel_stride)
        hbox1.addWidget(self.output_stride)

        hbox2 = QHBoxLayout()
        hbox2.addWidget(run_button)

        vbox = QVBoxLayout()

        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)

        self.setLayout(vbox)
        self.show()

    def runClicked(self):
        global Ori_Pixel_Stride, Resampled_Pixel_Stride
        Ori_Pixel_Stride = self.input_stride.text()
        Resampled_Pixel_Stride = self.output_stride.text()
        self.close()


# 图像切片——遍历要素
class MyWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.four = None
        self.center = None
        self.geotiff_input = None
        self.dem_input = None
        self.shp_input = None
        self.stride = None
        self.workspace_input = None
        self.corner = None
        self.output_text = None
        self.initUI()

    def open_dialog0(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "TIFF Files (*.tif *.tiff)")
        if file_path:
            self.dem_input.setText(file_path)

    def open_dialog1(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "TIFF Files (*.tif *.tiff)")
        if file_path:
            self.geotiff_input.setText(file_path)

    def open_dialog2(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "Shapefile (*.shp)")
        if file_path:
            self.shp_input.setText(file_path)

    def open_dialog3(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹", "/")
        if folder_path:
            self.workspace_input.setText(folder_path)

    def initUI(self):

        # self.setStyleSheet('''QWidget{background-color:#66CCFF;}''')

        self.setWindowTitle("图像切片——遍历要素")
        self.setGeometry(800, 300, 500, 400)

        geotiff_input_label = QLabel("     输入影像 :  ")
        geotiff_input_label.setFont(QFont("Times New Roman", 12))
        self.geotiff_input = QLineEdit()
        self.geotiff_input.setReadOnly(True)  # 设置为只读
        self.geotiff_input.setFixedSize(160, 30)

        dem_input_label = QLabel("输入DEM(可选) : ")
        dem_input_label.setFont(QFont("Times New Roman", 12))
        self.dem_input = QLineEdit()
        self.dem_input.setReadOnly(True)  # 设置为只读
        self.dem_input.setFixedSize(120, 30)

        shp_input_label = QLabel("     输入shp : ")
        shp_input_label.setFont(QFont("Times New Roman", 12))
        self.shp_input = QLineEdit()
        self.shp_input.setReadOnly(True)  # 设置为只读
        self.shp_input.setFixedSize(160, 30)

        workspace_label = QLabel("     输出路径:")
        workspace_label.setFont(QFont("Times New Roman", 12))
        self.workspace_input = QLineEdit()
        self.workspace_input.setReadOnly(True)  # 设置为只读
        self.workspace_input.setFixedSize(160, 30)  # 设置输入框的大小

        stride_label = QLabel("裁剪窗口大小：")
        stride_label.setFont(QFont("Times New Roman", 12))
        self.stride = QComboBox()
        self.stride.addItems(["64", "128", "256", "512", "1024"])
        self.stride.setFont(QFont("Times New Roman", 12))
        self.stride.setFixedSize(80, 40)  # 设置下拉框的大小

        center_label = QLabel("中心点:")
        center_label.setFont(QFont("Times New Roman", 12))
        self.center = QComboBox()
        self.center.addItems(["√", "-"])  # 替换为你的选择项
        self.center.setFont(QFont("Times New Roman", 12))
        self.center.setFixedSize(60, 30)  # 设置下拉框的大小

        four_label = QLabel("            四边:")
        four_label.setFont(QFont("Times New Roman", 12))
        self.four = QComboBox()
        self.four.addItems(["√", "-"])  # 替换为你的选择项
        self.four.setFont(QFont("Times New Roman", 12))
        self.four.setFixedSize(60, 30)  # 设置下拉框的大小

        corner_label = QLabel("            四角:")
        corner_label.setFont(QFont("Times New Roman", 12))
        self.corner = QComboBox()
        self.corner.addItems(["√", "-"])  # 替换为你的选择项
        self.corner.setFont(QFont("Times New Roman", 12))
        self.corner.setFixedSize(60, 30)  # 设置下拉框的大小

        run_button = QPushButton("开始运行")
        run_button.clicked.connect(self.runClicked_check)
        run_button.clicked.connect(self.runClicked)
        run_button.setFixedSize(100, 50)

        resample_button = QPushButton("DEM重采样")
        resample_button.clicked.connect(self.Clicked_resample)
        resample_button.setFixedSize(100, 50)

        # 创建 QTextEdit 控件用于显示输出信息
        self.output_text = QTextEdit()
        self.output_text.setFixedSize(500, 150)
        self.output_text.setReadOnly(True)  # 设置为只读

        # 创建垂直布局，并将控件添加到布局中
        vbox = QVBoxLayout()

        # 创建各个控件
        self.button_dem = QPushButton('浏览', self)
        self.button_dem.clicked.connect(self.open_dialog0)

        self.button_geotiff = QPushButton('浏览', self)
        self.button_geotiff.clicked.connect(self.open_dialog1)

        self.button_shp = QPushButton('浏览', self)
        self.button_shp.clicked.connect(self.open_dialog2)

        self.button_workspace = QPushButton('浏览', self)
        self.button_workspace.clicked.connect(self.open_dialog3)

        # 创建水平布局5
        hbox1 = QHBoxLayout()
        hbox1.addWidget(geotiff_input_label)
        hbox1.addWidget(self.geotiff_input)
        hbox1.addWidget(self.button_geotiff)

        hbox1.addWidget(shp_input_label)
        hbox1.addWidget(self.shp_input)
        hbox1.addWidget(self.button_shp)

        hbox1.addStretch(1)  # 添加右侧弹性空间

        # 创建水平布局
        hbox2 = QHBoxLayout()
        hbox2.addStretch(1)  # 添加右侧弹性空间
        hbox2.addWidget(dem_input_label)
        hbox2.addWidget(self.dem_input)
        hbox2.addWidget(self.button_dem)
        hbox2.addWidget(workspace_label)
        hbox2.addWidget(self.workspace_input)
        hbox2.addWidget(self.button_workspace)
        hbox2.addStretch(1)  # 添加右侧弹性空间

        # 创建水平布局
        hbox3 = QHBoxLayout()
        hbox3.addStretch(1)  # 添加右侧弹性空间
        hbox3.addWidget(resample_button)
        hbox3.addStretch(1)  # 添加右侧弹性空间
        hbox3.addWidget(center_label)
        hbox3.addWidget(self.center)
        hbox3.addWidget(four_label)
        hbox3.addWidget(self.four)
        hbox3.addWidget(corner_label)
        hbox3.addWidget(self.corner)
        hbox3.addStretch(1)  # 添加右侧弹性空间

        # 创建水平布局(步长选择)
        hbox_left_top = QHBoxLayout()
        hbox_left_top.addStretch(1)  # 添加左侧弹性空间
        hbox_left_top.addWidget(stride_label)  # 添加 stride_label 到 hbox_left 的左上角
        hbox_left_top.addWidget(self.stride)  # 添加 self.stride 到 hbox_left 的左上角
        hbox_left_top.addStretch(1)  # 添加左侧弹性空间
        # 创建水平布局(按钮)
        hbox_left_under = QHBoxLayout()
        hbox_left_under.addStretch(1)  # 添加左侧弹性空间
        hbox_left_under.addWidget(run_button)
        hbox_left_under.addStretch(1)  # 添加左侧弹性空间
        # 创建水平布局(输出显示)
        hbox_right = QHBoxLayout()
        hbox_right.addWidget(self.output_text)  # 添加 self.output_text 到 hbox_right 的右侧
        # 创建垂直布局（步长+按钮）
        vbox_left = QVBoxLayout()
        vbox_left.addLayout(hbox_left_top)  # 添加 hbox_left 到 vbox_left
        vbox_left.addLayout(hbox_left_under)  # 添加 run_button 到 vbox_left
        # 创建水平布局
        hbox5 = QHBoxLayout()
        hbox5.addLayout(vbox_left)  # 添加 vbox_left 到 hbox5
        hbox5.addLayout(hbox_right)  # 添加 hbox_right 到 hbox5

        # 将所有水平布局添加到垂直布局中
        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)
        vbox.addLayout(hbox3)
        vbox.addLayout(hbox5)

        self.setLayout(vbox)
        self.show()

    def runClicked_check(self):
        # 获取输入的值并进行处理
        input_geotiff = self.geotiff_input.text()
        input_dem = self.dem_input.text()
        if input_dem != "":
            flag = check_containment(input_dem, input_geotiff)
            if flag == 1:  # dem范围不足
                msg_box = QMessageBox()
                msg_box.setWindowTitle("警告")
                msg_box.setText(
                    "警告：输入的DEM范围无法完全覆盖输入的影像！\n该警告不影响程序运行，但可能会导致输出的DEM切片数据缺失！")
                msg_box.exec_()

    def runClicked(self):
        # 获取输入的值并进行处理
        workspace = self.workspace_input.text()
        stride = self.stride.currentText()
        input_geotiff = self.geotiff_input.text()
        input_dem = self.dem_input.text()
        input_shp = self.shp_input.text()
        center = self.center.currentText()
        four = self.four.currentText()
        corner = self.corner.currentText()

        if center == "√":
            center_flag = "1"
        else:
            center_flag = "0"

        if four == "√":
            four_flag = "1"
        else:
            four_flag = "0"

        if corner == "√":
            corner_flag = "1"
        else:
            corner_flag = "0"

        # 重定向标准输出流到 QTextEdit
        sys.stdout = ConsoleRedirector(self.output_text)


        # 调用函数执行逻辑
        cut_slice(input_dem, input_geotiff, input_shp, workspace, stride, center_flag,
              four_flag, corner_flag, Ori_Pixel_Stride, Resampled_Pixel_Stride)

        msg_box = QMessageBox()
        msg_box.setText("运行完毕")
        msg_box.exec_()

    def Clicked_resample(self):
        self.new_window2 = Resample_windows()
        self.new_window2.show()


# 图像切片——滑动窗口
class MyWindow2(QWidget):
    def __init__(self):
        super().__init__()
        self.four = None
        self.center = None
        self.geotiff_input = None
        self.dem_input = None
        self.shp_input = None
        self.stride = None
        self.workspace_input = None
        self.corner = None
        self.output_text = None
        self.initUI()

    def open_dialog0(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "TIFF Files (*.tif *.tiff)")
        if file_path:
            self.dem_input.setText(file_path)

    def open_dialog1(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "TIFF Files (*.tif *.tiff)")
        if file_path:
            self.geotiff_input.setText(file_path)

    def open_dialog2(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "Shapefile (*.shp)")
        if file_path:
            self.shp_input.setText(file_path)

    def open_dialog3(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹", "/")
        if folder_path:
            self.workspace_input.setText(folder_path)

    def initUI(self):

        # self.setStyleSheet('''QWidget{background-color:#66CCFF;}''')

        self.setWindowTitle("图像切片——滑动窗口")
        self.setGeometry(800, 300, 500, 400)

        geotiff_input_label = QLabel("     输入影像 :  ")
        geotiff_input_label.setFont(QFont("Times New Roman", 12))
        self.geotiff_input = QLineEdit()
        self.geotiff_input.setReadOnly(True)  # 设置为只读
        self.geotiff_input.setFixedSize(160, 30)

        dem_input_label = QLabel("输入DEM(可选) : ")
        dem_input_label.setFont(QFont("Times New Roman", 12))
        self.dem_input = QLineEdit()
        self.dem_input.setReadOnly(True)  # 设置为只读
        self.dem_input.setFixedSize(120, 30)

        resample_button = QPushButton("DEM重采样")
        resample_button.clicked.connect(self.Clicked_resample)
        resample_button.setFixedSize(100, 50)

        shp_input_label = QLabel("     输入shp : ")
        shp_input_label.setFont(QFont("Times New Roman", 12))
        self.shp_input = QLineEdit()
        self.shp_input.setReadOnly(True)  # 设置为只读
        self.shp_input.setFixedSize(160, 30)

        workspace_label = QLabel("     输出路径:")
        workspace_label.setFont(QFont("Times New Roman", 12))
        self.workspace_input = QLineEdit()
        self.workspace_input.setReadOnly(True)  # 设置为只读
        self.workspace_input.setFixedSize(160, 30)  # 设置输入框的大小

        stride_label = QLabel("裁剪窗口大小：")
        stride_label.setFont(QFont("Times New Roman", 12))
        self.stride = QComboBox()
        self.stride.addItems(["64", "128", "256", "512", "1024"])
        self.stride.setFont(QFont("Times New Roman", 12))
        self.stride.setFixedSize(80, 40)  # 设置下拉框的大小

        size_label = QLabel("        滑动步长：")
        size_label.setFont(QFont("Times New Roman", 12))
        self.size = QComboBox()
        self.size.addItems(["32", "64", "128", "256", "512"])
        self.size.setFont(QFont("Times New Roman", 12))
        self.size.setFixedSize(80, 40)  # 设置下拉框的大小

        run_button = QPushButton("开始运行")
        run_button.clicked.connect(self.runClicked_check)
        run_button.clicked.connect(self.runClicked)
        run_button.setFixedSize(100, 50)

        # 创建 QTextEdit 控件用于显示输出信息
        self.output_text = QTextEdit()
        self.output_text.setFixedSize(500, 150)
        self.output_text.setReadOnly(True)  # 设置为只读

        # 创建垂直布局，并将控件添加到布局中
        vbox = QVBoxLayout()

        # 创建各个控件
        self.button_dem = QPushButton('浏览', self)
        self.button_dem.clicked.connect(self.open_dialog0)

        self.button_geotiff = QPushButton('浏览', self)
        self.button_geotiff.clicked.connect(self.open_dialog1)

        self.button_shp = QPushButton('浏览', self)
        self.button_shp.clicked.connect(self.open_dialog2)

        self.button_workspace = QPushButton('浏览', self)
        self.button_workspace.clicked.connect(self.open_dialog3)

        # 创建水平布局5
        hbox1 = QHBoxLayout()
        hbox1.addWidget(geotiff_input_label)
        hbox1.addWidget(self.geotiff_input)
        hbox1.addWidget(self.button_geotiff)

        hbox1.addWidget(shp_input_label)
        hbox1.addWidget(self.shp_input)
        hbox1.addWidget(self.button_shp)

        hbox1.addStretch(1)  # 添加右侧弹性空间

        # 创建水平布局
        hbox2 = QHBoxLayout()
        hbox2.addStretch(1)  # 添加右侧弹性空间
        hbox2.addWidget(dem_input_label)
        hbox2.addWidget(self.dem_input)
        hbox2.addWidget(self.button_dem)
        hbox2.addWidget(workspace_label)
        hbox2.addWidget(self.workspace_input)
        hbox2.addWidget(self.button_workspace)
        hbox2.addStretch(1)  # 添加右侧弹性空间

        # 创建水平布局(步长选择)
        hbox_left_top = QHBoxLayout()
        hbox_left_top.addStretch(1)  # 添加左侧弹性空间
        hbox_left_top.addWidget(stride_label)
        hbox_left_top.addWidget(self.stride)
        hbox_left_top.addStretch(1)  # 添加左侧弹性空间

        # 创建水平布局(按钮)
        hbox_left_under = QHBoxLayout()
        hbox_left_under.addStretch(1)  # 添加左侧弹性空间
        hbox_left_under.addWidget(run_button)
        hbox_left_under.addStretch(1)  # 添加左侧弹性空间

        # 创建水平布局(滑动窗口选择)
        hbox = QHBoxLayout()
        hbox.addStretch(1)  # 添加左侧弹性空间
        hbox.addWidget(size_label)
        hbox.addWidget(self.size)
        hbox.addStretch(1)  # 添加左侧弹性空间

        hbox_resample = QHBoxLayout()
        hbox_resample.addStretch(1)  # 添加左侧弹性空间
        hbox_resample.addWidget(resample_button)
        hbox_resample.addStretch(1)  # 添加左侧弹性空间

        # 创建水平布局(输出显示)
        hbox_right = QHBoxLayout()
        hbox_right.addWidget(self.output_text)

        # 创建垂直布局（步长+按钮）
        vbox_left = QVBoxLayout()
        vbox_left.addLayout(hbox_resample)
        vbox_left.addLayout(hbox)  # 添加滑动步长
        vbox_left.addLayout(hbox_left_top)  # 添加窗口大小
        vbox_left.addLayout(hbox_left_under)  # 添加 run_button
        # 创建水平布局

        hbox5 = QHBoxLayout()
        hbox5.addLayout(vbox_left)  # 添加左侧组团
        hbox5.addLayout(hbox_right)  # 添加 显示屏

        # 将所有水平布局添加到垂直布局中
        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)
        vbox.addLayout(hbox5)

        self.setLayout(vbox)
        self.show()

    def runClicked_check(self):
        # 获取输入的值并进行处理
        input_geotiff = self.geotiff_input.text()
        input_dem = self.dem_input.text()
        if input_dem != "":
            flag = check_containment(input_dem, input_geotiff)
            if flag == 1:  # dem范围不足
                msg_box = QMessageBox()
                msg_box.setWindowTitle("警告")
                msg_box.setText(
                    "警告：输入的DEM范围无法完全覆盖输入的影像！\n该警告不影响程序运行，但可能会导致输出的DEM切片数据缺失！")
                msg_box.exec_()

    def runClicked(self):
        # 获取输入的值并进行处理
        workspace = self.workspace_input.text()
        size = self.stride.currentText()
        stride = self.size.currentText()
        input_geotiff = self.geotiff_input.text()
        input_dem = self.dem_input.text()
        input_shp = self.shp_input.text()

        # 重定向标准输出流到 QTextEdit
        sys.stdout = ConsoleRedirector(self.output_text)

        # 调用函数执行逻辑
        cut_slice_stride(input_dem, input_geotiff, input_shp, workspace, size, stride, Ori_Pixel_Stride, Resampled_Pixel_Stride)

        msg_box = QMessageBox()
        msg_box.setText("运行完毕")
        msg_box.exec_()

    def Clicked_resample(self):
        self.new_window2 = Resample_windows()
        self.new_window2.show()


class CustomLineEdit(QLineEdit):
    def __init__(self, placeholder_text):
        super().__init__()
        self.placeholder_text = placeholder_text
        self.setPlaceholderText(self.placeholder_text)

    def focusOutEvent(self, event):
        # 如果文本框内容为空，则将预填写文本重新填充到文本框中
        if not self.text():
            self.setText(self.placeholder_text)
        super().focusOutEvent(event)

    def text(self):
        # 重写text方法以确保当文本框内容为预填写内容时，返回预填写的内容
        if super().text() == self.placeholder_text:
            return self.placeholder_text
        return super().text() if super().text() != "" else self.placeholder_text


class MainWindow(QWidget):
    def clear_placeholder(self, event):
        if self.source_input.placeholderText() and \
                self.source_input.text() == self.source_input.placeholderText():
            # 如果当前文本为预填写文本，则清空
            self.source_input.clear()
        # 调用默认的鼠标点击事件
        QLineEdit.mousePressEvent(self.source_input, event)

    def __init__(self):
        super().__init__()

        self.setWindowTitle('图像切片')
        self.setGeometry(700, 300, 600, 430)

        source_information_label = QLabel("数据信息")
        source_information_label.setFont(QFont("Times New Roman", 12))

        source_label = QLabel("           数据源:    ")
        source_label.setFont(QFont("Times New Roman", 10))
        self.source_input = CustomLineEdit("例：sentinel-1A")
        self.source_input.setFixedSize(110, 25)
        resolution_label = QLabel("    分辨率:")
        resolution_label.setFont(QFont("Times New Roman", 10))
        self.resolution_input = CustomLineEdit("例：5米")
        self.resolution_input.setFixedSize(110, 25)
        time_label = QLabel("    数据时间:")
        time_label.setFont(QFont("Times New Roman", 10))
        self.time_input = CustomLineEdit("例：20210101")
        self.time_input.setFixedSize(110, 25)

        data_type_label = QLabel("           数据类型:")
        data_type_label.setFont(QFont("Times New Roman", 10))
        self.data_type_input = CustomLineEdit("例：uint")
        self.data_type_input.setFixedSize(110, 25)
        data_depth_label = QLabel("      位深:  ")
        data_depth_label.setFont(QFont("Times New Roman", 10))
        self.data_depth_input = CustomLineEdit("例：8bit")
        self.data_depth_input.setFixedSize(110, 25)
        grade_label = QLabel("        地形:     ")
        grade_label.setFont(QFont("Times New Roman", 10))
        self.grade_input = CustomLineEdit("例：山地/丘陵/平原")
        self.grade_input.setFixedSize(110, 25)

        district_label = QLabel("区域信息")
        district_label.setFont(QFont("Times New Roman", 12))
        province_label = QLabel("省:")
        province_label.setFont(QFont("Times New Roman", 10))
        self.province_input = CustomLineEdit("例：陕西省")
        self.province_input.setFixedSize(110, 25)
        municipal_label = QLabel("    市:")
        municipal_label.setFont(QFont("Times New Roman", 10))
        self.municipal_input = CustomLineEdit("例：榆林市")
        self.municipal_input.setFixedSize(110, 25)
        county_label = QLabel("    区县:")
        county_label.setFont(QFont("Times New Roman", 10))
        self.county_input = CustomLineEdit("例：神木市")
        self.county_input.setFixedSize(110, 25)

        label_information_label = QLabel("图像&标签信息")
        label_information_label.setFont(QFont("Times New Roman", 12))
        label_name_label = QLabel("图像&标签内容:")
        label_name_label.setFont(QFont("Times New Roman", 10))
        self.label_name_input = CustomLineEdit("例：采矿沉陷")
        self.label_name_input.setFixedSize(110, 25)
        classification_label = QLabel("    图像&标签用途:")
        classification_label.setFont(QFont("Times New Roman", 10))
        self.classification_input = CustomLineEdit("例：语义分割")
        self.classification_input.setFixedSize(110, 25)
        Spatial_reference_label = QLabel("    空间参考:")
        Spatial_reference_label.setFont(QFont("Times New Roman", 10))
        self.Spatial_reference_input = CustomLineEdit("例：WGS-1984")
        self.Spatial_reference_input.setFixedSize(110, 25)

        information_label = QLabel("组织信息")
        information_label.setFont(QFont("Times New Roman", 12))
        name_label = QLabel("制作单位/人")
        name_label.setFont(QFont("Times New Roman", 10))
        self.name_input = CustomLineEdit("")
        self.name_input.setFixedSize(110, 25)
        address_label = QLabel("    地址")
        address_label.setFont(QFont("Times New Roman", 10))
        self.address_input = CustomLineEdit("")
        self.address_input.setFixedSize(150, 25)
        email_label = QLabel("    联系方式")
        email_label.setFont(QFont("Times New Roman", 10))
        self.email_input = CustomLineEdit("")
        self.email_input.setFixedSize(110, 25)

        button1 = QPushButton('遍历要素裁剪', self)
        button1.setFixedSize(280, 60)
        button1.clicked.connect(self.open_new_window1)

        button2 = QPushButton('滑动窗口裁剪', self)
        button2.setFixedSize(280, 60)
        button2.clicked.connect(self.open_new_window2)

        vbox = QVBoxLayout()

        hbox_6_0 = QHBoxLayout()
        hbox_6_0.addStretch(1)  # 添加左侧弹性空间
        hbox_6_0.addWidget(source_information_label)
        hbox_6_0.addStretch(1)  # 添加左侧弹性空间
        hbox_6 = QHBoxLayout()
        hbox_6.addStretch(1)  # 添加左侧弹性空间
        hbox_6.addWidget(source_label)
        hbox_6.addWidget(self.source_input)
        hbox_6.addWidget(resolution_label)
        hbox_6.addWidget(self.resolution_input)
        hbox_6.addWidget(time_label)
        hbox_6.addWidget(self.time_input)
        hbox_6.addStretch(1)  # 添加左侧弹性空间
        hbox_6_1 = QHBoxLayout()
        hbox_6_1.addStretch(1)  # 添加左侧弹性空间
        hbox_6_1.addWidget(data_type_label)
        hbox_6_1.addWidget(self.data_type_input)
        hbox_6_1.addWidget(data_depth_label)
        hbox_6_1.addWidget(self.data_depth_input)
        hbox_6_1.addWidget(grade_label)
        hbox_6_1.addWidget(self.grade_input)
        hbox_6_1.addStretch(1)  # 添加左侧弹性空间

        hbox_5_0 = QHBoxLayout()
        hbox_5_0.addStretch(1)  # 添加左侧弹性空间
        hbox_5_0.addWidget(district_label)
        hbox_5_0.addStretch(1)  # 添加左侧弹性空间
        hbox_5 = QHBoxLayout()
        hbox_5.addStretch(1)  # 添加左侧弹性空间
        hbox_5.addWidget(province_label)
        hbox_5.addWidget(self.province_input)
        hbox_5.addWidget(municipal_label)
        hbox_5.addWidget(self.municipal_input)
        hbox_5.addWidget(county_label)
        hbox_5.addWidget(self.county_input)
        hbox_5.addStretch(1)  # 添加左侧弹性空间

        hbox_4_0 = QHBoxLayout()
        hbox_4_0.addStretch(1)  # 添加左侧弹性空间
        hbox_4_0.addWidget(label_information_label)
        hbox_4_0.addStretch(1)  # 添加左侧弹性空间
        hbox_4 = QHBoxLayout()
        hbox_4.addStretch(1)  # 添加左侧弹性空间
        hbox_4.addWidget(label_name_label)
        hbox_4.addWidget(self.label_name_input)
        hbox_4.addWidget(classification_label)
        hbox_4.addWidget(self.classification_input)
        hbox_4.addWidget(Spatial_reference_label)
        hbox_4.addWidget(self.Spatial_reference_input)
        hbox_4.addStretch(1)  # 添加左侧弹性空间

        hbox_3_0 = QHBoxLayout()
        hbox_3_0.addStretch(1)  # 添加左侧弹性空间
        hbox_3_0.addWidget(information_label)
        hbox_3_0.addStretch(1)  # 添加左侧弹性空间
        hbox_3 = QHBoxLayout()
        hbox_3.addStretch(1)  # 添加左侧弹性空间
        hbox_3.addWidget(name_label)
        hbox_3.addWidget(self.name_input)
        hbox_3.addWidget(address_label)
        hbox_3.addWidget(self.address_input)
        hbox_3.addWidget(email_label)
        hbox_3.addWidget(self.email_input)
        hbox_3.addStretch(1)  # 添加左侧弹性空间

        hbox_1 = QHBoxLayout()
        hbox_1.addStretch(1)  # 添加左侧弹性空间
        hbox_1.addWidget(button1)
        hbox_1.addWidget(button2)
        hbox_1.addStretch(1)  # 添加左侧弹性空间

        vbox.addLayout(hbox_6_0)
        vbox.addLayout(hbox_6)
        vbox.addLayout(hbox_6_1)
        vbox.addSpacing(20)
        vbox.addLayout(hbox_5_0)
        vbox.addLayout(hbox_5)
        vbox.addSpacing(20)
        vbox.addLayout(hbox_4_0)
        vbox.addLayout(hbox_4)
        vbox.addSpacing(20)
        vbox.addLayout(hbox_3_0)
        vbox.addLayout(hbox_3)
        vbox.addSpacing(20)
        vbox.addLayout(hbox_1)

        self.setLayout(vbox)
        self.show()

    def open_new_window1(self):
        global Source, Resolution, Sourece_time, Data_type, Data_depth, Grade
        global Province, Municipal, County
        global Label_name, Classification, Spatial_reference
        global Name, Address, Email

        Source = self.source_input.text()
        Resolution = self.resolution_input.text()
        Sourece_time = self.time_input.text()
        Data_type = self.data_type_input.text()
        Data_depth = self.data_depth_input.text()
        Grade = self.grade_input.text()

        Province = self.province_input.text()
        Municipal = self.municipal_input.text()
        County = self.county_input.text()

        Label_name = self.label_name_input.text()
        Classification = self.classification_input.text()
        Spatial_reference = self.Spatial_reference_input.text()

        Name = self.name_input.text()
        Address = self.address_input.text()
        Email = self.email_input.text()

        self.new_window1 = MyWindow()
        self.new_window1.show()

    def open_new_window2(self):
        global Source, Resolution, Sourece_time, Data_type, Data_depth, Grade
        global Province, Municipal, County
        global Label_name, Classification, Spatial_reference
        global Name, Address, Email

        Source = self.source_input.text()
        Resolution = self.resolution_input.text()
        Sourece_time = self.time_input.text()
        Data_type = self.data_type_input.text()
        Data_depth = self.data_depth_input.text()
        Grade = self.grade_input.text()

        Province = self.province_input.text()
        Municipal = self.municipal_input.text()
        County = self.county_input.text()

        Label_name = self.label_name_input.text()
        Classification = self.classification_input.text()
        Spatial_reference = self.Spatial_reference_input.text()

        Name = self.name_input.text()
        Address = self.address_input.text()
        Email = self.email_input.text()

        self.new_window2 = MyWindow2()
        self.new_window2.show()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
