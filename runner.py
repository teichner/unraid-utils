#!/usr/bin/env python3

import os
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

class Runner():
    def remove(self, path):
        os.remove(path)

    def run(self, cmd):
        return subprocess.run(cmd)
