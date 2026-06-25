"""
单元测试 — 核心纯函数的正确性验证
不依赖外部服务，可直接运行：pytest test_unit.py -v
"""
import os
import sys
import json
import asyncio
import pytest
import tempfile

# 确保项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

pytest_plugins = ("pytest_asyncio",)

# ========== 分块器测试 ==========


class TestSplitSentences:
    """中文/英文句子分割"""

    def test_chinese(self):
        from mcp_rag_server import split_sentences
        result = split_sentences("今天天气很好。明天可能下雨！真的吗？")
        # 分割后标点可能附加在前一句末尾
        assert len(result) == 3
        assert "今天天气很好" in result[0]
        assert "明天可能下雨" in result[1]
        assert "真的吗" in result[2]

    def test_english(self):
        from mcp_rag_server import split_sentences
        result = split_sentences("Hello world. How are you? I am fine!")
        assert len(result) == 3

    def test_mixed(self):
        from mcp_rag_server import split_sentences
        result = split_sentences("价格100元。The price is $15. 结束")
        assert len(result) >= 2

    def test_empty(self):
        from mcp_rag_server import split_sentences
        assert split_sentences("") == []


class TestIsMarkdownTable:
    """Markdown 表格检测"""

    def test_valid_table(self):
        from mcp_rag_server import is_markdown_table
        text = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        assert is_markdown_table(text) is True

    def test_not_table(self):
        from mcp_rag_server import is_markdown_table
        assert is_markdown_table("普通文本") is False

    def test_single_line(self):
        from mcp_rag_server import is_markdown_table
        assert is_markdown_table("| A | B |") is False  # 少于 3 行


class TestChunkDocument:
    """文档分块"""

    def test_basic(self):
        from mcp_rag_server import chunk_document
        paras = ["第一段内容", "第二段内容", "第三段内容"]
        chunks = chunk_document(paras, chunk_size=100, overlap=0)
        assert len(chunks) >= 1
        assert all(isinstance(c, str) for c in chunks)

    def test_overlap(self):
        from mcp_rag_server import chunk_document
        # 构造足够长的段落以触发重叠
        paras = ["A" * 200, "B" * 200, "C" * 200]
        chunks = chunk_document(paras, chunk_size=100, overlap=20)
        assert len(chunks) > 1
        # 验证相邻分块有重叠
        if len(chunks) >= 2:
            tail = chunks[0][-10:]
            # overlap 把前一块的尾部拼到了后一块的开头
            assert tail in chunks[1]

    def test_empty_paragraphs(self):
        from mcp_rag_server import chunk_document
        assert chunk_document([]) == []

    def test_single_short_para(self):
        from mcp_rag_server import chunk_document
        chunks = chunk_document(["hello"], chunk_size=1000)
        assert chunks == ["hello"]


# ========== 文档 ID 生成测试 ==========


class TestGenerateDocId:
    """文档 ID 生成"""

    def test_consistent(self):
        from mcp_rag_server import _generate_doc_id
        # 同文件同时间戳应生成同一个 ID（确定性）
        import time
        ts = time.time()
        from unittest.mock import patch
        with patch("mcp_rag_server.datetime") as mock_dt:
            mock_dt.now.return_value.timestamp.return_value = ts
            id1 = _generate_doc_id("test.pdf")
            id2 = _generate_doc_id("test.pdf")
            assert id1 == id2

    def test_different_files(self):
        from mcp_rag_server import _generate_doc_id
        id_a = _generate_doc_id("a.pdf")
        id_b = _generate_doc_id("b.pdf")
        assert id_a != id_b


# ========== 文档解析器测试 ==========


class TestParseCSV:
    def test_simple_csv(self):
        from mcp_rag_server import parse_csv
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("姓名,年龄\n张三,25\n李四,30")
            text, paras = parse_csv(path)
            assert "张三" in text
            assert len(paras) >= 1
        finally:
            os.unlink(path)


class TestParseTXT:
    def test_paragraphs(self):
        from mcp_rag_server import parse_txt
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("段落一\n\n段落二\n\n段落三")
            text, paras = parse_txt(path)
            assert len(paras) == 3
        finally:
            os.unlink(path)


class TestParseMD:
    def test_markdown(self):
        from mcp_rag_server import parse_md
        fd, path = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("# 标题\n\n正文内容")
            text, paras = parse_md(path)
            assert "标题" in text
        finally:
            os.unlink(path)


# ========== QA 检测测试 ==========


class TestDetectQAFormat:
    def test_valid_qa(self):
        from mcp_rag_server import detect_qa_format
        text = "问：什么是AI？\n答：人工智能\n问：有什么用？\n答：很多用途"
        assert detect_qa_format(text) is True

    def test_not_qa(self):
        from mcp_rag_server import detect_qa_format
        assert detect_qa_format("这是普通文本") is False

    def test_single_pair(self):
        from mcp_rag_server import detect_qa_format
        # 单对不够（需要 >= 2 对）
        assert detect_qa_format("问：你好\n答：你好") is False


