#!/usr/bin/env python3
"""ref_after_await.py - a CI-friendly finder for the Riverpod disposal race.

Flags Dart code that uses a Riverpod `ref` (`ref.read/watch/listen(`) *after* an
`await`, within the same brace scope, without an intervening `mounted` /
`ref.mounted` / `context.mounted` guard. Using `ref` after the provider or widget
disposed during the await throws a StateError - an intermittent production crash.

This is a deliberately CONSERVATIVE line/scope heuristic, not a type-aware
analyzer: it errs toward *fewer* false positives so it's safe to gate CI on.
Consequences of that trade-off (documented, not bugs):
  * It clears suspicion on ANY `mounted` token seen after the await in that scope,
    so the rarer `if (mounted) {...} else { ref.read(...) }` shape (ref on the
    disposed else-branch) is NOT flagged. Review those by eye.
  * Scope is approximated by brace depth, which is reliable on dart-formatted code.
  * It is line/regex based, not string-aware: `await`/`mounted`/`ref.` tokens or
    braces inside string literals can mis-open or clear a window or skew depth. Rare
    in dart-formatted code; review a surprising result by eye.
  * It matches the conventional identifier `ref` only (ref.read/watch/listen). A
    WidgetRef stored under another name (e.g. `widgetRef`) is not detected - rename
    it to `ref` or extend REF_USE_RE for your codebase.
Every hit is still a CANDIDATE - read the enclosing method before acting.

Usage:
    python3 ref_after_await.py [PATH ...]         # report candidates (default: lib)
    python3 ref_after_await.py --ci [PATH ...]    # exit 1 if any UNSUPPRESSED hit
    python3 ref_after_await.py --self-test        # run the built-in test cases
    --allow FILE   # allowlist of verified-safe sites (default: .ref-after-await-allow)

Allowlist: one entry per line. An entry matches a finding if it equals the
finding's "path:line" OR is a substring of the offending line of code. Prefer a
path:line entry; a bare substring can also suppress a later, genuinely unsafe line
with the same text. Lines starting with '#' are comments. Suppress a site only
after you've verified it's safe (hoisted read, guarded else, etc.).
"""
from __future__ import annotations

import argparse
import os
import re
import sys

AWAIT_RE = re.compile(r"(^|[^\w.])await\b")   # covers `await foo`, `await(foo)`, line-broken await
REF_USE_RE = re.compile(r"\bref\.(read|watch|listen)\s*\(")
GUARD_RE = re.compile(r"\bmounted\b")            # context.mounted / ref.mounted / !mounted / if (mounted)
ARROW_RE = re.compile(r"=>")                     # arrow closure on the same line -> deferred, skip

# Generated Dart files are excluded, per the audit. Extend for other codegen
# in your project (e.g. .gr.dart, .mocks.dart, .config.dart).
GENERATED_SUFFIXES = (".g.dart", ".freezed.dart")


def _strip_comment(line: str) -> str:
    """Drop a trailing // comment (naive: ignores // inside strings - fine here)."""
    idx = line.find("//")
    return line[:idx] if idx != -1 else line


def scan_lines(lines: list[str]) -> list[tuple[int, str]]:
    """Return [(line_no, offending_code)] for unguarded ref-after-await candidates.

    Model: an `await` opens a "suspicion window" at its brace depth. While open,
    a `ref.read/watch/listen(` at that depth or deeper is a candidate - unless a
    `mounted` guard has since been seen (window cleared) or the use is an arrow
    closure. The window closes when the scope that owned the await exits (depth
    drops below the await's depth), so state never leaks across functions.
    """
    findings: list[tuple[int, str]] = []
    depth = 0
    await_depth: int | None = None   # brace depth at which the open await sits
    guarded = False                  # a mounted guard seen since the await

    for i, raw in enumerate(lines, start=1):
        code = _strip_comment(raw)
        depth_at_line_start = depth

        # Close the suspicion window if we've exited the awaiting scope.
        if await_depth is not None and depth_at_line_start < await_depth:
            await_depth = None
            guarded = False

        if await_depth is not None and GUARD_RE.search(code):
            guarded = True

        if await_depth is not None and not guarded and not ARROW_RE.search(code):
            # Any ref use inside an OPEN window is a candidate - including
            # `x = await ref.watch(p.future)`. An earlier await already suspended,
            # so ref may be disposed; being the awaited expression does not save it.
            # (A ref on the window-OPENING await line is not reached here: that line
            # opens the window below, after this check, so its own ref is exempt.)
            if REF_USE_RE.search(code):
                findings.append((i, raw.rstrip()))

        # A new await is a fresh suspension point, so any prior `mounted` guard no
        # longer protects code after it: re-arm suspicion. This catches
        # `await x(); if (!mounted) return; await y(); ref.read(p);` - the guard sits
        # before y, so the post-y ref is still a candidate.
        m = AWAIT_RE.search(code)
        if m:
            guarded = False
            if await_depth is None:
                # Open the window at the brace depth *at the await token*, so a
                # single-line function `a() async { await x(); }` doesn't leak its
                # window into the next function (whose body is a sibling scope).
                prefix = code[: m.start()]
                await_depth = depth_at_line_start + prefix.count("{") - prefix.count("}")

        depth += code.count("{") - code.count("}")

    return findings


