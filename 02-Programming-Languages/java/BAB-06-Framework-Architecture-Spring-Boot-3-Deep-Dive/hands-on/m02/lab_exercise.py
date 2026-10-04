#!/usr/bin/env python3
"""
Lab Hands-on: Spring Boot 3 Framework Architecture Deep Dive
Simulasi Inti: Inversion of Control (IoC), Conditional Auto-Configuration,
Bean Post-Processor, dan Aspect-Oriented Programming (AOP) Dynamic Proxy.
"""

import inspect
import functools
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Type

# ==============================================================================
# ANSI Color Formatting Utility
# ==============================================================================
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"

def log_info(module: str, msg: str):
    print(f"{TermColor.GRAY}[{time.strftime('%H:%M:%S')}] {TermColor.GREEN}[{module.upper():<14}] {TermColor.RESET}{msg}")

def log_aop(msg: str):
    print(f"{TermColor.GRAY}[{time.strftime('%H:%M:%S')}] {TermColor.MAGENTA}[AOP-PROXY     ] {TermColor.RESET}{msg}")

def log_warn(module: str, msg: str):
    print(f"{TermColor.GRAY}[{time.strftime('%H:%M:%S')}] {TermColor.YELLOW}[{module.upper():<14}] {TermColor.BOLD}{msg}{TermColor.RESET}")

def log_err(module: str, msg: str):
    print(f"{TermColor.GRAY}[{time.strftime('%H:%M:%S')}] {TermColor.RED}[{module.upper():<14}] {TermColor.BOLD}{msg}{TermColor.RESET}")

# ==============================================================================
# Decorators: Metadata Spring Annotations Simulator
# ==============================================================================
def Component(cls=None, *, name: Optional[str] = None):
    """Menandai class sebagai Spring-managed Bean (@Component, @Service, @Repository)."""
    def decorator(target_cls):
        target_cls.__spring_component__ = True
        target_cls.__bean_name__ = name or target_cls.__name__[:1].lower() + target_cls.__name__[1:]
        return target_cls
    return decorator(cls) if cls is not None else decorator

def Service(cls=None, *, name: Optional[str] = None):
    return Component(cls, name=name)

def Repository(cls=None, *, name: Optional[str] = None):
    return Component(cls, name=name)

def Transactional(propagation: str = "REQUIRED", read_only: bool = False):
    """Menandai method untuk diintersep oleh AOP TransactionInterceptor."""
    def decorator(fn: Callable):
        fn.__transactional__ = True
        fn.__tx_meta__ = {"propagation": propagation, "read_only": read_only}
        return fn
    return decorator

def ConditionalOnMissingBean(target_type: Type):
    """Simulasi Spring Boot Conditional Evaluation: @ConditionalOnMissingBean."""
    def decorator(fn: Callable):
        fn.__conditional_missing__ = target_type
        return fn
    return decorator

# ==============================================================================
# AOP Proxy: Dynamic Interceptor Engine
# ==============================================================================
class TransactionManager:
    """Simulasi PlatformTransactionManager Spring Boot 3."""
    @staticmethod
    def begin(tx_id: str, read_only: bool):
        mode = "READ-ONLY" if read_only else "READ-WRITE"
        log_aop(f"{TermColor.CYAN}--> BEGIN Transaction [{tx_id}] (Isolation=READ_COMMITTED, Mode={mode}){TermColor.RESET}")

    @staticmethod
    def commit(tx_id: str):
        log_aop(f"{TermColor.GREEN}--> COMMIT Transaction [{tx_id}] (Persisting state changes){TermColor.RESET}")

    @staticmethod
    def rollback(tx_id: str, exc: Exception):
        log_aop(f"{TermColor.RED}--> ROLLBACK Transaction [{tx_id}] due to {type(exc).__name__}: {exc}{TermColor.RESET}")

class AopProxyWrapper:
    """Dynamic Proxy Simulator (menyerupai CGLIB/JDK Dynamic Proxy)."""
    def __init__(self, target_instance: Any):
        self._target = target_instance
        self._tx_manager = TransactionManager()

    def __getattr__(self, name: str):
        target_attr = getattr(self._target, name)
        if not callable(target_attr):
            return target_attr

        is_tx = getattr(target_attr, "__transactional__", False)
        if not is_tx:
            return target_attr

        tx_meta = getattr(target_attr, "__tx_meta__", {})

        @functools.wraps(target_attr)
        def intercepted(*args, **kwargs):
            tx_id = f"tx-{int(time.time() * 1000) % 100000}"
            self._tx_manager.begin(tx_id, tx_meta.get("read_only", False))
            start_ns = time.perf_counter_ns()
            try:
                result = target_attr(*args, **kwargs)
                elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
                self._tx_manager.commit(tx_id)
                log_aop(f"{TermColor.GRAY}Invocation '{name}' completed in {elapsed_ms:.2f}ms{TermColor.RESET}")
                return result
            except Exception as e:
                self._tx_manager.rollback(tx_id, e)
                raise e

        return intercepted

