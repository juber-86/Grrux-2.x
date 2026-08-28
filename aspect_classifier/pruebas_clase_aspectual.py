"""Corroborador Van Valin — las pruebas de clase aspectual como juicios
de aceptabilidad con la cabeza MLM de BERTIN (sin reentrenar).

Segunda opinión ORTOGONAL al probing por embeddings: cada prueba se
operacionaliza como un CONTRASTE de par mínimo (nunca umbral absoluto,
para robustez a frecuencia léxica). Batería REAL del vector (veredicto
del checkpoint de Julian) — solo p1/p45/p6 alimentan el corroborador:

  1  Progresivo    "está {gerundio}" vs "{presente}"     -> pun (y stat):
      progresivo raro (s1 bajo) => evento puntual/estativo; es la señal
      más limpia (romper 0.01 / estornudar 0.16 vs correr 0.92 en s1).
  4/5 Durativo/terminativo: "{pret} [MASK] una hora",
      logit(en) - logit(durante) — máscara única, 1 forward -> tel.
      El ranking del Δ es correcto pero está DESPLAZADO ("en" gana
      siempre por frecuencia): se recentra con bias_mask (calibración).
  6  Participial   "El objeto está {participio}"          -> aporte LEVE
      a tel (estado resultante ~= telicidad). NO discrimina
      Achievement-vs-Semelfactive (falla: "estornudado" da 0.72).

Solo DIAGNÓSTICO (evaluar(..., diagnostico=True); NO entran al vector):
  2  Adv dinámico  "{pret} vigorosamente" vs neutro       -> inútil (no
      discrimina: todos ~=1, "saber" incluido).
  3  Adv de ritmo  "{pret} lentamente" vs "de repente"    -> inútil ("de
      repente" gana con cualquier pretérito por frecuencia narrativa).
  7  Paráfrasis causativa: la cubre el léxico causativo (Paso 4).

dyn NO tiene señal en esta batería (p2 descartada) -> se devuelve None,
que el blend trata como λ_dyn = 0 efectivo.
Los frames (construir_frames) son puros; solo evaluar() toca el modelo.
"""

import math
from pathlib import Path

from .gen_contextual_sentences import (OBJ, gerundio, participio,
                                       presente_3sg, preterito_3sg)

PKG_DIR = Path(__file__).parent

DEFAULTS = {
    "adv_dinamico": "vigorosamente",     # p2: solo diagnóstico (no vector)
    "adv_neutro": "aparentemente",
    "adv_durativo": "lentamente",        # p3: solo diagnóstico (no vector)
    "adv_puntual": "de repente",
    "prep_terminativa": "en",
    "prep_durativa": "durante",
    # temperaturas de la sigmoide (Δ→[0,1])
    "temperatura_pll": 0.5,              # Δ de media de pseudo-log-likelihood
    "temperatura_mask": 4.0,             # Δ de logits en máscara única
    # offset de centrado del contraste en/durante: el ranking del Δ es
    # correcto pero está desplazado (+: "en" gana siempre por frecuencia).
    # Se fija en la calibración.
    "bias_mask": 0.0,
    # peso de p6 (participio resultativo) dentro de tel; auxiliar de bajo
    # peso por decisión de Julian (falla en "estornudado")
    "peso_p6_en_tel": 0.2,
}


def _lema_base(lema: str) -> str:
    """Quita el clítico enclítico '-se' de infinitivos pronominales
    (detenerse→detener, volcarse→volcar) para poder conjugarlos: el rasgo
    pronominal ya lo marca el marco por separado. Un infinitivo español
    solo termina en '-se' cuando el 'se' es enclítico."""
    if lema.endswith(("arse", "erse", "irse")):
        return lema[:-2]
    return lema


def _od_de(lema: str) -> str | None:
    """OD específico del lema desde el mapa curado de gen_contextual_sentences
    ("Juan sabe la respuesta", no "Juan sabe el objeto")."""
    od = OBJ.get(lema)
    if od is None:
        od = next((v for k, v in OBJ.items()
                   if isinstance(k, tuple) and k[0] == lema), None)
    return od


