# BAB 01 — Web Platform Internals, DOM Rendering, & Modern TypeScript Core — Quiz & Chapter Challenge

---

## 📝 Bagian 1: Ujian Konsep & Pemahaman Teknis (10 Soal Pilihan Ganda)

---

### Soal 1

Perhatikan kode berikut:

```javascript
console.log('start');

setTimeout(() => console.log('timeout'), 0);

Promise.resolve().then(() => console.log('promise'));

queueMicrotask(() => console.log('microtask'));

console.log('end');
```

Apa urutan output yang **tepat** dari kode di atas?

**A.** `start` → `end` → `timeout` → `promise` → `microtask`
**B.** `start` → `end` → `promise` → `microtask` → `timeout`
**C.** `start` → `end` → `microtask` → `promise` → `timeout`
**D.** `start` → `promise` → `microtask` → `end` → `timeout`

**✅ Kunci Jawaban: B**

**📖 Penjelasan Mendalam:**

JavaScript menggunakan model **Event Loop** dengan dua jenis antrian tugas:

1. **Call Stack** — Eksekusi synchronous berjalan pertama kali. `console.log('start')` dan `console.log('end')` langsung masuk ke call stack dan dieksekusi.

2. **Microtask Queue** — Memiliki **prioritas lebih tinggi** dari Macrotask Queue. Antrian ini dikuras **habis** sebelum Event Loop mengambil task berikutnya dari Macrotask Queue. `Promise.resolve().then(...)` dan `queueMicrotask(...)` keduanya mendaftarkan microtask. Urutan eksekusi microtask mengikuti urutan pendaftaran: `promise` terdaftar lebih dulu, lalu `microtask`.

3. **Macrotask Queue (Task Queue)** — `setTimeout` dengan delay `0` mendaftarkan callback ke Macrotask Queue. Meskipun delay-nya nol, ia tetap harus menunggu seluruh microtask queue habis terlebih dahulu.

**Mengapa pilihan lain salah:**
- **A** salah karena memposisikan `timeout` sebelum `promise` dan `microtask`, mengabaikan prioritas microtask queue.
- **C** salah karena membalik urutan `microtask` dan `promise`; `Promise.then` didaftarkan lebih dulu sehingga dieksekusi lebih dulu.
- **D** salah karena `promise` dan `microtask` tidak bisa berjalan sebelum synchronous code selesai; call stack harus kosong terlebih dahulu.

---

### Soal 2

Seorang developer menemukan bahwa aplikasinya mengalami **layout thrashing** yang signifikan. Berikut adalah kode penyebabnya:

```javascript
const boxes = document.querySelectorAll('.box');

boxes.forEach(box => {
  const height = box.offsetHeight; // Read
  box.style.height = height * 2 + 'px'; // Write
});
```

Manakah refactor yang **paling efektif** untuk menghilangkan layout thrashing?

**A.**
```javascript
boxes.forEach(box => {
  requestAnimationFrame(() => {
    const height = box.offsetHeight;
    box.style.height = height * 2 + 'px';
  });
});
```

**B.**
```javascript
const heights = Array.from(boxes).map(box => box.offsetHeight); // Batch Read
heights.forEach((height, i) => {
  boxes[i].style.height = height * 2 + 'px'; // Batch Write
});
```

**C.**
```javascript
boxes.forEach(box => {
  setTimeout(() => {
    const height = box.offsetHeight;
    box.style.height = height * 2 + 'px';
  }, 0);
});
```

**D.**
```javascript
boxes.forEach(box => {
  const height = box.getBoundingClientRect().height;
  box.style.height = height * 2 + 'px';
});
```

**✅ Kunci Jawaban: B**

**📖 Penjelasan Mendalam:**

**Layout thrashing** terjadi ketika browser dipaksa melakukan **reflow (layout recalculation)** berulang kali dalam satu frame karena pola Read-Write yang bergantian. Setiap kali kode membaca properti geometri (seperti `offsetHeight`) setelah melakukan perubahan style, browser harus menyelesaikan layout yang tertunda terlebih dahulu untuk memberikan nilai yang akurat.

**Pilihan B benar** karena menerapkan pola **Batch Read → Batch Write**:
- Fase pertama: Semua nilai `offsetHeight` dibaca sekaligus. Browser hanya perlu melakukan layout sekali (atau tidak sama sekali jika layout belum dirty).
- Fase kedua: Semua perubahan style diterapkan sekaligus. Browser menandai layout sebagai dirty sekali dan akan menghitungnya di akhir frame.

