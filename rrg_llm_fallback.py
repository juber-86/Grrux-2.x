"""
rrg_llm_fallback.py
===================
Fallback LLM para clasificación aspectual GRR (Van Valin 2005).

Se activa cuando:
  (a) rrg_morph_classifier devuelve None (caso ambiguo morfosintácticamente), O
  (b) el verbo no está en VERB_CLASSES y el morph tampoco pudo decidir.

Modelo: qwen2.5:7b via Ollama  (~4.7 GB, corre bien en CPU con 16 GB RAM)
  ollama pull qwen2.5:7b

Estrategia de clasificación:
  1. Envía al LLM la matriz de rasgos aspectuales (Van Valin) + reglas de
     clasificación en formato JSON — estructurado, sin ambigüedad.
  2. Pide razonamiento explícito paso a paso (chain-of-thought) antes
     de la respuesta final — aprovecha las capacidades de Qwen2.5.
  3. _parse_class extrae 'ANSWER: <clase>' de la respuesta.

Interfaz pública:
  classify_with_llm(verb_lemma, morph_context, sentence_text) -> str | None
  classify_with_llm_verbose(...)                               -> dict
  ollama_status()                                              -> dict
"""

from __future__ import annotations
import json
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------------------
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"
TIMEOUT_SEC  = 120    # Qwen2.5:7b en CPU: 20-40s de razonamiento

VALID_CLASSES = {
    'state', 'activity', 'achievement',
    'accomplishment', 'semelfactive', 'active_accomplishment', 'causative',
}


# ---------------------------------------------------------------------------
# CONOCIMIENTO LINGÜÍSTICO — matrices JSON embebidas como dicts Python
#
# Fuente: Van Valin (2005) Exploring the Syntax-Semantics Interface
# Se serializan a JSON al construir el prompt para que el modelo los
# reciba como datos estructurados, no como prosa.
# ---------------------------------------------------------------------------

AKTIONSART_FEATURE_MATRIX = {
    "state":                 {"dynamic": False,      "telic": False,      "punctual": False},
    "activity":              {"dynamic": True,       "telic": False,      "punctual": False},
    "achievement":           {"dynamic": True,       "telic": True,       "punctual": True},
    "accomplishment":        {"dynamic": True,       "telic": True,       "punctual": False},
    "semelfactive":          {"dynamic": True,       "telic": False,      "punctual": True},
    "active_accomplishment": {"dynamic": True,       "telic": True,       "punctual": False,
                              "note": "atelic activity converted by a quantized/definite object"},
    "causative":             {"dynamic": True,       "telic": "variable", "punctual": "variable",
                              "note": "causing event produces change of state in patient"},
}

CLASSIFICATION_RULES = [
    {
        "step": 1,
        "target_class": "state",
        "conditions": "Verb is perception or cognition: ver, mirar, escuchar, oir, saber, "
                      "conocer, querer, creer, pensar, tener, pertenecer, existir, amar, odiar.",
        "overrides": [
            {"if": "verb has agentive/volitional reading (deliberate action, e.g. 'Juan miro la pantalla')",
             "then_class": "activity"},
            {"if": "verb is in progressive aspect",
             "then_class": "activity"},
             
        ],
    },
    {
        "step": 2,
        "target_class": "activity",
        "conditions": "Verb has a bare/mass noun object (e.g. 'comer pizza', 'beber agua') "
                      "OR is intransitive with no delimited endpoint.",
        "examples": ["correr", "cantar", "caminar", "hablar", "comer (bare object)"],
    },
    {
        "step": 3,
        "target_class": "achievement",
        "conditions": "Event is instantaneous with no internal stages or duration.",
        "diagnostic": "Is 'durante X tiempo' unnatural? If YES -> achievement.",
        "examples": ["explotar", "llegar", "morir", "nacer", "encontrar"],
    },
    {
        "step": 4,
        "target_class": "accomplishment",
        "conditions": "Event unfolds in phases toward an inherent terminal point.",
        "diagnostic": "Are BOTH 'durante X tiempo' AND 'en X tiempo' natural? If YES -> accomplishment.",
        "examples": ["construir la casa", "aprender el idioma", "derretir el hielo", "ir a Puebla"],
    },
    {
        "step": 5,
        "target_class": "semelfactive",
        "conditions": "Single instantaneous action with no lasting change; naturally iterable.",
        "examples": ["estornudar", "parpadear", "toser", "golpear (single contact)"],
    },
    {
        "step": 6,
        "target_class": "active_accomplishment",
        "conditions": "Activity verb PLUS a definite/quantized object (e.g. 'la pizza', 'tres manzanas') "
                      "OR uses aspectual clitic 'se' (e.g. 'se comio').",
        "diagnostic": "Does the object define a natural endpoint for the activity? If YES -> active_accomplishment.",
    },
    {
        "step": 7,
        "target_class": "causative",
        "conditions": "Transitive verb where animate/volitional Agent causes a change of state in Affected Patient.",
        "examples": ["matar", "romper (transitive)", "quemar", "despertar (transitive)", "empujar"],
    },
]


