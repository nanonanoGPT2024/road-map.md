#!/usr/bin/env python3
"""
Lab Exercise: V8 Engine Under the Hood & Execution Mechanics
Simulating Hidden Classes (Shapes), Transitions, Inline Caching (IC),
JIT Tier-Up (Ignition to TurboFan), and Deoptimization (Bailout).
"""

import time
import sys
from typing import Dict, Any, Optional, List, Tuple

# Terminal Colors for V8 Engine Diagnostics
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"


class Shape:
    """
    Represents a V8 Hidden Class (Map/Shape).
    Tracks property offsets and transitions to successor Shapes.
    """
    _id_counter = 0

    def __init__(self, parent: Optional['Shape'] = None, transition_prop: Optional[str] = None):
        self.id = Shape._id_counter
        Shape._id_counter += 1
        self.parent = parent
        self.transition_prop = transition_prop
        self.transitions: Dict[str, 'Shape'] = {}
        
        # Prop name -> array index offset in the object's backing store
        self.offsets: Dict[str, int] = {}
        if parent:
            self.offsets = parent.offsets.copy()
            if transition_prop is not None:
                self.offsets[transition_prop] = len(parent.offsets)

    def transition(self, prop: str) -> 'Shape':
        """Calculates or retrieves an existing Shape transition for a new property."""
        if prop not in self.transitions:
            self.transitions[prop] = Shape(parent=self, transition_prop=prop)
        return self.transitions[prop]

    def __repr__(self) -> str:
        props = list(self.offsets.keys())
        return f"Shape#{self.id}(keys={props})"


# Global Root Shape (Initial state of empty objects)
ROOT_SHAPE = Shape()


class JSObject:
    """
    Represents a JS Object in V8.
    Does not store a dictionary of keys to values. Instead, maintains a pointer
    to a Shape and a contiguous array of fast properties (backing store).
    """
    def __init__(self):
        self.shape: Shape = ROOT_SHAPE
        self.properties: List[Any] = []

    def set(self, prop: str, value: Any) -> None:
        """Sets a property, executing a Shape transition if the key is new."""
        if prop in self.shape.offsets:
            offset = self.shape.offsets[prop]
            self.properties[offset] = value
        else:
            # Transition to next shape
            new_shape = self.shape.transition(prop)
            self.shape = new_shape
            self.properties.append(value)

    def get(self, prop: str) -> Tuple[Any, int]:
        """Returns the value and property offset using slow Shape dictionary lookup."""
        if prop in self.shape.offsets:
            offset = self.shape.offsets[prop]
            return self.properties[offset], offset
        raise AttributeError(f"Property '{prop}' does not exist on object.")


class InlineCache:
    """
    Simulates V8 Inline Cache (IC) for property loads.
    States:
      - UNINITIALIZED: No shapes seen yet.
      - MONOMORPHIC: Exactly 1 shape observed (Fastest, direct offset).
      - POLYMORPHIC: 2 to 4 shapes observed (Linear search across cached shapes).
      - MEGAMORPHIC: >4 shapes observed (Fallback to generic dictionary lookup).
    """
    STATE_UNINITIALIZED = "UNINITIALIZED"
    STATE_MONOMORPHIC = "MONOMORPHIC"
    STATE_POLYMORPHIC = "POLYMORPHIC"
    STATE_MEGAMORPHIC = "MEGAMORPHIC"

    def __init__(self, site_id: str):
        self.site_id = site_id
        self.state = self.STATE_UNINITIALIZED
        self.entries: List[Tuple[Shape, int]] = []  # List of (Shape, offset)
        self.hits = 0
        self.misses = 0

    def load(self, obj: JSObject, prop: str) -> Any:
        """Loads property while updating Inline Cache feedback structures."""
        current_shape = obj.shape

        # 1. Monomorphic / Polymorphic fast path check
        for cached_shape, offset in self.entries:
            if cached_shape is current_shape:
                self.hits += 1
                return obj.properties[offset]

        # 2. Cache miss -> slow lookup and IC state transition
        self.misses += 1
        val, offset = obj.get(prop)

        if self.state == self.STATE_UNINITIALIZED:
            self.entries.append((current_shape, offset))
            self.state = self.STATE_MONOMORPHIC
        elif self.state == self.STATE_MONOMORPHIC:
            self.entries.append((current_shape, offset))
            self.state = self.STATE_POLYMORPHIC
        elif self.state == self.STATE_POLYMORPHIC:
            if len(self.entries) < 4:
                self.entries.append((current_shape, offset))
            else:
                self.entries.clear()
                self.state = self.STATE_MEGAMORPHIC
        elif self.state == self.STATE_MEGAMORPHIC:
            # Megamorphic stub: does not record further shapes to prevent unbounded cache growth
            pass

        return val


