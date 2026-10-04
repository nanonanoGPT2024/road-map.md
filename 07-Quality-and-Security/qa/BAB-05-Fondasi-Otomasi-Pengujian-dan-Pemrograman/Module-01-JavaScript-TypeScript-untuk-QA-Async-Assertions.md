---
[⬅️ BAB 04: Quiz & Challenge](../BAB-04-Pengujian-API-dan-Validasi-Kontrak/BAB-04-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Arsitektur POM & Design Patterns ➡️](./Module-02-Arsitektur-Framework-Otomasi-POM-dan-Design-Patterns.md)
---

# Module 01: Fondasi Pemrograman untuk QA: JavaScript/TypeScript, Asynchronous Flow, & Arsitektur Test Framework

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Menguasai konsep fundamental bahasa pemrograman **JavaScript / TypeScript modern (ES2022+)** yang esensial untuk rekayasa otomasi pengujian (*Software Development Engineer in Test / SDET*).
- Memahami secara mendalam **Asynchronous Programming**: *Event Loop, Microtasks vs Macrotasks, Callback Hell, Promises*, dan sintaks modern `async` / `await` untuk menangani operasi I/O dan interaksi browser.
- Menghindari perangkap umum dalam otomasi pengujian seperti *Unhandled Promise Rejection*, *Race Conditions*, dan pengujian asinkron yang selesai sebelum assertion dievaluasi (*False Passing Tests*).
- Memahami arsitektur internal dari test runner modern (mirip Jest, Mocha, Playwright Test Runner): struktur blok **`describe`**, **`it` / `test`**, lifecycle hooks (**`beforeAll`**, **`beforeEach`**, **`afterEach`**, **`afterAll`**), serta matcher assertions (**`expect().toBe()`**, **`toEqual()`**, **`toThrow()`**).
- Memanfaatkan **TypeScript Type Safety** (Interfaces, Generics, Enums, Union Types) untuk membangun test script yang bebas typo selector dan mudah dirawat.

---

## 2. Prerequisite
- Memahami konsep dasar logika pemrograman (variabel, perulangan, kondisi *if-else*, fungsi).
- Pengalaman dasar menjalankan skrip Node.js di terminal.

---

## 3. Concept
Otomasi pengujian modern bukanlah sekadar merekam gerakan mouse menggunakan tool perekam (*Record & Replay*). Tool perekam menghasilkan skrip yang rapuh, sulit dirawat, dan tidak mampu menangani logika bisnis yang dinamis. Seorang QA Automation Engineer atau SDET sejati menulis kode pengujian menggunakan bahasa pemrograman nyata.

Karena ekosistem web modern (Playwright, Cypress, WebDriverIO, Puppeteer) digerakkan oleh **JavaScript dan TypeScript**, pemahaman mendalam tentang **eksekusi asinkron (Asynchronous Flow)** menjadi prasyarat mutlak. Browser merender halaman secara asinkron, elemen HTML membutuhkan waktu untuk dimuat lewat jaringan, dan animasi CSS berjalan independen. Tanpa pemahaman `async`/`await`, skrip otomasi Anda akan gagal (*flaky*) bukan karena aplikasinya rusak, melainkan karena skrip pengujian berjalan lebih cepat daripada respon peramban.

---

## 4. Why?
Mengapa QA Engineer wajib menguasai pemrograman dan logika asinkron?
1. **Mengeliminasi Sleep Statis (`sleep(5000)`)**: Pemrogram pemula sering mengatasi ketidaksinkronan browser dengan memasang jeda waktu tidur statis. Ini memperlambat eksekusi suite hingga berjam-jam. Pemahaman Promises memungkinkan penggunaan *Conditional Auto-Waiting*.
2. **Mencegah "Silent False Passing Tests"**: Jika sebuah fungsi asinkron tidak di-`await` di dalam blok tes, runner JavaScript akan menyelesaikan tes dengan status "PASS" sebelum server atau browser sempat mengembalikan error. Anda mengira aplikasi Anda aman, padahal pengujiannya tidak pernah dievaluasi!
3. **Membangun Testing Framework Mandiri**: Memahami arsitektur test runner memberdayakan Anda untuk memperluas fungsionalitas, membuat custom reporter, dan mengintegrasikannya dengan infrastruktur CI/CD perusahaan.

---

## 5. What?

### A. Model Eksekusi Asynchronous JavaScript (Event Loop)
JavaScript adalah bahasa single-threaded yang menggunakan antrean kejadian (**Event Loop**) untuk menangani operasi yang membutuhkan waktu tunggu (seperti HTTP Fetch, Database Query, atau DOM Rendering):

