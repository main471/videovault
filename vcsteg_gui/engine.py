"""Moteur de fusion : conversion vidéo puis imbrication via vcsteg3.py.

Aucune dépendance à l'interface graphique : ce module est utilisable et
testable seul. Les messages de progression passent par un callback `log`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .resources import find_tool
from .vcsteg_manager import VcstegError, ensure_script

LogFn = Callable[[str], None]

# Conteneurs/codecs déjà compatibles MP4 : on peut remuxer sans ré-encoder.
MP4_FRIENDLY_VCODECS = {"h264", "hevc", "mpeg4", "av1"}
MP4_FRIENDLY_ACODECS = {"aac", "mp3", "ac3"}

VIDEO_EXTENSIONS = [
    "mp4", "mkv", "avi", "mov", "webm", "flv", "wmv", "m4v", "mpg", "mpeg", "ts",
]


class MergeError(Exception):
    """Erreur pendant la conversion ou la fusion."""


class Cancelled(Exception):
    """L'utilisateur a annulé l'opération."""


@dataclass
class MergeRequest:
    video_path: str          # vidéo source (n'importe quel format)
    container_path: str      # conteneur caché VeraCrypt (créé en dehors de l'appli)
    output_path: str         # fichier .mp4 final à produire
    keep_backup: bool = True # garder une copie .bak du conteneur


def _noop(_: str) -> None:
    pass


def _run(cmd: list[str], log: LogFn, is_cancelled: Callable[[], bool]) -> None:
    """Exécute une commande en streamant stderr vers le log, annulable."""
    log("$ " + " ".join(cmd))
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                log(line)
            if is_cancelled():
                proc.terminate()
                raise Cancelled()
    finally:
        proc.stdout.close()
    ret = proc.wait()
    if ret != 0:
        raise MergeError(f"La commande a échoué (code {ret}) : {cmd[0]}")


def ffmpeg_bin() -> str:
    """Chemin de ffmpeg (embarqué si présent, sinon système)."""
    return find_tool("ffmpeg") or "ffmpeg"


def ffprobe_bin() -> str:
    """Chemin de ffprobe (embarqué si présent, sinon système)."""
    return find_tool("ffprobe") or "ffprobe"


def check_tools() -> list[str]:
    """Retourne la liste des outils requis manquants (ffmpeg, ffprobe)."""
    missing = []
    for tool in ("ffmpeg", "ffprobe"):
        if find_tool(tool) is None:
            missing.append(tool)
    return missing


def probe_streams(path: str) -> tuple[str | None, str | None]:
    """Retourne (codec_vidéo, codec_audio) du fichier, via ffprobe."""
    try:
        out = subprocess.check_output(
            [ffprobe_bin(), "-v", "error", "-show_streams",
             "-print_format", "json", path],
            text=True,
        )
        data = json.loads(out)
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
        return None, None
    vcodec = acodec = None
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and vcodec is None:
            vcodec = s.get("codec_name")
        elif s.get("codec_type") == "audio" and acodec is None:
            acodec = s.get("codec_name")
    return vcodec, acodec


def human_size(n: int) -> str:
    units = ["o", "Ko", "Mo", "Go", "To"]
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            return f"{f:.1f} {u}"
        f /= 1024
    return f"{n} o"


def prepare_mp4(video_path: str, workdir: str, log: LogFn,
                is_cancelled: Callable[[], bool]) -> str:
    """Produit un .mp4 utilisable à partir de n'importe quelle vidéo.

    Stratégie : remux sans perte si les codecs sont compatibles MP4,
    sinon ré-encodage H.264/AAC.
    """
    src = Path(video_path)
    if not src.is_file():
        raise MergeError(f"Vidéo introuvable : {video_path}")

    vcodec, acodec = probe_streams(video_path)
    log(f"Codecs détectés : vidéo={vcodec or '?'}, audio={acodec or '?'}")

    out = os.path.join(workdir, "cover.mp4")
    faststart = ["-movflags", "+faststart"]

    is_mp4 = src.suffix.lower() in (".mp4", ".m4v", ".mov")
    can_remux = (
        vcodec in MP4_FRIENDLY_VCODECS
        and (acodec in MP4_FRIENDLY_ACODECS or acodec is None)
    )

    if is_mp4 and can_remux:
        log("Vidéo déjà compatible MP4 : remux rapide (sans perte).")
    elif can_remux:
        log("Codecs compatibles MP4 : remux rapide (sans perte).")

    if can_remux:
        maps = ["-map", "0:v:0", "-map", "0:a:0?"]
        cmd = [ffmpeg_bin(), "-y", "-i", video_path, *maps,
               "-c", "copy", *faststart, out]
        try:
            _run(cmd, log, is_cancelled)
            if Path(out).stat().st_size > 0:
                return out
        except MergeError:
            log("Remux échoué, bascule sur un ré-encodage complet.")

    log("Ré-encodage H.264/AAC (plus lent, qualité quasi identique).")
    cmd = [ffmpeg_bin(), "-y", "-i", video_path,
           "-map", "0:v:0", "-map", "0:a:0?",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "192k", *faststart, out]
    _run(cmd, log, is_cancelled)
    if Path(out).stat().st_size == 0:
        raise MergeError("La conversion vidéo a produit un fichier vide.")
    return out


def merge(req: MergeRequest, log: LogFn = _noop,
          is_cancelled: Callable[[], bool] = lambda: False,
          auto_download_script: bool = True) -> str:
    """Effectue la fusion complète et retourne le chemin du fichier final.

    Étapes : vérif outils → script vcsteg3 valide → conversion MP4 →
    copie du conteneur vers la sortie → imbrication vcsteg3 → contrôle.
    """
    missing = check_tools()
    if missing:
        raise MergeError("Outils manquants : " + ", ".join(missing) +
                         ". Installez ffmpeg.")

    container = Path(req.container_path)
    if not container.is_file():
        raise MergeError(f"Conteneur introuvable : {req.container_path}")
    if container.stat().st_size == 0:
        raise MergeError("Le conteneur est vide — créez-le d'abord avec VeraCrypt.")

    try:
        script = ensure_script(auto_download=auto_download_script)
    except VcstegError as e:
        raise MergeError(str(e)) from e
    log(f"Script vérifié : {script}")

    out_path = Path(req.output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    import tempfile
    with tempfile.TemporaryDirectory(prefix="videovault-") as workdir:
        if is_cancelled():
            raise Cancelled()

        # 1. Conversion de la vidéo de couverture.
        log("── Étape 1/3 : préparation de la vidéo ──")
        cover_mp4 = prepare_mp4(req.video_path, workdir, log, is_cancelled)
        log(f"Vidéo prête : {human_size(Path(cover_mp4).stat().st_size)}")

        # 2. Copie du conteneur vers la sortie (l'original reste intact).
        log("── Étape 2/3 : copie du conteneur ──")
        if req.keep_backup:
            bak = container.with_suffix(container.suffix + ".bak")
            if not bak.exists():
                shutil.copy2(container, bak)
                log(f"Sauvegarde du conteneur : {bak}")
        shutil.copy2(container, out_path)
        log(f"Conteneur copié vers : {out_path}")

        # 3. Imbrication via vcsteg3.py (modifie la sortie sur place).
        log("── Étape 3/3 : imbrication (vcsteg3) ──")
        if is_cancelled():
            raise Cancelled()
        cmd = [sys.executable, str(script), cover_mp4, str(out_path)]
        _run(cmd, log, is_cancelled)

    # Contrôle final.
    final_size = out_path.stat().st_size
    log(f"Fichier final : {human_size(final_size)}")
    if final_size < container.stat().st_size:
        raise MergeError("Le fichier final est anormalement petit — échec probable.")
    vcodec, _ = probe_streams(str(out_path))
    if vcodec:
        log(f"Lecture vérifiée : la vidéo s'ouvre (codec {vcodec}).")
    else:
        log("Attention : impossible de confirmer la lecture vidéo du résultat.")
    return str(out_path)
