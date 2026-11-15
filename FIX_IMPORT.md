# Fix for missing `_netucs_native` in Debian installation

The previous `build_deb.sh` shipped only `src/*.py` and `.proto` files,
while `src/native_api.py` requires a compiled pybind11 extension. The
resulting `Architecture: all` Debian package could never import successfully.

The corrected script builds the C++ extension, checks its presence, installs
it alongside the Python package, tests import from the staged package, and
marks the Debian package with the host architecture.

## Build and install (on the target Debian/Ubuntu system)

```sh
sudo apt-get install build-essential cmake python3-dev python3-pybind11 pybind11-dev python3-protobuf
./build_deb.sh
sudo apt install ./python3-netucs_*_$(dpkg --print-architecture).deb
python3 -c 'from netucs import network_client as nc; print(nc.NetworkClient)'
```

If `python3 -m pybind11 --cmakedir` is unavailable on your distribution,
install the matching pybind11 Python module or set `pybind11_DIR` to the
installed CMake package directory. Rebuild for each Python ABI and architecture.

`gscv_client.py` uses `netucs.network_client.NetworkClient`, `main()`,
`terminate()` and `terminate_requested`; these entrypoints are now routed to
the C++-backed compatibility class.

The original Python networking implementations remain available as
`network_client_legacy.py` and `network_server_legacy.py` for reference.
