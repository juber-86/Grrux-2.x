"""Interfaz pública del clasificador aspectual.

    from aspect_classifier import AspectClassifier

    clf = AspectClassifier()
    clf.load("aspect_classifier/models")
    clf.predict("cocinar")
    # {"clase": "...", "vector": {...}, "confianza": 0.84, "metodo": "lexical"}
"""

from pathlib import Path

import numpy as np
import pandas as pd

from .classifier import FeatureClassifiers
from .decision_tree import classify
from .extractor import VerbEmbeddingExtractor, load_config

PKG_DIR = Path(__file__).parent


class AspectClassifier:
    """Clasificación aspectual de predicados verbales en español (Vendler/Van Valin)."""

    def __init__(self, config_path: Path | None = None):
        self.config = load_config(config_path or PKG_DIR / "config.yaml")
        self.thresholds = self.config.get("decision_tree", {})
        self.classifiers: FeatureClassifiers | None = None
        self._extractor: VerbEmbeddingExtractor | None = None
        self.classifiers_ctx: FeatureClassifiers | None = None
        self._lexicon: pd.DataFrame | None = None
        # Corroborador Van Valin (MLM BERTIN): carga perezosa + caché de
        # evaluar() por (lema, transitivo, pronominal).
        self._corroborador = None
        self._pruebas_cache: dict[tuple, dict] = {}

    def load(self, models_dir: str | Path = PKG_DIR / "models") -> "AspectClassifier":
        self.classifiers = FeatureClassifiers.load(Path(models_dir))
        # Cabeza contextual (entrenada con embeddings complex-pooled).
        # Opcional: si no existe, Fase 2 usa la léxica sobre emb_ctx (fallback).
        ctx_dir = Path(models_dir) / "contextual"
        try:
            self.classifiers_ctx = FeatureClassifiers.load(ctx_dir)
        except FileNotFoundError:
            self.classifiers_ctx = None
        clean_csv = PKG_DIR / self.config["data"]["clean_csv"]
        if clean_csv.exists():
            self._lexicon = pd.read_csv(clean_csv).drop_duplicates("lema").set_index("lema")
        return self

    @property
    def extractor(self) -> VerbEmbeddingExtractor:
        # Carga perezosa: RoBERTa-BNE solo se instancia en el primer predict.
        if self._extractor is None:
            self._extractor = VerbEmbeddingExtractor(
                model_name=self.config["extractor"]["model"],
                layer=self.config["extractor"]["layer"],
            )
        return self._extractor

    @property
    def corroborador(self):
        """Corroborador Van Valin, instanciado PEREZOSAMENTE con la sección
        `pruebas` de config.yaml y el mismo model_name que declara el módulo.
        El MLM de BERTIN se carga en el primer evaluar(), no aquí."""
        if self._corroborador is None:
            from .pruebas_clase_aspectual import CorroboradorVanValin
            self._corroborador = CorroboradorVanValin(
                cfg=self.config.get("pruebas", {}))
        return self._corroborador

    def _pruebas_vec(self, lema: str, transitivo: int, pronominal: int) -> dict:
        """evaluar() del corroborador, cacheado por (lema, transitivo, pronominal)."""
        clave = (lema, transitivo, pronominal)
        if clave not in self._pruebas_cache:
            self._pruebas_cache[clave] = self.corroborador.evaluar(
                lema, transitivo, pronominal)
        return self._pruebas_cache[clave]

    def _marco_sintactico(self, lema: str) -> tuple[int, int]:
        """(transitivo, pronominal) desde el lexicón semilla; (0, 0) si es desconocido."""
        if self._lexicon is not None and lema in self._lexicon.index:
            row = self._lexicon.loc[lema]
            return int(row["transitivo"]), int(row["pronominal"])
        return 0, 0

    def _localizar_verbo(self, oracion: str, lema: str) -> tuple[int, int]:
        """Span (char_ini, char_fin) del token verbal en la oración.

        Busca el lema exacto; si no aparece (forma conjugada), toma el token
        con el prefijo compartido más largo con el lema (mínimo 4 caracteres).
        """
        low = oracion.lower()
        pos = low.find(lema.lower())
        if pos != -1:
            return pos, pos + len(lema)

        stem = lema.lower().rstrip("aeiour")  # quita terminación de infinitivo
        best, best_len = None, 3
        offset = 0
        for token in oracion.split():
            common = 0
            t = token.lower().strip(".,;:!?¿¡\"'()")
            for a, b in zip(t, lema.lower()):
                if a != b:
                    break
                common += 1
            if common > best_len and common >= min(4, len(stem)):
                start = oracion.index(token, offset)
                best, best_len = (start, start + len(token.strip(".,;:!?¿¡\"'()"))), common
            offset = oracion.index(token, offset) + len(token)
        if best is None:
            raise ValueError(
                f"No se encontró el verbo '{lema}' en la oración; pasa 'span' explícito."
            )
        return best

    def predict(
        self,
        lema: str,
        oracion: str | None = None,
        span: tuple[int, int] | list[tuple[int, int]] | None = None,
    ) -> dict:
        """Clasifica un predicado verbal.

        Fase 1 (solo lema): embedding del verbo en oración canónica.
        Fase 2 (con `oracion`): combina el vector léxico con el embedding
        contextual. `span` son OFFSETS DE CARÁCTER sobre `oracion`:
          - (char_ini, char_fin) para el token del verbo, o
          - [(ini, fin), ...] para un complejo verbal posiblemente
            discontiguo (ver complejo_verbal.extraer_complejo).
        Si se omite, el verbo se localiza automáticamente.
        """
        if self.classifiers is None:
            raise RuntimeError("Modelos no cargados: llama a .load() primero.")

        transitivo, pronominal = self._marco_sintactico(lema)
        emb_lex = self.extractor.embed_lemma(lema, transitivo, pronominal)
        probs = self.classifiers.predict_proba(emb_lex)[0]
        metodo = "lexical"

        if oracion is not None:
            if span is None:
                char_spans = [self._localizar_verbo(oracion, lema)]
            elif isinstance(span[0], (tuple, list)):
                char_spans = [tuple(s) for s in span]
            else:
                char_spans = [tuple(span)]
            emb_ctx = self.extractor.embed_char_spans(oracion, char_spans)
            # La cabeza contextual se entrenó con embeddings complex-pooled:
            # solo se usa cuando el pooling de entrada sigue esa receta
            # (fase2.usar_complejo_verbal). Con el flag apagado se conserva
            # el comportamiento previo (cabeza léxica sobre emb_ctx).
            usar_ctx = self.config.get("fase2", {}).get("usar_complejo_verbal", False)
            if usar_ctx and self.classifiers_ctx is not None:
                probs_ctx = self.classifiers_ctx.predict_proba(emb_ctx)[0]
            else:
                if usar_ctx:
                    import warnings
                    warnings.warn(
                        "Cabeza contextual no cargada (models/contextual/); "
                        "fallback: cabeza léxica sobre el embedding contextual. "
                        "Entrena con: python -m aspect_classifier.train_contextual"
                    )
                probs_ctx = self.classifiers.predict_proba(emb_ctx)[0]
            w = float(self.config.get("fase2", {}).get("peso_contextual", 0.5))
            probs = (1 - w) * probs + w * probs_ctx
            metodo = "contextual"

        from .classifier import FEATURES
        vector_probe = {f: round(float(p), 4) for f, p in zip(FEATURES, probs)}

        # ── Corroborador Van Valin: blend per-rasgo ──────────────────────
        #   P_final[f] = (1 − λ_f)·P_probe[f] + λ_f·P_pruebas[f]
        # con λ desde config.pruebas.lambdas. Si P_pruebas[f] es None (rasgo
        # sin señal, p. ej. dyn) → λ_f = 0 efectivo.
        lambdas = self.config.get("pruebas", {}).get("lambdas", {}) or {}
        lambdas = {f: float(lambdas.get(f, 0.0)) for f in FEATURES}

        vector_pruebas = None
        pruebas_detalle = None
        probs_final = probs

        # FAST PATH: si todas las λ son 0, el corroborador no participa y el
        # MLM NI se carga (regresión cero en resultado Y en tiempo).
        if any(lambdas[f] > 0.0 for f in FEATURES):
            try:
                res = self._pruebas_vec(lema, transitivo, pronominal)
                vp = res["vector"]
                pruebas_detalle = res["pruebas"]
                vector_pruebas = dict(vp)         # incluye None en rasgos sin señal
                blended = []
                for i, f in enumerate(FEATURES):
                    pv = vp.get(f)
                    if pv is None:                # sin señal → solo probe
                        blended.append(float(probs[i]))
                    else:
                        lam = lambdas[f]
                        blended.append((1 - lam) * float(probs[i]) + lam * float(pv))
                probs_final = np.array(blended)
                metodo = f"{metodo}+pruebas"
            except Exception as exc:              # MLM no carga / error del corroborador
                import warnings
                warnings.warn(
                    f"Corroborador Van Valin no disponible ({exc}); "
                    "degradando a solo-probe (pipeline intacto)."
                )
                probs_final = probs
                vector_pruebas = None
                pruebas_detalle = None

        vector = {f: round(float(p), 4) for f, p in zip(FEATURES, probs_final)}
        decision = classify(vector, self.thresholds)
        return {
            "clase": decision["clase"],
            "vector": vector,                     # vector FINAL (tras el blend)
            "vector_probe": vector_probe,
            "vector_pruebas": vector_pruebas,     # None si el corroborador no participó
            "pruebas_detalle": pruebas_detalle,
            "confianza": decision["confianza"],
            "metodo": metodo,                     # "…+pruebas" si el corroborador participó
            "regla": decision["regla"],
        }