class ExecutionPipeline:
    """
    Simulates V8 Engine Execution Mechanics:
    Bytecode Interpreter (Ignition) -> Optimization (TurboFan) -> Deoptimization.
    """
    TIER_IGNITION = "Ignition (Bytecode Interpreter)"
    TIER_TURBOFAN = "TurboFan (Optimized JIT Code)"
    HOT_THRESHOLD = 50

    def __init__(self):
        self.ic = InlineCache("load_point_x")
        self.invocation_count = 0
        self.tier = self.TIER_IGNITION
        self.optimized_shape: Optional[Shape] = None
        self.deopt_count = 0

    def get_x(self, obj: JSObject) -> Any:
        """Simulates compiled JS function: function getX(p) { return p.x; }"""
        self.invocation_count += 1

        # Check JIT Execution Path
        if self.tier == self.TIER_TURBOFAN:
            # TurboFan emits speculative machine instructions:
            # CMP [obj.shape], expected_shape; JNE deopt_trampoline
            if obj.shape is self.optimized_shape:
                # Direct memory dereference at optimized constant offset (0 overhead)
                return obj.properties[0]
            else:
                # Speculation failed -> DEOPTIMIZE (Bailout)
                self._deoptimize(reason=f"Shape mismatch! Expected Shape#{self.optimized_shape.id}, got Shape#{obj.shape.id}")
                return self.ic.load(obj, "x")

        # Interpreter Path (Ignition)
        val = self.ic.load(obj, "x")

        # Tier-up check: When invocation exceeds threshold and IC is stable (Monomorphic)
        if (self.tier == self.TIER_IGNITION and 
            self.invocation_count >= self.HOT_THRESHOLD and 
            self.ic.state == InlineCache.STATE_MONOMORPHIC):
            self._tier_up()

        return val

    def _tier_up(self):
        self.tier = self.TIER_TURBOFAN
        self.optimized_shape = self.ic.entries[0][0]
        print(f"{GREEN}[TurboFan Tier-Up]{RESET} Function compiled to machine code!")
        print(f"  └─ Speculated Shape: {CYAN}Shape#{self.optimized_shape.id}{RESET} (Offset: 0)")
        print(f"  └─ Inline Cache State: {MAGENTA}{self.ic.state}{RESET}\n")

    def _deoptimize(self, reason: str):
        self.deopt_count += 1
        self.tier = self.TIER_IGNITION
        print(f"{RED}[TurboFan Deopt / Bailout!]{RESET} Invariant broken: {reason}")
        print(f"  └─ Falling back to: {YELLOW}{self.tier}{RESET}")
        print(f"  └─ TurboFan code invalidated. Re-entering Ignition interpreter.\n")


def create_point_xy(x: int, y: int) -> JSObject:
    """Creates point object initialized in order: x, then y."""
    p = JSObject()
    p.set("x", x)
    p.set("y", y)
    return p


def create_point_yx(x: int, y: int) -> JSObject:
    """Creates point object initialized in order: y, then x (Causes Shape branch)."""
    p = JSObject()
    p.set("y", y)
    p.set("x", x)
    return p


