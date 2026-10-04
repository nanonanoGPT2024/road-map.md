# Kurikulum Rekayasa Frontend Enterprise: React
## BAB 08: Enterprise Form Systems & Mutation Workflows
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan memiliki kompetensi tingkat lanjut untuk:
*   Menganalisis dan merekonstruksi arsitektur internal manajemen form berbasis *subscription* (uncontrolled-with-proxy) guna menekan render cycle ke tingkat $O(1)$ relatif terhadap ukuran form tree.
*   Mengembangkan pipeline validasi schema-driven yang dinamis, strongly typed, dan mendukung dynamic conditional branching serta cross-field asynchronous validation menggunakan Zod dan React Hook Form.
*   Merancang orkestrasi mutasi server-state terdistribusi dengan TanStack Query v5, mencakup *optimistic UI updates* dengan snapshot rollback otomatis, concurrency race-condition handling, dan resilient multi-part mutation pipelines.
*   Mengimplementasikan arsitektur *Multi-Step Wizard Form Engine* modular yang mendukung isolated draft persistence, deep field nesting dynamic array indexing, dan state hydration antarsesi.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib menguasai:
*   Pemahaman mendalam tentang React Fiber Reconciler, Commit Phase vs. Render Phase, dan mekanisme SyntheticEvent.
*   TypeScript tingkat lanjut: Type conditional, template literal types, distributive conditional types, mapped types, dan type narrowing.
*   Arsitektur Web API: File API, Blob, FormData lifecycle, AbortController, serta Streams API.
*   Dasar TanStack Query (Query Cache, Query Invalidation, dan Mutation Lifecycle).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Anatomi Performa: Controlled State vs. Observer-Based Proxy State
Pada form enterprise dengan ratusan data-point (misalnya sistem underwriting perbankan atau konfigurasi multi-cloud ERP), pola tradisional *controlled component* menyebabkan degradasi performa:

```
[User Input: Keystroke 'a']
       │
       ▼
[SyntheticEvent onChange] ──► [setState(newValue)]
                                     │
                                     ▼
                        [Trigger Re-render Host Component]
                                     │
                       ┌─────────────┴─────────────┐
                       ▼                           ▼
            [Diff Virtual DOM Tree]     [Re-evaluate Children]
                       │                           │
                       └─────────────┬─────────────┘
                                     ▼
                            [Commit to Native DOM]
```

Kompleksitas render dari pola ini adalah $O(N \cdot M)$ di mana $N$ adalah kedalaman komponen dalam subtree form dan $M$ adalah frekuensi emisi event keyboard.

Sebaliknya, arsitektur modern berbasis *uncontrolled observer* (seperti React Hook Form) mendaftarkan referensi native DOM input (`HTMLInputElement`) ke dalam mutable central registry via React `ref`. State form tidak disimpan di dalam React Component State (`useState`), melainkan di dalam isolasi *Mutable Reference Store*.

```
[User Input: Keystroke 'a']
       │
       ▼
[Native DOM Input Event] ──► Updates DOM Value Directly (Native C++ Engine Level)
       │
       ├─► [RHF Native Listener (Change/Blur)]
       │         │
       │         ▼
       │   [Proxy Observer Pattern]
       │   Evaluates: Is this specific field subscribed by any UI component?
       │         │
       │         ├──► NO: Zero React Reconciliation! (CPU Cycles = ~0ms)
       │         │
       │         └──► YES (e.g., Error Message / Dependent Field):
       │                    │
       │                    ▼
       │              [Trigger Micro-render via Custom Subject/Proxy only on Subscriber]
       ▼
[Update Internal Form Values Ref]
```

Kompleksitas render ditekan menjadi $O(k)$ di mana $k$ adalah jumlah observer yang secara eksplisit melakukan *subscribe* ke field tertentu tersebut via proxy (sering kali $k = 0$ untuk input teks standar).

#### 3.2. Proxy and Path Resolution Engine
Untuk dynamic nested forms, path string seperti `"organization.members[3].security.roles"` harus diakses dan diubah secara instan tanpa melakukan parsing string runtime berulang kali. RHF dan schema resolver enterprise memanfaatkan representasi *Trie-based path parsing* atau regex-minified path-resolver yang melakukan resolusi pointer referensi langsung pada internal state graph:

$$\text{Address}(O, \text{Path}) = \Pi_{i=0}^{n} \text{Traverse}(O, K_i)$$

di mana setiap komponen array `$K_i$` dikonfigurasi melalui internal pointer arrays, menjaga immutability hanya ketika snapshot diperlukan untuk serialisasi validasi.

#### 3.3. Asynchronous Validation Pipeline Concurrency
Validasi asynchronous (seperti pengecekan ketersediaan Tax ID, duplikasi IBAN) menimbulkan masalah *race condition*. Jika user mengetik string `"ID-123"`, lalu dengan cepat mengubahnya menjadi `"ID-124"`, respon validasi untuk `"ID-123"` bisa kembali setelah respon `"ID-124"`. 

Arsitektur produksi mewajibkan integrasi `AbortController` terotomatisasi di level schema/resolver untuk membatalkan sinyal HTTP in-flight saat value berubah sebelum promise terselesaikan:

```
Request 1 ("ID-123") ────► [Pending] ──x (Aborted via signal.abort())
Request 2 ("ID-124") ─────────────► [Pending] ──► [HTTP 200: Valid] ──► Update UI
```

---

### 4. Why & What

| Fitur / Pola | Controlled Architecture (Native React) | Subscription/Proxy Architecture (RHF + Zod) | Mengapa Diperlukan di Enterprise? |
| :--- | :--- | :--- | :--- |
| **State Storage** | React State Fiber Node | Native DOM Engine + Internal Ref Map | Mencegah frame drops saat form berskala besar (>100 fields). |
| **Re-render Scope** | Seluruh Form Component & turunannya | Terisolasi per field subscriber (`useWatch`, `Controller`) | Mempertahankan batas 60fps (16.6ms frame budget) pada device berspesifikasi rendah. |
| **Schema Validation Engine** | Manual validation logic per-handler | Externalized Runtime Validation Schema (Zod/Valibot) | Decoupling aturan bisnis dari layer UI presentation; single source of truth. |
| **Server Synchronization** | Manual `fetch` + manual error parsing | TanStack Query Cache + Deterministic Rollback | Mengeliminasi inkonsistensi cache lokal dan memitigasi latensi jaringan dengan Optimistic UI. |

