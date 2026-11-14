---
description: "Clean Architecture layer-boundary breaks across feature folders: a domain file importing data or presentation, an application file importing presentation, a repository defined under presentation, a widget defined under domain, value entities missing == / hashCode, and JSON mapping written inside domain entities. Fast whole-repo sweep, report-only. For a deep single-feature review use the feature-architecture audit."
---
# Audit: Clean Architecture

This audit looks across your feature folders for **layer-boundary breaks**. Clean
Architecture splits a feature into four layers, and dependencies only point one
way (inward):

- **domain** - plain entities and value objects. Depends on nothing.
- **data** - repositories that talk to the backend. Depends on domain.
- **application** - use cases and business rules. Depends on domain (and data).
- **presentation** - widgets, screens, and state controllers. Depends on the
  inner layers.

A break is a dependency pointing the wrong way (an inner layer reaching out to an
outer one), or a file living in the wrong layer. This audit reports what it finds
and does not change any code.

> **This is triage, not depth.** It checks import direction and file placement
> across every feature quickly. For a deep, single-feature review with a
> remediation plan, use the **feature-architecture** audit and pass the feature path.

## Scope

- Include your feature folders, each with `domain/`, `data/`, `application/`, and
  `presentation/`. The examples below assume features live under `lib/` (for
  example `lib/<feature>/domain/`); change the path to your layout (some apps use
  `lib/src/`, `lib/features/`, and so on).
- Skip generated files (`*.g.dart`, `*.freezed.dart`) and any unused-code folder.
- Note any locked or do-not-edit file as a Blocker.

## Severity legend

| Severity | Meaning |
|---|---|
| **HIGH** | A clear layer break: a wrong-way import, or a file in the wrong layer |
| **MEDIUM** | An entity or controller contract issue: a value entity missing `==` / `hashCode`, or a controller on a legacy state base |
| **LOW** | A structural difference: an unapproved abstract class, or a missing layer folder |
| **OK** | On purpose (an approved abstract class): appendix only |

---

## How to run

### Step 1 - Before you start

1. Note any locked or do-not-edit file as a **Blocker**.
2. **Check past decisions** (`AUTHORING.md`, Making an audit trustworthy). An
   abstract class flagged below may already have been reviewed and approved. If you
   use GitHub and have the CLI, check closed issues; otherwise use wherever your past
   decisions live. In any project, check recent Git history:
   ```bash
   gh issue list --state closed --search "architecture OR layer OR abstract class in:title,body" --limit 15   # GitHub only
   git log --oneline -15 -- lib
   ```
   Hold any such item as a "past decisions" note.

### Step 2 - Run the searches

A search result is a possible case. Read a few lines around it and apply the rule.
Shared exclusions: `--include='*.dart' --exclude='*.g.dart' --exclude='*.freezed.dart'` (add your unused-code
folder if you have one).

#### HIGH - Layer breaks

**C1 - a `domain/` file imports from `data/`, `application/`, or `presentation/`.**
Domain must depend on nothing outward.
```bash
grep -rnE "import\s+['\"].*/(data|application|presentation)/" lib --include='*.dart' --exclude='*.g.dart' --exclude='*.freezed.dart' | awk -F: '$1 ~ /\/domain\//'
```
The trailing `awk -F: '$1 ~ /\/domain\//'` keeps only rows whose **file path** (the
part before the first colon) is under a `domain/` folder, so it does not match a
file that merely *imports from* a data/presentation path. Fix: turn the dependency
around.

**C2 - an `application/` file imports from `presentation/`.**
```bash
grep -rnE "import\s+['\"].*/presentation/" lib --include='*.dart' --exclude='*.g.dart' --exclude='*.freezed.dart' | awk -F: '$1 ~ /\/application\//'
```
Fix: return a typed result and let the widget render it.

**C3 - a repository class is defined under `presentation/`.**
```bash
grep -rln "class .*Repository" lib --include='*.dart' --exclude='*.g.dart' --exclude='*.freezed.dart' | grep '/presentation/'
```
`class .*Repository` also matches a name that merely contains "Repository" (a helper,
fake, or test double), so confirm the hit actually **defines** a repository before
recording. Fix: move it to `data/`.

