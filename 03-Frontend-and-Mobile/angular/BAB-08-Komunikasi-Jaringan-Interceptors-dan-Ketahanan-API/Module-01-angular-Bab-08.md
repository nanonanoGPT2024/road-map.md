# Bab 08 Module 01: Komunikasi Jaringan, Interceptors, dan Ketahanan API

---

## SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** 03-Frontend-and-Mobile
* **Jalur Spesialisasi:** Angular Enterprise Architecture & Production Readiness
* **Kode Modul:** ANG-08-01
* **Judul Modul:** Komunikasi Jaringan, Interceptors, dan Ketahanan API
* **Prasyarat Pengetahuan:** 
  * RxJS Deep Dive (Observables, Schedulers, Operators: `switchMap`, `catchError`, `retry`, `shareReplay`)
  * Dependency Injection (DI) Hierarki Angular & Injection Tokens
  * TypeScript Generics tingkat lanjut & Typing System
  * Arsitektur HTTP/2 dan HTTP/3 dasar, status codes, dan semantic REST
* **Tingkat Kesulitan:** Advanced / Enterprise Staff Engineer
* **Target Lingkungan Eksekusi:** Angular 17/18+ (Stand-alone API & Functional Interceptors), Node.js LTS, TypeScript 5.4+

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini secara mendalam, peserta didik diharapkan mampu:

1. **Mengonfigurasi dan Membedah Mekanisme Internal `HttpClient` Standalone:** Menguasai migrasi dari modul lama berbasis class (`HTTP_INTERCEPTORS`) menuju pola modern Angular berbasis fungsi (`provideHttpClient(withInterceptors([...]))`) serta memahami lifecyclenya.
2. **Merancang Komposisi Functional Interceptors Rantai Ganda:** Mengimplementasikan rantai pipeline asinkronus interceptor untuk mutasi header otentikasi, tracing korelasi ID, manipulasi request/response, dan penanganan status secara terisolasi.
3. **Membangun Pola Ketahanan Jaringan Tingkat Produksi (Production Resiliency Patterns):** Mengimplementasikan Circuit Breaker, Exponential Backoff dengan Dynamic Jitter, dan Request Retries cerdas berbasis error response klasifikasi (4xx vs 5xx vs Network Failure).
4. **Menerapkan Mekanisme Mutasi Token JWT yang Thread-Safe:** Mengatasi *Race Condition* pada penyegaran token paralel (concurrent 401 Unauthorized errors) menggunakan antrean RxJS (`Subject`, `filter`, `take`, `switchMap`).
5. **Mengamankan Jalur Komunikasi HTTP:** Mengurangi risiko celah keamanan Web Application Client-Side, meliputi mitigasi XSS/CSRF, sanitasi header berbahaya, isolasi kredensial, dan implementasi context token selektif (`HttpContextToken`).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Komunikasi Jaringan Adalah Rantai Mutasi Monadik Tak Tepercaya
Komunikasi jaringan pada arsitektur modern Angular bukanlah sekadar fungsi promise "panggil dan tunggu". Jaringan bersifat inheren tidak stabil, asinkron, dan berada di luar kontrol runtime aplikasi. Mental model yang tepat memperlakukan `HttpClient` sebagai **mesin pemrosesan stream berbasis event-driven** yang dibungkus oleh pola monad RxJS.

```
       [ Client Intent ]
              │
              ▼
   ┌─────────────────────┐
   │ HttpRequest Monad   │ ◄── Immutable Data Structure
   └─────────────────────┘
              │
    Pipeline Transformation (Interceptors)
              │
              ▼
   ┌─────────────────────┐
   │ In-Flight Execution │ ◄── Subjek Kegagalan Jaringan & Latensi
   └─────────────────────┘
              │
    Pipeline Transformation (Resilience & Handlers)
              │
              ▼
   ┌─────────────────────┐
   │ HttpResponse Monad  │ ◄── Validated Domain Data OR Handled Exception
   └─────────────────────┘
```

