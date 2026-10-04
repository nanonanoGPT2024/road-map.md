# Bab 04 Module 01: Navigation & Deep Linking Architecture

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik Spesialisasi:** React Native Core Architecture & Enterprise Engineering
*   **Modul:** Bab 04 Module 01 — Navigation & Deep Linking Architecture
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** Pemahaman mendalam tentang React Native Runtime (JSI, Fabric, TurboModules), State Management (Zustand/Redux), TypeScript Generics & Type Narrowing, serta Operating System Interop (Android Intents & iOS URL Schemes / Universal Links).
*   **Estimasi Waktu Selesai:** 8–10 Jam (Teori, Analisis Kode, Implementasi Enterprise Pattern)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1.  **Menganalisis Arsitektur Internal Navigasi:** Memahami perbedaan fundamental mekanika antara navigasi berbasis JavaScript thread (React Navigation) versus platform-native navigation stack (React Native Screens & Native Stack).
2.  **Merancang Deterministic State Synchronization:** Membangun konfigurasi TypeScript strict type-safe navigation tree dan state machine navigasi berbasis kondisi otentikasi tanpa flicker (*zero-flicker re-rendering*).
3.  **Mengimplementasikan Deep Linking & Universal Linking Skala Enterprise:** Menangani resolusi inbound URL, deferred deep linking, dan navigasi berbasis payload kompleks melalui Android Intent filters dan iOS Associated Domains.
4.  **Mengeksekusi Strategi Optimasi Memori:** Mengoptimalkan konsumsi memori native view recycling melalui `react-native-screens`, pencegahan kebocoran memori (memory leak) dari lingering navigation listeners, serta memangkas overdraw render stack.
5.  **Membangun Hardened Deep Link Security:** Melindungi aplikasi dari URL injection, parameter tampering, insecure dynamic routing, dan eksekusi instruksi unauthorized context via intent/schema payload verification.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam dunia web, navigasi bersifat *stateless* dan berpusat pada address bar browser: URL bertindak sebagai single source of truth absolut yang memicu destruksi DOM lama dan konstruksi DOM baru (atau update Virtual DOM).

Sebaliknya, pada platform mobile enterprise:
1.  **Navigasi adalah State Machine Berbasis Stack Bersarang (Nested Stacks):** Layar tidak sekadar diganti; mereka ditumpuk di memori native GPU/OS (`UINavigationController` di iOS, `FragmentManager` / `BackStackRecord` di Android). Layar sebelumnya tetap aktif di background memori, menahan subscriptions, memori tekstur gambar, dan context state.
2.  **Deep Link adalah Serialized Transaction Log:** Sebuah URL seperti `https://app.enterprise.com/checkout/order_8821?ref=promo` bukan sekadar string rute tunggal. Ia merupakan representasi singkat dari instruksi mutasi stack:
    *   Initialize Root Navigator.
    *   Verify Session Token (Auth Gate).
    *   Push `MainTabs` Screen.
    *   Push `ShopStack` Screen.
    *   Push `CheckoutDetailScreen` dengan payload `{ orderId: 'order_8821', ref: 'promo' }`.
3.  **Filosofi Strict Tree Synchronization:** Setiap cabang navigasi harus direpresentasikan sebagai struktur data pohon (Tree Data Structure) yang deterministik. Mengabaikan validasi skema payload pada deep link sama berbahayanya dengan mengeksekusi `eval()` pada raw network inputs.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### A. Lifecycle Resolusi Deep Link (Inbound Intent/Universal Link ke UI Stack)

