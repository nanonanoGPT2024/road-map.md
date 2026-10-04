---
[⬅️ Module 01: JS/TS Asynchronous Testing](./Module-01-JavaScript-TypeScript-untuk-QA-Async-Assertions.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 05 ➡️](./BAB-05-Quiz-dan-Challenge.md)
---

# Module 02: Arsitektur Framework Otomasi: Page Object Model (POM), Screenplay Pattern, & Test Data Factory

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Merancang arsitektur framework otomasi pengujian berskala enterprise dengan menerapkan prinsip **Separation of Concerns (SoC)** dan **Don't Repeat Yourself (DRY)**.
- Menguasai implementasi **Page Object Model (POM)**: pemisahan tegas antara definisi pemilih elemen (*Locators*), metode interaksi (*Page Actions*), dan skenario pengujian bisnis (*Test Cases*).
- Memahami alternatif arsitektur modern berorientasi peran: **Screenplay Pattern** (Actors, Abilities, Tasks, Questions, Interactions).
- Menerapkan **Factory Pattern & Builder Pattern** untuk memproduksi data uji dinamis (*Dynamic Test Data Generation*) yang unik dan terisolasi guna menghindari polusi database.
- Mengimplementasikan **Fluent Interface (Method Chaining)** pada kelas halaman web agar skrip pengujian terbaca seperti bahasa manusia yang alami (*DSL-like readability*).

---

## 2. Prerequisite
- Memahami dasar JavaScript/TypeScript modern dan eksekusi asinkron (`async`/`await`) dari Module 01.
- Pemahaman konsep Object-Oriented Programming (OOP): Class, Constructor, Methods, dan Inheritance.

---

## 3. Concept
Ketika seorang pemula menulis skrip otomasi pengujian, mereka cenderung menuliskan seluruh kode dalam satu file raksasa secara prosedural: membuka URL, mencari elemen dengan XPath/CSS selector panjang, mengetik teks, menekan tombol, dan melakukan assertion di baris yang sama.

Pendekatan ini akan runtuh seketika saat aplikasi berkembang. Jika tim frontend mengubah atribut `id="btn-login"` menjadi `id="btn-submit-v2"`, Anda harus mengedit 50 file test berbeda secara manual. 

Untuk mengatasi kerapuhan ini, industri rekayasa perangkat lunak mengadopsi pola arsitektur **Page Object Model (POM)**. POM memandang setiap halaman antarmuka web sebagai sebuah Class berorientasi objek. Seluruh detail teknis DOM (selector dan klik) disembunyikan di dalam Page Class, sementara file Test Case murni berfokus pada alur verifikasi bisnis tingkat tinggi.

---

## 4. Why?
Mengapa kita membutuhkan Page Object Model dan Design Patterns dalam otomasi?
1. **Titik Perubahan Tunggal (Single Point of Maintenance)**: Jika struktur HTML login berubah, Anda hanya perlu memperbarui 1 baris kode di dalam `LoginPage.js`. Seluruh 100 test case yang menggunakan login akan otomatis kembali bekerja normal.
2. **Keterbacaan Skenario Tingkat Tinggi (High Readability)**: Skrip pengujian berubah dari kode HTML mentah yang membingungkan menjadi rangkaian kalimat bisnis yang bersih:
   `await loginPage.loginWith("budi@mail.com", "Secret123");`
3. **Mencegah Duplikasi Kode (Zero Code Duplication)**: Alur umum (seperti proses autentikasi, navigasi menu, atau penambahan item ke cart) ditulis sekali dan digunakan kembali di seluruh test suite.

---

## 5. What?

### A. Tiga Lapisan Arsitektur Framework Otomasi Modern

```text
========================================================================================
                 TEST AUTOMATION ARCHITECTURE: 3-TIER LAYER
========================================================================================

 [ TIER 1: BUSINESS TEST CASES ]  --> checkout_test.spec.ts
   - Murni berisi logika bisnis & assertions (expect).
   - TIDAK BOLEH mengandung selector HTML (XPath/CSS) atau driver.click().
              |
              | Memanggil aksi halaman (Page Actions)
              v
 [ TIER 2: PAGE OBJECT MODEL (POM) ] --> LoginPage.ts, CartPage.ts
   - Menyimpan daftar Locators elemen antarmuka.
   - Menyediakan metode interaksi (fillForm, clickSubmit, getErrorMessage).
              |
              | Berinteraksi dengan browser engine
              v
 [ TIER 3: BROWSER / DRIVER DRIVER ] --> Playwright / Cypress / WebDriver
   - Eksekusi klik fisik, pengetikan keyboard, navigasi jaringan.
```

---

