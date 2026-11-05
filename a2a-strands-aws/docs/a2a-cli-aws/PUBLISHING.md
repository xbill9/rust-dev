# Where this article is

| Destination | State |
|---|---|
| dev.to (`aws-builders`, 2794) | **published** 2026-11-05, id `4983339`: https://dev.to/aws-builders/the-a2a-cli-on-aws-one-client-for-lightsail-bedrock-agentcore-and-localhost-o69 |
| Medium | draft `4b220d778b33`, https://medium.com/p/4b220d778b33/edit (title set; 90 blocks, 15 headings, 17 code blocks, 5 re-hosted images, read back from `?format=json`) |
| Substack (xbill9) | draft `223663994`, https://xbill9.substack.com/publish/post/223663994 (title + subtitle set; 15 h3, 17 code blocks, 5 re-hosted images, 10 link targets, read back with `ss.audit()`) |
| Builder Center, LinkedIn | not created |

Substack paste note: the References item `https://strandsagents.com/` (link text equal to a bare root URL) was saved as a plain paragraph outside the list, link dropped. The draft was re-pasted with that anchor's text set to `strandsagents.com`; the href is unchanged.

Kit: `~/publishing-kit/skills/publishing/scripts/`.

- Checks: `preflight.py docs/a2a-cli-aws/devto-a2a-cli-aws.md --live`
- Update the draft from source: `publish-devto.py --update 4983339 docs/a2a-cli-aws/devto-a2a-cli-aws.md`
- Go live: `publish-devto.py --publish 4983339`, then confirm with `--list`; fill `devto-aws` in `devto-a2a-cli-aws.links.txt` with the public URL
- Medium/Substack: `make-medium.py devto-a2a-cli-aws.md medium`, commit and push `medium/img`
- Cover: `python3 make-cover.py` (textless, content-addressed)
- Figures: `scripts/summarize-results.py > results/summary-20261105.txt`; `evidence/` links every cited file
