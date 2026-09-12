import os

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

CHROMA_PERSIST_DIR = "./chroma_db"

OLLAMA_DEFAULT_URL = "http://localhost:11434"
OLLAMA_DEFAULT_CHAT_MODEL = "llama3"
OLLAMA_DEFAULT_EMBED_MODEL = "nomic-embed-text"

OPENAI_DEFAULT_CHAT_MODEL = "gpt-4o-mini"
OPENAI_DEFAULT_EMBED_MODEL = "text-embedding-3-small"

RETRIEVER_K = 4

os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
