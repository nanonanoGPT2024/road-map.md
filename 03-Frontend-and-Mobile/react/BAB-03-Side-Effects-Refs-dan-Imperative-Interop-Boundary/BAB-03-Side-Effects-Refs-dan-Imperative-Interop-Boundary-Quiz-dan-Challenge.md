# BAB-03-Side-Effects-Refs-dan-Imperative-Interop-Boundary: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi mandiri untuk menguji pemahaman konseptual, mekanika runtime, lifecycle side-effects, mutable reference semantics, serta pola integrasi imperatif pihak ketiga (interop boundary) pada React 18/19.

---

## Bagian 1: 5 Basic Questions

### Soal 1: Perbedaan Mendasar Render Phase vs Commit/Layout Phase
**Pertanyaan:** Mengapa pemanggilan fungsi yang memicu mutasi DOM eksternal atau mutasi variabel global dilarang dilakukan di root body functional component React?
- **A.** Karena React compiler akan melempar syntax error saat proses build.
- **B.** Karena render phase harus bersifat pure (murni), idempoten, dan dapat dipanggil berulang kali atau dibatalkan (aborted) oleh Concurrent Renderer sebelum commit phase terjadi.
- **C.** Karena mutasi DOM hanya diizinkan melalui handler `onClick`.
- **D.** Karena mutable variables akan di-reset otomatis menjadi `undefined` oleh JavaScript Virtual Machine setiap render.

> **Kunci Jawaban:** **B**  
> **Penjelasan Teknis:** React mengeksekusi render phase untuk menghitung perbedaan Virtual DOM (reconciliation). Pada mode Concurrent (React 18+), render phase dapat dijeda, diulang (re-invoked), atau dibuang jika terdapat update prioritas lebih tinggi. Jika side effect ditempatkan langsung di function body, efek samping tersebut akan terpicu secara liar sebelum UI benar-benar di-commit ke DOM riil. Side effect murni harus ditangguhkan ke commit phase menggunakan `useEffect`, `useLayoutEffect`, atau event handler.

---

### Soal 2: Mutasi `useRef` dan Re-rendering
**Pertanyaan:** Diberikan potongan kode berikut:
```tsx
const countRef = useRef<number>(0);

const handleIncrement = () => {
  countRef.current += 1;
  console.log(countRef.current);
};
```
Apa dampak pemanggilan `handleIncrement` terhadap siklus render komponen?
- **A.** Komponen segera me-render ulang untuk menampilkan nilai `countRef.current` yang baru.
- **B.** Komponen menjadwalkan re-render pada microtask queue berikutnya.
- **C.** Komponen tidak melakukan re-render sama sekali karena perubahan properti `.current` tidak memicu state dispatcher reconciliation.
- **D.** React melempar runtime warning bahwa ref hanya boleh dimutasi di dalam `useEffect`.

> **Kunci Jawaban:** **C**  
> **Penjelasan Teknis:** `useRef` mengembalikan objek JavaScript stabil `{ current: initialValue }` yang persistensinya dipertahankan sepanjang masa hidup (lifetime) instance fiber komponen. Memodifikasi properti `.current` adalah mutasi referensi biasa yang tidak memberi tahu React scheduler bahwa ada perubahan state, sehingga reconciliation cycle tidak dipicu.

---

### Soal 3: Lifecycle Eksekusi Cleanup Function pada `useEffect`
**Pertanyaan:** Kapan tepatnya cleanup function yang dikembalikan oleh `useEffect` dieksekusi oleh React runtime?
- **A.** Hanya ketika komponen di-unmount dari DOM tree.
- **B.** Sebelum komponen me-render ulang, tepat di awal render phase berikutnya.
- **C.** Sebelum effect berikutnya dieksekusi pada re-render yang memicu perubahan dependency, dan saat komponen di-unmount.
- **D.** Bersamaan dengan event queue tick browser berikutnya sebelum JavaScript call stack kosong.