```text
========================================================================================
                          JAVASCRIPT EVENT LOOP ARCHITECTURE
========================================================================================

   [ CALL STACK ]                           [ WEB APIs / NODE C++ APIS ]
  (Eksekusi Sinkron)                        (Timer, Network Request, DOM I/O)
         |                                                 |
         | Operasi Asinkron Dipanggil                      | Operasi Selesai
         v                                                 v
  await fetch(...) -------------------------> Menunggu respon jaringan...
                                                           |
                                                           v
   [ EVENT LOOP ] <------------------------- [ TASK / MICROTASK QUEUE ]
  (Jika Stack Kosong,                               (Promise Resolution,
   Tarik Callback)                                   then / async callbacks)
         |
         v
   Eksekusi Assertion di Test Runner!
```

---

### B. Siklus Hidup Test Runner (Lifecycle Hooks)
Setiap framework otomasi profesional memiliki hierarki eksekusi standar:

```text
describe("Suite: Fitur Pembayaran E-Commerce", () => {
  beforeAll(() => {
    // Dijalankan 1 KALI SEBELUM semua tes dimulai (misal: Buka browser / DB Seed)
  });

  beforeEach(() => {
    // Dijalankan SETIAP KALI sebelum SATU test case dieksekusi (misal: Reset Keranjang)
  });

  test("TC-01: Pembayaran sukses", async () => {
    // Eksekusi skenario uji
  });

  afterEach(() => {
    // Dijalankan SETIAP KALI setelah SATU test case selesai (misal: Bersihkan Cookies / Screenshot jika gagal)
  });

  afterAll(() => {
    // Dijalankan 1 KALI SETELAH seluruh tes selesai (misal: Tutup koneksi DB / Close Browser)
  });
});
```

---

## 6. How? Menulis Asynchronous Test yang Andal

### 1. Pola Fatal (Anti-Pattern): Lupa Memasang `await`
```javascript
// BAHAYA BESAR: Test ini akan selalu PASS bahkan jika ekspektasi salah!
test("Anti-pattern: Missing await", () => {
  // fetchUserData bersifat asinkron (mengembalikan Promise)
  fetchUserData(101).then(user => {
    expect(user.name).toBe("Wrong Name"); // Assertion ini TIDAK PERNAH DITUNGGU!
  });
  // Runner langsung mencapai akhir fungsi dan menandai test PASS!
});
```

### 2. Pola Benar: Menggunakan `async` dan `await`
```javascript
// BENAR: Test menunggu Promise selesai sebelum menentukan status Pass/Fail
test("Reliable Async Test: Menggunakan async/await", async () => {
  const user = await fetchUserData(101);
  expect(user.name).toBe("Ahmad Fauzi");
  expect(user.role).toBe("QA_ENGINEER");
});
```

---

## 7. Analogy
Bayangkan memesan kopi di kedai yang sangat ramai:
- **Sinkron (Blocking)**: Anda berdiri di depan kasir dan kasir menolak melayani pelanggan lain sampai kopi Anda selesai diseduh selama 10 menit. Seluruh antrean macet total.
- **Asinkron (Non-Blocking / Promises)**: Kasir menerima pesanan Anda, menyerahkan kartu pager alarm bergetar (*Promise*), dan langsung melayani pelanggan berikutnya. Saat kopi matang, pager bergetar (*Promise Resolved*), dan Anda mengambil kopi Anda di konter (*`await`*).
- **Lupa `await` dalam Pengujian**: Anda memesan kopi, langsung pulang tanpa menunggu pager bergetar, lalu menulis ulasan *"Rasa kopinya enak!"* padahal Anda sama sekali belum pernah mencicipinya.

---

## 8. Diagram

```text
========================================================================================
                          TEST RUNNER EXECUTION FLOW
========================================================================================

                 [ START SUITE EXECUTION ]
                             |
                             v
                     [ beforeAll() Hook ]
                             |
              +------------->+
              |              |
              |              v
              |      [ beforeEach() Hook ]
              |              |
              |              v
        (Ulangi untuk   [ async test() Block ]
         setiap test)        |
              |              v (Evaluasi Assertion: expect().toBe())
              |              |
              |              v
              |      [ afterEach() Hook ]
              |              |
              +--------------+ (Ada test berikutnya?)
                             | (Semua test selesai)
                             v
                     [ afterAll() Hook ]
                             |
                             v
                 [ GENERATE SUMMARY REPORT ]
```

---

## 9. Simple Example: Anatomi Assertion Matcher Mandiri

Bagaimana method seperti `expect(a).toBe(b)` bekerja di balik layar?

