---
[⬅️ BAB 08 Quiz & Challenge](../BAB-08-Keamanan-Full-Stack-Defensif-OWASP/BAB-08-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: OpenTelemetry & Core Web Vitals ➡️](./Module-02-OpenTelemetry-FullStack-Tracing-dan-Core-Web-Vitals.md)
---

# Module 01: End-to-End Testing Modern: Playwright Automation, Component Testing, & Visual Regression

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Memahami filosofi dan keunggulan arsitektural **Playwright** dibandingkan alat pengujian terdahulu (Cypress, Selenium) dalam hal konkurensi, isolasi proses, dan eksekusi lintas browser (Chromium, Firefox, WebKit).
- Menguasai konsep **Auto-Waiting & Web-First Assertions**: menghilangkan *flaky tests* akibat jeda waktu manual (`sleep/timeout`) melalui mekanisme pooling predikat bawaan.
- Menerapkan teknik **Authentication State Re-use (`storageState.json`)**: melakukan autentikasi satu kali di fase *setup*, lalu menggunakannya kembali di ratusan pengujian tanpa harus mengisi form login berulang kali.
- Menguasai teknik **Network Interception & API Mocking (`page.route()`)**: mensimulasikan kegagalan server (500 Internal Server Error), *slow network throttling*, dan mock gateway pihak ketiga (Stripe, Midtrans) di pipeline CI/CD.
- Mengimplementasikan **Visual Regression Testing (`toHaveScreenshot()`)** untuk mendeteksi perubahan visual dan pergeseran tata letak antarmuka secara otomatis hingga ke level piksel.

---

## 2. Prerequisite
- Memahami struktur DOM, CSS Selectors, dan elemen semantik HTML (Roles, Labels, ARIA attributes).
- Memahami alur kerja autentikasi cookie dan Next.js App Router.
- Memahami eksekusi asynchronous di JavaScript / TypeScript (`async/await`, Promises).

---

## 3. Concept
Dalam piramida pengujian perangkat lunak (*Testing Pyramid*), pengujian unit (*Unit Test*) dan integrasi (*Integration Test*) sering kali dijalankan di lingkungan virtual sintetis seperti **JSDOM** (Node.js). Meskipun cepat, JSDOM tidak memiliki rendering engine nyata: ia tidak menghitung CSS layout, tidak merender font, dan tidak memahami bagaimana browser menangani event klik pengguna secara riil.

**End-to-End (E2E) Testing dengan Playwright** menjalankan aplikasi Anda di dalam **browser asli (*Real Headless Browsers*)**:

```
[ TEST RUNNER (Playwright Test Runner) ]
                    |
      (Chrome DevTools Protocol / CDP Socket)
                    v
+--------------------------------------------------------+
| BROWSER NYATA TERISOLASI (Chromium / Firefox / WebKit) |
|                                                        |
|  - Render Engine Nyata (Blink / Gecko / WebKit)        |
|  - Layout Engine, CSS Grid, Media Queries              |
|  - Network Stack, Cookies, IndexedDB, Service Worker   |
|  - Interaksi Nyata Pengguna: Click, Type, Hover        |
+--------------------------------------------------------+
                    |
            (HTTP / WebSocket)
                    v
    [ FULL-STACK APP UNDER TEST (Next.js) ]
```

Playwright berkomunikasi langsung dengan proses browser melalui soket berkecepatan tinggi tanpa perantara webdriver yang lambat, memungkinkan kontrol penuh atas multi-tab, multi-origin (misal: redirect ke OAuth Google), dan emulasi perangkat mobile secara instan.

---

## 4. Why? (Mengapa Memilih Playwright?)

| Fitur | Playwright | Cypress | Selenium Webdriver |
| :--- | :--- | :--- | :--- |
| **Arsitektur Eksekusi** | Di luar browser via CDP Socket | Di dalam iframe browser | Eksternal via HTTP Webdriver |
| **Multi-Tab & Multi-Window**| **Didukung Penuh secara Native** | Terbatas (Satu tab saja) | Didukung (Cenderung Lambat) |
| **Dukungan Browser** | Chromium, Firefox, WebKit (Safari)| Chromium, Firefox, Electron | Semua (via driver masing-masing)|
| **Auto-Waiting** | **Otomatis (Bebas Flaky)** | Perlu chaining manual | Butuh explicit wait |
| **Kecepatan & Konkurensi** | **Sangat Cepat (Worker Threads)**| Menengah | Lambat |
| **Mobile Emulation** | **Native Viewport & Geolocation** | Terbatas pada resize | Terbatas |

