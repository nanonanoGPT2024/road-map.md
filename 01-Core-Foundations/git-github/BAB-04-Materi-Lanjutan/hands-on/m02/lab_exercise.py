#!/usr/bin/env python3
"""
Lab Exercise: Git History Rewriting, Recovery, and Auditing Deep Dive.
Simulates Git's low-level DAG engine, Reflog tracking, Interactive Rebase,
Cryptographic Integrity Auditing (fsck), and Cascading Hash Rewrites (Filter-Repo).

Requirements: Python 3.8+ (Standard Library Only)
"""

import hashlib
import time
import re
from typing import Dict, List, Optional, Tuple, Set

# --- ANSI Terminal Color Palette ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[91m"
CLR_GREEN  = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE   = "\033[94m"
CLR_PURPLE = "\033[95m"
CLR_CYAN   = "\033[96m"
CLR_GRAY   = "\033[90m"


class GitObject:
    """Base class for Git Content-Addressable Storage (CAS) objects."""
    def serialize(self) -> bytes:
        raise NotImplementedError

    @property
    def oid(self) -> str:
        """Calculates Git's SHA-1 Object ID: sha1(type + ' ' + size + '\0' + content)."""
        data = self.serialize()
        header = f"{self.__class__.__name__.lower()} {len(data)}\0".encode("utf-8")
        return hashlib.sha1(header + data).hexdigest()


class Blob(GitObject):
    """Represents file content storage."""
    def __init__(self, content: str):
        self.content = content.encode("utf-8")

    def serialize(self) -> bytes:
        return self.content


class Tree(GitObject):
    """Represents directory state mapping filenames to Blob/Tree OIDs."""
    def __init__(self, entries: Optional[Dict[str, str]] = None):
        # Format: {filename: blob_oid}
        self.entries: Dict[str, str] = entries or {}

    def serialize(self) -> bytes:
        payload = bytearray()
        for name in sorted(self.entries.keys()):
            oid_bytes = bytes.fromhex(self.entries[name])
            payload.extend(f"100644 {name}\0".encode("utf-8") + oid_bytes)
        return bytes(payload)


class Commit(GitObject):
    """Represents a DAG commit node containing tree pointer, parents, metadata."""
    def __init__(self, tree_oid: str, parents: List[str], author: str, message: str, timestamp: Optional[float] = None):
        self.tree_oid = tree_oid
        self.parents = parents
        self.author = author
        self.message = message
        self.timestamp = timestamp if timestamp is not None else time.time()

    def serialize(self) -> bytes:
        parent_lines = "".join(f"parent {p}\n" for p in self.parents)
        content = (
            f"tree {self.tree_oid}\n"
            f"{parent_lines}"
            f"author {self.author} {int(self.timestamp)} +0000\n"
            f"committer {self.author} {int(self.timestamp)} +0000\n\n"
            f"{self.message}\n"
        )
        return content.encode("utf-8")


class ReflogEntry:
    """Records reference pointer transitions for disaster recovery."""
    def __init__(self, old_oid: str, new_oid: str, action: str, message: str):
        self.old_oid = old_oid
        self.new_oid = new_oid
        self.action = action
        self.message = message
        self.timestamp = time.strftime("%H:%M:%S", time.localtime())

    def __repr__(self) -> str:
        short_new = self.new_oid[:7] if self.new_oid != "0" * 40 else "0000000"
        return f"{CLR_GRAY}[{self.timestamp}]{CLR_RESET} {CLR_CYAN}{short_new}{CLR_RESET} {CLR_BOLD}{self.action}{CLR_RESET}: {self.message}"


