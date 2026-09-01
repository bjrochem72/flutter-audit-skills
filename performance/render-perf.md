---
description: "Drawing cost for Flutter: saveLayer effects (ShaderMask/ColorFilter/BackdropFilter) over large trees, opacity or clipping during animation, long lists built all at once, full-size image decodes with no cache size, operator== on Widget subclasses (which makes diffing slow), an AnimatedBuilder that rebuilds a heavy subtree, and an effect applied to a whole group instead of the one child that needs it. Whole-repo search, report-only."
---
# Audit: Render Performance

This audit looks in `lib/` at how much your widgets **cost to draw**, following the
[Flutter performance guide](https://docs.flutter.dev/perf/best-practices). These are
costs that do not come from redrawing too often: drawing to an off-screen buffer
(`saveLayer`), opacity or clipping during animation, long lists built all at once,
full-size image decodes, `operator ==` on widgets, and animation code that rebuilds
more than it needs to. **This audit reports what it finds; it does not change code.**

**What this audit is NOT:**
- **Not a `const` check.** If your analyzer turns on `prefer_const_*`
  (`very_good_analysis`, `flutter_lints`, or similar), a missing `const` cannot slip
  through, so never flag it. If yours does not, add a `const` check separately.
- **Not about how often a widget redraws.** A streaming provider in `build()`, a
  frequent `setState`, `.select` cases, and `MediaQuery.of` reading too much belong
  to `rebuild-scope`. Send those there; do not report them twice.

## Scope

- Include: `lib/**/*.dart` (focus on `*_screen.dart`, `*_widget.dart`, and files
  that draw, place markers, or animate). Change `lib/` if your source lives
  elsewhere.
- Skip: generated files (`*.g.dart`, `*.freezed.dart`), `test/`.
- Note any file the project marks do-not-edit or locked as a **Blocker**.

## Severity legend

| Severity | Meaning |
|---|---|
| **HIGH** | A per-frame cost on a large or animated part, or `operator ==` on a widget |
| **MEDIUM** | An off-screen buffer, a long list built all at once, a full-size image decode with no cache size, or clipping during animation, where a cheaper form exists |
| **LOW** | A one-off, unchanging effect with little real-world impact |
| **OK** | Fine as it is: appendix only, never a finding |

## Allowed (OK - appendix, never a finding)

- **Missing `const`**: your analyzer handles it (see above).
- **`AnimatedOpacity`, `FadeInImage`, `SliverOpacity`**: the recommended forms. Only
  the plain `Opacity` widget is a possible case.
- **`ClipRRect` around a real child that must be clipped** (a network image, video,
  map, or any child). Only flag a clip that (a) wraps a **simple rounded rectangle**
  that a `borderRadius` on the container's `BoxDecoration` would do, or (b) sits
  **inside an animation**.
- **`ListView(children: [...])` with a small fixed number of items**: building lazily
  only helps when the list is long or its length is set at run time.
- **`RepaintBoundary` already present** around the costly part.

---

## How to run

### Step 1 - Before you start

1. **(Optional) Record (or refresh) your starting counts** (see `AUTHORING.md`,
   Improving an audit over time) so the counts below are your project's, not another
   codebase's. Skip it on a first run; record the current count for each pattern and
   compare against it on later runs.
2. **Check past decisions** (`AUTHORING.md`, Making an audit trustworthy) about
   drawing and performance, so you do not raise a settled item:
   ```bash
   gh issue list --state closed --search "opacity OR saveLayer OR clip OR ListView OR render perf in:title,body" --limit 15
   git log --oneline -15 -- lib
   ```

### Step 2 - Run the searches

A search result is a possible case: open the widget and follow what the effect wraps
before you record it (see `AUTHORING.md`, Making an audit trustworthy).

#### P1 - `Opacity` widget, especially animated (LOW to MEDIUM)
```bash
rg -n -P '(?<![A-Za-z])Opacity\(' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
Record a hit only when the `opacity:` value is **driven by an `Animation` or
`AnimationController`** (or rebuilt every frame) AND the child is a **large or
non-const part**. Constant opacity on an unchanging child is LOW or OK. Fix:
`AnimatedOpacity` (set targets), `FadeTransition` (continuous), `FadeInImage`
(images), or a see-through colour. Do not flag a `const` child inside an
`AnimatedBuilder` driven by a continuous wave (already fine).

#### P2 - `saveLayer` effects over a large or animated part (MEDIUM)
```bash
rg -n 'ShaderMask\(|ColorFiltered\(|ColorFilter\.|BackdropFilter\(' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
Each of these draws to an **off-screen buffer** (a `saveLayer` and a switch of the
drawing target). Record a hit only when one wraps a **large or every-frame-animated**
part. A one-off `ColorFilter` on a small unchanging icon is OK. Fix: work out the
result once and reuse it, or wrap a smaller part. Confirm with DevTools
`checkerboardOffscreenLayers`.

#### P3 - Costly or animated clipping (LOW to MEDIUM)
```bash
rg -n 'antiAliasWithSaveLayer' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'   # always a finding if >0
rg -n 'ClipRRect\(|ClipPath\(|ClipOval\(' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
Record, as MEDIUM, when **`Clip.antiAliasWithSaveLayer`** appears at all (it forces a
`saveLayer`; prefer the default `Clip.antiAlias`), or when a clip sits **inside an
animation** and runs again every frame. Record as LOW a `ClipRRect` or `ClipOval`
around a **simple rounded rectangle** that a `borderRadius` would round instead. Do
not flag a clip around a real image, map, or any child.

#### P4 - Long lists built all at once (LOW to MEDIUM)
```bash
rg -n 'ListView\(|GridView\(' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
rg -n 'children: \[?\s*\.\.\.|\.map\(.*\)\.toList\(\)' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
Record a hit only when a `ListView(children:)` or `GridView(children:)` (or a
`SingleChildScrollView` wrapping a `Column`) is fed from a **run-time list that can be
long** (`items.map(...).toList()`), because all the child *widgets* are built up
front (the list items are still built lazily, but the widget objects and the
`.map().toList()` are not). Fix: `.builder` (or a `CustomScrollView` with
`SliverList.builder`). Notes: a `ListView(children:)` is already lazy at the item
level, so this is **LOW** for short lists, and MEDIUM only when the list is genuinely
long; a `shrinkWrap: true` that a content-sized sheet needs cannot be made lazy
without a fixed height, so mark it LOW and note the trade-off.

#### P5 - A full-size image decoded into a small box (MEDIUM)
```bash
rg -n 'Image\.network\(|Image\.asset\(|Image\.file\(|Image\.memory\(|NetworkImage\(|AssetImage\(|DecorationImage\(' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
Flutter decodes an image at its **full size** whatever the display size, unless you
tell it otherwise. A 4000x3000 photo shown in a 96x96 avatar wastes decode time and
holds the whole bitmap in the image cache. Record a hit when a large or remote image
is shown in a **much smaller** box **without** `cacheWidth:` / `cacheHeight:` (on
`Image.*`) or a `ResizeImage` wrapper (on `*ImageProvider`). Fix: add `cacheWidth`
and `cacheHeight` sized to the display (times the device pixel ratio), or
`ResizeImage(NetworkImage(url), width: ...)`. Do not flag small icons or thumbnails
whose image is already the display size, or providers already wrapped.

#### P6 - `operator ==` on a Widget subclass (HIGH)
```bash
rg -l 'extends (StatelessWidget|StatefulWidget|ConsumerWidget|ConsumerStatefulWidget)' lib -g '*.dart' |
  while IFS= read -r file; do
    rg -n 'operator ==' "$file"
  done
```
Adding `==` to a widget that has children makes Flutter compare the whole tree much
more slowly (per the Flutter `Widget.operator ==` docs). Record **any** hit on a
class that really `extends *Widget` (not a value object kept in the same file:
confirm in Step 3). This count should be **0**; a count above 0 is worth a look
(usually a value object saved in the wrong place as a widget). Fix: remove the
override, and rely on widget caching and `const`.

#### P7 - `AnimatedBuilder` rebuilding a heavy part (MEDIUM)
```bash
rg -n 'AnimatedBuilder\(|ListenableBuilder\(' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
Record a hit when the `builder:` returns a **large part that does not depend on the
animation** and does **not** use the `child:` argument, so it rebuilds every frame.
Fix: build the unchanging part once, pass it as `child:`, and use it in the builder.

#### P8 - Building a String with `+=` in a loop (LOW)
```bash
rg -n -P '\w+\s*\+=' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
This finds **all** `+=` (most are numbers, which is fine). Record a hit only when a
**String** is built with `+=` **inside a loop** (each step makes a new `String`).
Open the line and confirm both the String and a surrounding loop. Fix: `StringBuffer`
and `.toString()`. Number `+=` and one-off joins are fine. (A single pattern that
picks out only Strings breaks across shells, so search wide and read the line.)

#### P9 - An effect applied to a whole GROUP instead of the one child (LOW to MEDIUM)
```bash
rg -n -U -P '(Opacity|ColorFiltered|ClipRRect|ClipPath|ClipOval)\(\s*(\n[^)]*){0,6}child:\s*(const\s+)?(Column|Stack|Row|Wrap|ListView)\(' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
Per the [UI performance guide](https://docs.flutter.dev/perf/ui-performance): apply
opacity, a filter, a clip, or a shadow at the **lowest level**, not over a `Column`,
`Stack`, or `Row` group, because an effect on the whole group forces one `saveLayer`
over the whole part. Record a hit only when the group has **more than one child** and
the effect could move to the one child that needs it (or be written as a
`borderRadius` or a see-through colour). Do not flag an effect over a single child
that really needs it. (The pattern is rough: it allows an optional `const` and up to
6 lines before `child:`, but an earlier argument that contains a `)` - for example
`BorderRadius.circular(8)` - still breaks its `[^)]*` window, so also check
group-level effects by hand.)

### Step 3 - Check each result (drop anything that does not hold)

Re-read each `file:line` and confirm the exact condition (opacity is animated; a
filter wraps a large or animated part; it is `antiAliasWithSaveLayer`, or in an
animation, or replaceable by `borderRadius`; the list items come from a long run-time
list; the image is large and the box small with no cache size; the class really
`extends *Widget`; the `AnimatedBuilder` part does not depend on the animation and
ignores `child:`; the String is built in a loop; the effect wraps a group with more
than one child). Every finding you keep names a `file:line` you read and a one-line
quote.

### Step 4 - Report

```markdown
## Render-Performance Audit

### Summary
| Check | Count | Starting count (your repo) | Change? |
|---|---|---|---|
| P1 Opacity (animated) | | | |
| P2 saveLayer over large tree | | | |
| P3 antiAlias/animated/simple clip | | | |
| P4 long list built all at once | | | |
| P5 image decode with no cache size | | | |
| P6 operator== on widget | | 0 (must stay 0) | |
| P7 AnimatedBuilder heavy builder | | | |
| P8 String concat in loop | | | |
| P9 effect on group vs one child | | | |

### P1..P9 - findings
(one table per check: `file:line`, condition, severity, and fix, or "None")

### Prior decisions (not re-raised)
| ref | Item | Why out of scope |

### Appendix - OK
- missing const - analyzer handles it
- AnimatedOpacity / FadeInImage / SliverOpacity - recommended forms
- ClipRRect around images/maps/any child - fine
- how-often-it-redraws issues - belong to `rebuild-scope`

### Blockers
<locked/do-not-edit files that would need editing; "(none)" if none>
```

After the report, ask: **"Which finding do you want to fix first, or stop at
planning?"** Drawing and animation changes do not change behaviour, but they touch
parts that draw often, so test on a device (profile mode) after any P1, P2, P5, or P7
fix.

### Example - a filled-in finding

A run over a profile screen that shows remote avatars might produce:

```markdown
## Render-Performance Audit

### Summary
| Check | Count | Starting count (your repo) | Change? |
|---|---|---|---|
| P5 image decode with no cache size | 1 | 0 | +1 |
| (all other checks) | 0 | - | - |

### P5 - image decode with no cache size
| file:line | condition | severity | fix |
|---|---|---|---|
| `profile_header.dart:88` | `Image.network(user.photoUrl)` shown in a 48x48 `CircleAvatar` with no `cacheWidth`/`cacheHeight`: a roughly 1024x1024 image decodes at full size and is held in the image cache at that size | MEDIUM | `Image.network(user.photoUrl, cacheWidth: 96, cacheHeight: 96)` (48 times the device pixel ratio) |

### Blockers
(none)
```

Notice the shape: one exact `file:line` you read, the *condition that made it a
finding* (not just "an image"), a severity, and a clear fix. Then a question, and
**no change** until you approve it.

---

## Calibrating for your codebase

Based on the Flutter performance guide, and set up to sit alongside `rebuild-scope`
(how often a part redraws) and `isolate-offload` (heavy work on the UI thread). The
three cover different parts of performance and do not overlap.

Known sources of false matches (already built into the rules):
- **`ClipRRect` is usually fine**: only the `borderRadius`-replaceable rectangle or
  the in-animation clip is a finding.
- **Most `+=` is numbers**, not Strings: confirm the type and a surrounding loop.
- **`ListView(children:)` is fine for short fixed lists**: only a long run-time
  `.map().toList()` needs `.builder`.
- **P6 count is 0 on purpose**: treat any hit as worth a look.
- **P5**: skip icons and thumbnails already sized to their image, and providers
  already wrapped in `ResizeImage`.

Add a new pattern only after it holds on two or more places with no false match
(`AUTHORING.md`, Improving an audit over time).
