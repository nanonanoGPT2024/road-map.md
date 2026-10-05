# BAB-04-Navigation-dan-Deep-Linking-Architecture: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi mandiri komprehensif untuk menguji pemahaman arsitektural navigasi native, routing state machine, type-safety navigation stack, dynamic link parsing, Universal Links/App Links, serta penanganan cold-start deep linking pada React Native.

---

## Bagian 1: 5 Basic Questions

### Pertanyaan 1: Perbedaan Stack Navigator vs Native Stack Navigator
**Pertanyaan:**
Mengapa di arsitektur React Navigation modern direkomendasikan menggunakan `@react-navigation/native-stack` dibandingkan `@react-navigation/stack` standar berbasis JavaScript?

**Kunci Jawaban & Analisis:**
- `@react-navigation/stack` mengimplementasikan transisi, gestur swipe-back, dan lifecycle halaman sepenuhnya di JavaScript layer menggunakan React Native Reanimated dan Gesture Handler. Hal ini mengonsumsi jembatan JS-Native dan memory overhead yang lebih tinggi.
- `@react-navigation/native-stack` membungkus view container native secara langsung (`UINavigationController` pada iOS dan `FragmentContainerView` / `CoordinatorLayout` pada Android) melalui library `react-native-screens`. 
- Implikasinya: Transisi layar berjalan 60/120 FPS tanpa lag JS-thread, konsumsi memori jauh lebih rendah karena view yang tidak terlihat benar-benar di-unmount dari hierarchy native window, serta integrasi native header search bar berjalan out-of-the-box.

---

### Pertanyaan 2: Perilaku `navigation.navigate` vs `navigation.push`
**Pertanyaan:**
Kapan Anda harus menggunakan `navigation.push('ProductDetail', { id })` alih-alih `navigation.navigate('ProductDetail', { id })` pada sebuah Stack Navigator?

**Kunci Jawaban & Analisis:**
- `navigation.navigate('RouteName', params)` memeriksa history stack terlebih dahulu. Jika route target sudah ada di stack saat ini, navigator hanya memperbarui parameter (`setParams`) dan berpindah ke layar tersebut tanpa menambah instance layar baru ke atas stack.
- `navigation.push('RouteName', params)` selalu membuat dan menambahkan instance screen baru ke tumpukan navigasi, terlepas dari apakah route dengan nama tersebut sudah aktif sebelumnya.
- Kasus penggunaan `push`: Fitur e-commerce relasi produk (misal: "Produk Terkait" di mana user mengklik produk serupa dari layar `ProductDetail` dan ingin membuka layar `ProductDetail` berikutnya, dengan kemampuan tombol back mengembalikan user ke produk sebelumnya).

---

### Pertanyaan 3: Type Safety pada React Navigation (TypeScript)
**Pertanyaan:**
Bagaimana deklarasi tipe navigasi global didefinisikan menggunakan TypeScript Declaration Merging agar `useNavigation()` dan komponen navigasi otomatis memiliki auto-completion dan type safety tanpa perlu inject generic type manual di setiap hook?

**Kunci Jawaban & Analisis:**
Dengan melakukan declaration merging pada namespace global React Navigation:
```typescript
import { RootStackParamList } from './types';

declare global {
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}
```
Ketika `RootParamList` didefinisikan, hook `useNavigation()` dan component `Link` akan mengenali seluruh daftar route beserta tipe parameter masing-masing secara global di seluruh project.

---

### Pertanyaan 4: Perbedaan Custom URL Schemes vs Universal Links / Android App Links
**Pertanyaan:**
Sebutkan perbedaan arsitektur fundamental antara Custom URL Schemes (contoh: `myapp://checkout/123`) dengan Universal Links (iOS) / Android App Links (contoh: `https://app.example.com/checkout/123`) dari sisi keamanan dan UX fallback.

