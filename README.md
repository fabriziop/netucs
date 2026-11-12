# netucs - Network UDP Client Server Data Exchange

A Python package providing UDP-based asynchronous client/server data exchange for distributed signal processing applications. netucs stands for **Net**work **UCS** (UDP Client Server) data exchange.

## Description

netucs is a lightweight, asynchronous networking library built on Python's asyncio framework. It provides a robust protocol for client-server communication using UDP datagrams, designed specifically for real-time data distribution scenarios where multiple clients request data from a central server.

The package implements a request-response pattern where:
- **Clients** send periodic data requests to a server
- **Server** maintains a client registry with expiration times and sends data to active clients
- **Protocol** includes acknowledgment and error handling mechanisms

## Main Features

- **Asynchronous I/O**: Built on asyncio for efficient handling of multiple concurrent clients
- **UDP-based Communication**: Fast, lightweight datagram protocol suitable for real-time applications
- **Automatic Client Lifecycle Management**: Clients are automatically registered on first request and expire after a configurable timeout
- **Request Acknowledgment**: Server acknowledges client requests to ensure communication integrity
- **Portable Data Support**: Uses Protocol Buffers for typed, language-independent payloads, including numeric arrays
- **Configurable Timeouts**: Fine-grained control over client lifetime and request/response timing
- **Logging Integration**: Comprehensive logging at multiple levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Packet Typing**: Uses a `PacketTypeCode` to distinguish between message types (e.g., data queries, responses, acknowledgments), ensuring clients and servers can correctly interpret incoming data.

## Installation

### Building/Installing Debian Package

To build a `.deb` package for easy installation on Debian-based systems (like Ubuntu), use the provided build script.

1.  **Navigate to the project directory**:
    ```bash
    cd /path/to/your/netucs_project
    ```

2.  **Ensure the script is executable**:
    ```bash
    chmod +x build_deb.sh
    ```

3.  **Run the build script**:
    ```bash
    ./build_deb.sh
    ```
    The script creates a `.deb` file in the repository root. See the development build counter below.

4.  **Install the package**:
    You can then install the generated package on your target machine using `dpkg`.
    ```bash
    sudo apt install ./<generated_deb_file>
    ```

### From Source

Install the package and its Protobuf runtime dependency:

```bash
python3 -m pip install .
# Include numeric array support and the NumPy demo:
python3 -m pip install '.[numpy]'
```

Python requires `protobuf>=3.20.3,<7`. NumPy is optional for ordinary values;
install the `numpy` extra on both endpoints when sending arrays. The Debian
package depends on `python3-protobuf` and recommends `python3-numpy`.
The checked-in Python bindings mean no Protobuf compiler is needed at runtime.

## Quick Start

### Basic Server Example

```python
import asyncio
import queue as qu
from netucs import network_server as ns

# Create a data queue
data_queue = qu.Queue()

# Create server instance
server = ns.NetworkServer(
    address='127.0.0.1',
    port=12345,
    client_lifetime=30,  # seconds
    data_queue=data_queue
)

# Set logging level
import logging
logging.getLogger('netucs').setLevel(logging.INFO)

# Put some data in the queue
data_queue.put({'temperature': 23.5, 'humidity': 65})

# Run server (blocks until terminated)
server.main()
```

### Basic Client Example

```python
import queue as qu
from netucs import network_client as nc

# Create data receive queue
data_queue = qu.Queue()

# Create client instance
client = nc.NetworkClient(
    server_address='127.0.0.1',
    server_port=12345,
    client_lifetime=30,  # seconds
    client_lifetime_guard=5,  # seconds
    acknowledge_timeout=5,  # seconds
    data_queue=data_queue
)

# Set logging level
import logging
logging.getLogger('netucs').setLevel(logging.INFO)

# Run client (blocks until terminated)
client.main()

# Retrieve received data
while True:
    data = data_queue.get()
    print(f"Received: {data}")
```

### Client-Server Example

See `netucs/src/network_test.py` for a complete working example with producer/consumer patterns.

## Detailed API

### network_server.NetworkServer

UDP server that distributes data to registered clients on request.

#### Constructor Parameters

```python
NetworkServer(address, port, client_lifetime, data_queue)
```

- **address** (str): IP address to bind to (e.g., 192.168.1.100, '127.0.0.1')
- **port** (int): UDP port number to listen on
- **client_lifetime** (float): Time in seconds before a client is considered expired
- **data_queue** (queue.Queue): Queue from which data items are retrieved for distribution

