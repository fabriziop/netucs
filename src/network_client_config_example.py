#!/usr/bin/env python3
# .+
# .context    : generic data UDP sending from server to clients
# .title      : client network parameters example
# .kind       : python script
# .author     : Fabrizio Pollastri <mxgbot@gmail.com>
# .site       : Torino - Italy
# .creation   : 24-Feb-2026
# .copyright  : (c) 2026 Fabrizio Pollastri
# .license    : all right reserved
# .description
# Example usage:
#   import asyncio as ai
#   from netucs.network_client import NetworkClient
#   from netucs.network_client_config_example import CLIENT_CONFIG
#   data_queue = ai.Queue()
#   client = NetworkClient(data_queue=data_queue, **CLIENT_CONFIG)
# .-

from . import network_common as nc

# Example configuration for NetworkClient
CLIENT_CONFIG = {
    "server_address": "127.0.0.1",
    "server_port": 12345,
    "client_lifetime": 30.0,
    "client_lifetime_guard": 5.0,
    "acknowledge_timeout": 5.0,
    # "data_queue": <asyncio.Queue or queue.Queue>,
    "backoff_min_period": nc.BACKOFF_MIN_PERIOD,
    "backoff_max_period": nc.BACKOFF_MAX_PERIOD,
    "backoff_time_constant": nc.BACKOFF_TIME_CONSTANT,
    "backoff_variance": nc.BACKOFF_VARIANCE,
}
