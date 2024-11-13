#!/usr/bin/env python
# coding=utf-8
import glob
import shutil
import os
import sys
import unicodedata

import numpy as np
import requests
from shapely.geometry import shape, Point
from osgeo import gdal, gdalnumeric
import shapefile

def remove_txt(txt_path):
    path = txt_path
    for infile in glob.glob(os.path.join(path, '*.txt')):
        os.remove(infile)


def make_dem_boundary(list_lat_txt_path, list_lon_txt_path, list_lat_txt_srtm_path, list_lon_txt_srtm_path,
                      box_boundary):
    list_lat_path_dem_boundary = list_lat_txt_path
    list_lon_path_dem_boundary = list_lon_txt_path
    list_lat_srtm_path_dem_boundary = list_lat_txt_srtm_path
    list_lon_srtm_path_dem_boundary = list_lon_txt_srtm_path
    box_dem_boundary = box_boundary

    box_w = box_dem_boundary.split("/")[0]
    box_e = box_dem_boundary.split("/")[1]
    box_s = box_dem_boundary.split("/")[2]
    box_n = box_dem_boundary.split("/")[3]

    # Check the box left boundary
    box_W = int(float(box_w))
    if box_W < 0:
        box_W0 = str(abs(box_W) + 1).zfill(3)
        box_L = "W" + box_W0
    else:
        box_W0 = str(box_W).zfill(3)
        box_L = "E" + box_W0
    # Check the box right boundary
    box_E = int(float(box_e))
    if box_E < 0:
        box_E0 = str(abs(box_E)).zfill(3)
        box_R = "W" + box_E0
    else:
        box_E0 = str(box_E).zfill(3)
        box_R = "E" + box_E0

    # Check the box bottom boundary
    box_S = int(float(box_s))
    if box_S < 0:
        box_S0 = str(abs(box_S) + 1).zfill(2)
        box_B = "S" + box_S0
    else:
        box_S0 = str(box_S).zfill(2)
        box_B = "N" + box_S0

    # Check the box top boundary
    box_N = int(float(box_n))
    if box_N < 0:
        box_N0 = str(abs(box_N)).zfill(2)
        box_T = "S" + box_N0
    else:
        box_N0 = str(box_N).zfill(2)
        box_T = "N" + box_N0

    print("*********The DEM range:**********")
    print(f"       {box_L}/{box_R}/{box_B}/{box_T}")
    print("*********************************")

    if box_L[0] == box_R[0]:
        list_lon = list(range(int(box_W0), int(box_E0) + 1)) + list(range(int(box_E0), int(box_W0) + 1))
        list_lon = [f"{box_L[:1]}{str(id_lon).zfill(3)}" for id_lon in list_lon]
    else:
        list_lon = list(range(int(box_W), 0)) + list(range(0, int(box_E) + 1))
        list_lon_we = []
        for id_lon in list_lon:
            if int(id_lon) < 0:
                input_lon = 'W' + str(abs(id_lon)).zfill(3)
                list_lon_we = list_lon_we + [input_lon]
            else:
                input_lon = 'E' + str(id_lon).zfill(3)
                list_lon_we = list_lon_we + [input_lon]
        list_lon = list_lon_we
    if box_B[0] == box_T[0]:
        list_lat = list(range(int(box_N0), int(box_S0) + 1)) + list(range(int(box_S0), int(box_N0) + 1))
        list_lat = [f"{box_B[:1]}{str(id_lat).zfill(2)}" for id_lat in list_lat]
    else:
        list_lat = list(range(int(box_S), 0)) + list(range(0, int(box_N) + 1))
        list_lat_we = []
        for id_lat in list_lat:
            if int(id_lat) < 0:
                input_lat = 'S' + str(abs(id_lat)).zfill(3)
                list_lat_we = list_lat_we + [input_lat]
            else:
                input_lat = 'N' + str(id_lat).zfill(3)
                list_lat_we = list_lat_we + [input_lat]
        list_lat = list_lat_we

    with open(list_lon_path_dem_boundary, "w") as f_lon:
        f_lon.write('\n'.join(list_lon))

    with open(list_lat_path_dem_boundary, "w") as f_lat:
        f_lat.write('\n'.join(list_lat))

    # Read and process list_lon.txt
    with open(list_lon_path_dem_boundary, "r") as f_lon:
        lon_lines = f_lon.readlines()
        lon_lines = [line.strip().lower() for line in lon_lines]
        lon_lines = sorted(list(set(lon_lines)))

    with open(list_lon_srtm_path_dem_boundary, "w") as f_lon_srtm:
        f_lon_srtm.write(''.join(lon_lines))

    # Read and process list_lat.txt
    with open(list_lat_path_dem_boundary, "r") as f_lat:
        lat_lines = f_lat.readlines()
        lat_lines = [line.strip().lower() for line in lat_lines]
        lat_lines = sorted(list(set(lat_lines)))

    with open(list_lat_srtm_path_dem_boundary, "w") as f_lat_srtm:
        f_lat_srtm.write(''.join(lat_lines))

    # Print the sorted and unique lon and lat values
    print("Sorted and Unique lon values:")
    print(''.join(lon_lines))
    print("Sorted and Unique lat values:")
    print(''.join(lat_lines))
    print("\n")