#### Methods

**main()**
- Starts the server (blocking call)
- Creates UDP listener and data sender coroutines
- Runs until `terminate()` is called by the application

**terminate()**
- Signals server termination (application command)

**datagram_received(data, addr)**
- Callback for incoming UDP datagrams (internal use)
- Handles client registration and expiration

### network_client.NetworkClient

UDP client that requests data from the server at regular intervals.

#### Constructor Parameters

```python
NetworkClient(server_address, server_port, client_lifetime, 
              client_lifetime_guard, acknowledge_timeout, data_queue,
              backoff_min_period=1.0, backoff_max_period=60.0,
              backoff_time_constant=2.0, backoff_variance=0.1)
```

- **server_address** (str): Server IP address
- **server_port** (int): Server UDP port
- **client_lifetime** (float): Interval between data requests (seconds)
- **client_lifetime_guard** (float): Guard time before sending next request (seconds)
- **acknowledge_timeout** (float): Timeout waiting for server acknowledgment (seconds)
- **data_queue** (queue.Queue): Queue to place received data items
- **backoff_min_period** (float, optional): Minimum backoff delay in seconds (default: 1.0)
- **backoff_max_period** (float, optional): Maximum backoff delay in seconds (default: 60.0)
- **backoff_time_constant** (float, optional): Exponential backoff time constant (default: 2.0)
- **backoff_variance** (float, optional): Gaussian noise variance as fraction of base delay (default: 0.1)

#### Methods

**main()**
- Starts the client (blocking call)
- Creates UDP listener and request sender coroutines
- Runs until `terminate()` is called by the application

**terminate()**
- Signals client termination (application command)

**datagram_received(data, addr)**
- Callback for incoming UDP datagrams (internal use)
- Processes data responses and acknowledgments

### network_common Module

Contains shared protocol definitions and data structures.

#### Key Classes and Constants

**PacketTypeCode (Enum)**
- `DATA_QUERY = 1`: Client requests data from server
- `DATA_RESPONSE = 2`: Server sends data to client
- `ACKNOWLEDGE = 99`: Server acknowledges client request

**Client (dataclass)**
- Data descriptor for server client management
- Fields:
  - `addr` (str): Client address
  - `data_send_period` (float): Period for sending data
  - `data_send` (int): Timestamp of last data send
  - `expiration` (float): Time when client registration expires

**Protocol (asyncio.DatagramProtocol)**
- Base class for client and server
- Implements UDP datagram protocol hooks

#### Packet Structures

| Packet Type | Fields | Size |
|-------------|--------|------|
| Header | protocol_version (uint8), type (int16), seq_num (int16) | 5 bytes |
| Data Query | header, response_period (int32) | 9 bytes |
| Data Response | header, Protobuf `netucs.Value` | 5 bytes + payload |
| Acknowledge | header, ack_seq_num (int16), padding (2 bytes) | 9 bytes |

**Constants**
- `MAX_UDP_SIZE = 65507`: Maximum UDP datagram size

## Protocol Details

### Protocol Version

`network_common.PROTOCOL_VERSION = 3` is an unsigned one-byte field at the
start of every query, acknowledgment, and data response. All multi-byte fields
use network byte order (big-endian).

This version is independent of the code/package release version. Increment it
only when changing the packet format or handshake, not for ordinary code fixes
or releases. Values are 1 through 255; do not wrap or reuse versions.

Both endpoints discard packets whose version differs from their own and log
the mismatch before processing the payload. No version negotiation is performed.
Malformed or truncated headers, queries, and acknowledgments are also discarded.
The previous unversioned format and version 1 (pickle payloads) are incompatible:
upgrade client and server together. Version 2 peers must also be upgraded:
version 3 adds complex-array dtype semantics to the payload format. The Protobuf
field numbers and header layout are unchanged. There is no pickle fallback. A version mismatch cannot register a client or satisfy an acknowledgment.

### Protocol Buffers payload format

Only the DATA_RESPONSE body changes: the existing 5-byte network-order header,
DATA_QUERY, and ACKNOWLEDGE layouts remain unchanged, with protocol version 3
in every packet. DATA_RESPONSE contains exactly one serialized `netucs.Value`
message, defined in [src/netucs_payload.proto](src/netucs_payload.proto).
No extra length prefix is needed: the UDP datagram provides the message boundary.
The timestamp added to the client queue is still local receive time.

