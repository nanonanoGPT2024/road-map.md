---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Anatomi React Shadow Tree & C++ Immutability
Di arsitektur modern React Native (Fabric), setiap node visual di JavaScript dipetakan ke sebuah objek C++ bernama `ShadowNode`. Berbeda dengan DOM browser yang bersifat *mutable*, `ShadowNode` bersifat *immutable*. 

Ketika sebuah state berubah:
* React tidak memodifikasi properti instance `ShadowNode` yang sudah ada.
* React membuat salinan klona dari node tersebut (*copy-on-write*) beserta *ancestor path* miliknya menuju ke *root*.
* Konkurensi terjamin aman (*thread-safe*): thread layout Yoga dan thread JavaScript dapat membaca Shadow Tree tanpa race condition lock yang berat.

### 2. StyleSheet Mechanism: Mengapa Bukan Plain Objects?
Banyak engineer pemula mengira `StyleSheet.create` hanyalah pembungkus tipis (*identity function*) yang mengembalikan objek mentah. Di masa arsitektur bridge legacy, `StyleSheet.create` mendaftarkan objek ke tabel referensi global internal dan mengembalikan indeks angka integer (ID). ID tersebut dikirimkan melintasi JSON Bridge untuk menghemat bandwidth serialisasi.

Pada New Architecture (Fabric + JSI):
* `StyleSheet.create` mengembalikan objek yang dioptimalkan (*frozen shape* via optimization engines Hermes).
* Runtime melakukan validasi tipe dan normalisasi nilai deklaratif (seperti konversi `'red'` ke format heksadesimal integer 32-bit `0xFFFF0000` via Color Resolvers C++).
* Penggunaan `StyleSheet.create` memastikan referensi memori statis (singleton), sehingga mencegah pembuatan referensi objek baru di setiap siklus render (menghindari GC pressure pada Hermes engine).

### 3. Yoga Engine Layout Math
Yoga mengimplementasikan algoritma CSS Flexbox standar W3C namun tanpa ketergantungan pada browser DOM. 
* Yoga beroperasi menggunakan koordinat floating-point (Point/dp).
* Nilai persentase (misal `width: '50%'`) dihitung berdasarkan ukuran absolut node induk terdekat yang telah memiliki ukuran definitif (*resolved bounds*).
* Nilai floating point dibulatkan secara sub-pixel (*pixel snapping*) pada tahap akhir sebelum dikirim ke Native UI untuk mencegah artefak visual rendering (seperti garis kabur / 1px visual bleeding).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Render Phase vs Commit Phase
Pemahaman terhadap pemisahan fase sangat krusial dalam arsitektur React:

| Parameter | Render Phase | Commit Phase |
| :--- | :--- | :--- |
| **Karakteristik** | Asynchronous, concurrent, murni tanpa efek samping, dapat dihentikan (abortable/restartable). | Synchronous, tidak dapat diinterupsi, berinteraksi langsung dengan host layer. |
| **Eksekusi** | Pemanggilan fungsi komponen, komputasi useMemo, logika JSX. | Mutasi Host Views, eksekusi layout hook, dispatching side-effects. |
| **Operasi Ilegal** | Mutasi variabel global, trigger network request langsung, memodifikasi mutable refs yang mempengaruhi output. | Operasi komputasi intensif yang memblokir main thread UI. |

### Siklus Hooks: `useEffect` vs `useLayoutEffect` vs `useInsertionEffect`

1.  **`useInsertionEffect`:**
    *   **Kapan dieksekusi:** Tepat sebelum mutasi React Shadow Tree dilakukan.
    *   **Tujuan utama:** Menyuntikkan style dinamis ke runtime CSS-in-JS library. Jarang digunakan di level aplikasi biasa, krusial bagi library library styling.
2.  **`useLayoutEffect`:**
    *   **Kapan dieksekusi:** Secara *sinkron* tepat setelah Fabric memutasi Host Views di native, namun **sebelum** layar ponsel digambar ulang oleh GPU (*before paint*).
    *   **Implikasi Teknis:** Memblokir frame. Jika Anda menjalankan komputasi berat di sini, frame rate akan anjlok drastis (UI jank/stutter).
    *   **Use-Case Sah:** Mengukur ukuran layout absolut (`measure()`) dari view native dan memodifikasi state sebelum pengguna melihat frame yang belum rapi (*flicker prevention*).
3.  **`useEffect`:**
    *   **Kapan dieksekusi:** Secara *asinkron* setelah browser/native thread selesai menggambar UI ke layar ponsel (*after paint*).
    *   **Tujuan:** Interaksi dengan API luar, subscription event, timer, dan penulisan storage.

### The Golden Rule of Declarative UI
> Jangan pernah memanipulasi referensi node visual secara langsung kecuali untuk penanganan interaksi fokus input atau animasi berbasis hardware driver (seperti React Native Reanimated worklets). Kendalikan segalanya lewat aliran data satu arah (*Unidirectional Data Flow*).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah contoh modular yang mendemonstrasikan implementasi antarmuka deklaratif dengan manajemen siklus hidup hook, pengukuran layout, serta isolasi styling yang efisien.
