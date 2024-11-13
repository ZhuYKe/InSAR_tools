#!/usr/bin/env python
#coding=utf-8
import signal
import csv
import os
import glob
import shutil
import time
import sys
import os.path
import tempfile
import subprocess
import re
import base64
import ssl
import socket
import netrc
import xml.etree.ElementTree as ET
import getpass

import pykml
import requests
from pykml import parser
import data_downloader
from data_downloader import downloader, parse_urls
from pathlib import Path
import pandas as pd
import datetime as dt

try:
	from urllib2 import build_opener, install_opener, Request, urlopen, HTTPError
	from urllib2 import URLError, HTTPSHandler, HTTPHandler, HTTPCookieProcessor
	from cookielib import MozillaCookieJar
	from StringIO import StringIO

except ImportError as e:
	from urllib.request import build_opener, install_opener, Request, urlopen
	from urllib.request import HTTPHandler, HTTPSHandler, HTTPCookieProcessor
	from urllib.error import HTTPError, URLError
	from http.cookiejar import MozillaCookieJar
	from io import StringIO

abort = False


def signal_handler(sig, frame):
	global abort
	sys.stderr.output("\n > Caught Signal. Exiting!\n")
	abort = True  # necessary to cause the program to stop
	raise SystemExit  # this will only abort the thread that the ctrl+c was caught in


