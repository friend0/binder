#!/usr/bin/env python3
"""Hashed binder helper: 20 pages x 2 sides x 9 pockets = 360 slots.

Each card name hashes to TWO candidate sides, and the card always lives on one
of them. Finding a card means checking at most two page sides (18 pockets).
The binder itself is the only state: the tool never tracks pockets.

Placing a new card: put it on whichever of its two sides has more room.
If both are full, run `bump` to see which cards could move to their other side.

Usage:
  python3 binder.py where "Sol Ring" ["Mana Vault" ...]  # the two sides for each card
  python3 binder.py layout cards.txt                     # balanced plan for filling a binder from scratch
  python3 binder.py bump "New Card" cards.txt            # both sides full: what can move off them
  python3 binder.py diff old.txt new.txt                 # what left / arrived between two lists

Card lists: plain names, "1x Sol Ring (frc) 21 [Ramp]" lines, or a CSV with a
Name column (and optional Quantity). Basic lands are always skipped.
"""

import csv, hashlib, re, sys, unicodedata
from collections import Counter, deque

PAGES, POCKETS = 20, 9
SIDES = PAGES * 2
SALT = b"binder-v1"  # never change this once cards are placed
BASICS = {"plains", "island", "swamp", "mountain", "forest", "wastes"}
BASICS |= {f"snow-covered {b}" for b in BASICS}
SECTION_HEADERS = {
    "deck", "main", "mainboard", "commander", "commanders", "companion",
    "sideboard", "maybeboard", "considering", "tokens",
}


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


def label(side):
    return f"page {side // 2 + 1} {'front' if side % 2 == 0 else 'back'}"


def both(name):
    a, b = sorted(candidates(name))
    return f"{label(a)} or {label(b)}"


# ---------- card lists ----------


def _csv_rows(path):
    rows = csv.DictReader(open(path, encoding="utf-8-sig", newline=""))
    cols = {c.strip().casefold(): c for c in rows.fieldnames or []}
    name = next((cols[c] for c in ("name", "card name", "card") if c in cols), None)
    qty = next((cols[c] for c in ("quantity", "count", "qty") if c in cols), None)
    if name is None:
        raise SystemExit(f"{path}: CSV has no Name column (found: {', '.join(cols)})")
    for row in rows:
        if row[name].strip():
            yield row[name].strip(), int(row[qty] or 1) if qty else 1


def _text_rows(path):
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        m = re.match(r"(?:(\d+)x?\s+)?(.+?)(?:\s+\([a-z0-9]+\).*)?$", line, re.I)
        qty, name = m.group(1), m.group(2).strip()
        if qty is None and (name.endswith(":") or name.casefold() in SECTION_HEADERS):
            continue  # "Sideboard", "COMMANDER:" etc.
        yield name, int(qty or 1)


def read_list(path):
    """Card names from a list file, one entry per copy, basics removed."""
    with open(path, encoding="utf-8-sig") as f:
        first = f.readline()
    is_csv = path.lower().endswith(".csv") or re.search(r"(^|,)\s*\"?name\"?\s*(,|$)", first, re.I)
    rows = _csv_rows(path) if is_csv else _text_rows(path)
    return [n for n, q in rows for _ in range(q) if not is_basic(n)]


# ---------- placement ----------


def layout(cards):
    """Two-choice placement with cuckoo relocation, in a fixed (name-sorted) order,
    so the same list always gives the same plan. Returns (sides, cards that didn't fit)."""
    sides = [[] for _ in range(SIDES)]
    unplaced = []
    for card in sorted(cards, key=lambda c: (normalize(c), c)):
        a, b = candidates(card)
        prev = {a: None, b: None}
        q = deque([a, b] if len(sides[a]) <= len(sides[b]) else [b, a])
        free = None
        while q:
            s = q.popleft()
            if len(sides[s]) < POCKETS:
                free = s
                break
            for i, x in enumerate(sides[s]):
                xa, xb = candidates(x)
                alt = xb if xa == s else xa
                if alt not in prev:
                    prev[alt] = (s, i)
                    q.append(alt)
        if free is None:
            unplaced.append(card)
            continue
        s = free
        while prev[s] is not None:
            src, i = prev[s]
            sides[s].append(sides[src].pop(i))
            s = src
        sides[s].append(card)
    return sides, unplaced


# ---------- commands ----------


def cmd_where(names):
    for n in names:
        print(f"{n}: {'basic land, not binder' if is_basic(n) else both(n)}")


def cmd_layout(path):
    cards = read_list(path)
    sides, unplaced = layout(cards)
    for s, cs in enumerate(sides):
        print(f"{label(s)} [{len(cs)}/{POCKETS}]")
        for c in sorted(cs, key=normalize):
            print(f"    {c}")
    print(f"\n{len(cards) - len(unplaced)}/{SIDES * POCKETS} slots used")
    if unplaced:
        raise SystemExit(f"Binder full: {len(unplaced)} not placed: " + ", ".join(unplaced))


def cmd_bump(name, path):
    a, b = candidates(name)
    print(f"{name} goes on {label(a)} or {label(b)}. Both full? Move one of these to its other side:")
    for side in (a, b):
        print(f"  on {label(side)}:")
        movable = sorted(
            {c for c in read_list(path) if side in candidates(c)}, key=normalize
        )
        for c in movable:
            ca, cb = candidates(c)
            print(f"    {c} -> {label(cb if ca == side else ca)}")
        if not movable:
            print("    (none of the listed cards belong here; check for strays)")


def cmd_diff(old_path, new_path):
    old, new = read_list(old_path), read_list(new_path)
    display = {normalize(c): c for c in old + new}
    old, new = Counter(map(normalize, old)), Counter(map(normalize, new))
    gone, came = old - new, new - old
    for title, cards in (("Take out", gone), ("Put in", came)):
        print(f"{title} ({sum(cards.values())}):")
        for k in sorted(cards):
            qty = f"{cards[k]}x " if cards[k] > 1 else ""
            print(f"    {qty}{display[k]}: {both(display[k])}")


def main(argv):
    cmd, args = (argv[1], argv[2:]) if len(argv) > 1 else (None, [])
    if cmd == "where" and args:
        cmd_where(args)
    elif cmd == "layout" and len(args) == 1:
        cmd_layout(args[0])
    elif cmd == "bump" and len(args) == 2:
        cmd_bump(*args)
    elif cmd == "diff" and len(args) == 2:
        cmd_diff(*args)
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