# ---------------------------------------------------------------------------
# PROMPT
# ---------------------------------------------------------------------------

def _build_prompt(verb_lemma: str, morph_context: str, sentence: str) -> str:
    matrix_json = json.dumps(AKTIONSART_FEATURE_MATRIX, indent=2, ensure_ascii=False)
    rules_json  = json.dumps(
        {"instruction": "Apply steps 1 to 7 in strict order. Stop at the first matching step.",
         "rules": CLASSIFICATION_RULES},
        indent=2, ensure_ascii=False
    )

    return f"""You are a linguistic classifier specializing in Role and Reference Grammar (RRG) Aktionsart.

## FEATURE MATRIX (Van Valin 2005)
{matrix_json}

## CLASSIFICATION RULES — apply in order, stop at first match
{rules_json}

## MORPHOSYNTACTIC EVIDENCE (extracted by Stanza NLP)
Sentence  : {sentence}
Verb lemma: {verb_lemma}
Features  : {morph_context}

## TASK
Before answering, reason inside a <thinking> block following this exact path:

<thinking_instructions>
1. INITIAL STATE CHECK: Is the verb inherently stative (perception, cognition, possession) without agentive control?
   - If yes -> leaning towards 'state'.

2. CAUSATIVE CHECK: Is there a clear Agent causing a change of state in a distinct Patient?
   - If yes -> leaning towards 'causative'.

3. TRANSITIVITY & OBJECT BOUNDARY:
   - Bare/mass object (e.g. 'come pizza') -> atelicity -> 'activity'.
   - Quantized/definite object + aspectual 'se' -> telicity -> 'active_accomplishment'.

4. TEMPORAL DIAGNOSTICS:
   - 'durante X tiempo' natural? -> [-punctual, has duration]
   - 'en X tiempo' natural?      -> [+telic, has endpoint]
   - Combine: [+telic, -punctual] -> accomplishment or active_accomplishment
              [+telic, +punctual] -> achievement
              [-telic, +punctual] -> semelfactive

5. SYNTHESIS: Match features against the CLASSIFICATION RULES above.

6. FALLBACK: If ambiguous, choose the most canonical reading for the lemma.
</thinking_instructions>

After your <thinking> block, write your final answer as:
  ANSWER: <class>

The ANSWER must be exactly one word from:
  state | activity | achievement | accomplishment | semelfactive | active_accomplishment | causative

## EXAMPLES

Sentence: Juan come pizza | Verb: comer | Features: Tense=Pres Reflex=No DefObj=No BareObj=Yes
<thinking>
1. comer is not stative
2. no causation of change in patient
3. bare object 'pizza' -> atelic
4. 'durante horas' natural, 'en horas' not -> [-telic]
5. dynamic, atelic, not punctual -> activity
</thinking>
ANSWER: activity

Sentence: Juan se comio la pizza | Verb: comer | Features: Tense=Past Reflex=Yes DefObj=Yes BareObj=No
<thinking>
1. not stative
2. no distinct patient being changed
3. definite object 'la pizza' + aspectual 'se' -> telic
4. 'durante X' possible, 'en X' possible -> [-punctual, +telic]
5. activity + quantized object -> active_accomplishment
</thinking>
ANSWER: active_accomplishment

Sentence: Juan vio la pelicula | Verb: ver | Features: Tense=Past Reflex=No DefObj=Yes BareObj=No
<thinking>
1. ver is perception, no agentive override
5. -> state
</thinking>
ANSWER: state

Sentence: el nino rompió el juguete | Verb: romper | Features: Tense=Past Reflex=No DefObj=Yes BareObj=No
<thinking>
1. not stative
2. Agent (niño) causes change of state in Patient (juguete) -> causative
</thinking>
ANSWER: causative

## NOW CLASSIFY
Sentence: {sentence}
Verb: {verb_lemma}
Features: {morph_context}
"""