def download_dem_copernicus(list_lon_txt_srtm_path, list_lat_srtm_txt_path, diff_path):
    List_lon_srtm_path = list_lon_txt_srtm_path
    List_lat_srtm_path = list_lat_srtm_txt_path
    Diff_dir = diff_path

    with open(List_lon_srtm_path, 'r') as file:
        lines = file.read().replace('\n', '')
    list_lon_final = [lines[i:i + 4] for i in range(0, len(lines), 4)]
    list_lon_final = list(set(list_lon_final))

    with open(List_lat_srtm_path, 'r') as file:
        lines = file.read().replace('\n', '')
    list_lat_final = [lines[i:i + 3] for i in range(0, len(lines), 3)]
    list_lat_final = list(set(list_lat_final))

    # 遍历经度和纬度列表
    for lat in list_lat_final:
        for lon in list_lon_final:
            lat_UP = lat.upper()
            lon_UP = lon.upper()
            dem_name = f"Copernicus_DSM_COG_10_{lat_UP}_00_{lon_UP}_00_DEM"
            # 检查 DEM 文件是否存在
            if os.system(f"aws s3 ls s3://copernicus-dem-30m/{dem_name}/{dem_name}.tif --no-sign-request") == '':
                print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
                print(f"The requested CopDEM {dem_name} does not exist, please check!")
                print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
                exit()
            else:
                print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
                print(f"The CopDEM file {dem_name} has been found.")
                if os.path.isfile(f"{Diff_dir}/{dem_name}.tif"):
                    print(f"Skip the downloading of {dem_name}.tif as it already exists!")
                    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
                else:
                    print(f"Downloading {dem_name}.tif...")
                    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
                    os.system(
                        f"aws s3 cp s3://copernicus-dem-30m/{dem_name}/{dem_name}.tif {Diff_dir}/ --no-sign-request")
            print("\n")
    tif_name = os.listdir(Diff_dir)
    dem_list_path = Diff_dir + '/'
    dem_list = ''
    for i in tif_name:
        dem_list = dem_list + dem_list_path + str(i) + " "
    if dem_list == '':
        print("***************************************************************")
        print(f"Geotiff files do not exit in {Diff_dir}, please check !")
        print("\n")
    else:
        print("********************* Downloading of the Geotiff DEM files finished! **************************")
        print("\n")
    remove_txt(txt_path=dem_dir)


def get_shp_bbox(shp):
    # 读取 shapefile
    sf = shapefile.Reader(shp)
    # 获取所有形状的边界框
    all_bounds = [shape.bbox for shape in sf.shapes()]
    # 计算整体边界框
    min_lon = min(b[0] for b in all_bounds)  # 最小经度
    min_lat = min(b[1] for b in all_bounds)  # 最小纬度
    max_lon = max(b[2] for b in all_bounds)  # 最大经度
    max_lat = max(b[3] for b in all_bounds)  # 最大纬度
    # 格式化为指定字符串格式
    bbox = f"{min_lon:.2f}/{max_lon:.2f}/{min_lat:.2f}/{max_lat:.2f}"
    return bbox



if __name__ == "__main__":

    print("Script to download the DEM")

    if len(sys.argv) < 2:
        print("请按格式输入")
        print("<script_name> <shp_path> <workspace>")
        print("shp_path      shp文件地址")
        print("workspace：      工作路径（需已存在）")
        sys.exit(1)

    # ——————————————————————————————【Input Parameters】——————————————————————————————
    shp_path = sys.argv[1]
    # kml_path = "D:/ZYK/Dem_download_python/map-overlay.kml"
    output_path = sys.argv[2]
    # output_path = "D:/ZYK/workspace"

    # ——————————————————————————————【Get Input Box】——————————————————————————————
    box = get_shp_bbox(shp=shp_path)
    print(f"下载范围: {box}")

    # ——————————————————————————————【Build Work Path】——————————————————————————————
    dem_dir = output_path + '/' + 'dem'
    diff_dir = dem_dir + '/' + 'dem_tiff'

    if not os.path.exists(dem_dir):
        os.mkdir(dem_dir)
    if not os.path.exists(diff_dir):
        os.mkdir(diff_dir)

    # ——————————————————————————————【Make the DEM boundary】——————————————————————————————
    list_lat_path = dem_dir + '/' + 'list_lat.txt'
    list_lon_path = dem_dir + '/' + 'list_lon.txt'
    list_lat_srtm_path = dem_dir + '/' + 'list_lat_srtm.txt'
    list_lon_srtm_path = dem_dir + '/' + 'list_lon_srtm.txt'

    make_dem_boundary(list_lat_txt_path=list_lat_path, list_lon_txt_path=list_lon_path,
                      list_lat_txt_srtm_path=list_lat_srtm_path, list_lon_txt_srtm_path=list_lon_srtm_path,
                      box_boundary=box)

    # ——————————————————————————————【Download the Copernicus DEM 】——————————————————————————————
    download_dem_copernicus(list_lon_txt_srtm_path=list_lon_srtm_path, list_lat_srtm_txt_path=list_lat_srtm_path,
                            diff_path=diff_dir)