**Kunci Jawaban & Analisis:**
- **Custom URL Scheme (`myapp://`):**
  - Tidak diverifikasi secara kriptografis oleh OS. Aplikasi jahat (malicious app) dapat mendaftarkan schema yang sama dan berpotensi membajak (hijack) parameter/token deep link.
  - Jika aplikasi tidak terpasang di device, URL scheme akan gagal dieksekusi atau memunculkan pesan error "Address Invalid" di browser tanpa kemampuan fallback mulus ke halaman web resmi atau Play Store/App Store.
- **Universal Links / App Links (`https://`):**
  - Memerlukan kepemilikan domain terverifikasi melalui file JSON publik yang di-host di domain ber-HTTPS (`/.well-known/assetlinks.json` untuk Android dan `/.well-known/apple-app-site-association` untuk iOS).
  - Anti-hijacking karena OS hanya mengizinkan app dengan fingerprint certificate yang cocok untuk membuka link tersebut.
  - Fallback mulus: Jika aplikasi belum terinstall, link akan terbuka secara normal di browser web sebagai website reguler atau diarahkan ke landing page install.

---

### Pertanyaan 5: Siklus Hidup Layar pada React Native Screens
**Pertanyaan:**
Ketika berpindah dari Layar A ke Layar B menggunakan Stack Navigator, apakah komponen pada Layar A di-unmount? Hook apa yang tepat untuk mendeteksi bahwa Layar A kembali aktif di viewport?

**Kunci Jawaban & Analisis:**
- Komponen Layar A **tidak di-unmount** (`useEffect` cleanup tidak dipanggil). Layar A tetap berada di dalam memory stack tree namun status visibility-nya ditutup oleh Layar B.
- Untuk mendeteksi kapan Layar A mendapatkan fokus kembali atau kehilangan fokus, gunakan hook `useFocusEffect` dari React Navigation bersama dengan `React.useCallback`, bukan `useEffect` standar:
```typescript
import { useFocusEffect } from '@react-navigation/native';
import React from 'react';

useFocusEffect(
  React.useCallback(() => {
    // Dipanggil saat layar masuk ke viewport (focus)
    fetchDashboardData();

    return () => {
      // Dipanggil saat layar ditinggalkan (blur)
    };
  }, [])
);
```

---

## Bagian 2: 5 Intermediate Questions

### Pertanyaan 6: Dynamic Linking Configuration untuk Nested Navigator
**Pertanyaan:**
Diberikan URL `https://toko.com/shop/promo/flash-sale?source=banner`. Bagaimana konfigurasi objek `linking.config` di React Navigation jika arsitektur aplikasinya memiliki Root Stack -> Main Tab Navigator -> Shop Stack -> FlashSale Screen? Tuliskan struktur path mapping-nya.

**Kunci Jawaban & Analisis:**
Mapping nested route mengharuskan struktur hierarki navigator direfleksikan dalam property `screens`:
```typescript
const linking = {
  prefixes: ['https://toko.com', 'myapp://'],
  config: {
    screens: {
      MainTabs: {
        screens: {
          ShopTab: {
            screens: {
              FlashSale: {
                path: 'shop/promo/:campaignId',
                parse: {
                  campaignId: (id: string) => id.toLowerCase(),
                },
              },
            },
          },
        },
      },
    },
  },
};
```
Parameter query string seperti `?source=banner` secara otomatis diurai oleh React Navigation dan dimasukkan ke dalam `route.params.source`.

---

### Pertanyaan 7: Penanganan Cold Start vs Warm Start pada Deep Linking
**Pertanyaan:**
Jelaskan perbedaan penanganan `getInitialURL` (Cold Start) dan event listener `addEventListener('url')` (Warm/Hot Start) saat aplikasi menerima deep link dari status terminated vs background.

