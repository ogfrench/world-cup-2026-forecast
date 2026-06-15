#!/usr/bin/env python3
"""Build the deployed app.

Injects the simulation output (wc2026_results.json) into the single
/*DATA*/ token in wc2026_template.html and writes the self-contained
index.html at the repo root. This is the only supported way to produce
index.html. Do not hand-edit index.html; edit the template and rebuild.

Usage (from anywhere):
    python3 source/build_app.py
    python3 source/build_app.py --check   # verify index.html is up to date, do not write

Exit codes: 0 ok; 1 build/template error; 2 (--check) index.html is stale.
"""
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../source
ROOT = HERE.parent                              # repo root
TEMPLATE = HERE / "wc2026_template.html"
DATA = HERE / "wc2026_results.json"
OUTPUT = ROOT / "index.html"
TOKEN = "/*DATA*/"
CSP_ANCHOR = '<meta name="viewport" content="width=device-width, initial-scale=1.0">'


def csp_meta(html: str) -> str:
    """A Content-Security-Policy <meta> whose script-src hashes the page's inline
    <script> blocks, so a strict policy allows exactly those and no other script.

    Computed from the built HTML every run, so editing the template's JS and
    rebuilding keeps the hashes correct automatically (and build --check enforces it).
    frame-ancestors is set as an HTTP header in netlify.toml instead; <meta> CSP
    does not support it.
    """
    blocks = re.findall(r"<script>([\s\S]*?)</script>", html)
    hashes = " ".join(
        "'sha256-" + base64.b64encode(hashlib.sha256(b.encode("utf-8")).digest()).decode() + "'"
        for b in blocks
    )
    policy = ("default-src 'none'; "
              f"script-src 'self' {hashes}; "
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
              "font-src https://fonts.gstatic.com; "
              "img-src 'self' data:; "
              "connect-src https://raw.githubusercontent.com; "
              "base-uri 'none'; form-action 'none'")
    return f'<meta http-equiv="Content-Security-Policy" content="{policy}">'


def build() -> str:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    if tpl.count(TOKEN) != 1:
        sys.exit(f"error: expected exactly one {TOKEN} token in {TEMPLATE.name}, "
                 f"found {tpl.count(TOKEN)}")
    raw = DATA.read_text(encoding="utf-8")
    json.loads(raw)  # fail loudly if the results file is not valid JSON
    html = tpl.replace(TOKEN, raw)
    if CSP_ANCHOR not in html:
        sys.exit("error: viewport meta anchor not found; cannot insert the CSP meta")
    # the CSP must sit in <head>, before the scripts it hashes
    return html.replace(CSP_ANCHOR, CSP_ANCHOR + "\n" + csp_meta(html), 1)


def main() -> None:
    check = "--check" in sys.argv[1:]
    html = build()
    if check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != html:
            print("index.html is out of date. Run: python3 source/build_app.py", file=sys.stderr)
            sys.exit(2)
        print("index.html is up to date.")
        return
    OUTPUT.write_text(html, encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
