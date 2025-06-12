"""Tkinter GUI components for the autoplayer."""

import tkinter as tk
from tkinter import ttk, scrolledtext


def create_gui():
    """Create the main GUI window."""
    root = tk.Tk()
    root.title("Auto Co Lat")
    label = ttk.Label(root, text="Reversi Autoplayer")
    label.pack()
    log_area = scrolledtext.ScrolledText(root)
    log_area.pack(fill=tk.BOTH, expand=True)
    return root, log_area
