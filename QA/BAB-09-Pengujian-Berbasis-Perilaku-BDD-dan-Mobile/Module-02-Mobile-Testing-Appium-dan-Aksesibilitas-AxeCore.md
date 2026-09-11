---
[⬅️ Module 01: BDD, Gherkin, & Living Docs](./Module-01-Behavior-Driven-Development-BDD-Gherkin-Cucumber.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 09 ➡️](./BAB-09-Quiz-dan-Challenge.md)
---

# Module 02: Pengujian Aplikasi Mobile (Appium) & Otomasi Audit Aksesibilitas (axe-core)

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Mengidentifikasi arsitektur ekosistem pengujian mobile: perbedaan antara aplikasi **Native (Swift/Kotlin)**, **Hybrid/Webview**, dan **Cross-Platform (Flutter/React Native)**.
- Memahami arsitektur internal **Appium**: protokol W3C WebDriver, driver **UiAutomator2** untuk Android, dan driver **XCUITest** untuk iOS.
- Menguasai otomasi gestur sentuhan perangkat mobile (*W3C Actions API*): **Tap**, **Long Press**, **Scroll**, **Swipe**, dan **Pinch-to-Zoom**.
- Menangani tantangan fragmentasi perangkat mobile (*Device Fragmentation*), rotasi layar (*Orientation*), manipulasi izin akses (*Permissions*), dan emulasi kondisi jaringan (*2G, 3G, Flaky Network, Airplane Mode*).
- Mengintegrasikan engine audit aksesibilitas otomatis **axe-core** ke dalam pipeline pengujian Web dan Mobile untuk mendeteksi pelanggaran standar **WCAG 2.1 AA** secara instan.

---

## 2. Prerequisite
- Memahami konsep pengujian UI Web dan Page Object Model dari BAB 05 dan BAB 06.
- Pemahaman dasar tentang sistem operasi mobile (Android APK & iOS IPA/Simulator).

---

## 3. Concept
Pengujian aplikasi mobile menghadirkan tingkat kompleksitas yang jauh lebih tinggi daripada pengujian web desktop. Pengguna mobile tidak menggunakan mouse atau keyboard fisik; mereka berinteraksi menggunakan sentuhan jari (*Touch Gestures*), kamera pemindai QR, sensor GPS, dan autentikasi biometrik sidik jari. Selain itu, ekosistem Android terfragmentasi ke dalam ribuan variasi ukuran layar, spesifikasi RAM, dan versi OS dari berbagai vendor ponsel.

Untuk mengotomasi pengujian mobile lintas platform, standar emas industri adalah **Appium**. Appium mengadopsi filosofi: *"Anda tidak perlu memodifikasi kode sumber aplikasi atau menambahkan SDK khusus hanya untuk mengujinya."* Di sisi lain, untuk memastikan aplikasi mobile dan web ramah bagi penyandang disabilitas, QA menggunakan engine **axe-core** yang mampu mengaudit ribuan aturan kepatuhan aksesibilitas secara terprogram dalam hitungan detik.

---

## 4. Why?
Mengapa Appium dan axe-core sangat penting bagi QA profesional?
1. **Satu API untuk iOS dan Android (Cross-Platform Automation)**: Appium menggunakan protokol standar W3C WebDriver. Anda dapat menggunakan pola dan bahasa pemrograman yang sama (TypeScript/Python/Java) untuk menguji aplikasi Android dan iPhone.
2. **Pengujian Gestur Nyata**: Memverifikasi alur gestur kompleks seperti menarik untuk menyegarkan (*Pull-to-Refresh*), menggeser carousel banner (*Swipe*), atau mencubit peta (*Pinch to Zoom*).
3. **Pencegahan Diskriminasi Aksesibilitas (Automated A11y Guard)**: Audit manual membutuhkan waktu berhari-hari. Mengintegrasikan `axe-core` ke pipeline CI/CD menangkap 57% pelanggaran aksesibilitas WCAG secara otomatis sebelum aplikasi dirilis ke Google Play Store atau Apple App Store.

