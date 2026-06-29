#!/usr/bin/env python3
# .+
# .context    : simple client from server network data receiving
# .title      : test sending and receiving data from server to client
# .kind       : python module
# .author     : Fabrizio Pollastri <mxgbot@gmail.com>
# .site       : Torino - Italy
# .creation   : 06-Jul-2025
# .copyright  : (c) 2025 Fabrizio Pollastri
# .license    : all right reserved
# .-

from . network_common import *
from . network_server import *
from . network_client import *

import concurrent.futures as cf
import logging
import numpy as np
import time as tm

lg = logging.getLogger(__name__)

# parameters
PRODUCER_QUEUE_DEPTH = 3
CONSUMER_QUEUE_DEPTH = 3
PRODUCER_CYCLES = 4
CONSUMER_CYCLES = 4
SERVER_ADDRESS = '127.0.0.1'
SERVER_PORT = 12345
CLIENT_LIFETIME = 30    # seconds
CLIENT_LIFETIME_GUARD = 5   # seconds
ACKNOWLEDGE_TIMEOUT = 5  # seconds

# logging level
logging.basicConfig(level=logging.INFO)

# make random generation reproducible
np.random.seed(1)

# create a queue with the specified sizes

## use following lines for ProcessPoolExecutor
#from multiprocessing import Manager
#producer_queue = Manager().Queue(PRODUCER_QUEUE_DEPTH)
#consumer_queue = Manager().Queue(CONSUMER_QUEUE_DEPTH)

## use following lines for ThreadPoolExecutor
import asyncio
import queue as qu
import threading

producer_queue = qu.Queue(PRODUCER_QUEUE_DEPTH)
consumer_queue = qu.Queue(CONSUMER_QUEUE_DEPTH)

# create a network server and a client to send data from server to client
server = NetworkServer(SERVER_ADDRESS, SERVER_PORT, CLIENT_LIFETIME, producer_queue)
client = NetworkClient(SERVER_ADDRESS, SERVER_PORT, CLIENT_LIFETIME,
                       CLIENT_LIFETIME_GUARD, ACKNOWLEDGE_TIMEOUT, consumer_queue)


# fill queue with one element: ramdom data and its summation
def producer(producer_queue):
    """
    Producer function that fills the queue with random data and checksum.
    """
    lg.info("Producer starting...")

    for i in range(PRODUCER_CYCLES):
        # an array of random data and its summation
        rdata = np.random.randint(0, 100, size=100, dtype=np.int32)
        # its summation
        rdata_sum = np.sum(rdata)

        # put the data and its summation in the producer queue
        # This will block if the queue is full, providing natural backpressure.
        print(f"Producer sent summation: {rdata_sum} (cycle {i+1})")
        producer_queue.put((rdata, rdata_sum))

        tm.sleep(1)  # simulate some delay in producing data
    lg.info("Producer finished.")


# verify the checksum of the current queue element to be read
def consumer(consumer_queue, test_finished_event):
    """
    Consumer function that reads data from the queue and verify the checksum.
    """
    lg.info("Consumer starting...")
    for i in range(CONSUMER_CYCLES):
        try:
            # get the current queue element to be read
            # The client wraps data as (timestamp, (rdata, rdata_sum))
            # Use a very long timeout to account for network latency and scheduling delays
            timestamp, (rdata, rdata_sum) = consumer_queue.get(timeout=5)
            print(f"Consumer received summation: {rdata_sum} (cycle {i+1})")

            # verify array summation
            if np.sum(rdata) != rdata_sum:
                print("Consumer, sum error.")
        except qu.Empty:
            print(f"Consumer timed out waiting for data on cycle {i+1}.")
            break

    lg.info("Consumer finished.")
    test_finished_event.set()


async def main():
    test_finished_event = threading.Event()

    # Start server
    server_task = asyncio.create_task(server.run())
    lg.info("Server started, waiting a moment for it to initialize...")
    await asyncio.sleep(0.5)

    # Start client
    client_task = asyncio.create_task(client.run())
    lg.info("Client started.")

    # Start producer and consumer in separate threads
    producer_thread = threading.Thread(
        target=producer, args=(producer_queue,), daemon=False)
    consumer_thread = threading.Thread(
        target=consumer, args=(consumer_queue, test_finished_event), daemon=False)

    producer_thread.start()
    lg.info("Producer thread started.")
    consumer_thread.start()
    lg.info("Consumer thread started.")

    # Wait for the test to complete (block until test_finished_event is set)
    lg.info("Main: waiting for test to finish...")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, test_finished_event.wait)
    lg.info("Main: test finished event received.")

    # Wait for producer thread to finish
    producer_thread.join(timeout=5)
    lg.info("Producer thread joined.")
    
    # Give server time to process all remaining items in the producer queue
    lg.info("Waiting for producer queue to drain...")
    max_wait = 15  # seconds
    start_time = tm.time()
    while not producer_queue.empty() and (tm.time() - start_time) < max_wait:
        await asyncio.sleep(0.2)
    
    if not producer_queue.empty():
        lg.warning(f"Producer queue still has {producer_queue.qsize()} items after timeout")
    else:
        lg.info("Producer queue drained successfully.")

    # Now safely shutdown
    lg.info("Shutting down...")
    client.shutdown()
    server.shutdown()

    consumer_thread.join(timeout=3)

    # Cancel asyncio tasks
    server_task.cancel()
    client_task.cancel()
    
    try:
        await server_task
    except asyncio.CancelledError:
        lg.info("Server task cancelled.")
    
    try:
        await client_task
    except asyncio.CancelledError:
        lg.info("Client task cancelled.")

    print("Test finished successfully.")


# execution threads
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Test interrupted by user.")


#### END
