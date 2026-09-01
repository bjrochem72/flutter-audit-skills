---
description: "Dependency-injection completeness: outside services (`.instance` / `.instanceFor(` / a static class) reached directly instead of through a Riverpod provider, so a test cannot replace them. Searches the code and only reports. Provider files, the Firebase layer, and start-up code are the places where reaching a service directly is allowed."
---
# Audit: DI Completeness

This audit checks how your code reaches its outside services (the SDKs it depends
on, such as Firebase). The tidy way is to reach each service through one Riverpod
provider. A provider is a small wrapper, and it is the only place that touches the
service. Because a test can swap the provider for a fake, any code that reads the
provider is easy to test.

The audit looks in `lib/` for the opposite: code that reaches a service directly
(`*.instance`, `instanceFor(...)`, or a static class) instead of going through a
provider. When code does that, a test cannot replace the service, so that code is
hard to test. It reports what it finds and does not change any code.

Two kinds of files are allowed to reach a service directly, and never count as a
problem:

- **Provider files and the Firebase layer.** A provider such as
  `firebaseAuthProvider` or `firebaseFunctionsProvider` wraps `.instance` on
  purpose. That wrapper is the point, not a mistake.
- **Start-up code.** Code that runs before providers exist (an app bootstrap, a
  `*_initializer.dart`, a start-up file) has no provider to read yet.

## Scope

- Look in `lib/**/*.dart`. Skip generated files (`*.g.dart`, `*.freezed.dart`) and
  `test/`.
- The two allowed places above never count as a problem.
- Note any locked or do-not-edit file as a Blocker.

## Severity legend

| Severity | Meaning |
|---|---|
| **HIGH** | A provider already exists for this service, but the code reaches it directly and skips the provider (so a test cannot replace it) |
| **MEDIUM** | The service has no provider at all (nothing can replace it in a test) |
| **LOW** | A set-up gap: a lint that is installed but not switched on, or a config value repeated in many places |
| **OK** | Start-up code, a framework value, or a plugin value: listed in an appendix, never a problem |

## Allowed (OK - appendix, never a problem)

- **Start-up code** that runs before any provider exists: an app bootstrap or a
  `*_initializer.dart` that sets the service up first.
- **The provider wrappers themselves.** A `firebaseAuthProvider` or
  `firebaseFunctionsProvider` that wraps `.instance` is the wrapper you want, not a
  mistake.
- **Flutter framework values** such as `WidgetsBinding.instance`,
  `PaintingBinding.instance`, and `PlatformDispatcher.instance`. These are not
  outside services.
- **Plugin values used in the UI**, for example `SharePlus.instance` or
  `InAppReview.instance`. Low priority; wrap one only if that code needs a test.
- **Firestore types** such as `Timestamp`, `Query`, or `DocumentSnapshot` used
  above the `data/` layer. That is a different audit (repository boundary).
  Firestore is your backend, not a part you plan to swap out.

---

## How to run

### Step 1 - Before you start

1. Note any locked or do-not-edit file as a **Blocker**.
2. **Check past decisions** (`AUTHORING.md`, Making an audit trustworthy). An
   earlier review may have chosen to leave one of these as it is:
   ```bash
   gh issue list --state closed --search "dependency injection OR provider seam OR mockable in:title,body" --limit 15
   git log --oneline -15 -- lib
   ```
3. **(Optional) Record a starting count** (`AUTHORING.md`, Improving an audit over
   time): the number of `.instance` / `instanceFor(` uses outside the allowed
   places.

### Step 2 - Run the searches

A search result is a lead. Read a few lines around it and confirm the file is not
one of the allowed places before you record it.

