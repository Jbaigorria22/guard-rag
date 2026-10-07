"""Prueba de humo del backend Bedrock: un mensaje de chat y un embedding."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rag_engine  # noqa: E402

llm = rag_engine.get_llm("bedrock")
print("Chat (Haiku 4.5):", llm.invoke("Responde solo con la palabra OK").content)

embeddings = rag_engine.get_embeddings("bedrock")
vector = embeddings.embed_query("hola mundo")
print("Embedding (Titan v2): dimension =", len(vector))
