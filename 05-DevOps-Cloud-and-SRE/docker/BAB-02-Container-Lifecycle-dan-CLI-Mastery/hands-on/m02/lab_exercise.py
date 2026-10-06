#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Docker Container Lifecycle & CLI Architecture Simulation
Modul: BAB-02 Container Lifecycle dan CLI Mastery
Arsitektur Produksi: Simulasi State Machine Container, Event Engine, dan Signal Dispatcher
"""

import sys
import time
import json
import uuid
import random
from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# ANSI Color Codes for Production Terminal UX
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_DARK = "\033[40m"


class ContainerState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    EXITED = "exited"
    DEAD = "dead"


@dataclass
class ContainerConfig:
    image: str
    command: List[str]
    env_vars: Dict[str, str]
    memory_limit_mb: int
    cpu_shares: int
    restart_policy: str  # no, on-failure, always, unless-stopped


@dataclass
class ContainerMetadata:
    id: str
    name: str
    state: ContainerState
    pid: Optional[int]
    exit_code: int
    created_at: float
    started_at: Optional[float]
    finished_at: Optional[float]
    config: ContainerConfig
    oom_killed: bool = False
    restart_count: int = 0
    logs: List[str] = None

    def __post_init__(self):
        if self.logs is None:
            self.logs = []


class DockerEngineDaemon:
    """
    Simulasi containerd/dockerd high-performance engine yang mengelola
    state machine container lifecycle dan handling signal (SIGTERM, SIGKILL).
    """

    def __init__(self):
        self.containers: Dict[str, ContainerMetadata] = {}
        self.events_stream: List[str] = []
        self._next_pid = 12000

    def _log_event(self, action: str, container_id: str, details: str = ""):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        record = f"{timestamp} [ENGINE-EVENT] container={container_id[:12]} action={action} {details}".strip()
        self.events_stream.append(record)

    def docker_create(self, image: str, name: str, command: List[str], mem_limit: int = 512, restart_policy: str = "no") -> str:
        cid = str(uuid.uuid4()).replace("-", "")
        cfg = ContainerConfig(
            image=image,
            command=command,
            env_vars={"ENV": "production", "CONTAINER_RUNTIME": "containerd-v2"},
            memory_limit_mb=mem_limit,
            cpu_shares=1024,
            restart_policy=restart_policy
        )
        container = ContainerMetadata(
            id=cid,
            name=name,
            state=ContainerState.CREATED,
            pid=None,
            exit_code=0,
            created_at=time.time(),
            started_at=None,
            finished_at=None,
            config=cfg
        )
        self.containers[cid] = container
        self._log_event("create", cid, f"image={image} name={name}")
        return cid

    def docker_start(self, identifier: str) -> bool:
        container = self._resolve(identifier)
        if not container:
            return False

        if container.state not in (ContainerState.CREATED, ContainerState.EXITED):
            print(f"{TermColor.RED}[ERROR] Container {container.name} is not in runnable state (current: {container.state.value}){TermColor.RESET}")
            return False

        self._next_pid += 1
        container.pid = self._next_pid
        container.state = ContainerState.RUNNING
        container.started_at = time.time()
        container.exit_code = 0
        container.logs.append(f"[{time.strftime('%X')}] Process spawned with PID {container.pid}: {' '.join(container.config.command)}")
        self._log_event("start", container.id, f"pid={container.pid}")
        return True

    def docker_pause(self, identifier: str) -> bool:
        container = self._resolve(identifier)
        if not container:
            return False
        if container.state != ContainerState.RUNNING:
            print(f"{TermColor.RED}[ERROR] Cannot pause container {container.name} in state {container.state.value}{TermColor.RESET}")
            return False
        
        container.state = ContainerState.PAUSED
        container.logs.append(f"[{time.strftime('%X')}] cgroup freezer applied (SIGSTOP suspended)")
        self._log_event("pause", container.id, "cgroup.freezer=FROZEN")
        return True

    def docker_unpause(self, identifier: str) -> bool:
        container = self._resolve(identifier)
        if not container:
            return False
        if container.state != ContainerState.PAUSED:
            print(f"{TermColor.RED}[ERROR] Cannot unpause container {container.name} in state {container.state.value}{TermColor.RESET}")
            return False
        
        container.state = ContainerState.RUNNING
        container.logs.append(f"[{time.strftime('%X')}] cgroup freezer unfrozen (SIGCONT resumed)")
        self._log_event("unpause", container.id, "cgroup.freezer=THAWED")
        return True

    def docker_stop(self, identifier: str, timeout_seconds: int = 2) -> bool:
        container = self._resolve(identifier)
        if not container:
            return False
        if container.state not in (ContainerState.RUNNING, ContainerState.PAUSED):
            print(f"{TermColor.YELLOW}[WARN] Container is already stopped or dead.{TermColor.RESET}")
            return False

        print(f"{TermColor.CYAN}==> Sending SIGTERM (graceful shutdown) to PID {container.pid}...{TermColor.RESET}")
        container.logs.append(f"[{time.strftime('%X')}] Signal dispatched: SIGTERM (15)")
        time.sleep(min(timeout_seconds * 0.4, 0.8))

        # Graceful handling check (exit 143 = 128 + 15)
        container.state = ContainerState.EXITED
        container.finished_at = time.time()
        container.exit_code = 143
        container.pid = None
        container.logs.append(f"[{time.strftime('%X')}] Process terminated gracefully with code 143 (SIGTERM)")
        self._log_event("stop", container.id, "exit_code=143")
        return True

    def docker_kill(self, identifier: str, signal: str = "SIGKILL") -> bool:
        container = self._resolve(identifier)
        if not container:
            return False
        if container.state not in (ContainerState.RUNNING, ContainerState.PAUSED):
            print(f"{TermColor.RED}[ERROR] Cannot kill inactive container.{TermColor.RESET}")
            return False

        print(f"{TermColor.RED}==> Force terminating via {signal} (9) immediately...{TermColor.RESET}")
        container.state = ContainerState.EXITED
        container.finished_at = time.time()
        container.exit_code = 137  # 128 + 9
        container.pid = None
        container.logs.append(f"[{time.strftime('%X')}] SIGKILL received. Process hard-terminated. Exit Code: 137")
        self._log_event("kill", container.id, "signal=SIGKILL exit_code=137")
        return True

    def docker_oom_simulate(self, identifier: str) -> bool:
        """Simulasi OOMKilled (Out of Memory) di mana cgroup memotong proses (exit 137)."""
        container = self._resolve(identifier)
        if not container or container.state != ContainerState.RUNNING:
            print(f"{TermColor.RED}[ERROR] Container must be running to trigger OOM condition.{TermColor.RESET}")
            return False

        print(f"{TermColor.MAGENTA}==> Memory consumption exceeded cgroup limit ({container.config.memory_limit_mb}MB)!{TermColor.RESET}")
        print(f"{TermColor.RED}==> Kernel OOM Killer triggered: terminating PID {container.pid}{TermColor.RESET}")
        container.oom_killed = True
        container.state = ContainerState.EXITED
        container.exit_code = 137
        container.finished_at = time.time()
        container.pid = None
        container.logs.append(f"[{time.strftime('%X')}] Kernel OOM Killer invoked: cgroup memory exhausted")
        self._log_event("die", container.id, "oom_killed=true exit_code=137")

        if container.config.restart_policy in ("always", "on-failure"):
            print(f"{TermColor.YELLOW}==> Auto-restart triggered by policy '{container.config.restart_policy}'...{TermColor.RESET}")
            container.restart_count += 1
            container.state = ContainerState.RESTARTING
            self._log_event("restart", container.id, f"attempt={container.restart_count}")
            time.sleep(0.5)
            self.docker_start(container.id)
        return True

    def docker_rm(self, identifier: str, force: bool = False) -> bool:
        container = self._resolve(identifier)
        if not container:
            return False

        if container.state == ContainerState.RUNNING and not force:
            print(f"{TermColor.RED}[ERROR] You cannot remove a running container {container.name}. Stop the container before attempting removal or use -f/--force.{TermColor.RESET}")
            return False

        if container.state == ContainerState.RUNNING and force:
            self.docker_kill(container.id)

        del self.containers[container.id]
        self._log_event("destroy", container.id, f"name={container.name}")
        print(f"{TermColor.GREEN}[OK] Removed container: {container.name} ({container.id[:12]}){TermColor.RESET}")
        return True

    def docker_ps(self, all_containers: bool = False):
        print(f"\n{TermColor.BOLD}{TermColor.CYAN}{'CONTAINER ID':<14} {'IMAGE':<18} {'COMMAND':<22} {'CREATED':<14} {'STATUS':<24} {'PORTS/POLICY':<16} {'NAMES'}{TermColor.RESET}")
        print("-" * 115)
        now = time.time()
        displayed = 0
        for cid, c in self.containers.items():
            if not all_containers and c.state != ContainerState.RUNNING:
                continue

            displayed += 1
            age = f"{int(now - c.created_at)}s ago"
            cmd_str = f"\"{c.config.command[0]}\""[:20]

            if c.state == ContainerState.RUNNING:
                status_color = TermColor.GREEN
                status_str = f"Up {int(now - (c.started_at or now))} seconds"
            elif c.state == ContainerState.PAUSED:
                status_color = TermColor.YELLOW
                status_str = "Up (Paused)"
            elif c.state == ContainerState.RESTARTING:
                status_color = TermColor.YELLOW
                status_str = f"Restarting ({c.restart_count})"
            elif c.state == ContainerState.EXITED:
                status_color = TermColor.RED if c.exit_code != 0 else TermColor.WHITE
                status_str = f"Exited ({c.exit_code}) {'[OOM]' if c.oom_killed else ''}"
            else:
                status_color = TermColor.DIM
                status_str = c.state.value.capitalize()

            print(f"{cid[:12]:<14} {c.config.image:<18} {cmd_str:<22} {age:<14} {status_color}{status_str:<24}{TermColor.RESET} {c.config.restart_policy:<16} {c.name}")

        if displayed == 0:
            print(f"{TermColor.DIM}(No containers to display. Run 'create' or use flag '-a' for all){TermColor.RESET}")
        print()

    def docker_inspect(self, identifier: str):
        container = self._resolve(identifier)
        if not container:
            return
        dump_data = asdict(container)
        dump_data["state"] = container.state.value
        print(f"\n{TermColor.BOLD}{TermColor.BLUE}=== [DOCKER INSPECT: {container.name}] ==={TermColor.RESET}")
        print(json.dumps([dump_data], indent=2))
        print()

    def docker_logs(self, identifier: str):
        container = self._resolve(identifier)
        if not container:
            return
        print(f"\n{TermColor.BOLD}{TermColor.YELLOW}--- LOGS FOR {container.name} ({container.id[:12]}) ---{TermColor.RESET}")
        for log in container.logs:
            print(f"{TermColor.WHITE}{log}{TermColor.RESET}")
        print(f"{TermColor.DIM}--- End of container logs ---{TermColor.RESET}\n")

    def _resolve(self, query: str) -> Optional[ContainerMetadata]:
        query = query.strip()
        # Direct match by full or short ID
        for cid, c in self.containers.items():
            if cid.startswith(query) or c.name == query:
                return c
        print(f"{TermColor.RED}[ERROR] No such container: '{query}'{TermColor.RESET}")
        return None


def print_banner():
    banner = f"""{TermColor.CYAN}{TermColor.BOLD}
