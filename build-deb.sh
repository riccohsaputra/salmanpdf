#!/usr/bin/env bash
# Build .deb Tangerine Linux dari source + packaging/.
# PENTING: -Zgzip wajib — dpkg di Mint Ricco tidak bisa membaca .deb
# berkompresi zstd (default dpkg-deb baru).
set -e
cd "$(dirname "$0")"
VER=$(python3 -c "import re;print(re.search(r'__version__ = \"(.+)\"', open('tangerine/__init__.py').read()).group(1))")
BUILD=deb-build
rm -rf "$BUILD"
mkdir -p "$BUILD/pkg/DEBIAN" "$BUILD/pkg/opt/tangerine-linux" "$BUILD/pkg/usr/bin" "$BUILD/pkg/usr/share/applications"
cp -r main.py run.sh requirements.txt README.md tangerine tests packaging "$BUILD/pkg/opt/tangerine-linux/"
find "$BUILD/pkg/opt" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
sed "s/^Version: .*/Version: $VER/" packaging/control > "$BUILD/pkg/DEBIAN/control"
cp packaging/postinst "$BUILD/pkg/DEBIAN/postinst"
cp packaging/tangerine-linux.bin "$BUILD/pkg/usr/bin/tangerine-linux"
cp packaging/tangerine-linux.desktop "$BUILD/pkg/usr/share/applications/"
chmod 755 "$BUILD/pkg/DEBIAN" "$BUILD/pkg/DEBIAN/postinst" "$BUILD/pkg/usr/bin/tangerine-linux"
OUT="$HOME/workspace/your_files/tangerine-linux_${VER}_all.deb"
dpkg-deb -Zgzip -b "$BUILD/pkg" "$OUT"
echo "✅ $OUT"
