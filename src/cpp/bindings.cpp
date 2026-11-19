#include <netucs/network.hpp>
#include <netucs/value.hpp>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include <limits>
#include <cstring>
namespace py=pybind11;
namespace {
netucs::Value to_value(py::handle obj,int depth=0) {
 if(depth>32)throw py::value_error("Payload nesting exceeds 32 levels");
 if(obj.is_none())return {};
 if(py::isinstance<py::bool_>(obj))return netucs::Value{obj.cast<bool>()};
 if(py::isinstance<py::int_>(obj)){
  int overflow=0; auto signed_value=PyLong_AsLongLongAndOverflow(obj.ptr(),&overflow);
  if(!PyErr_Occurred() && !overflow)return netucs::Value{static_cast<std::int64_t>(signed_value)};
  PyErr_Clear(); auto unsigned_value=PyLong_AsUnsignedLongLong(obj.ptr());
  if(PyErr_Occurred()){PyErr_Clear();throw py::value_error("Integer outside signed/unsigned 64-bit range");}
  return netucs::Value{static_cast<std::uint64_t>(unsigned_value)};
 }
 if(py::isinstance<py::float_>(obj))return netucs::Value{obj.cast<double>()};
 if(py::isinstance<py::str>(obj))return netucs::Value{obj.cast<std::string>()};
 if(py::isinstance<py::bytes>(obj)){auto s=obj.cast<std::string>();return netucs::Value{netucs::Bytes(s.begin(),s.end())};}
 if(py::isinstance<py::array>(obj)){
  auto array=py::reinterpret_borrow<py::array>(obj);
  auto dtype=py::str(array.attr("dtype").attr("name")).cast<std::string>();
  static const std::map<std::string,std::string> dtypes={{"bool","?"},{"int8","i1"},{"int16","<i2"},{"int32","<i4"},{"int64","<i8"},{"uint8","u1"},{"uint16","<u2"},{"uint32","<u4"},{"uint64","<u8"},{"float32","<f4"},{"float64","<f8"},{"complex64","<c8"},{"complex128","<c16"}};
  auto it=dtypes.find(dtype);if(it==dtypes.end())throw py::value_error("Unsupported array dtype: "+dtype);
  if(array.ndim()>32)throw py::value_error("Array exceeds 32 dimensions");
  netucs::NumericArray a;a.dtype=dtype;
  for(auto i=0;i<array.ndim();++i){if(array.shape(i)>2147483647)throw py::value_error("Array dimension exceeds supported range");a.shape.push_back(static_cast<std::uint64_t>(array.shape(i)));}
  py::object normalized=array.attr("astype")(py::dtype(it->second),py::arg("copy")=false);
  std::string bytes=normalized.attr("tobytes")(py::arg("order")="C").cast<std::string>();
  a.data.assign(bytes.begin(),bytes.end());return netucs::Value{std::move(a)};
 }
 if(py::isinstance<py::tuple>(obj)||py::isinstance<py::list>(obj)){
  netucs::Value::Sequence seq;seq.is_tuple=py::isinstance<py::tuple>(obj);
  for(auto item:obj)seq.items.push_back(to_value(item,depth+1));return netucs::Value{std::move(seq)};
 }
 if(py::isinstance<py::dict>(obj)){
  netucs::Value::Mapping mapping;
  for(auto item:py::reinterpret_borrow<py::dict>(obj)){
   if(!py::isinstance<py::str>(item.first))throw py::value_error("Mapping keys must be strings");
   mapping.emplace(item.first.cast<std::string>(),to_value(item.second,depth+1));
  }return netucs::Value{std::move(mapping)};
 }
 if(py::hasattr(obj,"dtype") && py::hasattr(obj,"item"))return to_value(obj.attr("item")(),depth);
 throw py::value_error("Unsupported payload type");
}
py::object from_value(const netucs::Value& value,int depth=0){
 if(depth>32)throw py::value_error("Payload nesting exceeds 32 levels");
 return std::visit([&](const auto& v)->py::object{
  using T=std::decay_t<decltype(v)>;
  if constexpr(std::is_same_v<T,std::monostate>)return py::none();
  else if constexpr(std::is_same_v<T,bool>||std::is_same_v<T,std::int64_t>||std::is_same_v<T,std::uint64_t>||std::is_same_v<T,double>)return py::cast(v);
  else if constexpr(std::is_same_v<T,std::string>)return py::str(v);
  else if constexpr(std::is_same_v<T,netucs::Bytes>)return py::bytes(reinterpret_cast<const char*>(v.data()),v.size());
  else if constexpr(std::is_same_v<T,netucs::Value::Sequence>){py::list items;for(auto& item:v.items)items.append(from_value(item,depth+1));if(v.is_tuple)return py::tuple(items);return items;}
  else if constexpr(std::is_same_v<T,netucs::Value::Mapping>){py::dict out;for(auto& [key,item]:v)out[py::str(key)]=from_value(item,depth+1);return out;}
  else {
   static const std::map<std::string,std::pair<std::string,std::size_t>> dtypes={{"bool",{"?",1}},{"int8",{"i1",1}},{"int16",{"<i2",2}},{"int32",{"<i4",4}},{"int64",{"<i8",8}},{"uint8",{"u1",1}},{"uint16",{"<u2",2}},{"uint32",{"<u4",4}},{"uint64",{"<u8",8}},{"float32",{"<f4",4}},{"float64",{"<f8",8}},{"complex64",{"<c8",8}},{"complex128",{"<c16",16}}};
   auto it=dtypes.find(v.dtype);if(it==dtypes.end())throw py::value_error("Unsupported array dtype");
   std::size_t count=1;py::tuple shape(v.shape.size());
   for(std::size_t i=0;i<v.shape.size();++i){auto d=v.shape[i];if(d>2147483647||count>65502/it->second.second/std::max<std::uint64_t>(1,d))throw py::value_error("Invalid array shape");count*=d;shape[i]=py::int_(d);}
   if(count*it->second.second!=v.data.size())throw py::value_error("Array shape and dtype do not match byte count");
   if(v.dtype=="bool")for(auto b:v.data)if(b>1)throw py::value_error("Invalid boolean array data");
   auto np=py::module_::import("numpy");
   auto buffer=py::bytes(reinterpret_cast<const char*>(v.data.data()),v.data.size());
   return np.attr("frombuffer")(buffer,py::arg("dtype")=it->second.first).attr("reshape")(shape).attr("copy")();
  }
 },value.data);
}
}
PYBIND11_MODULE(_netucs_native,m) {
 m.def("set_log_callback",[](py::object callback){
   if(callback.is_none()){netucs::set_log_callback({});return;}
   auto* holder=new py::object(std::move(callback));
   // The Python callback is called from native threads under the GIL.
   // Keep it alive until process exit to avoid Python finalization races.
   netucs::set_log_callback([holder](netucs::LogLevel level,const std::string& logger,const std::string& message){
     py::gil_scoped_acquire gil;
     try {(*holder)(static_cast<int>(level),logger,message);}
     catch(py::error_already_set& e){e.discard_as_unraisable("netucs logging callback");}
   });
 });
 m.def("serialize",[](py::object value){auto b=netucs::serialize(to_value(value));return py::bytes(reinterpret_cast<const char*>(b.data()),b.size());});
 m.def("deserialize",[](py::bytes payload){auto s=payload.cast<std::string>();return from_value(netucs::deserialize(netucs::Bytes(s.begin(),s.end())));});
 py::class_<netucs::Backoff>(m,"Backoff").def(py::init<>()).def_readwrite("min_period",&netucs::Backoff::min_period).def_readwrite("max_period",&netucs::Backoff::max_period).def_readwrite("time_constant",&netucs::Backoff::time_constant).def_readwrite("variance",&netucs::Backoff::variance);
 py::class_<netucs::ClientConfig>(m,"ClientConfig").def(py::init<>()).def_readwrite("server_address",&netucs::ClientConfig::server_address).def_readwrite("server_port",&netucs::ClientConfig::server_port).def_readwrite("client_lifetime",&netucs::ClientConfig::client_lifetime).def_readwrite("client_lifetime_guard",&netucs::ClientConfig::client_lifetime_guard).def_readwrite("acknowledge_timeout",&netucs::ClientConfig::acknowledge_timeout).def_readwrite("backoff",&netucs::ClientConfig::backoff);
 py::class_<netucs::ServerConfig>(m,"ServerConfig").def(py::init<>()).def_readwrite("address",&netucs::ServerConfig::address).def_readwrite("port",&netucs::ServerConfig::port).def_readwrite("client_lifetime",&netucs::ServerConfig::client_lifetime).def_readwrite("backoff",&netucs::ServerConfig::backoff);
 py::class_<netucs::NetworkClient>(m,"NativeClient")
 .def(py::init([](netucs::ClientConfig c,py::object callback){return std::make_unique<netucs::NetworkClient>(std::move(c),[callback](double t,const netucs::Bytes& b){py::gil_scoped_acquire gil;try{callback(t,from_value(netucs::deserialize(b)));}catch(py::error_already_set& e){e.discard_as_unraisable("netucs client callback");}catch(const std::exception& e){PyErr_SetString(PyExc_ValueError,e.what());PyErr_WriteUnraisable(callback.ptr());}});}),py::arg("config"),py::arg("callback"))
 .def("start",&netucs::NetworkClient::start).def("main",&netucs::NetworkClient::main,py::call_guard<py::gil_scoped_release>()).def("join",&netucs::NetworkClient::join,py::call_guard<py::gil_scoped_release>()).def("terminate",&netucs::NetworkClient::terminate).def("shutdown",&netucs::NetworkClient::shutdown).def_property_readonly("running",&netucs::NetworkClient::running);
 py::class_<netucs::NetworkServer>(m,"NativeServer").def(py::init<netucs::ServerConfig>()).def("start",&netucs::NetworkServer::start).def("main",&netucs::NetworkServer::main,py::call_guard<py::gil_scoped_release>()).def("join",&netucs::NetworkServer::join,py::call_guard<py::gil_scoped_release>()).def("terminate",&netucs::NetworkServer::terminate).def("shutdown",&netucs::NetworkServer::shutdown)
 .def("publish",[](netucs::NetworkServer& s,py::bytes payload){std::string b=payload;s.publish({b.begin(),b.end()});})
 .def("publish_value",[](netucs::NetworkServer& s,py::object value){s.publish_value(to_value(value));})
 .def_property_readonly("running",&netucs::NetworkServer::running);
}
