# -*- coding: utf-8 -*-
import math
import time
import multiprocessing as mp
import logging
import os
from . import config
from .logger import log_message

def initialize_ai_services(use_multiprocessing=True):
    """Khởi tạo các dịch vụ cần thiết cho AI, đặc biệt là multiprocessing Pool."""
    if use_multiprocessing and config._pool is None:
        try:
            # Dọn dẹp pool cũ nếu có (trường hợp hiếm)
            if config._pool:
                config._pool.close()
                config._pool.join()
            
            num_workers = min(os.cpu_count(), config.CPU_WORKERS)
            config._pool = mp.Pool(processes=num_workers)
            log_message(f"Đã khởi tạo AI Pool với {num_workers} workers.", level=logging.INFO)
        except Exception as e:
            log_message(f"Lỗi khi khởi tạo AI Pool: {e}. AI sẽ chạy ở chế độ đơn luồng.", level=logging.ERROR)
            config._pool = None

def shutdown_ai_services():
    """Dọn dẹp và đóng các dịch vụ AI trước khi thoát."""
    if config._pool:
        log_message("Đang đóng AI Pool...", level=logging.INFO)
        try:
            config._pool.close()
            config._pool.join()
            log_message("AI Pool đã được đóng.", level=logging.INFO)
        except Exception as e:
            log_message(f"Lỗi khi đóng AI Pool: {e}", level=logging.ERROR)
        finally:
            config._pool = None

# --- HÀM TÍNH WIN% TỪ SCORE ---
def compute_win_probability(score: float, k: float = 0.1) -> float:
    """
    Sử dụng hàm logistic để map score thành xác suất thắng.
    k điều khiển độ dốc của đường cong (có thể tinh chỉnh).
    """
    p = 1.0 / (1.0 + math.exp(-k * score))
    return round(p * 100, 1)

def is_valid_coordinate(r, c):
    return 0 <= r < config.BOARD_SIZE and 0 <= c < config.BOARD_SIZE

def get_flips(board, r_start, c_start, player_color):
    if not is_valid_coordinate(r_start, c_start) or board[r_start][c_start] != '':
        return []
    opponent_color = 'W' if player_color == 'B' else 'B'
    flips_found = []
    for dr, dc in config.DIRECTIONS:
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
    for r in range(config.BOARD_SIZE):
        for c in range(config.BOARD_SIZE):
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
    temp_num_pieces = 0
    for r_idx_temp in range(config.BOARD_SIZE):
        for c_idx_temp in range(config.BOARD_SIZE):
            if board[r_idx_temp][c_idx_temp] != '':
                temp_num_pieces +=1

    current_weights = None
    if temp_num_pieces <= (config.BOARD_SIZE * config.BOARD_SIZE) * 0.33:
        current_weights = config.STATIC_POSITIONAL_WEIGHTS_EARLY
    elif temp_num_pieces <= (config.BOARD_SIZE * config.BOARD_SIZE) * 0.66:
        current_weights = config.STATIC_POSITIONAL_WEIGHTS_MID
    else:
        current_weights = config.STATIC_POSITIONAL_WEIGHTS_LATE

    # 1. Tính điểm vị trí với ma trận trọng số động
    for r in range(config.BOARD_SIZE):
        for c in range(config.BOARD_SIZE):
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
    
    current_mobility_weight = config.MOBILITY_WEIGHT_INITIAL
    if num_pieces > config.BOARD_SIZE * config.BOARD_SIZE * 0.75:
        current_mobility_weight = config.MOBILITY_WEIGHT_LATEGAME
    elif num_pieces > config.BOARD_SIZE * config.BOARD_SIZE * 0.35:
        current_mobility_weight = config.MOBILITY_WEIGHT_MIDGAME
    
    mobility_score = (my_num_moves - opponent_num_moves) * current_mobility_weight
    score += mobility_score

    # Thưởng/Phạt cho việc Pass
    if my_num_moves == 0 and opponent_num_moves > 0:
        score += config.PASS_PENALTY
    if opponent_num_moves == 0 and my_num_moves > 0:
        score += config.FORCE_PASS_BONUS

    # 3. Tính điểm ổn định cạnh (Edge Stability)
    my_stable_edges = _count_stable_edge_pieces_for_player(board, player_color)
    opponent_stable_edges = _count_stable_edge_pieces_for_player(board, opponent_color)
    
    stable_edge_score = (my_stable_edges - opponent_stable_edges) * config.STABLE_EDGE_PIECE_WEIGHT
    score += stable_edge_score

    # 4. Tính điểm Đếm Quân (Piece Parity/Count) theo giai đoạn
    my_pieces = 0
    opponent_pieces = 0
    for r_idx in range(config.BOARD_SIZE):
        for c_idx in range(config.BOARD_SIZE):
            if board[r_idx][c_idx] == player_color:
                my_pieces += 1
            elif board[r_idx][c_idx] == opponent_color:
                opponent_pieces += 1
    
    piece_count_score = 0
    if num_pieces > config.BOARD_SIZE * config.BOARD_SIZE * 0.75:
        piece_count_score = (my_pieces - opponent_pieces) * config.PIECE_COUNT_WEIGHT_LATE
    elif num_pieces > 0:
        piece_count_score = (my_pieces - opponent_pieces) * config.PIECE_COUNT_WEIGHT_EARLY_MID
    score += piece_count_score

    # 5. Đánh giá tình huống bẫy (Trap Situation)
    if opponent_num_moves > 0:
        num_opponent_bad_forced_moves = 0
        for move_coord in opponent_moves_list.keys():
            r_opp, c_opp = move_coord
            if current_weights[r_opp][c_opp] < config.BAD_MOVE_THRESHOLD:
                num_opponent_bad_forced_moves += 1
        opponent_bad_move_ratio = num_opponent_bad_forced_moves / opponent_num_moves
        score += opponent_bad_move_ratio * config.TRAP_SITUATION_WEIGHT

    if my_num_moves > 0:
        num_my_bad_forced_moves = 0
        for move_coord in my_moves_list.keys():
            r_my, c_my = move_coord
            if current_weights[r_my][c_my] < config.BAD_MOVE_THRESHOLD:
                num_my_bad_forced_moves += 1
        my_bad_move_ratio = num_my_bad_forced_moves / my_num_moves
        score -= my_bad_move_ratio * config.TRAP_SITUATION_WEIGHT

    return score