```
[OS System Level]
   │  Android: Intent (ACTION_VIEW)
   │  iOS: NSUserActivity (Universal Link) / Custom Scheme
   ▼
[Native Bridge / JSI Initialization]
   │  LinkingModule.mm (Extract Native URI & Initial URL)
   ▼
[React Native JS Runtime Engine]
   │
   ├─► App State: Cold Start? (Linking.getInitialURL())
   │        └─► Pipeline Deferred Deep Link Parser
   │
   └─► App State: Warm/Hot Run? (Linking.addEventListener('url'))
            └─► Runtime Payload Validator (Zod Schema Validation)
                     │
                     ├─► [Validation Failed] ──► Fallback Handler / Analytics Log
                     │
                     └─► [Validation Success]
                              │
                              ▼
            [Auth Engine State Verification]
               │
               ├─► [Unauthorized] ──► Push to Auth/Login Modal
               │                      (Cache Target Route di Secure Storage)
               │
               └─► [Authorized]
                        │
                        ▼
            [Navigation State Transformer / Reducer]
               │   Mengurai nested target path ke Root State
               │
               ▼
            [React Native Screens / Native Stack Driver]
               │   Instansiasi View Controller / Fragment
               │   Zero JS-Thread Thread Overhead
               ▼
      [Target UI Screen Rendered Deterministically]
```

### B. Topologi Arsitektur Stack Navigasi Bersarang Skala Enterprise

```
                       ┌─────────────────────────┐
                       │      Root Navigator     │
                       │   (Native Stack Modal)  │
                       └────────────┬────────────┘
                                    │
          ┌─────────────────────────┴─────────────────────────┐
          │ (conditional rendering / auth gate)               │
          ▼                                                   ▼
┌──────────────────┐                               ┌─────────────────────┐
│  Auth Navigator  │                               │    App Navigator    │
│  (Native Stack)  │                               │    (Bottom Tabs)    │
└─────────┬────────┘                               └──────────┬──────────┘
          │                                                   │
     ┌────┴────┐                             ┌────────────────┼────────────────┐
     ▼         ▼                             ▼                ▼                ▼
  [Login]  [Register]                 ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
                                      │ Home Stack  │  │ Orders Stack│  │Profile Stack│
                                      └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
                                             │                │                │
                                             ▼                ▼                ▼
                                         [Feed]           [History]        [Settings]
                                             │                │                │
                                             ▼                ▼                ▼
                                         [Detail]         [Tracking]       [Security]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Bridge/JSI Linking Interop
Pada tingkat sistem operasi:
*   **iOS:** Menggunakan `AppDelegate.mm`. Ketika URL dipanggil via skema kustom, OS memanggil method `application:openURL:options:`. Untuk Universal Links, OS memanggil `application:continueUserActivity:restorationHandler:`. React Native menyalurkan event ini ke native module `RCTLinkingManager`.
*   **Android:** Menggunakan konfigurasi `AndroidManifest.xml` dengan `<intent-filter>`. Ketika activity menerima target URL, Android menembakkannya via `onNewIntent(Intent intent)`. Native module `LinkingModule.java` menangkap intent, mengekstrak data string via `intent.getDataString()`, dan meneruskannya ke JS Runtime via Device Event Emitter.

### 2. JS Thread Navigation Stack vs. Native Stack Driver
*   **Legacy JavaScript Stack Navigator (`@react-navigation/stack`):** Seluruh logika transisi, gesture parsing, dan stack state dihitung di JavaScript thread. Komponen dibungkus dalam `Animated.View`. Jika JS thread terblokir oleh heavy array computation atau rendering besar, animasi gesture navigasi akan *stutter* (drop frames).
*   **Modern Native Stack Navigator (`@react-navigation/native-stack` + `react-native-screens`):** Memetakan setiap layar React langsung ke platform primitives: `UIViewController` pada iOS dan `Fragment` pada Android. Animasi transisi, gesture recognizers (seperti iOS swipe-to-back), dan render lifecycle dikontrol langsung oleh Operating System Compositor thread (CoreAnimation / Android RenderThread), membebaskan JavaScript thread sepenuhnya.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### State Representation & Navigation State Trees
Navigation state direpresentasikan sebagai pohon immutable murni:

$$\mathcal{S} = \{ \text{key}, \text{index}, \text{routes}: [ \mathcal{R}_0, \mathcal{R}_1, \dots, \mathcal{R}_n ] \}$$

Dimana setiap route $\mathcal{R}$ didefinisikan sebagai:

$$\mathcal{R} = \{ \text{key}: \text{string}, \text{name}: \text{string}, \text{params}?: \mathbf{P}, \text{state}?: \mathcal{S} \}$$

Jika terjadi interaksi deep link masuk:
$$\mathcal{U} \xrightarrow{\text{parse}} \mathcal{P}_{\text{route}}$$
Fungsi `getStateFromPath(path, options)` dari React Navigation akan melakukan translasi dari serial URI string menjadi structural branch representation:

$$\mathcal{U} = \text{"/orders/123/track"} \implies \mathcal{S}_{\text{resolved}} = \begin{bmatrix} \text{Root} \to \text{MainTabs} \to \text{OrdersStack} \\ \to \text{OrderDetail}(\text{id}: 123) \\ \to \text{OrderTracking}() \end{bmatrix}$$

Algoritma ini menggunakan dynamic regex path segment matching yang memetakan path segments ke screen definitions yang didefinisikan pada objek `linking`.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah setup fundamental type-safe navigation stack dan konfigurasinya.

```typescript
// types/navigation.ts
import { NavigatorScreenParams } from '@react-navigation/native';

