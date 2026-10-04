# BAB 02: Declarative UI, Component Lifecycle, dan Styling Systems
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis (C4)** siklus hidup komponen dan pipeline rendering React Native pada arsitektur Fabric, mulai dari fase deklaratif JSX hingga alokasi memori pada native views melalui Yoga Engine.
- **Mengevaluasi (C5)** trade-off performa, alokasi heap Hermes, dan layout overhead antara pendekatan styling tradisional (`StyleSheet.create`), utility-first modern (`NativeWind v4`), dan dynamic runtime C++ hybrid (`react-native-unistyles`).
- **Merancang (C6)** arsitektur Design Token & Theming System kelas enterprise yang memiliki kemampuan dynamic runtime skinning tanpa menimbulkan re-render cascading di seluruh subtree aplikasi.
- **Mengoptimalkan (C5)** alokasi memori dan render path dengan mengeliminasi *anonymous object allocations*, *layout thrashing*, dan *bridge/JSI saturation* pada komponen UI berdensitas tinggi.

---

### 2. Prerequisite

Sebelum memulai modul ini, pastikan Anda telah menguasai:
- **Fondasi React Core:** Rekonsiliasi React Fiber, state machine hooks (`useReducer`, `useMemo`, `useCallback`), dan aturan rendering murni (*pure component contracts*).
- **TypeScript Enterprise:** Variadic tuple types, generic constraints, mapped types, dan template literal types untuk inferensi token desain.
- **React Native Toolchain:** Pengalaman dasar menjalankan target platform Android (NDK/Gradle) dan iOS (CocoaPods/Xcode) dengan arsitektur New Architecture (Fabric & TurboModules) aktif.

---

### 3. Concept & Internal Architecture

Dalam arsitektur enterprise modern, declarative UI di React Native bukan sekadar abstraksi React DOM untuk mobile. UI direpresentasikan sebagai sebuah *immutable state tree* yang diproses oleh render pipeline multi-fase melintasi batas runtime JavaScript (Hermes Engine) dan C++ Core.

```
+-----------------------------------------------------------------------------------+
|                              HERMES JAVASCRIPT ENGINE                             |
|  [JSX Execution] -> [React Fiber Node] -> [Virtual DOM Diffing / Commit Phase]    |
+---------------------------------------------------------+-------------------------+
                                                          | JSI (Direct Memory Access)
+---------------------------------------------------------v-------------------------+
|                                C++ CORE (FABRIC ENGINE)                           |
|  +-----------------------------------------------------------------------------+  |
|  | New Shadow Tree Construction                                                |  |
|  |   └── ShadowNode (C++ representation of JSX)                                |  |
|  +-----------------------------------------------------------------------------+  |
|                                         |                                         |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  | Yoga Engine (Layout Calculation)                                            |  |
|  |   ├── Inputs: Flexbox styles, dimensions, constraints                       |  |
|  |   └── Outputs: Exact pixel bounding boxes (x, y, width, height)             |  |
|  +-----------------------------------------------------------------------------+  |
+---------------------------------------------------------+-------------------------+
                                                          | Direct Host Manipulation
+---------------------------------------------------------v-------------------------+
|                              HOST PLATFORM (NATIVE OS)                            |
|  +------------------------------------+    +------------------------------------+ |
|  | Android UI (View Hierarchy)        |    | iOS UI (CALayer / UIView)          | |
|  |   └── android.view.ViewGroup       |    |   └── UIView / RCTView             | |
|  +------------------------------------+    +------------------------------------+ |
+-----------------------------------------------------------------------------------+
```

#### Pipeline Rendering Fabric & Yoga Engine

1. **JavaScript React Layer:**
   Komponen React mengembalikan elemen JSX. React Fiber melakukan rekonsiliasi state diffing. Ketika sebuah perubahan disetujui (Commit Phase), React tidak memanipulasi native view secara langsung, melainkan mengeksekusi instruksi melalui JavaScript Interface (JSI).
2. **Fabric Shadow Tree:**
   Instruksi dari JSI dikirim secara sinkron ke C++ Fabric core untuk membentuk atau memperbarui *Shadow Tree*. Berbeda dengan New Architecture generasi lama yang mengandalkan JSON serialization melalui asinkron bridge, proses ini langsung mengalokasikan memori native di thread C++. Setiap elemen UI direfleksikan sebagai `ShadowNode`.
3. **Yoga Engine Computation:**
   `ShadowNode` mengirimkan metadata tata letak (flex, margins, paddings, display) ke **Yoga Engine** (engine C++ yang mengimplementasikan spesifikasi W3C Flexbox). Yoga melakukan *layout pass* untuk menghitung metrik absolut komponen: posisi `(x, y)` dan dimensi `(width, height)`.
4. **Native Mounting Layer:**
   Setelah kalkulasi Yoga selesai, pohon mutasi ditransmisikan ke thread UI utama OS host (Android/iOS). Native Mounting Manager mengalokasikan atau memutasi objek platform murni: `android.view.ViewGroup` di Android atau `UIView`/`CALayer` di iOS.

#### Deep Dive: Anatomi Styling System

Pada tingkat performa engine, mekanisme styling terbagi ke dalam tiga paradigma:

