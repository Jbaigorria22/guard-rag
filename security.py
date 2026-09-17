"""
Guard-RAG - Fase 2 - Capa de seguridad.
Deteccion de inyeccion de prompt (Capa 1: por patrones/regex).
"""
import re
from typing import List, NamedTuple


class InjectionMatch(NamedTuple):
    pattern: str
    matched_text: str


# Patrones comunes de inyeccion de prompt, en espanol e ingles.
# No es una lista exhaustiva -- es la primera linea de defensa.
INJECTION_PATTERNS = [
    r"ignor[ae]\s+(las\s+)?instruccion",
    r"ignore\s+(the\s+)?(previous|above)\s+instructions?",
    r"olvida\s+(todo\s+lo\s+)?anterior",
    r"disregard\s+(all\s+)?(previous|prior)",
    r"actua\s+como\s+si",
    r"act\s+as\s+if\s+you",
    r"eres\s+ahora\s+un[ao]?\s+asistente\s+sin",
    r"you\s+are\s+now\s+(a|an)\s+.*\s+without\s+restrictions",
    r"system\s*prompt",
    r"prompt\s+del\s+sistema",
    r"revela\s+tus\s+instrucciones",
    r"reveal\s+your\s+(system\s+)?instructions",
    r"no\s+sigas\s+las\s+reglas",
    r"do\s+not\s+follow\s+(the\s+)?rules",
    r"nueva\s+tarea\s*:",
    r"new\s+task\s*:",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def scan_text(text: str) -> List[InjectionMatch]:
    """Devuelve la lista de patrones sospechosos encontrados en el texto."""
    matches = []
    for pattern, compiled in zip(INJECTION_PATTERNS, _COMPILED_PATTERNS):
        found = compiled.search(text)
        if found:
            matches.append(InjectionMatch(pattern=pattern, matched_text=found.group(0)))
    return matches


def is_suspicious(text: str) -> bool:
    """True si el texto contiene al menos un patron sospechoso."""
    return len(scan_text(text)) > 0





def scan_chunks(chunks) -> tuple:
    """
    Escanea una lista de chunks (Document de LangChain).
    Devuelve (chunks_limpios, chunks_sospechosos) donde cada
    sospechoso es un dict con el chunk y los patrones que matchearon.
    """
    clean_chunks = []
    flagged_chunks = []

    for chunk in chunks:
        matches = scan_text(chunk.page_content)
        if matches:
            flagged_chunks.append({
                "chunk": chunk,
                "matches": matches,
            })
        else:
            clean_chunks.append(chunk)

    return clean_chunks, flagged_chunks





def log_detection(pdf_filename: str, flagged_chunks: list, log_path: str = "security_events.log") -> None:
    """Registra en un archivo de log cada deteccion de inyeccion de prompt."""
    from datetime import datetime

    with open(log_path, "a", encoding="utf-8") as f:
        for item in flagged_chunks:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            phrases = "; ".join(m.matched_text for m in item["matches"])
            f.write(f"[{timestamp}] archivo={pdf_filename} | patrones_detectados=\"{phrases}\"\n")



def check_output(answer: str) -> bool:
    """
    Revisa la respuesta del LLM antes de mostrarla al usuario.
    Reutiliza los mismos patrones de inyeccion: si el LLM esta a punto
    de repetir o confirmar una instruccion maliciosa, lo detectamos aca
    como ultima barrera antes de la pantalla.
    """
    return is_suspicious(answer)