> **Kunci Jawaban:** **C**  
> **Penjelasan Teknis:** Cleanup function pada `useEffect` bertindak sebagai teardown dari efek samping sebelumnya. Pada setiap re-render di mana array dependencies mengalami perubahan nilai (via `Object.is`), React akan menjalankan cleanup function dari render sebelumnya terlebih dahulu sebelum mengeksekusi callback effect yang baru, serta mengeksekusinya terakhir kali ketika komponen di-unmount.

---

### Soal 4: Eksekusi Efek dengan Empty Dependency Array `[]`
**Pertanyaan:** Pada React 18 dalam mode `<React.StrictMode>`, apa yang terjadi saat komponen dengan `useEffect(() => { ... return () => { ... }; }, [])` pertama kali di-mount ke DOM di development mode?
- **A.** Effect dieksekusi tepat 1 kali, dan cleanup tidak pernah dijalankan hingga unmount permanen.
- **B.** Effect dieksekusi 1 kali, cleanup 1 kali, lalu effect dieksekusi kembali untuk kedua kalinya (mount -> unmount -> remount simulation).
- **C.** Strict Mode mengabaikan empty dependency array dan mengeksekusinya di setiap frame animasi.
- **D.** React melempar error peringatan bahwa dependency array tidak boleh kosong.

> **Kunci Jawaban:** **B**  
> **Penjelasan Teknis:** Dalam Strict Mode development, React 18+ sengaja mensimulasikan mount-unmount-remount siklus langsung setelah inisialisasi awal. Tujuannya adalah menguji apakah developer telah menulis cleanup logic yang benar (idempoten dan bebas memory leak) untuk menangani pembersihan listener, koneksi socket, atau langganan eksternal.

---

### Soal 5: Kapan `useLayoutEffect` Harus Digunakan Dibanding `useEffect`?
**Pertanyaan:** Skenario manakah yang mewajibkan penggunaan `useLayoutEffect` daripada `useEffect` standar?
- **A.** Mengambil data dari REST API atau GraphQL server saat komponen di-mount.
- **B.** Mengukur dimensi layout DOM (misalnya `getBoundingClientRect()`) dan mengubah state atau gaya DOM secara sinkron sebelum browser melakukan repainting visual untuk mencegah flickering UI.
- **C.** Memasang event listener global pada objek `window` untuk menangani tombol shortcut keyboard.
- **D.** Melakukan logging metrik analytics tracking ke remote server.

> **Kunci Jawaban:** **B**  
> **Penjelasan Teknis:** `useEffect` dieksekusi secara asinkron setelah browser menyelesaikan proses layouting dan painting layar, sehingga tidak memblokir render frame utama. Namun, jika state diubah di dalam `useEffect` berdasarkan pembacaan dimensi DOM, pengguna akan melihat kedipan visual (flicker). `useLayoutEffect` dieksekusi secara sinkron tepat setelah mutasi DOM selesai tetapi sebelum browser melakukan painting ke layar fisik.

---

## Bagian 2: 5 Intermediate Questions

### Soal 6: Analisis Stale Closure dalam `useEffect`
**Pertanyaan:** Perhatikan potongan kode berikut:
```tsx
function TimerComponent() {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const timerId = setInterval(() => {
      setSeconds(seconds + 1);
    }, 1000);

    return () => clearInterval(timerId);
  }, []);

  return <div>{seconds}</div>;
}
```
Mengapa nilai `seconds` pada layar akan berhenti bertambah setelah angka 1?
- **A.** `setInterval` secara otomatis dihentikan oleh browser karena dianggap interval zombie.
- **B.** Callback di dalam `setInterval` menangkap (captures) variabel `seconds` dari scope lexical render awal (nilai `0`). Akibat empty dependency array `[]`, callback tidak pernah diperbarui dan selalu mengeksekusi `setSeconds(0 + 1)`.
- **C.** State `seconds` bernilai immutable sehingga tidak dapat dimutasi lebih dari satu kali tanpa `useReducer`.
- **D.** `clearInterval` dieksekusi secara instan sebelum interval pertama selesai berputar.

> **Kunci Jawaban:** **B**  
> **Penjelasan Teknis:** Ini adalah fenomena *stale closure*. Fungsi callback yang diberikan ke `setInterval` mengunci referensi variabel `seconds` pada render pertama di mana `seconds = 0`. Solusi yang benar adalah menggunakan updater function form `setSeconds((prev) => prev + 1)` yang tidak memerlukan variabel luar masuk ke dalam dependency array, atau menyertakan `seconds` dalam dependencies array dengan konsekuensi interval di-reset setiap detik.

---

### Soal 7: `useImperativeHandle` dan Boundary Keamanan Komponen Anak
**Pertanyaan:** Mengapa arsitektur modern React merekomendasikan penggunaan `forwardRef` yang dipadukan dengan `useImperativeHandle` dibandingkan meneruskan `ref` mentah langsung ke elemen native DOM di komponen anak?
- **A.** Karena `ref` native tidak mendukung TypeScript typing secara statis.
- **B.** Untuk menerapkan prinsip enkapsulasi (information hiding) dan Law of Demeter, sehingga komponen induk hanya memiliki akses ke metode terdefinisi (seperti `.focus()`, `.reset()`) tanpa mengekspos seluruh properti mutable DOM node internal.
- **C.** Karena native HTMLInputElement tidak dapat di-binding lebih dari satu kali dalam hierarki pohon komponen.
- **D.** Supaya React dapat mengonversi imperative code menjadi functional declarative hook secara otomatis di background.

> **Kunci Jawaban:** **B**  
> **Penjelasan Teknis:** Jika komponen anak hanya meneruskan `ref` mentah ke DOM node, komponen induk bebas memanipulasi style, atribut, innerHTML, atau bahkan menghapus node tersebut, merusak konsistensi virtual DOM React. Dengan `useImperativeHandle`, komponen anak mendefinisikan API kontrak eksplisit yang aman dan membatasi kontrol komponen induk hanya pada instruksi yang diizinkan.

---

### Soal 8: Objek Non-Primitif dalam Dependency Array dan Infinite Re-render
**Pertanyaan:** Analisis kode di bawah ini:
```tsx
function UserProfile({ userId }: { userId: string }) {
  const [data, setData] = useState<UserData | null>(null);
  
  const options = { timeout: 5000, traceId: userId };

  useEffect(() => {
    fetchUserData(userId, options).then(setData);
  }, [options]);

  return <div>{data?.name}</div>;
}
```
Apa dampak eksekusi kode di atas terhadap lifecycle komponen?
- **A.** Berjalan normal dan hanya melakukan fetch satu kali ketika `userId` berubah.
- **B.** Menyebabkan infinite re-render loop karena objek `options` dideklarasikan ulang sebagai instans memori baru (referential inequality) di setiap siklus render, menyebabkan `useEffect` dipicu terus-menerus.
- **C.** `useEffect` membandingkan properti `options` secara *deep equality*, sehingga aman dari infinite loop.
- **D.** React melempar compile time error karena objek dilarang berada di dalam dependency array.

> **Kunci Jawaban:** **B**  
> **Penjelasan Teknis:** React dependency comparison menggunakan mekanisme `Object.is` (shallow comparison). Pada setiap render, objek `options` dibuat ulang di memory heap dengan pointer reference yang berbeda. Ketika `useEffect` mengevaluasi dependencies, `Object.is(oldOptions, newOptions)` bernilai `false`, memicu pemanggilan `fetchUserData`, yang memanggil `setData`, yang memicu render baru, menghasilkan infinite loop tak berujung. Solusinya: bungkus dengan `useMemo`, pindahkan deklarasi ke dalam effect, atau ekstrak nilai primitif ke dependency array.

---

### Soal 9: Callback Ref vs `useEffect` untuk Integrasi Elemen Dinamis
**Pertanyaan:** Kapan teknik *Callback Ref* (`ref={(node) => ...}`) lebih unggul dibandingkan kombinasi `useRef` + `useEffect` untuk mengukur atau menginisialisasi node DOM?
- **A.** Callback Ref dieksekusi lebih cepat karena mem-bypass garbage collector.
- **B.** Ketika elemen DOM dirender secara kondisional (`{isVisible && <Modal />}`), `useRef.current` tidak memberikan notifikasi perubahan saat node di-mount/unmount, sedangkan Callback Ref di-invoke secara deterministik dengan argumen node DOM saat mount dan `null` saat unmount.
- **C.** Callback Ref wajib digunakan jika komponen menggunakan CSS Grid atau Flexbox.
- **D.** Callback Ref tidak dapat menyebabkan re-render di browser berbasis WebKit.

> **Kunci Jawaban:** **B**  
> **Penjelasan Teknis:** Objek ref yang dibuat oleh `useRef` tidak memiliki mekanisme reactive notification ketika properti `.current` berubah dari `null` ke node HTML aktual. Jika sebuah elemen muncul secara kondisional, `useEffect` yang memiliki dependency array kosong tidak akan tahu kapan node tersebut benar-benar ada di DOM. Callback Ref menjamin eksekusi fungsi segera setelah node DOM diikat atau dilepas oleh React engine.

---

### Soal 10: Mekanisme Race Condition Handling Menggunakan `useEffect` Cleanup Flag
**Pertanyaan:** Perhatikan pola pemanggilan asynchronous berikut:
```tsx
useEffect(() => {
  let isSubscribed = true;

  fetchData(query).then((response) => {
    if (isSubscribed) {
      setData(response);
    }
  });

  return () => {
    isSubscribed = false;
  };
}, [query]);
```
Bagaimana flag boolean `isSubscribed` mencegah race condition saat user mengetik kata kunci baru secara cepat?
- **A.** Flag tersebut membatalkan request HTTP TCP packet secara instan di level OS socket.
- **B.** Ketika query baru masuk, cleanup function dari render sebelumnya dieksekusi secara sinkron dan mengubah `isSubscribed` menjadi `false`, sehingga respons fetch lama yang lambat (out-of-order response) akan diabaikan dan tidak menimpa state terbaru.
- **C.** Flag tersebut menghentikan parsing JSON di browser main thread.
- **D.** Flag tersebut mencegah Promise melempar uncaught exception.

> **Kunci Jawaban:** **B**  
> **Penjelasan Teknis:** Request asinkron jaringan tidak dijamin selesai sesuai urutan pengiriman. Jika request pertama (query "A") butuh 1000ms dan request kedua (query "AB") butuh 200ms, tanpa proteksi response "A" akan tiba terakhir dan menimpa data "AB". Boolean flag dalam closure cleanup menandai effect sebelumnya sebagai *obsolete*, memastikan hanya respon dari effect siklus aktif yang diizinkan memperbarui state komponen.

---

## Bagian 3: 3 Skenario Kasus Nyata Produksi

### Skenario 1: Penanganan Memory Leak dan Zombie Listener pada WebSockets / SSE
**Konteks Masalah:**  
Sebuah aplikasi bursa kripto mengalami crash browser tab pada user setelah dibiarkan menyala selama 4 jam. Setelah dianalisis melalui Chrome DevTools Memory Heap Snapshot, ditemukan ribuan detached DOM nodes dan lonjakan event listener WebSocket `message` yang terus mendengarkan event harga lama.

