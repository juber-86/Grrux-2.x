"""Sub-paso 2.1 — Genera data/contextual_sentences.csv (oraciones de
entrenamiento para la cabeza contextual de Fase 2).

Una oración finita natural por cada fila de dataset_clean.csv (159) y
multiword_cases.csv (34), parseable con Stanza.

DECISIONES LINGÜÍSTICAS (revisables editando los diccionarios de abajo):

1. TIEMPO: State → presente 3sg ("Juan sabe la respuesta."); las clases
   dinámicas → pretérito 3sg ("Juan corrió."). El pretérito con estados
   fuerza lectura incoativa ("supo" = 'se enteró'), que contaminaría stat.

2. OD SEGÚN CLASE: las Activities transitivas llevan OD escueto/plural
   indefinido ("Juan leyó novelas.") porque un OD definido singular en
   pretérito coerciona a Active_Accomplishment y contaminaría la etiqueta.
   Accomplishment/Achievement/Semelfactive/State llevan OD definido.

3. SUJETO: "Juan" por defecto; sujeto inanimado/animal donde "Juan" es
   imposible ("La bomba estalló.", "El gato ronroneó.").

4. FILAS CON transitivo=1 Y pronominal=1 (12 Achievements/Semelfactives):
   se leen como anticausativas/medias ("La puerta se abrió.", "El perro
   se sacudió."); las dudosas van con revisar=True.

5. revisar=True donde la conjugación, el sujeto, el objeto o los flags
   del dataset son dudosos. Julian decide.

Uso:
    python -m aspect_classifier.gen_contextual_sentences
"""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
OUT_CSV = DATA_DIR / "contextual_sentences.csv"

# ---------------------------------------------------------------------------
# Conjugación 3sg
# ---------------------------------------------------------------------------
PRET_IRREG = {
    "hacer": "hizo", "componer": "compuso", "traducir": "tradujo",
    "producir": "produjo", "obtener": "obtuvo", "detener": "detuvo",
    "conseguir": "consiguió", "rendir": "rindió", "dormir": "durmió",
    "morir": "murió", "asentir": "asintió", "reír": "rio",
    "derretir": "derritió",
    # estados (los usa el corroborador Van Valin; en el CSV van en presente)
    "saber": "supo", "tener": "tuvo", "contener": "contuvo",
    "suponer": "supuso", "querer": "quiso", "poder": "pudo",
}

PRES_IRREG = {
    # estados
    "tener": "tiene", "contener": "contiene", "costar": "cuesta",
    "recordar": "recuerda", "preferir": "prefiere", "entender": "entiende",
    # dinámicos con diptongación/cambio de raíz (para variantes en presente)
    "temblar": "tiembla", "empezar": "empieza", "encender": "enciende",
    "perder": "pierde", "reventar": "revienta", "quebrar": "quiebra",
    "despertar": "despierta", "negar": "niega", "cerrar": "cierra",
    "dormir": "duerme", "morir": "muere", "volar": "vuela",
    "rodar": "rueda", "volcar": "vuelca", "encontrar": "encuentra",
    "demoler": "demuele", "resolver": "resuelve", "disolver": "disuelve",
    "rendir": "rinde", "conseguir": "consigue", "reír": "ríe",
    "derretir": "derrite", "jugar": "juega", "obtener": "obtiene",
    "detener": "detiene", "asentir": "asiente", "aullar": "aúlla",
    "maullar": "maúlla", "chirriar": "chirría", "vaciar": "vacía",
}


def preterito_3sg(lema: str) -> str:
    if lema in PRET_IRREG:
        return PRET_IRREG[lema]
    stem = lema[:-2]
    if lema.endswith("ar"):
        return stem + "ó"
    if lema.endswith(("er", "ir")) or lema.endswith("ír"):
        stem = lema[:-2]
        if stem and stem[-1].lower() in "aeiouáéíóú":
            return stem + "yó"          # leer→leyó, construir→construyó
        return stem + "ió"
    raise ValueError(f"No sé conjugar: {lema}")


