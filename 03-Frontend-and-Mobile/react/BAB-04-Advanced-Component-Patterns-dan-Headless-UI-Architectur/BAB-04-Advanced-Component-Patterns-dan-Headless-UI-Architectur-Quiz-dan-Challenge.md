# BAB-04-Advanced-Component-Patterns-dan-Headless-UI-Architectur: Quiz, Challenge, & Knowledge Check

Selamat datang di lembar evaluasi mandiri BAB-04. Dokumen ini dirancang untuk menguji penguasaan konseptual, kemampuan arsitektur komponen React tingkat lanjut, penerapan pola Headless UI, serta pemecahan masalah skala produksi berstandar enterprise.

---

## I. Basic Questions (5 Soal Pilihan Ganda & Konseptual)

### Soal 1: Filosofi Compound Components Pattern
**Pertanyaan:**
Apa tujuan mendasar penggunaan *Compound Components Pattern* dibandingkan pendekatan *Configuration Object / Prop-drilling* pada komponen UI kompleks seperti Tabs, Select, atau Accordion?

- A. Mengurangi bundle size JavaScript secara otomatis melalui static tree-shaking compiler.
- B. Memberikan fleksibilitas layout deklaratif kepada consumer dan mengeliminasi prop-drilling melalui pembagian implicit state internal (biasanya via React Context).
- C. Mencegah seluruh re-render komponen anak saat terjadi perubahan state pada parent component.
- D. Mengubah komponen React menjadi Web Component standar yang independen dari runtime React.

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Jawaban: B**

**Pembahasan:**
Compound Components membagi state internal antar elemen komponen secara implisit melalui React Context atau cloneElement, sehingga consumer bebas menyusun hierarki visual (`<Tabs.List>`, `<Tabs.Trigger>`, `<Tabs.Content>`) tanpa harus mengoper props berulang kali (*prop drilling*) atau mengunci struktur UI dalam *configuration array/object* yang kaku. Pilihan A salah karena compound component tidak secara intrinsik mengurangi bundle size. Pilihan C salah karena Context API default justru memicu re-render pada seluruh subscriber context jika tidak dioptimasi. Pilihan D salah karena polanya tetap berada dalam ekosistem React.
</details>

---

### Soal 2: Karakteristik Headless UI
**Pertanyaan:**
Manakah pernyataan berikut yang paling tepat mendefinisikan arsitektur **Headless UI** (seperti Radix UI, TanStack Table, Downshift, atau React Aria)?

- A. Library UI yang hanya berjalan di server (Node.js/Bun) tanpa rendering DOM di browser.
- B. Library yang menyediakan fungsionalitas logika state, state transitions, keyboard navigation, dan atribut ARIA accessibility tanpa menyertakan styling visual bawaan (CSS/styling-agnostic).
- C. Framework komponen yang tidak memerlukan hooks atau state management apapun.
- D. UI library yang hanya bisa digunakan bersama Tailwind CSS.

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Jawaban: B**

**Pembahasan:**
Headless UI berfokus sepenuhnya pada *behavior*, *state management*, *event handling*, dan kepatuhan standar aksesibilitas (WAI-ARIA). Desain visual diserahkan sepenuhnya (100%) kepada consumer atau design system tim menggunakan metode styling apapun (Tailwind CSS, CSS Modules, Styled Components, Emotion, vanilla CSS).
</details>

---

### Soal 3: Inversion of Control melalui Render Props
**Pertanyaan:**
Perhatikan potongan kode berikut:

```tsx
<ListFilter items={products}>
  {(filteredProducts) => (
    <div className="grid grid-cols-3 gap-4">
      {filteredProducts.map((p) => (
        <ProductCard key={p.id} product={p} />
      ))}
    </div>
  )}
</ListFilter>
```

Prinsip rekayasa perangkat lunak apa yang paling dominan diterapkan pada pola di atas?

- A. Inversion of Control (IoC), di mana logika pemfilteran dikontrol oleh komponen `ListFilter`, namun kendali representasi rendering DOM diserahkan sepenuhnya ke consumer.
- B. Uncontrolled Form Architecture, karena tidak menggunakan `useState` pada parent.
- C. Higher-Order Component (HOC) static composition.
- D. Strict Dependency Injection via Service Locator.

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Jawaban: A**