def run_lab():
    print(f"{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE}    V8 ENGINE EXECUTION & OPTIMIZATION PIPELINE SIMULATOR            {RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}\n")

    pipeline = ExecutionPipeline()

    # PHASE 1: Shape Transitions Demonstration
    print(f"{BOLD}{YELLOW}--- PHASE 1: Hidden Class (Shape) Transitions ---{RESET}")
    p1 = create_point_xy(10, 20)
    p2 = create_point_xy(30, 40)
    p3 = create_point_yx(50, 60)

    print(f"Object p1 (x, y): {CYAN}{p1.shape}{RESET} | Backing Store: {p1.properties}")
    print(f"Object p2 (x, y): {CYAN}{p2.shape}{RESET} | Backing Store: {p2.properties}")
    print(f"Object p3 (y, x): {MAGENTA}{p3.shape}{RESET} | Backing Store: {p3.properties}")
    print(f"  [*] p1 and p2 share the same Shape? {GREEN}{p1.shape is p2.shape}{RESET}")
    print(f"  [*] p1 and p3 share the same Shape? {RED}{p1.shape is p3.shape}{RESET} (Structural order matters!)\n")

    time.sleep(0.5)

    # PHASE 2: Warm-up in Ignition and JIT Tier-up
    print(f"{BOLD}{YELLOW}--- PHASE 2: Function Warm-Up & Inline Caching (Ignition) ---{RESET}")
    print(f"Invoking `getX(p)` across 55 iterations using identical shape...")
    
    for i in range(1, 56):
        obj = create_point_xy(i, i * 2)
        pipeline.get_x(obj)
        if i in (1, 10, 49, 50, 51):
            print(f"  Iteration {i:02d}: Tier={YELLOW if 'Ignition' in pipeline.tier else GREEN}{pipeline.tier}{RESET} | IC State={MAGENTA}{pipeline.ic.state}{RESET}")

    # PHASE 3: TurboFan Fast Path Executions
    print(f"\n{BOLD}{YELLOW}--- PHASE 3: Fast-Path TurboFan Execution ---{RESET}")
    for _ in range(3):
        res = pipeline.get_x(create_point_xy(99, 100))
    print(f"Successfully executed in {GREEN}{pipeline.tier}{RESET} (Direct machine register read, x={res})\n")

    time.sleep(0.5)

    # PHASE 4: Deoptimization Trigger (Bailout)
    print(f"{BOLD}{YELLOW}--- PHASE 4: Passing Anomalous Shape -> Triggering Deoptimization ---{RESET}")
    print("Feeding `p3` (Shape initialized with 'y' before 'x') into optimized TurboFan code...")
    pipeline.get_x(p3)

    # PHASE 5: Polymorphism and Megamorphism
    print(f"{BOLD}{YELLOW}--- PHASE 5: Polymorphism & Megamorphism Transitions ---{RESET}")
    print(f"Current IC State: {MAGENTA}{pipeline.ic.state}{RESET}")
    
    # Generate objects with distinct shapes
    shapes_pool = []
    for prop_char in ["a", "b", "c", "d"]:
        obj = JSObject()
        obj.set(prop_char, 1)
        obj.set("x", 42)
        shapes_pool.append(obj)

    for idx, dynamic_obj in enumerate(shapes_pool, start=1):
        pipeline.get_x(dynamic_obj)
        print(f"Introduced variant #{idx}: IC State mutated to -> {MAGENTA}{pipeline.ic.state}{RESET} (Entries count: {len(pipeline.ic.entries)})")

    # Final Engine Diagnostic Summary
    print(f"\n{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE}                     V8 ENGINE EXECUTION METRICS                      {RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")
    print(f" Total Invocations       : {pipeline.invocation_count}")
    print(f" Final Execution Tier    : {YELLOW}{pipeline.tier}{RESET}")
    print(f" Inline Cache State      : {MAGENTA}{pipeline.ic.state}{RESET}")
    print(f" IC Cache Hits / Misses  : {GREEN}{pipeline.ic.hits}{RESET} hits / {RED}{pipeline.ic.misses}{RESET} misses")
    print(f" Total Deopts Encountered: {RED}{pipeline.deopt_count}{RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}\n")


if __name__ == "__main__":
    run_lab()
02-Programming-Languages/javascript/01-v8-engine-under-the-hood-and-execution-mechanics/05-ignition-bytecode-interpreter/lab_exercise.py

        
        while self.pc < len(self.accumulator): # dummy check
            if self.pc >= len(self.code):
                break
            
            instr = self.code[self.pc]
            op = instr.op
            args = instr.args
            
            # Print execution step
            args_str = ", ".join(f"{k}={v}" for k, v in args.items())
            print(f"  {CYAN}0x{self.pc:04x}{RESET} : {YELLOW}{op.name:<18}{RESET} {args_str}")

            self.pc += 1

            # Dispatch opcode logic
            if op == Opcode.LdaNamedProperty:
                # Load named property from object in reg into acc using feedback slot
                obj: JSObject = self.registers[args['reg']]
                prop = args['prop']
                slot = args['slot']
                
                # Update Feedback Vector
                val = self.feedback_vector.record_property_load(slot, obj, prop)
                self.accumulator = val

            elif op == Opcode.Star:
                # Store accumulator to register
                dest_reg = args['reg']
                self.registers[dest_reg] = self.accumulator

            elif op == Opcode.LdaConstant:
                # Load constant to accumulator
                self.accumulator = args['val']

            elif op == Opcode.Add:
                # Add register to accumulator
                src_reg = args['reg']
                val = self.registers[src_reg]
                self.accumulator = val + self.accumulator

            elif op == Opcode.Return:
                print(f"  {GREEN}--> Return Value:{RESET} {BOLD}{self.accumulator}{RESET}")
                return self.accumulator

            else:
                raise RuntimeError(f"Unknown Bytecode Opcode: {op}")

        return self.accumulator


