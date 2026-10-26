// Browser port of binder.py's hashing and list handling. Must give the same
// sides as binder.py for every name: check with `python3 check_web.py`.

(function (root) {
  "use strict";

  const PAGES = 20, POCKETS = 9, SIDES = PAGES * 2;
  const SALT = new TextEncoder().encode("binder-v1"); // never change this once cards are placed
  const BASICS = new Set(["plains", "island", "swamp", "mountain", "forest", "wastes"]);
  for (const b of [...BASICS]) BASICS.add(`snow-covered ${b}`);

  // ---------- BLAKE2b (RFC 7693), keyed, BigInt words ----------

  const M64 = (1n << 64n) - 1n;
  const IV = [
    0x6a09e667f3bcc908n, 0xbb67ae8584caa73bn, 0x3c6ef372fe94f82bn, 0xa54ff53a5f1d36f1n,
    0x510e527fade682d1n, 0x9b05688c2b3e6c1fn, 0x1f83d9abfb41bd6bn, 0x5be0cd19137e2179n,
  ];
  const SIGMA = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
    [14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3],
    [11, 8, 12, 0, 5, 2, 15, 13, 10, 14, 3, 6, 7, 1, 9, 4],
    [7, 9, 3, 1, 13, 12, 11, 14, 2, 6, 5, 10, 4, 0, 15, 8],
    [9, 0, 5, 7, 2, 4, 10, 15, 14, 1, 11, 12, 6, 8, 3, 13],
    [2, 12, 6, 10, 0, 11, 8, 3, 4, 13, 7, 5, 15, 14, 1, 9],
    [12, 5, 1, 15, 14, 13, 4, 10, 0, 7, 6, 3, 9, 2, 8, 11],
    [13, 11, 7, 14, 12, 1, 3, 9, 5, 0, 15, 4, 8, 6, 2, 10],
    [6, 15, 14, 9, 11, 3, 0, 8, 12, 2, 13, 7, 1, 4, 10, 5],
    [10, 2, 8, 4, 7, 6, 1, 5, 15, 11, 9, 14, 3, 12, 13, 0],
  ];
  const rotr = (x, n) => ((x >> BigInt(n)) | (x << BigInt(64 - n))) & M64;

  function compress(h, block, t, last) {
    const m = [];
    for (let i = 0; i < 16; i++) {
      let w = 0n;
      for (let j = 7; j >= 0; j--) w = (w << 8n) | BigInt(block[i * 8 + j]);
      m.push(w);
    }
    const v = [...h, ...IV];
    v[12] ^= BigInt(t) & M64;
    if (last) v[14] ^= M64;
    const g = (a, b, c, d, x, y) => {
      v[a] = (v[a] + v[b] + x) & M64; v[d] = rotr(v[d] ^ v[a], 32);
      v[c] = (v[c] + v[d]) & M64;     v[b] = rotr(v[b] ^ v[c], 24);
      v[a] = (v[a] + v[b] + y) & M64; v[d] = rotr(v[d] ^ v[a], 16);
      v[c] = (v[c] + v[d]) & M64;     v[b] = rotr(v[b] ^ v[c], 63);
    };
    for (let r = 0; r < 12; r++) {
      const s = SIGMA[r % 10];
      g(0, 4, 8, 12, m[s[0]], m[s[1]]);
      g(1, 5, 9, 13, m[s[2]], m[s[3]]);
      g(2, 6, 10, 14, m[s[4]], m[s[5]]);
      g(3, 7, 11, 15, m[s[6]], m[s[7]]);
      g(0, 5, 10, 15, m[s[8]], m[s[9]]);
      g(1, 6, 11, 12, m[s[10]], m[s[11]]);
      g(2, 7, 8, 13, m[s[12]], m[s[13]]);
      g(3, 4, 9, 14, m[s[14]], m[s[15]]);
    }
    for (let i = 0; i < 8; i++) h[i] ^= v[i] ^ v[i + 8];
  }

  function blake2b(data, key, outLen) {
    const h = [...IV];
    h[0] ^= BigInt(0x01010000 ^ (key.length << 8) ^ outLen);
    const keyBlock = new Uint8Array(key.length ? 128 : 0);
    keyBlock.set(key);
    const msg = new Uint8Array(keyBlock.length + data.length);
    msg.set(keyBlock);
    msg.set(data, keyBlock.length);
    const blocks = Math.max(1, Math.ceil(msg.length / 128));
    for (let i = 0; i < blocks; i++) {
      const block = new Uint8Array(128);
      block.set(msg.subarray(i * 128, (i + 1) * 128));
      const last = i === blocks - 1;
      compress(h, block, last ? msg.length : (i + 1) * 128, last);
    }
    const out = new Uint8Array(outLen);
    for (let i = 0; i < outLen; i++) out[i] = Number((h[i >> 3] >> BigInt(8 * (i & 7))) & 0xffn);
    return out;
  }

  // ---------- names and sides ----------

  function casefold(s) {
    // toLowerCase plus the Python casefold() cases that differ from it
    return s.toLowerCase().replace(/ß/g, "ss").replace(/ς/g, "σ");
  }

  function normalize(name) {
    name = name.split(" // ")[0].normalize("NFKD").replace(/\p{M}/gu, "");
    name = casefold(name).replace(/’/g, "'").replace(/æ/g, "ae");
    return name.replace(/\s+/g, " ").trim();
  }

  const isBasic = (name) => BASICS.has(normalize(name));

  const bigEndian = (bytes) => bytes.reduce((n, b) => (n << 8n) | BigInt(b), 0n);

  function candidates(name) {
    const d = blake2b(new TextEncoder().encode(normalize(name)), SALT, 16);
    const x = bigEndian(d.subarray(0, 8)), y = bigEndian(d.subarray(8));
    const a = Number(x % BigInt(SIDES));
    let b = Number(y % BigInt(SIDES));
    if (b === a) b = (a + 1 + Number(y % BigInt(SIDES - 1))) % SIDES; // make sure the two choices differ
    return [a, b];
  }

  const label = (side) => `page ${Math.floor(side / 2) + 1} ${side % 2 === 0 ? "front" : "back"}`;

  function both(name) {
    const [a, b] = candidates(name).sort((p, q) => p - q);
    return [label(a), label(b)];
  }

  // ---------- ManaBox CSV ----------

  function parseCsv(text) {
    const rows = [];
    let row = [], field = "", quoted = false;
    text = text.replace(/^﻿/, "");
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quoted) {
        if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
        else if (c === '"') quoted = false;
        else field += c;
      } else if (c === '"') quoted = true;
      else if (c === ",") { row.push(field); field = ""; }
      else if (c === "\n" || c === "\r") {
        if (c === "\r" && text[i + 1] === "\n") i++;
        row.push(field); rows.push(row); row = []; field = "";
      } else field += c;
    }
    if (field || row.length) { row.push(field); rows.push(row); }
    return rows.filter((r) => r.some((f) => f.trim()));
  }

  // Card names from a CSV export, one entry per copy, basics removed.
  function readCsv(text) {
    const [header, ...rows] = parseCsv(text);
    const cols = (header || []).map((c) => c.trim().toLowerCase());
    const name = ["name", "card name", "card"].map((c) => cols.indexOf(c)).find((i) => i >= 0);
    const qty = ["quantity", "count", "qty"].map((c) => cols.indexOf(c)).find((i) => i >= 0);
    if (name === undefined) throw new Error(`No Name column (found: ${cols.join(", ")})`);
    const cards = [];
    for (const r of rows) {
      const n = (r[name] || "").trim();
      if (!n || isBasic(n)) continue;
      const q = qty === undefined ? 1 : parseInt(r[qty] || "1", 10);
      for (let i = 0; i < q; i++) cards.push(n);
    }
    return cards;
  }

  function counts(cards) {
    const c = new Map();
    for (const n of cards) c.set(normalize(n), (c.get(normalize(n)) || 0) + 1);
    return c;
  }

  // Multiset diff by normalized name, like `binder.py diff`. Entries are
  // {name, qty, sides}, alphabetical by normalized name.
  function diff(oldCards, newCards) {
    const display = new Map();
    for (const n of [...oldCards, ...newCards]) display.set(normalize(n), n);
    const o = counts(oldCards), n = counts(newCards);
    const minus = (a, b) =>
      [...a].filter(([k, q]) => q > (b.get(k) || 0)).sort(([x], [y]) => (x < y ? -1 : x > y ? 1 : 0))
        .map(([k, q]) => ({ name: display.get(k), qty: q - (b.get(k) || 0), sides: both(display.get(k)) }));
    return { out: minus(o, n), in: minus(n, o) };
  }

  // Every card once, alphabetical, with copies counted.
  function inventory(cards) {
    return diff([], cards).in;
  }

  const api = { PAGES, POCKETS, SIDES, normalize, isBasic, candidates, label, both, readCsv, diff, inventory, blake2b };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Binder = api;
})(this);
