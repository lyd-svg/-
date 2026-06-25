"""
多轮对话测试 — 从简单到复杂，逐步递进
验证上下文保持、数据记忆、图像生成
"""
import asyncio, sys, os, time, re

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())
sys.stderr = open(os.devnull, 'w')

from dotenv import load_dotenv
load_dotenv()
from agent_system import run_agent_with_retry, setup_deepseek
from agent_system.conversation import run_agent
from agents.run import RunResult

setup_deepseek()

PASS = 0
FAIL = 0
TURNS = []


def check(name: str, ok: bool):
    global PASS, FAIL
    if ok: PASS += 1
    else: FAIL += 1
    icon = "PASS" if ok else "FAIL"
    print(f"  [{icon}] {name}")


def has_png(text: str) -> bool:
    return bool(re.search(r'\.png', text or ""))


def has_table(text: str) -> bool:
    return "|" in (text or "") and "---" in (text or "")


def has_error(text: str) -> bool:
    errors = ["错误", "失败", "异常", "超时"]
    return any(e in (text or "") for e in errors)


def summary(turns: list):
    print()
    print("="*60)
    print(f"  多轮对话测试报告（{len(turns)} 轮）")
    print("="*60)
    for i, t in enumerate(turns):
        print(f"\n  第 {i+1} 轮: {t['question'][:50]}")
        print(f"    耗时: {t['elapsed']:.1f}s")
        print(f"    状态: {'PASS' if t['status'] else 'FAIL'}")
        if t.get('checks'):
            for c, ok in t['checks']:
                print(f"    {'PASS' if ok else 'FAIL'} {c}")

    total = PASS + FAIL
    pct = max(PASS, 0) / max(total, 1) * 100
    print(f"\n  检查项: {PASS}/{total} 通过 ({pct:.0f}%)")

    if turns:
        print(f"  总耗时: {sum(t['elapsed'] for t in turns):.0f}s")
        print(f"  平均每轮: {sum(t['elapsed'] for t in turns)/len(turns):.0f}s")

    # Context retention check
    if len(turns) >= 4:
        last = turns[-1]
        mentions_previous = any(
            k in (last.get('output','') or '') for k in ['Q1', 'Q2', 'Q3', 'Q4', '季度', '之前'])
        if mentions_previous:
            print(f"\n  上下文保持: 末轮引用了前序数据 PASS")
        else:
            print(f"\n  上下文保持: 末轮未引用前序数据 ⚠️")


async def run_turn(question: str, prev_result=None, timeout=120):
    """执行一轮对话"""
    start = time.time()
    try:
        result = await asyncio.wait_for(
            run_agent(question, prev_result, max_history=10),
            timeout=timeout,
        )
        elapsed = time.time() - start
        return result.final_output, result, elapsed, None
    except asyncio.TimeoutError:
        elapsed = time.time() - start
        return None, prev_result, elapsed, "超时"
    except Exception as e:
        elapsed = time.time() - start
        return None, prev_result, elapsed, str(e)[:80]


