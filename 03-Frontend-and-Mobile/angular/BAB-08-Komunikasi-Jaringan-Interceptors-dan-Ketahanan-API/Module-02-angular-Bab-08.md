# BAB 08: Komunikasi Jaringan, Interceptors, dan Ketahanan API
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis & Mengonfigurasi Rantai Interceptor Fungsional Modern**: Menguasai arsitektur internal `HttpInterceptorFn`, mekanisme perambatan `HttpHandlerFn`, serta manipulasi pipeline request/response secara deklaratif dan immutable.
- **Mengimplementasikan Token Refresh Mutex (Anti-Race Condition)**: Merancang mekanisme penanganan HTTP 401 terkoordinasi menggunakan primitif sinkronisasi RxJS (`BehaviorSubject`, `filter`, `take`, `switchMap`) untuk mencegah *thundering herd problem* terhadap endpoint autentikasi.
- **Membangun Client-Side Circuit Breaker & Exponential Backoff**: Mengembangkan interceptor ketahanan jaringan tingkat enterprise dengan transisi state *Closed*, *Open*, dan *Half-Open* guna melindungi upstream service dari degradasi performa.
- **Mengonfigurasi Dynamic Context Injection via `HttpContext`**: Memanfaatkan `HttpContextToken` untuk mengontrol perilaku interceptor (bypass caching, custom retry budget, custom authentication header) secara granular per pemanggilan API.
- **Mendesain Request Deduplication & In-Flight Coalescing**: Mengeliminasi HTTP duplicate calls yang terjadi secara konkuren menggunakan strategi memory caching dan RxJS multicasting (`shareReplay`).

---

### 2. Prerequisites
Sebelum mendalami modul ini, Anda wajib memiliki pemahaman mendalam tentang:
- **TypeScript Generics & Typing Tingkat Lanjut**: Generic constraints, mapped types, conditional types, dan mutabilitas objek (`Readonly<T>`).
- **RxJS Concurrency & Multicasting**: Perbedaan mendalam antara `Subject`, `BehaviorSubject`, `ReplaySubject`, serta operator transformasi tingkat lanjut (`concatMap`, `mergeMap`, `switchMap`, `exhaustMap`, `catchError`, `retry`).
- **Modern Angular Standalone Architecture**: Dependency Injection modern (`inject()`), standalone components, dan konfigurasi bootstrapping berbasis `provideHttpClient(withInterceptors([...]))`.
- **Protokol HTTP/1.1 & HTTP/2**: Semantik header, status code spesifik (401 Unauthorized, 403 Forbidden, 429 Too Many Requests, 503 Service Unavailable), serta multiplexing connection.

---

### 3. Concept & Internal Architecture (Mendalam)

#### Arsitektur Rantai Interceptor Fungsional (`HttpInterceptorFn`)
Mulai Angular 15+, arsitektur HTTP berevolusi dari interceptor berbasis kelas (`HttpInterceptor`) menuju interceptor fungsional berbasis closure (`HttpInterceptorFn`). Pendekatan ini menurunkan overhead alokasi memory, meningkatkan tree-shaking secara optimal, dan menyederhanakan dependency injection melalui fungsi `inject()`.

```
[UI Component / Service]
         │
         ▼ (HttpClient.get / post)
[HttpInterceptorFn #1 (Logging / Correlation ID)]
         │ next(req)
         ▼
[HttpInterceptorFn #2 (Authentication & Token Injector)]
         │ next(req)
         ▼
[HttpInterceptorFn #3 (Circuit Breaker & Retry)]
         │ next(req)
         ▼
[HttpInterceptorFn #4 (Caching & In-Flight Deduplication)]
         │ next(req)
         ▼
   [HttpBackend] ────────> [Network / REST Gateway]
```

Secara internal, rantai eksekusi interceptor direduksi menjadi rantai fungsi rekursif yang mengeksekusi `HttpHandlerFn`. Setiap interceptor memegang referensi ke interceptor berikutnya melalui parameter `next`. 

Ketika `next(req)` dipanggil:
1. Engine Angular memanggil interceptor berikutnya dalam array konfigurasi `withInterceptors([...])`.
2. Interceptor terakhir mendelegasikan eksekusi ke `HttpBackend` (biasanya `HttpXhrBackend` atau `HttpFetchBackend`).
3. Stream respons mengalir kembali secara terbalik melalui operator RxJS yang terikat pada Observable masing-masing interceptor.

