# SEKSI 01 — IDENTITAS MODUL
* **Track:** Frontend & Mobile Engineering (03-Frontend-and-Mobile)
* **Topik:** HTML5 Native Forms & Constraint Validation API
* **Bab/Modul:** Bab 04 / Modul 01: Sistem Formulir Enterprise & Validasi Deklaratif
* **Target Audience:** Senior Frontend Engineers, Design System Engineers, Web Accessibility Specialists
* **Prasyarat Teknis:** DOM API, Event-driven Architecture, CSS Attribute Selectors, Web Accessibility (WCAG 2.2 AA).

---

# SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, peserta mampu:
1. Membedah siklus hidup *form submission* native browser dan interaksinya dengan engine parsing serta DOM.
2. Mengimplementasikan subsistem formulir skala enterprise dengan atribut deklaratif HTML5 murni tanpa dependensi JavaScript eksternal untuk validasi baseline.
3. Mengontrol state validitas browser melalui Constraint Validation API (`ValidityState`, `checkValidity()`, `reportValidity()`, `setCustomValidity()`).
4. Mengembangkan arsitektur formulir yang sepenuhnya aksesibel (WCAG 2.2 Level AA/AAA) dengan sinkronisasi ARIA Live Regions dan native semantics.
5. Membangun strategi mitigasi keamanan sisi klien (*client-side hardening*) terhadap eksfiltrasi data, over-posting, manipulasi DOM, serta integrasi anti-CSRF token.

---

# SEKSI 03 — MINDSET & MENTAL MODEL
### "Native-First, Script-Augmented"
Banyak rekayasawan web modern menganggap formulir HTML sekadar *wrapper* pasif yang harus digantikan secara agresif oleh JavaScript (*state management*, *controlled components*, *synthetic event listeners*). Pendekatan ini memicu *performance cost*, aksesibilitas yang rapuh, dan kegagalan total saat JavaScript terblokir atau mengalami error saat parsing.

Mental model yang benar:
* **Browser sebagai Mesin State Terintegrasi:** Browser memiliki internal state machine bawaan C++ untuk menangani nilai masukan, riwayat *undo/redo*, auto-fill, *sanitization*, dan validasi tipe. Tugas engineer adalah memprogram mesin state native ini melalui atribut deklaratif.
* **JavaScript Sebagai Augmentasi Progresif:** JavaScript digunakan secara eksklusif untuk orkestrasi skenario kompleks (koneksi asinkronus ke API, multi-step orchestration, custom visual rendering), bukan untuk menggantikan fondasi primitif yang telah disediakan browser secara gratis.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

