# 图片自动归类

一个跨平台的桌面小工具：扫描指定文件夹里的图片，按**拍摄日期**归类到 `2024/2024-05/` 这样的年月文件夹里，也可以按**图片内容**归类到「风景」「美食」「截图」这样的分类文件夹，或者两者叠着用。

界面用 PySide6（Qt）写，核心逻辑与界面分离，也可以直接当命令行工具用。

## 特点

- **预览带缩略图**：表格里直接看到每张图长什么样，只加载当前看得见的那几行，几万张图也不卡。
- **四种归类方式**：按拍摄日期、按图片内容、`风景/2024-05/`、`2024-05/风景/`，在界面里一选就换。
- **拍摄日期优先**：先读 EXIF 的 `DateTimeOriginal`；读不到就从文件名识别（`IMG_20240501_123001.jpg`、`PXL_20230115_...`、`2024-05-01.png` 等）；再不行才用文件修改时间兜底。三级来源都能在界面里单独关掉。
- **先预览再动手**：扫描只读磁盘，表格里逐条列出「原文件 → 整理后位置 → 日期是怎么来的」，确认无误再执行。
- **可撤销**：每次整理都会写一份操作日志，点「撤销上次整理」即可把文件搬回原位，顺带清理掉空文件夹。
- **不覆盖、不丢文件**：同名文件自动改成 `a (1).jpg`，或按设置跳过；目标已有内容完全相同的文件（比大小 + SHA1）时自动跳过，避免重复堆积。
- **移动或复制**：复制模式保留原件，适合先试一次。
- 支持子文件夹递归、自定义文件夹层级模板、无日期文件单独放一个文件夹。
- 扫描和整理都在后台线程里跑，几万张图片也不会卡住界面，中途可以随时停止。

### 按内容归类的两种方式

| 方式 | 需要什么 | 认得出什么 |
| --- | --- | --- |
| **快速规则**（默认） | 什么都不用装 | 截图、动图、长图、图标、图形、照片 —— 看的是尺寸、格式、EXIF 相机信息和配色 |
| **本地 AI 模型 CLIP** | `pip install torch open_clip_torch`，首次使用自动下载约 350MB 模型 | 人物、风景、美食、动物、植物、建筑、截图、文档、车辆…… 分类可以自己在界面里改，写什么就分什么 |

两种都在本地跑，图片不会外传。选了 CLIP 但依赖没装时，程序会提示一句并自动退回快速规则，不会整理不下去。

## 运行

需要 Python 3.8+。

```bash
pip install -r photo_sorter/requirements.txt
python -m photo_sorter
```

## 命令行用法

```bash
# 预览（默认不动文件）
python -m photo_sorter.cli ~/图片

# 真正整理，归到 ~/相册 下的 年/年-月 文件夹
python -m photo_sorter.cli ~/图片 -d ~/相册 --apply

# 复制而不是移动，且只处理当前文件夹
python -m photo_sorter.cli ~/图片 --copy --no-recursive --apply

# 先按日期分，再按内容分成 2024-05/风景/ 这样
python -m photo_sorter.cli ~/图片 -g date_category --apply

# 用本地 AI 模型按自定义分类归档
python -m photo_sorter.cli ~/图片 -g category --classifier clip --categories 人物,风景,美食,宠物 --apply

# 撤销上一次整理
python -m photo_sorter.cli --undo
```

常用参数：

| 参数 | 说明 |
| --- | --- |
| `-d, --dest` | 目标文件夹，默认与源文件夹相同 |
| `-p, --pattern` | 文件夹层级模板，默认 `%Y/%Y-%m`；也可用 `%Y-%m`、`%Y/%m月` 等 |
| `--copy` | 复制而不是移动 |
| `--no-recursive` | 不处理子文件夹 |
| `--no-exif` / `--no-filename-date` / `--no-mtime` | 关掉对应的日期来源 |
| `-g, --group-by` | `date`（默认）/ `category` / `category_date` / `date_category` |
| `--classifier` | `heuristic`（默认，快速规则）或 `clip`（本地 AI 模型） |
| `--categories` | CLIP 的分类，逗号分隔，如 `人物,风景,美食`；留空用默认 |
| `--on-conflict rename\|skip` | 目标有同名文件时改名还是跳过 |
| `--apply` | 真正执行（不加就只是预览） |
| `--undo` | 撤销上一次整理 |

## 打包成桌面应用

```bash
pip install pyinstaller
# Windows
pyinstaller -w -n 图片自动归类 photo_sorter/__main__.py
# macOS
pyinstaller -w -n PhotoSorter --osx-bundle-identifier com.example.photosorter photo_sorter/__main__.py
```

## 目录结构

```
photo_sorter/
├── __main__.py        # python -m photo_sorter 启动界面
├── cli.py             # 命令行入口
├── core/
│   ├── models.py      # 选项、计划、结果等数据结构
│   ├── datesource.py  # EXIF / 文件名 / 修改时间 三级取日期
│   ├── classifier.py  # 按内容分类：快速规则 + 本地 CLIP 模型
│   ├── planner.py     # 扫描并算出每个文件该去哪（只读）
│   └── executor.py    # 执行搬运、写日志、撤销
├── gui/
│   ├── app.py         # QApplication 入口
│   ├── main_window.py # 主窗口
│   └── workers.py     # 后台线程（扫描 / 执行 / 撤销 / 缩略图）
└── tests/test_core.py # 核心逻辑测试
```

## 测试

```bash
python -m unittest discover -s photo_sorter/tests -t .
```

## 说明

- 操作日志放在 `~/.photo_sorter/journals/`，「撤销」用的是最近一条。
- 想读 iPhone 的 HEIC，装上 `pillow-heif` 即可，程序会自动启用。
- 分类名会自动去掉 `/`、`:` 等不能作文件夹名的字符。
- 撤销时只还原确实由本程序搬动的文件：如果原位置已经被别的文件占了，或复制出的文件已被改动过位置，会跳过而不是强行覆盖。
