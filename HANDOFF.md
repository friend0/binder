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

## Chosen design: stateless two-choice hashing (user places cards)
- `normalize(name)`: front face only (split on `" // "`), Unicode NFKD with accents stripped
  (`Barad-dûr` → `barad-dur`), `æ` → `ae`, casefold, curly apostrophe → `'`, whitespace collapsed.
  All printings of a card hash identically.
- `candidates(name)`: BLAKE2b-128 keyed with salt `b"binder-v1"`; bytes 0–7 mod 40 → side A,
  bytes 8–15 mod 40 → side B (forced distinct from A).
- **Invariant:** every card is on one of its two candidate sides → lookup = scan ≤ 18 pockets.
- **No state file.** The physical binder is the state. User decision (Oct 2026): scanning two
  sides is cheap, so exact pocket tracking isn't worth a `binder.json` that must stay in sync.
  (The stateful version with pocket tracking and auto-relocation is commit `821cdeb`.)
- **Placing:** the user puts a new card on whichever of its two sides has more room.
  Both full (rare at ≤300 cards) → `bump` lists cards that may be on those sides and their
  other side; the user moves one that is physically there.
- **First fill:** `layout` gives a deterministic plan (cards processed in name-sorted order,
  two-choice + cuckoo BFS), so the same list always yields the same plan regardless of list order.
- Side index `s` (0–39) → `page s//2 + 1`, even = front, odd = back.
- **Never change** `SALT`, `PAGES`, or `POCKETS` once cards are placed (would remap everything).

## Evidence (analyze.py, 2,000 random collections per size from 467 unique non-basic cards)
| Cards | First-letter ranges: overflow | Single hash: displaced | Two-choice: displaced | Two-choice+cuckoo: relocations |
|---|---|---|---|---|
| 200 | 53 | 2.2 | 0 | 0.1 |
| 250 | 88 | 9.7 | 0 | 1.4 |
| 280 | 111 | 19.8 | 0.01 | 4.4 |
| 300 | 127 | 29.7 | 0.1 | 8.6 |
| 330 | 151 | 49.4 | 2.6 | 19.6 |

- Churn test: 250 cards, 1,000 random remove/add swaps → 0 cards off their candidate sides.
- `layout` on the 420-name EDHREC list fills 360/360 with 0 cards off their candidate sides.
- Recommended operating load: ~280–300 cards.

## Files
- `binder.py` — CLI (stdlib only, Python 3). Commands:
  - `where NAME...` — the two sides for each card.
  - `layout FILE` — page-by-page fill plan (cards alphabetical within a side); exit 1 + list if >360.
  - `bump NAME FILE` — for a card whose two sides are full, which cards in FILE could move off them.
  - `diff OLD NEW` — multiset diff of two lists (matched by normalized name): take out / put in,
    with each card's two sides. Intended for consecutive ManaBox exports of the binder.
  - Lists: plain names, `1x Sol Ring (frc) 21 [Ramp]` lines (section headers skipped), or CSV with
    a `Name` column and optional `Quantity`. Basic lands (incl. snow-covered) are always skipped:
    the user will never binder them.
- `analyze.py` — simulation comparing first-letter ranges, single hash + linear probing,
  two-choice, and cuckoo. Imports `normalize`/`candidates` from `binder.py` (one source of truth).
  Reads `edhrec_top.txt` and `decklist.txt` next to the script; writes `results.json` there.
  (Evidence table predates sharing the hash; numbers may shift slightly if re-run.)
- `flake.nix` — `nix develop` gives a Python 3.12 env (stdlib only; add packages in
  `python312.withPackages`).
- `edhrec_top.txt` — ~420 names from EDHREC top cards (past year) + top lands/creatures/artifacts/
  instants pages (fetched Oct 2026).
- `decklist.txt` — user's deck list (Moxfield-style export).

## Known limitations / open items
- **ManaBox CSV format is unverified.** The CSV reader accepts any header with Name / Card Name
  and optional Quantity / Count / Qty. ManaBox only documents its *import* columns. When the user
  has a real export, check its header and test `diff`/`layout` on it.
- No card-name validation for plain-text lists (ManaBox exports should already be canonical).
  Idea: Scryfall `/cards/named?fuzzy=` or a local bulk `oracle_cards` file.
- Offered but not built: a phone-friendly web UI (`where` lookup) for use at the table.
