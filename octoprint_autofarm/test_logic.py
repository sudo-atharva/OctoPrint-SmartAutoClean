"""Run directly: python octoprint_autofarm/test_logic.py"""
import numpy as np

from logic import bed_is_clear, diff_ratio, pop_next


def test_identical_frames_are_clear():
    frame = np.full((10, 10, 3), 100, dtype=np.uint8)
    assert diff_ratio(frame, frame) == 0
    assert bed_is_clear(frame, frame)


def test_large_change_is_not_clear():
    reference = np.zeros((10, 10, 3), dtype=np.uint8)
    current = np.full((10, 10, 3), 255, dtype=np.uint8)
    assert not bed_is_clear(current, reference)


def test_pop_next_empty_queue():
    item, rest = pop_next([])
    assert item is None
    assert rest == []


def test_pop_next_does_not_mutate():
    queue = [{"path": "a.gcode"}, {"path": "b.gcode"}]
    item, rest = pop_next(queue)
    assert item == {"path": "a.gcode"}
    assert rest == [{"path": "b.gcode"}]
    assert queue == [{"path": "a.gcode"}, {"path": "b.gcode"}]  # original untouched


if __name__ == "__main__":
    test_identical_frames_are_clear()
    test_large_change_is_not_clear()
    test_pop_next_empty_queue()
    test_pop_next_does_not_mutate()
    print("ok")
