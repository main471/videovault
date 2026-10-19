"""Interface graphique PySide6 (style Ubuntu/Yaru).

L'application ne fait QUE la fusion. Trois champs : vidéo source, conteneur
caché VeraCrypt, fichier de sortie. Un bouton lance l'opération dans un
thread de travail et affiche la progression et le journal.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QVBoxLayout, QWidget,
)

from . import __app_name__, __version__
from .engine import VIDEO_EXTENSIONS, Cancelled, MergeError, MergeRequest, merge
from .style import STYLESHEET
from .vcsteg_manager import VcstegError, download_script, find_valid_script


class Worker(QThread):
    """Thread de travail : exécute la fusion sans bloquer l'interface."""

    log = Signal(str)
    done = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, req: MergeRequest):
        super().__init__()
        self._req = req
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            out = merge(self._req, log=self.log.emit,
                        is_cancelled=lambda: self._cancel,
                        auto_download_script=True)
            self.done.emit(out)
        except Cancelled:
            self.cancelled.emit()
        except (MergeError, VcstegError) as e:
            self.failed.emit(str(e))
        except Exception as e:  # noqa: BLE001 — remonter toute erreur à l'UI
            self.failed.emit(f"Erreur inattendue : {e}")


class DownloadWorker(QThread):
    """Télécharge et vérifie vcsteg3.py en arrière-plan."""

    done = Signal(str)
    failed = Signal(str)

    def run(self) -> None:
        try:
            path = download_script()
            self.done.emit(str(path))
        except VcstegError as e:
            self.failed.emit(str(e))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"Erreur inattendue : {e}")


