#!/usr/bin/env python3
"""
Lab Hands-on: Branching Strategies & Merge Topologies
Category: 01-Core-Foundations | Chapter: 03 - Module 02 Deep Dive

Simulates the underlying Git Directed Acyclic Graph (DAG) commit engine,
modeling Fast-Forward Merges, Three-Way Recursive Merges (with Lowest Common
Ancestor / LCA calculation), and Rebase operations (history rewriting).
"""

import sys
import time
import hashlib
from typing import Dict, List, Optional, Set, Tuple

# ANSI Terminal Styling Constants
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_MAG    = "\033[35m"
CLR_CYAN   = "\033[36m"
CLR_GRAY   = "\033[90m"


class Commit:
    """
    Represents an immutable commit node within the Git DAG topology.
    Contains commit metadata, snapshot state (tree), and pointers to parent SHAs.
    """
    def __init__(self, parents: List[str], tree: Dict[str, str], message: str, author: str = "Lead Dev"):
        self.parents = parents
        self.tree = tree.copy()  # Snapshot of files at this commit
        self.message = message
        self.author = author
        self.timestamp = time.time()
        self.sha = self._compute_sha()

    def _compute_sha(self) -> str:
        """Computes deterministic SHA-1 hash from metadata, tree contents, and parents."""
        payload = (
            f"parents:{','.join(self.parents)}|"
            f"tree:{sorted(self.tree.items())}|"
            f"msg:{self.message}|"
            f"author:{self.author}|"
            f"ts:{self.timestamp}"
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]

    def __repr__(self) -> str:
        p_str = ",".join(self.parents) if self.parents else "root"
        return f"<Commit {self.sha} parents=[{p_str}] msg='{self.message}'>"


