import os
import sys
import time
import json
from dataclasses import dataclass, field
from typing import List, Dict, Set

# --- ANSI Colors ---
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

def print_info(msg):
    print(f"{Colors.OKCYAN}[INFO]{Colors.ENDC} {msg}")

def print_success(msg):
    print(f"{Colors.OKGREEN}[GRANTED]{Colors.ENDC} {msg}")

def print_error(msg):
    print(f"{Colors.FAIL}[DENIED]{Colors.ENDC} {msg}")

def print_warning(msg):
    print(f"{Colors.WARNING}[WARN]{Colors.ENDC} {msg}")

# --- Models ---
@dataclass
class User:
    user_id: str
    username: str
    roles: List[str]

# --- RBAC Database Simulation ---
ROLES_PERMISSIONS = {
    "admin": {
        "users": ["create", "read", "update", "delete"],
        "reports": ["read", "export"],
        "settings": ["read", "update"]
    },
    "manager": {
        "users": ["read"],
        "reports": ["read", "export"],
        "settings": ["read"]
    },
    "employee": {
        "users": ["read_self"],
        "reports": ["read"],
        "settings": []
    }
}

USERS_DB = {
    "u1": User("u1", "alice_admin", ["admin"]),
    "u2": User("u2", "bob_manager", ["manager"]),
    "u3": User("u3", "charlie_emp", ["employee"]),
    "u4": User("u4", "diana_dual", ["employee", "manager"])
}

# --- Access Control Engine ---
class RBACEngine:
    def __init__(self, roles_db):
        self.roles_db = roles_db

    def _get_user_permissions(self, roles: List[str]) -> Dict[str, Set[str]]:
        aggregated_perms = {}
        for role in roles:
            if role in self.roles_db:
                role_perms = self.roles_db[role]
                for resource, actions in role_perms.items():
                    if resource not in aggregated_perms:
                        aggregated_perms[resource] = set()
                    aggregated_perms[resource].update(actions)
        return aggregated_perms

    def authorize(self, user: User, resource: str, action: str) -> bool:
        print_info(f"Checking authorization for user '{user.username}' -> {action} on {resource}")
        time.sleep(0.5) # Simulate DB lookup or token parsing
        
        perms = self._get_user_permissions(user.roles)
        
        if resource not in perms:
            return False
            
        return action in perms[resource]

# --- Simulated API Requests ---
def simulate_api_request(engine: RBACEngine, user_id: str, resource: str, action: str):
    print(f"\n{Colors.HEADER}{'-'*50}{Colors.ENDC}")
    print(f"API Request: {Colors.BOLD}{action.upper()}{Colors.ENDC} /{resource}")
    
    if user_id not in USERS_DB:
        print_error("Invalid Auth Token: User not found.")
        return
        
    user = USERS_DB[user_id]
    print_info(f"Authenticated as: {user.username} (Roles: {', '.join(user.roles)})")
    
    is_authorized = engine.authorize(user, resource, action)
    
    if is_authorized:
        print_success(f"User '{user.username}' is authorized to {action} {resource}.")
        # Simulate processing
        time.sleep(0.3)
        print_info(f"Returning data for {resource}...")
    else:
        print_error(f"User '{user.username}' lacks permission to {action} {resource}.")

def main():
    print(f"{Colors.HEADER}=== Enterprise Security & RBAC Simulation ==={Colors.ENDC}")
    print("Initializing RBAC Engine...")
    engine = RBACEngine(ROLES_PERMISSIONS)
    time.sleep(1)
    
    print("\n--- Test Case 1: Admin Access ---")
    simulate_api_request(engine, "u1", "users", "delete")
    
    print("\n--- Test Case 2: Manager Access ---")
    simulate_api_request(engine, "u2", "reports", "export")
    simulate_api_request(engine, "u2", "users", "update") # Should fail
    
    print("\n--- Test Case 3: Employee Access ---")
    simulate_api_request(engine, "u3", "reports", "read")
    simulate_api_request(engine, "u3", "settings", "read") # Should fail
    
    print("\n--- Test Case 4: Dual Roles (Manager + Employee) ---")
    # Will have aggregated permissions
    simulate_api_request(engine, "u4", "reports", "export") # from manager
    simulate_api_request(engine, "u4", "settings", "read")  # from manager
    
    print("\n--- Test Case 5: Unauthenticated User ---")
    simulate_api_request(engine, "u99", "users", "read")

    print(f"\n{Colors.OKGREEN}Simulation Complete.{Colors.ENDC}")

if __name__ == "__main__":
    main()