def run_lab():
    print(f"{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE}       V8 IGNITION BYTECODE INTERPRETER & DISPATCH PIPELINE           {RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}\n")

    # 1. Bytecode Generation simulation
    # Corresponds to JavaScript:
    # function computeTotal(order) {
    #     let base = order.price;
    #     let tax = 5;
    #     return base + tax;
    # }
    print(f"{BOLD}{YELLOW}[Step 1] Bytecode Generation from AST:{RESET}")
    bytecode_stream = [
        # Slot 0 is assigned for 'price' lookup on order (passed in r0)
        BytecodeInstruction(Opcode.LdaNamedProperty, reg='r0', prop='price', slot=0),
        BytecodeInstruction(Opcode.Star, reg='r1'),              # r1 = order.price
        BytecodeInstruction(Opcode.LdaConstant, val=5),          # acc = 5 (tax)
        BytecodeInstruction(Opcode.Add, reg='r1'),               # acc = r1 + acc
        BytecodeInstruction(Opcode.Return)                       # return acc
    ]

    for idx, instr in enumerate(bytecode_stream):
        args_repr = ", ".join(f"{k}={v}" for k, v in instr.args.items())
        print(f"  BCode offset [{idx}]: {instr.op.name:<18} {args_repr}")

    # Initialize Engine Components
    feedback_vector = FeedbackVector(num_slots=1)
    vm = IgnitionVM(bytecode_stream, feedback_vector)

    # 2. Simulate Warm-Up Phase (Ignition interpreting identical object shapes)
    print(f"\n{BOLD}{YELLOW}[Step 2] Warm-up Execution: Gathering Monomorphic Feedback:{RESET}")
    for i in range(1, 4):
        print(f"\n--- Execution Run #{i} ---")
        order = JSObject("Order_Shape_A", {"price": 100 * i, "item": "Widget"})
        vm.execute(args=[order])

    # Inspect Feedback Vector
    print(f"\n{BOLD}{YELLOW}[Step 3] Inspecting Ignition Feedback Vector Slot 0:{RESET}")
    slot_info = feedback_vector.inspect_slot(0)
    print(f"  Status        : {GREEN}{slot_info['status']}{RESET}")
    print(f"  Invocations   : {slot_info['invocations']}")
    print(f"  Tracked Shapes: {slot_info['shapes']}")

    # 3. Polymorphic Transition
    print(f"\n{BOLD}{YELLOW}[Step 4] Triggering Polymorphic State (Different Object Shape):{RESET}")
    print("--- Execution Run #4 with Altered Shape ---")
    order_variant = JSObject("Order_Shape_B", {"id": 999, "price": 450})
    vm.execute(args=[order_variant])

    slot_info = feedback_vector.inspect_slot(0)
    print(f"\n  Updated Status : {YELLOW}{slot_info['status']}{RESET}")
    print(f"  Tracked Shapes : {slot_info['shapes']}")

    # 4. Megamorphic Transition
    print(f"\n{BOLD}{YELLOW}[Step 5] Forcing Megamorphic Fallback (>4 Distinct Shapes):{RESET}")
    for idx in range(3, 8):
        shape_name = f"Order_Shape_{chr(65 + idx)}"
        dynamic_order = JSObject(shape_name, {"price": 10 + idx})
        vm.execute(args=[dynamic_order])

    slot_info = feedback_vector.inspect_slot(0)
    print(f"\n{BOLD}{YELLOW}[Final Feedback Vector State]:{RESET}")
    print(f"  Slot 0 State  : {RED}{slot_info['status']}{RESET} (TurboFan will avoid inlining this property load)")
    print(f"  Total Calls   : {slot_info['invocations']}")

    print(f"\n{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE}               IGNITION SIMULATION COMPLETE                           {RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}\n")


if __name__ == "__main__":
    run_lab()
#!/usr/bin/env python3
"""
Lab Exercise: V8 Ignition Bytecode Interpreter Architecture
Simulates Ignition's Register-Accumulator register machine, Bytecode dispatch loop,
and type-feedback collection via the Feedback Vector.
"""

from enum import Enum, auto
from typing import Dict, Any, List, Optional

# ANSI Color Codes for terminal diagnostics
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"


class Opcode(Enum):
    """Core Ignition Bytecode Opcodes (Register/Accumulator architecture)."""
    LdaNamedProperty = auto()  # Load named property into accumulator: acc = obj.prop
    LdaConstant = auto()       # Load constant to accumulator: acc = const
    Star = auto()              # Store accumulator to register: reg = acc
    Add = auto()               # Add register value to accumulator: acc = reg + acc
    Return = auto()            # Return accumulator


class BytecodeInstruction:
    """Represents a single compiled Ignition bytecode instruction with operands."""
    def __init__(self, op: Opcode, **args):
        self.op = op
        self.args = args

    def __repr__(self):
        operands = ", ".join(f"{k}={v}" for k, v in self.args.items())
        return f"{self.op.name}({operands})"


class JSObject:
    """Mock JS Object with an explicit shape/map and property storage."""
    def __init__(self, shape_id: str, properties: Dict[str, Any]):
        self.shape_id = shape_id
        self.properties = properties


class FeedbackVector:
    """
    Feedback Vector attached to every function.
    Maintains slots tracking runtime type feedback (e.g., seen shapes for load ICs).
    """
    def __init__(self, num_slots: int):
        # Slots store shape mappings or Megamorphic sentinel
        self.slots: List[Dict[str, Any]] = [{"invocations": 0, "shapes": set(), "status": "UNINITIALIZED"} for _ in range(num_slots)]

    def record_property_load(self, slot_idx: int, obj: JSObject, prop: str) -> Any:
        slot = self.slots[slot_idx]
        slot["invocations"] += 1
        shapes = slot["shapes"]

        shapes.add(obj.shape_id)
        if len(shapes) == 1:
            slot["status"] = "MONOMORPHIC"
        elif len(shapes) <= 4:
            slot["status"] = "POLYMORPHIC"
        else:
            slot["status"] = "MEGAMORPHIC"

        return obj.properties.get(prop, None)

    def inspect_slot(self, slot_idx: int) -> Dict[str, Any]:
        return self.slots[slot_idx]


