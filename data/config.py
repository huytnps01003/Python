"""Configuration constants for the Reversi autoplayer."""

# Example constants copied from main.py
CPU_WORKERS = 16
DESIGN_WIDTH = 720
DESIGN_HEIGHT = 1560

# Coordinates for menu button
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
        "RGB": MENU_PIXEL_COLOR,
        "TOLERANCE": MENU_PIXEL_TOLERANCE,
    },
    "Thế cờ hẳng ngày": {
        "X": 319,
        "Y": 969,
        "RGB": (255, 225, 177),
        "TOLERANCE": 15,
    },
}
