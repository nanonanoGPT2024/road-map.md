# BAB-02-Declarative-UI-Component-Lifecycle-dan-Styling-Systems: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi teknis, pengujian pemahaman konseptual, serta uji kompetensi implementatif untuk topik **Declarative UI, Component Lifecycle, dan Styling Systems** pada React Native.

---

## Bagian 1: 5 Basic Questions (Pertanyaan Dasar)

### Pertanyaan 1: Perbedaan Imperative UI vs Declarative UI
Jelaskan perbedaan mendasar antara paradigma *Imperative UI* (seperti Android native berbasis `findViewById` / UIKit iOS) dengan *Declarative UI* pada React Native. Bagaimana React Native menjembatani pembaruan deklaratif JavaScript ke native view hierarchy?

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

- **Imperative UI:** Pengembang secara eksplisit memanipulasi instance view langkah demi langkah (`view.setText("Bar")`, `view.setVisibility(View.GONE)`). State dan representasi visual dikelola terpisah, rentan terhadap inkonsistensi state UI (*desync*).
- **Declarative UI:** UI dimodelkan murni sebagai fungsi dari state: `UI = f(state)`. Pengembang hanya mendeklarasikan bagaimana antarmuka harus terlihat pada suatu snapshot state tertentu. Saat state berubah, React merekonsiliasi Virtual DOM (atau shadow tree pada arsitektur Fabric) dan menghitung diff secara minimal.
- **Mekanisme Bridge / Fabric:**
  - *Legacy Architecture:* React JS Thread mengirimkan mutasi dalam bentuk batch JSON payload melalui Asynchronous Bridge ke Native Shadow Tree (Yoga Layout engine) lalu diterjemahkan ke Native UI thread.
  - *New Architecture (Fabric):* React langsung berinteraksi dengan C++ Core melalui JSI (JavaScript Interface), membentuk Fabric C++ Shadow Tree secara sinkron/bersamaan tanpa overhead serialisasi JSON, kemudian me-mount node native secara langsung.
</details>

---

### Pertanyaan 2: Primitif StyleSheet vs Objek Literal Inline
Mengapa penggunaan `StyleSheet.create` sangat direkomendasikan dibandingkan mendefinisikan objek literal style secara inline (contoh: `style={{ padding: 16 }}`)? Sebutkan aspek alokasi memori dan optimasi runtime!

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

1. **Alokasi Memori & Garbage Collection (GC):**
   - Objek inline literal akan dialokasikan ulang di JavaScript heap pada setiap siklus re-render komponen. Hal ini meningkatkan tekanan memori (*memory churn*) dan memicu eksekusi garbage collector secara agresif yang berpotensi menyebabkan micro-stutter/dropped frames.
   - `StyleSheet.create` membekukan (*freeze*) referensi objek di luar lifecycle render, sehingga pointer referensi bersifat statis dan stabil.
2. **Validasi & ID Registrasi:**
   - `StyleSheet.create` memvalidasi nama properti dan value style pada saat inisialisasi modul (fail-fast jika ada typo properti).
   - Pada runtime internals, StyleSheet mengorganisir style ke dalam representasi ID numerik/statis yang optimal saat dipetakan ke bridge/C++ shadow tree layout engine (Yoga).
</details>

---

### Pertanyaan 3: Flexbox Defaults pada React Native vs Web
Sebutkan tiga perbedaan konfigurasi default Flexbox pada React Native jika dibandingkan dengan standar CSS Flexbox di Web browser!

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

1. **`flexDirection` Default:**
   - Web: default `row` (arah horizontal).
   - React Native: default `column` (arah vertikal, disesuaikan dengan orientasi portrait perangkat mobile).
2. **`flexShrink` Default:**
   - Web: default `1` (elemen menciut jika ruang tidak mencukupi).
   - React Native: default `0` (elemen tidak menciut secara otomatis kecuali dideklarasikan eksplisit).
3. **Satuan Unit & Box Sizing:**
   - Web: mendukung satuan unit relatif seperti `px`, `em`, `rem`, `%`, serta `box-sizing: content-box` secara default.
   - React Native: semua nilai dimensi numerik murni adalah Density-independent Pixels (DP/PT), tidak menggunakan string unit seperti `px`, dan box-sizing selalu setara dengan `border-box`.
</details>

---

