#include <netucs/network.hpp>
#include <netucs/value.hpp>
#include <conductor/scheduler.hpp>
#include <arpa/inet.h>
#include <netdb.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstring>
#include <deque>
#include <map>
#include <random>
#include <stdexcept>
#include <thread>

namespace netucs {
namespace {
std::mutex log_mutex;
LogCallback log_callback;
void log(LogLevel level, const char* logger, const std::string& message) {
    LogCallback cb;
    { std::lock_guard<std::mutex> lock(log_mutex); cb=log_callback; }
    if (cb) { try { cb(level, logger, message); } catch (...) {} }
}

using Clock=std::chrono::steady_clock;
double now() { return std::chrono::duration<double>(Clock::now().time_since_epoch()).count(); }
double epoch() { return std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count(); }
void header(Bytes& b, std::int16_t type, std::uint16_t seq) {
    b.push_back(protocol_version); b.push_back(static_cast<std::uint8_t>(type>>8)); b.push_back(static_cast<std::uint8_t>(type));
    b.push_back(static_cast<std::uint8_t>(seq>>8)); b.push_back(static_cast<std::uint8_t>(seq));
}
int packet_type(const std::uint8_t* p, std::size_t n) {
    if(n<5 || p[0]!=protocol_version) return 0;
    int t=(p[1]<<8)|p[2];
    if((t==1 && n==9)||(t==99 && n==9)||(t==2 && n>5)) return t;
    return 0;
}
sockaddr_in resolve(const std::string& host, std::uint16_t port, bool passive) {
    addrinfo hints{}; hints.ai_family=AF_INET; hints.ai_socktype=SOCK_DGRAM;
    hints.ai_flags=passive?AI_PASSIVE:0;
    addrinfo* result=nullptr;
    auto service=std::to_string(port);
    int rc=getaddrinfo(host.empty()?nullptr:host.c_str(),service.c_str(),&hints,&result);
    if(rc!=0) throw std::runtime_error(gai_strerror(rc));
    sockaddr_in addr=*reinterpret_cast<sockaddr_in*>(result->ai_addr);
    freeaddrinfo(result); return addr;
}
int socket_open(const sockaddr_in* bind_addr=nullptr) {
    int fd=::socket(AF_INET,SOCK_DGRAM,0);
    if(fd<0) throw std::runtime_error(std::strerror(errno));
    if(bind_addr && ::bind(fd,reinterpret_cast<const sockaddr*>(bind_addr),sizeof(*bind_addr))<0) {
        auto msg=std::string(std::strerror(errno)); ::close(fd); throw std::runtime_error(msg);
    }
    return fd;
}
std::string key(const sockaddr_in& addr) { return std::string(reinterpret_cast<const char*>(&addr),sizeof(addr)); }
struct Worker {
    std::atomic<bool> active{false};
    std::thread thread;
    std::mutex mutex;
    std::condition_variable cv;
    int fd=-1;
    conductor::Scheduler scheduler{2};
    void stop() { active=false; cv.notify_all(); if(fd>=0) { ::close(fd); fd=-1; } }
    void join() { if(thread.joinable()) thread.join(); }
    ~Worker() { stop(); join(); }
};
void wait(Worker& w, double seconds) {
    std::unique_lock<std::mutex> lock(w.mutex);
    w.cv.wait_for(lock,std::chrono::duration<double>(std::max(0.0,seconds)),[&]{return !w.active.load();});
}
conductor::TaskOptions periodic(double seconds, const char* name) {
    conductor::TaskOptions o;
    o.task_id=name;
    o.period=std::chrono::microseconds(static_cast<std::int64_t>(seconds*1e6));
    o.overlap_policy=conductor::OverlapPolicy::Skip;
    return o;
}
}
void set_log_callback(LogCallback callback) {
    std::lock_guard<std::mutex> lock(log_mutex);
    log_callback=std::move(callback);
}
struct NetworkClient::Impl {
    ClientConfig config;
    ReceiveCallback callback;
    Worker w;
    sockaddr_in remote{};
    std::atomic<bool> ack{false};
    std::atomic<std::uint16_t> seq{0};
    double last_query=-1e10, ack_deadline=0, retry_after=0;
    unsigned retries=0;
    explicit Impl(ClientConfig c, ReceiveCallback cb):config(std::move(c)),callback(std::move(cb)) {}
    void query() {
        if(!w.active) return;
        double t=now();
        if(t<retry_after || t-last_query<std::max(.05,config.client_lifetime-config.client_lifetime_guard)) return;
        if(ack_deadline>0 && !ack.exchange(false) && t<ack_deadline) return;
        Bytes b; header(b,1,seq++); b.insert(b.end(),{0,0,0,1});
        if(w.fd>=0) {
            auto sent=::sendto(w.fd,b.data(),b.size(),0,reinterpret_cast<sockaddr*>(&remote),sizeof(remote));
            if(sent<0) log(LogLevel::Warning,"netucs.network_client","netucs: request send failed: "+std::string(std::strerror(errno)));
            else log(LogLevel::Debug,"netucs.network_client","netucs: sending data request");
        }
        last_query=t; ack_deadline=t+config.acknowledge_timeout;
    }
    void check_ack() {
        if(ack.exchange(false)) { retries=0; ack_deadline=0; log(LogLevel::Info,"netucs.network_client","netucs: received marker request acknowledge"); return; }
        if(ack_deadline>0 && now()>=ack_deadline) {
            double delay=std::min(config.backoff.max_period,config.backoff.min_period*std::pow(config.backoff.time_constant,std::min(retries,20u)));
            retry_after=now()+delay;
            last_query=-1e10;
            ack_deadline=0; ++retries;
            log(LogLevel::Warning,"netucs.network_client","netucs: marker request acknowledge timeout (retry count: "+std::to_string(retries)+")");
            log(LogLevel::Info,"netucs.network_client","netucs: applying exponential backoff: "+std::to_string(delay)+" seconds");
        }
    }
    void run() {
        try {
            remote=resolve(config.server_address,config.server_port,false);
            w.fd=socket_open();
            log(LogLevel::Debug,"netucs.network_client","netucs: UDP endpoint ready");
            w.scheduler.add_task([this]{check_ack();query();},periodic(.05,"client_query"));
            w.scheduler.start_engine();
            std::uint8_t buf[65507];
            while(w.active) {
                pollfd pfd{w.fd,POLLIN,0};
                if(::poll(&pfd,1,100)<=0) continue;
                sockaddr_in sender{}; socklen_t sl=sizeof(sender);
                ssize_t n=::recvfrom(w.fd,buf,sizeof(buf),0,reinterpret_cast<sockaddr*>(&sender),&sl);
                if(n<=0 || sender.sin_addr.s_addr!=remote.sin_addr.s_addr || sender.sin_port!=remote.sin_port) continue;
                int t=packet_type(buf,static_cast<std::size_t>(n));
                if(t==99) ack=true;
                else if(t==2 && callback) {
                    log(LogLevel::Debug,"netucs.network_client","netucs: received UDP data");
                    callback(epoch(),Bytes(buf+5,buf+n));
                }
            }
        } catch(const std::exception& e) {
            log(LogLevel::Error,"netucs.network_client",std::string("netucs: client worker failed: ")+e.what()); w.active=false;
        } catch(...) { log(LogLevel::Error,"netucs.network_client","netucs: client worker failed: unknown error"); w.active=false; }
        w.scheduler.stop(); w.active=false;
    }
};
NetworkClient::NetworkClient(ClientConfig c,ReceiveCallback cb):impl_(new Impl(std::move(c),std::move(cb))) {}
NetworkClient::~NetworkClient(){terminate();join();}
void NetworkClient::start(){auto& i=*impl_; if(i.w.active.exchange(true)) return; log(LogLevel::Info,"netucs.network_client","netucs: starting network client"); i.w.thread=std::thread([&i]{i.run();});}
void NetworkClient::main(){start();join();}
void NetworkClient::terminate(){log(LogLevel::Debug,"netucs.network_client","netucs: terminating network client"); impl_->w.stop();}
void NetworkClient::join(){impl_->w.join();}
bool NetworkClient::running() const{return impl_->w.active;}

struct NetworkServer::Impl {
    struct Client {sockaddr_in address{}; double expiration=0, next_send=0, period=1;};
    ServerConfig config;
    Worker w;
    std::mutex mutex;
    std::map<std::string,Client> clients;
    std::deque<Bytes> pending;
    std::atomic<std::uint16_t> seq{0};
    explicit Impl(ServerConfig c):config(std::move(c)){}
    void flush() {
        std::lock_guard<std::mutex> lock(mutex);
        if(!w.active || w.fd<0) return;
        while(!pending.empty()) {
            Bytes data=std::move(pending.front()); pending.pop_front();
            double t=now();
            for(auto it=clients.begin();it!=clients.end();) {
                auto& c=it->second;
                if(c.expiration<=t) {it=clients.erase(it);continue;}
                if(c.next_send<=t) {
                    Bytes pkt; header(pkt,2,seq++); pkt.insert(pkt.end(),data.begin(),data.end());
                    ::sendto(w.fd,pkt.data(),pkt.size(),0,reinterpret_cast<sockaddr*>(&c.address),sizeof(c.address));
                    c.next_send=t+std::max(.0,c.period-1.1);
                }
                ++it;
            }
        }
    }
    void run() {
        try {
            auto local=resolve(config.address,config.port,true);
            w.fd=socket_open(&local);
            log(LogLevel::Info,"netucs.network_server","netucs: UDP server listening");
            w.scheduler.add_task([this]{flush();},periodic(.01,"server_send"));
            w.scheduler.start_engine();
            std::uint8_t buf[65507];
            while(w.active) {
                pollfd pfd{w.fd,POLLIN,0};
                if(::poll(&pfd,1,100)<=0) continue;
                sockaddr_in sender{}; socklen_t sl=sizeof(sender);
                ssize_t n=::recvfrom(w.fd,buf,sizeof(buf),0,reinterpret_cast<sockaddr*>(&sender),&sl);
                if(n!=9 || packet_type(buf,static_cast<std::size_t>(n))!=1) continue;
                Bytes ackpkt; header(ackpkt,99,seq++); ackpkt.push_back(buf[3]);ackpkt.push_back(buf[4]);ackpkt.push_back(0);ackpkt.push_back(0);
                ::sendto(w.fd,ackpkt.data(),ackpkt.size(),0,reinterpret_cast<sockaddr*>(&sender),sizeof(sender));
                std::uint32_t period=(static_cast<std::uint32_t>(buf[5])<<24)|(static_cast<std::uint32_t>(buf[6])<<16)|(buf[7]<<8)|buf[8];
                std::lock_guard<std::mutex> lock(mutex);
                auto& c=clients[key(sender)];c.address=sender;c.expiration=now()+config.client_lifetime;c.period=std::max(1u,period);
                log(LogLevel::Debug,"netucs.network_server","netucs: client registration refreshed");
            }
        } catch(const std::exception& e) {log(LogLevel::Error,"netucs.network_server",std::string("netucs: server worker failed: ")+e.what());w.active=false;}
        catch(...) {log(LogLevel::Error,"netucs.network_server","netucs: server worker failed: unknown error");w.active=false;}
        w.scheduler.stop(); w.active=false;
    }
};
NetworkServer::NetworkServer(ServerConfig c):impl_(new Impl(std::move(c))){}
NetworkServer::~NetworkServer(){terminate();join();}
void NetworkServer::start(){auto& i=*impl_;if(i.w.active.exchange(true)) return;log(LogLevel::Info,"netucs.network_server","netucs: starting network server");i.w.thread=std::thread([&i]{i.run();});}
void NetworkServer::main(){start();join();}
void NetworkServer::terminate(){impl_->w.stop();}
void NetworkServer::join(){impl_->w.join();}
bool NetworkServer::running() const{return impl_->w.active;}
void NetworkServer::publish(Bytes b){if(b.empty() || b.size()>65502) throw std::invalid_argument("Invalid protobuf payload size");auto& i=*impl_;std::lock_guard<std::mutex> lock(i.mutex);i.pending.push_back(std::move(b));}
}

namespace netucs { void NetworkServer::publish_value(const Value& v) { publish(serialize(v)); } }
