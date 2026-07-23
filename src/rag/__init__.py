"""
RAG corpora for Sol, backed by Redis Stack (RediSearch + vector similarity)
via redisvl. See `src.rag.index` for the shared upsert/search API used by
both the CJ product catalog corpus and the internal playbook corpus.
"""