---

### 5. How (Workflow Detail)

Arsitektur form enterprise terbagi ke dalam 5 layer yang terisolasi secara fungsional:

```
[ Presentation Layer (UI Components: Inputs, FieldArrays, Steppers) ]
                                 │
                                 ▼
       [ Validation Engine (Zod Schema Pipeline + Dynamic Resolvers) ]
                                 │
                                 ▼
     [ Core Form Store (React Hook Form Controller Registry & Proxy) ]
                                 │
                                 ▼
   [ Mutation Layer (TanStack Query v5 optimistic Mutation Pipeline) ]
                                 │
                                 ▼
         [ Transport Layer (HTTP/2, AbortController, Server API) ]
```

#### Langkah-langkah Pemrosesan Mutasi Terintegrasi:
1. **User Action**: Form submission dipicu (`onSubmit`).
2. **Schema Interception**: Registry data diekstraksi ke plain object, dilempar ke Zod parse engine secara asinkron.
3. **Branching Evaluation**: Jika skema validasi conditional mendeteksi field dependensi (misal: `isCorporateAccount = true`), sub-skema turunan diinjeksikan secara dinamis.
4. **Optimistic Payload Construction**: TanStack Query mengintersepsi submit, membatalkan semua query refetch in-flight untuk entity yang dituju, mengambil snapshot cache saat ini, dan melakukan *in-place patching* ke cache secara sinkron.
5. **Network Dispatch**: Payload dikirim via HTTP POST/PUT/PATCH bersamaan dengan upload progress event listener jika terdapat binary attachment.
6. **Reconciliation & Finalization**: 
   * Jika sukses: Cache di-*settle* dengan ID definitif dari server, trigger notification.
   * Jika gagal: Tangkap error envelope, eksekusi pemulihan data dari snapshot rollback, dan petakan *server validation errors* kembali ke form field spesifik melalui RHF `setError()`.

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Bayangkan **Controlled Form Tradisional** seperti **Sistem Rapat Paripurna**: Setiap kali seorang anggota parlemen (input field) mengubah satu kata dalam rancangan undang-undang, seluruh anggota rapat di gedung (seluruh pohon komponen) harus berhenti, mendengarkan perubahan tersebut, dan menandatangani ulang draft dari awal.

Sebaliknya, **Observer-Based Subscription System** adalah **Bursa Saham Modern**: Para pialang (input field) memperbarui order book mereka secara langsung di terminal lokal (DOM node). Layar monitor besar (UI) hanya memperbarui satu baris angka tertentu yang mengalami fluktuasi harga jika ada penonton yang secara spesifik memesan alarm (*subscription*) untuk saham tersebut.

```
       TRADISIONAL (CONTROLLED)                 OBSERVER PROXY (ENTERPRISE)
       
      +------------------------+                +-------------------------+
      |      <FormRoot>        |                |       <FormRoot>        |
      |   (State: text="A")    |                | (Holds DOM Ref Registry)|
      +------------------------+                +-------------------------+
                   │                                         │
        [Every key stroke causes]                 [No Render on FormRoot]
        [re-render of everything]                            │
                   │                                         ▼
      +------------┴-----------+                      Native DOM Inputs
      ▼                        ▼                    [Input 1]   [Input 2]
+------------+           +------------+                 │           │
| <Input A>  |           | <Input B>  |                 │           │
| Render: OK |           | Render: OK |                 ▼           │
+------------+           +------------+          (Local Event)      │
                                                        │           ▼
                                                        └───► [Isolated UI Watcher]
                                                              (Only this re-renders)
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengakses Uncontrolled Input dengan Zod & Micro-Render Control
Contoh ini mendemonstrasikan bagaimana mengisolasi render text input tanpa memicu re-render pada container form utama.

```tsx
import React from 'react';
import { useForm, useWatch, Control } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

const simpleSchema = z.object({
  username: z.string().min(3, 'Username minimal 3 karakter'),
  realtimeCounter: z.string(),
});

type SimpleFormValues = z.infer<typeof simpleSchema>;

// Sub-komponen yang secara independen melakukan subscribe ke field "username"
function CharacterCountDisplay({ control }: { control: Control<SimpleFormValues> }) {
  const username = useWatch({
    control,
    name: 'username',
    defaultValue: '',
  });

  return (
    <div style={{ fontSize: '0.8rem', color: username.length > 10 ? 'red' : 'gray' }}>
      Karakter: {username.length} / 10
    </div>
  );
}

export function SimpleIsolatedForm() {
  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<SimpleFormValues>({
    resolver: zodResolver(simpleSchema),
    defaultValues: {
      username: '',
      realtimeCounter: '',
    },
  });

  const onSubmit = (data: SimpleFormValues) => {
    console.log('Form Submitted Successfully:', data);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="p-4 space-y-4">
      <div>
        <label>Username (Monitored): </label>
        <input {...register('username')} className="border p-1" />
        <CharacterCountDisplay control={control} />
        {errors.username && <p className="text-red-500">{errors.username.message}</p>}
      </div>

      <div>
        <label>Counter Biasa (Unmonitored): </label>
        {/* Mengubah input ini tidak akan menyebabkan CharacterCountDisplay re-render */}
        <input {...register('realtimeCounter')} className="border p-1" />
      </div>

      <button type="submit" className="bg-blue-500 text-white px-4 py-2">Submit</button>
    </form>
  );
}
```

#### Practical Example: Production-Ready Dynamic Fiscal Underwriting Form
Implementasi form enterprise lengkap dengan nested dynamic array, validasi conditional, upload progress, dan optimistic mutation rollback menggunakan TanStack Query v5.

```tsx
import React, { useState } from 'react';
import {
  useForm,
  useFieldArray,
  Controller,
  SubmitHandler,
} from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import axios, { AxiosProgressEvent } from 'axios';

// ==========================================
// 1. DOMAIN SCHEMAS & TYPES
// ==========================================

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
const ACCEPTED_DOCUMENT_TYPES = ['application/pdf', 'image/png', 'image/jpeg'];

