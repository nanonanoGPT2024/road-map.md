# BAB-05-Native-Device-Features-dan-Sensor-Integration: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi komprehensif untuk menguji pemahaman konseptual, arsitektur, dan penerapan praktis integrasi fitur native serta sensor perangkat keras pada ekosistem React Native (Bare React Native maupun Expo Application Services).

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1.1: Foreground vs. Background Permissions
**Pertanyaan:**  
Mengapa platform modern (iOS 14+ dan Android 10/11+) memisahkan izin akses lokasi antara *Foreground* (`ACCESS_FINE_LOCATION` / `When In Use`) dan *Background* (`ACCESS_BACKGROUND_LOCATION` / `Always`), serta apa konsekuensi arsitekturalnya pada alur UX perizinan aplikasi React Native?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Penjelasan:**  
Pemisahan izin dilakukan oleh Apple dan Google demi privasi pengguna dan efisiensi daya baterai (mencegah *battery drain* dari *wake-locks* terus-menerus).
1. **Konsekuensi UX:** Aplikasi tidak diperbolehkan langsung meminta izin background secara sekaligus pada prompt pertama di Android 11+. Pengembang harus meminta izin Foreground terlebih dahulu, kemudian jika disetujui, menyajikan *in-app rationalization dialog* yang menjelaskan alasan background tracking dibutuhkan sebelum mengarahkan pengguna ke sistem settings/prompt background terpisah.
2. **Implementasi Library:** Pada React Native / Expo (`expo-location`), pengembang harus mengeksekusi `requestForegroundPermissionsAsync()` sebelum memanggil `requestBackgroundPermissionsAsync()`. Jika urutan ini dilanggar, platform akan otomatis menolak request atau melempar runtime exception.
</details>

---

### Soal 1.2: Sensor Update Interval & Event Loop Throttling
**Pertanyaan:**  
Sensor seperti *Accelerometer* dan *Gyroscope* mampu melakukan sampling data pada frekuensi tinggi (hingga 100Hz–200Hz). Apa bahaya performa jika data stream sensor tersebut langsung di-*pipe* ke React state (`useState`) tanpa throttling atau Native Driver bridge optimization?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Penjelasan:**  
1. **Bridge/Thread Congestion:** Pengiriman event berfrekuensi tinggi (misal 100Hz = 1 event tiap 10ms) dari thread native ke JavaScript runtime melalui Bridge (arsitektur lama) atau JSI (New Architecture) akan membebani JS Thread.
2. **Re-render Hell:** Memperbarui React state (`setState`) pada 100Hz memicu rekonsiliasi VDOM dan re-render komponen UI sebanyak 100 frame per detik, jauh melampaui refresh rate layar standar (60Hz / 16.6ms). Ini mengakibatkan *JS thread starvation*, frame drops (*jank*), dan UI menjadi tidak responsif.
3. **Mitigasi:** Atur `setUpdateInterval` ke frekuensi minimum yang dapat diterima use-case bisnis, gunakan `useSharedValue` dari `react-native-reanimated` untuk memproses koordinat di UI Thread langsung tanpa bolak-balik ke JS engine, atau gunakan operator throttling/debounce.
</details>

---

### Soal 1.3: Biometric Authentication vs. Secure Storage
**Pertanyaan:**  
Mengapa pemanggilan fungsi autentikasi biometrik standar (seperti `LocalAuthentication.authenticateAsync()`) saja **tidak cukup** untuk mengamankan data rahasia perbankan/token sesi, dan bagaimana rantai kriptografi yang benar di Android Keystore dan iOS Keychain?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Penjelasan:**  
Fungsi `authenticateAsync()` hanya mengembalikan boolean `success: true/false`. Pada perangkat yang di-*root* atau di-*jailbreak*, fungsi ini rentan di-*bypass* melalui runtime instrumentation (misal: Frida script hooking).  
**Pola Kriptografis yang Benar:**  
Data rahasia (auth token / refresh token) harus dienkripsi dengan kunci privat yang tersimpan di *Secure Enclave* (iOS) atau *Android Keystore/TEE* dengan flag `kSecAccessControlBiometryAny` / `setUserAuthenticationRequired(true)`. Operasi dekripsi materi rahasia hanya dapat diakses secara hardware jika autentikasi biometrik berhasil dilakukan oleh Secure Processor, bukan dari evaluasi boolean di sisi JavaScript.
</details>

