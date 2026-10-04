# Kurikulum Enterprise: React Architecture & Design Systems
## Kategori: 03-Frontend-and-Mobile
### BAB-04: Advanced Component Patterns & Headless UI Architecture
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal/Senior Frontend Engineer diharapkan mampu:
1. **Merancang Headless Component Engines**: Membangun komponen UI kompleks yang sepenuhnya memisahkan *state machine*, logika aksesibilitas (WAI-ARIA 1.2), dan interaksi keyboard dari lapisan presentasi visual (CSS/Tailwind).
2. **Menguasai Pattern Polymorphic & Slot Machine**: Mengimplementasikan typing TypeScript tingkat lanjut (`PolymorphicComponentPropsWithRef`) dan arsitektur komposisi `asChild` (Slot pattern) untuk mencegah *DOM wrapper hell*.
3. **Mengoptimalkan Fine-Grained Context Subscription**: Mengeliminasi rendering *cascade* (render trashing) pada Compound Components skala besar menggunakan strategi *External Store Subscription* (`useSyncExternalStore`) dan *Context Selectors*.
4. **Menerapkan Production-Grade Design System Architecture**: Menstandarisasi antarmuka komponen enterprise multi-brand berbasis *Inversion of Control* (IoC) yang lolos audit aksesibilitas WCAG 2.2 Level AAA.

---

### 2. Prerequisite

* Pemahaman mendalam mengenai React Fiber Reconciler, Lifecycle, dan Hooks runtime engine.
* Penguasaan TypeScript Lanjutan: Generics, Conditional Types, Type Narrowing, Template Literal Types, dan Indexed Access Types.
* Pemahaman arsitektur DOM: Event bubbling/capturing, Synthetic Events, Focus Management, dan Keyboard Navigation APIs.
* Pengetahuan dasar standar W3C WAI-ARIA Authoring Practices Guide (APG).

---

### 3. Concept & Internal Architecture (Mendalam)

#### Arsitektur Headless UI & Inversion of Control (IoC)

Pendekatan monolitik UI tradisional mengikat *logic*, *accessibility*, dan *styling* dalam satu bundel komponen. Ketika sistem enterprise berkembang menjadi multi-brand atau multi-platform, pendekatan ini kolaps akibat ledakan kombinatorial props (`variant`, `size`, `isRounded`, `customIconStyle`, dll).

Headless UI memecah tanggung jawab ini menjadi tiga layer arsitektur:
1. **State & Logic Machine**: Mengelola transisi state internal, keyboard navigation, dan event handling (biasanya dibungkus dalam Custom Hooks murni).
2. **Accessibility & Attribute Engine**: Memetakan state ke atribut WAI-ARIA spesifik (`aria-expanded`, `aria-activedescendant`, `role`, `id`) dan menangani *focus trapping*.
3. **Presentational Layer**: Didelegasikan sepenuhnya kepada konsumer komponen via *Render Props*, *Slot Pattern*, atau *Compound Components*.

```
+-----------------------------------------------------------------+
|                       Consumer Component                        |
|             (Tailwind / Vanilla Extract / Emotion)              |
+-----------------------------------------------------------------+
                                |
                                v
+-----------------------------------------------------------------+
|               Layer 2: Slot / Polymorphic Bridge                |
|             (Radix-like Slot, asChild, Ref Merging)             |
+-----------------------------------------------------------------+
                                |
                                v
+-----------------------------------------------------------------+
|              Layer 1: Headless Hook / State Machine             |
|   (useSyncExternalStore, Keyboard Matrix, Focus Management)     |
+-----------------------------------------------------------------+
                                |
                                v
+-----------------------------------------------------------------+
|                       DOM & Accessibility                       |
|           (WAI-ARIA Attributes, Live Regions, Native DOM)       |
+-----------------------------------------------------------------+
```

#### Mekanisme Kerja Slot Pattern (`asChild`)

Slot Pattern (dipopulerkan oleh Radix UI) memecahkan masalah wrapping `<div>` atau `<span>` yang tidak perlu. Alih-alih merender elemen HTML sendiri, komponen Slot memproyeksikan semua props, atribut ARIA, event handler, dan `ref` langsung ke anak pertamanya (*first valid React element child*).

Internal mechanics dari Slot Pattern:
1. Memvalidasi bahwa `children` adalah elemen React tunggal yang valid via `React.isValidElement`.
2. Melakukan *deep merge* terhadap props:
   * **Event Handlers**: Menggabungkan handler internal dan handler milik konsumen. Jika handler konsumen memanggil `event.preventDefault()`, logika internal dapat merespons sesuai kebutuhan (atau sebaliknya).
   * **ClassNames/Styles**: Menggabungkan string kelas atau style objects.
   * **Refs**: Menggabungkan `forwardedRef` komponen dengan `ref` internal menggunakan *utility compose refs*.

#### Resolusi Tipe Komponen Polymorphic

Komponen polymorphic memungkinkan konsumer mengubah tag HTML yang mendasari (misal: `<Button as="a" href="...">`) dengan *type safety* penuh. Jika tag diubah menjadi `<a>`, TypeScript harus secara otomatis mewajibkan atribut `href` dan melarang atribut khusus `<button>` seperti `type="submit"`.

Tantangannya adalah *Ref Forwarding*. Tipe elemen DOM tujuan harus cocok secara dinamis dengan nilai generic `as`:

