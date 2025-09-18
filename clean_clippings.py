# -*- coding: utf-8 -*-
"""
clipping_cleaner_v2.py
Enhanced cleaner for Kindle My Clippings.txt
Usage:
  python clipping_cleaner_v2.py [in_file] [out_md]
Examples:
  python clipping_cleaner_v2.py "My Clippings.txt" "Clipping_cleaned.md"
"""
from __future__ import print_function
import re
import sys
import hashlib
import difflib
from collections import defaultdict
from typing import List, Tuple, Optional, Dict, Any
import time

BOM = "\ufeff"
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

LOC_PATTERNS = [
    re.compile(r"位置\s*#?(\d+)(?:-(\d+))?"),
    re.compile(r"Location(?:s)?\s*#?(\d+)(?:-(\d+))?", re.I),
    re.compile(r"loc\.\s*(\d+)(?:-(\d+))?", re.I),
]

TYPE_PATTERNS = [
    re.compile(r"Your\s+(Highlight|Note|Bookmark)", re.I),
    re.compile(r"您在.*?的(标注|笔记|书签)"),
]

TS_PATTERNS = [
    re.compile(r"Added on\s+(.+)", re.I),
    re.compile(r"添加于\s+(.+)")
]

# sentence/ clause split (Chinese and common punctuation)
CLAUSE_SPLIT_RE = re.compile(r'[。！？；;.!?\n]+')

def strip_bom(s: str) -> str:
    return s.lstrip(BOM).strip()

def mostly_cjk(text: str, threshold: float = 0.3) -> bool:
    if not text:
        return False
    cjk = len(CJK_RE.findall(text))
    return (cjk / max(1, len(text))) >= threshold

def normalize_for_compare(text: str) -> str:
    if not text:
        return ""
    t = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    t = re.sub(r"\s+", " ", t)
    if mostly_cjk(t):
        t = re.sub(r"\s+", "", t)  # remove spaces for CJK
    t = re.sub(r"[。！？…\.\!\?]+$", "", t)
    return t

def md5_utf8(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()

def parse_loc(meta: str) -> Tuple[Optional[int], Optional[int]]:
    for pat in LOC_PATTERNS:
        m = pat.search(meta)
        if m:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else start
            if start > end:
                start, end = end, start
            return start, end
    return None, None

def parse_type(meta: str) -> str:
    for pat in TYPE_PATTERNS:
        m = pat.search(meta)
        if m:
            t = m.group(1).lower()
            if t in ("highlight", "标注"):
                return "highlight"
            if t in ("note", "笔记"):
                return "note"
            if t in ("bookmark", "书签"):
                return "bookmark"
    return "unknown"

def parse_timestamp(meta: str) -> Optional[str]:
    for pat in TS_PATTERNS:
        m = pat.search(meta)
        if m:
            return m.group(1).strip()
    return None

def parse_timestamp_to_epoch(ts: Optional[str]) -> Optional[int]:
    """Try to parse timestamp strings to epoch seconds (naive, local time).
    Supports Chinese 'YYYY年M月D日 上午/下午 HH:MM:SS' and ISO-like numeric dates.
    Returns None if cannot parse.
    """
    if not ts:
        return None
    ts = ts.strip()
    # Chinese pattern: 2025年9月18日 星期四 上午11:20:48 or without weekday
    m = re.search(r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日.*?(上午|下午)?\s*(\d{1,2}):(\d{2}):(\d{2})', ts)
    if m:
        year = int(m.group(1)); month = int(m.group(2)); day = int(m.group(3))
        ampm = m.group(4)
        hh = int(m.group(5)); mm = int(m.group(6)); ss = int(m.group(7))
        if ampm:
            if ampm == '下午' and hh < 12:
                hh += 12
            if ampm == '上午' and hh == 12:
                hh = 0
        try:
            struct = time.struct_time((year, month, day, hh, mm, ss, 0, 0, -1))
            return int(time.mktime(struct))
        except Exception:
            return None
    # ISO-ish or numeric: 2025-09-18 11:20:48 or 2025/09/18 11:20:48
    m2 = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})[ T](\d{1,2}):(\d{2}):(\d{2})', ts)
    if m2:
        y,mn,d,h,mi,s = map(int, m2.groups())
        try:
            struct = time.struct_time((y,mn,d,h,mi,s,0,0,-1))
            return int(time.mktime(struct))
        except Exception:
            return None
    # fallback: extract first occurrence of HH:MM:SS and today's date -> not reliable
    return None

