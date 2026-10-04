# BAB-08-Enterprise-Form-Systems-dan-Mutation-Workflows: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi komprehensif untuk menguji pemahaman arsitektur form skala enterprise, integrasi schema validation tingkat lanjut, orkestrasi mutasi data asinkron, hingga penanganan konkurensi serta optimasi performa form pada ekosistem React.

---

## Bagian 1: Basic Questions (Konsep Fundamental)

### Soal 1.1: Controlled vs. Uncontrolled Form Architecture
**Pertanyaan:**  
Jelaskan perbedaan mendasar antara pendekatan *Controlled Components* (`useState`) dan *Uncontrolled Components* berbasis refs (`useRef` / React Hook Form) dalam konteks siklus re-render React. Mengapa enterprise dashboard dengan puluhan input field lebih memilih arsitektur berbasis uncontrolled refs?

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

- **Controlled Components:** State input disimpan langsung dalam React component state (`useState`). Setiap kali pengguna mengetik satu karakter, terjadi event trigger `onChange` yang mengeksekusi `setState`, memicu proses rekonsiliasi dan re-render seluruh subtree komponen bersangkutan (kecuali diisolasi secara eksplisit). Pada form berisi puluhan field, latency frame budget 16ms untuk 60fps dapat terlampaui (mengakibatkan typing lag).
- **Uncontrolled Components (React Hook Form):** Input DOM elemen dikelola langsung oleh native browser DOM melalui mutable reference (`ref`). Komponen form utama tidak melakukan re-render saat nilai field berubah. State internal hanya dilacak di level native input event listener dan disinkronkan hanya ketika ada kebutuhan validasi, sub-komponen isolasi terdaftar, atau saat `handleSubmit` dipicu.
- **Kesimpulan:** Uncontrolled components mengeliminasi rendering overhead overhead `O(N)` di mana `N` adalah jumlah field form, menjaga performa tetap `O(1)` per keystroke.
</details>

---

### Soal 1.2: Peran Validasi Skema Berbasis Zod Resolver
**Pertanyaan:**  
Mengapa arsitektur form modern memisahkan logika validasi ke dalam *Single Source of Truth* eksternal seperti Zod schema resolver (`@hookform/resolvers/zod`), alih-alih menaruh inline validation logic pada masing-masing field?

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

- **Separation of Concerns:** Memisahkan representasi UI dari aturan bisnis domain. Komponen input hanya bertanggung jawab atas rendering dan interaktivitas, bukan logika domain kompleks.
- **Type Inference:** Skema Zod dapat menghasilkan TypeScript interface secara otomatis melalui `z.infer<typeof schema>`, mencegah duplikasi definisi tipe antara antarmuka API, form input, dan database schema.
- **Cross-Field Validation:** Validasi yang melibatkan dependensi multi-field (misalnya mencocokkan `password` dan `confirmPassword`, atau validasi kondisional tanggal) menjadi tersentralisasi di method `.refine()` atau `.superRefine()`.
- **Code Sharing:** Skema yang sama dapat di-share secara isomorfik antara server-side endpoint handler (Next.js server action / Node API) dan client-side form validator.
</details>

---

### Soal 1.3: Siklus State Form (`isDirty`, `isValid`, `isSubmitting`)
**Pertanyaan:**  
Bagaimana mekanisme kalkulasi state `isDirty` pada React Hook Form, dan mengapa pemanggilan `reset(values)` penting dilakukan setelah mutasi backend berhasil alih-alih hanya mengosongkan state secara manual?

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

- **Kalkulasi `isDirty`:** Dihitung dengan melakukan deep comparison antara nilai form saat ini (`currentValues`) terhadap baseline `defaultValues` yang didaftarkan saat inisialisasi hook.
- **Pentingnya `reset(newValues)`:** Mengosongkan field secara manual hanya akan mengubah `currentValues` menjadi kosong, tetapi baseline `defaultValues` tetap tidak berubah sehingga `isDirty` tetap bernilai `true`. Memanggil `reset(newValues)` akan menetapkan baseline `defaultValues` baru sesuai respons data mutasi dari server, mengembalikan status `isDirty` ke `false`, dan mereset penanda flag error/touched.
</details>

---

### Soal 1.4: Optimistic UI Updates & Error Rollback
**Pertanyaan:**  
Dalam orkestrasi mutasi asinkron (misalnya menggunakan TanStack Query), apa peran method `cancelQueries`, snapshot data konteks, dan `rollback` pada siklus hidup `onMutate`, `onError`, dan `onSettled`?

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