**Pembahasan:**
Render Props (khususnya *children-as-a-function*) adalah bentuk nyata dari *Inversion of Control* (IoC) di level presentasi UI React. Komponen `ListFilter` membungkus kompleksitas logika algoritma pemfilteran state, namun mendelegasikan wewenang bagaimana data tersebut di-render ke consumer.
</details>

---

### Soal 4: State Reducer Pattern
**Pertanyaan:**
Kapan *State Reducer Pattern* (dipopulerkan oleh Kent C. Dodds) sebaiknya diimplementasikan pada custom headless hook atau komponen?

- A. Ketika aplikasi ingin menggantikan Redux Toolkit di seluruh level global state.
- B. Ketika pembuat library/komponen ingin memberikan hak kepada consumer untuk mengintersep, memodifikasi, atau membatalkan transisi state internal pada event/action tertentu tanpa perlu memecah (*eject*) komponen tersebut.
- C. Ketika komponen hanya memiliki satu boolean toggle sederhana.
- D. Ketika asynchronous API call perlu dibatalkan secara otomatis dengan AbortController.

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Jawaban: B**

**Pembahasan:**
State Reducer Pattern memungkinkan consumer mengoper fungsi `stateReducer(state, action)` custom ke komponen/hook. Consumer dapat memeriksa tipe action (misalnya `ToggleActionTypes.toggle`) dan membatasi perilaku default (contohnya: membatasi toggle maksimal 4 kali klik atau menolak perubahan state saat kondisi tertentu terpenuhi).
</details>

---

### Soal 5: WAI-ARIA pada Interaksi Modal/Dialog
**Pertanyaan:**
Dalam mengimplementasikan headless modal dialog dari nol (*scratch*), atribut aksesibilitas dan perilaku fokus keyboard manakah yang **wajib** dipenuhi menurut WAI-ARIA Authoring Practices Guide (APG)?

- A. Cukup menambahkan `aria-hidden="true"` pada elemen modal trigger.
- B. Menggunakan `role="dialog"` atau `role="alertdialog"`, `aria-modal="true"`, mengikat `aria-labelledby` ke ID judul dialog, serta menerapkan *Focus Trap* (fokus tab tidak boleh keluar dari dialog) dan tombol `Escape` untuk menutup dialog.
- C. Menonaktifkan seluruh event keyboard agar pengguna hanya bisa berinteraksi menggunakan mouse cursor.
- D. Mengharuskan `tabIndex={0}` pada setiap tag `<div>` di dalam modal.

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Jawaban: B**

**Pembahasan:**
WAI-ARIA APG menetapkan bahwa modal dialog harus memiliki `role="dialog"` atau `role="alertdialog"`, deklarasi modalitas melalui `aria-modal="true"`, penamaan yang diakses screen reader melalui `aria-labelledby` / `aria-describedby`, manajemen siklus hidup fokus (memindahkan fokus ke dalam modal saat dibuka, mengunci navigasi TAB di dalam modal via focus trap, dan mengembalikan fokus ke trigger button saat ditutup via keyboard Escape atau close button).
</details>

---

## II. Intermediate Questions (5 Soal Analisis & Implementasi)

### Soal 6: Prop Getters Pattern vs Plain Props Object
**Pertanyaan:**
Mengapa pola *Prop Getters* (seperti `getToggleProps()`) jauh lebih tangguh dan aman dibandingkan hanya mengembalikan objek plain props (seperti `{ onClick, ariaExpanded }`) dalam custom headless hooks?

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Pembahasan:**
Pada plain props object:
```tsx
const { buttonProps } = useToggle();
<button {...buttonProps} onClick={customHandler} />
```
Jika consumer mendefinisikan `onClick={customHandler}`, handler tersebut akan secara tidak sengaja menimpa (*override/shadow*) `onClick` internal yang disediakan oleh hook, memutus state internal hook.

