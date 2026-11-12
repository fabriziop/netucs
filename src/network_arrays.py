"""Portable NumericArray layout, independent of the Protobuf runtime."""
import math

# dtype name -> NumPy wire dtype and bytes per element.
ARRAY_DTYPES = {
    'bool': ('?', 1), 'int8': ('i1', 1), 'int16': ('<i2', 2),
    'int32': ('<i4', 4), 'int64': ('<i8', 8), 'uint8': ('u1', 1),
    'uint16': ('<u2', 2), 'uint32': ('<u4', 4), 'uint64': ('<u8', 8),
    'float32': ('<f4', 4), 'float64': ('<f8', 8),
    'complex64': ('<c8', 8), 'complex128': ('<c16', 16),
}


def require_numpy():
    try:
        import numpy
    except ImportError as exc:
        raise ValueError('NumPy is required for numeric array payloads; install netucs[numpy]') from exc
    return numpy


def _layout(dtype, shape):
    if dtype not in ARRAY_DTYPES:
        raise ValueError(f'Unsupported array dtype {dtype!r}, shape={tuple(shape)}; '
                         'supported dtypes: ' + ', '.join(ARRAY_DTYPES))
    if len(shape) > 32:
        raise ValueError(f'Array has {len(shape)} dimensions, shape={tuple(shape)}; maximum is 32')
    if any(dimension < 0 or dimension > (1 << 31) - 1 for dimension in shape):
        raise ValueError(f'Array dimension exceeds supported range: shape={tuple(shape)}')
    return ARRAY_DTYPES[dtype]


def encode_array(value):
    """Return dtype name, shape and little-endian row-major element bytes."""
    dtype = value.dtype.name
    wire_dtype, _ = _layout(dtype, value.shape)
    data = value.astype(wire_dtype, copy=False).tobytes(order='C')
    return dtype, tuple(value.shape), data


def decode_array(dtype, shape, data):
    """Validate and reconstruct a writable array; complex elements are real, imag."""
    wire_dtype, size = _layout(dtype, shape)
    if math.prod(shape) * size != len(data):
        raise ValueError(f'Array shape {tuple(shape)} and dtype {dtype!r} do not match '
                         f'its byte count {len(data)}')
    if dtype == 'bool' and any(byte > 1 for byte in data):
        raise ValueError('Invalid boolean array data')
    np = require_numpy()
    return np.frombuffer(data, dtype=wire_dtype).reshape(tuple(shape)).copy()
