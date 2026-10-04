# Bab 06 Module 01: High-Performance Animations & Gestures

---

## SEKSI 01 — IDENTITAS MODUL
* **Kategori**: `03-Frontend-and-Mobile`
* **Kurikulum**: `react-native`
* **Topik**: High-Performance Animations & Gestures
* **Tingkat Kesulitan**: Advanced / Staff Engineer Level
* **Prasyarat Konseptual**:
  * Arsitektur Threading React Native (UI Thread, JS Thread, Shadow Thread/Layout Engine).
  * New Architecture React Native (Fabric Renderer, TurboModules, JSI - JavaScript Interface).
  * React Core: Siklus Render, Garbage Collection, Rekonsiliasi VDOM, Hooks Lifecycle.
* **Target Ekosistem**: React Native >= 0.74, React Native Reanimated v3+, React Native Gesture Handler v2+, TypeScript 5+.

---

## SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, Anda ditargetkan untuk:
1. **Menganalisis dan Membedah Internal Execution Model**: Memahami secara deterministik bagaimana animasi dieksekusi di *UI Thread* melalui JavaScript Interface (JSI) Runtime terpisah (*Worklet Runtime*), mengeliminasi *bridge crossing serialization overhead*.
2. **Mendesain Interaksi Gesture 60/120 FPS**: Mengintegrasikan API deklaratif `react-native-gesture-handler` (RNGH) dengan *Shared Values* `react-native-reanimated` tanpa pernah memicu *frame drop* akibat *JS Thread starvation*.
3. **Menguasai Layout Animations & Shared Element Transitions**: Mengonfigurasi transisi struktural dan translasi komponen berbasis interpolasi matriks transformasi 3D dan kalkulasi batas bounding box native.
4. **Mendeteksi dan Memitigasi Memory Leak & Garbage Collection Spikes**: Mengidentifikasi capturing scope closure ilegal pada worklet, memory retention cycle, serta alokasi array/objek imperatif di dalam animation frame loop.
5. **Mengimplementasikan Telemetri Frame Rate Skala Produksi**: Membangun visualizer dan monitor performa real-time berbasis frame callback (`useFrameCallback`) untuk mendeteksi *Jank* (16.67ms/8.33ms deadline overrun).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Dual-Runtime vs Single-Thread Illusion
Secara fundamental, React Native beroperasi di bawah realitas multi-thread:
1. **JavaScript Thread**: Tempat engine Hermes mengeksekusi kode React, kalkulasi state, network response, reducers, dan business logic. Thread ini rentan terhadap *starvation* (tersumbat) ketika ada kalkulasi parsing JSON besar, serialisasi Redux, atau render pohon komponen masif.
2. **UI Thread (Main Thread)**: Thread native platform (Android Choreographer / iOS Core Animation run loop) yang bertugas menangkap event sentuhan (touch events), menghitung layout akhir, dan menggambar piksel ke buffer layar pada interval refresh rate (60Hz = 16.67ms, 120Hz = 8.33ms).

```
   PENDEKATAN KLASIK (Animated API lama / Bridge):
   [Touch Event] -> (UI Thread) 
                     \-- Bridge Serialization (JSON) --> (JS Thread) [Hitung State]
                                                         /-- Bridge Serialization (JSON) --/
                     [Draw Frame] <-- (UI Thread) <-----/
   *Masalah: Jika JS Thread sibuk selama 50ms, frame drop terjadi = ANIMASI PATAH (JANK).*

   PENDEKATAN MODERN (Reanimated v3 + Gesture Handler via JSI):
   [Touch Event] -> (UI Thread)
                     \-> [Worklet Runtime (JSI)] -> [Mutasi Render Node Native] -> [Draw Frame]
   *Hasil: JS Thread dilewati sepenuhnya. 120 FPS terjamin bahkan saat JS Thread 100% blocked.*
```

