# Bab 02 Module 01: Declarative UI, Component Lifecycle & Styling Systems

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik Spesialisasi:** React Native Core Engineering
*   **Modul:** Bab 02 Module 01: Declarative UI, Component Lifecycle & Styling Systems
*   **Prasyarat Pengetahuan:** 
    *   Penguasaan JavaScript Modern (ES6+, Event Loop, Microtasks, Closures).
    *   Fondasi TypeScript (Generics, Mapped Types, Union Types, Utility Types).
    *   Pemahaman Arsitektur React Web dasar (JSX, Hooks API).
    *   Pengenalan CLI Development Tools (Node.js, Yarn/npm, Android SDK, Xcode Toolchain).
*   **Estimasi Waktu Selesai:** 8 – 10 Jam Pembelajaran Intensif & Hands-on Coding.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1.  **Mendekonstruksi Paradigma UI Deklaratif vs Imperatif:** Menganalisis secara matematis fungsi transformasional UI $UI = f(State)$ serta membedakan alur eksekusi React Native terhadap alur modul native murni (UIKit/Android Views).
2.  **Menganalisis Siklus Hidup Komponen dan React Fiber:** Membedakan fase *Render* (murni dan bebas side-effect) dengan fase *Commit* (mutasi host/DOM/Shadow Tree) di dalam siklus hidup Hooks (`useEffect`, `useLayoutEffect`, `useInsertionEffect`).
3.  **Membedah Engine Styling React Native:** Menjelaskan secara mendalam bagaimana CSS subsets diterjemahkan oleh Yoga Layout Engine (C++ implementation of Flexbox) dan bagaimana `StyleSheet.create` mengoptimalkan alokasi memori melalui *ID-based style resolution*.
4.  **Mengimplementasikan Desain Sistem Skalabel:** Membangun antarmuka berbasis tema dinamis yang bebas dari perenderan berulang (*render thrashing*) menggunakan teknik memoization, context splitting, dan token-based abstraction.
5.  **Mendeteksi & Mengatasi Memory Leak & Render Pitfalls:** Menemukan *re-render cascade*, *closure capture stale state*, serta alokasi array/object inline pada props styling menggunakan profiling tools tingkat lanjut.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam pemrograman mobile konvensional (UIKit imperatif di iOS atau Android View System imperatif di Android), antarmuka dibangun dan diubah secara manual melalui instruksi prosedural:

```text
// Model Imperatif (Android Java/Kotlin atau iOS Swift kuno)
button.setColor(RED);
button.setText("Loading...");
loadingSpinner.setVisibility(VISIBLE);
```

Setiap perubahan status mengharuskan mutasi langsung terhadap pohon tampilan native (*Host Views*). Pendekatan ini rentan terhadap ketidaksinkronan status antarmuka (*state-view desynchronization*). 

Sebaliknya, **React Native mengadopsi Paradigma Deklaratif Komputasional**:

$$\text{UI} = f(\text{State}, \text{Props})$$

Antarmuka pengguna adalah proyeksi matematis deterministik dari data internal (*State*) dan data eksternal (*Props*). Anda tidak memerintahkan elemen visual untuk berpindah, berubah warna, atau bersembunyi. Anda mendeklarasikan *kondisi visual seperti apa yang harus hadir untuk sekumpulan data tertentu*, lalu mendelegasikan eksekusi perubahan pohon tampilan ke *Reconciliation Engine* (React Fiber) dan *Layout Engine* (Yoga).

### Perbedaan Mental Model: Web DOM vs React Native Host Trees

```text
[Web Platform]
JSX -> React Fiber -> Virtual DOM -> Real DOM Browser -> Layout Engine Browser (Blink/WebKit)

[React Native Architecture]
JSX -> React Fiber -> React Shadow Tree -> Yoga Engine (C++) -> Native Host Views (UIView / android.view.View)
```

1.  **Yoga Engine Membaca Flexbox:** Web menggunakan CSS box model konvensional dengan *block*, *inline*, *float*, *table*, dan *flexbox*. React Native murni menggunakan subset Flexbox yang diimplementasikan ulang dalam C++ oleh Yoga Engine. `flexDirection` default pada React Native adalah `column`, bukan `row` seperti pada browser web.
2.  **Tanpa Cascading Asli:** React Native tidak memiliki aturan cascading class global seperti browser. Setiap komponen harus menerima styling secara eksplisit via inline styles atau style sheets yang dikirim melalui props.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah siklus interaksi antara JavaScript Virtual Machine (Hermes), React Fiber, C++ Shadow Tree, Yoga Layout Engine, dan Native UI Manager (Fabric Architecture):