**Mengapa pilihan lain salah:**
- **A** salah karena `requestAnimationFrame` hanya memindahkan eksekusi ke frame berikutnya, tetapi pola Read-Write bergantian di dalam loop tetap ada, sehingga thrashing tetap terjadi di setiap frame.
- **C** salah karena `setTimeout` memiliki masalah yang sama dengan pilihan A; pola interleave Read-Write tidak dihilangkan, hanya ditunda.
- **D** salah karena `getBoundingClientRect()` juga merupakan **forced synchronous layout** sama seperti `offsetHeight`. Menggantinya tidak menyelesaikan masalah thrashing karena pola Read-Write masih bergantian dalam satu iterasi loop.

---

### Soal 3

Perhatikan definisi TypeScript berikut:

```typescript
type DeepReadonly<T> = {
  readonly [K in keyof T]: T[K] extends object ? DeepReadonly<T[K]> : T[K];
};

interface Config {
  server: {
    host: string;
    port: number;
    tls: {
      enabled: boolean;
      cert: string;
    };
  };
  retries: number;
}

const config: DeepReadonly<Config> = {
  server: { host: 'localhost', port: 3000, tls: { enabled: true, cert: 'cert.pem' } },
  retries: 3,
};

// Manakah operasi berikut yang akan menghasilkan ERROR kompilasi TypeScript?
```

**A.** `config.retries`
**B.** `config.server.host`
**C.** `config.server.tls.enabled = false;`
**D.** `const host = config.server.host;`

**✅ Kunci Jawaban: C**

**📖 Penjelasan Mendalam:**

`DeepReadonly<T>` adalah **recursive mapped type** yang menerapkan modifier `readonly` secara rekursif ke semua properti nested. Cara kerjanya:

1. Untuk setiap key `K` di `T`, jika nilainya adalah `object`, terapkan `DeepReadonly` secara rekursif.
2. Jika bukan `object`, gunakan tipe aslinya.

Hasilnya, `config` memiliki struktur di mana **setiap properti di semua level kedalaman bersifat readonly**, termasuk `config.server.tls.enabled`.

**Pilihan C benar (menghasilkan error)** karena mencoba melakukan assignment `config.server.tls.enabled = false`. TypeScript akan mengeluarkan error: *"Cannot assign to 'enabled' because it is a read-only property."*

**Mengapa pilihan lain salah (tidak menghasilkan error):**
- **A** hanya membaca `config.retries` — operasi read yang valid.
- **B** hanya membaca `config.server.host` — operasi read yang valid.
- **D** hanya membaca dan menyalin nilai ke variabel baru — operasi read yang valid; variabel `host` sendiri bukan readonly.

**Catatan penting:** Tanpa `DeepReadonly`, `readonly` biasa hanya melindungi satu level. `config.server` tidak bisa di-reassign, tetapi `config.server.tls.enabled` masih bisa diubah karena `readonly` tidak bersifat deep secara default.

---

### Soal 4

Browser sedang melakukan **rendering pipeline**. Setelah tahap **Style Calculation** selesai, tahap apa yang terjadi berikutnya dan kapan sebuah perubahan CSS akan **melewati (skip)** tahap Layout?

**A.** Tahap berikutnya adalah **Paint**. Perubahan `color` akan melewati Layout karena tidak mengubah geometri elemen.

**B.** Tahap berikutnya adalah **Layout**. Tidak ada perubahan CSS yang bisa melewati Layout; semua perubahan harus melalui seluruh pipeline.

**C.** Tahap berikutnya adalah **Layout**. Perubahan properti seperti `transform` dan `opacity` dapat melewati Layout **dan** Paint karena diproses langsung oleh Compositor Thread.

**D.** Tahap berikutnya adalah **Compositing**. Perubahan `width` akan melewati Layout karena browser sudah menyimpan cache ukuran elemen.

**✅ Kunci Jawaban: C**

**📖 Penjelasan Mendalam:**

**Rendering Pipeline Browser** secara lengkap adalah:
```
JavaScript → Style → Layout → Paint → Composite
```

Setelah **Style Calculation**, tahap berikutnya adalah **Layout** (juga disebut Reflow). Namun, tidak semua perubahan CSS harus melalui seluruh pipeline:

**Tiga jalur rendering:**

1. **Full Pipeline (JS → Style → Layout → Paint → Composite):** Terjadi saat properti yang mempengaruhi geometri berubah, seperti `width`, `height`, `margin`, `padding`, `font-size`. Paling mahal.

