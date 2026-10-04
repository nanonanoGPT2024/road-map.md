# Kurikulum Enterprise Angular: Bab 06 - Form Enterprise & Validasi Reaktif Lanjutan
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Engineer / Senior Angular Developer diharapkan mampu:

1. **Mendekonstruksi & Merekayasa Arsitektur Form Lanjutan:** Menguasai siklus hidup internal `AbstractControl`, `FormControl`, `FormGroup`, dan `FormArray` pada level engine Change Detection dan microtask queue.
2. **Membangun Komponen Form Kustom Skala Enterprise:** Mengimplementasikan interface `ControlValueAccessor` (CVA) tingkat lanjut untuk komponen UI kustom yang kompleks (composite form controls) dengan integrasi two-way model-to-view synchronization tanpa memory leak.
3. **Merancang Mesin Validasi Reaktif Terdistribusi:** Mengembangkan synchronous dan asynchronous cross-field validators yang tahan terhadap race conditions, memanfaatkan caching (memoization), dynamic validator switching, serta integrasi debouncing stream RxJS.
4. **Mengoptimalkan Kinerja Form Skala Masif:** Mengatasi degradasi performa pada form dinamis ratusan kontrol menggunakan `FormRecord`, dynamic tree virtualization, dan isolasi `ChangeDetectionStrategy.OnPush`.
5. **Mengimplementasikan Schema-Driven Dynamic Forms:** Membangun metadata engine deklaratif yang mengubah dynamic schema (JSON/Metadata API) menjadi strongly typed reactive forms dengan dirty-checking dan auto-save differential patching.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
*   **Angular Core:** Dependency Injection token (`InjectionToken`, `forwardRef`, multi-providers), Signals & Change Detection (`ChangeDetectorRef`, `OnPush`), Standalone Components lifecycle.
*   **RxJS Deep Dive:** Higher-order mapping operators (`switchMap`, `concatMap`, `exhaustMap`), multi-casting (`shareReplay`), lifecycle control (`takeUntilDestroyed`), serta profiling event loop.
*   **TypeScript Advanced Typing:** Generics, Mapped Types, Conditional Types, Type Narrowing, dan inferensi Typed Forms (`FormGroup<{ [K in keyof T]: FormControl<T[K]> }>`).
*   **Reactive Forms Fundamentals:** Penggunaan dasar `FormBuilder`, integrasi `formControlName`, dan validasi sinkron standar.

---

### 3. Concept & Internal Architecture

#### 3.1 Resolusi Internal Node Graph `AbstractControl`

Di dalam Angular Reactive Forms engine, setiap kontrol bukanlah representasi langsung dari DOM element, melainkan sebuah simpul (node) dalam graph pohon berarah (*directed tree*) berbasis kelas dasar abstrak `AbstractControl`.

```
                    ┌─────────────────────────┐
                    │       FormGroup         │ (Root Control)
                    │  status: VALID/PENDING  │
                    └────────────┬────────────┘
                                 │
            ┌────────────────────┴────────────────────┐
            ▼                                         ▼
┌─────────────────────────┐               ┌─────────────────────────┐
│       FormArray         │               │       FormControl       │
│  (Indexed dynamic list) │               │   (Atomic value node)   │
└───────────┬─────────────┘               └─────────────────────────┘
            │
    ┌───────┴───────┐
    ▼               ▼
┌───────┐       ┌───────┐
│Control│       │Control│
└───────┘       └───────┘
```

Ketika nilai sebuah node atomik (`FormControl`) berubah:
1. Engine memanggil `setValue` atau mengonsumsi input dari `ControlValueAccessor`.
2. Pipeline validator sinkron dieksekusi secara lokal pada node tersebut.
3. Node memancarkan perubahan melalui event stream `valueChanges` dan `statusChanges` (RxJS `Subject`).
4. Engine menaikkan (*bubbles up*) event ke simpul induknya (`FormGroup`/`FormArray`) secara rekursif via `updateValueAndValidity()`.
5. Pada setiap level pohon, agregator status mengevaluasi apakah grup berstatus `VALID`, `INVALID`, `PENDING`, atau `DISABLED`.
6. Jika validator asinkron terdaftar, node beralih ke state `PENDING`, menunda kepastian status validitas grup induk sampai seluruh Promise atau Observable terselesaikan.

#### 3.2 Anatomi Jembatan: `ControlValueAccessor` (CVA)

`ControlValueAccessor` bertindak sebagai jembatan *bi-directional adapter* antara Angular Reactive Form API dan DOM Element / Komponen Presentasional Kustom.

