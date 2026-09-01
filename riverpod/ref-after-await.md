---
description: "Riverpod disposal race: a `ref` (Ref or WidgetRef) used after an `await` with no mounted/ref.mounted check in between, in an autoDispose provider or a Consumer widget callback. If the provider or widget was disposed during the await, using ref throws a StateError. Whole-repo search, report-only."
---
# Audit: Ref-After-Await (Riverpod disposal race)

This audit finds places where a Riverpod `ref` is used **after an `await`** without
a `mounted` check. If the provider or widget is **disposed during the await** (the
user leaves the screen, or an autoDispose provider is no longer watched), the next
`ref.read`, `ref.watch`, or `ref.listen` (or a saved `WidgetRef`) throws a
`StateError` (`Cannot use "ref" after the widget was disposed`, or `Bad state`).
This is an occasional crash that is hard to reproduce: it shows up in real use, not
in tests. **The audit reports possible cases and does not change your code.**

## The rule

After any `await`, treat the `ref` as **maybe already gone**:

```dart
// BAD: crashes if disposed during the await
Future<void> _save() async {
  await useCase.save();
  ref.read(loggerProvider).log('saved');   // <-- ref after await, no check
}

// GOOD: check the disposed case first
Future<void> _save() async {
  final logger = ref.read(loggerProvider); // read BEFORE the await
  await useCase.save();
  if (!context.mounted) return;            // or: if (!ref.mounted) return;
  logger.log('saved');
}
```

Two safe forms, both fine (never flag them):
- **Read early:** move the `ref.read(...)` into a local **before** the first
  `await`, then use the local afterwards.
- **Check:** add `if (!context.mounted) return;` (widgets) or `if (!ref.mounted)
  return;` (a Ref or provider, Riverpod 3.0 or later) **between** the `await` and the
  `ref` use. `ref.mounted` is new in Riverpod 3.0. On Riverpod 2 there is no
  `ref.mounted`, so check widgets with `context.mounted`, and read early or
  restructure provider code instead.

## Scope

- **Where it matters most:** `autoDispose` providers, and `ConsumerWidget` or
  `ConsumerStatefulWidget` async callbacks (button handlers, `onTap`, form submits)
  that `await` and then use `ref` or a `WidgetRef`.
- **Lower risk:** providers kept alive for the relevant part of the app. They are
  not dropped just because their listeners go away, but a rebuild can still dispose
  the previous state, so it is still worth flagging as a latent risk.
- Include `lib/**/*.dart`. Skip generated files and `test/`.

## How to run

### Step 1 - Scope first, then find possible cases

**Run this on one file or feature by default.** Point it at the widget or provider
you just changed. A whole-repo search with a plain pattern matches far too much: in
a large app *hundreds* of files legitimately `await` and then use `ref`, so a blunt
pattern returns thousands of results no one will read. The reliable whole-repo
version is the CI script (see below), not a search.

```bash
# candidate FILES in a path: those using BOTH await and ref - inspect each
rg -l 'ref\.(read|watch|listen)\(' <path> -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart' -g '!test/**' |
  while IFS= read -r file; do
    rg -l 'await ' "$file"
  done
```

In each file found, look for methods that `await` and **then** use `ref`, and apply
the rule below. (A within-file hint, `rg -n -U 'await [\s\S]{0,400}?ref\.' <file>`,
matches too much, so use it only to find lines to read, never as the finding set.)

### Step 2 - The rule (read the whole method)

For each case, read the whole method it is in, and record a finding **only if all**
of these are true:
1. A `ref.` use (or a saved `WidgetRef`) is **reached only after** an `await` on
   that path.
2. There is **no** `mounted` or `ref.mounted` check between the `await` and the use
   on that path.
3. The use after the `await` is **not** on a value read from `ref.read/watch/listen`
   before the `await`. (Moving `ref` itself into a local, `final r = ref;`, does not
   make a later `r.read(...)` safe. Only moving the *result* does.)

**Do NOT flag (the common false matches):**
- **Read early** - `final x = ref.read(p);` appears before the `await`; the use after
  is on the local, not on `ref`.
