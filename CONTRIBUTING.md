# Contributing

This guide is for people who want to write new audits, or improve the ones here.
New audits and improvements are welcome.

My aim is to share the audits I use to keep my Flutter and Dart code tidy and in
line with current good practice.

**Before you write an audit, read [`AUTHORING.md`](AUTHORING.md).** It explains how
these audits are meant to work. An audit that only matches a text pattern, without
a rule for judging each match and a step to check it, produces findings that do not
hold up.

What a new audit needs:

- **It is about Dart, Flutter, or Firebase.** These audits are for that stack, not
  a general code checker for any language.
- **Every check has three parts:** a search pattern, a rule for deciding whether a
  match is a real problem, and a note on what it means when the search finds
  nothing. A plain match is never a finding on its own.
- **The starting count comes from the reader's own project,** not fixed numbers
  from yours.
- **It only reports.** No changes to code without the user's approval.
- **It has a "do not flag" list** of the false matches you met while testing it.
  Add a pattern to this list only after it holds up on two or more projects.
- **The body works in any AI agent.** Use plain `rg` and `dart` commands and state
  the default paths. Do not put editor-, CI-, or agent-specific commands in the
  audit text.

If your audit ships a script, give it a `--self-test` and run it before you submit.
Try a new audit on at least one real project before you share it.

By contributing, you agree that your work is shared under
[CC BY-NC 4.0](LICENSE).
