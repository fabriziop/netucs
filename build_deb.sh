#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Get version from git tag, removing the 'v' prefix
VERSION=$(git describe --tags --abbrev=0 | sed 's/^v//')
if [ -z "$VERSION" ]; then
    echo "Error: No git tag found. Please create a tag (e.g., git tag -a v1.0.0 -m 'Version 1.0.0')."
    exit 1
fi

# Update version in debian/changelog if it exists
if [ -f "debian/changelog" ]; then
    dch -v "${VERSION}-1" "New upstream release."
fi

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

rm -f "${PKG}_*_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT"

echo "Built package: $OUT"
