# Computer Science Foundations
## Bab 01 — Module 01: Cara Komputer Berpikir — Representasi Data & Logika Biner

---

> **Jalur:** Computer Science Foundations
> **Kode:** `computer-science/ch01/m01`
> **Prasyarat:** Tidak ada — ini adalah modul pertama
> **Estimasi Waktu:** 90–120 menit
> **Tingkat:** Pemula Absolut → Menengah Awal

---

## SEKSI 01 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda akan mampu:

| # | Objective | Tingkat Bloom | Indikator Keberhasilan |
|---|-----------|---------------|------------------------|
| LO-1 | Menjelaskan mengapa komputer menggunakan sistem biner (basis-2) bukan desimal (basis-10) | Memahami | Dapat menjelaskan alasan fisik/elektronik tanpa melihat catatan |
| LO-2 | Mengkonversi bilangan antara biner, oktal, desimal, dan heksadesimal | Menerapkan | Akurasi ≥ 90% pada 10 soal konversi acak |
| LO-3 | Mendeskripsikan bagaimana teks, gambar, dan suara direpresentasikan sebagai bit | Memahami | Dapat menelusuri encoding karakter 'A' dari keyboard ke memori |
| LO-4 | Menerapkan operasi logika Boolean dasar (AND, OR, NOT, XOR) | Menerapkan | Mengisi truth table dengan benar dan menulis ekspresi Boolean sederhana |
| LO-5 | Menghitung kapasitas penyimpanan menggunakan satuan bit, byte, KB, MB, GB, TB | Menerapkan | Mengestimasi ukuran file dengan margin error < 20% |
| LO-6 | Menganalisis bagaimana abstraksi berlapis memungkinkan kompleksitas dikelola | Menganalisis | Dapat menggambar 5 lapisan abstraksi dari transistor ke aplikasi |

---

## SEKSI 02 — CONCEPT OVERVIEW (Peta Konsep)

```
┌─────────────────────────────────────────────────────────────────┐
│              CARA KOMPUTER BERPIKIR                             │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │   FISIKA     │───▶│   LOGIKA     │───▶│  REPRESENTASI    │  │
│  │              │    │              │    │                  │  │
│  │ Tegangan     │    │ Boolean      │    │ Teks, Gambar,    │  │
│  │ Tinggi/Rendah│    │ AND/OR/NOT   │    │ Suara, Video     │  │
│  │ = 1 atau 0   │    │ XOR/NAND/NOR │    │ = Bit & Byte     │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│         │                  │                      │             │
│         └──────────────────┴──────────────────────┘             │
│                            │                                    │
│                    ┌───────▼────────┐                           │
│                    │  ABSTRAKSI     │                           │
│                    │                │                           │
│                    │ Transistor →   │                           │
│                    │ Gate → Circuit │                           │
│                    │ → CPU → OS →   │                           │
│                    │ Aplikasi       │                           │
│                    └────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

**Tiga Pilar Modul Ini:**
1. **Representasi** — Bagaimana dunia nyata dikodekan menjadi 0 dan 1
2. **Logika** — Bagaimana 0 dan 1 dimanipulasi untuk menghasilkan makna
3. **Abstraksi** — Bagaimana kompleksitas disembunyikan di balik lapisan yang lebih sederhana

---

## SEKSI 03 — WHY THIS MATTERS (Mengapa Ini Penting)

### Masalah Nyata yang Dipecahkan

Bayangkan Anda sedang membangun sistem perbankan. Nasabah mengirim transfer Rp 1.000.000. Komputer harus:

1. **Menerima** input angka dari keyboard (representasi)
2. **Menyimpan** angka itu di memori tanpa kehilangan presisi (encoding)
3. **Menghitung** saldo baru (aritmatika biner)
4. **Memverifikasi** apakah saldo cukup (logika Boolean)
5. **Mengirim** data ke bank lain melalui jaringan (transmisi bit)

Setiap langkah bergantung pada konsep yang akan Anda pelajari di modul ini.

### Mengapa Ini Fondasi dari Segalanya

```
Tanpa memahami representasi data:
├── Anda tidak bisa debug masalah encoding (karakter rusak, "mojibake")
├── Anda tidak bisa memahami mengapa floating-point tidak presisi
├── Anda tidak bisa mengerti keamanan (enkripsi, hashing)
├── Anda tidak bisa mengoptimalkan penggunaan memori
└── Anda tidak bisa memahami protokol jaringan

Dengan memahami representasi data:
├── Bug encoding menjadi mudah didiagnosis
├── Anda tahu kapan menggunakan integer vs float
├── Konsep kriptografi menjadi intuitif
├── Optimasi memori menjadi sistematis
└── Protokol jaringan menjadi transparan
```

### Relevansi Karir

| Peran | Kapan Konsep Ini Digunakan |
|-------|---------------------------|
| Software Engineer | Debugging encoding, optimasi memori, bit manipulation |
| Data Engineer | Kompresi data, format file (Parquet, Avro) |
| Security Engineer | Kriptografi, hashing, analisis binary |
| Embedded Engineer | Setiap hari — langsung bekerja dengan bit |
| ML Engineer | Representasi numerik, quantization model |
| DevOps | Ukuran file, bandwidth, kapasitas storage |

---

## SEKSI 04 — PREREQUISITE CHECK (Cek Prasyarat)

Modul ini adalah **titik awal**. Tidak ada prasyarat teknis. Namun, pastikan Anda memiliki:

### Pengetahuan Matematika Dasar yang Dibutuhkan

```
✅ Perkalian dan pembagian bilangan bulat
✅ Konsep pangkat (2³ = 8, 10² = 100)
✅ Konsep sisa bagi / modulo (17 mod 5 = 2)
✅ Membaca tabel sederhana
```

### Self-Assessment Cepat

Jawab dalam 60 detik:
1. Berapa 2⁸? → *(jawaban: 256)*
2. Berapa sisa 13 ÷ 2? → *(jawaban: 1)*
3. Berapa 16 × 16? → *(jawaban: 256)*

Jika Anda bisa menjawab ketiganya, Anda siap. Jika tidak, luangkan 15 menit untuk mengulang konsep pangkat dan pembagian.

---

## SEKSI 05 — CORE CONCEPT: MENGAPA BINER? (Fondasi Fisik)

### Dari Fisika ke Logika

Komputer modern dibangun dari **transistor** — komponen elektronik yang bertindak sebagai saklar. Sebuah transistor hanya memiliki dua kondisi yang dapat diandalkan:

```
TEGANGAN TINGGI (~3.3V atau 5V)  →  Logika 1  →  "ON" / "TRUE"
TEGANGAN RENDAH (~0V)            →  Logika 0  →  "OFF" / "FALSE"
```

**Mengapa tidak menggunakan 10 level tegangan untuk sistem desimal?**

```
MASALAH DENGAN 10 LEVEL TEGANGAN:
─────────────────────────────────
Tegangan ideal:  0V  0.5V  1V  1.5V  2V  2.5V  3V  3.5V  4V  4.5V
                  0    1    2    3    4    5    6    7    8    9

