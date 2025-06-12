# -*- coding: utf-8 -*-
import logging
from . import config
from .logger import log_message
from .pixel_utils import check_pixel_match, check_pixel_color

def build_custom_piece_maps():
    """Chuyển CUSTOM_PIECE_DATA thành hai map BLACK / WHITE."""
    config.CELL_BLACK_MAP.clear()
    config.CELL_WHITE_MAP.clear()

    for entry in config.CUSTOM_PIECE_DATA:
        r, c = entry["r"], entry["c"]
        x, y = entry["x"], entry["y"]
        rgb = tuple(entry["rgb"])  # e.g. (R,G,B)
        piece = entry["piece"].upper()  # 'B' hoặc 'W'

        if piece == "B":
            config.CELL_BLACK_MAP.setdefault((r,c), []).append((x, y, rgb))
        elif piece == "W":
            config.CELL_WHITE_MAP.setdefault((r,c), []).append((x, y, rgb))
        else:
            # Nếu có piece khác, bỏ qua
            continue
    log_message(f"Đã xây dựng xong custom piece maps. Black map có {len(config.CELL_BLACK_MAP)} entries, White map có {len(config.CELL_WHITE_MAP)} entries.", level=logging.INFO)


def calculate_board_geometry():
    """Tính toán BOARD_POS, CELL_WIDTH/HEIGHT và cell_centers dựa trên A1, H8."""
    if config.H8_CENTER_X <= config.A1_CENTER_X or config.H8_CENTER_Y <= config.A1_CENTER_Y:
        log_message("Lỗi: Tọa độ tâm A1, H8 không hợp lệ (H8 phải ở dưới bên phải A1).", level=logging.ERROR)
        config.BOARD_X, config.BOARD_Y, config.BOARD_W, config.BOARD_H = 0, 0, 0, 0
        config.CELL_WIDTH, config.CELL_HEIGHT = 0, 0
        config.cell_centers = []
        return

    total_width_centers = config.H8_CENTER_X - config.A1_CENTER_X
    total_height_centers = config.H8_CENTER_Y - config.A1_CENTER_Y

    config.CELL_WIDTH = total_width_centers / (config.BOARD_SIZE - 1.0)
    config.CELL_HEIGHT = total_height_centers / (config.BOARD_SIZE - 1.0)

    config.BOARD_X = int(round(config.A1_CENTER_X - config.CELL_WIDTH / 2.0))
    config.BOARD_Y = int(round(config.A1_CENTER_Y - config.CELL_HEIGHT / 2.0))

    config.BOARD_W = int(round(config.CELL_WIDTH * config.BOARD_SIZE))
    config.BOARD_H = int(round(config.CELL_HEIGHT * config.BOARD_SIZE))

    log_message(f"Tính toán Geometry: Cell({config.CELL_WIDTH:.2f}, {config.CELL_HEIGHT:.2f}), BoardXY({config.BOARD_X}, {config.BOARD_Y}), BoardWH({config.BOARD_W}, {config.BOARD_H})", level=logging.INFO)

    temp_centers = []
    for r in range(config.BOARD_SIZE):
        row_centers = []
        for c in range(config.BOARD_SIZE):
            center_x = config.BOARD_X + c * config.CELL_WIDTH + config.CELL_WIDTH / 2.0
            center_y = config.BOARD_Y + r * config.CELL_HEIGHT + config.CELL_HEIGHT / 2.0
            row_centers.append((int(round(center_x)), int(round(center_y))))
        temp_centers.append(row_centers)

    config.cell_centers = temp_centers
    log_message(f"Đã tính toán và lưu {len(config.cell_centers) * len(config.cell_centers[0])} tọa độ tâm ô.", level=logging.INFO)