---

### Soal 1.4: VisionCamera Frame Processors vs. Standard Snapshot
**Pertanyaan:**  
Apa perbedaan mendasar antara metode snapshot berkala (misal: `takePictureAsync()` interval) dengan *Frame Processors* (pada `react-native-vision-camera`) untuk use case Optical Character Recognition (OCR) atau deteksi QR/Barcode real-time?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Penjelasan:**  
- `takePictureAsync()` menghentikan streaming preview sesaat, memproses kompresi JPEG resolusi penuh, dan menyimpannya ke memori/file disk. Ini lambat (latency 300ms–1500ms per capture) dan boros alokasi memori heap.
- *Frame Processors* berjalan langsung pada buffer native kamera (*YUV/RGB surface*) di thread native kamera (worklet thread) secara real-time (30–60 FPS) tanpa alokasi disk dan tanpa serialisasi bridge. Frame dianalisis oleh plugin native (MLKit, TensorFlow Lite, OpenCV) menggunakan JSI secara zero-copy sebelum frame tersebut dibuang dari memori.
</details>

---

### Soal 1.5: Lifecycles dan Sensor Cleanup
**Pertanyaan:**  
Apa dampak yang terjadi pada sistem operasi dan aplikasi jika listener sensor hardware (`accelerometer.subscribe`) tidak dibersihkan saat komponen di-*unmount* atau aplikasi masuk ke state `background`?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Penjelasan:**  
1. **Memory Leak:** Callback JavaScript tetap tertahan di heap memory karena GC (Garbage Collector) mendeteksi referensi aktif dari native event emitter.
2. **Battery Drain:** Hardware controller sensor di SoC (System on Chip) tetap berada pada power state aktif (*wake lock* internal), menguras baterai ponsel pengguna secara signifikan meski layar mati atau pengguna berada di screen lain.
3. **Penyelesaian:** Selalu panggil `.unsubscribe()` atau `.remove()` pada return statement cleanup function di dalam hook `useEffect`, serta integrasikan dengan `AppState` listener untuk mematikan sensor ketika app berstatus `'background'` dan menyalakannya kembali saat `'active'`.
</details>

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 2.1: Dead Reckoning dan Filter Sensor Fusion
**Pertanyaan:**  
Dalam pelacakan orientasi perangkat tanpa GPS, penggunaan data *raw* Accelerometer saja menghasilkan *noise* tinggi akibat getaran, sedangkan data *Gyroscope* mengalami akumulasi *drift error* seiring waktu. Jelaskan bagaimana algoritma *Complementary Filter* atau *Kalman Filter* menyelesaikan masalah ini dalam aplikasi React Native!

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Penjelasan:**  
- **Karakteristik Sensor:** Accelerometer akurat dalam jangka panjang (menunjukkan arah gravitasi bumi 1G), namun sangat berisik (*high-frequency noise*) saat digerakkan dinamis. Gyroscope mengukur kecepatan sudut rotasi secara presisi dalam jangka pendek (*fast response*), namun memiliki kecenderungan melenceng (*low-frequency drift*) akibat akumulasi galat integrasi numerik waktu ($\Delta t$).
- **Complementary Filter:** Menggabungkan kedua karakteristik dengan menerapkan *High-Pass Filter* pada sinyal Gyroscope dan *Low-Pass Filter* pada sinyal Accelerometer:
  $$\theta_{filtered} = \alpha \cdot (\theta + \omega \cdot \Delta t) + (1 - \alpha) \cdot \theta_{acc}$$
  Di mana $\alpha$ biasanya bernilai $0.95 - 0.98$.
- Di React Native, pemrosesan ini idealnya dieksekusi di C++ JSI / Reanimated Worklet agar kalkulasi matriks per millisecond tidak mengalami latency jitter akibat garbage collection JS.
</details>

---

