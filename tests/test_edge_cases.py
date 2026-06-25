"""
边界条件 / 异常情况测试
验证系统在错误输入、极端值、资源缺失时的行为
"""
import os
import sys
import asyncio
import pytest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ========== 文档解析 — 不支持的格式 ==========


class TestUnsupportedFormat:
    def test_unknown_extension(self):
        from mcp_rag_server import parse_document
        with pytest.raises(ValueError, match="不支持的格式"):
            parse_document("test.xyz")


class TestParseEmptyFile:
    def test_empty_txt(self):
        from mcp_rag_server import parse_txt
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
            text, paras = parse_txt(path)
            assert text == ""
            assert paras == []
        finally:
            os.unlink(path)

    def test_whitespace_only(self):
        from mcp_rag_server import parse_txt
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("   \n\n   \n")
            text, paras = parse_txt(path)
            # 空白段落应被过滤
            assert len(paras) == 0
        finally:
            os.unlink(path)


# ========== 分块 — 极端值 ==========


class TestChunkEdgeCases:
    def test_chunk_larger_than_text(self):
        """分块大小远大于文本，所有内容在一个分块"""
        from mcp_rag_server import chunk_document
        chunks = chunk_document(["hello world"], chunk_size=10000, overlap=0)
        assert len(chunks) == 1
        assert "hello world" in chunks[0]

    def test_tiny_chunk_size(self):
        """极小分块（每个字一块）"""
        from mcp_rag_server import chunk_document
        chunks = chunk_document(["ABC", "DEF"], chunk_size=1, overlap=0)
        assert len(chunks) >= 2  # 应被拆成多个小块

    def test_negative_overlap(self):
        """负重叠 = 无重叠"""
        from mcp_rag_server import chunk_document
        chunks = chunk_document(["A" * 200, "B" * 200], chunk_size=100, overlap=-1)
        assert len(chunks) >= 1  # 不会崩溃

    def test_zero_overlap(self):
        from mcp_rag_server import chunk_document
        chunks = chunk_document(["A" * 200, "B" * 200], chunk_size=100, overlap=0)
        assert len(chunks) >= 1


# ========== BM25 — 空输入 ==========


class TestBM25EdgeCases:
    def test_search_with_empty_query(self):
        from mcp_rag_server import BM25Index
        idx = BM25Index()
        idx.add_chunks(["电商数据"])
        results = idx.search("", top_k=5)
        # 空查询不会崩溃，BM25Okapi 返回零分或低分
        assert isinstance(results, list)

    def test_search_before_index(self):
        from mcp_rag_server import BM25Index
        idx = BM25Index()
        assert idx.search("test") == []

    def test_add_empty_chunks(self):
        from mcp_rag_server import BM25Index
        idx = BM25Index()
        idx.add_chunks([])
        assert len(idx.chunks) == 0
        assert idx.bm25 is None

    def test_remove_out_of_range(self):
        from mcp_rag_server import BM25Index
        idx = BM25Index()
        idx.add_chunks(["AAAA"])
        idx.remove_indices([999])  # 不应崩溃
        assert len(idx.chunks) == 1


# ========== 检索 — 空库 / 超长输入 ==========


class TestHybridSearchEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_knowledge_base(self):
        """知识库为空时应返回空列表，不崩溃"""
        from mcp_rag_server import hybrid_search
        from mcp_rag_server import _vector_index
        # 若索引为空
        if _vector_index is None or _vector_index.count() == 0:
            result = hybrid_search("测试查询")
            assert result == []

    def test_very_long_query(self):
        """超长查询不崩溃"""
        from mcp_rag_server import hybrid_search
        from mcp_rag_server import _vector_index
        if _vector_index and _vector_index.count() > 0:
            result = hybrid_search("A" * 10000)
            # 返回空或结果，但不崩溃
            assert isinstance(result, list)


# ========== 数据分析 — 空/坏数据 ==========


class TestVizEdgeCases:
    def test_empty_dataframe(self):
        from mcp_analysis_server import _auto_xy
        import pandas as pd
        df = pd.DataFrame()
        with pytest.raises(Exception):  # IndexError 或类似
            _auto_xy(df)

    def test_single_row(self):
        from mcp_analysis_server import _auto_xy
        import pandas as pd
        df = pd.DataFrame({"x": [1], "y": [2]})
        x, y = _auto_xy(df)
        assert x in df.columns
        assert y in df.columns


# ========== 并发 — 限流器压力 ==========


class TestRateLimiterStress:
    @pytest.mark.asyncio
    async def test_concurrent_under_limit(self):
        """并发在限制内，全部通过"""
        from mcp_rag_server import RateLimiter
        limiter = RateLimiter(max_concurrent=5, max_per_second=100, max_queue=50)
        async def task():
            await limiter.acquire()
            await asyncio.sleep(0.01)
            limiter.release()
        tasks = [task() for _ in range(10)]
        await asyncio.gather(*tasks)  # 不应有异常

    @pytest.mark.asyncio
    async def test_concurrent_over_limit(self):
        """并发超过限制 + 排队溢出，部分被拒绝"""
        from mcp_rag_server import RateLimiter
        limiter = RateLimiter(max_concurrent=1, max_per_second=100, max_queue=2)
        errors = 0
        async def task():
            nonlocal errors
            try:
                await limiter.acquire()
                await asyncio.sleep(0.05)
                limiter.release()
            except RuntimeError:
                errors += 1
        tasks = [task() for _ in range(20)]
        await asyncio.gather(*tasks)
        assert errors > 0  # 部分被拒绝


# ========== 数据库 — 假连接测试 ==========


class TestDBConnection:
    def test_no_db_file(self):
        """无 DB 文件时连接返回 None"""
        from mcp_db_server import _get_db_connection
        import mcp_db_server
        old_path = mcp_db_server.DB_PATH
        mcp_db_server.DB_PATH = None
        try:
            assert _get_db_connection() is None
        finally:
            mcp_db_server.DB_PATH = old_path


# ========== 工具函数 — 参数校验 ==========


class TestParameterValidation:
    def test_top_k_clamped(self):
        """top_k 参数被限制在 1-20 范围"""
        from mcp_rag_server import MAX_TOP_K
        assert MAX_TOP_K == 20
        # 这个逻辑在 search_knowledge 函数里通过 min/max 实现

    def test_chunk_config_positive(self):
        from mcp_rag_server import CHUNK_SIZE, CHUNK_OVERLAP, RRF_K
        assert CHUNK_SIZE > 0
        assert CHUNK_OVERLAP >= 0
        assert RRF_K > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
