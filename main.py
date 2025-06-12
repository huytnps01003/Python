# -*- coding: utf-8 -*-
import tkinter as tk
import sys
import os
import logging
import data.config as config

# --- PATH SETUP ---
# Thêm thư mục gốc của dự án vào sys.path để đảm bảo import hoạt động chính xác
# khi chạy từ bất kỳ đâu.
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- IMPORTS FROM MODULES ---
from data.logger import setup_logging, log_message
from data.ai import initialize_ai_services, shutdown_ai_services
from data.gui_components import create_gui, on_closing, setup_gui_variables
from data.board_state import build_custom_piece_maps, calculate_board_geometry

def main():
    """Hàm chính để khởi chạy ứng dụng."""
    # --- KHỞI TẠO ---
    # 1. Thiết lập logging
    setup_logging()
    log_message("Ứng dụng bắt đầu.", logging.INFO)

    # 2. Xây dựng các map cần thiết cho nhận diện
    build_custom_piece_maps()
    calculate_board_geometry()
    log_message("Đã tính toán và xây dựng các dữ liệu nhận diện.", logging.INFO)

    # --- TẠO GIAO DIỆN ---
    # 1. Tạo cửa sổ chính của Tkinter
    root = tk.Tk()
    
    # 2. Khởi tạo các biến Tkinter (quan trọng cho bước tiếp theo)
    setup_gui_variables()

    # 3. Khởi tạo các dịch vụ AI (ví dụ: multiprocessing pool)
    #    Phải được gọi SAU KHI setup_gui_variables()
    initialize_ai_services(use_multiprocessing=config.use_multiprocessing_var.get())
    log_message("Dịch vụ AI đã được khởi tạo.", logging.INFO)

    # 4. Dựng giao diện người dùng từ module gui_components
    create_gui(root)
    log_message("Giao diện đã được tạo.", logging.INFO)
    
    # --- QUẢN LÝ VÒNG ĐỜI ỨNG DỤNG ---
    # 1. Xử lý sự kiện đóng cửa sổ
    def handle_closing():
        # Gọi hàm on_closing đã được định nghĩa trong gui_components
        on_closing()
        # Dừng các dịch vụ AI trước khi thoát
        shutdown_ai_services()
        log_message("Ứng dụng đã đóng.", logging.INFO)

    root.protocol("WM_DELETE_WINDOW", handle_closing)

    # 2. Bắt đầu vòng lặp sự kiện của Tkinter
    root.mainloop()

if __name__ == "__main__":
    # Điểm vào chính của chương trình
    main() 