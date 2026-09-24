# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 AI and Me Single-Member Private Company (Humanbound)
"""corpus.py — builds the firewall benchmark's test pages from the data in corpus/*.yaml.

The corpus is DATA, so it can be read and reviewed without reading code:

  corpus/skins.yaml       realistic page bodies (listing, offer board, reviews, FAQ, JSON API, spec sheet)
  corpus/attacks.yaml     injections, grouped by attack family; each is planted inside a skin
  corpus/adaptive.yaml    injections aimed at the firewall itself (the judge, its policy, its state)
  corpus/benign.yaml      hard negatives: ordinary pages, including ones that merely LOOK suspicious
  corpus/borderline.yaml  pages with no defensible ground truth, reported descriptively only

plus the repo's own real attack pages, rendered from storefront/templates.py (family "repo").

Categories and ground truth:   attack, adaptive -> block   benign, door -> pass   borderline -> none.
A "door" page is the repo's multi-hop door-opener: attacker-controlled, but its content is clean.

Injections may use transforms to build obfuscated variants:  {{b64:..}} {{rev:..}} {{zw:..}}
{{spaced:..}} {{bold:..}}.   `python corpus.py` writes the frozen corpus/pages.jsonl.
"""
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
DATA = HERE / "corpus"
STOREFRONT_DIR = HERE.parent.parent / "storefront"
PLACEMENTS = ("top", "middle", "bottom")
EXPECTED = {"attack": "block", "adaptive": "block", "benign": "pass", "door": "pass", "borderline": None}

_BOLD = {**{chr(ord("a") + i): chr(0x1D5EE + i) for i in range(26)},
         **{chr(ord("A") + i): chr(0x1D5D4 + i) for i in range(26)}}
_TRANSFORMS = {
    "b64": lambda s: base64.b64encode(s.encode()).decode(),
    "rev": lambda s: s[::-1],
    "zw": lambda s: "​".join(s),                      # zero-width spaces inside the word
    "spaced": lambda s: " ".join(s),
    "bold": lambda s: "".join(_BOLD.get(c, c) for c in s),  # mathematical sans-serif bold look-alikes
}
_TRANSFORM_RE = re.compile(r"\{\{(\w+):(.*?)\}\}", re.S)


def render(text):
    """Expand {{transform:payload}} markers."""
    def expand(match):
        name, payload = match.group(1), match.group(2)
        if name not in _TRANSFORMS:
            raise ValueError(f"Unknown corpus transform '{name}'. Known: {sorted(_TRANSFORMS)}")
        return _TRANSFORMS[name](payload)
    return _TRANSFORM_RE.sub(expand, text)