export const FacilityTypeEnum = z.enum(['REVOLVING_CREDIT', 'TERM_LOAN', 'LETTER_OF_CREDIT']);

export const dynamicFacilitySchema = z
  .object({
    facilityId: z.string().uuid(),
    facilityType: FacilityTypeEnum,
    requestedAmount: z.number().positive('Jumlah harus bernilai positif'),
    tenorMonths: z.number().min(1).max(360),
    requiresCollateral: z.boolean(),
    collateralDescription: z.string().optional(),
  })
  .superRefine((data, ctx) => {
    if (data.requiresCollateral && (!data.collateralDescription || data.collateralDescription.trim().length < 10)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['collateralDescription'],
        message: 'Deskripsi agunan wajib diisi minimal 10 karakter jika agunan disyaratkan.',
      });
    }
  });

export const corporateUnderwritingSchema = z.object({
  legalEntityName: z.string().min(3, 'Nama entitas legal wajib diisi'),
  taxIdentificationNumber: z
    .string()
    .regex(/^\d{2}\.\d{3}\.\d{3}\.\d{1}-\d{3}\.\d{3}$/, 'Format NPWP tidak valid (XX.XXX.XXX.X-XXX.XXX)'),
  facilities: z.array(dynamicFacilitySchema).min(1, 'Minimal ajukan satu fasilitas finansial'),
  auditReport: z
    .custom<File>((file) => file instanceof File, 'File laporan audit diperlukan')
    .refine((file) => file.size <= MAX_FILE_SIZE, 'Ukuran file maksimal adalah 5MB')
    .refine(
      (file) => ACCEPTED_DOCUMENT_TYPES.includes(file.type),
      'Hanya format PDF, PNG, atau JPEG yang didukung'
    ),
});

export type CorporateUnderwritingFormValues = z.infer<typeof corporateUnderwritingSchema>;

interface ApplicationEntity extends Omit<CorporateUnderwritingFormValues, 'auditReport'> {
  id: string;
  auditReportUrl: string;
  submissionStatus: 'PENDING' | 'APPROVED' | 'REJECTED';
}

// ==========================================
// 2. NETWORK MUTATION ENGINE
// ==========================================

async function submitUnderwritingApplication(
  payload: CorporateUnderwritingFormValues,
  onUploadProgress?: (progressEvent: AxiosProgressEvent) => void
): Promise<ApplicationEntity> {
  const formData = new FormData();
  formData.append('legalEntityName', payload.legalEntityName);
  formData.append('taxIdentificationNumber', payload.taxIdentificationNumber);
  formData.append('facilities', JSON.stringify(payload.facilities));
  formData.append('auditReport', payload.auditReport);

  const response = await axios.post<ApplicationEntity>('/api/v1/underwriting/apply', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress,
  });

  return response.data;
}

// ==========================================
// 3. ENTERPRISE FORM COMPONENT
// ==========================================

