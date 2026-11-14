---
description: "GoRouter configuration and usage problems: a crash on a missing path parameter, hardcoded route strings, a watched router provider, tab switches that stack screens, missing page keys, and navigator keys without labels. Searches the code and only reports."
---
# Audit: Routing

This audit checks how your app configures and uses GoRouter. It looks for the
mistakes that break navigation (a crash on a missing path parameter, tabs that
stack screens on top of each other) and the quieter ones that cause stale pages
and confusing back-button behaviour. It reports what it finds and does not
change any code.

It assumes GoRouter. If you expose the router through a Riverpod provider, the
provider checks apply too; skip them if you do not.

## Scope

- Route definitions: the folder that holds them. The commands below call it
  `$ROUTES`; set it first, for example `ROUTES=lib/routing`.
- Route usage: `lib/**/*.dart`. Skip generated files (`*.g.dart`,
  `*.freezed.dart`).
- Note any locked or do-not-edit file as a Blocker.

## Severity legend

| Severity | Meaning |
|---|---|
| **HIGH** | Breaks navigation: a crash on a null parameter, a watched router, tabs that stack |
| **MEDIUM** | Works today but fragile: missing keys, missing fallbacks, drift from your own helper |
| **LOW** | Diagnostics only: a missing `debugLabel`, mixed transitions |
| **OK** | Compliant; counted, never reported as a problem |

---

## How to run

### Step 1 - Before you start

1. Note any locked or do-not-edit file as a **Blocker**.
2. **Check past decisions** (AUTHORING.md, Making an audit trustworthy):
   ```bash
   gh issue list --state closed --search "routing OR GoRouter OR deep link OR navigation in:title,body" --limit 15   # GitHub only
   git log --oneline -15 -- $ROUTES
   ```
   Hold won't-fix and by-design items as a "past decisions" list; do not
   re-raise them without new evidence.

### Step 2 - Run the searches

A result is a possible case. Read around it before recording anything.

#### HIGH

**H1 - Force unwrap on a path parameter.**
```bash
rg -n "pathParameters\[.*\]!" lib -g '*.dart' -g '!*.g.dart'
```
A missing parameter crashes the route. Fix: read it null-safely and show a
not-found page when it is absent. If your app keeps one small helper for this,
H2 checks everyone uses it.

**H2 - Direct `pathParameters` access outside your one helper.**
```bash
rg -n "state\.pathParameters\[" lib -g '*.dart' -g '!*.g.dart'
```
Only meaningful if your app has a single helper that reads a required
parameter and handles null. If it does, every hit outside that helper's own
file is drift. If it does not, treat each hit as an H1 candidate instead.

**H3 - Hardcoded route strings.**
```bash
rg -n "(router|context)\.(push|go)\(['\"]/[a-z]" lib -g '*.dart' -g '!*.g.dart'
```
Fix: route-name constants, one per route, used by both the definition and the
call sites. Skip doc-comment examples.

**H4 - A tab switch that stacks screens.**
```bash
rg -n "\.push\(" "$SHELL_FILES" -g '*.dart'   # set SHELL_FILES to your shell / bottom-navigation dir
```
Symptom: tapping a tab piles a new copy on the stack, and the back button
cycles through tabs instead of leaving. Inside a tab handler, use
`navigationShell.goBranch(index)` or `context.go(...)`; `.push` is for
stacking a detail screen.

**H5 - Watching the router provider.**
```bash
rg -n "ref\.watch\(goRouterProvider\)" lib -g '*.dart' -g '!*.g.dart'
```
(Adjust the provider name to yours.) Watching the router rebuilds the watcher
on every navigation. Zero hits is the expected state; this is a regression
tripwire, and the literal call cannot go stale. Fix:
`final router = ref.read(goRouterProvider);` and reuse the local.

**H6 - Repeated chained router reads in one file.**
```bash
rg -c "ref\.read\(goRouterProvider\)\." lib -g '*.dart' -g '!*.g.dart' | awk -F: '$2>=3'
```
A cached `final router = ref.read(goRouterProvider);` declaration does not
count; the problem is three or more chained reads. Fix: cache once at the top
of the method.

#### MEDIUM