def presente_3sg(lema: str) -> str:
    if lema in PRES_IRREG:
        return PRES_IRREG[lema]
    if lema.endswith("uir") and not lema.endswith("guir"):
        return lema[:-2] + "ye"        # construir→construye, fluir→fluye
    stem = lema[:-2]
    return stem + ("a" if lema.endswith("ar") else "e")


GER_IRREG = {
    "dormir": "durmiendo", "morir": "muriendo", "derretir": "derritiendo",
    "rendir": "rindiendo", "conseguir": "consiguiendo", "reír": "riendo",
    "preferir": "prefiriendo", "asentir": "asintiendo", "hervir": "hirviendo",
    "pedir": "pidiendo", "sentir": "sintiendo", "seguir": "siguiendo",
    "venir": "viniendo", "decir": "diciendo", "poder": "pudiendo",
    "ir": "yendo", "vestir": "vistiendo",
}

PART_IRREG = {
    "abrir": "abierto", "romper": "roto", "escribir": "escrito",
    "morir": "muerto", "resolver": "resuelto", "volver": "vuelto",
    "cubrir": "cubierto", "descubrir": "descubierto", "hacer": "hecho",
    "componer": "compuesto", "disolver": "disuelto", "ver": "visto",
    "devolver": "devuelto", "envolver": "envuelto", "poner": "puesto",
    "decir": "dicho", "freír": "frito", "imprimir": "impreso",
}


def gerundio(lema: str) -> str:
    if lema in GER_IRREG:
        return GER_IRREG[lema]
    if lema.endswith("ar"):
        return lema[:-2] + "ando"
    stem = lema[:-2]
    if stem and stem[-1].lower() in "aeiouáéíóú":
        return stem + "yendo"          # leer→leyendo, construir→construyendo
    return stem + "iendo"


def participio(lema: str) -> str:
    if lema in PART_IRREG:
        return PART_IRREG[lema]
    if lema.endswith("ar"):
        return lema[:-2] + "ado"
    stem = lema[:-2]
    if stem and stem[-1].lower() in "aeo":
        return stem + "ído"            # leer→leído, caer→caído
    return stem + "ido"                # construir→construido


# ---------------------------------------------------------------------------
# Curaduría por lema
# ---------------------------------------------------------------------------
# Oraciones completas para casos que las reglas no cubren bien:
# pronominales, flags contradictorios, sujetos obligados, verbos raros.
# lema -> (oracion, revisar)
FULL = {
    # pronominales (incluye los 12 con transitivo=1 y pronominal=1)
    "llegar":       ("Juan llegó.", True),          # trans+pron en el dataset: raro
    "morir":        ("El abuelo se murió.", False),
    "encontrar":    ("Juan se encontró una moneda.", False),
    "perder":       ("Juan se perdió.", True),      # ¿'perderse' o 'perder las llaves'?
    "romper":       ("El vaso se rompió.", False),
    "despertar":    ("Juan se despertó.", False),
    "caer":         ("Juan se cayó.", False),
    "disparar":     ("La alarma se disparó.", False),
    "aparecer":     ("El fantasma se apareció.", True),
    "desaparecer":  ("La mancha desapareció.", True),   # 'se desapareció' es no estándar
    "abrir":        ("La puerta se abrió.", False),
    "cerrar":       ("La puerta se cerró.", False),
    "detenerse":    ("El tren se detuvo.", False),
    "lograr":       ("El plan se logró.", True),    # pasiva-se; pron=1 dudoso
    "ceder":        ("La cuerda cedió.", True),     # trans+pron dudosos
    "rendirse":     ("El soldado se rindió.", False),
    "derrumbarse":  ("El edificio se derrumbó.", False),
    "hundirse":     ("El barco se hundió.", False),
    "encenderse":   ("La luz se encendió.", False),
    "apagarse":     ("La luz se apagó.", False),
    "sacudir":      ("El perro se sacudió.", False),
    "agitar":       ("El pájaro se agitó.", True),
    "chasquear":    ("Juan chasqueó los dedos.", True),  # pron=1 dudoso
    # intransitivos con flags o sintaxis dudosos
    "reír":         ("Juan rio.", True),            # ortografía RAE 2010 ('rio')
    "dudar":        ("Juan duda de todo.", False),
    "reconocer":    ("Juan reconoció el error.", True), # trans=0 pero pide OD
    "alcanzar":     ("Juan alcanzó la cima.", True),    # trans=0 pero pide OD
    "obtener":      ("Juan obtuvo el premio.", True),   # trans=0 pero pide OD
    "recibir":      ("Juan recibió la carta.", True),   # trans=0 pero pide OD
    "rebotar":      ("La pelota rebotó.", True),        # trans=1 dudoso
    "pitar":        ("El árbitro pitó la falta.", False),
    # estados con sujeto/estructura obligados
    "contener":     ("La caja contiene agua.", False),
    "costar":       ("El libro cuesta diez euros.", False),
    "valer":        ("El anillo vale mucho.", False),
    "bastar":       ("El dinero basta.", True),
    "sobrar":       ("La comida sobra.", False),
    "pertenecer":   ("Juan pertenece al club.", False),
    "existir":      ("El problema existe.", False),
    "depender":     ("El resultado depende de Juan.", False),
    # accomplishments con sujeto humano específico
    "curar":        ("El médico curó al paciente.", False),
    "sanar":        ("El médico sanó al paciente.", True),  # ¿trans o intrans?
}

