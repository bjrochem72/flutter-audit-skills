---
description: "Rebuild frequency for Flutter/Riverpod: a streaming (.snapshots()/Stream) provider watched in a large widget's build(), a high-frequency setState() driving a tiny subtree, MediaQuery.of reading too much, and watching a whole object when one field is used (a .select case). Whole-repo search, report-only."
---
# Audit: Rebuild Scope

This audit looks in `lib/` for widgets that redraw a large or unchanging part of the
screen **too often**. It is about how often a part of the screen redraws, not how
big the widget is. What matters is how often a part redraws and how much each redraw
costs. **It reports what it finds and never changes code on its own.**

**What this audit is NOT:** it is not a `const` check (your analyzer is assumed to
turn on `prefer_const_*`, for example through `very_good_analysis` or
`flutter_lints`, so never flag a missing `const`; add a `const` check if yours does
not). It is also not about how much a widget costs to draw (`saveLayer`, opacity,
clipping, image decoding), which belongs to `render-perf`.

> **Other state managers.** The checks are written for **Riverpod** (`ref.watch` and
> `.select`). The idea maps straight onto any reactive state manager: for `provider`
> read `context.watch` and `context.select`; for `bloc` or `setState`, "a wide part
> redrawn by a frequent trigger" is the same idea. Adapt the patterns to your stack.

## Scope

- Include: `lib/**/*.dart` (focus on `*_screen.dart` and `*_widget.dart`).
- Skip: generated files, `test/`.
- Note any file the project marks do-not-edit or locked as a Blocker.

## Severity legend

| Severity | Meaning |
|---|---|
| **HIGH** | A large part redraws every frame, or on every stream update |
| **MEDIUM** | A wide part redraws often, where separating it out is easy |
| **LOW** | Reads more than it needs to, with little real-world effect |
| **OK** | A rare trigger, or already separated out: listed in an appendix only |

## Allowed (OK - appendix, never a finding)

- **Missing `const`** - your analyzer handles it.
- **One-shot cache providers** that emit about once (loading, then data) and then
  return early: watching them in `build()` is fine.
- **A whole screen redrawing on a rare trigger** (permissions, sign-in, a Firestore
  document that changes only when the user acts): fine. Only GPS, location, gesture,
  animation, or stream-update triggers are frequent.
- **A text field echoing keystrokes through its own `TextEditingController`**: the
  echo is fine. Only flag the *surrounding part* redrawing, and only if it is wide.

(Note: `RepaintBoundary` is a *drawing* tweak. It separates repainting, not
rebuilding, so it does not help here. It belongs to `render-perf`.)

---

## How to run

### Step 1 - Before you start

1. **(Optional) Record your starting counts** (`AUTHORING.md`, Improving an audit
   over time). Note the current count for each pattern and watch for a change over
   time, not an absolute number. Skip it on a first run. (These counts are large in
   any real app, for example thousands of `ref.watch` uses, so a change over time is
   the signal, not the raw total.)
2. **Check past decisions** (`AUTHORING.md`, Making an audit trustworthy):
   ```bash
   gh issue list --state closed --search "rebuild OR select OR optimisation in:title,body" --limit 15
   git log --oneline -15 -- lib
   ```

### Step 2 - Run the searches

A search result is a possible case. Follow the build path and check how often the
provider sends a new value before you record it (see `AUTHORING.md`, Making an audit
trustworthy).

#### R1 - A streaming provider watched in a large build() (HIGH/MEDIUM)
```bash
rg -n 'ref\.watch\(' lib -g '*.dart' -g '!*.g.dart'
rg -l '\.snapshots\(\)|Stream<' lib -g '*.dart' -g '!*.g.dart'   # which providers are really streams
```
Record a hit only when the watched provider is a **Firestore `.snapshots()` or a
`Stream`** AND the watch sits in `build()` (or a helper it calls) of a widget that
*also* builds a **large or unchanging** part in the same `build()`. Every update
redraws the whole part. Confirm the provider really is a stream and the part really
is large. Grade it HIGH for an update every frame or every second (or a part with
many items, such as a long list or a map with many markers), otherwise MEDIUM.
**Fix: pull the streaming part into its own small `ConsumerWidget`** so only it
redraws on each update.

