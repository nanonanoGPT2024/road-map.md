---
[⬅️ BAB 02: Quiz & Challenge](../BAB-02-Tingkatan-dan-Tipe-Pengujian/BAB-02-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: State Transition & White-Box ➡️](./Module-02-State-Transition-dan-White-Box-Coverage.md)
---

# Module 01: Teknik Pengujian Black-Box: Equivalence Partitioning (EP), Boundary Value Analysis (BVA), & Decision Table

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Memahami esensi dan filosofi **Black-Box Testing (Specification-Based Testing)** tanpa perlu mengetahui struktur internal kode program.
- Menguasai teknik **Equivalence Partitioning (EP)** untuk membagi domain input menjadi partisi valid dan invalid guna mereduksi jumlah kombinasi pengujian secara dramatis tanpa mengurangi cakupan uji (*test coverage*).
- Menguasai teknik **Boundary Value Analysis (BVA)** baik model 2-titik (*2-value boundary: boundary, just-above, just-below*) maupun model 3-titik (*min, min+, nominal, max-, max, out-of-bounds*).
- Menyusun **Decision Table Testing** (Tabel Keputusan) untuk memetakan kombinasi logika kondisi bisnis multi-variabel yang kompleks (*Boolean combinatorial testing*).
- Menerapkan **Cause-Effect Graphing** untuk mengidentifikasi kombinasi kondisi masukan dan efek keluaran yang saling bergantung.

---

## 2. Prerequisite
- Memahami konsep dasar testing, verification vs validation, dan defect lifecycle dari BAB 01.
- Pemahaman logika Boolean dasar (`AND`, `OR`, `NOT`).

---

## 3. Concept
Dalam dunia pengujian perangkat lunak, menguji setiap kemungkinan nilai masukan (*exhaustive testing*) adalah kemustahilan fisik dan matematis. Jika sebuah kolom isian formulir menerima bilangan bulat antara $1$ hingga $100.000$, menjalankan $100.000$ skenario pengujian adalah pemborosan waktu dan biaya yang tidak masuk akal.

**Teknik Desain Test Case Black-Box** hadir sebagai fondasi sains matematika untuk memilih subset data uji yang paling optimal dengan probabilitas tertinggi dalam menemukan cacat. Dua teknik paling fundamental dan wajib dikuasai oleh setiap QA profesional adalah **Equivalence Partitioning (EP)** dan **Boundary Value Analysis (BVA)**, ditambah **Decision Table Testing** untuk logika bisnis berbasis aturan jamak.

---

## 4. Why?
Mengapa kita membutuhkan teknik perancangan formal ini?
1. **Efisiensi Maksimal (Anti-Waste)**: Mereduksi 1.000 skenario pengujian acak menjadi hanya 4 atau 5 skenario berbobot tinggi yang merepresentasikan seluruh domain input.
2. **Karakteristik Kegagalan Perangkat Lunak di Titik Batas**: Riset empiris industri software menunjukkan bahwa lebih dari 70% bug logika terjadi tepat pada batas tepi (*boundaries*) akibat kesalahan operator pemrograman (misalnya menggunakan `<` alih-alih `<=`, atau kesalahan *Off-by-One*).
3. **Cakupan Logika yang Terbukti Secara Matematis**: Decision Table mencegah adanya kondisi logika tersembunyi (*hidden edge cases*) yang terlupakan oleh tim developer maupun product manager.

---

## 5. What?

### A. Equivalence Partitioning (EP)
Equivalence Partitioning adalah teknik membagi himpunan data input ke dalam kelompok-kelompok (*partitions / classes*) di mana sistem diasumsikan akan memperlakukan semua anggota dalam satu kelompok secara setara (*equivalent*).

- **Valid Equivalence Partition (VEP)**: Himpunan nilai input yang sah dan diterima oleh spesifikasi sistem.
- **Invalid Equivalence Partition (IEP)**: Himpunan nilai input yang tidak sah dan wajib ditolak oleh sistem dengan pesan error yang tepat.
- **Aturan Emas EP**: Cukup pilih **1 nilai perwakilan** dari setiap partisi untuk diuji. Jika 1 nilai perwakilan berhasil (atau gagal), maka semua anggota partisi tersebut diasumsikan berperilaku sama.

### B. Boundary Value Analysis (BVA)
Boundary Value Analysis adalah teknik pelengkap EP yang berfokus menguji nilai-nilai ekstrem pada batas tepi partisi. Cacat sistem paling sering bersembunyi tepat di garis perbatasan.

