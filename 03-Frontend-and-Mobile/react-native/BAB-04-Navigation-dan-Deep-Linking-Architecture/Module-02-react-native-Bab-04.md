# BAB 04: Navigation & Deep Linking Architecture
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Merancang Topologi Navigasi Berlapis (Multi-tier Navigation Topology)**: Mengimplementasikan kombinasi Native Stack, Bottom Tabs, dan Modal Flow dengan isolasi *state* modular dan *zero memory leakage*.
2. **Membangun Arsitektur Deep Linking Skala Enterprise**: Mengonfigurasi Universal Links (iOS) dan Android App Links (Android) dengan sistem resolusi path deterministik, *fallback routing*, dan *payload sanitization*.
3. **Menerapkan Strict End-to-End Type Safety**: Menyusun kontrak navigasi TypeScript tingkat lanjut (*discriminated unions*, *composite screen props*, dan *nested navigator params inference*) yang mengeliminasi *runtime route errors*.
4. **Mengoptimalkan Lifecycle & Performa Rendering Navigasi**: Mengintegrasikan `react-native-screens` dengan arsitektur Fabric/JSI untuk meminimalkan *overdraw*, mengatur *view recycling*, serta mengaktifkan *screen freeze* pada *background stack*.
5. **Mengimplementasikan Navigation State Persistence & Hydration**: Membangun mekanisme pemulihan state navigasi deterministik dengan validasi skema runtime untuk penanganan *crash-recovery* dan *seamless user re-engagement*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* Fundamental React Native: Siklus hidup komponen, Hooks (`useCallback`, `useMemo`, `useRef`), dan React Context API.
* TypeScript Tingkat Lanjut: Generics, Mapped Types, Conditional Types, dan Utility Types (`Extract`, `Exclude`, `Parameters`).
* Native OS Application Lifecycle:
  * **Android**: `Activity`, `Intent`, `Task`, `BackStack`, `launchMode` (`standard`, `singleTop`, `singleTask`, `singleInstance`).
  * **iOS**: `UIViewController`, `UINavigationController`, `AppDelegate`, `SceneDelegate`, `NSUserActivity`.
* Pemahaman dasar arsitektur React Native (Bridge vs JSI/Fabric Engine).

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi navigasi modern di React Native terbagi menjadi dua paradigma utama: **JS-based Navigation** (`@react-navigation/stack`) dan **Native-backed Navigation** (`@react-navigation/native-stack` yang didukung oleh `react-native-screens`). Pada lingkungan enterprise, Native-backed Navigation merupakan standar *de facto* untuk memastikan performa native 60/120 FPS.

```
+-------------------------------------------------------------------------+
|                          JavaScript Thread                              |
|  +-------------------------------------------------------------------+  |
|  |                 Navigation State Tree (Redux/State)               |  |
|  |   { index: 1, routes: [{ name: 'Home' }, { name: 'Profile' }] }    |  |
|  +---------------------------------+---------------------------------+  |
|                                    |                                    |
|                                    | JSI / TurboModules                 |
+------------------------------------v------------------------------------+
|                           C++ / Fabric Core                             |
|  +-------------------------------------------------------------------+  |
|  |                 RNSScreenStack / ComponentDescriptor              |  |
|  +---------------------------------+---------------------------------+  |
|                                    |                                    |
+------------------------------------v------------------------------------+
|                           Native OS UI Layer                            |
|       +----------------------------+----------------------------+       |
|       |          Android           |            iOS             |       |
|       |  Fragment / FragmentTrans. |  UIViewController / NavCtx |       |
|       +----------------------------+----------------------------+       |
+-------------------------------------------------------------------------+
```