class IgnitionVM:
    """
    Simulates the V8 Ignition Interpreter:
    - Accumulator register (implicit operand for ALU & property loads).
    - Register file (r0, r1, ... rN) for local variables and arguments.
    - Bytecode Program Counter (PC) and instruction dispatch loop.
    """
    def __init__(self, bytecode: List[BytecodeInstruction], feedback_vector: FeedbackVector):
        self.code = bytecode
        self.feedback_vector = feedback_vector
        self.pc = 0
        self.accumulator: Any = None
        self.registers: Dict[str, Any] = {}

    def reset(self, args: Optional[List[Any]] = None):
        """Resets VM state before function invocation."""
        self.pc = 0
        self.accumulator = None
        self.registers.clear()
        if args:
            for idx, arg in enumerate(args):
                self.registers[f"r{idx}"] = arg

    def execute(self, args: Optional[List[Any]] = None) -> Any:
        """Executes bytecode stream via the dispatch loop."""
        self.reset(args)
        print(f"{BOLD}[Ignition Dispatch]{RESET} Entering Bytecode Loop...")02-Programming-Languages/javascript/02-advanced-asynchronous-javascript-and-event-loop/02-libuv-and-browser-event-loop-differences/lab_exercise.py

        print(f"[{color}Thread-{threading.get_ident() % 1000:03d}{RESET}] "
              f"libuv Worker Pool: Processing {CYAN}{self.name}{RESET} "
              f"(Simulating blocking I/O: {self.duration_ms}ms)...")
        time.sleep(self.duration_ms / 1000.0)
        print(f"[{color}Thread-{threading.get_ident() % 1000:03d}{RESET}] "
              f"libuv Worker Pool: Completed {CYAN}{self.name}{RESET}. Queuing completion event to poll queue.")


class BrowserEventLoop:
    """
    Simulates the HTML5 Standard Browser Event Loop.
    Microtasks (Promises, MutationObserver) are fully drained after each macrotask
    and before rendering steps (requestAnimationFrame).
    """
    def __init__(self):
        self.macrotask_queue = deque()
        self.microtask_queue = deque()
        self.animation_queue = deque()
        self.current_time = 0

    def queue_macrotask(self, name: str, callback: Callable):
        self.macrotask_queue.append((name, callback))

    def queue_microtask(self, name: str, callback: Callable):
        self.microtask_queue.append((name, callback))

    def queue_raf(self, name: str, callback: Callable):
        self.animation_queue.append((name, callback))

    def drain_microtasks(self):
        """Microtask checkpoint: microtasks run to completion, including recursive ones."""
        while self.microtask_queue:
            name, cb = self.microtask_queue.popleft()
            print(f"    {GREEN}↳ [Microtask]{RESET} Executing: {name}")
            cb()

    def run_step(self):
        # 1. Run oldest macrotask
        if self.macrotask_queue:
            name, cb = self.macrotask_queue.popleft()
            print(f"  {YELLOW}[Macrotask]{RESET} Executing: {name}")
            cb()

        # 2. Microtask checkpoint
        self.drain_microtasks()

        # 3. Render steps (rAF)
        if self.animation_queue:
            print(f"  {MAGENTA}[Rendering/rAF Step]{RESET} Executing animation frame callbacks...")
            raf_tasks = list(self.animation_queue)
            self.animation_queue.clear()
            for name, cb in raf_tasks:
                print(f"    {MAGENTA}↳ [rAF]{RESET} Executing: {name}")
                cb()
            # Microtask checkpoint after rAF
            self.drain_microtasks()