---

## 5. What?

### A. Arsitektur Internal Appium

```text
========================================================================================
                          APPIUM CLIENT-SERVER ARCHITECTURE
========================================================================================

  [ QA Test Script (TypeScript / Playwright / WebdriverIO) ]
                 |
                 | HTTP REST (W3C WebDriver Commands)
                 v
        [ APPIUM SERVER (Node.js) ]
                 |
         +-------+-------------------------------+
         |                                       |
         | (Untuk Android)                       | (Untuk iOS)
         v                                       v
  [ UiAutomator2 Driver ]                 [ XCUITest Driver ]
         |                                       |
         v                                       v
  [ Android Device / Emulator ]           [ iOS Device / Simulator ]
  (Mengontrol Sistem Operasi via          (Mengontrol Sistem Operasi via
   Appium Server Instrumentation)          Apple WebDriverAgent.app)
```

---

### B. Gestur Mobile W3C Actions API
Interaksi sentuhan modern diatur oleh W3C Actions standard:
- **Tap**: `pointerDown` $\to$ pause(50ms) $\to$ `pointerUp`.
- **Long Press**: `pointerDown` $\to$ pause(1000ms) $\to$ `pointerUp`.
- **Swipe / Scroll**: `pointerMove(startX, startY)` $\to$ `pointerDown` $\to$ `pointerMove(endX, endY, duration: 600ms)` $\to$ `pointerUp`.
- **Pinch-to-Zoom**: Dua pointer bergerak saling mendekat (*Pinch In*) atau menjauh (*Pinch Out*).

---

### C. Engine Aksesibilitas Otomatis: axe-core
`axe-core` (oleh Deque Systems) adalah mesin audit aksesibilitas open-source standar dunia.
Ketika diinjeksikan ke halaman web atau webview mobile, `axe-core` mengevaluasi pohon elemen DOM terhadap aturan WCAG:
- **Kategori Pelanggaran (Impact Levels)**: `minor`, `moderate`, `serious`, dan `critical`.
- **Contoh Rule**: `color-contrast`, `image-alt`, `label`, `button-name`, `aria-roles`.

---

## 6. How? Menjalankan Script Uji Appium & axe-core

### 1. Contoh Skrip Gestur Sentuhan Mobile (WebdriverIO / Appium):
```typescript
// Melakukan gestur Swipe dari bawah ke atas (Vertical Scroll)
async function swipeUp(driver) {
  const { width, height } = await driver.getWindowRect();
  const startX = Math.floor(width / 2);
  const startY = Math.floor(height * 0.8); // 80% layar bawah
  const endY = Math.floor(height * 0.2);   // 20% layar atas

  await driver.action("pointer")
    .move({ x: startX, y: startY })
    .down()
    .pause(100)
    .move({ duration: 600, x: startX, y: endY })
    .up()
    .perform();
}
```

---

### 2. Contoh Audit Aksesibilitas Otomatis dengan axe-core:
```typescript
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("Halaman checkout bebas dari pelanggaran kritis WCAG", async ({ page }) => {
  await page.goto("https://shop.testing.id/checkout");

  // Jalankan audit axe-core pada seluruh halaman
  const accessibilityScanResults = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"]) // Standar WCAG 2.1 AA
    .analyze();

  // Filter hanya pelanggaran serius dan kritis
  const criticalViolations = accessibilityScanResults.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious"
  );

  // Assertion: Wajib 0 pelanggaran kritis!
  expect(criticalViolations).toEqual([]);
});
```

---

