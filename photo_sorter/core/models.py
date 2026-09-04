# -*- coding: utf-8 -*-

"""数据模型：整理选项、单条整理计划、整理结果。"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# 默认识别的图片扩展名（小写，含点）
DEFAULT_EXTENSIONS = (
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tif', '.tiff',
    '.webp', '.heic', '.heif', '.avif', '.dng', '.cr2', '.cr3',
    '.nef', '.arw', '.orf', '.rw2', '.raf', '.sr2',
)

# 目标文件夹层级模板，键为界面展示文本
FOLDER_PATTERNS = {
    '年 / 年-月（2024/2024-05）': '%Y/%Y-%m',
    '年-月（2024-05）': '%Y-%m',
    '年 / 月（2024/05月）': '%Y/%m月',
    '年 / 年-月-日（2024/2024-05-01）': '%Y/%Y-%m-%d',
    '年（2024）': '%Y',
}

# 归类方式
GROUP_DATE = 'date'
GROUP_CATEGORY = 'category'
GROUP_CATEGORY_DATE = 'category_date'
GROUP_DATE_CATEGORY = 'date_category'

GROUP_LABELS = {
    '按拍摄日期': GROUP_DATE,
    '按图片内容': GROUP_CATEGORY,
    '先内容再日期（风景/2024-05）': GROUP_CATEGORY_DATE,
    '先日期再内容（2024-05/风景）': GROUP_DATE_CATEGORY,
}

# 内容识别方式
CLASSIFIER_HEURISTIC = 'heuristic'
CLASSIFIER_CLIP = 'clip'

CLASSIFIER_LABELS = {
    '快速规则（看尺寸、格式、EXIF，秒出结果）': CLASSIFIER_HEURISTIC,
    '本地 AI 模型 CLIP（识别画面内容，需先下载模型）': CLASSIFIER_CLIP,
}

# CLIP 默认分类；键是文件夹名，值是给模型看的英文描述
DEFAULT_CLIP_CATEGORIES = (
    '人物', '风景', '美食', '动物', '植物', '建筑',
    '截图', '文档', '车辆', '其它',
)

CATEGORY_UNKNOWN = '其它'

# 取日期的来源
SOURCE_EXIF = 'EXIF 拍摄时间'
SOURCE_FILENAME = '文件名日期'
SOURCE_MTIME = '文件修改时间'
SOURCE_NONE = '无法识别'

# 计划条目的动作
ACTION_MOVE = 'move'
ACTION_COPY = 'copy'
ACTION_SKIP = 'skip'

OP_MOVE = 'move'
OP_COPY = 'copy'

# 目标已存在同名文件时的处理方式
CONFLICT_RENAME = 'rename'
CONFLICT_SKIP = 'skip'


@dataclass(frozen=True)
class SortOptions:
    """一次整理任务的全部可调项。"""

    pattern: str = '%Y/%Y-%m'
    operation: str = OP_MOVE
    recursive: bool = True
    use_exif: bool = True
    use_filename: bool = True
    use_mtime: bool = True
    unknown_dir: str = '未知日期'
    on_conflict: str = CONFLICT_RENAME
    skip_same_content: bool = True
    extensions: tuple = DEFAULT_EXTENSIONS
    group_by: str = GROUP_DATE
    classifier: str = CLASSIFIER_HEURISTIC
    categories: tuple = DEFAULT_CLIP_CATEGORIES
    clip_model: str = 'ViT-B-32'
    clip_pretrained: str = 'openai'

    @property
    def needs_category(self) -> bool:
        return self.group_by != GROUP_DATE

    @property
    def needs_date(self) -> bool:
        return self.group_by != GROUP_CATEGORY

    def normalized_extensions(self) -> frozenset:
        return frozenset(e.lower() if e.startswith('.') else '.' + e.lower()
                         for e in self.extensions)


@dataclass
class PlanItem:
    """一个待处理文件：从哪来、到哪去、为什么。"""

    source: Path
    dest: Path
    action: str = ACTION_MOVE
    taken_at: Optional[datetime] = None
    date_source: str = SOURCE_NONE
    category: str = ''
    reason: str = ''

    @property
    def will_change(self) -> bool:
        return self.action in (ACTION_MOVE, ACTION_COPY)


@dataclass
class Plan:
    """扫描后得到的完整计划。"""

    items: List[PlanItem] = field(default_factory=list)
    source_root: Optional[Path] = None
    dest_root: Optional[Path] = None
    options: SortOptions = field(default_factory=SortOptions)

    @property
    def pending(self) -> List[PlanItem]:
        return [i for i in self.items if i.will_change]

    @property
    def skipped(self) -> List[PlanItem]:
        return [i for i in self.items if not i.will_change]


@dataclass
class ExecResult:
    """执行结果，journal 用于撤销。"""

    done: int = 0
    skipped: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)
    journal_path: Optional[Path] = None
    canceled: bool = False