- **Legacy `StyleSheet.create`:**
  Mengirimkan objek style ke native layer saat inisialisasi aplikasi. Di New Architecture, properti style langsung di-serialize ke bentuk representasi `folly::dynamic` C++, lalu di-cache. Modifikasi style dinamis yang dioperasikan melalui inline object `style={{ marginTop: condition ? 10 : 20 }}` memaksa alokasi memori JS baru pada setiap render cycle dan memicu invalidasi node pada C++ Shadow Tree.
- **Zero-Runtime / Build-time Compilation (NativeWind v4):**
  Menggunakan engine Tailwind compiler melalui plugin Babel/SWC. Utilitas class di-resolve saat build-time menjadi objek style terindeks atau langsung berinteraksi dengan Native CSSInterop runtime, meminimalkan latensi evaluasi style saat run-time.
- **C++ TurboModule Accelerated (Unistyles v2/v3):**
  Memindahkan komputasi responsivitas, breakpoints, dan token injection ke layer native C++ via JSI. Variasi tema tidak melewati rekonsiliasi JS runtime sepenuhnya, melainkan langsung mengubah dynamic properties di Fabric C++ node, mereduksi rendering overhead secara drastis saat screen rotation atau dark-mode toggle.

---

### 4. Why & What

#### Mengapa Arsitektur Komponen dan Styling Menentukan Keberhasilan Aplikasi Skala Besar?
Pada aplikasi enterprise dengan ratusan view terkomposisi (misal: feed media sosial berkecepatan tinggi atau checkout funnel e-commerce), inefisiensi minor dalam component lifecycle atau dynamic styling akan terakumulasi menjadi:
- **Frame Drop (Jank):** Alokasi inline styles memicu Hermes Garbage Collection (GC) berhenti sejenak (*stop-the-world pauses*), menjatuhkan refresh rate dari 120 FPS ke <45 FPS.
- **Layout Thrashing:** Komputasi ukuran manual via `onLayout` JavaScript layer memicu relayout pass ganda (JS $\rightarrow$ Native $\rightarrow$ JS $\rightarrow$ Native), menyebabkan latency render naik ratusan milidetik.
- **Theme Mutation Delay:** Aplikasi yang mengimplementasikan tema via dynamic React Context murni akan memicu re-render seluruh subtree DOM/Native dari akar (*root*), mengakibatkan visual freezing sesaat saat tema berganti.

#### Apa yang Dibangun?
Arsitektur styling enterprise mengisolasi komputasi desain ke dalam:
1. **Immutable Design Token Contract:** Single source of truth berbasis TypeScript strict inference.
2. **Optimized Layout Lifecycle:** Menghindari trigger lifecycle yang tidak perlu melalui strict memoization dan meminimalkan ketergantungan pada runtime state.
3. **Atomic Multi-Theme Resolution Engine:** Abstraksi styling berperforma tinggi yang memotong siklus render JS untuk operasi tata letak murni.

---

### 5. How (Workflow Detail)

Siklus pembuatan komponen dari deklarasi hingga penampilan di layar mengikuti rantai berikut:

```
[Design Token Definition]
          │
          ▼
[StyleSheet Compilation / Macro Resolution]
          │
          ▼
[React Render Phase (Props/State Change)]
          │
          ├─► Identical Primitive Check (Object.is)
          │         │
          │         ├─► Sama: Abort Re-render (Fast Path)
          │         └─► Berubah: Lanjut ke Fiber Diffing
          ▼
[Fabric Node Sync via JSI (C++ Thread)]
          │
          ▼
[Yoga Flexbox Layout Calculation]
          │
          ▼
[OS View Hierarchy Commit (Main Thread)]
```

1. **Token Ingestion:** Variabel desain (warna, skala spacing, border radius) dikompilasi menjadi C++ cacheable memory references.
2. **Pure Render Contract Enforcement:** Komponen diisolasi menggunakan `React.memo` dengan custom equality comparator khusus untuk layout props, mencegah mutasi child tree jika dimensi tidak berubah.
3. **Layout Pipeline Bypass:** Styling dinamis berbasis gestur atau animasi dieksekusi melalui driver native (Reanimated / Animated JSI Driver) untuk mengubah node C++ langsung tanpa re-render React Lifecycle.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitek, Mandor C++, dan Kuli Native

Bayangkan membangun gedung pencakar langit:
- **Developer (React JSX):** Menulis cetak biru di atas kertas (menyatakan *apa* yang diinginkan: "Dinding ini berwarna biru, lebarnya 50%").
- **Mandor Berpengalaman (Yoga Engine & Fabric di C++):** Membaca cetak biru, menghitung kalkulasi gaya berat, sudut, dan panjang presisi menggunakan alat ukur metrik standar internasional (menghitung Flexbox menjadi koordinat absolut piksel secara instan di latar belakang).
- **Pekerja Konstruksi (Android ViewGroup / iOS UIView):** Hanya menerima perintah kerja jadi: "Letakkan balok beton berukuran $300\times400$ mm pada koordinat $(X=20, Y=50)$". Mereka tidak perlu mengerti apa itu Flexbox; mereka hanya merender bentuk fisik.