class bulk_downloader:
	def __init__(self, download_name_list, username, password):
		# List of files to download
		self.files = download_name_list

		self.cookie_jar_path = os.path.join(os.path.expanduser('~'), ".bulk_download_cookiejar.txt")
		self.cookie_jar = None

		self.asf_urs4 = {'url': 'https://urs.earthdata.nasa.gov/oauth/authorize',
						 'client': 'BO_n7nTIlMljdvU6kRRB3g',
						 'redir': 'https://auth.asf.alaska.edu/login'}

		# Make sure we can write it our current directory
		if os.access(os.getcwd(), os.W_OK) is False:
			print("WARNING: Cannot write to current path! Check permissions for {0}".format(os.getcwd()))
			exit(-1)

		# For SSL
		self.context = {}

		# Make sure cookie_jar is good to go!
		self.get_cookie(username, password)

		# summary
		self.total_bytes = 0
		self.total_time = 0
		self.cnt = 0
		self.success = []
		self.failed = []
		self.skipped = []

	# Get and validate a cookie
	def get_cookie(self, username, password):
		if os.path.isfile(self.cookie_jar_path):
			self.cookie_jar = MozillaCookieJar()
			self.cookie_jar.load(self.cookie_jar_path)

			# make sure cookie is still valid
			if self.check_cookie():
				# print(" > Reusing previous cookie jar.")
				return True

		# Keep trying 'till user gets the right U:P
		while self.check_cookie() is False:
			self.get_new_cookie(username, password)
		return True

	# Validate cookie before we begin
	def check_cookie(self):

		global resp_code, response
		if self.cookie_jar is None:
			print(" > Cookiejar is bunk: {0}".format(self.cookie_jar))
			return False

		# File we know is valid, used to validate cookie
		file_check = 'https://urs.earthdata.nasa.gov/profile'

		# Apply custom Redirect Hanlder
		opener = build_opener(HTTPCookieProcessor(self.cookie_jar), HTTPHandler(), HTTPSHandler(**self.context))
		install_opener(opener)

		# Attempt a HEAD request
		request = Request(file_check)
		request.get_method = lambda: 'HEAD'
		try:
			# print(" > 尝试下载 {0}".format(file_check))
			response = urlopen(request, timeout=30)
			resp_code = response.getcode()
			# Make sure we're logged in
			if not self.check_cookie_is_logged_in(self.cookie_jar):
				return False

			# Save cookiejar
			self.cookie_jar.save(self.cookie_jar_path)

		except HTTPError:
			# If we ge this error, again, it likely means the user has not agreed to current EULA
			print("\nIMPORTANT: ")
			print("Your user appears to lack permissions to download data from the ASF Datapool.")
			print(
				"\n\nNew users: you must first log into Vertex and accept the EULA. In addition, your Study Area must be set at Earthdata https://urs.earthdata.nasa.gov")
			exit(-1)

		# This return codes indicate the USER has not been approved to download the data
		if resp_code in (300, 301, 302, 303):
			try:
				redir_url = response.info().getheader('Location')
			except AttributeError:
				redir_url = response.getheader('Location')

			# Funky Test env:
			if "vertex-retired.daac.asf.alaska.edu" in redir_url and "test" in self.asf_urs4['redir']:
				print("Cough, cough. It's dusty in this test env!")
				return True

			print("Redirect ({0}) occured, invalid cookie value!".format(resp_code))
			return False

		# These are successes!
		if resp_code in (200, 307):
			return True

		return False

	def get_new_cookie(self, username, password):
		# Start by prompting user to input their credentials

		# Another Python2/3 workaround
		global response
		# new_username = input("Username: ")
		new_username = username
		# new_password = getpass.getpass(prompt="Password (will not be displayed): ")
		new_password = password

		# Build URS4 Cookie request
		auth_cookie_url = self.asf_urs4['url'] + '?client_id=' + self.asf_urs4['client'] + '&redirect_uri=' + \
						  self.asf_urs4['redir'] + '&response_type=code&state='

		try:
			# python2
			user_pass = base64.b64encode(bytes(new_username + ":" + new_password))
		except TypeError:
			# python3
			user_pass = base64.b64encode(bytes(new_username + ":" + new_password, "utf-8"))
			user_pass = user_pass.decode("utf-8")

		# Authenticate against URS, grab all the cookies
		self.cookie_jar = MozillaCookieJar()
		opener = build_opener(HTTPCookieProcessor(self.cookie_jar), HTTPHandler(), HTTPSHandler(**self.context))
		request = Request(auth_cookie_url, headers={"Authorization": "Basic {0}".format(user_pass)})

		# Watch out cookie rejection!
		try:
			response = opener.open(request)
		except HTTPError as e:
			if "WWW-Authenticate" in e.headers and "Please enter your Earthdata Login credentials" in e.headers[
				"WWW-Authenticate"]:
				print(" > Username and Password combo was not successful. Please try again.")
				return False
			else:
				# If an error happens here, the user most likely has not confirmed EULA.
				print("\nIMPORTANT: There was an error obtaining a download cookie!")
				print("Your user appears to lack permission to download data from the ASF Datapool.")
				print(
					"\n\nNew users: you must first log into Vertex and accept the EULA. In addition, your Study Area must be set at Earthdata https://urs.earthdata.nasa.gov")
				exit(-1)
		except URLError as e:
			print("\nIMPORTANT: There was a problem communicating with URS, unable to obtain cookie. ")
			print("Try cookie generation later.")
			exit(-1)

		# Did we get a cookie?
		if self.check_cookie_is_logged_in(self.cookie_jar):
			# COOKIE SUCCESS!
			self.cookie_jar.save(self.cookie_jar_path)
			return True

		# if we aren't successful generating the cookie, nothing will work. Stop here!
		print("WARNING: Could not generate new cookie! Cannot proceed. Please try Username and Password again.")
		print("Response was {0}.".format(response.getcode()))
		print(
			"\n\nNew users: you must first log into Vertex and accept the EULA. In addition, your Study Area must be set at Earthdata https://urs.earthdata.nasa.gov")
		exit(-1)

	# make sure we're logged into URS
	def check_cookie_is_logged_in(self, cj):
		for cookie in cj:
			if cookie.name == 'urs_user_already_logged':
				# Only get this cookie if we logged in successfully!
				return True
		return False

	def download_file_with_cookiejar(self, url, file_count, total, tempfile_output_path, recursion=False):
		Tempfile_output_path = tempfile_output_path
		download_file = Tempfile_output_path + '/' + os.path.basename(url).split('?')[0]
		if os.path.isfile(download_file):
			try:
				request = Request(url)
				request.get_method = lambda: 'HEAD'
				response = urlopen(request, timeout=30)
				remote_size = self.get_total_size(response)
				# Check that we were able to derive a size.
				if remote_size:
					local_size = os.path.getsize(download_file)
					if (local_size + (local_size * .01)) > remote_size > (local_size - (local_size * .01)):
						print(" > Download file {0} exists! \n > Skipping download of {1}. ".format(download_file, url))
						return None, None
					# partial file size wasn't full file size, lets blow away the chunk and start again
					print(" > Found {0} but it wasn't fully downloaded. Removing file and downloading again.".format(
						download_file))
					os.remove(download_file)

			except ssl.CertificateError as e:
				print(" > ERROR: {0}".format(e))
				print(" > Could not validate SSL Cert. You may be able to overcome this using the --insecure flag")
				return False, None

			except HTTPError as e:
				if e.code == 401:
					print(" > IMPORTANT: Your user may not have permission to download this type of data!")
				else:
					print(" > Unknown Error, Could not get file HEAD: {0}".format(e))

			except URLError as e:
				print("URL Error (from HEAD): {0}, {1}".format(e.reason, url))
				if "ssl.c" in "{0}".format(e.reason):
					print(
						"IMPORTANT: Remote location may not be accepting your SSL configuration. This is a terminal error.")
				return False, None

		# attempt https connection
		try:
			request = Request(url)
			response = urlopen(request, timeout=30)

			# Watch for redirect
			if response.geturl() != url:

				# See if we were redirect BACK to URS for re-auth.
				if 'https://urs.earthdata.nasa.gov/oauth/authorize' in response.geturl():

					if recursion:
						print(" > Entering seemingly endless auth loop. Aborting. ")
						return False, None

					# make this easier. If there is no app_type=401, add it
					new_auth_url = response.geturl()
					if "app_type" not in new_auth_url:
						new_auth_url += "&app_type=401"

					print(" > While attempting to download {0}....".format(url))
					print(" > Need to obtain new cookie from {0}".format(new_auth_url))
					old_cookies = [cookie.name for cookie in self.cookie_jar]
					opener = build_opener(HTTPCookieProcessor(self.cookie_jar), HTTPHandler(),
										  HTTPSHandler(**self.context))
					request = Request(new_auth_url)
					try:
						response = opener.open(request)
						for cookie in self.cookie_jar:
							if cookie.name not in old_cookies:
								print(" > Saved new cookie: {0}".format(cookie.name))

								# A little hack to save session cookies
								if cookie.discard:
									cookie.expires = int(time.time()) + 60 * 60 * 24 * 30
									print(" > Saving session Cookie that should have been discarded! ")

						self.cookie_jar.save(self.cookie_jar_path, ignore_discard=True, ignore_expires=True)
					except HTTPError as e:
						print("HTTP Error: {0}, {1}".format(e.code, url))
						return False, None

					print(" > Attempting download again with new cookies!")
					return self.download_file_with_cookiejar(url, file_count, total, recursion=True)

				# print(" > 'Temporary' Redirect download @ Remote archive:\n > {0}".format(response.geturl()))

			# seems to be working
			print("【{0}/{1}】 正在下载：{2}".format(file_count, total, url))

			# Open our local file for writing and build status bar
			tf = tempfile.NamedTemporaryFile(mode='w+b', delete=False, dir=Tempfile_output_path)
			self.chunk_read(response, tf, report_hook=self.chunk_report)

			# Reset download status
			sys.stdout.write('\n')

			tempfile_name = tf.name
			tf.close()

		# handle errors
		except HTTPError as e:
			print("HTTP Error: {0}, {1}".format(e.code, url))

			if e.code == 401:
				print(" > IMPORTANT: Your user does not have permission to download this type of data!")

			if e.code == 403:
				print(" > Got a 403 Error trying to download this file.  ")
				print(" > You MAY need to log in this app and agree to a EULA. ")

			return False, None

		except URLError as e:
			print("URL Error (from GET): {0}, {1}, {2}".format(e, e.reason, url))
			if "ssl.c" in "{0}".format(e.reason):
				print(
					"IMPORTANT: Remote location may not be accepting your SSL configuration. This is a terminal error.")
			return False, None

		except socket.timeout as e:
			print(" > timeout requesting: {0}; {1}".format(url, e))
			return False, None

		except ssl.CertificateError as e:
			print(" > ERROR: {0}".format(e))
			print(" > Could not validate SSL Cert. You may be able to overcome this using the --insecure flag")
			return False, None

		# Return the file size
		shutil.copy(tempfile_name, download_file)
		os.remove(tempfile_name)
		file_size = self.get_total_size(response)
		actual_size = os.path.getsize(download_file)
		if file_size is None:
			# We were unable to calculate file size.
			file_size = actual_size
		return actual_size, file_size

	def get_redirect_url_from_error(self, error):
		find_redirect = re.compile(r"id=\"redir_link\"\s+href=\"(\S+)\"")
		print("error file was: {}".format(error))
		redirect_url = find_redirect.search(error)
		if redirect_url:
			print("Found: {0}".format(redirect_url.group(0)))
			return redirect_url.group(0)

		return None

	#  chunk_report taken from http://stackoverflow.com/questions/2028517/python-urllib2-progress-hook
	def chunk_report(self, bytes_so_far, file_size):

		if file_size is not None:
			percent = float(bytes_so_far) / file_size
			percent = round(percent * 100, 2)
			sys.stdout.write(" >已下载 %d/%d bytes (%0.2f%%)\r" %
							 (bytes_so_far, file_size, percent))
		else:
			# We couldn't figure out the size.
			sys.stdout.write(" > 已下载 %d/未知大小 bytes\r" % bytes_so_far)

	#  chunk_read modified from http://stackoverflow.com/questions/2028517/python-urllib2-progress-hook
	def chunk_read(self, response, local_file, chunk_size=8192, report_hook=None):
		file_size = self.get_total_size(response)
		bytes_so_far = 0

		while 1:
			try:
				chunk = response.read(chunk_size)
			except:
				sys.stdout.write("\n > There was an error reading data. \n")
				break

			try:
				local_file.write(chunk)
			except TypeError:
				local_file.write(chunk.decode(local_file.encoding))
			bytes_so_far += len(chunk)

			if not chunk:
				break

			if report_hook:
				report_hook(bytes_so_far, file_size)

		return bytes_so_far

	def get_total_size(self, response):
		try:
			file_size = response.info().getheader('Content-Length').strip()
		except AttributeError:
			try:
				file_size = response.getheader('Content-Length').strip()
			except AttributeError:
				print("> Problem getting size")
				return None

		return int(file_size)


	# Download all the files in the list
	def download_files(self, save_path):
		Save_path = save_path
		for file_name in self.files:
			failed_count = 0  # 记录失败次数
			while True:
				# make sure we haven't ctrl+c'd or some other abort trap
				if abort:
					raise SystemExit

				# download counter
				self.cnt += 1

				# set a timer
				start = time.time()

				# run download
				size, total_size = self.download_file_with_cookiejar(file_name, self.cnt, len(self.files), tempfile_output_path=Save_path)

				# calculte rate
				end = time.time()

				# stats:
				if size is None:
					self.skipped.append(file_name)
					break
				# Check to see that the download didn't error and is the correct size
				elif size is not False and ((size + (size * .01)) > total_size > (size - (size * .01))):
					# Download was good!
					elapsed = end - start
					elapsed = 1.0 if elapsed < 1 else elapsed
					rate = (size / 1024 ** 2) / elapsed

					print("共下载：{0}MB 用时：{1:.2f}秒, 平均速度: {2:.2f}MB/秒".format((size / 1024 ** 2), elapsed, rate))

					# add up metrics
					self.total_bytes += size
					self.total_time += elapsed
					self.success.append({'file': file_name, 'size': size})

					# 当前文件下载成功，跳出while循环进行下一个文件的下载
					break

				else:
					print("此文件下载出现问题：{0}".format(file_name))
					# 失败次数计数
					failed_count += 1
					self.cnt -= 1
					if failed_count >= 10:
						self.failed.append(file_name)
						# 如果失败次数达到10次，跳出while循环
						break
					else:
						print(f"再试一次，第{failed_count}次")
						continue

	def print_summary(self):
		# Print summary:
		print("\n\n")
		print("---------------------------下载完成-----------------------------------------")
		print("  下载成功 {0} 个文件, {1} bytes ".format(len(self.success), self.total_bytes))
		if len(self.failed) > 0:
			print("  下载失败: {0} 个文件".format(len(self.failed)))
			for failed_file in self.failed:
				print("          - {0}".format(failed_file))
		if len(self.skipped) > 0:
			print("  已下载，跳过: {0} 个文件".format(len(self.skipped)))
		if len(self.success) > 0:
			print("  平均下载速度: {0:.2f}MB/秒".format((self.total_bytes / 1024.0 ** 2) / self.total_time))
		print("--------------------------------------------------------------------------")


