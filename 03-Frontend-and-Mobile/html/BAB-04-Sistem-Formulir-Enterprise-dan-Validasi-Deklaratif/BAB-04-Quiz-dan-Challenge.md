# BAB 04: Quiz, Challenge, & Knowledge Check
**Sistem Formulir Enterprise & Validasi Deklaratif**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Form Submission Algorithm & Enctype Serialization
Jelaskan secara mendalam perbedaan teknis antara `application/x-www-form-urlencoded`, `multipart/form-data`, dan `text/plain` dalam *Form Submission Algorithm* spesifikasi W3C/WHATWG. Bagaimana browser menstrukturisasi *stream* byte, menangani *boundary delimiter*, serta mengalokasikan memori ketika sebuah form memuat kombinasi data tekstual UTF-8 dan berkas biner berukuran besar?

### Soal 1.2: Siklus Hidup dan State Machine `ValidityState`
Antarmuka `ValidityState` mengontrol status validitas elemen form melalui 11 boolean flag (seperti `valueMissing`, `typeMismatch`, `patternMismatch`, hingga `customError`). Jelaskan urutan evaluasi browser terhadap flag-flag tersebut saat `checkValidity()` atau `reportValidity()` dipanggil! Bagaimana browser menentukan pesan galat default lokal (*localized validation message*) berdasarkan prioritas flag tersebut?

### Soal 1.3: Konsep "Submittable Elements" vs "Form-Associated Elements"
Sebutkan kriteria ketat spesifikasi HTML5 yang menentukan apakah suatu elemen dianggap sebagai *submittable element*. Mengapa elemen dengan atribut `disabled` dieksklusikan secara otomatis dari *form data set*, sementara elemen dengan atribut `readonly` tetap diserialisasi? Apa implikasi struktural dari ketiadaan atribut `name` pada elemen input terhadap alokasi payload HTTP?

### Soal 1.4: Semantik Relasional Aksesibilitas (`<label>`, `aria-describedby`, dan `aria-invalid`)
Dalam arsitektur form enterprise yang memenuhi WCAG 2.1 Level AA, mengapa pembungkusan implisit (`<label><input /></label>`) sering kali dianggap tidak mencukupi untuk skenario pesan validasi dinamis jika dibandingkan dengan asosiasi eksplisit (`for`/`id`) yang dipadukan dengan `aria-describedby` dan `aria-errormessage`? Jelaskan bagaimana pohon aksesibilitas (*Accessibility Tree*) merefleksikan perubahan status validasi tersebut ke *assistive technology* (screen reader)!

### Soal 1.5: Mekanisme Atribut Override pada Trigger Pengiriman
Jelaskan peran teknis dari famili atribut *form submission overrides*: `formaction`, `formenctype`, `formmethod`, `formnovalidate`, dan `formtarget` pada elemen `<button type="submit">` atau `<input type="submit">`. Bagaimana browser menyelesaikan konflik (*cascade resolution*) apabila terdapat inkonsistensi antara deklarasi atribut pada level root `<form>` dengan atribut pada tombol pemicu (*submission trigger*) yang diklik?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Mutasi State `:invalid` vs `:user-invalid`
CSS Pseudo-class `:invalid` sering memicu masalah UX kritis berupa *premature error display* (menampilkan visual eror sebelum pengguna selesai berinteraksi). Jelaskan algoritma internal browser dalam menentukan status pseudo-class baru `:user-invalid` dan kaitannya dengan status interaksi *user-interaction flag*! Mengapa manipulasi DOM terprogram via JavaScript (`element.value = "..."`) tidak serta merta memicu `:user-invalid`?

### Soal 2.2: The `setCustomValidity()` Trap & Event Loop Scheduling
Sebuah tim pengembang mengimplementasikan validasi custom dengan memanggil `input.setCustomValidity("Format tidak valid")` pada event listener `input`. Namun, form menjadi terkunci (*permanently invalid*) dan tidak dapat disubmit meskipun pengguna telah memasukkan format yang benar. Bedah mekanisme internal yang menyebabkan jebakan ini terjadi! Bagaimana siklus mikro dan makrotask browser memproses pembersihan string validasi tersebut agar form kembali ke status `valid`?

