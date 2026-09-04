# -*- coding: utf-8 -*-

"""主窗口：选文件夹 → 预览 → 整理 → 需要时撤销。"""

from pathlib import Path

from PySide6.QtCore import QSettings, QSize
from PySide6.QtGui import QBrush, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox,
                               QFileDialog, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMessageBox, QProgressBar,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ..core import executor
from ..core.classifier import ClipClassifier
from ..core.models import (CLASSIFIER_CLIP, CLASSIFIER_HEURISTIC,
                           CLASSIFIER_LABELS, CONFLICT_RENAME, CONFLICT_SKIP,
                           DEFAULT_CLIP_CATEGORIES, FOLDER_PATTERNS, GROUP_DATE,
                           GROUP_LABELS, OP_COPY, OP_MOVE, SortOptions)
from .workers import ExecuteWorker, ScanWorker, ThumbnailLoader, UndoWorker

# 表格太长会拖慢界面，超过这个数量只展示前面一部分
MAX_PREVIEW_ROWS = 3000

COLUMNS = ['预览', '文件名', '拍摄时间', '时间来源', '分类', '整理后位置', '说明']
COL_THUMB, COL_NAME, COL_TAKEN, COL_SOURCE, COL_CATEGORY, COL_DEST, COL_REASON = range(7)

THUMB_SIZE = 48


