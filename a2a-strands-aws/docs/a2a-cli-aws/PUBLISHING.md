# Where this article is

| Destination | State |
|---|---|
| dev.to | not created (source: `devto-a2a-cli-aws.md`, `published: false`) |
| Medium, Substack, Builder Center, LinkedIn | not created |

Kit: `~/publishing-kit/skills/publishing/scripts/`.

- Checks: `preflight.py docs/a2a-cli-aws/devto-a2a-cli-aws.md --live`
- dev.to draft: `publish-devto.py --create docs/a2a-cli-aws/devto-a2a-cli-aws.md --org-slug aws-builders` (AWS piece)
- Medium/Substack: `make-medium.py devto-a2a-cli-aws.md medium`, commit and push `medium/img`
- Cover: `python3 make-cover.py` (textless, content-addressed)
- Figures: `scripts/summarize-results.py > results/summary-20261105.txt`; `evidence/` links every cited file