# Sujeto no humano para intransitivos donde "Juan" es imposible
SUBJ = {
    "brillar": "La estrella", "fluir": "El río", "gotear": "El grifo",
    "latir": "El corazón", "rugir": "El león", "ronronear": "El gato",
    "maullar": "El gato", "aullar": "El lobo", "temblar": "El suelo",
    "vibrar": "El teléfono", "rodar": "La pelota", "destellar": "La luz",
    "picar": "El mosquito", "chocar": "El coche", "aterrizar": "El avión",
    "despegar": "El avión", "estallar": "La bomba", "explotar": "La bomba",
    "fallecer": "El abuelo", "nacer": "El bebé", "cicatrizar": "La herida",
    "madurar": "La fruta", "fermentar": "El vino", "volar": "El pájaro",
}

# OD por lema (o por (lema, clase) si el lema está duplicado con clases
# distintas). Activities → escueto/indefinido; resto → definido.
OBJ = {
    "saber": "la respuesta", "creer": "la historia", "tener": "un coche",
    "necesitar": "ayuda", "ignorar": "la respuesta", "odiar": "el ruido",
    "amar": "a María", "recordar": "la fecha", "olvidar": "las fechas",
    "desear": "un cambio", "preferir": "el café", "suponer": "lo peor",
    "entender": "la lección", "comprender": "el problema",
    "temer": "la oscuridad", "respetar": "las normas",
    "admirar": "a su maestro", "envidiar": "a su hermano",
    "merecer": "un premio",
    "estudiar": "matemáticas", "escuchar": "música", "mirar": "el paisaje",
    "buscar": "trabajo", "cantar": "canciones", "leer": "novelas",
    ("escribir", "Activity"): "cartas",
    ("escribir", "Accomplishment"): "la novela",
    "susurrar": "secretos", "escalar": "montañas", "limpiar": "ventanas",
    "ganar": "el premio", "descubrir": "el secreto", "terminar": "el trabajo",
    "empezar": "el discurso", "golpear": "la mesa", "saltar": "la valla",
    "tocar": "el timbre", "arrancar": "el motor", "conseguir": "el empleo",
    "convencer": "a su amigo",
    "construir": "la casa", "pintar": "el cuadro", "hornear": "el pan",
    "tejer": "la bufanda", "diseñar": "el logotipo", "componer": "la canción",
    "traducir": "el documento", "resolver": "el acertijo",
    "aprender": "el oficio", "memorizar": "el poema", "preparar": "la cena",
    "reparar": "el coche", "organizar": "el evento", "demoler": "el muro",
    "restaurar": "la iglesia", "reformar": "la cocina",
    "elaborar": "el informe", "fabricar": "la pieza",
    "producir": "la película", "desarrollar": "el programa",
    "redactar": "el contrato", "calcular": "el presupuesto",
    "planificar": "el viaje", "ensamblar": "la máquina",
    "fundar": "la empresa", "establecer": "las reglas",
    "erradicar": "la enfermedad",
}

