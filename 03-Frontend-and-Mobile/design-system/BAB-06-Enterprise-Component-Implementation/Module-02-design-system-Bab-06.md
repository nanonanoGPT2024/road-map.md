# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Topik: Design System (Kategori: 03-Frontend-and-Mobile)
### Bab 06: Enterprise Component Implementation
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   **Merancang dan Mengimplementasikan Pola Komponen Lanjutan**: Menguasai arsitektur *Headless Components*, *Polymorphic Components*, dan *Compound Components* dengan kontrol penuh terhadap rendering, state, dan event logic.
*   **Membangun Finite State Machine (FSM) untuk Komponen Kompleks**: Menerapkan state machine deterministik untuk mengeliminasi *impossible states* pada widget interaktif seperti Combobox, Date Picker, dan Modal Dialog.
*   **Mencapai Standar Aksesibilitas WCAG 2.1 Tingkat AA/AAA**: Mengimplementasikan WAI-ARIA Authoring Practices (APG), pengelolaan fokus (*focus trap*, *roving tabindex*, *aria-activedescendant*), dan pengumuman *screen reader* secara native.
*   **Mengembangkan Type System Skala Enterprise**: Membangun definisi TypeScript generik tingkat lanjut yang mampu melakukan inferensi tipe otomatis terhadap elemen DOM (*polymorphic props with ref forwarding*).
*   **Mengoptimalkan Performa Rendering Komponen**: Menganalisis dan mengeliminasi *unnecessary re-renders*, mengelola *layout shifts* (CLS), dan memitigasi dampak komputasi styling terhadap runtime performance.

---

## 2. Prerequisite

Untuk menyerap materi ini secara maksimal, peserta harus memiliki kompetensi:
*   **Advanced TypeScript**: Penguasaan *conditional types*, *mapped types*, *template literal types*, `infer` keyword, dan *type predicates*.
*   **React Internal Mechanics**: Pemahaman mendalam mengenai siklus hidup Fiber, Reconciliation Engine, Synthetic Event System, Context propagation cost, dan React 18/19 Concurrency/Transitions.
*   **DOM & CSS Object Model (CSSOM)**: Pemahaman mendalam tentang *bubbling/capturing*, *event target vs current target*, *compositing layers*, *stacking context*, serta *reflow* & *repaint triggers*.
*   **Spesifikasi W3C WAI-ARIA 1.2**: Konsep semantik peran (*roles*), status (*states*), dan properti (*properties*) pada *accessibility tree*.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. Dekomposisi Arsitektur Komponen Enterprise

Komponen skala enterprise tidak boleh dibangun sebagai blok monolitik yang menggabungkan state, logika bisnis, aksesibilitas, dan presentasi visual dalam satu file. Arsitektur enterprise memisahkan tanggung jawab ini menjadi empat layer diskrit:

```
+------------------------------------------------------------------+
|                   CONSUMING APPLICATION CODE                     |
+------------------------------------------------------------------+
                                |
                                v
+------------------------------------------------------------------+
| LAYER 4: PRESENTATIONAL ADAPTER (Style Engine / CSS-in-JS / Zero-Runtime) |
| - Design Token bindings, Variant Management (cva/vanilla-extract) |
+------------------------------------------------------------------+
                                |
                                v
+------------------------------------------------------------------+
| LAYER 3: COMPOSITION & SLOTS (Polymorphic Layout Engine)         |
| - Ref forwarding, element swapping (`as`), context distribution   |
+------------------------------------------------------------------+
                                |
                                v
+------------------------------------------------------------------+
| LAYER 2: HEADLESS BEHAVIOR & ACCESSIBILITY (WAI-ARIA Primitives)  |
| - Keyboard navigation, ARIA attributes, Focus orchestration      |
+------------------------------------------------------------------+
                                |
                                v
+------------------------------------------------------------------+
| LAYER 1: DETERMINISTIC STATE ENGINE (Finite State Machine / Hook)|
| - Event-driven transitions, Pure reducers, Zero DOM dependency   |
+------------------------------------------------------------------+
```

1.  **Layer 1 (State Engine)**: Core logic independen yang merepresentasikan status komponen sebagai *statechart*. Tidak ada manipulasi DOM langsung, tidak ada dependency terhadap engine rendering tertentu.
2.  **Layer 2 (Headless Primitives)**: Bertanggung jawab menerjemahkan state machine ke atribut WAI-ARIA dan mendaftarkan event handler (misalnya: `onKeyDown`, `onBlur`). Menggunakan mekanisme *prop getters* atau *compound component contexts*.
3.  **Layer 3 (Composition & Slots)**: Mengabstraksikan struktur DOM node. Mengizinkan fleksibilitas semantik melalui *polymorphism* (`as` prop atau `asChild` delegation) dan delegasi *forwardedRef*.
4.  **Layer 4 (Presentational Adapter)**: Menghubungkan *design token* dengan elemen DOM melalui *class composition*, *atomic CSS*, atau *CSS modules*. Layer ini bersifat *purely visual*.

### 3.2. Polymorphism Engine dengan TypeScript Type Inference

Masalah fundamental pada polymorphic component seperti `<Box as="button" />` atau `<Box as="a" href="..." />` adalah mempertahankan *type safety*. Jika atribut `as` bernilai `"a"`, TypeScript harus mewajibkan atribut `href` dan melarang atribut native milik elemen lain (seperti `disabled` milik `<button>`), sembari meneruskan referensi DOM (`ref`) yang bertipe akurat (`HTMLAnchorElement` vs `HTMLButtonElement`).

Algoritma resolusi tipe polimorfik bekerja dengan prinsip:
$$\text{FinalProps<C, P>} = P \cup (\text{ComponentPropsWithRef<C>} \setminus \text{keysof}(P))$$

