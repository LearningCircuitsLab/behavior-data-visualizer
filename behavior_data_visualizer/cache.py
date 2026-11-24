"""
A cache of dataframes shared by everyone using the dashboard.

Several people can use one dashboard at the same time (each request runs in
its own thread), so the cache:

- reads each entry once: if two people open the same mouse at the same time,
  the second waits for the first one to read it instead of reading it again,
- is read again when its file changes (the version of an entry, e.g. the
  time its file was modified),
- keeps the entries used last, up to a total memory (the trials of a mouse
  with a long history can take close to 1 GB), and always the last one read.
"""

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Dict, Hashable, List

import pandas as pd


def memory_of(value: Any) -> int:
    """Bytes taken by a dataframe (0 for anything else, e.g. None)."""
    if isinstance(value, pd.DataFrame):
        return int(value.memory_usage(deep=True).sum())
    return 0


@dataclass
class Entry:
    version: Hashable
    value: Any
    size: int


class SharedCache:
    def __init__(self, max_bytes: int, name: str = "cache"):
        self.max_bytes = max_bytes
        self.name = name
        self._entries: "OrderedDict[Hashable, Entry]" = OrderedDict()
        self._lock = threading.Lock()  # protects _entries and _key_locks
        self._key_locks: Dict[Hashable, threading.Lock] = {}
        self.loads = 0  # times an entry was read (for the status page and the tests)

    def get(self, key: Hashable, version: Hashable, load: Callable[[], Any]) -> Any:
        """The value of key, read with load() if it is not in the cache or its version changed."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry.version == version:
                self._entries.move_to_end(key)
                return entry.value
            key_lock = self._key_locks.setdefault(key, threading.Lock())
        with key_lock:  # one reading of each key at a time
            with self._lock:  # someone else may have read it while this one waited
                entry = self._entries.get(key)
                if entry is not None and entry.version == version:
                    self._entries.move_to_end(key)
                    return entry.value
            value = load()
            with self._lock:
                self.loads += 1
                self._entries[key] = Entry(version, value, memory_of(value))
                self._entries.move_to_end(key)
                self._evict()
            return value

    def _evict(self) -> None:
        """Removes the entries used least recently until the total fits (keeping the last one)."""
        while len(self._entries) > 1 and sum(e.size for e in self._entries.values()) > self.max_bytes:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self.loads = 0

    def summary(self) -> List[str]:
        """The entries in memory, most recently used last (for the status page)."""
        with self._lock:
            return [f"{key}: {entry.size / 1e6:.0f} MB" for key, entry in self._entries.items()]

    def total_bytes(self) -> int:
        with self._lock:
            return sum(e.size for e in self._entries.values())