# Multipalabra: normalizaciones especiales (el resto sigue el patrón
# "Juan {pretérito(verbo)} {resto}.")
MW_FULL = {
    "hipo / hipar?":  ("hipar", "Juan hipó.", True),
    "negar (gesto)":  ("negar", "Juan negó con la cabeza.", True),
    "correr 5km":     ("correr", "Juan corrió cinco kilómetros.", False),
}


def _oracion_simple(row) -> tuple[str, bool]:
    lema, clase = row["lema"], row["clase"]
    if lema in FULL:
        return FULL[lema]

    verbo = presente_3sg(lema) if clase == "State" else preterito_3sg(lema)
    sujeto = SUBJ.get(lema, "Juan")
    se = "se " if row["pronominal"] == 1 else ""

    if row["transitivo"] == 1:
        od = OBJ.get((lema, clase)) or OBJ.get(lema)
        if od is None:
            return f"{sujeto} {se}{verbo} el objeto.", True   # sin curar: revisar
        return f"{sujeto} {se}{verbo} {od}.", False
    return f"{sujeto} {se}{verbo}.", False


def _oracion_multiword(row) -> tuple[str, str, bool]:
    frase = row["lema"].strip()
    if frase in MW_FULL:
        return MW_FULL[frase]
    partes = frase.split()
    lema, resto = partes[0], " ".join(partes[1:])
    return lema, f"Juan {preterito_3sg(lema)} {resto}.", False


# ---------------------------------------------------------------------------
# AUGMENTACIÓN (Paso 3B) — APPEND-ONLY sobre el CSV curado a mano
# ---------------------------------------------------------------------------
CLASES_DINAMICAS = {"Activity", "Accomplishment", "Active_Accomplishment",
                    "Achievement", "Semelfactive"}

# Pares de alternancia de OD: la etiqueta sigue a la ORACIÓN, no al lema.
# OD escueto/indefinido → Activity; OD acotado/definido → Active_Accomplishment.
OD_PAIRS = [
    # (lema, oracion, clase, stat, dyn, tel, pun, transitivo)
    ("comer",   "Juan comió sopa.",             "Activity",              0, 1, 0, 0, 1),
    ("beber",   "Juan bebió agua.",             "Activity",              0, 1, 0, 0, 1),
    ("cocinar", "Juan cocinó.",                 "Activity",              0, 1, 0, 0, 0),
    ("dibujar", "Juan dibujó paisajes.",        "Activity",              0, 1, 0, 0, 1),
    ("cantar",  "Juan cantó el himno.",         "Active_Accomplishment", 0, 1, 1, 0, 1),
    ("nadar",   "Juan nadó dos kilómetros.",    "Active_Accomplishment", 0, 1, 1, 0, 1),
    ("caminar", "Juan caminó diez kilómetros.", "Active_Accomplishment", 0, 1, 1, 0, 1),
]


def _base_verbal(lema: str) -> str:
    """'derretirse' -> 'derretir' (para conjugar lemas con -se incorporado)."""
    return lema[:-2] if lema.endswith("rse") else lema


