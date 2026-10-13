"""Compare placement strategies for a 40-side x 9-slot binder using real card names."""

import random, re, statistics, collections, json, os

# share the exact hash and normalization the real binder uses
from binder import BASICS, SIDES, POCKETS as CAP, normalize, candidates as hashes

HERE = os.path.dirname(os.path.abspath(__file__))


def load_pool():
    names = set()
    for line in open(os.path.join(HERE, "edhrec_top.txt"), encoding="utf-8"):
        if line.strip():
            names.add(line.strip())
    deck = set()
    for line in open(os.path.join(HERE, "decklist.txt"), encoding="utf-8"):
        m = re.match(r"\d+x (.+?) \(", line)
        if m:
            deck.add(m.group(1))
    names |= deck
    pool = {}
    for n in names:
        k = normalize(n)
        if k not in BASICS:
            pool[k] = n
    return sorted(pool.values()), deck


# ---------- strategies: each returns (placement dict name->side, extra stats) ----------


def first_letter(cards):
    # naive range partition: letters spread evenly over sides (what attribute/alpha keys look like)
    demand = collections.Counter()
    for c in cards:
        ch = normalize(c)[0]
        idx = ord(ch) - 97 if ch.isalpha() else 0
        demand[idx * SIDES // 26] += 1
    return demand


def single_hash(cards):
    load = [0] * SIDES
    displaced = 0
    worst = 0
    for c in cards:
        h, _ = hashes(c)
        steps = 0
        while load[(h + steps) % SIDES] >= CAP:
            steps += 1
        load[(h + steps) % SIDES] += 1
        displaced += steps > 0
        worst = max(worst, steps + 1)
    return load, displaced, worst


def two_choice(cards):
    load = [0] * SIDES
    displaced = 0
    worst = 0
    for c in cards:
        a, b = hashes(c)
        if load[a] < CAP or load[b] < CAP:
            tgt = a if load[a] <= load[b] else b
            load[tgt] += 1
            worst = max(worst, 2)
        else:
            steps = 1
            while load[(a + steps) % SIDES] >= CAP:
                steps += 1
            load[(a + steps) % SIDES] += 1
            displaced += 1
            worst = max(worst, steps + 2)
    return load, displaced, worst


def cuckoo(cards):
    """Every card lives in one of its two sides; insert may relocate other cards (BFS shortest path)."""
    side_cards = [[] for _ in range(SIDES)]
    choices = {}
    moves = 0
    failed = 0
    for c in cards:
        choices[c] = hashes(c)
        a, b = choices[c]
        # BFS over sides: find a path from {a,b} to a side with free space
        prev = {a: None, b: None}
        queue = [a, b]
        found = None
        while queue:
            s = queue.pop(0)
            if len(side_cards[s]) < CAP:
                found = s
                break
            for x in side_cards[s]:
                xa, xb = choices[x]
                alt = xb if xa == s else xa
                if alt not in prev:
                    prev[alt] = (s, x)
                    queue.append(alt)
        if found is None:
            failed += 1
            continue
        s = found
        while prev[s] is not None:  # shift cards along the path
            src, x = prev[s]
            side_cards[src].remove(x)
            side_cards[s].append(x)
            moves += 1
            s = src
        side_cards[s].append(c)
    return [len(x) for x in side_cards], moves, failed


def main():
    pool, deck = load_pool()
    print(f"pool: {len(pool)} unique non-basic cards ({len(deck)} deck entries)")
    rng = random.Random(7)
    trials = 2000
    out = {}
    for n in (150, 200, 250, 280, 300, 330):
        if n > len(pool):
            continue
        r = collections.defaultdict(list)
        for _ in range(trials):
            cards = rng.sample(pool, n)
            fl = first_letter(cards)
            r["fl_max"].append(max(fl.values()))
            r["fl_over"].append(sum(max(0, v - CAP) for v in fl.values()))
            load, disp, worst = single_hash(cards)
            r["s_disp"].append(disp)
            r["s_worst"].append(worst)
            load, disp, worst = two_choice(cards)
            r["t_disp"].append(disp)
            r["t_worst"].append(worst)
            load, moves, failed = cuckoo(cards)
            r["c_moves"].append(moves)
            r["c_fail"].append(failed)
        mean = lambda k: statistics.mean(r[k])
        out[n] = {k: round(mean(k), 2) for k in r} | {
            "s_worst_max": max(r["s_worst"]),
            "t_worst_max": max(r["t_worst"]),
            "c_fail_rate": sum(1 for x in r["c_fail"] if x) / trials,
        }
        print(n, out[n])

    # churn: hold ~250 cards, swap one out / one in 1000 times (two-choice, no cleanup)
    rng = random.Random(11)
    cards = rng.sample(pool, 250)
    rest = [c for c in pool if c not in set(cards)]
    load = [0] * SIDES
    where = {}

    def place(c):
        a, b = hashes(c)
        if load[a] < CAP or load[b] < CAP:
            t = a if load[a] <= load[b] else b
        else:
            t = next(
                (a + s) % SIDES for s in range(1, SIDES) if load[(a + s) % SIDES] < CAP
            )
        load[t] += 1
        where[c] = t

    for c in cards:
        place(c)
    for _ in range(1000):
        out_c = rng.choice(cards)
        cards.remove(out_c)
        load[where.pop(out_c)] -= 1
        rest.append(out_c)
        in_c = rng.choice(rest)
        rest.remove(in_c)
        cards.append(in_c)
        place(in_c)
    disp = sum(1 for c in cards if where[c] not in hashes(c))
    print("churn two-choice displaced after 1000 swaps @250:", disp)

    # the actual deck, single-hash vs two-choice side loads
    deck_cards = sorted({d for d in deck if normalize(d) not in BASICS})
    print("deck cards:", len(deck_cards))
    print("single loads:", sorted(single_hash(deck_cards)[0]))
    print("two-choice loads:", sorted(two_choice(deck_cards)[0]))
    json.dump(out, open(os.path.join(HERE, "results.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