def _sujeto_y_marco(lema: str, transitivo: int, pronominal: int):
    """(sujeto, clítico, OD) del frame canónico según el marco del léxico."""
    if pronominal:
        return "El objeto", "se ", ""            # anticausativo/medio
    if transitivo:
        return "Juan", "", f" {_od_de(lema) or 'el objeto'}"
    return "Juan", "", ""


def construir_frames(lema: str, transitivo: int = 0, pronominal: int = 0,
                     cfg: dict | None = None) -> dict:
    """Frames de las pruebas 1-6 para un lema. Puro: sin modelo.

    Cada prueba es un par mínimo (a, b) — el contraste es Δ = PLL(a)−PLL(b) —
    salvo la telicidad, que es una plantilla con [MASK] y dos rellenadores.
    p6 usa sujeto genérico "El objeto está {part}." en transitivos/pronominales
    para evitar la concordancia género/número con el OD específico del lema.
    """
    c = {**DEFAULTS, **(cfg or {})}
    suj, se, od = _sujeto_y_marco(lema, transitivo, pronominal)
    base = _lema_base(lema)                       # detenerse→detener para conjugar
    pret, pres = preterito_3sg(base), presente_3sg(base)
    ger, part = gerundio(base), participio(base)

    return {
        "p1_progresivo": (f"{suj} {se}está {ger}{od}.",
                          f"{suj} {se}{pres}{od}."),
        "p2_dinamico":   (f"{suj} {se}{pret}{od} {c['adv_dinamico']}.",
                          f"{suj} {se}{pret}{od} {c['adv_neutro']}."),
        "p3_ritmo":      (f"{suj} {se}{pret}{od} {c['adv_durativo']}.",
                          f"{suj} {se}{pret}{od} {c['adv_puntual']}."),
        "p45_telicidad": {"plantilla": f"{suj} {se}{pret}{od} [MASK] una hora.",
                          "candidatos": (c["prep_terminativa"],
                                         c["prep_durativa"])},
        "p6_participial": (f"El objeto está {part}." if (transitivo or pronominal)
                           else f"{suj} está {part}.",
                           f"El objeto se está {ger}." if pronominal
                           else (f"El objeto está siendo {part}." if transitivo
                                 else f"{suj} está {ger}.")),
    }


def _sigmoide(delta: float, tau: float) -> float:
    return 1.0 / (1.0 + math.exp(-delta / tau))


def _score_p45(delta: float, cfg: dict) -> float:
    """Score de telicidad de p45 desde el Δ CRUDO de logits, recentrado por
    bias_mask: s = σ((Δ − bias_mask) / temperatura_mask). Pura y testeable
    sin MLM (el bias se puede recalibrar sobre Δ cacheados)."""
    bias = cfg.get("bias_mask", DEFAULTS["bias_mask"])
    tau = cfg.get("temperatura_mask", DEFAULTS["temperatura_mask"])
    return _sigmoide(delta - bias, tau)


