from __future__ import annotations

from pathlib import Path
from typing import Final


BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent
MODULOS_DIR: Final[Path] = BASE_DIR / "modulos"

PAGE_TITLE: Final[str] = "QGP Online - SUPESP/CE"
PAGE_ICON: Final[str] = "🛡️"
PAGE_LAYOUT: Final[str] = "wide"
INITIAL_SIDEBAR_STATE: Final[str] = "collapsed"

VERSAO_SISTEMA: Final[str] = "1.0.0"