**Masalah "Flaky Test" Teratasi**:
Penyebab utama pengembang membenci pengujian E2E adalah tes yang kadang lulus (*pass*) dan kadang gagal (*fail*) tanpa perubahan kode (*flakiness*), biasanya karena tombol belum selesai di-render saat skrip mencoba mengkliknya. 

Playwright menyelesaikan ini dengan **Auto-Waiting**: sebelum mengklik elemen, Playwright secara otomatis memastikan bahwa elemen tersebut:
1. Terpasang di DOM (*Attached*).
2. Terlihat di viewport (*Visible*).
3. Menghentikan animasi (*Stable*).
4. Mampu menerima event klik (*Receives Events*).
5. Tidak dalam keadaan disabled (*Enabled*).

---

## 5. What? (Komponen Utama Pengujian Playwright)

### A. Locators Berbasis Pengguna (User-Centric Locators)
Playwright mendorong pengujian dari sudut pandang pengguna nyata, bukan implementasi kode:
- `page.getByRole('button', { name: 'Bayar Sekarang' })`: Mencari tombol berdasarkan peran aksesibilitas dan teksnya.
- `page.getByLabel('Alamat Email')`: Menemukan input berdasarkan label `<label>`.
- `page.getByTestId('cart-total')`: Digunakan sebagai opsi cadangan jika elemen tidak memiliki teks semantik.

### B. Fixtures & Storage State
Menyimpan state login pengguna ke file JSON sehingga pengujian berikutnya dapat langsung berada dalam keadaan login tanpa harus mengisi form berulang-ulang:
- `browser.newContext({ storageState: 'playwright/.auth/user.json' })`.

---

## 6. How? (Implementasi Pengujian E2E & Mocking)

### 1. Konfigurasi Autentikasi Global (tests/auth.setup.ts)
```typescript
import { test as setup, expect } from "@playwright/test";

const authFile = "playwright/.auth/user.json";

setup("authenticate", async ({ page }) => {
  // 1. Buka halaman login
  await page.goto("/login");

  // 2. Isi formulir
  await page.getByLabel("Email").fill("tester@perusahaan.com");
  await page.getByLabel("Password").fill("PasswordAman123!");
  await page.getByRole("button", { name: "Masuk ke Dashboard" }).click();

  // 3. Pastikan halaman beralih ke dashboard
  await expect(page).toHaveURL("/dashboard");
  await expect(page.getByRole("heading", { name: "Selamat Datang" })).toBeVisible();

  // 4. Simpan cookies dan state sesi ke file JSON
  await page.context().storageState({ path: authFile });
});
```

### 2. Pengujian Alur Checkout & Network Mocking (tests/checkout.spec.ts)
```typescript
import { test, expect } from "@playwright/test";

// Gunakan sesi login yang sudah disimpan di setup!
test.use({ storageState: "playwright/.auth/user.json" });

test.describe("Alur Transaksi E-Commerce", () => {
  test("berhasil melakukan checkout saat gateway pembayaran sukses", async ({ page }) => {
    // 1. Mocking Panggilan Jaringan ke Gateway Eksternal (Stripe API)
    await page.route("**/api/payments/charge", async (route) => {
      // Kembalikan respons palsu instan (tanpa memotong saldo kartu kredit nyata!)
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          transactionId: "trx_mock_998877",
          status: "SETTLED",
        }),
      });
    });

    // 2. Buka katalog produk
    await page.goto("/products/macbook-pro");
    await page.getByRole("button", { name: "Tambah ke Keranjang" }).click();

    // 3. Masuk ke halaman keranjang
    await page.goto("/cart");
    await expect(page.getByTestId("cart-item-count")).toHaveText("1");

    // 4. Klik Tombol Bayar
    await page.getByRole("button", { name: "Konfirmasi & Bayar" }).click();

    // 5. Web-First Assertion: Verifikasi halaman sukses muncul
    await expect(page.getByRole("heading", { name: "Pembayaran Berhasil!" })).toBeVisible();
    await expect(page.getByText("trx_mock_998877")).toBeVisible();
  });

  test("menampilkan pesan error yang ramah saat server melempar error 500", async ({ page }) => {
    // Simulasi kegagalan server backend
    await page.route("**/api/payments/charge", async (route) => {
      await route.fulfill({
        status: 500,
        body: JSON.stringify({ error: "Koneksi gateway terputus" }),
      });
    });

    await page.goto("/cart");
    await page.getByRole("button", { name: "Konfirmasi & Bayar" }).click();

    // Verifikasi alert error muncul
    await expect(page.getByRole("alert")).toContainText("Gagal memproses pembayaran. Silakan coba lagi.");
  });
});
```