Masalah nyata:
├── Noise listrik: ±0.2V variasi → ambiguitas antara level berdekatan
├── Suhu: tegangan berubah seiring suhu
├── Degradasi: komponen menua, tegangan bergeser
└── Kecepatan: membedakan 10 level butuh waktu lebih lama

SOLUSI BINER:
─────────────
Hanya 2 level: 0V dan 3.3V
Margin noise: ±1.5V → sangat toleran terhadap gangguan
Kecepatan: keputusan ya/tidak jauh lebih cepat
Keandalan: hampir tidak ada ambiguitas
```

### Konsekuensi Desain

Karena komputer menggunakan biner, **semua informasi** — teks, gambar, suara, video, program — harus direpresentasikan sebagai rangkaian 0 dan 1. Ini bukan keterbatasan; ini adalah **kekuatan**: satu mekanisme sederhana yang dapat merepresentasikan segalanya.

---

## SEKSI 06 — CORE CONCEPT: SISTEM BILANGAN

### Memahami "Basis" (Radix)

Sistem bilangan adalah cara kita merepresentasikan kuantitas menggunakan simbol. Kunci pemahamannya adalah konsep **nilai posisi**.

```
SISTEM DESIMAL (Basis-10):
─────────────────────────
Simbol: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9  (10 simbol)

Angka 1.347 artinya:
  1 × 10³  +  3 × 10²  +  4 × 10¹  +  7 × 10⁰
= 1 × 1000 +  3 × 100  +  4 × 10   +  7 × 1
= 1000     +  300      +  40        +  7
= 1.347

SISTEM BINER (Basis-2):
───────────────────────
Simbol: 0, 1  (2 simbol)

Angka 1011₂ artinya:
  1 × 2³  +  0 × 2²  +  1 × 2¹  +  1 × 2⁰
= 1 × 8   +  0 × 4   +  1 × 2   +  1 × 1
= 8       +  0       +  2       +  1
= 11₁₀
```

### Empat Sistem Bilangan yang Digunakan dalam Komputasi

| Sistem | Basis | Simbol | Prefix Notasi | Digunakan Untuk |
|--------|-------|--------|---------------|-----------------|
| Biner | 2 | 0–1 | `0b` atau subscript ₂ | Representasi internal hardware |
| Oktal | 8 | 0–7 | `0o` atau subscript ₈ | Permission Unix (chmod 755) |
| Desimal | 10 | 0–9 | (tidak ada) | Input/output manusia |
| Heksadesimal | 16 | 0–9, A–F | `0x` atau subscript ₁₆ | Alamat memori, warna, encoding |

### Tabel Referensi Konversi

```
┌─────────┬──────────┬────────┬──────┐
│ Desimal │  Biner   │ Oktal  │ Hex  │
├─────────┼──────────┼────────┼──────┤
│    0    │  0000    │   0    │  0   │
│    1    │  0001    │   1    │  1   │
│    2    │  0010    │   2    │  2   │
│    3    │  0011    │   3    │  3   │
│    4    │  0100    │   4    │  4   │
│    5    │  0101    │   5    │  5   │
│    6    │  0110    │   6    │  6   │
│    7    │  0111    │   7    │  7   │
│    8    │  1000    │  10    │  8   │
│    9    │  1001    │  11    │  9   │
│   10    │  1010    │  12    │  A   │
│   11    │  1011    │  13    │  B   │
│   12    │  1100    │  14    │  C   │
│   13    │  1101    │  15    │  D   │
│   14    │  1110    │  16    │  E   │
│   15    │  1111    │  17    │  F   │
└─────────┴──────────┴────────┴──────┘
```

---

## SEKSI 07 — HOW IT WORKS: ALGORITMA KONVERSI

### Metode 1: Desimal → Biner (Pembagian Berulang)

**Algoritma:** Bagi dengan 2 berulang kali, catat sisa, baca dari bawah ke atas.

```
Konversi 45₁₀ ke biner:

Langkah  │ Pembagian │ Hasil │ Sisa
─────────┼───────────┼───────┼──────
   1     │  45 ÷ 2   │  22   │  1   ← bit paling kanan (LSB)
   2     │  22 ÷ 2   │  11   │  0
   3     │  11 ÷ 2   │   5   │  1
   4     │   5 ÷ 2   │   2   │  1
   5     │   2 ÷ 2   │   1   │  0
   6     │   1 ÷ 2   │   0   │  1   ← bit paling kiri (MSB)

Baca sisa dari BAWAH ke ATAS: 1 0 1 1 0 1

Verifikasi: 101101₂
= 1×32 + 0×16 + 1×8 + 1×4 + 0×2 + 1×1
= 32 + 0 + 8 + 4 + 0 + 1
= 45 ✓
```

### Metode 2: Biner → Desimal (Nilai Posisi)

```
Konversi 110110₂ ke desimal:

Posisi:  5    4    3    2    1    0
Bit:     1    1    0    1    1    0
Nilai: 2⁵  2⁴  2³  2²  2¹  2⁰
      = 32   16    8    4    2    1

Kalikan bit × nilai posisi:
  1×32 + 1×16 + 0×8 + 1×4 + 1×2 + 0×1
= 32   + 16   + 0   + 4   + 2   + 0
= 54₁₀
```

### Metode 3: Biner ↔ Heksadesimal (Pengelompokan 4-bit)

**Insight kunci:** Setiap digit hex tepat mewakili 4 bit biner.

```
Biner → Hex:
─────────────
Biner: 1010 1111 0011 1100
       ──── ──── ──── ────
Hex:    A    F    3    C
Hasil: 0xAF3C

Hex → Biner:
─────────────
Hex:  0x2D7B
       2    D    7    B
Biner: 0010 1101 0111 1011
Hasil: 0010110101111011₂

Mengapa ini berguna?
Biner 32-bit: 10101111001111001010000100000001
Hex 8-digit:  AF3CA101
→ Jauh lebih mudah dibaca!
```

### Metode 4: Desimal → Heksadesimal

```
Konversi 255₁₀ ke hex:

255 ÷ 16 = 15 sisa 15 → F  (LSB)
 15 ÷ 16 =  0 sisa 15 → F  (MSB)

Hasil: 0xFF

Verifikasi: F×16 + F×1 = 15×16 + 15 = 240 + 15 = 255 ✓

Catatan: 0xFF adalah nilai maksimum 1 byte (8 bit)
         Ini mengapa warna RGB: rgb(255, 255, 255) = #FFFFFF
