# BAB-06-High-Performance-Animations-dan-Gestures: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi teknis, verifikasi pemahaman arsitektur, dan uji implementasi hands-on untuk materi **High-Performance Animations & Gestures** pada React Native. Fokus pengujian mencakup runtime Reanimated (v2/v3), Worklets, UI thread execution, integrasi Gesture Handler, shared element transitions, hingga teknik profiling animasi 60/120 FPS.

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1: Threading Model Animasi Native vs JS Thread
**Pertanyaan:** Mengapa eksekusi animasi murni di JavaScript thread (JS Thread) sering mengalami *frame drops* (jank) saat aplikasi melakukan operasi asynchronous seperti network fetch atau re-rendering list yang kompleks, dan bagaimana React Native Reanimated menyelesaikan kendala arsitektural ini?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
JavaScript thread pada React Native bersifat single-threaded dan menjalankan seluruh siklus hidup React (reconciliation, state updates, virtual DOM diffing), logic bisnis, pemrosesan respon HTTP, hingga serialisasi bridge/JSI. Ketika JS Thread terblokir oleh komputasi berat (misalnya JSON parsing berukuran besar atau re-render ratusan item pada FlatList), event frame animation (`requestAnimationFrame`) terlambat dieksekusi, mengakibatkan frame rate turun di bawah target 60 FPS (frame time > 16.67ms).

React Native Reanimated mengatasi masalah ini dengan memindahkan engine animasi langsung ke **UI Thread / Render Thread** melalui runtime JavaScript sekunder yang dieksekusi oleh mesin Hermes/JSC secara terpisah. Nilai animasi dimutasi langsung di UI Thread menggunakan shared memory (`SharedValue`), sehingga interpolasi transformasi visual dan gesture tracking tetap berjalan mulus pada 60/120 FPS meskipun JS Thread utama sedang mengalami komputasi intensif hingga 100% CPU lock.
</details>

---

### Soal 2: Konsep Dasar dan Karakteristik Worklet
**Pertanyaan:** Jelaskan apa yang dimaksud dengan *Worklet* dalam Reanimated, apa fungsi direktif `'worklet';` di awal sebuah fungsi, dan bagaimana Babel plugin memproses fungsi tersebut pada saat build time?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
*Worklet* adalah fungsi JavaScript ringkas yang dikompilasi secara khusus agar dapat diserialisasi dan dieksekusi di thread terpisah (biasanya UI thread runtime). 

- **Fungsi `'worklet';`**: Direktif ini memberi sinyal ke Babel compiler (`react-native-reanimated/plugin`) bahwa fungsi tersebut harus diperlakukan sebagai worklet, bukan fungsi JS biasa.
- **Build-Time Transformation**: Babel plugin mentranspilasi fungsi bertanda `'worklet';` menjadi sebuah objek metadata JavaScript yang berisi:
  1. Versi string bytecode/AST dari fungsi yang dapat dibaca oleh runtime UI.
  2. Tabel *closure capture* yang mendata semua variabel di luar lingkup fungsi yang perlu di-copy atau di-share ke UI runtime.
  3. Properti `_closure` yang memetakan binding variabel agar dapat diakses secara transparan saat dipanggil di UI Thread.

Fungsi bawaan Reanimated seperti callback pada `useAnimatedStyle`, `useDerivedValue`, dan gesture callbacks otomatis disuntikkan direktif worklet oleh Babel plugin.
</details>

---

### Soal 3: SharedValue vs React State (`useState`)
**Pertanyaan:** Dalam konteks performa animasi, mengapa memperbarui nilai animasi menggunakan `useState` merupakan *anti-pattern*, dan bagaimana cara kerja `useSharedValue` yang membuatnya jauh lebih efisien?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
Memperbarui posisi atau skala animasi dengan `useState`:
1. Memicu siklus reconciler React penuh: pemanggilan render function komponen, reconciler diffing, evaluasi hook, dan komitmen update ke Shadow Tree.
2. Seluruh alur terjadi di JS Thread, menimbulkan overhead CPU dan memory allocation per frame (60 kali per detik).

Sebaliknya, `useSharedValue`:
1. Menyimpan referensi mutable pointer thread-safe yang diakses melalui C++ layer menggunakan JSI (JavaScript Interface).
2. Perubahan pada `sharedValue.value` di UI thread **tidak** memicu re-render komponen React.
3. Node tampilan yang terikat melalui `useAnimatedStyle` akan langsung menerima update transformasi geometris di UI Thread tanpa menyentuh siklus render React sama sekali.
</details>

---

### Soal 4: Peran React Native Gesture Handler (RNGH)
**Pertanyaan:** Mengapa gesture event native seperti `PanResponder` bawaan React Native memiliki latensi lebih tinggi dibandingkan `GestureDetector` dari `react-native-gesture-handler` (RNGH v2)?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
`PanResponder` bergantung pada event handling sistem React Native standar:
1. Sentuhan fisik di layar diterima oleh OS (Android `MotionEvent` / iOS `UIGestureRecognizer`).
2. Event dikirim ke platform bridge atau diteruskan ke JS Thread.
3. JS Thread memproses logic sentuhan dan menghitung koordinat baru.
4. Nilai baru dikirim kembali ke UI thread untuk memperbarui posisi view. Loop round-trip ini menciptakan keterlambatan (touch-to-draw latency) minimal 1–2 frame.

