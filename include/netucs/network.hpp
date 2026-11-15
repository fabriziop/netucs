#pragma once
#include <atomic>
#include <cstdint>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

namespace netucs {
struct Value;

constexpr std::uint8_t protocol_version = 3;
using Bytes = std::vector<std::uint8_t>;
enum class LogLevel { Debug=10, Info=20, Warning=30, Error=40 };
using LogCallback = std::function<void(LogLevel, const std::string&, const std::string&)>;
// Callback must be thread-safe; invoked from worker threads.
void set_log_callback(LogCallback callback);
using ReceiveCallback = std::function<void(double, const Bytes&)>;
struct Backoff { double min_period=1, max_period=20, time_constant=2, variance=0.1; };
struct ClientConfig {
    std::string server_address="127.0.0.1";
    std::uint16_t server_port=0;
    double client_lifetime=30, client_lifetime_guard=5, acknowledge_timeout=2;
    Backoff backoff{};
};
struct ServerConfig {
    std::string address="0.0.0.0";
    std::uint16_t port=0;
    double client_lifetime=30;
    Backoff backoff{};
};
class NetworkClient {
public:
    explicit NetworkClient(ClientConfig, ReceiveCallback = {});
    ~NetworkClient();
    NetworkClient(const NetworkClient&)=delete;
    NetworkClient& operator=(const NetworkClient&)=delete;
    void start();
    void main();
    void terminate();
    void shutdown() { terminate(); }
    void join();
    bool running() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
class NetworkServer {
public:
    explicit NetworkServer(ServerConfig);
    ~NetworkServer();
    NetworkServer(const NetworkServer&)=delete;
    NetworkServer& operator=(const NetworkServer&)=delete;
    void start();
    void main();
    void terminate();
    void shutdown() { terminate(); }
    void join();
    bool running() const;
    void publish(Bytes protobuf_payload);
    void publish_value(const Value& value);
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}