2. **Skip Layout (JS → Style → Paint → Composite):** Terjadi saat properti yang tidak mempengaruhi geometri berubah, seperti `color`, `background-color`, `border-color`. Layout di-skip karena posisi dan ukuran elemen tidak berubah.

3. **Skip Layout & Paint (JS → Style → Composite):** Terjadi untuk properti `transform` dan `opacity`. Kedua properti ini diproses oleh **Compositor Thread** secara terpisah dari Main Thread, sehingga animasi yang hanya menggunakan `transform` dan `opacity` tidak memblokir Main Thread dan menghasilkan performa 60fps yang konsisten.

**Mengapa pilihan lain salah:**
- **A** salah pada tahap berikutnya; setelah Style adalah Layout, bukan Paint. Meskipun benar bahwa `color` melewati Layout, tahap awalnya salah.
- **B** salah karena klaim bahwa tidak ada CSS yang bisa melewati Layout adalah keliru; `transform` dan `opacity` adalah contoh nyata.
- **D** salah pada tahap berikutnya (setelah Style bukan langsung Composite) dan salah pada klaim tentang `width` (ia tetap memerlukan Layout).

---

### Soal 5

Perhatikan kode TypeScript berikut yang menggunakan **Conditional Types** dan **infer**:

```typescript
type UnpackPromise<T> = T extends Promise<infer U> ? U : T;
type UnpackArray<T> = T extends Array<infer U> ? U : T;

type A = UnpackPromise<Promise<string>>;
type B = UnpackPromise<number>;
type C = UnpackArray<string[]>;
type D = UnpackArray<UnpackPromise<Promise<boolean[]>>>;
```

Manakah pernyataan yang **benar** tentang tipe `A`, `B`, `C`, dan `D`?

**A.** `A = string`, `B = never`, `C = string`, `D = boolean`
**B.** `A = string`, `B = number`, `C = string`, `D = boolean`
**C.** `A = Promise<string>`, `B = number`, `C = string[]`, `D = boolean[]`
**D.** `A = string`, `B = number`, `C = string[]`, `D = boolean`

**✅ Kunci Jawaban: B**

**📖 Penjelasan Mendalam:**

Mari kita trace setiap tipe secara manual:

**`type A = UnpackPromise<Promise<string>>`**
- `Promise<string> extends Promise<infer U>` → **true**, `U` diinfer sebagai `string`
- Hasil: `A = string` ✓

**`type B = UnpackPromise<number>`**
- `number extends Promise<infer U>` → **false**, `number` bukan Promise
- Karena false, kembalikan `T` yaitu `number`
- Hasil: `B = number` ✓

**`type C = UnpackArray<string[]>`**
- `string[] extends Array<infer U>` → **true**, `U` diinfer sebagai `string`
- Hasil: `C = string` ✓

**`type D = UnpackArray<UnpackPromise<Promise<boolean[]>>>`**
- Pertama evaluasi inner: `UnpackPromise<Promise<boolean[]>>`
  - `Promise<boolean[]> extends Promise<infer U>` → true, `U = boolean[]`
  - Hasil inner: `boolean[]`
- Kemudian: `UnpackArray<boolean[]>`
  - `boolean[] extends Array<infer U>` → true, `U = boolean`
  - Hasil: `D = boolean` ✓

**Mengapa pilihan lain salah:**
- **A** salah karena `B = never` adalah keliru; ketika kondisi false, `UnpackPromise` mengembalikan `T` (yaitu `number`), bukan `never`.
- **C** salah karena `A = Promise<string>` keliru (seharusnya `string`) dan `C = string[]` keliru (seharusnya `string`).
- **D** salah karena `C = string[]` keliru; `UnpackArray` mengekstrak elemen array, hasilnya `string` bukan `string[]`.

---

### Soal 6

Sebuah tim menggunakan **Virtual DOM diffing** di React. Mereka memiliki komponen list yang me-render 1000 item. Mereka menghapus item pertama dari array tanpa menggunakan `key` prop. Apa yang terjadi pada proses reconciliation?

```jsx
// Tanpa key
{items.map(item => <ItemComponent data={item} />)}

// Dengan key
{items.map(item => <ItemComponent key={item.id} data={item} />)}
```

**A.** Tanpa `key`, React akan melakukan unmount dan remount semua 1000 komponen karena tidak bisa mengidentifikasi perubahan.

**B.** Tanpa `key`, React menggunakan **index-based diffing**: ia membandingkan elemen berdasarkan posisi. Menghapus item pertama menyebabkan React mengupdate props **999 komponen** yang tersisa karena
