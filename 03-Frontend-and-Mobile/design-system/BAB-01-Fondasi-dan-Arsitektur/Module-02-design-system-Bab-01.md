# MODULE 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi Design System

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Mendesain Arsitektur Token Multidimensi**: Mengonstruksi hierarki Design Tokens (*Global*, *Semantic/Alias*, dan *Component-scoped*) sesuai spesifikasi W3C Design Tokens Community Group (DTCG).
- **Membangun Pipeline Transformasi Token Otomatis**: Mengembangkan *custom engine* berbasis AST (*Abstract Syntax Tree*) dan *Style Dictionary* untuk mentranspilasi token JSON menjadi artefak multi-platform (CSS Variables, TypeScript definitions, SCSS, Tailwind config, Android XML/Compose, iOS Swift).
- **Mengimplementasikan Arsitektur Komponen Headless & Polimorfik**: Mengisolasi *state*, aksesibilitas (WAI-ARIA 1.2), dan *keyboard navigation* dari representasi visual menggunakan pola *Headless UI Primitives* dan *Compound Components*.
- **Menata Infrastruktur Monorepo Enterprise**: Mengonfigurasi monorepo berbasis Turborepo/PNPM Workspaces dengan isolasi paket yang ketat, *dual-build distribution* (ESM & CJS), *tree-shaking validation*, dan *automated semantic release*.
- **Menerapkan Strategi Mitigasi Regresi Desain & Performa**: Menjalankan pengujian visual terotomatisasi (*Visual Regression Testing*), *bundle size budget gating*, dan audit kontras warna secara terprogram di dalam *CI/CD pipeline*.

---

## 2. Prerequisites

### Prasyarat Pengetahuan
- **TypeScript Tingkat Lanjut**: Pemahaman mendalam mengenai *conditional types*, *mapped types*, *template literal types*, `infer`, serta manipulasi generic constraints.
- **Modern DOM & CSS**: Memahami spesifikasi *CSS Cascading Variables*, CSS Modules, *layout algorithms* (Flexbox/Grid), serta spesifikasi *CSS Paint/Typed Object Model*.
- **Accessibility Engine**: Pemahaman mendalam tentang WAI-ARIA Authoring Practices Guide (APG), kalkulasi kontras warna WCAG 2.2, *focus management*, dan *virtual screen reader testing*.
- **Build Tools & AST**: Dasar-dasar kompilasi JavaScript/TypeScript melalui SWC/Rollup/tsup dan manipulasi JSON/AST via Babel atau PostCSS.

### Prasyarat Lingkungan Pengembangan
- **Node.js**: `v20.x LTS` atau `v22.x LTS`
- **Package Manager**: `pnpm >= 9.x`
- **Build Engine**: `Turbo >= 2.x`
- **Compiler Target**: `ES2022`, ModuleResolution `NodeNext`

---

## 3. Concept & Internal Architecture

### 3.1 Token Engine: Hierarki Token Tiga Tingkat (Three-Tier Token Architecture)

Sebuah enterprise design system yang tangguh tidak pernah mengekspos nilai mentah (*raw values*) langsung ke komponen UI. Arsitektur token dibagi menjadi tiga lapisan diskrit:

```
[ Tier 1: Global / Reference Tokens ] (Raw / Primitive)
                │
                ▼
[ Tier 2: Semantic / Alias Tokens ]  (Contextual / Functional / Intent-based)
                │
                ▼
[ Tier 3: Component-Scoped Tokens ]  (Component specific API bindings)
```

1. **Global Tokens (Primitives)**: Nilai absolut tanpa konteks penggunaan. Bersifat agnostik terhadap tema.
   - Contoh: `color.blue.500 = "#0066FF"`, `spacing.4 = "16px"`.
2. **Semantic / System Tokens (Aliases)**: Abstraksi yang memberikan arti, fungsi, dan intent terhadap global tokens. Lapisan ini yang berganti nilai saat perpindahan tema (*light/dark mode*, *brand swapping*, *high-contrast mode*).
   - Contoh: `color.background.interactive.hover = "{color.blue.500}"`.
3. **Component Tokens**: Pemetaan semantic tokens ke ruang lingkup (*scope*) komponen tunggal untuk mengisolasi perubahan lokal agar tidak merusak komponen lain.
   - Contoh: `button.primary.hover.background = "{color.background.interactive.hover}"`.

```
                    ┌────────────────────────┐
                    │ Raw Design Tokens JSON │
                    │   (W3C DTCG Format)    │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │ Style Dictionary AST   │
                    │ Parser & Token Resolver│
                    └───────────┬────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│ CSS / SCSS   │        │  TypeScript  │        │ Android/iOS  │
│  Variables   │        │ Type-Safe DTO│        │ XML & Swift  │
└──────────────┘        └──────────────┘        └──────────────┘
```

### 3.2 Dynamic Resolution & AST Token Parsing

