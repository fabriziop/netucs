"""Protobuf payload compatibility, data validation, and interoperability vectors."""
import importlib
from pathlib import Path
import sys
import types
import unittest

package = types.ModuleType('_netucs_serialization_tests')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'src')]
sys.modules[package.__name__] = package
codec = importlib.import_module(package.__name__ + '.network_serialization')
pb = importlib.import_module(package.__name__ + '.netucs_payload_pb2')


class SerializationTests(unittest.TestCase):
    def test_primitives_and_nested_values(self):
        values = [None, False, True, -(1 << 63), (1 << 63) - 1, 1 << 63,
                  (1 << 64) - 1, 0, -1, 1.25, '', 'hello π', b'', b'\x00\xff',
                  [], (), {}, {'a': [None, True, (1, 'x')], 'b': {'c': b'bytes'}}]
        for value in values:
            with self.subTest(value=value):
                decoded = codec.deserialize(codec.serialize(value))
                self.assertEqual(decoded, value)
                self.assertIs(type(decoded), type(value))

    def test_known_cross_language_wire_vectors(self):
        # Official Protobuf field-key/varint/length-delimited encoding.
        vectors = [(None, b'\x08\x01'), (False, b'\x10\x00'),
                   (-1, b'\x18\x01'), ('hello', b'\x32\x05hello'),
                   (b'abc', b'\x3a\x03abc')]
        for value, wire in vectors:
            self.assertEqual(codec.serialize(value), wire)
            self.assertEqual(codec.deserialize(wire), value)

    def test_generated_message_interoperability(self):
        msg = pb.Value()
        msg.mapping_value.fields['name'].string_value = 'foreign sender'
        msg.mapping_value.fields['count'].int_value = 123
        self.assertEqual(codec.deserialize(msg.SerializeToString()),
                         {'name': 'foreign sender', 'count': 123})
        decoded = pb.Value.FromString(codec.serialize({'count': 42}))
        self.assertEqual(decoded.mapping_value.fields['count'].int_value, 42)

    def test_reject_unsupported_values_and_cycles(self):
        cycle = []; cycle.append(cycle)
        for value in [object(), {1: 'non-string key'}, {1, 2}, 1 << 64,
                      -(1 << 63) - 1, cycle, b'x' * 65502]:
            with self.subTest(value_type=type(value)):
                with self.assertRaises(ValueError):
                    codec.serialize(value)

    def test_reject_malformed_and_invalid_messages(self):
        invalid = [b'', b'\x32\x05abc', b'\xff', b'\x08\x00', b'\x78\x01', b'x' * 65503]
        for wire in invalid:
            with self.subTest(wire=wire[:20]):
                with self.assertRaises(ValueError):
                    codec.deserialize(wire)
        msg = pb.Value()
        msg.sequence_value.items.add()  # A nested Value without its oneof.
        with self.assertRaises(ValueError):
            codec.deserialize(msg.SerializeToString())

    def test_array_validation_without_allocation(self):
        for dtype, shape, data in [('object', [1], b'12345678'),
                                   ('int32', [2], b'1234'),
                                   ('int32', [1 << 32], b''),
                                   ('bool', [1], b'\x02')]:
            msg = pb.Value()
            msg.array_value.dtype = dtype
            msg.array_value.shape.extend(shape)
            msg.array_value.data = data
            with self.assertRaises(ValueError):
                codec.deserialize(msg.SerializeToString())

    def test_numpy_array_and_scalar_roundtrip(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest('optional NumPy is not installed')
        for array in [np.arange(12, dtype='>i4').reshape(3, 4)[:, ::2],
                      np.array(7, dtype='int16'), np.empty((0, 2)),
                      np.array([True, False]),
                      np.array([1 + 2j, -3 + 4j], dtype='complex64'),
                      np.array([1 + 2j, -3 + 4j], dtype='>c16')[::-1], np.array([1.25, -0.5], dtype='float32')]:
            decoded = codec.deserialize(codec.serialize(array))
            np.testing.assert_array_equal(array, decoded)
            self.assertTrue(decoded.flags.writeable)
        self.assertEqual(codec.deserialize(codec.serialize(np.int64(5))), 5)
        with self.assertRaises(ValueError):
            codec.serialize(np.array([object()], dtype=object))
        # Existing network_test.py payload is supported without an API change.
        array = np.arange(100, dtype=np.int32)
        received, checksum = codec.deserialize(codec.serialize((array, np.sum(array))))
        np.testing.assert_array_equal(received, array)
        self.assertEqual(checksum, np.sum(array))