#### A. Native View Hierarchy & JSI Synchronization
Ketika sebuah rute di-push ke dalam `@react-navigation/native-stack`:
1. Navigasi JavaScript mengevaluasi *Navigation State Tree*.
2. Melalui JSI (JavaScript Store Interface), instruksi perubahan state ditransmisikan secara langsung (sinkron) ke *native shadow tree* tanpa serialisasi JSON asynchronous seperti pada arsitektur Bridge klasik.
3. Di sisi Android, `react-native-screens` memetakan komponen `Screen` ke native Android `Fragment` di dalam `ScreenContainerViewManager`. Transisi stack dijalankan langsung oleh native `FragmentManager.beginTransaction()`.
4. Di sisi iOS, setiap `Screen` dipetakan ke native `RNSScreen` yang merupakan turunan dari `UIViewController`. Transisi dikelola langsung oleh native `UINavigationController`.
5. **Screen Freezing Engine**: Ketika layar tidak aktif (tertutup oleh layar baru di stack), `react-native-screens` memanfaatkan mekanisme `react-freeze`. Komponen React pada layar yang tertimbun di-suspend dari siklus render React, sehingga perubahan state global tidak akan memicu re-render di layar latar belakang tersebut.

#### B. Resolusi Deep Link Native OS ke JavaScript Runtime
Deep linking bukan sekadar pembacaan string URL, melainkan orkestrasi siklus hidup native OS:

```
[Incoming External URL: https://app.enterprise.com/orders/8841]
                               |
                               v
+-------------------------------------------------------------+
| OS Entrypoint Level                                         |
| - Android: Intent Filter (android.intent.action.VIEW)       |
| - iOS: NSUserActivity / Universal Link verification         |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Native App Delegate / Activity Lifecycle Hook               |
| - Android: MainActivity.onNewIntent() / onCreate()          |
| - iOS: application:continueUserActivity:restorationHandler:  |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Linking Module (TurboModule / Native Module)                |
| - Emits event ke JavaScript Runtime                         |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Navigation State Compiler (React Navigation LinkingEngine) |
| 1. Path Matcher (Regex / Trie traversal)                    |
| 2. Parameter Extraction & Normalization                     |
| 3. Auth Guard & Redirection Pipeline                        |
| 4. Navigation State Synthesis (Root -> Tab -> Stack)        |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Target Screen Mount & Side-Effect Dispatch                  |
+-------------------------------------------------------------+
```

1. **Cold Boot vs Warm Boot**:
   * *Cold Boot*: OS membuat proses baru. Native runtime memanggil `Linking.getInitialURL()`. JS thread membaca URL ini sebelum navigasi pertama dirender.
   * *Warm/Hot Boot*: Aplikasi sudah berada di memory/background. OS memicu `onNewIntent` (Android) atau callback `continueUserActivity` (iOS). Native module memancarkan event `url` melalui `Linking.addEventListener('url', ...)`.
2. **State Synthesis**: URL linear (misal: `/app/orders/8841`) harus ditransformasi menjadi struktur hierarki navigasi nested:
   ```json
   {
     "routes": [
       {
         "name": "AuthenticatedTab",
         "state": {
           "routes": [
             {
               "name": "OrdersTab",
               "state": {
                 "routes": [
                   { "name": "OrdersListScreen" },
                   { "name": "OrderDetailScreen", "params": { "orderId": "8841" } }
                 ]
               }
             }
           ]
         }
       }
     ]
   }
   ```

---

### 4. Why & What

#### Mengapa Pola Navigasi Naif Gagal di Skala Enterprise?
1. **Memory Bloat & Crash (OOM)**: Navigasi naif sering kali me-mount screen bertingkat tanpa mekanisme pelepasan native view atau suspend render, memicu OOM (Out of Memory) crash pada device Android low-end (RAM ≤ 3GB).
2. **Broken Navigation State Tree**: Tanpa isolasi state yang ketat, notifikasi push atau deep link dapat memicu navigasi ganda (double-mount) atau navigasi yang menimpa alur autentikasi aktif.
3. **Implicit/String-based Routing**: Menggunakan string mentah (misal: `navigation.navigate('Detail', { id: 1 })`) menyebabkan regresi silent saat terjadi refactoring nama route atau modifikasi tipe payload.

#### Apa yang Dibangun dalam Arsitektur Ini?
* **Type-Safe Contract Hub**: Single source of truth untuk seluruh rute aplikasi menggunakan tipe TypeScript rekursif.
* **Deterministic Deep Link Router**: Mesin routing yang menjamin URL publik dapat diterjemahkan secara presisi ke dalam nested state tanpa memotong riwayat back-stack native.
* **Secure Navigation Gatekeeper**: Interseptor rute untuk verifikasi token, status registrasi biometrik, dan *permission check* sebelum Native View Controller dialokasikan di memory.

