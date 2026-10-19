#!/usr/bin/env python3
"""Tests fonctionnels hors interface graphique."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vcsteg_gui import engine, vcsteg_manager  # noqa: E402


def make_test_video(path: str, seconds: int = 2) -> None:
    """Génère une petite vidéo mkv (H.264/AAC) de test."""
    subprocess.check_call([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=size=320x240:rate=15:d={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-c:v", "libx264", "-c:a", "aac", "-shortest", path,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_probe_and_convert():
    print("== Test 1 : conversion mkv -> mp4 ==")
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "clip.mkv")
        make_test_video(src)
        vcodec, acodec = engine.probe_streams(src)
        print(f"  codecs source : {vcodec}/{acodec}")
        assert vcodec == "h264", vcodec
        logs = []
        out = engine.prepare_mp4(src, d, logs.append, lambda: False)
        assert os.path.getsize(out) > 0
        vcodec2, _ = engine.probe_streams(out)
        assert vcodec2 in engine.MP4_FRIENDLY_VCODECS
        print(f"  sortie OK : {engine.human_size(os.path.getsize(out))}, codec {vcodec2}")
    print("  OK\n")


def test_full_merge_with_stub(monkeypatch_target):
    print("== Test 2 : flux de fusion complet (stub vcsteg3) ==")
    # Stub qui imite vcsteg3 : préfixe le conteneur avec les octets de la vidéo.
    stub = f"""import sys
video, container = sys.argv[1], sys.argv[2]
with open(video, 'rb') as v: vdata = v.read()
with open(container, 'rb') as c: cdata = c.read()
with open(container, 'wb') as c: c.write(vdata + cdata)
print('stub merge done')
"""
    with tempfile.TemporaryDirectory() as d:
        stub_path = os.path.join(d, "vcsteg3_stub.py")
        Path(stub_path).write_text(stub)

        # Forcer le moteur à utiliser notre stub au lieu du vrai script.
        engine.ensure_script = lambda auto_download=True: Path(stub_path)

        src = os.path.join(d, "clip.mkv")
        make_test_video(src)
        container = os.path.join(d, "secret.hc")
        Path(container).write_bytes(os.urandom(2 * 1024 * 1024))  # 2 Mo
        out = os.path.join(d, "final.mp4")

        req = engine.MergeRequest(video_path=src, container_path=container,
                                  output_path=out, keep_backup=True)
        logs = []
        result = engine.merge(req, log=logs.append, auto_download_script=False)

        assert os.path.exists(result), "sortie manquante"
        assert os.path.exists(container + ".bak"), "sauvegarde manquante"
        orig = os.path.getsize(container)
        final = os.path.getsize(result)
        assert final > orig, f"final {final} <= orig {orig}"
        print(f"  conteneur original : {engine.human_size(orig)}")
        print(f"  fichier final : {engine.human_size(final)}")
        print(f"  sauvegarde .bak présente : oui")
    print("  OK\n")


def test_sha_pinning():
    print("== Test 3 : vérification SHA256 (rejet d'un faux script) ==")
    with tempfile.TemporaryDirectory() as d:
        fake = os.path.join(d, "vcsteg3.py")
        Path(fake).write_text("print('malveillant')")
        digest = vcsteg_manager.sha256_of(fake)
        assert digest != vcsteg_manager.VCSTEG3_SHA256
        print(f"  faux script -> empreinte {digest[:16]}… ≠ attendue : rejeté")
    print("  OK\n")


if __name__ == "__main__":
    test_probe_and_convert()
    test_full_merge_with_stub(None)
    test_sha_pinning()
    print("TOUS LES TESTS PASSENT ✓")
