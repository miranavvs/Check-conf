from __future__ import annotations

import os
import sys

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from pcinfo.i18n import APP_VERSION, DEFAULT_LANG, LANGS
from pcinfo.ui import MainWindow


def detect_lang() -> str:
    for var in ("LANG", "LC_ALL", "LC_MESSAGES", "LANGUAGE"):
        raw = os.environ.get(var, "")
        if raw:
            code = raw.split(":")[0].split(".")[0].split("_")[0].lower()
            if code in LANGS:
                return code
    name = QLocale.system().name().lower().replace("-", "_")
    code = name.split("_")[0]
    return code if code in LANGS else DEFAULT_LANG


def main() -> int:
    lang = detect_lang()
    app = QApplication(sys.argv)
    QLocale.setDefault(QLocale(lang))
    app.setApplicationName("check-conf")
    app.setApplicationDisplayName("CheckConf — Config PC")
    app.setApplicationVersion(APP_VERSION)

    window = MainWindow(lang=lang)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