class CorroboradorVanValin:
    """Evalúa las pruebas con la cabeza MLM de BERTIN (pesos ya en caché;
    se cargan perezosamente y una sola vez)."""

    def __init__(self, model_name: str = "bertin-project/bertin-roberta-base-spanish",
                 device: str = "cpu", cfg: dict | None = None):
        self.model_name = model_name
        self.device = device
        self.cfg = {**DEFAULTS, **(cfg or {})}
        self._tok = None
        self._mlm = None

    def _cargar(self):
        if self._mlm is None:
            from transformers import (AutoModelForMaskedLM, AutoTokenizer,
                                      logging as hf_logging)
            hf_logging.set_verbosity_error()
            self._tok = AutoTokenizer.from_pretrained(self.model_name)
            self._mlm = AutoModelForMaskedLM.from_pretrained(self.model_name)
            self._mlm.eval().to(self.device)

    def _pll_media(self, oracion: str) -> float:
        """Pseudo-log-likelihood media (mask-one-out, en un solo batch)."""
        import torch
        self._cargar()
        enc = self._tok(oracion, return_tensors="pt")
        ids = enc["input_ids"][0]
        n = len(ids) - 2                     # sin <s> ni </s>
        if n <= 0:
            return 0.0
        lote = ids.unsqueeze(0).repeat(n, 1)
        pos = torch.arange(1, n + 1)
        lote[torch.arange(n), pos] = self._tok.mask_token_id
        with torch.no_grad():
            logits = self._mlm(input_ids=lote.to(self.device)).logits
        logp = torch.log_softmax(logits[torch.arange(n), pos], dim=-1)
        return float(logp[torch.arange(n), ids[pos]].mean())

    def _contraste_pll(self, par: tuple[str, str]) -> tuple[float, float]:
        delta = self._pll_media(par[0]) - self._pll_media(par[1])
        return delta, _sigmoide(delta, self.cfg["temperatura_pll"])

    def _contraste_mask(self, plantilla: str,
                        candidatos: tuple[str, str]) -> tuple[float, float]:
        """Δ de logits entre dos rellenadores de una máscara única, con el
        offset de centrado bias_mask aplicado: s = sigmoide((Δ − bias)/τ).
        Si algún candidato no es monotoken, cae a PLL de las dos oraciones."""
        import torch
        self._cargar()
        ids_cand = [self._tok.encode(f" {c}", add_special_tokens=False)
                    for c in candidatos]
        if any(len(i) != 1 for i in ids_cand):
            par = tuple(plantilla.replace("[MASK]", c) for c in candidatos)
            return self._contraste_pll(par)
        enc = self._tok(plantilla.replace("[MASK]", self._tok.mask_token),
                        return_tensors="pt")
        pos = (enc["input_ids"][0] == self._tok.mask_token_id).nonzero()[0, 0]
        with torch.no_grad():
            logits = self._mlm(input_ids=enc["input_ids"].to(self.device)).logits
        delta = float(logits[0, pos, ids_cand[0][0]]
                      - logits[0, pos, ids_cand[1][0]])
        # Recentrado por bias_mask (calibrable). El Δ CRUDO se devuelve intacto
        # para poder recalibrar el bias sin recomputar el MLM.
        return delta, _score_p45(delta, self.cfg)

    def evaluar(self, lema: str, transitivo: int = 0,
                pronominal: int = 0, diagnostico: bool = False) -> dict:
        """Corre las pruebas del vector (p1/p45/p6) y devuelve el vector
        corroborador. Con diagnostico=True computa ADEMÁS p2/p3 (4 PLLs
        extra) SOLO para el detalle; por defecto no se pagan.

        vector: {stat, dyn, tel, pun}. dyn es None (SIN SEÑAL: p2 descartada);
        el blend lo trata como λ_dyn = 0 efectivo.
          pun  = 1 − s1     (progresivo raro ⇒ evento puntual)
          stat = 1 − s1     (mismo lado negativo de p1; la atenuación la pone
                             λ_stat bajo en el blend, no una fórmula aparte)
          tel  = (1 − peso_p6_en_tel)·s45 + peso_p6_en_tel·s6
                             (s45 ya recentrado por bias_mask en _contraste_mask)
          dyn  = None
        El `detalle` conserva el Δ CRUDO de p45 (no recentrado) para la
        calibración del bias.
        """
        frames = construir_frames(lema, transitivo, pronominal, self.cfg)
        detalle = {}

        d1, s1 = self._contraste_pll(frames["p1_progresivo"])
        detalle["p1_progresivo"] = {
            "frames": frames["p1_progresivo"],
            "delta": round(d1, 3), "score": round(s1, 3),
            "verdicto": "progresivo OK (dinámico/durativo)"
            if s1 >= 0.5 else "progresivo raro (estativo o puntual)"}

        d45, s45 = self._contraste_mask(
            plantilla=frames["p45_telicidad"]["plantilla"],
            candidatos=frames["p45_telicidad"]["candidatos"])
        detalle["p45_telicidad"] = {
            "frames": frames["p45_telicidad"],
            "delta": round(d45, 3), "score": round(s45, 3),
            "verdicto": "télico ('en una hora')"
            if s45 >= 0.5 else "atélico ('durante una hora')"}

        d6, s6 = self._contraste_pll(frames["p6_participial"])
        detalle["p6_participial"] = {
            "frames": frames["p6_participial"],
            "delta": round(d6, 3), "score": round(s6, 3),
            "verdicto": "estado resultante (aporta a tel)"
            if s6 >= 0.5 else "sin estado resultante"}

        if diagnostico:
            d2, s2 = self._contraste_pll(frames["p2_dinamico"])
            detalle["p2_dinamico"] = {
                "frames": frames["p2_dinamico"],
                "delta": round(d2, 3), "score": round(s2, 3),
                "verdicto": ("+dinámico" if s2 >= 0.5 else "−dinámico")
                + " (DIAGNÓSTICO; fuera del vector)"}
            d3, s3 = self._contraste_pll(frames["p3_ritmo"])
            detalle["p3_ritmo"] = {
                "frames": frames["p3_ritmo"],
                "delta": round(d3, 3), "score": round(s3, 3),
                "verdicto": ("durativo" if s3 >= 0.5 else "puntual")
                + " (DIAGNÓSTICO; fuera del vector)"}

        peso_p6 = float(self.cfg.get("peso_p6_en_tel", 0.2))
        tel = (1 - peso_p6) * s45 + peso_p6 * s6
        vector = {"stat": round(1 - s1, 4),
                  "dyn": None,                      # SIN SEÑAL (p2 descartada)
                  "tel": round(tel, 4),
                  "pun": round(1 - s1, 4)}
        return {"vector": vector, "pruebas": detalle}


