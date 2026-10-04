# Bab 05 Module 01: Component Primitives & Headless UI Architecture

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Frontend and Mobile Engineering
*   **Kategori:** 03-Frontend-and-Mobile
*   **Topik Spesifik:** Design Systems
*   **Kode Modul:** DS-05-01
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat Pengetahuan:**
    *   Penguasaan mendalam atas React 18+ (Hooks, Context API, Ref Forwarding, Concurrent Rendering).
    *   Pemahaman WCAG 2.1/2.2 AA/AAA Specification dan WAI-ARIA Authoring Practices (APG).
    *   Pengalaman arsitektur Component-Driven Development (CDD).
    *   Familiaritas dengan TypeScript Generic Types, Polymorphic Components, dan Type Narrowing.

---

## SEKSI 02 — LEARNING OBJECTIVES

1.  **Mendekomposisi dan Mengisolasi State Mesin dari Presentasi:** Mampu memisahkan secara mutlak logika aksesibilitas, *keyboard navigation*, dan *state transitions* dari token visual atau styling CSS/Tailwind.
2.  **Membangun Headless Primitives Siap Produksi:** Menguasai implementasi pola *Render Props*, *Custom Hooks*, dan *Compound Components* untuk komponen kompleks (seperti Dialog/Modal, Combobox, Listbox).
3.  **Mengimplementasikan Kontrak Aksesibilitas WAI-ARIA Eksplisit:** Mengintegrasikan pengelolaan focus trap, penanganan tombol ESC, pembacaan screen reader (`aria-expanded`, `aria-controls`, `aria-activedescendant`), dan Portal rendering tanpa kebocoran memory DOM.
4.  **Menangani Komposisi Polimorfik (*as* / *asChild* Pattern):** Merancang arsitektur API komponen yang fleksibel menggunakan teknik delegasi slot berbasis Radix-style `Slot` primitive tanpa menghasilkan markup DOM wrapper yang tidak semantik.
5.  **Menganalisis Trade-off Arsitektur Headless vs. Tightly-Coupled:** Memvalidasi kapan harus mengadopsi abstraksi headless murni, mengonsumsi library pihak ketiga (Radix UI, React Aria), atau membuat *in-house headless primitives*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa sistem antarmuka berskala enterprise, musuh terbesar dari skalabilitas bukanlah CSS yang tidak rapi, melainkan **penggabungan erat (tight coupling) antara *State & Behavior* dengan *Visual Markup & Styling***. 

```
               TRADITIONAL COUPLED UI MODEL
+--------------------------------------------------------+
|                      <Select />                        |
|  [State: isOpen] + [Aria: haspopup] + [CSS: .my-theme] |
+--------------------------------------------------------+
                           |
                           v
   Kelemahan: Rebranding memerlukan rewrite total logika.
              Sulit diadaptasi ke Mobile Web vs Desktop.
```

### Mental Model: Headless UI sebagai Finite State Machine (FSM) Berbasis Data

Komponen UI pada dasarnya adalah proyeksi visual dari sebuah *Finite State Machine*. Sebuah modal atau dropdown memiliki state deterministik:
*   `IDLE` / `CLOSED`
*   `OPENING` (animasi berjalan)
*   `OPEN` (fokus terkunci, backdrop aktif)
*   `CLOSING`

Headless UI memandang elemen UI bukan sebagai "tombol berwarna biru" atau "kotak dropdown dengan shadow", melainkan sebagai **kontrak komputasional** yang:
1.  Menyimpan state diskrit (apakah elemen terbuka atau tertutup?).
2.  Menerima input event pengguna (klik, tombol `ArrowDown`, tombol `Escape`).
3.  Memancarkan set atribut HTML & WAI-ARIA (`aria-expanded="true"`, `id="xyz"`, `tabIndex={0}`).
4.  Mengatur efek samping browser (fokus DOM, penguncian scrollbar dokumen).

```
                 HEADLESS UI SEPARATION OF CONCERNS
+-----------------------------------------------------------------+
|                        Headless State Engine                    |
|             (useCombobox / Radix Primitive / Custom Hook)       |
|  - WAI-ARIA Semantics      - Keyboard Matrix (Up/Down/Enter/Esc)|
|  - Focus Trap / Restore    - Controlled / Uncontrolled Sync     |
+-----------------------------------------------------------------+
           |                                     |
           v                                     v
+-----------------------+             +-----------------------+
|  Design System Web    |             |   Enterprise Portal   |
|     (Tailwind CSS)    |             |     (CSS Modules)     |
| [Visual Layer: Alpha] |             | [Visual Layer: Beta]  |
+-----------------------+             +-----------------------+
```

