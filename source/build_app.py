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
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../source
ROOT = HERE.parent                              # repo root
TEMPLATE = HERE / "wc2026_template.html"
DATA = HERE / "wc2026_results.json"
OUTPUT = ROOT / "index.html"
TOKEN = "/*DATA*/"


def build() -> str:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    if tpl.count(TOKEN) != 1:
        sys.exit(f"error: expected exactly one {TOKEN} token in {TEMPLATE.name}, "
                 f"found {tpl.count(TOKEN)}")
    raw = DATA.read_text(encoding="utf-8")
    json.loads(raw)  # fail loudly if the results file is not valid JSON
    return tpl.replace(TOKEN, raw)


def main() -> None:
    check = "--check" in sys.argv[1:]
    html = build()
    if check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != html:
            sys.exit("index.html is out of date. Run: python3 source/build_app.py")
        print("index.html is up to date.")
        return
    OUTPUT.write_text(html, encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
