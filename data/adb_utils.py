# -*- coding: utf-8 -*-
import time
import cv2
import numpy as np
import random
import sys
import logging
import subprocess
import shutil
import traceback
from PIL import Image, ImageTk
from tkinter import messagebox, filedialog
import tkinter as tk

try:
    from ppadb.client import Client as AdbClient
except ImportError:
    print("Lỗi: Không tìm thấy thư viện pure-python-adb.")
    print("Vui lòng cài đặt: pip install pure-python-adb")
    sys.exit()

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


from . import config
from .logger import log_message
from .board_state import get_board_state_cv

def get_connected_devices_with_names():
    """Lấy danh sách các thiết bị ADB đang kết nối và trả về dưới dạng list of tuples (serial, model_name)."""
    devices_info = []
    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        devices_ppadb = client.devices()
        if devices_ppadb:
            for dev in devices_ppadb:
                try:
                    model = dev.shell("getprop ro.product.model").strip()
                    serial = dev.serial
                    devices_info.append((serial, model if model else "Unknown"))
                except Exception:
                    if dev and dev.serial:
                        devices_info.append((dev.serial, "Unknown"))
        return devices_info
    except Exception as e:
        log_message(f"Lỗi khi lấy danh sách thiết bị: {e}", level=logging.ERROR)
        return [] # Trả về list rỗng nếu có lỗi

def connect_to_selected_device():
    """Kết nối đến thiết bị ADB đã chọn trong combobox và khởi tạo u2_device."""
    if not config.device_selection_var:
        log_message("Lỗi: device_selection_var chưa được khởi tạo.", level=logging.ERROR)
        return False
        
    selected_device_display_name = config.device_selection_var.get()
    if not selected_device_display_name:
        log_message("Chưa chọn thiết bị ADB từ combobox.", level=logging.WARNING)
        messagebox.showwarning("Thiếu Thiết Bị", "Vui lòng chọn một thiết bị ADB từ danh sách.")
        return False

    selected_serial = None
    try:
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

    if config.u2_device:
        log_message(f"Ngắt kết nối uiautomator2 hiện tại (nếu có) để kết nối lại với {selected_serial}.", level=logging.DEBUG)
        config.u2_device = None 

    log_message(f"Đang kết nối với thiết bị đã chọn: {selected_serial} (từ '{selected_device_display_name}')", level=logging.INFO)
    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        device_to_connect = client.device(selected_serial)
        
        if device_to_connect:
            config.adb_device = device_to_connect
            log_message(f"Đã kết nối ADB (ppadb) thành công với: {config.adb_device.serial}", level=logging.INFO)
            
            if u2:
                try:
                    config.u2_device = u2.connect(selected_serial)
                    log_message(f"Đã kết nối uiautomator2 thành công với: {selected_serial}", level=logging.INFO)
                except Exception as e_u2:
                    log_message(f"Lỗi kết nối uiautomator2: {e_u2}", level=logging.ERROR)
                    config.u2_device = None
            return True
        else:
            log_message(f"Không tìm thấy thiết bị ADB với serial: {selected_serial}", level=logging.ERROR)
            return False

    except Exception as e:
        log_message(f"Lỗi kết nối ADB: {e}", level=logging.ERROR)
        return False

def connect_adb_device():
    if config.adb_device:
        try:
            config.adb_device.shell("echo test > /dev/null")
            return True
        except Exception:
            log_message("Mất kết nối ADB (ppadb), đang thử kết nối lại...", level=logging.WARNING)
            config.adb_device = None
            config.u2_device = None # Reset u2 nếu ppadb mất

    log_message("Đang tìm thiết bị ADB (sử dụng ppadb)...", level=logging.INFO)
    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        devices = client.devices()
        if not devices:
            log_message("Không tìm thấy thiết bị ADB nào (ppadb).", level=logging.ERROR)
            messagebox.showerror("Lỗi ADB", "Không tìm thấy thiết bị ADB. Hãy đảm bảo điện thoại đã kết nối và bật USB Debugging.")
            config.adb_device = None
            return False
        config.adb_device = devices[0]
        log_message(f"Đã kết nối ADB (ppadb) thành công với thiết bị: {config.adb_device.serial}", level=logging.INFO)
        return True
    except ConnectionRefusedError:
        log_message("Lỗi: Không thể kết nối tới ADB server (ppadb). ADB server chưa chạy?", level=logging.ERROR)
        messagebox.showerror("Lỗi ADB", "Không thể kết nối tới ADB server. Hãy đảm bảo ADB server đang chạy.")
        config.adb_device = None
        return False
    except Exception as e:
        log_message(f"Lỗi không xác định khi kết nối ADB (ppadb): {e}", level=logging.ERROR)
        messagebox.showerror("Lỗi ADB", f"Lỗi kết nối ADB (ppadb) không xác định:\n{e}")
        config.adb_device = None
        return False