Proses resolusi token bekerja secara transitif menggunakan *Directed Acyclic Graph* (DAG). Ketika Style Dictionary memproses token:
1. **Ingestion & Deep Merge**: Menggabungkan seluruh file token berbasis namespace JSON.
2. **Graph Dependency Sorting**: Menyelesaikan dependensi hierarkis (Tier 3 mereferensikan Tier 2, Tier 2 mereferensikan Tier 1). Apabila terdeteksi siklus (`A -> B -> A`), parser melempar *Circular Reference Error*.
3. **Transformation Pipeline**: Mengaplikasikan `matcher`, `transformer`, dan `formatter` untuk menghasilkan artefak target.

### 3.3 Headless Primitive vs Styled Component Layer

Arsitektur komponen enterprise memisahkan **State & Accessibility Behavior** dari **Visual Presentation**.

```
┌────────────────────────────────────────────────────────┐
│ UI Consumer (Aplikasi Produk / Feature Engineers)      │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Visual Presentation Layer (CSS Modules / Vanilla Ext)   │
│ - Design Tokens Integration                            │
│ - Responsive Variants / Micro-interactions             │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Headless Behavior Layer (Primitives: Radix / React-Aria)│
│ - State Machine (Open/Close/Focus/Disable)             │
│ - WAI-ARIA Attributes (aria-expanded, aria-controls)   │
│ - Keyboard Handlers (Arrow navigation, ESC dismiss)    │
└────────────────────────────────────────────────────────┘
```

- **Headless Layer**: Menjamin bahwa seluruh komponen (misal: Select, Modal, Dropdown) 100% patuh pada aturan aksesibilitas WAI-ARIA APG tanpa bergantung pada gaya visual.
- **Visual Layer**: Menerapkan token visual melalui CSS Variables / class names murni tanpa merusak kalkulasi *state* komponen.

---

## 4. Why & What

| Dimensi | Pendekatan Ad-Hoc / Legacy | Modern Enterprise Design System |
| :--- | :--- | :--- |
| **Konsistensi UI** | *Hardcoded hex values* dan arbitrary margin/padding di setiap CSS file. Rentan desinkronisasi antar produk. | Single source of truth via Design Tokens. Perubahan global cukup melalui pembaruan token. |
| **Cross-Platform Delivery** | Implementasi manual terpisah untuk Web, iOS, dan Android. Memerlukan komunikasi konstan via spreadsheet. | Pipeline kompilasi terotomatisasi dari satu sumber JSON ke CSS, Swift (iOS), dan XML/Compose (Android). |
| **Aksesibilitas (a11y)** | Diuji pasca-rilis; sering kali tag `div` digunakan untuk tombol dan elemen interaktif tanpa atribut ARIA. | Terjamin secara arsitektural menggunakan Headless Primitive Engine dengan audit a11y bawaan pada level testing. |
| **Skalabilitas Brand** | Duplikasi repository atau conditional logic CSS yang rumit untuk menangani multi-tenant/multi-brand. | *Semantic Token Swap*: Penggantian tema dan brand hanya memerlukan substitusi file variabel CSS tanpa modifikasi kode komponen. |
| **Konsumsi Paket** | Monolithic bundle; mengimpor satu komponen memaksa browser memuat seluruh library (ukuran bundle membengkak). | Struktur monorepo modular dengan isolasi paket, mendukung *Subpath Exports* dan *Tree-shaking* native. |

---

## 5. How: End-to-End Delivery Workflow

Alur kerja distribusi token dan komponen dalam siklus CI/CD enterprise:

```
[ Designer: Figma Token Studio ]
               │
               ▼ (Export / Sync via Webhook/Git Action)
[ Git Repository: packages/tokens ]
               │
               ▼ (pnpm build -> Style Dictionary)
[ Compiled Artifacts: CSS, TS Types, JSON DTO ]
               │
               ▼ (turbo build -> Bundle Component Library)
[ Packages: @org/primitives & @org/react ]
               │
               ▼ (Changesets & Semantic Release)
[ NPM Private Registry / GitHub Packages ]
               │
               ▼ (pnpm install @org/react)
[ Consumer Applications: Web, Microfrontends, Mobile Apps ]
```

1. **Sinkronisasi Desain**: Desainer memutakhirkan token di Figma. Menggunakan plugin seperti *Tokens Studio*, perubahan diekspor sebagai JSON ke repositori Git via Pull Request terotomatisasi.
2. **Kompilasi Token**: Style Dictionary mengeksekusi pipeline: membersihkan format, me-resolve referensi token, dan menghasilkan artefak target platform.
3. **Build Komponen**: Komponen React mengonsumsi tipe data token dan mendefinisikan *custom properties*. Build tool (`tsup`/Rollup) melakukan kompilasi dengan target dual ESM/CJS dan mengikutsertakan sourcemap serta deklarasi TypeScript (`.d.ts`).
4. **Verifikasi Kualitas**: CI mengeksekusi *Linter*, *Unit Test*, *Visual Regression (Playwright)*, dan *Size Limit Guard*.
5. **Rilis Terkelola**: Versi dinaikkan secara semantik menggunakan `@changesets/cli`, mempublikasikan paket ke registri npm privat, dan membuat changelog otomatis.

---

## 6. Analogy & Architectural Diagram