Jika developer mengubah cetak biru secara terus-menerus setiap milidetik (inline dynamic objects), mandor harus membuang kalkulasi sebelumnya dan menghitung ulang dari nol, membuat pekerja konstruksi berhenti bekerja menunggu instruksi baru (*jank*).

#### Siklus Hidup dan Memory Pipeline

```
JSX Source Code
  │
  ├─► React Fiber Commit (JavaScript Heap)
  │     │ 
  │     └─► [Allocation Check: Apakah objek style dialokasikan ulang?]
  │           ├─► YA: Alokasi memori baru di JS Heap -> Picu Hermes GC
  │           └─► TIDAK: Gunakan memory reference yang sudah di-cache
  │
  ├─► JSI Boundary Transition (Direct Pointer Passing)
  │     │
  │     ▼
  ├─► Fabric C++ Core
  │     │
  │     ├── Shadow Tree Clone & Mutation
  │     └── Yoga Layout Pass
  │           ├── Resolusi 'flexDirection'
  │           ├── Resolusi 'alignItems'
  │           └── Output: rect { left: 0, top: 44, width: 390, height: 844 }
  │
  └─► Native Platform Commit (Android Choreographer / iOS DisplayLink)
        │
        ▼
      Pixel Rendered on Display (Hardware Buffer Swap)
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengatasi Perangkap Inline Style
Pendekatan naif mengalokasikan objek baru pada setiap frame rendering:

```tsx
// ❌ ANTI-PATTERN: Alokasi memori berulang memicu GC thrashing
export const BadCard = ({ title, isActive }: { title: string; isActive: boolean }) => {
  return (
    <View style={{ padding: 16, backgroundColor: isActive ? '#007AFF' : '#FFFFFF' }}>
      <Text style={{ fontSize: 14, color: '#333333' }}>{title}</Text>
    </View>
  );
};

//  PRODUCTION PATTERN: Ekstraksi static style, minimalisasi alokasi dynamic branch
import React from 'react';
import { StyleSheet, View, Text } from 'react-native';

export const GoodCard = React.memo(({ title, isActive }: { title: string; isActive: boolean }) => {
  return (
    <View style={[styles.container, isActive ? styles.containerActive : styles.containerInactive]}>
      <Text style={styles.text}>{title}</Text>
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    padding: 16,
  },
  containerActive: {
    backgroundColor: '#007AFF',
  },
  containerInactive: {
    backgroundColor: '#FFFFFF',
  },
  text: {
    fontSize: 14,
    color: '#333333',
  },
});
```

---

#### Practical Example: Design Token Contract Engine yang Type-Safe dan Zero-Cost
Berikut implementasi design token foundation tingkat enterprise menggunakan TypeScript murni tanpa dynamic CSS-in-JS overhead:

```tsx
// src/theme/tokens.ts
export const DesignTokens = {
  colors: {
    light: {
      backgroundPrimary: '#FFFFFF',
      textPrimary: '#111827',
      accent: '#2563EB',
      surfaceDanger: '#DC2626',
    },
    dark: {
      backgroundPrimary: '#0F172A',
      textPrimary: '#F8FAFC',
      accent: '#3B82F6',
      surfaceDanger: '#EF4444',
    },
  },
  spacing: {
    none: 0,
    xs: 4,
    sm: 8,
    md: 16,
    lg: 24,
    xl: 32,
  },
  radii: {
    none: 0,
    sm: 4,
    md: 8,
    lg: 16,
    full: 9999,
  },
} as const;

export type ThemeMode = 'light' | 'dark';
export type SpacingToken = keyof typeof DesignTokens.spacing;
export type RadiiToken = keyof typeof DesignTokens.radii;
```

```tsx
// src/components/DynamicBox.tsx
import React, { useMemo } from 'react';
import { View, ViewStyle, StyleSheet, StyleProp } from 'react-native';
import { DesignTokens, ThemeMode, SpacingToken, RadiiToken } from '../theme/tokens';

export interface DynamicBoxProps {
  padding?: SpacingToken;
  borderRadius?: RadiiToken;
  mode: ThemeMode;
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}

export const DynamicBox: React.FC<DynamicBoxProps> = React.memo(({
  padding = 'md',
  borderRadius = 'none',
  mode,
  children,
  style,
}) => {
  // Hanya menghitung ulang styles jika token berubah, bukan setiap parent re-render
  const dynamicStyles = useMemo(() => {
    return StyleSheet.create({
      box: {
        backgroundColor: DesignTokens.colors[mode].backgroundPrimary,
        padding: DesignTokens.spacing[padding],
        borderRadius: DesignTokens.radii[borderRadius],
      },
    });
  }, [mode, padding, borderRadius]);

  return <View style={[dynamicStyles.box, style]}>{children}</View>;
});

DynamicBox.displayName = 'DynamicBox';
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Theming Aplikasi Multi-Brand Fintech Global
**Skala:** 8 juta active users harian, 4 brand core perbankan (white-label app), pergantian tema dinamis berdasarkan segmentasi nasabah (Retail vs Wealth Priority).