Di mana:
*   $C$ adalah target elemen (`React.ElementType`).
*   $P$ adalah properti kustom komponen kita.
*   Operasi *omit/difference* ($\setminus$) mencegah *prop collision* antara atribut kustom dan atribut native HTML.

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal di Skala Enterprise?
1.  **Ledakan Kombinatorik Props (*Props Explosion*)**: Penambahan varian desain secara imperatif menghasilkan komponen dengan puluhan boolean props (`isSearchable`, `isRounded`, `hasIconLeft`, `withFloatingLabel`). Hal ini memicu *cyclomatic complexity* yang tinggi dan rentan regresi.
2.  **State Desynchronization**: Mengelola status multi-step (misalnya: *idle*, *loading*, *success*, *error*, *disabled*) menggunakan kombinasi boolean flags (`const [loading, setLoading] = useState(false)`) dapat menimbulkan anomali di mana aplikasi berada pada kondisi yang mustahil (*impossible state*), seperti `isLoading === true` bersamaan dengan `isSuccess === true`.
3.  **Fragmentasi Aksesibilitas**: Menerapkan atribut ARIA secara manual pada tiap komponen visual sering berujung pada kelalaian implementasi standardisasi keyboard navigation (seperti *Home*, *End*, *Typeahead Search*, atau *Focus Trapping*).

### Solusi Arsitektural Enterprise
*   **Headless-First Development**: Memisahkan fungsi interaktivitas dari styling. Tim design system mendistribusikan *logic hook* dan *primitives*, sehingga tim produk bebas menyesuaikan layer presentasi tanpa merusak aksesibilitas.
*   **Deterministic Finite State Machines (FSM)**: Transisi state hanya bisa terjadi melalui *explicit events*. Komponen dipaksa untuk selalu berada dalam satu status yang valid.
*   **Slot / AsChild Delegation Pattern**: Menggantikan injeksi DOM wrapper dengan teknik delegasi properti (*cloning children* dengan shallow merge props dan event handler composition), menjaga kedalaman DOM tree tetap ramping.

---

## 5. How (Workflow detail)

Implementasi komponen enterprise mengikuti alur rekayasa yang ketat:

```
[W3C APG Specification Analysis]
               │
               ▼
[Statechart Modeling (FSM)] ──> Validasi State Invariants
               │
               ▼
[Headless Hook Primitives] ───> Unit Test: State Transitions & Keyboard Events
               │
               ▼
[Polymorphic Shell / Adapter] ─> Type Test: tsd / expect-type for strict types
               │
               ▼
[Token Injection / Styling] ───> Component Visual Variants (CVA/Style Engine)
               │
               ▼
[Accessibility Auditing] ─────> Automated axe-core & manual screen reader test
               │
               ▼
[Perf Profiling & Bundle CI] ─> Tree-shaking verification, Bundle Size Budgets
```

1.  **Spesifikasi Desain & Aksesibilitas**: Dokumentasikan *keyboard interaction pattern* dan *ARIA roles/states* berdasarkan W3C APG.
2.  **Pemodelan State Machine**: Definisikan semua state yang mungkin, event yang diakui, dan transisi transisi yang sah.
3.  **Implementasi Layer Primitif (Headless Hook)**: Tulis *custom hook* yang mengekspos *state* dan *prop getters* (fungsi yang mengembalikan koleksi atribut ARIA dan event handler yang diperlukan).
4.  **Konstruksi Polymorphic Shell**: Bungkus primitif dengan dukungan `as` prop dan `forwardRef` tanpa menyebabkan *render overhead*.
5.  **Integrasi Token**: Pasang layer visual menggunakan token yang di-compile menjadi CSS variables atau atomic classes.
6.  **Verifikasi & Validasi Mutu**:
    *   *Unit Testing*: Verifikasi transisi FSM via pure logic runner.
    *   *Type Testing*: Menguji variasi tipe polimorfik menggunakan pustaka assertion tipe.
    *   *A11y Testing*: Mengaudit DOM tree menggunakan `@axe-core/react`.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Sasis Mobil Modular
Bayangkan memproduksi armada kendaraan komersial. 
*   **Layer Headless & FSM** adalah *sasis, mesin, transmisi, dan sistem pengereman ABS*. Logika pengereman (FSM: Rem ditekan $\rightarrow$ deselerasi aktif) dan koneksi mekanis roda (Aksesibilitas/Keyboard focus) bekerja secara universal tanpa memedulikan eksterior.
*   **Layer Polymorphic Shell** adalah *titik pasang universal (mounting points)* sasis. Anda dapat memasang sasis tersebut pada rangka truk, sedan, atau van kargo (`as="div"`, `as="section"`, `as="a"`).
*   **Layer Styling** adalah *bodi, warna cat, dan interior mewah*. Anda bisa mengganti bodi luar dari baja menjadi serat karbon tanpa mendesain ulang sistem transmisi atau membahayakan standar keselamatan jalan raya (WCAG).

### Diagram Interaksi Komponen Primitif

```
 USER ACTION               HEADLESS PRIMITIVE                 ACCESSIBILITY TREE / DOM
      │                            │                                      │
      │ 1. Press "ArrowDown"       │                                      │
      ├───────────────────────────>│                                      │
      │                            │ 2. Evaluate State (Closed -> Open)   │
      │                            │    Compute next activeIndex = 0      │
      │                            │                                      │
      │                            │ 3. Return Prop Getters Mutations     │
      │                            ├─────────────────────────────────────>│
      │                            │    aria-expanded: true               │
      │                            │    aria-activedescendant: "opt-0"    │
      │                            │                                      │
      │ 4. Screen Reader reads     │                                      │
      │<──────────────────────────────────────────────────────────────────┤ "Option 1, 1 of 5"
      │                            │                                      │
      │ 5. Press "Enter"           │                                      │
      ├───────────────────────────>│                                      │
      │                            │ 6. Evaluate State (Commit Selection) │
      │                            │    Trigger onChange(value)           │
      │                            │    Transition to Closed              │
      │                            │                                      │
      │                            │ 7. Return Prop Getters Mutations     │
      │                            ├─────────────────────────────────────>│
      │                            │    aria-expanded: false              │
      │                            │    focus returned to trigger button  │
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: True Polymorphic Box Engine

Berikut adalah implementasi sistem polimorfik tipe-murni (*zero runtime library overhead*) yang mempertahankan validasi tipe DOM dan referensi pointer DOM secara deterministik.

```typescript
// types/polymorphic.ts
import React from 'react';

// Atribut `as` mendefinisikan target elemen
type AsProp<C extends React.ElementType> = {
  as?: C;
};