Mental model Staff Engineer: **"Animasi dan gesture adalah domain UI Thread; JS Thread hanya bertindak sebagai deklarator state awal dan koordinator side effect akhir."** Kode animasi yang ditulis dalam JavaScript harus dipandang sebagai instruksi yang dikompilasi ke bytecode untuk dieksekusi oleh mesin eksekusi sekunder di UI Thread langsung melalui JSI pointer.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur aliran data sinkron antara Hardware Digitizer, Platform Touch Event Pipeline, JSI Bridge-less Runtime, dan Fabric Shadow Tree:

```
+--------------------------------------------------------------------------------------------------+
|                                    PLATFORM HARDWARE (TOUCH SCREEN)                              |
+--------------------------------------------------------------------------------------------------+
                                                 | (Raw Hardware Interrupts: MotionEvent / UIEvent)
                                                 v
+--------------------------------------------------------------------------------------------------+
|                                     UI THREAD / MAIN RUN LOOP                                    |
|                                                                                                  |
|   +------------------------------------+          +------------------------------------------+   |
|   |   Platform Gesture Recognizers     | -------> | RNGH Native Handler (RNGestureHandler)   |   |
|   |   (Android / iOS View System)      |          | - State machine: BEGAN, ACTIVE, ENDED    |   |
|   +------------------------------------+          +------------------------------------------+   |
|                                                                    |                             |
|                                                                    v (Synchronous C++ Event Push)|
|   +------------------------------------------------------------------------------------------+   |
|   |                            REANIMATED WORKLET RUNTIME (HERMES JSI)                       |   |
|   |                                                                                          |   |
|   |   +-------------------------------+               +----------------------------------+   |   |
|   |   | Worklet Event Callback        | ------------> | SharedValue<T> Direct Pointer    |   |   |
|   |   | (onUpdate, onBegin, etc.)     |               | (Atomic thread-safe mutation)    |   |   |
|   |   +-------------------------------+               +----------------------------------+   |   |
|   |                                                                    |                     |   |
|   |                                                                    v                     |   |
|   |   +----------------------------------------------------------------------------------+   |   |
|   |   | Layout/Style Derivation Engine (useAnimatedStyle)                                |   |   |
|   |   | Computes: Matrix4x4 Transform, Opacity, Layout Dimensions                        |   |   |
|   |   +----------------------------------------------------------------------------------+   |   |
|   +------------------------------------------------------------------------------------------+   |
|                                                |                                                 |
|                                                v (Direct C++ Mutation via JSI)                   |
|   +------------------------------------------------------------------------------------------+   |
|   | FABRIC COMPONENT INSTANCE (ShadowNode / Platform View: android.view.View / UIView)       |   |
|   | Mutates Render Pipeline: RenderLayer -> CoreAnimation / RenderNode                     |   |
|   +------------------------------------------------------------------------------------------+   |
+--------------------------------------------------------------------------------------------------+
         |                                                                      ^
         | (Asynchronous Notification via JSI - Microtask Queue)                | (Initial Layout
         v                                                                      |  & Tree Setup)
+-------------------------------------------------------------------------------+------------------+
|                                  JAVASCRIPT THREAD (REACT RUNTIME)                               |
|                                                                                                  |
|   +-------------------------------------+             +--------------------------------------+   |
|   | React Fiber Reconciliation Tree     |             | Reanimated UI Props Registry         |   |
|   | (VDOM, State hooks, Business Logic) |             | (Holds WeakRef to Host Components)   |   |
|   +-------------------------------------+             +--------------------------------------+   |
|                     |                                                                            |
|                     v (runOnJS invocation only when required for side-effects)                   |
|   +------------------------------------------------------------------------------------------+   |
|   | Application State Transition / Analytics / Database Queries / Network Requests           |   |
|   +------------------------------------------------------------------------------------------+   |
+--------------------------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Worklet Internals
Sebuah *worklet* adalah fungsi JavaScript biasa yang diawali oleh direktif `"worklet";` (atau ditransformasi secara otomatis oleh Babel plugin Reanimated). Pada saat proses kompilasi Babel:
* Kode fungsi di-ekstrak dan dibuatkan representasi serialisasi.
* Babel menghasilkan objek penanda (*closure capture*) yang berisi:
  * ID unik fungsi.
  * Pointer ke kode yang dikompilasi untuk engine Hermes sekunder.
  * Array variabel yang di-*capture* dari enclosing scope (upvalues).
* Ketika dilewatkan ke UI thread, Reanimated menginstansiasi fungsi tersebut di dalam konteks **Hermes Runtime kedua** yang dialokasikan khusus untuk Main Thread.

### 2. Shared Values (`SharedValue<T>`)
`SharedValue` bukan sekadar React ref (`useRef`). Anatominya mencakup:
* **C++ Core**: Kelas C++ (`reanimated::ShareableValue`) yang mengelola nilai memori mentah yang dapat diakses secara thread-safe menggunakan atomic pointers atau lock-free synchronization primitives.
* **JS Thread Proxy**: Properti `.value` pada JS Thread dipetakan melalui JSI host object getter/setter. Ketika diubah di JS Thread, ia menjadwalkan update sinkronisasi ke UI Runtime.
* **UI Thread Reference**: Pada UI Thread, modifikasi `.value` bersifat instan dan memicu dirty-flag checking pada listener (`useAnimatedStyle`) secara langsung di frame cycle berjalan tanpa overhead rekonsiliasi.

### 3. Gesture Handler Synchronous State Machine
`react-native-gesture-handler` mendaftarkan native touch listener langsung pada sistem windowing platform:
* Mengintersepsi event sistem operasi sebelum React Native root view memprosesnya.
* Mengevaluasi kondisi batas (*hit-testing*, *velocity thresholds*, *directional locks*) secara native di thread utama.
* Melakukan dispatch event langsung ke fungsi worklet Reanimated melalui C++ JSI call tanpa memicu event serialisasi React Synthetic Event.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Vektor Transformasi dan Matriks 4x4
Setiap properti animasi yang memengaruhi tampilan visual wajib menghindari pemicuan *Layout Pass* (Yoga Layout engine). Properti yang memicu layout pass: `width`, `height`, `top`, `left`, `margin`, `padding`. Properti ini memaksa CPU menghitung ulang geometri node lain (*Reflow/Relayout*), yang pada UI masif menghabiskan waktu > 16ms per frame.

Gunakan selalu properti *compositor-only*:
* `transform: [{ translateX }, { translateY }, { scale }, { rotate }]`
* `opacity`

Secara grafis, transformasi ini direpresentasikan sebagai operasi perkalian matriks 4x4 pada hardware GPU:

$$M_{final} = M_{parent} \times T(x, y, z) \times R(\theta) \times S(s_x, s_y, s_z)$$

Perubahan pada matriks ini diunggah langsung ke layer visual GPU (RenderNode pada Android RenderThread, CoreAnimation layer pada iOS QuartzCore) tanpa menyentuh CPU untuk layout bounding recalculation.

### Physics-Based Springs vs Duration-Based Timings
Animasi kurva Bézier klasik (`timing`) memetakan waktu $t \in [0, 1]$ ke nilai menggunakan fungsi polinomial. Masalah utamanya adalah hilangnya momentum. Jika pengguna melepaskan swipe dengan kecepatan $v = 1500\text{ px/s}$, `withTiming` akan mengabaikan kecepatan tersebut dan memulai kurva dari nol, memicu diskontinuitas akselerasi (jank perseptual).

Reanimated mengimplementasikan *Damped Harmonic Oscillator* via `withSpring`:

$$F = -k x - c v$$

Di mana:
* $m$ = massa (*mass*, default $1$)
* $k$ = kekakuan pegas (*stiffness*)
* $c$ = koefisien redaman (*damping*)
* $x$ = simpangan dari target posisi
* $v$ = kecepatan sesaat

Persamaan diferensial diselesaikan secara numerik di setiap frame Choreographer/CADisplayLink menggunakan integrasi Euler atau Runge-Kutta orde ke-4 (RK4). Ini mempertahankan transfer momentum yang natural ketika gesture selesai dilepaskan oleh jari user.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental interaksi gesture pan-drag berbasis physics spring dengan kalkulasi velocity clamp dan boundary limits.

```typescript
// Path: src/components/fundamental/DraggableCard.tsx
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Gesture, GestureDetector, GestureHandlerRootView } from 'react-native-gesture-handler';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  WithSpringConfig,
} from 'react-native-reanimated';