```

---

## SEKSI 08 — DIAGRAM ASCII: ARSITEKTUR REPRESENTASI DATA

### Diagram 1: Hierarki Bit ke Informasi

```
                    HIERARKI REPRESENTASI DATA
                    ══════════════════════════

  Level 7: MAKNA        "Harga saham naik 5%"
                              ▲
  Level 6: APLIKASI     Spreadsheet, Database, Browser
                              ▲
  Level 5: FILE         invoice.pdf  (2.3 MB)
                              ▲
  Level 4: KARAKTER     'H' 'e' 'l' 'l' 'o'
                              ▲
  Level 3: BYTE         01001000  (8 bit = 1 byte)
                              ▲
  Level 2: BIT          0  atau  1
                              ▲
  Level 1: FISIK        Tegangan Rendah / Tegangan Tinggi
                              ▲
  Level 0: HARDWARE     Transistor ON / OFF


  Setiap level MENYEMBUNYIKAN kompleksitas level di bawahnya.
  Ini adalah prinsip ABSTRAKSI.
```

### Diagram 2: Anatomi Sebuah Byte

```
  SATU BYTE = 8 BIT
  ══════════════════

  Bit ke-7  Bit ke-6  Bit ke-5  Bit ke-4  Bit ke-3  Bit ke-2  Bit ke-1  Bit ke-0
  (MSB)                                                                   (LSB)
  ┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐
  │    1    │    0    │    1    │    0    │    0    │    1    │    1    │    0    │
  └─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘
      ↑                                                                       ↑
  Most Significant Bit                                           Least Significant Bit
  (Bit paling berpengaruh)                                    (Bit paling kecil nilainya)

  Nilai:  128  +   0   +  32   +   0   +   0   +   4   +   2   +   0   =  166

  Dalam hex: 1010 0110 → A6 → 0xA6

  Range 1 byte: 0 (00000000) sampai 255 (11111111) = 256 nilai berbeda
```

### Diagram 3: Lapisan Abstraksi Komputer

```
  ┌─────────────────────────────────────────────────────────────┐
  │                    APLIKASI PENGGUNA                        │
  │              (Python, Java, Browser, Game)                  │
  └──────────────────────────┬──────────────────────────────────┘
                             │ System Calls
  ┌──────────────────────────▼──────────────────────────────────┐
  │                  SISTEM OPERASI (OS)                        │
  │           (Linux, Windows, macOS, Android)                  │
  └──────────────────────────┬──────────────────────────────────┘
                             │ Instruction Set Architecture (ISA)
  ┌──────────────────────────▼──────────────────────────────────┐
  │              ARSITEKTUR MESIN (ISA)                         │
  │              (x86-64, ARM, RISC-V)                          │
  └──────────────────────────┬──────────────────────────────────┘
                             │ Microarchitecture
  ┌──────────────────────────▼──────────────────────────────────┐
  │           MIKROARSITEKTUR / SIRKUIT DIGITAL                 │
  │         (ALU, Register, Cache, Pipeline)                    │
  └──────────────────────────┬──────────────────────────────────┘
                             │ Logic Gates
  ┌──────────────────────────▼──────────────────────────────────┐
  │                   GERBANG LOGIKA                            │
  │              (AND, OR, NOT, XOR, NAND)                      │
  └──────────────────────────┬──────────────────────────────────┘
                             │ Transistors
  ┌──────────────────────────▼──────────────────────────────────┐
  │                    TRANSISTOR                               │
  │              (Saklar elektronik: ON/OFF)                    │
  └─────────────────────────────────────────────────────────────┘

  Setiap lapisan hanya perlu tahu cara berkomunikasi
  dengan lapisan LANGSUNG di atas dan di bawahnya.
```

---

## SEKSI 09 — SIMPLE EXAMPLE: LOGIKA BOOLEAN

### Gerbang Logika Dasar

Boolean Algebra menggunakan variabel yang hanya bernilai TRUE (1) atau FALSE (0). Ada 6 operasi dasar:

#### AND Gate (Konjungsi)

```
Simbol:  A ──┐
             ├── AND ──── Y
         B ──┘

Aturan: Y = 1 HANYA JIKA A=1 DAN B=1

Truth Table:
┌───┬───┬───────┐
│ A │ B │ A AND B│
├───┼───┼───────┤
│ 0 │ 0 │   0   │
│ 0 │ 1 │   0   │
│ 1 │ 0 │   0   │
│ 1 │ 1 │   1   │  ← Hanya ini yang menghasilkan 1
└───┴───┴───────┘

Analogi: Pintu terbuka JIKA kartu valid DAN PIN benar
```

#### OR Gate (Disjungsi)

```
Simbol:  A ──┐
             ├── OR ──── Y
         B ──┘

Aturan: Y = 1 JIKA A=1 ATAU B=1 (atau keduanya)

Truth Table:
┌───┬───┬──────┐
│ A │ B │ A OR B│
├───┼───┼──────┤
│ 0 │ 0 │  0   │  ← Hanya ini yang menghasilkan 0
│ 0 │ 1 │  1   │
│ 1 │ 0 │  1   │
│ 1 │ 1 │  1   │
└───┴───┴──────┘

Analogi: Alarm berbunyi JIKA pintu terbuka ATAU jendela pecah
```

#### NOT Gate (Negasi/Inverter)

```
Simbol:  A ──── NOT ──○── Y

Aturan: Y = kebalikan dari A

Truth Table:
┌───┬───────┐
│ A │ NOT A │
├───┼───────┤
│ 0 │   1   │
│ 1 │   0   │
└───┴───────┘

Analogi: Lampu menyala JIKA saklar TIDAK ditekan
```

#### XOR Gate (Exclusive OR)

```
Simbol:  A ──┐
             ├── XOR ──── Y
         B ──┘

Aturan: Y = 1 JIKA A dan B BERBEDA

Truth Table:
┌───┬───┬───────┐
│ A │ B │ A XOR B│
├───┼───┼───────┤
│ 0 │ 0 │   0   │  ← Sama → 0
│ 0 │ 1 │   1   │  ← Berbeda → 1
│ 1 │ 0 │   1   │  ← Berbeda → 1
│ 1 │ 1 │   0   │  ← Sama → 0
└───┴───┴───────┘

Kegunaan: Deteksi perbedaan, enkripsi sederhana, penjumlahan biner
```

### Ekspresi Boolean Gabungan

```
Contoh: Sistem keamanan gedung
Kondisi masuk: (Kartu_Valid AND PIN_Benar) OR Sidik_Jari_Valid

Jika:
  Kartu_Valid = 1, PIN_Benar = 0, Sidik_Jari_Valid = 1

Evaluasi:
  (1 AND 0) OR 1
= 0 OR 1
= 1  → Akses DIBERIKAN ✓
```

---

## SEKSI 10 — PRACTICAL EXAMPLE: REPRESENTASI DATA NYATA

### Contoh 1: Bagaimana Teks Direpresentasikan (ASCII & Unicode)

```
PERJALANAN KARAKTER 'A' DARI KEYBOARD KE LAYAR:

Langkah 1: Anda menekan tombol 'A' di keyboard
           ↓
Langkah 2: Keyboard mengirim sinyal ke OS
           ↓
Langkah 3: OS mencari kode ASCII untuk 'A'
           ASCII 'A' = 65₁₀ = 0x41 = 01000001₂
           ↓
Langkah 4: Byte 01000001 disimpan di memori
           ↓