1. **`onMutate`:**
   - Mengeksekusi `await queryClient.cancelQueries({ queryKey })` untuk membatalkan refetching query yang sedang berjalan di latar belakang agar tidak menimpa state optimistik sementara.
   - Mengambil snapshot cache sebelum mutasi melalui `queryClient.getQueryData(queryKey)`.
   - Menginjeksikan payload optimistik ke cache secara sinkron (`queryClient.setQueryData`).
   - Mengembalikan context object yang menyimpan snapshot data original.
2. **`onError`:**
   - Menerima context snapshot yang dikembalikan oleh `onMutate`.
   - Melakukan rollback state cache ke snapshot original menggunakan `queryClient.setQueryData(queryKey, context.previousData)` agar UI kembali konsisten dengan database.
3. **`onSettled`:**
   - Mengeksekusi `queryClient.invalidateQueries({ queryKey })` terlepas dari hasil mutasi (sukses maupun gagal) untuk memastikan sinkronisasi final dengan server truth.
</details>

---

### Soal 1.5: Dynamic Discriminated Unions pada Form
**Pertanyaan:**  
Apa keuntungan menggunakan discriminated union pada Zod schema untuk formulir yang memiliki variasi metode (misalnya metode pembayaran: `TRANSFER_BANK` dengan field `bankName` & `accountNumber` vs `CREDIT_CARD` dengan field `cardNumber`, `cvv`, `expiry`)?

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

- **Strict Type Narrowing:** TypeScript dan Zod dapat mempersempit validasi secara eksklusif berdasarkan nilai literal pembeda (`type` atau `discriminator`).
- **Pembersihan Payload Otomatis:** Menghindari pengiriman payload "hantu" (ghost fields) di mana data kartu kredit terkirim padahal metode pembayaran yang dipilih pengguna adalah transfer bank.
- **Validasi Spesifik Konteks:** Field validasi kartu kredit (`cvv` 3 digit) tidak akan dievaluasi atau memunculkan error validasi palsu jika tipe transaksi aktif adalah transfer bank.
</details>

---

## Bagian 2: Intermediate Questions (Deep-Dive & Arsitektur)

### Soal 2.1: Isolasi Re-rendering Menggunakan `useWatch` dan `Controller`
**Pertanyaan:**  
Pada form dengan 100 field, jika satu field dropdown `country` menentukan opsi pada field `city`, bagaimana strategi arsitektur menggunakan React Hook Form untuk mencegah seluruh 100 field me-render ulang ketika `country` berubah?

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

- Jangan gunakan `watch('country')` di root component form, karena pemanggilan `watch` di root akan memaksa root component re-render setiap kali nilai field berubah, memicu render cascade ke seluruh child inputs.
- Gunakan hook `useWatch({ control, name: 'country' })` secara eksklusif di dalam sub-komponen terisolasi `<CitySelectField />`.
- Dengan memindahkan `useWatch` ke sub-komponen, boundary re-render terkurung hanya pada sub-komponen kota tersebut dan elemen input lainnya tetap diam tanpa rendering siklus baru.
</details>

---

### Soal 2.2: Race Condition pada Auto-save & Debounced Mutation
**Pertanyaan:**  
Sebuah form dokumen memiliki fitur auto-save dengan interval debounced typing 500ms. Jika pengguna mengetik revisi A, lalu dengan cepat mengetik revisi B, namun request HTTP revisi A mengalami latency network tinggi dan selesai *setelah* revisi B diterima server, bagaimana cara mengamankan integritas data dari client-side?

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

1. **AbortController:** Setiap kali request mutasi auto-save baru dipicu oleh debounced event, batalkan request HTTP sebelumnya yang masih berjalan menggunakan `abortController.abort()`.
2. **Sequential Mutation Queue / Concurrency Control:** Gunakan queue mutasi serial atau mekanisme versioning (misal `versionId` incremental atau timestamp ISO).
3. **Optimistic Locking:** Kirim version token saat ini ke backend. Backend menolak update jika version token yang dikirim client lebih usang daripada version token dokumen di database.
</details>

---

### Soal 2.3: Performa dan Re-indexing Dynamic `useFieldArray`
**Pertanyaan:**  
Mengapa kita dilarang keras menggunakan array index (`index`) sebagai React `key` saat me-render elemen dari `useFieldArray`, dan bagaimana cara kerja properti `field.id` bawaan RHF?

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