`react-native-gesture-handler` mengintegrasikan handler gesture langsung pada level native OS platform dan terhubung langsung ke Reanimated UI worklet runtime via JSI:
- Event gesture langsung ditangkap oleh C++ / Native layer dan dikirim instan ke UI worklet thread.
- Koordinat `translationX`/`translationY` langsung memutasi `SharedValue` di thread yang sama tanpa ada transit ke JS Thread, menghasilkan tracking sentuhan dengan latensi nol (zero round-trip latency).
</details>

---

### Soal 5: Komputasi Layout Animasi: Transform vs Posisi Statis
**Pertanyaan:** Mengapa menganimasikan properti layout seperti `top`, `left`, `width`, `height`, atau `margin` dianggap merusak performa animasi, sedangkan memanipulasi properti `transform` (`translateX`, `scale`) dan `opacity` sangat direkomendasikan?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
1. **Reflow & Layout Recalculation (Yoga Engine):**
   Memodifikasi `top`, `left`, `width`, atau `height` memaksa mesin layout React Native (Yoga Engine) melakukan kalkulasi ulang hierarki layout (*measure & layout pass*) pada view tersebut dan seluruh child/sibling nodes di sekitarnya. Ini memicu pipeline layout komputasi berat di native thread.
2. **GPU Composition vs CPU Layout:**
   Properti `transform` (`translate`, `scale`, `rotate`) dan `opacity` tidak mengubah geometri bounding-box layout Yoga. Perubahan ini ditangani langsung oleh subsistem compositing GPU (Core Animation di iOS atau RenderNode DisplayList di Android) sebagai manipulasi matriks transformasi grafis. Oleh karena itu, operasi ini dapat dieksekusi secara hardware-accelerated tanpa reflow biaya komputasi tinggi.
</details>

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 6: Komunikasi Lintas Thread Menggunakan `runOnJS` dan `runOnUI`
**Pertanyaan:** Analisis kode berikut dan jelaskan apa yang terjadi di balik layar pada runtime JSI saat `runOnJS` dipanggil dari dalam gesture callback:

```tsx
const onEndGesture = () => {
  'worklet';
  // UI Thread execution
  offset.value = withSpring(0);
  runOnJS(notifyServerAnalytic)(offset.value);
};
```
Kapan developer harus menggunakan `runOnJS`, dan apa risiko arsitektural jika `runOnJS` dipanggil terlalu sering (misalnya di dalam `onUpdate` per 16ms)?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
1. **Mekanisme JSI:**
   Ketika `runOnJS(notifyServerAnalytic)(arg)` dipanggil dari dalam worklet UI, Reanimated mengambil fungsi JS yang berada di JS runtime, membuat payload pesan yang diserialisasi melalui JSI microtask queue, dan menjadwalkan eksekusinya pada message queue JS thread loop berikutnya.
2. **Kapan Digunakan:**
   Digunakan saat worklet UI perlu berinteraksi dengan API yang hanya hidup di JS Thread, seperti navigasi (`navigation.navigate`), dispatch state global (Redux/Zustand), penyimpanan lokal (AsyncStorage/MMKV non-sync), pemanggilan callback prop, atau analytics network request.
3. **Risiko Arsitektural Jika Dipanggil di `onUpdate`:**
   Memanggil `runOnJS` pada gesture stream frekuensi tinggi (60–120 call/detik) akan membanjiri JS Event Loop dengan task serialization. Hal ini menyebabkan fenomena *Bridge/Queue Congestion*: JS thread menjadi tidak responsif, garbage collection terpicu secara agresif, dan keuntungan eksekusi gesture di UI Thread menjadi sia-sia karena bottleneck komunikasi antar-thread.
</details>

---

### Soal 7: Karakteristik `withSpring` vs `withTiming`
**Pertanyaan:** Jelaskan perbedaan fundamental mekanisme kalkulasi matematis antara animasi berbasis durasi (`withTiming`) dan animasi berbasis fisika (`withSpring`). Parameter apa saja yang mengontrol osilasi pegas pada Reanimated (seperti `damping`, `stiffness`, `mass`), dan mengapa aplikasi modern berorientasi gestur lebih memilih spring physics?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
1. **Perbedaan Matematis:**
   - `withTiming`: Menggunakan fungsi interpolasi kurva kurir tetap (Bézier curves / Easing functions) berdasarkan waktu deterministik (`duration: number`). Kecepatan objek dipaksa mengikuti fungsi matematika waktu $f(t)$ terlepas dari inersia awal.
   - `withSpring`: Menggunakan persamaan diferensial hukum fisika gerak harmonik teredam (*damped harmonic oscillator*):
     $$F = -kx - c v$$
     di mana posisi dan kecepatan objek dihitung dinamis setiap frame berdasarkan inersia, resistansi, dan gaya tarik pegas.