Langkah 5: Program membaca byte dari memori
           ↓
Langkah 6: Font renderer mengubah kode 65 menjadi gambar huruf 'A'
           ↓
Langkah 7: Gambar ditampilkan di layar

TABEL ASCII PENTING:
┌──────────┬─────────┬──────────┬────────────┐
│ Karakter │ Desimal │   Hex    │   Biner    │
├──────────┼─────────┼──────────┼────────────┤
│   'A'    │   65    │   0x41   │ 01000001   │
│   'Z'    │   90    │   0x5A   │ 01011010   │
│   'a'    │   97    │   0x61   │ 01100001   │
│   'z'    │  122    │   0x7A   │ 01111010   │
│   '0'    │   48    │   0x30   │ 00110000   │
│   '9'    │   57    │   0x39   │ 00111001   │
│  Space   │   32    │   0x20   │ 00100000   │
│  Enter   │   10    │   0x0A   │ 00001010   │
└──────────┴─────────┴──────────┴────────────┘

POLA MENARIK:
'A' = 65 = 01000001
'a' = 97 = 01100001
Perbedaan: bit ke-5 (nilai 32)
→ Mengubah huruf besar ke kecil = SET bit ke-5
→ Mengubah huruf kecil ke besar = CLEAR bit ke-5
```

### Contoh 2: Bagaimana Warna Direpresentasikan (RGB)

```
MODEL WARNA RGB:
Setiap warna = 3 byte (Red, Green, Blue)
Setiap channel: 0–255 (8 bit)
Total: 24 bit = 16.777.216 warna berbeda

Contoh warna:
┌─────────────┬──────┬──────┬──────┬──────────────┐
│    Warna    │  R   │  G   │  B   │  Hex Code    │
├─────────────┼──────┼──────┼──────┼──────────────┤
│ Merah murni │ 255  │  0   │  0   │  #FF0000     │
│ Hijau murni │  0   │ 255  │  0   │  #00FF00     │
│ Biru murni  │  0   │  0   │ 255  │  #0000FF     │
│ Putih       │ 255  │ 255  │ 255  │  #FFFFFF     │
│ Hitam       │  0   │  0   │  0   │  #000000     │
│ Kuning      │ 255  │ 255  │  0   │  #FFFF00     │
│ Abu-abu 50% │ 128  │ 128  │ 128  │  #808080     │
└─────────────┴──────┴──────┴──────┴──────────────┘

