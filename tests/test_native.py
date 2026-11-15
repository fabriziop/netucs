import socket
import threading
import queue
import time
import pytest
from src import _netucs_native as native
from src import network_serialization as legacy

@pytest.mark.parametrize('value', [None, True, False, -42, 2**63, 1.25, 'hi', b'bytes', (1, 'a'), {'key': [False, 42]}])
def test_wire_compatibility(value):
    assert native.deserialize(legacy.serialize(value)) == value
    assert legacy.deserialize(native.serialize(value)) == value

def test_numpy_wire_compatibility():
    np = pytest.importorskip('numpy')
    for dtype in ('bool','int8','int16','int32','int64','uint8','uint16','uint32','uint64','float32','float64','complex64','complex128'):
        value=np.arange(6).astype(dtype).reshape(2,3)
        np.testing.assert_array_equal(native.deserialize(legacy.serialize(value)),value)
        np.testing.assert_array_equal(legacy.deserialize(native.serialize(value)),value)
    value=np.arange(6,dtype='>i4').reshape(2,3)[:, ::-1]
    np.testing.assert_array_equal(native.deserialize(native.serialize(value)),value)

def test_udp_python_api():
    from src.native_api import NetworkClient, NetworkServer
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    incoming=queue.Queue(); outgoing=queue.Queue()
    server=NetworkServer('127.0.0.1',port,30,outgoing)
    client=NetworkClient('127.0.0.1',port,30,5,1,incoming)
    server.start();client.start()
    try:
        time.sleep(.25)
        for _ in range(15):
            outgoing.put({'data':[1,2,3]})
            try:
                timestamp, data=incoming.get(timeout=.2)
                assert isinstance(timestamp,float)
                assert data=={'data':[1,2,3]}
                break
            except queue.Empty: pass
        else: pytest.fail('UDP message not received')
    finally:
        client.terminate();server.terminate();client.join();server.join()
