"""Sub-paso 2.2 — Extracción de embeddings contextuales (complex-pooled).

Para cada oración de data/contextual_sentences.csv (revisado por el
lingüista): parse con Stanza → desde_stanza() → extraer_complejo() →
embed_char_spans() con BERTIN capa 8. MISMA receta de pooling que usa
rrg_ls_mapper en inferencia — prohibido reimplementarla en paralelo.

Salidas:
    data/embeddings/embeddings_ctx.npy
    data/embeddings/index_ctx.json

Uso:
    python -m aspect_classifier.extractor_contextual
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .complejo_verbal import desde_stanza, extraer_complejo
from .extractor import VerbEmbeddingExtractor, load_config

PKG_DIR = Path(__file__).parent


def run(config: dict | None = None) -> tuple[np.ndarray, list[dict]]:
    import stanza

    config = config or load_config()
    fase2_cfg = config["fase2"]
    csv_path = PKG_DIR / config["data"].get(
        "contextual_csv", "data/contextual_sentences.csv")
    df = pd.read_csv(csv_path)

    # REGLA DE HIGIENE (Pre-Paso 4): al entrenamiento solo entran filas
    # con revisar=False. Todo skip se lista explícitamente (0 silenciosos).
    revisar = df["revisar"].astype(str).str.lower().isin(("true", "1"))
    pendientes = df[revisar]
    if len(pendientes):
        print(f"EXCLUIDAS por revisar=True ({len(pendientes)}; pendientes de curaduría):")
        for _, r in pendientes.iterrows():
            print(f"  id={r['id']}: {r['oracion']!r} [{r['clase']}]")
    df = df[~revisar]

    print(f"[1/3] Parseando {len(df)} oraciones con Stanza...")
    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    print("[2/3] Cargando BERTIN y extrayendo embeddings complex-pooled...")
    extractor = VerbEmbeddingExtractor(
        model_name=config["extractor"]["model"],
        layer=config["extractor"]["layer"],
    )

    vectors, index, descartadas = [], [], []
    for _, row in df.iterrows():
        doc = nlp(row["oracion"])
        if len(doc.sentences) != 1:
            descartadas.append((row["id"], row["oracion"], "múltiples oraciones"))
            continue
        sent = doc.sentences[0]
        tokens = desde_stanza(sent.words)
        root_id = next((t["id"] for t in tokens if t["head"] == 0), None)
        if root_id is None or sent.words[root_id - 1].upos != "VERB":
            descartadas.append((row["id"], row["oracion"],
                                f"raíz no verbal ({sent.words[root_id - 1].upos if root_id else 'sin raíz'})"))
            continue

        comp = extraer_complejo(tokens, root_id, fase2_cfg)
        # El "texto" de extraer_complejo ES lo que se poolea: única fuente
        # de verdad de los offsets (mismo contrato que en inferencia).
        emb = extractor.embed_char_spans(comp["texto"], comp["spans"])

        vectors.append(emb)
        index.append({
            "id": int(row["id"]),
            "lema": row["lema"],
            "oracion": row["oracion"],
            "texto": comp["texto"],
            "clase": row["clase"],
            "stat": float(row["stat"]), "dyn": float(row["dyn"]),
            "tel": float(row["tel"]), "pun": float(row["pun"]),
            "fuente": row["fuente"],
            "incluidos": [
                {"id": t["id"], "text": t["text"], "deprel": t["deprel"]}
                for t in tokens if t["id"] in comp["incluidos"]
            ],
        })

    print("[3/3] Guardando...")
    emb_dir = PKG_DIR / config["data"]["embeddings_dir"]
    emb_dir.mkdir(parents=True, exist_ok=True)
    matrix = np.stack(vectors)
    np.save(emb_dir / "embeddings_ctx.npy", matrix)
    with open(emb_dir / "index_ctx.json", "w") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)

    # ---- Reporte ----
    print(f"\n{matrix.shape[0]} embeddings de dim {matrix.shape[1]} "
          f"(capa {config['extractor']['layer']}, receta complex_pool)")
    n_con_od = sum(1 for e in index
                   if any(t["deprel"] in fase2_cfg.get("od_like_deprels", ["obj"])
                          for t in e["incluidos"]))
    n_con_clitico = sum(1 for e in index
                        if any(t["deprel"].startswith("expl") for t in e["incluidos"]))
    print(f"Complejos con núcleo de OD: {n_con_od} | con clítico: {n_con_clitico}")
    if descartadas:
        print(f"\nDESCARTADAS ({len(descartadas)}):")
        for id_, o, motivo in descartadas:
            print(f"  id={id_}: {o!r} — {motivo}")
    else:
        print("Descartadas: 0")
    return matrix, index


if __name__ == "__main__":
    run()
