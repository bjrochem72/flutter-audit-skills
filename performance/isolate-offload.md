---
description: "Heavy work that runs on Flutter's main thread and should move to a background worker: a large parse or serialize (GPX, big JSON/XML), image byte decode/resize/compress, and heavy crypto or compression run directly instead of through Isolate.run() or compute(). Whole-repo search, report-only."
---
# Audit: Isolate Offload

This audit looks in `lib/` for **heavy work running on the main thread**. In Flutter
the main thread draws the screen, and it is called the UI isolate. An isolate is a
separate worker. Following the [Dart concurrency guide](https://dart.dev/language/concurrency)
and the [Flutter performance guide](https://docs.flutter.dev/perf/best-practices),
work that can take longer than the time to draw one frame (about 16 ms) should move
to a **background isolate**: a large parse or serialize, image byte work, encryption
or hashing, or compression. If you can show the work takes too long, move it with
**`Isolate.run()`** (Dart 2.19 or later, the usual choice) or Flutter's **`compute()`**
helper. Heavy work on the UI isolate drops frames and freezes scrolling and
movement. **The audit only reports; you make any change yourself.**

**What this audit is NOT:**
- **Not an `async`/`await` audit.** `await` on input/output (network, disk,
  database) already lets the app carry on, so it is not a finding. This is about
  heavy work that runs straight through and uses the processor.
- **Not a "move everything to a worker" search.** Starting a background isolate has a
  real cost (starting it up, and copying the data across). Small, limited work stays
  on the main thread. Flag only genuinely heavy work on **large or user-supplied**
  data.
- Overlap: `render-perf` (drawing) and `rebuild-scope` (how often a part redraws)
  cover the drawing side; this one covers heavy work on the UI thread.

## Scope

- Include: `lib/**/*.dart`. Skip generated files and `test/`.
- Note any file the project marks do-not-edit or locked as a **Blocker**.

## Severity legend

| Severity | Meaning |
|---|---|
| **HIGH** | Heavy work on large user-supplied data while the user waits (parsing an imported file, decoding a full-size image) |
| **MEDIUM** | Heavy work on data that is usually small but can grow |
| **LOW** | Borderline; measure before you change it |
| **OK** | Small or limited work, or already moved to a worker: appendix only |

## Allowed (OK - appendix, never a finding)

- **Awaited input/output** (`await` on network, disk, database, `readAsBytes`, and
  `AssetBundle.loadString`, which also moves large text decoding to a worker):
  already does not block.
- **Already moved to a worker** through `Isolate.run()` or `compute()`: the state
  you want.
- **Framework and `dart:ui` image decoders** (`Image` and `FadeInImage` widgets,
  `decodeImageFromList`, `instantiateImageCodec`): these decode off the UI thread
  already. The `image`-package path that runs straight through is the real case to
  look for.
- **Small, limited work** such as turning a database document into an object,
  sorting one screen of items, or hashing a short id. Moving these to a worker would
  cost more than it saves.
- **Words that only look like compression**, for example an `archive` or `archived`
  field, which is not `gzip`. Match exact API names, never a plain `archive`.

---

## How to run

### Step 1 - Before you start

1. **(Optional) Record your starting counts** (`AUTHORING.md`, Improving an audit
   over time): counts for each pattern, to watch for a change over time. Skip it on
   a first run.
2. **Check past decisions** (`AUTHORING.md`, Making an audit trustworthy):
   ```bash
   gh issue list --state closed --search "isolate OR compute OR jank OR parse in:title,body" --limit 15
   git log --oneline -15 -- lib
   ```
   Note where you already move work to a worker (`rg -n 'Isolate\.run\(|compute\(' lib`).
   Those are the example to copy, not findings.

### Step 2 - Run the searches

A search result is a possible case. Open the actual code and confirm the work is
(a) using the processor, (b) running straight through (no `await` inside it), and
(c) on large or user-supplied data, before you record it.

#### I1 - Heavy parse or serialize on the main thread (HIGH/MEDIUM)
```bash
rg -n 'jsonDecode\(|XmlDocument\.parse\(|utf8\.decode\(' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
Record a hit only when a **straight-through** parse or serialize of **large or
user-supplied** data runs on the UI thread (not inside `Isolate.run()` or
`compute()`). A common HIGH: reading an imported file's bytes and then parsing the
whole thing (XML, GPX, CSV) while the user waits, which drops a frame on import. Fix:
move the parse into `Isolate.run(() => parse(bytes))`. Note that some values (id
makers, callbacks) cannot cross to a worker: parse to plain data in the worker and
add them back on return. Ignore `jsonDecode` of small config or API data.

Also under I1: **heavy in-memory work** such as `.sort()`, nested
`.where(...contains...)`, or costly per-item `.map()` (distance, date or timezone
parsing), but **only over a genuinely large list** (thousands of items while the
user waits). Sorting one screen of items takes under a millisecond, so it is fine.

#### I2 - Image byte work on the main thread (HIGH)
```bash
rg -n 'img\.decode|decodeImage\(|\.resize\(|encodeJpg\(|encodePng\(' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
This looks for the **straight-through** `image`-package path (`img.decode` or a plain
`decodeImage`, `.resize`, `encodeJpg`, `encodePng`), which decodes, resizes, or
re-encodes full-size bytes on the thread that calls it. Record it when it runs on the
UI thread. Fix: `compute(processImage, bytes)`. **Not findings:** the framework
`Image` and `FadeInImage` widgets, and `dart:ui`'s `decodeImageFromList` and
`instantiateImageCodec`, which decode off the UI thread already. Tip: to read only
the *size* of an image, a header-only read (`findDecoderForData().startDecode()`)
beats decoding every pixel.

#### I3 - Heavy encryption, hashing, or compression on the main thread (MEDIUM)
```bash
rg -n 'sha256|Hmac\(|md5\.|encrypt\(|GZipCodec|gzip\.|GZipEncoder|GZipDecoder|\.inflate\(|\.deflate\(' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
Record a hit only when hashing, encrypting, or compressing a **large amount of data**
(a file, an image, a big string) straight through. Hashing a short id or handle is
small, so it is fine. Do **not** match a plain `archive` (an everyday word, not
compression).

#### I4 - Blocking file input/output that runs straight through (LOW)
```bash
rg -n 'readAsBytesSync|readAsStringSync|writeAsBytesSync|writeAsStringSync|\.listSync\(' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
File reads and writes that run straight through block the thread that calls them.
(I4 is the one check here about blocking **input/output**, not processor work: the
fix is async input/output, not a move to a worker.) Record only a straight-through
**read or write of a large file**. A cheap `existsSync()` or `statSync()` check is
tiny, so it is fine. Prefer async `readAsBytes()`.

### Step 3 - Check each result (drop anything that does not hold)

Re-read each `file:line`: confirm the work **runs straight through** and either
**uses the processor** (I1-I3) or is **blocking input/output** (I4). Open the method
it calls: a `List<...> foo(...)` with no `await` inside runs straight through; a
`Future` that only `await`s input/output is not a finding. Confirm the data is
**large or user-supplied**, and that it is **not** already inside `Isolate.run()` or
`compute()`. Every finding you keep names a `file:line` you read and a one-line
quote.

### Step 4 - Report

```markdown
## Isolate-Offload Audit

### Summary
| Check | Findings | Starting count (your repo) |
|---|---|---|
| I1 Heavy parse/serialize + in-memory work | | |
| I2 Image bytes on main thread | | |
| I3 Heavy crypto/compression | | |
| I4 Blocking file input/output | | |

### I1..I4 - findings
(one table per check: `file:line` - operation - data size/source - severity - fix,
or "None")

### Prior decisions (not re-raised)
| ref | Item | Why out of scope |

### Appendix - OK
- awaited input/output - already does not block
- work already moved to a worker via Isolate.run()/compute() - the example to copy
- small, limited work (document to object, one-screen sorts, short-id hashes)

### Blockers
<locked/do-not-edit files; "(none)" if none>
```

After the report, ask: **"Which finding do you want to fix first, or stop at
planning?"** Moving work to a worker adds the cost of copying the data across, so
test on a device (profile mode) after any I1 or I2 fix, and confirm small inputs did
not get slower.

---

## Calibrating for your codebase

Known sources of false matches (built into the rules):
- **`archive` is an everyday word**, not compression. A plain match is almost all
  noise. Use exact API names.
- **`await` is not the same as blocking.** Only work that runs straight through and
  uses the processor counts. Open the method it calls.
- **Moving to a worker has a cost.** Small, limited work (document to object,
  one-screen sort, short-id hash) costs more to move than to run in place. Flag only
  large or user-supplied data.
- **A small parse at start-up of a small bundled file** (tens of KB, done off the
  first-frame path) is usually fine: the cost of moving it is more than the
  under-a-millisecond parse.

Add a new heavy-work pattern only after it holds on two or more places
(`AUTHORING.md`, Improving an audit over time). Works with `render-perf` and
`rebuild-scope`. The three cover different parts of performance (processor work,
drawing, and how often a part redraws) and do not overlap.
