---
[⬅️ Module 02: Advanced Web Testing](./Module-02-Advanced-Web-Testing-Iframes-ShadowDOM-NetworkMocks.md) | [📋 Silabus Induk](../README.md) | [BAB 07: Pengujian Database ➡️](../BAB-07-Pengujian-Database-dan-Test-Data-Management/Module-01-Database-Testing-ACID-SQL-Verification-Migrations.md)
---

# BAB 06: Quiz, Evaluasi, & Practical Challenge

## 1. Chapter Summary & Evaluasi Pemahaman
Pada BAB 06, Anda telah menguasai teknologi otomasi Web UI paling canggih di era modern:
1. **Arsitektur Playwright Modern**: Komunikasi dua arah via WebSocket langsung ke proses browser, multi-browser engine asli (Chromium, Firefox, WebKit/Safari), dan isolasi *Browser Contexts*.
2. **Auto-Waiting & 5 Actionability Checks**: Mengeliminasi uji rapuh (*flaky tests*) dengan memeriksa status *Attached, Visible, Stable, Free of Overlays,* dan *Enabled* secara otomatis sebelum aksi dieksekusi.
3. **Resilient User-Facing Locators**: Memprioritaskan `getByRole()`, `getByLabel()`, dan `getByTestId()` yang tahan terhadap perubahan estetika CSS dan layout HTML.
4. **Visual Regression Testing**: Menjaga integritas visual aplikasi dengan komparasi screenshot piksel terhadap baseline emas (*golden image*).
5. **Penanganan Elemen Tingkat Lanjut**: Mengendalikan formulir terisolasi di dalam *Nested Iframes* (`page.frameLocator()`) dan menembus enkapsulasi *Shadow DOM*.
6. **Optimasi & Ketahanan Jaringan**: Menerapkan *Storage State Injection* untuk login instan dalam 5 milidetik serta *Network Interception* (`page.route()`) untuk mensimulasikan kegagalan server dan mode offline.

---

## 2. Interactive Quiz

### Bagian A: Basic Questions (Konseptual Fundamental)
1. **Pertanyaan 1**: Apa perbedaan utama arsitektur komunikasi antara Selenium WebDriver (HTTP REST) dan Microsoft Playwright (WebSocket/CDP)?
2. **Pertanyaan 2**: Sebutkan 5 syarat aksi (*Actionability Checks*) yang diperiksa Playwright secara otomatis sebelum mengeksekusi perintah `.click()`!
3. **Pertanyaan 3**: Mengapa locator `page.getByRole("button", { name: "Beli" })` jauh lebih disarankan dibandingkan `page.locator("button.btn-primary.shadow-sm")`?
4. **Pertanyaan 4**: Mengapa perintah `page.locator("#submit-btn").click()` gagal menemukan elemen jika tombol tersebut berada di dalam tag `<iframe>`? Method apa yang wajib digunakan?
5. **Pertanyaan 5**: Apa keuntungan menggunakan fitur **Storage State Injection** (`storageState.json`) dibandingkan menjalankan alur login UI pada setiap file pengujian?

### Bagian B: Intermediate Questions (Analisis & Teknik Lanjutan)
6. **Pertanyaan 6**: Jelaskan apa yang dimaksud dengan **Web-First Assertions** di Playwright (contoh: `await expect(locator).toBeVisible()`) dan mengapa pendekatan ini mengeliminasi kebutuhan `sleep()` manual!
7. **Pertanyaan 7**: Bagaimana cara kerja **Visual Regression Testing** mendeteksi regresi antarmuka dan apa fungsi parameter toleransi `maxDiffPixelRatio`?
8. **Pertanyaan 8**: Seorang developer membuat Web Component dengan Shadow DOM mode `open`. Mengapa Playwright dapat mencari tombol di dalam Shadow DOM tersebut tanpa memerlukan script eksekusi JavaScript manual?
9. **Pertanyaan 9**: Jelaskan bagaimana Anda menggunakan `page.route()` untuk menguji tampilan antarmuka saat endpoint API produk mengembalikan status **HTTP 500 Internal Server Error**!
10. **Pertanyaan 10**: Apa yang dimaksud dengan fitur **Trace Viewer** di Playwright dan bagaimana alat ini membantu investigasi bug pada pipeline CI/CD yang berjalan secara *headless* tanpa monitor?

