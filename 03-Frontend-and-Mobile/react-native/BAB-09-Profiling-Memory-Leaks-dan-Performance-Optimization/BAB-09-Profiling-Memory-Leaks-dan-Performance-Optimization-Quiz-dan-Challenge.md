# BAB-09-Profiling-Memory-Leaks-dan-Performance-Optimization: Quiz, Challenge, & Knowledge Check

Uji pemahaman mendalam Anda mengenai profiling runtime, identifikasi memory leak (JS heap dan native retained memory), teknik optimasi frame rate (JS vs UI thread 60/120 FPS), layout thrashing, image memory footprint, serta arsitektur New Architecture (Hermes GC, JSI, Fabric).

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1: Peran Hermes Profiler dan Trace Recording
Mengapa sampling profiler bawaan Hermes engine lebih direkomendasikan untuk menelusuri eksekusi JavaScript lambat di perangkat Android/iOS pada production-like builds dibandingkan remote debugging dengan Chrome DevTools klasik?

- A. Remote debugging klasik menjalankan JS di thread terpisah di dalam browser Chrome (V8 engine) melalui WebSocket bridge, sehingga karakteristik timing eksekusi, micro-task scheduling, dan JIT/AOT bytecode Hermes tidak merefleksikan performa nyata di device.
- B. Hermes sampling profiler menghentikan UI thread setiap 1 milidetik untuk mengambil snapshot memori lengkap secara sinkron.
- C. Remote debugging Chrome tidak mendukung console.log dan source maps modern di React Native 0.70+.
- D. Hermes sampling profiler secara otomatis memindahkan operasi rendering berat dari JS thread langsung ke GPU render pass.

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban: A**

**Pembahasan:**
Remote debugging klasik (Chrome DevTools via legacy WebSocket bridge) mengeksekusi bundle JavaScript di dalam instance browser Chrome menggunakan V8 engine pada workstation host, bukan di device target. Hal ini mendistorsi pengukuran performa secara signifikan karena perbedaan engine (V8 vs Hermes), kecepatan CPU host vs mobile device, latency serialisasi JSON lewat WebSocket bridge, dan tidak aktifnya hermes bytecode execution. Hermes sampling profiler mencatat call stack secara langsung pada runtime Hermes di target device dengan overhead minimal (~few percent CPU), menghasilkan trace `.cpuprofile` yang akurat sesuai kondisi nyata.
</details>

---

### Soal 2: Karakteristik `InteractionManager.runAfterInteractions`
Kapan skenario yang paling tepat untuk memanfaatkan API `InteractionManager.runAfterInteractions()` pada transisi navigasi React Native?

- A. Ketika ingin menghentikan render React navigation bar secara permanen.
- B. Untuk menunda eksekusi task komputasi JS berat atau fetch data inisial layar tujuan hingga animasi transisi navigasi/gesture selesai agar tidak terjadi dropped frames (jank).
- C. Untuk mengubah listener WebSocket menjadi asynchronous worker thread native secara otomatis.
- D. Untuk memaksa layout engine Yoga menghitung ulang flexbox sebelum screen di-mount.

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban: B**

**Pembahasan:**
Ketika screen baru dibuka, React Navigation umumnya menjalankan animasi transisi layar (seperti slide-in atau card stack push) pada UI thread atau didorong oleh gesture. Jika JS thread secara bersamaan sibuk me-mount ratusan komponen, mem-parsing response JSON besar, atau mengkalkulasi state berat, JS thread akan terhambat dan tidak sempat merespons event gesture atau frame updates, memicu dropped frame. `InteractionManager.runAfterInteractions` menunda task berat tersebut ke dalam queue yang baru dieksekusi setelah semua interaksi aktif/animasi tercatat selesai.
</details>

---

### Soal 3: Memory Leak pada `useEffect` Event Listeners
Perhatikan snippet hook berikut:

```typescript
useEffect(() => {
  const subscription = DeviceEventEmitter.addListener('LocationUpdate', (coords) => {
    setLocation(coords);
  });
}, []);
```

Apa akar penyebab terjadinya memory leak pada snippet di atas jika komponen di-unmount dan di-mount berulang kali?

- A. `DeviceEventEmitter` hanya mendukung format event berbasis JSON schema.
- B. Fungsi `setLocation` tidak dibungkus oleh `useCallback`.
- C. Hook `useEffect` tidak mengembalikan fungsi cleanup (`subscription.remove()`), sehingga reference closure handler beserta instance komponen tetap tersimpan dalam dispatch registry `DeviceEventEmitter` di native memory/global scope.
- D. Dependensi array `[]` menyebabkan React me-reset subscriber setiap render cycle.

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban: C**

**Pembahasan:**
`DeviceEventEmitter` menyimpan callback listener di dalam array/list global. Tanpa cleanup function di return `useEffect` (yaitu `return () => subscription.remove()`), setiap kali komponen di-mount, listener baru ditambahkan, sementara listener lama tidak pernah dihapus. Hal ini menahan referensi terhadap scope closure komponen (termasuk setter state dan variabel terkait), mencegah Hermes Garbage Collector membersihkan instance komponen yang telah unmount, memicu akumulasi memory leak.
</details>

---