---

### 5. How (Workflow Detail)

1. **Inisialisasi Native Configuration**:
   * Menyiapkan file konfigurasi domain verification: `assetlinks.json` (Android) dan `apple-app-site-association` (iOS).
   * Menyesuaikan `AndroidManifest.xml` dengan `android:launchMode="singleTask"` guna mencegah replikasi `MainActivity`.
2. **Konstruksi Typings Core**:
   * Mendefinisikan `RootStackParamList`, `AuthStackParamList`, dan `MainTabParamList`.
   * Melakukan registrasi global type augmentation via `declare global { namespace ReactNavigation { ... } }`.
3. **Membangun Linking Configuration**:
   * Mengatur `prefixes` (Custom scheme + Universal/App Link domains).
   * Mendefinisikan `config.screens` secara deklaratif untuk pemetaan path linear ke navigasi hierarkis.
4. **Implementasi State Serialization & Guards**:
   * Melakukan persistensi state navigasi ke storage aman untuk restorasi sesi crash.
   * Mengintegrasikan conditional rendering pada Root Navigator berbasis state autentikasi (Auth vs App).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Transit Bandara Internasional (Hub-and-Spoke)
Bayangkan sebuah bandara internasional:
* **Root Navigator (Pintu Masuk Utama/Imigrasi)**: Memeriksa visa dan paspor (Status Autentikasi). Anda tidak bisa masuk ke terminal penerbangan (Main App) tanpa lolos imigrasi.
* **Bottom Tab Navigator (Terminal Antar-Wilayah)**: Terminal 1, Terminal 2, Terminal 3. Semua berjalan paralel, mempertahankan status gate dan ruang tunggu masing-masing.
* **Native Stack (Gate Menuju Pesawat / Lorong Belakang)**: Lorong satu arah menuju pesawat. Setiap pintu baru menutupi pintu lama. Jika Anda mundur, Anda kembali ke lorong sebelumnya.
* **Deep Link (Tiket Khusus Masuk Cepat)**: Tamu VIP yang mendarat langsung diinstruksikan oleh petugas bandara menuju Terminal 2 -> Gate 4 tanpa harus bingung mencari jalan dari pintu masuk terminal dasar, namun tetap melewati pemeriksaan imigrasi otomatis jika visa belum diverifikasi.

#### Diagram Interaksi Deep Link Runtime

```
[Universal Link Triggered]
           |
           v
+----------------------+
| Android/iOS Native   |
+----------+-----------+
           |
           v
+-------------------------------------------------------+
| React Native Linking Middleware                       |
+--------------------------+----------------------------+
                           |
                           v
+-------------------------------------------------------+
| Zod URL & Payload Schema Validator                    |
| - Parse Path: /orders/:orderId                        |
| - Verify: orderId is UUID, Token is Active            |
+--------------------------+----------------------------+
          | OK                     | Invalid / Tampered
          v                        v
+----------------------+   +----------------------------+
| Is User Authenticated?|   | Drop & Redirect to Fallback|
+----------+-----------+   +----------------------------+
    YES    |      | NO
           |      +---------------------+
           |                            |
           v                            v
+----------------------+   +----------------------------+
| Target Screen Stack  |   | Cache DeepLink Intent      |
| Push [Home -> Order] |   | -> Mount Auth Screen       |
+----------------------+   | -> Resolve Post-Login      |
                           +----------------------------+
```

---

### 7. Simple Example & Practical Example (Standar Industri)

#### A. Strict Type-Safe Navigation Contracts (`src/navigation/types.ts`)

