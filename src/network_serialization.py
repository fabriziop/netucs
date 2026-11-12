"""Language-independent UDP payloads defined in netucs_payload.proto."""
from google.protobuf.message import DecodeError

from . import netucs_payload_pb2 as pb
from .network_arrays import encode_array, decode_array, require_numpy

MAX_PAYLOAD_SIZE = 65502  # IPv4 UDP limit minus the 5-byte netucs header.
MAX_DEPTH = 32

def _encode(value, message, depth):
    if depth > MAX_DEPTH:
        raise ValueError('Payload nesting exceeds 32 levels (or contains a cycle)')
    # Only import NumPy when a NumPy value is actually encountered.
    if type(value).__module__.split('.')[0] == 'numpy':
        np = require_numpy()
        if isinstance(value, np.ndarray):
            name, shape, data = encode_array(value)
            array = message.array_value
            array.dtype = name
            array.shape.extend(shape)
            array.data = data
            return
        if isinstance(value, np.generic):
            value = value.item()
    if value is None:
        message.null_value = True
    elif isinstance(value, bool):
        message.bool_value = value
    elif isinstance(value, int):
        if -(1 << 63) <= value < (1 << 63):
            message.int_value = value
        elif (1 << 63) <= value < (1 << 64):
            message.uint_value = value
        else:
            raise ValueError('Integer outside signed/unsigned 64-bit range')
    elif isinstance(value, float):
        message.float_value = value
    elif isinstance(value, str):
        message.string_value = value
    elif isinstance(value, bytes):
        message.bytes_value = value
    elif isinstance(value, (list, tuple)):
        sequence = message.sequence_value
        sequence.SetInParent()
        sequence.is_tuple = isinstance(value, tuple)
        for item in value:
            _encode(item, sequence.items.add(), depth + 1)
    elif isinstance(value, dict):
        mapping = message.mapping_value
        mapping.SetInParent()
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError('Mapping keys must be strings')
            _encode(item, mapping.fields[key], depth + 1)
    else:
        raise ValueError('Unsupported payload type: ' + type(value).__name__)


def _decode(message, depth):
    if depth > MAX_DEPTH:
        raise ValueError('Payload nesting exceeds 32 levels')
    kind = message.WhichOneof('kind')
    if kind is None:
        raise ValueError('Payload Value has no recognized kind')
    if kind == 'null_value':
        if not message.null_value:
            raise ValueError('null_value must be true')
        return None
    if kind == 'sequence_value':
        sequence = message.sequence_value
        values = [_decode(item, depth + 1) for item in sequence.items]
        return tuple(values) if sequence.is_tuple else values
    if kind == 'mapping_value':
        return {key: _decode(item, depth + 1) for key, item in message.mapping_value.fields.items()}
    if kind == 'array_value':
        array = message.array_value
        return decode_array(array.dtype, array.shape, array.data)
    return getattr(message, kind)


def serialize(value):
    """Encode supported Python values as a netucs.Value Protobuf message."""
    message = pb.Value()
    _encode(value, message, 0)
    if message.ByteSize() > MAX_PAYLOAD_SIZE:
        raise ValueError('Serialized payload exceeds maximum UDP payload size')
    return message.SerializeToString()


def deserialize(data):
    """Decode and validate a netucs.Value message; never execute Python objects."""
    if not data or len(data) > MAX_PAYLOAD_SIZE:
        raise ValueError('Invalid UDP payload size')
    message = pb.Value()
    try:
        message.ParseFromString(data)
    except DecodeError as exc:
        raise ValueError('Malformed Protocol Buffers payload') from exc
    return _decode(message, 0)
