# -*- coding: utf-8 -*-
import threading
import time
import traceback
import sys
import os
import logging
import cv2
import numpy as np

try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
except NameError:
    if '.' not in sys.path:
        sys.path.insert(0, '.')

from data.config import *
import data.config as config
from data.logger import log_message
from data.pixel_utils import check_pixel_match
from data.board_state import get_board_state_cv, detect_ai_color_cv, calculate_board_geometry
from data.ai import find_best_move, compute_win_probability
from data.adb_utils import adb_screencap, click_at, click_and_verify
from data.experience import save_game_experience

# --- GUI WIDGETS (Sẽ được truyền vào từ gui_components) ---
# Khai báo để tránh lỗi "not defined" và để dễ theo dõi
class GuiWidgets:
    def __init__(self):
        self.root = None
        self.ai_color_label = None
        self.current_move_label = None
        self.last_move_label = None
        self.win_probability_label = None
        self.status_label = None
        self.progress_bar = None
        self.progress_label = None
        self.update_stats_display = None
        self.update_button_states = None
        self.stop_after_current_game_var = None

# Biến toàn cục để giữ các widgets
gui = GuiWidgets()

def initialize_new_game_state(cv_img_param):
    """
    Khởi tạo hoặc reset trạng thái cho một ván game mới.
    Hàm này được gọi khi bắt đầu một ván mới.
    """
    log_message("--- BẮT ĐẦU VÁN MỚI ---", logging.WARNING)

    # Sử dụng global để thay đổi các biến toàn cục
    config.current_game_ai_color = None
    config.ai_color_locked_this_game = False
    config.ai_moved = False
    config.current_game_moves = []
    config.last_known_board_state_for_opponent_move = None
    config.waiting_room_enter_time = None

    # Cập nhật GUI
    if gui.root:
        gui.root.after(0, lambda: gui.ai_color_label.config(text="Đang xác định..."))
        gui.root.after(0, lambda: gui.current_move_label.config(text="N/A"))
        gui.root.after(0, lambda: gui.last_move_label.config(text="N/A"))
        gui.root.after(0, lambda: gui.win_probability_label.config(text="N/A"))

    # Xác định màu quân AI cho ván này
    # Thử vài lần nếu lần đầu không thành công
    for i in range(3):
        log_message(f"Đang xác định màu quân AI (lần {i+1})...", logging.INFO)
        color = detect_ai_color_cv(cv_img_param)
        if color:
            config.current_game_ai_color = color
            log_message(f"AI xác định đi quân '{'Đen' if color == 'B' else 'Trắng'}'.", logging.INFO)
            if gui.root:
                gui.root.after(0, lambda: gui.ai_color_label.config(text=f"{'Đen' if color == 'B' else 'Trắng'}"))
            break
        else:
            log_message("Không xác định được màu của AI, thử lại sau 0.5 giây.", logging.INFO)
            time.sleep(0.5)
            # Chụp lại màn hình để thử lại
            screenshot = adb_screencap()
            if screenshot:
                cv_img_param = screenshot
            else:
                log_message("Không thể chụp màn hình để xác định lại màu AI.", logging.ERROR)
                return False # Báo hiệu thất bại
    
    if not config.current_game_ai_color:
        log_message("Không thể xác định màu quân AI sau nhiều lần thử. Hủy ván game.", logging.ERROR)
        return False

    # Lấy trạng thái bàn cờ ban đầu
    initial_board_state, _ = get_board_state_cv(cv_img_param)
    config.last_known_board_state_for_opponent_move = initial_board_state
    
    return True # Báo hiệu thành công

