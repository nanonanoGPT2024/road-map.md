#!/usr/bin/env python3
"""
Lab Exercise: Distributed Architecture & Remote Synchronization Protocol
Module: 01-Core-Foundations / Chapter 05 - Remote Collaboration & Distributed Architectures

Simulates internal Git distributed synchronization mechanics:
- DAG-based Commit Graph and Content-Addressable Object Store (SHA-1).
- Remote Protocol Negotiation (Determining common ancestors via 'have'/'want' exchange).
- Fast-Forward verification vs. Non-Fast-Forward push rejections.
- Fetch, 3-Way Merge resolution (Base, Ours, Theirs), and Fast-Forward catch-up.
"""

import hashlib
import json
import time
from typing import Dict, List, Optional, Set, Tuple

# Terminal ANSI Styling
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_CYAN = "\033[36m"
CLR_MAGENTA = "\033[35m"


def sha1_hash(content: str) -> str:
    """Generates standard SHA-1 hex digest for content-addressable storage."""
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:10]


class Commit:
    """Represents an immutable Git Commit object."""
    def __init__(self, tree: Dict[str, str], parents: List[str], author: str, message: str, timestamp: float = None):
        self.tree = tree  # Dict[filepath, file_content_hash]
        self.parents = parents
        self.author = author
        self.message = message
        self.timestamp = timestamp or time.time()
        
        # Serialize for hashing
        payload = json.dumps({
            "tree": sorted(self.tree.items()),
            "parents": self.parents,
            "author": self.author,
            "message": self.message
        }, sort_keys=True)
        self.hash = sha1_hash(payload)

    def __repr__(self):
        p_str = ",".join(self.parents) if self.parents else "root"
        return f"Commit({self.hash} | P:[{p_str}] | {self.author}: {self.message})"