2. **Parameter Pengontrol Spring:**
   - `mass` ($m$): Bobot inersia objek. Semakin besar mass, semakin lambat objek berakselerasi dan berhenti.
   - `stiffness` ($k$): Kekakuan pegas. Semakin tinggi nilainya, semakin besar gaya tarik ke posisi target (gerakan lebih agresif/cepat).
   - `damping` ($c$): Redaman gesekan. Menentukan seberapa cepat osilasi getaran ditiadakan. Nilai rendah menyebabkan bouncing berkepanjangan (underdamped), nilai seimbang menghasilkan transisi mulus tanpa overshoot (critically damped).
   - `velocity`: Kecepatan awal saat animasi dimulai.
3. **Alasan Dipilih pada Gesture-driven UI:**
   Ketika pengguna melepaskan jari dari layar dengan kecepatan tertentu (*fling gesture*), nilai gesture velocity (`event.velocityX`) dapat langsung dioper ke `withSpring({ velocity: event.velocityX })`. Animasi melanjutkan momentum lemparan jari pengguna secara kontinu tanpa jeda atau pemotongan kecepatan yang kaku, menciptakan kesan interaksi sentuhan yang natural dan organik.
</details>

---

### Soal 8: Integrasi Komposisi Gesture (`Simultaneous`, `Exclusive`, `Race`)
**Pertanyaan:** Dalam aplikasi video streaming atau photo viewer, Anda sering kali harus mengelola `PinchGesture` (zoom), `PanGesture` (panning/drag), dan `TapGesture` (toggle controls UI) pada satu container view yang sama. Jelaskan bagaimana RNGH v2 mengelola relasi gesture ini menggunakan API `Gesture.Simultaneous`, `Gesture.Exclusive`, dan `Gesture.Race`.

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
RNGH v2 menyediakan deklarasi hubungan gesture state machine tingkat lanjut:

1. **`Gesture.Simultaneous(panGesture, pinchGesture)`:**
   Mengizinkan kedua gesture aktif dan memproses event touch secara bersamaan. Sangat penting pada kanvas peta atau penampil foto: pengguna dapat mencubit untuk zoom sambil menggeser posisi jari di layar sekaligus tanpa salah satu gesture membatalkan yang lain.
2. **`Gesture.Exclusive(doubleTapGesture, singleTapGesture)`:**
   Mendefinisikan hierarki prioritas mutual-exclusion. `singleTapGesture` akan menunggu dalam durasi waktu tertentu (`maxDelay`) untuk memastikan apakah sentuhan kedua terjadi. Jika terjadi sentuhan kedua, `doubleTapGesture` yang diaktifkan (misalnya: zoom-in otomatis) dan `singleTapGesture` digagalkan. Jika batas waktu habis tanpa sentuhan lanjutan, barulah `singleTap` dieksekusi (misalnya: menyembunyikan player controls).
3. **`Gesture.Race(swipeGesture, longPressGesture)`:**
   Membuat kompetisi deterministik antar gesture. Gesture mana pun yang pertama kali memenuhi kriteria aktivasinya (misalnya threshold displacement pada swipe terpenuhi sebelum timer `minDurationMs` pada long-press selesai) akan memenangkan state `ACTIVE`, dan semua gesture saingan lainnya dalam race group akan dipaksa berpindah ke state `FAILED` atau `CANCELLED`.
</details>

---

### Soal 9: Optimasi Memory & Render Pipeline dengan Animated Style
**Pertanyaan:** Perhatikan potongan kode berikut:

```tsx
// Anti-pattern
const animatedStyle = useAnimatedStyle(() => {
  return {
    transform: [{ translateX: x.value }],
    backgroundColor: isDarkMode ? '#121212' : '#FFFFFF',
  };
}, [isDarkMode]);
```
Apa dampak memasukkan dependensi non-animasi (`isDarkMode`) ke dalam dependency array `useAnimatedStyle`, dan bagaimana pendekatan arsitektur yang benar untuk menangani properti statis vs dinamis teranimasi?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
1. **Dampak Negatif:**
   - Memasukkan dependensi React state (`isDarkMode`) ke dependency array memaksa Reanimated menghancurkan dan menginstansiasi ulang worklet context serta meregistrasikan kembali updater view node ke UI Thread setiap kali `isDarkMode` berubah.
   - Properti yang tidak berubah per frame animasi (seperti `backgroundColor` dari theme) ikut dievaluasi berulang-ulang di UI thread saat `x.value` bergerak, membebani alokasi C++ JSI object.
2. **Pendekatan Arsitektur yang Benar:**
   - Pisahkan style statis atau berbasis React state reguler ke dalam `style` standar (menggunakan `StyleSheet.create` atau array style).
   - Batasi `useAnimatedStyle` murni hanya untuk properti yang nilainya dinamis dimutasi oleh `SharedValue` di UI Thread:

```tsx
// Best Practice
const dynamicAnimatedStyle = useAnimatedStyle(() => {
  'worklet';
  return {
    transform: [{ translateX: x.value }],
  };
});

return (
  <Animated.View 
    style={[
      styles.baseContainer, 
      { backgroundColor: isDarkMode ? '#121212' : '#FFFFFF' }, 
      dynamicAnimatedStyle
    ]} 
  />
);
```
Jika warna latar belakang memang harus bertransisi halus mengikuti animasi, gunakan `interpolateColor` yang dikendalikan oleh `SharedValue` progresif, bukan conditional branching berbasis React state.
</details>

---

### Soal 10: Shared Element Transition (SET) Lifecycle & Gotchas
**Pertanyaan:** Bagaimana mekanisme kerja Shared Element Transitions pada Reanimated v3 (menggunakan `sharedTransitionTag`), dan apa saja kendala yang sering terjadi ketika elemen berpindah antar screen di React Navigation (misalnya perbedaan clipping, layout hierarchy, atau image resizeMode)?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
1. **Mekanisme Kerja:**
   - Reanimated menandai dua komponen `Animated.View` atau `Animated.Image` pada screen yang berbeda dengan `sharedTransitionTag` identik.
   - Ketika navigasi screen terjadi, native layout manager Reanimated mengukur posisi absolut di layar (`x, y, width, height`) dari node target di screen A dan node tujuan di screen B.
   - Reanimated membuat view snapshot temporer yang di-render di layer overlay khusus (di atas stack navigasi) dan menganimasikan properti transformasi geometris dari koordinat screen A ke screen B selama transisi berlangsung, lalu menempelkannya kembali ke view hierarchy screen tujuan saat transisi selesai.
2. **Gotchas & Kendala Produksi:**
   - **Perbedaan `resizeMode` Image:** Jika screen asal menggunakan `resizeMode="cover"` dan screen tujuan menggunakan `resizeMode="contain"`, transisi dapat mengalami glitch aspek rasio mendadak karena proses re-interpolasi rasterisasi gambar.
   - **Overflow & Clipping:** Jika salah satu parent view memiliki `overflow: 'hidden'`, snapshot shared element dapat terpotong secara visual di tengah animasi saat bergerak melintasi batas parent lama.
   - **Perbedaan Border Radius:** Jika radius sudut tidak disinkronkan melalui custom shared transition configurator, bentuk visual elemen akan melompat secara instan di awal/akhir navigasi.
   - **Timing Lifecycle React Navigation:** Jika screen tujuan memerlukan fetch data sebelum merender elemen target, tag shared element tidak ditemukan pada saat transisi dimulai, menyebabkan transisi gagal kembali ke navigasi slide default.
</details>

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Kasus)

---

### Skenario 1: Bottom Sheet Modal Laggy & Gesture Dropping pada Android Low-End

#### Konteks & Gejala Masalah
Sebuah aplikasi e-commerce merilis fitur Bottom Sheet interaktif untuk filter produk. Pada iPhone 13 ke atas fitur berjalan sangat mulus (120 FPS). Namun, pada perangkat Android budget (contoh: chipset Helio P35 / Snapdragon 665 dengan RAM 3GB), Bottom Sheet mengalami:
1. Gesture sentuhan sering lepas (*snapping* tiba-tiba kembali ke bawah saat pengguna menggeser perlahan).
2. Frame drop parah (FPS turun ke 18–24 FPS).
3. Saat pengguna melepaskan jari, animasi snapping menuju anchor point terhenti sejenak (*freeze*) selama 300ms sebelum mulai bergerak.

#### Analisis Akar Masalah (Root Cause)
1. **Kompilasi JS Bridge:** Pengembang membungkus callback gesture menggunakan fungsi biasa yang mengeksekusi `setState` pada event drag, mengirim data ratusan kali lewat bridge.
2. **Layout Thrashing:** Sheet container menggunakan manipulasi `height` secara langsung saat di-drag:
   ```tsx
   // Kode bermasalah
   const animatedStyle = useAnimatedStyle(() => ({
     height: sheetPosition.value, // Memicu reflow layout Yoga per frame
   }));
   ```
3. **Heavy Re-rendering Sibling:** Konten di dalam sheet merender list ribuan item tanpa memoization, sehingga ketika layout height berubah, seluruh child component melakukan re-calculating dimensions.

#### Solusi Arsitektural & Perbaikan Kode

1. Ganti manipulasi `height` dengan `transform: [{ translateY }]` dengan fixed layout dimensions.
2. Gunakan `Gesture.Pan()` yang murni berjalan di UI worklet dengan event tracking kontinu.
3. Terapkan `clamp` matematis di worklet untuk mencegah nilai out-of-bounds tanpa round-trip JS.