$$\text{Props} = \text{ComponentOwnProps} \cup (\text{TagProps} \setminus \text{ComponentOwnProps})$$

---

### 4. Why & What

| Dimensi | Tightly-Coupled UI (Monolitik) | Headless UI Pattern |
| :--- | :--- | :--- |
| **Kopling Desain** | Sangat tinggi. Terikat pada CSS runtime / framework tertentu. | Nol. Framework-agnostic styling (CSS Modules, Tailwind, Zero-runtime). |
| **Aksesibilitas (a11y)** | Rentan rusak jika ada kustomisasi visual mendalam. | Terjamin. Logic a11y terkunci di headless engine, tidak terpengaruh styling. |
| **Bundle Size** | Membesar seiring variasi props visual baru. | Minimal dan modular; hanya mengimpor logic yang dipakai (*tree-shakeable*). |
| **Maintenance Cost** | Tinggi saat redesign visual: butuh refactor logic komponen. | Sangat rendah: visual diubah tanpa menyentuh *core behavioral tests*. |

---

### 5. How (Workflow Detail)

Alur kerja perancangan enterprise Headless UI Primitive:

```
[1. Analisis Spesifikasi APG W3C]
       │
       ▼
[2. Definisi State Machine Engine] ─── (Finite State: Open/Closed/Navigating)
       │
       ▼
[3. Hook Abstraction: useDropdownPrimitive] ─── (Keyboard Navigation & ARIA)
       │
       ▼
[4. Context Selector Architecture] ─── (useSyncExternalStore to eliminate cascades)
       │
       ▼
[5. Polymorphic / Slot Integration] ─── (Mendukung asChild & Ref Merging)
       │
       ▼
[6. Visual Skinning & Consumer Distribution]
```

1. **Analisis Spesifikasi APG**: Tentukan peran aksesibilitas (misal: `combobox`, `listbox`, `dialog`), keyboard interaction contract (`ArrowDown`, `Escape`, `Home`, `End`), dan atribut reaktif.
2. **Definisi State Machine Engine**: Bangun reduksi state yang deterministik (hindari multiple `useState` desinkron).
3. **Hook Abstraction**: Isolasi penanganan keyboard dan ARIA props ke dalam hook terpisah.
4. **Context Selector Architecture**: Bungkus state machine dalam context engine berbasis granular subscription agar komponen anak (misal: `Item`) tidak re-render saat state sibling berubah.
5. **Slot Integration**: Implementasikan antarmuka `Slot` agar elemen visual sepenuhnya dikontrol oleh konsumen.
6. **Visual Skinning**: Distribusikan komponen sebagai Design System Primitive.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Orkestra Simfoni
* **Headless Primitive Engine**: Komposer dan Partitur Musik (Partitur mengatur nada, birama, dan urutan nada yang tidak dapat ditawar agar harmonis/aksesibel).
* **Slot / Polymorphic Interface**: Stand partitur fleksibel (bisa dipasang untuk biola, cello, atau flute).
* **Styling (Tailwind/CSS)**: Kostum panggung pemain musik. Mau bermain memakai jas formal, pakaian tradisional, atau pakaian kasual, simfoninya tetap harmonis dan dimengerti penonton.

#### Diagram Interaksi Ref & Event Merging pada Slot

```
       Consumer Prop:                     Slot Primitive Logic:
    onClick={(e) => ...}                  handleKeyDown / onClick
            │                                       │
            ▼                                       ▼
  +───────────────────────────────────────────────────────────+
  |                   composeEventHandlers                    |
  |  1. Eksekusi Consumer Handler                             |
  |  2. Periksa event.defaultPrevented                        |
  |  3. Eksekusi Primitive Handler (jika tidak dicegah)       |
  +───────────────────────────────────────────────────────────+
                                │
                                ▼
                       Target DOM Element
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: The Polymorphic Slot Component (`asChild`)

Implementasi TypeScript murni untuk engine `Slot` dan utilitas `composeRefs`:

```typescript
// primitives/Slot.tsx
import * as React from 'react';

export type PossibleRef<T> = React.Ref<T> | undefined;

/**
 * Menggabungkan multiple refs (callback atau object refs) menjadi satu callback ref.
 */
export function composeRefs<T>(...refs: PossibleRef<T>[]): (node: T) => void {
  return (node: T) => {
    refs.forEach((ref) => {
      if (!ref) return;
      if (typeof ref === 'function') {
        ref(node);
      } else {
        (ref as React.MutableRefObject<T>).current = node;
      }
    });
  };
}

interface SlotProps extends React.HTMLAttributes<HTMLElement> {
  children?: React.ReactNode;
}

export const Slot = React.forwardRef<HTMLElement, SlotProps>((props, forwardedRef) => {
  const { children, ...slotProps } = props;

  if (React.isValidElement(children)) {
    const childRef = (children as any).ref;
    
    // Deep merge props & ref
    return React.cloneElement(children, {
      ...mergeProps(slotProps, children.props),
      ref: forwardedRef ? composeRefs(forwardedRef, childRef) : childRef,
    });
  }

  if (React.Children.count(children) > 1) {
    throw new Error('[Slot]: Slot component expects exactly one React element child.');
  }

  return null;
});

Slot.displayName = 'Slot';

