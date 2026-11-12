"""Numeric wire-layout tests that do not require the Protobuf runtime."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location(
    '_netucs_array_layout', Path(__file__).resolve().parents[1] / 'src/network_arrays.py')
arrays = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arrays)
try:
    import numpy as np
except ImportError:
    np = None


@unittest.skipIf(np is None, 'optional NumPy is not installed')
class ArrayLayoutTests(unittest.TestCase):
    def test_gscv_complex64_wire_layout(self):
        source = np.array([1 + 2j, -3 + 4j], dtype=np.complex64)
        dtype, shape, data = arrays.encode_array(source)
        self.assertEqual((dtype, shape), ('complex64', (2,)))
        self.assertEqual(data, struct.pack('<ffff', 1, 2, -3, 4))
        result = arrays.decode_array(dtype, shape, data)
        self.assertEqual(result.dtype, np.dtype('complex64'))
        np.testing.assert_array_equal(result, source)

    def test_complex128_foreign_sender(self):
        result = arrays.decode_array('complex128', [2], struct.pack('<dddd', 1, -2, 3, -4))
        np.testing.assert_array_equal(result, np.array([1 - 2j, 3 - 4j], dtype='complex128'))

    def test_big_endian_noncontiguous_complex_arrays(self):
        for dtype, component in [('>c8', 'f'), ('>c16', 'd')]:
            source = np.array([[1 + 2j, 9 + 8j], [3 + 4j, 7 + 6j]], dtype=dtype)[:, ::-1]
            name, shape, data = arrays.encode_array(source)
            self.assertEqual(data, struct.pack('<' + component * 8, 9, 8, 1, 2, 7, 6, 3, 4))
            decoded = arrays.decode_array(name, shape, data)
            np.testing.assert_array_equal(decoded, source)
            self.assertTrue(decoded.flags.writeable)

    def test_all_supported_dtypes(self):
        for dtype in arrays.ARRAY_DTYPES:
            with self.subTest(dtype=dtype):
                source = np.array([0, 1], dtype=dtype)
                decoded = arrays.decode_array(*arrays.encode_array(source))
                np.testing.assert_array_equal(decoded, source)
                self.assertEqual(decoded.dtype.name, dtype)

    def test_zero_dimensional_and_empty_arrays(self):
        for source in [np.array(1 + 2j, dtype='complex64'), np.empty((0, 3), dtype='complex128')]:
            decoded = arrays.decode_array(*arrays.encode_array(source))
            self.assertEqual(decoded.shape, source.shape)
            np.testing.assert_array_equal(decoded, source)

    def test_complex_nan_infinity_and_negative_zero(self):
        data = struct.pack('<ffff', float('nan'), float('inf'), -0.0, -float('inf'))
        decoded = arrays.decode_array('complex64', (2,), data)
        self.assertEqual(arrays.encode_array(decoded)[2], data)

    def test_invalid_sizes_and_shapes(self):
        for dtype, shape, data in [('complex64', [2], bytes(8)),
                                   ('complex128', [1], bytes(8)),
                                   ('complex64', [1 << 32], b''),
                                   ('complex64', [-1], b''),
                                   ('complex64', [1] * 33, bytes(8)),
                                   ('bool', [1], b'\x02')]:
            with self.subTest(dtype=dtype, shape=shape):
                with self.assertRaises(ValueError):
                    arrays.decode_array(dtype, shape, data)

    def test_diagnostics_include_unsupported_dtype_and_shape(self):
        for source in [np.array([object()], dtype=object),
                       np.zeros((2, 3), dtype=[('field', 'i4')])]:
            with self.assertRaises(ValueError) as error:
                arrays.encode_array(source)
            self.assertIn(source.dtype.name, str(error.exception))
            self.assertIn(str(source.shape), str(error.exception))
