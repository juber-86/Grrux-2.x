"""
rrg_morph_classifier.py
=======================
Clasificador aspectual morfosintáctico para GRR.
Opción A del pipeline: lee los rasgos (feats) que Stanza ya produce
y los convierte en clase aspectual GRR, sin modelo externo.

Cubre los casos que el léxico estático (VERB_CLASSES) no puede:
  - Telicidad por reflexivo + objeto definido
      Juan come pizza       → activity
      Juan se comió la pizza → active_accomplishment  (o accomplishment)
  - Perfectividad morfológica
      La ciudad creció      → accomplishment  (BECOME)
      La ciudad crece       → activity        (do')
  - Verbos fuera del léxico con rasgos claros
      El niño pataleó       → semelfactive   (si hay reflex o puntual)

Interfaz pública:
  classify_from_morph(root, all_words) -> str | None
    Retorna la clase GRR o None si no puede decidir (→ pasa al fallback LLM).
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# HELPERS: lectura de rasgos UD
# ---------------------------------------------------------------------------

def _feats(word) -> dict[str, str]:
    """
    Convierte la cadena de feats UD ("Aspect=Perf|Number=Sing|…")
    en un dict {'Aspect': 'Perf', 'Number': 'Sing', …}.
    Devuelve {} si feats es None o '_'.
    """
    raw = getattr(word, 'feats', None)
    if not raw or raw == '_':
        return {}
    result = {}
    for pair in raw.split('|'):
        if '=' in pair:
            k, v = pair.split('=', 1)
            result[k] = v
    return result


def _has_reflexive(root, all_words) -> bool:
    """
    True si hay clítico reflexivo dependiendo del root.

    Stanza español lematiza 'se' como 'él', así que no se puede confiar
    solo en el lemma. Se detecta por cualquiera de estas señales:
      1. feats contiene Reflex=Yes  (el más confiable)
      2. deprel es expl:pv          (clítico pronominal verbal — siempre reflexivo)
      3. text o lemma están en la lista de clíticos conocidos
    """
    reflex_texts  = {'se', 'me', 'te', 'nos', 'os'}
    reflex_lemmas = {'se', 'me', 'te', 'nos', 'os'}
    for w in all_words:
        if w.head == root.id and w.deprel in {'expl:pv', 'expl', 'obj'}:
            feats = _feats(w)
            if (feats.get('Reflex') == 'Yes'              # ← señal primaria
                    or w.deprel == 'expl:pv'              # ← siempre reflexivo
                    or w.text.lower()  in reflex_texts
                    or w.lemma.lower() in reflex_lemmas):
                return True
    return False


def _has_definite_object(root, all_words) -> bool:
    """
    True si el objeto directo del verbo lleva determinante definido
    (el/la/los/las) — señal de télicidad en español.

    Nota: cuando hay clítico reflexivo (se/me), Stanza a veces etiqueta
    el objeto léxico como 'iobj' en lugar de 'obj'. Se comprueban ambos.
    """
    det_definidos = {'el', 'la', 'los', 'las'}
    obj_words = [w for w in all_words
                 if w.head == root.id and w.deprel in {'obj', 'iobj'}]
    for obj in obj_words:
        for w in all_words:
            if w.head == obj.id and w.deprel == 'det':
                if w.text.lower() in det_definidos:
                    return True
    return False


def _has_bare_object(root, all_words) -> bool:
    """
    True si hay objeto directo sin determinante (masa/indefinido):
    "come pizza", "bebe agua" → objeto escueto → atélico.
    Comprueba obj e iobj por la misma razón que _has_definite_object.
    """
    obj_words = [w for w in all_words
                 if w.head == root.id and w.deprel in {'obj', 'iobj'}]
    for obj in obj_words:
        dets = [w for w in all_words
                if w.head == obj.id and w.deprel == 'det']
        if not dets:
            return True
    return False


def _aspect(root) -> str | None:
    """Retorna el valor de Aspect del verbo raíz o None."""
    return _feats(root).get('Aspect')

def _tense(root) -> str | None:
    """Retorna el valor de Tense del verbo raíz o None."""
    return _feats(root).get('Tense')

def _mood(root) -> str | None:
    return _feats(root).get('Mood')

def _verbform(root) -> str | None:
    return _feats(root).get('VerbForm')


# ---------------------------------------------------------------------------
# CLASIFICADOR PRINCIPAL
# ---------------------------------------------------------------------------

# Verbos inherentemente puntuales que no están en el léxico GRR
# y que el morpho puede clasificar con seguridad como semelfactive
_SEMELFACTIVE_CUES = {
    'pestañear', 'titilar', 'chisporrotear', 'parpadear',
    'destellar', 'relampaguear', 'bostezar', 'estornudar', 'toser', 'aplaudir', 'girar'
}

# Verbos de cambio de estado que tampoco están en el léxico
_CHANGE_OF_STATE_SUFFIXES = (
    'arse', 'erse', 'irse',   # reflexivos incoativos: cansarse, romperse
    'ecer',                    # palidecer, oscurecer
    'izar',                    # modernizarse, cristalizar
)


def classify_from_morph(root, all_words, lexicon_class=None) -> str | None:
    """
    Intenta determinar la clase aspectual GRR a partir de rasgos morfosintácticos.

    Reglas aplicadas en orden de precedencia:

    1. Reflexivo + objeto definido + perfectivo  → active_accomplishment
       "Juan se comió la pizza"
    2. Reflexivo + objeto definido (imperfectivo) → accomplishment
       "Juan se come la pizza"  (proceso delimitado)
    3. Objeto escueto (sin det) + actividad      → activity
       "Juan come pizza"
    4. Perfectivo puro sin télico               → achievement  (INGR)
       "Juan llegó / Juan estornudó"
    5. Sufijo incoativo (-arse/-erse + perfectivo) → accomplishment (BECOME)
       "La ciudad creció" / "el hielo se derritió"
    6. Imperfectivo / presente habitual          → activity
       "Juan camina todos los días"
    7. No puede decidir                         → None (→ fallback LLM)

    Parámetros:
      root       : Word de Stanza (el verbo raíz)
      all_words  : lista completa de words de la oración

    Retorna str (clase GRR) o None.
    """
    lemma      = root.lemma.lower() if root.lemma else ''
    asp        = _aspect(root)       # Imp | Perf | Hab | Prog | None
    tense      = _tense(root)        # Past | Pres | Fut | None
    reflex     = _has_reflexive(root, all_words)
    def_obj    = _has_definite_object(root, all_words)
    bare_obj   = _has_bare_object(root, all_words)
    is_perf    = (asp == 'Perf') or (tense == 'Past' and asp not in {'Imp', 'Hab'})

    # ── Regla 1: reflexivo télico perfectivo ──────────────────────────────
    # "se comió la pizza", "se bebió la cerveza"
    if reflex and def_obj and is_perf:
        return 'active_accomplishment'

    # ── Regla 2: reflexivo télico imperfectivo ────────────────────────────
    # "se come la pizza" (delimitado pero no puntual)
    if reflex and def_obj and not is_perf:
        return 'accomplishment'

    # ── Regla 3: objeto escueto → actividad atélica ───────────────────────
    # "come pizza", "bebe agua", "lee libros"
    if bare_obj and not reflex:
        return 'activity'

    # ── Regla 4: perfectivo puro (sin télico) → achievement ──────────────
    # Verbos puntuales o logros: "llegó", "nació", "estalló"
    # También cubre semelfactivos conocidos
    if is_perf and not def_obj and not bare_obj:
        if lemma in _SEMELFACTIVE_CUES:
            return 'semelfactive'
        # Perfectivo sin objeto = achievement por defecto
        return 'achievement'

    # ── Regla 5: sufijo incoativo + perfectivo → accomplishment ──────────
    # "se derritió", "se modernizó", "palideció"
    if is_perf and any(lemma.endswith(suf) for suf in _CHANGE_OF_STATE_SUFFIXES):
        return 'accomplishment'

    # ── Regla 6: imperfectivo → activity ─────────────────────────────────
    if asp in {'Imp', 'Hab', 'Prog'} or (tense == 'Pres' and not reflex):
        return 'activity'

    # No hay suficiente evidencia
    return None


# ---------------------------------------------------------------------------
# RESUMEN DE RASGOS (para debug / logging)
# ---------------------------------------------------------------------------

def morph_summary(root, all_words, lexicon_class=None) -> str:
    """
    Devuelve una cadena legible con los rasgos clave usados en la clasificación.
    Útil para el comentario rrg_morph en el .conllu.

    Ejemplo:
      "Aspect=Perf|Reflex=Yes|DefObj=Yes → active_accomplishment"
    """
    asp     = _aspect(root)  or '–'
    tense   = _tense(root)   or '–'
    reflex  = 'Yes' if _has_reflexive(root, all_words)       else 'No'
    def_obj = 'Yes' if _has_definite_object(root, all_words) else 'No'
    bare    = 'Yes' if _has_bare_object(root, all_words)     else 'No'
    result  = classify_from_morph(root, all_words)
    label   = result if result else 'None (→ fallback)'

    return (f"Aspect={asp} Tense={tense} "
            f"Reflex={reflex} DefObj={def_obj} BareObj={bare} "
            f"→ {label}")
