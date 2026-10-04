#!/usr/bin/env python3
"""
Lab Hands-on: Kotlin Interoperabilitas Java & JVM Internals (Deep Dive)
Bab: 08 - Modul 02

Script ini mensimulasikan mekanisme internal compiler Kotlin (kotlinc) dan runtime JVM:
1. Synthetic Default Methods & Bitmask Parameter Resolution (@JvmOverloads).
2. Name Mangling pada Inline Value Classes & Internal Modifiers.
3. Companion Object Dispatch vs @JvmStatic Direct Invocations.
4. Runtime Null-Safety Metadata & Intrinsics Enforcement (checkNotNullParameter).
5. Benchmark Kinerja: Primitive Unboxed vs Boxed Types (Simulasi JVM GC & Overhead).
"""

import sys
import time
import struct
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


# --- ANSI Terminal Formatting ---
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


# --- JVM Internal Bytecode Models ---
@dataclass
class BytecodeInstruction:
    opcode: str
    operand: Any = None
    comment: str = ""

    def __str__(self) -> str:
        op = f"{self.opcode:<22} {str(self.operand or ''):<20}"
        return f"    {op} {Colors.DIM}// {self.comment}{Colors.RESET}"


@dataclass
class JVMClassMethod:
    name: str
    descriptor: str
    access_flags: List[str]
    instructions: List[BytecodeInstruction] = field(default_factory=list)


# ==============================================================================
# 1. SIMULASI KOTLINC COMPILER INTERNALS
# ==============================================================================
class KotlinCompilerSimulator:
    """
    Mensimulasikan transformasi AST Kotlin ke struktur Classfile JVM Bytecode.
    """

    @staticmethod
    def mangle_inline_class_method(method_name: str, inline_type: str) -> str:
        """
        Kotlin Inline Value Class mengalami name mangling untuk mencegah bentrokan
        signature di level JVM dan membatasi pemanggilan langsung dari Java.
        Format: <nama_method>-<hash(tipe)>
        """
        type_hash = hashlib.sha256(inline_type.encode()).hexdigest()[:7]
        return f"{method_name}-{type_hash}"

    @staticmethod
    def mangle_internal_member(member_name: str, module_name: str) -> str:
        """
        Modifier 'internal' Kotlin diterjemahkan menjadi 'public' di JVM,
        tetapi namanya di-mangle dengan format: <nama>$<module_name>
        """
        sanitized_mod = module_name.replace(".", "_").replace("-", "_")
        return f"{member_name}${sanitized_mod}"

    @staticmethod
    def generate_synthetic_default_bridge(
        func_name: str,
        params: List[Tuple[str, str, Any]],  # [(name, type, default_val)]
    ) -> JVMClassMethod:
        """
        Kotlin menghasilkan method sintetis static tambahan untuk default arguments:
        <name>$default(Target, Param1, ..., ParamN, int bitmask, Object defaultMarker)
        """
        desc = "(" + "".join([p[1] for p in params]) + "ILjava/lang/Object;)V"
        method = JVMClassMethod(
            name=f"{func_name}$default",
            descriptor=desc,
            access_flags=["ACC_PUBLIC", "ACC_STATIC", "ACC_SYNTHETIC"],
        )

        # Emit simulasi instruksi bitmask resolution
        for idx, (p_name, _, default_val) in enumerate(params):
            if default_val is not None:
                mask_val = 1 << idx
                method.instructions.append(
                    BytecodeInstruction("ILOAD", f"mask_{idx}", f"Load bitmask integer")
                )
                method.instructions.append(
                    BytecodeInstruction("ICONST", mask_val, f"Bitmask check 0x{mask_val:02X}")
                )
                method.instructions.append(
                    BytecodeInstruction("IAND", None, "Periksa apakah bit diset (default digunakan)")
                )
                method.instructions.append(
                    BytecodeInstruction("IFEQ", f"SKIP_DEFAULT_{idx}", f"Jika 0, gunakan argumen pemanggil")
                )
                method.instructions.append(
                    BytecodeInstruction("LDC", default_val, f"Default: {p_name} = {default_val}")
                )
                method.instructions.append(
                    BytecodeInstruction("ASTORE/ISTORE", p_name, f"Setel variabel lokal {p_name}")
                )

        method.instructions.append(
            BytecodeInstruction("INVOKESTATIC", f"{func_name}", "Panggil method target asli")
        )
        return method