### Soal 4: FlatList Optimization: `windowSize` dan `getItemLayout`
Bagaimana konfigurasi properti `getItemLayout` membantu FlatList mencegah jank dan menghemat CPU saat scrolling cepat?

- A. Mengompres ukuran file gambar secara dinamis sebelum masuk ke memory cache.
- B. Memotong data array ke dalam chunk berukuran maksimal 10 item per render.
- C. Memungkinkan FlatList menghitung posisi koordinat piksel (offset dan tinggi/lebar) setiap baris secara matematis deterministik tanpa harus mengukur layout elemen secara dinamis (melewati fase asynchronous layout measurement di Yoga).
- D. Mengubah FlatList menjadi native scroll view murni tanpa virtualisasi React DOM tree.

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban: C**

**Pembahasan:**
Secara default, FlatList harus me-render item off-screen untuk mengukur tinggi dan lebarnya via layout pass agar offset scroll dapat dihitung. Dengan menyediakan `getItemLayout={(data, index) => ({ length: ITEM_HEIGHT, offset: ITEM_HEIGHT * index, index })}`, FlatList dapat langsung melompati tahapan pengukuran layout dinamis, memungkinkan instantaneous jump scroll (`scrollToIndex`) dan virtualisasi windowing yang sangat hemat CPU cycle.
</details>

---

### Soal 5: Native Module Memory Leak via Retained Callbacks
Dalam arsitektur React Native Bridge / TurboModule lama, mengapa menyimpan instance `Callback` atau `Promise` di field statis native module (Java/Kotlin atau Obj-C/Swift) tanpa resolusi berpotensi menyebabkan memory leak yang parah?

- A. Callback native memblokir garbage collection pada thread V8/Hermes karena native object mempertahankan JSI host reference atau bridge message callback pointer secara global.
- B. Callback native secara otomatis mengalokasikan 64 MB buffer di stack heap Android NDK.
- C. Promise native akan mematikan koneksi IPC bridge setelah timeout 30 detik.
- D. Hermes GC tidak memiliki akses ke thread CPU utama native.

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban: A**

**Pembahasan:**
Ketika bridge callback dikirim dari JavaScript ke Native, native runtime menerima pointer/reference wrapper yang terikat ke callback JavaScript di JS heap. Jika native module menyimpan referensi callback/promise tersebut secara persisten (misalnya di static field, singleton, atau asynchronous long-running task) tanpa pernah memanggil `invoke` atau melepas referensinya saat task dibatalkan/activity hancur, closure JavaScript di balik callback tersebut tidak dapat di-garbage collect oleh Hermes/V8.
</details>

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 6: Analisis Alokasi Memori dengan Hermes Heap Snapshot
Dalam Chrome DevTools / Flipper Memory Inspector saat menginspeksi file `.heapsnapshot` Hermes, apa perbedaan mendasar antara kolom **Shallow Size** dan **Retained Size**?

- A. Shallow Size adalah ukuran memori yang dialokasikan di swap disk, sedangkan Retained Size adalah alokasi di RAM fisik.
- B. Shallow Size adalah ukuran memori yang dimiliki langsung oleh object itu sendiri (misalnya primitive fields dan internal structure), sedangkan Retained Size adalah total ukuran memori yang akan dibebaskan secara otomatis jika object tersebut di-garbage collect (termasuk referensi object turunan yang hanya bisa dijangkau lewat object ini).
- C. Retained Size selalu bernilai lebih kecil dari Shallow Size pada object array bersarang.
- D. Shallow Size mengukur memori native C++, sedangkan Retained Size mengukur alokasi JavaScript string buffer murni.

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban: B**

**Pembahasan:**
- **Shallow Size:** Ukuran memori internal yang dialokasikan secara eksklusif untuk struktur objek itu sendiri (tidak termasuk objek lain yang dirujuk oleh properti/field-nya).
- **Retained Size:** Ukuran memori total yang akan terlepas (freed) jika objek tersebut dimusnahkan dan GC mendeteksi bahwa objek-objek child dalam dominator tree-nya tidak lagi memiliki referensi hidup dari GC Roots lain. Saat mendiagnosis memory leak, target utama eliminasi adalah objek dengan Retained Size raksasa.
</details>

---

### Soal 7: Mengatasi Image Memory Footprint di Android (`react-native-fast-image` / Fresco)
Aplikasi menampilkan feed 200 foto beresolusi tinggi (4000x3000 piksel) yang dirender di feed berukuran container 300x225 piksel. Walaupun FlatList telah divirtualisasi, aplikasi sering mengalami Crash `OutOfMemoryError` (OOM) di perangkat Android low-end (RAM 2 GB - 3 GB). Apa akar masalah teknis di layer native engine (Fresco / Bitmap pipeline) dan mitigasi yang tepat?

- A. Hermes tidak mendukung decoding format WebP di level engine bytecode.
- B. Bitmaps di Android di-decode pada resolusi aslinya (4000x3000 x 4 byte per pixel ARGB_8888 = ~48 MB RAM per gambar yang aktif di memori bitmap native), melampaui alokasi dalvik/art heap limit. Solusinya adalah mengaktifkan downsampling/resizing di Fresco atau menentukan `resizeMethod="resize"` / `resizeMode` pada native image pipeline agar bitmap di-decode sesuai resolusi tampilan viewport saja.
- C. FlatList tidak menghapus event listener layout saat scroll. Solusinya adalah mengubah FlatList menjadi ScrollView dengan pagingEnabled.
- D. Komponen View React Native tidak mendukung hardware acceleration layer untuk image containers.

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban: B**

