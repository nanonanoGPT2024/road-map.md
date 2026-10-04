# BAB 05: Component Primitives dan Headless UI Architecture
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang & Mengimplementasikan Headless State Machines**: Membangun state machine UI headless berbasis *micro-reducer* dan *finite-state automata* untuk komponen kompleks (Combobox, Nested Cascading Menu, TreeView).
- **Menguasai Mekanisme Polymorphic & Slot Engine**: Mengimplementasikan *pattern* polymorphic Radix-style `Slot` vs `as` prop secara type-safe menggunakan TypeScript meta-programming tingkat lanjut (`ComponentPropsWithRef`, template literal types, distributed conditional types).
- **Mengembangkan Focus Management & Spatial Navigation Engine**: Mengonstruksi sistem roving tabindex, active-descendant focus virtualization, serta non-leaking dynamic focus trap untuk nested overlay stacks.
- **Mengintegrasikan Custom Positioning & Virtualization Pipeline**: Menghubungkan headless primitives dengan positioning engine (subpixel floating/anchoring math) dan viewport virtualization tanpa mengorbankan accessibility tree (ARIA 1.2).
- **Mengevaluasi & Mengoptimalkan Re-render Footprint**: Mengeliminasi context thrashing menggunakan atomic micro-stores, memoization bailout, dan context selector internal.

---

### 2. Prerequisites
Sebelum mendalami modul ini, Anda wajib memiliki pemahaman solid pada domain:
- **TypeScript Advanced**: Invariant/Covariant/Contravariant typing, Generic Parameter Defaults, Conditional Types, Type Narrowing, Discriminated Unions.
- **W3C WAI-ARIA 1.2 Specifications**: Pola desain keyboard interaction matrix untuk `combobox`, `dialog`, `menu`, `treegrid`, dan implementasi accessibility live regions (`aria-live`).
- **DOM Level 3 Events & Coordinate Systems**: Penanganan pointer events, synthetic events, bounding client rect calculation, visual vs layout viewports, stacking context (`z-index` and isolation rules).
- **React Internals**: Reconciler tree traversal, Fiber lifecycles, SyntheticEvent bubbling phases, `useInsertionEffect`/`useLayoutEffect` synchronization guarantees.

---

### 3. Concept & Internal Architecture

Arsitektur Headless UI tingkat enterprise memisahkan sebuah komponen visual menjadi empat lapisan decoupled:

```
+-----------------------------------------------------------------------+
|                    CONSUMER COMPONENT (Skin / Theme)                 |
|            Tailwind, CSS Modules, Styled Components, etc.             |
+-----------------------------------------------------------------------+
                                    │
                                    ▼
+-----------------------------------------------------------------------+
|                     HEADLESS COMPOSITION LAYER                        |
|            Polymorphic Elements, Slot Engine, Context API             |
+-----------------------------------------------------------------------+
         │                                              │
         ▼                                              ▼
+-----------------------------+          +------------------------------+
|     STATE & LOGIC ENGINE    |          |      ACCESSIBILITY & I/O     |
| - Finite State Automata     |          | - Focus Trap & Restoration   |
| - Micro-store / PubSub      |          | - Roving TabIndex Manager    |
| - Selection & Cursor State  |          | - Viewport Spatial Engine    |
+-----------------------------+          +------------------------------+
```

#### 3.1. Slot Engine & Polymorphic Mechanics
Pendekatan konvensional `as="button"` menciptakan masalah kompilasi TypeScript (*type inference explosion*) ketika props komponen dasar bertabrakan dengan props tag target. Pola modern menggunakan **Slot Composition Engine** (dikenal dari Radix UI). 

Slot Engine bekerja dengan konsep *clone-and-merge*: jika komponen primitif menerima `asChild={true}`, alih-alih me-render tag HTML bawaan, primitif tersebut mencegat *immediate child element*, menggabungkan (*merging*) props internal (seperti `aria-expanded`, event handler `onClick`, `onKeyDown`, dan `ref`) ke child tersebut tanpa menambah wrapper `<div>` tambahan di DOM tree.

#### 3.2. Focus Management Engine: Roving TabIndex vs Active Descendant
Untuk komponen berbasis koleksi (Menu, Listbox, Grid), ada dua paradigma navigasi keyboard:
1. **Roving TabIndex**: Hanya satu item dalam list yang memiliki `tabIndex={0}`, sementara item lainnya diset ke `tabIndex={-1}`. Saat tombol panah ditekan, focus DOM aktual berpindah menggunakan `.focus()` ke node elemen berikutnya, dan nilai `tabIndex` dimutasi secara reaktif.
2. **Active Descendant (`aria-activedescendant`)**: Elemen input/container tetap memegang DOM focus (`tabIndex={0}`). Navigasi panah hanya memutasi atribut `aria-activedescendant="item-id-n"`. Browser memetakan fokus virtual ini ke Accessibility API (Screen Reader) tanpa menggerakkan DOM focus sesungguhnya. Model ini esensial ketika mengintegrasikan *virtual scrolling* (virtualized lists) di mana node DOM fisik belum di-render.

#### 3.3. Positioning Engine Lifecycle
Elemen *floating* (popover, dropdown) memerlukan siklus hidup kalkulasi anchoring yang sinkron:
1. **Anchor Discovery**: Deteksi posisi bounding box elemen pemicu (`triggerRect`).
2. **Floating Measurement**: Pengukuran dimensi elemen overlay sebelum di-render ke user (`floatingRect`).
3. **Collision Detection**: Deteksi tabrakan koordinat terhadap *clipping boundary* atau *viewport edge*.
4. **Flip & Shift Fallback**: Penyesuaian axis koordinat (misal: jika `bottom` overflow, flip ke `top`; jika tepi kanan terpotong, shift koordinat horizontal).
5. **Subpixel Antialiasing Rounding**: Pembulatan koordinat integer berbasis `window.devicePixelRatio` untuk menghindari teks blur akibat transform GPU acceleration.