def adb_screencap():
    if not u2:
        log_message("Lỗi: Thiếu thư viện uiautomator2. Không thể chụp màn hình.", level=logging.ERROR)
        return None
    if not config.u2_device:
        if config.is_running:
             log_message("Lỗi: Chưa kết nối uiautomator2 để chụp màn hình.", level=logging.ERROR)
        return None
    try:
        t_start_ss = time.monotonic()
        pil_image = config.u2_device.screenshot(format="pillow")
        ss_time = time.monotonic() - t_start_ss
        if pil_image is None:
             log_message("uiautomator2 screenshot trả về None.", level=logging.WARNING)
             return None
        t_start_resize = time.monotonic()
        try:
             resized_image = pil_image.resize((config.DESIGN_WIDTH, config.DESIGN_HEIGHT), Image.Resampling.LANCZOS)
        except AttributeError:
             resized_image = pil_image.resize((config.DESIGN_WIDTH, config.DESIGN_HEIGHT), Image.LANCZOS)
        resize_time = time.monotonic() - t_start_resize
        return resized_image
    except Exception as e:
        log_message(f"Lỗi khi chụp màn hình uiautomator2: {e}", level=logging.ERROR)
        err_str = str(e).lower()
        if "adbconnectionreseterror" in err_str or "disconnected" in err_str or "jsonrpcerror" in err_str or "socket connection broken" in err_str:
            log_message("Kết nối uiautomator2 có thể đã bị ngắt. Sẽ thử kết nối lại.", level=logging.WARNING)
            config.u2_device = None
        return None

def click_at(x, y):
    if not config.adb_device:
        log_message("Trong click_at: adb_device is None. Thử kết nối lại thiết bị đã chọn...", level=logging.WARNING)
        if not connect_to_selected_device():
            log_message("Trong click_at: Vẫn không kết nối được ADB. Click thất bại.", level=logging.ERROR)
            return
        else:
            log_message("Trong click_at: Kết nối lại ADB thành công. Tiếp tục click.", level=logging.INFO)
    
    if not config.adb_device:
        log_message("Lỗi: Không có thiết bị ADB sau khi thử kết nối lại trong click_at.", level=logging.ERROR)
        return

    if x is None or y is None or x < 0 or y < 0:
        log_message(f"Lỗi: Tọa độ click không hợp lệ ({x}, {y}).", level=logging.ERROR)
        return
    x_int, y_int = int(round(x)), int(round(y))
    try:
        command = f"input tap {x_int} {y_int}"
        config.adb_device.shell(command)
    except Exception as e:
        log_message(f"Lỗi khi thực hiện ADB tap tại ({x_int}, {y_int}): {e}", level=logging.ERROR)
        if "device offline" in str(e).lower() or "connection reset" in str(e).lower():
             log_message("Thiết bị ADB offline/reset trong click_at. Thử kết nối lại thiết bị ĐÃ CHỌN...", level=logging.WARNING)
             if not connect_to_selected_device():
                 log_message("Click_at: Thất bại kết nối lại thiết bị đã chọn sau lỗi. Click có thể không hoạt động.", level=logging.ERROR)
    