// Hilangkan duplikasi kunci antara kustom props dan native props
type PropsToOmit<C extends React.ElementType, P> = keyof (AsProp<C> & P);

// Ekstrak props polimorfik tanpa ref
export type PolymorphicComponentProp<
  C extends React.ElementType,
  Props = {}
> = React.PropsWithChildren<Props & AsProp<C>> &
  Omit<React.ComponentPropsWithoutRef<C>, PropsToOmit<C, Props>>;

// Ekstrak props polimorfik LENGKAP dengan ref yang sesuai
export type PolymorphicComponentPropWithRef<
  C extends React.ElementType,
  Props = {}
> = PolymorphicComponentProp<C, Props> & {
  ref?: PolymorphicRef<C>;
};

// Evaluasi tipe ref berdasarkan React.ElementType
export type PolymorphicRef<C extends React.ElementType> =
  React.ComponentPropsWithRef<C>['ref'];
```

```tsx
// components/Box.tsx
import React, { forwardRef } from 'react';
import { PolymorphicComponentPropWithRef, PolymorphicRef } from '../types/polymorphic';

interface BoxCustomProps {
  className?: string;
  // Contoh prop layout design token dasar
  p?: number | string;
  m?: number | string;
}

type BoxComponent = <C extends React.ElementType = 'div'>(
  props: PolymorphicComponentPropWithRef<C, BoxCustomProps>
) => React.ReactElement | null;

export const Box: BoxComponent = forwardRef(function Box<
  C extends React.ElementType = 'div'
>(
  { as, children, className, style, p, m, ...restProps }: BoxCustomProps & { as?: C },
  ref?: PolymorphicRef<C>
) {
  const Component = as || 'div';

  const inlineStyles: React.CSSProperties = {
    padding: typeof p === 'number' ? `${p * 4}px` : p,
    margin: typeof m === 'number' ? `${m * 4}px` : m,
    ...style,
  };

  return (
    <Component
      ref={ref}
      className={className}
      style={inlineStyles}
      {...restProps}
    >
      {children}
    </Component>
  );
});
```

*Verifikasi Penggunaan Tipenya:*
```tsx
// VALID: TypeScript mengizinkan 'href' karena 'as="a"'
<Box as="a" href="https://internal.enterprise.com" target="_blank">
  Enterprise Link
</Box>;

// ERROR: Property 'href' does not exist on type ... (HTMLButtonElement)
// <Box as="button" href="https://error.com">Invalid Button</Box>
```

---

### 7.2. Practical Example: Enterprise Accessible Combobox / Select Primitive

Contoh berikut mendemonstrasikan implementasi komponen *Combobox/Select Primitif* siap produksi menggunakan pendekatan **FSM murni**, **Headless Context**, dan **WAI-ARIA 1.2 Active Descendant Pattern**.

#### Bagian A: State Machine Engine
```typescript
// primitives/select/selectMachine.ts
export type SelectState = 'IDLE' | 'OPEN' | 'DISABLED';

export type SelectEvent =
  | { type: 'OPEN' }
  | { type: 'CLOSE' }
  | { type: 'TOGGLE' }
  | { type: 'FOCUS_NEXT' }
  | { type: 'FOCUS_PREV' }
  | { type: 'FOCUS_FIRST' }
  | { type: 'FOCUS_LAST' }
  | { type: 'SET_DISABLED'; payload: boolean };

export interface SelectContextState {
  state: SelectState;
  activeIndex: number;
  totalItems: number;
  selectedValue: string | null;
}

export function selectReducer(
  ctx: SelectContextState,
  event: SelectEvent
): SelectContextState {
  switch (ctx.state) {
    case 'DISABLED':
      if (event.type === 'SET_DISABLED' && !event.payload) {
        return { ...ctx, state: 'IDLE' };
      }
      return ctx;

    case 'IDLE':
      if (event.type === 'SET_DISABLED' && event.payload) {
        return { ...ctx, state: 'DISABLED' };
      }
      if (event.type === 'OPEN' || event.type === 'TOGGLE') {
        return {
          ...ctx,
          state: 'OPEN',
          activeIndex: ctx.activeIndex >= 0 ? ctx.activeIndex : 0,
        };
      }
      return ctx;

    case 'OPEN':
      if (event.type === 'SET_DISABLED' && event.payload) {
        return { ...ctx, state: 'DISABLED', activeIndex: -1 };
      }
      if (event.type === 'CLOSE' || event.type === 'TOGGLE') {
        return { ...ctx, state: 'IDLE' };
      }
      if (event.type === 'FOCUS_NEXT') {
        const next = ctx.activeIndex + 1 >= ctx.totalItems ? 0 : ctx.activeIndex + 1;
        return { ...ctx, activeIndex: next };
      }
      if (event.type === 'FOCUS_PREV') {
        const prev = ctx.activeIndex - 1 < 0 ? ctx.totalItems - 1 : ctx.activeIndex - 1;
        return { ...ctx, activeIndex: prev };
      }
      if (event.type === 'FOCUS_FIRST') {
        return { ...ctx, activeIndex: 0 };
      }
      if (event.type === 'FOCUS_LAST') {
        return { ...ctx, activeIndex: Math.max(0, ctx.totalItems - 1) };
      }
      return ctx;

    default:
      return ctx;
  }
}
```

#### Bagian B: Primitif React Context & Compound Components
```tsx
// primitives/select/Select.tsx
import React, {
  createContext,
  useContext,
  useReducer,
  useId,
  useCallback,
  useRef,
  useEffect,
} from 'react';
import { selectReducer, SelectContextState, SelectEvent } from './selectMachine';

interface SelectContextValue {
  state: SelectContextState;
  dispatch: React.Dispatch<SelectEvent>;
  triggerId: string;
  listboxId: string;
  getOptionId: (index: number) => string;
  onSelect: (value: string) => void;
  registerItem: (value: string) => number;
}

const SelectContext = createContext<SelectContextValue | null>(null);

function useSelectContext() {
  const context = useContext(SelectContext);
  if (!context) {
    throw new Error('Select compound components must be rendered within <Select.Root>');
  }
  return context;
}