**Pembahasan:**
Memori gambar di Android dihitung berdasarkan resolusi piksel bitmap hasil decode (lebar × tinggi × byte per piksel), bukan ukuran kompresi file JPG/PNG di storage atau jaringan. Satu gambar 12 MP (4000×3000) yang didecode dengan konfigurasi default `ARGB_8888` (4 byte/pixel) membutuhkan 48 MB RAM uncompressed di native bitmap heap. Jika 10 gambar di-decode secara bersamaan di memory cache Fresco tanpa downsampling (`downsampleOptions` / `resizeMethod="resize"`), aplikasi mengonsumsi ~480 MB RAM seketika, memicu low memory killer (LMK) atau OOM.
</details>

---

### Soal 8: Reanimated vs JS Driven Animation pada JS Thread Saturation
Mengapa animasi berbasis `react-native-reanimated` (v2/v3) tetap berjalan mulus pada 60/120 FPS meskipun JS Thread utama sedang mengalami blocking selama 500ms akibat eksekusi kalkulasi enkripsi data berat, sedangkan animasi `Animated.timing({ useNativeDriver: false })` terhenti seketika (freeze)?

- A. Reanimated otomatis memindahkan kode kalkulasi enkripsi ke WebWorker background.
- B. Reanimated menggunakan runtime JavaScript sekunder (Hermes secondary runtime) yang berjalan langsung pada UI Thread (Worklet context) dan mengoperasikan node animasi langsung ke platform native views tanpa bergantung pada event loop utama di React JS Thread.
- C. Reanimated secara langsung menginstruksikan GPU untuk mengabaikan command buffer dari React reconciler.
- D. Reanimated mengonversi seluruh tree JSX menjadi C++ TurboModules sebelum aplikasi di-compile.

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban: B**

**Pembahasan:**
Ketika properti `useNativeDriver: false` digunakan pada library `Animated` lama, setiap frame interpolasi dihitung di JS Thread utama dalam requestAnimationFrame loop, lalu ditransformasikan dan dikirim melalui bridge/JSI. Jika JS Thread terblokir oleh komputasi sinkron, loop berhenti dan frame drop terjadi. Sebaliknya, `react-native-reanimated` memanfaatkan arsitektur Worklet: fungsi JavaScript kecil yang dikompilasi oleh Babel plugin dan dieksekusi di runtime Hermes sekunder yang hidup langsung di Native UI Thread, independen dari antrean event loop utama React JS Thread.
</details>

---

### Soal 9: Memory Churn dan GC Pressure akibat Anonymous Objects & Inline Callbacks
Mengapa pembuatan object literal baru dan closure inline function di dalam render loop FlatList (`renderItem={({ item }) => <Card config={{ id: item.id, active: true }} onPress={() => handle(item.id)} />}`) dapat memicu stutter/micro-jank periodik, meskipun tidak ada memory leak permanen?

- A. Objek baru tersebut memicu crash kernel OS akibat stack overflow di tingkat pthread.
- B. Pembuatan alokasi ribuan ephemeral (short-lived) objects secara masif pada setiap frame scroll menyebabkan memori generasi muda (Hermes young generation) cepat penuh, memaksa garbage collector berjalan terlalu sering (frequent GC sweeps/pauses) yang menghentikan eksekusi JS thread sementara (Stop-The-World micro-pauses).
- C. Hermes compiler tidak mampu mengompilasi inline arrow function ke dalam bytecode.
- D. Inline closures secara otomatis menduplikasi DOM node di layer Fabric C++ shadow tree.

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban: B**

**Pembahasan:**
Meskipun short-lived objects akan otomatis dibersihkan oleh Garbage Collector tanpa menjadi memory leak permanen, laju alokasi memori yang sangat agresif (*memory churn*) menekan GC. Pada generational garbage collector seperti Hermes Hades GC, ketika alokasi memori melewati ambang batas tertentu, GC cycle harus dijalankan untuk sweep memory. Meskipun Hades memiliki background GC thread, sinkronisasi alokasi dan penandaan object references tetap dapat memicu micro-stalls pada JS thread yang terlihat sebagai micro-jank atau frame drops selama interaksi scroll cepat.
</details>

---

### Soal 10: TurboModule C++ JSI Retained References (`jsi::Value` & `jsi::Object`)
Saat menulis custom native module menggunakan JSI (JavaScript Interface) di C++, kesalahan apa yang paling sering menyebabkan crash memori `SIGSEGV` atau memory leak saat menyimpan callback JavaScript ke layer C++?

- A. Menyimpan `facebook::jsi::Function` langsung sebagai C++ pointer tanpa membungkusnya ke dalam `facebook::jsi::Value`.
- B. Mengakses `jsi::Runtime` dari sembarang background thread tanpa melakukan penjaminan thread safety atau mencoba mempertahankan referensi `jsi::Value` antar session tanpa menggunakan `jsi::WeakObject` / lifecycle management yang sinkron dengan Hermes GC cycle.
- C. Menggunakan tipe data `std::string` alih-alih `char*` saat me-return string ke JavaScript.
- D. Mengaktifkan flag RTTI pada compiler clang Android NDK.

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban: B**

