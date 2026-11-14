---
description: "Code-quality problems in one feature that an architecture audit cannot see: flow-sensitive bugs, handling that differs between similar paths, silent failures, dead defensive code, validation gaps, and parameters plumbed through layers to nowhere. Static searches plus an optional model-assisted pass. Takes one feature path. Report-only."
---
# Audit: Quality

This audit checks one feature for the problems that layer rules cannot catch:
a button tap that silently does nothing, two similar save paths that handle
errors differently, a `try/catch` wrapped around code that cannot throw, a
required parameter threaded through three layers that nothing reads any more.
It reports what it finds and does not change any code.

Run the **feature-architecture** audit first and fix its findings; this audit
then looks at what architecture checks do not see. The two overlap in exactly
two places - the `copyWith` null trap and the keepAlive-watching-autoDispose
check - and feature-architecture owns both: cite its rows, do not re-derive
them.

Run with a feature path, for example `lib/features/orders`. If no path is
given, stop and ask.

## What it catches

Twenty-two checks in seven groups. "Static" is a search plus a read. "Model"
needs the optional model-assisted pass (below) and is otherwise listed as
"needs manual review".

| ID | Concern | Method |
|---|---|---|
| E1 | An enum value in validation logic that branch order makes unreachable | Model |
| E2 | One field validated much more strictly than a similar field | Model |
| E3 | `toString` printing a non-nullable field as the text "null" | Static |
| E4 | `copyWith` that can never clear a nullable field | Cite feature-architecture D8 |
| E5 | Field docs missing or in a mixed style (`///` versus a trailing `//`) | Static |
| E6 | Equality or `hashCode` built on timestamps, with no warning comment | Model |
| V1 | Inline validation that repeats your shared validation helpers | Static |
| V2 | A feature validator re-implementing checks your shared helpers already have | Model |
| V3 | A form field whose `maxLength` disagrees with its validator's constant | Model |
| B1 | A silent early return on a user action - the tap runs, returns, and the user sees nothing | Model |
| B2 | An error path documented as user-visible that can never run | Model |
| B3 | `unawaited(...)` with no error handling in the chain | Static |
| B4 | A save-success listener that navigates without checking the widget is still mounted | Static |
| D1 | A dead `try/catch` around code that cannot throw | Static |
| D2 | A defensive null check on a non-nullable parameter | Model |
| D3 | Re-checking a precondition the caller already enforced | Model |
| D4 | A dead `required` parameter plumbed through several layers to nowhere | Static + read |
| C1 | Error handling that differs between similar methods | Model |
| C2 | Loading-state behaviour that differs between similar mutations | Model |
| C3 | Documentation style that differs between similar members | Model |
| L1 | KeepAlive provider watching an autoDispose dependency | Cite feature-architecture X4 |
| N1 | A nested-if maze (three or more directly nested ifs) hiding the normal path | Static detector + judgement |
| G1 | Legacy Riverpod API anywhere in `lib/` (not just the feature) | Static |

## Severity legend

| Severity | Meaning |
|---|---|
| **HIGH** | A user-visible bug or silent data problem |
| **MEDIUM** | Wrong today only in edge cases, or drift between similar paths |
| **LOW** | Dead code, doc drift |
| **OK** | Checked and fine; never reported as a problem |

---

## How to run

### Step 1 - Before you start

1. Note locked or do-not-edit files in the feature as **Blockers**.
2. **Check past decisions** (AUTHORING.md, Making an audit trustworthy):
   ```bash
   gh issue list --state closed --search "<feature> in:title,body" --limit 30   # GitHub only
   git log --oneline -15 -- "<feature-path>"
   ```
   Read the most relevant closed item in full. Won't-fix and by-design items
   go to a "past decisions" list; a finding that repeats one is dropped and
   listed there instead, unless you have new evidence the decision was wrong.

### Step 2 - Static checks

`F` is the feature path. Every search carries `-g '*.dart' -g '!*.g.dart'`.

**E3 - "null" printed for a non-nullable field.**
```bash
rg -n "'null'|\"null\"" "$F/domain/" -g '*.dart' -g '!*.g.dart' | rg -v ':\s*//'
```
Confirm the hit is inside `toString`, then read the field's declaration.
Record only when the field is non-nullable: it can be empty, never null, so
the output lies.

**E5 - Mixed field doc style.**
```bash
rg -n 'final\s+[\w<>?]+\s+\w+;\s*//\s*\S' "$F/domain/" -g '*.dart' -g '!*.g.dart'
```
A trailing `//` should be `///` so the doc shows on hover.

**V1 - Inline validation beside shared helpers.**
```bash
rg -n '(value|name|description)\.trim\(\)\.isEmpty|\.length > [0-9]+|\.length < [0-9]+' "$F/presentation/" -g '*.dart' -g '!*.g.dart'
```
Only meaningful if your app has shared validation helpers. Record a hit when
the surrounding code is a validation guard and the feature is not calling the
shared helper for the same job.

**B3 - Fire-and-forget without error handling.**
```bash
rg -n 'unawaited\(' "$F" -g '*.dart' -g '!*.g.dart'
```
Read to the closing bracket; record it if the inner chain has no `.catchError`
and no surrounding `try`. Include provider files: long-lived providers often
own fire-and-forget side effects that matter most.