#### Immutable Request & Clone Pattern
Objek `HttpRequest<T>` dan `HttpResponse<T>` dirancang secara mutlak sebagai objek **immutable** (tidak dapat diubah langsung). Karakteristik immutabilitas ini mencegah *side-effect* lintas interceptor paralel. Setiap mutasi header, parameter URL, atau body wajib dilakukan melalui metode `.clone()`:

```typescript
// Mekanisme internal Angular HttpHeaders clone
const modifiedReq = req.clone({
  headers: req.headers.set('X-Correlation-ID', crypto.randomUUID()),
  setHeaders: {
    'Authorization': `Bearer ${token}`
  }
});
```

#### Metadata Per-Request via `HttpContext`
Sering kali interceptor membutuhkan instruksi spesifik per-request (misal: "request ini tidak boleh di-cache" atau "request ini boleh melakukan 5x retry"). Mengotori HTTP Header dengan metadata internal klien merupakan antipattern. Angular menyediakan `HttpContext` yang berbasis tipe aman (`HttpContextToken<T>`).

```
┌────────────────────────────────────────────────────────┐
│                   HttpRequest                          │
│ ┌─────────────────┬──────────────────────────────────┐ │
│ │ Url, Method,    │           HttpContext            │ │
│ │ Body, Headers   │ ┌──────────────────────────────┐ │ │
│ │                 │ │ HttpContextToken<boolean>    │ │ │
│ │                 │ │ HttpContextToken<RetryConfig>│ │ │
│ │                 │ └──────────────────────────────┘ │ │
│ └─────────────────┴──────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

Konteks ini hidup di memori selama siklus hidup request dan tidak dipancarkan ke network wire, menjamin keamanan data dan efisiensi transmisi.

---

### 4. Why & What

| Dimensi | Pendekatan Naif / Tradisional | Arsitektur Interceptor Modern Enterprise |
| :--- | :--- | :--- |
| **Refresh Token Handling** | Menembak refresh endpoint di setiap kegagalan komponen secara terisolasi (menimbulkan N x refresh calls). | **Token Refresh Mutex**: Request pertama memicu refresh token; request konkuren lainnya di-*queue* via `BehaviorSubject` hingga token baru terbit. |
| **Fault Tolerance** | Mengabaikan kegagalan jaringan atau sekadar menampilkan popup error instan. | **Client-Side Circuit Breaker**: Mencegah downstream crash dengan memblokir panggilan saat server upstream mengalami failure beruntun. |
| **Request Optimization** | Komponen independen memicu request identik ke server secara bersamaan. | **In-Flight Request Deduplication**: Menggabungkan HTTP get paralel yang sama persis menjadi satu koneksi TCP menggunakan multicasting. |
| **Metadata Passing** | Menyuntikkan custom HTTP header (cth: `X-Skip-Auth: true`) yang kemudian harus dihapus manual. | **Type-Safe `HttpContext`**: Metadata diproses murni di runtime Angular tanpa menyentuh HTTP wire. |

---

### 5. How: Alur Kerja & Lifecycle Eksekusi

#### Skenario 1: Refresh Token Mutex (Concurreny Locking)
Ketika beberapa komponen memuat data secara paralel saat masa berlaku JWT kadaluarsa, seluruh pemanggilan API mengembalikan status 401 Unauthorized secara simultan.

```
Request A (401) ──┐
Request B (401) ──┼──> Interceptor ──> [Is Refreshing? NO]  ──> Panggil /auth/refresh
Request C (401) ──┘         │
                            ├──> [Is Refreshing? YES] ──> Tahan di Queue (RxJS Subject)
                            │                                     │
                            ▼                                     │
                 Refresh Berhasil (Token Baru)                     │
                            │                                     │
                            ├─────────────────────────────────────┘
                            ▼
              Rilis Seluruh Request dengan Token Baru
