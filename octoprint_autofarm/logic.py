"""Pure helpers with no OctoPrint import, so they're testable standalone.

numpy is imported lazily inside the functions that need it, not at module
level - numpy/opencv are optional (see HAS_CV2 in __init__.py), and this
module gets imported unconditionally on plugin load. A top-level import
here would crash plugin load entirely on any install without numpy.
"""


def diff_ratio(current, reference, pixel_threshold=30):
    """Fraction of pixels that changed between two same-shape BGR arrays."""
    import numpy as np

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