- Jika array index digunakan sebagai `key`, saat operasi penghapusan, penyisipan di tengah, atau drag-and-drop reordering terjadi, React Virtual DOM mendeteksi posisi index bukan identitas elemen sesungguhnya. Akibatnya, uncontrolled DOM input state internal (seperti focus, text selection, input cursor, atau dirty status) tertinggal pada node yang salah.
- `useFieldArray` membangkitkan UUID internal sintetis yang disimpan pada `field.id`. Properti `field.id` ini persisten dan terikat erat pada item tertentu sepanjang siklus hidup entri tersebut, terlepas dari pergeseran posisinya di dalam array list.
</details>

---

### Soal 2.4: Multi-Step Wizard: State Management & Draft Persistence
**Pertanyaan:**  
Bandingkan trade-off penyimpanan state wizard form bertingkat antara: (A) URL Search Parameters, (B) Global Store (Zustand) + Local Storage, dan (C) Server-side Draft API. Kapan masing-masing pendekatan wajib digunakan?

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

| Strategi | Kelebihan | Kekurangan | Kasus Penggunaan Ideal |
|---|---|---|---|
| **URL Search Params** | Shareable state, mendukung browser back/forward navigation secara native, deep-linking. | Kapasitas payload terbatas (panjang URL), tidak aman untuk data sensitif (PII/kredensial). | Filter form publik, booking flow sederhana, search wizard. |
| **Zustand + Local Storage** | Kapasitas penyimpanan besar (hingga ~5MB), akses instan offline, performa cepat tanpa network roundtrip. | Data terisolasi pada satu device/browser, rentan terhadap data drift jika skema berubah. | Onboarding personal, pengaturan preferensi, draft form yang tidak sensitif. |
| **Server-side Draft API** | Cross-device continuity (user bisa mulai di web dan lanjut di mobile app), audit logging terpusat, aman untuk PII. | Memerlukan latency HTTP call, menambah beban database, memerlukan strategi cleanup draft kadaluwarsa. | B2B onboarding, aplikasi kredit finansial, klaim asuransi perusahaan. |
</details>

---

### Soal 2.5: Idempotency Key pada Transaksi Finansial Form
**Pertanyaan:**  
Jelaskan bagaimana implementasi *Idempotency Key* pada lapisan client-side mutation form untuk menjamin bahwa koneksi jaringan yang flapping/terputus di tengah proses tidak menyebabkan eksekusi ganda pada endpoint pembayaran backend!

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

- **Generasi Kunci:** Saat form submit diinisiasi untuk pertama kali, client membangkitkan UUID v4 unik yang disebut `Idempotency-Key` dan menyimpannya di context mutasi lokal form.
- **Pengiriman Header:** UUID tersebut dikirimkan via HTTP header kustom (`X-Idempotency-Key: <UUID>`).
- **Mekanisme Retry:** Jika terjadi network timeout atau kegagalan koneksi di mana client tidak menerima respons status HTTP, client melakukan retry dengan mengirim ulang payload beserta `Idempotency-Key` yang **persis sama**.
- **Backend Recognition:** Backend mendeteksi jika idempotency key tersebut sudah pernah diproses atau sedang berada dalam antrean pemrosesan, backend mengembalikan status cached respons transaksi tanpa mendebit ulang saldo pengguna.
</details>

---

## Bagian 3: Skenario Kasus Nyata Produksi (Production Scenarios)

### Skenario 3.1: "Ghost Submissions" & Double Invoicing pada Flash-Sale
**Konteks Masalah:**  
Sebuah platform checkout tiket konser mengalami insiden di mana puluhan pengguna menerima tagihan ganda untuk satu pesanan yang sama saat server mengalami response lag sebesar 4.5 detik. Kode tombol submit hanya menonaktifkan tombol secara visual menggunakan class CSS, dan mutasi dijalankan via `fetch` standar di dalam event handler `onSubmit`.

**Tantangan Arsitektur:**
1. Analisis titik kegagalan (failure points) dari implementasi eksisting.
2. Rancang solusi arsitektur form yang resisten terhadap multiple rapid clicks, network jitter, dan browser page refresh.

<details>
<summary>Solusi Rekayasa Sistem</summary>

