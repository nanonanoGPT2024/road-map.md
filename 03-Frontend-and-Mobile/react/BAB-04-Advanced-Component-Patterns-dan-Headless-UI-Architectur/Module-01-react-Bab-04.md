# Bab 04 Module 01: Advanced Component Patterns & Headless UI Architecture

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Frontend and Mobile Engineering (`03-Frontend-and-Mobile`)
*   **Mata Pelajaran:** Advanced React Core Architecture
*   **Modul:** Bab 04 Modul 01 — Advanced Component Patterns & Headless UI Architecture
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** Pemahaman mendalam mengenai React Core (Reconciliation, Fiber Architecture, Hooks Lifecycle), TypeScript Generics & Mapped Types, Variadic Tuples, Accessibility (WAI-ARIA 1.2), dan DOM Event Bubbling/Capture Phases.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1.  **Mendekomposisi dan Mengabstraksi State:** Memisahkan *behavior*, *state machine*, dan *accessibility layer* secara penuh dari representasi visual (*presentation/styling*) menggunakan metodologi Headless UI.
2.  **Mengimplementasikan Pola Tingkat Lanjut:** Menguasai implementasi *Compound Components*, *Custom Controlled/Uncontrolled Inversion*, *State Reducer Pattern*, dan *Prop Getters* dengan inferensi tipe TypeScript yang ketat.
3.  **Mencegah Anti-Patterns Desain:** Mengeliminasi *prop drilling*, *boolean explosion* (prop antipattern seperti `isDropdown`, `isLarge`, `hasIcon`), serta fragmentasi state rendering via Context API optimization.
4.  **Menjamin Aksesibilitas Terintegrasi:** Mengembangkan komponen headless yang mematuhi standar WAI-ARIA APG (Authoring Practices Guide) secara deterministik tanpa mengorbankan fleksibilitas styling konsumen kode.
5.  **Membangun Primitive UI Enterprise-Grade:** Mengotomatisasi penanganan event composition, referential stability, focus management, dan slotting architecture siap pakai untuk Design System skala enterprise.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa front-end modern, komponen sering kali dibebani oleh tiga tanggung jawab sekaligus:
1.  **State & Lifecycle Management** (Kapan menu terbuka, item mana yang aktif).
2.  **Accessibility & Event Wiring** (Penanganan keyboard navigation, ARIA attributes, focus trapping).
3.  **Visual Presentation & DOM Semantics** (CSS classes, layout Tailwind, ikon, rendering HTML tags).

Penggabungan ketiga domain ini menciptakan kode yang rapuh (*brittle*). Ketika tim desain meminta perubahan visual dari *dropdown standar* menjadi *modal sheet responsive*, pengembang sering kali harus menulis ulang seluruh logika state dan aksesibilitasnya.

```
Pendekatan Klasik (Coupled):
┌────────────────────────────────────────────────────────┐
│ <Select />                                             │
│ ┌────────────────────────────────────────────────────┐ │
│ │ State Logic + A11y Attributes + CSS/DOM Markup     │ │
│ └────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
          ▼ (Sulit di-maintain, rapuh, zero flexibility)

Pendekatan Headless Architecture (Decoupled):
┌────────────────────────────────────────────────────────┐
│ State Engine & A11y Core (Headless Primitive Hook)     │
│  - State Machine (Open/Closed/Focused)                │
│  - Keyboard Navigation & ARIA Prop Getters             │
└──────────────────────────┬─────────────────────────────┘
                           │ Menyediakan fungsionalitas murni
        ┌──────────────────┴──────────────────┐
        ▼                                     ▼
┌──────────────────────────┐       ┌──────────────────────────┐
│ Desktop Combobox View    │       │ Mobile Bottom-Sheet View │
│ (Floating UI + Tailwind) │       │ (Framer Motion + Radix)  │
└──────────────────────────┘       └──────────────────────────┘
```