def check_and_log_waiting_room_pixel(cv_img):
    """Kiểm tra pixel của phòng chờ và ghi log nếu cần."""
    try:
        # Lấy thông tin mục tiêu hiện tại từ config
        target_info = config.TARGET_OPTIONS.get(config.selected_target_name, {})
        if not target_info:
            return # Không có mục tiêu hợp lệ

        pixel_x = target_info.get("X")
        pixel_y = target_info.get("Y")
        pixel_color = target_info.get("RGB")
        pixel_tolerance = target_info.get("TOLERANCE")

        # Kiểm tra pixel
        if check_pixel_match(cv_img, pixel_x, pixel_y, pixel_color, pixel_tolerance):
            if config.waiting_room_enter_time is None:
                config.waiting_room_enter_time = time.time()
                log_message(f"Đã vào phòng chờ '{config.selected_target_name}'. Bắt đầu đếm thời gian.", logging.INFO)
        else:
            if config.waiting_room_enter_time is not None:
                elapsed_time = time.time() - config.waiting_room_enter_time
                log_message(f"Đã rời phòng chờ. Thời gian chờ: {elapsed_time:.2f} giây.", logging.INFO)
                config.waiting_room_enter_time = None # Reset lại khi không còn ở phòng chờ
    except Exception as e:
        log_message(f"Lỗi khi kiểm tra pixel phòng chờ: {e}", logging.ERROR)