### Pertanyaan 4: Cleanup Function pada `useEffect`
Kapan tepatnya fungsi cleanup (return value) dari hook `useEffect` dieksekusi oleh React runtime pada komponen fungsional? Berikan contoh skenario wajib pembersihannya di React Native!

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

- **Waktu Eksekusi:**
  1. Tepat sebelum efek dijalankan kembali akibat perubahan nilai pada *dependency array*.
  2. Saat komponen di-*unmount* dari component tree.
- **Skenario Wajib:**
  - Pembatalan langganan event listener native: `AppState.addEventListener`, `BackHandler.addEventListener`, atau listener `Dimensions`.
  - Pembersihan timer atau interval: `clearInterval(intervalId)` atau `clearTimeout(timerId)`.
  - Pembatalan koneksi jaringan / socket / background subscription (`AbortController.abort()`) untuk mencegah memory leak dan peringatan *"Can't perform a React state update on an unmounted component"*.
</details>

---

### Pertanyaan 5: Density-Independent Pixels (DP) vs Physical Pixels
Bagaimana hubungan matematis antara nilai numerik style (Density-independent Pixel / DP) pada React Native dengan Physical Pixels pada layar perangkat? Tool API apa yang digunakan untuk mengetahuinya?

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

- **Rumus Matematis:**
  $$\text{Physical Pixels} = \text{DP} \times \text{Pixel Ratio}$$
- **Penjelasan:**
  - React Native menggunakan DP (Android) / Points (iOS) sebagai unit ukuran abstrak agar ukuran fisik elemen konsisten di berbagai ukuran dan kerapatan layar (DPI/PPI).
  - Skala pixel ratio umumnya berkisar antara `1x` (mdpi), `2x` (xhdpi / Retina @2x), `3x` (xxhdpi / Super Retina @3x), hingga `3.5x - 4x`.
- **API React Native:**
  - `PixelRatio.get()` untuk mendapatkan rasio densitas layar perangkat.
  - `PixelRatio.getPixelSizeForLayoutSize(dp)` untuk mengonversi nilai DP menjadi physical pixel (sangat krusial saat me-request ukuran gambar dari CDN).
  - `PixelRatio.roundToNearestPixel(dp)` untuk menghindari sub-pixel rendering artifact.
</details>

---

## Bagian 2: 5 Intermediate Questions (Pertanyaan Menengah)

### Pertanyaan 1: Perbedaan `useEffect` vs `useLayoutEffect` dalam Konteks Render Frame
Jelaskan perbedaan timing eksekusi antara `useEffect` dan `useLayoutEffect` serta implikasinya terhadap layout measurement dan layout shift (flickering) pada native UI!

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

- **`useLayoutEffect`:**
  - Berjalan secara **sinkron** tepat setelah React mengomputasi Virtual DOM / Shadow Tree mutasi, tetapi **sebelum** browser atau native UI thread melukis (paint) frame ke layar perangkat.
  - Menghentikan proses rendering visual sampai eksekusi di dalamnya selesai.
  - Digunakan jika perlu mengukur geometri node (`measureLayout` / DOM geometry) dan langsung memperbarui state posisi sebelum user melihat visual layout awal (mencegah flickering/layout shift).
- **`useEffect`:**
  - Berjalan secara **asinkron** dan *deferred* setelah render frame selesai digambar ke layar (post-paint).
  - Tidak memblokir frame rendering, ideal untuk data fetching, subscriptions, logging, dan tugas non-visual blocking.
- **Rekomendasi di React Native:** Gunakan `useEffect` sebagai default. Hindari `useLayoutEffect` kecuali benar-benar dibutuhkan untuk sinkronisasi layout kalkulasi, karena eksekusi JS yang berat di `useLayoutEffect` akan menyebabkan frame drop seketika.
</details>

---

### Pertanyaan 2: Trade-off Arsitektural: Runtime CSS-in-JS vs Static Extraction / NativeWind
Bandingkan mekanisme runtime CSS-in-JS (seperti Emotion/Styled-Components runtime) dengan compile-time utility styling (seperti NativeWind / Tailwind) pada aplikasi React Native berskala besar!

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

