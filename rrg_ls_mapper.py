"""
rrg_ls_mapper.py
================
Mapeador de Estructura Lógica (LS) basado en la taxonomía de 7 tipos de la
Gramática de Rol y Referencia (Van Valin 2005).

Produce dos representaciones:
  - LS formal:  do'(x, [comer'(x, y)])           — variables abstractas
  - LS léxica:  do'(Juan, [comer'(Juan, pizza)])  — con formas superficiales

Manejo especial de estados copulativos:
  - estar + atributo  → pred'(x)             e.g. broken'(ventana)
  - ser  + predicado  → be'(x, [pred'])       e.g. be'(Juan, [doctor'])
  - estar/ser + prep locativa → be-[prep]'(loc, figura)
                                               e.g. be-in'(biblioteca, Juan)

Compatible con anotaciones de Stanza (UD) para español.

Clasificación aspectual: aspect_classifier (roBERTa + regresores por rasgo
+ árbol de decisión), en modo contextual (Fase 2): combina el embedding
léxico del lema con el embedding del verbo dentro de la oración real.
La cascada anterior (VERB_CLASSES → morph → LLM) está desactivada;
VERB_CLASSES se conserva solo como referencia/datos para otros scripts.
"""

# ---------------------------------------------------------------------------
# IMPORTACIONES DE MÓDULOS OPCIONALES
# Se cargan con try/except para que el mapper funcione aunque los módulos
# extra no estén presentes (compatibilidad hacia atrás).
# ---------------------------------------------------------------------------
try:
    from aspect_classifier import AspectClassifier
    from aspect_classifier.complejo_verbal import extraer_complejo, desde_stanza
    _aspect_clf = AspectClassifier().load()
    _ASPECT_CLF_AVAILABLE = True
except Exception:
    _aspect_clf = None
    _ASPECT_CLF_AVAILABLE = False

# Paso 4: causatividad como parámetro ortogonal ([do'(x,Ø)] CAUSE [β]).
# Si el léxico causativo no está disponible, el mapper sigue funcionando
# sin CAUSE (dict vacío → la cascada nunca dispara por léxico).
try:
    from aspect_classifier.causatividad import (
        aplicar_gate_semelfactive, cargar_lexicon, componer_cause,
        detectar_causatividad, log_candidato)
    _CAUS_LEXICON = cargar_lexicon()
except Exception:
    _CAUS_LEXICON = None

# Etapa 1: enrutado core/periferia consciente de mismatch (precursor
# rule-based del linking algorithm; el linking completo NO está aquí).
from aspect_classifier.nucleo_periferia import (analizar_roles,
                                                objeto_con_numeral_medida,
                                                tiene_delimitador_nuclear)

# Pruebas de Van Valin ESTRUCTURALES: detectan el entorno de prueba (P1-P5)
# en la oración real y licencian coerciones (R1/R2) o solo anotan (R3/R4).
from aspect_classifier.pruebas_estructurales import (aplicar_coerciones,
                                                     detectar_evidencia,
                                                     linea_coherencia)

# Fase LINKING, Etapa L1b: wrappers de periferia en la LS (be-in'/for'/
# yesterday'...). Módulo puro; recibe periferia ya tipada por Etapa 1.
from aspect_classifier.wrappers_ls import componer_wrappers

# Etapa OPERATORS: operadores de la GRR (IF/TNS/ASP/NEG/MOD/STA). NO tocan el
# árbol ni la EL interna — la ENVUELVEN con ⟨ ⟩ en el orden de scope de 2.25,
# POR FUERA de los wrappers de periferia.
from aspect_classifier import operadores as _operadores

# Fase LINKING, Etapa LA1: el linking algorithm explícito (macropapeles por
# AUH, PSA+concordancia, traza de 5 pasos, round-trip). Módulo puro; lee la
# EL ya construida, no la cambia.
from aspect_classifier import linking as _linking
from aspect_classifier.rrg_variables import canonical_variables

# Fase LINKING, Etapa L2.5: Estructuras Lógicas ditransitivas (recipiente).
# Si el léxico ditransitivo no está disponible, el mapper sigue funcionando
# sin él (dict vacío → el trigger nunca dispara por léxico, cae a default).
try:
    from aspect_classifier.ditransitivas import (construir_ditransitiva,
                                                  cargar_lexicon as
                                                  cargar_lexicon_ditrans,
                                                  log_candidato as
                                                  log_candidato_ditrans)
    _DITRANS_LEXICON = cargar_lexicon_ditrans()
except Exception:
    _DITRANS_LEXICON = None

# Clases del aspect_classifier (Vendler/Van Valin) → tipos LS del mapper
_ASPECT_TO_LS = {
    'State':                 'state',
    'Activity':              'activity',
    'Achievement':           'achievement',
    'Semelfactive':          'semelfactive',
    'Accomplishment':        'accomplishment',
    'Active_Accomplishment': 'active_accomplishment',
    'State_Activity':        'state',   # ambiguo ±dyn: se trata como estado
}

# ---------------------------------------------------------------------------
# 1. LÉXICO ASPECTUAL
# ---------------------------------------------------------------------------
VERB_CLASSES = {
    # Estados (States) — pred'(x) / pred'(x,y)
    'saber':        'state',
    'amar':         'state',
    'estar':        'state',
    'ser':          'state',
    'tener':        'state',
    'conocer':      'state',
    'creer':        'state',
    'parecer':      'state',
    'odiar':        'state',
    'preferir':     'state',
    'desear':       'state',
    'necesitar':    'state',
    'recordar':     'state',
    'olvidar':      'state',
    'temer':        'state',
    'respetar':     'state',
    'admirar':      'state',
    'ignorar':      'state',
    'pertenecer':   'state',
    'contener':     'state',
    'merecer':      'state',
    'importar':     'state',
    'suponer':      'state',
    'entender':     'state',
    'dudar':        'state',
    'depender':     'state',
    'costar':       'state',
    'valer':        'state',

    # Actividades (Activities) — do'(x, [pred'(x,y)])
    'caminar':      'activity',
    'cantar':       'activity',
    'llorar':       'activity',
    'comer':        'activity',
    'correr':       'activity',
    'nadar':        'activity',
    'hablar':       'activity',
    'trabajar':     'activity',
    'leer':         'activity',
    'escribir':     'activity',
    'bailar':       'activity',
    'jugar':        'activity',
    'conducir':     'activity',
    'dibujar':      'activity',
    'volar':        'activity',
    'respirar':     'activity',
    'escuchar':     'activity',
    'mirar':        'activity',
    'gritar':       'activity',
    'susurrar':     'activity',
    'pensar':       'activity',
    'empujar':      'activity',
    'jalar':        'activity',
    'teclear':      'activity',
    'estudiar':     'activity',
    'investigar':   'activity',
    'viajar':       'activity',
    'explorar':     'activity',
    'pelear':       'activity',
    'charlar':      'activity',

    # Logros (Achievements) — INGR pred'(x)
    'estallar':     'achievement',
    'reventar':     'achievement',
    'llegar':       'achievement',
    'morir':        'achievement',
    'nacer':        'achievement',
    'reconocer':    'achievement',
    'despertar':    'achievement',
    'caer':         'achievement',
    'aparecer':     'achievement',
    'desaparecer':  'achievement',
    'explotar':     'achievement',
    'chocar':       'achievement',
    'ganar':        'achievement',
    'perder':       'achievement',
    'encontrar':    'achievement',
    'romper':       'achievement',
    'terminar':     'achievement',
    'empezar':      'achievement',
    'alcanzar':     'achievement',
    'fallar':       'achievement',
    'capturar':     'achievement',
    'escapar':      'achievement',
    'tropezar':     'achievement',
    'encender':     'achievement',
    'apagar':       'achievement',

    # Realizaciones (Accomplishments) — BECOME pred'(x)
    'secarse':      'accomplishment',
    'derretirse':   'accomplishment',
    'construir':    'accomplishment',
    'aprender':     'accomplishment',
    'madurar':      'accomplishment',
    'envejecer':    'accomplishment',
    'enfermarse':   'accomplishment',
    'curarse':      'accomplishment',
    'cansarse':     'accomplishment',
    'llenarse':     'accomplishment',
    'vaciarse':     'accomplishment',
    'romperse':     'accomplishment',
    'congelarse':   'accomplishment',
    'calentarse':   'accomplishment',
    'enfriarse':    'accomplishment',
    'oscurecerse':  'accomplishment',
    'aclararse':    'accomplishment',
    'hincharse':    'accomplishment',
    'desarrollarse':'accomplishment',
    'crecer':       'accomplishment',
    'mejorar':      'accomplishment',
    'empeorar':     'accomplishment',
    'organizarse':  'accomplishment',
    'enamorarse':   'accomplishment',
    'convertirse':  'accomplishment',

    # Semelfactivos (Semelfactives) — SEML pred'(x)
    'estornudar':   'semelfactive',
    'parpadear':    'semelfactive',
    'golpear':      'semelfactive',
    'toser':        'semelfactive',
    'saltar':       'semelfactive',
    'bostezar':     'semelfactive',
    'guiñar':       'semelfactive',
    'patalear':     'semelfactive',
    'aplaudir':     'semelfactive',
    'silbar':       'semelfactive',
    'vislumbrar':   'semelfactive',
    'rozar':        'semelfactive',
    'picar':        'semelfactive',
    'temblar':      'semelfactive',
    'agitar':       'semelfactive',
    'pellizcar':    'semelfactive',
    'mordisquear':  'semelfactive',
    'sacudir':      'semelfactive',
    'chisporrotear':'semelfactive',
    'destellar':    'semelfactive',
    'frotar':       'semelfactive',
    'chapotear':    'semelfactive',

    # Causativos (Causatives) — α CAUSE β
    'abrir':        'causative',
    'cerrar':       'causative',
    'fundir':       'causative',
    'quemar':       'causative',
    'matar':        'causative',
    'asustar':      'causative',
    'alegrar':      'causative',
    'entristecer':  'causative',
    'enfriar':      'causative',
    'calentar':     'causative',
    'secar':        'causative',
    'mojar':        'causative',
    'llenar':       'causative',
    'vaciar':       'causative',
    'detener':      'causative',
    'iniciar':      'causative',
    'derribar':     'causative',
    'inflar':       'causative',
    'envenenar':    'causative',
    'curar':        'causative',
    'cansar':       'causative',
    'confundir':    'causative',
    'iluminar':     'causative',
}

