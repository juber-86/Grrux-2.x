"""Carga y limpieza del conjunto de verbos semilla con clase aspectual.

Pipeline (Fase 1 del módulo aspect_classifier de grrux):
  1. Carga todas las hojas del Excel semilla.
  2. Normaliza las variantes ortográficas de la columna `clase`.
  3. Separa entradas ambiguas (State/Activity) -> ambiguous_cases.csv
  4. Separa entradas multipalabra ("correr 5km") -> multiword_cases.csv
  5. Resuelve conflictos de clase entre lemas duplicados por confianza
     (menor valor = más seguro: 1=seguro, 2=dudoso, 3=incierto).
     Empate con clases distintas -> se conservan ambas (ambigüedad legítima).
  6. Exporta dataset_clean.csv y muestra un reporte.

Uso:
    python -m aspect_classifier.load_data
"""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
XLSX_PATH = DATA_DIR / "conjunto_verbos_semilla_clase_aspectual.xlsx"
CLEAN_CSV = DATA_DIR / "dataset_clean.csv"
AMBIGUOUS_CSV = DATA_DIR / "ambiguous_cases.csv"
MULTIWORD_CSV = DATA_DIR / "multiword_cases.csv"

# Mapa exacto de normalización de las variantes ortográficas presentes
# en el Excel. Cualquier valor fuera de este mapa aborta la carga: una
# variante nueva debe revisarse a mano, no adivinarse.
CLASS_MAP = {
    "State": "State",
    "Activity": "Activity",
    "achivement ": "Achievement",
    "achivemet ": "Achievement",
    "Achievement": "Achievement",
    "semelfactivo ": "Semelfactive",
    "semelfactico ": "Semelfactive",
    "semelfactive": "Semelfactive",
    "semelfactive ": "Semelfactive",
    "semelfative": "Semelfactive",
    "Semelfactive": "Semelfactive",
    "Accomplishment": "Accomplishment",
    "Active Acc.": "Active_Accomplishment",
    "Active_Accomplishment": "Active_Accomplishment",
    "State / Activity": "AMBIGUOUS",
    "Activity / State": "AMBIGUOUS",
}

CANONICAL_CLASSES = [
    "State",
    "Activity",
    "Achievement",
    "Semelfactive",
    "Accomplishment",
    "Active_Accomplishment",
]

# Matriz aspectual de referencia [stat, dyn, tel, pun] por clase
# (Vendler/Van Valin). La usa la validación de consistencia y, más
# adelante, decision_tree.py como prototipos.
CLASS_PROTOTYPES = {
    "State": [1, 0, 0, 0],
    "Activity": [0, 1, 0, 0],
    "Achievement": [0, 0, 1, 1],
    "Semelfactive": [0, 0.5, 0, 1],
    "Accomplishment": [0, 0, 1, 0],
    "Active_Accomplishment": [0, 1, 1, 0],
}

FEATURES = ["stat", "dyn", "tel", "pun"]


def load_raw(xlsx_path: Path = XLSX_PATH) -> pd.DataFrame:
    """Carga y concatena todas las hojas del Excel."""
    sheets = pd.read_excel(xlsx_path, sheet_name=None)
    frames = []
    for name, df in sheets.items():
        df = df.copy()
        df["hoja"] = name
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)
    raw["lema"] = raw["lema"].astype(str).str.strip()
    return raw


