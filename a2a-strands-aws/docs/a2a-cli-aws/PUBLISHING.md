# Where this article is

| Destination | State |
|---|---|
| dev.to (`aws-builders`, 2794) | **published** 2026-11-05, id `4983339`: https://dev.to/aws-builders/the-a2a-cli-on-aws-one-client-for-lightsail-bedrock-agentcore-and-localhost-o69 |
| Medium | **published** 2026-11-05, Notify on, no paywall (`isSubscriptionLocked: false`): https://medium.com/@xbill999/the-a2a-cli-on-aws-one-client-for-lightsail-bedrock-agentcore-and-localhost-4b220d778b33 |
| Substack (xbill9) | **published** 2026-11-05 and emailed (`email_sent_at` 18:42:16Z): https://xbill9.substack.com/p/the-a2a-cli-on-aws-one-client-for |
| AWS Builder Center | **published** 2026-11-05: https://builder.aws.com/content/3LhRgOSkTc8n2rMhcyO9J8g4M8F/the-a2a-cli-on-aws-one-client-for-lightsail-bedrock-agentcore-and-localhost (from `builder-a2a-cli-aws.md`; cover `builder-cover.428e9189.jpg`; tags amazon-bedrock-agentcore, amazon-lightsail, amazon-bedrock, agentic-ai, rust; saved preview read back: 34 code blocks, 3 tables, 10 links) |
| LinkedIn | **posted** 2026-11-05 with the cover: https://www.linkedin.com/feed/update/urn:li:activity:7524183996034043905/ |
| AWS Community Builders Slack | posted 2026-11-05 in `#boost-ai-engineering` by the author, from `slack-a2a-cli-aws.txt` with the dev.to cover attached |

Substack paste note: the References item `https://strandsagents.com/` (link text equal to a bare root URL) was saved as a plain paragraph outside the list, link dropped. The draft was re-pasted with that anchor's text set to `strandsagents.com`; the href is unchanged.

Kit: `~/publishing-kit/skills/publishing/scripts/`.

- Checks: `preflight.py docs/a2a-cli-aws/devto-a2a-cli-aws.md --live`
- Update the draft from source: `publish-devto.py --update 4983339 docs/a2a-cli-aws/devto-a2a-cli-aws.md`
- Go live: `publish-devto.py --publish 4983339`, then confirm with `--list`; fill `devto-aws` in `devto-a2a-cli-aws.links.txt` with the public URL
- Medium/Substack: `make-medium.py devto-a2a-cli-aws.md medium`, commit and push `medium/img`
- Cover: `python3 make-cover.py` (textless, content-addressed); Builder Center 1200x675: `python3 make-builder-cover.py`
- Builder Center body: `make-builder.py devto-a2a-cli-aws.md --out builder-a2a-cli-aws.md --title ... --subtitle ...`
- Figures: `scripts/summarize-results.py > results/summary-20261105.txt`; `evidence/` links every cited file