## 7. Analogy
- **Mobile Testing**: Bayangkan menguji sebuah helikopter mini (*Drone*). Anda tidak bisa hanya memeriksa baling-balingnya saat diam di meja; Anda harus mengujinya saat tertiup angin kencang (*Koneksi sinyal jelek*), saat baterai tinggal 5% (*Low Battery Throttling*), dan saat dikendalikan dengan joystick sentuh (*Touch Gestures*).
- **axe-core**: Bayangkan seorang petugas inspektur keselamatan bangunan yang datang membawa checklist resmi. Dalam 5 detik, ia memeriksa apakah ada jalur kursi roda, apakah tulisan rambu evakuasi kebakaran cukup terang, dan apakah tombol darurat lift dapat ditekan tanpa tangga.

---

## 8. Diagram

```text
========================================================================================
                      axe-core AUDIT INGESTION ARCHITECTURE
========================================================================================

  [ BROWSER CONTEXT / MOBILE WEBVIEW ]
                 |
                 | 1. Injeksi skrip axe.min.js ke dalam DOM runtime
                 v
       [ AXE-CORE AUDIT ENGINE ]
                 |
                 | 2. Evaluasi 90+ Aturan WCAG 2.1 AA
                 |    - Memeriksa rasio kontras elemen
                 |    - Memeriksa peran ARIA
                 |    - Memeriksa atribut alt gambar
                 v
       [ VIOLATION JSON REPORT ]
                 |
         +-------+-------+
         |               |
(Pelanggaran Kritis = 0) (Ditemukan Pelanggaran Serius/Kritis)
         |               |
         v               v
  [ PASS BUILD ]   [ CI/CD BUILD REJECTED! ]
                   - Tampilkan elemen HTML yang melanggar
                   - Berikan link rekomendasi perbaikan WCAG
```

---

## 9. Simple Example: Penanganan Emulasi Kondisi Jaringan Mobile

```typescript
// Mensimulasikan koneksi lambat 3G pedesaan pada aplikasi mobile
async function emulateSlowNetwork(driver) {
  // Mengatur profil jaringan via Appium Android / Chrome DevTools
  await driver.setNetworkConnection({
    airplaneMode: false,
    wifi: false,
    data: true // Hanya koneksi data seluler lambat
  });

  // Uji timeout handling: Apakah aplikasi menampilkan loader atau offline banner?
  const isOfflineBannerVisible = await driver.$("~offline-banner").isDisplayed();
  expect(isOfflineBannerVisible).toBe(true);
}
```

---

## 10. Practical Example: Format Laporan Pelanggaran axe-core

Ketika `axe-core` mendeteksi cacat aksesibilitas, ia menghasilkan laporan terperinci yang memandu developer memperbaiki masalah secara presisi:

```json
{
  "id": "color-contrast",
  "impact": "serious",
  "description": "Ensures the contrast between foreground and background colors meets WCAG 2 AA thresholds",
  "help": "Elements must have sufficient color contrast",
  "helpUrl": "https://dequeuniversity.com/rules/axe/4.8/color-contrast",
  "nodes": [
    {
      "html": "<span class=\"text-muted\">Total Diskon: Rp 10.000</span>",
      "target": [".text-muted"],
      "failureSummary": "Element has insufficient color contrast of 2.45:1 (foreground color: #a0aec0, background color: #ffffff, font size: 12.0pt). Expected contrast ratio of 4.5:1"
    }
  ]
}
```

---

## 11. Real World Example: Kegagalan Biometrik Mobile Banking pada Android Terfragmentasi
Sebuah aplikasi perbankan meluncurkan fitur login sidik jari (*Fingerprint Login*):
- Fitur diuji hanya pada 2 perangkat emulator Google Pixel terbaru. Test PASS 100%.
- Saat dirilis ke publik, aplikasi mengalami force close pada jutaan ponsel vendor tertentu (Xiaomi, Samsung, Oppo lawas) karena implementasi sensor biometrik vendor menggunakan API non-standar (*Vendor-specific Biometric Prompt*).
- Rating aplikasi di Google Play Store anjlok dari 4.6 menjadi 1.8 dalam satu malam.
- **Solusi QA**: Memanfaatkan *Cloud Device Farm* (seperti BrowserStack / AWS Device Farm) untuk menjalankan skrip Appium pada 20 variasi ponsel Android fisik nyata sebelum rilis produksi.

