import os

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

CHROMA_PERSIST_DIR = "./chroma_db"

OLLAMA_DEFAULT_URL = "http://localhost:11434"
OLLAMA_DEFAULT_CHAT_MODEL = "llama3"
OLLAMA_DEFAULT_EMBED_MODEL = "nomic-embed-text"

OPENAI_DEFAULT_CHAT_MODEL = "gpt-4o-mini"
OPENAI_DEFAULT_EMBED_MODEL = "text-embedding-3-small"

# Amazon Bedrock: credentials do NOT go here. boto3 picks them up on its own
# (an ~/.aws profile locally, the task IAM role on ECS).
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_CHAT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
BEDROCK_EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"

RETRIEVER_K = 4

os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)


QA_SYSTEM_PROMPT = (
    "You are an expert assistant that answers questions based ONLY on "
    "the following context extracted from a PDF document. "
    "If the answer is not in the context, say so explicitly. "
    "Do not make up facts. Answer in the same language as the user's "
    "question.\n\nContext:\n{context}"
)

CONTEXTUALIZE_SYSTEM_PROMPT = (
    "Given a chat history and the user's latest question, which may "
    "refer to earlier context in the history, rewrite the question so "
    "that it can be understood completely on its own. Do NOT answer the "
    "question, only rewrite it if needed; if it already stands on its "
    "own, return it unchanged. Keep the question in its original language."
)
