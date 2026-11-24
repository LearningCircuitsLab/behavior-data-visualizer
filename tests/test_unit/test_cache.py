import threading
import time

import pandas as pd

from behavior_data_visualizer import data
from behavior_data_visualizer.cache import SharedCache, memory_of
from tests.conftest import VISUAL_COT


def frame(n_rows: int) -> pd.DataFrame:
    return pd.DataFrame({"x": range(n_rows)})


def test_reads_once_and_again_when_the_version_changes():
    cache = SharedCache(max_bytes=10**9)
    assert cache.get("a", 1, lambda: frame(3)).equals(frame(3))
    assert cache.get("a", 1, lambda: frame(5)).equals(frame(3))  # same version: not read again
    assert cache.get("a", 2, lambda: frame(5)).equals(frame(5))  # file changed
    assert cache.loads == 2


def test_same_key_at_the_same_time_is_read_once():
    cache = SharedCache(max_bytes=10**9)
    started = threading.Event()

    def slow_read():
        started.set()
        time.sleep(0.3)
        return frame(10)

    results = []
    threads = [threading.Thread(target=lambda: results.append(cache.get("mouse", 1, slow_read))) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert cache.loads == 1
    assert len(results) == 5 and all(r is results[0] for r in results)


def test_different_keys_are_read_at_the_same_time():
    cache = SharedCache(max_bytes=10**9)
    start = time.monotonic()
    threads = [
        threading.Thread(target=cache.get, args=(key, 1, lambda: (time.sleep(0.3), frame(1))[1])) for key in "abc"
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert cache.loads == 3
    assert time.monotonic() - start < 0.8  # not one after the other (0.9 s)


def test_keeps_the_last_used_up_to_the_memory():
    size = memory_of(frame(1000))
    cache = SharedCache(max_bytes=int(size * 2.5))
    for key in "abc":
        cache.get(key, 1, lambda: frame(1000))
    assert [line.split(":")[0] for line in cache.summary()] == ["b", "c"]  # a was the least recently used
    cache.get("b", 1, lambda: frame(1000))  # b used again
    cache.get("d", 1, lambda: frame(1000))
    assert [line.split(":")[0] for line in cache.summary()] == ["b", "d"]
    assert cache.total_bytes() == 2 * size


def test_keeps_the_last_one_even_if_it_does_not_fit():
    cache = SharedCache(max_bytes=10)
    cache.get("big", 1, lambda: frame(1000))
    assert len(cache.summary()) == 1


def test_mice_are_shared_and_cleared():
    first = data.load_mouse_data(*VISUAL_COT)
    assert data.load_mouse_data(*VISUAL_COT) is first
    assert data.MICE.loads == 1
    data.clear_cache()
    assert data.load_mouse_data(*VISUAL_COT) is not first
