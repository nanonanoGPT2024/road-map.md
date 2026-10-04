+---------------------------------------------------------------------------------------------------+
|                                  FASE 1: CONTINUOUS INTEGRATION (CI)                              |
+---------------------------------------------------------------------------------------------------+
  [Developer Git Push]
           │
           ▼
  ┌────────────────────────────────────────────────────────┐
  │                 GitHub Actions Runner                  │
  │                   (ubuntu-latest)                      │
  ├────────────────────────────────────────────────────────┤
  │ 1. Checkout Code + Node Setup (LTS)                    │
  │ 2. Install Deps (npm ci / yarn --frozen-lockfile)      │
  │ 3. Static Analysis: ESLint + TypeScript TypeCheck (tsc)│
  │ 4. Unit Testing: Jest (Mock Native Modules/TurboMods)  │
  │ 5. Component Integration: React Native Testing Library │
  └───────────────────────────┬────────────────────────────┘
                              │
                              ▼ (Pass)
+---------------------------------------------------------------------------------------------------+
|                              FASE 2: PARALLEL NATIVE MATRIX BUILDS                                |
+---------------------------------------------------------------------------------------------------+
              ┌───────────────┴────────────────┐
              │                                │
              ▼                                ▼
  ┌──────────────────────────────┐ ┌─────────────────────────────────────────┐
  │     ANDROID RUNNER           │ │              IOS RUNNER                 │
  │    (ubuntu-latest)           │ │            (macos-14 M1/M2)             │
  ├──────────────────────────────┤ ├─────────────────────────────────────────┤
  │ • Setup Java JDK 17 & NDK    │ │ • Select Xcode 15.x / 16.x              │
  │ • Restore Gradle Cache       │ │ • Restore CocoaPods & DerivedData Cache │
  │ • Fastlane Match / Keystore  │ │ • Fastlane Match (Decrypt Apple Certs)  │
  │ • Run Maestro E2E Headless   │ │ • Run Maestro iOS Simulator Test        │
  │ • ./gradlew bundleRelease    │ │ • Gym: Build & Archive .ipa             │
  │ • Output: release.aab        │ │ • Output: release.ipa                   │
  └──────────────┬───────────────┘ └────────────────────┬────────────────────┘
                 │                                      │
                 └──────────────────┬───────────────────┘
                                    │
                                    ▼
+---------------------------------------------------------------------------------------------------+
|                             FASE 3: CONTINUOUS DEPLOYMENT (FASTLANE)                              |
+---------------------------------------------------------------------------------------------------+
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │ Google Play Console API                        Apple App Store Connect API      │
  │ (Service Account JSON)                         (App Store Connect API Key p8)   │
  ├────────────────────────────────────────────────┼────────────────────────────────┤
  │ upload_to_play_store(                          │ upload_to_testflight(          │
  │   track: 'internal',                           │   skip_waiting_for_build_proc: │
  │   aab: 'release.aab'                           │     false,                         │
  │ )                                              │   ipa: 'release.ipa'           │
  │                                                │ )                              │
  └────────────────────────┬───────────────────────┴────────────────┬───────────────┘
                           │                                        │
                           ▼                                        ▼
                   [Play Internal Testers]                 [TestFlight Beta Team]
                           │                                        │
                           └───────────────────┬────────────────────┘
                                               │
                                               ▼
                              [Production Staged Rollout (10% -> 100%)]