Prinsip fundamental:
* **Immutabilitas Total:** Objek `HttpRequest` dan `HttpResponse` bersifat immutable. Setiap interceptor tidak memodifikasi objek yang ada, melainkan membuat kloningan baru (`req.clone()`) dengan nilai ter-update.
* **Functional Chain of Responsibility:** Setiap interceptor adalah satu tautan dalam rantai (`HttpHandlerFn`). Interceptor memiliki kontrol mutlak untuk meneruskan request, memblokirnya, memperbanyaknya, atau mengalihkan jalurnya ke cache lokal tanpa menyentuh network layer fisik.
* **Graceful Degradation:** Aplikasi tidak boleh crash atau menampilkan state rusak akibat *timeout* atau *packet drop*. Kegagalan jaringan adalah skenario kelas satu (*first-class citizen*) yang wajib diantisipasi dengan sistem pertahanan berlapis (circuit breaking, fallback response, dan exponential backoff).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram aliran data end-to-end pemrosesan HTTP Request/Response dalam Angular modern, mencakup rantai functional interceptors, mitigasi 401 token refresh concurrency, dan circuit breaker:

```
[ Angular Service / Feature Component ]
                   │
                   ▼  (Invokes http.get / http.post)
       ┌────────────────────────┐
       │   HttpClient Engine    │
       └────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│           FUNCTIONAL INTERCEPTORS PIPELINE             │
│                                                        │
│  [ Interceptor 1: Correlation & Tracing ID ]           │
│        │  Injects 'X-Correlation-ID'                   │
│        ▼                                               │
│  [ Interceptor 2: Authentication (Bearer Token) ]      │
│        │  Injects Authorization Header                 │
│        ▼                                               │
│  [ Interceptor 3: Resilience & Circuit Breaker ]       │
│        │  Evaluates Circuit State: OPEN / HALF / CLOSE │
│        ▼                                               │
│  [ Interceptor 4: HttpCaching (Optional Bypass) ]      │
└────────────────────────────────────────────────────────┘
                   │
                   ▼ (Forwarded via HttpBackend)
       ┌────────────────────────┐
       │  Angular HttpBackend   │ (Translates to native fetch/XHR)
       └────────────────────────┘
                   │
                   ▼
      ═════════════════════════════  [ Physical Network Boundary ]
             Remote Server
      ═════════════════════════════  [ Physical Network Boundary ]
                   │
                   ▼ (Raw HTTP Response / Error 401/500/Timeout)
       ┌────────────────────────┐
       │  Angular HttpBackend   │
       └────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│         RESPONSE PIPELINE (Unwinding Interceptors)     │
│                                                        │
│  [ Error Evaluator & Circuit Breaker State Recorder ]  │
│        │                                               │
│        ├─── (HTTP 200 OK) ──► Record Success in Breaker│
│        │                                               │
│        └─── (HTTP 401 Unauthorized)                    │
│                 │                                      │
│                 ▼                                      │
│      [ Token Refresh Mutex Lock ]                      │
│                 │                                      │
│         Is Refreshing?                                 │
│         ├── NO  ──► Launch Refresh Token Request       │
│         │           Block Subsequent 401 Requests      │
│         │           On Success: Replay Pending Reqs    │
│         │                                              │
│         └── YES ──► Queue in Waiter BehaviorSubject    │
│                     Wait for New Token & Re-issue      │
└────────────────────────────────────────────────────────┘
                   │
                   ▼
       [ Final Domain Observable ] ──► (Component Subscription)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Evolusi Arsitektur: Class Interceptor vs Functional Interceptor
Sebelum Angular 15, interceptor didefinisikan melalui interface `HttpInterceptor` berbasis class dan didaftarkan ke array injection token `HTTP_INTERCEPTORS` multi-provider. Kelemahannya meliputi:
* Masalah *tree-shaking* dan overhead boilerplate class.
* Resolusi dependensi yang lambat karena pencarian di multiple injector hierarchy.
* Kompleksitas dalam pengujian unit yang membutuhkan setup `TestBed` masif.

Angular modern beralih ke functional interceptor yang menggunakan fungsi bertipe `HttpInterceptorFn`. Signature intinya adalah:

```typescript
export type HttpInterceptorFn = (
  req: HttpRequest<unknown>,
  next: HttpHandlerFn
) => Observable<HttpEvent<unknown>>;
```

`HttpHandlerFn` sendiri adalah fungsi bertipe `(req: HttpRequest<unknown>) => Observable<HttpEvent<unknown>>`. Saat `provideHttpClient(withInterceptors([fn1, fn2, fn3]))` dipanggil, Angular secara internal menyusun pipeline komposisi fungsi menggunakan teknik serupa dengan middleware pipeline (contoh: Redux middleware atau Koa).

### 2. Mekanisme Internal Penyusunan Pipeline
Di dalam `@angular/common/http`, Angular mengompilasi rantai array interceptor secara berurutan. Mekanisme simplifikasinya dapat diilustrasikan sebagai berikut:

```typescript
// Konseptual engine internal Angular HttpClient
function buildChain(interceptors: HttpInterceptorFn[], backend: HttpBackend): HttpHandlerFn {
  return interceptors.reduceRight<HttpHandlerFn>(
    (nextHandler, currentInterceptor) => (req) => currentInterceptor(req, nextHandler),
    (req) => backend.handle(req)
  );
}
```
* **Arah Request:** Dari interceptor array index `0` ke index `N-1`, lalu ke `HttpBackend`.
* **Arah Response:** Dibalik dari `HttpBackend`, mengalir kembali melalui operator RxJS dari index `N-1` mundur ke index `0`.

### 3. HttpContext: Parameterisasi Metadatalevel Request
Seringkali sebuah interceptor harus bersifat selektif (misal: bypass logging untuk request analytics, atau bypass retry untuk mutasi kritis non-idempotent). Mengotori URL atau header kustom untuk mengirim flag metadata internal aplikasi adalah antipattern yang berbahaya.

Angular menyediakan `HttpContext` dan `HttpContextToken`. Objek ini bersifat type-safe, mutabel lokal pada level inisialisasi request, dan tidak akan bocor ke dalam HTTP header aktual yang dikirimkan ke server.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. Analisis Status Idempotensi dan Kebijakan Retry
Retry jaringan tidak boleh dilakukan secara membabi buta. Sesuai spesifikasi RFC 7231 / RFC 9110:
* **Metode Idempotent (`GET`, `PUT`, `DELETE`, `HEAD`, `OPTIONS`):** Secara teoritis aman dieksekusi berulang kali tanpa mengubah state sistem di luar eksekusi pertama.
* **Metode Non-Idempotent (`POST`, `PATCH`):** Retry otomatis pada kegagalan timeout berisiko menciptakan duplikasi transaksi keuangan, duplikasi entitas, atau inkonsistensi state jika server sebenarnya telah memproses request namun koneksi ACK terputus di tengah jalan.

Oleh karena itu, strategi retry pada interceptor enterprise **wajib** memeriksa:
1. HTTP Method dari `HttpRequest`.
2. HTTP Status Code (hanya melakukan retry pada error transien: status code `0` (Network Error/CORS Drop), `408` (Request Timeout), `429` (Too Many Requests), `502` (Bad Gateway), `503` (Service Unavailable), dan `504` (Gateway Timeout)). Jangan pernah me-retry status `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, atau `404 Not Found`.