**Mental Model Headless UI:** Anggap komponen UI sebagai *mesin komputasi tak terlihat* (invisibles state engine). Komponen tersebut tidak peduli apakah ia dirender sebagai elemen `<div>`, `<button>`, canvas, atau bahkan terminal CLI. Komponen hanya bertugas menerima interaksi, menghitung state berikutnya, dan mengekspos atribut ARIA serta event handlers ke elemen presentasi melalui *Prop Getters* atau *Compound Context*.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram aliran eksekusi untuk Compound Component dengan Prop Getters dan State Reducer:

```
[User Event: Keyboard Down Arrow]
               │
               ▼
   [Consumer Native Element] (e.g. <input {...getInputProps()} />)
               │
               │ (1) Event Interception via composeEventHandlers()
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ HEADLESS HOOK ENGINE                                                    │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ User Custom Handler (e.g., onKeyDown dari Props)                   │  │
│  │ -> Apakah event.defaultPrevented == true?                         │  │
│  └──────────────────┬────────────────────────────────────────────────┘  │
│                     │ No                                                │
│                     ▼                                                   │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ State Reducer Pipeline                                            │  │
│  │                                                                   │  │
│  │ Action: { type: 'NAVIGATE_DOWN' }                                 │  │
│  │ Current State: { highlightedIndex: 0, isOpen: true }              │  │
│  │                                                                   │  │
│  │ Invocations:                                                      │  │
│  │ internalReducer(state, action)                                    │  │
│  │       │                                                           │  │
│  │       ▼                                                           │  │
│  │ customReducerOverride?(state, action) <── [Consumer Interception] │  │
│  │       │                                                           │  │
│  │       ▼ Returns: Next Calculated State                            │  │
│  │ { highlightedIndex: 1, isOpen: true }                             │  │
│  └──────────────────┬────────────────────────────────────────────────┘  │
│                     │                                                   │
│                     ▼                                                   │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Apply Controlled/Uncontrolled Sync via onChange Notification      │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ REACT RENDER CYCLE                                                      │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Context Provider Value Update (Memoized Slice)                    │  │
│  └──────────────────┬────────────────────────────────────────────────┘  │
│                     │                                                   │
│                     ▼                                                   │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Subscribed Compound Children Re-render:                           │  │
│  │  - <Listbox.Option index={0} /> -> aria-selected="false"          │  │
│  │  - <Listbox.Option index={1} /> -> aria-selected="true"           │  │
│  │  - DOM Focus/ScrollIntoView Sync via layoutEffect                 │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Compound Components
Pola di mana sekumpulan komponen bekerja sama secara deklaratif untuk mengelola state implisit bersama melalui React Context. Alih-alih meneruskan data kompleks melalui props tunggal:
```tsx
// Anti-Pattern: Monolithic Config Props
<Select options={items} isOpen={isOpen} onSelect={fn} renderItem={...} />

// Pro-Pattern: Compound Components
<Select value={value} onChange={setValue}>
  <Select.Trigger />
  <Select.Content>
    <Select.Option value="1">Item 1</Select.Option>
  </Select.Content>