| Parameter Evaluasi | Runtime CSS-in-JS | Compile-time Utility (NativeWind / Restyle) |
| :--- | :--- | :--- |
| **Kompilasi** | String template/objek diurai (*parsed*) saat runtime komponen di-mount. | Ekstraksi utility class dilakukan saat build-time menggunakan Babel/Metro plugin. |
| **Overhead JS Thread** | Tinggi: perhitungan interpolasi props, hashing class, dan inject objek style terjadi berulang di runtime JS. | Minimal: ditransformasi langsung menjadi objek `StyleSheet.create` statis dengan integer ID mapping. |
| **Dukungan Fabric C++** | Sering kali memicu overhead bridge/JSI karena style objek dinamis dialokasikan berulang. | Native-friendly, selaras dengan tree layout optimization C++ Yoga engine. |
| **Bundle Size & Startup** | Menambah ukuran runtime library dan memperlambat TTI (*Time to Interactive*). | Runtime sangat tipis (*zero-runtime overhead / negligible bundle footprint*). |
</details>

---

### Pertanyaan 3: Penanganan Notch & Dynamic Island Menggunakan Safe Area Insets
Mengapa penggunaan bawaan `SafeAreaView` dari package core `react-native` sudah dianggap usang (*deprecated*) dan tidak memadai untuk aplikasi modern? Mengapa arsitektur industri beralih ke `react-native-safe-area-context`?

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

1. **Keterbatasan Native `SafeAreaView` (Core):**
   - Hanya mendukung platform iOS; tidak memiliki efek pada Android (terutama untuk Android notch, edge-to-edge system navigation bars, dan punch-hole camera).
   - Menggunakan kalkulasi view wrapper statis murni yang sering kali tidak sinkron dengan rotasi layar dinamis atau keyboard overlay.
2. **Keunggulan `react-native-safe-area-context`:**
   - **Cross-Platform:** Mengambil *window insets* asli dari sistem operasi (Android WindowInsetsCompat & iOS UIEdgeInsets) via native module/Fabric component.
   - **Hook-based (`useSafeAreaInsets`):** Menyediakan kontrol berbasis nilai numerik padding (`top`, `bottom`, `left`, `right`) sehingga developer bisa memanipulasi layout custom (misal: sticky headers, transparent status bar, floating bottom bars).
   - **Performan tinggi:** Insets dipetakan ke React Context yang efisien dan mendukung konsumsi inset pada level native view controller tanpa layout jumping.
</details>

---

### Pertanyaan 4: Perangkap Stale Closure pada Hooks Lifecycle
Perhatikan cuplikan kode berikut:
```tsx
const [count, setCount] = useState(0);

useEffect(() => {
  const interval = setInterval(() => {
    console.log("Count saat ini:", count);
    setCount(count + 1);
  }, 1000);
  return () => clearInterval(interval);
}, []);
```
Jelaskan mengapa kode di atas gagal menambahkan nilai `count` lebih dari 1, dan bagaimana dua cara berbeda untuk memperbaikinya tanpa merusak intent interval!

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

- **Akar Masalah (Stale Closure):**
  - Dependency array `[]` menyebabkan effect callback hanya dieksekusi satu kali saat komponen pertama kali di-mount.
  - Closure interval callback mengikat (*capture*) variabel `count` dari scope render pertama, di mana `count = 0`.
  - Setiap detik, interval mengeksekusi `setCount(0 + 1)`. Hasil update selalu `1` dan nilai variabel dalam closure tidak pernah di-refresh.
- **Solusi 1: Functional State Update (Rekomendasi Utama)**
  ```tsx
  useEffect(() => {
    const interval = setInterval(() => {
      setCount((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, []);
  ```
- **Solusi 2: Sinkronisasi via `useRef`**
  ```tsx
  const countRef = useRef(count);
  countRef.current = count;

  useEffect(() => {
    const interval = setInterval(() => {
      setCount(countRef.current + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, []);
  ```
</details>

---

### Pertanyaan 5: Mengatasi Perbedaan Dimensi Layar Dinamis (`Dimensions` vs `useWindowDimensions`)
Kapan penggunaan `Dimensions.get('window')` berpotensi menyebabkan bug tata letak UI, dan mengapa `useWindowDimensions` menyelesaikan masalah tersebut secara reaktif?

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