### 2. Teori Exponential Backoff dengan Jitter
Algoritma Backoff eksponensial standar meningkatkan waktu jeda secara eksponensial:
$$\text{Delay} = \text{base} \times 2^{\text{attempt}}$$
Namun, jika ratusan ribu client mengalami kegagalan serentak (misal, backend restart), backoff murni akan menghasilkan fenomena **Thundering Herd Problem** di mana seluruh client melakukan koneksi kembali pada detik yang sama secara periodik.

Solusinya adalah menambahkan **Full Jitter**:
$$\text{Delay}_{\text{actual}} = \text{random}(0, \, \min(\text{maxDelay}, \, \text{base} \times 2^{\text{attempt}}))$$
Jitter menyebarkan trafik secara merata di sepanjang sumbu waktu, meredam lonjakan beban saat server dalam masa pemulihan.

### 3. Finite State Machine: Circuit Breaker Pattern
Circuit Breaker pada arsitektur frontend memproteksi thread client dan mencegah membanjiri server yang sedang *down*. Pola ini memiliki 3 state:
1. **CLOSED:** Semua request dilewatkan secara normal. Kegagalan dihitung menggunakan sliding time window. Jika failure rate melebihi ambang batas (*threshold*), state berubah menjadi **OPEN**.
2. **OPEN:** Jaringan langsung diputus di client tanpa mengirim request ke server. `Observable` langsung melempar fallback error lokal `CircuitBreakerOpenException`. Timer cool-off diaktifkan.
3. **HALF-OPEN:** Setelah timer cool-off habis, sistem mengizinkan satu request uji (*trial probe*). Jika sukses, sirkuit kembali ke **CLOSED**. Jika gagal, sirkuit kembali ke **OPEN** dan timer diperpanjang.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi functional interceptor fundamental untuk injeksi Bearer Token dan Tracing Header menggunakan `HttpContextToken` untuk bypass otentikasi.

