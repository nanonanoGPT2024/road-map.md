#!/usr/bin/env python3
"""
Lab Hands-on: Trees & Hierarchical State Traversal (LeetCode Deep Dive)
Focus:
  1. LeetCode-compliant Level-Order Serializer/Deserializer (LC 297).
  2. O(1) Auxiliary Space Morris Inorder Traversal (Threaded Binary Tree).
  3. Post-Order Hierarchical State Aggregation: Diameter (LC 543) & Lowest Common Ancestor (LC 236).
  4. Large-Scale Benchmark: Iterative DFS vs BFS vs Morris Traversal on 32,767-node Trees.
"""

import sys
import time
from collections import deque
from typing import Optional, List, Tuple

# Terminal ANSI Styling
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"


class TreeNode:
    """Standard LeetCode Binary Tree Node."""
    def __init__(self, val: int = 0, left: Optional['TreeNode'] = None, right: Optional['TreeNode'] = None):
        self.val = val
        self.left = left
        self.right = right

    def __repr__(self) -> str:
        return f"TreeNode({self.val})"


class TreeCodec:
    """
    LeetCode 297: Serialize and Deserialize Binary Tree.
    Implements standard BFS level-order serialization using sentinel 'null'.
    """

    @staticmethod
    def serialize(root: Optional[TreeNode]) -> str:
        """Serializes a tree to a single comma-delimited string."""
        if not root:
            return "[]"
        
        result: List[str] = []
        queue = deque([root])
        
        while queue:
            node = queue.popleft()
            if node:
                result.append(str(node.val))
                queue.append(node.left)
                queue.append(node.right)
            else:
                result.append("null")
        
        # Strip trailing 'null' entries to match standard LeetCode compact form
        while result and result[-1] == "null":
            result.pop()
            
        return "[" + ",".join(result) + "]"

    @staticmethod
    def deserialize(data: str) -> Optional[TreeNode]:
        """Deserializes comma-delimited string representation to binary tree."""
        if not data or data == "[]":
            return None
        
        tokens = data.strip("[]").split(",")
        if not tokens or tokens[0] == "null" or tokens[0] == "":
            return None

        root = TreeNode(int(tokens[0]))
        queue = deque([root])
        i = 1
        n = len(tokens)

        while queue and i < n:
            curr = queue.popleft()

            # Process left child
            if i < n and tokens[i] != "null":
                curr.left = TreeNode(int(tokens[i]))
                queue.append(curr.left)
            i += 1

            # Process right child
            if i < n and tokens[i] != "null":
                curr.right = TreeNode(int(tokens[i]))
                queue.append(curr.right)
            i += 1

        return root


class TreeAlgorithms:
    """Hierarchical state traversal and structural analysis algorithms."""

    @staticmethod
    def morris_inorder_traversal(root: Optional[TreeNode]) -> List[int]:
        """
        Morris Traversal achieves Inorder Traversal with O(1) Auxiliary Space.
        Temporarily threads the rightmost node of the left subtree (inorder predecessor)
        to point to the current root, avoiding recursive or explicit stack memory.
        Guarantees complete restoration of tree topology upon completion.
        """
        traversal: List[int] = []
        curr = root

        while curr:
            if curr.left is None:
                # No left subtree: visit current and step right
                traversal.append(curr.val)
                curr = curr.right
            else:
                # Find inorder predecessor (rightmost node in left subtree)
                predecessor = curr.left
                while predecessor.right is not None and predecessor.right is not curr:
                    predecessor = predecessor.right

                if predecessor.right is None:
                    # Establish temporary backlink (threading)
                    predecessor.right = curr
                    curr = curr.left
                else:
                    # Thread already exists: revert backlink, visit current, step right
                    predecessor.right = None
                    traversal.append(curr.val)
                    curr = curr.right

        return traversal

    @staticmethod
    def calculate_diameter(root: Optional[TreeNode]) -> int:
        """
        LeetCode 543: Diameter of Binary Tree.
        Post-order traversal aggregating depth states bottom-up.
        Returns the longest path (number of edges) between any two nodes.
        """
        max_diameter = 0

        def max_depth(node: Optional[TreeNode]) -> int:
            nonlocal max_diameter
            if not node:
                return 0
            
            # Post-order hierarchical evaluation
            left_d = max_depth(node.left)
            right_d = max_depth(node.right)

            # Path passing through current node
            max_diameter = max(max_diameter, left_d + right_d)

            # Propagate height to parent
            return 1 + max(left_d, right_d)

        max_depth(root)
        return max_diameter

    @staticmethod
    def lowest_common_ancestor(root: Optional[TreeNode], p: int, q: int) -> Optional[TreeNode]:
        """
        LeetCode 236: Lowest Common Ancestor of a Binary Tree.
        Traverses hierarchy top-down, bubbling matches upward via divide-and-conquer.
        """
        if not root or root.val == p or root.val == q:
            return root

        left = TreeAlgorithms.lowest_common_ancestor(root.left, p, q)
        right = TreeAlgorithms.lowest_common_ancestor(root.right, p, q)

        # Discovered targets in opposing subtrees -> current node is the LCA
        if left and right:
            return root

        # Return non-null branch
        return left if left else right