```text
+----------------------------------------------------------------------------------------------------+
|                                      JAVASCRIPT REALM (Hermes)                                     |
|                                                                                                    |
|  [State Update Action] ---> Dispatcher                                                             |
|                                  |                                                                 |
|                                  v                                                                 |
|  +------------------------------------------------------------------+                             |
|  | REACT FIBER RECONCILER (Render Phase - Concurrent & Asynchronous) |                             |
|  | - Evaluasi Hooks: useState, useReducer                            |                             |
|  | - Eksekusi Fungsi Komponen: UI = f(state)                         |                             |
|  | - Diffing: Komputasi perubahan pada Fiber Tree Baru               |                             |
|  +------------------------------------------------------------------+                             |
|                                  |                                                                 |
+----------------------------------|-----------------------------------------------------------------+
                                   | (JSI - JavaScript Interface Direct C++ Access)
                                   v
+----------------------------------------------------------------------------------------------------+
|                                      C++ HOST RUNTIME LAYER (Fabric)                               |
|                                                                                                    |
|  +------------------------------------------------------------------+                             |
|  | REACT SHADOW TREE MUTATION (Commit Phase)                        |                             |
|  | - Clone Shadow Nodes (Immutable C++ Nodes)                       |                             |
|  | - Binding StyleSheet Flattened Properties                        |                             |
|  +------------------------------------------------------------------+                             |
|                                  |                                                                 |
|                                  v                                                                 |
|  +------------------------------------------------------------------+                             |
|  | YOGA LAYOUT CALCULATION ENGINE (libyoga.so / Yoga.framework)     |                             |
|  | - Input: flex, padding, margin, width, height                    |                             |
|  | - Kalkulasi Relatif -> Absolut Koordinat:                       |                             |
|  |   { x: 24.0, y: 120.5, width: 342.0, height: 48.0 }              |                             |
|  +------------------------------------------------------------------+                             |
|                                  |                                                                 |
+----------------------------------|-----------------------------------------------------------------+
                                   | (Direct JNI / Objective-C++ Callbacks)
                                   v
+----------------------------------------------------------------------------------------------------+
|                                   NATIVE OS THREAD (Main UI Thread)                                |
|                                                                                                    |
|  +------------------------------------------------------------------+                             |
|  | PLATFORM HOST VIEW MOUNTING                                      |                             |
|  | - Android: ViewGroup.addView(), View.layout()                    |                             |
|  | - iOS: UIView.addSubview(), UIView.layoutSubviews()              |                             |
|  | - GPU Draw Call via Platform Render Pipeline (Skia/Metal)       |                             |
|  +------------------------------------------------------------------+                             |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### Alur Eksekusi Component Lifecycle (Hooks Implementation)

```text
[Mounting Stage]
   (JS) Run Component Function Body (Render Phase)
      |
      v
   (JS) Return JSX Elements Description
      |
      v
   (C++) Fabric Clones Shadow Tree & Yoga Computes Coordinates
      |
      v
   (Native UI) Mount Platform Views to Screen
      |
      +-----> (Synchronous blocking UI) useLayoutEffect Callback Run
      |
      v
   (JS Event Loop Tick)
      |
      +-----> (Asynchronous non-blocking) useEffect Callback Run

[Updating Stage]
   State / Props Change
      |
      v
   (JS) Run Component Body (Diffing Fiber)
      |
      v
   (C++) Shadow Tree Delta Calculation
      |
      v
   (Native UI) Mutation Applied to Views
      |
      +-----> (Synchronous) useLayoutEffect Cleanup -> useLayoutEffect Execution
      |
      v
   (JS Event Loop Tick)
      |
      +-----> (Asynchronous) useEffect Cleanup -> useEffect Execution

[Unmounting Stage]
   Component Detached
      |
      v
   (Synchronous) useLayoutEffect Cleanup Execution
      |
      v
   (Asynchronous) useEffect Cleanup Execution
      |
      v
   (C++) Destroy Shadow Nodes & Release Native Host Views
```

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

```typescript
// components/AdaptiveSurfaceCard.tsx
import React, { useState, useEffect, useLayoutEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Platform,
  LayoutChangeEvent,
} from 'react-native';

export interface AdaptiveCardProps {
  readonly title: string;
  readonly description: string;
  readonly initialExpanded?: boolean;
  readonly onExpansionChange?: (expanded: boolean) => void;
}