### Konfigurasi HttpContext Token (`auth.context.ts`)

```typescript
import { HttpContextToken } from '@angular/common/http';

/**
 * Token konteks untuk menandai apakah request memerlukan token JWT atau bersifat publik.
 * Default: true (memerlukan otentikasi)
 */
export const REQUIRES_AUTH = new HttpContextToken<boolean>(() => true);
```

### Implementasi Functional Auth Interceptor (`auth.interceptor.ts`)

```typescript
import { inject } from '@angular/core';
import { 
  HttpInterceptorFn, 
  HttpRequest, 
  HttpHandlerFn, 
  HttpEvent 
} from '@angular/common/http';
import { Observable } from 'rxjs';
import { REQUIRES_AUTH } from './auth.context';
import { AuthService } from './auth.service';

export const authInterceptor: HttpInterceptorFn = (
  req: HttpRequest<unknown>,
  next: HttpHandlerFn
): Observable<HttpEvent<unknown>> => {
  const authService = inject(AuthService);
  const requiresAuth = req.context.get(REQUIRES_AUTH);

  // Jalur Bypass: Jika request secara eksplisit menandai tidak membutuhkan otentikasi
  if (!requiresAuth) {
    return next(req);
  }

  const token = authService.getAccessToken();

  // Jika token belum tersedia di storage, teruskan tanpa modifikasi
  if (!token) {
    return next(req);
  }

  // Lakukan immutability clone dan sertakan Header Authorization
  const authReq = req.clone({
    setHeaders: {
      Authorization: `Bearer ${token}`,
      'X-Client-Timestamp': Date.now().toString()
    }
  });

  return next(authReq);
};
```

### Registrasi Interceptor pada Standalone Application (`app.config.ts`)

```typescript
import { ApplicationConfig } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { authInterceptor } from './auth.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideHttpClient(
      withInterceptors([
        authInterceptor
      ])
    )
  ]
};
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Membedah baris kode kritis pada file `auth.interceptor.ts`:

1. `export const authInterceptor: HttpInterceptorFn = (req, next) => {`:
   * **Analisis:** Mendefinisikan interceptor sebagai fungsi murni (*pure function*) yang memenuhi interface `HttpInterceptorFn`. Ini menghilangkan kebutuhan instansiasi class dan dekorator `@Injectable()`.
2. `const authService = inject(AuthService);`:
   * **Analisis:** Menggunakan runtime function `inject()` dari Angular Core. Injeksi dependensi dieksekusi secara instan dalam execution context pembuatan pipeline tanpa konstruktor.
3. `const requiresAuth = req.context.get(REQUIRES_AUTH);`:
   * **Analisis:** Mengakses map metadata internal yang menempel pada instance request. Jika pengembang memanggil HTTP method dengan `new HttpContext().set(REQUIRES_AUTH, false)`, nilai ini akan dievaluasi `false`.
4. `if (!requiresAuth) { return next(req); }`:
   * **Analisis:** Optimasi *early return*. Menghindari cloning dan akses storage yang tidak perlu untuk resource publik seperti static assets, manifest, atau login endpoint itu sendiri.
5. `const authReq = req.clone({ setHeaders: { ... } });`:
   * **Analisis:** `req.clone()` mutlak diperlukan karena objek `HttpRequest` di-freeze secara internal oleh Angular. Properti `setHeaders` secara otomatis menggabungkan (*shallow merge*) header baru tanpa menghapus header yang telah didefinisikan sebelumnya pada layer pemanggilan service.
6. `return next(authReq);`:
   * **Analisis:** Meneruskan salinan request yang telah termutasi ke interceptor berikutnya di rantai handler, atau langsung dieksekusi ke network gateway jika ini interceptor terakhir.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Enterprise: Sistem Pembayaran FinTech Skala Global
Pada platform core-banking berskala 10 juta pengguna aktif harian, dua masalah utama sering mengacaukan operasional sistem:
1. **The 401 Parallel Storm:** Saat JWT access-token kedaluwarsa (masa aktif 5 menit), sebuah dasbor yang memuat 12 micro-widget secara simultan menembakkan 12 HTTP request paralel. Ke-12 request tersebut serentak menerima status `401 Unauthorized`. Tanpa penanganan khusus, aplikasi akan menembakkan 12 request *refresh token* ke Identity Provider (IdP) secara paralel. Hal ini memicu IdP mendeteksi anomali *replay attack*, membatalkan *refresh token family*, dan secara paksa melempar sesi user ke halaman login (*forced logout*).
2. **Network Flapping & Spikes:** Koneksi seluler pengguna mikro di daerah terpencil sering mengalami drop sementara (durasi 500ms - 2000ms). Kegagalan langsung pada API mutasi query membuat aplikasi terlihat rapuh jika tidak ada retry pintar dan pemantauan kegagalan total server melalui Circuit Breaker.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi skala enterprise yang menyelesaikan kedua masalah di atas. Sistem mencakup **Thread-Safe Concurrent Token Refresh Lock** dan **Circuit Breaker dengan Adaptive Backoff**.

### 1. Token Refresh Mutex Service (`token-vault.service.ts`)

```typescript
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpContext } from '@angular/common/http';
import { Observable, BehaviorSubject, throwError, of } from 'rxjs';
import { catchError, filter, switchMap, take, tap } from 'rxjs/operators';
import { REQUIRES_AUTH } from './auth.context';

