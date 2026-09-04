# -*- coding: utf-8 -*-

"""扫描源文件夹，算出“每个文件该去哪”，但不动任何文件。"""

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from .classifier import BaseClassifier, create_classifier
from .datesource import resolve_datetime
from .models import (ACTION_COPY, ACTION_MOVE, ACTION_SKIP, CATEGORY_UNKNOWN,
                     CONFLICT_SKIP, GROUP_CATEGORY, GROUP_CATEGORY_DATE,
                     GROUP_DATE_CATEGORY, OP_COPY, SOURCE_NONE, Plan, PlanItem,
                     SortOptions)

ProgressCb = Optional[Callable[[int, int, Path], None]]
CancelCb = Optional[Callable[[], bool]]

_CHUNK = 1024 * 1024


def scan_images(root: Path, options: SortOptions) -> List[Path]:
    """列出源文件夹下的图片文件，跳过隐藏文件和隐藏目录。"""
    exts = options.normalized_extensions()
    found: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith('.'))
        for name in sorted(filenames):
            if name.startswith('.'):
                continue
            if os.path.splitext(name)[1].lower() in exts:
                found.append(Path(dirpath) / name)
        if not options.recursive:
            dirnames[:] = []
    return found


def _sanitize(name: str) -> str:
    """文件夹名里不能有路径分隔符和 Windows 禁用字符。"""
    cleaned = ''.join('_' if ch in '\\/:*?"<>|' else ch for ch in name).strip(' .')
    return cleaned or CATEGORY_UNKNOWN


def _date_parts(taken_at: Optional[datetime], options: SortOptions) -> list:
    """把日期模板展开成一层层文件夹名。"""
    if taken_at is None:
        return [_sanitize(options.unknown_dir)]
    rendered = taken_at.strftime(options.pattern)
    return [_sanitize(part) for part in rendered.replace('\\', '/').split('/') if part.strip()]


def _target_dir(dest_root: Path, taken_at: Optional[datetime], category: str,
                options: SortOptions) -> Path:
    """按归类方式拼出目标文件夹。"""
    category_parts = [_sanitize(category or CATEGORY_UNKNOWN)]
    if options.group_by == GROUP_CATEGORY:
        parts = category_parts
    elif options.group_by == GROUP_CATEGORY_DATE:
        parts = category_parts + _date_parts(taken_at, options)
    elif options.group_by == GROUP_DATE_CATEGORY:
        parts = _date_parts(taken_at, options) + category_parts
    else:
        parts = _date_parts(taken_at, options)
    target = dest_root
    for part in parts:
        target = target / part
    return target


def unique_name(target: Path, taken: Optional[set] = None) -> Path:
    """同名时追加 (1)、(2)… 直到不冲突。taken 是本次计划里已经占用的路径。"""
    taken = taken or set()
    if not target.exists() and target not in taken:
        return target
    stem, suffix = target.stem, target.suffix
    index = 1
    while True:
        candidate = target.with_name('%s (%d)%s' % (stem, index, suffix))
        if not candidate.exists() and candidate not in taken:
            return candidate
        index += 1


def file_digest(path: Path) -> Optional[str]:
    """整份文件的 sha1，读不动就返回 None。"""
    h = hashlib.sha1()
    try:
        with open(path, 'rb') as fp:
            for chunk in iter(lambda: fp.read(_CHUNK), b''):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def same_content(a: Path, b: Path) -> bool:
    """先比大小再比摘要，避免对大文件白算一遍。"""
    try:
        if a.stat().st_size != b.stat().st_size:
            return False
    except OSError:
        return False
    da = file_digest(a)
    return da is not None and da == file_digest(b)


def build_plan(source_root: Path, dest_root: Path, options: SortOptions,
               progress: ProgressCb = None, cancel: CancelCb = None,
               classifier: Optional[BaseClassifier] = None) -> Plan:
    """扫描并生成整理计划；只读磁盘，不做任何修改。"""
    source_root = Path(source_root).resolve()
    dest_root = Path(dest_root).resolve()
    files = scan_images(source_root, options)
    plan = Plan(items=[], source_root=source_root, dest_root=dest_root, options=options)
    total = len(files)
    taken: set = set()
    action = ACTION_COPY if options.operation == OP_COPY else ACTION_MOVE
    if options.needs_category and classifier is None:
        classifier = create_classifier(options)

    for index, path in enumerate(files, 1):
        if cancel and cancel():
            break
        if progress:
            progress(index, total, path)

        if options.needs_date:
            taken_at, date_source = resolve_datetime(path, options)
        else:
            taken_at, date_source = None, SOURCE_NONE
        category = classifier.classify(path)[0] if classifier is not None else ''
        target = _target_dir(dest_root, taken_at, category, options) / path.name

        if target == path:
            plan.items.append(PlanItem(path, target, ACTION_SKIP, taken_at,
                                       date_source, category, '已在目标位置'))
            continue

        if target.exists() or target in taken:
            if options.skip_same_content and target.exists() and same_content(path, target):
                plan.items.append(PlanItem(path, target, ACTION_SKIP, taken_at,
                                           date_source, category, '目标已存在相同文件'))
                continue
            if options.on_conflict == CONFLICT_SKIP:
                plan.items.append(PlanItem(path, target, ACTION_SKIP, taken_at,
                                           date_source, category, '目标已存在同名文件'))
                continue
            target = unique_name(target, taken)

        taken.add(target)
        plan.items.append(PlanItem(path, target, action, taken_at, date_source, category, ''))

    return plan