def split_entries(content: str) -> List[str]:
    parts = content.split("==========")
    return [p.strip() for p in parts if p.strip()]

def split_clauses(text: str) -> List[str]:
    if not text:
        return []
    clauses = [c.strip() for c in CLAUSE_SPLIT_RE.split(text) if c.strip()]
    return clauses if clauses else [text.strip()]

def parse_entry(block: str, idx: int) -> Optional[Dict[str, Any]]:
    lines = [l.rstrip("\n") for l in block.split("\n")]
    if len(lines) < 2:
        return None
    title = strip_bom(lines[0])
    meta = lines[1].strip()
    body_lines = lines[2:]
    # remove leading empty lines in body
    while body_lines and not body_lines[0].strip():
        body_lines = body_lines[1:]
    body = "\n".join(body_lines).strip()
    kind = parse_type(meta)
    loc_start, loc_end = parse_loc(meta)
    ts_raw = parse_timestamp(meta)
    ts_epoch = parse_timestamp_to_epoch(ts_raw)
    norm = normalize_for_compare(body)
    return {
        "idx": idx,
        "title": title,
        "meta": meta,
        "type": kind,
        "loc": (loc_start, loc_end),
        "timestamp_raw": ts_raw,
        "timestamp": ts_epoch,
        "body": body,
        "norm": norm,
        "hash": md5_utf8(norm),
        "clauses": split_clauses(norm)
    }

def ranges_overlap(a, b, tol=8):
    a1, a2 = a
    b1, b2 = b
    if a1 is None or b1 is None:
        return False
    return not ((a2 + tol) < b1 or (b2 + tol) < a1)

def very_close(a: str, b: str, ratio: float = 0.92) -> bool:
    if not a or not b:
        return False
    if min(len(a), len(b)) < 8:
        return a == b
    return difflib.SequenceMatcher(None, a, b).ratio() >= ratio

def clause_based_match(a_clauses: List[str], b_clauses: List[str], min_len: int = 8, ratio: float = 0.90) -> bool:
    # if any clause from a is subset of any clause in b (or vice versa) or very close -> match
    for ca in a_clauses:
        if len(ca) < min_len:
            continue
        for cb in b_clauses:
            if len(cb) < min_len:
                continue
            if ca in cb or cb in ca:
                return True
            if difflib.SequenceMatcher(None, ca, cb).ratio() >= ratio:
                return True
    return False

def is_duplicate(cur, kept, time_tol=300, clause_min_len=12, debug=False):
    """Enhanced duplicate detection using:
       - exact norm equality
       - location overlap
       - clause-based matching
       - timestamp proximity to be more permissive
    """
    a, b = cur["norm"], kept["norm"]
    if not a or not b:
        return False
    if a == b:
        if debug: print("dup exact equal")
        return True

    overlap = ranges_overlap(cur["loc"], kept["loc"], tol=8)
    # If timestamps exist and are close, be more permissive
    ta, tb = cur.get("timestamp"), kept.get("timestamp")
    time_close = (ta is not None and tb is not None and abs(ta - tb) <= time_tol)

    # clause-level matching
    clause_match = clause_based_match(cur["clauses"], kept["clauses"], min_len=clause_min_len,
                                      ratio=(0.88 if time_close else 0.92))
    if overlap:
        if clause_match:
            if debug: print("dup overlap+clause")
            return True
        # subset inclusion on overlapping ranges
        if is_subset(a, b, min_len=12):
            if debug: print("dup overlap+subset")
            return True
        if very_close(a, b, ratio=(0.90 if time_close else 0.92)):
            if debug: print("dup overlap+very_close")
            return True
        return False
    else:
        # not overlapping locations: be stricter unless time_close
        if clause_match:
            if debug: print("dup clause_match non-overlap")
            return True
        if is_subset(a, b, min_len=(10 if time_close else 16)):
            if debug: print("dup subset non-overlap")
            return True
        if very_close(a, b, ratio=(0.95 if not time_close else 0.92)):
            if debug: print("dup very_close non-overlap")
            return True
        return False