export interface TokenResponse {
  accessToken: string;
  refreshToken: string;
}

@Injectable({
  providedIn: 'root'
})
export class TokenVaultService {
  private readonly http = inject(HttpClient);
  
  private rawAccessToken: string | null = null;
  private rawRefreshToken: string | null = null;
  
  // State lock flag dan notifier untuk paralelisme request
  private isRefreshingToken = false;
  private readonly refreshTokenSubject = new BehaviorSubject<string | null>(null);

  getAccessToken(): string | null {
    return this.rawAccessToken;
  }

  setTokens(access: string, refresh: string): void {
    this.rawAccessToken = access;
    this.rawRefreshToken = refresh;
  }

  clearTokens(): void {
    this.rawAccessToken = null;
    this.rawRefreshToken = null;
    this.refreshTokenSubject.next(null);
  }

  /**
   * Mengatur antrean terpusat untuk refresh token.
   * Menjamin hanya SATU request POST refresh yang mengudara,
   * sementara request 401 lainnya parkir menunggu token baru.
   */
  handle401Concurrency(failedRequestCaller: (newToken: string) => Observable<unknown>): Observable<unknown> {
    if (!this.isRefreshingToken) {
      this.isRefreshingToken = true;
      this.refreshTokenSubject.next(null); // Reset barrier lock

      return this.executeRefreshToken().pipe(
        switchMap((tokens: TokenResponse) => {
          this.isRefreshingToken = false;
          this.setTokens(tokens.accessToken, tokens.refreshToken);
          this.refreshTokenSubject.next(tokens.accessToken); // Rilis antrean dengan token baru
          return failedRequestCaller(tokens.accessToken);
        }),
        catchError((refreshErr) => {
          this.isRefreshingToken = false;
          this.clearTokens();
          // Notifikasi session drop/logout paksa
          return throwError(() => refreshErr);
        })
      );
    }

    // Jika refresh sedang berjalan, tunggu hingga refreshTokenSubject memancarkan token non-null
    return this.refreshTokenSubject.pipe(
      filter((token): token is string => token !== null),
      take(1),
      switchMap((token: string) => {
        return failedRequestCaller(token);
      })
    );
  }

