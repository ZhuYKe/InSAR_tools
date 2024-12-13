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


def get_value_and_update_shp(shp_file, image_path, name, output_shp_file, value_choose):

    with fiona.open(shp_file, 'r') as shp:
        schema = shp.schema.copy()

        field = [f'{name}']
        if field in schema['properties']:
            print(f"已有字段{name} 更新信息")
        else:
            schema['properties'][field] = 'float'
            print(f"添加新字段{name}")

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
					
                    if value_choose == "1":
                        value = max_value
                    elif value_choose == "2":
                        value = min_value
                    else:
                        value = avg_value
			
                    feature['properties'][f'{name}'] = float(value)
                    print(f"要素{str(int(feature['id'])+1)} {name}字段 更新为{float(value)}")
                else:
                    print(f"要素{str(int(feature['id'])+1)} 对应参考geotiff区域无有效值 {name}字段未更新")
                output.write(feature)

        print(f"保存至 {output_shp_file}")


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("请按格式输入")
        print("<script_name> <ori_shp> <ref_geotiff> <key_word> <output_shp> <value_choose>")
        print("ori_shp：输入shp")
        print("ref_geotiff：参考影像geotiff")
        print("key_word: 待更新（添加）要素范围内信息的字段名")
        print("output_shp：更新（添加）字段信息的输出shp")
        print("value_choose: 更新（添加）字段内的值选择 0：要素范围内平均值 1：要素范围内最大值 2：要素范围内最小值")
        sys.exit(1)
    ori_shp = sys.argv[1]
    ref_geotiff = sys.argv[2]
    name = sys.argv[3]
    output_shp = sys.argv[4]
    value_choose = sys.argv[5]

    get_value_and_update_shp(ori_shp, ref_geotiff, name, output_shp, value_choose)