Dengan mengadopsi pemikiran ini, desainer sistem antarmuka dapat merombak 100% tampilan visual aplikasi tanpa merusak kepatuhan aksesibilitas legalitas (misalnya standar Section 508 / EAA) atau alur interaksi keyboard.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur aliran interaksi komprehensif dari sebuah Headless Modal/Dialog Primitive yang mengelola fokus keyboard, status WAI-ARIA, dan pemisahan rendering melalui React Portal.

```
+---------------------------------------------------------------------------------------------------+
| USER INTERACTION EVENT PIPELINE (HEADLESS DIALOG)                                                |
+---------------------------------------------------------------------------------------------------+

[User Trigger Event] 
       |
       v
+------------------+       No       +-------------------------------+
|  Trigger Click/  | -------------> | Component Remains IDLE/CLOSED |
|  Enter Keydown?  |                +-------------------------------+
+------------------+
       |
       | Yes
       v
+-------------------------------------------------------------------+
| DIALOG PRIMITIVE ENGINE (State Engine)                            |
| 1. Simpan Ref elemen trigger (Original Focus Target)              |
| 2. Set State: isOpen = true                                       |
| 3. Disable Document Body Scroll (Overflow: hidden & padding comp) |
+-------------------------------------------------------------------+
       |
       v
+-------------------------------------------------------------------+
| DOM PROJECTION LAYER via <Portal>                                 |
| 1. Render Dialog Container ke document.body / target root node    |
| 2. Inject ARIA Atribut:                                           |
|    - role="dialog"                                                |
|    - aria-modal="true"                                            |
|    - aria-labelledby="dialog-title-uuid"                          |
|    - aria-describedby="dialog-desc-uuid"                          |
+-------------------------------------------------------------------+
       |
       v
+-------------------------------------------------------------------+
| ACCESSIBILITY & FOCUS MANAGEMENT SUBSYSTEM                        |
| 1. Query seluruh node interaktif di dalam Dialog Container        |
|    (button, [href], input, select, textarea, [tabindex]:not(-1))  |
| 2. Pindahkan fokus aktif ke Elemen Interaktif Pertama             |
|    (Atau elemen eksplisit via initialFocusRef)                    |
+-------------------------------------------------------------------+
       |
       +------------------------------------+
       |                                    |
       v (Event: Tab Keydown)               v (Event: Escape / Click Outside)
+-------------------------------+   +-------------------------------------+
| FOCUS TRAP LOGIC              |   | DISMISSAL PIPELINE                  |
| - Jika pada elemen terakhir   |   | 1. Intersep Escape / Backdrop Click |
|   dan tombol 'Tab' ditekan:   |   | 2. Set State: isOpen = false        |
|   Wrap fokus -> Elemen pertama|   | 3. Restore Document Body Scroll     |
| - Jika pada elemen pertama    |   | 4. Kembalikan fokus aktif DOM ke    |
|   dan 'Shift+Tab' ditekan:    |   |    Original Focus Target (Trigger)  |
|   Wrap fokus -> Elemen akhir  |   +-------------------------------------+
+-------------------------------+                   |
       |                                            v
       +------------------------------------> [Clean Exit to IDLE]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

Sebuah *Headless Component Primitive* kelas industri tersusun atas beberapa subsistem independen yang diorkestrasikan secara mulus:

```
+-------------------------------------------------------------------+
|               HEADLESS COMPONENT PRIMITIVE INTERNALS              |
+-------------------------------------------------------------------+
|  1. State Machine Controller                                      |
|     - Controlled State (props.value / props.onChange)             |
|     - Uncontrolled State (internal useState / useReducer)         |
+-------------------------------------------------------------------+
|  2. Identity & Semantic Wiring Subsystem                          |
|     - useId() hook integration untuk pasangan ID elemen           |
|     - aria-* property synthesizers                                |
+-------------------------------------------------------------------+
|  3. Interaction Listeners & DOM Event Interceptors                |
|     - Keyboard event dispatchers (Enter, Esc, Space, Arrows)      |
|     - Pointer down outside listeners (Click-outside detection)    |
+-------------------------------------------------------------------+
|  4. Hardware / Browser Effects Harness                            |
|     - Active Focus Trap Controller (Mutation-resilient)           |
|     - Scroll-locking subsystem                                    |
|     - Screen reader announce bridges (`aria-live` regions)        |
+-------------------------------------------------------------------+
|  5. Consumer API Inversion Interface                              |
|     - Prop-Getters: `getTriggerProps()`, `getModalProps()`        |
|     - Compound Context: `<Dialog.Root>`, `<Dialog.Trigger>`       |
|     - Polymorphic Delegator: `Slot` architecture                  |
+-------------------------------------------------------------------+
```

### Mekanisme Prop-Getters vs. Compound Components

1.  **Compound Components (`<Dialog.Root>`, `<Dialog.Content>`):** Mengandalkan React Context internal untuk meneruskan state secara implisit. Mengurangi kerumitan penulisan kode bagi pengguna komponen, namun menuntut struktur tree komponen yang kaku.
2.  **Prop Getters Pattern (`getTriggerProps`, `getItemProps`):** Pola fungsional di mana hook mengekspos fungsi yang mengembalikan objek atribut HTML yang sudah mencakup *event handlers* bawaan dan ARIA tokens. Memungkinkan penggabungan (*merging*) event handler custom milik pengguna dengan aman tanpa menimpa logika headless.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. Polimorfisme: Masalah Elemen HTML dan Solusi `Slot` Pattern

Dalam sistem antarmuka fleksibel, pengguna sering kali menginginkan sebuah trigger headless berfungsi sebagai tautan (`<a>`), tombol native (`<button>`), atau komponen routing khusus aplikasi (misal: `NextLink`).

Model usang menggunakan prop `as="a"` menciptakan tantangan berat pada TypeScript, sering kali menghasilkan kebocoran ref atau masalah *type widening* yang membingungkan. 

Standar modern industri (dipelopori oleh Radix UI) menggunakan arsitektur **Slotting / `asChild` Pattern**. Saat `asChild` bernilai `true`, alih-alih me-render tag HTML baru, komponen wrapper headless akan melakukan *cloning* terhadap elemen *immediate child*-nya dan menggabungkan (*merge*) properti, style, ID, ref, dan event handler secara mendalam.

### 2. Komposisi Event Handlers (Chained Event Invocation)

Ketika pengguna ingin mengeksekusi logika kustom pada event klik, sistem headless tidak boleh mematikan fungsi tersebut atau sebaliknya dimatikan oleh pengguna. Pola *Compose Event Handlers* menjamin bahwa kedua fungsi berjalan berurutan, dengan mekanisme interupsi ala `event.preventDefault()`:

$$\text{composedHandler}(e) = \text{userHandler}(e) \implies (\neg e.\text{defaultPrevented} \implies \text{internalHandler}(e))$$

Jika pengguna memanggil `event.preventDefault()`, logika internal headless dibatalkan. Ini memberikan kendali penuh kepada pengembang aplikasi.

### 3. Focus Management dan Algoritma Traversal Aksesibilitas

Spesifikasi WAI-ARIA APG mewajibkan fokus tidak boleh keluar dari dialog modal yang aktif. Menemukan elemen interaktif yang valid di dalam DOM membutuhkan evaluasi query selektor kompleks:

```css
a[href], area[href], input:not([disabled]), select:not([disabled]), 
textarea:not([disabled]), button:not([disabled]), iframe, 
[tabindex]:not([tabindex="-1"]), [contenteditable="true"]
```

Selain sekadar menemukan elemen, logika focus trap harus memperhitungkan elemen yang memiliki `display: none`, `visibility: hidden`, atau elemen di dalam container tersembunyi.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi dasar fondasi headless: utilitas komposisi event handler, polymorphic slot cloning, dan implementasi Headless Toggle primitive.

```typescript
// File: src/primitives/utils.ts
import * as React from 'react';