```tsx
// IMPLEMENTASI BERMASALAH DI KODE LAMA
function CryptoLivePrice({ symbol }: { symbol: string }) {
  const [price, setPrice] = useState<number>(0);

  useEffect(() => {
    const ws = new WebSocket(`wss://stream.exchange.com/rates?symbol=${symbol}`);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setPrice(data.price);
    };
    // Dev lupa menambahkan return cleanup function!
  }, [symbol]);

  return <div className="ticker">{symbol}: {price}</div>;
}
```

**Analisis Masalah & Dampak Sistem:**
1. Setiap kali prop `symbol` berganti (atau saat HMR / hot reload / remounting terjadi), koneksi `WebSocket` baru dibuka tanpa pernah menutup socket lama (`ws.close()`).
2. Event listener lama tetap hidup di background browser context, menerima frame stream, mengalokasikan memori, dan terus memicu state updater pada komponen yang mungkin sudah tidak relevan.

**Solusi Standar Produksi:**
```tsx
function CryptoLivePrice({ symbol }: { symbol: string }) {
  const [price, setPrice] = useState<number>(0);

  useEffect(() => {
    let ws: WebSocket | null = new WebSocket(
      `wss://stream.exchange.com/rates?symbol=${encodeURIComponent(symbol)}`
    );

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        setPrice(data.price);
      } catch (err) {
        console.error("Gagal mendeserialisasi data WebSocket payload:", err);
      }
    };

    ws.onerror = (err) => {
      console.error(`WebSocket error pada stream ${symbol}:`, err);
    };

    // TEARDOWN CONTRACT MUTLAK
    return () => {
      if (ws) {
        // Hilangkan handler untuk mencegah firing event saat socket dalam proses closing
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
          ws.close(1000, "Component unmounted or symbol changed");
        }
        ws = null;
      }
    };
  }, [symbol]);

  return <div className="ticker">{symbol}: {price}</div>;
}
```

---

### Skenario 2: AbortController untuk Mencegah Race Condition & Network Overhead
**Konteks Masalah:**  
Komponen *Typeahead Search Bar* sering menampilkan hasil pencarian yang tidak sinkron dengan input teks pengguna. Saat pengguna mengetik kata "REACT" lalu menghapus cepat menjadi "RE", respons API pencarian untuk "REACT" yang berukuran besar selesai belakangan dan menimpa hasil pencarian untuk "RE".

**Analisis Masalah:**
1. Latensi jaringan bervariasi; urutan penyelesaian Promise HTTP tidak deterministic (Out-of-order arrival).
2. Request yang sudah usang tetap mengonsumsi bandwidth klien dan bandwidth server API pencarian.

**Solusi Standar Produksi Menggunakan `AbortController`:**
```tsx
function SearchTypeahead({ query }: { query: string }) {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Abaikan input kosong
    if (!query.trim()) {
      setResults([]);
      setIsLoading(false);
      return;
    }

    const abortController = new AbortController();
    const { signal } = abortController;

    const executeFetch = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `/api/v1/search?q=${encodeURIComponent(query)}`,
          { signal }
        );

        if (!response.ok) {
          throw new Error(`HTTP Error status: ${response.status}`);
        }

        const data: SearchResult[] = await response.json();
        setResults(data);
      } catch (err: unknown) {
        // Abaikan error abort karena ini adalah ekspektasi lifecycle normal saat typing
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setError(err instanceof Error ? err.message : "Terjadi kesalahan sistem");
      } finally {
        if (!signal.aborted) {
          setIsLoading(false);
        }
      }
    };

    executeFetch();

    // TEARDOWN: Batalkan request HTTP di level transport browser
    return () => {
      abortController.abort();
    };
  }, [query]);

  return (
    <div>
      {isLoading && <span className="loader">Mencari...</span>}
      {error && <span className="error">{error}</span>}
      <ul>
        {results.map((item) => (
          <li key={item.id}>{item.title}</li>
        ))}
      </ul>
    </div>
  );
}
```

---

### Skenario 3: Interop Boundary Pihak Ketiga (Integrasi Chart.js / Leaflet / Mapbox Imperative Lifecycle)
**Konteks Masalah:**  
Sebuah library visualisasi grafik imperatif berbasis canvas (misalnya library pihak ketiga yang membutuhkan manipulasi DOM langsung) diintegrasikan ke dalam dashboard analitik. Komponen sering mengalami error: `Canvas is already in use. Chart with id '0' must be destroyed before the canvas can be reused`.

**Analisis Masalah:**
1. Library imperatif mengasumsikan kepemilikan mutlak atas node DOM tertentu dan mengikat konteks internal.
2. Ketika React me-render ulang komponen (misalnya karena perubahan filter tanggal atau resize container), instance instance grafik lama masih mengikat elemen canvas tersebut. Jika inisialisasi dipanggil ulang tanpa destroy, terjadi memory leak dan conflict instance.

**Solusi Standar Produksi:**
```tsx
import React, { useRef, useLayoutEffect, useImperativeHandle, forwardRef } from "react";
// Asumsi type stub ThirdPartyChartInstance
interface ThirdPartyChartInstance {
  updateData: (newData: number[]) => void;
  destroy: () => void;
  resize: () => void;
}