1. **Root Cause Analysis:**
   - Menonaktifkan tombol hanya via visual styling (CSS class) tetap memungkinkan event dispatch `Enter` key dari keyboard atau event firing ganda.
   - Tidak adanya status disabling fisik (`disabled={isSubmitting}`) pada elemen HTML button.
   - Ketiadaan idempotency contract antara client dan backend payment gateway.

2. **Perbaikan Arsitektur:**
   - **Form State Lock:** Manfaatkan `formState.isSubmitting` dari RHF untuk mengunci field dan tombol secara fisik:
     ```tsx
     <button type="submit" disabled={isSubmitting || !isValid}>
       {isSubmitting ? <Spinner /> : "Konfirmasi Pembayaran"}
     </button>
     ```
   - **AbortController & Mutex Flag:** Bungkus mutasi dalam mutation hook dengan pembatalan request berulang atau menggunakan mutex state ref (`isSubmittingRef.current = true`).
   - **Client-Generated Idempotency Header:**
     ```typescript
     const idempotencyKey = useMemo(() => crypto.randomUUID(), [orderId]);
     await apiClient.post('/api/checkout', payload, {
       headers: { 'Idempotency-Key': idempotencyKey }
     });
     ```
</details>

---

### Skenario 3.2: Input Latency 400ms pada B2B Compliance Dynamic Form
**Konteks Masalah:**  
Sebuah form audit perizinan legal B2B memiliki 150 input fields, 8 dynamic field arrays untuk daftar direktur dan dokumen legal, serta validasi skema menyeluruh. Pengguna mengeluhkan bahwa saat mengetik di input nama perusahaan, terdapat lag parah (~400ms) di mana kursor macet dan UI terasa membeku. Profiling React DevTools menunjukkan seluruh 150 input komponen melakukan re-render setiap kali 1 karakter diketik.

**Tantangan Arsitektur:**
Identifikasi penyebab render waterfall tersebut dan lakukan rekayasa performa agar rendering latency berada di bawah batas 16ms (60fps).

<details>
<summary>Solusi Rekayasa Sistem</summary>

1. **Investigasi Masalah:**
   - Ditemukan adanya pemanggilan `const values = watch()` di level root `<ComplianceFormContainer />`.
   - Seluruh sub-input menerima props baru dari root object `values` sehingga membatalkan optimasi memoization.
   - Validasi skema Zod diatur dengan mode default `mode: "onChange"` pada seluruh form root.

2. **Langkah Optimasi:**
   - **Ubah Mode Validasi:** Ubah mode validasi ke `mode: "onBlur"` atau `mode: "onSubmit"`, sehingga Zod validation run tidak dieksekusi pada setiap keystroke melainkan saat pengguna meninggalkan field.
   - **Hapus Global Watch:** Ganti global `watch()` dengan `useWatch({ control, name: "specificField" })` hanya pada komponen yang benar-benar membutuhkan data tersebut untuk visual toggling.
   - **Gunakan `<Controller />` dengan Komponen Termoisolasi:** Bungkus input kompleks dengan `React.memo` dan serahkan interaksi ke React Hook Form Controller:
     ```tsx
     const MemoizedTextInput = React.memo(({ control, name, label }) => {
       return (
         <Controller
           name={name}
           control={control}
           render={({ field, fieldState: { error } }) => (
             <div>
               <label>{label}</label>
               <input {...field} />
               {error && <span>{error.message}</span>}
             </div>
           )}
         />
       );
     });
     ```
   - **Hasil:** Profiling waktu render per keystroke turun dari ~400ms menjadi ~4ms.
</details>

---

### Skenario 3.3: Multi-Tab Stale Mutation Concurrency
**Konteks Masalah:**  
Seorang operator procurement membuka form pengadaan barang di Tab A browser, lalu membuka form pengadaan yang sama di Tab B untuk memeriksa spesifikasi. Operator mengubah data vendor di Tab B dan menyimpan perubahan. Satu jam kemudian, operator kembali ke Tab A yang masih menampilkan data vendor lama, lalu menekan tombol "Submit Persetujuan", yang secara tidak sengaja menimpa perubahan dari Tab B dengan data usang.

**Tantangan Arsitektur:**
Bagaimana mendeteksi konflik konkurensi data sebelum mutasi dieksekusi dan menyajikan resolusi konflik interaktif kepada pengguna?

<details>
<summary>Solusi Rekayasa Sistem</summary>