def get_board_state_cv(cv_img):
    if not config.cell_centers:
        calculate_board_geometry()
        if not config.cell_centers:
            log_message("Vẫn chưa tính được tọa độ tâm ô.", level=logging.ERROR)
            empty = [['' for _ in range(config.BOARD_SIZE)] for _ in range(config.BOARD_SIZE)]
            return empty, 0, 0

    if cv_img is None:
        log_message("Ảnh không hợp lệ để quét bàn cờ.", level=logging.ERROR)
        empty = [['' for _ in range(config.BOARD_SIZE)] for _ in range(config.BOARD_SIZE)]
        return empty, 0, 0

    board_state = [['' for _ in range(config.BOARD_SIZE)] for _ in range(config.BOARD_SIZE)]
    black_count, white_count = 0, 0
    img_h, img_w = cv_img.shape[:2]

    for r_idx in range(config.BOARD_SIZE):
        for c_idx in range(config.BOARD_SIZE):
            # --- 1) Dò custom‐pixel: BLACK trước ---
            cell_black_list = config.CELL_BLACK_MAP.get((r_idx, c_idx), [])
            found = False
            for (x_pix, y_pix, target_rgb) in cell_black_list:
                if 0 <= y_pix < img_h and 0 <= x_pix < img_w:
                    if check_pixel_match(cv_img, x_pix, y_pix, target_rgb, config.CUSTOM_PIECE_TOLERANCE_BLACK):
                        board_state[r_idx][c_idx] = 'B'
                        black_count += 1
                        found = True
                        break
            if found:
                continue

            # --- 2) Dò custom‐pixel: WHITE ---
            cell_white_list = config.CELL_WHITE_MAP.get((r_idx, c_idx), [])
            for (x_pix, y_pix, target_rgb) in cell_white_list:
                if 0 <= y_pix < img_h and 0 <= x_pix < img_w:
                    if check_pixel_match(cv_img, x_pix, y_pix, target_rgb, config.CUSTOM_PIECE_TOLERANCE_WHITE):
                        board_state[r_idx][c_idx] = 'W'
                        white_count += 1
                        found = True
                        break
            if found:
                continue

            # --- 3) Fallback: check pixel trung tâm ô với PIECE_COLOR_TOLERANCE ---
            try:
                # Đảm bảo cell_centers[r_idx][c_idx] tồn tại trước khi truy cập
                if not config.cell_centers or r_idx >= len(config.cell_centers) or c_idx >= len(config.cell_centers[r_idx]):
                    log_message(f"Lỗi: Tọa độ ({r_idx},{c_idx}) không hợp lệ cho cell_centers trong fallback.", level=logging.WARNING)
                    continue # Bỏ qua ô này nếu tọa độ không hợp lệ

                center_x, center_y = config.cell_centers[r_idx][c_idx]
                if check_pixel_color(cv_img, center_x, center_y, config.PIECE_COLOR_BLACK, config.PIECE_COLOR_TOLERANCE_BLACK):
                    board_state[r_idx][c_idx] = 'B'
                    black_count += 1
                elif check_pixel_color(cv_img, center_x, center_y, config.PIECE_COLOR_WHITE, config.PIECE_COLOR_TOLERANCE_WHITE):
                    board_state[r_idx][c_idx] = 'W'
                    white_count += 1
                # Nếu không match cả hai, để trống
            except IndexError as e: # Xử lý cụ thể IndexError nếu cell_centers có cấu trúc không mong muốn
                log_message(f"Lỗi IndexError khi truy cập cell_centers[{r_idx}][{c_idx}] trong fallback: {e}", level=logging.WARNING)
            except Exception as e:
                log_message(f"Lỗi fallback pixel ô ({r_idx},{c_idx}): {e}", level=logging.WARNING)

    return board_state, black_count, white_count

def detect_ai_color_cv(cv_img):
    if cv_img is None: return None
    
    # Thay vì check 1 pixel, check 1 vùng 5x5 xung quanh điểm trung tâm
    check_size = 5
    start_x = config.AI_COLOR_DETECT_PIXEL_X - check_size // 2
    start_y = config.AI_COLOR_DETECT_PIXEL_Y - check_size // 2
    
    black_matches = 0
    white_matches = 0
    
    for i in range(check_size):
        for j in range(check_size):
            x = start_x + j
            y = start_y + i
            if check_pixel_color(cv_img, x, y, config.AI_COLOR_DETECT_PIXEL_COLOR_BLACK, config.AI_COLOR_DETECT_PIXEL_TOLERANCE):
                black_matches += 1
            # Sử dụng elif để tối ưu, một pixel không thể vừa đen vừa trắng
            elif check_pixel_color(cv_img, x, y, config.AI_COLOR_DETECT_PIXEL_COLOR_WHITE, config.AI_COLOR_DETECT_PIXEL_TOLERANCE):
                white_matches += 1

    # Yêu cầu đa số pixel trong vùng phải khớp để giảm nhiễu
    # Ví dụ, trong vùng 25 pixel, cần ít nhất 13 pixel khớp.
    required_matches = (check_size * check_size) // 2 + 1

    if black_matches > white_matches and black_matches >= required_matches:
        return 'B'
    if white_matches > black_matches and white_matches >= required_matches:
        return 'W'
        
    return None 