# ==============================================================================
# Core Engine: ApplicationContext & Auto-Configuration Pipeline
# ==============================================================================
class SpringApplicationContext:
    """Implementasi ringkas ApplicationContext & BeanFactory."""
    def __init__(self):
        self._singleton_registry: Dict[str, Any] = {}
        self._bean_definitions: Dict[str, Type] = {}
        self._auto_config_factories: List[Callable] = []

    def register_component(self, cls: Type):
        """Registrasi class blueprint ke dalam container."""
        bean_name = getattr(cls, "__bean_name__", cls.__name__[:1].lower() + cls.__name__[1:])
        self._bean_definitions[bean_name] = cls
        log_info("BeanFactory", f"Registered BeanDefinition: '{TermColor.CYAN}{bean_name}{TermColor.RESET}' [{cls.__name__}]")

    def register_auto_configuration(self, factory_fn: Callable):
        """Registrasi auto-configuration factory provider."""
        self._auto_config_factories.append(factory_fn)

    def refresh(self):
        """Siklus hidup 'refresh()': Evaluasi kondisi, instansiasi, DI, dan Proxying."""
        log_info("Context", f"{TermColor.BOLD}Starting ApplicationContext refresh pipeline...{TermColor.RESET}")

        # Tahap 1: Evaluasi Conditional Auto-Configurations
        for factory in self._auto_config_factories:
            condition_type = getattr(factory, "__conditional_missing__", None)
            bean_name = factory.__name__.replace("create_", "")
            
            should_instantiate = True
            if condition_type:
                for registered_cls in self._bean_definitions.values():
                    if issubclass(registered_cls, condition_type):
                        log_warn("AutoConfig", f"Skipping '{bean_name}': Bean of type '{condition_type.__name__}' already exists.")
                        should_instantiate = False
                        break

            if should_instantiate:
                instance = factory()
                self._singleton_registry[bean_name] = instance
                log_info("AutoConfig", f"Activated fallback auto-configured bean: '{TermColor.YELLOW}{bean_name}{TermColor.RESET}'")

        # Tahap 2: Instansiasi & Dependency Injection (Constructor-based)
        unresolved = dict(self._bean_definitions)
        while unresolved:
            progress = False
            for name, cls in list(unresolved.items()):
                sig = inspect.signature(cls.__init__)
                params = [p for p in sig.parameters.values() if p.name != "self"]
                
                dependencies = {}
                can_resolve = True
                for p in params:
                    # Resolve bean berdasarkan anotasi tipe atau nama parameter
                    dep_instance = None
                    for inst in self._singleton_registry.values():
                        # Handle raw atau proxied instance
                        raw = getattr(inst, "_target", inst)
                        if (p.annotation != inspect.Parameter.empty and isinstance(raw, p.annotation)) or (p.name in self._singleton_registry):
                            dep_instance = inst
                            break

                    if dep_instance is not None:
                        dependencies[p.name] = dep_instance
                    else:
                        can_resolve = False
                        break

                if can_resolve:
                    raw_instance = cls(**dependencies)
                    # Tahap 3: BeanPostProcessor - AOP Proxy Wrap jika memiliki @Transactional
                    has_tx = any(getattr(getattr(raw_instance, m), "__transactional__", False) 
                                 for m in dir(raw_instance) if callable(getattr(raw_instance, m)))
                    
                    if has_tx:
                        proxied = AopProxyWrapper(raw_instance)
                        self._singleton_registry[name] = proxied
                        log_info("AopProxy", f"Created transactional AOP proxy for bean: '{TermColor.MAGENTA}{name}{TermColor.RESET}'")
                    else:
                        self._singleton_registry[name] = raw_instance
                        log_info("IoC-Resolve", f"Instantiated and injected dependencies for: '{TermColor.CYAN}{name}{TermColor.RESET}'")
                    
                    del unresolved[name]
                    progress = True

            if not progress and unresolved:
                circular_deps = ", ".join(unresolved.keys())
                raise RuntimeError(f"Unresolvable circular dependency or missing bean definitions: {circular_deps}")

        log_info("Context", f"{TermColor.BOLD}{TermColor.GREEN}ApplicationContext initialized successfully. Singletons: {len(self._singleton_registry)}{TermColor.RESET}")

    def get_bean(self, cls: Type) -> Any:
        """Mengambil bean dari registry berdasarkan tipe class."""
        for inst in self._singleton_registry.values():
            raw = getattr(inst, "_target", inst)
            if isinstance(raw, cls):
                return inst
        raise KeyError(f"No qualifying bean of type '{cls.__name__}' found in ApplicationContext")