**M1 - A route without a `name:`.**
```bash
rg -nU "GoRoute\([^)]*?path:" $ROUTES -g '*.dart'
```
Read each block for a `name:` argument. Named routes keep call sites off
hardcoded strings (H3's fix depends on this).

**M2 - A full-screen or modal route missing `parentNavigatorKey`.**
```bash
rg -n "fullscreenDialog: true" $ROUTES -g '*.dart'
```
Read the enclosing `GoRoute` for `parentNavigatorKey:`. Symptom: a paywall,
viewer, or onboarding screen renders inside the tab shell with the tab bar
still visible. Fix: `parentNavigatorKey: rootNavigatorKey`.

**M3 - `state.extra` used without an ID fallback.**
```bash
rg -n "state\.extra!? as " $ROUTES -g '*.dart'
```
Read for an `if (extra == null)` refetch branch. `extra` is null on a deep
link or cold start; carry the ID in the path and refetch when `extra` is
missing.

**M4 - `CustomTransitionPage` missing `state.pageKey`.**
```bash
rg -n -A8 "CustomTransitionPage(<[^>]*>)?\(" $ROUTES -g '*.dart' | rg -v "key: state\.pageKey"
```
Without the key, stale pages can stay in the navigator across route changes.

#### Keys

Keys give navigators identity and pages de-duplication. Constructor arguments
sit on later lines, so read each block from `(` to its matching `)`, never the
first line alone. These two recipes use look-ahead patterns and need `rg -P`
(PCRE2); without `-P` they are a hard error, not a silent miss.

**K1 - A page constructor with no `key: state.pageKey`.**
```bash
rg -nU -P '(?:MaterialPage|CupertinoPage|NoTransitionPage|CustomTransitionPage)(?:<[^>]*>)?\((?:(?!state\.pageKey)[^;])*?\)\s*[,;]' $ROUTES -g '*.dart'
```

**K2 - Navigator keys: top-level, unique, labelled.**
```bash
rg -n 'GlobalKey<NavigatorState>\(' lib -g '*.dart' -g '!*.g.dart'
rg -nU -P 'GlobalKey<NavigatorState>\((?:(?!debugLabel:)[^;])*?\)' lib -g '*.dart' -g '!*.g.dart'
```
Each key must be a top-level or static declaration (declared inside `build`,
it resets every rebuild), each must be a distinct identifier (reuse is a
runtime assertion), and each should carry a `debugLabel:` (LOW) so error
messages and DevTools name it.

**K3 - An imperative push inside a shell that should escape it.**
```bash
rg -n 'Navigator\.of\(context\)\.push' lib -g '*.dart' -g '!*.g.dart'
```
A full-screen dialog or image viewer pushed from inside a tab shell needs
`Navigator.of(context, rootNavigator: true)`, or the shell stays visible
behind it. This is the imperative twin of M2.

### Step 3 - Structural checks (read, not search)

- **Registration:** every route your route files define is reachable from the
  router's assembly (top-level list, a shell branch, or nested `routes`).
- **Ordering:** specific paths come before parameterised ones (`/item/create`
  before `/item/:id`).
- **Shell shape:** `StatefulShellRoute.indexedStack` for tabs; each branch has
  its own navigator key; re-tapping the active tab resets it via
  `goBranch(index, initialLocation: index == navigationShell.currentIndex)`.
- **Async navigation:** after an `await`, the code checks `context.mounted`
  (or cached the router before the gap) before navigating.

### Step 4 - Report

```markdown
## Routing Audit

### Summary
HIGH <n> | MEDIUM <n> | LOW <n>

### Findings
| Severity | file:line | Pattern | Fix |
(or "None")

### Keys coverage
| Check | file:line | Note |
(pages missing state.pageKey; keys without debugLabel; pushes missing rootNavigator)

### Unregistered or misordered routes
| Route | Defined in | Problem |
(or "None")

### Past decisions (not re-raised)
- [item]: [reference]

### Blockers
<locked files; "(none)">
```

After the report, ask which one to fix first, or stop at planning. Do not
change any code without approval.

## Optional model-assisted pass

The judgement-call checks (M1 to M4, K1 to K3) can be classified by a model
when the candidate list is long: give it each code block and the rule, and
require a verdict plus a verbatim quote of the lines it judged. Then re-read
every quoted block yourself and drop anything that does not hold; a finding
whose quote is not really in the file is invented. Report how many were
dropped - a high drop rate means the blocks you sent were incomplete.

## Calibrating for your codebase

- Set `$ROUTES` and the shell-file paths before running; the defaults here are
  placeholders.
- H5 and H6 assume a router-in-a-provider setup. Skip them otherwise.
- Record a starting count for the H and K searches on your first run
  (AUTHORING.md, record a starting count), and compare against it later. If a
  count halves or doubles between runs, re-read the pattern before trusting
  it: route files move, and a search that matches nothing looks the same as a
  clean result.
