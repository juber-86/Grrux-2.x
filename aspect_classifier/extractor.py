"""Extracción de embeddings verbales con RoBERTa-BNE congelado.

Para cada lema del dataset limpio se construye una oración canónica
controlada, se localiza el span del verbo por offsets y se extrae el
hidden state de la capa configurada (mean pooling sobre subtokens).

Salidas:
    data/embeddings/embeddings.npy  (N x hidden_size, float32)
    data/embeddings/index.json      (metadatos alineados fila a fila)

Uso:
    python -m aspect_classifier.extractor
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml
from transformers import AutoModel, AutoTokenizer

PKG_DIR = Path(__file__).parent
CONFIG_PATH = PKG_DIR / "config.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def build_sentence(lema: str, transitivo: int, pronominal: int) -> tuple[str, int, int]:
    """Oración canónica controlada. Devuelve (oración, char_ini, char_fin) del verbo."""
    prefix = "El agente se " if pronominal else "El agente "
    suffix = " el objeto." if transitivo else "."
    sentence = f"{prefix}{lema}{suffix}"
    start = len(prefix)
    return sentence, start, start + len(lema)


class VerbEmbeddingExtractor:
    """Extrae el embedding del token verbal de una capa fija de RoBERTa-BNE."""

    def __init__(self, model_name: str, layer: int, device: str = "cpu"):
        # Silencia el aviso de pesos no inicializados del pooler (no usamos
        # el pooler); solo baja el logging de transformers a nivel error.
        from transformers import logging as hf_logging
        hf_logging.set_verbosity_error()
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name, output_hidden_states=True)
        self.model.eval().to(device)
        self.layer = layer
        self.device = device

    @torch.no_grad()
    def embed_char_spans(self, sentence: str, spans: list[tuple[int, int]]) -> np.ndarray:
        """Mean pooling de todos los subtokens que solapan CUALQUIERA de los
        char-spans [ini, fin) — admite complejos verbales discontiguos
        (p. ej. "se comió … pizza" saltándose el determinante)."""
        enc = self.tokenizer(sentence, return_offsets_mapping=True, return_tensors="pt")
        offsets = enc.pop("offset_mapping")[0].tolist()
        enc = {k: v.to(self.device) for k, v in enc.items()}
        # hidden_states[0] = embeddings; hidden_states[i] = salida de la capa i
        hidden = self.model(**enc).hidden_states[self.layer][0]

        token_ids = [
            i for i, (s, e) in enumerate(offsets)
            if s != e and any(s < fin and e > ini for ini, fin in spans)
        ]
        if not token_ids:
            raise ValueError(
                f"No se pudo alinear ningún span de {spans} en: {sentence!r}"
            )
        return hidden[token_ids].mean(dim=0).cpu().numpy().astype(np.float32)

    def embed_span(self, sentence: str, char_start: int, char_end: int) -> np.ndarray:
        """Embedding del span único [char_start, char_end) en offsets de
        carácter. Delega en embed_char_spans."""
        return self.embed_char_spans(sentence, [(char_start, char_end)])

    def embed_lemma(self, lema: str, transitivo: int = 0, pronominal: int = 0) -> np.ndarray:
        sentence, start, end = build_sentence(lema, transitivo, pronominal)
        return self.embed_span(sentence, start, end)


def run(config: dict | None = None) -> tuple[np.ndarray, list[dict]]:
    config = config or load_config()
    data_dir = PKG_DIR / Path(config["data"]["clean_csv"]).parent
    df = pd.read_csv(PKG_DIR / config["data"]["clean_csv"])

    extractor = VerbEmbeddingExtractor(
        model_name=config["extractor"]["model"],
        layer=config["extractor"]["layer"],
    )

    vectors, index = [], []
    for i, row in df.iterrows():
        transitivo = int(row["transitivo"]) if pd.notna(row["transitivo"]) else 0
        pronominal = int(row["pronominal"]) if pd.notna(row["pronominal"]) else 0
        sentence, start, end = build_sentence(row["lema"], transitivo, pronominal)
        vectors.append(extractor.embed_span(sentence, start, end))
        index.append({
            "row": int(i),
            "lema": row["lema"],
            "oracion": sentence,
            "clase": row["clase"],
            "stat": float(row["stat"]),
            "dyn": float(row["dyn"]),
            "tel": float(row["tel"]),
            "pun": float(row["pun"]),
        })
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(df)} embeddings extraídos")

    emb_dir = PKG_DIR / config["data"]["embeddings_dir"]
    emb_dir.mkdir(parents=True, exist_ok=True)
    matrix = np.stack(vectors)
    np.save(emb_dir / "embeddings.npy", matrix)
    with open(emb_dir / "index.json", "w") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)

    print(f"Guardado: {matrix.shape[0]} embeddings de dim {matrix.shape[1]} "
          f"(capa {config['extractor']['layer']}) en {emb_dir}")
    return matrix, index


if __name__ == "__main__":
    run()