```

#### Skenario 2: State Machine Circuit Breaker
Circuit Breaker beroperasi menggunakan tiga state transisional:
1. **CLOSED**: Request diizinkan lewat secara normal. Jika rasio kegagalan melampaui ambang batas (*failure threshold*), transisi ke **OPEN**.
2. **OPEN**: Semua request langsung digagalkan secara instan di sisi klien (*fast-fail*) tanpa membuat koneksi HTTP ke server selama durasi `resetTimeout`.
3. **HALF-OPEN**: Setelah `resetTimeout` habis, satu request uji coba (*canary request*) diizinkan lewat. Jika sukses, kembali ke **CLOSED**. Jika gagal, kembali ke **OPEN**.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional & Paspor Kadaluarsa
Bayangkan sekelompok delegasi bisnis (Request HTTP paralel) melewati pos pemeriksaan imigrasi (Interceptor):
- Petugas imigrasi menemukan paspor kelompok tersebut telah kadaluarsa (401 Unauthorized).
- Jika setiap anggota delegasi lari sendiri-sendiri ke loket perpanjangan paspor, loket akan mengalami desak-desakan parah (*thundering herd*).
- Solusi interceptor: Delegasi A (request pertama) maju ke loket perpanjangan paspor. Delegasi B dan C diminta duduk di ruang tunggu VIP (Queue via `BehaviorSubject`).
- Begitu delegasi A kembali membawa buku paspor baru yang telah dicap, ia membagikan salinan visa baru kepada delegasi B dan C, lalu mereka semua melewati pos imigrasi tanpa kepanikan.

```
       [State: CLOSED]
        │            ▲
Failure │            │ Canary Request
Exceeded│            │ Success
        ▼            │
       [State: OPEN] ┘
        │
Duration│
Elapsed │
        ▼
     [State: HALF-OPEN]
```

---

### 7. Implementation: Simple & Practical Production Example

Berikut adalah implementasi sistem interceptor standar perbankan / enterprise:

#### 1. Definisi Konteks (Context Tokens)
File: `src/app/core/http/http-context.tokens.ts`

```typescript
import { HttpContextToken } from '@angular/common/http';

export interface RetryConfig {
  maxRetries: number;
  backoffMs: number;
  jitter: boolean;
}

export const BYPASS_AUTH = new HttpContextToken<boolean>(() => false);
export const RETRY_STRATEGY = new HttpContextToken<RetryConfig>(() => ({
  maxRetries: 3,
  backoffMs: 1000,
  jitter: true,
}));
export const ENABLE_CACHE = new HttpContextToken<boolean>(() => false);
```

#### 2. Circuit Breaker Service State Machine
File: `src/app/core/resilience/circuit-breaker.service.ts`

```typescript
import { Injectable } from '@angular/core';

export enum CircuitState {
  CLOSED,
  OPEN,
  HALF_OPEN,
}

@Injectable({
  providedIn: 'root',
})
export class CircuitBreakerService {
  private state: CircuitState = CircuitState.CLOSED;
  private failureCount = 0;
  private readonly failureThreshold = 5;
  private readonly resetTimeoutMs = 15000;
  private lastFailureTime = 0;

  public canExecute(): boolean {
    if (this.state === CircuitState.OPEN) {
      const now = Date.now();
      if (now - this.lastFailureTime > this.resetTimeoutMs) {
        this.state = CircuitState.HALF_OPEN;
        return true;
      }
      return false;
    }
    return true;
  }

  public recordSuccess(): void {
    this.failureCount = 0;
    this.state = CircuitState.CLOSED;
  }

  public recordFailure(): void {
    this.failureCount++;
    this.lastFailureTime = Date.now();
    if (this.failureCount >= this.failureThreshold || this.state === CircuitState.HALF_OPEN) {
      this.state = CircuitState.OPEN;
    }
  }

  public getState(): CircuitState {
    return this.state;
  }
}
```

#### 3. Token Refresh Mutex Interceptor (Anti-Race Condition)
File: `src/app/core/interceptors/auth.interceptor.ts`

```typescript
import { inject } from '@angular/core';
import {
  HttpInterceptorFn,
  HttpRequest,
  HttpHandlerFn,
  HttpErrorResponse,
  HttpEvent,
} from '@angular/common/http';
import { Observable, BehaviorSubject, throwError } from 'rxjs';
import { catchError, filter, switchMap, take } from 'rxjs/operators';
import { AuthService } from '../auth/auth.service';
import { BYPASS_AUTH } from '../http/http-context.tokens';

// State global lokal untuk sinkronisasi antrean token refresh
let isRefreshing = false;
const refreshTokenSubject = new BehaviorSubject<string | null>(null);