### Soal 2.3: Form-Associated Custom Elements (FACE) & `ElementInternals`
Dalam arsitektur *Design System* modern berbasis Web Components (Custom Elements), bagaimana antarmuka `ElementInternals` dan deklarasi statis `static formAssociated = true` menjembatani komponen di dalam Shadow DOM yang terisolasi agar dapat berpartisipasi dalam form validation lifecycle, berinteraksi dengan API `FormData`, serta merespons pemanggilan native `form.reset()`?

### Soal 2.4: I/O Bottleneck dan Memory Leak pada Penanganan Input File Masif
Sebuah aplikasi web enterprise mengizinkan pengunggahan batch multi-file (`<input type="file" multiple>`). Ketika pengguna memilih 50 file dengan total ukuran 4 GB, memori browser mengalami lonjakan drastis (*heap memory spike*) sesaat sebelum transmisi `fetch()` dengan payload `new FormData(form)`. Di lapisan mana (*browser process* vs *renderer process*) objek file tersebut diakses, dan bagaimana strategi mitigasi berbasis streaming File API untuk mencegah kegagalan tab browser (*OOM crash*)?

### Soal 2.5: Heuristik Browser Autofill vs Enkapsulasi Keamanan
Bagaimana browser enterprise (berbasis Blink dan Gecko) menerapkan heuristik pencocokan otomatis (*credential & address autofill engine*) terhadap atribut `autocomplete` (misalnya: `autocomplete="current-password"`, `autocomplete="one-time-code"`, atau token bertingkat `section-*`)? Apa celah keamanan yang timbul jika form registrasi tidak menggunakan atribut `autocomplete` secara ketat, terutama terkait kerentanan *form-hijacking* atau *hidden input autofill scraping*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Transaksi Ganda (Double-Submit Race Condition) pada Core Banking
* **Kasus:** Pada hari peluncuran sistem pembayaran baru di sebuah institusi perbankan, tercatat lonjakan transaksi ganda sebesar 3.4% pada jam sibuk. Investigasi forensik menunjukkan bahwa pengguna dengan latensi jaringan tinggi mengklik tombol "Bayar Sekarang" berulang kali. Tombol tersebut dinonaktifkan (`disabled = true`) oleh skrip SPA *setelah* request pertama dikirim. Namun, analisis log server membuktikan dua request valid masuk dengan selisih waktu 12 milidetik.
* **Pertanyaan Diagnostik:**
  1. Berdasarkan spesifikasi siklus submit HTML5 native, jelaskan mengapa penonaktifan tombol menggunakan `button.disabled = true` pada synchronous event handler `submit` masih menyisakan *execution window* yang memungkinkan submission paralel jika pemrosesan melibatkan event `click` vs `submit`!
  2. Bagaimana browser memperlakukan elemen input yang mendadak diberi atribut `disabled` saat fase serialisasi payload sedang berlangsung?
  3. Rancang arsitektur pencegahan berbasis HTML native murni dan API level platform (tanpa library pihak ketiga) yang menjamin *idempotency submission* di level browser engine!

### Skenario B: Silent Client-Side Validation Bypass pada E-Commerce Flash Sale
* **Kasus:** Platform e-commerce mendapati ribuan order saat *flash sale* lolos dengan nilai kuantitas melebihi batas inventaris (`max="2"` dijebol menjadi `max="999"`), meskipun validasi native HTML5 (`<input type="number" min="1" max="2" required>`) dan validasi JavaScript telah dipasang. Log web application firewall (WAF) menunjukkan request dikirim langsung dari browser resmi, bukan bot headless.
* **Pertanyaan Diagnostik:**
  1. Analisis tiga metode teknis bagaimana client-side declarative validation dapat dibypass secara instan langsung dari DevTools atau console pengguna tanpa perlu mematikan JavaScript secara total!
  2. Mengapa atribut `novalidate` pada tag `<form>` atau modifikasi atribut DOM via `setAttribute` dapat melumpuhkan seluruh barikade deklaratif yang sudah dibangun?
  3. Buat kontrak kerja sama struktural (*architectural contract*) antara representasi validasi HTML deklaratif di sisi frontend dengan subsistem schema parser di sisi backend API untuk memastikan *zero-trust constraint enforcement*!

