"""
GUI Tangerine Linux v1 — drop-zone + wheel.

Alur v1 (kompromi Linux, lihat README):
1. User seret file dari Nemo/Nautilus ke drop-zone (atau klik untuk memilih).
2. Wheel muncul berisi format yang valid untuk file itu.
3. User klik satu sektor -> konversi lokal -> hasil di sebelah file asli.

Konversi jalan di QThread supaya UI tidak freeze.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from .converters import ConversionError, convert_many, detect_kind, formats_for
from .editor import ImageEditorDialog
from .overlay import WheelOverlay
from .statemachine import DragTracker
from .wheel import WheelWidget
from .xpoll import X11Poller, session_is_x11

KIND_LABEL = {
    "pdf": "PDF", "image": "Gambar", "video": "Video",
    "audio": "Audio", "text": "Teks",
}


class ConvertWorker(QThread):
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, files: list[Path], fmt: str):
        super().__init__()
        self._files, self._fmt = files, fmt

    def run(self) -> None:
        try:
            self.done.emit([str(p) for p in convert_many(self._files, self._fmt)])
        except ConversionError as e:
            self.failed.emit(str(e))
        except Exception as e:  # jaga-jaga: jangan sampai thread mati diam-diam
            self.failed.emit(f"Error tak terduga: {e}")


class DropZone(QLabel):
    filesDropped = Signal(list)

    def __init__(self):
        super().__init__("🍊\n\nSeret file ke sini\natau klik untuk memilih file")
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.setMinimumHeight(110)
        self.setStyleSheet(
            "QLabel{border:2px dashed #ff7a1a;border-radius:14px;"
            "padding:18px;font-size:15px;color:#26221f;background:#ffffff}"
        )

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):  # noqa: N802
        files = [Path(u.toLocalFile()) for u in event.mimeData().urls()
                 if u.isLocalFile()]
        if files:
            self.filesDropped.emit(files)

    def mousePressEvent(self, event):  # noqa: N802
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Pilih file",
            "", "Didukung (*.pdf *.jpg *.jpeg *.png *.webp *.bmp *.tiff "
                "*.mp4 *.mov *.mkv *.webm *.mp3 *.wav *.ogg *.flac "
                "*.txt *.text *.md *.log *.csv *.ini *.cfg *.sh *.py *.json);;"
                "Semua file (*)")
        if paths:
            self.filesDropped.emit([Path(p) for p in paths])


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        from . import __version__
        self.setWindowTitle(f"Tangerine Linux 🍊 — v{__version__}")
        self.resize(520, 640)
        self._files: list[Path] = []
        self._worker: ConvertWorker | None = None

        self.drop = DropZone()
        self.drop.filesDropped.connect(self.on_files)

        self.info = QLabel("Belum ada file.")
        self.info.setWordWrap(True)

        self.wheel = WheelWidget()
        self.wheel.formatSelected.connect(self.on_format)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.hide()

        self.status = QLabel("")
        self.status.setWordWrap(True)

        self.open_btn = QPushButton("Buka folder hasil")
        self.open_btn.hide()
        self.open_btn.clicked.connect(self.open_folder)
        self._last_folder: Path | None = None

        self.edit_btn = QPushButton("✂️ Crop & Add BG (1 gambar)")
        self.edit_btn.setEnabled(False)
        self.edit_btn.clicked.connect(self.on_edit)

        # ---- Mode global Shift+Drag (v2, X11 eksperimental) ----
        self.global_btn = QPushButton("🖱️ Aktifkan mode global Shift+Drag (X11)")
        self.global_btn.clicked.connect(self.toggle_global)
        self._poller: X11Poller | None = None
        self._tracker = DragTracker()
        self._overlay: WheelOverlay | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(25)
        self._poll_timer.timeout.connect(self._poll_global)

        layout = QVBoxLayout()
        layout.addWidget(self.drop)
        layout.addWidget(self.info)
        layout.addWidget(self.wheel, stretch=1)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.global_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.open_btn)
        layout.addLayout(btn_row)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    # ------------------------------------------------------------- flow
    def on_files(self, files: list[Path]) -> None:
        self.edit_btn.setEnabled(False)
        supported = [f for f in files if detect_kind(f) is not None]
        skipped = [f.name for f in files if detect_kind(f) is None]
        if not supported:
            self.status.setText("⚠️ Tipe file belum didukung di v1: "
                                + ", ".join(skipped))
            return
        kinds = {detect_kind(f) for f in supported}
        if len(kinds) > 1:
            self.status.setText("⚠️ Campur tipe file belum didukung — "
                                "drop file sejenis saja ya (mis. semua PDF / semua gambar).")
            return
        # Format wheel = irisan format valid semua file
        common = set(formats_for(supported[0]))
        for f in supported[1:]:
            common &= set(formats_for(f))
        if not common:
            self.status.setText("⚠️ Nggak ada format tujuan yang sama untuk file-file ini.")
            return
        order = [f for f in formats_for(supported[0]) if f in common]
        self._files = supported
        self.edit_btn.setEnabled(
            len(supported) == 1 and detect_kind(supported[0]) == "image")
        kind = KIND_LABEL[detect_kind(supported[0])]
        names = ", ".join(f.name for f in supported[:3])
        if len(supported) > 3:
            names += f", +{len(supported) - 3} lagi"
        self.info.setText(f"📄 {len(supported)} file {kind}: {names}\n"
                          "Klik format di wheel untuk konversi 👇")
        center = supported[0].name if len(supported) == 1 else f"{len(supported)} file"
        self.wheel.set_wheel(order, center)
        msg = "Siap. Semua konversi lokal, hasil disimpan di sebelah file asli."
        if skipped:
            msg += f" (Dilewati, tak didukung: {', '.join(skipped)})"
        self.status.setText(msg)
        self.open_btn.hide()

    def on_format(self, fmt: str) -> None:
        if not self._files or (self._worker and self._worker.isRunning()):
            return
        self.progress.show()
        self.status.setText(f"⏳ Mengonversi ke {fmt}…")
        self._worker = ConvertWorker(self._files, fmt)
        self._worker.done.connect(self.on_done)
        self._worker.failed.connect(self.on_failed)
        self._worker.start()

    def on_done(self, outputs: list) -> None:
        self.progress.hide()
        names = "\n".join(f"• {Path(o).name}" for o in outputs)
        self.status.setText(f"✅ Beres! {len(outputs)} file hasil:\n{names}")
        if outputs:
            self._last_folder = Path(outputs[0]).parent
            self.open_btn.show()

    def on_failed(self, msg: str) -> None:
        self.progress.hide()
        self.status.setText(f"❌ {msg}")

    def on_edit(self) -> None:
        if len(self._files) != 1 or detect_kind(self._files[0]) != "image":
            return
        dlg = ImageEditorDialog(self._files[0], self)
        if dlg.exec() and dlg.saved_path is not None:
            self.status.setText(
                f"✅ Hasil edit tersimpan: {dlg.saved_path.name} "
                f"(di sebelah {self._files[0].name})")
            self._last_folder = dlg.saved_path.parent
            self.open_btn.show()

    def open_folder(self) -> None:
        if self._last_folder:
            subprocess.Popen(["xdg-open", str(self._last_folder)])

    # ------------------------------------------------- mode global (v2)
    def toggle_global(self) -> None:
        if self._poller is not None:
            self._poll_timer.stop()
            self._poller.close()
            self._poller = None
            if self._overlay:
                self._overlay.hide()
            self.global_btn.setText("🖱️ Aktifkan mode global Shift+Drag (X11)")
            self.status.setText("Mode global mati.")
            return
        if not session_is_x11():
            self.status.setText(
                "⚠️ Mode global butuh sesi X11 — sesi kamu terdeteksi bukan X11 "
                "(Wayland mengunci intip drag global). Di Mint: logout, di layar "
                "login pilih sesi Cinnamon on X11, lalu coba lagi. Mode drop-zone "
                "di atas tetap jalan di sesi apa pun.")
            return
        try:
            self._poller = X11Poller()
        except RuntimeError as e:
            self.status.setText(f"⚠️ {e}")
            return
        if self._overlay is None:
            self._overlay = WheelOverlay()
            self._overlay.dropped.connect(self.on_overlay_drop)
        self._tracker.reset()
        self._poll_timer.start()
        self.global_btn.setText("⏹️ Matikan mode global Shift+Drag")
        self.status.setText(
            "🟢 Mode global AKTIF (eksperimental). Sekarang coba: seret file "
            "di Nemo, tahan Shift sambil menyeret — wheel muncul di kursor. "
            "Geser ke sektor format, lalu lepas mouse untuk konversi.")

    def _poll_global(self) -> None:
        if self._poller is None or self._overlay is None:
            return
        # Jangan ganggu drag yang sedang masuk ke overlay (Qt yang pegang).
        if self._overlay.isVisible() and self._overlay._files:
            return
        try:
            event = self._tracker.feed(self._poller.sample())
        except Exception:
            return
        if event == "show":
            self._overlay.show_at_cursor()
        elif event == "hide":
            self._overlay.hide()

    def on_overlay_drop(self, files: list, fmt: str) -> None:
        self._files = [Path(f) for f in files]
        self.info.setText(f"🎯 Dari mode global: {len(self._files)} file → {fmt}")
        self.on_format(fmt)


# Tema terang "frosted glass" ala Tangerine asli — berlaku app-wide,
# termasuk dialog editor (menimpa tema gelap bawaan desktop).
LIGHT_THEME = """
QMainWindow, QDialog { background: #f6f4ef; }
QLabel { color: #26221f; }
QCheckBox { color: #26221f; }
QPushButton { background: #ffffff; color: #26221f; border: 1px solid #d8d3c8;
              border-radius: 8px; padding: 6px 10px; }
QPushButton:hover { border-color: #ff7a1a; }
QPushButton:disabled { color: #a49e93; background: #efece6; }
QComboBox { background: #ffffff; color: #26221f; border: 1px solid #d8d3c8;
            border-radius: 6px; padding: 4px; }
"""


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(LIGHT_THEME)
    win = MainWindow()
    win.show()
    return app.exec()
