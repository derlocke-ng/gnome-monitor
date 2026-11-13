---
name: kiwi-docs
description: Write or update the README.md and the docs/ folder of a Kiwi Network repository (kiwi-server, kiwi-updater, kiwi-proxy, armory, kiwi-framework and the other kiwi tools) so that they are accurate, read plainly, and can be pulled into the documentation on kiwi-network.eu. Use whenever you create or change a README or anything under docs/, document a new feature, prepare a release, or are asked to "write the docs" for a Kiwi tool.
---

# Kiwi docs

Every Kiwi Network repository documents itself in two places:

- **`README.md`**: the front door on GitHub. Short. It says what the tool is,
  who it is for, how to install it, how to start, and where the rest is.
- **`docs/`**: everything else, as Markdown pages. kiwi-network.eu pulls this
  folder at the repository's **latest release tag** and shows it under the
  tool's overview page. What you write here is what users read on the site.

The rules below make both of them correct, plain, and fit for the site. Read
the reference pages before you write:

| Read | When |
|---|---|
| [reference/voice.md](reference/voice.md) | always: how the text has to sound |
| [reference/facts.md](reference/facts.md) | always: how to check every claim against the code |
| [reference/readme.md](reference/readme.md) | when you touch `README.md` |
| [reference/docs-folder.md](reference/docs-folder.md) | when you touch anything in `docs/` |

Templates: [templates/README.md](templates/README.md),
[templates/docs/README.md](templates/docs/README.md),
[templates/docs/kiwi-docs.yml](templates/docs/kiwi-docs.yml).

## Workflow

1. **Read the code before you write a word.** Make a fact list with file and
   line for each item: commands and options, defaults, file paths, supported
   systems, versions, dependencies, limits, what runs as root, what is
   planned. The README and the docs only say what is on that list.
   [reference/facts.md](reference/facts.md) says how.
2. **Sort the facts.** The README gets what a newcomer needs in the first five
   minutes. Everything else goes to a page in `docs/`, one page per task or
   topic (install, use, configure, security, writing a plugin, development …).
   A fact lives in one place; other places link to it.
3. **Write** in the Kiwi voice ([reference/voice.md](reference/voice.md)):
   start with what the thing is for, say literally what happens, full
   sentences, terms explained where they first appear, no hype, limits and
   status words stated exactly.
4. **Check** every sentence against the fact list. Anything you cannot back
   with code, a test or a changelog entry comes out or is marked as it is
   (planned, designed, untested). Claim "tested on X" only if CI or you ran it.
5. **Run the checker** from the repository root and fix every error:

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/check-docs.py .
   ```

   It checks the README's shape, the `docs/` layout and `kiwi-docs.yml`,
   every relative link and anchor, headings, and common style slips, and it
   warns when kiwi-network has a newer version of this guide. When this skill
   is a copy inside the repository, the same script is at
   `.claude/skills/kiwi-docs/scripts/check-docs.py`.
6. **Reread as a stranger.** Read the README and each page you changed from
   top to bottom as someone who has never seen the project. Rewrite whatever
   makes you stumble.
7. **Report what kiwi-network needs to know.** kiwi-network keeps a short,
   translated overview page for each tool (what it is, who it is for, the
   current release, supported systems, install). If your change alters any of
   those facts, say so in your final message and in the pull request, so the
   overview can be updated. Your `docs/` pages reach the site by themselves
   with the next release tag.

## Keeping this guide current

The source of this guide is
`plugins/kiwi-docs/skills/kiwi-docs/` in
[derlocke-ng/kiwi-network](https://github.com/derlocke-ng/kiwi-network). Tool
repositories carry a copy in `.claude/skills/kiwi-docs/`, because cloud
sessions load skills from the repository but not plugins. The checker warns
when the copy is older than the source. To update the copy, run from the
repository root:

```bash
tmp=$(mktemp -d) && git clone -q --depth 1 https://github.com/derlocke-ng/kiwi-network "$tmp" \
  && rm -rf .claude/skills/kiwi-docs && mkdir -p .claude/skills \
  && cp -r "$tmp/plugins/kiwi-docs/skills/kiwi-docs" .claude/skills/ && rm -rf "$tmp"
```

If the repository's `.gitignore` excludes `.claude/`, the copy is never
committed. Replace that line with `.claude/*` and `!.claude/skills/`; the
checker reports this case as an error.

Do not edit the copy by hand. Change the source in kiwi-network and bump its
`VERSION`.