### Analogi Sistem Kelistrikan Rumah Tangga
Bayangkan Design System sebagai **jaringan infrastruktur kelistrikan modular**:
- **Global Tokens** adalah **Pembangkit Listrik (Tegangan Tinggi - 500kV)**: Sumber daya mentah universal. Tidak aman untuk dihubungkan langsung ke perangkat Anda.
- **Semantic Tokens** adalah **Trafo Distribusi Lokal (220V)**: Disesuaikan dengan kebutuhan penggunaan spesifik (kebutuhan listrik rumah tangga standar vs industri).
- **Component Tokens** adalah **Kabel & Colokan Stopkontak (Socket Type-C)**: Antarmuka spesifik yang terhubung langsung ke peralatan rumah Anda (Komponen).
- **Headless Primitive** adalah **Sirkuit Pengaman Internal dan Sakelar**: Bertanggung jawab penuh atas aliran listrik yang aman, tombol on/off, dan proteksi beban berlebih, tanpa peduli apakah casing luar sakelar terbuat dari plastik hitam, kayu, atau metalik.
- **Styled Component** adalah **Casing Dekoratif Luar Sakelar**: Tampilan estetis yang Anda lihat dan sentuh, yang dapat diganti sewaktu-waktu tanpa membongkar sirkuit listrik di dalamnya.

### Diagram Arsitektur Monorepo & Distribusi

```
┌────────────────────────────────────────────────────────────────────────┐
│                   ENTERPRISE DESIGN SYSTEM MONOREPO                    │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌────────────────────────┐         ┌────────────────────────┐         │
│  │   packages/tokens      │────────▶│  packages/primitives   │         │
│  │  (W3C JSON Source)     │         │  (Headless Components) │         │
│  │  - Style Dictionary    │         │  - Focus Trap          │         │
│  │  - CSS Custom Props    │         │  - A11y State Machines │         │
│  │  - TS Token Types      │         │  - Keyboard Navigation │         │
│  └───────────┬────────────┘         └───────────┬────────────┘         │
│              │                                  │                      │
│              │     ┌────────────────────────────┘                      │
│              ▼     ▼                                                   │
│  ┌────────────────────────┐         ┌────────────────────────┐         │
│  │    packages/react      │         │     apps/storybook     │         │
│  │  (Styled Components)   │────────▶│  (Documentation Hub)   │         │
│  │  - Button, Modal, etc. │         │  - Interaction Tests   │         │
│  │  - Variant Management  │         │  - Visual Regression   │         │
│  └────────────────────────┘         └────────────────────────┘         │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Simple & Practical Examples

### 7.1 Simple Example: Pipeline Token W3C ke CSS Variables Menggunakan Style Dictionary

#### Langkah 1: Token Mentah dalam Format DTCG (`tokens/globals.json`)
```json
{
  "color": {
    "brand": {
      "primary": {
        "$value": "#0F52BA",
        "$type": "color",
        "$description": "Sapphire Blue - Primary Brand Color"
      }
    }
  },
  "semantic": {
    "color": {
      "action": {
        "background": {
          "$value": "{color.brand.primary}",
          "$type": "color",
          "$description": "Default background for primary action surfaces"
        }
      }
    }
  }
}
```

#### Langkah 2: Build Script Transformer (`build-tokens.mjs`)
```javascript
import StyleDictionary from 'style-dictionary';

const sd = new StyleDictionary({
  source: ['tokens/**/*.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: 'dist/css/',
      files: [
        {
          destination: 'variables.css',
          format: 'css/variables',
          options: {
            outputReferences: true
          }
        }
      ]
    },
    ts: {
      transformGroup: 'js',
      buildPath: 'dist/ts/',
      files: [
        {
          destination: 'tokens.ts',
          format: 'javascript/es6'
        },
        {
          destination: 'tokens.d.ts',
          format: 'typescript/es6-declarations'
        }
      ]
    }
  }
});

await sd.buildAllPlatforms();
console.log('✔ Design tokens successfully compiled.');
```

---

### 7.2 Practical Example: Enterprise-Grade Polymorphic Headless-Integrated Component

Berikut adalah implementasi tombol produksi (*Button*) dengan fitur:
1. Dukungan **Polimorfik** melalui *asChild pattern* (komposisi Slot).
2. Dukungan **Variant Matrix** berbasis *Type-Safe Data Attributes*.
3. Aksesibilitas penuh (keyboard activation, state reflection).

#### Implementasi Core Slot / Slot Primitives (`packages/react/src/components/Slot.tsx`)
```typescript
import * as React from 'react';

export interface SlotProps extends React.HTMLAttributes<HTMLElement> {
  children?: React.ReactNode;
}

export const Slot = React.forwardRef<HTMLElement, SlotProps>((props, forwardedRef) => {
  const { children, ...slotProps } = props;

  if (React.isValidElement(children)) {
    return React.cloneElement(children, {
      ...mergeProps(slotProps, children.props),
      ref: forwardedRef ? composeRefs(forwardedRef, (children as any).ref) : (children as any).ref,
    });
  }

  return children ? <>{children}</> : null;
});

Slot.displayName = 'Slot';

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