def auto_play_loop():
    """Vòng lặp chính để tự động chơi game."""
    last_check_time = 0
    in_game_state = False # Cờ để xác định có đang trong ván hay không
    
    while config.is_running:
        try:
            # Điều chỉnh tốc độ vòng lặp
            time.sleep(0.1) 
            
            # Lấy ảnh màn hình
            cv_img = adb_screencap()
            if cv_img is None:
                log_message("Lỗi: Không thể chụp màn hình, kiểm tra kết nối.", logging.ERROR)
                time.sleep(1)
                continue

            # --- KIỂM TRA CÁC TRẠNG THÁI NGOÀI GAME ---
            # 1. Kiểm tra màn hình chờ (menu chính)
            check_and_log_waiting_room_pixel(cv_img)
            
            # 2. Kiểm tra nút "Thoát" hoặc "Trở về" sau game
            if check_pixel_match(cv_img, config.ENDGAME_PIXEL_X, config.ENDGAME_PIXEL_Y, config.ENDGAME_PIXEL_COLOR, config.ENDGAME_PIXEL_TOLERANCE):
                log_message("Phát hiện màn hình kết thúc game, nhấn trở về...", logging.INFO)
                click_at(config.ENDGAME_CLICK_X, config.ENDGAME_CLICK_Y)
                in_game_state = False # Kết thúc trạng thái trong game
                time.sleep(1) 
                continue

            # 3. Kiểm tra lỗi mạng
            if check_pixel_match(cv_img, config.NETWORK_ERROR_PIXEL_X, config.NETWORK_ERROR_PIXEL_Y, config.NETWORK_ERROR_PIXEL_COLOR, config.NETWORK_ERROR_PIXEL_TOLERANCE):
                log_message("Phát hiện lỗi mạng, nhấn OK...", logging.WARNING)
                click_at(config.NETWORK_ERROR_CLICK_X, config.NETWORK_ERROR_CLICK_Y)
                time.sleep(1)
                continue
            
            # 4. Tìm trận mới nếu đang ở màn hình menu
            target_info = config.TARGET_OPTIONS.get(config.selected_target_name)
            if target_info and check_pixel_match(cv_img, target_info["X"], target_info["Y"], target_info["RGB"], target_info["TOLERANCE"]):
                if not in_game_state:
                    log_message(f"Đang ở menu, tìm trận mới tại '{config.selected_target_name}'...", logging.INFO)
                    click_at(target_info["X"], target_info["Y"])
                    time.sleep(2) # Chờ vào game
                    # Chụp lại màn hình để kiểm tra ngay lập tức
                    cv_img = adb_screencap()
                    if cv_img is None: continue
                
            # --- LOGIC XỬ LÝ TRONG GAME ---
            is_ai_turn = check_pixel_match(cv_img, config.TURN_PIXEL_X, config.TURN_PIXEL_Y, config.TURN_PIXEL_COLOR, config.TURN_PIXEL_TOLERANCE)
            is_opponent_turn = check_pixel_match(cv_img, config.OPPONENT_TURN_PIXEL_X, config.OPPONENT_TURN_PIXEL_Y, config.OPPONENT_TURN_PIXEL_COLOR, config.OPPONENT_TURN_PIXEL_TOLERANCE)

            # Nếu không phải lượt của ai và cũng không phải của đối thủ, có thể là màn hình kết thúc game
            if not is_ai_turn and not is_opponent_turn:
                # Kiểm tra thắng/thua chỉ khi đang trong game
                if in_game_state:
                    game_ended = False
                    result = None
                    if check_pixel_match(cv_img, config.WIN_PIXEL_X, config.WIN_PIXEL_Y, config.WIN_PIXEL_COLOR, config.WIN_PIXEL_TOLERANCE):
                        config.win_count += 1
                        result = "win"
                        log_message("===> THẮNG! <===", logging.WARNING)
                        game_ended = True
                    elif check_pixel_match(cv_img, config.LOSS_PIXEL_X, config.LOSS_PIXEL_Y, config.LOSS_PIXEL_COLOR, config.LOSS_PIXEL_TOLERANCE):
                        config.loss_count += 1
                        result = "loss"
                        log_message("===> THUA! <===", logging.WARNING)
                        game_ended = True

                    if game_ended:
                        log_message(f"Tỉ số hiện tại: Thắng {config.win_count} - Thua {config.loss_count} - Hòa {config.draw_count}", logging.INFO)
                        if gui.root:
                           gui.root.after(0, gui.update_stats_display)
                        
                        # Lưu kinh nghiệm ván đấu
                        if config.current_game_ai_color and config.current_game_moves:
                            save_game_experience(config.current_game_ai_color, result, config.current_game_moves)

                        # Reset trạng thái game cho ván mới
                        in_game_state = False 
                        
                        # Kiểm tra nếu có yêu cầu dừng sau ván này
                        if config.stop_after_current_game:
                            log_message("Đã hoàn thành ván game, dừng bot theo yêu cầu.", logging.INFO)
                            stop_auto() # Dùng hàm stop_auto để dừng hẳn
                            break # Thoát khỏi vòng lặp

                        time.sleep(2) # Chờ một chút trước khi tìm cách thoát ra menu
                        continue
            else:
                # Nếu phát hiện một trong hai bên có lượt, ta đang ở trong game
                if not in_game_state:
                    in_game_state = True
                    if not initialize_new_game_state(cv_img):
                        # Nếu không khởi tạo được game, dừng vòng lặp này và thử lại
                        log_message("Lỗi khởi tạo game, sẽ thử lại...", logging.ERROR)
                        time.sleep(2)
                        continue
                
            # Xử lý khi đến lượt AI
            if is_ai_turn and config.current_game_ai_color:
                if not config.ai_moved: # Chỉ thực hiện nếu AI chưa đi nước này
                    log_message("Đến lượt AI.", logging.INFO)
                    
                    board_state, piece_counts = get_board_state_cv(cv_img)
                    
                    if board_state:
                        # Tìm nước đi tốt nhất
                        best_move, best_score = find_best_move(board_state, config.current_game_ai_color)

                        if best_move:
                            r, c = best_move
                            log_message(f"AI quyết định đi tại ({r}, {c}). Score: {best_score:.2f}", logging.INFO)
                            if gui.root:
                                gui.root.after(0, lambda: gui.current_move_label.config(text=f"({r}, {c}) - Score: {best_score:.2f}"))
                                win_prob = compute_win_probability(best_score)
                                gui.root.after(0, lambda: gui.win_probability_label.config(text=f"{win_prob}%"))

                            # Thực hiện click và xác minh
                            if click_and_verify(r, c, config.current_game_ai_color):
                                log_message(f"Đã click tại ({r}, {c}).", logging.DEBUG)
                                config.current_game_moves.append(
                                    {"player": config.current_game_ai_color, "move": (r, c), "board": board_state}
                                )
                                config.ai_moved = True # Đánh dấu AI đã di chuyển
                                config.last_known_board_state_for_opponent_move = board_state
                            else:
                                log_message(f"Lỗi: Click tại ({r}, {c}) không làm thay đổi bàn cờ.", logging.ERROR)
                        else:
                            log_message("Không tìm thấy nước đi hợp lệ cho AI.", logging.WARNING)
                    else:
                        log_message("Không thể đọc trạng thái bàn cờ.", logging.ERROR)
            
            # Xử lý khi đến lượt đối thủ
            elif is_opponent_turn:
                if config.ai_moved: # Reset cờ khi đối thủ có lượt
                    log_message("Lượt đối thủ.", logging.INFO)
                    config.ai_moved = False 
                
                # Logic phát hiện nước đi của đối thủ (nếu cần)
                # Có thể so sánh `last_known_board_state_for_opponent_move` với trạng thái hiện tại
                # để tìm ra nước đi của đối thủ và ghi lại.

            # Cập nhật GUI định kỳ
            current_time = time.time()
            if current_time - last_check_time > 2: # Cập nhật mỗi 2 giây
                if gui.root:
                    status_text = "Đang chạy" if config.is_running else "Đã dừng"
                    if in_game_state:
                        status_text += " (Trong ván)"
                    else:
                        status_text += " (Ngoài sảnh)"
                    gui.root.after(0, lambda: gui.status_label.config(text=status_text))
                last_check_time = current_time


        except Exception as e:
            log_message(f"Lỗi nghiêm trọng trong vòng lặp auto_play: {e}", logging.CRITICAL)
            log_message(traceback.format_exc(), logging.DEBUG)
            time.sleep(2)

    log_message("Vòng lặp tự động đã dừng.", logging.INFO)


