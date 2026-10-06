#!/usr/bin/env python3
"""
Lab Exercise: Docker Container Lifecycle & CLI Mastery Simulation
BAB-02: Container Lifecycle dan CLI Mastery
Simulasi teknis interaktif berbasis state-machine container dengan CLI interface & ANSI color output.
"""

import sys
import time
import uuid
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

# ANSI Color Codes
class Color:
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
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"

class ContainerState(Enum):
    CREATED = "Created"
    RUNNING = "Running"
    PAUSED = "Paused"
    RESTARTING = "Restarting"
    EXITED = "Exited"
    DEAD = "Dead"

@dataclass
class Container:
    id: str
    name: str
    image: str
    command: str
    created_at: float
    state: ContainerState = ContainerState.CREATED
    pid: Optional[int] = None
    exit_code: int = 0
    ports: Dict[str, str] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)

    def short_id(self) -> str:
        return self.id[:12]

class DockerDaemonSimulator:
    def __init__(self):
        self.containers: Dict[str, Container] = {}
        self.next_pid: int = 1000

    def create(self, image: str, command: str, name: Optional[str] = None,
               ports: Optional[Dict[str, str]] = None, env: Optional[Dict[str, str]] = None) -> Container:
        cid = uuid.uuid4().hex
        cname = name if name else f"vibrant_{cid[:6]}"
        
        # Check name uniqueness
        for c in self.containers.values():
            if c.name == cname:
                raise ValueError(f"Conflict. The container name \"{cname}\" is already in use by container \"{c.short_id()}\".")

        container = Container(
            id=cid,
            name=cname,
            image=image,
            command=command,
            created_at=time.time(),
            state=ContainerState.CREATED,
            ports=ports or {},
            env=env or {}
        )
        container.logs.append(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ')}] Container created from image '{image}'")
        self.containers[cid] = container
        return container

    def start(self, identifier: str) -> Container:
        c = self._resolve_container(identifier)
        if c.state == ContainerState.RUNNING:
            return c
        if c.state in [ContainerState.PAUSED, ContainerState.DEAD]:
            raise RuntimeError(f"Cannot start container in state {c.state.value}")

        self.next_pid += 1
        c.pid = self.next_pid
        c.state = ContainerState.RUNNING
        c.exit_code = 0
        c.logs.append(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ')}] Started main process PID {c.pid}: {c.command}")
        return c

    def run(self, image: str, command: str, name: Optional[str] = None,
            ports: Optional[Dict[str, str]] = None, env: Optional[Dict[str, str]] = None) -> Container:
        c = self.create(image, command, name, ports, env)
        return self.start(c.id)

    def pause(self, identifier: str) -> Container:
        c = self._resolve_container(identifier)
        if c.state != ContainerState.RUNNING:
            raise RuntimeError(f"Cannot pause container in state {c.state.value} (must be Running)")
        c.state = ContainerState.PAUSED
        c.logs.append(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ')}] SIGSTOP / cgroup freezer: process group paused")
        return c

    def unpause(self, identifier: str) -> Container:
        c = self._resolve_container(identifier)
        if c.state != ContainerState.PAUSED:
            raise RuntimeError(f"Cannot unpause container in state {c.state.value} (must be Paused)")
        c.state = ContainerState.RUNNING
        c.logs.append(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ')}] SIGCONT / cgroup thawed: process group resumed")
        return c

    def stop(self, identifier: str, timeout_sec: int = 10) -> Container:
        c = self._resolve_container(identifier)
        if c.state == ContainerState.EXITED:
            return c
        if c.state == ContainerState.PAUSED:
            raise RuntimeError("Cannot stop a paused container. Unpause first.")
        
        c.logs.append(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ')}] Sending SIGTERM to PID {c.pid} (grace period: {timeout_sec}s)")
        c.logs.append(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ')}] Container stopped gracefully. Exit status: 0")
        c.state = ContainerState.EXITED
        c.pid = None
        c.exit_code = 0
        return c

    def kill(self, identifier: str, signal: str = "SIGKILL") -> Container:
        c = self._resolve_container(identifier)
        if c.state in [ContainerState.EXITED, ContainerState.CREATED]:
            return c
        c.logs.append(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ')}] Forced termination with {signal} to PID {c.pid}")
        c.state = ContainerState.EXITED
        c.pid = None
        c.exit_code = 137
        return c

    def restart(self, identifier: str) -> Container:
        c = self._resolve_container(identifier)
        if c.state == ContainerState.RUNNING:
            self.stop(c.id, timeout_sec=2)
        c.state = ContainerState.RESTARTING
        time.sleep(0.3)
        return self.start(c.id)

    def remove(self, identifier: str, force: bool = False) -> str:
        c = self._resolve_container(identifier)
        if c.state == ContainerState.RUNNING and not force:
            raise RuntimeError(f"You cannot remove a running container {c.short_id()}. Stop the container before attempting removal or force remove.")
        del self.containers[c.id]
        return c.id

    def list_containers(self, all_containers: bool = False) -> List[Container]:
        if all_containers:
            return list(self.containers.values())
        return [c for c in self.containers.values() if c.state in [ContainerState.RUNNING, ContainerState.PAUSED, ContainerState.RESTARTING]]

    def inspect(self, identifier: str) -> dict:
        c = self._resolve_container(identifier)
        return {
            "Id": c.id,
            "Created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(c.created_at)),
            "Path": c.command.split()[0] if c.command else "",
            "Args": c.command.split()[1:] if c.command else [],
            "State": {
                "Status": c.state.value.lower(),
                "Running": c.state == ContainerState.RUNNING,
                "Paused": c.state == ContainerState.PAUSED,
                "Restarting": c.state == ContainerState.RESTARTING,
                "ExitCode": c.exit_code,
                "Pid": c.pid or 0
            },
            "Image": c.image,
            "Name": f"/{c.name}",
            "NetworkSettings": {
                "Ports": {f"{k}/tcp": [{"HostIp": "0.0.0.0", "HostPort": v}] for k, v in c.ports.items()}
            },
            "Config": {
                "Env": [f"{k}={v}" for k, v in c.env.items()],
                "Cmd": c.command.split()
            }
        }

    def _resolve_container(self, identifier: str) -> Container:
        # Match by full ID
        if identifier in self.containers:
            return self.containers[identifier]
        # Match by prefix
        matches = [c for c in self.containers.values() if c.id.startswith(identifier) or c.name == identifier]
        if not matches:
            raise KeyError(f"No such container: {identifier}")
        if len(matches) > 1:
            raise ValueError(f"Ambiguous container identifier: '{identifier}'")
        return matches[0]

def print_header(title: str):
    width = 75
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} {title.center(width - 2)} {Color.RESET}")

def print_state_badge(state: ContainerState) -> str:
    if state == ContainerState.RUNNING:
        return f"{Color.GREEN}{Color.BOLD}● RUNNING{Color.RESET}"
    elif state == ContainerState.PAUSED:
        return f"{Color.YELLOW}{Color.BOLD}⏸ PAUSED{Color.RESET}"
    elif state == ContainerState.CREATED:
        return f"{Color.CYAN}{Color.BOLD}○ CREATED{Color.RESET}"
    elif state == ContainerState.EXITED:
        return f"{Color.DIM}{Color.WHITE}■ EXITED{Color.RESET}"
    elif state == ContainerState.RESTARTING:
        return f"{Color.MAGENTA}{Color.BOLD}↻ RESTARTING{Color.RESET}"
    return f"{Color.RED}{Color.BOLD}✖ DEAD{Color.RESET}"

def print_ps_table(containers: List[Container]):
    if not containers:
        print(f"{Color.DIM}(No containers found matching criteria){Color.RESET}")
        return

    header = f"{Color.BOLD}{'CONTAINER ID':<14} {'IMAGE':<18} {'COMMAND':<22} {'STATUS':<20} {'PORTS':<18} {'NAMES'}{Color.RESET}"
    print(header)
    print("-" * 105)

    for c in containers:
        cid = c.short_id()
        img = (c.image[:16] + "..") if len(c.image) > 18 else c.image
        cmd = f"\"{c.command[:18]}..\"" if len(c.command) > 20 else f"\"{c.command}\""
        
        status_str = f"Up (PID {c.pid})" if c.state == ContainerState.RUNNING else (
            "Paused" if c.state == ContainerState.PAUSED else f"Exited ({c.exit_code})"
        )
        status_colored = f"{print_state_badge(c.state)} {Color.DIM}{status_str}{Color.RESET}"
        
        port_repr = ", ".join(f"0.0.0.0:{v}->{k}" for k, v in c.ports.items()) if c.ports else ""
        if len(port_repr) > 16:
            port_repr = port_repr[:14] + ".."

        print(f"{Color.CYAN}{cid:<14}{Color.RESET} {img:<18} {cmd:<22} {status_colored:<30} {port_repr:<18} {Color.BOLD}{c.name}{Color.RESET}")

def print_lifecycle_diagram():
    diagram = f"""
{Color.BOLD}{Color.YELLOW}=== SIKLUS HIDUP CONTAINER (DOCKER LIFECYCLE STATE MACHINE) ==={Color.RESET}
                               +-------------+
                               |    IMAGE    |
                               +------+------+
                                      |
                           docker create (cgroup & ns initialized)
                                      |
                                      v
                               +-------------+
            +----------------->|   CREATED   |
            |                  +------+------+
            |                         |
      docker restart             docker start / run
            |                         |
            |                         v
            |                  +-------------+ <---- docker unpause ---+
            |  +-------------->|   RUNNING   |                         |
            |  |  (PID alive)  +---+-----+---+ ----- docker pause ---->+
            |  |                   |     |                         [PAUSED]
            |  |      docker stop  |     | docker kill / OOM (137)
            |  |        (SIGTERM)  |     | (SIGKILL)
            |  |                   v     v
            |  |               +-------------+
            |  +-- docker start|   EXITED    |
            |                  +------+------+
            |                         |
            +-------------------------+ docker rm (storage removed)
    """
    print(diagram)

def run_automated_lifecycle_demo(engine: DockerDaemonSimulator):
    print_header("DEMO OTOMATIS: DOCKER CONTAINER LIFECYCLE (CLI MASTERY)")
    print_lifecycle_diagram()

    print(f"\n{Color.BOLD}[LANGKAH 1] docker create & inspect initial state{Color.RESET}")
    c1 = engine.create(image="nginx:alpine", command="nginx -g 'daemon off;'", name="web-gateway", ports={"80": "8080"})
    print(f"Container Created: {Color.GREEN}{c1.name}{Color.RESET} (ID: {c1.short_id()})")
    print(f"Status saat ini: {print_state_badge(c1.state)}")
    time.sleep(0.5)

    print(f"\n{Color.BOLD}[LANGKAH 2] docker start & ps{Color.RESET}")
    engine.start(c1.id)
    print(f"Status setelah start: {print_state_badge(c1.state)} (PID Assigned: {Color.BOLD}{c1.pid}{Color.RESET})")
    print_ps_table(engine.list_containers(all_containers=False))
    time.sleep(0.5)

    print(f"\n{Color.BOLD}[LANGKAH 3] docker run (create + start background service){Color.RESET}")
    c2 = engine.run(image="redis:7-alpine", command="redis-server --protected-mode no", name="cache-db", ports={"6379": "6379"})
    print(f"Spawning container baru via run: {Color.GREEN}{c2.name}{Color.RESET} (ID: {c2.short_id()})")
    print_ps_table(engine.list_containers(all_containers=False))
    time.sleep(0.5)

    print(f"\n{Color.BOLD}[LANGKAH 4] docker pause & freeze process (cgroup freezer){Color.RESET}")
    engine.pause(c1.id)
    print(f"Container '{c1.name}' di-pause:")
    print_ps_table(engine.list_containers(all_containers=True))
    time.sleep(0.5)

    print(f"\n{Color.BOLD}[LANGKAH 5] docker unpause & resume{Color.RESET}")
    engine.unpause(c1.id)
    print(f"Container '{c1.name}' di-unpause:")
    print_ps_table(engine.list_containers(all_containers=True))
    time.sleep(0.5)

    print(f"\n{Color.BOLD}[LANGKAH 6] docker stop (Graceful SIGTERM -> SIGKILL){Color.RESET}")
    engine.stop(c1.id, timeout_sec=10)
    print(f"Container '{c1.name}' distop:")
    print_ps_table(engine.list_containers(all_containers=True))
    time.sleep(0.5)

    print(f"\n{Color.BOLD}[LANGKAH 7] docker kill (Forced SIGKILL exit code 137){Color.RESET}")
    engine.kill(c2.id)
    print(f"Container '{c2.name}' di-kill seketika:")
    print_ps_table(engine.list_containers(all_containers=True))
    time.sleep(0.5)

    print(f"\n{Color.BOLD}[LANGKAH 8] docker logs inspection{Color.RESET}")
    print(f"{Color.YELLOW}--- Logs for {c1.name} ---{Color.RESET}")
    for entry in c1.logs:
        print(f"  {Color.DIM}>> {entry}{Color.RESET}")

    print(f"{Color.YELLOW}--- Logs for {c2.name} ---{Color.RESET}")
    for entry in c2.logs:
        print(f"  {Color.DIM}>> {entry}{Color.RESET}")
    time.sleep(0.5)

    print(f"\n{Color.BOLD}[LANGKAH 9] docker rm & cleanup{Color.RESET}")
    rm_id1 = engine.remove(c1.id)
    rm_id2 = engine.remove(c2.id)
    print(f"Removed containers: {rm_id1[:12]}, {rm_id2[:12]}")
    print(f"Active containers post cleanup:")
    print_ps_table(engine.list_containers(all_containers=True))

def interactive_cli_shell(engine: DockerDaemonSimulator):
    print_header("INTERACTIVE DOCKER CLI SIMULATION REPL")
    print(f"{Color.CYAN}Ketik perintah docker seperti biasa ({Color.BOLD}docker run, ps, stop, start, pause, unpause, rm, logs, inspect{Color.CYAN}) atau 'exit' / 'demo'.{Color.RESET}\n")

    while True:
        try:
            line = input(f"{Color.GREEN}user@docker-host{Color.RESET}:{Color.BLUE}~{Color.RESET}$ ").strip()
            if not line:
                continue

            parts = line.split()
            if parts[0] == "exit" or parts[0] == "quit":
                print(f"{Color.YELLOW}Exiting Docker Lifecycle CLI REPL. Terima kasih!{Color.RESET}")
                break

            if parts[0] == "help":
                print(f"""
{Color.BOLD}Available Commands in Simulation:{Color.RESET}
  docker run -d --name <name> -p <host:cont> <image> <cmd>
  docker create --name <name> <image> <cmd>
  docker start <id/name>
  docker stop <id/name>
  docker pause <id/name>
  docker unpause <id/name>
  docker restart <id/name>
  docker kill <id/name>
  docker rm [-f] <id/name>
  docker ps [-a]
  docker logs <id/name>
  docker inspect <id/name>
  demo              -> Jalankan skenario demonstrasi otomatis
  lifecycle         -> Cetak diagram siklus hidup ASCII
  exit              -> Keluar
""")
                continue

            if parts[0] == "lifecycle":
                print_lifecycle_diagram()
                continue

            if parts[0] == "demo":
                run_automated_lifecycle_demo(engine)
                continue

            if parts[0] != "docker":
                print(f"{Color.RED}Perintah '{parts[0]}' tidak dikenali. Ketik 'help' atau gunakan prefix 'docker'.{Color.RESET}")
                continue

            if len(parts) == 1:
                print("Usage: docker [OPTIONS] COMMAND [ARG...]")
                continue

            subcmd = parts[1]

            if subcmd == "ps":
                show_all = "-a" in parts or "--all" in parts
                print_ps_table(engine.list_containers(all_containers=show_all))

            elif subcmd in ["run", "create"]:
                # Simple flag parsing
                name = None
                ports = {}
                idx = 2
                while idx < len(parts) and parts[idx].startswith("-"):
                    if parts[idx] in ["-d", "--detach"]:
                        idx += 1
                    elif parts[idx] in ["--name", "-n"] and idx + 1 < len(parts):
                        name = parts[idx + 1]
                        idx += 2
                    elif parts[idx] in ["-p", "--publish"] and idx + 1 < len(parts):
                        port_str = parts[idx + 1]
                        if ":" in port_str:
                            hp, cp = port_str.split(":", 1)
                            ports[cp] = hp
                        idx += 2
                    else:
                        idx += 1

                if idx >= len(parts):
                    print(f"{Color.RED}Error: Image name required for docker {subcmd}.{Color.RESET}")
                    continue

                image = parts[idx]
                cmd = " ".join(parts[idx + 1:]) if idx + 1 < len(parts) else "sh"

                if subcmd == "run":
                    c = engine.run(image=image, command=cmd, name=name, ports=ports)
                    print(c.id)
                else:
                    c = engine.create(image=image, command=cmd, name=name, ports=ports)
                    print(c.id)

            elif subcmd in ["start", "stop", "pause", "unpause", "restart", "kill"]:
                if len(parts) < 3:
                    print(f"{Color.RED}\"docker {subcmd}\" requires at least 1 argument.{Color.RESET}")
                    continue
                target = parts[2]
                func = getattr(engine, subcmd)
                c = func(target)
                print(c.name)

            elif subcmd == "rm":
                force = "-f" in parts or "--force" in parts
                targets = [p for p in parts[2:] if not p.startswith("-")]
                if not targets:
                    print(f"{Color.RED}\"docker rm\" requires at least 1 container identifier.{Color.RESET}")
                    continue
                for t in targets:
                    res = engine.remove(t, force=force)
                    print(res)

            elif subcmd == "logs":
                if len(parts) < 3:
                    print(f"{Color.RED}\"docker logs\" requires 1 container identifier.{Color.RESET}")
                    continue
                c = engine._resolve_container(parts[2])
                for entry in c.logs:
                    print(f"{Color.DIM}{entry}{Color.RESET}")

            elif subcmd == "inspect":
                if len(parts) < 3:
                    print(f"{Color.RED}\"docker inspect\" requires 1 container identifier.{Color.RESET}")
                    continue
                data = engine.inspect(parts[2])
                print(json.dumps([data], indent=2))

            else:
                print(f"{Color.RED}docker: '{subcmd}' is not a simulated docker command. See 'help'.{Color.RESET}")

        except (KeyError, ValueError, RuntimeError) as e:
            print(f"{Color.RED}Error: {e}{Color.RESET}")
        except KeyboardInterrupt:
            print("\nAborted.")
            break
        except Exception as e:
            print(f"{Color.RED}Unexpected error: {e}{Color.RESET}")

def main():
    engine = DockerDaemonSimulator()
    # Check if run non-interactively or via args
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_automated_lifecycle_demo(engine)
    elif not sys.stdin.isatty():
        # Pipe or non-interactive mode: run full demo
        run_automated_lifecycle_demo(engine)
    else:
        # Interactive mode: first run concise demo then launch shell
        run_automated_lifecycle_demo(engine)
        print("\n" + "=" * 75)
        interactive_cli_shell(engine)

if __name__ == "__main__":
    main()
