#!/usr/bin/env python
# coding=utf-8
from osgeo import gdal
import numpy as np
import sys


def load_color_map(filename):
    color_map = {}
    with open(filename, 'r') as file:
        next(file)  # 跳过第一行
        for line in file:
            parts = line.strip().split(',')
            range_start = float(parts[0]) if parts[0] != '-inf' else -float('inf')
            range_end = float(parts[1]) if parts[1] != '+inf' else float('inf')
            color = list(map(int, parts[2:]))
            color_map[(range_start, range_end)] = color
    return color_map


def color_standard(value, color_map):
    for range_tuple, color in color_map.items():
        if range_tuple[0] < value <= range_tuple[1]:
            return color
    return [0, 0, 0]  # Default


def color_standard_array(values, color_map):
    # 创建一个与 values 大小相同的空白 RGB 数据数组
    rgb_values = np.zeros((values.shape[0], values.shape[1], 3), dtype=int)

    for (range_start, range_end), color in color_map.items():
        mask = (values > range_start) & (values <= range_end)
        rgb_values[mask] = color  # 将符合条件的值更新为对应颜色

    return rgb_values


def color(input_file, output_file, color_bar_txt):
    dataset = gdal.Open(input_file)
    band = dataset.GetRasterBand(1)
    data = band.ReadAsArray()
    print(f"input:{input_file}")
    print(f"color_bar:{color_bar_txt}")
    print(f"output:{output_file}")

    driver = gdal.GetDriverByName('GTiff')
    output_dataset = driver.Create(
        output_file,
        dataset.RasterXSize,
        dataset.RasterYSize,
        3,
        gdal.GDT_Byte
    )
    output_dataset.SetGeoTransform(dataset.GetGeoTransform())
    output_dataset.SetProjection(dataset.GetProjection())

    data_scaled = data  # 假设 data 是一个二维数组
    color_map = load_color_map(color_bar_txt)  # 加载颜色映射
    colors = color_standard_array(data_scaled, color_map)
    rgb_data = colors.transpose(2, 0, 1)

    for i in range(3):
        band = output_dataset.GetRasterBand(i + 1)
        band.WriteArray(rgb_data[i])
        band.FlushCache()

    del output_dataset


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("请按格式输入")
        print("<script_name> <input_file> <output_file> <color_bar>")
        print("input_file：待上色geotoff文件(float32)")
        print("output_file：上色的geotiff文件(uint8_RGB)")
        print("color_bar：上色方案")
        sys.exit(1)

    input = sys.argv[1]
    output = sys.argv[2]
    bar = sys.argv[3]

    color(input, output, bar)