export const authInterceptor: HttpInterceptorFn = (
  req: HttpRequest<unknown>,
  next: HttpHandlerFn
): Observable<HttpEvent<unknown>> => {
  const authService = inject(AuthService);

  // Periksa apakah request dikonfigurasi untuk bypass otentikasi
  if (req.context.get(BYPASS_AUTH)) {
    return next(req);
  }

  const token = authService.getAccessToken();
  let authReq = req;

  if (token) {
    authReq = addTokenHeader(req, token);
  }

  return next(authReq).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && error.status === 401) {
        return handle401Error(authReq, next, authService);
      }
      return throwError(() => error);
    })
  );
};

function addTokenHeader(request: HttpRequest<unknown>, token: string): HttpRequest<unknown> {
  return request.clone({
    setHeaders: {
      Authorization: `Bearer ${token}`,
    },
  });
}

function handle401Error(
  request: HttpRequest<unknown>,
  next: HttpHandlerFn,
  authService: AuthService
): Observable<HttpEvent<unknown>> {
  if (!isRefreshing) {
    isRefreshing = true;
    refreshTokenSubject.next(null);

    return authService.refreshAccessToken().pipe(
      switchMap((newTokenResponse) => {
        isRefreshing = false;
        refreshTokenSubject.next(newTokenResponse.accessToken);
        return next(addTokenHeader(request, newTokenResponse.accessToken));
      }),
      catchError((refreshErr) => {
        isRefreshing = false;
        refreshTokenSubject.next(null);
        authService.terminateSession();
        return throwError(() => refreshErr);
      })
    );
  } else {
    // Request konkuren menunggu hingga refreshTokenSubject mengeluarkan token valid
    return refreshTokenSubject.pipe(
      filter((token): token is string => token !== null),
      take(1),
      switchMap((validToken) => {
        return next(addTokenHeader(request, validToken));
      })
    );
  }
}
```

#### 4. Resilient Retry Interceptor with Jitter
File: `src/app/core/interceptors/resilience.interceptor.ts`

```typescript
import { inject } from '@angular/core';
import {
  HttpInterceptorFn,
  HttpRequest,
  HttpHandlerFn,
  HttpEvent,
  HttpErrorResponse,
} from '@angular/common/http';
import { Observable, throwError, timer } from 'rxjs';
import { mergeMap, retry, tap } from 'rxjs/operators';
import { RETRY_STRATEGY } from '../http/http-context.tokens';
import { CircuitBreakerService, CircuitState } from '../resilience/circuit-breaker.service';

