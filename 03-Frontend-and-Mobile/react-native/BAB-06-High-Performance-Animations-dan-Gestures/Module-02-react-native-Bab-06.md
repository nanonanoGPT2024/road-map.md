# Kurikulum Enterprise React Native
## Kategori: 03-Frontend-and-Mobile
### BAB-06: High-Performance Animations & Gestures
### MODUL 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, tech lead dan mobile engineer tingkat lanjut diharapkan mampu:
- Menguasai arsitektur internal runtime Reanimated v3 (Hermes secondary runtime, JSI bindings, Shareables, dan Worklets compiler transformation).
- Merancang dan mengorkestrasi sistem interaksi gestur multi-layer yang kompleks menggunakan React Native Gesture Handler (RNGH) v2 API (`Gesture.Pan`, `Gesture.Pinch`, `Gesture.Simultaneous`, `Gesture.Race`).
- Menghilangkan *frame drops* (jank) dengan memindahkan 100% beban komputasi interpolasi, tracking gestur, dan mutasi state visual langsung ke UI Thread tanpa melewati React render lifecycle.
- Mengintegrasikan mekanisme animasi dengan New Architecture React Native (Fabric C++ Core dan TurboModules) secara efisien tanpa menyebabkan UI Thread starvation.
- Melakukan profil memori, deteksi *memory leak* pada shareable references, dan pelacakan *micro-stutter* menggunakan Hermes CPU Profiler dan platform-native tools (Systrace/Perfetto/Instruments).

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda wajib memahami:
- Siklus render React Native, React 18 Concurrent Features, dan New Architecture (Fabric, Yoga layout engine, JSI basics).
- Dasar Reanimated v3: `useSharedValue`, `useAnimatedStyle`, `withTiming`, `withSpring`.
- Dasar React Native Gesture Handler: Integrasi dasar `GestureDetector` dan `GestureHandlerRootView`.
- Konsep thread computing: Main/UI Thread (Android Choreographer / iOS CADisplayLink), JavaScript Thread, Shadow Thread.
- TypeScript level lanjut: Generics, type inference, dan typing worklets.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Dual-Runtime Architecture & Worklets Internals
Pada React Native standar dengan New Architecture, aplikasi berjalan di atas Hermes JavaScript Engine. Namun, Reanimated menginstansiasi sebuah **Hermes Runtime kedua yang terisolasi khusus di UI Thread** (sering disebut *Reanimated UI Runtime*).

```
+-----------------------------------------------------------------------+
|                           NATIVE APPLICATION                          |
|                                                                       |
|  +---------------------------+       +-----------------------------+  |
|  |    React JS Runtime       |       |    Reanimated UI Runtime    |  |
|  |      (Main Thread)        |       |         (UI Thread)         |  |
|  |                           |       |                             |  |
|  | - React Components        |       | - Worklets Execution Engine |  |
|  | - Business Logic          |       | - Gesture Responders        |  |
|  | - Network / Storage       |       | - Physics / Interpolation   |  |
|  | - State Management        |       |                             |  |
|  +-------------+-------------+       +--------------+--------------+  |
|                |                                    |                 |
|                |              JSI Layer             |                 |
|                +====================================+                 |
|                                  |                                    |
|                   +--------------v--------------+                     |
|                   |  Shareable Values Registry  |                     |
|                   |  (C++ Host Objects / JSI)   |                     |
|                   +--------------+--------------+                     |
|                                  |                                    |
|                                  v                                    |
|                   +-----------------------------+                     |
|                   |   Fabric Component Core     |                     |
|                   |   (Direct ShadowNode Mut.)  |                     |
|                   +--------------+--------------+                     |
|                                  |                                    |
|                                  v                                    |
|                   +-----------------------------+                     |
|                   |    OS Compositor (60/120Hz) |                     |
|                   |  Android SurfaceFlinger /   |                     |
|                   |      Apple CoreAnimation    |                     |
|                   +-----------------------------+                     |
+-----------------------------------------------------------------------+
```

1. **Babel Plugin Transformation**:
   Ketika fungsi ditandai dengan direktif `'worklet';`, Babel plugin Reanimated (`react-native-reanimated/plugin`) mengekstrak fungsi tersebut, menghasilkan closure data structure, menetapkan hash unik (`__workletHash`), dan mengubah referensi variabel luar (lexical scope) menjadi mekanisme capture eksplisit:
   ```javascript
   // Source Code
   function customWorklet(val) {
     'worklet';
     return val * 2;
   }

   // Transformed Output (Konseptual)
   var customWorklet = (function () {
     var _f = function (val) {
       return val * 2;
     };
     _f._closure = {};
     _f.__initData = {
       code: "function customWorklet(val){return val*2;}",
       hash: 2894719284
     };
     _f.__workletHash = 2894719284;
     return _f;
   })();
   ```
2. **JSI (JavaScript Interface) & Shareables**:
   Primitive values, functions, dan object yang berpindah antara Main JS Runtime dan UI Runtime dibungkus ke dalam **C++ `ShareableValue`**. 
   - `useSharedValue(initialValue)` membuat host object C++ yang menyimpan pointer memori ke data tersebut.
   - Mutasi `.value` di UI thread membaca/menulis memori JSI C++ secara sinkron tanpa serialisasi JSON, tanpa batasan bridge asynchronous, dan tanpa memicu re-render siklus React.