def normalize_classes(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica CLASS_MAP sobre la columna `clase` (falla ante variantes nuevas)."""
    df = df.copy()
    unknown = set(df["clase"]) - set(CLASS_MAP)
    if unknown:
        raise ValueError(
            f"Variantes de clase no contempladas en CLASS_MAP: {sorted(map(repr, unknown))}"
        )
    df["clase_original"] = df["clase"]
    df["clase"] = df["clase"].map(CLASS_MAP)
    return df


def split_ambiguous(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa las entradas AMBIGUOUS del resto."""
    mask = df["clase"] == "AMBIGUOUS"
    return df[~mask].copy(), df[mask].copy()


def split_multiword(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa entradas multipalabra ("correr 5km") de los lemas simples."""
    mask = df["lema"].str.contains(r"\s")
    return df[~mask].copy(), df[mask].copy()


def _sort_key_confianza(s: pd.Series) -> pd.Series:
    """Menor confianza numérica = más seguro; NaN se trata como la peor."""
    return s.fillna(float("inf"))


def resolve_conflicts(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Deduplica lemas repetidos.

    - Misma clase: conserva la entrada con mejor confianza (menor valor).
    - Clases distintas: conserva la de mejor confianza; si empatan,
      conserva todas y marca `ambiguo_lexico=True`.

    Devuelve (df_resuelto, log de decisiones para el reporte).
    """
    df = df.copy()
    df["ambiguo_lexico"] = False
    log: list[dict] = []
    keep_parts = []
    for lema, group in df.groupby("lema", sort=False):
        if len(group) == 1:
            keep_parts.append(group)
            continue
        best = _sort_key_confianza(group["confianza"]).min()
        winners = group[_sort_key_confianza(group["confianza"]) == best]
        conflict = group["clase"].nunique() > 1
        if winners["clase"].nunique() > 1:
            # Empate entre clases distintas: ambigüedad legítima.
            winners = winners.copy()
            winners["ambiguo_lexico"] = True
            keep_parts.append(winners)
            log.append({
                "lema": lema,
                "clases": list(group["clase"]),
                "confianzas": list(group["confianza"]),
                "decision": f"EMPATE -> se conservan {len(winners)} entradas "
                            f"({' / '.join(winners['clase'])}) como ambigüedad legítima",
            })
        else:
            keep_parts.append(winners.head(1))
            kept = winners.iloc[0]
            motivo = "conflicto de clase" if conflict else "duplicado de la misma clase"
            log.append({
                "lema": lema,
                "clases": list(group["clase"]),
                "confianzas": list(group["confianza"]),
                "decision": f"{motivo} -> se conserva '{kept['clase']}' "
                            f"(confianza {kept['confianza']})",
            })
    resolved = pd.concat(keep_parts, ignore_index=True)
    return resolved, log


def check_feature_consistency(df: pd.DataFrame) -> pd.DataFrame:
    """Filas cuyos rasgos [stat,dyn,tel,pun] no coinciden con el prototipo de su clase."""
    proto = df["clase"].map(CLASS_PROTOTYPES)
    mismatch = df[FEATURES].apply(pd.to_numeric, errors="coerce").values != [list(p) for p in proto]
    return df[mismatch.any(axis=1)]


def run(xlsx_path: Path = XLSX_PATH, out_dir: Path = DATA_DIR) -> pd.DataFrame:
    raw = load_raw(xlsx_path)
    df = normalize_classes(raw)

    df, ambiguous = split_ambiguous(df)
    df, multiword = split_multiword(df)
    clean, conflict_log = resolve_conflicts(df)

    out_dir.mkdir(parents=True, exist_ok=True)
    clean.to_csv(out_dir / CLEAN_CSV.name, index=False)
    ambiguous.to_csv(out_dir / AMBIGUOUS_CSV.name, index=False)
    multiword.to_csv(out_dir / MULTIWORD_CSV.name, index=False)

    # ---- Reporte ----
    print(f"Filas totales en el Excel: {len(raw)} "
          f"({raw['hoja'].nunique()} hoja(s): {', '.join(raw['hoja'].unique())})")
    print()
    print("SPLITS")
    print(f"  dataset_clean.csv    : {len(clean):4d} entradas "
          f"({clean['lema'].nunique()} lemas únicos)")
    print(f"  ambiguous_cases.csv  : {len(ambiguous):4d} entradas")
    print(f"  multiword_cases.csv  : {len(multiword):4d} entradas")
    print()
    print("DISTRIBUCIÓN DE CLASES (dataset_clean)")
    counts = clean["clase"].value_counts()
    for cls in CANONICAL_CLASSES:
        n = counts.get(cls, 0)
        print(f"  {cls:<22} {n:4d}  {'█' * n}")
    print()
    print("CONFLICTOS/DUPLICADOS RESUELTOS")
    for entry in conflict_log:
        pares = ", ".join(
            f"{c} (conf={k})" for c, k in zip(entry["clases"], entry["confianzas"])
        )
        print(f"  {entry['lema']:<12} [{pares}]")
        print(f"      -> {entry['decision']}")
    print()
    inconsistent = check_feature_consistency(clean)
    if len(inconsistent):
        print(f"AVISO: {len(inconsistent)} entradas con rasgos que no coinciden "
              f"con el prototipo de su clase:")
        for _, row in inconsistent.iterrows():
            vec = [row[f] for f in FEATURES]
            print(f"  {row['lema']:<15} clase={row['clase']:<22} "
                  f"[stat,dyn,tel,pun]={vec} "
                  f"esperado={CLASS_PROTOTYPES[row['clase']]}")
    else:
        print("Consistencia rasgos/clase: OK (todas las filas coinciden con su prototipo)")
    return clean


if __name__ == "__main__":
    run()
