#include <iostream>
#include <string_view>
#include <chrono>
#include <thread>
#include <atomic>
#include <array>
#include <vector>
#include <cstdint>
#include <memory>
#include <span>

#include "SpscRingBuffer.hpp"

// ==========================================
// 1. DOMAIN MODELS (Tightly Packed Structs)
// ==========================================
enum class Side : uint8_t { Buy = 0, Sell = 1 };
enum class OrderType : uint8_t { Limit = 0, Market = 1 };

struct alignas(32) OrderCommand {
    uint64_t order_id{0};
    uint64_t timestamp_ns{0};
    uint32_t instrument_id{0};
    uint32_t quantity{0};
    double   price{0.0};
    Side     side{Side::Buy};
    OrderType type{OrderType::Limit};
    char     padding[6]; // Explicit padding to reach 32 bytes exact
};
static_assert(sizeof(OrderCommand) == 32, "OrderCommand must be exactly 32 bytes.");

struct ExecutionReport {
    uint64_t order_id{0};
    uint64_t match_timestamp_ns{0};
    uint32_t executed_quantity{0};
    double   execution_price{0.0};
    bool     is_filled{false};
};

// ==========================================
// 2. PORTS (C++20 Concepts Definition)
// ==========================================
template <typename T>
concept ExecutionListener = requires(T listener, const ExecutionReport& report) {
    { listener.on_execution(report) } noexcept -> std::same_as<void>;
};

// ==========================================
// 3. ADAPTERS (Outbound Fast Journaler)
// ==========================================
class FastAuditJournaler {
public:
    void on_execution(const ExecutionReport& report) noexcept {
        // Pada skenario produksi nyata: Tulis ke Lock-Free Memory-Mapped File (mmap)
        // Di sini kita catat mutasi tanpa interupsi stream lambat
        sink_executions_count_++;
    }

    [[nodiscard]] size_t total_recorded() const noexcept {
        return sink_executions_count_;
    }

private:
    size_t sink_executions_count_{0};
};
static_assert(ExecutionListener<FastAuditJournaler>);

// ==========================================
// 4. CORE ENGINE (Clean Architecture Domain)
// ==========================================
template <ExecutionListener ListenerAdapter>
class MatchingEngineCore {
public:
    explicit MatchingEngineCore(ListenerAdapter& listener) noexcept
        : listener_(listener) {}

    // Deterministic Hot-path Execution
    void process_command(const OrderCommand& cmd) noexcept {
        // Simulasi internal matching logic
        const uint64_t now = std::chrono::steady_clock::now().time_since_epoch().count();
        
        ExecutionReport report{
            .order_id = cmd.order_id,
            .match_timestamp_ns = now,
            .executed_quantity = cmd.quantity,
            .execution_price = cmd.price,
            .is_filled = true
        };

        // Static dispatch via concept/templates -> Zero runtime overhead
        listener_.on_execution(report);
        processed_count_++;
    }

    [[nodiscard]] size_t get_processed_count() const noexcept {
        return processed_count_;
    }

private:
    ListenerAdapter& listener_;
    size_t processed_count_{0};
};

// ==========================================
// 5. APPLICATION ORCHESTRATOR & BENCHMARK
// ==========================================
constexpr size_t RING_BUFFER_CAPACITY = 1048576; // 2^20 entries (~32 MB preallocated)
constexpr size_t TOTAL_MESSAGES = 2000000;

int main() {
    std::cout << "[Enterprise Capstone] Booting Low-Latency Core...\n";

    // Setup Shared IPC / In-Memory Inter-thread Ring Buffer
    auto inbound_ring_buffer = std::make_unique<SpscRingBuffer<OrderCommand, RING_BUFFER_CAPACITY>>();
    std::atomic<bool> is_running{true};

    FastAuditJournaler journaler_adapter;
    MatchingEngineCore<FastAuditJournaler> engine(journaler_adapter);

    // THREAD 1: Consumer (Domain Engine Core pinned to logical processing)
    std::thread consumer_thread([&]() {
        OrderCommand cmd;
        size_t consumed = 0;

        while (is_running.load(std::memory_order_relaxed) || !inbound_ring_buffer->empty()) {
            if (inbound_ring_buffer->pop(cmd)) {
                engine.process_command(cmd);
                consumed++;
            } else {
                // Yield thread cycle briefly jika buffer kosong
                #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause();
                #elif defined(__aarch64__)
                asm volatile("yield");
                #endif
            }
        }
    });

    // THREAD 2: Producer (Network/Gateway Inbound Adapter simulator)
    std::cout << "[Producer] Emitting " << TOTAL_MESSAGES << " structured orders...\n";
    const auto start_time = std::chrono::high_resolution_clock::now();

    for (uint64_t i = 1; i <= TOTAL_MESSAGES; ++i) {
        OrderCommand cmd{
            .order_id = i,
            .timestamp_ns = static_cast<uint64_t>(i * 100),
            .instrument_id = 42,
            .quantity = 10,
            .price = 1500.50,
            .side = Side::Buy,
            .type = OrderType::Limit,
            .padding = {0}
        };

        // Busy spin jika buffer sementara penuh
        while (!inbound_ring_buffer->emplace(cmd)) {
            #if defined(__x86_64__) || defined(_M_X64)
            __builtin_ia32_pause();
            #elif defined(__aarch64__)
            asm volatile("yield");
            #endif
        }
    }

    // Tunggu data dikuras oleh consumer
    while (!inbound_ring_buffer->empty()) {
        std::this_thread::yield();
    }

    is_running.store(false, std::memory_order_release);
    consumer_thread.join();

    const auto end_time = std::chrono::high_resolution_clock::now();
    const auto duration_us = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time).count();
    const double throughput_ops = (static_cast<double>(TOTAL_MESSAGES) / static_cast<double>(duration_us)) * 1000000.0;

    std::cout << "====================================================\n";
    std::cout << "Execution Completed Successfully.\n";
    std::cout << "Total Processed : " << engine.get_processed_count() << " orders\n";
    std::cout << "Journal Recorded: " << journaler_adapter.total_recorded() << " executions\n";
    std::cout << "Elapsed Time    : " << duration_us << " microseconds\n";
    std::cout << "Throughput      : " << static_cast<uint64_t>(throughput_ops) << " ops/sec\n";
    std::cout << "Average Latency : " << (static_cast<double>(duration_us) * 1000.0 / TOTAL_MESSAGES) << " ns/op\n";
    std::cout << "====================================================\n";

    return 0;
}
