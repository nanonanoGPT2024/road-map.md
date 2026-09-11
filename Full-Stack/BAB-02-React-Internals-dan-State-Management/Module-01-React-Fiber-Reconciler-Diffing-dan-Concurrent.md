---
[⬅️ BAB 01 Quiz & Challenge](../BAB-01-Arsitektur-Full-Stack-dan-Browser-Internals/BAB-01-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Server State vs Client State ➡️](./Module-02-Server-State-Client-State-dan-Optimistic-UI.md)
---

# Module 01: React Internals: Fiber Reconciler, Virtual DOM Diffing, & Concurrent Features

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Memahami evolusi arsitektur internal React: mengapa **Stack Reconciler** kuno (React 15) ditinggalkan dan digantikan oleh **Fiber Reconciler** berbasis *Time-Slicing* dan *Priority Queue* (React 16+).
- Menguasai algoritma heuristik **Virtual DOM Diffing $O(N)$**: aturan pencocokan tipe elemen (*Element Type Match*), fungsi identitas **`key` prop** pada daftar dinamis, dan bahaya fatal menggunakan *Array Index as Key*.
- Memahami struktur data internal **Fiber Node**: rantai berkait ganda (*Child, Sibling, Return pointers*), pemisahan antara **Render Phase (Asinkron / Dapat Dibatalkan)** dan **Commit Phase (Sinkron / Mutasi DOM)**.
- Menguasai mekanika internal React Hooks: bagaimana urutan pemanggilan (*Hook Call Order*) disimpan dalam linked list di dalam Fiber node.
- Menerapkan fitur **Concurrent React**: fungsi `useTransition` (prioritas rendah) vs `useDeferredValue` untuk mencegah pembekuan antarmuka saat input pengguna intensif.

---

## 2. Prerequisite
- Memahami konsep JavaScript closures, linked lists, dan Call Stack (Backend BAB 02).
- Pemahaman siklus hidup browser rendering dan frame rate 60 FPS (16.6 ms per frame) (BAB 01).
- Pemahaman dasar penggunaan React JSX, `useState`, dan `useEffect`.

---

## 3. Concept
React bukan sekadar library UI; di balik layar, React adalah **mesin penjadwal komputasi (Scheduler)**.

Pada React 15 ke bawah (*Stack Reconciler*), proses rekonsiliasi Virtual DOM berjalan secara rekursif sinkron. Jika aplikasi memiliki pohon komponen dengan 5.000 elemen, JavaScript akan mendominasi Main Thread selama 200 milidetik penuh. Selama waktu tersebut, browser tidak dapat merender frame baru, merespons ketikan keyboard, atau menangani klik mouse (*Jank / Freeze*).

Untuk memecahkan masalah ini, tim React merancang ulang arsitektur dari nol: **React Fiber**.
Fiber mengubah rekursi sinkron menjadi perulangan berbasis **Unit of Work** yang dapat diinterupsi (*Cooperative Multitasking* / *Time-Slicing*):
- React mengerjakan kalkulasi Virtual DOM selama 5 milidetik.
- React memeriksa: *"Apakah ada input user yang mendesak atau browser butuh menggambar frame baru?"*
- Jika ada, React menunda (*yield*) pekerjaannya ke browser, membiarkan browser menggambar layar, lalu melanjutkan kembali pekerjaan Fiber di frame berikutnya.

---

## 4. Why?
Tanpa pemahaman mendalam tentang React Fiber dan algoritma Diffing:
1. **Unnecessary Re-renders Masif:** Komponen induk me-render ulang, memicu render ulang rekursif pada 500 komponen anak yang sebenarnya tidak mengalami perubahan data sama sekali.
2. **Bug Fatal State Corruption Akibat `key={index}`:** Menghapus atau menyortir elemen daftar yang menggunakan indeks array sebagai key membuat input form, checkbox, atau state lokal tertukar secara acak ke baris lain.
3. **Penyalahgunaan Hooks:** Menaruh pemanggilan `useState` di dalam blok `if-else` atau perulangan, menyebabkan rantai linked list hook rusak dan melempar error legendaris: *"Rendered more hooks than during the previous render"*.
4. **Antarmuka Membeku saat Mengetik di Search Bar:** Render hasil pencarian 1.000 item memblokir Main Thread, membuat ketikan pengguna di input teks terlambat muncul (*Input Lag*).

