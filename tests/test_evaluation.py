"""
系统评估测试：跑 6 个核心场景，输出结构化报告
"""
import asyncio
import sys
import os
import time
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from agent_system import run_agent_with_retry, setup_deepseek, enable_progress

RESULTS = []
FAILURES = []


async def test(name: str, query: str, max_history: int = 0, checks: list = None):
    """运行单个测试并记录结果"""
    print(f"\n{'='*60}")
    print(f"  [{name}]")
    print(f"  查询: {query[:80]}")
    print(f"{'='*60}")

    start = time.time()
    try:
        result = await run_agent_with_retry(query, max_history=max_history)
        elapsed = time.time() - start
        output = result.final_output

        passed_checks = 0
        total_checks = 0
        details = []

        if checks:
            for check_name, check_fn in checks:
                total_checks += 1
                ok = check_fn(output)
                details.append((check_name, ok))
                if ok:
                    passed_checks += 1

        status = "✅" if (not checks or passed_checks == total_checks) else "⚠️"
        print(f"  耗时: {elapsed:.1f}s")
        print(f"  状态: {status}")
        for chk_name, ok in details:
            print(f"    {'✅' if ok else '❌'} {chk_name}")

        RESULTS.append({
            "name": name, "query": query, "elapsed": elapsed,
            "output_preview": output[:200], "checks": details,
            "passed": not checks or passed_checks == total_checks,
        })
        return result

    except Exception as e:
        elapsed = time.time() - start
        print(f"  耗时: {elapsed:.1f}s")
        print(f"  状态: ❌ 异常: {str(e)[:100]}")
        FAILURES.append({"name": name, "error": str(e)})
        RESULTS.append({
            "name": name, "query": query, "elapsed": elapsed,
            "output_preview": f"ERROR: {str(e)[:100]}",
            "checks": [], "passed": False,
        })
        return None


def has_chart_path(output: str) -> bool:
    """检查输出是否包含图表路径"""
    return bool(re.search(r'\.png', output))


def has_error(output: str) -> bool:
    """检查输出是否包含错误提示"""
    errors = ["错误", "失败", "超时", "未找到", "异常"]
    return any(e in output for e in errors)


def has_table(output: str) -> bool:
    """检查输出是否包含 Markdown 表格"""
    return "|" in output and "---" in output


def has_markdown_image(output: str) -> bool:
    """检查输出是否包含 ![]() 图片标记"""
    return bool(re.search(r'!\[.*\]\(.*\)', output))


def no_data_empty(output: str) -> bool:
    """检查不包含'数据为空'"""
    return "数据为空" not in output


def no_please_provide(output: str) -> bool:
    """检查 VIZ 没有向用户要数据"""
    return "请提供数据" not in output and "把数据" not in output


async def main():
    print("=" * 60)
    print("  多智能体数据分析系统 — 评估测试")
    print("=" * 60)

    setup_deepseek()
    enable_progress()

    # ── 测试1: 基础查询 ──
    await test(
        "基础查询",
        "各品类销售额排行",
        checks=[
            ("返回了数据表格", lambda o: has_table(o) or "品类" in o),
            ("没有报错", lambda o: not has_error(o)),
            ("有具体数值", lambda o: bool(re.search(r'\d+', o))),
        ],
    )

    # ── 测试2: 查询 + 画图 ──
    await test(
        "查询+画图",
        "各品类销售额排行，画成柱状图",
        checks=[
            ("生成了图表文件", has_chart_path),
            ("VIZ 没有要数据", no_please_provide),
            ("没有报错", lambda o: not has_error(o)),
        ],
    )

    # ── 测试3: 多步链路（Q1Q2对比+增长率+双图）──
    await test(
        "多步链路",
        "对比 2024 年 Q1 和 Q2 的品类销售额，计算每个品类的环比增长率，画双柱状对比图，再画一张增长率柱状图",
        max_history=0,
        checks=[
            ("至少生成一张图", has_chart_path),
            ("没有报错", lambda o: not has_error(o)),
            ("不是数据为空", no_data_empty),
        ],
    )

    # ── 测试4: 知识库检索 ──
    await test(
        "知识库检索",
        '查一下知识库里有关于"电商"的资料',
        checks=[
            ("返回了内容", lambda o: len(o) > 50),
            ("没有报错", lambda o: not has_error(o)),
        ],
    )

    # ── 测试5: 纯计算 ──
    await test(
        "数值计算",
        "计算 15000 除以 12000 的百分比",
        checks=[
            ("返回了数字", lambda o: bool(re.search(r'\d+\.?\d*', o))),
            ("没有报错", lambda o: not has_error(o)),
        ],
    )

    # ── 测试6: 异常输入 ──
    await test(
        "异常输入",
        "哈哈哈",
        checks=[
            ("友好回复", lambda o: "报错" not in o and "错误" not in o),
            ("有回复内容", lambda o: len(o) > 10),
        ],
    )

    # ── 输出评估报告 ──
    print("\n\n")
    print("=" * 60)
    print("  评 估 报 告")
    print("=" * 60)

    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["passed"])
    print(f"\n  通过: {passed}/{total}")
    print(f"  失败: {total - passed}/{total}")
    if FAILURES:
        for f in FAILURES:
            print(f"    ❌ {f['name']}: {f['error'][:80]}")

    print(f"\n  平均耗时: {sum(r['elapsed'] for r in RESULTS)/total:.1f}s")

    print(f"\n  逐项结果:")
    for r in RESULTS:
        icon = "✅" if r["passed"] else "❌"
        print(f"    {icon} {r['name']} ({r['elapsed']:.1f}s)")
        for chk_name, ok in r["checks"]:
            print(f"      {'✅' if ok else '❌'} {chk_name}")
        preview = r["output_preview"].replace("\n", " ")[:120]
        print(f"      → {preview}")

    print()
    return 0 if passed == total else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
