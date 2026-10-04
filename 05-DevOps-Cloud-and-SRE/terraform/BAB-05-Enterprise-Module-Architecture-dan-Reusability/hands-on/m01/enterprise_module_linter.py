#!/usr/bin/env python3
"""
Enterprise Terraform Module Linter & Architectural Validator.
Author: Principal Cloud & SRE Curriculum Architect
Language: Python 3.8+

Skrip ini melakukan validasi kepatuhan statik pada arsitektur modul Terraform:
1. Memastikan file esensial tersedia (main.tf, variables.tf, outputs.tf, versions.tf, README.md).
2. Memverifikasi child module tidak meng-hardcode blok 'provider' dengan kredensial atau 'backend'.
3. Memastikan semua 'variable' memiliki deskripsi dan blok 'validation' (khusus variabel tanpa default).
4. Memastikan semua 'output' memiliki deskripsi dan menandai data sensitif jika mengandung kata kunci tertentu.
5. Memverifikasi batasan versi 'required_version' dan 'required_providers' pada versions.tf.
"""

import os
import sys
import re
from pathlib import Path

REQUIRED_FILES = [
    "main.tf",
    "variables.tf",
    "outputs.tf",
    "versions.tf",
    "README.md"
]

SENSITIVE_KEYWORDS = ["password", "secret", "token", "credential", "private_key", "conn_str"]

class ModuleLintError:
    def __init__(self, file_path, line_number, rule_id, message):
        self.file_path = file_path
        self.line_number = line_number
        self.rule_id = rule_id
        self.message = message

    def __str__(self):
        location = f"{self.file_path}:{self.line_number}" if self.line_number else self.file_path
        return f"[{self.rule_id}] at {location} -> {self.message}"

class EnterpriseModuleLinter:
    def __init__(self, module_dir: str):
        self.module_dir = Path(module_dir)
        self.errors = []
        self.warnings = []

    def log_error(self, file_path, line_number, rule_id, message):
        self.errors.append(ModuleLintError(file_path, line_number, rule_id, message))

    def log_warning(self, file_path, line_number, rule_id, message):
        self.warnings.append(ModuleLintError(file_path, line_number, rule_id, message))

    def check_file_structure(self):
        """Memeriksa keberadaan file standar enterprise."""
        for filename in REQUIRED_FILES:
            target = self.module_dir / filename
            if not target.exists():
                self.log_error(str(target), 0, "ENT-MOD-01", f"File wajib tidak ditemukan: {filename}")

    def check_versions_tf(self):
        """Memeriksa versions.tf untuk required_version dan required_providers."""
        versions_file = self.module_dir / "versions.tf"
        if not versions_file.exists():
            return

        content = versions_file.read_text(encoding="utf-8")
        
        if "required_version" not in content:
            self.log_error("versions.tf", 1, "ENT-MOD-02", "versions.tf wajib mendefinisikan 'required_version'.")
        
        if "required_providers" not in content:
            self.log_error("versions.tf", 1, "ENT-MOD-03", "versions.tf wajib mendefinisikan blok 'required_providers'.")

    def check_forbidden_blocks(self):
        """Child module dilarang memiliki blok provider terkonfigurasi dan blok backend."""
        tf_files = list(self.module_dir.glob("*.tf"))
        
        provider_block_regex = re.compile(r'^\s*provider\s+"[^"]+"\s*\{', re.MULTILINE)
        backend_block_regex = re.compile(r'^\s*backend\s+"[^"]+"\s*\{', re.MULTILINE)

        for tf_file in tf_files:
            content = tf_file.read_text(encoding="utf-8")
            
            for match in provider_block_regex.finditer(content):
                line_no = content[:match.start()].count("\n") + 1
                self.log_error(tf_file.name, line_no, "ENT-MOD-04", 
                               "Child module dilarang mengonfigurasi blok 'provider'. Gunakan 'required_providers' di versions.tf.")

            for match in backend_block_regex.finditer(content):
                line_no = content[:match.start()].count("\n") + 1
                self.log_error(tf_file.name, line_no, "ENT-MOD-05", 
                               "Child module dilarang mengonfigurasi blok 'backend'. Backend hanya boleh di Root Module.")

    def check_variables(self):
        """Memeriksa kelengkapan dokumentasi dan validasi variabel."""
        var_file = self.module_dir / "variables.tf"
        if not var_file.exists():
            return

        content = var_file.read_text(encoding="utf-8")
        # Ekstrak setiap blok variable
        var_pattern = re.compile(r'variable\s+"([^"]+)"\s*\{([^}]+(?:\{[^}]*\}[^}]+)*)\}', re.MULTILINE | re.DOTALL)

        for match in var_pattern.finditer(content):
            var_name = match.group(1)
            body = match.group(2)
            line_no = content[:match.start()].count("\n") + 1

            if "description" not in body:
                self.log_error("variables.tf", line_no, "ENT-MOD-06", 
                               f"Variabel '{var_name}' tidak memiliki atribut 'description'.")

            has_default = "default" in body
            has_validation = "validation" in body

            if not has_default and not has_validation:
                self.log_warning("variables.tf", line_no, "ENT-MOD-07", 
                                 f"Variabel mandatory '{var_name}' tidak memiliki blok 'validation'. Disarankan menerapkan input validation.")

    def check_outputs(self):
        """Memeriksa kelengkapan deskripsi dan proteksi sensitive output."""
        output_file = self.module_dir / "outputs.tf"
        if not output_file.exists():
            return

        content = output_file.read_text(encoding="utf-8")
        out_pattern = re.compile(r'output\s+"([^"]+)"\s*\{([^}]+(?:\{[^}]*\}[^}]+)*)\}', re.MULTILINE | re.DOTALL)

        for match in out_pattern.finditer(content):
            out_name = match.group(1)
            body = match.group(2)
            line_no = content[:match.start()].count("\n") + 1

            if "description" not in body:
                self.log_error("outputs.tf", line_no, "ENT-MOD-08", 
                               f"Output '{out_name}' wajib memiliki atribut 'description'.")

            # Deteksi potensi kebocoran data sensitif
            contains_sensitive_keyword = any(k in out_name.lower() for k in SENSITIVE_KEYWORDS)
            is_marked_sensitive = "sensitive" in body and "true" in body

            if contains_sensitive_keyword and not is_marked_sensitive:
                self.log_error("outputs.tf", line_no, "ENT-MOD-09", 
                               f"Output '{out_name}' berpotensi membawa data rahasia tetapi belum diset 'sensitive = true'.")

    def run_all_checks(self) -> bool:
        print(f"[*] Menjalankan Enterprise Module Linter pada: {self.module_dir.resolve()}...")
        self.check_file_structure()
        self.check_versions_tf()
        self.check_forbidden_blocks()
        self.check_variables()
        self.check_outputs()

        print("\n" + "="*70)
        print("HASIL PEMERIKSAAN KEPATUHAN ARSITEKTUR MODUL:")
        print("="*70)

        if self.warnings:
            print(f"\n[!] DITEMUKAN {len(self.warnings)} WARNING:")
            for w in self.warnings:
                print(f"  {w}")

        if self.errors:
            print(f"\n[X] DITEMUKAN {len(self.errors)} FATAL ERROR:")
            for e in self.errors:
                print(f"  {e}")
            print("\nKesimpulan: GAGAL (Modul belum memenuhi standar enterprise).\n")
            return False
        else:
            print("\n[OK] SELURUH PEMERIKSAAN LULUS (Modul memenuhi standar arsitektur enterprise).\n")
            return True

def main():
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    linter = EnterpriseModuleLinter(target_dir)
    success = linter.run_all_checks()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()