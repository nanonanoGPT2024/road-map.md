+---------------------------------------------------------------------------------------------------+
|                                      GIT REPOSITORY WORKFLOW                                      |
+---------------------------------------------------------------------------------------------------+
                                                  |
                 [Developer Git Push: feat/* / fix/* / main / release/*]
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                  CI ORCHESTRATOR (GitHub Actions)                                 |
|                                                                                                   |
|  +---------------------------+  +---------------------------+  +-------------------------------+  |
|  | Job 1: Static Analysis    |  | Job 2: Unit & UI Tests    |  | Job 3: Build & Distribution   |  |
|  | - SwiftLint / SwiftFormat |  | - xcodebuild test         |  | - fastlane match (Sync Certs) |  |
|  | - Periphery (Dead Code)   |  | - Parallel Simulators     |  | - gym / xcodebuild archive    |  |
|  | - Dependency Audit (SPM)  |  | - Slather (Code Coverage) |  | - deliver / pilot (Upload)    |  |
|  +---------------------------+  +---------------------------+  +-------------------------------+  |
+---------------------------------------------------------------------------------------------------+
                                                  |
                    +-----------------------------+-----------------------------+
                    |                                                           |
                    v (Fetch Certs / Profiles via Git Storage)                  v (Authenticate API)
+---------------------------------------+             +---------------------------------------------+
|    CERTIFICATE STORAGE (Private Git)  |             |      APP STORE CONNECT API (Headless JWT)   |
|                                       |             |                                             |
|  - Encrypted Distribution Cert (.p12) |             |  - Issuer ID                                |
|  - Encrypted Apple WWDRCA             |             |  - Key ID                                   |
|  - Provisioning Profiles (.mobileprov)|             |  - Private Key (.p8)                        |
+---------------------------------------+             +---------------------------------------------+
                    |                                                           |
                    +-----------------------------+-----------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                     MACOS EPHEMERAL BUILD RUNNER                                  |
|                                                                                                   |
| 1. Create Transient Keychain: `fastlane_tmp_keychain`                                             |
| 2. Import Decrypted Keys & Certificates                                                           |
| 3. Resolve SPM Dependencies (Cache: ~/Library/Caches/org.swift.swiftpm)                           |
| 4. Compile & Link: `xcodebuild -workspace App.xcworkspace -scheme Production -configuration ...`  |
| 5. Sign Binary: `codesign -s "Apple Distribution: ..." Payload/App.app`                           |
| 6. Package: Generate Production IPA (`App.ipa`) & dSYM bundles                                    |
| 7. Cleanup: Delete `fastlane_tmp_keychain`                                                        |
+---------------------------------------------------------------------------------------------------+
                                                  |
                    +-----------------------------+-----------------------------+
                    | (Upload Crash Artifacts)                                  | (Upload Binary & Meta)
                    v                                                           v
+---------------------------------------+             +---------------------------------------------+
|     CRASH MONITORING (e.g. Sentry)    |             |              APPLE INFRASTRUCTURE           |
|                                       |             |                                             |
|  - App.app.dSYM.zip (Debug Symbols)   |             |  - TestFlight Internal (QA Engineers)       |
|  - Proguard / Swift Source Maps       |             |  - TestFlight External (Beta Testers)       |
|                                       |             |  - App Store Review (Production Release)    |
+---------------------------------------+             +---------------------------------------------+
