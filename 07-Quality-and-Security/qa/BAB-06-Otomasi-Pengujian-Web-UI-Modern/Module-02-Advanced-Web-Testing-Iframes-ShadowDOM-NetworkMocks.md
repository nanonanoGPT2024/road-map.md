---
[⬅️ Module 01: Playwright Auto-Waiting & Locators](./Module-01-Playwright-Web-UI-Automation-Locators-AutoWaiting.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 06 ➡️](./BAB-06-Quiz-dan-Challenge.md)
---

# Module 02: Pengujian Web Lanjutan: Iframes, Shadow DOM, Storage Injection, & Network Mocking

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Mengatasi tantangan isolasi dokumen peramban paling rumit: mengontrol dan berinteraksi dengan elemen di dalam **Nested Iframes** menggunakan `page.frameLocator()`.
- Menembus batas enkapsulasi Web Components (**Shadow DOM Piercing**) secara transparan tanpa skrip injeksi JavaScript buatan.
- Menerapkan teknik **Instant Authentication Bypass (Storage State Injection)**: menyuntikkan Cookies, JWT Token, dan LocalStorage secara langsung ke dalam browser context guna menghemat 80% waktu eksekusi test (menghindari proses login manual via UI berulang kali).
- Menguasai teknik **Network Interception & API Mocking** (`page.route()`): memanipulasi, memblokir, atau memalsukan (*stubbing*) respon HTTP API dari browser untuk menguji kondisi darurat (*Error 500, Offline Mode, Throttling*).
- Melakukan emulasi lingkungan perangkat (*Device Emulation*): mengubah koordinat GPS (*Geolocation*), zona waktu (*Timezone*), orientasi layar, dan dimensi Viewport mobile/desktop secara presisi.

---

## 2. Prerequisite
- Memahami konsep dasar Playwright, Resilient Locators, dan Page Object Model dari Module 01.
- Pemahaman umum tentang cara kerja Cookies, LocalStorage, dan arsitektur Web Components HTML5.

---

## 3. Concept
Dalam aplikasi web enterprise modern, antarmuka jarang berdiri sebagai halaman HTML monolitik yang sederhana. Form pembayaran kartu kredit sering disematkan di dalam dokumen terisolasi yang disebut **Iframe** demi keamanan kepatuhan PCI-DSS. Komponen UI modern (seperti date-picker atau video player) sering dienkapsulasi menggunakan **Shadow DOM** agar CSS global tidak bocor ke dalam komponen.

Selain itu, menjalankan 100 skenario pengujian di mana setiap skenario harus mengetik email dan password di halaman login adalah pemborosan waktu yang sangat masif. Melalui teknik lanjutan **Storage Injection** dan **Network Interception**, QA dapat menginjeksi token sesi secara instan di level browser context dan memotong ketergantungan pada backend nyata melalui manipulasi rute jaringan (*network stubbing*).

---

## 4. Why?
Mengapa teknik pengujian web lanjutan ini sangat krusial?
1. **Efisiensi Waktu Eksekusi Eksponensial**: Mengetik email dan password via UI membutuhkan waktu 4–6 detik per test. Menyuntikkan `storageState.json` langsung ke browser context hanya membutuhkan waktu 5 milidetik! Untuk 500 test case, Anda menghemat lebih dari 40 menit waktu pipeline CI/CD.
2. **Menguji Skenario Bencana yang Mustahil di Lingkungan Nyata**: Bagaimana Anda menguji tampilan UI saat server payment gateway melempar error 503 atau internet pengguna tiba-tiba offline? Melalui `page.route()`, Anda dapat memalsukan respon jaringan seketika tanpa perlu mematikan server backend staging.
3. **Menembus Proteksi Iframe Payment Gateway**: Gateway pembayaran seperti Midtrans, Stripe, atau Xendit menampilkan formulir OTP kartu kredit di dalam Iframe lintas domain (*cross-origin iframe*). Alat otomasi tradisional sering macet total di titik ini.

---

## 5. What?

### A. Anatomi Iframe & Shadow DOM Piercing
- **Iframe (Inline Frame)**: Sebuah dokumen HTML independen yang disematkan di dalam dokumen HTML induk. Driver browser biasa tidak bisa melihat elemen di dalam iframe tanpa berpindah konteks secara eksplisit.
- **Playwright Solution**: `page.frameLocator("iframe#payment-frame").getByLabel("Card Number")`.
- **Shadow DOM**: Pohon DOM tersembunyi yang diisolasi oleh Web Components (`#shadow-root (open)`).
- **Playwright Solution**: Playwright secara otomatis menembus Shadow DOM (*pierces shadow roots*) secara transparan saat menggunakan CSS atau Role locators tanpa konfigurasi khusus.

