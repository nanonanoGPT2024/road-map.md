#pragma once

#include <atomic>
#include <concepts>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <new>
#include <span>
#include <string_view>
#include <sys/mman.h>
#include <sys/stat.h>
#include <system_error>
#include <unistd.h>
#include <utility>

namespace ipc {

// Struktur pesan market telemetry POD (Plain Old Data)
struct alignas(64) MarketTick {
    uint64_t timestamp_ns;
    char symbol[8];
    double bid_price;
    double ask_price;
    uint32_t bid_volume;
    uint32_t ask_volume;
    uint32_t sequence_id;
};
static_assert(std::is_trivially_copyable_v<MarketTick>, "MarketTick harus Trivially Copyable");

// Layout Shared Memory Segment
template <typename T, std::size_t Capacity>
requires (std::is_trivially_copyable_v<T> && ((Capacity & (Capacity - 1)) == 0)) // Wajib power-of-two
struct alignas(64) ShmRingBufferLayout {
    // Cache line isolation untuk menghindari False Sharing lintas CPU core
    alignas(64) std::atomic<std::size_t> write_index{0};
    alignas(64) std::atomic<std::size_t> read_index{0};
    alignas(64) T storage[Capacity];
};

template <typename T, std::size_t Capacity>
class ShmSPSCQueue {
public:
    using Layout = ShmRingBufferLayout<T, Capacity>;

    enum class Mode {
        Producer,
        Consumer
    };

    ShmSPSCQueue(std::string_view shm_name, Mode mode) 
        : name_{shm_name}, mode_{mode} 
    {
        const std::size_t total_size = sizeof(Layout);
        
        int flags = (mode == Mode::Producer) 
                    ? (O_RDWR | O_CREAT | O_CLOEXEC) 
                    : (O_RDWR | O_CLOEXEC);

        shm_fd_ = ::shm_open(name_.data(), flags, S_IRUSR | S_IWUSR);
        if (shm_fd_ < 0) {
            throw std::system_error(errno, std::generic_category(), "shm_open gagal");
        }

        if (mode == Mode::Producer) {
            if (::ftruncate(shm_fd_, static_cast<off_t>(total_size)) != 0) {
                ::close(shm_fd_);
                throw std::system_error(errno, std::generic_category(), "ftruncate gagal");
            }
        }

        void* mapped = ::mmap(nullptr, total_size, PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd_, 0);
        if (mapped == MAP_FAILED) {
            ::close(shm_fd_);
            throw std::system_error(errno, std::generic_category(), "mmap gagal");
        }

        layout_ = static_cast<Layout*>(mapped);

        if (mode == Mode::Producer) {
            // Placement new untuk menginisialisasi atomic state pada proses pertama
            new (&layout_->write_index) std::atomic<std::size_t>(0);
            new (&layout_->read_index) std::atomic<std::size_t>(0);
        }
    }

    ~ShmSPSCQueue() noexcept {
        if (layout_ != nullptr) {
            ::munmap(layout_, sizeof(Layout));
        }
        if (shm_fd_ >= 0) {
            ::close(shm_fd_);
        }
        // Producer menghapus resource dari kernel namespace saat destruct
        if (mode_ == Mode::Producer) {
            ::shm_unlink(name_.data());
        }
    }

    ShmSPSCQueue(const ShmSPSCQueue&) = delete;
    ShmSPSCQueue& operator=(const ShmSPSCQueue&) = delete;

    // Zero-Copy Enqueue (Khusus Producer)
    bool push(const T& item) noexcept {
        const std::size_t current_write = layout_->write_index.load(std::memory_order_relaxed);
        const std::size_t current_read  = layout_->read_index.load(std::memory_order_acquire);

        // Jika buffer penuh (Full)
        if ((current_write - current_read) >= Capacity) {
            return false;
        }

        // Fast bitwise indexing karena Capacity adalah 2^N
        std::size_t slot = current_write & (Capacity - 1);
        std::memcpy(&layout_->storage[slot], &item, sizeof(T));

        // Rilis data ke Consumer menggunakan memory_order_release
        layout_->write_index.store(current_write + 1, std::memory_order_release);
        return true;
    }

    // Zero-Copy Dequeue (Khusus Consumer)
    bool pop(T& item) noexcept {
        const std::size_t current_read  = layout_->read_index.load(std::memory_order_relaxed);
        const std::size_t current_write = layout_->write_index.load(std::memory_order_acquire);

        // Jika buffer kosong (Empty)
        if (current_read == current_write) {
            return false;
        }

        std::size_t slot = current_read & (Capacity - 1);
        std::memcpy(&item, &layout_->storage[slot], sizeof(T));

        // Rilis slot ke Producer
        layout_->read_index.store(current_read + 1, std::memory_order_release);
        return true;
    }

private:
    std::string_view name_;
    Mode mode_;
    int shm_fd_{-1};
    Layout* layout_{nullptr};
};

} // namespace ipc