class RepositoryEngine:
    """Simulates repository operations: CAS, DAG rewriting, fsck, and reflogs."""
    def __init__(self):
        self.object_store: Dict[str, GitObject] = {}
        self.branches: Dict[str, str] = {}
        self.head_ref: str = "main"
        self.reflog: List[ReflogEntry] = []
        self.branches["main"] = "0" * 40

    def put_object(self, obj: GitObject) -> str:
        """Stores object in CAS table using its hash key."""
        oid = obj.oid
        self.object_store[oid] = obj
        return oid

    def update_head(self, new_oid: str, action: str, message: str):
        """Atomic pointer manipulation logging transitions to reflog."""
        old_oid = self.branches.get(self.head_ref, "0" * 40)
        self.branches[self.head_ref] = new_oid
        entry = ReflogEntry(old_oid, new_oid, action, message)
        self.reflog.append(entry)

    def commit(self, files: Dict[str, str], message: str, author: str = "Lead Dev <lead@kernel.org>") -> str:
        """Creates Blobs, Tree, and Commit objects, advancing HEAD."""
        tree_entries = {}
        for filename, content in files.items():
            blob = Blob(content)
            blob_oid = self.put_object(blob)
            tree_entries[filename] = blob_oid

        tree = Tree(tree_entries)
        tree_oid = self.put_object(tree)

        current_head = self.branches[self.head_ref]
        parents = [current_head] if current_head != "0" * 40 else []

        commit = Commit(tree_oid, parents, author, message)
        commit_oid = self.put_object(commit)

        self.update_head(commit_oid, "commit", message)
        return commit_oid

    def reset_hard(self, target_oid: str):
        """Simulates destructive 'git reset --hard' by resetting branch pointer."""
        if target_oid not in self.object_store:
            raise ValueError(f"Target OID {target_oid} does not exist.")
        self.update_head(target_oid, "reset --hard", f"moving to {target_oid[:7]}")

    def audit_fsck(self) -> Dict[str, List[str]]:
        """
        Audits DAG health, identifying unreachable/dangling commits
        detached from any known reference or tree traversal.
        """
        reachable_oids: Set[str] = set()

        def traverse(oid: str):
            if oid in reachable_oids or oid not in self.object_store:
                return
            reachable_oids.add(oid)
            obj = self.object_store[oid]
            if isinstance(obj, Commit):
                traverse(obj.tree_oid)
                for p in obj.parents:
                    traverse(p)
            elif isinstance(obj, Tree):
                for entry_oid in obj.entries.values():
                    traverse(entry_oid)

        # Traverse from active references
        for branch_head in self.branches.values():
            if branch_head != "0" * 40:
                traverse(branch_head)

        all_commits = {oid for oid, obj in self.object_store.items() if isinstance(obj, Commit)}
        dangling_commits = list(all_commits - reachable_oids)

        return {"reachable": list(reachable_oids), "dangling": dangling_commits}

    def rebase_interactive(self, base_oid: str, script: List[Tuple[str, str, Optional[str]]]) -> str:
        """
        Simulates interactive rebase (pick, squash, reword, drop).
        Demonstrates why rewritten commits generate completely new SHA-1 hashes.
        script format: [('pick'|'squash'|'reword'|'drop', commit_oid, extra_param)]
        """
        current_parent = base_oid
        squashed_message = ""
        last_tree_oid = None

        for idx, step in enumerate(script):
            action, oid, param = step
            commit_obj: Commit = self.object_store[oid] # type: ignore

            if action == "drop":
                continue

            elif action == "pick":
                # Create a cloned commit on top of current_parent
                new_commit = Commit(commit_obj.tree_oid, [current_parent], commit_obj.author, commit_obj.message)
                current_parent = self.put_object(new_commit)
                last_tree_oid = new_commit.tree_oid

            elif action == "reword":
                new_message = param if param else commit_obj.message
                new_commit = Commit(commit_obj.tree_oid, [current_parent], commit_obj.author, new_message)
                current_parent = self.put_object(new_commit)
                last_tree_oid = new_commit.tree_oid

            elif action == "squash":
                # Fold changes and message into previous commit
                prior_commit: Commit = self.object_store[current_parent] # type: ignore
                squashed_message = f"{prior_commit.message}\n\n* Squashed: {commit_obj.message}"
                # Merge trees (for simplicity: current tree overrides prior)
                last_tree_oid = commit_obj.tree_oid
                
                # Replace the prior commit on current_parent's parent
                replacement_commit = Commit(
                    last_tree_oid,
                    prior_commit.parents,
                    prior_commit.author,
                    squashed_message
                )
                current_parent = self.put_object(replacement_commit)

        self.update_head(current_parent, "rebase -i (finish)", f"rebased onto {base_oid[:7]}")
        return current_parent

    def purge_secret_filter_repo(self, regex_pattern: str, replacement: str = "[REDACTED]"):
        """
        Simulates deep history rewrite (git filter-repo / filter-branch).
        Scans all Blobs, sanitizes matched patterns, reconstructs Trees,
        and cascades hash recalculations through child commits down the DAG.
        """
        compiled = re.compile(regex_pattern)
        blob_replacements: Dict[str, str] = {}
        tree_replacements: Dict[str, str] = {}
        commit_replacements: Dict[str, str] = {}

        # Pass 1: Sanitize Blobs
        for oid, obj in list(self.object_store.items()):
            if isinstance(obj, Blob):
                content = obj.content.decode("utf-8", errors="replace")
                if compiled.search(content):
                    sanitized_content = compiled.sub(replacement, content)
                    sanitized_blob = Blob(sanitized_content)
                    new_oid = self.put_object(sanitized_blob)
                    blob_replacements[oid] = new_oid

        # Pass 2: Reconstruct Trees referencing rewritten Blobs
        for oid, obj in list(self.object_store.items()):
            if isinstance(obj, Tree):
                modified = False
                new_entries = {}
                for name, entry_oid in obj.entries.items():
                    if entry_oid in blob_replacements:
                        new_entries[name] = blob_replacements[entry_oid]
                        modified = True
                    else:
                        new_entries[name] = entry_oid
                if modified:
                    new_tree = Tree(new_entries)
                    new_tree_oid = self.put_object(new_tree)
                    tree_replacements[oid] = new_tree_oid

        # Pass 3: Recompute Commits in topological order
        # Sort commits by timestamp
        commits = [obj for obj in self.object_store.values() if isinstance(obj, Commit)]
        commits.sort(key=lambda c: c.timestamp)

        for commit in commits:
            old_oid = commit.oid
            new_tree = tree_replacements.get(commit.tree_oid, commit.tree_oid)
            new_parents = [commit_replacements.get(p, p) for p in commit.parents]
            new_msg = compiled.sub(replacement, commit.message)

            if new_tree != commit.tree_oid or new_parents != commit.parents or new_msg != commit.message:
                sanitized_commit = Commit(new_tree, new_parents, commit.author, new_msg, commit.timestamp)
                new_commit_oid = self.put_object(sanitized_commit)
                commit_replacements[old_oid] = new_commit_oid

        # Update references pointing to modified tip
        for branch, tip_oid in self.branches.items():
            if tip_oid in commit_replacements:
                new_tip = commit_replacements[tip_oid]
                self.update_head(new_tip, "filter-repo", "purged sensitive payload")