```typescript
import type {
  NavigatorScreenParams,
  CompositeScreenProps,
} from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { BottomTabScreenProps } from '@react-navigation/bottom-tabs';

// 1. Tab Navigator Types
export type MainTabParamList = {
  FeedTab: undefined;
  OrdersTab: undefined;
  ProfileTab: undefined;
};

// 2. Orders Stack Types (Nested inside Tab)
export type OrdersStackParamList = {
  OrderHistory: undefined;
  OrderDetail: { readonly orderId: string; readonly source?: 'push' | 'deep_link' };
  OrderTracking: { readonly orderId: string; readonly trackingNumber: string };
};

// 3. Root Stack Types
export type RootStackParamList = {
  Auth: undefined;
  Main: NavigatorScreenParams<MainTabParamList>;
  OrdersFlow: NavigatorScreenParams<OrdersStackParamList>;
  NotFound: undefined;
};

// 4. Global Declaration for Type-Safe `useNavigation()`
declare global {
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}

// 5. Composite Screen Props Helpers
export type OrderDetailScreenProps = CompositeScreenProps<
  NativeStackScreenProps<OrdersStackParamList, 'OrderDetail'>,
  CompositeScreenProps<
    BottomTabScreenProps<MainTabParamList>,
    NativeStackScreenProps<RootStackParamList>
  >
>;
```

#### B. Production Enterprise Linking Engine (`src/navigation/linking.ts`)

```typescript
import { LinkingOptions } from '@react-navigation/native';
import { Linking } from 'react-native';
import { z } from 'zod';
import { RootStackParamList } from './types';

// Validasi skema payload runtime untuk mengamankan Deep Links dari input injection
export const OrderDetailPayloadSchema = z.object({
  orderId: z.string().uuid(),
  source: z.enum(['push', 'deep_link']).optional(),
});

export const enterpriseLinkingConfig: LinkingOptions<RootStackParamList> = {
  prefixes: [
    'enterpriseapp://',
    'https://mobile.enterprise.com',
    'https://*.enterprise.page.link',
  ],
  config: {
    screens: {
      Auth: 'auth',
      Main: {
        screens: {
          FeedTab: 'feed',
          OrdersTab: 'orders',
          ProfileTab: 'profile',
        },
      },
      OrdersFlow: {
        path: 'orders-flow',
        screens: {
          OrderHistory: 'history',
          OrderDetail: {
            path: 'detail/:orderId',
            parse: {
              orderId: (orderId: string) => {
                // Parsing dan validasi inline
                const validation = z.string().uuid().safeParse(orderId);
                if (!validation.success) {
                  // Fallback fallback ID atau return empty string untuk penanganan fallback
                  return 'INVALID_ID';
                }
                return validation.data;
              },
            },
          },
          OrderTracking: 'tracking/:orderId/:trackingNumber',
        },
      },
      NotFound: '*',
    },
  },
  // Custom subscriber untuk intercepting, logging, dan telemetry
  subscribe(listener) {
    const onReceiveURL = ({ url }: { url: string }) => {
      // Telemetry / Security audit log
      console.info(`[Navigation Engine] Deep Link intercepted: ${url}`);
      listener(url);
    };

    const subscription = Linking.addEventListener('url', onReceiveURL);

    return () => {
      subscription.remove();
    };
  },
};
```

#### C. Enterprise Root Navigator dengan Freeze & Lifecycle Optimization (`src/navigation/RootNavigator.tsx`)