**Pembahasan:**
Instance `facebook::jsi::Runtime` di React Native **bukan** thread-safe. Menjalankan operasi pada runtime yang sama dari thread native lain secara bersamaan akan mengacaukan internal heap Hermes dan menyebabkan memory corruption / crash `SIGSEGV`. Selain itu, jika C++ code mempertahankan strong reference ke `jsi::Object` atau `jsi::Function` setelah JavaScript context-nya hancur (atau melintasi reload bundle), pointer tersebut menjadi *dangling reference* yang memicu crash fatal saat diakses.
</details>

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 1: The Infinite Scrolling Feed Crash (E-Commerce Mega Sale)

#### Konteks Masalah:
Sebuah aplikasi e-commerce besar meluncurkan fitur live feed promo flash-sale. Pengguna biasanya melakukan scrolling feed produk hingga ribuan item secara maraton selama berjam-jam. Tim monitoring Sentry melaporkan lonjakan drastis pada metrik **OOM (Out Of Memory) Crashes** khusus di perangkat Android dengan RAM < 4 GB setelah pengguna menelusuri sekitar 300–500 item produk.

#### Kode Komponen Bermasalah:
```tsx
import React, { useState, useEffect } from 'react';
import { View, Text, FlatList, Image, TouchableOpacity } from 'react-native';

export const FlashSaleFeed = () => {
  const [products, setProducts] = useState<any[]>([]);
  const [page, setPage] = useState(1);

  const fetchMoreData = async () => {
    const res = await fetch(`https://api.mall.com/flash-sale?page=${page}&limit=50`);
    const newItems = await res.json();
    setProducts((prev) => [...prev, ...newItems]);
    setPage((p) => p + 1);
  };

  useEffect(() => {
    fetchMoreData();
  }, []);

  return (
    <FlatList
      data={products}
      keyExtractor={(item) => item.uuid}
      onEndReached={fetchMoreData}
      onEndReachedThreshold={0.5}
      windowSize={31}
      removeClippedSubviews={false}
      renderItem={({ item }) => (
        <View style={{ height: 280, padding: 12, backgroundColor: '#fff' }}>
          <Image
            source={{ uri: item.imageUrl }}
            style={{ width: '100%', height: 200 }}
            resizeMode="cover"
          />
          <Text style={{ fontSize: 16, fontWeight: 'bold' }}>{item.title}</Text>
          <Text style={{ color: 'red' }}>Rp {item.price.toLocaleString('id-ID')}</Text>
        </View>
      )}
    />
  );
};
```

#### Analisis Akar Masalah:
1. **`windowSize={31}` Terlalu Besar:** Nilai default `windowSize` adalah 21 (10 viewport ke atas, 1 di layar, 10 ke bawah). Dengan nilai 31, FlatList me-render dan menahan 31 kali tinggi layar sekaligus di memory shadow DOM.
2. **`removeClippedSubviews={false}`:** Subview native yang berada di luar viewport tidak pernah dilepas dari native view hierarchy Android.
3. **Array Penampung Memory (`products` State Unbounded Growth):** Menyimpan ribuan object JSON detail produk di single state array tanpa windowing atau pagination cleanup.
4. **Bitmap Heap Exhaustion:** Gambar beresolusi tinggi di-decode dan ditahan di memori native tanpa downsizing cache limit.

#### Solusi Refactoring & Remediasi Teknis:
```tsx
import React, { useState, useCallback, useMemo } from 'react';
import { View, Text, FlatList, StyleSheet } from 'react-native';
import FastImage from 'react-native-fast-image';

const ITEM_HEIGHT = 280;

interface ProductItem {
  uuid: string;
  imageUrl: string;
  title: string;
  price: number;
}

const ProductCard = React.memo(({ item }: { item: ProductItem }) => {
  return (
    <View style={styles.cardContainer}>
      <FastImage
        source={{
          uri: item.imageUrl,
          priority: FastImage.priority.normal,
          cache: FastImage.cacheControl.immutable,
        }}
        style={styles.image}
        resizeMode={FastImage.resizeMode.cover}
      />
      <Text numberOfLines={1} style={styles.title}>{item.title}</Text>
      <Text style={styles.price}>Rp {item.price.toLocaleString('id-ID')}</Text>
    </View>
  );
});

export const OptimizedFlashSaleFeed = () => {
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(false);

  const fetchMoreData = useCallback(async () => {
    if (isLoading) return;
    setIsLoading(true);
    try {
      const res = await fetch(`https://api.mall.com/flash-sale?page=${page}&limit=20`);
      const newItems: ProductItem[] = await res.json();
      setProducts((prev) => [...prev, ...newItems]);
      setPage((p) => p + 1);
    } finally {
      setIsLoading(false);
    }
  }, [page, isLoading]);

  const getItemLayout = useCallback(
    (_: any, index: number) => ({
      length: ITEM_HEIGHT,
      offset: ITEM_HEIGHT * index,
      index,
    }),
    []
  );

  const renderItem = useCallback(({ item }: { item: ProductItem }) => {
    return <ProductCard item={item} />;
  }, []);

  return (
    <FlatList
      data={products}
      keyExtractor={(item) => item.uuid}
      onEndReached={fetchMoreData}
      onEndReachedThreshold={0.3}
      maxToRenderPerBatch={5}
      updateCellsBatchingPeriod={50}
      initialNumToRender={6}
      windowSize={5} // Mengurangi footprint: hanya 2 viewport atas, 1 viewport aktif, 2 viewport bawah
      removeClippedSubviews={true} // Membebaskan native views saat keluar dari window
      getItemLayout={getItemLayout}
      renderItem={renderItem}
    />
  );
};

