# BAB 02 — Quiz, Challenge, & Knowledge Check: State Primitives & Re-render Lifecycle

## Quiz

### Basic (Konsep Inti)
1. **Pertanyaan**: Apa yang dimaksud dengan re-render dalam konteks komponen React?
2. **Pertanyaan**: Kapan tepatnya React memutuskan untuk menjadwalkan (schedule) re-render setelah kita memanggil fungsi *setter* dari `useState`?
3. **Pertanyaan**: Apa perbedaan utama antara variabel lokal biasa (menggunakan `let` atau `const`) dengan variabel state yang dideklarasikan menggunakan `useState`?
4. **Pertanyaan**: Apa fungsi dari *State Batching* di React?
5. **Pertanyaan**: Mengapa kita tidak boleh memodifikasi objek atau array state secara langsung (mutate) di React?

### Intermediate (Mekanisme Internal & Troubleshooting)
1. **Pertanyaan**: Jika kita memiliki komponen dengan state `count` yang bernilai `0`, apa nilai `count` setelah kita menjalankan `setCount(count + 1); setCount(count + 1); setCount(count + 1);` secara berurutan dalam satu handler? Jelaskan alasannya.
2. **Pertanyaan**: Bagaimana cara mengatasi masalah pada pertanyaan sebelumnya agar `count` bertambah 3? Jelaskan konsep *updater function*.
3. **Pertanyaan**: Anda memiliki state objek `user = { name: 'Budi', address: { city: 'Jakarta' } }`. Anda ingin memperbarui kota menjadi 'Bandung'. Tuliskan cara yang benar menggunakan `setUser` tanpa mengubah (*mutate*) state sebelumnya.
4. **Pertanyaan**: Mengapa kadang-kadang kita mengalami "Infinite Loop" (Maximum update depth exceeded) ketika menaruh fungsi *setter* state langsung di body komponen (bukan di dalam *event handler* atau `useEffect`)?
5. **Pertanyaan**: Apa itu "Stale State" atau "Stale Closure" di React, dan bagaimana biasanya hal ini terjadi dalam konteks fungsi *timeout* atau pemanggilan API asynchronous?

### Skenario Kasus Nyata Produksi
1. **Skenario 1**: Di production, Anda mendapati aplikasi e-commerce Anda melambat (*laggy*) saat pengguna mengetik di kolom *Search*. Saat diperiksa menggunakan React DevTools Profiler, ternyata seluruh komponen ProductList ikut me-render ulang setiap karakter diketik.
   - **Tantangan**: Apa penyebab struktural masalah ini, dan bagaimana strategi refactoring state (misal: state colocation atau penggunaan `useDeferredValue`/`memo`) yang harus dilakukan?
2. **Skenario 2**: Anda membuat form wizard kompleks dengan beberapa langkah (step). Data disimpan dalam sebuah root state `wizardData` (objek besar bersarang). Tim QA melaporkan saat mengubah nilai pada "Step 3", terjadi delay yang cukup terasa sebelum UI terupdate.
   - **Tantangan**: Evaluasi trade-off antara menggunakan satu state objek besar di tingkat atas vs memecah state menjadi state primitive yang lebih kecil atau menggunakan library form management.
3. **Skenario 3**: Sebuah komponen *live dashboard* menerima event dari WebSocket setiap 50 milidetik dan memperbarui state yang menyimpan list notifikasi terbaru. Terjadi *jank* di browser (FPS drop drastis).
   - **Tantangan**: Bagaimana cara mengoptimalkan pembaruan state yang terlalu cepat ini? Kapan *React 18 automatic batching* membantu dan kapan Anda perlu membuat *throttling/debouncing* manual pada update state?

---

## Chapter Challenge

**Simulasi Keranjang Belanja Dinamis (Dynamic Shopping Cart)**

**Deskripsi Kasus:**
Anda ditugaskan membuat komponen keranjang belanja yang memiliki item dengan tipe yang berbeda-beda. Beberapa item adalah produk fisik dengan varian warna, sementara yang lain adalah lisensi digital yang membutuhkan email pengiriman khusus.

**Requirements:**
1. State harus bisa menangani penambahan barang baru, penghapusan barang, dan mengubah kuantitas barang.
2. Untuk barang fisik, pengguna dapat mengubah warna.
3. Perubahan kuantitas harus dicegah (*disabled*) jika melebihi *stock* (anggap stock adalah data dummy yang diberikan).
4. Ada fitur "Pilih Semua" (Select All) untuk *checkout*.

**Tantangan Ekstra (Tanpa Solusi Instan):**
- Anda harus mengelola state array of objects yang *nested* dengan cara immutable.
- Jangan sampai meng-update satu item di keranjang menyebabkan komponen item lain di dalam *list* keranjang melakukan *expensive re-render* (pertimbangkan bagaimana struktur state dan *key* berinteraksi, walaupun `React.memo` belum dibahas mendalam, pikirkan secara desain state-nya).
- Bagaimana cara yang paling bersih (*clean*) untuk mengatur state ini? Satu state array besar, atau kombinasi useReducer (bila sudah dipelajari) / dipisah komponen?

---

## Knowledge Check

### Saya harus memahami
- Konsep dasar bahwa React UI adalah proyeksi dari state.
- Perbedaan *Render Phase* dan *Commit Phase*.
- Aturan ketat *immutability* dalam memperbarui State (terutama Objek dan Array).
- Mekanisme *State Batching* dan kapan React akan menggabungkan update state.
- Bagaimana *Updater Function* (`setCount(prev => prev + 1)`) bekerja secara sinkron terhadap *queue* state.

### Saya tidak perlu menghafal
- Seluruh struktur internal antrian *Fiber tree* React. Cukup pahami bahwa pembaruan dijadwalkan secara logis.
- Detail implementasi algoritma diffing (heuristic algorithm) di luar dari fungsi *key* pada list (akan dipelajari nanti).

### Saya harus bisa melakukan
- Mendeklarasikan dan menggunakan `useState` untuk berbagai tipe data (primitif dan kompleks).
- Memecahkan masalah "stale state" menggunakan *updater function*.
- Memodifikasi (*update*) state objek dan array menggunakan *spread operator* atau metode immutable lainnya (seperti `map`, `filter`).

### Checklist
- [ ] Memahami konsep re-render di React
- [ ] Memahami cara kerja State Batching
- [ ] Bisa memperbarui state berdasarkan state sebelumnya (updater function)
- [ ] Bisa memanipulasi State Objek (nested object update) tanpa mutasi
- [ ] Bisa memanipulasi State Array (add, remove, update) tanpa mutasi
- [ ] Bisa melakukan debugging pada infinite re-render sederhana
- [ ] Memahami trade-off dari menaruh state terlalu tinggi atau terlalu rendah (*state colocation*)