const SPRING_CONFIG: WithSpringConfig = {
  damping: 15,
  stiffness: 120,
  mass: 1,
  overshootClamping: false,
  restDisplacementThreshold: 0.01,
  restSpeedThreshold: 2,
};

export const DraggableCard: React.FC = () => {
  // 1. Inisialisasi Shared Values di UI Runtime
  const translationX = useSharedValue<number>(0);
  const translationY = useSharedValue<number>(0);
  const prevTranslationX = useSharedValue<number>(0);
  const prevTranslationY = useSharedValue<number>(0);
  const isInteracting = useSharedValue<boolean>(false);

  // 2. Deklarasi Gesture Object menggunakan RNGH v2 Builder API
  const panGesture = Gesture.Pan()
    .onStart(() => {
      'worklet';
      // Simpan offset translasi terakhir sebagai anchor point
      prevTranslationX.value = translationX.value;
      prevTranslationY.value = translationY.value;
      isInteracting.value = true;
    })
    .onUpdate((event) => {
      'worklet';
      // Mutasi real-time sinkron tanpa menyentuh JS Thread
      translationX.value = prevTranslationX.value + event.translationX;
      translationY.value = prevTranslationY.value + event.translationY;
    })
    .onEnd((event) => {
      'worklet';
      isInteracting.value = false;
      // Kembalikan ke koordinat origin (0, 0) dengan mempertahankan inersia velocity
      translationX.value = withSpring(0, {
        ...SPRING_CONFIG,
        velocity: event.velocityX,
      });
      translationY.value = withSpring(0, {
        ...SPRING_CONFIG,
        velocity: event.velocityY,
      });
    });

  // 3. Pemetaan Shared Values ke GPU Transformation Layer
  const animatedStyle = useAnimatedStyle(() => {
    'worklet';
    return {
      transform: [
        { translateX: translationX.value },
        { translateY: translationY.value },
        { scale: withSpring(isInteracting.value ? 1.08 : 1) },
      ],
      elevation: isInteracting.value ? 10 : 2,
      shadowOpacity: withSpring(isInteracting.value ? 0.3 : 0.1),
    };
  });

  return (
    <View style={styles.container}>
      <GestureDetector gesture={panGesture}>
        <Animated.View style={[styles.card, animatedStyle]} />
      </GestureDetector>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F8F9FA',
  },
  card: {
    width: 140,
    height: 140,
    backgroundColor: '#0F172A',
    borderRadius: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 10 },
    shadowRadius: 15,
  },
});
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Konstruksi Gesture & Runtime Hooking
* **Baris 19-23**: `useSharedValue<number>(0)` mengalokasikan slot memori kontinu di heap C++ JSI yang ditautkan ke pointer JS runtime. Nilai ini tidak reaktif terhadap React rerender cycle; perubahan nilai tidak memicu eksekusi fungsi komponen `DraggableCard`.
* **Baris 26**: `Gesture.Pan()` menginstansiasi PanGestureHandler native. Tidak ada JSX element wrapper handler lama (`<PanGestureHandler>`), mengeliminasi hierarki native view yang tidak perlu.
* **Baris 27, 34, 40**: Direktif eksplisit `'worklet';` memastikan fungsi diekstrak oleh Babel Reanimated plugin untuk dijalankan pada Hermes Worklet Runtime di UI thread.
* **Baris 29-30**: Mempertahankan origin translasi. Menghindari "jumping behavior" saat gesture kedua dimulai sebelum pegas selesai kembali ke titik asal.
* **Baris 36-37**: Akumulasi perpindahan. `event.translationX` dihitung relatif terhadap titik start gesture saat ini, ditambahkan ke basis `prevTranslationX`.
* **Baris 43-50**: `withSpring(0, { ..., velocity: event.velocityX })`. **Kritis:** Mentransfer momentum fisik dari jari pengguna langsung ke persamaan pegas. Animasi tidak melambat secara artifisial, melainkan meluncur sesuai gaya dorong (*kinetic flick*).
* **Baris 54-64**: `useAnimatedStyle`. Fungsi mapper murni yang dieksekusi setiap kali salah satu SharedValue internal (`translationX`, `translationY`, atau `isInteracting`) ditandai kotor (*dirty*). Menghasilkan representasi style tree ringkas yang disuntikkan langsung ke Fabric C++ node tanpa layout invalidation.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Enterprise Bottom Sheet dengan Fluid Drag-to-Dismiss dan Interactive Rubber-Banding
Pada aplikasi perbankan tier-1 atau ride-hailing skala enterprise, Bottom Sheet interaktif adalah komponen inti yang sering kali rusak performanya karena:
1. Menangani gestur dragging sekaligus mengelola scrolling internal (nested scrolling conflict).
2. Perlu memicu transisi rute (native back atau sheet dismissal) sembari memperbarui backdrop opacity yang halus.
3. Mengharuskan efek *rubber-banding* (tahanan elastis non-linear) saat ditarik melampaui batas ekspansi maksimum.