#### Masalah:
Implementasi styling sebelumnya berbasis dynamic Context Provider yang membungkus seluruh aplikasi. Ketika nasabah berganti status atau aplikasi berpindah mode secara otomatis saat malam:
- Terjadi **Root Re-render Cascade** (seluruh tree dari `<App />` hingga daun terdalam dikalkulasi ulang).
- Memory footprint melonjak 80 MB karena pembuatan ulang inline styles di 4.000+ active DOM/Native nodes.
- Frame rate anjlok hingga 18 FPS selama transisi, menghasilkan UX "layar putih" sesaat.

#### Solusi Arsitektural:
Migrasi ke **Unistyles Architecture (JSI Hybrid Pattern)** yang mendaftarkan tokens langsung ke C++ runtime engine tanpa re-render massal tree React.

```tsx
// src/styles/unistyles.ts
import { UnistylesRegistry } from 'react-native-unistyles';
import { DesignTokens } from '../theme/tokens';

export const lightTheme = {
  colors: DesignTokens.colors.light,
  spacing: DesignTokens.spacing,
  radii: DesignTokens.radii,
};

export const darkTheme = {
  colors: DesignTokens.colors.dark,
  spacing: DesignTokens.spacing,
  radii: DesignTokens.radii,
};

type AppThemes = {
  light: typeof lightTheme;
  dark: typeof darkTheme;
};

declare module 'react-native-unistyles' {
  export interface UnistylesThemes extends AppThemes {}
}

UnistylesRegistry
  .addThemes({
    light: lightTheme,
    dark: darkTheme,
  })
  .addConfig({
    adaptiveThemes: true,
  });
```

```tsx
// src/components/AccountSummaryCard.tsx
import React from 'react';
import { View, Text } from 'react-native';
import { createStyleSheet, useStyles } from 'react-native-unistyles';

interface AccountCardProps {
  accountNumber: string;
  balance: string;
  isPriority: boolean;
}

export const AccountSummaryCard: React.FC<AccountCardProps> = React.memo(({
  accountNumber,
  balance,
  isPriority,
}) => {
  const { styles } = useStyles(stylesheet, { isPriority });

  return (
    <View style={styles.container}>
      <Text style={styles.accountNumberLabel}>{accountNumber}</Text>
      <Text style={styles.balanceText}>{balance}</Text>
    </View>
  );
});

AccountSummaryCard.displayName = 'AccountSummaryCard';

const stylesheet = createStyleSheet((theme) => ({
  container: {
    backgroundColor: theme.colors.backgroundPrimary,
    padding: theme.spacing.lg,
    borderRadius: theme.radii.md,
    variants: {
      isPriority: {
        true: {
          borderWidth: 2,
          borderColor: theme.colors.accent,
        },
        false: {
          borderWidth: 1,
          borderColor: '#E2E8F0',
        },
      },
    },
  },
  accountNumberLabel: {
    fontSize: 12,
    color: theme.colors.textPrimary,
    marginBottom: theme.spacing.xs,
  },
  balanceText: {
    fontSize: 24,
    fontWeight: 'bold',
    color: theme.colors.textPrimary,
  },
}));
```

#### Hasil:
- Pindah tema terjadi dalam **0 frame drop** (tetap locked pada 60/120 FPS).
- Root component tidak perlu di-mount ulang.
- CPU consumption pada Main Thread berkurang sebesar **42%**.

---

### 9. Trade-offs

| Pendekatan Styling | Kelebihan | Kelemahan | Dampak Memori & Garbage Collection | Ideal Digunakan Pada |
| :--- | :--- | :--- | :--- | :--- |
| **`StyleSheet.create` (Built-in RN)** | • Zero dependency eksternal<br>• Kecepatan parsing tercepat<br>• Sangat stabil | • Kurang ergonomis untuk responsive/theme dinamis<br>• Menuntut boilerplate code manual | **Sangat Rendah**<br>Semua styles dialokasikan sekali saat engine load. | Komponen UI statis, SDK performa tinggi, Library pihak ketiga. |
| **`NativeWind v4` (Tailwind)** | • Developer Experience (DX) luar biasa cepat<br>• Berbasis Tailwind CSS mental model<br>• Optimasi compile-time | • Dependensi build pipeline ketat (Babel/Metro plugin)<br>• Error compile-time sulit di-debug jika konfigurasi tailwind bermasalah | **Rendah**<br>Di-compile mendekati pure `StyleSheet` via CSS Interop. | Aplikasi enterprise dengan tim multi-platform (Web & Mobile). |
| **`react-native-unistyles`** | • Kecepatan dynamic theme mendekati native (C++ based)<br>• Dukungan breakpoints & dynamic variants deklaratif | • Mengandalkan custom C++ code via JSI (membutuhkan New Architecture/JSI)<br>• Kurva belajar custom styling schema | **Sangat Rendah (JS Heap)**<br>Overhead dialihkan ke native C++ stack memory. | Aplikasi enterprise multi-brand kompleks dengan pergantian tema runtime intensif. |
| **Runtime CSS-in-JS (`styled-components`, `emotion`)** | • Fleksibilitas dynamic props berbasis tagged template literals tinggi | • Runtime overhead parah<br>• Re-parsing string CSS di JS thread pada setiap render | **Sangat Tinggi**<br>Membuat GC Hermes tertekan, potensi layout thrashing masif. | **Hindari** untuk sistem enterprise modern. |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Dynamic Styles Melalui Callback Objek di Setiap Render
```tsx
// ❌ WRONG: Menghasilkan objek baru pada setiap pass render
<View style={getContainerStyle(isActive)} />

// Solusi: Gunakan style flattening arrays dengan referensi stabil
<View style={[styles.base, isActive && styles.active]} />
```

