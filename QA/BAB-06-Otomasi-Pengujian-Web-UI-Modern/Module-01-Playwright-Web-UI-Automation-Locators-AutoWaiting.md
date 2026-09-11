---
[⬅️ BAB 05: Quiz & Challenge](../BAB-05-Fondasi-Otomasi-Pengujian-dan-Pemrograman/BAB-05-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Advanced Web Testing ➡️](./Module-02-Advanced-Web-Testing-Iframes-ShadowDOM-NetworkMocks.md)
---

# Module 01: Otomasi Web UI Modern: Arsitektur Playwright, Auto-Waiting, Resilient Locators, & Visual Regression

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Memahami evolusi dan keunggulan arsitektur otomasi browser modern **Playwright** berbasis protokol koneksi persisten tunggal (*WebSocket / Chrome DevTools Protocol*) dibandingkan arsitektur lawas HTTP JSON Wire Protocol (*Selenium WebDriver*).
- Menguasai konsep **Browser Contexts** untuk menjalankan pengujian multi-sesi yang sepenuhnya terisolasi dan instan (*sub-millisecond incognito contexts*) tanpa overhead membuka ulang instance browser fisik.
- Menguasai mekanisme **Auto-Waiting & Actionability Checks** bawaan Playwright (memeriksa elemen: *Visible, Stable, Receives Events, Enabled, Editable*) untuk mengeliminasi flakiness pengujian antarmuka.
- Menerapkan strategi **Resilient Locators** berbasis aksesibilitas dan perilaku pengguna: `getByRole()`, `getByLabel()`, `getByText()`, dan `getByTestId()` yang tahan terhadap perombakan desain visual (*anti-breakage*).
- Melakukan **Visual Regression Testing** (komparasi pixel-by-pixel snapshot) untuk mendeteksi deviasi tata letak UI yang tidak disengaja.

---

## 2. Prerequisite
- Memahami konsep dasar JavaScript/TypeScript asinkron (`async`/`await`) dan Page Object Model dari BAB 05.
- Pemahaman struktur DOM HTML dan atribut semantik web.

---

## 3. Concept
Selama hampir dua dekade, pengujian web UI didominasi oleh Selenium WebDriver yang mengendalikan browser melalui permintaan HTTP REST bolak-balik untuk setiap aksi klik. Pola ini lambat, sering mengalami putus koneksi, dan memaksa tester menulis kode tunggu manual yang rentan gagal (*flaky*).

Generasi baru pengujian web dipimpin oleh **Playwright (oleh Microsoft)** dan **Cypress**. Playwright berkomunikasi langsung dengan proses inti peramban (Chromium, Firefox, dan WebKit/Safari) melalui koneksi WebSocket persisten berkecepatan tinggi. Playwright menghadirkan paradigma **Auto-Waiting**: setiap kali Anda menginstruksikan `page.click('button')`, Playwright secara cerdas memeriksa apakah tombol tersebut sudah terlihat, animasinya sudah berhenti, tidak tertutup elemen lain, dan siap menerima klik fisik, sebelum aksi dieksekusi.

---

## 4. Why?
Mengapa Playwright menjadi standar de facto pengujian web UI saat ini?
1. **Zero Flakiness berkat Auto-Waiting**: Mengakhiri era `sleep(5000)` dan loop polling manual; Playwright otomatis menunggu hingga elemen memenuhi 5 syarat aksi (*Actionability Checks*).
2. **Dukungan Multi-Browser Sejati (Chromium, Firefox, WebKit)**: Menguji rendering mesin Safari asli (WebKit) di sistem operasi Linux dan Windows tanpa perlu perangkat keras Mac fisik.
3. **Isolasi Sesi Super Cepat (Browser Contexts)**: Membuka browser fisik satu kali, lalu membuat tab-tab profil baru (*incognito context*) dalam hitungan milidetik. Anda dapat mensimulasikan interaksi multi-pengguna secara bersamaan (misal: Skenario Chat antara Pembeli dan Penjual di dua tab terpisah).