export const resilienceInterceptor: HttpInterceptorFn = (
  req: HttpRequest<unknown>,
  next: HttpHandlerFn
): Observable<HttpEvent<unknown>> => {
  const circuitBreaker = inject(CircuitBreakerService);
  const retryPolicy = req.context.get(RETRY_STRATEGY);

  if (!circuitBreaker.canExecute()) {
    return throwError(
      () =>
        new HttpErrorResponse({
          error: 'Circuit breaker is OPEN: Request ditolak untuk melindungi gateway.',
          status: 503,
          statusText: 'Service Unavailable (Fast-Fail)',
        })
    );
  }

  return next(req).pipe(
    tap({
      next: () => circuitBreaker.recordSuccess(),
      error: (err: unknown) => {
        if (err instanceof HttpErrorResponse && err.status >= 500) {
          circuitBreaker.recordFailure();
        }
      },
    }),
    retry({
      count: retryPolicy.maxRetries,
      delay: (error: unknown, retryCount: number) => {
        // Hanya lakukan retry pada Network Error atau 5xx status (bukan 4xx)
        if (error instanceof HttpErrorResponse && (error.status === 0 || error.status >= 500)) {
          let calculatedDelay = retryPolicy.backoffMs * Math.pow(2, retryCount - 1);
          if (retryPolicy.jitter) {
            // Full jitter implementation: delay random antara 0 sampai calculatedDelay
            calculatedDelay = Math.random() * calculatedDelay;
          }
          return timer(calculatedDelay);
        }
        return throwError(() => error);
      },
    })
  );
};
```

#### 5. Registrasi App Config
File: `src/app/app.config.ts`

```typescript
import { ApplicationConfig } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { resilienceInterceptor } from './core/interceptors/resilience.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideHttpClient(
      withInterceptors([
        authInterceptor,
        resilienceInterceptor,
      ])
    ),
  ],
};
```

---

### 8. Real World Case Study (Enterprise Fintech Portal)

#### Kasus: Degradasi Sistem Pembayaran Terdistribusi
Sebuah platform Core Banking memiliki Dashboard Settlement yang mengeksekusi 12 API GET secara serentak ketika teller/supervisor membuka halaman utama settlement.

#### Masalah Produksi
1. Setiap pagi pukul 08:00 saat masa sesi (1 jam) kedaluwarsa, 12 pemanggilan API tersebut gagal bersamaan dengan kode `401 Unauthorized`.
2. Interceptor naif memicu 12 request POST `/api/v1/auth/refresh` sekaligus.
3. Server otentikasi menerapkan *Refresh Token Rotation* dengan strategi *Single-Use Refresh Token*. Panggilan pertama berhasil mengonsumsi refresh token dan menerbitkan pasangan token baru.
4. Panggilan ke-2 hingga ke-12 tiba di server otentikasi dengan refresh token lama yang sudah hangus. Akibatnya, server mendeteksi aktivitas anomali (potensi replay attack) dan langsung memblokir akun teller secara permanen!

#### Solusi Arsitektur
1. **Mutex Serialization**: Menerapkan arsitektur `isRefreshing` lock flag dengan `BehaviorSubject` untuk memastikan tepat **satu** request mutasi refresh token yang lolos ke wire.
2. **Context Preservation**: Request yang tertunda dialirkan ulang menggunakan token baru yang didapat dari pipeline internal tanpa men-trigger siklus error baru.
3. **Hasil**: Beban endpoint otentikasi turun sebesar 91.6% pada jam puncak pergantian sesi, dan insiden *false-positive account lock* tereliminasi sepenuhnya (0 insiden).

---

### 9. Trade-offs: Analisis Komparatif

| Strategi | Keuntungan | Kerugian & Batasan | Mitigasi Dampak |
| :--- | :--- | :--- | :--- |
| **In-Memory Request Caching** | Mereduksi network footprint, zero UI latency untuk request berulang. | Risiko *stale data* tinggi, konsumsi RAM pada tab klien bertambah. | Gunakan TTL ketat (Time-To-Live < 30 detik) dan invalidasi cache pada aksi mutasi (POST/PUT/DELETE). |
| **Circuit Breaker di Klien** | Melindungi baterai perangkat mobile, mengurangi beban server yang sedang drop (*cascading failure* terputus). | User melihat pesan error lokal meskipun service mungkin sudah pulih sesaat kemudian (*lag recovery*). | Pasang status polling ringan atau integrasikan WebSocket push untuk auto-reset circuit breaker. |
| **Exponential Backoff dengan Jitter** | Mencegah lonjakan trafik periodik seragam (*thundering herds*) saat server pulih. | Durasi eksekusi request yang gagal memakan waktu total lebih lama sebelum melempar error final ke UI. | Terapkan hard timeout (cth: RxJS `timeout(10000)`) agar request tidak menggantung tanpa batas. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Mutasi Objek Request Secara Langsung (Direct Mutation)
*Kesalahan*:
```typescript
// ERROR: Headers bersifat immutable di Angular!
req.headers.set('Authorization', `Bearer ${token}`);
return next(req);
```
*Dampak*: Header tidak pernah terkirim ke backend karena `req.headers.set()` mengembalikan objek `HttpHeaders` baru tanpa mengubah instance request asli.
*Solusi*: Wajib memakai `req.clone({ setHeaders: { ... } })`.

#### 2. Infinite Loop pada Refresh Token yang Gagal
*Kesalahan*: Endpoint refresh token itu sendiri mengalami error 401 (misal refresh token sudah kedaluwarsa total), tetapi interceptor menangkap kembali error 401 tersebut dan mencoba refresh kembali secara rekursif tak berhingga.
*Solusi*: Gunakan `HttpContextToken` `BYPASS_AUTH` atau pastikan pengecekan URL secara eksplisit:
```typescript
if (req.url.includes('/auth/refresh') || req.context.get(BYPASS_AUTH)) {
  return next(req);
}
```

#### 3. Memory Leak Akibat RxJS Subject yang Tidak Pernah Selesai
*Kesalahan*: Menggunakan operator queueing tanpa `take(1)` saat mengambil nilai dari `refreshTokenSubject`.
```typescript
// MEMORY LEAK & EVENT MULTIPLIER:
return refreshTokenSubject.pipe(
  filter(token => token !== null),
  switchMap(token => next(addTokenHeader(request, token)))
);
```
*Dampak*: Stream Observable tidak pernah complete, menyebabkan closure menahan memori komponen selamanya.
*Solusi*: Wajib tambahkan operator `take(1)`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Functional Interceptor Migration**: Hindari pendaftaran berbasis modul `HTTP_INTERCEPTORS` lama; gunakan `provideHttpClient(withInterceptors([...]))`.
- [ ] **Urutan Interceptor (Execution Order)**: Susun urutan secara logis: (1) Logging & Correlation ID $\rightarrow$ (2) Authentication $\rightarrow$ (3) Circuit Breaker / Retry $\rightarrow$ (4) Deduplication / Cache.
- [ ] **Bypass Flags via Context**: Hindari parsing URL berbasis substring (misal `req.url.indexOf('/public') > -1`). Gunakan `HttpContextToken` untuk fleksibilitas modular.
- [ ] **Type Safety Response**: Jangan biarkan `HttpClient.get<any>()`. Wajib buatkan interface DTO untuk seluruh API contract.
- [ ] **HttpErrorResponse Serialization**: Ekstrak correlation ID dari header response (`X-Request-ID`) di level interceptor saat terjadi error untuk diteruskan ke service monitoring (misal Sentry/Datadog).

---

### 12. Hands-on Practice

Buat skenario interceptor lengkap di direktori proyek Anda: `hands-on/m02/`.

#### Langkah 1: Inisialisasi Mock Service & State
Buat file `hands-on/m02/auth.service.ts`:
```typescript
import { Injectable } from '@angular/core';
import { Observable, of, throwError, delay } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private token: string | null = 'EXPIRED_JWT_SECRET';
  public refreshCount = 0;

  getAccessToken(): string | null {
    return this.token;
  }

  refreshAccessToken(): Observable<{ accessToken: string }> {
    this.refreshCount++;
    if (this.refreshCount > 3) {
      return throwError(() => new Error('Session hard expired'));
    }
    const newToken = `VALID_JWT_TOKEN_${Date.now()}`;
    this.token = newToken;
    return of({ accessToken: newToken }).pipe(delay(800)); // Simulasi network delay
  }

  terminateSession(): void {
    this.token = null;
  }
}
```

#### Langkah 2: Buat Pipeline Test Harness
Buat file `hands-on/m02/network.spec.ts` untuk memverifikasi anti-race condition:
```typescript
import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { authInterceptor } from './auth.interceptor';
import { AuthService } from './auth.service';
import { forkJoin } from 'rxjs';

