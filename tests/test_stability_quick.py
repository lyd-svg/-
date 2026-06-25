"""
稳定性测试精简版 — 压制 SDK 清理报错
"""
import asyncio, sys, os, time, re, subprocess, socket

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())
sys.stderr = open(os.devnull, 'w')

from dotenv import load_dotenv
load_dotenv()
from agent_system import run_agent_with_retry, setup_deepseek
setup_deepseek()

PASS, FAIL = 0, 0
REPORT = []

def check(name, ok):
    global PASS, FAIL
    if ok: PASS += 1
    else: FAIL += 1
    REPORT.append((name, ok))

async def q(query, timeout=60):
    try:
        r = await asyncio.wait_for(run_agent_with_retry(query, max_history=0), timeout=timeout)
        return r.final_output
    except asyncio.TimeoutError:
        return None
    except Exception as e:
        return f'__ERROR__:{str(e)[:80]}'

def section(name):
    print(f'\n  [{name}]')

async def main():
    # 1/5: 交替查询
    section('交替查询（模拟真实使用）')
    questions = ['各品类销售额排行','每月销售趋势如何','用户等级分布','各城市销售额TOP10','计算 5000 的 15%','哪个商品评价最好']
    for i, txt in enumerate(questions):
        resp = await q(txt, 60)
        ok = resp and '__ERROR__' not in resp
        check(f'[{i+1}/6] {txt[:20]}', ok)
        print(f'  {"PASS" if ok else "FAIL"} [{i+1}/6] {txt[:20]}')

    # 2/5: 长链路
    section('长链路压力（4 DB + VIZ）')
    resp = await q('对比2024年Q1和Q2的品类销售额，计算环比增长率，画双柱对比图', 300)
    ok = resp and '__ERROR__' not in resp
    has_chart = bool(re.search(r'\.png', resp or ''))
    check('长链路完成', ok)
    check('生成了图表', has_chart)
    print(f'  {"PASS" if ok else "FAIL"} 长链路完成')
    print(f'  {"PASS" if has_chart else "FAIL"} 生成了图表')

    # 3/5: 断连恢复
    section('断连恢复')
    resp1 = await q('各品类销售额排行', 60)
    check('断连前正常', resp1 and '__ERROR__' not in resp1)
    print(f'  {"PASS" if resp1 and "__ERROR__" not in resp1 else "FAIL"} 断连前正常')

    # Kill db_server
    try:
        r = subprocess.run(['netstat','-ano','-p','tcp'], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if ':8000 ' in line and 'LISTENING' in line:
                pid = line.strip().split()[-1]
                subprocess.run(['taskkill','-f','-pid',pid], capture_output=True, timeout=5)
                print(f'  KILL port 8000 PID {pid}')
                break
    except: pass
    await asyncio.sleep(2)
    resp2 = await q('各品类销售额排行', 60)
    # Restart
    subprocess.Popen([sys.executable, '-m', 'mcp_servers.db_server.main'], cwd=os.getcwd())
    check('断连后恢复', resp2 and '__ERROR__' not in resp2)
    print(f'  {"PASS" if resp2 and "__ERROR__" not in resp2 else "FAIL"} 断连后恢复')

    # 4/5: 极端输入
    section('极端输入')
    for name, text in [('超长输入','分析 '*500+'各品类'),('特殊字符','!@#$% 100% --- ===')]:
        resp = await q(text, 30)
        ok = resp is not None
        check(f'{name} 不崩溃', ok)
        print(f'  {"PASS" if ok else "FAIL"} {name} 不崩溃')

    # 5/5: 并发
    section('并发请求')
    t0 = time.time()
    rs = await asyncio.gather(q('各品类销售额排行',120), q('每月销售趋势',120), return_exceptions=True)
    elapsed = time.time() - t0
    ok_count = sum(1 for r in rs if isinstance(r,str) and '__ERROR__' not in r)
    check(f'并发 {ok_count}/2', ok_count > 0)
    print(f'  {"PASS" if ok_count > 0 else "FAIL"} 并发 {ok_count}/2 成功 ({elapsed:.1f}s)')

    # 报告
    print()
    print('='*56)
    print('  稳定性评估报告')
    print('='*56)
    total = PASS + FAIL
    pct = PASS / total * 100 if total else 0
    print(f'  检查项通过: {PASS}/{total}')
    print(f'  失败: {FAIL}/{total}')
    print(f'  通过率: {pct:.0f}%')
    grade = '稳定' if pct >= 90 else '一般' if pct >= 70 else '不稳定'
    print(f'  综合评级: {grade}')
    print()
    return 0 if FAIL == 0 else 1

if __name__ == '__main__':
    exit(asyncio.run(main()))
