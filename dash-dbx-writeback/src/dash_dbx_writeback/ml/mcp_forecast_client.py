"""MCP (Model-Context-Protocol) client that connects to a *forecast MCP server*
via stdio and lets you ask natural-language questions about forecast results.

This script follows the official quick-start instructions at
https://modelcontextprotocol.io/quickstart/client .  It is intentionally kept
minimal so it can double as a reference implementation.

USAGE
-----
$ python -m dash_dbx_writeback.ml.mcp_forecast_client path/to/mcp_forecast_server.py

Then type questions such as:
    › Which premium Confectionery items are forecast above 300 units?

Type ``quit`` to exit.
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import AsyncExitStack
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()


class MCPForecastClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()

    async def connect(self, server_script: str):
        is_py = server_script.endswith(".py")
        is_js = server_script.endswith(".js")
        if not (is_py or is_js):
            raise ValueError("Server script must be .py or .js")

        command = "python" if is_py else "node"
        server_params = StdioServerParameters(command=command, args=[server_script], env=None)
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()

        resp = await self.session.list_tools()
        self.tools = resp.tools
        print("Connected. Tools:", [t.name for t in self.tools])

    async def process_query(self, query: str) -> str:
        """Send query to Claude with tool descriptions; execute tool calls."""
        msgs = [{"role": "user", "content": query}]
        tool_desc = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema,
            }
            for t in self.tools
        ]

        # initial call
        resp = self.anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=msgs,
            tools=tool_desc,
        )

        out_lines = []
        for part in resp.content:
            if part.type == "text":
                out_lines.append(part.text)
            elif part.type == "tool_use":
                result = await self.session.call_tool(part.name, part.input)
                out_lines.append(f"[tool {part.name}→ OK]")
                msgs.extend(
                    [
                        {"role": "assistant", "content": resp.content},
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
                resp = self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1000,
                    messages=msgs,
                    tools=tool_desc,
                )
                out_lines.append(resp.content[0].text)
        return "\n".join(out_lines)

    async def chat_loop(self):
        print("Type your query (quit to exit):")
        while True:
            q = input("› ").strip()
            if q.lower() in {"quit", "exit"}:
                break
            ans = await self.process_query(q)
            print(ans)

    async def close(self):
        await self.exit_stack.aclose()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python -m dash_dbx_writeback.ml.mcp_forecast_client path/to/mcp_server.py")
        sys.exit(1)
    server_path = sys.argv[1]
    cli = MCPForecastClient()
    try:
        await cli.connect(server_path)
        await cli.chat_loop()
    finally:
        await cli.close()


if __name__ == "__main__":
    asyncio.run(main()) 