3. **Fabric Shadow Tree Direct Mutation**:
   Dalam Fabric (New Architecture), `useAnimatedStyle` tidak mengirim prop update kembali ke React Reconciliation. Sebaliknya, Reanimated langsung berinteraksi dengan Fabric C++ Core API (`NativeReanimatedModule::setNativeProps`) untuk memperbarui state `ShadowNode` lokal atau menginjeksi properti mutasi langsung ke platform-native views (Surface/UIView) sebelum frame dirender oleh Choreographer (Android) atau CADisplayLink (iOS).

#### 3.2 RNGH v2 State Machine & Event Interception
RNGH memotong stream sentuhan native OS sebelum mencapai sistem responder React Native standar.
- **Android**: Mengintersepsi `MotionEvent` via wrapper ViewGroup root (`RNGHRootView`) dengan meng-override method `onInterceptTouchEvent` dan `dispatchTouchEvent`.
- **iOS**: Memanfaatkan subclass `UIGestureRecognizer` native yang berjalan langsung di sub-layer UIKit.
- **RNGH v2 Architecture**: Menggunakan *Fluent API* (`Gesture.Pan()`, `Gesture.Tap()`) yang merepresentasikan konfigurator deklaratif di C++ layer. Ketika gestur aktif, RNGH mengeksekusi worklet handler langsung di UI Runtime via direct JSI call, menjamin responsivitas sentuhan dengan latensi 0-frame (sub-millisecond).

---

### 4. Why & What

| Dimensi | Legacy Animated API (React Native Core) | Reanimated v3 + RNGH v2 |
| :--- | :--- | :--- |
| **Execution Thread** | Bergantung pada konfigurasi (`useNativeDriver: true` terbatas pada transform & opacity; non-transform berjalan di JS Thread). | **100% UI Thread** untuk interpolasi, perhitungan gestur, physics engine, dan layout updates. |
| **Data Synchronization** | Asynchronous JSON message passing melalui React Native Bridge (atau asynchronous batch update di Fabric). | **Synchronous Direct Memory Access** via C++ JSI Shareables across dual runtimes. |
| **Gesture Coordination** | Membutuhkan transisi state JS (`PanResponder`), menyebabkan frame-drop saat JS Thread sibuk (heavy business logic, rendering list). | **Native Interception + UI Worklet Handling**. Gestur tetap halus (120 FPS) meskipun JS thread 100% saturated. |
| **Layout Animations** | Sangat terbatas, rawan layout flickering, membutuhkan layout measure async (`UIManager.measure`). | Native **Layout Animations Engine** (Entering/Exiting/Layout Transitions) dikomputasi sinkron di C++. |
| **Dev Velocity & Safety** | API deklaratif kaku, parsing kompleks, race condition tinggi pada interaksi kompleks. | Type-safe Fluent API, First-class TypeScript support, shared state composability. |

---

### 5. How (Workflow Detail)

Alur eksekusi dari input sentuhan layar hingga visual compositing:

```
[OS Touch Controller]
        |
        v (Raw MotionEvent / TouchEvent)
[Native View Root (Android/iOS Window)]
        |
        v (Interception hook)
[RNGH Native C++ Event Interceptor]
        |
        |--- (Evaluate Gesture State: UNDETERMINED -> BEGAN -> ACTIVE)
        v
[Reanimated UI Runtime (Hermes secondary runtime on UI Thread)]
        |
        |--- 1. Eksekusi Worklet Handler: gesture.onUpdate((e) => { ... })
        |--- 2. Sinkronisasi SharedValue: translationX.value = e.translationX
        |--- 3. Evaluasi Dependensi: useAnimatedStyle menghitung diff matrix
        |--- 4. Eksekusi Engine Physics: withSpring / withDecay recalculation
        v
[JSI Native C++ Core (NativeReanimatedModule)]
        |
        v (Direct mutation via Fabric C++ ShadowNode or Platform View)
[Platform UI Framework (Render Node / CoreAnimation Layer)]
        |
        v (V-Sync pulse from Choreographer / CADisplayLink)
[Display Hardware (Output Frame: 60/120Hz)]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Menara Pengawas Bandara vs. Pilot di Kokpit
- **Legacy Approach (JS Thread Animations)**: Setiap penyesuaian kemudi pesawat (posisi jari di layar) harus dikirim lewat radio ke Menara Pengawas Pusat (JS Thread). Menara pengawas sedang sibuk memproses ratusan log kargo (state management, API payload parsing). Setelah 5 detik tertunda, menara mengizinkan belok. Akibatnya: Pesawat mengalami turbulensi hebat (*frame drop/jank*).
- **Modern Reanimated + RNGH Approach (Worklets on UI Thread)**: Pilot di kokpit (UI Runtime) memiliki kendali langsung dan otonom atas sirip sayap pesawat. Pilot melihat perubahan angin (input gestur) dan langsung memutar kemudi secara real-time. Menara Pengawas Pusat hanya menerima laporan ringkas *setelah* pesawat mendarat (`runOnJS`). Hasilnya: Penerbangan mulus sempurna pada 120 FPS.

#### Diagram Interaksi State Machine RNGH & Reanimated UI Thread

```
+-----------------------------------------------------------------------------+
|                          GESTURE STATE MACHINE                              |
|                                                                             |
|      [ UNDETERMINED ]  --- Touch Detected ---> [ BEGAN ]                    |
|             ^                                      |                        |
|             | (Fail threshold)                     | (Pass threshold)       |
|             +--------------------------------------+                        |
|             |                                      v                        |
|        [ FAILED ]                             [ ACTIVE ]                    |
|             ^                                      |                        |
|             | (Interrupted)                        | (Finger Lifted)        |
|             +--------------------------------------+                        |
|                                                    v                        |
|                                                [ END ]                      |
+-----------------------------------------------------------------------------+
                                     |
               Event disalurkan via JSI ke UI Thread
                                     v