class GitRepository:
    """Simulates a local or remote Git repository with DAG traversal & object transport."""
    def __init__(self, name: str, is_bare: bool = False):
        self.name = name
        self.is_bare = is_bare
        self.objects: Dict[str, Commit] = {}
        self.blobs: Dict[str, str] = {}  # sha -> actual text content
        self.refs: Dict[str, str] = {}    # ref_path -> commit_hash (e.g. 'refs/heads/main')
        self.remotes: Dict[str, 'GitRepository'] = {}
        self.index: Dict[str, str] = {}   # Staging area: filepath -> content

    def write_blob(self, content: str) -> str:
        """Stores content in blob store, returns SHA-1."""
        b_hash = sha1_hash(content)
        self.blobs[b_hash] = content
        return b_hash

    def stage_file(self, path: str, content: str):
        """Emulates 'git add'."""
        self.index[path] = content

    def create_commit(self, message: str, author: str, parent_override: List[str] = None) -> Commit:
        """Creates a new commit pointing to the current staged index tree."""
        current_tree = {}
        head_commit_hash = self.refs.get("refs/heads/main")
        
        if head_commit_hash and head_commit_hash in self.objects:
            current_tree = dict(self.objects[head_commit_hash].tree)

        for path, content in self.index.items():
            blob_hash = self.write_blob(content)
            current_tree[path] = blob_hash
        self.index.clear()

        parents = parent_override if parent_override is not None else ([head_commit_hash] if head_commit_hash else [])
        commit = Commit(tree=current_tree, parents=parents, author=author, message=message)
        
        self.objects[commit.hash] = commit
        self.refs["refs/heads/main"] = commit.hash
        return commit

    def get_ancestors(self, commit_hash: str) -> Set[str]:
        """Traverses the DAG backwards via BFS to find all ancestors of a commit."""
        ancestors = set()
        queue = [commit_hash]
        while queue:
            curr = queue.pop(0)
            if curr in self.objects and curr not in ancestors:
                ancestors.add(curr)
                queue.extend(self.objects[curr].parents)
        return ancestors

    def is_ancestor(self, possible_ancestor: str, descendant: str) -> bool:
        """Returns True if possible_ancestor is in the DAG lineage behind descendant."""
        if possible_ancestor == descendant:
            return True
        return possible_ancestor in self.get_ancestors(descendant)

    def find_lowest_common_ancestor(self, c1: str, c2: str) -> Optional[str]:
        """Finds merge-base (Lowest Common Ancestor) between two branches/commits."""
        if not c1 or not c2:
            return None
        ancestors_c1 = self.get_ancestors(c1)
        
        # Traverse c2 lineage in topological BFS to hit earliest common node
        queue = [c2]
        visited = set()
        while queue:
            curr = queue.pop(0)
            if curr in ancestors_c1:
                return curr
            visited.add(curr)
            for p in self.objects[curr].parents:
                if p not in visited:
                    queue.append(p)
        return None

    def fetch(self, remote_name: str) -> List[str]:
        """
        Simulates 'git fetch'.
        Exchanges 'want'/'have' packs with remote, copies missing objects, 
        and updates 'refs/remotes/<remote>/<branch>'.
        """
        remote = self.remotes.get(remote_name)
        if not remote:
            raise ValueError(f"Remote {remote_name} not configured.")

        print(f"{CLR_CYAN}[{self.name}] Initiating fetch from '{remote.name}'...{CLR_RESET}")
        transferred_commits = []

        for ref_name, remote_hash in remote.refs.items():
            if not ref_name.startswith("refs/heads/"):
                continue
            branch = ref_name.split("/")[-1]
            remote_tracking_ref = f"refs/remotes/{remote_name}/{branch}"

            # Protocol Discovery: Discover objects remote has that local lacks
            queue = [remote_hash]
            needed_commits = []
            while queue:
                curr_h = queue.pop(0)
                if curr_h and curr_h not in self.objects:
                    needed_commits.append(curr_h)
                    remote_commit = remote.objects[curr_h]
                    for p in remote_commit.parents:
                        if p not in self.objects:
                            queue.append(p)

            # Replicate pack payload
            for h in reversed(needed_commits):
                commit_obj = remote.objects[h]
                self.objects[h] = commit_obj
                # Replicate associated blobs
                for b_hash in commit_obj.tree.values():
                    if b_hash in remote.blobs:
                        self.blobs[b_hash] = remote.blobs[b_hash]
                transferred_commits.append(h)

            self.refs[remote_tracking_ref] = remote_hash
            print(f"  {CLR_BLUE}Fetched {len(transferred_commits)} objects. Tracking: {remote_tracking_ref} -> {remote_hash}{CLR_RESET}")

        return transferred_commits

    def push(self, remote_name: str, branch: str = "main") -> bool:
        """
        Simulates 'git push'.
        Executes Fast-Forward validation on remote ref before pushing objects.
        """
        remote = self.remotes.get(remote_name)
        local_ref = f"refs/heads/{branch}"
        remote_ref = f"refs/heads/{branch}"
        local_hash = self.refs.get(local_ref)

        print(f"{CLR_BOLD}[{self.name}] Attempting push to '{remote.name}/{branch}' (HEAD: {local_hash})...{CLR_RESET}")
        if not local_hash:
            print(f"{CLR_RED}Push failed: Local branch {branch} does not exist.{CLR_RESET}")
            return False

        remote_hash = remote.refs.get(remote_ref)

        # Non-fast-forward check: remote tip must be an ancestor of local commit!
        if remote_hash and not self.is_ancestor(remote_hash, local_hash):
            print(f"{CLR_RED}  [REJECTED - NON-FAST-FORWARD] Remote '{branch}' has diverged!{CLR_RESET}")
            print(f"  Remote tip is {remote_hash}, but it is NOT an ancestor of {local_hash}.")
            print(f"  Hint: Run 'git fetch' and merge/rebase remote changes before pushing.")
            return False

        # Transfer packfile objects to remote
        push_queue = [local_hash]
        to_transfer = []
        while push_queue:
            curr = push_queue.pop(0)
            if curr and curr not in remote.objects:
                to_transfer.append(curr)
                for p in self.objects[curr].parents:
                    push_queue.append(p)

        for h in reversed(to_transfer):
            remote.objects[h] = self.objects[h]
            for b_hash in self.objects[h].tree.values():
                remote.blobs[b_hash] = self.blobs[b_hash]

        # Fast-Forward pointer update on remote
        remote.refs[remote_ref] = local_hash
        self.refs[f"refs/remotes/{remote_name}/{branch}"] = local_hash
        print(f"{CLR_GREEN}  [SUCCESS] Updated {remote.name}:{remote_ref} -> {local_hash} (Fast-forward){CLR_RESET}")
        return True

    def merge_three_way(self, remote_tracking_ref: str, author: str) -> Optional[Commit]:
        """
        Executes 3-Way Merge:
        LCA (Base) vs Local HEAD (Ours) vs Remote HEAD (Theirs).
        Detects conflicts or automatically merges clean modifications.
        """
        local_head = self.refs.get("refs/heads/main")
        remote_head = self.refs.get(remote_tracking_ref)
        
        if not local_head or not remote_head:
            raise ValueError("Invalid references for merge.")

        base_hash = self.find_lowest_common_ancestor(local_head, remote_head)
        print(f"{CLR_MAGENTA}[{self.name}] 3-Way Merge Analysis:{CLR_RESET}")
        print(f"  - Base (LCA):    {base_hash}")
        print(f"  - Ours  (Local): {local_head}")
        print(f"  - Theirs(Remote):{remote_head}")

        if base_hash == remote_head:
            print(f"{CLR_GREEN}  Already up-to-date.{CLR_RESET}")
            return None

        if base_hash == local_head:
            print(f"{CLR_YELLOW}  Fast-forwarding local branch to {remote_head}...{CLR_RESET}")
            self.refs["refs/heads/main"] = remote_head
            return self.objects[remote_head]

        base_tree = self.objects[base_hash].tree if base_hash else {}
        our_tree = self.objects[local_head].tree
        their_tree = self.objects[remote_head].tree

        all_files = set(base_tree.keys()) | set(our_tree.keys()) | set(their_tree.keys())
        merged_tree = {}
        conflicts = []

        for f in all_files:
            b_val = base_tree.get(f)
            o_val = our_tree.get(f)
            t_val = their_tree.get(f)

            if o_val == t_val:
                # Both agreed or unmodified
                if o_val:
                    merged_tree[f] = o_val
            elif b_val == o_val:
                # Local didn't touch, take remote modification
                if t_val:
                    merged_tree[f] = t_val
            elif b_val == t_val:
                # Remote didn't touch, retain local modification
                if o_val:
                    merged_tree[f] = o_val
            else:
                # Divergence on both branches -> Conflict
                conflicts.append(f)

        if conflicts:
            print(f"{CLR_RED}  Merge conflict in files: {conflicts}{CLR_RESET}")
            print(f"  Simulating automatic conflict resolution strategy: Union synthesis.")
            # Synthesize conflict resolution for automation
            for c_file in conflicts:
                merged_content = (
                    f"<<<<<<< OURS\n{self.blobs.get(our_tree[c_file], '')}\n"
                    f"=======\n{self.blobs.get(their_tree[c_file], '')}\n>>>>>>> THEIRS"
                )
                b_hash = self.write_blob(merged_content)
                merged_tree[c_file] = b_hash

        # Create Merge Commit with 2 parents
        merge_commit = Commit(
            tree=merged_tree,
            parents=[local_head, remote_head],
            author=author,
            message=f"Merge branch '{remote_tracking_ref}' into main"
        )
        self.objects[merge_commit.hash] = merge_commit
        self.refs["refs/heads/main"] = merge_commit.hash
        print(f"{CLR_GREEN}  Merge commit created: {merge_commit.hash}{CLR_RESET}")
        return merge_commit


