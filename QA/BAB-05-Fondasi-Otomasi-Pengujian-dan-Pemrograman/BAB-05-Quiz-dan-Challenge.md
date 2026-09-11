---
[⬅️ Module 02: Arsitektur POM & Design Patterns](./Module-02-Arsitektur-Framework-Otomasi-POM-dan-Design-Patterns.md) | [📋 Silabus Induk](../README.md) | [BAB 06: Otomasi Pengujian Web UI ➡️](../BAB-06-Otomasi-Pengujian-Web-UI-Modern/Module-01-Playwright-Web-UI-Automation-Locators-AutoWaiting.md)
---

# BAB 05: Quiz, Evaluasi, & Practical Challenge

## 1. Chapter Summary & Evaluasi Pemahaman
Pada BAB 05, Anda telah membangun keterampilan rekayasa perangkat lunak sejati untuk Quality Engineering:
1. **Logika Asinkron JavaScript/TypeScript**: Menguasai Event Loop, eksekusi Promises, dan penerapan mutlak `async`/`await` untuk menghentikan fenomena *Silent False Passing Tests*.
2. **Arsitektur Test Runner**: Memahami cara kerja blok `describe`, `test`, lifecycle hooks (`beforeAll`, `beforeEach`, `afterEach`, `afterAll`), serta custom assertion matchers.
3. **Isolasi State Pengujian**: Menjamin setiap test case mandiri dan tidak saling mencemari status data (*Shared Mutable State Anti-Pattern*).
4. **Page Object Model (POM)**: Memisahkan 3 lapisan: Skenario Bisnis (*Test File*), Antarmuka Halaman (*Page Class & Locators*), dan Mesin Peramban (*Driver Engine*).
5. **Pola Desain Otomasi**: Menggunakan Fluent Interface (Method Chaining) untuk keterbacaan tinggi dan Test Data Factory untuk menghasilkan fixture data unik dinamis.

---

## 2. Interactive Quiz

### Bagian A: Basic Questions (Konseptual Fundamental)
1. **Pertanyaan 1**: Mengapa melupakan kata kunci `await` pada pemanggilan Promise di dalam blok `test()` dapat menyebabkan tes lulus palsu (*False Pass*)?
2. **Pertanyaan 2**: Apa perbedaan mendasar antara lifecycle hook `beforeAll()` dan `beforeEach()`?
3. **Pertanyaan 3**: Apa itu pola desain **Page Object Model (POM)** dan masalah apa dalam pengujian antarmuka yang diselesaikannya?
4. **Pertanyaan 4**: Mengapa fungsi assertion seperti `expect().toBe()` **DILARANG KERAS** ditaruh di dalam method Page Object Class?
5. **Pertanyaan 5**: Apa keunggulan menggunakan **Test Data Factory** dibandingkan menggunakan data uji statis (*Hardcoded Fixtures*)?

### Bagian B: Intermediate Questions (Analisis & Desain)
6. **Pertanyaan 6**: Jelaskan mengapa penggunaan `await new Promise(r => setTimeout(r, 5000))` (Static Sleep) dianggap sebagai praktik terburuk (*code smell*) dalam otomasi pengujian modern, dan apa solusi penggantinya?
7. **Pertanyaan 7**: Perhatikan potongan kode berikut:
   ```typescript
   class UserProfilePage {
     async updateBio(newBio: string) {
       await this.page.fill("#bio", newBio);
       await this.page.click("#save");
       return this;
     }
   }
   ```
   Pola desain apa yang diterapkan dengan mengembalikan nilai `return this;` pada method di atas, dan bagaimana manfaatnya bagi penulisan test?
8. **Pertanyaan 8**: Bagaimana cara kerja strategi *Auto-Waiting* di balik layar dalam menangani elemen DOM yang sedang memuat data melalui jaringan?
9. **Pertanyaan 9**: Apa yang dimaksud dengan strategi selector berbasis *Semantic Roles* (seperti `getByRole("button", { name: "Submit" })`) dan mengapa pendekatan ini jauh lebih stabil dibandingkan selector XPath absolut (`/html/body/div[2]/form/button`)?
10. **Pertanyaan 10**: Apa perbedaan antara shallow assertion (`toBe()`) dan deep equality assertion (`toEqual()`) saat membandingkan dua objek data pengguna?

