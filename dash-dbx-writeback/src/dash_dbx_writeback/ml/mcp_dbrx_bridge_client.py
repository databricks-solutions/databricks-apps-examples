"""Databricks-AI-Bridge MCP reference client.

This script demonstrates how to consume an MCP server that was published with
`databricks-ai-bridge` (https://github.com/databricks/databricks-ai-bridge).
It mirrors the logic in *mcp_forecast_client.py* but delegates transport &
message formatting to the bridge's higher-level helper classes so you write
very little glue code.

NOTE  The `databricks-ai-bridge` Python package is still in rapid evolution. If
your installed version ships the MCP helpers under a different import path,
edit the two import lines marked "🔧" below.
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import AsyncExitStack
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv

# 🔧 These two imports come from the AI-Bridge project
from databricks_ai_bridge.mcp.client import BridgeClientSession
from databricks_ai_bridge.mcp.client.stdio import bridge_stdio_client

load_dotenv()


class DbrxBridgeClient:
    """Simple interactive CLI that proxies questions to Claude + MCP server."""

    def __init__(self):
        self.session: Optional[BridgeClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()

    async def connect(self, server_script: str):
        command = "python" if server_script.endswith(".py") else "node"
        client_transport = await self.exit_stack.enter_async_context(
            bridge_stdio_client(command=command, args=[server_script])
        )
        self.session = await self.exit_stack.enter_async_context(
            BridgeClientSession(*client_transport)
        )
        await self.session.initialize()
        tools = await self.session.list_tools()
        self.tools = tools.tools
        print("Connected (bridge). Tools:", [t.name for t in self.tools])

    async def ask(self, question: str) -> str:
        msgs = [{"role": "user", "content": question}]
        available_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.inputSchema}
            for t in self.tools
        ]
        reply = self.anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=800,
            messages=msgs,
            tools=available_tools,
        )
        final = []
        for part in reply.content:
            if part.type == "text":
                final.append(part.text)
            elif part.type == "tool_use":
                result = await self.session.call_tool(part.name, part.input)
                final.append(f"[tool {part.name} executed]")
                msgs.extend(
                    [
                        {"role": "assistant", "content": reply.content},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": part.id,
                                    "content": result.content,
                                }
                            ],
                        },
                    ]
                )
                reply = self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=800,
                    messages=msgs,
                    tools=available_tools,
                )
                final.append(reply.content[0].text)
        return "\n".join(final)

    async def loop(self):
        print("Ask a question (quit to exit):")
        while True:
            q = input("» ").strip()
            if q.lower() in {"quit", "exit"}:
                break
            ans = await self.ask(q)
            print(ans)

    async def close(self):
        await self.exit_stack.aclose()


async def _main():
    if len(sys.argv) < 2:
        print("Usage: python -m dash_dbx_writeback.ml.mcp_dbrx_bridge_client path/to/server.py")
        sys.exit(1)
    server = sys.argv[1]
    client = DbrxBridgeClient()
    try:
        await client.connect(server)
        await client.loop()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(_main()) 