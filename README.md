# Flutter Audit Skills

## About these audits

I am a solo Flutter and Dart developer. I mostly use Firebase as a backend, and I
use AI models to help me while I build. I wrote these ***audits*** to keep my code
tidy and consistent, to follow good practice, and to spot habits I want to drop. I
use AI mainly to review code, not to write it. I run these Markdown audits with
Claude Code, or with OpenCode using local models such as Qwen and Gemma.

I am sharing these audits in case they help other people. Suggestions and
contributions are welcome. If you contribute, you agree that your work is shared
under this repository's CC BY-NC 4.0 licence.

You might call these something else, such as skills or commands. "Audit" is not a
perfect word for every case, but I use it the same way all through this
repository.

- The audits are written in Markdown. That keeps things simple for me, and I hope
  for you too.
- They are written for ***Flutter 3.47*** and ***Dart 3.13***, and I try to keep
  them up to date.
- By default an audit only reports. It writes up what it found and does not change
  your code. The audit itself does not send your code anywhere. But if you run it
  with a cloud model such as Claude, your code goes to that provider as usual. If
  you choose to, an audit can also open a GitHub issue.
- An audit can tell an AI agent what to do, but it cannot control what an outside
  tool does. So always check what your agent and tools are allowed to do before
  you run one.
- Read the audit yourself, and ask your agent to read it too. Make sure it does
  not ask the agent to do anything you do not want.

## How these audits work

Each audit starts by searching your code for possible problems. A search result
is a lead, not a finding. The reviewer then reads the code around it, checks that
the problem really applies, and looks at the project's history and past decisions
before reporting anything.

The aim is a short report backed by evidence, not a long list of guesses. Each
audit looks at one type of problem, and says what evidence you need before you
raise it.

To learn how the audits are built, see [AUTHORING.md](AUTHORING.md).

## How to run an audit

Copy the audit into the right commands folder for your tool. The file name becomes
the command name (for example, `render-perf.md`).

| Tool | Put the file at | Run it |
|---|---|---|
| Claude Code | `.claude/commands/render-perf.md` | `/render-perf` |
| Cursor | `.cursor/commands/render-perf.md` | type `/`, select it |
| OpenCode | `.opencode/commands/render-perf.md` | `/render-perf` |

In Claude Code, a subfolder adds a prefix to the command name
(`.claude/commands/audits/render-perf.md` becomes `/audits:render-perf`). Claude
Code also supports Skills (`.claude/skills/<name>/SKILL.md`). Skills are now the
suggested format for larger, reusable commands, but a plain
`.claude/commands/*.md` file still works.

Other ways to run one:

- Any chat model: paste the audit, then the files you want checked, and ask it to
  follow the steps and write the report.
- Command-line agents (such as Aider): add the `.md` file as context and ask the
  agent to run the audit.

Each audit uses `ripgrep` (`rg`) for its searches, and the Dart analyzer where it
helps. `ref-after-await` also comes with a small Python script for use in CI.

## Audit catalogue

Each audit has its own file with the full method. Here is what each one looks for
and why it matters.

### Performance

**[render-perf](performance/render-perf.md)** finds widgets that cost more to draw
than they need to: an image decoded at full size into a small box, effects such as
fading or clipping used while something moves, or a very long list built all at
once. These are common reasons an app drops frames and feels jerky, especially on
cheaper phones.

**[rebuild-scope](performance/rebuild-scope.md)** finds widgets that redraw a large
part of the screen too often. A common case is a live data feed read at the top of
a big `build` method, so every update redraws everything below it. Redrawing less
keeps scrolling and movement smooth.

**[isolate-offload](performance/isolate-offload.md)** finds heavy work running on
the screen's own thread: reading a large file, decoding image data, hashing, or
compressing. That work blocks the next frame and freezes the app until it
finishes. Moving it to a background thread keeps the app responsive.

### Riverpod

**[ref-after-await](riverpod/ref-after-await.md)** finds a Riverpod `ref` used
after an `await` without first checking the widget is still on screen. If the user
left the screen during the `await`, that line throws an error and crashes. This bug
tends to show up in real use but not in tests.

**[async-state-ui](riverpod/async-state-ui.md)** finds a screen that loads data but
does not handle every outcome: a loading, error, or data branch that is missing or
incomplete. When the load fails, the user is left with a blank screen or a spinner
that never stops, instead of a clear error they can act on.

**[provider-reactivity](riverpod/provider-reactivity.md)** finds `watch` and `read`
used for the wrong situation: a value watched even though it never changes while
the widget is on screen (a redraw for nothing), or one read even though it does
change (a screen that goes stale). It also flags a `watch` inside a callback, which
should be a `read`.

**[di-completeness](riverpod/di-completeness.md)** finds an outside service reached
directly (`.instance`, `.instanceFor(...)`, or a static class) instead of through
its provider. When code reaches the service directly, a test cannot swap in a fake,
so that code is hard to test. Provider files and start-up code are the two places
where reaching it directly is fine.

More audits (architecture, Firestore, Dart habits, testing) will follow.

## Adapting to your codebase

- Paths default to `lib/`. Change them if your code lives somewhere else.
- `render-perf` and `rebuild-scope` assume your analyzer turns on the
  `prefer_const_*` lints (for example through `very_good_analysis` or
  `flutter_lints`), so they do not flag a missing `const`. Add a `const` check if
  yours does not.
- `rebuild-scope` is written for Riverpod, but the idea works with any reactive
  state manager.
- Where an audit relies on a shared piece of your own app, `AUTHORING.md` explains
  how to add a check of your own.

## Licence

[CC BY-NC 4.0](LICENSE): free to use and adapt with credit, but not for commercial
use. See [COMMERCIAL-USE.md](COMMERCIAL-USE.md) for what I think that means for
using them at work.