### 3. Pengujian Visual Regression (tests/visual.spec.ts)
```typescript
import { test, expect } from "@playwright/test";

test("memverifikasi tampilan halaman utama tidak bergeser tata letaknya", async ({ page }) => {
  await page.goto("/");
  // Menunggu font dan gambar selesai di-render
  await page.waitForLoadState("networkidle");

  // Bandingkan tangkapan layar piksel-per-piksel dengan snapshot baseline!
  await expect(page).toHaveScreenshot("homepage-baseline.png", {
    maxDiffPixelRatio: 0.02, // Toleransi perbedaan maksimal 2%
  });
});
```

---

## 7. Analogy
Bayangkan proses pengujian mobil sebelum diproduksi massal:
- **Unit Test (JSDOM)**: Anda menguji apakah baut roda memiliki ukuran yang tepat menggunakan jangka sorong di atas meja bengkel (*cepat, tapi Anda tidak tahu apakah mobil bisa berjalan*).
- **Manual QA**: Manusia menyetir mobil mengelilingi sirkuit setiap hari (*sangat lambat, membosankan, dan manusia bisa lelah atau lupa memeriksa indikator bensin*).
- **Playwright E2E Automation**: Sebuah robot presisi tinggi yang duduk di kursi pengemudi mobil nyata. Robot dapat menginjak pedal gas, mengerem, menyalakan AC, memutar setir di tengah hujan badai buatan (*network throttling*), dan mengukur kecepatan pengereman hingga satuan milidetik—mengulangi 1.000 tes dalam 5 menit tanpa pernah lelah!

---

## 8. Diagram Siklus Pengujian Terisolasi Playwright

```
+-----------------------------------------------------------------------------------+
| PLAYWRIGHT TEST RUNNER ENGINE                                                     |
|                                                                                   |
|  [ Setup Phase ]                                                                  |
|    - Login satu kali via UI/API                                                   |
|    - Ekspor cookies & localStorage ke `user.json`                                 |
|                                                                                   |
|  [ Worker Thread 1 ]           [ Worker Thread 2 ]          [ Worker Thread 3 ]   |
|    BrowserContext A              BrowserContext B             BrowserContext C    |
|    (Isolasi Cookie & Storage)    (Isolasi Cookie & Storage)   (Isolasi Cookie)    |
|    Test: Beli Produk             Test: Batalkan Pesanan       Test: Ubah Profil   |
|         |                             |                            |              |
|         +-----------------------------+----------------------------+              |
|                                       |                                           |
|                             (CDP WebSocket Socket)                                |
+---------------------------------------|-------------------------------------------+
                                        v
+-----------------------------------------------------------------------------------+
| HEADLESS CHROME / FIREFOX / WEBKIT INSTANCES                                      |
|                                                                                   |
|  [ Auto-Wait ] -> [ Intercept Network ] -> [ Real DOM Click ] -> [ Assert ]      |
+-----------------------------------------------------------------------------------+
```

---

## 9. Simple Example: Perbedaan Selektor Rapuh vs Resilient Locators

```typescript
// ❌ SANGAT RAPUH (Mudah rusak saat class CSS berubah atau div bertambah):
await page.click("div.container > div:nth-child(2) > form > button.btn-blue");

// ❌ RAPUH TERHADAP REFECTOR STRUKTUR:
await page.click('xpath=//*[@id="main"]/div[1]/button');

// ✅ SANGAT KUAT & BERPUSAT PADA PENGGUNA (Resilient):
await page.getByRole("button", { name: "Simpan Perubahan" }).click();

// ✅ AKSESIBEL & MEMATUHI STANDAR ARIA:
await page.getByLabel("Nomor Rekening").fill("1234567890");
```

---

