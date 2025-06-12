# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import scrolledtext, messagebox, font as tkfont, ttk, filedialog
import threading
import os
import sys
import logging
import importlib

# Thêm đường dẫn gốc của dự án vào sys.path để import các module khác
# Điều này quan trọng khi chạy main.py từ thư mục gốc
try:
    # Lấy đường dẫn tuyệt đối của thư mục chứa file này (data)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Lấy đường dẫn của thư mục cha (thư mục gốc của dự án)
    project_root = os.path.dirname(current_dir)
    # Thêm thư mục gốc vào sys.path nếu chưa có
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
except NameError:
    # Nếu __file__ không được định nghĩa (ví dụ: trong một số môi trường REPL)
    # chúng ta giả định rằng script được chạy từ thư mục gốc.
    if '.' not in sys.path:
        sys.path.insert(0, '.')


from data.config import *
import data.config as config
from data.logger import log_message
from data.adb_utils import (
    connect_to_selected_device,
    view_device_screen,
    pick_coordinate_and_color,
    get_connected_devices_with_names
)
from data.experience import save_game_experience, load_game_experience, analyze_game_experience, update_weights_from_experience, format_game_experience, build_opening_book_statistics

# --- KHAI BÁO BIẾN GIAO DIỆN ---
root = None
log_widget = None
device_list_combobox = None
start_button = None
stop_button = None
stop_after_game_button = None
refresh_button = None
view_screen_button = None
pick_coords_button = None
reset_stats_button = None
target_combobox = None
win_label = None
loss_label = None
draw_label = None
win_rate_label = None
total_games_label = None
ai_color_label = None
status_label = None
current_move_label = None
last_move_label = None
win_probability_label = None
progress_bar = None
progress_label = None
log_frame = None

# Biến Tkinter
selected_device_var = None
selected_target_var = None
stop_after_current_game_var = None
use_custom_skin_var = None
use_multiprocessing_var = None
display_log_var = None

# --- WRAPPER FUNCTIONS (để gọi code từ auto_loop một cách an toàn) ---
def start_auto_wrapper():
    """Tải module auto_loop, gom các widget và gọi hàm start_auto."""
    auto_loop = importlib.import_module("data.auto_loop")
    
    gui_widgets = auto_loop.GuiWidgets()
    gui_widgets.root = root
    gui_widgets.ai_color_label = ai_color_label
    gui_widgets.current_move_label = current_move_label
    gui_widgets.last_move_label = last_move_label
    gui_widgets.win_probability_label = win_probability_label
    gui_widgets.status_label = status_label
    gui_widgets.progress_bar = progress_bar
    gui_widgets.progress_label = progress_label
    gui_widgets.update_stats_display = update_stats_display
    gui_widgets.update_button_states = update_button_states
    gui_widgets.stop_after_current_game_var = stop_after_current_game_var

    auto_loop.start_auto(gui_widgets)

def stop_auto_wrapper():
    """Tải module auto_loop và gọi hàm stop_auto."""
    auto_loop = importlib.import_module("data.auto_loop")
    auto_loop.stop_auto()

def request_stop_after_game_wrapper():
    """Tải module auto_loop và gọi hàm request_stop_after_game."""
    auto_loop = importlib.import_module("data.auto_loop")
    auto_loop.request_stop_after_game()

# --- GUI SETUP FUNCTIONS ---
def setup_gui_variables():
    """Khởi tạo tất cả các biến Tkinter và gán chúng vào module config."""
    global selected_device_var, selected_target_var, stop_after_current_game_var
    global use_custom_skin_var, use_multiprocessing_var, display_log_var
    
    # Tạo các biến Tkinter
    selected_device_var = tk.StringVar()
    selected_target_var = tk.StringVar(value=DEFAULT_TARGET_NAME)
    stop_after_current_game_var = tk.BooleanVar(value=False)
    use_custom_skin_var = tk.BooleanVar(value=True)
    use_multiprocessing_var = tk.BooleanVar(value=True)
    display_log_var = tk.BooleanVar(value=True)

    # Gán các biến vừa tạo vào module config để các module khác có thể truy cập
    config.device_selection_var = selected_device_var
    config.target_selection_var = selected_target_var
    config.stop_after_current_game_var = stop_after_current_game_var
    config.use_multiprocessing_var = use_multiprocessing_var


def on_target_selected_internal(event=None):
    """Cập nhật biến toàn cục khi người dùng chọn mục tiêu mới."""
    config.selected_target_name = selected_target_var.get()
    log_message(f"Đã chọn mục tiêu: {config.selected_target_name}", logging.INFO)

