"""Pure helpers with no OctoPrint/cv2 import, so they're testable standalone."""
import numpy as np


def diff_ratio(current, reference, pixel_threshold=30):
    """Fraction of pixels that changed between two same-shape BGR arrays."""
    diff = np.abs(current.astype(int) - reference.astype(int))
    if diff.ndim == 3:
        diff = diff.mean(axis=2)
    changed = np.count_nonzero(diff > pixel_threshold)
    return changed / diff.size


def bed_is_clear(current, reference, pixel_threshold=30, ratio_threshold=0.02):
    return diff_ratio(current, reference, pixel_threshold) < ratio_threshold


def pop_next(queue):
    """Return (next_item_or_None, remaining_queue) without mutating input."""
    if not queue:
        return None, queue
    return queue[0], queue[1:]