- **Kelemahan `Dimensions.get('window')`:**
  - Mengambil nilai skalar statis pada momen fungsi tersebut dipanggil.
  - Jika dideklarasikan di luar siklus render (misalnya pada level root file atau modul statis), nilainya tidak akan pernah berubah saat terjadi:
    1. Rotasi layar (portrait $\leftrightarrow$ landscape).
    2. Perubahan mode Split Screen / Multi-Window di Android/iPadOS.
    3. Perubahan foldable screen geometry (unfolding device).
- **Keunggulan `useWindowDimensions`:**
  - Merupakan React Hook resmi yang mendaftarkan listener ke event native resize.
  - Memperbarui state dimensi internal React secara otomatis dan memicu re-render reaktif dengan nilai lebar, tinggi, skala, dan font scale yang akurat seketika saat orientasi atau viewport berubah.
</details>

---

## Bagian 3: 3 Skenario Kasus Nyata Produksi (Real-World Production Scenarios)

### Skenario 1: Layout Thrashing & Frame Drop pada Dynamic Infinite List
**Konteks Masalah:**
Sebuah aplikasi e-commerce FinTech memiliki feed katalog produk dengan ribuan item menggunakan `FlatList`. Setiap kartu produk memiliki variasi status dinamis (diskon, flash sale, badge merchant) di mana styling dihitung langsung menggunakan fungsi kalkulasi inline kompleks:
```tsx
<View style={[styles.card, computeCardDynamicStyles(item.status, isDarkMode)]}>
```
Saat user melakukan scroll cepat, FPS JS Thread anjlok dari 60 FPS ke 18 FPS, menyebabkan visual stutter parah (*dropped frames*).

**Tugas Evaluasi:**
1. Identifikasi penyebab utama degradasi performa dari sudut pandang alokasi memori dan render tree.
2. Rancang solusi refactoring konkret untuk memulihkan performa kembali stabil di 60 FPS!

<details>
<summary><b>Analisis & Solusi Arsitektur</b></summary>

1. **Akar Masalah:**
   - `computeCardDynamicStyles` dieksekusi ratusan kali per detik saat scroll, mengembalikan objek baru setiap saat.
   - Array spread `[styles.card, {...}]` mengalokasikan array baru pada setiap render item.
   - Peningkatan Garbage Collection (GC) pauses di JS thread yang menyebabkan frame deadline (16.6ms) terlewati.
2. **Solusi Perbaikan:**
   - **Static Variant Cache:** Pra-komputasi semua kombinasi style yang mungkin menggunakan `StyleSheet.create` di luar siklus render item.
     ```tsx
     const VARIANT_STYLES = StyleSheet.create({
       active_light: { backgroundColor: '#FFFFFF', borderColor: '#007AFF' },
       active_dark: { backgroundColor: '#1C1C1E', borderColor: '#0A84FF' },
       discount_light: { backgroundColor: '#FFF0F0', borderColor: '#FF3B30' },
       // ... varian lainnya
     });
     ```
   - **Komponen Memoized:** Bungkus item dengan `React.memo` menggunakan perbandingan props granular.
   - **Gunakan ID lookup statis:** Daripada mengomputasi objek runtime, gunakan key lookup cepat:
     ```tsx
     const variantKey = `${item.status}_${isDarkMode ? 'dark' : 'light'}`;
     <View style={[styles.card, VARIANT_STYLES[variantKey]]} />
     ```
</details>

---

### Skenario 2: Memory Leak & Race Condition pada Asynchronous Navigation
**Konteks Masalah:**
Sebuah modul detail transfer perbankan melakukan fetching status transaksi melalui API REST saat layar dimuat. Jika pengguna langsung menekan tombol *Back* sebelum fetch selesai (kurang dari 500ms), console production crash reporter (Sentry) mencatat lonjakan unhandled promise rejection dan memory leak:
```tsx
export const TransactionDetailScreen = ({ route }) => {
  const [data, setData] = useState<Transaction | null>(null);

  useEffect(() => {
    fetchTransactionDetail(route.params.id).then((result) => {
      setData(result);
    });
  }, [route.params.id]);

  return <View>...</View>;
};
```

**Tugas Evaluasi:**
1. Mengapa pola di atas berbahaya saat komponen di-*unmount* sebelum promise resolved?
2. Tuliskan implementasi refactoring standar industri menggunakan `AbortController`!

<details>
<summary><b>Analisis & Solusi Arsitektur</b></summary>

