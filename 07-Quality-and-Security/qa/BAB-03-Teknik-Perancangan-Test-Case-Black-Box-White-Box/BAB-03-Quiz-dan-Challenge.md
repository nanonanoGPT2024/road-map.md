---
[⬅️ Module 02: State Transition & White-Box](./Module-02-State-Transition-dan-White-Box-Coverage.md) | [📋 Silabus Induk](../README.md) | [BAB 04: Pengujian API ➡️](../BAB-04-Pengujian-API-dan-Validasi-Kontrak/Module-01-Fondasi-API-Testing-HTTP-Status-Codes-Headers.md)
---

# BAB 03: Quiz, Evaluasi, & Practical Challenge

## 1. Chapter Summary & Evaluasi Pemahaman
Pada BAB 03, Anda telah menguasai metode ilmiah perancangan test case tingkat tinggi:
1. **Black-Box Testing**: Merancang test case berbasis spesifikasi fungsi tanpa melihat struktur kode internal.
2. **Equivalence Partitioning (EP)**: Membagi domain masukan menjadi partisi valid dan invalid, serta memilih satu nilai perwakilan dari setiap partisi untuk memangkas jumlah pengujian secara masif.
3. **Boundary Value Analysis (BVA)**: Menangkap bug off-by-one yang bersembunyi tepat di tepi batas (2-value boundary dan 3-value robustness model).
4. **Decision Table Testing**: Memetakan kombinasi logika bisnis multivariabel ($2^N$ aturan) secara terstruktur.
5. **State Transition Testing**: Menguji sistem stateful melalui matriks transisi valid dan penolakan transisi terlarang (*negative testing*).
6. **White-Box Code Coverage & Cyclomatic Complexity**: Mengukur kecukupan uji struktural (Statement, Branch, MC/DC) dan menghitung jumlah jalur independen ($V(G) = P + 1$) untuk membuktikan integritas kode secara matematis.

---

## 2. Interactive Quiz

### Bagian A: Basic Questions (Konseptual Fundamental)
1. **Pertanyaan 1**: Mengapa pengujian nilai tengah pada Equivalence Partitioning belum cukup untuk menjamin kebenaran logika validasi angka?
2. **Pertanyaan 2**: Sebutkan titik-titik uji 3-Value BVA untuk sebuah input kuota pengiriman barang yang dibatasi antara 1 kg hingga 30 kg!
3. **Pertanyaan 3**: Apa perbedaan antara **State (Status)** dan **Event (Pemicu)** dalam State Transition Testing?
4. **Pertanyaan 4**: Mengapa pencapaian 100% **Statement Coverage** belum menjamin bahwa 100% **Branch Coverage** telah tercapai?
5. **Pertanyaan 5**: Apa rumus Thomas McCabe untuk menghitung **Cyclomatic Complexity** menggunakan jumlah titik predikat keputusan ($P$)?

### Bagian B: Intermediate Questions (Analisis & Perhitungan)
6. **Pertanyaan 6**: Sebuah formulir diskon belanja memiliki aturan: *"Diskon 15% diberikan jika pengguna berstatus Mahasiswa ATAU memiliki kupon promo, DAN total transaksi minimal Rp 100.000."* Berapa jumlah aturan teoretis pada Decision Table sebelum disederhanakan (*collapsed*)?
7. **Pertanyaan 7**: Perhatikan kode fungsi berikut:
   ```javascript
   function classifyGrade(score) {
     if (score >= 85) return "A";
     else if (score >= 70) return "B";
     else if (score >= 55) return "C";
     return "D";
   }
   ```
   Hitunglah nilai Cyclomatic Complexity $V(G)$ dari fungsi di atas dan tentukan jumlah minimum test case untuk mencapai 100% Branch Coverage!
8. **Pertanyaan 8**: Dalam State Transition Testing, apa yang dimaksud dengan **1-Switch Coverage** dan mengapa pengujian ini penting untuk mendeteksi bug efek samping status perantara?
9. **Pertanyaan 9**: Apa prinsip *Single Fault Assumption* saat menguji partisi ekuivalensi invalid (negatif)? Mengapa memasukkan beberapa input salah sekaligus dalam 1 test case adalah praktik buruk?
10. **Pertanyaan 10**: Apa itu standar cakupan **MC/DC (Modified Condition/Decision Coverage)** dan mengapa standar ini diwajibkan dalam pengujian perangkat lunak penerbangan komersial (DO-178C)?