---

## 5. What?

### A. Perbandingan Arsitektur: Selenium vs Playwright

| Dimensi | Selenium WebDriver (Legacy) | Microsoft Playwright (Modern) |
|---|---|---|
| **Protokol Komunikasi** | HTTP REST Request bolak-balik per perintah (*JSON Wire Protocol*). | WebSocket Dua Arah Persisten (*Chrome DevTools Protocol*). |
| **Kecepatan Eksekusi** | Lambat (Tinggi overhead latensi HTTP). | Sangat Cepat (Komunikasi real-time tingkat proses). |
| **Menunggu Elemen** | Manual (`Thread.sleep` atau `WebDriverWait` manual). | **Auto-Waiting Otomatis** sebelum setiap aksi interaksi. |
| **Isolasi Antar-Test** | Membuka dan menutup jendela browser fisik (berat & lambat). | **Browser Contexts** terisolasi instan (seperti tab incognito). |
| **Multi-Tab & Iframes** | Sangat rumit berpindah window handles. | Dukungan kelas satu (*First-class citizen*) untuk multi-page/tab. |

---

### B. 5 Syarat Aksi (Playwright Actionability Checks)
Sebelum Playwright mengeksekusi aksi seperti `.click()` atau `.fill()`, sistem secara otomatis memvalidasi kondisi berikut:

```text
========================================================================================
                     PLAYWRIGHT ACTIONABILITY CHECKS FOR .click()
========================================================================================

 1. ATTACHED        --> Apakah elemen sudah ada di dalam dokumen DOM?
          | (YA)
          v
 2. VISIBLE         --> Apakah elemen memiliki ukuran fisik dan tidak display:none / hidden?
          | (YA)
          v
 3. STABLE          --> Apakah animasi CSS / posisi elemen sudah berhenti bergerak?
          | (YA)
          v
 4. RECEIVES EVENTS --> Apakah titik tengah elemen bebas dan tidak tertutup popup modal lain?
          | (YA)
          v
 5. ENABLED         --> Apakah elemen tombol tidak berstatus "disabled"?
          | (YA)
          v
 ===> EKSEKUSI KLIK FISIK BERHASIL TANPA FLAKINESS! <===
```

---

### C. Hierarki Resilient Locators (Panduan Prioritas Locator)
Playwright mendorong pengujian yang berfokus pada pengalaman pengguna riil melalui **User-Facing Locators**:

1. **`page.getByRole(role, { name })` (PRIORITAS TERTINGGI)**:
   Mencari elemen berdasarkan peran semantik aksesibilitas:
   `page.getByRole("button", { name: "Bayar Sekarang" })`
2. **`page.getByLabel(text)`**:
   Mencari input berdasarkan label formulir pendamping:
   `page.getByLabel("Alamat Email")`
3. **`page.getByText(text)`**:
   Mencari teks informasi non-interaktif:
   `page.getByText("Pesanan Berhasil Dibuat")`
4. **`page.getByTestId(id)`**:
   Digunakan jika elemen sulit diidentifikasi secara semantik:
   `page.getByTestId("cart-badge-count")`
5. **CSS / XPath (HINDARI JIKA MEMUNGKINKAN)**:
   Sangat rapuh terhadap perubahan class atau struktur HTML (`div > p:nth-child(3)`).

---

## 6. How? Menulis Script Pengujian Playwright

```typescript
import { test, expect } from "@playwright/test";

test.describe("Alur Pembelian E-Commerce", () => {
  test("Pengguna berhasil menambahkan barang ke keranjang belanja", async ({ page }) => {
    // 1. Navigasi
    await page.goto("https://shop.testing.id");

    // 2. Resilient Locators & Auto-Waiting
    await page.getByPlaceholder("Cari produk impian...").fill("Keyboard Wireless");
    await page.getByRole("button", { name: "Cari" }).click();

    // 3. Interaksi dengan kartu produk
    const productCard = page.locator(".product-card").filter({ hasText: "Keyboard Wireless RGB" });
    await productCard.getByRole("button", { name: "Tambah ke Keranjang" }).click();

    // 4. Assertions Cerdas (Web-First Assertions)
    // Playwright otomatis menunggu hingga kondisi assertion terpenuhi (auto-retrying assertion)
    const cartBadge = page.getByTestId("cart-counter");
    await expect(cartBadge).toHaveText("1");
    await expect(page.getByText("Produk berhasil ditambahkan")).toBeVisible();
  });
});
```

