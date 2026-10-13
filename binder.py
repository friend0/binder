#!/usr/bin/env python3
"""Hashed binder manager: 20 pages x 2 sides x 9 pockets = 360 slots.

Each card name hashes to TWO candidate sides. A new card goes into whichever
candidate side is emptier. If both are full, existing cards are relocated to
their other candidate side (cuckoo hashing) so the invariant always holds:

    every card is on one of its two hashed sides.

So finding any card means checking at most two page sides, and the tool tells
you the exact pocket anyway. Basic lands are never stored.

Usage:
  python3 binder.py add "Sol Ring" ["Mana Vault" ...]
  python3 binder.py remove "Sol Ring"
  python3 binder.py find "Sol Ring"
  python3 binder.py import decklist.txt      # lines like "1x Sol Ring (frc) 21 [Ramp]" or plain names
  python3 binder.py show                     # full binder map
  python3 binder.py stats

State lives in binder.json next to this script (override with BINDER_FILE).
The previous state is kept as binder.json.bak on every save.
"""

import hashlib, json, os, re, sys, unicodedata
from collections import deque

PAGES, POCKETS = 20, 9
SIDES = PAGES * 2
SALT = b"binder-v1"  # never change this once cards are placed
STATE = os.environ.get(
    "BINDER_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "binder.json"),
)
BASICS = {"plains", "island", "swamp", "mountain", "forest", "wastes"}
BASICS |= {f"snow-covered {b}" for b in BASICS}
SECTION_HEADERS = {
    "deck", "main", "mainboard", "commander", "commanders", "companion",
    "sideboard", "maybeboard", "considering", "tokens",
}


class BinderFull(Exception):
    pass


def normalize(name):
    name = name.split(" // ")[0]
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.casefold().replace("’", "'").replace("æ", "ae")
    return re.sub(r"\s+", " ", name).strip()


def is_basic(name):
    return normalize(name) in BASICS


def candidates(name):
    d = hashlib.blake2b(normalize(name).encode(), key=SALT, digest_size=16).digest()
    a = int.from_bytes(d[:8], "big") % SIDES
    b = int.from_bytes(d[8:], "big") % SIDES
    if b == a:  # make sure the two choices differ
        b = (a + 1 + int.from_bytes(d[8:], "big") % (SIDES - 1)) % SIDES
    return a, b


def label(side, pocket=None):
    s = f"page {side // 2 + 1} {'front' if side % 2 == 0 else 'back'}"
    return s if pocket is None else f"{s}, pocket {pocket + 1}"


class Binder:
    def __init__(self):
        self.sides = [[None] * POCKETS for _ in range(SIDES)]
        if os.path.exists(STATE):
            state = json.load(open(STATE, encoding="utf-8"))
            if state.get("salt") != SALT.decode() or len(state["sides"]) != SIDES:
                raise SystemExit(
                    f"{STATE} was laid out with salt {state.get('salt')!r} and "
                    f"{len(state['sides'])} sides; this script uses {SALT.decode()!r} and "
                    f"{SIDES}. Refusing to run: lookups would point to the wrong pages."
                )
            self.sides = state["sides"]

    def save(self):
        # keep the previous state as a backup, then swap in the new file atomically
        if os.path.exists(STATE):
            os.replace(STATE, STATE + ".bak")
        tmp = STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {"salt": SALT.decode(), "sides": self.sides},
                f,
                indent=1,
                ensure_ascii=False,
            )
        os.replace(tmp, STATE)

    def count(self, s):
        return sum(x is not None for x in self.sides[s])

    def locate(self, name):
        key = normalize(name)
        return [
            (s, p)
            for s in candidates(name)
            for p, x in enumerate(self.sides[s])
            if x and normalize(x) == key
        ]

    def _put(self, s, card):
        p = self.sides[s].index(None)
        self.sides[s][p] = card
        return p

    def add(self, card):
        a, b = candidates(card)
        if self.count(a) < POCKETS or self.count(b) < POCKETS:
            s = a if self.count(a) <= self.count(b) else b
            return s, self._put(s, card), []
        # both full: BFS for the shortest chain of relocations
        prev = {a: None, b: None}
        q = deque([a, b])
        free = None
        while q:
            s = q.popleft()
            if self.count(s) < POCKETS:
                free = s
                break
            for p, x in enumerate(self.sides[s]):
                xa, xb = candidates(x)
                alt = xb if xa == s else xa
                if alt not in prev:
                    prev[alt] = (s, p)
                    q.append(alt)
        if free is None:
            raise BinderFull(f"No room for {card}: binder is effectively full.")
        # walk back from the free side; each move fills the pocket the previous one emptied
        moves, s = [], free
        while prev[s] is not None:
            src, p = prev[s]
            x = self.sides[src][p]
            self.sides[src][p] = None
            np = self._put(s, x)
            moves.append(f"move {x}: {label(src, p)} -> {label(s, np)}")
            s = src
        return s, self._put(s, card), moves

    def remove(self, name):
        hits = self.locate(name)
        if not hits:
            return None
        s, p = hits[0]
        card = self.sides[s][p]
        self.sides[s][p] = None
        return card, s, p


def parse_list(path):
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        m = re.match(r"(?:(\d+)x?\s+)?(.+?)(?:\s+\([a-z0-9]+\).*)?$", line, re.I)
        qty, name = m.group(1), m.group(2).strip()
        if qty is None and (name.endswith(":") or name.casefold() in SECTION_HEADERS):
            continue  # "Sideboard", "COMMANDER:" etc.
        for _ in range(int(qty or 1)):
            yield name


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return
    cmd, args = argv[1], argv[2:]
    b = Binder()
    if cmd in ("add", "import"):
        names = list(parse_list(args[0])) if cmd == "import" else args
        basics = [n for n in names if is_basic(n)]
        if basics:
            print(f"skipped {len(basics)} basic land(s)")
        failed = []
        for n in names:
            if is_basic(n):
                continue
            try:
                s, p, moves = b.add(n)
            except BinderFull:
                failed.append(n)
                continue
            for m in moves:
                print("  " + m)
            print(f"{n}: {label(s, p)}")
        b.save()
        if failed:
            raise SystemExit(
                f"Binder full: {len(failed)} card(s) not added: " + ", ".join(failed)
            )
    elif cmd == "remove":
        missing = []
        for n in args:
            hit = b.remove(n)
            if hit is None:
                missing.append(n)
                continue
            card, s, p = hit
            print(f"removed {card} from {label(s, p)}")
        b.save()
        if missing:
            raise SystemExit("not in the binder: " + ", ".join(missing))
    elif cmd == "find":
        for n in args:
            hits = b.locate(n)
            if hits:
                print(f"{n}: " + "; ".join(label(s, p) for s, p in hits))
            else:
                print(
                    f"{n}: not in binder (would go on {label(candidates(n)[0])} or {label(candidates(n)[1])})"
                )
    elif cmd == "show":
        for s in range(SIDES):
            cards = [x or "-" for x in b.sides[s]]
            print(f"{label(s):<16} [{b.count(s)}/9]  " + " | ".join(cards))
    elif cmd == "stats":
        loads = [b.count(s) for s in range(SIDES)]
        print(
            f"{sum(loads)}/{SIDES * POCKETS} slots used; per-side min {min(loads)}, max {max(loads)}"
        )
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