def _row(parent_layout, label_text, placeholder, button_text):
    """Construit une ligne 'label + champ + bouton' et retourne (edit, button)."""
    lbl = QLabel(label_text)
    lbl.setObjectName("StepLabel")
    parent_layout.addWidget(lbl)
    row = QHBoxLayout()
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)
    btn = QPushButton(button_text)
    row.addWidget(edit, 1)
    row.addWidget(btn)
    parent_layout.addLayout(row)
    return edit, btn


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{__app_name__} — fusion vidéo / conteneur VeraCrypt")
        self.setMinimumSize(720, 640)
        self._worker: Worker | None = None
        self._dl: DownloadWorker | None = None
        self._build_ui()
        self._refresh_script_state()

    # ---- Construction de l'interface -------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 20, 22, 16)
        root.setSpacing(14)

        title = QLabel(__app_name__)
        title.setObjectName("Title")
        root.addWidget(title)
        sub = QLabel("Dissimule un conteneur caché VeraCrypt dans une vidéo lisible. "
                     "Cette application réalise uniquement la fusion.")
        sub.setObjectName("Subtitle")
        sub.setWordWrap(True)
        root.addWidget(sub)

        card = QFrame()
        card.setObjectName("Card")
        form = QVBoxLayout(card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(10)

        self.video_edit, b1 = _row(
            form, "Vidéo source (tout format)",
            "Choisissez la vidéo de couverture…", "Parcourir")
        b1.clicked.connect(self._pick_video)

        self.container_edit, b2 = _row(
            form, "Conteneur caché VeraCrypt (créé en dehors de l'appli)",
            "Choisissez le conteneur…", "Parcourir")
        b2.clicked.connect(self._pick_container)

        self.output_edit, b3 = _row(
            form, "Fichier de sortie (.mp4)",
            "Où enregistrer la vidéo finale…", "Enregistrer sous")
        b3.clicked.connect(self._pick_output)

        self.backup_check = QCheckBox("Sauvegarder le conteneur (.bak) avant la fusion")
        self.backup_check.setChecked(True)
        form.addWidget(self.backup_check)
        root.addWidget(card)

        # État du script vcsteg3.
        script_row = QHBoxLayout()
        self.script_label = QLabel()
        self.script_label.setObjectName("Subtitle")
        self.script_label.setWordWrap(True)
        self.dl_button = QPushButton("Télécharger le script")
        self.dl_button.clicked.connect(self._download_script)
        script_row.addWidget(self.script_label, 1)
        script_row.addWidget(self.dl_button)
        root.addLayout(script_row)

        # Progression + actions.
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indéterminé
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self._cancel)
        self.merge_button = QPushButton("Fusionner")
        self.merge_button.setObjectName("Primary")
        self.merge_button.clicked.connect(self._start_merge)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.merge_button)
        root.addLayout(actions)

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("Log")
        self.log_view.setReadOnly(True)
        root.addWidget(self.log_view, 1)

        self.statusBar().showMessage(f"{__app_name__} {__version__}")

    # ---- Sélecteurs de fichiers ------------------------------------------

    def _pick_video(self) -> None:
        exts = " ".join(f"*.{e}" for e in VIDEO_EXTENSIONS)
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir la vidéo source", "",
            f"Vidéos ({exts});;Tous les fichiers (*)")
        if path:
            self.video_edit.setText(path)
            if not self.output_edit.text():
                base = os.path.splitext(os.path.basename(path))[0]
                folder = os.path.dirname(path)
                self.output_edit.setText(os.path.join(folder, f"{base}_vault.mp4"))

    def _pick_container(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir le conteneur VeraCrypt", "",
            "Tous les fichiers (*)")
        if path:
            self.container_edit.setText(path)

    def _pick_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer la vidéo finale", self.output_edit.text() or "",
            "Vidéo MP4 (*.mp4)")
        if path:
            if not path.lower().endswith(".mp4"):
                path += ".mp4"
            self.output_edit.setText(path)

    # ---- Script vcsteg3 ---------------------------------------------------

    def _refresh_script_state(self) -> None:
        found = find_valid_script()
        if found:
            self.script_label.setText(f"✓ Script vcsteg3.py vérifié : {found}")
            self.dl_button.setVisible(False)
        else:
            self.script_label.setText(
                "⚠ Script vcsteg3.py absent. Il sera téléchargé et vérifié "
                "(SHA256) au besoin, ou cliquez pour le faire maintenant.")
            self.dl_button.setVisible(True)

    def _download_script(self) -> None:
        self.dl_button.setEnabled(False)
        self._append_log("Téléchargement du script officiel vcsteg3.py…")
        self._dl = DownloadWorker()
        self._dl.done.connect(self._on_download_done)
        self._dl.failed.connect(self._on_download_failed)
        self._dl.start()

    def _on_download_done(self, path: str) -> None:
        self._append_log(f"Script téléchargé et vérifié : {path}")
        self.dl_button.setEnabled(True)
        self._refresh_script_state()

    def _on_download_failed(self, msg: str) -> None:
        self.dl_button.setEnabled(True)
        self._append_log("ÉCHEC du téléchargement : " + msg)
        QMessageBox.warning(self, "Téléchargement impossible", msg)

    # ---- Fusion -----------------------------------------------------------

    def _start_merge(self) -> None:
        video = self.video_edit.text().strip()
        container = self.container_edit.text().strip()
        output = self.output_edit.text().strip()

        if not video or not container or not output:
            QMessageBox.warning(self, "Champs manquants",
                                "Renseignez la vidéo, le conteneur et la sortie.")
            return
        if os.path.abspath(container) == os.path.abspath(output):
            QMessageBox.warning(self, "Chemins identiques",
                                "La sortie doit être différente du conteneur "
                                "original.")
            return

        req = MergeRequest(video_path=video, container_path=container,
                           output_path=output,
                           keep_backup=self.backup_check.isChecked())
        self.log_view.clear()
        self._set_running(True)
        self._worker = Worker(req)
        self._worker.log.connect(self._append_log)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.start()

    def _cancel(self) -> None:
        if self._worker:
            self._append_log("Annulation demandée…")
            self._worker.cancel()

    def _set_running(self, running: bool) -> None:
        self.progress.setVisible(running)
        self.cancel_button.setVisible(running)
        self.merge_button.setEnabled(not running)
        for w in (self.video_edit, self.container_edit, self.output_edit,
                  self.backup_check):
            w.setEnabled(not running)

    def _on_done(self, out: str) -> None:
        self._set_running(False)
        self._refresh_script_state()
        self._append_log(f"✓ Terminé : {out}")
        QMessageBox.information(
            self, "Fusion réussie",
            f"Fichier créé :\n{out}\n\n"
            "Rappels :\n"
            "• Montez-le avec le mot de passe du volume CACHÉ.\n"
            "• N'écrivez jamais dans le volume externe.\n"
            "• Ne conservez pas la vidéo d'origine à côté.")

    def _on_failed(self, msg: str) -> None:
        self._set_running(False)
        self._append_log("ÉCHEC : " + msg)
        QMessageBox.critical(self, "Échec de la fusion", msg)

    def _on_cancelled(self) -> None:
        self._set_running(False)
        self._append_log("Opération annulée.")

    def _append_log(self, line: str) -> None:
        self.log_view.appendPlainText(line)
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())


def main() -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName(__app_name__)
    app.setStyleSheet(STYLESHEET)
    win = MainWindow()
    win.show()
    return app.exec()
