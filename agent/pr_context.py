"""What LOCALIZE and REPRODUCE may know about a PR beyond its changed paths: its interface, never its implementation.

- interface(): signatures (from the AST, no bodies, docstrings or decorators) of functions and classes the
  PR adds or re-signatures, and the names of functions whose bodies it changes.
- related_test(): the existing test file that best covers the changed modules, chosen without a model.
"""

import ast
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from agent import guards, tools

HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def source_paths(paths):
    return [p for p in paths if p.endswith(".py") and not guards.is_test_file(p)]


def changed_lines(patch):
    """{path: (base line numbers removed, head line numbers added)}."""
    lines, path, old_n, new_n = {}, None, 0, 0
    old_path = None
    for line in patch.splitlines():
        if line.startswith("--- "):
            old_path = guards._diff_path(line)
        elif line.startswith("+++ "):
            path = guards._diff_path(line) or old_path
            lines.setdefault(path, (set(), set()))
        elif (m := HUNK.match(line)) and path:
            old_n, new_n = int(m.group(1)), int(m.group(2))
        elif path and line.startswith("-"):
            if line[1:].strip():  # a blank line between methods would otherwise count as a change to the class
                lines[path][0].add(old_n)
            old_n += 1
        elif path and line.startswith("+"):
            if line[1:].strip():
                lines[path][1].add(new_n)
            new_n += 1
        elif path and line.startswith(" "):
            old_n += 1
            new_n += 1
    return lines


def signatures(source):
    """{qualified name: (signature text, first line, last line)} for every def and class."""
    found = {}

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{child.name}"
                ret = f" -> {ast.unparse(child.returns)}" if child.returns else ""
                kw = "async def" if isinstance(child, ast.AsyncFunctionDef) else "def"
                found[name] = (f"{kw} {name}({ast.unparse(child.args)}){ret}", child.lineno, child.end_lineno)
                visit(child, f"{name}.")
            elif isinstance(child, ast.ClassDef):
                name = f"{prefix}{child.name}"
                bases = ", ".join(ast.unparse(b) for b in child.bases + child.keywords)
                found[name] = (f"class {name}({bases})" if bases else f"class {name}", child.lineno, child.end_lineno)
                visit(child, f"{name}.")

    visit(ast.parse(source), "")
    return found


def innermost(defs, line):
    hits = [(end - start, name) for name, (_, start, end) in defs.items() if start <= line <= end]
    return min(hits)[1] if hits else None


def head_sources(root, patch, paths):
    """{path: head source} for the given paths, by applying the patch to copies in a temp dir."""
    with tempfile.TemporaryDirectory() as d:
        for p in paths:
            if (Path(root) / p).exists():
                (Path(d) / p).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(Path(root) / p, Path(d) / p)
        includes = [f"--include={p}" for p in paths]
        r = subprocess.run(["git", "apply", "--whitespace=nowarn", *includes, "-"], cwd=d, input=patch,
                           capture_output=True, text=True)
        if r.returncode:
            return {}
        return {p: (Path(d) / p).read_text() for p in paths if (Path(d) / p).exists()}


def interface(root, patch, paths):
    """Text block listing the PR's interface changes, or "" if there is nothing to show."""
    paths = source_paths(paths)
    heads = head_sources(root, patch, paths)
    lines = changed_lines(patch)
    out = []
    for p in paths:
        try:
            base_file = Path(root) / p
            base = signatures(base_file.read_text()) if base_file.exists() else {}
            head = signatures(heads[p]) if p in heads else {}
        except (SyntaxError, ValueError, UnicodeDecodeError):
            continue  # old or unparsable code: show nothing rather than guess
        resigned = [n for n, (sig, _, _) in head.items() if n not in base or base[n][0] != sig]
        removed, added = lines.get(p, (set(), set()))
        bodies = {innermost(head, n) for n in added} | {innermost(base, n) for n in removed}
        bodies = sorted(b for b in bodies if b and b not in resigned)
        out += [f"{p}: changed signature: {head[n][0]}" for n in resigned]
        out += [f"{p}: body changed: {', '.join(bodies)}"] if bodies else []
    if not out:
        return ""
    return ("\n\nInterface of the pull request (signatures and names only; the implementation is hidden):\n"
            + "\n".join(out))


def module_names(path):
    """(dotted module, stem) for a source path, e.g. src/flask/config.py -> (flask.config, config)."""
    parts = path[:-3].split("/")
    if parts[0] in ("src", "lib") and len(parts) > 1:
        parts = parts[1:]
    if parts[-1] == "__init__" and len(parts) > 1:
        parts = parts[:-1]
    return ".".join(parts), parts[-1]


def related_test(root, paths, exclude=""):
    """(path, score) of the tracked test file that best covers the changed modules, or None."""
    names = [module_names(p) for p in source_paths(paths)]
    if not names:
        return None
    best = None
    # Not tools.list_files: that truncates at 200 lines, and big repos keep their tests further down.
    tracked = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True).stdout
    for path in tracked.splitlines():
        if not path.endswith(".py") or not guards.is_test_file(path) or path == exclude:
            continue
        try:
            text = (Path(root) / path).read_text()
        except (OSError, UnicodeDecodeError):
            continue
        score = 0
        for dotted, stem in names:
            score += 10 if f"test_{stem}" in Path(path).name else 0
            score += 5 if dotted in text else 0
            score += min(5, len(re.findall(rf"\b{re.escape(stem)}\b", text)))
        if score and (best is None or (score, -len(path)) > (best[1], -len(best[0]))):
            best = (path, score)
    return best


def related_test_block(root, paths, exclude=""):
    best = related_test(root, paths, exclude)
    if not best:
        return ""
    return (f"\n\nAn existing test file for the changed code ({best[0]}, first 150 lines). Import and set up "
            f"things the same way:\n{tools.read_file(root, best[0], 1, 150)}")
