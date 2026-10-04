import time
import random
import threading
import sys
import json
import uuid

# --- SIMULASI SISTEM OBSERVABILITAS (LOGGING & METRICS) ---
class MetricsRegistry:
    def __init__(self):
        self.metrics = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_failed": 0,
            "circuit_breaker_trips": 0
        }
        self.lock = threading.Lock()

    def inc(self, metric_name):
        with self.lock:
            if metric_name in self.metrics:
                self.metrics[metric_name] += 1

    def print_summary(self):
        print("\n\033[95m=== METRICS SUMMARY ===\033[0m")
        print(json.dumps(self.metrics, indent=2))
        print("\033[95m=======================\033[0m\n")

metrics = MetricsRegistry()

def log_trace(trace_id, span_name, status, duration_ms):
    log_entry = {
        "timestamp": time.time(),
        "trace_id": trace_id,
        "span": span_name,
        "status": status,
        "duration_ms": round(duration_ms, 2)
    }
    # Simulate sending log to a centralized logging system (e.g., Datadog, ELK)
    print(f"\033[90m[TRACE LOG] {json.dumps(log_entry)}\033[0m")

# --- SIMULASI RESILIENSI (CIRCUIT BREAKER) ---
class CircuitBreaker:
    def __init__(self, name, failure_threshold=3, recovery_timeout=5):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_failure_time = None
        self.lock = threading.Lock()
        
    def call(self, func, *args, **kwargs):
        trace_id = kwargs.pop("trace_id", str(uuid.uuid4()))
        start_time = time.time()
        
        with self.lock:
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    print(f"\033[93m[Circuit Breaker '{self.name}'] Timeout reached. Transitioning to HALF-OPEN.\033[0m")
                    self.state = "HALF-OPEN"
                else:
                    duration = (time.time() - start_time) * 1000
                    log_trace(trace_id, self.name, "REJECTED (FAST FAIL)", duration)
                    metrics.inc("requests_failed")
                    raise Exception(f"Circuit '{self.name}' is OPEN. Fast failing request.")
        
        try:
            result = func(*args, **kwargs)
            duration = (time.time() - start_time) * 1000
            
            with self.lock:
                if self.state == "HALF-OPEN":
                    print(f"\033[92m[Circuit Breaker '{self.name}'] Success in HALF-OPEN state. Transitioning to CLOSED.\033[0m")
                    self.state = "CLOSED"
                    self.failure_count = 0
                    
            log_trace(trace_id, self.name, "SUCCESS", duration)
            metrics.inc("requests_success")
            return result
            
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            
            with self.lock:
                if self.state == "HALF-OPEN":
                    print(f"\033[91m[Circuit Breaker '{self.name}'] Failure in HALF-OPEN state. Transitioning back to OPEN.\033[0m")
                    self.state = "OPEN"
                    self.last_failure_time = time.time()
                    metrics.inc("circuit_breaker_trips")
                else:
                    self.failure_count += 1
                    print(f"\033[91m[Circuit Breaker '{self.name}'] Failure count: {self.failure_count}/{self.failure_threshold}\033[0m")
                    if self.failure_count >= self.failure_threshold:
                        print(f"\033[91m[Circuit Breaker '{self.name}'] Threshold reached. Transitioning to OPEN.\033[0m")
                        self.state = "OPEN"
                        self.last_failure_time = time.time()
                        metrics.inc("circuit_breaker_trips")
                        
            log_trace(trace_id, self.name, "ERROR", duration)
            metrics.inc("requests_failed")
            raise e

# --- SIMULASI MICROSERVICES ---
def payment_service():
    """Simulates a flaky payment gateway that randomly fails or times out"""
    time.sleep(random.uniform(0.1, 0.5)) # Network latency
    chance = random.random()
    if chance < 0.5: # 50% chance of failure (high error rate for simulation)
        raise Exception("503 Service Unavailable (Payment Gateway)")
    return "200 OK - Payment Processed"

def simulate_traffic():
    print("\033[96m=== Starting Next.js Observability & Resilience Simulation ===\033[0m")
    print("\033[96mSimulating API Route calling an unreliable Payment Service with Circuit Breaker...\033[0m\n")
    
    cb = CircuitBreaker(name="PaymentAPI", failure_threshold=3, recovery_timeout=4)
    
    # Simulate 25 requests over time
    for i in range(1, 26):
        metrics.inc("requests_total")
        trace_id = f"req-{i:03d}-{uuid.uuid4().hex[:8]}"
        print(f"\n\033[94m--- [Next.js API Route] Request {i} (Trace: {trace_id}) ---\033[0m")
        
        try:
            # API Route calling backend with Circuit Breaker
            res = cb.call(payment_service, trace_id=trace_id)
            print(f"\033[92m[Client Response] 200 OK: {res}\033[0m")
        except Exception as e:
            print(f"\033[91m[Client Response] 500 Internal Error: {e}\033[0m")
            
        time.sleep(0.8) # Traffic rate

    metrics.print_summary()

if __name__ == "__main__":
    try:
        simulate_traffic()
    except KeyboardInterrupt:
        print("\n\033[93mSimulation stopped by user.\033[0m")
        sys.exit(0)
