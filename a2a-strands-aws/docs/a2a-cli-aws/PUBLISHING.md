# Where this article is

| Destination | State |
|---|---|
| dev.to (`aws-builders`, 2794) | draft created 2026-11-05 | id `4983339`, https://dev.to/aws-builders/the-a2a-cli-on-aws-one-client-for-lightsail-bedrock-agentcore-and-localhost-4ag2-temp-slug-4062625 (the slug changes on publish) |
| Medium, Substack, Builder Center, LinkedIn | not created |

Kit: `~/publishing-kit/skills/publishing/scripts/`.

- Checks: `preflight.py docs/a2a-cli-aws/devto-a2a-cli-aws.md --live`
- Update the draft from source: `publish-devto.py --update 4983339 docs/a2a-cli-aws/devto-a2a-cli-aws.md`
- Go live: `publish-devto.py --publish 4983339`, then confirm with `--list`; fill `devto-aws` in `devto-a2a-cli-aws.links.txt` with the public URL
- Medium/Substack: `make-medium.py devto-a2a-cli-aws.md medium`, commit and push `medium/img`
- Cover: `python3 make-cover.py` (textless, content-addressed)
- Figures: `scripts/summarize-results.py > results/summary-20261105.txt`; `evidence/` links every cited file
