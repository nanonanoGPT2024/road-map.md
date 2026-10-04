import os
import sys
import time
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
from urllib.error import URLError

# ANSI Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_step(step_name):
    print(f"\n{Colors.HEADER}{Colors.BOLD}--- [{time.strftime('%H:%M:%S')}] STEP: {step_name} ---{Colors.ENDC}")

class MockNextjsServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = {"status": "ok", "message": "Mock Next.js E2E Server"}
        self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass

def start_mock_server(port):
    server = HTTPServer(('localhost', port), MockNextjsServerHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server

def simulate_linting():
    print_step("Linting Next.js Codebase")
    print("Running ESLint checks...")
    time.sleep(1)
    files_checked = 150
    print(f"{Colors.OKCYAN}Checked {files_checked} files.{Colors.ENDC}")
    print(f"{Colors.OKGREEN}Linting passed with 0 errors and 0 warnings.{Colors.ENDC}")

def simulate_unit_tests():
    print_step("Running Unit Tests (Jest)")
    print("Executing test suites...")
    suites = ['components/Header.test.tsx', 'pages/index.test.tsx', 'utils/api.test.ts']
    for suite in suites:
        time.sleep(0.5)
        print(f"  {Colors.OKGREEN}PASS{Colors.ENDC} {suite}")
    print(f"\n{Colors.BOLD}Test Suites:{Colors.ENDC} {Colors.OKGREEN}3 passed{Colors.ENDC}, 3 total")
    print(f"{Colors.BOLD}Tests:{Colors.ENDC}       {Colors.OKGREEN}12 passed{Colors.ENDC}, 12 total")

def simulate_build():
    print_step("Building Next.js Application")
    print("Creating an optimized production build...")
    time.sleep(1.5)
    print(f"{Colors.OKCYAN}Route (pages)                              Size     First Load JS{Colors.ENDC}")
    print(f"┌ ● /                                      4.2 kB           85 kB")
    print(f"├   /_app                                  0 B              80.8 kB")
    print(f"├ ○ /404                                   194 B            81 kB")
    print(f"└ λ /api/hello                             0 B              80.8 kB")
    print(f"{Colors.OKGREEN}Build completed successfully.{Colors.ENDC}")

def simulate_e2e_tests():
    print_step("Running End-to-End Tests (Cypress/Playwright)")
    port = 8080
    print(f"Starting local mock Next.js server on port {port}...")
    server = start_mock_server(port)
    time.sleep(1)
    
    print("Server ready. Executing E2E specs...")
    specs = [
        "auth.spec.ts (User Login Flow)",
        "checkout.spec.ts (Shopping Cart Checkout)",
        "navigation.spec.ts (Main Menu Navigation)"
    ]
    
    for spec in specs:
        print(f"[{Colors.WARNING}RUNNING{Colors.ENDC}] {spec}...")
        try:
            # Simulate a health check/fetch done by the E2E tool
            req = urllib.request.Request(f'http://localhost:{port}/')
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    time.sleep(1)
                    print(f"[{Colors.OKGREEN}PASSED{Colors.ENDC}]  {spec}")
                else:
                    print(f"[{Colors.FAIL}FAILED{Colors.ENDC}]  {spec} - Bad status {response.status}")
        except URLError as e:
            print(f"[{Colors.FAIL}FAILED{Colors.ENDC}]  {spec} - Server unreachable: {e}")
            raise e
            
    print("Shutting down mock server...")
    server.shutdown()
    print(f"{Colors.OKGREEN}All E2E tests completed successfully.{Colors.ENDC}")

def simulate_deployment():
    print_step("Deploying to Staging Environment")
    print("Uploading build artifacts...")
    for i in range(1, 101, 25):
        print(f"Upload progress: {i}%")
        time.sleep(0.3)
    print("Upload progress: 100%")
    print(f"{Colors.OKGREEN}Deployment successful!{Colors.ENDC}")
    print(f"Staging URL: {Colors.UNDERLINE}https://staging.example-nextjs-app.com{Colors.ENDC}")

def run_pipeline():
    print(f"{Colors.BOLD}{Colors.OKBLUE}===================================================={Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.OKBLUE}       NEXT.JS CI/CD AUTOMATION SIMULATOR           {Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.OKBLUE}===================================================={Colors.ENDC}")
    
    start_time = time.time()
    try:
        simulate_linting()
        simulate_unit_tests()
        simulate_build()
        simulate_e2e_tests()
        simulate_deployment()
    except Exception as e:
        print(f"\n{Colors.FAIL}Pipeline failed: {e}{Colors.ENDC}")
        sys.exit(1)
    
    end_time = time.time()
    duration = end_time - start_time
    print(f"\n{Colors.BOLD}{Colors.OKGREEN}===================================================={Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.OKGREEN} PIPELINE SUCCESSFUL (Duration: {duration:.2f}s) {Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.OKGREEN}===================================================={Colors.ENDC}")

if __name__ == '__main__':
    run_pipeline()