The Python server queue accepts the following values and nested combinations.
The client reconstructs them and queues `(receive_timestamp, value)` as before.

| Python value | Protobuf `Value.kind` | Rules |
|---|---|---|
| `None` | `null_value` | Boolean true denotes null |
| `bool` | `bool_value` | False remains distinct from null |
| `int` | `int_value` / `uint_value` | Signed 64-bit; larger positive values through 2^64-1 use uint64 |
| `float` | `float_value` | IEEE 754 double |
| `str` | `string_value` | UTF-8 |
| `bytes` | `bytes_value` | Raw bytes |
| `list`, `tuple` | `sequence_value` | Recursive values; `is_tuple` preserves tuple intent |
| `dict` | `mapping_value` | String keys only; mapping order is not a wire contract |
| NumPy array | `array_value` | Typed binary numeric data, described below |
| NumPy scalar | Corresponding scalar kind | Converted to a Python scalar |

Custom Python objects, sets, non-string dictionary keys, cyclic data, and integers
outside the supported range are rejected. Nesting is limited to 32 levels. Empty
lists, tuples, mappings, strings, and byte strings are supported. Protocol Buffers
provides serialization, not packet authentication.

Example payload; the existing demo's `(array, checksum)` tuple also still works:

```python
import numpy as np

data_queue.put({
    'sensor': 'A',
    'samples': np.arange(100, dtype=np.int32),
    'valid': True,
})
```

`NumericArray` contains `dtype`, `shape`, and `data`. Supported dtype names are
`bool`, `int8`, `int16`, `int32`, `int64`, `uint8`, `uint16`, `uint32`, `uint64`,
`float32`, `float64`, `complex64`, and `complex128`. Elements are contiguous in C (row-major) order, always
little-endian, regardless of sender machine byte order. Booleans use one byte
per element, 0 or 1. Complex elements use interleaved real then imaginary
components: `complex64` uses two little-endian IEEE 754 float32 components
(8 bytes per element); `complex128` uses two float64 components (16 bytes).
This supports GSCV IQ arrays without discarding imaginary values. Noncontiguous
and big-endian sender arrays are normalized to this same wire layout. Arrays may have up to 32 dimensions; dimensions must fit
0 through 2^31-1. A zero-dimensional array has one element. The product of the
shape times the element size must equal the data byte count. Object, string,
and structured dtypes are unsupported. The receiver validates metadata
before constructing a writable NumPy array; other languages can use native arrays.

The serialized body must fit 65,502 bytes (65,507-byte IPv4 UDP limit minus the
header). This is a protocol ceiling, not a guarantee against IP fragmentation.
Oversized or unsupported outgoing values are logged and dropped; malformed
incoming Protobuf data is logged and discarded without stopping the client.
Ordinary values do not require NumPy; a receiver without NumPy discards array
payloads with a logged error. No received data is passed to pickle.

### Using the schema from another language

Generate bindings from the same schema using your language's Protobuf tooling.
For example, C++:

```bash
mkdir -p generated
protoc --proto_path=src --cpp_out=generated src/netucs_payload.proto
```

For a received DATA_RESPONSE, validate version/type/length in the netucs header,
then parse bytes from offset 5 as `netucs.Value`. Inspect its `kind` oneof, recurse
into `Sequence` and `Mapping`, and interpret `NumericArray` using the rules above.
For example, string `"hello"` has Protobuf body hex `32 05 68 65 6c 6c 6f`; a full
response with sequence 0 is `03 00 02 00 00 32 05 68 65 6c 6c 6f`.
Clients must also implement the existing DATA_QUERY/ACKNOWLEDGE exchange; these
control messages remain fixed binary structures, not Protobuf messages.

Python bindings are in `src/netucs_payload_pb2.py`. To regenerate them, use a
compatible Protobuf compiler (for example protoc 3.21):

```bash
protoc --proto_path=src --python_out=src src/netucs_payload.proto
```

A newer compiler may require increasing the declared Python runtime dependency;
check generated-code/runtime compatibility before committing regenerated files.
Never reuse Protobuf field numbers. Increment the netucs protocol version for
packet-format or handshake changes, independently of `VERSION` and Git tags.
Run the full suite with `python3 -m unittest discover -s tests -v` after installing
the package dependencies (and NumPy for array tests).

### Exponential Backoff with Noise