#### Mistake 2: Missing Flex Basis / Parent Height pada Deep Flexbox Hierarchies
**Gejala:** Komponen tidak muncul (tinggi 0) pada layar Android tapi muncul di iOS.  
**Akar Masalah:** Yoga Engine menangani unconstrained layout secara berbeda jika root view tidak memiliki `flex: 1` atau dimensi eksplisit saat anak memiliki styling `flex: 1`.  
**Troubleshooting:** Pastikan wrapper hierarki paling atas menerapkan `flex: 1` atau menggunakan styling `flexGrow: 1` untuk viewport container berbasis ScrollView.

#### Mistake 3: Layout Thrashing Melalui Excessive `onLayout` Hooks
**Gejala:** Animasi tersendat (*stuttering*) saat transisi screen.  
**Akar Masalah:** Menghitung koordinat elemen menggunakan event `onLayout` di JavaScript layer, lalu menyimpannya ke local state:
```tsx
// ❌ ANTI-PATTERN
const [width, setWidth] = useState(0);
return <View onLayout={(e) => setWidth(e.nativeEvent.layout.width)} style={{ width: width * 0.5 }} />;
```
Setiap kali layout selesai di native, event dilempar ke JS, state di-update, memicu re-render Fiber, mengirim pembaruan ke C++, dan memicu relayout di Yoga. Ini adalah infinite/multi-pass loop.  
**Solusi:** Gunakan kalkulasi berbasis persentase bawaan Yoga Flexbox (`width: '50%'`) atau gunakan Native Layout Measurements dari library animasi UI yang berjalan langsung di UI thread (seperti React Native Reanimated `measure`).

---

### 11. Best Practices (Production Checklist)

- [ ] **Zero Inline Object Literals:** Pastikan tidak ada inline style object `{ margin: 10 }` pada virtual list (`FlatList`, `FlashList`) item renders.
- [ ] **Strict Memoization Contracts:** Gunakan `React.memo` dengan shallow equality checks pada atomic design components (`Text`, `Button`, `Badge`).
- [ ] **Theme Isolation:** Jangan gunakan global Context murni untuk mengekspos variabel warna secara dinamis jika app memiliki >100 views per screen; gunakan C++-backed dynamic storage (seperti Unistyles) atau scoped context updates.
- [ ] **No Over-flexing:** Hindari penggunaan `flex: 1` yang bertumpuk hingga >10 level kedalaman. Setiap nesting flex memperlambat recursive layout pass pada Yoga Engine.
- [ ] **Layout Animation via Native Driver:** Jalankan styling perubahan posisi/opacity secara eksklusif menggunakan driver native (`useNativeDriver: true` atau Reanimated worklets).
- [ ] **Style Flattening Guards:** Hindari penggunaan `StyleSheet.flatten()` di dalam loop atau render method berulang, karena membatalkan optimasi integer-ID lookup Fabric native layer.

---

### 12. Hands-on Practice

Mari bangun sebuah modular design engine atomik yang mengisolasi render tree dari layout cost di direktori project: `hands-on/m02/`.

#### Langkah 1: Inisialisasi Project Directory
Jalankan di root workspace Anda:
```bash
mkdir -p hands-on/m02/src/components
mkdir -p hands-on/m02/src/theme
```

#### Langkah 2: Buat Token Definition File
Simpan kode berikut di `hands-on/m02/src/theme/tokens.ts`:
```typescript
export const Tokens = {
  colors: {
    brand: {
      primary: '#0D9488',
      secondary: '#14B8A6',
    },
    neutral: {
      50: '#F8FAFC',
      500: '#64748B',
      900: '#0F172A',
    },
  },
  space: {
    4: 4,
    8: 8,
    16: 16,
    24: 24,
  },
  radii: {
    base: 6,
    pill: 9999,
  },
} as const;
```

#### Langkah 3: Bangun Atomic Surface Component
Simpan kode berikut di `hands-on/m02/src/components/EnterpriseSurface.tsx`:
```tsx
import React, { useMemo } from 'react';
import { View, StyleSheet, StyleProp, ViewStyle, DimensionValue } from 'react-native';
import { Tokens } from '../theme/tokens';

export interface EnterpriseSurfaceProps {
  padding?: keyof typeof Tokens.space;
  width?: DimensionValue;
  elevation?: 1 | 2 | 3;
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}

export const EnterpriseSurface = React.memo<EnterpriseSurfaceProps>(({
  padding = 16,
  width = '100%',
  elevation = 1,
  children,
  style,
}) => {
  const dynamicElevationStyle = useMemo(() => {
    switch (elevation) {
      case 1:
        return styles.elevation1;
      case 2:
        return styles.elevation2;
      case 3:
        return styles.elevation3;
      default:
        return styles.elevation1;
    }
  }, [elevation]);

  return (
    <View
      style={[
        styles.base,
        {
          padding: Tokens.space[padding],
          width,
        },
        dynamicElevationStyle,
        style,
      ]}
    >
      {children}
    </View>
  );
});

EnterpriseSurface.displayName = 'EnterpriseSurface';

const styles = StyleSheet.create({
  base: {
    backgroundColor: Tokens.colors.neutral[50],
    borderRadius: Tokens.radii.base,
  },
  elevation1: {
    shadowColor: Tokens.colors.neutral[900],
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1, // Android Platform Support
  },
  elevation2: {
    shadowColor: Tokens.colors.neutral[900],
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 6,
    elevation: 3,
  },
  elevation3: {
    shadowColor: Tokens.colors.neutral[900],
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.15,
    shadowRadius: 15,
    elevation: 6,
  },
});
```