Dengan *Prop Getters*:
```tsx
const { getButtonProps } = useToggle();
<button {...getButtonProps({ onClick: customHandler })} />
```
Fungsi getter menerapkan utilitas composition helper (seperti `callAllEventHandlers(internalHandler, customHandler)`). Fungsi ini menjalankan handler internal sekaligus handler consumer secara berurutan, serta memungkinkan consumer membatalkan action internal melalui `event.defaultPrevented`.
</details>

---

### Soal 7: Slot Pattern (`asChild`) pada Headless Primitives
**Pertanyaan:**
Jelaskan cara kerja mekanisme `asChild` (seperti yang digunakan Radix UI melalui `@radix-ui/react-slot`) dalam menghindari wrapping DOM element berlebih (*DOM bloat*) dan jelaskan bagaimana props, ref, dan event handlers dimerge ke elemen anak.

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Pembahasan:**
1. **Pencegahan DOM Bloat:** Tanpa slot, komponen pembungkus seperti `<Button as="a">` atau `<TooltipTrigger>` sering kali merender elemen wrapper `<div>` atau `<button>` tambahan yang dapat merusak flexbox/grid layout atau melanggar semantik HTML (misalnya `<button>` membungkus `<a>`).
2. **Mekanisme Kerja Slot:** Komponen `Slot` mengevaluasi `children`. Alih-alih merender elemen DOM baru, `Slot` melakukan kloning pada elemen anak tunggalnya (`React.cloneElement(children, mergedProps)`).
3. **Merging Strategy:**
   - **Props Biasa:** Props dari komponen Slot digabungkan dengan props elemen anak (props eksplisit pada anak umumnya memiliki prioritas kecuali kelas styling yang digabung).
   - **Event Handlers:** Menggabungkan handler internal Slot dengan handler bawaan anak menggunakan chaining (`childHandler?.(event); slotHandler?.(event)`).
   - **Ref Merging:** Menggunakan utilitas `composeRefs(slotRef, childRef)` untuk memastikan baik internal controller maupun user ref menerima referensi node DOM yang sama.
</details>

---

### Soal 8: Mitigasi Rendering Bottleneck pada Compound Components via Context
**Pertanyaan:**
Pada hierarki Compound Component yang besar dengan ratusan child nodes, pemanggilan Context sering memicu re-render yang tidak perlu pada setiap child saat satu field state kecil berubah. Sebutkan dan jelaskan 2 strategi arsitektural untuk mengisolasi re-render pada React Context!

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Pembahasan:**
1. **Split State & Dispatch Context:**
   Pisahkan context menjadi dua: `StateContext` (berisi state yang dinamis berubah) dan `DispatchContext` (berisi fungsi dispatch/updater yang stabil via `useCallback`). Komponen yang hanya memicu aksi (seperti trigger button atau close icon) hanya berlangganan `DispatchContext`, sehingga tidak akan pernah me-render ulang saat state berubah.
2. **Context Selectors / Atomic Store Pattern:**
   Menggunakan pustaka seperti `use-context-selector` atau mengintegrasikan micro-store internal (seperti Zustand atau vanilla pub-sub store via `useSyncExternalStore`). Child component hanya berlangganan slice data tertentu (`useStore(selector)`). Child hanya me-render ulang jika nilai kembalian dari selector berubah secara komparasi nilai (`Object.is` atau shallow equal).
</details>

---

### Soal 9: Controlled vs Uncontrolled API Dual-Mode
**Pertanyaan:**
Bagaimana cara merancang komponen headless agar dapat beroperasi secara *Dual Mode* (mendukung `value` & `onChange` untuk controlled mode, sekaligus `defaultValue` untuk uncontrolled mode) tanpa menyebabkan peringatan (*warning*) pergantian controlled/uncontrolled pada React?

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Pembahasan:**
Komponen harus menggunakan custom hook (sering disebut `useControllableState`):
1. **Deteksi Mode:** Identifikasi apakah `prop.value !== undefined`. Jika ya, komponen berada pada *controlled mode*. Jika tidak, *uncontrolled mode*.
2. **Internal State Initialization:** Menginisialisasi internal state hanya dengan `defaultValue` satu kali saat mount.
3. **State Resolution:** Nilai aktif yang dirender adalah `isControlled ? prop.value : internalState`.
4. **Setter Dispatch:** Ketika state hendak diperbarui:
   - Jika uncontrolled: perbarui `internalState` dan panggil callback opsional `onChange?.(newValue)`.
   - Jika controlled: jangan mutasi state lokal, tetapi panggil `onChange?.(newValue)` agar parent mengupdate value-nya.