export function EnterpriseUnderwritingEngine() {
  const queryClient = useQueryClient();
  const [uploadPercent, setUploadPercent] = useState<number>(0);

  const {
    register,
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<CorporateUnderwritingFormValues>({
    resolver: zodResolver(corporateUnderwritingSchema),
    defaultValues: {
      legalEntityName: '',
      taxIdentificationNumber: '',
      facilities: [
        {
          facilityId: crypto.randomUUID(),
          facilityType: 'REVOLVING_CREDIT',
          requestedAmount: 100000000,
          tenorMonths: 12,
          requiresCollateral: false,
          collateralDescription: '',
        },
      ],
    },
    mode: 'onBlur', // Optimalkan performa validasi runtime
  });

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'facilities',
    keyName: '_clientAssignedId', // Menghindari modifikasi deep object properties
  });

  // Mutasi dengan Optimistic UI dan Error Rollback Snapshot
  const underwritingMutation = useMutation({
    mutationFn: (variables: CorporateUnderwritingFormValues) =>
      submitUnderwritingApplication(variables, (progressEvent) => {
        const percent = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1));
        setUploadPercent(percent);
      }),
    onMutate: async (newApplication) => {
      // 1. Batalkan queries yang sedang berjalan untuk menghindari race condition
      await queryClient.cancelQueries({ queryKey: ['underwriting-applications'] });

      // 2. Snapshot state saat ini untuk rollback
      const previousApplications = queryClient.getQueryData<ApplicationEntity[]>(['underwriting-applications']);

      // 3. Buat optimistic representation
      const optimisticEntity: ApplicationEntity = {
        id: `temp-client-id-${Date.now()}`,
        legalEntityName: newApplication.legalEntityName,
        taxIdentificationNumber: newApplication.taxIdentificationNumber,
        facilities: newApplication.facilities,
        auditReportUrl: URL.createObjectURL(newApplication.auditReport),
        submissionStatus: 'PENDING',
      };

      // 4. Update cache TanStack Query secara optimistik
      queryClient.setQueryData<ApplicationEntity[]>(['underwriting-applications'], (old = []) => [
        ...old,
        optimisticEntity,
      ]);

      return { previousApplications };
    },
    onError: (err, newApplication, context) => {
      // Kembalikan cache ke state snapshot saat eksekusi mutasi gagal
      if (context?.previousApplications) {
        queryClient.setQueryData(['underwriting-applications'], context.previousApplications);
      }
      alert(`Mutasi data underwriting gagal: ${err.message}`);
    },
    onSettled: () => {
      setUploadPercent(0);
      // Invalidation untuk memastikan sinkronisasi absolut dengan database
      queryClient.invalidateQueries({ queryKey: ['underwriting-applications'] });
    },
    onSuccess: () => {
      reset();
    },
  });

  const processFormSubmission: SubmitHandler<CorporateUnderwritingFormValues> = (formData) => {
    underwritingMutation.mutate(formData);
  };

  return (
    <div className="max-w-4xl mx-auto p-6 bg-white rounded-lg shadow-md">
      <h1 className="text-2xl font-bold border-b pb-4 mb-6">Aplikasi Corporate Underwriting</h1>

      <form onSubmit={handleSubmit(processFormSubmission)} noValidate className="space-y-6">
        {/* Legal Identity Section */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Nama Entitas Legal</label>
            <input
              type="text"
              {...register('legalEntityName')}
              className="mt-1 block w-full border rounded-md p-2 border-gray-300"
              placeholder="PT Contoh Sukses Bersama"
            />
            {errors.legalEntityName && (
              <p className="mt-1 text-sm text-red-600">{errors.legalEntityName.message}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">NPWP Perusahaan</label>
            <input
              type="text"
              {...register('taxIdentificationNumber')}
              className="mt-1 block w-full border rounded-md p-2 border-gray-300"
              placeholder="01.234.567.8-901.000"
            />
            {errors.taxIdentificationNumber && (
              <p className="mt-1 text-sm text-red-600">{errors.taxIdentificationNumber.message}</p>
            )}
          </div>
        </div>

        {/* Dynamic Nested Facility Section */}
        <div className="border-t pt-4">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold">Struktur Fasilitas Finansial</h2>
            <button
              type="button"
              onClick={() =>
                append({
                  facilityId: crypto.randomUUID(),
                  facilityType: 'TERM_LOAN',
                  requestedAmount: 50000000,
                  tenorMonths: 24,
                  requiresCollateral: false,
                  collateralDescription: '',
                })
              }
              className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
            >
              + Tambah Fasilitas
            </button>
          </div>

          {fields.map((fieldItem, index) => (
            <div
              key={fieldItem._clientAssignedId}
              className="p-4 mb-4 border border-gray-200 rounded-md bg-gray-50 space-y-4"
            >
              <div className="flex justify-between items-center">
                <span className="font-semibold text-sm">Fasilitas #{index + 1}</span>
                {fields.length > 1 && (
                  <button
                    type="button"
                    onClick={() => remove(index)}
                    className="text-red-600 hover:text-red-800 text-sm"
                  >
                    Hapus
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700">Tipe Fasilitas</label>
                  <select
                    {...register(`facilities.${index}.facilityType`)}
                    className="mt-1 block w-full border rounded p-2 bg-white"
                  >
                    <option value="REVOLVING_CREDIT">Revolving Credit</option>
                    <option value="TERM_LOAN">Term Loan</option>
                    <option value="LETTER_OF_CREDIT">Letter of Credit</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700">Limit Diminta (IDR)</label>
                  <input
                    type="number"
                    {...register(`facilities.${index}.requestedAmount`, { valueAsNumber: true })}
                    className="mt-1 block w-full border rounded p-2"
                  />
                  {errors.facilities?.[index]?.requestedAmount && (
                    <p className="text-xs text-red-600 mt-1">
                      {errors.facilities[index]?.requestedAmount?.message}
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700">Tenor (Bulan)</label>
                  <input
                    type="number"
                    {...register(`facilities.${index}.tenorMonths`, { valueAsNumber: true })}
                    className="mt-1 block w-full border rounded p-2"
                  />
                </div>
              </div>

              {/* Conditional Form Logic Micro-Subtree */}
              <div className="pt-2">
                <label className="inline-flex items-center">
                  <input
                    type="checkbox"
                    {...register(`facilities.${index}.requiresCollateral`)}
                    className="rounded border-gray-300 text-indigo-600"
                  />
                  <span className="ml-2 text-sm text-gray-600">Sertakan Agunan Tambahan</span>
                </label>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700">Deskripsi Agunan</label>
                <input
                  type="text"
                  {...register(`facilities.${index}.collateralDescription`)}
                  placeholder="Sertifikat Tanah No. ..., Deposito Bilyet ..."
                  className="mt-1 block w-full border rounded p-2 bg-white"
                />
                {errors.facilities?.[index]?.collateralDescription && (
                  <p className="text-xs text-red-600 mt-1">
                    {errors.facilities[index]?.collateralDescription?.message}
                  </p>
                )}
              </div>
            </div>
          ))}
          {errors.facilities?.root && (
            <p className="text-sm text-red-600">{errors.facilities.root.message}</p>
          )}
        </div>

        {/* Binary Multipart Section */}
        <div className="border-t pt-4">
          <label className="block text-sm font-medium text-gray-700">Laporan Keuangan Diaudit (PDF/PNG)</label>
          <Controller
            control={control}
            name="auditReport"
            render={({ field: { onChange, ref } }) => (
              <input
                type="file"
                ref={ref}
                accept=".pdf,.png,.jpg,.jpeg"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) onChange(file);
                }}
                className="mt-2 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              />
            )}
          />
          {errors.auditReport && (
            <p className="mt-1 text-sm text-red-600">{errors.auditReport.message}</p>
          )}
        </div>

        {/* Upload Progress Indicator */}
        {uploadPercent > 0 && (
          <div className="w-full bg-gray-200 rounded-full h-2.5">
            <div
              className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
              style={{ width: `${uploadPercent}%` }}
            />
            <span className="text-xs text-gray-500 mt-1 block">Uploading: {uploadPercent}%</span>
          </div>
        )}

        {/* Submit Execution */}
        <div className="flex justify-end pt-4 border-t">
          <button
            type="submit"
            disabled={isSubmitting || underwritingMutation.isPending}
            className="px-6 py-2 bg-indigo-600 text-white font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            {underwritingMutation.isPending ? 'Memproses Pengajuan...' : 'Kirim Pengajuan Underwriting'}
          </button>
        </div>
      </form>
    </div>
  );
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Platform: *Global Multi-Tier Merchant Settlement Engine*.  
Skala: Form onboarding pedagang lintas negara dengan 140 input field, mencakup KYC berlapis, identifikasi beneficial ownership (UBO) dinamis tak terbatas, verifikasi IBAN/SWIFT asinkron, dan auto-save state terenkripsi.

#### Problem Statement
1. **CPU Choke & Input Lag**: Penggunaan library state standar (`Formik` berbasis React State) menyebabkan keystroke latency melonjak hingga 180ms saat array pemegang saham (UBO) melebihi 10 entitas. Batas responsivitas UI 60fps terlampaui drastis.
2. **Loss of In-flight Drafts**: Refresh tidak disengaja menyebabkan user enterprise kehilangan progress onboarding berdurasi ~45 menit.
3. **Double Submission & Split Ingestion**: Koneksi seluler tidak stabil menyebabkan kegagalan parsial submission pada multi-part form, memicu duplikasi data di core ledger.

#### Arsitektur Solusi Terapan
```
[ User Keystroke ]
        │
        ▼
[ RHF Native Refs ] ──► (No Re-render)
        │
        ├─► [Web Worker (Zod Background Compiler)]
        │         │
        │         ▼
        │   Validates deep node concurrency without blocking Main Thread
        │
        ├─► [IndexedDB Local Engine (via idb-keyval)]
        │         │
        │         ▼ (Debounced: 500ms)
        │   Encrypted Draft Pipeline (AES-GCM via WebCrypto API)
        │
        ▼
[ Form Submission via Mutation Orchestrator ]
        │
        ├──► Generate Idempotency-Key (UUID v4)
        ├──► TanStack Query Snapshot Cache
        └──► Streaming Chunked Upload via Axios + Progress Tracker
```

#### Hasil Metrik Rekayasa (Sebelum vs. Sesudah)
*   **Keystroke Execution Latency**: Turun dari $180\text{ ms}$ (Controlled) ke $3.2\text{ ms}$ (Observer Proxy).
*   **Memory Footprint per Session**: Berkurang 62% karena penurunan alokasi anonymous function handler di JSX render loop.
*   **Draft Recovery Rate**: 99.98% terselamatkan saat tab browser crash melalui background IndexedDB hydration.

---

### 9. Trade-offs (Analisis Arsitektur)

| Dimensi | Controlled Native Form Tree | Uncontrolled Observer Pattern (RHF) | Redux/Zustand Synchronized Form State |
| :--- | :--- | :--- | :--- |
| **Performance Overhead** | Buruk: $O(N)$ re-render di setiap event input. Memerlukan manual memoization via `useMemo`/`useCallback`. | Optimal: $O(1)$ re-render. State diperbarui di level node DOM C++ engine. | Sedang-Tinggi: Memerlukan selector memoization (`shallow`) untuk memitigasi broad re-renders. |
| **Latency Toleransi** | Rendah: Keystroke latency bertambah secara linear mengikuti ukuran DOM node. | Sangat Tinggi: Zero frame dropped pada form dengan >1000 input fields. | Menengah: Tergantung middleware payload processing overhead. |
| **Scalability & Code Complexity** | Sederhana di awal, namun sulit dimaintain pada skala enterprise karena prop drilling atau context hell. | Kurva belajar menengah: Pemahaman mutasi refs, schema resolvers, dan transient subscriptions via `useWatch`. | Kompleks: Boilerplate action types, reducers, payload serializability requirements. |
| **Edge-case Debuggability** | Sangat Mudah: React DevTools langsung menginspeksi state tree di setiap titik waktu. | Menengah: State tersimpan di internal ref variables; memerlukan library specialized devtools. | Mudah: Time-travel debugging bawaan Redux/Zustand devtools. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Memory Leak Akibat Penyimpanan File Object pada Persistent Storage
*   *Kesalahan*: Menyimpan instance `File` atau `Blob` langsung ke dalam `localStorage` atau cache TanStack Query tanpa serialisasi, atau membuat Object URL via `URL.createObjectURL(file)` tanpa mengeksekusi `URL.revokeObjectURL(url)`.
*   *Dampak*: Browser tab mengalami alokasi memori heap yang terus membengkak (*out-of-memory crash*).
*   *Solusi*: Implementasikan pembersihan siklus hidup URL di `useEffect` cleanup hook:
    ```tsx
    useEffect(() => {
      const objectUrl = URL.createObjectURL(file);
      setPreview(objectUrl);
      return () => {
        URL.revokeObjectURL(objectUrl); // Release native memory reference
      };
    }, [file]);
    ```

#### 10.2. Kehilangan Focus & Input De-synchronization pada Dynamic Field Arrays
*   *Kesalahan*: Menggunakan array index (`index`) sebagai React `key` attribute saat melakukan rendering item dari `useFieldArray`.
    ```tsx
    // ANTI-PATTERN
    {fields.map((field, index) => <input key={index} {...register(`items.${index}.name`)} />)}
    ```
*   *Dampak*: Saat item di tengah dihapus atau dipindahkan (`swap`/`move`), state internal DOM input tertukar antar elemen karena reconciliation React mencocokkan key berbasis posisi array statis.
*   *Solusi*: Selalu gunakan properti `id` unik yang diinjeksi oleh RHF:
    ```tsx
    // PRODUCTION STANDARD
    {fields.map((field, index) => <input key={field.id} {...register(`items.${index}.name`)} />)}
    ```

#### 10.3. Server State Sync Drift pada Optimistic Updates Tanpa Concurrency Locking
*   *Kesalahan*: Tidak membatalkan (*cancel*) queries in-flight saat mutasi optimistik dimulai via `queryClient.cancelQueries()`.
*   *Dampak*: Permintaan fetching query lambat yang dikirim sebelum eksekusi mutasi kembali setelah mutasi dimulai, menimpa (*overwrite*) cache optimistik dengan data usang (*stale data race condition*).

---

### 11. Best Practices (Production Checklist)

- [ ] **Decoupled Architecture**: Seluruh aturan validasi dideklarasikan secara eksternal via schema engine (Zod/Valibot), bukan di-hardcode di dalam JSX tag atribut `required`, `pattern`, dsb.
- [ ] **Sub-tree Isolation**: Gunakan sub-komponen terisolasi dengan hook `useWatch` atau `useFormContext` untuk bagian form yang membutuhkan re-render real-time, menjaga form root tetap bebas re-render.
- [ ] **Dynamic Array Invariance**: Hindari penyisipan default value bertipe *circular structure* ke dalam dynamic field array.
- [ ] **Idempotent Mutations**: Injeksi custom `Idempotency-Key` header (UUID v4) pada setiap mutasi kritis finansial untuk mencegah double-charge akibat retry jaringan otomatis.
- [ ] **Sanitization Pipeline**: Implementasikan pembersihan karakter non-printable, XSS script tags, dan sanitasi spasi sebelum validasi Zod dijalankan melalui schema transforms:
  ```typescript
  const sanitizedString = z.string().trim().transform((val) => DOMPurify.sanitize(val));
  ```
- [ ] **Strict Form Destruction Handling**: Set `shouldUnregister: false` jika mempertahankan state form wizard antarlangkah, atau simpan secara eksplisit ke centralized multi-step storage state.
- [ ] **Accessibility (a11y)**: Pastikan setiap error message terhubung dengan input terkait via atribut `aria-invalid={!!errors.field}` dan `aria-describedby="field-error-id"`.

---

### 12. Hands-on Practice

Buat dan simpan struktur project form engine ini di direktori `hands-on/m02/`.

#### Langkah 1: Inisialisasi Project dan Dependensi
Jalankan di terminal Anda:
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install react react-dom @hookform/resolvers react-hook-form zod @tanstack/react-query axios
npm install -D typescript @types/react @types/react-dom vite
```

#### Langkah 2: Buat Abortable Async Validator (`hands-on/m02/src/validators.ts`)
```typescript
// Implementasi pengecekan Tax ID asinkron dengan simulasi server delay & signal cancellation
export function verifyTaxIdUnique(taxId: string, signal?: AbortSignal): Promise<boolean> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      // Simulasi ID yang sudah terdaftar di database
      if (taxId === '00.000.000.0-000.000') {
        resolve(false);
      } else {
        resolve(true);
      }
    }, 1200);

    if (signal) {
      signal.addEventListener('abort', () => {
        clearTimeout(timer);
        reject(new DOMException('Validation aborted by user input', 'AbortError'));
      });
    }
  });
}
```

#### Langkah 3: Bangun Dynamic Resolver Multi-Step Wizard (`hands-on/m02/src/WizardEngine.tsx`)
```tsx
import React, { useState } from 'react';
import { useForm, FormProvider, useFormContext } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

