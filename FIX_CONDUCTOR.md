# Conductor C++ dependency

Netucs uses the system-installed **C++** Conductor library, not just its Python extension. It requires `conductor/scheduler.hpp` and `libconductor.a` (or `.so`). No Conductor source or binaries are bundled in netucs.

Check the installation:

```sh
find /usr /usr/local -name scheduler.hpp -o -name libconductor.a -o -name libconductor.so 2>/dev/null
```

If absent, from the separate Conductor source checkout:

```sh
cmake -S . -B build -DCONDUCTOR_BUILD_PYTHON=OFF -DCONDUCTOR_BUILD_EXAMPLES=OFF
cmake --build build -j$(nproc)
sudo cmake --install build
```

Then build netucs:

```sh
./build_deb.sh
```

For a nonstandard installation prefix, use `CONDUCTOR_ROOT=/opt/conductor ./build_deb.sh`, or specify `CONDUCTOR_INCLUDE_DIR=/path/to/include CONDUCTOR_LIBRARY=/path/to/libconductor.a ./build_deb.sh`. The include directory is the directory *containing* `conductor/`, not the `conductor/` directory itself.
