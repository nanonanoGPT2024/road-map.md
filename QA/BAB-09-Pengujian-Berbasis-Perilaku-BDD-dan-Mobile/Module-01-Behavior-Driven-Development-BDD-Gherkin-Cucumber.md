---
[⬅️ BAB 08: Quiz & Challenge](../BAB-08-Pengujian-Performa-dan-Beban-Sistem/BAB-08-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Mobile Testing & AxeCore ➡️](./Module-02-Mobile-Testing-Appium-dan-Aksesibilitas-AxeCore.md)
---

# Module 01: Behavior-Driven Development (BDD), Sintaks Gherkin, & Living Documentation

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Memahami filosofi **Behavior-Driven Development (BDD)** yang dipelopori oleh Dan North sebagai jembatan komunikasi antara Product Owner (Bisnis), Software Engineer (Developer), dan QA Engineer (**The Three Amigos**).
- Menguasai penulisan spesifikasi menggunakan bahasa domain alami terstruktur **Gherkin**: kata kunci `Feature`, `Rule`, `Scenario`, `Given`, `When`, `Then`, `And`, `But`, `Background`, dan `Tags`.
- Menerapkan parameterisasi skenario skala besar menggunakan **Scenario Outline** dan **Examples Table** untuk menguji variasi data input secara ringkas.
- Memahami arsitektur pemetaan teknis dari teks Gherkin ke kode otomasi program (**Step Definitions & Regular Expression Matchers**).
- Membedakan secara tegas antara gaya penulisan **Declarative BDD (Berorientasi Nilai Bisnis)** versus anti-pattern berbahaya **Imperative BDD (Tercemar Detail Klik UI)**.
- Menjadikan file `.feature` sebagai **Living Documentation (Dokumentasi Hidup)** yang selalu sinkron 100% dengan status fungsionalitas sistem di produksi.

---

## 2. Prerequisite
- Memahami konsep dasar Test Case Design dan Page Object Model dari BAB 03 dan BAB 05.
- Kemampuan membaca dan menulis kalimat terstruktur dalam bahasa Inggris teknis atau bahasa Indonesia formal.

---

## 3. Concept
Dalam pengembangan perangkat lunak tradisional, sering terjadi jurang kesalahpahaman komunikasi (*Communication Gap*). Product Owner menulis dokumen kebutuhan bisnis (*PRD*) setebal puluhan halaman, Developer menerjemahkannya ke dalam arsitektur kode teknis yang rumit, dan QA menulis ratusan skrip pengujian yang bahasanya tidak dimengerti oleh Product Owner maupun Developer. Ketika fitur selesai, produk yang dihasilkan berbeda jauh dari apa yang sebenarnya diinginkan oleh bisnis.

**Behavior-Driven Development (BDD)** hadir untuk meruntuhkan sekat ini. BDD menggunakan bahasa alami yang dapat dibaca oleh manusia biasa namun dapat dieksekusi oleh komputer menggunakan sintaks standar yang disebut **Gherkin**. Melalui kolaborasi segitiga *The Three Amigos*, skenario pengujian disepakati bersama sebelum koding dimulai, berfungsi ganda sebagai **Spesifikasi Kebutuhan**, **Dokumentasi Sistem**, sekaligus **Skrip Pengujian Otomasi**.

---

## 4. Why?
Mengapa tim engineering modern mengadopsi BDD dan Gherkin?
1. **Bahasa Pemersatu (Ubiquitous Language)**: Product Owner, Developer, dan QA berbicara menggunakan terminologi bisnis yang sama persis tanpa distorsi jargon teknis.
2. **Dokumentasi yang Tidak Pernah Usang (Living Documentation)**: Dokumentasi Word atau PDF biasanya usang setelah rilis pertama. File fitur Gherkin dieksekusi di setiap pipeline CI/CD; jika dokumentasi tidak cocok dengan perilaku aplikasi, build akan langsung gagal (*Self-Validating Docs*).
3. **Mencegah Ambiguitas Kebutuhan Sejak Dini**: Pertemuan *Three Amigos* menemukan lubang kebutuhan bisnis sebelum developer menulis satu baris kode pun (*Shift-Left Requirement Analysis*).

---

## 5. What?

### A. Anatomi Sintaks Gherkin Standar

