#!/usr/bin/env python3
# .+
# .context    : generic data UDP sending from server to clients
# .title      : common code to client and server
# .kind       : python script
# .author     : Fabrizio Pollastri <mxgbot@gmail.com>
# .site       : Torino - Italy
# .creation   : 9-Oct-2023
# .copyright  : (c) 2023 Fabrizio Pollastri
# .license    : all right reserved
# .-

import asyncio as ai
from dataclasses import dataclass
import enum as en
import errno
import logging
import struct as st

lg = logging.getLogger(__name__)

## client/server protocol

# Independent of the code/package release version. Increment only when the
# wire packet format or handshake changes; valid versions are 1..255.
PROTOCOL_VERSION = 3

MAX_UDP_SIZE = 65507  # https://en.wikipedia.org/wiki/User_Datagram_Protocol

# Exponential backoff default parameters
BACKOFF_MIN_PERIOD = 1.0  # Minimum backoff delay in seconds
BACKOFF_MAX_PERIOD = 20.0  # Maximum backoff delay in seconds
BACKOFF_TIME_CONSTANT = 2.0  # Exponential growth factor
BACKOFF_VARIANCE = 0.1  # Gaussian noise variance as fraction of base delay

# OS error numbers that indicate a transient network outage on a connected
# UDP socket.  When received, the socket must be recreated because Linux
# caches the ICMP error and returns it on every subsequent send, even after
# connectivity is restored.
_NETWORK_ERRORS = frozenset((
    errno.EHOSTUNREACH,   # 113 No route to host
    errno.ENETUNREACH,    # 101 Network is unreachable
    errno.ECONNREFUSED,   # 111 Connection refused (ICMP port unreachable)
    errno.EHOSTDOWN,      # 112 Host is down
    errno.ETIMEDOUT,      # 110 Connection timed out
    errno.ENETDOWN,       # 100 Network is down
))


# packet types
class PacketTypeCode(en.Enum):
    DATA_QUERY = 1
    DATA_RESPONSE = 2
    ACKNOWLEDGE = 99


# packet structures

# All packets start with: protocol version (unsigned byte), packet type
# (signed 16-bit), sequence number (signed 16-bit), in network byte order.
HEADER_FMT = "!Bhh"
packet_header = st.Struct(HEADER_FMT)

# Query payload: response period (signed 32-bit).
data_query_packet = st.Struct(HEADER_FMT + "l")
data_query_payload = st.Struct("!l")

# Response payload: serialized application data.
data_response_packet = st.Struct(HEADER_FMT)

# ACK payload: acknowledged sequence (signed 16-bit), two padding bytes.
acknowledge_packet = st.Struct(HEADER_FMT + "hxx")


# data client descriptor

@dataclass
class Client:
    """GSCV client data descriptor for clients management by server."""

    addr: str
    data_send_period: float
    data_send: float
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
        # Reject incompatible packets before interpreting their body or changing
        # receive state. Legacy unversioned packets are incompatible as well.
        if not data:
            return False
        if data[0] != PROTOCOL_VERSION:
            lg.warning("netucs: Ignoring UDP packet from %s: protocol version %d; expected %d",
                       addr, data[0], PROTOCOL_VERSION)
            return False
        if len(data) < packet_header.size:
            return False
        _, packet_type, sequence = packet_header.unpack_from(data)
        if packet_type == PacketTypeCode.DATA_QUERY.value:
            if len(data) != data_query_packet.size:
                return False
        elif packet_type == PacketTypeCode.ACKNOWLEDGE.value:
            if len(data) != acknowledge_packet.size:
                return False
        elif packet_type == PacketTypeCode.DATA_RESPONSE.value:
            if len(data) <= packet_header.size:
                return False
        else:
            return False

        self.data = data
        self.addr = addr
        self.receive_packet_type = packet_type
        self.receive_seq_num = sequence
        return True

    # exc: OS error instance
    def error_received(self, exc):
        # Log UDP errors but don't terminate - these are common when server is unreachable
        # The acknowledge timeout and backoff mechanism will handle retries
        lg.debug("netucs: UDP socket error (expected when server unreachable): %s", exc)

    def connection_lost(self, exc):
        # Never auto-terminate here: shutdown is controlled by application
        # via explicit terminate() command.
        if exc:
            lg.warning("netucs: Connection lost with error: %s", exc)
        else:
            lg.debug("netucs: Connection closed")


#### END