### B. Komponen Page Object Model (POM)
Setiap Page Class memiliki 3 tanggung jawab utama:
1. **Locators Repository**: Properti yang mendefinisikan cara menemukan elemen (misal: `#username`, `.btn-checkout`, `[data-testid="price"]`).
2. **Action Methods**: Fungsi yang mensimulasikan interaksi pengguna pada halaman tersebut (misal: `enterCredentials()`, `proceedToCheckout()`).
3. **State Inquiries**: Fungsi yang mengembalikan informasi dari halaman untuk diverifikasi oleh assertion (misal: `getAlertMessage()`, `isCartBadgeVisible()`).

---

### C. Test Data Factory (Factory Pattern)
Menghindari ketergantungan pada data kotor yang di-hardcode (*Hardcoded Fixtures*).
Alih-alih menggunakan email statis `"user@test.com"`, Test Data Factory memproduksi data acak valid secara dinamis untuk setiap iterasi pengujian:
```typescript
const user = UserFactory.create({ role: "ADMIN" });
// Menghasilkan: { id: "USR_9182", email: "user_178911@test.com", role: "ADMIN" }
```

---

## 6. How? Implementasi Page Object Model dengan Method Chaining (Fluent API)

### 1. Definisi Page Class: `LoginPage.js`
```javascript
class LoginPage {
  constructor(pageDriver) {
    this.driver = pageDriver;
    // 1. Locators
    this.emailInput = "#input-email";
    this.passwordInput = "#input-password";
    this.loginButton = "button[type='submit']";
    this.errorMessage = ".alert-error";
  }

  // 2. Action Methods dengan Fluent API (mengembalikan this untuk chaining)
  async navigate() {
    await this.driver.goto("/login");
    return this;
  }

  async enterEmail(email) {
    await this.driver.fill(this.emailInput, email);
    return this;
  }

  async enterPassword(password) {
    await this.driver.fill(this.passwordInput, password);
    return this;
  }

  async clickSubmit() {
    await this.driver.click(this.loginButton);
    return this;
  }

  // Helper Aksi Majemuk
  async loginWith(email, password) {
    await this.enterEmail(email);
    await this.enterPassword(password);
    await this.clickSubmit();
  }

  // 3. State Inquiry untuk Assertion
  async getErrorText() {
    return await this.driver.getText(this.errorMessage);
  }
}
```

### 2. Implementasi Test Case Bersih: `login.spec.js`
```javascript
describe("Fitur Autentikasi Pengguna", () => {
  test("Menampilkan pesan error saat password salah", async () => {
    const loginPage = new LoginPage(mockBrowser);

    // Fluent method chaining yang sangat mudah dibaca
    await loginPage.navigate();
    await loginPage.loginWith("tester@corp.id", "PasswordSalah");

    // Assertion murni di file test
    const errorText = await loginPage.getErrorText();
    expect(errorText).toBe("Kombinasi email atau password salah");
  });
});
```

---

## 7. Analogy
Bayangkan memesan taksi melalui aplikasi smartphone:
- **Pendekatan Tanpa POM**: Anda harus membongkar kap mesin mobil taksi, menghubungkan kabel starter aki secara manual, menginjak pedal gas dengan menarik kawat rem, dan membaca koordinat GPS menggunakan sinyal satelit mentah.
- **Pendekatan Dengan POM**: Anda duduk manis di kursi penumpang dan berinteraksi melalui antarmuka kemudi supir taksi (*Page Object*). Anda cukup berkata: *"Tolong antar saya ke Bandara Soekarno-Hatta"* (`taxi.driveTo("Bandara")`). Seluruh kerumitan teknis mesin dan navigasi diurus oleh supir.

---

## 8. Diagram

```text
========================================================================================
                 PAGE OBJECT MODEL & DATA FACTORY INTERACTION
========================================================================================

     [ Test Data Factory ]
               |
               | Hasilkan User Baru Dinamis
               v
  +--------------------------+
  |    TEST CASE SCRIPT      | <------- Berisi expect() assertions
  +--------------------------+
               |
               | Panggil Aksi Bisnis (loginWith, addToCart)
               v
  +--------------------------+
  |     PAGE OBJECT (POM)    | <------- Menyembunyikan Locators & DOM
  |   (e.g., CheckoutPage)   |
  +--------------------------+
               |
               | Eksekusi Browser Commands (click, type, wait)
               v
  +--------------------------+
  |    BROWSER AUTOMATION    | <------- Playwright / Puppeteer
  |       (DOM Engine)       |
  +--------------------------+
```

---

## 9. Simple Example: Test Data Factory Generator

