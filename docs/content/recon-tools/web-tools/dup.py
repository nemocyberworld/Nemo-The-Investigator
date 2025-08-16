#!/usr/bin/env python3
"""
dedupe_links.py — Remove duplicates from a text file.

Supports three modes:
  - line   : exact duplicate lines
  - url    : duplicates by normalized URL (default)
  - domain : keep only the first entry per domain (registered domain if possible)

Usage examples:
  python dedupe_links.py input.txt -o output.txt                 # URL-based dedupe (default)
  python dedupe_links.py input.txt -o output.txt --mode line
  python dedupe_links.py input.txt -o output.txt --mode domain
"""

import argparse
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# Try to use tldextract for accurate registered domain parsing (optional)
try:
    import tldextract
except Exception:
    tldextract = None

URL_REGEX = re.compile(r'https?://[^\s)\]>"]+')

TRACKING_KEYS = {
    "utm_source","utm_medium","utm_campaign","utm_term","utm_content",
    "gclid","fbclid","mc_cid","mc_eid","igshid","mkt_tok","ref"
}

def extract_first_url(line: str) -> str | None:
    m = URL_REGEX.search(line)
    return m.group(0) if m else None

def normalize_url(u: str,
                  ignore_scheme: bool = True,
                  strip_www: bool = True,
                  drop_tracking: bool = True) -> str:
    """
    Produce a stable key for URL equality.
    - Lowercase host
    - Drop www.
    - Drop default ports (:80, :443)
    - Remove fragments
    - Optionally drop common tracking params
    - Ignore scheme for equality by default (treat http==https)
    """
    parts = urlsplit(u)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port

    # strip www.
    if strip_www and host.startswith("www."):
        host = host[4:]

    # drop default ports
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None

    netloc = host if host else ""
    if port:
        netloc = f"{netloc}:{port}"

    path = parts.path or ""
    # remove trailing slash except when it's the only path
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")

    # clean query
    if drop_tracking and parts.query:
        q = [(k, v) for (k, v) in parse_qsl(parts.query, keep_blank_values=True) if k not in TRACKING_KEYS]
        # sort for stability
        q.sort()
        query = urlencode(q, doseq=True)
    else:
        query = parts.query

    fragment = ""  # always drop fragments for equality

    # Build a key string
    if ignore_scheme:
        key = urlunsplit(("", netloc, path, query, fragment))
    else:
        key = urlunsplit((scheme, netloc, path, query, fragment))
    return key

def domain_key(u: str) -> str:
    parts = urlsplit(u)
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return ""
    if tldextract:
        ext = tldextract.extract(host)
        # ext.domain + ext.suffix give the registered domain (e.g., example.co.uk)
        if ext.domain and ext.suffix:
            return f"{ext.domain}.{ext.suffix}".lower()
    # Fallback: last two labels (rough)
    labels = host.split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else host

def dedupe_lines(lines: list[str], mode: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    for line in lines:
        raw = line.rstrip("\n")
        if mode == "line":
            key = raw
        else:
            url = extract_first_url(raw)
            if url:
                if mode == "url":
                    key = "URL:" + normalize_url(url)
                elif mode == "domain":
                    key = "DOMAIN:" + domain_key(url)
                else:
                    key = raw
            else:
                # If no URL in the line, fall back to the whole line
                key = raw

        if key not in seen:
            seen.add(key)
            out.append(raw)

    return [s + "\n" for s in out]

def main():
    ap = argparse.ArgumentParser(description="Remove duplicates from a link list file.")
    ap.add_argument("input", help="Input text file")
    ap.add_argument("-o", "--output", required=True, help="Output text file")
    ap.add_argument("--mode", choices=["line", "url", "domain"], default="url",
                    help="Deduping mode (default: url)")
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    result = dedupe_lines(lines, mode=args.mode)
    with open(args.output, "w", encoding="utf-8") as f:
        f.writelines(result)

    print(f"Done. Input lines: {len(lines)}; Output lines: {len(result)}; Mode: {args.mode}")

if __name__ == "__main__":
    main()