export const AdaptiveSurfaceCard: React.FC<AdaptiveCardProps> = ({
  title,
  description,
  initialExpanded = false,
  onExpansionChange,
}) => {
  // 1. Declarative UI State
  const [isExpanded, setIsExpanded] = useState<boolean>(initialExpanded);
  const [contentHeight, setContentHeight] = useState<number>(0);

  // 2. Mutable Ref for layout tracking without causing re-renders
  const viewContainerRef = useRef<View>(null);
  const renderCounter = useRef<number>(0);
  renderCounter.current += 1;

  // 3. useLayoutEffect: Digunakan untuk operasi layout-blocking jika diperlukan
  useLayoutEffect(() => {
    // Dipanggil sinkron setelah rendering native siap, sebelum paint.
    // Tidak boleh menjalankan blocking computation di sini.
  }, [isExpanded]);

  // 4. useEffect: Asynchronous side-effects pasca-paint
  useEffect(() => {
    onExpansionChange?.(isExpanded);

    const subscriptionCleanup = () => {
      // Cleanup effect run pada saat unmount atau sebelum re-run effect
    };

    return subscriptionCleanup;
  }, [isExpanded, onExpansionChange]);

  // 5. Stable Event Handlers
  const handleToggle = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  const handleLayout = useCallback((event: LayoutChangeEvent) => {
    const { height } = event.nativeEvent.layout;
    setContentHeight(height);
  }, []);

  return (
    <View 
      ref={viewContainerRef} 
      style={styles.cardContainer}
      onLayout={handleLayout}
    >
      <View style={styles.headerRow}>
        <Text style={styles.titleText}>{title}</Text>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Toggle Content Expansion"
          accessibilityState={{ expanded: isExpanded }}
          onPress={handleToggle}
          style={({ pressed }) => [
            styles.toggleButton,
            pressed && styles.toggleButtonPressed,
          ]}
        >
          <Text style={styles.buttonText}>{isExpanded ? 'Collapse' : 'Expand'}</Text>
        </Pressable>
      </View>

      {isExpanded && (
        <View style={styles.bodyContainer}>
          <Text style={styles.descriptionText}>{description}</Text>
        </View>
      )}

      <Text style={styles.footerDebug}>
        Render count: {renderCounter.current} | Height: {contentHeight.toFixed(1)}pt
      </Text>
    </View>
  );
};

// 6. Memory-optimized StyleSheet Singleton
const styles = StyleSheet.create({
  cardContainer: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginVertical: 8,
    marginHorizontal: 16,
    ...Platform.select({
      ios: {
        shadowColor: '#000000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.08,
        shadowRadius: 8,
      },
      android: {
        elevation: 3,
      },
    }),
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  titleText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#1A1A1A',
    flex: 1,
  },
  toggleButton: {
    backgroundColor: '#0F62FE',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
  },
  toggleButtonPressed: {
    backgroundColor: '#0043CE',
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '600',
  },
  bodyContainer: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#E0E0E0',
  },
  descriptionText: {
    fontSize: 14,
    color: '#525252',
    lineHeight: 20,
  },
  footerDebug: {
    marginTop: 8,
    fontSize: 10,
    color: '#A8A8A8',
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
});
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 19-20 (`useState` declarations):** Menginisialisasi status lokal `isExpanded` dan `contentHeight`. Pemanggilan updater function `setIsExpanded` menjadwalkan siklus render baru di Fiber Reconciler.
*   **Baris 23-25 (`renderCounter` ref):** Objek `useRef` mempertahankan identitas yang sama di seluruh siklus hidup komponen tanpa memicu re-render ketika nilainya diubah secara mutatif (`renderCounter.current += 1`).
*   **Baris 28-32 (`useLayoutEffect`):** Blok sinkron yang berjalan tepat setelah rekonsiliasi native selesai namun sebelum framebuffer dikirim ke layar. Sangat tepat digunakan bila kita butuh intervensi layout instan tanpa *layout flickers*.
*   **Baris 35-43 (`useEffect`):** Memisahkan side effect pasca render secara asynchronous. Penggunaan dependensi array `[isExpanded, onExpansionChange]` menjamin fungsi effect hanya dieksekusi saat status benar-benar berubah secara referensial.
*   **Baris 46-48 (`useCallback`):** Membungkus updater callback dalam identitas referensial stabil sehingga aman dioperasikan sebagai dependency array ataupun dikirimkan ke memoized child components (`React.memo`).
*   **Baris 50-53 (`onLayout` callback):** Menerima event layout asli dari Yoga Layout engine. `event.nativeEvent.layout` diekstrak asinkron oleh OS saat ukuran frame telah definitif.
*   **Baris 69-72 (`Pressable style function`):** Menerapkan dynamic functional style pattern `({ pressed }) => [...]`. Ini menghindari alokasi state manual untuk status sentuhan dan dihitung langsung oleh gesture engine internal.
*   **Baris 92-105 (`Platform.select` didalam `StyleSheet`):** Mengabstraksi perbedaan rendering bayangan antara platform iOS (CoreGraphics shadows) dan platform Android (RenderNode elevation layer).

