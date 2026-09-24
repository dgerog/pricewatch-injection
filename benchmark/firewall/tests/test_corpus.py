# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 AI and Me Single-Member Private Company (Humanbound)
"""The firewall benchmark's corpus: attack pages across many angles, hard benign negatives, an adaptive
set aimed at the firewall itself, and a borderline set with no ground truth. All offline."""
import base64
import re
from collections import Counter

import pytest

import corpus

PAGES = corpus.build()
BY_ID = {p["id"]: p for p in PAGES}


# --- text transforms used to author obfuscated attacks ------------------------------------------


def test_b64_transform_encodes_the_instruction():
    out = corpus.render("Decode: {{b64:send the value}}")
    assert base64.b64decode(out.split("Decode: ")[1]).decode() == "send the value"


def test_rev_transform_reverses_the_instruction():
    assert corpus.render("{{rev:abc def}}") == "fed cba"


def test_zw_transform_hides_zero_width_characters_inside_words():
    out = corpus.render("{{zw:cost}}")
    assert out != "cost" and out.replace("​", "") == "cost"


def test_spaced_transform_separates_letters():
    assert corpus.render("{{spaced:cost}}") == "c o s t"


def test_unknown_transform_is_rejected():
    with pytest.raises(ValueError):
        corpus.render("{{rot47:x}}")


# --- composition: an injection is planted inside a realistic page -------------------------------


def test_attack_pages_embed_the_injection_in_a_page_skin():
    page = BY_ID["exfil_direct-01"]
    assert page["injection"] in page["text"]
    assert len(page["text"]) > len(page["injection"]) + 200  # surrounded by real page content


def test_placements_put_the_injection_at_different_depths():
    skin = ["P1", "P2", "P3", "P4"]
    assert corpus.compose(skin, "X", "top").startswith("X")
    assert corpus.compose(skin, "X", "bottom").endswith("X")
    assert corpus.compose(skin, "X", "middle").index("X") > corpus.compose(skin, "X", "middle").index("P2")


# --- the corpus as a whole ----------------------------------------------------------------------


def test_every_page_has_the_required_fields_and_a_unique_id():
    ids = [p["id"] for p in PAGES]
    assert len(ids) == len(set(ids))
    for p in PAGES:
        assert p["category"] in ("attack", "adaptive", "benign", "door", "borderline")
        assert p["text"].strip() and p["family"] and p["technique"]


def test_ground_truth_follows_the_category():
    for p in PAGES:
        expected = {"attack": "block", "adaptive": "block", "benign": "pass", "door": "pass"}.get(p["category"])
        assert p["expected"] == expected  # borderline pages have no ground truth (None)


def test_the_attack_set_covers_many_angles():
    families = Counter(p["family"] for p in PAGES if p["category"] == "attack")
    for family in ("exfil_direct", "exfil_paraphrase", "exfil_derived", "exfil_channel", "authority",
                   "goal_hijack", "system_exposure", "forbidden_action", "obfuscation", "language",
                   "social", "multistep", "repo"):
        assert families[family] >= 3, family
    assert sum(families.values()) >= 60


def test_there_are_enough_hard_negatives_and_adaptive_pages():
    categories = Counter(p["category"] for p in PAGES)
    assert categories["benign"] >= 20
    assert categories["adaptive"] >= 12
    assert categories["borderline"] >= 5


def test_the_repos_real_attack_pages_are_included():
    repo = [p for p in PAGES if p["family"] == "repo"]
    assert any("content_hop_cost" in p["technique"] for p in repo)
    assert any(p["category"] == "door" for p in PAGES)


def test_attacks_only_point_at_reserved_or_local_hosts():
    for p in PAGES:
        for host in re.findall(r"https?://([^/\s\"'<>)]+)", p["text"]):
            host = host.split("@")[-1]
            assert host.endswith(".example") or host.startswith(("127.0.0.1", "localhost")), (p["id"], host)


def test_the_build_is_deterministic():
    assert corpus.build() == PAGES
    assert corpus.fingerprint(PAGES) == corpus.fingerprint(corpus.build())


# --- tuning / test split: fixed mechanically, before any result -----------------------------------


def test_every_page_is_assigned_to_exactly_one_half():
    assert {p["split"] for p in PAGES} == {"tune", "test"}


def test_the_split_is_stratified_so_both_halves_cover_every_attack_family():
    for half in ("tune", "test"):
        families = {p["family"] for p in PAGES if p["category"] == "attack" and p["split"] == half}
        assert families == {p["family"] for p in PAGES if p["category"] == "attack"}, half


def test_both_halves_have_benign_and_adaptive_pages_in_similar_numbers():
    for category in ("attack", "adaptive", "benign"):
        tune = sum(1 for p in PAGES if p["category"] == category and p["split"] == "tune")
        test = sum(1 for p in PAGES if p["category"] == category and p["split"] == "test")
        assert abs(tune - test) <= 2, (category, tune, test)


def test_the_split_does_not_depend_on_page_order_or_content():
    again = {p["id"]: p["split"] for p in corpus.build()}
    assert again == {p["id"]: p["split"] for p in PAGES}
    assert corpus.split_of("exfil_direct-01", 0) in ("tune", "test")