```gherkin
@regression @checkout
Feature: Perhitungan Diskon Promo Tanggal Kembar
  Sebagai pengguna setia e-commerce
  Saya ingin mendapatkan potongan harga menggunakan kupon promo
  Agar total belanja saya menjadi lebih hemat

  Background:
    Given pengguna telah login dengan akun "budi@testing.id"
    And saldo dompet pengguna adalah Rp 500.000

  Scenario: Kupon diskon 20% berhasil dipotong saat memenuhi syarat
    Given keranjang belanja berisi item senilai Rp 200.000
    When pengguna menerapkan kode voucher "HEMAT20"
    Then total tagihan belanja berkurang sebesar Rp 40.000
    And status voucher menampilkan pesan "Voucher Berhasil Digunakan"

  Scenario Outline: Validasi batas minimum transaksi berbagai jenis promo
    Given keranjang belanja berisi item senilai <subtotal>
    When pengguna menerapkan kode voucher "<kode_promo>"
    Then sistem menghasilkan status "<ekspektasi_status>"

    Examples:
      | subtotal | kode_promo | ekspektasi_status    |
      | 150000   | DISKON50   | DITERIMA             |
      | 40000    | DISKON50   | DIBAWAH_MINIMUM      |
      | 200000   | KODE_KADALUARSA | VOUCHER_EXPIRED |
```

---

### B. Kata Kunci Utama Gherkin (Gherkin Keywords)
- **`Given` (Prasyarat / Konteks Awal)**: Menjelaskan kondisi awal sistem sebelum aksi dilakukan (misal: status login, saldo akun, data di database).
- **`When` (Aksi / Kejadian)**: Tindakan spesifik yang dilakukan oleh pengguna atau sistem eksternal (misal: klik tombol bayar, submit formulir).
- **`Then` (Hasil / Ekspektasi)**: Konsekuensi atau keluaran yang diharapkan terjadi setelah aksi (misal: verifikasi saldo terpotong, email notifikasi terkirim).
- **`And` / `But`**: Penghubung logis untuk menyambungkan beberapa kondisi tanpa mengulang kata `Given/When/Then`.
- **`Background`**: Kumpulan langkah prasyarat yang otomatis dijalankan sebelum setiap skenario di dalam file feature yang sama.
- **`Scenario Outline` + `Examples`**: Tabel data berulang untuk menjalankan 1 alur pengujian dengan puluhan kombinasi data uji berbeda.

---

### C. Kolaborasi "The Three Amigos"

```text
========================================================================================
                          THE THREE AMIGOS BDD WORKFLOW
========================================================================================

    [ PRODUCT OWNER / PM ]          [ SOFTWARE DEVELOPER ]         [ QA ENGINEER / SDET ]
    (Membawa Masalah Bisnis)       (Membawa Arsitektur Teknis)   (Membawa Edge Cases & Sikap Kritis)
              \                                |                               /
               \                               |                              /
                +------------------------------+-----------------------------+
                                               |
                                               v
                                [ THREE AMIGOS SESSION ]
                                (Diskusi Spesifikasi & Contoh Riil)
                                               |
                                               v
                                [ Menulis File .feature Gherkin ]
                                               |
                         +---------------------+---------------------+
                         |                                           |
                         v                                           v
               [ Developer Koding ]                        [ QA Otomasi Step Definitions ]
           (TDD: Menulis Unit Test &                  (Menghubungkan Gherkin ke
            Implementasi Fitur Backend)                Page Object Model / API Client)
                         |                                           |
                         +---------------------+---------------------+
                                               |
                                               v
                                [ AUTOMATED BDD CI/CD TEST ]
                                (100% PASS = Fitur Siap Rilis!)
```

---

## 6. How? Menghindari Anti-Pattern Imperative BDD

Salah satu kesalahan paling fatal dalam industri adalah menulis Gherkin dengan gaya **Imperative (Perintah Langkah Klik Antarmuka)**.

### Perbandingan: Imperative (BURUK) vs Declarative (BAIK)

