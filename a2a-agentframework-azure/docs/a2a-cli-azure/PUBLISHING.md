# Where this article is

| Destination | State |
|---|---|
| dev.to (personal account, no org: the Azure subject fits neither `gde` nor `aws-builders`) | **published** 2026-11-06, id `4989681`: https://dev.to/xbill/the-a2a-cli-on-azure-one-client-for-container-apps-agent-framework-and-localhost-4b6k |
| Medium | not started |
| Substack | not started |
| AWS Builder Center | SKIP (Azure article) |
| LinkedIn | not started |

Kit: `~/.claude/skills/publishing/scripts/`.

- Checks: `preflight.py docs/a2a-cli-azure/devto-a2a-cli-azure.md --live`
- Update the draft from source: `publish-devto.py --update 4989681 docs/a2a-cli-azure/devto-a2a-cli-azure.md`
- Go live: `publish-devto.py --publish 4989681`, then confirm with `--list`; fill `devto` in `devto-a2a-cli-azure.links.txt` with the public URL
- Medium/Substack: `make-medium.py devto-a2a-cli-azure.md medium`, commit and push `medium/img`
- Cover: `make-cover.py --out devto-cover.jpg --mode devto --no-text --flow --source "a2a|cli" --dest "rust|local|blue" --dest "coordinator|local|orange" --dest "rust|container apps|blue" --dest "coordinator|container apps|orange" --content-address`
- Figures: `scripts/summarize-results.py > results/summary-20261106.txt`; `evidence/` links every cited file
- The Azure resources were torn down on 2026-11-06 (`results/teardown-20261106.txt`); the hostnames in the article no longer resolve.