---

## 7. Analogy
Bayangkan mengemudikan mobil otonom berteknologi tinggi:
- **Selenium (Legacy)**: Anda harus berteriak setiap detik: *"Apakah lampu hijau sudah menyala? Apakah mobil di depan sudah bergerak? Boleh saya jalan sekarang?"*. Jika salah timing 1 detik saja, mobil menabrak.
- **Playwright (Modern)**: Mobil dilengkapi sensor radar dan kamera cerdas (*Auto-Waiting & Actionability Checks*). Anda cukup menekan tombol *"Tancap Gas"* (`click`). Mobil otomatis menunggu lampu lalu lintas hijau, memastikan penyeberang jalan sudah lewat, dan meluncur mulus saat jalanan benar-benar aman.

---

## 8. Diagram

```text
========================================================================================
                      BROWSER CONTEXTS & ISOLATION IN PLAYWRIGHT
========================================================================================

                 [ BROWSER INSTANCE (Chromium Single Process) ]
                                      |
         +----------------------------+----------------------------+
         |                                                         |
  [ Browser Context 1 ]                                     [ Browser Context 2 ]
  - User: Pembeli (Buyer)                                   - User: Penjual (Merchant)
  - Cookies: Session A                                      - Cookies: Session B
  - Storage: Cart ID #1001                                  - Storage: Dashboard Seller
         |                                                         |
         v                                                         v
   [ Page / Tab 1 ]                                          [ Page / Tab 2 ]
 (Buka Halaman Checkout)                                    (Buka Notifikasi Pesanan Masuk)
```

---

## 9. Simple Example: Visual Regression Testing (Snapshot Matching)

Visual Regression Testing memverifikasi bahwa tidak ada elemen antarmuka yang bergeser atau salah warna secara visual:

```typescript
test("Halaman beranda bebas dari regresi visual tata letak", async ({ page }) => {
  await page.goto("https://shop.testing.id");

  // Playwright mengambil screenshot dan membandingkannya dengan baseline emas (golden image)
  // Toleransi perbedaan piksel (maxDiffPixelRatio) dapat disesuaikan
  await expect(page).toHaveScreenshot("homepage-golden-baseline.png", {
    maxDiffPixelRatio: 0.02 // Maksimal 2% perbedaan toleransi font anti-aliasing
  });
});
```

Jika seorang developer secara tidak sengaja mengubah margin CSS tombol sehingga tombol turun 5 piksel, test ini akan GAGAL seketika dan menghasilkan gambar komparasi: **Actual vs Expected vs Diff (highlight merah)**.

---

## 10. Practical Example: Multi-User Collaborative Testing (Simulasi Transaksi 2 Pengguna)

Salah satu keunggulan terbesar Browser Contexts Playwright adalah kemampuan menguji interaksi antar-dua pengguna di jendela terpisah dalam satu skrip tes yang sama:

```typescript
test("Skenario Kolaborasi: Pembeli checkout, Penjual menerima notifikasi", async ({ browser }) => {
  // Buat sesi Buyer
  const buyerContext = await browser.newContext();
  const buyerPage = await buyerContext.newPage();

  // Buat sesi Merchant terisolasi
  const sellerContext = await browser.newContext();
  const sellerPage = await sellerContext.newPage();

  // 1. Buyer melakukan checkout
  await buyerPage.goto("https://shop.id/order/101");
  await buyerPage.getByRole("button", { name: "Bayar" }).click();

  // 2. Seller memverifikasi pesanan masuk secara real-time via WebSocket
  await sellerPage.goto("https://shop.id/merchant/orders");
  await expect(sellerPage.getByText("Pesanan Baru #101")).toBeVisible();

  // Bersihkan resource
  await buyerContext.close();
  await sellerContext.close();
});
```

