# Python bindings for netucs_payload.proto. Do not edit the serialized descriptor.
# To regenerate using protoc, see README.md.
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf.internal import builder as _builder

DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x14netucs_payload.proto\x12\x06netucs"\xaf\x02\n\x05Value\x12\x14\n\nnull_value\x18\x01 \x01(\x08H\x00\x12\x14\n\nbool_value\x18\x02 \x01(\x08H\x00\x12\x13\n\tint_value\x18\x03 \x01(\x12H\x00\x12\x14\n\nuint_value\x18\x04 \x01(\x04H\x00\x12\x15\n\x0bfloat_value\x18\x05 \x01(\x01H\x00\x12\x16\n\x0cstring_value\x18\x06 \x01(\tH\x00\x12\x15\n\x0bbytes_value\x18\x07 \x01(\x0cH\x00\x12*\n\x0esequence_value\x18\x08 \x01(\x0b2\x10.netucs.SequenceH\x00\x12(\n\rmapping_value\x18\t \x01(\x0b2\x0f.netucs.MappingH\x00\x12+\n\x0barray_value\x18\n \x01(\x0b2\x14.netucs.NumericArrayH\x00B\x06\n\x04kind":\n\x08Sequence\x12\x1c\n\x05items\x18\x01 \x03(\x0b2\r.netucs.Value\x12\x10\n\x08is_tuple\x18\x02 \x01(\x08"t\n\x07Mapping\x12+\n\x06fields\x18\x01 \x03(\x0b2\x1b.netucs.Mapping.FieldsEntry\x1a<\n\x0bFieldsEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\x1c\n\x05value\x18\x02 \x01(\x0b2\r.netucs.Value:\x028\x01":\n\x0cNumericArray\x12\r\n\x05dtype\x18\x01 \x01(\t\x12\r\n\x05shape\x18\x02 \x03(\x04\x12\x0c\n\x04data\x18\x03 \x01(\x0cb\x06proto3')
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, __name__, globals())
