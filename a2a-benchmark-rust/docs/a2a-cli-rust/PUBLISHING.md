# Where this article is

| Destination | State | Id / URL |
|---|---|---|
| dev.to (`gde`, 11939) | published 2026-11-04 | id `4972235`, https://dev.to/gde/the-a2a-cli-and-rust-the-same-code-three-ways-to-serve-it-4el0 |
| Medium | published 2026-11-04, no paywall, 240 subscribers notified | https://xbill999.medium.com/the-a2a-cli-and-rust-the-same-code-three-ways-to-serve-it-6f06bcf76f68 (id 6f06bcf76f68; (135 blocks, 21 headings, 26 code blocks, 9 images, checked from `?format=json`) |
| Substack | published 2026-11-04 01:15 UTC, emailed | https://xbill9.substack.com/p/the-a2a-cli-and-rust-the-same-code (post 223410921; (21 headings, 26 code blocks, 9 images, 9 links, checked with `ss.audit()`) |
| LinkedIn | posted 2026-11-04 with the cover | https://www.linkedin.com/feed/update/urn:li:activity:7523554207636013056/ (`linkedin-devto-a2a-cli-rust.txt`, template `linkedin.template.txt`) |

Kit: `~/publishing-kit/skills/publishing/scripts/`.

- Update the draft from source: `publish-devto.py --update 4972235 docs/a2a-cli-rust/devto-a2a-cli-rust.md`
- `--update` on a live article: confirm with `--list` that it is still published afterwards
- Rebuild Medium/Substack after any edit: `make-medium.py devto-a2a-cli-rust.md medium`, commit and push `medium/img`
- Checks: `preflight.py docs/a2a-cli-rust/devto-a2a-cli-rust.md --live`

Publishing the Substack post emails subscribers by default; `ss.publish()` needs an explicit `email:` answer. On Medium, set topics after publishing: the topic field sits in the publish dialog. Fill `medium` and `substack` in `devto-a2a-cli-rust.links.txt` with the public URLs once live.