5. Menghindari inisialisasi state dengan `undefined` kemudian beralih ke defined string/object di render berikutnya agar React tidak mendeteksi switching mode.
</details>

---

### Soal 10: Polymorphic Component Typing pada TypeScript
**Pertanyaan:**
Tuliskan generic type helper TypeScript untuk membuat komponen polymorphic dengan prop `as` opsional yang secara dinamis mewarisi HTML attribute yang valid sesuai tag yang dipilih (contoh: jika `as="a"`, atribut `href` wajib/tersedia; jika `as="button"`, atribut `type` tersedia).

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Pembahasan:**
Implementasi TypeScript tipe polymorphic yang presisi:

```typescript
import React from 'react';

// Props dasar komponen sendiri
type AsProp<C extends React.ElementType> = {
  as?: C;
};

// Menggabungkan props komponen + HTML attributes bawaan tag 'as',
// mengecualikan kunci yang bertabrakan dengan Omit
export type PolymorphicComponentProps<
  C extends React.ElementType,
  Props = {}
> = React.PropsWithChildren<Props & AsProp<C>> &
  Omit<React.ComponentPropsWithoutRef<C>, keyof (Props & AsProp<C>)>;

// Tipe untuk komponen dengan forwardRef yang aman secara polimorfik
export type PolymorphicRef<C extends React.ElementType> =
  React.ComponentPropsWithRef<C>['ref'];
```
Dengan pola ini, jika consumer menulis `<Button as="a" href="/dashboard">`, IDE akan mengaktifkan autocomplete untuk `href` dan memvalidasi tipe tanpa kompromi `any`.
</details>

---

## III. Skenario Kasus Nyata Produksi (3 Real-World Case Studies)

### Kasus 1: Refaktorisasi Design System Monolitik Menuju Headless Architecture pada Ekosistem Multi-Brand
* **Konteks:** Perusahaan enterprise memiliki 4 produk SaaS dengan visual identity (brand) berbeda: SaaS FinTech (gaya visual flat & compact), SaaS MedTech (gaya visual accessible tinggi dengan font besar), SaaS eCommerce (modern Tailwind UI), dan Internal Admin Portal. Sebelumnya, tim menggunakan library UI monolitik berbasis styled-components kaku yang sangat sulit dikustomisasi CSS-nya dan memicu duplikasi logika dropdown/modal di tiap repositori produk.
* **Tantangan:** 
  1. Bagaimana menyusun arsitektur library komponen bersama (*core design system*) yang membagikan 100% logic, keyboard behavior, dan a11y tanpa memaksakan CSS opinionated pada masing-masing produk?
  2. Bagaimana mendistribusikan package tersebut di monorepo monolitik?
* **Solusi Arsitektural:**
  1. **Core Primitives Layer:** Bangun package `@company/ui-primitives` berbasis Headless primitives (menggunakan Radix UI primitives atau custom headless hooks dengan Prop Getters). Layer ini murni TypeScript, zero-CSS, dan mengekspor komponen compound seperti `<Dropdown.Root>`, `<Dropdown.Trigger asChild>`, `<Dropdown.Content>`.
  2. **Theming/Consumer Layer:** Setiap produk mengonsumsi `@company/ui-primitives` dan membungkusnya dengan *preset styling* masing-masing produk (misal: Tailwind variant classes via `cva` - *class-variance-authority* di eCommerce, CSS Modules di MedTech).
  3. **Hasil:** Logika bug fixes (seperti perbaikan accessibility ARIA atau Safari iOS keyboard jump) diselesaikan sekali di core primitives dan langsung menguntungkan keempat produk tanpa merusak tata letak visual.

---