---

## 5. What? (Anatomi Fiber Node & Algoritma Diffing)

### A. Struktur Data Fiber Node
Setiap elemen React memiliki representasi internal bernama **Fiber Node** di memori:
```javascript
{
  tag: 5,                  // Tipe komponen (FunctionComponent, HostComponent/div, dll)
  key: 'user-8841',        // Kunci identitas unik
  type: UserCard,          // Fungsi komponen atau string tag ('div')
  stateNode: HTMLDivElement, // Referensi ke DOM node fisik asli di browser
  
  // Rantai Pointer Graf Pohon (Linked List)
  child: FiberNode,        // Anak pertama
  sibling: FiberNode,      // Saudara kandung berikutnya
  return: FiberNode,       // Induk (Parent)
  
  // State & Hooks
  memoizedState: { ... },  // Linked list data hooks (useState, useReducer)
  memoizedProps: { ... },  // Props sebelumnya
  
  // Penjadwalan & Efek Samping
  flags: 2,                // Penanda mutasi (Placement, Update, Deletion)
  alternate: FiberNode     // Pointer ke fiber node pasangannya (Double Buffering)
}
```

### B. Algoritma Heuristik Virtual DOM Diffing $O(N)$
Secara matematis, membandingkan dua pohon graf acak membutuhkan kompleksitas waktu $O(N^3)$ (memerlukan 1 miliar operasi untuk 1.000 elemen!).
React memangkasnya menjadi $O(N)$ linier menggunakan 2 asumsi heuristik:
1. **Dua elemen dengan tipe berbeda akan menghasilkan pohon yang sama sekali berbeda:**
   - Jika `<div className="card">` berubah menjadi `<section className="card">`, React tidak akan memeriksa anak-anaknya. React akan menghancurkan (*Unmount*) seluruh pohon `div` lama dan membangun pohon `section` baru dari nol!
2. **Pengembang dapat memberikan stabilitas identitas elemen anak menggunakan prop `key`:**
   - Saat elemen bertukar posisi, React menggunakan `key` untuk memindahkan DOM node yang sudah ada tanpa perlu merusak dan membuatnya ulang.

---

## 6. How? (Dua Fase Kerja React Fiber: Render vs Commit)

React membagi siklus kerjanya menjadi dua fase yang sangat berbeda:

```
[ Trigger Update: setState() ]
               │
               ▼
 ┌────────────────────────────────────────────────────────┐
 │ FASE 1: RENDER PHASE (Reconciliation)                  │
 │ - Bekerja secara asinkron di memori murni.             │
 │ - Dapat dijeda, dibatalkan, atau dibagi per frame      │
 │   (Time-slicing via requestIdleCallback / MessageChannel)│
 │ - Membangun 'workInProgress' Fiber Tree.               │
 │ - Menghitung 'flags' (Placement, Update, Deletion).    │
 └──────────────────────────┬─────────────────────────────┘
                            │ (Selesai Menghitung Seluruh Pohon)
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │ FASE 2: COMMIT PHASE (DOM Mutation)                    │
 │ - Bekerja secara SINKRON & CEPAT di Main Thread.       │
 │ - TIDAK BOLEH DIINTERUPSI!                             │
 │ - Memanipulasi DOM asli: appendChild, removeChild.     │
 │ - Menjalankan lifecycle: useLayoutEffect -> Paint ->   │
 │   useEffect (asinkron pasca-paint).                    │
 └────────────────────────────────────────────────────────┘
```

---