```
                                      ALUR CONSTRAINT VALIDATION & SUBMISSION
                                      
  [User Action: Input / Change]
                │
                ▼
  ┌──────────────────────────┐
  │   Native Parser Engine   │
  │    (Value Sanitization)  │
  └─────────────┬────────────┘
                │
                ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │                   Browser Constraint Validation Engine                 │
  │  Evaluasi Boolean Flags:                                               │
  │  - valueMissing       - typeMismatch        - patternMismatch          │
  │  - tooLong/tooShort   - rangeUnder/Overflow - stepMismatch             │
  │  - badInput           - customError                                    │
  └───────────────────────────────┬────────────────────────────────────────┘
                                  │
                       Is ValidityState.valid == true?
                                  │
                 ┌────────────────┴────────────────┐
                 │                                 │
              [ FALSE ]                         [ TRUE ]
                 │                                 │
                 ▼                                 ▼
  ┌───────────────────────────────┐  ┌───────────────────────────────────────┐
  │  1. Dispatch event: 'invalid' │  │ Dispatch event: 'submit'              │
  │  2. Apply CSS :invalid pseudo │  │ (Event bubbles up to HTMLFormElement) │
  │  3. Halt pipeline             │  └──────────────────┬────────────────────┘
  │  4. Focus element & draw native│                    │
  │     error tooltip (if default │       Is event.preventDefault() called?
  │     not prevented)            │                    │
  └───────────────────────────────┘            ┌───────┴───────┐
                                               │               │
                                           [ YES ]           [ NO ]
                                               │               │
                                               ▼               ▼
                                 ┌──────────────────┐  ┌───────────────────────┐
                                 │ Serahkan kontrol │  │ Serialisasi Payload   │
                                 │ ke JS AJAX/Fetch │  │ (x-www-form-urlencoded│
                                 │ API              │  │  atau multipart) &    │
                                 │                  │  │ HTTP Request Native   │
                                 └──────────────────┘  └───────────────────────┘
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The `ValidityState` Interface
Setiap elemen yang berpartisipasi dalam form validation (`HTMLInputElement`, `HTMLSelectElement`, `HTMLTextAreaElement`, `HTMLButtonElement`) mengimplementasikan properti readonly `validity`. Objek `ValidityState` memiliki 11 boolean flags:

* `badInput`: Nilai masukan gagal dikonversi oleh browser (misal: teks alfabet pada `<input type="number">`).
* `customError`: Flag diaktifkan via `element.setCustomValidity(nonEmptyString)`.
* `patternMismatch`: Isi input tidak cocok dengan regular expression pada atribut `pattern`.
* `rangeOverflow`: Nilai melebihi atribut `max`.
* `rangeUnderflow`: Nilai kurang dari atribut `min`.
* `stepMismatch`: Nilai tidak cocok dengan interval atribut `step`.
* `tooLong`: Nilai melampaui `maxlength`.
* `tooShort`: Nilai lebih pendek dari `minlength`.
* `typeMismatch`: Sintaks nilai tidak valid untuk tipe yang dideklarasikan (`type="email"` atau `type="url"`).
* `valueMissing`: Atribut `required` aktif namun input bernilai kosong.
* `valid`: `true` jika dan hanya jika seluruh 10 flag di atas bernilai `false`.

### 2. Method Eksekusi Validasi
* `element.checkValidity()`: Menjalankan evaluasi. Menembakkan event `invalid` pada elemen jika ditemukan kesalahan. Mengembalikan `boolean`. Tidak memunculkan UI dialog/bubble bawaan browser.
* `element.reportValidity()`: Menjalankan evaluasi, menembakkan event `invalid`, dan menampilkan native validation bubble serta memindahkan fokus kursor ke elemen invalid pertama. Mengembalikan `boolean`.
* `form.checkValidity()` / `form.reportValidity()`: Menjalankan evaluasi iteratif ke seluruh *form-associated elements* di dalam form.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Relasi Kontrol Formulir & Aksesibilitas
Label eksplisit mengikat konteks semantik secara langsung ke kontrol. Hubungan atribut `for` pada `<label>` dengan `id` kontrol input bukan sekadar kosmetik:
1. **Perluasan Hitbox:** Area sentuh/klik label otomatis memicu fokus kontrol input, krusial bagi perangkat mobile dan aksesibilitas motorik.
2. **Accessible Name Computation:** Screen reader menggunakan algoritma *Accessible Name and Description Computation (AccName)* untuk mengekstrak label teks dan membacakannya ke pengguna tunanetra saat kontrol difokuskan.

### Mekanisme Pseudoclass `:user-invalid` vs `:invalid`
* `:invalid` dievaluasi langsung sejak *initial DOM render*. Jika field diberi tanda `required`, field tersebut seketika `:invalid` bahkan sebelum pengguna menyentuhnya, memicu *validation fatigue*.
* `:user-invalid` (W3C Selectors Level 4) hanya aktif jika pengguna telah berinteraksi dengan field (misal: memindahkan fokus / *blur*) dan nilainya melanggar validasi. Ini menghasilkan User Experience yang adaptif secara murni deklaratif CSS.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi form native enterprise baseline yang memvalidasi format rekening IBAN, nominal transfer, tanggal transaksi, dan otorisasi.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Fund Transfer Engine</title>
  <style>
    /* Indikator Status Deklaratif Native */
    .form-group {
      margin-bottom: 1.5rem;
      display: flex;
      flex-direction: column;
    }

    input:focus {
      outline: 2px solid #005fcc;
    }

    /* Menggunakan :user-invalid agar tidak memicu error sebelum disentuh */
    input:user-invalid {
      border: 2px solid #d9383a;
      background-color: #fff8f8;
    }

    input:user-valid {
      border: 2px solid #198754;
      background-color: #f8fff9;
    }

    .error-hint {
      display: none;
      color: #d9383a;
      font-size: 0.875rem;
      margin-top: 0.25rem;
    }

    input:user-invalid + .error-hint {
      display: block;
    }
  </style>
</head>
<body>

  <form id="transferForm" action="/api/v1/transfers" method="POST" novalidate>
    <!-- Field 1: Akun Tujuan (RegEx Pattern) -->
    <div class="form-group">
      <label for="targetAccount">ID Akun Tujuan (Format: ACC-XXXX-YY)</label>
      <input 
        type="text" 
        id="targetAccount" 
        name="target_account"
        required
        pattern="^ACC-[0-9]{4}-[A-Z]{2}$"
        autocomplete="off"
        aria-describedby="accountHint"
      />
      <span id="accountHint" class="error-hint">Format akun harus ACC-1234-AB (4 digit, 2 huruf kapital).</span>
    </div>

    <!-- Field 2: Nominal Transfer (Step & Range Boundaries) -->
    <div class="form-group">
      <label for="transferAmount">Jumlah Transfer (IDR, Kelipatan 10.000)</label>
      <input 
        type="number" 
        id="transferAmount" 
        name="amount"
        required
        min="10000"
        max="100000000"
        step="10000"
        aria-describedby="amountHint"
      />
      <span id="amountHint" class="error-hint">Minimum transfer Rp10.000, maksimum Rp100.000.000 dalam kelipatan 10.000.</span>
    </div>

    <button type="submit">Kirim Dana</button>
  </form>

</body>
</html>
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 38:** `<form ... novalidate>`: Atribut `novalidate` mematikan visual *bubble popup* bawaan browser yang sering kali merusak layout visual enterprise dan tidak seragam antar-engine (Blink vs Gecko vs WebKit), namun tetap membiarkan mesin validasi dan CSS pseudoclass internal aktif bekerja.
* **Baris 45:** `required`: Mengaktifkan flag `valueMissing`. Jika string bernilai kosong (`""`), form submission dicegah.
* **Baris 46:** `pattern="^ACC-[0-9]{4}-[A-Z]{2}$"`: Mengaktifkan flag `patternMismatch`. Engine browser mengevaluasi input terhadap RegExp ini secara penuh (`^(?:pattern)$`), menghemat penulisan handler JS custom.
* **Baris 48:** `aria-describedby="accountHint"`: Memberikan context relationship semantik bagi assistive technology, memastikan pengguna screen reader langsung mendengarkan pesan kesalahan saat kontrol gagal divalidasi.
* **Baris 58-60:** `min="10000" max="100000000" step="10000"`: Mengontrol secara presisi flag `rangeUnderflow`, `rangeOverflow`, dan `stepMismatch`. Browser secara native menolak eksekusi input angka float ganjil atau nilai di luar batas nominal.
* **Baris 19-27:** `input:user-invalid`: Selektor CSS modern yang menghindari visual error state saat inisialisasi awal render, dan hanya aktif setelah field ditinggalkan oleh user dalam kondisi data korup.

---

# SEKSI 09 — STUDI KASUS NYATA (ENTERPRISE SCENARIO)

### Sistem Pembayaran FinTech B2B (Global Settlement Gateway)
Dalam platform perbankan korporat, formulir transaksi harus menangani validasi multi-level:
1. Pemenuhan format ISO-20022 IBAN dan SWIFT-BIC secara deterministik.
2. Pencegahan race condition submission ganda (*double-spending anomaly*).
3. Feedback aksesibel real-time bagi user tunanetra yang bekerja di back-office operasional treasury.
4. Integrasi audit payload dengan proteksi Cross-Site Request Forgery (CSRF).

Solusi berbasis pustaka JavaScript eksternal murni mengalami masalah *bundle bloating* (React Hook Form / Formik mencapai 40KB+ parsial) dan sering kali menabrak mekanisme AutoFill password manager perbankan (1Password, Bitwarden). Pendekatan yang diimplementasikan adalah: **Constraint Validation API Hybrid Architecture** menggunakan Web Component berkinerja tinggi.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Corporate Settlement Portal</title>
  <style>
    :root {
      --color-err: #b00020;
      --color-border: #767676;
      --color-focus: #0d6efd;
      --color-bg-err: #fdf2f2;
    }

    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 2rem; }
    .form-pane { max-width: 600px; margin: 0 auto; border: 1px solid #ccc; padding: 2rem; border-radius: 4px; }
    
    .field-container { margin-bottom: 1.5rem; }
    .field-container label { display: block; font-weight: 600; margin-bottom: 0.5rem; }
    
    .field-container input {
      width: 100%;
      padding: 0.75rem;
      box-sizing: border-box;
      border: 1px solid var(--color-border);
      border-radius: 4px;
      font-size: 1rem;
    }

    .field-container input:focus {
      outline: 2px solid var(--color-focus);
      outline-offset: 2px;
    }

    .field-container[data-invalid="true"] input {
      border-color: var(--color-err);
      background-color: var(--color-bg-err);
    }

    .message-slot {
      display: block;
      color: var(--color-err);
      font-size: 0.875rem;
      min-height: 1.25rem;
      margin-top: 0.25rem;
    }

    .sr-only {
      position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
      overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border-0;
    }

    button:disabled { opacity: 0.6; cursor: not-allowed; }
  </style>
</head>
<body>

<main class="form-pane">
  <h2>Instruksi Kliring Devisa (ISO-20022)</h2>
  
  <!-- Live region untuk dynamic a11y announcements -->
  <div id="statusRegion" class="sr-only" aria-live="polite" aria-atomic="true"></div>

  <form id="settlementForm" method="POST" action="/api/v1/settle" novalidate>
    <!-- Hidden Security Context -->
    <input type="hidden" name="csrf_token" value="d9g8a7sdf6g78as6dfg87as6df78asd6f">

    <!-- Field 1: SWIFT / BIC Code -->
    <div class="field-container" id="container-swift">
      <label for="swiftCode">SWIFT / BIC Code Perbankan</label>
      <input 
        type="text" 
        id="swiftCode" 
        name="swift_code" 
        required 
        pattern="^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$"
        autocomplete="off"
        autocapitalize="characters"
        aria-describedby="swiftError"
        aria-invalid="false"
      />
      <span class="message-slot" id="swiftError" aria-live="polite"></span>
    </div>

    <!-- Field 2: Target IBAN -->
    <div class="field-container" id="container-iban">
      <label for="ibanCode">International Bank Account Number (IBAN)</label>
      <input 
        type="text" 
        id="ibanCode" 
        name="iban_code" 
        required
        minlength="15"
        maxlength="34"
        autocomplete="off"
        aria-describedby="ibanError"
        aria-invalid="false"
      />
      <span class="message-slot" id="ibanError" aria-live="polite"></span>
    </div>

    <button type="submit" id="submitBtn">Eksekusi Transaksi Finansial</button>
  </form>
</main>

<script>
(() => {
  'use strict';

  const form = document.getElementById('settlementForm');
  const submitBtn = document.getElementById('submitBtn');
  const statusRegion = document.getElementById('statusRegion');

  // Matrix Pemetaan Kesalahan Native ke Pesan Finansial
  const resolveErrorMessage = (element) => {
    const validity = element.validity;
    if (validity.valid) return '';
    if (validity.valueMissing) return 'Bidang ini wajib diisi oleh staf otorisasi.';
    if (validity.patternMismatch) return 'Format SWIFT/BIC tidak valid. Harus 8 atau 11 karakter alfanumerik kapital.';
    if (validity.tooShort) return `Karakter IBAN terlalu pendek. Minimum ${element.minLength} karakter.`;
    if (validity.tooLong) return `Karakter IBAN melebihi batas. Maksimum ${element.maxLength} karakter.`;
    if (validity.customError) return element.validationMessage;
    return 'Entri data tidak valid.';
  };

  // Sinkronisasi Status Form & Kontrak Visual
  const validateField = (inputEl) => {
    const container = inputEl.closest('.field-container');
    const messageSlot = container.querySelector('.message-slot');
    
    // Validasi Kompleks: Algoritma Checksum IBAN Sederhana via Script Augmentation
    if (inputEl.id === 'ibanCode' && !inputEl.validity.valueMissing) {
      if (!inputEl.value.startsWith('DE') && !inputEl.value.startsWith('GB')) {
        inputEl.setCustomValidity('Sistem saat ini hanya menerima kliring IBAN yurisdiksi DE atau GB.');
      } else {
        inputEl.setCustomValidity(''); // Reset custom error flag
      }
    }

    const isValid = inputEl.checkValidity();
    
    // Mutasi Atribut Semantik untuk Screen Reader & Visual State
    inputEl.setAttribute('aria-invalid', String(!isValid));
    container.setAttribute('data-invalid', String(!isValid));
    messageSlot.textContent = resolveErrorMessage(inputEl);

    return isValid;
  };

  // Event Binding: Validasi Real-time saat 'blur' dan pembersihan error saat 'input'
  const targetInputs = form.querySelectorAll('input:not([type="hidden"])');
  
  targetInputs.forEach((input) => {
    input.addEventListener('blur', () => {
      validateField(input);
    });

    input.addEventListener('input', () => {
      // Hapus error visual jika user sudah mulai memperbaiki input
      if (input.getAttribute('aria-invalid') === 'true') {
        validateField(input);
      }
    });
  });

  // Submission Pipeline Orchestration
  form.addEventListener('submit', async (event) => {
    event.preventDefault(); // Menghentikan sinkronisasi full reload, beralih ke secure fetch

    let isFormValid = true;
    let firstFailingElement = null;

    targetInputs.forEach((input) => {
      const fieldValid = validateField(input);
      if (!fieldValid && !firstFailingElement) {
        firstFailingElement = input;
      }
      isFormValid = isFormValid && fieldValid;
    });

    if (!isFormValid) {
      statusRegion.textContent = 'Formulir mengandung kesalahan data. Mohon koreksi bidang yang ditandai.';
      if (firstFailingElement) {
        firstFailingElement.focus();
      }
      return;
    }

    // Eksekusi Pipeline Pengiriman yang Aman
    submitBtn.disabled = true;
    statusRegion.textContent = 'Memproses settlement devisa ke gateway...';

    const payload = new FormData(form);

    try {
      const response = await fetch(form.action, {
        method: form.method,
        body: payload,
        headers: {
          'X-Requested-With': 'XMLHttpRequest'
        }
      });

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      statusRegion.textContent = 'Instruksi pembayaran berhasil diproses.';
      window.location.href = '/settlement/success';
    } catch (err) {
      statusRegion.textContent = `Kegagalan sistem jaringan: ${err.message}`;
      submitBtn.disabled = false;
    }
  });
})();
</script>
</body>
</html>
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Parameter | HTML5 Constraint Validation API murni | Form Library JS Pihak Ketiga (e.g., Formik, React Hook Form) | Validasi Manual Custom via Input Event JS |
| :--- | :--- | :--- | :--- |
| **Ukuran Bundle (Impact on TTI)** | 0 KB (Zero-cost native) | 10 KB - 45 KB Gzipped | 1 KB - 5 KB (Tergantung implementasi) |
| **Kompatibilitas Autofill Browser** | Maksimal (Native engine hooking) | Sering terdegradasi / butuh synthetic triggers | Menengah |
| **Ketergantungan Eksekusi JS** | Tetap memvalidasi tanpa JS | Rusak total jika script gagal di-load | Rusak total jika script gagal di-load |
| **Dukungan Desain Visual Kustom** | Memerlukan sinkronisasi CSS/JS | Sangat mudah dikustomisasi out-of-the-box | Bebas, seluruh CSS ditangani manual |
| **Validasi Asinkronus Kompleks** | Terbatas (harus manual via `setCustomValidity`) | Sangat fleksibel (mendukung async/await, Zod, Yup) | Fleksibel, ditangani secara imperatif |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The `novalidate` Bypassing Trap
Jika form memiliki atribut `novalidate`, browser **tidak akan** menjalankan validasi otomatis saat *native submit* (misal: user menekan enter di salah satu field). Jika pengembang lupa menjalankan `form.checkValidity()` di layer JavaScript, data yang tidak tervalidasi dapat bocor ke fungsi pengiriman.
*Mitigasi:* Selalu jalankan `input.checkValidity()` atau `form.checkValidity()` sebelum payload diproses secara asinkronus.

### 2. Format Sanitization pada `type="number"`
Input bertipe `number` tidak mengembalikan nilai representasi string ke DOM (`input.value`) jika karakter yang dimasukkan ilegal (contoh: huruf `e` untuk notasi eksponensial ilmiah atau tanda minus berulang). `input.value` akan mengembalikan empty string `""`, membuat aplikasi salah menduga bahwa field tersebut kosong (`valueMissing`), padahal kegagalan yang sebenarnya terjadi adalah `badInput`.
*Mitigasi:* Selalu periksa `element.validity.badInput` sebelum mengasumsikan input benar-benar kosong.

### 3. Mutasi Nilai via Script Mengabaikan Event Validasi
Memperbarui nilai form control secara programatis (`input.value = 'foo'`) **tidak menembakkan** event `input` maupun `change`, dan tidak memicu validasi ulang otomatis.
*Mitigasi:* Panggil `element.dispatchEvent(new Event('input'))` atau panggil langsung evaluasi validasi saat mutasi nilai dilakukan dari script.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menghilangkan Label Visibel Demi `placeholder`
* *Anti-Pattern:* `<input type="text" placeholder="Masukkan Nama Anda">` tanpa elemen `<label>`.
* *Dampak:* `placeholder` hilang saat input diketik, memori jangka pendek pengguna terbebani, screen reader sering kali mengabaikan teks petunjuk, dan rasio kontras warna placeholder umumnya gagal dalam tes WCAG.
* *Solusi:* Selalu gunakan elemen `<label>` eksplisit yang dipetakan via atribut `for` dan `id`.

### 2. Terlalu Dini Memanggil `setCustomValidity`
* *Anti-Pattern:* Memanggil `element.setCustomValidity('Format salah')` di event listener tanpa mekanisme pembersihan.
* *Dampak:* Nilai validasi kustom bersifat permanen sampai string tersebut dikosongkan. Field tersebut akan selamanya berstatus invalid (`customError: true`) meskipun user telah mengoreksi datanya.
* *Solusi:* Kosongkan pesan kesalahan (`element.setCustomValidity('')`) di baris paling awal dari fungsi verifikasi input sebelum mengecek aturan logika bisnis.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI
1. **Pemanfaatan Atribut Input Auto-complete Eksplisit:** Manfaatkan token standar WHATWG (misal: `autocomplete="billing street-address"`, `autocomplete="one-time-code"`) untuk mempercepat proses entri dan kompatibilitas sistem pengelola kredensial internal korporasi.
2. **Defensive Validation Boundaries:** Terapkan aturan kesetaraan ketat: Atribut validasi deklaratif di HTML (`maxlength`, `min`, `pattern`) harus identik dengan skema validasi backend (Zod, Joi, FluentValidation, Hibernate Validator) untuk menjamin paritas validasi.
3. **Penyajian Pesan Berdasarkan Konteks:** Hindari visual native error popup bawaan browser pada sistem enterprise. Gunakan `novalidate` pada form lalu render pesan kesalahan kustom ke DOM dengan integrasi atribut `aria-live`.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN
* **Penundaan Parsing Regex (RegExp Engine Footprint):** Eksekusi atribut `pattern` berjalan di thread parsing native C++ browser yang jauh lebih cepat daripada regex engine V8 JavaScript. Memanfaatkan native pattern menurunkan konsumsi memory garbage collection saat memvalidasi form besar secara dinamis.
* **Debouncing Event Validasi:** Hindari memvalidasi field yang melibatkan operasi berat pada event `keydown`. Gunakan kombinasi validasi instan pada event `blur` dan validasi adaptif pada event `input` setelah field masuk dalam state error.

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Form Action Hijacking & Open Redirect
Atribut `action` pada `<form>` dapat disusupi jika aplikasi merender URL action secara dinamis dari query string.
```html
<!-- Bahaya: Rentan Form Action Injection -->
<form action="<?= $_GET['redirect_url'] ?>">
```
*Hardening:* Selalu terapkan *Content Security Policy (CSP)* dengan direktif `form-action`:
```http
Content-Security-Policy: form-action 'self' https://payment-gateway.enterprise.com;
```

### 2. Over-posting / Mass Assignment Mitigation
Browser mengirimkan seluruh kontrol form yang memiliki atribut `name` dan tidak berstatus `disabled`.
*Hardening:* Jangan pernah melakukan pemetaan otomatis langsung (*auto-binding*) dari serialisasi form data ke database entity backend. Bangun layer *Data Transfer Object (DTO)* yang secara eksplisit melakukan *whitelisting* terhadap atribut field yang diizinkan.

---

# SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Untuk memantau *friction rate* pada form pengajuan korporat, kita dapat menyadap native event `invalid` pada tingkat root document selama fase bubbling/capturing:

```javascript
// Telemetri Validasi Formulir Global
document.addEventListener('invalid', (event) => {
  const target = event.target;
  const errorPayload = {
    fieldId: target.id,
    fieldName: target.name,
    validityState: {
      badInput: target.validity.badInput,
      patternMismatch: target.validity.patternMismatch,
      rangeOverflow: target.validity.rangeOverflow,
      rangeUnderflow: target.validity.rangeUnderflow,
      stepMismatch: target.validity.stepMismatch,
      tooLong: target.validity.tooLong,
      tooShort: target.validity.tooShort,
      typeMismatch: target.validity.typeMismatch,
      valueMissing: target.validity.valueMissing,
      customError: target.validity.customError
    },
    timestamp: Date.now()
  };

  // Kirim metrik ke pipeline analytics tanpa memblokir thread
  if ('sendBeacon' in navigator) {
    navigator.sendBeacon('/telemetry/form-errors', JSON.stringify(errorPayload));
  }
}, true); // Menangkap pada capture phase karena event 'invalid' tidak bubble secara native
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