const styles = StyleSheet.create({
  cardContainer: {
    height: ITEM_HEIGHT,
    padding: 12,
    backgroundColor: '#fff',
  },
  image: {
    width: '100%',
    height: 200,
    backgroundColor: '#f2f2f2',
  },
  title: {
    fontSize: 16,
    fontWeight: 'bold',
    marginTop: 4,
  },
  price: {
    color: '#e53935',
    fontWeight: '600',
    marginTop: 2,
  },
});
```

---

### Skenario 2: The Navigation Stack Zombie Component Leak

#### Konteks Masalah:
Pada aplikasi telemedicine dengan stack navigasi `@react-navigation/native-stack`, dokter membuka layar "Patient Detail" untuk melihat rekam medis, kembali ke daftar pasien, lalu membuka rekam medis pasien lain. Setelah berpindah 20 kali, aplikasi menjadi lambat (frame rate drop hingga 15 FPS) dan Chrome DevTools Heap Snapshot menunjukkan ada **20 instance `PatientDetailScreen`** yang masih bertahan di JS Heap dengan retained size mencapai 180 MB.

#### Kode Komponen Bermasalah:
```tsx
import React, { useState, useEffect } from 'react';
import { View, Text } from 'react-native';
import { globalEventEmitter } from '../services/eventBus';
import { telemetryClient } from '../services/telemetry';

export const PatientDetailScreen = ({ route }: any) => {
  const { patientId } = route.params;
  const [vitalSigns, setVitalSigns] = useState<any>(null);

  // Kebocoran 1: Event listener tidak di-cleanup
  useEffect(() => {
    globalEventEmitter.on('VITAL_SIGN_SYNC', (data) => {
      if (data.patientId === patientId) {
        setVitalSigns(data.vitals);
      }
    });
  }, [patientId]);

  // Kebocoran 2: Singleton service menyimpan closure callback ke state
  useEffect(() => {
    telemetryClient.registerHeartbeatWatcher(patientId, () => {
      console.log(`Pinging status for patient ${patientId}`);
    });
  }, [patientId]);

  return (
    <View>
      <Text>Patient: {patientId}</Text>
      <Text>Vitals: {JSON.stringify(vitalSigns)}</Text>
    </View>
  );
};
```

#### Analisis Akar Masalah:
1. `globalEventEmitter.on(...)` mendaftarkan callback tanpa pernah memanggil `globalEventEmitter.off(...)` saat layar di-unmount.
2. Callback anonymous tersebut mempertahankan closure scope yang memuat fungsi `setVitalSigns`, objek `route.params`, dan seluruh context komponen `PatientDetailScreen`.
3. `telemetryClient.registerHeartbeatWatcher` menyimpan reference fungsi ke dalam static Map di memory service tanpa mekanisme unregister.
4. Meskipun user telah menekan tombol "Back" dan screen di-pop dari navigation stack, GC Root dari singleton `globalEventEmitter` dan `telemetryClient` tetap menahan reference hidup ke setiap instance layar yang pernah dibuka.

#### Solusi Refactoring & Remediasi Teknis:
```tsx
import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { globalEventEmitter } from '../services/eventBus';
import { telemetryClient } from '../services/telemetry';

interface VitalsData {
  patientId: string;
  vitals: {
    heartRate: number;
    bloodPressure: string;
  };
}