**Kunci Jawaban & Analisis:**
- **Cold Start (Status Terminated):**
  - Proses OS aplikasi belum berjalan di memori.
  - Link yang memicu pembukaan aplikasi ditangkap saat native engine booting. Method `Linking.getInitialURL()` mengembalikan Promise yang me-resolve URL tersebut sekali saja.
  - Tantangan arsitektur: Navigasi tidak boleh dipanggil sebelum seluruh authentication state (misal token JWT dari SecureStore) dan route hierarchy selesai diinisialisasi.
- **Warm / Hot Start (Status Background):**
  - Aplikasi sudah aktif di memory state dan hanya berpindah dari background ke foreground.
  - `getInitialURL()` akan mengembalikan `null` atau URL lama yang sudah usang.
  - URL baru ditangkap melalui subscriber event native: `Linking.addEventListener('url', callback)`.

---

### Pertanyaan 8: Arsitektur Protected Routes vs Dynamic Authentication Flow
**Pertanyaan:**
Mengapa pola rendering kondisional (`isLoggedIn ? <AppStack /> : <AuthStack />`) lebih disukai daripada menggunakan imperatif `navigation.navigate('Login')` ketika token kedaluwarsa? Apa dampak arsitekturalnya terhadap back-button stack?

**Kunci Jawaban & Analisis:**
- **Pembersihan Stack Otomatis (Deterministic State):**
  Dengan kondisional rendering, ketika state `isLoggedIn` berubah menjadi `false`, seluruh tumpukan `AppStack` seketika di-unmount dari React tree.
- **Mencegah Security Leak pada Back Button:**
  Jika menggunakan navigasi imperatif (`navigation.navigate('Login')`), halaman internal user (seperti saldo, profil, transaksi) masih tertinggal di bawah stack history. Pengguna dapat menekan tombol back hardware Android dan kembali melihat tampilan rahasia tanpa autentikasi valid.
- **Transisi Bebas Race-Condition:**
  State otentikasi dikendalikan oleh single source of truth (Context/Zustand/Redux). Navigator bereaksi secara deklaratif murni, menghindari bug navigasi tumpang-tindih saat refresh token gagal bersamaan dengan proses perpindahan screen.

---

### Pertanyaan 9: Deferred Deep Linking Architecture
**Pertanyaan:**
Apa yang dimaksud dengan Deferred Deep Linking, dan mengapa ini tidak dapat diselesaikan hanya dengan library bawaan `Linking` React Native tanpa backend service atau SDK pihak ketiga (seperti Branch.io, Adjust, atau Firebase Dynamic Links/AppsFlyer)?

**Kunci Jawaban & Analisis:**
- **Definisi:** Deferred Deep Linking adalah skenario di mana pengguna mengklik tautan campaign di web/iklan, namun **belum menginstal aplikasi**. Pengguna diarahkan ke App Store/Play Store terlebih dahulu. Setelah aplikasi diinstal dan dibuka pertama kali, aplikasi tetap harus membuka konten spesifik yang dituju oleh link awal tersebut.
- **Keterbatasan Native `Linking`:** OS mobile (iOS sandbox dan Android) tidak meneruskan parameter URL Safari/Chrome ke installer App Store secara default.
- **Mekanisme Solusi:** Memerlukan fingerprinting (IP address, user agent, canvas fingerprinting) atau Native Install Referrer API (Android Play Install Referrer) yang dicatat di server saat link diklik, lalu di-match oleh SDK pada saat aplikasi pertama kali launch dan mengirimkan payload attribution ke React layer.

---

### Pertanyaan 10: Mengatasi Memory Leak dan Optimasi Layar Kompleks dengan `freezeOnBlur`
**Pertanyaan:**
Apa fungsi properti `freezeOnBlur: true` yang disediakan oleh `react-native-screens` dalam Stack atau Bottom Tab Navigator? Bagaimana dampaknya terhadap komponen yang sedang melakukan render intensif?

