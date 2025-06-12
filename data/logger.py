# -*- coding: utf-8 -*-
import logging
import sys
import time
import tkinter as tk
from logging.handlers import RotatingFileHandler
from . import config

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
    if config.root and config.log_area and config.log_area.winfo_exists():
        def update_log_on_gui():
            if config.log_area.winfo_exists():
                config.log_area.config(state=tk.NORMAL)
                timestamp = time.strftime('%H:%M:%S')
                config.log_area.insert(tk.END, f"{timestamp} - {message}\n")
                config.log_area.see(tk.END)
                config.log_area.config(state=tk.DISABLED)
        try:
            config.root.after(0, update_log_on_gui)
        except tk.TclError:
            pass 