describe('Resilient Network Pipeline Integration', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;
  let authService: AuthService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        AuthService,
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });

    http = inject(HttpClient);
    httpMock = inject(HttpTestingController);
    authService = inject(AuthService);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('harus menyelesaikan 3 pemanggilan API paralel dengan hanya 1 kali refresh token', () => {
    let responses: unknown[] = [];

    // Trigger 3 request paralel
    forkJoin([
      http.get('/api/resource/1'),
      http.get('/api/resource/2'),
      http.get('/api/resource/3'),
    ]).subscribe((res) => {
      responses = res;
    });

    // Ketiga request awal gagal 401
    const req1 = httpMock.expectOne('/api/resource/1');
    const req2 = httpMock.expectOne('/api/resource/2');
    const req3 = httpMock.expectOne('/api/resource/3');

    req1.flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });
    req2.flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });
    req3.flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });

    // Tunggu refresh token internal (dikontrol oleh delay/fakeAsync di production test)
    // Verifikasi request di-replay dengan token baru
  });
});
```

---

### 13. Exercises

#### Level Easy
Buat `correlationIdInterceptor` yang bertugas memeriksa apakah header `X-Correlation-ID` sudah ada di request keluar. Jika belum, generate UUID v4 baru dan injeksikan ke header request.

#### Level Medium
Buat caching interceptor menggunakan `Map<string, { timestamp: number, response: HttpResponse<unknown> }>`. Interceptor hanya meng-cache request GET yang memiliki context `ENABLE_CACHE` aktif dan mengembalikan response dari cache jika umurnya kurang dari 60 detik.

#### Level Hard
Rancang interceptor anti-duplikasi (*request coalescing*) menggunakan RxJS. Jika ada 5 komponen yang meminta GET `/api/lookup-codes` dalam rentang waktu 100ms, interceptor hanya boleh menembakkan **satu** request network HTTP asli dan membagikan (*multicast*) respons yang sama ke kelima subscriber tanpa menggunakan persistent cache.

---

### 14. Challenge

#### Skenario: Arsitektur Multi-Tenant Gateway Fallback
Perusahaan perbankan Anda menggunakan sistem dua Gateway API:
1. `Primary Gateway`: `https://api.corebank.internal` (Prioritas utama)
2. `Secondary Disaster Gateway`: `https://api-backup.corebank.internal` (Digunakan hanya jika primary mengalami degradasi)