/**
 * Menggabungkan beberapa event handler menjadi satu.
 * Jika handler pertama memanggil event.preventDefault(), handler berikutnya tidak dieksekusi.
 */
export function composeEventHandlers<E extends React.SyntheticEvent>(
  originalHandler?: (event: E) => void,
  ourHandler?: (event: E) => void,
  { checkForDefaultPrevented = true } = {}
) {
  return function handleEvent(event: E) {
    originalHandler?.(event);

    if (checkForDefaultPrevented === false || !event.defaultPrevented) {
      return ourHandler?.(event);
    }
  };
}

/**
 * Menggabungkan beberapa React Refs (Callback Ref atau RefObject) menjadi satu.
 */
export function composeRefs<T>(...refs: (React.Ref<T> | undefined)[]) {
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

// File: src/primitives/Slot.tsx
interface SlotProps extends React.HTMLAttributes<HTMLElement> {
  children?: React.ReactNode;
}

export const Slot = React.forwardRef<HTMLElement, SlotProps>((props, forwardedRef) => {
  const { children, ...slotProps } = props;

  if (React.isValidElement(children)) {
    return React.cloneElement(children, {
      ...slotProps,
      ...children.props,
      // Merge style objek
      style: {
        ...slotProps.style,
        ...children.props.style,
      },
      // Merge className jika ada
      className: [slotProps.className, children.props.className].filter(Boolean).join(' '),
      // Merge refs secara aman
      ref: forwardedRef
        ? composeRefs(forwardedRef, (children as any).ref)
        : (children as any).ref,
    });
  }

  return children as React.ReactElement | null;
});
Slot.displayName = 'Slot';

// File: src/primitives/useToggle.ts
export interface UseToggleProps {
  defaultPressed?: boolean;
  pressed?: boolean;
  onPressedChange?: (pressed: boolean) => void;
  disabled?: boolean;
}

export function useToggle({
  defaultPressed = false,
  pressed: controlledPressed,
  onPressedChange,
  disabled = false,
}: UseToggleProps = {}) {
  const isControlled = controlledPressed !== undefined;
  const [uncontrolledPressed, setUncontrolledPressed] = React.useState(defaultPressed);

  const isPressed = isControlled ? controlledPressed : uncontrolledPressed;

  const toggle = React.useCallback(() => {
    if (disabled) return;

    if (!isControlled) {
      setUncontrolledPressed((prev) => !prev);
    }
    onPressedChange?.(!isPressed);
  }, [disabled, isControlled, isPressed, onPressedChange]);

  const getButtonProps = <E extends React.SyntheticEvent>(
    userProps: React.ButtonHTMLAttributes<HTMLButtonElement> = {}
  ): React.ButtonHTMLAttributes<HTMLButtonElement> => {
    return {
      ...userProps,
      type: 'button',
      'aria-pressed': isPressed,
      'data-state': isPressed ? 'on' : 'off',
      'data-disabled': disabled ? '' : undefined,
      disabled,
      onClick: composeEventHandlers(userProps.onClick, () => {
        toggle();
      }),
    };
  };

  return {
    isPressed,
    setPressed: toggle,
    getButtonProps,
  };
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Utilitas Komposisi Event Handlers (`composeEventHandlers`)
*   **Fungsi Parameter:** Menerima `originalHandler` (event handler yang dilewatkan oleh pengguna komponen UI konsumen) dan `ourHandler` (event handler internal milik mesin headless).
*   **Evaluasi `defaultPrevented`:** Kode memeriksa apakah `originalHandler` telah menginterupsi alur standar via `event.preventDefault()`. Jika ya, logika internal tidak akan dipicu, memberikan kebebasan kontrol pembatalan pada aplikasi.

### Elemen Polimorfik (`Slot`)
*   `React.isValidElement(children)`: Menjamin bahwa child tunggal yang dilewatkan adalah elemen React yang valid, bukan teks mentah atau array.
*   `React.cloneElement(...)`: Memproyeksikan seluruh atribut headless ke dalam tag asli child tanpa menambahkan tag pembungkus ekstra (seperti `<div>` wrapper) ke dalam struktur DOM akhir.
*   `composeRefs(...)`: Mencegah tertimpanya ref internal milik headless engine saat pengguna komponen juga memasang ref kustom pada elemen anak.

### Hook Headless (`useToggle`)
*   `isControlled = controlledPressed !== undefined`: Menentukan arsitektur reaktif secara otomatis (*controlled* vs *uncontrolled* paradigm) tanpa melempar warning React saat runtime.
*   `aria-pressed`: Mematuhi WAI-ARIA Toggle Button Pattern sehingga screen reader membaca status tombol sebagai ditekan (*pressed*) atau belum.
*   `data-state`: Menghasilkan atribut selektor data CSS (`on` / `off`), memudahkan styling modern via Tailwind CSS variant (`data-[state=on]:bg-blue-600`).

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Arsitektur Multi-Brand Fintech Modal Dialog System
Sebuah institusi perbankan multinasional membawahi tiga brand produk:
1.  **Bank Retail Tradisional:** Memerlukan antarmuka web klasik dengan Bootstrap/CSS lama dan dialog berbentuk rounded standar.
2.  **Aplikasi Investasi Kripto/Gen-Z:** Memerlukan Tailwind CSS, Framer Motion transitions, dark mode permanen, dan tampilan bottom-sheet di resolusi mobile.
3.  **Backoffice CMS Internal:** Menggunakan enterprise data-grid dengan tema antarmuka high-density.

### Masalah
Jika masing-masing tim membuat modal sendiri, terjadi duplikasi pengujian kepatuhan hukum WCAG 2.1 AA. Ditemukan bahwa 2 dari 3 aplikasi gagal uji audit auditabilitas regulasi karena:
*   Fokus keyboard bocor ke latar belakang dokumen saat dialog terbuka.
*   Tombol Escape gagal menutup dialog jika dropdown di dalam modal terbuka bersamaan.
*   Screen reader tidak membacakan judul dialog saat modal muncul.

### Solusi Desain
Membangun satu package headless murni: `@enterprise-ds/headless-dialog`. Package ini sepenuhnya bebas dari CSS, SVG icons, dan dependensi visual lainnya. Paket ini hanya mengimplementasikan state machine dialog, *focus trap*, *scroll locking*, serta *WAI-ARIA semantics*, kemudian didistribusikan ke ketiga lini tim produk untuk dipasangkan dengan lapisan styling masing-masing.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Di bawah ini adalah implementasi level enterprise dari Headless Dialog Primitive yang mencakup:
1.  Compound components model dengan React Context.
2.  Focus Trap native anti-bocor.
3.  Scroll lock dengan kompensasi scrollbar shift.
4.  Dukungan Slotting (`asChild`).
5.  Portalling aman dari manipulasi SSR.

```tsx
// File: src/components/headless-dialog/HeadlessDialog.tsx
import * as React from 'react';
import * as ReactDOM from 'react-dom';
import { composeEventHandlers, composeRefs, Slot } from '../primitives/utils';

// --- TYPES ---
interface DialogContextValue {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  titleId: string;
  descriptionId: string;
  contentRef: React.RefObject<HTMLDivElement>;
}

const DialogContext = React.createContext<DialogContextValue | null>(null);

function useDialogContext(componentName: string) {
  const context = React.useContext(DialogContext);
  if (!context) {
    throw new Error(`${componentName} must be used within a <Dialog.Root />`);
  }
  return context;
}

// --- FOCUS TRAP HOOK ---
function useFocusTrap(
  containerRef: React.RefObject<HTMLElement>,
  isActive: boolean
) {
  const previousActiveElement = React.useRef<HTMLElement | null>(null);

  React.useEffect(() => {
    if (!isActive) return;

    // Simpan elemen yang memiliki fokus sebelum dialog terbuka
    previousActiveElement.current = document.activeElement as HTMLElement;

    const container = containerRef.current;
    if (!container) return;

    // Selektor elemen yang dapat difokuskan
    const focusableSelectors = [
      'a[href]',
      'area[href]',
      'input:not([disabled])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      'button:not([disabled])',
      'iframe',
      '[tabindex]:not([tabindex="-1"])',
      '[contenteditable="true"]',
    ].join(',');

    const focusableElements = Array.from(
      container.querySelectorAll<HTMLElement>(focusableSelectors)
    ).filter((el) => el.offsetParent !== null); // Filter elemen yang terlihat

    // Pindahkan fokus ke elemen pertama atau kontainer dialog itu sendiri
    if (focusableElements.length > 0) {
      focusableElements[0].focus();
    } else {
      container.focus();
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;

      const currentFocusables = Array.from(
        container.querySelectorAll<HTMLElement>(focusableSelectors)
      ).filter((el) => el.offsetParent !== null);

      if (currentFocusables.length === 0) {
        e.preventDefault();
        return;
      }

      const firstElement = currentFocusables[0];
      const lastElement = currentFocusables[currentFocusables.length - 1];

      if (e.shiftKey) {
        // Navigasi mundur: Shift + Tab
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement.focus();
        }
      } else {
        // Navigasi maju: Tab
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      // Kembalikan fokus ke trigger asal saat dialog hancur (unmount)
      if (previousActiveElement.current && previousActiveElement.current.focus) {
        previousActiveElement.current.focus();
      }
    };
  }, [isActive, containerRef]);
}

// --- SCROLL LOCK HOOK ---
function useBodyScrollLock(isActive: boolean) {
  React.useEffect(() => {
    if (!isActive) return;

    const originalOverflow = document.body.style.overflow;
    const originalPaddingRight = document.body.style.paddingRight;
    
    // Hitung lebar scrollbar untuk mencegah tata letak bergeser (layout shift)
    const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;

    document.body.style.overflow = 'hidden';
    if (scrollbarWidth > 0) {
      document.body.style.paddingRight = `${scrollbarWidth}px`;
    }

    return () => {
      document.body.style.overflow = originalOverflow;
      document.body.style.paddingRight = originalPaddingRight;
    };
  }, [isActive]);
}

// --- COMPOUND COMPONENTS ---

export interface DialogRootProps {
  children: React.ReactNode;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export function Root({
  children,
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
}: DialogRootProps) {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen);
  const isControlled = controlledOpen !== undefined;
  const isOpen = isControlled ? controlledOpen : uncontrolledOpen;

  const contentRef = React.useRef<HTMLDivElement>(null);
  const uniqueId = React.useId();
  const titleId = `dialog-title-${uniqueId}`;
  const descriptionId = `dialog-desc-${uniqueId}`;

  const open = React.useCallback(() => {
    if (!isControlled) setUncontrolledOpen(true);
    onOpenChange?.(true);
  }, [isControlled, onOpenChange]);

  const close = React.useCallback(() => {
    if (!isControlled) setUncontrolledOpen(false);
    onOpenChange?.(false);
  }, [isControlled, onOpenChange]);

  return (
    <DialogContext.Provider
      value={{
        isOpen,
        open,
        close,
        titleId,
        descriptionId,
        contentRef,
      }}
    >
      {children}
    </DialogContext.Provider>
  );
}

export interface DialogTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

export const Trigger = React.forwardRef<HTMLButtonElement, DialogTriggerProps>(
  ({ asChild = false, onClick, ...props }, forwardedRef) => {
    const context = useDialogContext('Dialog.Trigger');
    const Component = asChild ? Slot : 'button';

    return (
      <Component
        type={asChild ? undefined : 'button'}
        aria-haspopup="dialog"
        aria-expanded={context.isOpen}
        aria-controls={context.isOpen ? 'dialog-content' : undefined}
        data-state={context.isOpen ? 'open' : 'closed'}
        ref={forwardedRef}
        onClick={composeEventHandlers(onClick, () => {
          context.open();
        })}
        {...props}
      />
    );
  }
);
Trigger.displayName = 'DialogTrigger';

export interface DialogPortalProps {
  children: React.ReactNode;
  container?: HTMLElement;
}

export function Portal({ children, container }: DialogPortalProps) {
  const context = useDialogContext('Dialog.Portal');
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  if (!context.isOpen || !mounted) {
    return null;
  }

  const mountNode = container || document.body;
  return ReactDOM.createPortal(children, mountNode);
}

export interface DialogOverlayProps extends React.HTMLAttributes<HTMLDivElement> {
  asChild?: boolean;
}

export const Overlay = React.forwardRef<HTMLDivElement, DialogOverlayProps>(
  ({ asChild = false, ...props }, forwardedRef) => {
    const context = useDialogContext('Dialog.Overlay');
    const Component = asChild ? Slot : 'div';

    return (
      <Component
        aria-hidden="true"
        data-state={context.isOpen ? 'open' : 'closed'}
        ref={forwardedRef}
        {...props}
      />
    );
  }
);
Overlay.displayName = 'DialogOverlay';

export interface DialogContentProps extends React.HTMLAttributes<HTMLDivElement> {
  asChild?: boolean;
  onEscapeKeyDown?: (event: KeyboardEvent) => void;
  onPointerDownOutside?: (event: MouseEvent) => void;
}

export const Content = React.forwardRef<HTMLDivElement, DialogContentProps>(
  (
    { asChild = false, onEscapeKeyDown, onPointerDownOutside, ...props },
    forwardedRef
  ) => {
    const context = useDialogContext('Dialog.Content');
    const Component = asChild ? Slot : 'div';

    // Sambungkan focus trap dan scroll lock
    useFocusTrap(context.contentRef, context.isOpen);
    useBodyScrollLock(context.isOpen);

    // Escape Key Listener
    React.useEffect(() => {
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          if (onEscapeKeyDown) {
            onEscapeKeyDown(e);
          }
          if (!e.defaultPrevented) {
            context.close();
          }
        }
      };
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }, [context, onEscapeKeyDown]);

    // Click Outside Listener
    React.useEffect(() => {
      const handlePointerDown = (e: MouseEvent) => {
        const target = e.target as Node;
        if (
          context.contentRef.current &&
          !context.contentRef.current.contains(target)
        ) {
          if (onPointerDownOutside) {
            onPointerDownOutside(e);
          }
          if (!e.defaultPrevented) {
            context.close();
          }
        }
      };
      document.addEventListener('pointerdown', handlePointerDown);
      return () => document.removeEventListener('pointerdown', handlePointerDown);
    }, [context, onPointerDownOutside]);

    return (
      <Component
        id="dialog-content"
        role="dialog"
        aria-modal="true"
        aria-labelledby={context.titleId}
        aria-describedby={context.descriptionId}
        tabIndex={-1}
        data-state={context.isOpen ? 'open' : 'closed'}
        ref={composeRefs(forwardedRef, context.contentRef)}
        {...props}
      />
    );
  }
);
Content.displayName = 'DialogContent';

export const Title = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement> & { asChild?: boolean }
>(({ asChild = false, ...props }, forwardedRef) => {
  const context = useDialogContext('Dialog.Title');
  const Component = asChild ? Slot : 'h2';

  return <Component id={context.titleId} ref={forwardedRef} {...props} />;
});
Title.displayName = 'DialogTitle';

export const Description = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement> & { asChild?: boolean }
>(({ asChild = false, ...props }, forwardedRef) => {
  const context = useDialogContext('Dialog.Description');
  const Component = asChild ? Slot : 'p';

  return <Component id={context.descriptionId} ref={forwardedRef} {...props} />;
});
Description.displayName = 'DialogDescription';

export const Close = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }
>(({ asChild = false, onClick, ...props }, forwardedRef) => {
  const context = useDialogContext('Dialog.Close');
  const Component = asChild ? Slot : 'button';

  return (
    <Component
      type={asChild ? undefined : 'button'}
      ref={forwardedRef}
      onClick={composeEventHandlers(onClick, () => {
        context.close();
      })}
      {...props}
    />
  );
});
Close.displayName = 'DialogClose';

export const Dialog = {
  Root,
  Trigger,
  Portal,
  Overlay,
  Content,
  Title,
  Description,
  Close,
};
```

### Konsumsi oleh Aplikasi (Pemberian Visual Layer via Tailwind CSS)

```tsx
// File: src/components/CryptoWithdrawalModal.tsx
import * as React from 'react';
import { Dialog } from './headless-dialog/HeadlessDialog';

export function CryptoWithdrawalModal() {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium rounded-lg transition-colors focus:ring-2 focus:ring-emerald-400 focus:outline-none">
          Withdraw Funds
        </button>
      </Dialog.Trigger>

      <Dialog.Portal>
        {/* Background Overlay */}
        <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 transition-opacity animate-in fade-in" />

        {/* Modal Window Container */}
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <Dialog.Content className="w-full max-w-md bg-neutral-900 border border-neutral-800 rounded-xl p-6 shadow-2xl text-white outline-none focus:ring-1 focus:ring-neutral-700">
            <Dialog.Title className="text-xl font-bold tracking-tight">
              Confirm Withdrawal
            </Dialog.Title>
            
            <Dialog.Description className="mt-2 text-sm text-neutral-400">
              Please verify your wallet address carefully. Transactions deployed
              to the blockchain network cannot be reverted.
            </Dialog.Description>

            <div className="mt-4 space-y-3">
              <label className="block text-xs font-semibold uppercase text-neutral-400">
                Destination Address
              </label>
              <input
                type="text"
                placeholder="0x71C...8976"
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded text-sm text-neutral-200 focus:border-emerald-500 focus:outline-none"
              />
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <Dialog.Close asChild>
                <button className="px-3 py-1.5 text-sm text-neutral-400 hover:text-white rounded">
                  Cancel
                </button>
              </Dialog.Close>
              
              <button
                onClick={() => alert('Broadcasted to blockchain')}
                className="px-4 py-1.5 text-sm bg-emerald-500 hover:bg-emerald-600 text-black font-semibold rounded"
              >
                Sign & Transact
              </button>
            </div>
          </Dialog.Content>
        