```tsx
import React from 'react';
import { StyleSheet, Dimensions } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  clamp,
} from 'react-native-reanimated';

const { height: SCREEN_HEIGHT } = Dimensions.get('window');
const SHEET_MAX_TRANSLATE = -SCREEN_HEIGHT * 0.7; // Buka hingga 70% layar

export const OptimizedBottomSheet = ({ children }: { children: React.ReactNode }) => {
  const translateY = useSharedValue(0);
  const context = useSharedValue(0);

  const panGesture = Gesture.Pan()
    .onStart(() => {
      'worklet';
      context.value = translateY.value;
    })
    .onUpdate((event) => {
      'worklet';
      // Murni dihitung di UI thread tanpa bridge
      translateY.value = clamp(
        context.value + event.translationY,
        SHEET_MAX_TRANSLATE,
        0
      );
    })
    .onEnd((event) => {
      'worklet';
      // Snapping berdasarkan velocity inersia dan posisi
      const shouldSnapToTop = 
        translateY.value < SHEET_MAX_TRANSLATE / 2 || event.velocityY < -800;

      translateY.value = withSpring(
        shouldSnapToTop ? SHEET_MAX_TRANSLATE : 0,
        {
          damping: 20,
          stiffness: 150,
          mass: 0.8,
          velocity: event.velocityY,
        }
      );
    });

  const animatedStyle = useAnimatedStyle(() => {
    'worklet';
    return {
      transform: [{ translateY: translateY.value }],
    };
  });

  return (
    <GestureDetector gesture={panGesture}>
      <Animated.View style={[styles.sheetContainer, animatedStyle]}>
        {children}
      </Animated.View>
    </GestureDetector>
  );
};

const styles = StyleSheet.create({
  sheetContainer: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: -SHEET_MAX_TRANSLATE, // Tersembunyi di bawah layar
    height: -SHEET_MAX_TRANSLATE,
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    elevation: 16,
  },
});
```

---

### Skenario 2: FlatList Scroll Stuttering Saat Sync Animasi Parallax Header

#### Konteks & Gejala Masalah
Aplikasi media sosial memiliki profil pengguna dengan Sticky Parallax Header:
- Saat FlatList di-scroll ke atas, avatar mengecil dan header meredup.
- Saat di-overscroll ke bawah (pull-down), gambar cover header membesar (*scale-up*).

Masalah muncul: Ketika user melakukan *fast scroll* (fling), animasi header tersentak-sentak (*stuttering*), dan scroll list terasa berat seakan kehilangan inersia native.

#### Analisis Akar Masalah (Root Cause)
1. Developer mendengarkan event scroll menggunakan event listener React Native standar:
   ```tsx
   <FlatList onScroll={(e) => setScrollY(e.nativeEvent.contentOffset.y)} />
   ```
   State `scrollY` memperbarui state React puluhan kali per detik, memicu re-render FlatList dan seluruh komponen profil.
2. Penggunaan `Animated.event` versi legacy yang tidak dikonfigurasikan dengan `useNativeDriver: true`.

#### Solusi Arsitektural & Perbaikan Kode

1. Gunakan `Animated.FlatList` dari `react-native-reanimated`.
2. Ikat `scrollHandler` menggunakan hook `useAnimatedScrollHandler` yang langsung mengeksekusi komputasi di UI Thread.
3. Gunakan `interpolate` dan `Extrapolation.CLAMP` untuk mengontrol skala dan translasi header tanpa menyentuh React render lifecycle.

```tsx
import React from 'react';
import { StyleSheet, View, Text } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedScrollHandler,
  useAnimatedStyle,
  interpolate,
  Extrapolation,
} from 'react-native-reanimated';

const HEADER_HEIGHT = 250;

export const ParallaxProfileScreen = ({ posts }: { posts: Array<{ id: string; title: string }> }) => {
  const scrollY = useSharedValue(0);

  const scrollHandler = useAnimatedScrollHandler({
    onScroll: (event) => {
      'worklet';
      scrollY.value = event.contentOffset.y;
    },
  });

  const headerAnimatedStyle = useAnimatedStyle(() => {
    'worklet';
    // Zoom in saat overscroll pull-down (scrollY < 0)
    const scale = interpolate(
      scrollY.value,
      [-HEADER_HEIGHT, 0],
      [2, 1],
      Extrapolation.CLAMP
    );

    // Parallax effect saat scroll up (scrollY > 0)
    const translateY = interpolate(
      scrollY.value,
      [0, HEADER_HEIGHT],
      [0, -HEADER_HEIGHT / 2],
      Extrapolation.CLAMP
    );

    return {
      transform: [{ translateY }, { scale }],
    };
  });

  return (
    <View style={styles.container}>
      <Animated.View style={[styles.header, headerAnimatedStyle]}>
        <View style={styles.headerContent}>
          <Text style={styles.headerTitle}>User Profile</Text>
        </View>
      </Animated.View>

      <Animated.FlatList
        data={posts}
        keyExtractor={(item) => item.id}
        onScroll={scrollHandler}
        scrollEventThrottle={16} // 60 FPS sampling
        contentContainerStyle={{ paddingTop: HEADER_HEIGHT }}
        renderItem={({ item }) => (
          <View style={styles.postItem}>
            <Text>{item.title}</Text>
          </View>
        )}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FAFAFA' },
  header: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: HEADER_HEIGHT,
    backgroundColor: '#3B82F6',
    zIndex: 10,
  },
  headerContent: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  headerTitle: { color: '#FFFFFF', fontSize: 20, fontWeight: '700' },
  postItem: {
    padding: 20,
    borderBottomWidth: 1,
    borderColor: '#E5E7EB',
    backgroundColor: '#FFFFFF',
  },
});
```

