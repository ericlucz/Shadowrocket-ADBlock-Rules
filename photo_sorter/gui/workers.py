# -*- coding: utf-8 -*-

"""把扫描、执行、撤销放到后台线程，别卡住界面。"""

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ..core import executor, planner
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

    def __init__(self, source: Path, dest: Path, options: SortOptions, parent=None):
        super().__init__(parent)
        self._source = source
        self._dest = dest
        self._options = options

    def run(self) -> None:
        try:
            plan = planner.build_plan(self._source, self._dest, self._options,
                                      progress=self._emit_progress,
                                      cancel=self.is_canceled)
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