# ==============================================================================
# 2. RUNTIME INTRINSICS & COMPANION CALL ENGINE
# ==============================================================================
class KotlinJVMRuntime:
    """
    Mensimulasikan eksekusi runtime JVM dan penegakan kotlin.jvm.internal.Intrinsics
    """

    @staticmethod
    def check_not_null_parameter(value: Any, param_name: str, method_name: str):
        """
        Simulasi Intrinsics.checkNotNullParameter(value, paramName)
        Kotlin menginjeksi ini di awal method publik untuk menjamin batas interop Java.
        """
        if value is None:
            raise NullPointerException(
                f"Parameter specified as non-null is null: "
                f"method {method_name}, parameter {param_name}"
            )

    @classmethod
    def invoke_with_defaults(
        cls,
        target_fn,
        defaults_info: List[Tuple[str, Any]],
        args: List[Any],
        mask: int,
    ) -> Dict[str, Any]:
        """
        Mengeksekusi method dengan resolusi bitmask persis seperti JVM bytecode Kotlin.
        """
        resolved_args = {}
        for idx, (name, def_val) in enumerate(defaults_info):
            # Jika bit ke-idx bernilai 1, gunakan default value
            if (mask & (1 << idx)) != 0:
                resolved_args[name] = def_val
            else:
                arg_index = idx
                if arg_index < len(args) and args[arg_index] is not None:
                    resolved_args[name] = args[arg_index]
                else:
                    resolved_args[name] = def_val

        return target_fn(**resolved_args)


class NullPointerException(Exception):
    pass


# ==============================================================================
# 3. DOMAIN LOGIC: INTEROP DEMONSTRATIONS
# ==============================================================================
class ServiceConfiguration:
    """
    Kelas simulasi yang merefleksikan hasil kompilasi kelas Kotlin ke JVM.
    """

    # Companion Object Instance (Singleton pattern di JVM)
    class Companion:
        def __init__(self):
            self.INSTANCE_NAME = "DatabaseConnection"

        def get_timeout(self) -> int:
            return 3000

    CompanionInstance = Companion()

    @staticmethod
    def get_timeout_jvm_static() -> int:
        """Hasil transformasi anotasi @JvmStatic: dapat dipanggil tanpa INSTANCE"""
        return 3000

    @classmethod
    def connect_target(cls, host: str, port: int, timeout: int, secure: bool) -> str:
        # Kotlin Intrinsics null guard
        KotlinJVMRuntime.check_not_null_parameter(host, "host", "connect")
        protocol = "https" if secure else "http"
        return f"{protocol}://{host}:{port} (Timeout: {timeout}ms)"


# ==============================================================================
# 4. BENCHMARKING ENGINE: BOXED VS UNBOXED PRIMITIVES
# ==============================================================================
def benchmark_primitive_unboxing():
    """
    Mendemonstrasikan perbedaan performa antara Int murni (primitive int)
    dan Boxed Int? (java.lang.Integer) yang sering terjadi secara implisit
    saat interop generic atau nullable type di Kotlin.
    """
    iterations = 2_000_000

    # 1. Unboxed Primitive Loop (Simulasi JVM primitive register)
    start_time = time.perf_counter()
    primitive_sum = 0
    for i in range(iterations):
        primitive_sum += i
    primitive_duration = time.perf_counter() - start_time

    # 2. Boxed Reference Loop (Simulasi JVM Integer object instantiation & pointer dereference)
    start_time = time.perf_counter()
    boxed_sum = 0
    # struct.pack & unpack digunakan untuk mensimulasikan overhead memori & alokasi objek boxed
    for i in range(iterations):
        boxed_val = struct.pack("i", i)  # Alokasi simulasi java.lang.Integer(i)
        unboxed_val = struct.unpack("i", boxed_val)[0]  # Unboxing .intValue()
        boxed_sum += unboxed_val
    boxed_duration = time.perf_counter() - start_time

    return primitive_duration, boxed_duration, primitive_sum == boxed_sum