+-----------------------------------------------------------------------------+
|                     REANIMATED UI THREAD RUNTIME                            |
|                                                                             |
|  .onBegin()   ---> Capture start position (Context Object)                  |
|  .onUpdate()  ---> Mutasi SharedValue secara sinkron (60/120 FPS)           |
|  .onEnd()     ---> Trigger withSpring / withDecay physics computation        |
|  .onFinalize()---> Cleanup / Release memory / Reset locks                   |
|                                                                             |
|                        useAnimatedStyle Evaluation                          |
|    Output: Direct C++ Transform Matrix Mutation (Translate, Scale, Rotate)  |
+-----------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: High-Performance Swipable Card (Pure Worklet)

```typescript
import React from 'react';
import { StyleSheet, View, Text } from 'react-native';
import { GestureDetector, Gesture, GestureHandlerRootView } from 'react-native-gesture-handler';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  runOnJS,
} from 'react-native-reanimated';

const SWIPE_THRESHOLD = 120;

export const SimpleSwipeCard: React.FC<{ onDismiss: () => void }> = ({ onDismiss }) => {
  const translateX = useSharedValue(0);
  const isInteracting = useSharedValue(false);

  const panGesture = Gesture.Pan()
    .onBegin(() => {
      'worklet';
      isInteracting.value = true;
    })
    .onUpdate((event) => {
      'worklet';
      translateX.value = event.translationX;
    })
    .onEnd(() => {
      'worklet';
      if (Math.abs(translateX.value) > SWIPE_THRESHOLD) {
        const dest = Math.sign(translateX.value) * 500;
        translateX.value = withTiming(dest, { duration: 200 }, (finished) => {
          if (finished) {
            runOnJS(onDismiss)();
          }
        });
      } else {
        translateX.value = withSpring(0, { damping: 15, stiffness: 120 });
      }
    })
    .onFinalize(() => {
      'worklet';
      isInteracting.value = false;
    });

  const animatedStyle = useAnimatedStyle(() => {
    return {
      transform: [
        { translateX: translateX.value },
        { scale: isInteracting.value ? 1.05 : 1 },
      ],
      opacity: withTiming(Math.abs(translateX.value) > 200 ? 0 : 1, { duration: 100 }),
    };
  });

  return (
    <GestureDetector gesture={panGesture}>
      <Animated.View style={[styles.card, animatedStyle]}>
        <Text style={styles.cardText}>Swipe Me Left or Right</Text>
      </Animated.View>
    </GestureDetector>
  );
};

const styles = StyleSheet.create({
  card: {
    width: 300,
    height: 120,
    backgroundColor: '#1E293B',
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 5,
    shadowColor: '#000',
    shadowOpacity: 0.2,
    shadowRadius: 8,
  },
  cardText: {
    color: '#F8FAFC',
    fontWeight: '600',
    fontSize: 16,
  },
});
```

#### 7.2 Practical Example: Enterprise Pan-Zoom-Rotate Canvas dengan Matrix Decomposition

