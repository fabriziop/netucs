# Logging integration

Native C++ networking events are forwarded through the pybind11 callback to
Python `logging`, using `netucs.network_client` and `netucs.network_server`.
The application controls log levels and handlers; netucs does not call
`logging.basicConfig()` or print to stdout.

Example:

```python
import logging
logging.getLogger("netucs").setLevel(logging.DEBUG)
```

The C++ API can register `netucs::set_log_callback` directly. The callback
may run on Conductor or UDP worker threads and must be thread-safe.

Native errors previously swallowed by worker loops are now logged. Logging
is best-effort and must not interrupt the transport.