def remove_csv(csv_download_path):
	path = csv_download_path
	for infile in glob.glob(os.path.join(path, '*.csv')):
		os.remove(infile)


def read_csv_file(csv_download_path):
	path = csv_download_path + '/'
	file_name = []
	a = os.listdir(path)
	for j in a:
		if os.path.splitext(j)[1] == '.csv':
			file_name.append(j)

	name = ''.join(file_name)
	csv_path = path + name

	with open(csv_path, 'r') as file:
		reader = csv.reader(file)
		column_data = [row[25] for row in reader]
		column_data.pop(0)
	return column_data


def search_ASF_API(start_time, end_time, platform_choose, processinglevel_choose, beammode_choose, input_path,
				   input_frame, flight_direction):
	# ASF API
	asf_base_url = 'https://api.daac.asf.alaska.edu/services/search/param?'
	# 下载图像设置
	platform = 'platform=' + platform_choose + '&'  # Sentinel-1A
	processinglevel = 'processingLevel=' + processinglevel_choose + '&'  # SLC
	beammode = 'beamMode=' + beammode_choose + '&'  # IW
	starttime = 'start=' + start_time + 'T00:00:00UTC' + '&'
	endtime = 'end=' + end_time + 'T23:59:59UTC' + '&'
	path = 'relativeOrbit=' + input_path + '&'
	frame = 'asfframe=' + input_frame + '&'
	flightdirection = 'flightDirection=' + flight_direction + '&'
	output_set = 'output=csv'
	output_set_kml = 'output=kml'

	model = platform + processinglevel + beammode

	ASF_url_path_and_frame = asf_base_url + model + path + frame + starttime + endtime + flightdirection + output_set
	ASF_url_path_and_frame_kml = asf_base_url + model + path + frame + starttime + endtime + flightdirection + output_set_kml

	return ASF_url_path_and_frame, ASF_url_path_and_frame_kml