Jika diimplementasikan menggunakan state React biasa (`useState`), setiap pergeseran piksel memicu re-render seluruh hierarki sheet, menyebabkan frame rate anjlok hingga < 20 FPS pada perangkat Android mid-to-low end. Kita akan membangun komponen **Enterprise Fluid Bottom Sheet** dengan kalkulasi elastisitas logaritmik murni di UI Thread.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA

```tsx
// Path: src/components/interactive/EnterpriseBottomSheet.tsx
import React, { useCallback, useId } from 'react';
import {
  Dimensions,
  StyleSheet,
  View,
  Text,
  Pressable,
} from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  interpolate,
  Extrapolation,
  runOnJS,
  useAnimatedReaction,
} from 'react-native-reanimated';

const { height: SCREEN_HEIGHT } = Dimensions.get('window');
const SHEET_MAX_HEIGHT = SCREEN_HEIGHT * 0.75;
const SHEET_MIN_HEIGHT = 100;
const DISMISS_THRESHOLD = 50;

interface BottomSheetProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
}

export const EnterpriseBottomSheet: React.FC<BottomSheetProps> = ({
  isOpen,
  onClose,
  children,
}) => {
  // Posisi Y vertikal dari sheet. 
  // Nilai 0 merepresentasikan posisi fully open (SHEET_MAX_HEIGHT).
  // Nilai positif merepresentasikan offset ke bawah (tertutup).
  const translateY = useSharedValue<number>(SCREEN_HEIGHT);
  const context = useSharedValue<{ startY: number }>({ startY: 0 });

  const springConfig = {
    damping: 20,
    stiffness: 150,
    mass: 0.8,
    overshootClamping: false,
  };

  // Sinkronisasi prop isOpen dengan animasi native
  useAnimatedReaction(
    () => isOpen,
    (currentIsOpen, previousIsOpen) => {
      'worklet';
      if (currentIsOpen !== previousIsOpen) {
        if (currentIsOpen) {
          translateY.value = withSpring(0, springConfig);
        } else {
          translateY.value = withTiming(SCREEN_HEIGHT, { duration: 250 });
        }
      }
    },
    [isOpen]
  );

  const handleDismissComplete = useCallback(() => {
    onClose();
  }, [onClose]);

  // Algoritma Rubber-Banding Logaritmik (Worklet murni)
  const calculateRubberBanding = (delta: number, dimension: number): number => {
    'worklet';
    const c = 0.55; // Koefisien resistensi iOS standar
    return (delta * dimension * c) / (dimension + c * delta);
  };

  const panGesture = Gesture.Pan()
    .onStart(() => {
      'worklet';
      context.value = { startY: translateY.value };
    })
    .onUpdate((event) => {
      'worklet';
      const rawY = context.value.startY + event.translationY;

      if (rawY < 0) {
        // Efek tarikan ke atas melebihi batas maksimum (Overdrag Rubber-Band)
        const overdrag = -rawY;
        const resisted = calculateRubberBanding(overdrag, SHEET_MAX_HEIGHT);
        translateY.value = -resisted;
      } else {
        translateY.value = rawY;
      }
    })
    .onEnd((event) => {
      'worklet';
      // Kondisi 1: Kecepatan lempar ke bawah tinggi -> Tutup
      if (event.velocityY > 1200) {
        translateY.value = withTiming(
          SCREEN_HEIGHT,
          { duration: 200 },
          (isFinished) => {
            if (isFinished) {
              runOnJS(handleDismissComplete)();
            }
          }
        );
        return;
      }

      // Kondisi 2: Drag melebihi batas threshold -> Tutup
      if (translateY.value > SHEET_MAX_HEIGHT * 0.4) {
        translateY.value = withTiming(
          SCREEN_HEIGHT,
          { duration: 250 },
          (isFinished) => {
            if (isFinished) {
              runOnJS(handleDismissComplete)();
            }
          }
        );
        return;
      }

      // Kondisi 3: Reset kembali ke kondisi Snap Terbuka (0)
      translateY.value = withSpring(0, {
        ...springConfig,
        velocity: event.velocityY,
      });
    });

  const sheetAnimatedStyle = useAnimatedStyle(() => {
    'worklet';
    return {
      transform: [{ translateY: translateY.value }],
    };
  });

  const backdropAnimatedStyle = useAnimatedStyle(() => {
    'worklet';
    const opacity = interpolate(
      translateY.value,
      [0, SHEET_MAX_HEIGHT],
      [0.6, 0],
      Extrapolation.CLAMP
    );

    return {
      opacity,
      pointerEvents: translateY.value >= SHEET_MAX_HEIGHT ? 'none' : 'auto',
    };
  });

  return (
    <View style={StyleSheet.absoluteFillObject} pointerEvents="box-none">
      <Animated.View style={[styles.backdrop, backdropAnimatedStyle]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
      </Animated.View>

      <GestureDetector gesture={panGesture}>
        <Animated.View style={[styles.sheetContainer, sheetAnimatedStyle]}>
          <View style={styles.handleContainer}>
            <View style={styles.indicator} />
          </View>
          <View style={styles.contentContainer}>{children}</View>
        </Animated.View>
      </GestureDetector>
    </View>
  );
};

const styles = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#000',
    zIndex: 10,
  },
  sheetContainer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: SHEET_MAX_HEIGHT,
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    zIndex: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 24,
  },
  handleContainer: {
    width: '100%',
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  indicator: {
    width: 48,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: '#CBD5E1',
  },
  contentContainer: {
    flex: 1,
    paddingHorizontal: 24,
  },
});
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Evaluasi | Animated API Bawaan (Classic Bridge) | Reanimated v3 + RNGH v2 (Modern Architecture) | Skia Animation Canvas Direct Engine |
| :--- | :--- | :--- | :--- |
| **Execution Runtime** | JS Thread (atau native driver terbatas) | Main UI Thread via Worklet JSI Runtime | Render Thread Skia C++ Pipeline |
| **Dukungan Properti Dinamis** | Terbatas pada `transform` & `opacity` jika `useNativeDriver: true` | Penuh: transforms, colors, layout transitions, style objects | Grafis 2D murni, shaders, canvas path morphing |
| **Beban Memory Per Hook** | Rendah (hanya alokasi JS instan) | Sedang (instansiasi C++ JSI host object + Hermes Worklet runtime) | Tinggi (Skia Graphics Context + GPU Framebuffers) |
| **Kompleksitas Debugging** | Sederhana (console.log standar di JS engine) | Kompleks (Log di Worklet melintasi boundaries, butuh C++ debugging) | Sangat Kompleks (Shader language debugging / GL traces) |
| **Overhead Frame Dropping** | Sangat Rentan terhadap pemblokiran JS runtime | Rendah (kebal terhadap JS loop blocking) | Nol (Langsung digambar di GPU draw loop) |
| **Kesesuaian Use-case** | Form input sederhana & transisi fade dasar | Mobile Application UI, Bottom Sheets, Gestures, List Items | Data visualization kompleks, gaming ringan, filter grafis |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Zombie Child Nodes & Late Layout Arrival
Saat mengimplementasikan *Layout Animations* (`entering`, `exiting`, `layout`), sebuah node yang telah di-unmount dari React tree secara visual masih ada di layar hingga animasi keluar selesai.
* **Failure Mode**: Terjadi null-pointer exception atau data inconsistency jika child component mengonsumsi React Context yang sudah dibersihkan sebelum animasi exit selesai.
* **Mitigasi**: Gunakan snapshot ref internal untuk membekukan state lokal di dalam komponen child, mencegah binding data yang mengasumsikan context induk selalu valid selama fase exiting.

### 2. Velocity Explosion pada Multi-Touch Abrupt Release
Ketika gesture berpindah dari 1 jari ke 2 jari (atau jari bergetar di akhir sentuhan), `event.velocityX` dapat melonjak ke angka > 25,000 px/s secara tidak wajar.
* **Mitigasi**: Selalu gunakan fungsi *velocity clamping* sebelum memasukkan kecepatan ke physics spring:

```typescript
const MAX_PERMISSIBLE_VELOCITY = 3000;
const clampedVelocity = Math.max(
  -MAX_PERMISSIBLE_VELOCITY, 
  Math.min(event.velocityX, MAX_PERMISSIBLE_VELOCITY)
);
```

### 3. Gesture Conflict pada Nested Scrollables
Komponen `PanGesture` di dalam `ScrollView` atau `FlatList` native sering kali "mencuri" event atau sebaliknya, terkunci secara kaku.
* **Mitigasi**: Gunakan API `simultaneousWithExternalGesture` atau definisikan `activeOffsetX` / `failOffsetY` secara eksplisit untuk memberikan toleransi scroll vertikal native sebelum pan gesture diaktifkan:

```typescript
const pan = Gesture.Pan()
  .activeOffsetX([-15, 15]) // Butuh pergeseran horizontal 15px sebelum gesture aktif
  .failOffsetY([-10, 10]);  // Batalkan pan jika user melakukan gesture vertikal > 10px
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Mengakses Variabel Non-Worklet di Dalam Worklet (Capturing Mutability)
```typescript
// SALAH (ANTI-PATTERN FATAL):
let externalFlag = false;

const gesture = Gesture.Pan().onUpdate(() => {
  'worklet';
  // externalFlag di-capture saat kompilasi. 
  // Nilai ini adalah salinan yang TIDAK AKAN PERNAH sinkron dengan JS runtime!
  if (externalFlag) { 
    // Mutasi ini sia-sia dan memicu race condition tak terlihat
  }
});

// BENAR:
const isExternalFlagActive = useSharedValue<boolean>(false);

const gesture = Gesture.Pan().onUpdate(() => {
  'worklet';
  if (isExternalFlagActive.value) {
    // SharedValue menjamin referensi atomic C++ yang sinkron di kedua runtime
  }
});
```