#### R2 - A frequent setState driving a small part (MEDIUM)
```bash
rg -n 'onPointer|onScroll|onMapEvent|addListener|AnimationController' lib -g '*.dart' -g '!*.g.dart'
rg -n 'setState\(' lib -g '*.dart' -g '!*.g.dart'
```
Record a hit only when a `setState` runs from a **frequent callback** (gesture,
scroll, animation, or map-move) and changes a field used only by a **small** part
(an icon, a floating button, a badge). **Fix: use a `ValueNotifier` and a
`ValueListenableBuilder` around just that part**, so the frequent updates no longer
redraw the parent. Ignore a one-off or rare `setState` (such as a toggle).

#### R3 - MediaQuery.of reading too much (LOW)
```bash
rg -n 'MediaQuery\.of\(context\)' lib -g '*.dart' -g '!*.g.dart'
```
Record a hit only when **one part** is read (`.size`, `.devicePixelRatio`, and so
on) but `MediaQuery.of` listens to **all** of it, so opening the keyboard redraws the
screen. Fix: `MediaQuery.sizeOf`, `.devicePixelRatioOf`, or `.viewInsetsOf`. LOW
(often not worth it if the widget must react to the keyboard anyway).

#### R4 - Watching a whole object when one field is used (.select) (LOW)
```bash
rg -n 'ref\.watch\(\w+Provider(\(|\))' lib -g '*.dart' -g '!*.g.dart'
```
(This pattern keys on the `Provider` ending, so it misses a provider held in a local
or a family such as `itemProvider(1)`; widen from `ref\.watch\(` and filter by type
if your names differ.)
Record a hit only when a **wide object or settings stream** is watched whole but only
**one field** drives the build (for example one colour from a settings stream). Fix:
`ref.watch(prov.select((s) => s.field))`. LOW. Skip it if several fields are used, or
the object is already small. **Do not suggest `.select` on a `List`**: when the whole
list is the value, the fix is to pull that part out (R1), not `.select`.

### Step 3 - Check each result

Re-read each `file:line` and **follow the build path**: R1 - trace the provider to a
`.snapshots()` or repository `Stream` and confirm the same `build()` makes a large or
unchanging part; R2 - confirm the callback runs every frame or every event and the
field feeds only a small part; R3/R4 - confirm only the one part or field is used.

### Step 4 - Report

```markdown
## Rebuild-Scope Audit

### Summary
| Category | Count | Starting count (your repo) |
|---|---|---|
| R1 Stream watch in large build() | (HIGH / MED) | |
| R2 Frequent setState feeding a small part | | |
| R3 MediaQuery.of reading too much | | |
| R4 Whole-object watch, one field used (.select) | | |

### R1..R4 - findings
(one table per check: `file:line` - detail - severity - fix, or "None")

### Prior decisions (not re-raised)
| ref | Item | Why out of scope |

### Appendix - OK
- missing const - analyzer handles it
- one-shot cache providers (emit about once)
- rare whole-screen redraws (sign-in, permission, user-action documents)

### Blockers
<locked/do-not-edit files; "(none)" if none>
```

After the report, ask: **"Which finding do you want to fix first, or stop at
planning?"** Pulling a part out does not change behaviour, but it touches parts that
redraw often, so test on a device (profile mode) after any R1 or R2 fix.

---

## Calibrating for your codebase

This audit needs *tracing*, not counting: a 2,000-line widget can be perfectly
separated, and a 50-line one can redraw the whole screen on a gesture. Always weigh
how often a part redraws against how much each redraw costs, and never flag on size
alone.

Known sources of false matches: one-shot caches look like frequent watches (confirm
the provider really keeps sending values); `.select` on a whole `List` does not help
(pull it out instead). Add a new pattern only after it holds on two or more widgets
(`AUTHORING.md`, Improving an audit over time).

> **Add a check of your own.** If your app sends all map, tile, or chart screens (or
> any shared, measured resource) through a single factory, add a check that flags
> screens building the raw widget directly instead of going through it. See
> `AUTHORING.md`, Improving an audit over time, for the template.

Works with `render-perf` (drawing cost) and `isolate-offload` (work on the screen's
thread). The three do not overlap.
