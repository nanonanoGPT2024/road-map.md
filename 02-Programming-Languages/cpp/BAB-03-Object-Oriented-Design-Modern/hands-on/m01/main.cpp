#include <iostream>
#include <memory>
#include <string>
#include <vector>
#include <utility>
#include <array>
#include <cstdint>

// ============================================================================
// DOMAIN STRUCTS: Protokol-Protokol Berbeda (Tipe Konkret Independen)
// Perhatikan: Tipe-tipe ini TIDAK mewarisi kelas dasar yang sama!
// ============================================================================

struct FixOrder {
    uint64_t order_id;
    double price;
    uint32_t quantity;

    void process_execution() const {
        std::cout << "[FIX 4.4] Routing Order ID: " << order_id 
                  << " | Prc: " << price << " | Qty: " << quantity << '\n';
    }
};

struct OuchOrder {
    const char* token;
    uint32_t shares;

    void process_execution() const {
        std::cout << "[OUCH Protocol] Fast-Ack Token: " << token 
                  << " | Shares: " << shares << '\n';
    }
};

// ============================================================================
// MODERN TYPE ERASURE WRAPPER: OrderDispatcher
// Bertindak sebagai Value Object yang menyembunyikan detail tipe konkret
// ============================================================================

class OrderDispatcher {
private:
    // 1. Antarmuka Konsep Internal (Abstract Base)
    struct ExecutionConcept {
        virtual ~ExecutionConcept() = default;
        virtual void execute() const = 0;
        virtual std::unique_ptr<ExecutionConcept> clone() const = 0;
    };

    // 2. Model Generik Internal (Menjembatani Tipe Asli dengan Konsep)
    template <typename ConcreteOrderType>
    struct ExecutionModel final : public ExecutionConcept {
        ConcreteOrderType m_data;

        explicit ExecutionModel(ConcreteOrderType data) : m_data(std::move(data)) {}

        void execute() const override {
            m_data.process_execution();
        }

        std::unique_ptr<ExecutionConcept> clone() const override {
            return std::make_unique<ExecutionModel<ConcreteOrderType>>(*this);
        }
    };

    // Storage: Pointer ke antarmuka tersembunyi
    std::unique_ptr<ExecutionConcept> m_concept;

public:
    // Konstruktor Universal: Menerima tipe APA SAJA yang memiliki method process_execution()
    template <typename T>
    OrderDispatcher(T order) 
        : m_concept(std::make_unique<ExecutionModel<T>>(std::move(order))) {}

    // Aturan Lima (Rule of Five) untuk Memastikan Semantik Nilai
    ~OrderDispatcher() = default;
    
    // Copy Constructor: Polimorfisme Deep Copy
    OrderDispatcher(const OrderDispatcher& other) 
        : m_concept(other.m_concept ? other.m_concept->clone() : nullptr) {}

    // Copy Assignment Operator
    OrderDispatcher& operator=(const OrderDispatcher& other) {
        if (this != &other) {
            OrderDispatcher temp(other);
            std::swap(m_concept, temp.m_concept);
        }
        return *this;
    }

    // Move Operations (Default via std::unique_ptr)
    OrderDispatcher(OrderDispatcher&&) noexcept = default;
    OrderDispatcher& operator=(OrderDispatcher&&) noexcept = default;

    // Dispatcher API Utama: Pemanggilan Polimorfik
    void dispatch() const {
        if (m_concept) {
            m_concept->execute();
        }
    }
};

// ============================================================================
// SIMULASI PIPELINE EKSEKUSI
// ============================================================================

int main() {
    // Koleksi nilai heterogen tanpa raw pointers atau deklarasi pointer eksternal
    std::vector<OrderDispatcher> order_queue;

    // Memasukkan tipe konkret yang sama sekali berbeda ke dalam satu kontainer bernilai
    order_queue.emplace_back(FixOrder{10098234, 150.25, 500});
    order_queue.emplace_back(OuchOrder{"NASDAQ-ALPHA-09", 1200});
    order_queue.emplace_back(FixOrder{10098235, 3050.00, 50});

    std::cout << "--- MEMULAI PENGIRIMAN ORDER BATCH --- \n";
    for (const auto& order : order_queue) {
        // Pemanggilan terlihat seperti nilai murni, polimorfisme terjadi di dalam
        order.dispatch();
    }

    // Pembuktian Semantik Nilai (Copyable)
    std::cout << "\n--- MENGUJI SEMANTIK NILAI (COPY) --- \n";
    OrderDispatcher single_order = order_queue[1]; // Salinan penuh, bukan pointer sharing
    single_order.dispatch();

    return 0;
}
