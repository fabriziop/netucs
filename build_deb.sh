#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "Error: dpkg-deb not found in PATH" >&2
  exit 1
fi

# Shared upstream version for Python and Debian packages.
VERSION=$(cat VERSION)
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Error: VERSION must contain MAJOR.MINOR.PATCH" >&2
  exit 1
fi

PKG=python3-netucs
REL=1
COUNTER_FILE=.deb-build-counter
IS_RELEASE=false
# Only a clean checkout of a matching release tag gets the release revision.
if command -v git >/dev/null 2>&1 && \
   [ "$(git rev-parse --show-toplevel 2>/dev/null || true)" = "$PWD" ] && \
   [ -n "$(git tag --points-at HEAD --list "$VERSION" "v$VERSION")" ] && \
   [ -z "$(git --no-optional-locks status --porcelain --untracked-files=all)" ]; then
  IS_RELEASE=true
fi

if [ "$IS_RELEASE" = false ]; then
  counter=0
  if [ -f "$COUNTER_FILE" ]; then
    if ! read -r counter_version counter extra < "$COUNTER_FILE" || \
       [[ ! "$counter" =~ ^(0|[1-9][0-9]{0,8})$ ]] || [ -n "$extra" ]; then
      echo "Error: invalid $COUNTER_FILE; expected VERSION and a build counter" >&2
      exit 1
    fi
    [ "$counter_version" = "$VERSION" ] || counter=0
  fi
  counter=$((counter + 1))
  REL="${REL}+build${counter}"
fi

ARCH=all
STAGE=debian
OUT=${PKG}_${VERSION}-${REL}_${ARCH}.deb
PKG_DIR="$STAGE/usr/lib/python3/dist-packages/netucs"
DOC_DIR="$STAGE/usr/share/doc/$PKG"

cleanup_generated() {
  rm -rf build build-deb debpkg dist .eggs
  rm -rf src/*.egg-info
  find . -type d -name '__pycache__' -prune -exec rm -rf {} +
  find . -type f -name '*.pyc' -delete
  find . -type f -name '*.egg' -delete
}

cleanup_generated
rm -rf "$STAGE"
mkdir -p \
  "$STAGE/DEBIAN" \
  "$PKG_DIR" \
  "$DOC_DIR"

# Install the netucs package, including __init__.py for its relative imports.
for module in src/*.py; do
  name=$(basename "$module")
  cp "$module" "$PKG_DIR/$name"
done

cp README.md "$DOC_DIR/README.md"
cp LICENSE "$DOC_DIR/copyright"

cat > "$DOC_DIR/copyright" <<EOF2
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: plugin-manager
Source: local

Files: *
Copyright: 2026 Fabrizio Pollastri
License: GPL-3.0-or-later
 This package is distributed under the terms of the GNU General Public License,
 version 3 or later.
EOF2


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

# Count successful development builds only; release builds leave it untouched.
if [ "$IS_RELEASE" = false ]; then
  printf '%s %s\n' "$VERSION" "$counter" > "$COUNTER_FILE"
fi

cleanup_generated

echo "Built package: $OUT"