### Bagian C: Scenario-Based Questions (Problem Solving Dunia Nyata)
11. **Skenario 1**: Sebuah test otomasi checkout sering mengalami error acak: `TimeoutError: Element is not receiving click events, obscured by <div class="backdrop">`. Spinner loading hanya muncul selama 200 milidetik saat halaman menghitung ongkos kirim. Sebagai SDET, bagaimana Anda mengatasi masalah ini secara elegan tanpa menambahkan jeda waktu statis `sleep(3000)`?
12. **Skenario 2**: Anda diminta menguji fitur web chat real-time antara Pembeli dan Penjual menggunakan Playwright. Jelaskan bagaimana Anda memanfaatkan fitur **Browser Contexts** untuk menjalankan dua pengguna dengan sesi independen di satu mesin secara bersamaan dalam 1 test script!
13. **Skenario 3**: Sebuah aplikasi e-commerce memiliki integrasi pembayaran kartu kredit yang menampilkan form input nomor kartu di dalam Iframe Stripe pihak ketiga. Karena form tersebut memerlukan kartu kredit riil dengan OTP SMS, jelaskan strategi kombinasi antara `frameLocator()` dan `page.route()` untuk menguji alur pembayaran hingga selesai tanpa biaya tagihan perbankan!

---

## 3. Chapter Challenge: Perancangan Suite Otomasi E-Commerce Enterprise dengan Playwright

### Deskripsi Skenario
Sebuah marketplace fashion bernama **"TrendModa"** memiliki alur belanja kritis:
- Pengguna yang sudah login membuka halaman produk `/p/jaket-kulit`.
- Memilih ukuran "L" dan menekan tombol "Beli Sekarang".
- Modal pembayaran muncul dengan form kartu kredit di dalam Iframe: `<iframe id="xendit-card-frame">`.
- Setelah nomor kartu diisi, pengguna menekan "Bayar Tagihan" di parent page.
- Sistem memanggil API backend `/api/v1/charge`.

### Tugas Anda (Deliverables):
1. **Penerapan Storage State Injection**:
   Tuliskan kode konfigurasi setup global yang menyimpan sesi login pengguna ke dalam file `auth/buyerStorage.json` agar pengujian langsung dimulai dari status terautentikasi.
2. **Implementasi Page Object Model Playwright**:
   - Rancang class `ProductDetailPage` menggunakan Resilient Locators (`getByRole`, `getByLabel`).
   - Rancang class `PaymentModalPage` yang menggunakan `page.frameLocator("#xendit-card-frame")` untuk mengisi form nomor kartu dan CVV.
3. **Network Mocking & Error Simulation**:
   Tuliskan skrip uji yang mencegat rute `POST **/api/v1/charge` dan mensimulasikan penolakan bank: HTTP 402 Payment Required (`{ "error": "INSUFFICIENT_FUNDS" }`).
4. **Visual Assertion & Verification**:
   Tambahkan assertion bahwa banner merah bertuliskan *"Saldo kartu Anda tidak mencukupi"* muncul di layar dan lakukan visual snapshot check pada modal error.

---

## 4. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Keunggulan arsitektur Playwright WebSocket dibandingkan Selenium HTTP.
- [ ] 5 Actionability Checks pada mekanisme Auto-Waiting.
- [ ] Hirarki Resilient Locators berbasis aksesibilitas (`getByRole`, `getByLabel`, `getByTestId`).
- [ ] Cara kerja komparasi Visual Regression Testing berbasis pixel difference.
- [ ] Penanganan dokumen terisolasi Iframe dan Shadow DOM.
- [ ] Optimalisasi waktu test menggunakan Storage State Injection.
- [ ] Manipulasi rute jaringan menggunakan `page.route()`.

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh daftar konfigurasi Viewport ukuran ponsel di library Playwright (cukup menggunakan kamus `devices`).
- [ ] Sintaks internal protokol Chrome DevTools mentah.

### Saya Harus Bisa Melakukan:
- [ ] Menulis skrip otomasi web UI yang bebas dari sleep statis.
- [ ] Mengakses elemen di dalam nested iframe dengan `frameLocator()`.
- [ ] Memalsukan respon API backend untuk menguji skenario error 500 dan offline mode.

---
[⬅️ Module 02: Advanced Web Testing](./Module-02-Advanced-Web-Testing-Iframes-ShadowDOM-NetworkMocks.md) | [📋 Silabus Induk](../README.md) | [BAB 07: Pengujian Database ➡️](../BAB-07-Pengujian-Database-dan-Test-Data-Management/Module-01-Database-Testing-ACID-SQL-Verification-Migrations.md)
---
