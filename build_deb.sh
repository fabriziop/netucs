#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
PKG=python3-netucs
REL=1
ARCH=all
STAGE=debian
OUT=${PKG}_${VERSION}-${REL}_${ARCH}.deb
PKG_DIR="$STAGE/usr/lib/python3/dist-packages/netucs"
DOC_DIR="$STAGE/usr/share/doc/$PKG"

rm -rf "$STAGE"
mkdir -p \
  "$STAGE/DEBIAN" \
  "$PKG_DIR" \
  "$DOC_DIR"

cp -r src/. "$PKG_DIR/"
find "$PKG_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$PKG_DIR" -type f -name '*.pyc' -delete

cp README.md "$DOC_DIR/README.md"
cp LICENSE "$DOC_DIR/copyright"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG
Version: ${VERSION}-${REL}
Section: python
Priority: optional
Architecture: $ARCH
Maintainer: Fabrizio Pollastri <mxgbot@gmail.com>
Depends: python3 (>= 3.8)
Homepage: https://github.com/fabriziop/netucs
Description: Network UDP Client Server data exchange
 Asynchronous client/server UDP communication library for Python 3.
EOF

find "$STAGE/usr" -type d -exec chmod 0755 {} +
find "$STAGE/usr" -type f -exec chmod 0644 {} +
chmod 0755 "$STAGE/DEBIAN"
chmod 0644 "$STAGE/DEBIAN/control"

rm -f "$OUT"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT"

echo "Built package: $OUT"