```
       Angular Forms API                              Custom DOM / Widget UI
┌──────────────────────────────┐              ┌─────────────────────────────────────┐
│                              │  writeValue  │                                     │
│  FormControl.setValue(val)   ├─────────────►│  Element rendering / Internal state │
│                              │              │                                     │
│  FormControl.statusChanges   │              │  View visual states (error, blur)   │
│                              │              │                                     │
│  onChange(nextValue) callback│◄─────────────┤  User Interaction (click, keypress) │
│                              │ registerOn.. │                                     │
│  onTouched() callback        │◄─────────────┤  Focus loss (blur event)            │
└──────────────────────────────┘              └─────────────────────────────────────┘
```

Secara internal, dependensi ini dihubungkan via multi-provider token:
```typescript
{
  provide: NG_VALUE_ACCESSOR,
  useExisting: forwardRef(() => CustomControlComponent),
  multi: true
}
```

Metode internal CVA yang wajib dipenuhi:
*   `writeValue(obj: any): void`: Dipanggil oleh engine Angular Forms untuk meneruskan nilai dari model ke view. Eksekusi ini tidak boleh memicu callback `onChange`.
*   `registerOnChange(fn: any): void`: Menyimpan referensi fungsi callback Angular. Dipanggil ketika view berinteraksi dan menghasilkan nilai baru yang harus diinjeksikan kembali ke form model.
*   `registerOnTouched(fn: any): void`: Menyimpan referensi callback untuk menandai kontrol telah berstatus `touched` (umumnya saat event `blur`).
*   `setDisabledState?(isDisabled: boolean): void`: Dipanggil engine untuk merefleksikan status disable/enable dari kontrol ke DOM host element.

#### 3.3 Engine Validasi Asinkron & Race Condition Hazard

Validasi asinkron di Angular mengeksekusi fungsi bertipe `AsyncValidatorFn`:
```typescript
type AsyncValidatorFn = (control: AbstractControl) => 
  Promise<ValidationErrors | null> | Observable<ValidationErrors | null>;
```

Tantangan arsitektur enterprise muncul ketika validasi asinkron memicu HTTP request (misal: verifikasi nomor NPWP/Tax ID ke microservice). Jika user mengetik cepat:
* Request $N_1$ dikirim ke server.
* Request $N_2$ dikirim sebelum $N_1$ selesai.
* Jika network latensi $N_1$ lebih lambat dari $N_2$, respons $N_1$ dapat tiba terakhir dan menimpa validasi state $N_2$.
* Arsitektur validasi harus menggunakan operator pembatalan stream (`switchMap`) dan mekanika caching/memoization untuk mengisolasi request kadaluwarsa (*out-of-order responses*).

---

### 4. Why & What

| Dimensi | Pendekatan Enterprise Modern | Pendekatan Naif / Standard | Dampak Arsitektur |
| :--- | :--- | :--- | :--- |
| **Integrasi Komponen** | `ControlValueAccessor` terisolasi dengan state immutability. | Menggunakan `@Input` & `@Output` manual untuk setiap state form. | Mengeliminasi boilerplate passing props; kontrol kustom otomatis mewarisi pipeline validasi global. |
| **Type Safety** | Strictly Typed Forms (`FormGroup<T>`, `FormRecord`). | Untyped `FormGroup` (`any`). | Deteksi kesalahan compile-time saat mapping skema data; refactoring aman tanpa runtime breakages. |
| **Skalabilitas Performa** | Unbound execution via dynamic controls decoupling, manual event suppression (`emitEvent: false`). | Native recalculation pada setiap keystroke di seluruh pohon form. | Mencegah bottleneck rendering ratusan elemen UI; CPU cycle tetap stabil di bawah frame budget 16ms. |
| **Asynchronous Engine** | Stream debouncing, memoized cache, switch-cancellation. | Panggilan direct async validator pada raw `valueChanges`. | Mengurangi beban trafik gateway hingga 90%; mencegah race condition status validasi. |

---

### 5. How (Workflow Detail)

Alur internal siklus data pada implementasi Form Enterprise:

```
[User Mengubah Input pada Custom Component]
                   │
                   ▼
       DOM Event Trigger (e.g. input/blur)
                   │
                   ▼
       CVA: memanggil this.onChange(parsedValue)
            memanggil this.onTouched()
                   │
                   ▼
     FormControl Engine menerima Value
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
Eksekusi Sync          Eksekusi Async
Validator Array        Validator Array
       │                       │
       ▼                       ▼
Ada error?             Set status = 'PENDING'
- YA: set INVALID      Pipe RxJS Stream:
- TDK: lanjut           debounceTime -> distinctUntilChanged -> switchMap
                               │
                               ▼
                       API Validasi Eksternal
                               │
                               ▼
                       Hasil Async Tiba
                               │
                               ▼
                       Kombinasi Sync & Async
                               │
                               ▼
               Tentukan Status Final (VALID / INVALID)
                               │
                               ▼
               Bubble Up ke Parent (FormGroup / Tree)
                               │
                               ▼
          Update UI State (Classes, Errors, OnPush View)
```

1. **User Action:** User mengetik karakter pada antarmuka kustom (misal: Dynamic Currency Input).
2. **Sanitization & Normalization:** Nilai mentah ("Rp 1.000.000") diformat menjadi representasi murni data model (`1000000`).
3. **CVA Propagation:** Callback `onChange` yang didaftarkan engine dipanggil dengan data yang telah dibersihkan.
4. **Synchronous Validation Phase:** Seluruh array validator sinkron dieksekusi secara instan. Jika ada rule gagal, form langsung berstatus `INVALID` dan async validation tidak perlu diproses lebih jauh.
5. **Asynchronous Validation Phase:** Jika sync validator lolos, kontrol masuk ke status `PENDING`. Engine memicu stream validasi asinkron yang telah dibungkus mekanisme `debounceTime` dan `switchMap`.
6. **State Aggregation:** Hasil akhir (berupa `ValidationErrors` atau `null`) digabungkan. Pohon form mengevaluasi ulang status keseluruhan secara atomik.
7. **Change Propagation Suppression:** Jika perubahan dilakukan secara terprogram (misal via auto-fill/patching internal), eksekusi memanfaatkan flag `{ emitEvent: false }` untuk mencegah siklus propagasi berulang (*infinite loops*).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Verifikasi Paspor Bandara Otomatis
Bayangkan sebuah gerbang imigrasi bandara modern (*Form Validation System*):
* **Custom Input Control (CVA):** Mesin pemindai paspor fisik. Mesin mengonversi bentuk fisik paspor (kertas, hologram) ke data digital terstruktur (JSON).
* **Sync Validators (Pemeriksaan Lokal):** Pemeriksaan langsung di mesin: Apakah masa berlaku habis? Apakah format halaman sesuai? (Hasilnya instan, tidak butuh internet).
* **Async Validators (Pemeriksaan Interpol/Database Imigrasi Pusat):** Komputer mengirim data paspor ke server pusat Interpol. Butuh jeda waktu (*latency*). Mesin berstatus lampu kuning (*PENDING*). Jika penumpang membatalkan dan menempelkan paspor lain, pencarian sebelumnya dibatalkan (*cancellation via switchMap*).
* **FormGroup:** Gerbang akhir. Penumpang hanya boleh masuk jika paspor valid, tiket valid, dan deklarasi bea cukai valid (Agregasi multi-kontrol).

#### Diagram Interaksi Objek Internal

```
+---------------------------------------------------------------------------------------+
|                                    ANGULAR CORE                                       |
|                                                                                       |
|   +------------------------------------+             +----------------------------+   |
|   |            FormControl             |             |        AsyncEngine         |   |
|   |                                    |             |                            |   |
|   | value: 15000000                    |             | status$: 'PENDING'         |   |
|   | status: VALID                      |             | debounce: 300ms            |   |
|   +-----------------+------------------+             | switchMap -> Microservice  |   |
|                     │                                +-------------+--------------+   |
|         writeValue()│ ▲ onChange()                                 ▲                  |
|                     │ │                                            │                  |
|   +-----------------▼─┴────────────────────────────────────────────┴──────────────+   |
|   |                    ControlValueAccessor (Bridge Layer)                        |   |
|   |                                                                               |   |
|   |  - Formats internal values for display (e.g., adds "IDR " currency symbol)    |   |
|   |  - Strips formatting before propagating back to FormControl model             |   |
|   |  - Intercepts onTouched() to flag UI blur state                               |   |
|   +---------------------------------+---------------------------------------------+   |
|                                     │                                                 |
|                       DOM Events    │  Render Pass                                    |
|                                     ▼                                                 |
|   +-------------------------------------------------------------------------------+   |
|   |                        CUSTOM UI VIEW (Component Template)                    |   |
|   |                                                                               |   |
|   |   <input class="input-control" [value]="displayValue" (input)="onInput($event)"/> |
|   +-------------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Tri-State Boolean Selector via CVA
Implementasi kontrol input kustom 3-kondisi (`true`, `false`, `null`) yang mengimplementasikan interface `ControlValueAccessor`.

```typescript
// tri-state-toggle.component.ts
import { Component, forwardRef, ChangeDetectionStrategy } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { CommonModule } from '@angular/common';