export const SafePatientDetailScreen = ({ route }: any) => {
  const { patientId } = route.params;
  const [vitalSigns, setVitalSigns] = useState<VitalsData['vitals'] | null>(null);

  useEffect(() => {
    const handleVitalUpdate = (data: VitalsData) => {
      if (data.patientId === patientId) {
        setVitalSigns(data.vitals);
      }
    };

    // Mendaftarkan event listener
    globalEventEmitter.on('VITAL_SIGN_SYNC', handleVitalUpdate);

    // Mendaftarkan heartbeat watcher dengan return function unsubscribe
    const heartbeatUnsubscribe = telemetryClient.registerHeartbeatWatcher(
      patientId,
      () => {
        // Callback terisolasi tanpa menahan closure state besar
      }
    );

    // Cleanup wajib saat unmount atau patientId berubah
    return () => {
      globalEventEmitter.off('VITAL_SIGN_SYNC', handleVitalUpdate);
      if (typeof heartbeatUnsubscribe === 'function') {
        heartbeatUnsubscribe();
      } else {
        telemetryClient.unregisterHeartbeatWatcher(patientId);
      }
    };
  }, [patientId]);

  return (
    <View style={styles.container}>
      <Text style={styles.header}>Patient ID: {patientId}</Text>
      {vitalSigns ? (
        <View>
          <Text>Heart Rate: {vitalSigns.heartRate} bpm</Text>
          <Text>Blood Pressure: {vitalSigns.bloodPressure}</Text>
        </View>
      ) : (
        <Text>Menunggu sinkronisasi data vitals...</Text>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#fff' },
  header: { fontSize: 18, fontWeight: '700', marginBottom: 12 },
});
```

---

### Skenario 3: High-Frequency WebSocket Rerender Freeze (Crypto Trading Dashboard)

#### Konteks Masalah:
Sebuah aplikasi crypto trading menampilkan ticker grafik harga dan order book order book real-time. Backend mengirimkan delta update harga via WebSocket dengan frekuensi rata-rata **40–60 pesan per detik (60 Hz)**. Ketika pengguna membuka layar perdagangan, UI aplikasi membeku total (0–5 FPS), tombol buy/sell tidak merespons sentuhan (touch lag > 2 detik), dan CPU usage di profiler mencapai 100% pada JS Thread.

#### Kode Komponen Bermasalah:
```tsx
import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';

export const CryptoTickerDashboard = () => {
  const [currentPrice, setCurrentPrice] = useState<number>(0);
  const [orderBook, setOrderBook] = useState<any[]>([]);
  const [tradesHistory, setTradesHistory] = useState<any[]>([]);

  useEffect(() => {
    const ws = new WebSocket('wss://stream.cryptoexchange.com/tickers');
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      // Dipanggil 50x per detik:
      setCurrentPrice(data.price);
      setOrderBook(data.bids);
      setTradesHistory((prev) => [data.latestTrade, ...prev.slice(0, 50)]);
    };
    return () => ws.close();
  }, []);

  return (
    <View style={{ flex: 1, padding: 16 }}>
      <Text style={{ fontSize: 32 }}>${currentPrice.toFixed(2)}</Text>
      {/* Heavy Sub-tree: me-render ulang ratusan baris 50 kali setiap detik */}
      <OrderBookView data={orderBook} />
      <TradeHistoryView data={tradesHistory} />
      <TouchableOpacity onPress={() => alert('Order Placed!')}>
        <Text>Buy Now</Text>
      </TouchableOpacity>
    </View>
  );
};
```

#### Analisis Akar Masalah:
1. **Re-render Thrashing:** Memanggil `useState` setter 50x per detik memicu rekonsiliasi React DOM tree sebanyak 50 kali per detik.
2. **Bridge/JSI Flooding:** Serialisasi data array order book besar dari native WebSocket client ke JS thread menghabiskan kuota frame budget (16.6ms per frame).
3. **Touch Event Starvation:** Event gesture dan tap yang masuk ke antrean JS thread tertunda di belakang tumpukan task update state React yang tak henti-hentinya.

#### Solusi Arsitektur & Remediasi Teknis:
1. **Throttling / Batching Updates:** Batasi pembaruan state visual ke frekuensi manusiawi (misalnya 4–10 Hz atau setiap 150ms).
2. **Reanimated Shared Values untuk Realtime Ticker:** Alirkan angka harga langsung ke UI thread menggunakan Text animation/worklet tanpa re-render pohon React.
3. **Pemisahan State Sub-tree:** Pisahkan komponen Ticker, OrderBook, dan Tombol Interaksi agar tidak saling memicu cascading re-render.

```tsx
import React, { useEffect, useRef, useState, memo } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';

interface WebSocketPayload {
  price: number;
  bids: any[];
  latestTrade: any;
}

export const OptimizedCryptoDashboard = () => {
  const [displayPrice, setDisplayPrice] = useState<number>(0);
  const [orderBook, setOrderBook] = useState<any[]>([]);
  
  // Penampung buffer update
  const latestDataRef = useRef<WebSocketPayload | null>(null);

  useEffect(() => {
    const ws = new WebSocket('wss://stream.cryptoexchange.com/tickers');

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // Simpan data di mutable ref tanpa memicu re-render sinkron
        latestDataRef.current = data;
      } catch (err) {
        console.error('WS Parse Error', err);
      }
    };

    // Batching interval: hanya render UI setiap 200ms (5 FPS update rate untuk data feed)
    // Cukup halus untuk mata manusia tanpa membuat JS Thread choke
    const intervalTimer = setInterval(() => {
      if (latestDataRef.current) {
        const { price, bids } = latestDataRef.current;
        setDisplayPrice(price);
        setOrderBook(bids);
        latestDataRef.current = null;
      }
    }, 200);

    return () => {
      clearInterval(intervalTimer);
      ws.close();
    };
  }, []);

  return (
    <View style={styles.container}>
      <PriceDisplay price={displayPrice} />
      <MemoizedOrderBook bids={orderBook} />
      <TouchableOpacity
        style={styles.actionBtn}
        onPress={() => console.log('Instant Touch Response!')}
      >
        <Text style={styles.btnText}>Quick Buy</Text>
      </TouchableOpacity>
    </View>
  );
};

const PriceDisplay = memo(({ price }: { price: number }) => (
  <Text style={styles.priceText}>${price.toFixed(2)}</Text>
));

