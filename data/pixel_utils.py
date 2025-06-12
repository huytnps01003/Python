# -*- coding: utf-8 -*-
import logging
from .logger import log_message

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