type TriState = boolean | null;

@Component({
  selector: 'app-tri-state-toggle',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="toggle-container" [class.disabled]="disabled">
      <button type="button" (click)="setVal(true)" [class.active]="value === true">YES</button>
      <button type="button" (click)="setVal(false)" [class.active]="value === false">NO</button>
      <button type="button" (click)="setVal(null)" [class.active]="value === null">N/A</button>
    </div>
  `,
  styles: [`
    .toggle-container { display: inline-flex; border: 1px solid #ccc; border-radius: 4px; }
    button { padding: 8px 16px; border: none; background: transparent; cursor: pointer; }
    button.active { background: #0284c7; color: white; }
    .disabled { opacity: 0.5; pointer-events: none; }
  `],
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => TriStateToggleComponent),
      multi: true
    }
  ],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class TriStateToggleComponent implements ControlValueAccessor {
  value: TriState = null;
  disabled = false;

  private onChange: (val: TriState) => void = () => {};
  private onTouched: () => void = () => {};

  writeValue(val: TriState): void {
    this.value = val;
  }

  registerOnChange(fn: (val: TriState) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled = isDisabled;
  }

  setVal(val: TriState): void {
    if (this.disabled) return;
    this.value = val;
    this.onChange(this.value);
    this.onTouched();
  }
}
```

#### 7.2 Practical Example: Enterprise Currency Input dengan Memoized Async Cross-Field Validator

Implementasi *Enterprise Masked Currency Input* terintegrasi dengan CVA, validasi cross-field dinamis, dan async business rule verification menggunakan Reactive Forms strictly typed.

##### Komponen CVA: Currency Masked Input
```typescript
// currency-input.component.ts
import { Component, forwardRef, ElementRef, ViewChild, ChangeDetectionStrategy } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-currency-input',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="input-wrapper" [class.is-disabled]="disabled">
      <span class="currency-prefix">IDR</span>
      <input
        #inputRef
        type="text"
        [disabled]="disabled"
        (input)="onInputChange($event)"
        (blur)="onBlur()"
        class="native-input"
        placeholder="0"
      />
    </div>
  `,
  styles: [`
    .input-wrapper { display: flex; align-items: center; border: 1px solid #94a3b8; border-radius: 6px; padding: 0 12px; }
    .currency-prefix { font-weight: 600; color: #64748b; margin-right: 8px; }
    .native-input { width: 100%; border: none; padding: 10px 0; outline: none; text-align: right; }
    .is-disabled { background-color: #f1f5f9; cursor: not-allowed; }
  `],
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => CurrencyInputComponent),
      multi: true
    }
  ],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class CurrencyInputComponent implements ControlValueAccessor {
  @ViewChild('inputRef', { static: true }) inputRef!: ElementRef<HTMLInputElement>;
  
  disabled = false;
  private onChange: (val: number | null) => void = () => {};
  private onTouched: () => void = () => {};

  writeValue(value: number | null): void {
    const rawVal = value !== null && value !== undefined ? value : '';
    this.inputRef.nativeElement.value = this.formatDisplay(rawVal.toString());
  }

  registerOnChange(fn: (val: number | null) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled = isDisabled;
  }

  onInputChange(event: Event): void {
    const target = event.target as HTMLInputElement;
    const cleanNumbers = target.value.replace(/\D/g, '');
    
    if (!cleanNumbers) {
      target.value = '';
      this.onChange(null);
      return;
    }

    const numericValue = parseInt(cleanNumbers, 10);
    target.value = this.formatDisplay(cleanNumbers);
    this.onChange(numericValue);
  }

  onBlur(): void {
    this.onTouched();
  }

  private formatDisplay(numericStr: string): string {
    if (!numericStr) return '';
    return new Intl.NumberFormat('id-ID').format(Number(numericStr));
  }
}
```

##### Async Validator Factory dengan Caching & SwitchMap

```typescript
// fiscal-validators.ts
import { AbstractControl, AsyncValidatorFn, ValidationErrors } from '@angular/forms';
import { Observable, of, timer } from 'rxjs';
import { map, switchMap, catchError, shareReplay } from 'rxjs/operators';
import { HttpClient } from '@angular/common/http';

export class FiscalValidators {
  private static cache = new Map<string, boolean>();

  static createTaxComplianceValidator(http: HttpClient, delayMs = 400): AsyncValidatorFn {
    return (control: AbstractControl): Observable<ValidationErrors | null> => {
      const taxId = control.value;

      if (!taxId || taxId.length < 10) {
        return of(null);
      }

      // Check In-Memory Cache to prevent duplicated network flights
      if (FiscalValidators.cache.has(taxId)) {
        const isValid = FiscalValidators.cache.get(taxId);
        return of(isValid ? null : { taxComplianceFailed: { reason: 'Blacklisted or invalid entity ID' } });
      }

      return timer(delayMs).pipe(
        switchMap(() => 
          http.get<{ isCompliant: boolean }>(`/api/v1/compliance/verify?taxId=${taxId}`).pipe(
            map(response => {
              FiscalValidators.cache.set(taxId, response.isCompliant);
              return response.isCompliant ? null : { taxComplianceFailed: { reason: 'Blacklisted entity' } };
            }),
            catchError(() => of({ taxComplianceFailed: { reason: 'Network or validation server failure' } }))
          )
        )
      );
    };
  }
}
```

##### Implementasi Typed Enterprise Container Form

```typescript
// corporate-loan-form.component.ts
import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { 
  FormBuilder, 
  FormGroup, 
  FormControl, 
  Validators, 
  ReactiveFormsModule 
} from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { CurrencyInputComponent } from './currency-input.component';
import { FiscalValidators } from './fiscal-validators';

export interface LoanApplicationForm {
  applicantName: FormControl<string>;
  taxRegistrationNumber: FormControl<string>;
  loanAmount: FormControl<number | null>;
  collateralValue: FormControl<number | null>;
}

@Component({
  selector: 'app-corporate-loan-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, CurrencyInputComponent],
  template: `
    <form [formGroup]="form" (ngSubmit)="submitApplication()" class="p-6 max-w-xl mx-auto space-y-4">
      <div>
        <label>Corporate Name</label>
        <input type="text" formControlName="applicantName" class="w-full border p-2 rounded" />
      </div>

      <div>
        <label>Tax Registration Number (NPWP)</label>
        <input type="text" formControlName="taxRegistrationNumber" class="w-full border p-2 rounded" />
        <div *ngIf="form.controls.taxRegistrationNumber.pending" class="text-blue-500">
          Memvalidasi status kepatuhan perpajakan...
        </div>
        <div *ngIf="form.controls.taxRegistrationNumber.errors?.['taxComplianceFailed']" class="text-red-500">
          {{ form.controls.taxRegistrationNumber.errors?.['taxComplianceFailed'].reason }}
        </div>
      </div>

      <div>
        <label>Requested Loan Amount</label>
        <app-currency-input formControlName="loanAmount"></app-currency-input>
      </div>

      <div>
        <label>Collateral Asset Valuation</label>
        <app-currency-input formControlName="collateralValue"></app-currency-input>
      </div>

      <div *ngIf="form.errors?.['insufficientCollateral']" class="p-3 bg-red-100 text-red-700 rounded">
        Nilai agunan minimal harus bernilai 120% dari total pengajuan pinjaman.
      </div>

      <button 
        type="submit" 
        [disabled]="form.invalid || form.pending"
        class="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
      >
        Submit Underwriting
      </button>
    </form>
  `
})
export class CorporateLoanFormComponent implements OnInit {
  private fb = inject(FormBuilder);
  private http = inject(HttpClient);

  form!: FormGroup<LoanApplicationForm>;

  ngOnInit(): void {
    this.form = this.fb.group<LoanApplicationForm>({
      applicantName: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
      taxRegistrationNumber: new FormControl('', {
        nonNullable: true,
        validators: [Validators.required, Validators.pattern(/^[0-9]{15,16}$/)],
        asyncValidators: [FiscalValidators.createTaxComplianceValidator(this.http)]
      }),
      loanAmount: new FormControl<number | null>(null, [Validators.required, Validators.min(10_000_000)]),
      collateralValue: new FormControl<number | null>(null, [Validators.required])
    }, {
      validators: [this.crossFieldCollateralRule]
    });
  }

  // Cross-Field Validator
  private crossFieldCollateralRule(control: AbstractControl): ValidationErrors | null {
    const loan = control.get('loanAmount')?.value;
    const collateral = control.get('collateralValue')?.value;

    if (!loan || !collateral) {
      return null;
    }

    const minRequiredCollateral = loan * 1.20;
    return collateral < minRequiredCollateral ? { insufficientCollateral: true } : null;
  }

  submitApplication(): void {
    if (this.form.valid) {
      console.log('Valid Application Submitted: ', this.form.getRawValue());
    }
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Dynamic Policy Underwriting Engine (Multi-Tenant FinTech Core)

* **Skala Masalah:** Sebuah sistem asuransi korporat global memproses polis yang memuat hingga 800 parameter penilaian risiko. Form dibangun secara dinamis berdasarkan respons API Schema (JSON Schema standard) yang bervariasi bergantung pada industri klien (Maritim, Pertambangan, Aviasi).
* **Kendala Arsitektur Form:**
  1. *Change Detection Overhead:* Setiap input keystroke memicu siklus change detection pada 800 kontrol, mengakibatkan dropping frame hingga 12 FPS pada mesin client perbankan.
  2. *Cascade Validation Death Spiral:* Perubahan pada kontrol "Risk Industry Code" menuntut penambahan/penghapusan puluhan field turunan dengan aturan validasi berbeda secara real-time via `addControl` / `removeControl`, menyebabkan multiple redundant validations.
  3. *Unsynchronized State:* Draft formulir harus di-autosave setiap 10 detik hanya jika model mengalami mutasi (`dirty`) dengan differential patch payload (bukan keseluruhan payload 800 field).

#### Solusi Arsitektur

```
[Schema Ingestion Layer] -> Ingest Dynamic Meta-Schema (JSON)
           │
           ▼
[Dynamic Form Factory Engine] -> Build Optimized FormRecord / FormGroup Graph
           │
           ▼
[Decoupled Control Nodes] -> ChangeDetectionStrategy.OnPush + Virtualized Form Sections
           │
           ▼
[Selective Pipeline Dispatcher] -> RxJS Buffer & Diff Engine -> Minimal HTTP Patch Payload
```

1. **FormRecord & Type Decoupling:** Penggunaan `FormRecord` daripada `FormGroup` standar untuk kontrol dinamis dengan key yang tidak diketahui pada saat compile time, meminimalkan memory footprint.
2. **Suppression of Propagation Waves:** Ketika menyusun kembali validator dinamis pada ratusan kontrol secara bersamaan:
   ```typescript
   control.clearValidators();
   control.setValidators(newValidators);
   // Penundaan eksekusi validasi hingga seluruh kontrol selesai dikonfigurasi
   control.updateValueAndValidity({ emitEvent: false });
   ```
   Pemanggilan `this.form.updateValueAndValidity()` dilakukan satu kali secara global di level root pada akhir batch update.
3. **Differential Autosave RxJS Engine:**
   ```typescript
   this.form.valueChanges.pipe(
     filter(() => this.form.dirty && this.form.valid),
     debounceTime(10000),
     pairwise(),
     map(([prev, curr]) => this.calculateDifferentialPatch(prev, curr)),
     filter(diff => Object.keys(diff).length > 0),
     switchMap(patch => this.underwritingService.persistDraft(patch)),
     takeUntilDestroyed(this.destroyRef)
   ).subscribe(() => this.form.markAsPristine());
   ```

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Biaya / Kerugian Arsitektur | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **ControlValueAccessor (CVA)** | Enkapsulasi desain kontrol kustom murni; integrasi native dengan ekosistem validasi Angular. | *High Boilerplate*. Membutuhkan pemahaman siklus multi-provider (`NG_VALUE_ACCESSOR`) & manual handling disable/blur state. | Komponen UI terstandardisasi pada enterprise design system (Design System Library). |
| **Cross-field Validation at FormGroup Level** | Akses komprehensif ke semua sibling kontrol; atomic error state pada root level. | Memicu kalkulasi ulang validator grup setiap kali salah satu kontrol di dalam grup berubah nilainya. | Validasi komparasi relasional (misal: Date Range `startDate` < `endDate`, Password Confirm). |
| **Dynamic Form via Meta-Schema Ingestion** | Konfigurasi form diatur melalui server tanpa perlu deploy ulang bundle JS frontend. | Hilangnya compile-time safety dari TypeScript; kompleksitas debugging error rendering sangat tinggi. | Sistem form berbasis workflow dinamis, CMS formulir, mesin underwriting multi-step. |
| **Strictly Typed Forms (v14+)** | Menghindari `undefined` runtime error; inferensi tipe otomatis pada `getRawValue()`. | Kesulitan saat menangani mutasi struktur form yang sangat dinamis (menuntut `FormRecord` atau complex Generics). | Semua proyek enterprise Angular modern tanpa pengecualian. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Circular Loops via `valueChanges` Listener
* **Anti-pattern:** Mengubah nilai form di dalam subscription `valueChanges` kontrol yang sama tanpa mematikan event emission.
  ```typescript
  // BAD: Infinite Loop
  this.form.get('code')?.valueChanges.subscribe(val => {
    this.form.get('code')?.setValue(val.toUpperCase()); 
  });
  ```
* **Solusi Enterprise:** Gunakan option `{ emitEvent: false }` atau tangani via reactive mapping CVA.
  ```typescript
  // CORRECT:
  this.form.get('code')?.valueChanges.subscribe(val => {
    if (val) {
      this.form.get('code')?.setValue(val.toUpperCase(), { emitEvent: false });
    }
  });
  ```

#### 2. Subscriptions Bocor (Memory Leak) pada Async Validators
* **Anti-pattern:** Menginstansiasi Observable internal dalam Async Validator tanpa completion boundary.
* **Solusi Enterprise:** Pastikan stream async validator selalu mengembalikan Observable yang *complete* menggunakan operator seperti `first()` atau `take(1)`. Angular Form Engine mengharapkan stream validator mengirimkan status dan langsung *completed*.
  ```typescript
  // Async Validator Engine expects a completed stream:
  return this.api.check(control.value).pipe(
    take(1),
    map(res => res.exists ? { duplicate: true } : null)
  );
  ```

#### 3. Kehilangan Data Kontrol Disabel via `form.value`
* **Anti-pattern:** Menggunakan `form.value` untuk mengirimkan payload ke backend. Kontrol yang di-*disable* (misal: read-only fields yang dihitung otomatis) akan diabaikan (`undefined`) oleh engine.
* **Solusi Enterprise:** Gunakan `form.getRawValue()` untuk memastikan serialisasi seluruh struktur model form secara utuh tanpa terpengaruh status interaktivitas field.

---

### 11. Best Practices (Production Checklist)

1. **Selalu Gunakan `ChangeDetectionStrategy.OnPush`:** Integrasikan dengan `ChangeDetectorRef` di dalam CVA untuk memaksa paint cycle saat `writeValue` dipanggil dari luar zone engine.
2. **Pisahkan Parser dan Formatter di CVA:** View layer harus menampilkan data terformat (e.g., "$1,200.00"), sedangkan `FormControl` model selalu menyimpan tipe data primitif murni (`1200.00`).
3. **Immutability pada Model Mutasi:** Hindari mutasi objek referensi internal FormArray/FormGroup secara langsung; gunakan method bawaan Angular (`patchValue`, `push`, `removeAt`).
4. **Debounce Semua Async Validators:** Pasang `timer()` atau `debounceTime()` minimal 300ms untuk semua validasi jaringan.
5. **Gunakan `FormRecord` untuk Dynamic Key-Value Pairs:** Hindari pemaksaan type assertion `(form as any)` saat menyusun dynamic fields.
6. **Pastikan Multi-Provider Bersifat Standalone Friendly:** Definisikan provider `NG_VALUE_ACCESSOR` secara eksplisit pada array `@Component({ providers: [...] })`.
7. **Handle `setDisabledState` dengan Sempurna:** Pastikan event handler internal di-disable dan style visual CSS diubah saat CVA menerima instruksi disable dari model parent.
8. **Sanitasi Nilai Input:** Bersihkan data dari karakter berbahaya (XSS injection strings) sebelum ditransmisikan ke tree `FormControl`.
9. **Gunakan `takeUntilDestroyed`:** Sambungkan semua internal subscription form lifecycle dengan `DestroyRef` konteks terkini.
10. **Implementasikan Caching Layer pada Validator Asinkron:** Jangan pernah melakukan HTTP request untuk value yang sama yang baru saja diverifikasi.

---

### 12. Hands-on Practice

Panduan implementasi step-by-step untuk membangun arsitektur form dynamic checklist enterprise yang disimpan pada direktori: `hands-on/m02/`.

#### Struktur Direktori
```
hands-on/m02/
├── dynamic-survey/
│   ├── survey-matrix.component.ts
│   ├── matrix-rating.component.ts
│   └── survey-schema.interface.ts
└── main-practice.ts
```

#### Langkah 1: Buat interface schema
Simpan pada `hands-on/m02/dynamic-survey/survey-schema.interface.ts`:
```typescript
export interface SurveyQuestion {
  id: string;
  label: string;
  category: string;
  weight: number;
}

export interface SurveyScoreResult {
  scores: Record<string, number>;
  aggregateScore: number;
  isAuditRequired: boolean;
}
```

#### Langkah 2: Buat Sub-komponen CVA Matrix Rating
Simpan pada `hands-on/m02/dynamic-survey/matrix-rating.component.ts`:
```typescript
import { Component, forwardRef, ChangeDetectionStrategy, ChangeDetectorRef, inject } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-matrix-rating',
  standalone: true,
  imports: [CommonModule],
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => MatrixRatingComponent),
      multi: true
    }
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="rating-group" [class.rating-disabled]="disabled">
      <button 
        type="button" 
        *ngFor="let star of stars" 
        (click)="selectRating(star)"
        [class.selected]="currentRating !== null && star <= currentRating"
        class="star-btn"
      >
        ★
      </button>
      <span class="rating-display" *ngIf="currentRating">({{ currentRating }}/5)</span>
    </div>
  `,
  styles: [`
    .rating-group { display: inline-flex; align-items: center; gap: 4px; }
    .star-btn { background: none; border: none; font-size: 20px; color: #cbd5e1; cursor: pointer; }
    .star-btn.selected { color: #f59e0b; }
    .rating-disabled { opacity: 0.5; pointer-events: none; }
    .rating-display { font-size: 12px; font-weight: bold; margin-left: 8px; color: #64748b; }
  `]
})
export class MatrixRatingComponent implements ControlValueAccessor {
  private cdr = inject(ChangeDetectorRef);
  stars = [1, 2, 3, 4, 5];
  currentRating: number | null = null;
  disabled = false;

  private onChange: (val: number | null) => void = () => {};
  private onTouched: () => void = () => {};

  writeValue(val: number | null): void {
    this.currentRating = val;
    this.cdr.markForCheck();
  }

  registerOnChange(fn: (val: number | null) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled = isDisabled;
    this.cdr.markForCheck();
  }

  selectRating(score: number): void {
    if (this.disabled) return;
    this.currentRating = score;
    this.onChange(this.currentRating);
    this.onTouched();
  }
}
```

#### Langkah 3: Buat Container Matrix Dynamic Record
Simpan pada `hands-on/m02/dynamic-survey/survey-matrix.component.ts`:
```typescript
import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormRecord, FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatrixRatingComponent } from './matrix-rating.component';
import { SurveyQuestion } from './survey-schema.interface';