const MemoizedOrderBook = memo(({ bids }: { bids: any[] }) => (
  <View style={styles.orderBookContainer}>
    {bids.slice(0, 5).map((bid, i) => (
      <Text key={i} style={styles.bidRow}>
        Bid: {bid.rate} | Qty: {bid.qty}
      </Text>
    ))}
  </View>
));

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#121212' },
  priceText: { fontSize: 36, color: '#00e676', fontWeight: 'bold' },
  orderBookContainer: { marginVertical: 16, backgroundColor: '#1e1e1e', padding: 8 },
  bidRow: { color: '#e0e0e0', marginVertical: 2 },
  actionBtn: { backgroundColor: '#2979ff', padding: 14, borderRadius: 8, alignItems: 'center' },
  btnText: { color: '#fff', fontWeight: 'bold' },
});
```

---

## Bagian 4: Practical Chapter Challenge (Hands-on Mini Project)

### Deskripsi Challenge:
Buatlah sebuah test harness dan profiling interceptor bernama **`MemoryLeakSentinel`** di React Native untuk mendeteksi komponen yang gagal di-garbage collect saat unmount, serta script benchmark untuk mengukur memory footprint dan frame drops pada daftar data dinamis.

### Persyaratan Teknis:
1. **WeakRef Registry:** Menggunakan JavaScript standard API `WeakRef` dan `FinalizationRegistry` untuk melacak apakah instance komponen React yang telah di-unmount berhasil dibersihkan oleh Garbage Collector setelah waktu tenggang tertentu (misalnya 10 detik).
2. **Stall Detector (JS Frame Tracker):** Membuat hook monitoring performa `useFrameRateMonitor` yang mendeteksi frame drop / long task di JS thread dengan mengukur selisih waktu antar `requestAnimationFrame`.
3. **Simulasi Memory Leak & Self-Healing:** Membuat satu komponen yang sengaja memiliki leak (uncleaned timer & listener) dan satu komponen yang telah diperbaiki, lalu bandingkan hasilnya di console log.

### Implementasi Lengkap Code Harness:

```typescript
import React, { useEffect, useRef, useState } from 'react';
import { View, Text, Button, StyleSheet, ScrollView } from 'react-native';

/**
 * 1. FinalizationRegistry & WeakRef Sentinel
 * Mendeteksi komponen yang tertinggal di memori setelah di-unmount.
 */
class MemorySentinelRegistry {
  private registry: FinalizationRegistry<string>;
  private trackedInstances = new Map<string, WeakRef<object>>();

  constructor() {
    this.registry = new FinalizationRegistry((token: string) => {
      console.log(`[SENTINEL - SUCCESS] Garbage Collector membebaskan instance: ${token}`);
      this.trackedInstances.delete(token);
    });
  }

  public register(target: object, identifier: string) {
    console.log(`[SENTINEL - TRACK] Mendaftarkan monitor untuk: ${identifier}`);
    this.trackedInstances.set(identifier, new WeakRef(target));
    this.registry.register(target, identifier);
  }

  public auditLeak(identifier: string) {
    const ref = this.trackedInstances.get(identifier);
    if (ref && ref.deref()) {
      console.warn(
        `[SENTINEL - LEAK DETECTED] Instance ${identifier} masih HIDUP di memori setelah unmount! Periksa event listener/closure leak.`
      );
    } else {
      console.log(`[SENTINEL - CLEAN] Instance ${identifier} tidak lagi dapat diakses (siap/sudah di-GC).`);
    }
  }
}

export const Sentinel = new MemorySentinelRegistry();

/**
 * 2. Hook JS Thread Frame Drop / Stall Monitor
 */
export const useFrameRateMonitor = (thresholdMs: number = 32) => {
  const [jankCount, setJankCount] = useState(0);
  const isRunning = useRef(true);

  useEffect(() => {
    let lastFrameTime = performance.now();
    let frameId: number;

    const checkFrame = (currentTime: number) => {
      const delta = currentTime - lastFrameTime;
      if (delta > thresholdMs) {
        // Jika selisih antar frame > 32ms (melewatkan minimal 1 frame di 60 FPS)
        console.warn(`[PERF STALL] JS Thread Freeze terdeteksi: ${delta.toFixed(2)}ms`);
        setJankCount((c) => c + 1);
      }
      lastFrameTime = currentTime;
      if (isRunning.current) {
        frameId = requestAnimationFrame(checkFrame);
      }
    };

    frameId = requestAnimationFrame(checkFrame);

    return () => {
      isRunning.current = false;
      cancelAnimationFrame(frameId);
    };
  }, [thresholdMs]);

  return jankCount;
};

/**
 * 3. Komponen Uji: Leaky Component (Sengaja Bocor)
 */
const LeakyComponent = () => {
  const [counter, setCounter] = useState(0);

  useEffect(() => {
    // Objek marker untuk dideteksi oleh Sentinel
    const trackerToken = `LeakyComponent_${Date.now()}`;
    const memoryMarker = { name: trackerToken };
    Sentinel.register(memoryMarker, trackerToken);

    // KEBOCORAN: Timer tidak di-clear dan closure menahan referensi
    const interval = setInterval(() => {
      // Memory marker ditahan di dalam closure interval
      setCounter((prev) => prev + (memoryMarker ? 1 : 0));
    }, 1000);

    return () => {
      // BENCANA: Tidak ada clearInterval(interval)
      setTimeout(() => {
        Sentinel.auditLeak(trackerToken);
      }, 5000);
    };
  }, []);

  return (
    <View style={styles.leakyBox}>
      <Text style={styles.boxText}>Leaky Component Aktif (Counter: {counter})</Text>
    </View>
  );
};

