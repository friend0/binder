# binder

Find any Magic card in a 360-pocket binder by checking at most two page sides.

The binder has 20 pages × 2 sides × 9 pockets. Each card name hashes to two
candidate sides, and the card always lives on one of them. Cards are never
sorted or shifted: a new card goes on whichever of its two sides has more room.
The physical binder is the only state; no tool tracks pockets.

## Web page

**https://friend0.github.io/binder/** (from `docs/`). On a phone, add it to the home screen.

- **Find a card:** type a name (checked on Scryfall) to see its two sides.
- **Changes from an export:** load a ManaBox CSV export to see what to put in and
  take out since the baseline, alphabetical, with sides. "Baseline from repo"
  uses the newest file in `exports/`; the baseline is then kept in that browser.

## Command line

Python 3, standard library only (`nix develop` gives a shell with Python and Node).

```sh
python3 binder.py where "Sol Ring" "Mana Vault"   # the two sides for each card
python3 binder.py diff exports/OLD.csv exports/NEW.csv  # what to take out and put in
python3 binder.py layout cards.csv                # plan for filling an empty binder
python3 binder.py bump "New Card" cards.csv       # both sides full: what can move off them
```

Lists can be ManaBox CSV exports (only `Name` and `Quantity` are used), plain
names, or `1x Sol Ring (frc) 21` lines. Basic lands are always skipped.

## Exports

`exports/YYYY-MM-DD.csv` are ManaBox exports of the binder, one per scanning
session, stored byte-for-byte and named by export date. The newest is the
baseline. `2026-10-13.layout.txt` is the plan the binder was first filled from.

## How it works

- **Key:** the card's front-face name, with accents stripped, case folded and
  whitespace collapsed, so every printing hashes the same.
- **Hash:** BLAKE2b-128 keyed with `binder-v1`. Bytes 0–7 mod 40 give side A,
  bytes 8–15 mod 40 give side B (forced different from A).
- **Side numbers:** side `s` (0–39) is page `s // 2 + 1`; even is the front, odd the back.
- `layout` places cards in name order with two-choice and cuckoo relocation, so
  the same list always gives the same plan.

Never change the salt, page count or pocket count once cards are placed: every
card would move.

`docs/binder.js` reimplements the hashing for the browser. After changing either
version, run `python3 check_web.py` (needs Node) to confirm they agree.

Design notes and the simulation behind the choices are in [`research/`](research/).
