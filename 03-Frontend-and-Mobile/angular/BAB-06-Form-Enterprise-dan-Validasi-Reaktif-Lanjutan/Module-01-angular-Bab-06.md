# BAB 06: MODULE 01 — FORM ENTERPRISE & VALIDASI REAKTIF LANJUTAN

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 03-Frontend-and-Mobile
* **Teknologi Utama:** Angular (v16+ hingga v19)
* **Topik Modul:** Form Enterprise & Validasi Reaktif Lanjutan
* **Kode Modul:** ANG-ADV-06-01
* **Tingkat Kompleksitas:** Advanced / Staff Engineer Level
* **Prasyarat:** Pemahaman solid mengenai RxJS Observables, Angular Dependency Injection, Typed Reactive Forms dasar, arsitektur OnPush Change Detection, dan Angular Lifecycle Hooks.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Membangun Komponen Form Kustom Skala Enterprise:** Mengimplementasikan interface `ControlValueAccessor` (CVA) secara tepat, bebas memory leak, dan sepenuhnya kompatibel dengan Form API standar Angular.
2. **Menguasai Validasi Asinkron & Cross-Field:** Merancang validator reaktif murni (Sync dan Async) berbasis RxJS pipe (`switchMap`, `debounceTime`, `distinctUntilChanged`) dengan penanganan `cancellation` dan `race conditions`.
3. **Mengimplementasikan Struktur Form Dinamis Bertingkat:** Memanipulasi `FormArray` dan `FormRecord` secara dinamis pada runtime untuk menangani payload JSON kompleks dengan performa rendering optimal.
4. **Menerapkan Tipestriktural (Strict Typing):** Memanfaatkan fitur Strongly Typed Reactive Forms bawaan Angular untuk mengeliminasi kesalahan tipe saat compile-time pada hierarki form bertingkat tinggi.
5. **Menghubungkan State Form dengan Reaktivitas Modern:** Menyelaraskan status validitas form, pending states, dan mutasi payload ke dalam paradigma modern Angular (kombinasi RxJS dan Signals).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam aplikasi monolitik enterprise (seperti perbankan, sistem klaim asuransi, atau ERP), form bukan sekadar kumpulan elemen tag `<input>` dan `<select>` dalam HTML. Form harus diperlakukan sebagai **state machine terisolasi yang mengelola siklus hidup data tak tepercaya (untrusted external state)** sebelum data tersebut ditransformasikan menjadi entitas domain yang valid.

### Mental Model 1: UI Input vs. Model Abstraction
Elemen DOM native hanya memahami tipe primitif (string, boolean, number via parse). Jangan membiarkan hierarki bisnis Anda didikte oleh keterbatasan native DOM. Melalui `ControlValueAccessor`, kita membangun jembatan dua arah (bidirectional adapter pattern) yang mengonversi data domain kompleks (misalnya objek `{ currency: 'IDR', amount: 5000000, exchangeRate: 1 }`) ke representasi visual, dan sebaliknya.

```
[ Domain Object ] <---> [ ControlValueAccessor ] <---> [ Native DOM / Canvas ]
```

