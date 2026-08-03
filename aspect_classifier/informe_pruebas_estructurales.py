"""Mini-informe de checkpoint — pruebas de Van Valin ESTRUCTURALES.

Corre la batería de dianas conocidas + las frases del checkpoint pedido y
lista, por frase: clase del clasificador (antes de gates/coerciones),
evidencias P1-P5 detectadas, regla disparada (si alguna) y clase final.
No modifica nada — solo lee (Stanza + BERTIN + el mapper ya cableado).

Ejecutar:
    ./venv/bin/python -m aspect_classifier.informe_pruebas_estructurales
"""

import sys

# Dianas ya cubiertas por las suites de regresión existentes (unión de
# test_nucleo_periferia, test_causatividad y test_fase2_contextual --slow),
# más las 7 frases explícitas del checkpoint (Van Valin estructural).
DIANAS = [
    # nucleo_periferia (Etapa 1)
    "estudié tres horas anoche",
    "Juan corrió cinco kilómetros",
    "Juan corrió",
    "corrió",
    "el pastel fue comido por Juan",
    "llueve",
    "el jarrón se rompió",
    # causatividad (Paso 4)
    "El ruido asustó al niño",
    "El niño destrozó el juguete",
    "El sol secó la ropa",
    "El faro destelló una señal",
    "Juan rodó la pelota",
    "Juan paseó al perro",
    "El perro se sacudió",
    "Juan leyó el libro",
    # fase2_contextual (AA + controles)
    "Juan se comió la pizza completa",
    "Juan corre todos los días",
    "Juan sabe la respuesta",
    "Juan llegó",
]

# Checkpoint pedido explícitamente para esta tarea (pruebas estructurales).
CHECKPOINT = [
    "tosió durante una hora",
    "está tosiendo",
    "leyó el libro durante una hora",
    "la ropa se secó en una hora",
    "corrió vigorosamente",
    "Juan sabe la respuesta",
    "los invitados llegaron durante una hora",
]


def _fmt_evidencias(evs: list[dict]) -> str:
    if not evs:
        return "—"
    return ", ".join(f"{e['prueba']}:'{e['trigger']}'" for e in evs)


def _fmt_reglas(notas: list[str]) -> str:
    return "; ".join(notas) if notas else "—"


def main():
    import stanza
    import rrg_ls_mapper as m

    print("Cargando Stanza (es)...", file=sys.stderr)
    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    # frases en orden, sin duplicar
    vistas = set()
    frases = []
    for f in DIANAS + CHECKPOINT:
        if f not in vistas:
            vistas.add(f)
            frases.append(f)

    filas = []
    for frase in frases:
        ls = m.map_sentence_to_ls(nlp(frase).sentences[0])
        filas.append({
            "frase": frase,
            "clasificador": ls.get("ls_type_clasificador", "?"),
            "evidencias": _fmt_evidencias(ls.get("pruebas_evidencia", [])),
            "regla": _fmt_reglas(ls.get("coerciones", [])),
            "final": ls["ls_type"],
        })

    w_frase = max(len(f["frase"]) for f in filas)
    w_clasif = max(len(f["clasificador"]) for f in filas)
    w_final = max(len(f["final"]) for f in filas)

    header = (f"{'FRASE':<{w_frase}}  {'CLASIFICADOR':<{w_clasif}}  "
             f"{'EVIDENCIAS':<40}  {'REGLA':<45}  {'FINAL':<{w_final}}")
    print(header)
    print("-" * len(header))
    cambios = []
    for f in filas:
        print(f"{f['frase']:<{w_frase}}  {f['clasificador']:<{w_clasif}}  "
             f"{f['evidencias']:<40}  {f['regla']:<45}  {f['final']:<{w_final}}")
        if f["clasificador"] != f["final"]:
            cambios.append(f)

    print()
    print(f"{len(filas)} frases · {len(cambios)} con cambio de clase "
         f"(clasificador → final):")
    for f in cambios:
        print(f"  - {f['frase']}: {f['clasificador']} → {f['final']} "
             f"[{f['regla']}]")


if __name__ == "__main__":
    main()
