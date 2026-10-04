---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Zustand Internal Mechanics
Zustand beroperasi di luar siklus hidup React. Store Zustand pada intinya adalah penutupan (*closure*) JavaScript sederhana yang mengelola `state`, `listeners` (berupa `Set<Listener>`), dan fungsi dispatch (`setState`, `getState`, `subscribe`).

Ketika `setState` dipanggil:
1. State baru dihitung melalui partial state update: `const nextState = typeof partial === 'function' ? partial(state) : partial`.
2. Dilakukan perbandingan referensial `Object.is(nextState, state)`. Jika referensi sama, mutasi dibatalkan (*no-op*).
3. Jika referensi berbeda, `state = Object.assign({}, state, nextState)` dijalankan.
4. Semua callback dalam listener `Set` dipanggil secara iteratif: `listeners.forEach(listener => listener(state, prevState))`.
5. Komponen React yang terhubung via `useStore(selector, equalityFn)` memanfaatkan hook internal `useSyncExternalStoreWithSelector` dari React 18+. Hook ini mengevaluasi apakah hasil dari `selector(nextState)` secara referensial berbeda dari `selector(prevState)` menggunakan equality check (default: `Object.is`).
6. Jika selector menghasilkan nilai yang identik, React melewati proses reconciliation pada komponen tersebut secara penuh.

### 2. MMKV Storage Engine via JSI
Dibandingkan dengan `AsyncStorage` yang menggunakan thread pool native (melalui Java/Objective-C serialization ke SQLite atau flat file), MMKV memanfaatkan **Tencent's Memory Mapping (mmap)** yang diekspos langsung ke JavaScript melalui JavaScript Interface (JSI).

*   **mmap (POSIX):** MMKV memetakan deskriptor file ke dalam memori virtual aplikasi. Membaca dan menulis ke array memori ini secara langsung memanipulasi disk virtual tanpa context switch dari User Space ke Kernel Space melalui syscall manual `read()` / `write()`.
*   **Protobuf Serialization:** MMKV menyimpan data dalam format biner Protocol Buffers mini. Tidak ada proses `JSON.stringify` atau `JSON.parse` yang membebani CPU JS thread.
*   **JSI Host Objects:** Objek MMKV diinstansiasi sebagai `HostObject` C++. Engine JavaScript (Hermes) memiliki referensi pointer langsung ke instance C++ ini. Fungsi seperti `mmkv.getString('key')` dieksekusi secara sinkronis dalam hitungan *sub-millisecond* (skala nanodetik ke mikrodetik), menghindari latency asinkronisasi Promise queue.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### State Colocation vs Global State
Salah satu kegagalan arsitektur terbesar adalah sentralisasi *semua* state ke store global. Prinsip rekayasa state performan:
1.  **Ephemeral UI State:** Harus diisolasi pada level komponen menggunakan `useState` / `useReducer` (contoh: status ekspansi akordeon, animasi toggle).
2.  **Server Cache State:** State yang bersumber dari server dan di-cache secara lokal (contoh: data profil, list produk). Harus ditangani oleh dedicated server-cache tools seperti `@tanstack/react-query`.
3.  **App/Client State:** State murni aplikasi yang mengatur sesi pengguna, preferensi global, keranjang belanja lokal, atau mutasi outbox offline. Inilah ruang lingkup sejati **Zustand**.

### Re-render Cascades & Zombie Child Problem
Pada arsitektur state berbasis Context API bawaan React, setiap perubahan *value* pada Context Provider memicu re-render pada seluruh konsumen context tersebut, mengabaikan apakah subtree komponen tersebut membutuhkan fragmen data yang berubah atau tidak.

Zustand menghindari problem ini dengan sistem subskripsi berbasis selektor *pub-sub*. Namun, sistem pub-sub eksternal rentan terhadap **Zombie Child Problem**: kondisi ketika child component membaca data store yang sudah dihapus oleh parent component sebelum parent component sempat meng-unmount child tersebut dalam siklus render. React 18 memitigasi problem ini secara fundamental via hook `useSyncExternalStore`, yang menjamin sinkronisasi pembacaan state eksternal secara konsisten tanpa tearing pada transisi concurrent.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi custom MMKV storage adapter untuk Zustand yang mengintegrasikan validasi TypeScript strictly-typed dan enkripsi.

### File: `src/storage/mmkv.ts`