## 7. Analogy
- **Stack Reconciler (React 15) ibarat Penelepon Tak Punya Sopan Santun:** Seseorang menelpon Anda dan berbicara tanpa henti selama 2 jam. Meskipun pintu rumah Anda diketuk kurir paket (**Input User**), Anda tidak bisa membukakan pintu sampai penelepon selesai berbicara.
- **Fiber Reconciler (React 16+) ibarat Pembicara yang Penuh Perhatian:** Dia berbicara selama 1 menit, lalu berhenti dan bertanya: *"Apakah Anda perlu minum atau ada tamu di depan pintu?"* Jika kurir datang, dia mempersilakan Anda menerima paket terlebih dahulu, baru kemudian melanjutkan pembicaraan.
- **Double Buffering Fiber ibarat Layar Bioskop:** Di layar depan proyektor, penonton melihat adegan film aktif (*Current Tree*). Di ruang proyeksionis di belakang layar, asisten proyektor sedang menyiapkan gulungan rol film berikutnya (*workInProgress Tree*). Saat rol selesai, proyektor hanya membalikkan cermin (*Switch Pointer*) dalam 0,1 milidetik tanpa ada jeda hitam.

---

## 8. Diagram: Mengapa Menggunakan `key={index}` Sangat Berbahaya?

```
KONDISI AWAL (List 3 Item):
Index 0: Key 0 -> [Input: "Item A"] (State Lokal: "Ditandai ✅")
Index 1: Key 1 -> [Input: "Item B"]
Index 2: Key 2 -> [Input: "Item C"]

AKSI USER: HAPUS ELEMEN PERTAMA ("Item A"):
Hasil Ekspektasi: Item A musnah, tersisa Item B dan Item C.

KENYATAAN DENGAN KEY=INDEX:
Lama (Key 0: Item A) vs Baru (Key 0: Item B) ──▶ React berpikir: "Key 0 tetap ada, hanya teksnya berubah!"
Lama (Key 1: Item B) vs Baru (Key 1: Item C) ──▶ React berpikir: "Key 1 tetap ada, hanya teksnya berubah!"
Lama (Key 2: Item C) vs Baru (Key 2: Tidak ada)──▶ React menghapus Key 2 (ITEM C DIHAPUS!)

BENCANA: State "Ditandai ✅" dari Item A secara keliru menempel ke Item B!
```

---

## 9. Simple Example: Penjadwalan Prioritas dengan `useTransition` (Concurrent React)

```javascript
import { useState, useTransition } from 'react';

function SearchComponent({ allLargeProducts }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [filteredList, setFilteredList] = useState(allLargeProducts);
  
  // useTransition membedakan update mendesak (Urgent) vs transisi latar belakang (Non-urgent)
  const [isPending, startTransition] = useTransition();

  const handleInputChange = (e) => {
    const value = e.target.value;
    
    // UPDATE PRIORITAS TINGGI (URGENT): Input teks harus merespons instan (< 16 ms)
    setSearchTerm(value);

    // UPDATE PRIORITAS RENDAH (TRANSITION): Filter 10.000 item boleh dicicil di latar belakang!
    startTransition(() => {
      const results = allLargeProducts.filter(item => 
        item.name.toLowerCase().includes(value.toLowerCase())
      );
      setFilteredList(results);
    });
  };

  return (
    <div>
      <input type="text" value={searchTerm} onChange={handleInputChange} placeholder="Cari produk..." />
      {isPending && <div className="spinner">Menyaring hasil di latar belakang...</div>}
      <ProductListView items={filteredList} />
    </div>
  );
}
```

---

## 10. Practical Example: Mekanisme Rantai Linked List pada React Hooks

```javascript
// SIMULASI INTERNAL HOOK ENGINE SEDERHANA
let currentlyRenderingFiber = null;
let workInProgressHook = null;

function useState(initialState) {
  const fiber = currentlyRenderingFiber;

  // Jika hook pertama kali dipanggil pada komponen ini
  if (!fiber.memoizedState) {
    fiber.memoizedState = {
      memoizedState: typeof initialState === 'function' ? initialState() : initialState,
      queue: [],
      next: null // Pointer ke hook berikutnya dalam rantai
    };
    workInProgressHook = fiber.memoizedState;
  } else if (!workInProgressHook.next) {
    // Tambahkan hook baru ke ujung rantai linked list
    const newHook = {
      memoizedState: initialState,
      queue: [],
      next: null
    };
    workInProgressHook.next = newHook;
    workInProgressHook = newHook;
  } else {
    // Pada re-render berikutnya: telusuri rantai hook sesuai urutan pemanggilan
    workInProgressHook = workInProgressHook.next;
  }

  const hook = workInProgressHook;
  const setState = (action) => {
    hook.memoizedState = action;
    scheduleReRender(fiber); // Memicu re-render komponen
  };

  return [hook.memoizedState, setState];
}
// KESIMPULAN MENGAPA HOOKS TIDAK BOLEH DI DALAM IF-ELSE:
// Jika pemanggilan hook di dalam IF dilewati pada re-render ke-2,
// urutan penelusuran linked list akan meleset satu posisi dan mencampur aduk state variabel lain!
```