function mergeProps(parentProps: Record<string, any>, childProps: Record<string, any>) {
  const overrideProps = { ...childProps };

  for (const propName in parentProps) {
    const parentPropValue = parentProps[propName];
    const childPropValue = childProps[propName];

    // Merge Event Handlers
    if (/^on[A-Z]/.test(propName)) {
      if (parentPropValue && childPropValue) {
        overrideProps[propName] = (...args: unknown[]) => {
          childPropValue(...args);
          parentPropValue(...args);
        };
      } else if (parentPropValue) {
        overrideProps[propName] = parentPropValue;
      }
    } 
    // Merge Classnames
    else if (propName === 'className') {
      overrideProps[propName] = [parentPropValue, childPropValue].filter(Boolean).join(' ');
    } 
    // Merge Styles
    else if (propName === 'style') {
      overrideProps[propName] = { ...parentPropValue, ...childPropValue };
    } else {
      overrideProps[propName] = parentPropValue;
    }
  }

  return { ...parentProps, ...overrideProps };
}
```

---

#### B. Practical Example: Production-Grade Headless Dropdown Engine

Sebuah engine dropdown berbasis *external store subscription* (tanpa render cascades) dengan implementasi WAI-ARIA lengkap.

```typescript
// primitives/dropdown/DropdownContext.ts
import { createContext, useContext, useSyncExternalStore } from 'react';

export interface DropdownState {
  isOpen: boolean;
  highlightedIndex: number;
  selectedItem: string | null;
  items: string[];
}

export type DropdownAction =
  | { type: 'OPEN' }
  | { type: 'CLOSE' }
  | { type: 'TOGGLE' }
  | { type: 'NAVIGATE_UP' }
  | { type: 'NAVIGATE_DOWN' }
  | { type: 'SELECT_INDEX'; index: number }
  | { type: 'REGISTER_ITEM'; item: string }
  | { type: 'UNREGISTER_ITEM'; item: string };

export class DropdownStore {
  private state: DropdownState = {
    isOpen: false,
    highlightedIndex: -1,
    selectedItem: null,
    items: [],
  };

  private listeners = new Set<() => void>();

  public getSnapshot = (): DropdownState => this.state;

  public subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  public dispatch = (action: DropdownAction): void => {
    this.state = this.reducer(this.state, action);
    this.listeners.forEach((listener) => listener());
  };

  private reducer(state: DropdownState, action: DropdownAction): DropdownState {
    switch (action.type) {
      case 'OPEN':
        return { ...state, isOpen: true, highlightedIndex: 0 };
      case 'CLOSE':
        return { ...state, isOpen: false, highlightedIndex: -1 };
      case 'TOGGLE':
        return state.isOpen
          ? { ...state, isOpen: false, highlightedIndex: -1 }
          : { ...state, isOpen: true, highlightedIndex: 0 };
      case 'NAVIGATE_DOWN':
        if (!state.isOpen) return { ...state, isOpen: true, highlightedIndex: 0 };
        return {
          ...state,
          highlightedIndex:
            state.highlightedIndex < state.items.length - 1 ? state.highlightedIndex + 1 : 0,
        };
      case 'NAVIGATE_UP':
        if (!state.isOpen) return { ...state, isOpen: true, highlightedIndex: state.items.length - 1 };
        return {
          ...state,
          highlightedIndex:
            state.highlightedIndex > 0 ? state.highlightedIndex - 1 : state.items.length - 1,
        };
      case 'SELECT_INDEX':
        return {
          ...state,
          selectedItem: state.items[action.index] ?? null,
          isOpen: false,
          highlightedIndex: -1,
        };
      case 'REGISTER_ITEM':
        return { ...state, items: [...state.items, action.item] };
      case 'UNREGISTER_ITEM':
        return { ...state, items: state.items.filter((i) => i !== action.item) };
      default:
        return state;
    }
  }
}

export const DropdownStoreContext = createContext<DropdownStore | null>(null);

export function useDropdownStore(): DropdownStore {
  const store = useContext(DropdownStoreContext);
  if (!store) {
    throw new Error('Component must be wrapped within a <Dropdown.Root>');
  }
  return store;
}

export function useDropdownSelector<T>(selector: (state: DropdownState) => T): T {
  const store = useDropdownStore();
  return useSyncExternalStore(store.subscribe, () => selector(store.getSnapshot()));
}
```

```typescript
// primitives/dropdown/DropdownComponents.tsx
import * as React from 'react';
import {
  DropdownStore,
  DropdownStoreContext,
  useDropdownStore,
  useDropdownSelector,
} from './DropdownContext';
import { Slot } from '../Slot';

export interface RootProps {
  children: React.ReactNode;
}

export function Root({ children }: RootProps) {
  const [store] = React.useState(() => new DropdownStore());

  return (
    <DropdownStoreContext.Provider value={store}>
      <div className="relative inline-block text-left">{children}</div>
    </DropdownStoreContext.Provider>
  );
}

export interface TriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

