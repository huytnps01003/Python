# -*- coding: utf-8 -*-
# Cần cài đặt: pip install opencv-python pillow tk pure-python-adb numpy uiautomator2

# --- BIẾN TOÀN CỤC LƯU SỐ QUÂN CUỐI CÙNG ---
last_known_black_count_global = 0
last_known_white_count_global = 0

import tkinter as tk
from tkinter import scrolledtext, messagebox, font as tkfont
import threading
import time
import cv2
import numpy as np
import os
from io import BytesIO
from PIL import Image, ImageTk
import sys
import logging
from logging.handlers import RotatingFileHandler
import json
import math
import copy
import multiprocessing as mp
from collections import defaultdict
import random
from tkinter import ttk
import subprocess
import shutil # Thêm import này cho shutil.which
import traceback # Thêm import này cho traceback.format_exc()

# --- KHAI BÁO BIẾN TOÀN CỤC CHO TRẠNG THÁI VÀ THIẾT BỊ ---
adb_device = None
u2_device = None
is_running = False
auto_thread = None
current_scenario = None 
selected_target_name = "" # Sẽ được cập nhật bởi on_target_selected_internal

# Biến đếm thắng thua
win_count = 0
loss_count = 0
draw_count = 0

# Biến cho game hiện tại
current_game_ai_color = None
ai_color_locked_this_game = False
ai_moved = False
current_game_moves = []
last_known_board_state_for_opponent_move = None
waiting_room_enter_time = None
stop_after_current_game = False # Biến logic (stop_after_current_game_var là của Tkinter)

# --- HÀM TÍNH WIN% TỪ SCORE ---
def compute_win_probability(score: float, k: float = 0.1) -> float:
    """
    Sử dụng hàm logistic để map score thành xác suất thắng.
    k điều khiển độ dốc của đường cong (có thể tinh chỉnh).
    """
    p = 1.0 / (1.0 + math.exp(-k * score))
    return round(p * 100, 1)

# --- Import ADB ---
try:
    from ppadb.client import Client as AdbClient
except ImportError:
    print("Lỗi: Không tìm thấy thư viện pure-python-adb.")
    print("Vui lòng cài đặt: pip install pure-python-adb")
    sys.exit()

# --- Import UI Automator 2 ---
try:
    import uiautomator2 as u2
except ImportError:
    print("\n"+"="*50)
    print("Lỗi: Không tìm thấy thư viện uiautomator2.")
    print("Đây là thư viện cần thiết để chụp màn hình nhanh hơn.")
    print("Vui lòng cài đặt bằng lệnh:")
    print("   pip install uiautomator2")
    print("Sau đó chạy lệnh này để khởi tạo trên điện thoại (chỉ lần đầu):")
    print("   python -m uiautomator2 init")
    print("="*50 + "\n")
    u2 = None

# --- Hằng số ---
CPU_WORKERS = 16       # Số luồng CPU cho AI
DESIGN_WIDTH = 720       # Chiều rộng màn hình game chuẩn
DESIGN_HEIGHT = 1560     # Chiều cao màn hình game chuẩn

# Khởi tạo Pool đa luồng toàn cục
_pool = None

# Tọa độ và màu nút "100 xu"
CLICK_100XU_X = 314
CLICK_100XU_Y = 812
MENU_PIXEL_X = 314
MENU_PIXEL_Y = 812
MENU_PIXEL_COLOR = (134, 81, 153)
MENU_PIXEL_TOLERANCE = 10

DEFAULT_TARGET_NAME = "100 Xu"
TARGET_OPTIONS = {
    "10 Xu": {"X": 320, "Y": 593, "RGB": (89, 112, 58), "TOLERANCE": 15},
    "100 Xu": {
        "X": CLICK_100XU_X,
        "Y": CLICK_100XU_Y,
        "RGB": MENU_PIXEL_COLOR, # Giả sử màu của "100 Xu" giống MENU_PIXEL
        "TOLERANCE": MENU_PIXEL_TOLERANCE # Giả sử tolerance giống MENU_PIXEL
    },
    "Thế cờ hằng ngày": {"X": 319, "Y": 969, "RGB": (255, 225, 177), "TOLERANCE": 15}
    # Người dùng có thể thêm các mục tiêu khác vào đây
    # Ví dụ:
    # "Another Target": {
    #     "X": 123,
    #     "Y": 456,
    #     "RGB": (10, 20, 30),
    #     "TOLERANCE": 5
    # }
}

# Tọa độ và màu pixel chỉ báo lượt đi AI
TURN_PIXEL_X = 455
TURN_PIXEL_Y = 385
TURN_PIXEL_COLOR = (120, 67, 17)
TURN_PIXEL_TOLERANCE = 10

# Tọa độ và màu pixel chỉ báo lượt đi ĐỐI THỦ (mới)
OPPONENT_TURN_PIXEL_X = 260
OPPONENT_TURN_PIXEL_Y = 388
OPPONENT_TURN_PIXEL_COLOR = (118, 66, 18)
OPPONENT_TURN_PIXEL_TOLERANCE = 10 # Giữ nguyên tolerance

# Tọa độ pixel để nhận diện màu quân AI
AI_COLOR_DETECT_PIXEL_X = 484
AI_COLOR_DETECT_PIXEL_Y = 398
AI_COLOR_DETECT_PIXEL_COLOR_BLACK = (63, 62, 70)
AI_COLOR_DETECT_PIXEL_COLOR_WHITE = (218, 233, 238)
AI_COLOR_DETECT_PIXEL_TOLERANCE = 20

# Màu pixel nhận diện quân Đen/Trắng trên bàn cờ
PIECE_COLOR_BLACK = (55, 55, 65)
PIECE_COLOR_WHITE = (220, 230, 239)
PIECE_COLOR_TOLERANCE_BLACK = 19 # đang chỉnh sửa nhận thiếu xuống thì tăng lên , nhận dư nước thì giảm xuống
PIECE_COLOR_TOLERANCE_WHITE = 10# Giữ nguyên giá trị cũ cho màu trắng (có thể điều chỉnh sau)

# Độ lệch màu cho custom‐pixel (khi check dựa vào CUSTOM_PIECE_DATA)
CUSTOM_PIECE_TOLERANCE_BLACK = 10 # Giữ nguyên giá trị cũ cho màu đen (custom)
CUSTOM_PIECE_TOLERANCE_WHITE = 6 # Giữ nguyên giá trị cũ cho màu trắng (custom)

# Độ lệch màu cho fallback pixel trung tâm (khi skin mặc định)


# Tọa độ bàn cờ và ô (sẽ được tính toán)
BOARD_X, BOARD_Y, BOARD_W, BOARD_H = 100, 550, 520, 520
CELL_WIDTH, CELL_HEIGHT = 65, 65
BOARD_SIZE = 8
cell_centers = []


# Tọa độ nút "Trở về" hoặc "Lối thoát" sau game
ENDGAME_CLICK_X = 123
ENDGAME_CLICK_Y = 1219
ENDGAME_PIXEL_X = 123
ENDGAME_PIXEL_Y = 1219
ENDGAME_PIXEL_COLOR = (198, 171, 160)
ENDGAME_PIXEL_TOLERANCE = 10

# Hằng số nhận diện thắng/thua bằng pixel
WIN_PIXEL_X = 338
WIN_PIXEL_Y = 335
WIN_PIXEL_COLOR = (212, 87, 81)
WIN_PIXEL_TOLERANCE = 15

LOSS_PIXEL_X = 521
LOSS_PIXEL_Y = 547
LOSS_PIXEL_COLOR = (121, 124, 133)
LOSS_PIXEL_TOLERANCE = 15 # Giữ nguyên tolerance

# Hằng số nhận diện và xử lý lỗi mạng
NETWORK_ERROR_PIXEL_X = 354
NETWORK_ERROR_PIXEL_Y = 847
NETWORK_ERROR_PIXEL_COLOR = (233, 120, 24)
NETWORK_ERROR_PIXEL_TOLERANCE = 20 # Giữ nguyên tolerance, có thể điều chỉnh nếu cần
NETWORK_ERROR_CLICK_X = 354
NETWORK_ERROR_CLICK_Y = 847

# --- DỮ LIỆU NHẬN DIỆN QUÂN CỜ TÙY CHỈNH ---
CUSTOM_PIECE_DATA = [
    {"r": 0, "c": 0, "x": 133, "y": 592, "rgb": (46, 140, 214), "piece": "B"},
    {"r": 1, "c": 0, "x": 130, "y": 654, "rgb": (66, 157, 228), "piece": "B"},
    {"r": 2, "c": 0, "x": 128, "y": 720, "rgb": (49, 167, 217), "piece": "B"},
    {"r": 3, "c": 0, "x": 130, "y": 788, "rgb": (64, 189, 237), "piece": "B"},
    {"r": 4, "c": 0, "x": 130, "y": 852, "rgb": (63, 172, 231), "piece": "B"},
    {"r": 5, "c": 0, "x": 130, "y": 919, "rgb": (50, 180, 229), "piece": "B"},
    {"r": 6, "c": 0, "x": 126, "y": 983, "rgb": (51, 167, 214), "piece": "B"},
    {"r": 7, "c": 0, "x": 128, "y": 1049, "rgb": (48, 177, 219), "piece": "B"},
    {"r": 0, "c": 1, "x": 192, "y": 593, "rgb": (17, 179, 194), "piece": "B"},
    {"r": 1, "c": 1, "x": 190, "y": 659, "rgb": (32, 176, 203), "piece": "B"},
    {"r": 2, "c": 1, "x": 192, "y": 722, "rgb": (30, 175, 206), "piece": "B"},
    {"r": 3, "c": 1, "x": 194, "y": 786, "rgb": (58, 165, 217), "piece": "B"},
    {"r": 4, "c": 1, "x": 192, "y": 850, "rgb": (50, 148, 211), "piece": "B"},
    {"r": 5, "c": 1, "x": 192, "y": 918, "rgb": (46, 171, 215), "piece": "B"},
    {"r": 6, "c": 1, "x": 192, "y": 987, "rgb": (19, 185, 201), "piece": "B"},
    {"r": 7, "c": 1, "x": 194, "y": 1049, "rgb": (57, 178, 223), "piece": "B"},
    {"r": 0, "c": 2, "x": 250, "y": 592, "rgb": (39, 208, 229), "piece": "B"},
    {"r": 1, "c": 2, "x": 260, "y": 658, "rgb": (58, 208, 241), "piece": "B"},
    {"r": 2, "c": 2, "x": 261, "y": 722, "rgb": (67, 201, 238), "piece": "B"},
    {"r": 3, "c": 2, "x": 261, "y": 786, "rgb": (61, 177, 228), "piece": "B"},
    {"r": 4, "c": 2, "x": 260, "y": 852, "rgb": (63, 177, 227), "piece": "B"},
    {"r": 5, "c": 2, "x": 260, "y": 916, "rgb": (57, 151, 213), "piece": "B"},
    {"r": 6, "c": 2, "x": 261, "y": 985, "rgb": (69, 207, 244), "piece": "B"},
    {"r": 7, "c": 2, "x": 260, "y": 1049, "rgb": (60, 183, 225), "piece": "B"},
    {"r": 0, "c": 3, "x": 325, "y": 589, "rgb": (53, 162, 218), "piece": "B"},
    {"r": 1, "c": 3, "x": 325, "y": 654, "rgb": (56, 155, 220), "piece": "B"},
    {"r": 2, "c": 3, "x": 324, "y": 719, "rgb": (48, 145, 213), "piece": "B"},
    {"r": 3, "c": 3, "x": 327, "y": 783, "rgb": (64, 142, 227), "piece": "B"},
    {"r": 4, "c": 3, "x": 324, "y": 852, "rgb": (46, 166, 216), "piece": "B"},
    {"r": 5, "c": 3, "x": 327, "y": 916, "rgb": (60, 154, 216), "piece": "B"},
    {"r": 6, "c": 3, "x": 327, "y": 983, "rgb": (65, 170, 228), "piece": "B"},
    {"r": 7, "c": 3, "x": 325, "y": 1048, "rgb": (61, 166, 221), "piece": "B"},
    {"r": 0, "c": 4, "x": 386, "y": 590, "rgb": (45, 181, 219), "piece": "B"},
    {"r": 1, "c": 4, "x": 390, "y": 656, "rgb": (39, 167, 204), "piece": "B"},
    {"r": 2, "c": 4, "x": 391, "y": 720, "rgb": (62, 169, 225), "piece": "B"},
    {"r": 3, "c": 4, "x": 393, "y": 786, "rgb": (51, 150, 209), "piece": "B"},
    {"r": 4, "c": 4, "x": 393, "y": 852, "rgb": (60, 170, 231), "piece": "B"},
    {"r": 5, "c": 4, "x": 391, "y": 921, "rgb": (45, 205, 229), "piece": "B"},
    {"r": 6, "c": 4, "x": 391, "y": 985, "rgb": (47, 181, 218), "piece": "B"},
    {"r": 7, "c": 4, "x": 391, "y": 1048, "rgb": (58, 163, 218), "piece": "B"},
    {"r": 0, "c": 5, "x": 455, "y": 590, "rgb": (47, 172, 218), "piece": "B"},
    {"r": 1, "c": 5, "x": 457, "y": 656, "rgb": (52, 181, 221), "piece": "B"},
    {"r": 2, "c": 5, "x": 455, "y": 720, "rgb": (57, 160, 218), "piece": "B"},
    {"r": 3, "c": 5, "x": 457, "y": 786, "rgb": (59, 159, 211), "piece": "B"},
    {"r": 4, "c": 5, "x": 459, "y": 853, "rgb": (62, 180, 230), "piece": "B"},
    {"r": 5, "c": 5, "x": 455, "y": 918, "rgb": (47, 172, 218), "piece": "B"},
    {"r": 6, "c": 5, "x": 455, "y": 983, "rgb": (49, 167, 215), "piece": "B"},
    {"r": 7, "c": 5, "x": 455, "y": 1048, "rgb": (56, 162, 220), "piece": "B"},
    {"r": 0, "c": 6, "x": 523, "y": 592, "rgb": (59, 208, 238), "piece": "B"},
    {"r": 1, "c": 6, "x": 523, "y": 656, "rgb": (55, 191, 231), "piece": "B"},
    {"r": 2, "c": 6, "x": 520, "y": 722, "rgb": (38, 177, 210), "piece": "B"},
    {"r": 3, "c": 6, "x": 521, "y": 788, "rgb": (21, 173, 197), "piece": "B"},
    {"r": 4, "c": 6, "x": 521, "y": 853, "rgb": (20, 164, 198), "piece": "B"},
    {"r": 5, "c": 6, "x": 521, "y": 919, "rgb": (25, 163, 202), "piece": "B"},
    {"r": 6, "c": 6, "x": 523, "y": 983, "rgb": (58, 169, 225), "piece": "B"},
    {"r": 7, "c": 6, "x": 523, "y": 1046, "rgb": (56, 139, 219), "piece": "B"},
    {"r": 0, "c": 7, "x": 590, "y": 590, "rgb": (64, 180, 227), "piece": "B"},
    {"r": 1, "c": 7, "x": 587, "y": 656, "rgb": (39, 168, 207), "piece": "B"},
    {"r": 2, "c": 7, "x": 589, "y": 720, "rgb": (63, 167, 220), "piece": "B"},
    {"r": 3, "c": 7, "x": 589, "y": 786, "rgb": (54, 170, 219), "piece": "B"},
    {"r": 4, "c": 7, "x": 587, "y": 853, "rgb": (30, 164, 199), "piece": "B"},
    {"r": 5, "c": 7, "x": 587, "y": 918, "rgb": (42, 167, 211), "piece": "B"},
    {"r": 6, "c": 7, "x": 590, "y": 983, "rgb": (56, 171, 216), "piece": "B"},
    {"r": 7, "c": 7, "x": 585, "y": 1049, "rgb": (47, 180, 221), "piece": "B"},
    {"r": 0, "c": 0, "x": 130, "y": 587, "rgb": (251, 183, 148), "piece": "W"},
    {"r": 1, "c": 0, "x": 128, "y": 658, "rgb": (255, 213, 185), "piece": "W"},
    {"r": 2, "c": 0, "x": 130, "y": 727, "rgb": (255, 223, 201), "piece": "W"},
    {"r": 3, "c": 0, "x": 128, "y": 786, "rgb": (255, 193, 163), "piece": "W"},
    {"r": 4, "c": 0, "x": 130, "y": 855, "rgb": (251, 199, 177), "piece": "W"},
    {"r": 5, "c": 0, "x": 126, "y": 918, "rgb": (255, 196, 156), "piece": "W"},
    {"r": 6, "c": 0, "x": 131, "y": 983, "rgb": (243, 180, 145), "piece": "W"},
    {"r": 7, "c": 0, "x": 131, "y": 1049, "rgb": (242, 179, 144), "piece": "W"},
    {"r": 0, "c": 1, "x": 195, "y": 593, "rgb": (255, 212, 186), "piece": "W"},
    {"r": 1, "c": 1, "x": 194, "y": 659, "rgb": (255, 214, 187), "piece": "W"},
    {"r": 2, "c": 1, "x": 192, "y": 723, "rgb": (246, 195, 166), "piece": "W"},
    {"r": 3, "c": 1, "x": 195, "y": 786, "rgb": (255, 190, 158), "piece": "W"},
    {"r": 4, "c": 1, "x": 194, "y": 852, "rgb": (255, 199, 165), "piece": "W"},
    {"r": 5, "c": 1, "x": 194, "y": 919, "rgb": (255, 209, 173), "piece": "W"},
    {"r": 6, "c": 1, "x": 195, "y": 983, "rgb": (252, 189, 154), "piece": "W"},
    {"r": 7, "c": 1, "x": 195, "y": 1052, "rgb": (255, 211, 188), "piece": "W"},
    {"r": 0, "c": 2, "x": 263, "y": 590, "rgb": (246, 180, 146), "piece": "W"},
    {"r": 1, "c": 2, "x": 260, "y": 658, "rgb": (255, 210, 179), "piece": "W"},
    {"r": 2, "c": 2, "x": 260, "y": 720, "rgb": (255, 197, 165), "piece": "W"},
    {"r": 3, "c": 2, "x": 260, "y": 789, "rgb": (255, 210, 186), "piece": "W"},
    {"r": 4, "c": 2, "x": 260, "y": 853, "rgb": (255, 204, 170), "piece": "W"},
    {"r": 5, "c": 2, "x": 258, "y": 919, "rgb": (246, 194, 157), "piece": "W"},
    {"r": 6, "c": 2, "x": 260, "y": 983, "rgb": (255, 196, 160), "piece": "W"},
    {"r": 7, "c": 2, "x": 258, "y": 1049, "rgb": (250, 191, 157), "piece": "W"},
    {"r": 0, "c": 3, "x": 324, "y": 590, "rgb": (251, 193, 155), "piece": "W"},
    {"r": 1, "c": 3, "x": 325, "y": 658, "rgb": (255, 210, 177), "piece": "W"},
    {"r": 2, "c": 3, "x": 324, "y": 722, "rgb": (250, 195, 164), "piece": "W"},
    {"r": 3, "c": 3, "x": 324, "y": 788, "rgb": (253, 198, 167), "piece": "W"},
    {"r": 4, "c": 3, "x": 324, "y": 853, "rgb": (250, 194, 161), "piece": "W"},
    {"r": 5, "c": 3, "x": 325, "y": 918, "rgb": (255, 200, 167), "piece": "W"},
    {"r": 6, "c": 3, "x": 325, "y": 983, "rgb": (254, 196, 159), "piece": "W"},
    {"r": 7, "c": 3, "x": 325, "y": 1049, "rgb": (255, 197, 165), "piece": "W"},
    {"r": 0, "c": 4, "x": 390, "y": 592, "rgb": (254, 203, 176), "piece": "W"},
    {"r": 1, "c": 4, "x": 391, "y": 658, "rgb": (255, 213, 182), "piece": "W"},
    {"r": 2, "c": 4, "x": 391, "y": 723, "rgb": (255, 208, 181), "piece": "W"},
    {"r": 3, "c": 4, "x": 390, "y": 788, "rgb": (248, 198, 163), "piece": "W"},
    {"r": 4, "c": 4, "x": 393, "y": 852, "rgb": (251, 186, 154), "piece": "W"},
    {"r": 5, "c": 4, "x": 393, "y": 918, "rgb": (252, 187, 157), "piece": "W"},
    {"r": 6, "c": 4, "x": 388, "y": 982, "rgb": (252, 196, 159), "piece": "W"},
    {"r": 7, "c": 4, "x": 393, "y": 1049, "rgb": (249, 188, 157), "piece": "W"},
    {"r": 0, "c": 5, "x": 455, "y": 589, "rgb": (255, 195, 158), "piece": "W"},
    {"r": 1, "c": 5, "x": 457, "y": 654, "rgb": (255, 191, 156), "piece": "W"},
    {"r": 2, "c": 5, "x": 455, "y": 720, "rgb": (247, 193, 159), "piece": "W"},
    {"r": 3, "c": 5, "x": 457, "y": 788, "rgb": (255, 210, 181), "piece": "W"},
    {"r": 4, "c": 5, "x": 457, "y": 852, "rgb": (255, 196, 164), "piece": "W"},
    {"r": 5, "c": 5, "x": 455, "y": 919, "rgb": (249, 196, 164), "piece": "W"},
    {"r": 6, "c": 5, "x": 455, "y": 985, "rgb": (246, 197, 164), "piece": "W"},
    {"r": 7, "c": 5, "x": 457, "y": 1048, "rgb": (255, 198, 168), "piece": "W"},
    {"r": 0, "c": 6, "x": 524, "y": 590, "rgb": (255, 198, 162), "piece": "W"},
    {"r": 1, "c": 6, "x": 524, "y": 658, "rgb": (255, 210, 177), "piece": "W"},
    {"r": 2, "c": 6, "x": 524, "y": 723, "rgb": (255, 206, 174), "piece": "W"},
    {"r": 3, "c": 6, "x": 521, "y": 786, "rgb": (253, 191, 154), "piece": "W"},
    {"r": 4, "c": 6, "x": 524, "y": 855, "rgb": (255, 213, 186), "piece": "W"},
    {"r": 5, "c": 6, "x": 521, "y": 918, "rgb": (250, 189, 158), "piece": "W"},
    {"r": 6, "c": 6, "x": 523, "y": 982, "rgb": (255, 192, 154), "piece": "W"},
    {"r": 7, "c": 6, "x": 523, "y": 1049, "rgb": (255, 200, 166), "piece": "W"},
    {"r": 0, "c": 7, "x": 585, "y": 590, "rgb": (255, 199, 162), "piece": "W"},
    {"r": 1, "c": 7, "x": 592, "y": 658, "rgb": (246, 183, 150), "piece": "W"},
    {"r": 2, "c": 7, "x": 592, "y": 722, "rgb": (245, 182, 149), "piece": "W"},
    {"r": 3, "c": 7, "x": 592, "y": 786, "rgb": (246, 177, 144), "piece": "W"},
    {"r": 4, "c": 7, "x": 590, "y": 852, "rgb": (253, 190, 159), "piece": "W"},
    {"r": 5, "c": 7, "x": 590, "y": 918, "rgb": (252, 196, 163), "piece": "W"},
    {"r": 6, "c": 7, "x": 590, "y": 980, "rgb": (255, 181, 149), "piece": "W"},
    {"r": 7, "c": 7, "x": 592, "y": 1049, "rgb": (246, 180, 148), "piece": "W"},
]