export type RootStackParamList = {
  Auth: undefined;
  App: NavigatorScreenParams<AppTabParamList>;
  NotFound: undefined;
};

export type AppTabParamList = {
  HomeStack: NavigatorScreenParams<HomeStackParamList>;
  Profile: { userId: string };
};

export type HomeStackParamList = {
  Feed: undefined;
  Details: { itemId: string; source: 'push' | 'organic' };
};

declare global {
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}
```

```typescript
// navigation/linkingConfig.ts
import { LinkingOptions } from '@react-navigation/native';
import { RootStackParamList } from '../types/navigation';

export const linkingConfig: LinkingOptions<RootStackParamList> = {
  prefixes: ['enterpriseapp://', 'https://mobile.enterprise.com'],
  config: {
    screens: {
      Auth: 'auth',
      App: {
        screens: {
          HomeStack: {
            screens: {
              Feed: 'feed',
              Details: 'feed/item/:itemId/:source',
            },
          },
          Profile: 'user/:userId',
        },
      },
      NotFound: '*',
    },
  },
};
```

```tsx
// navigation/RootNavigator.tsx
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { RootStackParamList } from '../types/navigation';
import { linkingConfig } from './linkingConfig';
import { AppTabNavigator } from './AppTabNavigator';
import { AuthNavigator } from './AuthNavigator';
import { NotFoundScreen } from '../screens/NotFoundScreen';
import { useAuthSession } from '../context/AuthContext';

const Stack = createNativeStackNavigator<RootStackParamList>();