def start_auto(gui_widgets_to_pass):
    """Bắt đầu luồng tự động chơi."""
    global gui
    if config.is_running:
        log_message("Bot đã chạy rồi.", logging.WARNING)
        return

    if not config.adb_device:
        log_message("Lỗi: Chưa kết nối với thiết bị nào.", logging.ERROR)
        # messagebox.showerror("Lỗi", "Vui lòng kết nối với thiết bị trước.")
        return
        
    log_message("Bắt đầu tự động chơi...", logging.INFO)
    config.is_running = True
    config.stop_after_current_game = False
    if gui.stop_after_current_game_var:
        gui.stop_after_current_game_var.set(False)

    # Khởi tạo lại các giá trị hình học của bàn cờ
    calculate_board_geometry()

    config.auto_thread = threading.Thread(target=auto_play_loop, daemon=True)
    config.auto_thread.start()
    
    if gui.update_button_states:
        gui.update_button_states()
        gui.status_label.config(text="Đang chạy...")

def stop_auto(event=None):
    """Dừng luồng tự động chơi."""
    if not config.is_running:
        log_message("Bot chưa chạy.", logging.WARNING)
        return

    log_message("Đang dừng bot...", logging.INFO)
    config.is_running = False
    
    # Không cần join ở đây vì có thể gây treo GUI. 
    # Vòng lặp sẽ tự thoát khi is_running=False
    
    if gui.update_button_states:
        gui.update_button_states()
    if gui.status_label:
        gui.status_label.config(text="Đã dừng")
    if gui.progress_bar:
        gui.progress_bar['value'] = 0
    if gui.progress_label:
        gui.progress_label.config(text="0/0")


def request_stop_after_game():
    """Yêu cầu dừng bot sau khi ván game hiện tại kết thúc."""
    if not config.is_running:
        log_message("Bot chưa chạy để yêu cầu dừng sau.", logging.WARNING)
        return

    config.stop_after_current_game = not config.stop_after_current_game # Toggle
    
    if gui.stop_after_current_game_var:
        gui.stop_after_current_game_var.set(config.stop_after_current_game)

    if config.stop_after_current_game:
        log_message("Yêu cầu dừng sau khi kết thúc ván hiện tại.", logging.INFO)
    else:
        log_message("Đã hủy yêu cầu dừng sau ván.", logging.INFO)
        
    if gui.update_button_states:
        gui.update_button_states() 