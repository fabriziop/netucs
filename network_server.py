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
import logging as log
import pickle as pk
import socket as sk
import struct as st
import time as tm

from . import network_common as nc


class NetworkServer(nc.Protocol):
    """
    Server network data sending on client requests. Client requests have
    an expiration time.
    """

    def __init__(self, address, port, client_lifetime, data_queue):

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
        self.clients_to_add = ai.Queue()
        self.clients = {}
        self.packet_header_size = st.calcsize(nc.HEADER_FMT)
        self.log = log.getLogger(__name__)

    def log_level(self, alog_level):

        self.log.setLevel(alog_level)

    def terminate(self):

        self.terminate_event.set()

    def datagram_received(self, data, addr):

        try:
            super().datagram_received(data, addr)

            # get packet header
            packet_type, receive_seq_num = nc.packet_header.unpack(data[0:4])

            # if it is a data query packet ...
            # not data query packets are silently discarded
            if packet_type == nc.PacketTypeCode["DATA_QUERY"].value:
                self.log.info("received data request from %s}",addr)

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
                    data_send_period = nc.data_query_payload.unpack(data[4:8])
                    # queue new client to be added: operation managed by sender.
                    self.clients_to_add.put_nowait(
                        nc.Client(addr, data_send_period, now, expiration)
                    )
                # client already present: update expiration time
                else:
                    self.clients[addr].expiration = expiration
        except:
            self.log.exception("")
            self.terminate()

    async def listener(self):

        # create a UDP listener
        self.transport, self.protocol = await self.loop.create_datagram_endpoint(
            lambda: self,
            local_addr=(self.address, self.port),
            family=sk.AF_INET,
            proto=sk.IPPROTO_UDP,
        )

        # run until task termination signal
        try:
            await self.terminate_event.wait()
        except:
            self.log.exception("")
        finally:
            self.transport.close()

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

            # if no data to send, wait a while releasing execution to
            # listener and other coroutines the restart cycle.
            if self.data_queue.empty():
                await ai.sleep(0.1)
                continue

            # there is data to send, get and serialize it
            data = pk.dumps(self.data_queue.get())

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

    async def run(self):
        try:
            async with ai.TaskGroup() as tg:
                self.loop = ai.get_event_loop()
                self.terminate_event = ai.Event()
                self.task_listener = tg.create_task(self.listener())
                self.task_sender = tg.create_task(self.sender())
        except:
            self.log.exception("")
            self.terminate()

    def main(self):
        try:
            ai.run(self.run())
        except:
            self.log.exception("")
            self.terminate()


#### END
