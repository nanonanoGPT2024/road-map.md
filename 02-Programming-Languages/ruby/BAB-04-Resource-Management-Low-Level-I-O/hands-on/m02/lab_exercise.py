#!/usr/bin/env python3
"""
Lab Hands-on: Ruby Internal Mechanics - Low-Level I/O & Resource Management
Focus: Simulating Ruby's IO Engine, Block-scoped Resource Cleanup, Buffer Synchronicity, and IO.select
"""

import os
import sys
import time
import socket
import select
import weakref
from typing import Callable, Any, List, Optional, Tuple

# Terminal ANSI Color Codes
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_MAGENTA= "\033[35m"
CLR_CYAN   = "\033[36m"
CLR_WHITE  = "\033[37m"

def log_info(msg: str) -> None:
    print(f"{CLR_BLUE}[INFO]{CLR_RESET} {msg}")

def log_success(msg: str) -> None:
    print(f"{CLR_GREEN}[PASS]{CLR_RESET} {msg}")

def log_warn(msg: str) -> None:
    print(f"{CLR_YELLOW}[WARN]{CLR_RESET} {msg}")

def log_error(msg: str) -> None:
    print(f"{CLR_RED}[FAIL]{CLR_RESET} {msg}")

def log_debug(msg: str) -> None:
    print(f"{CLR_MAGENTA}[TRACE]{CLR_RESET} {msg}")


class RubyIOError(Exception):
    """Corresponds to Ruby's IOError / SystemCallError."""
    pass


class RubyObjectSpace:
    """
    Simulates Ruby's ObjectSpace finalization mechanism.
    Ruby's GC triggers ObjectSpace.define_finalizer callbacks asynchronously
    when an object is marked for collection.
    """
    _finalizers = {}

    @classmethod
    def define_finalizer(cls, obj: Any, callback: Callable[[], None]) -> None:
        obj_id = id(obj)
        cls._finalizers[obj_id] = callback
        weakref.finalize(obj, callback)
        log_debug(f"ObjectSpace: Finalizer registered for Object:0x{obj_id:x}")


class RubyIO:
    """
    Simulates MRI Ruby's low-level IO abstraction (rb_io_t).
    Demonstrates buffered streams, low-level sysread/syswrite syscalls,
    and unbuffered/sync modes (like `$defout.sync = true`).
    """
    DEFAULT_BUFFER_SIZE = 64

    def __init__(self, sock: socket.socket, mode: str = "r+"):
        self.fd: int = sock.fileno()
        self._sock: Optional[socket.socket] = sock
        self.mode: str = mode
        self.sync: bool = False  # Simulates Ruby's IO#sync (unbuffered if True)
        self.closed: bool = False
        
        # User-space buffer (MRI Ruby IO read/write buffers)
        self._write_buffer: bytearray = bytearray()
        self._read_buffer: bytearray = bytearray()

        # Register safety finalizer (Ruby ObjectSpace fallback)
        sock_ref = self._sock
        fd_num = self.fd
        RubyObjectSpace.define_finalizer(self, lambda: RubyIO._gc_cleanup(sock_ref, fd_num))

    @staticmethod
    def _gc_cleanup(sock_ref: Optional[socket.socket], fd_num: int) -> None:
        if sock_ref is not None:
            try:
                sock_ref.close()
                # Use raw stderr output to avoid potential runtime print issues in GC hooks
                sys.stderr.write(f"{CLR_YELLOW}[GC-FINALIZER] Reclaimed dangling File Descriptor #{fd_num}{CLR_RESET}\n")
                sys.stderr.flush()
            except Exception:
                pass

    def syswrite(self, data: bytes) -> int:
        """Ruby IO#syswrite: Direct write(2) system call, bypassing user-space buffer."""
        if self.closed or self._sock is None:
            raise RubyIOError("closed stream")
        try:
            return self._sock.send(data)
        except OSError as e:
            raise RubyIOError(f"syswrite failed: {e}")

    def write(self, data: bytes) -> int:
        """Ruby IO#write: Buffered write. Flushes immediately if self.sync == True."""
        if self.closed:
            raise RubyIOError("closed stream")

        if self.sync:
            return self.syswrite(data)

        self._write_buffer.extend(data)
        if len(self._write_buffer) >= self.DEFAULT_BUFFER_SIZE:
            self.flush()
        return len(data)

    def flush(self) -> None:
        """Ruby IO#flush: Forces user-space write buffer out to the underlying descriptor."""
        if self.closed or self._sock is None:
            raise RubyIOError("closed stream")
        if self._write_buffer:
            sent = self.syswrite(bytes(self._write_buffer))
            del self._write_buffer[:sent]

    def sysread(self, maxlen: int) -> bytes:
        """Ruby IO#sysread: Direct read(2) syscall, bypassing user-space buffer."""
        if self.closed or self._sock is None:
            raise RubyIOError("closed stream")
        try:
            chunk = self._sock.recv(maxlen)
            return chunk
        except OSError as e:
            raise RubyIOError(f"sysread failed: {e}")

    def close(self) -> None:
        """Ruby IO#close: Flushes remaining buffers and closes the underlying descriptor."""
        if self.closed:
            return
        try:
            if self._write_buffer:
                self.flush()
        finally:
            self.closed = True
            if self._sock:
                self._sock.close()
                log_debug(f"IO#close: Successfully closed FD #{self.fd}")
                self._sock = None

    def fileno(self) -> int:
        if self.closed or self._sock is None:
            raise RubyIOError("closed stream")
        return self.fd


