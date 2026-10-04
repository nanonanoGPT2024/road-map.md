#include <iostream>
#include <memory>

class Resource {
public:
    Resource() { std::cout << "[RAII] Resource di-alokasi ke memori heap\n"; }
    ~Resource() { std::cout << "[RAII] Resource otomatis di-dealokasi (No Memory Leak)\n"; }
    void act() { std::cout << "  Sedang mengeksekusi operasi penting...\n"; }
};

int main() {
    std::cout << "=== C++ MODERN MEMORY MANAGEMENT (RAII & SMART POINTERS) ===\n";
    {
        std::unique_ptr<Resource> ptr = std::make_unique<Resource>();
        ptr->act();
    }
    std::cout << "Keluar dari scope. Perhatikan destruktor terpanggil otomatis!\n";
    return 0;
}