#### DI1 - Code reaches a service directly even though a provider exists (HIGH)
```bash
rg -n '\.instance\b|\.instanceFor\(' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
Add any static entry point your SDKs expose (for example `Purchases\.[a-z]` for
RevenueCat, or an analytics class). Record a hit only when it is **outside** the
allowed places (provider files, the Firebase layer, start-up code) **and** a
provider already exists for that service (name it in your finding). A repository,
use case, or widget reaching `.instance` when `firebaseAuthProvider` exists is the
real problem, because a test cannot replace it.

#### DI2 - A service with no provider at all (MEDIUM)
```bash
rg -n 'FirebaseMessaging\.|FirebaseFunctions\.instanceFor|FirebaseAppCheck\.|Purchases\.' lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
This is a starting list of common entry points. Add the static entry point of
every outside SDK your app uses. List each service that has **no provider anywhere**
(search for `<Service>Provider` to check). Group by service: **one finding per
service**, not one per line. The fix is a provider that wraps `.instance` (or a
thin wrapper of your own for a service you want to hide behind your own type). Note
any small local wrapper that already exists.

#### DI3 - riverpod_lint is installed but switched off (LOW)
```bash
grep -n 'riverpod_lint' pubspec.yaml; grep -nA5 'analyzer:' analysis_options.yaml
```
Record this when `riverpod_lint` is listed in `pubspec.yaml` but the `custom_lint`
plugin is not turned on under the `analyzer: plugins:` block in
`analysis_options.yaml`. Your Riverpod lints are installed but never run. (The
search is only a hint: check that `custom_lint` really is under `analyzer.plugins`
and not in a comment.) Note that `riverpod_lint` checks general Riverpod habits,
**not** the direct-service problem this audit is about. For that, add a CI search
that bans `.instance` outside the allowed places. Fix: turn on `custom_lint`, and
add that CI search.

#### DI4 - A config value repeated across many `instanceFor` calls (LOW)
```bash
rg -n "region:\s*['\"]" lib -g '*.dart' -g '!*.g.dart' -g '!*.freezed.dart'
```
Record this when a config value (for example a Cloud Functions region such as
`'europe-west1'`) is repeated across many `instanceFor` calls. This matches
`region:` in any position; add `-U` for calls split over several lines. Move it to
one shared constant next to the provider. This usually folds into the DI2 finding
for that service.

### Step 3 - Check each result (drop anything that does not hold)

- DI1 - confirm the file is not one of the allowed places, and that a provider for
  that exact service exists (name it). Drop hits inside provider files, the
  Firebase layer, or start-up code, and drop framework and plugin values.
- DI2 - confirm there really is no provider (search `<Service>Provider`). Note any
  small local wrapper (a callable typedef, a service class) as partial cover, rather
  than calling the service fully untestable.

### Step 4 - Report

```markdown
## DI Completeness Audit

### Summary
| Category | Count |
|---|---|
| DI1 Reaches a service directly although a provider exists | <n> |
| DI2 Services with no provider | <n> services |
| DI3 riverpod_lint switched off | yes/no |
| DI4 Config value repeated | <n> places |

### DI1 - Reaches a service directly (provider exists)
| file:line | Service reached | Provider it should use | Fix |
(or "None")

### DI2 - No provider (per service)
| Service | Where it is called | Any local wrapper? | Suggested provider |
(or "None")

### DI3 / DI4 - Set-up and repetition
| Item | State | Fix |
(or "None")

### Not reported (if any)
- [result]: [why it was skipped or was already decided]

### Blockers
<locked/do-not-edit files; "(none)" if none>
```

After the report, ask which one to fix first, or stop at planning. Do not change
any code without approval.

## Calibrating for your codebase

- **The allowed places do most of the work.** Most `.instance` hits are the
  provider wrappers or start-up code. DI1 only counts a hit that is outside those
  places and where a provider for the service already exists.
- **Framework and plugin values** (`WidgetsBinding.instance`,
  `SharePlus.instance`) match the search but are out of scope. Step 3 drops them.
- **A small wrapper still counts.** A service reached through a callable typedef or
  a service class is partly testable already. Note it, rather than calling it fully
  untestable.
- **Do not double up with other audits.** A wrapper skipped for a location or
  permissions SDK may belong to a dependency-hygiene audit, and a Firestore-type
  leak to a repository-boundary audit. Point to those, do not file the same thing
  twice.
