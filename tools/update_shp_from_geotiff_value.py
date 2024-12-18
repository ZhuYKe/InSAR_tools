#!/usr/bin/env python
# coding=utf-8
import sys
from osgeo import gdal, ogr
import numpy as np
import fiona
import shapely.geometry
from shapely.geometry import box
import rasterio
from rasterio.mask import mask


def get_image_bounds(image_path):
    """
    获取GeoTIFF的地理范围，返回(x_min, y_min, x_max, y_max)
    """
    with rasterio.open(image_path) as ds:
        return ds.bounds


def get_image_bounds(image_path):
    """
    获取GeoTIFF的地理范围，返回(x_min, y_min, x_max, y_max)
    """
    ds = gdal.Open(image_path)
    gt = ds.GetGeoTransform()

    # 图像左上角坐标 (x_min, y_max)
    x_min = gt[0]
    y_max = gt[3]

    # 图像右下角坐标 (x_max, y_min)
    x_max = x_min + ds.RasterXSize * gt[1]
    y_min = y_max + ds.RasterYSize * gt[5]

    return (x_min, y_min, x_max, y_max)

def get_values_for_geometry(image_path, geom):
    """
    根据Shapefile中几何图形从GeoTIFF中提取对应区域的像素值。
    """
    with rasterio.open(image_path) as ds:
        # 通过mask函数提取几何形状对应区域的像素值
        geojson = [geom.__geo_interface__]
        out_image, out_transform = mask(ds, geojson, crop=True)

        # 只保留有效的像素（不包含NoData）
        out_image = out_image[0]  # 处理单波段
        out_image = out_image[out_image != ds.nodata]

        return out_image


def get_value_and_update_shp(shp_file, image_path, name, output_shp_file, value_choose):
    image_bounds = get_image_bounds(image_path)  # 获取GeoTIFF的范围

    with fiona.open(shp_file, 'r') as shp:
        schema = shp.schema.copy()

        field = f'{name}'
        if field in schema['properties']:
            print(f"已有字段{name} 更新信息")
        else:
            schema['properties'][field] = 'float'
            print(f"添加新字段{name}")

        with fiona.open(output_shp_file, 'w', driver='ESRI Shapefile', schema=schema, crs=shp.crs) as output:
            for feature in shp:
                geom = shapely.geometry.shape(feature['geometry'])

                # 创建一个 Shapely box 对象表示 GeoTIFF 的有效范围
                image_polygon = box(*image_bounds)
                # 判断要素是否完全在GeoTIFF的范围内
                if not image_polygon.contains(geom):
                    print(f"要素 {str(int(feature['id']) + 1)} 不完全在GeoTIFF范围内。")
                    continue  # 如果要素不完全在范围内，跳过该要素

                # 获取该要素几何形状在GeoTIFF图像中的像素值
                image_values = get_values_for_geometry(image_path, geom)

                if image_values is not None and len(image_values) > 0:
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
                    print(f"要素{str(int(feature['id']) + 1)} {name}字段 更新为{float(value)}")
                else:
                    print(f"要素{str(int(feature['id']) + 1)} 对应参考geotiff区域无有效值 {name}字段未更新")
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
