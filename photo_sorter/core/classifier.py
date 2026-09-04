# -*- coding: utf-8 -*-

"""按图片内容分类。

两种实现：
- HeuristicClassifier：只看尺寸、格式、EXIF 和配色，不需要模型，秒出结果；
- ClipClassifier：本地跑 CLIP 模型，认得出画面里是人是猫还是风景，第一次用要下载模型。
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import (CATEGORY_UNKNOWN, CLASSIFIER_CLIP, DEFAULT_CLIP_CATEGORIES,
                     SortOptions)

# 文件名里出现这些词，基本可以确定是截图
_SCREENSHOT_HINTS = ('screenshot', 'screen shot', 'screen_shot', 'screencapture',
                     'snipaste', '截屏', '截图', '屏幕快照', '屏幕截图')

# 常见屏幕分辨率，命中就更倾向判成截图
_SCREEN_SIZES = {
    (1920, 1080), (1080, 1920), (2560, 1440), (1440, 2560), (3840, 2160),
    (1366, 768), (1280, 720), (2880, 1800), (2560, 1600), (1440, 900),
    (750, 1334), (1125, 2436), (1170, 2532), (1179, 2556), (1284, 2778),
    (1290, 2796), (828, 1792), (1242, 2688), (1080, 2340), (1080, 2400),
}

# CLIP 用的提示词：文件夹名（中文）→ 给模型看的英文描述
_CLIP_PROMPTS: Dict[str, str] = {
    '人物': 'a photo of a person',
    '合影': 'a group photo of several people',
    '风景': 'a landscape photo of scenery, mountains or the sea',
    '美食': 'a photo of food or a meal',
    '动物': 'a photo of an animal or a pet',
    '植物': 'a photo of a plant or flowers',
    '建筑': 'a photo of a building or architecture',
    '截图': 'a screenshot of a computer or phone screen',
    '文档': 'a scanned document, a receipt or a page of text',
    '车辆': 'a photo of a car or other vehicle',
    '夜景': 'a photo taken at night with city lights',
    '天空': 'a photo of the sky or clouds',
    '艺术': 'a drawing, painting or illustration',
    '其它': 'a random photo',
}


def clip_prompt(category: str) -> str:
    """没预设过的分类就直接用中文字面意思拼一句英文提示。"""
    return _CLIP_PROMPTS.get(category, 'a photo of %s' % category)


class BaseClassifier:
    """分类器接口。classify 必须返回 (分类名, 置信度)，且不抛异常。"""

    name = ''

    def prepare(self) -> None:
        """可选：提前加载模型，避免第一张图特别慢。"""

    def classify(self, path: Path) -> Tuple[str, float]:
        raise NotImplementedError


class HeuristicClassifier(BaseClassifier):
    """不用模型，靠尺寸、格式、EXIF 和配色判断。"""

    name = 'heuristic'

    def classify(self, path: Path) -> Tuple[str, float]:
        try:
            from PIL import Image
        except ImportError:
            return CATEGORY_UNKNOWN, 0.0

        lowered = path.name.lower()
        if any(hint in lowered for hint in _SCREENSHOT_HINTS):
            return '截图', 1.0

        try:
            with Image.open(path) as image:
                width, height = image.size
                fmt = (image.format or '').upper()
                animated = getattr(image, 'n_frames', 1) > 1
                exif = image.getexif() or {}
                has_camera = bool(exif.get(0x010F) or exif.get(0x0110))  # Make / Model
                colors = self._count_colors(image)
        except Exception:
            return CATEGORY_UNKNOWN, 0.0

        if animated:
            return '动图', 1.0
        if max(width, height) <= 256:
            return '图标', 0.8

        long_side, short_side = max(width, height), max(min(width, height), 1)
        if long_side / short_side >= 3:
            return '长图', 0.8
        if has_camera:
            return '照片', 0.9
        if (width, height) in _SCREEN_SIZES and fmt in ('PNG', 'BMP'):
            return '截图', 0.8
        if colors is not None and colors <= 48:
            # 颜色数很少，多半是图标、logo、纯色图或者简单插画
            return '图形', 0.7
        if fmt == 'PNG' and colors is not None and colors <= 512:
            return '截图', 0.5
        return '照片', 0.5

    @staticmethod
    def _count_colors(image) -> Optional[int]:
        """在缩略图上数颜色，够用又便宜。"""
        try:
            small = image.convert('RGB').copy()
            small.thumbnail((64, 64))
            colors = small.getcolors(maxcolors=8192)
        except Exception:
            return None
        return len(colors) if colors else None


class ClipClassifier(BaseClassifier):
    """本地 CLIP 模型：把图片和每个分类的英文描述比相似度，取最像的那个。"""

    name = 'clip'

    def __init__(self, categories=DEFAULT_CLIP_CATEGORIES,
                 model_name: str = 'ViT-B-32', pretrained: str = 'openai',
                 min_confidence: float = 0.0):
        self.categories: List[str] = [c for c in categories if c.strip()] or list(DEFAULT_CLIP_CATEGORIES)
        self.model_name = model_name
        self.pretrained = pretrained
        self.min_confidence = min_confidence
        self._model = None
        self._preprocess = None
        self._text_features = None
        self._torch = None

    @staticmethod
    def is_installed() -> bool:
        """只看依赖装没装，不下载模型。"""
        try:
            import importlib.util
            return (importlib.util.find_spec('torch') is not None
                    and importlib.util.find_spec('open_clip') is not None)
        except Exception:
            return False

    def prepare(self) -> None:
        """加载模型并把分类描述编码好（只做一次，可能要下载模型）。"""
        if self._model is not None:
            return
        import open_clip
        import torch

        model, _, preprocess = open_clip.create_model_and_transforms(
            self.model_name, pretrained=self.pretrained)
        model.eval()
        tokenizer = open_clip.get_tokenizer(self.model_name)
        tokens = tokenizer([clip_prompt(c) for c in self.categories])
        with torch.no_grad():
            features = model.encode_text(tokens)
            features /= features.norm(dim=-1, keepdim=True)

        self._torch = torch
        self._model = model
        self._preprocess = preprocess
        self._text_features = features

    def classify(self, path: Path) -> Tuple[str, float]:
        try:
            self.prepare()
            from PIL import Image

            with Image.open(path) as image:
                tensor = self._preprocess(image.convert('RGB')).unsqueeze(0)
            with self._torch.no_grad():
                features = self._model.encode_image(tensor)
                features /= features.norm(dim=-1, keepdim=True)
                scores = (100.0 * features @ self._text_features.T).softmax(dim=-1)[0]
            index = int(scores.argmax())
            confidence = float(scores[index])
        except Exception:
            return CATEGORY_UNKNOWN, 0.0
        if confidence < self.min_confidence:
            return CATEGORY_UNKNOWN, confidence
        return self.categories[index], confidence


def create_classifier(options: SortOptions) -> Optional[BaseClassifier]:
    """按选项造分类器；不需要分类时返回 None。

    选了 CLIP 但依赖没装，就退回快速规则，总比整理不下去强。
    """
    if not options.needs_category:
        return None
    if options.classifier == CLASSIFIER_CLIP and ClipClassifier.is_installed():
        return ClipClassifier(options.categories, options.clip_model, options.clip_pretrained)
    return HeuristicClassifier()