1. **Optimistic Locking via Entity Version / ETag:**
   - Form menerima metadata `updatedAt` atau `version: 3` saat pertama kali di-fetch.
   - Payload mutasi wajib menyertakan `{ id, version: 3, ...formPayload }`.
2. **Backend Contract:**
   - Backend memverifikasi: `if (incoming.version !== currentDb.version) throw new ConflictException(409, latestData)`.
3. **Client-Side Conflict Resolution UI:**
   - Mutation hook menangkap error status HTTP 409 (Conflict).
   - Dialog "Konflik Data Terdeteksi" ditampilkan ke pengguna, menampilkan perbandingan side-by-side: *Data Versi Anda (Tab A)* vs *Data Versi Server Terkini (Tab B)*.
   - Pengguna diberikan dua opsi: "Paksa Timpa (Overwrite)" atau "Muat Data Terbaru & Gabungkan (Merge)".
</details>

---

## Bagian 4: Practical Chapter Challenge

### Tantangan: "Enterprise Batch Transaction & Settlement Ledger"

Anda ditugaskan membangun arsitektur form entri transaksi akuntansi enterprise dengan spesifikasi ketat berikut:

#### 1. Persyaratan Fungsional
1. **Dynamic Split Entries:** Form mendukung minimal 2 baris entri jurnal (Debit dan Credit) menggunakan `useFieldArray`.
2. **Double-Entry Balance Constraint:** Total nilai `Debit` harus sama persis dengan total nilai `Credit`. Validasi skema harus menampilkan pesan error terpusat: *"Total Debit dan Credit harus seimbang (Selisih: Rp X)"*.
3. **Tax & Currency Precision:** Input nominal harus menggunakan format mata uang integer dalam satuan sen (cents/satuan terkecil) untuk mencegah floating-point precision error di JavaScript.
4. **Draft Auto-save:** Sinkronisasi draft lokal ke `IndexedDB` atau `localStorage` setiap 1000ms jika form berstatus `isDirty`, dan tampilkan indikator visual: *"Draft tersimpan otomatis pada HH:mm:ss"*.
5. **Server Error Mapping:** Jika backend mengembalikan respons 422 Unprocessable Entity dengan format:
   ```json
   {
     "errors": [
       { "field": "entries.2.accountNumber", "code": "ACCOUNT_FROZEN", "message": "Rekening dibekukan oleh kepatuhan." }
     ]
   }
   ```
   Form harus secara otomatis memetakan pesan error tersebut ke field input bersangkutan menggunakan `setError` RHF.

#### 2. Kriteria Penerimaan Teknis (Rubrik Penilaian)
- [ ] **Validasi Skema:** Menggunakan Zod `superRefine` untuk kalkulasi kesetaraan total Debit vs Credit.
- [ ] **Optimasi Performa:** Render field array tidak memicu re-render pada header ledger info (Nomor Dokumen, Tanggal Transaksi).
- [ ] **Type-Safe:** TypeScript strict mode, 0 lint error, tidak ada penggunaan tipe `any`.
- [ ] **Penanganan Mutasi:** Integrasi tombol submit dengan status loading, disability management, dan auto rollback saat server error.

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan daftar periksa berikut untuk mengukur kesiapan Anda sebelum melangkah ke implementasi kode riil:

- [ ] Saya memahami mengapa `useRef` dan arsitektur *uncontrolled* pada form libraries memberikan keunggulan performa mutlak dibandingkan `useState` per input.
- [ ] Saya mampu mendefinisikan skema Zod multi-kondisional menggunakan `z.discriminatedUnion`, `refine`, dan `superRefine`.
- [ ] Saya memahami siklus hidup mutasi asinkron: `onMutate` (optimistic update), `onError` (rollback context snapshot), dan `onSettled` (invalidation).
- [ ] Saya menguasai penggunaan `useWatch` dan `useController` untuk membatasi re-render cascade pada form berskala besar (>50 field).
- [ ] Saya memahami penggunaan UUID sintetis pada `useFieldArray` (`field.id`) vs array index dalam menjaga identitas state komponen DOM.
- [ ] Saya memahami arsitektur idempotensi (Idempotency Key) untuk mencegah risiko duplikasi transaksi finansial pada kondisi koneksi flappy.
- [ ] Saya memahami mitigasi race condition dan konflik multi-tab menggunakan Optimistic Locking (ETag / versioning integer).
