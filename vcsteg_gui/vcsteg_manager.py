"""Gestion du script officiel vcsteg3.py.

Le script n'est pas redistribué avec l'application. Il est récupéré depuis
la source officielle VeraCrypt et son intégrité est vérifiée via un SHA256
épinglé avant toute utilisation. Un script dont l'empreinte ne correspond
pas est refusé.
"""

from __future__ import annotations

import hashlib
import os
import ssl
import urllib.request
from pathlib import Path

# Empreinte officielle de vcsteg3.py (dossier Contributions de VeraCrypt).
VCSTEG3_SHA256 = "c9aaad401b601be7415a973978b6da2fc31f26e58bcf5d4890a3cc1912d86843"

# URL officielle (SourceForge redirige vers un miroir).
VCSTEG3_URL = (
    "https://downloads.sourceforge.net/project/veracrypt/"
    "Contributions/vcsteg3.py"
)
VCSTEG3_URL_FALLBACK = (
    "https://sourceforge.net/projects/veracrypt/files/"
    "Contributions/vcsteg3.py/download"
)


class VcstegError(Exception):
    """Erreur liée au script vcsteg3.py (absent, corrompu, non téléchargeable)."""


def _app_data_dir() -> Path:
    """Dossier de données de l'application, conforme à XDG sous Linux."""
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    d = Path(base) / "videovault"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sha256_of(path: str | Path) -> str:
    """Retourne l'empreinte SHA256 d'un fichier."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def search_paths() -> list[Path]:
    """Emplacements où chercher un vcsteg3.py déjà présent, par priorité.

    Inclut les dossiers de ressources embarquées (binaire PyInstaller / AppImage),
    ce qui permet à un exécutable autonome d'inclure le script.
    """
    from .resources import resource_dirs

    paths: list[Path] = [_app_data_dir() / "vcsteg3.py"]
    for d in resource_dirs():
        paths.append(d / "vcsteg3.py")
    return paths


def find_valid_script() -> Path | None:
    """Retourne le premier vcsteg3.py présent ET valide (SHA256 correct)."""
    for p in search_paths():
        if p.is_file():
            try:
                if sha256_of(p) == VCSTEG3_SHA256:
                    return p
            except OSError:
                continue
    return None

def _open_url(url: str, timeout: int):
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "VideoVault/1.0"})
    return urllib.request.urlopen(req, timeout=timeout, context=ctx)


def download_script(timeout: int = 60) -> Path:
    """Télécharge le script officiel, vérifie son empreinte, puis le met en cache.

    Lève VcstegError si le téléchargement échoue ou si l'empreinte ne
    correspond pas (dans ce dernier cas le fichier est supprimé).
    """
    dest = _app_data_dir() / "vcsteg3.py"
    tmp = dest.with_suffix(".py.part")

    last_err: Exception | None = None
    for url in (VCSTEG3_URL, VCSTEG3_URL_FALLBACK):
        try:
            with _open_url(url, timeout) as resp, open(tmp, "wb") as out:
                out.write(resp.read())
            if tmp.stat().st_size == 0:
                raise VcstegError("fichier vide")
            break
        except Exception as e:  # noqa: BLE001 — on réessaie l'URL de secours
            last_err = e
            tmp.unlink(missing_ok=True)
    else:
        raise VcstegError(
            f"Téléchargement impossible du script officiel : {last_err}"
        )

    digest = sha256_of(tmp)
    if digest != VCSTEG3_SHA256:
        tmp.unlink(missing_ok=True)
        raise VcstegError(
            "Empreinte SHA256 incorrecte — script refusé.\n"
            f"  attendu : {VCSTEG3_SHA256}\n"
            f"  obtenu  : {digest}"
        )

    tmp.replace(dest)
    return dest


def ensure_script(auto_download: bool = False) -> Path:
    """Retourne un vcsteg3.py valide, en le téléchargeant si autorisé."""
    found = find_valid_script()
    if found:
        return found
    if auto_download:
        return download_script()
    raise VcstegError(
        "Script vcsteg3.py introuvable. Cliquez sur « Télécharger le script »."
    )