**Kunci Jawaban & Analisis:**
- `freezeOnBlur: true` menggunakan mekanisme React Freeze (atau native equivalent) untuk menangguhkan (suspend) render cycle komponen ketika layar tersebut kehilangan fokus (`blur`).
- Jika layar A berada di background dan ada perubahan state global (misalnya websocket update atau store re-render), sub-tree layar A tidak akan memicu rendering ulang kalkulasi UI atau render loop sampai layar tersebut kembali ke foreground.
- Dampak: Menghemat CPU cycle dan konsumsi baterai secara signifikan pada aplikasi kompleks bertingkat dengan banyak listener di background tab.

---

## Bagian 3: 3 Skenario Kasus Nyata Produksi

### Skenario 1: Token Kedaluwarsa Saat Navigasi Deep Link Masuk (Race Condition)
**Konteks Masalah:**
Aplikasi fintech Anda menerima push notification berisi Universal Link: `https://pay.bank.id/transfer/confirmation?trx_id=TRX-9981`. Saat link diklik dari status aplikasi terminated, aplikasi membuka deep link tersebut. Namun, access token di SecureStore sudah expired dan refresh token gagal divalidasi oleh backend (HTTP 401).

**Tantangan Arsitektur:**
1. Mencegah layar `TransferConfirmation` sempat ter-render sekilas (UI flashing).
2. Menyimpan intended destination (`trx_id=TRX-9981`) ke dalam temporary storage atau memory buffer.
3. Mengarahkan user ke `LoginScreen`, dan setelah login sukses, secara otomatis meneruskan navigasi ke `TransferConfirmation` tanpa kehilangan konteks parameter.

**Solusi Arsitektural:**
```typescript
// 1. Inisialisasi Auth State + Deep Link Interceptor
type PendingDeepLink = {
  route: string;
  params?: Record<string, any>;
};

export const useDeepLinkCoordinator = () => {
  const [pendingRoute, setPendingRoute] = useState<PendingDeepLink | null>(null);
  const { isAuthenticated, isInitializing } = useAuthStore();

  const handleInterceptedUrl = async (url: string) => {
    const parsed = parseDeepLink(url);
    if (!isAuthenticated) {
      // Simpan rute yang diinginkan ke buffer
      setPendingRoute(parsed);
    } else {
      // Langsung dispatch jika sudah authenticated
      rootNavigationRef.navigate(parsed.route, parsed.params);
    }
  };

  // Dipanggil setelah LoginScreen sukses mengautentikasi
  const resumePendingNavigation = () => {
    if (pendingRoute) {
      rootNavigationRef.reset({
        index: 1,
        routes: [
          { name: 'HomeScreen' },
          { name: pendingRoute.route, params: pendingRoute.params },
        ],
      });
      setPendingRoute(null);
    }
  };

  return { handleInterceptedUrl, resumePendingNavigation };
};
```
- **Prinsip Kunci:** Jangan biarkan React Navigation melakukan auto-mount deep link sebelum state `isInitializing` dan verifikasi auth selesai. Gunakan flag `enabled={!isAuthChecking}` pada properti `linking` di `NavigationContainer` atau kelola `getInitialURL` kustom secara manual.

---

### Skenario 2: Android Back Button Loop pada Hierarki Nested Bottom Tabs & Modals
**Konteks Masalah:**
Aplikasi memiliki root modal stack dan bottom tab:
- `Tab 1: Home` -> `Tab 2: Orders` -> `Tab 3: Profile`.
- Dari `Home`, user membuka modal checkout bertingkat: `CartModal` -> `PaymentMethodModal` -> `PinValidationModal`.
- Saat berada di `PinValidationModal`, user menekan tombol hardware Back fisik Android. Terjadi bug: aplikasi langsung menutup seluruh modal ke Home atau aplikasi langsung keluar (minimize) karena default handler BackHandler Android tidak terikat dengan tumpukan modal navigator.