def pick_coordinate_and_color():
    if config.is_running:
        messagebox.showwarning("Đang chạy", "Vui lòng dừng auto trước khi chọn tọa độ.")
        return

    if not connect_to_selected_device():
        return

    if not config.u2_device:
        log_message("Chọn tọa độ: Không thể kết nối uiautomator2 với thiết bị đã chọn. Vui lòng kiểm tra lại.", level=logging.ERROR)
        messagebox.showerror("Lỗi uiautomator2", "Không thể kết nối uiautomator2 với thiết bị đã chọn.\n"
                                         "Hãy đảm bảo thiết bị hỗ trợ và uiautomator2 đã được khởi tạo (python -m uiautomator2 init).")
        return

    log_message("Đang chụp màn hình để chọn tọa độ (sử dụng uiautomator2 đã kết nối)...", level=logging.INFO)
    screenshot_pil = adb_screencap()
    if screenshot_pil is None:
        messagebox.showerror("Lỗi", "Không thể chụp ảnh màn hình từ thiết bị.")
        return

    img_w, img_h = screenshot_pil.width, screenshot_pil.height
    win = tk.Toplevel(config.root)
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

    start_x = start_y = end_x = end_y = None
    dragging = False
    rect_id = None

    def on_mouse_down(event):
        nonlocal start_x, start_y, dragging
        start_x, start_y = event.x, event.y
        dragging = False
        
    def on_mouse_move(event):
        nonlocal start_x, start_y, end_x, end_y, dragging, rect_id
        if start_x is not None and start_y is not None:
            current_x, current_y = event.x, event.y
            if not dragging and (abs(current_x - start_x) > 5 or abs(current_y - start_y) > 5):
                dragging = True
            
            if dragging:
                end_x, end_y = current_x, current_y
                if rect_id is not None:
                    canvas.delete(rect_id)
                rect_id = canvas.create_rectangle(start_x, start_y, end_x, end_y, outline="red", width=2)

    def on_mouse_up(event):
        nonlocal start_x, start_y, end_x, end_y, dragging, rect_id
        
        if not dragging:
            click_x_disp, click_y_disp = event.x, event.y
            real_x, real_y = int(click_x_disp / scale), int(click_y_disp / scale)
            try:
                pixel_color = screenshot_pil.getpixel((real_x, real_y))
                r, g, b = pixel_color[:3] if isinstance(pixel_color, tuple) else (pixel_color, pixel_color, pixel_color)
                result_msg = f"Tọa độ gốc: ({real_x}, {real_y})\nMàu RGB: ({r}, {g}, {b})"
                log_message(f"Đã chọn điểm: {result_msg}", level=logging.INFO)
                if messagebox.askyesno("Kết quả", f"{result_msg}\n\nBạn có muốn copy thông tin này?", parent=win):
                    try:
                        config.root.clipboard_clear()
                        config.root.clipboard_append(f"X={real_x}, Y={real_y}, RGB=({r}, {g}, {b})")
                        log_message("Đã copy vào clipboard.", level=logging.INFO)
                    except tk.TclError:
                        log_message("Không thể truy cập clipboard.", level=logging.WARNING)
            except IndexError:
                messagebox.showerror("Lỗi", "Không thể lấy màu pixel.", parent=win)
            except Exception as e:
                 messagebox.showerror("Lỗi", f"Có lỗi xảy ra: {e}", parent=win)
        
        else:
            if end_x is None or end_y is None:
                end_x, end_y = event.x, event.y
            
            sx, sy = min(start_x, end_x), min(start_y, end_y)
            ex, ey = max(start_x, end_x), max(start_y, end_y)
            
            real_sx, real_sy = int(sx / scale), int(sy / scale)
            real_ex, real_ey = int(ex / scale), int(ey / scale)
            
            try:
                cropped_img = screenshot_pil.crop((real_sx, real_sy, real_ex, real_ey))
                
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".png",
                    filetypes=[("PNG files", "*.png"), ("All Files", "*.*")],
                    title="Lưu ảnh đã chụp",
                    parent=win
                )
                
                if file_path:
                    cropped_img.save(file_path)
                    log_message(f"Đã lưu ảnh vào: {file_path}", level=logging.INFO)
                    messagebox.showinfo("Thành công", f"Đã lưu ảnh vào: {file_path}", parent=win)
            except Exception as e:
                log_message(f"Lỗi khi lưu ảnh: {e}", level=logging.ERROR)
                messagebox.showerror("Lỗi", f"Không thể lưu ảnh: {e}", parent=win)
        
        if rect_id is not None:
            canvas.delete(rect_id)
        start_x = start_y = end_x = end_y = None
        dragging = False
        rect_id = None

    canvas.bind("<ButtonPress-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_move)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)
    
    win.transient(config.root)
    win.focus_set()
    
    def on_window_close():
        win.destroy()
        
    win.protocol("WM_DELETE_WINDOW", on_window_close)
    win.wm_attributes("-toolwindow", 0)
    
    win_w, win_h = disp_w, disp_h + 50
    x_pos = config.root.winfo_x() + (config.root.winfo_width() - win_w) // 2
    y_pos = config.root.winfo_y() + (config.root.winfo_height() - win_h) // 2
    win.geometry(f"{win_w}x{win_h}+{max(0, x_pos)}+{max(0, y_pos)}")
    
    win.wait_window()

def click_and_verify(r, c, player_color, retries=2, delay=0.25, click_random_range=2):
    if not config.cell_centers or r >= len(config.cell_centers) or c >= len(config.cell_centers[r]):
        log_message(f"Lỗi: cell_centers không hợp lệ hoặc tọa độ ({r},{c}) ngoài phạm vi trong click_and_verify.", level=logging.ERROR)
        return False

    for attempt in range(retries + 1):
        base_x, base_y = config.cell_centers[r][c]
        
        offset_x = random.randint(-click_random_range, click_random_range)
        offset_y = random.randint(-click_random_range, click_random_range)
        click_x_final = base_x + offset_x
        click_y_final = base_y + offset_y

        log_message(f"ClickVerify (Thử {attempt + 1}/{retries + 1}): Click tại ({click_x_final},{click_y_final}) cho ô ({r},{c})", level=logging.DEBUG)
        click_at(click_x_final, click_y_final)
        time.sleep(delay)

        screenshot_after_click = adb_screencap()
        if screenshot_after_click is None:
            log_message(f"ClickVerify (Thử {attempt + 1}): Không chụp được màn hình sau click. Tiếp tục...", level=logging.WARNING)
            if attempt < retries: time.sleep(delay * 2)
            continue

        cv_img_after_click = cv2.cvtColor(np.array(screenshot_after_click), cv2.COLOR_RGB2BGR)
        board_state_after_click, _, _ = get_board_state_cv(cv_img_after_click)

        if board_state_after_click and r < len(board_state_after_click) and c < len(board_state_after_click[r]):
            if board_state_after_click[r][c] == player_color:
                log_message(f"ClickVerify (Thử {attempt + 1}): Xác nhận thành công quân {player_color} tại ({r},{c}).", level=logging.INFO)
                config.last_known_board_state_for_opponent_move = [row[:] for row in board_state_after_click]
                log_message(f"ClickVerify: Đã cập nhật last_known_board_state sau nước đi của AI tại ({r},{c}).", level=logging.DEBUG)
                return True
            else:
                log_message(f"ClickVerify (Thử {attempt + 1}): Ô ({r},{c}) là '{board_state_after_click[r][c]}', mong đợi '{player_color}'.", level=logging.DEBUG)
        else:
            log_message(f"ClickVerify (Thử {attempt + 1}): Không lấy được trạng thái ô ({r},{c}) sau click.", level=logging.WARNING)
        
        if attempt < retries:
            log_message(f"ClickVerify (Thử {attempt + 1}): Thất bại, chuẩn bị thử lại...", level=logging.DEBUG)
            time.sleep(delay)
            
    log_message(f"ClickVerify: Thất bại sau {retries + 1} lần thử cho ô ({r},{c}), màu {player_color}.", level=logging.WARNING)
    return False

def view_device_screen():
    """Mở scrcpy để xem màn hình thiết bị đã chọn."""
    if not config.device_selection_var or not config.device_selection_var.get():
        messagebox.showerror("Lỗi", "Chưa chọn thiết bị ADB.")
        return
        
    selected_device_display = config.device_selection_var.get()
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
        log_message(f"Đang mở scrcpy ({scrcpy_executable}) cho thiết bị: {device_serial}", level=logging.INFO)
        subprocess.Popen([scrcpy_executable, "-s", device_serial])
    except FileNotFoundError:
        messagebox.showerror("Lỗi", f"Không tìm thấy file scrcpy tại: {scrcpy_executable}. Vui lòng kiểm tra lại.")
        log_message(f"Lỗi FileNotFoundError khi mở scrcpy: {scrcpy_executable}", level=logging.ERROR)
    except Exception as e_scrcpy:
        messagebox.showerror("Lỗi", f"Không thể mở scrcpy: {str(e_scrcpy)}")
        log_message(f"Lỗi khi mở scrcpy: {str(e_scrcpy)}", level=logging.ERROR)

def refresh_device_list():
    """Làm mới danh sách thiết bị ADB trong combobox. 
    Lưu ý: Logic chính đã được chuyển sang gui_components.py, hàm này có thể không còn cần thiết.
    """
    # DEPRECATED or to be used for non-GUI refresh logic if any.
    pass 