# Verbos copulativos — requieren análisis especial de su complemento
COPULATIVE_VERBS = {'ser', 'estar', 'parecer', 'quedar', 'permanecer', 'resultar'}

# Verbo → realización activa cuando hay objeto télico
ACTIVE_ACCOMPLISHMENT_TRIGGERS = {
    'escribir', 'pintar', 'construir', 'cocinar', 'leer',
}


# ---------------------------------------------------------------------------
# 2. PREPOSICIONES LOCATIVAS → predicado be-X'
# ---------------------------------------------------------------------------
LOCATIVE_PREP_MAP = {
    'en':        'be-in',
    'dentro':    'be-inside',
    'fuera':     'be-outside',
    'afuera':    'be-outside',
    'sobre':     'be-on',
    'encima':    'be-above',
    'bajo':      'be-under',
    'debajo':    'be-under',
    'detrás':    'be-behind',
    'tras':      'be-behind',
    'delante':   'be-in-front-of',
    'frente':    'be-in-front-of',
    'entre':     'be-between',
    'cerca':     'be-near',
    'junto':     'be-next-to',
    'arriba':    'be-above',
    'abajo':     'be-under',
    'contra':    'be-against',
    'ante':      'be-before',
}


# ---------------------------------------------------------------------------
# 3. MAPEO UD DEPREL → FUNCIÓN LÓGICA GRR
# ---------------------------------------------------------------------------
DEPREL_TO_LOGFUNC = {
    'nsubj':  'Agent',
    'obj':    'Patient',
    'iobj':   'Recipient',
    'obl':    'Location',
    'advmod': 'Modifier',
    'xcomp':  'Theme',
    'ccomp':  'Theme',
    'nmod':   'Theme',
}

def get_logical_function(deprel: str) -> str:
    return DEPREL_TO_LOGFUNC.get(deprel, 'Theme')


# ---------------------------------------------------------------------------
# 4. DETECCIÓN DE ASPECTO AUXILIAR
# ---------------------------------------------------------------------------
def detect_aux_aspect(root_word, all_words) -> str | None:
    """
    Busca auxiliares aspectuales dependientes del verbo principal.
    Retorna: 'prog' | 'complet' | None
    """
    aux_words = [w for w in all_words if w.head == root_word.id and w.deprel == 'aux']
    for aux in aux_words:
        lemma = aux.lemma.lower()
        if lemma == 'estar':
            return 'prog'
        if lemma == 'haber':
            return 'complet'
    return None


# ---------------------------------------------------------------------------
# 5. DETECCIÓN DE SUBTIPO DE ESTADO COPULATIVO
# ---------------------------------------------------------------------------
def detect_copula_info(root_word, all_words) -> dict | None:
    """
    En UD español, las oraciones copulativas tienen dos estructuras posibles:

    A) Predicado adjetival/nominal — root es ADJ o NOUN:
         "la ventana está rota"  → root=rota(ADJ),  cop=estar(AUX)
         "Juan es tonto"         → root=tonto(ADJ), cop=ser(AUX)
         "Juan es médico"        → root=médico(NOUN), cop=ser(AUX)

    B) Locativo — root es el verbo estar (VERB):
         "Juan está en la biblioteca" → root=estar(VERB), obl=biblioteca

    Retorna dict con:
      subtype    : 'locative' | 'attributive_estar' | 'attributive_ser'
      cop_lemma  : str | None    — lema del cop ('ser' | 'estar' | None)
      prep_pred  : str | None    — e.g. 'be-in', 'be-on'
      loc_word   : Word | None   — nominal de la locación
      attr_word  : Word | None   — la raíz adjetival/nominal (el atributo)

    Retorna None si la oración no es copulativa.
    """
    root_upos   = root_word.upos   # 'VERB', 'ADJ', 'NOUN', 'PROPN', etc.
    root_lemma  = root_word.lemma.lower()

    # ── CASO A: raíz es ADJ o NOUN con dependiente 'cop' ──────────────────
    if root_upos in {'ADJ', 'NOUN', 'PROPN'}:
        cop_words = [w for w in all_words
                     if w.head == root_word.id and w.deprel == 'cop']
        if cop_words:
            cop_lemma = cop_words[0].lemma.lower()
            if cop_lemma in COPULATIVE_VERBS:
                subtype = ('attributive_estar'
                           if cop_lemma == 'estar'
                           else 'attributive_ser')
                return {
                    'subtype':   subtype,
                    'cop_lemma': cop_lemma,
                    'prep_pred': None,
                    'loc_word':  None,
                    'attr_word': root_word,   # el adjetivo/nombre ES el atributo
                }

    # ── CASO B: raíz es VERB copulativo con complemento locativo ──────────
    if root_upos == 'VERB' and root_lemma in COPULATIVE_VERBS:
        # Buscar obl con preposición locativa
        obl_words = [w for w in all_words
                     if w.head == root_word.id and w.deprel == 'obl']
        for obl in obl_words:
            case_words = [w for w in all_words
                          if w.head == obl.id and w.deprel == 'case']
            for case_w in case_words:
                prep_lemma = case_w.lemma.lower()
                if prep_lemma in LOCATIVE_PREP_MAP:
                    return {
                        'subtype':   'locative',
                        'cop_lemma': root_lemma,
                        'prep_pred': LOCATIVE_PREP_MAP[prep_lemma],
                        'loc_word':  obl,
                        'attr_word': None,
                    }

        # Buscar advmod locativo simple ("aquí", "allí")
        advmod_words = [w for w in all_words
                        if w.head == root_word.id and w.deprel == 'advmod']
        for adv in advmod_words:
            if adv.lemma.lower() in LOCATIVE_PREP_MAP:
                return {
                    'subtype':   'locative',
                    'cop_lemma': root_lemma,
                    'prep_pred': LOCATIVE_PREP_MAP[adv.lemma.lower()],
                    'loc_word':  adv,
                    'attr_word': None,
                }

    # No es copulativa
    return None