### 2. Memanggil `runOnJS` Terlalu Sering di Animation Loop
```typescript
// SALAH (Frame Stuttering Generator):
const style = useAnimatedStyle(() => {
  'worklet';
  // Memanggil JS Thread pada setiap 16ms frame (60 FPS = 60 bridge-calls per detik!)
  runOnJS(notifyParentOnEveryFrame)(translationX.value);
  return { transform: [{ translateX: translationX.value }] };
});

// BENAR:
// Gunakan useAnimatedReaction dengan throttling atau debounce, 
// atau trigger callback HANYA pada gesture onEnd/completion callback.
```

### 3. Merender Nilai SharedValue Langsung sebagai Text Node
```typescript
// SALAH (Menyebabkan crash atau render kosong):
const counter = useSharedValue(0);
return <Text>{counter.value}</Text>; // Reanimated SharedValue bukan React State!

// BENAR:
// Gunakan createAnimatedComponent atau useDerivedValue + AnimatedText wrapper
import { TextInput } from 'react-native';
const AnimatedTextInput = Animated.createAnimatedComponent(TextInput);
// Ikat via native props menggunakan useAnimatedProps
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Strictly Compositor-Targeted Properties**: Hanya animasikan properti GPU-friendly: `transform` (translasi, skala, rotasi) dan `opacity`. Jika terpaksa mengubah dimensi, interpolasikan matriks transformasi skala ($Scale_X, Scale_Y$) alih-alih `width` dan `height`.
2. **Kompilasi Deklaratif Bersih**: Pastikan Babel plugin `'react-native-reanimated/plugin'` diletakkan pada posisi paling akhir (paling bawah) dari daftar plugin di `babel.config.js`. Urutan ini mutlak agar AST transformation dapat menangkap fungsi worklet sebelum transformer lain memodifikasinya.
3. **Immutabilitas Konfigurasi Pegas**: Deklarasikan `springConfig` di luar render cycle komponen atau bungkus menggunakan `useMemo` untuk mencegah alokasi objek repetitif di setiap siklus render React.
4. **Isolasi Node Handler Root**: Pastikan `<GestureHandlerRootView>` hanya dibungkus sekali pada root aplikasi (`App.tsx` atau root layout), bukan di setiap sub-komponen layar untuk mencegah pembuatan multiple native event multiplexer.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Mencegah GC Spikes pada 120Hz Displays
Pada display 120Hz (refresh rate 8.33ms), alokasi array dan objek anonim di dalam callback `useAnimatedStyle` atau `onUpdate` akan membebani engine garbage collector Hermes di UI Thread.

```typescript
// TIDAK OPTIMAL (Alokasi objek dan array baru terjadi setiap 8.33ms):
const animatedStyle = useAnimatedStyle(() => {
  'worklet';
  // Array [ { translateX: ... } ] dialokasikan kembali setiap frame!
  return {
    transform: [{ translateX: x.value }, { translateY: y.value }],
  };
});