**C4 - a widget is defined under `application/` or `domain/`.**
```bash
grep -rlnE "extends\s+(Stateless|Stateful|Consumer|ConsumerStateful|HookConsumer|Hook)Widget" lib --include='*.dart' --exclude='*.g.dart' --exclude='*.freezed.dart' | grep -E '/(application|domain)/'
```
The base list covers Flutter (`StatelessWidget` / `StatefulWidget`), Riverpod
(`ConsumerWidget` / `ConsumerStatefulWidget`), and hooks (`HookWidget` /
`HookConsumerWidget`); add any custom widget base your app uses. Fix: move the
widget to `presentation/`.

> **Layer name vs grouping name.** C1 to C4 assume `domain` / `data` /
> `application` / `presentation` are your **layer** folders, each a sibling of the
> other three inside a feature. If your repo also uses one of those words as a
> **grouping** folder - for example `core/domain/<module>/presentation/...`, where
> `domain` groups modules rather than naming a layer - files under it match the path
> filter but are **not** layer breaks. Drop them in Step 3: a real hit is a file in a
> leaf layer folder that sits alongside the other three.

#### MEDIUM - Entity and controller contract

**C5 - a value entity has no value-equality.** List the value classes under
`domain/` and read each one:
```bash
grep -rln "class " lib --include='*.dart' --exclude='*.g.dart' --exclude='*.freezed.dart' | grep '/domain/'
```
Entities may live in `domain/entities/`, `domain/models/`, `domain/value_objects/`,
or directly under `domain/`, so this lists all `domain/` classes; narrow the filter
to your entity folder if you keep them in one place. Record a class only when BOTH
hold: it is genuinely **compared by value** - deduped in a `Set`, compared with `==`,
or relied on to skip a rebuild when unchanged (merely being *stored* in state is not
enough; confirm it is actually compared) - AND it has no value-equality at all. "No
value-equality" means no explicit `operator ==` / `hashCode` **and** it does not get
them from a package: a class that `extends Equatable`, uses `with Equatable` / `with
EquatableMixin`, or is a `@freezed` class already has value-equality, so do **not**
flag it. This finds an absence, so read the class to confirm. A plain data-transfer
object that is never compared does not need value-equality. Fix: add `==` and
`hashCode` (or adopt `Equatable` / `freezed`), or document why it is not needed.

Do not shortcut this check with a search for files that lack `operator ==`. A
class that mixes in `Equatable` never declares `==` itself, so an absence
search wrongly flags it. Read the class.

**C6 - a controller uses a legacy state base.**
```bash
grep -rlnE "extends\s+(StateNotifier|ChangeNotifier)" lib --include='*.dart' --exclude='*.g.dart' --exclude='*.freezed.dart' | grep '/presentation/'
```
`StateNotifier` and `ChangeNotifier` are legacy state bases; the modern Riverpod
replacements are `Notifier` and `AsyncNotifier`. (Riverpod 3 relegated the legacy
pieces - `StateNotifier`, `StateProvider`, `StateNotifierProvider`,
`ChangeNotifierProvider` - to `legacy.dart`; `ChangeNotifier` itself is Flutter's own
class, so confirm the match
is a state controller, not an unrelated `ChangeNotifier`.) Fix: migrate. This
overlaps the feature-architecture audit's legacy-Riverpod check; note the cross-reference rather
than double-filing.

**C10 - JSON mapping written inside a domain entity.**
```bash
grep -rnE "factory\s+([A-Z][A-Za-z]*\.)?fromJson|Map<String,\s*dynamic>\s+toJson\s*\(" lib --include='*.dart' --exclude='*.g.dart' --exclude='*.freezed.dart' | awk -F: '$1 ~ /\/domain\//'
```
The class-name part of the pattern is optional on purpose. A Dart 3.13 class
with a primary constructor declares a bare `factory fromJson(` with no class
name in front of it, and a pattern that requires the class name silently stops
matching those files. Some teams keep manual JSON code in their entities on
purpose; if that is your stated choice, skip this check. The finding is a break
from your own chosen boundary: a project whose rule is "JSON lives in a DTO in
`data/`" with a handful of entities that still carry `fromJson` / `toJson`.
Skip doc comments. Fix: move the mapping into a DTO class under `data/`.

