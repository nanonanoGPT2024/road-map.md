#include <iostream>
#include <vector>
#include <memory>
#include <string_view>
#include <chrono>

// Interface Abstraksi Murni (Pure Virtual Interface)
class IOrderProcessor {
public:
    virtual ~IOrderProcessor() = default;

    // Interface contracts
    virtual void validate() const = 0;
    virtual void route_to_exchange(std::string_view exchange_mic) = 0;
    [[nodiscard]] virtual double calculate_margin() const noexcept = 0;
};

// Implementasi Konkret 1: Ekuitas
class EquityOrderProcessor final : public IOrderProcessor {
    uint64_t m_order_id;
    double m_price;
    uint32_t m_shares;

public:
    EquityOrderProcessor(uint64_t id, double price, uint32_t shares) noexcept
        : m_order_id(id), m_price(price), m_shares(shares) {}

    ~EquityOrderProcessor() override = default;

    void validate() const override {
        if (m_shares == 0 || m_price <= 0.0) {
            throw std::invalid_argument("Equity Order: Nilai harga/lot tidak valid");
        }
    }

    void route_to_exchange(std::string_view exchange_mic) override {
        // Simulasi pengiriman data FIX protocol
        std::cout << "[EQUITY] Order " << m_order_id 
                  << " dialihkan ke bursa: " << exchange_mic << '\n';
    }

    [[nodiscard]] double calculate_margin() const noexcept override {
        return m_price * m_shares * 0.20; // 20% margin requirement
    }
};

// Implementasi Konkret 2: Derivatif Futures
class FuturesOrderProcessor final : public IOrderProcessor {
    uint64_t m_order_id;
    double m_contract_price;
    uint32_t m_contracts;
    double m_leverage;

public:
    FuturesOrderProcessor(uint64_t id, double price, uint32_t contracts, double leverage) noexcept
        : m_order_id(id), m_contract_price(price), m_contracts(contracts), m_leverage(leverage) {}

    ~FuturesOrderProcessor() override = default;

    void validate() const override {
        if (m_contracts == 0 || m_leverage < 1.0) {
            throw std::invalid_argument("Futures Order: Kontrak atau leverage tidak valid");
        }
    }

    void route_to_exchange(std::string_view exchange_mic) override {
        std::cout << "[FUTURES] Contract Order " << m_order_id 
                  << " dialihkan ke derivatif: " << exchange_mic << '\n';
    }

    [[nodiscard]] double calculate_margin() const noexcept override {
        return (m_contract_price * m_contracts) / m_leverage;
    }
};

// Engine Eksekusi Gateway
class OrderExecutionGateway {
    std::vector<std::unique_ptr<IOrderProcessor>> m_order_queue;

public:
    void register_order(std::unique_ptr<IOrderProcessor> order) {
        order->validate(); // Dynamic dispatch untuk validasi
        m_order_queue.push_back(std::move(order));
    }

    void execute_all(std::string_view target_mic) {
        std::cout << "\n=== MEMULAI EKSEKUSI BATCH TRANSAKSI ===\n";
        double total_margin = 0.0;

        for (const auto& order : m_order_queue) {
            order->route_to_exchange(target_mic); // Dynamic dispatch vtable
            total_margin += order->calculate_margin();
        }

        std::cout << "Total Margin yang Ditahan: $" << total_margin << '\n';
    }
};

int main() {
    try {
        OrderExecutionGateway gateway;

        // Memasukkan variasi objek polimorfik ke pipeline yang sama
        gateway.register_order(std::make_unique<EquityOrderProcessor>(10101, 150.25, 200));
        gateway.register_order(std::make_unique<FuturesOrderProcessor>(20202, 4500.0, 5, 10.0));
        gateway.register_order(std::make_unique<EquityOrderProcessor>(10102, 2800.50, 15));

        gateway.execute_all("XNAS"); // NASDAQ MIC
    }
    catch (const std::exception& ex) {
        std::cerr << "CRITICAL ERROR: " << ex.what() << '\n';
        return 1;
    }

    return 0;
}
