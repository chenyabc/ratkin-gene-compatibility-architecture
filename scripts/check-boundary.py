#!/usr/bin/env python3
"""Fail closed when excluded material appears in the architecture repository."""

from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

# The repository is a clean-room documentation repository with a small,
# fully reviewed surface. Any path not listed here is rejected by default,
# in both the working tree and every reachable historical commit.
WORKFLOW_PATH = Path(".github/workflows/boundary-check.yml")
PRE_PUSH_PATH = Path(".githooks/pre-push")
CHECKER_PATH = Path("scripts/check-boundary.py")

ALLOWED_REPOSITORY_FILES = {
    WORKFLOW_PATH,
    Path(".gitignore"),
    PRE_PUSH_PATH,
    Path("LICENSE"),
    Path("README.md"),
    Path("THIRD_PARTY_REFERENCES.md"),
    Path("docs/ARCHITECTURE.md"),
    Path("docs/CLEAN_ROOM_BOUNDARY.md"),
    Path("docs/COMPATIBILITY_MATRIX.md"),
    Path("docs/RUNTIME_COLOR_PIPELINE.md"),
    Path("docs/XML_PATCH_STRATEGY.md"),
    Path("examples/ConditionalPatch.example.xml"),
    Path("examples/RuntimeGraphicCorrection.pseudocode.cs"),
    CHECKER_PATH,
}

LOCKED_FILE_CONTENTS = {
    WORKFLOW_PATH: (
        "name: boundary-check\n"
        "on:\n"
        "  push:\n"
        "  pull_request:\n"
        "\n"
        "permissions:\n"
        "  contents: read\n"
        "\n"
        "jobs:\n"
        "  check:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n"
        "        with:\n"
        "          fetch-depth: 0\n"
        "          persist-credentials: false\n"
        "      - run: python3 scripts/check-boundary.py\n"
    ),
    PRE_PUSH_PATH: (
        "#!/bin/sh\n"
        "# Run the clean-room boundary gate before pushing. This is a convenience\n"
        "# guard against accidental pushes, not a security boundary: it can be\n"
        "# bypassed with --no-verify or by pushing through the web UI / API.\n"
        "set -e\n"
        "repo_root=$(git rev-parse --show-toplevel)\n"
        "python3 \"$repo_root/scripts/check-boundary.py\"\n"
    ),
}

EXPECTED_HEAD_MODES = {
    WORKFLOW_PATH: "100644",
    PRE_PUSH_PATH: "100755",
}

# Split the marker so the checker source does not contain a literal LFS pointer
# header that would trip its own historical content scan.
LFS_POINTER_HEADER = "version https://git-lfs.github.com/spec/" + "v1"

# examples/ is intentionally a narrow, reviewed surface. New examples must be
# explicitly admitted here instead of being accepted by naming heuristics.
ALLOWED_EXAMPLE_FILES = {
    Path("examples/ConditionalPatch.example.xml"),
    Path("examples/RuntimeGraphicCorrection.pseudocode.cs"),
}

ALLOWED_XML_XPATHS = {
    '/Defs/ExampleRaceSettings[defName="ExampleRace"]/bodyAddons/li[id="ExampleEar"]/colorChannel',
    '/Defs/ExampleRaceSettings[defName="ExampleRace"]/bodyAddons/li[id="ExampleEar"]',
}
ALLOWED_XML_COMMENT = (
    "仅用于解释 Conditional Add/Replace 结构。\n"
    "ExampleRace、ExampleEar 和所有路径均为虚构标识，不能直接用于游戏。"
)

ALLOWED_CS_COMMENTS = {
    "Conceptual pseudocode only.",
    "The types and APIs are intentionally incomplete and fictional.",
    "Preserve the upstream texture, shader, draw size and variant choice.",
    "Only the conflicting color dimension is replaced.",
}
ALLOWED_CS_IDENTIFIERS = {
    "AddonNodeLike",
    "AlreadyMatches",
    "ColorPair",
    "ColorPolicy",
    "CompatibilityScope",
    "CorrectFinalGraphic",
    "Graphic",
    "GraphicPolicy",
    "GraphicsCache",
    "HasValue",
    "IsTargetEarOrTail",
    "IsTargetPawn",
    "MarkDirty",
    "OnRelevantLifecycleBoundary",
    "Optional",
    "PawnLike",
    "RelevantPawnsOnly",
    "TryRecolor",
    "TryResolveExpectedColors",
    "Value",
    "WorldLike",
    "expected",
    "foreach",
    "if",
    "in",
    "node",
    "original",
    "pawn",
    "return",
    "void",
    "world",
}