def get_min_bounding_rect_corners(kml_file_path):
	with open(kml_file_path, 'r') as file:
		kml_data = file.read()
		kml_data = kml_data.encode('ascii')
		root = pykml.parser.fromstring(kml_data)  # 获取Polygon的坐标
		coordinates = root.Document.Placemark.Polygon.outerBoundaryIs.LinearRing.coordinates.text.strip().split()  # 将坐标转换为浮点数列表
		coordinates = [list(map(float, coordinate.split(','))) for coordinate in coordinates]  # 获取最小外接矩形的四个角坐标
		x_coords = [coord[0] for coord in coordinates]
		y_coords = [coord[1] for coord in coordinates]
		minx = min(x_coords)
		maxx = max(x_coords)
		miny = min(y_coords)
		maxy = max(y_coords)
	return [(minx, miny), (minx, maxy), (maxx, maxy), (maxx, miny)]


def get_polygon(kml_file_path):
	corners_list = get_min_bounding_rect_corners(kml_file_path)
	corners_str = ''
	count = 0
	for corner in corners_list:
		list_a = list(corner)
		list_a_fore = [round(x, 4) for x in list_a]
		corner = str(list_a_fore)
		corner = corner.replace(' ', '')
		corner = corner.replace('[', '')
		corner = corner.replace(']', ',')
		if count == 0:
			save = ''.join(corner)
		corners_str = corners_str + corner
		count = count + 1
	corners_str = corners_str + save
	corners_str = corners_str[:-1]
	return corners_str