### Mental Model 2: The Push-Driven State Engine
`FormGroup`, `FormControl`, dan `FormArray` bukanlah visual container, melainkan **in-memory data nodes** yang independen dari DOM tree. Validasi bukan aksi prosedural yang dijalankan saat tombol "Submit" diklik; validasi adalah stream evaluator kontinu yang merespons event emisi (`valueChanges`, `statusChanges`) dengan kapabilitas pembatalan otomatis (*cancellation semantics*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur hidup sinkronisasi data dan evaluasi validasi asinkron di bawah naungan Angular Reactive Forms ditunjukkan oleh diagram alur arsitektural berikut:

```
+---------------------------------------------------------------------------------------------------+
| USER INTERACTION LAYER (DOM / Component Template)                                                |
|   User types: "ID-9921-X" -> triggers (input) event                                               |
+---------------------------------------------------------------------------------------------------+
                                            |
                                            v (View-to-Model sync)
+---------------------------------------------------------------------------------------------------+
| CONTROL VALUE ACCESSOR (CVA BRIDGE)                                                               |
|   1. Captures native event -> calls registered 'onChange(value)' callback                        |
|   2. Updates internal component rendering state                                                  |
+---------------------------------------------------------------------------------------------------+
                                            |
                                            v (Pushes value to FormControl)
+---------------------------------------------------------------------------------------------------+
| FORMCONTROL ABSTRACT NODE                                                                         |
|   1. Sets 'dirty = true', 'touched = true' (if blur)                                              |
|   2. Updates 'rawValue' & emits valueChanges stream                                               |
|   3. Status transition: STATUS = 'PENDING'                                                        |
+---------------------------------------------------------------------------------------------------+
                                            |
                                            +---------------------------------------+
                                            |                                       |
                                            v (Step A: Synchronous)                 v (Step B: Asynchronous)
+-----------------------------------------------+   +-----------------------------------------------+
| SYNCHRONOUS VALIDATORS                        |   | ASYNCHRONOUS VALIDATORS PIPELINE              |
| - RequiredValidator                           |   | - Debounce Input (e.g., 300ms)                |
| - RegexPatternValidator                       |   | - DistinctUntilChanged Filter                 |
| - Custom Cross-field Sync Check               |   | - switchMap to Backend API / gRPC-Web Client  |
+-----------------------------------------------+   +-----------------------------------------------+
      |                                                   |
      | Pass: null                                        | Returns: Observable<{ asyncError: true } | null>
      | Fail: { invalidFormat: true }                     | (Cancels previous pending HTTP via switchMap)
      |                                                   |
      +---------------------+-----------------------------+
                            |
                            v
+---------------------------------------------------------------------------------------------------+
| STATUS RESOLUTION ENGINE                                                                          |
|   If any Sync fails    -> STATUS = 'INVALID' (Short-circuit async validation)                     |
|   If Sync passes       -> Wait for Async stream resolution                                        |
|   If Async completes   -> STATUS = 'VALID' OR 'INVALID'                                           |
|   Emits statusChanges stream                                                                      |
+---------------------------------------------------------------------------------------------------+
                            |
                            v
+---------------------------------------------------------------------------------------------------+
| ROOT FORM NOTIFICATION & BUBBLING                                                                 |
|   Parent FormGroups & FormArrays recalculate validity based on leaf-node updates                  |
|   Triggers Angular OnPush Change Detection via Signal / MarkForCheck                             |
+---------------------------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. `NG_VALUE_ACCESSOR` Injection Token
`ControlValueAccessor` bekerja melalui mekanisme Dependency Injection (DI) multi-provider. Ketika direktif `formControlName`, `formControl`, atau `ngModel` diterapkan pada komponen kustom, Angular menginjeksi token `NG_VALUE_ACCESSOR`. 

```typescript
providers: [
  {
    provide: NG_VALUE_ACCESSOR,
    useExisting: forwardRef(() => CustomInputComponent),
    multi: true
  }
]
```
Jika kita lupa menyertakan konfigurasi provider ini, Angular melempar runtime error:
`Error: No value accessor for form control with name: 'xyz'`.

### 2. Interface Lifecycle CVA
* `writeValue(obj: any): void`
  Dipanggil oleh Angular Form API untuk mem-push model domain ke dalam View (Model-to-View). **Catatan krusial:** Fungsi ini dipanggil sebelum `ngOnInit`, sehingga inisialisasi internal harus aman dari nilai `null`/`undefined`.
* `registerOnChange(fn: any): void`
  Angular menyerahkan callback function internal (`fn`). Komponen bertanggung jawab memanggil `fn(value)` setiap kali interaksi pengguna memutasi nilai internal (View-to-Model).
* `registerOnTouched(fn: any): void`
  Menyerahkan callback yang harus dipanggil saat kontrol kehilangan fokus (event `blur`) untuk menandai control sebagai `touched`.
* `setDisabledState?(isDisabled: boolean): void`
  Dipanggil ketika status kontrol berubah via `.disable()` atau `.enable()` pada API reaktif. Mengontrol DOM attribute `disabled`.

### 3. Pipeline Validasi: Sinkron vs. Asinkron
Mekanisme internal `AbstractControl` mengevaluasi validasi secara serial bertahap:
1. Jalankan semua *Synchronous Validators*. Jika setidaknya satu menghasilkan objek error `ValidationErrors`, status langsung ditetapkan menjadi `INVALID`.
2. Validasi Asinkron **tidak pernah dijalankan** jika validasi sinkron gagal. Ini merupakan mekanisme optimasi native Angular untuk mencegah *unnecessary network calls*.
3. Jika validasi sinkron lulus, status kontrol berubah seketika menjadi `PENDING`, dan array *Async Validators* dievaluasi via `forkJoin` internal atau stream pipeline.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Strict Typing Reactive Forms (Angular 14+)
Secara historis, `FormGroup` dan `FormControl` bersifat untyped (`any`). Mulai Angular 14, tipe sistem didesain ulang secara fundamental menggunakan Generics TypeScript:

```typescript
export interface EmployeeForm {
  id: FormControl<string>;
  salary: FormControl<number>;
  department: FormControl<string | null>;
  skills: FormArray<FormControl<string>>;
}
```

Tipe kontrol mempertahankan status `nullability`. Secara default, memanggil `control.reset()` akan mengubah nilai kontrol menjadi `null`. Jika kontrol didefinisikan tidak boleh null:
```typescript
const idControl = new FormControl<string>('EMP-001', { nonNullable: true });
idControl.reset(); // Nilainya kembali ke 'EMP-001', bukan null!
```

### FormRecord: Koleksi Homogen Dinamis
Ketika jumlah kontrol berubah secara dinamis pada runtime dan nama propertinya (*keys*) tidak diketahui saat compile-time (misalnya: dictionary izin pengguna `permissions: { [permissionName: string]: boolean }`), gunakan `FormRecord`.

`FormGroup` biasa membutuhkan definisi struktur properti yang ketat dan statis. `FormRecord<FormControl<boolean>>` mengizinkan operasi penambahan dan penghapusan key secara dinamis dengan tetap mempertahankan keamanan tipe (type-safety) untuk nilai anak-anaknya.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi Custom Form Control menggunakan `ControlValueAccessor` untuk komponen pemilih mata uang enterprise (*Currency Amount Input*).

```typescript
// currency-input.component.ts
import { Component, forwardRef, ChangeDetectionStrategy, Input, signal } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { CommonModule } from '@angular/common';

export interface CurrencyValue {
  currency: string;
  amount: number;
}

@Component({
  selector: 'app-currency-input',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="currency-group" [class.disabled]="isDisabled()">
      <select 
        [value]="currentValue().currency" 
        [disabled]="isDisabled()"
        (change)="onCurrencyChange($event)">
        <option *ngFor="let c of supportedCurrencies" [value]="c">{{ c }}</option>
      </select>
      <input 
        type="number" 
        [value]="currentValue().amount" 
        [disabled]="isDisabled()"
        (input)="onAmountChange($event)"
        (blur)="onBlur()"
        placeholder="0.00" />
    </div>
  `,
  styles: [`
    .currency-group { display: flex; gap: 8px; }
    .currency-group.disabled { opacity: 0.5; pointer-events: none; }
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
  @Input() supportedCurrencies: string[] = ['IDR', 'USD', 'EUR', 'SGD'];

  // State internal dikelola via Angular Signals
  protected currentValue = signal<CurrencyValue>({ currency: 'IDR', amount: 0 });
  protected isDisabled = signal<boolean>(false);

  private onChange: (val: CurrencyValue) => void = () => {};
  private onTouched: () => void = () => {};

  // 1. Model-to-View: Dipanggil ketika FormControl mem-push nilai baru
  writeValue(value: CurrencyValue | null): void {
    if (value) {
      this.currentValue.set(value);
    } else {
      this.currentValue.set({ currency: 'IDR', amount: 0 });
    }
  }

  // 2. Registrasi event handler dari Reactive Forms
  registerOnChange(fn: (val: CurrencyValue) => void): void {
    this.onChange = fn;
  }

  // 3. Registrasi event touch (blur) dari Reactive Forms
  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  // 4. Penanganan status disabled
  setDisabledState(isDisabled: boolean): void {
    this.isDisabled.set(isDisabled);
  }

  // DOM Event Emitters -> Memanggil adapter CVA
  protected onCurrencyChange(event: Event): void {
    const target = event.target as HTMLSelectElement;
    const updated: CurrencyValue = { ...this.currentValue(), currency: target.value };
    this.currentValue.set(updated);
    this.onChange(updated);
  }

  protected onAmountChange(event: Event): void {
    const target = event.target as HTMLInputElement;
    const updated: CurrencyValue = { ...this.currentValue(), amount: parseFloat(target.value) || 0 };
    this.currentValue.set(updated);
    this.onChange(updated);
  }

  protected onBlur(): void {
    this.onTouched();
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 33–39:** Konfigurasi `providers` meregistrasikan `NG_VALUE_ACCESSOR`. Penggunaan `forwardRef(() => CurrencyInputComponent)` wajib dilakukan karena class `CurrencyInputComponent` belum selesai di-parsing oleh runtime JS engine saat objek dekorator dievaluasi.
* **Baris 43–44:** State internal komponen dilacak menggunakan Angular Signals (`signal<CurrencyValue>`). Hal ini mengisolasi pembaruan view internal secara cepat dan aman di bawah strategi `ChangeDetectionStrategy.OnPush`.
* **Baris 46–47:** Default no-op functions (`() => {}`) untuk `onChange` dan `onTouched`. Pola defensif ini mencegah terjadinya error `TypeError: this.onChange is not a function` apabila interaksi view terjadi secara instan sebelum registrasi Angular selesai.
* **Baris 50–56:** Implementasi `writeValue(value)`. Method ini memastikan fallback parsing jika data eksternal masuk berupa `null` atau `undefined`, mencegah downstream DOM rendering crash.
* **Baris 72–84:** Menghubungkan perubahan pada native DOM (`<select>` dan `<input>`) ke sistem reaktif form. Nilai diekstrak dari `event.target`, state sinyal diperbarui, lalu `this.onChange(updated)` dieksekusi untuk memicu emisi pada `FormControl.valueChanges`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Bisnis: Sistem Pengajuan Fasilitas Kredit Korporasi Multi-Cabang
Di industri *Corporate Banking*, calon debitur korporat mengajukan fasilitas kredit multi-mata uang (*Credit Facility Limits*). Form ini memiliki kompleksitas ekstrem:

1. **Struktur Matriks Bertingkat:** Satu aplikasi kredit memiliki multiple anak perusahaan (subsidiaries). Tiap anak perusahaan memiliki array alokasi limit kredit.
2. **Validasi Silang (Cross-Field Cross-Entity):** Total limit gabungan seluruh anak perusahaan tidak boleh melampaui `Global Parent Exposure Limit`.
3. **Validasi Asinkron Tingkat Tinggi:** Setiap NPWP/Tax Identification Number yang dimasukkan anak perusahaan harus divalidasi ke Core Banking AML (Anti-Money Laundering) dan Tax Clearing Engine via HTTP API. Panggilan API harus di-*debounce*, dibatalkan jika pengguna masih mengetik, dan tidak boleh menghasilkan race condition antar-baris array.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah arsitektur produksi lengkap yang mengintegrasikan Custom Validator, Async Validator berbasis HTTP, serta Typed Dynamic Forms.

### 1. Definisi Model dan Anti-Money Laundering Validation Service

```typescript
// credit-application.models.ts
import { FormControl, FormArray, FormGroup } from '@angular/forms';
import { CurrencyValue } from './currency-input.component';

export interface SubsidiaryLimitForm {
  subsidiaryName: FormControl<string>;
  taxId: FormControl<string>;
  allocatedFacility: FormControl<CurrencyValue>;
}

export interface CorporateCreditForm {
  parentCompanyName: FormControl<string>;
  maxGlobalLimit: FormControl<number>;
  subsidiaries: FormArray<FormGroup<SubsidiaryLimitForm>>;
}
```

```typescript
// aml-tax-validation.service.ts
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, timer } from 'rxjs';
import { map, switchMap, catchError } from 'rxjs/operators';
import { AbstractControl, AsyncValidatorFn, ValidationErrors } from '@angular/forms';

@Injectable({ providedIn: 'root' })
export class AmlValidationService {
  private http = inject(HttpClient);

  validateTaxId(): AsyncValidatorFn {
    return (control: AbstractControl): Observable<ValidationErrors | null> => {
      if (!control.value) {
        return of(null);
      }

      // Hindari validasi berulang jika nilainya tidak berubah secara signifikan
      return timer(400).pipe(
        switchMap(() => {
          return this.http.get<{ isBlacklisted: boolean; valid: boolean }>(
            `/api/v1/compliance/verify-tax/${control.value}`
          );
        }),
        map((response) => {
          if (!response.valid) {
            return { invalidTaxIdFormat: true };
          }
          if (response.isBlacklisted) {
            return { amlBlacklisted: { reason: 'Entity found in AML Watchlist database.' } };
          }
          return null;
        }),
        catchError(() => {
          // Failure Mode: Mengembalikan error jaringan spesifik
          return of({ networkValidationError: 'Gagal menghubungi server kepatuhan.' });
        })
      );
    };
  }
}
```

### 2. Cross-Field Validator: Total Exposure Limit Enforcement

```typescript
// corporate-validators.ts
import { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';
import { CurrencyValue } from './currency-input.component';

export function aggregateExposureValidator(): ValidatorFn {
  return (group: AbstractControl): ValidationErrors | null => {
    const maxLimit = group.get('maxGlobalLimit')?.value;
    const subsidiaries = group.get('subsidiaries') as AbstractControl | null;

    if (!subsidiaries || typeof maxLimit !== 'number') {
      return null;
    }

    const subsidiaryControls = (subsidiaries as any).controls as AbstractControl[];
    if (!subsidiaryControls || subsidiaryControls.length === 0) {
      return null;
    }

    // Normalisasi asumsi kurs ke IDR untuk komparasi sederhana
    const totalAllocated = subsidiaryControls.reduce((sum, subGroup) => {
      const facility = subGroup.get('allocatedFacility')?.value as CurrencyValue;
      if (!facility || !facility.amount) return sum;
      
      const rate = facility.currency === 'USD' ? 15000 : 1;
      return sum + (facility.amount * rate);
    }, 0);

    if (totalAllocated > maxLimit) {
      return {
        exposureLimitExceeded: {
          max: maxLimit,
          actual: totalAllocated,
          difference: totalAllocated - maxLimit
        }
      };
    }

    return null;
  };
}
```

### 3. Komponen Form Enterprise Utama

```typescript
// corporate-credit-form.component.ts
import { Component, OnInit, inject, ChangeDetectionStrategy, DestroyRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators, FormGroup, FormArray } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CurrencyInputComponent } from './currency-input.component';
import { AmlValidationService } from './aml-tax-validation.service';
import { CorporateCreditForm, SubsidiaryLimitForm } from './credit-application.models';
import { aggregateExposureValidator } from './corporate-validators';

@Component({
  selector: 'app-corporate-credit-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, CurrencyInputComponent],
  templateUrl: './corporate-credit-form.component.html',
  styleUrls: ['./corporate-credit-form.component.css'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class CorporateCreditFormComponent implements OnInit {
  private fb = inject(FormBuilder);
  private amlService = inject(AmlValidationService);
  private destroyRef = inject(DestroyRef);

  // Deklarasi Typed Root Form
  protected creditForm!: FormGroup<CorporateCreditForm>;

  get subsidiaries(): FormArray<FormGroup<SubsidiaryLimitForm>> {
    return this.creditForm.controls.subsidiaries;
  }

  ngOnInit(): void {
    this.buildForm();
    this.setupReactivity();
  }

  private buildForm(): void {
    this.creditForm = this.fb.group<CorporateCreditForm>({
      parentCompanyName: this.fb.control('', {
        nonNullable: true,
        validators: [Validators.required, Validators.minLength(4)]
      }),
      maxGlobalLimit: this.fb.control(100_000_000_000, {
        nonNullable: true,
        validators: [Validators.required, Validators.min(1_000_000)]
      }),
      subsidiaries: this.fb.array<FormGroup<SubsidiaryLimitForm>>([])
    }, {
      validators: [aggregateExposureValidator()]
    });

    // Inisialisasi minimal 1 form anak perusahaan
    this.addSubsidiary();
  }

  protected addSubsidiary(): void {
    const subGroup: FormGroup<SubsidiaryLimitForm> = this.fb.group<SubsidiaryLimitForm>({
      subsidiaryName: this.fb.control('', {
        nonNullable: true,
        validators: [Validators.required]
      }),
      taxId: this.fb.control('', {
        nonNullable: true,
        validators: [Validators.required, Validators.pattern(/^[0-9]{15,16}$/)],
        asyncValidators: [this.amlService.validateTaxId()]
      }),
      allocatedFacility: this.fb.control({ currency: 'IDR', amount: 0 }, {
        nonNullable: true,
        validators: [
          (control) => (control.value?.amount <= 0 ? { invalidAmount: true } : null)
        ]
      })
    });

    this.subsidiaries.push(subGroup);
  }

  protected removeSubsidiary(index: number): void {
    if (this.subsidiaries.length > 1) {
      this.subsidiaries.removeAt(index);
      this.creditForm.updateValueAndValidity();
    }
  }

  private setupReactivity(): void {
    // Audit log reaktif untuk perubahan status validitas form
    this.creditForm.statusChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((status) => {
        console.info(`[FORM-AUDIT] Form Validity Status Changed to: ${status}`);
      });
  }

  protected onSubmit(): void {
    if (this.creditForm.invalid) {
      this.creditForm.markAllAsTouched();
      return;
    }

    const payload = this.creditForm.getRawValue();
    console.info('Payload siap dikirim ke microservice ingestion engine:', payload);
    // Eksekusi HTTP Service Submission di sini
  }
}
```

```html
<!-- corporate-credit-form.component.html -->
<form [formGroup]="creditForm" (ngSubmit)="onSubmit()" class="enterprise-form">
  <h2>Permohonan Fasilitas Kredit Korporasi</h2>

  <div class="form-field">
    <label>Nama Korporasi Induk</label>
    <input type="text" formControlName="parentCompanyName" />
    <span class="error" *ngIf="creditForm.controls.parentCompanyName.touched && creditForm.controls.parentCompanyName.errors?.['required']">
      Nama Korporasi wajib diisi.
    </span>
  </div>

  <div class="form-field">
    <label>Maksimal Limit Exposure (IDR Equiv)</label>
    <input type="number" formControlName="maxGlobalLimit" />
  </div>

  <div class="subsidiaries-section" formArrayName="subsidiaries">
    <h3>Entitas Anak Perusahaan</h3>
    
    <div 
      *ngFor="let sub of subsidiaries.controls; let i = index" 
      [formGroupName]="i" 
      class="subsidiary-row">
      
      <div class="field">
        <label>Nama Entitas Anak</label>
        <input type="text" formControlName="subsidiaryName" />
      </div>

      <div class="field">
        <label>NPWP Entitas (15-16 Digit)</label>
        <input type="text" formControlName="taxId" />
        <span class="status" *ngIf="sub.controls.taxId.pending">Memeriksa AML & Status Pajak...</span>
        <span class="error" *ngIf="sub.controls.taxId.errors?.['amlBlacklisted']">
          {{ sub.controls.taxId.errors?.['amlBlacklisted'].reason }}
        </span>
      </div>

      <div class="field">
        <label>Alokasi Fasilitas</label>
        <app-currency-input formControlName="allocatedFacility"></app-currency-input>
      </div>

      <button type="button" class="btn-remove" (click)="removeSubsidiary(i)" [disabled]="subsidiaries.length === 1">
        Hapus
      </button>
    </div>

    <button type="button" class="btn-secondary" (click)="addSubsidiary()">+ Tambah Anak Perusahaan</button>
  </div>

  <!-- Form-level Cross-field Validation Feedback -->
  <div class="alert-error" *ngIf="creditForm.errors?.['exposureLimitExceeded']">
    Peringatan: Total alokasi entitas melebihi Global Limit sebesar: 
    {{ creditForm.errors?.['exposureLimitExceeded'].difference | number }} IDR
  </div>

  <div class="action-footer">
    <button type="submit" [disabled]="creditForm.pending || creditForm.invalid" class="btn-primary">
      Submit Form
    </button>
  </div>
</form>
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek Arsitektur | Template-Driven Forms | Reactive Forms Biasa (Untyped) | Strictly Typed Reactive Forms (Modern) |
| :--- | :--- | :--- | :--- |
| **Model Paradigma** | Aksidental dua arah (`[(ngModel)]`), async secara template compilation | Programmatik, mutable streams, untyped runtime objects | Deklaratif, Strongly Typed Compiler-Checked State Engine |
| **Beban Runtime vs Compile-time** | Error baru terdeteksi di runtime saat navigasi template | Tipe `any`, silent bug saat salah memetakan nama field | Semua key & tipe diuji saat compile (`tsc`), zero runtime overhead |
| **Kemudahan Testing** | Sulit (Wajib me-mount DOM/TestBed) | Mudah (Instansiasi kelas tanpa TestBed) | Sangat Tinggi (Unit test data pure class tanpa kompilasi template) |
| **Penanganan Dynamic Array** | Rapuh dan lambat pada data ribuan baris | Cepat, namun rentan *type drifting* | Cepat, aman, autocomplete aktif hingga deep child node |
| **Kompleksitas Implementasi** | Rendah (Cocok untuk form statis sederhana) | Menengah | Tinggi di awal, Maintenance TCO (Total Cost of Ownership) sangat rendah |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Race Condition pada Async Validators
* **Skenario Masalah:** Pengguna mengetik string `"A"`, validator asinkron memicu HTTP call #1 (latensi 1.5 detik). Pengguna langsung mengetik `"AB"`, memicu HTTP call #2 (latensi 200 milidetik). Jika HTTP call #2 selesai mendahului call #1, respons lama call #1 dapat menimpa hasil dan menandai form dengan status yang salah.
* **Mitigasi:** Gunakan operator RxJS `switchMap` di dalam fungsi validator (seperti pada implementasi `AmlValidationService`). `switchMap` secara otomatis melakukan `unsubscribe()` dan membatalkan underlying `XMLHttpRequest`/`fetch` HTTP call sebelumnya setiap kali emisi baru masuk dari debounce timer.

### 2. Disabling Control Mematikan Validasi dan Menghilangkan Nilai dari `.value`
* **Skenario Masalah:** Memanggil `control.disable()` menyebabkan kontrol tersebut dikeluarkan dari payload `form.value`. Jika backend enterprise membutuhkan kontrol yang disabled tersebut dikirim sebagai read-only payload, data akan hilang (`undefined`).
* **Mitigasi:** Jangan membaca dari `form.value` secara langsung. Gunakan method **`form.getRawValue()`**. `getRawValue()` menjamin seluruh hierarki form diekstraksi ke objek JSON terlepas dari status disabled kontrol individual.

### 3. Mutasi Nilai di dalam Subscription `valueChanges` yang Menyebabkan Infinite Loops
* **Skenario Masalah:** Melakukan formatting string di dalam listener:
  ```typescript
  this.control.valueChanges.subscribe(val => {
    this.control.setValue(val.toUpperCase()); // CRITICAL: Infinite recursion stack overflow!
  });
  ```
* **Mitigasi:** Selalu berikan opsi `{ emitEvent: false }` saat memutasi nilai dari dalam stream reaksi:
  ```typescript
  this.control.setValue(val.toUpperCase(), { emitEvent: false });
  ```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Mengabaikan Unsubscribe pada Form Stream
Memasang `.subscribe()` pada `form.valueChanges` di dalam komponen tanpa mekanisme penghancuran menyebabkan *detatched DOM memory leak*, karena tree form instance tetap terikat pada memori subscription stream.
* *Solusi:* Gunakan `takeUntilDestroyed()` dari `@angular/core/rxjs-interop` yang diinjeksi pada injection context constructor.

### Kesalahan Fatal 2: Menaruh Validasi Kompleks di Dalam Template HTML
Menulis logika evaluasi validasi rumit seperti `*ngIf="form.get('a').value > form.get('b').value && ..."` langsung pada template HTML.
* *Solusi:* Buat custom validator tingkat `FormGroup` (Cross-field validator). Template hanya bertugas memeriksa keberadaan flag error seperti `form.errors?.['exposureLimitExceeded']`.

### Kesalahan Fatal 3: Memanipulasi Native Input Langsung via Renderer2/ElementRef di CVA
Mengubah `inputElement.value` secara manual tanpa memanggil callback `this.onChange(val)` yang diberikan Angular.
* *Solusi:* Selalu delegasikan mutasi state data melalui pipeline resmi `this.onChange` agar Angular Forms Engine dapat mendistribusikannya secara konsisten ke seluruh node turunan dan induk.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Factory Method `FormBuilder.nonNullable`:**
   Manfaatkan `fb.nonNullable.group()` untuk mencegah nilai control kembali menjadi `null` secara tidak sengaja saat method `form.reset()` dieksekusi.
2. **Komposisi Validator Modular (Single Responsibility Principle):**
   Satu fungsi validator hanya boleh memvalidasi satu aturan bisnis spesifik. Gabungkan beberapa validator menggunakan array validator: `[Validators.required, customTaxFormatValidator(), blacklistValidator()]`.
3. **Immutabilitas Payload State:**
   Sebelum mengirim payload `form.getRawValue()` ke API, transformasikan payload menggunakan mapper function terisolasi (DTO Transformer) untuk memisahkan UI form state dari domain API contract.
4. **Sentralisasi Penanganan Pesan Error:**
   Hindari hardcoding pesan error di ratusan template HTML. Buat pipa atau komponen `<app-form-error [control]="control">` yang otomatis membaca key error Angular dan menerjemahkannya berdasarkan kamus i18n sistem.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Strategi Debouncing dan Pemfilteran Nilai Unik
Setiap ketikan user tidak boleh langsung mengevaluasi komputasi regex berat atau melempar query backend. Pastikan selalu ada pipeline:
```typescript
control.valueChanges.pipe(
  debounceTime(300),
  distinctUntilChanged(),
  // operasi lanjutan
)
```

### 2. Opsi `updateOn: 'blur'` untuk Skala Ekstrem
Secara default, Angular mengevaluasi validasi dan pembaruan model pada setiap *keystroke* (`updateOn: 'change'`). Jika Anda memiliki form dengan ratusan kontrol dinamis dalam satu layar, konfigurasikan strategi pembaruan kontrol menjadi `'blur'` atau `'submit'`:
```typescript
const control = new FormControl('', {
  updateOn: 'blur', // Hanya validasi saat kontrol kehilangan fokus DOM
  validators: [heavyComputationValidator]
});
```

### 3. Mengurangi CD Cycles dengan `ChangeDetectionStrategy.OnPush`
Pastikan seluruh komponen custom form menerapkan `OnPush`. Ketika nilai form berubah via `writeValue`, perbarui state internal menggunakan `Signal` atau panggil `ChangeDetectorRef.markForCheck()` secara eksplisit.

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Sanitasi Input vs. Blind Rendering
Jangan pernah mencetak teks input pengguna mentah yang berasal dari nilai form langsung ke dalam DOM via `[innerHTML]`. Selalu gunakan binding teks biasa `{{ formValue }}` untuk mengaktifkan mekanisme auto-escaping Angular yang memitigasi serangan Cross-Site Scripting (XSS).

### 2. Validasi Klien Bukan Garansi Integritas Data
Validasi reaktif pada Angular hanyalah instrumen UX (User Experience) untuk memberikan *feedback loop* instan kepada pengguna. Seluruh aturan validasi (termasuk format regex, batas angka, dan verifikasi identitas) **wajib diulang secara identik di Application Gateway / Backend API Layer**. Klien dapat memotong validasi Angular dengan mudah melalui browser DevTools atau manipulasi payload HTTP