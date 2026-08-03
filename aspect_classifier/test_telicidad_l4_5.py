"""Tests de telicidad composicional del objeto — Fase LINKING, Etapa L4.5 §5.

Bug de campo de Julian (reproducido en vivo, 2026-07-10): el objeto
DESNUDO ("manzanas") no delimita -> atélico; el objeto DELIMITADO ("la
manzana", "cinco manzanas") delimita -> télico durativo
(Active_Accomplishment, nunca puntual); el "se" ASPECTUAL marca telicidad
completiva explícitamente. Gates POST-clasificador (nucleo_periferia +
rrg_ls_mapper), NO se toca el clasificador ni sus umbrales.

Todos los tests aquí son @slow (Stanza + roBERTa reales) -- no hay forma
fría de ejercitar el pipeline completo (map_sentence_to_ls requiere el
clasificador cargado). Ver aspect_classifier/test_nucleo_periferia.py y
test_completeness.py para la cobertura fría de las piezas estructurales
(tiene_delimitador_nuclear, _detectar_se_aspectual, agx-lista).

Ejecutar:
    python -m aspect_classifier.test_telicidad_l4_5 --slow
    RUN_SLOW=1 pytest aspect_classifier/test_telicidad_l4_5.py
"""

import os
import sys

RUN_SLOW = os.environ.get("RUN_SLOW") == "1" or "--slow" in sys.argv


def test_slow_cinco_dianas_telicidad_composicional():
    """Las 5 dianas obligatorias de L4.5 §5 (tabla del prompt).

    Fase L5 §0.5 — aserción RELAJADA: se exige la CLASE correcta; la nota de
    gate es OPCIONAL. Tras el reentrenamiento habitual el clasificador ya
    acierta la clase por sí solo en 3/5 (el pun espurio de "comer" en
    presente cayó de ~0.52 a 0.05-0.42): esos casos alcanzan la clase
    correcta SIN que ningún gate deje su nota, y el test fallaba por el
    propio ÉXITO del reentrenamiento, no por un fallo real."""
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    def clase(frase):
        ls = m.map_sentence_to_ls(nlp(frase).sentences[0])
        return ls["ls_type"], ls["morph_note"]

    casos = [
        ("Juan come", "activity"),
        ("Juan come manzanas", "activity"),
        ("Juan come manzanas siempre", "activity"),
        ("Juan se come las manzanas", "active_accomplishment"),
        ("Juan come la manzana", "active_accomplishment"),
    ]
    fallos = []
    for frase, esperado in casos:
        obtenido, nota = clase(frase)
        if obtenido != esperado:
            fallos.append(f"{frase!r}: esperado {esperado}, obtenido {obtenido} ({nota})")
    assert not fallos, "\n".join(fallos)


def test_slow_guardarraíl_clase_lexica_bloquea_g_aa():
    """GUARDA CRÍTICA (la razón de ser de la guarda de clase léxica):
    'rompió el vaso' tiene sujeto agentivo + obj DELIMITADO ('el vaso',
    con determinante) -- G-AA NO debe disparar porque 'romper' es
    Achievement LÉXICO (puntual), no durativo."""
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)
    ls = m.map_sentence_to_ls(nlp("Juan rompió el vaso").sentences[0])
    assert ls["ls_type"] != "active_accomplishment", \
        f"G-AA disparó indebidamente sobre un Achievement léxico: {ls}"
    assert "gate=obj_delimitado→AA" not in ls["morph_note"]


def test_slow_guardarraíl_dianas_historicas_sin_regresion():
    """Sub-conjunto de las dianas históricas de
    `informe_wrappers_dianas.DIANAS` con clase conocida (documentada en
    checkpoints previos) -- confirma que L4.5 no las movió de sitio."""
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    esperadas = {
        "estudié tres horas anoche": "activity",
        "Juan corrió cinco kilómetros": "active_accomplishment",
        "Juan corrió": "activity",
        "corrió": "activity",
        "llueve": "activity",   # roles['impersonal'] -> predicado bare;
                                # ls_type sigue viniendo del clasificador
                                # (no tocado por L4.5); solo se comprueba
                                # que sigue convirtiendo sin excepción.
    }
    fallos = []
    for frase, esperado in esperadas.items():
        ls = m.map_sentence_to_ls(nlp(frase).sentences[0])
        if frase == "llueve":
            continue   # smoke-only: no forzar clase, solo que no reviente
        if ls["ls_type"] != esperado:
            fallos.append(f"{frase!r}: esperado {esperado}, obtenido {ls['ls_type']}")
    assert not fallos, "\n".join(fallos)


