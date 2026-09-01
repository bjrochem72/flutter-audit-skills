---
description: "ref.watch on a provider whose value cannot change while the widget is on screen: flags places where ref.read would do the same job for less. Sorted by how long the widget stays on screen, report-only."
---
# Audit: Provider Reactivity (ref.watch vs ref.read)

This audit flags `ref.watch(<provider>)` calls where `ref.read` would do the same
job and cost less. It looks for a provider whose value **cannot change while the
widget is on screen**. Watching such a provider sets up a subscription that can
never fire. The audit reports these places and does not change any code.

## Why this audit exists

`ref.watch` signs the widget up to a provider, tracks that on every rebuild, and
cleans it up when the widget goes away. `ref.read` just reads the value once and
does none of that. When the value cannot change while the widget is on screen,
`ref.watch` is work that gives nothing back, and `ref.read` does the same job for
less.

The question is **not** "does this value ever change?" It is "can it change *while
this widget is still on screen*?" That depends on **where the value is changed** and
**whether the widget is still there** at that moment.

> **This is a small performance tweak, not a rule for every case.** The usual
> Riverpod advice is "watch in build". The cost of `ref.watch` is small, and
> switching to `ref.read` is easy to get wrong: if the provider later starts to
> change (or you start showing a value that can change), the widget will quietly
> stop updating. Use `ref.read` only where you are sure the value is fixed, and keep
> `watch` whenever you are unsure.

**Worked example.** Say a `localeProvider` changes only when the user picks a
language on a **Settings** screen (and the app controls its own language; a provider
that copies the device language can change at any time and does **not** count as
fixed). A detail page opened from a list, with no link to Settings, can only see a
language change *after* the user closes it and goes to Settings. By then it is gone.
So it should `read` the language. A screen that stays on screen while Settings is
open (a tab or shell screen next to it, or a page with a shortcut to Settings) must
`watch`.

## Scope

- Target: `ref.watch(<provider>)` in your feature and page widgets.
- **First decide which of your providers cannot change while a widget is on screen.**
  These are synchronous `Provider<T>` values that are changed from a **single
  screen** and **not** by the device or a background source. List the ones that
  qualify, and run the audit once per provider.
- **Out of scope - keep `watch`:**
  - The root app, a shell that always stays, and navigation bars (app bars, bottom
    nav). They are on screen whenever the value changes, so `watch` is right.
  - A `ref.watch` from one provider or notifier to another. That is correct
    dependency tracking, not the problem.
  - **Async or stream providers** (`FutureProvider`, `StreamProvider`, or anything
    that returns an `AsyncValue`). Here `ref.watch` tracks the change from loading to
    data, which happens *after* the widget appears; `ref.read` would freeze whatever
    state is current. Only synchronous providers qualify.
  - **A provider whose life depends on this watch.** `ref.read` does not set up a
    dependency, so if this widget is the *only* one watching an `autoDispose`
    provider, switching to `read` lets it dispose and rebuild (losing its state).
    Only switch when the provider is `keepAlive` or has another always-on-screen
    watcher.
- Skip generated files (`*.g.dart`, `*.freezed.dart`) and `test/`. Note locked files
  as Blockers.

## How to run

### Step 1 - Before you start

1. Note any locked or do-not-edit file as a **Blocker**.
2. **Check past decisions** (`AUTHORING.md`, Making an audit trustworthy). A `watch`
   chosen on purpose is not a finding:
   ```bash
   gh issue list --state closed --search "ref.watch OR reactivity OR read in:title,body" --limit 20
   git log --oneline -15 -- lib
   ```
3. **(Optional) Record a starting count** (`AUTHORING.md`, Improving an audit over
   time): the number of `ref.watch(<provider>)` uses.

### Step 2 - Find possible cases

```bash
rg -n 'ref\.watch\(localeProvider\)' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
Replace `localeProvider` with each fixed provider you listed. This matches the exact
single-line `ref.watch(name)` form; for a family use `ref\.watch\(localeProvider\(`,
and add `-U` for calls split over lines. Finding nothing means no exact single-line
match for this provider, not that the whole codebase is clear of the pattern.

### Step 3 - Sort each result by how long the widget stays on screen

For each result, find the widget it is in and ask: **can the provider's value change
while this widget is still on screen?**

| Verdict | When | Recommendation |
|---|---|---|
| **watch REQUIRED** | Always on screen (root, shell, navigation bars); a tab in an `IndexedStack` or shell that stays alive while the screen that changes the value is open; that screen itself, or anything you can reach from it without leaving; or an opened page that has a shortcut to that screen (it survives while the shortcut is used) | Keep `watch` |
| **read SAFE** | An opened page with **no** path to the screen that changes the value (the user must close it to change the value, so it is gone by then); a dialog or bottom sheet the user must close before doing anything else | Recommend `ref.read` |
| **NEEDS REVIEW** | You cannot tell how long the widget stays from the code alone (a shared sub-widget used by several screens, a changing tree, or navigation passed in through a callback) | A person reviews it |

For an opened page, the deciding question is the **shortcut check**: does this widget
(or a child) contain a way to reach the screen that changes the value without
closing this one? If yes, keep `watch`. If no, `read` is safe.

### Step 4 - Report

```markdown
## Provider-Reactivity Audit

### Summary
`ref.watch(<provider>)` uses: <N> - read-safe: <a> - watch-required: <b> - review: <c>

### Findings
| file:line | Widget | How long on screen | Verdict | Reason |
|---|---|---|---|---|
(or "None")

### Not reported (if any)
- [case]: [why it was skipped or was already decided]

### Blockers
<locked/do-not-edit files; "(none)" if none>
```

After the report, ask which one to fix first, or stop at planning. Do not change any
code without approval.

## The fix

Each read-safe finding is a one-line change:

```dart
// Before
final locale = ref.watch(localeProvider);
// After
final locale = ref.read(localeProvider);
```

Do it feature by feature, and **check** that a value change (switch the language in
Settings) still shows correctly when you go back into each screen you touched.

## Limitations

- This reads the code only. A path to the screen that changes the value, passed in
  through a **callback**, is missed, so a "read-safe" verdict can be wrong. When
  unsure, mark it NEEDS REVIEW.
- The verdicts assume your navigation shape (which screens stay on screen under a
  shell, and which are opened on top). Check again after any router change.
- Run it once per fixed provider, and confirm each provider really is changed from
  only one screen before you trust that it is fixed.
