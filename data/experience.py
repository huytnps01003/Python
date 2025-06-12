# -*- coding: utf-8 -*-
import os
import json
import time
import sys
import traceback
import logging

from . import config
from .logger import log_message

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
        if os.path.exists(config.EXPERIENCE_FILE_PATH):
            with open(config.EXPERIENCE_FILE_PATH, 'r', encoding='utf-8') as f:
                text = f.read().strip()
                if text: # Chỉ parse JSON nếu text không rỗng
                    try:
                        experiences = json.loads(text)
                        if not isinstance(experiences, list):
                            log_message(f"Lỗi: File kinh nghiệm '{config.EXPERIENCE_FILE_PATH}' không chứa một danh sách. Sẽ tạo mới.", level=logging.WARNING)
                            experiences = []
                    except json.JSONDecodeError as e_json:
                        log_message(f"Lỗi giải mã JSON từ '{config.EXPERIENCE_FILE_PATH}': {e_json}. File có thể bị hỏng. Sẽ tạo mới.", level=logging.WARNING)
                        experiences = []

        experiences.append(record)

        # Ghi file và fsync để chắc chắn đã lưu
        with open(config.EXPERIENCE_FILE_PATH, 'w', encoding='utf-8') as f:
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

        log_message(f"Đã lưu kinh nghiệm ván đấu vào '{config.EXPERIENCE_FILE_PATH}'. Tổng số: {len(experiences)} bản ghi.", level=logging.INFO)

    except Exception as e:
        log_message(f"Lỗi nghiêm trọng khi lưu kinh nghiệm ván đấu: {e}", level=logging.ERROR)
        log_message(traceback.format_exc(), level=logging.ERROR)

