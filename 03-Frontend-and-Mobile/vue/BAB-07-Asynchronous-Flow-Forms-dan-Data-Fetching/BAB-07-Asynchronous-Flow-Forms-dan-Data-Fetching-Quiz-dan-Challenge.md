# BAB-07-Asynchronous-Flow-Forms-dan-Data-Fetching: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang untuk menguji, memvalidasi, dan mengkonsolidasikan pemahaman arsitektural serta teknis seputar pengelolaan formulir tingkat lanjut, *asynchronous flow control*, pembatalan request, integrasi server-state management (Vue Query / TanStack Query), dan mitigasi konkurensi data pada ekosistem Vue 3.

---

## Bagian 1: Basic Questions (5 Soal)

### Pertanyaan 1: Mekanisme Two-Way Binding `v-model` dan Modifiers
**Pertanyaan:**
Bagaimana cara kerja sintaksis internal `v-model` pada komponen kustom di Vue 3 secara default, dan apa perbedaan fungsional antara modifier `.lazy`, `.number`, serta `.trim` pada elemen formulir native?

<details>
<summary>Jawaban & Pembahasan</summary>

**Pembahasan:**
Secara default pada Vue 3, direktif `v-model="foo"` pada komponen kustom merupakan *syntactic sugar* untuk kombinasi passing prop dan event listener:
```vue
:modelValue="foo"
@update:modelValue="$event => foo = $event"
```
Jika menggunakan argumen khusus seperti `v-model:title="bar"`, transformasinya menjadi `:title="bar"` dan `@update:title="$event => bar = $event"`.

Pada elemen formulir native:
1. `.lazy`: Mengubah trigger sinkronisasi nilai reactive dari event `input` (setiap keystroke) menjadi event `change` (saat elemen kehilangan fokus/blur atau commit nilai dilakukan).
2. `.number`: Melakukan typecast otomatis nilai string input menjadi number via `parseFloat()`. Jika parsing menghasilkan `NaN` atau input gagal diparsing, nilai fallback kembali ke string asli.
3. `.trim`: Menjalankan sanitasi whitespace otomatis (`String.prototype.trim()`) pada awal dan akhir input string sebelum disimpan ke dalam state reaktif.
</details>

---

### Pertanyaan 2: AbortController dan Penghentian Network Request
**Pertanyaan:**
Mengapa penggunaan native Web API `AbortController` krusial dalam siklus hidup komponen Vue saat melakukan data fetching di `onMounted` atau composable data-fetching? Apa implikasi teknis jika `abort()` tidak dipanggil saat komponen di-unmount?

<details>
<summary>Jawaban & Pembahasan</summary>

**Pembahasan:**
`AbortController` menyediakan `signal` (`controller.signal`) yang dapat diteruskan ke `fetch()` atau library seperti Axios (`signal: controller.signal`).

Implikasi jika pembatalan tidak dilakukan:
1. **Memory Leaks & Zombie Callbacks:** Callback promise yang selesai setelah komponen di-unmount tetap mengeksekusi mutasi referensi reaktif (`state.value = data`), memicu referensi siklik pada Garbage Collector.
2. **Race Conditions:** Jika pengguna bernavigasi bolak-balik dengan cepat, request pertama yang tertunda dapat menyelesaikan transfer datanya setelah request kedua selesai, menimpa state terkini dengan payload usang (*stale overwrite*).
3. **Pemborosan Bandwidth/Koneksi:** Browser memiliki batasan koneksi konkuren HTTP/1.1 (6 koneksi per host). Membiarkan request usang tetap berjalan menunda request prioritas tinggi berikutnya.
</details>

---

### Pertanyaan 3: Server State vs. Client State
**Pertanyaan:**
Jelaskan perbedaan mendasar antara *Server State* dan *Client State* dalam konteks aplikasi Vue modern, dan mengapa mengelola server state semata-mata dengan Pinia sering menimbulkan masalah redundansi arsitektural (*anti-pattern*)?

<details>
<summary>Jawaban & Pembahasan</summary>