CELL_BLACK_MAP = {}  # key: (r,c) → list of (x,y,(R,G,B))
CELL_WHITE_MAP = {}  # key: (r,c) → list of (x,y,(R,G,B))

def build_custom_piece_maps():
    """Chuyển CUSTOM_PIECE_DATA thành hai map BLACK / WHITE."""
    global CELL_BLACK_MAP, CELL_WHITE_MAP
    CELL_BLACK_MAP.clear()
    CELL_WHITE_MAP.clear()

    for entry in CUSTOM_PIECE_DATA:
        r, c = entry["r"], entry["c"]
        x, y = entry["x"], entry["y"]
        rgb = tuple(entry["rgb"])  # e.g. (R,G,B)
        piece = entry["piece"].upper()  # 'B' hoặc 'W'

        if piece == "B":
            CELL_BLACK_MAP.setdefault((r,c), []).append((x, y, rgb))
        elif piece == "W":
            CELL_WHITE_MAP.setdefault((r,c), []).append((x, y, rgb))
        else:
            # Nếu có piece khác, bỏ qua
            continue
    log_message(f"Đã xây dựng xong custom piece maps. Black map có {len(CELL_BLACK_MAP)} entries, White map có {len(CELL_WHITE_MAP)} entries.")

def check_pixel_match(cv_img, x, y, target_rgb, tolerance):
    """
    Giống check_pixel_color nhưng rõ ràng hơn:
    - x,y: tọa độ pixel trên ảnh
    - target_rgb: tuple (R, G, B) cần so sánh
    - tolerance: ± lớn nhất cho mỗi kênh
    """
    if cv_img is None: # Thêm kiểm tra cv_img is None
        return False
    img_h, img_w = cv_img.shape[:2]
    if x < 0 or x >= img_w or y < 0 or y >= img_h:
        return False
    try:
        b_actual, g_actual, r_actual = cv_img[y, x]
        r_t, g_t, b_t = target_rgb
        return (abs(int(r_actual) - r_t) <= tolerance and
                abs(int(g_actual) - g_t) <= tolerance and
                abs(int(b_actual) - b_t) <= tolerance)
    except Exception as e: # Bắt lỗi chung và ghi log nếu cần
        # log_message(f"Lỗi trong check_pixel_match tại ({x},{y}): {e}", level=logging.DEBUG)
        return False

# --- Hằng số cho phòng chờ ghép đội
WAITING_ROOM_PIXEL_X = 625
WAITING_ROOM_PIXEL_Y = 99
WAITING_ROOM_PIXEL_COLOR = (19, 11, 8)
WAITING_ROOM_PIXEL_TOLERANCE = 10
WAITING_ROOM_BACK_CLICK_X = 28
WAITING_ROOM_BACK_CLICK_Y = 102
WAITING_ROOM_TIMEOUT_SECONDS = 60 # THAY ĐỔI TỪ 10 LÊN 60

# Trọng số cho việc đánh giá Mobilité
MOBILITY_WEIGHT_INITIAL = 15  # Tăng rất mạnh để ưu tiên mobility
MOBILITY_WEIGHT_MIDGAME = 25  # Tăng rất mạnh ở giữa game
MOBILITY_WEIGHT_LATEGAME = 40 # Tăng cực mạnh ở cuối game
FORCE_PASS_BONUS = 800      # Tăng cực mạnh thưởng khi ép pass
PASS_PENALTY = -600         # Tăng mạnh phạt khi bị pass
STABLE_EDGE_PIECE_WEIGHT = 60 # Tăng mạnh giá trị quân ổn định
PIECE_COUNT_WEIGHT_EARLY_MID = -2.0 # Tăng mạnh phạt khi có nhiều quân
PIECE_COUNT_WEIGHT_LATE = 0.5       # Giảm thưởng ở cuối game
BAD_MOVE_THRESHOLD = -40            # Hạ mạnh ngưỡng nước đi xấu
TRAP_SITUATION_WEIGHT = 150         # Tăng cực mạnh việc ép đối thủ

# --- HỌC TỪ KINH NGHIỆM ---
EXPERIENCE_FILE_PATH = "reversi_experience.json"
loaded_game_experiences = []
# OPENING_BOOK_DEPTH = 12       # Bỏ, sẽ dùng thống kê
# OPENING_BOOK_WIN_BONUS = 85   # Bỏ
# OPENING_BOOK_LOSS_PENALTY = 90 # Bỏ

# Thống kê khai cuộc mới
opening_stats = {}
OPENING_BOOK_STATISTICAL_WEIGHT_FACTOR = 50 # Có thể điều chỉnh

# Tọa độ tâm ô A1 và H8
A1_CENTER_X, A1_CENTER_Y = 128, 589
H8_CENTER_X, H8_CENTER_Y = 587, 1051

# Tọa độ tâm ô A1 và H8 cho màn hình KẾT THÚC GAME

# --- MA TRẬN TRỌNG SỐ VỊ TRÍ ĐỘNG THEO GIAI ĐOẠN ---
# Giai đoạn ĐẦU GAME: Thận trọng, tránh C/X squares, ưu tiên mobility và trung tâm nhẹ.
STATIC_POSITIONAL_WEIGHTS_EARLY = [
    [ 150, -80,  30,   5,   5,  30, -80, 150], # Tăng mạnh giá trị góc
    [-80, -150, -20,  -5,  -5, -20, -150, -80], # Tăng mạnh phạt X-squares
    [ 30, -20,   8,   2,   2,   8,  -20,  30],
    [  5,  -5,   2,   1,   1,   2,  -5,   5],
    [  5,  -5,   2,   1,   1,   2,  -5,   5],
    [ 30, -20,   8,   2,   2,   8,  -20,  30],
    [-80, -150, -20,  -5,  -5, -20, -150, -80],
    [ 150, -80,  30,   5,   5,  30, -80, 150]
]

# Giai đoạn GIỮA GAME: Góc quan trọng hơn, C/X vẫn rất tệ, cạnh bắt đầu có giá trị.
STATIC_POSITIONAL_WEIGHTS_MID = [
    [ 200, -100,  40,   8,   8,  40, -100, 200],
    [-100, -200, -30,  -8,  -8, -30, -200, -100],
    [ 40, -30,  10,   3,   3,  10,  -30,  40],
    [  8,  -8,   3,   2,   2,   3,  -8,   8],
    [  8,  -8,   3,   2,   2,   3,  -8,   8],
    [ 40, -30,  10,   3,   3,  10,  -30,  40],
    [-100, -200, -30,  -8,  -8, -30, -200, -100],
    [ 200, -100,  40,   8,   8,  40, -100, 200]
]

# Giai đoạn CUỐI GAME: Góc là vua, C/X vẫn phải tránh nếu không an toàn.
STATIC_POSITIONAL_WEIGHTS_LATE = [
    [ 300, -120,  50,  10,  10,  50, -120, 300],
    [-120, -250, -40, -10, -10, -40, -250, -120],
    [ 50, -40,  15,   3,   3,  15,  -40,  50],
    [ 10, -10,   3,   2,   2,   3,  -10,  10],
    [ 10, -10,   3,   2,   2,   3,  -10,  10],
    [ 50, -40,  15,   3,   3,  15,  -40,  50],
    [-120, -250, -40, -10, -10, -40, -250, -120],
    [ 300, -120,  50,  10,  10,  50, -120, 300]
]

def calculate_board_geometry():
    """Tính toán BOARD_POS, CELL_WIDTH/HEIGHT và cell_centers dựa trên A1, H8."""
    global BOARD_X, BOARD_Y, BOARD_W, BOARD_H, CELL_WIDTH, CELL_HEIGHT, cell_centers

    if H8_CENTER_X <= A1_CENTER_X or H8_CENTER_Y <= A1_CENTER_Y:
        log_message("Lỗi: Tọa độ tâm A1, H8 không hợp lệ (H8 phải ở dưới bên phải A1).", level=logging.ERROR)
        BOARD_X, BOARD_Y, BOARD_W, BOARD_H = 0, 0, 0, 0
        CELL_WIDTH, CELL_HEIGHT = 0, 0
        cell_centers = []
        return

    total_width_centers = H8_CENTER_X - A1_CENTER_X
    total_height_centers = H8_CENTER_Y - A1_CENTER_Y

    CELL_WIDTH = total_width_centers / (BOARD_SIZE - 1.0)
    CELL_HEIGHT = total_height_centers / (BOARD_SIZE - 1.0)

    BOARD_X = int(round(A1_CENTER_X - CELL_WIDTH / 2.0))
    BOARD_Y = int(round(A1_CENTER_Y - CELL_HEIGHT / 2.0))

    BOARD_W = int(round(CELL_WIDTH * BOARD_SIZE))
    BOARD_H = int(round(CELL_HEIGHT * BOARD_SIZE))

    log_message(f"Tính toán Geometry: Cell({CELL_WIDTH:.2f}, {CELL_HEIGHT:.2f}), BoardXY({BOARD_X}, {BOARD_Y}), BoardWH({BOARD_W}, {BOARD_H})")

    temp_centers = []
    for r in range(BOARD_SIZE):
        row_centers = []
        for c in range(BOARD_SIZE):
            center_x = BOARD_X + c * CELL_WIDTH + CELL_WIDTH / 2.0
            center_y = BOARD_Y + r * CELL_HEIGHT + CELL_HEIGHT / 2.0
            row_centers.append((int(round(center_x)), int(round(center_y))))
        temp_centers.append(row_centers)

    cell_centers = temp_centers
    log_message(f"Đã tính toán và lưu {len(cell_centers) * len(cell_centers[0])} tọa độ tâm ô.")

def setup_logging():
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%H:%M:%S')
    log_file = "reversi_adb_log_main.txt" # Đổi tên file log để phân biệt
    try:
        file_handler = RotatingFileHandler(log_file, maxBytes=2*1024*1024, backupCount=1, encoding='utf-8')
        file_handler.setFormatter(log_formatter)
        logging.getLogger().addHandler(file_handler)
        logging.getLogger().setLevel(logging.INFO)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(log_formatter)
        logging.getLogger().addHandler(stream_handler)
        print(f"Logging được thiết lập. Ghi vào file: {log_file}")
    except Exception as e:
        print(f"Lỗi khi thiết lập logging: {e}")

def log_message(message, level=logging.INFO):
    logging.log(level, message)
    if root and log_area and log_area.winfo_exists():
        def update_log_on_gui():
            if log_area.winfo_exists():
                log_area.config(state=tk.NORMAL)
                timestamp = time.strftime('%H:%M:%S')
                log_area.insert(tk.END, f"{timestamp} - {message}\n")
                log_area.see(tk.END)
                log_area.config(state=tk.DISABLED)
        try:
            root.after(0, update_log_on_gui)
        except tk.TclError:
            pass

# --- Các hàm ADB ---
def connect_adb_device():
    global adb_device, u2_device
    if adb_device:
        try:
            adb_device.shell("echo test > /dev/null")
            return True
        except Exception:
            log_message("Mất kết nối ADB (ppadb), đang thử kết nối lại...", level=logging.WARNING)
            adb_device = None
            u2_device = None # Reset u2 nếu ppadb mất

    log_message("Đang tìm thiết bị ADB (sử dụng ppadb)...")
    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        devices = client.devices()
        if not devices:
            log_message("Không tìm thấy thiết bị ADB nào (ppadb).", level=logging.ERROR)
            messagebox.showerror("Lỗi ADB", "Không tìm thấy thiết bị ADB. Hãy đảm bảo điện thoại đã kết nối và bật USB Debugging.")
            adb_device = None
            return False
        adb_device = devices[0]
        log_message(f"Đã kết nối ADB (ppadb) thành công với thiết bị: {adb_device.serial}")
        return True
    except ConnectionRefusedError:
        log_message("Lỗi: Không thể kết nối tới ADB server (ppadb). ADB server chưa chạy?", level=logging.ERROR)
        messagebox.showerror("Lỗi ADB", "Không thể kết nối tới ADB server. Hãy đảm bảo ADB server đang chạy.")
        adb_device = None
        return False
    except Exception as e:
        log_message(f"Lỗi không xác định khi kết nối ADB (ppadb): {e}", level=logging.ERROR)
        messagebox.showerror("Lỗi ADB", f"Lỗi kết nối ADB (ppadb) không xác định:\n{e}")
        adb_device = None
        return False

def adb_screencap():
    global u2_device
    if not u2:
        log_message("Lỗi: Thiếu thư viện uiautomator2. Không thể chụp màn hình.", level=logging.ERROR)
        return None
    if not u2_device:
        if is_running:
             log_message("Lỗi: Chưa kết nối uiautomator2 để chụp màn hình.", level=logging.ERROR)
        return None
    try:
        t_start_ss = time.monotonic()
        pil_image = u2_device.screenshot(format="pillow")
        ss_time = time.monotonic() - t_start_ss
        if pil_image is None:
             log_message("uiautomator2 screenshot trả về None.", level=logging.WARNING)
             return None
        t_start_resize = time.monotonic()
        try:
             resized_image = pil_image.resize((DESIGN_WIDTH, DESIGN_HEIGHT), Image.Resampling.LANCZOS)
        except AttributeError:
             resized_image = pil_image.resize((DESIGN_WIDTH, DESIGN_HEIGHT), Image.LANCZOS)
        resize_time = time.monotonic() - t_start_resize
        # log_message(f"[Profile Screencap] u2: {ss_time*1000:.1f}ms, Resize: {resize_time*1000:.1f}ms", level=logging.DEBUG)
        return resized_image
    except Exception as e:
        log_message(f"Lỗi khi chụp màn hình uiautomator2: {e}", level=logging.ERROR)
        err_str = str(e).lower()
        if "adbconnectionreseterror" in err_str or "disconnected" in err_str or "jsonrpcerror" in err_str or "socket connection broken" in err_str:
            log_message("Kết nối uiautomator2 có thể đã bị ngắt. Sẽ thử kết nối lại.", level=logging.WARNING)
            u2_device = None
        return None

def click_at(x, y):
    global adb_device # Đảm bảo rằng chúng ta đang tham chiếu đến adb_device toàn cục
    if not adb_device:
        log_message("Trong click_at: adb_device is None. Thử kết nối lại thiết bị đã chọn...", level=logging.WARNING)
        if not connect_to_selected_device(): # connect_to_selected_device sẽ cập nhật adb_device toàn cục
            log_message("Trong click_at: Vẫn không kết nối được ADB. Click thất bại.", level=logging.ERROR)
            return
        else:
            log_message("Trong click_at: Kết nối lại ADB thành công. Tiếp tục click.", level=logging.INFO)
    
    # Kiểm tra lại adb_device sau khi có thể đã kết nối lại
    if not adb_device: # Phòng trường hợp connect_to_selected_device() không thành công nhưng không trả về False rõ ràng (ít khả năng)
        log_message("Lỗi: Không có thiết bị ADB sau khi thử kết nối lại trong click_at.", level=logging.ERROR)
        return

    if x is None or y is None or x < 0 or y < 0:
        log_message(f"Lỗi: Tọa độ click không hợp lệ ({x}, {y}).", level=logging.ERROR)
        return
    x_int, y_int = int(round(x)), int(round(y))
    t_start_click = time.monotonic()
    shell_time = 0
    try:
        command = f"input tap {x_int} {y_int}"
        t_start_shell = time.monotonic()
        adb_device.shell(command)
        shell_time = time.monotonic() - t_start_shell
        # time.sleep(0.03) # ĐÃ XÓA
    except Exception as e:
        log_message(f"Lỗi khi thực hiện ADB tap tại ({x_int}, {y_int}): {e}", level=logging.ERROR)
        if "device offline" in str(e).lower() or "connection reset" in str(e).lower():
             log_message("Thiết bị ADB offline/reset trong click_at. Thử kết nối lại thiết bị ĐÃ CHỌN...", level=logging.WARNING)
             if not connect_to_selected_device():
                 log_message("Click_at: Thất bại kết nối lại thiết bị đã chọn sau lỗi. Click có thể không hoạt động.", level=logging.ERROR)
    finally:
        total_click_time = time.monotonic() - t_start_click
        # log_message(f"[Profile Click] Total: {total_click_time*1000:.1f}ms, Shell: {shell_time*1000:.1f}ms", level=logging.DEBUG)
        pass