---

## 11. Real World Example: Optimalisasi Dashboard Finansial Robinhood / Bloomberg

Pada aplikasi analitik pasar saham real-time:
- Ratusan harga ticker saham berfluktuasi setiap 100 milidetik via WebSocket.
- Pada saat bersamaan, pengguna sedang mengetik formula filter grafik atau menggeser slider rentang tanggal.
- Tanpa Concurrent React:
  - Lonjakan render ulang ticker saham membekukan slider grafik pengguna (*Unresponsive Input Lag*).
- Dengan `useTransition` & `useDeferredValue`:
  - Interaksi geser slider pengguna diberikan status **High Priority** (merespons dalam 8 ms).
  - Render pembaruan grafik latar belakang di-downgrade menjadi **Transition Priority**. React menunda render grafik jika jari pengguna masih menggeser slider.
- Hasil: Pengalaman pengguna terasa sehalus aplikasi native desktop macOS/iOS.

---

## 12. Trade-offs

| Pendekatan Optimasi | Keuntungan Performa | Biaya Kompleksitas | Risiko Overengineering |
|---|---|---|---|
| **`React.memo` pada Komponen** | Mencegah re-render jika props identik | Biaya komputasi membandingkan props ($O(P)$) | Sia-sia jika props menyertakan fungsi inline anonim |
| **`useMemo` & `useCallback`** | Menjaga stabilitas referensi memori objek/fungsi | Alokasi memori tambahan untuk dependency array | Kode menjadi kembung jika dipakai untuk kalkulasi ringan ($A + B$) |
| **`useTransition` (Concurrent)** | Main thread tidak pernah membeku saat kalkulasi berat | Komponen bisa merender status *Stale* sesaat | Membutuhkan UI feedback visual (`isPending`) |

---

## 13. When To Use
- **Gunakan `key` yang Benar-Benar Unik (ID Database / UUID):** Wajib digunakan pada setiap elemen yang dipetakan menggunakan fungsi `.map()`.
- **Gunakan `useTransition`:** Saat menangani pembaruan state berat yang tidak boleh menghambat kelancaran input teks pengguna, klik tombol, atau animasi navigasi.
- **Gunakan `useMemo`:** Hanya untuk kalkulasi matematis yang terbukti lambat (misal: pengurutan 50.000 item, kalkulasi data kriptografi, atau operasi grafis canvas).

---

## 14. When NOT To Use
- **Jangan Pernah Menggunakan `key={Math.random()}`:** Memberikan key acak pada setiap render memaksa React menghancurkan (*Unmount*) dan membuat ulang (*Mount*) seluruh elemen DOM fisik pada setiap kali state berubah, menghancurkan fokus kursor dan memicu kebocoran memori.
- **Jangan Bungkus Setiap Fungsi dengan `useCallback` Secara Membabi Buta:** Membungkus handler klik sederhana pada tombol biasa tidak memberikan manfaat apa pun selain menambah alokasi memori array dependensi dan memperlambat waktu parsing kode.

---

## 15. Common Mistakes
1. **Mengubah State Secara Langsung (*Direct State Mutation*):** Menjalankan `state.push(item)` lalu `setState(state)`. Karena referensi objek array di memori tidak berubah (`oldArray === newArray`), React Fiber menganggap tidak ada perubahan dan melewatkan proses re-render!
2. **Infinite Render Loop di `useEffect`:** Memanggil `setState` di dalam `useEffect` tanpa menyertakan dependency array yang tepat, atau memasukkan objek baru sebagai dependensi tanpa `useMemo`.
3. **Mengabaikan Cleanup Function pada Subscriptions:** Membuka koneksi WebSocket atau event listener di dalam `useEffect` tanpa mengembalikan fungsi `return () => { socket.close(); }`, memicu kebocoran memori (*Memory Leaks*).

