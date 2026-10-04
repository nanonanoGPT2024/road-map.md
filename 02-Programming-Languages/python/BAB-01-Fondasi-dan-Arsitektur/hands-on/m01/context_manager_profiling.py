import time
from contextlib import contextmanager

@contextmanager
def execution_timer(label):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"[{label}] Durasi eksekusi: {elapsed*1000:.3f} ms")

print("=== PYTHON ADVANCED: CONTEXT MANAGER & PROFILING ===")
with execution_timer("List Comprehension 1 Juta Elemen"):
    data = [x * 2 for x in range(1_000_000)]
print("Selesai.")
