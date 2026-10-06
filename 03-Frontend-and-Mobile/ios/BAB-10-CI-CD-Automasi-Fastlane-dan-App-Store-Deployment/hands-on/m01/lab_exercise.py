#!/usr/bin/env python3
"""
Lab Exercise: iOS CI/CD Automation Engine Simulator
Topik: BAB-10-CI-CD-Automasi-Fastlane-dan-App-Store-Deployment (Modul 01)
Simulasi eksekusi pipeline Fastlane, Code Signing (Match), Build (Gym), Test (Scan), dan TestFlight (Pilot).
"""

import sys
import time
import os
import random
from typing import Dict, List, Optional

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_BG_DARK = "\033[40m"


def print_banner():
    banner = f"""
{CLR_CYAN}{CLR_BOLD}======================================================================
     iOS CI/CD & FASTLANE AUTOMATION PIPELINE SIMULATOR (v2.1)
           BAB 10: Fastlane, Match, Gym, Scan & App Store Connect
======================================================================{CLR_RESET}
"""
    print(banner)


def log_step(lane: str, action: str, message: str):
    prefix = f"{CLR_MAGENTA}[fastlane:{lane}]{CLR_RESET} {CLR_CYAN}▸ {action}:{CLR_RESET}"
    print(f"{prefix} {message}")


def log_success(message: str):
    print(f" {CLR_GREEN}{CLR_BOLD}✔ [SUCCESS]{CLR_RESET} {message}")


def log_warn(message: str):
    print(f" {CLR_YELLOW}{CLR_BOLD}⚠ [WARNING]{CLR_RESET} {message}")


def log_error(message: str):
    print(f" {CLR_RED}{CLR_BOLD}✖ [FAILED]{CLR_RESET} {message}")


class FastlaneEngine:
    def __init__(self, app_id: str, scheme: str):
        self.app_id = app_id
        self.scheme = scheme
        self.build_number = 142
        self.version = "2.4.0"
        self.git_branch = "release/v2.4.0"
        self.provisioning_profile: Optional[str] = None
        self.cert_id: Optional[str] = None
        self.ipa_path: Optional[str] = None

    def step_ensure_git_clean(self) -> bool:
        log_step("common", "ensure_git_status_clean", "Checking working directory state...")
        time.sleep(0.3)
        dirty_chance = random.random()
        if dirty_chance < 0.1:
            log_error("Uncommitted changes detected in repo: `Podfile.lock` modified.")
            print(f"   {CLR_RED}Run `git stash` or commit changes before triggering lane.{CLR_RESET}")
            return False
        log_success(f"Git working directory clean on branch: {CLR_BOLD}{self.git_branch}{CLR_RESET}")
        return True

    def step_increment_build_number(self):
        log_step("beta", "increment_build_number", f"Reading current build from Info.plist ({self.build_number})...")
        time.sleep(0.2)
        self.build_number += 1
        log_success(f"Updated CFBundleVersion to {CLR_BOLD}{self.build_number}{CLR_RESET} (Version: {self.version})")

    def step_run_scan_tests(self) -> bool:
        log_step("test", "scan", f"Invoking xcodebuild test -workspace App.xcworkspace -scheme {self.scheme}...")
        test_suites = [
            ("AuthServiceTests", 14),
            ("NetworkClientSpec", 28),
            ("PaymentFlowUITests", 6),
            ("KeychainHelperTests", 9),
        ]
        
        total_tests = sum(c for _, c in test_suites)
        print(f"   {CLR_BLUE}Running {total_tests} test cases across 4 test targets (iOS 17.4 Simulator)...{CLR_RESET}")
        
        for suite, count in test_suites:
            time.sleep(0.25)
            print(f"    • {suite}: {count} tests executed... {CLR_GREEN}PASSED{CLR_RESET}")
            
        log_success("All unit & integration tests succeeded! Code Coverage: 88.4%")
        return True

    def step_sync_code_signing(self, signing_type: str = "appstore") -> bool:
        log_step("signing", "match", f"Syncing certificates and provisioning profiles (type: {signing_type})...")
        print(f"   {CLR_YELLOW}Cloning git storage repo: git@github.com:myorg/ios-certificates.git{CLR_RESET}")
        time.sleep(0.3)
        print(f"   {CLR_YELLOW}Decrypting OpenSSL AES-256 certificate repository using MATCH_PASSWORD...{CLR_RESET}")
        time.sleep(0.3)

        self.cert_id = "Apple Distribution: Acme Global Ltd (TEAM9876XY)"
        profile_filename = f"match_AppStore_{self.app_id}.mobileprovision"
        self.provisioning_profile = profile_filename

        print(f"   Identity  : {CLR_CYAN}{self.cert_id}{CLR_RESET}")
        print(f"   Profile   : {CLR_CYAN}{self.provisioning_profile}{CLR_RESET}")
        print(f"   Bundle ID : {CLR_CYAN}{self.app_id}{CLR_RESET}")
        log_success("Installed valid signing certificate & provisioning profile to Keychain.")
        return True

    def step_build_app_gym(self) -> bool:
        log_step("build", "gym", f"Archiving project (Scheme: {self.scheme}, Config: Release)...")
        time.sleep(0.3)
        print(f"   {CLR_BLUE}▸ xcodebuild -archivePath ./build/App.xcarchive -sdk iphoneos archive{CLR_RESET}")
        time.sleep(0.4)
        print(f"   {CLR_BLUE}▸ Generating dSYM symbols for crash reporting...{CLR_RESET}")
        time.sleep(0.2)
        print(f"   {CLR_BLUE}▸ Exporting IPA with ExportOptions.plist (method: app-store)...{CLR_RESET}")
        time.sleep(0.3)

        self.ipa_path = f"./build/{self.scheme}_{self.version}_{self.build_number}.ipa"
        ipa_size_mb = round(random.uniform(42.5, 48.0), 2)
        log_success(f"Built IPA successfully: {CLR_BOLD}{self.ipa_path}{CLR_RESET} ({ipa_size_mb} MB)")
        return True

    def step_upload_testflight_pilot(self) -> bool:
        log_step("deploy", "pilot", "Authenticating with App Store Connect API (Key ID: 4N8X92KP)...")
        time.sleep(0.3)
        print(f"   {CLR_YELLOW}Uploading binary {self.ipa_path} to Apple Transport Service (iTMSTransporter)...{CLR_RESET}")
        
        # Progress bar simulation
        progress_steps = [15, 45, 75, 100]
        for p in progress_steps:
            time.sleep(0.2)
            filled = int(p / 5)
            bar = "█" * filled + "░" * (20 - filled)
            sys.stdout.write(f"\r   [{CLR_GREEN}{bar}{CLR_RESET}] {p}% Uploaded")
            sys.stdout.flush()
        print()

        log_success(f"Build {self.version} ({self.build_number}) successfully uploaded to TestFlight!")
        print(f"   {CLR_CYAN}Processing status: App Store Connect is processing symbols. Ready in ~5 mins.{CLR_RESET}")
        return True

    def run_beta_lane(self):
        print(f"\n{CLR_BOLD}{CLR_BG_DARK}=== TRIGGERING LANE: ios beta ==={CLR_RESET}\n")
        start_time = time.time()

        if not self.step_ensure_git_clean():
            log_error("Lane 'ios beta' aborted due to git dirty status.")
            return

        self.step_increment_build_number()

        if not self.step_run_scan_tests():
            log_error("Lane 'ios beta' aborted due to test failure.")
            return

        if not self.step_sync_code_signing("appstore"):
            log_error("Lane 'ios beta' aborted due to code signing issue.")
            return

        if not self.step_build_app_gym():
            log_error("Lane 'ios beta' aborted due to archive compilation error.")
            return

        self.step_upload_testflight_pilot()

        elapsed = round(time.time() - start_time, 2)
        print(f"\n{CLR_GREEN}{CLR_BOLD}======================================================================{CLR_RESET}")
        print(f"{CLR_GREEN}{CLR_BOLD}   FASTLANE SUMMARY: LANE 'ios beta' FINISHED SUCCESSFULLY in {elapsed}s{CLR_RESET}")
        print(f"{CLR_GREEN}{CLR_BOLD}======================================================================{CLR_RESET}\n")