class NodeLibuvEventLoop:
    """
    Simulates Node.js libuv Multi-phased Event Loop & Thread Pool.
    Phases: Timers -> Pending Callbacks -> Poll (I/O) -> Check (setImmediate) -> Close.
    Process.nextTick queue is drained between phases and after each tick callback.
    """
    def __init__(self, thread_pool_size: int = 4):
        self.timers_phase = deque()
        self.poll_phase = deque()
        self.check_phase = deque()
        self.next_tick_queue = deque()
        self.microtask_queue = deque()
        self.thread_pool = ThreadPoolExecutor(max_workers=thread_pool_size)

    def queue_next_tick(self, name: str, callback: Callable):
        self.next_tick_queue.append((name, callback))

    def queue_microtask(self, name: str, callback: Callable):
        self.microtask_queue.append((name, callback))

    def queue_timer(self, name: str, callback: Callable):
        self.timers_phase.append((name, callback))

    def queue_check(self, name: str, callback: Callable):
        self.check_phase.append((name, callback))

    def submit_io(self, io_task: LibuvAsyncWorker, completion_cb: Callable):
        """Offload blocking I/O to libuv thread pool, invoke callback in Poll phase upon finish."""
        def worker():
            io_task.execute()
            # Push completed callback to poll queue safely
            self.poll_phase.append((f"Poll::Callback({io_task.name})", completion_cb))
        self.thread_pool.submit(worker)

    def drain_ticks_and_microtasks(self):
        """
        Drains process.nextTick priority queue first, then Promise microtasks.
        Repeats until both queues are fully empty.
        """
        while self.next_tick_queue or self.microtask_queue:
            while self.next_tick_queue:
                name, cb = self.next_tick_queue.popleft()
                print(f"    {RED}↳ [process.nextTick]{RESET} Executing: {name}")
                cb()
            while self.microtask_queue:
                name, cb = self.microtask_queue.popleft()
                print(f"    {GREEN}↳ [Promise Microtask]{RESET} Executing: {name}")
                cb()

    def run_tick(self):
        print(f"\n{BOLD}{CYAN}--- [Phase 1: Timers (setTimeout)] ---{RESET}")
        while self.timers_phase:
            name, cb = self.timers_phase.popleft()
            print(f"  {YELLOW}[Timer]{RESET} Executing: {name}")
            cb()
            self.drain_ticks_and_microtasks()

        print(f"\n{BOLD}{CYAN}--- [Phase 2: Poll (I/O Callbacks)] ---{RESET}")
        while self.poll_phase:
            name, cb = self.poll_phase.popleft()
            print(f"  {BLUE}[Poll]{RESET} Executing: {name}")
            cb()
            self.drain_ticks_and_microtasks()

        print(f"\n{BOLD}{CYAN}--- [Phase 3: Check (setImmediate)] ---{RESET}")
        while self.check_phase:
            name, cb = self.check_phase.popleft()
            print(f"  {MAGENTA}[Check]{RESET} Executing: {name}")
            cb()
            self.drain_ticks_and_microtasks()

    def shutdown(self):
        self.thread_pool.shutdown(wait=True)


def simulate_browser():
    print(f"{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE}      PART 1: HTML5 BROWSER EVENT LOOP (Macrotask, Microtask, rAF)    {RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")

    browser = BrowserEventLoop()

    # Setup simulated tasks
    def on_timeout_1():
        print("    Body: Timeout 1 executed.")
        browser.queue_microtask("Promise.then inside Timeout 1", lambda: print("      Body: Promise settled."))

    def on_timeout_2():
        print("    Body: Timeout 2 executed.")

    def on_raf():
        print("    Body: Repainting DOM elements on next visual tick.")

    browser.queue_macrotask("setTimeout(1)", on_timeout_1)
    browser.queue_macrotask("setTimeout(2)", on_timeout_2)
    browser.queue_raf("requestAnimationFrame", on_raf)
    browser.queue_microtask("Initial Promise.resolve()", lambda: print("      Body: Top-level Promise resolved."))

    print(f"\n{YELLOW}Triggering Browser Loop Steps:{RESET}")
    # Drain initial script microtask
    print("Initial Microtask Checkpoint:")
    browser.drain_microtasks()

    # Step 1: Processes first macrotask + microtasks + rAF
    print("\n--- Event Loop Turn 1 ---")
    browser.run_step()

    # Step 2: Processes second macrotask
    print("\n--- Event Loop Turn 2 ---")
    browser.run_step()


def simulate_node_libuv():
    print(f"\n{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE}    PART 2: NODE.JS LIBUV EVENT LOOP (Multi-phase + Worker Threads)   {RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")

    node = NodeLibuvEventLoop(thread_pool_size=2)

    # 1. Dispatch asynchronous blocking work (fs.readFile, crypto)
    task1 = LibuvAsyncWorker("fs.readFile('large_dataset.json')", duration_ms=100)
    task2 = LibuvAsyncWorker("crypto.pbkdf2(password, salt)", duration_ms=150)

    node.submit_io(task1, completion_cb=lambda: node.queue_next_tick(
        "nextTick inside fs callback", lambda: print("      Body: Handled urgent metadata update.")
    ))
    node.submit_io(task2, completion_cb=lambda: print("      Body: Encryption key derived successfully."))

    # 2. Queue phase-specific tasks
    node.queue_timer("setTimeout(cb, 0)", lambda: node.queue_microtask(
        "Promise.resolve() in Timer", lambda: print("      Body: Resolved promise during Timers phase.")
    ))
    node.queue_check("setImmediate(cb)", lambda: print("      Body: Executed in Check phase immediate callback."))
    node.queue_next_tick("process.nextTick(initial)", lambda: print("      Body: High-priority tick processed."))

    print("\nStarting Node Loop Tick 1 (Initial Timers & Immediate Check):")
    # Drain initial global nextTick / microtasks before loop starts
    node.drain_ticks_and_microtasks()
    node.run_tick()

    # Wait for background thread pool I/O to finish
    print(f"\n{YELLOW}Waiting for libuv Worker Thread pool to complete async tasks...{RESET}")
    time.sleep(0.2)

    print("\nStarting Node Loop Tick 2 (Poll phase with incoming I/O events):")
    node.run_tick()

    node.shutdown()