### Kasus 2: Memory Leak & Focus Jittering pada Virtualized Headless Select Component
* **Konteks:** Tim mengembangkan Headless Select/Combobox untuk memilih lebih dari 50.000 item nasabah bank menggunakan kombinasi headless state hook dan virtual list (`@tanstack/react-virtual`).
* **Gejala:** Pengguna melaporkan bahwa ketika menavigasi list menggunakan panah keyboard (`ArrowDown` / `ArrowUp`), browser mengalami freeze sesaat (jank), screen reader membaca nomor indeks secara kacau, dan fokus tiba-tiba terlempar keluar dari list ke elemen `<body>`.
* **Root Cause Analysis:**
  1. Komponen mencoba memindahkan fokus DOM nyata (`element.focus()`) ke setiap item baris yang ter-render. Karena list divirtualisasi, elemen DOM di luar viewport di-*unmount* secara instan. Ketika elemen yang sedang aktif di-unmount oleh virtualizer, browser kehilangan node aktif dan mereset fokus ke `document.body`.
  2. Setiap pergerakan panah memperbarui state `focusedIndex` di root Context yang memicu re-render seluruh 50 baris virtual DOM node sekaligus.
* **Solusi Perbaikan:**
  1. **Terapkan `aria-activedescendant`:** Jangan pindahkan fokus DOM fisik dari input search/trigger. Pertahankan fokus fisik tetap pada elemen input text, lalu gunakan atribut `aria-activedescendant="item-${activeId}"` pada input yang menunjuk ke ID item yang sedang disorot.
  2. **Sinkronisasi Virtualizer Scroll:** Panggil `virtualizer.scrollToIndex(activeIndex)` secara terprogram saat panah keyboard ditekan agar item aktif selalu berada di dalam viewport virtual DOM.
  3. **Isolasi State Sorotan:** Pisahkan penandaan visual (*highlight*) menggunakan atribut data `data-highlighted="true"` berbasis CSS selector ringan daripada re-render React state yang berat.

---

### Kasus 3: Headless Form Field Compound Component dengan Schema Validation Coupling
* **Konteks:** Sebuah tim membangun compound form component:
  ```tsx
  <Form>
    <FormField name="email">
      <FormLabel>Email</FormLabel>
      <FormControl>
        <Input />
      </FormControl>
      <FormMessage />
    </FormField>
  </Form>
  ```
* **Masalah:** Komponen `<FormControl>` secara kaku dipasangkan (*hard-coupled*) dengan React Hook Form dan Zod schema validator tertentu. Ketika tim lain mencoba menggunakan komponen UI `<FormField>` untuk step wizard berbasis state machine internal (XState) tanpa React Hook Form, seluruh komponen meledak (*runtime crash*) karena tidak menemukan context React Hook Form.
* **Solusi Rekayasa:**
  1. Pisahkan layer Context: Sediakan `<FormFieldProvider>` generik yang menerima antarmuka standar:
     ```typescript
     interface FormFieldContextValue {
       id: string;
       name: string;
       error?: string;
       isTouched?: boolean;
       inputProps: React.InputHTMLAttributes<HTMLInputElement>;
     }
     ```
  2. Buat adapter khusus: `@company/ui-form-rhf` untuk integrasi React Hook Form, dan biarkan core UI primitives tetap netral (*schema & state agnostic*).
  3. Gunakan Prop Getters pada level field: `getFieldProps(name)` yang menghasilkan `id`, `aria-describedby` (mengarah ke error message ID), dan `aria-invalid={!!error}`.

---

## IV. Practical Chapter Challenge: Building a Production-Ready Headless Accordion Primitive

### Deskripsi Tantangan
Buatlah sebuah implementasi **Headless Accordion** menggunakan pola **Compound Components**, **Prop Getters**, serta kepatuhan standar aksesibilitas **WAI-ARIA Accordion Pattern**.

### Ketentuan Teknis:
1. **Fitur Fungsional:**
   - Mendukung mode `single` (hanya 1 panel yang terbuka) dan `multiple` (banyak panel dapat dibuka bersamaan).
   - Mendukung mode `collapsible` (apakah panel aktif boleh ditutup kembali pada mode `single`).
   - Keyboard Navigation: Menekan tombol panah `ArrowDown` dan `ArrowUp` harus memindahkan fokus antar trigger accordion. Menekan `Home` memindahkan fokus ke trigger pertama, dan `End` memindahkan ke trigger terakhir.
