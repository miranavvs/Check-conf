from __future__ import annotations

import unicodedata

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import collectors, export
from .icons import accent, app_pixmap, icon
from .i18n import LANGS, LANG_NAMES, t
from .model import Report
from .theme import STYLESHEET, level_color
from .utils import human_datetime, num


def _fold(value: str) -> str:
    plain = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in plain if not unicodedata.combining(ch)).casefold()


def _match(query: str, *needles) -> bool:
    if not query:
        return True
    return any(query in _fold(needle) for needle in needles)


class CollectWorker(QThread):
    progress = Signal(str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, deep: bool, lang: str, parent=None):
        super().__init__(parent)
        self._deep = deep
        self._lang = lang

    def run(self):
        try:
            report = collectors.collect_report(self._deep, self._lang, self.progress.emit)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.done.emit(report)


class FieldRow(QWidget):
    def __init__(self, key: str, value: str, level: str, lang: str, parent=None):
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(7)
        grid.setColumnStretch(1, 1)

        name = QLabel(t(key, lang))
        name.setObjectName("FieldKey")
        name.setWordWrap(True)
        name.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        name.setAlignment(Qt.AlignRight | Qt.AlignTop)

        content = QLabel(value)
        content.setObjectName("FieldValue")
        content.setWordWrap(True)
        content.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content.setStyleSheet(f"color: {level_color(level)};")

        grid.addWidget(name, 0, 0)
        grid.addWidget(content, 0, 1)


