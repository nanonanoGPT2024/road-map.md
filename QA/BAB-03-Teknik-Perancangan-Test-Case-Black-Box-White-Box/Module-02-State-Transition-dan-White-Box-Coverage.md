---
[⬅️ Module 01: Black-Box EP, BVA, & Decision Table](./Module-01-Black-Box-Equivalence-Partitioning-BVA-Decision-Table.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 03 ➡️](./BAB-03-Quiz-dan-Challenge.md)
---

# Module 02: State Transition Testing & Teknik White-Box (Statement, Branch, & Cyclomatic Complexity)

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Menguasai teknik perancangan **State Transition Testing** (State Diagram & State Transition Table) untuk menguji sistem yang perilakunya bergantung pada riwayat kondisi masa lalu (*stateful systems*).
- Membedakan pengujian transisi valid (*Valid Transitions: 0-switch, 1-switch coverage*) dan penolakan transisi terlarang (*Invalid Transitions / Negative Testing*).
- Memahami filosofi **White-Box Testing (Structural Testing)** yang memeriksa jalur eksekusi internal, logika percabangan, dan aliran kontrol program (*Control Flow Graph*).
- Menghitung dan membedakan metrik cakupan struktural: **Statement Coverage**, **Branch / Decision Coverage**, **Condition Coverage**, serta standar avionik **Modified Condition/Decision Coverage (MC/DC)**.
- Menghitung kompleksitas siklomatis program (**Thomas McCabe's Cyclomatic Complexity**: $V(G) = E - N + 2P$) untuk menentukan batas bawah jumlah test case independen yang wajib dirancang.

---

## 2. Prerequisite
- Memahami konsep dasar Black-Box (EP, BVA, Decision Table) dari Module 01.
- Pemahaman logika percabangan kode (`if-else`, `switch-case`, `loops`) dan representasi graf sederhana (Nodes, Edges).

---

## 3. Concept
Sebagian besar sistem perangkat lunak modern tidak berperilaku seperti fungsi matematika murni yang tanpa ingatan (*stateless*). Aplikasi perbankan, proses checkout e-commerce, mesin ATM, dan alur pemesanan tiket penerbangan adalah **Sistem Berbasis State (Stateful Systems)**. Masukan (*input*) yang sama dapat menghasilkan keluaran (*output*) yang sama sekali berbeda tergantung pada status (*state*) sistem saat itu.

Untuk menguji aspek dinamis ini, QA menggunakan **State Transition Testing**. Di sisi lain, untuk membuktikan bahwa tidak ada baris kode atau percabangan logika tersembunyi yang belum teruji oleh Black-Box, kita menggunakan teknik **White-Box Testing** dengan metrik matematis **Code Coverage** dan **Cyclomatic Complexity**.

---

## 4. Why?
Mengapa State Transition dan White-Box Testing sangat krusial?
1. **Mendeteksi Kerentanan Urutan Alur (Out-of-Order Execution Bug)**: Banyak bug berbahaya terjadi ketika pengguna melompati langkah-langkah tertentu (misal: langsung memanggil API `/order/pay` sebelum keranjang belanja di-checkout).
2. **Menemukan "Dead Code" dan "Untested Logic Branches"**: Black-Box test bisa saja lulus 100%, namun ternyata 40% kode percabangan darurat (*error handling blocks*) di dalam fungsi tidak pernah tersentuh oleh pengujian.
3. **Mengukur Kompleksitas Kode Secara Objektif**: Cyclomatic Complexity memberikan metrik pasti kepada QA dan Tech Lead kapan sebuah modul harus dipecah (*refactoring*) karena terlalu rumit untuk diuji secara aman.

---

## 5. What?

### A. Komponen State Transition Testing
1. **State (Keadaan)**: Kondisi stabil di mana sistem sedang menunggu satu atau lebih kejadian (*events*), misalnya: `LOGGED_OUT`, `AUTHENTICATED`, `LOCKED`.
2. **Event / Trigger (Pemicu)**: Masukan dari luar sistem yang memicu respon, misalnya: `Input PIN Benar`, `Klik Tombol Batal`.
3. **Transition (Transisi)**: Perpubahan status sistem dari satu state ke state lain yang diakibatkan oleh suatu event.
4. **Action (Aksi)**: Respon atau keluaran sistem yang terjadi bersamaan dengan transisi, misalnya: `Keluarkan Uang Tunai`, `Tampilkan Pesan Blokir`.

#### Tingkatan Cakupan Transisi (Switch Coverage):
- **0-Switch Coverage**: Setiap transisi tunggal ($S_A \to S_B$) diuji minimal 1 kali.
- **1-Switch Coverage**: Menguji pasangan transisi berurutan ($S_A \to S_B \to S_C$) untuk memverifikasi efek samping status perantara.

---

### B. Spektrum Cakupan White-Box (Code Coverage Hierarchy)

```text
+-------------------------------------------------------------------------+
| Level 4: MODIFIED CONDITION/DECISION COVERAGE (MC/DC)                   |
| Standar keselamatan tinggi (Avionik DO-178C). Setiap kondisi terbukti   |
| mempengaruhi hasil keputusan secara independen.                         |
+-------------------------------------------------------------------------+
| Level 3: CONDITION COVERAGE                                             |
| Setiap sub-kondisi boolean dievaluasi TRUE dan FALSE minimal 1 kali.   |
+-------------------------------------------------------------------------+
| Level 2: BRANCH / DECISION COVERAGE                                     |
| Setiap cabang percabangan (TRUE dan FALSE) dieksekusi minimal 1 kali.   |
+-------------------------------------------------------------------------+
| Level 1: STATEMENT COVERAGE                                             |
| Setiap baris pernyataan instruksi kode dieksekusi minimal 1 kali.       |
+-------------------------------------------------------------------------+
```

1. **Statement Coverage**:
   $$\text{Statement Coverage} = \left( \frac{\text{Jumlah Statement Tereksekusi}}{\text{Total Statement}} \right) \times 100\%$$
   *Kelemahan*: Dapat mencapai 100% statement coverage tanpa pernah menguji cabang `else` yang kosong!
2. **Branch / Decision Coverage**:
   $$\text{Branch Coverage} = \left( \frac{\text{Jumlah Cabang Percabangan Tereksekusi}}{\text{Total Cabang}} \right) \times 100\%$$
   Menjamin setiap keputusan `if` dievaluasi baik kondisi `TRUE` maupun `FALSE`.
3. **Cyclomatic Complexity (Thomas McCabe)**:
   Mengukur jumlah jalur independen secara linier melalui graf kontrol aliran (*Control Flow Graph / CFG*):
   $$V(G) = E - N + 2P$$
   - $E$: Jumlah garis busur (*Edges*).
   - $N$: Jumlah titik simpul (*Nodes*).
   - $P$: Jumlah komponen yang terhubung (biasanya $P = 1$ untuk satu fungsi tunggal).
   - *Alternatif Praktis*: $V(G) = \text{Jumlah Titik Keputusan (Predikat: if, while, for, case)} + 1$.

---

## 6. How? Menganalisis State Transition dan Menghitung Kompleksitas

### Kasus 1: State Machine Otentikasi Akun (3 Kali Percobaan Salah -> Akun Terkunci)

#### Matriks Tabel Transisi (State Transition Table):

| State Asal | Event: PIN Benar | Event: PIN Salah (< 3 Kali) | Event: PIN Salah (= 3 Kali) | Event: Reset Admin |
|---|---|---|---|---|
| **S1: LOGGED_OUT** | $\to$ S2 (Dashboard) [Valid] | $\to$ S1 (Tampil Gagal) [Valid] | $\to$ S3 (Terkunci) [Valid] | Tidak Ada Aksi [Invalid] |
| **S2: LOGGED_IN** | Tidak Ada Aksi [Invalid] | Tidak Ada Aksi [Invalid] | Tidak Ada Aksi [Invalid] | $\to$ S1 [Valid] |
| **S3: LOCKED** | Ditolak [Invalid] | Ditolak [Invalid] | Ditolak [Invalid] | $\to$ S1 [Valid] |

*Pengujian Negatif (Invalid Transitions)*: Mencoba login dengan akun yang berstatus `S3: LOCKED` menggunakan PIN yang benar harus tetap **DITOLAK** oleh sistem.

---

### Kasus 2: Menghitung Cyclomatic Complexity dari Kode Nyata

```javascript
function evaluateLoan(income, creditScore, hasCollateral) {
  // Node 1: Entry
  if (income >= 10000000) {          // Predikat 1 (Node 2)
    if (creditScore >= 700) {        // Predikat 2 (Node 3)
      return "APPROVED_PREMIUM";     // Node 4
    } else {
      return "APPROVED_STANDARD";    // Node 5
    }
  } else if (hasCollateral) {         // Predikat 3 (Node 6)
    return "APPROVED_WITH_COLLATERAL"; // Node 7
  }
  return "REJECTED";                 // Node 8 (Exit)
}
```

#### Perhitungan $V(G)$:
- Titik Predikat Keputusan:
  1. `if (income >= 10000000)`
  2. `if (creditScore >= 700)`
  3. `else if (hasCollateral)`
- Total Predikat = 3
- $$V(G) = \text{Predikat} + 1 = 3 + 1 = 4$$
- **Artinya**: Dibutuhkan **minimal 4 test case independen** untuk mencapai 100% Branch Coverage pada fungsi ini!

---

## 7. Analogy
- **State Transition Testing**: Bayangkan sebuah pintu putar otomatis kereta bawah tanah (Turnstile):
  - Dalam kondisi `LOCKED`, Anda mendorong pintu: pintu tetap macet (*Invalid Action*).
  - Anda menempelkan tiket kartu (*Event*): status berubah menjadi `UNLOCKED`.
  - Anda mendorong pintu (*Event*): Anda lewat, dan pintu otomatis kembali ke status `LOCKED`.
  - Jika seorang penumpang bisa lewat dua kali hanya dengan satu kali tap tiket, ada cacat transisi state pada sistem pintu.
- **Cyclomatic Complexity**: Bayangkan labirin jalan raya:
  - Setiap kali ada persimpangan jalan bercabang dua (`if-else`), jumlah rute perjalanan bertambah satu.
  - Kompleksitas siklomatis adalah jumlah rute minimum yang harus dilalui oleh mobil patroli inspeksi agar tidak ada satu pun ruas jalan di labirin yang terlewat dari patroli.

---

## 8. Diagram

```text
========================================================================================
                          STATE TRANSITION DIAGRAM (AKUN LOGIN)
========================================================================================

                 +---------------------------------------------+
                 |                                             |
                 v                                             | Admin Unlock
          +-------------+      PIN Benar      +-------------+  |
          |             | ------------------> |             |  |
          | LOGGED_OUT  |                     |  LOGGED_IN  |  |
          |             | <------------------ |             |  |
          +------+------+        Logout       +-------------+  |
                 |                                             |
                 | PIN Salah (< 3x)                            |
                 v (Looping State)                             |
          [Increment Counter]                                  |
                 |                                             |
                 | PIN Salah (Ke-3 Kali)                       |
                 v                                             |
          +-------------+                                      |
          |   LOCKED    | -------------------------------------+
          +-------------+
            (Semua login ditolak)

========================================================================================
                     CONTROL FLOW GRAPH (CYCLOMATIC COMPLEXITY)
========================================================================================

                             ( 1. Entry )
                                  |
                                  v
                        [ 2. income >= 10jt? ]
                               /      \
                             TRUE    FALSE
                             /          \
            [ 3. creditScore >= 700? ]   [ 6. hasCollateral? ]
                 /            \                 /        \
               TRUE          FALSE            TRUE      FALSE
               /                \             /            \
        (4. APPROVED)    (5. STANDARD)  (7. COLLATERAL)  (8. REJECTED)
               \                /             \            /
                +-------+------+               +-----+----+
                        |                            |
                        v                            v
                            =====> ( EXIT ) <=====
```

---

## 9. Simple Example: Perbedaan 100% Statement vs 100% Branch Coverage

Perhatikan kode berikut:

```javascript
function checkAccess(isAdmin, isActive) {
  let access = "DENIED";
  if (isAdmin && isActive) {
    access = "GRANTED";
  }
  return access;
}
```

- **Skenario 1**: Input `isAdmin = true, isActive = true` -> Output: `"GRANTED"`.
  - Seluruh baris kode (Statement 1, 2, 3, 4) tereksekusi.
  - **Statement Coverage = 100%**!
  - Namun apakah cabang `FALSE` dari `if` sudah teruji? **BELUM!**
- **Skenario 2**: Tambahkan input `isAdmin = false, isActive = true` -> Output: `"DENIED"`.
  - Cabang `FALSE` tereksekusi.
  - **Branch Coverage = 100%**.
- Pelajaran: Statement coverage 100% dapat memberikan kepalsuan rasa aman (*false sense of thoroughness*).

---

## 10. Practical Example: 4 Test Case Independen untuk Basis Path Testing

Berdasarkan fungsi kalkulasi pinjaman dengan $V(G) = 4$ di section 6:

| Test Case ID | Input: `income` | Input: `creditScore` | Input: `hasCollateral` | Expected Output | Jalur Independen yang Diuji |
|---|---|---|---|---|---|
| **TC-01** | Rp 15.000.000 | 750 | Tidak Relevan | `"APPROVED_PREMIUM"` | Path 1: 1 -> 2 -> 3 -> 4 -> Exit |
| **TC-02** | Rp 15.000.000 | 650 | Tidak Relevan | `"APPROVED_STANDARD"`| Path 2: 1 -> 2 -> 3 -> 5 -> Exit |
| **TC-03** | Rp 5.000.000  | Tidak Relevan | `true` | `"APPROVED_WITH_COLLATERAL"` | Path 3: 1 -> 2 -> 6 -> 7 -> Exit |
| **TC-04** | Rp 5.000.000  | Tidak Relevan | `false`| `"REJECTED"` | Path 4: 1 -> 2 -> 6 -> 8 -> Exit |

Dengan 4 test case ini, kita menjamin **100% Branch Coverage** dan **100% Statement Coverage** secara matematis!

---

## 11. Real World Example: Tragedi Medis Therac-25 Akibat Cacat State Transition
Pada tahun 1985–1987, mesin terapi radiasi kanker **Therac-25** menewaskan beberapa pasien akibat overdosis radiasi masif ribuan rad:
- **Penyebab Utama**: Bug pada State Transition Machine perangkat lunak pengendali.
- **Kondisi Cacat**: Ketika operator mengetik instruksi penyiapan berkas elektron (*Electron Mode*), lalu dalam waktu kurang dari 8 detik menyadari kesalahan dan menekan tombol panah atas (*Cursor Up*) untuk mengganti ke *X-Ray Mode*, sistem berpindah state secara tidak sinkron (*Race Condition*).
- Cermin kolimator fisik belum bergeser ke posisi aman, tetapi berkas radiasi X-Ray berkekuatan penuh sudah ditembakkan langsung ke tubuh pasien.
- Pengujian perangkat lunak mesin tersebut gagal melakukan pengujian transisi state cepat (*rapid sequence transitions / negative state flows*).

---

## 12. Trade-offs

| Aspek Pengujian | Statement Coverage | Branch / Decision Coverage | State Transition Testing |
|---|---|---|---|
| **Kemudahan Implementasi**| Sangat Mudah (Banyak tool otomatis). | Sedang (Perlu memetakan semua jalur boolean). | Sedang hingga Rumit (Perlu membuat state diagram). |
| **Daya Tangkap Bug** | Rendah (Banyak edge case terlewat). | Tinggi (Menangkap kegagalan percabangan logika). | Sangat Tinggi untuk alur transaksi & sesi. |
| **Biaya Pemeliharaan** | Rendah. | Sedang. | Bertambah saat ada penambahan status baru. |

---

## 13. When To Use
- Gunakan **State Transition Testing** pada:
  - Alur Checkout & Pembayaran (Draft -> Pending Payment -> Paid -> Shipped -> Delivered -> Refunded).
  - Manajemen Sesi Pengguna (Guest -> Active -> Idle -> Expired -> Locked).
  - Alur Pemesanan Transportasi Online (Mencari Driver -> Driver Menuju Lokasi -> Perjalanan -> Selesai).
- Gunakan **Cyclomatic Complexity Analysis** sebagai metrik review kode: Jika $V(G) > 10$, fungsi tersebut wajib dipecah menjadi fungsi yang lebih kecil.

## 14. When NOT To Use
- Jangan membuat State Machine diagram untuk fungsi perhitungan matematika murni seperti konversi Celsius ke Fahrenheit (fungsi murni tidak memiliki state internal).
- Jangan memaksakan MC/DC testing (Modified Condition) pada aplikasi landing page promosi statis; MC/DC dikhususkan untuk software berisiko nyawa (*Safety-Critical: otomotif, penerbangan, alat medis*).

---

## 15. Common Mistakes

```text
1. MISTAKE: Hanya menguji transisi valid (Happy Path State) dan melupakan Invalid State Transitions.
   WHY IT HAPPENS: QA hanya mengikuti petunjuk alur normal di dokumen PRD.
   WHY IT IS BAD: Pengguna dapat memanggil API aksi terlarang (misal membatalkan pesanan yang statusnya sudah "Shipped").
   IMPACT: Kerugian finansial, inkonsistensi status database transaksi.
   CORRECT APPROACH: Bangun State Transition Matrix lengkap dan uji setiap sel yang bertanda "Invalid Transition" untuk memastikan dilempar HTTP 400/409 Conflict.

2. MISTAKE: Menganggap 100% Statement Coverage berarti kode sudah bebas bug.
   WHY IT HAPPENS: Laporan coverage di SonarQube/Istanbul menampilkan angka 100% berwarna hijau.
   WHY IT IS BAD: Mengabaikan percabangan null-check atau kondisi boolean majemuk.
   CORRECT APPROACH: Jadikan Branch Coverage sebagai target utama, bukan sekadar Statement Coverage.
```

---

## 16. Best Practices

### Must Have
- Memetakan seluruh transisi tidak sah (*Illegal State Transitions*) dan memverifikasi bahwa sistem menolaknya secara anggun (*graceful error handling*).
- Mencapai minimal **80% Branch Coverage** pada seluruh modul core business logic.

### Recommended
- Menggunakan library finite state machine formal di backend (misal `XState` atau `Spring Statemachine`) daripada puluhan variabel boolean `isPending`, `isPaid`, `isCancelled` yang rentan terhadap *Invalid State Combination*.
- Menjalankan tool analisis kompleksitas (seperti ESLint rule `complexity`) dengan ambang batas peringatan $V(G) = 10$.

### Advanced
- Menerapkan **1-Switch Coverage** pada state machine transaksi kritis (misal menguji rantai transisi $A \to B \to C$ dan $A \to D \to C$).

### Avoid / Overengineering
- Mengejar target 100% coverage pada file konfigurasi deklaratif atau wrapper library eksternal.

---

## 17. Troubleshooting: Mendeteksi "State Bleeding" pada Pengujian Otomasi
Jika test case A berhasil saat dijalankan sendiri, tetapi gagal saat dijalankan berurutan dengan test case B:
1. **Penyebab**: Terjadi kebocoran state (*State Bleeding / Shared In-Memory State*). Test case B mengubah variabel global atau database tanpa membersihkannya kembali.
2. **Solusi**: Wajib menerapkan *Teardown / Cleanup Hook* (`afterEach` / `resetDatabase`) agar setiap test case dimulai dari *Initial State* yang bersih dan independen.

---

## 18. Exercise
1. Sebuah siklus hidup pesanan e-commerce memiliki 4 state: `CART`, `CHECKOUT`, `PAID`, `CANCELLED`.
   - Buatlah State Transition Table lengkap yang mencantumkan event: `Checkout`, `Bayar Sukses`, `Bayar Gagal`, `Batalkan`.
   - Tentukan minimal 2 transisi invalid yang wajib ditolak oleh sistem.
2. Hitung nilai Cyclomatic Complexity $V(G)$ dari cuplikan kode berikut:
   ```javascript
   function validateUser(age, hasId, isBlacklisted) {
     if (isBlacklisted) {
       return "BLOCKED";
     }
     if (age >= 17 && hasId) {
       return "ALLOWED";
     }
     return "REJECTED";
   }
   ```
   Berapa jumlah test case minimum yang dibutuhkan untuk mencapai 100% branch coverage?

---

## 19. Challenge
Rancang sebuah **Finite State Machine Automation Engine** untuk alur otentikasi login multi-faktor (MFA):
- State: `INIT`, `PASSWORD_VERIFIED`, `MFA_PENDING`, `SESSION_ACTIVE`, `SUSPENDED`.
- Aturan: Pengguna hanya boleh salah memasukkan kode OTP maksimal 3 kali. Pada kesalahan ke-3, akun berpindah ke `SUSPENDED`.
- Buktikan dengan test suite bahwa upaya melompati state dari `INIT` langsung ke `SESSION_ACTIVE` tanpa melalui `MFA_PENDING` memicu `IllegalStateException`.

---

## 20. Summary
- State Transition Testing memverifikasi sistem stateful berdasarkan diagram dan tabel transisi, menguji jalur sah maupun penolakan aksi tidak sah.
- White-Box Testing mengevaluasi struktur logika kode internal menggunakan metrik cakupan Statement, Branch, Condition, dan MC/DC.
- Cyclomatic Complexity ($V(G) = \text{Predikat} + 1$) menentukan jumlah jalur uji independen yang dibutuhkan untuk menjamin tidak ada cabang logika yang terabaikan.

---

## Hands-on Practice: Simulator State Transition Machine & Cyclomatic Coverage
Jalankan script simulator yang mengimplementasikan state machine ATM/Fintech, memverifikasi aturan transisi state, menghitung graf aliran kontrol (CFG), dan mengevaluasi Branch Coverage secara real-time:

```bash
node QA/BAB-03-Teknik-Perancangan-Test-Case-Black-Box-White-Box/hands-on/m02/state_transition_coverage_sim.js
```

---
[⬅️ Module 01: Black-Box EP, BVA, & Decision Table](./Module-01-Black-Box-Equivalence-Partitioning-BVA-Decision-Table.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 03 ➡️](./BAB-03-Quiz-dan-Challenge.md)
---