const Step1Schema = z.object({
  fullName: z.string().min(2, 'Nama lengkap wajib diisi'),
  email: z.string().email('Alamat email invalid'),
});

const Step2Schema = z.object({
  companyRegistrationNumber: z.string().min(5, 'Nomor registrasi wajib valid'),
  employeeCount: z.number().min(1, 'Jumlah karyawan minimal 1'),
});

const WizardMasterSchema = Step1Schema.and(Step2Schema);
type WizardValues = z.infer<typeof WizardMasterSchema>;

function Step1View() {
  const { register, formState: { errors } } = useFormContext<WizardValues>();
  return (
    <div className="space-y-4">
      <h2 className="text-md font-bold">Langkah 1: Identitas Personal</h2>
      <input {...register('fullName')} placeholder="Nama Lengkap" className="border p-2 w-full block" />
      {errors.fullName && <p className="text-red-500 text-xs">{errors.fullName.message}</p>}

      <input {...register('email')} placeholder="Corporate Email" className="border p-2 w-full block" />
      {errors.email && <p className="text-red-500 text-xs">{errors.email.message}</p>}
    </div>
  );
}

function Step2View() {
  const { register, formState: { errors } } = useFormContext<WizardValues>();
  return (
    <div className="space-y-4">
      <h2 className="text-md font-bold">Langkah 2: Data Perusahaan</h2>
      <input {...register('companyRegistrationNumber')} placeholder="No. Registrasi" className="border p-2 w-full block" />
      {errors.companyRegistrationNumber && <p className="text-red-500 text-xs">{errors.companyRegistrationNumber.message}</p>}

      <input 
        type="number" 
        {...register('employeeCount', { valueAsNumber: true })} 
        placeholder="Jumlah Pegawai" 
        className="border p-2 w-full block" 
      />
      {errors.employeeCount && <p className="text-red-500 text-xs">{errors.employeeCount.message}</p>}
    </div>
  );
}

