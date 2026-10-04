import threading
import time
import queue
import random
import sys

# ANSI Colors
C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'
C_RED = '\033[91m'
C_BLUE = '\033[94m'
C_CYAN = '\033[96m'
C_RESET = '\033[0m'

class DatabaseConnection:
    def __init__(self, id):
        self.id = id
        self.is_active = False

    def connect(self):
        time.sleep(random.uniform(0.1, 0.3)) # Simulate connection setup time
        self.is_active = True
        return self

    def query(self, sql):
        time.sleep(random.uniform(0.2, 0.5)) # Simulate query execution time
        return f"Result for {sql}"

    def close(self):
        self.is_active = False

class ConnectionPool:
    def __init__(self, size):
        self.size = size
        self.pool = queue.Queue(maxsize=size)
        self.active_connections = 0
        self.lock = threading.Lock()
        
        print(f"{C_CYAN}[SYSTEM]{C_RESET} Initializing Connection Pool with size {size}...")
        for i in range(size):
            conn = DatabaseConnection(i+1)
            self.pool.put(conn)
            print(f"  {C_GREEN}+ Created connection #{conn.id}{C_RESET}")
            
    def get_connection(self, request_id):
        print(f"{C_YELLOW}[REQ-{request_id}]{C_RESET} Waiting for an available connection...")
        start_time = time.time()
        
        try:
            # Block until a connection is available (timeout after 5s)
            conn = self.pool.get(timeout=5)
            wait_time = time.time() - start_time
            
            with self.lock:
                self.active_connections += 1
                
            print(f"{C_BLUE}[REQ-{request_id}]{C_RESET} Acquired connection #{conn.id} (waited {wait_time:.2f}s). Active: {self.active_connections}/{self.size}")
            return conn
            
        except queue.Empty:
            print(f"{C_RED}[REQ-{request_id}]{C_RESET} Timeout! No connection available in the pool.")
            return None

    def release_connection(self, conn, request_id):
        with self.lock:
            self.active_connections -= 1
            
        self.pool.put(conn)
        print(f"{C_GREEN}[REQ-{request_id}]{C_RESET} Released connection #{conn.id}. Active: {self.active_connections}/{self.size}")

def worker_task(pool, request_id):
    conn = pool.get_connection(request_id)
    if not conn:
        return
        
    try:
        # Simulate executing a query
        print(f"{C_YELLOW}[REQ-{request_id}]{C_RESET} Executing database query using connection #{conn.id}...")
        conn.query("SELECT * FROM users")
        print(f"{C_BLUE}[REQ-{request_id}]{C_RESET} Query completed successfully.")
    finally:
        pool.release_connection(conn, request_id)

def main():
    print(f"{C_CYAN}======================================================={C_RESET}")
    print(f"{C_CYAN}    Next.js Database Connection Pool Simulation        {C_RESET}")
    print(f"{C_CYAN}======================================================={C_RESET}\n")
    
    POOL_SIZE = 3
    TOTAL_REQUESTS = 10
    
    pool = ConnectionPool(POOL_SIZE)
    
    print(f"\n{C_CYAN}[SYSTEM]{C_RESET} Simulating {TOTAL_REQUESTS} concurrent requests arriving at the Edge/Serverless function...")
    print(f"{C_CYAN}[SYSTEM]{C_RESET} Notice how requests queue up when active connections exceed POOL_SIZE ({POOL_SIZE})\n")
    
    threads = []
    
    for i in range(TOTAL_REQUESTS):
        # Requests come in slightly staggered
        time.sleep(random.uniform(0.05, 0.2))
        t = threading.Thread(target=worker_task, args=(pool, i+1))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    print(f"\n{C_CYAN}======================================================={C_RESET}")
    print(f"{C_CYAN}    Simulation Completed Successfully!                 {C_RESET}")
    print(f"{C_CYAN}======================================================={C_RESET}")

if __name__ == '__main__':
    main()
