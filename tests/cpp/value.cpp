#include <netucs/value.hpp>
#include <cassert>
#include <cstdint>
#include <iostream>
int main(){
 using namespace netucs;
 Value::Mapping m;
 m["signed"]=Value{std::int64_t(-123)};
 m["unsigned"]=Value{std::uint64_t(UINT64_MAX)};
 m["float"]=Value{3.5};
 m["list"]=Value{Value::Sequence{{Value{true},Value{std::string("hi")}},false}};
 m["array"]=Value{NumericArray{"int16",{2},{1,0,2,0}}};
 auto wire=serialize(Value{m});
 auto result=deserialize(wire);
 auto& out=std::get<Value::Mapping>(result.data);
 assert(std::get<std::int64_t>(out.at("signed").data)==-123);
 assert(std::get<std::uint64_t>(out.at("unsigned").data)==UINT64_MAX);
 assert(std::get<double>(out.at("float").data)==3.5);
 assert(std::get<NumericArray>(out.at("array").data).data.size()==4);
 assert(serialize(result)==wire);
 assert(serialize(Value{})==Bytes({8,1}));
 assert(serialize(Value{std::int64_t(-1)})==Bytes({24,1}));
 std::cout<<"Value protobuf round-trip OK\n";
}
