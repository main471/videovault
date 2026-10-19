"""Localisation des ressources, embarquées (binaire PyInstaller) ou système.

Quand l'application est gelée par PyInstaller, les fichiers ajoutés via
``--add-binary`` / ``--add-data`` sont extraits dans ``sys._MEIPASS``. On les
cherche là en priorité, puis à côté de l'exécutable, puis dans le PATH système.
Ainsi un AppImage ou un .exe peut embarquer ffmpeg, ffprobe et vcsteg3.py et
fonctionner sans rien installer.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def resource_dirs() -> list[Path]:
    """Dossiers où chercher une ressource embarquée, par priorité."""
    dirs: list[Path] = []
    # 1. Dossier d'extraction PyInstaller (onefile) ou dossier du bundle.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.append(Path(meipass))
        dirs.append(Path(meipass) / "bin")
    # 2. À côté de l'exécutable gelé.
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        dirs.append(exe_dir)
        dirs.append(exe_dir / "bin")
    # 3. Racine du projet (exécution depuis les sources).
    root = Path(__file__).resolve().parent.parent
    dirs.append(root)
    dirs.append(root / "bin")
    dirs.append(root / "vendor")
    return dirs


def find_bundled(filename: str) -> Path | None:
    """Retourne le premier chemin existant pour ``filename`` parmi les dossiers."""
    candidates = [filename]
    if not filename.endswith(".exe"):
        candidates.append(filename + ".exe")  # tolérer Windows
    for d in resource_dirs():
        for name in candidates:
            p = d / name
            if p.is_file():
                return p
    return None


def find_tool(name: str) -> str | None:
    """Localise un outil (ffmpeg, ffprobe) : embarqué d'abord, sinon PATH système."""
    bundled = find_bundled(name)
    if bundled:
        # S'assurer qu'il est exécutable (droits parfois perdus à l'extraction).
        try:
            os.chmod(bundled, 0o755)
        except OSError:
            pass
        return str(bundled)
    return shutil.which(name)