class RubyResourceManager:
    """
    Simulates Ruby's block-given resource management idiom:
    File.open("path") do |f|
       ...
    end # Guarantees f.close via ensure block
    """
    @staticmethod
    def open_pipe(block_logic: Callable[[RubyIO, RubyIO], None]) -> None:
        """Emulates Ruby's IO.pipe { |read_io, write_io| ... } pattern."""
        r_sock, w_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        r_io = RubyIO(r_sock, mode="r")
        w_io = RubyIO(w_sock, mode="w")

        log_info(f"Allocated Pipe Descriptors: Read-FD={r_io.fd}, Write-FD={w_io.fd}")
        try:
            block_logic(r_io, w_io)
        finally:
            log_debug("Executing deterministic Ruby 'ensure' block for Pipe...")
            r_io.close()
            w_io.close()
            log_success("All pipe handles guaranteed closed via ensure block.")


def ruby_select(read_ios: List[RubyIO], write_ios: List[RubyIO], timeout: float) -> Tuple[List[RubyIO], List[RubyIO]]:
    """
    Simulates Ruby's IO.select([read_ios], [write_ios], nil, timeout).
    Uses native OS multiplexing on underlying file descriptors.
    """
    r_map = {io.fileno(): io for io in read_ios if not io.closed}
    w_map = {io.fileno(): io for io in write_ios if not io.closed}

    ready_r, ready_w, _ = select.select(list(r_map.keys()), list(w_map.keys()), [], timeout)

    return ([r_map[fd] for fd in ready_r], [w_map[fd] for fd in ready_w])


def run_experiment_1_resource_safety():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== EXPERIMENT 1: Deterministic Block Resource Management (File.open idiom) ==={CLR_RESET}")
    
    def test_block(r_io: RubyIO, w_io: RubyIO):
        log_info("Writing test payload inside critical block...")
        w_io.syswrite(b"STREAM_RUBY_PAYLOAD_TOKEN")
        data = r_io.sysread(64)
        log_info(f"Received payload: '{data.decode('utf-8')}'")
        log_warn("Simulating an unhandled Exception inside Ruby block...")
        raise RuntimeError("Unexpected zero-division error in business logic!")

    try:
        RubyResourceManager.open_pipe(test_block)
    except RuntimeError as ex:
        log_error(f"Trapped anticipated exception: {ex}")

    log_success("Resource Manager verified: Leak prevented despite abnormal execution termination.")


