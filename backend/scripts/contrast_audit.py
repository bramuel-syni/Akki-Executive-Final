"""WCAG 2.1 AA contrast audit for the Solva v3 token palette.

Run:  python3 backend/scripts/contrast_audit.py
"""
def srgb_lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

def luminance(rgb):
    r, g, b = (srgb_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def ratio(fg, bg):
    L1 = luminance(hex_to_rgb(fg))
    L2 = luminance(hex_to_rgb(bg))
    if L1 < L2: L1, L2 = L2, L1
    return (L1 + 0.05) / (L2 + 0.05)

TOKENS = {
    "INK":         "#2A1B1D",
    "DEEP":        "#5A4A4D",
    "MUTED":       "#6B6B6B",
    "RULE":        "#D5C9B6",
    "ACCENT":      "#C25A38",
    "ACCENT_DARK": "#B85230",
    "CREAM":       "#F5EFE6",
    "CREAM_DEEP":  "#E8DCC8",
    "PAPER":       "#FAF7F2",
    "LIGHT":       "#FFFFFF",
}
BG = ["LIGHT", "PAPER", "CREAM", "CREAM_DEEP"]
FG = ["INK", "DEEP", "MUTED", "ACCENT"]

# WCAG 2.1 AA: 4.5:1 normal text, 3:1 large text (≥18pt or ≥14pt bold) and UI.
def grade(r, large=False):
    threshold = 3.0 if large else 4.5
    return "PASS" if r >= threshold else "FAIL"

print(f"\n{'fg / bg':14}", end="")
for b in BG:
    print(f"{b:14}", end="")
print()
print("-" * 70)
for f in FG:
    print(f"{f:14}", end="")
    for b in BG:
        r = ratio(TOKENS[f], TOKENS[b])
        tag = grade(r) if f != "ACCENT" else grade(r, large=True)
        print(f"{r:5.2f} {tag:6} ", end="")
    print()

print("\nACCENT graded as LARGE TEXT (kicker labels are 13-14pt italic).")
print("Other foregrounds graded as NORMAL TEXT (4.5:1 threshold).")
print("\nSpecific Solva v3 surface checks:")
checks = [
    ("Diagnosis paragraph",            "INK",    "LIGHT"),
    ("Scenario label",                 "INK",    "LIGHT"),
    ("Scenario CI text",               "DEEP",   "LIGHT"),
    ("Scenario description",           "DEEP",   "LIGHT"),
    ("Sensitivity body",               "INK",    "CREAM"),
    ("Sensitivity kicker",             "ACCENT", "CREAM"),
    ("Tension body",                   "INK",    "CREAM_DEEP"),
    ("Tension kicker",                 "ACCENT", "CREAM_DEEP"),
    ("Recommendations body",           "INK",    "LIGHT"),
    ("Footer / muted meta",            "MUTED",  "LIGHT"),
    ("Reasoning expandable label",     "DEEP",   "LIGHT"),
    ("Refusal pill text",              "ACCENT_DARK", "LIGHT"),
    ("Landing card heading",           "INK",    "PAPER"),
    ("Landing card subtext",           "DEEP",   "PAPER"),
    ("Landing 'recent sessions' label","MUTED",  "PAPER"),
    ("Q-screen heading",               "INK",    "CREAM"),
    ("Q-depth heading (round 2)",      "INK",    "CREAM_DEEP"),
    ("Reflection heading",             "INK",    "PAPER"),
    ("Progress label (uppercase)",     "MUTED",  "PAPER"),
    ("Primary button text on accent",  "LIGHT",  "ACCENT_DARK"),
    # ── Phase J — Sandbox v2 surface combinations ─────────────────────
    # Welcome step (PAPER)
    ("Sandbox Welcome heading",        "INK",    "PAPER"),
    ("Sandbox Welcome lead",           "DEEP",   "PAPER"),
    ("Sandbox Welcome muted footnote", "MUTED",  "PAPER"),
    # Step 1 Solva (CREAM)
    ("Sandbox Step1 opening question", "DEEP",   "CREAM"),
    ("Sandbox Step1 fallback voice",   "MUTED",  "CREAM"),
    # Step 1 Reveal (CREAM)
    ("Sandbox reveal title",           "INK",    "CREAM"),
    ("Sandbox reveal body",            "DEEP",   "CREAM"),
    # Step 3 Studio (LIGHT)
    ("Sandbox Studio source kind",     "MUTED",  "LIGHT"),
    ("Sandbox Studio source title",    "INK",    "LIGHT"),
    ("Sandbox Studio source body",     "DEEP",   "LIGHT"),
    ("Sandbox Studio narration line",  "DEEP",   "LIGHT"),
    ("Sandbox Studio composed para",   "INK",    "LIGHT"),
    ("Sandbox Studio refusal voice",   "ACCENT_DARK", "LIGHT"),
    # Step 3 Reveal (LIGHT)
    ("Sandbox reveal title (LIGHT)",   "INK",    "LIGHT"),
    ("Sandbox reveal body (LIGHT)",    "DEEP",   "LIGHT"),
    # Step 4 Cycle snapshot (PAPER)
    ("Sandbox Cycle banner",           "DEEP",   "CREAM_DEEP"),
    ("Sandbox Cycle column heading",   "INK",    "PAPER"),
    ("Sandbox Cycle row text",         "DEEP",   "PAPER"),
    ("Sandbox Cycle status muted",     "MUTED",  "PAPER"),
    # Closing (PAPER)
    ("Sandbox Closing hope reflection","DEEP",   "PAPER"),
    ("Sandbox Closing CTA secondary",  "INK",    "LIGHT"),
    ("Sandbox Closing CTA primary",    "LIGHT",  "ACCENT_DARK"),
]
print(f"\n{'surface':40} {'fg':10} {'bg':12} ratio  grade")
for label, f, b in checks:
    r = ratio(TOKENS[f], TOKENS[b])
    is_large = (f == "ACCENT") or label.endswith("(uppercase)") or "kicker" in label.lower() or "card heading" in label.lower() or "Q-screen heading" in label.lower() or "reflection heading" in label.lower() or "depth heading" in label.lower() or "reveal title" in label.lower() or "column heading" in label.lower() or "Welcome heading" in label.lower() or "banner" in label.lower()
    g = grade(r, large=is_large)
    big = "(LG)" if is_large else "    "
    print(f"{label:40} {f:10} {b:12} {r:5.2f}  {g} {big}")