#### Langkah 4: Uji Integrasi pada View Utama
Simpan kode berikut di `hands-on/m02/src/App.tsx`:
```tsx
import React, { useState } from 'react';
import { SafeAreaView, Text, Button, StyleSheet } from 'react-native';
import { EnterpriseSurface } from './components/EnterpriseSurface';

export const App = () => {
  const [level, setLevel] = useState<1 | 2 | 3>(1);

  return (
    <SafeAreaView style={styles.container}>
      <EnterpriseSurface padding={24} elevation={level}>
        <Text style={styles.heading}>Enterprise Design Architecture</Text>
        <Text style={styles.body}>Current Elevation Level: {level}</Text>
        <Button
          title="Tingkatkan Elevasi"
          onPress={() => setLevel((prev) => (prev === 3 ? 1 : ((prev + 1) as 1 | 2 | 3)))}
        />
      </EnterpriseSurface>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#E2E8F0',
  },
  heading: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  body: {
    fontSize: 14,
    color: '#475569',
    marginBottom: 16,
  },
});

export default App;
```

---

### 13. Exercise

#### Level Easy
Ekstrak komponen `Badge` dari token styling yang telah dibuat di Hands-on Practice. Komponen harus menerima prop `variant: 'primary' | 'neutral'` dan merender teks dengan background yang sesuai dari `Tokens.colors` tanpa inline dynamic styling objects.

#### Level Medium
Buat sebuah responsive grid component bernama `FlexGrid` yang menerima prop `columns: 2 | 3 | 4`. Komponen harus menghitung layout item secara efisien menggunakan Flexbox wrapping murni di Yoga Engine (`flexWrap: 'wrap'`), tanpa memicu pemanggilan event `onLayout` di JavaScript layer.

#### Level Hard
Rancang custom hook `useScreenOrientationStyle` yang mendengarkan perubahan orientasi layar (`Dimensions`). Hook ini harus mengembalikan referensi `StyleSheet` yang di-cache menggunakan `useMemo` sehingga re-render hanya dipicu satu kali per rotasi layar dan tidak memicu layout invalidation pada static sibling views.

---

### 14. Challenge

**Skenario Kasus Kompleks:**  
Anda adalah Lead Mobile Architect pada aplikasi super-app logistik. Aplikasi memiliki layar "Live Dispatch Tracker" dengan daftar dinamis yang berisi 500+ entitas armada kendaraan dalam format FlashList. Setiap item memiliki data telemetri yang diperbarui setiap 200ms melalui WebSocket.

**Tantangan:**
1. Desain arsitektur atomic component untuk entitas armada tersebut. Komponen harus memiliki 4 state visual yang berbeda berdasarkan kecepatan kendaraan: *Idle*, *Normal*, *Speeding*, dan *Critical*.
2. State visual ini tidak boleh menggunakan inline style object.
3. Anda tidak diperbolehkan me-mount ulang (*unmount/mount*) child native views ketika armada beralih state.
4. Render time per item harus di bawah **2ms** di perangkat Android level low-end (e.g., spesifikasi setara Snapdragon 450).
5. Buat architectural blueprint tertulis beserta implementasi komponen TypeScript-nya yang membuktikan efisiensi memori, mematuhi kontrak Fiber reconciliation, dan mengeliminasi layout thrashing pada pipeline Yoga C++.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. Apa fungsi utama Yoga Engine dalam arsitektur rendering React Native?
   - a) Mengeksekusi bytecode JavaScript secara asinkron.
   - b) Menghitung tata letak W3C Flexbox menjadi koordinat absolut piksel secara native di C++.
   - c) Mengubah file gambar bitmap menjadi vector displayable.
   - d) Mengelola siklus Garbage Collection pada Hermes runtime.

2. Mengapa penggunaan inline styling seperti `style={{ margin: 10 }}` dianggap anti-pattern di production view?
   - a) Karena React Native menolak merender komponen yang memiliki inline styles.
   - b) Karena setiap siklus render mengalokasikan referensi objek memori baru di JS Heap, memicu overhead Hermes GC.
   - c) Karena inline style tidak kompatibel dengan arsitektur Android ViewGroup.
   - d) Karena Yoga Engine tidak dapat memetakan objek yang tidak dibuat via `StyleSheet.create`.

3. Pada fase React rendering manakah mutasi native tree dikirim secara langsung ke Fabric Shadow Tree?
   - a) Render Phase
   - b) Commit Phase
   - c) Reconciliation Interruption
   - d) Layout Pass Callback

