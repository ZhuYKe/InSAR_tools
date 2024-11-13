#!/usr/bin/env python
# coding=utf-8
import sys
from osgeo import gdal
import numpy as np

def is_valid_region(band_array, x, y, expand_cc_threshold, min_percent, region_size):
    """
    检查给定点周围 region_size x region_size 区域内是否有至少 min_count 个像素值高于 threshold。
    """
    rows, cols = band_array.shape
    half_size = region_size // 2
    count = 0
    min_count = (region_size * region_size) * min_percent
    for i in range(-half_size, half_size + 1):
        for j in range(-half_size, half_size + 1):
            xi, yj = x + i, y + j
            if 0 <= yj < cols and 0 <= xi < rows:
                if band_array[xi, yj] > min_threhold:
                    count += 1
            else:
                print("out of range")
            if count >= min_count:
                return True

    return False


def auto_ref_point(cc_ad_tiff, mask):
    dataset = gdal.Open(cc_ad_tiff)
    width = dataset.RasterXSize
    height = dataset.RasterYSize
    band = dataset.GetRasterBand(1)
    cc_band_array = band.ReadAsArray()
    data = band.ReadAsArray(0, 0, width, height)

    dataset_mask = gdal.Open(mask)
    band_mask = dataset_mask.GetRasterBand(1)
    data_mask = band_mask.ReadAsArray(0, 0, width, height)

    combined_condition = np.logical_and(data > 0.99, data_mask != 0)
    high_intensity_coords = np.argwhere(combined_condition)
    high_intensity_coords = [(x, y) for x, y in high_intensity_coords]
    max_cc_intensity = 0
    max_intensity_coord = None
    for coord in high_intensity_coords:
        y, x = coord
        intensity = cc_band_array[y, x]
        # 该点cc值在0.99以上 & 该点周围10*10的像素有70%的像素的cc值在0.9以上
        if intensity > max_cc_intensity and is_valid_region(cc_band_array, y, x, expand_cc_threshold=0.9,
                                                            min_percent=0.7, region_size=10):
            max_intensity_coord = (x, y)
            max_cc_intensity = intensity
    pixel_x, pixel_y = max_intensity_coord
    print(pixel_x, pixel_y)
    return int(pixel_x), int(pixel_y)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("请按格式输入")
        print("<script_name> <cc_ad> <mask> <out_path>")
        print("cc_ad：cc_ad.tif")
        print("mask：Mask区域 ( .shp - )")
        print("out_path：记录文件输出路径")
        sys.exit(1)

    cc_ad = os.path.abspath(sys.argv[1])
    mask = os.path.abspath(sys.argv[2])
    txt = os.path.abspath(sys.argv[3])

    rpos_mul, azpos_mul = auto_ref_point(cc_ad, mask)
    with open(txt + "/auto_ref_rpos_azpos.txt", "w") as file:
        print(f"rpops_mul:{rpos_mul}\nazpos_mul:{azpos_mul}")