export const Trigger = React.forwardRef<HTMLButtonElement, TriggerProps>(
  ({ asChild, children, ...props }, ref) => {
    const store = useDropdownStore();
    const isOpen = useDropdownSelector((s) => s.isOpen);
    const selectedItem = useDropdownSelector((s) => s.selectedItem);

    const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        store.dispatch({ type: 'NAVIGATE_DOWN' });
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        store.dispatch({ type: 'NAVIGATE_UP' });
      } else if (e.key === 'Escape' && isOpen) {
        e.preventDefault();
        store.dispatch({ type: 'CLOSE' });
      }
    };

    const handleClick = () => {
      store.dispatch({ type: 'TOGGLE' });
    };

    const Component = asChild ? Slot : 'button';

    return (
      <Component
        ref={ref as any}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        {...props}
      >
        {children ?? selectedItem ?? 'Select an option'}
      </Component>
    );
  }
);
Trigger.displayName = 'DropdownTrigger';

export interface MenuProps extends React.HTMLAttributes<HTMLUListElement> {
  asChild?: boolean;
}

export const Menu = React.forwardRef<HTMLUListElement, MenuProps>(
  ({ asChild, ...props }, ref) => {
    const isOpen = useDropdownSelector((s) => s.isOpen);
    const store = useDropdownStore();

    if (!isOpen) return null;

    const Component = asChild ? Slot : 'ul';

    return (
      <Component
        ref={ref as any}
        role="listbox"
        tabIndex={-1}
        onKeyDown={(e: React.KeyboardEvent<HTMLUListElement>) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            store.dispatch({ type: 'NAVIGATE_DOWN' });
          } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            store.dispatch({ type: 'NAVIGATE_UP' });
          } else if (e.key === 'Escape') {
            e.preventDefault();
            store.dispatch({ type: 'CLOSE' });
          }
        }}
        {...props}
      />
    );
  }
);
Menu.displayName = 'DropdownMenu';

export interface ItemProps extends React.LiHTMLAttributes<HTMLLIElement> {
  value: string;
  index: number;
  asChild?: boolean;
}

export const Item = React.forwardRef<HTMLLIElement, ItemProps>(
  ({ value, index, asChild, children, ...props }, ref) => {
    const store = useDropdownStore();
    const isHighlighted = useDropdownSelector((s) => s.highlightedIndex === index);
    const isSelected = useDropdownSelector((s) => s.selectedItem === value);

    React.useEffect(() => {
      store.dispatch({ type: 'REGISTER_ITEM', item: value });
      return () => store.dispatch({ type: 'UNREGISTER_ITEM', item: value });
    }, [store, value]);

    const Component = asChild ? Slot : 'li';

    return (
      <Component
        ref={ref as any}
        role="option"
        aria-selected={isSelected}
        data-highlighted={isHighlighted ? '' : undefined}
        onClick={() => store.dispatch({ type: 'SELECT_INDEX', index })}
        {...props}
      >
        {children ?? value}
      </Component>
    );
  }
);
Item.displayName = 'DropdownItem';
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Perusahaan SaaS FinTech Multi-Brand (beroperasi di 14 negara dengan 3 sub-brand: B2C Core, B2B Enterprise, dan Merchant Portal) mengalami degradasi performa UI dan audit kepatuhan.

* **Masalah**:
  1. Komponen Data Filter & Combobox monolitik memiliki bundle size 84KB per instance karena mengikat pustaka styling Material-UI versi lama.
  2. Terjadi render cascading ekstrem: Mengetik 1 karakter pada Autocomplete menyebabkan re-render di 150 baris tabel transaksi di bawahnya.
  3. Kegagalan audit aksesibilitas (WAI-ARIA Screen Reader nvda/VoiceOver gagal mengumumkan opsi aktif pada virtualized list).

#### Solusi Arsitektur
1. **Pemisahan Core Behavioral Primitive**:
   Mengisolasi *Combobox Machine* menggunakan arsitektur Headless UI dengan *Store-based fine-grained subscriptions*.
2. **Virtualization Integration**:
   Menghubungkan `highlightedIndex` dengan dynamic scroll anchoring via `@tanstack/react-virtual`, tetap menjaga atribut `aria-activedescendant` pada input kontrol.
3. **Penerapan Multi-Brand Theme Provider**:
   Memanfaatkan `Slot` (`asChild`) untuk memetakan class tokens tanpa me-mount DOM nodes tambahan.

#### Hasil Metrik Produksi

```
Metrik Performa & Skalabilitas:
├── Total JS Bundle (Dropdown/Combobox): 84KB  ──>  6.2KB (-92.6%)
├── Input Latency (INP - Typing Delay): 140ms ──>  11ms  (-92.1% [Good Category])
├── Virtual DOM Re-renders per keystroke: 152 nodes ──> 2 nodes (Active element only)
└── WCAG 2.2 AAA Compliance: PASSED (Zero critical violations pada Axe-Core Engine)
```

---

### 9. Trade-offs