# ========== BM25 分词测试 ==========


class TestBM25Tokenize:
    def test_chinese(self):
        from mcp_rag_server import _bm25_index
        tokens = _bm25_index.tokenize("电商行业市场规模")
        assert len(tokens) >= 2
        assert "电商" in tokens

    def test_empty(self):
        from mcp_rag_server import _bm25_index
        tokens = _bm25_index.tokenize("")
        assert tokens == []


class TestBM25Index:
    """BM25 索引增删查"""

    def test_add_and_search(self):
        from mcp_rag_server import BM25Index
        idx = BM25Index()
        idx.add_chunks(["电商市场规模持续增长", "今天天气很好", "电商行业发展迅速"])
        results = idx.search("电商", top_k=2)
        assert len(results) == 2
        # 相关性分数应该 > 0
        for _, score in results:
            assert score > 0

    def test_search_empty(self):
        from mcp_rag_server import BM25Index
        idx = BM25Index()
        assert idx.search("query") == []

    def test_remove_indices(self):
        from mcp_rag_server import BM25Index
        idx = BM25Index()
        idx.add_chunks(["AAAA", "BBBB", "CCCC"])
        assert len(idx.chunks) == 3
        idx.remove_indices([1])
        assert len(idx.chunks) == 2
        assert idx.chunks == ["AAAA", "CCCC"]

    def test_clear(self):
        from mcp_rag_server import BM25Index
        idx = BM25Index()
        idx.add_chunks(["AAAA", "BBBB"])
        idx.clear()
        assert len(idx.chunks) == 0
        assert idx.bm25 is None


# ========== 数据分析工具测试 ==========


class TestJsonToDF:
    def test_basic(self):
        from mcp_analysis_server import json_to_df
        data = json.dumps([{"品类": "手机", "销售额": 100}, {"品类": "电脑", "销售额": 200}])
        df = json_to_df(data)
        assert len(df) == 2
        assert "品类" in df.columns
        assert "销售额" in df.columns

    def test_with_data_wrapper(self):
        from mcp_analysis_server import json_to_df
        data = json.dumps({"data": [{"x": 1}, {"x": 2}]})
        df = json_to_df(data)
        assert len(df) == 2

    def test_invalid_json(self):
        from mcp_analysis_server import json_to_df
        with pytest.raises(Exception):
            json_to_df("not json")


class TestAutoXY:
    def test_mixed_columns(self):
        from mcp_analysis_server import _auto_xy
        import pandas as pd
        df = pd.DataFrame({"类别": ["A", "B"], "数值": [10, 20]})
        x, y, err = _auto_xy(df)
        assert err is None
        assert x == "类别"
        assert y == "数值"

    def test_all_numeric(self):
        from mcp_analysis_server import _auto_xy
        import pandas as pd
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        x, y, err = _auto_xy(df)
        assert err is None
        assert x in df.columns
        assert y in df.columns

    def test_single_column(self):
        from mcp_analysis_server import _auto_xy
        import pandas as pd
        df = pd.DataFrame({"数值": [10, 20]})
        x, y, err = _auto_xy(df)
        assert err is not None  # 单列无法同时作为 x 和 y

    def test_no_numeric(self):
        from mcp_analysis_server import _auto_xy
        import pandas as pd
        df = pd.DataFrame({"a": ["A", "B"], "b": ["X", "Y"]})
        x, y, err = _auto_xy(df)
        assert err is None  # 无数值列时 y 降级为第二列


# ========== 限流器测试 ==========


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_acquire_release(self):
        from mcp_rag_server import RateLimiter
        limiter = RateLimiter(max_concurrent=2, max_per_second=100, max_queue=100)
        await limiter.acquire()
        limiter.release()

    @pytest.mark.asyncio
    async def test_rate_exceeded(self):
        from mcp_rag_server import RateLimiter
        limiter = RateLimiter(max_concurrent=10, max_per_second=3, max_queue=100)
        # 快速消耗 3 次配额
        for _ in range(3):
            await limiter.acquire()
            limiter.release()
        # 第 4 次应该被拒绝
        with pytest.raises(RuntimeError, match="太频繁"):
            await limiter.acquire()

    @pytest.mark.asyncio
    async def test_queue_overflow(self):
        from mcp_rag_server import RateLimiter
        limiter = RateLimiter(max_concurrent=1, max_per_second=100, max_queue=2)
        await limiter.acquire()  # 占用唯一的槽位
        # 排队 2 个
        async def waiter():
            await limiter.acquire()
            limiter.release()
        asyncio.ensure_future(waiter())
        asyncio.ensure_future(waiter())
        await asyncio.sleep(0.1)
        # 第 3 个应该溢出
        with pytest.raises(RuntimeError, match="繁忙"):
            await limiter.acquire()
        limiter.release()
        await asyncio.sleep(0.2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