export function MultiStepWizard() {
  const [currentStep, setCurrentStep] = useState<number>(0);
  const stepsSchemas = [Step1Schema, Step2Schema];

  const methods = useForm<WizardValues>({
    resolver: zodResolver(stepsSchemas[currentStep]),
    mode: 'onBlur',
    defaultValues: {
      fullName: '',
      email: '',
      companyRegistrationNumber: '',
      employeeCount: 1,
    }
  });

  const isLastStep = currentStep === stepsSchemas.length - 1;

  const handleNextStep = async () => {
    // Validasi hanya field untuk step aktif saat ini
    const isStepValid = await methods.trigger();
    if (isStepValid) {
      if (!isLastStep) {
        setCurrentStep((prev) => prev + 1);
      } else {
        // Eksekusi submit akhir dengan validasi seluruh schema
        methods.handleSubmit((data) => {
          console.log('Final Wizard Ingestion Complete:', data);
          alert('Wizard Submitted Successfully');
        })();
      }
    }
  };

  const handlePreviousStep = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 0));
  };

  return (
    <FormProvider {...methods}>
      <div className="max-w-md mx-auto p-4 border rounded shadow">
        {currentStep === 0 && <Step1View />}
        {currentStep === 1 && <Step2View />}

        <div className="flex justify-between mt-6">
          <button
            type="button"
            onClick={handlePreviousStep}
            disabled={currentStep === 0}
            className="px-4 py-1 bg-gray-300 disabled:opacity-50"
          >
            Kembali
          </button>
          <button
            type="button"
            onClick={handleNextStep}
            className="px-4 py-1 bg-blue-600 text-white"
          >
            {isLastStep ? 'Selesai & Kirim' : 'Lanjut'}
          </button>
        </div>
      </div>
    </FormProvider>
  );
}
```

---

### 13. Exercise

#### Level Easy
Tulis skema validasi Zod untuk registrasi akun yang memastikan:
*   `password`: minimal 8 karakter, mengandung setidaknya 1 angka dan 1 karakter spesial.
*   `confirmPassword`: bernilai identik dengan `password` via `.refine()`.
*   Tampilkan pesan error spesifik jika konfirmasi password tidak cocok langsung di bawah field konfirmasi password.

#### Level Medium
Buat custom React Hook bernama `useDebouncedAsyncValidation` yang mengintegrasikan validasi asinkron Zod dengan React Hook Form. Hook harus:
1. Menerima field name dan fungsi verifikasi API asinkron.
2. Membatalkan in-flight promise jika input baru dimasukkan dalam rentang delay 400ms menggunakan `AbortController`.
3. Mengatur status visual loading field (misal: spinner kecil) via localized state tanpa memicu render pada keseluruhan form.

#### Level Hard
Rancang komponen form tabel dinamis (*Grid Data Entry Form*) berkekuatan 500 baris. 
*   Masing-masing baris memiliki 5 input field: `sku`, `quantity`, `unitPrice`, `discountPercent`, dan `totalPrice` (derived value: `quantity * unitPrice * (1 - discountPercent / 100)`).
*   **Persyaratan Mutlak**: Perubahan nilai pada `quantity` pada baris ke-45 tidak boleh memicu rendering ulang baris ke-44 atau baris ke-46. Kalkulasi `totalPrice` baris ke-45 harus terjadi secara instan tanpa mendegradasi frame rate di bawah 60 FPS. Gunakan kombinasi `useFieldArray`, memoized row components, dan RHF native dynamic subscriptions.

---

### 14. Challenge

#### Skenario Kasus: Dynamic Architectural Rule-Set Engine
Sebuah konglomerasi logistik maritim internasional memerlukan sistem pembuatan dokumen *Customs Declaration Manifest* lintas batas negara. Kebutuhan arsitektur:

1. **Graph-Driven Dependency Matrix**:
   * Jika pelabuhan asal (`originPort`) berada di Uni Eropa dan pelabuhan tujuan (`destinationPort`) di non-EU, suntikkan sekumpulan sub-field wajib: `EORI_Number`, `Export_Declaration_MRN`, dan `DualUse_Goods_Verification`.
   * Jika komoditas yang dimuat di dalam dynamic array `cargoItems` memuat flag `isHazardous = true`, munculkan array baru `hazardDetails` yang memiliki validasi bertingkat ke regulasi UN Hazardous Material Code.

2. **Offline-Resilient Idempotent Mutation Engine**:
   * Form harus beroperasi dalam kondisi internet kapal laut yang sering terputus (*flaky connection*).
   * Validasi skema harus tetap bekerja secara lokal offline.
   * State mutasi harus dimasukkan ke dalam antrean lokal berbasis IndexedDB jika jaringan terputus (`navigator.onLine === false`).
   * Ketika koneksi tersambung kembali, seluruh antrean mutasi harus dikirimkan secara sekuensial dengan payload *delta-changes* (hanya mengirim properti yang ditandai `isDirty`), menggunakan single-flight idempotency signature untuk mencegah duplikasi pemrosesan oleh backend ledger.

3. **Deliverables Arsitektur**:
   * Definisikan struktur Type System TypeScript secara hierarkis (menggunakan Union Types terdiskriminasi untuk membedakan kategori deklarasi pelabuhan).
   * Implementasikan Zod schema dengan recursive dynamic refinement.
   * Buat custom React Query mutator interceptor yang menangani transisi offline-to-online reconciliation.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Mengapa React Hook Form memberikan performa render yang jauh lebih tinggi dibanding pendekatan Formik standar?**
   * *Jawaban*: RHF memanfaatkan arsitektur *uncontrolled form* yang mengandalkan mutable DOM references (`ref`). Alih-alih memicu siklus render reconciler React di setiap perubahan event keyboard melalui `useState`, RHF mengisolasi event di tingkat native DOM dan hanya memicu *micro-render* secara spesifik pada komponen yang secara eksplisit mendaftar (*subscribe*) ke perubahan state tersebut.

2. **Apa peran dari metode `superRefine()` pada Zod schema dibanding `refine()` standar?**
   * *Jawaban*: `superRefine()` memberikan kontrol imperatif penuh terhadap pembuatan error issues (`ctx.addIssue`). Ini memungkinkan penambahan beberapa error issue sekaligus pada path-path field yang berbeda di dalam satu traversal validasi objek komposit, sedangkan `refine()` standar umumnya hanya menghasilkan single boolean evaluation untuk satu path target.

3. **Mengapa attribute `key` pada rendering `useFieldArray` tidak boleh menggunakan variable `index` dari pemetaan `.map()`?**
   * *Jawaban*: Jika menggunakan array `index`, saat sebuah item di posisi tengah dihapus, disisipkan, atau diubah urutannya, algoritma Virtual DOM Diffing React mencocokkan node lama dan baru berdasarkan index yang identik. Hal ini menyebabkan status input tak terkontrol (uncontrolled values), internal state elemen DOM, dan input focus berpindah ke elemen yang salah. Key harus selalu menggunakan unique persistent identifier (misal: `field.id`).

4. **Bagaimana cara mencegah default form submit browser me-refresh seluruh halaman web di React?**
   * *Jawaban*: Memanggil method `event.preventDefault()` pada handler submit native DOM, atau membungkus function submit melalui abstraction helper seperti `handleSubmit` milik React Hook Form yang secara otomatis mengeksekusi `e.preventDefault()`.

5. **Apa fungsi dari method `reset()` pada React Hook Form?**
   * *Jawaban*: Menghapus nilai form yang ada di internal registry dan native DOM inputs, membersihkan seluruh state validation errors, serta menyetel ulang flag `isDirty`, `touchedFields`, dan `isSubmitted` kembali ke initial `defaultValues` yang didefinisikan.

#### Intermediate (5 Pertanyaan)
6. **Pada skenario optimistik TanStack Query v5, mengapa pemanggilan `await queryClient.cancelQueries()` di dalam `onMutate` wajib dieksekusi sebelum melakukan `queryClient.setQueryData()`?**
   * *Jawaban*: Untuk menghentikan proses fetch/refetch queries in-flight yang sedang berjalan di jaringan sebelum mutasi optimistik dilakukan. Jika tidak dihentikan, respons fetch lama yang membawa data sebelum mutasi dapat tiba beberapa milidetik setelah mutasi optimistik, menimpa update optimistik di cache (*cache clobbering / race condition*).

7. **Bagaimana arsitektur Zod menangani isolasi transformasi tipe runtime data input HTML native yang secara natural selalu bertipe string?**
   * *Jawaban*: Menggunakan modifier pipeline seperti `z.preprocess()` atau chaining `.transform()` dan `.pipe()`, serta memanfaatkan integrasi RHF native registration casting seperti `{ valueAsNumber: true }` atau `{ valueAsDate: true }` yang mengonversi string native DOM input menjadi tipe data yang sesuai sebelum parsing schema dijalankan.

8. **Apa perbedaan mendasar antara method `watch()` dan hook `useWatch()` pada React Hook Form?**
   * *Jawaban*: `watch()` menyebabkan root component (atau komponen tempat hook diinisialisasi) melakukan re-render di setiap perubahan nilai field yang diamati. Sedangkan `useWatch()` mengisolasi langganan (subscription) tersebut ke level custom hook pada sub-komponen terpisah, sehingga perubahan nilai tidak memicu re-render pada parent component tree.

9. **Bagaimana cara memetakan server validation error envelope (misal: `422 Unprocessable Entity`) kembali ke field error state spesifik pada React Hook Form?**
   * *Jawaban*: Mengiterasi payload error dari response server di dalam blok `onError` mutasi, lalu memanggil fungsi `setError('namaField' as Path<T>, { type: 'server', message: err.message })` milik RHF untuk menginjeksi error ke masing-masing field registry.

10. **Apa implikasi performa dari penyetelan opsi `mode: 'onChange'` pada form berskala enterprise di React Hook Form?**
    * *Jawaban*: Mengaktifkan validasi schema komprehensif pada setiap ketukan keyboard (*keystroke*). Pada form kompleks yang menggunakan Zod resolver besar, hal ini dapat meningkatkan beban pemrosesan CPU thread utama secara eksponensial. Disarankan untuk menggunakan `mode: 'onBlur'` atau `mode: 'onSubmit'` demi efisiensi render thread.

#### Production Scenarios (3 Skenario Kasus)
11. **Skenario 1**: Tim Anda merilis wizard multi-step form. Pengguna mengeluhkan bahwa saat mereka kembali ke Step 1 dari Step 2, nilai yang sebelumnya telah mereka isi hilang secara total. Kode form me-render step secara kondisional menggunakan `{currentStep === 1 && <StepOne />}`. Apa akar masalah arsitekturalnya dan bagaimana solusinya?
    * *Analisis & Solusi*: 
      * *Root Cause*: Secara default, saat komponen input unmount dari Virtual DOM tree, React Hook Form menjalankan mekanisme unregistration untuk menghemat memori, menghapus referensi field dari form registry internal.
      * *Solusi*: Atur opsi form initialization `shouldUnregister: false` pada `useForm({ shouldUnregister: false })`, atau sembunyikan UI komponen yang tidak aktif menggunakan representasi CSS (`display: none` / hidden visibility) alih-alih melepaskan komponen dari DOM tree, atau sinkronisasikan state antar-step ke state store eksternal (Persistent Zustand / Context).

12. **Skenario 2**: Sistem portal trading sering menerima komplain dari nasabah dengan koneksi buruk: setelah menekan tombol "Eksekusi Order", transaksi terpotong dua kali di server. Tombol submit sebenarnya sudah diatur `disabled={isSubmitting}`. Mengapa tombol disabled masih gagal mencegah masalah ini dan bagaimana penanganan tingkat produksinya?
    * *Analisis & Solusi*:
      * *Root Cause*: Pemicu ganda bisa terjadi jika user melakukan double-click sangat cepat sebelum state re-render `isSubmitting` sempat dikomit ke native DOM oleh React runtime scheduler, atau terjadi retry otomatis oleh layer HTTP client/service worker pada level network saat response pertama mengalami timeout.
      * *Solusi*:
        1. Di layer UI: Gunakan sinkronisasi native ref flag langsung (`isLockedRef.current = true`) yang dieksekusi secara instan sebelum pemanggilan promise async apa pun.
        2. Di layer Transport: Generate cryptographic client-side unique key (*Idempotency Key*, misalnya UUID v4) per sesi pembuatan formulir dan kirimkan di HTTP Request Header (`Idempotency-Key: uuid`). Backend engine wajib menolak atau mengembalikan respons cache yang sama jika request dengan key tersebut telah diproses sebelumnya.

13. **Skenario 3**: Sebuah form upload dokumen enterprise memvalidasi ekstensi file menggunakan Zod: `z.instanceof(File).refine(f => f.name.endsWith('.pdf'))`. Namun, sistem security audit mendapati pengguna dapat mengunggah file executable `.exe` berbahaya yang hanya di-rename menjadi `.pdf`. Bagaimana memperbaikinya pada layer frontend sebelum binary streaming dispatch dikirim?
    * *Analisis & Solusi*:
      * *Root Cause*: Pengecekan nama ekstensi string dan `file.type` (MIME-type browser) sepenuhnya bergantung pada sistem operasi lokal user dan sangat mudah dimanipulasi (*trivial spoofing*).
      * *Solusi*: Baca *Magic Numbers* (byte signature heksadesimal) langsung dari binary array buffer file menggunakan FileReader API/Blob slicing pada custom Zod async refinement:
        ```typescript
        const isValidPdfBuffer = async (file: File): Promise<boolean> => {
          const slice = file.slice(0, 4);
          const buffer = await slice.arrayBuffer();
          const view = new Uint8Array(buffer);
          // Magic number PDF: 25 50 44 46 (%PDF)
          return (
            view[0] === 0x25 &&
            view[1] === 0x50 &&
            view[2] === 0x44 &&
            view[3] === 0x46
          );
        };
        ```

---

### 16. Summary

*   Arsitektur form enterprise memisahkan manipulasi state DOM dari siklus render React via *uncontrolled observer pattern*, membatasi kompleksitas komputasi rendering pada tingkat $O(1)$.
*   Validasi schema-first (menggunakan Zod) bertindak sebagai layer pertahanan tipe runtime mandiri yang menjamin sanitasi dan integritas data payload sebelum menyentuh transport layer jaringan.
*   Orkestrasi mutasi data enterprise mewajibkan integrasi *Optimistic UI updates* yang resilient dengan kapabilitas snapshot rollback terotomatisasi serta pencegahan network race condition via pembatalan query in-flight.
*   Isolasi micro-rendering menggunakan selective subscription hook (`useWatch`, `Controller`) adalah strategi mutlak untuk menjaga budget performa responsivitas 60 FPS pada aplikasi modern berskala masif.