#### Dua Pendekatan BVA:
1. **2-Value BVA (Standar ISTQB)**:
   - Menguji tepat pada nilai batas (*boundary value*).
   - Menguji nilai tetangga terdekat di luar batas (*just outside / invalid*).
2. **3-Value BVA (Robustness Testing)**:
   - Untuk rentang $[A, B]$:
     - Titik Bawah: $A-1$ (Invalid), $A$ (Valid Min), $A+1$ (Valid Min+)
     - Titik Nominal: Nilai tengah aman
     - Titik Atas: $B-1$ (Valid Max-), $B$ (Valid Max), $B+1$ (Invalid)

### C. Decision Table Testing (Cause-Effect Analysis)
Ketika perilaku sistem ditentukan oleh kombinasi beberapa kondisi masukan (*business rules*), tabel keputusan digunakan untuk memetakan seluruh kombinasi logika.

Struktur Tabel Keputusan:
- **Conditions (Kondisi/Penyebab)**: Input variabel Boolean (True/False atau Yes/No).
- **Actions (Aksi/Efek)**: Respon atau keluaran sistem yang diharapkan.
- **Rules (Aturan/Kolom)**: Setiap kolom merepresentasikan 1 skenario pengujian unik. Jumlah aturan teoretis adalah $2^N$, di mana $N$ adalah jumlah kondisi Boolean.

---

## 6. How? Langkah Demi Langkah Penerapan

### Kasus: Validasi Usia Pengajuan Kartu Kredit
Spesifikasi Bisnis:
> *"Pengajuan kartu kredit hanya diizinkan untuk pemohon yang berusia antara 21 tahun hingga 65 tahun (inklusif). Usia harus berupa bilangan bulat positif."*

#### 1. Menerapkan Equivalence Partitioning (EP):
- Partisi Invalid 1: Usia $< 21$ (Contoh perwakilan: `15`) -> Sistem menolak (Terlalu muda).
- Partisi Valid: $21 \le \text{Usia} \le 65$ (Contoh perwakilan: `35`) -> Sistem menerima.
- Partisi Invalid 2: Usia $> 65$ (Contoh perwakilan: `72`) -> Sistem menolak (Melebihi batas usia).
- Partisi Invalid 3 (Tipe Data): Input non-numerik atau desimal (Contoh: `"dua puluh"`, `25.5`) -> Sistem menolak.

*Hasil EP*: Dari tak hingga kemungkinan angka, kita cukup menguji 4 test case!

#### 2. Menerapkan Boundary Value Analysis (BVA 3-Value):
Batas bawah adalah $21$, batas atas adalah $65$.
- Nilai Uji Batas Bawah:
  - `20` ($21 - 1$): Invalid (Ditolak)
  - `21` (Tepat Min): Valid (Diterima)
  - `22` ($21 + 1$): Valid (Diterima)
- Nilai Uji Batas Atas:
  - `64` ($65 - 1$): Valid (Diterima)
  - `65` (Tepat Max): Valid (Diterima)
  - `66` ($65 + 1$): Invalid (Ditolak)

*Hasil BVA*: 6 test case kritis yang akan langsung mendeteksi jika programmer salah menulis `usia > 21` (sehingga umur 21 tertolak secara tidak sengaja).

---

## 7. Analogy
Bayangkan sebuah jembatan penyeberangan yang memiliki tanda batas: *"Beban Maksimal 100 kg - 500 kg"*:
- **Equivalence Partitioning**:
  - Partisi 1 (Terlalu Ringan): Anda mencoba menaruh beban 50 kg. Sensor tidak mendeteksi kendaraan.
  - Partisi 2 (Normal): Anda menaruh beban 300 kg. Jembatan bekerja normal.
  - Partisi 3 (Overload): Anda menaruh beban 800 kg. Alarm berbunyi.
- **Boundary Value Analysis**:
  - Anda tidak menaruh beban 300 kg lagi. Anda menguji dengan tepat beban 99 kg, 100 kg, 101 kg, serta 499 kg, 500 kg, dan 501 kg.
  - Jika jembatan runtuh pada 500 kg padahal rambu menuliskan "hingga 500 kg", Anda telah menemukan bug kritis pada batas tepi.

---

## 8. Diagram

```text
========================================================================================
                          EQUIVALENCE PARTITIONING & BVA MAP
========================================================================================

    Invalid Partition 1          Valid Partition             Invalid Partition 2
     (Usia < 21 Tahun)        (21 <= Usia <= 65 Tahun)        (Usia > 65 Tahun)
 <-------------------------|=============================|------------------------->
                           21                           65
            |        |     |              |              |     |        |
           20       21    22             40             64    65       66
         (BVA)    (BVA)  (BVA)          (EP)           (BVA) (BVA)    (BVA)
        Invalid   Valid  Valid          Valid          Valid Valid   Invalid

========================================================================================
                    DECISION TABLE TESTING (LOGIKA DISKON MEMBER)
========================================================================================

 +------------------------------+---------+---------+---------+---------+
 | KONDISI (CONDITIONS)         | Rule 1  | Rule 2  | Rule 3  | Rule 4  |
 +------------------------------+---------+---------+---------+---------+
 | Apakah Pengguna Member VIP?  |   YES   |   YES   |   NO    |   NO    |
 | Total Belanja >= Rp 500.000? |   YES   |   NO    |   YES   |   NO    |
 +------------------------------+---------+---------+---------+---------+
 | AKSI (ACTIONS)               |         |         |         |         |
 +------------------------------+---------+---------+---------+---------+
 | Berikan Diskon 20%           |    X    |    -    |    -    |    -    |
 | Berikan Diskon 10%           |    -    |    X    |    X    |    -    |
 | Tidak Ada Diskon (Harga Pas) |    -    |    -    |    -    |    X    |
 +------------------------------+---------+---------+---------+---------+
```

---

## 9. Simple Example: Implementasi Fungsi Validasi dan Bug "Off-by-One"

Berikut adalah implementasi JavaScript sederhana yang mengandung bug batas tepi:

```javascript
// KODE SISTEM (SUT - System Under Test)
function isEligibleForCreditCard(age) {
  // BUG: Menggunakan operator '>' alih-alih '>='
  // Akibatnya pemohon berumur tepat 21 tahun tertolak!
  if (age > 21 && age <= 65) {
    return { eligible: true, message: "Pengajuan Diterima" };
  }
  return { eligible: false, message: "Usia Tidak Memenuhi Syarat" };
}

// TEST SUITE DENGAN BVA
console.log("Uji Batas 20 (Invalid):", isEligibleForCreditCard(20).eligible === false ? "PASS" : "FAIL");
console.log("Uji Batas 21 (Valid)  :", isEligibleForCreditCard(21).eligible === true ? "PASS" : "FAIL (BUG TERDETEKSI!)");
console.log("Uji Batas 65 (Valid)  :", isEligibleForCreditCard(65).eligible === true ? "PASS" : "FAIL");
console.log("Uji Batas 66 (Invalid):", isEligibleForCreditCard(66).eligible === false ? "PASS" : "FAIL");
```

---

## 10. Practical Example: Merancang Decision Table untuk Sistem Checkout Promo

Spesifikasi Promo E-Commerce:
1. Kondisi 1 ($C_1$): Menggunakan Kartu Debit Mandiri.
2. Kondisi 2 ($C_2$): Total transaksi $\ge \text{Rp } 300.000$.
3. Kondisi 3 ($C_3$): Kuota promo harian masih tersedia.
4. Aturan: Cashback Rp 50.000 hanya diberikan jika ketiga kondisi terpenuhi ($C_1 \land C_2 \land C_3$). Jika salah satu tidak terpenuhi, harga normal tanpa cashback.

Tabel Keputusan Lengkap:

| Kondisi & Aksi | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 |
|---|---|---|---|---|---|---|---|---|
| $C_1$: Debit Mandiri? | Y | Y | Y | Y | T | T | T | T |
| $C_2$: Belanja $\ge$ 300k? | Y | Y | T | T | Y | Y | T | T |
| $C_3$: Kuota Tersedia? | Y | T | Y | T | Y | T | Y | T |
| **Aksi: Diberikan Cashback 50k** | **[X]** | - | - | - | - | - | - | - |
| **Aksi: Harga Normal (No Cashback)**| - | **[X]**| **[X]**| **[X]**| **[X]**| **[X]**| **[X]**| **[X]**|

*Optimasi QA (Collapsing Rules)*: Rule 5–8 dapat disatukan jika kondisi kartu bukan Mandiri otomatis menggagalkan promo tanpa peduli belanja dan kuota. Namun Decision Table memastikan tim tidak melupakan skenario *kuota habis saat kartu dan belanja valid* (Rule 2).

---

## 11. Real World Example: Ledakan Roket Ariane 5 Akibat Konversi Data Batas Tepi
Pada tanggal 4 Juni 1996, roket tanpa awak **Ariane 5** milik European Space Agency meledak 37 detik setelah peluncuran dengan kerugian lebih dari $370 juta:
- **Penyebab Utama**: Terjadi konversi nilai floating point 64-bit kecepatan horizontal ke dalam integer 16-bit bertanda (*signed 16-bit integer*).
- **Analisis Batas (BVA)**: Integer 16-bit hanya mampu menampung nilai antara $-32.768$ hingga $+32.767$. Kecepatan roket Ariane 5 melebihi angka $32.767$.
- **Akibat**: Terjadi *Arithmetic Overflow Trap*. Komputer kemudi mengalami crash, sistem roket berbelok tajam 90 derajat hingga pecah di udara akibat tekanan aerodinamis.
- Pelajaran Berharga: Kegagalan menguji nilai batas (*boundary overflow test*) pada konversi tipe data dapat berakibat fatal pada sistem kritikal.

---

## 12. Trade-offs

| Teknik Desain Test | Kelebihan | Kelemahan | Kapan Paling Efektif? |
|---|---|---|---|
| **Equivalence Partitioning (EP)** | Memangkas jumlah test case secara masif, mudah dipahami tim. | Melewatkan bug di tepi batas jika hanya memilih nilai tengah partisi. | Form input isian tunggal, range angka besar, enum kategori. |
| **Boundary Value Analysis (BVA)** | Menangkap bug paling umum (off-by-one, overflow) dengan akurasi tinggi. | Hanya berlaku untuk tipe data yang dapat diurutkan (angka, tanggal, panjang teks). | Batas minimum belanja, batas karakter password, limit kuota transfer. |
| **Decision Table** | Menemukan kombinasi logika bisnis yang terabaikan, dokumentasi jelas. | Ukuran tabel membengkak eksponensial ($2^N$) jika kondisi terlalu banyak. | Logika diskon bertingkat, matriks tarif asuransi, aturan persetujuan kredit. |

---

## 13. When To Use
- Gunakan **EP** pada setiap field formulir pendaftaran untuk menentukan nilai valid, format email salah, dan karakter dilarang.
- Gunakan **BVA** pada setiap input yang memiliki batas eksplisit (panjang karakter teks, umur, saldo, kuota, tanggal kedaluwarsa).
- Gunakan **Decision Table** ketika logika bisnis memiliki kombinasi 3 atau lebih aturan `IF-ELSE` bersarang.

## 14. When NOT To Use
- Jangan menggunakan BVA pada tipe data kategorikal yang tidak memiliki urutan alamiah (misalnya warna: Merah, Hijau, Biru; tidak ada konsep "Batas Merah"). Gunakan EP.
- Jangan membuat Decision Table untuk alur yang sepenuhnya berurutan dari langkah A ke B tanpa percabangan kondisi.

---

## 15. Common Mistakes

```text
1. MISTAKE: Hanya menguji nilai tengah partisi dan melewatkan nilai batas (Hanya EP tanpa BVA).
   WHY IT HAPPENS: QA mengira menguji umur 35 tahun sudah cukup membuktikan validasi 21–65 tahun bekerja.
   WHY IT IS BAD: Bug off-by-one pada umur 21 atau 65 tahun lolos sepenuhnya ke produksi.
   CORRECT APPROACH: Pasangkan selalu Equivalence Partitioning dengan Boundary Value Analysis.

2. MISTAKE: Memasukkan dua nilai input invalid sekaligus dalam satu skenario uji EP.
   WHY IT HAPPENS: QA ingin menghemat waktu dengan menguji umur negatif (-5) dan nama kosong sekaligus.
   WHY IT IS BAD: Fenomena Masking: Anda tidak tahu error mana yang sebenarnya memicu penolakan sistem.
   CORRECT APPROACH: Uji partisi invalid satu per satu secara terisolasi (Single Fault Assumption).
```

---

## 16. Best Practices

### Must Have
- Untuk setiap rentang numerik $[MIN, MAX]$, wajib menyertakan minimal 4 titik uji BVA: $MIN-1$, $MIN$, $MAX$, dan $MAX+1$.
- Menerapkan *Single Fault Assumption* saat menguji partisi invalid (hanya 1 field yang dibuat salah dalam satu waktu).

