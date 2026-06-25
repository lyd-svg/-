"""
集成测试 — RAG 端到端链路验证
需要 Supabase 可用，否则自动跳过：pytest test_integration.py -v
"""
import os
import sys
import json
import pytest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
pytest_plugins = ("pytest_asyncio",)

# ========== 前置条件检查 ==========

_supabase_available = bool(
    os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY")
)

skip_if_no_supabase = pytest.mark.skipif(
    not _supabase_available,
    reason="需要配置 SUPABASE_URL 和 SUPABASE_KEY",
)


# ========== RAG 完整链路 ==========


@pytest.mark.asyncio
@skip_if_no_supabase
class TestRAGPipeline:
    """上传文档 → 检索 → 清理 的完整流程"""

    @pytest.mark.asyncio
    async def test_upload_and_search(self):
        """上传一篇 TXT 文档，确认能检索到"""
        from mcp_rag_server import (
            _init_indexes, _bm25_index, _vector_index,
        )
        # 确保索引已初始化
        if _vector_index is None:
            _init_indexes()

        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("2025年电商行业市场规模达到15万亿元\n\n"
                        "直播电商占比持续提升\n\n"
                        "跨境电商增速超过40%")

            # 上传并索引
            from mcp_rag_server import _index_document, hybrid_search
            doc_id = _index_document(path)

            # 检索验证
            results = hybrid_search("电商市场规模", top_k=3)
            assert len(results) > 0, "应检索到结果"
            # 验证结果包含相关内容
            texts = [r["text"] for r in results]
            assert any("15万亿" in t for t in texts), f"应找到包含'15万亿'的文本，实际: {texts}"
            assert all("doc_id" in r for r in results)

            # 清理
            from mcp_rag_server import _get_chunk_info_by_doc_id
            indices, vi = _get_chunk_info_by_doc_id(doc_id)
            if vi:
                vi.delete_document(doc_id)
            _bm25_index.remove_indices(indices)
            from mcp_rag_server import _delete_meta_entry
            _delete_meta_entry(doc_id)

        finally:
            os.unlink(path)


@pytest.mark.asyncio
@skip_if_no_supabase
class TestRAGDocumentLifecycle:
    """文档 CRUD 操作"""

    @pytest.mark.asyncio
    async def test_list_documents_empty(self):
        """空库状态下列出文档不崩溃"""
        from mcp_rag_server import list_documents
        result = await list_documents()
        assert isinstance(result, str)
        assert "知识库" in result

    @pytest.mark.asyncio
    async def test_get_nonexistent_document(self):
        """查询不存在的文档返回错误提示"""
        from mcp_rag_server import get_document_info
        result = await get_document_info("doc_nonexistent")
        assert "不存在" in result or "错误" in result

    @pytest.mark.asyncio
    async def test_delete_nonexistent_document(self):
        """删除不存在的文档返回错误提示"""
        from mcp_rag_server import delete_document
        result = await delete_document("doc_nonexistent")
        assert "不存在" in result or "错误" in result


@pytest.mark.asyncio
@skip_if_no_supabase
class TestHealthCheck:
    """健康检查端点"""

    @pytest.mark.asyncio
    async def test_health_check_rag(self):
        from mcp_rag_server import health_check
        result = await health_check()
        assert "Supabase" in result
        assert "BM25" in result
        assert "向量" in result
        assert "嵌入模型" in result


# ========== 数据库查询集成测试 ==========


class TestDBIntegration:
    """数据库工具调用"""

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_get_tables(self):
        from mcp_db_server import get_tables
        result = await get_tables()
        assert "users" in result
        assert "orders" in result
        assert "products" in result

    @pytest.mark.asyncio
    async def test_get_schema(self):
        from mcp_db_server import get_schema
        result = await get_schema("users")
        assert "用户ID" in result

    @pytest.mark.asyncio
    async def test_get_schema_markdown(self):
        from mcp_db_server import get_schema_markdown
        result = await get_schema_markdown()
        assert "users" in result
        assert "products" in result

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_get_table_stats(self):
        from mcp_db_server import get_table_stats
        import mcp_db_server
        if mcp_db_server.DB_PATH:
            result = await get_table_stats("users")
            assert "总行数" in result

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_query_empty_result(self):
        """无结果查询不应崩溃"""
        from mcp_db_server import query_sql
        import mcp_db_server
        if mcp_db_server.DB_PATH:
            result = await query_sql(
                "SELECT * FROM users WHERE 用户ID = -9999"
            )
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_db_health_check(self):
        from mcp_db_server import health_check
        result = await health_check()
        assert "系统" in result


# ========== 可视化集成测试 ==========


class TestVizIntegration:
    """可视化工具调用"""

    @pytest.mark.asyncio
    async def test_get_chart_types(self):
        from mcp_analysis_server import get_chart_types
        result = await get_chart_types()
        assert "bar" in result
        assert "pie" in result

    @pytest.mark.asyncio
    async def test_describe_data(self):
        from mcp_analysis_server import describe_data
        data = json.dumps([
            {"品类": "手机", "销售额": 1000},
            {"品类": "电脑", "销售额": 2000},
        ])
        result = await describe_data(data)
        assert "手机" in result
        assert "销售额" in result

    @pytest.mark.asyncio
    async def test_visualize_data(self):
        from mcp_analysis_server import visualize_data
        data = json.dumps([
            {"品类": "手机", "销售额": 1000},
            {"品类": "电脑", "销售额": 2000},
        ])
        result = await visualize_data(data, chart_type="bar", title="测试图表")
        assert "base64" in result or "图表" in result or "测试图表" in result

    @pytest.mark.asyncio
    async def test_visualize_invalid_type(self):
        from mcp_analysis_server import visualize_data
        result = await visualize_data("[]", chart_type="invalid_type")
        assert "不支持" in result

    @pytest.mark.asyncio
    async def test_list_reports(self):
        from mcp_analysis_server import list_reports
        result = await list_reports()
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_viz_health_check(self):
        from mcp_analysis_server import health_check
        result = await health_check()
        assert "Matplotlib" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