SECRET_PATTERNS = (
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "private key"),
    (r"\bgithub_pat_[A-Za-z0-9_]+\b", "GitHub token"),
    (r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", "GitHub token"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS access key"),
    (r"(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token|secret)\s*[:=]", "credential assignment"),
    (r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", "bearer token"),
)

# Boundary-sensitive files use blob approval for history. The current HEAD blob
# is allowed automatically. Any older version must be explicitly reviewed and
# added here, so deleting a bad version in a later commit cannot make it vanish
# from the gate.
APPROVED_HISTORICAL_BLOBS: dict[Path, set[str]] = {}
SENSITIVE_HISTORY_PATHS = {CHECKER_PATH, WORKFLOW_PATH, PRE_PUSH_PATH} | ALLOWED_EXAMPLE_FILES

errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def normalize_comment(text: str | None) -> str:
    lines = (text or "").strip().splitlines()
    return "\n".join(line.strip() for line in lines)


def describe(context: str | None, message: str) -> str:
    return f"{context}: {message}" if context else message


def check_secret_text(relative: Path | str, text: str, context: str | None = None) -> None:
    for pattern, label in SECRET_PATTERNS:
        if re.search(pattern, text):
            fail(describe(context, f"{label}: {relative}"))


def check_lfs_pointer(relative: Path | str, text: str, context: str | None = None) -> None:
    if LFS_POINTER_HEADER in text:
        fail(describe(context, f"Git LFS pointer not allowed: {relative}"))


def check_repository_material() -> None:
    actual_files: set[Path] = set()

    for path in ROOT.rglob("*"):
        if ".git" in path.parts:
            continue

        relative = path.relative_to(ROOT)

        if path.is_symlink():
            actual_files.add(relative)
            fail(f"symlink not allowed: {relative}")
            continue
        if not path.is_file():
            continue

        actual_files.add(relative)

        if relative not in ALLOWED_REPOSITORY_FILES:
            fail(f"unreviewed repository file: {relative}")
            continue

        # Every allowed file must be strict UTF-8 text. A binary payload
        # renamed to a text extension (or an archive) is rejected here.
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError) as exc:
            fail(f"non-UTF-8 repository file: {relative} ({exc})")
            continue

        check_lfs_pointer(relative, text)

        expected = LOCKED_FILE_CONTENTS.get(relative)
        if expected is not None and text != expected:
            fail(f"locked repository file content changed: {relative}")

    for relative in sorted(ALLOWED_REPOSITORY_FILES - actual_files, key=str):
        fail(f"expected repository file missing: {relative}")


def check_high_confidence_secrets() -> None:
    checker = Path(__file__).resolve()

    for path in ROOT.rglob("*"):
        if ".git" in path.parts or path.is_symlink() or not path.is_file() or path.resolve() == checker:
            continue
        if path.relative_to(ROOT) not in ALLOWED_REPOSITORY_FILES:
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except UnicodeDecodeError:
            fail(f"non-UTF-8 file skipped by secret scan: {path.relative_to(ROOT)}")
            continue
        except OSError:
            continue

        check_secret_text(path.relative_to(ROOT), text)


