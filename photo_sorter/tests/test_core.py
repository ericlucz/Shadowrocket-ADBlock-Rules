# -*- coding: utf-8 -*-

"""核心逻辑的测试，不涉及界面。"""

import os
import shutil
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path

from PIL import Image

from photo_sorter.core import executor, planner
from photo_sorter.core.classifier import (ClipClassifier, HeuristicClassifier,
                                          clip_prompt, create_classifier)
from photo_sorter.core.datesource import (read_exif_datetime,
                                          read_filename_datetime,
                                          resolve_datetime)
from photo_sorter.core.models import (ACTION_SKIP, CATEGORY_UNKNOWN,
                                      CLASSIFIER_CLIP, CONFLICT_SKIP,
                                      GROUP_CATEGORY, GROUP_CATEGORY_DATE,
                                      GROUP_DATE_CATEGORY, OP_COPY,
                                      SOURCE_EXIF, SOURCE_FILENAME,
                                      SOURCE_MTIME, SOURCE_NONE, SortOptions)


def make_jpeg(path: Path, taken: str = None, color=(255, 0, 0)) -> Path:
    """生成一张小 JPEG，taken 形如 '2024:05:01 12:00:00'。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new('RGB', (16, 16), color)
    if taken:
        exif = Image.Exif()
        exif[0x8769] = {0x9003: taken}
        image.save(path, 'JPEG', exif=exif)
    else:
        image.save(path, 'JPEG')
    return path


class TempCaseBase(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='photo_sorter_test_'))
        self.src = self.tmp / 'src'
        self.src.mkdir()
        # 别把测试日志写进用户主目录
        self._real_journal_dir = executor.JOURNAL_DIR
        executor.JOURNAL_DIR = self.tmp / 'journals'

    def tearDown(self):
        executor.JOURNAL_DIR = self._real_journal_dir
        shutil.rmtree(self.tmp, ignore_errors=True)


class DateSourceTest(TempCaseBase):

    def test_exif_datetime_is_read(self):
        path = make_jpeg(self.src / 'a.jpg', '2024:05:01 12:30:00')
        self.assertEqual(read_exif_datetime(path), datetime(2024, 5, 1, 12, 30))

    def test_broken_file_does_not_raise(self):
        path = self.src / 'broken.jpg'
        path.write_bytes(b'not really a jpeg')
        self.assertIsNone(read_exif_datetime(path))

    def test_zero_exif_date_is_rejected(self):
        path = make_jpeg(self.src / 'zero.jpg', '0000:00:00 00:00:00')
        self.assertIsNone(read_exif_datetime(path))

    def test_filename_dates(self):
        self.assertEqual(read_filename_datetime('IMG_20240501_123001.jpg'),
                         datetime(2024, 5, 1, 12, 30, 1))
        self.assertEqual(read_filename_datetime('PXL_20230115_101112345.jpg'),
                         datetime(2023, 1, 15, 10, 11, 12))
        self.assertEqual(read_filename_datetime('2024-05-01.png'), datetime(2024, 5, 1))
        self.assertIsNone(read_filename_datetime('20241332.jpg'))
        self.assertIsNone(read_filename_datetime('随手拍.jpg'))

    def test_resolution_order(self):
        options = SortOptions()
        exif_file = make_jpeg(self.src / 'IMG_20200101_000000.jpg', '2024:05:01 12:30:00')
        self.assertEqual(resolve_datetime(exif_file, options),
                         (datetime(2024, 5, 1, 12, 30), SOURCE_EXIF))

        name_file = make_jpeg(self.src / 'IMG_20200101_000000_b.jpg')
        self.assertEqual(resolve_datetime(name_file, options),
                         (datetime(2020, 1, 1), SOURCE_FILENAME))

        plain = make_jpeg(self.src / 'plain.jpg')
        os.utime(plain, (1700000000, 1700000000))
        _, source = resolve_datetime(plain, options)
        self.assertEqual(source, SOURCE_MTIME)

        _, source = resolve_datetime(plain, SortOptions(use_mtime=False))
        self.assertEqual(source, SOURCE_NONE)


class PlannerTest(TempCaseBase):

    def test_targets_follow_pattern(self):
        make_jpeg(self.src / 'a.jpg', '2024:05:01 12:30:00')
        make_jpeg(self.src / 'sub' / 'b.jpg', '2023:12:31 23:00:00')
        plan = planner.build_plan(self.src, self.tmp / 'out', SortOptions())
        targets = {i.source.name: i.dest for i in plan.items}
        self.assertEqual(targets['a.jpg'], self.tmp / 'out' / '2024' / '2024-05' / 'a.jpg')
        self.assertEqual(targets['b.jpg'], self.tmp / 'out' / '2023' / '2023-12' / 'b.jpg')

    def test_non_recursive_ignores_subfolders(self):
        make_jpeg(self.src / 'a.jpg', '2024:05:01 12:30:00')
        make_jpeg(self.src / 'sub' / 'b.jpg', '2024:05:01 12:30:00')
        plan = planner.build_plan(self.src, self.src, SortOptions(recursive=False))
        self.assertEqual([i.source.name for i in plan.items], ['a.jpg'])

    def test_non_images_and_hidden_files_ignored(self):
        make_jpeg(self.src / 'a.jpg', '2024:05:01 12:30:00')
        (self.src / 'note.txt').write_text('hi', encoding='utf-8')
        (self.src / '.hidden.jpg').write_bytes(b'x')
        plan = planner.build_plan(self.src, self.src, SortOptions())
        self.assertEqual([i.source.name for i in plan.items], ['a.jpg'])

    def test_unknown_date_goes_to_its_own_folder(self):
        make_jpeg(self.src / 'plain.jpg')
        options = SortOptions(use_mtime=False)
        plan = planner.build_plan(self.src, self.src, options)
        self.assertEqual(plan.items[0].dest, self.src / '未知日期' / 'plain.jpg')

    def test_already_sorted_file_is_skipped(self):
        make_jpeg(self.src / '2024' / '2024-05' / 'a.jpg', '2024:05:01 12:30:00')
        plan = planner.build_plan(self.src, self.src, SortOptions())
        self.assertEqual(plan.items[0].action, ACTION_SKIP)
        self.assertEqual(plan.items[0].reason, '已在目标位置')

    def test_same_name_different_content_is_renamed(self):
        make_jpeg(self.src / 'one' / 'a.jpg', '2024:05:01 12:30:00', color=(255, 0, 0))
        make_jpeg(self.src / 'two' / 'a.jpg', '2024:05:01 12:30:00', color=(0, 0, 255))
        plan = planner.build_plan(self.src, self.tmp / 'out', SortOptions())
        names = sorted(i.dest.name for i in plan.items)
        self.assertEqual(names, ['a (1).jpg', 'a.jpg'])

    def test_identical_file_already_at_target_is_skipped(self):
        make_jpeg(self.src / '2024' / '2024-05' / 'a.jpg', '2024:05:01 12:30:00')
        shutil.copy2(self.src / '2024' / '2024-05' / 'a.jpg', self.src / 'a.jpg')
        plan = planner.build_plan(self.src, self.src, SortOptions())
        loose = [i for i in plan.items if i.source == self.src / 'a.jpg'][0]
        self.assertEqual(loose.action, ACTION_SKIP)
        self.assertEqual(loose.reason, '目标已存在相同文件')

    def test_conflict_skip_option(self):
        make_jpeg(self.src / 'one' / 'a.jpg', '2024:05:01 12:30:00', color=(255, 0, 0))
        make_jpeg(self.src / 'two' / 'a.jpg', '2024:05:01 12:30:00', color=(0, 0, 255))
        plan = planner.build_plan(self.src, self.tmp / 'out',
                                  SortOptions(on_conflict=CONFLICT_SKIP))
        actions = sorted(i.action for i in plan.items)
        self.assertEqual(actions, ['move', ACTION_SKIP])


class ExecutorTest(TempCaseBase):

    def test_move_then_undo_restores_everything(self):
        original = make_jpeg(self.src / 'a.jpg', '2024:05:01 12:30:00')
        digest_before = planner.file_digest(original)
        plan = planner.build_plan(self.src, self.src, SortOptions())
        result = executor.execute(plan)

        moved = self.src / '2024' / '2024-05' / 'a.jpg'
        self.assertEqual(result.done, 1)
        self.assertTrue(moved.exists())
        self.assertFalse(original.exists())

        undo_result = executor.undo(result.journal_path)
        self.assertEqual(undo_result.done, 1)
        self.assertTrue(original.exists())
        self.assertFalse(moved.exists())
        self.assertFalse((self.src / '2024').exists())  # 空文件夹被清掉
        self.assertEqual(planner.file_digest(original), digest_before)

    def test_copy_keeps_original_and_undo_removes_the_copy(self):
        original = make_jpeg(self.src / 'a.jpg', '2024:05:01 12:30:00')
        plan = planner.build_plan(self.src, self.tmp / 'out', SortOptions(operation=OP_COPY))
        result = executor.execute(plan)
        copied = self.tmp / 'out' / '2024' / '2024-05' / 'a.jpg'
        self.assertTrue(original.exists() and copied.exists())

        executor.undo(result.journal_path)
        self.assertTrue(original.exists())
        self.assertFalse(copied.exists())

    def test_existing_target_is_never_overwritten(self):
        make_jpeg(self.src / 'a.jpg', '2024:05:01 12:30:00', color=(255, 0, 0))
        plan = planner.build_plan(self.src, self.src, SortOptions())
        # 计划做好之后目标位置才冒出同名文件
        other = make_jpeg(self.src / '2024' / '2024-05' / 'a.jpg', color=(0, 255, 0))
        other_digest = planner.file_digest(other)
        result = executor.execute(plan)
        self.assertEqual(result.done, 1)
        self.assertEqual(planner.file_digest(other), other_digest)
        self.assertTrue((self.src / '2024' / '2024-05' / 'a (1).jpg').exists())

    def test_missing_source_is_reported_not_raised(self):
        make_jpeg(self.src / 'a.jpg', '2024:05:01 12:30:00')
        plan = planner.build_plan(self.src, self.src, SortOptions())
        (self.src / 'a.jpg').unlink()
        result = executor.execute(plan)
        self.assertEqual(result.done, 0)
        self.assertEqual(result.failed, 1)

    def test_no_journal_when_nothing_was_done(self):
        plan = planner.build_plan(self.src, self.src, SortOptions())
        result = executor.execute(plan)
        self.assertIsNone(result.journal_path)


class StubClassifier(HeuristicClassifier):
    """测试用：按文件名前缀给分类，不看画面。"""

    def classify(self, path):
        return path.name.split('_')[0], 1.0


class HeuristicClassifierTest(TempCaseBase):

    def setUp(self):
        super().setUp()
        self.classifier = HeuristicClassifier()

    def category(self, path):
        return self.classifier.classify(path)[0]

    def test_screenshot_by_filename(self):
        path = make_jpeg(self.src / 'Screenshot 2024-05-01.png')
        self.assertEqual(self.category(path), '截图')

    def test_animated_gif(self):
        path = self.src / 'dance.gif'
        frames = [Image.new('RGB', (64, 64), (r, 0, 0)) for r in (0, 128, 255)]
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=100, loop=0)
        self.assertEqual(self.category(path), '动图')

    def test_tiny_image_is_icon(self):
        path = self.src / 'small.png'
        Image.new('RGB', (32, 32), (10, 20, 30)).save(path)
        self.assertEqual(self.category(path), '图标')

    def test_very_long_image(self):
        path = self.src / 'long.png'
        Image.new('RGB', (600, 4000), (10, 20, 30)).save(path)
        self.assertEqual(self.category(path), '长图')

    def test_camera_exif_means_photo(self):
        path = self.src / 'cam.jpg'
        image = Image.new('RGB', (800, 600), (30, 60, 90))
        exif = Image.Exif()
        exif[0x010F] = 'Apple'
        exif[0x0110] = 'iPhone 15'
        image.save(path, 'JPEG', exif=exif)
        self.assertEqual(self.category(path), '照片')

    def test_flat_color_image_is_graphic(self):
        path = self.src / 'flat.png'
        Image.new('RGB', (900, 700), (200, 30, 30)).save(path)
        self.assertEqual(self.category(path), '图形')

    def test_broken_file_falls_back(self):
        path = self.src / 'broken.jpg'
        path.write_bytes(b'nope')
        self.assertEqual(self.category(path), CATEGORY_UNKNOWN)

    def test_clip_prompts_cover_custom_categories(self):
        self.assertIn('landscape', clip_prompt('风景'))
        self.assertIn('自定义分类', clip_prompt('自定义分类'))

    def test_clip_falls_back_when_not_installed(self):
        options = SortOptions(group_by=GROUP_CATEGORY, classifier=CLASSIFIER_CLIP)
        classifier = create_classifier(options)
        expected = ClipClassifier if ClipClassifier.is_installed() else HeuristicClassifier
        self.assertIsInstance(classifier, expected)

    def test_no_classifier_when_grouping_by_date_only(self):
        self.assertIsNone(create_classifier(SortOptions()))


def _torch_available() -> bool:
    import importlib.util
    return importlib.util.find_spec('torch') is not None


@unittest.skipUnless(_torch_available(), '没装 torch，跳过 CLIP 相关测试')
class ClipClassifierTest(TempCaseBase):
    """用假的 open_clip 顶替真模型，验证取分类的那套流程本身是对的。"""

    def setUp(self):
        super().setUp()
        import torch

        text_features = torch.tensor([[1.0, 0.0], [0.0, 1.0]])
        image_features = torch.tensor([[0.0, 1.0]])  # 与第二个分类最像

        class FakeModel:
            def eval(self):
                return self

            def encode_text(self, tokens):
                return text_features.clone()

            def encode_image(self, tensor):
                return image_features.clone()

        fake = types.ModuleType('open_clip')
        fake.create_model_and_transforms = (
            lambda name, pretrained=None: (FakeModel(), None,
                                           lambda image: torch.zeros(3, 4, 4)))
        fake.get_tokenizer = lambda name: (lambda prompts: prompts)
        self._saved = sys.modules.get('open_clip')
        sys.modules['open_clip'] = fake
        self.image = make_jpeg(self.src / 'a.jpg', '2024:05:01 12:30:00')

    def tearDown(self):
        if self._saved is None:
            sys.modules.pop('open_clip', None)
        else:
            sys.modules['open_clip'] = self._saved
        super().tearDown()

    def test_picks_the_closest_category(self):
        classifier = ClipClassifier(('人物', '风景'))
        category, confidence = classifier.classify(self.image)
        self.assertEqual(category, '风景')
        self.assertGreater(confidence, 0.9)

    def test_model_is_loaded_only_once(self):
        classifier = ClipClassifier(('人物', '风景'))
        classifier.prepare()
        model = classifier._model
        classifier.prepare()
        self.assertIs(classifier._model, model)

    def test_low_confidence_falls_back_to_unknown(self):
        classifier = ClipClassifier(('人物', '风景'), min_confidence=1.1)
        self.assertEqual(classifier.classify(self.image)[0], CATEGORY_UNKNOWN)

    def test_unreadable_file_is_not_fatal(self):
        broken = self.src / 'broken.jpg'
        broken.write_bytes(b'nope')
        self.assertEqual(ClipClassifier(('人物', '风景')).classify(broken),
                         (CATEGORY_UNKNOWN, 0.0))


class GroupingTest(TempCaseBase):

    def setUp(self):
        super().setUp()
        make_jpeg(self.src / '风景_a.jpg', '2024:05:01 12:30:00')

    def plan_with(self, group_by):
        options = SortOptions(group_by=group_by)
        return planner.build_plan(self.src, self.tmp / 'out', options,
                                  classifier=StubClassifier())

    def test_group_by_category(self):
        item = self.plan_with(GROUP_CATEGORY).items[0]
        self.assertEqual(item.dest, self.tmp / 'out' / '风景' / '风景_a.jpg')
        self.assertEqual(item.category, '风景')
        self.assertIsNone(item.taken_at)  # 不按日期归类时就不去读日期

    def test_category_then_date(self):
        item = self.plan_with(GROUP_CATEGORY_DATE).items[0]
        self.assertEqual(item.dest,
                         self.tmp / 'out' / '风景' / '2024' / '2024-05' / '风景_a.jpg')

    def test_date_then_category(self):
        item = self.plan_with(GROUP_DATE_CATEGORY).items[0]
        self.assertEqual(item.dest,
                         self.tmp / 'out' / '2024' / '2024-05' / '风景' / '风景_a.jpg')

    def test_category_name_is_sanitized(self):
        class SlashClassifier(HeuristicClassifier):
            def classify(self, path):
                return 'a/b:c', 1.0

        plan = planner.build_plan(self.src, self.tmp / 'out',
                                  SortOptions(group_by=GROUP_CATEGORY),
                                  classifier=SlashClassifier())
        self.assertEqual(plan.items[0].dest.parent, self.tmp / 'out' / 'a_b_c')


if __name__ == '__main__':
    unittest.main()