### Soal 2.2: Geofencing Accuracy vs Battery Consumption Trade-offs
**Pertanyaan:**  
Jelaskan perbedaan pendekatan native antara iOS *Significant Location Change Service* / *Region Monitoring (CLCircularRegion)* dan Android *FusedLocationProvider GeofencingClient* terhadap penjadwalan CPU dan penghematan baterai!

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Penjelasan:**  
- **iOS:** Menggunakan hardware baseband seluler (Cell Tower triangulation) dan Wi-Fi AP scanner tanpa menyalakan chip GPS aktif hingga perangkat bergerak signifikan (>500 meter atau berpindah cell tower). Ketika boundary geofence terlewati, kernel iOS membangunkan aplikasi yang tersuspensi (*silent wake*) selama maksimal 10 detik untuk memproses event `location`.
- **Android:** *FusedLocationProvider* mengelola *GeofencingClient* langsung pada subsistem hardware *CHRE (Context Hub Runtime Environment)* atau sensor fusion hub SoC. Pemantauan boundary dilakukan tanpa membangkitkan AP (Application Processor) utama sampai transisi (`GEOFENCE_TRANSITION_ENTER` / `EXIT`) terdeteksi, sehingga konsumsi daya CPU mendekati 0%.
- Kedua pendekatan memungkinkan tracking boundary tanpa perlu polling loop GPS terus-menerus.
</details>

---

### Soal 2.3: VisionCamera Skia / JSI Worklet Pipeline
**Pertanyaan:**  
Pada VisionCamera v3/v4, bagaimana arsitektur bridging bekerja saat kita ingin merender bounding box deteksi objek secara real-time di atas preview kamera tanpa mengalami desinkronisasi (*frame tearing*)?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Penjelasan:**  
Desinkronisasi terjadi jika koordinat objek dikirimkan melalui asynchronous bridge ke JavaScript thread lalu baru digambar oleh komponen React biasa. Pada saat koordinat tiba di JS thread, frame kamera native sudah bergeser 2-3 frame lebih maju.  
**Solusi Arsitektural:**  
1. Frame Processor berjalan sebagai Worklet (berbasis JSI) di thread kamera native.
2. Model deteksi (misal: TFLite via VisionCamera plugin) mengembalikan koordinat `[x, y, w, h]` langsung ke C++ pointer.
3. Menggunakan library `@shopify/react-native-skia` atau VisionCamera Canvas yang terikat pada native SurfaceView/Metal, bounding box digambar langsung di frame buffer yang sama atau di-overlay sinkron via shared memory worklet, menjaga koordinat dan frame kamera 100% *frame-accurate* pada 60 FPS.
</details>

---

### Soal 2.4: Handling App State Transitions pada Audio & Haptic Hardware
**Pertanyaan:**  
Ketika aplikasi pemutar audio atau perekam suara beralih ke background, kondisi apa saja yang menyebabkan sistem operasi membunuh process audio secara paksa pada iOS dan Android, dan konfigurasi apa yang wajib disertakan pada level native?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Penjelasan:**  
- **iOS:** Audio akan dihentikan paksa jika:
  1. `UIBackgroundModes` tidak menyertakan nilai `audio` pada `Info.plist`.
  2. Kategori `AVAudioSession` tidak diinisialisasi dengan `.playback` atau `.record` (misal tetap default `.ambient`).
  3. Aplikasi tidak menangani event *interruption* (misal panggilan telepon masuk via `AVAudioSessionInterruptionNotification`).
- **Android:** Service audio akan diterminasi oleh *Low Memory Killer (LMK)* jika:
  1. Background process tidak dideklarasikan sebagai `Foreground Service` bertipe `android:foregroundServiceType="mediaPlayback"`.
  2. Service tidak menampilkan persistent notification (`startForeground(ID, notification)`).
  3. Mengabaikan *Audio Focus* (`AudioManager.AUDIOFOCUS_REQUEST_GRANTED`), sehingga saat aplikasi lain membunyikan audio, sistem mematikan playback tanpa transisi halus.
</details>

---