---

### 4. Why & What

| Dimensi | Headless UI Primitives | Monolithic Component Libraries (MUI/AntD) |
| :--- | :--- | :--- |
| **Kopling Styling** | **Zero-styling**. Mengeluarkan struktur semantic dan atribut ARIA murni. | **Tight coupling**. Membawa CSS-in-JS atau runtime stylesheet sendiri. |
| **Customizability** | **Total**. Pengembang mengontrol 100% markup dan CSS class/tokens. | **Terbatas**. Bergantung pada `theme override`, `css injection`, atau `!important`. |
| **Bundle Size Overhead** | **Ultra-lightweight**. Tree-shakeable, hanya menyertakan logic yang digunakan. | **Heavy**. Seringkali mengikutsertakan runtime styling engine kompleks. |
| **Aksessibilitas (a11y)** | **Standard-compliant by default**. Mematuhi WAI-ARIA authoring practices. | Bervariasi. Rentan regresi saat custom styling merusak accessibility tree. |
| **Adaptabilitas Multi-Platform** | **Tinggi**. Logika hooks dapat digunakan ulang di React Native/Web. | **Rendah**. Web-DOM specific. |

---

### 5. How: Architectural Workflow

Diagram alur berikut mengilustrasikan transisi state dan event flow dari interaksi pengguna pada headless combobox:

```
[User Types Char] ───► [Combobox State Engine]
                             │
                             ├──► Validasi Input & Filter Data
                             ├──► Transisi State ke "OPEN"
                             ├──► Set 'aria-expanded=true'
                             │
                             ▼
[Floating Layout Sync] ◄─────┤
  │                          │
  ├─ Hitung Koordinat Viewport│
  └─ Update Posisi via Transform
                             │
                             ▼
[Focus Coordination] ◄───────┘
  │
  ├─ Update 'aria-activedescendant="opt-x"'
  └─ Virtual Scroll Window Sync -> Auto-scroll to index
```

1. **Event Interception**: Event listener internal pada root/input mencegat payload keyboard native (`keydown`).
2. **State Transition**: Finite State Machine menentukan validitas state change (misal: tombol `ArrowDown` memindahkan pointer dari state `Idle` ke `Navigating`).
3. **Ref Synchronization**: Sinkronisasi referensi DOM internal antara trigger, dropdown portal, dan scrolling container tanpa memicu cascading re-renders.
4. **Portal Rendering & Trap Execution**: Overlay di-mount ke React Portal terisolasi, mengunci loop fokus (jika modal) menggunakan boundary nodes.
5. **Attribute Mutation**: Modifikasi reaktif pada `aria-*` attributes disalurkan ke node DOM akhir via props-getter atau merged props slot.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Mobil Modern (Drive-by-Wire)
Bayangkan merancang supercar:
- **Monolithic UI**: Beli sedan utuh dari pabrik. Anda tidak bisa mengganti bodi sedan menjadi truk tanpa memotong sasis dan merusak garansi serta fitur keselamatan pabrik.
- **Headless UI Primitives**: Anda hanya membeli **Sasis, Mesin, Suspensi, Rem ABS, dan Sistem Kemudi Elektronik (Drive-by-Wire)**. Seluruh komponen mekanis dan komputasi keselamatan sudah tervalidasi ISO. Desainer eksterior bebas memasang bodi serat karbon, kayu, atau baja tanpa mempengaruhi fungsi rem ABS atau suspensi mobil.

```
       HEADLESS ENGINE ARCHITECTURE (Composite Slot Pattern)

  <Dropdown.Root>
  │  (Context: State Machine, Floating Controller, Focus Coordinator)
  │
  ├─── <Dropdown.Trigger asChild>
  │    │
  │    └── [ Button (Consumer Design Token) ]
  │         - Merged Props: onClick, aria-haspopup, aria-expanded, ref
  │
  └─── <Dropdown.Portal>
       │
       └── <Dropdown.Content asChild>
            │
            └── [ Popover Card (Consumer Floating Surface) ]
                 │   - Position: absolute / fixed (Transformed via Hook)
                 │   - Role: "menu", aria-orientation: "vertical"
                 │   - Event: onKeyDown (Trap arrow keys)
                 │
                 ├── <Dropdown.Item asChild>
                 │    └── [ MenuItem "Profile" ] -> tabIndex: -1 / 0
                 │
                 └── <Dropdown.Item asChild>
                      └── [ MenuItem "Logout" ]  -> tabIndex: -1 / 0
```

---

### 7. Implementation Examples

#### 7.1. Simple Example: Type-Safe Radix-Style Slot Engine
Mengimplementasikan pattern `Slot` dan `SlotClone` untuk dynamic child prop merging tanpa wrapper node tambahan.