Merah (#FF0000) dalam biner:
R: 11111111  G: 00000000  B: 00000000
= 111111110000000000000000₂

Ukuran gambar 1920×1080 (Full HD):
Pixel: 1920 × 1080 = 2.073.600 pixel
Byte per pixel: 3 (RGB)
Total: 2.073.600 × 3 = 6.220.800 byte ≈ 5.93 MB (tanpa kompresi)
```

### Contoh 3: Satuan Penyimpanan Data

```
HIERARKI SATUAN DATA:
══════════════════════

1 bit      = 0 atau 1
8 bit      = 1 Byte (B)
1.024 B    = 1 Kilobyte (KB)    = 2¹⁰ byte
1.024 KB   = 1 Megabyte (MB)    = 2²⁰ byte = 1.048.576 byte
1.024 MB   = 1 Gigabyte (GB)    = 2³⁰ byte ≈ 1 miliar byte
1.024 GB   = 1 Terabyte (TB)    = 2⁴⁰ byte ≈ 1 triliun byte
1.024 TB   = 1 Petabyte (PB)    = 2⁵⁰ byte

CATATAN PENTING — Dua Standar:
┌──────────┬──────────────────┬──────────────────────┐
│  Satuan  │ Standar Biner    │ Standar Desimal (SI) │
│          │ (IEC, digunakan  │ (digunakan produsen  │
│          │ oleh OS)         │ hard disk)           │
├──────────┼──────────────────┼──────────────────────┤
│ 1 KB     │ 1.024 byte       │ 1.000 byte           │
│ 1 MB     │ 1.048.576 byte   │ 1.000.000 byte       │
│ 1 GB     │ 1.073.741.824 B  │ 1.000.000.000 byte   │
└──────────┴──────────────────┴──────────────────────┘

Inilah mengapa hard disk 1TB terlihat hanya 931 GB di Windows!
1.000.000.000.000 ÷ 1.073.741.824 = 931,32 GB

REFERENSI UKURAN NYATA:
├── 1 karakter teks         ≈ 1 byte
├── 1 halaman teks          ≈ 2 KB
├── 1 foto smartphone       ≈ 3–5 MB
├── 1 lagu MP3              ≈ 3–8 MB
├── 1 film HD               ≈ 1–4 GB
├── 1 game modern           ≈ 50–100 GB
└── Data Facebook per hari  ≈ 4 Petabyte
```

---

## SEKSI 11 — TRADE-OFFS & DESIGN DECISIONS

### Trade-off 1: Presisi vs Ukuran dalam Representasi Angka

```
REPRESENTASI INTEGER:
─────────────────────
┌──────────┬──────┬──────────────────────────┬──────────────────────┐
│   Tipe   │ Bit  │         Range            │    Kapan Digunakan   │
├──────────┼──────┼──────────────────────────┼──────────────────────┤
│  int8    │   8  │       -128 s/d 127        │ Nilai kecil, hemat   │
│  uint8   │   8  │         0 s/d 255         │ Warna RGB, byte data │
│  int16   │  16  │    -32.768 s/d 32.767     │ Audio 16-bit         │
│  int32   │  32  │  -2,1M s/d 2,1M (approx) │ Integer umum         │
│  int64   │  64  │  -9,2E18 s/d 9,2E18       │ Timestamp, ID besar  │
└──────────┴──────┴──────────────────────────┴──────────────────────┘

MASALAH INTEGER OVERFLOW:
int8 menyimpan nilai 127, lalu ditambah 1:
01111111 + 00000001 = 10000000 = -128 (bukan 128!)
→ Ini adalah bug nyata yang menyebabkan crash sistem!
```

### Trade-off 2: Floating Point — Presisi vs Jangkauan

```
MENGAPA 0.1 + 0.2 ≠ 0.3 DALAM KOMPUTER:

0.1 dalam biner = 0.0001100110011... (berulang tak terhingga!)
Seperti 1/3 = 0.333... dalam desimal

Komputer harus memotong di suatu titik:
0.1 ≈ 0.1000000000000000055511151231257827021181583404541015625

Sehingga:
0.1 + 0.2 = 0.30000000000000004 (bukan 0.3!)

IMPLIKASI DESAIN:
├── JANGAN gunakan float untuk uang → gunakan integer (sen/rupiah)
├── JANGAN bandingkan float dengan == → gunakan epsilon comparison
├── GUNAKAN float untuk sains/grafis di mana presisi relatif cukup
└── GUNAKAN library Decimal untuk kalkulasi keuangan
```

### Trade-off 3: Encoding Teks — ASCII vs Unicode

```
ASCII:
├── Ukuran: 7 bit (128 karakter)
├── Cakupan: Bahasa Inggris + simbol dasar
├── Kelebihan: Sederhana, efisien untuk teks Inggris
└── Kekurangan: Tidak bisa merepresentasikan 'é', 'ñ', 'あ', '中', '🎉'

UNICODE (UTF-8):
├── Ukuran: 1–4 byte per karakter (variabel)
├── Cakupan: 143.859 karakter dari 154 skrip + emoji
├── Kelebihan: Universal, backward-compatible dengan ASCII
└── Kekurangan: Lebih kompleks, teks non-Latin bisa 2–4x lebih besar

UTF-8 Encoding:
┌──────────────────┬──────────────────────────────────────────┐
│   Range Unicode  │              Format Bit                  │
├──────────────────┼──────────────────────────────────────────┤
│ U+0000–U+007F    │ 0xxxxxxx (1 byte, kompatibel ASCII)      │
│ U+0080–U+07FF    │ 110xxxxx 10xxxxxx (2 byte)               │
│ U+0800–U+FFFF    │ 1110xxxx 10xxxxxx 10xxxxxx (3 byte)      │
│ U+10000–U+10FFFF │ 11110xxx 10xxxxxx 10xxxxxx 10xxxxxx (4B) │
└──────────────────┴──────────────────────────────────────────┘

'A' (U+0041) → 1 byte: 01000001
'é' (U+00E9) → 2 byte: 11000011 10101001
'あ' (U+3042) → 3 byte: 11100011 10000001 10000010
'🎉' (U+1F389) → 4 byte: 11110000 10011111 10001110 10001001
```

---

## SEKSI 12 — BEST PRACTICES

### BP-1: Selalu Tentukan Encoding Secara Eksplisit

```python
# ❌ BURUK: Bergantung pada encoding default sistem
with open('data.txt', 'r') as f:
    content = f.read()
# Bisa gagal di sistem dengan locale berbeda!

# ✅ BAIK: Selalu tentukan encoding
with open('data.txt', 'r', encoding='utf-8') as f:
    content = f.read()
```

### BP-2: Gunakan Tipe Data yang Tepat untuk Uang

```python
# ❌ BURUK: Float untuk uang
harga = 19.99
pajak = 0.11
total = harga * (1 + pajak)
print(total)  # 22.188999999999998 ← SALAH!

# ✅ BAIK: Decimal untuk uang
from decimal import Decimal
harga = Decimal('19.99')
pajak = Decimal('0.11')
total = harga * (1 + pajak)
print(total)  # 22.1889 ← Presisi terjaga

# ✅ ALTERNATIF: Integer dalam satuan terkecil (sen/rupiah)
harga_rupiah = 19990  # dalam rupiah (bukan ribu)
pajak_persen = 11     # 11%
total_rupiah = harga_rupiah * (100 + pajak_persen) // 100
```

### BP-3: Waspadai Integer Overflow

```python
# Python: Integer tidak overflow (arbitrary precision)
x = 2 ** 1000  # Bekerja dengan baik di Python

# C/Java/Go: Overflow adalah nyata!
# int8_t x = 127;
# x++;  // x = -128 ← BUG!

# ✅ Di bahasa dengan fixed-size integer:
# Selalu validasi range sebelum operasi kritis
MAX_INT32 = 2_147_483_647
nilai = 2_000_000_000
tambahan = 200_000_000
if nilai > MAX_INT32 - tambahan:
    raise OverflowError("Nilai melebihi kapasitas int32")
```

### BP-4: Gunakan Hex untuk Representasi Binary Data

```python
# ❌ BURUK: Sulit dibaca
data = b'\xff\xfe\x00\x01\xab\xcd'
print(data)  # b'\xff\xfe\x00\x01\xab\xcd'

# ✅ BAIK: Hex lebih mudah dibaca dan dianalisis
print(data.hex())          # 'fffe0001abcd'
print(data.hex(' '))       # 'ff fe 00 01 ab cd'
print(f"0x{int.from_bytes(data, 'big'):012X}")  # 0xFFFE0001ABCD
```

### BP-5: Dokumentasikan Asumsi Bit-Level

```python
# ✅ BAIK: Jelaskan operasi bit dengan komentar
def extract_rgb(color_int: int) -> tuple[int, int, int]:
    """
    Ekstrak komponen RGB dari integer 24-bit.
    Format: 0xRRGGBB
    Contoh: 0xFF8000 → (255, 128, 0) = oranye
    """
    red   = (color_int >> 16) & 0xFF  # Ambil 8 bit tertinggi
    green = (color_int >> 8)  & 0xFF  # Ambil 8 bit tengah
    blue  =  color_int        & 0xFF  # Ambil 8 bit terendah
    return red, green, blue

# Test
r, g, b = extract_rgb(0xFF8000)
assert r == 255 and g == 128 and b == 0
```

---

## SEKSI 13 — COMMON MISTAKES & MISCONCEPTIONS

### Kesalahan 1: Mengira 1 KB = 1000 Byte

```
❌ MISKONSEPSI:
"File saya 1 KB, berarti 1000 byte"

✅ FAKTA:
1 KB (Kibibyte, standar OS) = 1024 byte = 2¹⁰ byte
1 kB (Kilobyte, standar SI) = 1000 byte = 10³ byte

Produsen hard disk menggunakan 1 kB = 1000 byte (menguntungkan mereka)
OS menggunakan 1 KB = 1024 byte

Ini menyebabkan "hilangnya" kapasitas yang terlihat di OS.
```

### Kesalahan 2: Mengira Biner Hanya untuk Angka

```
❌ MISKONSEPSI:
"Biner hanya untuk merepresentasikan angka"

✅ FAKTA:
Biner merepresentasikan SEMUA jenis data:
├── Teks → encoding (ASCII, UTF-8)
├── Gambar → pixel values (RGB, RGBA)
├── Suara → sample amplitudes (PCM)
├── Video → sequence of image frames
├── Program → machine code instructions
└── Jaringan → packet bytes

Interpretasi bit bergantung pada KONTEKS, bukan bit itu sendiri.
Byte 01000001 bisa berarti:
├── Angka 65 (integer)
├── Karakter 'A' (ASCII)
├── Warna merah 65/255 (RGB channel)
└── Instruksi mesin tertentu (machine code)
```

### Kesalahan 3: Membandingkan Float dengan ==

```python
# ❌ BUG KLASIK:
x = 0.1 + 0.2
if x == 0.3:
    print("Sama")
else:
    print("Berbeda")  # ← Ini yang tercetak! Bug!

# ✅ BENAR: Gunakan epsilon comparison
import math
EPSILON = 1e-9
if math.isclose(x, 0.3, rel_tol=EPSILON):
    print("Sama (dalam toleransi)")  # ← Ini yang tercetak ✓

# Atau untuk nilai kecil:
if abs(x - 0.3) < EPSILON:
    print("Sama (dalam toleransi)")
```

### Kesalahan 4: Mengira Hex Adalah Sistem Berbeda dari Biner

```
❌ MISKONSEPSI:
"Hex dan biner adalah dua cara berbeda untuk menyimpan data"

✅ FAKTA:
Hex adalah NOTASI untuk merepresentasikan biner, bukan format penyimpanan.
Data selalu disimpan sebagai biner di hardware.
Hex hanya cara manusia membaca biner dengan lebih mudah.

0xFF = 11111111₂ = 255₁₀
Ketiganya adalah REPRESENTASI BERBEDA dari nilai yang SAMA.
```

### Kesalahan 5: Mengira Lebih Banyak Bit Selalu Lebih Baik

```
❌ MISKONSEPSI:
"Selalu gunakan int64 agar aman dari overflow"

✅ TRADE-OFF NYATA:
├── int64 menggunakan 8 byte vs int8 yang hanya 1 byte
├── Array 1 juta elemen: int8 = 1 MB, int64 = 8 MB
├── Cache CPU lebih efisien dengan data yang lebih kecil
├── Bandwidth jaringan/disk lebih hemat dengan tipe kecil
└── Untuk ML: model dengan float16 vs float32 bisa 2x lebih cepat

Pilih tipe data TERKECIL yang cukup untuk kebutuhan Anda.
```

---

## SEKSI 14 — HANDS-ON EXERCISES

### Exercise 1: Konversi Manual (Tanpa Kalkulator)

```
Konversikan bilangan berikut. Tunjukkan langkah-langkah Anda:

LEVEL 1 (Dasar):
a) 42₁₀  → biner
b) 11001010₂ → desimal
c) 0xFF → desimal
d) 200₁₀ → heksadesimal