class SectionCard(QFrame):
    def __init__(self, key: str, icon_name: str, lang: str, parent=None):
        super().__init__(parent)
        self.key = key
        self._lang = lang
        self.setObjectName("Card")

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 13, 16, 15)
        root.setSpacing(11)

        head = QHBoxLayout()
        head.setSpacing(9)
        self._dot = QLabel()
        self._dot.setFixedSize(9, 9)
        self._title = QLabel(t(f"sec.{key}", lang))
        self._title.setObjectName("CardTitle")
        self._count = QLabel()
        self._count.setObjectName("CardCount")
        head.addWidget(self._dot)
        head.addWidget(self._title)
        head.addStretch(1)
        head.addWidget(self._count)
        root.addLayout(head)

        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(14)
        self._grid.setVerticalSpacing(7)
        self._grid.setColumnStretch(1, 1)
        root.addLayout(self._grid)

        self._error = QLabel()
        self._error.setObjectName("CardError")
        self._error.setWordWrap(True)
        self._error.hide()
        root.addWidget(self._error)

        self._rows: list[FieldRow] = []
        self.set_icon(icon_name)

    def set_icon(self, icon_name: str) -> None:
        color = accent(icon_name)
        self._dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
        self._dot.setToolTip(icon_name)

    def clear_rows(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()

    def add_row(self, row: FieldRow) -> None:
        self._grid.addWidget(row, len(self._rows), 0, 1, 2)
        self._rows.append(row)

    def set_count(self, shown: int, total: int) -> None:
        if shown == total:
            self._count.setText(t("section.count", self._lang).format(n=total))
        else:
            self._count.setText(f"{shown}/{total}")

    def set_error(self, message: str | None) -> None:
        self._error.setText(message or "")
        self._error.setVisible(bool(message))


class MainWindow(QMainWindow):
    def __init__(self, lang: str = "fr"):
        super().__init__()
        self.lang = lang
        self.report: Report | None = None
        self.worker: CollectWorker | None = None
        self._cards: dict[str, SectionCard] = {}
        self._selected = None

        self.setWindowIcon(QIcon(app_pixmap(256)))
        self.resize(1180, 780)
        self.setStyleSheet(STYLESHEET)
        self._build()
        self._retranslate()
        self.refresh()

    def _build(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        toolbar = self._build_toolbar()
        root.addWidget(toolbar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.container = QWidget()
        self._cards_layout = QVBoxLayout(self.container)
        self._cards_layout.setContentsMargins(20, 18, 20, 22)
        self._cards_layout.setSpacing(13)
        self._empty = QLabel()
        self._empty.setObjectName("Empty")
        self._empty.setAlignment(Qt.AlignCenter)
        self._cards_layout.addWidget(self._empty)
        self._cards_layout.addStretch(1)
        self.scroll.setWidget(self.container)
        body.addWidget(self.scroll, 1)
        root.addLayout(body, 1)

        self.setCentralWidget(central)
        self.status_label = QLabel()
        self.statusBar().addWidget(self.status_label, 1)

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("Header")
        frame.setFixedHeight(72)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(13)

        logo = QLabel()
        logo.setPixmap(app_pixmap(40).scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(logo)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        self.app_title = QLabel()
        self.app_title.setObjectName("AppTitle")
        self.app_subtitle = QLabel()
        self.app_subtitle.setObjectName("AppSubtitle")
        titles.addWidget(self.app_title)
        titles.addWidget(self.app_subtitle)
        layout.addLayout(titles)
        layout.addStretch(1)

        self.host_info = QLabel()
        self.host_info.setObjectName("HostInfo")
        self.host_info.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.host_info.setTextFormat(Qt.RichText)
        layout.addWidget(self.host_info)
        return frame

    def _build_toolbar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("Toolbar")
        frame.setFixedHeight(56)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(20, 9, 20, 9)
        layout.setSpacing(9)

        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(240)
        self.search.textChanged.connect(self._render)
        layout.addWidget(self.search, 1)

        self.deep_box = QCheckBox()
        self.deep_box.toggled.connect(self._on_deep_toggled)
        layout.addWidget(self.deep_box)

        self.lang_box = QComboBox()
        for code in LANGS:
            self.lang_box.addItem(LANG_NAMES[code], code)
        self.lang_box.setCurrentIndex(max(0, list(LANGS).index(self.lang)))
        self.lang_box.currentIndexChanged.connect(self._on_lang_changed)
        layout.addWidget(self.lang_box)

        self.copy_btn = QPushButton()
        self.copy_btn.clicked.connect(self.copy_report)
        layout.addWidget(self.copy_btn)

        self.export_btn = QPushButton()
        self.export_btn.clicked.connect(self.export_report)
        layout.addWidget(self.export_btn)

        self.refresh_btn = QPushButton()
        self.refresh_btn.setObjectName("Primary")
        self.refresh_btn.setDefault(True)
        self.refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_btn)
        return frame

    def _build_sidebar(self) -> QWidget:
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("Sections")
        self.sidebar.setFixedWidth(196)
        self.sidebar.setSelectionMode(QAbstractItemView.SingleSelection)
        self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sidebar.currentItemChanged.connect(self._on_section_picked)
        return self.sidebar

    def _retranslate(self) -> None:
        self.setWindowTitle(t("app.name", self.lang))
        self.app_title.setText(t("app.name", self.lang))
        self.app_subtitle.setText(t("app.subtitle", self.lang))
        self.search.setPlaceholderText(t("search.ph", self.lang))
        self.refresh_btn.setText(t("toolbar.refresh", self.lang))
        self.export_btn.setText(t("toolbar.export", self.lang))
        self.copy_btn.setText(t("toolbar.copy", self.lang))
        self.deep_box.setText(t("toolbar.deep", self.lang))
        self.deep_box.setToolTip(t("toolbar.deep.tip", self.lang))
        self._retranslate_menu()
        self._rebuild_sidebar()
        self._update_host_info()
        self._render()

    def _retranslate_menu(self) -> None:
        menu = self.menuBar()
        menu.clear()
        fr = self.lang == "fr"
        file_menu = menu.addMenu("&Fichier" if fr else "&File")
        export_action = QAction(t("toolbar.export", self.lang), self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self.export_report)
        file_menu.addAction(export_action)

        copy_action = QAction(t("toolbar.copy", self.lang), self)
        copy_action.setShortcut(QKeySequence("Ctrl+C"))
        copy_action.triggered.connect(self.copy_report)
        file_menu.addAction(copy_action)

        refresh_action = QAction(t("toolbar.refresh", self.lang), self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self.refresh)
        file_menu.addAction(refresh_action)

        file_menu.addSeparator()
        quit_action = QAction("&Quitter" if fr else "&Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = menu.addMenu("&Affichage" if fr else "&View")
        for code in LANGS:
            action = QAction(LANG_NAMES[code], self, checkable=True)
            action.setChecked(code == self.lang)
            action.triggered.connect(lambda _checked=False, c=code: self.set_lang(c))
            view_menu.addAction(action)

    def _rebuild_sidebar(self) -> None:
        self.sidebar.blockSignals(True)
        self.sidebar.clear()
        if self.report is not None:
            for section in self.report.sections:
                spec = collectors.spec_for(section.key)
                name = spec.icon if spec else section.icon
                item = QListWidgetItem(icon(name, accent(name), 64), t(f"sec.{section.key}", self.lang))
                item.setData(Qt.UserRole, section.key)
                self.sidebar.addItem(item)
        self.sidebar.blockSignals(False)

    def _on_section_picked(self, current, _previous=None) -> None:
        if current is None:
            return
        key = current.data(Qt.UserRole)
        self._selected = key
        card = self._cards.get(key)
        if card is None:
            return
        top = card.geometry().top() - 12
        bar = self.scroll.verticalScrollBar()
        bar.setValue(max(0, min(top, bar.maximum())))

    def _on_deep_toggled(self, _checked: bool) -> None:
        self.refresh()

    def _on_lang_changed(self, index: int) -> None:
        code = self.lang_box.itemData(index)
        if code and code != self.lang:
            self.set_lang(code)

    def set_lang(self, code: str) -> None:
        if code not in LANGS or code == self.lang:
            return
        self.lang = code
        self._retranslate()

    def _update_host_info(self) -> None:
        if self.report is None:
            self.host_info.setText(t("empty.all", self.lang))
            return
        parts = []
        if self.report.hostname:
            parts.append(f"<b>{self.report.hostname}</b>")
        if self.report.os_label:
            parts.append(self.report.os_label)
        parts.append(human_datetime(self.report.generated_at, self.lang))
        self.host_info.setText(" &nbsp;·&nbsp; ".join(parts))

    def _set_busy(self, busy: bool) -> None:
        self.refresh_btn.setEnabled(not busy)
        self.export_btn.setEnabled(not busy and self.report is not None)
        self.copy_btn.setEnabled(not busy and self.report is not None)
        self.sidebar.setEnabled(not busy)
        if busy:
            self.status_label.setText(t("status.collecting", self.lang))

    def refresh(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self._set_busy(True)
        self.worker = CollectWorker(self.deep_box.isChecked(), self.lang, self)
        self.worker.done.connect(self._on_collected)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_finished(self) -> None:
        self._set_busy(False)

    def _on_collected(self, report: Report) -> None:
        self.report = report
        self._update_host_info()
        self._rebuild_sidebar()
        self.status_label.setText(
            t("status.elapsed", self.lang).format(s=num(report.duration, 2, self.lang))
        )
        self._render()

    def _on_failed(self, message: str) -> None:
        self._set_busy(False)
        self.status_label.setText(message)

    def _visible_fields(self, section) -> list:
        query = _fold(self.search.text().strip())
        if not query:
            return list(section.fields)
        return [
            item
            for item in section.fields
            if _match(query, t(f"f.{item.key}", self.lang), item.value, t(f"sec.{section.key}", self.lang))
        ]

    def _render(self) -> None:
        for card in self._cards.values():
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        query = self.search.text().strip()
        if self.report is None:
            self._empty.setText(t("empty.all", self.lang))
            self._empty.show()
            return

        total_matches = 0
        for section in self.report.sections:
            rows = self._visible_fields(section)
            if query and not rows:
                continue
            total_matches += len(rows)
            card = SectionCard(section.key, section.icon, self.lang)
            for item in rows:
                card.add_row(FieldRow(f"f.{item.key}", item.display(self.lang), item.level, self.lang))
            card.set_count(len(rows), len(section.fields))
            card.set_error(section.error if not query else None)
            self._cards[section.key] = card
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

        if not self._cards:
            self._empty.setText(
                t("empty.search", self.lang).format(q=query) if query else t("empty.none", self.lang)
            )
            self._empty.show()
        else:
            self._empty.hide()

        if self._selected and self._selected in self._cards:
            self.scroll.verticalScrollBar().setValue(0)
        elif not self._selected:
            self.scroll.verticalScrollBar().setValue(0)

    def copy_report(self) -> None:
        if self.report is None:
            return
        text = export.to_text(self.report, self.lang)
        if not text.strip():
            QMessageBox.information(self, t("app.name", self.lang), t("msg.nothing", self.lang))
            return
        QGuiApplication.clipboard().setText(text)
        self.status_label.setText(t("msg.copied", self.lang))

    def export_report(self) -> None:
        if self.report is None:
            return
        default = f"{t('export.default', self.lang)}-{self.report.generated_at:%Y%m%d-%H%M%S}"
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("export.dialog", self.lang),
            default,
            t("export.filter", self.lang),
        )
        if not path:
            return
        if not path.lower().endswith((".txt", ".json", ".html")):
            path += ".txt"
        try:
            export.write_report(self.report, path, self.lang)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(
                self,
                t("app.name", self.lang),
                t("msg.export_err", self.lang).format(err=exc),
            )
            return
        self.status_label.setText(t("msg.export_ok", self.lang).format(path=path))