async def main():
    print("="*60)
    print("  多轮对话测试")
    print("  从简单到复杂，观察上下文保持和图像生成")
    print("="*60)
    print()

    prev_result = None

    # ── 第1轮：简单查询 ──
    print("─" * 50)
    print("  第 1 轮: 简单查询 —— \"各品类销售额排行\"")
    print("─" * 50)
    output, prev_result, elapsed, err = await run_turn("各品类销售额排行", timeout=120)
    ok = output and not err
    checks = [
        ("返回了数据", bool(output and len(output) > 20)),
        ("未报错", ok),
        ("包含表格", has_table(output or "")),
    ]
    TURNS.append({"question": "各品类销售额排行", "output": output, "elapsed": elapsed, "status": ok, "checks": checks})
    for c, o in checks: check(c, o)

    # ── 第2轮：延续第1轮，画图（验证上下文：记住上轮数据）──
    print()
    print("─" * 50)
    print("  第 2 轮: 延续上轮画图 —— \"画成柱状图\"")
    print("─" * 50)
    output, prev_result, elapsed, err = await run_turn("画成柱状图", prev_result, timeout=120)
    ok = output and not err
    checks = [
        ("生成了图表", has_png(output or "")),
        ("未报错", ok),
        ("VIZ 没要数据", "请提供数据" not in (output or "") and "把数据" not in (output or "")),
    ]
    TURNS.append({"question": "画成柱状图", "output": output, "elapsed": elapsed, "status": ok, "checks": checks})
    for c, o in checks: check(c, o)

    # ── 第3轮：延续上两轮，增加计算（验证：记住上轮图，计算新指标）──
    print()
    print("─" * 50)
    print("  第 3 轮: 延续计算占比 —— \"计算每个品类占总额的百分比\"")
    print("─" * 50)
    output, prev_result, elapsed, err = await run_turn("计算每个品类占总额的百分比", prev_result, timeout=120)
    ok = output and not err
    checks = [
        ("未报错", ok),
        ("提到了占比或百分比", bool(re.search(r'[占比%]', output or ""))),
    ]
    TURNS.append({"question": "计算占比", "output": output, "elapsed": elapsed, "status": ok, "checks": checks})
    for c, o in checks: check(c, o)

    # ── 第4轮：换主题，查询新数据（验证：不混淆新旧数据）──
    print()
    print("─" * 50)
    print("  第 4 轮: 换主题查新数据 —— \"每月销售趋势如何\"")
    print("─" * 50)
    output, prev_result, elapsed, err = await run_turn("每月销售趋势如何", prev_result, timeout=120)
    ok = output and not err
    checks = [
        ("返回了数据", bool(output and len(output) > 20)),
        ("未报错", ok),
    ]
    TURNS.append({"question": "每月销售趋势", "output": output, "elapsed": elapsed, "status": ok, "checks": checks})
    for c, o in checks: check(c, o)

    # ── 第5轮：延续第4轮画图（验证：跨主题上下文切换正确）──
    print()
    print("─" * 50)
    print("  第 5 轮: 延续上轮画趋势图 —— \"画成折线图\"")
    print("─" * 50)
    output, prev_result, elapsed, err = await run_turn("画成折线图", prev_result, timeout=120)
    ok = output and not err
    checks = [
        ("生成了图表", has_png(output or "")),
        ("未报错", ok),
        ("VIZ 没要数据", "请提供数据" not in (output or "") and "把数据" not in (output or "")),
    ]
    TURNS.append({"question": "画成折线图", "output": output, "elapsed": elapsed, "status": ok, "checks": checks})
    for c, o in checks: check(c, o)

    # ── 第6轮：混合引用前序数据（验证：长期记忆）──
    print()
    print("─" * 50)
    print("  第 6 轮: 引用前序结论 —— \"刚才的品类排行中，哪个品类销售额最高？\"")
    print("─" * 50)
    output, prev_result, elapsed, err = await run_turn("刚才的品类排行中，哪个品类销售额最高？", prev_result, timeout=120)
    ok = output and not err
    mentions_previous = any(k in (output or '') for k in ['笔记本', '手机', '平板', '品类', '最高', '榜'])
    checks = [
        ("引用了前序对话", mentions_previous),
        ("未报错", ok),
    ]
    TURNS.append({"question": "引用前序结论", "output": output, "elapsed": elapsed, "status": ok, "checks": checks})
    for c, o in checks: check(c, o)

    # ── 第7轮：复杂多步（验证：长上下文保持+多图）──
    print()
    print("─" * 50)
    print("  第 7 轮: 复杂多步 —— \"对比Q1和Q2的品类销售额，算增长率，画双柱图\"")
    print("─" * 50)
    output, prev_result, elapsed, err = await run_turn(
        "对比 2024 年 Q1 和 Q2 的品类销售额，计算环比增长率，画双柱对比图",
        prev_result, timeout=300,
    )
    ok = output and not err
    checks = [
        ("未报错", ok),
        ("包含增长率数值", bool(re.search(r'\d+\.?\d*%', output or ""))),
        ("生成了图表", has_png(output or "")),
    ]
    TURNS.append({"question": "Q1Q2对比+增长率+图", "output": output, "elapsed": elapsed, "status": ok, "checks": checks})
    for c, o in checks: check(c, o)

    # 输出报告
    summary(TURNS)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