```typescript
// primitives/Slot.tsx
import * as React from 'react';

export interface SlotProps extends React.HTMLAttributes<HTMLElement> {
  children?: React.ReactNode;
}

export const Slot = React.forwardRef<HTMLElement, SlotProps>((props, forwardedRef) => {
  const { children, ...slotProps } = props;

  if (React.isValidElement(children)) {
    return React.cloneElement(children, {
      ...mergeProps(slotProps, children.props as any),
      ref: forwardedRef ? composeRefs(forwardedRef, (children as any).ref) : (children as any).ref,
    });
  }

  if (React.Children.count(children) > 1) {
    throw new Error('Slot engine hanya mendukung tepat 1 single React element child.');
  }

  return null;
});

Slot.displayName = 'Slot';

// Utilitas penggabungan handler event dan styling classes
function mergeProps(parentProps: Record<string, any>, childProps: Record<string, any>) {
  const overrideProps = { ...childProps };

  for (const propName in parentProps) {
    const parentValue = parentProps[propName];
    const childValue = childProps[propName];

    if (/^on[A-Z]/.test(propName)) {
      if (parentValue && childValue) {
        overrideProps[propName] = (...args: unknown[]) => {
          childValue(...args);
          parentValue(...args);
        };
      } else if (parentValue) {
        overrideProps[propName] = parentValue;
      }
    } else if (propName === 'className') {
      overrideProps[propName] = [parentValue, childValue].filter(Boolean).join(' ');
    } else if (propName === 'style') {
      overrideProps[propName] = { ...parentValue, ...childValue };
    } else {
      overrideProps[propName] = childValue !== undefined ? childValue : parentValue;
    }
  }

  return { ...parentProps, ...overrideProps };
}

// Utilitas composition ref untuk multi-subscriber ref pattern
function composeRefs<T>(...refs: (React.Ref<T> | undefined)[]) {
  return (node: T) => {
    refs.forEach((ref) => {
      if (!ref) return;
      if (typeof ref === 'function') {
        ref(node);
      } else {
        (ref as React.MutableRefObject<T | null>).current = node;
      }
    });
  };
}
```

#### 7.2. Practical Example: Headless Autocomplete Combobox dengan ARIA 1.2
Komponen Combobox headless lengkap dengan roving active-descendant, keyboard loop isolation, dan focus restoration.

```typescript
// primitives/combobox/useCombobox.ts
import * as React from 'react';

export interface ComboboxItem {
  id: string;
  label: string;
  disabled?: boolean;
}

interface UseComboboxProps<T extends ComboboxItem> {
  items: T[];
  onSelect: (item: T) => void;
  isOpenDefault?: boolean;
}

export function useCombobox<T extends ComboboxItem>({
  items,
  onSelect,
  isOpenDefault = false,
}: UseComboboxProps<T>) {
  const [isOpen, setIsOpen] = React.useState(isOpenDefault);
  const [activeIndex, setActiveIndex] = React.useState<number>(-1);
  const [query, setQuery] = React.useState('');
  
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const listboxId = React.useId();

  const enabledItems = React.useMemo(() => {
    return items.map((item, index) => ({ ...item, originalIndex: index }))
      .filter((item) => !item.disabled);
  }, [items]);

  const selectItem = React.useCallback((item: T) => {
    if (item.disabled) return;
    setQuery(item.label);
    onSelect(item);
    setIsOpen(false);
    setActiveIndex(-1);
    inputRef.current?.focus();
  }, [onSelect]);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    switch (event.key) {
      case 'ArrowDown': {
        event.preventDefault();
        if (!isOpen) {
          setIsOpen(true);
          setActiveIndex(0);
        } else {
          setActiveIndex((prev) => (prev + 1 < enabledItems.length ? prev + 1 : 0));
        }
        break;
      }
      case 'ArrowUp': {
        event.preventDefault();
        if (!isOpen) {
          setIsOpen(true);
          setActiveIndex(enabledItems.length - 1);
        } else {
          setActiveIndex((prev) => (prev - 1 >= 0 ? prev - 1 : enabledItems.length - 1));
        }
        break;
      }
      case 'Enter': {
        if (isOpen && activeIndex >= 0 && enabledItems[activeIndex]) {
          event.preventDefault();
          selectItem(items[enabledItems[activeIndex].originalIndex]);
        }
        break;
      }
      case 'Escape': {
        if (isOpen) {
          event.preventDefault();
          setIsOpen(false);
          setActiveIndex(-1);
        }
        break;
      }
      case 'Tab': {
        if (isOpen) {
          setIsOpen(false);
          setActiveIndex(-1);
        }
        break;
      }
    }
  };

  const getActiveDescendantId = () => {
    if (!isOpen || activeIndex < 0 || !enabledItems[activeIndex]) return undefined;
    return `${listboxId}-option-${enabledItems[activeIndex].originalIndex}`;
  };

  const getInputProps = () => ({
    ref: inputRef,
    role: 'combobox' as const,
    'aria-autocomplete': 'list' as const,
    'aria-expanded': isOpen,
    'aria-controls': listboxId,
    'aria-activedescendant': getActiveDescendantId(),
    value: query,
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
      setQuery(e.target.value);
      if (!isOpen) setIsOpen(true);
      setActiveIndex(0);
    },
    onKeyDown: handleKeyDown,
  });

  const getListboxProps = () => ({
    id: listboxId,
    role: 'listbox' as const,
    'aria-label': 'Suggestions',
  });

  const getItemProps = (item: T, index: number) => {
    const isSelected = enabledItems[activeIndex]?.originalIndex === index;
    return {
      id: `${listboxId}-option-${index}`,
      role: 'option' as const,
      'aria-selected': isSelected,
      'aria-disabled': item.disabled,
      onClick: () => selectItem(item),
      onMouseEnter: () => {
        if (!item.disabled) {
          const enabledIdx = enabledItems.findIndex((e) => e.originalIndex === index);
          if (enabledIdx !== -1) setActiveIndex(enabledIdx);
        }
      },
    };
  };

  return {
    isOpen,
    setIsOpen,
    query,
    activeIndex: enabledItems[activeIndex]?.originalIndex ?? -1,
    getInputProps,
    getListboxProps,
    getItemProps,
  };
}
```