# ==============================================================================
# Model Lab: Domain Service, Repository, & Auto-Configuration Setup
# ==============================================================================
class DataSource:
    def __init__(self, provider: str):
        self.provider = provider
    def query(self, sql: str):
        return f"[{self.provider}] Executed: {sql}"

# Simulasi Auto-Configuration: Default fallback jika user tidak menyediakan DataSource
@ConditionalOnMissingBean(DataSource)
def create_hikariDataSource() -> DataSource:
    return DataSource(provider="HikariCP-DefaultEmbeddedPool")

@Repository
class AccountRepository:
    def __init__(self, data_source: DataSource):
        self.ds = data_source
        self.ledger: Dict[str, float] = {"ACC_A": 1000.0, "ACC_B": 250.0}

    def debit(self, account_id: str, amount: float):
        if self.ledger[account_id] < amount:
            raise ValueError(f"Insufficient funds in {account_id}. Balance: {self.ledger[account_id]}")
        self.ledger[account_id] -= amount
        print(f"       -> {self.ds.query(f'UPDATE account SET balance = balance - {amount} WHERE id = {account_id}')}")

    def credit(self, account_id: str, amount: float):
        self.ledger[account_id] += amount
        print(f"       -> {self.ds.query(f'UPDATE account SET balance = balance + {amount} WHERE id = {account_id}')}")

@Service
class BankingTransferService:
    def __init__(self, account_repo: AccountRepository):
        self.repo = account_repo

    @Transactional(propagation="REQUIRED")
    def transfer(self, src: str, dest: str, amount: float):
        log_info("Business", f"Initiating transfer: {amount} EUR from {src} to {dest}")
        self.repo.debit(src, amount)
        self.repo.credit(dest, amount)
        return True

    @Transactional(read_only=True)
    def check_balance(self, account_id: str) -> float:
        return self.repo.ledger.get(account_id, 0.0)

# ==============================================================================
# Main Execution / Lab Walkthrough
# ==============================================================================
def main():
    print(f"\n{TermColor.BOLD}{TermColor.BLUE}======================================================================{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.BLUE}  SPRING BOOT 3 ARCHITECTURE: CORE IOC, AOP & AUTO-CONFIG DEEP DIVE  {TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.BLUE}======================================================================{TermColor.RESET}\n")

    context = SpringApplicationContext()

    # Step 1: Daftarkan Auto-Configuration fallback
    context.register_auto_configuration(create_hikariDataSource)

    # Step 2: Daftarkan Komponen Aplikasi
    context.register_component(AccountRepository)
    context.register_component(BankingTransferService)

    # Step 3: Lifecycle Refresh
    context.refresh()

    print(f"\n{TermColor.BOLD}--- [1] Menjalankan Transaksi Normal (@Transactional COMMIT) ---{TermColor.RESET}")
    service = context.get_bean(BankingTransferService)
    
    initial_a = service.check_balance("ACC_A")
    initial_b = service.check_balance("ACC_B")
    print(f"Saldo Awal -> ACC_A: {initial_a} EUR | ACC_B: {initial_b} EUR\n")

    service.transfer("ACC_A", "ACC_B", 300.0)
    
    print(f"\nSaldo Akhir -> ACC_A: {service.check_balance('ACC_A')} EUR | ACC_B: {service.check_balance('ACC_B')} EUR")

    print(f"\n{TermColor.BOLD}--- [2] Menjalankan Transaksi Gagal (@Transactional ROLLBACK) ---{TermColor.RESET}")
    try:
        # Mencoba transfer melebihi saldo: memicu ValueError
        service.transfer("ACC_A", "ACC_B", 5000.0)
    except Exception as e:
        log_err("App-Handler", f"Caught expected exception: {e}")

    print(f"\nVerifikasi Saldo Tidak Berubah Pasca-Rollback:")
    print(f"Saldo Saat Ini -> ACC_A: {service.check_balance('ACC_A')} EUR | ACC_B: {service.check_balance('ACC_B')} EUR\n")

    print(f"{TermColor.GREEN}✔ Skenario Berhasil: Simulasi IoC, Conditional Bean, dan Transactional Proxying Selesai.{TermColor.RESET}\n")

if __name__ == "__main__":
    main()