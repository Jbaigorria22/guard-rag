import os
import tempfile

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

import config
import rag_engine
import security

st.set_page_config(page_title="Guard-RAG", page_icon="🛡️", layout="wide")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "rag_chain" not in st.session_state:
    st.session_state.rag_chain = None
if "processed_file" not in st.session_state:
    st.session_state.processed_file = None
if "question_timestamps" not in st.session_state:
    st.session_state.question_timestamps = []

rate_limiter = security.RateLimiter(max_requests=10, window_seconds=60)

with st.sidebar:
    st.header("🛡️ Guard-RAG - Settings")

    BACKENDS = {
        "Option A: OpenAI": "openai",
        "Option B: Ollama (100% local)": "ollama",
        "Option C: Amazon Bedrock (AWS)": "bedrock",
    }
    backend_choice = st.selectbox("AI backend", options=list(BACKENDS))
    backend = BACKENDS[backend_choice]

    openai_api_key = None
    ollama_url = config.OLLAMA_DEFAULT_URL
    ollama_chat_model = config.OLLAMA_DEFAULT_CHAT_MODEL
    ollama_embed_model = config.OLLAMA_DEFAULT_EMBED_MODEL

    if backend == "openai":
        openai_api_key = st.text_input("OpenAI API Key", type="password")
        embed_model_label = config.OPENAI_DEFAULT_EMBED_MODEL
    elif backend == "bedrock":
        st.caption(f"Region: {config.AWS_REGION} | Chat: Claude Haiku 4.5 | Embeddings: Titan v2")
        st.caption("Uses the AWS credentials of the environment (no API key).")
        embed_model_label = config.BEDROCK_EMBED_MODEL_ID
    else:
        ollama_url = st.text_input("Ollama URL", value=config.OLLAMA_DEFAULT_URL)
        ollama_chat_model = st.text_input("Chat model (Ollama)", value=config.OLLAMA_DEFAULT_CHAT_MODEL)
        ollama_embed_model = st.text_input("Embeddings model (Ollama)", value=config.OLLAMA_DEFAULT_EMBED_MODEL)
        embed_model_label = ollama_embed_model

    st.divider()

    uploaded_pdf = st.file_uploader("Upload a PDF", type=["pdf"])

    process_clicked = st.button("🔍 Process PDF", use_container_width=True)

    if process_clicked:
        if uploaded_pdf is None:
            st.error("Upload a PDF file first.")
        elif backend == "openai" and not openai_api_key:
            st.error("Enter your OpenAI API key to continue.")
        else:
            try:
                with st.spinner("Processing PDF..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                        tmp_file.write(uploaded_pdf.getvalue())
                        tmp_path = tmp_file.name

                    chunks = rag_engine.load_and_split_pdf(tmp_path)
                    os.remove(tmp_path)

                    if not chunks:
                        st.error("Could not extract text from the PDF.")
                        st.stop()

                    llm_for_check = rag_engine.get_llm(
                        backend=backend,
                        openai_api_key=openai_api_key,
                        ollama_url=ollama_url,
                        ollama_chat_model=ollama_chat_model,
                    )

                    clean_chunks, flagged_chunks = security.filter_chunks(chunks, llm_for_check)

                    if flagged_chunks:
                        security.log_detection(uploaded_pdf.name, flagged_chunks)
                        st.warning(
                            f"Detected {len(flagged_chunks)} chunk(s) "
                            f"with suspicious prompt-injection patterns. "
                            f"They were excluded from the index for security."
                        )
                        for item in flagged_chunks:
                            matched_phrases = ", ".join(m.matched_text for m in item["matches"])
                            st.caption(f"⚠️ Pattern detected: \"{matched_phrases}\"")

                    if not clean_chunks:
                        st.error("All chunks were flagged as suspicious. Processing cancelled.")
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

                st.success(f"'{uploaded_pdf.name}' indexed in {len(chunks)} chunks.")
            except Exception as e:
                st.error(f"Error processing the PDF: {e}")

    if st.session_state.processed_file:
        st.info(f"Active document: {st.session_state.processed_file}")

st.title("🛡️ Guard-RAG")
st.caption("Chat with your PDF. Every answer passes through injection and leakage defenses.")

for message in st.session_state.chat_history:
    role = "user" if isinstance(message, HumanMessage) else "assistant"
    with st.chat_message(role):
        st.markdown(message.content)

user_question = st.chat_input("Ask your PDF something...")

if user_question:
    if not rate_limiter.is_allowed(st.session_state.question_timestamps):
        st.error(
            "You reached the question limit (10 per minute). "
            "Wait a moment before asking again."
        )
        st.stop()

    st.session_state.question_timestamps = rate_limiter.record(
        st.session_state.question_timestamps
    )

    if st.session_state.rag_chain is None:
        st.warning("Upload and process a PDF from the sidebar first.")
        st.stop()

    with st.chat_message("user"):
        st.markdown(user_question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = st.session_state.rag_chain.invoke(
                    {
                        "input": user_question,
                        "chat_history": st.session_state.chat_history,
                    }
                )
                answer = response["answer"]

                answer, blocked, matches = security.guard_answer(
                    answer, [config.QA_SYSTEM_PROMPT, config.CONTEXTUALIZE_SYSTEM_PROMPT]
                )

                if blocked:
                    security.log_detection(
                        st.session_state.processed_file,
                        [{"chunk": None, "matches": matches}],
                    )

                st.markdown(answer)
            except Exception as e:
                answer = f"An error occurred while generating the answer: {e}"
                st.error(answer)

    st.session_state.chat_history.append(HumanMessage(content=user_question))
    st.session_state.chat_history.append(AIMessage(content=answer))