LEVEL 2 (Menengah):
e) 0b10110111 → heksadesimal (tanpa konversi ke desimal dulu)
f) 0x3A7F → biner
g) 255 + 1 dalam int8 (8-bit signed) → apa hasilnya?
h) Berapa bit yang dibutuhkan untuk merepresentasikan 1000 nilai berbeda?

LEVEL 3 (Tantangan):
i) Warna CSS #1A2B3C → nilai R, G, B dalam desimal
j) Jika sebuah gambar 800×600 pixel dengan 32-bit RGBA,
   berapa ukurannya dalam MB (tanpa kompresi)?

JAWABAN:
a) 42 = 32+8+2 = 101010₂
b) 128+64+8+2 = 202₁₀
c) 15×16+15 = 255₁₀
d) 200 = 12×16+8 → C8 → 0xC8
e) 1011 0111 → B7 → 0xB7
f) 0011 1010 0111 1111 → 0011101001111111₂
g) 01111111 + 1 = 10000000 = -128 (overflow!)
h) 2^n ≥ 1000 → n = 10 (2^10 = 1024)
i) 1A=26, 2B=43, 3C=60 → R=26, G=43, B=60
j) 800×600×4 = 1.920.000 byte ÷ 1.048.576 ≈ 1.83 MB
```

### Exercise 2: Truth Table Completion

```
Lengkapi truth table untuk ekspresi: Y = (A AND B) OR (NOT A AND C)

┌───┬───┬───┬───────┬───────┬──────────────────────────┐
│ A │ B │ C │ A AND B│NOT A  │ NOT A AND C │     Y      │
├───┼───┼───┼───────┼───────┼─────────────┼────────────┤
│ 0 │ 0 │ 0 │       │       │             │            │
│ 0 │ 0 │ 1 │       │       │             │            │
│ 0 │ 1 │ 0 │       │       │             │            │
│ 0 │ 1 │ 1 │       │       │             │            │
│ 1 │ 0 │ 0 │       │       │             │            │
│ 1 │ 0 │ 1 │       │       │             │            │
│ 1 │ 1 │ 0 │       │       │             │            │
│ 1 │ 1 │ 1 │       │       │             │            │
└───┴───┴───┴───────┴───────┴─────────────┴────────────┘

JAWABAN:
┌───┬───┬───┬───────┬───────┬─────────────┬────────────┐
│ A │ B │ C │ A AND B│NOT A  │ NOT A AND C │     Y      │
├───┼───┼───┼───────┼───────┼─────────────┼────────────┤
│ 0 │ 0 │ 0 │   0   │   1   │      0      │     0      │
│ 0 │ 0 │ 1 │   0   │   1   │      1      │     1      │
│ 0 │ 1 │ 0 │   0   │   1   │      0      │     0      │
│ 0 │ 1 │ 1 │   0   │   1   │      1      │     1      │
│ 1 │ 0 │ 0 │   0   │   0   │      0      │     0      │
│ 1 │ 0 │ 1 │   0   │   0   │      0      │     0      │
│ 1 │ 1 │ 0 │   1   │   0   │      0      │     1      │
│ 1 │ 1 │ 1 │   1   │   0   │      0      │     1      │
└───┴───┴───┴───────┴───────┴─────────────┴────────────┘
```

### Exercise 3: Kode Python — Eksplorasi Bit

```python
# Jalankan kode ini dan amati hasilnya.
# Kemudian modifikasi untuk menjawab pertanyaan di bawah.

def analisis_byte(nilai: int) -> None:
    """Analisis representasi sebuah nilai sebagai byte."""
    assert 0 <= nilai <= 255, "Nilai harus antara 0-255"
    
    print(f"Nilai Desimal : {nilai}")
    print(f"Nilai Biner   : {nilai:08b}")
    print(f"Nilai Hex     : 0x{nilai:02X}")
    print(f"Jumlah bit '1': {bin(nilai).count('1')}")
    print(f"Bit ke-7 (MSB): {(nilai >> 7) & 1}")
    print(f"Bit ke-0 (LSB): {nilai & 1}")
    print(f"Nilai genap?  : {'Ya' if nilai % 2 == 0 else 'Tidak'}")
    print("-" * 35)

# Jalankan untuk beberapa nilai
for v in [0, 1, 127, 128, 255, 65, 97]:
    analisis_byte(v)

# PERTANYAAN:
# 1. Apa pola bit yang membedakan angka genap dan ganjil?
# 2. Mengapa 65 ('A') dan 97 ('a') hanya berbeda 1 bit?
# 3. Berapa nilai yang memiliki tepat 4 bit bernilai '1'?
```

---

## SEKSI 15 — REAL-WORLD CASE STUDY

### Kasus: Bug Ariane 5 — Overflow yang Menghancurkan Roket (1996)

```
KONTEKS:
Pada 4 Juni 1996, roket Ariane 5 meledak 37 detik setelah peluncuran.
Kerugian: $370 juta. Penyebab: integer overflow.

KRONOLOGI TEKNIS:
─────────────────
1. Ariane 5 menggunakan kembali software navigasi dari Ariane 4
2. Software menyimpan kecepatan horizontal sebagai float 64-bit
3. Kemudian mengkonversi ke integer 16-bit (signed)
4. Ariane 5 lebih cepat dari Ariane 4
5. Nilai kecepatan melebihi 32.767 (maksimum int16)
6. OVERFLOW terjadi → nilai menjadi negatif
7. Sistem navigasi mengira roket terbang ke arah salah
8. Sistem self-destruct diaktifkan

