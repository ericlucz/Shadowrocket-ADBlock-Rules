# -*- coding: utf-8 -*-

"""命令行版本：photo-sorter <源文件夹> [-d 目标文件夹] [--apply]"""

import argparse
import sys
from pathlib import Path

from .core import executor, planner
from .core.models import (CLASSIFIER_CLIP, CLASSIFIER_HEURISTIC,
                          CONFLICT_RENAME, CONFLICT_SKIP,
                          DEFAULT_CLIP_CATEGORIES, GROUP_CATEGORY,
                          GROUP_CATEGORY_DATE, GROUP_DATE, GROUP_DATE_CATEGORY,
                          OP_COPY, OP_MOVE, SortOptions)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='photo-sorter', description='按拍摄日期把图片归类到年月文件夹。')
    parser.add_argument('source', nargs='?', help='要整理的图片文件夹')
    parser.add_argument('-d', '--dest', help='目标文件夹，默认与源文件夹相同')
    parser.add_argument('-p', '--pattern', default='%Y/%Y-%m',
                        help='文件夹层级模板，默认 %%Y/%%Y-%%m')
    parser.add_argument('--copy', action='store_true', help='复制而不是移动')
    parser.add_argument('--no-recursive', action='store_true', help='不处理子文件夹')
    parser.add_argument('--no-exif', action='store_true', help='不读 EXIF')
    parser.add_argument('--no-filename-date', action='store_true', help='不从文件名识别日期')
    parser.add_argument('--no-mtime', action='store_true', help='不用文件修改时间兜底')
    parser.add_argument('--unknown-dir', default='未知日期', help='无法识别日期时的文件夹名')
    parser.add_argument('--on-conflict', choices=[CONFLICT_RENAME, CONFLICT_SKIP],
                        default=CONFLICT_RENAME, help='目标有同名文件时改名还是跳过')
    parser.add_argument('-g', '--group-by',
                        choices=[GROUP_DATE, GROUP_CATEGORY, GROUP_CATEGORY_DATE,
                                 GROUP_DATE_CATEGORY],
                        default=GROUP_DATE,
                        help='归类方式：按日期 / 按内容 / 内容+日期 / 日期+内容')
    parser.add_argument('--classifier', choices=[CLASSIFIER_HEURISTIC, CLASSIFIER_CLIP],
                        default=CLASSIFIER_HEURISTIC,
                        help='内容识别方式：快速规则或本地 CLIP 模型')
    parser.add_argument('--categories', default='',
                        help='CLIP 的分类，逗号分隔，如「人物,风景,美食」；留空用默认')
    parser.add_argument('--apply', action='store_true', help='真正执行；默认只预览')
    parser.add_argument('--undo', action='store_true', help='撤销上一次整理')
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.undo:
        journal = executor.latest_journal()
        if journal is None:
            print('没有可撤销的整理记录。')
            return 1
        result = executor.undo(journal)
        print('撤销完成：还原 %d 个，跳过 %d 个，失败 %d 个。'
              % (result.done, result.skipped, result.failed))
        for error in result.errors:
            print('  ! ' + error)
        return 0 if result.failed == 0 else 1

    if not args.source:
        print('请指定源文件夹，或用 --undo 撤销上次整理。')
        return 2
    source = Path(args.source).expanduser()
    if not source.is_dir():
        print('源文件夹不存在：%s' % source)
        return 2
    dest = Path(args.dest).expanduser() if args.dest else source

    options = SortOptions(
        pattern=args.pattern,
        operation=OP_COPY if args.copy else OP_MOVE,
        recursive=not args.no_recursive,
        use_exif=not args.no_exif,
        use_filename=not args.no_filename_date,
        use_mtime=not args.no_mtime,
        unknown_dir=args.unknown_dir,
        on_conflict=args.on_conflict,
        group_by=args.group_by,
        classifier=args.classifier,
        categories=tuple(c for c in args.categories.replace('，', ',').split(',') if c.strip())
                   or DEFAULT_CLIP_CATEGORIES,
    )

    plan = planner.build_plan(source, dest, options)
    for item in plan.items:
        if item.will_change:
            tag = item.category if not options.needs_date else item.date_source
            print('%s  ->  %s  [%s]' % (item.source.name, item.dest, tag))
        else:
            print('%s  --  %s' % (item.source.name, item.reason))
    print('共 %d 个文件，待处理 %d 个，跳过 %d 个。'
          % (len(plan.items), len(plan.pending), len(plan.skipped)))

    if not args.apply:
        print('这是预览，加 --apply 才会真正整理。')
        return 0

    result = executor.execute(plan)
    print('整理完成：处理 %d 个，失败 %d 个。' % (result.done, result.failed))
    for error in result.errors:
        print('  ! ' + error)
    if result.journal_path:
        print('可用 --undo 撤销（记录：%s）' % result.journal_path)
    return 0 if result.failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