| Pendekatan | Pros | Cons | Biaya & Dampak Sistem |
| :--- | :--- | :--- | :--- |
| **Monolithic UI (e.g., MUI, AntD)** | - Setup instan.<br>- *Out-of-the-box styling* siap pakai. | - Sulit di-rebrand.<br>- Ledakan ukuran bundle.<br>- Resiko DOM wrapper yang tebal. | Murah di awal; sangat mahal saat scaling aplikasi ke multi-brand. |
| **Pure Headless UI (In-house Engine)** | - Kontrol penuh atas arsitektur.<br>- Zero visual debt.<br>- Skalabilitas performa tinggi. | - Memerlukan engineer berkualifikasi a11y & pattern tingkat lanjut.<br>- Timeline rilis awal lebih lama. | Biaya engineering awal tinggi; *Total Cost of Ownership* (TCO) jangka panjang sangat rendah. |
| **Radix / Zag.js Adoption** | - Kepatuhan a11y teruji secara global.<br>- Kompatibel dengan Slot pattern modern. | - Ketergantungan pihak ketiga.<br>- Harus memahami mental model state machine library. | Keseimbangan optimal untuk sebagian besar tim enterprise. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. "Ref Dropping" pada Komponen Polymorphic
* **Problem**: Developer menggunakan `Slot` atau prop `as`, tetapi komponen anak merupakan *Function Component* biasa yang tidak dibungkus `React.forwardRef`.
* **Dampak**: Runtime warning: `Function components cannot be given refs. Attempts to access this ref will fail.` Fitur focus management dan auto-positioning (Floating UI) gagal total.
* **Troubleshooting & Fix**:

```typescript
// SALAH: CustomButton tidak meneruskan ref
const CustomButton = (props: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
  <button className="btn-primary" {...props} />
);

// BENAR: Menggunakan forwardRef secara eksplisit
const CustomButton = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement>>(
  (props, ref) => <button ref={ref} className="btn-primary" {...props} />
);
CustomButton.displayName = 'CustomButton';
```

#### 2. Event Handler Override Overwrite
* **Problem**: Konsumer menulis `onClick` pada anak di dalam `Slot`, menimpa logika navigasi keyboard milik komponen headless.
* **Troubleshooting**: Selalu gunakan fungsi komposisi (`composeEventHandlers`) di mana handler konsumer dipanggil terlebih dahulu. Berikan kemampuan bagi konsumer untuk membatalkan aksi internal dengan `event.preventDefault()`.

```typescript
function composeEventHandlers<E extends React.SyntheticEvent>(
  originalHandler?: (event: E) => void,
  ourHandler?: (event: E) => void,
  { checkForDefaultPrevented = true } = {}
) {
  return function handleEvent(event: E) {
    originalHandler?.(event);
    if (!checkForDefaultPrevented || !event.defaultPrevented) {
      return ourHandler?.(event);
    }
  };
}
```

#### 3. Context Trap Re-renders
* **Problem**: Mengoper state utuh lewat single `React.createContext`. Setiap kali `highlightedIndex` berubah saat menekan tombol panah, seluruh list items (misal 500 items) melakukan re-render.
* **Fix**: Pisahkan context menjadi static actions context dan subscribe state via `useSyncExternalStore` dengan atomic selector per item.

---

### 11. Best Practices (Production Checklist)

- [ ] **Type Narrowing**: Props polymorphic didukung oleh TypeScript Generics tanpa casting `as any`.
- [ ] **Slot Element Check**: Komponen Slot memvalidasi bahwa `children` bukan teks murni atau multi-nodes (`React.isValidElement` & `React.Children.only`).
- [ ] **Ref Forwarding Sanitization**: Semua primitive mengekspor ref yang terikat pada elemen DOM nyata menggunakan `composeRefs`.
- [ ] **Keyboard APG Completeness**: Mendukung seluruh matriks navigasi: `Tab`, `Shift+Tab`, `ArrowUp`, `ArrowDown`, `Home`, `End`, `Space`, `Enter`, dan `Escape`.
- [ ] **ARIA State Synchronization**: Properti reaktif (`aria-expanded`, `aria-selected`, `aria-controls`, `aria-activedescendant`) sinkron secara atomik dengan DOM state tanpa jeda 1 frame.
- [ ] **Separation of Concerns**: Nol token styling/CSS dalam layer Headless Primitives.
- [ ] **SSR Safe**: Pembangkitan IDs unik menggunakan `React.useId` untuk menghindari hydration mismatch error.

---

### 12. Hands-on Practice

Implementasikan enterprise-grade headless accordion engine dengan dukungan composable slots. Simpan seluruh implementasi ini di direktori project: `hands-on/m02/`.

#### Langkah 1: Setup Workspace
Buat struktur direktori berikut di environment Anda:
```bash
mkdir -p hands-on/m02/src/primitives/accordion
mkdir -p hands-on/m02/src/components
```

#### Langkah 2: Buat State Engine Accordion
File: `hands-on/m02/src/primitives/accordion/accordionStore.ts`
Implementasikan class `AccordionStore` dengan kemampuan konfigurasi mode `single` atau `multiple`.

```typescript
export type AccordionType = 'single' | 'multiple';

export interface AccordionState {
  value: string[];
}

export class AccordionStore {
  private state: AccordionState;
  private listeners = new Set<() => void>();
  private type: AccordionType;

  constructor(type: AccordionType = 'single', defaultValue: string[] = []) {
    this.type = type;
    this.state = { value: defaultValue };
  }

  public getSnapshot = (): AccordionState => this.state;

  public subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  public toggleItem = (itemValue: string): void => {
    const exists = this.state.value.includes(itemValue);

    if (this.type === 'single') {
      this.state = {
        value: exists ? [] : [itemValue],
      };
    } else {
      this.state = {
        value: exists
          ? this.state.value.filter((val) => val !== itemValue)
          : [...this.state.value, itemValue],
      };
    }
    this.listeners.forEach((listener) => listener());
  };
}
```

