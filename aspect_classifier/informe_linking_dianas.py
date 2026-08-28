"""Checkpoint LA1 §3 — tabla de reconciliación: macropapeles por la AUH
(linking.asignar_macropapeles) vs la asignación YA existente (args_map,
deprel/plantilla) sobre la batería de dianas del proyecto. NO edita ningún
gold ni la EL — es un informe de SOLO LECTURA para que Julian revise las
discrepancias encontradas (probablemente indican bugs de una de las dos
vías, ver docstring de `linking.reconciliar`).

Ejecutar:
    ./venv/bin/python -m aspect_classifier.informe_linking_dianas
"""

import sys

# Misma batería reconstruida en informe_wrappers_dianas.py/
# informe_pruebas_estructurales.py (unión de las dianas históricas) + las
# oraciones propias de LA1 (ditransitiva, se-pasivo, pasiva perifrástica,
# estado de dos lugares, atransitivo).
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
    "Juan corrió en el parque",
    "Juan rezó durante la clase",
    "Pedro corrió por tres horas",
    "Juan llegó ayer",
    "Le compró un regalo a María",
    "Le dije la verdad",
    "Ayer Juan corrió tres horas en el parque",
]

NUEVAS_LA1 = [
    "Juan le dio flores a María",
    "Se venden casas",
    "Se vende casas",
    "Juan es médico",
    "La ventana está rota",
    "Juan está en la biblioteca",
    "Llegaron los invitados",
    "Llegó los invitados",
]


def main():
    import stanza
    import rrg_ls_mapper as m

    print("Cargando Stanza (es)...", file=sys.stderr)
    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    vistas = set()
    frases = [f for f in DIANAS + NUEVAS_LA1 if not (f in vistas or vistas.add(f))]

    filas = []
    for frase in frases:
        ls = m.map_sentence_to_ls(nlp(frase).sentences[0])
        linking_info = ls.get("linking")
        if not linking_info:
            filas.append({"frase": frase, "sin_linking": True})
            continue
        mp = linking_info["macropapeles"]
        psa = linking_info["psa"]
        conc = linking_info["concordancia"]
        # Las copulativas no traen reconciliación (§3): esa rama etiqueta el
        # macropapel como "Agent" -- literal preexistente, no Actor/Undergoer
        # -- comparar contra eso solo generaría ruido, ver rrg_ls_mapper.py.
        recon = linking_info.get("reconciliacion")
        filas.append({
            "frase": frase, "sin_linking": False, "clase": ls["ls_type"],
            "actor": mp["actor"]["texto"] if mp["actor"] else None,
            "undergoer": mp["undergoer"]["texto"] if mp["undergoer"] else None,
            "m": mp["m_transitividad"], "psa": psa["macrorol"],
            "concordancia_ok": conc.get("ok") if conc.get("aplica") else None,
            "recon": recon,
        })

    print(f"\n{len(filas)} frases analizadas.\n")
    print("=" * 78)
    print("TABLA DE RECONCILIACIÓN (§3): AUH (posicional) vs args_map (deprel)")
    print("=" * 78)
    discrepancias = []
    for f in filas:
        if f["sin_linking"]:
            print(f"[sin linking] {f['frase']}")
            continue
        if f["recon"] is None:
            marca = "  sin §3  "
        else:
            marca = "⚠ DISCREPA" if f["recon"]["hay_discrepancia"] else "  coincide"
        conc = ("—" if f["concordancia_ok"] is None
               else ("✓" if f["concordancia_ok"] else "⚠"))
        print(f"[{marca}] {f['frase']}  (clase={f['clase']}, M={f['m']}, "
             f"PSA={f['psa']}, concordancia={conc})")
        print(f"    Actor={f['actor']}  Undergoer={f['undergoer']}")
        if f["recon"] is None:
            print("    (copulativa: sin reconciliación §3, ver docstring)")
            print()
            continue
        for fila in f["recon"]["filas"]:
            simbolo = "✓" if fila["coincide"] else "✗"
            print(f"    {simbolo} {fila['macrorol_auh']}='{fila['texto']}' "
                 f"({fila['justificacion']}) vs args_map='{fila['macropapel_previo']}'")
        if f["recon"]["hay_discrepancia"]:
            discrepancias.append(f)
        print()

    print("=" * 78)
    print(f"RESUMEN: {len(discrepancias)}/{len([f for f in filas if not f['sin_linking']])} "
         "oraciones con discrepancia AUH↔args_map.")
    if discrepancias:
        print("\nDiagnóstico por discrepancia (para revisión de Julian):")
        for f in discrepancias:
            print(f"  · {f['frase']}")
    warnings_concordancia = [f for f in filas
                             if not f["sin_linking"] and f["concordancia_ok"] is False]
    print(f"\n{len(warnings_concordancia)} oración(es) con advertencia de concordancia:")
    for f in warnings_concordancia:
        print(f"  · {f['frase']}")


if __name__ == "__main__":
    main()