### Soal 2.5: Hardware Concurrency: Bluetooth LE (BLE) MTU & Scanning Duty Cycles
**Pertanyaan:**  
Dalam komunikasi Bluetooth Low Energy (BLE) di React Native, apa keterbatasan *Maximum Transmission Unit (MTU)* default dan mengapa scanning BLE secara kontinyu tanpa filter UUID service dapat merusak performa Wi-Fi dan baterai perangkat?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Penjelasan:**  
1. **MTU Limitation:** MTU default BLE specification adalah 23 bytes (3 bytes untuk ATT header, hanya 20 bytes data payload efektif). Mengirim data sensor besar memerlukan negosiasi runtime `requestMTU(512)` agar throughput meningkat dan fragmentasi paket berkurang.
2. **Coexistence Interference & Battery:** Modul Bluetooth dan Wi-Fi pada kebanyakan smartphone berbagi antena 2.4GHz dan transceiver RF yang sama (*combo chip*). Melakukan BLE Scan tanpa batasan waktu (*infinite scan*) dan tanpa `serviceUUIDs` filter memaksa radio RF bekerja terus pada high-duty cycle, menyebabkan paket drop pada koneksi Wi-Fi, kenaikan suhu perangkat, dan penghentian paksa scan oleh Android OS setelah beberapa menit (*BLE Scan Throttling* sejak Android 7+).
</details>

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 1: Aplikasi Kurir Logistik & Pelacakan Armada Real-Time
**Konteks Masalah:**  
Sebuah aplikasi kurir logistik berbasis React Native ditugaskan mengirimkan koordinat lokasi driver ke backend setiap 10 detik saat melakukan pengantaran paket. Namun di produksi:
- Pada perangkat Xiaomi, Huawei, dan Samsung, tracking terhenti setelah 3 menit layar dimatikan (*screen off*).
- Pada perangkat iOS, aplikasi menerima status error `Location tracking terminated by system due to excessive power consumption`.
- Penggunaan baterai kurir turun drastis (habis dalam waktu 3.5 jam operasional).

**Tugas Anda:**  
Rancang arsitektur perbaikan menyeluruh yang mencakup lapisan Native Android, iOS, dan implementasi library React Native!

<details>
<summary>Solusi Teknis & Arsitektur</summary>

1. **Mengatasi Battery Aggressive OS Killers (Android OEM):**
   - Bungkus background task dalam Android **Foreground Service** dengan `foregroundServiceType="location"`.
   - Gunakan library teruji produksi seperti `react-native-background-actions` atau `@transistorsoft/react-native-background-geolocation`.
   - Minta izin eksplisit `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` melalui flow UI khusus (mengarahkan pengguna mematikan optimasi baterai via Settings intent OEM seperti AutoStart pada MIUI/EMUI).
   - Tampilkan persistent notification berprioritas rendah yang memenuhi kepatuhan regulasi Play Store.

2. **Mengatasi iOS Battery Consumption Kill:**
   - Ubah konfigurasi `CLLocationManager`: Jangan gunakan `kCLLocationAccuracyBestForNavigation` secara konstan.
   - Pasang `pausesLocationUpdatesAutomatically = true` dan gunakan `activityType = .automotiveNavigation`.
   - Implementasikan *Adaptive Accuracy*: Ketika sensor accelerometer mendeteksi perangkat diam (stationary state via *CoreMotion Activity Recognition*), turunkan akurasi GPS ke 100m–1km atau hentikan GPS dan aktifkan geofence radius 50 meter. Nyalakan GPS berpresisi tinggi kembali hanya jika perangkat keluar dari geofence atau sensor akselerasi mendeteksi gerakan kendaraan.

3. **Optimasi Jaringan & Sync Batching:**
   - Jangan melakukan HTTP POST setiap 10 detik saat sinyal seluler lemah (radio transmisi seluler menguras daya besar saat switching antar tower).
   - Simpan koordinat ke dalam SQLite/WatermelonDB lokal terlebih dahulu (*offline-first buffer*), lalu kirimkan secara batch setiap 60 detik atau jika payload mencapai 10 titik koordinat.
</details>

---

### Skenario 2: Mobile Banking e-KYC dengan Liveness Detection
**Konteks Masalah:**  
Aplikasi perbankan digital mengintegrasikan verifikasi wajah (e-KYC) dengan instruksi liveness: "Tengok ke kiri", "Kedipkan mata", dan "Buka mulut".  
Implementasi awal menggunakan snapshot `Camera.takePictureAsync()` interval tiap 250ms yang dikirimkan ke cloud AI via Base64. Dampak di lapangan:
- Latensi per verifikasi mencapai 6-12 detik per perintah; pengguna sering membatalkan proses (*drop-off rate* > 45%).
- Biaya API cloud AI membengkak 400%.
- Heap memory aplikasi melonjak hingga memicu *Out of Memory (OOM) Crash* pada perangkat Android berspesifikasi 3GB/4GB RAM.