#### Langkah 3: Bangun Primitive Components
File: `hands-on/m02/src/primitives/accordion/Accordion.tsx`
Gunakan `useSyncExternalStore` dan Slot Pattern yang telah dibuat di Seksi 7.

```typescript
import * as React from 'react';
import { AccordionStore, AccordionType } from './accordionStore';
import { Slot } from '../Slot';

const AccordionContext = React.createContext<AccordionStore | null>(null);
const ItemContext = React.createContext<{ value: string; id: string } | null>(null);

export interface AccordionRootProps {
  type?: AccordionType;
  defaultValue?: string[];
  children: React.ReactNode;
}

export function Root({ type = 'single', defaultValue = [], children }: AccordionRootProps) {
  const [store] = React.useState(() => new AccordionStore(type, defaultValue));
  return <AccordionContext.Provider value={store}>{children}</AccordionContext.Provider>;
}

export function Item({ value, children }: { value: string; children: React.ReactNode }) {
  const id = React.useId();
  return <ItemContext.Provider value={{ value, id }}><div>{children}</div></ItemContext.Provider>;
}

export function Trigger({ asChild, children, ...props }: { asChild?: boolean; children: React.ReactNode }) {
  const store = React.useContext(AccordionContext);
  const item = React.useContext(ItemContext);
  if (!store || !item) throw new Error('Trigger used outside valid Provider hierarchy');

  const isExpanded = React.useSyncExternalStore(
    store.subscribe,
    () => store.getSnapshot().value.includes(item.value)
  );

  const Component = asChild ? Slot : 'button';

  return (
    <Component
      id={`trigger-${item.id}`}
      aria-controls={`content-${item.id}`}
      aria-expanded={isExpanded}
      onClick={() => store.toggleItem(item.value)}
      {...props}
    >
      {children}
    </Component>
  );
}

export function Content({ asChild, children, ...props }: { asChild?: boolean; children: React.ReactNode }) {
  const store = React.useContext(AccordionContext);
  const item = React.useContext(ItemContext);
  if (!store || !item) throw new Error('Content used outside valid Provider hierarchy');

  const isExpanded = React.useSyncExternalStore(
    store.subscribe,
    () => store.getSnapshot().value.includes(item.value)
  );

  if (!isExpanded) return null;

  const Component = asChild ? Slot : 'div';

  return (
    <Component
      id={`content-${item.id}`}
      role="region"
      aria-labelledby={`trigger-${item.id}`}
      {...props}
    >
      {children}
    </Component>
  );
}
```

---

### 13. Exercise

#### Level 1 (Easy): Focus Visible Ring Injection via Slot
* **Instruksi**: Tambahkan kemampuan ke komponen `Slot` untuk mendeteksi apakah child menerima event focus dari keyboard (`:focus-visible`), kemudian secara dinamis menyuntikkan data attribute `data-focus-visible="true"` tanpa memicu state re-render tambahan.
* **Kriteria Keberhasilan**: Atribut `data-focus-visible` muncul pada elemen DOM saat diakses via tabulasi keyboard, tetapi tidak muncul saat diklik via mouse.

#### Level 2 (Medium): Type-Safe Polymorphic Box Component
* **Instruksi**: Buat komponen polymorphic `Box` dengan TypeScript Generic yang memiliki batasan: jika props `as="button"` diberikan, props wajib menerima tipe native button HTML. Jika diberikan `as={Link}` dari router pihak ketiga, tipe props Link harus terinferensi otomatis beserta validasi prop generic-nya.
* **Kriteria Keberhasilan**: Editor TypeScript menghasilkan autocompletion akurat dan melempar *compiler error* jika developer mengisi `href` pada komponen saat didefinisikan `as="button"`.

#### Level 3 (Hard): Context Selector with Dependency Tracking (Micro-Proxy)
* **Instruksi**: Rancang hooks `useTrackedSelector` menggantikan `useSyncExternalStore` sederhana. Gunakan JavaScript `Proxy` untuk merekam properti objek state mana saja yang diakses oleh komponen selama phase rendering, dan hanya picu re-render jika field yang diakses tersebut berubah nilainya (*granular shallow comparison*).
* **Kriteria Keberhasilan**: Perubahan pada `store.highlightedIndex` tidak boleh memicu rendering ulang komponen yang hanya mengakses `store.isOpen`.

---

### 14. Challenge

Rancang arsitektur **Headless Multi-Level Hierarchical TreeView** (`role="tree"`) skala enterprise dengan spesifikasi ketat:
1. **Dukungan Virtualisasi**: Harus mampu menangani 100.000 nodes bertingkat tak terbatas (*infinite nested nodes*) menggunakan dynamic node flattening algorithm.
2. **Keyboard Trapping & APG Compliance**:
   * Panah Bawah/Atas: Pindah ke baris node visual berikutnya tanpa peduli level kedalamannya.
   * Panah Kanan: Buka branch node yang tertutup; jika sudah terbuka, pindah ke child pertamanya.
   * Panah Kiri: Tutup branch node yang terbuka; jika sudah tertutup, lompat langsung ke parent node-nya.
   * Navigasi Karakter: Ketik "abc" untuk langsung melompat ke node dengan awalan tersebut dalam selang waktu buffer 500ms.