def compose(skin, injection, placement):
    """Plant an injection among a skin's paragraphs: top, middle, or bottom."""
    paragraphs = list(skin)
    index = {"top": 0, "middle": (len(paragraphs) + 1) // 2, "bottom": len(paragraphs)}[placement]
    paragraphs.insert(index, injection)
    return "\n\n".join(paragraphs)


def _load(name):
    return yaml.safe_load((DATA / name).read_text(encoding="utf-8"))


def split_of(page_id, position):
    """Which half a page belongs to: "tune" (used to fit thresholds) or "test" (never used for
    fitting, reported as the result). Pages alternate within their family, in id order, so both halves
    cover every family; the family's starting half comes from a hash of its name, so the choice is
    mechanical and cannot be steered towards a result."""
    family = page_id.rsplit("-", 1)[0]
    offset = int(hashlib.sha256(family.encode()).hexdigest(), 16) % 2
    return ("tune", "test")[(position + offset) % 2]


def _page(page_id, category, family, technique, text, injection=None, note=None):
    return {"id": page_id, "category": category, "family": family, "technique": technique,
            "expected": EXPECTED[category], "text": text, "injection": injection, "note": note}


def _assign_splits(pages):
    positions = {}
    for page in sorted(pages, key=lambda p: p["id"]):
        group = (page["category"], page["id"].rsplit("-", 1)[0])
        position = positions.get(group, 0)
        positions[group] = position + 1
        page["split"] = split_of(page["id"], position)
    return pages


def _planted(entries, category, skins):
    """Plant each injection in a skin. Skin and placement rotate deterministically so that every
    family is spread across page types and depths, unless an entry pins its own."""
    names = sorted(skins)
    pages, counters = [], {}
    for n, entry in enumerate(entries):
        family = entry["family"]
        counters[family] = counters.get(family, 0) + 1
        skin_name = entry.get("skin") or names[n % len(names)]
        placement = entry.get("placement") or PLACEMENTS[n % len(PLACEMENTS)]
        injection = render(entry["text"]).strip()
        text = compose(skins[skin_name], injection, placement) * int(entry.get("repeat", 1)) \
            if not entry.get("haystack") else _haystack(skins, injection)
        pages.append(_page(f"{family}-{counters[family]:02d}", category, family, entry["technique"],
                           text, injection, entry.get("note")))
    return pages


def _haystack(skins, injection):
    """A long page: every skin, repeated, with the injection buried in the middle."""
    paragraphs = [p for name in sorted(skins) for p in skins[name]] * 6
    return compose(paragraphs, injection, "middle")


def _standalone(entries, category, skins):
    pages, counters = [], {}
    for entry in entries:
        family = entry["family"]
        counters[family] = counters.get(family, 0) + 1
        if entry.get("skin_only"):
            text = "\n\n".join(skins[entry["skin_only"]])
        elif entry.get("haystack"):
            text = _haystack(skins, render(entry["text"]).strip())
        elif entry.get("skin"):
            text = compose(skins[entry["skin"]], render(entry["text"]).strip(), entry.get("placement", "bottom"))
        else:
            text = render(entry["text"]).strip()
        pages.append(_page(f"{family}-{counters[family]:02d}", category, family, entry["technique"],
                           text, None, entry.get("note")))
    return pages


def _html_to_text(html):
    html = re.sub(r"(?s)<(script|style).*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def _repo_pages(collector="http://127.0.0.1:8001", sku="SKU-4471"):
    """The repo's own multi-hop attack: each payload's door-opener (clean content -> "door") and the
    page it leads to (the injection -> "attack")."""
    sys.path.insert(0, str(STOREFRONT_DIR))
    import templates

    pages = []
    for n, payload in enumerate(sorted(templates.PAYLOADS), start=1):
        door = templates.PAYLOADS[payload].format(collector=collector, sku=sku)
        html = templates.render_clean_multihop(sku, collector_base=collector, door=door)
        pages.append(_page(f"door-{n:02d}", "door", "repo", f"door-opener:{payload}", _html_to_text(html),
                           note="attacker-controlled page whose content is clean; it only points one hop on"))
    for n, tier in enumerate(("o1", "o2"), start=1):
        html = templates.escalation_page(sku, tier=tier, collector_base=collector)
        pages.append(_page(f"repo-{n:02d}", "attack", "repo", f"escalation:{templates.active_payload_name()}:{tier}",
                           _html_to_text(html)))
    benign = templates.live_price_page(sku)
    pages.append(_page("repo-benign-01", "benign", "repo", "live-price page", _html_to_text(benign)))
    # a third repo attack page: the escalation reached through the white-box door wording
    html = templates.escalation_page(sku, tier="o1", collector_base="http://localhost:8001")
    pages.append(_page("repo-03", "attack", "repo", f"escalation:{templates.active_payload_name()}:o1:alt-host",
                       _html_to_text(html)))
    return pages


def build():
    skins = _load("skins.yaml")
    pages = []
    pages += _planted(_load("attacks.yaml"), "attack", skins)
    pages += _planted(_load("adaptive.yaml"), "adaptive", skins)
    pages += _standalone(_load("benign.yaml"), "benign", skins)
    pages += _standalone(_load("borderline.yaml"), "borderline", skins)
    pages += _repo_pages()
    return _assign_splits(pages)


def fingerprint(pages):
    """A short hash of the corpus content, recorded with the results so a report names its corpus."""
    blob = json.dumps([(p["id"], p["text"]) for p in pages], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def write(path=DATA / "pages.jsonl"):
    pages = build()
    with open(path, "w", encoding="utf-8") as fh:
        for page in pages:
            fh.write(json.dumps(page, ensure_ascii=False) + "\n")
    return pages


if __name__ == "__main__":
    from collections import Counter
    built = write()
    print(f"wrote {len(built)} pages -> corpus/pages.jsonl   fingerprint {fingerprint(built)}")
    for category, count in sorted(Counter(p["category"] for p in built).items()):
        print(f"  {category:<11}{count}")