def run_lab():
    simulate_browser()
    simulate_node_libuv()
    print(f"\n{BOLD}{GREEN}======================================================================{RESET}")
    print(f"{BOLD}{GREEN}   SIMULATION COMPLETE: ARCHITECTURAL DIFFERENCES DEMONSTRATED       {RESET}")
    print(f"{BOLD}{GREEN}======================================================================{RESET}\n")


if __name__ == "__main__":
    run_lab()
#!/usr/bin/env python3
"""
Lab Exercise: Libuv vs Browser Event Loop Differences
Simulates and contrasts the HTML5 Browser Event Loop model (Macrotask, Microtask, rAF)
against the Node.js / Libuv Multi-Phase Event Loop (Timers, Poll, Check) with Thread Pool offloading.
"""

import time
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, Optional

# Terminal ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
RED = "\033[31m"


class LibuvAsyncWorker:
    """Represents a simulated libuv thread pool background worker for blocking I/O."""
    def __init__(self, name: str, duration_ms: int):
        self.name = name
        self.duration_ms = duration_ms

    def execute(self):
        color = CYAN if "fs" in self.name else MAGENTA02-Programming-Languages/javascript/01-v8-engine-under-the-hood-and-execution-mechanics/02-hidden-classes-shapes-and-transitions/lab_exercise.py
#!/usr/bin/env python3
"""
Lab Exercise: V8 Hidden Classes (Shapes) and Transition Trees
Simulates:
1. Shape Transition Tree (Root -> Property Addition -> Branching).
2. Point-Object initialization order divergence.
3. Shape-sharing verification and memory layout overhead.
4. Inline Cache (IC) hit/miss lookup simulator utilizing cached property offsets.
"""

import sys
from typing import Dict, Any, List, Optional, Tuple

# Terminal ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
RED = "\033[31m"


class Shape:
    """
    Represents a V8 Hidden Class (internal Map / Shape).
    Forms a directed acyclic transition graph.
    """
    _id_counter = 0

    def __init__(self, parent: Optional['Shape'] = None, transition_prop: Optional[str] = None):
        self.id = Shape._id_counter
        Shape._id_counter += 1
        self.parent = parent
        self.transition_prop = transition_prop
        self.transitions: Dict[str, 'Shape'] = {}
        
        # Property descriptors: mapping from property name to contiguous index offset
        self.offsets: Dict[str, int] = {}
        if parent is not None:
            self.offsets = parent.offsets.copy()
            if transition_prop is not None:
                self.offsets[transition_prop] = len(parent.offsets)

    def transition(self, prop: str) -> 'Shape':
        """
        Retrieves or creates a transition for a new property.
        Ensures objects with identical property sequences share the same Shape node.
        """
        if prop not in self.transitions:
            self.transitions[prop] = Shape(parent=self, transition_prop=prop)
        return self.transitions[prop]

    def __repr__(self) -> str:
        keys = list(self.offsets.keys())
        return f"Shape[#{self.id} | props={keys}]"


# Root empty shape for all standard plain JavaScript objects ({})
GLOBAL_ROOT_SHAPE = Shape()


class JSObject:
    """
    Simulates a V8 JavaScript Object instance.
    Points to a Shape and stores values in an array-like fast property buffer.
    """
    def __init__(self, identifier: str):
        self.identifier = identifier
        self.shape: Shape = GLOBAL_ROOT_SHAPE
        self.properties: List[Any] = []

    def set_property(self, key: str, value: Any) -> None:
        """
        Sets a property on the object.
        Transitions the shape if the key is previously unseen.
        """
        if key in self.shape.offsets:
            # In-place update (fast-path: existing property slot)
            offset = self.shape.offsets[key]
            self.properties[offset] = value
        else:
            # Structural change: transition to successor shape
            prev_shape_id = self.shape.id
            self.shape = self.shape.transition(key)
            self.properties.append(value)
            print(f"  {CYAN}{self.identifier}{RESET}: Added '{key}={value}' -> "
                  f"Shape#{prev_shape_id} => {GREEN}Shape#{self.shape.id}{RESET}")

    def get_property(self, key: str) -> Any:
        """Retrieves a property using Shape metadata offset."""
        if key in self.shape.offsets:
            offset = self.shape.offsets[key]
            return self.properties[offset]
        raise AttributeError(f"Property '{key}' not found on {self.identifier}")