interface RootProps {
  children: React.ReactNode;
  value?: string;
  onChange?: (val: string) => void;
  disabled?: boolean;
}

export function Root({ children, value = '', onChange, disabled = false }: RootProps) {
  const baseId = useId();
  const triggerId = `${baseId}-trigger`;
  const listboxId = `${baseId}-listbox`;
  const itemsRef = useRef<string[]>([]);

  const registerItem = useCallback((itemVal: string) => {
    const existingIndex = itemsRef.current.indexOf(itemVal);
    if (existingIndex !== -1) return existingIndex;
    itemsRef.current.push(itemVal);
    return itemsRef.current.length - 1;
  }, []);

  const [state, dispatch] = useReducer(selectReducer, {
    state: disabled ? 'DISABLED' : 'IDLE',
    activeIndex: -1,
    totalItems: 0,
    selectedValue: value || null,
  });

  useEffect(() => {
    dispatch({
      type: 'SET_DISABLED',
      payload: disabled,
    });
  }, [disabled]);

  const onSelect = useCallback(
    (val: string) => {
      onChange?.(val);
      dispatch({ type: 'CLOSE' });
    },
    [onChange]
  );

  const getOptionId = useCallback((idx: number) => `${baseId}-opt-${idx}`, [baseId]);

  return (
    <SelectContext.Provider
      value={{
        state: { ...state, totalItems: itemsRef.current.length, selectedValue: value || state.selectedValue },
        dispatch,
        triggerId,
        listboxId,
        getOptionId,
        onSelect,
      }}
    >
      <div className="relative inline-block w-full">{children}</div>
    </SelectContext.Provider>
  );
}

export function Trigger({ children, className }: { children: React.ReactNode; className?: string }) {
  const { state, dispatch, triggerId, listboxId, getOptionId } = useSelectContext();
  const isOpen = state.state === 'OPEN';

  const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (state.state === 'DISABLED') return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        if (!isOpen) dispatch({ type: 'OPEN' });
        else dispatch({ type: 'FOCUS_NEXT' });
        break;
      case 'ArrowUp':
        e.preventDefault();
        if (!isOpen) dispatch({ type: 'OPEN' });
        else dispatch({ type: 'FOCUS_PREV' });
        break;
      case 'Home':
        if (isOpen) {
          e.preventDefault();
          dispatch({ type: 'FOCUS_FIRST' });
        }
        break;
      case 'End':
        if (isOpen) {
          e.preventDefault();
          dispatch({ type: 'FOCUS_LAST' });
        }
        break;
      case 'Escape':
        if (isOpen) {
          e.preventDefault();
          dispatch({ type: 'CLOSE' });
        }
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        dispatch({ type: 'TOGGLE' });
        break;
    }
  };

  const activeDescendant =
    isOpen && state.activeIndex >= 0 ? getOptionId(state.activeIndex) : undefined;

  return (
    <button
      id={triggerId}
      type="button"
      role="combobox"
      aria-haspopup="listbox"
      aria-expanded={isOpen}
      aria-controls={listboxId}
      aria-activedescendant={activeDescendant}
      disabled={state.state === 'DISABLED'}
      onClick={() => dispatch({ type: 'TOGGLE' })}
      onKeyDown={handleKeyDown}
      className={className || 'px-4 py-2 border rounded flex justify-between items-center w-full'}
    >
      {children}
    </button>
  );
}

export function Content({ children, className }: { children: React.ReactNode; className?: string }) {
  const { state, listboxId, triggerId } = useSelectContext();

  if (state.state !== 'OPEN') return null;

  return (
    <ul
      id={listboxId}
      role="listbox"
      aria-labelledby={triggerId}
      tabIndex={-1}
      className={
        className ||
        'absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white py-1 shadow-lg ring-1 ring-black ring-opacity-5'
      }
    >
      {children}
    </ul>
  );
}

interface OptionProps {
  value: string;
  children: React.ReactNode;
  className?: string;
}

export function Option({ value, children, className }: OptionProps) {
  const { state, getOptionId, onSelect, registerItem } = useSelectContext();
  const itemIndex = registerItem(value);

  const isSelected = state.selectedValue === value;
  const isActive = state.activeIndex === itemIndex;
  const optionId = getOptionId(itemIndex);

  // Otomatis memilih saat pengguna menekan Enter di keyboard ketika option aktif
  useEffect(() => {
    // Dipantau oleh keyboard action trigger
  }, [isActive]);

  return (
    <li
      id={optionId}
      role="option"
      aria-selected={isSelected}
      onClick={() => onSelect(value)}
      className={`cursor-pointer px-4 py-2 text-sm select-none ${
        isActive ? 'bg-blue-600 text-white' : 'text-gray-900 hover:bg-gray-100'
      } ${isSelected ? 'font-bold' : 'font-normal'} ${className || ''}`}
    >
      {children}
    </li>
  );
}

export const Select = {
  Root,
  Trigger,
  Content,
  Option,
};
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Global Fintech Real-Time Trading Terminal (Multi-Brand & High-Frequency Streaming)

#### Masalah Arsitektur
Sebuah platform broker multinasional melayani lebih dari 15 label perbankan (*white-label*) menggunakan satu basis kode frontend. Pada antarmuka eksekusi order instan:
1.  **Rendering Bottleneck**: Data *ticker stock price* mengalir via WebSocket pada frekuensi 60fps (16ms per payload). Komponen *Dropdown Order Type* dan *Quantity Input* mengalami re-render masif tiap kali harga instrumen berfluktuasi karena state dikonsolidasikan dalam global context tree yang tidak terisolasi.
2.  **Aksesibilitas Gagal**: Trader dengan disabilitas visual tidak dapat mengeksekusi hotkey navigasi (`Alt + Enter`, `Down Arrow`) karena *synthetic focus management* bertabrakan dengan re-render komponen secara konstan.
3.  **Varian Theme Meledak**: Implementasi lama mengandalkan CSS-in-JS runtime (`styled-components`) yang menyuntikkan tag `<style>` baru ke DOM setiap kali tema berganti atau state tombol berubah, memicu CSSOM recalculation berulang pada CPU thread utama (*layout thrashing*).