def load_game_experience():
    if os.path.exists(config.EXPERIENCE_FILE_PATH):
        try:
            with open(config.EXPERIENCE_FILE_PATH, 'r', encoding='utf-8') as f:
                experiences_from_file = json.load(f)
                if isinstance(experiences_from_file, list):
                    config.loaded_game_experiences = experiences_from_file
                    log_message(f"Đã tải {len(config.loaded_game_experiences)} bản ghi kinh nghiệm từ '{config.EXPERIENCE_FILE_PATH}'.", level=logging.INFO)
                else:
                    log_message(f"Lỗi: File kinh nghiệm '{config.EXPERIENCE_FILE_PATH}' không chứa một danh sách. Không tải.", level=logging.WARNING)
                    config.loaded_game_experiences = []
        except json.JSONDecodeError:
            log_message(f"Lỗi giải mã JSON khi tải từ '{config.EXPERIENCE_FILE_PATH}'. File có thể bị hỏng. Không tải.", level=logging.WARNING)
            config.loaded_game_experiences = []
        except Exception as e:
            log_message(f"Lỗi không xác định khi tải file kinh nghiệm: {e}", level=logging.ERROR)
            config.loaded_game_experiences = []
    else:
        log_message(f"File kinh nghiệm '{config.EXPERIENCE_FILE_PATH}' không tồn tại. Sẽ tạo mới khi có ván đấu kết thúc.", level=logging.INFO)
        config.loaded_game_experiences = []

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
    if not win_games and not loss_games:
        log_message("Không có dữ liệu thắng/thua (từ file) để cập nhật trọng số AI.", level=logging.INFO)
        return

    changes_made = False
    # Điều chỉnh trọng số dựa trên việc có ván thắng/thua
    if win_games:
        original_weights = (config.MOBILITY_WEIGHT_INITIAL, config.MOBILITY_WEIGHT_MIDGAME, config.MOBILITY_WEIGHT_LATEGAME, config.FORCE_PASS_BONUS, config.STABLE_EDGE_PIECE_WEIGHT)
        config.MOBILITY_WEIGHT_INITIAL = min(20, config.MOBILITY_WEIGHT_INITIAL + 1)
        config.MOBILITY_WEIGHT_MIDGAME = min(30, config.MOBILITY_WEIGHT_MIDGAME + 1)
        config.MOBILITY_WEIGHT_LATEGAME = min(45, config.MOBILITY_WEIGHT_LATEGAME + 1)
        config.FORCE_PASS_BONUS = min(1000, config.FORCE_PASS_BONUS + 50)
        config.STABLE_EDGE_PIECE_WEIGHT = min(80, config.STABLE_EDGE_PIECE_WEIGHT + 5)
        if original_weights != (config.MOBILITY_WEIGHT_INITIAL, config.MOBILITY_WEIGHT_MIDGAME, config.MOBILITY_WEIGHT_LATEGAME, config.FORCE_PASS_BONUS, config.STABLE_EDGE_PIECE_WEIGHT):
            changes_made = True

    if loss_games:
        original_weights_loss = (config.MOBILITY_WEIGHT_INITIAL, config.MOBILITY_WEIGHT_MIDGAME, config.MOBILITY_WEIGHT_LATEGAME, config.PASS_PENALTY, config.PIECE_COUNT_WEIGHT_EARLY_MID)
        config.MOBILITY_WEIGHT_INITIAL = max(10, config.MOBILITY_WEIGHT_INITIAL - 1)
        config.MOBILITY_WEIGHT_MIDGAME = max(20, config.MOBILITY_WEIGHT_MIDGAME - 1)
        config.MOBILITY_WEIGHT_LATEGAME = max(35, config.MOBILITY_WEIGHT_LATEGAME - 1)
        config.PASS_PENALTY = max(-800, config.PASS_PENALTY - 50)
        config.PIECE_COUNT_WEIGHT_EARLY_MID = max(-3.0, config.PIECE_COUNT_WEIGHT_EARLY_MID - 0.1)
        if original_weights_loss != (config.MOBILITY_WEIGHT_INITIAL, config.MOBILITY_WEIGHT_MIDGAME, config.MOBILITY_WEIGHT_LATEGAME, config.PASS_PENALTY, config.PIECE_COUNT_WEIGHT_EARLY_MID):
            changes_made = True

    if changes_made:
        log_message(f"Đã cập nhật trọng số AI dựa trên {len(win_games)} ván thắng và {len(loss_games)} ván thua.", level=logging.INFO)
        log_message(f"Trọng số mới: MOB_INIT={config.MOBILITY_WEIGHT_INITIAL}, MOB_MID={config.MOBILITY_WEIGHT_MIDGAME}, MOB_LATE={config.MOBILITY_WEIGHT_LATEGAME}, FORCE_PASS={config.FORCE_PASS_BONUS}, PASS_PENALTY={config.PASS_PENALTY}, STABLE_EDGE={config.STABLE_EDGE_PIECE_WEIGHT}, PIECE_COUNT_EM={config.PIECE_COUNT_WEIGHT_EARLY_MID:.1f}", level=logging.DEBUG)
    else:
        log_message(f"Không có thay đổi trọng số AI sau khi phân tích {len(win_games)} thắng / {len(loss_games)} thua (có thể đã đạt giới hạn hoặc không có game).", level=logging.INFO)

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
    config.opening_stats = {} # Reset mỗi lần xây dựng lại
    if not config.loaded_game_experiences:
        log_message("OPENING_BOOK_BUILD: Không có kinh nghiệm nào để xây dựng thống kê.", level=logging.INFO)
        return

    num_records_processed = 0
    for record in config.loaded_game_experiences:
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
                    valid_sequence = False
                    break
            else:
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

            stats_for_prefix = config.opening_stats.setdefault(prefix_tuple, {})
            current_win_loss = stats_for_prefix.setdefault(move_made_from_prefix, [0, 0])

            if game_result_for_ai == "WIN":
                current_win_loss[0] += 1
            elif game_result_for_ai == "LOSS":
                current_win_loss[1] += 1
            # Các ván hòa không làm thay đổi win/loss count trong opening book này

            stats_for_prefix[move_made_from_prefix] = current_win_loss
        num_records_processed +=1

    log_message(f"OPENING_BOOK_BUILD: Đã xây dựng xong thống kê khai cuộc từ {num_records_processed} bản ghi. {len(config.opening_stats)} tiền tố được ghi nhận.", level=logging.INFO) 