```gherkin
# GAYA BURUK: IMPERATIVE BDD (Sangat Rapuh, Penuh Sampah Teknis, Dibenci Product Owner)
Scenario: Login Gagal
  Given pengguna membuka browser di "https://app.id/login"
  When pengguna mengetik "budi@mail.com" pada input dengan id "#user-email"
  And pengguna mengetik "password123" pada input dengan id "#user-pass"
  And pengguna mengklik elemen tombol "button.btn-primary"
  Then pengguna harus melihat elemen ".alert-danger" dengan teks "Gagal"

# GAYA BAIK: DECLARATIVE BDD (Fokus Nilai Bisnis, Tahan Banting, Disukai Semua Pihak)
Scenario: Penolakan akses saat kredensial akun salah
  Given akun pengguna "budi@mail.com" terdaftar di sistem
  When pengguna mencoba masuk dengan kata sandi yang salah
  Then sistem menolak autentikasi dengan pesan "Kredensial Tidak Valid"
```

*Prinsip Emas*: Sembunyikan detail teknis (URL, ID elemen, klik tombol) di dalam file **Step Definitions** dan **Page Object Model**; pertahankan file `.feature` murni sebagai dokumen bisnis!

---

## 7. Analogy
Bayangkan memesan makanan di restoran mewah:
- **Declarative BDD (Gaya Benar)**: Anda berkata kepada pelayan: *"Saya memesan Nasi Goreng Spesial tanpa udang"* (`Given/When/Then` berfokus pada hasil yang diinginkan).
- **Imperative BDD (Gaya Salah)**: Anda masuk ke dapur dan mendikte koki: *"Nyalakan kompor gas tombol hitam, tuangkan 2 sendok makan minyak kelapa merek X, iris 3 siung bawang merah setebal 2 milimeter, aduk wajan 45 kali putaran..."*. Jika koki mengganti merek minyak kelapa, pesanan Anda gagal.

---

## 8. Diagram

```text
========================================================================================
                      BDD TEST AUTOMATION STACK ARCHITECTURE
========================================================================================

 [ TIER 1: GHERKIN FEATURE FILE ] --> checkout.feature
   "Given pengguna memiliki voucher diskon 50%..."
   (Bahasa Manusia Alami / Living Documentation)
              |
              | Diparsing oleh Cucumber / Playwright-BDD
              v
 [ TIER 2: STEP DEFINITIONS (Glue Code) ] --> checkout.steps.ts
   Given('pengguna memiliki voucher diskon {int}%', async (discount) => {
     await cartPage.applyVoucher(discount);
   });
              |
              | Memanggil aksi halaman
              v
 [ TIER 3: PAGE OBJECT MODEL ] --> CartPage.ts
   async applyVoucher(discount) { await this.page.fill(...); }
              |
              v
 [ TIER 4: BROWSER / API ENGINE ] --> Playwright / REST Client
```

---

## 9. Simple Example: Implementasi Step Definitions (Glue Code)

```javascript
// Step Definition: Menghubungkan teks Gherkin ke Page Object nyata
const { Given, When, Then } = require("@cucumber/cucumber");
const { expect } = require("@playwright/test");

Given("keranjang belanja berisi item senilai Rp {int}", async function (subtotal) {
  this.cartPage = new CartPage(this.page);
  await this.cartPage.seedCartWithAmount(subtotal);
});

When("pengguna menerapkan kode voucher {string}", async function (voucherCode) {
  await this.cartPage.applyVoucher(voucherCode);
});

Then("total tagihan belanja berkurang sebesar Rp {int}", async function (expectedDiscount) {
  const actualDiscount = await this.cartPage.getAppliedDiscount();
  expect(actualDiscount).toBe(expectedDiscount);
});
```

---

## 10. Practical Example: Menggunakan Tags untuk Seleksi Eksekusi Test (`@smoke`, `@wip`)

Gherkin Tags (`@tags`) memungkinkan QA memfilter skenario pengujian mana yang ingin dijalankan di berbagai tahapan CI/CD:

```gherkin
@smoke @p0
Scenario: Transaksi checkout normal pelanggan terverifikasi
  Given ...
  When ...
  Then ...

@regression @slow @flaky-quarantine
Scenario: Rekonsiliasi mutasi bank rekening internasional
  Given ...
  When ...
  Then ...
```

**Perintah Eksekusi Terminal**:
- Menjalankan hanya Smoke Test saat Pull Request:
  `npx cucumber-js --tags "@smoke and not @slow"`