---

## SEKSI 09 — STUDI KASUS NYATA

### Enterprise Scenario: FinTech High-Frequency Stock Ticker & Portfolio Dashboard

**Konteks Masalah:**
Sebuah aplikasi bursa efek skala enterprise memiliki dashboard analitik instrumen investasi real-time. Dashboard menerima pembaruan harga saham via WebSocket dengan frekuensi ~20 update per detik across 50 instrumen. 

**Kegagalan Sistem yang Muncul:**
1.  **Render Cascading Extreme:** Pengembang awal menempatkan skema tema (*Theming Engine*) dan data WebSocket dalam satu React Context tunggal. Setiap harga saham berfluktuasi, seluruh komponen hirarki—termasuk header statis, navigasi, dan deskripsi akun—mengalami re-render.
2.  **Memory Spike & Frame Drops (Jank):** Implementasi kartu saham membuat dynamic style objects secara inline (`style={{ backgroundColor: isPositive ? 'green' : 'red', margin: 10 }}`). Engine Hermes kewalahan mengalokasikan dan membersihkan memory heap garbage collection ribuan objek per detik. Frame rate anjlok dari 60/120 FPS ke 14 FPS di platform low-end Android.
3.  **UI Thread Locking:** Perubahan warna indikator saham dilakukan menggunakan `useLayoutEffect` yang memicu pemblokiran siklus commit thread UI.

**Solusi Arsitektural:**
1.  **Isolasi Konteks Tema & State:** Pisahkan *Theme Token Context* dari *Real-Time Data Streams*.
2.  **Structural Memory Pooling:** Ubah inline styling menjadi memoized style sheet factory patterns dengan semantic CSS tokens.
3.  **Lifecycle Shifting:** Pindahkan visual tracking dari main JavaScript render pass ke un-synced layout triggers yang dievaluasi terpisah.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi skala industri untuk sistem dashboard performa tinggi tersebut:

```typescript
// theme/ThemeContext.tsx
import React, { createContext, useContext, useMemo } from 'react';

export interface ThemePalette {
  readonly background: string;
  readonly cardSurface: string;
  readonly textPrimary: string;
  readonly textSecondary: string;
  readonly positiveGreen: string;
  readonly negativeRed: string;
  readonly borderSubtle: string;
}

const DarkTheme: ThemePalette = {
  background: '#121212',
  cardSurface: '#1E1E1E',
  textPrimary: '#FFFFFF',
  textSecondary: '#A0A0A0',
  positiveGreen: '#00E676',
  negativeRed: '#FF1744',
  borderSubtle: '#2C2C2C',
};

const LightTheme: ThemePalette = {
  background: '#F4F5F7',
  cardSurface: '#FFFFFF',
  textPrimary: '#111827',
  textSecondary: '#6B7280',
  positiveGreen: '#059669',
  negativeRed: '#DC2626',
  borderSubtle: '#E5E7EB',
};

interface ThemeContextType {
  readonly theme: ThemePalette;
  readonly isDark: boolean;
}

const ThemeContext = createContext<ThemeContextType | null>(null);

export const ThemeProvider: React.FC<{ isDark: boolean; children: React.ReactNode }> = ({
  isDark,
  children,
}) => {
  const value = useMemo(
    () => ({
      theme: isDark ? DarkTheme : LightTheme,
      isDark,
    }),
    [isDark]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};

export const useAppTheme = (): ThemePalette => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useAppTheme must be consumed within a ThemeProvider');
  }
  return context.theme;
};
```