def filter_aux_poeorb_urls(aux_poeorb_urls, date_start, date_end, platform='all'):
	if platform in ['S1A', 'S1B', 'all']:
		if platform == 'all':
			platform = ['S1A', 'S1B']
		else:
			platform = [platform]
	else:
		raise ValueError("platform must be one of ['S1A', 'S1B','all']")

	date_start = pd.to_datetime(date_start).date()
	date_end = pd.to_datetime(date_end).date()

	_urls = [i for i in aux_poeorb_urls if Path(i).suffix == '.EOF']
	urls_filter = []
	for i in _urls:
		name = Path(i).stem
		dt_i = (pd.to_datetime(name.split('_')[-1]).date()
				- dt.timedelta(days=1))

		if (name[:3] in platform and
				date_start <= dt_i <= date_end):
			urls_filter.append(i)

	return urls_filter


def update_netrc(machine, login, password): 

	netrc_path = os.path.expanduser('~/.netrc')
	with open(netrc_path, 'w') as f:
		f.write(f"machine {machine}\n")
		f.write(f"    login {login}\n")
		f.write(f"    password {password}\n")
	os.chmod(netrc_path, 0o600)


def download_data(url, file_path):
	subprocess.run(["wget", url, "-O", file_path, "-q"])



def down_load_orbit(orbit_work_path, orbit_username, orbit_password, orbit_starttime, orbit_endtime):

	Orbit_path = orbit_work_path + '/' + 'Orbit'

	if not os.path.exists(Orbit_path):
		os.mkdir(Orbit_path)

	# 指定精密轨道数据的下载文件夹
	folder_preorb = Path(Orbit_path)


	orbit_starttime = orbit_starttime.replace("-", "")
	orbit_endtime = orbit_endtime.replace("-", "")
 
	update_netrc('urs.earthdata.nasa.gov', orbit_username, orbit_password)
	netrcObj = netrc.netrc()

	# 执行下载
	#  download precise orbit
	home_preorb = 'https://s1qc.asf.alaska.edu/aux_poeorb/'
	urls_preorb = parse_urls.from_html(home_preorb)

	urls = filter_aux_poeorb_urls(urls_preorb,
								  orbit_starttime, orbit_endtime,
								  'S1A')  # 获取所有S1A在Starttime-Endtime期间的精密轨道数据的链接
	for url in urls:
		file_name = url.split('/')[-1] #解析URL获取文件名
		if file_name not in os.listdir(folder_preorb):
			download_data(url, os.path.join(folder_preorb, file_name))
		else:
			print(f"{file_name} already exists. Skipping download.")

	urls = filter_aux_poeorb_urls(urls_preorb,
								  orbit_starttime, orbit_endtime,
								  'S1B')  # 获取所有S1B在Starttime-Endtime期间的精密轨道数据的链接
	for url in urls:
		file_name = url.split('/')[-1] #解析URL获取文件名
		if file_name not in os.listdir(folder_preorb):
			download_data(url, os.path.join(folder_preorb, file_name))
		else:
			print(f"{file_name} already exists. Skipping download.")