4. Properti flex CSS mana yang diimplementasikan secara default bernilai `column` di React Native, berbeda dengan standar Web CSS?
   - a) `justifyContent`
   - b) `alignItems`
   - c) `flexDirection`
   - d) `flexWrap`

5. Apa kegunaan utama dari metode `StyleSheet.create` dibanding objek JavaScript biasa?
   - a) Memastikan enkripsi style sheet agar tidak dapat dibaca reverse-engineering.
   - b) Mengoptimalkan alokasi ID/Bridge/C++ caching, serta menyediakan validasi tipe dan auto-complete.
   - c) Menjalankan rendering langsung ke GPU tanpa melewati Yoga.
   - d) Mengubah satuan pixel density (`dp`) menjadi `rem`.

---

#### Intermediate (5 Pertanyaan)
6. Bagaimana cara kerja arsitektur *Unistyles* atau styling berbasis C++ TurboModule dalam mengeliminasi delay pergantian tema aplikasi?
   - a) Mengubah file CSS pada bundle Metro secara live-reload.
   - b) Menyimpan data tema di C++ layer dan memutasi props Fabric secara langsung tanpa memicu re-render cascading di seluruh Fiber tree.
   - c) Menghapus cache memory Hermes saat dark mode diaktifkan.
   - d) Menggunakan service worker mobile untuk merender ulang halaman di background thread.

7. Perhatikan potongan kode berikut:
   ```tsx
   const Card = ({ active }) => (
     <View style={[styles.card, active && styles.active]} />
   );
   ```
   Jika `active` bernilai `false`, apa yang diterima oleh pipeline styling React Native?
   - a) Melempar Exception `NullPointerException`.
   - b) Nilai `false` diabaikan oleh array parser internal React Native tanpa merusak susunan hierarki layout.
   - c) Menghapus class `styles.card` dari memory stack.
   - d) Memaksa Yoga untuk merender elemen transparan selebar 0 piksel.

8. Mengapa `onLayout` hook berpotensi memicu masalah performa (layout thrashing) jika digunakan untuk layout responsif dinamis?
   - a) Karena `onLayout` berjalan di Web Worker terpisah.
   - b) Karena membutuhkan perjalanan round-trip: Native Layout Pass $\rightarrow$ Serialized Event ke JS $\rightarrow$ State Update $\rightarrow$ Re-render $\rightarrow$ Native Layout Pass baru.
   - c) Karena `onLayout` memblokir Hermes GC agar tidak berjalan selamanya.
   - d) Karena nilai koordinat yang dikembalikan selalu tidak akurat di platform Android.

9. Manakah di antara pernyataan berikut yang mendeskripsikan perilaku React Native Fabric Shadow Tree secara tepat?
   - a) Shadow Tree bersifat *mutable* dan dapat diubah langsung oleh JavaScript thread kapan saja.
   - b) Shadow Tree bersifat *immutable*, thread-safe, dan memungkinkan operasi kalkulasi layout C++ paralel tanpa memblokir interaksi UI.
   - c) Shadow Tree berjalan di atas WebKit rendering engine bawaan platform host.
   - d) Shadow Tree menggantikan sepenuhnya peran Yoga layout engine di C++.

10. Apa dampak memori dari runtime CSS-in-JS (seperti `styled-components/native`) dibanding static styling approach di React Native?
    - a) Tidak ada dampak, keduanya menghasilkan machine code yang identik.
    - b) Runtime CSS-in-JS meningkatkan beban JS Heap secara dramatis karena melakukan parsing dynamic style rules berulang kali pada setiap siklus render komponen.
    - c) Runtime CSS-in-JS sepenuhnya dieksekusi oleh native C++ GPU shader.
    - d) Static styling membutuhkan memori lebih besar karena semua styles di-load di awal.

---

#### Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario 1:** Tim Anda mendeteksi bahwa layar katalog produk mengalami degradasi frame rate parah (rata-rata 24 FPS) saat pengguna melakukan *fast scrolling* pada `FlashList`. Setiap card item menggunakan puluhan ternary operator inline untuk layout (`style={{ padding: isTablet ? 20 : 10, margin: hasPromo ? 8 : 4 }}`).  
    Sebagai Software Architect, mitigasi apa yang paling efektif dan scalable untuk diterapkan oleh tim engineering?
    - a) Mengaktifkan dynamic memory swapping di Android Manifest.
    - b) Mengisolasi variasi gaya ke dalam static atomic styles dengan multi-class combining, dan membungkus item renderer dengan `React.memo` yang memeriksa shallow property equality.
    - c) Mengubah format gambar pada katalog produk menjadi vector SVG murni.
    - d) Menghapus batasan `maxItemsToRender` pada FlashList agar semua dirender sekaligus di awal.

12. **Skenario 2:** Aplikasi perbankan Anda harus mendukung rotasi layar dinamis pada perangkat Tablet dan Lipat (Foldable). Penggunaan kalkulasi layout manual di JS menghasilkan *visual lag* di mana tata letak card terpotong selama 150-300ms setelah perangkat selesai diputar secara fisik.  
    Solusi arsitektur manakah yang mengeliminasi visual lag tersebut?
    - a) Menggunakan percentage-based dan flexbox layout murni yang diproses langsung oleh Yoga Engine di C++ tanpa menunggu event layout JavaScript berputar balik.
    - b) Memaksa orientasi aplikasi terkunci ke portrait saja via platform manifest.
    - c) Menambahkan timeout 300ms di JavaScript sebelum menampilkan UI yang baru.
    - d) Mengganti seluruh komponen React Native menjadi WebView HTML5 responsive.