- Menjalankan seluruh pengujian rilis mingguan:
  `npx cucumber-js --tags "@regression"`

---

## 11. Real World Example: Kegagalan Proyek Digital Banking Akibat BDD Palsu
Sebuah bank terkemuka memutuskan mengadopsi BDD untuk 2.000 skenario pengujian:
- **Kesalahan Fatal**: Tim QA tidak melibatkan Product Owner dan menulis Gherkin bergaya Imperative berisi ribuan langkah klik: `And I click on div#btn-x-3`.
- Ketika tim desain merilis antarmuka baru, 1.800 skenario Gherkin rusak total.
- Product Owner menolak membaca file fitur karena isinya penuh kode XPath yang tidak dapat dimengerti bisnis.
- Proyek BDD ditinggalkan setelah membuang anggaran jutaan dolar.
- **Pelajaran**: BDD adalah proses kolaborasi komunikasi (*People Process*), bukan sekadar alat otomasi (*Testing Tool*).

---

## 12. Trade-offs

| Aspek Pengujian | Skrip Otomasi Standar (Playwright Native) | Behavior-Driven Development (Cucumber/BDD) |
|---|---|---|
| **Keterlibatan Bisnis (PO/PM)** | Nol (Product Owner tidak membaca kode TS). | Sangat Tinggi (PO ikut menyetujui teks skenario Gherkin). |
| **Kecepatan Penulisan Skrip** | Sangat Cepat (Langsung koding di TypeScript). | Lebih Lambat (Perlu menulis Gherkin + Step Definitions). |
| **Lapisan Abstraksi (Overhead)**| Minimal (Hanya Test File & Page Objects). | Tambahan satu lapisan ekstra (*Gherkin Glue Code Layer*). |
| **Nilai Dokumentasi** | Rendah (Dokumentasi teknis untuk engineer saja). | Sangat Tinggi (*Living Documentation* untuk seluruh perusahaan). |

---

## 13. When To Use
- Terapkan **BDD** jika organisasi Anda memiliki budaya komunikasi erat antara Product Management, Developer, dan QA (*The Three Amigos*).
- Gunakan Gherkin untuk fitur dengan **logika bisnis yang kaya dan rumit** (misal: matriks persetujuan kredit, alur asuransi, kalkulasi perpajakan).
- Gunakan **Scenario Outline** untuk menguji aturan validasi bertingkat dengan tabel matriks data.

## 14. When NOT To Use
- Jangan memaksakan BDD jika tim QA bekerja sendirian dan Product Owner tidak pernah peduli membaca file `.feature` (Ini hanya membuang waktu membuat boilerplate ekstra).
- Jangan menggunakan BDD untuk pengujian performa beban, pengujian keamanan penetrasi, atau pengujian unit test algoritma internal.

---

## 15. Common Mistakes

```text
1. MISTAKE: Menulis detail implementasi teknis di dalam Gherkin (Imperative BDD).
   Contoh Buruk: "When I type 'admin' in input#username and click button.submit-login".
   WHY IT HAPPENS: QA menganggap Gherkin adalah perekam aksi mouse.
   WHY IT IS BAD: Menghancurkan keterbacaan bisnis dan membuat skenario sangat rapuh saat UI berubah.
   CORRECT APPROACH: Tulis secara deklaratif: "When user logs in with valid credentials".

2. MISTAKE: Satu Scenario menguji terlalu banyak alur sekaligus (Endless Megascenario).
   WHY IT HAPPENS: QA malas memecah skenario dan menggabungkan Login, Belanja, Refund, dan Ubah Profil dalam 1 Scenario dengan 40 baris "And".
   WHY IT IS BAD: Jika langkah ke-5 gagal, 35 langkah berikutnya tidak teruji dan akar masalah sulit dilacak.
   CORRECT APPROACH: 1 Scenario hanya memverifikasi 1 perilaku bisnis spesifik (*Single Behavior Focus*).
```

---

## 16. Best Practices

### Must Have
- Menulis skenario Gherkin dengan gaya **Declarative** yang berfokus pada hasil bisnis.
- Melakukan sesi *Three Amigos* sebelum proses koding sprint dimulai.