def _variante_presente(row) -> dict | None:
    """Deriva la variante en presente de una fila dinámica sustituyendo la
    forma de pretérito por la de presente. None si no se pudo localizar
    la forma (p. ej. ortografía editada a mano): se reporta y se salta."""
    base = _base_verbal(row["lema"])
    pret, pres = preterito_3sg(base), presente_3sg(base)
    if pret not in row["oracion"]:
        return None
    nueva = {**row, "oracion": row["oracion"].replace(pret, pres, 1)}
    nueva.pop("id", None)
    nueva["fuente"] = "augment_presente"
    nueva["revisar"] = False
    return nueva


def augment() -> pd.DataFrame:
    """Añade filas al contextual_sentences.csv curado (NUNCA modifica las
    existentes): pares de alternancia de OD, verbos nuevos del sub-paso 3A
    y variantes en PRESENTE de todas las filas de clases dinámicas
    (rompe el confound tiempo↔clase). Los States NO se pasan a pretérito."""
    df = pd.read_csv(OUT_CSV)
    orig_len, orig_ids = len(df), set(df["id"])
    oraciones = set(df["oracion"])
    nuevos, saltadas = [], []

    def add(fila: dict):
        if fila["oracion"] not in oraciones:
            oraciones.add(fila["oracion"])
            nuevos.append(fila)

    # 1) pares de alternancia de OD
    for lema, oracion, clase, stat, dyn, tel, pun, trans in OD_PAIRS:
        add({"lema": lema, "oracion": oracion, "clase": clase,
             "stat": stat, "dyn": dyn, "tel": tel, "pun": pun,
             "transitivo": trans, "pronominal": 0,
             "fuente": "augment_od", "revisar": False})

    # 2) verbos nuevos del sub-paso 3A (semelfactive_candidates.csv curado)
    cand = pd.read_csv(DATA_DIR / "semelfactive_candidates.csv")
    for _, r in cand.iterrows():
        add({"lema": r["lema"], "oracion": r["oracion"], "clase": r["clase"],
             "stat": r["stat"], "dyn": r["dyn"], "tel": r["tel"], "pun": r["pun"],
             "transitivo": r["transitivo"], "pronominal": r["pronominal"],
             "fuente": "augment_semilla", "revisar": False})

    # 3) variantes en presente para todas las filas dinámicas (curadas + nuevas)
    dinamicas = [r for r in df.to_dict("records") + list(nuevos)
                 if r["clase"] in CLASES_DINAMICAS]
    for r in dinamicas:
        var = _variante_presente(r)
        if var is None:
            saltadas.append((r["lema"], r["oracion"]))
        else:
            add(var)

    df_nuevos = pd.DataFrame(nuevos)
    df_nuevos.insert(0, "id", range(df["id"].max() + 1,
                                    df["id"].max() + 1 + len(df_nuevos)))
    out = pd.concat([df, df_nuevos], ignore_index=True)
    out.to_csv(OUT_CSV, index=False)

    # Garantía append-only
    assert len(out) == orig_len + len(df_nuevos)
    assert set(out["id"][:orig_len]) == orig_ids

    print(f"Augmentación: {orig_len} filas curadas + {len(df_nuevos)} nuevas "
          f"= {len(out)}")
    print("\nNuevas por fuente:", df_nuevos["fuente"].value_counts().to_dict())
    print("\nDistribución total de clases:")
    print(out["clase"].value_counts().to_string())
    tiempo = out[out["clase"].isin(CLASES_DINAMICAS)]["fuente"].str.contains("presente").sum()
    print(f"\nFilas dinámicas en presente: {tiempo}")
    if saltadas:
        print(f"\nSALTADAS (forma de pretérito no localizada; revisar a mano): {len(saltadas)}")
        for lema, o in saltadas:
            print(f"  {lema}: {o!r}")
    return out