class SimulatedInlineCache:
    """
    Simulates a Monomorphic/Polymorphic Call-Site Property Access Inline Cache.
    """
    def __init__(self, name: str):
        self.name = name
        self.cached_shape: Optional[Shape] = None
        self.cached_offset: Optional[int] = None
        self.hits = 0
        self.misses = 0

    def read_property(self, obj: JSObject, key: str) -> Any:
        """Attempts fast property read via cached shape offset; falls back on miss."""
        if self.cached_shape is obj.shape and self.cached_offset is not None:
            self.hits += 1
            # Fast Path: Direct array dereference
            return obj.properties[self.cached_offset]

        # Slow Path: Cache Miss
        self.misses += 1
        if key in obj.shape.offsets:
            self.cached_shape = obj.shape
            self.cached_offset = obj.shape.offsets[key]
            return obj.properties[self.cached_offset]
        raise AttributeError(f"Cannot resolve '{key}' on {obj.identifier}")


def print_tree(node: Shape, prefix: str = "", is_tail: bool = True):
    """Recursively visualizes the Shape transition hierarchy."""
    node_str = f"{GREEN}Shape#{node.id}{RESET} (Prop: '{node.transition_prop or 'ROOT'}', Offsets: {dict(node.offsets)})"
    print(prefix + ("└── " if is_tail else "├── ") + node_str)
    
    children = list(node.transitions.values())
    for i, child in enumerate(children):
        is_last = (i == len(children) - 1)
        extension = "    " if is_tail else "│   "
        print_tree(child, prefix + extension, is_last)


def run_lab():
    print(f"{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE}        V8 HIDDEN CLASSES (SHAPES) & TRANSITIONS LAB                  {RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}\n")

    # 1. Instantiate objects with identical initialization order
    print(f"{BOLD}{YELLOW}[Step 1] Constructing Objects with Identical Property Order (x, y, z):{RESET}")
    obj_a = JSObject("objA")
    obj_a.set_property("x", 100)
    obj_a.set_property("y", 200)
    obj_a.set_property("z", 300)

    print()
    obj_b = JSObject("objB")
    obj_b.set_property("x", 10)
    obj_b.set_property("y", 20)
    obj_b.set_property("z", 30)

    print(f"\n{BOLD}Shape Sharing Verification:{RESET}")
    print(f"  objA.shape ID: {GREEN}{obj_a.shape.id}{RESET}")
    print(f"  objB.shape ID: {GREEN}{obj_b.shape.id}{RESET}")
    print(f"  Shared Shape Reference: {BOLD}{GREEN}{obj_a.shape is obj_b.shape}{RESET} (V8 memory optimization achieved)\n")

    # 2. Instantiate object with altered order (y, then x) -> Branching Transition
    print(f"{BOLD}{YELLOW}[Step 2] Constructing Object with Altered Property Order (y, x, z):{RESET}")
    obj_c = JSObject("objC")
    obj_c.set_property("y", 55)
    obj_c.set_property("x", 66)
    obj_c.set_property("z", 77)

    print(f"\n{BOLD}Divergent Shape Evaluation:{RESET}")
    print(f"  objA.shape ID: {GREEN}{obj_a.shape.id}{RESET} (Offsets: {obj_a.shape.offsets})")
    print(f"  objC.shape ID: {RED}{obj_c.shape.id}{RESET} (Offsets: {obj_c.shape.offsets})")
    print(f"  Shared Shape Reference: {BOLD}{RED}{obj_a.shape is obj_c.shape}{RESET} (Antipattern: Shape bifurcation occurred!)\n")

    # 3. Print complete Transition Tree
    print(f"{BOLD}{YELLOW}[Step 3] Visualizing Global Shape Transition Tree:{RESET}")
    print_tree(GLOBAL_ROOT_SHAPE)
    print()

    # 4. Inline Cache Simulation across shared vs unshared shapes
    print(f"{BOLD}{YELLOW}[Step 4] Inline Cache (IC) Benchmarking on Property 'x':{RESET}")
    ic = SimulatedInlineCache(name="load_x")

    # Accessing shared shape repeatedly
    print("Reading objA.x and objB.x (Monomorphic access pattern)...")
    for _ in range(5):
        ic.read_property(obj_a, "x")
        ic.read_property(obj_b, "x")
    print(f"  Status after objA & objB: Hits={GREEN}{ic.hits}{RESET}, Misses={RED}{ic.misses}{RESET}")

    # Accessing diverged shape (obj_c) triggers IC miss and re-caching
    print("Reading objC.x (Diverged shape access)...")
    ic.read_property(obj_c, "x")
    print(f"  Status after objC access: Hits={GREEN}{ic.hits}{RESET}, Misses={RED}{ic.misses}{RESET}")
    print(f"  Cached Shape is now: {MAGENTA}Shape#{ic.cached_shape.id}{RESET} with Offset={ic.cached_offset}\n")

    print(f"{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE}                           LAB SUMMARY                                {RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")
    print(f"  1. Identical order creates shared linear paths in the transition graph.")
    print(f"  2. Out-of-order assignments force graph bifurcation, creating duplicate metadata.")
    print(f"  3. Inline Caches perform optimal O(1) reads only when shapes remain monomorphic.")
    print(f"{BOLD}{BLUE}======================================================================{RESET}\n")


if __name__ == "__main__":
    run_lab()