### Recommended
- Menggunakan parameter regex strongly-typed di Step Definitions (`{int}`, `{string}`, `{float}`) untuk memvalidasi masukan data secara ketat.
- Menjaga panjang skenario maksimal 5 hingga 8 langkah baris instruksi.

### Advanced
- Mengintegrasikan hasil eksekusi Gherkin dengan tool pelaporan Living Documentation otomatis (seperti *Allure Report* atau *Cucumber Living Docs Generator*) yang dapat diakses publik oleh seluruh stakeholder non-teknis.

### Avoid / Overengineering
- Membuat step definition baru untuk setiap sinonim kalimat kecil. Manfaatkan *Reusability* langkah yang sudah ada.

---

## 17. Troubleshooting: Gagal Menemukan Step Definition (Undefined Step Error)
Jika runner BDD menampilkan:
`Undefined. Implement with the following snippet: Given('pengguna login', ...)`
1. **Penyebab**: Teks di file `.feature` tidak cocok persis (misal ada perbedaan spasi, huruf besar-kecil, atau parameter tipe) dengan regex di file step definitions.
2. **Solusi**:
   - Salin snippet yang disarankan runner ke dalam file step definitions.
   - Gunakan parameterisasi generik `{string}` untuk menangani teks dinamis.

---

## 18. Exercise
1. Tinjau skenario Gherkin imperatif berikut dan ubah menjadi skenario deklaratif yang elegan:
   ```gherkin
   Scenario: Tambah Produk
     Given pengguna membuka web "https://toko.id"
     And pengguna klik "a#catalog-link"
     When pengguna klik tombol "button.add-to-cart[data-id='101']"
     Then pengguna melihat badge "span.badge-count" berisi angka "1"
   ```
2. Tuliskan sebuah `Scenario Outline` Gherkin dengan tabel `Examples` untuk menguji kalkulasi tarif parkir kendaraan bermotor:
   - Motor: Rp 2.000/jam
   - Mobil: Rp 5.000/jam
   - Truk: Rp 10.000/jam
   Uji untuk durasi 1 jam, 3 jam, dan denda tiket hilang (flat Rp 50.000).

---

## 19. Challenge
Rancang sebuah dokumen **Living Documentation BDD Suite** untuk fitur penarikan dana mesin ATM:
1. Tuliskan file `atm_withdrawal.feature` lengkap dengan `Feature`, `Background` (Status kartu ATM valid dan saldo awal), serta 3 `Scenario`:
   - Penarikan sukses dengan saldo mencukupi.
   - Penolakan penarikan saat saldo tidak mencukupi.
   - Penolakan penarikan saat melebihi batas limit harian penarikan tunai (Scenario Outline).
2. Tuliskan implementasi pseudo-code Step Definitions dalam JavaScript yang memanggil method kelas `AtmSessionPage`.

---

## 20. Summary
- BDD menjembatani komunikasi antara bisnis, developer, dan QA melalui kolaborasi The Three Amigos.
- Bahasa Gherkin mendefinisikan perilaku sistem dalam format terstruktur `Given-When-Then` yang berfungsi ganda sebagai spesifikasi dan skrip otomasi.
- Gaya penulisan Declarative berfokus pada intensi bisnis, menjamin dokumen tahan lama dan tidak rapuh saat antarmuka berubah.
- Living Documentation menjamin bahwa dokumentasi sistem selalu hidup, terverifikasi, dan sinkron 100% dengan status aplikasi terkini.

---

## Hands-on Practice: Simulator Parser Gherkin & Runner Step Definitions Mandiri
Jalankan script simulator yang mem-parsing file teks sintaks Gherkin, mencocokkan regex kata kunci Given-When-Then, mengeksekusi parameter Scenario Outline, dan menghasilkan Living Report:

```bash
node QA/BAB-09-Pengujian-Berbasis-Perilaku-BDD-dan-Mobile/hands-on/m01/gherkin_bdd_parser_sim.js
```

---
[⬅️ BAB 08: Quiz & Challenge](../BAB-08-Pengujian-Performa-dan-Beban-Sistem/BAB-08-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Mobile Testing & AxeCore ➡️](./Module-02-Mobile-Testing-Appium-dan-Aksesibilitas-AxeCore.md)
---