**B4 - Navigation in a listener without a mounted check.**
```bash
rg -n 'Navigator\.of\(context\)\.pop\(\)' "$F/presentation/" -g '*.dart' -g '!*.g.dart'
```
Read fifteen lines around it. Record only a call inside a `ref.listen` or
similar callback with no mounted or `canPop` guard. Ordinary dialog
dismissals in `onPressed` are correct; they are most of the hits.

**D1 - Dead try/catch.**
```bash
rg -Un 'try\s*\{[^}]{0,200}l10n\.' "$F" -g '*.dart' -g '!*.g.dart'
```
Localisation getters do not throw; a `catch` around only them is dead
defensive code. Widen the idea to any wrapped call you can show cannot throw.

**D4 - Dead parameter plumbed through layers.**
```bash
rg -n 'required\s+[\w<>?,\s]+\s+\w+,' "$F/application/" "$F/presentation/" -g '*.dart' -g '!*.g.dart'
```
For each `required` parameter on a public method, read the body; if the name
never appears, it is dead. Skip `const` constructors, `build` overrides, and
`super` calls. When one is dead, follow its call sites down the layers and
record the whole chain, so the fix removes the dead computation everywhere. A
common cause is an analytics or logging consumer that was removed while its
inputs stayed wired through.

**N1 - Nested-if maze.**
Flag an `if (...) {` chain where each inner `if` is the very next code line,
one indent deeper, three or more levels down. Do not flag absolute
indentation; that over-reports enormously. Depth alone is never a finding:
read the whole function and judge whether guard clauses would flatten it.
Necessary nesting is out of scope - a null guard before a dereference, a
post-`await` mounted check, a debug-only block, a parser or builder closure.

**G1 - Legacy Riverpod API (repo-wide on purpose).**
```bash
rg -n 'extends\s+StateNotifier<|\bStateNotifierProvider\b|\bStateProvider\b|\bChangeNotifierProvider\b|riverpod/legacy\.dart' lib -g '*.dart' -g '!*.g.dart'
```
Riverpod 3 moved these to a legacy library; the modern family is `Notifier` /
`AsyncNotifier`. The word boundary keeps names like `appStateProvider` from
matching. This check deliberately scans all of `lib/`, whatever feature you
passed, so legacy code cannot creep into shared folders unseen.

**E4 and L1.** Run them with the feature-architecture audit's rules (D8 and
X4) and report them here marked "shared with feature-architecture - fix once,
both reports update".

### Step 3 - Optional model-assisted pass

The Model checks (E1, E2, E6, V2, V3, B1, B2, D2, D3, C1, C2, C3, and the N1
judgement) need reading comprehension, not pattern matching. Any capable model
works - a local one or a cloud one; be aware that a cloud model means your
code leaves your machine. Without a model, list these checks in the report as
"needs manual review" with the files each one would have covered.

Rules that make model findings trustworthy:

- **Ask for structured findings**: file, line, severity, confidence, a
  one-sentence description, a one-sentence quote of the code as evidence, and
  a one-sentence fix. No evidence quote, no finding: drop it unread.
- **Verify every finding yourself before it reaches the report.** Read the
  cited line. If the quote is not in the file (or nothing close), the model
  invented it: drop it. If the line is wrong but the issue is real nearby,
  correct the line. If the fix is wrong, rewrite it from what you read.
- **Low-confidence findings are not verified**; list them under "needs manual
  review" and make no claim about them.
- **Track the drop rate.** If more than roughly a third of the model's
  findings fail verification, say so in the report: the model is too small,
  the prompt too thin, or the feature unusual. Do not trust the survivors
  more because the others were dropped.

Feed each check the files it concerns: entity files for E1/E2/E6, validator
files for V2, form plus constants files for V3, every file with a tap handler
for B1 (widgets as well as screens), repository stream methods paired with
their consuming error branches for B2, use cases and controllers for the D
and C checks, and the full enclosing function for each N1 hit.

### Step 4 - Report

Cite sites as file plus symbol (`order_entity.dart`, `toString`), not a bare
line number - line numbers drift.

```markdown
## Quality Audit - <feature>

### Static findings
| ID | Site | Severity | Description |
(or "None")

### Model-assisted findings (verified)
| ID | Site | Severity | Confidence | Description | Evidence | Fix |
(or "None" / "static-only run")

### Dropped after verification
| ID | Cited site | Why |

### Needs manual review
| ID | Site | Note |

### Shared with feature-architecture
| ID | Site | Description |

### Past decisions (not re-raised)
- [item]: [reference]

### Run notes
Mode: static-only / model-assisted. Files read: <n>. Findings dropped after
verification: <n> of <n>.
```

After the report, ask which finding to address first, or stop at planning.
Do not change any code without approval.

## Out of scope

Layer-boundary breaks belong to the clean-architecture and
feature-architecture audits; widget redraw cost to a performance audit;
loading and error branch shape to the async-state-ui audit. If a finding fits
one of those, point there instead of double-filing.

## Calibrating for your codebase

- Patterns earn a place here only after they hold on two or more features
  without a false match; keep your own "do not flag" notes as you run it.
- N1 is a regression tripwire: in a codebase disciplined about guard clauses
  it stays silent, and a new depth-three chain is a strong signal.
- Record starting counts for the static searches on your first run and
  compare later runs against them. If a count halves or doubles, re-read the
  pattern before trusting it - a search that stopped matching looks exactly
  like a clean codebase.