```tsx
// Consumer Implementasi (Industrial Skin)
import * as React from 'react';
import { useCombobox, ComboboxItem } from './useCombobox';

interface TechStackItem extends ComboboxItem {
  runtime: string;
}

const DATA: TechStackItem[] = [
  { id: '1', label: 'React 19 Core', runtime: 'Client/Server' },
  { id: '2', label: 'Rust WebAssembly', runtime: 'Wasm Edge' },
  { id: '3', label: 'Golang Microservices', runtime: 'Container Native' },
  { id: '4', label: 'PostgreSQL Distributed', disabled: true, runtime: 'Database Engine' },
];

export function EnterpriseSearchPalette() {
  const {
    isOpen,
    getInputProps,
    getListboxProps,
    getItemProps,
    activeIndex,
  } = useCombobox({
    items: DATA,
    onSelect: (item) => console.log('Selected Payload:', item),
  });

  return (
    <div style={{ width: '400px', position: 'relative', fontFamily: 'sans-serif' }}>
      <label htmlFor="search-input" style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>
        Runtime Architecture Lookup
      </label>
      <input
        id="search-input"
        {...getInputProps()}
        placeholder="Type framework..."
        style={{
          width: '100%',
          padding: '8px 12px',
          border: '1px solid #ccc',
          borderRadius: 4,
          outline: 'none',
        }}
      />
      {isOpen && (
        <ul
          {...getListboxProps()}
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            background: '#ffffff',
            border: '1px solid #ddd',
            borderRadius: 4,
            margin: '4px 0 0 0',
            padding: 0,
            listStyle: 'none',
            boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
            zIndex: 1000,
          }}
        >
          {DATA.map((item, index) => {
            const itemProps = getItemProps(item, index);
            const isActive = activeIndex === index;
            return (
              <li
                key={item.id}
                {...itemProps}
                style={{
                  padding: '8px 12px',
                  cursor: item.disabled ? 'not-allowed' : 'pointer',
                  backgroundColor: isActive ? '#f0f7ff' : '#ffffff',
                  color: item.disabled ? '#999' : '#111',
                  borderLeft: isActive ? '3px solid #0066cc' : '3px solid transparent',
                  display: 'flex',
                  justifyContent: 'space-between',
                }}
              >
                <span>{item.label}</span>
                <span style={{ fontSize: '0.8em', color: '#666' }}>{item.runtime}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
```

---

### 8. Real World Case Study: Unified Multi-Brand Enterprise Migration

#### 8.1. Konteks Masalah
Sebuah konglomerat platform FinTech global mengoperasikan 3 core apps:
- **Brand A**: Enterprise B2B Treasury Portal (Density tinggi, dark theme, styling Tailwind).
- **Brand B**: Consumer Micro-lending App (Design playful, rounded, styling CSS Modules).
- **Brand C**: White-label Banking Portal (Dynamic runtime branding berbasis customer token CSS-in-JS).

Sebelumnya, ketiga tim membangun komponen dropdown, modal, dan listbox masing-masing menggunakan wrapper dari UI kit yang berbeda (MUI, Semantic UI, custom `<select>` hack). Hal ini mengakibatkan:
- **WCAG Audit Failure**: 47 violation a11y terkait keyboard entrapment dan penanganan screen reader yang salah pada modal tier-2.
- **Maintenance Cost**: Ketika regulasi perbankan mewajibkan auto-logout confirmation modal di seluruh portal, engineering membutuhkan 4 bulan kalender untuk propagasi.

#### 8.2. Solusi Rekayasa
Core Architecture Guild mengabstraksi semua interaksi visual menjadi **Enterprise Headless Primitives Library (`@corp/primitives`)**:
- `@corp/primitives` dibuat berbasis **Zero CSS Engine**.
- Semua state navigasi keyboard divalidasi menggunakan XState internal.
- Polymorphism ditangani secara eksklusif via custom `Slot` engine yang bebas dependensi.
- Masing-masing brand membuat adapter visual wrapper tipis:
  - `@corp/b2b-ui` membungkus primitives dengan styling Tailwind class.
  - `@corp/consumer-ui` membungkus primitives dengan PandaCSS tokens.
  - `@corp/whitelabel-ui` membungkus primitives dengan dynamic inline custom properties.

#### 8.3. Hasil Arsitektural & Metrik Produksi
- **Zero Accessibility Non-compliance**: Audit WAI-ARIA 1.2 menghasilkan skor 100% lulus di Axe-core dan evaluasi manual NVDA/JAWS.
- **Bundle Size Drop**: Ukuran rata-rata modul shared components turun dari 142 KB (akibat runtime CSS-in-JS MUI lama) menjadi 14.8 KB gzipped per application bundle.
- **Engineering Velocity**: Propagasi security compliance alert modal antar 3 brand selesai dalam 3 hari kerja tanpa mengubah logika state/keyboard navigation sama sekali.

---

### 9. Trade-offs

```
  +-------------------------------------------------------------------------+
  |              KOMPLEKSITAS ARSITEKTUR vs FLEKSIBILITAS                    |
  +-------------------------------------------------------------------------+
  | [Rendah]                                                      [Tinggi]  |
  | Monolithic UI Kit                Custom Hooks           Slot Primitives  |
  | (e.g. AntD/MUI)                  (e.g. React-Aria)      (e.g. Radix UI) |
  |                                                                         |
  | Bundled Style, No Setup          Logika Lepas,          Total Visual    |
  | Zero Dev Ergonomics Setup        Markup Bebas,          Freedom, API    |
  | Kaku, Bundle Gendut              JSX Kurang Deklaratif  Compound Bersih |
  +-------------------------------------------------------------------------+
```