---

## 16. Best Practices

### Must Have
- Selalu perbarui state berbasis array/objek secara **Immutable** menggunakan spread operator (`[...prev, newItem]`) atau library pembantu seperti Immer.
- Patuhi **Rules of Hooks**: Panggil Hooks hanya di tingkat teratas komponen fungsional React (jangan pernah di dalam loops, kondisi if, atau fungsi bersarang).
- Gunakan pengidentifikasi stabil bisnis (`item.id`) sebagai prop `key`.

### Recommended
- Aktifkan **React Developer Tools Profiler** di browser untuk mendeteksi komponen mana yang memicu render ulang paling lama dan alasan re-render (*"Why did this render?"*).
- Bungkus aplikasi dengan `<React.StrictMode>` selama tahap pengembangan lokal untuk mendeteksi efek samping yang tidak murni (*Impure Side Effects*).

### Advanced
- Gabungkan **Custom Hooks** dengan arsitektur *Headless UI* (seperti Radix UI atau React Aria) untuk memisahkan logika interaktivitas dan aksesibilitas secara bersih dari lapisan visual CSS.

---

## 17. Troubleshooting

| Gejala Masalah | Indikasi Penyebab | Langkah Investigasi | Tindakan Perbaikan |
|---|---|---|---|
| **Error: `Rendered more hooks than during the previous render`** | Pemanggilan hook berada di dalam percabangan kondisi `if` | Periksa urutan pemanggilan hooks pada file komponen | Pindahkan seluruh pemanggilan hooks ke bagian paling atas fungsi komponen |
| **Input Form Kehilangan Fokus (*Focus Drop*) saat Mengetik** | Komponen anak didefinisikan di dalam tubuh fungsi komponen induk | Cek deklarasi fungsi komponen | Pindahkan deklarasi komponen anak ke luar komponen induk agar tipenya stabil |
| **Nilai State di dalam `setTimeout` Selalu Nilai Lama (*Stale Closure*)** | Closure JavaScript menangkap variabel state pada saat render awal | Periksa fungsi handler callback | Gunakan *Functional State Update*: `setCount(prev => prev + 1)` atau simpan di `useRef` |

---

## 18. Exercise
1. Bangun simulator in-memory React Fiber WorkLoop di Node.js yang memecah kalkulasi rekonsiliasi 10 node menjadi unit kerja (*Time-Slicing*).
2. Simulasikan interupsi prioritas: Jika ada event "USER_CLICK" masuk di tengah proses render, batalkan pekerjaan fiber berprioritas rendah dan jalankan event klik terlebih dahulu.
3. Buktikan bahwa perulangan daftar dengan key unik hanya memicu operasi pemindahan node tanpa pembuatan ulang elemen DOM.

---

## 19. Challenge
Rancang arsitektur komponen **Live Spreadsheet (Kloning Google Sheets)** di React:
1. Grid berukuran 100 kolom $\times$ 1.000 baris (Total 100.000 sel).
2. Ketika pengguna mengetik formula di sel `A1` yang memengaruhi 5.000 sel dependen lainnya, rancang arsitektur state management dan integrasikan `useTransition` agar pengetikan kursor tetap responsif pada 60 FPS tanpa macet!

---

## 20. Summary
React Fiber adalah mahakarya rekayasa penjadwalan komputasi grafis yang menyeimbangkan antara beban kalkulasi Virtual DOM dengan kelancaran responsivitas Main Thread browser. Dengan memahami cara kerja Fiber reconciler, menghormati aturan immutability, dan menguasai teknik pemisahan prioritas Concurrent React, seorang Full-Stack Engineer mampu membangun antarmuka web skala besar yang terasa secepat kilat dan bebas hambatan bagi jutaan pengguna.

---
[⬅️ BAB 01 Quiz & Challenge](../BAB-01-Arsitektur-Full-Stack-dan-Browser-Internals/BAB-01-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Server State vs Client State ➡️](./Module-02-Server-State-Client-State-dan-Optimistic-UI.md)
---
