"""aspect_classifier — clasificación aspectual de predicados verbales (grrux).

Fase 1: clasificación léxica vía embeddings RoBERTa-BNE (congelado, capa 8)
+ 4 LogisticRegression por rasgo [stat, dyn, tel, pun] + árbol de decisión.
Fase 2 (futura): clasificación contextual con oración y span.
"""

from .predict import AspectClassifier

__all__ = ["AspectClassifier"]