| Matriks Keputusan | Slot Primitive Pattern | Compound Component Pattern (Context) | Custom Hooks Pure (`useX`) |
| :--- | :--- | :--- | :--- |
| **Render Performance** | Sangat Tinggi (No intermediate DOM, no mandatory Context cascades). | Menengah (Beresiko Context thrashing jika root re-render). | Tertinggi (Eksekusi logic direct inline). |
| **Developer Ergonomics** | Superior (Declarative JSX: `<Modal.Trigger asChild>`). | Superior (Declarative JSX: `<Modal.Trigger>`). | Menengah (Banyak manual prop spreading boilerplate). |
| **Type Safety Strictness** | Kompleks (Perlu handling recursive generic types untuk ref). | Terisolasi (Prop typing statis per elemen). | Sederhana (Return plain typed props). |
| **Code Footprint** | Kecil. | Sedang (Perlu create context per level primitif). | Minimal (Hanya logic function). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Props Merging Overwrite pada `onClick` dan Event Listeners
*Problem*: Menggabungkan props child dan parent tanpa eksekusi berantai (*chaining*), sehingga salah satu event handler tertimpa dan tidak pernah tereksekusi.
```typescript
// ❌ SALAH: Child onClick tertimpa parent props
const mergedProps = { ...child.props, ...parentProps };

//  BENAR: Eksekusi berantai dengan pencegahan default event bubbling
const mergedOnClick = (e: React.MouseEvent) => {
  child.props.onClick?.(e);
  if (!e.defaultPrevented) {
    parentProps.onClick?.(e);
  }
};
```

#### Kesalahan 2: Context Re-render Cascading pada Input Frequent Typing
*Problem*: Menyimpan state `query` input search di dalam Context root headless combobox. Setiap keystroke memicu re-render pada seluruh cabang tree hingga item-item listbox.
*Solusi Arsitektur*: Pisahkan Context menjadi 2 boundary:
1. `ComboboxStateContext` (Menyimpan item list statis dan state `isOpen`).
2. `ComboboxActiveDescendantContext` (Atomic subscribe / micro-store subscription yang hanya di-subscribe oleh item yang sedang aktif).

#### Kesalahan 3: Multiple Ref Conflict pada Polymorphic Wrappers
*Problem*: Developer meneruskan forwardedRef dari consumer, namun primitif headless juga membutuhkan instance node DOM aktual untuk mengukur posisi bounding box atau focus loop.
*Solusi*: Wajib menggunakan pola **Ref Composition (`composeRefs`)**:
```typescript
const internalRef = React.useRef<HTMLElement | null>(null);
const combinedRef = useComposedRefs(forwardedRef, internalRef);
return <Comp ref={combinedRef} />;
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Polymorphic Ref Guarantee**: Komponen primitif selalu meneruskan ref asli ke elemen DOM fisik terbawah tanpa merusak functional/callback refs.
- [ ] **ARIA 1.2 Compliance Matrix**:
  - [ ] Role `combobox` dipasangkan dengan `aria-controls`, `aria-expanded`, dan `aria-haspopup="listbox"`.
  - [ ] Listbox memiliki role `listbox` dan item memiliki role `option`.
  - [ ] Item aktif ditandai secara visual dan terhubung via `aria-activedescendant`.
- [ ] **Focus Trap Non-Destructive Bailout**: Saat modal/overlay unmount, kembalikan fokus DOM ke elemen pemicu awal (`triggerRef.current?.focus()`).
- [ ] **Zero Styling Rule**: Engine primitif tidak boleh menginjeksi inline style atribut font, warna, margin, atau layout structure selain komputasi koordinat penempatan absolut (`transform`, `top`, `left`).
- [ ] **SSR Safe IDs**: Gunakan `React.useId()` untuk mengaitkan atribut pairing `aria-labelledby`, `aria-describedby`, dan `aria-controls` guna mencegah hydration mismatch ID antara server dan client.

---

### 12. Hands-on Practice: Building a Zero-Dependency Headless Cascading Menu

Implementasikan modul latihan berikut pada repositori lokal Anda:
Direktori kerja: `hands-on/m02/`

#### Struktur Proyek:
```
hands-on/m02/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── src/
    ├── primitives/
    │   ├── composeRefs.ts
    │   ├── Slot.tsx
    │   └── MenuPrimitive.tsx
    ├── components/
    │   └── EnterpriseMenu.tsx
    └── App.tsx
```

#### Langkah 1: `src/primitives/composeRefs.ts`
Implementasikan utility composer ref tingkat industri:
```typescript
import * as React from 'react';

type PossibleRef<T> = React.Ref<T> | undefined;

export function composeRefs<T>(...refs: PossibleRef<T>[]) {
  return (node: T) => {
    let hasCleanups = false;
    const cleanups = refs.map((ref) => {
      if (!ref) return undefined;
      if (typeof ref === 'function') {
        const cleanup = ref(node);
        if (typeof cleanup === 'function') {
          hasCleanups = true;
          return cleanup;
        }
      } else {
        (ref as React.MutableRefObject<T | null>).current = node;
      }
      return undefined;
    });

    if (hasCleanups) {
      return () => {
        cleanups.forEach((cleanup) => {
          if (typeof cleanup === 'function') cleanup();
        });
      };
    }
  };
}

export function useComposedRefs<T>(...refs: PossibleRef<T>[]) {
  return React.useCallback(composeRefs(...refs), refs);
}
```

#### Langkah 2: `src/primitives/MenuPrimitive.tsx`
Bangun Compound Primitive Headless Menu dengan Spatial Keyboard Navigation (ArrowUp, ArrowDown, ArrowRight, ArrowLeft):
```typescript
import * as React from 'react';
import { Slot } from './Slot';
import { useComposedRefs } from './composeRefs';

