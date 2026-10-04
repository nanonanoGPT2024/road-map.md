#include <iostream>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <optional>
#include <string>
#include <vector>
#include <chrono>
#include <thread>

// Representasi payload data transaksi trading
struct TradeOrder {
    uint64_t orderId;
    std::string symbol;
    double price;
    uint32_t quantity;
};

// Implementasi Thread-Safe Bounded Queue Production Grade
template <typename T>
class BoundedBlockingQueue {
private:
    std::queue<T> queue_;
    const size_t capacity_;
    mutable std::mutex mtx_;
    std::condition_variable cvNotEmpty_;
    std::condition_variable cvNotFull_;
    bool isShutdown_{false};

public:
    explicit BoundedBlockingQueue(size_t capacity) 
        : capacity_(capacity) {
        if (capacity == 0) {
            throw std::invalid_argument("Kapasitas antrean harus lebih besar dari 0.");
        }
    }

    ~BoundedBlockingQueue() {
        shutdown();
    }

    // Non-copyable, Non-movable untuk integritas sinkronisasi
    BoundedBlockingQueue(const BoundedBlockingQueue&) = delete;
    BoundedBlockingQueue& operator=(const BoundedBlockingQueue&) = delete;
    BoundedBlockingQueue(BoundedBlockingQueue&&) = delete;
    BoundedBlockingQueue& operator=(BoundedBlockingQueue&&) = delete;

    // Produser: Menambahkan item dengan blokade jika antrean penuh
    bool push(T item) {
        std::unique_lock<std::mutex> lock(mtx_);

        // Tunggu hingga antrean memiliki ruang ATAU queue dimatikan
        // cv.wait menerima Lock dan Predicate untuk mencegah spurious wakeups
        cvNotFull_.wait(lock, [this]() {
            return queue_.size() < capacity_ || isShutdown_;
        });

        if (isShutdown_) {
            return false; // Penolakan ingestion saat fase shutdown
        }

        queue_.push(std::move(item));

        // Beri tahu konsumen yang sedang tidur bahwa ada data baru
        lock.unlock(); // Unlock lebih awal sebelum notify untuk menghindari unneeded context switch
        cvNotEmpty_.notify_one();
        return true;
    }

    // Konsumen: Mengambil item dengan blokade jika antrean kosong
    std::optional<T> pop() {
        std::unique_lock<std::mutex> lock(mtx_);

        // Tunggu hingga antrean memiliki item ATAU queue dimatikan
        cvNotEmpty_.wait(lock, [this]() {
            return !queue_.empty() || isShutdown_;
        });

        // Drain mode: Jika shutdown namun queue masih memiliki data, habiskan datanya
        if (queue_.empty() && isShutdown_) {
            return std::nullopt;
        }

        T item = std::move(queue_.front());
        queue_.pop();

        // Beri tahu produser bahwa slot telah tersedia
        lock.unlock();
        cvNotFull_.notify_one();
        return item;
    }

    // Menghentikan antrean secara aman dan membangunkan seluruh thread yang tertahan
    void shutdown() {
        {
            std::lock_guard<std::mutex> lock(mtx_);
            if (isShutdown_) return;
            isShutdown_ = true;
        }
        // Bangunkan semua thread yang menunggu di cvNotFull dan cvNotEmpty
        cvNotEmpty_.notify_all();
        cvNotFull_.notify_all();
    }

    size_t size() const {
        std::lock_guard<std::mutex> lock(mtx_);
        return queue_.size();
    }
};

// Simulasi Pipeline Eksekusi
int main() {
    const size_t QUEUE_CAPACITY = 10;
    BoundedBlockingQueue<TradeOrder> orderQueue(QUEUE_CAPACITY);

    std::cout << "[SYSTEM] Memulai Trading Engine Pipeline...\n";

    // 1. Inisialisasi Consumer Thread (Matching Engine)
    std::jthread consumer([&orderQueue](std::stop_token st) {
        uint64_t processedCount = 0;
        while (!st.stop_requested()) {
            auto orderOpt = orderQueue.pop();
            if (!orderOpt.has_value()) {
                // Queue telah ditutup dan kosong sepenuhnya
                break;
            }

            const auto& order = *orderOpt;
            // Simulasi proses pencocokan order (matching)
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            processedCount++;
            
            if (processedCount % 5 == 0) {
                std::cout << "[ENGINE] Terproses: ID " << order.orderId 
                          << " | " << order.symbol 
                          << " | Qty: " << order.quantity 
                          << " @ $" << order.price << "\n";
            }
        }
        std::cout << "[ENGINE] Consumer selesai. Total order final: " << processedCount << "\n";
    });

    // 2. Inisialisasi Producer Threads (Network Gateways)
    std::vector<std::jthread> producers;
    producers.reserve(3);

    for (int pId = 0; pId < 3; ++pId) {
        producers.emplace_back([&orderQueue, pId]() {
            for (int i = 0; i < 15; ++i) {
                TradeOrder order{
                    .orderId = static_cast<uint64_t>(pId * 1000 + i),
                    .symbol = (pId % 2 == 0) ? "BTC/USD" : "ETH/USD",
                    .price = 50000.0 + (i * 10.5),
                    .quantity = static_cast<uint32_t>((i + 1) * 2)
                };

                if (!orderQueue.push(std::move(order))) {
                    std::cout << "[GATEWAY " << pId << "] Push gagal, antrean dimatikan.\n";
                    break;
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
            }
            std::cout << "[GATEWAY " << pId << "] Selesai mengirim data.\n";
        });
    }

    // Tunggu semua produser selesai mengirim data
    producers.clear(); // Memanggil destruktor jthread -> implicit join()
    std::cout << "[SYSTEM] Semua gateway selesai mengirim order. Menginisiasi shutdown antrean...\n";

    // Shutdown antrean: Izinkan antrean di-drain hingga kosong oleh consumer
    orderQueue.shutdown();

    // Consumer jthread akan selesai membaca sisa order dan exit naturally
    return 0;
}
