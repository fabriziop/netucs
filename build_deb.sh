#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# dpkg-buildpackage writes artifacts to the parent directory; copy packages
# back to the NetUCS repository root as requested.
dpkg-buildpackage -us -uc -b "$@"
shopt -s nullglob
for package in ../libnetucs0_*.deb ../libnetucs-dev_*.deb ../python3-netucs_*.deb; do
  cp -f -- "$package" ./
done
printf 'Debian packages copied to %s\n' "$PWD"