**Pembahasan:**
* **Client State (UI State):** Data yang dimiliki dan dikontrol sepenuhnya oleh antarmuka pengguna lokal (misalnya status modal buka/tutup, tab aktif, step wizard form, tema gelap/terang). State ini bersifat sinkron dan deterministik.
* **Server State:** Data yang berada di remote server, diakses secara asinkron, dimiliki oleh pihak eksternal, dan berpotensi berubah sewaktu-waktu di luar kendali klien (misalnya daftar transaksi, inventaris stok, data user profile).

**Alasan redundansi menggunakan Pinia untuk Server State:**
Menggunakan global store murni (seperti Pinia) untuk server state memaksa developer mengimplementasikan sendiri boilerplate masif:
- State pending, success, error, idle.
- Mekanisme *caching*, TTL (time-to-live), dan *invalidation logic*.
- *Deduplication* atas request identik yang dipanggil simultan.
- *Refetch on window focus* atau *reconnect retry*.
Library dedicated seperti TanStack Query (Vue Query) memisahkan server cache dari client store, meminimalkan memory footprint dan bug sinkronisasi.
</details>

---

### Pertanyaan 4: Peran Axios Request & Response Interceptors
**Pertanyaan:**
Pada lapisan abstraksi HTTP client, apa perbedaan tanggung jawab teknis antara *Request Interceptor* dan *Response Interceptor*, serta sebutkan dua use case tipikal masing-masing?

<details>
<summary>Jawaban & Pembahasan</summary>

**Pembahasan:**
* **Request Interceptor:** Dijalankan sebelum sebuah HTTP request dikirimkan ke jaringan.
  - *Use Case 1 (Token Injection):* Membaca accessToken dari secure storage/memory dan menyuntikkannya ke header `Authorization: Bearer <token>`.
  - *Use Case 2 (Metadata Injection & Tracing):* Menambahkan header pelacakan microservice seperti `X-Correlation-ID`, `X-Client-Version`, atau timestamp request.
* **Response Interceptor:** Dijalankan segera setelah respons diterima dari server sebelum promise di-resolve ke komponen pemanggil.
  - *Use Case 1 (Global Error Normalization):* Menangkap error HTTP 401 untuk memicu refresh-token rotation atau redirect ke authentication flow.
  - *Use Case 2 (Payload Unwrapping):* Mengeluarkan nested property data (misalnya mengembalikan `response.data.data` langsung daripada membungkus objek AxiosResponse penuh).
</details>

---

### Pertanyaan 5: Async Component dan `<Suspense>`
**Pertanyaan:**
Bagaimana deklarasi `defineAsyncComponent` bekerja dalam memotong bundle size (code-splitting), dan apa peran elemen `<Suspense>` dalam merender fallback UI ketika async dependency sedang dimuat?

<details>
<summary>Jawaban & Pembahasan</summary>

**Pembahasan:**
`defineAsyncComponent` menerima fungsi loader yang mengembalikan Promise modul dinamis (misalnya `() => import('./HeavyModal.vue')`). Bundler seperti Vite/Rollup otomatis memisahkan komponen tersebut menjadi chunk file `.js` terpisah yang hanya diunduh saat komponen benar-benar dirender di viewport/DOM.

Elemen `<Suspense>` adalah built-in component di Vue 3 yang mengoordinasikan rendering asinkron pada hierarki komponen turunan:
- Memiliki dua slot: `#default` dan `#fallback`.
- Jika komponen di `#default` memiliki `async setup()` atau berupa async component yang belum tuntas diunduh, `<Suspense>` mempertahankan rendering slot `#fallback` (misal skeleton loading spinner) hingga seluruh async child selesai di-resolve.
</details>

---

## Bagian 2: Intermediate Questions (5 Soal)

### Pertanyaan 6: Debouncing Asinkron vs. Race Conditions pada Search Autocomplete
**Pertanyaan:**
Mengapa teknik *debouncing* saja tidak cukup untuk menjamin kebenaran data pada fitur pencarian autocomplete dengan dependensi API asinkron? Bagaimana arsitektur penanganan *race condition* yang benar menggunakan kombinasi debounce dan token pembatalan?

