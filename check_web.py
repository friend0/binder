#!/usr/bin/env python3
"""Check that docs/binder.js gives the same sides as binder.py.

Usage:
  python3 check_web.py [names.txt ...]   # default: exports/*.csv and research/ lists

Needs node. Exit 1 on any mismatch.
"""

import glob, json, os, subprocess, sys

from binder import candidates, normalize, read_list

HERE = os.path.dirname(os.path.abspath(__file__))
JS = """
const B = require(process.argv[1]);
const names = JSON.parse(require("fs").readFileSync(0, "utf8"));
console.log(JSON.stringify(names.map((n) => [B.normalize(n), B.candidates(n)])));
"""


def main(paths):
    paths = paths or sorted(glob.glob(os.path.join(HERE, "exports", "*.csv"))) + [
        os.path.join(HERE, "research", "edhrec_top.txt"),
        os.path.join(HERE, "research", "decklist.txt"),
    ]
    paths = [p for p in paths if os.path.exists(p)]
    names = sorted({n for p in paths for n in read_list(p)})
    out = subprocess.run(
        ["node", "-e", JS, os.path.join(HERE, "docs", "binder.js")],
        input=json.dumps(names), capture_output=True, text=True, check=True,
    ).stdout
    bad = 0
    for n, (norm, sides) in zip(names, json.loads(out)):
        if norm != normalize(n) or tuple(sides) != candidates(n):
            bad += 1
            print(f"MISMATCH {n!r}: py {normalize(n)!r} {candidates(n)} / js {norm!r} {tuple(sides)}")
    print(f"{len(names) - bad}/{len(names)} names match")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
