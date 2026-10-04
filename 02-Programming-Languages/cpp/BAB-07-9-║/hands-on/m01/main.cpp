#include <iostream>
#include <vector>
#include <queue>
#include <string>
#include <mutex>
#include <condition_variable>
#include <thread>
#include <chrono>
#include <memory>
#include <sstream>

struct ExecutionReport {
    uint64_t order_id;
    char symbol[8];
    double price;
    uint32_t quantity;
    uint64_t timestamp_ns;
};

class ProductionTelemetrySink {
public:
    explicit ProductionTelemetrySink(size_t max_capacity = 10000)
        : max_capacity_(max_capacity) 
    {
        // Jalankan background worker
        worker_ = std::jthread([this](std::stop_token st) { 
            worker_loop(st); 
        });
    }

    ~ProductionTelemetrySink() {
        // Shutdown kooperatif dan deterministik
        stop_source_.request_stop();
        {
            std::lock_guard<std::mutex> lock(queue_mtx_);
            cv_drain_.notify_all();
        }
        // worker_ jthread akan otomatis me-request stop dan join di sini
    }

    ProductionTelemetrySink(const ProductionTelemetrySink&) = delete;
    ProductionTelemetrySink& operator=(const ProductionTelemetrySink&) = delete;

    bool submit_record(ExecutionReport report) {
        {
            std::lock_guard<std::mutex> lock(queue_mtx_);
            if (buffer_.size() >= max_capacity_) {
                // Backpressure: drop record atau return false untuk alert trading engine
                dropped_events_++;
                return false;
            }
            buffer_.push(report);
        }
        cv_drain_.notify_one();
        return true;
    }

    size_t get_dropped_count() const {
        return dropped_events_.load(std::memory_order_relaxed);
    }

private:
    void worker_loop(std::stop_token st) {
        std::vector<ExecutionReport> batch;
        batch.reserve(512);

        while (!st.stop_requested()) {
            {
                std::unique_lock<std::mutex> lock(queue_mtx_);
                
                // Tunggu sampai ada data ATAU terjadi request stop
                cv_drain_.wait_for(lock, std::chrono::milliseconds(10), [this, &st]() {
                    return !buffer_.empty() || st.stop_requested();
                });

                // Batch drain pattern: Pindahkan seluruh queue ke lokal
                // untuk meminimalkan durasi penahanan lock (Critical Section Minimalization)
                while (!buffer_.empty() && batch.size() < 512) {
                    batch.push_back(buffer_.front());
                    buffer_.pop();
                }
            } // Lock otomatis dilepas di sini!

            if (!batch.empty()) {
                flush_to_underlying_media(batch);
                batch.clear();
            }
        }

        // Drain sisa data sebelum thread benar-benar mati
        drain_remaining();
    }

    void flush_to_underlying_media(const std::vector<ExecutionReport>& batch) {
        // Simulasi penulisan hardware (Disk I/O / Socket)
        // Di sini sama sekali TIDAK ADA penguncian mutex queue_mtx_!
        std::ostringstream ss;
        for (const auto& r : batch) {
            ss << "[SINK-FLUSH] OrderID: " << r.order_id 
               << " | Price: " << r.price 
               << " | Qty: " << r.quantity << "\n";
        }
        std::cout << ss.str();
    }

    void drain_remaining() {
        std::lock_guard<std::mutex> lock(queue_mtx_);
        while (!buffer_.empty()) {
            const auto& r = buffer_.front();
            std::cout << "[FINAL-DRAIN] OrderID: " << r.order_id << "\n";
            buffer_.pop();
        }
    }

    const size_t max_capacity_;
    std::queue<ExecutionReport> buffer_;
    mutable std::mutex queue_mtx_;
    std::condition_variable cv_drain_;
    std::atomic<size_t> dropped_events_{0};
    std::stop_source stop_source_;
    std::jthread worker_;
};

int main() {
    std::cout << "Memulai Production Telemetry System Pipeline...\n";
    ProductionTelemetrySink sink(5000);

    // Simulasi 4 Matching Engine Threads yang memuntahkan report secara masif
    std::vector<std::jthread> matching_cores;
    for (int core_id = 0; core_id < 4; ++core_id) {
        matching_cores.emplace_back([&sink, core_id]() {
            for (int i = 0; i < 50; ++i) {
                ExecutionReport r{
                    .order_id = static_cast<uint64_t>(core_id * 1000 + i),
                    .symbol = "BTCUSDT",
                    .price = 65000.0 + (i * 1.5),
                    .quantity = 2,
                    .timestamp_ns = 1700000000ULL + i
                };
                sink.submit_record(r);
                std::this_thread::sleep_for(std::chrono::microseconds(200));
            }
        });
    }

    // Tunggu semua thread trading core selesai
    matching_cores.clear(); 
    
    std::cout << "Semua Matching Engine Threads selesai. Menunggu Sink shutdown...\n";
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    return 0;
}