### Recommended
- Menggunakan generator kombinasi uji otomatis (*pairwise / orthogonal arrays*) jika kondisi tabel keputusan melebihi 5 variabel ($> 32$ kombinasi).
- Mendokumentasikan tabel partisi EP dan BVA langsung pada lampiran tiket User Story sebelum koding dimulai (*Shift-Left Specification*).

### Advanced
- Melakukan analisis BVA pada batas memori buffer dan ukuran payload HTTP (misal: tepat 1 byte sebelum batas limit upload 10 MB dan 1 byte setelahnya).

### Avoid / Overengineering
- Menguji 50 variasi angka invalid di dalam satu partisi yang sama (misal menguji umur -1, -2, -3, -4, -5...). Menguji -1 sudah mewakili seluruh partisi bilangan bulat negatif.

---

## 17. Troubleshooting: Menangani Batas Tepi Tanggal dan Waktu (Timezone Edge Cases)
BVA pada tanggal sering menimbulkan bug rumit akibat zona waktu (*Timezone Leap*):
1. **Penyebab**: Batas akhir promo adalah pukul `23:59:59 WIB (UTC+7)`. Jika server backend menggunakan UTC, promo bisa mati lebih awal pada pukul `16:59:59 WIB`.
2. **Solusi QA**: Uji tepat pada detik pergantian hari:
   - $T_1$: `2026-12-31 23:59:59` (Promo Wajib Aktif).
   - $T_2$: `2027-01-01 00:00:00` (Promo Wajib Tertolak Tepat Waktu).
   - Pastikan pengujian dilakukan dengan menyamakan zona waktu klien dan server.

---

## 18. Exercise
1. Sebuah kolom input password memiliki aturan:
   - Panjang karakter: minimal 8 karakter dan maksimal 16 karakter.
   - Karakter harus alfanumerik.
   - Tentukan:
     - Partisi valid dan partisi invalid menggunakan teknik **Equivalence Partitioning**.
     - Nilai panjang karakter yang wajib diuji menggunakan teknik **Boundary Value Analysis (BVA 3-Value)**.
2. Buatlah tabel keputusan (Decision Table) untuk sistem penentuan denda keterlambatan buku perpustakaan:
   - Kondisi 1: Keterlambatan $\le 7$ hari.
   - Kondisi 2: Buku berkategori "Referensi Khusus".
   - Aturan: Buku biasa terlambat denda Rp 1.000/hari; Buku referensi terlambat denda Rp 5.000/hari; Jika tepat waktu denda Rp 0.

---

## 19. Challenge
Rancang sebuah **Test Case Specification Document** komprehensif untuk modul kalkulasi premi asuransi kendaraan bermotor:
- Aturan Usia Pengemudi: $< 25$ tahun (Premi Tinggi), $25–60$ tahun (Premi Normal), $> 60$ tahun (Premi Tinggi).
- Riwayat Kecelakaan: Pernah klaim dalam 2 tahun terakhir (Ya/Tidak). Jika Ya, ada tambahan surcharge 30%.
- Jenis Asuransi: Total Loss Only (TLO) vs All Risk.
Tentukan partisi EP, nilai BVA, dan susun Decision Table lengkap untuk memetakan seluruh kombinasi premi.

---

## 20. Summary
- Equivalence Partitioning membagi domain input menjadi kelompok setara untuk memilih perwakilan data uji secara efisien.
- Boundary Value Analysis memfokuskan pengujian pada titik batas tepi di mana mayoritas bug logika (*off-by-one*) terjadi.
- Decision Table Testing memastikan seluruh kombinasi aturan bisnis multi-variabel terpetakan secara lengkap dan tidak ada skenario terabaikan.

---

## Hands-on Practice: Simulator Generator Test Case BVA, EP, & Decision Table
Jalankan script generator mandiri yang mem-parsing spesifikasi rentang data, mengkalkulasi partisi valid/invalid, memproduksi titik uji batas BVA, dan mengevaluasi tabel keputusan logika bisnis secara otomatis:

```bash
node QA/BAB-03-Teknik-Perancangan-Test-Case-Black-Box-White-Box/hands-on/m01/bva_equivalence_generator_sim.js
```

---
[⬅️ BAB 02: Quiz & Challenge](../BAB-02-Tingkatan-dan-Tipe-Pengujian/BAB-02-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: State Transition & White-Box ➡️](./Module-02-State-Transition-dan-White-Box-Coverage.md)
---