def display_fastfile():
    code = f"""{CLR_YELLOW}# Sample Fastfile (Modul 01: CI/CD Automasi Fastlane){CLR_RESET}
default_platform(:ios)

platform :ios do
  desc "Push a new beta build to TestFlight"
  lane :beta do
    ensure_git_status_clean
    increment_build_number(xcodeproj: "App.xcodeproj")
    scan(scheme: "ProductionApp", clean: true)
    match(type: "appstore", readonly: is_ci)
    gym(
      scheme: "ProductionApp",
      export_method: "app-store",
      output_directory: "./build"
    )
    pilot(
      skip_waiting_for_build_processing: true,
      changelog: "CI automated build from commit"
    )
  end
end
"""
    print(code)


def interactive_menu():
    engine = FastlaneEngine(app_id="com.acme.mobile.ios", scheme="ProductionApp")
    
    while True:
        print_banner()
        print(f"{CLR_BOLD}Pilih Skenario Simulasi CI/CD & Fastlane:{CLR_RESET}")
        print(f" {CLR_CYAN}1.{CLR_RESET} Jalankan Lane Penuh (:beta -> TestFlight)")
        print(f" {CLR_CYAN}2.{CLR_RESET} Uji Tahap Fastlane Match (Code Signing Sync & Keystore)")
        print(f" {CLR_CYAN}3.{CLR_RESET} Uji Tahap Fastlane Scan (Automated Unit & UI Testing)")
        print(f" {CLR_CYAN}4.{CLR_RESET} Lihat Contoh Representasi Fastfile Standar")
        print(f" {CLR_CYAN}5.{CLR_RESET} Keluar Simulator")
        
        choice = input(f"\n{CLR_BOLD}Masukkan pilihan (1-5): {CLR_RESET}").strip()
        
        if choice == "1":
            engine.run_beta_lane()
        elif choice == "2":
            print()
            engine.step_sync_code_signing("appstore")
            print()
        elif choice == "3":
            print()
            engine.step_run_scan_tests()
            print()
        elif choice == "4":
            print()
            display_fastfile()
        elif choice == "5":
            print(f"\n{CLR_GREEN}Terima kasih telah menjalankan simulasi CI/CD Fastlane.{CLR_RESET}")
            break
        else:
            print(f"\n{CLR_RED}Pilihan tidak valid. Silakan pilih 1-5.{CLR_RESET}\n")

        input(f"{CLR_BOLD}Tekan [Enter] untuk kembali ke menu utama...{CLR_RESET}")


if __name__ == "__main__":
    try:
        interactive_menu()
    except KeyboardInterrupt:
        print(f"\n\n{CLR_YELLOW}Simulasi dihentikan oleh pengguna.{CLR_RESET}")
        sys.exit(0)