# ---------------------------------------------------------------------------
# 6. CONSTRUCTOR DE LS
# ---------------------------------------------------------------------------
def build_ls(verb_lemma: str, args: dict, verb_class: str,
             aux_asp: str | None = None) -> dict:
    """
    Construye la cadena LS formal y léxica según la taxonomía GRR de 7 tipos.

    Parámetros:
      verb_lemma : lema del verbo principal
      args       : {'x': 'Juan', 'y': 'pizza', '_loc_info': {...}, ...}
      verb_class : state | activity | achievement | accomplishment |
                   semelfactive | active_accomplishment | causative
      aux_asp    : 'prog' | 'complet' | None

    Retorna:
      {'formal': str, 'lexical': str}
    """
    x1_var = 'x'
    x2_var = 'y' if 'y' in args else None
    x1_lex = args.get('x', 'x')
    x2_lex = args.get('y', None)

    pred_name = f"{verb_lemma}'"

    def pred_formal(v1, v2_var):
        return f"{pred_name}({v1}, {v2_var})" if v2_var else f"{pred_name}({v1})"

    def pred_lexical(l1, l2_lex):
        return f"{pred_name}({l1}, {l2_lex})" if l2_lex else f"{pred_name}({l1})"

    # ── Fase LINKING, LA1 §1: posiciones AUH de cada predicado genérico ────
    # (helpers locales — evitan repetir la misma rama 1_pred_xy/arg_estado o
    # 1_do/2_pred_xy en cada clase de verbo_class). Ver docstring de
    # aspect_classifier.linking para las 5 posiciones y su justificación.
    def _estructura_pred_generico(pred, l1_lex, l2_lex):
        if l2_lex:
            return [_linking.frame(pred, _linking.arg(l1_lex, "1_pred_xy"),
                                   _linking.arg(l2_lex, "2_pred_xy"))]
        return [_linking.frame(pred, _linking.arg(l1_lex, "arg_estado"))]

    def _estructura_do(l1_lex, l2_lex, pred):
        frames = [_linking.frame("do'", _linking.arg(l1_lex, "1_do"))]
        if l2_lex:
            frames.append(_linking.frame(pred, _linking.arg(l2_lex, "2_pred_xy")))
        return frames

    # ── Construir según clase ──────────────────────────────────────────────

    if verb_class == 'state':
        loc_info = args.get('_loc_info')

        # ── LOCATIVO: be-[prep]'(locación, figura) ──────────────────────
        if loc_info and loc_info['subtype'] == 'locative':
            prep_pred = loc_info['prep_pred']          # e.g. 'be-in'
            loc_lex   = loc_info.get('loc_lex', 'loc')

            figura_lex = args.get('y', 'figura')
            # Posiciones locativas: x=locación, y=figura.
            f = f"{prep_pred}'(x, y)"
            l = f"{prep_pred}'({loc_lex}, {figura_lex})"
            # La figura (y, lo ubicado) es el argumento de estado por
            # defecto (Undergoer); el lugar NO compite por macropapel (NMR
            # — decisión de esta etapa, documentada: las locaciones son
            # oblicuas para efectos de linking, igual que el dativo).
            estructura = [_linking.frame(f"{prep_pred}'",
                                         _linking.arg(loc_lex, "1_pred_xy", nmr=True),
                                         _linking.arg(figura_lex, "2_pred_xy"))]

        # ── ATRIBUTIVO con ESTAR: pred'(x) ──────────────────────────────
        #    "La ventana está rota" → broken'(ventana)
        elif loc_info and loc_info['subtype'] == 'attributive_estar':
            attr_word = loc_info.get('attr_word')
            if attr_word:
                attr_pred = f"{attr_word.lemma.lower()}'"
                f = f"{attr_pred}({x1_var})"
                l = f"{attr_pred}({x1_lex})"
                estructura = [_linking.frame(attr_pred, _linking.arg(x1_lex, "arg_estado"))]
            else:
                # Sin atributo detectado: fallback genérico
                f = pred_formal(x1_var, x2_var)
                l = pred_lexical(x1_lex, x2_lex)
                estructura = _estructura_pred_generico(pred_name, x1_lex, x2_lex)

        # ── ATRIBUTIVO / PREDICATIVO con SER: be'(x, [pred']) ───────────
        #    "Juan es médico" → be'(Juan, [doctor'])
        elif loc_info and loc_info['subtype'] == 'attributive_ser':
            attr_word = loc_info.get('attr_word')
            if attr_word:
                attr_pred = f"{attr_word.lemma.lower()}'"
                f = f"be'({x1_var}, [{attr_pred}])"
                l = f"be'({x1_lex}, [{attr_pred}])"
                estructura = [_linking.frame("be'", _linking.arg(x1_lex, "arg_estado"))]
            elif x2_lex:
                attr_pred = f"{x2_lex.lower()}'"
                f = f"be'({x1_var}, [{attr_pred}])"
                l = f"be'({x1_lex}, [{attr_pred}])"
                estructura = [_linking.frame("be'", _linking.arg(x1_lex, "arg_estado"))]
            else:
                f = pred_formal(x1_var, x2_var)
                l = pred_lexical(x1_lex, x2_lex)
                estructura = _estructura_pred_generico(pred_name, x1_lex, x2_lex)

        # ── ESTADO GENÉRICO (saber, amar, tener…) ───────────────────────
        else:
            f = pred_formal(x1_var, x2_var)
            l = pred_lexical(x1_lex, x2_lex)
            estructura = _estructura_pred_generico(pred_name, x1_lex, x2_lex)

    elif verb_class == 'activity':
        f = f"do'({x1_var}, [{pred_formal(x1_var, x2_var)}])"
        l = f"do'({x1_lex}, [{pred_lexical(x1_lex, x2_lex)}])"
        estructura = _estructura_do(x1_lex, x2_lex, pred_name)

    elif verb_class == 'achievement':
        f = f"INGR {pred_formal(x1_var, x2_var)}"
        l = f"INGR {pred_lexical(x1_lex, x2_lex)}"
        estructura = _estructura_pred_generico(pred_name, x1_lex, x2_lex)

    elif verb_class == 'accomplishment':
        f = f"BECOME {pred_formal(x1_var, x2_var)}"
        l = f"BECOME {pred_lexical(x1_lex, x2_lex)}"
        estructura = _estructura_pred_generico(pred_name, x1_lex, x2_lex)

    elif verb_class == 'semelfactive':
        f = f"SEML {pred_formal(x1_var, x2_var)}"
        l = f"SEML {pred_lexical(x1_lex, x2_lex)}"
        estructura = _estructura_pred_generico(pred_name, x1_lex, x2_lex)

    elif verb_class == 'active_accomplishment':
        if x2_var is None:
            # Sin Undergoer nuclear la plantilla AA no puede saturarse:
            # NUNCA emitir consumed'(None); degradar a actividad.
            f = f"do'({x1_var}, [{pred_formal(x1_var, None)}])"
            l = f"do'({x1_lex}, [{pred_lexical(x1_lex, None)}])"
            estructura = _estructura_do(x1_lex, None, pred_name)
        else:
            f = (f"do'({x1_var}, [{pred_formal(x1_var, x2_var)}])"
                 f" & INGR consumed'({x2_var})")
            l = (f"do'({x1_lex}, [{pred_lexical(x1_lex, x2_lex)}])"
                 f" & INGR consumed'({x2_lex})")
            estructura = _estructura_do(x1_lex, x2_lex, pred_name)

    elif verb_class == 'causative':
        f = (f"[do'({x1_var}, Ø)]"
             f" CAUSE [BECOME {pred_formal(x2_var or 'y', None)}]")
        l = (f"[do'({x1_lex}, Ø)]"
             f" CAUSE [BECOME {pred_lexical(x2_lex or 'y', None)}]")
        # Rama MUERTA en el pipeline vivo (ningún verb_class del clasificador
        # produce 'causative' — la causatividad real se compone aparte, ver
        # causatividad.componer_cause); estructura consistente por si algún
        # test llama a build_ls directamente con esta clase.
        estructura = [_linking.frame("do'", _linking.arg(x1_lex, "1_do"))]
        if x2_lex:
            estructura.append(_linking.frame(pred_name, _linking.arg(x2_lex, "arg_estado")))

    else:
        f = pred_formal(x1_var, x2_var)
        l = pred_lexical(x1_lex, x2_lex)
        estructura = _estructura_pred_generico(pred_name, x1_lex, x2_lex)

    # ── Aspecto auxiliar: YA NO se escribe en la EL ───────────────────────
    # Etapa OPERATORS_2 §1. Hasta aquí, `aux_asp` metía en la EL un envoltorio
    # `prog(…)` / `complet(…)`. Eso es un PSEUDO-PREDICADO: el aspecto es una
    # categoría gramatical cerrada, y en Van Valin su lugar es ⟨ASP PROG⟩ /
    # ⟨ASP PERF⟩ —no un predicado de la EL, que está reservada al contenido
    # LÉXICO (`comer'`, `be-in'`, `yesterday'`)—. `operadores.detectar_operadores`
    # ya deriva ASP de las MISMAS señales (los auxiliares 'haber'/'estar'),
    # así que la información no se pierde: deja de estar DUPLICADA.
    #
    # Además de ortodoxia, es una precondición de LA1: el linking algorithm
    # leerá POSICIONES de la EL para asignar macropapeles por la jerarquía
    # Actor-Padecedor, y estas capas falsas desplazaban los argumentos un
    # nivel hacia dentro, ensuciando esa lectura.
    #
    # `aux_asp` se conserva en la firma: sigue siendo insumo de
    # `pruebas_estructurales` (P1 progresivo) y de la propia detección de ASP.
    #
    # `estructura` (Fase LINKING, LA1 §1): la representación posicional AUH
    # de este mismo LS, para que `linking.asignar_macropapeles` no tenga que
    # volver a parsear `f`/`l`. Se genera SIEMPRE (no gated por
    # `linking.enabled` — es barata, y así el flag solo controla si el
    # MAPPER la usa, no si build_ls la calcula).
    return {'formal': f, 'lexical': l, 'estructura': estructura}