---

## 11. Real World Example: Kegagalan Rilis Maskapai Penerbangan Akibat Selector CSS Rapuh
Sebuah maskapai penerbangan menggunakan selector class CSS:
`page.click('.btn-blue-rounded-lg')`
- Tim UI melakukan update tema musiman menyambut perayaan akhir tahun dan mengubah warna tema menjadi merah: `.btn-red-rounded-lg`.
- Seluruh 1.200 skenario automated test gagal (*Broken Build*). Tim QA harus menghabiskan 4 hari penuh kerja lembur untuk memperbarui selector.
- **Pelajaran**: Jika mereka menggunakan Resilient Locator `page.getByRole("button", { name: "Pesan Penerbangan" })`, tes tidak akan terpengaruh sama sekali oleh perubahan warna atau nama class CSS!

---

## 12. Trade-offs

| Fitur | Playwright | Cypress | Selenium WebDriver |
|---|---|---|---|
| **Dukungan Multi-Tab / Window** | Penuh (Sangat mudah). | Terbatas (Menolak multi-tab di dalam 1 test). | Penuh (Namun lambat & rumit). |
| **Bahasa Pemrograman** | TypeScript, JavaScript, Python, Java, C#. | JavaScript / TypeScript saja. | Seluruh bahasa utama. |
| **Dukungan Safari / WebKit** | Asli di Linux/Windows/Mac. | Menggunakan browser browser emulator. | Memerlukan Mac fisik untuk Safari asli. |
| **Kecepatan Eksekusi** | Paling Cepat. | Cepat. | Paling Lambat. |

---

## 13. When To Use
- Gunakan **Playwright** untuk proyek web modern yang membutuhkan pengujian lintas-browser sejati (Chromium, Firefox, Safari WebKit).
- Gunakan **Resilient Locators (`getByRole`)** pada 90% interaksi elemen halaman.
- Gunakan **Browser Contexts** saat menguji alur multi-aktor (User vs Admin, Pembeli vs Penjual).

## 14. When NOT To Use
- Jangan gunakan pengujian Web UI untuk memverifikasi 100 kombinasi perhitungan diskon atau validasi regex nomor KTP. Gunakan Unit Testing / API Testing di level bawah piramida.
- Jangan menggunakan Visual Regression Testing pada komponen yang memiliki konten dinamis acak (seperti banner jam digital atau ticker saham live) tanpa melakukan *masking* elemen terlebih dahulu.

---

## 15. Common Mistakes

```text
1. MISTAKE: Memakai selector XPath absolut: "/html/body/div[1]/div[2]/main/div/button".
   WHY IT HAPPENS: QA menggunakan fitur "Copy XPath" bawaan Chrome DevTools.
   WHY IT IS BAD: Satu penambahan tag <div> pembungkus oleh developer akan menghancurkan test secara permanen.
   CORRECT APPROACH: Gunakan getByRole() atau data-testid.

2. MISTAKE: Menulis assertion sinkron "expect(await page.isVisible('.modal')).toBe(true)".
   WHY IT HAPPENS: Terbiasa dengan assertion unit test tradisional.
   WHY IT IS BAD: Assertion ini TIDAK menunggu (No Auto-retry)! Jika modal butuh 50ms untuk muncul, test langsung gagal seketika.
   CORRECT APPROACH: Gunakan Web-First Assertion: "await expect(page.locator('.modal')).toBeVisible();".
```

---

## 16. Best Practices

### Must Have
- Selalu gunakan **Web-First Assertions** (`await expect(locator).toBeVisible()`) agar Playwright melakukan auto-retrying hingga timeout tercapai.
- Memprioritaskan **User-Facing Locators** (`getByRole`, `getByLabel`) yang mencerminkan cara manusia berinteraksi dengan layar.

