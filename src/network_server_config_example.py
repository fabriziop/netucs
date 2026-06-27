#!/usr/bin/env python3
# .+
# .context    : generic data UDP sending from server to clients
# .title      : server network parameters example
# .kind       : python script
# .author     : Fabrizio Pollastri <mxgbot@gmail.com>
# .site       : Torino - Italy
# .creation   : 24-Feb-2026
# .copyright  : (c) 2026 Fabrizio Pollastri
# .license    : all right reserved
# .description
# Example usage:
#   import asyncio as ai
#   from netucs.network_server import NetworkServer
#   from netucs.network_server_config_example import SERVER_CONFIG
#   data_queue = ai.Queue()
#   server = NetworkServer(data_queue=data_queue, **SERVER_CONFIG)
# .-

# Example configuration for NetworkServer
SERVER_CONFIG = {
    "address": "127.0.0.1",
    "port": 12345,
    "client_lifetime": 30.0,
    # "data_queue": <asyncio.Queue or queue.Queue>,
}
