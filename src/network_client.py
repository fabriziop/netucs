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
import errno
import logging
import pickle as pk
import struct as st
import time as tm
import random as rd

from . import network_common as nc

lg = logging.getLogger(__name__)


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
        self.terminate_requested = False
        self.last_request_time = 0
        self.reconnect_event = None
        self.packet_header_size = st.calcsize(nc.HEADER_FMT)

        # Exponential backoff parameters
        self.backoff_min_period = backoff_min_period
        self.backoff_max_period = backoff_max_period
        self.backoff_time_constant = backoff_time_constant
        self.backoff_variance = backoff_variance
        self.backoff_retry_count = 0
        self.listener_backoff_retry_count = 0

    def terminate(self):
        self.terminate_requested = True
        # terminate_event is created inside run(); terminate may be requested
        # earlier when startup fails in another thread.
        if self.terminate_event is None:
            lg.debug("terminate requested before network client startup")
            return
        try:
            if self.loop is not None and self.loop.is_running():
                self.loop.call_soon_threadsafe(self.terminate_event.set)
            else:
                self.terminate_event.set()
        except RuntimeError:
            # Fallback for race windows while event loop is shutting down.
            self.terminate_event.set()

    def _calculate_backoff_delay(self, retry_count):
        """Calculate exponential backoff with noise.

        Formula: delay = min(max_period, min_period * (time_constant ^ retry_count) + noise)
        where noise is gaussian with variance parameter.
        """
        # Calculate exponential base delay
        base_delay = self.backoff_min_period * (self.backoff_time_constant ** retry_count)

        # Add gaussian noise with standard deviation = backoff_variance * base_delay
        noise = rd.gauss(0, self.backoff_variance * base_delay)

        # Calculate final delay, bounded by min and max
        delay = base_delay + noise
        delay = max(self.backoff_min_period, min(self.backoff_max_period, delay))

        return delay

    def _is_endpoint_create_retryable(self, exc):
        """True when UDP endpoint create failure is transient."""
        return isinstance(exc, OSError) and exc.errno in nc._NETWORK_ERRORS


    def datagram_received(self, data, addr):
        super().datagram_received(data, addr)

        # process data response
        if self.receive_packet_type == nc.PacketTypeCode["DATA_RESPONSE"].value:

            # skip packet header, add rx timestamp, deserialize data and put
            # it on output queue.
            self.data_queue.put((tm.time(), pk.loads(data[self.packet_header_size :])))
            lg.debug("received time marker from server")

        # process marker ackknowledge
        elif self.receive_packet_type == nc.PacketTypeCode["ACKNOWLEDGE"].value:

            # stop acknowledge timeout
            self.acknowledge_received.set()

    def error_received(self, exc):
        if isinstance(exc, OSError) and exc.errno in nc._NETWORK_ERRORS:
            lg.warning("UDP network error (%s) — will recreate socket", exc)
            if self.reconnect_event is not None:
                self.reconnect_event.set()
        else:
            lg.debug("UDP socket error: %s", exc)

    async def listener(self):
        """Create (and recreate after network outages) the UDP datagram endpoint."""
        while not self.terminate_event.is_set():

            # (re)create the UDP datagram endpoint
            try:
                self.transport, self.protocol = \
                    await self.loop.create_datagram_endpoint(
                        lambda: self,
                        remote_addr=(self.server_address, self.server_port),
                    )
            except OSError as exc:
                if not self._is_endpoint_create_retryable(exc):
                    lg.error("could not create UDP endpoint: %s", exc)
                    self.terminate()
                    raise
                delay = self._calculate_backoff_delay(
                    self.listener_backoff_retry_count
                )
                lg.warning(
                    "could not create UDP endpoint: %s — retrying in %.2f s"
                    " (retry count: %d)",
                    exc,
                    delay,
                    self.listener_backoff_retry_count,
                )
                self.listener_backoff_retry_count += 1
                try:
                    await ai.wait_for(
                        self.terminate_event.wait(), timeout=delay
                    )
                except ai.TimeoutError:
                    pass
                continue
            except Exception:
                lg.exception("unexpected error creating UDP endpoint")
                self.terminate()
                raise

            lg.debug("UDP endpoint ready")
            self.reconnect_event.clear()
            self.listener_backoff_retry_count = 0

            # Wait until termination or a socket error signals reconnect is needed
            terminate_task = ai.create_task(self.terminate_event.wait())
            reconnect_task = ai.create_task(self.reconnect_event.wait())
            done, pending = await ai.wait(
                {terminate_task, reconnect_task},
                return_when=ai.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
                try:
                    await task
                except ai.CancelledError:
                    pass

            # Always close the broken/used transport before looping or exiting
            try:
                self.transport.close()
            except Exception:
                pass
            self.transport = None

            if self.terminate_event.is_set():
                break

            # reconnect_event fired: backoff, then recreate socket
            delay = self._calculate_backoff_delay(
                self.listener_backoff_retry_count
            )
            lg.info(
                "network error detected — recreating UDP socket in %.2f s"
                " (retry count: %d)",
                delay,
                self.listener_backoff_retry_count,
            )
            self.listener_backoff_retry_count += 1
            self.reconnect_event.clear()
            try:
                await ai.wait_for(
                    self.terminate_event.wait(), timeout=delay
                )
            except ai.TimeoutError:
                pass

    async def sender(self):

        # wait for datagram endpoint to be established
        await ai.sleep(0.2)

        # loop until termination required
        loop_iteration = 0
        while not self.terminate_event.is_set():

            loop_iteration += 1
            lg.debug("sender loop iteration %d (backoff_retry_count=%d)", 
                          loop_iteration, self.backoff_retry_count)

            # wait for time to send marker request to server
            now = tm.time()
            delay = (
                self.client_lifetime
                - self.client_lifetime_guard
                + self.last_request_time
                - now
            )
            if delay > 0:
                lg.debug("waiting %.3f seconds before next request", delay)
                for awaitable in ai.as_completed(
                    [ai.sleep(delay), self.terminate_event.wait()]
                ):
                    await awaitable
                    break
                if self.terminate_event.is_set():
                    break

            # send data request
            lg.debug("sending data request (seq_num=%d)", self.send_seq_num)
            if self.transport is None:
                lg.debug("transport not ready (reconnecting), skipping send")
                self.last_request_time = tm.time()
                continue
            try:
                self.transport.sendto(
                    nc.data_query_packet.pack(
                        nc.PacketTypeCode.DATA_QUERY.value, self.send_seq_num, 1
                    ),
                    (self.server_address, self.server_port),
                )
            except (AttributeError, RuntimeError, OSError) as exc:
                if self.terminate_event.is_set():
                    lg.debug("sender send aborted during shutdown: %s", exc)
                    break
                lg.warning("send request failed (%s), scheduling reconnect", exc)
                if self.reconnect_event is not None:
                    self.reconnect_event.set()
                self.last_request_time = tm.time()
                continue
            self.last_request_time = tm.time()
            self.send_seq_num += 1
            self.send_seq_num &= 0x7FFF

            # wait for acknowledge with timeout
            try:
                async with ai.timeout(self.acknowledge_timeout):
                    await self.acknowledge_received.wait()
                    self.acknowledge_received.clear()
                    lg.info("received marker request acknowledge")
                    # Reset backoff on successful acknowledgment
                    self.backoff_retry_count = 0
            # if timeout expired, apply exponential backoff
            except ai.TimeoutError:
                lg.warning("marker request acknowledge timeout (retry count: %d)", self.backoff_retry_count)

                # Check if already terminating
                if self.terminate_event.is_set():
                    lg.warning("terminate_event already set before backoff, exiting sender loop")
                    break

                # Ensure the ack event does not stay set after a timeout.
                self.acknowledge_received.clear()

                # Calculate and apply exponential backoff with noise
                backoff_delay = self._calculate_backoff_delay(
                    self.backoff_retry_count
                )
                lg.info("applying exponential backoff: %.3f seconds (retry count: %d)",
                             backoff_delay, self.backoff_retry_count)

                # Increment retry counter before backoff wait
                self.backoff_retry_count += 1

                # Wait for backoff duration, but allow clean termination.
                lg.debug("starting backoff wait of %.3f seconds", backoff_delay)

                # Use asyncio.wait_for to combine sleep and termination check
                backoff_task = ai.create_task(ai.sleep(backoff_delay))
                terminate_task = ai.create_task(self.terminate_event.wait())

                done, pending = await ai.wait(
                    {backoff_task, terminate_task},
                    return_when=ai.FIRST_COMPLETED
                )

                # Cancel pending task
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except ai.CancelledError:
                        pass

                # Check which completed first
                if terminate_task in done:
                    lg.debug("termination requested during backoff")
                    break
                else:
                    lg.debug("backoff wait completed, will retry immediately (new retry_count=%d)",
                                  self.backoff_retry_count)

                # Send immediately after backoff (skip the remaining lifetime delay).
                self.last_request_time = tm.time() - (
                    self.client_lifetime - self.client_lifetime_guard
                )

    async def run(self):
        try:
            async with ai.TaskGroup() as tg:
                self.loop = ai.get_running_loop()
                self.terminate_event = ai.Event()
                self.acknowledge_received = ai.Event()
                self.reconnect_event = ai.Event()
                if self.terminate_requested:
                    self.terminate_event.set()
                self.task_listener = tg.create_task(self.listener())
                self.task_sender = tg.create_task(self.sender())
        except ai.CancelledError:
            lg.debug("Client run cancelled.")
        except Exception:
            lg.exception("")

    def shutdown(self):
        """Gracefully shutdown the client."""
        self.terminate()

    def main(self):
        try:
            with ai.Runner() as runner:
                runner.run(self.run())
        except:
            lg.exception("")

#### END