**Tugas Anda:**  
Rancang ulang pipeline kamera dan liveness detection tersebut agar efisien, aman, dan berjalan secara on-device real-time!

<details>
<summary>Solusi Teknis & Arsitektur</summary>

1. **Migrasi ke On-Device VisionCamera Frame Processors:**
   - Gunakan `react-native-vision-camera` v3/v4 dengan Worklet JSI.
   - Integrasikan Google MLKit Face Detection Native Plugin (`vision-camera-face-detector` atau custom C++/Java/Obj-C plugin).
   - Jalankan deteksi orientasi kepala (*Euler Y Angle* untuk tengok kiri/kanan), status mata (*Eye Open Probability* untuk kedip), dan *Mouth Open Detection* langsung di CPU/GPU perangkat pengguna pada rate 30 FPS.

2. **Eliminasi Base64 & OOM Issues:**
   - Hilangkan transmisi gambar Base64 melalui bridge. Pemrosesan citra dilakukan langsung di memory frame buffer ($YUV\_420\_888$ pada Android / $CVPixelBuffer$ pada iOS).
   - Logika state machine liveness (Menunggu Mulai -> Instruksi 1: Kedip -> Instruksi 2: Tengok -> Selesai) dieksekusi secara lokal di client.

3. **Verifikasi Final Anti-Spoofing:**
   - Hanya ketika seluruh sequence instruksi liveness lokal terpenuhi dengan timestamp dan motion vector yang valid, ambil 1 single high-resolution image (`takePictureAsync()`) bersama cryptographic hash token yang ditandatangani Secure Enclave untuk dikirim ke backend perbankan sebagai bukti audit KYC final.
   - Hasil: Pengurangan latensi verifikasi menjadi < 1.5 detik, 0 crash OOM, dan pemotongan biaya API cloud hingga 90%.
</details>

---

### Skenario 3: Health & Fitness IoT: Audio Coaching + Heart Rate BLE Disconnects
**Konteks Masalah:**  
Sebuah aplikasi kebugaran terhubung ke perangkat Heart Rate Monitor (HRM) via Bluetooth LE, memutar instruksi suara berkala ("Denyut jantung Anda di zona anaerobik"), dan memetakan rute lari via GPS. Masalah yang sering dilaporkan pengguna:
- Ketika audio coaching berbunyi, koneksi BLE ke HRM mendadak *timed out* / terputus.
- Jika pengguna menerima panggilan WhatsApp, setelah panggilan berakhir, audio background tracking mati selamanya dan musik Spotify pengguna berhenti total.
- Saat sinyal GPS hilang di bawah flyover atau terowongan, aplikasi langsung crash.

**Tugas Anda:**  
Analisis akar penyebab masalah hardware/OS tersebut dan buat panduan arsitektur perbaikannya!

<details>
<summary>Solusi Teknis & Arsitektur</summary>

1. **Akar Masalah BLE Disconnects:**
   - **RF Interference & Thread Blocking:** Thread audio decoding dan BLE scanning/reception saling berebut prioritas pada CPU core, atau BLE peripheral kehabisan connection supervisory timeout karena radio switching saat audio session dibuka.
   - **Solusi:** Tingkatkan `Connection Priority` pada Android BLE (`requestConnectionPriority(CONNECTION_PRIORITY_HIGH)`) sebelum sesi audio dimulai, dan sesuaikan peripheral *supervision timeout* minimal ke 2000ms.

2. **Audio Focus & Ducking Configuration:**
   - Kegagalan Spotify dan crash audio pasca panggilan disebabkan oleh penanganan *Audio Ducking* dan *Audio Interruption* yang keliru.
   - **Solusi:**
     - Konfigurasikan iOS `AVAudioSession`: Atur opsi `.duckOthers` (`setCategory(AVAudioSessionCategoryPlayback, options: [.duckOthers])`). Ini memerintahkan Spotify untuk mengecilkan volume sementara saat instruksi suara diputar, lalu kembali normal secara otomatis.
     - Tangani listener `AVAudioSessionInterruptionNotification` di iOS dan `onAudioFocusChange` di Android. Saat panggilan WhatsApp masuk (`AUDIOFOCUS_LOSS_TRANSIENT`), pause playback; saat panggilan selesai (`AUDIOFOCUS_GAIN`), resume audio cue engine.

