# 项目介绍
InSAR数据处理中用到的一些自制工具、其中使用形变量txt生成shp工具和根据shp及geotiff进行数据集切片工具创造了GUI界面

# 环境依赖
numpy、gdal、PyQt5、pillow、shapely、fiona、requests、pyshp、lxml、pykml、data_downloader、pandas、scipy、geopandas

# 目录结构描述
    ├── README.txt           // 帮助文档
    ├── tools
        ├── color_tif.py        // float32格式的geotiff文件上色为uint8三通道RGB的geotiff工具
        ├── color_bar          // float32格式的geotiff文件上色配置文件
        ├── cut_slice_GUI.py                      // 根据shp、geotiff进行数据集切片工具
        ├── txt_generate_shp_GUI.py        // 形变量txt文件生成point格式shp工具
        ├── tifmode2.py           // geotiff去众数工具
        ├── get_height.py        // DEM输入坐标获取高程
        ├── dem_download_use_shp.py        // 根据shp输入下载相应地区DEM工具
        ├── SAR_orbit_download_use_Path_Frame.py        // 根据Path、Frame输入下载相应地区哨兵一号影像及精密轨道数据工具
        ├── geotif_shp_generate_mask_bmp.py        // 根据输入geotiff和shp生成掩膜bmp
        ├── geotif_shp_generate_mask_tif.py           // 根据输入geotiff和shp生成掩膜geotiff
        ├── auto_refpoint_choose.py                       // 根据输入shp区域和cc_ad.tif选择参考点经纬度