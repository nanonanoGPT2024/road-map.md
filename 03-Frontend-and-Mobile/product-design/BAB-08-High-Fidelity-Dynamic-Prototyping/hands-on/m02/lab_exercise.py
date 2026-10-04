import os
import sys
import time
import json

# Terminal colors for high-fidelity UI simulation
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

class DynamicPrototypeSimulator:
    """
    Simulates a high-fidelity dynamic prototype's state machine in the terminal.
    It demonstrates how states, variables, and conditional logic interact 
    without needing a real GUI, perfect for testing prototype logic.
    """
    def __init__(self):
        self.state = {
            'cart': [],
            'balance': 1000.0,
            'current_view': 'home',
            'notifications': []
        }
        self.products = [
            {"id": 1, "name": "Premium UI Kit", "price": 45.0, "stock": 10},
            {"id": 2, "name": "UX Research Template", "price": 120.0, "stock": 5},
            {"id": 3, "name": "Icon Set", "price": 30.0, "stock": 20},
        ]

    def render(self):
        clear_screen()
        print(f"{Colors.HEADER}{Colors.BOLD}=== High-Fidelity Prototype State Simulator ==={Colors.ENDC}")
        print(f"Current View: {Colors.CYAN}{self.state['current_view'].upper()}{Colors.ENDC}\n")
        
        if self.state['notifications']:
            print(f"{Colors.WARNING}System Notifications:{Colors.ENDC}")
            for n in self.state['notifications']:
                print(f" - {n}")
            print()
            self.state['notifications'] = [] # Clear after showing
            
        if self.state['current_view'] == 'home':
            self._render_home()
        elif self.state['current_view'] == 'cart':
            self._render_cart()
        elif self.state['current_view'] == 'checkout':
            self._render_checkout()
            
        print(f"\n{Colors.BOLD}User Balance: ${self.state['balance']:.2f}{Colors.ENDC}")
        print("-" * 50)

    def _render_home(self):
        print(f"{Colors.BLUE}Storefront (Available Products):{Colors.ENDC}")
        for p in self.products:
            stock_color = Colors.GREEN if p['stock'] > 0 else Colors.FAIL
            print(f" [{p['id']}] {p['name']} - ${p['price']:.2f} (Stock: {stock_color}{p['stock']}{Colors.ENDC})")
            
        print("\nInteractions: [add <id>] to cart, [go cart] to view cart, [quit]")

    def _render_cart(self):
        print(f"{Colors.BLUE}Shopping Cart View:{Colors.ENDC}")
        if not self.state['cart']:
            print(" -> Cart is currently empty.")
        else:
            total = 0
            for item in self.state['cart']:
                print(f" -> {item['name']} (${item['price']:.2f})")
                total += item['price']
            print(f"{Colors.BOLD}Total Amount: ${total:.2f}{Colors.ENDC}")
            
        print("\nInteractions: [remove <id>], [checkout], [go home], [quit]")

    def _render_checkout(self):
        print(f"{Colors.BLUE}Checkout Process (Simulating Payment Gateway)...{Colors.ENDC}")
        total = sum(item['price'] for item in self.state['cart'])
        print(f"Amount to pay: ${total:.2f}")
        print("\nInteractions: [confirm], [cancel]")

    def process_input(self, cmd):
        parts = cmd.strip().lower().split()
        if not parts:
            return True
            
        action = parts[0]
        
        if action == 'quit':
            return False
            
        if self.state['current_view'] == 'home':
            if action == 'add' and len(parts) > 1:
                try:
                    self._add_to_cart(int(parts[1]))
                except ValueError:
                    self.state['notifications'].append("Invalid ID format.")
            elif action == 'go' and len(parts) > 1 and parts[1] == 'cart':
                self.state['current_view'] = 'cart'
        elif self.state['current_view'] == 'cart':
            if action == 'remove' and len(parts) > 1:
                try:
                    self._remove_from_cart(int(parts[1]))
                except ValueError:
                    self.state['notifications'].append("Invalid ID format.")
            elif action == 'go' and len(parts) > 1 and parts[1] == 'home':
                self.state['current_view'] = 'home'
            elif action == 'checkout':
                if self.state['cart']:
                    self.state['current_view'] = 'checkout'
                else:
                    self.state['notifications'].append("Action denied: Cart is empty!")
        elif self.state['current_view'] == 'checkout':
            if action == 'confirm':
                self._process_payment()
            elif action == 'cancel':
                self.state['current_view'] = 'cart'
                self.state['notifications'].append("Checkout cancelled by user.")
                
        return True

    def _add_to_cart(self, prod_id):
        product = next((p for p in self.products if p['id'] == prod_id), None)
        if product:
            if product['stock'] > 0:
                self.state['cart'].append(product)
                product['stock'] -= 1
                self.state['notifications'].append(f"Success: Added '{product['name']}' to cart.")
            else:
                self.state['notifications'].append(f"Error: '{product['name']}' is out of stock.")
        else:
            self.state['notifications'].append("Error: Product ID not found.")

    def _remove_from_cart(self, prod_id):
        for i, item in enumerate(self.state['cart']):
            if item['id'] == prod_id:
                self.state['cart'].pop(i)
                # Restore stock
                product = next(p for p in self.products if p['id'] == prod_id)
                product['stock'] += 1
                self.state['notifications'].append(f"Success: Removed '{item['name']}' from cart.")
                return
        self.state['notifications'].append("Error: Item not found in the cart.")

    def _process_payment(self):
        total = sum(item['price'] for item in self.state['cart'])
        if self.state['balance'] >= total:
            print("\n[Simulating network latency for realistic prototype feeling]")
            for i in range(5):
                time.sleep(0.4)
                sys.stdout.write("█")
                sys.stdout.flush()
            
            self.state['balance'] -= total
            self.state['cart'] = []
            self.state['current_view'] = 'home'
            self.state['notifications'].append(f"{Colors.GREEN}Payment successful! Deducted ${total:.2f}.{Colors.ENDC}")
        else:
            self.state['notifications'].append(f"{Colors.FAIL}Error: Insufficient funds! Please top up.{Colors.ENDC}")
            self.state['current_view'] = 'cart'

def main():
    simulator = DynamicPrototypeSimulator()
    running = True
    
    while running:
        simulator.render()
        try:
            cmd = input(f"{Colors.BOLD}Enter interaction>{Colors.ENDC} ")
            running = simulator.process_input(cmd)
        except KeyboardInterrupt:
            break
        except Exception as e:
            simulator.state['notifications'].append(f"Unexpected Error: {e}")

    print("\nExiting State Simulator. Goodbye!")

if __name__ == "__main__":
    main()