```typescript
import React, { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { enableScreens } from 'react-native-screens';
import { ActivityIndicator, View, StyleSheet } from 'react-native';

import { RootStackParamList } from './types';
import { enterpriseLinkingConfig } from './linking';
import { useAuthStore } from '../modules/auth/authStore';

// Mengaktifkan optimalisasi Native Screens & React Freeze engine
enableScreens(true);

const Stack = createNativeStackNavigator<RootStackParamList>();

// Dummy imports untuk demonstrasi arsitektural
const AuthScreen = () => <View style={styles.center} />;
const MainTabNavigator = () => <View style={styles.center} />;
const OrdersNavigator = () => <View style={styles.center} />;
const NotFoundScreen = () => <View style={styles.center} />;

export const RootNavigator: React.FC = () => {
  const { isAuthenticated, isInitializing } = useAuthStore();
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    // Simulasi inisialisasi persistensi navigasi atau dependency injection
    setIsReady(true);
  }, []);

  if (!isReady || isInitializing) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#0047AB" />
      </View>
    );
  }

  return (
    <NavigationContainer
      linking={enterpriseLinkingConfig}
      fallback={
        <View style={styles.center}>
          <ActivityIndicator size="small" color="#0047AB" />
        </View>
      }
    >
      <Stack.Navigator
        screenOptions={{
          headerShown: false,
          animation: 'slide_from_right',
          freezeOnBlur: true, // Optimalisasi memory react-freeze
          orientation: 'portrait',
        }}
      >
        {!isAuthenticated ? (
          <Stack.Screen
            name="Auth"
            component={AuthScreen}
            options={{
              animationTypeForReplace: 'pop', // Menghilangkan flicker backward transition
            }}
          />
        ) : (
          <>
            <Stack.Screen name="Main" component={MainTabNavigator} />
            <Stack.Screen
              name="OrdersFlow"
              component={OrdersNavigator}
              options={{
                presentation: 'card',
              }}
            />
          </>
        )}
        <Stack.Screen
          name="NotFound"
          component={NotFoundScreen}
          options={{ title: 'Page Not Found' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
};

const styles = StyleSheet.create({
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: SuperApp FinTech (Ride Hailing, Merchant Payment, dan Investasi)
* **Skala**: 12 juta Monthly Active Users (MAU), 80+ tim pengembang produk mandiri, 400+ screen.
* **Insiden Produksi**:
  1. *Link Hijacking & Fragment Mutation*: Link promosi eksternal memicu perpindahan langsung ke checkout payment tanpa validasi status KYC (Know Your Customer) dan token transaksi.
  2. *Android OOM Crash Rate Melonjak ke 4.8%*: Pengguna yang membuka riwayat transaksi dari notifikasi push mengakibatkan fragment stack terduplikasi secara berulang (menghasilkan 15-20 layer Native Fragment yang tertahan di memory).
* **Solusi Arsitektur**:
  1. **Sentralisasi Navigation Gateway**: Menerapkan pola `NavigationInterceptors`. Setiap deep link didekodekan ke antrean intent. Layar target tidak langsung dipasang; state engine memeriksa status session, KYC level, dan device integrity (Play Integrity / DeviceCheck).
  2. **Manifest LaunchMode Fix**: Mengubah konfigurasi Android Manifest untuk `MainActivity` menjadi `android:launchMode="singleTask"` dan membersihkan stack redundant dengan native action reset:
     ```xml
     <activity
       android:name=".MainActivity"
       android:launchMode="singleTask"
       android:exported="true">
       <intent-filter android:autoVerify="true">
         <action android:name="android.intent.action.VIEW" />
         <category android:name="android.intent.category.DEFAULT" />
         <category android:name="android.intent.category.BROWSABLE" />
         <data android:scheme="https" android:host="pay.superapp.com" />
       </intent-filter>
     </activity>
     ```
  3. **React Freeze Activation**: Memangkas memory consumption hingga 42% pada device Android 3GB RAM dengan menghentikan siklus rekonsiliasi VDOM pada inactive stacks.

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian | Skenario Terbaik |
| :--- | :--- | :--- | :--- |
| **Native Stack (`native-stack`)** | Menggunakan native controllers (`UINavigationController`, `Fragment`). Bebas overhead JS frame drops saat animasi. Memory management native. | Kustomisasi transisi visual terbatas pada API OS; integrasi gesture kustom rumit di JS layer. | Aplikasi enterprise skala besar, aplikasi berbasis performa, standar UI OS. |
| **JS Stack (`stack`)** | Sangat fleksibel, kustomisasi transisi mikro berbasis CSS-like interpolation secara leluasa via `react-native-reanimated`. | Menggunakan memori JS lebih tinggi; resiko frame drop pada low-end Android saat thread JS sibuk. | Dashboard internal atau UI dengan transisi non-standar (misal: hero animation cross-stack kustom). |
| **Universal Links / App Links** | Standar keamanan tertinggi (verifikasi domain OS via JSON), seamless UX tanpa peringatan browser popup. | Membutuhkan domain ber-SSL publik, registrasi sertifikat SHA-256 fingerprint di host, dan waktu deployment CDN. | Akses publik, otentikasi OAuth redirect, email marketing, notifikasi push. |
| **Custom Schemes (`app://`)** | Setup instan tanpa verifikasi domain server eksternal. | Resiko dibajak (*app collision*) oleh aplikasi jahat lain di Android jika scheme sama; OS menampilkan dialog konfirmasi. | Internal testing / prototyping sandbox, debugging offline via Android ADB. |
| **Unmount on Blur (`unmountOnBlur: true`)** | Membebaskan memori RAM seketika dengan menghancurkan komponen saat tab berganti. | Kehilangan local UI state (scroll position, form input); terjadi latency saat tab dipilih kembali (harus re-fetch & re-render). | Tab berat dengan beban memory tinggi (misal: live camera viewer, WebGL viewer). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Missing Intent Configuration pada Android Warm Boot
* **Gejala**: Deep link berfungsi normal saat aplikasi mati (*cold boot*), namun saat aplikasi ada di latar belakang (*warm boot*), mengklik link tidak mengubah layar atau parameter tidak ter-update.
* **Penyebab**: `MainActivity.java` / `MainActivity.kt` tidak meng-override method `onNewIntent` untuk meneruskan intent baru ke React Native bridge.
* **Solusi**:
  ```kotlin
  // MainActivity.kt
  override fun onNewIntent(intent: Intent) {
      super.onNewIntent(intent)
      setIntent(intent)
  }
  ```

