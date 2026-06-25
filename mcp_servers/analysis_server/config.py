"""
分析服务配置
目录、中文字体、颜色、图表类型
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from mcp_servers.common import setup_logger, RateLimiter

# ========== 日志系统 ==========

logger = setup_logger("analysis_server", console_prefix="[VIZ]")

# ========== 限流器 ==========

rate_limiter = RateLimiter(max_concurrent=5, max_per_second=20, max_queue=30)

# ========== 目录配置 ==========

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BASE_DIR)   # mcp_servers/
BASE_DIR = os.path.dirname(BASE_DIR)   # 项目根目录

REPORT_DIR = os.path.join(BASE_DIR, "reports")
CHART_DIR = os.path.join(REPORT_DIR, "charts")
os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(CHART_DIR, exist_ok=True)

# ========== pyecharts 配置 ==========

CHART_WIDTH = "100%"
CHART_HEIGHT = "500px"

# ========== matplotlib 配置 ==========

_zh_fonts = ['Microsoft YaHei', 'SimHei', 'PingFang SC', 'Noto Sans CJK SC', 'DejaVu Sans']
_available = {f.name for f in fm.fontManager.ttflist}
_font_found = None
for _f in _zh_fonts:
    if _f in _available:
        _font_found = _f
        break
if _font_found:
    plt.rcParams['font.sans-serif'] = [_font_found, 'DejaVu Sans']
else:
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

MPL_COLORS = [
    '#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F',
    '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#BAB0AC',
]

# ========== 图表类型 ==========

CHART_TYPES = {
    "bar": "柱状图 - 适用于类别对比",
    "line": "折线图 - 适用于趋势分析",
    "pie": "饼图 - 适用于占比分析",
    "scatter": "散点图 - 适用于相关性分析",
}