3. **Zero Rendering Cascades**: Node yang terbuka/tertutup tidak boleh menyebabkan komponen parent atau sibling me-render ulang DOM tree yang lain.
4. **Bebas Komponen Wrapper Visual**: Seluruh DOM Tree dirender melalui `asChild` Slot, memungkinkan styling dinamis via utility library apa pun tanpa style coupling.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. Apa fungsi utama arsitektur Headless UI dalam enterprise design systems?
   * A. Menghapus kebutuhan CSS di seluruh aplikasi.
   * B. Memisahkan logika state/aksesibilitas dari presentasi visual agar dapat digunakan kembali secara fleksibel.
   * C. Menghindari pemakaian React Hooks dalam komponen modern.
   * D. Mengganti Virtual DOM dengan direct DOM manipulation engine.
   * *Jawaban:* **B**. Headless UI memisahkan state & a11y dari visual layer.

2. Masalah apa yang dipecahkan oleh Slot pattern (`asChild`) dibandingkan wrapper HTML tradisional?
   * A. Mencegah error memory leak pada garbage collector.
   * B. Mengurangi komputasi CPU browser saat parsing JSON.
   * C. Menghilangkan elemen pembungkus (DOM wrapper hell) dan meneruskan props/refs langsung ke anak target.
   * D. Menjamin CSS module selalu ter-compile secara inline.
   * *Jawaban:* **C**. Mencegah `<div>` berlebih dan memproyeksikan props langsung ke elemen target.

3. Mengapa `React.Children.only` sering digunakan di dalam implementasi engine `Slot`?
   * A. Agar React dapat menjalankan multithreading optimization.
   * B. Untuk memvalidasi bahwa Slot hanya menerima tepat satu child valid React element.
   * C. Memastikan child komponen tidak memiliki dependency lifecycle.
   * D. Mengubah elemen child menjadi native string.
   * *Jawaban:* **B**. Slot mensyaratkan single element target agar props merge tidak ambigu.

4. Kapan waktu yang tepat untuk memanfaatkan `useSyncExternalStore` pada library UI Component?
   * A. Setiap kali ingin melakukan HTTP fetch request ke backend.
   * B. Saat ingin berlangganan ke state store eksternal secara atomik guna mencegah render tearing dan render cascades.
   * C. Menggantikan seluruh peran `useEffect` dalam aplikasi.
   * D. Saat membuat animasi CSS berbasis JavaScript frame loop.
   * *Jawaban:* **B**. Menghubungkan external store ke React dengan jaminan thread-safety / tanpa render tearing.

5. Apa tujuan implementasi utilitas `composeRefs` pada pembuatan polymorphic component?
   * A. Menjalankan garbage collection otomatis pada elemen DOM.
   * B. Menggabungkan ref internal komponen dengan ref yang dipass oleh konsumer dari luar.
   * C. Mencegah komponen anak menerima ref dari parent.
   * D. Mengubah object ref menjadi primitive number.
   * *Jawaban:* **B**. Memastikan baik internal engine maupun consumer bisa mengakses native DOM node bersamaan.

#### Intermediate (5 Pertanyaan)
6. Apa konsekuensi buruk dari menggabungkan event handler dengan cara `props.onClick = internalClick` tanpa menggunakan komposisi?
   * A. Runtime Type Error: Memory buffer overflow.
   * B. Event handler konsumer akan ter-overwrite sehingga logic konsumer tidak akan pernah tereksekusi.
   * C. Synthetic Event React akan otomatis crash dan menyebabkan white-screen.
   * D. Komponen me-render DOM sebanyak 2 kali.
   * *Jawaban:* **B**. Handler konsumer tertimpa oleh handler internal jika tidak di-compose.

7. Bagaimana TypeScript menangani tipe props pada polymorphic component dengan prop `as`?
   * A. Menggunakan Dynamic Variable Injection.
   * B. Menggunakan TypeScript Generics yang dipetakan ke `React.ElementType` dengan type exclusion (`Omit<ComponentProps, ...>`).
   * C. Mentranspile seluruh prop ke tipe `any` saat runtime.
   * D. Memaksa konsumer membuat type interface manual setiap kali rendering.
   * *Jawaban:* **B**. Generics dengan tipe penolakan (`Omit`) menjamin tidak ada duplikasi dan type narrowing tepat.

8. Atribut ARIA manakah yang wajib ada pada elemen `trigger` dropdown untuk memenuhi standar WAI-ARIA 1.2?
   * A. `role="navigation"` dan `aria-live="polite"`.
   * B. `aria-haspopup` dan `aria-expanded`.
   * C. `aria-hidden="true"` dan `aria-selected`.
   * D. `aria-level` dan `aria-setsize`.
   * *Jawaban:* **B**. `aria-haspopup` menandai relasi popup dan `aria-expanded` mengindikasikan status buka/tutup.

9. Mengapa penggunaan standard `React.createContext` murni sering memicu masalah performa pada Compound Components berskala besar?
   * A. Context membatasi kuota memori browser hingga 50MB.
   * B. Setiap perubahan nilai sekecil apa pun pada Context Value object akan mere-render seluruh komponen consumer tanpa terkecuali.
   * C. Context berjalan di luar Web Worker thread.
   * D. Context tidak dapat dipadukan dengan TypeScript Generic.
   * *Jawaban:* **B**. React Context default me-render ulang seluruh subscriber saat reference value berubah.