def _resumen_pruebas(detalle: dict) -> str:
    """Resumen legible de los veredictos del corroborador Van Valin, para
    incrustar en aspect_note (lo renderiza el `morph_note` existente, sin
    tocar gruxx_ai1.py). p. ej.:
        Pruebas VV: p1 progresivo✗→puntual · p45 en<durante→atélico · p6 —
    Un rasgo/prueba sin señal se muestra como "—".
    """
    partes = []
    p1 = detalle.get("p1_progresivo")
    if p1 is not None:
        partes.append("p1 progresivo✓→durativo" if p1["score"] >= 0.5
                      else "p1 progresivo✗→puntual")
    p45 = detalle.get("p45_telicidad")
    if p45 is not None:
        partes.append("p45 en>durante→télico" if p45["score"] >= 0.5
                      else "p45 en<durante→atélico")
    p6 = detalle.get("p6_participial")
    if p6 is not None:
        partes.append("p6 resultativo✓" if p6["score"] >= 0.5 else "p6 —")
    return "Pruebas VV: " + " · ".join(partes) if partes else ""


def debe_degradar_por_objeto_desnudo(verb_class: str, sujeto_agentivo: bool,
                                     obj_delimita: bool,
                                     clase_lexica: str | None) -> bool:
    """Gate composicional G-obj, aislado para auditoría y regresión.

    Solo una base léxicamente durativa puede degradarse a actividad por falta
    de delimitador. Un Achievement léxico como ``explotar`` no contiene un
    objeto incremental omitido: su único argumento es el padecedor.
    """
    return (
        verb_class in ("semelfactive", "achievement", "accomplishment",
                       "active_accomplishment")
        and sujeto_agentivo
        and not obj_delimita
        and clase_lexica in ("activity", "active_accomplishment")
    )


# ---------------------------------------------------------------------------
# 6.5 ETAPA OPERATORS — operadores sobre la EL ya construida
# ---------------------------------------------------------------------------
def _calcular_operadores(toks: list[dict], root_id: int, aux_asp: str | None,
                         sent_text: str = "") -> dict:
    """Operadores de la cláusula, o `{}` si la etapa está apagada.

    Se calcula ANTES de componer los wrappers de periferia (OPERATORS_2 §1):
    su resultado decide qué elementos NO deben envolverse como predicados
    porque ya se representan como operador.
    """
    cfg = (_aspect_clf.config.get('operadores', {})
           if _ASPECT_CLF_AVAILABLE else {})
    if not cfg.get('enabled', True):
        return {}
    ops = _operadores.detectar_operadores(toks, root_id, aux_asp, cfg)

    # Perífrasis de frontera que todavía no son operador: no cambian nada,
    # solo se loguean para curaduría (mismo criterio que ditransitivas).
    for p in _operadores.perifrasis_no_cubiertas(toks, root_id, cfg):
        try:
            _operadores.log_perifrasis(p['lema'], sent_text)
        except Exception:
            pass   # el logueo NUNCA puede romper un análisis
    return ops


def _anotar_operadores(salida: dict, toks: list[dict], root_id: int,
                       aux_asp: str | None, sent_text: str = "",
                       ops: dict | None = None) -> dict:
    """Añade al dict de salida del mapper las tres claves de la etapa
    OPERATORS y devuelve el mismo dict.

      operadores      : dict crudo {OP: {valor, estrato, origen}}
      ls_formal_ops   : `ls_formal`  envuelta con ⟨ ⟩
      ls_lexical_ops  : `ls_lexical` envuelta con ⟨ ⟩

    Se llama SIEMPRE AL FINAL, después de los wrappers de periferia: los
    operadores envuelven POR FUERA de todo lo demás —
    `⟨IF DEC ⟨TNS PAST ⟨yesterday'(be-in'(parque, [do'(…)]))⟩⟩⟩`.

    `ls_formal`/`ls_lexical` NO se tocan: la EL interna de las dianas
    históricas queda byte a byte igual y las versiones envueltas viajan en
    claves NUEVAS. Con `operadores.enabled: false` no se añade ninguna clave
    y la salida es idéntica a la de antes de esta etapa.
    """
    if ops is None:
        ops = _calcular_operadores(toks, root_id, aux_asp, sent_text)
    if not ops:
        return salida

    salida['operadores'] = ops
    salida['ls_formal_ops'] = _operadores.envolver_ls(salida.get('ls_formal', ''), ops)
    salida['ls_lexical_ops'] = _operadores.envolver_ls(salida.get('ls_lexical', ''), ops)
    return salida