1. **Akar Masalah:**
   - Ketika pengguna meninggalkan layar, komponen `TransactionDetailScreen` di-unmount, namun promise `fetchTransactionDetail` tetap menggantung di microtask queue.
   - Ketika promise akhirnya resolve, `setData(result)` dipanggil pada komponen yang sudah mati (*unmounted*). Hal ini menahan referensi komponen di memori (memory leak) dan berpotensi memicu crash jika efek samping melibatkan akses native bridge yang telah di-dispose.
2. **Solusi Refactoring:**
   ```tsx
   import React, { useEffect, useState } from 'react';
   import { View, Text, ActivityIndicator } from 'react-native';

   export const TransactionDetailScreen = ({ route }: { route: { params: { id: string } } }) => {
     const [data, setData] = useState<Transaction | null>(null);
     const [error, setError] = useState<string | null>(null);
     const [loading, setLoading] = useState<boolean>(true);

     useEffect(() => {
       const abortController = new AbortController();

       const loadData = async () => {
         try {
           setLoading(true);
           const result = await fetchTransactionDetail(route.params.id, {
             signal: abortController.signal,
           });
           setData(result);
         } catch (err: any) {
           if (err.name !== 'AbortError') {
             setError(err.message || 'Gagal memuat transaksi');
           }
         } finally {
           if (!abortController.signal.aborted) {
             setLoading(false);
           }
         }
       };

       loadData();

       return () => {
         // Batalkan request saat unmount atau route id berubah
         abortController.abort();
       };
     }, [route.params.id]);

     if (loading) return <ActivityIndicator />;
     if (error) return <Text>{error}</Text>;
     return <View>{/* Render detail */}</View>;
   };
   ```
</details>

---

### Skenario 3: Kerusakan Tampilan Edge-to-Edge pada Berbagai Vendor Android
**Konteks Masalah:**
Aplikasi rilis global mengalami keluhan visual dari pengguna perangkat Samsung OneUI dan Xiaomi MIUI. Ketika keyboard virtual muncul, tombol aksi *"Submit"* tertutup navigation bar sistem atau terpotong oleh notch kamera. Tim sebelumnya menggunakan nilai konstanta statis `marginTop: 40` dan `paddingBottom: 20` untuk mengakali status bar.

**Tugas Evaluasi:**
1. Mengapa hardcoded spacing menjadi anti-pattern kritis dalam arsitektur mobile cross-platform?
2. Bagaimana strategi styling sistem yang benar menggunakan `react-native-safe-area-context` dan `KeyboardAvoidingView`?

<details>
<summary><b>Analisis & Solusi Arsitektur</b></summary>

1. **Akar Masalah:**
   - Setiap pabrikan Android mengimplementasikan tinggi status bar, display cutout (notch/punch-hole), dan tinggi system navigation gesture bar secara berbeda.
   - Nilai hardcoded (`40`, `20`) mengasumsikan standar fiktif. Pada layar dengan gesture bar tipis, tombol melayang terlalu tinggi; pada layar dengan notch lebar, konten terpotong.
2. **Strategi Arsitektur Standar Industri:**
   - Pasang `SafeAreaProvider` di root aplikasi.
   - Gunakan hook `useSafeAreaInsets` untuk menyuntikkan inset secara presisi ke container padding.
   - Bungkus form input dengan `KeyboardAvoidingView` yang dikonfigurasi secara spesifik per platform (`behavior={Platform.OS === 'ios' ? 'padding' : undefined}`).
   ```tsx
   import React from 'react';
   import { View, StyleSheet, KeyboardAvoidingView, Platform, ScrollView } from 'react-native';
   import { useSafeAreaInsets } from 'react-native-safe-area-context';

   export const EdgeToEdgeContainer: React.FC<{ children: React.ReactNode }> = ({ children }) => {
     const insets = useSafeAreaInsets();

     return (
       <KeyboardAvoidingView
         style={styles.keyboardRoot}
         behavior={Platform.OS === 'ios' ? 'padding' : undefined}
       >
         <ScrollView
           contentContainerStyle={[
             styles.scrollContent,
             {
               paddingTop: insets.top,
               paddingBottom: insets.bottom > 0 ? insets.bottom : 16,
               paddingLeft: insets.left + 16,
               paddingRight: insets.right + 16,
             },
           ]}
           keyboardShouldPersistTaps="handled"
         >
           {children}
         </ScrollView>
       </KeyboardAvoidingView>
     );
   };

   const styles = StyleSheet.create({
     keyboardRoot: { flex: 1, backgroundColor: '#0F172A' },
     scrollContent: { flexGrow: 1 },
   });
   ```
