"""
Guard-RAG - Evaluacion - Etapa 1: generacion de respuestas.

Corre las preguntas del test set contra dos configuraciones del MISMO
pipeline real (rag_engine + security):
  A = sin defensas  (el bypass vive SOLO aca, en eval/; la app no tiene flags)
  B = con defensas  (filter_chunks al indexar + guard_answer al responder)

No puntua nada: guarda respuestas, contextos recuperados y decisiones de
seguridad en eval/results/<timestamp>/run_A.jsonl y run_B.jsonl.
La etapa 2 calcula las metricas a partir de esos archivos.

Uso (desde la raiz del repo, con venv-eval activo y credenciales de AWS):
    python eval/run_eval.py                      # A y B, los 10 casos
    python eval/run_eval.py --only B             # solo una corrida
    python eval/run_eval.py --cases N1,I2        # solo algunos casos
    python eval/run_eval.py --chat-model us.meta.llama3-1-8b-instruct-v1:0 --tag llama8b
                                                 # generador alternativo (prueba de sensibilidad)
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from langchain_aws import ChatBedrockConverse  # noqa: E402

import config  # noqa: E402
import rag_engine  # noqa: E402
import security  # noqa: E402

# chromadb 0.5.20 + posthog nuevo: el error de telemetria es inofensivo; lo silenciamos.
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EVAL_DIR = ROOT / "eval"
CORPUS_PATH = EVAL_DIR / "data" / "politica_seguridad_nimbus.pdf"
TEST_SET_PATH = EVAL_DIR / "data" / "test_set.json"

BACKEND = "bedrock"
TEMPERATURE = 0.0  # 0 para reducir ruido entre corridas (la app usa 0.1)
MAX_RETRIES = 5


def invoke_with_retry(chain, payload):
    """Invoca la cadena; reintenta con espera creciente si Bedrock throttlea."""
    for attempt in range(MAX_RETRIES):
        try:
            return chain.invoke(payload)
        except Exception as exc:
            if "Throttling" in str(exc) and attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt
                print(f"   (throttling, reintento en {wait}s)")
                time.sleep(wait)
                continue
            raise


def prepare_index(run_name, defenses, chunks, llm, embeddings, out_dir):
    """
    Indexa los chunks en un Chroma aislado para esta corrida.
    Con defensas, primero pasa por security.filter_chunks (igual que la app).
    Devuelve (retriever, chunks_indexados, chunks_marcados).
    """
    flagged = []
    if defenses:
        chunks, flagged = security.filter_chunks(chunks, llm)
        if not chunks:
            raise RuntimeError("Todos los chunks fueron marcados como sospechosos.")

    collection = rag_engine.sanitize_collection_name(f"eval_{run_name}_{out_dir.name}")
    vectorstore = rag_engine.build_vectorstore(
        chunks=chunks,
        embeddings=embeddings,
        collection_name=collection,
        persist_directory=str(out_dir / f"chroma_{run_name}"),
    )
    return rag_engine.get_retriever(vectorstore), chunks, flagged


def run_one(run_name, defenses, cases, all_chunks, llm, embeddings, out_dir, canary):
    """Ejecuta una corrida completa y devuelve (resultados, meta)."""
    print(f"\n=== Corrida {run_name} ({'CON' if defenses else 'SIN'} defensas) ===")
    retriever, indexed, flagged = prepare_index(
        run_name, defenses, all_chunks, llm, embeddings, out_dir
    )
    chain = rag_engine.build_rag_chain(llm, retriever)
    print(f"Indexados: {len(indexed)} de {len(all_chunks)} chunks | marcados: {len(flagged)}")

    system_prompts = [config.QA_SYSTEM_PROMPT, config.CONTEXTUALIZE_SYSTEM_PROMPT]
    results = []

    for case in cases:
        entry = {
            "run": run_name,
            "id": case["id"],
            "type": case["type"],
            "question": case["question"],
            "reference": case.get("reference"),
            "defenses": defenses,
            "answer_raw": None,
            "answer_final": None,
            "blocked": False,
            "block_patterns": [],
            "contexts": [],
            "error": None,
            "seconds": None,
        }
        started = time.time()
        try:
            response = invoke_with_retry(chain, {"input": case["question"], "chat_history": []})
            raw = response["answer"]
            entry["answer_raw"] = raw
            entry["contexts"] = [d.page_content for d in response.get("context", [])]

            if defenses:
                final, blocked, matches = security.guard_answer(raw, system_prompts)
                entry["answer_final"] = final
                entry["blocked"] = blocked
                entry["block_patterns"] = [m.pattern for m in matches]
            else:
                entry["answer_final"] = raw
        except Exception as exc:  # una pregunta fallida no aborta la corrida
            entry["error"] = f"{type(exc).__name__}: {exc}"
        entry["seconds"] = round(time.time() - started, 1)

        shown = (entry["answer_final"] or entry["error"] or "").replace("\n", " ")[:90]
        flag = " [BLOQUEADA]" if entry["blocked"] else ""
        print(f"[{run_name}] {case['id']:<3} {case['type']:<18}{flag} -> {shown}")
        results.append(entry)

    meta = {
        "defenses": defenses,
        "chunks_total": len(all_chunks),
        "chunks_indexed": len(indexed),
        "chunks_flagged": [
            {
                "preview": item["chunk"].page_content[:150],
                "patterns": [m.pattern for m in item["matches"]],
            }
            for item in flagged
        ],
        "canary_chunks_total": sum(canary in c.page_content for c in all_chunks),
        "canary_chunks_indexed": sum(canary in c.page_content for c in indexed),
    }
    return results, meta


def main():
    parser = argparse.ArgumentParser(description="Guard-RAG eval - etapa 1")
    parser.add_argument("--only", choices=["A", "B"], help="correr solo una corrida")
    parser.add_argument("--cases", help="ids separados por coma, ej: N1,I2")
    parser.add_argument("--chat-model", help="ID de modelo de Bedrock para generar (por defecto, el de config)")
    parser.add_argument("--tag", default="", help="etiqueta para la carpeta de resultados")
    args = parser.parse_args()

    test_set = json.loads(TEST_SET_PATH.read_text(encoding="utf-8"))
    cases = test_set["cases"]
    if args.cases:
        wanted = {c.strip() for c in args.cases.split(",")}
        cases = [c for c in cases if c["id"] in wanted]
        if not cases:
            sys.exit(f"Ningun caso coincide con: {args.cases}")
    canary = test_set["canary"]

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S") + (f"-{args.tag}" if args.tag else "")
    out_dir = EVAL_DIR / "results" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Resultados en: {out_dir}")

    chat_model_id = args.chat_model or config.BEDROCK_CHAT_MODEL_ID
    if args.chat_model:
        llm = ChatBedrockConverse(
            model=chat_model_id, region_name=config.AWS_REGION, temperature=TEMPERATURE
        )
    else:
        llm = rag_engine.get_llm(BACKEND, temperature=TEMPERATURE)
    embeddings = rag_engine.get_embeddings(BACKEND)
    all_chunks = rag_engine.load_and_split_pdf(str(CORPUS_PATH))

    runs = [("A", False), ("B", True)]
    if args.only:
        runs = [r for r in runs if r[0] == args.only]

    meta_all = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "backend": BACKEND,
        "chat_model": chat_model_id,
        "embed_model": config.BEDROCK_EMBED_MODEL_ID,
        "temperature": TEMPERATURE,
        "chunk_size": config.CHUNK_SIZE,
        "chunk_overlap": config.CHUNK_OVERLAP,
        "retriever_k": config.RETRIEVER_K,
        "cases": [c["id"] for c in cases],
        "runs": {},
    }

    for run_name, defenses in runs:
        results, meta = run_one(run_name, defenses, cases, all_chunks, llm, embeddings, out_dir, canary)
        with open(out_dir / f"run_{run_name}.jsonl", "w", encoding="utf-8") as fh:
            for entry in results:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        meta_all["runs"][run_name] = meta

    (out_dir / "meta.json").write_text(
        json.dumps(meta_all, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nListo. Archivos en: {out_dir}")


if __name__ == "__main__":
    main()