## 10. Practical Example: Menguji Respon Desain di Mobile Viewport
Playwright memudahkan pengujian tampilan responsif tanpa memerlukan perangkat fisik:

```typescript
import { test, expect, devices } from "@playwright/test";

// Simulasikan perangkat iPhone 14 Pro
test.use({ ...devices["iPhone 14 Pro"] });

test("menu navigasi mobile dapat dibuka dan ditutup", async ({ page }) => {
  await page.goto("/");

  // Pada mobile, tombol burger menu harus terlihat
  const menuButton = page.getByRole("button", { name: "Buka Navigasi" });
  await expect(menuButton).toBeVisible();

  await menuButton.click();
  // Sidebar navigasi terbuka
  await expect(page.getByRole("link", { name: "Katalog Produk" })).toBeVisible();

  // Tutup kembali menu
  await page.getByRole("button", { name: "Tutup Menu" }).click();
  await expect(page.getByRole("link", { name: "Katalog Produk" })).toBeHidden();
});
```

---

## 11. Real-World Example: Multi-User Collaborative Canvas Testing
Menguji interaksi real-time di mana dua pengguna berada di dokumen yang sama secara bersamaan:

```typescript
test("dua pengguna dapat melihat perubahan kursor satu sama lain secara real-time", async ({ browser }) => {
  // Buat dua konteks browser yang sepenuhnya terpisah (User Alice & User Bob)
  const contextAlice = await browser.newContext();
  const contextBob = await browser.newContext();

  const pageAlice = await contextAlice.newPage();
  const pageBob = await contextBob.newPage();

  // Keduanya membuka room kolaborasi yang sama
  await pageAlice.goto("/board/room-101");
  await pageBob.goto("/board/room-101");

  // Alice menggambar kotak di kanvas
  await pageAlice.locator("#canvas").click({ position: { x: 100, y: 150 } });

  // Verifikasi di layar Bob: Elemen kotak harus muncul dalam waktu < 1 detik!
  await expect(pageBob.locator("#shape-box-1")).toBeVisible({ timeout: 2000 });
});
```

---

## 12. Trade-offs: E2E Testing vs Unit Testing

| Kriteria | End-to-End Test (Playwright) | Unit Testing (Vitest / Jest) |
| :--- | :--- | :--- |
| **Kepercayaan (*Confidence*)** | **Sangat Tinggi (Menguji Sistem Nyata)** | Menengah (Hanya menguji fungsi terisolasi) |
| **Kecepatan Eksekusi** | Menengah (Hitungan detik per skenario) | **Sangat Cepat (Hitungan milidetik)** |
| **Biaya Pemeliharaan** | Menengah | Sangat Rendah |
| **Deteksi Bug Integrasi** | **Sangat Baik (Menangkap bug UI + API)** | Lemah |
| **Kebutuhan Resource CI/CD** | Membutuhkan dependensi browser sistem | Sangat ringan |

---

## 13. When To Use Playwright E2E
- Jalur kritis bisnis (*Critical User Journeys*): Pendaftaran, Login, Onboarding, Checkout Pembayaran, Pengaturan Akun.
- Pengujian cross-browser (memastikan Safari/WebKit di iOS tidak rusak tata letaknya).
- Pengujian regresi visual halaman promosi dan landing page.

---

## 14. When NOT To Use Playwright
- Menguji fungsi utilitas murni seperti kalkulasi pajak atau formatting tanggal (Gunakan Unit Test Vitest).
- Menguji ratusan kombinasi variasi error validasi form kecil (Gunakan Component Test atau Unit Test).

---

## 15. Common Mistakes
1. **Menggunakan `page.waitForTimeout(3000)` (Hardcoded Sleep)**:
   - Membuat pengujian menjadi lambat dan tetap rentan gagal di server CI yang sedang lambat. Gunakan *Web-First Assertion* (`await expect(locator).toBeVisible()`).
2. **Menghubungkan Pengujian dengan ID Database yang Statis**:
   - Mengharap `user_id=1` selalu ada di database. Jika database di-reset, tes akan rusak. Selalu buat data baru (*Factory Data*) atau gunakan mocking jaringan.
3. **Mengabaikan Screenshot Snapshot Divergence di CI**:
   - Font di Ubuntu (server CI) berbeda dengan font di macOS/Windows lokal, menyebabkan tes visual selalu gagal. Solusi: Jalankan visual test di dalam Docker container terstandarisasi.

