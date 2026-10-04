# Computer Science Foundations
## Kurikulum Komprehensif 10 Bab — Standar GEMINI.md

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ██████╗███████╗    ███████╗ ██████╗ ██╗   ██╗███╗   ██╗██████╗  █████╗ ████████╗
██╔════╝██╔════╝    ██╔════╝██╔═══██╗██║   ██║████╗  ██║██╔══██╗██╔══██╗╚══██╔══╝
██║     ███████╗    █████╗  ██║   ██║██║   ██║██╔██╗ ██║██║  ██║███████║   ██║   
██║     ╚════██║    ██╔══╝  ██║   ██║██║   ██║██║╚██╗██║██║  ██║██╔══██║   ██║   
╚██████╗███████║    ██║     ╚██████╔╝╚██████╔╝██║ ╚████║██████╔╝██║  ██║   ██║   
 ╚═════╝╚══════╝    ╚═╝      ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═════╝ ╚═╝  ╚═╝   ╚═╝   
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    C O M P U T E R   S C I E N C E   F O U N D A T I O N S
                         Roadmap Resmi · roadmap.sh/computer-science
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 📋 Daftar Isi

- [Course Overview & Mindset](#-course-overview--mindset)
- [Prasyarat & Target Audiens](#-prasyarat--target-audiens)
- [Metrik Keberhasilan](#-metrik-keberhasilan)
- [Learning Roadmap — Diagram Pohon ASCII](#-learning-roadmap--diagram-pohon-ascii)
- [Navigasi Detail Per Bab](#-navigasi-detail-per-bab)
  - [Bab 01 — Logika Komputasi & Matematika Diskrit](#bab-01--logika-komputasi--matematika-diskrit)
  - [Bab 02 — Arsitektur Komputer & Sistem Digital](#bab-02--arsitektur-komputer--sistem-digital)
  - [Bab 03 — Sistem Operasi & Manajemen Proses](#bab-03--sistem-operasi--manajemen-proses)
  - [Bab 04 — Struktur Data Fundamental](#bab-04--struktur-data-fundamental)
  - [Bab 05 — Algoritma & Analisis Kompleksitas](#bab-05--algoritma--analisis-kompleksitas)
  - [Bab 06 — Jaringan Komputer & Protokol Internet](#bab-06--jaringan-komputer--protokol-internet)
  - [Bab 07 — Basis Data & Sistem Penyimpanan](#bab-07--basis-data--sistem-penyimpanan)
  - [Bab 08 — Rekayasa Perangkat Lunak & Paradigma Pemrograman](#bab-08--rekayasa-perangkat-lunak--paradigma-pemrograman)
  - [Bab 09 — Keamanan Komputer & Kriptografi](#bab-09--keamanan-komputer--kriptografi)
  - [Bab 10 — Komputasi Lanjutan & Tren Masa Depan](#bab-10--komputasi-lanjutan--tren-masa-depan)
- [Capstone Project Enterprise](#-capstone-project-enterprise)
- [Sumber Daya & Referensi](#-sumber-daya--referensi)
- [Kontribusi & Lisensi](#-kontribusi--lisensi)

---

## 🎯 Course Overview & Mindset

### Filosofi Kurikulum

> *"Computer Science is not about computers, any more than astronomy is about telescopes."*
> — **Edsger W. Dijkstra**

Kurikulum ini dirancang berdasarkan prinsip bahwa **Ilmu Komputer adalah ilmu berpikir**, bukan sekadar ilmu mengoperasikan mesin. Setiap konsep yang dipelajari bukan hanya relevan untuk menulis kode hari ini, melainkan untuk membangun **fondasi intelektual** yang memungkinkan Anda memahami, merancang, dan mengevaluasi sistem komputasi generasi berikutnya.

### Tiga Pilar Mindset Wajib

```
┌─────────────────────────────────────────────────────────────────┐
│                    TIGA PILAR MINDSET CS                        │
├─────────────────┬───────────────────┬───────────────────────────┤
│  🧠 ABSTRAKSI   │  ⚙️  DEKOMPOSISI  │  📐 POLA & GENERALISASI  │
├─────────────────┼───────────────────┼───────────────────────────┤
│ Kemampuan       │ Memecah masalah   │ Mengenali kesamaan        │
│ menyembunyikan  │ kompleks menjadi  │ struktural antar domain   │
│ kompleksitas    │ unit-unit kecil   │ yang berbeda              │
│ di balik        │ yang dapat        │                           │
│ antarmuka       │ diselesaikan      │                           │
│ sederhana       │ secara mandiri    │                           │
└─────────────────┴───────────────────┴───────────────────────────┘
```

### Pendekatan Pedagogis

| Dimensi | Pendekatan |
|---|---|
| **Teori → Praktik** | Setiap konsep teoritis diikuti implementasi langsung dalam kode |
| **Bottom-Up Learning** | Dimulai dari level paling rendah (logika biner) hingga sistem terdistribusi |
| **Problem-First** | Masalah nyata diperkenalkan sebelum solusi diajarkan |
| **Spaced Repetition** | Konsep kunci diulang dalam konteks berbeda di bab selanjutnya |
| **Socratic Method** | Pertanyaan pemantik disediakan di setiap modul untuk mendorong eksplorasi mandiri |

### Mengapa Computer Science Foundations Penting?

```
Tanpa Fondasi CS yang Kuat:          Dengan Fondasi CS yang Kuat:
─────────────────────────────        ────────────────────────────────
❌ Menulis kode tanpa memahami       ✅ Memilih algoritma yang tepat
   mengapa kode itu lambat              untuk skala data tertentu

❌ Memilih database secara           ✅ Merancang skema yang optimal
   sembarangan                          berdasarkan pola akses data

❌ Debugging tanpa arah              ✅ Melokalisasi bug secara
   yang jelas                           sistematis menggunakan model
                                        mental yang tepat

❌ Tidak bisa membaca paper          ✅ Mengadopsi teknologi baru
   atau dokumentasi teknis              dengan cepat karena memahami
   yang mendalam                        prinsip dasarnya
```

---

## 👥 Prasyarat & Target Audiens

### Target Audiens

```
┌──────────────────────────────────────────────────────────────┐
│                    TARGET AUDIENS UTAMA                      │
├──────────────────────────────────────────────────────────────┤
│  🎓 Mahasiswa Informatika/Teknik yang ingin memperkuat       │
│     pemahaman konseptual di luar kurikulum kampus            │
│                                                              │
│  💼 Software Engineer Junior-Mid yang ingin naik level       │
│     ke posisi Senior/Staff Engineer                          │
│                                                              │
│  🔄 Career Switcher dari bidang non-teknis yang serius       │
│     membangun karir di industri teknologi                    │
│                                                              │
│  🏗️  Tech Lead & Architect yang ingin menyegarkan dan        │
│     memperdalam fondasi teoritis                             │
└──────────────────────────────────────────────────────────────┘
```

### Prasyarat Teknis

| Level | Prasyarat | Keterangan |
|---|---|---|
| **Wajib** | Kemampuan pemrograman dasar (bahasa apapun) | Minimal mampu menulis fungsi, loop, dan kondisional |
| **Wajib** | Matematika SMA (aljabar, fungsi) | Diperlukan untuk analisis kompleksitas |
| **Disarankan** | Pengalaman menggunakan terminal/CLI | Mempercepat pemahaman bab sistem operasi |
| **Opsional** | Pengetahuan dasar jaringan | Membantu di Bab 06 |

### Estimasi Waktu Studi

```
┌─────────────────────────────────────────────────────────────┐
│                   ESTIMASI WAKTU TOTAL                      │
├──────────────────────┬──────────────────────────────────────┤
│  Intensif (full-time)│  3–4 bulan (40 jam/minggu)          │
│  Reguler (part-time) │  6–8 bulan (15–20 jam/minggu)       │
│  Santai (weekend)    │  10–12 bulan (8–10 jam/minggu)      │
├──────────────────────┴──────────────────────────────────────┤
│  Total Jam Konten: ±320 jam teori + praktik                 │
│  Capstone Project:  ±80 jam pengerjaan                      │
│  TOTAL KESELURUHAN: ±400 jam                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Metrik Keberhasilan

Peserta dinyatakan berhasil menyelesaikan kurikulum ini apabila mampu:

- [ ] **M-01** — Membuktikan kebenaran algoritma sederhana menggunakan induksi matematika
- [ ] **M-02** — Menganalisis kompleksitas waktu dan ruang suatu algoritma dalam notasi Big-O
- [ ] **M-03** — Mengimplementasikan minimal 8 struktur data dari awal (tanpa library)
- [ ] **M-04** — Menjelaskan cara kerja TCP/IP handshake dan DNS resolution secara detail
- [ ] **M-05** — Merancang skema database relasional yang ternormalisasi hingga 3NF
- [ ] **M-06** — Mengidentifikasi dan memitigasi minimal 5 jenis kerentanan keamanan umum
- [ ] **M-07** — Menyelesaikan Capstone Project Enterprise dengan skor review ≥ 80/100

---

## 🗺️ Learning Roadmap — Diagram Pohon ASCII

```
╔══════════════════════════════════════════════════════════════════════════════╗
║           COMPUTER SCIENCE FOUNDATIONS — LEARNING ROADMAP                  ║
║                        roadmap.sh/computer-science                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

                    ┌─────────────────────────┐
                    │   🚀 TITIK AWAL BELAJAR  │
                    │   (Prasyarat Terpenuhi)  │
                    └────────────┬────────────┘
                                 │
                    ╔════════════▼════════════╗
                    ║  BAB 01 · LAYER 1       ║
                    ║  Logika Komputasi &     ║
                    ║  Matematika Diskrit     ║
                    ╚════════════╤════════════╝
                                 │
                    ╔════════════▼════════════╗
                    ║  BAB 02 · LAYER 1       ║
                    ║  Arsitektur Komputer &  ║
                    ║  Sistem Digital         ║
                    ╚════════════╤════════════╝
                                 │
                    ╔════════════▼════════════╗
                    ║  BAB 03 · LAYER 2       ║
                    ║  Sistem Operasi &       ║
                    ║  Manajemen Proses       ║
                    ╚════════════╤════════════╝
                                 │
               ┌─────────────────┴──────────────────┐
               │                                    │
  ╔════════════▼════════════╗       ╔═══════════════▼═══════════╗
  ║  BAB 04 · LAYER 3       ║       ║  BAB 05 · LAYER 3         ║
  ║  Struktur Data          ║       ║  Algoritma &              ║
  ║  Fundamental            ║       ║  Analisis Kompleksitas    ║
  ╚════════════╤════════════╝       ╚═══════════════╤═══════════╝
               │                                    │
               └─────────────────┬──────────────────┘
                                 │
               ┌─────────────────┴──────────────────┐
               │                                    │
  ╔════════════▼════════════╗       ╔═══════════════▼═══════════╗
  ║  BAB 06 · LAYER 4       ║       ║  BAB 07 · LAYER 4         ║
  ║  Jaringan Komputer &    ║       ║  Basis Data &             ║
  ║  Protokol Internet      ║       ║  Sistem Penyimpanan       ║
  ╚════════════╤════════════╝       ╚═══════════════╤═══════════╝
               │                                    │
               └─────────────────┬──────────────────┘
                                 │
                    ╔════════════▼════════════╗
                    ║  BAB 08 · LAYER 5       ║
                    ║  Rekayasa Perangkat     ║
                    ║  Lunak & Paradigma      ║
                    ║  Pemrograman            ║
                    ╚════════════╤════════════╝
                                 │
                    ╔════════════▼════════════╗
                    ║  BAB 09 · LAYER 5       ║
                    ║  Keamanan Komputer &    ║
                    ║  Kriptografi            ║
                    ╚════════════╤════════════╝
                                 │
                    ╔════════════▼════════════╗
                    ║  BAB 10 · LAYER 6       ║
                    ║  Komputasi Lanjutan &   ║
                    ║  Tren Masa Depan        ║
                    ╚════════════╤════════════╝
                                 │
                    ╔════════════▼════════════╗
                    ║  🏆 CAPSTONE PROJECT    ║
                    ║  Enterprise-Grade       ║
                    ║  Distributed System     ║
                    ╚═════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KETERANGAN LAYER:
  Layer 1 ── Fondasi Matematis & Hardware (Bab 01–02)
  Layer 2 ── Abstraksi Sistem (Bab 03)
  Layer 3 ── Struktur Data & Algoritma — INTI CS (Bab 04–05)  ← TERPENTING
  Layer 4 ── Sistem & Infrastruktur (Bab 06–07)
  Layer 5 ── Rekayasa & Keamanan (Bab 08–09)
  Layer 6 ── Frontier & Integrasi (Bab 10)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DEPENDENSI ANTAR BAB:
  Bab 01 ──► Bab 02 ──► Bab 03 ──► Bab 04 ──► Bab 05
                                         └──────────────► Bab 06
                                         └──────────────► Bab 07
  Bab 04 + Bab 05 + Bab 06 + Bab 07 ──────────────────► Bab 08
  Bab 08 ──────────────────────────────────────────────► Bab 09
  Semua Bab ───────────────────────────────────────────► Bab 10
  Semua Bab ───────────────────────────────────────────► CAPSTONE
```

---

## 📚 Navigasi Detail Per Bab

### Legenda Status & Tingkat Kesulitan

```
Status Modul:  📖 Teori   💻 Praktik   🧪 Lab   📝 Kuis   🏋️ Latihan
Kesulitan:     ⭐ Dasar   ⭐⭐ Menengah   ⭐⭐⭐ Lanjutan   ⭐⭐⭐⭐ Expert
Estimasi:      ⏱️ [X jam]
```

---

## BAB 01 — Logika Komputasi & Matematika Diskrit

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 01  │  Logika Komputasi & Matematika Diskrit                           │
├──────────┼──────────────────────────────────────────────────────────────────┤
│  Layer   │  1 — Fondasi Matematis                                           │
│  Level   │  ⭐⭐ Menengah                                                    │
│  Durasi  │  ⏱️ 28–35 jam                                                    │
│  Prasyarat│ Matematika SMA, Kemampuan berpikir logis                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Matematika Diskrit adalah bahasa ibu Ilmu Komputer. Bab ini membangun kemampuan berpikir formal yang menjadi fondasi untuk memahami algoritma, struktur data, kriptografi, dan teori komputasi. Tanpa bab ini, semua bab selanjutnya akan terasa seperti menghafal resep tanpa memahami kimia di baliknya.

**Kompetensi yang Dicapai:**
- Menulis dan mengevaluasi ekspresi logika proposisional dan predikat
- Membuktikan kebenaran pernyataan matematis menggunakan berbagai teknik
- Mengaplikasikan teori himpunan, relasi, dan fungsi dalam konteks pemrograman
- Menganalisis masalah kombinatorik untuk estimasi kompleksitas

---

#### Modul 01.1 — Logika Proposisional, Predikat & Teknik Pembuktian

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐ Menengah  |  ⏱️ 10–12 jam
```

**📂 Path:** [`bab-01/modul-01-logika-proposisional/`](./bab-01/modul-01-logika-proposisional/)

**Topik yang Dibahas:**

```
01.1.1  Proposisi, Nilai Kebenaran & Tabel Kebenaran
        ├── Operator logika: AND (∧), OR (∨), NOT (¬), XOR (⊕)
        ├── Implikasi (→) dan Biimplikasi (↔)
        ├── Tautologi, Kontradiksi, dan Kontingensi
        └── Ekuivalensi logis & Hukum De Morgan

01.1.2  Logika Predikat (First-Order Logic)
        ├── Kuantor Universal (∀) dan Eksistensial (∃)
        ├── Negasi kuantor bersarang
        ├── Translasi bahasa natural ↔ logika formal
        └── Aplikasi dalam spesifikasi perangkat lunak (pre/post-condition)

01.1.3  Teknik Pembuktian Matematis
        ├── Bukti langsung (Direct Proof)
        ├── Bukti kontrapositif (Contrapositive)
        ├── Bukti kontradiksi (Proof by Contradiction)
        ├── Induksi Matematika (Weak & Strong Induction)
        └── Bukti dengan kasus (Proof by Cases)
```

**🧪 Lab Praktik:**
```python
# Lab 01.1 — Implementasi Truth Table Generator
# File: bab-01/modul-01-logika-proposisional/lab/truth_table_generator.py

def generate_truth_table(expression: str, variables: list[str]) -> None:
    """
    Menghasilkan tabel kebenaran untuk ekspresi logika yang diberikan.
    
    Contoh penggunaan:
    >>> generate_truth_table("(p AND q) OR (NOT p)", ["p", "q"])
    
    Output yang diharapkan:
    ┌───┬───┬──────────────────────┐
    │ p │ q │ (p ∧ q) ∨ (¬p)      │
    ├───┼───┼──────────────────────┤
    │ T │ T │         T            │
    │ T │ F │         F            │
    │ F │ T │         T            │
    │ F │ F │         T            │
    └───┴───┴──────────────────────┘
    """
    pass  # Implementasi oleh peserta
```

**📝 Kuis Formatif:** [`bab-01/modul-01-logika-proposisional/kuis/kuis-01.1.md`](./bab-01/modul-01-logika-proposisional/kuis/kuis-01.1.md)

**🏋️ Latihan Mandiri:**
1. Buktikan bahwa `¬(p ∨ q) ≡ (¬p ∧ ¬q)` menggunakan tabel kebenaran DAN aljabar logika
2. Gunakan induksi matematika untuk membuktikan: `∑(i=1 to n) i = n(n+1)/2`
3. Terjemahkan spesifikasi fungsi `binary_search` ke dalam logika predikat formal

---

#### Modul 01.2 — Teori Himpunan, Relasi, Fungsi & Graf Dasar

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐ Menengah  |  ⏱️ 10–12 jam
```

**📂 Path:** [`bab-01/modul-02-himpunan-relasi-fungsi/`](./bab-01/modul-02-himpunan-relasi-fungsi/)

**Topik yang Dibahas:**

```
01.2.1  Teori Himpunan
        ├── Notasi himpunan, himpunan kosong, himpunan semesta
        ├── Operasi: Union (∪), Intersection (∩), Difference (\), Complement
        ├── Power Set dan Cartesian Product
        └── Prinsip Inklusi-Eksklusi

01.2.2  Relasi & Propertinya
        ├── Relasi biner dan representasi matriks/graf
        ├── Properti: Refleksif, Simetris, Antisimetris, Transitif
        ├── Relasi Ekuivalensi & Kelas Ekuivalensi
        └── Relasi Order Parsial & Total (Poset, Hasse Diagram)

01.2.3  Fungsi & Klasifikasinya
        ├── Injektif (one-to-one), Surjektif (onto), Bijektif
        ├── Komposisi fungsi dan fungsi invers
        ├── Fungsi rekursif dan definisi rekursif
        └── Aplikasi: Hash function sebagai fungsi matematis

01.2.4  Pengantar Teori Graf
        ├── Graf berarah (digraph) dan tak berarah
        ├── Terminologi: vertex, edge, degree, path, cycle
        ├── Representasi: Adjacency Matrix vs Adjacency List
        └── Konektivitas dan komponen terhubung
```

**🧪 Lab Praktik:**
```python
# Lab 01.2 — Set Operations & Relation Analyzer
# File: bab-01/modul-02-himpunan-relasi-fungsi/lab/

# Bagian A: Implementasi operasi himpunan dari scratch (tanpa built-in set)
class CustomSet:
    def union(self, other: 'CustomSet') -> 'CustomSet': ...
    def intersection(self, other: 'CustomSet') -> 'CustomSet': ...
    def power_set(self) -> list['CustomSet']: ...

# Bagian B: Analisis properti relasi
def analyze_relation(relation: list[tuple], domain: list) -> dict:
    """
    Mengembalikan dict berisi properti relasi:
    {'reflexive': bool, 'symmetric': bool, 
     'antisymmetric': bool, 'transitive': bool,
     'equivalence': bool, 'partial_order': bool}
    """
    pass
```

**📝 Kuis Formatif:** [`bab-01/modul-02-himpunan-relasi-fungsi/kuis/kuis-01.2.md`](./bab-01/modul-02-himpunan-relasi-fungsi/kuis/kuis-01.2.md)

---

#### Modul 01.3 — Kombinatorik, Probabilitas Diskrit & Teori Bilangan

```
📖 Teori + 💻 Praktik
⭐⭐⭐ Lanjutan  |  ⏱️ 8–11 jam
```

**📂 Path:** [`bab-01/modul-03-kombinatorik-probabilitas/`](./bab-01/modul-03-kombinatorik-probabilitas/)

**Topik yang Dibahas:**

```
01.3.1  Kombinatorik
        ├── Prinsip perkalian dan penjumlahan
        ├── Permutasi (dengan/tanpa pengulangan)
        ├── Kombinasi dan Koefisien Binomial
        └── Aplikasi: Analisis kasus terburuk algoritma

01.3.2  Probabilitas Diskrit
        ├── Ruang sampel, kejadian, dan probabilitas
        ├── Probabilitas bersyarat dan Teorema Bayes
        ├── Variabel acak diskrit dan ekspektasi
        └── Aplikasi: Analisis algoritma probabilistik (QuickSort average case)

01.3.3  Teori Bilangan Dasar
        ├── Keterbagian, GCD, LCM (Algoritma Euclidean)
        ├── Bilangan prima dan Sieve of Eratosthenes
        ├── Aritmetika modular dan kongruensi
        └── Aplikasi: Fondasi kriptografi RSA
```

**🏋️ Latihan Mandiri:**
1. Hitung berapa banyak password 8 karakter yang mungkin dengan aturan tertentu
2. Implementasikan Algoritma Euclidean Extended untuk mencari invers modular
3. Analisis probabilitas collision pada hash table dengan load factor berbeda

**📝 Evaluasi Bab 01:** [`bab-01/evaluasi-bab-01.md`](./bab-01/evaluasi-bab-01.md)

---

## BAB 02 — Arsitektur Komputer & Sistem Digital

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 02  │  Arsitektur Komputer & Sistem Digital                            │
├──────────┼──────────────────────────────────────────────────────────────────┤
│  Layer   │  1 — Fondasi Hardware                                            │
│  Level   │  ⭐⭐ Menengah                                                    │
│  Durasi  │  ⏱️ 30–38 jam                                                    │
│  Prasyarat│ Bab 01 (Logika Proposisional)                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Memahami cara komputer bekerja di level hardware memberikan intuisi yang tak ternilai saat melakukan optimasi performa, debugging masalah memori, atau merancang sistem yang efisien. Bab ini menjembatani dunia logika abstrak dengan realitas fisik mesin komputasi.

**Kompetensi yang Dicapai:**
- Mengkonversi bilangan antar sistem bilangan (biner, oktal, heksadesimal, desimal)
- Merancang rangkaian logika kombinasional dan sekuensial sederhana
- Menjelaskan arsitektur Von Neumann dan siklus fetch-decode-execute
- Menganalisis hierarki memori dan implikasinya terhadap performa program

---

#### Modul 02.1 — Sistem Bilangan, Representasi Data & Gerbang Logika

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐ Menengah  |  ⏱️ 10–12 jam
```

**📂 Path:** [`bab-02/modul-01-sistem-bilangan-gerbang-logika/`](./bab-02/modul-01-sistem-bilangan-gerbang-logika/)

**Topik yang Dibahas:**

```
02.1.1  Sistem Bilangan
        ├── Biner (Base-2), Oktal (Base-8), Heksadesimal (Base-16)
        ├── Konversi antar basis bilangan
        ├── Representasi bilangan negatif: Sign-Magnitude, One's Complement,
        │   Two's Complement
        └── Representasi bilangan pecahan: Fixed-point & Floating-point (IEEE 754)

02.1.2  Representasi Data dalam Komputer
        ├── Representasi karakter: ASCII, Unicode (UTF-8, UTF-16, UTF-32)
        ├── Representasi gambar: Bitmap, piksel, color depth
        ├── Representasi audio: Sampling, quantization, bit rate
        └── Kompresi data: Lossless vs Lossy (konsep dasar)

02.1.3  Gerbang Logika & Aljabar Boolean
        ├── Gerbang dasar: AND, OR, NOT, NAND, NOR, XOR, XNOR
        ├── Aljabar Boolean: Aksioma, Teorema, Hukum De Morgan
        ├── Penyederhanaan ekspresi Boolean (Karnaugh Map)
        └── Implementasi gerbang logika dengan transistor (konsep)
```

**🧪 Lab Praktik:**
```python
# Lab 02.1 — Bit Manipulation & IEEE 754 Visualizer
# File: bab-02/modul-01-sistem-bilangan-gerbang-logika/lab/

def to_twos_complement(n: int, bits: int = 8) -> str:
    """Konversi integer ke representasi Two's Complement."""
    pass

def ieee754_breakdown(f: float) -> dict:
    """
    Breakdown representasi IEEE 754 single precision.
    Returns: {'sign': int, 'exponent': int, 'mantissa': str, 
              'actual_value': float}
    """
    pass

def karnaugh_map_simplify(truth_table: list[int]) -> str:
    """Sederhanakan ekspresi Boolean menggunakan K-Map 2/3/4 variabel."""
    pass
```

---

#### Modul 02.2 — Arsitektur CPU, Hierarki Memori & Instruksi Set

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐⭐ Lanjutan  |  ⏱️ 12–15 jam
```

**📂 Path:** [`bab-02/modul-02-arsitektur-cpu-memori/`](./bab-02/modul-02-arsitektur-cpu-memori/)

**Topik yang Dibahas:**

```
02.2.1  Arsitektur Von Neumann & Harvard
        ├── Komponen utama: CPU, Memory, I/O, Bus
        ├── Siklus instruksi: Fetch → Decode → Execute → Write-back
        ├── Register: General Purpose, Program Counter, Stack Pointer,
        │   Instruction Register, Flag Register
        └── Perbedaan Von Neumann vs Harvard Architecture

02.2.2  Central Processing Unit (CPU)
        ├── Arithmetic Logic Unit (ALU): operasi aritmetika & logika
        ├── Control Unit: hardwired vs microprogrammed
        ├── Pipeline: IF, ID, EX, MEM, WB stages
        ├── Hazard: Data hazard, Control hazard, Structural hazard
        └── Superscalar, Out-of-Order Execution, Branch Prediction

02.2.3  Hierarki Memori
        ├── Register → L1 Cache → L2 Cache → L3 Cache → RAM → SSD → HDD
        ├── Prinsip lokalitas: Temporal & Spatial Locality
        ├── Cache mapping: Direct-mapped, Set-associative, Fully-associative
        ├── Cache replacement policy: LRU, FIFO, Random
        └── Implikasi terhadap penulisan kode yang cache-friendly

02.2.4  Instruction Set Architecture (ISA)
        ├── RISC vs CISC: filosofi dan trade-off
        ├── Pengantar Assembly Language (x86-64 / ARM)
        ├── Addressing modes: Immediate, Register, Direct, Indirect
        └── Calling convention dan stack frame
```

**🧪 Lab Praktik:**
```nasm
; Lab 02.2 — Assembly Language Exploration
; File: bab-02/modul-02-arsitektur-cpu-memori/lab/

; Tugas 1: Implementasikan fungsi faktorial dalam x86-64 Assembly
; Tugas 2: Analisis output compiler (gcc -O0 vs -O2) untuk fungsi C sederhana
; Tugas 3: Ukur cache miss rate menggunakan perf atau valgrind --tool=cachegrind
;          untuk dua implementasi matrix multiplication yang berbeda urutan loop-nya
```

---

#### Modul 02.3 — Rangkaian Digital, ALU Sederhana & Simulasi CPU

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐⭐ Lanjutan  |  ⏱️ 8–11 jam
```

**📂 Path:** [`bab-02/modul-03-rangkaian-digital-simulasi/`](./bab-02/modul-03-rangkaian-digital-simulasi/)

**Topik yang Dibahas:**

```
02.3.1  Rangkaian Kombinasional
        ├── Half Adder & Full Adder
        ├── Ripple Carry Adder & Carry Lookahead Adder
        ├── Multiplexer (MUX) & Demultiplexer (DEMUX)
        └── Decoder & Encoder

02.3.2  Rangkaian Sekuensial
        ├── Flip-flop: SR, D, JK, T
        ├── Register dan Shift Register
        ├── Counter: Synchronous & Asynchronous
        └── Finite State Machine (FSM): Moore vs Mealy

02.3.3  Simulasi CPU Sederhana
        ├── Implementasi CPU 8-bit sederhana dalam Python/JavaScript
        ├── Instruction set minimal: LOAD, STORE, ADD, SUB, JMP, HALT
        ├── Assembler sederhana untuk CPU buatan sendiri
        └── Menjalankan program sederhana di atas CPU simulasi
```

**🧪 Lab Utama — Mini CPU Simulator:**
```python
# Lab 02.3 — 8-bit CPU Simulator
# File: bab-02/modul-03-rangkaian-digital-simulasi/lab/cpu_simulator.py

class CPU8Bit:
    """
    Simulasi CPU 8-bit dengan:
    - 4 register general purpose (R0–R3)
    - 256 byte memory
    - Instruction set: LOAD, STORE, ADD, SUB, AND, OR, JMP, JZ, HALT
    - Flag register: Zero, Carry, Negative
    """
    def __init__(self): ...
    def fetch(self) -> int: ...
    def decode(self, instruction: int) -> tuple: ...
    def execute(self, opcode: int, operands: tuple) -> None: ...
    def run(self, program: list[int]) -> None: ...
    def dump_state(self) -> None: ...
```

**📝 Evaluasi Bab 02:** [`bab-02/evaluasi-bab-02.md`](./bab-02/evaluasi-bab-02.md)

---

## BAB 03 — Sistem Operasi & Manajemen Proses

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 03  │  Sistem Operasi & Manajemen Proses                               │
├──────────┼──────────────────────────────────────────────────────────────────┤
│  Layer   │  2 — Abstraksi Sistem                                            │
│  Level   │  ⭐⭐⭐ Lanjutan                                                  │
│  Durasi  │  ⏱️ 35–42 jam                                                    │
│  Prasyarat│ Bab 02 (Arsitektur Komputer)                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Sistem Operasi adalah lapisan abstraksi paling fundamental yang memungkinkan program berjalan tanpa harus mengelola hardware secara langsung. Pemahaman mendalam tentang OS adalah kunci untuk menulis program yang efisien, aman, dan dapat diandalkan.

---

#### Modul 03.1 — Proses, Thread & Penjadwalan CPU

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐⭐ Lanjutan  |  ⏱️ 12–15 jam
```

**📂 Path:** [`bab-03/modul-01-proses-thread-penjadwalan/`](./bab-03/modul-01-proses-thread-penjadwalan/)

**Topik yang Dibahas:**

```
03.1.1  Proses & Process Control Block (PCB)
        ├── Definisi proses vs program
        ├── State diagram proses: New, Ready, Running, Waiting, Terminated
        ├── Process Control Block: PID, state, registers, memory maps
        ├── Context switching: mekanisme dan overhead
        └── Operasi proses: fork(), exec(), wait(), exit()

03.1.2  Thread & Multithreading
        ├── Thread vs Proses: shared resources dan isolasi
        ├── User-level threads vs Kernel-level threads
        ├── Model multithreading: Many-to-One, One-to-One, Many-to-Many
        ├── Thread pool pattern
        └── Masalah thread safety dan race condition

03.1.3  Algoritma Penjadwalan CPU
        ├── FCFS (First-Come, First-Served)
        ├── SJF (Shortest Job First) — preemptive & non-preemptive
        ├── Round Robin dengan time quantum
        ├── Priority Scheduling (dengan aging untuk mencegah starvation)
        ├── Multilevel Queue & Multilevel Feedback Queue
        └── Metrik evaluasi: Throughput, Turnaround Time, Waiting Time,
            Response Time
```

**🧪 Lab Praktik:**
```python
# Lab 03.1 — CPU Scheduler Simulator
# File: bab-03/modul-01-proses-thread-penjadwalan/lab/scheduler_sim.py

class Process:
    def __init__(self, pid: int, arrival: int, burst: int, priority: int = 0):
        self.pid = pid
        self.arrival_time = arrival
        self.burst_time = burst
        self.priority = priority
        self.waiting_time = 0
        self.turnaround_time = 0

class CPUScheduler:
    def fcfs(self, processes: list[Process]) -> dict: ...
    def sjf_preemptive(self, processes: list[Process]) -> dict: ...
    def round_robin(self, processes: list[Process], quantum: int) -> dict: ...
    def priority_aging(self, processes: list[Process]) -> dict: ...
    def generate_gantt_chart(self, schedule: list) -> str: ...
    def compute_metrics(self, processes: list[Process]) -> dict: ...
```

---

#### Modul 03.2 — Sinkronisasi, Deadlock & Manajemen Memori

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐⭐ Lanjutan  |  ⏱️ 13–16 jam
```

**📂 Path:** [`bab-03/modul-02-sinkronisasi-deadlock-memori/`](./bab-03/modul-02-sinkronisasi-deadlock-memori/)

**Topik yang Dibahas:**

```
03.2.1  Sinkronisasi & Critical Section
        ├── Race condition dan critical section problem
        ├── Syarat solusi: Mutual Exclusion, Progress, Bounded Waiting
        ├── Solusi perangkat lunak: Peterson's Algorithm
        ├── Solusi hardware: Test-and-Set, Compare-and-Swap (CAS)
        ├── Mutex, Semaphore (binary & counting)
        ├── Monitor dan Condition Variable
        └── Masalah klasik: Producer-Consumer, Readers-Writers,
            Dining Philosophers

03.2.2  Deadlock
        ├── Kondisi Coffman: Mutual Exclusion, Hold & Wait,
        │   No Preemption, Circular Wait
        ├── Resource Allocation Graph (RAG)
        ├── Strategi: Prevention, Avoidance (Banker's Algorithm),
        │   Detection & Recovery, Ignorance (Ostrich Algorithm)
        └── Livelock dan Starvation

03.2.3  Manajemen Memori
        ├── Logical vs Physical Address Space
        ├── Binding: Compile-time, Load-time, Execution-time
        ├── Teknik alokasi: Contiguous (Fixed/Variable Partition),
        │   Segmentation, Paging
        ├── Page Table: Single-level, Multi-level, Inverted
        ├── Translation Lookaside Buffer (TLB)
        └── Virtual Memory: Demand Paging, Page Fault, Page Replacement
            (FIFO, Optimal, LRU, Clock Algorithm)
```

**🧪 Lab Praktik:**
```python
# Lab 03.2A — Dining Philosophers dengan berbagai solusi
# File: bab-03/modul-02-sinkronisasi-deadlock-memori/lab/dining_philosophers.py

import threading
import time

class DiningPhilosophers:
    """
    Implementasikan solusi Dining Philosophers menggunakan:
    1. Naive approach (demonstrasi deadlock)
    2. Resource hierarchy solution
    3. Arbitrator solution (menggunakan semaphore)
    4. Chandy/Misra solution (tanpa central coordinator)
    """
    pass

# Lab 03.2B — Banker's Algorithm
# File: bab-03/modul-02-sinkronisasi-deadlock-memori/lab/bankers_algorithm.py

class BankersAlgorithm:
    def __init__(self, available: list, max_demand: list, allocation: list):
        ...
    
    def is_safe_state(self) -> tuple[bool, list]:
        """Cek apakah sistem dalam safe state. Return (is_safe, safe_sequence)."""
        pass
    
    def request_resources(self, process_id: int, request: list) -> bool:
        """Proses permintaan resource. Return True jika dikabulkan."""
        pass
```

---

#### Modul 03.3 — Sistem File, I/O & Virtualisasi

```
📖 Teori + 💻 Praktik
⭐⭐⭐ Lanjutan  |  ⏱️ 10–11 jam
```

**📂 Path:** [`bab-03/modul-03-sistem-file-io-virtualisasi/`](./bab-03/modul-03-sistem-file-io-virtualisasi/)

**Topik yang Dibahas:**

```
03.3.1  Sistem File
        ├── Abstraksi file: nama, tipe, atribut, operasi
        ├── Struktur direktori: single-level, two-level, tree, acyclic graph
        ├── Implementasi: FAT, inode (ext4), NTFS, APFS
        ├── Alokasi blok: Contiguous, Linked, Indexed (i-node)
        ├── Free space management: Bitmap, Linked List
        └── Journaling dan crash consistency

03.3.2  Subsistem I/O
        ├── Teknik I/O: Polling, Interrupt-driven, DMA
        ├── Device driver dan kernel I/O subsystem
        ├── Buffering, Caching, Spooling
        └── Disk scheduling: FCFS, SSTF, SCAN, C-SCAN, LOOK

03.3.3  Virtualisasi & Kontainerisasi
        ├── Hypervisor Type 1 vs Type 2
        ├── Hardware-assisted virtualization (Intel VT-x, AMD-V)
        ├── Kontainer vs VM: trade-off isolasi dan overhead
        ├── Namespace dan cgroups (fondasi Docker)
        └── Pengantar unikernel dan WebAssembly sebagai runtime
```

**📝 Evaluasi Bab 03:** [`bab-03/evaluasi-bab-03.md`](./bab-03/evaluasi-bab-03.md)

---

## BAB 04 — Struktur Data Fundamental

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 04  │  Struktur Data Fundamental                                       │
├──────────┼──────────────────────────────────────────────────────────────────┤
│  Layer   │  3 — INTI CS (Terpenting)                                        │
│  Level   │  ⭐⭐⭐ Lanjutan                                                  │
│  Durasi  │  ⏱️ 40–50 jam                                                    │
│  Prasyarat│ Bab 01 (Matematika Diskrit), Bab 03 (Memori)                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Struktur data adalah cara kita mengorganisasi data di memori untuk memungkinkan operasi tertentu dilakukan secara efisien. Pilihan struktur data yang tepat seringkali membedakan solusi O(n²) dengan O(n log n) — perbedaan antara program yang berjalan dalam 1 detik vs 1 jam untuk input besar.

> ⚠️ **Perhatian Penting:** Semua struktur data di bab ini **wajib diimplementasikan dari awal** (dari scratch) tanpa menggunakan library bawaan bahasa. Tujuannya adalah memahami mekanisme internal, bukan sekadar menggunakan API.

---

#### Modul 04.1 — Array, Linked List, Stack & Queue

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐ Menengah  |  ⏱️ 14–17 jam
```

**📂 Path:** [`bab-04/modul-01-array-linkedlist-stack-queue/`](./bab-04/modul-01-array-linkedlist-stack-queue/)

**Topik yang Dibahas:**

```
04.1.1  Array & Dynamic Array
        ├── Array statis: alokasi memori, akses O(1), cache locality
        ├── Dynamic Array (ArrayList/Vector): amortized O(1) append
        ├── Analisis amortized: Aggregate, Accounting, Potential method
        └── Multidimensional array: row-major vs column-major order

04.1.2  Linked List
        ├── Singly Linked List: node, head, tail, traversal O(n)
        ├── Doubly Linked List: prev pointer, O(1) delete dengan node reference
        ├── Circular Linked List: aplikasi di round-robin scheduler
        ├── Skip List: probabilistic data structure O(log n) average
        └── Memory layout: pointer overhead vs cache efficiency

04.1.3  Stack
        ├── LIFO principle, operasi: push, pop, peek, isEmpty
        ├── Implementasi dengan array vs linked list
        ├── Aplikasi: function call stack, undo/redo, expression evaluation,
        │   backtracking, DFS iteratif
        └── Monotonic Stack: teknik lanjutan untuk masalah "next greater element"

04.1.4  Queue & Variannya
        ├── FIFO principle, operasi: enqueue, dequeue, front, rear
        ├── Circular Queue: mengatasi false overflow
        ├── Deque (Double-Ended Queue): operasi di kedua ujung
        ├── Priority Queue: konsep (implementasi detail di Bab 04.2)
        └── Aplikasi: BFS, task scheduling, buffer I/O
```

**🧪 Lab Implementasi:**
```python
# Lab 04.1 — Implementasi dari Scratch
# File: bab-04/modul-01-array-linkedlist-stack-queue/lab/

# Tugas 1: Dynamic Array dengan amortized analysis
class DynamicArray:
    def __init__(self): 
        self._capacity = 1
        self._size = 0
        self._data = [None] * self._capacity
    
    def append(self, item) -> None: ...      # Amortized O(1)
    def insert(self, index: int, item) -> None: ...  # O(n)
    def delete(self, index: int) -> None: ...         # O(n)
    def __getitem__(self, index: int): ...            # O(1)
    def _resize(self, new_capacity: int) -> None: ... # Internal

# Tugas 2: Doubly Linked List lengkap
class DoublyLinkedList:
    class Node:
        def __init__(self, data):
            self.data = data
            self.prev = None
            self.next = None
    
    def insert_front(self, data) -> None: ...
    def insert_back(self, data) -> None: ...
    def insert_after(self, node: 'Node', data) -> None: ...
    def delete(self, node: 'Node') -> None: ...  # O(1) dengan node reference
    def reverse(self) -> None: ...
    def find_middle(self): ...  # Floyd's tortoise and hare

# Tugas 3: Aplikasi Stack — Evaluator Ekspresi
class ExpressionEvaluator:
    def infix_to_postfix(self, expression: str) -> str: ...
    def evaluate_postfix(self, expression: str) -> float: ...
    def check_balanced_brackets(self, s: str) -> bool: ...
```

---

#### Modul 04.2 — Tree, Heap & Priority Queue

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐⭐ Lanjutan  |  ⏱️ 14–18 jam
```

**📂 Path:** [`bab-04/modul-02-tree-heap-priority-queue/`](./bab-04/modul-02-tree-heap-priority-queue/)

**Topik yang Dibahas:**

```
04.2.1  Binary Tree
        ├── Terminologi: root, leaf, height, depth, level, subtree
        ├── Jenis: Full, Complete, Perfect, Balanced, Degenerate
        ├── Traversal: Pre-order, In-order, Post-order, Level-order (BFS)
        ├── Rekonstruksi tree dari traversal
        └── Aplikasi: Expression tree, Huffman coding tree

04.2.2  Binary Search Tree (BST)
        ├── Properti BST: left < root < right
        ├── Operasi: Search O(h), Insert O(h), Delete O(h)
        ├── Kasus terburuk O(n) pada BST tidak seimbang
        └── Predecessor dan Successor

04.2.3  Self-Balancing BST
        ├── AVL Tree: balance factor, rotasi (LL, RR, LR, RL)
        ├── Red-Black Tree: properti, rotasi, recoloring
        ├── Perbandingan AVL vs Red-Black: kapan menggunakan mana
        └── B-Tree & B+ Tree: optimasi untuk disk storage (preview Bab 07)

04.2.4  Heap & Priority Queue
        ├── Binary Heap: Max-Heap dan Min-Heap
        ├── Representasi array: parent = (i-1)//2, children = 2i+1, 2i+2
        ├── Operasi: insert O(log n), extract-max/min O(log n),
        │   heapify O(n), build-heap O(n)
        ├── Heap Sort: in-place O(n log n)
        └── Fibonacci Heap: konsep dan aplikasi di Dijkstra's Algorithm

04.2.5  Trie (Prefix Tree)
        ├── Struktur dan operasi: insert, search, startsWith — O(L)
        ├── Compressed Trie (Patricia Tree / Radix Tree)
        └── Aplikasi: autocomplete, spell checker, IP routing
```

**🧪 Lab Implementasi:**
```python
# Lab 04.2 — Tree Implementations
# File: bab-04/modul-02-tree-heap-priority-queue/lab/

class AVLTree:
    class Node:
        def __init__(self, key):
            self.key = key
            self.left = None
            self.right = None
            self.height = 1
    
    def insert(self, key) -> None: ...
    def delete(self, key) -> None: ...
    def search(self, key) -> bool: ...
    def _rotate_right(self, z: 'Node') -> 'Node': ...
    def _rotate_left(self, z: 'Node') -> 'Node': ...
    def _get_balance(self, node: 'Node') -> int: ...
    def _rebalance(self, node: 'Node') -> 'Node': ...

class BinaryHeap:
    def __init__(self, heap_type: str = 'min'):  # 'min' or 'max'
        self._data = []
        self._type = heap_type
    
    def push(self, item) -> None: ...        # O(log n)
    def pop(self) -> any: ...               # O(log n)
    def peek(self) -> any: ...              # O(1)
    def heapify(self, array: list) -> None: ...  # O(n)
    def heap_sort(self, array: list) -> list: ... # O(n log n)
```

---

#### Modul 04.3 — Hash Table, Graf & Struktur Data Lanjutan

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐⭐⭐ Expert  |  ⏱️ 12–15 jam
```

**📂 Path:** [`bab-04/modul-03-hashtable-graf-lanjutan/`](./bab-04/modul-03-hashtable-graf-lanjutan/)

**Topik yang Dibahas:**

```
04.3.1  Hash Table
        ├── Hash function: properti (deterministic, uniform, efficient)
        ├── Collision resolution:
        │   ├── Chaining (Separate Chaining)
        │   └── Open Addressing: Linear Probing, Quadratic Probing,
        │       Double Hashing
        ├── Load factor dan rehashing
        ├── Analisis: average O(1), worst O(n)
        └── Aplikasi: dictionary, set, caching, deduplication

04.3.2  Graf (Representasi & Traversal)
        ├── Directed vs Undirected, Weighted vs Unweighted
        ├── Representasi: Adjacency Matrix O(V²), Adjacency List O(V+E)
        ├── Edge List dan Incidence Matrix
        ├── BFS: level-order traversal, shortest path unweighted
        ├── DFS: pre/post-order, topological sort, cycle detection
        └── Strongly Connected Components: Kosaraju's, Tarjan's Algorithm

04.3.3  Struktur Data Lanjutan
        ├── Disjoint Set Union (Union-Find)
        │   ├── Union by Rank
        │   └── Path Compression — amortized O(α(n)) ≈ O(1)
        ├── Segment Tree: range query & point update O(log n)
        ├── Fenwick Tree (Binary Indexed Tree): prefix sum O(log n)
        └── Bloom Filter: probabilistic membership testing
```

**🧪 Lab Implementasi:**
```python
# Lab 04.3 — Advanced Data Structures
# File: bab-04/modul-03-hashtable-graf-lanjutan/lab/

class HashTable:
    """Hash Table dengan open addressing (double hashing)."""
    def __init__(self, initial_capacity: int = 16, load_factor: float = 0.75):
        ...
    
    def put(self, key, value) -> None: ...
    def get(self, key): ...
    def delete(self, key) -> bool: ...
    def _hash1(self, key) -> int: ...
    def _hash2(self, key) -> int: ...
    def _rehash(self) -> None: ...

class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n
    
    def find(self, x: int) -> int: ...   # Path compression
    def union(self, x: int, y: int) -> bool: ...  # Union by rank
    def connected(self, x: int, y: int) -> bool: ...

class SegmentTree:
    def __init__(self, array: list, operation=sum): ...
    def query(self, left: int, right: int): ...  # O(log n)
    def update(self, index: int, value) -> None: ...  # O(log n)
    def build(self, array: list) -> None: ...  # O(n)
```

**📝 Evaluasi Bab 04:** [`bab-04/evaluasi-bab-04.md`](./bab-04/evaluasi-bab-04.md)

---

## BAB 05 — Algoritma & Analisis Kompleksitas

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 05  │  Algoritma & Analisis Kompleksitas                               │
├──────────┼──────────────────────────────────────────────────────────────────┤
│  Layer   │  3 — INTI CS (Terpenting)                                        │
│  Level   │  ⭐⭐⭐⭐ Expert                                                  │
│  Durasi  │  ⏱️ 45–55 jam                                                    │
│  Prasyarat│ Bab 01 (Matematika Diskrit), Bab 04 (Struktur Data)            │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Algoritma adalah jantung Ilmu Komputer. Bab ini tidak hanya mengajarkan algoritma-algoritma penting, tetapi lebih krusial lagi: mengajarkan **cara berpikir algoritmik** — kemampuan untuk melihat masalah baru dan merancang solusi yang efisien secara sistematis.

---

#### Modul 05.1 — Analisis Kompleksitas & Paradigma Divide and Conquer

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐⭐ Lanjutan  |  ⏱️ 15–18 jam
```

**📂 Path:** [`bab-05/modul-01-kompleksitas-divide-conquer/`](./bab-05/modul-01-kompleksitas-divide-conquer/)

**Topik yang Dibahas:**

```
05.1.1  Analisis Kompleksitas Algoritma
        ├── Notasi Asimtotik: Big-O (O), Big-Omega (Ω), Big-Theta (Θ)
        ├── Analisis kasus: terbaik, rata-rata, terburuk
        ├── Kompleksitas waktu vs ruang (space complexity)
        ├── Analisis rekursi: Recurrence Relation
        │   ├── Substitution Method
        │   ├── Recursion Tree Method
        │   └── Master Theorem: T(n) = aT(n/b) + f(n)
        └── Amortized Analysis: Aggregate, Accounting, Potential

05.1.2  Algoritma Pengurutan (Sorting)
        ├── Comparison-based sorting: lower bound Ω(n log n)
        ├── O(n²): Bubble Sort, Selection Sort, Insertion Sort
        │   └── Kapan Insertion Sort lebih baik dari Merge Sort?
        ├── O(n log n): Merge Sort, Heap Sort, Quick Sort
        │   ├── Merge Sort: stable, guaranteed O(n log n)
        │   ├── Heap Sort: in-place, O(n log n) worst case
        │   └── Quick Sort: average O(n log n), pivot selection strategies
        ├── O(n): Counting Sort, Radix Sort, Bucket Sort
        │   └── Kapan linear sorting bisa digunakan?
        └── Tim Sort: hybrid algorithm (Python's built-in sort)

05.1.3  Divide and Conquer
        ├── Template: Divide → Conquer → Combine
        ├── Binary Search: O(log n), variasi (lower/upper bound)
        ├── Merge Sort sebagai contoh D&C klasik
        ├── Strassen's Matrix Multiplication: O(n^2.807) vs O(n³)
        ├── Closest Pair of Points: O(n log n)
        └── Karatsuba Algorithm: fast multiplication O(n^1.585)
```

**🧪 Lab Praktik:**
```python
# Lab 05.1 — Sorting Algorithm Benchmarking Suite
# File: bab-05/modul-01-kompleksitas-divide-conquer/lab/

import time
import random
import matplotlib.pyplot as plt

class SortingBenchmark:
    """
    Benchmark suite untuk membandingkan algoritma sorting.
    Implementasikan semua algoritma dari scratch, kemudian:
    1. Plot waktu eksekusi vs ukuran input (n = 100 hingga 100,000)
    2. Verifikasi bahwa kurva sesuai dengan kompleksitas teoritis
    3. Identifikasi crossover point antara algoritma O(n²) dan O(n log n)
    """
    
    def bubble_sort(self, arr: list) -> list: ...
    def insertion_sort(self, arr: list) -> list: ...
    def merge_sort(self, arr: list) -> list: ...
    def quick_sort(self, arr: list, pivot_strategy: str = 'median3') -> list: ...
    def heap_sort(self, arr: list) -> list: ...
    def counting_sort(self, arr: list) -> list: ...
    def radix_sort(self, arr: list) -> list: ...
    
    def benchmark(self, sizes: list[int], trials: int = 5) -> dict: ...
    def plot_results(self, results: dict) -> None: ...
```

---

#### Modul 05.2 — Dynamic Programming & Greedy Algorithms

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐⭐⭐ Expert  |  ⏱️ 18–22 jam
```

**📂 Path:** [`bab-05/modul-02-dynamic-programming-greedy/`](./bab-05/modul-02-dynamic-programming-greedy/)

**Topik yang Dibahas:**

```
05.2.1  Dynamic Programming (DP)
        ├── Dua properti: Optimal Substructure & Overlapping Subproblems
        ├── Pendekatan: Top-Down (Memoization) vs Bottom-Up (Tabulation)
        ├── Identifikasi state dan transisi
        ├── Masalah klasik DP:
        │   ├── Fibonacci (pengantar memoization)
        │   ├── Longest Common Subsequence (LCS)
        │   ├── Longest Increasing Subsequence (LIS) — O(n log n)
        │   ├── 0/1 Knapsack Problem
        │   ├── Coin Change (minimum coins & number of ways)
        │   ├── Edit Distance (Levenshtein Distance)
        │   ├── Matrix Chain Multiplication
        │   └── Optimal Binary Search Tree
        └── DP pada Graf: Bellman-Ford, Floyd-Warshall

05.2.2  Greedy Algorithms
        ├── Greedy choice property dan optimal substructure
        ├── Perbedaan Greedy vs DP: kapan greedy benar?
        ├── Masalah klasik Greedy:
        │   ├── Activity Selection Problem
        │   ├── Fractional Knapsack
        │   ├── Huffman Coding: optimal prefix-free code
        │   ├── Minimum Spanning Tree: Kruskal's & Prim's Algorithm
        │   └── Dijkstra's Shortest Path (greedy dengan priority queue)
        └── Matroid Theory: fondasi matematis greedy algorithm
```

**🧪 Lab Praktik:**
```python
# Lab 05.2 — DP Problem Solver dengan Visualisasi
# File: bab-05/modul-02-dynamic-programming-greedy/lab/

class DPSolver:
    def lcs(self, s1: str, s2: str) -> tuple[int, str]:
        """Return (length, subsequence) dengan rekonstruksi solusi."""
        pass
    
    def edit_distance(self, s1: str, s2: str) -> tuple[int, list]:
        """Return (distance, operations) — operasi: insert/delete/replace."""
        pass
    
    def knapsack_01(self, weights: list, values: list, capacity: int) -> tuple[int, list]:
        """Return (max_value, selected_items)."""
        pass
    
    def visualize_dp_table(self, table: list[list], 
                           row_labels: list, col_labels: list) -> None:
        """Visualisasi tabel DP dalam format ASCII yang mudah dibaca."""
        pass

class HuffmanCoding:
    def encode(self, text: str) -> tuple[str, dict]:
        """Return (encoded_bits, codebook)."""
        pass
    
    def decode(self, encoded: str, codebook: dict) -> str: ...
    def compression_ratio(self, original: str, encoded: str) -> float: ...
    def visualize_tree(self) -> str: ...  # ASCII tree visualization
```

---

#### Modul 05.3 — Algoritma Graf Lanjutan & Teori Kompleksitas

```
📖 Teori + 💻 Praktik
⭐⭐⭐⭐ Expert  |  ⏱️ 12–15 jam
```

**📂 Path:** [`bab-05/modul-03-algoritma-graf-teori-kompleksitas/`](./bab-05/modul-03-algoritma-graf-teori-kompleksitas/)

**Topik yang Dibahas:**

```
05.3.1  Algoritma Graf Lanjutan
        ├── Shortest Path:
        │   ├── Dijkstra's: O((V+E) log V) dengan binary heap
        │   ├── Bellman-Ford: O(VE), mendeteksi negative cycle
        │   ├── Floyd-Warshall: O(V³), all-pairs shortest path
        │   └── A* Search: heuristic-guided shortest path
        ├── Minimum Spanning Tree:
        │   ├── Kruskal's: O(E log E) dengan Union-Find
        │   └── Prim's: O((V+E) log V) dengan priority queue
        ├── Network Flow:
        │   ├── Ford-Fulkerson Method
        │   ├── Edmonds-Karp: O(VE²)
        │   └── Aplikasi: bipartite matching, project selection
        └── Topological Sort & DAG algorithms

05.3.2  Backtracking & Branch and Bound
        ├── Template backtracking: choose, explore, unchoose
        ├── Masalah klasik: N-Queens, Sudoku Solver, Subset Sum,
        │   Graph Coloring, Hamiltonian Path
        ├── Pruning strategies untuk efisiensi
        └── Branch and Bound: optimasi backtracking

05.3.3  Teori Kompleksitas Komputasi
        ├── Kelas kompleksitas: P, NP, NP-Complete, NP-Hard
        ├── Polynomial-time reduction
        ├── Masalah NP-Complete klasik: SAT, 3-SAT, Clique, Vertex Cover,
        │   Traveling Salesman Problem (TSP), Knapsack (decision version)
        ├── Strategi menghadapi NP-Hard: Approximation, Heuristic,
        │   Parameterized, Randomized
        └── P vs NP: pertanyaan terbuka terbesar dalam CS
```

**📝 Evaluasi Bab 05:** [`bab-05/evaluasi-bab-05.md`](./bab-05/evaluasi-bab-05.md)

---

## BAB 06 — Jaringan Komputer & Protokol Internet

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 06  │  Jaringan Komputer & Protokol Internet                           │
├──────────┼──────────────────────────────────────────────────────────────────┤
│  Layer   │  4 — Sistem & Infrastruktur                                      │
│  Level   │  ⭐⭐⭐ Lanjutan                                                  │
│  Durasi  │  ⏱️ 32–40 jam                                                    │
│  Prasyarat│ Bab 03 (Sistem Operasi), Bab 04 (Struktur Data)                │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Di era modern, hampir semua perangkat lunak adalah perangkat lunak jaringan. Memahami cara data bergerak dari satu titik ke titik lain — melalui lapisan protokol, routing, dan enkripsi — adalah kompetensi wajib setiap software engineer.

---

#### Modul 06.1 — Model OSI/TCP-IP & Protokol Layer Bawah

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐ Menengah  |  ⏱️ 10–12 jam
```

**📂 Path:** [`bab-06/modul-01-model-osi-tcpip-layer-bawah/`](./bab-06/modul-01-model-osi-tcpip-layer-bawah/)

**Topik yang Dibahas:**

```
06.1.1  Model Referensi Jaringan
        ├── Model OSI 7 Layer: Physical, Data Link, Network, Transport,
        │   Session, Presentation, Application
        ├── Model TCP/IP 4 Layer: Network Access, Internet, Transport,
        │   Application
        ├── Enkapsulasi data: bit → frame → packet → segment → data
        └── Perbandingan OSI vs TCP/IP: mengapa TCP/IP yang dominan?

06.1.2  Layer Fisik & Data Link
        ├── Media transmisi: kabel tembaga, fiber optik, wireless
        ├── Encoding: NRZ, Manchester, 4B/5B
        ├── Error detection: Parity, Checksum, CRC
        ├── Error correction: Hamming Code
        ├── MAC Address dan ARP (Address Resolution Protocol)
        ├── Ethernet: CSMA/CD, frame format
        └── Switching: MAC table, VLAN, Spanning Tree Protocol

06.1.3  Layer Network — IP & Routing
        ├── IPv4: format paket, fragmentasi, TTL
        ├── IPv6: format, auto-configuration, transisi dari IPv4
        ├── Subnetting: CIDR notation, subnet mask, VLSM
        ├── ICMP: ping, traceroute, error messages
        ├── Routing: static vs dynamic
        ├── Routing protocols: RIP (Distance Vector), OSPF (Link State),
        │   BGP (Path Vector)
        └── NAT: Source NAT, Destination NAT, PAT
```

**🧪 Lab Praktik:**
```python
# Lab 06.1 — Network Packet Analyzer
# File: bab-06/modul-01-model-osi-tcpip-layer-bawah/lab/

import socket
import struct

class PacketAnalyzer:
    """
    Analisis paket jaringan menggunakan raw socket.
    Tugas:
    1. Capture dan parse Ethernet frame
    2. Decode IP header (version, TTL, protocol, src/dst IP)
    3. Decode TCP/UDP header
    4. Implementasikan CRC-32 checksum dari scratch
    5. Visualisasikan struktur paket dalam format hex dump
    """
    
    def parse_ethernet_frame(self, raw_data: bytes) -> dict: ...
    def parse_ip_packet(self, raw_data: bytes) -> dict: ...
    def parse_tcp_segment(self, raw_data: bytes) -> dict: ...
    def crc32(self, data: bytes) -> int: ...
    def hex_dump(self, data: bytes, width: int = 16) -> str: ...

# Jalankan dengan: sudo python3 packet_analyzer.py
```

---

#### Modul 06.2 — TCP, UDP & Protokol Aplikasi

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐⭐ Lanjutan  |  ⏱️ 12–15 jam
```

**📂 Path:** [`bab-06/modul-02-tcp-udp-protokol-aplikasi/`](./bab-06/modul-02-tcp-udp-protokol-aplikasi/)

**Topik yang Dibahas:**

```
06.2.1  Transport Layer — TCP
        ├── TCP segment format: sequence number, ACK, flags, window size
        ├── Three-way handshake: SYN → SYN-ACK → ACK
        ├── Four-way termination: FIN → ACK → FIN → ACK
        ├── Reliable delivery: retransmission, timeout, duplicate detection
        ├── Flow control: sliding window, receive buffer
        ├── Congestion control: Slow Start, Congestion Avoidance,
        │   Fast Retransmit, Fast Recovery (TCP Reno, TCP CUBIC)
        └── TCP state machine: LISTEN, SYN_SENT, ESTABLISHED, TIME_WAIT, dll.

06.2.2  Transport Layer — UDP & QUIC
        ├── UDP: connectionless, unreliable, low overhead
        ├── Kapan UDP lebih baik dari TCP: gaming, DNS, streaming, VoIP
        ├── Reliable UDP: implementasi reliability di atas UDP (QUIC, RUDP)
        └── QUIC: HTTP/3, 0-RTT connection, multiplexing tanpa head-of-line blocking

06.2.3  Protokol Aplikasi Penting
        ├── DNS: hierarki, recursive vs iterative query, record types
        │   (A, AAAA, CNAME, MX, TXT, NS), DNS caching, DNSSEC
        ├── HTTP/1.1: request/response, headers, methods, status codes,
        │   persistent connection, pipelining
        ├── HTTP/2: multiplexing, header compression (HPACK), server push
        ├── HTTP/3 (QUIC): eliminasi TCP head-of-line blocking
        ├── HTTPS & TLS: handshake, certificate, cipher suite
        ├── WebSocket: full-duplex communication
        └── REST vs GraphQL vs gRPC: trade-off dan use case
```

**🧪 Lab Praktik:**
```python
# Lab 06.2 — HTTP Server dari Scratch
# File: bab-06/modul-02-tcp-udp-protokol-aplikasi/lab/

import socket
import threading

class HTTPServer:
    """
    Implementasi HTTP/1.1 server minimal dari scratch menggunakan raw socket.
    Fitur yang harus diimplementasikan:
    - GET, POST, HEAD methods
    - Static file serving
    - MIME type detection
    - Keep-alive connections
    - Basic routing
    - Request logging
    """
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8080): ...
    def start(self) -> None: ...
    def handle_connection(self, conn: socket.socket, addr: tuple) -> None: ...
    def parse_request(self, raw: str) -> dict: ...
    def build_response(self, status: int, headers: dict, body: bytes) -> bytes: ...
    def route(self, method: str, path: str) -> callable: ...
```

---

#### Modul 06.3 — Keamanan Jaringan, CDN & Arsitektur Terdistribusi

```
📖 Teori + 💻 Praktik
⭐⭐⭐⭐ Expert  |  ⏱️ 10–13 jam
```

**📂 Path:** [`bab-06/modul-03-keamanan-jaringan-arsitektur-terdistribusi/`](./bab-06/modul-03-keamanan-jaringan-arsitektur-terdistribusi/)

**Topik yang Dibahas:**

```
06.3.1  Keamanan Jaringan
        ├── Serangan umum: Man-in-the-Middle, ARP Spoofing, DNS Poisoning,
        │   DDoS, SYN Flood, Port Scanning
        ├── Firewall: packet filtering, stateful inspection, application layer
        ├── IDS/IPS: signature-based vs anomaly-based
        ├── VPN: IPSec, OpenVPN, WireGuard
        └── Zero Trust Network Architecture

06.3.2  Load Balancing & CDN
        ├── Load balancing algorithms: Round Robin, Least Connections,
        │   IP Hash, Weighted, Resource-based
        ├── Layer 4 vs Layer 7 load balancing
        ├── Health checks dan failover
        ├── CDN: edge caching, anycast routing, cache invalidation
        └── Reverse proxy: Nginx, HAProxy sebagai case study

06.3.3  Arsitektur Sistem Terdistribusi (Pengantar)
        ├── CAP Theorem: Consistency, Availability, Partition Tolerance
        ├── BASE vs ACID
        ├── Eventual Consistency dan model konsistensi lainnya
        ├── Service Discovery: DNS-based, Consul, etcd
        └── Message Queue: konsep pub/sub, point-to-point
```

**📝 Evaluasi Bab 06:** [`bab-06/evaluasi-bab-06.md`](./bab-06/evaluasi-bab-06.md)

---

## BAB 07 — Basis Data & Sistem Penyimpanan

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 07  │  Basis Data & Sistem Penyimpanan                                 │
├──────────┼──────────────────────────────────────────────────────────────────┤
│  Layer   │  4 — Sistem & Infrastruktur                                      │
│  Level   │  ⭐⭐⭐ Lanjutan                                                  │
│  Durasi  │  ⏱️ 35–42 jam                                                    │
│  Prasyarat│ Bab 04 (Struktur Data — B-Tree), Bab 05 (Algoritma)            │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Data adalah aset paling berharga di era digital. Bab ini mengajarkan cara menyimpan, mengorganisasi, dan mengakses data secara efisien — mulai dari model relasional yang telah teruji selama 50 tahun hingga sistem NoSQL modern yang dirancang untuk skala web.

---

#### Modul 07.1 — Model Relasional, SQL & Normalisasi

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐ Menengah  |  ⏱️ 12–15 jam
```

**📂 Path:** [`bab-07/modul-01-model-relasional-sql-normalisasi/`](./bab-07/modul-01-model-relasional-sql-normalisasi/)

**Topik yang Dibahas:**

```
07.1.1  Model Data Relasional
        ├── Relasi, tuple, atribut, domain
        ├── Kunci: Primary Key, Foreign Key, Candidate Key, Super Key
        ├── Integritas: Entity Integrity, Referential Integrity
        ├── Aljabar Relasional: Select (σ), Project (π), Join (⋈),
        │   Union (∪), Difference (-), Cartesian Product (×)
        └── Relational Calculus: Tuple RC & Domain RC

07.1.2  SQL Komprehensif
        ├── DDL: CREATE, ALTER, DROP, TRUNCATE
        ├── DML: SELECT, INSERT, UPDATE, DELETE
        ├── Klausa lanjutan: JOIN (INNER, LEFT, RIGHT, FULL, CROSS, SELF),
        │   GROUP BY, HAVING, ORDER BY, LIMIT/OFFSET
        ├── Subquery: correlated vs non-correlated
        ├── Window Functions: ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD,
        │   PARTITION BY, OVER
        ├── CTE (Common Table Expressions) dan Recursive CTE
        └── Stored Procedure, Function, Trigger, View

07.1.3  Normalisasi Database
        ├── Functional Dependency dan Armstrong's Axioms
        ├── 1NF: eliminasi repeating groups
        ├── 2NF: eliminasi partial dependency
        ├── 3NF: eliminasi transitive dependency
        ├── BCNF (Boyce-Codd Normal Form)
        ├── 4NF: eliminasi multi-valued dependency
        └── Denormalisasi: kapan dan mengapa melanggar normalisasi
```

**🧪 Lab Praktik:**
```sql
-- Lab 07.1 — Database Design & Query Optimization
-- File: bab-07/modul-01-model-relasional-sql-normalisasi/lab/

-- Tugas 1: Rancang skema database untuk sistem e-commerce
-- (Users, Products, Orders, OrderItems, Categories, Reviews, Inventory)
-- Pastikan memenuhi 3NF

-- Tugas 2: Implementasikan query kompleks
-- Temukan top 10 produk berdasarkan revenue bulan lalu,
-- beserta persentase perubahan dari bulan sebelumnya,
-- hanya untuk kategori yang memiliki minimal 100 transaksi

WITH monthly_revenue AS (
    SELECT 
        p.product_id,
        p.name,
        c.category_name,
        DATE_TRUNC('month', o.created_at) AS month,
        SUM(oi.quantity * oi.unit_price) AS revenue,
        COUNT(DISTINCT o.order_id) AS transaction_count
    FROM order_items oi
    -- Lengkapi query ini...
),
-- Tugas 3: Analisis query plan menggunakan EXPLAIN ANALYZE
-- dan identifikasi bottleneck
```

---

#### Modul 07.2 — Internals Database: Indexing, Transaksi & Query Optimizer

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐⭐⭐ Expert  |  ⏱️ 13–16 jam
```

**📂 Path:** [`bab-07/modul-02-internals-indexing-transaksi/`](./bab-07/modul-02-internals-indexing-transaksi/)

**Topik yang Dibahas:**

```
07.2.1  Indexing & Storage Engine
        ├── B+ Tree Index: struktur, operasi, mengapa B+ bukan BST?
        ├── Hash Index: kapan lebih baik dari B+ Tree?
        ├── Clustered vs Non-clustered Index
        ├── Composite Index: column ordering dan selectivity
        ├── Covering Index: index-only scan
        ├── Index pada kolom dengan kardinalitas rendah
        ├── Partial Index dan Expression Index
        └── Storage engine: InnoDB vs MyISAM vs RocksDB

07.2.2  Transaksi & ACID
        ├── Atomicity: all-or-nothing, rollback mechanism
        ├── Consistency: constraint enforcement
        ├── Isolation: concurrency anomalies
        │   ├── Dirty Read, Non-repeatable Read, Phantom Read
        │   └── Isolation levels: READ UNCOMMITTED, READ COMMITTED,
        │       REPEATABLE READ, SERIALIZABLE
        ├── Durability: WAL (Write-Ahead Logging), fsync
        ├── Concurrency Control:
        │   ├── Pessimistic: 2PL (Two-Phase Locking), lock types
        │   └── Optimistic: MVCC (Multi-Version Concurrency Control)
        └── Deadlock detection dan resolution di database

07.2.3  Query Optimizer & Execution Engine
        ├── Query parsing: lexer, parser, AST
        ├── Logical plan: relational algebra tree
        ├── Physical plan: join algorithms (Nested Loop, Hash Join, Sort-Merge)
        ├── Cost-based optimization: statistics, cardinality estimation
        ├── EXPLAIN dan EXPLAIN ANALYZE: membaca query plan
        └── Query optimization techniques: predicate pushdown, join reordering
```

---

#### Modul 07.3 — NoSQL, NewSQL & Sistem Penyimpanan Modern

```
📖 Teori + 💻 Praktik
⭐⭐⭐ Lanjutan  |  ⏱️ 10–11 jam
```

**📂 Path:** [`bab-07/modul-03-nosql-newsql-penyimpanan-modern/`](./bab-07/modul-03-nosql-newsql-penyimpanan-modern/)

**Topik yang Dibahas:**

```
07.3.1  Kategori NoSQL
        ├── Key-Value Store: Redis, DynamoDB
        │   └── Use case: caching, session, leaderboard
        ├── Document Store: MongoDB, CouchDB
        │   └── Use case: content management, user profiles
        ├── Column-Family Store: Cassandra, HBase
        │   └── Use case: time-series, IoT, analytics
        ├── Graph Database: Neo4j, Amazon Neptune
        │   └── Use case: social network, recommendation, fraud detection
        └── Search Engine: Elasticsearch, Solr
            └── Use case: full-text search, log analytics

07.3.2  Distributed Database Concepts
        ├── Sharding: horizontal partitioning strategies
        │   (Range, Hash, Directory, Geo-based)
        ├── Replication: Master-Slave, Master-Master, Quorum
        ├── Consistent Hashing: virtual nodes, ring topology
        ├── Vector Clocks dan Conflict Resolution
        └── Distributed Transactions: 2PC, Saga Pattern

07.3.3  Sistem Penyimpanan Modern
        ├── LSM Tree (Log-Structured Merge Tree): RocksDB, Cassandra
        ├── Column-oriented storage: Parquet, ORC (untuk analytics)
        ├── Time-series databases: InfluxDB, TimescaleDB
        ├── Data Warehouse vs Data Lake vs Lakehouse
        └── HTAP (Hybrid Transactional/Analytical Processing)
```

**📝 Evaluasi Bab 07:** [`bab-07/evaluasi-bab-07.md`](./bab-07/evaluasi-bab-07.md)

---

## BAB 08 — Rekayasa Perangkat Lunak & Paradigma Pemrograman

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 08  │  Rekayasa Perangkat Lunak & Paradigma Pemrograman                │
├──────────┼──────────────────────────────────────────────────────────────────┤
│  Layer   │  5 — Rekayasa & Keamanan                                         │
│  Level   │  ⭐⭐⭐ Lanjutan                                                  │
│  Durasi  │  ⏱️ 35–42 jam                                                    │
│  Prasyarat│ Bab 04, 05, 06, 07 (semua bab layer 3 & 4)                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Menulis kode yang bekerja adalah langkah pertama. Menulis kode yang dapat dipelihara, diuji, dan dikembangkan oleh tim selama bertahun-tahun adalah seni yang membutuhkan pemahaman mendalam tentang prinsip rekayasa perangkat lunak.

---

#### Modul 08.1 — Paradigma Pemrograman & Prinsip Desain

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐⭐ Lanjutan  |  ⏱️ 12–15 jam
```

**📂 Path:** [`bab-08/modul-01-paradigma-pemrograman-prinsip-desain/`](./bab-08/modul-01-paradigma-pemrograman-prinsip-desain/)

**Topik yang Dibahas:**

```
08.1.1  Paradigma Pemrograman
        ├── Imperatif: Prosedural (C), Object-Oriented (Java, Python)
        ├── Deklaratif: Fungsional (Haskell, Erlang), Logic (Prolog)
        ├── Pemrograman Fungsional:
        │   ├── Pure functions dan immutability
        │   ├── Higher-order functions: map, filter, reduce
        │   ├── Closures dan currying
        │   ├── Lazy evaluation
        │   └── Monad: Maybe, Either, IO (konsep)
        ├── Pemrograman Reaktif: Observable, stream, backpressure
        └── Multi-paradigma: Python, Scala, Rust sebagai contoh

08.1.2  Prinsip Desain Perangkat Lunak
        ├── SOLID Principles:
        │   ├── S — Single Responsibility Principle
        │   ├── O — Open/Closed Principle
        │   ├── L — Liskov Substitution Principle
        │   ├── I — Interface Segregation Principle
        │   └── D — Dependency Inversion Principle
        ├── DRY (Don't Repeat Yourself)
        ├── KISS (Keep It Simple, Stupid)
        ├── YAGNI (You Aren't Gonna Need It)
        └── Law of Demeter (Principle of Least Knowledge)

08.1.3  Design Patterns (GoF)
        ├── Creational: Singleton, Factory Method, Abstract Factory,
        │   Builder, Prototype
        ├── Structural: Adapter, Bridge, Composite, Decorator,
        │   Facade, Flyweight, Proxy
        └── Behavioral: Chain of Responsibility, Command, Iterator,
            Mediator, Memento, Observer, State, Strategy, Template Method,
            Visitor
```

---

#### Modul 08.2 — Arsitektur Perangkat Lunak & Pengujian

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐⭐ Lanjutan  |  ⏱️ 13–16 jam
```

**📂 Path:** [`bab-08/modul-02-arsitektur-perangkat-lunak-pengujian/`](./bab-08/modul-02-arsitektur-perangkat-lunak-pengujian/)

**Topik yang Dibahas:**

```
08.2.1  Arsitektur Perangkat Lunak
        ├── Monolith: kelebihan dan keterbatasan
        ├── Layered Architecture: Presentation, Business, Data Access
        ├── Hexagonal Architecture (Ports & Adapters)
        ├── Clean Architecture: Dependency Rule
        ├── Event-Driven Architecture: Event Sourcing, CQRS
        ├── Microservices: dekomposisi, komunikasi, trade-off
        ├── Service Mesh: Istio, Linkerd
        └── Serverless: FaaS, BaaS, cold start problem

08.2.2  Pengujian Perangkat Lunak
        ├── Testing pyramid: Unit → Integration → E2E
        ├── Unit Testing: isolation, mocking, stubbing, faking
        ├── Test-Driven Development (TDD): Red → Green → Refactor
        ├── Behavior-Driven Development (BDD): Given-When-Then
        ├── Property-Based Testing: QuickCheck, Hypothesis
        ├── Mutation Testing: mengukur kualitas test suite
        ├── Performance Testing: load, stress, soak, spike testing
        └── Chaos Engineering: Netflix Chaos Monkey, Gremlin

08.2.3  DevOps & Continuous Delivery
        ├── Version Control: Git internals (object model, DAG)
        ├── CI/CD Pipeline: build, test, deploy automation
        ├── Infrastructure as Code: Terraform, Ansible
        ├── Containerization: Docker, container registry
        ├── Orchestration: Kubernetes core concepts
        ├── Observability: Metrics, Logging, Tracing (OpenTelemetry)
        └── SRE: SLI, SLO, SLA, Error Budget
```

---

#### Modul 08.3 — Teori Bahasa Pemrograman & Kompilator

```
📖 Teori + 💻 Praktik
⭐⭐⭐⭐ Expert  |  ⏱️ 10–11 jam
```

**📂 Path:** [`bab-08/modul-03-teori-bahasa-kompilator/`](./bab-08/modul-03-teori-bahasa-kompilator/)

**Topik yang Dibahas:**

```
08.3.1  Teori Bahasa Formal & Automata
        ├── Alfabet, string, bahasa formal
        ├── Regular Language & Finite Automata (DFA, NFA)
        ├── Regular Expression: sintaks dan semantik formal
        ├── Context-Free Language & Pushdown Automata
        ├── Context-Free Grammar (CFG) & Parse Tree
        ├── Turing Machine: model komputasi universal
        └── Chomsky Hierarchy: Type 0, 1, 2, 3

08.3.2  Prinsip Kompilator
        ├── Fase kompilasi: Lexing → Parsing → Semantic Analysis →
        │   IR Generation → Optimization → Code Generation
        ├── Lexer: tokenisasi, regular expression, DFA
        ├── Parser: top-down (LL), bottom-up (LR), recursive descent
        ├── Abstract Syntax Tree (AST)
        ├── Symbol Table dan Scope
        ├── Type System: static vs dynamic, strong vs weak
        └── Optimasi: constant folding, dead code elimination,
            loop unrolling, inlining

08.3.3  Runtime & Memory Management
        ├── Stack vs Heap allocation
        ├── Garbage Collection: Mark-and-Sweep, Reference Counting,
        │   Generational GC, Tri-color marking
        ├── Memory safety: dangling pointer, use-after-free, buffer overflow
        ├── Ownership model: Rust's borrow checker
        └── JIT Compilation: V8, HotSpot JVM
```

**📝 Evaluasi Bab 08:** [`bab-08/evaluasi-bab-08.md`](./bab-08/evaluasi-bab-08.md)

---

## BAB 09 — Keamanan Komputer & Kriptografi

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 09  │  Keamanan Komputer & Kriptografi                                 │
├──────────┼──────────────────────────────────────────────────────────────────┤
│  Layer   │  5 — Rekayasa & Keamanan                                         │
│  Level   │  ⭐⭐⭐⭐ Expert                                                  │
│  Durasi  │  ⏱️ 35–42 jam                                                    │
│  Prasyarat│ Bab 01 (Teori Bilangan), Bab 06 (Jaringan), Bab 08 (RPL)      │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Keamanan bukan fitur yang ditambahkan belakangan — ia harus menjadi bagian integral dari setiap keputusan desain. Bab ini membangun pemahaman dari fondasi matematis kriptografi hingga teknik serangan dan pertahanan sistem nyata.

> ⚠️ **Etika:** Semua teknik yang dipelajari di bab ini hanya boleh diterapkan pada sistem yang Anda miliki atau memiliki izin eksplisit untuk diuji. Penggunaan ilegal adalah pelanggaran hukum.

---

#### Modul 09.1 — Kriptografi: Fondasi Matematis & Algoritma

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐⭐⭐ Expert  |  ⏱️ 14–17 jam
```

**📂 Path:** [`bab-09/modul-01-kriptografi-fondasi-algoritma/`](./bab-09/modul-01-kriptografi-fondasi-algoritma/)

**Topik yang Dibahas:**

```
09.1.1  Kriptografi Simetris
        ├── Prinsip: confusion dan diffusion (Shannon)
        ├── Stream Cipher: RC4, ChaCha20
        ├── Block Cipher: DES (historis), AES (Rijndael)
        │   ├── AES internals: SubBytes, ShiftRows, MixColumns, AddRoundKey
        │   └── Mode operasi: ECB (tidak aman), CBC, CTR, GCM
        └── Key management: key derivation, key exchange

09.1.2  Kriptografi Asimetris (Public-Key)
        ├── Fondasi matematis: one-way function, trapdoor function
        ├── RSA: key generation, enkripsi, dekripsi, tanda tangan
        │   └── Keamanan RSA: integer factorization problem
        ├── Diffie-Hellman Key Exchange: discrete logarithm problem
        ├── Elliptic Curve Cryptography (ECC): ECDH, ECDSA
        │   └── Mengapa ECC lebih efisien dari RSA?
        └── Post-Quantum Cryptography: ancaman quantum computing,
            NIST PQC standards (CRYSTALS-Kyber, CRYSTALS-Dilithium)

09.1.3  Hash Function & MAC
        ├── Properti: pre-image resistance, second pre-image resistance,
        │   collision resistance
        ├── MD5 (broken), SHA-1 (deprecated), SHA-256, SHA-3 (Keccak)
        ├── HMAC: keyed hash untuk message authentication
        ├── Password hashing: bcrypt, scrypt, Argon2 (mengapa bukan SHA?)
        └── Digital Signature: RSA-PSS, ECDSA, EdDSA (Ed25519)

09.1.4  Protokol Kriptografi
        ├── TLS 1.3: handshake, cipher suite, perfect forward secrecy
        ├── PKI: Certificate Authority, X.509, certificate chain
        ├── Certificate Transparency
        └── Zero-Knowledge Proof: konsep dan aplikasi
```

**🧪 Lab Praktik:**
```python
# Lab 09.1 — Cryptography Implementation (Educational)
# File: bab-09/modul-01-kriptografi-fondasi-algoritma/lab/
# PERINGATAN: Jangan gunakan implementasi ini di production!
# Selalu gunakan library kriptografi yang telah diaudit (cryptography, libsodium)

class AESEducational:
    """
    Implementasi AES-128 untuk tujuan pembelajaran.
    Memahami setiap langkah: SubBytes, ShiftRows, MixColumns, AddRoundKey
    """
    S_BOX = [...]  # AES S-Box lookup table
    
    def sub_bytes(self, state: list[list]) -> list[list]: ...
    def shift_rows(self, state: list[list]) -> list[list]: ...
    def mix_columns(self, state: list[list]) -> list[list]: ...
    def add_round_key(self, state: list[list], round_key: list) -> list[list]: ...
    def key_expansion(self, key: bytes) -> list: ...
    def encrypt_block(self, plaintext: bytes, key: bytes) -> bytes: ...

class RSAEducational:
    """Implementasi RSA untuk pembelajaran — BUKAN untuk production."""
    def generate_keys(self, bits: int = 1024) -> tuple[tuple, tuple]:
        """Return ((n, e), (n, d)) sebagai (public_key, private_key)."""
        pass
    
    def encrypt(self, message: int, public_key: tuple) -> int: ...
    def decrypt(self, ciphertext: int, private_key: tuple) -> int: ...
    def sign(self, message: int, private_key: tuple) -> int: ...
    def verify(self, message: int, signature: int, public_key: tuple) -> bool: ...
```

---

#### Modul 09.2 — Keamanan Sistem & Teknik Serangan-Pertahanan

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐⭐⭐ Expert  |  ⏱️ 12–15 jam
```

**📂 Path:** [`bab-09/modul-02-keamanan-sistem-serangan-pertahanan/`](./bab-09/modul-02-keamanan-sistem-serangan-pertahanan/)

**Topik yang Dibahas:**

```
09.2.1  Kerentanan Perangkat Lunak
        ├── Buffer Overflow: stack overflow, heap overflow, return-oriented
        │   programming (ROP)
        ├── Format String Vulnerability
        ├── Integer Overflow & Underflow
        ├── Use-After-Free & Double Free
        ├── Race Condition (TOCTOU)
        └── Mitigasi: ASLR, Stack Canary, NX bit, PIE, CFI

09.2.2  Kerentanan Aplikasi Web (OWASP Top 10)
        ├── Injection: SQL Injection, Command Injection, LDAP Injection
        ├── Broken Authentication & Session Management
        ├── Cross-Site Scripting (XSS): Reflected, Stored, DOM-based
        ├── Insecure Direct Object Reference (IDOR)
        ├── Security Misconfiguration
        ├── Cross-Site Request Forgery (CSRF)
        ├── Using Components with Known Vulnerabilities
        └── Server-Side Request Forgery (SSRF)

09.2.3  Secure Development Lifecycle
        ├── Threat Modeling: STRIDE, PASTA, Attack Tree
        ├── Secure Coding Practices: input validation, output encoding,
        │   parameterized queries, least privilege
        ├── Security Testing: SAST, DAST, IAST, Penetration Testing
        ├── Dependency scanning: SCA (Software Composition Analysis)
        └── Incident Response: detection, containment, eradication, recovery
```

---

#### Modul 09.3 — Keamanan Infrastruktur & Compliance

```
📖 Teori + 💻 Praktik
⭐⭐⭐ Lanjutan  |  ⏱️ 9–10 jam
```

**📂 Path:** [`bab-09/modul-03-keamanan-infrastruktur-compliance/`](./bab-09/modul-03-keamanan-infrastruktur-compliance/)

**Topik yang Dibahas:**

```
09.3.1  Keamanan Infrastruktur
        ├── Hardening OS: minimal install, patch management, CIS Benchmarks
        ├── Network segmentation: DMZ, VLAN, micro-segmentation
        ├── Identity & Access Management (IAM): RBAC, ABAC, OAuth 2.0,
        │   OpenID Connect, SAML
        ├── Secrets Management: HashiCorp Vault, AWS Secrets Manager
        └── Container Security: image scanning, runtime security, Pod Security

09.3.2  Kriptografi dalam Praktik
        ├── Key Management: HSM, KMS, key rotation
        ├── Enkripsi data at-rest dan in-transit
        ├── Certificate lifecycle management
        └── Secure random number generation

09.3.3  Compliance & Regulasi
        ├── Framework keamanan: ISO 27001, NIST CSF, SOC 2
        ├── Regulasi data: GDPR, CCPA, UU PDP Indonesia
        ├── PCI DSS untuk sistem pembayaran
        └── Privacy by Design dan Security by Design
```

**📝 Evaluasi Bab 09:** [`bab-09/evaluasi-bab-09.md`](./bab-09/evaluasi-bab-09.md)

---

## BAB 10 — Komputasi Lanjutan & Tren Masa Depan

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 10  │  Komputasi Lanjutan & Tren Masa Depan                            │
├──────────┼──────────────────────────────────────────────────────────────────┤
│  Layer   │  6 — Frontier & Integrasi                                        │
│  Level   │  ⭐⭐⭐⭐ Expert                                                  │
│  Durasi  │  ⏱️ 30–38 jam                                                    │
│  Prasyarat│ Semua bab sebelumnya (Bab 01–09)                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Bab penutup ini mengintegrasikan semua pengetahuan yang telah dibangun dan memproyeksikannya ke arah frontier komputasi modern. Tujuannya bukan menguasai setiap topik secara mendalam, melainkan membangun **peta mental** yang memungkinkan Anda belajar mandiri di bidang-bidang ini.

---

#### Modul 10.1 — Komputasi Paralel, Terdistribusi & Cloud

```
📖 Teori + 💻 Praktik + 🧪 Lab
⭐⭐⭐⭐ Expert  |  ⏱️ 12–15 jam
```

**📂 Path:** [`bab-10/modul-01-komputasi-paralel-terdistribusi-cloud/`](./bab-10/modul-01-komputasi-paralel-terdistribusi-cloud/)

**Topik yang Dibahas:**

```
10.1.1  Komputasi Paralel
        ├── Flynn's Taxonomy: SISD, SIMD, MISD, MIMD
        ├── Shared Memory: OpenMP, POSIX Threads
        ├── Distributed Memory: MPI (Message Passing Interface)
        ├── GPU Computing: CUDA, OpenCL, SIMT model
        ├── Amdahl's Law: batas speedup dari paralelisasi
        ├── Gustafson's Law: weak scaling
        └── Parallel algorithms: parallel prefix sum, parallel sort,
            parallel BFS

10.1.2  Sistem Terdistribusi Lanjutan
        ├── Consensus Algorithms: Paxos, Raft
        ├── Distributed Ledger: Blockchain (konsep CS, bukan investasi)
        ├── Distributed File System: GFS, HDFS, Ceph
        ├── MapReduce & Spark: model pemrograman untuk big data
        ├── Stream Processing: Kafka Streams, Apache Flink
        └── Koordinasi terdistribusi: ZooKeeper, etcd

10.1.3  Cloud Computing & Serverless
        ├── Model layanan: IaaS, PaaS, SaaS, FaaS
        ├── Virtualisasi vs Kontainerisasi di cloud
        ├── Auto-scaling: horizontal vs vertical, predictive vs reactive
        ├── Multi-region deployment: latency, data residency, failover
        └── FinOps: optimasi biaya cloud
```

---

#### Modul 10.2 — Kecerdasan Buatan, Machine Learning & Komputasi Kuantum

```
📖 Teori + 💻 Praktik
⭐⭐⭐⭐ Expert  |  ⏱️ 12–15 jam
```

**📂 Path:** [`bab-10/modul-02-ai-ml-komputasi-kuantum/`](./bab-10/modul-02-ai-ml-komputasi-kuantum/)

**Topik yang Dibahas:**

```
10.2.1  Fondasi Machine Learning dari Perspektif CS
        ├── ML sebagai optimasi: loss function, gradient descent
        ├── Kompleksitas komputasi ML: training vs inference
        ├── Struktur data untuk ML: tensor, sparse matrix
        ├── Algoritma klasik ML: kNN, Decision Tree, SVM, k-Means
        │   (dari perspektif algoritma dan struktur data)
        ├── Neural Network: forward pass, backpropagation
        │   (matematika di balik gradient descent)
        └── Transformer Architecture: attention mechanism, self-attention

10.2.2  Sistem AI di Production
        ├── ML Pipeline: data ingestion, feature engineering, training,
        │   evaluation, serving
        ├── Model serving: latency vs throughput trade-off
        ├── Distributed training: data parallelism, model parallelism
        ├── MLOps: versioning, monitoring, drift detection
        └── LLM Infrastructure: tokenization, KV cache, quantization

10.2.3  Komputasi Kuantum
        ├── Qubit vs bit klasik: superposisi dan entanglement
        ├── Quantum gates: Hadamard, CNOT, Toffoli
        ├── Quantum circuit model
        ├── Algoritma kuantum:
        │   ├── Grover's Algorithm: pencarian O(√N)
        │   └── Shor's Algorithm: faktorisasi O((log N)³) — ancaman RSA
        ├── Quantum error correction
        └── NISQ era: Noisy Intermediate-Scale Quantum computers
```

---

#### Modul 10.3 — Frontier CS: Integrasi & Refleksi

```
📖 Teori + 💻 Praktik + Diskusi
⭐⭐⭐ Lanjutan  |  ⏱️ 6–8 jam
```

**📂 Path:** [`bab-10/modul-03-frontier-integrasi-refleksi/`](./bab-10/modul-03-frontier-integrasi-refleksi/)

**Topik yang Dibahas:**

```
10.3.1  Topik Frontier CS
        ├── Formal Verification: model checking, theorem proving (Coq, Lean)
        ├── Programming Language Theory: type theory, dependent types
        ├── Computational Biology: sequence alignment, protein folding
        ├── Quantum Machine Learning: intersection QC dan ML
        └── Neuromorphic Computing: Intel Loihi, IBM TrueNorth

10.3.2  Etika & Dampak Sosial Teknologi
        ├── Algorithmic bias dan fairness
        ├── Privacy: differential privacy, federated learning
        ├── AI safety dan alignment
        ├── Digital divide dan aksesibilitas
        └── Tanggung jawab profesional software engineer

10.3.3  Refleksi & Peta Belajar Lanjutan
        ├── Review koneksi antar semua bab
        ├── Identifikasi area yang ingin diperdalam
        ├── Roadmap spesialisasi: Systems, AI/ML, Security, Distributed Systems
        └── Komunitas dan sumber daya untuk belajar berkelanjutan
```

**📝 Evaluasi Bab 10:** [`bab-10/evaluasi-bab-10.md`](./bab-10/evaluasi-bab-10.md)

---

## 🏆 Capstone Project Enterprise

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    CAPSTONE PROJECT ENTERPRISE                              ║
║                                                                              ║
║   "Distributed Key-Value Store with Consensus & Security Layer"             ║
║                                                                              ║
║   Tingkat Kesulitan: ⭐⭐⭐⭐ Expert                                          ║
║   Estimasi Waktu:    ⏱️ 80–100 jam                                          ║
║   Tim:               1–3 orang                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### Deskripsi Proyek

Anda akan membangun **sistem penyimpanan key-value terdistribusi** yang mengintegrasikan hampir semua konsep yang dipelajari sepanjang kurikulum. Sistem ini terinspirasi dari arsitektur nyata seperti etcd, Consul, dan Redis Cluster — namun dibangun dari fondasi untuk membuktikan pemahaman mendalam.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ARSITEKTUR SISTEM CAPSTONE                               │
│                                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                              │
│  │  Client  │    │  Client  │    │  Client  │                              │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘                              │
│       │               │               │                                     │
│       └───────────────┼───────────────┘                                     │
│                       │ TLS 1.3                                             │
│              ┌────────▼────────┐                                            │
│              │   Load Balancer  │  (Layer 06)                               │
│              │  (Round Robin + │                                            │
│              │   Health Check) │                                            │
│              └────────┬────────┘                                            │
│                       │                                                     │
│         ┌─────────────┼─────────────┐                                      │
│         │             │             │                                       │
│  ┌──────▼──────┐ ┌────▼──────┐ ┌───▼───────┐                              │
│  │   Node 1    │ │  Node 2   │ │  Node 3   │  (Raft Consensus)            │
│  │  [LEADER]   │ │[FOLLOWER] │ │[FOLLOWER] │  (Layer 10)                  │
│  └──────┬──────┘ └────┬──────┘ └───┬───────┘                              │
│         │             │             │                                       │
│         └─────────────┼─────────────┘                                      │
│                       │ Replication Log                                     │
│              ┌────────▼────────┐                                            │
│              │  Storage Engine  │  (LSM Tree)  (Layer 07)                  │
│              │  ┌────────────┐ │                                            │
│              │  │  MemTable  │ │                                            │
│              │  ├────────────┤ │                                            │
│              │  │  WAL Log   │ │                                            │
│              │  ├────────────┤ │                                            │
│              │  │  SSTable   │ │                                            │
│              │  └────────────┘ │                                            │
│              └─────────────────┘                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Spesifikasi Fungsional

#### Fitur Wajib (Minimum Viable Product)

```
F-01  Key-Value Operations
      ├── GET key → value | null
      ├── PUT key value [TTL]
      ├── DELETE key
      ├── EXISTS key → bool
      ├── KEYS pattern (glob matching)
      └── SCAN cursor count → [cursor, keys]

F-02  Data Types
      ├── String (dengan encoding otomatis: int, float, raw)
      ├── List (doubly linked list)
      ├── Hash Map
      ├── Sorted Set (skip list + hash map)
      └── Bloom Filter (probabilistic membership)

F-03  Persistence
      ├── Write-Ahead Log (WAL) untuk durability
      ├── MemTable (in-memory, sorted)
      ├── SSTable (immutable, sorted, disk)
      ├── Compaction: size-tiered & leveled strategy
      └── Snapshot & Point-in-time recovery

F-04  Distributed Consensus (Raft)
      ├── Leader election dengan randomized timeout
      ├── Log replication ke majority quorum
      ├── Log compaction (snapshot)
      ├── Membership change (joint consensus)
      └── Read linearizability: ReadIndex & LeaseRead

F-05  Client Protocol
      ├── Custom binary protocol (lebih efisien dari text)
      ├── Pipelining: multiple commands per round-trip
      ├── Pub/Sub messaging
      └── Transactions: MULTI/EXEC dengan optimistic locking
```

#### Fitur Keamanan (Wajib — Bab 09)

```
S-01  Transport Security
      ├── TLS 1.3 mutual authentication (mTLS)
      ├── Certificate rotation tanpa downtime
      └── Perfect Forward Secrecy

S-02  Authentication & Authorization
      ├── Token-based authentication (JWT dengan Ed25519)
      ├── RBAC: role-based access control per key prefix
      ├── Rate limiting: token bucket per client
      └── Audit log: semua operasi write dicatat

S-03  Encryption at Rest
      ├── AES-256-GCM untuk SSTable encryption
      ├── Key derivation: HKDF dari master key
      └── Key rotation: re-encryption tanpa downtime
```

#### Fitur Observabilitas (Wajib — Bab 08)

```
O-01  Metrics (Prometheus format)
      ├── Latency histogram: p50, p95, p99, p999
      ├── Throughput: ops/sec per operation type
      ├── Cache hit rate: MemTable vs SSTable
      ├── Raft metrics: leader changes, log lag
      └── Resource: CPU, memory, disk I/O

O-02  Distributed Tracing (OpenTelemetry)
      ├── Trace setiap request end-to-end
      ├── Span untuk setiap fase: network, consensus, storage
      └── Baggage propagation antar node

O-03  Structured Logging
      ├── JSON format dengan correlation ID
      ├── Log level: DEBUG, INFO, WARN, ERROR, FATAL
      └── Log rotation dan retention policy
```

### Spesifikasi Non-Fungsional

| Metrik | Target | Cara Pengukuran |
|---|---|---|
| **Throughput** | ≥ 50,000 ops/detik (single node) | Benchmark dengan 16 thread concurrent |
| **Latency P99** | ≤ 5ms untuk GET, ≤ 10ms untuk PUT | Histogram dengan HdrHistogram |
| **Availability** | ≥ 99.9% (toleransi 1 node failure dari 3) | Chaos testing: kill 1 node |
| **Consistency** | Linearizable reads | Jepsen-style correctness test |
| **Durability** | Tidak ada data loss setelah crash | Kill -9 saat write, verifikasi recovery |
| **Scalability** | Linear throughput scaling hingga 3 node | Benchmark 1, 2, 3 node |

### Struktur Direktori Proyek

```
capstone-kvstore/
├── README.md                    # Dokumentasi proyek
├── DESIGN.md                    # Dokumen desain arsitektur
├── BENCHMARKS.md                # Hasil benchmark dan analisis
│
├── src/
│   ├── server/
│   │   ├── main.go              # Entry point
│   │   ├── config/              # Konfigurasi server
│   │   └── api/                 # gRPC & HTTP API handler
│   │
│   ├── consensus/               # Implementasi Raft
│   │   ├── raft.go              # Core Raft state machine
│   │   ├── log.go               # Raft log management
│   │   ├── snapshot.go          # Log compaction
│   │   └── transport.go         # Network transport
│   │
│   ├── storage/                 # Storage Engine (LSM Tree)
│   │   ├── memtable.go          # In-memory sorted table
│   │   ├── wal.go               # Write-Ahead Log
│   │   ├── sstable.go           # Sorted String Table
│   │   ├── compaction.go        # Compaction strategies
│   │   └── bloom_filter.go      # Bloom filter untuk SSTable
│   │
│   ├── datatype/                # Data type implementations
│   │   ├── string.go
│   │   ├── list.go              # Doubly linked list
│   │   ├── hashmap.go
│   │   └── sorted_set.go        # Skip list + hash map
│   │
│   ├── security/                # Security layer
│   │   ├── tls.go               # mTLS configuration
│   │   ├── auth.go              # JWT authentication
│   │   ├── rbac.go              # Role-based access control
│   │   ├── ratelimit.go         # Token bucket rate limiter
│   │   └── encryption.go        # At-rest encryption
│   │
│   ├── cluster/                 # Cluster management
│   │   ├── discovery.go         # Node discovery
│   │   ├── loadbalancer.go      # Client-side load balancing
│   │   └── healthcheck.go       # Health monitoring
│   │
│   └── observability/           # Metrics, tracing, logging
│       ├── metrics.go           # Prometheus metrics
│       ├── tracing.go           # OpenTelemetry tracing
│       └── logging.go           # Structured logging
│
├── client/
│   ├── cli/                     # Command-line client
│   └── sdk/                     # Client SDK (Go + Python)
│
├── tests/
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   ├── chaos/                   # Chaos engineering tests
│   │   ├── network_partition.sh # Simulasi network partition
│   │   ├── node_failure.sh      # Kill node secara acak
│   │   └── disk_full.sh         # Simulasi disk penuh
│   └── benchmark/               # Performance benchmarks
│       ├── throughput_test.go
│       └── latency_test.go
│
├── deploy/
│   ├── docker-compose.yml       # 3-node cluster lokal
│   ├── kubernetes/              # K8s manifests
│   │   ├── statefulset.yaml
│   │   ├── service.yaml
│   │   └── configmap.yaml
│   └── terraform/               # Cloud deployment (AWS/GCP)
│
├── docs/
│   ├── api/                     # API documentation
│   ├── architecture/            # Architecture diagrams
│   └── runbook/                 # Operational runbook
│
└── scripts/
    ├── setup.sh                 # Development environment setup
    ├── benchmark.sh             # Run all benchmarks
    └── chaos_test.sh            # Run chaos tests
```

### Rubrik Penilaian

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RUBRIK PENILAIAN CAPSTONE                           │
├──────────────────────────────────┬──────────┬───────────────────────────────┤
│  Komponen                        │  Bobot   │  Kriteria Penilaian           │
├──────────────────────────────────┼──────────┼───────────────────────────────┤
│  Correctness & Functionality     │  25%     │  Semua fitur wajib berjalan,  │
│                                  │          │  lulus test suite             │
├──────────────────────────────────┼──────────┼───────────────────────────────┤
│  Distributed Consensus           │  20%     │  Raft benar: leader election, │
│  (Raft Implementation)           │          │  log replication, linearizable│
├──────────────────────────────────┼──────────┼───────────────────────────────┤
│  Storage Engine                  │  15%     │  LSM Tree benar, WAL durability│
│  (LSM Tree)                      │          │  compaction berjalan          │
├──────────────────────────────────┼──────────┼───────────────────────────────┤
│  Security Implementation         │  15%     │  mTLS, RBAC, encryption at   │
│                                  │          │  rest, rate limiting          │
├──────────────────────────────────┼──────────┼───────────────────────────────┤
│  Performance                     │  10%     │  Memenuhi target throughput   │
│                                  │          │  dan latency                  │
├──────────────────────────────────┼──────────┼───────────────────────────────┤
│  Code Quality & Testing          │  10%     │  Test coverage ≥ 80%,        │
│                                  │          │  kode bersih dan terdokumentasi│
├──────────────────────────────────┼──────────┼───────────────────────────────┤
│  Observability                   │  5%      │  Metrics, tracing, logging    │
│                                  │          │  berfungsi                    │
└──────────────────────────────────┼──────────┼───────────────────────────────┤
│  TOTAL                           │  100%    │  Minimum lulus: 70/100        │
└──────────────────────────────────┴──────────┴───────────────────────────────┘

BONUS (hingga +15 poin):
  +5  — Implementasi Jepsen-style linearizability checker
  +5  — Deployment ke cloud dengan Kubernetes + Terraform
  +5  — Dashboard monitoring dengan Grafana
```

### Milestone & Timeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MILESTONE CAPSTONE PROJECT                          │
├──────────┬──────────────────────────────────────────────────────────────────┤
│  Minggu  │  Deliverable                                                     │
├──────────┼──────────────────────────────────────────────────────────────────┤
│  M-01    │  📄 Design Document: arsitektur, API spec, data model            │
│          │  Review: peer review dari 2 peserta lain                        │
├──────────┼──────────────────────────────────────────────────────────────────┤
│  M-02    │  💾 Storage Engine: MemTable + WAL + SSTable dasar               │
│          │  Test: unit test untuk semua komponen storage                   │
├──────────┼──────────────────────────────────────────────────────────────────┤
│  M-03    │  🔄 Raft Consensus: leader election + log replication            │
│          │  Test: 3-node cluster, kill 1 node, verifikasi availability     │
├──────────┼──────────────────────────────────────────────────────────────────┤
│  M-04    │  🔒 Security Layer: mTLS + RBAC + encryption at rest             │
│          │  Test: penetration testing dasar                                │
├──────────┼──────────────────────────────────────────────────────────────────┤
│  M-05    │  📊 Observability + Performance Tuning + Final Documentation     │
│          │  Demo: live demo 30 menit kepada reviewer                       │
└──────────┴──────────────────────────────────────────────────────────────────┘
```

### Koneksi ke Materi Kurikulum

```
Komponen Capstone          ←→  Bab Kurikulum
─────────────────────────────────────────────────────────────
LSM Tree Storage Engine    ←→  Bab 04 (Struktur Data: Skip List, B-Tree)
                               Bab 07 (Database Internals: LSM Tree)

Raft Consensus Algorithm   ←→  Bab 05 (Algoritma: Distributed Consensus)
                               Bab 10 (Komputasi Terdistribusi: Raft)

Network Protocol (gRPC)    ←→  Bab 06 (Jaringan: TCP, HTTP/2, Protocol Buffer)

TLS & Encryption           ←→  Bab 09 (Kriptografi: TLS 1.3, AES-GCM)

RBAC & Authentication      ←→  Bab 09 (Keamanan: IAM, JWT)

Bloom Filter               ←→  Bab 04 (Struktur Data Lanjutan: Bloom Filter)

Load Balancer              ←→  Bab 06 (Load Balancing)

Prometheus Metrics         ←→  Bab 08 (DevOps: Observability)

Docker & Kubernetes        ←→  Bab 03 (Virtualisasi & Kontainerisasi)
                               Bab 08 (DevOps: Container Orchestration)

Chaos Testing              ←→  Bab 08 (Chaos Engineering)
                               Bab 10 (Sistem Terdistribusi: Fault Tolerance)
```

---

## 📖 Sumber Daya & Referensi

### Buku Teks Utama

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BUKU WAJIB                                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  [1] Cormen, T.H. et al. — "Introduction to Algorithms" (CLRS), 4th Ed.   │
│      MIT Press. → Bab 04, 05                                               │
│                                                                             │
│  [2] Silberschatz, A. et al. — "Operating System Concepts", 10th Ed.      │
│      Wiley. → Bab 03                                                       │
│                                                                             │
│  [3] Tanenbaum, A. — "Computer Networks", 6th Ed.                         │
│      Pearson. → Bab 06                                                     │
│                                                                             │
│  [4] Ramakrishnan, R. — "Database Management Systems", 3rd Ed.            │
│      McGraw-Hill. → Bab 07                                                 │
│                                                                             │
│  [5] Patterson, D. & Hennessy, J. — "Computer Organization and Design",   │
│      6th Ed. Morgan Kaufmann. → Bab 02                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  BUKU PENDUKUNG                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  [6] Kleppmann, M. — "Designing Data-Intensive Applications"               │
│      O'Reilly. → Bab 07, 10                                                │
│                                                                             │
│  [7] Boneh, D. & Shoup, V. — "A Graduate Course in Applied Cryptography"  │
│      (Free online). → Bab 09                                               │
│                                                                             │
│  [8] Gamma, E. et al. — "Design Patterns: Elements of Reusable OO SW"     │
│      Addison-Wesley. → Bab 08                                              │
│                                                                             │
│  [9] Rosen, K. — "Discrete Mathematics and Its Applications", 8th Ed.     │
│      McGraw-Hill. → Bab 01                                                 │
│                                                                             │
│  [10] Martin, R.C. — "Clean Architecture"                                  │
│       Prentice Hall. → Bab 08                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Kursus Online Gratis

| Topik | Platform | Link |
|---|---|---|
| Algorithms & Data Structures | MIT OpenCourseWare | [6.006](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/) |
| Operating Systems | UC Berkeley | [CS 162](https://cs162.org/) |
| Computer Networks | Stanford | [CS 144](https://cs144.github.io/) |
| Databases | CMU | [15-445](https://15-445.courses.cs.cmu.edu/) |
| Computer Architecture | CMU | [15-213](https://www.cs.cmu.edu/~213/) |
| Cryptography | Coursera (Stanford) | [Crypto I](https://www.coursera.org/learn/crypto) |
| Distributed Systems | MIT | [6.824](https://pdos.csail.mit.edu/6.824/) |

### Tools & Platform Praktik

```
Algoritma & Struktur Data:
  ├── LeetCode (https://leetcode.com) — latihan soal
  ├── Visualgo (https://visualgo.net) — visualisasi algoritma
  └── Algorithm Visualizer (https://algorithm-visualizer.org)

Jaringan:
  ├── Wireshark — packet analyzer
  ├── Netcat (nc) — network debugging
  └── curl & httpie — HTTP testing

Database:
  ├── PostgreSQL — RDBMS utama untuk praktik
  ├── Redis — Key-value store referensi
  └── SQLite — embedded database untuk eksperimen

Keamanan:
  ├── OWASP WebGoat — vulnerable app untuk latihan
  ├── HackTheBox / TryHackMe — CTF platform
  └── Burp Suite Community — web security testing

Sistem Operasi:
  ├── Linux (Ubuntu/Debian) — environment utama
  ├── strace, ltrace — system call tracing
  └── perf, valgrind — performance profiling
```

---

## 🤝 Kontribusi & Lisensi

### Cara Berkontribusi

```bash
# 1. Fork repositori ini
git fork https://github.com/[org]/cs-foundations-curriculum

# 2. Buat branch untuk kontribusi Anda
git checkout -b feat/improve-bab-04-modul-02

# 3. Commit dengan pesan yang deskriptif
git commit -m "feat(bab-04): tambah visualisasi AVL tree rotation"

# 4. Push dan buat Pull Request
git push origin feat/improve-bab-04-modul-02
```

### Panduan Kontribusi

- **Bug/Typo:** Langsung buat PR dengan perbaikan
- **Konten Baru:** Diskusikan dulu di Issues sebelum implementasi
- **Soal Latihan:** Sertakan solusi di folder terpisah (`/solutions/`)
- **Terjemahan:** Buat folder bahasa baru (`/en/`, `/ms/`)

### Standar Kode

```python
# Semua kode contoh harus:
# ✅ Memiliki type hints (Python 3.10+)
# ✅ Memiliki docstring yang menjelaskan kompleksitas
# ✅ Memiliki contoh penggunaan di docstring
# ✅ Lulus linter (black, flake8, mypy)
# ✅ Memiliki unit test minimal

def binary_search(arr: list[int], target: int) -> int:
    """
    Cari target dalam array terurut menggunakan binary search.
    
    Kompleksitas Waktu: O(log n)
    Kompleksitas Ruang: O(1)
    
    Args:
        arr: Array integer yang sudah terurut secara ascending
        target: Nilai yang dicari
    
    Returns:
        Index target jika ditemukan, -1 jika tidak ditemukan
    
    Examples:
        >>> binary_search([1, 3, 5, 7, 9], 5)
        2
        >>> binary_search([1, 3, 5, 7, 9], 4)
        -1
    """
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = left + (right - left) // 2  # Hindari integer overflow
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1
```

### Lisensi

```
MIT License

Copyright (c) 2024 CS Foundations Curriculum Contributors

Izin diberikan secara gratis kepada siapa pun yang mendapatkan salinan
perangkat lunak ini dan file dokumentasi terkait ("Perangkat Lunak"),
untuk menggunakan Perangkat Lunak tanpa batasan, termasuk tanpa batasan
hak untuk menggunakan, menyalin, memodifikasi, menggabungkan, menerbitkan,
mendistribusikan, mensublisensikan, dan/atau menjual salinan Perangkat Lunak.
```

---

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    RINGKASAN KURIKULUM — QUICK REFERENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  BAB 01 │ Logika & Matematika Diskrit    │ ⭐⭐      │ ⏱️ 28–35 jam
  BAB 02 │ Arsitektur Komputer            │ ⭐⭐      │ ⏱️ 30–38 jam
  BAB 03 │ Sistem Operasi                 │ ⭐⭐⭐    │ ⏱️ 35–42 jam
  BAB 04 │ Struktur Data ★ INTI          │ ⭐⭐⭐    │ ⏱️ 40–50 jam
  BAB 05 │ Algoritma ★ INTI              │ ⭐⭐⭐⭐  │ ⏱️ 45–55 jam
  BAB 06 │ Jaringan Komputer              │ ⭐⭐⭐    │ ⏱️ 32–40 jam
  BAB 07 │ Basis Data                     │ ⭐⭐⭐    │ ⏱️ 35–42 jam
  BAB 08 │ Rekayasa Perangkat Lunak       │ ⭐⭐⭐    │ ⏱️ 35–42 jam
  BAB 09 │ Keamanan & Kriptografi         │ ⭐⭐⭐⭐  │ ⏱️ 35–42 jam
  BAB 10 │ Komputasi Lanjutan             │ ⭐⭐⭐⭐  │ ⏱️ 30–38 jam
  ───────┼────────────────────────────────┼──────────┼──────────────
  TOTAL  │ 10 Bab · 30 Modul             │          │ ⏱️ ~400 jam
  ───────┼────────────────────────────────┼──────────┼──────────────
  CAPSTONE│ Distributed KV Store          │ ⭐⭐⭐⭐  │ ⏱️ 80–100 jam

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Referensi Resmi: https://roadmap.sh/computer-science
  Versi Kurikulum: 2.0.0 | Terakhir Diperbarui: 2024
  Standar: GEMINI.md Technical Curriculum Architecture
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```