---

### B. Network Interception & Routing (`page.route()`)
Playwright memungkinkan QA bertindak sebagai *Proxy Man-in-the-Middle* di dalam peramban:

```text
========================================================================================
                      NETWORK INTERCEPTION WITH page.route()
========================================================================================

  [ BROWSER UI (Frontend Client) ]
                 |
                 | Melakukan request: GET /api/v1/user/balance
                 v
     +-----------------------+
     | page.route() Listener | <--- QA mencegat request di jaringan
     +-----------------------+
                 |
         +-------+-------+
         |               |
(Fulfill Mock Respon) (Lanjutkan ke Backend Asli)
         |               |
         v               v
  Kembalikan JSON      route.continue() ➔ Kirim ke Staging Server
  Palsu Buatan QA:
  { balance: 9999999 }
         |
         v
  [ UI Render Saldo Tanpa Akses Database Nyata! ]
```

---

## 6. How? Langkah Demi Langkah Implementasi

### 1. Instant Auth Bypass Menggunakan `storageState`
Jalankan login satu kali di `global-setup`, simpan sesi ke file, lalu gunakan kembali di seluruh test:

```typescript
// 1. Simpan sesi login ke file JSON
await page.goto("https://app.testing.id/login");
await page.getByLabel("Email").fill("tester@corp.id");
await page.getByLabel("Password").fill("Secret123!");
await page.getByRole("button", { name: "Masuk" }).click();
await page.context().storageState({ path: "auth-session.json" });

// 2. Di file test lain: Langsung buka dashboard tanpa login lagi!
test.use({ storageState: "auth-session.json" });

test("Buka halaman profil langsung terotentikasi", async ({ page }) => {
  await page.goto("https://app.testing.id/profile");
  // Pengguna langsung berstatus login! Menghemat 5 detik per test case.
  await expect(page.getByText("Profil Saya")).toBeVisible();
});
```

---

### 2. Network Mocking: Mensimulasikan Error 500 pada Server
```typescript
test("UI menampilkan pesan darurat saat API katalog melempar 500", async ({ page }) => {
  // Cegat request ke endpoint produk dan kembalikan status 500
  await page.route("**/api/v1/products", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ error: "INTERNAL_SERVER_ERROR", message: "Database Down" })
    });
  });

  await page.goto("https://app.testing.id/products");

  // Verifikasi antarmuka merespon error secara anggun (Graceful Degradation)
  await expect(page.getByText("Maaf, layanan katalog sedang mengalami gangguan")).toBeVisible();
  await expect(page.getByRole("button", { name: "Coba Lagi" })).toBeVisible();
});
```

---

## 7. Analogy
- **Iframe**: Bayangkan sebuah loket kasir bank kaca anti-peluru (*parent window*) yang di dalamnya memiliki loket khusus penukaran mata uang asing milik perusahaan rekanan (*iframe*). Anda tidak bisa menyodorkan uang rupiah ke meja utama kasir; Anda harus memasukkan tangan Anda khusus ke laci loket rekanan tersebut (*frameLocator*).
- **Storage Injection**: Alih-alih Anda harus antre di pos satpam, menunjukkan KTP, mengisi buku tamu, dan difoto setiap kali masuk gedung kantor (Login via UI), Anda langsung diberi kartu akses VIP sidik jari (*storageState cookies*) sehingga Anda bisa melenggang masuk langsung ke lantai 10 dalam 1 detik.

---

## 8. Diagram

```text
========================================================================================
                      NESTED IFRAME INTERACTION ARCHITECTURE
========================================================================================

  [ PARENT PAGE DOM (https://checkout.shop.id) ]
    |
    |-- <div class="header">
    |-- <div class="order-summary">
    |
    +-- <iframe id="stripe-modal" src="https://js.stripe.com/v3">
          |
          v (page.frameLocator("#stripe-modal"))
          |
          +-- [ IFRAME DOM LEVEL 1 ]
                |-- <input name="cardnumber">
                |-- <input name="cvc">
                |
                +-- <iframe id="3d-secure-otp">
                      |
                      v (.frameLocator("#3d-secure-otp"))
                      |
                      +-- [ NESTED IFRAME LEVEL 2 ]
                            |-- <input id="sms-otp-token">
                            |-- <button id="btn-submit-otp">
```

---

## 9. Simple Example: Berinteraksi dengan Elemen di dalam Iframe

