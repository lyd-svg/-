"""
智能体定义
4 个智能体：Main / DB / VIZ / RAG
"""
from agents import Agent, handoff

from .config import db_mcp_server, viz_mcp_server, rag_mcp_server, calc_mcp_server, MODEL
from .handoff_filters import strip_tool_filter


# ---------- 数据库查询智能体 ----------

db_agent = Agent(
    name="数据库查询智能体",
    instructions="""查数据库，返回原始数据。

## 执行步骤
1. get_schema 看表结构
2. query_sql 执行查询
3. return_to_main 返回数据

## 规则
- 只返回 Markdown 表格数据，不要加分析、建议、总结
- 列名是中文，SQL 直接用
- 只能 SELECT
- 查不到 → 返回"数据为空"
- 不需要计算，计算由主智能体负责
""",
    mcp_servers=[db_mcp_server, calc_mcp_server],
    model=MODEL,
)

# ---------- 数据分析可视化智能体 ----------

viz_agent = Agent(
    name="数据分析可视化智能体",
    instructions="""根据用户传入的数据生成图表，返回图片路径。

## 工作方式
主智能体会在 handoff 消息中把数据发给你。**阅读对话历史中主智能体发给你的消息**，
从中提取数据。

数据格式一般是 Markdown 表格或 JSON。直接使用，不要问用户要数据。

## 执行步骤
1. 从主智能体的最新消息中提取数据
2. describe_data 分析数据
3. draw_chart 生成图表
4. return_to_main 返回图片路径

## 规则
- 只返回图表图片路径和图表类型，不要加分析文字
- 数据为空 → 返回"数据为空"
- 不需要计算，计算由主智能体负责
""",
    mcp_servers=[viz_mcp_server, calc_mcp_server],
    model=MODEL,
)

# ---------- 知识库RAG检索智能体 ----------

rag_agent = Agent(
    name="知识库检索智能体",
    instructions="""检索知识库或联网，返回原始结果。

## 执行步骤
1. search_knowledge 或 web_search
2. return_to_main 返回检索结果

## 规则
- 只返回检索到的原文内容，不要加总结分析
- 搜不到 → 返回"未找到相关信息"
- 不需要计算，计算由主智能体负责
""",
    mcp_servers=[rag_mcp_server, calc_mcp_server],
    model=MODEL,
)

# ---------- 主智能体 ----------

main_agent = Agent(
    name="主智能体",
    instructions="""你是调度中枢。收到用户问题后：

## 工作流程

### 场景一：查数据（如"各品类销售额排行"）
1. handoff query_database_agent → 拿到数据
2. **把数据原文整理好**，然后 handoff visualize_analysis_agent
   → 在 handoff 消息中把数据原文附上，传给ta画图
3. 用 calculate 做数值计算
4. 回复用户（数据结论 + 图表路径 + 计算结果）

### 场景二：查知识库（如"行业报告"）
→ handoff search_knowledge_agent → 回复用户

### 场景三：知识库+图表
1. handoff search_knowledge_agent → 拿到原文
2. handoff visualize_analysis_agent → 画图
3. 回复用户

### 场景四：纯聊天
→ 直接回复

## 你的工具
- query_database_agent → 查数据库（handoff）
- visualize_analysis_agent → 生成图表（handoff，数据会自动传递）
- search_knowledge_agent → 检索知识库（handoff）
- calculate → 数值计算

## 规则
- 需要看图时，先查数据再 handoff 给 visualize_analysis_agent
- **需要多张图表时，逐张 handoff 给 visualize_analysis_agent**，每次只传一张图需要的数据
- 每个 handoff 只做一件事
- 计算用 calculate，不要自己算

### 多图表场景示例（如"对比Q1和Q2，算增长率，画双柱图和增长率图"）
1. handoff query_database_agent → 拿到 Q1 数据
2. handoff query_database_agent → 拿到 Q2 数据
3. 用 calculate 算每个品类的环比增长率
4. handoff visualize_analysis_agent → Q1+Q2 对比数据 → 生成双柱图
5. handoff visualize_analysis_agent → 增长率数据 → 生成增长率图
6. 回复用户（结论 + 两张图路径 + 计算结果）
""",
    handoffs=[
        handoff(db_agent, tool_name_override="query_database_agent",
                tool_description_override="查数据库，返回原始数据表格",
                input_filter=strip_tool_filter),
        handoff(viz_agent, tool_name_override="visualize_analysis_agent",
                tool_description_override="根据已有数据生成图表，返回图片路径",
                input_filter=strip_tool_filter),
        handoff(rag_agent, tool_name_override="search_knowledge_agent",
                tool_description_override="检索知识库或联网，返回原文",
                input_filter=strip_tool_filter),
    ],
    mcp_servers=[calc_mcp_server],
    model=MODEL,
)

# ---------- 子智能体 handoff 配置（只能 return_to_main）----------

db_agent.handoffs = [
    handoff(main_agent, tool_name_override="return_to_main",
            tool_description_override="查询完成，把原始数据返回给主智能体"),
]

viz_agent.handoffs = [
    handoff(main_agent, tool_name_override="return_to_main",
            tool_description_override="图表生成完成，把图片路径返回给主智能体"),
]

rag_agent.handoffs = [
    handoff(main_agent, tool_name_override="return_to_main",
            tool_description_override="检索完成，把原文结果返回给主智能体"),
]
