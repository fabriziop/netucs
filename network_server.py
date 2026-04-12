# .+
# .context    : generic data UDP sending from server to clients
# .title      : server data sender for clients
# .kind       : python module
# .author     : Fabrizio Pollastri <mxgbot@gmail.com>
# .site       : Torino - Italy
# .creation   : 10-Oct-2023
# .copyright  : (c) 2023 Fabrizio Pollastri
# .license    : all right reserved
# .changes
#   FP20250711 full refactor to work with agnostic data
# .-

import asyncio as ai
import errno
import logging
import pickle as pk
import queue as qu
import socket as sk
import struct as st
import time as tm

from . import network_common as nc

lg = logging.getLogger(__name__)


class NetworkServer(nc.Protocol):
    """
    Server network data sending on client requests. Client requests have
    an expiration time.
    """

    def __init__(
        self,
        address,
        port,
        client_lifetime,
        data_queue,
        fatal_error_callback=None,
        stopped_callback=None,
    ):

        super().__init__()
        self.address = address
        self.port = port
        self.transport = None
        self.protocol = None
        self.client_lifetime = client_lifetime
        self.data_queue = data_queue
        self.loop = None
        self.terminate_event = None
        self.task_listener = None
        self.task_sender = None
        self.terminate_requested = False
        self.clients_to_add = ai.Queue()
        self.clients = {}
        self.packet_header_size = st.calcsize(nc.HEADER_FMT)
        self.log = lg
        self.fatal_error_callback = fatal_error_callback
        self.stopped_callback = stopped_callback

    def terminate(self):
        self.terminate_requested = True
        # terminate_event is created inside run(); terminate may be requested
        # earlier when startup fails in another thread.
        if self.terminate_event is None:
            lg.debug("terminate requested before network server startup")
            return
        self.terminate_event.set()

    def _notify_fatal_error(self, exc):
        """Request full application shutdown on unrecoverable network errors."""
        if self.fatal_error_callback is None:
            return

        try:
            self.fatal_error_callback(exc)
        except Exception:
            self.log.exception("fatal error callback failed")

    def _is_bind_address_error(self, exc):
        """True when UDP bind failed because the local address is not usable."""
        if not isinstance(exc, OSError):
            return False
        if exc.errno == errno.EADDRNOTAVAIL:
            return True
        return "Cannot assign requested address" in str(exc)

    def _notify_stopped(self):
        """Notify host app that the network server loop has exited."""
        if self.stopped_callback is None:
            return

        try:
            self.stopped_callback()
        except Exception:
            self.log.exception("network stopped callback failed")

    def datagram_received(self, data, addr):

        try:
            super().datagram_received(data, addr)

            # get packet header
            packet_type, receive_seq_num = nc.packet_header.unpack(data[0:4])

            # if it is a data query packet ...
            # not data query packets are silently discarded
            if packet_type == nc.PacketTypeCode["DATA_QUERY"].value:
                self.log.info("received data request from %s}", addr)

                # send acknowledge to client
                packet = nc.acknowledge_packet.pack(
                    nc.PacketTypeCode["ACKNOWLEDGE"].value,
                    self.send_seq_num,
                    receive_seq_num,
                )
                self.transport.sendto(packet, addr)
                self.send_seq_num += 1
                self.send_seq_num &= 0x7FFF
                self.log.info("sent data request acknowledge to %s",addr)

                # if client is not on the send list: queue its addition.
                now = tm.time()
                # update client expiration time
                expiration = now + self.client_lifetime
                if not addr in self.clients:
                    # get data send period
                    data_send_period, = nc.data_query_payload.unpack(data[4:8])
                    # queue new client to be added: operation managed by sender.
                    self.clients_to_add.put_nowait(
                        nc.Client(addr, data_send_period, now, expiration)
                    )
                # client already present: update expiration time
                else:
                    self.clients[addr].expiration = expiration
        except:
            self.log.exception("")

    async def listener(self):
        try:
            self.transport, self.protocol = await self.loop.create_datagram_endpoint(
                lambda: self,
                local_addr=(self.address, self.port),
                family=sk.AF_INET,
                proto=sk.IPPROTO_UDP,
            )
        except OSError as exc:
            self.log.error(
                "could not create UDP listener on %s:%s: %s",
                self.address,
                self.port,
                exc,
            )
            self.terminate()
            if self._is_bind_address_error(exc):
                self._notify_fatal_error(exc)
            return
        except Exception as exc:
            self.log.exception(
                "unexpected error creating UDP listener on %s:%s",
                self.address,
                self.port,
            )
            self.terminate()
            self._notify_fatal_error(exc)
            return

        # run until task termination signal
        try:
            await self.terminate_event.wait()
        except Exception:
            self.log.exception("")
        finally:
            if self.transport is not None:
                self.transport.close()
                self.transport = None

    async def sender(self):

        # wait for datagram endpoint to be established
        await ai.sleep(0.2)

        # loop until termination required
        while not self.terminate_event.is_set():

            # add client if any, to active clients.
            while not self.clients_to_add.empty():
                client = self.clients_to_add.get_nowait()
                self.clients[client.addr] = client
                self.log.info("added client %s to client list",client.addr)

            # Block on marker queue with timeout to periodically check termination.
            try:
                marker_data = await ai.to_thread(self.data_queue.get, True, 0.1)
            except qu.Empty:
                continue

            # Serialize marker for UDP payload.
            data = pk.dumps(marker_data)

            # check for max allowed size
            if len(data) > nc.MAX_UDP_SIZE - self.packet_header_size:
                self.log.error("data exceeding max udp packet size (%d), data discarded",nc.MAX_UDP_SIZE)
                continue

            # there is new data: send it to all active clients
            # print("new data")
            now = tm.time()
            self.log.debug("data send time %s UTC OS",now)

            for addr, client in list(self.clients.items()):

                # if client is expired, delete it
                if client.expiration <= now:
                    self.log.info("removing expired client %s",client.addr)
                    del self.clients[addr]
                    continue

                # if not time to send data, go to next client
                if not client.data_send <= now:
                    continue

                # send data to current client
                self.log.info("sending data to client %s",client.addr)
                data_to_send = bytearray(4)
                nc.data_response_packet.pack_into(
                    data_to_send,
                    0,
                    nc.PacketTypeCode["DATA_RESPONSE"].value,
                    self.send_seq_num,
                )
                data_to_send += data
                self.transport.sendto(data_to_send, addr)
                self.send_seq_num += 1
                self.send_seq_num &= 0x7FFF
                client.data_send = now + float(client.data_send_period) - 1.1

    async def run(self):
        try:
            async with ai.TaskGroup() as tg:
                self.loop = ai.get_event_loop()
                self.terminate_event = ai.Event()
                if self.terminate_requested:
                    self.terminate_event.set()
                self.task_listener = tg.create_task(self.listener())
                self.task_sender = tg.create_task(self.sender())
        except Exception:
            self.log.exception("")
        finally:
            self._notify_stopped()

    def main(self):
        try:
            ai.run(self.run())
        except Exception:
            self.log.exception("")

#### END