function mergeProps(parentProps: Record<string, any>, childProps: Record<string, any>) {
  const overrideProps = { ...childProps };

  for (const propName in childProps) {
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
    }
  }

  return { ...parentProps, ...overrideProps };
}
```

#### Implementasi Button Terintegrasi Token (`packages/react/src/components/Button.tsx`)
```typescript
import * as React from 'react';
import { Slot } from './Slot';
import styles from './Button.module.css';

export type ButtonVariant = 'primary' | 'secondary' | 'critical' | 'ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonBaseProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  isDisabled?: boolean;
  asChild?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export type ButtonProps = ButtonBaseProps &
  React.ButtonHTMLAttributes<HTMLButtonElement>;

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      isLoading = false,
      isDisabled = false,
      asChild = false,
      leftIcon,
      rightIcon,
      children,
      className,
      disabled,
      ...restProps
    },
    forwardedRef
  ) => {
    const Component = asChild ? Slot : 'button';
    const effectivelyDisabled = isDisabled || disabled || isLoading;

    return (
      <Component
        ref={forwardedRef}
        aria-disabled={effectivelyDisabled ? 'true' : undefined}
        aria-busy={isLoading ? 'true' : undefined}
        disabled={asChild ? undefined : effectivelyDisabled}
        data-variant={variant}
        data-size={size}
        data-loading={isLoading ? '' : undefined}
        data-disabled={effectivelyDisabled ? '' : undefined}
        className={[styles.button, className].filter(Boolean).join(' ')}
        {...restProps}
      >
        {isLoading && (
          <span className={styles.spinner} aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" className={styles.spinnerIcon}>
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" opacity="0.25" />
              <path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </span>
        )}
        {!isLoading && leftIcon && <span className={styles.icon}>{leftIcon}</span>}
        <span className={styles.content}>{children}</span>
        {!isLoading && rightIcon && <span className={styles.icon}>{rightIcon}</span>}
      </Component>
    );
  }
);

Button.displayName = 'Button';
```

#### Gaya CSS Scoped Mengonsumsi Token (`packages/react/src/components/Button.module.css`)
```css
/* Mengonsumsi Component Tokens yang memetakan Semantic Tokens */
.button {
  --btn-bg: var(--ds-color-action-bg-primary);
  --btn-fg: var(--ds-color-action-fg-primary);
  --btn-border: transparent;
  --btn-padding-x: var(--ds-spacing-4);
  --btn-padding-y: var(--ds-spacing-2);
  --btn-font-size: var(--ds-font-size-md);
  --btn-radius: var(--ds-radius-md);

  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--ds-spacing-2);
  padding: var(--btn-padding-y) var(--btn-padding-x);
  font-size: var(--btn-font-size);
  font-weight: var(--ds-font-weight-semibold);
  color: var(--btn-fg);
  background-color: var(--btn-bg);
  border: 1px solid var(--btn-border);
  border-radius: var(--btn-radius);
  cursor: pointer;
  text-decoration: none;
  transition: background-color 150ms cubic-bezier(0.4, 0, 0.2, 1),
              border-color 150ms cubic-bezier(0.4, 0, 0.2, 1),
              box-shadow 150ms cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
}

.button:focus-visible {
  box-shadow: 0 0 0 3px var(--ds-color-focus-ring);
}

/* Variant Mappings via Data Attributes */
.button[data-variant="secondary"] {
  --btn-bg: var(--ds-color-action-bg-secondary);
  --btn-fg: var(--ds-color-action-fg-secondary);
  --btn-border: var(--ds-color-action-border-secondary);
}

.button[data-variant="critical"] {
  --btn-bg: var(--ds-color-action-bg-critical);
  --btn-fg: var(--ds-color-action-fg-critical);
}

.button[data-variant="ghost"] {
  --btn-bg: transparent;
  --btn-fg: var(--ds-color-action-fg-ghost);
}

/* Size Adjustments */
.button[data-size="sm"] {
  --btn-padding-x: var(--ds-spacing-3);
  --btn-padding-y: var(--ds-spacing-1);
  --btn-font-size: var(--ds-font-size-sm);
}

.button[data-size="lg"] {
  --btn-padding-x: var(--ds-spacing-6);
  --btn-padding-y: var(--ds-spacing-3);
  --btn-font-size: var(--ds-font-size-lg);
}