### Recommended
- Mengaktifkan fitur **Trace Viewer** di Playwright (`trace: "on-first-retry"`). Fitur ini merekam rekaman video DOM, network request, dan console logs untuk debugging instan jika test gagal di CI/CD.
- Menggunakan `test.step()` untuk membagi skenario panjang menjadi langkah-langkah yang jelas pada laporan eksekusi.

### Advanced
- Melakukan *Network Mocking* (`page.route()`) untuk mengisolasi pengujian UI dari downtime server backend.

### Avoid / Overengineering
- Melakukan screenshot visual testing untuk setiap tombol di seluruh website. Batasi visual testing hanya pada halaman kunci (*Design System components / Landing Page*).

---

## 17. Troubleshooting: Elemen Tertutup Overlay ("Element is not clickable at point...")
Jika Playwright melempar error:
`TimeoutError: element is not receiving click events, obscured by <div class="loading-backdrop">`
1. **Penyebab**: Elemen sebenarnya sudah ada di DOM, tetapi sedang tertutup animasi spinner loading semi-transparan.
2. **Solusi Elegan**:
   - Jangan pasang `sleep(3000)`.
   - Tunggu hingga spinner loading hilang:
     `await expect(page.locator('.loading-backdrop')).toBeHidden();`
   - Baru eksekusi klik tombol utama.

---

## 18. Exercise
1. Tinjau potongan kode tombol HTML berikut:
   ```html
   <button type="submit" aria-label="Konfirmasi Pemesanan Tiket" class="btn-primary py-2 px-4">
     <svg class="icon-cart"></svg>
     <span>Checkout</span>
   </button>
   ```
   Tuliskan kode Playwright yang paling tahan banting (*most resilient locator*) untuk mengklik tombol tersebut.
2. Jelaskan perbedaan cara kerja antara `expect(await locator.innerText()).toBe("Sukses")` dan `await expect(locator).toHaveText("Sukses")`. Mengapa yang kedua jauh lebih stabil?

---

## 19. Challenge
Rancang sebuah **Playwright Test Suite Otomasi** untuk skenario transfer dana perbankan online:
1. Skenario Happy Path: Login menggunakan `getByLabel()`, input rekening tujuan, pilih nominal, tekan tombol transfer menggunakan `getByRole()`, dan verifikasi receipt dialog.
2. Terapkan Web-First Assertions untuk memastikan tombol "Konfirmasi" hanya diklik setelah status loading spinner hilang.
3. Tambahkan 1 langkah Visual Snapshot comparison untuk memastikan tampilan struk transfer tidak mengalami regresi tata letak.

---

## 20. Summary
- Playwright merevolusi otomasi web melalui arsitektur WebSocket langsung, dukungan multi-browser sejati, dan kecepatan eksekusi tinggi.
- Mekanisme Auto-Waiting dan 5 Actionability Checks mengeliminasi tes rapuh (*flaky tests*) tanpa memerlukan jeda waktu tidur statis.
- Resilient Locators (`getByRole`, `getByLabel`, `getByTestId`) menjamin skrip uji tetap stabil meskipun class CSS dan tata letak halaman berubah.
- Browser Contexts memungkinkan isolasi sesi berkecepatan tinggi dan simulasi alur interaksi multi-pengguna secara bersamaan.

---

## Hands-on Practice: Simulator Engine Headless Playwright & Auto-Waiting Checks
Jalankan script simulator yang mereplikasi protokol CDP Playwright, memvalidasi 5 actionability checks elemen DOM, mengeksekusi resilient locators, dan mendeteksi regresi visual berbasis pixel diff:

```bash
node QA/BAB-06-Otomasi-Pengujian-Web-UI-Modern/hands-on/m01/playwright_headless_runner_sim.js
```

---
[⬅️ BAB 05: Quiz & Challenge](../BAB-05-Fondasi-Otomasi-Pengujian-dan-Pemrograman/BAB-05-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Advanced Web Testing ➡️](./Module-02-Advanced-Web-Testing-Iframes-ShadowDOM-NetworkMocks.md)
---
