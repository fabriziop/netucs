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
- **Serializable Data Support**: Uses pickle to serialize arbitrary Python objects for transmission
- **Configurable Timeouts**: Fine-grained control over client lifetime and request/response timing
- **Logging Integration**: Comprehensive logging at multiple levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Protocol Versioning**: Structured packet format with sequence numbers for ordering

## Installation

### From Source

1. Place the `netucs` package in your Python project directory or in your Python path:

```bash
# If in the main directory structure
from netucs import network_client as nc
from netucs import network_server as ns
```

2. Ensure dependencies are installed:

```bash
pip install python>=3.8  # asyncio is built-in
```

No external dependencies required - netucs uses only Python standard library modules.

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
server.log_level(logging.INFO)

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
client.log_level(logging.INFO)

# Run client (blocks until terminated)
client.main()

# Retrieve received data
while True:
    data = data_queue.get()
    print(f"Received: {data}")
```

### Client-Server Example

See `netucs/network_test.py` for a complete working example with producer/consumer patterns.

## Detailed API

### network_server.NetworkServer

UDP server that distributes data to registered clients on request.

#### Constructor Parameters

```python
NetworkServer(address, port, client_lifetime, data_queue)
```

- **address** (str): IP address to bind to (e.g., '0.0.0.0', '127.0.0.1')
- **port** (int): UDP port number to listen on
- **client_lifetime** (float): Time in seconds before a client is considered expired
- **data_queue** (queue.Queue): Queue from which data items are retrieved for distribution

#### Methods

**log_level(log_level)**
- Sets the logging level for the server
- Parameters:
  - `log_level`: logging level (logging.DEBUG, logging.INFO, etc.)

**main()**
- Starts the server (blocking call)
- Creates UDP listener and data sender coroutines
- Runs until interrupted or error occurs

**terminate()**
- Signals server termination (internal use)

**datagram_received(data, addr)**
- Callback for incoming UDP datagrams (internal use)
- Handles client registration and expiration

### network_client.NetworkClient

UDP client that requests data from the server at regular intervals.

#### Constructor Parameters

```python
NetworkClient(server_address, server_port, client_lifetime, 
              client_lifetime_guard, acknowledge_timeout, data_queue,
              backoff_min_repeat=1.0, backoff_max_repeat=60.0,
              backoff_time_constant=2.0, backoff_variance=0.1)
```

- **server_address** (str): Server IP address
- **server_port** (int): Server UDP port
- **client_lifetime** (float): Interval between data requests (seconds)
- **client_lifetime_guard** (float): Guard time before sending next request (seconds)
- **acknowledge_timeout** (float): Timeout waiting for server acknowledgment (seconds)
- **data_queue** (queue.Queue): Queue to place received data items
- **backoff_min_repeat** (float, optional): Minimum backoff delay in seconds (default: 1.0)
- **backoff_max_repeat** (float, optional): Maximum backoff delay in seconds (default: 60.0)
- **backoff_time_constant** (float, optional): Exponential backoff time constant (default: 2.0)
- **backoff_variance** (float, optional): Gaussian noise variance as fraction of base delay (default: 0.1)

#### Methods

**log_level(log_level)**
- Sets the logging level for the client
- Parameters:
  - `log_level`: logging level (logging.DEBUG, logging.INFO, etc.)

**main()**
- Starts the client (blocking call)
- Creates UDP listener and request sender coroutines
- Runs until interrupted or error occurs

**terminate()**
- Signals client termination (internal use)

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
| Header | type (int16), seq_num (int16) | 4 bytes |
| Data Query | type, seq_num, response_period (int32) | 8 bytes |
| Data Response | type, seq_num, [serialized data] | 4+ bytes |
| Acknowledge | type, seq_num, ack_seq_num (int16), padding | 8 bytes |

**Constants**
- `MAX_UDP_SIZE = 65507`: Maximum UDP datagram size

## Protocol Details

### Exponential Backoff with Noise

When a client fails to receive an acknowledgment within `acknowledge_timeout`, it applies exponential backoff before the next request attempt. This prevents overwhelming the server during network issues or server unavailability.

**Backoff Formula:**
```
base_delay = min_repeat × (time_constant ^ retry_count)
noise = Gaussian(μ=0, σ=variance × base_delay)
delay = max(min_repeat, min(max_repeat, base_delay + noise))
```

**Parameters:**
- `backoff_min_repeat`: Minimum delay between retries (seconds)
- `backoff_max_repeat`: Maximum delay between retries (seconds)  
- `backoff_time_constant`: Exponential growth factor (e.g., 2.0 = double each retry)
- `backoff_variance`: Gaussian noise amplitude as fraction of base delay

**Example:**
With `min_repeat=1.0`, `time_constant=2.0`:
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

### High-Frequency Real-Time System

```python
# Server: Short timeout for responsive client cleanup
server = ns.NetworkServer(
    address='0.0.0.0',
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
    address='0.0.0.0',
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
    backoff_min_repeat=5.0,  # start at 5 seconds
    backoff_max_repeat=300.0,  # max 5 minutes
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
    backoff_min_repeat=2.0,  # start at 2 seconds
    backoff_max_repeat=120.0,  # max 2 minutes
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
server.log_level(logging.DEBUG)
client.log_level(logging.DEBUG)
```

### Log Levels

- **DEBUG**: Detailed packet information, timing details
- **INFO**: Client registration/removal, data send events
- **WARNING**: Timeouts, failed operations
- **ERROR**: Communication failures, data serialization errors
- **CRITICAL**: Impossible states, fatal errors

## Error Handling

Both client and server include try-except blocks to:
- Log exceptions with full tracebacks
- Gracefully terminate on errors
- Preserve state during recoverable errors

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
INRIM - Istituto Nazionale di Ricerca Metrologica
Torino, Italy