# --- Demonstration Flow ---
def main():
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_PURPLE}   GIT ENGINE: HISTORY REWRITING, AUDITING & RECOVERY SIMULATION      {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}\n")

    repo = RepositoryEngine()

    print(f"{CLR_BOLD}Phase 1: Initializing Commit DAG with Secret Vulnerability{CLR_RESET}")
    c1 = repo.commit({"main.py": "print('Application Booting...')\n"}, "feat: initial commit")
    c2 = repo.commit(
        {"main.py": "print('Application Booting...')\n", "config.py": "AWS_SECRET_KEY='AKIA_DEMO_EXPOSED_SECRET_12345'\n"},
        "feat: introduce production configuration"
    )
    c3 = repo.commit(
        {"main.py": "print('Application Online')\n", "config.py": "AWS_SECRET_KEY='AKIA_DEMO_EXPOSED_SECRET_12345'\n"},
        "fix: typo in main banner"
    )
    c4 = repo.commit(
        {"worker.py": "def task(): pass\n"},
        "wip: experimental background queue"
    )

    print(f"  {CLR_GREEN}✓{CLR_RESET} Base Commit  : {CLR_CYAN}{c1[:7]}{CLR_RESET}")
    print(f"  {CLR_GREEN}✓{CLR_RESET} Secret Added : {CLR_RED}{c2[:7]}{CLR_RESET} (AWS Token Embedded)")
    print(f"  {CLR_GREEN}✓{CLR_RESET} Trivial Fix  : {CLR_CYAN}{c3[:7]}{CLR_RESET}")
    print(f"  {CLR_GREEN}✓{CLR_RESET} WIP Feature  : {CLR_CYAN}{c4[:7]}{CLR_RESET}")

    # Phase 2: Interactive Rebase
    print(f"\n{CLR_BOLD}Phase 2: Interactive Rebase (Squash WIP & Reword Fix){CLR_RESET}")
    print(f"  Executing sequence against Base {CLR_CYAN}{c2[:7]}{CLR_RESET}:")
    print(f"    - {CLR_YELLOW}reword{CLR_RESET} {c3[:7]} -> 'fix: standardized banner startup message'")
    print(f"    - {CLR_YELLOW}squash{CLR_RESET} {c4[:7]} into reworded commit")

    rebase_script = [
        ("reword", c3, "fix: standardized banner startup message"),
        ("squash", c4, None)
    ]
    rebased_head = repo.rebase_interactive(c2, rebase_script)
    print(f"  {CLR_GREEN}✓ Rebase Successful.{CLR_RESET} New HEAD: {CLR_BOLD}{rebased_head[:7]}{CLR_RESET}")

    # Phase 3: Disaster Simulation (Accidental Hard Reset)
    print(f"\n{CLR_BOLD}Phase 3: Disaster Injection (Simulating Destructive 'reset --hard'){CLR_RESET}")
    print(f"  Accidentally rolling back branch tip to initial commit {CLR_CYAN}{c1[:7]}{CLR_RESET}...")
    repo.reset_hard(c1)
    print(f"  Current Branch Pointer: {CLR_RED}{repo.branches['main'][:7]}{CLR_RESET}")

    # Phase 4: Auditing with fsck
    print(f"\n{CLR_BOLD}Phase 4: Integrity Auditing (fsck - Dangling Object Detection){CLR_RESET}")
    audit = repo.audit_fsck()
    print(f"  Total Reachable Objects : {len(audit['reachable'])}")
    print(f"  Dangling/Lost Commits   : {CLR_RED}{len(audit['dangling'])}{CLR_RESET}")
    for dangling_oid in audit["dangling"]:
        commit_obj: Commit = repo.object_store[dangling_oid] # type: ignore
        first_line = commit_obj.message.splitlines()[0]
        print(f"    -> Dangling Commit: {CLR_YELLOW}{dangling_oid[:7]}{CLR_RESET} | {first_line}")

    # Phase 5: Reflog Recovery
    print(f"\n{CLR_BOLD}Phase 5: Disaster Recovery via Reflog Inspection{CLR_RESET}")
    print(f"  {CLR_BOLD}Active Reflog Records:{CLR_RESET}")
    for idx, entry in enumerate(reversed(repo.reflog)):
        print(f"    HEAD@{{{idx}}}: {entry}")

    target_recovery = rebased_head
    print(f"\n  Initiating Recovery to: {CLR_CYAN}{target_recovery[:7]}{CLR_RESET}...")
    repo.reset_hard(target_recovery)
    print(f"  {CLR_GREEN}✓ Branch recovered.{CLR_RESET} Current HEAD: {CLR_CYAN}{repo.branches['main'][:7]}{CLR_RESET}")

    # Phase 6: Sensitive Data Scrubbing
    print(f"\n{CLR_BOLD}Phase 6: Cascading History Rewrite (Filter-Repo Secret Scrub){CLR_RESET}")
    secret_pattern = r"AKIA_[A-Z0-9_]+"
    print(f"  Target pattern: {CLR_RED}{secret_pattern}{CLR_RESET}")
    pre_rewrite_head = repo.branches["main"]

    repo.purge_secret_filter_repo(secret_pattern, "[SECRET_SCRUBBED_BY_AUDITOR]")
    post_rewrite_head = repo.branches["main"]

    print(f"  Pre-purge HEAD OID  : {CLR_YELLOW}{pre_rewrite_head}{CLR_RESET}")
    print(f"  Post-purge HEAD OID : {CLR_GREEN}{post_rewrite_head}{CLR_RESET}")
    print(f"  {CLR_GRAY}Notice: SHA-1 cascade completely rewrote downstream hashes!{CLR_RESET}")

    # Verify content sanitization
    final_commit: Commit = repo.object_store[post_rewrite_head] # type: ignore
    config_blob_oid = None
    curr: Optional[Commit] = final_commit
    
    # Trace back to find config.py blob in rewritten history
    visited = set()
    found_clean = False
    queue = [post_rewrite_head]
    while queue:
        oid = queue.pop(0)
        if oid in visited: continue
        visited.add(oid)
        c: Commit = repo.object_store[oid] # type: ignore
        tree: Tree = repo.object_store[c.tree_oid] # type: ignore
        if "config.py" in tree.entries:
            blob: Blob = repo.object_store[tree.entries["config.py"]] # type: ignore
            content = blob.content.decode()
            if "[SECRET_SCRUBBED_BY_AUDITOR]" in content:
                found_clean = True
                print(f"\n  {CLR_BOLD}Audit Verification on Rewritten config.py:{CLR_RESET}")
                print(f"  {CLR_GREEN}{content.strip()}{CLR_RESET}")
                break
        queue.extend(c.parents)

    assert found_clean, "Purge validation failed!"
    print(f"\n{CLR_BOLD}{CLR_GREEN}✔ Lab verification complete: DAG rewritten, secrets purged, history secured.{CLR_RESET}")


if __name__ == "__main__":
    main()