def refresh_device_list():
    """Làm mới danh sách thiết bị trong combobox."""
    log_message("Làm mới danh sách thiết bị...", logging.INFO)
    devices = get_connected_devices_with_names()
    device_list = [f"{name} ({serial})" for serial, name in devices]
    
    if not device_list:
        device_list.append("Không tìm thấy thiết bị")
        selected_device_var.set("Không tìm thấy thiết bị")
        connect_button['state'] = 'disabled'
    else:
        connect_button['state'] = 'normal'

    device_list_combobox['values'] = device_list
    
    # Cố gắng chọn lại thiết bị đang được chọn hoặc chọn thiết bị đầu tiên
    current_selection = selected_device_var.get()
    if current_selection in device_list:
        device_list_combobox.set(current_selection)
    elif device_list:
        device_list_combobox.current(0)
    
    log_message(f"Tìm thấy {len(devices)} thiết bị.", logging.INFO)
    update_button_states()

def reset_stats():
    """Reset lại các chỉ số thắng/thua/hòa."""
    global win_count, loss_count, draw_count
    if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn reset lại chỉ số thống kê không?"):
        win_count = 0
        loss_count = 0
        draw_count = 0
        update_stats_display()
        log_message("Đã reset chỉ số thống kê.", logging.INFO)
        
def update_button_states():
    """Cập nhật trạng thái (enable/disable) của các nút bấm."""
    is_device_connected = config.adb_device is not None
    
    start_button['state'] = 'normal' if is_device_connected and not config.is_running else 'disabled'
    stop_button['state'] = 'normal' if config.is_running else 'disabled'
    stop_after_game_button['state'] = 'normal' if config.is_running else 'disabled'
    
    view_screen_button['state'] = 'normal' if is_device_connected else 'disabled'
    pick_coords_button['state'] = 'normal' if is_device_connected else 'disabled'
    connect_button['state'] = 'disabled' if config.is_running else 'normal'
    device_list_combobox['state'] = 'readonly' if not config.is_running else 'disabled'
    refresh_button['state'] = 'normal' if not config.is_running else 'disabled'
    
    if stop_after_current_game_var:
        is_waiting_to_stop = stop_after_current_game_var.get()
        stop_after_game_button.config(text="Dừng sau ván" + (" (Chờ...)" if is_waiting_to_stop else ""))


def update_stats_display():
    """Cập nhật các label hiển thị thống kê thắng/thua."""
    total_games = win_count + loss_count + draw_count
    win_rate = (win_count / total_games * 100) if total_games > 0 else 0

    win_label.config(text=f"Thắng: {win_count}")
    loss_label.config(text=f"Thua: {loss_count}")
    draw_label.config(text=f"Hòa: {draw_count}")
    total_games_label.config(text=f"Tổng số trận: {total_games}")
    win_rate_label.config(text=f"Tỉ lệ thắng: {win_rate:.1f}%")