def _count_stable_edge_pieces_for_player(board_state, player_color):
    stable_pieces = set()
    N = config.BOARD_SIZE

    # Kiểm tra từ 4 góc
    if board_state[0][0] == player_color:
        for c in range(N):
            if board_state[0][c] == player_color: stable_pieces.add((0, c))
            else: break
        for r in range(N):
            if board_state[r][0] == player_color: stable_pieces.add((r, 0))
            else: break
    
    if board_state[0][N-1] == player_color:
        for c in range(N-1, -1, -1):
            if board_state[0][c] == player_color: stable_pieces.add((0, c))
            else: break
        for r in range(N):
            if board_state[r][N-1] == player_color: stable_pieces.add((r, N-1))
            else: break

    if board_state[N-1][0] == player_color:
        for c in range(N):
            if board_state[N-1][c] == player_color: stable_pieces.add((N-1, c))
            else: break
        for r in range(N-1, -1, -1):
            if board_state[r][0] == player_color: stable_pieces.add((r, 0))
            else: break

    if board_state[N-1][N-1] == player_color:
        for c in range(N-1, -1, -1):
            if board_state[N-1][c] == player_color: stable_pieces.add((N-1, c))
            else: break
        for r in range(N-1, -1, -1):
            if board_state[r][N-1] == player_color: stable_pieces.add((r, N-1))
            else: break
                
    return len(stable_pieces)

def _minimax(board, depth, maximizing_player, player_color, alpha, beta):
    opponent_color = 'W' if player_color == 'B' else 'B'
    current_player_for_this_level = player_color if maximizing_player else opponent_color
    valid_moves = get_valid_moves(board, current_player_for_this_level)

    if depth == 0 or not valid_moves:
        return evaluate_board(board, player_color)

    if maximizing_player:
        max_eval = -math.inf
        for move, flips in valid_moves.items():
            temp_board = [row[:] for row in board]
            make_move(temp_board, move[0], move[1], current_player_for_this_level, flips)
            eval_score = _minimax(temp_board, depth - 1, False, player_color, alpha, beta)
            max_eval = max(max_eval, eval_score)
            alpha = max(alpha, eval_score)
            if beta <= alpha: break
        return max_eval
    else:
        min_eval = math.inf
        for move, flips in valid_moves.items():
            temp_board = [row[:] for row in board]
            make_move(temp_board, move[0], move[1], current_player_for_this_level, flips)
            eval_score = _minimax(temp_board, depth - 1, True, player_color, alpha, beta)
            min_eval = min(min_eval, eval_score)
            beta = min(beta, eval_score)
            if beta <= alpha: break
        return min_eval

