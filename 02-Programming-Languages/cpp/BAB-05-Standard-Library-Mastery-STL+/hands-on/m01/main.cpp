#include <iostream>
#include <memory_resource>
#include <vector>
#include <string_view>
#include <variant>
#include <array>
#include <cstdint>
#include <chrono>

// Definisi berbagai tipe payload
struct Heartbeat { uint64_t timestamp; };
struct TradeExecution { uint64_t trade_id; double price; uint32_t volume; };
struct SystemAlert { int32_t severity; std::string_view message; };

// Variant memori lokal tanpa alokasi heap
using IngressPayload = std::variant<Heartbeat, TradeExecution, SystemAlert>;

struct IngressPacket {
    uint32_t sequence_id;
    IngressPayload payload;
};

// Visitor pattern untuk memproses variant
struct PacketDispatcher {
    void operator()(const Heartbeat& hb) const {
        // Hot-path processing Heartbeat
        (void)hb;
    }
    void operator()(const TradeExecution& tx) const {
        // Hot-path processing Trade
        (void)tx;
    }
    void operator()(const SystemAlert& sa) const {
        std::cout << "[ALERT] Level " << sa.severity << ": " << sa.message << "\n";
    }
};

void run_hot_path_network_ingress() {
    // 1. Siapkan Buffer Memori di Stack sebesar 64 KB
    std::array<std::byte, 65536> stack_buffer;

    // 2. Bungkus ke dalam Monotonic Buffer Resource
    // Jika stack_buffer habis, ia fallback ke null_memory_resource (melempar std::bad_alloc)
    // untuk menjamin TIDAK ADA alokasi heap tersembunyi.
    std::pmr::monotonic_buffer_resource mem_pool(
        stack_buffer.data(), 
        stack_buffer.size(), 
        std::pmr::null_memory_resource()
    );

    // 3. Buat PMR Container yang menggunakan memory resource lokal di atas
    std::pmr::vector<IngressPacket> packet_queue(&mem_pool);
    packet_queue.reserve(1000); // Alokasi instan berbasis pointer-bump dari stack_buffer

    // 4. Simulasi Ingestion Loop
    for (uint32_t i = 0; i < 5; ++i) {
        if (i % 2 == 0) {
            packet_queue.push_back(IngressPacket{
                i, TradeExecution{1000000ULL + i, 4523.50 + i, 100}
            });
        } else {
            packet_queue.push_back(IngressPacket{
                i, SystemAlert{2, "Warning: Latency jitter detected"}
            });
        }
    }

    // 5. Konsumsi antrean menggunakan std::visit (Pattern Matching)
    PacketDispatcher dispatcher;
    for (const auto& packet : packet_queue) {
        std::visit(dispatcher, packet.payload);
    }

    std::cout << "Processed " << packet_queue.size() << " packets entirely on stack memory.\n";
    // Seluruh memori packet_queue dibersihkan instan saat stack unwinds (No OS system call overhead)
}

int main() {
    run_hot_path_network_ingress();
    return 0;
}