def pick_coordinate_and_color():
    global u2_device # u2_device là biến toàn cục, sẽ được cập nhật bởi connect_to_selected_device
    if is_running:
        messagebox.showwarning("Đang chạy", "Vui lòng dừng auto trước khi chọn tọa độ.")
        return

    # Sử dụng hàm connect_to_selected_device để đảm bảo kết nối đúng thiết bị
    if not connect_to_selected_device():
        # connect_to_selected_device đã xử lý log và messagebox khi có lỗi
        return

    # Sau khi connect_to_selected_device() được gọi, adb_device và u2_device (biến toàn cục)
    # đã được cố gắng thiết lập dựa trên lựa chọn của người dùng.
    # Bây giờ, kiểm tra xem u2_device có được kết nối thành công không.
    if not u2_device:
        log_message("Chọn tọa độ: Không thể kết nối uiautomator2 với thiết bị đã chọn. Vui lòng kiểm tra lại.", level=logging.ERROR)
        messagebox.showerror("Lỗi uiautomator2", "Không thể kết nối uiautomator2 với thiết bị đã chọn.\n"
                                         "Hãy đảm bảo thiết bị hỗ trợ và uiautomator2 đã được khởi tạo (python -m uiautomator2 init).")
        return

    log_message("Đang chụp màn hình để chọn tọa độ (sử dụng uiautomator2 đã kết nối)...")
    screenshot_pil = adb_screencap() # adb_screencap sử dụng u2_device toàn cục
    if screenshot_pil is None:
        messagebox.showerror("Lỗi", "Không thể chụp ảnh màn hình từ thiết bị.")
        return

    img_w, img_h = screenshot_pil.width, screenshot_pil.height
    win = tk.Toplevel(root)
    win.title("Chọn tọa độ & Màu - Click để lấy tọa độ, kéo để chụp ảnh")
    win.attributes("-topmost", True)
    screen_w, screen_h = win.winfo_screenwidth(), win.winfo_screenheight()
    scale = min(0.9 * screen_w / img_w, 0.9 * screen_h / img_h, 1.0)
    disp_w, disp_h = int(img_w * scale), int(img_h * scale)
    try:
        img_disp_pil = screenshot_pil.resize((disp_w, disp_h), Image.Resampling.LANCZOS)
    except AttributeError:
        img_disp_pil = screenshot_pil.resize((disp_w, disp_h), Image.LANCZOS)
    photo = ImageTk.PhotoImage(img_disp_pil)
    canvas = tk.Canvas(win, width=disp_w, height=disp_h, cursor="cross")
    canvas.pack()
    canvas.create_image(0, 0, image=photo, anchor='nw')
    canvas.image = photo

    # Biến để theo dõi trang thái kéo
    start_x = start_y = end_x = end_y = None
    dragging = False
    rect_id = None

    def on_mouse_down(event):
        nonlocal start_x, start_y, dragging, rect_id
        start_x, start_y = event.x, event.y
        dragging = False  # Bắt đầu click nhưng chưa kéo
        
    def on_mouse_move(event):
        nonlocal start_x, start_y, end_x, end_y, dragging, rect_id
        if start_x is not None and start_y is not None:  # Nếu đã nhấn chuột xuống
            current_x, current_y = event.x, event.y
            # Nếu kéo đủ xa (>5 pixels) thì coi như đang kéo
            if not dragging and (abs(current_x - start_x) > 5 or abs(current_y - start_y) > 5):
                dragging = True
            
            if dragging:
                end_x, end_y = current_x, current_y
                # Xóa rectangle cũ nếu có
                if rect_id is not None:
                    canvas.delete(rect_id)
                # Vẽ rectangle mới
                rect_id = canvas.create_rectangle(
                    start_x, start_y, end_x, end_y,
                    outline="red", width=2
                )

    def on_mouse_up(event):
        nonlocal start_x, start_y, end_x, end_y, dragging, rect_id
        
        if not dragging:  # Nếu chỉ click không kéo -> xử lý như cũ
            click_x_disp, click_y_disp = event.x, event.y
            real_x, real_y = int(click_x_disp / scale), int(click_y_disp / scale)
            try:
                pixel_color = screenshot_pil.getpixel((real_x, real_y))
                r, g, b = pixel_color[:3] if isinstance(pixel_color, tuple) else (pixel_color, pixel_color, pixel_color)
                result_msg = f"Tọa độ gốc: ({real_x}, {real_y})\nMàu RGB: ({r}, {g}, {b})"
                log_message(f"Đã chọn điểm: {result_msg}")
                if messagebox.askyesno("Kết quả", f"{result_msg}\n\nBạn có muốn copy thông tin này?", parent=win):
                    try:
                        root.clipboard_clear()
                        root.clipboard_append(f"X={real_x}, Y={real_y}, RGB=({r}, {g}, {b})")
                        log_message("Đã copy vào clipboard.")
                    except tk.TclError:
                        log_message("Không thể truy cập clipboard.", level=logging.WARNING)
            except IndexError:
                messagebox.showerror("Lỗi", "Không thể lấy màu pixel.", parent=win)
            except Exception as e:
                 messagebox.showerror("Lỗi", f"Có lỗi xảy ra: {e}", parent=win)
        
        else:  # Nếu đã kéo -> lưu ảnh vùng được chọn
            if end_x is None or end_y is None:
                end_x, end_y = event.x, event.y
            
            # Đảm bảo tọa độ start < end
            sx, sy = min(start_x, end_x), min(start_y, end_y)
            ex, ey = max(start_x, end_x), max(start_y, end_y)
            
            # Chuyển tọa độ hiển thị sang tọa độ thật
            real_sx, real_sy = int(sx / scale), int(sy / scale)
            real_ex, real_ey = int(ex / scale), int(ey / scale)
            
            # Crop ảnh gốc
            try:
                cropped_img = screenshot_pil.crop((real_sx, real_sy, real_ex, real_ey))
                
                # Hiển thị hộp thoại lưu file
                from tkinter import filedialog
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".png",
                    filetypes=[("PNG files", "*.png"), ("All Files", "*.*")],
                    title="Lưu ảnh đã chụp",
                    parent=win
                )
                
                if file_path:
                    cropped_img.save(file_path)
                    log_message(f"Đã lưu ảnh vào: {file_path}")
                    messagebox.showinfo("Thành công", f"Đã lưu ảnh vào: {file_path}", parent=win)
            except Exception as e:
                log_message(f"Lỗi khi lưu ảnh: {e}", level=logging.ERROR)
                messagebox.showerror("Lỗi", f"Không thể lưu ảnh: {e}", parent=win)
        
        # Reset các biến
        if rect_id is not None:
            canvas.delete(rect_id)
        start_x = start_y = end_x = end_y = None
        dragging = False
        rect_id = None

    # Gán các hàm xử lý sự kiện
    canvas.bind("<ButtonPress-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_move)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)
    
    # Sửa lỗi không thể ẩn cửa sổ xuống (minimize)
    # Thay vì grab_set() sẽ dùng transient và focus
    win.transient(root)  # Đặt cửa sổ là transient của cửa sổ chính
    win.focus_set()      # Đặt focus cho cửa sổ
    
    # Protocol khi đóng cửa sổ
    def on_window_close():
        win.destroy()
        
    win.protocol("WM_DELETE_WINDOW", on_window_close)
    
    # Cho phép ẩn xuống và hỗ trợ các nút minimize, maximize
    win.wm_attributes("-toolwindow", 0)
    
    # Đặt vị trí cửa sổ
    win_w, win_h = disp_w, disp_h + 50  # Thêm chiều cao cho các nút nếu có
    x_pos = root.winfo_x() + (root.winfo_width() - win_w) // 2
    y_pos = root.winfo_y() + (root.winfo_height() - win_h) // 2
    win.geometry(f"{win_w}x{win_h}+{max(0, x_pos)}+{max(0, y_pos)}")
    
    win.wait_window()

def click_and_verify(r, c, player_color, retries=2, delay=0.25, click_random_range=2):
    """
    Thử click vào ô (r,c) và sau đó kiểm tra xem quân đã xuất hiện chưa.
    Nếu chưa, retry tối đa retries lần.
    Thêm một chút ngẫu nhiên vào tọa độ click.
    """
    global cell_centers # Đảm bảo cell_centers được cập nhật
    if not cell_centers or r >= len(cell_centers) or c >= len(cell_centers[r]):
        log_message(f"Lỗi: cell_centers không hợp lệ hoặc tọa độ ({r},{c}) ngoài phạm vi trong click_and_verify.", level=logging.ERROR)
        return False

    for attempt in range(retries + 1): # retries=2 nghĩa là thử 3 lần (0, 1, 2)
        base_x, base_y = cell_centers[r][c]
        
        # Thêm ngẫu nhiên vào tọa độ click
        offset_x = random.randint(-click_random_range, click_random_range)
        offset_y = random.randint(-click_random_range, click_random_range)
        click_x_final = base_x + offset_x
        click_y_final = base_y + offset_y

        log_message(f"ClickVerify (Thử {attempt + 1}/{retries + 1}): Click tại ({click_x_final},{click_y_final}) cho ô ({r},{c})", level=logging.DEBUG)
        click_at(click_x_final, click_y_final)
        time.sleep(delay) # Chờ cho game xử lý click

        screenshot_after_click = adb_screencap()
        if screenshot_after_click is None:
            log_message(f"ClickVerify (Thử {attempt + 1}): Không chụp được màn hình sau click. Tiếp tục...", level=logging.WARNING)
            if attempt < retries: time.sleep(delay * 2) # Chờ lâu hơn nếu không chụp được màn hình
            continue # Thử lại

        cv_img_after_click = cv2.cvtColor(np.array(screenshot_after_click), cv2.COLOR_RGB2BGR)
        board_state_after_click, _, _ = get_board_state_cv(cv_img_after_click)

        if board_state_after_click and r < len(board_state_after_click) and c < len(board_state_after_click[r]):
            if board_state_after_click[r][c] == player_color:
                log_message(f"ClickVerify (Thử {attempt + 1}): Xác nhận thành công quân {player_color} tại ({r},{c}).", level=logging.INFO)

                # --- CẬP NHẬT last_known_board_state sau khi AI đi và xác nhận ---
                global last_known_board_state_for_opponent_move
                last_known_board_state_for_opponent_move = [row[:] for row in board_state_after_click]
                log_message(f"ClickVerify: Đã cập nhật last_known_board_state sau nước đi của AI tại ({r},{c}).", level=logging.DEBUG)
                # --- Kết thúc cập nhật ---

                return True
            else:
                log_message(f"ClickVerify (Thử {attempt + 1}): Ô ({r},{c}) là '{board_state_after_click[r][c]}', mong đợi '{player_color}'.", level=logging.DEBUG)
        else:
            log_message(f"ClickVerify (Thử {attempt + 1}): Không lấy được trạng thái ô ({r},{c}) sau click.", level=logging.WARNING)
        
        if attempt < retries:
            log_message(f"ClickVerify (Thử {attempt + 1}): Thất bại, chuẩn bị thử lại...", level=logging.DEBUG)
            time.sleep(delay) # Chờ thêm trước khi thử lại
            
    log_message(f"ClickVerify: Thất bại sau {retries + 1} lần thử cho ô ({r},{c}), màu {player_color}.", level=logging.WARNING)
    return False

# --- Các hàm nhận diện trạng thái ---
def check_pixel_color(cv_img, x, y, target_rgb, tolerance):
    if cv_img is None or y < 0 or y >= cv_img.shape[0] or x < 0 or x >= cv_img.shape[1]:
        return False
    try:
        b, g, r_val = cv_img[y, x]
        r_target, g_target, b_target = target_rgb
        return (abs(int(r_val) - r_target) <= tolerance and
                abs(int(g) - g_target) <= tolerance and
                abs(int(b) - b_target) <= tolerance)
    except IndexError:
        return False
    except Exception as e:
        log_message(f"Lỗi khi kiểm tra pixel ({x},{y}): {e}", level=logging.WARNING)
        return False

def get_board_state_cv(cv_img):
    global cell_centers
    if not cell_centers:
        calculate_board_geometry()
        if not cell_centers:
            log_message("Vẫn chưa tính được tọa độ tâm ô.", level=logging.ERROR)
            empty = [['' for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
            return empty, 0, 0

    if cv_img is None:
        log_message("Ảnh không hợp lệ để quét bàn cờ.", level=logging.ERROR)
        empty = [['' for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        return empty, 0, 0

    board_state = [['' for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    black_count, white_count = 0, 0
    img_h, img_w = cv_img.shape[:2]

    for r_idx in range(BOARD_SIZE):
        for c_idx in range(BOARD_SIZE):
            # --- 1) Dò custom‐pixel: BLACK trước ---
            cell_black_list = CELL_BLACK_MAP.get((r_idx, c_idx), [])
            found = False
            for (x_pix, y_pix, target_rgb) in cell_black_list:
                if 0 <= y_pix < img_h and 0 <= x_pix < img_w:
                    if check_pixel_match(cv_img, x_pix, y_pix, target_rgb, CUSTOM_PIECE_TOLERANCE_BLACK):
                        board_state[r_idx][c_idx] = 'B'
                        black_count += 1
                        found = True
                        break
            if found:
                continue

            # --- 2) Dò custom‐pixel: WHITE ---
            cell_white_list = CELL_WHITE_MAP.get((r_idx, c_idx), [])
            for (x_pix, y_pix, target_rgb) in cell_white_list:
                if 0 <= y_pix < img_h and 0 <= x_pix < img_w:
                    if check_pixel_match(cv_img, x_pix, y_pix, target_rgb, CUSTOM_PIECE_TOLERANCE_WHITE):
                        board_state[r_idx][c_idx] = 'W'
                        white_count += 1
                        found = True
                        break
            if found:
                continue

            # --- 3) Fallback: check pixel trung tâm ô với PIECE_COLOR_TOLERANCE ---
            try:
                # Đảm bảo cell_centers[r_idx][c_idx] tồn tại trước khi truy cập
                if not cell_centers or r_idx >= len(cell_centers) or c_idx >= len(cell_centers[r_idx]):
                    log_message(f"Lỗi: Tọa độ ({r_idx},{c_idx}) không hợp lệ cho cell_centers trong fallback.", level=logging.WARNING)
                    continue # Bỏ qua ô này nếu tọa độ không hợp lệ

                center_x, center_y = cell_centers[r_idx][c_idx]
                if check_pixel_color(cv_img, center_x, center_y, PIECE_COLOR_BLACK, PIECE_COLOR_TOLERANCE_BLACK):
                    board_state[r_idx][c_idx] = 'B'
                    black_count += 1
                elif check_pixel_color(cv_img, center_x, center_y, PIECE_COLOR_WHITE, PIECE_COLOR_TOLERANCE_WHITE):
                    board_state[r_idx][c_idx] = 'W'
                    white_count += 1
                # Nếu không match cả hai, để trống
            except IndexError: # Xử lý cụ thể IndexError nếu cell_centers có cấu trúc không mong muốn
                log_message(f"Lỗi IndexError khi truy cập cell_centers[{r_idx}][{c_idx}] trong fallback: {e}", level=logging.WARNING)
            except Exception as e:
                log_message(f"Lỗi fallback pixel ô ({r_idx},{c_idx}): {e}", level=logging.WARNING)

    return board_state, black_count, white_count

def detect_ai_color_cv(cv_img):
    if cv_img is None: return None
    if check_pixel_color(cv_img, AI_COLOR_DETECT_PIXEL_X, AI_COLOR_DETECT_PIXEL_Y, AI_COLOR_DETECT_PIXEL_COLOR_BLACK, AI_COLOR_DETECT_PIXEL_TOLERANCE):
        return 'B'
    if check_pixel_color(cv_img, AI_COLOR_DETECT_PIXEL_X, AI_COLOR_DETECT_PIXEL_Y, AI_COLOR_DETECT_PIXEL_COLOR_WHITE, AI_COLOR_DETECT_PIXEL_TOLERANCE):
        return 'W'
    return None

# --- Logic Cờ lật & AI ---
DIRECTIONS = [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)]
def is_valid_coordinate(r, c):
    return 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE

def get_flips(board, r_start, c_start, player_color):
    if not is_valid_coordinate(r_start, c_start) or board[r_start][c_start] != '':
        return []
    opponent_color = 'W' if player_color == 'B' else 'B'
    flips_found = []
    for dr, dc in DIRECTIONS:
        r, c = r_start + dr, c_start + dc
        potential_flips_in_direction = []
        while is_valid_coordinate(r, c):
            if board[r][c] == opponent_color:
                potential_flips_in_direction.append((r, c))
            elif board[r][c] == player_color:
                flips_found.extend(potential_flips_in_direction)
                break
            else: break
            r += dr
            c += dc
    return flips_found

def get_valid_moves(board, player_color):
    valid_moves = {}
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] == '':
                flips = get_flips(board, r, c, player_color)
                if flips:
                    valid_moves[(r, c)] = flips
    return valid_moves

def make_move(board, move_r, move_c, player_color, flips):
    if not is_valid_coordinate(move_r, move_c): return
    board[move_r][move_c] = player_color
    for r_flip, c_flip in flips:
        if is_valid_coordinate(r_flip, c_flip):
            board[r_flip][c_flip] = player_color

def evaluate_board(board, player_color):
    score = 0
    opponent_color = 'W' if player_color == 'B' else 'B'

    # Xác định ma trận trọng số vị trí dựa trên giai đoạn game
    # (num_pieces sẽ được tính sau, nhưng chúng ta cần nó để chọn ma trận)
    # Tạm thời đếm num_pieces ở đây để chọn ma trận, sau đó sẽ dùng lại giá trị này.
    temp_num_pieces = 0
    for r_idx_temp in range(BOARD_SIZE):
        for c_idx_temp in range(BOARD_SIZE):
            if board[r_idx_temp][c_idx_temp] != '':
                temp_num_pieces +=1

    current_weights = None
    if temp_num_pieces <= (BOARD_SIZE * BOARD_SIZE) * 0.33: # Đầu game (ví dụ <= 1/3 số ô)
        current_weights = STATIC_POSITIONAL_WEIGHTS_EARLY
    elif temp_num_pieces <= (BOARD_SIZE * BOARD_SIZE) * 0.66: # Giữa game (ví dụ <= 2/3 số ô)
        current_weights = STATIC_POSITIONAL_WEIGHTS_MID
    else: # Cuối game
        current_weights = STATIC_POSITIONAL_WEIGHTS_LATE

    # 1. Tính điểm vị trí với ma trận trọng số động
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] == player_color:
                score += current_weights[r][c]
            elif board[r][c] == opponent_color:
                score -= current_weights[r][c]

    # 2. Tính điểm Mobilité và Pass
    my_moves_list = get_valid_moves(board, player_color)
    opponent_moves_list = get_valid_moves(board, opponent_color)
    my_num_moves = len(my_moves_list)
    opponent_num_moves = len(opponent_moves_list)

    num_pieces = temp_num_pieces
    
    current_mobility_weight = MOBILITY_WEIGHT_INITIAL
    if num_pieces > BOARD_SIZE * BOARD_SIZE * 0.75: # Cuối game
        current_mobility_weight = MOBILITY_WEIGHT_LATEGAME
    elif num_pieces > BOARD_SIZE * BOARD_SIZE * 0.35: # Giữa game
        current_mobility_weight = MOBILITY_WEIGHT_MIDGAME
    
    mobility_score = (my_num_moves - opponent_num_moves) * current_mobility_weight
    score += mobility_score

    # Thưởng/Phạt cho việc Pass
    if my_num_moves == 0 and opponent_num_moves > 0: # AI bị pass và đối thủ còn nước đi
        score += PASS_PENALTY
    if opponent_num_moves == 0 and my_num_moves > 0: # Đối thủ bị pass và AI còn nước đi
        score += FORCE_PASS_BONUS
    # Trường hợp cả hai cùng hết nước (kết thúc game) thì không cộng trừ gì thêm ở đây

    # 3. Tính điểm ổn định cạnh (Edge Stability)
    my_stable_edges = _count_stable_edge_pieces_for_player(board, player_color)
    opponent_stable_edges = _count_stable_edge_pieces_for_player(board, opponent_color)
    
    stable_edge_score = (my_stable_edges - opponent_stable_edges) * STABLE_EDGE_PIECE_WEIGHT
    score += stable_edge_score

    # 4. Tính điểm Đếm Quân (Piece Parity/Count) theo giai đoạn
    my_pieces = 0
    opponent_pieces = 0
    for r_idx in range(BOARD_SIZE):
        for c_idx in range(BOARD_SIZE):
            if board[r_idx][c_idx] == player_color:
                my_pieces += 1
            elif board[r_idx][c_idx] == opponent_color:
                opponent_pieces += 1
    
    piece_count_score = 0
    # (Sử dụng lại biến num_pieces đã được gán từ temp_num_pieces)
    if num_pieces > BOARD_SIZE * BOARD_SIZE * 0.75: # Cuối game
        piece_count_score = (my_pieces - opponent_pieces) * PIECE_COUNT_WEIGHT_LATE
    elif num_pieces > 0: # Đầu và Giữa game (chỉ áp dụng khi đã có quân trên bàn)
        piece_count_score = (my_pieces - opponent_pieces) * PIECE_COUNT_WEIGHT_EARLY_MID
    score += piece_count_score

    # 5. Đánh giá tình huống bẫy (Trap Situation) dựa trên chất lượng nước đi bắt buộc
    # current_weights, my_moves_list, opponent_moves_list đã có sẵn
    
    # Đánh giá cho đối thủ
    if opponent_num_moves > 0:
        num_opponent_bad_forced_moves = 0
        for move_coord in opponent_moves_list.keys(): # opponent_moves_list là dict
            r_opp, c_opp = move_coord
            if current_weights[r_opp][c_opp] < BAD_MOVE_THRESHOLD:
                num_opponent_bad_forced_moves += 1
        opponent_bad_move_ratio = num_opponent_bad_forced_moves / opponent_num_moves
        score += opponent_bad_move_ratio * TRAP_SITUATION_WEIGHT

    # Đánh giá cho AI
    if my_num_moves > 0: # my_num_moves đã được tính trước đó
        num_my_bad_forced_moves = 0
        for move_coord in my_moves_list.keys(): # my_moves_list là dict
            r_my, c_my = move_coord
            if current_weights[r_my][c_my] < BAD_MOVE_THRESHOLD:
                num_my_bad_forced_moves += 1
        my_bad_move_ratio = num_my_bad_forced_moves / my_num_moves
        score -= my_bad_move_ratio * TRAP_SITUATION_WEIGHT

    return score

# --- Hàm phụ để đếm quân cờ ổn định trên cạnh ---
def _count_stable_edge_pieces_for_player(board_state, player_color):
    stable_pieces = set()
    N = BOARD_SIZE # BOARD_SIZE là hằng số toàn cục

    # Kiểm tra từ 4 góc
    # Góc trên-trái (0,0)
    if board_state[0][0] == player_color:
        # Quét ngang sang phải
        for c in range(N):
            if board_state[0][c] == player_color:
                stable_pieces.add((0, c))
            else:
                break
        # Quét dọc xuống dưới
        for r in range(N):
            if board_state[r][0] == player_color:
                stable_pieces.add((r, 0))
            else:
                break
    
    # Góc trên-phải (0, N-1)
    if board_state[0][N-1] == player_color:
        # Quét ngang sang trái
        for c in range(N-1, -1, -1):
            if board_state[0][c] == player_color:
                stable_pieces.add((0, c))
            else:
                break
        # Quét dọc xuống dưới
        for r in range(N):
            if board_state[r][N-1] == player_color:
                stable_pieces.add((r, N-1))
            else:
                break

    # Góc dưới-trái (N-1, 0)
    if board_state[N-1][0] == player_color:
        # Quét ngang sang phải
        for c in range(N):
            if board_state[N-1][c] == player_color:
                stable_pieces.add((N-1, c))
            else:
                break
        # Quét dọc lên trên
        for r in range(N-1, -1, -1):
            if board_state[r][0] == player_color:
                stable_pieces.add((r, 0))
            else:
                break

    # Góc dưới-phải (N-1, N-1)
    if board_state[N-1][N-1] == player_color:
        # Quét ngang sang trái
        for c in range(N-1, -1, -1):
            if board_state[N-1][c] == player_color:
                stable_pieces.add((N-1, c))
            else:
                break
        # Quét dọc lên trên
        for r in range(N-1, -1, -1):
            if board_state[r][N-1] == player_color:
                stable_pieces.add((r, N-1))
            else:
                break
                
    return len(stable_pieces)

def _minimax(board, depth, maximizing_player, player_color, alpha, beta):
    opponent_color = 'W' if player_color == 'B' else 'B'
    current_player_for_this_level = player_color if maximizing_player else opponent_color
    valid_moves = get_valid_moves(board, current_player_for_this_level)

    if depth == 0 or not valid_moves:
        return evaluate_board(board, player_color)

    if maximizing_player:
        max_eval = -math.inf
        # Sắp xếp nước đi theo ưu tiên (ví dụ: góc, cạnh) có thể thêm ở đây nếu muốn
        # sorted_moves = sorted(valid_moves.items(), key=lambda item: move_priority(item[0]), reverse=True)
        for move, flips in valid_moves.items(): # Hoặc sorted_moves
            temp_board = [row[:] for row in board]
            make_move(temp_board, move[0], move[1], current_player_for_this_level, flips)
            eval_score = _minimax(temp_board, depth - 1, False, player_color, alpha, beta)
            max_eval = max(max_eval, eval_score)
            alpha = max(alpha, eval_score)
            if beta <= alpha: break
        return max_eval
    else:
        min_eval = math.inf
        # sorted_moves = sorted(valid_moves.items(), key=lambda item: move_priority(item[0]), reverse=True)
        for move, flips in valid_moves.items(): # Hoặc sorted_moves
            temp_board = [row[:] for row in board]
            make_move(temp_board, move[0], move[1], current_player_for_this_level, flips)
            eval_score = _minimax(temp_board, depth - 1, True, player_color, alpha, beta)
            min_eval = min(min_eval, eval_score)
            beta = min(beta, eval_score)
            if beta <= alpha: break
        return min_eval

def _search_one_move(args):
    board_after_move, depth_remaining, original_player, initial_move, game_moves_up_to_this_point, ai_color_for_this_turn = args
    # original_player là màu của AI trong toàn bộ ván đấu (current_game_ai_color)
    # initial_move là nước đi (r,c) hoặc 'PASS' mà nhánh này đang đánh giá cho AI
    # game_moves_up_to_this_point là current_game_moves (list of (player, move_coord_or_pass)) trước khi AI thực hiện initial_move
    # ai_color_for_this_turn là màu AI đang đi cho lượt này (thường giống original_player)

    score_from_minimax = _minimax(board_after_move, depth_remaining, False, original_player, -math.inf, math.inf)
    
    # --- Opening Book Thống Kê Mới ---
    opening_book_bonus = 0
    # Tạo prefix key từ game_moves_up_to_this_point (chỉ lấy tọa độ/PASS)
    # game_moves_up_to_this_point là một list các tuple (player_color, move_coord_or_PASS)
    # Ví dụ: [('B', (3,3)), ('W', (3,4)), ...]
    prefix_for_lookup = []
    for move_entry in game_moves_up_to_this_point:
        if isinstance(move_entry, (list, tuple)) and len(move_entry) == 2:
            actual_m = move_entry[1]
            if isinstance(actual_m, (list, tuple)) and len(actual_m) == 2 and \
               isinstance(actual_m[0], int) and isinstance(actual_m[1], int):
                prefix_for_lookup.append(tuple(actual_m))
            elif actual_m == 'PASS':
                prefix_for_lookup.append('PASS')
            # Bỏ qua các nước đi không hợp lệ trong prefix nếu có, nhưng điều này ít khi xảy ra với current_game_moves
    prefix_tuple = tuple(prefix_for_lookup)

    if prefix_tuple in opening_stats:
        stats_for_this_prefix = opening_stats[prefix_tuple]
        # initial_move là nước đi (r,c) hoặc 'PASS' đang được đánh giá
        move_stats = stats_for_this_prefix.get(initial_move)
        if move_stats:
            wins, losses = move_stats[0], move_stats[1]
            if wins + losses > 0:
                # Công thức: λ * (win−loss)/(win+loss)
                opening_book_bonus = OPENING_BOOK_STATISTICAL_WEIGHT_FACTOR * (wins - losses) / (wins + losses + 1e-6) # +1e-6 để tránh chia cho 0
                # log_message(f"[OB_STAT] Prefix: {prefix_tuple}, Move: {initial_move}, Wins: {wins}, Losses: {losses}, Bonus: {opening_book_bonus:.2f}", level=logging.DEBUG)
            # else: # Không có win/loss nào được ghi nhận cho nước này từ prefix này
                # log_message(f"[OB_STAT] Prefix: {prefix_tuple}, Move: {initial_move}, No win/loss data.", level=logging.DEBUG)
    # else: # Prefix này chưa có trong opening_stats
        # log_message(f"[OB_STAT] Prefix: {prefix_tuple} not in opening_stats.", level=logging.DEBUG)

    # --- Bỏ Opening Book cũ ---
    # opening_book_adjustment = 0
    # if len(game_moves_up_to_this_point) < OPENING_BOOK_DEPTH: 
    #     current_tested_move_tuple = (ai_color_for_this_turn, initial_move) 
    #     hypothetical_sequence = game_moves_up_to_this_point + [current_tested_move_tuple]
    #     
    #     for record in loaded_game_experiences:
    #         if record.get("ai_color") == ai_color_for_this_turn and \
    #            len(record.get("moves", [])) >= len(hypothetical_sequence) and \
    #            record.get("moves", [])[:len(hypothetical_sequence)] == hypothetical_sequence:
    #             
    #             if record.get("result_for_ai") == "WIN":
    #                 opening_book_adjustment += OPENING_BOOK_WIN_BONUS
    #                 break 
    #             elif record.get("result_for_ai") == "LOSS":
    #                 opening_book_adjustment -= OPENING_BOOK_LOSS_PENALTY
    #                 break 
    
    final_score = score_from_minimax + opening_book_bonus # Sử dụng bonus mới
    return final_score, initial_move

def find_best_move(board_state, player_color, depth=6): # player_color ở đây là current_game_ai_color
    valid_moves = get_valid_moves(board_state, player_color)
    if not valid_moves:
        log_message(f"[AI {player_color}] Không có nước đi hợp lệ.", level=logging.INFO)
        return None, 0.0

    best_move_found = None
    best_score_found = -math.inf
    turn_start_time = time.monotonic()
    TIME_LIMIT_SECONDS = 13.0 # Giới hạn thời gian tìm kiếm
    fallback_move = list(valid_moves.keys())[0]

    tasks_for_pool = []
    for move, flips in valid_moves.items():
        temp_board = [row[:] for row in board_state]
        make_move(temp_board, move[0], move[1], player_color, flips)
        # Truyền current_game_moves (toàn cục, chứa lịch sử đến TRƯỚC lượt AI này)
        # và player_color (màu AI đang đi cho lượt này)
        tasks_for_pool.append({'args': (temp_board, depth - 1, player_color, move, list(current_game_moves), player_color), 'original_move': move})

    if not _pool:
        log_message(f"[AI {player_color}] Lỗi: _pool chưa được khởi tạo. Chạy đơn luồng.", level=logging.ERROR)
        # Fallback đơn luồng nếu pool lỗi
        for task_info in tasks_for_pool:
            score, move_from_worker = _search_one_move(task_info['args'])
            if score > best_score_found:
                best_score_found = score
                best_move_found = move_from_worker
        if not best_move_found: best_move_found = fallback_move
        log_message(f"[AI {player_color}] Đơn luồng: {best_move_found} ({best_score_found:.0f})")
        return best_move_found, best_score_found
        
    async_results_map = {}
    num_tasks = len(tasks_for_pool)
    log_message(f"[AI {player_color}] Bắt đầu tìm nước đi (Pool, depth={depth}, tasks={num_tasks}, limit={TIME_LIMIT_SECONDS}s)")

    for task_info in tasks_for_pool:
        async_res = _pool.apply_async(_search_one_move, args=(task_info['args'],))
        async_results_map[async_res] = task_info['original_move']

    processed_tasks = 0
    results_from_workers = []
    active_async_results = list(async_results_map.keys())

    for async_res in active_async_results:
        if not async_res in async_results_map: continue
        elapsed_time = time.monotonic() - turn_start_time
        if elapsed_time >= TIME_LIMIT_SECONDS:
            log_message(f"[AI {player_color}] Timeout tổng ({elapsed_time:.2f}s). Đã xử lý {processed_tasks}/{num_tasks}.", level=logging.WARNING)
            break
        remaining_time_for_task = max(0.01, TIME_LIMIT_SECONDS - elapsed_time)
        original_move_for_this_task = async_results_map[async_res]
        try:
            score, move_from_worker = async_res.get(timeout=remaining_time_for_task)
            processed_tasks += 1
            results_from_workers.append({'score': score, 'move': move_from_worker})
            # log_message(f"[AI {player_color}] KQ cho {move_from_worker} (score: {score:.0f}). ({processed_tasks}/{num_tasks}).", level=logging.DEBUG)
            if score > best_score_found:
                best_score_found = score
                best_move_found = move_from_worker
            del async_results_map[async_res]
        except mp.TimeoutError:
            log_message(f"[AI {player_color}] Timeout luồng con cho {original_move_for_this_task}.", level=logging.WARNING)
        except Exception as e:
            log_message(f"[AI {player_color}] Lỗi luồng con cho {original_move_for_this_task}: {e}.", level=logging.ERROR)
            if async_res in async_results_map: del async_results_map[async_res]

    final_search_time = time.monotonic() - turn_start_time
    if best_move_found is None:
        if results_from_workers:
            results_from_workers.sort(key=lambda x: x['score'], reverse=True)
            best_move_found = results_from_workers[0]['move']
            best_score_found = results_from_workers[0]['score']
            log_message(f"[AI {player_color}] Timeout, chọn top KQ: {best_move_found} ({best_score_found:.0f}). Time: {final_search_time:.2f}s.", level=logging.INFO)
        else:
            best_move_found = fallback_move
            log_message(f"[AI {player_color}] Không có KQ từ workers. Fallback: {best_move_found}. Time: {final_search_time:.2f}s.", level=logging.WARNING)
    else:
        log_message(f"[AI {player_color}] Hoàn tất. Best: {best_move_found} (score: {best_score_found:.0f}). Time: {final_search_time:.2f}s.")

    if best_move_found:
        move_str_log = f"{chr(ord('A') + best_move_found[1])}{best_move_found[0] + 1}"
        log_message(f"[AI {player_color}] Chọn nước: {move_str_log} ({best_move_found}) với điểm: {best_score_found:.0f}")
    else:
        return fallback_move, -math.inf
    return best_move_found, best_score_found

# --- Vòng lặp Auto ---
def auto_play_loop():
    global is_running, current_scenario, current_game_ai_color, \
           ai_color_locked_this_game, ai_moved, \
           win_count, loss_count, draw_count, current_game_moves, \
           waiting_room_enter_time, selected_target_name, \
           last_known_board_state_for_opponent_move, stop_after_current_game
    global general_win_draw_loss_var, general_win_draw_loss_label, root
    # Các biến UI khác như *_label, *_var được cập nhật thông qua các hàm con như initialize_new_game_state hoặc trực tiếp nếu cần.
    # game_progress_bar và các biến liên quan cũng được quản lý bởi initialize_new_game_state.

    log_message("Bắt đầu vòng lặp tự động với cấu trúc 3 kịch bản...")
    ai_moved = False    # ← reset mỗi lần vòng lặp tự động (auto_play_loop) được gọi/bắt đầu
    loop_delay = 0.01 # Giảm loop_delay

    while is_running:
        specific_sleep_needed = 0 # Khởi tạo ở đầu mỗi vòng lặp

        # 1) Chụp màn hình
        screenshot = adb_screencap()
        if screenshot is None:
            log_message("Không chụp được màn hình, thử lại sau 0.5s...", level=logging.WARNING)
            specific_sleep_needed = 0.5
            # Xử lý sleep ở cuối vòng lặp
        else:
            cv_img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

            # Xử lý lỗi mạng ưu tiên
            if check_pixel_color(cv_img, NETWORK_ERROR_PIXEL_X, NETWORK_ERROR_PIXEL_Y, NETWORK_ERROR_PIXEL_COLOR, NETWORK_ERROR_PIXEL_TOLERANCE):
                log_message("Phát hiện lỗi mạng. Click để xử lý...", level=logging.WARNING)
                click_at(NETWORK_ERROR_CLICK_X, NETWORK_ERROR_CLICK_Y)
                current_scenario = None # Reset scenario để dò lại từ đầu
                specific_sleep_needed = 1.0 # Chờ xử lý lỗi mạng
                # Không continue, để sleep ở cuối
            else:
                # 2) Xác định kịch bản chính
                main_scenario_determined = None
                if check_pixel_color(cv_img, ENDGAME_PIXEL_X, ENDGAME_PIXEL_Y, ENDGAME_PIXEL_COLOR, ENDGAME_PIXEL_TOLERANCE):
                    main_scenario_determined = 'GAME_OVER'
                elif (check_pixel_color(cv_img, TURN_PIXEL_X, TURN_PIXEL_Y, TURN_PIXEL_COLOR, TURN_PIXEL_TOLERANCE) or
                      check_pixel_color(cv_img, OPPONENT_TURN_PIXEL_X, OPPONENT_TURN_PIXEL_Y, OPPONENT_TURN_PIXEL_COLOR, OPPONENT_TURN_PIXEL_TOLERANCE) or
                      (current_scenario == 'POST_MENU_CLICK_CHECK' and main_scenario_determined != 'LOBBY') or 
                      current_scenario == 'IN_GAME'): 
                    main_scenario_determined = 'IN_GAME'
                else:
                    main_scenario_determined = 'LOBBY'
                
                # CẬP NHẬT SỐ QUÂN TOÀN CỤC NẾU ĐANG TRONG GAME (TẠM THỜI VÔ HIỆU HÓA)
                # if main_scenario_determined == 'IN_GAME':
                #     temp_board_state, temp_b_count, temp_w_count = get_board_state_cv(cv_img)
                #     if temp_board_state: # Kiểm tra get_board_state_cv thành công
                #         global last_known_black_count_global, last_known_white_count_global
                #         last_known_black_count_global = temp_b_count
                #         last_known_white_count_global = temp_w_count
                #         log_message(f"AUTO_LOOP: Cập nhật số quân toàn cục: Đen {temp_b_count}, Trắng {temp_w_count}", level=logging.DEBUG)
                
                # 3) Xử lý theo 3 kịch bản chính
                if main_scenario_determined == 'LOBBY':
                    target_info = TARGET_OPTIONS.get(selected_target_name)
                    if target_info and check_pixel_color(cv_img, target_info["X"], target_info["Y"], target_info["RGB"], target_info["TOLERANCE"]):
                        if current_scenario != 'MENU_CLICKED_RECENTLY':
                            log_message(f"LOBBY (MENU): Phát hiện pixel mục tiêu '{selected_target_name}'. Click cho phép.")
                            click_at(target_info["X"], target_info["Y"])
                            current_scenario = 'POST_MENU_CLICK_CHECK'
                            waiting_room_enter_time = None
                            specific_sleep_needed = 1.0
                    elif current_scenario == 'POST_MENU_CLICK_CHECK':
                        log_message("LOBBY (POST_MENU_CLICK_CHECK): Kiểm tra trạng thái sau click menu...")
                        if check_pixel_color(cv_img, TURN_PIXEL_X, TURN_PIXEL_Y, TURN_PIXEL_COLOR, TURN_PIXEL_TOLERANCE) or \
                           check_pixel_color(cv_img, OPPONENT_TURN_PIXEL_X, OPPONENT_TURN_PIXEL_Y, OPPONENT_TURN_PIXEL_COLOR, OPPONENT_TURN_PIXEL_TOLERANCE):
                            log_message("LOBBY (POST_MENU_CLICK_CHECK): Vào trận. Chuyển sang IN_GAME và khởi tạo.")
                            current_scenario = 'IN_GAME' 
                        elif check_and_log_waiting_room_pixel(cv_img):
                            log_message("LOBBY (POST_MENU_CLICK_CHECK): Vào phòng chờ.")
                            waiting_room_enter_time = time.monotonic()
                            current_scenario = 'IN_WAITING_ROOM'
                        else:
                            log_message("LOBBY (POST_MENU_CLICK_CHECK): Chưa vào trận hoặc phòng chờ. Tiếp tục chờ...", level=logging.DEBUG)
                            specific_sleep_needed = 0.5
                    elif check_and_log_waiting_room_pixel(cv_img) or current_scenario == 'IN_WAITING_ROOM':
                        if current_scenario != 'IN_WAITING_ROOM': 
                             log_message("LOBBY: Phát hiện vào phòng chờ bằng pixel.")
                             waiting_room_enter_time = time.monotonic()
                             current_scenario = 'IN_WAITING_ROOM'
                        if waiting_room_enter_time is None: 
                            waiting_room_enter_time = time.monotonic()
                            log_message("LOBBY (IN_WAITING_ROOM): waiting_room_enter_time is None, đặt lại.", level=logging.WARNING)
                        elapsed_wait_time = time.monotonic() - waiting_room_enter_time
                        if elapsed_wait_time > WAITING_ROOM_TIMEOUT_SECONDS:
                            log_message(f"LOBBY (IN_WAITING_ROOM): Hết {WAITING_ROOM_TIMEOUT_SECONDS}s chờ. Click Trở về.")
                            click_at(WAITING_ROOM_BACK_CLICK_X, WAITING_ROOM_BACK_CLICK_Y)
                            current_scenario = None 
                            waiting_room_enter_time = None
                            specific_sleep_needed = 1.5 
                        elif check_pixel_color(cv_img, TURN_PIXEL_X, TURN_PIXEL_Y, TURN_PIXEL_COLOR, TURN_PIXEL_TOLERANCE) or \
                             check_pixel_color(cv_img, OPPONENT_TURN_PIXEL_X, OPPONENT_TURN_PIXEL_Y, OPPONENT_TURN_PIXEL_COLOR, OPPONENT_TURN_PIXEL_TOLERANCE):
                            log_message("LOBBY (IN_WAITING_ROOM): Thoát phòng chờ, vào trận. Chuyển sang IN_GAME.")
                            current_scenario = 'IN_GAME' 
                            waiting_room_enter_time = None
                        else:
                            remaining_time = WAITING_ROOM_TIMEOUT_SECONDS - elapsed_wait_time
                            log_message(f"LOBBY (IN_WAITING_ROOM): Đang chờ, còn {remaining_time:.1f} giây...", level=logging.DEBUG)
                            specific_sleep_needed = 0.5 
                    else:
                        if current_scenario not in [None, 'POST_MENU_CLICK_CHECK', 'IN_WAITING_ROOM', 'MENU_CLICKED_RECENTLY']:
                            log_message(f"LOBBY: Trạng thái không xác định '{current_scenario}', reset về chờ MENU.", level=logging.DEBUG)
                        current_scenario = None 
                        log_message("LOBBY: Chờ phát hiện trạng thái (MENU, Phòng chờ)...", level=logging.DEBUG)

                elif main_scenario_determined == 'IN_GAME':
                    if current_scenario != 'IN_GAME_INITIALIZED_AND_RUNNING':
                        log_message("IN_GAME: Bắt đầu/Tiếp tục ván đấu. Khởi tạo nếu cần...")
                        initialize_new_game_state(cv_img)
                        current_scenario = 'IN_GAME_INITIALIZED_AND_RUNNING'

                    # --- Phát hiện đối thủ hết nước đi, ép AI đi tiếp ---
                    # Lấy trạng thái bàn cờ và danh sách nước đi của 2 bên
                    board_state_now, b_now, w_now = get_board_state_cv(cv_img) # Đọc board state ở đầu mỗi vòng IN_GAME
                    opponent_color = 'W' if current_game_ai_color == 'B' else 'B' # Sẽ cần màu AI để xác định màu đối thủ
                    # Nếu đối thủ đã hết nước đi nhưng AI vẫn còn (chỉ check khi màu AI đã xác định)
                    if current_game_ai_color and not get_valid_moves(board_state_now, opponent_color) and get_valid_moves(board_state_now, current_game_ai_color):
                        log_message("Đối thủ không còn nước đi – tự động trả lượt cho AI.", level=logging.INFO)
                        ai_moved = False  # cho phép AI đánh tiếp
                        # Không cần sleep đặc biệt ở đây, vòng lặp sẽ kiểm tra lại ngay

                    # --- Phát hiện khi đối thủ vừa đánh xong (pixel Opponent turn) ---
                    # Chỉ kiểm tra khi AI đã đi và đang chờ đối thủ
                    if ai_moved and check_pixel_color(cv_img,
                                                    OPPONENT_TURN_PIXEL_X,
                                                    OPPONENT_TURN_PIXEL_Y,
                                                    OPPONENT_TURN_PIXEL_COLOR,
                                                    OPPONENT_TURN_PIXEL_TOLERANCE):
                        log_message("IN_GAME: Phát hiện pixel lượt đối thủ.")
                        # board_state_now đã được đọc ở trên
                        opp_color_detect = 'W' if current_game_ai_color == 'B' else ('B' if current_game_ai_color == 'W' else None) # Màu đối thủ để detect
                        
                        if last_known_board_state_for_opponent_move and opp_color_detect:
                            opponent_move_found = None
                            # Tìm ô khác biệt (ô trống hoặc quân mình thành quân đối thủ)
                            for r_find in range(BOARD_SIZE):
                                for c_find in range(BOARD_SIZE):
                                    if board_state_now[r_find][c_find] == opp_color_detect and \
                                       (last_known_board_state_for_opponent_move[r_find][c_find] == '' or \
                                        (current_game_ai_color and last_known_board_state_for_opponent_move[r_find][c_find] == current_game_ai_color)):
                                        opponent_move_found = (r_find, c_find)
                                        break # Found one change is enough for simple detection
                                if opponent_move_found: break

                            if opponent_move_found:
                                move_s_opp = f"{chr(ord('A') + opponent_move_found[1])}{opponent_move_found[0] + 1}"
                                log_message(f"IN_GAME: Nước đối thủ ({opp_color_detect}) vừa đi: {move_s_opp}")
                                current_game_moves.append((opp_color_detect, opponent_move_found))
                                # cập nhật GUI thông tin đối thủ
                                if opponent_info_last_move_label and opponent_info_last_move_label.winfo_exists() and root and root.winfo_exists():
                                    root.after(0, lambda m=move_s_opp: opponent_info_last_move_var.set(f"Nước cuối: {m}"))
                                # reset ai_moved để cho phép AI đi lượt kế tiếp
                                ai_moved = False
                            else:
                                log_message("IN_GAME: Phát hiện pixel lượt đối thủ nhưng không tìm thấy nước đi khác biệt trên bàn cờ.", level=logging.DEBUG)

                        # Cập nhật last_known_board_state sau khi đối thủ đi xong (hoặc pixel xuất hiện)
                        last_known_board_state_for_opponent_move = [row[:] for row in board_state_now]
                        log_message("IN_GAME: Đã cập nhật last_known_board_state sau khi phát hiện pixel lượt đối thủ.", level=logging.DEBUG)
                        specific_sleep_needed = 0.1 # Chờ ngắn để AI turn pixel có thể xuất hiện

                    # --- Xử lý lượt AI (khi pixel AI turn) ---
                    elif check_pixel_color(cv_img, TURN_PIXEL_X, TURN_PIXEL_Y, TURN_PIXEL_COLOR, TURN_PIXEL_TOLERANCE):
                        # print("DEBUG MARKER checkpoint_AI_turn_block_entry") # DEBUG - REMOVE
                        if not ai_moved: # Chỉ xử lý nếu AI chưa đi trong lượt được phát hiện này
                            log_message("IN_GAME: Đến lượt AI. Chụp màn hình mới...")
                            
                            screenshot_for_ai_turn = adb_screencap() # Chụp ảnh mới cho lượt AI
                            if screenshot_for_ai_turn is None:
                                log_message("IN_GAME (Lượt AI): Không chụp được màn hình mới. Bỏ qua lượt này.", level=logging.WARNING)
                                specific_sleep_needed = 0.5 
                            else:
                                cv_img_for_ai_turn = cv2.cvtColor(np.array(screenshot_for_ai_turn), cv2.COLOR_RGB2BGR)
                                board_state_now, b_now, w_now = get_board_state_cv(cv_img_for_ai_turn) # Sử dụng ảnh mới
                                
                                # --- CẬP NHẬT TIẾN ĐỘ VÁN ---
                                total_pieces = b_now + w_now
                                percent = int(total_pieces / (BOARD_SIZE * BOARD_SIZE) * 100)
                                if root and root.winfo_exists() and game_progress_bar and game_progress_bar.winfo_exists():
                                    root.after(0, lambda p=percent: game_progress_bar.config(value=p) if game_progress_bar.winfo_exists() else None)
                                if root and root.winfo_exists() and game_progress_text_var and game_progress_text_label and game_progress_text_label.winfo_exists():
                                    root.after(0, lambda p=percent: game_progress_text_var.set(f"{p}%") if game_progress_text_label.winfo_exists() else None)

                                # --- Phát hiện nước đi của đối thủ nếu bị bỏ lỡ (từ ảnh mới) ---
                                opponent_color_for_move_detect = 'W' if current_game_ai_color == 'B' else ('B' if current_game_ai_color == 'W' else None)
                                if last_known_board_state_for_opponent_move and opponent_color_for_move_detect:
                                    opponent_move_found = None
                                    for r_find in range(BOARD_SIZE):
                                        for c_find in range(BOARD_SIZE):
                                            if board_state_now[r_find][c_find] == opponent_color_for_move_detect and \
                                               last_known_board_state_for_opponent_move[r_find][c_find] != opponent_color_for_move_detect and \
                                               (last_known_board_state_for_opponent_move[r_find][c_find] == '' or \
                                                last_known_board_state_for_opponent_move[r_find][c_find] == current_game_ai_color): 
                                                opponent_move_found = (r_find, c_find)
                                                break
                                        if opponent_move_found: break
                                    if opponent_move_found:
                                        move_s_opp_log = f"{chr(ord('A') + opponent_move_found[1])}{opponent_move_found[0] + 1}"
                                        log_message(f"Nước đối thủ ({opponent_color_for_move_detect}) vừa đi (phát hiện ở lượt AI từ ảnh mới): {move_s_opp_log}")
                                        current_game_moves.append((opponent_color_for_move_detect, opponent_move_found))
                                        if opponent_info_last_move_label and opponent_info_last_move_label.winfo_exists() and root and root.winfo_exists():
                                           root.after(0, lambda m=move_s_opp_log: opponent_info_last_move_var.set(f"Nước cuối: {m}"))
                                
                                # --- Xác định màu AI nếu chưa lock (từ ảnh mới) ---
                                if not ai_color_locked_this_game or not current_game_ai_color:
                                    log_message("IN_GAME (Lượt AI): Màu AI chưa lock/xác định, thử phát hiện từ ảnh mới...")
                                    detected_color = detect_ai_color_cv(cv_img_for_ai_turn) # Sử dụng ảnh mới
                                    if detected_color:
                                        current_game_ai_color = detected_color
                                        ai_color_locked_this_game = True
                                        log_message(f"===> AI là quân: {current_game_ai_color}")
                                        if ai_info_color_label and ai_info_color_label.winfo_exists() and root and root.winfo_exists():
                                             root.after(0, lambda c=current_game_ai_color: ai_info_color_var.set(f"AI: {c}"))
                                        opp_color_display = 'W' if current_game_ai_color == 'B' else 'B'
                                        if opponent_info_color_label and opponent_info_color_label.winfo_exists() and root and root.winfo_exists():
                                            root.after(0, lambda c=opp_color_display: opponent_info_color_var.set(f"Đối thủ: {c}"))
                                    else:
                                        log_message("IN_GAME (Lượt AI): Không nhận diện được màu AI từ ảnh mới. Chờ...", level=logging.WARNING)
                                        specific_sleep_needed = 0.5
                                
                                # --- AI thực hiện nước đi --- 
                                if current_game_ai_color: # Chỉ đi nếu có màu
                                    my_pieces_count = b_now if current_game_ai_color == 'B' else w_now
                                    opponent_pieces_count = w_now if current_game_ai_color == 'B' else b_now
                                    if ai_info_pieces_label and ai_info_pieces_label.winfo_exists() and root and root.winfo_exists():
                                        root.after(0, lambda pc=my_pieces_count: ai_info_pieces_var.set(f"Quân: {pc}"))
                                    if opponent_info_pieces_label and opponent_info_pieces_label.winfo_exists() and root and root.winfo_exists():
                                        root.after(0, lambda pc=opponent_pieces_count: opponent_info_pieces_var.set(f"Quân: {pc}"))
                                    
                                    t0_ai_find = time.perf_counter()
                                    best_move, score = find_best_move(board_state_now, current_game_ai_color, depth=6) # board_state_now là từ ảnh mới
                                    t_ms_ai_find = (time.perf_counter() - t0_ai_find) * 1000
                                    win_p = compute_win_probability(score) 
                                    move_s_ai_display = f"{chr(ord('A') + best_move[1])}{best_move[0] + 1}" if best_move else "PASS"
                                    if ai_info_last_move_label and ai_info_last_move_label.winfo_exists() and root and root.winfo_exists():
                                        root.after(0, lambda m=move_s_ai_display: ai_info_last_move_var.set(f"Nước cuối: {m}"))
                                    if ai_info_win_pct_label and ai_info_win_pct_label.winfo_exists() and root and root.winfo_exists():
                                        root.after(0, lambda wp=win_p, t=t_ms_ai_find: ai_info_win_pct_var.set(f"Win%: {wp}% ({t:.0f}ms)"))
                                    
                                    if best_move:
                                        if not cell_centers or best_move[0] >= len(cell_centers) or best_move[1] >= len(cell_centers[best_move[0]]):
                                             log_message(f"Lỗi: Tọa độ AI click {best_move} không hợp lệ từ cell_centers.", level=logging.ERROR)
                                             ai_moved = False # Lỗi, không đi, thử lại ở vòng lặp sau nếu còn lượt
                                        else:
                                            r_ai_click, c_ai_click = best_move
                                            success_click = click_and_verify(r_ai_click, c_ai_click, current_game_ai_color, retries=2, delay=0.25)
                                            if success_click:
                                                log_message(f"AI ({current_game_ai_color}) đi: {move_s_ai_display} (Xác nhận thành công)")
                                                current_game_moves.append((current_game_ai_color, best_move))
                                                ai_moved = True # AI đã đi thành công
                                                specific_sleep_needed = 0.05 
                                            else:
                                                log_message(f"⚠️ AI ({current_game_ai_color}) click hụt tại {move_s_ai_display} sau nhiều lần thử. Sẽ thử lại ở vòng lặp sau.", level=logging.WARNING)
                                                ai_moved = False # Click hụt, đánh dấu chưa đi để thử lại
                                    else: # AI PASS
                                        log_message(f"AI ({current_game_ai_color}) PASS.")
                                        current_game_moves.append((current_game_ai_color, 'PASS'))
                                        ai_moved = True # PASS cũng là đã đi
                                        specific_sleep_needed = 0.05
                                    # Không còn dòng `ai_moved = True` vô điều kiện ở đây nữa
                                else: # current_game_ai_color không xác định được
                                    log_message("IN_GAME (Lượt AI): Không có màu AI để thực hiện nước đi. Chờ...", level=logging.WARNING)
                                    specific_sleep_needed = 0.5 # ai_moved vẫn là False
                        else: # ai_moved is True
                            # print("DEBUG MARKER checkpoint_AI_already_moved") # DEBUG - REMOVE
                            log_message("IN_GAME (Lượt AI): AI đã hoàn thành lượt đi, chờ pixel thay đổi.", level=logging.DEBUG)
                            specific_sleep_needed = 0.1
                    # KHỐI ELIF LẶP BỊ XÓA (Nội dung từ dòng ~1284 đến ~1362 trong file gốc)
                    elif check_pixel_color(cv_img, ENDGAME_PIXEL_X, ENDGAME_PIXEL_Y, ENDGAME_PIXEL_COLOR, ENDGAME_PIXEL_TOLERANCE):
                        log_message("IN_GAME: Phát hiện ENDGAME pixel. Sẽ chuyển sang GAME_OVER ở vòng lặp sau.")
                    else:
                        log_message("IN_GAME: Chờ lượt tiếp theo (không phải AI theo pixel).", level=logging.DEBUG)
                        specific_sleep_needed = 0.1

                elif main_scenario_determined == 'GAME_OVER':
                    log_message("GAME_OVER: Trò chơi kết thúc.")
                    ai_moved = False # Reset cờ cho ván tiếp theo

                    ai_final_pieces = 0
                    opponent_final_pieces = 0
                    b_final_for_log = 0 # For logging "Đen X - Trắng Y" if possible
                    w_final_for_log = 0 # For logging "Đen X - Trắng Y" if possible

                    try:
                        if ai_info_pieces_var and opponent_info_pieces_var and \
                           ai_info_pieces_var.get() and opponent_info_pieces_var.get(): # Check if vars exist and have values
                            ai_pieces_str = ai_info_pieces_var.get().split(':')[-1].strip()
                            opponent_pieces_str = opponent_info_pieces_var.get().split(':')[-1].strip()
                            ai_final_pieces = int(ai_pieces_str)
                            opponent_final_pieces = int(opponent_pieces_str)
                            log_message(f"GAME_OVER: Đã lấy số quân từ GUI: AI={ai_final_pieces}, Đối thủ={opponent_final_pieces}", level=logging.INFO)

                            # Determine b_final_for_log and w_final_for_log for accurate logging
                            if current_game_ai_color == 'B':
                                b_final_for_log = ai_final_pieces
                                w_final_for_log = opponent_final_pieces
                            elif current_game_ai_color == 'W':
                                w_final_for_log = ai_final_pieces
                                b_final_for_log = opponent_final_pieces
                            # If current_game_ai_color is None, b_final_for_log/w_final_for_log remain 0, direct AI/Opponent counts will be logged.
                        else:
                            log_message("GAME_OVER: Không thể lấy số quân từ biến GUI (ai_info_pieces_var hoặc opponent_info_pieces_var trống hoặc không tồn tại).", level=logging.WARNING)
                    except ValueError:
                        log_message("GAME_OVER: Lỗi khi chuyển đổi số quân từ GUI vars thành số nguyên.", level=logging.ERROR)
                    except Exception as e_parse_gui_score:
                        log_message(f"GAME_OVER: Lỗi không xác định khi lấy số quân từ GUI: {e_parse_gui_score}", level=logging.ERROR)

                    game_result_for_ai = "UNKNOWN_RESULT"

                    is_win_pixel_detected = check_pixel_color(cv_img, WIN_PIXEL_X, WIN_PIXEL_Y, WIN_PIXEL_COLOR, WIN_PIXEL_TOLERANCE)
                    is_loss_pixel_detected = check_pixel_color(cv_img, LOSS_PIXEL_X, LOSS_PIXEL_Y, LOSS_PIXEL_COLOR, LOSS_PIXEL_TOLERANCE)

                    if is_win_pixel_detected:
                        game_result_for_ai = 'WIN'
                        win_count += 1
                        log_message(f"===> Kết quả (TỪ PIXEL): Thắng (AI: {current_game_ai_color or 'Không rõ màu'}) <===")
                    elif is_loss_pixel_detected:
                        game_result_for_ai = 'LOSS'
                        loss_count += 1
                        log_message(f"===> Kết quả (TỪ PIXEL): Thua (AI: {current_game_ai_color or 'Không rõ màu'}) <===")
                        if is_running:
                            log_message("Thua trận (pixel). Đợi 5 giây...")
                            wait_start_time = time.monotonic()
                            seconds_to_wait_after_loss = 5
                            while time.monotonic() - wait_start_time < seconds_to_wait_after_loss:
                                if not is_running:
                                    log_message("Đã dừng auto trong khi chờ sau khi thua (pixel).")
                                    break
                                time.sleep(0.2)
                            if is_running:
                                log_message(f"Đã hết {seconds_to_wait_after_loss} giây chờ sau khi thua (pixel).")
                    else:
                        log_message("GAME_OVER: Không phát hiện pixel Thắng/Thua. Dựa vào so sánh số quân từ GUI (nếu có).")
                        if current_game_ai_color and (ai_info_pieces_var and ai_info_pieces_var.get()): # Check if AI color is known and GUI var was present
                            if ai_final_pieces > opponent_final_pieces:
                                game_result_for_ai = 'WIN'
                                win_count += 1
                                log_message(f"===> Kết quả (TỪ SO SÁNH QUÂN): Thắng (AI: {current_game_ai_color}) <===")
                            elif ai_final_pieces < opponent_final_pieces:
                                game_result_for_ai = 'LOSS'
                                loss_count += 1
                                log_message(f"===> Kết quả (TỪ SO SÁNH QUÂN): Thua (AI: {current_game_ai_color}) <===")
                                if is_running:
                                    log_message("Thua trận (so sánh quân). Đợi 5 giây...")
                                    wait_start_time = time.monotonic()
                                    seconds_to_wait_after_loss = 5
                                    while time.monotonic() - wait_start_time < seconds_to_wait_after_loss:
                                        if not is_running:
                                            log_message("Đã dừng auto trong khi chờ sau khi thua (so sánh quân).")
                                            break
                                        time.sleep(0.2)
                                    if is_running:
                                        log_message(f"Đã hết {seconds_to_wait_after_loss} giây chờ sau khi thua (so sánh quân).")
                            else: # ai_final_pieces == opponent_final_pieces
                                game_result_for_ai = 'DRAW'
                                draw_count += 1
                                log_message(f"===> Kết quả (TỪ SO SÁNH QUÂN): Hòa (AI: {current_game_ai_color}) <===")
                        else:
                            log_message(f"GAME_OVER: Không thể xác định kết quả từ so sánh quân (Màu AI: {current_game_ai_color}, " +
                                        f"Điểm AI GUI: '{ai_info_pieces_var.get() if ai_info_pieces_var else 'N/A'}').", level=logging.WARNING)
                            if ai_info_pieces_var and ai_info_pieces_var.get(): 
                                log_message(f"GAME_OVER: Điểm (từ GUI, màu AI không rõ): AI={ai_final_pieces}, Đối thủ={opponent_final_pieces}.")

                    if current_game_ai_color and (ai_info_pieces_var and ai_info_pieces_var.get()): 
                        log_message(f"GAME_OVER: Điểm cuối cùng (Đen: {b_final_for_log}, Trắng: {w_final_for_log}) - AI ({current_game_ai_color}): {ai_final_pieces}, Đối Thủ: {opponent_final_pieces}")
                    elif ai_info_pieces_var and ai_info_pieces_var.get(): 
                        log_message(f"GAME_OVER: Điểm cuối cùng (Màu AI không rõ) - AI: {ai_final_pieces}, Đối Thủ: {opponent_final_pieces}")
                    else: 
                         log_message(f"GAME_OVER: Không lấy được điểm từ GUI để báo cáo chi tiết. Kết quả dựa trên pixel hoặc không xác định.")

                    if general_win_draw_loss_label and general_win_draw_loss_label.winfo_exists() and root and root.winfo_exists():
                        root.after(0, lambda w=win_count, l=loss_count, d=draw_count: general_win_draw_loss_var.set(f"Thắng: {w}  Thua: {l}  Hòa: {d}"))
                    
                    if game_result_for_ai in ("WIN", "LOSS", "DRAW") and current_game_ai_color: 
                        save_game_experience(current_game_ai_color, game_result_for_ai, current_game_moves)
                    else:
                        log_message(f"GAME_OVER: Kết quả ('{game_result_for_ai}') hoặc màu AI ('{current_game_ai_color}') không hợp lệ để lưu kinh nghiệm chuẩn.", level=logging.WARNING)
                    
                    click_at(ENDGAME_CLICK_X, ENDGAME_CLICK_Y)
                    if stop_after_current_game:
                        log_message("GAME_OVER: Dừng auto theo yêu cầu (stop_after_current_game).")
                        is_running = False 
                    current_scenario = None 
                    current_game_ai_color = None
                    ai_color_locked_this_game = False
                    current_game_moves = []
                    last_known_board_state_for_opponent_move = None
                    waiting_room_enter_time = None 
                    specific_sleep_needed = 2.5 

        # 4) Sleep logic at the end of the loop
        if specific_sleep_needed > 0:
            time.sleep(specific_sleep_needed)
        else:
            if screenshot is not None: # Chỉ sleep loop_delay nếu có ảnh được xử lý
                time.sleep(loop_delay) # Default sleep if no specific one was set and screenshot was processed
            # Nếu screenshot is None, vòng lặp đã sleep 0.5s ở trên rồi.

    log_message("Vòng lặp tự động đã kết thúc.")
    if root and root.winfo_exists():
        root.after(0, update_button_states)

# --- HÀM LƯU VÀ TẢI KINH NGHIỆM ---
def format_game_experience(record):
    """Định dạng một bản ghi kinh nghiệm game thành chuỗi dễ đọc."""
    moves_str = []
    for i, (color, move) in enumerate(record["moves"], 1):
        if move == 'PASS':
            move_str = "PASS"
        else:
            r, c = move
            move_str = f"{chr(ord('A') + c)}{r + 1}"
        moves_str.append(f"{i}. {color}: {move_str}")
    
    return {
        "timestamp": record["timestamp"],
        "ai_color": record["ai_color"],
        "result": record["result_for_ai"],
        "moves": "\n".join(moves_str)
    }

def save_game_experience(ai_color, result, moves_history):
    record = {
        "ai_color": ai_color, # Có thể là None nếu màu AI không xác định được
        "result_for_ai": result,
        "moves": moves_history,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    log_message(f"[SAVE_EXP] Chuẩn bị lưu: AI Color='{ai_color}', Result='{result}', Moves_Count={len(moves_history)}", level=logging.INFO)

    try:
        experiences = []
        if os.path.exists(EXPERIENCE_FILE_PATH):
            with open(EXPERIENCE_FILE_PATH, 'r', encoding='utf-8') as f:
                text = f.read().strip()
                if text: # Chỉ parse JSON nếu text không rỗng
                    try:
                        experiences = json.loads(text)
                        if not isinstance(experiences, list):
                            log_message(f"Lỗi: File kinh nghiệm '{EXPERIENCE_FILE_PATH}' không chứa một danh sách. Sẽ tạo mới.", level=logging.WARNING)
                            experiences = []
                    except json.JSONDecodeError as e_json:
                        log_message(f"Lỗi giải mã JSON từ '{EXPERIENCE_FILE_PATH}': {e_json}. File có thể bị hỏng. Sẽ tạo mới.", level=logging.WARNING)
                        experiences = []
        
        experiences.append(record)

        # Ghi file và fsync để chắc chắn đã lưu
        with open(EXPERIENCE_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(experiences, f, indent=2, ensure_ascii=False)
            f.flush() # Đảm bảo buffer được ghi ra OS
            if hasattr(os, 'fsync'): # os.fsync không có trên Windows cho file objects thường, kiểm tra trước
                try:
                    os.fsync(f.fileno()) # Yêu cầu OS ghi ra đĩa vật lý
                except OSError as e_fsync:
                    log_message(f"Lưu ý: Không thể fsync file trên hệ điều hành này hoặc file không hỗ trợ: {e_fsync}", level=logging.DEBUG)
            elif sys.platform == 'win32':
                # Trên Windows, flush thường đủ cho file text, nhưng có thể xem xét win32file.FlushFileBuffers nếu cần sự đảm bảo cao hơn
                # Tuy nhiên, điều đó sẽ thêm một dependency mới.
                pass 

        log_message(f"Đã lưu kinh nghiệm ván đấu vào '{EXPERIENCE_FILE_PATH}'. Tổng số: {len(experiences)} bản ghi.")
            
    except Exception as e:
        log_message(f"Lỗi nghiêm trọng khi lưu kinh nghiệm ván đấu: {e}", level=logging.ERROR)
        import traceback
        log_message(traceback.format_exc(), level=logging.ERROR)

def load_game_experience():
    global loaded_game_experiences
    if os.path.exists(EXPERIENCE_FILE_PATH):
        try:
            with open(EXPERIENCE_FILE_PATH, 'r', encoding='utf-8') as f:
                experiences_from_file = json.load(f)
                if isinstance(experiences_from_file, list):
                    loaded_game_experiences = experiences_from_file
                    log_message(f"Đã tải {len(loaded_game_experiences)} bản ghi kinh nghiệm từ '{EXPERIENCE_FILE_PATH}'.")
                else:
                    log_message(f"Lỗi: File kinh nghiệm '{EXPERIENCE_FILE_PATH}' không chứa một danh sách. Không tải.", level=logging.WARNING)
                    loaded_game_experiences = [] 
        except json.JSONDecodeError:
            log_message(f"Lỗi giải mã JSON khi tải từ '{EXPERIENCE_FILE_PATH}'. File có thể bị hỏng. Không tải.", level=logging.WARNING)
            loaded_game_experiences = []
        except Exception as e:
            log_message(f"Lỗi không xác định khi tải file kinh nghiệm: {e}", level=logging.ERROR)
            loaded_game_experiences = []
    else:
        log_message(f"File kinh nghiệm '{EXPERIENCE_FILE_PATH}' không tồn tại. Sẽ tạo mới khi có ván đấu kết thúc.")
        loaded_game_experiences = [] 

def analyze_game_experience(record):
    """Phân tích một ván đấu để rút kinh nghiệm."""
    moves_str = []
    analysis = {
        "early_game": [],  # 10 nước đầu
        "mid_game": [],    # 10 nước tiếp
        "late_game": []    # Các nước còn lại
    }
    
    for i, (color, move) in enumerate(record["moves"], 1):
        if move == 'PASS':
            move_str = "PASS"
        else:
            r, c = move
            move_str = f"{chr(ord('A') + c)}{r + 1}"
        moves_str.append(f"{i}. {color}: {move_str}")
        
        # Phân loại nước đi theo giai đoạn
        if i <= 10:
            analysis["early_game"].append((color, move))
        elif i <= 20:
            analysis["mid_game"].append((color, move))
        else:
            analysis["late_game"].append((color, move))
    
    return {
        "timestamp": record["timestamp"],
        "ai_color": record["ai_color"],
        "result": record["result_for_ai"],
        "moves": "\n".join(moves_str),
        "analysis": analysis
    }

def update_weights_from_experience(win_games, loss_games):
    """Cập nhật trọng số dựa trên phân tích các ván đấu."""
    global MOBILITY_WEIGHT_INITIAL, MOBILITY_WEIGHT_MIDGAME, MOBILITY_WEIGHT_LATEGAME
    global FORCE_PASS_BONUS, PASS_PENALTY, STABLE_EDGE_PIECE_WEIGHT
    global PIECE_COUNT_WEIGHT_EARLY_MID, PIECE_COUNT_WEIGHT_LATE
    global BAD_MOVE_THRESHOLD, TRAP_SITUATION_WEIGHT
    
    if not win_games and not loss_games:
        log_message("Không có dữ liệu thắng/thua (từ file) để cập nhật trọng số AI.", level=logging.INFO)
        return
        
    # Phần phân tích chi tiết nước đi đã được loại bỏ vì chưa hoàn thiện và gây lỗi.
    # Các biến win_early_moves, loss_early_moves,... không còn được sử dụng ở đây.

    changes_made = False
    # Điều chỉnh trọng số dựa trên việc có ván thắng/thua
    if win_games: 
        original_weights = (MOBILITY_WEIGHT_INITIAL, MOBILITY_WEIGHT_MIDGAME, MOBILITY_WEIGHT_LATEGAME, FORCE_PASS_BONUS, STABLE_EDGE_PIECE_WEIGHT)
        MOBILITY_WEIGHT_INITIAL = min(20, MOBILITY_WEIGHT_INITIAL + 1)
        MOBILITY_WEIGHT_MIDGAME = min(30, MOBILITY_WEIGHT_MIDGAME + 1)
        MOBILITY_WEIGHT_LATEGAME = min(45, MOBILITY_WEIGHT_LATEGAME + 1)
        FORCE_PASS_BONUS = min(1000, FORCE_PASS_BONUS + 50)
        STABLE_EDGE_PIECE_WEIGHT = min(80, STABLE_EDGE_PIECE_WEIGHT + 5)
        if original_weights != (MOBILITY_WEIGHT_INITIAL, MOBILITY_WEIGHT_MIDGAME, MOBILITY_WEIGHT_LATEGAME, FORCE_PASS_BONUS, STABLE_EDGE_PIECE_WEIGHT):
            changes_made = True
    
    if loss_games:
        original_weights_loss = (MOBILITY_WEIGHT_INITIAL, MOBILITY_WEIGHT_MIDGAME, MOBILITY_WEIGHT_LATEGAME, PASS_PENALTY, PIECE_COUNT_WEIGHT_EARLY_MID)
        MOBILITY_WEIGHT_INITIAL = max(10, MOBILITY_WEIGHT_INITIAL - 1)
        MOBILITY_WEIGHT_MIDGAME = max(20, MOBILITY_WEIGHT_MIDGAME - 1)
        MOBILITY_WEIGHT_LATEGAME = max(35, MOBILITY_WEIGHT_LATEGAME - 1)
        PASS_PENALTY = max(-800, PASS_PENALTY - 50)
        PIECE_COUNT_WEIGHT_EARLY_MID = max(-3.0, PIECE_COUNT_WEIGHT_EARLY_MID - 0.1)
        if original_weights_loss != (MOBILITY_WEIGHT_INITIAL, MOBILITY_WEIGHT_MIDGAME, MOBILITY_WEIGHT_LATEGAME, PASS_PENALTY, PIECE_COUNT_WEIGHT_EARLY_MID):
            changes_made = True
    
    if changes_made:
        log_message(f"Đã cập nhật trọng số AI dựa trên {len(win_games)} ván thắng và {len(loss_games)} ván thua.")
        log_message(f"Trọng số mới: MOB_INIT={MOBILITY_WEIGHT_INITIAL}, MOB_MID={MOBILITY_WEIGHT_MIDGAME}, MOB_LATE={MOBILITY_WEIGHT_LATEGAME}, FORCE_PASS={FORCE_PASS_BONUS}, PASS_PENALTY={PASS_PENALTY}, STABLE_EDGE={STABLE_EDGE_PIECE_WEIGHT}, PIECE_COUNT_EM={PIECE_COUNT_WEIGHT_EARLY_MID:.1f}", level=logging.DEBUG)
    else:
        log_message(f"Không có thay đổi trọng số AI sau khi phân tích {len(win_games)} thắng / {len(loss_games)} thua (có thể đã đạt giới hạn hoặc không có game).", level=logging.INFO)

# --- HÀM KHỞI TẠO TRẠNG THÁI GAME MỚI ---
def initialize_new_game_state(cv_img_param):
    """Khởi tạo các biến và trạng thái cần thiết cho một ván game mới."""
    global current_game_ai_color, ai_color_locked_this_game, current_game_moves, \
           last_known_board_state_for_opponent_move, ai_moved
    global opponent_info_color_var, opponent_info_pieces_var, opponent_info_last_move_var
    global ai_info_color_var, ai_info_pieces_var, ai_info_last_move_var, ai_info_win_pct_var
    # Thêm các biến label toàn cục vào đây
    global opponent_info_color_label, opponent_info_pieces_label, opponent_info_last_move_label
    global ai_info_color_label, ai_info_pieces_label, ai_info_last_move_label, ai_info_win_pct_label

    log_message("GAME_INIT: Bắt đầu khởi tạo ván đấu mới...")

    current_game_ai_color = None
    ai_color_locked_this_game = False
    ai_moved = False # Reset cờ ai_moved cho ván mới
    current_game_moves = []
    last_known_board_state_for_opponent_move = None

    # Reset GUI vars, kiểm tra sự tồn tại của LABEL WIDGET
    if opponent_info_color_label and opponent_info_color_label.winfo_exists(): opponent_info_color_var.set("Đối thủ: --")
    if opponent_info_pieces_label and opponent_info_pieces_label.winfo_exists(): opponent_info_pieces_var.set("Quân: 0")
    if opponent_info_last_move_label and opponent_info_last_move_label.winfo_exists(): opponent_info_last_move_var.set("Nước cuối: --")
    if ai_info_color_label and ai_info_color_label.winfo_exists(): ai_info_color_var.set("AI: --")
    if ai_info_pieces_label and ai_info_pieces_label.winfo_exists(): ai_info_pieces_var.set("Quân: 0")
    if ai_info_last_move_label and ai_info_last_move_label.winfo_exists(): ai_info_last_move_var.set("Nước cuối: --")
    if ai_info_win_pct_label and ai_info_win_pct_label.winfo_exists(): ai_info_win_pct_var.set("Win%: --")

    log_message("GAME_INIT: Tải lại kinh nghiệm...")
    load_game_experience() # Tải kinh nghiệm
    
    log_message("GAME_INIT: Xây dựng thống kê khai cuộc...")
    build_opening_book_statistics() # Xây dựng opening book từ kinh nghiệm vừa tải

    log_message("GAME_INIT: Chụp trạng thái bàn cờ ban đầu...")
    initial_board_state, b_init, w_init = get_board_state_cv(cv_img_param)
    last_known_board_state_for_opponent_move = [row[:] for row in initial_board_state]
    log_message(f"GAME_INIT: Trạng thái bàn cờ ban đầu đã lưu. B:{b_init} W:{w_init}")

    global last_known_black_count_global, last_known_white_count_global
    last_known_black_count_global = b_init
    last_known_white_count_global = w_init
    log_message(f"GAME_INIT: Cập nhật số quân toàn cục: Đen {b_init}, Trắng {w_init}", level=logging.DEBUG)

    # Cố gắng xác định màu AI ban đầu
    log_message("GAME_INIT: Cố gắng xác định màu AI ban đầu...")
    detected_color_init = None # Đổi tên biến để tránh xung đột với cv_img_param
    temp_cv_img_param = cv_img_param # Tạo bản sao để không thay đổi cv_img_param gốc nếu screenshot thất bại
    for i in range(3): # Lặp tối đa 3 lần
        detected_color_init = detect_ai_color_cv(temp_cv_img_param) # Sử dụng temp_cv_img_param
        if detected_color_init:
            log_message(f"GAME_INIT: Phát hiện màu AI (lần {i+1}/3): {detected_color_init}")
            break
        log_message(f"GAME_INIT: Chưa phát hiện màu AI (lần {i+1}/3). Chờ 0.1s và thử lại...")
        time.sleep(0.1)
        if i < 2: # Chỉ chụp lại màn hình nếu chưa phải lần cuối
            new_screenshot = adb_screencap()
            if new_screenshot:
                temp_cv_img_param = cv2.cvtColor(np.array(new_screenshot), cv2.COLOR_RGB2BGR)
            else:
                log_message("GAME_INIT: Không thể chụp lại màn hình trong lúc retry.", level=logging.WARNING)
                # Vẫn tiếp tục thử với ảnh cũ nếu không chụp lại được

    if detected_color_init:
        current_game_ai_color = detected_color_init
        ai_color_locked_this_game = True
        log_message(f"GAME_INIT: AI là quân: {current_game_ai_color} (xác định khi khởi tạo)")
        if ai_info_color_label and ai_info_color_label.winfo_exists():
            root.after(0, lambda c=current_game_ai_color: ai_info_color_var.set(f"AI: {c}"))
        opp_color_display_init = 'W' if current_game_ai_color == 'B' else 'B'
        if opponent_info_color_label and opponent_info_color_label.winfo_exists():
            root.after(0, lambda c=opp_color_display_init: opponent_info_color_var.set(f"Đối thủ: {c}"))
    else:
        log_message("GAME_INIT: Không xác định được màu AI khi khởi tạo. Sẽ thử lại ở lượt AI.", level=logging.WARNING)

    # Cập nhật số quân dựa trên màu AI (nếu đã xác định được)
    # Nếu current_game_ai_color là None, giả sử AI là 'B' cho hiển thị ban đầu, sẽ được sửa lại sau
    my_initial_pieces = b_init
    opponent_initial_pieces = w_init
    if current_game_ai_color == 'W': # Nếu AI là trắng
        my_initial_pieces = w_init
        opponent_initial_pieces = b_init
    
    if opponent_info_pieces_label and opponent_info_pieces_label.winfo_exists(): 
        opponent_info_pieces_var.set(f"Quân: {opponent_initial_pieces}") 
    if ai_info_pieces_label and ai_info_pieces_label.winfo_exists(): 
        ai_info_pieces_var.set(f"Quân: {my_initial_pieces}") 
    
    if game_progress_bar and game_progress_bar.winfo_exists(): # Reset progress bar
        root.after(0, lambda: game_progress_bar.config(value=0))
    if game_progress_text_var and game_progress_text_label and game_progress_text_label.winfo_exists():
        root.after(0, lambda: game_progress_text_var.set("0%"))

    log_message("GAME_INIT: Hoàn tất khởi tạo ván đấu.")

# --- HÀM DEBUG KIỂM TRA PIXEL PHÒNG CHỜ ---
def check_and_log_waiting_room_pixel(cv_img):
    x, y = WAITING_ROOM_PIXEL_X, WAITING_ROOM_PIXEL_Y
    target_rgb = WAITING_ROOM_PIXEL_COLOR
    tolerance = WAITING_ROOM_PIXEL_TOLERANCE
    
    if cv_img is None:
        # log_message(f"DEBUG_WAITING_ROOM: cv_img is None. Cannot check pixel.", level=logging.DEBUG)
        return False
    if not (0 <= y < cv_img.shape[0] and 0 <= x < cv_img.shape[1]):
        # log_message(f"DEBUG_WAITING_ROOM: Coords ({x},{y}) are out of bounds for image shape {cv_img.shape[:2]}.", level=logging.DEBUG)
        return False
    
    try:
        b_actual, g_actual, r_actual = cv_img[y, x]
        is_match = (abs(int(r_actual) - target_rgb[0]) <= tolerance and
                    abs(int(g_actual) - target_rgb[1]) <= tolerance and
                    abs(int(b_actual) - target_rgb[2]) <= tolerance)
        
        # if is_match: # Chỉ log nếu thực sự khớp, hoặc nếu cần debug thì bật lại log dưới
            # log_message(f"DEBUG_WAITING_ROOM: At ({x},{y}), Found RGB=({r_actual},{g_actual},{b_actual}). Target={target_rgb}, Tol={tolerance}. Match={is_match}", level=logging.INFO)
        # else:
            # log_message(f"DEBUG_WAITING_ROOM: At ({x},{y}), Found RGB=({r_actual},{g_actual},{b_actual}). Target={target_rgb}, Tol={tolerance}. Match={is_match}", level=logging.DEBUG)
        return is_match
    except IndexError:
        # log_message(f"DEBUG_WAITING_ROOM: IndexError accessing pixel at ({x},{y}). Image shape {cv_img.shape[:2]}", level=logging.DEBUG)
        return False
    except Exception as e:
        log_message(f"Lỗi khi kiểm tra pixel phòng chờ ({x},{y}): {e}", level=logging.WARNING) # Giữ lại lỗi này ở WARNING
        return False

def build_opening_book_statistics():
    """
    Xây dựng thống kê khai cuộc từ loaded_game_experiences.
    opening_stats = {
        prefix_tuple (chỉ moves): {
            move_coord_or_pass: [win_count, loss_count],
            ...
        },
        ...
    }
    """
    global opening_stats, loaded_game_experiences
    opening_stats = {} # Reset mỗi lần xây dựng lại
    if not loaded_game_experiences:
        log_message("OPENING_BOOK_BUILD: Không có kinh nghiệm nào để xây dựng thống kê.", level=logging.INFO)
        return

    num_records_processed = 0
    for record in loaded_game_experiences:
        if "moves" not in record or not isinstance(record["moves"], list):
            continue

        # Chỉ lấy phần tọa độ nước đi hoặc 'PASS'
        sequence_of_actual_moves = []
        valid_sequence = True
        for move_entry in record["moves"]:
            if isinstance(move_entry, (list, tuple)) and len(move_entry) == 2:
                # move_entry[0] là màu, move_entry[1] là nước đi (r,c) hoặc 'PASS'
                actual_move = move_entry[1]
                # Đảm bảo nước đi là tuple (int, int) hoặc string 'PASS'
                if isinstance(actual_move, (list, tuple)) and len(actual_move) == 2 and \
                   isinstance(actual_move[0], int) and isinstance(actual_move[1], int):
                    sequence_of_actual_moves.append(tuple(actual_move)) # Chuyển list thành tuple nếu cần
                elif actual_move == 'PASS':
                    sequence_of_actual_moves.append('PASS')
                else:
                    # log_message(f"OPENING_BOOK_BUILD: Nước đi không hợp lệ trong record: {actual_move}. Bỏ qua record này.", level=logging.DEBUG)
                    valid_sequence = False
                    break
            else:
                # log_message(f"OPENING_BOOK_BUILD: Định dạng move_entry không hợp lệ: {move_entry}. Bỏ qua record này.", level=logging.DEBUG)
                valid_sequence = False
                break
        
        if not valid_sequence:
            continue

        game_result_for_ai = record.get("result_for_ai")

        for i in range(len(sequence_of_actual_moves)):
            # prefix_tuple là các nước đi LÊN ĐẾN (không bao gồm) nước đi thứ i
            prefix_tuple = tuple(sequence_of_actual_moves[:i])
            # move_made_from_prefix là nước đi thứ i được thực hiện từ trạng thái prefix_tuple
            move_made_from_prefix = sequence_of_actual_moves[i]

            stats_for_prefix = opening_stats.setdefault(prefix_tuple, {})
            current_win_loss = stats_for_prefix.setdefault(move_made_from_prefix, [0, 0])

            if game_result_for_ai == "WIN":
                current_win_loss[0] += 1
            elif game_result_for_ai == "LOSS":
                current_win_loss[1] += 1
            # Các ván hòa không làm thay đổi win/loss count trong opening book này
            
            stats_for_prefix[move_made_from_prefix] = current_win_loss
        num_records_processed +=1
        
    log_message(f"OPENING_BOOK_BUILD: Đã xây dựng xong thống kê khai cuộc từ {num_records_processed} bản ghi. {len(opening_stats)} tiền tố được ghi nhận.", level=logging.INFO)
    # log_message(f"DEBUG opening_stats (first 5): {dict(list(opening_stats.items())[:5])}", level=logging.DEBUG)

def connect_to_selected_device():
    """Kết nối đến thiết bị ADB đã chọn trong combobox và khởi tạo u2_device."""
    global adb_device, u2_device, device_selection_var

    if not device_selection_var:
        log_message("Lỗi: device_selection_var chưa được khởi tạo.", level=logging.ERROR)
        return False
        
    selected_device_display_name = device_selection_var.get()
    if not selected_device_display_name:
        log_message("Chưa chọn thiết bị ADB từ combobox.", level=logging.WARNING)
        messagebox.showwarning("Thiếu Thiết Bị", "Vui lòng chọn một thiết bị ADB từ danh sách.")
        return False

    selected_serial = None
    try:
        # Trích xuất serial từ chuỗi hiển thị dạng "Model (serial)" hoặc chỉ "serial"
        if '(' in selected_device_display_name and ')' in selected_device_display_name:
            selected_serial = selected_device_display_name.split('(')[1].split(')')[0].strip()
        else:
            selected_serial = selected_device_display_name 
            log_message(f"Giả sử '{selected_serial}' là serial do không có định dạng Model (serial).", level=logging.DEBUG)

        if not selected_serial:
            log_message(f"Không thể xác định serial từ '{selected_device_display_name}'.", level=logging.ERROR)
            return False

    except IndexError:
        log_message(f"Lỗi IndexError khi trích xuất serial từ '{selected_device_display_name}'.", level=logging.ERROR)
        return False
    except Exception as e_parse_serial:
        log_message(f"Lỗi không xác định khi trích xuất serial: {e_parse_serial}", level=logging.ERROR)
        return False

    # Ngắt kết nối u2 hiện tại nếu có
    if u2_device:
        log_message(f"Ngắt kết nối uiautomator2 hiện tại (nếu có) để kết nối lại với {selected_serial}.", level=logging.DEBUG)
        u2_device = None 

    log_message(f"Đang kết nối với thiết bị đã chọn: {selected_serial} (từ '{selected_device_display_name}')")
    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        device_to_connect = client.device(selected_serial)
        
        if device_to_connect:
            adb_device = device_to_connect
            log_message(f"Đã kết nối ADB (ppadb) thành công với: {adb_device.serial}")
            
            # Kết nối uiautomator2 nếu ppadb thành công
            if u2:
                try:
                    u2_device = u2.connect(selected_serial)
                    log_message(f"Đã kết nối uiautomator2 thành công với: {selected_serial}")
                except Exception as e_u2:
                    log_message(f"Lỗi kết nối uiautomator2: {e_u2}", level=logging.ERROR)
                    u2_device = None
            return True
        else:
            log_message(f"Không tìm thấy thiết bị ADB với serial: {selected_serial}", level=logging.ERROR)
            return False

    except Exception as e:
        log_message(f"Lỗi kết nối ADB: {e}", level=logging.ERROR)
        return False

# ===== GUI FUNCTIONS AND RELATED LOGIC =====

def start_auto():
    """Bật auto-play."""
    global is_running, auto_thread, ai_moved, adb_device, u2_device # Thêm adb_device, u2_device để kiểm tra
    
    # Kiểm tra kết nối trước khi bắt đầu
    if not connect_to_selected_device():
        log_message("Start Auto: Không thể kết nối với thiết bị đã chọn. Vui lòng kiểm tra lại.", level=logging.ERROR)
        # connect_to_selected_device() đã hiển thị messagebox nếu có lỗi
        return

    if not is_running:
        log_message("Chuẩn bị bắt đầu auto...")
        is_running = True
        ai_moved = False # Reset cờ ai_moved mỗi khi auto bắt đầu
        auto_thread = threading.Thread(target=auto_play_loop, daemon=True)
        auto_thread.start()
        update_button_states()
        log_message("Auto-play đã bắt đầu.")
    else:
        log_message("Auto đã chạy rồi.", level=logging.WARNING)

def stop_auto():
    """Tắt auto-play."""
    global is_running
    if is_running:
        is_running = False
        # auto_thread là daemon nên sẽ tự kết thúc khi is_running = False và vòng lặp của nó thoát
        # Nếu cần join, phải đợi ở đây, nhưng có thể làm GUI bị treo nếu auto_thread mất nhiều thời gian để dừng.
        log_message("Đang yêu cầu dừng Auto-play...")
        # Chờ một chút để thread có thể nhận thấy is_running = False và thoát vòng lặp
        # Tuy nhiên, việc join trực tiếp ở đây có thể không lý tưởng cho GUI.
        # Cách tốt hơn là auto_thread tự gọi update_button_states khi nó thực sự kết thúc.
    else:
        log_message("Auto chưa chạy.", level=logging.INFO)
    update_button_states() # Cập nhật nút ngay lập tức
    # log_message("Auto-play đã dừng (yêu cầu dừng đã được gửi).") # Log này nên ở cuối auto_play_loop

def stop_auto_event(event=None):
    """Gắn phím F3 để dừng auto."""
    stop_auto()

def update_button_states():
    """Bật/tắt trạng thái Start/Stop button tuỳ is_running."""
    global start_button, stop_button, pick_button, stop_after_game_button, device_combobox, root, is_running, stop_after_current_game_var, stop_after_current_game
    if not root or not root.winfo_exists(): return

    try:
        s_normal, s_disabled = "normal", "disabled"
        
        # Start button
        if start_button and start_button.winfo_exists():
            start_button.config(state=s_disabled if is_running else s_normal)
        
        # Stop button
        if stop_button and stop_button.winfo_exists():
            stop_button.config(state=s_normal if is_running else s_disabled)
        
        # Pick coordinate button
        if pick_button and pick_button.winfo_exists():
            pick_button.config(state=s_disabled if is_running else s_normal)
        
        # Device combobox
        if device_combobox and device_combobox.winfo_exists():
            device_combobox.config(state=s_disabled if is_running else "readonly")

        # Stop after game checkbutton
        if stop_after_game_button and isinstance(stop_after_game_button, tk.Checkbutton) and stop_after_game_button.winfo_exists():
            # Checkbutton nên luôn enabled để người dùng có thể thay đổi ý định
            # Trạng thái của nó được quản lý bởi stop_after_current_game_var
            # Logic stop_after_current_game được xử lý trong request_stop_after_game()
            # và trong vòng lặp auto_play_loop()
            # Nếu muốn disable nó khi không chạy auto, có thể thêm:
            # stop_after_game_button.config(state=s_normal if is_running else s_disabled)
            # Nhưng thường thì để nó enabled sẽ thân thiện hơn.
            # Cập nhật trạng thái check của nó dựa trên biến logic
            if stop_after_current_game_var: # Đảm bảo biến tồn tại
                 current_check_state = stop_after_current_game_var.get()
                 if current_check_state != stop_after_current_game:
                    # Nếu trạng thái GUI khác với trạng thái logic (ví dụ, auto dừng và reset logic)
                    # Cập nhật lại GUI cho khớp
                    if not is_running and stop_after_current_game == False:
                         stop_after_current_game_var.set(False)
            pass

    except tk.TclError as e:
        log_message(f"Lỗi TclError trong update_button_states: {e}", level=logging.DEBUG)
    except Exception as e_upd_btn:
        log_message(f"Lỗi không xác định trong update_button_states: {e_upd_btn}", level=logging.ERROR)

def create_gui():
    global root, start_button, stop_button, pick_button, stop_after_game_button, stop_after_current_game_var
    global log_area, target_selection_var, device_selection_var, device_combobox, DEFAULT_TARGET_NAME, TARGET_OPTIONS
    global game_progress_bar, game_progress_text_label, game_progress_text_var 
    global general_win_draw_loss_var, general_win_draw_loss_label
    global opponent_info_color_var, opponent_info_pieces_var, opponent_info_last_move_var
    global ai_info_color_var, ai_info_pieces_var, ai_info_last_move_var, ai_info_win_pct_var
    global opponent_info_color_label, opponent_info_pieces_label, opponent_info_last_move_label
    global ai_info_color_label, ai_info_pieces_label, ai_info_last_move_label, ai_info_win_pct_label
    global reset_stats_button

    # --- Dark-mode style ---
    style = ttk.Style(root)
    style.theme_use('clam')
    
    # Màu nền chính cho cửa sổ và các frame
    dark_bg = '#2e2e2e'
    light_text = '#e0e0e0'
    button_bg = '#4a90e2'
    button_active_bg = '#357ABD'
    entry_bg = '#3c3c3c'
    entry_fg = '#e0e0e0'
    
    root.configure(bg=dark_bg)
    
    style.configure('TFrame', background=dark_bg)
    style.configure('TLabel', background=dark_bg, foreground=light_text, font=('Segoe UI', 9))
    style.configure('TLabelframe', background=dark_bg, foreground=light_text, font=('Segoe UI', 9, 'bold'))
    style.configure('TLabelframe.Label', background=dark_bg, foreground=light_text, font=('Segoe UI', 9, 'bold'))
    
    style.configure('TButton', font=('Segoe UI', 9, 'bold'), borderwidth=1)
    style.map('TButton',
              foreground=[('active', light_text), ('!disabled', light_text)],
              background=[('active', button_active_bg), ('!disabled', button_bg)],
              relief=[('pressed', 'sunken'), ('!pressed', 'raised')])

    # --- Summary & progress ---
    summary_frame = ttk.Frame(root, padding=(10, 5, 10, 8))
    summary_frame.grid(row=3, column=0, sticky='ew')
    summary_frame.columnconfigure(2, weight=1) # Cho progressbar mở rộng

    # Frame cho thống kê và nút reset
    stats_frame = ttk.Frame(summary_frame)
    stats_frame.grid(row=0, column=0, sticky='w')
    
    general_win_draw_loss_label = ttk.Label(stats_frame, textvariable=general_win_draw_loss_var,
                                            font=('Segoe UI',10,'bold'))
    general_win_draw_loss_label.pack(side='left')
    
    reset_stats_button = ttk.Button(stats_frame, text="↺", width=3, command=reset_stats)
    reset_stats_button.pack(side='left', padx=(5,0))
    
    ttk.Label(summary_frame, text='Tiến độ ván:').grid(row=0, column=1, padx=(20,5), sticky='w')
    
    game_progress_bar = ttk.Progressbar(summary_frame, length=100, mode='determinate', maximum=100)
    game_progress_bar.grid(row=0, column=2, sticky='ew', padx=(0,5))
    
    game_progress_text_label = ttk.Label(summary_frame, textvariable=game_progress_text_var, width=5, anchor='w')
    game_progress_text_label.grid(row=0, column=3, sticky='w')

    # --- Device selection row ---
    device_frame = ttk.Frame(root, padding=(10, 10, 10, 5))
    device_frame.grid(row=0, column=0, sticky='ew')
    device_frame.columnconfigure(1, weight=1) # Cho combobox mở rộng

    ttk.Label(device_frame, text='Thiết bị ADB:').grid(row=0, column=0, sticky='w', padx=(0,5))
    device_combobox = ttk.Combobox(device_frame, textvariable=device_selection_var, state='readonly', width=30) # Gán biến toàn cục
    device_combobox.grid(row=0, column=1, sticky='ew', padx=5)
    
    refresh_btn = ttk.Button(device_frame, text='Làm mới', command=refresh_device_list, width=10)
    refresh_btn.grid(row=0, column=2, padx=(0,5))
    
    view_btn = ttk.Button(device_frame, text='Xem MH', command=view_device_screen, width=10) # Gán cho biến nếu cần, nhưng hiện tại chỉ gọi lệnh
    view_btn.grid(row=0, column=3)

    # --- Controls row ---
    controls_frame = ttk.Frame(root, padding=(10, 5, 10, 5))
    controls_frame.grid(row=1, column=0, sticky='ew')
    # controls_frame.columnconfigure(3, weight=1) # Có thể không cần nếu các nút có độ rộng cố định

    ttk.Label(controls_frame, text='Mục tiêu:').grid(row=0, column=0, sticky='w', padx=(0,5))
    target_combo = ttk.Combobox(controls_frame, textvariable=target_selection_var,
                                values=list(TARGET_OPTIONS.keys()), state='readonly', width=18)
    target_combo.grid(row=0, column=1, padx=(0,10))

    # def on_target_selected_internal(event=None): # XÓA ĐỊNH NGHĨA KHỎI ĐÂY
    #     global selected_target_name 
    #     selected_target_name = target_selection_var.get()
    #     log_message(f"Đã chọn mục tiêu: {selected_target_name}")
    
    target_combo.bind("<<ComboboxSelected>>", on_target_selected_internal)
    # if not target_selection_var.get() and DEFAULT_TARGET_NAME in TARGET_OPTIONS: # Đã chuyển logic này ra ngoài
    #     target_selection_var.set(DEFAULT_TARGET_NAME)

    start_button = ttk.Button(controls_frame, text='Bắt đầu (F2)', command=start_auto, width=12) # Gán biến toàn cục
    start_button.grid(row=0, column=2, padx=(0,5))
    
    stop_button  = ttk.Button(controls_frame, text='Dừng (F3)',  command=stop_auto_event, width=12) # Gán biến toàn cục
    stop_button.grid(row=0, column=3, padx=(0,5))
    
    pick_button  = ttk.Button(controls_frame, text='Chọn Tọa Độ', command=pick_coordinate_and_color, width=12) # Gán biến toàn cục
    pick_button.grid(row=0, column=4, padx=(0,10))
    
    stop_after_game_button = ttk.Checkbutton(controls_frame, text='Dừng sau ván', # Gán biến toàn cục
                                             variable=stop_after_current_game_var,
                                             command=request_stop_after_game)
    stop_after_game_button.grid(row=0, column=5, sticky='e')
    controls_frame.columnconfigure(5, weight=1) # Để checkbutton đẩy sang phải

    # --- Game info panels ---
    info_frame = ttk.Frame(root, padding=(10, 5, 10, 5))
    info_frame.grid(row=2, column=0, sticky='ew')
    info_frame.columnconfigure((0,1), weight=1) # Cả hai panel thông tin đều mở rộng

    # Đối thủ
    opp_frame = ttk.LabelFrame(info_frame, text='Thông Tin Đối Thủ', padding=10)
    opp_frame.grid(row=0, column=0, sticky='nsew', padx=(0,5))
    opponent_info_color_label = ttk.Label(opp_frame, textvariable=opponent_info_color_var) # Gán biến toàn cục
    opponent_info_color_label.pack(anchor='w', pady=1)
    opponent_info_pieces_label = ttk.Label(opp_frame, textvariable=opponent_info_pieces_var) # Gán biến toàn cục
    opponent_info_pieces_label.pack(anchor='w', pady=1)
    opponent_info_last_move_label = ttk.Label(opp_frame, textvariable=opponent_info_last_move_var) # Gán biến toàn cục
    opponent_info_last_move_label.pack(anchor='w', pady=1)

    # AI
    ai_frame = ttk.LabelFrame(info_frame, text='Thông Tin AI', padding=10)
    ai_frame.grid(row=0, column=1, sticky='nsew', padx=(5,0))
    ai_info_color_label = ttk.Label(ai_frame, textvariable=ai_info_color_var) # Gán biến toàn cục
    ai_info_color_label.pack(anchor='w', pady=1)
    ai_info_pieces_label = ttk.Label(ai_frame, textvariable=ai_info_pieces_var) # Gán biến toàn cục
    ai_info_pieces_label.pack(anchor='w', pady=1)
    ai_info_last_move_label = ttk.Label(ai_frame, textvariable=ai_info_last_move_var) # Gán biến toàn cục
    ai_info_last_move_label.pack(anchor='w', pady=1)
    ai_info_win_pct_label = ttk.Label(ai_frame, textvariable=ai_info_win_pct_var) # Gán biến toàn cục
    ai_info_win_pct_label.pack(anchor='w', pady=1)

    # --- Log area ---
    log_frame = ttk.Frame(root, padding=(10,0,10,10)) # Frame để có padding cho scrollbar
    log_frame.grid(row=4, column=0, sticky='nsew')
    log_frame.rowconfigure(0, weight=1)
    log_frame.columnconfigure(0, weight=1)

    log_area = scrolledtext.ScrolledText(log_frame, # Gán biến toàn cục
        state='disabled', height=10, wrap=tk.WORD,
        relief=tk.SUNKEN, borderwidth=1,
        bg='#1c1c1c', fg='#d4d4d4', # Màu nền và chữ cho log
        insertbackground='#ffffff', # Màu con trỏ nếu editable
        selectbackground=button_active_bg, # Màu nền khi bôi đen
        selectforeground=light_text,
        font=('Consolas', 9)
    )
    log_area.grid(row=0, column=0, sticky='nsew')
    
    # Scrollbar cho log_area (nếu dùng scrolledtext thì nó đã có sẵn)
    # Tuy nhiên, để custom style cho scrollbar với ttk, có thể làm như sau, nhưng ScrolledText đã có
    # vsb = ttk.Scrollbar(log_frame, orient="vertical", command=log_area.yview)
    # log_area.configure(yscrollcommand=vsb.set)
    # vsb.grid(row=0, column=1, sticky='ns')


    # Make the log area expandable
    root.rowconfigure(4, weight=1)
    root.columnconfigure(0, weight=1) # Cho phép cột chính mở rộng

    # Initial calls
    # refresh_device_list() # XÓA LỆNH GỌI NÀY
    # update_button_states() # XÓA LỆNH GỌI NÀY

def view_device_screen():
    """Mở scrcpy để xem màn hình thiết bị đã chọn."""
    global device_selection_var
    if not device_selection_var or not device_selection_var.get():
        messagebox.showerror("Lỗi", "Chưa chọn thiết bị ADB.")
        return
        
    selected_device_display = device_selection_var.get()
    device_serial = ""
    try:
        if '(' in selected_device_display and ')' in selected_device_display:
            device_serial = selected_device_display.split('(')[-1].split(')')[0]
        else:
            device_serial = selected_device_display 
        if not device_serial:
            messagebox.showerror("Lỗi", f"Không thể lấy serial từ: {selected_device_display}")
            return
    except Exception as e_serial:
        messagebox.showerror("Lỗi", f"Lỗi trích xuất serial: {e_serial}")
        return
        
    scrcpy_path_candidates = [
        r"C:\scrcpy\scrcpy.exe", 
        r"scrcpy.exe", 
        r"C:\Users\Admin\Desktop\scrcpy-win64-v3.2\scrcpy.exe"
    ]
    
    scrcpy_executable = None
    for path_candidate in scrcpy_path_candidates:
        if shutil.which(path_candidate):
             scrcpy_executable = shutil.which(path_candidate)
             break
        elif os.path.exists(path_candidate) and os.access(path_candidate, os.X_OK):
            scrcpy_executable = path_candidate
            break

    if not scrcpy_executable:
        messagebox.showerror("Lỗi", f"Không tìm thấy scrcpy.exe. Hãy kiểm tra đường dẫn hoặc cài đặt và đảm bảo nó trong PATH.")
        log_message(f"Không tìm thấy scrcpy tại các đường dẫn đã thử hoặc trong PATH.", level=logging.ERROR)
        return
        
    try:
        log_message(f"Đang mở scrcpy ({scrcpy_executable}) cho thiết bị: {device_serial}")
        subprocess.Popen([scrcpy_executable, "-s", device_serial])
    except FileNotFoundError:
        messagebox.showerror("Lỗi", f"Không tìm thấy file scrcpy tại: {scrcpy_executable}. Vui lòng kiểm tra lại.")
        log_message(f"Lỗi FileNotFoundError khi mở scrcpy: {scrcpy_executable}", level=logging.ERROR)
    except Exception as e_scrcpy:
        messagebox.showerror("Lỗi", f"Không thể mở scrcpy: {str(e_scrcpy)}")
        log_message(f"Lỗi khi mở scrcpy: {str(e_scrcpy)}", level=logging.ERROR)

def request_stop_after_game(): 
    global stop_after_current_game, stop_after_current_game_var, is_running
    # stop_after_current_game là biến logic chính, stop_after_current_game_var là của Checkbutton
    # Cập nhật biến logic dựa trên trạng thái của checkbutton
    stop_after_current_game = stop_after_current_game_var.get()
    
    if stop_after_current_game:
        if is_running:
            log_message("Sẽ dừng auto sau khi kết thúc ván hiện tại.")
        else:
            log_message("Auto chưa chạy. Yêu cầu 'Dừng sau ván' sẽ có hiệu lực khi auto bắt đầu và vào game.")
    else:
        log_message("Đã hủy yêu cầu dừng sau ván.")
    update_button_states() # Cập nhật lại trạng thái nút nếu cần thiết (ví dụ: disable checkbutton khi auto dừng)

def refresh_device_list():
    """Làm mới danh sách thiết bị ADB trong combobox."""
    global device_combobox, device_selection_var, adb_device, u2_device, root # Thêm root
    if not device_combobox or not (root and root.winfo_exists()) or not device_combobox.winfo_exists():
        return
        
    log_message("Đang làm mới danh sách thiết bị ADB...")
    current_selection_display = device_selection_var.get()

    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        devices_ppadb = client.devices()
        device_display_list = []
        if devices_ppadb:
            for dev in devices_ppadb:
                try:
                    model = dev.shell("getprop ro.product.model").strip()
                    serial = dev.serial
                    device_display_list.append(f"{model} ({serial})")
                except Exception:
                    if dev and dev.serial: device_display_list.append(f"Unknown ({dev.serial})")
                    # else: device_display_list.append(f"Unknown Device (no serial)") # Ít khi xảy ra
        
        device_combobox['values'] = device_display_list

        if not device_display_list:
            log_message("Không tìm thấy thiết bị ADB nào.", level=logging.WARNING)
            device_selection_var.set("")
            if adb_device or u2_device: # Nếu có kết nối cũ, reset chúng
                adb_device = None 
                u2_device = None
                log_message("Đã ngắt kết nối ADB/U2 do không còn thiết bị.", level=logging.INFO)
            update_button_states()
            return

        # Cố gắng chọn lại thiết bị cũ nếu còn trong danh sách mới, nếu không thì chọn cái đầu tiên
        new_selection_made = False
        if current_selection_display and current_selection_display in device_display_list:
            device_selection_var.set(current_selection_display)
            log_message(f"Đã giữ lại lựa chọn thiết bị: {current_selection_display}")
            new_selection_made = True
        elif device_display_list: # Nếu có thiết bị và không giữ được lựa chọn cũ
            device_selection_var.set(device_display_list[0])
            log_message(f"Đã chọn thiết bị đầu tiên: {device_display_list[0]}")
            new_selection_made = True
        else: # Không có thiết bị nào cả
             device_selection_var.set("")

        # Nếu có lựa chọn mới (hoặc lựa chọn cũ được xác nhận lại), thử kết nối
        if new_selection_made and device_selection_var.get():
            connect_to_selected_device()
        elif not device_selection_var.get() and (adb_device or u2_device): # Không có lựa chọn nào và đang có kết nối
            adb_device = None
            u2_device = None
            log_message("Đã ngắt kết nối ADB/U2 do không có thiết bị nào được chọn sau khi làm mới.", level=logging.INFO)

    except ConnectionRefusedError:
        log_message("Lỗi làm mới thiết bị: Không thể kết nối tới ADB server.", level=logging.ERROR)
        device_combobox['values'] = []
        device_selection_var.set("")
        if adb_device or u2_device: adb_device = None; u2_device = None
        if messagebox.askretrycancel("Lỗi ADB", "Không thể kết nối tới ADB server. Server chưa chạy hoặc bị chặn?\nBạn có muốn thử lại?"):
            if root and root.winfo_exists(): root.after(200, refresh_device_list) 
    except Exception as e_refresh:
        log_message(f"Lỗi không xác định khi làm mới danh sách thiết bị: {e_refresh}\n{traceback.format_exc()}", level=logging.ERROR)
        device_combobox['values'] = []
        device_selection_var.set("")
        if adb_device or u2_device: adb_device = None; u2_device = None
    finally:
        update_button_states() 

def reset_stats():
    """Reset thống kê thắng thua hòa về 0"""
    global win_count, loss_count, draw_count
    win_count = 0
    loss_count = 0
    draw_count = 0
    if general_win_draw_loss_var:
        general_win_draw_loss_var.set("Thắng: 0  Thua: 0  Hòa: 0")
    log_message("Đã reset thống kê thắng thua hòa về 0")

# ĐỊNH NGHĨA HÀM on_target_selected_internal Ở PHẠM VI TOÀN CỤC
def on_target_selected_internal(event=None):
    global selected_target_name, target_selection_var # Đảm bảo các biến toàn cục được tham chiếu đúng
    selected_target_name = target_selection_var.get()
    log_message(f"Đã chọn mục tiêu: {selected_target_name}")

if __name__ == "__main__":
    if mp.current_process().name == "MainProcess":
        mp.freeze_support()
        _pool = None
        try:
            if CPU_WORKERS > 0:
                _pool = mp.Pool(processes=CPU_WORKERS)
                print(f"Đã khởi tạo multiprocessing.Pool với {CPU_WORKERS} workers.")
            else:
                print("CPU_WORKERS <= 0, không khởi tạo Pool.")
        except Exception as e_pool_init:
            print(f"Lỗi khởi tạo multiprocessing.Pool: {e_pool_init}")
            _pool = None

    setup_logging()
    # load_game_experience() # XÓA DÒNG NÀY
    # build_custom_piece_maps() # XÓA DÒNG NÀY

    root = tk.Tk()
    root.title("Auto Cờ Lật (Minimax)")
    
    # Khởi tạo các StringVar/BooleanVar toàn cục TRƯỚC KHI gọi create_gui
    device_selection_var = tk.StringVar()
    target_selection_var = tk.StringVar() # Sẽ được gán giá trị mặc định trong create_gui nếu rỗng
    stop_after_current_game_var = tk.BooleanVar(value=False) # THAY ĐỔI value từ True thành False

    # Khởi tạo các StringVar cho thông tin game (đã có trong file, nhưng để đây cho rõ ràng)
    opponent_info_color_var = tk.StringVar(value="Đối thủ: --")
    opponent_info_pieces_var = tk.StringVar(value="Quân: 0")
    opponent_info_last_move_var = tk.StringVar(value="Nước cuối: --")
    ai_info_color_var = tk.StringVar(value="AI: --")
    ai_info_pieces_var = tk.StringVar(value="Quân: 0")
    ai_info_last_move_var = tk.StringVar(value="Nước cuối: --")
    ai_info_win_pct_var = tk.StringVar(value="Win%: --")
    general_win_draw_loss_var = tk.StringVar(value="Thắng: 0  Thua: 0  Hòa: 0")
    game_progress_text_var = tk.StringVar(value="0%") # Khởi tạo StringVar ở đây nữa
    
    create_gui()
    # Gọi các hàm khởi tạo/cập nhật GUI sau khi create_gui đã hoàn thành
    if root and root.winfo_exists(): # Đảm bảo root đã được tạo
        # Lấy giá trị target mặc định nếu chưa có và gọi on_target_selected_internal
        if not target_selection_var.get() and DEFAULT_TARGET_NAME in TARGET_OPTIONS:
            target_selection_var.set(DEFAULT_TARGET_NAME)
        on_target_selected_internal() # THÊM LỆNH GỌI NÀY
        
        refresh_device_list() # THÊM LỆNH GỌI NÀY
        update_button_states() # THÊM LỆNH GỌI NÀY

    calculate_board_geometry()
    load_game_experience() # THÊM DÒNG NÀY Ở ĐÂY
    build_custom_piece_maps() # THÊM DÒNG NÀY Ở ĐÂY

    def on_closing():
        log_message("Đang đóng ứng dụng...")
        if is_running: stop_auto()
        global _pool
        if _pool:
            log_message("Đang đóng multiprocessing.Pool...")
            try:
                _pool.close()
                _pool.join()
                log_message("Đã đóng multiprocessing.Pool.")
            except Exception as e_pool_close:
                log_message(f"Lỗi khi đóng Pool: {e_pool_close}", level=logging.ERROR)
            finally:
                _pool = None
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.bind("<F3>", stop_auto_event)
    update_button_states()
    log_message("Chương trình đã khởi động.")
    log_message(f"Sử dụng STATIC_POSITIONAL_WEIGHTS cố định cho AI. {CPU_WORKERS} luồng CPU.")
    root.mainloop()