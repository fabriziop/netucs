#!/usr/bin/env python3
# .+
# .context    : generic data UDP sending from server to clients
# .title      : common code to client and server
# .kind       : python script
# .author     : Fabrizio Pollastri <f.pollastri@inrim.it>
# .site       : Torino - Italy
# .creation   : 9-Oct-2023
# .copyright  : (c) 2023 Fabrizio Pollastri
# .license    : all right reserved
# .-

import asyncio as ai
from dataclasses import dataclass
import enum as en
import struct as st

## client/server protocol

MAX_UDP_SIZE = 65507  # https://en.wikipedia.org/wiki/User_Datagram_Protocol


# packet types
class PacketTypeCode(en.Enum):
    DATA_QUERY = 1
    DATA_RESPONSE = 2
    ACKNOWLEDGE = 99


# packet structures

# packet header: fields common to all packets.
# 1. packet type, 2 bytes
# 2. sequence number, 2 bytes
HEADER_FMT = "!hh"
packet_header = st.Struct(HEADER_FMT)

# data query
# 1. packet type, 2 bytes
# 2. sequence number, 2 bytes
# 3. response period, 4 bytes
data_query_packet = st.Struct("!hhl")

# data query: payload only (all non header).
# 1. response period, 4 bytes
data_query_payload = st.Struct("!l")

# data response: fixed size fields only (data trail fields can have
# programmable size).
# 1. packet type, 2 bytes
# 2. sequence number, 2 bytes
data_response_packet = st.Struct("!hh")

# acknowledge:
# 1. packet type, 2 bytes
# 2. sequence number, 2 bytes
# 3. sequence number of packet to by acknowledged, 2 bytes
# 4. padding to x4 alignment, 2 bytes
acknowledge_packet = st.Struct("!hhhxx")


# data client descriptor

@dataclass
class Client:
    """GSCV client data descriptor for clients management by server."""

    addr: str
    data_send_period: float
    data_send: int
    expiration: float



class Protocol(ai.DatagramProtocol):
    """Generic Signal Common View Protocol compatible with
    "create_datagram_endpoint" method of asyncio.
    """

    def __init__(self):
        self.transport = None
        self.send_seq_num = 0
        self.receive_seq_num = 0
        self.receive_packet_type = None
        self.data = None
        self.addr = None
        super().__init__()

    def terminate(self):
        raise NotImplementedError()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.data = data
        self.addr = addr

        # get packet header
        self.receive_packet_type, self.receive_seq_num = packet_header.unpack(data[0:4])

    # exc: OS error instance
    def error_received(self, exc):
        self.terminate()

    def connection_lost(self, exc):
        self.terminate()


#### END