3. **GPS Loss Handling:**
   - Jangan biarkan error callback `POSITION_UNAVAILABLE` melempar unhandled exception.
   - Pasang filter *Kalman Filter* atau fallback ke estimasi *Dead Reckoning* menggunakan data sensor Pedometer (`CoreMotion` / Android `Step Counter`) untuk memprediksi jarak tempuh sementara selama berada di area tanpa satelit GPS.
</details>

---

## Bagian 4: Practical Chapter Challenge

### Tantangan: "Smart Hardware Compass & Leveler with Auto-Haptics"

Bangun sebuah modul fungsional React Native (Single Component/Hook Architecture) yang mengombinasikan sensor **Magnetometer**, **Accelerometer**, dan modul **Haptics** dengan spesifikasi teknis berikut:

#### 1. Persyaratan Fungsional
1. **True Heading Compass:**
   - Menghitung sudut orientasi kompas ($0^\circ - 359^\circ$) berdasarkan kombinasi sumbu $X$ dan $Y$ dari Magnetometer.
   - Menampilkan indikator mata angin (N, NE, E, SE, S, SW, W, NW).
2. **Spirit Leveler (Waterpass):**
   - Menggunakan data Accelerometer ($X$ dan $Y$) untuk mendeteksi kemiringan bidang datar.
   - Sebuah visual "bubble" harus berada tepat di titik tengah jika kemiringan berada di toleransi $\pm 1.5^\circ$.
3. **Tactile Haptic Feedback:**
   - Ketika orientasi kompas tepat mengarah ke Utara ($0^\circ / 360^\circ \pm 2^\circ$), picu haptic feedback dengan pola `ImpactFeedbackStyle.Heavy`.
   - Ketika posisi waterpass mencapai titik datar sempurna, picu `NotificationFeedbackType.Success`.
   - **PENTING:** Haptic feedback tidak boleh terpicu berulang-ulang setiap 10ms (harus ada debouncing / state lock sampai pengguna meninggalkan rentang toleransi).

#### 2. Kriteria Kode Bersih & Efisiensi Hardware
- Menggunakan `setUpdateInterval` yang terukur (misal: 60ms – 100ms) untuk mencegah CPU thermal throttling.
- Integrasi `AppState` listener: Ketika aplikasi masuk ke background, sensor **wajib di-unmount/unsubscribed** secara otomatis, dan disambungkan kembali saat foreground.
- Penanganan izin jika sensor membutuhkan permission khusus pada platform tertentu.

---

## Bagian 5: Checklist Pemahaman (Self-Audit)

Gunakan daftar periksa ini untuk mengevaluasi kesiapan Anda dalam mengintegrasikan fitur native dan sensor perangkat di tingkat produksi:

- [ ] **Sistem Izin Modern:** Memahami perbedaan alur runtime permission antara Android API 33+ (termasuk izin media terpisah dan notifikasi) dan iOS Info.plist usage descriptions.
- [ ] **Background Processing Limits:** Mengetahui batas eksekusi task di background (iOS Background Tasks Framework vs. Android WorkManager/Foreground Services) dan larangan Apple App Store terkait arbitrary background execution.
- [ ] **Sensor Performance:** Mampu menerapkan debouncing, throttling, atau Reanimated UI Worklets saat mengolah data stream dari sensor inertial (IMU).
- [ ] **Hardware Security:** Mampu mengimplementasikan penyimpanan kriptografis terproteksi biometrik menggunakan Android Keystore / iOS Keychain alih-alih hanya mengandalkan boolean result dari library UI.
- [ ] **Vision & Frame Processing:** Memahami alur kerja zero-copy image analysis menggunakan VisionCamera dan C++/JSI Frame Processors.
- [ ] **Battery Profiling:** Terbiasa memonitor konsumsi energi aplikasi menggunakan Android Studio Profiler (Energy Profiler) dan Xcode Instruments (Energy Impact & Location template).
- [ ] **Hardware Lifecycle Management:** Selalu membersihkan native listeners, event subscriptions, dan hardware wake-locks pada lifecycle hook teardown.