2. **Kepatuhan WAI-ARIA:**
   - Trigger berupa `<button>` dengan `aria-expanded="true|false"` dan `aria-controls="panel-{id}"`.
   - Content panel memiliki `role="region"`, `id="panel-{id}"`, dan `aria-labelledby="trigger-{id}"`.
   - Menghilangkan panel dari accessibility tree ketika tertutup (`hidden` atau tidak di-render).
3. **Mekanisme Ekspor:**
   Komponen harus diekspor sebagai compound component:
   - `Accordion.Root`
   - `Accordion.Item`
   - `Accordion.Trigger`
   - `Accordion.Content`

### Skeleton Implementasi Acuan

```tsx
import React, {
  createContext,
  useContext,
  useId,
  useRef,
  useCallback,
  KeyboardEvent,
  ReactNode,
} from 'react';

// ==========================================
// 1. Types & Context Definition
// ==========================================
type AccordionType = 'single' | 'multiple';

interface AccordionRootProps {
  type?: AccordionType;
  collapsible?: boolean;
  value?: string[];
  defaultValue?: string[];
  onValueChange?: (value: string[]) => void;
  children: ReactNode;
  className?: string;
}

interface AccordionContextValue {
  type: AccordionType;
  collapsible: boolean;
  expandedValues: Set<string>;
  toggleItem: (itemValue: string) => void;
  registerTrigger: (node: HTMLButtonElement | null) => void;
  unregisterTrigger: (node: HTMLButtonElement | null) => void;
  triggersRef: React.MutableRefObject<HTMLButtonElement[]>;
}

const AccordionContext = createContext<AccordionContextValue | null>(null);

const useAccordionContext = () => {
  const ctx = useContext(AccordionContext);
  if (!ctx) throw new Error('Accordion components must be wrapped in <Accordion.Root>');
  return ctx;
};

// ==========================================
// 2. Accordion Item Context
// ==========================================
interface AccordionItemContextValue {
  value: string;
  triggerId: string;
  contentId: string;
  isExpanded: boolean;
}

const AccordionItemContext = createContext<AccordionItemContextValue | null>(null);

const useAccordionItemContext = () => {
  const ctx = useContext(AccordionItemContext);
  if (!ctx) throw new Error('<Accordion.Trigger> and <Accordion.Content> must be inside <Accordion.Item>');
  return ctx;
};

// ==========================================
// 3. Components Implementation
// ==========================================
export const AccordionRoot = ({
  type = 'single',
  collapsible = true,
  children,
  className,
}: AccordionRootProps) => {
  const [expandedValues, setExpandedValues] = React.useState<Set<string>>(new Set());
  const triggersRef = useRef<HTMLButtonElement[]>([]);

  const registerTrigger = useCallback((node: HTMLButtonElement | null) => {
    if (node && !triggersRef.current.includes(node)) {
      triggersRef.current.push(node);
    }
  }, []);

  const unregisterTrigger = useCallback((node: HTMLButtonElement | null) => {
    if (node) {
      triggersRef.current = triggersRef.current.filter((n) => n !== node);
    }
  }, []);

  const toggleItem = useCallback(
    (itemValue: string) => {
      setExpandedValues((prev) => {
        const next = new Set(prev);
        const isOpen = next.has(itemValue);

        if (type === 'single') {
          if (isOpen) {
            if (collapsible) next.clear();
          } else {
            next.clear();
            next.add(itemValue);
          }
        } else {
          if (isOpen) {
            next.delete(itemValue);
          } else {
            next.add(itemValue);
          }
        }
        return next;
      });
    },
    [type, collapsible]
  );

  return (
    <AccordionContext.Provider
      value={{
        type,
        collapsible,
        expandedValues,
        toggleItem,
        registerTrigger,
        unregisterTrigger,
        triggersRef,
      }}
    >
      <div className={className} data-accordion-root="">
        {children}
      </div>
    </AccordionContext.Provider>
  );
};

export const AccordionItem = ({
  value,
  children,
  className,
}: {
  value: string;
  children: ReactNode;
  className?: string;
}) => {
  const generatedId = useId();
  const triggerId = `accordion-trigger-${generatedId}`;
  const contentId = `accordion-content-${generatedId}`;
  const { expandedValues } = useAccordionContext();
  const isExpanded = expandedValues.has(value);

  return (
    <AccordionItemContext.Provider value={{ value, triggerId, contentId, isExpanded }}>
      <div
        className={className}
        data-state={isExpanded ? 'open' : 'closed'}
        data-accordion-item=""
      >
        {children}
      </div>
    </AccordionItemContext.Provider>
  );
};

export const AccordionTrigger = ({
  children,
  className,
  onClick,
  onKeyDown,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) => {
  const { toggleItem, registerTrigger, unregisterTrigger, triggersRef } = useAccordionContext();
  const { value, triggerId, contentId, isExpanded } = useAccordionItemContext();

  const refCallback = useCallback(
    (node: HTMLButtonElement | null) => {
      registerTrigger(node);
      return () => unregisterTrigger(node);
    },
    [registerTrigger, unregisterTrigger]
  );

  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    onKeyDown?.(e);
    if (e.defaultPrevented) return;

    const list = triggersRef.current;
    const currentIndex = list.indexOf(e.currentTarget);
    if (currentIndex === -1) return;

    let targetIndex = -1;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        targetIndex = (currentIndex + 1) % list.length;
        break;
      case 'ArrowUp':
        e.preventDefault();
        targetIndex = (currentIndex - 1 + list.length) % list.length;
        break;
      case 'Home':
        e.preventDefault();
        targetIndex = 0;
        break;
      case 'End':
        e.preventDefault();
        targetIndex = list.length - 1;
        break;
      default:
        return;
    }

    if (targetIndex >= 0 && list[targetIndex]) {
      list[targetIndex].focus();
    }
  };

  return (
    <button
      ref={refCallback}
      id={triggerId}
      type="button"
      aria-expanded={isExpanded}
      aria-controls={contentId}
      data-state={isExpanded ? 'open' : 'closed'}
      className={className}
      onClick={(e) => {
        onClick?.(e);
        toggleItem(value);
      }}
      onKeyDown={handleKeyDown}
      {...props}
    >
      {children}
    </button>
  );
};

export const AccordionContent = ({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => {
  const { triggerId, contentId, isExpanded } = useAccordionItemContext();

  if (!isExpanded) {
    return null;
  }

  return (
    <div
      id={contentId}
      role="region"
      aria-labelledby={triggerId}
      data-state={isExpanded ? 'open' : 'closed'}
      className={className}
      {...props}
    >
      {children}
    </div>
  );
};

export const Accordion = {
  Root: AccordionRoot,
  Item: AccordionItem,
  Trigger: AccordionTrigger,
  Content: AccordionContent,
};
```

