"""Board state detection utilities."""

from typing import Dict, List
import cv2
import numpy as np

# Placeholder for custom piece data loaded from main
CUSTOM_PIECE_DATA: Dict[str, List] = {}

CELL_BLACK_MAP = {}
CELL_WHITE_MAP = {}


def build_custom_piece_maps() -> None:
    """Build custom maps for black and white pieces from CUSTOM_PIECE_DATA."""
    # TODO: Implement loading logic
    pass


def get_board_state_cv(cv_img):
    """Detect board state from a screenshot."""
    pass


def detect_ai_color_cv(cv_img):
    """Detect the AI color based on board screenshot."""
    pass


def calculate_board_geometry():
    """Calculate board geometry based on screen resolution."""
    pass
