#include <netucs/network.hpp>
#include <atomic>
#include <chrono>
#include <thread>
#include <iostream>
int main() {
    std::atomic<int> received{0};
    netucs::ServerConfig sc; sc.address="127.0.0.1"; sc.port=49281;
    netucs::ClientConfig cc; cc.server_address="127.0.0.1"; cc.server_port=49281;
    cc.client_lifetime=2; cc.client_lifetime_guard=1; cc.acknowledge_timeout=.5;
    netucs::NetworkServer server(sc);
    netucs::NetworkClient client(cc,[&](double,const netucs::Bytes& data){if(data==netucs::Bytes{8,1}) ++received;});
    server.start(); client.start();
    for(int i=0;i<30 && received==0;++i) {
        server.publish({8,1});
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    client.terminate(); server.terminate(); client.join(); server.join();
    std::cout << "received=" << received << '\n';
    return received>0?0:1;
}