  private executeRefreshToken(): Observable<TokenResponse> {
    if (!this.rawRefreshToken) {
      return throwError(() => new Error('No refresh token available.'));
    }

    // Hindari pemanggilan auth interceptor yang rekursif
    const context = new HttpContext().set(REQUIRES_AUTH, false);

    return this.http.post<TokenResponse>(
      'https://api.enterprise.fintech.io/v1/auth/refresh',
      { refreshToken: this.rawRefreshToken },
      { context }
    );
  }
}
```

### 2. Core Circuit Breaker Primitive (`circuit-breaker.ts`)

```typescript
export enum CircuitState {
  CLOSED,
  OPEN,
  HALF_OPEN
}

export class CircuitBreakerConfig {
  constructor(
    public readonly failureThreshold: number = 5,
    public readonly resetTimeoutMs: number = 15000,
    public readonly monitoredStatusCodes: number[] = [0, 500, 502, 503, 504]
  ) {}
}

export class CircuitBreaker {
  private state: CircuitState = CircuitState.CLOSED;
  private failureCount = 0;
  private lastFailureTime = 0;

  constructor(private readonly config: CircuitBreakerConfig = new CircuitBreakerConfig()) {}

  canExecute(): boolean {
    if (this.state === CircuitState.OPEN) {
      const now = Date.now();
      if (now - this.lastFailureTime > this.config.resetTimeoutMs) {
        this.state = CircuitState.HALF_OPEN;
        return true;
      }
      return false;
    }
    return true;
  }

  recordSuccess(): void {
    this.failureCount = 0;
    this.state = CircuitState.CLOSED;
  }

  recordFailure(status: number): void {
    if (!this.config.monitoredStatusCodes.includes(status)) {
      return; // Status non-infrastruktur tidak mempengaruhi sirkuit
    }

    this.failureCount++;
    this.lastFailureTime = Date.now();

    if (this.state === CircuitState.HALF_OPEN || this.failureCount >= this.config.failureThreshold) {
      this.state = CircuitState.OPEN;
    }
  }

  getState(): CircuitState {
    return this.state;
  }
}

export const GlobalApiCircuitBreaker = new CircuitBreaker();
```

### 3. Production Resilient Interceptor (`enterprise-resilience.interceptor.ts`)

```typescript
import { inject } from '@angular/core';
import {
  HttpInterceptorFn,
  HttpRequest,
  HttpHandlerFn,
  HttpEvent,
  HttpErrorResponse
} from '@angular/common/http';
import { Observable, throwError, timer } from 'rxjs';
import { catchError, retry } from 'rxjs/operators';
import { TokenVaultService } from './token-vault.service';
import { GlobalApiCircuitBreaker, CircuitState } from './circuit-breaker';

const MAX_RETRIES = 3;
const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 5000;

/**
 * Menghitung jeda eksponensial dengan Full Jitter.
 */
function calculateJitterBackoff(attempt: number): number {
  const exponential = INITIAL_BACKOFF_MS * Math.pow(2, attempt);
  const capped = Math.min(exponential, MAX_BACKOFF_MS);
  return Math.floor(Math.random() * capped);
}

