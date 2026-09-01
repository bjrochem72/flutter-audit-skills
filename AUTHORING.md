# Authoring audits

A good audit does not try to find every possible match. It finds a small number of
problems, each checked carefully enough to trust.

That one idea shapes everything below. An audit that only matches a text pattern
produces a lot of findings that do not hold up. That wastes the reader's time, and
it can lead to "fixing" something that was meant to be there. The steps here help
you avoid that.

If you have never written one, start at "Create your first audit" and copy the
template. The sections after it help you make an audit more trustworthy and improve
it over time. You do not need them for a good first version. The audits in this
repository are worked examples you can read next to this guide.

---

## What an audit is

An audit is a short Markdown file. It holds a set of searches. Each search comes
with a rule for deciding whether a result is a real problem, and then instructions
to report what was found without changing any code. You give the file to an AI
agent, or work through it yourself, and it produces a list of problems for you to
review.

---

## Create your first audit

Five steps, only the essentials.

1. **Pick one problem.** An audit covers a single type of problem, for example "an
   image decoded at full size into a small box". Narrow beats broad.
2. **Search for possible cases.** Write one or two `rg` (ripgrep) patterns that find
   places the problem could be. A search result is a possible case, not a finding.
3. **Check each case in context.** Read the few lines around each result, and keep
   it only if the rule really applies. If deciding needs analysis the agent cannot
   do, mark it for a person to review instead of guessing.
4. **Say what to skip.** List the things that look similar but are not the problem,
   so they are not reported. Also say what it means when the search finds nothing: a
   clean result, or a pattern that has stopped matching.
5. **Write a report, not changes.** The audit lists what it found and stops. It does
   not change code unless the reader asks.

That is enough for a useful first audit. The template below turns these five steps
into a file you can adapt.

---

## A copyable audit template

Copy this, rename it, and fill in the parts in brackets.

```markdown
# [problem-name] audit

Finds [one sentence: the single problem this looks for].

## Search

Run this from the project root (paths assume `lib/`; change them if your source
lives elsewhere):

    rg -n '[your pattern]' lib -g '*.dart'

Each result is a possible case, not a finding.

## Decide

For each result, read the surrounding lines and keep it only if [the rule that makes
it a real problem]. Skip [the things that look similar but are not the problem].

Finding nothing means [what a clean result tells you].

## Report

List each kept result as `file:line` with a one-line quote and a short reason.
Do not change any code. Produce a report only.

## Not reported (if any)

- [case]: [why it was skipped or was already decided]
```

---

## Making an audit trustworthy

Once the first version works, these steps keep its findings honest.

- **Check the behaviour in the code, not in a summary.** A comment or a document is
  a lead. Open the code and check it. A comment that says a stream "swallows errors"
  is not proof that it does.
- **Show the problem can happen.** Something that looks wrong is not a finding until
  you can say what inputs or state reach it. If a guard or an early return means it
  cannot happen, leave it.
- **Allow for other safeguards.** A gap in the app that a server rule or a database
  limit already stops is minor. Grade it that way.
- **Keep the evidence.** Each finding names a `file:line` you read and a one-line
  quote. If there is no quote, it is not a finding.
- **Treat locked and generated files as blockers.** Note any file the project marks
  as locked, generated, or do-not-edit, and report it as a blocker rather than a
  finding.

If the project uses GitHub and you have the GitHub CLI installed, check closed
issues:

```bash
gh issue list --state closed --search "<feature-or-pattern> in:title,body" --limit 20
```

In any project, check recent Git history:

```bash
git log --oneline -15 -- "<path>"
```

Read the most relevant closed item in full, comments included. Treat won't-fix,
no-action, and by-design items as out of scope, and list them. Only raise one again
if you have new evidence that the earlier decision was wrong.

---

## Improving an audit over time

These are extra steps. A good first audit does not need them.

- **Turn a pattern into a check only after it holds up twice.** One result is just
  one example. Trust a pattern once it holds on two or more separate places with no
  false match.
- **Write down the false matches you met, and why.** Those "do not flag" notes are
  what stop the next run from raising them again.
- **Prefer exact API names to broad words.** Matching `archive` for compression
  returned 125 results, almost all of them the ordinary word "archived". Match
  `GZipCodec`, `gzip.`, or `.deflate(` instead.
- **Let a model judge what a pattern cannot.** A model's judgement is fine, but each
  finding it makes must quote the line it is based on, and a later step must re-read
  that line and drop anything that does not hold. If the model keeps finding
  something the patterns miss, add a pattern for it. If a pattern keeps needing
  judgement, move that part to the model with a required quote.
- **Cover your own conventions.** Your app has shared parts a general audit cannot
  know about: a design system, a data layer, a house widget. Add your own check for
  them. Pick the one thing everyone is meant to use, and search for the plain form it
  replaces. Write the search so it does not also match the wrapper itself
  (`\bText\(` when you have `AppText`, so `AppText(` and `RichText(` are left out; or
  a direct SDK call when you have a wrapper). Record a result only outside the file
  that defines that shared part. Finding nothing means everyone is using it.

### Optional: record a starting count

Part of a check's value is the number: "operator == on a widget should be 0, so any
result is worth a look." But the right starting count is your project's, not the
author's. This step is optional; skip it until you want numbers you can track over
time.

```bash
{
  echo "opacity=$(rg -c --no-filename '\bOpacity\(' lib -g '*.dart' | awk '{s+=$1} END{print s+0}')"
  echo "widget_eq=$(
    rg -l 'extends (StatelessWidget|StatefulWidget)' lib -g '*.dart' |
      while IFS= read -r file; do rg -l 'operator ==' "$file"; done | wc -l | tr -d ' '
  )"
} > .audit-baseline
```

After that, compare against `.audit-baseline` and report on a change from it,
rather than an absolute number that only meant something in another project.

---

## Packaging: one file that runs anywhere

The body of an audit is instructions plus a few short shell commands, so it runs
anywhere.

- Use plain `rg`, `grep`, and `dart` commands. Describe what to read, not which
  button to press.
- The way you run it is a thin wrapper. Slash-command tools want a one-line
  `description` in the small block at the top of the file; a chat model just needs
  the body pasted in. Keep that top block small so the same file works in both.
- Assume `lib/` for paths, but say so, so a reader with a different layout knows what
  to change.

---

## Checklist for a new audit

- [ ] Covers one problem, with a pattern, a rule, and a note on what finding nothing means
- [ ] Each possible case is checked in context before it becomes a finding
- [ ] Every model finding quotes a line that gets re-read
- [ ] Has a "do not flag" list for the things that look similar
- [ ] Reports only and does not edit; a "Not reported" section lists what it
      skipped (out-of-scope look-alikes and past decisions)
- [ ] Checks past decisions before flagging
- [ ] The body works in any tool and states the default paths
- [ ] The starting count, if used, comes from the reader's project, not fixed numbers