#### Kesalahan 2: Retained Event Listeners pada Blurred Screens
* **Gejala**: Konsumsi memori terus meningkat (memory leak) dan pemanggilan API redundant terjadi di background saat pengguna berpindah antar tab.
* **Penyebab**: Menggunakan hook `useEffect` biasa untuk mendengarkan WebSocket atau global event emitter tanpa menghentikannya saat layar tidak aktif.
* **Solusi**: Gunakan `useFocusEffect` dari React Navigation:
  ```typescript
  import { useFocusEffect } from '@react-navigation/native';
  import { useCallback } from 'react';

  useFocusEffect(
    useCallback(() => {
      const subscription = DataStream.subscribe();
      return () => {
        subscription.unsubscribe(); // Dijalankan seketika saat screen kehilangan fokus
      };
    }, [])
  );
  ```

#### Kesalahan 3: Circular Dependency pada Type Definitions
* **Gejala**: TypeScript compiler mengeluarkan error *Type instantiation is excessively deep and possibly infinite* (TS2589).
* **Penyebab**: Mendefinisikan tipe screen props yang saling mereferensikan RootNavigator dan ChildNavigator tanpa mengisolasi parameter stack masing-masing.
* **Solusi**: Gunakan `CompositeScreenProps` dengan hierarki bertingkat strictly downward: `ChildProps -> IntermediateProps -> RootProps`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Native Freeze Enabled**: Pastikan `enableScreens(true)` dipanggil sebelum root application mount (biasanya di `index.js`).
- [ ] **LaunchMode Strategy**: Konfigurasikan `android:launchMode="singleTask"` pada entry activity di `AndroidManifest.xml`.
- [ ] **Domain Verification Asset Check**:
  - Validasi iOS: Pastikan file `apple-app-site-association` dapat diakses di `https://yourdomain.com/.well-known/apple-app-site-association` dengan content-type `application/json` tanpa redirect (HTTP 200).
  - Validasi Android: Pastikan file `assetlinks.json` memiliki SHA-256 fingerprint yang cocok dengan keystore rilis aplikasi (`release.keystore` atau Google Play App Signing key).
- [ ] **Runtime Schema Validation**: Lakukan parsing semua parameter rute dinamis deep link menggunakan pustaka validasi runtime (misal: Zod) sebelum parameter digunakan di layer data/query.
- [ ] **Stack Boundary Fallback**: Selalu sediakan rute `NotFound` (`*`) di level Root Stack untuk menangani 404 URL matching secara elegan tanpa memicu blank screen.
- [ ] **Header Configuration Performance**: Konfigurasikan header styling melalui `screenOptions` native stack daripada membuat custom React components untuk header, guna mempertahankan 120 FPS native scrolling behavior.

---

### 12. Hands-on Practice

Buat struktur direktori berikut di environment Anda:
```
hands-on/m02/
├── navigation/
│   ├── types.ts
│   ├── linking.ts
│   └── RootNavigator.tsx
├── screens/
│   ├── AuthScreen.tsx
│   ├── HomeScreen.tsx
│   ├── OrderDetailScreen.tsx
│   └── NotFoundScreen.tsx
└── App.tsx
```