- **Arrow callback** - `onPressed: () => ref.read(p).doThing()` passed to a widget.
  The callback runs later in a valid place, not in the current async flow. (A
  *block-body* callback that runs straight away in this flow is not exempt: read it.)
- **Checked** - the use sits inside `if (context.mounted) { ... }` or `if
  (ref.mounted) { ... }`, or the method returns early on `!mounted` first.
- **No `await` before it** on that path.

**Watch two easy-to-miss cases** a quick line scan can miss:
- **`if (mounted) ... else { ref.read(...) }`** - the `else` runs on the *disposed*
  path. A `ref.` in the `else` is a finding unless it checks again.
- **catch blocks** - `try { await ... } catch (e) { ref.read(loggerProvider)... }`
  runs after the `await`, on a path that may be disposed. Flag a `ref.` in the catch
  with no check.

### Step 3 - Report

```markdown
## Ref-After-Await Audit

### Summary
| Checked correctly | No check (findings) | Cases inspected |
|---|---|---|

### Findings
| file:line | Method | ref use after await | Fix (read early / check) |
(or "None")

### Prior decisions (not re-raised)
| ref | Item | Why out of scope |

### Blockers
<locked/do-not-edit files; "(none)" if none>
```

Fix each one by **reading early** (move the read before the `await`), or, in widgets
and Riverpod 3.0+ provider code, adding a `mounted` check after it (`if
(!context.mounted) return;` or `if (!ref.mounted) return;`). Note: in Riverpod,
adding the check sometimes means moving *all* later `ref.read`s above the first
`await` anyway (once one check returns early, later reads must still be valid). Do it
the same way throughout.

---

## Optional: whole-repository CI check (`ref_after_await.py`)

Do the file- or feature-scoped audit above first. When you want a whole-repo check,
this repository ships a small Python script with no dependencies,
`ref_after_await.py`. Copy it into your project (for example into `tool/`) and run
it from the project root:

```bash
python3 tool/ref_after_await.py lib            # list possible cases
python3 tool/ref_after_await.py --ci lib       # exit 1 on any hit not on the allow list (CI/pre-commit)
python3 tool/ref_after_await.py --self-test    # check the script against its own examples
```

It is a **careful** line and scope scanner: it prefers to miss a case rather than
raise a false one, so gating CI on it will not fail the build on noise. It is a
heuristic with a few known blind spots (below), so it catches the common shape, not
every one. It has an allow list for places you have checked and know are safe:

- Make a `.ref-after-await-allow` file, and add one entry per place you have
  **checked** and know is safe (read early, checked `else`, and so on). Prefer a
  `path:line` entry. Use a piece of the line only when that line is one of a kind,
  since a plain piece of text can also silence a later, genuinely unsafe line with
  the same text. `--ci` then fails only on cases not on the list.
- Known trade-offs (written in the script header, not bugs): it stops being
  suspicious after any `mounted` word once the `await` has passed, so the rare
  `if (mounted) ... else { ref... }` shape needs a person to review it; scope is
  worked out from brace depth (reliable on `dart format`-ed code).
- It looks for the usual name `ref` (`ref.read/watch/listen`). A `WidgetRef` stored
  under another name (for example `widgetRef`) is not matched: check those by eye,
  or extend the pattern for your codebase.
- It skips generated files by ending (`*.g.dart`, `*.freezed.dart`). Add other
  generated endings (`*.gr.dart`, `*.mocks.dart`, and so on) for your project.

How to use it: run it, read each case against the rule above, fix the real ones, add
the safe ones to the allow list, then wire `--ci` into CI so new ones fail the build.

## Calibrating for your codebase

- The `{0,400}` window in Step 1 is a starting point. Widen it for long methods, but
  always **read the whole method**, not just the window.
- Most cases are safe (read early or checked), so expect few real hits. That is the
  point: this bug is rare, but it crashes when it happens, and it hides from tests.
- Turn a new safe-or-unsafe shape into a rule only after it holds on two or more
  places (`AUTHORING.md`, Improving an audit over time).