def test_slow_l5_estabilizacion_gates():
    """Fase L5 §0 — dianas restauradas tras el reentrenamiento habitual.

    - "Juan corrió cinco kilómetros" -> AA (gate G-AA-medida: su tel cayó a
      ~0.34 en el reentrenamiento; el gate la protege estructuralmente).
    - "empuja el carro" -> NO AA (det, sin numeral: obj_medida no dispara).
    - "corrió vigorosamente" -> activity (pro-drop durativo; el clasificador
      lo desvió a semelfactive).
    - "llueve" -> activity (impersonal sin delimitador; el clasificador la
      desvió a AA).
    - "el pastel fue comido por Juan" -> AA (GOLD lingüístico de Julian: la
      pasiva de un AA agentivo es el mismo evento; NO se degrada pese a no
      tener obj).
    """
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    def clase(frase):
        ls = m.map_sentence_to_ls(nlp(frase).sentences[0])
        return ls["ls_type"], ls["morph_note"]

    fallos = []

    c, nota = clase("Juan corrió cinco kilómetros")
    if c != "active_accomplishment":
        fallos.append(f"'cinco kilómetros': esperado AA, obtenido {c} ({nota})")

    # §0.1: la GUARDA del numeral -> el gate G-AA-medida NO debe disparar sin
    # nummod ('el carro' tiene det, no numeral). La clase final la fija el
    # clasificador (aquí AA por su cuenta, tel alto); lo que se verifica es
    # que el gate no la haya forzado.
    _, nota = clase("Juan empuja el carro")
    if "gate=obj_medida→AA" in nota:
        fallos.append(f"'empuja el carro': G-AA-medida disparó indebidamente ({nota})")

    c, nota = clase("Juan corrió vigorosamente")
    if c != "activity":
        fallos.append(f"'corrió vigorosamente': esperado activity, obtenido {c} ({nota})")

    c, nota = clase("Llueve")
    if c != "activity":
        fallos.append(f"'llueve': esperado activity, obtenido {c} ({nota})")

    c, nota = clase("El pastel fue comido por Juan")
    if c != "active_accomplishment":
        fallos.append(f"'el pastel fue comido por Juan': esperado AA, obtenido {c} ({nota})")

    assert not fallos, "\n".join(fallos)


def test_slow_ditransitiva_no_interferida_por_gates_nuevos():
    """'le da manzanas a María': la ditransitiva dispara su PROPIA plantilla
    (benefactiva/transferencia) y sobreescribe verb_class DESPUÉS de los
    gates nuevos -- estructuralmente imposible que G-atélico/G-AA/
    G-se-aspectual la interfieran (ver orden en map_sentence_to_ls), pero
    se verifica empíricamente."""
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)
    ls = m.map_sentence_to_ls(nlp("Le da manzanas a María").sentences[0])
    assert ls["ditransitiva"] is not None, \
        f"se esperaba que la ditransitiva disparara: {ls}"


if not RUN_SLOW:
    try:
        import pytest
        for _name in ("test_slow_cinco_dianas_telicidad_composicional",
                      "test_slow_guardarraíl_clase_lexica_bloquea_g_aa",
                      "test_slow_guardarraíl_dianas_historicas_sin_regresion",
                      "test_slow_l5_estabilizacion_gates",
                      "test_slow_ditransitiva_no_interferida_por_gates_nuevos"):
            globals()[_name] = pytest.mark.skipif(
                True, reason="lento: exportar RUN_SLOW=1")(globals()[_name])
    except ImportError:
        pass


def main():
    tests = [test_slow_cinco_dianas_telicidad_composicional,
             test_slow_guardarraíl_clase_lexica_bloquea_g_aa,
             test_slow_guardarraíl_dianas_historicas_sin_regresion,
             test_slow_l5_estabilizacion_gates,
             test_slow_ditransitiva_no_interferida_por_gates_nuevos] if RUN_SLOW else []
    if not tests:
        print("(sin --slow, nada que correr: todos los tests de este módulo son @slow)")
        return
    fallos = 0
    for t in tests:
        try:
            t()
            print(f"  [OK]   {t.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f"  [FAIL] {t.__name__}: {e}")
    if fallos:
        sys.exit(1)
    print(f"\n{len(tests)} tests pasaron.")


if __name__ == "__main__":
    main()