```typescript
test("Memasukkan nomor kartu kredit di dalam Iframe Stripe", async ({ page }) => {
  await page.goto("https://shop.testing.id/checkout");

  // 1. Temukan iframe menggunakan frameLocator
  const paymentFrame = page.frameLocator("iframe[title='Form Pembayaran Kartu']");

  // 2. Akses elemen di dalam iframe seperti biasa
  await paymentFrame.getByPlaceholder("Nomor Kartu").fill("4111 2222 3333 4444");
  await paymentFrame.getByPlaceholder("MM/YY").fill("12/28");
  await paymentFrame.getByPlaceholder("CVC").fill("123");

  // 3. Tombol konfirmasi berada di halaman luar (parent DOM)
  await page.getByRole("button", { name: "Konfirmasi Pembayaran" }).click();
  await expect(page.getByText("Pembayaran Berhasil")).toBeVisible();
});
```

---

## 10. Practical Example: Geolocation & Mobile Device Emulation

```typescript
import { test, expect, devices } from "@playwright/test";

// Emulasi perangkat iPhone 14 dengan koordinat GPS Monas Jakarta
test.use({
  ...devices["iPhone 14"],
  geolocation: { latitude: -6.175392, longitude: 106.827153 }, // Monas Jakarta
  permissions: ["geolocation"],
  locale: "id-ID",
  timezoneId: "Asia/Jakarta"
});

test("Aplikasi mendeteksi lokasi toko terdekat di Jakarta", async ({ page }) => {
  await page.goto("https://toko.id/stores");

  // Verifikasi banner toko terdekat menampilkan cabang Gambir Jakarta Pusat
  await expect(page.getByText("Toko Terdekat: Cabang Jakarta Monas")).toBeVisible();
});
```

---

## 11. Real World Example: Kegagalan Otomasi Finansial Akibat Iframe 3D Secure
Sebuah platform fintech e-wallet mengotomasi pengujian pembayaran kartu kredit:
- Pengujian selalu macet pada langkah verifikasi OTP perbankan karena bank menerapkan proteksi Iframe 3D Secure bertingkat dua (*nested cross-origin iframe*).
- Tester manual harus duduk menunggu di depan layar CI setiap rilis untuk mengklik popup OTP secara manual.
- **Solusi Playwright**: Dengan merantai dua kali `.frameLocator()`, Playwright mampu mendeteksi elemen input OTP di dalam iframe bank secara otomatis, memulihkan status 100% *Unattended Automation* pada pipeline rilis malam hari.

---

## 12. Trade-offs

| Pendekatan Pengujian | Keuntungan | Kelemahan |
|---|---|---|
| **UI Login Setiap Test** | Menguji proses login nyata 100%. | Sangat lambat; jika server auth down, seluruh 200 test gagal bersamaan. |
| **Storage State Injection** | Super cepat (< 10 ms), stabil. | Tidak menguji proses submit form login (harus diuji terpisah di 1 test khusus). |
| **Network Mocking (`page.route`)** | Menguji skenario offline/error secara instan, bebas biaya API vendor. | Data yang diuji adalah data tiruan; tidak mendeteksi perubahan kontrak API riil di backend. |

---

## 13. When To Use
- Gunakan **Storage State Injection** untuk 95% pengujian yang memerlukan status pengguna login (*Authenticated E2E tests*).
- Gunakan **`page.route()`** untuk memalsukan pemanggilan API pihak ketiga yang berbayar (seperti API SMS OTP, face recognition, atau credit scoring).
- Gunakan **Device Emulation** saat menguji responsivitas antarmuka pada layar smartphone dan orientasi portrait/landscape.

## 14. When NOT To Use
- Jangan menggunakan Network Mocking untuk semua hal pada pengujian integrasi E2E sejati (*True E2E Testing*); biarkan beberapa skenario kritis memanggil backend asli staging.
- Jangan menggunakan Storage Injection pada skenario yang memang bertujuan menguji fungsionalitas formulir login itu sendiri (*Login Feature Test*).

---

## 15. Common Mistakes

```text
1. MISTAKE: Mencoba mencari elemen di dalam iframe menggunakan page.locator() biasa.
   WHY IT HAPPENS: QA lupa bahwa elemen tersebut terbungkus di dalam tag <iframe>.
   WHY IT IS BAD: Playwright melempar TimeoutError karena elemen tidak ditemukan di parent DOM.
   CORRECT APPROACH: Gunakan page.frameLocator("iframe_selector").getByRole(...)!

2. MISTAKE: Network mock yang terlalu luas (wildcard "page.route('**/*')").
   WHY IT HAPPENS: Menulis aturan interceptor tanpa filter path spesifik.
   WHY IT IS BAD: File statis penting seperti CSS, JavaScript bundle, dan gambar ikut terblokir sehingga halaman rusak.
   CORRECT APPROACH: Targetkan URL spesifik: "page.route('**/api/v1/checkout', handler)".
```

