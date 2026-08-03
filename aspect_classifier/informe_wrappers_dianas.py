"""Checkpoint L1d — LS vieja (sin wrappers) vs LS nueva (con wrappers_ls) en
las dianas conocidas. NO edita ningún gold — es un informe de solo lectura
para que Julian apruebe (o no) el gold nuevo de las dianas que cambian.

Ejecutar:
    ./venv/bin/python -m aspect_classifier.informe_wrappers_dianas
"""

import sys

# Misma batería reconstruida en informe_pruebas_estructurales.py (unión de
# las dianas de test_nucleo_periferia/test_causatividad/test_fase2_contextual
# --slow) + frases nuevas que ejercitan wrappers_ls específicamente.
DIANAS = [
    "estudié tres horas anoche",
    "Juan corrió cinco kilómetros",
    "Juan corrió",
    "corrió",
    "el pastel fue comido por Juan",
    "llueve",
    "el jarrón se rompió",
    "El ruido asustó al niño",
    "El niño destrozó el juguete",
    "El sol secó la ropa",
    "El faro destelló una señal",
    "Juan rodó la pelota",
    "Juan paseó al perro",
    "El perro se sacudió",
    "Juan leyó el libro",
    "Juan se comió la pizza completa",
    "Juan corre todos los días",
    "Juan sabe la respuesta",
    "Juan llegó",
]

NUEVAS_WRAPPERS = [
    "Juan corrió en el parque",
    "Juan rezó durante la clase",
    "Pedro corrió por tres horas",
    "Juan llegó ayer",
    "Le compró un regalo a María",
    "Le dije la verdad",
    "Ayer Juan corrió tres horas en el parque",
]


def main():
    import stanza
    import rrg_ls_mapper as m

    print("Cargando Stanza (es)...", file=sys.stderr)
    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    vistas = set()
    frases = [f for f in DIANAS + NUEVAS_WRAPPERS
             if not (f in vistas or vistas.add(f))]

    cfg = m._aspect_clf.config["wrappers_ls"]
    filas = []
    for frase in frases:
        doc = nlp(frase).sentences[0]
        cfg["enabled"] = True
        nueva = m.map_sentence_to_ls(doc)
        cfg["enabled"] = False
        vieja = m.map_sentence_to_ls(doc)
        cfg["enabled"] = True
        filas.append({"frase": frase, "vieja": vieja["ls_formal"],
                      "nueva": nueva["ls_formal"],
                      "cambio": vieja["ls_formal"] != nueva["ls_formal"],
                      "clase_vieja": vieja["ls_type"],
                      "clase_nueva": nueva["ls_type"]})

    cambios = [f for f in filas if f["cambio"]]
    print(f"\n{len(filas)} frases · {len(cambios)} con LS distinta "
         f"(vieja→nueva) por wrappers_ls:\n")
    for f in filas:
        marca = "★ CAMBIA" if f["cambio"] else "  igual "
        print(f"[{marca}] {f['frase']}")
        print(f"    vieja : {f['vieja']}")
        if f["cambio"]:
            print(f"    nueva : {f['nueva']}")
        if f["clase_vieja"] != f["clase_nueva"]:
            print(f"    ⚠ CLASE CAMBIÓ: {f['clase_vieja']} → {f['clase_nueva']}")
        print()

    print("=" * 72)
    print(f"RESUMEN: {len(cambios)}/{len(filas)} dianas ganan wrapper. "
         "Ninguna diana debería cambiar de CLASE aspectual (solo LS) — "
         "si alguna sí, es un caso a reportar a Julian, no a forzar.")
    cambios_clase = [f for f in filas if f["clase_vieja"] != f["clase_nueva"]]
    if cambios_clase:
        print(f"⚠ {len(cambios_clase)} diana(s) CAMBIARON DE CLASE:")
        for f in cambios_clase:
            print(f"    {f['frase']}: {f['clase_vieja']} → {f['clase_nueva']}")
    else:
        print("✓ Ninguna diana cambió de clase aspectual (solo LS/wrappers).")


if __name__ == "__main__":
    main()