#### LOW - Structure

**C7 - an unapproved abstract class.**
```bash
grep -rnE "^[[:space:]]*abstract class" lib --include='*.dart' --exclude='*.g.dart' --exclude='*.freezed.dart'
```
Record a class only when it is not on your approved-abstract-class list (keep one;
see the appendix). The generated-file exclusions matter: without them, generated
classes (`*.g.dart`, `*.freezed.dart`) dominate the results. Note that `freezed` and
`riverpod` declare an `abstract class` in the **source** file (for example
`abstract class Foo with _$Foo`), which the `*.freezed.dart` exclusion does not
remove - put those base classes on the approved list. Fix: approve it (add to the
list) or remove it.

**C8 - a feature folder is missing one of the four layers.**
```bash
for d in lib/features/*/; do for l in application data domain presentation; do [ -d "$d$l" ] || echo "$d missing $l/"; done; done
```
**Point the loop at the folder that holds your features** (for example
`lib/features/*/` or `lib/src/pages/*/`), not all of `lib/`. A top-level `lib/` also
holds non-feature folders (`core/`, `shared/`, `theme/`, `l10n/`, and so on) that
have no layer structure and would all report as "missing" - noise, not findings.
Record only a real feature folder (not a grouping folder that just holds
sub-features). Fix: add the folder, or confirm the feature is meant to be partial.

#### C9 - Module-direction (optional; enforce with a test, not a search)

If your app splits into an outer layer (features or pages) and an inner shared
layer (core or common), the rule is that the outer layer may depend on the inner
one but **never the other way**. A search cannot check this reliably across a
whole app; a small test that walks imports can. If you have such a split, add a
test that fails when an inner-layer file imports from the outer layer, with an
explicit allow-list of any sanctioned crossings. Then:

- Record **HIGH** if that test fails.
- Record **MEDIUM** for any newly added entry in the allow-list since the last run
  (read its justification; the list growing is itself a finding, not
  housekeeping).

If you have no such split, skip C9.

### Step 3 - Check each result

Re-read each cited line. For C1 and C2, confirm it is a real **wrong-way (outward)**
import - an inner-layer file reaching out to an outer layer - not a same-layer
re-export. For C5, confirm the class is really compared by value before flagging. A
pure data-transfer object that is never
compared does not need `==`.

### Step 4 - Report

```markdown
## Clean Architecture Audit

### Summary
- Features scanned: <N> | HIGH layer: <a> | MEDIUM entity/controller: <b> | LOW structure: <c>

### HIGH - Layer breaks
| ID | file:line | Evidence (the bad import / misplaced class) | Fix |
|---|---|---|---|
(or "(none)")

### MEDIUM - Entity / controller contract
| ID | file:line | Evidence | Fix |
|---|---|---|---|
(or "(none)")

### LOW - Structure
| ID | file:line | Evidence | Fix |
|---|---|---|---|
(or "(none)")

### Features checked
- OK `<feature>` - compliant
- WARN `<feature>` - <n> issues

### Prior decisions (not re-raised)
| #issue | Item | Why out of scope |
(or "(none found)")

### Blockers
<locked/do-not-edit files; "(none)">
```

After the report, ask which one to fix first, or stop at planning. Do not change
any code without approval.

---

## Approved abstract classes (OK; appendix, never a finding)

Keep a short list of the abstract classes you have reviewed and accepted (a shared
base widget, a domain exception base, and so on), plus generated ones (an env
config, localisations). C7 records only abstract classes that are **not** on this
list.

## Calibrating for your codebase

Import direction and file placement are deterministic, so C1 to C4 are reliable.
The only judgement calls are C5 (is the entity really compared by value?) and C8
(is this a real feature or just a grouping folder?), both settled by the Step 3
read. This audit stays shallow on purpose. For anything beyond import direction and
file placement, use the feature-architecture audit on the single feature.
