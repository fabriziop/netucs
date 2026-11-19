# Debian packaging

NetUCS follows Conductor's three-package Debian layout:

* `libnetucs0`: shared native runtime (`libnetucs.so.0`).
* `libnetucs-dev`: C++ headers, linker symlink and CMake config; requires `libconductor-dev`.
* `python3-netucs`: Python modules and native bindings; depends on `libnetucs0`.

Install Conductor's `libconductor-dev` and its runtime before building.
Run `./build_deb.sh` from any directory. `dpkg-buildpackage` creates packages
in the parent directory, and the script copies `.deb` files to the NetUCS
repository root. Debian packaging metadata lives in `debian/`; build products
must not be committed.

CMake consumers can use `find_package(netucs CONFIG REQUIRED)` and link
`netucs::netucs`; the exported target resolves Conductor through its CMake
package configuration.

The native C++ sources are in `src/cpp/`, matching Conductor's `src/` layout.
The existing Python package remains in `src/` to preserve imports and wheel
configuration. Conductor's `build_deb.sh` is otherwise kept independent.