---

## 16. Best Practices

### Must Have
- Gunakan *User-Facing Locators* (`getByRole`, `getByText`, `getByLabel`) alih-alih selektor CSS/XPath.
- Gunakan `storageState` untuk menghemat waktu login pada pengujian rute terproteksi.
- Konfigurasikan *Trace Viewer* (`trace: 'on-first-retry'`) untuk merekam video dan DOM snapshot saat tes gagal di CI/CD.

### Recommended
- Jalankan pengujian secara paralel menggunakan worker threads (`fullyParallel: true`).
- Lakukan mocking pada layanan pihak ketiga berbayar (SMS gateway, kartu kredit).

### Advanced
- Gabungkan Playwright dengan *Synthetic Monitoring* di production untuk menguji jalur checkout setiap 15 menit sekali secara otomatis.

### Avoid
- Jangan menguji seluruh skenario negatif (*edge cases*) di E2E. Alokasikan 80% edge cases ke unit/integration tests dan simpan E2E untuk *happy path* & *critical error path*.

---

## 17. Troubleshooting Guide

| Gejala Masalah | Kemungkinan Akar Masalah | Solusi |
| :--- | :--- | :--- |
| Error `Timeout 30000ms exceeded while waiting for locator`. | Elemen terhalang oleh modal lain, loading spinner belum hilang, atau teks tombol berbeda. | Periksa tangkapan layar di folder `test-results` atau buka rekaman via `npx playwright show-trace`. |
| Pengujian visual selalu gagal dengan perbedaan 1% di font teks. | Anti-aliasing font berbeda antara sistem operasi lokal dan Linux di GitHub Actions. | Jalankan pengujian visual menggunakan container resmi `mcr.microsoft.com/playwright`. |
| Error `Target closed` saat menjalankan browser di Linux CI/CD. | Kurang dependensi paket OS (seperti library GTK atau NSS). | Jalankan `npx playwright install-deps` pada skrip workflow CI Anda. |

---

## 18. Exercise
- **Easy**: Tulis skrip Playwright sederhana yang membuka halaman `/about` dan memverifikasi bahwa judul halaman mengandung kata "Tentang Kami".
- **Medium**: Tulis tes yang mengisi form kontak, melakukan submit, dan memverifikasi bahwa tombol menjadi `disabled` selama proses loading.
- **Hard**: Buat pengujian multi-origin yang menguji alur Login with Google: mengklik tombol OAuth, menangani halaman popup login Google yang di-mock, dan memverifikasi token sesi tersimpan di browser utama.

---

## 19. Challenge
Rancang arsitektur pipeline pengujian E2E otomatis di GitHub Actions untuk monorepo e-commerce: Pipeline harus menjalankan setup database sementara (*ephemeral database*), melakukan seeding data produk acak, menjalankan 50 skenario pengujian Playwright secara paralel di 4 mesin worker (*sharding*), merekam trace saat terjadi kegagalan, dan mempublikasikan laporan HTML interaktif ke GitHub Pages.

---

## 20. Summary
- **Playwright** merevolusi pengujian End-to-End dengan menghadirkan eksekusi browser nyata yang cepat, andal, dan bebas dari *flaky tests*.
- Fitur **Auto-Waiting** dan **User-Centric Locators** memastikan pengujian Anda tahan banting terhadap perubahan implementasi styling atau refactoring kode.
- Menggabungkan autentikasi tersimpan (`storageState`), mocking jaringan fleksibel, dan visual regression testing memberikan keyakinan tertinggi bagi tim pengembang untuk merilis fitur baru ke produksi tanpa rasa cemas.

---

## Hands-on Practice: Simulasi Headless Browser E2E Test Runner & Network Mocking
Jalankan simulator engine test runner, auto-waiting assertion, dan network interceptor mandiri:

```bash
node Full-Stack/BAB-09-Testing-E2E-Playwright-dan-Observabilitas/hands-on/m01/e2e_browser_test_runner_sim.js
```

---
[⬅️ BAB 08 Quiz & Challenge](../BAB-08-Keamanan-Full-Stack-Defensif-OWASP/BAB-08-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: OpenTelemetry & Core Web Vitals ➡️](./Module-02-OpenTelemetry-FullStack-Tracing-dan-Core-Web-Vitals.md)
---