#### Solusi Rekayasa
1.  **Headless Engine dengan Subtree Isolation**:
    Memigrasikan seluruh form widget ke *Headless Custom Primitives* yang mengisolasi local interactive state menggunakan transient listeners dan *uncontrolled boundaries* (menggunakan native DOM event capture).
2.  **Eliminasi Runtime CSS-in-JS**:
    Mengganti runtime CSS injection dengan **Zero-Runtime Tokens via CSS Custom Properties**. Nilai warna dan *elevation* diikat ke runtime variables global yang didefinisikan di level `<html>`:
    ```css
    :root[data-tenant="wealth-corp"] {
      --ds-color-interactive-primary: #0052cc;
      --ds-focus-ring: 0 0 0 2px rgba(0, 82, 204, 0.6);
    }
    :root[data-tenant="crypto-fast"] {
      --ds-color-interactive-primary: #f7931a;
      --ds-focus-ring: 0 0 0 2px rgba(247, 147, 26, 0.6);
    }
    ```
3.  **Active Descendant Focus Virtualization**:
    Mengganti pemindahan fokus aktual (`element.focus()`) yang memicu reflow besar dengan pattern `aria-activedescendant`. Hanya kontainer listbox yang menerima fokus DOM; kursor visual dikendalikan via transisi styling yang diakselerasi GPU (`transform: translateY(...)`), mereduksi komputasi layout engine dari **45ms** menjadi **< 1.5ms** per frame.

---

## 9. Trade-offs (Analisis Kompromi Teknis)

| Pendekatan / Pola | Keuntungan (*Pros*) | Kerugian / Biaya (*Cons*) | Skenario Pemilihan Tepat |
| :--- | :--- | :--- | :--- |
| **Polymorphic Components (`as` prop)** | Fleksibilitas tinggi bagi consumer; kebebasan markup semantik tanpa memecah konsistensi desain visual. | Tipe TypeScript sangat kompleks; waktu kompilasi (*tsc*) meningkat tajam; resiko wrapper bloating. | Komponen atomik inti: `Box`, `Text`, `Button`, `Stack`. |
| **Compound Components (via Context)** | Deklaratif; developer experience (DX) elegan; pembagian state implisit tanpa *prop drilling*. | Komponen terikat erat pada tree struktur tertentu; overhead pembuatan Context/Subtree allocations. | Widget interaktif multi-bagian: `Tabs`, `Accordion`, `Select`, `Dialog`. |
| **Active Descendant Navigation** | Sangat hemat performa; tidak ada reflow akibat fokus DOM yang berpindah-pindah. Mendukung virtualized lists. | Pengelolaan scroll-in-view harus dikalkulasi manual; screen reader lawas memiliki implementasi buggy. | Listbox, autocomplete, command palettes dengan > 100 entri atau streaming dataset. |
| **Roving Tabindex Navigation** | Kompatibilitas screen reader terbaik; fokus DOM sinkron dengan aksentuasi keyboard. | Membutuhkan perbaruan atribut `tabIndex` pada banyak node DOM; biaya render meningkat jika list sangat panjang. | Toolbar, Menu bar, Radio Group, Navigation rails (koleksi elemen kecil < 20 item). |
| **Zero-Runtime CSS vs Runtime CSS-in-JS** | Performa runtime optimal; zero JavaScript runtime styling overhead; hemat memori. | Kemampuan komputasi dinamis berbasis props JavaScript berkurang; membutuhkan setup build tool ekstra. | Arsitektur Design System Enterprise multi-platform skala besar. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan: Hilangnya Forwarded Ref pada Polymorphic Wrappers
Seringkali developer mengimplementasikan `forwardRef` tanpa memperhatikan penataan tipe generik. Akibatnya, `ref` bernilai `never` atau bertipe default `HTMLDivElement` meskipun pengguna menentukan `as="button"`.

*Anti-Pattern:*
```tsx
// SALAH: Type assertion memaksa ref menjadi HTMLDivElement!
export const BadBox = React.forwardRef(({ as: Comp = 'div', ...props }: any, ref: any) => {
  return <Comp ref={ref} {...props} />;
});
```

*Troubleshooting Checklist:*
1.  Gunakan deklarasi antarmuka helper khusus polimorfik seperti `PolymorphicRef<C>` (lihat Bab 7.1).
2.  Jangan pernah membungkus polymorphic base component menggunakan fungsi inline anonymous. Definisikan tipe fungsi komponen secara eksplisit sebelum cast `forwardRef`.

### 10.2. Kesalahan: SSR Hydration ID Mismatch pada Aksesibilitas
Menggunakan ID statis atau random number generik (`Math.random()`) untuk mengaitkan atribut `id` pada listbox dengan `aria-controls` pada trigger memicu kegagalan fatal saat Server-Side Rendering (Next.js/Remix).

*Solusi Teknis:*
Gunakan hook `useId()` dari React 18+ yang menjamin identitas string unik deterministik di antara server pass dan hydration client pass:
```tsx
const baseId = useId();
const triggerId = `ds-trigger-${baseId}`;
const contentId = `ds-panel-${baseId}`;
```

### 10.3. Kesalahan: Memory Leak pada Event Listeners Primitif
Komponen overlay (seperti `Popover`, `Toast`, `Tooltip`) yang memantau event global seperti `pointerdown` (untuk klik di luar / *click-outside*) atau `keydown` (Escape key) sering lupa mencabut listener saat *unmount* atau mendaftarkan listener baru pada setiap siklus re-render.

*Solusi Debugging:*
Periksa via Chrome DevTools: `getEventListeners(document)` pada Console. Pastikan listener berkurang saat komponen tertutup. Gunakan hook capture yang stabil:
```tsx
useEffect(() => {
  const handlePointerDown = (event: PointerEvent) => {
    if (!ref.current?.contains(event.target as Node)) {
      onClose();
    }
  };
  // Gunakan capture phase jika portal elemen lain memutus event propagation
  document.addEventListener('pointerdown', handlePointerDown, { capture: true });
  return () => {
    document.removeEventListener('pointerdown', handlePointerDown, { capture: true });
  };
}, [onClose]);
```

---

## 11. Best Practices (Production Checklist)