**Solusi Arsitektural:**
1. Mengatur `backBehavior="history"` atau `"order"` secara eksplisit pada BottomTabNavigator.
2. Memanfaatkan `useFocusEffect` dengan `BackHandler` native untuk mengonsumsi event back secara deterministik pada modal level tertinggi:
```typescript
import { BackHandler } from 'react-native';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import React from 'react';

export const PinValidationModal = () => {
  const navigation = useNavigation();

  useFocusEffect(
    React.useCallback(() => {
      const onBackPress = () => {
        // Tampilkan konfirmasi pembatalan transaksi, jangan biarkan pop langsung
        showAbortConfirmationDialog({
          onConfirmAbort: () => {
            navigation.getParent()?.goBack(); // Tutup seluruh modal flow
          },
        });
        return true; // Menandakan event telah di-handle, cegah default behavior
      };

      const subscription = BackHandler.addEventListener(
        'hardwareBackPress',
        onBackPress
      );

      return () => subscription.remove();
    }, [navigation])
  );

  return <PinValidationView />;
};
```

---

### Skenario 3: Penanganan Universal Links Gagal Validasi AASA (Apple App Site Association) di Lingkungan Enterprise
**Konteks Masalah:**
Sebuah aplikasi iOS enterprise dirilis ke internal tester melalui TestFlight. Universal Link `https://mycompany.com/report/100` selalu terbuka di Safari, tidak pernah membuka aplikasi native, padahal `Associated Domains` sudah diset ke `applinks:mycompany.com`.

**Root Cause Troubleshooting & Solusi:**
1. **Pemeriksaan File AASA:**
   - URL harus dapat diakses via HTTPS tanpa redirect (HTTP 301/302 dilarang keras oleh Apple CDN).
   - Header `Content-Type` wajib `application/json` (tidak boleh `text/plain` atau `text/html`).
   - Format App ID harus: `<TeamID>.<BundleID>` (contoh: `9ABC123DEF.com.company.enterpriseapp`).
2. **Apple CDN Cache Invalidation:**
   - Sejak iOS 14, Apple mengunduh file AASA melalui Apple CDN scraping cache, bukan langsung dari server domain setiap saat.
   - Mode developer bypass untuk testing: Ubah entitlement di Xcode menjadi `applinks:mycompany.com?mode=developer` agar iOS langsung membaca ke server lokal tanpa melewati cache CDN Apple.
3. **Konfigurasi Path Pattern yang Valid:**
   Pastikan JSON AASA menggunakan pola format modern (Components array):
   ```json
   {
     "applinks": {
       "apps": [],
       "details": [
         {
           "appID": "9ABC123DEF.com.company.enterpriseapp",
           "components": [
             {
               "/": "/report/*",
               "comment": "Rute validasi report deep link"
             }
           ]
         }
       ]
     }
   }
   ```

---

## Bagian 4: 1 Practical Chapter Challenge

### Tantangan Implementasi: Robust Deep Link & Navigation Router Engine
**Instruksi:**
Buat sebuah arsitektur router file `NavigationCoordinator.ts` yang mengimplementasikan configuration object lengkap untuk `NavigationContainer` dengan kriteria teknis berikut:

#### Spesifikasi Kebutuhan:
1. **Dual Prefix Support:** Mendukung scheme custom `corpapp://` dan domain universal link `https://app.corp.io`.
2. **Deep Path Mapping:**
   - `corpapp://workspace/:workspaceId/document/:docId`
   - Mapping ke: `RootStack` -> `AppDrawer` -> `WorkspaceScreen` (param: `workspaceId`) -> `DocumentDetailModal` (param: `docId`).
3. **Custom `getInitialURL` dengan Event Telemetry:**
   - Log URL cold start ke analitik mock (`AnalyticsService.track('DEEP_LINK_OPENED', { url })`).
   - Sediakan fallback timeout 2000ms jika `Linking.getInitialURL()` hang di Android tertentu.
4. **Subscribe Function:**
   - Pasang listener `Linking.addEventListener` yang mengembalikan unsubscribe cleanup function.
5. **State Restoration & Fallback Loading Screen:**
   - Tampilkan `<SplashScreen />` native sampai custom routing config selesai ter-parse.

