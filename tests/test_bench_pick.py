from bench.pick import patch_test_files, pick

PATCH = "diff --git a/t/test_a.py b/t/test_a.py\n--- a/t/test_a.py\n+++ b/t/test_a.py\n@@\n+x\n--- /dev/null\n+++ b/t/test_new.py\n"


def row(iid, repo, difficulty="<15 min fix"):
    return {"instance_id": iid, "repo": repo, "image": "img", "base_commit": "c", "difficulty": difficulty,
            "problem_statement": "p", "test_patch": PATCH}


def test_patch_test_files():
    assert patch_test_files(PATCH + "+++ b/t/data.toml\n") == ["t/test_a.py", "t/test_new.py"]


def test_pick_filters_caps_and_orders():
    rows = [
        row("django__django-1", "django/django"),
        row("psf__requests-3", "psf/requests", "1-4 hours"),
        row("psf__requests-2", "psf/requests"),
        row("psf__requests-1", "psf/requests"),
        row("pallets__flask-1", "pallets/flask", "15 min - 1 hour"),
    ]
    ids = [c["instance_id"] for c in pick(rows, n=10, per_repo=2)]
    assert ids == ["psf__requests-1", "psf__requests-2", "pallets__flask-1"]