export const RootNavigator: React.FC = () => {
  const { isAuthenticated, isBootstrapping } = useAuthSession();

  if (isBootstrapping) {
    return null; // Atau render native splash screen container
  }

  return (
    <NavigationContainer linking={linkingConfig}>
      <Stack.Navigator
        screenOptions={{
          headerShown: false,
          animation: 'slide_from_right',
        }}
      >
        {!isAuthenticated ? (
          <Stack.Screen name="Auth" component={AuthNavigator} />
        ) : (
          <Stack.Screen name="App" component={AppTabNavigator} />
        )}
        <Stack.Screen 
          name="NotFound" 
          component={NotFoundScreen} 
          options={{ presentation: 'modal' }} 
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
};
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis File `types/navigation.ts`
*   **Baris 1:** Mengimpor `NavigatorScreenParams` dari core navigation library. Ini krusial agar nested navigators menerima parameter parent secara strict type-safe.
*   **Baris 3–7:** `RootStackParamList` mendefinisikan layer teratas. `App` dikaitkan dengan `NavigatorScreenParams<AppTabParamList>` yang mengizinkan pemanggilan navigasi type-checking dari root menembus langsung ke level tab.
*   **Baris 19–23:** *Declaration Merging* pada TypeScript namespace `ReactNavigation`. Ini meng-override interface global `RootParamList`, sehingga hook seperti `useNavigation()` secara otomatis mengetahui seluruh schema rute tanpa harus manual passing generics di setiap komponen UI.

### Analisis File `navigation/linkingConfig.ts`
*   **Baris 5:** `prefixes` menampung custom URI scheme (`enterpriseapp://`) dan FQDN Universal Links (`https://mobile.enterprise.com`). Native OS routing engine membaca array ini.
*   **Baris 6–18:** `config.screens` merefleksikan nesting pohon navigator. Segment `:itemId` dan `:source` diekstrak menjadi key-value pair dari object `params` yang divalidasi dan diinjeksi ke stack `Details`.

### Analisis File `navigation/RootNavigator.tsx`
*   **Baris 15–17:** Evaluasi status bootstrapping auth (misal: verifikasi token JWT dari `react-native-keychain`). Render null menunda tree navigation terpasang hingga identitas diketahui, mencegah bouncing visual antar halaman login dan feed.
*   **Baris 24–28:** *Conditional Screen Pattern*. Layar `Auth` dan `App` dieksekusi secara mutual exclusive. Tidak boleh menavigasikan manual via `navigation.navigate('Auth')` pasca logout; melainkan lakukan mutasi status `isAuthenticated`, dan React reconciliation engine akan membuang memory stack internal `App` secara otomatis.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Aplikasi Enterprise Financial SuperApp
Sebuah institusi perbankan dan e-commerce multimodal mengalami masalah kritis:
1.  **Race Condition & State Desync:** Ketika pengguna yang belum terotentikasi membuka URL Universal Link dari WhatsApp atau Email (`https://fintech.enterprise.com/transfer/target?account=882910`), aplikasi langsung melempar error crash karena komponen target mengeksekusi fetch request dengan `Bearer null` pada headers.
2.  **Missing Back Pathing:** Saat rute dalam deep link berhasil dibuka langsung oleh authenticated user, menekan tombol hardware "Back" pada Android langsung menutup aplikasi (exit to home screen), bukan kembali ke parent list dashboard (hierarchical back-up navigation broken).
3.  **Insecure Direct Object Reference (IDOR) via Deep Link:** Payload parameter rute pembayaran bisa dimanipulasi melalui custom scheme injection oleh aplikasi berbahaya yang terpasang di OS target.

Solusi arsitektur: Membangun Unified Navigation Guard Engine yang memvalidasi parsing deep link menggunakan skema Zod, menahan deep-link context di storage transient jika token auth invalidated, serta merekonstruksi nested state stack history secara runtime.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

```typescript
// navigation/security/DeepLinkValidator.ts
import { z } from 'zod';

export const TransferRouteParamSchema = z.object({
  account: z.string().regex(/^[0-9]{8,12}$/, 'Invalid account format'),
  amount: z.string().optional().transform((val) => (val ? parseFloat(val) : 0)),
  tokenRef: z.string().uuid('Invalid secure token reference'),
});

export type TransferRouteParams = z.infer<typeof TransferRouteParamSchema>;

export const sanitizeAndValidateDeepLink = (
  rawUrl: string
): { isValid: boolean; path: string; params: Record<string, unknown> } => {
  try {
    const parsed = new URL(rawUrl);
    const path = parsed.pathname;
    const searchParams = Object.fromEntries(parsed.searchParams.entries());

    if (path.includes('transfer')) {
      const validatedParams = TransferRouteParamSchema.parse(searchParams);
      return { isValid: true, path, params: validatedParams };
    }

    return { isValid: true, path, params: searchParams };
  } catch (error) {
    // Audit Telemetry Logging
    return { isValid: false, path: '', params: {} };
  }
};
```

```typescript
// navigation/EnterpriseLinkingPipeline.ts
import { LinkingOptions, getStateFromPath } from '@react-navigation/native';
import { Linking } from 'react-native';
import { RootStackParamList } from '../types/navigation';
import { sanitizeAndValidateDeepLink } from './security/DeepLinkValidator';
import { TokenVault } from '../security/TokenVault';
import { NavigationQueue } from './NavigationQueue';

export const EnterpriseLinkingConfig: LinkingOptions<RootStackParamList> = {
  prefixes: ['https://fintech.enterprise.com', 'fintechapp://'],

  // Custom getInitialURL untuk menangani Cold Start dengan validasi
  async getInitialURL() {
    const url = await Linking.getInitialURL();
    if (!url) return null;

    const validation = sanitizeAndValidateDeepLink(url);
    if (!validation.isValid) {
      return null;
    }

    const token = await TokenVault.getAccessToken();
    if (!token) {
      // Simpan rute target ke antrian untuk dieksekusi pasca login
      NavigationQueue.setDeferredPath(url);
      return null;
    }

    return url;
  },

  // Subscribe ke event URL saat aplikasi dalam status Warm/Background
  subscribe(listener) {
    const onReceiveURL = async ({ url }: { url: string }) => {
      const validation = sanitizeAndValidateDeepLink(url);
      if (!validation.isValid) {
        return;
      }

      const token = await TokenVault.getAccessToken();
      if (!token) {
        NavigationQueue.setDeferredPath(url);
        return;
      }

      listener(url);
    };

    const subscription = Linking.addEventListener('url', onReceiveURL);
    return () => subscription.remove();
  },

  // Transformasi konfigurasi URL mapping ke internal navigation stack
  config: {
    screens: {
      App: {
        screens: {
          HomeStack: {
            initialRouteName: 'Feed',
            screens: {
              Feed: 'feed',
              Transfer: 'transfer/target',
            },
          },
        },
      },
      Auth: 'auth',
      NotFound: '*',
    },
  },

  // State reconstruction: Memaksa pembangunan stack history secara manual
  getStateFromPath(path, options) {
    const state = getStateFromPath(path, options);
    if (!state) return undefined;

    // Pastikan jika navigasi ke Transfer, history stack memiliki Feed sebagai index 0
    return {
      ...state,
      routes: state.routes.map((route) => {
        if (route.name === 'App' && route.state) {
          return {
            ...route,
            state: {
              ...route.state,
              routes: route.state.routes.map((subRoute) => {
                if (subRoute.name === 'HomeStack' && subRoute.state) {
                  const hasFeed = subRoute.state.routes.some((r) => r.name === 'Feed');
                  if (!hasFeed) {
                    return {
                      ...subRoute,
                      state: {
                        ...subRoute.state,
                        index: subRoute.state.routes.length,
                        routes: [{ name: 'Feed' }, ...subRoute.state.routes],
                      },
                    };
                  }
                }
                return subRoute;
              }),
            },
          };
        }
        return route;
      }),
    };
  },
};
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Dimensi Arsitektural | React Navigation Native Stack | React Native Screens Standalone | Pure JS Stack Navigator |
| :--- | :--- | :--- | :--- |
| **Driver Runtime** | Platform Native (UINavigationController/Fragment) | Primitives Container Views | JS Thread Animated Engine |
| **Overdraw & Memori** | **Rendah:** Layar yang tertutup di-unmount secara grafis oleh native subsystem | **Sangat Rendah:** Membutuhkan integrasi manual tingkat lanjut | **Tinggi:** Seluruh layer tersimpan di layout render JS, rentan memory pressure |
| **Gesture Fidelity** | **100% Native:** Mendukung behavior gesture bawaan OS (iOS interactive back swipe) | **Tinggi:** Tergantung integrasi platform host | **Menengah:** Simulasi gesture JS rentan dropped-frame saat heavy computation |
| **Kustomisasi Animasi** | **Terbatas:** Terikat pada batasan native API animasi platform | **Rendah:** Dikelola pada interface container | **Maksimal:** Bebas manipulasi kustom frame-by-frame via Reanimated |
| **Bundle Size Overhead** | **Ringan:** Minimal code overhead, meminjam native standard lib | **Sangat Ringan** | **Lebih Besar:** Membawa dependency polyfill & JS gesture math |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Phantom Stack Leak (Infinite Linking Memory Growth)
*   **Masalah:** Deep link trigger berulang yang memanggil rute yang sama dapat menumpuk screen identik ke dalam native stack tanpa batas, menyebabkan heap memory exhaustion.
*   **Mitigasi:** Konfigurasikan prop `getId` pada `Stack.Screen` atau gunakan policy action `navigate({ name, params, merge: true })` untuk mencegah duplikasi instance.

```tsx
<Stack.Screen
  name="Details"
  component={DetailsScreen}
  getId={({ params }) => params?.itemId} // Layar tidak akan di-push jika ID sama sudah ada di stack
/>
```

### 2. Android Hardware Back Button Exit Trap
*   **Masalah:** Ketika user masuk melalui deep link ke level cabang terbawah, menekan native back button langsung membubarkan task activity karena Android stack history lokal tidak mengenali parent rute aplikasi.
*   **Mitigasi:** Wajib mengimplementasikan interpolasi custom `getStateFromPath` (seperti yang ditunjukkan pada Seksi 10) untuk secara eksplisit menginjeksi array root screen history ke navigation state resolver.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Mengarahkan Navigasi Manual di Response Callback Authentication (Imperative anti-pattern)
*   *Salah:*
    ```typescript
    // ANTI-PATTERN: Menyebabkan race condition jika komponen di-unmount
    const handleLoginSuccess = async () => {
      await authenticate();
      navigation.navigate('App'); // CRITICAL: Potensi navigation state collision
    };
    ```
*   *Benar:*
    ```typescript
    // STATE-DRIVEN PATTERN
    const handleLoginSuccess = async () => {
      // Cukup ubah state global/context
      authStore.setAuthenticated(true);
      // Navigation stack akan re-render via declarative conditional routing
    };
    ```

### 2. Membaca Query Params Deep Link Tanpa Type Guard / Sanitasi
*   *Salah:* Mengekstrak query parameter dan langsung menginjeksinya ke state atau fetch request API (`fetch('/api/user/' + route.params.id)`).
*   *Benar:* Gunakan parser runtime (seperti `Zod`) dengan proteksi sanitasi string regex untuk menolak invalid payload sebelum UI component di-mount.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Strict Type Declaration Merging:** Selalu override global interface `namespace ReactNavigation` untuk memastikan developer lain dalam organisasi mendapatkan error compile-time saat memanggil rute typo atau parameter yang tidak lengkap.
2.  **Screen Param Minimalism:** Navigation parameters **hanya boleh membawa identifier primitif** (contoh: `orderId: string`). Dilarang keras melewatkan full-object payload atau function callback melalui navigation params. Full-object harus diambil dari application cache (React Query, Zustand) via ID tersebut guna menghindari memory serializing lag dan memory stale state.
3.  **Universal Links Over Custom URL Schemes:** Gunakan scheme `https://` yang terverifikasi via iOS Apple App Site Association (AASA) dan Android Digital Asset Links. Custom scheme (`myapp://`) rentan terhadap URL scheme hijacking oleh aplikasi fraudster di OS yang sama.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Native Screen Freezing Mechanism
Gunakan fitur `enableFreeze()` dari `react-native-screens`. Mekanisme ini menggunakan React 18 Suspense internals untuk menahan update re-render pada layar yang berada di background stack sampai layar tersebut kembali terlihat di viewport terdepan.

```typescript
// index.js atau App.tsx
import { enableScreens, enableFreeze } from 'react-native-screens';

enableScreens(true);
enableFreeze(true); // Membekukan render sub-tree layar yang ada di bawah stack
```

### Dampak Pengurangan CPU & Memori
*   **Tanpa Freeze:** Layar di balik stack terus menerima context/store updates dan mengeksekusi virtual DOM diffing secara konstan. Konsumsi CPU thread meningkat 15–30% saat rendering data berat.
*   **Dengan Freeze:** React component subtree di-bypass dari diffing cycle. Thread idle time meningkat drastis, menghemat alokasi daya baterai dan memori frame rate 60/120 FPS tetap konsisten pada thread UI utama.

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **URL Validation & Path Traversal Prevention:** Cegah parameter tampering yang mencoba mengeksploitasi direct internal webview linking:
    ```typescript
    const isValidAppRedirect = (url: string): boolean => {
      const allowedHosts = ['mobile.enterprise.com', 'secure.fintech.com'];
      try {
        const parsed = new URL(url);
        return allowedHosts.includes(parsed.hostname);
      } catch {
        return false;
      }
    };
    ```
2.  **Sanitisasi Target Payload:** Lakukan validasi terhadap karakter jahat seperti format query yang memicu SQL Injection atau Cross-Site Scripting (XSS) apabila parameter deep link digunakan dalam komponen `WebView`.

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Lacak pergerakan state navigation tree dengan memasang lifecycle state tracking listener pada `NavigationContainer`.

```tsx
// observability/NavigationTracker.tsx
import React, { useRef } from 'react';
import { NavigationContainer, NavigationContainerRef } from '@react-navigation/native';
import { AnalyticsService } from '../services/AnalyticsService';

interface Props {
  children: React.ReactNode;
  linking: any;
}

export const ObservableNavigationContainer: React.FC<Props> = ({ children, linking }) => {
  const routeNameRef = useRef<string>();
  const navigationRef = useRef<NavigationContainerRef<any>>(null);

  return (
    <NavigationContainer
      ref={navigationRef}
      linking={linking}
      onReady={() => {
        routeNameRef.current = navigationRef.current?.getCurrentRoute()?.name;
      }}
      onStateChange={async () => {
        const previousRouteName = routeNameRef.current;
        const currentRoute = navigationRef.current?.getCurrentRoute();
        const currentRouteName = currentRoute?.name;

        if (previousRouteName !== currentRouteName && currentRouteName) {
          await AnalyticsService.logScreenView({
            screen_name: currentRouteName,
            screen_class: currentRouteName,
            params: currentRoute.params,
          });
        }
        routeNameRef.current = currentRouteName;
      }}
    >
      {children}
    </NavigationContainer>
  );
};
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **Pondasi Utama:** Gunakan `@react-navigation/native-stack` untuk arsitektur berbasis native primitives.
*   **Otentikasi:** Gunakan *Conditional Screen Mounting* declarative: `isAuthenticated ? <AppStack /> : <AuthStack />`.
*   **Deep Link Protocol:**
    1.  Parse URL masuk via custom handler (`LinkingOptions.getInitialURL` & `LinkingOptions.subscribe`).
    2.  Validasi strict schema parameter via `Zod`.
    3.  Evaluasi session state (jika unauthorized, simpan URL ke persistent deferred queue).
    4.  Bangun fallback stack history via manual `getStateFromPath`.
*   **Performa:** Selalu aktifkan `enableScreens(true)` dan `enableFreeze(true)` pada application entry point.
*   **Security:** Jangan lewatkan raw parameters langsung ke business logic/query strings; validasi whitelist domains secara ketat.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Mengapa `@react-navigation/native-stack` menghasilkan performa animasi transisi gesture yang jauh lebih konsisten dibandingkan `@react-navigation/stack` berbasis JavaScript?
*   A. Karena native-stack mengeksekusi rendering seluruh elemen langsung dari file WebAssembly.
*   B. Karena native-stack mendelegasikan struktur layar dan transisi langsung ke komponen native OS (`UINavigationController` dan `Fragment`), berjalan independen dari kesibukan JavaScript single thread.
*   C. Karena JS Stack Navigator tidak mendukung React Hooks dan TypeScript compilation.
*   D. Karena native-stack tidak menyimpan state view ke dalam RAM.

### Soal 2
Ketika implementasi flow otentikasi login/logout di React Native, pendekatan arsitektur mana yang dianggap paling tepat menurut standar modern React?
*   A. Memanggil `navigation.dispatch(StackActions.popToTop())` di dalam action login.
*   B. Mengarahkan navigasi secara manual menggunakan `navigation.navigate('Login')` di dalam catch block interceptor Axios.
*   C. Melakukan conditional rendering pada tree navigator berdasarkan nilai auth state token (`isAuthenticated ? <AppScreen /> : <AuthScreen />`).
*   D. Menghapus instance React Navigation Container dari DOM root secara paksa.

### Soal 3
Apa risiko utama dari tidak menerapkan konfigurasi `getStateFromPath` kustom saat aplikasi menerima deep link yang mengarah ke hierarki layar yang bersarang dalam (deeply nested)?
*   A. Aplikasi secara otomatis menghapus storage persistent Keychain.
*   B. Animasi transisi screen akan dipaksa bergerak dari atas ke bawah.
*   C. Back history stack tidak terbentuk, sehingga menekan tombol native hardware back pada Android akan langsung keluar dari aplikasi.
*   D. Kompiler TypeScript akan menghasilkan runtime error saat mem-parsing JavaScript bundle.

### Soal 4
Parameter apa yang dianjurkan untuk dikirimkan melalui navigation params (`route.params`) dalam best practice enterprise?
*   A. Function callback untuk manipulasi state parent.
*   B. Objek data lengkap berikut relasinya (misal: objek User lengkap berukuran 50KB).
*   C. Array of JSX Elements.
*   D. Primitive identifier unik (misal: `userId: string`) yang digunakan untuk fetching/reading dari local cache store.

### Soal 5
Fitur `enableFreeze(true)` dari library `react-native-screens` bertujuan untuk:
*   A. Menghentikan execution loop JavaScript thread saat terjadi error unhandled rejection.
*   B. Membekukan proses rendering dan diffing Virtual DOM pada layar yang sedang tertutup di balik stack navigator untuk menghemat CPU dan memori.
*   C. Mengunci orientasi layar perangkat secara permanen ke portrait mode.
*   D. Menunda splash screen native agar tidak berpindah sebelum jaringan internet stabil.

---

### Kunci Jawaban & Evaluasi Teknis
*   **Soal 1: B** — `@react-navigation/native-stack` memanfaatkan primitives UI native host secara langsung, memisahkan beban rendering layar dari JS Event Loop.
*   **Soal 2: C** — Conditional rendering memastikan state navigator lama dibersihkan secara alami oleh React Reconciliation tanpa meninggalkan history stack tak berizin di memori.
*   **Soal 3: C** — Tanpa rekonstruksi manual rute leluhur, OS hanya mengenali rute target sebagai satu-satunya entitas pada activity back stack.
*   **Soal 4: D** — Navigation parameters dirancang untuk serializable primitive identifiers. Mengirim objek besar memperlambat performa deserialisasi dan menyebabkan inkonsistensi cache.
*   **Soal 5: B** — `enableFreeze(true)` memanfaatkan React Suspense boundary untuk memangkas aktivitas rerender pada offscreen subtrees.

---

## SEKSI 20 — TANTANGAN MANDIRI & PROYEK PRAKTIKUM

### Instruksi Penugasan Praktikum
Bangun sistem *Resilient Deep-Link Auth Gateway* dengan spesifikasi tingkat industri:

1.  **Requirement 1 (Type-Safe Topology):** Rancang arsitektur stack bertingkat yang terdiri atas:
    *   `AuthStack` (`Login`, `TwoFactorAuth`).
    *   `MainTabs` (`DashboardStack`, `PortfolioStack`).
    *   `DashboardStack` memiliki sub-layar `Feed`, `MarketAnalytics`, dan `TransactionDetail`.
2.  **Requirement 2 (Secure Deep Linking Pipeline):**
    *   Dukung schema: `https://app.sandbox.enterprise.io/market/:symbol` dan `enterprise://market/:symbol`.
    *   Terapkan validator Zod runtime untuk memastikan parameter `:symbol` berupa uppercase string dengan panjang 3–5 karakter (contoh: `BTC`, `ETH`).
3.  **Requirement 3 (Deferred Deep Link Trap):**
    *   Jika link diakses oleh pengguna yang belum terotentikasi, tangkap URL tersebut ke transient in-memory store.
    *   Arahkan user ke `Login` -> `TwoFactorAuth`.
    *   Setelah proses verifikasi otentikasi berhasil diselesaikan, eksekusi deferred URL yang tertunda secara deterministik tanpa user harus mengklik ulang link tersebut.
4.  **Requirement 4 (Performance & Hardening):**
    *   Aktifkan `enableFreeze(true)`.
    *   Pastikan hardware back navigation pada Android saat berada di `TransactionDetail` kembali ke `Feed`, bukan menutup aplikasi. Tolak semua URL yang mengandung subdomain tidak terverifikasi.