---

### Skenario 3: Race Condition & Memory Leak pada Micro-Interactions Lottie/Reanimated

#### Konteks & Gejala Masalah
Aplikasi trading crypto memiliki widget animasi real-time ticker harga. Jika harga naik, card berkedip hijau dengan animasi scale-up; jika turun, berkedip merah. Data harga di-stream via WebSocket dengan frekuensi hingga 10 update per detik.

Gejala yang terjadi:
1. Setelah aplikasi berjalan selama 10 menit, memori RAM melonjak drastis (*memory leak*) hingga terjadi crash Out-Of-Memory (OOM) pada Android.
2. Animasi visual sering "tersangkut" pada scale 1.05 atau opacity 0.5 dan tidak pernah kembali ke posisi normal (*stuck state*).

#### Analisis Akar Masalah (Root Cause)
1. **Uncancelled Animation Sequences:** Setiap paket WebSocket memicu pemanggilan animasi baru:
   ```tsx
   scale.value = withSequence(withTiming(1.05, { duration: 100 }), withTiming(1, { duration: 100 }));
   ```
   Jika update berikutnya masuk dalam rentang waktu <200ms, animasi lama ditumpuk tanpa dibatalkan secara bersih, menyebabkan alokasi closure native animation loop yang tidak ter-garbage-collect.
2. **Missing Component Unmount Cleanup:** Komponen row unmount saat berpindah tab sementara animasi sedang berjalan aktif di UI thread, meninggalkan referensi native dangling pointer.

#### Solusi Arsitektural & Perbaikan Kode

1. Gunakan fungsi `cancelAnimation(sharedValue)` dari Reanimated sebelum memulai sequence baru untuk membatalkan thread execution sebelumnya secara deterministik.
2. Manfaatkan hook cleanup `useEffect` untuk memastikan seluruh shared values dihentikan animasinya saat komponen unmount.
3. Terapkan throttling ringan di JS thread sebelum memicu animasi visual jika frekuensi stream melebihi batas pandang manusia (>30 FPS).

```tsx
import React, { useEffect, useRef } from 'react';
import { StyleSheet, Text } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSequence,
  withTiming,
  interpolateColor,
  cancelAnimation,
} from 'react-native-reanimated';

interface PriceTickerProps {
  price: number;
}

export const ResilientPriceTicker = ({ price }: PriceTickerProps) => {
  const prevPriceRef = useRef(price);
  const flashAnim = useSharedValue(0); // 0 = Neutral, -1 = Red, 1 = Green
  const scale = useSharedValue(1);

  useEffect(() => {
    const isPriceUp = price > prevPriceRef.current;
    const isPriceDown = price < prevPriceRef.current;
    prevPriceRef.current = price;

    if (!isPriceUp && !isPriceDown) return;

    // 1. CANCEL animasi aktif untuk mencegah overlapping & leak
    cancelAnimation(scale);
    cancelAnimation(flashAnim);

    // 2. Reset initial state instan di UI thread
    flashAnim.value = isPriceUp ? 1 : -1;
    scale.value = 1;

    // 3. Jalankan sequence baru yang terkontrol
    scale.value = withSequence(
      withTiming(1.04, { duration: 80 }),
      withTiming(1, { duration: 120 })
    );

    flashAnim.value = withTiming(0, { duration: 400 });

    // 4. Cleanup saat unmount
    return () => {
      cancelAnimation(scale);
      cancelAnimation(flashAnim);
    };
  }, [price]);

  const animatedStyle = useAnimatedStyle(() => {
    'worklet';
    const backgroundColor = interpolateColor(
      flashAnim.value,
      [-1, 0, 1],
      ['rgba(239, 68, 68, 0.2)', 'rgba(255, 255, 255, 1)', 'rgba(34, 197, 94, 0.2)']
    );

    return {
      transform: [{ scale: scale.value }],
      backgroundColor,
    };
  });

  return (
    <Animated.View style={[styles.card, animatedStyle]}>
      <Text style={styles.priceText}>${price.toFixed(2)}</Text>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  card: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  priceText: {
    fontSize: 18,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
  },
});
```

---

## Bagian 4: Practical Chapter Challenge

### Judul Challenge: "Interactive Tinder-Style Swipeable Deck with Physics & Velocity Throw"