========================================================================================
       DOCKER CONTAINER LIFECYCLE & CLI MASTERY - INTERACTIVE LAB (BAB-02)
  Engine: Mocked containerd/dockerd Engine with High-Fidelity Signal & State Dispatcher
========================================================================================{TermColor.RESET}
Commands available:
  {TermColor.GREEN}1. run{TermColor.RESET} <image> <name> [cmd]   : Atomic Create + Start container
  {TermColor.GREEN}2. create{TermColor.RESET} <img > <name> [cmd] : Initialize container into CREATED state
  {TermColor.GREEN}3. start{TermColor.RESET} <id|name>            : Transition container from CREATED/EXITED to RUNNING
  {TermColor.YELLOW}4. pause{TermColor.RESET} <id|name>            : Freeze processes using cgroups freezer (PAUSED)
  {TermColor.YELLOW}5. unpause{TermColor.RESET} <id|name>          : Unfreeze processes (RUNNING)
  {TermColor.RED}6. stop{TermColor.RESET} <id|name>             : Graceful shutdown (SIGTERM -> exit 143)
  {TermColor.RED}7. kill{TermColor.RESET} <id|name>             : Immediate kill (SIGKILL -> exit 137)
  {TermColor.MAGENTA}8. oom{TermColor.RESET} <id|name>              : Simulate OOM (Out-of-Memory) eviction
  {TermColor.WHITE}9. ps{TermColor.RESET} [-a]                   : List containers (active or all)
  {TermColor.WHITE}10. logs{TermColor.RESET} <id|name>            : Fetch stdout/stderr buffer
  {TermColor.WHITE}11. inspect{TermColor.RESET} <id|name>         : Deep JSON inspection (metadata & state)
  {TermColor.RED}12. rm{TermColor.RESET} [-f] <id|name>          : Remove container from storage
  {TermColor.CYAN}13. events{TermColor.RESET}                   : View engine audit event log stream
  {TermColor.DIM}14. exit / quit{TermColor.RESET}              : Terminate lab simulation