### Checklist Arsitektur Komponen
- [ ] **Decoupled Business Logic**: Tidak ada referensi eksplisit ke API domain spesifik (e.g., `userId`, `fetchCart()`) di dalam repositori Design System.
- [ ] **Zero Any Types**: Konfigurasi `tsconfig.json` mengaktifkan `"strict": true` dan `"noImplicitAny": true`.
- [ ] **Strict Event Delegation**: Event bubbling dicegah secara selektif tanpa menggunakan `event.stopPropagation()` secara serampangan (utamakan deteksi *target boundaries*).

### Checklist Aksesibilitas (WCAG 2.1 & WAI-ARIA)
- [ ] **Validasi Keyboard Non-Mouse**: Seluruh fungsi interaktif dapat dioperasikan penuh hanya menggunakan tombol `Tab`, `Shift+Tab`, `Space`, `Enter`, `Escape`, dan tombol `Panah`.
- [ ] **Aria States Synchronicity**: Nilai `aria-expanded`, `aria-checked`, `aria-selected`, dan `aria-hidden` selalu terikat dengan deterministik state machine.
- [ ] **Screen Reader Contrast & High Contrast Mode**: Komponen diuji menggunakan Windows High Contrast Mode / Forced Colors Mode (`@media (forced-colors: active)`).

### Checklist Performa Rendering
- [ ] **Layout Shift Zero (CLS)**: Elemen overlay, placeholder gambar, dan font fallbacks telah dialokasikan ukuran dimensinya untuk mencegah lonjakan layout visual.
- [ ] **Tree-shaking Valid**: Build package mendistribusikan berkas dalam format ES Modules (`esm`) murni dengan flag `"sideEffects": false` pada `package.json`.

---

## 12. Hands-on Practice

Buatlah implementasi lengkap komponen primitif **Accordion** compound yang memenuhi standar enterprise headless di repositori lokal Anda.

### Struktur Direktori Proyek
```text
hands-on/m02/
├── package.json
├── tsconfig.json
└── src/
    ├── primitives/
    │   └── accordion/
    │       ├── Accordion.tsx
    │       ├── accordionMachine.ts
    │       └── types.ts
    └── index.tsx
```

### Panduan Langkah Implementasi

#### Langkah 1: Siapkan `hands-on/m02/package.json`
```json
{
  "name": "@enterprise-ds/module-02",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "typescript": "^5.6.3"
  }
}
```

#### Langkah 2: Buat State Machine (`src/primitives/accordion/accordionMachine.ts`)
Tuliskan logic reducer yang mendukung dua skenario mode: `single` (hanya satu panel terbuka dalam satu waktu) dan `multiple` (banyak panel dapat dibuka bersamaan).

```typescript
export type AccordionType = 'single' | 'multiple';

export interface AccordionState {
  expandedItems: Set<string>;
  type: AccordionType;
}

export type AccordionEvent =
  | { type: 'TOGGLE_ITEM'; payload: { id: string } }
  | { type: 'COLLAPSE_ALL' };

export function accordionReducer(state: AccordionState, event: AccordionEvent): AccordionState {
  switch (event.type) {
    case 'TOGGLE_ITEM': {
      const { id } = event.payload;
      const nextExpanded = new Set(state.expandedItems);

      if (state.type === 'single') {
        if (nextExpanded.has(id)) {
          nextExpanded.clear();
        } else {
          nextExpanded.clear();
          nextExpanded.add(id);
        }
      } else {
        if (nextExpanded.has(id)) {
          nextExpanded.delete(id);
        } else {
          nextExpanded.add(id);
        }
      }

      return { ...state, expandedItems: nextExpanded };
    }
    case 'COLLAPSE_ALL':
      return { ...state, expandedItems: new Set() };
    default:
      return state;
  }
}
```

#### Langkah 3: Bangun Komponen Primitif (`src/primitives/accordion/Accordion.tsx`)
Implementasikan komponen compound:
*   `Accordion.Root` (Penyedia Context state global item yang aktif)
*   `Accordion.Item` (Penyedia Context untuk individual item)
*   `Accordion.Header` (Semantik `<h3>` wrapper standar ARIA)
*   `Accordion.Trigger` (Button pengendali interaktivitas dengan kaitan ARIA yang tepat)
*   `Accordion.Content` (Panel display dengan korelasi `aria-labelledby`)

Pastikan atribut `aria-controls` pada trigger mengarah secara presisi ke `id` panel content, dan `aria-expanded` sinkron dengan status internal FSM.

---

## 13. Exercise

### Level Easy: Accessible Dismissible Alert Primitive
Buat komponen `<Alert.Root>` dan `<Alert.Dismiss>` dengan WAI-ARIA role `alert` atau `status`. 
*   **Kebutuhan**: Saat tombol dismiss ditekan, komponen menghilang dari DOM secara halus dan mengumumkan pembatalan tersebut kepada screen reader tanpa memecah fokus user jika alert tidak memiliki interaktivitas kritis.

### Level Medium: Polymorphic Button dengan Slot Icon Pattern
Rancang komponen polymorphic button `<Button as="a">` yang menerima slot icon kiri dan kanan (`leftIcon`, `rightIcon`), state loading (`isLoading`), dan otomatis menginjeksi properti `aria-busy="true"` serta mematikan pointer events saat status loading aktif, tanpa menghilangkan ukuran dimensi fisik tombol (*layout stability*).

### Level Hard: Roving TabIndex Data-Table Navigation Primitive
Bangun headless hook `useRovingTabIndex` untuk navigasi cell data-table (2 dimensi: koordinat baris $X$ dan kolom $Y$).
*   Navigasi tombol panah atas, bawah, kiri, dan kanan harus memindahkan nilai `tabIndex={0}` secara deterministik.
*   Hanya ada 1 cell di seluruh tabel yang memiliki `tabIndex={0}` pada satu waktu, sementara seluruh cell lainnya bernilai `tabIndex={-1}`.
*   Dukung hotkey `Home` (pindah ke cell pertama pada baris aktif) dan `End` (pindah ke cell terakhir pada baris aktif).

---

## 14. Challenge

### Studi Kasus: Cross-Framework Micro-Frontend Component Federation with Isolated Tokens