# ---------------------------------------------------------------------------
# 7. FUNCIÓN PRINCIPAL: procesar una oración Stanza  (aqui se debe hacer cambios)
# ---------------------------------------------------------------------------
def _mapear_argumentos_genericos(roles: dict) -> tuple[dict, dict, list[str], list[str]]:
    """Asigna x/y por función semántica, nunca por orden superficial.

    ``z`` queda reservado a las plantillas compuestas ditransitivas. Un tercer
    participante sin posición licenciada se conserva en ``roles`` para el
    diagnóstico, pero no se fuerza dentro de un predicado primitivo.
    """
    args: dict[str, str] = {}
    id_a_var: dict[int, str] = {}
    meta: list[str] = []
    diagnosticos: list[str] = []
    core = list(roles.get('core') or [])
    actores = [c for c in core if (c.get('macropapel') or '').startswith('Actor')]
    padecedores = [c for c in core
                    if (c.get('macropapel') or '').startswith('Undergoer')]
    otros = [c for c in core if c not in actores and c not in padecedores]

    tiene_se_sin_actor = any(e['fuente'] in ('se_pasivo', 'se_impersonal')
                             for e in roles.get('agx') or [])
    if roles.get('actor_implicito') is not None:
        etiqueta = roles['actor_implicito']['etiqueta']
        args['x'] = etiqueta
        meta.append(f"x:{etiqueta},pro-drop,Actor(implícito)")
    elif tiene_se_sin_actor:
        args['x'] = 'Ø'
        meta.append("x:Ø,—,actor inespecificado (se)")

    def asignar(var: str, c: dict) -> None:
        if var in args:
            diagnosticos.append(
                f"argumento {c['text']!r} ({c['deprel']}) sin posición "
                "licenciada en la EL seleccionada"
            )
            return
        args[var] = c['text']
        id_a_var[c['id']] = var
        meta.append(f"{var}:{c['text']},{c['deprel']},{c['macropapel']}")

    # La pasiva queda resuelta aquí: el obl:agent/Actor recibe x aunque siga
    # superficialmente al nsubj:pass/Undergoer.
    if actores:
        if 'x' not in args:
            asignar('x', actores[0])
        else:
            diagnosticos.extend(
                f"argumento {c['text']!r} ({c['deprel']}) sin posición licenciada "
                "en la EL seleccionada" for c in actores
            )
    if padecedores:
        asignar('y' if 'x' in args else 'x', padecedores[0])

    for c in actores[1:] + padecedores[1:] + otros:
        disponible = next((v for v in ('x', 'y') if v not in args), None)
        if disponible is None:
            diagnosticos.append(
                f"argumento {c['text']!r} ({c['deprel']}) sin posición "
                "licenciada en la EL seleccionada"
            )
        else:
            asignar(disponible, c)
    return args, id_a_var, meta, diagnosticos