"""
    print(banner)


def run_interactive_lab():
    engine = DockerEngineDaemon()

    # Pre-populate sample enterprise workloads
    cid1 = engine.docker_create(image="nginx:alpine", name="web-gateway", command=["nginx", "-g", "daemon off;"], mem_limit=256, restart_policy="always")
    engine.docker_start(cid1)

    cid2 = engine.docker_create(image="postgres:15-alpine", name="core-database", command=["postgres"], mem_limit=1024, restart_policy="on-failure")
    engine.docker_start(cid2)

    cid3 = engine.docker_create(image="batch-worker:latest", name="ml-processor", command=["python", "worker.py"], mem_limit=512, restart_policy="no")

    print_banner()
    print(f"{TermColor.BOLD}{TermColor.GREEN}[INIT] Initialized 3 baseline enterprise containers.{TermColor.RESET}")
    engine.docker_ps(all_containers=True)

    while True:
        try:
            raw_input = input(f"{TermColor.BOLD}{TermColor.CYAN}docker-cli # {TermColor.RESET}").strip()
            if not raw_input:
                continue

            parts = raw_input.split()
            cmd = parts[0].lower()
            args = parts[1:]

            if cmd in ("exit", "quit", "q"):
                print(f"{TermColor.GREEN}Shutting down interactive lab daemon. All virtual namespaces destroyed.{TermColor.RESET}")
                sys.exit(0)

            elif cmd == "ps":
                all_flag = "-a" in args or "--all" in args
                engine.docker_ps(all_containers=all_flag)

            elif cmd == "run":
                if len(args) < 2:
                    print(f"{TermColor.YELLOW}Usage: run <image> <name> [cmd...]{TermColor.RESET}")
                    continue
                img = args[0]
                name = args[1]
                command = args[2:] if len(args) > 2 else ["sh", "-c", "echo Ready && sleep 3600"]
                cid = engine.docker_create(image=img, name=name, command=command)
                if engine.docker_start(cid):
                    print(f"{TermColor.GREEN}[OK] Container {name} ({cid[:12]}) successfully running.{TermColor.RESET}")

            elif cmd == "create":
                if len(args) < 2:
                    print(f"{TermColor.YELLOW}Usage: create <image> <name> [cmd...]{TermColor.RESET}")
                    continue
                img = args[0]
                name = args[1]
                command = args[2:] if len(args) > 2 else ["entrypoint.sh"]
                cid = engine.docker_create(image=img, name=name, command=command)
                print(f"{TermColor.GREEN}[OK] Created container {cid[:12]} ({name}) in CREATED state.{TermColor.RESET}")

            elif cmd == "start":
                if not args:
                    print(f"{TermColor.YELLOW}Usage: start <id|name>{TermColor.RESET}")
                    continue
                if engine.docker_start(args[0]):
                    print(f"{TermColor.GREEN}[OK] Container started successfully.{TermColor.RESET}")

            elif cmd == "pause":
                if not args:
                    print(f"{TermColor.YELLOW}Usage: pause <id|name>{TermColor.RESET}")
                    continue
                if engine.docker_pause(args[0]):
                    print(f"{TermColor.YELLOW}[OK] Container processes paused via cgroup freezer.{TermColor.RESET}")

            elif cmd == "unpause":
                if not args:
                    print(f"{TermColor.YELLOW}Usage: unpause <id|name>{TermColor.RESET}")
                    continue
                if engine.docker_unpause(args[0]):
                    print(f"{TermColor.GREEN}[OK] Container processes resumed.{TermColor.RESET}")

            elif cmd == "stop":
                if not args:
                    print(f"{TermColor.YELLOW}Usage: stop <id|name>{TermColor.RESET}")
                    continue
                engine.docker_stop(args[0])

            elif cmd == "kill":
                if not args:
                    print(f"{TermColor.YELLOW}Usage: kill <id|name>{TermColor.RESET}")
                    continue
                engine.docker_kill(args[0])

            elif cmd == "oom":
                if not args:
                    print(f"{TermColor.YELLOW}Usage: oom <id|name>{TermColor.RESET}")
                    continue
                engine.docker_oom_simulate(args[0])

            elif cmd == "logs":
                if not args:
                    print(f"{TermColor.YELLOW}Usage: logs <id|name>{TermColor.RESET}")
                    continue
                engine.docker_logs(args[0])

            elif cmd == "inspect":
                if not args:
                    print(f"{TermColor.YELLOW}Usage: inspect <id|name>{TermColor.RESET}")
                    continue
                engine.docker_inspect(args[0])

            elif cmd == "rm":
                force = "-f" in args or "--force" in args
                clean_args = [a for a in args if not a.startswith("-")]
                if not clean_args:
                    print(f"{TermColor.YELLOW}Usage: rm [-f] <id|name>{TermColor.RESET}")
                    continue
                engine.docker_rm(clean_args[0], force=force)

            elif cmd == "events":
                print(f"\n{TermColor.BOLD}{TermColor.MAGENTA}=== ENGINE REAL-TIME EVENT STREAM ==={TermColor.RESET}")
                for evt in engine.events_stream[-20:]:
                    print(f"{TermColor.CYAN}{evt}{TermColor.RESET}")
                print()

            elif cmd in ("help", "?"):
                print_banner()

            else:
                print(f"{TermColor.RED}Unknown command: '{cmd}'. Type 'help' for instruction list.{TermColor.RESET}")

        except (KeyboardInterrupt, EOFError):
            print(f"\n{TermColor.YELLOW}Exiting simulation session...{TermColor.RESET}")
            break
        except Exception as ex:
            print(f"{TermColor.RED}[INTERNAL ERROR] {ex}{TermColor.RESET}")


if __name__ == "__main__":
    run_interactive_lab()