When a client fails to receive an acknowledgment within `acknowledge_timeout`, it applies exponential backoff before the next request attempt. This prevents overwhelming the server during network issues or server unavailability.

**Backoff Formula:**
```
base_delay = min_period × (time_constant ^ retry_count)
noise = Gaussian(μ=0, σ=variance × base_delay)
delay = max(min_period, min(max_period, base_delay + noise))
```

**Parameters:**
- `backoff_min_period`: Minimum delay between retries (seconds)
- `backoff_max_period`: Maximum delay between retries (seconds)  
- `backoff_time_constant`: Exponential growth factor (e.g., 2.0 = double each retry)
- `backoff_variance`: Gaussian noise amplitude as fraction of base delay

**Example:**
With `min_period=1.0`, `time_constant=2.0`:
- Retry 0: ~1.0 second
- Retry 1: ~2.0 seconds + noise
- Retry 2: ~4.0 seconds + noise
- Retry 3: ~8.0 seconds + noise
- etc., capped at `max_repeat`

**Backoff Reset:**
The retry counter resets to 0 upon successful acknowledgment, so recovery is immediate when the server responds.

### Communication Flow

```
Client                          Server
  |                               |
  |------- DATA_QUERY ------>     |
  |                               |
  |  <---- ACKNOWLEDGE --------   |
  |                               |
  |  <---- DATA_RESPONSE -------  |
  |                               |
  |------- DATA_QUERY ------>     |
  |       (periodic)              |
```

### Client Lifecycle

1. **Registration**: First DATA_QUERY from new client triggers server-side registration
2. **Active**: Client receives periodic DATA_RESPONSE while registered
3. **Expiration**: If no request received within `client_lifetime`, client is removed
4. **Guard Time**: `client_lifetime_guard` provides buffer before next request deadline

### Sequence Numbering

- Both client and server maintain sequence numbers (16-bit, wraps at 32767)
- Packets out of order are accepted; sequencing is for ordering, not reliability
- Useful for detecting duplicate or reordered packets in analysis

## Configuration Examples

### Config Files

```python
import asyncio as ai
from netucs.network_client import NetworkClient
from netucs.network_server import NetworkServer
from netucs.network_client_config_example import CLIENT_CONFIG
from netucs.network_server_config_example import SERVER_CONFIG

data_in = ai.Queue()
data_out = ai.Queue()

server = NetworkServer(data_queue=data_in, **SERVER_CONFIG)
client = NetworkClient(data_queue=data_out, **CLIENT_CONFIG)
```

### High-Frequency Real-Time System

```python
# Server: Short timeout for responsive client cleanup
server = ns.NetworkServer(
    address='192.168.1.100',
    port=5000,
    client_lifetime=5,  # 5 second lifetime
    data_queue=data_in
)

# Client: Shorter request interval
client = nc.NetworkClient(
    server_address='192.168.1.100',
    server_port=5000,
    client_lifetime=4,  # request every 4 seconds
    client_lifetime_guard=0.5,
    acknowledge_timeout=2,  # quick timeout
    data_queue=data_out
)
```

### Low-Bandwidth Periodic System

```python
# Server: Long timeout for stable connections
server = ns.NetworkServer(
    address='192.168.1.100',
    port=5000,
    client_lifetime=300,  # 5 minute lifetime
    data_queue=data_in
)

# Client: Longer request interval with conservative backoff
client = nc.NetworkClient(
    server_address='192.168.1.100',
    server_port=5000,
    client_lifetime=240,  # request every 4 minutes
    client_lifetime_guard=30,  # 30 second guard
    acknowledge_timeout=10,
    data_queue=data_out,
    backoff_min_period=5.0,  # start at 5 seconds
    backoff_max_period=300.0,  # max 5 minutes
    backoff_time_constant=1.5,  # conservative growth
    backoff_variance=0.2  # 20% noise
)
```

### Unreliable Network (High Backoff)

```python
# Client for unreliable networks with aggressive backoff strategy
client = nc.NetworkClient(
    server_address='remote.network.example.com',
    server_port=5000,
    client_lifetime=30,
    client_lifetime_guard=5,
    acknowledge_timeout=10,
    data_queue=data_out,
    backoff_min_period=2.0,  # start at 2 seconds
    backoff_max_period=120.0,  # max 2 minutes
    backoff_time_constant=2.0,  # exponential growth
    backoff_variance=0.3  # 30% noise for jitter
)
```

