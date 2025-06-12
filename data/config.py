# -*- coding: utf-8 -*-
import math

# --- BIẾN TOÀN CỤC LƯU SỐ QUÂN CUỐI CÙNG ---
last_known_black_count_global = 0
last_known_white_count_global = 0

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
opening_stats = {}
OPENING_BOOK_STATISTICAL_WEIGHT_FACTOR = 50 # Có thể điều chỉnh

# Tọa độ tâm ô A1 và H8
A1_CENTER_X, A1_CENTER_Y = 128, 589
H8_CENTER_X, H8_CENTER_Y = 587, 1051

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

# --- Logic Cờ lật & AI ---
DIRECTIONS = [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)]

# --- Các biến GUI sẽ được khởi tạo và quản lý trong gui_components ---
# Các module khác không nên truy cập trực tiếp vào các biến này.
# Thay vào đó, thông tin sẽ được truyền qua các hàm.
root = None
log_area = None
device_selection_var = None
target_selection_var = None
stop_after_current_game_var = None
use_multiprocessing_var = None 