def _search_one_move(args):
    board_after_move, depth_remaining, original_player, initial_move, game_moves_up_to_this_point, ai_color_for_this_turn = args
    
    score_from_minimax = _minimax(board_after_move, depth_remaining, False, original_player, -math.inf, math.inf)
    
    opening_book_bonus = 0
    prefix_for_lookup = []
    for move_entry in game_moves_up_to_this_point:
        if isinstance(move_entry, (list, tuple)) and len(move_entry) == 2:
            actual_m = move_entry[1]
            if isinstance(actual_m, (list, tuple)) and len(actual_m) == 2 and \
               isinstance(actual_m[0], int) and isinstance(actual_m[1], int):
                prefix_for_lookup.append(tuple(actual_m))
            elif actual_m == 'PASS':
                prefix_for_lookup.append('PASS')
    prefix_tuple = tuple(prefix_for_lookup)

    if prefix_tuple in config.opening_stats:
        stats_for_this_prefix = config.opening_stats[prefix_tuple]
        move_stats = stats_for_this_prefix.get(initial_move)
        if move_stats:
            wins, losses = move_stats[0], move_stats[1]
            if wins + losses > 0:
                opening_book_bonus = config.OPENING_BOOK_STATISTICAL_WEIGHT_FACTOR * (wins - losses) / (wins + losses + 1e-6)
    
    final_score = score_from_minimax + opening_book_bonus
    return final_score, initial_move

def find_best_move(board_state, player_color, depth=6):
    # player_color ở đây là current_game_ai_color
    valid_moves = get_valid_moves(board_state, player_color)
    if not valid_moves:
        log_message(f"[AI {player_color}] Không có nước đi hợp lệ.", level=logging.INFO)
        return None, 0.0

    best_move_found = None
    best_score_found = -math.inf
    turn_start_time = time.monotonic()
    TIME_LIMIT_SECONDS = 13.0
    fallback_move = list(valid_moves.keys())[0]

    tasks_for_pool = []
    for move, flips in valid_moves.items():
        temp_board = [row[:] for row in board_state]
        make_move(temp_board, move[0], move[1], player_color, flips)
        tasks_for_pool.append({'args': (temp_board, depth - 1, player_color, move, list(config.current_game_moves), player_color), 'original_move': move})

    if not config._pool:
        log_message(f"[AI {player_color}] Lỗi: _pool chưa được khởi tạo. Chạy đơn luồng.", level=logging.ERROR)
        for task_info in tasks_for_pool:
            score, move_from_worker = _search_one_move(task_info['args'])
            if score > best_score_found:
                best_score_found = score
                best_move_found = move_from_worker
        if not best_move_found: best_move_found = fallback_move
        log_message(f"[AI {player_color}] Đơn luồng: {best_move_found} ({best_score_found:.0f})", level=logging.INFO)
        return best_move_found, best_score_found
        
    async_results_map = {}
    num_tasks = len(tasks_for_pool)
    log_message(f"[AI {player_color}] Bắt đầu tìm nước đi (Pool, depth={depth}, tasks={num_tasks}, limit={TIME_LIMIT_SECONDS}s)", level=logging.INFO)

    for task_info in tasks_for_pool:
        async_res = config._pool.apply_async(_search_one_move, args=(task_info['args'],))
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
        log_message(f"[AI {player_color}] Hoàn tất. Best: {best_move_found} (score: {best_score_found:.0f}). Time: {final_search_time:.2f}s.", level=logging.INFO)

    if best_move_found:
        move_str_log = f"{chr(ord('A') + best_move_found[1])}{best_move_found[0] + 1}"
        log_message(f"[AI {player_color}] Chọn nước: {move_str_log} ({best_move_found}) với điểm: {best_score_found:.0f}", level=logging.INFO)
    else:
        return fallback_move, -math.inf
    return best_move_found, best_score_found 