## Logging

### Enable Detailed Logging

```python
import logging

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Server will log to 'netucs.network_server'
# Client will log to 'netucs.network_client'
logging.getLogger('netucs').setLevel(logging.DEBUG)
```

All netucs runtime log messages and demo output start with `netucs: `.
The prefix is part of the message, independent of the application logging formatter.

### Log Levels

- **DEBUG**: Detailed packet information, timing details
- **INFO**: Client registration/removal, data send events
- **WARNING**: Timeouts, failed operations
- **ERROR**: Communication failures, data serialization errors
- **CRITICAL**: Impossible states, fatal errors

## Error Handling

Both client and server include try-except blocks to:
- Log exceptions with full tracebacks
- Preserve state during recoverable errors

Note: runtime network errors and transport close events do not
auto-terminate the process. Shutdown is command-driven through
explicit `terminate()` calls.

```python
try:
    server.main()
except KeyboardInterrupt:
    print("Server stopped by user")
except Exception as e:
    print(f"Server error: {e}")
```

## Troubleshooting

### Client Not Receiving Data

1. **Check server is running**: Verify server.main() is executing
2. **Verify address/port**: Ensure client uses correct server address and port
3. **Check firewall**: UDP port must be open on server machine
4. **Review logs**: Set log level to DEBUG and check messages
5. **Timeout issue**: Increase `acknowledge_timeout` if network is slow

### Data Queue Empty

1. **Check data_queue.put()**: Ensure data is being added to server queue
2. **Verify client lifetime**: Increase `client_lifetime` on server
3. **Check acknowledgment**: Verify client receives acknowledgments (check logs)

### High CPU Usage

1. **Increase sleep intervals**: Modify await sleep durations in sender/listener
2. **Reduce log verbosity**: Use logging.WARNING or higher
3. **Check queue depth**: Limit producer queue size

## License

GNU General Public License v3 (GPLv3)

Copyright (c) 2023-2026 Fabrizio Pollastri

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

See the [LICENSE](LICENSE) file for details.

## Author

Fabrizio Pollastri <mxgbot@gmail.com>
Torino, Italy

### Release version

`VERSION` is the single source for the Python and Debian upstream version.
Update and commit it before a release, then tag that commit with `v` followed
by its contents. The Debian package adds its packaging revision (for example,
upstream `0.6.0` becomes Debian `0.6.0-1`). The protocol version is independent.

### Creating a release tag

1. Fetch remote tags with `git fetch --tags` so the local release history is current.
2. Increase `VERSION` above all existing stable release tags and commit all changes.
3. Run `python3 release.py --check` to validate without tagging.
4. Run `python3 release.py` to create an annotated local tag, for example `v0.6.1`.
5. Push the commit and tag when ready.

The script compares numeric `MAJOR.MINOR.PATCH` versions, accepts existing tags
with or without `v`, and refuses dirty working trees, duplicate releases, and
version decreases. Unrelated tags are ignored. New tags always use `v`.
It does not fetch, commit, or push automatically; checks cover local tags only.

For release CI, fetch the complete tag history, check out the tagged commit, and
run `python3 release.py --check-tag "$RELEASE_TAG"` before building or publishing.
Set `RELEASE_TAG` from your CI provider's release-tag event. This validates that
the tag matches committed `VERSION`, points to HEAD, and exceeds the other
stable release tags. It is intended for the current release, not rebuilding older
releases after newer ones have been tagged. Enforce this check in CI and protect
release tags against deletion or replacement to prevent bypassing local checks.

### Debian development build counter

Run `./build_deb.sh` as usual. Development builds use revisions such as
`0.6.0-1+build1`, `0.6.0-1+build2`, and so on. A clean checkout whose HEAD
has tag `v0.6.0` (or legacy `0.6.0`) matching `VERSION` builds `0.6.0-1`.
Dirty tagged checkouts are development builds too.

The counter is stored locally in `.deb-build-counter`, excluded from Git, and
advances only after a successful development build. Changing `VERSION` resets
the next development build to 1. Release builds leave the counter unchanged.
It is local to this working copy; fresh copies start at 1. Run one build at a time.

Keep the last released `VERSION` during development and increase it when cutting
the next release. A development revision sorts after its same-version release;
the next higher upstream release sorts after these development builds. Python
package versions continue to use `VERSION` without the Debian build counter.