declare function createThirdPartyChart(canvas: HTMLCanvasElement, options: any): ThirdPartyChartInstance;

export interface ChartHandle {
  exportAsImage: () => string | null;
  forceReset: () => void;
}

interface AnalyticsChartProps {
  dataPoints: number[];
  chartType: "line" | "bar";
}

export const AnalyticsChart = forwardRef<ChartHandle, AnalyticsChartProps>(
  function AnalyticsChart({ dataPoints, chartType }, ref) {
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const chartInstanceRef = useRef<ThirdPartyChartInstance | null>(null);

    // EKSPOS HANYA API YANG AMAN KE PARENT
    useImperativeHandle(ref, () => ({
      exportAsImage: () => {
        if (canvasRef.current) {
          return canvasRef.current.toDataURL("image/png");
        }
        return null;
      },
      forceReset: () => {
        if (chartInstanceRef.current) {
          chartInstanceRef.current.destroy();
          if (canvasRef.current) {
            chartInstanceRef.current = createThirdPartyChart(canvasRef.current, {
              data: dataPoints,
              type: chartType,
            });
          }
        }
      },
    }), [dataPoints, chartType]);

    // SIKLUS INISIALISASI & TEARDOWN IMPERATIVE
    useLayoutEffect(() => {
      const canvasElement = canvasRef.current;
      if (!canvasElement) return;

      // Inisialisasi library pihak ketiga
      const instance = createThirdPartyChart(canvasElement, {
        data: dataPoints,
        type: chartType,
      });

      chartInstanceRef.current = instance;

      // TEARDOWN MUTLAK: Lepas instance sebelum instansiasi baru atau unmount
      return () => {
        instance.destroy();
        chartInstanceRef.current = null;
      };
    }, [chartType]); // Inisialisasi ulang hanya jika tipe diagram berubah

    // UPDATE VALUE SECARA EFISIEN TANPA MENGHANCURKAN INSTANCE CANVAS
    useLayoutEffect(() => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.updateData(dataPoints);
      }
    }, [dataPoints]);

    return (
      <div className="chart-wrapper">
        <canvas ref={canvasRef} />
      </div>
    );
  }
);
```

---

## Bagian 4: Practical Chapter Challenge: Custom Hook `useEventListener` & `useIntersectionObserver`

### Deskripsi Tantangan
Rancang dan bangun arsitektur custom hook produksi bernama `useEventSubscription` dan `useImperativeBoundaryRef` dengan kriteria teknis berikut:

1. **Safety & Zero Memory Leak:**
   - Listener harus terikat secara otomatis ke target (`window`, `document`, atau `HTMLElement` via Ref).
   - Wajib menangani event handler terkini menggunakan teknik `useRef` (Latest Ref Pattern) agar pendaftaran ulang event listener (`addEventListener` / `removeEventListener`) tidak terjadi secara sia-sia setiap kali function handler berubah referensi.
2. **Support Dynamic Ref Target:**
   - Harus mampu menerima target berupa ref objek yang nilainya bisa bernilai `null` saat inisialisasi awal.
3. **Strict Mode Resilient:**
   - Harus lolos uji remounting siklus ganda tanpa meninggalkan handler duplikat di runtime.

### Solusi Referensi Implementasi:

```tsx
import { useEffect, useRef, useLayoutEffect, RefObject } from "react";