REPRESENTASI MASALAH:
float64: 40.000 (kecepatan dalam m/s)
int16 max: 32.767
Konversi: 40.000 → overflow → -25.536 (SALAH!)

PELAJARAN:
├── Selalu validasi range sebelum konversi tipe data
├── Jangan asumsikan software lama aman di konteks baru
├── Test dengan nilai ekstrem (boundary testing)
└── Overflow bukan hanya bug kecil — bisa fatal

KODE YANG SEHARUSNYA ADA:
if kecepatan > MAX_INT16:
    raise SafetyException(f"Kecepatan {kecepatan} melebihi kapasitas sensor")
```

### Kasus: Y2K — Representasi Tahun dengan 2 Digit

```
KONTEKS:
Pada 1990-an, banyak sistem menyimpan tahun hanya 2 digit:
"99" untuk 1999, "00" untuk 2000.

MASALAH:
Tahun 2000 direpresentasikan sebagai "00"
Sistem mengira "00" < "99"
→ Komputer berpikir waktu berjalan mundur!

REPRESENTASI:
Tahun 1999: "99" (2 byte)
Tahun 2000: "00" (2 byte) ← Dianggap tahun 1900!

Perbandingan: "00" < "99" → TRUE (salah!)
Seharusnya: 2000 > 1999 → TRUE

BIAYA PERBAIKAN: $300–600 miliar di seluruh dunia

PELAJARAN:
├── Representasi data harus cukup untuk seluruh siklus hidup sistem
├── Hemat 2 byte per record bisa menyebabkan kerugian triliunan
├── Selalu gunakan format standar (ISO 8601: YYYY-MM-DD)
└── Pertimbangkan masa depan saat mendesain representasi data
```

---

## SEKSI 16 — CONNECTIONS TO OTHER MODULES

### Bagaimana Modul Ini Terhubung ke Materi Berikutnya

```
MODUL INI (M01: Representasi Data & Logika Biner)
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │  M02:   │ │  M03:   │ │  M04:   │
   │ Aritme- │ │ Memori  │ │ Sistem  │
   │ tika    │ │ & Alamat│ │ Operasi │
   │ Biner   │ │ an      │ │ Dasar   │
   └────┬────┘ └────┬────┘ └────┬────┘
        │           │           │
        └───────────┼───────────┘
                    ▼
             ┌─────────────┐
             │    M05:     │
             │  Algoritma  │
             │  & Kompleks-│
             │  itas       │
             └─────────────┘

KONEKSI SPESIFIK:
M01 → M02: Logika Boolean → Sirkuit Adder (penjumlahan biner)
M01 → M03: Representasi data → Bagaimana data disimpan di RAM
M01 → M04: Bit & Byte → Sistem file, permission (chmod 755)
M01 → M05: Representasi → Analisis kompleksitas (bit complexity)

KONEKSI KE MATA KULIAH LAIN:
├── Jaringan Komputer: Protokol, header packet, checksum
├── Keamanan: Enkripsi XOR, hashing, kriptografi
├── Database: Tipe data, indexing, storage format
├── Machine Learning: Quantization, floating point precision
└── Sistem Operasi: Memory addressing, file permissions
```

---

## SEKSI 17 — SUMMARY & KEY TAKEAWAYS

### Ringkasan Konsep Utama

```
┌─────────────────────────────────────────────────────────────────┐
│                    RINGKASAN MODUL 01                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. MENGAPA BINER                                               │
│     Transistor hanya punya 2 kondisi stabil (ON/OFF)           │
│     → Sistem biner paling andal dan cepat                       │
│                                                                 │
│  2. SISTEM BILANGAN                                             │
│     Biner (2) ↔ Oktal (8) ↔ Desimal (10) ↔ Hex (16)           │
│     Konversi: pembagian berulang, nilai posisi, grup 4-bit      │
│                                                                 │
│  3. REPRESENTASI DATA                                           │
│     Teks  → ASCII/Unicode (1–4 byte per karakter)              │
│     Warna → RGB (3 byte = 16,7 juta warna)                     │
│     Angka → Integer (fixed) atau Float (IEEE 754)              │
│                                                                 │
│  4. LOGIKA BOOLEAN                                              │
│     AND: keduanya harus 1                                       │
│     OR:  salah satu harus 1                                     │
│     NOT: kebalikan                                              │
│     XOR: harus berbeda                                          │
│                                                                 │
│  5. SATUAN DATA                                                 │
│     bit → byte → KB → MB → GB → TB → PB                        │
│     Hati-hati: 1 KB = 1024 byte (bukan 1000)                   │
│                                                                 │
│  6. ABSTRAKSI                                                   │
│     Transistor → Gate → Circuit → CPU → OS → App               │
│     Setiap lapisan menyembunyikan kompleksitas di bawahnya      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5 Insight Terpenting

| # | Insight | Implikasi Praktis |
|---|---------|-------------------|
| 1 | Semua data adalah bit — interpretasi bergantung konteks | Selalu tentukan tipe data secara eksplisit |
| 2 | Float tidak presisi karena keterbatasan representasi biner | Jangan gunakan float untuk uang |
| 3 | Overflow adalah bug nyata dengan konsekuensi serius | Selalu validasi range sebelum konversi |
| 4 | Encoding teks harus eksplisit | Selalu tentukan UTF-8 saat membuka file |
| 5 | Abstraksi memungkinkan kompleksitas dikelola | Pahami lapisan yang Anda kerjakan |

---

## SEKSI 18 — SELF-ASSESSMENT QUIZ

### Quiz Formatif (10 Soal)

**Instruksi:** Jawab tanpa melihat materi. Nilai ≥ 8/10 = siap ke modul berikutnya.

