#!/usr/bin/env python3
"""
Lab Hands-on: Git Core Architecture & Plumbing vs. Porcelain Deep Dive
Kategori: 01-Core-Foundations, Bab 01 - Modul 02

Script ini mensimulasikan implementasi internal Git dari tingkat byte-level:
1. Object Storage (Blob, Tree, Commit) dengan SHA-1 hashing & zlib compression.
2. Direct Plumbing Operations: hash-object, cat-file, write-tree, commit-tree, update-ref.
3. Porcelain Abstraction Layer: git init, git add, git commit, git log.
4. Verifikasi DAG (Directed Acyclic Graph) dan visualisasi perbedaan arsitektur.
"""

import os
import sys
import time
import zlib
import hashlib
import tempfile
import binascii
from typing import Dict, List, Tuple, Optional

# ANSI Color Codes untuk visualisasi terminal
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_CYAN   = "\033[96m"
CLR_GREEN  = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE   = "\033[94m"
CLR_MAG    = "\033[95m"
CLR_RED    = "\033[91m"

class MiniGitEngine:
    """
    Simulasi engine internal Git yang membedakan Plumbing (low-level primitives)
    dan Porcelain (high-level user commands).
    """

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.git_dir = os.path.join(base_dir, ".minigit")
        self.objects_dir = os.path.join(self.git_dir, "objects")
        self.refs_dir = os.path.join(self.git_dir, "refs")
        self.heads_dir = os.path.join(self.refs_dir, "heads")
        self.index_file = os.path.join(self.git_dir, "index")
        self.head