```typescript
import React from 'react';
import { StyleSheet, View, Dimensions } from 'react-native';
import {
  GestureDetector,
  Gesture,
  GestureHandlerRootView,
} from 'react-native-gesture-handler';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withDecay,
  withSpring,
} from 'react-native-reanimated';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

export const EnterpriseTransformViewer: React.FC = () => {
  // Shared transformations
  const translationX = useSharedValue<number>(0);
  const translationY = useSharedValue<number>(0);
  const prevTranslationX = useSharedValue<number>(0);
  const prevTranslationY = useSharedValue<number>(0);

  const scale = useSharedValue<number>(1);
  const startScale = useSharedValue<number>(1);

  const rotation = useSharedValue<number>(0);
  const startRotation = useSharedValue<number>(0);

  // Gesture 1: Pinch (Zoom)
  const pinchGesture = Gesture.Pinch()
    .onStart(() => {
      'worklet';
      startScale.value = scale.value;
    })
    .onUpdate((event) => {
      'worklet';
      // Clamping scale between 0.5x and 4x
      scale.value = Math.min(Math.max(startScale.value * event.scale, 0.5), 4);
    })
    .onEnd(() => {
      'worklet';
      if (scale.value < 1) {
        scale.value = withSpring(1, { damping: 15, stiffness: 150 });
      }
    });

  // Gesture 2: Rotation
  const rotationGesture = Gesture.Rotation()
    .onStart(() => {
      'worklet';
      startRotation.value = rotation.value;
    })
    .onUpdate((event) => {
      'worklet';
      rotation.value = startRotation.value + event.rotation;
    });

  // Gesture 3: Pan with Inertial Decay
  const panGesture = Gesture.Pan()
    .averageTouches(true)
    .onStart(() => {
      'worklet';
      prevTranslationX.value = translationX.value;
      prevTranslationY.value = translationY.value;
    })
    .onUpdate((event) => {
      'worklet';
      translationX.value = prevTranslationX.value + event.translationX;
      translationY.value = prevTranslationY.value + event.translationY;
    })
    .onEnd((event) => {
      'worklet';
      // Momentum decay computation executed direct on UI Thread
      translationX.value = withDecay({
        velocity: event.velocityX,
        clamp: [-SCREEN_WIDTH, SCREEN_WIDTH],
      });
      translationY.value = withDecay({
        velocity: event.velocityY,
        clamp: [-SCREEN_HEIGHT / 2, SCREEN_HEIGHT / 2],
      });
    });

  // Compose Gestures to execute simultaneously without race conditions
  const composedGesture = Gesture.Simultaneous(
    panGesture,
    Gesture.Simultaneous(pinchGesture, rotationGesture)
  );

  const animatedStyle = useAnimatedStyle(() => {
    'worklet';
    return {
      transform: [
        { translateX: translationX.value },
        { translateY: translationY.value },
        { scale: scale.value },
        { rotateZ: `${rotation.value}rad` },
      ],
    };
  });

  return (
    <GestureHandlerRootView style={styles.container}>
      <GestureDetector gesture={composedGesture}>
        <Animated.View style={[styles.box, animatedStyle]} />
      </GestureDetector>
    </GestureHandlerRootView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F172A',
    justifyContent: 'center',
    alignItems: 'center',
    overflow: 'hidden',
  },
  box: {
    width: 250,
    height: 250,
    backgroundColor: '#38BDF8',
    borderRadius: 24,
    borderWidth: 2,
    borderColor: '#E2E8F0',
  },
});
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Interactive Production Bottom Sheet dengan Physics Snapping, Dynamic Backdrop Blur, & Scroll Collision

Di aplikasi Super-App (Ride Hailing & Fintech), bottom sheet sering kali crash, bergetar saat scroll (scroll-clash), atau mengalami frame-drop saat map view dirender di latar belakang bersamaan dengan gestur sheet.

```typescript
import React, { forwardRef, useImperativeHandle } from 'react';
import { StyleSheet, View, Dimensions, LayoutChangeEvent } from 'react-native';
import {
  GestureDetector,
  Gesture,
} from 'react-native-gesture-handler';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  interpolate,
  Extrapolation,
  runOnJS,
} from 'react-native-reanimated';

const { height: SCREEN_HEIGHT } = Dimensions.get('window');

interface BottomSheetProps {
  snapPoints: number[]; // e.g., [-100, -300, -600]
  initialSnapIndex?: number;
  onSnapChange?: (index: number) => void;
  children: React.ReactNode;
}

export interface BottomSheetRef {
  snapTo: (index: number) => void;
  close: () => void;
}

const SPRING_CONFIG = {
  damping: 20,
  stiffness: 150,
  mass: 0.8,
  overshootClamping: false,
  restDisplacementThreshold: 0.1,
  restSpeedThreshold: 0.1,
};

