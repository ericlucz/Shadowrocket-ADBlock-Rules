# -*- coding: utf-8 -*-

"""按计划真正搬文件，并写下操作日志以便撤销。"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from .models import ACTION_COPY, ExecResult, Plan
from .planner import unique_name

ProgressCb = Optional[Callable[[int, int, Path], None]]
CancelCb = Optional[Callable[[], bool]]

JOURNAL_DIR = Path.home() / '.photo_sorter' / 'journals'


def _journal_path() -> Path:
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    path = JOURNAL_DIR / ('journal-%s.jsonl' % stamp)
    index = 1
    while path.exists():
        path = JOURNAL_DIR / ('journal-%s-%d.jsonl' % (stamp, index))
        index += 1
    return path


def latest_journal() -> Optional[Path]:
    """最近一次整理的日志，没有则返回 None。"""
    if not JOURNAL_DIR.is_dir():
        return None
    journals = sorted(JOURNAL_DIR.glob('journal-*.jsonl'))
    return journals[-1] if journals else None


def execute(plan: Plan, progress: ProgressCb = None, cancel: CancelCb = None) -> ExecResult:
    """执行计划。每完成一步立即落盘日志，中途崩溃也能撤销已完成的部分。"""
    result = ExecResult(journal_path=_journal_path())
    pending = plan.pending
    result.skipped = len(plan.skipped)
    total = len(pending)

    with open(result.journal_path, 'a', encoding='utf-8') as journal:
        for index, item in enumerate(pending, 1):
            if cancel and cancel():
                result.canceled = True
                break
            if progress:
                progress(index, total, item.source)
            try:
                if not item.source.exists():
                    raise FileNotFoundError('源文件已不存在')
                created_dir = not item.dest.parent.exists()
                item.dest.parent.mkdir(parents=True, exist_ok=True)
                # 计划到执行之间可能又冒出同名文件，这里再让一次路，绝不覆盖
                target = unique_name(item.dest)
                if item.action == ACTION_COPY:
                    shutil.copy2(str(item.source), str(target))
                else:
                    shutil.move(str(item.source), str(target))
                journal.write(json.dumps({
                    'action': item.action,
                    'source': str(item.source),
                    'dest': str(target),
                    'created_dir': str(item.dest.parent) if created_dir else '',
                }, ensure_ascii=False) + '\n')
                journal.flush()
                result.done += 1
            except Exception as exc:  # 单个文件失败不该中断整批
                result.failed += 1
                result.errors.append('%s：%s' % (item.source.name, exc))

    if result.done == 0:
        try:
            result.journal_path.unlink()
        except OSError:
            pass
        result.journal_path = None
    return result


def _prune_empty_dirs(dirs: List[Path]) -> None:
    """撤销后顺手删掉自己建的空文件夹。"""
    for directory in sorted(set(dirs), key=lambda p: len(p.parts), reverse=True):
        current = directory
        while current.is_dir():
            try:
                next(current.iterdir())
                break
            except StopIteration:
                try:
                    current.rmdir()
                except OSError:
                    break
                current = current.parent
            except OSError:
                break


def undo(journal_path: Path, progress: ProgressCb = None) -> ExecResult:
    """按日志回滚：移动的搬回去，复制的删掉。任何有疑问的都不动。"""
    result = ExecResult()
    entries = []
    try:
        with open(journal_path, 'r', encoding='utf-8') as journal:
            for line in journal:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except (OSError, ValueError) as exc:
        result.failed += 1
        result.errors.append('读取日志失败：%s' % exc)
        return result

    created_dirs: List[Path] = []
    total = len(entries)
    for index, entry in enumerate(reversed(entries), 1):
        source = Path(entry['source'])
        dest = Path(entry['dest'])
        if progress:
            progress(index, total, dest)
        try:
            if not dest.exists():
                result.skipped += 1
                continue
            if entry['action'] == ACTION_COPY:
                # 只删我们复制出来的那一份，源文件必须还在，否则宁可不动
                if source.exists():
                    dest.unlink()
                    result.done += 1
                else:
                    result.skipped += 1
            else:
                if source.exists():
                    result.skipped += 1
                    continue
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dest), str(source))
                result.done += 1
            if entry.get('created_dir'):
                created_dirs.append(Path(entry['created_dir']))
        except Exception as exc:
            result.failed += 1
            result.errors.append('%s：%s' % (dest.name, exc))

    _prune_empty_dirs(created_dirs)
    if result.failed == 0:
        try:
            Path(journal_path).unlink()
        except OSError:
            pass
    return result
