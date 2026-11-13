# Checking the facts

Docs that are wrong are worse than no docs. Every page on kiwi-network.eu was
once checked against the code of its repository, and many claims did not
survive: a feature listed as planned that had shipped, a group name that only
fits one distribution, an install path that skipped a step, a system that had
never been tested. Check before you write, and again before you commit.

## Build a fact list first

Go through the code, not the old README. For each item, note the file and line:

- **Commands and options**: the real names, arguments and defaults (read the
  argument parser, `--help` output, the man page if there is one).
- **Files and paths** the tool reads and writes, and their permissions.
- **What runs as root**, what asks for a password, what opens a port.
- **Supported systems**: what CI tests (read the workflow files), what the
  installer checks for, what you tested yourself. Nothing else counts.
- **Versions**: the current release tag, the minimum versions of dependencies
  the code enforces.
- **Limits**: what the code refuses or does not handle (IPv6, UDP, ARM, a
  single configuration …).
- **Status**: what is merged and released, what is only on a branch, what is
  planned (an issue, a roadmap file) and what is only an idea.

## Rules

- **Code beats prose.** When the README, a comment, a template or the changelog
  disagree with the code, the code is right. Fix the others in the same change.
- **Released beats merged.** The site shows `docs/` at the latest release tag.
  Describe what that tag does. A feature that is merged but not released is
  either left out or marked "in the next release".
- **No guessing.** If you cannot establish what something does, say less, ask,
  or leave it out. Never fill a gap with what the tool probably does.
- **"Tested on" means tested.** Only name systems that CI or you ran the real
  thing on. Everything else is "not tested yet".
- **Planned means planned.** Only call something planned if there is a decision
  (a roadmap entry, an issue, the owner said so). An idea is not a plan; leave
  it out.
- **Say each fact once.** Put it on one page and link to it from others, so it
  cannot be updated in one place and forgotten in another.
- **Dates and numbers exactly**: versions as tags (`v2.5.1`), sizes with units,
  defaults as the code has them.

## Before you commit

1. Reread every changed sentence next to the fact list.
2. Run every command you show, or at least `--help` for its options, where the
   environment allows.
3. Run `scripts/check-docs.py`.
4. In the commit message or pull request, list what you checked and how, and
   anything you could not check.
