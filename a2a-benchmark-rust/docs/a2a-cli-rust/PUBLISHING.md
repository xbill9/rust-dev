# Where this article is

| Destination | State | Id / URL |
|---|---|---|
| dev.to (`gde`, 11939) | published 2026-11-04 | id `4972235`, https://dev.to/gde/the-a2a-cli-and-rust-the-same-code-three-ways-to-serve-it-4el0 |
| Medium | built, not posted | paste `medium/devto-a2a-cli-rust-hosted.html`; type the title by hand |
| Substack | built, not posted | same hosted HTML through `ss.prepare()` (kit `references/substack.md`) |

Kit: `~/publishing-kit/skills/publishing/scripts/`.

- Update the draft from source: `publish-devto.py --update 4972235 docs/a2a-cli-rust/devto-a2a-cli-rust.md`
- `--update` on a live article: confirm with `--list` that it is still published afterwards
- Rebuild Medium/Substack after any edit: `make-medium.py devto-a2a-cli-rust.md medium`, commit and push `medium/img`
- Checks: `preflight.py docs/a2a-cli-rust/devto-a2a-cli-rust.md --live`
