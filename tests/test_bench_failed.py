from bench.failed_patches import choose

RANKED = [("strong", "lite/strong", {"x__x-1"}), ("mid", "lite/mid", set()), ("weak", "lite/weak", set())]


def reports(**by_system):
    return lambda prefix, iid: {iid: by_system[prefix.split("/")[1]]} if prefix.split("/")[1] in by_system else None


def test_skips_resolved_unapplied_and_empty_patches():
    rep = reports(
        mid={"patch_successfully_applied": False, "resolved": False},  # didn't apply to base
        weak={"patch_successfully_applied": True, "resolved": False},
    )
    pick = choose("x__x-1", RANKED, rep, lambda prefix, iid: f"diff from {prefix}")
    assert pick == {"system": "weak", "patch": "diff from lite/weak"}  # "strong" resolved it


def test_prefers_the_strongest_qualifying_system():
    ok = {"patch_successfully_applied": True, "resolved": False}
    pick = choose("y__y-2", RANKED, reports(strong=ok, mid=ok), lambda p, i: "d")
    assert pick["system"] == "strong"


def test_needs_an_official_not_resolved_and_a_non_empty_patch():
    ok = {"patch_successfully_applied": True, "resolved": False}
    assert choose("y__y-2", RANKED, reports(strong={"patch_successfully_applied": True}), lambda p, i: "d") is None
    assert choose("y__y-2", RANKED, reports(strong=ok, mid=ok, weak=ok), lambda p, i: "  \n") is None