class GitDAGSimulator:
    """
    Simulates Git's branch reference system, DAG operations, LCA resolution,
    Fast-Forward merges, 3-Way Merge commits, and Commit Replaying (Rebase).
    """
    def __init__(self):
        self.commits: Dict[str, Commit] = {}
        self.branches: Dict[str, str] = {}  # branch_name -> commit_sha
        self.head: str = "main"             # Current branch or detached commit SHA
        self.is_detached: bool = False

    def get_head_commit_sha(self) -> Optional[str]:
        """Resolves HEAD to a commit SHA."""
        if self.is_detached:
            return self.head
        return self.branches.get(self.head)

    def commit(self, message: str, file_updates: Dict[str, str]) -> Commit:
        """
        Creates a new commit node with current HEAD as parent and advances HEAD ref.
        """
        current_sha = self.get_head_commit_sha()
        parents = [current_sha] if current_sha else []
        
        # Build new snapshot based on parent state
        base_tree = self.commits[current_sha].tree.copy() if current_sha else {}
        base_tree.update(file_updates)

        node = Commit(parents=parents, tree=base_tree, message=message)
        self.commits[node.sha] = node

        if not self.is_detached:
            self.branches[self.head] = node.sha
        else:
            self.head = node.sha

        return node

    def branch(self, name: str) -> None:
        """Creates a new branch pointing to current HEAD."""
        sha = self.get_head_commit_sha()
        if not sha:
            raise RuntimeError("Cannot branch without an initial commit.")
        self.branches[name] = sha

    def checkout(self, target: str) -> None:
        """Updates HEAD pointer to a specified branch or commit hash."""
        if target in self.branches:
            self.head = target
            self.is_detached = False
        elif target in self.commits:
            self.head = target
            self.is_detached = True
        else:
            raise ValueError(f"Ref or commit '{target}' does not exist.")

    def find_ancestors(self, start_sha: str) -> Set[str]:
        """Traverses the DAG backwards via BFS to find all reachable ancestor commits."""
        ancestors: Set[str] = set()
        queue = [start_sha]
        while queue:
            curr = queue.pop(0)
            if curr in self.commits and curr not in ancestors:
                ancestors.add(curr)
                queue.extend(self.commits[curr].parents)
        return ancestors

    def find_lca(self, sha_a: str, sha_b: str) -> Optional[str]:
        """
        Finds the Lowest Common Ancestor (LCA) / Merge Base between two commits.
        Uses BFS ancestor traversal from both branches.
        """
        if sha_a == sha_b:
            return sha_a
        ancestors_a = self.find_ancestors(sha_a)
        
        # Traverse from sha_b via BFS to locate closest match in ancestors_a
        queue = [sha_b]
        visited = set()
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            if curr in ancestors_a:
                return curr
            if curr in self.commits:
                queue.extend(self.commits[curr].parents)
        return None

    def merge_fast_forward(self, target_branch: str) -> bool:
        """
        Attempts a Fast-Forward merge.
        Succeeds only if current HEAD is an ancestor of the target branch.
        Advances current branch pointer without creating a merge commit.
        """
        curr_sha = self.get_head_commit_sha()
        target_sha = self.branches.get(target_branch)

        if not curr_sha or not target_sha:
            raise ValueError("Invalid branch state for merge.")

        ancestors_target = self.find_ancestors(target_sha)
        if curr_sha in ancestors_target:
            # Fast-Forward is topologically possible
            self.branches[self.head] = target_sha
            return True
        return False

    def merge_three_way(self, source_branch: str) -> Tuple[Commit, bool]:
        """
        Performs a 3-way recursive merge:
        1. Identifies LCA (merge-base).
        2. Reconciles file trees (Ancestor, Our HEAD, Theirs).
        3. Detects write-write conflicts.
        4. Generates a merge commit with dual parents [HEAD_SHA, SOURCE_SHA].
        """
        head_sha = self.get_head_commit_sha()
        src_sha = self.branches.get(source_branch)
        if not head_sha or not src_sha:
            raise ValueError("Invalid refs for 3-way merge.")

        lca_sha = self.find_lca(head_sha, src_sha)
        if not lca_sha:
            raise RuntimeError("No common ancestor found (disjoint histories).")

        base_tree = self.commits[lca_sha].tree
        ours_tree = self.commits[head_sha].tree
        theirs_tree = self.commits[src_sha].tree

        all_keys = set(base_tree.keys()) | set(ours_tree.keys()) | set(theirs_tree.keys())
        merged_tree = {}
        has_conflicts = False

        for key in all_keys:
            base_val = base_tree.get(key)
            our_val = ours_tree.get(key)
            their_val = theirs_tree.get(key)

            if our_val == their_val:
                if our_val is not None:
                    merged_tree[key] = our_val
            elif our_val == base_val:
                # Upstream modified this file; apply upstream change
                if their_val is not None:
                    merged_tree[key] = their_val
            elif their_val == base_val:
                # We modified this file; retain our change
                if our_val is not None:
                    merged_tree[key] = our_val
            else:
                # Both modified the file differently: Conflict
                has_conflicts = True
                merged_tree[key] = f"<<<< HEAD ({our_val}) ==== {source_branch} ({their_val}) >>>>"

        # Create dual-parent merge commit
        merge_msg = f"Merge branch '{source_branch}' into {self.head}"
        merge_commit = Commit(parents=[head_sha, src_sha], tree=merged_tree, message=merge_msg)
        self.commits[merge_commit.sha] = merge_commit
        self.branches[self.head] = merge_commit.sha
        return merge_commit, has_conflicts

    def rebase(self, upstream_branch: str) -> List[str]:
        """
        Simulates Git Rebase:
        1. Identifies diverge point (LCA) between upstream and current branch.
        2. Collects commits unique to current branch in chronological order.
        3. Sequentially replays/recomputes each commit on top of upstream HEAD.
        Returns the list of newly created commit SHAs.
        """
        curr_sha = self.get_head_commit_sha()
        upstream_sha = self.branches.get(upstream_branch)
        if not curr_sha or not upstream_sha:
            raise ValueError("Invalid branches for rebase operation.")

        lca_sha = self.find_lca(curr_sha, upstream_sha)
        if not lca_sha:
            raise RuntimeError("Cannot rebase without common ancestor.")

        # Collect commits on current branch back to LCA
        commits_to_replay = []
        curr = curr_sha
        while curr != lca_sha:
            node = self.commits[curr]
            commits_to_replay.append(node)
            curr = node.parents[0] if node.parents else None
            if not curr:
                break
        commits_to_replay.reverse()

        # Replay commits on top of upstream_sha
        new_parent = upstream_sha
        replayed_shas = []
        for old_commit in commits_to_replay:
            # Reconstruct tree with base of new_parent
            base_tree = self.commits[new_parent].tree.copy()
            base_tree.update(old_commit.tree)
            
            replayed_node = Commit(
                parents=[new_parent],
                tree=base_tree,
                message=f"{old_commit.message} (rebased)",
                author=old_commit.author
            )
            self.commits[replayed_node.sha] = replayed_node
            new_parent = replayed_node.sha
            replayed_shas.append(replayed_node.sha)

        # Repoint current branch to the head of rebased chain
        self.branches[self.head] = new_parent
        return replayed_shas

    def display_topology(self, title: str) -> None:
        """Visualizes the commit nodes and branch pointers in the current DAG state."""
        print(f"\n{CLR_BOLD}{CLR_CYAN}=== {title} ==={CLR_RESET}")
        
        # Build inverted branch map for labeling
        branch_refs: Dict[str, List[str]] = {}
        for b_name, b_sha in self.branches.items():
            branch_refs.setdefault(b_sha, []).append(b_name)

        # Topological sorting via DFS traversal
        visited = set()
        stack = list(self.branches.values())
        sorted_commits = []
        while stack:
            sha = stack.pop()
            if sha not in visited:
                visited.add(sha)
                sorted_commits.append(sha)
                if sha in self.commits:
                    stack.extend(reversed(self.commits[sha].parents))

        for sha in sorted_commits:
            c = self.commits[sha]
            refs = branch_refs.get(sha, [])
            ref_badges = []
            for r in refs:
                if r == self.head and not self.is_detached:
                    ref_badges.append(f"{CLR_BOLD}{CLR_GREEN}[HEAD -> {r}]{CLR_RESET}")
                else:
                    ref_badges.append(f"{CLR_BOLD}{CLR_YELLOW}[{r}]{CLR_RESET}")
            
            parents_str = f"({', '.join(c.parents)})" if c.parents else "(root)"
            is_merge = len(c.parents) > 1
            node_glyph = f"{CLR_MAG}* (MERGE){CLR_RESET}" if is_merge else f"{CLR_BLUE}*{CLR_RESET}"
            
            badges_str = " ".join(ref_badges)
            print(f" {node_glyph} {CLR_BOLD}{c.sha}{CLR_RESET} {parents_str} {badges_str}")
            print(f"   {CLR_GRAY}|-- Msg: {c.message}{CLR_RESET}")
            print(f"   {CLR_GRAY}\\-- Tree: {c.tree}{CLR_RESET}")