def run_distributed_collaboration_lab():
    print(f"\n{CLR_BOLD}=== SIMULATING DISTRIBUTED COLLABORATION & NEGOTIATION PROTOCOL ==={CLR_RESET}\n")

    # 1. Initialize Central Remote (GitHub Bare Repository)
    github_remote = GitRepository("origin (Central Remote)", is_bare=True)

    # 2. Initialize Workstations: Alice & Bob
    alice_repo = GitRepository("Alice-PC")
    alice_repo.remotes["origin"] = github_remote

    bob_repo = GitRepository("Bob-PC")
    bob_repo.remotes["origin"] = github_remote

    # Initial Shared Project Scaffold
    alice_repo.stage_file("app.py", "print('Init v1.0')\n")
    alice_repo.stage_file("README.md", "# Distributed Project\n")
    c0 = alice_repo.create_commit("Initial commit", author="Alice <alice@corp.io>")
    print(f"{CLR_CYAN}[Setup] Alice initializes baseline repository: Commit {c0.hash}{CLR_RESET}")

    # Alice pushes baseline to Origin
    alice_repo.push("origin", "main")

    # Bob clones from Origin (simulate initial fetch & branch setup)
    print(f"\n{CLR_CYAN}[Setup] Bob synchronizes workspace with Origin...{CLR_RESET}")
    bob_repo.fetch("origin")
    bob_repo.refs["refs/heads/main"] = bob_repo.refs["refs/remotes/origin/main"]

    print("\n" + "="*70)
    print(f"{CLR_BOLD}SCENARIO 1: Divergence & Non-Fast-Forward Rejection{CLR_RESET}")
    print("="*70)

    # Alice makes changes and pushes
    alice_repo.stage_file("app.py", "print('Init v1.0')\nprint('Alice feature')\n")
    c_alice = alice_repo.create_commit("Add Alice feature", author="Alice")
    alice_repo.push("origin", "main")

    # Meanwhile, Bob makes an independent change on his local workstation without fetching first
    bob_repo.stage_file("app.py", "print('Init v1.0')\nprint('Bob feature')\n")
    bob_repo.stage_file("logger.py", "def log(): pass\n")
    c_bob = bob_repo.create_commit("Add Bob feature & logger", author="Bob")
    print(f"\nBob local commit created: {c_bob.hash}")

    # Bob tries to push directly to remote
    print("\nBob attempts to push directly without fetching remote updates:")
    success = bob_repo.push("origin", "main")
    assert not success, "Push should have been rejected as Non-Fast-Forward!"

    print("\n" + "="*70)
    print(f"{CLR_BOLD}SCENARIO 2: Protocol Fetch, 3-Way Merge, & Push Resolution{CLR_RESET}")
    print("="*70)

    # Bob fetches the remote state
    bob_repo.fetch("origin")

    # Bob performs 3-way merge to integrate remote changes
    merge_commit = bob_repo.merge_three_way("refs/remotes/origin/main", author="Bob")

    # Bob pushes merged state back to Origin (Should be Fast-Forward now)
    print("\nBob attempts to push resolved DAG to Origin:")
    push_success = bob_repo.push("origin", "main")
    assert push_success, "Push after merge resolution must succeed!"

    print("\n" + "="*70)
    print(f"{CLR_BOLD}SCENARIO 3: Alice Fast-Forwards Her Workspace{CLR_RESET}")
    print("="*70)

    # Alice fetches latest updates
    alice_repo.fetch("origin")
    # Alice merges origin/main (which should fast-forward)
    alice_repo.merge_three_way("refs/remotes/origin/main", author="Alice")

    print("\n" + "="*70)
    print(f"{CLR_BOLD}DAG REPOSITORY AUDIT{CLR_RESET}")
    print("="*70)
    print(f"Origin HEAD:    {github_remote.refs['refs/heads/main']}")
    print(f"Alice HEAD:     {alice_repo.refs['refs/heads/main']}")
    print(f"Bob HEAD:       {bob_repo.refs['refs/heads/main']}")

    assert (
        github_remote.refs["refs/heads/main"] == 
        alice_repo.refs["refs/heads/main"] == 
        bob_repo.refs["refs/heads/main"]
    ), "All nodes must achieve distributed eventual consistency!"

    print(f"\n{CLR_GREEN}{CLR_BOLD}[VERIFIED] Distributed convergence complete. All distributed nodes synchronized.{CLR_RESET}\n")


if __name__ == "__main__":
    run_distributed_collaboration_lab()