<details>
<summary>Jawaban & Pembahasan</summary>

**Pembahasan:**
Debounce hanya menunda eksekusi request selama periode inaktivitas (misalnya 300ms). Namun, debounce **tidak mengontrol latensi jaringan**:
- User mengetik "vue", request A berjalan (latensi jaringan 800ms).
- User mengetik "vue router", request B berjalan (latensi jaringan 200ms).
- Request B selesai lebih dahulu dan menampilkan hasil "vue router".
- 600ms kemudian, Request A baru selesai dan menimpa UI dengan hasil pencarian "vue" (out-of-order response).

**Solusi Arsitektural:**
1. Menyimpan referensi `AbortController` aktif di closure/ref composable.
2. Setiap kali debounced trigger terpanggil, eksekusi `activeController.value?.abort()` sebelum membuat controller baru.
3. Kirimkan `signal: activeController.value.signal` ke fetcher.
4. Tangani error `DOMException (AbortError)` atau `axios.isCancel(err)` agar tidak dianggap sebagai failure error di antarmuka.
</details>

---

### Pertanyaan 7: Optimistic UI Updates dan Rollback Strategy
**Pertanyaan:**
Jelaskan alur siklus hidup *Optimistic Updates* pada mutation data (misalnya aksi "Like Post" atau "Toggle Todo"). Bagaimana struktur data cache harus disimpan dan dipulihkan ketika server mengembalikan respons error HTTP 500?

<details>
<summary>Jawaban & Pembahasan</summary>

**Pembahasan:**
Alur siklus hidup Optimistic Update:
1. **OnMutate:**
   - Batalkan query aktif yang sedang berjalan untuk endpoint terkait (`queryClient.cancelQueries({ queryKey })`).
   - Buat *snapshot* dari cache state saat ini (`previousData = queryClient.getQueryData(queryKey)`).
   - Manipulasi cache secara langsung dengan nilai baru yang diestimasikan sukses (`queryClient.setQueryData(queryKey, updater)`).
   - Return objek konteks yang memuat `previousData`.
2. **OnError:**
   - Tangkap konteks error dan kembalikan state cache ke snapshot awal (`queryClient.setQueryData(queryKey, context.previousData)`).
   - Tampilkan notifikasi error/toast kepada pengguna bahwa aksi gagal disinkronkan ke server.
3. **OnSettled:**
   - Selalu picu `queryClient.invalidateQueries({ queryKey })` untuk memastikan data lokal sinkron 100% dengan database authoritative.
</details>

---

### Pertanyaan 8: Refresh Token Rotation dan Concurrency Queue
**Pertanyaan:**
Ketika accessToken kedaluwarsa dan terdapat 5 request HTTP paralel yang secara serentak menerima status HTTP 401 Unauthorized, bagaimana mencegah terjadinya 5 kali request duplikat ke endpoint `/auth/refresh`? Tuliskan arsitektur queue mutex pada Axios response interceptor!

<details>
<summary>Jawaban & Pembahasan</summary>

**Pembahasan:**
Jika beberapa request gagal secara bersamaan karena 401, refresh token hanya boleh dipanggil tepat satu kali. Request lain harus ditahan di antrean (*in-flight promise queue*) sampai refresh token selesai, lalu di-retry menggunakan token baru.

**Konsep Implementasi Interceptor:**
```ts
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token!);
    }
  });
  failedQueue = [];
};

axiosInstance.interceptors.response.use(
  res => res,
  async error => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(newToken => {
          originalRequest.headers['Authorization'] = `Bearer ${newToken}`;
          return axiosInstance(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const { data } = await axios.post('/api/auth/refresh');
        const newToken = data.accessToken;
        authStore.setToken(newToken);
        processQueue(null, newToken);
        originalRequest.headers['Authorization'] = `Bearer ${newToken}`;
        return axiosInstance(originalRequest);
      } catch (refreshErr) {
        processQueue(refreshErr, null);
        authStore.forceLogout();
        return Promise.reject(refreshErr);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);
```
</details>

---