---

## 16. Best Practices

### Must Have
- Memisahkan satu file pengujian khusus untuk validasi form login UI, dan menggunakan `storageState` untuk seluruh file pengujian lainnya.
- Menutup (*abort*) atau melanjutkan (*continue*) setiap rute yang dicegat oleh `page.route()` agar tidak menggantung (*hanging requests*).

### Recommended
- Menggunakan `storageState` berbasis role (misal: `adminAuth.json`, `sellerAuth.json`, `buyerAuth.json`) untuk memudahkan pengujian multi-peran.
- Melakukan unroute (`await page.unroute()`) setelah pengujian mock selesai agar tidak mempengaruhi test case berikutnya.

### Advanced
- Menerapkan *HAR Recording & Replay* di Playwright: Merekam seluruh traffic jaringan sesi pengujian ke dalam file `.har`, lalu memutar ulang traffic tersebut di CI/CD tanpa koneksi internet sama sekali.

### Avoid / Overengineering
- Membuat 20 file `storageState` berbeda untuk variasi atribut minor seperti warna avatar profil. Cukup satu akun per role.

---

## 17. Troubleshooting: Gagal Mengakses Iframe Lintas Domain (Cross-Origin Policy)
Jika Playwright menampilkan error saat mengakses iframe:
`SecurityError: Blocked a frame with origin "https://app.id" from accessing a cross-origin frame.`
1. **Penyebab**: Browser security sandbox membatasi akses JavaScript antar-origin yang berbeda.
2. **Solusi Playwright**: Playwright mengabaikan SOP (*Same-Origin Policy*) di level browser CDP jika Anda menggunakan `page.frameLocator()`. Jangan gunakan `page.evaluate()` mentah di dalam iframe cross-origin.

---

## 18. Exercise
1. Tuliskan kode Playwright untuk mencegat permintaan API `GET /api/v1/user/notifications` dan mengembalikan daftar notifikasi palsu berisi 3 pesan promo diskon.
2. Jelaskan bagaimana Anda menguji bahwa aplikasi web Anda mampu beroperasi dalam kondisi **Offline Mode** (koneksi internet terputus) menggunakan fitur network routing Playwright.

---

## 19. Challenge
Rancang sebuah skenario pengujian otomasi pembayaran e-commerce tingkat lanjut:
1. Bypass autentikasi login menggunakan injeksi token JWT ke dalam `localStorage` sebelum halaman dibuka (`page.addInitScript`).
2. Masuk ke halaman pembayaran dan isi nomor kartu kredit yang terletak di dalam Iframe: `<iframe id="midtrans-payment-frame">`.
3. Gunakan `page.route()` untuk memotong request `POST /api/charge` dan memalsukan respon sukses pembayaran HTTP 200 (`{ "transaction_status": "settlement" }`).
4. Verifikasi bahwa halaman sukses menampilkan pesan *"Transaksi Berhasil"* tanpa memotong saldo bank nyata.

---

## 20. Summary
- Iframe memisahkan dokumen independen dan wajib diakses menggunakan `page.frameLocator()`.
- Shadow DOM Web Components dapat ditembus secara transparan oleh locator bawaan Playwright.
- Storage State Injection mengeliminasi overhead login UI yang berulang, menghemat 80% waktu eksekusi test suite.
- Network Interception (`page.route()`) memberikan kekuatan penuh bagi QA untuk memalsukan respon backend, mensimulasikan kegagalan server, dan menguji ketahanan antarmuka tanpa biaya pihak ketiga.

---

## Hands-on Practice: Simulator Shadow DOM & Storage State Injector
Jalankan script simulator yang mendemonstrasikan penembusan Shadow DOM, injeksi token sesi instan ke dalam storage browser, dan manipulasi interceptor rute jaringan:

```bash
node QA/BAB-06-Otomasi-Pengujian-Web-UI-Modern/hands-on/m02/shadow_dom_storage_injector_sim.js
```

---
[⬅️ Module 01: Playwright Auto-Waiting & Locators](./Module-01-Playwright-Web-UI-Automation-Locators-AutoWaiting.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 06 ➡️](./BAB-06-Quiz-dan-Challenge.md)
---
