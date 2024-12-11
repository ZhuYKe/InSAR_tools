# Introduction
Some of the homemade tools used in InSAR data processing, including the shp generation tool using the form variable txt and the data set slicing tool based on shp and geotiff created the GUI interface

# requirements
numpy、gdal、PyQt5、pillow、shapely、fiona、requests、pyshp、lxml、pykml、data_downloader、pandas、scipy、geopandas

# Directory structure description
    ├── README.txt           // Help document
    ├── tools
        ├── color_tif.py                                  // float32 format geotiff files are colored with uint8 tri-channel RGB geotiff tool
        ├── color_bar                                     // float32 format geotiff file coloring configuration file(Can be modified as needed)
        ├── cut_slice_GUI.py                             // Data set slicing tool according to shp, geotiff
        ├── txt_generate_shp_GUI.py                      // Form variable txt file generated point format shp tool
        ├── tifmode2.py                                  // geotiff demode tool
        ├── get_height.py                                // DEM input coordinates to get elevation
        ├── dem_download_use_shp.py                     // Download the DEM tool for the corresponding region according to the shp input
        ├── SAR_orbit_download_use_Path_Frame.py        // Download Sentinel-1 image and precision orbit data tool for the corresponding area according to Path and Frame input
        ├── geotif_shp_generate_mask_bmp.py             // Generate mask BMP based on input geotiff and shp
        ├── geotif_shp_generate_mask_tif.py             // Generate mask geotiff based on input geotiff and shp
        ├── auto_refpoint_choose.py                     // Select the latitude and longitude of the reference point based on the shp region and cc_ad.tif
        ├── update_shp_geotiff_disp.py                  // upddate disp information in shpfile form dispmap geotiff