@Component({
  selector: 'app-survey-matrix',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MatrixRatingComponent],
  template: `
    <div class="matrix-card">
      <h2>Audit Penilaian Risiko Operasional</h2>
      <form [formGroup]="surveyForm" (ngSubmit)="persistForm()">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="border-b">
              <th class="py-2">Indikator Kepatuhan</th>
              <th class="py-2">Kategori</th>
              <th class="py-2">Rating Evaluasi</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let q of questions" class="border-b">
              <td class="py-2">{{ q.label }}</td>
              <td class="py-2 text-sm text-gray-500">{{ q.category }}</td>
              <td class="py-2">
                <app-matrix-rating [formControlName]="q.id"></app-matrix-rating>
              </td>
            </tr>
          </tbody>
        </table>

        <div class="mt-4 flex items-center justify-between">
          <div>
            <strong>Status Formulir:</strong>
            <span [class.text-green-600]="surveyForm.valid" [class.text-red-600]="surveyForm.invalid">
              {{ surveyForm.valid ? 'LENGKAP & VALID' : 'BELUM SELESAI' }}
            </span>
          </div>
          <button 
            type="submit" 
            [disabled]="surveyForm.invalid"
            class="bg-indigo-600 text-white px-4 py-2 rounded disabled:opacity-50"
          >
            Kirim Hasil Audit
          </button>
        </div>
      </form>
    </div>
  `,
  styles: [`
    .matrix-card { max-width: 800px; margin: 2rem auto; padding: 1.5rem; background: white; border-radius: 8px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
  `]
})
export class SurveyMatrixComponent implements OnInit {
  private fb = inject(FormBuilder);

  questions: SurveyQuestion[] = [
    { id: 'SEC_01', label: 'Protokol Enkripsi Database End-to-End', category: 'Security', weight: 3 },
    { id: 'SEC_02', label: 'Manajemen Rotasi Kunci SSH Produksi', category: 'Security', weight: 2 },
    { id: 'OPS_01', label: 'Tingkat Dokumentasi Runbook Insiden P1', category: 'Operations', weight: