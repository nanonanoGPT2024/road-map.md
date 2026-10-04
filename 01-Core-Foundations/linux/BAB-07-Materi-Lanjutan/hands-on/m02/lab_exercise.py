#!/usr/bin/env python3
"""
Lab Hands-on: Tata Kelola Izin Linux, Engine Autentikasi PAM, dan Hardening
Kategori: 01-Core-Foundations / Bab 07 - Modul 02 Deep Dive

Skrip ini mengimplementasikan simulasi kernel-space & user-space untuk:
1. Linux DAC (Discretionary Access Control) Engine: Evaluasi Octal/rwx, SUID, SGID, dan Sticky Bit.
2. Pluggable Authentication Modules (PAM) Stack Processor: Algoritma evaluasi flag
   'required', 'requisite', 'sufficient', dan 'optional' dengan modul pam_faillock & pam_unix.
3. System Security Hardening Auditor: Deteksi miskonfigurasi perizinan file kritis (/etc/shadow, suid bins).
"""

import sys
import os
import time
import hashlib
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Tuple, Optional

# ANSI Color Codes untuk visualisasi terminal
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[91m"
CLR_GREEN  = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE   = "\033[94m"
CLR_CYAN   = "\033[96m"
CLR_WHITE  = "\033[97m"

def print_section(title: str):
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_WHITE}[+] {title}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*75}{CLR_RESET}")

def print_status(component: str, msg: str, success: bool = True):
    symbol = f"{CLR_GREEN}[PASS]{CLR_RESET}" if success else f"{CLR_RED}[FAIL]{CLR_RESET}"
    print(f"  {symbol} {CLR_BOLD}{component:<18}{CLR_RESET} : {msg}")


# ==============================================================================
# 1. LINUX DAC (Discretionary Access Control) SUBSYSTEM
# ==============================================================================

class FileMode:
    """Representasi bitmask izin POSIX: Special bits (SUID/SGID/Sticky) + User + Group + Others"""
    S_ISUID = 0o4000  # Set UID
    S_ISGID = 0o2000  # Set GID
    S_ISVTX = 0o1000  # Sticky Bit
    S_IRUSR = 0o0400  # Read User
    S_IWUSR = 0o0200  # Write User
    S_IXUSR = 0o0100  # Exec User
    S_IRGRP = 0o0040  # Read Group
    S_IWGRP = 0o0020  # Write Group
    S_IXGRP = 0o0010  # Exec Group
    S_IROTH = 0o0004  # Read Others
    S_IWOTH = 0o0002  # Write Others
    S_IXOTH = 0o0001  # Exec Others


@dataclass
class Inode:
    path: str
    owner_uid: int
    owner_gid: int
    mode: int
    is_directory: bool = False
    content: str = ""

    def mode_string(self) -> str:
        """Konversi integer mode menjadi representasi simbolik UNIX (misal: -rwsr-xr-t)"""
        d = 'd' if self.is_directory else '-'
        
        # User
        ur = 'r' if self.mode & FileMode.S_IRUSR else '-'
        uw = 'w' if self.mode & FileMode.S_IWUSR else '-'
        if self.mode & FileMode.S_ISUID:
            ux = 's' if (self.mode & FileMode.S_IXUSR) else 'S'
        else:
            ux = 'x' if (self.mode & FileMode.S_IXUSR) else '-'

        # Group
        gr = 'r' if self.mode & FileMode.S_IRGRP else '-'
        gw = 'w' if self.mode & FileMode.S_IWGRP else '-'
        if self.mode & FileMode.S_ISGID:
            gx = 's' if (self.mode & FileMode.S_IXGRP) else 'S'
        else:
            gx = 'x' if (self.mode & FileMode.S_IXGRP) else '-'

        # Others
        or_ = 'r' if self.mode & FileMode.S_IROTH else '-'
        ow = 'w' if self.mode & FileMode.S_IWOTH else '-'
        if self.mode & FileMode.S_ISVTX:
            ox = 't' if (self.mode & FileMode.S_IXOTH) else 'T'
        else:
            ox = 'x' if (self.mode & FileMode.S_IXOTH) else '-'

        return f"{d}{ur}{uw}{ux}{gr}{gw}{gx}{or_}{ow}{ox}"


class SecurityContext:
    """Kredensial proses runtime (Real UID/GID vs Effective UID/GID)"""
    def __init__(self, ruid: int, rgid: int, groups: List[int]):
        self.ruid = ruid
        self.rgid = rgid
        self.euid = ruid  # Effective UID untuk evaluasi permission kernel
        self.egid = rgid
        self.groups = groups


class KernelPermissionEvaluator:
    """Evaluasi hak akses file berbasis algoritma standard Linux VFS DAC"""
    
    @staticmethod
    def evaluate(inode: Inode, cred: SecurityContext, req_mask: str) -> Tuple[bool, str]:
        # Rule 0: Root bypass (EUID 0) memiliki hak istimewa CAP_DAC_OVERRIDE
        if cred.euid == 0:
            if 'x' in req_mask:
                # Root hanya bisa eksekusi jika setidaknya satu bit executable aktif
                can_exec = bool(inode.mode & 0o111)
                return can_exec, "Root privilege granted (CAP_DAC_OVERRIDE)" if can_exec else "Root exec denied: No exec bit set"
            return True, "Root privilege override (CAP_DAC_OVERRIDE)"

        # Parse requested permissions
        need_r = 'r' in req_mask
        need_w = 'w' in req_mask
        need_x = 'x' in req_mask

        # Rule 1: Jika EUID sama dengan Owner file, HANYA gunakan User Permission
        if cred.euid == inode.owner_uid:
            has_r = bool(inode.mode & FileMode.S_IRUSR)
            has_w = bool(inode.mode & FileMode.S_IWUSR)
            has_x = bool(inode.mode & FileMode.S_IXUSR)
            if (not need_r or has_r) and (not need_w or has_w) and (not need_x or has_x):
                return True, "Access granted via Owner permissions"
            return False, "Access denied: Missing required Owner permission bit"

        # Rule 2: Jika EGID atau Supplementary Group cocok, HANYA gunakan Group Permission
        if cred.egid == inode.owner_gid or inode.owner_gid in cred.groups:
            has_r = bool(inode.mode & FileMode.S_IRGRP)
            has_w = bool(inode.mode & FileMode.S_IWGRP)
            has_x = bool(inode.mode & FileMode.S_IXGRP)
            if (not need_r or has_r) and (not need_w or has_w) and (not need_x or has_x):
                return True, "Access granted via Group membership permissions"
            return False, "Access denied: Missing required Group permission bit"

        # Rule 3: Menggunakan Other Permission
        has_r = bool(inode.mode & FileMode.S_IROTH)
        has_w = bool(inode.mode & FileMode.S_IWOTH)
        has_x = bool(inode.mode & FileMode.S_IXOTH)
        if (not need_r or has_r) and (not need_w or has_w) and (not need_x or has_x):
            return True, "Access granted via Other permissions"
        return False, "Access denied: Others permission insufficient"


# ==============================================================================
# 2. LINUX PAM (Pluggable Authentication Modules) SUBSYSTEM
# ==============================================================================

class PAMControl(Enum):
    REQUIRED = "required"
    REQUISITE = "requisite"
    SUFFICIENT = "sufficient"
    OPTIONAL = "optional"


class PAMStatus(Enum):
    PAM_SUCCESS = auto()
    PAM_AUTH_ERR = auto()
    PAM_MAXTRIES = auto()
    PAM_USER_UNKNOWN = auto()
    PAM_IGNORE = auto()


@dataclass
class PAMUserEntry:
    username: str
    password_hash: str
    failed_attempts: int = 0
    locked: bool = False


class PAMModule:
    """Interface dasar untuk modul-modul PAM"""
    def authenticate(self, user_entry: Optional[PAMUserEntry], **kwargs) -> PAMStatus:
        raise NotImplementedError()


class PamFaillockModule(PAMModule):
    """Simulasi modul pam_faillock (proteksi account lockout akibat brute-force)"""
    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts

    def authenticate(self, user_entry: Optional[PAMUserEntry], **kwargs) -> PAMStatus:
        if not user_entry:
            return PAMStatus.PAM_USER_UNKNOWN
        if user_entry.locked:
            return PAMStatus.PAM_MAXTRIES
        return PAMStatus.PAM_SUCCESS


class PamUnixModule(PAMModule):
    """Simulasi modul pam_unix (validasi password shadow menggunakan hashing SHA-256)"""
    @staticmethod
    def hash_password(password: str, salt: str = "linux_security_salt") -> str:
        return hashlib.sha256((salt + password).encode()).hexdigest()

    def authenticate(self, user_entry: Optional[PAMUserEntry], **kwargs) -> PAMStatus:
        if not user_entry:
            return PAMStatus.PAM_USER_UNKNOWN
        provided_password = kwargs.get("password", "")
        if self.hash_password(provided_password) == user_entry.password_hash:
            user_entry.failed_attempts = 0
            return PAMStatus.PAM_SUCCESS
        else:
            user_entry.failed_attempts += 1
            if user_entry.failed_attempts >= 3:
                user_entry.locked = True
            return PAMStatus.PAM_AUTH_ERR


@dataclass
class PAMRule:
    control: PAMControl
    module: PAMModule
    module_name: str


class PAMStackEngine:
    """
    Engine Evaluasi PAM Stack:
    - required:   Gagal -> Catat kegagalan, teruskan evaluasi modul berikutnya.
    - requisite:  Gagal -> Catat kegagalan, langsung TERMINASI stack auth.
    - sufficient: Berhasil -> Jika tidak ada modul 'required' sebelumnya yang gagal, TERMINASI & SUKSES.
    - optional:   Hanya mempengaruhi hasil jika tidak ada modul lain yang menentukan.
    """
    def __init__(self):
        self.rules: List[PAMRule] = []

    def add_rule(self, control: PAMControl, module: PAMModule, module_name: str):
        self.rules.append(PAMRule(control, module, module_name))

    def authenticate(self, user_entry: Optional[PAMUserEntry], password: str) -> Tuple[bool, List[str]]:
        audit_trail = []
        overall_status = True
        required_failure = False

        for rule in self.rules:
            res = rule.module.authenticate(user_entry, password=password)
            audit_trail.append(f"Modul: {rule.module_name:<15} | Flag: {rule.control.value:<10} | Hasil: {res.name}")

            if rule.control == PAMControl.REQUISITE:
                if res != PAMStatus.PAM_SUCCESS:
                    audit_trail.append(f"-> REQUISITE FAIL: Abort stack langsung.")
                    return False, audit_trail

            elif rule.control == PAMControl.REQUIRED:
                if res != PAMStatus.PAM_SUCCESS:
                    required_failure = True
                    overall_status = False

            elif rule.control == PAMControl.SUFFICIENT:
                if res == PAMStatus.PAM_SUCCESS and not required_failure:
                    audit_trail.append(f"-> SUFFICIENT PASS: Auth stack sukses secara dini.")
                    return True, audit_trail

            elif rule.control == PAMControl.OPTIONAL:
                pass

        if required_failure or not overall_status:
            return False, audit_trail
        return True, audit_trail


# ==============================================================================
# 3. SYSTEM SECURITY HARDENING AUDITOR
# ==============================================================================

class HardeningAuditor:
    """Mendeteksi perizinan longgar dan celah eskalasi hak akses (Privilege Escalation)"""
    
    @staticmethod
    def audit_filesystem(fs: List[Inode]) -> List[Tuple[str, str, str]]:
        findings = []
        for inode in fs:
            # Audit 1: File rahasia dapat dibaca oleh others
            if inode.path in ["/etc/shadow", "/etc/gshadow"]:
                if inode.mode & (FileMode.S_IROTH | FileMode.S_IWOTH | FileMode.S_IRGRP):
                    findings.append(("CRITICAL", inode.path, f"Permissions {oct(inode.mode)} terlalu longgar! Seharusnya 0o600 atau 0o640 root:shadow."))

            # Audit 2: SUID bit aktif pada binary yang tidak lazim
            if not inode.is_directory and (inode.mode & FileMode.S_ISUID):
                if inode.owner_uid == 0:
                    findings.append(("WARNING", inode.path, f"SUID Root aktif ({inode.mode_string()}). Potensial privilege escalation jika binary dieksploitasi."))

            # Audit 3: Directory /tmp tanpa Sticky Bit
            if inode.is_directory and inode.path == "/tmp":
                if not (inode.mode & FileMode.S_ISVTX):
                    findings.append(("HIGH", inode.path, "Direktori shared /tmp tidak memiliki Sticky Bit (+t)! User dapat menghapus file user lain."))

            # Audit 4: File writable oleh World/Others
            if inode.mode & FileMode.S_IWOTH:
                findings.append(("HIGH", inode.path, f"World-writable file detected ({inode.mode_string()}). Siapapun dapat memodifikasi konten."))

        return findings


# ==============================================================================
# MAIN SIMULATION RUNNER
# ==============================================================================

def main():
    print(f"{CLR_BOLD}{CLR_WHITE}SIMULATOR SISTEM OPERASI: TATA KELOLA IZIN, PAM, & SECURITY HARDENING{CLR_RESET}")
    print(f"Target: Linux Kernel Virtual File System (VFS) & Linux-PAM Subsystem\n")

    # -------------------------------------------------------------------------
    # DEMO 1: DAC Kernel Permission Check Simulation
    # -------------------------------------------------------------------------
    print_section("1. SIMULASI KERNEL DAC EVALUATION (VFS)")
    
    test_files = [
        Inode("/var/log/secure", owner_uid=0, owner_gid=0, mode=0o600),
        Inode("/usr/bin/passwd", owner_uid=0, owner_gid=0, mode=0o4755),
        Inode("/shared/project", owner_uid=1001, owner_gid=2000, mode=0o770, is_directory=True),
    ]
    
    # User dev (UID 1002, GID 2000 - masuk dalam group project)
    cred_dev = SecurityContext(ruid=1002, rgid=2000, groups=[2000])
    # User attacker (UID 1003, GID 1003 - group asing)
    cred_attacker = SecurityContext(ruid=1003, rgid=1003, groups=[1003])
    # User root
    cred_root = SecurityContext(ruid=0, rgid=0, groups=[0])

    for f in test_files:
        print(f"\n{CLR_BOLD}Evaluasi Node: {f.path} [{f.mode_string()} / {oct(f.mode)}]{CLR_RESET}")
        
        # Test Case 1: Dev group member
        allowed, reason = KernelPermissionEvaluator.evaluate(f, cred_dev, "r")
        print_status(f"Dev Read ({cred_dev.ruid}:{cred_dev.rgid})", f"{reason}", allowed)

        # Test Case 2: Attacker
        allowed, reason = KernelPermissionEvaluator.evaluate(f, cred_attacker, "w")
        print_status(f"Attacker Write", f"{reason}", allowed)

        # Test Case 3: Root override
        allowed, reason = KernelPermissionEvaluator.evaluate(f, cred_root, "r")
        print_status(f"Root Read", f"{reason}", allowed)

    # -------------------------------------------------------------------------
    # DEMO 2: PAM Stack Logic Execution
    # -------------------------------------------------------------------------
    print_section("2. SIMULASI EVALUASI STACK LINUX-PAM")
    
    # Setup Database User Mock
    hashed_pwd = PamUnixModule.hash_password("SuperSecure123!")
    user_db = {
        "alice": PAMUserEntry("alice", hashed_pwd)
    }

    # Setup PAM Configuration:
    # auth  requisite  pam_faillock.so
    # auth  sufficient pam_unix.so
    pam = PAMStackEngine()
    pam.add_rule(PAMControl.REQUISITE, PamFaillockModule(max_attempts=3), "pam_faillock.so")
    pam.add_rule(PAMControl.SUFFICIENT, PamUnixModule(), "pam_unix.so")

    print(f"{CLR_BOLD}Mencoba autentikasi user 'alice':{CLR_RESET}")
    
    # 1. Login Sukses
    print(f"\n{CLR_YELLOW}Scenario 1: Password Valid{CLR_RESET}")
    success, trail = pam.authenticate(user_db["alice"], "SuperSecure123!")
    for step in trail:
        print(f"  [PAM TRACE] {step}")
    print_status("Hasil Auth", "Autentikasi Diterima", success)

    # 2. Simulasi Brute-Force (3x Gagal)
    print(f"\n{CLR_YELLOW}Scenario 2: Simulasi Brute Force Password (pam_faillock trigger){CLR_RESET}")
    for i in range(1, 4):
        print(f"Percobaan ke-{i} (Salah Password):")
        success, trail = pam.authenticate(user_db["alice"], "WrongPass")
        print_status("Hasil Auth", f"Status: {'Berhasil' if success else 'Gagal'} (Failed Counter: {user_db['alice'].failed_attempts})", success)

    # 3. Percobaan ke-4 dengan Password Benar saat akun sudah terkunci
    print(f"\n{CLR_YELLOW}Scenario 3: Input Password Benar Saat Akun Locked{CLR_RESET}")
    success, trail = pam.authenticate(user_db["alice"], "SuperSecure123!")
    for step in trail:
        print(f"  [PAM TRACE] {step}")
    print_status("Hasil Auth", f"Status: {'Berhasil' if success else 'Ditolak (Akun Terkunci oleh Faillock)'}", success)

    # -------------------------------------------------------------------------
    # DEMO 3: Linux Security Hardening Audit
    # -------------------------------------------------------------------------
    print_section("3. AUDIT INSPEKSI HARDENING DAN HAK AKSES SISTEM")
    
    mock_system_files = [
        Inode("/etc/shadow", owner_uid=0, owner_gid=0, mode=0o644),       # Flaw: Readable by world
        Inode("/tmp", owner_uid=0, owner_gid=0, mode=0o777, is_directory=True), # Flaw: Missing Sticky Bit
        Inode("/usr/bin/nmap", owner_uid=0, owner_gid=0, mode=0o4755),    # Flaw: Dangerous SUID binary
        Inode("/home/developer/app.sh", owner_uid=1000, owner_gid=1000, mode=0o777), # Flaw: World writable
        Inode("/etc/passwd", owner_uid=0, owner_gid=0, mode=0o644),       # Safe
        Inode("/tmp_secure", owner_uid=0, owner_gid=0, mode=0o1777, is_directory=True) # Safe: Sticky Bit present
    ]

    findings = HardeningAuditor.audit_filesystem(mock_system_files)
    
    for level, path, issue in findings:
        color = CLR_RED if level == "CRITICAL" else CLR_YELLOW
        print(f"  {color}[{level:<8}]{CLR_RESET} File: {CLR_BOLD}{path:<24}{CLR_RESET} -> {issue}")

    print(f"\n{CLR_BOLD}{CLR_GREEN}[+] Simulasi Selesai: Seluruh modul keamanan berhasil dieksekusi.{CLR_RESET}")

if __name__ == "__main__":
    main()