13. **Skenario 3:** Sebuah super-app mengalami kebocoran memori (Memory Leak) bertahap pada production environment yang menyebabkan app crash (OOM) setelah dipakai continuous selama 20 menit. Profiling memory menunjukkan jutaan string styling yang di-retain pada Hermes heap, diasosiasikan dengan Dynamic Context Theming.  
    Apa sumber masalah arsitekturalnya dan bagaimana memperbaikinya?
    - a) React Native engine rusak; harus downgrade versi SDK.
    - b) Provider tema menginstansiasi objek `StyleSheet` baru di dalam body komponen setiap kali render loop terpicu, mencegah GC membebaskan memori; perbaikannya adalah mengekstraksi stylesheet di luar lifecycle komponen atau memanfaatkan dynamic reference lookup berbasis singleton token registry.
    - c) Dynamic Context Theming tidak boleh digunakan bersamaan dengan TypeScript.
    - d) Hermes engine tidak memiliki Garbage Collector otomatis untuk object context.

---

### Kunci Jawaban Quiz

#### Basic
1. **b** — Yoga Engine menghitung aturan W3C Flexbox menjadi posisi pixel absolut $(x, y, w, h)$ di layer native C++.
2. **b** — Setiap render pass menginstansiasi referensi objek baru, memicu pressure tinggi pada memory heap dan memicu GC pause.
3. **b** — Mutasi pohon Virtual DOM/Fiber dikomit ke C++ Shadow Tree saat Commit Phase.
4. **c** — React Native menggunakan `flexDirection: 'column'` secara default, berbanding terbalik dengan Web CSS yang menggunakan `row`.
5. **b** — `StyleSheet.create` mengoptimalkan mapping style ke integer/ID references, memastikan validasi type-check ketat, dan meminimalkan memory thrashing.

#### Intermediate
6. **b** — Engine berbasis C++ berkomunikasi via JSI langsung dengan shadow node tanpa memicu broad-spectrum Fiber re-renders di JavaScript thread.
7. **b** — Parser array internal React Native mengevaluasi falsy values (`false`, `null`, `undefined`) sebagai no-op tanpa memicu error atau rendering layout tambahan.
8. **b** — `onLayout` mengharuskan native event dikirim via bridge/JSI kembali ke JS thread, memicu state update, rekonsiliasi baru, dan round-trip layout pass tambahan.
9. **b** — Fabric Shadow Tree bersifat immutable dan thread-safe, memastikan C++ core dapat menghitung kalkulasi secara asinkron tanpa thread locking dengan main thread.
10. **b** — Runtime CSS-in-JS mengeksekusi string interpolation dan regex token matching di JS thread pada setiap cycle rendering, menghambat Hermes heap.

#### Skenario Kasus Produksi
11. **b** — Menghilangkan anonymous object allocations dengan static pre-defined style rules dan memanfaatkan shallow equality guards (`React.memo`) meminimalisir overhead render path secara instan.
12. **a** — Melimpahkan perhitungan responsive geometry ke Yoga Engine (C++) menghindari round-trip latency ke JS thread, memastikan frame tersinkronisasi tepat pada saat OS window manager melakukan transformasi tampilan.
13. **b** — Pembuatan dynamic `StyleSheet` di dalam functional component body mengikat referensi closure baru ke heap memori secara tak terbatas setiap kali dependency context berubah; solusinya adalah mengangkat deklarasi stylesheet ke luar render tree atau menggunakan token cache manager yang stabil.

---

### 16. Summary

1. **Pipeline Deklaratif Fabric & Yoga Engine:**  
   UI di React Native dieksekusi secara deklaratif di JavaScript, ditranslasikan melalui JSI ke bentuk immutable C++ Shadow Tree, lalu dihitung koordinat geometris absolutnya secara native oleh **Yoga Layout Engine** sebelum dicerminkan ke views sistem operasi platform host.
2. **Eliminasi Memory Heap Garbage Collection Pressure:**  
   Penyebab utama jank dan frame drop di UI berdensitas tinggi adalah alokasi objek dinamis (inline styles) yang memicu siklus pembersihan Hermes Garbage Collector. Komponen kelas enterprise wajib memisahkan static visual declarations dari dynamic runtime conditions.
3. **Arsitektur Theming Modern Bertingkat Tinggi:**  
   Menghindari cascading re-renders skala luas akibat pergantian tema global dicapai dengan beralih dari dynamic React Context murni ke arsitektur berbasis native C++ TurboModules/JSI (seperti *Unistyles*) atau zero-runtime compilation (seperti *NativeWind v4* via CSS Interop).
4. **Isolasi Layout Pass:**  
   Mengandalkan Flexbox bawaan Yoga jauh lebih efisien daripada melakukan pengukuran dimensi manual melalui event `onLayout` di JavaScript thread. Menghilangkan round-trip JS-to-Native loop adalah kunci mencapai locked 60/120 FPS performa mobile native.