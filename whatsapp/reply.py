#!/usr/bin/env python3
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    if len(sys.argv) < 2:
        return
    user_input = sys.argv[1]
    from brain.router import route
    response, _ = route(user_input)
    print(response)

if __name__ == "__main__":
    main()
