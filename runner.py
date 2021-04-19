#!/usr/bin/env python3

import os
import os.path
import subprocess
from dataclasses import dataclass

@dataclass
class FakeCompletedProcess:
    args: list
    returncode: int

class DryRunner():
    def remove(self, path):
        print(f"Removing {path}")

    def run(self, cmd):
        print(' '.join(cmd))
        return FakeCompletedProcess(args=cmd, returncode=0)

    def copy(self, src, dst):
        print(f"Copying {src} to {dst}")

class Runner():
    def remove(self, path):
        os.remove(path)

    def run(self, cmd):
        return subprocess.run(cmd)

    def copy(self, src, dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.copy(src, dst)