# ---------------------------------------------------------------------------
# CHECKPOINT LIGERO: revisión lingüística de los frames (y evidencia real
# de los contrastes con --evidencia) antes de calibrar.
# ---------------------------------------------------------------------------
CHECKPOINT_LEMAS = [("estudiar", 1, 0), ("estornudar", 0, 0),
                    ("romper", 1, 1), ("correr", 0, 0)]


def checkpoint_frames() -> None:
    for lema, trans, pron in CHECKPOINT_LEMAS:
        frames = construir_frames(lema, trans, pron)
        print(f"\n── {lema} (transitivo={trans}, pronominal={pron}) ──")
        for nombre, par in frames.items():
            if isinstance(par, dict):
                print(f"  {nombre:<15} {par['plantilla']}  "
                      f"candidatos={par['candidatos']}")
            else:
                print(f"  {nombre:<15} ✓ {par[0]}")
                print(f"  {'':<15} ✗ {par[1]}")


def evidencia(lemas_marcos=None, diagnostico=True) -> None:
    corr = CorroboradorVanValin()

    def fmt(x):
        return "  — " if x is None else f"{x:.2f}"

    for lema, trans, pron in (lemas_marcos or CHECKPOINT_LEMAS):
        r = corr.evaluar(lema, trans, pron, diagnostico=diagnostico)
        v = r["vector"]
        print(f"\n── {lema} ── vector: stat={fmt(v['stat'])} dyn={fmt(v['dyn'])} "
              f"tel={fmt(v['tel'])} pun={fmt(v['pun'])}")
        for nombre, d in r["pruebas"].items():
            print(f"  {nombre:<15} Δ={d['delta']:+.3f} s={d['score']:.2f}  {d['verdicto']}")


if __name__ == "__main__":
    import sys
    checkpoint_frames()
    if "--evidencia" in sys.argv:
        evidencia()