```javascript
class UserDataFactory {
  static buildUser(overrides = {}) {
    const timestamp = Date.now();
    const randomSuffix = Math.floor(Math.random() * 1000);
    return {
      name: `User Test ${randomSuffix}`,
      email: `test_${timestamp}_${randomSuffix}@qa-sandbox.id`,
      password: "StrongPassword2026!",
      phone: `0812${Math.floor(10000000 + Math.random() * 90000000)}`,
      role: "CUSTOMER",
      ...overrides // Mengizinkan kustomisasi field tertentu
    };
  }
}

// Penggunaan di dalam test:
const regularUser = UserDataFactory.buildUser();
const adminUser = UserDataFactory.buildUser({ role: "SUPER_ADMIN" });
```

---

## 10. Practical Example: Pemisahan Tanggung Jawab (Separation of Concerns)

### Aturan Emas POM:
1. **Page Object TIDAK BOLEH mengandung fungsi `expect()` atau assertion framework!**
   - *Alasan*: Page Object merepresentasikan perilaku halaman antarmuka. Jika assertion ditaruh di dalam Page Object, method tersebut tidak dapat digunakan kembali pada skenario negatif di mana kita justru mengharapkan error.
2. **File Test TIDAK BOLEH memanggil selector DOM secara langsung!**
   - *Alasan*: Jika file test berisi string selector seperti `page.click('div.btn > span')`, isolasi enkapsulasi rusak dan manfaat POM hilang seketika.

---

## 11. Real World Example: Migrasi Redesign Halaman E-Commerce Skala Besar
Sebuah platform e-commerce dengan 400 skenario automated test melakukan *rebranding* visual total:
- Seluruh antarmuka web diubah dari framework Bootstrap lawas ke Tailwind CSS modern. Seluruh nama class CSS dan layout tombol berubah 100%.
- **Organisasi A (Tanpa POM)**: Membutuhkan waktu 3 minggu kerja lembur untuk 6 orang QA hanya untuk mencari dan mengganti selector satu per satu di dalam 400 file test script.
- **Organisasi B (Menerapkan POM Ketat)**: 1 orang QA menyelesaikan pembaruan dalam waktu 4 jam, cukup dengan memperbarui selector di dalam 12 file Page Object. Seluruh 400 skenario test langsung berjalan hijau kembali tanpa menyentuh file test satupun.

---

## 12. Trade-offs

| Aspek Arsitektur | Script Prosedural Kasar | Page Object Model (POM) | Screenplay Pattern |
|---|---|---|---|
| **Waktu Inisiasi Awal** | Sangat Cepat (Tulis langsung). | Sedang (Perlu membuat class page). | Tinggi (Banyak boilerplate class task & actor). |
| **Biaya Pemeliharaan** | Bencana (*Unmaintainable* saat test > 20). | Sangat Rendah (Perubahan terisolasi). | Sangat Rendah & Sangat Fleksibel. |
| **Keterbacaan Kode** | Buruk (Tercampur kode DOM & logika). | Sangat Bersih & Intuitif. | Menyerupai bahasa manusia alami (*BDD-like*). |
| **Kecocokan Tim** | Proyek prototipe 1 minggu. | Standar emas industri software. | Tim enterprise dengan ratusan SDET. |

---

## 13. When To Use
- Terapkan **Page Object Model** pada seluruh proyek otomasi pengujian Web UI dan Mobile UI (Playwright, Cypress, Selenium, Appium).
- Terapkan **Test Data Factory** untuk setiap pengujian yang membuat record baru di database guna menjamin isolasi data antar-eksekusi uji.
- Terapkan **Fluent API / Method Chaining** pada form pengisian bertingkat (*Multi-Step Wizards*).

## 14. When NOT To Use
- Jangan membuat Page Object untuk pengujian API murni tanpa UI. Gunakan *API Client Service Pattern*.
- Jangan memecah halaman kecil yang hanya memiliki 1 tombol statis menjadi 5 file class berbeda (*Overengineering*).

---

## 15. Common Mistakes

```text
1. MISTAKE: Memasukkan fungsi assertion (expect) ke dalam Page Object Class.
   WHY IT HAPPENS: QA ingin menghemat baris kode di file test.
   WHY IT IS BAD: Page object kehilangan fleksibilitas. Jika method "clickLogin()" otomatis mengecek dashboard muncul, method tersebut tidak bisa dipakai untuk skenario uji "Login Gagal".
   CORRECT APPROACH: Page Object hanya melakukan aksi dan mengembalikan data/status; assertion tetap ditulis di file test.

2. MISTAKE: Locator di-hardcode berulang kali di berbagai method dalam Page yang sama.
   WHY IT HAPPENS: Menulis 'this.page.click("#btn")' langsung tanpa membuat properti 'this.submitBtn = "#btn"'.
   WHY IT IS BAD: Jika selector tombol berubah, Anda harus mengedit 5 method berbeda di file yang sama.
   CORRECT APPROACH: Deklarasikan seluruh locator di constructor atau getters di bagian paling atas Page Class.
```