**Tugas Arsitektural**:
Rancang dan implementasikan sistem interceptor Angular yang:
- Mendeteksi secara mandiri kegagalan Primary Gateway (jika menghasilkan 3 kali error berturut-turut dengan status code `502/503/504` atau koneksi putus/Network Error `status === 0`).
- Secara otomatis dan transparan mengalihkan base URL dari request yang gagal tersebut, serta semua request downstream berikutnya, ke Secondary Gateway.
- Menjalankan health-check background ping secara periodik (setiap 30 detik) ke Primary Gateway tanpa mengganggu traffic pengguna.
- Mengembalikan rute request downstream ke Primary Gateway begitu health-check mengembalikan status `200 OK` sebanyak 2 kali berturut-turut.
- Semua logic routing ini harus transparan bagi komponen UI; UI Service hanya memanggil relative path seperti `this.http.get('/v1/transactions')`.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level
1. **Mengapa Angular memigrasikan arsitektur interceptor dari berbasis kelas (`HttpInterceptor`) ke fungsional (`HttpInterceptorFn`)?**
   - *Jawaban*: Untuk mendukung arsitektur Standalone secara penuh, memungkinkan tree-shaking yang jauh lebih efisien, mengurangi alokasi prototype class, dan memanfaatkan API functional Dependency Injection (`inject()`).

2. **Apa yang terjadi jika Anda memodifikasi properti `req.url` atau `req.headers` secara langsung tanpa memanggil `req.clone()`?**
   - *Jawaban*: TypeScript compiler akan melempar compile-error karena properti tersebut bertipe `readonly`. Di runtime, objek `HttpRequest` bersifat immutable untuk mencegah efek samping yang tidak terprediksi pada rantai interceptor concurrent.

3. **Kapan `HttpBackend` dieksekusi dalam rantai interceptor Angular?**
   - *Jawaban*: `HttpBackend` dieksekusi di akhir seluruh rantai interceptor. Ia bertindak sebagai interceptor pamungkas yang tidak memiliki handler `next` lagi, bertugas menerjemahkan `HttpRequest` menjadi panggilan XMLHttpRequest (XHR) atau Fetch API riil ke browser.

4. **Bagaimana cara mencegah `authInterceptor` agar tidak menyuntikkan token Authorization pada request pihak ketiga (misalnya request peta ke OpenStreetMap)?**
   - *Jawaban*: Menggunakan `HttpContextToken` (misal `BYPASS_AUTH`) yang diset bernilai `true` saat pemanggilan request HTTP dilakukan, atau memvalidasi domain dari target URL request.

5. **Apa fungsi utama dari operator `shareReplay(1)` dalam konteks pemanggilan HTTP pada service Angular?**
   - *Jawaban*: Mengubah Cold Observable menjadi Hot Observable dan men-cache emisi terakhir, sehingga subscriber berikutnya menerima data yang sama tanpa memicu request HTTP fisik baru ke server.

#### Intermediate Level
6. **Dalam implementasi Refresh Token Mutex, mengapa kita harus menggunakan `take(1)` di dalam pipeline `refreshTokenSubject.pipe(...)`?**
   - *Jawaban*: Tanpa `take(1)`, Observable dari `BehaviorSubject` tidak akan pernah complete. Hal ini mengakibatkan memory leak dan menyebabkan request berikutnya dieksekusi ulang berkali-kali setiap kali nilai refresh token baru dipancarkan di masa depan.

7. **Mengapa penambahan Jitter (variasi acak) sangat krusial pada algoritma Exponential Backoff di sisi frontend?**
   - *Jawaban*: Jika ribuan klien gagal terhubung di waktu yang sama, exponential backoff murni tanpa jitter akan membuat ribuan klien tersebut melakukan retry pada detik yang sama secara berbarengan, menimbulkan lonjakan traffic periodik (*thundering herd problem*) yang kembali merobohkan server.

