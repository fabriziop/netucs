# netucs C++ migration: implementation and compatibility

This tree retains `.git` and the original Python modules for protocol regression
comparison. C++20 implements the UDP transport and the `netucs.Value` protobuf
codec; Conductor schedules periodic transport work. The Python interface uses
pybind11 and a small queue adapter in `src/native_api.py`.

## Build and test

```sh
cmake -S . -B build -DNETUCS_BUILD_PYTHON=OFF -DNETUCS_BUILD_TESTS=ON
cmake --build build -j
ctest --test-dir build --output-on-failure
python -m pip install --build-isolation .
python -m pytest -q tests/test_native.py tests/test_serialization.py tests/test_arrays.py tests/test_protocol.py
```

The Python build needs `scikit-build-core` and `pybind11` from the build
requirements. The C++ library requires a POSIX platform and C++20. `numpy` is
optional, required only for numeric array payloads. The original protobuf
Python package is retained for compatibility and comparison tests.

## Native C++ API

```cpp
#include <netucs/network.hpp>
#include <netucs/value.hpp>
#include <iostream>

netucs::ServerConfig config;
config.address = "127.0.0.1";
config.port = 12345;
netucs::NetworkServer server(config);
server.start();
netucs::Value::Mapping values;
values["temperature"] = netucs::Value{23.5};
server.publish_value(netucs::Value{values});
server.terminate();
server.join();
```

`publish_value()` accepts the typed C++ variant; `publish()` accepts an already
serialized protobuf payload. Client callbacks receive timestamp and encoded
payload, which may be decoded with `netucs::deserialize()`. `NumericArray`
contains a dtype name, shape and little-endian row-major bytes. Dtypes,
shape limits and byte count are checked on encode and decode.

## Python API

```python
from netucs import NetworkClient, NetworkServer
from queue import Queue

outgoing, incoming = Queue(), Queue()
server = NetworkServer('127.0.0.1', 12345, 30, outgoing)
client = NetworkClient('127.0.0.1', 12345, 30, 5, 2, incoming)
server.start()
client.start()
outgoing.put({'temperature': 23.5})
# ...
client.terminate()
server.terminate()
client.join()
server.join()
```

The binding also exports `_netucs_native.serialize(value)` and
`_netucs_native.deserialize(bytes)` for direct value conversion, including
NumPy arrays, tuples and dictionaries. The queue wrapper uses native
`publish_value()` and receives native-decoded values, not the legacy Python
protobuf serializer. `main()` is blocking; `start()` launches a background
thread. `terminate()` and `shutdown()` request stop; `join()` waits.

## Compatibility and remaining limitations

- Protocol version 3 and protobuf field numbering are retained. The original
  Python protocol and serialization tests, plus native round-trip and UDP
  integration tests, serve as compatibility checks.
- The old asyncio-specific `run()` and `asyncio.DatagramProtocol` extension
  hooks are not implemented; applications using those internals need changes.
- POSIX IPv4 UDP is supported; Windows and IPv6 are not implemented.
- Fatal-error callback and detailed error propagation from background C++
  threads are not yet equivalent to the original Python implementation.
- Backoff and reconnection are implemented at a basic level, but exhaustive
  fault-injection and interoperability tests with a separate legacy process
  are still needed before claiming production parity.
- Python wheel installation requires the declared build dependencies; offline
  environments must provide them locally.

## System Conductor dependency

Conductor is **not bundled or built** by netucs. Install the Conductor C++
headers and library on the system first (typically `libconductor.a` and
`include/conductor/scheduler.hpp`). CMake searches system library/include paths.
For a custom installation prefix, set `CMAKE_PREFIX_PATH` or explicitly set
`CONDUCTOR_INCLUDE_DIR` and `CONDUCTOR_LIBRARY` when configuring netucs.

```sh
cmake -S . -B build -DNETUCS_BUILD_PYTHON=OFF \
  -DCONDUCTOR_INCLUDE_DIR=/usr/local/include \
  -DCONDUCTOR_LIBRARY=/usr/local/lib/libconductor.a
cmake --build build
```

Debian package builds likewise require the system-installed Conductor library
and headers. Conductor is not included in the resulting package.
