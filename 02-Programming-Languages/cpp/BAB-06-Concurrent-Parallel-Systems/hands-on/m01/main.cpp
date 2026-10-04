#include <iostream>
#include <vector>
#include <queue>
#include <memory>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <future>
#include <functional>
#include <stdexcept>
#include <new>

// Mengoptimalkan memory boundary untuk mencegah False Sharing
#if defined(__cpp_lib_hardware_interference_size)
    using std::hardware_destructive_interference_size;
#else
    // Default fallback 64 byte untuk arsitektur x86-64 / ARMv8 kontemporer
    constexpr size_t hardware_destructive_interference_size = 64;
#endif

class ThreadPool {
public:
    explicit ThreadPool(size_t thread_count = std::thread::hardware_concurrency());
    
    // Non-copyable & Non-movable untuk integritas resource
    ThreadPool(const ThreadPool&) = delete;
    ThreadPool& operator=(const ThreadPool&) = delete;
    ThreadPool(ThreadPool&&) = delete;
    ThreadPool& operator=(ThreadPool&&) = delete;

    template<class F, class... Args>
    auto enqueue(F&& f, Args&&... args) 
        -> std::future<typename std::invoke_result<F, Args...>::type>;

    ~ThreadPool();

private:
    // Alokasi sebaris cache-line untuk mencegah False Sharing antar pool metadata
    alignas(hardware_destructive_interference_size) struct WorkerState {
        std::vector<std::thread> workers;
        std::queue<std::function<void()>> tasks;
        std::mutex queue_mutex;
        std::condition_variable cv;
        bool stop{false};
    } state_;
};

ThreadPool::ThreadPool(size_t thread_count) {
    if (thread_count == 0) {
        thread_count = 1; // Fallback jika detection hardware_concurrency gagal (return 0)
    }

    state_.workers.reserve(thread_count);
    for (size_t i = 0; i < thread_count; ++i) {
        state_.workers.emplace_back([this]() {
            while (true) {
                std::function<void()> task;
                {
                    std::unique_lock<std::mutex> lock(this->state_.queue_mutex);
                    this->state_.cv.wait(lock, [this]() {
                        return this->state_.stop || !this->state_.tasks.empty();
                    });

                    if (this->state_.stop && this->state_.tasks.empty()) {
                        return; // Terminasi worker secara bersih
                    }

                    task = std::move(this->state_.tasks.front());
                    this->state_.tasks.pop();
                }
                
                // Eksekusi task di luar critical section
                try {
                    task();
                } catch (const std::exception& e) {
                    std::cerr << "[ThreadPool Worker Error]: " << e.what() << "\n";
                } catch (...) {
                    std::cerr << "[ThreadPool Worker Error]: Fatal unknown exception caught\n";
                }
            }
        });
    }
}

template<class F, class... Args>
auto ThreadPool::enqueue(F&& f, Args&&... args) 
    -> std::future<typename std::invoke_result<F, Args...>::type> 
{
    using return_type = typename std::invoke_result<F, Args...>::type;

    // Membungkus callable object ke dalam std::packaged_task melalui heap-pointer (shared_ptr)
    auto task_pkg = std::make_shared<std::packaged_task<return_type()>>(
        std::bind(std::forward<F>(f), std::forward<Args>(args)...)
    );
    
    std::future<return_type> res = task_pkg->get_future();
    {
        std::unique_lock<std::mutex> lock(state_.queue_mutex);
        if (state_.stop) {
            throw std::runtime_error("Submission rejected: ThreadPool is shutting down.");
        }

        // Simpan wrapper lambda yang mengeksekusi packaged_task
        state_.tasks.emplace([task_pkg]() { 
            (*task_pkg)(); 
        });
    }
    state_.cv.notify_one();
    return res;
}

ThreadPool::~ThreadPool() {
    {
        std::unique_lock<std::mutex> lock(state_.queue_mutex);
        state_.stop = true;
    }
    
    state_.cv.notify_all(); // Bangunkan seluruh worker untuk proses flush akhir
    
    for (std::thread& worker : state_.workers) {
        if (worker.joinable()) {
            worker.join();
        }
    }
}

// Driver demonstrasi komputasi konkruen
int main() {
    try {
        ThreadPool pool(4);
        std::vector<std::future<uint64_t>> results;

        std::cout << "[Main] Enqueueing intensive cryptographic tasks...\n";

        for (int i = 0; i < 8; ++i) {
            results.emplace_back(pool.enqueue([i]() -> uint64_t {
                uint64_t accumulator = 0;
                for (uint64_t j = 0; j < 5'000'000; ++j) {
                    accumulator += (j ^ (i + 1));
                }
                return accumulator;
            }));
        }

        for (size_t i = 0; i < results.size(); ++i) {
            std::cout << "[Main] Task #" << i << " Result: " 
                      << results[i].get() << "\n";
        }
    } 
    catch (const std::exception& ex) {
        std::cerr << "[Fatal Exception]: " << ex.what() << "\n";
        return 1;
    }

    std::cout << "[Main] All tasks completed successfully. Pipeline closed.\n";
    return 0;
}
