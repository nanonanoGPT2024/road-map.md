# Hands-On Lab 01: Simulasi STP Root Bridge Election & Protection Toolkit

## Deskripsi Laboratorium
Lab ini menyediakan simulasi interaktif berbasis Python murni (`stp_root_bridge_election_sim.py`) untuk membedah internal state machine protokol Spanning Tree (IEEE 802.1D / IEEE 802.1w RSTP) tanpa memerlukan perangkat keras switch fisik. 

Anda akan menyaksikan secara transparan bagaimana paket BPDU (Bridge Protocol Data Unit) dipertukarkan, bagaimana penentuan Root Bridge berlangsung secara deterministik berdasarkan Bridge ID, bagaimana Port Role (Root, Designated, Alternate) diputuskan, serta bagaimana fitur proteksi enterprise seperti **Root Guard** dan **BPDU Guard** bekerja menangkal ancaman loop atau pembajakan topologi.

---

## Prasyarat Lingkungan
- Python 3.8 atau versi yang lebih tinggi terpasang di sistem operasi Anda.
- Terminal / Command Prompt dengan dukungan output teks standar.
- Tidak memerlukan modul eksternal (menggunakan standard library Python).

---

## Struktur File Lab
```text
hands-on/m01/
├── README.md                          # Panduan eksekusi praktikum
└── stp_root_bridge_election_sim.py    # Skrip simulator STP & Proteksi
```

---

## Langkah-Langkah Praktikum

### Langkah 1: Validasi Lingkungan
Pastikan interpreter Python Anda telah terkonfigurasi dengan benar:
```bash
python3 --version
```

### Langkah 2: Jalankan Simulasi STP Dasar
Eksekusi simulasi topologi segitiga enterprise:
```bash
python3 stp_root_bridge_election_sim.py
```

### Langkah 3: Analisis Output Konvergensi STP
Perhatikan tabel topologi yang dihasilkan pada terminal:
1. **Root Bridge Identification**:
   - Amati kolom `Bridge ID`. Switch dengan nilai terkecil (`SW-CORE-01` dengan priority 4096) terpilih sebagai Root Bridge.
2. **Port Role Mapping**:
   - Seluruh interface fisik pada `SW-CORE-01` berada dalam role `DESIGNATED` dan status `FORWARDING`.
   - Switch downstream (`SW-DIST-02` dan `SW-ACC-03`) memilih satu port terdekat menuju root sebagai `ROOT` port.
   - Jalur interkoneksi redundan antara `SW-DIST-02` dan `SW-ACC-03` mengalami pemblokiran logis: port `Eth1/2` pada `SW-ACC-03` dialihkan ke role `ALTERNATE` dengan status `DISCARDING` untuk mengeliminasi potensi broadcast storm.

### Langkah 4: Observasi Simulasi Serangan Rogue Root Switch
Skrip akan secara otomatis menjalankan fase pengujian serangan:
1. Sebuah switch liar (`SW-ROGUE`) dicolokkan ke port edge access switch dengan Bridge Priority `0` (membawa klaim superior).
2. **Fase Tanpa Proteksi**: Perhatikan bagaimana `SW-ROGUE` berhasil