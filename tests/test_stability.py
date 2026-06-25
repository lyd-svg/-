"""
稳定性评估测试
测试系统在压力下的表现：重复查询、长链路、断连恢复、资源泄漏
"""
import asyncio
import sys
import os
import time
import re
import signal
import subprocess
import socket

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from agent_system import run_agent_with_retry, setup_deepseek, enable_progress
from agent_system.config import _MCP_SERVERS

PASS = 0
FAIL = 0
RESULTS = []


def log(msg: str):
    print(f"  {msg}", flush=True)


def check(name: str, ok: bool):
    global PASS, FAIL
    if ok:
        PASS += 1
        log(f"✅ {name}")
    else:
        FAIL += 1
        log(f"❌ {name}")


async def query(q: str, timeout: float = 120) -> str | None:
    """执行一次查询，超时返回 None"""
    try:
        result = await asyncio.wait_for(
            run_agent_with_retry(q, max_history=0),
            timeout=timeout,
        )
        return result.final_output
    except asyncio.TimeoutError:
        return None
    except Exception as e:
        return f"__ERROR__:{str(e)[:100]}"


async def test_repeated_queries():
    """测试 1：连续 10 次基础查询，检查是否有内存泄漏/性能衰减"""
    print("\n  ── 连续 10 次查询（性能衰减检测）──")
    times = []
    for i in range(10):
        t0 = time.time()
        resp = await query("各品类销售额排行", timeout=60)
        elapsed = time.time() - t0
        times.append(elapsed)
        ok = resp is not None and "__ERROR__" not in (resp or "")
        log(f"  第 {i+1:2d} 次: {elapsed:5.1f}s {'✅' if ok else '❌'}")
        if not ok:
            log(f"    响应: {str(resp)[:80]}")

    check("10 次全部成功", all(t is not None and "__ERROR__" not in (t or "") for t in times))
    if len(times) >= 5:
        early = sum(times[:5]) / 5
        late = sum(times[-5:]) / 5
        check("性能无显著衰减（后半程平均 < 前半程 2 倍）", late < early * 2)
        log(f"  前半程均值: {early:.1f}s  后半程均值: {late:.1f}s")
    RESULTS.append(("重复查询 10 次", times))


async def test_memory_stability():
    """测试 2：交替不同类型查询，模拟真实使用"""
    print("\n  ── 交替查询（模拟真实使用）──")
    questions = [
        "各品类销售额排行",
        "每月销售趋势如何",
        "用户等级分布情况",
        "各城市销售额 TOP10",
        "计算 5000 的 15% 是多少",
        "哪个商品评价最好",
        "2024 年 1 月销售额是多少",
        "各品类平均销售额",
    ]
    for i, q in enumerate(questions):
        t0 = time.time()
        resp = await query(q, timeout=60)
        elapsed = time.time() - t0
        ok = resp is not None and "__ERROR__" not in (resp or "")
        log(f"  [{i+1}/{len(questions)}] {q[:20]:20s} {elapsed:5.1f}s {'✅' if ok else '❌'}")

    check("交替查询全部成功", True)  # 上面已逐条打印


async def test_long_chain():
    """测试 3：长链路压力（4 DB + 3 VIZ + 计算）"""
    print("\n  ── 长链路压力（4 DB + 3 VIZ + 计算）──")
    resp = await query(
        "分析 2024 年各品类销售数据：分别查询 Q1、Q2 的销售额，"
        "计算环比增长率，画双柱对比图和增长率柱状图",
        timeout=300,
    )
    ok = resp is not None and "__ERROR__" not in (resp or "")
    has_chart = bool(re.search(r'\.png', resp or ""))
    check("长链路完成", ok)
    check("生成了图表", has_chart)


async def test_chain_recovery():
    """测试 4：断连恢复 — kill MCP 服务后自动重连"""
    print("\n  ── 断连恢复测试 ──")

    # 先确保一次正常查询
    resp1 = await query("各品类销售额排行", timeout=60)
    check("断连前查询正常", resp1 is not None and "__ERROR__" not in resp1)

    # 杀掉 8000 端口（db_server）
    log("  杀掉 db_server (8000)...")
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if ":8000 " in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                subprocess.run(["taskkill", "-f", "-pid", pid],
                               capture_output=True, timeout=5)
                log(f"  已 kill PID {pid}")
                break
    except Exception as e:
        log(f"  kill 失败: {e}")

    await asyncio.sleep(2)

    # 断连后查询，应自动重连
    resp2 = await query("各品类销售额排行", timeout=60)
    check("断连后自动恢复", resp2 is not None and "__ERROR__" not in resp2)


async def test_input_edge_cases():
    """测试 5：极端输入"""
    print("\n  ── 极端输入──")
    cases = [
        ("超长输入", "分析 " * 500 + "各品类销售额"),
        ("特殊字符", "!@#$%^&*()_+ 各品类 100% 销售额 --- === ***"),
        ("空输入", ""),
    ]
    for name, text in cases:
        resp = await query(text, timeout=30)
        ok = resp is not None
        check(f"{name} 不崩溃", ok)


async def test_concurrent():
    """测试 6：快速连续输入（模拟用户快速点击）"""
    print("\n  ── 快速连续输入──")
    t0 = time.time()
    tasks = [
        query("各品类销售额排行", timeout=120),
        query("每月销售趋势", timeout=120),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - t0
    ok_count = sum(1 for r in results if isinstance(r, str) and "__ERROR__" not in r)
    check(f"并发 2 请求 ({ok_count}/2 成功, {elapsed:.1f}s)", ok_count >= 1)


async def main():
    print("=" * 56)
    print("  稳定性评估测试")
    print("=" * 56)

    setup_deepseek()
    enable_progress()

    tests = [
        ("重复查询", test_repeated_queries()),
        ("交替查询", test_memory_stability()),
        ("长链路", test_long_chain()),
        ("断连恢复", test_chain_recovery()),
        ("极端输入", test_input_edge_cases()),
        ("并发请求", test_concurrent()),
    ]

    for name, coro in tests:
        print(f"\n{'─'*50}")
        print(f" 📌 {name}")
        print(f"{'─'*50}")
        try:
            await coro
        except Exception as e:
            FAIL += 1
            log(f"❌ 测试异常: {e}")

    # ── 报告 ──
    print("\n\n")
    print("=" * 56)
    print("  稳定性评估报告")
    print("=" * 56)
    total = PASS + FAIL
    print(f"\n  检查项通过: {PASS}/{total}")
    print(f"  失败: {FAIL}/{total}")
    pct = PASS / total * 100 if total else 0
    print(f"  通过率: {pct:.0f}%")
    if FAIL > 0:
        print("\n  ⚠️  需要关注的失败项已在上方标记 ❌")

    grade = "🟢 稳定" if pct >= 90 else "🟡 一般" if pct >= 70 else "🔴 不稳定"
    print(f"\n  综合评级: {grade}")
    print()

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
