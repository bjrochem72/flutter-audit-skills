---
description: "Checks AsyncValue.when() in screen widgets for consistent handling: a loading spinner that ignores the platform, an error branch with no logging or navigation, and a data branch that uses a possibly-null value without checking. Searches screen .when() callbacks and only reports."
---
# Audit: Async State UI (AsyncValue.when)

This audit checks how your screens handle data that loads over time. In Riverpod
that data is an `AsyncValue`, and `AsyncValue.when()` splits it into three cases:
loading, error, and data. The audit looks for three common gaps:

- a loading spinner that ignores the platform,
- an error branch that shows a plain message but does not log the error or move the
  user anywhere,
- a data branch that uses a value that might be null without checking for null
  first.

It reports what it finds and does not change any code.

> **Other state managers.** This is written for **Riverpod** (`AsyncValue.when`).
> The same idea works with any tool that splits loading, error, and data, such as
> `AsyncSnapshot` in a `FutureBuilder` or `StreamBuilder`, or a `bloc` state switch.

## Scope

- Include your screen widgets. Default: `lib/**/*_screen.dart`. Change the pattern
  to match how you name screens (a `presentation/screens/` folder, `*_page.dart`,
  and so on).
- Only `.when()` callbacks. Not button spinners or small in-list loaders, which are
  listed as allowed cases below.
- Skip generated files (`*.g.dart`, `*.freezed.dart`) and `test/`.
- Note any file the project marks as locked or do-not-edit as a Blocker.

## Severity legend

| Severity | Meaning |
|---|---|
| **HIGH** | A clear gap: a spinner that ignores the platform, an error screen with no logging, or a value used without a null check |
| **MEDIUM** | A likely gap that depends on context |
| **OK** | Meant to be there (a button or in-list loader): listed in an appendix only |

---

## How to run

### Step 1 - Before you start

1. Note any locked or do-not-edit file as a **Blocker**.
2. **Check past decisions** (`AUTHORING.md`, Making an audit trustworthy) so you do
   not raise something already settled:
   ```bash
   gh issue list --state closed --search "AsyncValue OR loading OR error screen in:title,body" --limit 15
   git log --oneline -15 -- lib
   ```
3. **(Optional) Record a starting count** (`AUTHORING.md`, Improving an audit over
   time): the number of `.when(` uses, to track changes on later runs.

### Step 2 - Run the searches

A search result is a possible case. Read a few lines around it and apply the rule.
Keep every search inside your screen pattern; do not widen it to all of `lib`, or
you pick up `///` comment examples in other files that are out of scope. These are
narrow single-line patterns: they catch the common arrow-callback shape, not
block-body branches, callbacks split over lines, or every message string. Finding
nothing means those exact shapes are not present (and that the pattern matched some
files). It is not a promise that nothing is wrong; AS4's read of every `.when()`
branch is the thorough check.

#### AS1 - An iOS-style spinner in a `.when()` loading branch (HIGH)
```bash
rg -n 'loading:\s*\(\)\s*=>.*CupertinoActivityIndicator' lib -g '**/*_screen.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
Record a hit only when it is the `loading:` branch of a top-level `.when(` (not a
button or in-list spinner). A `CupertinoActivityIndicator` shows the iOS spinner on
every platform. Fix: `CircularProgressIndicator.adaptive()` (or your app's shared
loading widget).

#### AS2 - A spinner that ignores the platform in a `.when()` loading branch (HIGH)
```bash
rg -n 'loading:\s*\(\)\s*=>.*CircularProgressIndicator\(' lib -g '**/*_screen.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
Record a hit only when it is a non-`.adaptive()` spinner in a `.when()` `loading:`
branch (the pattern matches the spinner with or without arguments;
`CircularProgressIndicator.adaptive()` is not matched, because its `(` follows
`.adaptive`). Fix: add `.adaptive()`, or use your app's shared loading widget.

#### AS3 - An error branch with a plain message and no logging or navigation (HIGH)
```bash
rg -n 'error:\s*\(.*\)\s*=>.*\bText\(' lib -g '**/*_screen.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
This finds single-line `error:` arrow branches that show a `Text`. **Read each one**
(and the block-body error branches you find through AS4's `.when(` search; this
pattern only sees single-line arrows). Record a hit only when the branch shows a
plain message with no error report (no call to your logger, Sentry, or Crashlytics)
and no navigation. Fix: use your app's shared error widget that reports the error,
or a not-found or empty state.

#### AS4 - A possibly-null value used in a `data:` branch without a check (MEDIUM)
```bash
rg -n '\.when\(' lib -g '**/*_screen.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
Then read each `data:` branch. Record a hit only when it uses a value that might be
null without an early check (`if (x == null) return <empty/not-found state>;`). Fix:
add the null check. This is the read-heavy check: expect many `.when(` uses, most of
them fine.

### Step 3 - Check each result (drop anything that does not hold)

Re-read each `file:line`. Drop any result that is:
- a button spinner or a small in-list loader (see Allowed cases);
- a `.when()` whose branch already uses the right widget;
- **a comment**: a result on a `//` or `///` line. Comment examples often quote
  these exact patterns; a comment is never a finding.

Every finding you keep names a `file:line` you read and a one-line quote.

### Step 4 - Report

```markdown
## Async State UI Audit

### Summary
`.when()` uses: <N> - loading gaps: <a> - error gaps: <b> - null gaps: <c>

### Findings (HIGH / MEDIUM)
| ID | file:line | Evidence | Fix |
|---|---|---|---|
(or "None")

### Not reported (if any)
- [case]: [why it was skipped or was already decided]

### Blockers
<locked/do-not-edit files; "(none)" if none>
```

After the report, ask: **"Which finding do you want to fix first, or stop at
planning?"** Do not change any code without approval.

---

## Fix reference - which widget to use

This audit does not assume your app's widgets, so the fixes name Flutter defaults or
"your shared X". Map them to your own design system.

| Case | Inside `.when()` (branch returns the screen body) | Outside `.when()` (returns just content) |
|---|---|---|
| `loading:` | your shared loading screen, or `CircularProgressIndicator.adaptive()` | `CircularProgressIndicator.adaptive()` |
| `error:` (report it) | your shared error screen that logs | your shared error content that logs |
| `error:` (no logging) | your not-found / empty screen | your not-found / empty content |
| `data:` null | your not-found / empty screen | your not-found / empty content |

## Allowed cases (OK - appendix, never a finding)

- **Button loading**: a `CupertinoActivityIndicator` inside a button.
- **In-list loading**: a `CircularProgressIndicator` in a list tile.

## Calibrating for your codebase

These are simple `.when()`-branch patterns. Known sources of false matches (handled
by the rules):
- Button or in-list spinners rather than a `.when()` branch: handled by the
  screens-only scope and the Step 3 check.
- `///` comment examples that quote the patterns: handled by the screens pattern and
  the Step 3 comment rule.

Adjust the screen pattern to your layout, record your own starting count, and check
against one feature before a wider run.