class MainWindow(QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('图片自动归类')
        self.resize(1000, 680)

        self._settings = QSettings('photo_sorter', 'photo_sorter')
        self._plan = None
        self._worker = None
        self._loading = False   # 读配置期间不弹提示
        self._thumb_rows = {}   # 行号 -> 图片路径
        self._thumb_done = set()
        self._thumbs = ThumbnailLoader(THUMB_SIZE, self)
        self._thumbs.ready.connect(self._on_thumbnail)
        self._thumbs.start()

        self._build_ui()
        self._load_settings()
        self._update_buttons()

    # ---------- 界面 ----------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(self._build_folder_box())
        layout.addWidget(self._build_option_box())
        layout.addLayout(self._build_button_row())
        layout.addWidget(self._build_table(), 1)
        layout.addWidget(self._build_status_row())

    def _build_folder_box(self) -> QGroupBox:
        box = QGroupBox('文件夹')
        grid = QGridLayout(box)

        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText('选择要整理的图片文件夹')
        self.source_edit.textChanged.connect(self._on_folder_changed)
        source_btn = QPushButton('浏览…')
        source_btn.clicked.connect(self._pick_source)
        grid.addWidget(QLabel('源文件夹：'), 0, 0)
        grid.addWidget(self.source_edit, 0, 1)
        grid.addWidget(source_btn, 0, 2)

        self.same_dest_check = QCheckBox('整理到源文件夹内')
        self.same_dest_check.setChecked(True)
        self.same_dest_check.toggled.connect(self._on_same_dest_toggled)
        self.dest_edit = QLineEdit()
        self.dest_edit.setPlaceholderText('目标文件夹')
        self.dest_edit.setEnabled(False)
        self.dest_edit.textChanged.connect(self._on_folder_changed)
        self.dest_btn = QPushButton('浏览…')
        self.dest_btn.setEnabled(False)
        self.dest_btn.clicked.connect(self._pick_dest)
        grid.addWidget(QLabel('目标文件夹：'), 1, 0)
        grid.addWidget(self.dest_edit, 1, 1)
        grid.addWidget(self.dest_btn, 1, 2)
        grid.addWidget(self.same_dest_check, 2, 1)
        grid.setColumnStretch(1, 1)
        return box

    def _build_option_box(self) -> QGroupBox:
        box = QGroupBox('整理规则')
        outer = QHBoxLayout(box)

        left = QFormLayout()
        self.group_combo = QComboBox()
        for label, value in GROUP_LABELS.items():
            self.group_combo.addItem(label, value)
        self.group_combo.currentIndexChanged.connect(self._on_group_changed)
        left.addRow('归类方式：', self.group_combo)

        self.classifier_combo = QComboBox()
        for label, value in CLASSIFIER_LABELS.items():
            self.classifier_combo.addItem(label, value)
        self.classifier_combo.currentIndexChanged.connect(self._on_classifier_changed)
        left.addRow('内容识别：', self.classifier_combo)

        self.pattern_combo = QComboBox()
        for label, pattern in FOLDER_PATTERNS.items():
            self.pattern_combo.addItem(label, pattern)
        left.addRow('文件夹层级：', self.pattern_combo)

        self.operation_combo = QComboBox()
        self.operation_combo.addItem('移动文件', OP_MOVE)
        self.operation_combo.addItem('复制文件（保留原件）', OP_COPY)
        left.addRow('处理方式：', self.operation_combo)

        self.conflict_combo = QComboBox()
        self.conflict_combo.addItem('自动改名，如 IMG_0001 (1).jpg', CONFLICT_RENAME)
        self.conflict_combo.addItem('跳过不处理', CONFLICT_SKIP)
        left.addRow('同名文件：', self.conflict_combo)

        self.unknown_edit = QLineEdit('未知日期')
        left.addRow('无日期时放入：', self.unknown_edit)

        self.categories_edit = QLineEdit()
        self.categories_edit.setPlaceholderText('用空格或逗号分隔，如：人物 风景 美食 动物')
        self.categories_edit.setToolTip('只对 AI 模型识别生效；留空则用默认分类。')
        left.addRow('内容分类：', self.categories_edit)
        outer.addLayout(left, 1)

        right = QVBoxLayout()
        self.recursive_check = QCheckBox('包含子文件夹')
        self.recursive_check.setChecked(True)
        self.exif_check = QCheckBox('读取 EXIF 拍摄时间')
        self.exif_check.setChecked(True)
        self.filename_check = QCheckBox('EXIF 缺失时，从文件名识别日期')
        self.filename_check.setChecked(True)
        self.mtime_check = QCheckBox('仍无日期时，用文件修改时间')
        self.mtime_check.setChecked(True)
        self.dedup_check = QCheckBox('目标已有内容相同的文件时跳过')
        self.dedup_check.setChecked(True)
        for widget in (self.recursive_check, self.exif_check, self.filename_check,
                       self.mtime_check, self.dedup_check):
            right.addWidget(widget)
        right.addStretch(1)
        outer.addLayout(right, 1)
        return box

    def _build_button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.preview_btn = QPushButton('预览整理结果')
        self.preview_btn.clicked.connect(self._start_scan)
        self.run_btn = QPushButton('开始整理')
        self.run_btn.clicked.connect(self._start_execute)
        self.cancel_btn = QPushButton('停止')
        self.cancel_btn.clicked.connect(self._cancel)
        self.undo_btn = QPushButton('撤销上次整理')
        self.undo_btn.clicked.connect(self._start_undo)
        row.addWidget(self.preview_btn)
        row.addWidget(self.run_btn)
        row.addWidget(self.cancel_btn)
        row.addStretch(1)
        row.addWidget(self.undo_btn)
        return row

    def _build_table(self) -> QTableWidget:
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        self.table.verticalHeader().setDefaultSectionSize(THUMB_SIZE + 8)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_THUMB, QHeaderView.Fixed)
        header.resizeSection(COL_THUMB, THUMB_SIZE + 12)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_DEST, QHeaderView.Stretch)
        self.table.verticalScrollBar().valueChanged.connect(self._request_visible_thumbnails)
        return self.table

    def _build_status_row(self) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        self.status_label = QLabel('选择文件夹后点“预览整理结果”。')
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setMaximumWidth(260)
        row.addWidget(self.status_label, 1)
        row.addWidget(self.progress)
        return widget

    # ---------- 配置读写 ----------

    def _load_settings(self) -> None:
        self._loading = True
        try:
            self._apply_saved_settings()
        finally:
            self._loading = False
        self._on_group_changed()

    def _apply_saved_settings(self) -> None:
        get = self._settings.value
        self.source_edit.setText(get('source', '', str))
        self.dest_edit.setText(get('dest', '', str))
        self.same_dest_check.setChecked(get('same_dest', True, bool))
        index = self.group_combo.findData(get('group_by', GROUP_DATE, str))
        if index >= 0:
            self.group_combo.setCurrentIndex(index)
        index = self.classifier_combo.findData(get('classifier', CLASSIFIER_HEURISTIC, str))
        if index >= 0:
            self.classifier_combo.setCurrentIndex(index)
        self.categories_edit.setText(get('categories', '', str))
        index = self.pattern_combo.findData(get('pattern', '%Y/%Y-%m', str))
        if index >= 0:
            self.pattern_combo.setCurrentIndex(index)
        index = self.operation_combo.findData(get('operation', OP_MOVE, str))
        if index >= 0:
            self.operation_combo.setCurrentIndex(index)
        index = self.conflict_combo.findData(get('conflict', CONFLICT_RENAME, str))
        if index >= 0:
            self.conflict_combo.setCurrentIndex(index)
        self.unknown_edit.setText(get('unknown_dir', '未知日期', str))
        self.recursive_check.setChecked(get('recursive', True, bool))
        self.exif_check.setChecked(get('use_exif', True, bool))
        self.filename_check.setChecked(get('use_filename', True, bool))
        self.mtime_check.setChecked(get('use_mtime', True, bool))
        self.dedup_check.setChecked(get('dedup', True, bool))

    def _save_settings(self) -> None:
        put = self._settings.setValue
        put('source', self.source_edit.text())
        put('dest', self.dest_edit.text())
        put('same_dest', self.same_dest_check.isChecked())
        put('group_by', self.group_combo.currentData())
        put('classifier', self.classifier_combo.currentData())
        put('categories', self.categories_edit.text())
        put('pattern', self.pattern_combo.currentData())
        put('operation', self.operation_combo.currentData())
        put('conflict', self.conflict_combo.currentData())
        put('unknown_dir', self.unknown_edit.text().strip() or '未知日期')
        put('recursive', self.recursive_check.isChecked())
        put('use_exif', self.exif_check.isChecked())
        put('use_filename', self.filename_check.isChecked())
        put('use_mtime', self.mtime_check.isChecked())
        put('dedup', self.dedup_check.isChecked())

    def closeEvent(self, event) -> None:
        self._save_settings()
        self._thumbs.stop()
        self._thumbs.wait(2000)
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)

    # ---------- 交互 ----------

    def _pick_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, '选择源文件夹', self.source_edit.text())
        if path:
            self.source_edit.setText(path)

    def _pick_dest(self) -> None:
        path = QFileDialog.getExistingDirectory(self, '选择目标文件夹', self.dest_edit.text())
        if path:
            self.dest_edit.setText(path)

    def _on_same_dest_toggled(self, checked: bool) -> None:
        self.dest_edit.setEnabled(not checked)
        self.dest_btn.setEnabled(not checked)
        self._on_folder_changed()

    def _on_group_changed(self, *_) -> None:
        """归类方式一变，跟日期或内容相关的控件也跟着可用/禁用。"""
        options = self._current_options()
        for widget in (self.pattern_combo, self.unknown_edit, self.exif_check,
                       self.filename_check, self.mtime_check):
            widget.setEnabled(options.needs_date)
        self.classifier_combo.setEnabled(options.needs_category)
        self.categories_edit.setEnabled(
            options.needs_category and options.classifier == CLASSIFIER_CLIP)
        self.table.setColumnHidden(COL_CATEGORY, not options.needs_category)
        self.table.setColumnHidden(COL_TAKEN, not options.needs_date)
        self.table.setColumnHidden(COL_SOURCE, not options.needs_date)
        self._on_folder_changed()

    def _on_classifier_changed(self, *_) -> None:
        self.categories_edit.setEnabled(
            self.classifier_combo.currentData() == CLASSIFIER_CLIP
            and self.classifier_combo.isEnabled())
        if (not self._loading
                and self.classifier_combo.currentData() == CLASSIFIER_CLIP
                and not ClipClassifier.is_installed()):
            QMessageBox.information(
                self, '还没装 AI 模型依赖',
                'AI 内容识别需要额外安装：\n\n    pip install torch open_clip_torch\n\n'
                '装好后重开程序即可使用。现在会先用“快速规则”来分类。')
        self._on_folder_changed()

    def _on_folder_changed(self, *_) -> None:
        # 文件夹一改，之前的预览就作废了
        self._clear_plan()
        self._update_buttons()

    def _clear_plan(self) -> None:
        self._plan = None
        self.table.setRowCount(0)

    def _busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _update_buttons(self) -> None:
        busy = self._busy()
        has_source = bool(self.source_edit.text().strip())
        self.preview_btn.setEnabled(not busy and has_source)
        self.run_btn.setEnabled(not busy and self._plan is not None and bool(self._plan.pending))
        self.cancel_btn.setEnabled(busy)
        self.undo_btn.setEnabled(not busy and executor.latest_journal() is not None)

    def _parsed_categories(self) -> tuple:
        text = self.categories_edit.text().replace('，', ' ').replace(',', ' ')
        parts = tuple(part for part in text.split() if part)
        return parts or DEFAULT_CLIP_CATEGORIES

    def _current_options(self) -> SortOptions:
        return SortOptions(
            pattern=self.pattern_combo.currentData(),
            operation=self.operation_combo.currentData(),
            recursive=self.recursive_check.isChecked(),
            use_exif=self.exif_check.isChecked(),
            use_filename=self.filename_check.isChecked(),
            use_mtime=self.mtime_check.isChecked(),
            unknown_dir=self.unknown_edit.text().strip() or '未知日期',
            on_conflict=self.conflict_combo.currentData(),
            skip_same_content=self.dedup_check.isChecked(),
            group_by=self.group_combo.currentData(),
            classifier=self.classifier_combo.currentData(),
            categories=self._parsed_categories(),
        )

    def _resolved_folders(self):
        """返回 (源, 目标)；有问题时弹窗并返回 None。"""
        source_text = self.source_edit.text().strip()
        if not source_text:
            QMessageBox.warning(self, '还差一步', '请先选择源文件夹。')
            return None
        source = Path(source_text).expanduser()
        if not source.is_dir():
            QMessageBox.warning(self, '文件夹不存在', '源文件夹不存在：\n%s' % source)
            return None
        if self.same_dest_check.isChecked():
            return source, source
        dest_text = self.dest_edit.text().strip()
        if not dest_text:
            QMessageBox.warning(self, '还差一步', '请选择目标文件夹，或勾选“整理到源文件夹内”。')
            return None
        return source, Path(dest_text).expanduser()

    # ---------- 扫描 ----------

    def _start_scan(self) -> None:
        folders = self._resolved_folders()
        if not folders:
            return
        source, dest = folders
        self._clear_plan()
        self._save_settings()
        self.status_label.setText('正在扫描…')
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)

        worker = ScanWorker(source, dest, self._current_options(), self)
        worker.stage.connect(self.status_label.setText)
        worker.progress.connect(self._on_progress)
        worker.finished_plan.connect(self._on_plan_ready)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_done)
        self._worker = worker
        worker.start()
        self._update_buttons()

    def _on_plan_ready(self, plan) -> None:
        self._plan = plan
        self._fill_table(plan)
        pending, skipped = len(plan.pending), len(plan.skipped)
        if not plan.items:
            self.status_label.setText('没有找到图片文件。')
        else:
            verb = '复制' if plan.options.operation == OP_COPY else '移动'
            self.status_label.setText(
                '共 %d 个文件：待%s %d 个，跳过 %d 个。确认无误后点“开始整理”。'
                % (len(plan.items), verb, pending, skipped))

    def _fill_table(self, plan) -> None:
        items = plan.items[:MAX_PREVIEW_ROWS]
        self._thumbs.clear()
        self._thumb_rows = {}
        self._thumb_done = set()
        self.table.setRowCount(len(items))
        grey = QBrush(QColor(150, 150, 150))
        dest_root = plan.dest_root
        for row, item in enumerate(items):
            try:
                shown_dest = item.dest.relative_to(dest_root)
            except ValueError:
                shown_dest = item.dest
            taken = item.taken_at.strftime('%Y-%m-%d %H:%M:%S') if item.taken_at else '—'
            values = {
                COL_THUMB: '',
                COL_NAME: item.source.name,
                COL_TAKEN: taken,
                COL_SOURCE: item.date_source if item.taken_at else '—',
                COL_CATEGORY: item.category or '—',
                COL_DEST: str(shown_dest),
                COL_REASON: item.reason or ('待复制' if item.action == 'copy' else '待移动'),
            }
            for column, text in values.items():
                cell = QTableWidgetItem(text)
                cell.setToolTip(str(item.source))
                if not item.will_change:
                    cell.setForeground(grey)
                self.table.setItem(row, column, cell)
            self._thumb_rows[row] = item.source
        self._request_visible_thumbnails()
        if len(plan.items) > MAX_PREVIEW_ROWS:
            self.status_label.setText('文件较多，表格只显示前 %d 条。' % MAX_PREVIEW_ROWS)

    # ---------- 缩略图 ----------

    def _request_visible_thumbnails(self, *_) -> None:
        """只给看得见的行排队加载，多几行富余以便滚动时不空着。"""
        if not self._thumb_rows:
            return
        first = self.table.rowAt(0)
        last = self.table.rowAt(self.table.viewport().height() - 1)
        if first < 0:
            first = 0
        if last < 0:
            last = self.table.rowCount() - 1
        wanted = []
        for row in range(max(first - 5, 0), min(last + 6, self.table.rowCount())):
            if row in self._thumb_done or row not in self._thumb_rows:
                continue
            self._thumb_done.add(row)
            wanted.append((row, str(self._thumb_rows[row])))
        self._thumbs.request(wanted)

    def _on_thumbnail(self, row: int, image) -> None:
        cell = self.table.item(row, COL_THUMB)
        if cell is None or row not in self._thumb_rows:
            return
        cell.setIcon(QIcon(QPixmap.fromImage(image)))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._request_visible_thumbnails()

    # ---------- 执行 ----------

    def _start_execute(self) -> None:
        if not self._plan or not self._plan.pending:
            return
        pending = len(self._plan.pending)
        verb = '复制' if self._plan.options.operation == OP_COPY else '移动'
        answer = QMessageBox.question(
            self, '确认整理',
            '将%s %d 个文件到：\n%s\n\n整理后可以用“撤销上次整理”还原。' % (verb, pending, self._plan.dest_root),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return

        self.status_label.setText('正在整理…')
        self.progress.setVisible(True)
        self.progress.setRange(0, pending)
        worker = ExecuteWorker(self._plan, self)
        worker.progress.connect(self._on_progress)
        worker.finished_result.connect(self._on_execute_done)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_done)
        self._worker = worker
        worker.start()
        self._update_buttons()

    def _on_execute_done(self, result) -> None:
        self._clear_plan()
        parts = ['已处理 %d 个' % result.done]
        if result.skipped:
            parts.append('跳过 %d 个' % result.skipped)
        if result.failed:
            parts.append('失败 %d 个' % result.failed)
        if result.canceled:
            parts.append('（已停止）')
        self.status_label.setText('整理完成：' + '，'.join(parts) + '。')
        if result.errors:
            detail = '\n'.join(result.errors[:20])
            if len(result.errors) > 20:
                detail += '\n…还有 %d 条' % (len(result.errors) - 20)
            QMessageBox.warning(self, '部分文件没有处理成功', detail)

    # ---------- 撤销 ----------

    def _start_undo(self) -> None:
        journal = executor.latest_journal()
        if journal is None:
            QMessageBox.information(self, '没有可撤销的记录', '还没有可以撤销的整理记录。')
            self._update_buttons()
            return
        answer = QMessageBox.question(
            self, '撤销上次整理',
            '将把上次整理的文件还原到原来的位置。\n记录：%s\n\n继续吗？' % journal.name,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return

        self.status_label.setText('正在撤销…')
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        worker = UndoWorker(journal, self)
        worker.progress.connect(self._on_progress)
        worker.finished_result.connect(self._on_undo_done)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_done)
        self._worker = worker
        worker.start()
        self._update_buttons()

    def _on_undo_done(self, result) -> None:
        self._clear_plan()
        self.status_label.setText('撤销完成：还原 %d 个，跳过 %d 个，失败 %d 个。'
                                 % (result.done, result.skipped, result.failed))
        if result.errors:
            QMessageBox.warning(self, '部分文件没有还原', '\n'.join(result.errors[:20]))

    # ---------- 公共回调 ----------

    def _on_progress(self, index: int, total: int, path: str) -> None:
        if self.progress.maximum() > 0:
            self.progress.setValue(index)
        self.status_label.setText('%d/%d  %s' % (index, total, Path(path).name))

    def _on_failed(self, message: str) -> None:
        self.status_label.setText('出错了。')
        QMessageBox.critical(self, '出错了', message)

    def _cancel(self) -> None:
        if self._busy():
            self._worker.cancel()
            self.status_label.setText('正在停止…')

    def _on_worker_done(self) -> None:
        self.progress.setVisible(False)
        self.progress.setRange(0, 1)
        self._worker = None
        self._update_buttons()