```
1. Mengapa komputer menggunakan sistem biner bukan desimal?
   a) Karena biner lebih mudah dipahami manusia
   b) Karena transistor hanya memiliki dua kondisi stabil
   c) Karena biner lebih akurat untuk semua jenis data
   d) Karena desimal membutuhkan lebih banyak memori

2. Berapa nilai desimal dari 10110₂?
   a) 16    b) 20    c) 22    d) 26

3. Apa representasi heksadesimal dari 175₁₀?
   a) 0xAF  b) 0xBF  c) 0xAE  d) 0xBA

4. Operasi Boolean mana yang menghasilkan 1 HANYA ketika
   kedua input berbeda?
   a) AND   b) OR    c) XOR   d) NAND

5. Berapa byte yang dibutuhkan untuk menyimpan karakter 'é'
   dalam encoding UTF-8?
   a) 1 byte  b) 2 byte  c) 3 byte  d) 4 byte

6. Sebuah gambar 1920×1080 pixel dengan format RGB (24-bit).
   Berapa ukuran tanpa kompresi dalam MB (gunakan 1 MB = 2²⁰)?
   a) ≈ 3 MB  b) ≈ 6 MB  c) ≈ 12 MB  d) ≈ 24 MB

7. Apa yang terjadi ketika nilai 127 dalam int8 ditambah 1?
   a) Hasilnya 128
   b) Hasilnya -128 (overflow)
   c) Program otomatis menggunakan int16
   d) Hasilnya 0

8. Mengapa 0.1 + 0.2 ≠ 0.3 dalam kebanyakan bahasa pemrograman?
   a) Bug dalam compiler
   b) 0.1 tidak dapat direpresentasikan secara tepat dalam biner
   c) Floating point menggunakan basis 8, bukan 10
   d) Presisi float hanya 2 desimal

9. Berapa nilai desimal dari 0xFF?
   a) 128   b) 240   c) 255   d) 256

10. Lapisan abstraksi komputer dari bawah ke atas yang benar adalah:
    a) OS → CPU → Transistor → Aplikasi → Gate
    b) Transistor → Gate → CPU → OS → Aplikasi
    c) Gate → Transistor → OS → CPU → Aplikasi
    d) Aplikasi → OS → Gate → Transistor → CPU

KUNCI JAWABAN:
1-b, 2-c, 3-a, 4-c, 5-b, 6-b, 7-b, 8-b, 9-c, 10-b

PENJELASAN SINGKAT:
2: 1×16 + 0×8 + 1×4 + 1×2 + 0×1 = 16+4+2 = 22
3: 175 ÷ 16 = 10 sisa 15 → A=10, F=15 → 0xAF
6: 1920×1080×3 = 6.220.800 byte ÷ 1.048.576 ≈ 5.93 MB ≈ 6 MB
```

---

## SEKSI 19 — FURTHER READING & RESOURCES

### Sumber Belajar Lanjutan

#### Buku Referensi

| Judul | Penulis | Level | Fokus |
|-------|---------|-------|-------|
| *Code: The Hidden Language of Computer Hardware and Software* | Charles Petzold | Pemula | Sangat direkomendasikan — membangun dari nol |
| *Computer Organization and Design* | Patterson & Hennessy | Menengah | Arsitektur komputer lengkap |
| *The Art of Computer Programming Vol. 2* | Donald Knuth | Lanjut | Aritmatika seminumerik |
| *But How Do It Know?* | J. Clark Scott | Pemula | CPU dari gerbang logika |

#### Sumber Online Interaktif

```
VISUALISASI & SIMULASI:
├── https://www.nandgame.com/
│   → Bangun CPU dari gerbang NAND (game interaktif!)
│
├── https://logic.ly/
│   → Simulator gerbang logika visual
│
├── https://www.rapidtables.com/convert/number/
│   → Konverter bilangan dengan penjelasan langkah
│
└── https://floating-point-gui.de/
    → Penjelasan mendalam tentang floating point

VIDEO:
├── "How Computers Work" — Khan Academy (gratis)
├── "Binary, Decimal and Hexadecimal" — Computerphile (YouTube)
├── "Floating Point Numbers" — Computerphile (YouTube)
└── "Boolean Logic & Logic Gates" — Crash Course CS #3 (YouTube)
```

#### Latihan Tambahan

```python
# Proyek Mini: Implementasikan konverter bilangan sendiri
# Tanpa menggunakan fungsi built-in (bin(), hex(), int())

def desimal_ke_biner(n: int) -> str:
    """
    Konversi integer positif ke string biner.
    Implementasikan menggunakan algoritma pembagian berulang.
    
    Contoh:
    >>> desimal_ke_biner(10)
    '1010'
    >>> desimal_ke_biner(255)
    '11111111'
    """
    # TODO: Implementasikan di sini
    pass

def biner_ke_desimal(biner: str) -> int:
    """
    Konversi string biner ke integer.
    
    Contoh:
    >>> biner_ke_desimal('1010')
    10
    >>> biner_ke_desimal('11111111')
    255
    """
    # TODO: Implementasikan di sini
    pass

# Test cases
assert desimal_ke_biner(0) == '0'
assert desimal_ke_biner(1) == '1'
assert desimal_ke_biner(10) == '1010'
assert desimal_ke_biner(255) == '11111111'
assert biner_ke_desimal('0') == 0
assert biner_ke_desimal('1010') == 10
assert biner_ke_desimal('11111111') == 255
print("Semua test passed! ✓")
```

---

## SEKSI 20 — MODULE METADATA & NAVIGATION

### Metadata Modul

```yaml
module:
  id: "computer-science/ch01/m01"
  title: "Cara Komputer Berpikir — Representasi Data & Logika Biner"
  chapter: 1
  module_number: 1
  version: "1.0.0"
  created: "2024-01"
  last_updated: "2024-01"
  
  authors:
    - role: "Content Architect"
      standard: "GEMINI.md v1.0"
  
  classification:
    level: "Pemula Absolut → Menengah Awal"
    domain: "Computer Science Foundations"
    tags:
      - binary
      - boolean-logic
      - data-representation
      - number-systems
      - abstraction
      - bits-and-bytes
  
  timing:
    estimated_read: "45-60 menit"
    exercises: "30-45 menit"
    total: "90-120 menit"
  
  learning_objectives: 6
  sections: 20
  exercises: 3
  quiz_questions: 10
  case_studies: 2
```

### Navigasi Modul

```
┌─────────────────────────────────────────────────────────────────┐
│                        NAVIGASI                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ◀ SEBELUMNYA                              BERIKUTNYA ▶        │
│  (Tidak ada — ini                   M02: Aritmatika Biner      │
│   modul pertama)                    & Representasi Angka       │
│                                     computer-science/ch01/m02  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  📍 POSISI ANDA: Chapter 01 → Module 01 / 6                    │
│                                                                 │
│  Chapter 01: Fondasi Hardware & Representasi                    │
│  ├── [M01] ✅ Representasi Data & Logika Biner  ← ANDA DI SINI│
│  ├── [M02] ○  Aritmatika Biner & Representasi Angka            │
│  ├── [M03] ○  Memori: RAM, Cache, dan Hierarki Storage         │
│  ├── [M04] ○  CPU: Fetch-Decode-Execute Cycle                  │
│  ├── [M05] ○  Sistem Operasi: Abstraksi Hardware               │
│  └── [M06] ○  Jaringan: Dari Bit ke Internet                   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  CHECKLIST SEBELUM LANJUT:                                      │
│  □ Bisa konversi biner↔desimal↔hex tanpa kalkulator            │
│  □ Bisa mengisi truth table AND, OR, NOT, XOR                   │
│  □ Bisa menghitung ukuran file dari dimensi dan bit depth       │
│  □ Mengerti mengapa float tidak cocok untuk uang                │
│  □ Quiz score ≥ 8/10                                            │
│  □ Selesaikan minimal Exercise 1 dan Exercise 3                 │
└─────────────────────────────────────────────────────────────────┘
```

---

*Modul ini adalah bagian dari kurikulum **Computer Science Foundations**.*
*Dibangun sesuai standar GEMINI.md — 20 seksi, bahasa Indonesia teknis.*
*Versi 1.0.0 — Januari 2024*