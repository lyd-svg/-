"""
Agent 路由逻辑测试
验证工具归属映射、智能体标签、进度处理器的正确性
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ========== 工具映射完整性 ==========


class TestToolOwnerMapping:
    """验证 _TOOL_OWNER 覆盖了所有 MCP 工具"""

    def test_all_db_tools_mapped(self):
        """数据库查询智能体的所有工具都已映射"""
        from agent_system import _TOOL_OWNER
        db_tools = [
            "query_sql",
            "get_tables",
            "get_schema",
            "get_schema_markdown",
            "get_sample_data",
            "get_table_stats",
            "query_database_agent",
        ]
        for tool in db_tools:
            assert tool in _TOOL_OWNER, f"缺失工具映射: {tool}"
            assert _TOOL_OWNER[tool] == "数据库查询智能体"

    def test_all_viz_tools_mapped(self):
        """可视化智能体的所有工具都已映射"""
        from agent_system import _TOOL_OWNER
        viz_tools = [
            "visualize_data",
            "describe_data",
            "generate_report",
            "get_chart_types",
            "list_reports",
            "visualize_analysis_agent",
        ]
        for tool in viz_tools:
            assert tool in _TOOL_OWNER, f"缺失工具映射: {tool}"
            assert _TOOL_OWNER[tool] == "数据分析可视化智能体"

    def test_all_rag_tools_mapped(self):
        """知识库检索智能体的所有工具都已映射"""
        from agent_system import _TOOL_OWNER
        rag_tools = [
            "search_knowledge",
            "web_search",
            "list_documents",
            "upload_document",
            "delete_document",
            "reindex_all",
            "get_document_info",
            "search_knowledge_agent",
        ]
        for tool in rag_tools:
            assert tool in _TOOL_OWNER, f"缺失工具映射: {tool}"
            assert _TOOL_OWNER[tool] == "知识库检索智能体"


# ========== 智能体标签正确性 ==========


class TestAgentLabels:
    def test_all_agents_have_labels(self):
        import agent_system
        # 3 个子智能体 + 主智能体
        agents = ["主智能体", "数据库查询智能体", "数据分析可视化智能体", "知识库检索智能体"]
        for name in agents:
            label = agent_system._AGENT_LABELS.get(name)
            assert label is not None, f"缺失标签: {name}"
            assert len(label) >= 2, f"标签过短: {name} → {label}"

    def test_agent_names_match_agent_definitions(self):
        import agent_system
        assert agent_system.db_agent.name == "数据库查询智能体"
        assert agent_system.viz_agent.name == "数据分析可视化智能体"
        assert agent_system.rag_agent.name == "知识库检索智能体"
        assert agent_system.main_agent.name == "主智能体"


# ========== 工具名称映射 ==========


class TestFuncNames:
    def test_health_check_mapped(self):
        from agent_system import _FUNC_NAMES
        assert "health_check" in _FUNC_NAMES
        assert "健康" in _FUNC_NAMES["health_check"]

    def test_all_heavy_tools_have_readable_names(self):
        from agent_system import _FUNC_NAMES
        # 关键工具都有中文名
        assert "search_knowledge" in _FUNC_NAMES
        assert "query_sql" in _FUNC_NAMES
        assert "visualize_data" in _FUNC_NAMES
        assert "web_search" in _FUNC_NAMES


# ========== 进度处理器逻辑 ==========


class TestProgressProcessor:
    """验证 _ProgressProcessor 的边界处理"""

    def test_skip_none_handoff(self):
        """from_agent=None, to_agent=None → 跳过"""
        import agent_system
        from agents.tracing import HandoffSpanData
        proc = agent_system._ProgressProcessor()
        # 模拟 SDK 空 handoff
        data = HandoffSpanData(from_agent=None, to_agent=None)
        # 不应抛异常
        proc.on_span_start(type("Span", (), {"span_data": data}))

    def test_skip_main_to_none(self):
        """from_agent='主智能体', to_agent=None → 跳过"""
        import agent_system
        from agents.tracing import HandoffSpanData
        proc = agent_system._ProgressProcessor()
        data = HandoffSpanData(from_agent="主智能体", to_agent=None)
        proc.on_span_start(type("Span", (), {"span_data": data}))

    def test_process_valid_handoff(self):
        """正常 handoff 不抛异常"""
        import agent_system
        from agents.tracing import HandoffSpanData
        proc = agent_system._ProgressProcessor()
        data = HandoffSpanData(
            from_agent="主智能体",
            to_agent="数据库查询智能体",
        )
        proc.on_span_start(type("Span", (), {"span_data": data}))
        assert proc._current == "数据库查询智能体"


# ========== Agent 配置完整性 ==========


class TestAgentConfig:
    def test_all_agents_have_instructions(self):
        import agent_system
        assert len(agent_system.db_agent.instructions) > 50
        assert len(agent_system.viz_agent.instructions) > 50
        assert len(agent_system.rag_agent.instructions) > 50
        assert len(agent_system.main_agent.instructions) > 50

    def test_health_check_in_all_instructions(self):
        """每个子智能体的提示词都提到了 health_check"""
        import agent_system
        for agent in [agent_system.db_agent, agent_system.viz_agent, agent_system.rag_agent]:
            assert "health_check" in agent.instructions, \
                f"{agent.name} 的 instructions 中未提及 health_check"

    def test_fault_troubleshooting_in_all_instructions(self):
        """每个子智能体都有'故障排除'章节"""
        import agent_system
        for agent in [agent_system.db_agent, agent_system.viz_agent, agent_system.rag_agent]:
            assert "故障排除" in agent.instructions, \
                f"{agent.name} 缺少'故障排除'章节"

    def test_handoff_rules_in_db_agent(self):
        """数据库智能体有明确的 handoff 规则"""
        import agent_system
        assert "handoff_to_viz" in agent_system.db_agent.instructions
        assert "return_to_main" in agent_system.db_agent.instructions

    def test_source_citation_in_rag_agent(self):
        """RAG 智能体强制要求来源标注"""
        import agent_system
        inst = agent_system.rag_agent.instructions
        assert "📄" in inst, "缺少知识库来源标记"
        assert "🌐" in inst, "缺少联网来源标记"


# ========== MCP 服务定义 ==========


class TestMCPServerConfig:
    def test_all_servers_registered(self):
        import agent_system
        names = [s.name for s in agent_system._MCP_SERVERS]
        assert "数据库查询服务" in names
        assert "数据分析可视化服务" in names
        assert "知识库RAG检索服务" in names

    def test_server_urls_configured(self):
        import agent_system
        assert agent_system.DB_SERVER_URL.startswith("http://")
        assert agent_system.VIZ_SERVER_URL.startswith("http://")
        assert agent_system.RAG_SERVER_URL.startswith("http://")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