# ---------------------------------------------------------------------------
# AUGMENTACIÓN PRE-PASO 4 (Frentes 2 y 3) — APPEND-ONLY
# ---------------------------------------------------------------------------
# Frente 2: State en marcos variados. Presente por defecto; los pretéritos
# son SOLO los genuinamente estativos (duración/precio), nunca los que
# coercionan a incoativo ("supo"='se enteró', "recordó", "olvidó").
# (lema, oracion, transitivo, pronominal, revisar)
STATE_AUGMENT = [
    ("saber",      "María sabe la verdad.",                       1, 0, False),
    ("creer",      "El niño cree en los fantasmas.",              1, 0, False),
    ("tener",      "La empresa tiene problemas.",                 1, 0, False),
    ("contener",   "El frasco contiene azúcar.",                  1, 0, False),
    ("necesitar",  "La ciudad necesita agua.",                    1, 0, False),
    ("ignorar",    "El alumno ignora la regla.",                  1, 0, False),
    ("odiar",      "María odia el frío.",                         1, 0, False),
    ("amar",       "La abuela ama las flores.",                   1, 0, False),
    ("recordar",   "El testigo recuerda el accidente.",           1, 0, False),
    ("olvidar",    "El paciente olvida los nombres.",             1, 0, False),
    ("pertenecer", "La finca pertenece al municipio.",            0, 0, False),
    ("existir",    "La injusticia existe.",                       0, 0, False),
    ("costar",     "La entrada cuesta veinte euros.",             0, 0, False),
    ("depender",   "La cosecha depende de la lluvia.",            0, 0, False),
    ("desear",     "El equipo desea la victoria.",                1, 0, False),
    ("preferir",   "La niña prefiere el helado.",                 1, 0, False),
    ("suponer",    "El juez supone su inocencia.",                1, 0, False),
    ("entender",   "La alumna entiende el problema.",             1, 0, False),
    ("comprender", "El lector comprende la novela.",              1, 0, False),
    ("temer",      "El perro teme los truenos.",                  1, 0, False),
    ("respetar",   "El pueblo respeta la tradición.",             1, 0, False),
    ("admirar",    "La crítica admira su obra.",                  1, 0, False),
    ("envidiar",   "El vecino envidia su suerte.",                1, 0, False),
    ("merecer",    "La actriz merece el premio.",                 1, 0, False),
    ("dudar",      "El científico duda del resultado.",           0, 0, False),
    ("bastar",     "Una firma basta.",                            0, 0, False),
    # pretéritos genuinamente estativos (precio/posesión/duración)
    ("costar",     "El libro costó diez euros.",                  0, 0, False),
    ("tener",      "Juan tuvo tres coches.",                      1, 0, False),
    ("pertenecer", "La casa perteneció a su familia durante décadas.", 0, 0, False),
    ("amar",       "Juan amó a María toda su vida.",              1, 0, False),
    ("valer",      "El cuadro valió una fortuna.",                0, 0, False),
    ("temer",      "La abuela temió las tormentas toda su vida.", 1, 0, True),
]

# Frente 3: frases de medida/camino AA en PRETÉRITO (sin homógrafos).
# Objetivo: robustecer tel_ctx en medidas para poder SUBIR el umbral tel.
MEASURE_AUGMENT = [
    ("correr",   "Juan corrió diez kilómetros.",           1, 0, False),
    ("correr",   "María corrió la maratón.",               1, 0, False),
    ("caminar",  "María caminó una milla.",                1, 0, False),
    ("recorrer", "El excursionista recorrió el sendero.",  1, 0, False),
    ("nadar",    "Ana nadó tres kilómetros.",              1, 0, False),
    ("pedalear", "El ciclista pedaleó veinte kilómetros.", 1, 0, False),
    ("volar",    "El piloto voló mil kilómetros.",         1, 0, False),
    ("navegar",  "El barco navegó cien millas.",           1, 0, False),
    ("escalar",  "Juan escaló mil metros.",                1, 0, False),
    ("cruzar",   "Juan cruzó el puente.",                  1, 0, False),
]