</Select>
```

### 2. Prop Getters vs. Spread Props
Jika render props menyuplai atribut mentah:
```tsx
// Rentan bug overriding handlers:
<button {...props} onClick={myCustomHandler} /> // myCustomHandler dapat menghapus props.onClick internal
```
*Prop Getters* membungkus atribut dan menggabungkan fungsi (*event composition*) secara mulus:
```tsx
// Aman: Menjamin event internal dan eksternal dieksekusi secara berurutan
<button {...getTriggerProps({ onClick: myCustomHandler })} />
```

### 3. State Reducer Pattern
Pola pembalikan kontrol (*Inversion of Control*) mutlak di mana konsumen dapat mengintersepsi aksi internal komponen dan mengubah state transisi sebelum React menerapkannya ke virtual DOM.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Event Handler Chaining Tanpa Kerusakan Side Effect
Masalah umum saat merancang headless library adalah: *Bagaimana cara menjalankan logika internal komponen (seperti menutup popup saat tombol Escape ditekan) sembari mengizinkan konsumen menyuntikkan logika bisnis mereka sendiri pada event handler yang sama?*

Jawabannya adalah **Higher-Order Event Composition**.
Rumus matematis/fungsional untuk event composition:
$$f_{composed}(e) = f_{consumer}(e) \to (\neg e.defaultPrevented \implies f_{internal}(e))$$

Jika konsumen memanggil `event.preventDefault()`, komponen headless akan membatalkan transisi state internal. Mekanisme ini memberikan kontrol penuh kepada konsumen.

```typescript
function composeEventHandlers<E extends React.SyntheticEvent | Event>(
  consumerHandler?: (event: E) => void,
  internalHandler?: (event: E) => void
) {
  return (event: E) => {
    consumerHandler?.(event);
    if (!event.defaultPrevented) {
      internalHandler?.(event);
    }
  };
}
```

### Controlled vs Uncontrolled Dual-State Synchronization
Sebuah komponen headless tingkat enterprise harus mampu bekerja secara *uncontrolled* (menggunakan internal state default) maupun *controlled* (state didorong sepenuhnya oleh parent props) tanpa mengubah API permukaan.

Pergeseran dari *uncontrolled* ke *controlled* sering menimbulkan React warning jika diimplementasikan dengan naif:
`Warning: A component is changing an uncontrolled input to be controlled.`

Untuk mengatasinya secara arsitektural, gunakan abstraksi internal state yang memprioritaskan props jika terdefinisi (`value !== undefined`), dan jatuh kembali (*fallback*) ke internal state jika tidak:

$$\text{ActiveState} = \begin{cases} \text{PropsState}, & \text{jika } \text{PropsState} \neq \text{undefined} \\ \text{InternalState}, & \text{lainnya} \end{cases}$$

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Implementasi hook dasar Headless Toggle menggunakan pola **Prop Getters** dan **State Reducer**.

```typescript
import * as React from 'react';

// 1. Tipe Aksi dan State
export interface ToggleState {
  on: boolean;
}

export type ToggleAction =
  | { type: 'TOGGLE' }
  | { type: 'RESET'; payload: boolean }
  | { type: 'SET_ON'; payload: boolean };

export type ToggleReducer = (state: ToggleState, action: ToggleAction) => ToggleState;

// 2. Default Internal Reducer
const defaultToggleReducer: ToggleReducer = (state, action) => {
  switch (action.type) {
    case 'TOGGLE':
      return { on: !state.on };
    case 'RESET':
    case 'SET_ON':
      return { on: action.payload };
    default:
      return state;
  }
};

// 3. Helper Utility: Compose Handlers
export function callAll<E extends React.SyntheticEvent | Event>(
  ...fns: Array<((event: E) => void) | undefined>
) {
  return (event: E) => {
    for (const fn of fns) {
      fn?.(event);
      if (event.defaultPrevented) {
        break;
      }
    }
  };
}

// 4. Props dan Return Interface
export interface UseToggleProps {
  initialOn?: boolean;
  reducer?: ToggleReducer;
  onChange?: (on: boolean) => void;
}

export interface ButtonPropsGetter extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  [key: string]: unknown;
}

