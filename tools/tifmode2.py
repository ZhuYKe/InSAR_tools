#!/usr/bin/env python
from osgeo import gdal
import numpy as np
import scipy
from scipy import stats
import sys
import os


def usage():
    print("""
    usage tifmode2.py <input> <output> 

      input         输入栅格影像
      output        输出栅格影像

""")
    sys.exit()

def tifmode():
    print('*** 栅格数据减去众数 ***')
    if len(sys.argv) < 2:
        usage()
    input_tif=sys.argv[1]
    output_tif=sys.argv[2]
    dataset=gdal.Open(input_tif, gdal.GA_ReadOnly)

    if dataset is None:
        print("无法打开TIF文件")
        exit()

    band=dataset.GetRasterBand(1)

    nodata_value=band.GetNoDataValue()
    data=band.ReadAsArray().astype(np.float32)
    mask=(data!=nodata_value)
    data[data==nodata_value]=np.nan

    mode_value=float(stats.mode(data[mask],axis=None).mode)
    print("像元值的众数值：", mode_value)

    corrected_data=data - mode_value

    output_driver=gdal.GetDriverByName("GTiff")
    output_dataset=output_driver.Create(output_tif,dataset.RasterXSize,dataset.RasterYSize,1,gdal.GDT_Float32)
    output_dataset.SetGeoTransform(dataset.GetGeoTransform())
    output_dataset.SetProjection(dataset.GetProjection())
    output_band=output_dataset.GetRasterBand(1)

    output_band.WriteArray(corrected_data)

    output_dataset=None
    dataset=None
    print(f"已生成校正后的TIFF文件:{output_tif}")


def tifmode_new():
    print('*** 栅格数据减去众数 ***')
    if len(sys.argv) < 2:
        usage()
    input_tif = sys.argv[1]
    output_tif = sys.argv[2]
    dataset = gdal.Open(input_tif, gdal.GA_ReadOnly)

    if dataset is None:
        print("无法打开TIF文件")
        exit()

    band = dataset.GetRasterBand(1)
    nodata_value = band.GetNoDataValue()
    data = band.ReadAsArray().astype(np.float32)
    mask = (data != nodata_value)
    data[data == nodata_value] = np.nan

    while True:
        mode_value = float(stats.mode(data[mask], axis=None).mode)
        print("当前众数值：", mode_value)

        corrected_data = data - mode_value
        data = corrected_data

        if mode_value == 0:
            break

    output_driver = gdal.GetDriverByName("GTiff")
    output_dataset = output_driver.Create(output_tif, dataset.RasterXSize, dataset.RasterYSize, 1, gdal.GDT_Float32)
    output_dataset.SetGeoTransform(dataset.GetGeoTransform())
    output_dataset.SetProjection(dataset.GetProjection())
    output_band = output_dataset.GetRasterBand(1)

    output_band.WriteArray(corrected_data)

    output_dataset = None
    dataset = None
    print(f"已生成校正后的TIFF文件: {output_tif}")

if __name__ == '__main__':
    tifmode_new()