export const EnterpriseBottomSheet = forwardRef<BottomSheetRef, BottomSheetProps>(
  ({ snapPoints, initialSnapIndex = 0, onSnapChange, children }, ref) => {
    // Current translation along Y axis. 0 is closed (offscreen).
    const translateY = useSharedValue<number>(snapPoints[initialSnapIndex] ?? 0);
    const contextY = useSharedValue<number>(0);

    const handleSnapChange = (index: number) => {
      if (onSnapChange) {
        onSnapChange(index);
      }
    };

    useImperativeHandle(ref, () => ({
      snapTo: (index: number) => {
        'worklet';
        const target = snapPoints[index];
        if (target !== undefined) {
          translateY.value = withSpring(target, SPRING_CONFIG);
          if (onSnapChange) {
            runOnJS(handleSnapChange)(index);
          }
        }
      },
      close: () => {
        'worklet';
        translateY.value = withSpring(0, SPRING_CONFIG);
      },
    }));

    const panGesture = Gesture.Pan()
      .onStart(() => {
        'worklet';
        contextY.value = translateY.value;
      })
      .onUpdate((event) => {
        'worklet';
        const nextPosition = contextY.value + event.translationY;
        const maxSnap = Math.min(...snapPoints); // Paling tinggi (nilai negatif terbesar)
        
        // Resistance effect when pulling beyond top threshold
        if (nextPosition < maxSnap) {
          const overflow = nextPosition - maxSnap;
          translateY.value = maxSnap + overflow * 0.2; // Rubber-band effect
        } else {
          translateY.value = nextPosition;
        }
      })
      .onEnd((event) => {
        'worklet';
        const projectedTarget = translateY.value + event.velocityY * 0.15;
        
        // Find closest snap point based on trajectory + position
        let closestSnap = snapPoints[0];
        let minDistance = Math.abs(projectedTarget - closestSnap);
        let selectedIndex = 0;

        for (let i = 1; i < snapPoints.length; i++) {
          const distance = Math.abs(projectedTarget - snapPoints[i]);
          if (distance < minDistance) {
            minDistance = distance;
            closestSnap = snapPoints[i];
            selectedIndex = i;
          }
        }

        translateY.value = withSpring(closestSnap, SPRING_CONFIG, (finished) => {
          if (finished && onSnapChange) {
            runOnJS(handleSnapChange)(selectedIndex);
          }
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
      const maxRange = Math.min(...snapPoints);
      const opacity = interpolate(
        translateY.value,
        [0, maxRange],
        [0, 0.6],
        Extrapolation.CLAMP
      );
      return {
        opacity,
        display: opacity === 0 ? 'none' : 'flex',
      };
    });

    return (
      <>
        <Animated.View style={[styles.backdrop, backdropAnimatedStyle]} pointerEvents="none" />
        <GestureDetector gesture={panGesture}>
          <Animated.View style={[styles.sheetContainer, sheetAnimatedStyle]}>
            <View style={styles.indicatorContainer}>
              <View style={styles.indicator} />
            </View>
            {children}
          </Animated.View>
        </GestureDetector>
      </>
    );
  }
);

const styles = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#000000',
    zIndex: 10,
  },
  sheetContainer: {
    position: 'absolute',
    top: SCREEN_HEIGHT,
    left: 0,
    right: 0,
    height: SCREEN_HEIGHT,
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    zIndex: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 10,
  },
  indicatorContainer: {
    width: '100%',
    alignItems: 'center',
    paddingVertical: 12,
  },
  indicator: {
    width: 40,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: '#CBD5E1',
  },
});
```

---

### 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Kerugian & Batasan | Rekomendasi Kasus Penggunaan |
| :--- | :--- | :--- | :--- |
| **`useAnimatedStyle` dengan Direct Matrix Mutation** | Zero re-render cycle; performa stabil di 120 FPS; memory allocation sangat minim. | Debugging profiling kompleks; tidak dapat mengupdate layout sibling component di React tree secara otomatis. | Semua interaksi dragging, pinching, sheet opening, dan card dismissing. |
| **Layout Animations (`FadeIn`, `LinearTransition`)** | Native C++ layout calculations; tidak ada flicker pada dynamic list; deklaratif. | Kurang fleksibel jika animasi membutuhkan koordinasi eksternal berbasis gestur fisik secara dinamis. | List insertion, item deletion, expand/collapse accordions. |
| **`runOnJS` Callbacks** | Memberikan feedback data native UI ke domain state React / Redux / Zustand. | Overuse menyebabkan thread hops; jika payload besar, serialisasi JSI memakan memory bus; micro-jank bila JS thread lambat. | Eksekusi analytics event, haptic trigger confirmation, navigation trigger di akhir animasi. |
| **Simultaneous Gestures Composition** | Memungkinkan interaksi paralel tingkat tinggi (zoom + pan + rotate serentak). | Kompleksitas penanganan pointer hit testing; konsumsi resource meningkat bila multi-touch mencapai > 4 titik sentuh. | Map navigation, canvas painting tools, image crop manipulation. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Closure Variable Capture Trap
*Penyebab*: Mencoba memodifikasi JavaScript variable lokal biasa dari dalam worklet UI thread.
```typescript
// FATAL CODE:
let localCounter = 0;
const pan = Gesture.Pan().onUpdate(() => {
  'worklet';
  localCounter++; // Error atau tidak berdampak ke JS scope!
});
```
*Solusi*: Gunakan `useSharedValue` untuk state primitif lintas runtime, atau kirim mutasi lewat `runOnJS`.

#### 10.2 Synchronous Blocking Inside Worklet
*Penyebab*: Menjalankan algoritma loop `O(n^2)` atau komputasi kriptografi/JSON stringify di dalam block worklet. Hal ini akan langsung mem-freeze UI thread, memicu Android ANR (Application Not Responding) atau iOS Watchdog termination.
*Solusi*: Jaga worklet tetap linear `O(1)`: hanya kalkulasi formula interpolasi, update koordinat, dan passing transformasi. Pindahkan heavy parsing ke JS background workers via web workers / TurboModules C++.

#### 10.3 Missing `GestureHandlerRootView`
*Penyebab*: Gesture tidak merespons di Android atau crash saat start.
*Solusi*: Pastikan `GestureHandlerRootView` dibungkus pada root tree aplikasi (misalnya pada `App.tsx` atau root layout wrapper), dengan styling `{ flex: 1 }`.

#### 10.4 Mengakses `.value` di Render Body
*Penyebab*:
```typescript
const App = () => {
  const x = useSharedValue(0);
  return <Text>{x.value}</Text>; // Tidak akan re-render saat x.value berubah!
}
```
*Solusi*: Gunakan komponen pembungkus Reanimated seperti `AnimatedTextInput` atau binding melalui `useAnimatedProps`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Worklet Purity**: Pastikan semua callbacks gestur (`onStart`, `onUpdate`, `onEnd`, `onFinalize`) secara eksplisit memiliki tag `'worklet';` jika dipisahkan ke dalam utility functions mandiri.
- [ ] **Thread Decoupling**: Jangan pernah memanggil `setState` React langsung di `onUpdate` gestur. Lakukan state bridge hanya pada fase `onEnd` atau `onFinalize` via `runOnJS`.
- [ ] **Matrix Transformations**: Prioritaskan memanipulasi `transform` (`translateX`, `translateY`, `scale`, `rotate`) dan `opacity`. Hindari menganimasikan properti layout langsung (`width`, `height`, `top`, `left`, `margin`) karena memicu sinkronisasi reflow layout engine Yoga yang berat di Shadow Tree.
- [ ] **Spring Dynamics Optimization**: Gunakan parameter `damping` dan `stiffness` terukur. Pastikan mendefinisikan `restDisplacementThreshold: 0.01` dan `restSpeedThreshold: 2` agar spring engine cepat memasuki status idle (menghemat clock siklus CPU & baterai).
- [ ] **Hit Slop Control**: Atur `hitSlop` pada touch targets untuk memperluas boundary area interaksi tanpa memperbesar view hierarchy layout.
- [ ] **Memory Leak Auditing**: Hapus reference event emitter dan batalkan animasi (`cancelAnimation(sharedValue)`) pada *unmount* lifecycle component (`useEffect` cleanup).

---

### 12. Hands-on Practice

Buat direktori baru dan implementasikan interactive dismissable list item dengan feedback haptics dan destructive visual trigger.

#### File: `hands-on/m02/InteractiveItem.tsx`

```typescript
import React from 'react';
import { StyleSheet, Text, View, Dimensions } from 'react-native';
import { GestureDetector, Gesture } from 'react-native-gesture-handler';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  runOnJS,
  interpolate,
  Extrapolation,
} from 'react-native-reanimated';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const THRESHOLD = -SCREEN_WIDTH * 0.3;

