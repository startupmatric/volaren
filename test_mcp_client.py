"""
Minimal MCP client — connects to mcp_server/server.py via stdio
and calls tools, exactly like the Inspector or Claude Desktop would.
"""

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server/server.py"],
        env=None,
    )

    print("Starting MCP server as subprocess...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Handshake OK")

            tools = await session.list_tools()
            print(f"\nTools available: {len(tools.tools)}")
            for t in tools.tools:
                print(f"  - {t.name}")

            print("\nCalling get_portfolio_summary({portfolio_id: 1})...")
            result = await session.call_tool(
                "get_portfolio_summary",
                {"portfolio_id": 1},
            )

            for content in result.content:
                if hasattr(content, "text"):
                    print("\nResponse:")
                    print(content.text)

            for name in [
                "get_portfolio_movers",
                "get_portfolio_sectors",
                "get_portfolio_history",
                "get_portfolio_changes",
            ]:
                print(f"\n=== {name} ===")
                r = await session.call_tool(name, {"portfolio_id": 1})
                for c in r.content:
                    if hasattr(c, "text"):
                        print(c.text[:300])


if __name__ == "__main__":
    asyncio.run(main())