8. **Apa perbedaan mendasar antara `HttpContext` dan `HttpHeaders` dalam objek `HttpRequest`?**
   - *Jawaban*: `HttpHeaders` dikirimkan secara fisik melalui jaringan ke web server sesuai protokol HTTP, sedangkan `HttpContext` murni hidup dalam memori Angular di browser untuk berbagi status dan konfigurasi antar-interceptor tanpa diekspos ke jaringan.

9. **Jika urutan penyusunan interceptor adalah `withInterceptors([A, B, C])`, bagaimana urutan penanganan error pada blok `catchError` di masing-masing interceptor?**
   - *Jawaban*: Urutan request outbound berjalan searah: `A -> B -> C -> Backend`. Namun urutan respons inbound dan penanganan error (`catchError`) berjalan terbalik: `Backend -> C -> B -> A`.

10. **Apa bahaya terbesar jika circuit breaker diimplementasikan pada scope `Component` (bukan root service)?**
    - *Jawaban*: Status circuit breaker (kegagalan dan transisi OPEN/CLOSED) akan terisolasi hanya untuk instance komponen tersebut dan langsung ter-reset ketika komponen di-destroy, menghilangkan fungsi proteksi sistemik aplikasi secara global.

#### Kasus Arsitektural Produksi
11. **Skenario 1**: Aplikasi perbankan Anda menerima ratusan error 401 saat sesi kedaluwarsa. Anda mendapati bahwa fungsi refresh token Anda dipanggil 5 kali alih-alih 1 kali, meskipun Anda sudah memakai flag boolean `isRefreshing = false`. Mengapa ini bisa terjadi?
    - *Solusi & Analisis*: Hal ini terjadi karena sifat asynchronous dari stream JS. Antara request pertama memicu error 401 dan flag `isRefreshing` diset ke `true`, beberapa microtask/macrotask request lain telah melewati pengecekan `if (!isRefreshing)` jika flag tersebut tidak diubah secara atomik/sinkron seketika sebelum pemanggilan async terjadi, atau terdapat lebih dari satu instance interceptor akibat kesalahan konfigurasi injection token di tingkat child injector.

12. **Skenario 2**: Sistem Anda menerapkan Circuit Breaker. Saat backend mati total, user me-refresh halaman (F5) browser. Circuit breaker langsung kembali ke state CLOSED dan menembakkan request lagi ke backend yang mati. Bagaimana mengatasinya?
    - *Solusi & Analisis*: State dari Circuit Breaker secara default hanya berada di in-memory Angular runtime. Agar resisten terhadap reload halaman (F5), status breaker (`state`, `failureCount`, `lastFailureTime`) harus dipersistensikan ke `sessionStorage` atau `IndexedDB`, dan dihidupkan kembali (*rehydrated*) saat aplikasi diinisialisasi.

13. **Skenario 3**: Sebuah request unggah file besar (200MB) dibatalkan secara sepihak oleh interceptor timeout karena melampaui batas waktu 10 detik. Bagaimana arsitektur interceptor yang elegan menangani kebutuhan timeout yang dinamis?
    - *Solusi & Analisis*: Buat `HttpContextToken<number>` misal `REQUEST_TIMEOUT`. Request upload file menyetel context tersebut ke nilai lebih tinggi (misal `300000` ms) atau `0` (tanpa timeout). Interceptor membaca context tersebut; jika ditemukan nilai khusus, terapkan operator RxJS `timeout(customValue)` sesuai parameter tersebut secara dinamis.

---

### 16. Summary

- **Functional Architecture**: `HttpInterceptorFn` menggantikan interceptor berbasis kelas tradisional, menghadirkan dependensi yang terisolasi, komposisi yang lebih mudah, dan performa tree-shaking yang superior.
- **Resilience Engineering**: Sistem perbankan dan enterprise modern menuntut ketahanan jaringan di sisi klien yang mencakup **Token Refresh Mutex**, **Client-Side Circuit Breaker**, serta **Exponential Backoff dengan Jitter**.
- **Immutable Context Pattern**: Komunikasi instruksi internal antar interceptor harus menggunakan `HttpContext` dan `HttpContextToken`, bukan memanipulasi header HTTP jaringan secara sembarangan.
- **Concurreny Control**: Memanfaatkan primitif RxJS (`BehaviorSubject`, `filter`, `take(1)`, `switchMap`) sangat penting untuk memastikan tidak terjadi kondisi balapan (*race condition*) saat sinkronisasi state otentikasi global.