```typescript
// components/StockTickerCard.tsx
import React, { memo, useRef } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme, ThemePalette } from '../theme/ThemeContext';

export interface TickerData {
  readonly symbol: string;
  readonly currentPrice: number;
  readonly changePercentage: number;
}

interface StockTickerCardProps {
  readonly data: TickerData;
}

// Memory-optimized style cache factory
const createThemedStyles = (theme: ThemePalette) =>
  StyleSheet.create({
    cardContainer: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      paddingVertical: 14,
      paddingHorizontal: 16,
      backgroundColor: theme.cardSurface,
      borderBottomWidth: 1,
      borderBottomColor: theme.borderSubtle,
    },
    symbolText: {
      fontSize: 16,
      fontWeight: '700',
      color: theme.textPrimary,
      letterSpacing: 0.5,
    },
    priceText: {
      fontSize: 16,
      fontWeight: '600',
      color: theme.textPrimary,
      textAlign: 'right',
    },
    badge: {
      paddingHorizontal: 8,
      paddingVertical: 4,
      borderRadius: 4,
      minWidth: 72,
      alignItems: 'center',
    },
    badgePositive: {
      backgroundColor: 'rgba(5, 150, 105, 0.15)',
    },
    badgeNegative: {
      backgroundColor: 'rgba(220, 38, 38, 0.15)',
    },
    percentageText: {
      fontSize: 12,
      fontWeight: '700',
    },
    percentageTextPositive: {
      color: theme.positiveGreen,
    },
    percentageTextNegative: {
      color: theme.negativeRed,
    },
  });

export const StockTickerCard = memo<StockTickerCardProps>(
  ({ data }) => {
    const theme = useAppTheme();

    // Cache stylesheet references per theme identity to avoid JNI/Hermes thrashing
    const styles = React.useMemo(() => createThemedStyles(theme), [theme]);

    const isPositive = data.changePercentage >= 0;

    return (
      <View style={styles.cardContainer}>
        <View>
          <Text style={styles.symbolText}>{data.symbol}</Text>
        </View>
        <View style={{ alignItems: 'flex-end' }}>
          <Text style={styles.priceText}>${data.currentPrice.toFixed(2)}</Text>
          <View
            style={[
              styles.badge,
              isPositive ? styles.badgePositive : styles.badgeNegative,
            ]}
          >
            <Text
              style={[
                styles.percentageText,
                isPositive ? styles.percentageTextPositive : styles.percentageTextNegative,
              ]}
            >
              {isPositive ? '+' : ''}
              {data.changePercentage.toFixed(2)}%
            </Text>
          </View>
        </View>
      </View>
    );
  },
  (prevProps, nextProps) => {
    // Custom fine-grained equality comparator
    return (
      prevProps.data.symbol === nextProps.data.symbol &&
      prevProps.data.currentPrice === nextProps.data.currentPrice &&
      prevProps.data.changePercentage === nextProps.data.changePercentage
    );
  }
);
StockTickerCard.displayName = 'StockTickerCard';
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Pendekatan | Pure `StyleSheet.create` | Styled-Components (CSS-in-JS Legacy) | NativeWind (Tailwind / Static Engine) |
| :--- | :--- | :--- | :--- |
| **Parsing Overhead** | **Nol / Sangat Rendah.** Divalidasi secara statis pada inisialisasi JS bundle. | **Tinggi.** Regex parsing runtime, string template hashing per lifecycle. | **Hampir Nol.** Pre-compiled pada compile-time via Babel/Metro Transformers. |
| **Memory Footprint** | **Minimal.** Referensi statis tetap, tidak ada duplikasi metadata CSS. | **Tinggi.** Membuat ribuan wrapper komponen anonim di dalam Fiber Tree. | **Sangat Rendah.** Menggunakan direct StyleSheet IDs di balik layar. |
| **Dynamic Prop Theming** | **Manual.** Membutuhkan factory pattern atau array style composition. | **Native & Mudah.** Dynamic style injection via nested props interpolations. | **Deklaratif.** Menggunakan class names bersyarat via standard utility strings. |
| **New Arch (Fabric) Ready**| **100% Native.** Nol isu kompatibilitas JSI. | Sering bermasalah dengan synchronous layout phases di C++. | Sangat kompatibel jika menggunakan arsitektur v4+. |
| **DX (Developer Exp.)** | Sedang. Menuntut penulisan style sheet eksplisit yang verbose. | Sangat Disukai web developer konvensional, syntax familiar. | Sangat Cepat untuk rapid prototyping skala enterprise. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Flash of Unstyled / Miscalculated Content (Layout Flicker)
*   **Kasus:** Menghitung ukuran container menggunakan `useEffect` asinkron lalu menggeser posisi elemen. Pengguna akan melihat layout melompat (*flicker*) selama 1-2 frame.
*   **Mitigasi:** Gunakan `useLayoutEffect` untuk kalkulasi layout imperatif murni, atau lebih baik gunakan kalkulasi CSS Flexbox native murni tanpa intervensi JavaScript.

### 2. Closure Capture Stale State pada Subscriptions
*   **Kasus:** Penggunaan callback dalam `useEffect` yang membaca nilai state tanpa memasukkannya ke dependency array atau tanpa functional update.

```typescript
// BAHAYA (Stale Closure)
useEffect(() => {
  const timer = setInterval(() => {
    // Selalu membaca 'count' saat initial render!
    setCount(count + 1); 
  }, 1000);
  return () => clearInterval(timer);
}, []); // count tidak ada di dependensi