```javascript
function expect(actual) {
  return {
    toBe(expected) {
      if (actual !== expected) {
        throw new Error(`Assertion Failed:\n  Expected: ${expected} (${typeof expected})\n  Actual:   ${actual} (${typeof actual})`);
      }
    },
    toEqual(expected) {
      const actualJson = JSON.stringify(actual);
      const expectedJson = JSON.stringify(expected);
      if (actualJson !== expectedJson) {
        throw new Error(`Deep Equality Mismatch:\n  Expected: ${expectedJson}\n  Actual:   ${actualJson}`);
      }
    },
    toBeGreaterThan(min) {
      if (actual <= min) {
        throw new Error(`Expected ${actual} to be strictly greater than ${min}`);
      }
    }
  };
}

// Penggunaan:
expect(10).toBe(10); // Lolos
expect({ id: 1 }).toEqual({ id: 1 }); // Lolos
```

---

## 10. Practical Example: Menangani Penolakan Asinkron (`rejects` / `toThrow`)

Salah satu tanggung jawab utama QA adalah menguji apakah sistem melempar error yang tepat ketika masukan salah:

```javascript
async function withdrawMoney(amount, balance) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (amount > balance) {
        reject(new Error("INSUFFICIENT_FUNDS"));
      } else {
        resolve(balance - amount);
      }
    }, 50);
  });
}

// Skenario Pengujian Negatif Asinkron yang Andal:
test("Menolak penarikan jika saldo tidak mencukupi", async () => {
  let caughtError = null;
  try {
    await withdrawMoney(500000, 100000); // Tarik 500k dari saldo 100k
  } catch (err) {
    caughtError = err;
  }

  // Verifikasi bahwa error benar-benar dilempar dan memiliki pesan yang tepat
  expect(caughtError).not.toBeNull();
  expect(caughtError.message).toBe("INSUFFICIENT_FUNDS");
});
```

---

## 11. Real World Example: Kegagalan Pipeline CI/CD Akibat Test Suite yang "False Pass"
Sebuah perusahaan logistik memiliki 500 unit test untuk kalkulator tarif pengiriman:
- Developer mengubah fungsi kalkulator menjadi fungsi asinkron (`async calculateTariff()`) untuk mengambil data tarif terbaru dari cache Redis.
- Namun, tim pengembang lupa menambahkan kata kunci `await` pada pemanggilan fungsi di dalam 80 file unit test yang sudah ada.
- **Dampak Fatal**: Pipeline CI/CD tetap berwarna HIJAU (*All 500 tests passed in 1.2s*), padahal semua pengetesan melempar *Unhandled Promise Rejection* di latar belakang yang diabaikan runner.
- Kode dengan bug tarif gratis rilis ke produksi, menyebabkan ribuan pengguna mendapatkan ongkir Rp 0 selama 3 hari.

---

## 12. Trade-offs

| Pendekatan Scripting | Kelebihan | Kelemahan |
|---|---|---|
| **JavaScript Murni (Vanilla JS)** | Fleksibel, tanpa kompilasi build, cepat dieksekusi langsung di Node.js. | Tidak ada type safety; rawan typo nama field atau method yang baru ketahuan saat runtime. |
| **TypeScript untuk QA** | Auto-complete (*IntelliSense*) sangat kuat, menangkap error compile-time, dokumentasi tipe jelas. | Memerlukan proses kompilasi (`tsc` / `ts-node`), kurva belajar setup konfigurasi `tsconfig.json`. |
| **No-Code / Low-Code Test Tool**| Mudah digunakan pemula tanpa kemampuan koding. | Sangat rapuh, sulit menguji alur kompleks, vendor lock-in, sulit diintegrasikan ke Git CI/CD. |

---

## 13. When To Use
- Gunakan **TypeScript** pada proyek otomasi skala menengah hingga besar (> 50 test cases) untuk mencegah bug typo pada locator dan data model.
- Gunakan pola **`async` / `await`** pada seluruh interaksi yang melibatkan I/O, network request, animasi UI, atau operasi database.
- Manfaatkan **`beforeEach` hook** untuk mengisolasi kondisi awal setiap test case (*Clean State Principle*).

## 14. When NOT To Use
- Jangan gunakan `beforeAll` untuk membuat data mutabel yang nilainya diubah-ubah oleh test case berikutnya (menyebabkan *Test Interdependency* dan *Flakiness*). Gunakan `beforeEach`.
- Jangan menggunakan `setTimeout(fn, 5000)` manual di dalam test script. Gunakan fungsi polling atau *explicit conditional wait*.

---

## 15. Common Mistakes

