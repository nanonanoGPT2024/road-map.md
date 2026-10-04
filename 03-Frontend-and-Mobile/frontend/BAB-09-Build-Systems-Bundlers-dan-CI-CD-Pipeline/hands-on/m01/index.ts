┌────────────────────────────────────────────────────────────────────────┐
│                        DEVELOPER WORKSPACE                             │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ Git Push (Branch: Release/* / Main)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        CI/CD PIPELINE ORCHESTRATOR                     │
│                                                                        │
│ ┌──────────────────────┐  Cache Hit   ┌──────────────────────────────┐ │
│ │  Job 1: Setup & Deps ├─────────────►│ Restore Node Cache / Store   │ │
│ │  (pnpm fetch/install)│              └──────────────┬───────────────┘ │
│ └──────────┬───────────┘                             │                 │
│            ▼                                         ▼                 │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │  Job 2: Matrix Validation [Parallel Workers]                       │ │
│ │  ├── Worker A: TypeScript Compiler (`tsc --noEmit`)                 │ │
│ │  ├── Worker B: Linter & AST Analyzer (`eslint --max-warnings 0`)   │ │
│ │  └── Worker C: Unit/Integration Suite (`vitest run --coverage`)    │ │
│ └────────────────────────────────────┬───────────────────────────────┘ │
│                                      │ All Gates Passed                │
│                                      ▼                                 │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │  Job 3: Optimized Production Build Engine                          │ │
│ │  ├── Turbopack / Rollup Multi-core Compilation                     │ │
│ │  ├── Scope Hoisting, Terser/ESBuild Minification                   │ │
│ │  ├── Source Map Upload to Telemetry Server (Sentry)                │ │
│ │  └── Generation of Subresource Integrity (SRI) Manifest            │ │
│ └────────────────────────────────────┬───────────────────────────────┘ │
│                                      │                                 │
│                                      ▼                                 │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │  Job 4: Artifact Attestation & Security Scan                       │ │
│ │  ├── Software Bill of Materials (SBOM) Generation via Syft         │ │
│ │  └── Trivy Vulnerability Scan                                      │ │
│ └────────────────────────────────────┬───────────────────────────────┘ │
└──────────────────────────────────────┼─────────────────────────────────┘
                                       │ Deploy Stage Artifact
                                       ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        EDGE INFRASTRUCTURE (CDN)                       │
│  ├── /assets/*.hash.js       (Cache-Control: public, max-age=31536000) │
│  └── /index.html             (Cache-Control: no-cache, must-revalidate)│
└────────────────────────────────────────────────────────────────────────┘