**Skenario**:
Perusahaan Anda mengonsolidasikan arsitektur *micro-frontend* yang terdiri dari host Shell berbasis **Next.js (App Router)** dan tiga remote apps masing-masing berbasis **React 18**, **Vue 3**, dan **Vanilla Web Components**. Anda ditugaskan membangun arsitektur komponen input sentral yang mematuhi batasan teknis berikut:

1.  **CSS Variable Collisions**: Setiap remote app berjalan pada versi design token yang berpotensi memiliki inkonsistensi minor (misalnya perbedaan mapping token `color-primary`). Komponen harus menjamin isolasi styling visual menggunakan teknik *Shadow DOM* atau *CSS Scoped Encapsulation* tanpa kehilangan fleksibilitas font inheritence dari host app.
2.  **Focus Synchronization Bridge**: Dialog modal universal harus mampu di-trigger dari host app maupun remote app mana pun, membungkus konten arbitrary, dan menjaga loop penahanan fokus keyboard (*focus trap*) tetap solid melintasi batas *Shadow Root boundary* (`composedPath` evaluation).
3.  **Strict Performance Target**: Library primitive tidak boleh mengandalkan framework runtime bersama pada host. Komponen harus diekspor sebagai standar W3C Custom Elements (Web Components) tetapi menyediakan *first-class React Type-Safe Wrappers* yang mendukung event synthetic React, form binding native (`FormData`), dan Server-Side Rendering tanpa *hydration flickers*.

**Tugas Anda**:
Rancang dokumen arsitektur dan spesifikasi API dari design system tersebut, sertakan alur propagasi custom events lintas boundary micro-frontend, dan implementasikan *Focus Trap Engine* tingkat rendah yang kompatibel dengan Shadow DOM.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Basic Questions (5 Soal)

1.  **Apa tujuan utama penggunaan pola *Headless Component* dalam design system enterprise?**
    *   *Jawaban*: Memisahkan sepenuhnya logika interaktif, penanganan state, dan protokol aksesibilitas WAI-ARIA dari representasi visual (styling/CSS), sehingga komponen dapat digunakan kembali secara fleksibel di berbagai produk tanpa batasan tampilan visual.
2.  **Mengapa penggunaan tipe `any` pada *forwarded ref* komponen polimorfik dianggap sebagai anti-pattern kritis?**
    *   *Jawaban*: Mengabaikan type safety merusak kontrak TypeScript, menghilangkan autocomplete API native DOM dari elemen target (misalnya properti `.play()` pada `<video>` atau `.href` pada `<a>`), serta menyamarkan bug runtime saat ref digunakan untuk manipulasi DOM.
3.  **Apa fungsi dari atribut ARIA `aria-expanded`?**
    *   *Jawaban*: Memberi sinyal status semantik kepada teknologi asistif (seperti screen reader) mengenai apakah kontainer atau panel yang dikendalikan oleh elemen pemicu saat ini sedang ditampilkan (*true*) atau disembunyikan (*false*).
4.  **Pada pola *Active Descendant*, elemen mana yang menerima fokus keyboard DOM langsung (`document.activeElement`)?**
    *   *Jawaban*: Elemen kontainer induk (seperti elemen `<input>` combobox atau elemen wrapper `<ul>` listbox), bukan elemen opsi individual di dalamnya.
5.  **Kapan sebaiknya kita menggunakan `useId()` daripada membuat ID secara manual dengan hashing counter?**
    *   *Jawaban*: Setiap kali komponen memerlukan asosiasi ID deterministik yang sinkron antara proses kompilasi di sisi server (SSR) dan proses hidrasi di sisi klien (*hydration phase*) untuk mencegah *SSR mismatch warning*.

### 15.2. Intermediate Questions (5 Soal)

1.  **Jelaskan mekanisme kerja *Roving Tabindex* dalam navigasi keyboard sekumpulan elemen (misal: Radio Group)!**
    *   *Jawaban*: Mekanisme ini memastikan hanya satu item dalam grup yang memiliki atribut `tabIndex="0"` (item yang sedang aktif atau dipilih), sementara semua item lainnya memiliki `tabIndex="-1"`. Saat tombol navigasi panah ditekan, item target diubah menjadi `tabIndex="0"`, fokus DOM dipindahkan ke item tersebut secara manual via `.focus()`, dan item sebelumnya dikembalikan ke `tabIndex="-1"`.
2.  **Bagaimana cara mengatasi konflik nama props native dengan props kustom pada interface TypeScript polimorfik?**
    *   *Jawaban*: Menggunakan conditional utility type `Omit<React.ComponentPropsWithoutRef<C>, keyof CustomProps>` untuk mengekstraksi atribut native elemen target dan membuang property keys yang bertubrukan dengan interface kustom sebelum melakukan union.
3.  **Mengapa pendekatan Finite State Machine (FSM) lebih unggul daripada sekumpulan boolean flags (`useState(false)`) untuk interaktivitas komponen modal?**
    *   *Jawaban*: FSM menjamin transisi state yang deterministik dan mencegah *impossible states* (seperti modal berada pada status *opening* dan *closing* secara simultan). Transisi state hanya dapat dipicu oleh aksi (*events*) yang sah sesuai diagram status yang telah ditetapkan.
4.  **Apa dampak performa dari penggunaan teknik render delegasi `asChild` (seperti pada Radix UI) dibandingkan dengan polymorphic prop `as` tradisional?**
    *   *Jawaban*: `asChild` mengandalkan metode `React.cloneElement` untuk menyatukan event handlers dan properti visual langsung ke child element pertama pengguna. Ini mengeliminasi *DOM wrapper element* ekstra, mengurangi kedalaman *DOM tree*, serta menghindari abstraksi tipe generics polimorfik yang berat pada proses inferensi kompilator TypeScript.
5.  **Bagaimana cara mengamankan fokus keyboard agar tidak keluar dari komponen Dialog yang sedang terbuka (*Focus Trapping*) tanpa menggunakan pustaka eksternal?**
    *   *Jawaban*: Mendaftarkan event listener pada fase penekanan tombol `Tab` / `Shift+Tab`. Lakukan *query* terhadap semua elemen interaktif yang terlihat di dalam modal (`button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])`). Jika fokus berada pada elemen fokusable terakhir dan user menekan `Tab`, alihkan fokus paksa ke elemen fokusable pertama; lakukan operasi sebaliknya saat `Shift+Tab` ditekan dari elemen pertama.

