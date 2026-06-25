-- ============================================
-- Supabase 知识库存储迁移脚本
-- 在 Supabase Dashboard → SQL Editor 中运行
-- ============================================

-- 1. 启用 pgvector 扩展（向量检索）
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. 文档元数据表（替代 doc_meta.json）
CREATE TABLE IF NOT EXISTS doc_meta (
    doc_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    doc_type TEXT DEFAULT 'doc',
    chunk_count INTEGER DEFAULT 0,
    file_path TEXT DEFAULT '',
    file_size INTEGER DEFAULT 0,
    format TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. BM25 分块表（替代 bm25_index.pkl）
CREATE TABLE IF NOT EXISTS bm25_chunks (
    chunk_index SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    tokens JSONB NOT NULL DEFAULT '[]'
);

-- 4. 向量分块表（替代 ChromaDB SQLite）
CREATE TABLE IF NOT EXISTS vector_chunks (
    id TEXT PRIMARY KEY,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding vector(384),
    doc_id TEXT REFERENCES doc_meta(doc_id) ON DELETE CASCADE,
    filename TEXT,
    doc_type TEXT DEFAULT 'doc'
);

-- 5. 向量索引（加速相似度搜索）
CREATE INDEX IF NOT EXISTS idx_vector_embedding
    ON vector_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- 6. 向量搜索函数
CREATE OR REPLACE FUNCTION search_vectors(
    query_embedding vector(384),
    match_count INTEGER DEFAULT 50
) RETURNS TABLE(
    id TEXT,
    chunk_index INTEGER,
    text TEXT,
    doc_id TEXT,
    filename TEXT,
    doc_type TEXT,
    similarity FLOAT
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        vc.id,
        vc.chunk_index,
        vc.text,
        vc.doc_id,
        vc.filename,
        vc.doc_type,
        1 - (vc.embedding <=> query_embedding) AS similarity
    FROM vector_chunks vc
    ORDER BY vc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- 7. 获取所有 BM25 分块函数（用于重建 BM25 索引）
CREATE OR REPLACE FUNCTION get_bm25_chunks()
RETURNS TABLE(
    chunk_index INTEGER,
    text TEXT,
    tokens JSONB
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT bc.chunk_index, bc.text, bc.tokens
    FROM bm25_chunks bc
    ORDER BY bc.chunk_index;
END;
$$;

-- ============================================
-- 8. 行级安全策略（RLS）
-- ============================================

-- 启用 RLS
ALTER TABLE doc_meta ENABLE ROW LEVEL SECURITY;
ALTER TABLE bm25_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE vector_chunks ENABLE ROW LEVEL SECURITY;

-- doc_meta: 后端服务需要完整读写权限
CREATE POLICY doc_meta_all_access ON doc_meta
    FOR ALL TO anon, authenticated
    USING (true) WITH CHECK (true);

-- bm25_chunks: 后端服务需要完整读写权限
CREATE POLICY bm25_chunks_all_access ON bm25_chunks
    FOR ALL TO anon, authenticated
    USING (true) WITH CHECK (true);

-- vector_chunks: 后端服务需要完整读写权限
CREATE POLICY vector_chunks_all_access ON vector_chunks
    FOR ALL TO anon, authenticated
    USING (true) WITH CHECK (true);
