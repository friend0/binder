# Research

How the hashing scheme in `binder.py` was chosen. Nothing here is needed to use the binder.

## Problem

Organize high-value and Commander staple cards in a fixed binder of 360 slots
(40 sides × 9 pockets). The collection changes over time, so placing a card must
not require re-sorting or shifting others, and cards must spread evenly without
manual rebalancing.

## Decisions

- **Not alphabetical ranges.** Card names are not evenly spread across the
  alphabet, so letter ranges overflow (see the table below).
- **Key = normalized card name only.** Hashing on mana value, color, type or
  subtypes adds nothing: they are all functions of the name, and they are
  low-entropy and correlated among staples.
- **Two choices instead of one.** A single hash leaves some sides overfull.
  Giving every card two candidate sides and placing it on the emptier one keeps
  loads nearly flat, at the cost of checking two sides on lookup (≤ 18 pockets).
- **Stateless.** Scanning two sides is cheap, so exact pocket tracking isn't
  worth a state file that must stay in sync with the physical binder. (The
  stateful version with pocket tracking and auto-relocation is commit `821cdeb`.)
- **Hashing happens in code**, so the scheme isn't optimized for mental calculation.

## Evidence

`analyze.py`: 2,000 random collections per size, drawn from 467 unique
non-basic cards (`edhrec_top.txt` and `decklist.txt`).

| Cards | First-letter ranges: overflow | Single hash: displaced | Two-choice: displaced | Two-choice + cuckoo: relocations |
|---|---|---|---|---|
| 200 | 53 | 2.2 | 0 | 0.1 |
| 250 | 88 | 9.7 | 0 | 1.3 |
| 280 | 111 | 19.8 | 0 | 4.2 |
| 300 | 127 | 29.7 | 0.1 | 8.4 |
| 330 | 151 | 49.4 | 2.4 | 19.3 |

- Churn: 250 cards, 1,000 random remove/add swaps → 0 cards off their candidate sides.
- `layout` on the EDHREC list fills 360/360 with 0 cards off their candidate sides.
- Recommended load: about 280–300 cards.

## Files

- `analyze.py`: the simulation. Imports `normalize` and `candidates` from
  `../binder.py`; writes `results.json` here (git-ignored). Run with
  `python3 research/analyze.py` (about 20 seconds).
- `edhrec_top.txt`: about 420 names from EDHREC's top cards (past year) and its
  top lands, creatures, artifacts and instants pages, fetched October 2026.
- `decklist.txt`: a Saruman, the White Hand deck list (Moxfield export).

## Ideas not built

- Validate names in plain-text lists against Scryfall (`/cards/named?fuzzy=`) or
  a local bulk `oracle_cards` file. The web page already does this for lookups.