### Bagian C: Scenario-Based Questions (Problem Solving Dunia Nyata)
11. **Skenario 1**: Sebuah platform lelang online memiliki sistem penawaran: *"Penawar baru harus memasukkan harga penawaran minimal Rp 10.000 di atas harga tertinggi saat ini. Batas waktu lelang berakhir tepat pukul 23:59:59 WIB."* Rancanglah daftar skenario BVA untuk harga penawaran dan waktu penutupan lelang guna mendeteksi potensi bug off-by-one dan race condition.
12. **Skenario 2**: Pada aplikasi pinjaman online, ditemukan celah keamanan kritis di mana pengguna yang status pinjamannya masih `PENDING_SURVEY` berhasil mencairkan dana dengan langsung memanggil endpoint API `/loan/disburse`. Berdasarkan teknik State Transition Testing, kelalaian apa yang dilakukan oleh tim pengembang dan tim QA?
13. **Skenario 3**: Sebuah modul transfer bank memiliki 100% statement coverage di laporan SonarQube. Namun ketika terjadi lonjakan transaksi, sistem mengalami crash dengan error: `NullPointerException: account.currency is undefined`. Jelaskan bagaimana teknik White-Box Condition Coverage dapat mendeteksi celah ini sebelum kode dirilis.

---

## 3. Chapter Challenge: Perancangan Test Suite Sistem Ticketing Bioskop

### Deskripsi Skenario
Sebuah jaringan bioskop modern bernama **"CineStar"** memiliki aturan penentuan harga tiket dan status pemesanan kursi:
- **Aturan Hari & Kategori Usia**:
  - Hari Biasa (Senin - Kamis): Tiket Dewasa Rp 40.000, Anak-anak ($\le 12$ tahun) Rp 25.000, Lansia ($\ge 60$ tahun) Rp 30.000.
  - Akhir Pekan (Jumat - Minggu): Tambahan biaya flat Rp 15.000 untuk semua kategori usia.
  - Film Khusus Dewasa (Rating 21+): Penonton usia $< 21$ tahun dilarang keras membeli tiket (Sistem menolak transaksi).
- **State Machine Kursi**:
  - `AVAILABLE` $\to$ Pengguna memilih kursi $\to$ `RESERVED_TEMPORARY` (Timer 10 Menit).
  - Dari `RESERVED_TEMPORARY`:
    - Pembayaran Sukses $\to$ `BOOKED_PAID` (Selesai).
    - Timer Habis $\to$ `AVAILABLE` (Otomatis lepas).
    - Pengguna Klik Batal $\to$ `AVAILABLE`.
  - Dari `BOOKED_PAID`:
    - Refund Resmi Disetujui $\to$ `AVAILABLE`.

### Tugas Anda (Deliverables):
1. **Analisis BVA Kategori Usia**:
   Tentukan seluruh titik uji Boundary Value Analysis (3-value) untuk batasan umur anak-anak ($12$ tahun), batas bawah rating dewasa ($21$ tahun), dan batas lansia ($60$ tahun).
2. **Decision Table Matriks Harga Tiket**:
   Susun tabel keputusan lengkap untuk menentukan nominal harga tiket berdasarkan kombinasi Hari (Weekday vs Weekend) dan Usia (Anak, Dewasa, Lansia, serta usia $< 21$ pada film 21+).
3. **State Transition & Negative Test Matrix**:
   - Gambarkan matriks tabel transisi status kursi bioskop.
   - Rancang minimal 2 skenario pengujian negatif transisi terlarang (*illegal state transitions*), misalnya upaya membeli kursi yang sedang `BOOKED_PAID` tanpa refund.
4. **Analisis Kompleksitas Kode**:
   Tuliskan pseudo-code fungsi penentu harga dan hitung nilai Cyclomatic Complexity $V(G)$-nya.

---

## 4. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Prinsip Black-Box testing dan mengapa testing berbasis spesifikasi sangat efisien.
- [ ] Teknik pembagian partisi Equivalence Partitioning (VEP vs IEP).
- [ ] Titik-titik uji Boundary Value Analysis (2-value dan 3-value model).
- [ ] Cara menyusun dan menyederhanakan matriks Decision Table.
- [ ] Komponen State Machine (State, Event, Transition, Action).
- [ ] Hierarki Code Coverage (Statement, Branch, Condition, MC/DC).
- [ ] Perhitungan Cyclomatic Complexity ($V(G) = P + 1$).

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh bukti matematis teorema graf Euler-McCabe (cukup menggunakan rumus praktis $P + 1$).
- [ ] Syntax spesifik tool code coverage tertentu (prinsip instrumen cabang berlaku universal di semua bahasa).

### Saya Harus Bisa Melakukan:
- [ ] Merancang titik uji BVA untuk mendeteksi bug off-by-one.
- [ ] Menyusun Decision Table untuk logika bisnis majemuk.
- [ ] Menguji penolakan transisi status ilegal pada sistem perbankan/e-commerce.
- [ ] Menentukan jumlah test case basis path menggunakan Cyclomatic Complexity.

---
[⬅️ Module 02: State Transition & White-Box](./Module-02-State-Transition-dan-White-Box-Coverage.md) | [📋 Silabus Induk](../README.md) | [BAB 04: Pengujian API ➡️](../BAB-04-Pengujian-API-dan-Validasi-Kontrak/Module-01-Fondasi-API-Testing-HTTP-Status-Codes-Headers.md)
---