### Bagian C: Scenario-Based Questions (Problem Solving Dunia Nyata)
11. **Skenario 1**: Sebuah test suite berisi 50 skenario checkout e-commerce selalu sukses saat dijalankan secara berurutan (*sequential*), namun gagal 40% saat dijalankan secara paralel (*parallel execution*). Setelah diperiksa, seluruh skenario menggunakan akun pengguna yang sama: `demo_user@shop.id`. Berdasarkan prinsip *Test Isolation* dan *Data Factory*, jelaskan akar masalah dan cara memperbaikinya!
12. **Skenario 2**: Tim frontend memutuskan mengubah library styling dari Bootstrap ke Tailwind CSS. Seluruh class visual seperti `.btn-primary` berubah menjadi `.bg-blue-600 .hover:bg-blue-700`. Bagaimana arsitektur Page Object Model membuktikan efisiensinya dalam meminimalkan waktu perbaikan skrip pengujian?
13. **Skenario 3**: Dalam eksekusi pipeline CI/CD, ditemukan pesan error: `UnhandledPromiseRejection: Browser context closed before action completed`. Jelaskan langkah diagnosis teknis Anda untuk menemukan baris kode asinkron yang menjadi biang keladi!

---

## 3. Chapter Challenge: Perancangan Framework Otomasi Modular E-Commerce

### Deskripsi Skenario
Sebuah aplikasi web toko online bernama **"TokoSerba"** memiliki alur belanja utama:
1. Pengguna membuka halaman `/cart`.
2. Pengguna memasukkan kode promo kupon diskon.
3. Pengguna menekan tombol "Lanjut ke Pembayaran".
4. Di halaman checkout `/checkout`, pengguna memilih metode pengiriman (Reguler/Ekspres).
5. Pengguna menekan "Bayar Sekarang" dan sistem mengalihkan ke halaman `/receipt` dengan nomor pesanan unik.

### Tugas Anda (Deliverables):
1. **Rancang Page Object Class `CartPage`**:
   - Definisikan locator terpusat untuk input kupon, tombol apply kupon, tombol checkout, dan ringkasan subtotal.
   - Implementasikan method `applyCoupon(code)` dan `proceedToCheckout()` dengan dukungan method chaining (*Fluent API*).
2. **Rancang Page Object Class `CheckoutPage`**:
   - Definisikan locator untuk pilihan kurir dan tombol bayar.
   - Implementasikan method `selectShippingMethod(type)` dan `confirmOrder()`.
3. **Rancang `OrderDataFactory`**:
   - Buat fungsi pembuat data pesanan dinamis (`customerId`, `couponCode`, `shippingType`, `amount`).
4. **Tuliskan Spesifikasi Test Case (`e2e_checkout.spec.js`)**:
   - Tuliskan 1 skenario pengujian E2E lengkap yang bersih, mudah dibaca, dan bebas dari selector DOM, lengkap dengan verifikasi nomor invoice di halaman receipt.

---

## 4. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Mekanisme Event Loop dan pentingnya `async`/`await` pada pengujian browser.
- [ ] Struktur hierarki Test Runner dan siklus hidup hooks (`beforeEach`/`afterEach`).
- [ ] Prinsip isolasi data dan pencegahan Shared Mutable State.
- [ ] Arsitektur 3-Tier: Test Layer, Page Object Model Layer, dan Driver Layer.
- [ ] Aturan larangan menaruh assertion di dalam Page Object Class.
- [ ] Pemanfaatan Factory Pattern untuk produksi data uji dinamis unik.

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh nama method bawaan framework test tertentu (Jest vs Playwright vs Mocha).
- [ ] Seluruh sintaks CSS pseudo-selector tingkat rumit.

### Saya Harus Bisa Melakukan:
- [ ] Menulis test asinkron yang bebas dari fenomena false pass.
- [ ] Membuat class Page Object yang modular dan menerapkan method chaining.
- [ ] Menggunakan Test Data Factory untuk menghasilkan akun atau transaksi unik per test run.

---
[⬅️ Module 02: Arsitektur POM & Design Patterns](./Module-02-Arsitektur-Framework-Otomasi-POM-dan-Design-Patterns.md) | [📋 Silabus Induk](../README.md) | [BAB 06: Otomasi Pengujian Web UI ➡️](../BAB-06-Otomasi-Pengujian-Web-UI-Modern/Module-01-Playwright-Web-UI-Automation-Locators-AutoWaiting.md)
---
