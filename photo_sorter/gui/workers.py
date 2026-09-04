# -*- coding: utf-8 -*-

"""把扫描、执行、撤销放到后台线程，别卡住界面。"""

import threading
from collections import deque
from pathlib import Path

from PySide6.QtCore import QSize, QThread, Signal
from PySide6.QtGui import QImage, QImageReader

from ..core import executor, planner
from ..core.classifier import ClipClassifier, create_classifier
from ..core.models import Plan, SortOptions


class _CancelableThread(QThread):
    progress = Signal(int, int, str)  # 当前 / 总数 / 当前文件

    def __init__(self, parent=None):
        super().__init__(parent)
        self._canceled = False

    def cancel(self) -> None:
        self._canceled = True

    def is_canceled(self) -> bool:
        return self._canceled

    def _emit_progress(self, index: int, total: int, path: Path) -> None:
        self.progress.emit(index, total, str(path))


class ScanWorker(_CancelableThread):
    """扫描并生成计划。"""

    finished_plan = Signal(object)
    failed = Signal(str)
    stage = Signal(str)  # 阶段提示，比如“正在加载模型”

    def __init__(self, source: Path, dest: Path, options: SortOptions, parent=None):
        super().__init__(parent)
        self._source = source
        self._dest = dest
        self._options = options

    def run(self) -> None:
        try:
            classifier = None
            if self._options.needs_category:
                classifier = create_classifier(self._options)
                if isinstance(classifier, ClipClassifier):
                    self.stage.emit('正在加载 AI 模型（首次使用需要下载，请稍候）…')
                    classifier.prepare()
                self.stage.emit('正在识别图片内容…')
            if self.is_canceled():
                return
            plan = planner.build_plan(self._source, self._dest, self._options,
                                      progress=self._emit_progress,
                                      cancel=self.is_canceled,
                                      classifier=classifier)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished_plan.emit(plan)


class ExecuteWorker(_CancelableThread):
    """按计划搬文件。"""

    finished_result = Signal(object)
    failed = Signal(str)

    def __init__(self, plan: Plan, parent=None):
        super().__init__(parent)
        self._plan = plan

    def run(self) -> None:
        try:
            result = executor.execute(self._plan, progress=self._emit_progress,
                                      cancel=self.is_canceled)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished_result.emit(result)


class UndoWorker(_CancelableThread):
    """回滚上一次整理。"""

    finished_result = Signal(object)
    failed = Signal(str)

    def __init__(self, journal_path: Path, parent=None):
        super().__init__(parent)
        self._journal_path = journal_path

    def run(self) -> None:
        try:
            result = executor.undo(self._journal_path, progress=self._emit_progress)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished_result.emit(result)


class ThumbnailLoader(QThread):
    """按需加载缩略图：只做表格里正在看得见的那些行。"""

    ready = Signal(int, object)  # 行号 / QImage

    def __init__(self, size: int = 48, parent=None):
        super().__init__(parent)
        self._size = size
        self._queue = deque()
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stopping = False

    def request(self, items) -> None:
        """items 是 (行号, 路径) 的序列。"""
        if not items:
            return
        with self._lock:
            self._queue.extend(items)
        self._wake.set()

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()

    def stop(self) -> None:
        self._stopping = True
        self.clear()
        self._wake.set()

    def run(self) -> None:
        while not self._stopping:
            with self._lock:
                item = self._queue.popleft() if self._queue else None
            if item is None:
                self._wake.wait(0.2)
                self._wake.clear()
                continue
            row, path = item
            image = load_thumbnail(Path(path), self._size)
            if image is not None and not self._stopping:
                self.ready.emit(row, image)


def load_thumbnail(path: Path, size: int):
    """读一张缩略图，失败返回 None。Qt 读不了的（比如 HEIC）交给 Pillow。"""
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    source = reader.size()
    if source.isValid() and source.width() > 0 and source.height() > 0:
        scale = min(size / source.width(), size / source.height(), 1.0)
        reader.setScaledSize(QSize(max(int(source.width() * scale), 1),
                                   max(int(source.height() * scale), 1)))
    image = reader.read()
    if not image.isNull():
        return image
    return _pillow_thumbnail(path, size)


def _pillow_thumbnail(path: Path, size: int):
    try:
        from PIL import Image
        from PIL.ImageQt import ImageQt

        with Image.open(path) as opened:
            image = opened.convert('RGBA')
            image.thumbnail((size, size))
            return QImage(ImageQt(image))
    except Exception:
        return None