```text
1. MISTAKE: Memakai hardcoded delay "await new Promise(r => setTimeout(r, 5000))".
   WHY IT HAPPENS: QA ingin memastikan elemen browser sudah selesai loading.
   WHY IT IS BAD: Jika elemen selesai dalam 200ms, Anda membuang waktu 4.8 detik secara sia-sia. Jika koneksi lambat 5.1 detik, tes tetap gagal!
   CORRECT APPROACH: Gunakan polling bersyarat (Explicit Wait): tunggu hingga elemen berstatus visible dengan batas timeout maksimal.

2. MISTAKE: State tercemar antar-test case (Shared Mutable State).
   WHY IT HAPPENS: Menaruh variabel data global di luar blok describe/test tanpa meresetnya.
   WHY IT IS BAD: Test case B hanya bisa PASS jika test case A dijalankan sebelumnya. Jika test dijalankan secara acak atau paralel, test case B gagal.
   CORRECT APPROACH: Setiap test case harus mandiri (Self-Contained). Buat data baru atau reset state di beforeEach hook.
```

---

## 16. Best Practices

### Must Have
- Selalu tandai fungsi callback test dengan `async` jika di dalamnya memanggil operasi Promise, dan selalu gunakan `await`.
- Menegakkan prinsip **FIRST**: *Fast, Independent, Repeatable, Self-Validating, Timely*.

### Recommended
- Mengatur konfigurasi linting (*ESLint rule: `@typescript-eslint/no-floating-promises`*) untuk mendeteksi Promise yang lupa di-`await` secara otomatis.
- Mengelompokkan skenario terkait menggunakan blok `describe` hierarkis berjenjang.

### Advanced
- Membangun custom matcher assertions (misal: `expect(response).toBeValidUserSchema()`) untuk meningkatkan keterbacaan laporan kegagalan.

### Avoid / Overengineering
- Membuat abstraksi helper bertingkat 5 level untuk sekadar mengisi satu kolom form input.

---

## 17. Troubleshooting: Mendeteksi Unhandled Promise Rejection
Jika terminal menampilkan:
`[UnhandledPromiseRejection: This error originated either by throwing inside of an async function without a catch block...]`
1. **Penyebab**: Ada Promise asinkron yang melempar error di luar kendali test runner karena tidak di-`await`.
2. **Cara Mengatasi**:
   - Pasang event handler pendeteksi di root script:
     ```javascript
     process.on("unhandledRejection", (reason) => {
       console.error("CRITICAL UNHANDLED REJECTION DETECTED:", reason);
       process.exit(1);
     });
     ```
   - Telusuri baris fungsi yang tidak memiliki kata kunci `await`.

---

## 18. Exercise
1. Tinjau potongan kode test berikut dan temukan kesalahan logika fatalnya:
   ```javascript
   test("Verifikasi kalkulasi diskon", () => {
     apiClient.getDiscount(100).then(res => {
       expect(res.discount).toBe(20);
     });
   });
   ```
   Tuliskan kode perbaikan yang benar menggunakan `async`/`await`.
2. Buatlah custom assertion function bernama `assertBetween(actual, min, max)` yang melempar `AssertionError` jika nilai berada di luar rentang inklusif $[min, max]$.

---

## 19. Challenge
Rancang sebuah **Micro Test Runner Engine** mandiri dalam JavaScript murni yang mendukung:
1. Blok `describe(suiteName, fn)` dan `test(testName, asyncFn)`.
2. Lifecycle hooks `beforeEach(fn)` dan `afterEach(fn)`.
3. Assertion matcher: `toBe(expected)`, `toEqual(expected)`, dan `toBeGreaterThan(expected)`.
4. Pelaporan ringkasan di akhir eksekusi dengan warna hijau untuk PASS, merah untuk FAIL, serta durasi eksekusi per test dalam milidetik.

---

## 20. Summary
- Otomasi pengujian modern dibangun di atas pondasi bahasa pemrograman riil (JavaScript/TypeScript).
- Pemahaman ekosistem Asinkron (`Promises` dan `async`/`await`) adalah kunci mutlak untuk menghindari tes gagal palsu (*flaky*) atau lolos palsu (*false pass*).
- Struktur test runner standar terdiri dari `describe`, `test`, lifecycle hooks (`beforeEach`/`afterEach`), dan assertion matchers.
- Setiap test case wajib bersifat independen, deterministik, dan dapat dijalankan tanpa bergantung pada hasil test case lain.

---

## Hands-on Practice: Simulator Micro Test Framework & Async Assertion Engine
Jalankan script simulator yang mengimplementasikan test runner mandiri lengkap dengan blok describe, lifecycle hooks, evaluasi Promise asinkron, dan pelaporan statistik eksekusi:

```bash
node QA/BAB-05-Fondasi-Otomasi-Pengujian-dan-Pemrograman/hands-on/m01/mini_test_framework_sim.js
```

---
[⬅️ BAB 04: Quiz & Challenge](../BAB-04-Pengujian-API-dan-Validasi-Kontrak/BAB-04-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Arsitektur POM & Design Patterns ➡️](./Module-02-Arsitektur-Framework-Otomasi-POM-dan-Design-Patterns.md)
---