def run_laboratory_exercise():
    """Executes the deep dive laboratory simulation sequence."""
    print(f"{CLR_BOLD}{CLR_GREEN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}  LAB EXERCISE: BRANCHING STRATEGIES & MERGE TOPOLOGIES SIMULATION     {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}======================================================================{CLR_RESET}")

    repo = GitDAGSimulator()

    # Step 1: Base trunk line setup
    print(f"\n{CLR_YELLOW}[Step 1] Initializing repository and main branch baseline...{CLR_RESET}")
    c1 = repo.commit("Init: setup core engine files", {"main.py": "v1.0", "config.json": "env=prod"})
    c2 = repo.commit("Feature: add authentication framework", {"auth.py": "jwt_auth()"})
    repo.display_topology("Initial State: Main Branch")

    # Step 2: Branching out - Fast-Forward Candidate
    print(f"\n{CLR_YELLOW}[Step 2] Creating 'feature/profile' directly ahead of main...{CLR_RESET}")
    repo.branch("feature/profile")
    repo.checkout("feature/profile")
    c3 = repo.commit("feat(profile): create user avatar service", {"profile.py": "def get_avatar(): pass"})
    repo.display_topology("Feature Branch Created (No Divergence on Main)")

    # Step 3: Attempting Fast-Forward Merge
    print(f"\n{CLR_YELLOW}[Step 3] Checking out 'main' and executing Fast-Forward merge...{CLR_RESET}")
    repo.checkout("main")
    ff_success = repo.merge_fast_forward("feature/profile")
    print(f"Fast-Forward Result: {CLR_GREEN}{ff_success}{CLR_RESET} (Head pointer swung directly to target)")
    repo.display_topology("Post Fast-Forward Merge on Main")

    # Step 4: True Divergence (Branching + Trunk Movement)
    print(f"\n{CLR_YELLOW}[Step 4] Diverging branches for 3-Way Merge testing...{CLR_RESET}")
    repo.branch("feature/billing")
    repo.checkout("feature/billing")
    repo.commit("feat(billing): stripe integration", {"billing.py": "stripe.charge()", "config.json": "env=prod;stripe=active"})

    repo.checkout("main")
    repo.commit("fix(core): hotfix critical memory leak in auth", {"auth.py": "jwt_auth_optimized()", "metrics.py": "statsd.counter()"})
    repo.display_topology("Diverged State (LCA is at Fast-Forward point)")

    # Step 5: LCA Identification & 3-Way Merge
    sha_main = repo.branches["main"]
    sha_billing = repo.branches["feature/billing"]
    lca_sha = repo.find_lca(sha_main, sha_billing)
    print(f"\n{CLR_YELLOW}[Step 5] Lowest Common Ancestor (LCA) Resolution:{CLR_RESET}")
    print(f" -> Branch 'main' Commit:    {CLR_CYAN}{sha_main}{CLR_RESET}")
    print(f" -> Branch 'billing' Commit: {CLR_CYAN}{sha_billing}{CLR_RESET}")
    print(f" -> Resolved Merge Base/LCA: {CLR_BOLD}{CLR_GREEN}{lca_sha}{CLR_RESET} ('{repo.commits[lca_sha].message}')")

    print(f"\n{CLR_YELLOW}[Executing 3-Way Recursive Merge...]{CLR_RESET}")
    merge_node, conflicts = repo.merge_three_way("feature/billing")
    print(f"Merge Commit SHA: {CLR_BOLD}{merge_node.sha}{CLR_RESET} with dual parents: {merge_node.parents}")
    print(f"Conflict Status: {CLR_RED if conflicts else CLR_GREEN}{'CONFLICTS PRESENT' if conflicts else 'CLEAN MERGE'}{CLR_RESET}")
    repo.display_topology("Post 3-Way Merge Topology (Dual Parents)")

    # Step 6: Git Rebase (History Rewriting)
    print(f"\n{CLR_YELLOW}[Step 6] Modeling Linear Rebase: Branching off old LCA and rebasing onto latest main...{CLR_RESET}")
    repo.checkout(lca_sha)  # Detached HEAD at LCA
    repo.branch("feature/notifications")
    repo.checkout("feature/notifications")
    n1 = repo.commit("feat(notif): push notification client", {"notif.py": "send_fcm()"})
    n2 = repo.commit("feat(notif): email batch sender", {"mailer.py": "send_smtp()"})
    repo.display_topology("Notifications Branch Created Off Old Base")

    print(f"\n{CLR_YELLOW}[Executing Rebase: Replaying 'feature/notifications' onto 'main'...]{CLR_RESET}")
    replayed = repo.rebase("main")
    print(f"Replayed commit count: {len(replayed)}")
    print(f"Old SHAs transformed into new rewritten nodes: {replayed}")
    repo.display_topology("Post-Rebase Linear Topology (Clean History Replay)")

    print(f"\n{CLR_BOLD}{CLR_GREEN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}  LAB SIMULATION COMPLETE: ALL TOPOLOGIES SUCCESSFULLY PROCESSED       {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}======================================================================{CLR_RESET}\n")


if __name__ == "__main__":
    run_laboratory_exercise()