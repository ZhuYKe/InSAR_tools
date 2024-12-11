#!/usr/bin/env python
# coding=utf-8
import numpy as np
from osgeo import osr,gdal,ogr
import fiona
import shapely.geometry
import os
import sys

def get_polygon_bounds(polygon):
    return polygon.bounds


def get_image_values(image_path, bounds):
    ds = gdal.Open(image_path)
    gt = ds.GetGeoTransform()
    rb = ds.GetRasterBand(1)
    nodata = rb.GetNoDataValue()

    # 获取图像在多边形范围内的像素强度值
    offset = int((bounds[0] - gt[0]) / gt[1])
    size_x = int((bounds[2] - bounds[0]) / gt[1])
    offset_y = int((bounds[3] - gt[3]) / gt[5])
    size_y = int((bounds[1] - bounds[3]) / gt[5])

    data = rb.ReadAsArray(offset, offset_y, size_x, size_y)
    return data


def get_value(shp_file, image_path):
    with fiona.open(shp_file, 'r') as shp:
        for feature in shp:
            geom = shapely.geometry.shape(feature['geometry'])
            bounds = get_polygon_bounds(geom)

            # 获取多边形范围内的图像值
            image_values = get_image_values(image_path, bounds)

            # 计算平均值、最大值和最小值
            avg_value = np.nanmean(image_values)
            max_value = np.nanmax(image_values)
            min_value = np.nanmin(image_values)

            print(f"Polygon ID:  {str(int(feature['id']) + 1)}")
            print(f"Avg_disp：{avg_value:.5f} Min_disp：{min_value:.5f} Max_disp：{max_value:.5f}")


def get_value_and_update_shp(shp_file, image_path, key_word, output_shp_file):

    with fiona.open(shp_file, 'r') as shp:
        schema = shp.schema.copy()

        new_fields = [f'{key_word}_Avg_disp', f'{key_word}_Min_disp', f'{key_word}_Max_disp']
        for field in new_fields:
            if field in schema['properties']:
                pass
            else:
                schema['properties'][field] = 'float'

        with fiona.open(output_shp_file, 'w', driver='ESRI Shapefile', schema=schema, crs=shp.crs) as output:
            for feature in shp:
                geom = shapely.geometry.shape(feature['geometry'])
                bounds = get_polygon_bounds(geom)

                # 获取多边形范围内的图像值
                image_values = get_image_values(image_path, bounds)

                if image_values is not None:
                    # 计算平均值、最大值和最小值
                    avg_value = np.nanmean(image_values)
                    max_value = np.nanmax(image_values)
                    min_value = np.nanmin(image_values)

                    feature['properties']['Avg_disp'] = float(avg_value)
                    feature['properties']['Min_disp'] = float(min_value)
                    feature['properties']['Max_disp'] = float(max_value)
                else:
                    feature['properties']['Avg_disp'] = None
                    feature['properties']['Min_disp'] = None
                    feature['properties']['Max_disp'] = None

                output.write(feature)

        print(f"{shp_file}字段已添加{image_path}形变量信息 保存至 {output_shp_file}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("请按格式输入")
        print("<script_name> <ori_shp> <ref_geotiff> <key_word> <output_shp>")
        print("ori_shp：原始shp")
        print("ref_geotiff：disp_map_geotiff形变量参考影像")
        print("key_word: 形变量文件类型关键字(stacking、2pass、SBAS等)")
        print("output_shp：添加形变量字段的输出shp")
        sys.exit(1)
    ori_shp = sys.argv[1]
    ref_geotiff = sys.argv[2]
    keyword = sys.argv[3]
    output_shp = sys.argv[4]

    get_value(ori_shp, ref_geotiff)
    get_value_and_update_shp(ori_shp, ref_geotiff, keyword, output_shp)
