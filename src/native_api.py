"""Compatibility-facing Python API backed by the C++ network engine.

Protobuf value conversion remains in network_serialization for now.
"""
import logging
import queue
import threading
try:
    from . import _netucs_native as native
except ImportError as exc:
    raise ImportError(
        "netucs C++ extension '_netucs_native' could not be loaded. "
        "The netucs package must be built for this Python version and CPU "
        "architecture; a Python-only Debian package is not sufficient. "
        "Rebuild with ./build_deb.sh (requires cmake and pybind11-dev) "
        "or install a correctly built wheel. Original error: " + str(exc)
    ) from exc

# Forward native messages to the existing Python logging hierarchy.
# Logger names match the pre-migration modules; the application controls levels.
def _native_log(level, logger_name, message):
    logging.getLogger(logger_name).log(level, message)

native.set_log_callback(_native_log)

class NetworkClient:
    def __init__(self, server_address, server_port, client_lifetime,
                 client_lifetime_guard, acknowledge_timeout, data_queue,
                 backoff_min_period=1.0, backoff_max_period=20.0,
                 backoff_time_constant=2.0, backoff_variance=0.1):
        config = native.ClientConfig()
        config.server_address = server_address
        config.server_port = server_port
        config.client_lifetime = client_lifetime
        config.client_lifetime_guard = client_lifetime_guard
        config.acknowledge_timeout = acknowledge_timeout
        b = native.Backoff()
        b.min_period, b.max_period = backoff_min_period, backoff_max_period
        b.time_constant, b.variance = backoff_time_constant, backoff_variance
        config.backoff = b
        self.data_queue = data_queue
        self.terminate_requested = False
        def receive(t, payload):
            try:
                data_queue.put((t, payload))
            except ValueError:
                pass
        self._native = native.NativeClient(config, receive)
    def start(self):
        if not self.terminate_requested:
            self._native.start()
    def main(self):
        if not self.terminate_requested:
            self._native.main()
    def join(self): self._native.join()
    def terminate(self):
        self.terminate_requested = True
        self._native.terminate()
    shutdown = terminate
    @property
    def running(self): return self._native.running

class NetworkServer:
    def __init__(self, address, port, client_lifetime, data_queue,
                 backoff_min_period=1.0, backoff_max_period=20.0,
                 backoff_time_constant=2.0, backoff_variance=0.1,
                 fatal_error_callback=None, stopped_callback=None):
        config = native.ServerConfig()
        config.address, config.port = address, port
        config.client_lifetime = client_lifetime
        b = native.Backoff()
        b.min_period, b.max_period = backoff_min_period, backoff_max_period
        b.time_constant, b.variance = backoff_time_constant, backoff_variance
        config.backoff = b
        self._native = native.NativeServer(config)
        self.data_queue = data_queue
        self._stop = threading.Event()
        self._worker = None
        self._stopped_callback = stopped_callback
    def _pump(self):
        while not self._stop.is_set():
            try: item = self.data_queue.get(timeout=0.1)
            except queue.Empty: continue
            try: self._native.publish_value(item)
            except (ValueError, TypeError, OverflowError, RecursionError): pass
    def start(self):
        self._stop.clear()
        self._native.start()
        self._worker = threading.Thread(target=self._pump, daemon=True)
        self._worker.start()
    def main(self):
        self.start()
        self.join()
    def join(self):
        self._native.join()
        self._stop.set()
        if self._worker and self._worker is not threading.current_thread(): self._worker.join()
        if self._stopped_callback: self._stopped_callback()
    def terminate(self):
        self._stop.set()
        self._native.terminate()
    shutdown = terminate
    @property
    def running(self): return self._native.running
