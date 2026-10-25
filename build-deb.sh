#!/usr/bin/env bash
# Build .deb SalmanPDF dari source + packaging/.
# PENTING: -Zgzip wajib — dpkg di Mint Ricco tidak bisa membaca .deb
# berkompresi zstd (default dpkg-deb baru).
set -e
cd "$(dirname "$0")"
VER=$(python3 -c "import re;print(re.search(r'__version__ = \"(.+)\"', open('salmanpdf/__init__.py').read()).group(1))")
BUILD=deb-build
rm -rf "$BUILD"
mkdir -p "$BUILD/pkg/DEBIAN" "$BUILD/pkg/opt/salmanpdf" "$BUILD/pkg/usr/bin" "$BUILD/pkg/usr/share/applications"
cp -r main.py run.sh requirements.txt README.md salmanpdf tests packaging "$BUILD/pkg/opt/salmanpdf/"
find "$BUILD/pkg/opt" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
sed "s/^Version: .*/Version: $VER/" packaging/control > "$BUILD/pkg/DEBIAN/control"
cp packaging/postinst "$BUILD/pkg/DEBIAN/postinst"
cp packaging/salmanpdf.bin "$BUILD/pkg/usr/bin/salmanpdf"
cp packaging/salmanpdf.desktop "$BUILD/pkg/usr/share/applications/"
# Ikon PNG dihasilkan dari data tertanam (icon_data.py) bila file
# assets belum ada (snapshot GitHub hanya membawa file teks).
if [ ! -f salmanpdf/assets/appicon-512.png ]; then
  PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
  "$PY" - <<'PYEOF'
import base64, sys
sys.path.insert(0, ".")
from pathlib import Path
from PIL import Image
import io
from salmanpdf.icon_data import APPICON_PNG_B64
img = Image.open(io.BytesIO(base64.b64decode(APPICON_PNG_B64)))
out = Path("salmanpdf/assets"); out.mkdir(exist_ok=True)
for sz in (512, 256, 128, 64, 48):
    img.resize((sz, sz), Image.Resampling.LANCZOS).save(out / f"appicon-{sz}.png")
img.save(out / "appicon.png")
PYEOF
fi
for sz in 512 256 128 64 48; do
  mkdir -p "$BUILD/pkg/usr/share/icons/hicolor/${sz}x${sz}/apps"
  cp "salmanpdf/assets/appicon-${sz}.png" "$BUILD/pkg/usr/share/icons/hicolor/${sz}x${sz}/apps/salmanpdf.png"
done
chmod 755 "$BUILD/pkg/DEBIAN" "$BUILD/pkg/DEBIAN/postinst" "$BUILD/pkg/usr/bin/salmanpdf"
OUT="$HOME/workspace/your_files/salmanpdf_${VER}_all.deb"
dpkg-deb -Zgzip -b "$BUILD/pkg" "$OUT"
echo "✅ $OUT"
