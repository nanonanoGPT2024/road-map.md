## SEKSI 01 — IDENTITAS MODUL

* **Jalur Pembelajaran**: Frontend Development (Beginner)
* **Kategori**: 01-Core-Foundations
* **Bab**: 08 — JavaScript Asinkron, Web API & Integrasi REST
* **Modul**: 01 — Eksekusi Asinkron, Event Loop, Fetch API, dan Konsumsi RESTful Service
* **Prasyarat Pengetahuan**: 
  * Sintaks dasar JavaScript modern (ES6+): arrow functions, destructuring, modules.
  * DOM Manipulation: seleksi elemen, manipulasi atribut/konten, penanganan event.
  * Protokol Jaringan Dasar: konsep Client-Server, URL, dan format data JSON.
* **Estimasi Waktu Pengerjaan**: 8–10 jam pembelajaran terpandu dan praktik mandiri.
* **Tingkat Kesulitan**: Intermediate (Tingkat Menengah untuk Pemula).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Memprediksi Alur Eksekusi**: Menjelaskan siklus kerja *Single-Threaded Execution*, *Call Stack*, *Web APIs*, *Microtask Queue*, dan *Macrotask Queue* untuk memprediksi urutan output kode asinkron secara tepat tanpa bantuan runtime.
2. **Menguasai Evolusi Asinkron**: Mengubah pola penulisan *Callback-based* menjadi *Promise-based*, dan akhirnya mengimplementasikan sintaks *Async/Await* dengan penanganan error terstruktur (`try...catch`).
3. **Mengoperasikan Fetch API**: Mengirim HTTP request (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`) menggunakan `window.fetch`, mengonfigurasi header, payload (body), serta memvalidasi properti `response.ok` dan status HTTP.
4. **Mengimplementasikan Pembatalan Request**: Mengintegrasikan `AbortController` untuk membatalkan network request yang tidak lagi dibutuhkan guna mencegah *memory leak* dan *race condition*.
5. **Membangun Komponen UI Berbasis Status Jaringan**: Merancang antarmuka pengguna yang menangani 4 status siklus hidup data: *Idle*, *Loading*, *Success*, dan *Error* secara deklaratif dan defensif.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
JavaScript Runtime Environment
│
├── Concurrency Model
│   ├── Call Stack (LIFO, Single-Threaded)
│   ├── Browser Web APIs (DOM, Timer, Fetch, Network Layer)
│   └── Event Loop
│       ├── Microtask Queue (Promise callbacks, queueMicrotask)
│       └── Macrotask/Task Queue (setTimeout, setInterval, I/O events)
│
├── Pola Penanganan Asinkron
│   ├── Callback Pattern (Callback Hell, Inversion of Control)
│   ├── Promise API
│   │   ├── States: Pending, Fulfilled, Rejected
│   │   ├── Chaining: .then(), .catch(), .finally()
│   │   └── Concurrency Utilities: Promise.all, Promise.allSettled, Promise.race
│   └── Async/Await (Syntactic Sugar di atas Promise)
│       └── Penanganan Error: try...catch...finally blocks
│
└── Integrasi Jaringan (HTTP & REST)
    ├── RESTful Constraints (Stateless, Resource-based, HTTP Verbs)
    └── Fetch API
        ├── Request Configuration (Method, Headers, Body, Mode)
        ├── Response Lifecycle (Headers check, .json() stream reading)
        ├── Error Boundaries (Network error vs HTTP error status)
        └── Flow Control (AbortController & AbortSignal)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

JavaScript dirancang sebagai bahasa *single-threaded*, artinya mesin JavaScript (seperti V8 pada Chrome atau SpiderMonkey pada Firefox) hanya memiliki satu *call stack* utama dan hanya dapat mengeksekusi satu instruksi per satuan waktu. Jika JavaScript mengeksekusi tugas berat seperti kalkulasi matematika kompleks atau menunggu respons jaringan secara sinkron (*blocking*), UI browser akan mengalami *freeze* total; pengguna tidak dapat melakukan klik, scroll, maupun melihat animasi render.

Dalam arsitektur web modern, komunikasi client-server adalah kebutuhan mutlak. Browser harus memuat data katalog produk, memverifikasi kredensial login, atau mengirim analitik ke server backend yang mungkin berada di belahan bumi lain dengan latensi ratusan milidetik. 

Pemahaman mendalam mengenai eksekusi asinkron dan Web API memungkinkan developer untuk:
* Melakukan operasi I/O (Input/Output) jaringan di latar belakang tanpa mengunci antarmuka grafis pengguna (UI thread).
* Mencegah bug *race condition* yang timbul ketika beberapa respons HTTP tiba dalam urutan yang tidak dapat diprediksi.
* Mengelola memori browser secara higienis menggunakan fitur pemutusan sinyal (*abortion*), mencegah *memory leak* pada aplikasi Single Page Application (SPA).

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Eksekusi Asinkron (Asynchronous Execution)
Operasi asinkron adalah proses di mana program memulai sebuah tugas (misal: mengambil data dari server) dan dapat melanjutkan eksekusi baris kode berikutnya tanpa harus menunggu tugas tersebut selesai secara fisik. Ketika tugas di latar belakang selesai, runtime memberi tahu aplikasi untuk memproses hasilnya melalui fungsi callback.

### 2. Promise
`Promise` adalah objek yang mewakili penyelesaian (*completion*) atau kegagalan (*failure*) dari sebuah operasi asinkron, beserta nilai yang dihasilkannya. Objek `Promise` memiliki 3 state eksklusif:
* **Pending**: Operasi sedang berjalan; belum selesai dan belum gagal.
* **Fulfilled**: Operasi sukses diselesaikan; menghasilkan nilai (*value*).
* **Rejected**: Operasi gagal; menghasilkan alasan kegagalan (*error/reason*).

### 3. Async / Await
Sintaks yang diperkenalkan pada ECMAScript 2017 (ES8) yang membungkus Promise. Kata kunci `async` mengubah return value fungsi menjadi Promise secara implisit, sementara kata kunci `await` menghentikan sementara (*pause*) eksekusi di dalam fungsi asinkron tersebut hingga Promise yang dievaluasi selesai (*settled*), sehingga kode asinkron dapat dibaca dan distrukturkan layaknya kode sinkron.

### 4. RESTful API & HTTP
REST (*Representational State Transfer*) adalah gaya arsitektur antarmuka perangkat lunak yang menggunakan protokol HTTP untuk manipulasi data.
* **Resources**: Diidentifikasi via URI unik (misal: `/api/v1/users`).
* **HTTP Verbs**: 
  * `GET`: Membaca resource (Idempoten, Safe).
  * `POST`: Membuat resource baru (Non-idempoten).
  * `PUT`: Memperbarui seluruh isi resource atau membuat jika belum ada (Idempoten).
  * `PATCH`: Memperbarui sebagian atribut resource (Non-idempoten/Idempoten tergantung implementasi).
  * `DELETE`: Menghapus resource (Idempoten).
* **Status Codes**: 
  * `2xx` (Success, misal: `200 OK`, `201 Created`).
  * `3xx` (Redirection).
  * `4xx` (Client Error, misal: `400 Bad Request`, `401 Unauthorized`, `404 Not Found`).
  * `5xx` (Server Error, misal: `500 Internal Server Error`).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Mekanisme Event Loop
Mekanisme konkurensi JavaScript bergantung pada orchestrator yang disebut **Event Loop**. Komponen yang terlibat meliputi:

1. **Call Stack**: Struktur data LIFO (*Last In, First Out*) tempat eksekusi frame fungsi berada.
2. **Web APIs**: Fasilitas lingkungan host (browser) yang menangani timer, network request, dan DOM rendering secara multi-threaded di tingkat kernel/C++.
3. **Microtask Queue**: Antrean berprioritas tinggi yang menampung callback dari `Promise` (`.then`, `.catch`, `.finally`), `queueMicrotask`, dan `MutationObserver`.
4. **Macrotask/Task Queue**: Antrean yang menampung callback dari `setTimeout`, `setInterval`, `setImmediate`, dan event I/O pengguna.

**Algoritma Eksekusi Event Loop**:
1. Eksekusi semua kode sinkron di dalam **Call Stack** hingga kosong.
2. Periksa **Microtask Queue**. Eksekusi semua tugas di dalamnya satu per satu hingga antrean Microtask benar-benar kosong. Jika eksekusi microtask menjadwalkan microtask baru, tugas baru tersebut harus diselesaikan pada siklus yang sama.
3. Berikan kontrol ke proses rendering UI (jika diperlukan pembaruan tampilan grafis).
4. Ambil **satu** tugas terdepan dari **Macrotask Queue** dan dorong ke Call Stack untuk dieksekusi.
5. Ulangi siklus kembali ke langkah 1.

### 2. Siklus Hidup `fetch()`
Fungsi `fetch()` mengembalikan Promise yang memiliki karakteristik unik:
* Promise dari `fetch()` **hanya akan di-reject jika terjadi kegagalan jaringan fatal** (misal: DNS lookup gagal, kabel LAN terputus, atau CORS ditolak oleh browser).
* Jika server mengembalikan respons dengan status HTTP error seperti `404 Not Found` atau `500 Internal Server Error`, Promise tetap berstatus **Fulfilled**.
* Developer bertanggung jawab membaca properti boolean `response.ok` (bernilai `true` jika status berada di rentang 200–299) sebelum memproses payload data.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Diagram 1: Arsitektur Event Loop & Alur Antrean Microtask/Macrotask

```text
+-------------------------------------------------------------------------+
| JAVASCRIPT RUNTIME & BROWSER ENVIRONMENT                               |
+-------------------------------------------------------------------------+
|                                                                         |
|   +-----------------------+              +--------------------------+   |
|   |      CALL STACK       |              |         WEB APIs         |   |
|   |                       |              |                          |   |
|   |  [ fnC()           ]  |              |  - HTTP Network Fetch    |   |
|   |  [ fnB()           ]  |  Delegasi    |  - setTimeout Timers     |   |
|   |  [ fnA()           ]  | -----------> |  - DOM Event Listeners   |   |
|   |  [ Global Context  ]  |              |                          |   |
|   +-----------+-----------+              +------------+-------------+   |
|               |                                       |                 |
|               | Kosong?                               | Callback Selesai|
|               v                                       v                 |
|       +---------------+                  +--------------------------+   |
|       |               |                  |    PENAMPUNGAN ASINKRON  |   |
|       |               |                  +--------------------------+   |
|       |               |                               |                 |
|       |  EVENT LOOP   | <-----------------------------+                 |
|       |  (Orchestrator)                                                 |
|       |               |                                                 |
|       +-------+-------+                                                 |
|               |                                                         |
|               | 1. Prioritas TERTINGGI (Kuras habis hingga kosong)      |
|               v                                                         |
|   +-----------------------------------------------------------------+   |
|   | MICROTASK QUEUE                                                 |   |
|   | [ Promise Callback 1 ] -> [ Promise Callback 2 ] -> [ ... ]     |   |
|   +-----------------------------------------------------------------+   |
|               |                                                         |
|               | 2. Prioritas RENDAH (Ambil TEPAT SATU per loop cycle)   |
|               v                                                         |
|   +-----------------------------------------------------------------+   |
|   | MACROTASK QUEUE (Task Queue)                                    |   |
|   | [ setTimeout Callback ] -> [ DOM Event Handler ] -> [ ... ]     |   |
|   +-----------------------------------------------------------------+   |
+-------------------------------------------------------------------------+
```

### Diagram 2: Pipeline Request/Response Fetch API dengan AbortController

```text
 Client (Browser UI)                   Network Layer                 Server REST API
         |                                   |                              |
         | 1. Instansiasi AbortController    |                              |
         |    const ac = new AbortController |                              |
         |                                   |                              |
         | 2. Panggil fetch(url, {signal})   |                              |
         |---------------------------------->|                              |
         |                                   | 3. HTTP Request Dispatched   |
         |                                   |----------------------------->|
         |                                   |                              |
    KASUS A: SUKSES                          |                              |
         |                                   | 4. HTTP Headers + Body Res   |
         |                                   |<-----------------------------|
         | 5. Promise Fulfilled (Stream Init)|                              |
         |<----------------------------------|                              |
         | 6. await response.json()          |                              |
         |    (Baca body stream sampai EOF)  |                              |
         |                                   |                              |
    KASUS B: ABORT DIAKTIFKAN                |                              |
         | (Misal: User pindah halaman)      |                              |
         | ac.abort()                        |                              |
         |--X (Kirim sinyal batal)           |                              |
         |                                   |--X (Koneksi TCP diputus)     |
         | 7. Promise Rejected               |                              |
         |    (Error: "AbortError")          |                              |
         |    try...catch menangkap Abort    |                              |
         v                                   v                              v
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah evolusi dari pendekatan tradisional ke modern untuk memahami perbedaan paradigma penanganan asinkron.

### Evolusi Penanganan Operasi Asinkron

```javascript
// ==========================================
// 1. PENDEKATAN CALLBACK (Kuno & Rentan "Callback Hell")
// ==========================================
function getUserCallback(id, onSuccess, onError) {
  setTimeout(() => {
    if (id <= 0) {
      onError(new Error("ID tidak valid"));
    } else {
      onSuccess({ id: id, username: "alex_dev" });
    }
  }, 1000);
}

// Penggunaan callback bertingkat (Pyramid of Doom)
getUserCallback(1, (user) => {
  console.log("[Callback] User loaded:", user.username);
}, (err) => {
  console.error("[Callback] Error:", err.message);
});

// ==========================================
// 2. PENDEKATAN PROMISE (ES6)
// ==========================================
function getUserPromise(id) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (id <= 0) {
        reject(new Error("ID tidak valid"));
      } else {
        resolve({ id: id, username: "alex_dev" });
      }
    }, 1000);
  });
}

// Chaining promise
getUserPromise(1)
  .then((user) => {
    console.log("[Promise] User loaded:", user.username);
    return user.id;
  })
  .catch((err) => {
    console.error("[Promise] Error:", err.message);
  })
  .finally(() => {
    console.log("[Promise] Operasi selesai.");
  });

// ==========================================
// 3. PENDEKATAN ASYNC / AWAIT (Standar Modern)
// ==========================================
async function displayUser(id) {
  try {
    console.log("[Async/Await] Mengambil data...");
    // Eksekusi berhenti sejenak di baris ini hingga Promise resolve
    const user = await getUserPromise(id); 
    console.log("[Async/Await] User loaded:", user.username);
  } catch (err) {
    // Tangkap error jika Promise di-reject
    console.error("[Async/Await] Error ditangkap:", err.message);
  } finally {
    console.log("[Async/Await] Selesai membersihkan resource.");
  }
}

displayUser(1);
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus nyata implementasi modul client antarmuka data *Todo Management* yang terintegrasi dengan REST API public (`https://jsonplaceholder.typicode.com/todos`). Modul ini mengelola validasi status, abort network saat terjadi unmount/pemanggilan ganda, serta sanitasi state UI.

### File: `index.html`
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>REST Client UI Engine</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 2rem; }
    .status-box { padding: 1rem; margin-bottom: 1rem; border-radius: 4px; display: none; }
    .status-loading { display: block; background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }
    .status-error { display: block; background: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }
    .todo-item { display: flex; align-items: center; justify-content: space-between; padding: 0.5rem; border-bottom: 1px solid #ddd; }
    .todo-completed { text-decoration: line-through; color: #888; }
    button { cursor: pointer; padding: 0.4rem 0.8rem; border-radius: 4px; border: 1px solid #ccc; }
  </style>
</head>
<body>
  <h1>Daftar Tugas (REST Integration)</h1>
  
  <div>
    <button id="btn-load">Muat Ulang Tugas</button>
    <button id="btn-cancel">Batalkan Request</button>
  </div>

  <div id="status-container" class="status-box"></div>
  <ul id="todo-list"></ul>

  <script type="module" src="./app.js"></script>
</body>
</html>
```

### File: `apiClient.js`
```javascript
/**
 * Modul Infrastruktur HTTP Client Abstraksi
 */
const BASE_URL = 'https://jsonplaceholder.typicode.com';

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

/**
 * Wrapper serbaguna di atas Fetch API
 * @param {string} endpoint - Path API relatif
 * @param {RequestInit} options - Opsi native fetch
 * @returns {Promise<any>}
 */
export async function httpClient(endpoint, { body, ...customConfig } = {}) {
  const headers = { 'Content-Type': 'application/json' };

  const config = {
    method: body ? 'POST' : 'GET',
    ...customConfig,
    headers: {
      ...headers,
      ...customConfig.headers,
    },
  };

  if (body) {
    config.body = JSON.stringify(body);
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, config);

  // Parse JSON secara aman
  let responseData;
  try {
    responseData = await response.json();
  } catch {
    responseData = null;
  }

  // Fetch TIDAK throw error pada status HTTP 4xx/5xx, kita lakukan penanganan manual
  if (!response.ok) {
    throw new ApiError(
      `Request gagal dengan status HTTP ${response.status}: ${response.statusText}`,
      response.status,
      responseData
    );
  }

  return responseData;
}
```

### File: `app.js`
```javascript
import { httpClient } from './apiClient.js';

// DOM Element References
const btnLoad = document.getElementById('btn-load');
const btnCancel = document.getElementById('btn-cancel');
const statusContainer = document.getElementById('status-container');
const todoList = document.getElementById('todo-list');

// Controller untuk pembatalan request
let currentAbortController = null;

// UI State Renderers
function setUIState(state, message = '') {
  statusContainer.className = 'status-box';
  statusContainer.style.display = 'none';

  if (state === 'LOADING') {
    statusContainer.classList.add('status-loading');
    statusContainer.textContent = message || 'Sedang mengambil data dari server...';
  } else if (state === 'ERROR') {
    statusContainer.classList.add('status-error');
    statusContainer.textContent = message || 'Terjadi kesalahan sistem.';
  }
}

function renderTodos(todos) {
  todoList.innerHTML = '';
  const fragment = document.createDocumentFragment();

  todos.slice(0, 5).forEach((todo) => {
    const li = document.createElement('li');
    li.className = 'todo-item';
    
    const span = document.createElement('span');
    span.textContent = todo.title;
    if (todo.completed) {
      span.classList.add('todo-completed');
    }

    li.appendChild(span);
    fragment.appendChild(li);
  });

  todoList.appendChild(fragment);
}

// Controller Logic
async function fetchTodoList() {
  // Jika ada request yang masih aktif berjalan, batalkan dulu sebelum memulai baru
  if (currentAbortController) {
    currentAbortController.abort('Membatalkan operasi sebelumnya karena trigger baru.');
  }

  // Buat instance sinyal baru
  currentAbortController = new AbortController();
  const { signal } = currentAbortController;

  setUIState('LOADING');
  todoList.innerHTML = '';

  try {
    const data = await httpClient('/todos', { signal });
    renderTodos(data);
    setUIState('SUCCESS');
  } catch (error) {
    // Bedakan antara pembatalan yang disengaja vs error jaringan murni
    if (error.name === 'AbortError') {
      setUIState('ERROR', 'Pengambilan data dibatalkan oleh pengguna.');
      console.warn('Request dihentikan secara sadar.');
    } else {
      setUIState('ERROR', error.message || 'Gagal memuat tugas.');
      console.error('Fatal API Error:', error);
    }
  } finally {
    // Reset controller referensi
    currentAbortController = null;
  }
}

// Event Listeners
btnLoad.addEventListener('click', fetchTodoList);

btnCancel.addEventListener('click', () => {
  if (currentAbortController) {
    currentAbortController.abort('Pengguna mengklik tombol batal.');
  }
});

// Panggilan inisial
fetchTodoList();
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Pendekatan | Keunggulan (Pros) | Konsekuensi & Batasan (Cons) | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Raw Promises (`.then().catch()`)** | Baik untuk eksekusi paralel sederhana melalui method utility chaining seperti functional composition. | Menimbulkan nested callbacks (*chain hell*) jika flow data saling membutuhkan nilai dari tahapan sebelumnya. | Operasi paralel murni yang tidak membutuhkan percabangan state berurutan. |
| **Async / Await** | Kode terlihat sinkron, linear, dan intuitif. Mendukung struktur `try...catch...finally` standar native JS. | Dapat menyebabkan perangkap performa serial (*waterfall request*) jika tidak sengaja menempatkan `await` berulang kali secara tidak terisolasi. | Mayoritas logika kontrol alur asinkron di aplikasi modern. |
| **Native Fetch API** | Terbawa secara default dalam browser modern & Node.js 18+. Tanpa perlu menambah ukuran *bundle size* (0 KB dependency). | Tidak otomatis menolak (*reject*) HTTP error status (seperti 404, 500). Tidak memiliki parser timeout atau progress monitoring bawaan. | Aplikasi frontend modern yang ingin menjaga beban aset seminimal mungkin. |
| **Third-Party Client (Axios)** | Transformasi JSON otomatis, interceptor terintegrasi, built-in timeout setting, dan auto-rejection pada HTTP error. | Menambah ukuran paket dependensi (+30KB non-gzipped). Memerlukan proses instalasi dan audit paket reguler. | Aplikasi enterprise skala besar dengan kebutuhan mutlak interceptor token otentikasi global. |

---

## SEKSI 11 — BEST PRACTICES

1. **Selalu Validasi `response.ok` Sebelum Parsing**: Jangan pernah mengasumsikan respons `fetch()` berstatus `200 OK`. Jika backend mengembalikan dokumen error 404 berformat HTML, parsing `.json()` akan langsung mengakibatkan `SyntaxError`.
2. **Pakai AbortController untuk Cleanup**: Selalu sediakan pembatalan request ketika elemen web dilepas (unmounted) atau ketika input form cepat berubah (*debouncing*) guna menghemat resource client dan bandwidth.
3. **Pemberian Timeout Buatan Menggunakan `AbortSignal.timeout()`**: Jaringan mobile sering mengalami *hanging connection*. Pasang timeout otomatis agar eksekusi tidak macet selamanya:
   ```javascript
   // Otomatis batalkan jika koneksi tidak kembali dalam 8000ms
   const response = await fetch('/api/data', { 
     signal: AbortSignal.timeout(8000) 
   });
   ```
4. **Pisahkan Layer Akses Data (Data-Access Layer)**: Jauhkan pemanggilan URL dan konfigurasi header langsung dari file logika antarmuka UI. Bungkus pemanggilan HTTP dalam modul servis independen.
5. **Hindari Waterfall Execution Jika Bisa Paralel**:
   ```javascript
   // BURUK: Menunggu profil selesai selama 1 detik, baru menunggu pesanan 1 detik (Total 2 detik)
   const user = await fetchUser();
   const orders = await fetchOrders();

   // BAIK: Keduanya dipicu secara simultan (Total 1 detik)
   const [user, orders] = await Promise.all([fetchUser(), fetchOrders()]);
   ```
6. **Selalu Pasang Blok `finally` untuk Mengembalikan State**: Jangan biarkan status UI tersangkut di mode `isLoading = true` saat runtime mengalami kegagalan/exception di tengah pemrosesan.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Kesalahan: Menggunakan `forEach` Bersama `async/await`
*Anti-Pattern*:
```javascript
// FORBIDDEN: forEach TIDAK memedulikan Promise yang dikembalikan oleh callback!
items.forEach(async (id) => {
  await deleteItemOnServer(id);
});
console.log('Semua terhapus!'); // Baris ini dieksekusi SEBELUM penghapusan selesai!
```
*Solusi Benar*:
```javascript
// Opsi A: Eksekusi berurutan (Serial)
for (const id of items) {
  await deleteItemOnServer(id);
}
console.log('Semua terhapus secara sekuensial.');

// Opsi B: Eksekusi paralel simultan
await Promise.all(items.map((id) => deleteItemOnServer(id)));
console.log('Semua terhapus secara paralel.');
```

### 2. Kesalahan: Asumsi `fetch()` Otomatis Throw Error pada HTTP 404/500
*Anti-Pattern*:
```javascript
try {
  const res = await fetch('/api/user/tidak-ada');
  const data = await res.json(); // Jika server mengirim pesan error string, ini meledak
  render(data);
} catch (err) {
  // Blok ini HANYA terpanggil jika tidak ada koneksi internet sama sekali!
  console.log('Error ditangkap:', err);
}
```
*Solusi Benar*:
```javascript
const res = await fetch('/api/user/tidak-ada');
if (!res.ok) {
  throw new Error(`Permintaan HTTP bermasalah: ${res.status}`);
}
const data = await res.json();
```

### 3. Kesalahan: Membaca Stream Response Dua Kali
*Anti-Pattern*:
```javascript
const res = await fetch('/api/data');
const rawText = await res.text();
const jsonData = await res.json(); // ERROR: TypeError: Failed to execute 'json' on 'Response': body stream already read
```
*Solusi Benar*:
Stream HTTP hanya dapat dikonsumsi satu kali. Gunakan salah satu metode parsing, atau kloning respons terlebih dahulu jika memang mutlak diperlukan inspeksi ganda:
```javascript
const res = await fetch('/api/data');
const clonedRes = res.clone();
const text = await res.text();
const json = await clonedRes.json();
```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Level 1: Mengonversi Pola Callback Timer ke Promise Dasar
Ubahlah fungsi pembungkus native `setTimeout` lama berikut menjadi format fungsi berbasis Promise murni yang dapat di-`await`.
* **Spesifikasi**:
  * Buat fungsi `delay(ms)`.
  * Return instance `Promise`.
  * Selesai (*resolve*) setelah durasi `ms` berakhir.
```javascript
// TULIS KODE ANDA DI SINI
function delay(ms) {
  // Implementasi
}

// Skrip Verifikasi:
async function testDelay() {
  const start = Date.now();
  await delay(500);
  const elapsed = Date.now() - start;
  console.assert(elapsed >= 480, `Ekspektasi ~500ms, didapat ${elapsed}ms`);
  console.log("Level 1 Terverifikasi Sukses!");
}
testDelay();
```

### Level 2: Implementasi Safe Fetch Wrapper dengan Validasi Status
Bangun fungsi utility bernama `safeGet(url)` yang memenuhi kriteria:
* **Spesifikasi**:
  1. Menggunakan Fetch API.
  2. Jika status bukan 2xx, kembalikan objek: `{ data: null, error: 'Status: [CODE]' }`.
  3. Jika berhasil, kembalikan objek: `{ data: [HASIL_PARSING_JSON], error: null }`.
  4. Jika jaringan putus (network error), tangkap exception dan kembalikan: `{ data: null, error: error.message }`.
```javascript
// TULIS KODE ANDA DI SINI
async function safeGet(url) {
  // Implementasi
}

// Skrip Verifikasi:
async function testSafeGet() {
  // Test case A: Success
  const valid = await safeGet('https://jsonplaceholder.typicode.com/posts/1');
  console.assert(valid.data !== null && valid.error === null, 'Test Case Valid Gagal');

  // Test case B: 404
  const notFound = await safeGet('https://jsonplaceholder.typicode.com/posts/999999');
  console.assert(notFound.data === null && typeof notFound.error === 'string', 'Test Case 404 Gagal');

  console.log("Level 2 Terverifikasi Sukses!");
}
testSafeGet();
```

### Level 3: Menangani Race Condition pada Kasus Pencarian Cepat
Simulasikan mekanisme pencarian (*auto-complete*) di mana pengguna mengetikkan kata kunci secara cepat. Anda harus memastikan bahwa respons query lama yang datang terlambat (*lagging network*) tidak menimpa data query yang paling baru di-request.
* **Instruksi**:
  1. Buat class `SearchManager`.
  2. Sediakan method `search(query)`.
  3. Setiap kali `search` dipanggil, jika request sebelumnya masih pending, batalkan secara otomatis menggunakan `AbortController`.
```javascript
// TULIS KODE ANDA DI SINI
class SearchManager {
  constructor() {
    this.controller = null;
  }

  async search(query) {
    // Implementasi mekanisme pembatalan controller lama dan fetch baru
    // Gunakan Mock endpoint: `https://jsonplaceholder.typicode.com/comments?postId=${query}`
  }
}

// Skrip Verifikasi:
async function testSearchManager() {
  const manager = new SearchManager();
  
  // Panggil dua pencarian secara cepat berurutan
  const promise1 = manager.search(1);
  const promise2 = manager.search(2);

  const [res1, res2] = await Promise.allSettled([promise1, promise2]);

  console.assert(res1.status === 'rejected' && res1.reason.name === 'AbortError', 'Request 1 harusnya dibatalkan');
  console.assert(res2.status === 'fulfilled', 'Request 2 harusnya berhasil selesai');
  console.log("Level 3 Terverifikasi Sukses!");
}
testSearchManager();
```

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

### Pertanyaan Pilihan Ganda

#### 1. Perhatikan potongan kode berikut:
```javascript
console.log('1');
setTimeout(() => console.log('2'), 0);
Promise.resolve().then(() => console.log('3'));
console.log('4');
```
Berapakah urutan angka yang dicetak pada console browser?
* A) `1 -> 2 -> 3 -> 4`
* B) `1 -> 4 -> 2 -> 3`
* C) `1 -> 4 -> 3 -> 2`
* D) `3 -> 1 -> 4 -> 2`

#### 2. Apa status dari Promise yang dihasilkan oleh pemanggilan `window.fetch()` apabila server tujuan memberikan respons HTTP dengan status header `500 Internal Server Error`?
* A) Rejected
* B) Fulfilled
* C) Pending
* D) Aborted

#### 3. Kapan penggunaan `Promise.allSettled()` lebih direkomendasikan dibandingkan dengan `Promise.all()`?
* A) Ketika seluruh asynchronous tasks wajib berhasil semuanya tanpa kompromi.
* B) Ketika kita menginginkan perilaku *short-circuit* langsung segera setelah ada salah satu task yang mengalami error/reject.
* C) Ketika kita memiliki serangkaian operasi independen dan kita membutuhkan informasi lengkap hasil dari setiap operasi, terlepas dari apakah operasi itu sukses ataupun gagal.
* D) Ketika kita ingin menjalankan tugas secara serial/berurutan satu demi satu.

#### 4. Apa fungsi dari parameter kedua pada method `abortController.abort(reason)`?
* A) Menghapus cache browser secara paksa.
* B) Menentukan kode HTTP status buatan untuk dikirim balik ke server.
* C) Mengirimkan alasan pembatalan yang dapat ditangkap pada properti `signal.reason` atau `error` di blok `catch`.
* D) Mengatur durasi delay penundaan eksekusi pembatalan jaringan.

#### 5. Manakah pernyataan berikut yang mendefinisikan sifat idempoten (*idempotent*) pada metode HTTP REST?
* A) Metode yang menjamin data body payload dienkripsi secara penuh.
* B) Metode yang tidak mengubah data sama sekali di sisi server.
* C) Metode yang jika dieksekusi satu kali atau berkali-kali secara identik akan menghasilkan efek samping (*side-effect*) status resource server yang tetap sama.
* D) Metode yang hanya dapat dijalankan melalui koneksi protokol HTTPS.

---

### Kunci Jawaban & Evaluasi

1. **Jawaban: C**.
   * *Penjelasan*: Baris `1` dan `4` dieksekusi secara sinkron di Call Stack utama. Callback `Promise` masuk ke Microtask Queue, sedangkan callback `setTimeout` masuk ke Macrotask Queue. Berdasarkan prioritas Event Loop, Microtask Queue dikuras terlebih dahulu (`3`), baru kemudian giliran Macrotask Queue dieksekusi (`2`).
2. **Jawaban: B**.
   * *Penjelasan*: Fetch API hanya akan me-reject Promise jika terjadi kegagalan jaringan secara fisik (*network failure*). Respons status HTTP 500 dianggap sebagai komunikasi client-server yang sukses tercapai (berhasil menerima paket balasan), sehingga statusnya tetap *Fulfilled*. Developer harus membaca nilai `response.ok` untuk memverifikasinya.
3. **Jawaban: C**.
   * *Penjelasan*: `Promise.all` menerapkan prinsip *fail-fast* di mana jika satu Promise reject, maka seluruh batch langsung dinyatakan reject dan sisa Promise lainnya diabaikan. Sebaliknya, `Promise.allSettled` menunggu seluruh array eksekusi selesai dan memberikan array status masing-masing objek (`status: 'fulfilled'` atau `'rejected'`).
4. **Jawaban: C**.
   * *Penjelasan*: Argumen opsional `reason` pada `.abort(reason)` memungkinkan developer memberikan konteks kontekstual mengapa sinyal diputus (misal: "User navigasi ke halaman lain"). Objek ini diteruskan langsung ke blok penanganan error.
5. **Jawaban: C**.
   * *Penjelasan*: Definisi formal idempotensi pada spesifikasi HTTP (RFC 9110) adalah beberapa permintaan identik memiliki efek samping yang sama pada server seperti satu permintaan saja. Contoh metode idempoten adalah `GET`, `PUT`, dan `DELETE`. Sebaliknya, `POST` bukan idempoten karena memicu pembuatan record ganda jika dikirim berulang kali.

---

### Checklist Evaluasi Diri (Self-Audit)
- [ ] Saya memahami mengapa eksekusi `console.log` di dalam microtask lebih cepat dibanding makrotask `setTimeout(..., 0)`.
- [ ] Saya tidak lagi menulis sintaks `async` di dalam parameter `.forEach()`.
- [ ] Saya selalu melakukan pengecekan `if (!response.ok)` setiap kali menggunakan `window.fetch()`.
- [ ] Saya dapat mengimplementasikan `AbortController` untuk membersihkan request jaringan yang usang.
- [ ] Saya dapat membedakan kapan harus menggunakan `Promise.all()` versus `Promise.allSettled()`.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi**:
  * [MDN Web Docs: Concurrency Model and the Event Loop](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Event_loop)
  * [MDN Web Docs: Using the Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch)
  * [MDN Web Docs: AbortController Interface](https://developer.mozilla.org/en-US/docs/Web/API/AbortController)
* **Buku & Standar Spesifikasi**:
  * *You Don't Know JS Yet: Async & Performance* — Kyle Simpson.
  * [WHATWG Fetch Living Standard](https://fetch.spec.whatwg.org/)
  * [RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html)
* **Visualisasi Interaktif**:
  * [JavaScript Visualized: The Event Loop](https://dev.to/lydiahallie/javascript-visualized-event-loop-3dif) oleh Lydia Hallie.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. JavaScript adalah bahasa eksekusi **single-threaded** yang menggunakan arsitektur **Event Loop** untuk mendelegasikan tugas I/O panjang ke lingkungan host (Web APIs) tanpa memblokir Call Stack rendering browser.
2. Urutan prioritas eksekusi Event Loop: **Call Stack (Sinkron) $\rightarrow$ Microtask Queue (Promise) $\rightarrow$ UI Render $\rightarrow$ Macrotask Queue (setTimeout/Interval)**.
3. Pola penulisan asinkron telah berevolusi dari raw **Callbacks** (rawan *callback hell* dan kehilangan kontrol), menjadi **Promises** (komposisi linear state), hingga sintaks modern **Async/Await** yang memudahkan penulisan logika yang rapi dan penanganan error terstruktur melalui `try...catch`.
4. Fungsi bawaan `fetch()` **tidak melakukan auto-throw pada status kode HTTP 4xx atau 5xx**. Developer wajib melakukan pengecekan manual terhadap properti boolean `response.ok`.
5. Manajemen lifecycle network request modern wajib memperhitungkan pembatalan task melalui **`AbortController`** guna mencegah *memory leaks* dan bug *race condition* pada koneksi jaringan yang lambat atau tidak stabil.

---

## SEKSI 17 — GLOSARIUM

* **Single-Threaded**: Model pemrosesan di mana komputasi dieksekusi hanya pada satu jalur thread secara sekuensial pada satu waktu.
* **Call Stack**: Struktur tumpukan memori tempat runtime mencatat fungsi apa yang sedang aktif berjalan dan dari mana fungsi tersebut dipanggil.
* **Event Loop**: Loop tak terbatas dalam runtime yang bertugas memantau apakah Call Stack sedang kosong untuk kemudian menarik tugas baru dari Microtask atau Macrotask Queue.
* **Microtask Queue**: Antrean penampungan eksekusi tugas ringan berprioritas paling tinggi (Promise callback, mutation observer) yang harus dikuras habis sebelum thread kembali merender frame atau mengambil tugas macrotask.
* **Macrotask Queue (Task Queue)**: Antrean penampungan callback operasi berbasis durasi waktu atau event hardware eksternal (seperti timer `setTimeout`, respons network I/O, event listener klik).
* **Idempotent**: Karakteristik dari suatu operasi/metode HTTP yang apabila dipanggil satu kali atau ribuan kali secara identik, status akhir resource pada sistem target tetap sama.
* **Race Condition**: Anomali bug perangkat lunak di mana output akhir sistem bergantung pada urutan waktu tiba eksekusi yang tidak konsisten dari dua atau lebih operasi asinkron yang berjalan paralel.
* **AbortController**: Objek antarmuka web standar yang memungkinkan developer mengirimkan sinyal pemutusan (*abort signal*) ke operasi berbasis Promise (seperti Fetch request).

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Titik Kesulitan Siswa (Common Traps)
* Siswa sering keliru menduga bahwa `setTimeout(fn, 0)` akan dieksekusi secara instan pada milidetik berikutnya. Tekankan kembali aturan Event Loop: meskipun durasi 0ms telah usai di level kernel Web API, callback tetap harus menunggu antrean giliran di Macrotask Queue dan **tidak akan dieksekusi** sebelum Call Stack dan seluruh Microtask Queue kosong total.
* Kebingungan umum mengenai status Fetch: "Mengapa endpoint `/users/tidak-ditemukan` masuk ke blok `try` dan bukan blok `catch`?" Berikan demonstrasi langsung mematikan koneksi internet (DevTools Offline Mode) untuk memperlihatkan kondisi apa yang sesungguhnya membuat blok `catch` pada fetch terpanggil secara natural.

### Saran Pembelajaran Praktis di Kelas
* Gunakan tool visualizer interaktif (seperti *Loupe* oleh Philip Roberts) saat mengajarkan Seksi 06 dan Seksi 07 agar pergerakan fungsi dari Stack menuju Web APIs dan antrean Queue terlihat secara spasial.
* Tekankan penulisan aplikasi frontend yang memiliki ketahanan (*resilience*) jaringan: wajib selalu ada representasi visual untuk Loading spinner, Error notification, dan penanganan saat Array respons kosong (*empty state*).

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal | Penulis | Deskripsi Perubahan |
| :--- | :--- | :--- | :--- |
| **v1.0.0** | 2024-03-01 | Frontend Core Team | Rilis dokumen awal silabus eksekusi asinkron & Fetch REST Client. |
| **v1.1.0** | 2024-06-15 | Lead Curriculum Architect | Penambahan standarisasi integrasi `AbortController` dan `AbortSignal.timeout()`. |
| **v1.2.0** | 2024-10-20 | Senior Technical Architect | Penyempurnaan diagram alur ASCII Event Loop dan ekspansi materi pemisahan layer client data. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `01-Core-Foundations/Bab-07-Module-02`: [Manipulasi DOM Tingkat Lanjut, Pola Event Bubbling, dan Web Storage]
* **Modul Saat Ini**: `01-Core-Foundations/Bab-08-Module-01`: [JavaScript Asinkron, Web API & Integrasi REST]
* **Modul Berikutnya**: `01-Core-Foundations/Bab-09-Module-01`: [Modern Tooling: Node.js Basics, NPM Packages, dan Bundler/Vite Setup]