# ---------------------------------------------------------------------------
# CLIENTE OLLAMA
# ---------------------------------------------------------------------------

def _ollama_available() -> bool:
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def _call_ollama(prompt: str) -> str | None:
    payload = json.dumps({
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 250,    # cadena de razonamiento + ANSWER
        }
    }).encode('utf-8')

    req = urllib.request.Request(
        OLLAMA_URL,
        data    = payload,
        headers = {"Content-Type": "application/json"},
        method  = "POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get("response", "").strip()
    except urllib.error.HTTPError as e:
        print(f"[LLM] HTTP {e.code}: {e.read().decode('utf-8')[:300]}")
        return None
    except urllib.error.URLError as e:
        print(f"[LLM] URLError: {e.reason}")
        return None
    except Exception as e:
        print(f"[LLM] Error: {type(e).__name__}: {e}")
        return None



def _parse_class(raw: str | None) -> str | None:
    if not raw:
        return None

    # Strip thinking block if present — answer is always after </thinking>
    if '</thinking>' in raw.lower():
        raw = raw.lower().split('</thinking>')[-1]

    lines = raw.strip().splitlines()

    # 1. Last line with ANSWER:
    for line in reversed(lines):
        stripped = line.strip().lower()
        if stripped.startswith('answer:'):
            candidate = stripped.replace('answer:', '').strip().strip('.,;:!?()"\'* ')
            if candidate in VALID_CLASSES:
                return candidate

    # 2. ANSWER: anywhere
    for line in lines:
        if 'answer:' in line.lower():
            after = line.lower().split('answer:')[-1].strip()
            for token in after.split():
                if token.strip('.,;:!?()"\'* ') in VALID_CLASSES:
                    return token.strip('.,;:!?()"\'* ')

    # 3. Last valid class mentioned (fallback)
    found = None
    for token in raw.lower().replace('\n', ' ').split():
        if token.strip('.,;:!?()"\'* ') in VALID_CLASSES:
            found = token.strip('.,;:!?()"\'* ')
    return found
# ---------------------------------------------------------------------------
# INTERFAZ PÚBLICA
# ---------------------------------------------------------------------------

def classify_with_llm(
    verb_lemma:    str,
    morph_context: str,
    sentence_text: str,
) -> str | None:
    """
    Clasifica la clase aspectual con Qwen2.5:7b via Ollama.
    Retorna str (clase GRR) o None si Ollama no está disponible.
    """
    if not _ollama_available():
        return None
    prompt = _build_prompt(verb_lemma, morph_context, sentence_text)
    raw    = _call_ollama(prompt)
    return _parse_class(raw)


def classify_with_llm_verbose(
    verb_lemma:    str,
    morph_context: str,
    sentence_text: str,
) -> dict:
    """
    Versión con razonamiento completo visible — útil para debug y evaluación.

    Retorna:
      result : str | None  — clase final
      raw    : str | None  — respuesta completa incluyendo chain-of-thought
      model  : str         — modelo usado
    """
    if not _ollama_available():
        return {"result": None, "raw": None, "model": OLLAMA_MODEL}
    prompt = _build_prompt(verb_lemma, morph_context, sentence_text)
    raw    = _call_ollama(prompt)
    return {"result": _parse_class(raw), "raw": raw, "model": OLLAMA_MODEL}


def ollama_status() -> dict:
    available = _ollama_available()
    if available:
        msg = f"Ollama disponible — modelo: {OLLAMA_MODEL}"
    else:
        msg = (
            "Ollama no detectado. El fallback LLM estará desactivado.\n"
            "  Para activarlo:\n"
            "    1. Instala Ollama: https://ollama.com/download\n"
            f"   2. Descarga el modelo: ollama pull {OLLAMA_MODEL}\n"
            "    3. Inicia el servidor: ollama serve"
        )
    return {"available": available, "model": OLLAMA_MODEL, "message": msg}