---

## 12. Trade-offs

| Aspek Pengujian | Web Browser Testing | Mobile App Testing (Appium) |
|---|---|---|
| **Kecepatan Eksekusi** | Sangat Cepat (Detik). | Lambat (Instalasi APK/IPA, boot emulator 1–3 menit). |
| **Biaya Infrastruktur** | Murah (Headless browser). | Tinggi (Memerlukan Cloud Device Farm / Mesin fisik). |
| **Stabilitas (Flakiness)**| Stabil. | Rentan flakiness akibat animasi native dan latensi USB/ADB. |
| **Cakupan Aksesibilitas**| axe-core otomatis sangat mudah. | Memerlukan inspeksi hierarchy accessibility label native. |

---

## 13. When To Use
- Gunakan **Appium** untuk menguji alur pengguna inti pada aplikasi Android dan iOS native (*End-to-End Mobile Journey*).
- Integrasikan **axe-core** pada seluruh pipeline pengujian web dan hybrid mobile webview sebagai *Quality Gate* wajib.
- Gunakan **Emulasi Jaringan** saat menguji sinkronisasi data offline pada aplikasi kurir logistik lapangan.

## 14. When NOT To Use
- Jangan menggunakan Appium untuk menguji logika perhitungan matematika atau parsing data murni; uji dengan Unit Testing di level kode Android/iOS (*JUnit / XCTest*).
- Jangan menjalankan pengujian Appium pada 100 variasi perangkat fisik di setiap commit kecil (terlalu lambat dan mahal); jalankan pengujian matriks perangkat penuh hanya pada jadwal build rilis mingguan.

---

## 15. Common Mistakes

```text
1. MISTAKE: Mengandalkan selector XPath absolut berbasis native index di Appium.
   Contoh Buruk: "//android.widget.FrameLayout[1]/android.view.ViewGroup[2]/android.widget.Button[1]".
   WHY IT HAPPENS: QA menyalin XPath dari Appium Inspector tanpa membuat ID khusus.
   WHY IT IS BAD: Perubahan minor pada susunan UI akan mengubah nomor index dan mematahkan seluruh skrip uji.
   CORRECT APPROACH: Minta developer menambahkan "accessibility-id" (content-desc pada Android dan accessibilityIdentifier pada iOS).

2. MISTAKE: Mengabaikan pengujian izin runtime (Runtime Permissions: Kamera, Lokasi, Notifikasi).
   WHY IT HAPPENS: Tester menguji aplikasi yang izinnya sudah disetujui secara manual.
   WHY IT IS BAD: Pengguna baru yang baru pertama kali menginstal aplikasi akan mengalami crash saat popup izin OS muncul.
   CORRECT APPROACH: Rancang skenario pengujian penolakan dan persetujuan izin runtime via Appium capability autoGrantPermissions.
```

---

## 16. Best Practices

### Must Have
- Menggunakan **Accessibility ID (`~locator`)** sebagai strategi locator utama di Appium.
- Menegakkan audit **axe-core** otomatis dengan batas toleransi 0 pelanggaran kritis (*Zero Critical A11y Violations*).

### Recommended
- Menggunakan *Cloud Device Farms* (BrowserStack, SauceLabs, AWS Device Farm) untuk pengujian paralel pada berbagai model ponsel nyata.
- Menambahkan kemampuan pemulihan otomatis (*Auto-Dismiss System Dialogs*) pada konfigurasi Desired Capabilities Appium.

### Advanced
- Mengintegrasikan analisis konsumsi baterai (*Battery Drain Profiling*) dan kebocoran memori perangkat (*Memory Leak Inspection via ADB dumpsys*) ke dalam eksekusi test mobile.