#### Langkah 1: Buat Screen Mockups dengan Parameter Check (`hands-on/m02/screens/OrderDetailScreen.tsx`)

```typescript
import React from 'react';
import { View, Text, StyleSheet, Button } from 'react-native';
import { OrderDetailScreenProps } from '../navigation/types';

export const OrderDetailScreen: React.FC<OrderDetailScreenProps> = ({ route, navigation }) => {
  const { orderId, source } = route.params;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Order Detail Screen</Text>
      <Text style={styles.info}>Order ID: {orderId}</Text>
      <Text style={styles.info}>Traffic Source: {source ?? 'direct'}</Text>
      <Button
        title="Back to Root Flow"
        onPress={() => navigation.navigate('Main', { screen: 'FeedTab' })}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 },
  title: { fontSize: 20, fontWeight: 'bold', marginBottom: 12 },
  info: { fontSize: 16, color: '#333', marginBottom: 8 },
});
```

#### Langkah 2: Simulasi Testing Deep Link via Terminal (CLI Execution)

Uji determinisme deep linking tanpa bergantung pada browser fisik menggunakan Android Debug Bridge (ADB) dan iOS Simulator CLI:

* **Android ADB Command**:
  ```bash
  # Uji valid link
  adb shell am start -W -a android.intent.action.VIEW \
    -d "https://mobile.enterprise.com/orders-flow/detail/a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11" com.enterpriseapp

  # Uji malformed / injection link
  adb shell am start -W -a android.intent.action.VIEW \
    -d "https://mobile.enterprise.com/orders-flow/detail/malicious-sql-injection-param" com.enterpriseapp
  ```

* **iOS Simulator XCExec Command**:
  ```bash
  xcrun simctl openurl booted "https://mobile.enterprise.com/orders-flow/detail/a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
  ```

---

### 13. Exercise

#### Level 1 (Easy): Parameterized Deep Linking
* **Instruksi**: Tambahkan rute baru di `MainTabParamList` bernama `NotificationsTab`. Konfigurasikan linking engine agar ketika URL `enterpriseapp://notifications?filter=unread` dipanggil, aplikasi membuka tab notifikasi dan mengekstrak query parameter `filter`.
* **Kriteria Keberhasilan**: Type definition valid tanpa `any`, query parameter diekstrak dengan aman.

#### Level 2 (Medium): Dynamic Protected Deep Linking
* **Instruksi**: Buat interceptor di level linking configuration: Jika user mengklik link `https://mobile.enterprise.com/orders-flow/detail/:orderId` saat status `isAuthenticated = false`, simpan intended URL tersebut di memory/storage, arahkan user ke `AuthScreen`, dan setelah login sukses, dispatch navigasi otomatis ke screen `OrderDetail` yang tertunda tadi.
* **Kriteria Keberhasilan**: Alur autentikasi tidak memotong riwayat navigasi, rute tertunda dieksekusi tepat satu kali (*atomic redirection*).

#### Level 3 (Hard): Multi-domain Nested Deep Link State Hydrator
* **Instruksi**: Aplikasi harus menangani dua domain berbeda: `partner.enterprise.com` dan `consumer.enterprise.com`. Jika deep link datang dari domain partner, struktur stack harus merender `PartnerTheme` dan menyuntikkan middleware autentikasi khusus partner sebelum screen dimuat. Tulis custom `getStateFromPath` implementation untuk menangani parsing multi-host ini.
* **Kriteria Keberhasilan**: Implementasi kustom `getStateFromPath` yang deterministik, penanganan edge-case domain mismatch, dan penulisan skema validasi tipe rute.

---

### 14. Challenge

#### Skenario: "The Zero-Downtime Deep Link Token Exchange Engine"
Perusahaan perbankan digital menerapkan sistem otentikasi stateless di mana deep link berisi *Single-Use Cryptographic Handshake Code* (misal: `https://bank.enterprise.com/verify-transaction?authNonce=xyz789&action=transfer`).