```
┌─────────────────────────┬──────────────────────────┬───────────────────────────────────────────┐
│ ATRIBUT / METODE        │ VALIDITYSTATE FLAG       │ TUJUAN TEKNIS                             │
├─────────────────────────┼──────────────────────────┼───────────────────────────────────────────┤
│ required                │ valueMissing             │ Memastikan field tidak berstatus kosong   │
│ pattern="[A-Z]+"        │ patternMismatch          │ Validasi ekspresi reguler (implicit ^...$)│
│ min / max               │ rangeUnderflow / Overflow│ Batas komparasi numerik / tanggal         │
│ step="0.01"             │ stepMismatch             │ Interval pecahan / batasan granular       │
│ minlength / maxlength   │ tooShort / tooLong       │ Batasan panjang karakter teks             │
│ type="email|url"        │ typeMismatch             │ Validasi format sintaks global            │
│ setCustomValidity("..") │ customError              │ Menyuntikkan status error kustom manual   │
│ checkValidity()         │ -> boolean               │ Cek validitas & menembakkan event invalid │
│ reportValidity()        │ -> boolean               │ checkValidity() + memunculkan UI bubble   │
└─────────────────────────┴──────────────────────────┴───────────────────────────────────────────┘
```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

1. **Bagaimana karakteristik propagasi dari event native `invalid` yang ditembakkan oleh browser saat form submission gagal?**
   * A. Bubble hingga ke level `window`.
   * B. Mengalir secara native via capturing dan bubbling phases pada form element.
   * C. Hanya berjalan pada target element dan tidak melakukan bubbling ke elemen *ancestor*.
   * D. Menghentikan seluruh proses rendering DOM hingga user memasukkan nilai baru.
   * *Jawaban yang benar:* **C**. Event `invalid` menembak langsung pada control yang gagal dan tidak memiliki karakteristik *bubble*. Oleh karena itu, *global event delegation* untuk event `invalid` harus mengaktifkan fase capture (`addEventListener('invalid', callback, true)`).