#### Implementasi Solusi Kode:

```typescript
import { LinkingOptions } from '@react-navigation/native';
import { Linking, Platform } from 'react-native';

export type RootParamList = {
  Auth: undefined;
  MainDrawer: {
    screen: string;
    params: {
      workspaceId: string;
      screen?: string;
      params?: {
        docId: string;
      };
    };
  };
  DocumentDetailModal: {
    workspaceId: string;
    docId: string;
  };
  NotFound: undefined;
};

// Mock telemetry service
const AnalyticsService = {
  track: (event: string, payload: Record<string, any>) => {
    console.log(`[Telemetry] ${event}:`, JSON.stringify(payload));
  },
};

export const AppLinkingConfig: LinkingOptions<RootParamList> = {
  prefixes: ['corpapp://', 'https://app.corp.io'],

  config: {
    screens: {
      MainDrawer: {
        screens: {
          Workspace: {
            path: 'workspace/:workspaceId',
          },
        },
      },
      DocumentDetailModal: {
        path: 'workspace/:workspaceId/document/:docId',
        parse: {
          workspaceId: String,
          docId: (id: string) => id.trim(),
        },
      },
      NotFound: '*',
    },
  },

  async getInitialURL() {
    // 1. Timeout protection pattern untuk menghindari cold start hang
    const linkingPromise = Linking.getInitialURL();
    const timeoutPromise = new Promise<null>((resolve) =>
      setTimeout(() => resolve(null), 2000)
    );

    const initialUrl = await Promise.race([linkingPromise, timeoutPromise]);

    if (initialUrl) {
      AnalyticsService.track('DEEP_LINK_COLD_START', {
        url: initialUrl,
        platform: Platform.OS,
        timestamp: Date.now(),
      });
      return initialUrl;
    }

    return null;
  },

  subscribe(listener) {
    const onReceiveURL = ({ url }: { url: string }) => {
      AnalyticsService.track('DEEP_LINK_WARM_START', {
        url,
        platform: Platform.OS,
        timestamp: Date.now(),
      });
      listener(url);
    };

    const subscription = Linking.addEventListener('url', onReceiveURL);

    return () => {
      subscription.remove();
    };
  },
};
```

---

## Bagian 5: Checklist Pemahaman (Self-Assessment)

Gunakan daftar periksa berikut untuk mengonfirmasi penguasaan materi Bab 4 sebelum melanjutkan ke tahap arsitektur berikutnya:

- [ ] **Type-Safety:** Saya mampu menyusun declaration merging `ReactNavigation.RootParamList` dan mengetikkan `NativeStackScreenProps<ParamList, RouteName>` dengan benar tanpa ada implicit `any`.
- [ ] **Stack Engine:** Saya memahami perbedaan mendalam antara `@react-navigation/native-stack` (`react-native-screens`) dan `@react-navigation/stack` berbasis JS animations.
- [ ] **Lifecycle Navigation:** Saya paham kapan harus memakai `useFocusEffect` dan `useIsFocused` alih-alih `useEffect` biasa untuk mencegah stale memory pada inactive screens.
- [ ] **Routing Kondisional vs Imperatif:** Saya memahami alasan keamanan perancangan protected stack menggunakan state kondisional deklaratif daripada memanggil `navigation.replace('Home')`.
- [ ] **Deep Linking Prefix & Path Parsing:** Saya mampu mengonfigurasi nested paths, parameter query string, dynamic segment params, dan wildcard fallback (`*`).
- [ ] **Security & Anti-Hijacking:** Saya dapat menjelaskan mekanisme otentikasi domain pada Apple App Site Association (`apple-app-site-association`) dan Android Digital Asset Links (`assetlinks.json`).
- [ ] **Hardware Back Handling:** Saya dapat mengontrol siklus event `hardwareBackPress` di Android menggunakan `BackHandler` dan mencegah back button loops pada modal flow.
