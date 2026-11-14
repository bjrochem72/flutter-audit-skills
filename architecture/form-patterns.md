---
description: "Form widget consistency: a form that breaks the state pattern your app chose (controllers or initialValue + onSaved), validation logic written inline instead of shared, missing loading / offline / reset wiring, giant screens with no extracted sections, and taps without semantics. Searches presentation form files and only reports."
---
# Audit: Form Patterns

This audit checks that your forms are consistent with each other. Flutter has
two reasonable ways to hold form state - a `TextEditingController` per field,
or `initialValue:` plus `onSaved:` - and both work. Problems start when one
app mixes them without a reason, writes validation logic inline in one form
and shares it in another, or ships one form with loading and offline handling
and the next with neither. The audit reports what it finds and does not change
any code.

Before running it, write down two choices:

1. **Your state pattern.** Controllers, or `initialValue` + `onSaved`. If you
   have no stated choice yet, the audit's first run tells you which way your
   code already leans.
2. **One reference form.** Your best form screen. The checks compare the
   others against it.

## Scope

- `lib/**/presentation/**/*form*.dart` (adjust to your layout).
- Skip generated files and tests.
- Note any locked or do-not-edit file as a Blocker.
- **The scope is name-based, and that is a known gap.** Add and edit screens
  without "form" in the file name fall outside it. List your known ones and
  check them by hand, or widen the glob for your project.

## Severity legend

| Severity | Meaning |
|---|---|
| **HIGH** | Breaks your chosen pattern, or validation logic that cannot be reused |
| **MEDIUM** | Missing wiring the reference form has: loading, offline, reset, semantics |
| **LOW** | Small drift worth noting |
| **OK** | Allowed exception; appendix only |

---

## How to run

### Step 1 - Before you start

1. Note locked files as **Blockers**.
2. **Check past decisions** (AUTHORING.md, Making an audit trustworthy):
   ```bash
   gh issue list --state closed --search "form OR validator OR upload in:title,body" --limit 15   # GitHub only
   git log --oneline -10 -- lib
   ```
   Hold won't-fix and by-design items; do not re-raise them.

### Step 2 - Run the searches

Read five lines around each hit before recording it. Comments and doc comments
are never findings.

#### F1 - Form state against your chosen pattern (HIGH)

```bash
rg -n 'TextEditingController' lib -g '**/presentation/**/*form*.dart' -g '!*.g.dart'
```

If your pattern is `initialValue` + `onSaved`: record a controller that only
holds plain save-time state. A controller is still fine for live formatting,
real-time validation, or async-seeded values synced on change - note those in
the appendix. If your pattern is controllers: invert the check, and record
forms that use `onSaved` instead.

#### F2 - Inline validation logic (HIGH)

```bash
rg -n 'validator:\s*\(' lib -g '**/presentation/**/*form*.dart' -g '!*.g.dart'
```

Record only when the closure holds the rules themselves (length checks, regex,
emptiness chains). A thin adapter that calls a shared validator class is fine.
Fix: move the rules to a shared validators class so every form and test uses
the same ones.

#### F3 - Error display that differs from the rest (HIGH)

```bash
rg -n 'showCupertinoDialog|showDialog\(' lib -g '**/presentation/**/*form*.dart' -g '!*.g.dart'
```

If your app has one standard way to show a save error (a snackbar helper, a
standard dialog), record a form that invents another. Confirmation dialogs are
not errors; skip them.

#### F4 - Wrong scroll container (HIGH)

```bash
rg -n '\bListView\(' lib -g '**/presentation/**/*form*.dart' -g '!*.g.dart'
```

Record only when the `ListView` is the form's own scroll container (a data
list inside one section is fine). A form body is usually a
`SingleChildScrollView` with a `Column`; a `ListView` can discard offscreen
field state.

#### F5 - Un-extracted form sections (MEDIUM)

```bash
rg -n '_build\w*(Card|Section)\b' lib -g '**/presentation/**/*form*.dart' -g '!*.g.dart'
```

Record only when the method holds a lot of inline UI. A `_build...` that just
passes work to an existing widget is fine. Fix: extract a section widget per
group of fields, the way your reference form does.

#### F6 - Tap targets without semantics (MEDIUM)

```bash
rg -n 'GestureDetector\(' lib -g '**/presentation/**/*form*.dart' -g '!*.g.dart'
```

Read around each hit for a wrapping `Semantics`, `InkWell`, or button (those
carry semantics already). Record a bare `GestureDetector` on an interactive
form element.

#### F7 - Missing loading state (MEDIUM, inventory)

```bash
rg -L '_?isLoading|_?isSaving' lib -g '**/presentation/**/*form*.dart' -g '!*.g.dart'
```

Lists form files with neither flag. Record a form that owns a save action but
gives no saving feedback. A section widget that does not own the save is fine.

#### F8 - Missing offline handling (MEDIUM, inventory)

If your app has a connectivity provider, list which forms check it before a
save or upload, and record the ones whose save path has no guard at all (a
guard in the hosting screen counts). Skip this check if your app treats
offline as the backend's problem.

#### F9 - Missing reset support (LOW, inventory)

If your reference form offers a reset, list the form widgets that do not, and
decide per form whether reset makes sense there.

#### F10 - Files picked before the record exists

If your app uploads files while the user is still filling in a create form,
the upload can outlive a cancelled form and leave an orphan in storage. If you
have a draft-upload lifecycle (a session that tracks pre-save uploads and
cleans up on cancel), check every pre-save upload in the form files registers
with it. If you do not have one, note any pre-save upload you find; the risk
and the cleanup strategy are a project decision, not a one-line fix.

### Step 3 - Check each result

Re-read each cited line. Drop comments, doc examples, and anything your
exceptions list allows. Allowed exceptions go in the appendix, not the
findings.

### Step 4 - Report

```markdown
## Form Patterns Audit

### Summary
Form files: <n> | Pattern: <yours> | HIGH <n> | MEDIUM <n> | LOW <n>

### Findings
| Severity | file:line | Pattern | Fix |
(or "None")

### Inventories
- Loading state: <n> of <n> forms
- Offline guard: <n> of <n> forms (or "not applicable")
- Reset: <n> of <n> form widgets

### Past decisions (not re-raised)
- [item]: [reference]

### Appendix - allowed
| file:line | Match | Why allowed |

### Blockers
<locked files; "(none)">
```

After the report, ask which one to fix first, or stop at planning. Do not
change any code without approval.

## Calibrating for your codebase

- **The pattern choice is yours.** This audit never says controllers are wrong
  or `onSaved` is right; it says an app that mixes both without a reason is
  harder to work on. Write the choice down and the audit enforces it.
- **Design-system checks belong to you.** If your app has its own button or
  text field, add a check that forms use it (AUTHORING.md, Cover your own
  conventions) rather than borrowing another project's widget names.
- **Record starting counts** for F1 and F2 on the first run and compare later
  runs against them; the raw numbers mean nothing outside your project.