### Avoid / Overengineering
- Mencoba membuat skrip otomasi yang menguji 100% gestur game 3D hiper-kompleks menggunakan Appium; Appium dirancang untuk aplikasi produktivitas bisnis, bukan game engine OpenGL/Unity.

---

## 17. Troubleshooting: Appium Sering Kehilangan Sesi (SessionNotCreatedException)
Jika terminal menampilkan:
`SessionNotCreatedException: UiAutomator2 server was unable to start on the device`
1. **Penyebab**: Sisa-sisa aplikasi penguji `io.appium.uiautomator2.server` di perangkat Android mengalami freeze atau crash dari sesi uji sebelumnya.
2. **Solusi Cepat**:
   - Hapus instrumen lama via terminal ADB:
     ```bash
     adb uninstall io.appium.uiautomator2.server
     adb uninstall io.appium.uiautomator2.server.test
     ```
   - Pasang capability: `appium:noReset = false` untuk pembersihan otomatis.

---

## 18. Exercise
1. Tuliskan potongan kode konfigurasi *Desired Capabilities* Appium untuk meluncurkan aplikasi Android dengan spesifikasi:
   - Platform: Android versi 14.0
   - Automation Engine: UiAutomator2
   - Nama Paket Aplikasi: `com.tokoserba.app`
   - Activity Awal: `com.tokoserba.app.MainActivity`
   - Opsi: Memberikan izin lokasi otomatis (*autoGrantPermissions: true*).
2. Jelaskan mengapa pengujian aksesibilitas menggunakan `axe-core` tetap membutuhkan pengujian manual pelengkap oleh pengguna disabilitas nyata (*Human Assisted Testing*).

---

## 19. Challenge
Rancang sebuah **Suite Pengujian Mobile & Aksesibilitas Terintegrasi**:
1. Rancang skenario pengujian gestur Appium: Pengguna membuka katalog mobile, melakukan gestur *Swipe Down* untuk memuat produk baru, dan mengklik item menggunakan Accessibility ID: `~product-card-101`.
2. Simulasikan penanganan kehilangan sinyal internet (*Network Disconnect*) di tengah proses pembayaran dan verifikasi bahwa aplikasi menampilkan dialog: *"Koneksi terputus. Pembayaran Anda aman dalam antrean lokal."*
3. Integrasikan audit `axe-core` pada halaman hasil transaksi dan cetak seluruh daftar pelanggaran standar WCAG 2.1 Level AA yang ditemukan.

---

## 20. Summary
- Pengujian aplikasi mobile (Appium) menguji interaksi sentuhan nyata (Tap, Swipe, Long Press) pada platform Android dan iOS tanpa mengubah kode sumber aplikasi.
- Accessibility ID (`content-desc` / `accessibilityIdentifier`) adalah strategi locator paling stabil dan tahan terhadap fragmentasi perangkat.
- `axe-core` mengotomasi audit aksesibilitas digital secara instan dan dapat diintegrasikan sebagai quality gate di pipeline CI/CD.
- Pengujian mobile yang tangguh wajib memperhitungkan tantangan dunia nyata: fragmentasi vendor perangkat, izin runtime, dan kondisi jaringan seluler yang fluktuatif.

---

## Hands-on Practice: Simulator Gestur Mobile & Engine Audit axe-core
Jalankan script simulator yang mendemonstrasikan kalkulasi koordinat gestur sentuhan mobile (Swipe, Tap, Scroll) dan mengeksekusi engine audit aksesibilitas otomatis yang memindai aturan WCAG 2.1 AA:

```bash
node QA/BAB-09-Pengujian-Berbasis-Perilaku-BDD-dan-Mobile/hands-on/m02/mobile_gesture_axe_auditor_sim.js
```

---
[⬅️ Module 01: BDD, Gherkin, & Living Docs](./Module-01-Behavior-Driven-Development-BDD-Gherkin-Cucumber.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 09 ➡️](./BAB-09-Quiz-dan-Challenge.md)
---
