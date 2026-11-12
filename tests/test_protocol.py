"""Protocol wire compatibility tests; run with python3 -m unittest discover -s tests."""
import asyncio
import importlib
from pathlib import Path
import queue
import struct
import sys
import types
import unittest
from unittest.mock import Mock, patch

# Load the protocol modules without executing the package's demo imports.
package = types.ModuleType('_netucs_protocol_tests')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'src')]
sys.modules[package.__name__] = package
nc = importlib.import_module(package.__name__ + '.network_common')
serialization = importlib.import_module(package.__name__ + '.network_serialization')
NetworkClient = importlib.import_module(package.__name__ + '.network_client').NetworkClient
NetworkServer = importlib.import_module(package.__name__ + '.network_server').NetworkServer
ADDR = ('127.0.0.1', 12345)


def make_client():
    client = NetworkClient(*ADDR, 10, 1, 1, queue.Queue())
    client.acknowledge_received = asyncio.Event()
    return client


class ProtocolTests(unittest.TestCase):
    def test_wire_layout(self):
        self.assertEqual(nc.PROTOCOL_VERSION, 3)
        self.assertEqual(nc.packet_header.size, 5)
        self.assertEqual(nc.data_query_packet.pack(nc.PROTOCOL_VERSION, 1, 7, 3),
                         b'\x03\x00\x01\x00\x07\x00\x00\x00\x03')
        self.assertEqual(nc.acknowledge_packet.size, 9)

    def test_registration_and_acknowledgment(self):
        server = NetworkServer(*ADDR, 10, queue.Queue())
        server.transport = Mock()
        server.datagram_received(nc.data_query_packet.pack(nc.PROTOCOL_VERSION, 1, 7, 3), ADDR)
        registration = server.clients_to_add.get_nowait()
        self.assertEqual(registration.addr, ADDR)
        self.assertEqual(registration.data_send_period, 3)
        ack, target = server.transport.sendto.call_args.args
        self.assertEqual(nc.acknowledge_packet.unpack(ack), (3, 99, 0, 7))
        client = make_client()
        client.datagram_received(ack, ADDR)
        self.assertTrue(client.acknowledge_received.is_set())

    def test_reject_before_side_effects(self):
        server = NetworkServer(*ADDR, 10, queue.Queue())
        server.transport = Mock()
        client = make_client()
        query = nc.data_query_packet.pack(nc.PROTOCOL_VERSION, 1, 7, 3)
        ack = nc.acknowledge_packet.pack(nc.PROTOCOL_VERSION, 99, 0, 7)
        response = nc.data_response_packet.pack(nc.PROTOCOL_VERSION, 2, 0) + serialization.serialize('data')
        invalid = [b'', struct.pack('!hhl', 1, 7, 3),
                   struct.pack('!hhhxx', 99, 0, 7),
                   struct.pack('!hh', 2, 0) + serialization.serialize('old')]
        for packet in (query, ack, response):
            invalid.extend(packet[:n] for n in range(nc.packet_header.size))
            invalid.extend(bytes([v]) + packet[1:] for v in (0, 1, 2, 255))
        invalid += [query[:-1], query + b'x', ack[:-1], ack + b'x',
                    response[:5], nc.packet_header.pack(nc.PROTOCOL_VERSION, 123, 0)]
        with patch.object(serialization, 'deserialize', side_effect=AssertionError('must not deserialize')):
            for packet in invalid:
                with self.subTest(packet=packet):
                    server.datagram_received(packet, ADDR)
                    client.datagram_received(packet, ADDR)
        server.transport.sendto.assert_not_called()
        self.assertTrue(server.clients_to_add.empty())
        self.assertFalse(client.acknowledge_received.is_set())
        self.assertTrue(client.data_queue.empty())
        self.assertIsNone(client.receive_packet_type)
        self.assertIsNone(server.receive_packet_type)

    def test_data_response(self):
        client = make_client()
        payload = {'value': [1, 2, 3]}
        client.datagram_received(nc.data_response_packet.pack(nc.PROTOCOL_VERSION, 2, 9) + serialization.serialize(payload), ADDR)
        self.assertEqual(client.data_queue.get_nowait()[1], payload)

    def test_bad_protobuf_is_dropped_and_client_recovers(self):
        client = make_client()
        client.datagram_received(nc.data_response_packet.pack(3, 2, 0) + b'\xff', ADDR)
        self.assertTrue(client.data_queue.empty())
        client.datagram_received(nc.data_response_packet.pack(nc.PROTOCOL_VERSION, 2, 1) + serialization.serialize('valid'), ADDR)
        self.assertEqual(client.data_queue.get_nowait()[1], 'valid')


class SenderTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_sender_versions_query(self):
        client = make_client()
        client.terminate_event = asyncio.Event()
        client.transport = Mock()
        def sent(packet, addr):
            self.assertEqual(nc.data_query_packet.unpack(packet), (3, 1, 0, 1))
            client.acknowledge_received.set()
            client.terminate_event.set()
        client.transport.sendto.side_effect = sent
        await asyncio.wait_for(client.sender(), 2)
        client.transport.sendto.assert_called_once()

    async def test_server_sender_versions_response(self):
        server = NetworkServer(*ADDR, 10, queue.Queue())
        server.terminate_event = asyncio.Event()
        server.transport = Mock()
        server.clients[ADDR] = nc.Client(ADDR, 1, 0, float('inf'))
        server.data_queue.put({'value': 42})
        def sent(packet, addr):
            self.assertEqual(nc.packet_header.unpack_from(packet), (3, 2, 0))
            self.assertEqual(serialization.deserialize(packet[nc.packet_header.size:]), {'value': 42})
            server.terminate_event.set()
        server.transport.sendto.side_effect = sent
        await asyncio.wait_for(server.sender(), 2)
        server.transport.sendto.assert_called_once()

    async def test_udp_loopback_roundtrip(self):
        server = NetworkServer('127.0.0.1', 0, 10, queue.Queue())
        client = make_client()
        loop = asyncio.get_running_loop()
        server_transport, _ = await loop.create_datagram_endpoint(
            lambda: server, local_addr=('127.0.0.1', 0))
        client_transport, _ = await loop.create_datagram_endpoint(
            lambda: client, remote_addr=server_transport.get_extra_info('sockname'))
        server.terminate_event = asyncio.Event()
        sender = asyncio.create_task(server.sender())
        try:
            client_transport.sendto(nc.data_query_packet.pack(nc.PROTOCOL_VERSION, 1, 12, 1))
            await asyncio.wait_for(client.acknowledge_received.wait(), 2)
            server.data_queue.put('loopback payload')
            _, payload = await asyncio.wait_for(asyncio.to_thread(client.data_queue.get, True, 2), 3)
            self.assertEqual(payload, 'loopback payload')
        finally:
            server.terminate_event.set()
            await asyncio.wait_for(sender, 2)
            client_transport.close()
            server_transport.close()
            await asyncio.sleep(0)