export function useToggle({
  initialOn = false,
  reducer = defaultToggleReducer,
  onChange,
}: UseToggleProps = {}) {
  const [{ on }, dispatch] = React.useReducer(reducer, { on: initialOn });

  const isFirstMount = React.useRef(true);
  React.useEffect(() => {
    if (isFirstMount.current) {
      isFirstMount.current = false;
      return;
    }
    onChange?.(on);
  }, [on, onChange]);

  const toggle = React.useCallback(() => dispatch({ type: 'TOGGLE' }), []);
  const setOn = React.useCallback((value: boolean) => dispatch({ type: 'SET_ON', payload: value }), []);
  const reset = React.useCallback(() => dispatch({ type: 'RESET', payload: initialOn }), [initialOn]);

  // Prop Getter: Menyediakan struktur ARIA & Composition
  const getTogglerProps = React.useCallback(
    <Props extends ButtonPropsGetter>({
      onClick,
      ...otherProps
    }: Props = {} as Props): ButtonPropsGetter => {
      return {
        'type': 'button',
        'aria-pressed': on,
        onClick: callAll<React.MouseEvent<HTMLButtonElement>>(onClick, () => toggle()),
        ...otherProps,
      };
    },
    [on, toggle]
  );

  return {
    on,
    toggle,
    setOn,
    reset,
    getTogglerProps,
  };
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah analisis struktural dari implementasi di Seksi 07:

1.  **Baris 24-34 (`callAll`)**:
    Fungsi utilitas fungsional yang melakukan iterasi array fungsi handler. Apabila konsumen mengeksekusi `event.preventDefault()`, iterasi berhenti (`break`), membatalkan fungsi internal toggle berikutnya.
2.  **Baris 48 (`React.useReducer(reducer, { on: initialOn })`)**:
    Komponen tidak melakukan mutasi langsung via `useState`, melainkan mengalirkan komputasi state ke sebuah fungsi reducer murni. Konsumen dapat mengganti reducer ini dengan *custom reducer* mereka sendiri.
3.  **Baris 50-57 (`isFirstMount` effect)**:
    Mencegah pemanggilan callback `onChange` pada render pertama (*initial mount*), memastikan event hanya dipicu oleh mutasi state nyata yang diinisiasi oleh interaksi pengguna atau dispatch terkontrol.
4.  **Baris 63-76 (`getTogglerProps`)**:
    *Core Prop Getter Pattern*. Fungsi ini mengembalikan objek properti yang dapat langsung di-spread pada tag native button. 
5.  **Baris 70 (`'aria-pressed': on`)**:
    Menyuntikkan atribut WAI-ARIA secara otomatis untuk merepresentasikan status toggle ke assistive technology (screen reader).
6.  **Baris 71 (`callAll(onClick, () => toggle())`)**:
    Mengomposisikan *consumer click handler* (`onClick`) dengan *internal state mutator* (`toggle()`) secara aman.

---

## SEKSI 09 — STUDI KASUS NYATA

### Konteks Kasus
Sebuah platform perbankan investasi digital (FinTech Enterprise) memerlukan komponen **Accessible Autocomplete/Combobox** untuk memilih instrumen perdagangan (Ticker Saham, Obligasi). 

### Problem Statement
1.  **Strict Performance Constraints:** Data instrumen mencapai ribuan item; re-rendering seluruh dropdown tree membuat pengetikan input menjadi *lagging* (> 50ms).
2.  **Strict Accessibility (Audit Compliance):** Sistem harus lolos uji WAI-ARIA 1.2 Combobox with Both List and Inline Autocomplete. Fokus keyboard (Up, Down, Home, End, Escape, Enter) dan sinkronisasi `aria-activedescendant` bersifat mutlak menurut regulasi ADA Section 508.
3.  **UI Fragmentation:** Tim Web menggunakan Tailwind CSS murni, tim Pro-Trading Terminal menggunakan Dark-Themed High-Density Material, namun keduanya **wajib** berbagi core logic yang sama untuk mencegah disparitas bug validasi.

### Arsitektur Solusi
Membangun Headless Combobox Primitive yang terdiri dari:
-   `useComboboxCore` Engine (Custom hook dengan Reducer & State Control).
-   Context Compound Parent (`ComboboxRoot`, `ComboboxInput`, `ComboboxList`, `ComboboxOption`).
-   Inversi kontrol navigasi keyboard berbasis Virtual Focusing (`aria-activedescendant`) tanpa memindahkan fokus fisik DOM (`document.activeElement`) dari input pencarian.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA

Berikut adalah implementasi penuh tingkat produksi menggunakan TypeScript murni tanpa modul eksternal.

```tsx
import * as React from 'react';

// ==========================================
// 1. DOM UTILITIES & TYPES
// ==========================================

export interface ComboboxOptionItem {
  id: string;
  value: string;
  label: string;
  disabled?: boolean;
}

export interface ComboboxState<T extends ComboboxOptionItem> {
  isOpen: boolean;
  highlightedIndex: number;
  selectedItem: T | null;
  inputValue: string;
}

export type ComboboxAction<T extends ComboboxOptionItem> =
  | { type: 'INPUT_CHANGE'; payload: string }
  | { type: 'ITEM_CLICK'; payload: T }
  | { type: 'NAVIGATE'; payload: number }
  | { type: 'OPEN' }
  | { type: 'CLOSE' }
  | { type: 'RESET' };

export type ComboboxStateReducer<T extends ComboboxOptionItem> = (
  state: ComboboxState<T>,
  action: ComboboxAction<T>
) => ComboboxState<T>;

function composeEvents<E extends React.SyntheticEvent | Event>(
  userHandler?: (e: E) => void,
  internalHandler?: (e: E) => void
) {
  return (e: E) => {
    userHandler?.(e);
    if (!e.defaultPrevented) {
      internalHandler?.(e);
    }
  };
}

// ==========================================
// 2. CORE HEADLESS ENGINE (HOOK)
// ==========================================

export interface UseComboboxProps<T extends ComboboxOptionItem> {
  items: T[];
  itemToString?: (item: T | null) => string;
  onSelectedItemChange?: (item: T | null) => void;
  stateReducer?: ComboboxStateReducer<T>;
  initialSelectedItem?: T | null;
}

export function useComboboxCore<T extends ComboboxOptionItem>({
  items,
  itemToString = (item) => (item ? item.label : ''),
  onSelectedItemChange,
  stateReducer,
  initialSelectedItem = null,
}: UseComboboxProps<T>) {
  const defaultReducer: ComboboxStateReducer<T> = (state, action) => {
    switch (action.type) {
      case 'INPUT_CHANGE':
        return {
          ...state,
          isOpen: true,
          inputValue: action.payload,
          highlightedIndex: items.findIndex((i) => !i.disabled),
        };
      case 'ITEM_CLICK':
        return {
          ...state,
          isOpen: false,
          selectedItem: action.payload,
          inputValue: itemToString(action.payload),
          highlightedIndex: -1,
        };
      case 'NAVIGATE':
        return {
          ...state,
          highlightedIndex: action.payload,
        };
      case 'OPEN':
        return {
          ...state,
          isOpen: true,
          highlightedIndex: state.selectedItem
            ? items.findIndex((i) => i.id === state.selectedItem?.id)
            : items.findIndex((i) => !i.disabled),
        };
      case 'CLOSE':
        return {
          ...state,
          isOpen: false,
          highlightedIndex: -1,
          inputValue: state.selectedItem ? itemToString(state.selectedItem) : '',
        };
      case 'RESET':
        return {
          isOpen: false,
          highlightedIndex: -1,
          selectedItem: null,
          inputValue: '',
        };
      default:
        return state;
    }
  };

  const combinedReducer = React.useCallback(
    (s: ComboboxState<T>, a: ComboboxAction<T>) => {
      const nextState = defaultReducer(s, a);
      return stateReducer ? stateReducer(nextState, a) : nextState;
    },
    [stateReducer, items, itemToString]
  );

  const [state, dispatch] = React.useReducer(combinedReducer, {
    isOpen: false,
    highlightedIndex: -1,
    selectedItem: initialSelectedItem,
    inputValue: itemToString(initialSelectedItem),
  });

  const generatedId = React.useId();
  const listboxId = `combobox-listbox-${generatedId}`;
  const inputId = `combobox-input-${generatedId}`;

  // Notify parent upon item selection
  const previousSelected = React.useRef(state.selectedItem);
  React.useEffect(() => {
    if (previousSelected.current !== state.selectedItem) {
      previousSelected.current = state.selectedItem;
      onSelectedItemChange?.(state.selectedItem);
    }
  }, [state.selectedItem, onSelectedItemChange]);

  // Prop Getters
  const getInputProps = React.useCallback(
    (props: React.InputHTMLAttributes<HTMLInputElement> = {}) => {
      const activeOption = items[state.highlightedIndex];
      const activeDescendantId =
        state.isOpen && activeOption ? `${listboxId}-option-${activeOption.id}` : undefined;

      return {
        ...props,
        'id': inputId,
        'role': 'combobox',
        'aria-autocomplete': 'list' as const,
        'aria-expanded': state.isOpen,
        'aria-haspopup': 'listbox' as const,
        'aria-controls': listboxId,
        'aria-activedescendant': activeDescendantId,
        'value': state.inputValue,
        onChange: composeEvents(props.onChange, (e: React.ChangeEvent<HTMLInputElement>) => {
          dispatch({ type: 'INPUT_CHANGE', payload: e.target.value });
        }),
        onKeyDown: composeEvents(props.onKeyDown, (e: React.KeyboardEvent<HTMLInputElement>) => {
          if (!state.isOpen && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
            e.preventDefault();
            dispatch({ type: 'OPEN' });
            return;
          }

          if (state.isOpen) {
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              let nextIdx = state.highlightedIndex + 1;
              while (nextIdx < items.length && items[nextIdx].disabled) {
                nextIdx++;
              }
              if (nextIdx < items.length) {
                dispatch({ type: 'NAVIGATE', payload: nextIdx });
              }
            } else if (e.key === 'ArrowUp') {
              e.preventDefault();
              let prevIdx = state.highlightedIndex - 1;
              while (prevIdx >= 0 && items[prevIdx].disabled) {
                prevIdx--;
              }
              if (prevIdx >= 0) {
                dispatch({ type: 'NAVIGATE', payload: prevIdx });
              }
            } else if (e.key === 'Enter') {
              e.preventDefault();
              if (state.highlightedIndex >= 0 && items[state.highlightedIndex]) {
                const item = items[state.highlightedIndex];
                if (!item.disabled) {
                  dispatch({ type: 'ITEM_CLICK', payload: item });
                }
              }
            } else if (e.key === 'Escape') {
              e.preventDefault();
              dispatch({ type: 'CLOSE' });
            }
          }
        }),
        onFocus: composeEvents(props.onFocus, () => {
          if (!state.isOpen) dispatch({ type: 'OPEN' });
        }),
      };
    },
    [state, items, listboxId, inputId]
  );

  const getListboxProps = React.useCallback(
    (props: React.HTMLAttributes<HTMLUListElement> = {}) => ({
      ...props,
      id: listboxId,
      role: 'listbox',
      'aria-labelledby': inputId,
      tabIndex: -1,
    }),
    [listboxId, inputId]
  );

  const getOptionProps = React.useCallback(
    (item: T, index: number, props: React.LiHTMLAttributes<HTMLLIElement> = {}) => {
      const isHighlighted = state.highlightedIndex === index;
      const isSelected = state.selectedItem?.id === item.id;

      return {
        ...props,
        'id': `${listboxId}-option-${item.id}`,
        'role': 'option',
        'aria-selected': isSelected,
        'aria-disabled': item.disabled,
        'data-highlighted': isHighlighted ? 'true' : undefined,
        onClick: composeEvents(props.onClick, () => {
          if (!item.disabled) {
            dispatch({ type: 'ITEM_CLICK', payload: item });
          }
        }),
      };
    },
    [state.highlightedIndex, state.selectedItem, listboxId]
  );

  return {
    state,
    dispatch,
    getInputProps,
    getListboxProps,
    getOptionProps,
  };
}

// ==========================================
// 3. COMPOUND COMPONENTS CONTEXT WRAPPER
// ==========================================

interface ComboboxContextValue<T extends ComboboxOptionItem> {
  state: ComboboxState<T>;
  getInputProps: ReturnType<typeof useComboboxCore<T>>['getInputProps'];
  getListboxProps: ReturnType<typeof useComboboxCore<T>>['getListboxProps'];
  getOptionProps: ReturnType<typeof useComboboxCore<T>>['getOptionProps'];
}

const ComboboxContext = React.createContext<ComboboxContextValue<any> | null>(null);

function useComboboxContext<T extends ComboboxOptionItem>() {
  const context = React.useContext(ComboboxContext);
  if (!context) {
    throw new Error('Combobox Compound Components must be used within <Combobox.Root>');
  }
  return context as ComboboxContextValue<T>;
}

export function ComboboxRoot<T extends ComboboxOptionItem>({
  children,
  items,
  onSelectedItemChange,
  stateReducer,
  initialSelectedItem,
}: UseComboboxProps<T> & { children: React.ReactNode }) {
  const combobox = useComboboxCore({
    items,
    onSelectedItemChange,
    stateReducer,
    initialSelectedItem,
  });

  const memoizedContext = React.useMemo<ComboboxContextValue<T>>(
    () => ({
      state: combobox.state,
      getInputProps: combobox.getInputProps,
      getListboxProps: combobox.getListboxProps,
      getOptionProps: combobox.getOptionProps,
    }),
    [
      combobox.state,
      combobox.getInputProps,
      combobox.getListboxProps,
      combobox.getOptionProps,
    ]
  );

  return (
    <ComboboxContext.Provider value={memoizedContext}>
      <div style={{ position: 'relative', display: 'inline-block', width: '100%' }}>
        {children}
      </div>
    </ComboboxContext.Provider>
  );
}

export const ComboboxInput = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>((props, ref) => {
  const { getInputProps } = useComboboxContext();
  const inputProps = getInputProps(props);
  return <input ref={ref} {...inputProps} />;
});
ComboboxInput.displayName = 'ComboboxInput';

export const ComboboxList = React.forwardRef<
  HTMLUListElement,
  React.HTMLAttributes<HTMLUListElement>
>((props, ref) => {
  const { state, getListboxProps } = useComboboxContext();
  if (!state.isOpen) return null;
  return <ul ref={ref} {...getListboxProps(props)} />;
});
ComboboxList.displayName = 'ComboboxList';

export interface ComboboxOptionComponentProps extends React.LiHTMLAttributes<HTMLLIElement> {
  item: ComboboxOptionItem;
  index: number;
}

export const ComboboxOption = React.forwardRef<HTMLLIElement, ComboboxOptionComponentProps>(
  ({ item, index, children, ...rest }, ref) => {
    const { getOptionProps } = useComboboxContext();
    return (
      <li ref={ref} {...getOptionProps(item, index, rest)}>
        {children || item.label}
      </li>
    );
  }
);
ComboboxOption.displayName = 'ComboboxOption';

// Export Compound Namespace
export const Combobox = {
  Root: ComboboxRoot,
  Input: ComboboxInput,
  List: ComboboxList,
  Option: ComboboxOption,
};
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Dimensi | Monolithic Components (`<Select />`) | Render Props Pattern (`<Select render={...}/>`) | Headless Hooks + Compound Components |
| :--- | :--- | :--- | :--- |
| **Inversion of Control** | Sangat Rendah. Semua styling di-hardcode di library. | Sedang. Markup diserahkan ke consumer, layout kaku. | **Tertinggi**. Konsumen mengontrol markup, layout, dan arsitektur styling secara independen. |
| **Re-render Optimization** | Sangat Sulit. State internal me-re-render seluruh komponen. | Rawan kebocoran rendering jika fungsi inline render prop dibuat baru setiap tick. | **Presisi Tinggi**. Pemisahan Context & Props memungkinkan optimasi granular (`React.memo`). |
| **Tree Shaking & Bundle** | Buruk. CSS bawaan dan aset ikon ikut terpaket ke bundler. | Cukup. Sering kali membengkak akibat logika wrapper kompleks. | **Maksimal**. Tidak ada payload CSS runtime; murni fungsional logic. |
| **Ergonomi Pengembang (DX)** | Mudah & Cepat untuk prototyping sederhana. | Sintaksis berantakan jika terdapat render callback bersarang (*Pyramid of Doom*). | Kurva belajar lebih curam, namun struktur kode bersih dan *composable* saat matang. |
| **A11y Predictability** | Kaku; sering kali rusak jika kustomisasi class merusak semantic DOM. | Membebankan penulisan ARIA tags secara manual kepada konsumen. | **Aman & Terjamin**. ARIA diekspos melalui Prop Getters secara otomatis dan deterministik. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Pointer Events vs. Keyboard Focus Drift
*Problem:* Saat pengguna menavigasi opsi menggunakan tombol panah keyboard (`highlightedIndex = 3`), kemudian kursor mouse secara tidak sengaja menyentuh elemen ke-1, terjadi *race-condition* antara event `onMouseMove` dan `onKeyDown`.

*Mitigasi:* Gunakan flag interaksi berbasis state mutable ref (`isUsingKeyboard.current`). Abaikan mutasi pointer hover jika pengguna sedang aktif menavigasi via keyboard sampai mouse bergerak lebih dari ambang batas perpindahan tertentu (*delta threshold movement*).

### 2. Auto-Scroll & Viewport Clipping pada Virtualized Lists
*Problem:* Ketika `aria-activedescendant` menunjuk ke item yang berada di luar viewable container yang memiliki `overflow: auto`, pembaca layar mengumumkan item aktif tersebut, tetapi item tersembunyi bagi pengguna penglihatan normal.

*Mitigasi:* Terapkan sinkronisasi layout effect:
```typescript
React.useLayoutEffect(() => {
  if (state.isOpen && state.highlightedIndex !== -1) {
    const activeElement = document.getElementById(
      `${listboxId}-option-${items[state.highlightedIndex]?.id}`
    );
    activeElement?.scrollIntoView({ block: 'nearest' });
  }
}, [state.highlightedIndex, state.isOpen, listboxId, items]);
```

### 3. Asynchronous Data Fetching Race Conditions
*Problem:* Konsumen menggunakan headless combobox untuk pencarian live API server-side. Respon query "APP" tiba setelah query "APPLE", mengakibatkan invalidasi state index opsi yang menyebabkan runtime out-of-bounds error.

*Mitigasi:* Reset `highlightedIndex` ke 0 atau -1 setiap kali `items` array referensinya berubah, dan pastikan bounds checking selalu diapit oleh math clamps:
$$\text{clampedIndex} = \min(\max(0, index), items.length - 1)$$

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Menimpa Event Consumer Tanpa Chaining
```typescript
// SALAH: Menghilangkan handler konsumen
const getButtonProps = (props) => ({
  ...props,
  onClick: () => doInternalAction(), // Props.onClick dari consumer hilang sama sekali!
});

// BENAR: Event Chaining melalui composeEvents
const getButtonProps = (props) => ({
  ...props,
  onClick: composeEvents(props?.onClick, () => doInternalAction()),
});
```

### Kesalahan Fatal 2: Context Provider Value Re-creating Setiap Render
```typescript
// SALAH: Provider value selalu mendapatkan alokasi referensi memori baru
<ComboboxContext.Provider value={{ state, dispatch }}>
  {children}
</ComboboxContext.Provider>

// BENAR: Memoize Context Value menggunakan useMemo
const contextValue = React.useMemo(() => ({ state, dispatch }), [state, dispatch]);
<ComboboxContext.Provider value={contextValue}>
  {children}
</ComboboxContext.Provider>
```

### Kesalahan Fatal 3: Melanggar Kontrak Single-Owner ID ARIA
Menggunakan ID ARIA statis (`id="listbox-id"`) di headless hook. Ketika komponen dipakai lebih dari satu kali dalam satu layar (misalnya: *Filter Departure* dan *Filter Destination*), DOM memiliki duplicate ID yang merusak aksesibilitas screen reader.

*Solusi:* Selalu gunakan hook `React.useId()` untuk mengisolasi namespace prefix identitas DOM.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Strict Prop Inversion Boundary:** Jangan pernah menyematkan kelas CSS framework apa pun (seperti Tailwind, Chakra, SCSS) di dalam *headless