/**
 * 4. Komponen Uji: Cleaned Component (Aman dari Leak)
 */
const CleanComponent = () => {
  const [counter, setCounter] = useState(0);

  useEffect(() => {
    const trackerToken = `CleanComponent_${Date.now()}`;
    const memoryMarker = { name: trackerToken };
    Sentinel.register(memoryMarker, trackerToken);

    const interval = setInterval(() => {
      setCounter((prev) => prev + 1);
    }, 1000);

    return () => {
      // PEMBERSIHAN SEMPURNA
      clearInterval(interval);
      setTimeout(() => {
        Sentinel.auditLeak(trackerToken);
      }, 5000);
    };
  }, []);

  return (
    <View style={styles.cleanBox}>
      <Text style={styles.boxText}>Clean Component Aktif (Counter: {counter})</Text>
    </View>
  );
};

/**
 * 5. Dashboard Test Harness
 */
export const MemoryChallengeHarness = () => {
  const [showLeaky, setShowLeaky] = useState(false);
  const [showClean, setShowClean] = useState(false);
  const jankCount = useFrameRateMonitor(32);

  const simulateHeavyComputation = () => {
    // Memblokir JS thread selama 300ms untuk menguji Frame Monitor
    const start = performance.now();
    while (performance.now() - start < 300) {
      Math.sqrt(Math.random() * 100000);
    }
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Memory & Performance Sentinel Harness</Text>
      <Text style={styles.metric}>Deteksi Frame Stall (>32ms): {jankCount} kejadian</Text>

      <View style={styles.buttonGroup}>
        <Button
          title={showLeaky ? 'Unmount Leaky Component' : 'Mount Leaky Component'}
          color="#d32f2f"
          onPress={() => setShowLeaky((v) => !v)}
        />
        <View style={{ height: 10 }} />
        <Button
          title={showClean ? 'Unmount Clean Component' : 'Mount Clean Component'}
          color="#388e3c"
          onPress={() => setShowClean((v) => !v)}
        />
        <View style={{ height: 10 }} />
        <Button
          title="Simulasikan JS Thread Block (300ms)"
          color="#f57c00"
          onPress={simulateHeavyComputation}
        />
      </View>

      <View style={styles.displayArea}>
        {showLeaky && <LeakyComponent />}
        {showClean && <CleanComponent />}
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#f5f5f5' },
  title: { fontSize: 20, fontWeight: 'bold', marginBottom: 8, color: '#212121' },
  metric: { fontSize: 14, color: '#e65100', marginBottom: 16, fontWeight: '600' },
  buttonGroup: { marginBottom: 20 },
  displayArea: { marginTop: 10 },
  leakyBox: { padding: 16, backgroundColor: '#ffebee', borderRadius: 8, marginBottom: 12 },
  cleanBox: { padding: 16, backgroundColor: '#e8f5e9', borderRadius: 8, marginBottom: 12 },
  boxText: { fontSize: 14, color: '#333' },
});
```

---

## Bagian 5: Checklist Pemahaman Evaluasi

Beri tanda centang `[x]` pada setiap kompetensi yang telah Anda kuasai dengan pembuktian empiris:

- [ ] **Hermes Engine Profiling:** Mampu mengekspor trace `.cpuprofile` dari Hermes, membukanya di Chrome DevTools Profiler / Speedscope, serta membaca waktu eksekusi self-time vs total-time pada call tree.
- [ ] **Heap Snapshot Analysis:** Mampu merekam snapshot memori `.heapsnapshot`, menyaring object berdasarkan constructor name, mendeteksi *Detached Fiber Nodes*, dan mengidentifikasi *Retaining Paths* menuju GC Root.
- [ ] **Thread Separation Awareness:** Memahami batas operasional antara UI/Main Thread (Native Android/iOS views, gesture handling), JS Thread (React reconciler, hooks, business logic), dan Shadow Thread (Yoga flexbox calculation).
- [ ] **Image Pipeline Memory Architecture:** Mengetahui cara kerja downsampling bitmap di memori (ARGB_8888 vs RGB_565), batas cache Fresco/SDWebImage, dan penggunaan library seperti `react-native-fast-image` atau `expo-image`.
- [ ] **FlatList Virtualization Tuning:** Mampu mengonfigurasi `windowSize`, `maxToRenderPerBatch`, `updateCellsBatchingPeriod`, `getItemLayout`, dan `removeClippedSubviews` untuk mencapai 60 FPS stabil pada list kompleks beribu baris.
- [ ] **Native Listener Cleanup Patterns:** Memastikan 100% integrasi event listener (`BackHandler`, `AppState`, `EventEmitter`, WebSocket, timer `setInterval`) memiliki cleanup callback saat komponen unmount.
- [ ] **Worklet & Reanimated Optimization:** Mengalihkan animasi padat komputasi (drag, pinch, swipe, scroll parallax) ke UI Thread menggunakan worklet Reanimated v3 untuk membebaskan JS thread dari jank.
- [ ] **New Architecture / Fabric Profiling:** Mengetahui karakteristik performa rendering sinkron Fabric C++ shadow tree vs legacy bridge JSON asynchronous serialization.