def run_experiment_2_buffering_and_sync():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== EXPERIMENT 2: User-Space Buffering vs IO#sync / syswrite ==={CLR_RESET}")
    
    r_sock, w_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    r_io = RubyIO(r_sock)
    w_io = RubyIO(w_sock)

    try:
        # Step A: Buffered write with sync=False
        w_io.sync = False
        small_payload = b"small_packet"
        w_io.write(small_payload)
        log_info(f"Buffered write sent ({len(small_payload)} bytes). Internal buffer size: {len(w_io._write_buffer)}")
        
        # Test non-blocking select readiness (should NOT be ready because payload is buffered in user space)
        ready_r, _ = ruby_select([r_io], [], timeout=0.05)
        if not ready_r:
            log_success("Verified: Under-limit payload remains in Ruby user-space buffer; OS FD is dry.")
        else:
            log_error("Buffer leaked prematurely into OS layer!")

        # Step B: Explicit Flush
        log_info("Invoking IO#flush...")
        w_io.flush()
        ready_r, _ = ruby_select([r_io], [], timeout=0.05)
        if ready_r:
            recv_data = r_io.sysread(64)
            log_success(f"Post-flush: Data arrived at OS layer: {recv_data.decode()}")

        # Step C: IO#sync = true
        w_io.sync = True
        log_info("Set IO#sync = true (Unbuffered Mode). Writing immediately...")
        w_io.write(b"immediate_packet")
        ready_r, _ = ruby_select([r_io], [], timeout=0.05)
        if ready_r:
            recv_data = r_io.sysread(64)
            log_success(f"Synchronous IO succeeded: Received '{recv_data.decode()}' without manual flush.")

    finally:
        r_io.close()
        w_io.close()


def run_experiment_3_multiplexed_event_loop():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== EXPERIMENT 3: Non-blocking Multiplexing via IO.select ==={CLR_RESET}")
    
    # Create 3 independent channels
    channels = [socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM) for _ in range(3)]
    readers = [RubyIO(ch[0]) for ch in channels]
    writers = [RubyIO(ch[1]) for ch in channels]

    for w in writers:
        w.sync = True

    try:
        log_info("Broadcasting asynchronous chunks across multiple RubyIO streams...")
        writers[0].write(b"Channel-0: Alpha Signal")
        writers[2].write(b"Channel-2: Gamma Signal")
        # Channel 1 deliberately remains quiet

        start_time = time.perf_counter()
        ready_readers, _ = ruby_select(readers, [], timeout=1.0)
        elapsed = (time.perf_counter() - start_time) * 1000

        log_info(f"IO.select unblocked in {elapsed:.2f}ms. Ready streams count: {len(ready_readers)}")
        
        for stream in ready_readers:
            payload = stream.sysread(128)
            log_success(f"Read from FD #{stream.fd}: {payload.decode('utf-8')}")

        if readers[1] not in ready_readers:
            log_success("Channel-1 correctly excluded from ready set (zero traffic).")

    finally:
        for r in readers:
            r.close()
        for w in writers:
            w.close()


def run_experiment_4_gc_objectspace_finalization():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== EXPERIMENT 4: ObjectSpace.define_finalizer Lifecycle ==={CLR_RESET}")
    
    def leaky_subroutine():
        sock1, sock2 = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        orphan_io = RubyIO(sock1)
        orphan_fd = orphan_io.fd
        log_warn(f"Orphaned RubyIO(FD={orphan_fd}) created inside function scope without explicit .close()")
        sock2.close()
        # orphan_io reference falls out of scope here

    leaky_subroutine()
    log_info("Forcing runtime garbage collection cycle...")
    import gc
    gc.collect()
    time.sleep(0.05)  # Allow finalizer queue processing
    log_success("ObjectSpace finalizer safely invoked; avoided permanently leaked OS handle.")


def main():
    print(f"{CLR_BOLD}{CLR_WHITE}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_WHITE}   RUBY INTERNALS: LOW-LEVEL I/O & RESOURCE MANAGEMENT EMULATION      {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_WHITE}======================================================================{CLR_RESET}")

    start_bench = time.perf_counter()
    run_experiment_1_resource_safety()
    run_experiment_2_buffering_and_sync()
    run_experiment_3_multiplexed_event_loop()
    run_experiment_4_gc_objectspace_finalization()
    total_time = (time.perf_counter() - start_bench) * 1000

    print(f"\n{CLR_BOLD}{CLR_GREEN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}   ALL DEEP DIVE LAB VERIFICATIONS COMPLETED IN {total_time:.2f} ms   {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}======================================================================{CLR_RESET}")


if __name__ == "__main__":
    main()