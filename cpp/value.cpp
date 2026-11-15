#include <netucs/value.hpp>
#include <cstring>
#include <limits>
#include <map>
#include <stdexcept>
#include <type_traits>
namespace netucs {
namespace {
constexpr std::size_t max_size=65502;
void var(Bytes& b,std::uint64_t n){while(n>=128){b.push_back(static_cast<std::uint8_t>(n)|128);n>>=7;}b.push_back(static_cast<std::uint8_t>(n));}
void tag(Bytes& b,unsigned field,unsigned wire){var(b,(field<<3)|wire);}
void blob(Bytes& b,unsigned field,const Bytes& data){tag(b,field,2);var(b,data.size());b.insert(b.end(),data.begin(),data.end());}
void str(Bytes& b,unsigned field,const std::string& s){tag(b,field,2);var(b,s.size());b.insert(b.end(),s.begin(),s.end());}
void num(Bytes& b,unsigned field,std::uint64_t n){tag(b,field,0);var(b,n);}
void validate_array(const NumericArray& a){
 static const std::map<std::string,std::size_t> sizes={{"bool",1},{"int8",1},{"int16",2},{"int32",4},{"int64",8},{"uint8",1},{"uint16",2},{"uint32",4},{"uint64",8},{"float32",4},{"float64",8},{"complex64",8},{"complex128",16}};
 auto it=sizes.find(a.dtype);if(it==sizes.end())throw std::invalid_argument("Unsupported array dtype");
 if(a.shape.size()>32)throw std::invalid_argument("Array exceeds 32 dimensions");
 std::size_t count=1;
 for(auto dim:a.shape){if(dim>2147483647 || (dim && count>max_size/it->second/dim))throw std::invalid_argument("Invalid array shape");count*=dim;}
 if(count*it->second!=a.data.size())throw std::invalid_argument("Array shape and dtype do not match byte count");
 if(a.dtype=="bool")for(auto b:a.data)if(b>1)throw std::invalid_argument("Invalid boolean array data");
}
Bytes encode(const Value& value,int depth){
 if(depth>32)throw std::invalid_argument("Payload nesting exceeds 32 levels");
 Bytes b;
 std::visit([&](const auto& x){using T=std::decay_t<decltype(x)>;
 if constexpr(std::is_same_v<T,std::monostate>)num(b,1,1);
 else if constexpr(std::is_same_v<T,bool>)num(b,2,x);
 else if constexpr(std::is_same_v<T,std::int64_t>)num(b,3,(static_cast<std::uint64_t>(x)<<1)^static_cast<std::uint64_t>(x>>63));
 else if constexpr(std::is_same_v<T,std::uint64_t>)num(b,4,x);
 else if constexpr(std::is_same_v<T,double>){tag(b,5,1);std::uint64_t bits;std::memcpy(&bits,&x,8);for(int i=0;i<8;++i)b.push_back(bits>>(8*i));}
 else if constexpr(std::is_same_v<T,std::string>)str(b,6,x);
 else if constexpr(std::is_same_v<T,Bytes>)blob(b,7,x);
 else if constexpr(std::is_same_v<T,Value::Sequence>){Bytes sub;for(const auto& item:x.items)blob(sub,1,encode(item,depth+1));if(x.is_tuple)num(sub,2,1);blob(b,8,sub);}
 else if constexpr(std::is_same_v<T,Value::Mapping>){Bytes sub;for(const auto& [key,item]:x){Bytes entry;str(entry,1,key);blob(entry,2,encode(item,depth+1));blob(sub,1,entry);}blob(b,9,sub);}
 else if constexpr(std::is_same_v<T,NumericArray>){validate_array(x);Bytes sub;str(sub,1,x.dtype);for(auto dim:x.shape)num(sub,2,dim);blob(sub,3,x.data);blob(b,10,sub);}
 },value.data);
 if(b.size()>max_size)throw std::invalid_argument("Serialized payload exceeds maximum UDP payload size");return b;
}
struct Reader {
 const Bytes& b;std::size_t p=0;
 bool more()const{return p<b.size();}
 std::uint64_t var(){std::uint64_t v=0;for(int i=0;i<10;++i){if(!more())throw std::invalid_argument("Truncated protobuf varint");auto c=b[p++];if(i==9 && c>1)throw std::invalid_argument("Invalid protobuf varint");v|=std::uint64_t(c&127)<<(7*i);if(!(c&128))return v;}throw std::invalid_argument("Invalid protobuf varint");}
 Bytes bytes(){auto n=var();if(n>b.size()-p)throw std::invalid_argument("Truncated protobuf bytes");Bytes out(b.begin()+p,b.begin()+p+static_cast<std::size_t>(n));p+=static_cast<std::size_t>(n);return out;}
 void skip(unsigned wire){if(wire==0){var();return;}if(wire==1){if(b.size()-p<8)throw std::invalid_argument("Truncated fixed64");p+=8;return;}if(wire==2){bytes();return;}if(wire==5){if(b.size()-p<4)throw std::invalid_argument("Truncated fixed32");p+=4;return;}throw std::invalid_argument("Unsupported protobuf wire type");}
};
Value decode(const Bytes& b,int depth){
 if(depth>32)throw std::invalid_argument("Payload nesting exceeds 32 levels");Reader r{b};Value result;bool seen=false;
 while(r.more()){auto t=r.var();unsigned field=t>>3,wire=t&7;if(!field)throw std::invalid_argument("Invalid protobuf field");
 if(field<1 || field>10){r.skip(wire);continue;}
 unsigned expected=(field==5?1:(field>=6?2:0));if(wire!=expected)throw std::invalid_argument("Invalid protobuf wire type");seen=true;
 switch(field){
 case 1:if(r.var()!=1)throw std::invalid_argument("null_value must be true");result=Value{};break;
 case 2:result=Value{bool(r.var())};break;
 case 3:{auto n=r.var();result=Value{static_cast<std::int64_t>((n>>1)^(~(n&1)+1))};break;}
 case 4:result=Value{r.var()};break;
 case 5:{if(b.size()-r.p<8)throw std::invalid_argument("Truncated double");std::uint64_t bits=0;for(int i=0;i<8;++i)bits|=std::uint64_t(b[r.p++])<<(8*i);double d;std::memcpy(&d,&bits,8);result=Value{d};break;}
 case 6:{auto v=r.bytes();result=Value{std::string(v.begin(),v.end())};break;}
 case 7:result=Value{r.bytes()};break;
 case 8:{auto sub=r.bytes();Reader s{sub};Value::Sequence seq;while(s.more()){auto f=s.var();if(f==10)seq.items.push_back(decode(s.bytes(),depth+1));else if(f==16)seq.is_tuple=bool(s.var());else s.skip(f&7);}result=Value{std::move(seq)};break;}
 case 9:{auto sub=r.bytes();Reader s{sub};Value::Mapping map;while(s.more()){auto f=s.var();if(f!=10){s.skip(f&7);continue;}auto entry=s.bytes();Reader e{entry};std::string key;Value v;while(e.more()){auto ef=e.var();if(ef==10){auto k=e.bytes();key.assign(k.begin(),k.end());}else if(ef==18)v=decode(e.bytes(),depth+1);else e.skip(ef&7);}map[key]=std::move(v);}result=Value{std::move(map)};break;}
 case 10:{auto sub=r.bytes();Reader s{sub};NumericArray a;while(s.more()){auto f=s.var();if(f==10){auto x=s.bytes();a.dtype.assign(x.begin(),x.end());}else if(f==16)a.shape.push_back(s.var());else if(f==18){auto packed=s.bytes();Reader pr{packed};while(pr.more())a.shape.push_back(pr.var());}else if(f==26)a.data=s.bytes();else s.skip(f&7);}validate_array(a);result=Value{std::move(a)};break;}
 }
 }
 if(!seen)throw std::invalid_argument("Payload Value has no recognized kind");return result;
}
}
Bytes serialize(const Value& v){return encode(v,0);}
Value deserialize(const Bytes& b){if(b.empty()||b.size()>max_size)throw std::invalid_argument("Invalid UDP payload size");return decode(b,0);}
}
