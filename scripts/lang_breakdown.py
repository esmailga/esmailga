"""Build assets/lang-breakdown.svg from the languages used across your own repos.

Runs with the standard library only. Forks and the profile repo itself are skipped.
Usage: python3 scripts/lang_breakdown.py [username]
Set GITHUB_TOKEN to avoid the unauthenticated API rate limit.
"""
import json
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

USER = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_REPOSITORY_OWNER", "esmailga")
TOP_N = 6  # languages shown before the rest are grouped as "Other"
SKIP = {"Jupyter Notebook"}  # notebook JSON inflates byte counts; Python already covers it
# Platform runner code that `flutter create` generates; not hand-written in a Dart repo.
FLUTTER_SCAFFOLD = {"C++", "C", "CMake", "Swift", "Kotlin", "Objective-C", "Ruby", "HTML"}
OUT = Path(__file__).resolve().parent.parent / "assets" / "lang-breakdown.svg"

PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#8a63d2", "#8b949e"]
TEXT = "#2D7AD2"  # readable on both GitHub light and dark backgrounds


def api(path):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Accept", "application/vnd.github+json")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def collect():
    totals = {}
    repos = api(f"/users/{USER}/repos?per_page=100&type=owner")
    for repo in repos:
        if repo["fork"] or repo["name"].lower() == USER.lower():
            continue
        langs = api(f"/repos/{USER}/{repo['name']}/languages")
        skip = SKIP | (FLUTTER_SCAFFOLD if "Dart" in langs else set())
        for lang, size in langs.items():
            if lang not in skip:
                totals[lang] = totals.get(lang, 0) + size
    return totals


def render(totals):
    total = sum(totals.values())
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    rows = ranked[:TOP_N]
    rest = sum(size for _, size in ranked[TOP_N:])
    if rest:
        rows.append(("Other", rest))

    width, gap = 440, 2
    usable = width - gap * (len(rows) - 1)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{{H}}" viewBox="0 0 {width} {{H}}">',
        "<style>text { font-family: -apple-system, 'Segoe UI', Ubuntu, Sans-Serif; }</style>",
        f'<defs><clipPath id="barclip"><rect x="0" y="4" width="{width}" height="14" rx="7" ry="7"/></clipPath></defs>',
        '<g clip-path="url(#barclip)">',
    ]
    x = 0.0
    for i, (_, size) in enumerate(rows):
        w = usable * size / total
        parts.append(f'<rect x="{x:.2f}" y="4" width="{w:.2f}" height="14" fill="{PALETTE[i]}"/>')
        x += w + gap
    parts.append("</g>")

    # Legend: two columns, filled top to bottom.
    per_col = (len(rows) + 1) // 2
    for i, (lang, size) in enumerate(rows):
        col, row = divmod(i, per_col)
        cx, cy = col * 230, 32 + row * 25
        pct = f"{100 * size / total:.1f}%"
        parts.append(f'<rect x="{cx}" y="{cy}" width="11" height="11" rx="3" fill="{PALETTE[i]}"/>')
        parts.append(f'<text x="{cx + 19}" y="{cy + 8 + 2}" font-size="13" fill="{TEXT}">{escape(lang)}</text>')
        parts.append(
            f'<text x="{cx + 210}" y="{cy + 10}" font-size="13" text-anchor="end" '
            f'font-variant-numeric="tabular-nums" fill="{TEXT}">{pct}</text>'
        )
    parts.append("</svg>")
    height = 32 + per_col * 25
    return "\n".join(parts).replace("{H}", str(height))


if __name__ == "__main__":
    data = collect()
    if not data:
        sys.exit(f"No language data found for {USER}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(data) + "\n")
    print(f"Wrote {OUT} from {len(data)} languages")
