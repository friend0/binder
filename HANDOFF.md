# Handoff: Hashed MTG Binder Organizer

## Goal
Organize high-value / Commander staple Magic: The Gathering cards in a **fixed-size binder**:
20 pages × 2 sides × 3×3 pockets = **40 sides × 9 pockets = 360 slots**.
The collection is **dynamic** (cards added/removed over time), so placement must not require
re-sorting or shifting cards, and must spread cards evenly without manual rebalancing.

## User constraints / preferences (important)
- Hashing is computed **in code**, not by hand. Do not optimize for mental calculation.
- MTG names are **not** evenly distributed alphabetically; range/alphabetical partitioning was rejected.
- User raised hashing on attributes (mana value, color, type, subtypes). Conclusion: every attribute
  is a function of the card name, so with a real hash they add no distribution benefit; they are also
  low-entropy and correlated among staples. **Key = normalized card name.**
- Design inputs: EDHREC top cards + the user's Saruman, the White Hand (Grixis) deck list.

## Chosen design: two-choice hashing with cuckoo relocation
- `normalize(name)`: front face only (split on `" // "`), Unicode NFKD with accents stripped
  (`Barad-dûr` → `barad-dur`), casefold, curly apostrophe → `'`, whitespace collapsed.
  All printings of a card hash identically.
- `candidates(name)`: BLAKE2b-128 keyed with salt `b"binder-v1"`; bytes 0–7 mod 40 → side A,
  bytes 8–15 mod 40 → side B (forced distinct from A).
- **Insert:** put the card in whichever candidate side has fewer cards (tie → A), first empty pocket.
  If both are full, BFS for the shortest chain of relocations (each moved card goes to its *other*
  candidate side) ending at a side with space; apply the moves and report them to the user.
- **Invariant:** every card is always on one of its two candidate sides → lookup ≤ 2 page sides
  (and the tool records the exact pocket).
- Side index `s` (0–39) → `page s//2 + 1`, even = front, odd = back. Pockets are 1–9 for display.
- **Never change** `SALT`, `PAGES`, or `POCKETS` once cards are placed (would remap everything).
  If a migration is ever needed, write an explicit re-layout command that outputs a move list.

## Evidence (analyze.py, 2,000 random collections per size from 467 unique non-basic cards)
| Cards | First-letter ranges: overflow | Single hash: displaced | Two-choice: displaced | Two-choice+cuckoo: relocations |
|---|---|---|---|---|
| 200 | 53 | 2.2 | 0 | 0.1 |
| 250 | 88 | 9.7 | 0 | 1.4 |
| 280 | 111 | 19.8 | 0.01 | 4.4 |
| 300 | 127 | 29.7 | 0.1 | 8.6 |
| 330 | 151 | 49.4 | 2.6 | 19.6 |

- Churn test: 250 cards, 1,000 random remove/add swaps → 0 cards off their candidate sides.
- Real fill test of binder.py: 324 cards placed with 1 relocation; filled to 357/360 before refusing;
  0 invariant violations.
- Recommended operating load: ~280–300 cards.

## Files
- `binder.py` — CLI manager (stdlib only, Python 3). State in `binder.json` beside the script
  (override with env `BINDER_FILE`). State format: `{"salt": "...", "sides": [[name|null × 9] × 40]}`.
  Commands: `add NAME...`, `remove NAME...`, `find NAME...` (shows candidate sides if absent),
  `import FILE` (accepts `1x Sol Ring (frc) 21 [Ramp]` lines or plain names; quantities create
  separate copies; section headers like `Sideboard` / `COMMANDER:` are skipped), `show`, `stats`.
  Basic lands (incl. snow-covered) are always skipped: the user will never binder them.
  On "binder full", import keeps trying the remaining cards, saves, and lists what didn't fit.
  `remove` saves the successful removals and lists names not found (exit 1).
  Relocation moves print in physical order: each move targets a pocket that is already empty.
  On load, refuses to run if the file's salt/side count differs from the script's.
  Saves are atomic; the previous state is kept as `binder.json.bak`.
  `normalize` also maps `æ` → `ae` (Æther Vial == Aether Vial).
- `analyze.py` — simulation comparing first-letter ranges, single hash + linear probing,
  two-choice, and cuckoo. Imports `normalize`/`candidates` from `binder.py` (one source of truth).
  Reads `edhrec_top.txt` and `decklist.txt` next to the script; writes `results.json` there.
  (Evidence table above predates sharing the hash; numbers may shift slightly if re-run.)
- `flake.nix` — `nix develop` gives a Python 3.12 env (stdlib only; add packages in
  `python312.withPackages`).
- `edhrec_top.txt` — ~470 names from EDHREC top cards (past year) + top lands/creatures/artifacts/
  instants pages (fetched Oct 2026).
- `decklist.txt` — user's deck list (Moxfield-style export).

## Known limitations / open items
- No card-name validation: typos create bogus entries. Next step idea: validate against Scryfall
  (`/cards/named?fuzzy=`) or a local Scryfall bulk `oracle_cards` file. (The original sandbox
  could not reach Scryfall/EDHREC from the shell; the user's machine likely can.)
- `remove` with duplicates removes the first copy found; no per-copy identity (foil, printing, etc.).
- Pocket order within a side is arbitrary (first empty pocket); no in-side sorting.
- No undo / move log beyond the single `.bak` (consider an append-only log).
- Offered but not built: a phone-friendly web UI (search/add/remove) for use at the table.