interface MenuContextValue {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  activeIndex: number;
  setActiveIndex: React.Dispatch<React.SetStateAction<number>>;
  items: React.RefObject<HTMLElement[]>;
  registerItem: (node: HTMLElement) => () => void;
}

const MenuContext = React.createContext<MenuContextValue | null>(null);

function useMenuContext() {
  const ctx = React.useContext(MenuContext);
  if (!ctx) throw new Error('Menu compound component harus berada dalam MenuPrimitive.Root');
  return ctx;
}

export function Root({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  const [activeIndex, setActiveIndex] = React.useState(-1);
  const items = React.useRef<HTMLElement[]>([]);

  const registerItem = React.useCallback((node: HTMLElement) => {
    if (!node) return () => {};
    items.current.push(node);
    return () => {
      items.current = items.current.filter((el) => el !== node);
    };
  }, []);

  return (
    <MenuContext.Provider
      value={{ open, setOpen, activeIndex, setActiveIndex, items, registerItem }}
    >
      <div style={{ position: 'relative', display: 'inline-block' }}>{children}</div>
    </MenuContext.Provider>
  );
}

export interface TriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

export const Trigger = React.forwardRef<HTMLButtonElement, TriggerProps>(
  ({ asChild, ...props }, forwardedRef) => {
    const { open, setOpen, items, setActiveIndex } = useMenuContext();
    const Component = asChild ? Slot : 'button';

    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
      props.onClick?.(e);
      if (!e.defaultPrevented) {
        setOpen((prev) => {
          const next = !prev;
          if (next) setActiveIndex(0);
          return next;
        });
      }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
      props.onKeyDown?.(e);
      if (e.defaultPrevented) return;
      if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        setOpen(true);
        setActiveIndex(0);
      }
    };

    return (
      <Component
        aria-haspopup="menu"
        aria-expanded={open}
        {...props}
        ref={forwardedRef}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
      />
    );
  }
);
Trigger.displayName = 'MenuPrimitive.Trigger';

export interface ContentProps extends React.HTMLAttributes<HTMLDivElement> {
  asChild?: boolean;
}

export const Content = React.forwardRef<HTMLDivElement, ContentProps>(
  ({ asChild, ...props }, forwardedRef) => {
    const { open, setOpen, activeIndex, setActiveIndex, items } = useMenuContext();
    const contentRef = React.useRef<HTMLDivElement | null>(null);
    const composedRef = useComposedRefs(forwardedRef, contentRef);

    React.useEffect(() => {
      if (open && activeIndex >= 0 && items.current[activeIndex]) {
        items.current[activeIndex].focus();
      }
    }, [open, activeIndex]);

    if (!open) return null;

    const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
      props.onKeyDown?.(e);
      if (e.defaultPrevented) return;

      const total = items.current.length;
      if (total === 0) return;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setActiveIndex((prev) => (prev + 1 < total ? prev + 1 : 0));
          break;
        case 'ArrowUp':
          e.preventDefault();
          setActiveIndex((prev) => (prev - 1 >= 0 ? prev - 1 : total - 1));
          break;
        case 'Escape':
          e.preventDefault();
          setOpen(false);
          setActiveIndex(-1);
          break;
      }
    };

    const Component = asChild ? Slot : 'div';

    return (
      <Component
        role="menu"
        tabIndex={-1}
        {...props}
        ref={composedRef}
        onKeyDown={handleKeyDown}
      />
    );
  }
);
Content.displayName = 'MenuPrimitive.Content';

export interface ItemProps extends React.HTMLAttributes<HTMLDivElement> {
  asChild?: boolean;
  disabled?: boolean;
}

