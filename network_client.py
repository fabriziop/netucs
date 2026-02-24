# .+
# .context    : generic data UDP sending from server to clients
# .title      : client network data receiver
# .kind       : python module
# .author     : Fabrizio Pollastri <mxgbot@gmail.com>
# .site       : Torino - Italy
# .creation   : 11-Oct-2023
# .copyright  : (c) 2023 Fabrizio Pollastri
# .license    : all right reserved
# .-

import asyncio as ai
import logging as log
import pickle as pk
import struct as st
import time as tm
import random as rd

from . import network_common as nc


class NetworkClient(nc.Protocol):
    """Generic Signal Common View Protocol client network operations."""

    def __init__(
        self,
        server_address,
        server_port,
        client_lifetime,
        client_lifetime_guard,
        acknowledge_timeout,
        data_queue,
        backoff_min_period=nc.BACKOFF_MIN_PERIOD,
        backoff_max_period=nc.BACKOFF_MAX_PERIOD,
        backoff_time_constant=nc.BACKOFF_TIME_CONSTANT,
        backoff_variance=nc.BACKOFF_VARIANCE,
    ):

        super().__init__()
        self.server_address = server_address
        self.server_port = server_port
        self.transport = None
        self.protocol = None
        self.client_lifetime = client_lifetime
        self.client_lifetime_guard = client_lifetime_guard
        self.data_queue = data_queue
        self.loop = None
        self.terminate_event = None
        self.acknowledge_timeout = acknowledge_timeout
        self.acknowledge_received = None
        self.task_listener = None
        self.task_sender = None
        self.last_request_time = 0
        self.packet_header_size = st.calcsize(nc.HEADER_FMT)
        self.log = log.getLogger(__name__)
        
        # Exponential backoff parameters
        self.backoff_min_period = backoff_min_period
        self.backoff_max_period = backoff_max_period
        self.backoff_time_constant = backoff_time_constant
        self.backoff_variance = backoff_variance
        self.backoff_retry_count = 0

    def log_level(self, alog_level):

        self.log.setLevel(alog_level)

    def terminate(self):

        self.terminate_event.set()

    def _calculate_backoff_delay(self):
        """Calculate exponential backoff with noise.
        
        Formula: delay = min(max_period, min_period * (time_constant ^ retry_count) + noise)
        where noise is gaussian with variance parameter.
        """
        # Calculate exponential base delay
        base_delay = self.backoff_min_period * (self.backoff_time_constant ** self.backoff_retry_count)
        
        # Add gaussian noise with standard deviation = backoff_variance * base_delay
        noise = rd.gauss(0, self.backoff_variance * base_delay)
        
        # Calculate final delay, bounded by min and max
        delay = base_delay + noise
        delay = max(self.backoff_min_period, min(self.backoff_max_period, delay))
        
        return delay


    def datagram_received(self, data, addr):
        super().datagram_received(data, addr)

        # process data response
        if self.receive_packet_type == nc.PacketTypeCode["DATA_RESPONSE"].value:

            # skip packet header, deserialize data and put it on output queue
            self.data_queue.put(pk.loads(data[self.packet_header_size :]))
            log.debug("received time marker from server")

        # process marker ackknowledge
        elif self.receive_packet_type == nc.PacketTypeCode["ACKNOWLEDGE"].value:

            # stop acknowledge timeout
            self.acknowledge_received.set()

    async def listener(self):

        # create a UDP listener
        self.transport, self.protocol = await self.loop.create_datagram_endpoint(
            lambda: self, remote_addr=(self.server_address, self.server_port)
        )

        #self.transport._sock.settimeout(self.acknowledge_timeout)

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

            # wait for time to send marker request to server
            now = tm.time()
            delay = (
                self.client_lifetime
                - self.client_lifetime_guard
                + self.last_request_time
                - now
            )
            if delay > 0:
                for awaitable in ai.as_completed(
                    [ai.sleep(delay), self.terminate_event.wait()]
                ):
                    await awaitable
                    break
                if self.terminate_event.is_set():
                    break

            # send data request
            self.transport.sendto(
                nc.data_query_packet.pack(
                    nc.PacketTypeCode.DATA_QUERY.value, self.send_seq_num, 1
                ),
                (self.server_address, self.server_port),
            )
            self.last_request_time = tm.time()
            self.send_seq_num += 1
            self.send_seq_num &= 0x7FFF

            # wait for acknowledge with timeout
            try:
                async with ai.timeout(self.acknowledge_timeout):
                    await self.acknowledge_received.wait()
                    self.acknowledge_received.clear()
                    self.log.info("received marker request acknowledge")
                    # Reset backoff on successful acknowledgment
                    self.backoff_retry_count = 0
            # if timeout expired, apply exponential backoff
            except ai.TimeoutError:
                self.log.warning("marker request acknowledge timeout (retry count: %d)", self.backoff_retry_count)
                
                # Calculate and apply exponential backoff with noise
                backoff_delay = self._calculate_backoff_delay()
                self.log.info("applying exponential backoff: %.3f seconds (retry count: %d)", 
                             backoff_delay, self.backoff_retry_count)
                
                # Schedule next request with backoff delay
                self.last_request_time = tm.time() - (self.client_lifetime - self.client_lifetime_guard - backoff_delay)
                
                # Increment retry counter for next timeout
                self.backoff_retry_count += 1

    async def run(self):
        try:
            async with ai.TaskGroup() as tg:
                self.loop = ai.get_event_loop()
                self.terminate_event = ai.Event()
                self.acknowledge_received = ai.Event()
                self.task_listener = tg.create_task(self.listener())
                self.task_sender = tg.create_task(self.sender())
        except:
            self.log.exception("")
            self.terminate()

    def main(self):
        try:
            with ai.Runner() as runner:
                runner.run(self.run())
        except:
            self.log.exception("")
            self.terminate()


#### END
"""
TO BE PUT IN THE NETWORK CLIENT CALLER
            # unpack reseponse into a numpy complex array (the marker) and
            # a float (marker timestamp)
            marker = np.frombuffer(data,np.csingle,offset=12)
            timestamp, = marker_response_timestamp.unpack(data[0:12])

            lg.debug("received marker timestamp %lf @time %lf"
                % (timestamp,tm.time()))

        # if gscv_client is terminating, terminate also.
        if self.gscv_client.terminate.is_set():
            self.terminate.set()
"""
