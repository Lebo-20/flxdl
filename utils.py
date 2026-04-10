import math

def get_progress_bar(current, total, length=15):
    """Generates a visual progress bar string."""
    percent = (current / total) * 100
    completed = int((current / total) * length)
    remaining = length - completed
    bar = "█" * completed + "░" * remaining
    return f"[{bar}] {percent:.1f}%"