export const Item = React.forwardRef<HTMLDivElement, ItemProps>(
  ({ asChild, disabled = false, ...props }, forwardedRef) => {
    const { registerItem, setOpen } = useMenuContext();
    const itemRef = React.useRef<HTMLDivElement | null>(null);
    const composedRef = useComposedRefs(forwardedRef, itemRef);

    React.useEffect(() => {
      if (itemRef.current && !disabled) {
        return registerItem(itemRef.current);
      }
    }, [disabled, registerItem]);

    const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
      props.onClick?.(e);
      if (!disabled && !e.defaultPrevented) {
        setOpen(false);
      }
    };

    const Component = asChild ? Slot : 'div';

    return (
      <Component
        role="menuitem"
        tabIndex={-1}
        aria-disabled={disabled}
        {...props}
        ref={composedRef}
        onClick={handleClick}
      />
    );
  }
);
Item.displayName = 'MenuPrimitive.Item';
```

#### Langkah 3: Testing Integrasi Consumer
Implementasikan di `src/components/EnterpriseMenu.tsx` menggunakan CSS Modules atau utility class pilihan Anda dan jalankan dev server (`vite`) untuk memverifikasi fungsionalitas navigasi arrow loop dan focus management.

---

### 13. Exercises

#### Level 1 (Easy) - Type-Safe Accessible Tooltip Primitive
Buat primitif headless `useTooltip` yang mengembalikan props untuk trigger dan content dengan spesifikasi:
- Content ditampilkan ketika trigger menerima event `onFocus` atau `onMouseEnter`.
- Content disembunyikan saat `onBlur` atau `onMouseLeave`, atau ketika tombol `Escape` ditekan.
- Atribut pengait `aria-describedby` pada trigger harus secara otomatis sinkron dengan ID konten tooltip.

#### Level 2 (Medium) - Roving TabIndex RadioGroup Primitive
Rancang headless compound component `RadioGroup` (`RadioGroup.Root` dan `RadioGroup.Item`) yang menggunakan mekanisme **Roving TabIndex**:
- Elemen terpilih (`checked`) mendapatkan `tabIndex={0}`, sementara radio item lainnya diset ke `tabIndex={-1}`.
- Navigasi keyboard `ArrowDown`/`ArrowRight` memindahkan seleksi dan fokus DOM ke radio item berikutnya.
- Navigasi keyboard `ArrowUp`/`ArrowLeft` memindahkan seleksi dan fokus DOM ke radio item sebelumnya.
- Wajib membungkus state menggunakan context selector agar pergantian item terpilih tidak me-re-render seluruh radio list.

#### Level 3 (Hard) - Multi-level Nested Submenu Primitive dengan Spatial Traversal
Bangun ekstensi dari modul hands-on di atas untuk mendukung **Submenu bertingkat**:
- Submenu terbuka jika tombol panah kanan (`ArrowRight`) ditekan pada parent item pembawa submenu.
- Submenu tertutup dan fokus kembali ke parent menu jika tombol panah kiri (`ArrowLeft`) ditekan di dalam submenu.
- Perhitungan penutupan submenu harus menerapkan algoritma **Pointer Vector Aiming** (segitiga deteksi kursor mouse) untuk mencegah submenu tertutup tanpa sengaja ketika pointer melintasi item lain saat bergerak diagonal menuju child menu.

---

### 14. Complex Architectural Challenge
*(Studi Kasus Produksi Skala Besar Tanpa Solusi Instan)*

**Skenario**:
Anda adalah Principal Frontend Architect di sebuah platform Observability & Monitoring global sekelas Datadog. Tim Anda sedang membangun **Command Palette & Omnibox Query Engine** yang terpasang di seluruh platform.

**Kebutuhan Spesifikasi Teknis**:
1. **Virtual DOM Domination**: Palette harus mampu merender hingga 150.000 metrik series secara virtualized (`virtual scrolling`) dengan frame rate konstan 60 FPS tanpa freezing pada frame input.
2. **Accessible Tree Consistency**: Walaupun elemen DOM virtual di-unmount dari visual tree, screen reader harus tetap mampu membaca total index item, status active cursor item, dan group boundary via accessibility tree (`aria-setsize`, `aria-posinset`, dan `aria-activedescendant`).
3. **Cross-Window Floating Anchor**: Command Palette dapat di-*pop out* (dipisahkan menjadi window browser terpisah melalui Native Window API `window.open()`) seraya mempertahankan single React context state, focus restoration pipeline, dan keyboard coordination engine.

**Tugas Anda**:
Tuliskan cetak biru arsitektur lengkap (*technical specification document*) yang mencakup:
- Struktur state graph engine (finite state machine model).
- Desain abstraksi DOM Event Listener lintas context multi-window.
- Mekanisme memory pooling untuk item virtualization agar GC (Garbage Collection) pause time tetap berada di bawah 4 milidetik per frame interaksi.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level (5 Soal)
1. **Apa perbedaan mendasar antara pola polymorphic `as` prop konvensional dengan Radix-style `asChild` (Slot)?**
   *Jawaban*: Pola `as` prop me-render tag target baru dan sering memicu masalah resolusi type TypeScript ketika atribut tag bertabrakan, sedangkan `asChild` tidak me-render tag baru melainkan menyuntikkan props dan listener secara transparan ke satu-satunya elemen anak (child) menggunakan teknik *clone-and-merge*.
2. **Kapan sebaiknya arsitek UI memilih pendekatan Headless UI Primitive dibandingkan Monolithic UI Library?**
   *Jawaban*: Ketika aplikasi memerlukan kebebasan styling 100% tanpa overhead CSS-in-JS, mendukung standarisasi multi-brand/multi-theme, mematuhi audit a11y yang sangat ketat, atau menghindari dependensi visual kit yang rentan breaking change pada layout.
3. **Mengapa `tabIndex={-1}` penting dalam implementasi Roving TabIndex?**
   *Jawaban*: Nilai `-1` mengeluarkan elemen dari urutan tab sequensial keyboard default (`Tab` key), namun tetap memungkinkan elemen tersebut menerima fokus secara programatik via script (`.focus()`).
4. **Apa fungsi dari `React.useId()` dalam pembangunan komponen primitif accessible?**
   *Jawaban*: Untuk menghasilkan identifier unik yang stabil di server dan client sehingga menghindari terjadinya React hydration mismatch saat menghubungkan elemen kontrol dengan label/deskripsinya (misal: `aria-controls` dan `id`).
5. **Mengapa kita tidak boleh membungkus child element di dalam `Slot` dengan `<div>` tambahan?**
   *Jawaban*: Penambahan `<div>` wrapper dapat merusak semantic layout HTML (misal: `<button>` di dalam `<div>` di dalam `<ul>`), mengacaukan struktur flexbox/grid layout consumer, dan merusak relasi parent-child pada accessibility tree.

#### Intermediate Level (5 Soal)
6. **Jelaskan perbedaan mendasar penanganan fokus antara *Roving TabIndex* dan *aria-activedescendant*!**
   *Jawaban*: Roving TabIndex memindahkan fokus DOM aktual antar elemen (mengubah `tabIndex` elemen aktif menjadi `0` dan yang lain `-1` serta memanggil `.focus()`), sedangkan `aria-activedescendant` mempertahankan fokus DOM pada elemen container/input dan hanya menginformasikan ke accessibility tree node virtual mana yang sedang aktif melalui referensi ID.
7. **Bagaimana cara mencegah race conditions saat beberapa ref digabungkan menggunakan custom hook `composeRefs`?**
   *Jawaban*: Fungsi merger ref harus mengeksekusi masing-masing callback atau mutable object setter secara iteratif berurutan, dan mengembalikan single cleanup function jika ref bertipe function callback mengembalikan pembersihan ref (dukungan React 19 ref cleanup).
8. **Apa yang menyebabkan terjadinya "Context Re-render Thrashing" pada implementasi Headless State Compound Components?**
   *Jawaban*: Menyatukan mutable state yang sering berubah (misal: cursor pointer hover position atau teks input typing) dengan konfigurasi state statis (misal: metadata item atau orientation props) dalam satu Context Provider tunggal tanpa context splitting atau selector memoization.
9. **Bagaimana cara menangani *Focus Restoration* yang aman saat modal primitif ditutup?**
   *Jawaban*: Catat referensi elemen aktif DOM (`document.activeElement`) sesaat sebelum modal dibuka ke dalam closure/ref, lalu pada saat lifecycle unmount jalankan `.focus()` kembali pada node elemen referensi tersebut secara asinkron atau via `requestAnimationFrame` untuk memastikan overlay selesai di-unmount.
10. **Mengapa penggunaan inline callback function pada props `Slot` dapat merusak performa render jika tidak di-memoize dengan benar?**
    *Jawaban*: Karena penggabungan handler event via helper merging membuat reference function baru di setiap render parent, yang akan mematikan optimasi `React.memo` pada child komponen jika child mengandalkan referensi props yang stabil (*shallow equality check*).

#### Production Scenarios (3 Soal)

11. **Skenario 1**: Di lingkungan staging aplikasi FinTech, tim QA melaporkan bahwa dropdown menu headless sering kali tidak merespons klik pada lingkungan mobile touch, sedangkan pada laptop click berfungsi normal. Kode menggunakan listener `onKeyDown` dan `onClick` murni pada Trigger. Apa penyebabnya dan bagaimana arsitektur penanganannya?
    *Jawaban Arsitektural*: Pointer events handling tidak terabstraksi. Browser mobile menangani urutan event `touchstart` -> `touchend` -> synthetic `click` (terkadang dengan delay 300ms atau pembatalan jika terjadi scroll gesture). Solusinya adalah mengikat listener menggunakan abstraction Pointer Event API (`onPointerDown` dengan pengecekan `e.button === 0` dan pemanggilan `e.preventDefault()` terkontrol untuk mencegah sintetik click ghosting), serta menyinkronkan event pemicu terhadap state `pointerType` ('touch' | 'mouse' | 'pen').

12. **Skenario 2**: Anda memiliki Dropdown Overlay yang di-mount via Portal ke akhir tag `<body>`. Ketika Dropdown terbuka di dalam Modal dialog yang memiliki focus trap aktif, fokus pengguna tiba-tiba terlempar keluar dan trap modal mengalami infinite loop error. Mengapa hal ini terjadi dan bagaimana solusinya?
    *Jawaban Arsitektural*: Terjadi tubrukan antara dua Focus Trap engine terpisah (*Stack Trap Contention*). Modal dialog menganggap node Dropdown Portal di luar hierarki DOM-nya sebagai "klik di luar" atau "elemen luar", sehingga Trap Modal mencoba menarik paksa fokus kembali ke dalam dirinya. Solusinya: Implementasikan **Layered/Nested Overlay Stack Context Registry**. Ketika Dropdown Portal dibuka dari dalam context Modal, Dropdown mendaftarkan nodenya ke Modal sebagai nested child boundary yang sah, atau Trap Modal induk dialihkan ke mode suspended (paused) sementara waktu hingga child overlay di-unmount.

13. **Skenario 3**: Sebuah implementasi headless combobox dengan 5.000 list item menyebabkan waktu render keyboard interaction (*key-to-paint latency*) mencapai 120 milidetik, menciptakan lag ketik yang sangat mengganggu (INP metric buruk). Setelah diperiksa, setiap penekanan `ArrowDown` memicu re-render pada seluruh 5.000 node item JSX. Bagaimana langkah refactoring Anda?
    *Jawaban Arsitektural*: 
    1. Ganti paradigma navigasi dari per-node state props menjadi **Virtual Active Descendant**: node tidak lagi menerima prop boolean `isActive` individual.
    2. Container listbox memegang satu atribut tunggal: `aria-activedescendant={activeId}`.
    3. Hentikan styling berbasis props; gunakan CSS Selector murni berbasis attribute state, misal: `&[data-active="true"]` atau gunakan selector CSS `:has()` / `:focus-visible`.
    4. Implementasikan viewport DOM virtualization (seperti `@tanstack/react-virtual`) sehingga hanya 20-30 node fisik yang berada di DOM, menurunkan re-render lifecycle cost ke batas <16 milidetik.

---

### 16. Summary
- **Pondasi Headless**: Memisahkan kalkulasi interaksi (FSM), penanganan accessibility tree (ARIA 1.2), dan navigasi spatial dari representasi grafis (styling/markup).
- **Slot Composition Engine**: Pola `asChild` mengeliminasi *wrapper hell* dan konflik polymorphic props TypeScript dengan menyuntikkan fungsionalitas langsung ke immediate child via smart *props & ref merger*.
- **Focus Sovereignty**: Komponen enterprise mutlak memiliki focus management deterministik; memadukan roving tabindex atau active-descendant focus virtualization dengan auto-restoration loop untuk menjamin compliance WCAG AAA.
- **Performance Boundary**: Pisahkan context yang sering terpicu mutasi event (seperti text cursor atau typing state) dari context statis arsitektur guna mencegah cascading re-render thrashing di skala aplikasi enterprise.