#pragma once
#include <netucs/network.hpp>
#include <cstdint>
#include <map>
#include <string>
#include <variant>
#include <vector>
namespace netucs {
struct NumericArray { std::string dtype; std::vector<std::uint64_t> shape; Bytes data; };
struct Value {
    struct Sequence { std::vector<Value> items; bool is_tuple=false; };
    using Mapping=std::map<std::string,Value>;
    using Storage=std::variant<std::monostate,bool,std::int64_t,std::uint64_t,double,std::string,Bytes,Sequence,Mapping,NumericArray>;
    Storage data;
    Value()=default;
    template<class T> Value(T v):data(std::move(v)) {}
};
// Protocol Buffers netucs.Value encoding, identical field numbers to src/netucs_payload.proto.
Bytes serialize(const Value& value);
Value deserialize(const Bytes& payload);
}
