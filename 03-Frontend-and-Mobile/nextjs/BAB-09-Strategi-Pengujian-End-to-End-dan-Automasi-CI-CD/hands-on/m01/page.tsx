[ Developer Commit / PR ]
         │
         ▼
[ GitHub Actions: Workflow Trigger ]
         │
         ├─────────────────────────────────────────────┐
         ▼                                             ▼
[ Job: Lint, Typecheck & Static Sec ]       [ Job: Cache Restore Engine ]
(biome/eslint + tsc --noEmit + gitleaks)    (PNPM + Turborepo + Next Cache)
         │                                             │
         └──────────────────────┬──────────────────────┘
                                │
                                ▼
                    [ Job: Production Build ]
                    (next build: Standalone Output)
                                │
                                ├───────────────────────────────┐
                                ▼                               ▼
                [ Ephemeral DB Provisioning ]        [ Artifact Distribution ]
                (Neon/Supabase Branching API)         (Standalone .next + public)
                                │                               │
                                └───────────────┬───────────────┘
                                                │
                                                ▼
                                [ Job: Playwright Orchestration ]
                                (Matrix Shard: 1/4, 2/4, 3/4, 4/4)
                                                │
                ┌───────────────────────────────┴───────────────────────────────┐
                ▼                                                               ▼
        [ Shard 1..N: Browser Pool ]                                [ Global Setup: Auth State ]
   (Chromium, WebKit, Mobile Safari)                                (StorageState JWT Storage)
                │                                                               │
                └───────────────────────────────┬───────────────────────────────┘
                                                │
                                                ▼
                                  [ Target: Standalone Next.js App ]
                                                │
                        ┌───────────────────────┴───────────────────────┐
                        ▼                                               ▼
                [ PASS: Status Green ]                          [ FAIL: Diagnostics ]
                        │                                               │
                        ▼                                               ▼
            [ Ephemeral DB De-provision ]                      [ Upload Traces & Videos ]
                        │                                               │
                        ▼                                               ▼
             [ Trigger Deploy / Merge ]                        [ Notify via Webhook PR ]