def augment_pre4() -> pd.DataFrame:
    """Frentes 2 y 3 del Pre-Paso 4: append-only sobre el CSV curado."""
    df = pd.read_csv(OUT_CSV)
    orig_len, orig_ids = len(df), set(df["id"])
    oraciones = set(df["oracion"])
    nuevos = []

    for lema, oracion, trans, pron, revisar in STATE_AUGMENT:
        if oracion not in oraciones:
            oraciones.add(oracion)
            nuevos.append({"lema": lema, "oracion": oracion, "clase": "State",
                           "stat": 1, "dyn": 0, "tel": 0, "pun": 0,
                           "transitivo": trans, "pronominal": pron,
                           "fuente": "augment_state", "revisar": revisar})
    for lema, oracion, trans, pron, revisar in MEASURE_AUGMENT:
        if oracion not in oraciones:
            oraciones.add(oracion)
            nuevos.append({"lema": lema, "oracion": oracion,
                           "clase": "Active_Accomplishment",
                           "stat": 0, "dyn": 1, "tel": 1, "pun": 0,
                           "transitivo": trans, "pronominal": pron,
                           "fuente": "augment_medida", "revisar": revisar})

    df_nuevos = pd.DataFrame(nuevos)
    df_nuevos.insert(0, "id", range(df["id"].max() + 1,
                                    df["id"].max() + 1 + len(df_nuevos)))
    out = pd.concat([df, df_nuevos], ignore_index=True)
    out.to_csv(OUT_CSV, index=False)

    assert len(out) == orig_len + len(df_nuevos)
    assert set(out["id"][:orig_len]) == orig_ids

    print(f"Pre-Paso 4: {orig_len} filas + {len(df_nuevos)} nuevas = {len(out)}")
    print("Por fuente:", df_nuevos["fuente"].value_counts().to_dict())
    print("State total:", (out["clase"] == "State").sum(),
          "| AA total:", (out["clase"] == "Active_Accomplishment").sum())
    print("revisar=True nuevas:", int(df_nuevos["revisar"].sum()))
    return out


def run() -> pd.DataFrame:
    if OUT_CSV.exists():
        raise SystemExit(
            f"{OUT_CSV.name} ya existe y está CURADO A MANO: no se regenera.\n"
            "Usa 'python -m aspect_classifier.gen_contextual_sentences --augment' "
            "para añadir filas (append-only)."
        )
    clean = pd.read_csv(DATA_DIR / "dataset_clean.csv")
    mw = pd.read_csv(DATA_DIR / "multiword_cases.csv")

    filas = []
    for _, row in clean.iterrows():
        oracion, revisar = _oracion_simple(row)
        filas.append({
            "lema": row["lema"], "oracion": oracion, "clase": row["clase"],
            "stat": row["stat"], "dyn": row["dyn"],
            "tel": row["tel"], "pun": row["pun"],
            "transitivo": row["transitivo"], "pronominal": row["pronominal"],
            "fuente": "simple", "revisar": revisar,
        })
    for _, row in mw.iterrows():
        lema, oracion, revisar = _oracion_multiword(row)
        filas.append({
            "lema": lema, "oracion": oracion, "clase": row["clase"],
            "stat": row["stat"], "dyn": row["dyn"],
            "tel": row["tel"], "pun": row["pun"],
            "transitivo": row["transitivo"], "pronominal": row["pronominal"],
            "fuente": "multiword", "revisar": revisar,
        })

    df = pd.DataFrame(filas)
    df.insert(0, "id", range(1, len(df) + 1))
    df.to_csv(OUT_CSV, index=False)

    print(f"Generado {OUT_CSV.name}: {len(df)} oraciones "
          f"({(df['fuente']=='simple').sum()} simples + "
          f"{(df['fuente']=='multiword').sum()} multiword)")
    print("\nDistribución de clases:")
    print(df["clase"].value_counts().to_string())
    print(f"\nMarcadas revisar=True: {df['revisar'].sum()}")
    print(df[df["revisar"]][["id", "lema", "oracion", "clase"]].to_string(index=False))
    return df


if __name__ == "__main__":
    import sys
    if "--augment-pre4" in sys.argv:
        augment_pre4()
    elif "--augment" in sys.argv:
        augment()
    else:
        run()
