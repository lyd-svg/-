"""
MCP Server 工具测试脚本
自动启动 MCP Server -> 测试所有工具 -> 关闭服务
"""
import asyncio
import subprocess
import sys
import os
import time
import urllib.request
from mcp import ClientSession
from mcp.client.sse import sse_client

PORT = 18765
SERVER_URL = f"http://127.0.0.1:{PORT}/sse"


async def wait_for_server(timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = urllib.request.urlopen(SERVER_URL, timeout=2)
            if r.status == 200:
                return True
        except Exception:
            await asyncio.sleep(0.5)
    return False


async def test_all_tools():
    proc = subprocess.Popen(
        [sys.executable, "-c", f"""
import sys
sys.path.insert(0, {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))!r})
import uvicorn
from mcp_db_server import mcp
uvicorn.run(mcp.sse_app(), host='0.0.0.0', port={PORT})
"""],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    print(f"[MCP Server starting on port {PORT}]...", end=" ", flush=True)
    ready = await wait_for_server(timeout=10)
    if not ready:
        print("[FAILED]")
        proc.kill()
        return
    print("[OK]")
    print()

    try:
        async with sse_client(SERVER_URL) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # list tools
                tools_result = await session.list_tools()
                tools = {t.name: t for t in tools_result.tools}
                print(f"Found {len(tools)} tools:")
                print()
                for name, t in tools.items():
                    props = t.inputSchema.get("properties", {}) if t.inputSchema else {}
                    params = ", ".join(f"{k}" for k in props.keys())
                    print(f"  * {name}({params})")
                    print(f"    {t.description}")
                print()
                print("=" * 60)
                print()

                # test each tool
                tests = [
                    ("get_tables", "get_tables()", {}),
                    ("get_schema", 'get_schema(table_name="users")', {"table_name": "users"}),
                    ("get_schema", "get_schema() [all tables]", {}),
                    ("get_schema_markdown", "get_schema_markdown()", {}),
                    ("get_sample_data", 'get_sample_data(table_name="orders", limit=3)', {"table_name": "orders", "limit": 3}),
                    ("query_sql", "query_sql(user level stats)", {
                        "sql": "SELECT 用户等级, COUNT(*) AS 人数 FROM users GROUP BY 用户等级 ORDER BY 人数 DESC"
                    }),
                    ("get_table_stats", 'get_table_stats(table_name="orders")', {"table_name": "orders"}),
                ]

                for tool_name, label, args in tests:
                    print(f">> {label}")
                    result = await session.call_tool(tool_name, args)
                    text = result.content[0].text if result.content else "(empty)"
                    if len(text) > 800:
                        print(text[:800])
                        print("... (truncated)")
                    else:
                        print(text)
                    print("=" * 60)
                    print()

                print("[All tests passed]")

    finally:
        proc.kill()
        proc.wait()
        print("[MCP Server stopped]")


if __name__ == "__main__":
    asyncio.run(test_all_tools())