if __name__ == "__main__":

	if len(sys.argv) < 7:
		print("请按格式输入")
		print("<script_name> <Output_path> <FlightDirection> <Path> <Frame> <Starttime> <Endtime>")
		print("Output_path :SAR影像及Orbit输出文件夹保存的路径(需要是已存在的路径)")
		print("FlightDirection: 升降轨模式(A/D)")
		print("Path：像幅号")
		print("Frame：像幅号")
		print("Starttime ：下载图像的开始日期(YYYY-MM-DD)")
		print("Endtime ：下载图像的截止日期(YYYY-MM-DD)")
		sys.exit(1)

	Output_path = sys.argv[1]

	Output_path = Output_path + '/' + 'sentinel_orbit'
	if not os.path.exists(Output_path):
		os.mkdir(Output_path)

	Csv_download_path = Output_path + '/' + 'csv_save' + '/'  # csv文件下载路径
	csv_file_name = "url.csv"
	if not os.path.exists(Csv_download_path):
		os.mkdir(Csv_download_path)

	SLC_output_path = Output_path + '/' + 'SLC'  # 全部zip文件下载至输出文件夹

	# 参数选择
	Platform = 'Sentinel-1A'  # 卫星平台
	Processinglevel = 'SLC'  # 产品类型
	Beammode = 'IW'  # 成像模式

	FlightDirection = sys.argv[2]
	Input_path = sys.argv[3]
	Input_frame = sys.argv[4]
	Starttime = sys.argv[5]
	Endtime = sys.argv[6]

	# ASF账号、密码
	Username = 'laddermaster'
	# Username = sys.argv[7]
	Password = 'zykZYK1998'
	# Password = sys.argv[8]

	#  清空csv文件路径中的csv文件
	remove_csv(csv_download_path=Csv_download_path)


	url_flag = 1  # 0:仅使用kml  1:仅使用frame及path确定下载范围   2:使用kml及path确定下载范围
	#  查询ASF文件的api接口
	url = search_ASF_API(start_time=Starttime, end_time=Endtime, platform_choose=Platform,
						 processinglevel_choose=Processinglevel, beammode_choose=Beammode,
						 flight_direction=FlightDirection, input_path=Input_path,
						 input_frame=Input_frame)[0]

	print(url)

	#  使用requests库发送HTTP请求，获取文件内容
	response = requests.get(url)
	#  检查响应状态码是否为200（表示请求成功）
	if response.status_code == 200:
		# 使用urllib库将文件保存到本地
		with open(Csv_download_path + csv_file_name, 'wb') as f:
			f.write(response.content)
		print("csv文件获取成功！")
	else:
		print("csv文件获取失败！")

	#  读取csv文件，获得下载列表
	Download_list = read_csv_file(csv_download_path=Csv_download_path)
	#  删除csv下载文件夹
	shutil.rmtree(Csv_download_path)
	
	print("-—-—查询到SAR影像数量:-—-—-—")
	print(len(Download_list))

	print("--------文件名：--------")
	for i in Download_list:
		print(i)

	# 影像数据下载
	#  脚本所在路径下如果没有SLC_output输出文件夹，则在此位置创建SLC_output输出文件夹
	if not os.path.exists(SLC_output_path):
	   os.mkdir(SLC_output_path)

	# 根据下载列表下载zip文件，下载至脚本目录内
	signal.signal(signal.SIGINT, signal_handler)
	downloader = bulk_downloader(download_name_list=Download_list, username=Username, password=Password)
	# 下载
	downloader.download_files(save_path=SLC_output_path)
	# 下载进度可视化
	downloader.print_summary()

	time.sleep(2)

	print(f"SAR数据下载完毕，数据位于{SLC_output_path}文件夹内")

	# 精密轨道数据下载
	for name in Download_list:
		orbit_start_time = name[56:64]
		orbit_end_time = name[56:64]

		print(f"下载{orbit_start_time}精密轨道数据")

		down_load_orbit(orbit_work_path=Output_path, orbit_username=Username, orbit_password=Password,
							orbit_starttime=orbit_start_time, orbit_endtime=orbit_end_time)

	print(f"精密轨道数据下载完毕，数据位于{Output_path + '/Orbit'}文件夹内")






