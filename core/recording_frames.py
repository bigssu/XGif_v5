"""Replayable BGR capture frames with a bounded RAM prefix and a raw disk tail."""

from collections.abc import Iterator
from contextlib import suppress
import errno
import operator
import os
import shutil
import tempfile
import threading

import numpy as np


class RecordingFrames:
    """The last owner releases the temporary file, including on process exit."""

    def __init__(self, budget_bytes: int):
        if budget_bytes < 0:
            raise ValueError("Frame memory budget must be nonnegative")
        self.byte_budget = min(operator.index(budget_bytes), 128 * 1024**2)
        self._ram = []
        self._shape = ()
        self._frame_bytes = 0
        self._disk_count = 0
        self._file = None
        self._reader = None
        self._reader_lock = threading.Lock()
        self._writer_lock = threading.Lock()
        self._publish_lock = threading.Lock()
        self._sealed = False

    def seal(self) -> None:
        """Freeze the complete prefix without waiting for a stalled capture write."""
        with self._publish_lock:
            self._sealed = True

    def __len__(self) -> int:
        return len(self._ram) + self._disk_count

    @property
    def resident_bytes(self) -> int:
        return len(self._ram) * self._frame_bytes

    @property
    def disk_bytes(self) -> int:
        return self._disk_count * self._frame_bytes

    def append(self, frame: np.ndarray) -> None:
        if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3:
            raise ValueError("Expected a uint8 BGR capture frame")
        if frame.shape[2] != 3 or not frame.size:
            raise ValueError("Expected a nonempty BGR capture frame")
        with self._writer_lock:
            if self._sealed:
                return
            if len(self) and frame.shape != self._shape:
                raise ValueError("Capture frame dimensions changed")
            self._shape = frame.shape
            self._frame_bytes = frame.nbytes
            if self.resident_bytes + frame.nbytes <= self.byte_budget:
                snapshot = frame.copy(order="C")
                snapshot.setflags(write=False)
                with self._publish_lock:
                    if not self._sealed:
                        self._ram.append(snapshot)
                return

            directory = tempfile.gettempdir()
            # Leave the same output headroom used by the GIF encoder's preflight.
            reserve = max(100 * 1024**2, (len(self) + 1) * frame.nbytes // 10)
            if shutil.disk_usage(directory).free < reserve + frame.nbytes:
                raise OSError(errno.ENOSPC, "Insufficient disk space for capture frames", directory)
            if self._file is None:
                self._file = tempfile.TemporaryFile(  # noqa: SIM115 - shared with replay readers until the last owner exits
                    dir=directory, prefix="xgif-capture-", buffering=0
                )
            if os.name == "nt" and self._reader is None:
                # An independent seek position and delete-sharing keep committed
                # frames readable while the writer is blocked on a later frame.
                self._reader = open(  # noqa: SIM115
                    self._file.name, "rb", buffering=0,
                    opener=lambda path, flags: os.open(path, flags | os.O_TEMPORARY),
                )
            offset = self.disk_bytes
            self._file.seek(offset)
            try:
                written = self._file.write(np.ascontiguousarray(frame))
                if written != frame.nbytes:
                    raise OSError(errno.ENOSPC, "Incomplete write to the capture file")
            except OSError:
                with suppress(OSError):
                    self._file.truncate(offset)
                raise
            with self._publish_lock:
                if not self._sealed:
                    self._disk_count += 1

    def __getitem__(self, index: int) -> np.ndarray:
        index = operator.index(index)
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        if index < len(self._ram):
            return self._ram[index]
        offset = (index - len(self._ram)) * self._frame_bytes
        if self._reader is None:
            data = os.pread(self._file.fileno(), self._frame_bytes, offset)
            if len(data) != self._frame_bytes:
                raise OSError(errno.EIO, "Incomplete frame in the capture file")
            return np.frombuffer(data, dtype=np.uint8).reshape(self._shape)
        frame = np.empty(self._shape, dtype=np.uint8)
        with self._reader_lock:
            self._reader.seek(offset)
            if self._reader.readinto(frame) != self._frame_bytes:
                raise OSError(errno.EIO, "Incomplete frame in the capture file")
        frame.setflags(write=False)
        return frame

    def __iter__(self) -> Iterator[np.ndarray]:
        for index in range(len(self)):
            yield self[index]