interface Props {
  id: string;
  title: string;
  onDelete: (id: string) => void;
}

export const InteractiveItem: React.FC<Props> = ({ id, title, onDelete }) => {
  const translateX = useSharedValue(0);
  const itemHeight = useSharedValue(70);
  const opacity = useSharedValue(1);

  const triggerDelete = () => {
    onDelete(id);
  };

  const panGesture = Gesture.Pan()
    .activeOffsetX([-10, 10])
    .onUpdate((event) => {
      'worklet';
      // Hanya izinkan swipe ke kiri
      if (event.translationX < 0) {
        translateX.value = event.translationX;
      }
    })
    .onEnd(() => {
      'worklet';
      if (translateX.value < THRESHOLD) {
        // Slide out to the left
        translateX.value = withTiming(-SCREEN_WIDTH, { duration: 200 }, (finished) => {
          if (finished) {
            // Collapse height and fade
            itemHeight.value = withTiming(0, { duration: 150 });
            opacity.value = withTiming(0, { duration: 150 }, (closed) => {
              if (closed) {
                runOnJS(triggerDelete)();
              }
            });
          }
        });
      } else {
        // Reset position
        translateX.value = withSpring(0, { damping: 15 });
      }
    });

  const animatedContentStyle = useAnimatedStyle(() => {
    'worklet';
    return {
      transform: [{ translateX: translateX.value }],
    };
  });

  const animatedContainerStyle = useAnimatedStyle(() => {
    'worklet';
    return {
      height: itemHeight.value,
      opacity: opacity.value,
      marginBottom: itemHeight.value === 0 ? 0 : 8,
    };
  });

  const deleteActionStyle = useAnimatedStyle(() => {
    'worklet';
    const iconScale = interpolate(
      translateX.value,
      [THRESHOLD, THRESHOLD - 40],
      [0.8, 1.2],
      Extrapolation.CLAMP
    );
    return {
      transform: [{ scale: iconScale }],
    };
  });

  return (
    <Animated.View style={[styles.container, animatedContainerStyle]}>
      <View style={styles.deleteBackground}>
        <Animated.Text style={[styles.deleteText, deleteActionStyle]}>
          DELETE
        </Animated.Text>
      </View>
      <GestureDetector gesture={panGesture}>
        <Animated.View style={[styles.content, animatedContentStyle]}>
          <Text style={styles.title}>{title}</Text>
        </Animated.View>
      </GestureDetector>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    width: '100%',
    overflow: 'hidden',
  },
  deleteBackground: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#EF4444',
    justifyContent: 'center',
    alignItems: 'flex-end',
    paddingRight: 24,
    borderRadius: 12,
  },
  deleteText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 14,
  },
  content: {
    flex: 1,
    backgroundColor: '#1E293B',
    borderRadius: 12,
    justifyContent: 'center',
    paddingHorizontal: 20,
    borderWidth: 1,
    borderColor: '#334155',
  },
  title: {
    color: '#F8FAFC',
    fontSize: 16,
    fontWeight: '500',
  },
});
```

---

### 13. Exercise

#### Level: Easy
Implementasikan interaksi tombol tap berbasis `Gesture.Tap()` menggunakan Reanimated yang memicu efek haptic feedback (via native helper) dan kompresi skala visual (`scale: 0.95`) dengan spring rebound tanpa menggunakan `TouchableOpacity` bawaan.
- *Kriteria Evaluasi*: Tidak ada rendering ulang komponen saat ditekan; visual transformasi berlangsung di UI thread.

#### Level: Medium
Buat komponen Floating Action Button (FAB) yang dapat didrag secara bebas ke seluruh penjuru layar (`Gesture.Pan()`). Saat user melepas jari, tombol harus secara otomatis meluncur (snapping) ke sisi pinggir layar terdekat (kiri atau kanan) dengan kalkulasi `withDecay` yang bertransisi halus ke `withSpring`.
- *Kriteria Evaluasi*: Memperhitungkan safe-area insets; perhitungan kalkulasi snapping terdekat dilakukan murni di dalam worklet.

#### Level: Hard
Bangun komponen Dual-Thumb Range Slider sepenuhnya dari scratch. Dua pointer thumb harus dapat digeser bersamaan (multi-touch tracking) tanpa saling tumpang-tindih melampaui batas thumb lainnya.
- *Kriteria Evaluasi*: Koordinasi dilakukan via `Gesture.Simultaneous`; posisi thumb tidak boleh desinkronisasi; komputasi range persentase (0% - 100%) dikirimkan ke state parent hanya ketika gestur berakhir.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Mobile Architect di platform broker saham global. Desain dan bangun sebuah **Real-time Interactive Stock Chart Scrubber Canvas**.
- **Kebutuhan Teknis**:
  1. Chart berupa garis data points (1000 data points).
  2. Ketika user melakukan *Long Press* lalu *Drag* di layar, kursor scrubbing vertikal muncul dan mengikuti posisi jari secara instan (120 FPS target).
  3. Indikator harga pada kursor harus menginterpolasi data terdekat dari array `SharedValue` berukuran 1000 elemen tanpa serialisasi ulang ke JS Thread.
  4. Ketika user mencubit layar (*Pinch*), skala horizontal rentang waktu chart mengembang (zoom in) dan mengecil (zoom out), di mana titik pivot zoom berada tepat di antara dua jari user.
  5. Seluruh kalkulasi matriks data coordinate transform dan hit testing pointer wajib berjalan di Reanimated Secondary UI Runtime.
- **Batasan**: Tidak boleh menggunakan library third-party chart (seperti victory-native atau react-native-svg charts) untuk rendering interaktifnya; interaksi scrubber harus diimplementasikan murni menggunakan `react-native-gesture-handler` v2 dan `react-native-reanimated` v3 primitives.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Apa fungsi dari direktif `'worklet';` pada Reanimated v3?
   - *Jawaban*: Memberikan instruksi ke Babel plugin Reanimated untuk mengompilasi dan mentransformasi fungsi tersebut menjadi unit kode yang mandiri, dapat diserialisasi ke C++, dan dapat dieksekusi secara independen di Reanimated UI Runtime.
2. Mengapa Reanimated v3 jauh lebih unggul dibandingkan React Native Animated API native driver saat menangani gestur dinamis?
   - *Jawaban*: Karena Native Driver bawaan React Native hanya mendukung animasi yang predefined (dikirim diawal), sedangkan gesture handling real-time mengharuskan pemrosesan continuous loop yang pada Animated API fallback ke JS Thread. Reanimated mengeksekusi continuous loop gestur secara native di UI Thread.
3. Apa perbedaan fundamental antara `runOnJS` dan `runOnUI`?
   - *Jawaban*: `runOnJS` digunakan untuk menjadwalkan eksekusi fungsi reguler pada Main JavaScript Thread dari dalam UI Runtime/worklet, sedangkan `runOnUI` menjadwalkan fungsi worklet untuk dieksekusi di UI Thread dari JavaScript thread.
4. Apa kegunaan utama dari method `.simultaneousWithExternalGesture()` pada RNGH v2?
   - *Jawaban*: Memungkinkan gesture recognizer berjalan secara paralel dengan gestur lain (seperti native `ScrollView` scroll gesture) tanpa saling membatalkan satu sama lain.
5. Apa konsekuensi teknis jika memanggil state setter React (misal `setValue(...)`) di dalam callback `Gesture.Pan().onUpdate()`?
   - *Jawaban*: Menimbulkan bottleneck drastis berupa jank dan frame-drop, karena memaksa React melakukan reconciliation dan re-render cycle hingga 60-120 kali per detik di Main JavaScript Thread.

#### 5 Pertanyaan Intermediate
6. Bagaimana cara kerja internal transmisi memori `ShareableValue` antara Hermes JS Engine utama dan UI Thread Hermes Runtime?
   - *Jawaban*: Nilai dialokasikan pada memori C++ Heap via JSI Host Objects. Pointer memori dibagikan langsung ke kedua runtime tanpa serialisasi JSON, memungkinkan thread membaca dan menulis mutasi secara atomic thread-safe.
7. Mengapa pengubahan properti `transform` jauh lebih optimal performanya dibandingkan menginterpolasi properti `width` atau `height` pada `useAnimatedStyle`?
   - *Jawaban*: `transform` diproses langsung oleh GPU/Compositor platform native tanpa memicu reflow layout recalculation pada Yoga Layout Engine. Sebaliknya, mutasi `width`/`height` memicu recalculation traversal pada seluruh subtree Fabric Shadow Nodes.
8. Bagaimana strategi mencegah tabrakan gestur horizontal swipe-to-dismiss dengan native parent navigasi (seperti iOS swipe-back navigation gesture)?
   - *Jawaban*: Menggunakan modifier `activeOffsetX` untuk memberikan ambang batas threshold geseran sebelum gestur mengklaim kepemilikan touch event, atau menggunakan `Gesture.Race` / dependensi eksplisit via `requireExternalGestureToFail()`.
9. Apa yang terjadi jika referensi non-worklet closure (seperti variable lokal module) diakses di dalam worklet?
   - *Jawaban*: Babel plugin mencoba meng-copy nilai tersebut ke dalam metadata object `_closure`. Jika nilai tersebut adalah fungsi reguler atau circular data complex object, aplikasi akan mengalami error runtime *Freeze* atau crash dereferencing JSI undefined pointer.
10. Bagaimana cara kerja `withDecay` dan parameter apa yang mengontrol berhentinya komputasi gerak inersia tersebut?
    - *Jawaban*: `withDecay` menggunakan persamaan diferensial perlambatan berbasis eksponensial berdasarkan `velocity` awal yang diterima saat jari diangkat. Gerakan berhenti saat kecepatan mencapai `deceleration` factor atau menabrak batasan `clamp`.

#### 3 Skenario Kasus Produksi
11. **Skenario 1**: Pada production release aplikasi e-commerce, user mengeluhkan bahwa interaksi scrolling `FlashSaleList` terasa patah-patah (stuttering) saat animasi banner countdown berjalan. Setelah diaudit, banner menggunakan `useAnimatedStyle` yang memutasi `backgroundColor` setiap detik. Apa akar masalahnya dan bagaimana solusinya?
    - *Solusi Root-Cause*: Animasi warna tersebut mungkin memicu layout repaint yang luas atau memicu bridging style jika format warna di-passing sebagai string HEX dinamis yang memerlukan kalkulasi parser. Solusi: Gunakan representasi interpolasi warna RGBA terhitung, isolasi banner view hierarchy menggunakan layer compositing (GPU layer), pastikan tidak ada dependency React state yang bocor ke komponen list, dan gunakan `renderToHardwareTextureAndroid` / `shouldRasterizeIOS`.
12. **Skenario 2**: BottomSheet modal sering kali macet (stuck di tengah layar) saat user menggeser sheet dengan kecepatan sangat tinggi (fling velocity > 4000 pt/s).
    - *Solusi Root-Cause*: Terjadi overflow kalkulasi velocity yang memicu spring instability atau `withSpring` crash karena nilai target berada di luar clamp array bounds. Solusi: Sanitasi velocity input menggunakan clamping `Math.max(MIN_VEL, Math.min(event.velocityY, MAX_VEL))`, dan gunakan physics spring config dengan parameter `overshootClamping: true` untuk membatasi momentum ekstrem.
13. **Skenario 3**: Memory Profiler menunjukkan konsumsi native RAM meningkat secara bertahap (leak) setiap kali user membuka dan menutup halaman Media Viewer yang mengimplementasikan Pinch-to-Zoom dengan `useSharedValue`.
    - *Solusi Root-Cause*: Referensi pointer JSI HostObject pada secondary runtime tidak dilepaskan karena closure capture di dalam handler gesture menahan context lifecycle view, atau animasi spring/timing yang sedang berlangsung tidak dihentikan sebelum unmount. Solusi: Panggil `cancelAnimation(scale)` dan `cancelAnimation(translation)` pada return callback `useEffect` cleanup hook untuk melepaskan listener pada display loop.

---

### 16. Summary
1. **Reanimated v3 Architecture**: Menjalankan secondary Hermes Runtime langsung di UI Thread. Hal ini menghilangkan dependensi pada Main JS Thread untuk seluruh eksekusi animasi dan perhitungan gestur.
2. **JSI & Worklets Foundation**: Direktif `'worklet';` menginstruksikan compiler untuk mengekstraksi logika agar dapat dipanggil langsung oleh C++ core via direct pointer access, menyediakan 0-frame latency mutation.
3. **RNGH v2 Synergy**: Intersepsi event gesture pada tingkat OS terendah dipadukan langsung dengan Worklet handlers, mencegah starvation frame rate di angka 60/120 FPS.
4. **Architectural Guardrails**: Hindari layout reflow properties (`width`/`margin`), pastikan worklet berjalan secara linier `O(1)`, delegasikan back-to-react state updates via `runOnJS` hanya pada status `onEnd`/`onFinalize`, dan bersihkan active display loops pada unmount lifecycle untuk menjamin arsitektur mobile enterprise yang stabil dan bebas leak.