### Pertanyaan 9: Validasi Form Skema (Vee-Validate / Zod) vs. State Reaktif Native
**Pertanyaan:**
Apa keuntungan menggunakan library skema deklaratif seperti Zod bersama `vee-validate` dibandingkan membangun validasi form kustom hanya dengan `watch`, `computed`, dan `v-model` biasa pada form multi-step kompleks?

<details>
<summary>Jawaban & Pembahasan</summary>

**Pembahasan:**
1. **Type-Safety & Single Source of Truth:** Skema Zod dapat di-infer langsung menjadi tipe TypeScript (`z.infer<typeof schema>`). Kontrak tipe antara backend DTO, validasi frontend, dan form data dijamin identik.
2. **Field State Granularity:** Validasi manual sering kesulitan melacak flag *touched*, *dirty*, *validating*, dan *error bag* per-field secara efisien. `vee-validate` mengelola status ini di level input individual tanpa memicu re-render keseluruhan form.
3. **Cross-Field & Conditional Validation:** Menangani ketergantungan antar field (misal: "Field B wajib diisi jika opsi A dipilih" atau konfirmasi password) jauh lebih bersih dengan mekanisme skema (`refine()`, `superRefine()`) dibanding rantai `computed`/`watch` manual yang rawan circular dependency.
4. **Transformasi Nilai Otomatis:** Zod mampu melakukan parsing, sanitasi, dan coercing tipe (misalnya mengubah string kosong menjadi `undefined` atau string angka menjadi `number`) sebelum dikirimkan ke mutation pipeline.
</details>

---

### Pertanyaan 10: Invalidation Granularity pada TanStack Query / Vue Query
**Pertanyaan:**
Diberikan query key terstruktur: `['todos', 'detail', todoId]` dan `['todos', 'list', { status: 'completed' }]`. Bagaimana strategi mutasi menambahkan todo baru agar cache diupdate secara efisien tanpa melakukan refetch tidak terarah ke seluruh database endpoint?

<details>
<summary>Jawaban & Pembahasan</summary>

**Pembahasan:**
Hierarki query key pada Vue Query bersifat predikatif berbasis array prefix matching:
- Pemanggilan `queryClient.invalidateQueries({ queryKey: ['todos'] })` akan meng-invalidasi **semua** query yang diawali dengan `todos` (baik list maupun detail).
- Untuk invalidasi presisi:
  ```ts
  // Hanya invalidasi semua jenis list todos, tanpa merusak cache detail item yang tidak berubah
  queryClient.invalidateQueries({ 
    queryKey: ['todos', 'list'],
    exact: false 
  });
  ```
- **Strategi Optimal (Direct Cache Update + Targeted Invalidation):**
  Alih-alih refetch penuh, gunakan `queryClient.setQueryData` untuk menyuntikkan item baru langsung ke `['todos', 'list', { status: 'all' }]`, lalu hanya invalidasi query list yang memiliki filter aktif yang terdampak.
</details>

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 1: "Phantom Form Submission" pada Koneksi Seluler Flaky
**Konteks Masalah:**
Aplikasi e-commerce Vue 3 mengalami komplain dari pelanggan seluler di area minim sinyal. Pengguna mengeklik tombol "Bayar Sekarang" berulang kali karena indikator loading tidak segera muncul akibat *event-loop blockage* atau delay koneksi awal, mengakibatkan pembayaran terpotong 2-3 kali untuk pesanan yang sama.

**Analisis Masalah:**
1. Tidak ada idempotency guard di sisi klien maupun payload jaringan.
2. Form submission tidak di-lock seketika saat event `submit` pertama kali diterima.
3. Tombol submit tidak dinonaktifkan secara deterministik sebelum request jaringan asinkron dilepas.

**Solusi Teknis:**
1. **Idempotency Key:** Generate UUID v4 saat form pertama kali dimuat atau diinisialisasi (`idempotency-key`). Kirimkan header ini ke gateway pembayaran backend.
2. **Atomic Submission Lock:**
   ```ts
   const isSubmitting = ref(false);
   
   async function handleCheckout() {
     if (isSubmitting.value) return;
     isSubmitting.value = true;
     
     try {
       await checkoutApi.pay({
         orderId,
         idempotencyKey: currentSessionKey.value
       });
       router.push('/order-success');
     } catch (err) {
       showErrorToast(err);
     } finally {
       isSubmitting.value = false;
     }
   }
   ```