def map_sentence_to_ls(sentence) -> dict:
    """
    Recibe un objeto sentence de Stanza y retorna el análisis LS completo.

    Manejo de copulativas (UD español):
      - root ADJ/NOUN + cop(ser/estar) → estado atributivo
      - root VERB(estar) + obl(prep locativa) → estado locativo
      - root VERB(normal) → clases aspectuales estándar

    Retorna dict con:
      ls_type    : clase aspectual GRR
      ls_formal  : LS con variables abstractas
      ls_lexical : LS con formas léxicas superficiales
      args_map   : string para comentario rrg_args
      variables  : dict {var -> forma_léxica}
    """
    words = sentence.words

    # ── Raíz ──────────────────────────────────────────────────────────────
    root = next((w for w in words if w.head == 0), None)
    if root is None:
        return _empty_ls()

    # Correcciones de lemas mal generados por Stanza (es)
    LEMA_FIXES = {'comir': 'comer', 'secuir': 'secar',
                  'derritir': 'derretir', 'tosear': 'toser',
                  'estudir': 'estudiar', 'llueve': 'llover'}

    # ── Detectar si es oración copulativa ─────────────────────────────────
    cop_info = detect_copula_info(root, words)

    if cop_info is not None:
        # El sujeto siempre es nsubj dependiente de la raíz
        subj = next(
            (w for w in words if w.head == root.id and w.deprel == 'nsubj'),
            None
        )
        figura_lex = subj.text if subj else 'x'

        # Para locativos añadimos el lexema del lugar
        if cop_info['subtype'] == 'locative' and cop_info['loc_word']:
            cop_info['loc_lex'] = cop_info['loc_word'].text
            loc_word = cop_info['loc_word']
            args = {'x': loc_word.text, 'y': figura_lex, '_loc_info': cop_info}
            variables = {'x': loc_word.text, 'y': figura_lex}
            id_a_var = {loc_word.id: 'x'}
            if subj is not None:
                id_a_var[subj.id] = 'y'
            arg_meta = (f"x:{loc_word.text},{loc_word.deprel},NMR(Locación); "
                        f"y:{figura_lex},nsubj,Undergoer(Figura)")
        else:
            args = {'x': figura_lex, '_loc_info': cop_info}
            variables = {'x': figura_lex}
            id_a_var = {subj.id: 'x'} if subj is not None else {}
            arg_meta = f"x:{figura_lex},nsubj,Undergoer"

        ls = build_ls(
            verb_lemma = cop_info.get('cop_lemma', 'ser'),
            args       = args,
            verb_class = 'state',
            aux_asp    = None,
        )

        toks_cop = desde_stanza(words)
        salida = {
            'ls_type':    'state',
            'ls_formal':  ls['formal'],
            'ls_lexical': ls['lexical'],
            'verb_lemma': cop_info.get('cop_lemma') or root.lemma.lower(),
            'args_map':   arg_meta,
            'variables':  canonical_variables(variables),
            'id_a_var':   id_a_var,
            'cls_source': 'lexicon',
            'morph_note': '',
            'root_id':    root.id,
            'core': ([{"id": cop_info['loc_word'].id,
                       "text": cop_info['loc_word'].text,
                       "deprel": cop_info['loc_word'].deprel,
                       "macropapel": "NMR(Locación)"},
                      {"id": subj.id, "text": figura_lex,
                       "deprel": "nsubj", "macropapel": "Undergoer"}]
                     if cop_info['subtype'] == 'locative' and subj is not None
                     else ([{"id": subj.id, "text": figura_lex,
                             "deprel": "nsubj", "macropapel": "Undergoer"}]
                           if subj is not None else [])),
            'periferia': [],
            'agx': [],
            'impersonal': False,
            'actor_implicito': None,
            'wrappers': [],
            'diagnosticos_analisis': [],
        }

        # Fase LINKING, Etapa LA1 (también en copulativas: "Juan es médico"
        # tiene macropapel/PSA/concordancia igual que cualquier estado).
        # Sin `roles`/`agx`/`caus` en esta rama (no pasa por
        # nucleo_periferia.analizar_roles) — se le da la estructura mínima
        # equivalente. Sin §3 (reconciliación): `arg_meta` etiqueta el
        # macropapel como "Agent" (literal preexistente, no "Actor"/
        # "Undergoer" — inconsistencia ajena a esta etapa), reconciliar
        # contra eso solo generaría ruido, no hallazgos.
        linking_cfg = _aspect_clf.config.get('linking', {}) if _ASPECT_CLF_AVAILABLE else {}
        if linking_cfg.get('enabled', True):
            estructura = ls.get('estructura', [])
            if subj is not None:
                texto_a_id = {figura_lex: subj.id}
                if cop_info['subtype'] == 'locative' and cop_info.get('loc_word'):
                    texto_a_id[cop_info['loc_word'].text] = cop_info['loc_word'].id
                _linking.enriquecer_ids(estructura, texto_a_id)
            resultado_linking = _linking.analizar_linking(
                estructura, {'core': [], 'periferia': [], 'impersonal': False}, [],
                None, toks_cop, root.id, 'state',
                {'nombre': 'copulativa', 'fuente': 'léxico'})
            salida['ls_estructura'] = estructura
            salida['linking'] = resultado_linking

        # Etapa OPERATORS: las copulativas también llevan operadores (el
        # tiempo y la fuerza ilocutiva viven en el `cop`, que `verbo_finito`
        # sabe encontrar cuando la raíz es ADJ/NOUN y no es finita).
        return _anotar_operadores(salida, toks_cop, root.id, None,
            ' '.join(w.text for w in words))

    # ── Raíz verbal normal ────────────────────────────────────────────────
    verb_lemma = LEMA_FIXES.get(root.lemma.lower(), root.lemma.lower())

    # Tokens UD (una sola vez, con el lema del root ya corregido): los usan
    # el enrutado core/periferia, el complejo verbal y la causatividad.
    toks = [{**t, "lemma": verb_lemma} if t["id"] == root.id else t
            for t in desde_stanza(words)]

    # ── Etapa 1: core (argumentos semánticos) vs periferia (adjuntos) ─────
    # Sintaxis y semántica no son isomorfas: obl es periferia por defecto
    # (antes se barría como argumento y "tres horas" acababa de Actor).
    np_cfg = _aspect_clf.config.get('nucleo_periferia', {}) if _ASPECT_CLF_AVAILABLE else {}
    roles = analizar_roles(toks, root.id, np_cfg)

    args, id_a_var, arg_meta_parts, diagnosticos = _mapear_argumentos_genericos(roles)
    if roles['impersonal']:
        arg_meta_parts.append("—,impersonal,sin argumento semántico")
    if roles['periferia']:
        detalle = ", ".join(f"{p['text']}({p['deprel']}/{p['tipo']})"
                            for p in roles['periferia'])
        arg_meta_parts.append(f"Periferia: {detalle}")

    # ── Clase aspectual — solo aspect_classifier (roBERTa) ───────────────
    #
    # Fase 1+2: el vector difuso [stat, dyn, tel, pun] se obtiene combinando
    # el embedding léxico (oración canónica) con el embedding del verbo en
    # la oración real (contextual), y el árbol de decisión asigna la clase.
    # La cascada anterior (VERB_CLASSES → morph → LLM) queda desactivada.

    if not _ASPECT_CLF_AVAILABLE:
        raise RuntimeError(
            "aspect_classifier no está disponible (¿modelos sin entrenar?). "
            "Ejecuta: python -m aspect_classifier.train"
        )

    fase2_cfg = _aspect_clf.config.get('fase2', {})
    complejo_note = ''

    if fase2_cfg.get('usar_complejo_verbal', False):
        # Pooling sobre el complejo verbal (verbo + clíticos + núcleo del OD),
        # posiblemente discontiguo. "texto" del complejo es la fuente de
        # verdad de los offsets.
        comp = extraer_complejo(toks, root.id, fase2_cfg)
        sent_text = comp['texto']
        verb_span = comp['spans']
        agrupados = ', '.join(f"{w.text}({w.id})" for w in words
                              if w.id in comp['incluidos'])
        complejo_note = f" complejo={{{agrupados}}}"
    else:
        sent_text = ' '.join(w.text for w in words)
        # Span del verbo en sent_text: se reconstruye por posición del token
        verb_span = None
        char_pos = 0
        for w in words:
            if w.id == root.id:
                verb_span = (char_pos, char_pos + len(w.text))
                break
            char_pos += len(w.text) + 1

    ac_result = _aspect_clf.predict(verb_lemma, oracion=sent_text, span=verb_span)
    verb_class = _ASPECT_TO_LS.get(ac_result["clase"], 'activity')
    ls_type_clasificador = verb_class   # antes de gates/coerciones (para diagnóstico)
    classification_source = 'roberta'
    vec = ac_result["vector"]
    aspect_note = (f"stat={vec['stat']:.2f} dyn={vec['dyn']:.2f} "
                   f"tel={vec['tel']:.2f} pun={vec['pun']:.2f} "
                   f"conf={ac_result['confianza']:.2f} ({ac_result['metodo']})"
                   f"{complejo_note}")

    # Resumen del corroborador Van Valin (si participó en este predict).
    if ac_result.get("pruebas_detalle"):
        resumen_vv = _resumen_pruebas(ac_result["pruebas_detalle"])
        if resumen_vv:
            aspect_note += f" · {resumen_vv}"

    # ── Causatividad (Paso 4): detección híbrida + gate ──────────────────
    caus = {"causativo": False, "tipo": None, "source": None,
            "confianza": None, "se_anticausativo": False,
            "se_reflexivo_no_causativo": False}
    if _CAUS_LEXICON is not None:
        # toks ya lleva el lema del root corregido por LEMA_FIXES
        caus = detectar_causatividad(toks, root.id, _CAUS_LEXICON, fase2_cfg)

        # Gate 4D (solo léxico): `se` medio/reflexivo de base Semelfactive
        # + pun alto → Semelfactive, no Achievement (telicidad espuria).
        gated = aplicar_gate_semelfactive(verb_class, vec["pun"], caus)
        if gated != verb_class:
            verb_class = gated
            aspect_note += " gate=se_reflexivo→Semelfactive"

    # ── Gates de telicidad COMPOSICIONAL del objeto (Fase L4.5 §5, bug de
    # campo de Julian, 2026-07-10: "Juan come manzanas" salía Semelfactive,
    # "Juan come la manzana" salía Achievement). Doctrina RRG (delimitación
    # incremental, misma familia que "corrió cinco kilómetros"): un objeto
    # DESNUDO (plural/masa, sin det ni numeral) NUNCA delimita -> atélico;
    # un objeto DELIMITADO (con det o numeral) delimita -> télico DURATIVO
    # (Active_Accomplishment, nunca puntual). Gates POST-clasificador: NO
    # se toca el vector ni los umbrales (mover pun ya demostró empeorar
    # Semelfactive). Generaliza y sustituye el gate AA-sin-delimitador
    # anterior (ese solo cubría verb_class=='active_accomplishment'; ahora
    # `tiene_delimitador_nuclear` además exige que el obj no sea desnudo).
    sujeto_agentivo = any(c['deprel'] == 'nsubj' and c['macropapel'] == 'Actor'
                          for c in roles['core'])
    obj_delimita = tiene_delimitador_nuclear(roles, toks)
    obj_medida = objeto_con_numeral_medida(roles, toks)
    # Clase LÉXICA del lema (VERB_CLASSES, el léxico semilla -- NO el
    # clasificador contextual): GUARDA CRÍTICA de G-AA/G-se-aspectual.
    # "rompió el vaso" tiene obj definido y sujeto agentivo, pero "romper"
    # es Achievement léxico (puntual): sin esta guarda, G-AA promovería
    # incorrectamente a Active_Accomplishment cualquier logro con objeto
    # definido.
    clase_lexica = VERB_CLASSES.get(verb_lemma)
    clase_lexica_durativa = clase_lexica in ('activity', 'active_accomplishment')

    if debe_degradar_por_objeto_desnudo(
            verb_class, sujeto_agentivo, obj_delimita, clase_lexica):
        verb_class = 'activity'
        aspect_note += " gate=obj_desnudo→Activity"
    elif (verb_class == 'active_accomplishment' and roles.get('impersonal')
            and not obj_delimita):
        # Fase L5 §0.3 — AA-sin-delimitador (impersonal): "llueve" salió AA
        # del clasificador (deriva del reentrenamiento), pero es impersonal
        # SIN ningún delimitador nuclear -> Prueba 4 de Van Valin, la clase
        # colapsa a activity. Scoped a `impersonal`: una pasiva de AA ("el
        # pastel fue comido por Juan") SÍ tiene delimitador (el padecedor
        # nsubj:pass) y NO debe degradarse (es AA, §0.4).
        verb_class = 'activity'
        aspect_note += " gate=impersonal_sin_delimitador→Activity"
    elif (verb_class in ('semelfactive', 'achievement') and not obj_delimita
            and roles.get('actor_implicito') is not None and clase_lexica_durativa):
        # Fase L5 §0.2 — pro-drop + verbo durativo léxico + sin delimitador:
        # "corrió vigorosamente" (el clasificador lo desvió a semelfactive
        # tras el reentrenamiento; correr es durativo léxico -> actividad
        # atélica). El gate obj_desnudo de arriba exige `sujeto_agentivo`
        # EXPLÍCITO y no rescataba el pro-drop; la guarda de clase léxica
        # durativa impide degradar un logro pro-drop genuino ("llegó").
        verb_class = 'activity'
        aspect_note += " gate=prodrop_durativo→Activity"
    elif (verb_class in ('achievement', 'accomplishment')
            and sujeto_agentivo and obj_delimita and clase_lexica_durativa):
        verb_class = 'active_accomplishment'
        aspect_note += " gate=obj_delimitado→AA"
    elif (verb_class == 'activity' and sujeto_agentivo and obj_medida
            and clase_lexica_durativa):
        # Fase L5 §0.1 — G-AA-medida: actividad + objeto de MEDIDA (numeral)
        # + verbo durativo léxico -> Active_Accomplishment composicional.
        # "Juan corrió cinco kilómetros": regresión del reentrenamiento (su
        # tel cayó a ~0.34, por debajo de todo umbral posible -- irreparable
        # por umbral); este gate la restaura ESTRUCTURALMENTE. "empuja el
        # carro" (det, sin numeral) NO dispara (ver objeto_con_numeral_medida).
        verb_class = 'active_accomplishment'
        aspect_note += " gate=obj_medida→AA"

    # G-se-aspectual: "se" aspectual (clítico correferencial + verbo
    # transitivo con obj, ver nucleo_periferia._detectar_se_aspectual, agx
    # fuente='se_aspectual') + obj DELIMITADO -> marcador explícito de
    # telicidad completiva. Misma guarda de clase léxica durativa.
    tiene_se_aspectual = any(e['fuente'] == 'se_aspectual' for e in roles['agx'])
    if (tiene_se_aspectual and obj_delimita and clase_lexica_durativa
            and verb_class != 'active_accomplishment'):
        verb_class = 'active_accomplishment'
        aspect_note += " gate=se_aspectual→AA"

    # ── Aspecto auxiliar ──────────────────────────────────────────────────
    aux_asp = detect_aux_aspect(root, words)

    # ── Pruebas de Van Valin ESTRUCTURALES (P1-P5 sobre la oración real) ──
    # DESPUÉS de detect_aux_aspect y de los gates existentes (4D, AA): el
    # vector del clasificador NUNCA se toca, solo verb_class y las notas.
    # R1/R2 son coerciones licenciadas por la teoría; R3/R4 solo anotan.
    evidencia_estructural = {"evidencias": []}
    coerciones_notas = []
    pe_cfg = _aspect_clf.config.get('pruebas_estructurales', {})
    if pe_cfg.get('enabled', True):
        evidencia_estructural = detectar_evidencia(toks, root.id, roles,
                                                    aux_asp, pe_cfg)
        resultado_pe = aplicar_coerciones(verb_class, evidencia_estructural,
                                          tiene_delimitador_nuclear(roles, toks),
                                          pe_cfg)
        verb_class = resultado_pe['clase']
        coerciones_notas = resultado_pe['notas']
        for nota in coerciones_notas:
            aspect_note += f" {nota}"
        coherencia = linea_coherencia(verb_class, evidencia_estructural)
        if coherencia:
            aspect_note += f" · {coherencia}"

    # ── Fase LINKING, Etapa L2.5: Estructuras Lógicas ditransitivas ───────
    # ANTES de construir la LS normal — si dispara, SU plantilla manda y
    # se salta por completo la rama de causatividad (nunca hay doble CAUSE:
    # el CAUSE de transferencia/benefactiva ya viene en la propia plantilla).
    # El gate AA y las coerciones de pruebas_estructurales de arriba ya
    # corrieron sobre verb_class, pero quedan anulados por el override —
    # misma política que la causatividad léxica (su nota de gate puede
    # seguir viéndose en aspect_note, informativa, sin efecto en ls_type).
    ditrans = None
    ditrans_cfg = _aspect_clf.config.get('ditransitivas', {})
    if _DITRANS_LEXICON is not None and ditrans_cfg.get('enabled', True):
        ditrans = construir_ditransitiva(roles, verb_lemma, _DITRANS_LEXICON,
                                         ditrans_cfg)

    # ── Construir LS ──────────────────────────────────────────────────────
    if ditrans is not None:
        diagnosticos = []
        ls = {'formal': ditrans['formal'], 'lexical': ditrans['lexical'],
             'estructura': ditrans['estructura']}
        verb_class = ditrans['clase']
        arg_meta_parts = ditrans['arg_meta_parts']
        id_a_var = ditrans['id_a_var']
        variables = ditrans['variables']
        if ditrans['y_periferia_id'] is not None:
            # decisión 4: el beneficiario sin clítico ASCIENDE de periferia
            # a argumento — no debe listarse dos veces.
            roles['periferia'] = [p for p in roles['periferia']
                                  if p['id'] != ditrans['y_periferia_id']]

        aspect_note += f" ditrans={ditrans['plantilla']}({ditrans['source']})"
        if ditrans['source'] == 'default' or ditrans['ambiguo']:
            log_candidato_ditrans(verb_lemma, sent_text, ditrans['plantilla'])
    elif caus["causativo"]:
        diagnosticos = []
        # [do'(x, Ø)] CAUSE [β]: β conserva su Aktionsart. Con léxico, la
        # clase de β viene de aktionsart_base; con heurístico, del
        # clasificador. El vector de 4 rasgos y cls_source NO se tocan.
        lexent = _CAUS_LEXICON.get(verb_lemma)
        if caus["source"] == "lexicon" and lexent:
            base = lexent["aktionsart_base"]
            pred_base = lexent.get("predicado_base") or None
        else:
            base = next(k for k, v in _ASPECT_TO_LS.items() if v == verb_class)
            pred_base = None
        textos = {t["id"]: t["text"] for t in toks}
        causer = textos.get(caus["causer_id"])
        patient = textos.get(caus["patient_id"])
        ls = componer_cause(
            base, pred_base, verb_lemma, causer, patient,
            caus["se_anticausativo"],
            causativo_heuristico=(caus["source"] == "heuristic"),
        )
        verb_class = _ASPECT_TO_LS.get(base, verb_class)

        arg_meta_parts = []
        id_a_var = {}
        variables = {'x': 'Ø', 'y': patient} if caus["se_anticausativo"] \
            else {'x': causer or 'x', 'y': patient}
        if caus["se_anticausativo"]:
            arg_meta_parts.append("x:Ø,—,causante inespecificado")
        elif causer:
            arg_meta_parts.append(f"x:{causer},nsubj,Actor(causante)")
            if caus["causer_id"] is not None:
                id_a_var[caus["causer_id"]] = "x"
        if patient:
            rel = "nsubj" if caus["se_anticausativo"] else "obj"
            psa = "→PSA" if caus["se_anticausativo"] else ""
            arg_meta_parts.append(f"y:{patient},{rel},Undergoer(paciente{psa})")
            if caus["patient_id"] is not None:
                id_a_var[caus["patient_id"]] = "y"

        operador_causativo = ("INGR" if "INGR " in ls["formal"] else
                              "BECOME" if "BECOME " in ls["formal"] else None)
        caus["clase_derivada"] = {
            "BECOME": "realizacion_causativa",
            "INGR": "logro_causativo",
        }.get(operador_causativo)
        aspect_note += f" CAUSE[{caus['tipo']},{caus['confianza']}]"
        if caus.get("clase_derivada"):
            aspect_note += f" derivada={caus['clase_derivada']} fuente=EL"
        if caus["source"] == "heuristic":
            log_candidato(verb_lemma, sent_text)
    elif roles['impersonal']:
        # Impersonal/pleonástico (llover, nevar…): solo el predicado,
        # sin argumento semántico inventado. LA1: `estructura` vacía —
        # ninguna posición AUH ocupada → M-transitividad 0 (atransitivo).
        ls = {'formal': f"{verb_lemma}'", 'lexical': f"{verb_lemma}'", 'estructura': []}
        variables = {}
    else:
        ls = build_ls(verb_lemma, args, verb_class, aux_asp)
        variables = args

    # ── Fase LINKING, Etapa L1b: wrappers de periferia en la LS ───────────
    # Tras build_ls/componer_cause. Anota 'cuantificada' en los items de
    # periferia sin preposición que P4 (pruebas_estructurales) ya confirmó
    # como duración cuantificada (numeral/det de cantidad) — wrappers_ls no
    # recibe toks, así que reutiliza esta evidencia en vez de duplicar la
    # heurística (ver docstring de wrappers_ls.componer_wrappers).
    p4_bare_triggers = {e['trigger'] for e in evidencia_estructural['evidencias']
                        if e['prueba'] == 'P4'}
    for p in roles['periferia']:
        if p.get('case') is None and p['text'] in p4_bare_triggers:
            p['cuantificada'] = True

    # Etapa OPERATORS_2 §1: los operadores se calculan ANTES de los wrappers
    # porque deciden cuáles NO deben componerse (un elemento ya representado
    # como operador no se escribe además como predicado de la EL).
    operadores_detectados = _calcular_operadores(toks, root.id, aux_asp, sent_text)
    cubiertos = _operadores.tokens_cubiertos(operadores_detectados)

    wrappers_aplicados = []
    wrappers_cfg = _aspect_clf.config.get('wrappers_ls', {})
    if wrappers_cfg.get('enabled', True):
        ls['formal'], ls['lexical'], wrappers_aplicados = componer_wrappers(
            ls['formal'], ls['lexical'], roles['periferia'], wrappers_cfg,
            cubiertos)
        reales = [w for w in wrappers_aplicados if w['aplicado']]
        if reales:
            resumen_w = '·'.join(f"{w['pred']}({w['trigger']})" for w in reales)
            aspect_note += f" wrappers: {resumen_w}"

    salida = {
        'ls_type':    verb_class,
        'ls_formal':  ls['formal'],
        'ls_lexical': ls['lexical'],
        # OPERATORS_2 §3: el lema del verbo raíz, EXPLÍCITO. `correccion._lema_de`
        # lo adivinaba parseando la EL léxica (primer predicado primado que no
        # fuera un primitivo), y eso falla justo donde la EL no contiene ningún
        # predicado léxico: las ditransitivas son solo do'/have'/CAUSE, así que
        # "María le dio flores a Pedro" caía al fallback `ls_type` y la
        # corrección acababa en `staging_lema_no_identificable`. El lema no hay
        # que deducirlo de la representación: el mapper ya lo tiene aquí.
        'verb_lemma': verb_lemma,
        'args_map':   '; '.join(arg_meta_parts),
        'variables':  canonical_variables(variables),
        'cls_source': classification_source,   # 'roberta' (o 'lexicon' en copulativas)
        'morph_note': aspect_note,             # vector aspectual [stat dyn tel pun] + confianza
        'vector':     dict(vec),               # {stat,dyn,tel,pun} crudo (L5 §3: línea Rasgos)
        'confianza':  ac_result['confianza'],  # 0-1 (L5 §3)
        'metodo':     ac_result['metodo'],     # 'lexical'|'contextual' (L5 §3)
        'causativo':           caus["causativo"],
        'causativo_tipo':      caus["tipo"],
        'causativo_source':    caus["source"],
        'causativo_confianza': caus["confianza"],
        # Contrato estable LA2: la GUI/terminal no tienen que inferir la
        # clase visible leyendo la EL con regex. La clase del clasificador
        # permanece en ls_type_clasificador; esta es la lectura derivada.
        'causativo_clase_derivada': caus.get('clase_derivada'),
        'core':                roles['core'],
        'periferia':           roles['periferia'],
        'actor_implicito':     roles['actor_implicito'],
        'agx':                 roles['agx'],
        'impersonal':          roles['impersonal'],
        'id_a_var':            id_a_var,
        'diagnosticos_analisis': diagnosticos,
        'root_id':             root.id,
        'pruebas_evidencia':   evidencia_estructural['evidencias'],
        'coerciones':          coerciones_notas,
        'wrappers':            wrappers_aplicados,
        'ls_type_clasificador': ls_type_clasificador,
        'ditransitiva': ({'plantilla': ditrans['plantilla'], 'trigger': ditrans['trigger'],
                         'source': ditrans['source'], 'ambiguo': ditrans['ambiguo'],
                         'subtipo_benefactivo': ditrans.get('subtipo_benefactivo'),
                         'predicado_resultado': ditrans.get('predicado_resultado'),
                         'proposito': ditrans.get('proposito')}
                        if ditrans is not None else None),
        'roles_tematicos': (ditrans['roles_tematicos'] if ditrans is not None else {}),
    }

    # ── Fase LINKING, Etapa LA1: macropapeles por AUH, PSA+concordancia, ──
    # traza de producción, reconciliación §3. ADITIVA por construcción: con
    # el flag apagado no se añade NINGUNA clave (byte-idéntico verificado en
    # test_linking.py::test_flag_apagado_byte_identico).
    linking_cfg = _aspect_clf.config.get('linking', {}) if _ASPECT_CLF_AVAILABLE else {}
    if linking_cfg.get('enabled', True):
        estructura = ls.get('estructura', [])
        # Los constructores de EL (build_ls/componer_cause/construir_el) no
        # conocen ids de token, solo texto plano — el mapper sí los tiene
        # aquí (toks + el id_a_var YA FINAL de la rama que haya disparado:
        # ditrans/causativo reasignan id_a_var desde cero, igual que ya
        # documenta completeness.py sobre `variables`/`core`).
        textos = {t['id']: t['text'] for t in toks}
        texto_a_id = {textos[tid]: tid for tid in id_a_var if tid in textos}
        _linking.enriquecer_ids(estructura, texto_a_id)

        if ditrans is not None:
            plantilla_info = {'nombre': ditrans['plantilla'], 'fuente': ditrans['source']}
        elif caus['causativo']:
            plantilla_info = {'nombre': f"causativa ({caus['tipo']})", 'fuente': caus['source']}
        elif roles['impersonal']:
            plantilla_info = {'nombre': 'impersonal', 'fuente': 'léxico'}
        else:
            plantilla_info = {'nombre': 'estándar', 'fuente': classification_source}

        resultado_linking = _linking.analizar_linking(
            estructura, roles, roles['agx'], caus, toks, root.id, verb_class,
            plantilla_info)

        # §3 — reconciliación con args_map (ya construido arriba, en
        # arg_meta_parts): si NO coincide, se loguea para decisión de
        # Julian, sin tocar ni el gold ni la asignación vieja.
        reconciliacion = _linking.reconciliar(resultado_linking['macropapeles'],
                                              '; '.join(arg_meta_parts))
        for fila in reconciliacion['filas']:
            if not fila['coincide']:
                _linking.log_discrepancia(verb_lemma, sent_text, fila)
        resultado_linking['reconciliacion'] = reconciliacion

        salida['ls_estructura'] = estructura
        salida['linking'] = resultado_linking

    return _anotar_operadores(salida, toks, root.id, aux_asp, sent_text, operadores_detectados)


def _empty_ls() -> dict:
    return {
        'ls_type':    'unknown',
        'ls_formal':  "pred'(?)",
        'ls_lexical': "pred'(?)",
        'args_map':   '',
        'variables':  {},
    }