export const enterpriseResilienceInterceptor: HttpInterceptorFn = (
  req: HttpRequest<unknown>,
  next: HttpHandlerFn
): Observable<HttpEvent<unknown>> => {
  const tokenVault = inject(TokenVaultService);

  // 1. Eksekusi Pengecekan Circuit Breaker
  if (!GlobalApiCircuitBreaker.canExecute()) {
    return throwError(() => new Error(
      `[CircuitBreaker] Komunikasi ke API diblokir sementara. Status: OPEN`
    ));
  }

  const executePipeline = (activeReq: HttpRequest<unknown>): Observable<HttpEvent<unknown>> => {
    return next(activeReq).pipe(
      // 2. Retry Logic hanya untuk Error Transien & Operasi Idempotent
      retry({
        count: MAX_RETRIES,
        delay: (error: unknown, retryIndex: number) => {
          if (error instanceof HttpErrorResponse) {
            const isIdempotent = ['GET', 'HEAD', 'PUT', 'DELETE', 'OPTIONS'].includes(activeReq.method);
            const isTransientError = [0, 408, 429, 502, 503, 504].includes(error.status);

            if (isIdempotent && isTransientError) {
              const jitterDelay = calculateJitterBackoff(retryIndex);
              return timer(jitterDelay);
            }
          }
          // Gagalkan retry jika tidak memenuhi kriteria
          return throwError(() => error);
        }
      }),
      // Catat respon sukses ke circuit breaker
      catchError((error: unknown) => {
        if (error instanceof HttpErrorResponse) {
          GlobalApiCircuitBreaker.recordFailure(error.status);

          // 3. Mutex Handling untuk Kasus Konkuren 401 Unauthorized
          if (error.status === 401) {
            return tokenVault.handle401Concurrency((newToken: string) => {
              const retryWithFreshToken = activeReq.clone({
                setHeaders: {
                  Authorization: `Bearer ${newToken}`
                }
              });
              return next(retryWithFreshToken);
            }) as Observable<HttpEvent<unknown>>;
          }
        } else {
          GlobalApiCircuitBreaker.recordFailure(0);
        }
        return throwError(() => error);
      })
    );
  };

  return executePipeline(req);
};
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter / Dimensi | Class-Based Interceptor (Legacy) | Functional Interceptor (Modern) | Service-Level Resilience (Decorator/Direct) |
| :--- | :--- | :--- | :--- |
| **Pohon Dependensi (DI)** | Terikat pada `HTTP_INTERCEPTORS` multi-token; resolusi runtime lebih berat | Hierarki fungsional langsung; dieksekusi via `inject()` saat pipeline dibentuk | Manual diinjeksikan per class/method service |
| **Efisiensi Bundler (Tree-Shaking)** | Rendah; class dan prototypenya sulit dieliminasi static analyzer | Sangat Tinggi; fungsi yang tidak direferensikan dipotong oleh Terser/Rollup | Tinggi (bila ditulis fungsional) |
| **Kapasitas Pemeliharaan & Skalabilitas** | Menghasilkan boilerplate class yang masif untuk logika sederhana | Ramping, mudah dikomposisikan via array (`pipe`-like design) | Buruk; duplikasi logika di banyak Angular services |
| **Fleksibilitas State Management** | State tersimpan di dalam instance class singleton | Memerlukan closures atau delegasi ke stateful service (`inject()`) | Tersimpan lokal di scope service bersangkutan |
| **Tracing & Testing** | Mocking kompleks; butuh konfigurasi `TestBed` masif dengan class provider | Mudah diuji secara unit murni dengan mengoper argumen mock `req` dan `next` | Sulit dipisahkan dari business logic service |

---

## SEKSI 12 — EDGE CASES & PITFALLS (Failure Modes & Mitigation)

### 1. The Infinite Token Refresh Loop
* **Skenario Gagal:** Endpoint autentikasi `/auth/refresh` itu sendiri merespon dengan status `401 Unauthorized` (misal refresh token telah habis masa aktifnya atau di-*revoke* oleh IdP). Jika interceptor secara naif menangkap semua `401` dan mencoba me-refresh token, aplikasi akan masuk ke infinite loop yang membekukan browser dan membombardir server backend.
* **Mitigasi:** Gunakan `HttpContextToken` untuk menandai request refresh token (`REQUIRES_AUTH = false`) dan berikan bypass guard eksplisit: jika URL request adalah endpoint `/auth/refresh`, bypass mutasi 401 dan langsung kirim event logout/redirect login.

### 2. Request Payload Stream Mutability pada Request Retry
* **Skenario Gagal:** Me-retry request dengan payload tipe `FormData` atau `ReadableStream`. Pada browser tertentu, stream reader yang telah terbaca parsial pada request pertama akan hangus (*consumed*), menyebabkan retry dikirimkan dengan payload kosong (0 bytes).
* **Mitigasi:** Hindari retry otomatis pada request yang membawa payload bertipe non-replayable body (seperti streaming upload chunks), atau pastikan wrapper stream membuat instance stream baru per percobaan.

### 3. Kebocoran Memori (Memory Leaks) pada BehaviorSubject Antrean
* **Skenario Gagal:** Komponen membatalkan subscription (`takeUntilDestroyed`) saat request 401 sedang parkir di dalam `refreshTokenSubject`. Jika subject mempertahankan referensi observer yang tidak pernah dibersihkan saat navigasi dibatalkan, memori komponen bocor.
* **Mitigasi:** Gunakan operator `take(1)` secara disiplin pada consumer antrean refresh token untuk memastikan subscription otomatis *complete* segera setelah emisi pertama terjadi.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Menimpa Header Tanpa Immutability Clone
```typescript
// SALAH (Mengakibatkan Runtime Error atau Silent Mutation)
req.headers.set('Authorization', `Bearer ${token}`); 
return next(req);

// BENAR
const secureReq = req.clone({
  setHeaders: {
    Authorization: `Bearer ${token}`
  }
});
return next(secureReq);
```

