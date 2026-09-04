# -*- coding: utf-8 -*-

"""从图片里取“拍摄日期”：优先 EXIF，其次文件名，最后文件修改时间。"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from .models import (SOURCE_EXIF, SOURCE_FILENAME, SOURCE_MTIME, SOURCE_NONE,
                     SortOptions)

# Exif IFD 指针，DateTimeOriginal/DateTimeDigitized 存在这个子 IFD 里
_EXIF_IFD = 0x8769
_TAG_DATETIME_ORIGINAL = 0x9003
_TAG_DATETIME_DIGITIZED = 0x9004
_TAG_DATETIME = 0x0132  # IFD0 里的修改时间，最后才用

_MIN_YEAR = 1900

# 文件名里常见的日期写法：20240501_120000 / 2024-05-01 / IMG_20240501 / PXL_20240501_...
_FILENAME_PATTERNS = (
    re.compile(r'(?<!\d)(?P<y>19\d{2}|20\d{2})(?P<m>0[1-9]|1[0-2])(?P<d>0[1-9]|[12]\d|3[01])'
               r'[_\-\s]?(?P<H>[01]\d|2[0-3])(?P<M>[0-5]\d)(?P<S>[0-5]\d)(?:\d{1,3})?(?!\d)'),
    re.compile(r'(?<!\d)(?P<y>19\d{2}|20\d{2})[-_.](?P<m>0[1-9]|1[0-2])[-_.](?P<d>0[1-9]|[12]\d|3[01])(?!\d)'),
    re.compile(r'(?<!\d)(?P<y>19\d{2}|20\d{2})(?P<m>0[1-9]|1[0-2])(?P<d>0[1-9]|[12]\d|3[01])(?!\d)'),
)


# 装了 pillow-heif 就顺带支持 iPhone 的 HEIC；没装也不影响其它格式
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:
    pass


def _sane(dt: Optional[datetime]) -> Optional[datetime]:
    """挡掉 0000:00:00 之类的垃圾时间和明显穿越的未来时间。"""
    if dt is None:
        return None
    if dt.year < _MIN_YEAR:
        return None
    if dt > datetime.now().replace(hour=23, minute=59, second=59):
        return None
    return dt


def _parse_exif_datetime(raw) -> Optional[datetime]:
    """EXIF 时间形如 '2024:05:01 12:00:00'，也见过用 '-' 或缺秒的。"""
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', 'ignore')
    text = str(raw).strip().replace('/', ':').replace('-', ':')
    text = re.sub(r'\s+', ' ', text).strip('\x00 ')
    for fmt in ('%Y:%m:%d %H:%M:%S', '%Y:%m:%d %H:%M', '%Y:%m:%d'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def read_exif_datetime(path: Path) -> Optional[datetime]:
    """读 EXIF 拍摄时间；文件损坏、格式不支持时返回 None（不抛异常）。"""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None
            candidates = []
            try:
                sub = exif.get_ifd(_EXIF_IFD)
            except Exception:
                sub = {}
            if sub:
                candidates.append(sub.get(_TAG_DATETIME_ORIGINAL))
                candidates.append(sub.get(_TAG_DATETIME_DIGITIZED))
            candidates.append(exif.get(_TAG_DATETIME_ORIGINAL))
            candidates.append(exif.get(_TAG_DATETIME))
            for raw in candidates:
                dt = _sane(_parse_exif_datetime(raw))
                if dt:
                    return dt
    except Exception:
        return None
    return None


def read_filename_datetime(name: str) -> Optional[datetime]:
    """从文件名里抠日期，抠不到返回 None。"""
    for pattern in _FILENAME_PATTERNS:
        m = pattern.search(name)
        if not m:
            continue
        g = m.groupdict()
        try:
            dt = datetime(int(g['y']), int(g['m']), int(g['d']),
                          int(g.get('H') or 0), int(g.get('M') or 0), int(g.get('S') or 0))
        except ValueError:
            continue
        dt = _sane(dt)
        if dt:
            return dt
    return None


def resolve_datetime(path: Path, options: SortOptions) -> Tuple[Optional[datetime], str]:
    """按 EXIF → 文件名 → 修改时间的顺序取日期，返回 (时间, 来源说明)。"""
    if options.use_exif:
        dt = read_exif_datetime(path)
        if dt:
            return dt, SOURCE_EXIF
    if options.use_filename:
        dt = read_filename_datetime(path.name)
        if dt:
            return dt, SOURCE_FILENAME
    if options.use_mtime:
        try:
            dt = _sane(datetime.fromtimestamp(path.stat().st_mtime))
        except OSError:
            dt = None
        if dt:
            return dt, SOURCE_MTIME
    return None, SOURCE_NONE