#### Deskripsi & Sasaran
Anda diminta untuk membangun komponen kartu swipe interaktif (*Swipeable Deck*) tingkat produksi yang tahan uji performa pada Android dan iOS. Komponen ini digunakan untuk memilih atau menolak item dengan gestur horizontal cepat.

#### Persyaratan Teknis & Spesifikasi Implementasi
1. **Arsitektur Thread:**
   - 100% perhitungan pergeseran (`translationX`, `translationY`) dan rotasi sudut (`rotateZ`) wajib dieksekusi di **UI Thread** via worklet.
   - Dilarang menggunakan `useState` untuk mencatat koordinat posisi selama jari masih menempel di layar.
2. **Kalkulasi Sudut Rotasi & Opacity Badge:**
   - Saat kartu ditarik ke kanan: Sudut rotasi miring searah jarum jam (maksimal 15 derajat), dan overlay badge label **"LIKE"** (warna hijau) bertambah opacity-nya dari 0 ke 1 seiring pertambahan jarak.
   - Saat kartu ditarik ke kiri: Sudut rotasi miring berlawanan arah jarum jam (maksimal -15 derajat), dan overlay badge **"NOPE"** (warna merah) bertambah opacity-nya dari 0 ke 1.
3. **Threshold & Inersia Physics:**
   - Jika kartu dilempar dengan kecepatan tinggi (`Math.abs(event.velocityX) > 1200`) atau ditarik melebihi threshold $40\%$ lebar layar:
     - Kartu harus terlempar keluar layar (*thrown off-screen*) ke arah yang relevan menggunakan `withTiming` atau `withSpring`.
     - Panggil callback `onSwipeLeft` atau `onSwipeRight` ke JS Thread menggunakan `runOnJS` **hanya setelah kartu benar-benar lenyap dari layar**.
   - Jika threshold tidak terpenuhi:
     - Kartu harus kembali membal ke titik tengah `(0, 0)` secara halus menggunakan `withSpring` dengan parameter `damping: 18, stiffness: 120`.
4. **Stacked Deck Visuals:**
   - Di belakang kartu aktif, terdapat kartu berikutnya (kartu kedua) yang sedikit mengecil (`scale: 0.95`) dan berada di posisi sedikit lebih rendah (`translateY: 10`). Saat kartu depan di-swipe keluar, kartu kedua membesar secara progresif ke `scale: 1.0` dan `translateY: 0`.

#### Arsitektur Solusi Lengkap

