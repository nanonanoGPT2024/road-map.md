# C++ Modern Engineering
## Bab 01 — Fondasi & Ekosistem C++ Modern
### Module 01 — Pengantar C++ Modern dan Lingkungan Pengembangan

---

> **Metadata Modul**
> | Atribut | Nilai |
> |---|---|
> | Kode Modul | CPP-01-01 |
> | Prasyarat | Pemahaman dasar algoritma, logika pemrograman |
> | Durasi Estimasi | 4–6 jam |
> | Tingkat Kesulitan | ⭐☆☆☆☆ Pemula |
> | Standar C++ Target | C++17 / C++20 |
> | Compiler Referensi | GCC 13+, Clang 16+, MSVC 19.3+ |

---

## Daftar Isi

1. [Filosofi dan Sejarah Singkat C++](#s01)
2. [Peta Standar C++: C++11 hingga C++23](#s02)
3. [Arsitektur Toolchain C++ Modern](#s03)
4. [Instalasi GCC/G++ di Linux & Windows (WSL2)](#s04)
5. [Instalasi Clang/LLVM dan MSVC](#s05)
6. [CMake: Build System de facto C++ Modern](#s06)
7. [Konfigurasi VS Code untuk C++ Modern](#s07)
8. [Konfigurasi CLion dan IDE Alternatif](#s08)
9. [Anatomi Program C++ Modern Pertama](#s09)
10. [Sistem Tipe Dasar dan Type Safety](#s10)
11. [Kompilasi, Linking, dan Proses Build](#s11)
12. [Manajemen Paket dengan vcpkg dan Conan](#s12)
13. [Debugging Dasar: GDB, LLDB, dan AddressSanitizer](#s13)
14. [Static Analysis: clang-tidy dan cppcheck](#s14)
15. [Formatting Kode: clang-format dan Konvensi Modern](#s15)
16. [Unit Testing Pertama dengan Catch2](#s16)
17. [Continuous Integration Dasar untuk Proyek C++](#s17)
18. [Pola Kesalahan Umum Pemula C++ Modern](#s18)
19. [Latihan Terstruktur dan Mini-Project](#s19)
20. [Ringkasan, Referensi, dan Peta Jalan Belajar](#s20)

---

<a name="s01"></a>
## Seksi 01 — Filosofi dan Sejarah Singkat C++

### 1.1 Mengapa C++ Masih Relevan di Era Modern?

C++ bukan sekadar bahasa pemrograman tua yang bertahan karena inersia. Ia adalah bahasa yang **secara aktif berevolusi** dengan rilis standar baru setiap tiga tahun. Pada 2024, C++ mendominasi domain-domain berikut:

| Domain | Contoh Sistem Nyata |
|---|---|
| Sistem Operasi & Kernel | Windows NT kernel components, macOS frameworks |
| Game Engine | Unreal Engine 5, id Tech 7, Frostbite |
| Database Engine | MySQL, PostgreSQL, RocksDB, ClickHouse |
| Browser & Runtime | V8 (Chrome), SpiderMonkey (Firefox), WebKit |
| Machine Learning Infra | TensorFlow core, PyTorch C++ backend, ONNX Runtime |
| Embedded & Automotive | AUTOSAR Adaptive Platform, QNX, FreeRTOS C++ layer |
| High-Frequency Trading | Latency-critical matching engines |
| Compiler & Toolchain | LLVM/Clang, GCC, Rust compiler backend |

**Alasan fundamental** C++ tetap dipilih:

1. **Zero-overhead abstraction** — Abstraksi tingkat tinggi tanpa biaya runtime tersembunyi
2. **Deterministic resource management** — Kontrol eksplisit atas memori dan sumber daya
3. **Interoperabilitas C** — Kompatibel dengan ekosistem C yang masif
4. **Portabilitas** — Berjalan di arsitektur dari microcontroller 8-bit hingga supercomputer
5. **Ekosistem matang** — Puluhan tahun library, tool, dan pengetahuan terakumulasi

### 1.2 Garis Waktu Sejarah C++

```
1979  ──► Bjarne Stroustrup mulai mengerjakan "C with Classes" di Bell Labs
          Motivasi: Simulasi sistem terdistribusi (Simula + C)

1983  ──► Nama "C++" diperkenalkan (Rick Mascitti)
          Fitur: class, virtual function, operator overloading, reference

1985  ──► C++ 1.0 dirilis (The C++ Programming Language, edisi pertama)
          Cfront compiler: transpile C++ → C

1989  ──► C++ 2.0: multiple inheritance, abstract class, static member

1998  ──► ISO/IEC 14882:1998 (C++98) — Standar internasional pertama
          STL (Standard Template Library) dari Alexander Stepanov

2003  ──► C++03 — Perbaikan bug minor dari C++98

2011  ──► C++11 ★ REVOLUSI MODERN ★
          auto, lambda, move semantics, smart pointer, thread, range-for

2014  ──► C++14 — Penyempurnaan C++11
          generic lambda, make_unique, relaxed constexpr

2017  ──► C++17 — Fitur produktivitas besar
          structured binding, if constexpr, std::optional, std::variant

2020  ──► C++20 — Fitur terbesar sejak C++11
          concepts, ranges, coroutines, modules, std::format

2023  ──► C++23 — Iterasi dan penyempurnaan
          std::expected, std::mdspan, print/println

2026  ──► C++26 (dalam pengembangan)
          reflection, contracts, executors
```

### 1.3 Filosofi Inti C++ (Bjarne Stroustrup)

> *"C++ is designed to allow you to express ideas directly in code."*
> — Bjarne Stroustrup

Empat prinsip desain yang memandu evolusi C++:

**Prinsip 1: Zero-Overhead Abstraction**
```
"What you don't use, you don't pay for.
 What you do use, you couldn't hand-code any better."
```

**Prinsip 2: Value Semantics**
Objek berperilaku seperti nilai matematika — dapat disalin, dipindahkan, dan dibandingkan secara natural.

**Prinsip 3: Type Safety**
Sistem tipe yang kuat mencegah kesalahan kelas besar pada waktu kompilasi, bukan runtime.

**Prinsip 4: Compatibility**
Kode C yang valid adalah kode C++ yang valid (dengan pengecualian minor yang terdokumentasi).

---

<a name="s02"></a>
## Seksi 02 — Peta Standar C++: C++11 hingga C++23

### 2.1 Mengapa Memahami Versi Standar Itu Penting?

Dalam lingkungan profesional, Anda akan menemukan kode dari berbagai era C++. Kemampuan membaca kode C++98 sambil menulis C++20 adalah keterampilan nyata yang dibutuhkan engineer.

### 2.2 Matriks Fitur per Standar

```
┌─────────────────────────────────────────────────────────────────┐
│                    PETA FITUR C++ MODERN                        │
├──────────┬──────────────────────────────────────────────────────┤
│ STANDAR  │ FITUR KUNCI                                          │
├──────────┼──────────────────────────────────────────────────────┤
│ C++11    │ auto, decltype, nullptr, range-for, lambda           │
│          │ move semantics (&&), rvalue reference                │
│          │ smart pointers (unique_ptr, shared_ptr, weak_ptr)    │
│          │ std::thread, std::mutex, std::atomic                 │
│          │ initializer_list, uniform initialization {}          │
│          │ constexpr (dasar), static_assert                     │
│          │ variadic templates, alias template (using)           │
├──────────┼──────────────────────────────────────────────────────┤
│ C++14    │ generic lambda (auto parameter)                      │
│          │ std::make_unique, binary literal (0b1010)            │
│          │ digit separator (1'000'000)                          │
│          │ relaxed constexpr (loop dalam constexpr)             │
│          │ [[deprecated]] attribute                             │
├──────────┼──────────────────────────────────────────────────────┤
│ C++17    │ structured bindings (auto [x, y] = pair)             │
│          │ if constexpr, if/switch dengan initializer           │
│          │ std::optional, std::variant, std::any                │
│          │ std::string_view, std::filesystem                    │
│          │ fold expressions, class template argument deduction  │
│          │ parallel algorithms (std::execution::par)            │
│          │ [[nodiscard]], [[maybe_unused]], [[fallthrough]]      │
├──────────┼──────────────────────────────────────────────────────┤
│ C++20    │ Concepts & Constraints (requires)                    │
│          │ Ranges library (std::views::filter, transform)       │
│          │ Coroutines (co_await, co_yield, co_return)           │
│          │ Modules (import std;)                                │
│          │ std::format (type-safe formatting)                   │
│          │ Three-way comparison operator <=>                    │
│          │ std::span, std::bit_cast                             │
│          │ Designated initializers, template lambda             │
├──────────┼──────────────────────────────────────────────────────┤
│ C++23    │ std::expected<T, E>                                  │
│          │ std::mdspan (multidimensional span)                  │
│          │ std::print / std::println                            │
│          │ std::flat_map, std::flat_set                         │
│          │ Deducing this (explicit object parameter)            │
│          │ if consteval                                         │
└──────────┴──────────────────────────────────────────────────────┘
```

### 2.3 Strategi Adopsi Standar di Proyek Nyata

```cpp
// ❌ C++98 style — Hindari dalam kode baru
std::vector<int>::iterator it = vec.begin();
for (; it != vec.end(); ++it) {
    std::cout << *it << std::endl;
}

// ✅ C++11 style — Minimum acceptable modern
for (auto& element : vec) {
    std::cout << element << '\n';
}

// ✅✅ C++20 style — Target untuk kode baru
std::ranges::for_each(vec, [](const auto& element) {
    std::cout << element << '\n';
});
```

> **📌 Rekomendasi Kursus Ini:**
> Kode yang ditulis dalam kursus ini menargetkan **C++17 sebagai baseline** dengan fitur C++20 diperkenalkan secara eksplisit saat digunakan. Ini mencerminkan realitas industri 2024.

---

<a name="s03"></a>
## Seksi 03 — Arsitektur Toolchain C++ Modern

### 3.1 Komponen Toolchain

Sebelum menulis satu baris kode pun, pahami **ekosistem alat** yang akan Anda gunakan setiap hari:

```
┌─────────────────────────────────────────────────────────────────┐
│                   TOOLCHAIN C++ MODERN                          │
│                                                                 │
│  Source Code (.cpp, .hpp)                                       │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │ Preprocessor│───►│   Compiler   │───►│     Linker       │   │
│  │ (cpp/clang) │    │ (g++/clang++)│    │ (ld/lld/link.exe)│   │
│  └─────────────┘    └──────────────┘    └──────────────────┘   │
│       │                    │                     │              │
│  Expand macros        .o object files      Executable /        │
│  Include headers      Assembly code        Shared library       │
│  Conditional compile  IR (LLVM)                                 │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   BUILD SYSTEM                           │  │
│  │  CMake ──► Ninja/Make ──► Invokes compiler/linker        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                 QUALITY TOOLS                            │  │
│  │  clang-tidy (linter) │ clang-format (formatter)         │  │
│  │  AddressSanitizer    │ Valgrind (memory checker)         │  │
│  │  cppcheck (static)   │ Catch2/GTest (unit test)          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │               PACKAGE MANAGER                            │  │
│  │  vcpkg (Microsoft) │ Conan (JFrog) │ CPM.cmake           │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Perbandingan Compiler Utama

| Aspek | GCC (g++) | Clang (clang++) | MSVC (cl.exe) |
|---|---|---|---|
| Platform Utama | Linux, Windows (MinGW) | Linux, macOS, Windows | Windows |
| Kecepatan Kompilasi | Sedang | Cepat | Sedang |
| Kualitas Pesan Error | Baik | **Terbaik** | Baik |
| Optimisasi | **Terbaik** | Sangat Baik | Baik |
| Dukungan C++20 | Lengkap (GCC 13+) | Lengkap (Clang 16+) | Lengkap (VS 2022+) |
| Tooling Ekosistem | Luas | **Terluas** (clang-tidy, dll) | Terbatas ke Windows |
| Lisensi | GPL | Apache 2.0 | Proprietary |

### 3.3 Alur Kerja Engineer C++ Modern (Daily Workflow)

```
Edit kode (VS Code / CLion)
    │
    ▼
clang-format otomatis (on save)
    │
    ▼
CMake configure + build (Ninja)
    │
    ├── Build sukses ──► Run unit tests (Catch2/CTest)
    │                        │
    │                        ├── Tests pass ──► git commit
    │                        └── Tests fail ──► Debug (GDB/LLDB)
    │
    └── Build gagal ──► Baca error message Clang
                            │
                            ▼
                       clang-tidy check
                            │
                            ▼
                       Fix & rebuild
```

---

<a name="s04"></a>
## Seksi 04 — Instalasi GCC/G++ di Linux & Windows (WSL2)

### 4.1 Instalasi di Ubuntu/Debian Linux

```bash
# Update package index
sudo apt update && sudo apt upgrade -y

# Install build-essential (GCC, G++, Make, libc-dev)
sudo apt install -y build-essential

# Install GCC versi spesifik (GCC 13 untuk C++23 support)
sudo apt install -y gcc-13 g++-13

# Install tools tambahan
sudo apt install -y cmake ninja-build git curl wget

# Verifikasi instalasi
gcc --version
g++ --version
cmake --version
ninja --version
```

**Output yang diharapkan:**
```
g++ (Ubuntu 13.2.0-4ubuntu3) 13.2.0
Copyright (C) 2023 Free Software Foundation, Inc.
```

### 4.2 Mengelola Multiple Versi GCC dengan update-alternatives

```bash
# Daftarkan GCC 12 dan 13 ke sistem alternatives
sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-12 12
sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-13 13
sudo update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-12 12
sudo update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-13 13

# Pilih versi aktif secara interaktif
sudo update-alternatives --config gcc
sudo update-alternatives --config g++

# Verifikasi versi aktif
g++ --version
```

### 4.3 Setup WSL2 di Windows

```powershell
# Di PowerShell (Run as Administrator)
# Aktifkan WSL2
wsl --install

# Install distribusi Ubuntu 22.04 LTS
wsl --install -d Ubuntu-22.04

# Set WSL2 sebagai default
wsl --set-default-version 2

# Verifikasi
wsl --list --verbose
```

```bash
# Di dalam WSL2 Ubuntu, lanjutkan dengan langkah Linux di atas
sudo apt update && sudo apt install -y build-essential g++-13 cmake ninja-build
```

### 4.4 Verifikasi Instalasi dengan Program Sederhana

```bash
# Buat file test
cat > /tmp/test_compiler.cpp << 'EOF'
#include <iostream>
#include <format>   // C++20
#include <vector>
#include <ranges>   // C++20

int main() {
    // Test C++20 features
    std::vector<int> numbers = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
    
    // Ranges + views (C++20)
    auto even_squares = numbers
        | std::views::filter([](int n) { return n % 2 == 0; })
        | std::views::transform([](int n) { return n * n; });
    
    // std::format (C++20)
    for (auto val : even_squares) {
        std::cout << std::format("Nilai: {:>4}\n", val);
    }
    
    return 0;
}
EOF

# Kompilasi dengan C++20
g++-13 -std=c++20 -Wall -Wextra -o /tmp/test_compiler /tmp/test_compiler.cpp

# Jalankan
/tmp/test_compiler
```

**Output yang diharapkan:**
```
Nilai:    4
Nilai:   16
Nilai:   36
Nilai:   64
Nilai:  100
```

---

<a name="s05"></a>
## Seksi 05 — Instalasi Clang/LLVM dan MSVC

### 5.1 Instalasi Clang di Ubuntu/Debian

```bash
# Metode 1: Dari repository Ubuntu (versi mungkin lebih lama)
sudo apt install -y clang clang-format clang-tidy

# Metode 2: Script resmi LLVM (DIREKOMENDASIKAN — versi terbaru)
wget https://apt.llvm.org/llvm.sh
chmod +x llvm.sh
sudo ./llvm.sh 17   # Install Clang 17

# Install tools LLVM lengkap
sudo apt install -y \
    clang-17 \
    clang-format-17 \
    clang-tidy-17 \
    lldb-17 \
    lld-17 \
    libc++-17-dev \
    libc++abi-17-dev

# Buat symlink untuk kemudahan penggunaan
sudo update-alternatives --install /usr/bin/clang clang /usr/bin/clang-17 100
sudo update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-17 100
sudo update-alternatives --install /usr/bin/clang-format clang-format /usr/bin/clang-format-17 100
sudo update-alternatives --install /usr/bin/clang-tidy clang-tidy /usr/bin/clang-tidy-17 100

# Verifikasi
clang++ --version
clang-format --version
clang-tidy --version
```

### 5.2 Instalasi di macOS

```bash
# Metode 1: Xcode Command Line Tools (Apple Clang)
xcode-select --install

# Metode 2: LLVM via Homebrew (DIREKOMENDASIKAN untuk versi terbaru)
brew install llvm cmake ninja

# Tambahkan ke PATH (tambahkan ke ~/.zshrc atau ~/.bash_profile)
echo 'export PATH="/opt/homebrew/opt/llvm/bin:$PATH"' >> ~/.zshrc
echo 'export LDFLAGS="-L/opt/homebrew/opt/llvm/lib"' >> ~/.zshrc
echo 'export CPPFLAGS="-I/opt/homebrew/opt/llvm/include"' >> ~/.zshrc
source ~/.zshrc

# Verifikasi
clang++ --version
```

### 5.3 Instalasi MSVC (Visual Studio Build Tools)

```powershell
# Download Visual Studio Build Tools 2022
# https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022

# Atau via winget
winget install Microsoft.VisualStudio.2022.BuildTools

# Komponen yang diperlukan (pilih saat instalasi):
# ✅ MSVC v143 - VS 2022 C++ x64/x86 build tools
# ✅ Windows 11 SDK (10.0.22621.0)
# ✅ C++ CMake tools for Windows
# ✅ C++ AddressSanitizer
```

```cmd
:: Verifikasi dari Developer Command Prompt
cl.exe
:: Output: Microsoft (R) C/C++ Optimizing Compiler Version 19.38...

cmake --version
ninja --version
```

### 5.4 Perbandingan Kualitas Pesan Error

Salah satu keunggulan Clang adalah **pesan error yang lebih informatif**:

```cpp
// error_example.cpp — Kode dengan bug tipe
#include <string>
#include <vector>

int main() {
    std::vector<int> v = {1, 2, 3};
    std::string s = v;  // Error: tipe tidak kompatibel
    return 0;
}
```

**GCC Error:**
```
error: conversion from 'std::vector<int>' to non-scalar type 'std::string' requested
```

**Clang Error (lebih informatif):**
```
error: no viable conversion from 'vector<int>' to 'string'
    std::string s = v;
                ^
note: candidate constructor not viable: no known conversion from
      'vector<int>' to 'const string &' for 1st argument
```

---

<a name="s06"></a>
## Seksi 06 — CMake: Build System de facto C++ Modern

### 6.1 Mengapa CMake?

CMake bukan compiler — ia adalah **meta-build system** yang menghasilkan file build untuk sistem lain (Ninja, Make, Visual Studio, Xcode). Ini memungkinkan satu konfigurasi berjalan di semua platform.

```
CMakeLists.txt
     │
     ▼
  cmake (configure)
     │
     ├──► Ninja build files  ──► ninja ──► executable
     ├──► Makefiles          ──► make  ──► executable
     ├──► Visual Studio .sln ──► msbuild ──► executable
     └──► Xcode .xcodeproj  ──► xcodebuild ──► executable
```

### 6.2 Instalasi CMake

```bash
# Ubuntu/Debian
sudo apt install -y cmake

# Atau versi terbaru via pip
pip3 install cmake

# macOS
brew install cmake

# Verifikasi (butuh minimal CMake 3.20)
cmake --version
```

### 6.3 Struktur Proyek C++ Modern yang Direkomendasikan

```
my_project/
├── CMakeLists.txt              # Root CMake configuration
├── cmake/                      # CMake helper modules
│   ├── CompilerWarnings.cmake
│   └── StaticAnalyzers.cmake
├── src/                        # Source files
│   ├── main.cpp
│   └── CMakeLists.txt
├── include/                    # Public headers
│   └── my_project/
│       └── core.hpp
├── lib/                        # Internal libraries
│   ├── math/
│   │   ├── CMakeLists.txt
│   │   ├── math.cpp
│   │   └── math.hpp
│   └── utils/
│       ├── CMakeLists.txt
│       ├── utils.cpp
│       └── utils.hpp
├── tests/                      # Unit tests
│   ├── CMakeLists.txt
│   └── test_math.cpp
├── docs/                       # Documentation
├── .clang-format               # Formatting config
├── .clang-tidy                 # Linting config
└── .gitignore
```

### 6.4 CMakeLists.txt Modern — Root Level

```cmake
# CMakeLists.txt (root)
cmake_minimum_required(VERSION 3.20)

# Deklarasi proyek dengan versi dan bahasa
project(
    MyProject
    VERSION 1.0.0
    DESCRIPTION "Contoh proyek C++ modern"
    LANGUAGES CXX
)

# ─── Pengaturan Standar C++ ───────────────────────────────────────
# Wajib: Gunakan C++17 minimum
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)  # Gunakan standar ISO, bukan ekstensi GCC

# ─── Export compile commands untuk clang-tidy ─────────────────────
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# ─── Build type default ───────────────────────────────────────────
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Debug" CACHE STRING "Build type" FORCE)
endif()

# ─── Warning flags ────────────────────────────────────────────────
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    add_compile_options(
        -Wall           # Warning standar
        -Wextra         # Warning tambahan
        -Wpedantic      # Kepatuhan standar ISO
        -Werror         # Treat warnings as errors (opsional, ketat)
        -Wshadow        # Variabel yang menyembunyikan variabel lain
        -Wnon-virtual-dtor  # Virtual destructor yang hilang
        -Wold-style-cast    # C-style cast
        -Wcast-align        # Cast yang berpotensi alignment issue
        -Wunused            # Variabel/fungsi tidak terpakai
        -Woverloaded-virtual # Virtual function yang tersembunyi
        -Wconversion        # Konversi tipe implisit
        -Wsign-conversion   # Konversi signed/unsigned
    )
elseif(MSVC)
    add_compile_options(/W4 /WX /permissive-)
endif()

# ─── Subdirectories ───────────────────────────────────────────────
add_subdirectory(lib/math)
add_subdirectory(lib/utils)
add_subdirectory(src)

# ─── Testing ──────────────────────────────────────────────────────
option(BUILD_TESTS "Build unit tests" ON)
if(BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()
```

### 6.5 CMakeLists.txt untuk Library Internal

```cmake
# lib/math/CMakeLists.txt

# Buat library (STATIC = .a/.lib, SHARED = .so/.dll, INTERFACE = header-only)
add_library(math_lib STATIC
    math.cpp
)

# Target-based include directories (MODERN WAY)
target_include_directories(math_lib
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
        $<INSTALL_INTERFACE:include>
)

# Properti target
target_compile_features(math_lib PUBLIC cxx_std_17)
```

### 6.6 CMakeLists.txt untuk Executable

```cmake
# src/CMakeLists.txt

add_executable(my_app main.cpp)

# Link ke library internal
target_link_libraries(my_app
    PRIVATE
        math_lib
        utils_lib
)
```

### 6.7 Workflow Build dengan CMake + Ninja

```bash
# ─── Configure ────────────────────────────────────────────────────
# Buat direktori build (JANGAN build di source directory)
cmake -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_CXX_COMPILER=clang++ \
    -DBUILD_TESTS=ON

# ─── Build ────────────────────────────────────────────────────────
cmake --build build --parallel $(nproc)

# ─── Test ─────────────────────────────────────────────────────────
cd build && ctest --output-on-failure

# ─── Release build ────────────────────────────────────────────────
cmake -B build-release -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_COMPILER=clang++

cmake --build build-release --parallel $(nproc)

# ─── Clean ────────────────────────────────────────────────────────
# Cukup hapus direktori build
rm -rf build
```

---

<a name="s07"></a>
## Seksi 07 — Konfigurasi VS Code untuk C++ Modern

### 7.1 Ekstensi yang Diperlukan

```
Extensions yang WAJIB diinstall:
┌─────────────────────────────────────────────────────────────────┐
│ 1. C/C++ (Microsoft)          — IntelliSense, debugging         │
│ 2. CMake Tools (Microsoft)    — CMake integration               │
│ 3. CMake (twxs)               — CMake syntax highlighting       │
│ 4. clangd (LLVM)              — Language server (LEBIH BAIK)    │
│    ⚠️  Nonaktifkan IntelliSense jika pakai clangd               │
└─────────────────────────────────────────────────────────────────┘

Extensions yang SANGAT DIREKOMENDASIKAN:
┌─────────────────────────────────────────────────────────────────┐
│ 5. GitLens                    — Git integration                 │
│ 6. Error Lens                 — Inline error display            │
│ 7. Better C++ Syntax          — Syntax highlighting improved    │
│ 8. Doxygen Documentation      — Doc comment generation          │
│ 9. CodeLLDB                   — LLDB debugger integration       │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Konfigurasi .vscode/settings.json

```json
{
    // ─── Editor ───────────────────────────────────────────────────
    "editor.formatOnSave": true,
    "editor.formatOnType": false,
    "editor.tabSize": 4,
    "editor.insertSpaces": true,
    "editor.rulers": [80, 120],
    "editor.renderWhitespace": "boundary",
    
    // ─── C/C++ Extension ──────────────────────────────────────────
    "C_Cpp.default.cppStandard": "c++17",
    "C_Cpp.default.compilerPath": "/usr/bin/clang++",
    "C_Cpp.default.intelliSenseMode": "linux-clang-x64",
    "C_Cpp.clang_format_style": "file",
    
    // ─── clangd (Language Server) ─────────────────────────────────
    "clangd.path": "/usr/bin/clangd-17",
    "clangd.arguments": [
        "--background-index",
        "--clang-tidy",
        "--header-insertion=iwyu",
        "--completion-style=detailed",
        "--function-arg-placeholders",
        "--fallback-style=llvm",
        "--compile-commands-dir=${workspaceFolder}/build"
    ],
    
    // ─── CMake Tools ──────────────────────────────────────────────
    "cmake.buildDirectory": "${workspaceFolder}/build",
    "cmake.generator": "Ninja",
    "cmake.configureArgs": [
        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"
    ],
    "cmake.buildArgs": ["--parallel"],
    "cmake.ctest.testExplorerIntegration": true,
    
    // ─── File Associations ────────────────────────────────────────
    "files.associations": {
        "*.hpp": "cpp",
        "*.tpp": "cpp",
        "*.ipp": "cpp",
        "CMakeLists.txt": "cmake"
    },
    
    // ─── Exclude dari file explorer ───────────────────────────────
    "files.exclude": {
        "**/build": true,
        "**/.cache": true
    }
}
```

### 7.3 Konfigurasi .vscode/tasks.json

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "CMake: Configure",
            "type": "shell",
            "command": "cmake",
            "args": [
                "-B", "${workspaceFolder}/build",
                "-G", "Ninja",
                "-DCMAKE_BUILD_TYPE=Debug",
                "-DCMAKE_CXX_COMPILER=clang++",
                "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"
            ],
            "group": "build",
            "presentation": {
                "reveal": "always",
                "panel": "shared"
            }
        },
        {
            "label": "CMake: Build",
            "type": "shell",
            "command": "cmake",
            "args": [
                "--build", "${workspaceFolder}/build",
                "--parallel"
            ],
            "group": {
                "kind": "build",
                "isDefault": true
            },
            "dependsOn": "CMake: Configure",
            "presentation": {
                "reveal": "always",
                "panel": "shared"
            },
            "problemMatcher": ["$gcc"]
        },
        {
            "label": "CTest: Run All",
            "type": "shell",
            "command": "ctest",
            "args": [
                "--test-dir", "${workspaceFolder}/build",
                "--output-on-failure",
                "--parallel", "4"
            ],
            "group": "test",
            "dependsOn": "CMake: Build"
        }
    ]
}
```

### 7.4 Konfigurasi .vscode/launch.json (Debugging)

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Debug: my_app (LLDB)",
            "type": "lldb",
            "request": "launch",
            "program": "${workspaceFolder}/build/src/my_app",
            "args": [],
            "cwd": "${workspaceFolder}",
            "preLaunchTask": "CMake: Build",
            "stopAtEntry": false,
            "environment": []
        },
        {
            "name": "Debug: my_app (GDB)",
            "type": "cppdbg",
            "request": "launch",
            "program": "${workspaceFolder}/build/src/my_app",
            "args": [],
            "stopAtEntry": false,
            "cwd": "${workspaceFolder}",
            "environment": [],
            "externalConsole": false,
            "MIMode": "gdb",
            "setupCommands": [
                {
                    "description": "Enable pretty-printing for gdb",
                    "text": "-enable-pretty-printing",
                    "ignoreFailures": true
                }
            ],
            "preLaunchTask": "CMake: Build"
        }
    ]
}
```

---

<a name="s08"></a>
## Seksi 08 — Konfigurasi CLion dan IDE Alternatif

### 8.1 CLion — IDE C++ Terdedikasi dari JetBrains

CLion adalah IDE komersial yang menawarkan pengalaman C++ paling terintegrasi. Tersedia gratis untuk mahasiswa via JetBrains Education.

**Keunggulan CLion:**
- CMake integration native dan mendalam
- Refactoring C++ yang cerdas (rename, extract function, dll)
- Debugger visual yang powerful
- Database tools terintegrasi
- Remote development (SSH, Docker, WSL)

### 8.2 Konfigurasi CMake di CLion

```
File → Settings → Build, Execution, Deployment → CMake

Profile: Debug
  CMake options: -DCMAKE_CXX_COMPILER=clang++ -DBUILD_TESTS=ON
  Build directory: cmake-build-debug
  Generator: Ninja

Profile: Release  
  CMake options: -DCMAKE_CXX_COMPILER=clang++ -DCMAKE_BUILD_TYPE=Release
  Build directory: cmake-build-release
  Generator: Ninja
```

### 8.3 File .editorconfig — Konsistensi Lintas IDE

```ini
# .editorconfig — Berlaku untuk semua IDE yang mendukung EditorConfig
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.{cpp,hpp,h,cc,cxx}]
indent_style = space
indent_size = 4
max_line_length = 120

[CMakeLists.txt]
indent_style = space
indent_size = 4

[*.{json,yaml,yml}]
indent_style = space
indent_size = 2

[Makefile]
indent_style = tab
```

### 8.4 Perbandingan IDE/Editor untuk C++

| Fitur | VS Code + clangd | CLion | Visual Studio | Vim/Neovim + LSP |
|---|---|---|---|---|
| Biaya | Gratis | Berbayar (edu: gratis) | Gratis (Community) | Gratis |
| Platform | Linux/Mac/Win | Linux/Mac/Win | Windows | Linux/Mac/Win |
| CMake Support | Baik | **Terbaik** | Baik | Sedang |
| IntelliSense | Baik (clangd) | **Terbaik** | Baik | Baik (clangd) |
| Debugger | Baik | **Terbaik** | **Terbaik** | Sedang |
| Startup Speed | **Cepat** | Lambat | Lambat | **Tercepat** |
| Kustomisasi | Tinggi | Sedang | Sedang | **Tertinggi** |
| Rekomendasi | Pemula-Menengah | Profesional | Windows-only | Expert |

---

<a name="s09"></a>
## Seksi 09 — Anatomi Program C++ Modern Pertama

### 9.1 Program Hello World yang Sesungguhnya Modern

Mari kita tulis program pertama yang **benar-benar mencerminkan praktik C++ modern**, bukan sekadar `cout << "Hello"`:

```cpp
// src/main.cpp
// ─────────────────────────────────────────────────────────────────
// Program: Hello Modern C++
// Standar: C++17
// Deskripsi: Demonstrasi fitur-fitur dasar C++ modern
// ─────────────────────────────────────────────────────────────────

// ─── Standard Library Includes ───────────────────────────────────
#include <iostream>     // std::cout, std::cin
#include <string>       // std::string
#include <vector>       // std::vector
#include <optional>     // std::optional (C++17)
#include <string_view>  // std::string_view (C++17)
#include <algorithm>    // std::sort, std::find_if
#include <numeric>      // std::accumulate

// ─── Fungsi dengan return type modern ────────────────────────────
// std::optional: fungsi yang mungkin tidak menghasilkan nilai
[[nodiscard]]  // C++17: Caller harus menggunakan return value
std::optional<double> safe_divide(double numerator, double denominator) {
    if (denominator == 0.0) {
        return std::nullopt;  // Tidak ada nilai
    }
    return numerator / denominator;
}

// ─── Fungsi dengan string_view (efisien, tanpa copy) ─────────────
// std::string_view: referensi ke string tanpa ownership
void print_greeting(std::string_view name) {
    std::cout << "Halo, " << name << "! Selamat datang di C++ Modern.\n";
}

// ─── Struct dengan aggregate initialization ───────────────────────
struct Student {
    std::string name;
    int age{};          // Default member initializer (C++11)
    double gpa{0.0};
    
    // Method dengan const correctness
    [[nodiscard]] bool is_honor_student() const {
        return gpa >= 3.5;
    }
};

// ─── Fungsi template sederhana ────────────────────────────────────
template<typename Container>
void print_container(const Container& c, std::string_view label) {
    std::cout << label << ": [";
    bool first = true;
    for (const auto& item : c) {
        if (!first) std::cout << ", ";
        std::cout << item;
        first = false;
    }
    std::cout << "]\n";
}

// ─── Main function ────────────────────────────────────────────────
int main() {
    // ── 1. String dan string_view ──────────────────────────────────
    std::string user_name = "Engineer";
    print_greeting(user_name);           // Tidak ada copy string
    print_greeting("Dunia");             // String literal langsung

    // ── 2. Vector dan range-based for ─────────────────────────────
    std::vector<int> scores = {85, 92, 78, 95, 88, 76, 91};
    print_container(scores, "Nilai awal");

    // ── 3. Lambda dan algoritma ────────────────────────────────────
    // Sort descending menggunakan lambda
    std::sort(scores.begin(), scores.end(),
              [](int a, int b) { return a > b; });
    print_container(scores, "Nilai terurut");

    // ── 4. auto dan type deduction ─────────────────────────────────
    auto total = std::accumulate(scores.begin(), scores.end(), 0);
    auto count = static_cast<double>(scores.size());
    auto average = static_cast<double>(total) / count;
    
    std::cout << "Total: " << total << '\n';
    std::cout << "Rata-rata: " << average << '\n';

    // ── 5. std::optional (C++17) ───────────────────────────────────
    auto result1 = safe_divide(10.0, 3.0);
    auto result2 = safe_divide(10.0, 0.0);

    // Cara idiomatis menggunakan optional
    if (result1) {
        std::cout << "10 / 3 = " << *result1 << '\n';
    }
    
    // value_or: berikan default jika tidak ada nilai
    std::cout << "10 / 0 = " << result2.value_or(0.0) << " (default)\n";

    // ── 6. Structured bindings (C++17) ────────────────────────────
    std::vector<Student> students = {
        {"Alice", 20, 3.8},
        {"Bob",   22, 3.2},
        {"Carol", 21, 3.9},
    };

    std::cout << "\nDaftar Mahasiswa:\n";
    for (const auto& [name, age, gpa] : students) {  // Structured binding
        std::cout << "  " << name 
                  << " (umur " << age << ")"
                  << " GPA: " << gpa;
        if (Student{name, age, gpa}.is_honor_student()) {
            std::cout << " ⭐ Honor Student";
        }
        std::cout << '\n';
    }

    // ── 7. find_if dengan lambda ───────────────────────────────────
    auto honor_it = std::find_if(
        students.begin(), students.end(),
        [](const Student& s) { return s.is_honor_student(); }
    );
    
    if (honor_it != students.end()) {
        std::cout << "\nHonor student pertama: " << honor_it->name << '\n';
    }

    return 0;
}
```

### 9.2 Kompilasi dan Jalankan

```bash
# Kompilasi dengan warning lengkap
clang++ -std=c++17 -Wall -Wextra -Wpedantic \
        -o hello_modern src/main.cpp

# Jalankan
./hello_modern
```

**Output:**
```
Halo, Engineer! Selamat datang di C++ Modern.
Halo, Dunia! Selamat datang di C++ Modern.
Nilai awal: [85, 92, 78, 95, 88, 76, 91]
Nilai terurut: [95, 92, 91, 88, 85, 78, 76]
Total: 605
Rata-rata: 86.4286
10 / 3 = 3.33333
10 / 0 = 0 (default)

Daftar Mahasiswa:
  Alice (umur 20) GPA: 3.8 ⭐ Honor Student
  Bob (umur 22) GPA: 3.2
  Carol (umur 21) GPA: 3.9 ⭐ Honor Student

Honor student pertama: Alice
```

### 9.3 Anatomi File Header C++ Modern

```cpp
// include/my_project/math_utils.hpp
// ─────────────────────────────────────────────────────────────────
// Header guard modern: #pragma once (lebih sederhana dari #ifndef)
#pragma once

// Sertakan hanya yang diperlukan di header
#include <cstddef>      // std::size_t
#include <type_traits>  // std::is_arithmetic_v

// Namespace untuk menghindari name collision
namespace myproject::math {

// ─── Constant expressions ─────────────────────────────────────────
inline constexpr double PI = 3.14159265358979323846;
inline constexpr double E  = 2.71828182845904523536;

// ─── Template function dengan constraint (C++17 SFINAE) ───────────
template<typename T>
// Hanya aktif jika T adalah tipe aritmetik (int, float, double, dll)
std::enable_if_t<std::is_arithmetic_v<T>, T>
clamp(T value, T min_val, T max_val) {
    if (value < min_val) return min_val;
    if (value > max_val) return max_val;
    return value;
}

// ─── Class declaration ────────────────────────────────────────────
class Vector2D {
public:
    // Constructor dengan default arguments
    explicit Vector2D(double x = 0.0, double y = 0.0) noexcept;
    
    // Accessor (const member function)
    [[nodiscard]] double x() const noexcept { return x_; }
    [[nodiscard]] double y() const noexcept { return y_; }
    [[nodiscard]] double magnitude() const noexcept;
    [[nodiscard]] Vector2D normalized() const;
    
    // Operator overloading
    Vector2D operator+(const Vector2D& other) const noexcept;
    Vector2D& operator+=(const Vector2D& other) noexcept;
    bool operator==(const Vector2D& other) const noexcept;
    
    // Friend function untuk output stream
    friend std::ostream& operator<<(std::ostream& os, const Vector2D& v);

private:
    double x_;  // Trailing underscore: konvensi member variable
    double y_;
};

}  // namespace myproject::math
```

---

<a name="s10"></a>
## Seksi 10 — Sistem Tipe Dasar dan Type Safety

### 10.1 Tipe Fundamental C++ Modern

```cpp
#include <cstdint>   // Fixed-width integer types
#include <cstddef>   // std::size_t, std::ptrdiff_t
#include <climits>   // Batas nilai integer
#include <cfloat>    // Batas nilai floating point

// ─── Integer Types ────────────────────────────────────────────────
// ❌ HINDARI: Ukuran bergantung platform
int x;          // Bisa 16, 32, atau 64 bit tergantung platform
long y;         // Bisa 32 atau 64 bit

// ✅ GUNAKAN: Fixed-width types untuk kode yang portable
int8_t   a = -128;          // Tepat 8 bit signed
uint8_t  b = 255;           // Tepat 8 bit unsigned
int16_t  c = -32768;        // Tepat 16 bit signed
uint16_t d = 65535;         // Tepat 16 bit unsigned
int32_t  e = -2147483648;   // Tepat 32 bit signed
uint32_t f = 4294967295U;   // Tepat 32 bit unsigned
int64_t  g = -9223372036854775807LL;  // Tepat 64 bit signed
uint64_t h = 18446744073709551615ULL; // Tepat 64 bit unsigned

// ─── Tipe untuk ukuran dan indeks ─────────────────────────────────
std::size_t    size = 42;       // Unsigned, untuk ukuran container
std::ptrdiff_t diff = -5;       // Signed, untuk perbedaan pointer

// ─── Floating Point ───────────────────────────────────────────────
float       f32 = 3.14f;        // 32-bit, ~7 digit presisi
double      f64 = 3.14159265;   // 64-bit, ~15 digit presisi (DEFAULT)
long double f80 = 3.14159265L;  // 80/128-bit, platform-dependent

// ─── Boolean ──────────────────────────────────────────────────────
bool flag = true;   // true atau false (bukan 1 atau 0)

// ─── Character Types ──────────────────────────────────────────────
char     c1 = 'A';          // 8-bit, signed atau unsigned (impl-defined)
char8_t  c2 = u8'A';        // C++20: UTF-8 character
char16_t c3 = u'A';         // UTF-16 character
char32_t c4 = U'A';         // UTF-32 character
wchar_t  c5 = L'A';         // Wide character (platform-dependent)
```

### 10.2 Type Deduction dengan auto

```cpp
// ─── auto: Compiler menentukan tipe ──────────────────────────────
auto i = 42;            // int
auto d = 3.14;          // double
auto f = 3.14f;         // float
auto s = std::string{"hello"};  // std::string
auto v = std::vector<int>{1, 2, 3};  // std::vector<int>

// ─── auto dengan referensi ────────────────────────────────────────
std::vector<std::string> names = {"Alice", "Bob"};

auto  copy = names[0];   // std::string (COPY — mungkin tidak diinginkan)
auto& ref  = names[0];   // std::string& (referensi — efisien)
const auto& cref = names[0];  // const std::string& (read-only referensi)

// ─── Kapan TIDAK menggunakan auto ─────────────────────────────────
// ❌ Tipe tidak jelas dari konteks
auto result = compute();  // Apa tipe return compute()?

// ✅ Lebih jelas dengan tipe eksplisit
double result2 = compute();

// ✅ auto baik saat tipe jelas atau verbose
auto it = std::find(v.begin(), v.end(), 42);  // Lebih baik dari iterator verbose
auto [key, value] = some_map.find("key");     // Structured binding
```

### 10.3 Konversi Tipe yang Aman

```cpp
// ─── C-style cast: HINDARI ────────────────────────────────────────
double d = 3.14;
int i = (int)d;  // ❌ Tidak aman, tidak jelas maksudnya

// ─── C++ named casts: GUNAKAN ─────────────────────────────────────

// static_cast: Konversi yang well-defined dan diperiksa compiler
int i2 = static_cast<int>(d);          // ✅ Truncate double ke int
double ratio = static_cast<double>(7) / 3;  // ✅ Integer division → float

// const_cast: Hanya untuk menambah/menghapus const
// (Gunakan sangat jarang, biasanya tanda desain yang buruk)
const int ci = 42;
int* pi = const_cast<int*>(&ci);  // ⚠️ Undefined behavior jika dimodifikasi

// reinterpret_cast: Reinterpretasi bit mentah
// (Sangat jarang, hanya untuk low-level programming)
uint64_t bits = reinterpret_cast<uint64_t>(some_pointer);  // ⚠️

// dynamic_cast: Downcasting yang aman (runtime check)
// (Dibahas di modul OOP)
```

### 10.4 Literal Modern

```cpp
// ─── Integer literals ─────────────────────────────────────────────
int decimal     = 1'000'000;    // C++14: digit separator
int hex         = 0xFF'FF'FF;   // Hexadecimal
int octal       = 0755;         // Octal
int binary      = 0b1010'1010;  // C++14: binary literal

// ─── Floating point literals ──────────────────────────────────────
double d1 = 1.5e10;     // Scientific notation
double d2 = 0x1.8p+1;   // Hexadecimal floating point (C++17)

// ─── String literals ──────────────────────────────────────────────
const char* s1 = "Hello\nWorld";          // Escape sequences
const char* s2 = R"(Hello\nWorld)";       // Raw string (C++11): \n literal
const char* s3 = R"delimiter(
    Multi-line
    raw string
)delimiter";

// ─── User-defined literals (C++11) ────────────────────────────────
using namespace std::literals;
auto str  = "hello"s;       // std::string
auto sv   = "hello"sv;      // std::string_view (C++17)
auto dur  = 100ms;          // std::chrono::milliseconds
auto dur2 = 2.5s;           // std::chrono::duration<double>
```

### 10.5 nullptr vs NULL vs 0

```cpp
// ─── Pointer null: SELALU gunakan nullptr ─────────────────────────
int* p1 = nullptr;   // ✅ C++11: Type-safe null pointer
int* p2 = NULL;      // ⚠️ C-style: Macro, bisa jadi int 0
int* p3 = 0;         // ❌ Ambigu: integer atau pointer?

// Mengapa nullptr lebih baik:
void foo(int x)    { std::cout << "int version\n"; }
void foo(int* ptr) { std::cout << "pointer version\n"; }

foo(0);       // Memanggil foo(int) — mungkin tidak diinginkan!
foo(NULL);    // Memanggil foo(int) — SALAH jika ingin pointer!
foo(nullptr); // ✅ Memanggil foo(int*) — benar

// Cek null pointer
if (p1 != nullptr) { /* ... */ }  // Eksplisit
if (p1)            { /* ... */ }  // Idiomatis (sama)
```

---

<a name="s11"></a>
## Seksi 11 — Kompilasi, Linking, dan Proses Build

### 11.1 Tahapan Kompilasi C++ Secara Detail

```
SOURCE FILE (.cpp)
      │
      ▼ Tahap 1: PREPROCESSING
      │  • Ekspansi #include
      │  • Ekspansi #define macro
      │  • Evaluasi #ifdef/#ifndef
      │  • Hapus komentar
      │
TRANSLATION UNIT (kode C++ murni, tanpa direktif preprocessor)
      │
      ▼ Tahap 2: COMPILATION
      │  • Lexical analysis (tokenisasi)
      │  • Syntax analysis (parsing → AST)
      │  • Semantic analysis (type checking)
      │  • Optimization (berbagai level)
      │  • Code generation
      │
OBJECT FILE (.o / .obj)
      │
      ▼ Tahap 3: LINKING
      │  • Resolve symbol references
      │  • Gabungkan object files
      │  • Link dengan libraries (.a, .so, .lib, .dll)
      │  • Generate executable atau library
      │
EXECUTABLE / LIBRARY
```

### 11.2 Melihat Setiap Tahap Secara Manual

```bash
# ─── Tahap 1: Preprocessing saja ─────────────────────────────────
clang++ -E -std=c++17 main.cpp -o main.preprocessed
# Lihat output: file besar berisi semua header yang di-include

# ─── Tahap 2: Kompilasi ke assembly ──────────────────────────────
clang++ -S -std=c++17 -O2 main.cpp -o main.s
cat main.s  # Lihat assembly code

# ─── Tahap 3: Kompilasi ke object file ───────────────────────────
clang++ -c -std=c++17 main.cpp -o main.o
file main.o  # ELF 64-bit LSB relocatable object

# ─── Tahap 4: Linking ─────────────────────────────────────────────
clang++ main.o -o my_program

# ─── Semua tahap sekaligus (normal) ──────────────────────────────
clang++ -std=c++17 main.cpp -o my_program
```

### 11.3 Optimization Levels

```bash
# -O0: Tanpa optimisasi (default Debug) — kompilasi cepat, debug mudah
clang++ -O0 -g -std=c++17 main.cpp -o debug_build

# -O1: Optimisasi dasar — keseimbangan
clang++ -O1 -std=c++17 main.cpp -o o1_build

# -O2: Optimisasi standar (DIREKOMENDASIKAN untuk Release)
clang++ -O2 -std=c++17 main.cpp -o o2_build

# -O3: Optimisasi agresif — mungkin lebih lambat karena code size
clang++ -O3 -std=c++17 main.cpp -o o3_build

# -Os: Optimisasi untuk ukuran binary (embedded systems)
clang++ -Os -std=c++17 main.cpp -o os_build

# -Oz: Optimisasi ukuran agresif (Clang only)
clang++ -Oz -std=c++17 main.cpp -o oz_build

# -g: Sertakan debug symbols (bisa dikombinasikan dengan -O)
clang++ -O2 -g -std=c++17 main.cpp -o release_with_debug
```

### 11.4 Static vs Dynamic Linking

```bash
# ─── Membuat static library (.a) ─────────────────────────────────
clang++ -c -std=c++17 math.cpp -o math.o
ar rcs libmath.a math.o          # Buat static library

# Link dengan static library
clang++ -std=c++17 main.cpp -L. -lmath -o my_app_static
# Hasil: binary besar, tidak perlu libmath.a saat runtime

# ─── Membuat shared library (.so) ────────────────────────────────
clang++ -c -fPIC -std=c++17 math.cpp -o math_pic.o
clang++ -shared -o libmath.so math_pic.o  # Buat shared library

# Link dengan shared library
clang++ -std=c++17 main.cpp -L. -lmath -o my_app_dynamic
# Hasil: binary kecil, butuh libmath.so saat runtime

# Jalankan dengan shared library di direktori saat ini
LD_LIBRARY_PATH=. ./my_app_dynamic
```

### 11.5 Memahami Linker Errors

```cpp
// math.hpp
#pragma once
int add(int a, int b);  // Deklarasi

// math.cpp
#include "math.hpp"
int add(int a, int b) { return a + b; }  // Definisi

// main.cpp
#include "math.hpp"
int main() {
    return add(1, 2);  // Penggunaan
}
```

```bash
# ❌ Lupa link math.cpp → Linker error
clang++ -std=c++17 main.cpp -o app
# error: undefined reference to `add(int, int)'

# ✅ Link semua file yang diperlukan
clang++ -std=c++17 main.cpp math.cpp -o app
```

**Jenis Linker Error Umum:**

| Error | Penyebab | Solusi |
|---|---|---|
| `undefined reference to 'foo'` | Fungsi dideklarasikan tapi tidak didefinisikan/dilink | Tambahkan file .cpp atau -l flag |
| `multiple definition of 'foo'` | Fungsi didefinisikan di header tanpa `inline` | Tambahkan `inline` atau pindah ke .cpp |
| `undefined reference to 'vtable for Foo'` | Virtual function tidak diimplementasikan | Implementasikan semua pure virtual |

---

<a name="s12"></a>
## Seksi 12 — Manajemen Paket dengan vcpkg dan Conan

### 12.1 Mengapa Package Manager Diperlukan?

Tanpa package manager, menambahkan library eksternal ke proyek C++ adalah proses manual yang menyakitkan:
1. Download source code library
2. Kompilasi library
3. Salin header ke direktori include
4. Salin library ke direktori lib
5. Update CMakeLists.txt
6. Ulangi untuk setiap platform

Package manager mengotomatiskan semua ini.

### 12.2 vcpkg — Package Manager dari Microsoft

```bash
# ─── Instalasi vcpkg ──────────────────────────────────────────────
git clone https://github.com/microsoft/vcpkg.git ~/vcpkg
cd ~/vcpkg
./bootstrap-vcpkg.sh  # Linux/macOS
# atau: bootstrap-vcpkg.bat  # Windows

# Tambahkan ke PATH (tambahkan ke ~/.bashrc atau ~/.zshrc)
export VCPKG_ROOT="$HOME/vcpkg"
export PATH="$VCPKG_ROOT:$PATH"

# ─── Instalasi library ────────────────────────────────────────────
vcpkg install fmt           # {fmt} library
vcpkg install catch2        # Catch2 testing framework
vcpkg install nlohmann-json # JSON library
vcpkg install boost-algorithm boost-filesystem  # Boost components
vcpkg install spdlog        # Fast logging library
vcpkg install eigen3        # Linear algebra library

# ─── Integrasi dengan CMake ───────────────────────────────────────
# Tambahkan toolchain file saat configure
cmake -B build \
    -DCMAKE_TOOLCHAIN_FILE="$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake" \
    -G Ninja
```

### 12.3 vcpkg Manifest Mode (Direkomendasikan)

```json
// vcpkg.json — Taruh di root proyek
{
    "name": "my-project",
    "version": "1.0.0",
    "dependencies": [
        "fmt",
        "catch2",
        "nlohmann-json",
        {
            "name": "boost-filesystem",
            "version>=": "1.83.0"
        },
        "spdlog"
    ],
    "builtin-baseline": "2024.01.12"
}
```

```cmake
# CMakeLists.txt — Gunakan library yang diinstall vcpkg
find_package(fmt CONFIG REQUIRED)
find_package(Catch2 3 REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)
find_package(spdlog CONFIG REQUIRED)

target_link_libraries(my_app
    PRIVATE
        fmt::fmt
        nlohmann_json::nlohmann_json
        spdlog::spdlog
)

target_link_libraries(my_tests
    PRIVATE
        Catch2::Catch2WithMain
)
```

### 12.4 Contoh Penggunaan Library via vcpkg

```cpp
// Menggunakan {fmt} library (lebih baik dari printf/cout)
#include <fmt/core.h>
#include <fmt/ranges.h>
#include <nlohmann/json.hpp>
#include <spdlog/spdlog.h>

int main() {
    // ─── fmt: Type-safe formatting ────────────────────────────────
    fmt::print("Halo, {}!\n", "Dunia");
    fmt::print("Pi ≈ {:.4f}\n", 3.14159265);
    
    std::vector<int> v = {1, 2, 3, 4, 5};
    fmt::print("Vector: {}\n", v);  // Langsung print container!
    
    // ─── spdlog: Structured logging ───────────────────────────────
    spdlog::info("Aplikasi dimulai");
    spdlog::warn("Ini adalah peringatan: {}", 42);
    spdlog::error("Error terjadi: {}", "file not found");
    
    // ─── nlohmann/json: JSON parsing ──────────────────────────────
    using json = nlohmann::json;
    
    json config = {
        {"name", "MyApp"},
        {"version", 1},
        {"features", {"logging", "networking", "database"}},
        {"settings", {
            {"debug", true},
            {"max_connections", 100}
        }}
    };
    
    // Serialize ke string
    std::string json_str = config.dump(4);  // 4-space indent
    fmt::print("Config JSON:\n{}\n", json_str);
    
    // Akses nilai
    fmt::print("App name: {}\n", config["name"].get<std::string>());
    fmt::print("Debug mode: {}\n", config["settings"]["debug"].get<bool>());
    
    return 0;
}
```

### 12.5 Conan — Alternatif Package Manager

```bash
# Instalasi Conan
pip3 install conan

# Buat profil default
conan profile detect --force
```

```ini
# conanfile.txt
[requires]
fmt/10.1.1
catch2/3.4.0
nlohmann_json/3.11.2

[generators]
CMakeDeps
CMakeToolchain

[layout]
cmake_layout
```

```bash
# Install dependencies
conan install . --output-folder=build --build=missing

# Configure CMake dengan Conan toolchain
cmake -B build \
    -DCMAKE_TOOLCHAIN_FILE=build/conan_toolchain.cmake \
    -DCMAKE_BUILD_TYPE=Release
```

---

<a name="s13"></a>
## Seksi 13 — Debugging Dasar: GDB, LLDB, dan AddressSanitizer

### 13.1 Kompilasi untuk Debugging

```bash
# Selalu kompilasi dengan -g untuk debug symbols
# -O0: Tanpa optimisasi (variabel tidak di-optimize away)
# -g3: Level debug info maksimum (termasuk macro)
clang++ -std=c++17 -O0 -g3 -fsanitize=address,undefined \
        main.cpp -o debug_app
```

### 13.2 GDB — GNU Debugger

```bash
# Mulai GDB
gdb ./debug_app

# ─── Perintah GDB Esensial ────────────────────────────────────────
(gdb) run                    # Jalankan program
(gdb) run arg1 arg2          # Jalankan dengan argumen

# Breakpoints
(gdb) break main             # Breakpoint di fungsi main
(gdb) break math.cpp:42      # Breakpoint di file:baris
(gdb) break MyClass::method  # Breakpoint di method
(gdb) info breakpoints       # Lihat semua breakpoints
(gdb) delete 1               # Hapus breakpoint #1

# Eksekusi
(gdb) next    # (n) Eksekusi baris berikutnya (step over)
(gdb) step    # (s) Masuk ke dalam fungsi (step into)
(gdb) finish  # Eksekusi sampai keluar dari fungsi saat ini
(gdb) continue # (c) Lanjutkan eksekusi sampai breakpoint berikutnya

# Inspeksi variabel
(gdb) print variable_name    # Cetak nilai variabel
(gdb) print *pointer         # Dereference pointer
(gdb) print vec              # Cetak vector (dengan pretty-printer)
(gdb) display counter        # Auto-print setiap step
(gdb) info locals            # Semua variabel lokal
(gdb) info args              # Argumen fungsi saat ini

# Stack
(gdb) backtrace  # (bt) Lihat call stack
(gdb) frame 2    # Pindah ke frame #2
(gdb) up / down  # Naik/turun satu frame

# Keluar
(gdb) quit
```

### 13.3 LLDB — LLVM Debugger

```bash
# Mulai LLDB
lldb ./debug_app

# ─── Perintah LLDB Esensial ───────────────────────────────────────
(lldb) run                           # Jalankan program
(lldb) process launch -- arg1 arg2   # Jalankan dengan argumen

# Breakpoints
(lldb) breakpoint set --name main           # Breakpoint di fungsi
(lldb) breakpoint set --file math.cpp --line 42  # File:baris
(lldb) breakpoint list                      # Lihat breakpoints
(lldb) breakpoint delete 1                  # Hapus breakpoint

# Eksekusi
(lldb) next      # Step over
(lldb) step      # Step into
(lldb) finish    # Step out
(lldb) continue  # Continue

# Inspeksi
(lldb) frame variable                # Semua variabel lokal
(lldb) frame variable my_var         # Variabel spesifik
(lldb) print my_var                  # Print variabel
(lldb) po my_object                  # Print object (menggunakan description)

# Stack
(lldb) thread backtrace  # Call stack
(lldb) frame select 2    # Pilih frame

# Keluar
(lldb) quit
```

### 13.4 AddressSanitizer (ASan) — Deteksi Memory Bugs

AddressSanitizer adalah tool yang **sangat powerful** untuk mendeteksi bug memori saat runtime:

```cpp
// bugs_demo.cpp — Kode dengan berbagai memory bugs
#include <iostream>
#include <vector>

void heap_buffer_overflow() {
    int* arr = new int[5];
    arr[10] = 42;  // ❌ Buffer overflow: akses di luar batas
    delete[] arr;
}

void use_after_free() {
    int* p = new int(42);
    delete p;
    std::cout << *p << '\n';  // ❌ Use-after-free
}

void stack_buffer_overflow() {
    int arr[5];
    arr[10] = 42;  // ❌ Stack buffer overflow
}

void memory_leak() {
    int* p = new int(42);
    // ❌ Lupa delete p — memory leak
}

int main() {
    heap_buffer_overflow();
    return 0;
}
```

```bash
# Kompilasi dengan AddressSanitizer
clang++ -std=c++17 -fsanitize=address -fno-omit-frame-pointer \
        -g -O1 bugs_demo.cpp -o bugs_demo

# Jalankan — ASan akan mendeteksi dan melaporkan bug
./bugs_demo
```

**Output ASan (sangat informatif):**
```
=================================================================
==12345==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x...
READ of size 4 at 0x... thread T0
    #0 0x... in heap_buffer_overflow bugs_demo.cpp:6
    #1 0x... in main bugs_demo.cpp:24

0x... is located 20 bytes to the right of 20-byte region [0x...,0x...)
allocated by thread T0 here:
    #0 0x... in operator new[](unsigned long)
    #1 0x... in heap_buffer_overflow bugs_demo.cpp:5
```

### 13.5 Sanitizer Lainnya

```bash
# UndefinedBehaviorSanitizer (UBSan)
clang++ -fsanitize=undefined -g main.cpp -o app_ubsan

# ThreadSanitizer (TSan) — Deteksi data race
clang++ -fsanitize=thread -g main.cpp -o app_tsan

# MemorySanitizer (MSan) — Deteksi uninitialized reads
clang++ -fsanitize=memory -g main.cpp -o app_msan

# Kombinasi ASan + UBSan (paling umum untuk development)
clang++ -fsanitize=address,undefined -g -O1 main.cpp -o app_sanitized
```

---

<a name="s14"></a>
## Seksi 14 — Static Analysis: clang-tidy dan cppcheck

### 14.1 clang-tidy — Linter C++ Berbasis LLVM

clang-tidy menganalisis kode **tanpa menjalankannya** dan mendeteksi pola kode yang bermasalah.

### 14.2 File Konfigurasi .clang-tidy

```yaml
# .clang-tidy — Taruh di root proyek
---
Checks: >
  -*,
  bugprone-*,
  clang-analyzer-*,
  cppcoreguidelines-*,
  modernize-*,
  performance-*,
  portability-*,
  readability-*,
  -modernize-use-trailing-return-type,
  -cppcoreguidelines-avoid-magic-numbers,
  -readability-magic-numbers,
  -cppcoreguidelines-pro-bounds-array-to-pointer-decay,
  -cppcoreguidelines-pro-type-vararg

WarningsAsErrors: ''

HeaderFilterRegex: '.*'

CheckOptions:
  - key: readability-identifier-naming.ClassCase
    value: CamelCase
  - key: readability-identifier-naming.FunctionCase
    value: lower_case
  - key: readability-identifier-naming.VariableCase
    value: lower_case
  - key: readability-identifier-naming.MemberCase
    value: lower_case
  - key: readability-identifier-naming.MemberSuffix
    value: '_'
  - key: readability-identifier-naming.ConstantCase
    value: UPPER_CASE
  - key: modernize-use-default-member-init.UseAssignment
    value: '0'
  - key: cppcoreguidelines-special-member-functions.AllowSoleDefaultDtor
    value: '1'
```

### 14.3 Menjalankan clang-tidy

```bash
# Jalankan pada satu file
clang-tidy src/main.cpp -- -std=c++17

# Jalankan dengan compile_commands.json (DIREKOMENDASIKAN)
# Pastikan CMAKE_EXPORT_COMPILE_COMMANDS=ON
clang-tidy -p build src/main.cpp

# Jalankan pada semua file proyek
find src lib -name "*.cpp" | \
    xargs clang-tidy -p build

# Auto-fix masalah yang bisa diperbaiki otomatis
clang-tidy -p build --fix src/main.cpp

# Jalankan via CMake (dengan cmake-tidy target)
cmake --build build --target clang-tidy
```

### 14.4 Contoh Deteksi clang-tidy

```cpp
// problematic_code.cpp
#include <iostream>
#include <vector>
#include <memory>

class Resource {
public:
    Resource() { data_ = new int[100]; }
    ~Resource() { delete[] data_; }
    // ❌ clang-tidy: cppcoreguidelines-special-member-functions
    // Missing copy constructor, copy assignment, move constructor, move assignment
    
private:
    int* data_;
};

void old_style_code() {
    // ❌ modernize-use-nullptr
    int* p = NULL;
    
    // ❌ modernize-use-auto
    std::vector<int>::iterator it = std::vector<int>().begin();
    
    // ❌ performance-unnecessary-copy-initialization
    std::vector<int> v = {1, 2, 3};
    for (std::vector<int>::iterator i = v.begin(); i != v.end(); ++i) {
        // ❌ modernize-loop-convert: gunakan range-for
        std::cout << *i << '\n';
    }
    
    // ❌ cppcoreguidelines-owning-memory
    int* raw = new int(42);
    // Tidak ada delete!
}

// ✅ Versi yang diperbaiki
void modern_code() {
    int* p = nullptr;  // ✅
    
    std::vector<int> v = {1, 2, 3};
    for (const auto& item : v) {  // ✅ range-for
        std::cout << item << '\n';
    }
    
    auto managed = std::make_unique<int>(42);  // ✅ RAII
}
```

### 14.5 cppcheck — Static Analyzer Alternatif

```bash
# Instalasi
sudo apt install -y cppcheck

# Jalankan analisis
cppcheck --enable=all \
         --std=c++17 \
         --suppress=missingIncludeSystem \
         --error-exitcode=1 \
         src/ lib/

# Output ke XML untuk CI
cppcheck --enable=all \
         --std=c++17 \
         --xml \
         src/ 2> cppcheck_report.xml

# Dengan compile database
cppcheck --project=build/compile_commands.json \
         --enable=all \
         --std=c++17
```

---

<a name="s15"></a>
## Seksi 15 — Formatting Kode: clang-format dan Konvensi Modern

### 15.1 Mengapa Formatting Konsisten Penting?

Formatting yang konsisten:
- Mengurangi cognitive load saat membaca kode
- Menghilangkan debat "style wars" di tim
- Membuat diff/review lebih bersih
- Dapat diotomatisasi sepenuhnya

### 15.2 File Konfigurasi .clang-format

```yaml
# .clang-format — Taruh di root proyek
---
Language: Cpp
BasedOnStyle: LLVM

# ─── Indentation ──────────────────────────────────────────────────
IndentWidth: 4
TabWidth: 4
UseTab: Never
ContinuationIndentWidth: 4
IndentCaseLabels: true
IndentPPDirectives: BeforeHash

# ─── Line Length ──────────────────────────────────────────────────
ColumnLimit: 100

# ─── Braces ───────────────────────────────────────────────────────
BreakBeforeBraces: Attach  # K&R style: if (...) {
AllowShortFunctionsOnASingleLine: Inline
AllowShortIfStatementsOnASingleLine: Never
AllowShortLoopsOnASingleLine: false
AllowShortLambdasOnASingleLine: All

# ─── Spaces ───────────────────────────────────────────────────────
SpaceBeforeParens: ControlStatements
SpaceInEmptyParentheses: false
SpacesInAngles: Never
SpaceAfterTemplateKeyword: true
SpaceBeforeRangeBasedForLoopColon: true

# ─── Alignment ────────────────────────────────────────────────────
AlignConsecutiveAssignments: false
AlignConsecutiveDeclarations: false
AlignTrailingComments: true

# ─── Include Sorting ──────────────────────────────────────────────
SortIncludes: CaseSensitive
IncludeBlocks: Regroup
IncludeCategories:
  # 1. Project headers (dalam tanda kutip)
  - Regex: '^"'
    Priority: 1
  # 2. System headers (dalam tanda kurung sudut)
  - Regex: '^<[a-z]'
    Priority: 2
  # 3. Third-party headers
  - Regex: '^<'
    Priority: 3

# ─── Pointer/Reference Alignment ─────────────────────────────────
PointerAlignment: Left   # int* p; bukan int *p;
ReferenceAlignment: Left # int& r; bukan int &r;

# ─── Constructor Initializer ──────────────────────────────────────
ConstructorInitializerIndentWidth: 4
BreakConstructorInitializers: BeforeColon

# ─── Template ─────────────────────────────────────────────────────
AlwaysBreakTemplateDeclarations: Yes

# ─── Penalty (untuk line breaking decisions) ──────────────────────
PenaltyBreakBeforeFirstCallParameter: 1
PenaltyReturnTypeOnItsOwnLine: 200
```

### 15.3 Menjalankan clang-format

```bash
# Format satu file (in-place)
clang-format -i src/main.cpp

# Format semua file C++ di proyek
find src lib include -name "*.cpp" -o -name "*.hpp" | \
    xargs clang-format -i

# Cek apakah file sudah terformat (untuk CI)
clang-format --dry-run --Werror src/main.cpp

# Lihat diff tanpa mengubah file
clang-format src/main.cpp | diff src/main.cpp -

# Format via CMake target
cmake --build build --target format
```

### 15.4 Konvensi Penamaan C++ Modern

```cpp
// ─── Konvensi Penamaan yang Direkomendasikan ──────────────────────

// Namespace: lowercase dengan underscore
namespace my_project::math_utils { }

// Class/Struct: PascalCase
class HttpClient { };
struct UserProfile { };

// Fungsi: snake_case
void calculate_average();
bool is_valid_input();
std::string format_output();

// Variabel lokal: snake_case
int user_count = 0;
double average_score = 0.0;
std::string file_path;

// Member variabel: snake_case dengan trailing underscore
class MyClass {
    int value_;
    std::string name_;
    bool is_active_;
};

// Konstanta: SCREAMING_SNAKE_CASE atau kConstantCase
constexpr int MAX_BUFFER_SIZE = 4096;
constexpr double kPi = 3.14159265;

// Template parameter: PascalCase
template<typename ValueType, typename AllocatorType>
class Container { };

// Macro (hindari jika bisa): SCREAMING_SNAKE_CASE
#define MY_PROJECT_VERSION_MAJOR 1

// Enum class: PascalCase untuk nama, PascalCase untuk nilai
enum class ConnectionState {
    Disconnected,
    Connecting,
    Connected,
    Error
};
```

---

<a name="s16"></a>
## Seksi 16 — Unit Testing Pertama dengan Catch2

### 16.1 Mengapa Unit Testing?

Unit testing bukan tentang menemukan bug — ini tentang **mendefinisikan perilaku yang diharapkan** dan memastikan perilaku tersebut tidak berubah saat kode dimodifikasi (regression testing).

### 16.2 Setup Catch2 dengan vcpkg

```bash
# Install Catch2 via vcpkg
vcpkg install catch2

# Atau tambahkan ke vcpkg.json
# "dependencies": ["catch2"]
```

```cmake
# tests/CMakeLists.txt
find_package(Catch2 3 REQUIRED)

add_executable(unit_tests
    test_math.cpp
    test_string_utils.cpp
)

target_link_libraries(unit_tests
    PRIVATE
        Catch2::Catch2WithMain  # Sertakan main() dari Catch2
        math_lib
        utils_lib
)

# Integrasi dengan CTest
include(CTest)
include(Catch)
catch_discover_tests(unit_tests)
```

### 16.3 Menulis Test dengan Catch2

```cpp
// tests/test_math.cpp
#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>
#include <catch2/generators/catch_generators.hpp>

#include "math_utils.hpp"

// ─── Test Case Dasar ──────────────────────────────────────────────
TEST_CASE("safe_divide mengembalikan hasil yang benar", "[math][divide]") {
    
    SECTION("pembagian normal") {
        auto result = safe_divide(10.0, 2.0);
        REQUIRE(result.has_value());
        REQUIRE(result.value() == Catch::Approx(5.0));
    }
    
    SECTION("pembagian dengan nol mengembalikan nullopt") {
        auto result = safe_divide(10.0, 0.0);
        REQUIRE_FALSE(result.has_value());
    }
    
    SECTION("pembagian negatif") {
        auto result = safe_divide(-10.0, 2.0);
        REQUIRE(result.has_value());
        REQUIRE(result.value() == Catch::Approx(-5.0));
    }
    
    SECTION("pembagian menghasilkan desimal") {
        auto result = safe_divide(1.0, 3.0);
        REQUIRE(result.has_value());
        // Approx dengan toleransi
        REQUIRE(result.value() == Catch::Approx(0.3333).epsilon(0.001));
    }
}

// ─── Test dengan Generator (Data-Driven Testing) ──────────────────
TEST_CASE("clamp bekerja untuk berbagai nilai", "[math][clamp]") {
    using namespace myproject::math;
    
    SECTION("nilai dalam range tidak berubah") {
        auto value = GENERATE(1, 3, 5, 7, 9);
        REQUIRE(clamp(value, 0, 10) == value);
    }
    
    SECTION("nilai di bawah min dikembalikan sebagai min") {
        REQUIRE(clamp(-5, 0, 10) == 0);
        REQUIRE(clamp(-100, 0, 10) == 0);
    }
    
    SECTION("nilai di atas max dikembalikan sebagai max") {
        REQUIRE(clamp(15, 0, 10) == 10);
        REQUIRE(clamp(1000, 0, 10) == 10);
    }
}

// ─── Test Class ───────────────────────────────────────────────────
TEST_CASE("Vector2D operasi dasar", "[math][vector2d]") {
    using namespace myproject::math;
    
    SECTION("konstruksi default menghasilkan zero vector") {
        Vector2D v;
        REQUIRE(v.x() == Catch::Approx(0.0));
        REQUIRE(v.y() == Catch::Approx(0.0));
        REQUIRE(v.magnitude() == Catch::Approx(0.0));
    }
    
    SECTION("magnitude dihitung dengan benar") {
        Vector2D v{3.0, 4.0};
        REQUIRE(v.magnitude() == Catch::Approx(5.0));  // 3-4-5 triangle
    }
    
    SECTION("penjumlahan vector") {
        Vector2D a{1.0, 2.0};
        Vector2D b{3.0, 4.0};
        auto c = a + b;
        REQUIRE(c.x() == Catch::Approx(4.0));
        REQUIRE(c.y() == Catch::Approx(6.0));
    }
    
    SECTION("normalized vector memiliki magnitude 1") {
        Vector2D v{3.0, 4.0};
        auto n = v.normalized();
        REQUIRE(n.magnitude() == Catch::Approx(1.0).epsilon(1e-10));
    }
}

// ─── Test Exception ───────────────────────────────────────────────
TEST_CASE("Vector2D normalized melempar exception untuk zero vector", 
          "[math][vector2d][exception]") {
    using namespace myproject::math;
    
    Vector2D zero_vector{0.0, 0.0};
    REQUIRE_THROWS_AS(zero_vector.normalized(), std::domain_error);
}

// ─── Benchmark (Catch2 v3) ────────────────────────────────────────
// #include <catch2/benchmark/catch_benchmark.hpp>
// TEST_CASE("Vector2D magnitude benchmark", "[!benchmark]") {
//     Vector2D v{3.0, 4.0};
//     BENCHMARK("magnitude calculation") {
//         return v.magnitude();
//     };
// }
```

### 16.4 Menjalankan Tests

```bash
# Build dan jalankan semua tests
cmake --build build && cd build && ctest --output-on-failure

# Jalankan test binary langsung (lebih banyak opsi)
./build/tests/unit_tests

# Filter test berdasarkan tag
./build/tests/unit_tests "[math]"
./build/tests/unit_tests "[vector2d]"

# Jalankan test spesifik
./build/tests/unit_tests "Vector2D operasi dasar"

# Output verbose
./build/tests/unit_tests --reporter console --success

# Output XML untuk CI
./build/tests/unit_tests --reporter junit --out test_results.xml
```

**Output:**
```
===============================================================================
All tests passed (12 assertions in 4 test cases)
```

---

<a name="s17"></a>
## Seksi 17 — Continuous Integration Dasar untuk Proyek C++

### 17.1 GitHub Actions untuk C++

```yaml
# .github/workflows/ci.yml
name: CI — C++ Build & Test

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  # ─── Build & Test di Linux ──────────────────────────────────────
  linux-build:
    name: Linux (${{ matrix.compiler }}, C++${{ matrix.std }})
    runs-on: ubuntu-22.04
    
    strategy:
      fail-fast: false
      matrix:
        compiler: [gcc-13, clang-17]
        std: [17, 20]
    
    steps:
    - name: Checkout kode
      uses: actions/checkout@v4
    
    - name: Install dependencies
      run: |
        sudo apt-get update
        sudo apt-get install -y \
          gcc-13 g++-13 \
          clang-17 \
          cmake ninja-build \
          clang-tidy-17 clang-format-17
    
    - name: Setup vcpkg
      uses: lukka/run-vcpkg@v11
      with:
        vcpkgGitCommitId: '2024.01.12'
    
    - name: Configure CMake
      run: |
        cmake -B build -G Ninja \
          -DCMAKE_BUILD_TYPE=Release \
          -DCMAKE_CXX_STANDARD=${{ matrix.std }} \
          -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake \
          -DBUILD_TESTS=ON
      env:
        CC: ${{ matrix.compiler == 'gcc-13' && 'gcc-13' || 'clang-17' }}
        CXX: ${{ matrix.compiler == 'gcc-13' && 'g++-13' || 'clang++-17' }}
    
    - name: Build
      run: cmake --build build --parallel
    
    - name: Run Tests
      run: ctest --test-dir build --output-on-failure --parallel 4
    
    - name: Upload test results
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: test-results-${{ matrix.compiler }}-cpp${{ matrix.std }}
        path: build/test_results.xml

  # ─── Static Analysis ────────────────────────────────────────────
  static-analysis:
    name: Static Analysis
    runs-on: ubuntu-22.04
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Install clang-tidy
      run: sudo apt-get install -y clang-17 clang-tidy-17 cmake ninja-build
    
    - name: Configure (untuk compile_commands.json)
      run: |
        cmake -B build -G Ninja \
          -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
          -DCMAKE_CXX_COMPILER=clang++-17
    
    - name: Run clang-tidy
      run: |
        find src lib -name "*.cpp" | \
          xargs clang-tidy-17 -p build --warnings-as-errors='*'

  # ─── Format Check ───────────────────────────────────────────────
  format-check:
    name: Format Check
    runs-on: ubuntu-22.04
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Install clang-format
      run: sudo apt-get install -y clang-format-17
    
    - name: Check formatting
      run: |
        find src lib include -name "*.cpp" -o -name "*.hpp" | \
          xargs clang-format-17 --dry-run --Werror

  # ─── Sanitizer Build ────────────────────────────────────────────
  sanitizer-build:
    name: Sanitizer (${{ matrix.sanitizer }})
    runs-on: ubuntu-22.04
    
    strategy:
      matrix:
        sanitizer: [address,undefined, thread]
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Install dependencies
      run: sudo apt-get install -y clang-17 cmake ninja-build
    
    - name: Configure with sanitizer
      run: |
        cmake -B build -G Ninja \
          -DCMAKE_BUILD_TYPE=Debug \
          -DCMAKE_CXX_COMPILER=clang++-17 \
          -DCMAKE_CXX_FLAGS="-fsanitize=${{ matrix.sanitizer }} -fno-omit-frame-pointer" \
          -DBUILD_TESTS=ON
    
    - name: Build & Test
      run: |
        cmake --build build --parallel
        ctest --test-dir build --output-on-failure
```

### 17.2 CMake Target untuk CI Tasks

```cmake
# cmake/CITargets.cmake

# ─── clang-format target ──────────────────────────────────────────
find_program(CLANG_FORMAT clang-format clang-format-17)
if(CLANG_FORMAT)
    file(GLOB_RECURSE ALL_SOURCE_FILES
        "${CMAKE_SOURCE_DIR}/src/*.cpp"
        "${CMAKE_SOURCE_DIR}/src/*.hpp"
        "${CMAKE_SOURCE_DIR}/lib/*.cpp"
        "${CMAKE_SOURCE_DIR}/lib/*.hpp"
        "${CMAKE_SOURCE_DIR}/include/*.hpp"
    )
    
    add_custom_target(format
        COMMAND ${CLANG_FORMAT} -i ${ALL_SOURCE_FILES}
        COMMENT "Formatting source files..."
    )
    
    add_custom_target(format-check
        COMMAND ${CLANG_FORMAT} --dry-run --Werror ${ALL_SOURCE_FILES}
        COMMENT "Checking source formatting..."
    )
endif()

# ─── clang-tidy target ────────────────────────────────────────────
find_program(CLANG_TIDY clang-tidy clang-tidy-17)
if(CLANG_TIDY)
    add_custom_target(tidy
        COMMAND ${CLANG_TIDY}
            -p ${CMAKE_BINARY_DIR}
            ${ALL_SOURCE_FILES}
        COMMENT "Running clang-tidy..."
    )
endif()
```

---

<a name="s18"></a>
## Seksi 18 — Pola Kesalahan Umum Pemula C++ Modern

### 18.1 Kesalahan Tipe dan Konversi

```cpp
// ❌ KESALAHAN 1: Integer division yang tidak disengaja
int a = 7, b = 2;
double result = a / b;  // result = 3.0, BUKAN 3.5!
// Karena a/b adalah integer division → 3, lalu dikonversi ke double

// ✅ BENAR:
double result2 = static_cast<double>(a) / b;  // 3.5
double result3 = a / 2.0;                      // 3.5

// ─────────────────────────────────────────────────────────────────

// ❌ KESALAHAN 2: Signed/unsigned comparison
std::vector<int> v = {1, 2, 3};
for (int i = 0; i < v.size(); ++i) {  // ⚠️ Warning: signed/unsigned
    // v.size() returns size_t (unsigned)
    // Jika v.size() > INT_MAX, i < v.size() berperilaku salah
}

// ✅ BENAR:
for (std::size_t i = 0; i < v.size(); ++i) { }  // Gunakan size_t
for (auto i = 0u; i < v.size(); ++i) { }         // Atau unsigned
for (const auto& item : v) { }                    // Atau range-for (TERBAIK)

// ─────────────────────────────────────────────────────────────────

// ❌ KESALAHAN 3: Narrowing conversion
int big = 1000;
char small = big;  // ⚠️ Narrowing: nilai mungkin terpotong

// ✅ BENAR: Gunakan brace initialization yang mencegah narrowing
// char small2{big};  // ❌ Compile error! Brace init mencegah narrowing
char small3 = static_cast<char>(big);  // ✅ Eksplisit, programmer tahu risikonya
```

### 18.2 Kesalahan Manajemen Memori

```cpp
// ❌ KESALAHAN 4: Raw pointer tanpa RAII
void process_data() {
    int* data = new int[1000];
    
    if (some_condition()) {
        return;  // ❌ MEMORY LEAK! data tidak di-delete
    }
    
    // ... proses data ...
    
    delete[] data;  // Hanya tercapai jika tidak return awal
}

// ✅ BENAR: Gunakan smart pointer atau container
void process_data_modern() {
    auto data = std::make_unique<int[]>(1000);  // Otomatis di-delete
    
    if (some_condition()) {
        return;  // ✅ data otomatis di-delete saat keluar scope
    }
    
    // Atau lebih baik lagi:
    std::vector<int> data2(1000);  // RAII, tidak perlu delete
}

// ─────────────────────────────────────────────────────────────────

// ❌ KESALAHAN 5: Dangling reference
std::string& get_name() {
    std::string local = "Alice";
    return local;  // ❌ UB! Mengembalikan referensi ke variabel lokal
}

// ✅ BENAR: Return by value (compiler akan optimize dengan RVO/NRVO)
std::string get_name_safe() {
    std::string local = "Alice";
    return local;  // ✅ Return by value, RVO akan menghilangkan copy
}

// ─────────────────────────────────────────────────────────────────

// ❌ KESALAHAN 6: Iterator invalidation
std::vector<int> v = {1, 2, 3, 4, 5};
for (auto it = v.begin(); it != v.end(); ++it) {
    if (*it == 3) {
        v.push_back(99);  // ❌ UB! push_back bisa reallocate, invalidate iterator
    }
}

// ✅ BENAR: Kumpulkan dulu, modifikasi setelah
std::vector<int> to_add;
for (const auto& item : v) {
    if (item == 3) to_add.push_back(99);
}
v.insert(v.end(), to_add.begin(), to_add.end());
```

### 18.3 Kesalahan Logika dan Semantik

```cpp
// ❌ KESALAHAN 7: Lupa const correctness
class Calculator {
public:
    int get_result() {  // ❌ Seharusnya const
        return result_;
    }
    
    // Tidak bisa dipanggil pada const Calculator!
    
private:
    int result_ = 0;
};

// ✅ BENAR:
class Calculator {
public:
    [[nodiscard]] int get_result() const {  // ✅ const member function
        return result_;
    }
private:
    int result_ = 0;
};

// ─────────────────────────────────────────────────────────────────

// ❌ KESALAHAN 8: Mengabaikan return value penting
std::vector<int> v = {3, 1, 4, 1, 5};
std::remove(v.begin(), v.end(), 1);  // ❌ Tidak menghapus elemen!
// std::remove hanya memindahkan elemen, tidak mengubah size

// ✅ BENAR: Erase-remove idiom
v.erase(std::remove(v.begin(), v.end(), 1), v.end());

// Atau C++20:
std::erase(v, 1);  // ✅ Lebih bersih

// ─────────────────────────────────────────────────────────────────

// ❌ KESALAHAN 9: Object slicing
class Animal {
public:
    virtual std::string sound() const { return "..."; }
};

class Dog : public Animal {
public:
    std::string sound() const override { return "Woof"; }
};

void make_sound(Animal a) {  // ❌ Pass by value: object slicing!
    std::cout << a.sound();  // Selalu "..." karena Dog dipotong jadi Animal
}

// ✅ BENAR: Pass by reference atau pointer
void make_sound_correct(const Animal& a) {  // ✅ Polymorphism bekerja
    std::cout << a.sound();  // "Woof" jika Dog
}

// ─────────────────────────────────────────────────────────────────

// ❌ KESALAHAN 10: endl vs '\n'
for (int i = 0; i < 1000000; ++i) {
    std::cout << i << std::endl;  // ❌ LAMBAT! endl flush buffer setiap kali
}

// ✅ BENAR: Gunakan '\n' kecuali perlu flush eksplisit
for (int i = 0; i < 1000000; ++i) {
    std::cout << i << '\n';  // ✅ Jauh lebih cepat
}
std::cout.flush();  // Flush sekali di akhir jika diperlukan
```

### 18.4 Checklist Anti-Pattern

```
❌ HINDARI                          ✅ GUNAKAN
─────────────────────────────────────────────────────────────
using namespace std;               Prefix std:: eksplisit
#include <bits/stdc++.h>           Include spesifik yang diperlukan
NULL                               nullptr
(int)x                             static_cast<int>(x)
new/delete langsung                smart pointer / container
char array untuk string            std::string
printf/scanf                       std::cout/cin atau fmt::print
endl                               '\n'
int i; (uninitialized)             int i = 0; atau int i{};
for(int i=0;i<v.size();i++)        for(const auto& item : v)
std::vector<T> copy = original     const std::vector<T>& ref = original
return type void untuk error       std::optional<T> atau Result type
global variable                    Parameter atau class member
magic number (42, 3.14)            Named constexpr constant
```

---

<a name="s19"></a>
## Seksi 19 — Latihan Terstruktur dan Mini-Project

### 19.1 Latihan Bertingkat

#### Latihan 01 — Dasar (⭐)

**Tujuan:** Membiasakan diri dengan sintaks C++ modern dasar.

```cpp
// TUGAS: Lengkapi implementasi fungsi-fungsi berikut
// File: exercises/ex01_basics.cpp

#include <string>
#include <vector>
#include <optional>
#include <algorithm>

// Tugas 1: Implementasikan fungsi yang mengembalikan
// elemen terbesar dalam vector, atau nullopt jika kosong
std::optional<int> find_maximum(const std::vector<int>& numbers) {
    // TODO: Implementasikan menggunakan std::max_element
    // Hint: Cek apakah numbers.empty() terlebih dahulu
}

// Tugas 2: Implementasikan fungsi yang membalik string
// tanpa menggunakan std::reverse
std::string reverse_string(std::string_view input) {
    // TODO: Implementasikan
    // Hint: Gunakan konstruktor string dengan reverse iterator
}

// Tugas 3: Implementasikan fungsi yang menghitung
// frekuensi setiap karakter dalam string
// Return: vector of pairs (char, count), sorted by count descending
std::vector<std::pair<char, int>> char_frequency(std::string_view text) {
    // TODO: Implementasikan
    // Hint: Gunakan std::map atau std::unordered_map
}

// Tugas 4: Implementasikan FizzBuzz modern
// Return vector of strings: "Fizz", "Buzz", "FizzBuzz", atau angka
std::vector<std::string> fizzbuzz(int n) {
    // TODO: Implementasikan untuk 1 hingga n
}
```

#### Latihan 02 — Menengah (⭐⭐)

**Tujuan:** Memahami class, RAII, dan algoritma.

```cpp
// TUGAS: Implementasikan class Stack yang type-safe
// File: exercises/ex02_stack.hpp

#pragma once
#include <vector>
#include <optional>
#include <stdexcept>

template<typename T>
class Stack {
public:
    // Tugas: Implementasikan semua method berikut
    
    // Push element ke atas stack
    void push(T value);
    
    // Pop dan kembalikan element teratas
    // Throw std::underflow_error jika stack kosong
    T pop();
    
    // Kembalikan element teratas tanpa menghapus
    // Return nullopt jika stack kosong
    [[nodiscard]] std::optional<T> peek() const;
    
    // Cek apakah stack kosong
    [[nodiscard]] bool empty() const noexcept;
    
    // Kembalikan jumlah elemen
    [[nodiscard]] std::size_t size() const noexcept;
    
    // Kosongkan stack
    void clear() noexcept;

private:
    std::vector<T> data_;
};

// Tugas: Tulis unit tests untuk Stack menggunakan Catch2
// File: exercises/test_ex02_stack.cpp
```

### 19.2 Mini-Project: Kalkulator Ekspresi Sederhana

**Deskripsi:** Bangun kalkulator yang dapat mengevaluasi ekspresi matematika sederhana.

**Spesifikasi:**
- Input: String ekspresi seperti `"3 + 4 * 2"`, `"(10 - 2) / 4"`
- Output: Hasil perhitungan sebagai `double`
- Operator yang didukung: `+`, `-`, `*`, `/`
- Mendukung tanda kurung
- Error handling untuk ekspresi tidak valid dan pembagian nol

**Struktur Proyek:**

```
mini_calculator/
├── CMakeLists.txt
├── vcpkg.json
├── include/
│   └── calculator/
│       ├── lexer.hpp      # Tokenizer
│       ├── parser.hpp     # Expression parser
│       └── evaluator.hpp  # Expression evaluator
├── src/
│   ├── lexer.cpp
│   ├── parser.cpp
│   ├── evaluator.cpp
│   └── main.cpp
└── tests/
    ├── CMakeLists.txt
    ├── test_lexer.cpp
    ├── test_parser.cpp
    └── test_evaluator.cpp
```

**Skeleton Kode:**

```cpp
// include/calculator/lexer.hpp
#pragma once
#include <string>
#include <string_view>
#include <variant>
#include <vector>

namespace calculator {

// Token types menggunakan enum class
enum class TokenType {
    Number,
    Plus,
    Minus,
    Multiply,
    Divide,
    LeftParen,
    RightParen,
    EndOfInput
};

// Token menggunakan struct dengan variant untuk nilai
struct Token {
    TokenType type;
    std::variant<double, std::monostate> value;
    
    // Factory methods
    static Token number(double val) {
        return {TokenType::Number, val};
    }
    static Token op(TokenType t) {
        return {t, std::monostate{}};
    }
    
    [[nodiscard]] bool is_number() const {
        return type == TokenType::Number;
    }
    
    [[nodiscard]] double as_number() const {
        return std::get<double>(value);
    }
};

// Lexer: mengubah string menjadi sequence of tokens
class Lexer {
public:
    explicit Lexer(std::string_view input);
    
    // Kembalikan semua token dari input
    [[nodiscard]] std::vector<Token> tokenize();

private:
    std::string_view input_;
    std::size_t pos_{0};
    
    void skip_whitespace();
    Token read_number();
    char current() const;
    char advance();
    bool at_end() const;
};

}  // namespace calculator
```

```cpp
// src/main.cpp
#include <calculator/evaluator.hpp>
#include <iostream>
#include <string>

int main() {
    calculator::Evaluator eval;
    
    std::cout << "Kalkulator C++ Modern\n";
    std::cout << "Ketik ekspresi matematika (atau 'quit' untuk keluar):\n";
    
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line == "quit" || line == "q") break;
        if (line.empty()) continue;
        
        auto result = eval.evaluate(line);
        
        if (result) {
            std::cout << "= " << *result << '\n';
        } else {
            std::cout << "Error: " << result.error() << '\n';
        }
    }
    
    return 0;
}
```

**Kriteria Penilaian:**

| Kriteria | Poin |
|---|---|
| Semua unit test pass | 40 |
| Operator dasar (+, -, *, /) bekerja | 20 |
| Tanda kurung bekerja | 15 |
| Error handling yang baik | 15 |
| Kode mengikuti konvensi modern (clang-tidy clean) | 10 |
| **Total** | **100** |

---

<a name="s20"></a>
## Seksi 20 — Ringkasan, Referensi, dan Peta Jalan Belajar

### 20.1 Ringkasan Modul

Dalam modul ini, Anda telah mempelajari:

```
✅ FONDASI YANG DIBANGUN
─────────────────────────────────────────────────────────────────
□ Filosofi C++ dan mengapa ia relevan di era modern
□ Peta standar C++11 hingga C++23 dan fitur kuncinya
□ Arsitektur toolchain: compiler, linker, build system, tools
□ Instalasi dan konfigurasi GCC, Clang, MSVC
□ CMake sebagai build system modern
□ Konfigurasi IDE (VS Code, CLion) untuk produktivitas maksimal
□ Anatomi program C++ modern yang idiomatis
□ Sistem tipe dasar dan type safety
□ Proses kompilasi dan linking secara mendalam
□ Manajemen paket dengan vcpkg dan Conan
□ Debugging dengan GDB, LLDB, dan AddressSanitizer
□ Static analysis dengan clang-tidy dan cppcheck
□ Code formatting dengan clang-format
□ Unit testing dengan Catch2
□ CI/CD dasar dengan GitHub Actions
□ Anti-pattern umum dan cara menghindarinya
```

### 20.2 Konsep Kunci yang Harus Dikuasai

```cpp
// Setelah modul ini, Anda harus nyaman dengan:

// 1. Type deduction
auto x = compute_something();
const auto& ref = expensive_object;

// 2. Range-based for
for (const auto& item : container) { }

// 3. Lambda dasar
auto predicate = [threshold](int val) { return val > threshold; };

// 4. Smart pointer dasar
auto ptr = std::make_unique<MyClass>(args...);

// 5. std::optional
std::optional<Result> maybe_result = try_operation();
if (maybe_result) { use(*maybe_result); }

// 6. Structured bindings
auto [key, value] = *map.find("key");

// 7. [[nodiscard]] dan const correctness
[[nodiscard]] int compute() const;

// 8. Uniform initialization
std::vector<int> v{1, 2, 3, 4, 5};
MyStruct s{.field1 = 1, .field2 = "hello"};  // C++20 designated init
```

### 20.3 Referensi Utama

#### Dokumentasi Resmi
| Sumber | URL | Keterangan |
|---|---|---|
| cppreference.com | https://en.cppreference.com | **Referensi utama** — komprehensif dan akurat |
| isocpp.org | https://isocpp.org | Situs resmi ISO C++ |
| C++ Core Guidelines | https://isocpp.github.io/CppCoreGuidelines | Panduan best practice dari Stroustrup & Sutter |

#### Buku Referensi
| Judul | Penulis | Level |
|---|---|---|
| *A Tour of C++* (3rd ed.) | Bjarne Stroustrup | Pemula-Menengah |
| *Effective Modern C++* | Scott Meyers | Menengah |
| *C++ Templates: The Complete Guide* | Vandevoorde, Josuttis | Lanjutan |
| *C++ Concurrency in Action* | Anthony Williams | Lanjutan |
| *The C++ Programming Language* (4th ed.) | Bjarne Stroustrup | Referensi Lengkap |

#### Video & Kursus Online
| Platform | Konten | Keterangan |
|---|---|---|
| CppCon (YouTube) | Konferensi tahunan C++ | Talk dari expert industri |
| Jason Turner (YouTube) | C++ Weekly | Tips C++ modern mingguan |
| The Cherno (YouTube) | C++ Series | Pemula-Menengah |
| Compiler Explorer (godbolt.org) | Lihat assembly output | Tool esensial untuk pemahaman |

### 20.4 Peta Jalan Belajar C++ Modern Engineering

```
BAB 01 — FONDASI & EKOSISTEM (Modul ini)
    ├── M01: Pengantar & Lingkungan ◄ ANDA DI SINI
    ├── M02: Tipe, Variabel & Ekspresi
    ├── M03: Kontrol Alur Modern
    └── M04: Fungsi & Lambda

BAB 02 — MANAJEMEN MEMORI & RAII
    ├── M05: Stack vs Heap, Pointer Modern
    ├── M06: Smart Pointers (unique_ptr, shared_ptr, weak_ptr)
    ├── M07: Move Semantics & Rvalue References
    └── M08: RAII Pattern & Resource Management

BAB 03 — OOP MODERN
    ├── M09: Class Design & Encapsulation
    ├── M10: Inheritance & Polymorphism
    ├── M11: Operator Overloading
    └── M12: Rule of Zero/Three/Five

BAB 04 — TEMPLATE & GENERIC PROGRAMMING
    ├── M13: Function & Class Templates
    ├── M14: Template Specialization
    ├── M15: Variadic Templates
    └── M16: Concepts (C++20)

BAB 05 — STANDARD LIBRARY MENDALAM
    ├── M17: Containers (vector, map, set, unordered_*)
    ├── M18: Algorithms & Ranges (C++20)
    ├── M19: String & String Processing
    └── M20: Filesystem & I/O

BAB 06 — CONCURRENCY
    ├── M21: Thread & Mutex
    ├── M22: Atomic & Memory Model
    ├── M23: Async & Future
    └── M24: Coroutines (C++20)

BAB 07 — DESAIN & ARSITEKTUR
    ├── M25: Design Patterns in Modern C++
    ├── M26: Error Handling Strategies
    ├── M27: Performance Engineering
    └── M28: Large-Scale C++ Architecture

BAB 08 — PROYEK NYATA
    ├── M29: Membangun Library C++ yang Distributable
    ├── M30: Integrasi dengan Python (pybind11)
    ├── M31: Embedded C++ Modern
    └── M32: Capstone Project
```

### 20.5 Checklist Kesiapan Modul Berikutnya

Sebelum melanjutkan ke **Modul 02 (Tipe, Variabel & Ekspresi)**, pastikan Anda dapat:

```
□ Menginstal dan mengkonfigurasi compiler (GCC atau Clang)
□ Membuat proyek CMake dari awal dengan struktur yang benar
□ Mengkompilasi program C++17 dengan warning flags lengkap
□ Menjalankan clang-format dan clang-tidy pada kode Anda
□ Menulis dan menjalankan unit test sederhana dengan Catch2
□ Menggunakan debugger (GDB atau LLDB) untuk inspeksi variabel
□ Menjelaskan perbedaan antara C++11, C++14, C++17, dan C++20
□ Menghindari 10 anti-pattern yang dibahas di Seksi 18
□ Menyelesaikan minimal Latihan 01 dari Seksi 19
```

### 20.6 Pertanyaan Refleksi

Renungkan pertanyaan-pertanyaan berikut untuk memperdalam pemahaman:

1. **Mengapa** C++ memilih "zero-overhead abstraction" sebagai prinsip desain, dan apa konsekuensinya bagi programmer?

2. **Kapan** Anda akan memilih Clang over GCC, dan sebaliknya?

3. **Mengapa** `nullptr` lebih baik dari `NULL` atau `0` untuk pointer null?

4. **Apa** perbedaan fundamental antara static library (`.a`) dan shared library (`.so`), dan kapan Anda memilih masing-masing?

5. **Mengapa** `std::endl` lebih lambat dari `'\n'`, dan kapan Anda benar-benar membutuhkan `std::endl`?

---

> **📝 Catatan Instruktur**
>
> Modul ini dirancang sebagai fondasi yang solid. Jangan terburu-buru melanjutkan sebelum lingkungan pengembangan Anda berfungsi dengan baik. Waktu yang diinvestasikan untuk setup yang benar akan menghemat berjam-jam debugging di masa depan.
>
> **Tugas Sebelum Modul Berikutnya:**
> 1. Setup proyek CMake dengan struktur yang direkomendasikan
> 2. Konfigurasi VS Code atau CLion dengan semua ekstensi
> 3. Selesaikan mini-project kalkulator (minimal fitur dasar)
> 4. Pastikan CI pipeline berjalan di GitHub Actions

---

*© C++ Modern Engineering — Bab 01, Modul 01*
*Versi 1.0 | Standar: C++17/C++20 | Compiler: GCC 13+, Clang 17+*