### Kesalahan Fatal 2: Menempatkan Urutan Interceptor Secara Acak
* **Penyebab:** Menyusun Logging Interceptor sebelum Authentication Interceptor, atau Caching Interceptor setelah Error Handler.
* **Dampak:** Log header tidak mencatat header otentikasi aktual yang telah disuntikkan, atau cache mengembalikan cached-response lama sebelum otentikasi divalidasi.
* **Aturan Urutan Standar:**
  1. *Correlation/Tracing ID* (Selalu pertama agar semua logger mengenali trace ID).
  2. *Authentication/Authorization* (Injeksi kredensial sebelum menyentuh caching atau network).
  3. *Caching Interceptor* (Dapat mengembalikan response lebih awal dan memutus rantai).
  4. *Resilience/Circuit Breaker & Retry* (Membungkus transmisi riil).
  5. *Logging/Telemetry Interceptor* (Mencatat status final sebelum diteruskan ke backend).

### Kesalahan Fatal 3: Memanggil `subscribe()` di dalam Interceptor
* **Penyebab:** Memanggil `.subscribe()` di dalam body interceptor untuk mengekstrak data response atau melakukan side-effect.
* **Dampak:** Memutus rantai monadik RxJS, mengubah eksekusi menjadi eager, menyebabkan kebocoran subscription, dan membuang kemampuan pembatalan request (*cancellation propagation*). Interceptor **wajib** murni mentransformasi stream via RxJS pipe operators (`tap`, `map`, `switchMap`, `catchError`).

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Definisikan Granular Timeout pada Level Network Request:** Selalu pasang operator `timeout()` pada pipeline interceptor untuk mencegah request berada dalam status pending tanpa batas akibat dead socket pada infrastruktur ISP client.
2. **Standardisasi Trace Context Header (W3C Trace Context):** Gunakan standar industri `traceparent` (W3C standard) atau `X-Correlation-ID` untuk menyatukan tracing log frontend dengan distributed tracing di backend (OpenTelemetry, Jaeger).
3. **Fail-Fast pada Circuit Breaker Terbuka:** Segera berikan respon error typed (misal `CircuitBreakerError`) ke UI layer agar aplikasi dapat langsung beralih menampilkan fallback template / offline banner tanpa membiarkan user menunggu latensi koneksi.
4. **Isolasi Domain Kredensial:** Verifikasi *Origin* dari request target sebelum menyuntikkan token Bearer. Jangan kirim token otentikasi internal perusahaan ke domain pihak ketiga (contoh: CDN S3 bucket atau API publik Google Maps) yang dipanggil via `HttpClient`.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### In-Flight Request Deduplication (Request Coalescing)
Ketika dua komponen UI yang berbeda menginisialisasi panggilan ke endpoint data statis yang sama pada waktu yang hampir bersamaan (misal: `/api/v1/config/system`), jangan menembakkan dua request network fisik. Buat interceptor atau service layer deduplikasi menggunakan `shareReplay({ bufferSize: 1, refCount: true })`.

```typescript
import { inject } from '@angular/core';
import { HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { tap, shareReplay } from 'rxjs/operators';

const inFlightRequests = new Map<string, Observable<any>>();

export const deduplicationInterceptor: HttpInterceptorFn = (req, next) => {
  // Hanya berlaku untuk metode GET
  if (req.method !== 'GET') {
    return next(req);
  }

  const key = req.urlWithParams;

  if (inFlightRequests.has(key)) {
    return inFlightRequests.get(key)!;
  }

  const networkRequest$ = next(req).pipe(
    tap({
      next: (event) => {
        if (event instanceof HttpResponse) {
          inFlightRequests.delete(key);
        }
      },
      error: () => inFlightRequests.delete(key)
    }),
    shareReplay({ bufferSize: 1, refCount: true })
  );

  inFlightRequests.set(key, networkRequest$);
  return networkRequest$;
};
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Pertahanan Cross-Site