def load_allowlist(path: str) -> list[str]:
    if not path or not os.path.isfile(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line)
    return out


def is_allowed(rel_path: str, line_no: int, code: str, allow: list[str]) -> bool:
    # Normalise separators and match path:line as a SUFFIX, so a repo-relative entry
    # (lib/foo.dart:12) matches whether the scan ran with a relative or absolute path.
    # A code substring still matches too.
    norm = rel_path.replace("\\", "/")
    key = f"{norm}:{line_no}"
    for entry in allow:
        e = entry.replace("\\", "/")
        if e == key or key.endswith("/" + e) or entry in code:
            return True
    return False


def iter_dart_files(paths: list[str]):
    for base in paths:
        if (
            os.path.isfile(base)
            and base.endswith(".dart")
            and not base.endswith(GENERATED_SUFFIXES)
        ):
            yield base
            continue
        for root, _dirs, files in os.walk(base):
            # Match path *components* (normalise Windows '\\') so the exclusion works
            # cross-platform and when a top-level 'build'/'.git' is scanned directly.
            parts = root.replace("\\", "/").split("/")
            if any(seg in parts for seg in (".git", "build", ".dart_tool")):
                continue
            for name in files:
                if name.endswith(".dart") and not name.endswith(GENERATED_SUFFIXES):
                    yield os.path.join(root, name)


def run(paths: list[str], allow_path: str, ci: bool) -> int:
    allow = load_allowlist(allow_path)
    total = 0
    suppressed = 0
    for path in iter_dart_files(paths):
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.readlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line_no, code in scan_lines(lines):
            if is_allowed(path, line_no, code, allow):
                suppressed += 1
                continue
            total += 1
            marker = "::error::" if ci else ""
            print(f"{marker}{path}:{line_no}: ref used after await without a mounted guard")
            print(f"    {code.strip()}")

    if ci:
        if total == 0:
            print(f"::notice::ref-after-await clean - 0 unsuppressed ({suppressed} allowlisted)")
            return 0
        print(f"::error::{total} unguarded ref-after-await candidate(s) - guard or hoist, or allowlist if verified safe")
        return 1
    print(f"\n{total} candidate(s), {suppressed} suppressed. Each is a candidate - read the method before fixing.")
    return 0


# --------------------------------------------------------------------------- #
# Self-test - the scanner's contract, executable.
# --------------------------------------------------------------------------- #
_CASES = [
    ("unguarded_after_await", True, """
Future<void> save() async {
  await useCase.save();
  ref.read(loggerProvider).log('done');
}
"""),
    ("guarded_after_await", False, """
Future<void> save() async {
  await useCase.save();
  if (!context.mounted) return;
  ref.read(loggerProvider).log('done');
}
"""),
    ("ref_mounted_guard", False, """
Future<void> save() async {
  await useCase.save();
  if (!ref.mounted) return;
  ref.read(loggerProvider).log('done');
}
"""),
    ("hoisted_before_await", False, """
Future<void> save() async {
  final logger = ref.read(loggerProvider);
  await useCase.save();
  logger.log('done');
}
"""),
    ("arrow_closure_skipped", False, """
Widget build() {
  return Button(onPressed: () async {
    await x();
  }, onLongPress: () => ref.read(p).thing());
}
"""),
    ("no_await_no_flag", False, """
void save() {
  ref.read(loggerProvider).log('done');
}
"""),
    ("window_closes_next_function", False, """
Future<void> a() async { await x(); }
void b() { ref.read(p).thing(); }
"""),
    ("second_use_after_await_flagged", True, """
Future<void> save() async {
  await a();
  ref.read(p).one();
}
"""),
    ("awaited_ref_read_after_prior_await", True, """
Future<void> load() async {
  await setup();
  final x = await ref.watch(p.future);
}
"""),
    ("awaited_ref_read_is_the_only_await", False, """
Future<void> load() async {
  final x = await ref.watch(p.future);
}
"""),
    ("guard_then_second_await_reref", True, """
Future<void> save() async {
  await a();
  if (!context.mounted) return;
  await b();
  ref.read(p).go();
}
"""),
]


def self_test() -> int:
    ok = True
    for name, should_flag, src in _CASES:
        hits = scan_lines(src.splitlines(keepends=True))
        flagged = len(hits) > 0
        status = "PASS" if flagged == should_flag else "FAIL"
        if flagged != should_flag:
            ok = False
        print(f"[{status}] {name} (expected {'flag' if should_flag else 'clean'}, got {len(hits)} hit(s))")
    print("\nAll self-tests passed." if ok else "\nSELF-TEST FAILURES.")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Find unguarded ref-after-await (Riverpod disposal race).")
    ap.add_argument("paths", nargs="*", default=["lib"], help="files/dirs to scan (default: lib)")
    ap.add_argument("--ci", action="store_true", help="exit 1 on any unsuppressed hit, terse output")
    ap.add_argument("--allow", default=".ref-after-await-allow", help="allowlist file")
    ap.add_argument("--self-test", action="store_true", help="run built-in test cases and exit")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    paths = args.paths or ["lib"]
    return run(paths, args.allow, args.ci)


if __name__ == "__main__":
    sys.exit(main())