---

## 16. Best Practices

### Must Have
- Atribut locator terpusat di constructor Page Class.
- Larangan keras adanya pemilih CSS/XPath di file spesifikasi pengujian (`*.spec.ts`).
- Menggunakan data uji unik dinamis dari Data Factory (tidak memakai data statis yang sama berulang kali).

### Recommended
- Menggunakan penanda atribut pengujian khusus pada HTML: `[data-testid="login-button"]` alih-alih mengandalkan class CSS visual yang sering berubah saat styling diperbarui.
- Memisahkan komponen halaman yang sering muncul berulang (seperti *Navbar, Sidebar, Modal Dialog, Footer*) ke dalam **Component Objects** tersendiri yang diwarisi oleh Page Objects.

### Advanced
- Mengintegrasikan Builder Pattern pada Test Data Factory:
  `UserDataFactory.aUser().asAdmin().withVerifiedEmail().build();`

### Avoid / Overengineering
- Mewajibkan 10 lapisan inheritance class abstract yang berlebihan untuk aplikasi landing page sederhana.

---

## 17. Troubleshooting: Selector Flakiness & Dinamis ID
Jika pengujian gagal karena elemen ID berubah-ubah setiap reload (misal: `id="btn_1872a_submit"`):
1. **Penyebab**: Framework frontend modern (seperti React / Vue / Styled-Components) sering menghasilkan hash acak pada atribut ID atau class.
2. **Solusi Standar QA**:
   - Gunakan strategi selector berbasis teks atau role semantik: `page.getByRole("button", { name: "Simpan" })`.
   - Minta tim frontend menambahkan atribut stabil: `data-testid="save-btn"`.

---

## 18. Exercise
1. Tinjau potongan skrip test berikut dan refactor ke dalam struktur **Page Object Model (POM)** yang bersih:
   ```javascript
   test("Checkout barang", async () => {
     await driver.goto("https://shop.id/cart");
     await driver.fill("#voucher-code", "HEMAT50");
     await driver.click("#btn-apply");
     await driver.click("#btn-checkout");
     const text = await driver.getText(".order-status");
     expect(text).toBe("Pesanan Berhasil");
   });
   ```
   Pisahkan menjadi class `CartPage` dan file `checkout.spec.js`.
2. Buatlah sebuah class `ProductDataFactory` yang memproduksi data katalog produk acak (`id`, `sku`, `title`, `price`, `stock`).

---

## 19. Challenge
Rancang arsitektur framework pengujian Web E-Commerce lengkap:
- Buat Base Page class (`BasePage.js`) yang menginisialisasi driver dan method umum (`navigate`, `waitForUrl`).
- Buat 2 Page Object: `LoginPage` dan `InventoryPage` dengan method chaining.
- Buat `UserDataFactory` yang mendukung kustomisasi role pengguna.
- Tuliskan 2 test case: 1 skenario sukses (*Login valid dan verifikasi inventory*) dan 1 skenario gagal (*Login akun terkunci dan verifikasi banner alert*).

---

## 20. Summary
- Page Object Model (POM) adalah pola desain standar industri yang memisahkan definisi pemilih elemen dan metode interaksi dari skenario uji bisnis.
- POM meningkatkan keterbacaan kode, mengurangi duplikasi, dan menyederhanakan pemeliharaan saat antarmuka aplikasi berubah.
- Test Data Factory menjamin ketersediaan data uji dinamis yang terisolasi dan unik untuk setiap test run.
- File test bertugas memverifikasi ekspektasi bisnis (*assertions*), sementara Page Object bertugas mengeksekusi manipulasi antarmuka.

---

## Hands-on Practice: Simulator Engine Page Object Model & Data Factory
Jalankan script simulator yang mengimplementasikan arsitektur Page Object Model, Virtual DOM Driver, Data Factory dinamis, dan method chaining fluent interface secara nyata:

```bash
node QA/BAB-05-Fondasi-Otomasi-Pengujian-dan-Pemrograman/hands-on/m02/page_object_model_engine_sim.js
```

---
[⬅️ Module 01: JS/TS Asynchronous Testing](./Module-01-JavaScript-TypeScript-untuk-QA-Async-Assertions.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 05 ➡️](./BAB-05-Quiz-dan-Challenge.md)
---
