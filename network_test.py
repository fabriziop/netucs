#!/usr/bin/env python3
# .+
# .context    : simple client from server network data receiving
# .title      : test sending and receiving data from server to client
# .kind       : python module
# .author     : Fabrizio Pollastri <f.pollastri@inrim.it>
# .site       : Torino - Italy
# .creation   : 06-Jul-2025
# .copyright  : (c) 2025 Fabrizio Pollastri
# .license    : all right reserved
# .-

from .network_common import *
from .network_server import *
from .network_client import *

import concurrent.futures as cf
import logging as lg
import numpy as np
import time as tm

# parameters
PRODUCER_QUEUE_DEPTH = 3
CONSUMER_QUEUE_DEPTH = 3
PRODUCER_CYCLES = 6
CONSUMER_CYCLES = 6
SERVER_ADDRESS = '127.0.0.1'
SERVER_PORT = 12345
CLIENT_LIFETIME = 30    # seconds
CLIENT_LIFETIME_GUARD = 5   # seconds
ACKNOWLEDGE_TIMEOUT = 5  # seconds

# logging level
lg.basicConfig(level=lg.INFO)

# make random generation reproducible
np.random.seed(1)

# create a queue with the specified sizes

## use following lines for ProcessPoolExecutor
#from multiprocessing import Manager
#producer_queue = Manager().Queue(PRODUCER_QUEUE_DEPTH)
#consumer_queue = Manager().Queue(CONSUMER_QUEUE_DEPTH)

## use following lines for ThreadPoolExecutor
import queue as qu
producer_queue = qu.Queue(PRODUCER_QUEUE_DEPTH)
consumer_queue = qu.Queue(CONSUMER_QUEUE_DEPTH)

# create a network server and a client to send data from server to client
server = NetworkServer(SERVER_ADDRESS,SERVER_PORT,CLIENT_LIFETIME,producer_queue)
server.log_level(lg.WARNING)
client = NetworkClient(SERVER_ADDRESS,SERVER_PORT,CLIENT_LIFETIME,
             CLIENT_LIFETIME_GUARD,ACKNOWLEDGE_TIMEOUT,consumer_queue)
client.log_level(lg.WARNING)

# fill queue with one element: ramdom data and its summation
def producer(producer_queue):
    """
    Producer function that fills the queue with random data and checksum.
    """

    for i in range(PRODUCER_CYCLES):

        # an array of random data and its summation
        rdata = np.random.randint(0,100,size=100,dtype=np.int32)
        # its summation
        rdata_sum = np.sum(rdata)

        # put the data and its summation in the producer queue
        print(f"Producer sent checksum: {rdata_sum} (cycle {i+1})")
        producer_queue.put((rdata, rdata_sum))

        tm.sleep(1)  # simulate some delay in producing data


# verify the checksum of the current queue element to be read
def consumer(consumer_queue):
    """
    Consumer function that reads data from the queue and verify the checksum.
    """

    for i in range(CONSUMER_CYCLES):

        # get the current queue element to be read
        rdata, rdata_sum = consumer_queue.get()
        print(f"Consumer received checksum: {rdata_sum} (cycle {i+1})")

        # verify array summation
        if np.sum(rdata) != rdata_sum:
            print("Consumer, checksum error.")

        tm.sleep(2)  # simulate some delay in consuming data

    print("Test terminated. Kill program (double CTRL-C).")


# execution threads
if __name__ == "__main__":

    with cf.ThreadPoolExecutor(max_workers=4) as executor:

        try:
            server_task = executor.submit(server.main)
            tm.sleep(0.5)  # give the server some time to start
            client_task = executor.submit(client.main)
            tm.sleep(1)  # give the client some time to register on server
            consumer_task = executor.submit(consumer,consumer_queue)
            producer_task = executor.submit(producer,producer_queue)

        except Exception as e:
            print(f"Error starting server: {e}")
            exit(1)


#### END
