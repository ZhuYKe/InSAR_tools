#!/usr/bin/env python
# coding=utf-8
import os
import re
import sys

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, \
    QMessageBox, QComboBox, QTextEdit, QFileDialog
from PyQt5.QtGui import QFont, QTextCursor


def txt2shp_short(file_path, name_file_path, save_path):
    result_path = save_path + '/' + 'shp'
    if not os.path.exists(result_path):
        os.mkdir(result_path)

    # 定义文件大小上限（G）和单个属性字段字节数
    file_size = 1.9
    data_size = 24

    # 读取txt文件并指定分隔符为', '
    with open(file_path, 'r') as f:
        # 读取文件内容
        content = f.read()

        # 使用正则表达式匹配分隔符
    delimiter_pattern = r', {2,3,4}'
    delimiter_match = re.search(delimiter_pattern, content)
    if delimiter_match:
        delimiter = delimiter_match.group()
    else:
        # 默认或错误处理
        delimiter = ","

    # 分割文本并获取行数和列数
    lines = content.split('\n')
    row_count = len(lines)
    col_count = len(re.split(delimiter, lines[0]))

    total_lines = row_count  # 总行数  # 11488305
    total_columns = col_count  # 总列数  # 73

    # 上限字符数量
    shp_size = round(file_size * 1024 * 1024 * 1024)  # 2040109466

    split_range = round(shp_size / data_size) // total_columns  # 85004561 // 73 = 1164446

    if (total_lines % split_range) == 0:
        file_number = total_lines // split_range  # 11488305 // 1164446 = 9
    else:
        file_number = (total_lines // split_range) + 1  # 11488305 // 1164446 + 1 = 10

    sys.stdout.write(f"\r预计输出shp数量 : {file_number}")

    start_line = 0

    sep = r'\s*,\s*'  # 逗号加数量不等的空格分隔符

    for i in range(1, file_number + 1):
        end_line = start_line + split_range

        # 使用pandas按行读取文件的部分数据
        df = pd.read_csv(file_path, delimiter=sep, header=None, engine='python', nrows=end_line - start_line, skiprows=start_line, usecols=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        new_columns = {0: "pt_num", 1: "x_img", 2: "y_img", 3: "lon", 4: "lat", 5: "hgt", 6: "def_V", 7: "sd_ph", 8: "unc_hgt", 9: "unc_V"}
        df = df.rename(columns=new_columns)

        sys.stdout.write(f"\r{df}")
        sys.stdout.write(f"\routput_{i}.shp写入中")
        # 创建几何列，将经纬度转换为Point对象
        geometry = [Point(xy) for xy in zip(df['lon'], df['lat'])]

        # 创建GeoDataFrame
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs='EPSG:4326')

        # 设置保存文件名
        output_file = result_path + '/' + f'output_{i}.shp'

        # 保存为点shp文件
        gdf.to_file(output_file, driver='ESRI Shapefile', index=False)
        sys.stdout.write(f"\routput_{i}.shp写入完毕")
        # 更新下一个文件的起始行数
        start_line = end_line


def txt2shp(file_path, name_file_path, save_path):
    result_path = save_path + '/' + 'shp'
    if not os.path.exists(result_path):
        os.mkdir(result_path)

    # 定义文件大小上限（G）和单个属性字段字节数
    file_size = 1.9
    data_size = 24

    # 读取txt文件并指定分隔符为', '
    with open(file_path, 'r') as f:
        # 读取文件内容
        content = f.read()

        # 使用正则表达式匹配分隔符
    delimiter_pattern = r', {2,3,4}'
    delimiter_match = re.search(delimiter_pattern, content)
    if delimiter_match:
        delimiter = delimiter_match.group()
    else:
        # 默认或错误处理
        delimiter = ","

    # 分割文本并获取行数和列数
    lines = content.split('\n')
    row_count = len(lines)
    col_count = len(re.split(delimiter, lines[0]))

    total_lines = row_count  # 总行数  # 11488305
    total_columns = col_count  # 总列数  # 73

    # 上限字符数量
    shp_size = round(file_size * 1024 * 1024 * 1024)  # 2040109466

    split_range = round(shp_size / data_size) // total_columns  # 85004561 // 73 = 1164446

    if (total_lines % split_range) == 0:
        file_number = total_lines // split_range  # 11488305 // 1164446 = 9
    else:
        file_number = (total_lines // split_range) + 1  # 11488305 // 1164446 + 1 = 10

    sys.stdout.write(f"\r预计输出shp数量 : {file_number}")

    start_line = 0

    sep = r'\s*,\s*'  # 逗号加数量不等的空格分隔符
    # base_name_list = ['pt_num', "x_img", "y_img", "lon(deg.)", "lat(deg.)", "hgt(m)", "defV(mm/y)", "sd_ph(rad)", "unc_hgt(m)", "uncV(mm/y)"]
    base_name_list = ['pt_num', "x_img", "y_img", "lon", "lat", "hgt", "def_V", "sd_ph", "unc_hgt", "unc_V"]
    # 打开文件
    with open(name_file_path, 'r') as file:
        # 跳过前10行
        for _ in range(10):
            next(file)

        # 初始化一个变量来保存日期部分
        date_value = None

        # 从第11行开始读取每行内容
        for line in file:
            # 检查行是否包含所需的内容
            if 'date: ' in line:
                # 找到 date: 后面的部分
                date_part = line.split('date: ')[1].strip()
                # 提取日期部分（"2016 10  2"）
                date_value = date_part[:10].replace("  ", "/0").replace(" ", "/")  # 提取前10个字符，即日期部分
                base_name_list.append(date_value)
                continue  # 继续下一行的处理

    for i in range(1, file_number + 1):
        end_line = start_line + split_range

        # 使用pandas按行读取文件的部分数据
        df = pd.read_csv(file_path, delimiter=sep, header=None, engine='python', nrows=end_line - start_line,
                         skiprows=start_line)
        # df = pd.read_csv(file_path, delimiter=sep, header=None, engine='python', nrows=end_line - start_line, skiprows=start_line, usecols=[3, 4, 5, 6])

        new_columns = {}
        for j in range(total_columns):
            field_name = base_name_list[j]
            new_columns[j] = field_name
        df = df.rename(columns=new_columns)

        sys.stdout.write(f"\r{df}")
        sys.stdout.write(f"\routput_{i}.shp写入中")
        # 创建几何列，将经纬度转换为Point对象
        geometry = [Point(xy) for xy in zip(df['lon'], df['lat'])]

        # 创建GeoDataFrame
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs='EPSG:4326')

        # 设置保存文件名
        output_file = result_path + '/' + f'output_{i}.shp'

        # 保存为点shp文件
        gdf.to_file(output_file, driver='ESRI Shapefile', index=False)
        sys.stdout.write(f"\routput_{i}.shp写入完毕")
        # 更新下一个文件的起始行数
        start_line = end_line


class ConsoleRedirector:
    def __init__(self, text_edit):
        self.text_edit = text_edit

    def write(self, message):
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(message)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()  # 确保光标可见

        # 实时刷新界面
        QApplication.processEvents()

    def flush(self):
        pass


# 完整版
class MyWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.geotiff_input = None
        self.workspace_input = None
        self.output_text = None
        self.initUI()


    def open_dialog0(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "TXT Files (*.txt)")
        if file_path:
            self.shp_input.setText(file_path)

    def open_dialog1(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "",  "TXT Files (*.txt)")
        if file_path:
            self.geotiff_input.setText(file_path)


    def open_dialog3(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹", "/")
        if folder_path:
            self.workspace_input.setText(folder_path)

    def initUI(self):
        self.setWindowTitle("完整版")
        self.setGeometry(800, 300, 500, 400)

        geotiff_input_label = QLabel(" 输入disp.txt : ")
        geotiff_input_label.setFont(QFont("Times New Roman", 12))
        self.geotiff_input = QLineEdit()
        self.geotiff_input.setReadOnly(True)  # 设置为只读
        self.geotiff_input.setFixedSize(160, 30)


        shp_input_label = QLabel("     输入list.txt : ")
        shp_input_label.setFont(QFont("Times New Roman", 12))
        self.shp_input = QLineEdit()
        self.shp_input.setReadOnly(True)  # 设置为只读
        self.shp_input.setFixedSize(160, 30)

        workspace_label = QLabel("     输出路径:")
        workspace_label.setFont(QFont("Times New Roman", 12))
        self.workspace_input = QLineEdit()
        self.workspace_input.setReadOnly(True)  # 设置为只读
        self.workspace_input.setFixedSize(160, 30)  # 设置输入框的大小


        run_button = QPushButton("开始运行")
        run_button.clicked.connect(self.runClicked)
        run_button.setFixedSize(100, 50)

        self.output_text = QTextEdit()
        self.output_text.setFixedSize(500, 150)
        self.output_text.setReadOnly(True)  # 设置为只读


        # 创建垂直布局，并将控件添加到布局中
        vbox = QVBoxLayout()

        # 创建各个控件
        self.button_dem = QPushButton('浏览', self)
        self.button_dem.clicked.connect(self.open_dialog0)

        self.button_geotiff = QPushButton('浏览', self)
        self.button_geotiff.clicked.connect(self.open_dialog1)

        self.button_workspace = QPushButton('浏览', self)
        self.button_workspace.clicked.connect(self.open_dialog3)


        # 创建水平布局5
        hbox1 = QHBoxLayout()
        hbox1.addWidget(geotiff_input_label)
        hbox1.addWidget(self.geotiff_input)
        hbox1.addWidget(self.button_geotiff)

        hbox1.addWidget(shp_input_label)
        hbox1.addWidget(self.shp_input)
        hbox1.addWidget(self.button_dem)

        hbox1.addStretch(1)  # 添加右侧弹性空间

        # 创建水平布局
        hbox2 = QHBoxLayout()
        hbox2.addStretch(1)  # 添加右侧弹性空间
        hbox2.addWidget(workspace_label)
        hbox2.addWidget(self.workspace_input)
        hbox2.addWidget(self.button_workspace)
        hbox2.addStretch(1)  # 添加右侧弹性空间

        hbox3 = QHBoxLayout()
        hbox3.addStretch(1)  # 添加左侧弹性空间
        hbox3.addWidget(run_button)
        hbox3.addStretch(1)  # 添加左侧弹性空间
        hbox3.addWidget(self.output_text)
        hbox3.addStretch(1)  # 添加左侧弹性空间

        # 将所有水平布局添加到垂直布局中
        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)
        vbox.addLayout(hbox3)

        self.setLayout(vbox)
        self.show()

    def runClicked(self):
        # 获取输入的值并进行处理
        file_path = self.geotiff_input.text()
        name_file_path = self.shp_input.text()

        save_path = self.workspace_input.text()

        # 重定向标准输出流到 QTextEdit
        sys.stdout = ConsoleRedirector(self.output_text)

        # 调用函数执行逻辑
        txt2shp(file_path, name_file_path, save_path)
        # print(file_path, name_file_path, save_path)

        msg_box = QMessageBox()
        msg_box.setText("运行完毕")
        msg_box.exec_()


# 快速版
class MyWindow2(QWidget):
    def __init__(self):
        super().__init__()
        self.geotiff_input = None
        self.workspace_input = None
        self.output_text = None
        self.initUI()

    def open_dialog0(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "TXT Files (*.txt)")
        if file_path:
            self.shp_input.setText(file_path)

    def open_dialog1(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "",  "TXT Files (*.txt)")
        if file_path:
            self.geotiff_input.setText(file_path)

    def open_dialog3(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹", "/")
        if folder_path:
            self.workspace_input.setText(folder_path)

    def initUI(self):
        self.setWindowTitle("快速版(仅输出简单信息)")
        self.setGeometry(800, 300, 500, 400)

        geotiff_input_label = QLabel(" 输入disp.txt : ")
        geotiff_input_label.setFont(QFont("Times New Roman", 12))
        self.geotiff_input = QLineEdit()
        self.geotiff_input.setReadOnly(True)  # 设置为只读
        self.geotiff_input.setFixedSize(160, 30)


        shp_input_label = QLabel("     输入list.txt : ")
        shp_input_label.setFont(QFont("Times New Roman", 12))
        self.shp_input = QLineEdit()
        self.shp_input.setReadOnly(True)  # 设置为只读
        self.shp_input.setFixedSize(160, 30)

        workspace_label = QLabel("     输出路径:")
        workspace_label.setFont(QFont("Times New Roman", 12))
        self.workspace_input = QLineEdit()
        self.workspace_input.setReadOnly(True)  # 设置为只读
        self.workspace_input.setFixedSize(160, 30)  # 设置输入框的大小


        run_button = QPushButton("开始运行")
        run_button.clicked.connect(self.runClicked)
        run_button.setFixedSize(100, 50)

        self.output_text = QTextEdit()
        self.output_text.setFixedSize(500, 150)
        self.output_text.setReadOnly(True)  # 设置为只读


        # 创建垂直布局，并将控件添加到布局中
        vbox = QVBoxLayout()

        # 创建各个控件
        self.button_dem = QPushButton('浏览', self)
        self.button_dem.clicked.connect(self.open_dialog0)

        self.button_geotiff = QPushButton('浏览', self)
        self.button_geotiff.clicked.connect(self.open_dialog1)

        self.button_workspace = QPushButton('浏览', self)
        self.button_workspace.clicked.connect(self.open_dialog3)


        # 创建水平布局5
        hbox1 = QHBoxLayout()
        hbox1.addWidget(geotiff_input_label)
        hbox1.addWidget(self.geotiff_input)
        hbox1.addWidget(self.button_geotiff)

        hbox1.addWidget(shp_input_label)
        hbox1.addWidget(self.shp_input)
        hbox1.addWidget(self.button_dem)

        hbox1.addStretch(1)  # 添加右侧弹性空间

        # 创建水平布局
        hbox2 = QHBoxLayout()
        hbox2.addStretch(1)  # 添加右侧弹性空间
        hbox2.addWidget(workspace_label)
        hbox2.addWidget(self.workspace_input)
        hbox2.addWidget(self.button_workspace)
        hbox2.addStretch(1)  # 添加右侧弹性空间

        hbox3 = QHBoxLayout()
        hbox3.addStretch(1)  # 添加左侧弹性空间
        hbox3.addWidget(run_button)
        hbox3.addStretch(1)  # 添加左侧弹性空间
        hbox3.addWidget(self.output_text)
        hbox3.addStretch(1)  # 添加左侧弹性空间

        # 将所有水平布局添加到垂直布局中
        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)
        vbox.addLayout(hbox3)

        self.setLayout(vbox)
        self.show()

    def runClicked(self):
        # 获取输入的值并进行处理
        file_path = self.geotiff_input.text()
        name_file_path = self.shp_input.text()

        save_path = self.workspace_input.text()

        # 重定向标准输出流到 QTextEdit
        sys.stdout = ConsoleRedirector(self.output_text)

        # 调用函数执行逻辑
        txt2shp_short(file_path, name_file_path, save_path)
        # print(file_path, name_file_path, save_path)

        msg_box = QMessageBox()
        msg_box.setText("运行完毕")
        msg_box.exec_()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('disp.txt_to_shp')
        self.setGeometry(700, 300, 500, 230)

        button1 = QPushButton('完整版', self)
        button1.setFixedSize(280, 60)
        button1.clicked.connect(self.open_new_window1)

        button2 = QPushButton('快速版(仅输出简单信息)', self)
        button2.setFixedSize(280, 60)
        button2.clicked.connect(self.open_new_window2)

        vbox = QVBoxLayout()
        hbox_1 = QHBoxLayout()
        hbox_1.addStretch(1)  # 添加左侧弹性空间
        hbox_1.addWidget(button1)
        hbox_1.addWidget(button2)
        hbox_1.addStretch(1)  # 添加左侧弹性空间
        vbox.addLayout(hbox_1)

        self.setLayout(vbox)
        self.show()


    def open_new_window1(self):
        self.new_window1 = MyWindow()
        self.new_window1.show()

    def open_new_window2(self):
        self.new_window2 = MyWindow2()
        self.new_window2.show()



if __name__ == '__main__':

    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())