# ==============================================================================
# MAIN EXECUTION ROUTINE
# ==============================================================================
def print_section(title: str):
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== {title} ==={Colors.RESET}")


def main():
    print(f"{Colors.BOLD}{Colors.CYAN}")
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║   KOTLIN INTEROP & JVM INTERNALS: DEEP-DIVE RUNTIME SIMULATOR    ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}")

    # --- BAGIAN 1: NAME MANGLING ---
    print_section("1. NAME MANGLING (Value Classes & Internal Modifier)")

    inline_class_type = "com.techcorp.model.UserId"
    original_func = "authenticate"
    mangled_func = KotlinCompilerSimulator.mangle_inline_class_method(
        original_func, inline_class_type
    )

    internal_func = "calculateSecurityHash"
    module_name = "network-core"
    mangled_internal = KotlinCompilerSimulator.mangle_internal_member(
        internal_func, module_name
    )

    print(f"{Colors.YELLOW}[Kotlin Source]{Colors.RESET}")
    print(f"  @JvmInline value class UserId(val id: String)")
    print(f"  fun {original_func}(userId: UserId) {{ ... }}")
    print(f"  internal fun {internal_func}() {{ ... }}")

    print(f"\n{Colors.GREEN}[JVM Bytecode Output]{Colors.RESET}")
    print(f"  Mangling Value Class -> {Colors.BOLD}{mangled_func}{Colors.RESET}")
    print(f"  Mangling Internal    -> {Colors.BOLD}{mangled_internal}{Colors.RESET}")
    print(
        f"  {Colors.DIM}Tujuan: Mencegah collision overload dan memblokir Java dari memanggil method internal.{Colors.RESET}"
    )

    # --- BAGIAN 2: SYNTHETIC OVERLOADS & BITMASK ---
    print_section("2. SYNTHETIC OVERLOADS & DEFAULT MASK RESOLUTION (@JvmOverloads)")

    params_definition = [
        ("host", "Ljava/lang/String;", None),
        ("port", "I", 8080),
        ("timeout", "I", 3000),
        ("secure", "Z", True),
    ]

    synthetic_method = KotlinCompilerSimulator.generate_synthetic_default_bridge(
        "connect", params_definition
    )

    print(f"Signature Sintetis: {Colors.CYAN}{synthetic_method.name}{synthetic_method.descriptor}{Colors.RESET}")
    print(f"Access Flags      : {Colors.CYAN}{', '.join(synthetic_method.access_flags)}{Colors.RESET}")
    print(f"Disassembled Bytecode:")
    for instr in synthetic_method.instructions:
        print(instr)

    # Uji coba simulasi pemanggilan dari Java
    print(f"\n{Colors.YELLOW}[Simulasi Pemanggilan Interop dari Java/Caller]{Colors.RESET}")
    defaults_data = [
        ("host", None),
        ("port", 8080),
        ("timeout", 3000),
        ("secure", True),
    ]

    # Kasus: Caller Java hanya mengisi (host="api.domain.io"), bitmask = 0b1110 (14)
    # Bit 0 (host) = 0 (manual), Bit 1 (port) = 1 (default), Bit 2 (timeout) = 1, Bit 3 (secure) = 1
    mask_java_call = (1 << 1) | (1 << 2) | (1 << 3)
    result = KotlinJVMRuntime.invoke_with_defaults(
        ServiceConfiguration.connect_target,
        defaults_data,
        args=["api.domain.io"],
        mask=mask_java_call,
    )
    print(f"  Java: Service.connect(\"api.domain.io\");")
    print(f"  -> Eksekusi Bytecode dengan Mask: 0b{mask_java_call:04b} (Bitmask Dec: {mask_java_call})")
    print(f"  -> Result: {Colors.GREEN}{result}{Colors.RESET}")

    # --- BAGIAN 3: NULL-SAFETY CHECK VIA INTRINSICS ---
    print_section("3. NULLABILITY BRIDGING & INTRINSICS RUNTIME CHECK")
    print(f"{Colors.YELLOW}[Java memanggil Kotlin non-nullable dengan parameter null]{Colors.RESET}")

    try:
        # Simulasi Java menerobos null-check Kotlin via unsafe interoperability
        print("  Java: Service.connect(null, 8080, 3000, true);")
        ServiceConfiguration.connect_target(None, 8080, 3000, True)
    except NullPointerException as npe:
        print(f"  {Colors.RED}Pengecualian JVM Terlempar: {npe}{Colors.RESET}")
        print(
            f"  {Colors.DIM}Berasal dari: Intrinsics.checkNotNullParameter(...) yang disuntikkan compiler.{Colors.RESET}"
        )

    # --- BAGIAN 4: COMPANION DISPATCH VS @JvmStatic ---
    print_section("4. COMPANION OBJECT INVOCATION VS @JvmStatic")
    print(f"Pemanggilan Standar (Tanpa @JvmStatic):")
    print(f"  Java Bytecode : {Colors.CYAN}GETSTATIC ServiceConfiguration.Companion : LCompanion;{Colors.RESET}")
    print(f"                  {Colors.CYAN}INVOKEVIRTUAL Companion.get_timeout ()I{Colors.RESET}")
    val_comp = ServiceConfiguration.CompanionInstance.get_timeout()
    print(f"  Output Value  : {val_comp} ms")

    print(f"\nDengan Anotasi @JvmStatic:")
    print(f"  Java Bytecode : {Colors.GREEN}INVOKESTATIC ServiceConfiguration.get_timeout_jvm_static ()I{Colors.RESET}")
    val_static = ServiceConfiguration.get_timeout_jvm_static()
    print(f"  Output Value  : {val_static} ms (Bypass singleton instance lookup overhead)")

    # --- BAGIAN 5: BENCHMARK PRIMITIVE VS BOXED ---
    print_section("5. BENCHMARK: PRIMITIVE UNBOXED (Int) VS BOXED (Int? / java.lang.Integer)")
    print(f"Menjalankan 2,000,000 iterasi kalkulasi aritmatika...")

    prim_time, boxed_time, valid = benchmark_primitive_unboxing()
    overhead_ratio = boxed_time / prim_time if prim_time > 0 else 0

    print(f"  Hasil Validasi Algoritma  : {'VALID' if valid else 'INVALID'}")
    print(f"  Waktu Primitive `Int`     : {Colors.GREEN}{prim_time:.4f} detik{Colors.RESET}")
    print(f"  Waktu Boxed `Int?`        : {Colors.RED}{boxed_time:.4f} detik{Colors.RESET}")
    print(f"  Rasio Penalti Overhead    : {Colors.BOLD}{Colors.YELLOW}{overhead_ratio:.2f}x lebih lambat{Colors.RESET}")
    print(
        f"  {Colors.DIM}Implikasi: Gunakan generic/nullable type secara bijak dalam hot-paths.{Colors.RESET}"
    )

    print(f"\n{Colors.BOLD}{Colors.GREEN}>>> Simulasi JVM Internals & Interoperabilitas Selesai dengan Sukses. <<<{Colors.RESET}\n")


if __name__ == "__main__":
    main()