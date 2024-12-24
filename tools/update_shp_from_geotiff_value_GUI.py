import sys
import numpy as np
import fiona
import shapely.geometry
from shapely.geometry import box
import rasterio
from rasterio.mask import mask
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLineEdit, QFileDialog, \
    QComboBox, QLabel, QMessageBox
from PyQt5.QtCore import Qt

def get_image_bounds(image_path):
    """
    获取GeoTIFF的地理范围，返回(x_min, y_min, x_max, y_max)
    """
    with rasterio.open(image_path) as ds:
        return ds.bounds


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
            schema['properties'][field] = 'str'
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

                    feature['properties'][f'{name}'] = str(value)
                    print(f"要素{str(int(feature['id']) + 1)} {name}字段 更新为{float(value)}")
                else:
                    print(f"要素{str(int(feature['id']) + 1)} 对应参考geotiff区域无有效值 {name}字段未更新")
                output.write(feature)

        print(f"保存至 {output_shp_file}")


class ShapefileProcessingApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('矢量文件&GeoTiff 数据获取与字段添加')
        self.setGeometry(100, 100, 500, 350)

        self.shp_input = None
        self.tiff_input = None
        self.output_shp = None
        self.selected_option = None
        self.input_text = 'MD_Ele'

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Shapefile input button
        self.shp_button = QPushButton('选择输入.shp文件', self)
        self.shp_button.clicked.connect(self.select_shp_file)
        layout.addWidget(self.shp_button)

        self.shp_label = QLabel('选择的输入.shp文件: None', self)
        layout.addWidget(self.shp_label)

        # TIFF file input button
        self.tiff_button = QPushButton('选择输入.tiff文件', self)
        self.tiff_button.clicked.connect(self.select_tiff_file)
        layout.addWidget(self.tiff_button)

        self.tiff_label = QLabel('选择的输入.tiff文件: None', self)
        layout.addWidget(self.tiff_label)

        # Input text field
        self.text_input_label = QLabel('输入字段名:(例：MD_Ele)', self)
        self.text_input = QLineEdit(self)
        layout.addWidget(self.text_input_label)
        layout.addWidget(self.text_input)

        self.combo_label = QLabel('选择模式(默认：平均):', self)
        self.combo_box = QComboBox(self)
        self.combo_box.addItems(['平均值', '最大值', '最小值'])
        layout.addWidget(self.combo_label)
        layout.addWidget(self.combo_box)

        # Output shapefile button
        self.output_button = QPushButton('选择输出.shp文件', self)
        self.output_button.clicked.connect(self.select_output_shp)
        layout.addWidget(self.output_button)

        self.output_label = QLabel('选择的输出.shp文件: None', self)
        layout.addWidget(self.output_label)

        # Run button
        self.run_button = QPushButton('运行', self)
        self.run_button.clicked.connect(self.run_processing)
        layout.addWidget(self.run_button)

        # Central widget setup
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def select_shp_file(self):
        file, _ = QFileDialog.getOpenFileName(self, '选择.shp文件', '', 'Shapefiles (*.shp)')
        if file:
            self.shp_input = file
            self.shp_label.setText(f'选择Shp文件: {file}')

    def select_tiff_file(self):
        file, _ = QFileDialog.getOpenFileName(self, '选择.tiff文件', '', 'TIFF files (*.tiff *.tif)')
        if file:
            self.tiff_input = file
            self.tiff_label.setText(f'选择Tiff文件: {file}')

    def select_output_shp(self):
        file, _ = QFileDialog.getSaveFileName(self, '输出.shp文件', '', 'Shapefiles (*.shp)')
        if file:
            self.output_shp = file
            self.output_label.setText(f'输出的的shp文件: {file}')

    def run_processing(self):
        self.input_text = self.text_input.text()
        self.selected_option = self.combo_box.currentText()

        print(f'SHP Input: {self.shp_input}')
        print(f'TIFF Input: {self.tiff_input}')
        print(f'Output SHP: {self.output_shp}')
        print(f'Input Text: {self.input_text}')
        print(f'Selected Option: {self.selected_option}')

        flag = 0
        if self.selected_option == '平均值':
            flag = 0
        if self.selected_option == '最大值':
            flag = 1
        if self.selected_option == '最小值':
            flag = 2

        print(f"flag: {flag}")

        get_value_and_update_shp(self.shp_input, self.tiff_input, self.input_text, self.output_shp, flag)

        msg_box = QMessageBox()
        msg_box.setText("运行完毕")
        msg_box.exec_()



if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ShapefileProcessingApp()
    window.show()
    sys.exit(app.exec_())

