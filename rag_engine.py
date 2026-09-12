import re
from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

import config


def load_and_split_pdf(pdf_path: str) -> List[Document]:
    loader = PyPDFLoader(pdf_path)
    pages = loader.load()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(pages)


def get_embeddings(backend, openai_api_key=None, ollama_url=config.OLLAMA_DEFAULT_URL, ollama_embed_model=config.OLLAMA_DEFAULT_EMBED_MODEL):
    if backend == "openai":
        if not openai_api_key:
            raise ValueError("Falta la API Key de OpenAI para generar embeddings.")
        return OpenAIEmbeddings(model=config.OPENAI_DEFAULT_EMBED_MODEL, api_key=openai_api_key)
    elif backend == "ollama":
        return OllamaEmbeddings(model=ollama_embed_model, base_url=ollama_url)
    raise ValueError(f"Backend de embeddings desconocido: {backend}")


def get_llm(backend, openai_api_key=None, ollama_url=config.OLLAMA_DEFAULT_URL, ollama_chat_model=config.OLLAMA_DEFAULT_CHAT_MODEL, temperature=0.1):
    if backend == "openai":
        if not openai_api_key:
            raise ValueError("Falta la API Key de OpenAI para el modelo de chat.")
        return ChatOpenAI(model=config.OPENAI_DEFAULT_CHAT_MODEL, api_key=openai_api_key, temperature=temperature)
    elif backend == "ollama":
        return ChatOllama(model=ollama_chat_model, base_url=ollama_url, temperature=temperature)
    raise ValueError(f"Backend de LLM desconocido: {backend}")

def sanitize_collection_name(raw_name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_name)
    name = name.strip("_-")
    if len(name) < 3:
        name = f"col_{name}"
    return name[:63]


def build_collection_name(pdf_filename: str, backend: str, embed_model: str) -> str:
    base = f"{pdf_filename}_{backend}_{embed_model}"
    return sanitize_collection_name(base)


def build_vectorstore(chunks, embeddings, collection_name, persist_directory=config.CHROMA_PERSIST_DIR):
    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_directory,
    )
    ids = [f"{collection_name}_chunk_{i}" for i in range(len(chunks))]
    vectorstore.add_documents(documents=chunks, ids=ids)
    return vectorstore


def get_retriever(vectorstore, k=config.RETRIEVER_K):
    return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": k})


def build_rag_chain(llm, retriever):
    contextualize_q_system_prompt = (
        "Dado un historial de chat y la ultima pregunta del usuario, la cual "
        "puede hacer referencia a contexto previo del historial, reformula "
        "la pregunta para que sea entendible de forma completamente "
        "independiente. NO respondas la pregunta, solo reformulala si es "
        "necesario; si ya es autonoma, devolvela tal cual."
    )
    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )

    qa_system_prompt = (
        "Sos un asistente experto que responde preguntas basandote "
        "UNICAMENTE en el siguiente contexto extraido de un documento PDF. "
        "Si la respuesta no esta en el contexto, decilo explicitamente. "
        "No inventes datos.\n\nContexto:\n{context}"
    )
    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", qa_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

    return create_retrieval_chain(history_aware_retriever, question_answer_chain)