// SOLUSI DETERMINISTIK (Functional Update)
useEffect(() => {
  const timer = setInterval(() => {
    setCount((currentCount) => currentCount + 1);
  }, 1000);
  return () => clearInterval(timer);
}, []);
```

### 3. Z-Index Inconsistencies Cross-Platform
*   **Kasus:** `zIndex` di iOS bekerja secara natural pada layer layer layer UIView. Di Android, `zIndex` **tidak bekerja** jika view tidak memiliki `elevation` atau jika view target berada di luar urutan hierarki sibling view native (*Android draws according to index order in ViewGroup*).
*   **Mitigasi:** Atur urutan rendering komponen secara deklaratif langsung di JSX tree. Elemen yang muncul paling akhir di markup akan dirender di atas elemen terdahulu pada Android.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Dynamic Inline Object Allocation
*   *Salah:* `<View style={{ flex: 1, padding: 16 }} />`
*   *Akibat:* Alokasi objek JavaScript baru `{ flex: 1, padding: 16 }` dibuat pada **setiap** siklus render. Ini memicu overhead GC (*Garbage Collector*) Hermes dan memaksa shallow comparison props gagal pada child components.
*   *Benar:* Alokasikan ke `StyleSheet.create` di luar body komponen, atau gunakan conditional styles array: `style={[styles.container, isPadded && styles.padded]}`.

### 2. Text Unwrapped Inside View (Crash pada iOS / Undefined Behaviour)
*   *Salah:* `<View>Hello Enterprise</View>`
*   *Akibat:* Crash instan pada runtime iOS (`Invariant Violation: Text strings must be rendered within a <Text> component`). Tidak seperti Web DOM di mana text node bisa hidup di dalam `<div>`, Fabric mewajibkan string primitif dibungkus oleh node `RCTText` (`<Text>`).
*   *Benar:* `<View><Text>Hello Enterprise</Text></View>`.

### 3. Asymmetric Cleanup Functions
*   *Salah:* Mendaftarkan listener global di `useEffect` tanpa fungsi pengembalian pembersih (*cleanup function*).
*   *Akibat:* Memory leak masif. Ketika layar di-unmount, listener tetap hidup dan mencoba memperbarui state komponen yang sudah tidak ada di Fiber Tree (*unmounted component state mutation warning*).
*   *Benar:* Selalu kembalikan fungsi pembersih yang simetris dengan proses registrasinya.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Token-Driven Theming:** Jangan gunakan string warna raw (`#FFFFFF`, `rgba(...)`) secara tersebar di kode. Definisikan design token global (`colors.surface.primary`, `spacing.md`) untuk isolasi dependensi visual.
2.  **Style Extraction Isolation:** Selalu posisikan `StyleSheet.create` di bagian paling bawah file komponen. Struktur ini memisahkan logika UI (JSX di atas) dengan deklarasi estetika (style di bawah).
3.  **Encapsulated Layout Boundaries:** Komponen reusable tingkat atomik (*Button*, *Card*, *Input*) **tidak boleh** memiliki properti layout eksternal seperti `margin`, `top`, `left`, atau `flex` langsung pada root container-nya. Biarkan komponen induk yang menentukan posisi spasial komponen anak.
4.  **Strict Component Purity:** Komponen fungsional harus bersikap murni (*idempotent*). Jangan pernah memanggil network call, I/O database, atau mutasi variabel global di luar hooks `useEffect` / `useCallback`.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Style Flattening Optimization
Ketika menggabungkan array style: `style={[styles.base, isActive && styles.active]}`, React Native membaca urutan array secara berurutan. Hindari pemanggilan `StyleSheet.flatten` kecuali benar-benar diwajibkan untuk inspeksi properti secara imperatif. `StyleSheet.flatten` menyatukan objek secara manual di level JavaScript, menghilangkan optimasi internal Fabric C++ Style Resolution.