/* State Handlers */
.button[data-disabled] {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

.button[data-loading] {
  cursor: wait;
}

.spinner {
  display: flex;
  align-items: center;
  animation: spin 1s linear infinite;
}

.spinnerIcon {
  width: 1em;
  height: 1em;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Kasus: Migrasi Multi-Brand FinTech Global (SuperApp Ecosystem)
- **Konteks**: Platform FinTech mengakuisisi 3 entitas perbankan di Asia Tenggara. Masing-masing aplikasi memiliki brand visual yang sangat berbeda, namun flow transaksi inti (Transfer, Pembayaran Tagihan, KYC) identik.
- **Problem**:
  1. Engineering mereplikasi repositori komponen untuk setiap entitas, menyebabkan 3x lipat *maintenance overhead*.
  2. Rilis fitur baru membutuhkan waktu berbulan-bulan karena perbaikan bug di aplikasi A harus di-porting secara manual ke aplikasi B dan C.
  3. Bundle size membengkak karena library komponen menyertakan stylesheet dari ketiga brand secara bersamaan.
- **Solusi Arsitektural**:
  1. **Ekstraksi Headless Core**: Mengisolasi 100% logic interaksi transaksi ke dalam `@fintech/primitives`.
  2. **Multi-Brand Token Separation**:
     - `brand-alpha.json`
     - `brand-beta.json`
     - `brand-gamma.json`
  3. **CSS Custom Properties Injection**: Aplikasi induk hanya menyertakan referensi variabel standar, sementara nilai konkret diinjeksikan pada level root dokumen (`:root[data-brand="beta"]`) menggunakan CSS modular.
- **Hasil Terukur**:
  - **Efisiensi Kode**: Mengeliminasi ~72% kode duplikat di 3 aplikasi.
  - **Kecepatan Time-to-Market**: Fitur pembayaran QRIS baru dirilis serentak di 3 brand dalam satu siklus sprint 2 minggu.
  - **Performa Runtime**: Penurunan ukuran JS bundle sebesar 38% karena komponen tidak lagi membawa styling logika kondisional JavaScript (`switch(brand)`).

---

## 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian / Biaya |
| :--- | :--- | :--- |
| **Runtime CSS-in-JS (e.g., Emotion, Styled-Components)** | Fleksibilitas tinggi dalam memanipulasi props secara dinamis di level JS; scoping CSS terisolasi otomatis. | Biaya runtime tinggi (overhead komputasi saat re-render); meningkatkan TTFB dan TBT; tidak kompatibel secara optimal dengan React Server Components (RSC). |
| **Zero-Runtime CSS / CSS Modules + CSS Variables** | Eksekusi instan tanpa JS execution cost; ukuran bundle JS jauh lebih kecil; interoperabilitas native dengan RSC. | Dinamisme styling terbatas pada variasi custom properties dan atribut HTML; memerlukan konfigurasi build tool ekstra untuk TypeScript typings. |
| **Monolithic Component Library Package** | Kemudahan pemeliharaan dependensi tunggal bagi tim produk (`import { Button } from '@org/ui'`). | Rentan terhadap kebocoran *tree-shaking* jika bundler konsumen salah konfigurasi; pembaruan komponen kecil memaksa rilis seluruh sistem UI. |
| **Granular Multi-Package Monorepo (`@org/button`, `@org/input`)** | *Tree-shaking* sempurna; dependensi dan rilis terisolasi per komponen secara independen. | *Dependency management overhead* tinggi; kompleksitas eksponensial dalam menyinkronkan kompatibilitas versi antar komponen. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Kebocoran Tree-Shaking Menggunakan File Barrel Tunggal
- **Gejala**: Aplikasi konsumen mengimpor `Button`, namun bundle akhir menyertakan pustaka charting dan modal yang berukuran besar.
- **Penyebab Utama**: Berkas `index.ts` utama mengekspor ulang seluruh pustaka, dan bundler mendeteksi potensi *side-effects*.
- **Solusi**:
  1. Set `"sideEffects": false` di dalam `package.json`.
  2. Konfigurasikan subpath exports modern:
  ```json
  {
    "exports": {
      "./button": {
        "types": "./dist/components/Button.d.ts",
        "import": "./dist/components/Button.mjs",
        "require": "./dist/components/Button.cjs"
      }
    }
  }
  ```

### Mistake 2: Desinkronisasi SSR (Hydration Mismatch) pada Dynamic Theming
- **Gejala**: Layar berkedip (*Flash of Unstyled Content/Theme*) atau konsol memunculkan warning `Hydration failed because the initial UI does not match the server-rendered UI`.
- **Penyebab Utama**: Pengecekan tema (e.g., `localStorage.getItem('theme')`) dijalankan di dalam hook `useEffect`, sementara server merender dengan tema default.
- **Solusi**: Hindari evaluasi tema via React state untuk render inisial. Suntikkan script sinkron kecil (*blocking inline script*) pada header HTML yang menetapkan kelas/atribut data tema pada tag `<html>` sebelum rendering halaman dimulai:
  ```html
  <script>
    (function() {
      const theme = localStorage.getItem('theme') || 'system';
      const resolvedTheme = theme === 'system' 
        ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
        : theme;
      document.documentElement.setAttribute('data-theme', resolvedTheme);
    })();
  </script>
  ```

### Mistake 3: Kehilangan Aksesibilitas pada Komponen Polimorfik
- **Gejala**: Mengubah Button menjadi tautan via `asChild` menghilangkan navigasi keyboard native atau melanggar role WAI-ARIA.
- **Solusi**: Pastikan primitive memetakan keyboard listeners (`onKeyDown` untuk tombol Spasi vs tautan Enter) dan atribut ARIA yang relevan sesuai elemen DOM yang dihasilkan.

---

## 11. Best Practices & Production Checklist

### Pre-Commit / Build Time Checklist
- [ ] Token terdefinisi lengkap di schema JSON dan lulus validasi skema DTCG.
- [ ] Seluruh warna fungsional telah melalui audit kontras rasio WCAG 2.2 AA (minimal 4.5:1 untuk normal text, 3:1 untuk large text/UI controls).
- [ ] Tidak ada referensi nilai *hardcoded* (hex, pixel) di file komponen selain CSS Variables token.
- [ ] Type definition generator mengekspor types yang *strict* tanpa tipe `any`.
- [ ] Package JSON menandai seluruh file bebas *side-effect* (`"sideEffects": false`).

### CI/CD Quality Gating Checklist
- [ ] **Lint Rule**: Eksekusi `@typescript-eslint` dengan *strict-type-checking*.
- [ ] **Bundle Budget**: Memasang `@size-limit/preset-small-lib` untuk membatasi ukuran komponen (misal: Button maksimal < 2.5KB gzipped).
- [ ] **Automated Visual Regression**: Uji komponen di headless Chromium/Firefox/WebKit menggunakan Playwright/Chromatic di berbagai resolusi layar dan kontras tema.
- [ ] **Automated A11y Suite**: Eksekusi `axe-core` pada Storybook untuk memverifikasi nol pelanggaran level kritis dan serius.

---

## 12. Hands-on Practice: Membangun Core Design System Package

Ikuti tahapan instruksional ini untuk memvalidasi pemahaman arsitektur sistem.

### Langkah 1: Inisialisasi Repositori Monorepo
Buka terminal dan eksekusi instruksi berikut:
```bash
mkdir enterprise-design-system
cd enterprise-design-system
pnpm init
touch pnpm-workspace.yaml
```

Isi `pnpm-workspace.yaml`:
```yaml
packages:
  - 'packages/*'
```

### Langkah 2: Setup Package Token (`packages/tokens`)
```bash
mkdir -p packages/tokens/src/tokens
mkdir -p packages/tokens/scripts
cd packages/tokens
pnpm init
pnpm add -D style-dictionary tsx typescript
```

Buat file token: `packages/tokens/src/tokens/color.json`
```json
{
  "ds": {
    "color": {
      "palette": {
        "blue-60": { "$value": "#0958d9", "$type": "color" },
        "neutral-10": { "$value": "#ffffff", "$type": "color" }
      },
      "action": {
        "primary": {
          "default": { "$value": "{ds.color.palette.blue-60}", "$type": "color" },
          "text": { "$value": "{ds.color.palette.neutral-10}", "$type": "color" }
        }
      }
    }
  }
}
```

Buat script builder: `packages/tokens/scripts/build.ts`
```typescript
import StyleDictionary from 'style-dictionary';

const sd = new StyleDictionary({
  source: ['src/tokens/**/*.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      prefix: 'ds',
      buildPath: 'dist/css/',
      files: [
        {
          destination: 'tokens.css',
          format: 'css/variables',
          options: { outputReferences: true }
        }
      ]
    }
  }
});

await sd.buildAllPlatforms();
```

Tambahkan ke `packages/tokens/package.json`:
```json
{
  "name": "@org/tokens",
  "version": "0.1.0",
  "main": "./dist/css/tokens.css",
  "scripts": {
    "build": "tsx scripts/build.ts"
  }
}
```

Jalankan build token:
```bash
pnpm run build
```

---

## 13. Exercises

### Level Easy
Modifikasi file `packages/tokens/src/tokens/color.json` untuk menambahkan skala netral (`neutral-20` sampai `neutral-90`). Ekspor hasilnya dan validasi bahwa file `dist/css/tokens.css` memperbarui pemetaan CSS Variables secara otomatis.

### Level Medium
Buat komponen `Badge` di dalam `packages/react` yang menerima prop `status` (`'success' | 'warning' | 'error' | 'neutral'`) dan `variant` (`'solid' | 'subtle'`). Komponen wajib mengonsumsi token yang didefinisikan secara khusus untuk semantic feedback surfaces, serta menyertakan role `status` dan label teks yang dapat diakses oleh screen reader secara otomatis jika hanya ikon yang ditampilkan.

### Level Hard
Implementasikan sebuah token parser plugin kustom untuk *Style Dictionary* yang mendeteksi rasio kontras warna secara dinamis saat tahap *build time*. Jika semantic token untuk teks (`--ds-action-primary-text`) di atas latar belakang (`--ds-action-primary-default`) memiliki kontras rasio WCAG di bawah 4.5:1, proses kompilasi CI harus membatalkan build dan melempar *Error Exception* yang merinci kalkulasi kontras beserta hex value yang melanggar.

---

## 14. Challenge: Multi-Brand Dynamic Swap Engine Tanpa Runtime Overhead

### Skenario Tantangan
Perusahaan Anda memiliki arsitektur Micro-Frontend di mana aplikasi induk meng-host tiga modul bisnis yang dimiliki oleh entitas anak perusahaan independen. Setiap modul dimuat secara runtime (Module Federation) di dalam satu viewport browser.

### Batasan Teknis
1. Tidak diperkenankan me-reload halaman ketika bertukar brand.
2. Tidak boleh ada styling leak: Modul Brand A harus tetap mempertahankan visual Brand A, bahkan ketika berada di dalam dashboard Brand B.
3. Nol biaya komputasi CSS-in-JS (dilarang menggunakan library runtime CSS-in-JS seperti Emotion atau Styled Components).
4. Solusi harus berbasis CSS Custom Properties, Scoped Data Attributes, dan AST-compiled output dari Design Token pipeline.

### Tugas Anda
Rancang dokumen arsitektur dan potongan kode lengkap (token configuration, scoped CSS layer injection, dan React ThemeBoundary container) yang mampu mengisolasi sub-pohon DOM aplikasi agar secara dinamis mengadopsi token brand spesifik secara independen tanpa memicu re-render pada seluruh komponen tree di luarnya.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. **Apa perbedaan mendasar antara Global Token dan Semantic Token dalam arsitektur Design System?**
   - A. Global Token digunakan di platform web, sedangkan Semantic Token khusus mobile (Android/iOS).
   - B. Global Token mendefinisikan nilai absolut (primitif) tanpa konteks, sedangkan Semantic Token memberikan konteks fungsional/intent atas nilai tersebut.
   - C. Global Token berformat CSS, sedangkan Semantic Token berformat JSON.
   - D. Semantic Token diproses pada saat runtime, sedangkan Global Token dikompilasi saat build time.

2. **Format standar yang saat ini didorong oleh W3C DTCG untuk mendefinisikan design tokens menggunakan ekstensi format data:**
   - A. YAML
   - B. XML
   - C. JSON
   - D. ProtoBuf

3. **Mengapa penambahan `"sideEffects": false` pada `package.json` penting bagi library Design System?**
   - A. Untuk mencegah script eksternal menyuntikkan malware.
   - B. Mengizinkan bundler konsumen untuk melakukan *tree-shaking* secara agresif terhadap modul yang tidak digunakan.
   - C. Menonaktifkan CSS transition dan animation agar performa lebih cepat.
   - D. Memastikan fungsi React rendering tidak memicu side effect asynchronous.

4. **Karakteristik utama dari komponen headless adalah:**
   - A. Tidak memiliki representasi visual bawaan dan hanya menangani logic, state, keyboard navigation, dan aksesibilitas WAI-ARIA.
   - B. Komponen yang hanya bisa dirender di server-side (RSC).
   - C. Komponen yang tidak memerlukan unit testing.
   - D. Komponen yang khusus dibuat tanpa JavaScript.

5. **Rasio kontras minimum yang diwajibkan oleh WCAG 2.2 Level AA untuk teks standar terhadap latar belakangnya adalah:**
   - A. 3.0:1
   - B. 4.5:1
   - C. 7.0:1
   - D. 2.0:1

---

### Bagian 2: Intermediate (Analisis Singkat)

6. Jelaskan bagaimana pola polimorfik `asChild` (seperti yang digunakan oleh Radix Primitives) menyelesaikan masalah *DOM wrapper pollution* jika dibandingkan dengan pendekatan `as="a"` tradisional!
7. Dalam monorepo design system, mengapa kita sebaiknya mengompilasi distribusi kode ke dalam dua modul sekaligus: ESM (*ECMAScript Modules*) dan CJS (*CommonJS*)?
8. Bagaimana CSS Cascading Variables mempermudah implementasi *Dark Mode* jika dibandingkan dengan pendekatan pengalihan kelas styling global konvensional?
9. Apa dampak penggunaan barrel file (`export * from './Component'`) berjenjang terhadap waktu kompilasi (*cold start*) bundler modern seperti Vite atau Webpack pada aplikasi konsumen skala besar?
10. Sebutkan urutan hierarki resolusi token yang ideal jika Anda ingin mengubah warna outline state interaktif pada komponen `Input` tanpa memengaruhi warna outline komponen `Button`!

---

### Bagian 3: Production Case Scenarios

11. **Skenario Kasus 1**: Tim Anda merilis versi mayor baru dari Design System yang mengubah nama variabel CSS token secara menyeluruh. Aplikasi produk skala enterprise memiliki ribuan baris kode yang mengonsumsi variabel lama. Bagaimana strategi migrasi arsitektural Anda agar produk tidak mengalami visual regression massal dan tim produk tidak terblokir untuk melakukan adopsi secara bertahap?
12. **Skenario Kasus 2**: Di aplikasi portal kesehatan, komponen Modal Anda yang telah patuh aksesibilitas memunculkan bug kritis di browser Safari iOS: ketika modal dibuka, pengguna screen reader (VoiceOver) masih dapat memfokuskan dan membaca elemen di belakang modal (*background page bleed*). Bagaimana Anda mengatasinya di tingkat arsitektur komponen headless?
13. **Skenario Kasus 3**: Audit performa aplikasi mencatat penurunan drastis pada metrik *Interaction to Next Paint* (INP) di tabel data yang merender 500 baris komponen `Select` kustom dari design system Anda. Setiap komponen `Select` membungkus instance state React independen dan me-resolve ratusan baris CSS Modules. Analisis akar masalahnya dan berikan rekayasa perbaikan arsitekturalnya!

---

## Kunci Jawaban & Panduan Evaluasi

### Bagian 1
1. **B**: Global Token mendefinisikan nilai absolut (misal: `#000`), sedangkan Semantic Token memberikan maksud/konteks (misal: `color.text.default`).
2. **C**: JSON (JavaScript Object Notation) dengan struktur metadata khusus seperti `$value` dan `$type`.
3. **B**: Memberi petunjuk formal kepada bundler bahwa file yang tidak diimpor secara langsung dapat dipangkas secara aman dari bundle final (*Dead Code Elimination*).
4. **A**: Komponen headless mengisolasi fungsionalitas murni tanpa opini styling visual.
5. **B**: 4.5:1 untuk normal text, sedangkan 3.0:1 berlaku untuk large text (18pt/24px atau 14pt/18.5px bold) serta UI control boundaries.

### Bagian 2
6. **Jawaban Inti**: Pendekatan `as="tag"` sering kali memicu konflik TypeScript types pada prop elemen DOM dan secara teknis dapat merusak elemen semantik jika dioperkan komponen kustom lain. Pola `asChild` murni mendelegasikan props, ref, dan event handling ke immediate child tunggal tanpa menambahkan elemen wrapper `<div>` ekstra di DOM, sehingga struktur nesting DOM tetap bersih dan valid secara semantik.
7. **Jawaban Inti**: ESM adalah standar modern browser dan bundler generasi baru yang mendukung tree-shaking native secara optimal. Namun, ekosistem enterprise legacy dan beberapa tooling Node.js SSR/testing environment (seperti Jest versi lawas) masih berjalan di environment CJS murni. Menyediakan dual build menjamin interoperabilitas total tanpa memaksa konsumen mengubah toolchain mereka.
8. **Jawaban Inti**: Dengan CSS Variables, browser menangani pergantian nilai secara native pada tingkat compositing engine. Kita hanya perlu mendefinisikan ulang nilai variabel di level parent scope/root (misal: atribut `[data-theme="dark"]`), tanpa perlu mengeksekusi komputasi ulang runtime JavaScript atau mengganti ratusan utility classes pada setiap elemen HTML.
9. **Jawaban Inti**: Barrel file memaksa compiler untuk mem-parse AST dari ratusan file modul yang saling tereksport meskipun yang dibutuhkan aplikasi hanya satu fungsi/komponen kecil. Ini memperlambat resolving module graph, memperbesar memory overhead pada build tools, dan sering merusak algoritma tree-shaking jika terjadi circular dependency.
10. **Jawaban Inti**: Component Token (`input.border.focus`) -> me-referensikan Semantic Token (`color.border.interactive.focus`) -> me-referensikan Global Token (`color.blue.600`). Dengan mengubah mapping di tingkat `input.border.focus`, kita mengisolasi perubahan warna outline spesifik pada Input tanpa mengubah semantic token yang dipakai bersama oleh Button.

### Bagian 3
11. **Panduan Penilaian Kasus 1**:
    - *Solusi Arsitektur*: Menerapkan **Compatibility Aliasing Layer** pada compiler Style Dictionary.
    - Parser menghasilkan file `compatibility-tokens.css` yang memetakan nama variabel CSS lama ke variabel CSS baru: `--ds-color-old-name: var(--ds-semantic-color-new-name);`.
    - Menyediakan codemod script (`jscodeshift`) otomatis untuk tim konsumen guna mentransformasikan nama API komponen dan CSS variable di repository mereka secara otomatis saat siap migrasi.
12. **Panduan Penilaian Kasus 2**:
    - *Solusi Arsitektur*: Menerapkan mekanisme **DOM Accessibility Tree Inerting** saat modal di-mount.
    - Menggunakan atribut HTML modern `inert` pada node saudara (*sibling nodes*) dari root modal, atau memanggil utilitas primitive seperti `aria-hidden="true"` pada seluruh elemen di luar portal Modal container.
    - Mengunci focus trap engine agar secara strict membatasi siklus tab keyboard dan gesture swipe VoiceOver hanya pada node di dalam container modal.
13. **Panduan Penilaian Kasus 3**:
    - *Akar Masalah*: Over-instantiation React context and internal state engines per baris, duplikasi listener DOM, serta kalkulasi DOM node berlebih (500 instance select me-render 500 virtual popover nodes).
    - *Solusi Arsitektur*:
      1. Terapkan **Virtual Windowing** (`@tanstack/react-virtual`): hanya me-render baris tabel yang terlihat di viewport.
      2. Terapkan arsitektur **Flyweight / Shared Controller**: Select tidak membuka dropdown terpisah per baris. Satu portal Popover global dibagi bersama oleh seluruh baris tabel; popover hanya diaktifkan dan diposisikan secara absolut ketika baris tertentu masuk ke mode edit/interaksi.

---

## 16. Summary

1. **Arsitektur Tiga Tingkat (Global, Semantic, Component)** adalah fondasi utama skalabilitas Design System lintas platform dan multi-brand.
2. **Style Dictionary** dan AST Token Engine bertindak sebagai kompilator *single source of truth*, mengeliminasi desinkronisasi desain dengan menghasilkan artefak target native secara otomatis.
3. **Pemisahan Headless Primitives dan Presentation Styling Layer** menjamin aksesibilitas WAI-ARIA dan robustness fungsional yang independen dari evolusi estetika antarmuka.
4. **Monorepo Enterprise Modern** memerlukan konfigurasi distribusi yang teliti: *strict package isolation*, validasi *tree-shaking*, penanganan SSR hydration yang tepat, dan *dual-build packaging* (ESM/CJS).