"""Experience persistence for the autoplayer."""

import json
from pathlib import Path

EXPERIENCE_FILE = Path("experience.json")


def save_game_experience(ai_color, result, moves_history):
    """Save game experience to disk."""
    data = {"ai_color": ai_color, "result": result, "moves": moves_history}
    EXPERIENCE_FILE.write_text(json.dumps(data, ensure_ascii=False))


def load_game_experience():
    """Load game experience from disk if available."""
    if EXPERIENCE_FILE.exists():
        return json.loads(EXPERIENCE_FILE.read_text())
    return None