10. Jika konsumen memanggil `event.preventDefault()` pada custom handler di elemen anak, bagaimana arsitektur Headless UI Slot harus merespons?
    * A. Melempar runtime exception ke console.
    * B. Mengabaikan tindakan user dan tetap mengeksekusi aksi bawaan.
    * C. Mengecek `event.defaultPrevented`; jika true, batalkan eksekusi internal headless action selanjutnya.
    * D. Memaksa refresh halaman browser.
    * *Jawaban:* **C**. Menghormati *Inversion of Control*, memungkinkan konsumer membatalkan behavior internal.

#### Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario 1**: Sebuah tim membangun modal dialog berbasis headless primitive. Namun, ketika pengguna menggunakan Screen Reader (NVDA) dan menekan tombol `Tab`, fokus navigasi keluar dari modal dan berpindah ke navbar aplikasi utama di balik overlay. Masalah mendasar apa yang terjadi dan bagaimana perbaikan arsitekturalnya?
    * *Jawaban/Analisis*: Terjadi ketiadaan **Focus Trap mechanism**. Sesuai standar WAI-ARIA Dialog (Modal), dialog harus menangkap event `keydown` (Tab dan Shift+Tab). Arsitektur harus mendeteksi seluruh elemen *focusable* di dalam modal, lalu mengunci navigasi: jika fokus ada di elemen focusable terakhir dan ditekan `Tab`, alihkan fokus paksa ke elemen focusable pertama (dan sebaliknya untuk `Shift+Tab`). Selain itu, elemen di luar modal harus diberi atribut `aria-hidden="true"` atau menggunakan library native dialog `inert`.

12. **Skenario 2**: Pada implementasi design system enterprise, tim Anda menemukan bahwa bundle size komponen form meningkat drastis setelah mengekspor wrapper styling yang mendukung 40 variasi props visual. Bagaimana strategi refactoring menggunakan materi modul ini untuk mereduksi bundle size tanpa mengorbankan fleksibilitas tim visual?
    * *Jawaban/Analisis*: 
      1. Tarik seluruh visual props dari komponen inti dan turunkan komponen menjadi **Headless UI Primitives** murni.
      2. Terapkan **Slot Pattern (`asChild`)**. Biarkan styling ditangani oleh styling utilities terpisah (misal: Variant utility seperti `cva` - Class Variance Authority).
      3. Komponen inti form hanya mengekspor logic ARIA, validasi, dan event lifecycle. Dengan demikian, *logic engine* tetap ramping (small bundle), *tree-shakeable*, dan varian visual dipecah menjadi static CSS/Tailwind classes di level konsumer.

13. **Skenario 3**: Sebuah data-table virtual menampilkan 10.000 data rows. Setiap baris memiliki menu dropdown individual yang dibangun menggunakan custom Compound Component dengan React Context. Saat menu di baris ke-10 dibuka, terjadi UI freeze selama ~300ms (INP gagal). DevTools Profiler menunjukkan 10.000 rows melakukan render ulang secara serempak. Bagaimana Anda mengeliminasi bottleneck ini secara definitif?
    * *Jawaban/Analisis*: Masalahnya adalah penyatuan state dropdown ke Context level atas atau satu store global yang didengarkan oleh setiap baris data. 
      Solusi:
      1. Pindahkan instance state context ke tingkat lokal per baris (isolasi Context scope agar hanya membungkus satu button dan menu per baris).
      2. Jika menu harus berpusat di luar viewport (portal) untuk menghindari `overflow: hidden`, gunakan arsitektur **External Store Selector** berbasis id: tiap baris hanya subscribe ke selector `store.activeMenuId === row.id`. Komponen baris hanya me-render ulang jika nilai boolean hasil selector tersebut berubah (dari `false` menjadi `true` atau sebaliknya), sehingga hanya 2 rows yang me-render ulang (baris yang baru dibuka dan baris yang sebelumnya ditutup), menekan re-render dari 10.000 menjadi 2 nodes.

---

### 16. Summary

```
                      ENTERPRISE HEADLESS UI MATRIX
┌───────────────────────┬────────────────────────────────────────────────────────┐
│ Separation of Layer   │ Logic (Hooks/Store) != Attribute (ARIA) != Style (Slot)│
├───────────────────────┼────────────────────────────────────────────────────────┤
│ Composition Primitive │ Slot (`asChild`) over Nesting Wrappers (Zero DOM Debt) │
├───────────────────────┼────────────────────────────────────────────────────────┤
│ Rendering Performance │ Fine-Grained Subscription (`useSyncExternalStore`)      │
├───────────────────────┼────────────────────────────────────────────────────────┤
│ Accessibility Standard│ W3C WAI-ARIA APG Strict Keyboard & Focus Contracts     │
└───────────────────────┴────────────────────────────────────────────────────────┘
```

Penerapan pola *Headless UI*, *Slot Pattern*, dan *Fine-Grained Context Subscription* merupakan standar baku dalam perancangan frontend berskala enterprise. Melalui pemisahan yang tegas antara logika perilaku komponen (behavioral layer) dan representasi visual (presentational layer), sistem frontend memperoleh ketahanan tinggi terhadap perubahan visual, performa optimal yang bebas dari render cascades, serta kepatuhan penuh terhadap standar aksesibilitas internasional.