// SANGAT OPTIMAL (Ekstraksi properti skalar, layout engine re-uses memory references):
// Pada Reanimated v3, gunakan objek transformasi terindeks jika dimungkinkan,
// dan hindari kalkulasi trigonometri/aljabar kompleks di useAnimatedStyle.
// Lakukan pre-komputasi di useDerivedValue.
const derivedTransform = useDerivedValue(() => {
  'worklet';
  return [
    { translateX: x.value },
    { translateY: y.value }
  ];
});

const animatedStyle = useAnimatedStyle(() => {
  'worklet';
  return {
    transform: derivedTransform.value,
  };
});
```

### JSI Memory Retention Checks
Ketika komponen yang memiliki worklet di-unmount, pastikan semua referensi `SharedValue` yang diakses di level modul luar dibersihkan. Hindari menyimpan `SharedValue` di singleton class global karena `ShareableValue` C++ akan menahan instance JS engine context dan mencegah pengumpulan memori saat komponen dilepas.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Worklet Context Injection Protection**: Jangan pernah mengevaluasi string runtime dinamis ke dalam worklet (hindari `eval` atau `new Function`). Input string dari remote server (misalnya payload push notification) tidak boleh diinterpretasikan secara langsung sebagai fungsi animasi.
2. **Gesture Spoofing & Tapjacking**: Pada view interaktif yang melakukan otorisasi finansial (misal: "Slide to Confirm Transaction"):
   * Validasi jarak translasi kumulatif minimal secara native.
   * Pastikan `hitSlop` didefinisikan secara ketat agar area transparan di luar elemen UI tidak dapat diintersepsi oleh overlay