def create_gui(main_root):
    """Tạo và sắp xếp các thành phần giao diện người dùng."""
    global root, log_widget, device_list_combobox, start_button, stop_button, \
           stop_after_game_button, refresh_button, view_screen_button, pick_coords_button, \
           reset_stats_button, target_combobox, connect_button, \
           win_label, loss_label, draw_label, win_rate_label, total_games_label, \
           ai_color_label, status_label, current_move_label, last_move_label, \
           win_probability_label, progress_bar, progress_label, log_frame

    root = main_root
    root.title("Reversi AI Bot")
    root.geometry("800x650")

    # --- STYLES ---
    style = ttk.Style()
    style.theme_use('clam')
    style.configure("TButton", padding=6, relief="flat", background="#cceeff")
    style.map("TButton", background=[('active', '#aaddff')])
    style.configure("TFrame", background="#f0f0f0")
    style.configure("TLabel", background="#f0f0f0", font=('Helvetica', 10))
    style.configure("Title.TLabel", font=('Helvetica', 12, 'bold'))
    style.configure("Stat.TLabel", font=('Helvetica', 10, 'bold'), foreground="#00529B")
    style.configure("TCombobox", padding=5)
    style.configure("TCheckbutton", background="#f0f0f0")

    main_frame = ttk.Frame(root, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Tách làm 2 cột chính
    left_frame = ttk.Frame(main_frame)
    left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    right_frame = ttk.Frame(main_frame)
    right_frame.grid(row=0, column=1, sticky="nsew")
    
    main_frame.grid_columnconfigure(0, weight=1)
    main_frame.grid_columnconfigure(1, weight=1)
    main_frame.grid_rowconfigure(0, weight=1)

    # --- LEFT FRAME ---
    
    # -- Control Frame --
    control_frame = ttk.LabelFrame(left_frame, text="Bảng điều khiển", padding="10")
    control_frame.pack(fill=tk.X, pady=(0, 10))

    # Device selection
    device_frame = ttk.Frame(control_frame)
    device_frame.pack(fill=tk.X, expand=True, pady=5)
    ttk.Label(device_frame, text="Thiết bị:").pack(side=tk.LEFT, padx=(0, 5))
    
    device_list_combobox = ttk.Combobox(device_frame, textvariable=selected_device_var, state='readonly', width=25)
    device_list_combobox.pack(side=tk.LEFT, expand=True, fill=tk.X)
    
    refresh_button = ttk.Button(device_frame, text="↻", command=refresh_device_list, width=3)
    refresh_button.pack(side=tk.LEFT, padx=(5, 0))

    connect_button = ttk.Button(device_frame, text="Kết nối", command=connect_to_selected_device)
    connect_button.pack(side=tk.LEFT, padx=(5, 0))

    # Target selection
    target_frame = ttk.Frame(control_frame)
    target_frame.pack(fill=tk.X, expand=True, pady=5, before=device_frame)
    ttk.Label(target_frame, text="Mục tiêu:").pack(side=tk.LEFT, padx=(0, 5))
    target_combobox = ttk.Combobox(target_frame, textvariable=selected_target_var, state='readonly', values=list(TARGET_OPTIONS.keys()))
    target_combobox.pack(side=tk.LEFT, expand=True, fill=tk.X)
    target_combobox.bind("<<ComboboxSelected>>", on_target_selected_internal)
    on_target_selected_internal() # Gọi lần đầu để khởi tạo

    # Action buttons
    action_frame = ttk.Frame(control_frame)
    action_frame.pack(fill=tk.X, expand=True, pady=10)
    
    start_button = ttk.Button(action_frame, text="Bắt đầu", command=start_auto_wrapper)
    start_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
    
    stop_button = ttk.Button(action_frame, text="Dừng Ngay", command=stop_auto_wrapper)
    stop_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

    stop_after_game_button = ttk.Button(action_frame, text="Dừng sau ván này", command=request_stop_after_game_wrapper)
    stop_after_game_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))

    # --- RIGHT FRAME ---
    
    # -- Status Frame --
    status_frame = ttk.LabelFrame(right_frame, text="Trạng thái & Thống kê", padding="10")
    status_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    status_frame.grid_columnconfigure(1, weight=1)

    # Status Labels
    ttk.Label(status_frame, text="Status:", style="Title.TLabel").grid(row=0, column=0, sticky="w", pady=2)
    status_label = ttk.Label(status_frame, text="Chưa kết nối", anchor="w", foreground="blue")
    status_label.grid(row=0, column=1, sticky="ew", padx=5)

    ttk.Label(status_frame, text="Màu quân AI:", style="Title.TLabel").grid(row=1, column=0, sticky="w", pady=2)
    ai_color_label = ttk.Label(status_frame, text="N/A", anchor="w")
    ai_color_label.grid(row=1, column=1, sticky="ew", padx=5)

    ttk.Label(status_frame, text="Nước đi AI:", style="Title.TLabel").grid(row=2, column=0, sticky="w", pady=2)
    current_move_label = ttk.Label(status_frame, text="N/A", anchor="w")
    current_move_label.grid(row=2, column=1, sticky="ew", padx=5)

    ttk.Label(status_frame, text="Win% AI:", style="Title.TLabel").grid(row=3, column=0, sticky="w", pady=2)
    win_probability_label = ttk.Label(status_frame, text="N/A", anchor="w")
    win_probability_label.grid(row=3, column=1, sticky="ew", padx=5)

    ttk.Label(status_frame, text="Nước đi cuối:", style="Title.TLabel").grid(row=4, column=0, sticky="w", pady=2)
    last_move_label = ttk.Label(status_frame, text="N/A", anchor="w")
    last_move_label.grid(row=4, column=1, sticky="ew", padx=5)
    
    # AI Search Progress
    ttk.Label(status_frame, text="AI Search:", style="Title.TLabel").grid(row=5, column=0, sticky="w", pady=2)
    progress_frame = ttk.Frame(status_frame)
    progress_frame.grid(row=5, column=1, sticky="ew", padx=5)
    progress_frame.grid_columnconfigure(0, weight=1)
    
    progress_bar = ttk.Progressbar(progress_frame, orient='horizontal', mode='determinate')
    progress_bar.grid(row=0, column=0, sticky="ew")
    progress_label = ttk.Label(progress_frame, text="0/0")
    progress_label.grid(row=0, column=1, sticky="w", padx=(5,0))


    # Stats Display
    stats_display_frame = ttk.Frame(status_frame)
    stats_display_frame.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10,0))
    stats_display_frame.grid_columnconfigure((0,1,2), weight=1)

    win_label = ttk.Label(stats_display_frame, text="Thắng: 0", style="Stat.TLabel", foreground="green")
    win_label.grid(row=0, column=0, sticky="w")
    loss_label = ttk.Label(stats_display_frame, text="Thua: 0", style="Stat.TLabel", foreground="red")
    loss_label.grid(row=0, column=1, sticky="w")
    draw_label = ttk.Label(stats_display_frame, text="Hòa: 0", style="Stat.TLabel", foreground="gray")
    draw_label.grid(row=0, column=2, sticky="w")

    total_games_label = ttk.Label(stats_display_frame, text="Tổng số trận: 0", style="Stat.TLabel")
    total_games_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5,0))
    win_rate_label = ttk.Label(stats_display_frame, text="Tỉ lệ thắng: 0.0%", style="Stat.TLabel")
    win_rate_label.grid(row=1, column=2, sticky="w", pady=(5,0))

    reset_stats_button = ttk.Button(stats_display_frame, text="Reset Thống Kê", command=reset_stats, width=15)
    reset_stats_button.grid(row=2, column=0, columnspan=3, pady=(10,0))

    # -- Utility Frame --
    utility_frame = ttk.LabelFrame(right_frame, text="Tiện ích", padding="10")
    utility_frame.pack(fill=tk.X, pady=(0, 10))
    utility_frame.grid_columnconfigure((0,1), weight=1)

    view_screen_button = ttk.Button(utility_frame, text="Xem màn hình", command=view_device_screen)
    view_screen_button.grid(row=0, column=0, sticky="ew", padx=(0,5))
    
    pick_coords_button = ttk.Button(utility_frame, text="Lấy tọa độ & màu", command=pick_coordinate_and_color)
    pick_coords_button.grid(row=0, column=1, sticky="ew", padx=(5,0))


    # -- Settings Frame --
    settings_frame = ttk.LabelFrame(left_frame, text="Cài đặt", padding="10")
    settings_frame.pack(fill=tk.X, pady=(0, 10))

    use_multiprocessing_var.set(True) # Bật mặc định
    use_multiprocessing_check = ttk.Checkbutton(settings_frame, text="Sử dụng đa luồng (AI nhanh hơn)", var=use_multiprocessing_var)
    use_multiprocessing_check.pack(anchor='w')

    use_custom_skin_var.set(True) # Bật mặc định
    use_custom_skin_check = ttk.Checkbutton(settings_frame, text="Sử dụng nhận diện skin tùy chỉnh", var=use_custom_skin_var)
    use_custom_skin_check.pack(anchor='w')

    display_log_var.set(True) # Bật mặc định
    display_log_check = ttk.Checkbutton(settings_frame, text="Hiển thị log", var=display_log_var, command=toggle_log_display)
    display_log_check.pack(anchor='w')


    # --- LOG FRAME (dưới cùng) ---
    log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
    log_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
    main_frame.grid_rowconfigure(1, weight=1) # Cho phép log frame co giãn

    log_widget = scrolledtext.ScrolledText(log_frame, state='disabled', height=10, width=80, wrap=tk.WORD, font=("Consolas", 9))
    log_widget.pack(fill=tk.BOTH, expand=True)

    # --- Initial State ---
    update_button_states()
    update_stats_display()
    refresh_device_list() # Lấy danh sách thiết bị khi khởi động

def toggle_log_display():
    """Ẩn hoặc hiện khung log."""
    if display_log_var.get():
        log_frame.grid()
    else:
        log_frame.grid_remove()

def on_closing():
    """Hỏi người dùng trước khi đóng cửa sổ."""
    auto_loop = importlib.import_module("data.auto_loop")
    if config.is_running:
        if messagebox.askokcancel("Thoát", "Bot đang chạy. Bạn có chắc muốn thoát không?"):
            auto_loop.stop_auto() # Cố gắng dừng bot một cách an toàn
            root.destroy()
    else:
        root.destroy() 