### Skenario C: Regresi Aksesibilitas Total Akibat Re-arsitektur Custom Input
* **Kasus:** Tim Frontend Core melakukan re-arsitektur desain formulir enterprise berskala 100+ input dari input HTML native ke custom-built UI components berbasis `div[contenteditable="true"]` dan custom CSS demi tuntutan desain seragam lintas sistem operasi. Pasca rilis, departemen *Compliance & Legal* memberikan audit kegagalan total: Pengguna disabilitas tuna netra tidak dapat menyelesaikan formulir, autofill pengelola kata sandi perusahaan gagal beroperasi, dan virtual keyboard pada perangkat mobile tidak memunculkan layout angka/email yang sesuai.
* **Pertanyaan Diagnostik:**
  1. Petakan kerugian arsitektur struktural (*structural architectural loss*) yang terjadi pada *Accessibility Tree* saat elemen `<input type="email">` digantikan oleh elemen generik non-input!
  2. Jelaskan mengapa atribut `inputmode`, `type`, dan `autocomplete` tidak dapat direplikasi secara sempurna perilakunya pada elemen non-form controls meskipun menggunakan atribut ARIA (`role="textbox"`)!
  3. Bagaimana strategi refactoring sistematis untuk mengembalikan fondasi native HTML tanpa mengorbankan fleksibilitas kustomisasi UI/CSS modern?

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi Zero-Dependency Enterprise Form Architecture dengan Asynchronous Constraint Validation & Accessible Error Pipeline

#### Deskripsi Masalah
Banyak aplikasi modern mengorbankan performa browser dengan mengimpor pustaka form state berbasis JavaScript yang berat (seperti Formik, React Hook Form, atau Vuelidate) hanya untuk mengelola validasi dasar, state tracking, dan penanganan pesan kesalahan. Anda ditugaskan oleh *Principal Architect* untuk merancang fondasi formulir pendaftaran rekening bisnis enterprise yang sepenuhnya mengandalkan platform web native: memanfaatkan *Constraint Validation API*, Web Accessibility semantics, dan *Progressive Enhancement*, tanpa dependensi library eksternal.

#### Kebutuhan Fungsional & Spesifikasi Teknis
1. **Struktur Semantik & Progressive Enhancement:**
   * Formulir harus tetap dapat disubmit secara fungsional menggunakan native POST request jika JavaScript dinonaktifkan pada browser klien.
   * Field mencakup: Nama Perusahaan (`text`), Nomor Induk Berusaha (NIB) 13-digit (`text` dengan format angka kaku), Email Korporat (`email`), Dokumen Akta (`file` format PDF, max 5MB), dan Tombol Submit ganda: "Simpan Draf" (bypass validation) dan "Kirim Pendaftaran" (strict validation).
2. **Accessible Error Pipeline (WCAG 2.1 AA):**
   * Hubungkan setiap input secara programatis ke penampung pesan galat (*error container*) menggunakan kombinasi `aria-describedby` dan `aria-errormessage`.
   * Error state wajib dinamis: input harus memiliki atribut `aria-invalid="true"` hanya jika input tersebut tidak valid dan telah disentuh/diinteraksi oleh pengguna.
   * Gunakan `aria-live="polite"` pada *summary alert region* di bagian atas form yang merangkum galat secara komprehensif saat submission gagal.
3. **Dual-Layer Validation Integration:**
   * **Deklaratif Native:** Gunakan atribut `pattern`, `minlength`, `maxlength`, `required`, `accept`.
   * **Custom Complex Check:** Validasi NIB (Nomor Induk Berusaha) memerlukan kalkulasi algoritma checksum modulo-11 lokal via JavaScript sebelum mengizinkan submit, menggunakan antarmuka `setCustomValidity`.
   * Sinkronisasi visual: Gunakan CSS modern berbasis pseudo-class `:user-invalid` dan pastikan tidak ada indikator visual eror saat formulir pertama kali dimuat.
