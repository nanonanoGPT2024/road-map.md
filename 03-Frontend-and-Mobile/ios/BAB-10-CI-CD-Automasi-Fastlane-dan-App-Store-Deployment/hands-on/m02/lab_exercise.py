#!/usr/bin/env python3
"""
Lab Hands-on: iOS CI/CD, Fastlane Automation, & App Store Deployment Engine
Bab 10: CI/CD, Automasi Fastlane, & App Store Deployment - Modul 02 Deep Dive

Script ini memodelkan runtime Fastlane dan App Store Connect API pipeline:
1. App Store Connect API JWT Generator (ES256/Token Auth simulation via HMAC/SHA256).
2. Fastlane Match: Enkripsi/Dekripsi sertifikat distribusi dan verifikasi MobileProvision.
3. Gym (xcodebuild archive wrapper): Kompilasi mock binary, signing, & bundle slicing.
4. Pilot / TestFlight Delivery: Multipart upload simulation, build processing, & distribution.
"""

import sys
import time
import json
import base64
import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Terminal ANSI Styling
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"


def log_fastlane(step: str, message: str, level: str = "INFO") -> None:
    """Format log menyerupai format output Fastlane CLI."""
    timestamp = time.strftime("%H:%M:%S")
    color = GREEN if level == "INFO" else (YELLOW if level == "WARN" else RED)
    prefix = f"{WHITE}[{timestamp}]{RESET}"
    if step:
        print(f"{prefix} {CYAN}--- Step: {step} ---{RESET}")
    print(f"{prefix} {color}[{level}]{RESET} {message}")


@dataclass
class ProvisioningProfile:
    name: str
    uuid: str
    bundle_id: str
    team_id: str
    entitlements: Dict[str, bool]
    expired_at: float
    raw_signature: str

    def is_valid(self, target_bundle_id: str) -> bool:
        """Memvalidasi integritas bundle ID dan tanggal kedaluwarsa profile."""
        now = time.time()
        return self.bundle_id == target_bundle_id and now < self.expired_at


class AppStoreConnectTokenProvider:
    """
    Simulasi pembuatan JWT untuk App Store Connect API.
    Sesuai spesifikasi Apple: Header (alg=ES256, kid=KeyID), Payload (iss, exp, aud).
    """
    def __init__(self, key_id: str, issuer_id: str, private_key_seed: bytes):
        self.key_id = key_id
        self.issuer_id = issuer_id
        self.private_key_seed = private_key_seed

    @staticmethod
    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

    def generate_token(self, expiration_seconds: int = 1200) -> str:
        header = {
            "alg": "ES256",
            "kid": self.key_id,
            "typ": "JWT"
        }
        payload = {
            "iss": self.issuer_id,
            "exp": int(time.time()) + expiration_seconds,
            "aud": "appstoreconnect-v1"
        }

        enc_header = self._b64url_encode(json.dumps(header).encode('utf-8'))
        enc_payload = self._b64url_encode(json.dumps(payload).encode('utf-8'))
        signing_input = f"{enc_header}.{enc_payload}".encode('utf-8')

        # Simulasi tanda tangan ECDSA menggunakan HMAC-SHA256 untuk standard library Python
        signature = hmac.new(self.private_key_seed, signing_input, hashlib.sha256).digest()
        enc_signature = self._b64url_encode(signature)

        return f"{enc_header}.{enc_payload}.{enc_signature}"


class MatchSyncEngine:
    """
    Simulasi modul Fastlane Match:
    Sinkronisasi sertifikat dan provisioning profiles terenkripsi dari git repo.
    """
    def __init__(self, git_url: str, repo_passphrase: str):
        self.git_url = git_url
        self.passphrase = repo_passphrase
        self._key = hashlib.sha256(repo_passphrase.encode('utf-8')).digest()

    def sync_certificates(self, app_identifier: str, type_profile: str) -> ProvisioningProfile:
        log_fastlane("match", f"Mengakses remote secure repo: {self.git_url}")
        time.sleep(0.3)
        log_fastlane("match", f"Mendekripsi sertifikat & profile untuk {app_identifier} [{type_profile}]")
        
        # Validasi passphrase dekripsi
        derived = hashlib.pbkdf2_hmac('sha256', self.passphrase.encode('utf-8'), b'fastlane_match_salt', 1000)
        signature_proof = hashlib.sha256(derived).hexdigest()[:16]

        # Inisialisasi Mock Distribution Profile
        profile = ProvisioningProfile(
            name=f"match AppStore {app_identifier}",
            uuid="87e2f5b4-d567-4ab2-b2fa-90812abce8f1",
            bundle_id=app_identifier,
            team_id="ABCDE12345",
            entitlements={
                "get-task-allow": False,
                "aps-environment": True,
                "com.apple.developer.associated-domains": True
            },
            expired_at=time.time() + (365 * 86400),
            raw_signature=signature_proof
        )
        log_fastlane("match", f"Sertifikat distribusi valid. Profile UUID: {profile.uuid}")
        return profile


class GymBuildSimulator:
    """
    Simulasi modul Fastlane Gym (Build & Packaging Tool):
    Memaketkan Mach-O binary, resource bundling, code signing injection, dan export .ipa.
    """
    def __init__(self, workspace: str, scheme: str, configuration: str):
        self.workspace = workspace
        self.scheme = scheme
        self.configuration = configuration

    def build_app(self, profile: ProvisioningProfile, build_num: int) -> Tuple[str, str, Dict[str, str]]:
        log_fastlane("gym", f"xcodebuild clean archive -workspace {self.workspace} -scheme {self.scheme} -configuration {self.configuration}")
        time.sleep(0.4)

        # Mocking Mach-O binary compilation artifacts
        pseudo_binary = f"MACHO_BINARY_DATA_{self.scheme}_{build_num}_{profile.uuid}".encode('utf-8')
        macho_hash = hashlib.sha256(pseudo_binary).hexdigest()

        log_fastlane("gym", f"Binary linked. Entitlements injected. Embedded provisioning profile matched.")
        log_fastlane("gym", f"Codesign identity: Apple Distribution: Enterprise Labs ({profile.team_id})")

        ipa_name = f"{self.scheme}_{build_num}.ipa"
        dsym_uuid = hashlib.md5(f"dsym_{macho_hash}".encode('utf-8')).hexdigest()
        
        metadata = {
            "binary_sha256": macho_hash,
            "dsym_uuid": dsym_uuid,
            "embedded_profile_uuid": profile.uuid,
            "size_mb": "42.8 MB"
        }
        return ipa_name, dsym_uuid, metadata


class PilotDeployer:
    """
    Simulasi modul Fastlane Pilot (TestFlight Delivery):
    Otentikasi via App Store Connect API, chunked upload binary, dan pemrosesan remote.
    """
    def __init__(self, jwt_token: str):
        self.jwt_token = jwt_token

    def upload_to_testflight(self, ipa_name: str, build_metadata: Dict[str, str], changelog: str) -> bool:
        log_fastlane("pilot", f"Memverifikasi kredensial token App Store Connect API...")
        if len(self.jwt_token.split('.')) != 3:
            log_fastlane("pilot", "JWT Token tidak valid!", "ERROR")
            return False

        log_fastlane("pilot", f"Menginisiasi chunked upload untuk {ipa_name} ({build_metadata['size_mb']})")
        total_chunks = 4
        for i in range(1, total_chunks + 1):
            time.sleep(0.15)
            log_fastlane("", f"Uploading chunk {i}/{total_chunks} [{(i/total_chunks)*100:.0f}%]...")

        log_fastlane("pilot", f"dSYM dikirimkan ke Apple Crash Reporting service. UUID: {build_metadata['dsym_uuid']}")
        log_fastlane("pilot", f"Memperbarui 'What to Test': '{changelog}'")
        
        # Simulasi Apple Transporter processing state
        log_fastlane("pilot", "Menunggu Apple backend processing...")
        time.sleep(0.3)
        log_fastlane("pilot", "Build status berganti dari 'Processing' -> 'Ready to Test'", "INFO")
        return True


def run_pipeline() -> None:
    start_time = time.time()
    steps_record = []

    print(f"\n{BOLD}{BG_BLUE}  FASTLANE AUTOMATION & APP STORE DEPLOYMENT ENGINE  {RESET}\n")

    # Konfigurasi Input Pipeline
    bundle_id = "com.leadsystem.secureapp"
    scheme = "SecureApp"
    key_id = "KEY99887766"
    issuer_id = "11223344-5566-7788-9900-aabbccddeeff"
    git_certs_repo = "git@github.com:leadsystem-infra/certificates.git"
    git_passphrase = "master_encryption_key_demo"

    # Step 1: Pre-build Checks & Build Number Bumping
    s1_start = time.time()
    log_fastlane("ensure_git_status_clean", "Checking working tree for uncommitted changes...")
    time.sleep(0.2)
    current_build_number = 142
    next_build_number = current_build_number + 1
    log_fastlane("increment_build_number", f"Build version di-bump dari {current_build_number} ke {next_build_number}")
    steps_record.append(("increment_build_number", time.time() - s1_start, "SUCCESS"))

    # Step 2: Code Signing via Match
    s2_start = time.time()
    match_engine = MatchSyncEngine(git_certs_repo, git_passphrase)
    profile = match_engine.sync_certificates(bundle_id, "appstore")
    if not profile.is_valid(bundle_id):
        log_fastlane("match", "Provisioning Profile invalid atau expired!", "ERROR")
        sys.exit(1)
    steps_record.append(("match", time.time() - s2_start, "SUCCESS"))

    # Step 3: Compile and Archive with Gym
    s3_start = time.time()
    gym = GymBuildSimulator(f"{scheme}.xcworkspace", scheme, "Release")
    ipa_path, dsym_id, meta = gym.build_app(profile, next_build_number)
    log_fastlane("gym", f"Sukses mengekspor IPA: {ipa_path} (SHA-256: {meta['binary_sha256'][:12]}...)")
    steps_record.append(("gym", time.time() - s3_start, "SUCCESS"))

    # Step 4: JWT App Store Connect Authentication
    s4_start = time.time()
    log_fastlane("app_store_connect_api_key", "Membuat authenticated API session token")
    token_provider = AppStoreConnectTokenProvider(key_id, issuer_id, b"private_key_pkcs8_seed")
    jwt_token = token_provider.generate_token()
    log_fastlane("app_store_connect_api_key", f"Bearer Token di-generate (Key ID: {key_id})")
    steps_record.append(("app_store_connect_api_key", time.time() - s4_start, "SUCCESS"))

    # Step 5: TestFlight Deployment (Pilot)
    s5_start = time.time()
    pilot = PilotDeployer(jwt_token)
    upload_success = pilot.upload_to_testflight(
        ipa_name=ipa_path,
        build_metadata=meta,
        changelog="Hotfix: Performance optimizations on memory cache and auth pipeline."
    )
    status_str = "SUCCESS" if upload_success else "FAILED"
    steps_record.append(("pilot", time.time() - s5_start, status_str))

    # Pipeline Summary Table
    total_elapsed = time.time() - start_time
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{WHITE}fastlane.tools finished successfully 🎉{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{'Step Name':<32} {'Time':<12} {'Status':<10}{RESET}")
    print(f"{'-'*60}")
    for name, dur, status in steps_record:
        status_color = GREEN if status == "SUCCESS" else RED
        print(f"{name:<32} {dur:.2f}s        {status_color}{status}{RESET}")
    print(f"{'-'*60}")
    print(f"{BOLD}Total Duration:{RESET} {total_elapsed:.2f}s\n")


if __name__ == "__main__":
    run_pipeline()