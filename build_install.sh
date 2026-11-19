#!/usr/bin/env bash
# Interactive NetUCS build/install entry point; run from anywhere.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

ask_choice() {
  local prompt="$1" default="$2" answer
  shift 2
  while true; do
    read -r -p "$prompt [$default]: " answer || exit 1
    answer="${answer:-$default}"
    for valid in "$@"; do
      if [[ "$answer" == "$valid" ]]; then REPLY="$answer"; return; fi
    done
    printf 'Invalid selection: %s\n' "$answer" >&2
  done
}

printf '\nNetUCS build / install\n'
printf '  1) CMake: build only\n'
printf '  2) CMake: build and install everything\n'
printf '  3) CMake: build and install runtime only\n'
printf '  4) CMake: build and install development files only\n'
printf '  5) CMake: build and install Python bindings only\n'
printf '  6) Debian: build runtime, development and Python .deb packages\n'
ask_choice 'Select operation (1-6)' 1 1 2 3 4 5 6
mode="$REPLY"

if [[ "$mode" == 6 ]]; then
  command -v dpkg-buildpackage >/dev/null || { echo 'Missing dpkg-buildpackage (install dpkg-dev).' >&2; exit 1; }
  echo 'Building Debian packages (no automatic installation)...'
  exec "$ROOT/build_deb.sh"
fi

command -v cmake >/dev/null || { echo 'Missing cmake.' >&2; exit 1; }
ask_choice 'Configuration: 1) Release 2) Debug' 1 1 2
if [[ "$REPLY" == 1 ]]; then config=Release; else config=Debug; fi
read -r -p 'Build directory [build-${config,,}]: ' build_dir || exit 1
build_dir="${build_dir:-build-${config,,}}"
read -r -p 'Installation prefix [/usr/local]: ' prefix || exit 1
prefix="${prefix:-/usr/local}"
ask_choice 'Build Python bindings? 1) no 2) yes' "$([[ "$mode" == 5 ]] && echo 2 || echo 1)" 1 2
if [[ "$REPLY" == 2 ]]; then python_flag=ON; else python_flag=OFF; fi
if [[ "$mode" == 5 && "$python_flag" != ON ]]; then
  echo 'Python-only installation requires Python bindings enabled.' >&2
  exit 1
fi
ask_choice 'Build and run C++ tests? 1) yes 2) no' 1 1 2
if [[ "$REPLY" == 1 ]]; then tests_flag=ON; else tests_flag=OFF; fi

cmake -S "$ROOT" -B "$build_dir" \
  -DCMAKE_BUILD_TYPE="$config" \
  -DCMAKE_INSTALL_PREFIX="$prefix" \
  -DNETUCS_BUILD_PYTHON="$python_flag" \
  -DNETUCS_BUILD_TESTS="$tests_flag"
cmake --build "$build_dir" --parallel
if [[ "$tests_flag" == ON ]]; then
  ctest --test-dir "$build_dir" --output-on-failure
fi
if [[ "$mode" == 1 ]]; then
  echo 'Build completed; nothing installed.'
  exit 0
fi

case "$mode" in
  2) component='';;
  3) component=Runtime;;
  4) component=Development;;
  5) component=Python;;
esac
printf '\nInstall prefix: %s\n' "$prefix"
if [[ -n "$component" ]]; then printf 'Component: %s\n' "$component"; else echo 'Components: all'; fi
if [[ "$mode" == 4 || "$mode" == 5 ]]; then
  echo 'Note: this component requires the NetUCS runtime to be installed separately.'
fi
ask_choice 'Installation privileges: 1) normal user 2) sudo' 1 1 2
if [[ "$REPLY" == 2 ]]; then install_cmd=(sudo cmake); else install_cmd=(cmake); fi
ask_choice 'Proceed with installation? 1) yes 2) no' 1 1 2
if [[ "$REPLY" != 1 ]]; then echo 'Installation skipped.'; exit 0; fi
args=(--install "$build_dir")
if [[ -n "$component" ]]; then args+=(--component "$component"); fi
"${install_cmd[@]}" "${args[@]}"
echo 'Installation completed.'