def check_example_file_set() -> None:
    examples_dir = ROOT / "examples"
    actual = (
        {
            path.relative_to(ROOT)
            for path in examples_dir.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        if examples_dir.exists()
        else set()
    )

    for relative in sorted(actual - ALLOWED_EXAMPLE_FILES, key=str):
        fail(f"unreviewed example file: {relative}")

    for relative in sorted(ALLOWED_EXAMPLE_FILES - actual, key=str):
        fail(f"expected example missing: {relative}")


def check_example_text_fallback(relative: Path, text: str) -> None:
    patterns = (
        (
            r"(?:[A-Za-z]:\\|/(?:Users|home|opt|var|mnt|srv|tmp|root|etc|volume\d*)/)[^\s\"'<>]+",
            "local filesystem path",
        ),
        (r"\b\d{7,}\b", "long numeric identifier"),
        (
            r"(?<![A-Za-z0-9_])-?\d+\.\d+(?![A-Za-z0-9_])",
            "floating-point production-like value",
        ),
        (
            r"(?<![A-Za-z0-9_])-?\d+\s*,\s*-?\d+(?![A-Za-z0-9_])",
            "coordinate-like numeric pair",
        ),
    )

    for pattern, label in patterns:
        if re.search(pattern, text):
            fail(f"{label}: {relative}")


def check_xml_example(relative: Path, text: str) -> None:
    comments = [
        normalize_comment(match.group(1))
        for match in re.finditer(r"<!--(.*?)-->", text, flags=re.DOTALL)
    ]
    if comments != [ALLOWED_XML_COMMENT]:
        fail(f"unreviewed XML comment content: {relative}")

    try:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        root = ET.fromstring(text, parser=parser)
    except ET.ParseError as exc:
        fail(f"invalid XML ({exc}): {relative}")
        return

    if root.tag != "Patch" or root.attrib:
        fail(f"unexpected XML root: {relative}")
        return

    root_children = list(root)
    if len(root_children) != 1 or root_children[0].tag != "Operation":
        fail(f"unexpected XML top-level structure: {relative}")
        return

    operation = root_children[0]
    if operation.attrib != {"Class": "PatchOperationConditional"}:
        fail(f"unexpected Operation attributes: {relative}")

    children = list(operation)
    if [child.tag for child in children] != ["xpath", "nomatch", "match"]:
        fail(f"unexpected Operation children: {relative}")
        return

    top_xpath, nomatch, match = children
    if top_xpath.attrib or (top_xpath.text or "").strip() not in ALLOWED_XML_XPATHS:
        fail(f"unreviewed XPath: {relative}")

    for node, expected_class in (
        (nomatch, "PatchOperationAdd"),
        (match, "PatchOperationReplace"),
    ):
        if node.attrib != {"Class": expected_class}:
            fail(f"unexpected {node.tag} attributes: {relative}")

        node_children = list(node)
        if [child.tag for child in node_children] != ["xpath", "value"]:
            fail(f"unexpected {node.tag} children: {relative}")
            continue

        xpath_node, value_node = node_children
        if xpath_node.attrib or (xpath_node.text or "").strip() not in ALLOWED_XML_XPATHS:
            fail(f"unreviewed XPath in {node.tag}: {relative}")

        if value_node.attrib:
            fail(f"unexpected value attributes: {relative}")

        value_children = list(value_node)
        if len(value_children) != 1 or value_children[0].tag != "colorChannel":
            fail(f"unexpected value structure: {relative}")
            continue

        color_node = value_children[0]
        if (
            color_node.attrib
            or list(color_node)
            or (color_node.text or "").strip() != "PlaceholderColor"
        ):
            fail(f"unexpected placeholder value: {relative}")

    # Defense in depth: a production-looking identifier cannot be smuggled in
    # through an otherwise unreviewed XML attribute such as defName="...".
    for element in root.iter():
        if element.tag is ET.Comment:
            continue
        allowed_attributes = {
            "Operation": {"Class"},
            "nomatch": {"Class"},
            "match": {"Class"},
        }.get(str(element.tag), set())
        unexpected = set(element.attrib) - allowed_attributes
        if unexpected:
            fail(f"unexpected XML attribute(s) {sorted(unexpected)}: {relative}")


def check_cs_example(relative: Path, text: str) -> None:
    # Every // comment is reviewed, including trailing comments after code.
    comments = {
        match.group(1).strip()
        for match in re.finditer(r"(?m)//([^\r\n]*)", text)
    }
    for comment in sorted(comments - ALLOWED_CS_COMMENTS):
        fail(f"unreviewed C# comment: {relative}")

    # Comments are removed only after they have been reviewed above.
    code = re.sub(r"(?m)//[^\r\n]*", "", text)

    # The pseudocode surface intentionally needs no non-ASCII source text.
    # Rejecting it also prevents Unicode identifiers from bypassing the ASCII
    # identifier allowlist below.
    if not code.isascii():
        fail(f"non-ASCII C# source text: {relative}")

    for pattern, label in (
        (r"\\u[0-9A-Fa-f]{4}|\\U[0-9A-Fa-f]{8}", "Unicode escape"),
        (r'(?s)@"(?:[^"]|"")*"', "verbatim string literal"),
        (r'"(?:\\.|[^"\\])*"', "string literal"),
        (r"'(?:\\.|[^'\\])+'", "character literal"),
        (r"(?m)^\s*using\s+", "using directive"),
        (r"(?m)^\s*namespace\s+", "namespace declaration"),
        (r"(?m)^\s*#\s*\w+", "preprocessor directive"),
        (r"\[\s*[A-Za-z_][A-Za-z0-9_]*(?:Attribute)?\b", "attribute"),
        (
            r"(?<![A-Za-z0-9_])(?:"
            r"0[xX][0-9A-Fa-f](?:_?[0-9A-Fa-f])*(?:[uUlL]{0,2})"
            r"|0[bB][01](?:_?[01])*(?:[uUlL]{0,2})"
            r"|\d(?:_?\d)*(?:\.\d(?:_?\d)*)?(?:[eE][+-]?\d(?:_?\d)*)?(?:[fFdDmMuUlL]{0,2})"
            r")(?![A-Za-z0-9_])",
            "numeric literal",
        ),
    ):
        if re.search(pattern, code):
            fail(f"unexpected C# {label}: {relative}")

    identifiers = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", code))
    for identifier in sorted(identifiers - ALLOWED_CS_IDENTIFIERS):
        fail(f"unreviewed C# identifier {identifier}: {relative}")


def check_examples() -> None:
    for relative in sorted(ALLOWED_EXAMPLE_FILES, key=str):
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            continue

        text = path.read_text(encoding="utf-8", errors="strict")
        check_example_text_fallback(relative, text)

        if path.suffix.lower() == ".xml":
            check_xml_example(relative, text)
        elif path.suffix.lower() == ".cs":
            check_cs_example(relative, text)
        else:
            fail(f"unsupported reviewed example type: {relative}")


def run_git(*args: str) -> subprocess.CompletedProcess[bytes] | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError:
        fail("Git executable not available; cannot verify repository history")
        return None

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        fail(f"Git history command failed ({' '.join(args)}): {stderr or 'unknown error'}")
        return None

    return result


def git_text(*args: str) -> str | None:
    result = run_git(*args)
    if result is None:
        return None
    try:
        return result.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        fail(f"Git command returned non-UTF-8 text: {' '.join(args)}")
        return None


def list_tree(commit: str) -> list[tuple[str, str, str, Path]] | None:
    result = run_git("ls-tree", "-r", "-z", "--full-tree", commit)
    if result is None:
        return None

    entries: list[tuple[str, str, str, Path]] = []
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, object_type, sha = metadata.decode("ascii").split()
            relative = Path(raw_path.decode("utf-8", errors="strict"))
        except (ValueError, UnicodeDecodeError):
            fail(f"history {commit[:12]}: malformed or non-UTF-8 Git tree entry")
            return None
        entries.append((mode, object_type, sha, relative))

    return entries


def read_blob(sha: str, cache: dict[str, bytes]) -> bytes | None:
    if sha in cache:
        return cache[sha]

    result = run_git("cat-file", "blob", sha)
    if result is None:
        return None
    cache[sha] = result.stdout
    return result.stdout


def check_git_history() -> None:
    inside = git_text("rev-parse", "--is-inside-work-tree")
    if inside is None:
        return
    if inside.strip() != "true":
        fail("not running inside a Git work tree; cannot verify repository history")
        return

    top_level = git_text("rev-parse", "--show-toplevel")
    if top_level is None:
        return
    try:
        if Path(top_level.strip()).resolve() != ROOT.resolve():
            fail("boundary checker is not located at the Git repository root it is auditing")
            return
    except OSError:
        fail("unable to resolve Git repository root")
        return

    shallow = git_text("rev-parse", "--is-shallow-repository")
    if shallow is None:
        return
    if shallow.strip() == "true":
        fail("shallow Git clone cannot prove full history; fetch complete history before running the gate")
        return

    rev_list = git_text("rev-list", "--all")
    if rev_list is None:
        return
    commits = [line.strip() for line in rev_list.splitlines() if line.strip()]
    if not commits:
        fail("no reachable Git commits found")
        return

    head_entries = list_tree("HEAD")
    if head_entries is None:
        return
    head_blobs = {
        relative: sha
        for mode, object_type, sha, relative in head_entries
        if object_type == "blob" and mode != "120000"
    }
    head_modes = {
        relative: mode
        for mode, object_type, sha, relative in head_entries
        if object_type == "blob"
    }

    for relative, expected_mode in EXPECTED_HEAD_MODES.items():
        actual_mode = head_modes.get(relative)
        if actual_mode != expected_mode:
            fail(f"HEAD file mode mismatch for {relative}: expected {expected_mode}, got {actual_mode or 'missing'}")

    allowed_sensitive_blobs: dict[Path, set[str]] = {
        path: set(APPROVED_HISTORICAL_BLOBS.get(path, set()))
        for path in SENSITIVE_HISTORY_PATHS
    }
    for path in SENSITIVE_HISTORY_PATHS:
        head_sha = head_blobs.get(path)
        if head_sha:
            allowed_sensitive_blobs[path].add(head_sha)

    blob_cache: dict[str, bytes] = {}
    scanned_secret_blobs: set[tuple[str, Path]] = set()

    for commit in commits:
        context = f"history {commit[:12]}"
        entries = list_tree(commit)
        if entries is None:
            continue

        commit_message = git_text("show", "-s", "--format=%B", commit)
        if commit_message is not None:
            check_secret_text("commit message", commit_message, context)

        author_email = git_text("show", "-s", "--format=%ae", commit)
        committer_email = git_text("show", "-s", "--format=%ce", commit)
        for label, email in (("author", author_email), ("committer", committer_email)):
            if email is not None and not re.search(r"@users\.noreply\.github\.com$", email.strip()):
                fail(describe(context, f"non-noreply {label} email: {email.strip()}"))

        for mode, object_type, sha, relative in entries:
            if relative not in ALLOWED_REPOSITORY_FILES:
                fail(describe(context, f"unreviewed historical file: {relative}"))

            if mode == "120000":
                fail(describe(context, f"symlink not allowed: {relative}"))
                continue
            if object_type == "commit" or mode == "160000":
                fail(describe(context, f"Git submodule not allowed: {relative}"))
                continue
            if object_type != "blob":
                fail(describe(context, f"unexpected Git object type {object_type}: {relative}"))
                continue

            if relative.parts and relative.parts[0] == "examples" and relative not in ALLOWED_EXAMPLE_FILES:
                fail(describe(context, f"unreviewed historical example file: {relative}"))

            if relative in SENSITIVE_HISTORY_PATHS:
                if sha not in allowed_sensitive_blobs.get(relative, set()):
                    fail(describe(context, f"unapproved historical blob {sha}: {relative}"))

            cache_key = (sha, relative)
            if cache_key in scanned_secret_blobs:
                continue
            scanned_secret_blobs.add(cache_key)

            data = read_blob(sha, blob_cache)
            if data is None:
                continue
            try:
                text = data.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                fail(describe(context, f"non-UTF-8 historical blob: {relative}"))
                continue
            check_lfs_pointer(relative, text, context)
            check_secret_text(relative, text, context)


check_repository_material()
check_high_confidence_secrets()
check_example_file_set()
check_examples()
check_git_history()

if errors:
    print("ARCHITECTURE BOUNDARY CHECK FAILED")
    for error in sorted(set(errors)):
        print(f"- {error}")
    sys.exit(1)

print("ARCHITECTURE BOUNDARY CHECK PASSED")
