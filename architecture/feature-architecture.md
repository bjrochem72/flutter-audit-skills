---
description: "Deep single-feature review against a four-layer architecture (domain, data, application, presentation) and modern Riverpod habits. Takes one feature path, walks each layer with small focused checks, and ends with a grouped fix plan. Report-only. For a fast whole-repo sweep use the clean-architecture audit."
---
# Audit: Feature Architecture

This audit reviews one feature in depth against a four-layer architecture and
modern Riverpod habits. It walks the feature layer by layer with small, focused
checks, then groups what it finds into ordered fix bundles so the work has a
sensible sequence. It reports and plans; it changes nothing without approval.

The layer model comes from Andrea Bizzotto's Code with Andrea articles
(https://codewithandrea.com), which set out the architecture this audit checks
against. The Riverpod advice follows the official Riverpod documentation, which
takes precedence where the two differ. Links to both are at the end.

The four layers, with dependencies only pointing inward:

- **domain** - plain entities and value objects. Depends on nothing.
- **data** - repositories that talk to the backend. Depends on domain.
- **application** - use cases and business rules. Depends on domain and data.
- **presentation** - widgets, screens, and controllers. Depends on the inner
  layers.

> **This is depth, not triage.** It takes one feature and reads it properly.
> For a quick import-direction sweep across every feature at once, use the
> **clean-architecture** audit instead.

## Usage

Run with a feature path, for example `lib/features/orders`. If no path is
given, stop and ask. Do not guess.

## What the agent running this needs

- File search, file reading, and a shell for `wc -l`.
- The ability to follow "read N lines around the match" instructions and make
  small judgements such as "is this match inside a build method?".
- Light class-scope reading for the checks marked (scope) below: read a class
  top to bottom and keep track of method boundaries and nesting. A large
  code-tuned model manages this; a very small one will guess. If the agent
  cannot do it, mark those checks "needs manual review" rather than guessing.

---

## How to run - ten steps

Finish each step before the next. Keep running notes; only Step 10 writes the
report.

### Step 1 - Before you start

1. Confirm the feature path exists (list its `*.dart` files). Zero files:
   stop and report "path not found".
2. Note any locked, generated, or do-not-edit file as a **Blocker**.
3. **Check past decisions** (see AUTHORING.md, Making an audit trustworthy).
   If the project uses GitHub and the CLI is available:
   ```bash
   gh issue list --state closed --search "<feature> in:title,body" --limit 20
   git log --oneline -15 -- "<feature-path>"
   ```
   Read the most relevant closed item in full, comments included. Anything
   marked won't-fix or by-design is held as a "past decisions" list. In Steps
   3 to 7, a finding that repeats one of those goes to the report's
   "Out of scope" section with the reference, not into the findings tables. It
   only returns as a finding with new evidence that the old decision was wrong.

### Step 2 - Inventory

List every `*.dart` file in the feature (skip generated files), take each
file's line count, and label each one by its path: entity, dto, repository,
use case, provider, controller, screen, widget, or test. Keep the table for
the report. Step 7 uses the list again.

### Step 3 - Domain checks

Scope: files under `<feature-path>/domain/`. For each hit, record
`ID, file:line, one-line description`.

The search patterns below assume ripgrep (`rg`): its Rust regex engine supports
`\s`, `\w` and capture groups with no extra flag. Only a lookaround (`(?=`,
`(?!`) needs `-P`. If you use POSIX `grep` instead, add `-E` and expect the
shorthand classes to behave differently.

| ID | Search and rule |
|---|---|
| D1 | `factory\s+([A-Z][a-zA-Z]*\.)?fromJson` or `Map<String,\s*dynamic>\s+toJson\s*\(` inside entities. Every hit except doc comments. The class-name part is optional on purpose: a Dart 3.13 primary-constructor class declares a bare `factory fromJson(`, and a pattern that requires the class name misses it. JSON mapping belongs in a DTO under `data/`. |
| D2 | `import\s+['"]package:cloud_firestore` inside `domain/` (the quote class covers both Dart quote styles). Backend types stay in the DTO. |
| D3 | An entity importing a data-layer casting or parsing helper. Move the casting into the DTO. |
| D4 | A validation getter on an entity that returns user-facing English strings (for example `String? get validationError`). Return a typed enum or sealed class instead, and let the UI translate it. |
| D5 | For each `class` in entities, read the lines just above it. No `@immutable` (and fields not all `final`): record it. |
| D6 | `ref\.watch|ref\.read|\bRef\s+|Provider<` inside `domain/`. Entities never reach for providers. |
| D7 | A field documented with a trailing `//` comment instead of `///`. The doc will not show on hover. |
| D8 | (scope) `\?\?\s+this\.\w+` inside entities. Record only when the hit is inside a `copyWith` body AND the field is nullable. That `copyWith` can never clear the field: passing `null` falls back to the old value. Fix: a sentinel default, or document the limit. |
| D9 | `'null'` or `"null"` inside entities. Record when a `toString` formats a **non-nullable** field as the text "null" - it can be empty, never null, so the output lies. |

Not a violation: reusing `entity.id` as the backend document id or storage
path. That is idiomatic in this architecture.

### Step 4 - Data (repository) checks

Scope: `<feature-path>/data/`.

| ID | Search and rule |
|---|---|
| R1 | A write method returning `Future<bool>` to signal success. Return `Future<void>` and throw; a bool invites silent failure. |
| R2 | `if\s*\(\s*!.*\.isValid\s*\)` - the repository running domain business validation. The caller owns that; the repository stores and fetches. |
| R3 | A repository method that catches an error and returns a made-up or empty value instead of logging and rethrowing. Read every `catch` block in `data/` and record the silent ones. |
| R4 | A mapping factory (`fromJson` / `fromFirestore` / `fromMap`) that falls back to a default for a **required** field: patterns like `as\s+\w+\??\s*\?\?\s*''`, `\?\?\s*0\b`, or a bool defaulted to true or false. For each hit, check whether the entity treats that field as required (non-nullable, or validated as non-empty). If it does, the fallback hides bad data. Fix: throw a `FormatException` and let the stream skip and log that record. |
| R5 | A stream that filters records with a domain `isValid` check (look for `.isValid` near `.where(`, `.map((`, or `.snapshots()`). Structurally bad records are the mapper's job; business-invalid records are the caller's call. |
| R6 | `BuildContext|AppLocalizations` inside `data/`. A repository never touches UI types. |

### Step 5 - Application checks

Scope: `<feature-path>/application/` (and `providers/` for A6).

| ID | Search and rule |
|---|---|
| A1 | `BuildContext|AppLocalizations` in a use-case signature. Return a typed result; let the widget localise it. |
| A2 | A use case returning pre-localised strings (search for your localisation accessor on or just after a `return`, for example `l10n\.`, `S\.of`, `context\.l10n`). Same fix as A1. |
| A3 | (scope) Mixed dependency injection: one dependency via the constructor, another passed into each method. Pick the constructor for all of them. |
| A4 | (scope) A use case whose every public method only forwards a single repository call with no logic at all. Delete it and call the repository; a pass-through layer earns nothing. |
| A5 | UI choreography inside a use case: `showDialog`, `showModal`, an image picker, `Navigator`. That belongs in the widget. |
| A6 | (scope) A business rule written inline in a provider body: a tier or plan comparison, a limit check against a constant, a feature gate. Extract it into a pure function in `application/` so it can be tested alone. |

### Step 6 - Presentation checks

Scope: `<feature-path>/presentation/` and `<feature-path>/providers/`.

| ID | Search and rule |
|---|---|
| P1 | Form state held in a `@riverpod class ...FormController`. Plain per-screen form state is simpler as widget-local state. |
| P2 | `ensureInitialized` called from `build`. Remove the need for it. |
| P3 | `Future.microtask` used to mutate state. Fix the root cause instead. |
| P4 | (scope) A `.notifier` method called synchronously in `initState` / `didChangeDependencies` without `addPostFrameCallback`. |
| P5 | A controller reading `.value` from an async provider and branching on null instead of using `.when(data:, loading:, error:)`. |
| P6 | A raw `try/catch` inside a mutation method on a controller. `AsyncValue.guard` keeps the error in the state where the UI can see it. |
| P7 | A record type like `({bool success, String? error})` used as an operation result. It can represent success-with-error. Use a sealed class. |
| P8 | A widget calling `ref.invalidate(...)` on a data provider to refresh. Give the controller a `refresh()` method. |
| P9 | A widget watching a raw stream or future provider directly for data it then manages. Check the provider definition: if it is a plain function returning `Stream`/`Future` (not a Notifier class), consider a `StreamNotifier` / `AsyncNotifier` so retries and updates have one home. |
| P10 | (scope) Business logic inside `build`: a tier or limit comparison, a length rule. Move it behind the application layer. |
| P11 | (scope) `ref.read` used in `build` for a value that can change, or `ref.watch` inside a callback (`onPressed:`, `builder:`, a lambda). Swap them. The provider-reactivity audit covers this repo-wide; here it is one feature deep. |
| P12 | `bool isSaving` style flags inside a provider's state type. Per-operation `AsyncNotifier<void>` or widget-local state is cleaner. |
| P13 | (scope) A `@riverpod class` with no mutable state and no reactivity - every member a getter, no `state =` anywhere. A plain function provider does the same with less. |
| P14 | (scope) Form state duplicating a value that a stream provider already supplies. Drop the duplicate and read the provider. |
| P15 | Legacy Riverpod API anywhere in the feature: `extends StateNotifier<`, `StateNotifierProvider`, `StateProvider`, `ChangeNotifierProvider`, or a `riverpod/legacy.dart` import. Riverpod 3 moved these to a legacy library; migrate to `Notifier` / `AsyncNotifier`. (`\bStateProvider\b` with the word boundary does not match names like `appStateProvider`.) |
| P16 | (scope) A widget that calls a use case's mutation directly and tracks progress with a local `bool _isSaving` plus `setState`. Introduce a small `AsyncNotifier<void>` controller; the widget watches `isLoading` and listens for completion. |

### Step 7 - Cross-layer checks

| ID | Search and rule |
|---|---|
| X1 | Sibling-feature imports. Build the feature's own package prefix (replace the leading `lib/` in the feature path with `package:<your_app>/`). Search the feature for imports of other features' paths; record any import of a sibling feature. Shared code belongs in a shared layer, not reached across. |
| X2 | A widget importing from `data/`. Widgets speak to controllers and use cases. |
| X3 | An entity importing `package:flutter/...`. Domain stays Flutter-free. |
| X4 | A `@Riverpod(keepAlive: true)` provider watching an autoDispose (`@riverpod`) provider. The keepAlive pins the autoDispose dependency alive forever, which defeats its lifecycle. If your project wires `riverpod_lint`, run `dart analyze` with no path arguments and record each `only_use_keep_alive_inside_keep_alive` diagnostic in the feature (a path-scoped analyze can skip plugin lints). Without the lint, check by hand: find each `@Riverpod(keepAlive: true)` in the feature, read its body, list every provider it watches, look up each one's annotation, and record the provider if any watched dependency is plain `@riverpod`. |

### Step 8 - Group the findings into bundles

Walk the finding IDs and trigger bundles with this mapping:

| Findings present | Bundle |
|---|---|
| D1, D2, D3, R4 | **1. DTO extraction** |
| D4 | **2. Typed validation errors** |
| R1, R3 | **3. Repository error contract** |
| R2, R5, R6 | **4. Remove repository-side business validation** |
| A1, A2, A3, A5 | **5. Sealed results and a UI-free application layer** |
| A6 | **6. Extract the business rule from the provider** |
| P8, P9 | **7. Controller for the read-side stream** |
| P16 | **12. Mutation controller extraction** |
| P1, P2, P3, P4, P5, P6, P7, P12, P14 | **8. Form-state migration** |
| (whenever 8 runs) | **9. Delete the old form controller** |
| P15 | **10. Legacy notifier upgrade** |
| X4 | **13. KeepAlive lifecycle fix** |
| A4 | (not a bundle) recommend deleting the use case |
| D5 to D9, P10, P11, P13, X1 to X3 | **11. Housekeeping** |

Order: 1, 2, 3, 4, 5, 6, 7, 12, 8, 9, 10, 13, 11. Bundle 12 sits before 8
because a small mutation controller proves the pattern before the form
migration leans on it. Bundle 13 is independent; it sits late only so
housekeeping stays last.

### Step 9 - Effort and blockers

Give each bundle a rough effort figure from your own project's history; a
first run can use the bundle list without numbers. List the blockers from
Step 1.

### Step 10 - Report

Sections, in order: inventory table; findings per layer (write "(none)" for an
empty table); the bundle plan, each bundle with the findings it resolves, the
files touched, what it depends on, and how it will be verified (analyzer clean
plus the feature's tests); blockers; estimated effort; out of scope, including
every past decision that was not re-raised, with its reference.

After the report, ask which bundle to run first, or stop at planning. Do not
edit without approval.

---

## Out of scope - do not flag

- `entity.id` reused as the backend document id or storage path. Idiomatic.
- Experimental Riverpod features (mutations) - do not recommend adopting them
  while the Riverpod documentation still marks them experimental.
- Sibling features themselves (only the imports that reach into them).
- Shared cross-feature controllers that live in a shared layer.
- Where an older architecture article and current Riverpod documentation
  disagree, the Riverpod documentation wins; do not flag code for following it.

## References

Architecture (Andrea Bizzotto, Code with Andrea):

- https://codewithandrea.com/articles/flutter-repository-pattern/
- https://codewithandrea.com/articles/flutter-app-architecture-domain-model/
- https://codewithandrea.com/articles/flutter-app-architecture-application-layer/
- https://codewithandrea.com/articles/flutter-presentation-layer/

Riverpod (takes precedence where it conflicts):

- https://riverpod.dev/docs/root/do_dont
- https://riverpod.dev/docs/whats_new

## Calibrating for your codebase

- The (scope) checks need real reading; a pure pattern match will over- and
  under-report on them. Mark them "needs manual review" when the agent cannot
  read class scope.
- Folder names differ between projects (`usecases/` for `application/`,
  `models/` for `entities/`). Map the checks to your names before running.
- Keep the report to the tables. The value is the ordered bundle plan, not
  prose.