4. **Form Submission Override:**
   * Tombol "Simpan Draf" harus mengarahkan submission ke endpoint `/draft` dan mematikan seluruh validasi melalui atribut HTML tanpa bantuan skrip JS.
   * Tombol "Kirim Pendaftaran" harus mengeksekusi validasi ketat ke endpoint `/submit`.

#### Batasan Teknis (Constraints)
* **Zero Dependencies:** Dilarang menggunakan framework JS, compiler/bundler runtime, CSS framework, atau pustaka eksternal.
* **Engine Parity:** Wajib beroperasi identik pada engine Chromium (Blink), Firefox (Gecko), dan Safari (WebKit).
* **DOM Pollution Minimal:** Kode JavaScript tidak boleh menambahkan atribut custom non-standar ke elemen form selain standar W3C/WHATWG/ARIA.

#### Expected Output
1. **Markup HTML5 Semantik:** Dokumen formulir lengkap dengan deklarasi relasi aksesibilitas, fallback attributes, dan struktur elemen override.
2. **Cascading Style Sheet (CSS):** Logika styling murni state-driven yang memisahkan status `:focus`, `:user-invalid`, dan visualisasi pesan eror yang tersembunyi hingga kondisi validitas terpenuhi.
3. **Controller JavaScript Ringan (< 2KB):** Script untuk validasi checksum modulo-11 NIB, pembaruan atribut ARIA secara reaktif, pengalihan fokus (*focus management*) ke input pertama yang invalid saat submit dicegah, serta pencegahan transmisi ganda.

---

## 5. Knowledge Check & Checklist

Verifikasi kesiapan pemahaman teknis sebelum melanjutkan ke modul arsitektur berikutnya.

### Saya harus memahami:
- [ ] Detail siklus Form Submission Algorithm menurut spesifikasi WHATWG, mulai dari penekanan tombol submit hingga konstruksi payload HTTP.
- [ ] Perbedaan fundamental representasi biner dan tekstual antara `multipart/form-data` dan `application/x-www-form-urlencoded`.
- [ ] Seluruh anggota properti boolean dari antarmuka `ValidityState` serta kondisi yang memicu aktivasinya.
- [ ] Mekanisme pemetaan relasi antar node DOM form control ke Accessibility Tree melalui `label[for]`, `aria-labelledby`, `aria-describedby`, dan `aria-errormessage`.
- [ ] Hierarki kekhususan (*specificity cascade*) antara atribut level `<form>` vs form-associated overrides (`formaction`, `formnovalidate`, dll.).
- [ ] Siklus kerja internal browser saat mengevaluasi pseudo-class `:user-invalid` dan `:user-valid` dibandingkan `:invalid` / `:valid`.
- [ ] Batasan keamanan dari browser autofill heuristics serta strategi mitigasi terhadap skenario eksfiltrasi data melalui hidden fields.

### Saya tidak perlu menghafal:
- [ ] Pola Regular Expression (Regex) kompleks untuk spesifikasi email standar RFC 5322 (cukup pahami batas kemampuan validasi native `type="email"`).
- [ ] Seluruh daftar MIME types standar di internet (cukup pahami cara kerja parsing ekspresi atribut `accept`).
- [ ] Implementasi internal kode sumber C++ browser engine (Blink/WebKit) dalam mengeksekusi multipart parsing.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi form HTML kompleks multi-partisipan yang tetap berfungsi secara degradasi anggun (*graceful degradation*) tanpa JavaScript.
- [ ] Menulis modul validasi JavaScript zero-dependency yang memanipulasi antarmuka `setCustomValidity` secara aman tanpa menimbulkan *infinite invalid loop*.
- [ ] Merancang arsitektur formulir yang lolos uji pembaca layar (*screen reader audit*) dengan fokus otomatis pada elemen invalid pertama secara berurutan.
- [ ] Melakukan debugging dan isolasi insiden double submission serta memverifikasi payload byte stream form via Network DevTools.
- [ ] Mengintegrasikan Web Components kustom ke dalam form native menggunakan API `ElementInternals` dan `formAssociated`.