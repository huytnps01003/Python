"""Pixel color checking helpers."""

import numpy as np


def check_pixel_color(image, x: int, y: int, target_rgb, tolerance: int = 10) -> bool:
    """Return True if the pixel at (x,y) matches the target color within tolerance."""
    pixel = image[y, x]
    return all(abs(int(pixel[i]) - target_rgb[i]) <= tolerance for i in range(3))


def check_pixel_match(image, x: int, y: int, target_rgb, tolerance: int = 10) -> bool:
    """Alias for check_pixel_color."""
    return check_pixel_color(image, x, y, target_rgb, tolerance)
