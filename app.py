import os
import tempfile

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

import config
import rag_engine
import security

st.set_page_config(page_title="Guard-RAG - Fase 1", page_icon="🛡️", layout="wide")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "rag_chain" not in st.session_state:
    st.session_state.rag_chain = None
if "processed_file" not in st.session_state:
    st.session_state.processed_file = None

with st.sidebar:
    st.header("🛡️ Guard-RAG - Configuracion")

    backend_choice = st.selectbox(
        "Backend de IA",
        options=["Opcion A: OpenAI", "Opcion B: Ollama (100% Local)"],
    )
    backend = "openai" if backend_choice.startswith("Opcion A") else "ollama"

    openai_api_key = None
    ollama_url = config.OLLAMA_DEFAULT_URL
    ollama_chat_model = config.OLLAMA_DEFAULT_CHAT_MODEL
    ollama_embed_model = config.OLLAMA_DEFAULT_EMBED_MODEL

    if backend == "openai":
        openai_api_key = st.text_input("OpenAI API Key", type="password")
        embed_model_label = config.OPENAI_DEFAULT_EMBED_MODEL
    else:
        ollama_url = st.text_input("URL de Ollama", value=config.OLLAMA_DEFAULT_URL)
        ollama_chat_model = st.text_input("Modelo de chat (Ollama)", value=config.OLLAMA_DEFAULT_CHAT_MODEL)
        ollama_embed_model = st.text_input("Modelo de embeddings (Ollama)", value=config.OLLAMA_DEFAULT_EMBED_MODEL)
        embed_model_label = ollama_embed_model

    st.divider()

    uploaded_pdf = st.file_uploader("Subi un PDF", type=["pdf"])

    process_clicked = st.button("🔍 Procesar PDF", use_container_width=True)



    if process_clicked:
        if uploaded_pdf is None:
            st.error("Primero subi un archivo PDF.")
        elif backend == "openai" and not openai_api_key:
            st.error("Ingresa tu OpenAI API Key para continuar.")
        else:
            try:
                with st.spinner("Procesando PDF..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                        tmp_file.write(uploaded_pdf.getvalue())
                        tmp_path = tmp_file.name

                    chunks = rag_engine.load_and_split_pdf(tmp_path)
                    os.remove(tmp_path)

                    if not chunks:
                        st.error("No se pudo extraer texto del PDF.")
                        st.stop()

                    clean_chunks, flagged_chunks = security.scan_chunks(chunks)

                    if flagged_chunks:
                        st.warning(
                            f"Se detectaron {len(flagged_chunks)} fragmento(s) "
                            f"con patrones sospechosos de inyeccion de prompt. "
                            f"Fueron excluidos del indice por seguridad."
                        )
                        for item in flagged_chunks:
                            matched_phrases = ", ".join(m.matched_text for m in item["matches"])
                            st.caption(f"⚠️ Patron detectado: \"{matched_phrases}\"")

                    if not clean_chunks:
                        st.error("Todos los fragmentos fueron marcados como sospechosos. Proceso cancelado.")
                        st.stop()

                    chunks = clean_chunks
                    embeddings = rag_engine.get_embeddings(
                        backend=backend,
                        openai_api_key=openai_api_key,
                        ollama_url=ollama_url,
                        ollama_embed_model=ollama_embed_model,
                    )
                    collection_name = rag_engine.build_collection_name(
                        pdf_filename=uploaded_pdf.name,
                        backend=backend,
                        embed_model=embed_model_label,
                    )
                    vectorstore = rag_engine.build_vectorstore(
                        chunks=chunks,
                        embeddings=embeddings,
                        collection_name=collection_name,
                    )
                    retriever = rag_engine.get_retriever(vectorstore)

                    llm = rag_engine.get_llm(
                        backend=backend,
                        openai_api_key=openai_api_key,
                        ollama_url=ollama_url,
                        ollama_chat_model=ollama_chat_model,
                    )
                    st.session_state.rag_chain = rag_engine.build_rag_chain(llm, retriever)
                    st.session_state.processed_file = uploaded_pdf.name
                    st.session_state.chat_history = []

                st.success(f"'{uploaded_pdf.name}' indexado en {len(chunks)} chunks.")
            except Exception as e:
                st.error(f"Error procesando el PDF: {e}")

    if st.session_state.processed_file:
        st.info(f"Documento activo: {st.session_state.processed_file}")




st.title("🛡️ Guard-RAG — Fase 1")
st.caption("Conversa con tu PDF. El pipeline corre localmente (o con OpenAI si lo elegis).")

for message in st.session_state.chat_history:
    role = "user" if isinstance(message, HumanMessage) else "assistant"
    with st.chat_message(role):
        st.markdown(message.content)

user_question = st.chat_input("Preguntale algo a tu PDF...")

if user_question:
    if st.session_state.rag_chain is None:
        st.warning("Primero subi y procesa un PDF desde la barra lateral.")
        st.stop()

    with st.chat_message("user"):
        st.markdown(user_question)

    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            try:
                response = st.session_state.rag_chain.invoke(
                    {
                        "input": user_question,
                        "chat_history": st.session_state.chat_history,
                    }
                )
                answer = response["answer"]
                st.markdown(answer)
            except Exception as e:
                answer = f"Ocurrio un error al generar la respuesta: {e}"
                st.error(answer)

    st.session_state.chat_history.append(HumanMessage(content=user_question))
    st.session_state.chat_history.append(AIMessage(content=answer))