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


QA_SYSTEM_PROMPT = (
    "Sos un asistente experto que responde preguntas basandote "
    "UNICAMENTE en el siguiente contexto extraido de un documento PDF. "
    "Si la respuesta no esta en el contexto, decilo explicitamente. "
    "No inventes datos.\n\nContexto:\n{context}"
)

CONTEXTUALIZE_SYSTEM_PROMPT = (
    "Dado un historial de chat y la ultima pregunta del usuario, la cual "
    "puede hacer referencia a contexto previo del historial, reformula "
    "la pregunta para que sea entendible de forma completamente "
    "independiente. NO respondas la pregunta, solo reformulala si es "
    "necesario; si ya es autonoma, devolvela tal cual."
)