3. **UI Feedback:** Atribut `:disabled="isSubmitting"` terpasang pada tombol submit bersama visual spinner instan yang tidak menunggu promise resolve.
</details>

---

### Skenario 2: Memory Leak dan Stale Data pada Dashboard Realtime Polling
**Konteks Masalah:**
Dashboard monitoring armada logistik memicu polling data setiap 5 detik menggunakan `setInterval` di dalam composable kustom. Operator yang membiarkan tab terbuka seharian mengalami degradasi performa drastis hingga browser tab crash (Out of Memory). Selain itu, ketika laptop dibuka dari mode sleep, terjadi lonjakan puluhan request tertunda yang dieksekusi serentak.

**Analisis Masalah:**
1. `setInterval` tidak dibersihkan saat komponen di-unmount (`clearInterval`).
2. `setInterval` tetap mengeksekusi fetch meskipun browser tab berada di latar belakang (*hidden visibility*).
3. Request yang berjalan lebih lambat dari 5 detik menumpuk (*cascading network congestion*).

**Solusi Teknis:**
1. **Migrasi ke Recursive Timeout dengan Lifecycle Awareness:**
   Ganti interval tetap dengan rekursif `setTimeout` yang hanya menjadwalkan request berikutnya setelah request sebelumnya benar-benar selesai (`onSettled`).
2. **Page Visibility API:** Hentikan polling jika tab tidak aktif (`document.hidden`).
3. **Implementasi Composable Robust:**
   ```ts
   export function useAdaptivePolling(fetchFn: () => Promise<void>, intervalMs = 5000) {
     let timerId: ReturnType<typeof setTimeout> | null = null;
     let isAlive = true;

     const run = async () => {
       if (!isAlive || document.hidden) return;
       try {
         await fetchFn();
       } finally {
         if (isAlive) {
           timerId = setTimeout(run, intervalMs);
         }
       }
     };

     const onVisibilityChange = () => {
       if (!document.hidden) run();
       else if (timerId) clearTimeout(timerId);
     };

     onMounted(() => {
       document.addEventListener('visibilitychange', onVisibilityChange);
       run();
     });

     onUnmounted(() => {
       isAlive = false;
       if (timerId) clearTimeout(timerId);
       document.removeEventListener('visibilitychange', onVisibilityChange);
     });
   }
   ```
</details>

---

### Skenario 3: Sinkronisasi Form Multi-Langkah dengan URL Query State & Server Draft
**Konteks Masalah:**
Form pengajuan pinjaman perbankan terdiri dari 4 langkah dengan validasi ketat. Calon nasabah sering kali me-refresh halaman atau tidak sengaja menekan tombol back browser, menyebabkan seluruh input yang sudah diisi di Langkah 1-3 hilang, menurunkan angka konversi aplikasi.

**Analisis Masalah:**
1. State form disimpan secara eksklusif di memori komponen lokal (`ref`).
2. Navigasi langkah tidak disinkronkan ke router (`useRoute` / `useRouter`), sehingga reload selalu mengembalikan user ke step 1.
3. Tidak ada persistensi draf lokal (IndexedDB/LocalStorage) atau autosave draft ke backend.

**Solusi Teknis:**
1. **Routing Query Synchronization:** Bind langkah aktif ke URL query string: `?step=3`.
2. **Hybrid Persistence:**
   - Gunakan `watchDebounced` untuk menyimpan payload form setiap 1 detik ke `localStorage` (atau panggil endpoint `/api/loan-draft` di latar belakang).
   - Saat komponen diinisialisasi, validasi data draft lokal/server dengan Zod skema sebelum mengisi default value form.