### 15.3. Skenario Kasus Produksi (3 Soal)

#### Skenario 1: Layout Thrashing pada Infinite Scroll Select List
*Kondisi*: Tim Anda merilis komponen Autocomplete Select yang memuat 2.000 entri data ke dalam viewport modal. Ketika pengguna menavigasi daftar dengan menahan tombol Panah Bawah (`ArrowDown`), browser mengalami drop frame ekstrem (FPS drop hingga < 15fps) dan aplikasi terasa macet.
*Pertanyaan*: Analisis akar permasalahan performa ini dan berikan arsitektur perbaikannya!
*Jawaban Arsitektural*:
1.  **Akar Masalah**: Komponen melakukan pergeseran fokus DOM aktual (`node.focus()`) yang memicu kalkulasi ulang *scroll-to-view* layout engine (`scrollIntoView` imperatif) dan memaksa browser melakukan *layout recalculation* (reflow) secara sinkron pada setiap frame. Selain itu, rendering 2.000 node DOM nyata membebani memori CSSOM dan Reconciliation Fiber.
2.  **Solusi Rekayasa**:
    *   Implementasikan **List Virtualization (Windowing)** sehingga hanya elemen yang masuk dalam area pandang (*viewport*) yang di-render ke DOM ($\approx 10-20$ node).
    *   Ubah pola navigasi dari manipulasi fokus native menjadi **`aria-activedescendant`**. Kontainer input tetap memegang fokus tunggal.
    *   Hitung offset visual scroll secara matematis menggunakan transformasi GPU (`transform: translateY(...)`) alih-alih membiarkan browser melakukan reflow otomatis per node.

#### Skenario 2: Hydration Mismatch & Event Bubbling Trap pada Portaled Overlays
*Kondisi*: Sebuah komponen Tooltip di-mount menggunakan `createPortal` langsung ke `document.body`. Ketika Tooltip dibuka di dalam Form, menekan tombol `Enter` saat fokus berada di dalam elemen interaktif Tooltip memicu submit pada form induk, meskipun form tersebut berada di luar hierarchy visual tooltip.
*Pertanyaan*: Mengapa fenomena ini terjadi dan bagaimana memitigasinya pada level desain komponen primitif?
*Jawaban Arsitektural*:
1.  **Akar Masalah**: Dalam model internal React, *Synthetic Event System* mengikuti struktur komponen hierarkis React Tree, **bukan** hierarki DOM tree fisik. Meskipun komponen di-portal ke `document.body`, event `keydown` atau `submit` akan tetap melakukan *bubbling up* melalui parent components di level React tree menuju ke `<form>`.
2.  **Solusi Rekayasa**:
    *   Pada layer primitif container Tooltip, tangkap event yang relevan secara native atau cegah bubbling internal:
        ```tsx
        <div onKeyDown={(e) => {
          // Hanya tangkap event jika event berasal dari dalam boundary interaktif overlay
          e.stopPropagation();
        }}>
        ```
    *   Atau secara arsitektural, jangan izinkan elemen interaktif berada di dalam Tooltip; alihkan ke tipe overlay semantik yang tepat seperti **Popover** atau **Dialog** yang memiliki kontrak peran aksesibilitas yang sesuai.

#### Skenario 3: Broken Screen Reader Focus saat Dynamic Content Re-renders
*Kondisi*: Aplikasi Single Page Application (SPA) memuat data pengguna secara asinkron. Komponen `<DynamicSelect />` mengubah opsi pilihannya secara dinamis setelah panggilan jaringan selesai. Screen reader NVDA/VoiceOver berhenti membacakan opsi yang sedang disorot setelah data baru masuk.
*Pertanyaan*: Langkah arsitektur apa yang harus diambil untuk memulihkan konteks screen reader secara deterministik?
*Jawaban Arsitektural*:
1.  **Akar Masalah**: Terjadi pembongkaran node (*node unmounting*) saat rendering data baru. Referensi ID yang ditunjuk oleh `aria-activedescendant` mengarah ke ID lama yang telah dieliminasi dari DOM sebelum elemen baru terpasang, menyebabkan State Machine kehilangan pointer sinkronisasi indeks aktif.
2.  **Solusi Rekayasa**:
    *   Gunakan **`aria-live="polite"`** pada region notifikasi invisible untuk mengumumkan ketersediaan pembaruan data secara verbal kepada teknologi asistif (misal: *"Daftar diperbarui, 10 opsi tersedia"*).
    *   State Machine harus secara deterministik me-reset `activeIndex` ke indeks awal yang valid (misal: indeks 0) atau mencocokkan nilai berdasarkan kestabilan data key unik, bukan array index numerik murni.
    *   Pertahankan kestabilan ID opsi dengan generator deterministik: `${listId}-item-${item.uniqueKey}` alih-alih mengandalkan auto-increment counter transient.

---

## 16. Summary

Implementasi komponen enterprise menuntut pemisahan tegas antara logika keadaan (*state*), kepatuhan aksesibilitas (*behavior & ARIA*), arsitektur polimorfik (*structural typing*), dan adaptasi visual (*styling*). 

Kunci stabilitas arsitektur komponen di skala besar berakar pada:
1.  **State Machines**: Menggantikan sekumpulan boolean mutable dengan FSM murni guna mengeliminasi kondisi inkonsisten.
2.  **Headless Architecture**: Menghilangkan dependensi erat pada markup dan CSS framework tertentu, memperpanjang siklus hidup kode core design system.
3.  **Strict Type Composition**: Memanfaatkan kapabilitas tingkat tinggi TypeScript untuk menjamin keselamatan tipe polimorfik tanpa mengorbankan pengalaman developer (*DX*).
4.  **Zero-Cost A11y Primitives**: Mengadopsi standar WAI-ARIA APG secara native dari layer pondasi sehingga kepatuhan aksesibilitas bersifat implisit bagi tim produk yang mengonsumsinya.