2. **Kapan kondisi flag `ValidityState.badInput` bernilai `true`?**
   * A. Ketika pengguna memasukkan email tanpa domain `@`.
   * B. Ketika browser parser tidak dapat mengonversi teks mentah menjadi representasi data primitif field (misal: string pada `<input type="number">`).
   * C. Ketika atribut `pattern` tidak lolos evaluasi engine regex.
   * D. Ketika panjang input melebihi `maxlength`.
   * *Jawaban yang benar:* **B**.

3. **Apa perbedaan perilaku fungsional antara selektor CSS `:invalid` dengan `:user-invalid`?**
   * A. `:user-invalid` hanya bekerja pada perangkat mobile.
   * B. `:invalid` aktif secara langsung sejak DOM pertama kali dirender jika input memiliki cacat validasi (seperti field kosong dengan atribut `required`), sedangkan `:user-invalid` menahan visual state error hingga user berinteraksi dengan field.
   * C. `:user-invalid` membutuhkan class JavaScript eksternal untuk dapat berfungsi di browser.
   * D. Tidak ada perbedaan, keduanya adalah sinonim alias pada spesifikasi W3C.
   * *Jawaban yang benar:* **B**.

4. **Jika Anda mengeksekusi `element.setCustomValidity("Error spesifik")`, apa efek langsungnya pada objek `element.validity`?**
   * A. `element.validity.customError` menjadi `true`, dan `element.validity.valid` menjadi `false`.
   * B. Nilai field seketika direset menjadi string kosong.
   * C. Seluruh flag `ValidityState` lainnya otomatis diabaikan oleh form.
   * D. Nilai atribut `novalidate` pada form otomatis diubah menjadi `false`.
   * *Jawaban yang benar:* **A**.

5. **Mengapa penambahan atribut `novalidate` pada elemen form sangat direkomendasikan pada implementasi desain enterprise berbasis JavaScript modern?**
   * A. Untuk mengabaikan validasi keamanan backend.
   * B. Untuk mematikan visual tooltip bawaan browser yang inkonsisten antar OS/engine tanpa mematikan logika native Constraint Validation API.
   * C. Untuk meningkatkan kecepatan rendering gambar sebesar 20%.
   * D. Agar form dapat mengirimkan format data JSON murni secara native.
   * *Jawaban yang benar:* **B**.

---

# SEKSI 20 — TANTANGAN MANDIRI & PROYEK PRAKTIKUM

### Rancang Komponen Pembayaran: "Credit Card Settlement Form"

#### Spesifikasi Fungsional:
1. Bangun form HTML5 murni dengan atribut semantik untuk menangani 3 bidang data:
   * **Nomor