3. **Route Navigation Guard:** Cegah kehilangan data mendadak menggunakan `onBeforeRouteLeave`:
   ```ts
   onBeforeRouteLeave((to, from, next) => {
     if (isDirty.value && !isSubmitted.value) {
       const answer = window.confirm('Draf pengajuan Anda belum selesai disimpan. Yakin ingin keluar?');
       if (answer) next();
       else next(false);
     } else {
       next();
     }
   });
   ```
</details>

---

## Bagian 4: Practical Chapter Challenge

### Tantangan: Membangun Resilient Data-Table & Filtering Engine
Bangun sebuah modul reaktif lengkap untuk menampilkan daftar pesanan (*Orders Table*) yang mencakup formulir filter pencarian, pengurutan, pagination asinkron, serta pembatalan request.

#### Persyaratan Teknis & Fungsional:
1. **Composable `useFetchOrders`:**
   - Menerima parameter reaktif: `searchQuery`, `statusFilter`, `page`, dan `sortBy`.
   - Menggunakan `AbortController` untuk membatalkan request sebelumnya setiap kali salah satu parameter berubah.
   - Mengintegrasikan mekanisme debounce 400ms khusus untuk `searchQuery`.
   - Mengembalikan state reaktif: `{ data, totalPages, isLoading, isError, errorMessage, refetch }`.
2. **Formulir Filter:**
   - Input pencarian berbasis keyword dengan tombol clear instan.
   - Dropdown status: `All`, `Pending`, `Paid`, `Shipped`, `Cancelled`.
   - Sinkronisasi nilai filter ke URL query string menggunakan `vue-router`.
3. **Error & Empty State Handling:**
   - Tampilkan skeleton loading saat data sedang dijemput.
   - Tampilkan banner error khusus lengkap dengan tombol "Coba Lagi" (*Retry*) jika API merespons status code non-200.
   - Tampilkan ilustrasi/pesan kosong jika filter menghasilkan 0 data.

#### Rubrik Penilaian:
| Kriteria | Bobot | Deskripsi Kualitas |
| :--- | :--- | :--- |
| **Arsitektur Concurrency** | 30% | Tidak ada race condition; request lama berhasil di-abort secara transparan di network tab. |
| **Pemisahan Logika (Separation of Concerns)** | 25% | Logika network terisolasi rapi dalam composable independen, terpisah dari UI komponen. |
| **UX & Error Handling** | 25% | Ada handling menyeluruh untuk status loading, retry action, empty state, dan debounce input. |
| **Type Safety & Clean Code** | 20% | Menggunakan antarmuka TypeScript lengkap, tanpa penggunaan tipe `any`, serta kode yang teruji. |

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan daftar periksa berikut untuk mengevaluasi kesiapan arsitektural sebelum melangkah ke bab berikutnya:

- [ ] **Mekanisme v-model:** Memahami binding kustom `:modelValue` + `@update:modelValue`, multiple v-model argumen, dan custom modifiers.
- [ ] **Asynchronous Lifecycle:** Mengetahui kapan dan di mana data fetching harus dipicu (`onMounted`, `watchEffect`, atau Vue Query composables).
- [ ] **Network Abortion:** Mahir menggunakan native `AbortController` dan menghubungkannya dengan lifecycle hook `onUnmounted` atau watcher cleanup.
- [ ] **Race Condition Prevention:** Mampu menjelaskan dan mendemonstrasikan mitigasi tabrakan respons jaringan menggunakan token pembatalan dan sequence guarding.
- [ ] **Axios Interceptors:** Menguasai pembuatan interceptor global untuk token injection, idempotency key generation, serta concurrent token refreshing queue.
- [ ] **Server State Caching:** Memahami konsep stale time, cache time (gcTime), query invalidation, dan deduplication menggunakan library server-state modern.
- [ ] **Optimistic UI:** Mampu merancang alur modifikasi antarmuka instan dengan snapshot rollback saat terjadi kegagalan jaringan.
- [ ] **Form Validation:** Menguasai integrasi skema deklaratif berbasis Zod / Vee-Validate dengan error messaging tingkat field dan level form.
- [ ] **Suspense & Code Splitting:** Mampu mengimplementasikan `defineAsyncComponent` dengan fallback loading UI yang terkoordinasi.