**Ketentuan Tantangan:**
1. Kode `authNonce` ini hanya valid selama **5 detik** sejak diterima oleh native intent OS.
2. Jika engine JS mengalami cold boot latency lebih dari 2.5 detik, thread JS harus segera memprioritaskan worker eksekusi pertukaran nonce ke API backend melalui JSI TurboModule sebelum Native Stack Screen dimount ke UI tree.
3. Jika pertukaran token gagal atau timeout, navigasi tidak boleh menampilkan layar transfer sedetik pun (mencegah screen leakage/flashing data transaksi sensitif). Aplikasi harus membatalkan pembentukan stack dan langsung menampilkan *Security Fallback UI*.
4. Rancang skema modul navigasi, penanganan state sinkronisasi, dan proteksi layout-nya secara utuh dengan standar keamanan finansial.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Basic
1. Apa perbedaan mendasar antara `@react-navigation/native-stack` dan `@react-navigation/stack` dalam alokasi memori di native OS?
2. Mengapa konfigurasi `launchMode="singleTask"` direkomendasikan pada `MainActivity` Android ketika mengimplementasikan deep linking?
3. Apa kegunaan utama dari pemanggilan `enableScreens(true)` dari pustaka `react-native-screens`?
4. Manakah tipe hook yang tepat digunakan untuk membatalkan subscription event global saat screen berpindah: `useEffect` atau `useFocusEffect`? Mengapa?
5. Mengapa format scheme `my-app://` lebih rentan terhadap serangan keamanan dibandingkan Universal Links (`https://`)?

#### Bagian B: Intermediate
6. Bagaimana cara kerja mekanisme `freezeOnBlur` dalam mengoptimalkan performa rendering layar yang berada di bawah stack?
7. Jelaskan alur kerja native runtime saat menerima Universal Link pada saat aplikasi berstatus *Cold Boot* versus *Warm Boot*!
8. Apa fungsi dari `NavigatorScreenParams<T>` dalam pendefinisian type-safe navigation di TypeScript?
9. Bagaimana Anda menangani parameter URL yang tidak valid pada konfigurasi deep link agar aplikasi tidak crash atau menampilkan undefined state?
10. Mengapa kita tidak disarankan melakukan dispatch navigasi langsung di dalam root component sebelum state navigasi di-hydrate?

#### Bagian C: Skenario Kasus Produksi
11. **Skenario 1**: Pengguna mengeluhkan bahwa saat mereka membuka link produk dari aplikasi perpesanan pihak ketiga, aplikasi membuka layar baru namun tombol "Back" native pada Android langsung menutup aplikasi alih-alih kembali ke halaman utama (Home). Di mana letak kegagalan arsitektur navigasinya dan bagaimana memperbaikinya?
12. **Skenario 2**: Pada rilis aplikasi versi terbaru, analitik Crashlytics melaporkan kenaikan tajam Fatal Exception: `java.lang.IllegalStateException: FragmentManager has been destroyed` saat transisi screen cepat dari deep link push notification. Identifikasi akar permasalahan dan berikan solusi pencegahannya!
13. **Skenario 3**: Sebuah aplikasi e-commerce memiliki form multi-step checkout. Saat user berada di Step 3, deep link push notifikasi diskon diklik. Bagaimana merancang hierarki navigasi agar alur checkout user tidak terhapus (hilang state), namun user tetap dapat melihat penawaran diskon tersebut?

---

### 16. Summary

1. **Native-Driven Performance**: Navigasi enterprise modern pada React Native bertumpu pada `react-native-screens` yang memetakan layer stack langsung ke `UIViewController` (iOS) dan `Fragment` (Android), mengeliminasi overhead serialisasi bridge melalui JSI.
2. **Deterministic Deep Linking**: Deep linking produksi membutuhkan verifikasi domain cryptographically secure (Universal Links / App Links), konfigurasi manifest native OS yang presisi (`singleTask`), dan validasi runtime payload menggunakan library seperti Zod.
3. **End-to-End Type Safety**: Pemanfaatan TypeScript hierarkis (`CompositeScreenProps`, global parameter mapping) mengeliminasi potensi silent runtime crash akibat salah penamaan screen atau mismatch data contracts.
4. **Lifecycle & Memory Discipline**: Pemanfaatan fitur `freezeOnBlur`, pembersihan listener via `useFocusEffect`, dan isolasi stack adalah strategi mutlak untuk mempertahankan crash-free rate 99.9% pada device dengan spesifikasi terbatas.