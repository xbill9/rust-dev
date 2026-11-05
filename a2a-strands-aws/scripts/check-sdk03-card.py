#!/usr/bin/env python3
"""Fetch an agent card with the a2a-sdk 0.3 Python client (the one Strands uses).

  scripts/check-sdk03-card.py http://localhost:8204   # Rust agent, A2A 1.0
  scripts/check-sdk03-card.py http://localhost:8209   # Strands coordinator, A2A 0.3

Prints the card's name and protocol version, or the client's validation error.
"""

import asyncio
import importlib.metadata
import sys

import httpx
from a2a.client import A2ACardResolver


async def main(url: str) -> int:
    print(f"a2a-sdk {importlib.metadata.version('a2a-sdk')}, card from {url}")
    async with httpx.AsyncClient(timeout=30) as h:
        try:
            card = await A2ACardResolver(h, url).get_agent_card()
        except Exception as e:  # noqa: BLE001 - report whatever the client raises
            print(f"{type(e).__name__}: {str(e)[:400]}")
            return 1
    print(f"ok: {card.name}, protocolVersion {card.protocol_version}, url {card.url}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8204")))