def is_subset(a: str, b: str, min_len: int = 12) -> bool:
    if not a or not b:
        return False
    if min(len(a), len(b)) < min_len:
        return False
    return a in b or b in a

def dedup_by_book(entries: List[Dict[str, Any]],
                  time_tol: int = 300,
                  clause_min_len: int = 12,
                  debug: bool = False) -> Dict[str, List[Dict[str, Any]]]:
    by_book = defaultdict(list)
    for e in entries:
        by_book[e["title"]].append(e)
    result = {}
    stats_filtered_empty = 0
    for book, es in by_book.items():
        # preserve original order but we prefer latest entries:
        # sort by idx ascending (original order), but we'll iterate reversed to keep later ones
        kept_h, kept_n, kept_b = [], [], []
        for cur in reversed(es):
            # filter empty bodies (no body and no meta useful)
            if not cur["body"] or not cur["body"].strip():
                # treat empty mark as noise; skip it
                stats_filtered_empty += 1
                if debug:
                    print("Filtered empty:", cur["title"], cur["meta"])
                continue
            t = cur["type"]
            if t == "highlight":
                dup = any(is_duplicate(cur, k, time_tol=time_tol, clause_min_len=clause_min_len, debug=debug) for k in kept_h)
                if not dup:
                    kept_h.append(cur)
            elif t == "note":
                if not any(cur["norm"] == k["norm"] for k in kept_n):
                    kept_n.append(cur)
            elif t == "bookmark":
                if not any(cur["meta"] == k["meta"] for k in kept_b):
                    kept_b.append(cur)
            else:
                dup = any(is_duplicate(cur, k, time_tol=time_tol, clause_min_len=clause_min_len, debug=debug) for k in kept_h)
                if not dup:
                    kept_h.append(cur)

        def sort_key(x):
            s, e2 = x["loc"]
            if s is None:
                # if no location, sort by timestamp (newer first)
                ts = x.get("timestamp") or 0
                return (10**12, -ts, x["idx"])
            return (s, x["idx"])

        kept_h.sort(key=sort_key)
        kept_n.sort(key=sort_key)
        kept_b.sort(key=sort_key)
        result[book] = kept_h + kept_n + kept_b
    if debug:
        print("Filtered empty markers:", stats_filtered_empty)
    return result

def save_md(by_book: Dict[str, List[Dict[str, Any]]], out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8-sig") as f:
        for book, items in by_book.items():
            f.write(f"## {book}\n\n")
            for it in items:
                if it["body"]:
                    f.write(f"{it['body']}\n\n")
                else:
                    f.write(f"（{it['type']}） {it['meta']}\n\n")

def main(in_path: str, out_md: str, time_tol: int = 300, clause_min_len: int = 12, debug: bool = False) -> None:
    with open(in_path, "r", encoding="utf-8", errors='ignore') as fp:
        content = fp.read()
    blocks = split_entries(content)
    parsed = []
    for i, blk in enumerate(blocks):
        e = parse_entry(blk, idx=i)
        if e:
            parsed.append(e)
    by_book = dedup_by_book(parsed, time_tol=time_tol, clause_min_len=clause_min_len, debug=debug)
    save_md(by_book, out_md)
    print(f"去重完成，共 {len(by_book)} 本书。已保存 -> {out_md}")

if __name__ == "__main__":
    # CLI handling
    if len(sys.argv) < 2:
        in_file = "My Clippings.txt"
        out_md = "Clipping_cleaned.md"
    else:
        in_file = sys.argv[1]
        out_md = sys.argv[2] if len(sys.argv) >= 3 else "Clipping_cleaned.md"

    # optional environment params via sys.argv? simple: read extra args if present
    # usage: python clipping_cleaner_v2.py in.txt out.md time_tol clause_min_len debug
    try:
        time_tol = int(sys.argv[3]) if len(sys.argv) >= 4 else 300
        clause_min_len = int(sys.argv[4]) if len(sys.argv) >= 5 else 12
        debug = bool(int(sys.argv[5])) if len(sys.argv) >= 6 else False
    except Exception:
        time_tol = 300
        clause_min_len = 12
        debug = False

    main(in_file, out_md, time_tol=time_tol, clause_min_len=clause_min_len, debug=debug)