---

## V. Checklist Pemahaman (Self-Assessment)

Gunakan lembar checklist ini untuk memvalidasi kesiapan sebelum melangkah ke bab berikutnya:

- [ ] **Konseptual:** Saya mengerti perbedaan mendasar antara Component Composition biasa, Compound Components, dan Higher-Order Components (HOC).
- [ ] **Pola Headless:** Saya memahami mengapa pemisahan state/a11y dari DOM/CSS memungkinkan tim membangun Design System enterprise yang tahan uji.
- [ ] **Inversion of Control:** Saya dapat menjelaskan dan mengimplementasikan pola *Render Props* dan *Prop Getters* untuk mencegah penimpaan event handler yang tidak disengaja.
- [ ] **Aksesibilitas (A11y):** Saya tahu cara mengimplementasikan standar WAI-ARIA dasar (role, aria-expanded, aria-controls, aria-labelledby, focus trap, roving tabindex).
- [ ] **State Reducer:** Saya memahami cara memberikan kebebasan bagi consumer komponen untuk mengintersep action reducer internal.
- [ ] **TypeScript Mastery:** Saya mampu menuliskan tipe Polymorphic Components menggunakan generic props (`as` prop) dan `forwardRef`.
- [ ] **Performance Engineering:** Saya menguasai teknik pemisahan React Context (state vs dispatch) untuk mencegah rendering cascading pada pohon komponen yang padat.