def generate_perfect_tree(depth: int, node_id: int = 1) -> Optional[TreeNode]:
    """Generates a balanced binary tree of a given depth recursively."""
    if depth <= 0:
        return None
    node = TreeNode(node_id)
    node.left = generate_perfect_tree(depth - 1, node_id * 2)
    node.right = generate_perfect_tree(depth - 1, node_id * 2 + 1)
    return node


def benchmark_traversals(root: TreeNode, total_nodes: int):
    """Benchmarks iterative DFS (stack), BFS (deque), and Morris Traversal (O(1) space)."""
    print(f"\n{BOLD}{CYAN}=== Benchmarking Tree Traversal Paradigms ({total_nodes:,} nodes) ==={RESET}")

    # 1. BFS Level-Order
    start = time.perf_counter()
    bfs_result = []
    q = deque([root])
    while q:
        curr = q.popleft()
        bfs_result.append(curr.val)
        if curr.left:
            q.append(curr.left)
        if curr.right:
            q.append(curr.right)
    bfs_time = (time.perf_counter() - start) * 1000

    # 2. Iterative Inorder DFS (Stack-based: O(H) auxiliary space)
    start = time.perf_counter()
    stack_result = []
    stack = []
    curr = root
    while curr or stack:
        while curr:
            stack.append(curr)
            curr = curr.left
        curr = stack.pop()
        stack_result.append(curr.val)
        curr = curr.right
    dfs_time = (time.perf_counter() - start) * 1000

    # 3. Morris Inorder Traversal (O(1) auxiliary space, destructive & restorative)
    start = time.perf_counter()
    morris_result = TreeAlgorithms.morris_inorder_traversal(root)
    morris_time = (time.perf_counter() - start) * 1000

    assert stack_result == morris_result, "Morris Traversal verification failed!"

    print(f"  {YELLOW}Standard BFS (Level-Order)   {RESET}: {bfs_time:7.2f} ms | Aux Space: O(W) [Queue]")
    print(f"  {YELLOW}Iterative DFS (Stack Inorder){RESET}: {dfs_time:7.2f} ms | Aux Space: O(H) [Stack]")
    print(f"  {GREEN}Morris Inorder Traversal     {RESET}: {morris_time:7.2f} ms | Aux Space: {BOLD}O(1){RESET} [Pointers]")
    print(f"  {MAGENTA}Integrity Check              {RESET}: {GREEN}PASSED (Morris matched Stack traversal exact sequence){RESET}")


def run_laboratory():
    """Main lab execution routine."""
    print(f"{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE} LAB 06: TREES & HIERARCHICAL STATE TRAVERSAL (DEEP DIVE)             {RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")

    # Test 1: Serialization / Deserialization (LeetCode 297)
    sample_repr = "[1,2,3,null,null,4,5]"
    print(f"\n{BOLD}{CYAN}[Step 1] LeetCode Serialization & Deserialization Engine{RESET}")
    print(f"  Input String        : {sample_repr}")
    
    root = TreeCodec.deserialize(sample_repr)
    serialized_output = TreeCodec.serialize(root)
    print(f"  Serialized Output   : {serialized_output}")
    assert sample_repr == serialized_output, "Tree serialization cycle failed!"
    print(f"  Codec Fidelity      : {GREEN}VERIFIED (Lossless Reconstruction){RESET}")

    # Test 2: Hierarchical State Aggregations (Diameter & LCA)
    print(f"\n{BOLD}{CYAN}[Step 2] Hierarchical State Aggregations (Diameter & LCA){RESET}")
    # Tree:
    #         1
    #        / \
    #       2   3
    #      / \
    #     4   5
    #        /
    #       6
    ext_tree_data = "[1,2,3,4,5,null,null,null,null,6]"
    ext_root = TreeCodec.deserialize(ext_tree_data)
    
    diameter = TreeAlgorithms.calculate_diameter(ext_root)
    lca_4_6 = TreeAlgorithms.lowest_common_ancestor(ext_root, 4, 6)
    lca_6_3 = TreeAlgorithms.lowest_common_ancestor(ext_root, 6, 3)

    print(f"  Tree Structure      : {ext_tree_data}")
    print(f"  Computed Diameter   : {YELLOW}{diameter}{RESET} edges")
    print(f"  LCA of (Node 4, 6)  : Node {GREEN}{lca_4_6.val if lca_4_6 else 'None'}{RESET} (Expected: 2)")
    print(f"  LCA of (Node 6, 3)  : Node {GREEN}{lca_6_3.val if lca_6_3 else 'None'}{RESET} (Expected: 1)")

    # Test 3: Large-Scale Benchmark on Deep Hierarchies
    tree_depth = 15
    total_nodes = (2 ** tree_depth) - 1
    print(f"\n{BOLD}{CYAN}[Step 3] Synthetic Large-Scale Hierarchy Generation{RESET}")
    print(f"  Generating Perfect Binary Tree of depth {tree_depth} ({total_nodes:,} nodes)...")
    
    large_root = generate_perfect_tree(tree_depth)
    assert large_root is not None

    benchmark_traversals(large_root, total_nodes)

    print(f"\n{BOLD}{GREEN}All tree algorithms executed with algorithmic integrity.{RESET}\n")


if __name__ == "__main__":
    # Expand recursion depth for deep hierarchical state exploration
    sys.setrecursionlimit(50000)
    run_laboratory()