</details>

---

## Bagian 4: Practical Chapter Challenge

### Judul Tantangan:
**"Membangun Adaptive Theme-Aware Profile Card dengan Reactive Lifecycle & Edge-to-Edge Safe Insets"**

### Instruksi Spesifikasi:
Buat sebuah file komponen mandiri bernama `AdaptiveProfileCard.tsx` yang mengimplementasikan spesifikasi berikut tanpa error TypeScript:

1. **State & Lifecycle Management:**
   - Menerima prop `userId: string`.
   - Mengambil data profil via simulasi asynchronous service dengan pembersihan `AbortController` (tangani status: `loading`, `success`, `error`).
   - Merekam durasi waktu pengguna berada di komponen menggunakan timer interval yang dibersihkan secara aman saat unmount (*no stale closure*).
2. **Styling & Layout Responsive:**
   - Komponen harus merespons perubahan orientasi layar secara reaktif menggunakan `useWindowDimensions`.
   - Pada layar vertikal (*portrait*), tampilkan tata letak bertingkat (*column*).
   - Pada layar horizontal (*landscape*), tampilkan tata letak berdampingan (*row*).
   - Integrasikan `useSafeAreaInsets` untuk memastikan container tidak menabrak notch atau navigation bar.
3. **Design System & Theme Integration:**
   - Gunakan `StyleSheet.create` yang mematuhi skema warna adaptif (*Dark / Light Mode*) berdasarkan hook `useColorScheme`.
   - Dilarang keras menggunakan inline object style untuk layout utama.

### Rubrik Penilaian Teknis:
| Kriteria | Bobot | Deskripsi Kualitas |
| :--- | :--- | :--- |
| **Lifecycle Integrity** | 30% | Cleanup effect dilakukan sempurna tanpa memory leak, abortable fetch diimplementasikan, timer bebas dari stale closure. |
| **Responsive Flexibility** | 25% | Menggunakan `useWindowDimensions` dengan layout switching (`column` vs `row`) yang mulus tanpa visual glitch. |
| **Safe Area Insets** | 20% | Penanganan edge-to-edge system insets akurat pada notch dan bottom bar. |
| **Styling Performance** | 15% | Penggunaan `StyleSheet.create` optimal tanpa alokasi inline berlebihan. |
| **TypeScript Strictness** | 10% | Bebas type `any`, interface props dan state didefinisikan eksplisit. |

---

## Bagian 5: Checklist Pemahaman Mandiri

Beri tanda centang $(\checkmark)$ pada kemampuan yang telah Anda kuasai dengan jujur:

- [ ] Saya mampu menjelaskan perbedaan eksekusi render tree antara arsitektur Bridge klasik dan Fabric C++ Shadow Tree.
- [ ] Saya memahami siklus hidup komponen fungsional React dan mampu mengimplementasikan cleanup function untuk event, timer, dan abortable network requests.
- [ ] Saya tahu kapan harus menggunakan `useLayoutEffect` dibandingkan `useEffect` dan memahami risiko frame drop-nya.
- [ ] Saya mampu menjelaskan perbedaan teknis unit DP/Points di React Native dengan Physical Pixels layar native.
- [ ] Saya memahami default Flexbox pada React Native (`column`, `flexShrink: 0`, `border-box`) dan perbedaannya dengan browser.
- [ ] Saya mampu merancang tata letak adaptif yang reaktif terhadap rotasi perangkat menggunakan `useWindowDimensions`.
- [ ] Saya menguasai integrasi `react-native-safe-area-context` dan mampu menyelesaikan masalah notch dan Android navigation bars.
- [ ] Saya dapat mengidentifikasi stale closure pada `useEffect` dan memperbaikinya menggunakan functional state update atau `useRef`.
- [ ] Saya memahami trade-off performa antara compile-time utility styling (NativeWind) dengan runtime CSS-in-JS.
- [ ] Saya mampu memecahkan masalah layout thrashing pada list data besar melalui teknik variant caching dan memoization.