```tsx
import React from 'react';
import { StyleSheet, View, Text, Dimensions } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  interpolate,
  runOnJS,
  Extrapolation,
} from 'react-native-reanimated';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const SWIPE_THRESHOLD = SCREEN_WIDTH * 0.4;
const VELOCITY_THRESHOLD = 1200;

interface CardData {
  id: string;
  name: string;
  age: number;
  bio: string;
}

interface SwipeCardProps {
  card: CardData;
  onSwipeLeft: (id: string) => void;
  onSwipeRight: (id: string) => void;
}

export const SwipeableCard = ({ card, onSwipeLeft, onSwipeRight }: SwipeCardProps) => {
  const translateX = useSharedValue(0);
  const translateY = useSharedValue(0);

  const handleSwipeComplete = (direction: 'left' | 'right') => {
    if (direction === 'right') {
      onSwipeRight(card.id);
    } else {
      onSwipeLeft(card.id);
    }
  };

  const panGesture = Gesture.Pan()
    .onUpdate((event) => {
      'worklet';
      translateX.value = event.translationX;
      translateY.value = event.translationY;
    })
    .onEnd((event) => {
      'worklet';
      const isFlingRight = event.velocityX > VELOCITY_THRESHOLD;
      const isFlingLeft = event.velocityX < -VELOCITY_THRESHOLD;
      const isSwipeRight = translateX.value > SWIPE_THRESHOLD || isFlingRight;
      const isSwipeLeft = translateX.value < -SWIPE_THRESHOLD || isFlingLeft;

      if (isSwipeRight) {
        translateX.value = withTiming(
          SCREEN_WIDTH * 1.5,
          { duration: 250 },
          (finished) => {
            if (finished) {
              runOnJS(handleSwipeComplete)('right');
            }
          }
        );
      } else if (isSwipeLeft) {
        translateX.value = withTiming(
          -SCREEN_WIDTH * 1.5,
          { duration: 250 },
          (finished) => {
            if (finished) {
              runOnJS(handleSwipeComplete)('left');
            }
          }
        );
      } else {
        // Snap back to origin dengan spring physics
        translateX.value = withSpring(0, { damping: 18, stiffness: 120 });
        translateY.value = withSpring(0, { damping: 18, stiffness: 120 });
      }
    });

  const cardAnimatedStyle = useAnimatedStyle(() => {
    'worklet';
    const rotateZ = `${interpolate(
      translateX.value,
      [-SCREEN_WIDTH / 2, 0, SCREEN_WIDTH / 2],
      [-15, 0, 15],
      Extrapolation.CLAMP
    )}deg`;

    return {
      transform: [
        { translateX: translateX.value },
        { translateY: translateY.value },
        { rotateZ },
      ],
    };
  });

  const likeOpacityStyle = useAnimatedStyle(() => {
    'worklet';
    const opacity = interpolate(
      translateX.value,
      [0, SWIPE_THRESHOLD / 2],
      [0, 1],
      Extrapolation.CLAMP
    );
    return { opacity };
  });

  const nopeOpacityStyle = useAnimatedStyle(() => {
    'worklet';
    const opacity = interpolate(
      translateX.value,
      [-SWIPE_THRESHOLD / 2, 0],
      [1, 0],
      Extrapolation.CLAMP
    );
    return { opacity };
  });

  return (
    <View style={styles.cardWrapper}>
      <GestureDetector gesture={panGesture}>
        <Animated.View style={[styles.card, cardAnimatedStyle]}>
          {/* Like Badge */}
          <Animated.View style={[styles.badge, styles.likeBadge, likeOpacityStyle]}>
            <Text style={styles.likeBadgeText}>LIKE</Text>
          </Animated.View>

          {/* Nope Badge */}
          <Animated.View style={[styles.badge, styles.nopeBadge, nopeOpacityStyle]}>
            <Text style={styles.nopeBadgeText}>NOPE</Text>
          </Animated.View>

          {/* Card Content */}
          <View style={styles.content}>
            <Text style={styles.nameText}>{card.name}, {card.age}</Text>
            <Text style={styles.bioText}>{card.bio}</Text>
          </View>
        </Animated.View>
      </GestureDetector>
    </View>
  );
};

const styles = StyleSheet.create({
  cardWrapper: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
  },
  card: {
    width: SCREEN_WIDTH * 0.9,
    height: 520,
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 8,
    padding: 24,
    justifyContent: 'flex-end',
  },
  badge: {
    position: 'absolute',
    top: 24,
    paddingHorizontal: 16,
    paddingVertical: 6,
    borderWidth: 3,
    borderRadius: 8,
  },
  likeBadge: {
    left: 24,
    borderColor: '#22C55E',
  },
  likeBadgeText: {
    color: '#22C55E',
    fontSize: 24,
    fontWeight: '800',
  },
  nopeBadge: {
    right: 24,
    borderColor: '#EF4444',
  },
  nopeBadgeText: {
    color: '#EF4444',
    fontSize: 24,
    fontWeight: '800',
  },
  content: {
    marginBottom: 8,
  },
  nameText: {
    fontSize: 26,
    fontWeight: '700',
    color: '#1F2937',
  },
  bioText: {
    fontSize: 16,
    color: '#6B7280',
    marginTop: 6,
  },
});
```

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan checklist ini untuk mengukur kesiapan Anda dalam mengimplementasikan animasi dan interaksi gestur berkinerja tinggi sebelum masuk ke modul arsitektur tingkat lanjut:

| Topik Evaluasi | Kriteria Keberhasilan Pemahaman | Status ([X] / [ ]) |
| :--- | :--- | :--- |
| **Threading Model** | Mampu menjelaskan perbedaan lifecycle JS Thread, UI Thread, dan Render Thread pada arsitektur React Native baru (Fabric/JSI). | [ ] |
| **Worklet Architecture** | Memahami proses serialisasi AST & closure capture Babel plugin serta batasan eksekusi variabel di dalam `'worklet'`. | [ ] |
| **Shared Values** | Menggunakan `useSharedValue` dan `useDerivedValue` secara eksklusif untuk nilai teranimasi tanpa memicu React re-rendering. | [ ] |
| **RNGH v2 API** | Menguasai penggunaan `Gesture.Pan()`, `Gesture.Tap()`, `Gesture.Pinch()`, serta komposisi gesture (`Simultaneous`, `Race`, `Exclusive`). | [ ] |
| **Spring Physics** | Memahami hubungan fisis antara `stiffness`, `damping`, dan `mass`, serta mampu memanfaatkan inersia gestur (`velocityX/Y`). | [ ] |
| **Memory & Cleanup** | Menguasai penggunaan `cancelAnimation` untuk mencegah dangling native callbacks dan memori bocor pada unmounted components. | [ ] |
| **Layout Optimization** | Menghindari animasi properti box-model Yoga (`width`, `height`, `top`, `margin`) dan fokus pada transformasi GPU (`transform`, `opacity`). | [ ] |
| **Scroll Sync** | Mampu mengintegrasikan `useAnimatedScrollHandler` dengan `Animated.FlatList` untuk header sticky/parallax tanpa stuttering. | [ ] |
| **Shared Element** | Memahami daur hidup `sharedTransitionTag` dan mitigasi glitch visual akibat perbedaan aspect ratio atau parent overflow clipping. | [ ] |
| **Profiling Animasi** | Mampu menggunakan React Native Performance Monitor, Flipper, atau Android Systrace / iOS Instruments untuk memverifikasi kestabilan 60/120 FPS. | [ ] |