/**
 * Hook bantuan untuk selalu mengikat callback terbaru tanpa memicu pendaftaran ulang listener.
 */
export function useLatest<T>(value: T): RefObject<T> {
  const ref = useRef<T>(value);
  useLayoutEffect(() => {
    ref.current = value;
  });
  return ref;
}

type EventTargetElement = Window | Document | HTMLElement | null | undefined;

/**
 * Production-ready Event Listener Hook
 */
export function useEventSubscription<K extends keyof WindowEventMap>(
  eventName: K,
  handler: (event: WindowEventMap[K]) => void,
  target?: Window | null,
  options?: boolean | AddEventListenerOptions
): void;
export function useEventSubscription<K extends keyof HTMLElementEventMap, T extends HTMLElement>(
  eventName: K,
  handler: (event: HTMLElementEventMap[K]) => void,
  target: RefObject<T | null>,
  options?: boolean | AddEventListenerOptions
): void;
export function useEventSubscription(
  eventName: string,
  handler: (event: any) => void,
  target: any = typeof window !== "undefined" ? window : null,
  options?: boolean | AddEventListenerOptions
): void {
  const savedHandler = useLatest(handler);

  useEffect(() => {
    // Evaluasi apakah target berupa RefObject atau DOM node langsung
    const targetElement: EventTargetElement = 
      target && "current" in target ? target.current : target;

    if (!targetElement || !targetElement.addEventListener) {
      return;
    }

    // Proxy listener yang selalu memanggil closure terbaru
    const eventListener: EventListener = (event: Event) => {
      if (savedHandler.current) {
        savedHandler.current(event);
      }
    };

    targetElement.addEventListener(eventName, eventListener, options);

    return () => {
      targetElement.removeEventListener(eventName, eventListener, options);
    };
  }, [eventName, target, options]);
}
```

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan daftar centang berikut untuk mengaudit pemahaman Anda terhadap seluruh materi pada Bab 03:

- [ ] **Mekanisme Eksekusi `useEffect`:** Saya memahami bahwa `useEffect` dieksekusi secara asinkron setelah browser painting selesai, dan saya tahu kapan harus memilih `useEffect` daripada `useLayoutEffect`.
- [ ] **Teardown Contract:** Saya selalu menyediakan cleanup function untuk setiap side effect yang membuka koneksi, mendaftarkan listener, atau membuat asynchronous interval/timeout.
- [ ] **Pemberantasan Stale Closures:** Saya mampu mengidentifikasi closure basi dalam callback asinkron dan mengatasinya dengan functional state updates (`prev => ...`) atau Latest Ref Pattern.
- [ ] **Komparasi Nilai Dependency:** Saya memahami bahwa dependency array React dibandingkan secara referensial (`Object.is`) dan tidak memasukkan objek literal / fungsi anonim tanpa memoization (`useMemo` / `useCallback`).
- [ ] **Semantik `useRef`:** Saya mengerti bahwa memutasi `.current` adalah operasi bebas side-effect reconciliation yang tidak memicu re-render dan aman digunakan untuk menyimpan instance mutable pihak ketiga.
- [ ] **Boundary Enkapsulasi Imperatif:** Saya menguasai integrasi `forwardRef` bersama `useImperativeHandle` untuk mengekspos public interface yang aman ke komponen induk.
- [ ] **Mitigasi Race Condition Jaringan:** Saya mampu mengimplementasikan proteksi balapan respon asinkron menggunakan boolean cleanup flag atau API native `AbortController`.
- [ ] **Resiliensi Strict Mode:** Seluruh effect yang saya tulis mampu bertahan dari siklus ganda mount -> unmount -> remount tanpa menyebabkan memory leak atau error duplikasi.
