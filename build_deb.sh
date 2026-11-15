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

ARCH=$(dpkg --print-architecture)
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

for tool in cmake c++ python3; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "Error: $tool is required to build the native extension" >&2; exit 1;
  }
done
PYBIND_CMAKE_DIR=$(python3 -m pybind11 --cmakedir 2>/dev/null || true)
if [ -z "$PYBIND_CMAKE_DIR" ]; then
  echo "Error: pybind11 is missing; install python3-pybind11 or pybind11-dev." >&2
  exit 1
fi
# Optional overrides: CONDUCTOR_ROOT, CONDUCTOR_INCLUDE_DIR, CONDUCTOR_LIBRARY.
conductor_args=()
for var in CONDUCTOR_ROOT CONDUCTOR_INCLUDE_DIR CONDUCTOR_LIBRARY; do
  if [ -n "${!var:-}" ]; then
    conductor_args+=("-D${var}=${!var}")
  fi
done
cmake -S . -B build-deb -DNETUCS_BUILD_PYTHON=ON -DNETUCS_BUILD_TESTS=OFF \
  -Dpybind11_DIR="$PYBIND_CMAKE_DIR" -DCMAKE_BUILD_TYPE=Release \
  "${conductor_args[@]}"
cmake --build build-deb --parallel "${JOBS:-2}"
NATIVE_SO=$(find build-deb -maxdepth 2 -type f -name '_netucs_native*.so' -print -quit)
if [ -z "$NATIVE_SO" ]; then
  echo "Error: C++ build did not produce _netucs_native*.so" >&2
  exit 1
fi
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

cp src/*.proto "$PKG_DIR/"
cp "$NATIVE_SO" "$PKG_DIR/"
# Fail the build if the installed package cannot import its native extension.
PYTHONPATH="$STAGE/usr/lib/python3/dist-packages" python3 -c \
  'import netucs; from netucs import network_client; assert network_client.NetworkClient is netucs.NetworkClient' 

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
Depends: python3 (>= 3.9), python3-protobuf (>= 3.20.3), libstdc++6, libc6
Recommends: python3-numpy
Homepage: https://github.com/fabriziop/netucs
Description: Network UDP Client Server data exchange
 Native C++20 client/server UDP communication with Python 3 bindings.
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
