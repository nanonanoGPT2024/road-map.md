import time
import json
import threading
from collections import deque

class ReactSimulator:
    def __init__(self):
        self.state = {}
        self.update_queue = deque()
        self.is_batching = False
        self.render_count = 0
    
    def use_state(self, key, initial_value):
        if key not in self.state:
            self.state[key] = initial_value
            print(f"[\033[94mMount\033[0m] Initialized state '{key}' with value: {initial_value}")
        
        def set_state(new_value_or_updater):
            print(f"[\033[93mAction\033[0m] set_state called for '{key}'")
            self.update_queue.append((key, new_value_or_updater))
            self.schedule_render()
            
        return self.state[key], set_state

    def schedule_render(self):
        if self.is_batching:
            print("[\033[90mScheduler\033[0m] Update batched (render deferred).")
            return
        
        print("[\033[90mScheduler\033[0m] Scheduling render microtask...")
        self.process_render()

    def process_render(self):
        if not self.update_queue:
            return
            
        self.render_count += 1
        print(f"\n[\033[95mRender Phase\033[0m] --- Render #{self.render_count} ---")
        
        next_state = self.state.copy()
        
        while self.update_queue:
            key, update = self.update_queue.popleft()
            if callable(update):
                # Updater function pattern
                next_state[key] = update(next_state[key])
                print(f"  -> Applied updater function for '{key}', new value: {next_state[key]}")
            else:
                next_state[key] = update
                print(f"  -> Applied value update for '{key}', new value: {next_state[key]}")
                
        # Simulate React's Object.is optimization
        has_changes = False
        for k in next_state:
            if k not in self.state or next_state[k] != self.state[k]:
                has_changes = True
                break
                
        if not has_changes:
            print("[\033[92mBailout\033[0m] State is equal to previous state. Bailing out of render.")
            return
            
        # Commit Phase
        self.state = next_state
        print(f"[\033[92mCommit Phase\033[0m] State committed to DOM simulator.")
        print(f"[\033[96mDOM\033[0m] Current UI State: {json.dumps(self.state, indent=2)}")

    def batch_updates(self, callback):
        """Simulates React 18 automatic batching for event handlers."""
        print("\n[\033[91mEvent Handler\033[0m] Starting batched event...")
        self.is_batching = True
        callback()
        self.is_batching = False
        print("[\033[91mEvent Handler\033[0m] Event finished. Triggering scheduled render if needed.")
        if self.update_queue:
            self.process_render()


def simulate_react_behavior():
    print("\n" + "="*50)
    print("REACT STATE & RENDER LIFECYCLE SIMULATOR")
    print("="*50 + "\n")
    
    react = ReactSimulator()
    
    # 1. Mount Phase
    count, set_count = react.use_state('count', 0)
    name, set_name = react.use_state('name', 'Anon')
    
    time.sleep(0.5)
    
    # 2. Synchronous Updates (Without Batching)
    print("\n--- SCENARIO 1: Unbatched Updates ---")
    set_count(1)
    
    time.sleep(0.5)
    
    # 3. Batched Updates (React 18 style event handler)
    print("\n--- SCENARIO 2: Batched Updates (Event Handler) ---")
    def handle_click():
        # Using updater functions to avoid stale state in multiple updates
        set_count(lambda prev: prev + 1)
        set_name("Budi")
        set_count(lambda prev: prev + 1)
        
    react.batch_updates(handle_click)
    
    time.sleep(0.5)
    
    # 4. Bailout (State unchanged)
    print("\n--- SCENARIO 3: State Bailout (Object.is optimization) ---")
    def handle_bailout():
        set_name("Budi") # Value is already "Budi"
        
    react.batch_updates(handle_bailout)
    
    time.sleep(0.5)
    print("\nSimulation complete.\n")

if __name__ == "__main__":
    simulate_react_behavior()
