#include <iostream>
#include <vector>
#include <memory>
#include <mutex>
#include <cstddef>
#include <cstdint>

class PacketMemoryPool {
public:
    static constexpr std::size_t BLOCK_SIZE = 2048; // 2KB per packet block

    explicit PacketMemoryPool(std::size_t block_count)
        : m_pool_storage(block_count * BLOCK_SIZE),
          m_block_count(block_count) {
        m_free_list.reserve(block_count);
        for (std::size_t i = 0; i < block_count; ++i) {
            m_free_list.push_back(&m_pool_storage[i * BLOCK_SIZE]);
        }
    }

    ~PacketMemoryPool() = default;
    
    // Disable Copying to enforce strict resource identity
    PacketMemoryPool(const PacketMemoryPool&) = delete;
    PacketMemoryPool& operator=(const PacketMemoryPool&) = delete;

    // Custom Deleter Functor
    struct PoolDeleter {
        PacketMemoryPool* pool;

        void operator()(std::byte* ptr) const noexcept {
            if (pool && ptr) {
                pool->return_block(ptr);
            }
        }
    };

    using PacketHandle = std::unique_ptr<std::byte[], PoolDeleter>;

    // Acquire block from pool wrapped in an Exception-Safe RAII Handle
    [[nodiscard]] PacketHandle acquire_packet() {
        std::lock_guard<std::mutex> lock(m_mutex);
        if (m_free_list.empty()) {
            throw std::bad_alloc(); // Pool exhausted
        }

        std::byte* block = m_free_list.back();
        m_free_list.pop_back();

        return PacketHandle(block, PoolDeleter{this});
    }

    [[nodiscard]] std::size_t available_blocks() const noexcept {
        std::lock_guard<std::mutex> lock(m_mutex);
        return m_free_list.size();
    }

private:
    void return_block(std::byte* ptr) noexcept {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_free_list.push_back(ptr);
        // Destructor unik tidak memanggil delete[], melainkan mengembalikan pointer ke pool list
    }

    std::vector<std::byte> m_pool_storage;
    std::vector<std::byte*> m_free_list;
    std::size_t m_block_count;
    mutable std::mutex m_mutex;
};

// Simulasi Konsumsi Network Pipeline
void process_network_frame(PacketMemoryPool& pool, int frame_id) {
    try {
        // Ambil buffer. Jika scope berakhir, Custom Deleter otomatis mengembalikan blok ke pool.
        auto packet = pool.acquire_packet();
        
        // Manipulasi payload buffer
        packet[0] = static_cast<std::byte>(0xAA);
        packet[1] = static_cast<std::byte>(frame_id & 0xFF);

        std::cout << "[Worker] Processed frame " << frame_id 
                  << " at block address: " << static_cast<void*>(packet.get()) 
                  << " | Remaining pool blocks: " << pool.available_blocks() << '\n';

    } catch (const std::bad_alloc&) {
        std::cerr << "[CRITICAL] Packet drop: Pool exhaustion on frame " << frame_id << '\n';
    }
}

int main() {
    constexpr std::size_t TOTAL_BLOCKS = 2;
    PacketMemoryPool network_pool(TOTAL_BLOCKS);

    std::cout << "Initial available blocks: " << network_pool.available_blocks() << "\n\n";

    {
        std::cout << "--- Mengambil 2 Handle Sekaligus ---\n";
        auto packet1 = network_pool.acquire_packet();
        std::cout << "Allocated packet 1. Sisa: " << network_pool.available_blocks() << '\n';

        {
            auto packet2 = network_pool.acquire_packet();
            std::cout << "Allocated packet 2. Sisa: " << network_pool.available_blocks() << '\n';

            // Memaksa eksekusi alokasi ketiga (harus gagal)
            process_network_frame(network_pool, 999);
            std::cout << "Keluar scope internal...\n";
        } // packet2 dihancurkan di sini: Deleter otomatis mengembalikan block ke pool!

        std::cout << "Pasca keluarnya packet2. Sisa: " << network_pool.available_blocks() << '\n';
    } // packet1 dihancurkan di sini.

    std::cout << "Semua resource keluar scope. Sisa pool: " << network_pool.available_blocks() << '\n';

    return 0;
}
