# Project Briefing: `aspect_classifier` — Clasificación Aspectual con RoBERTa-BNE
**Para:** Claude Cowork  
**Proyecto:** `grrux` / `ud2rrg`  
**Fecha:** Julio 2026  
**Autor:** Julian (profesor e investigador de lingüística)

---

## 1. Contexto general del proyecto

Julian desarrolla `grrux`, un sistema de análisis sintáctico-semántico del español basado en **Role and Reference Grammar (RRG)**. El objetivo final es que el sistema tome una oración en español y produzca su **estructura lógica (LS)** según la formalización de Van Valin.

Un componente crítico de ese pipeline es conocer la **clase aspectual** del predicado verbal, porque la clase determina qué operadores aspectuales aparecen en la LS (`INGR`, `BECOME`, `SEML`, etc.) y cómo se construye la representación semántica completa.

El módulo `aspect_classifier` es el componente encargado de esa clasificación. Es un sistema independiente que puede invocarse desde `grrux` con una interfaz simple: se le pasa un lema verbal (y opcionalmente una oración completa con el span del verbo) y devuelve la clase aspectual con un score de confianza.

---

## 2. Las 6 clases aspectuales de Vendler/Van Valin

El sistema clasifica predicados en estas 6 clases, definidas por 4 rasgos binarios/difusos:

| Clase | stat | dyn | tel | pun | Ejemplo |
|---|---|---|---|---|---|
| State | 1 | 0 | 0 | 0 | saber, creer, tener |
| Activity | 0 | 1 | 0 | 0 | correr, nadar, hablar |
| Achievement | 0 | 0 | 1 | 1 | llegar, morir, reconocer |
| Semelfactive | 0 | 0.5 | 0 | 1 | estornudar, toser, parpadear |
| Accomplishment | 0 | 0 | 1 | 0 | construir, escribir, pintar |
| Active Accomplishment | 0 | 1 | 1 | 0 | correr 5km, leer el libro |

**Notas teóricas importantes:**
- `dyn` es el único rasgo que admite el valor `0.5`, para casos `±dynamic` (Semelfactive, y verbos en la frontera State/Activity como *pensar* o *esperar*).
- La clase aspectual **no es una propiedad fija del verbo**: depende del contexto oracional. *Comer* es Activity en "Juan come todos los días" pero Active Accomplishment en "Juan se come la pizza" (el clítico aspectual *se* + objeto definido y acotado imponen telicidad). El sistema debe poder manejar ambos casos.
- Hay una clase adicional `State_Activity` (6 verbos en el dataset: *pensar*, *imaginar*, *pesar*, *medir*, *esperar*, *flotar*) que representa ambigüedad léxica genuina. Estos verbos están excluidos del entrenamiento pero documentados.

---

## 3. Arquitectura del sistema: Idea 3 — Probing Classifiers

### Decisión de diseño

Se eligió la arquitectura de **probing classifiers sobre embeddings congelados de RoBERTa-BNE** (`PlanTL-GOB-ES/roberta-base-bne`). Las razones:

- RoBERTa-BNE es un modelo encoder-only (~125M parámetros), mucho más pequeño que un LLM generativo. Corre en CPU en milisegundos en inferencia.
- El modelo está congelado: no se fine-tunea. Solo se usa como extractor de representaciones semánticas.
- Sobre esos embeddings se entrenan 4 clasificadores lineales (LogisticRegression de sklearn), uno por rasgo aspectual: `stat`, `dyn`, `tel`, `pun`.
- La salida de cada clasificador es una probabilidad P ∈ [0,1], formando un **vector difuso** que alimenta un árbol de decisión con umbrales configurables.
- El costo computacional de RoBERTa se paga una sola vez (extracción offline de embeddings). La inferencia en producción es solo una multiplicación de matrices + árbol de decisión.

### Por qué no un LLM completo

Tokens y costo prohibitivos para análisis a escala. Hardware fuera del alcance del consumidor promedio. RoBERTa-BNE corre localmente en cualquier laptop moderna.

### Por qué RoBERTa-BNE y no BETO

- Arquitectura encoder-only sin NSP (Next Sentence Prediction), que contamina las representaciones en BETO.
- Corpus de entrenamiento más limpio y más grande (BNE + otros).
- Embeddings más isotrópicos → mejor separabilidad lineal para el probing classifier.

---

## 4. Dataset semilla

### Composición

- **Archivo:** `conjunto_verbos_semilla_clase_aspectual.xlsx`
- **3 hojas:** Grupo A (States/Activities), Grupo B (Achievements/Semelfactives), Grupo C (Accomplishments/Active Accomplishments)
- **341 filas totales, 198 lemas únicos** tras deduplicar
  - 164 lemas simples (verbos individuales)
  - 34 entradas multipalabra (frases como "correr 5km", "leer el libro" — útiles para Fase 2)

### Columnas (header en fila 0)

```
lema | stat | dyn | tel | pun | clase | transitivo | pronominal | confianza | notas
```

- `confianza`: 1 = seguro, 2 = dudoso, 3 = muy incierto
- `pronominal`: 1 si el verbo lleva clítico aspectual (*se*) en su uso canónico
- `clase`: tiene variantes ortográficas que se normalizan en preprocessing

### Distribución de clases (post-limpieza)

| Clase | N |
|---|---|
| Achievement | 40 |
| Activity | 35 |
| Accomplishment | 32 |
| Active_Accomplishment | 29 |
| State | 28 |
| Semelfactive | 28 |
| State_Activity (excluidos) | 6 |

### Problemas ya conocidos del dataset

1. **Variantes ortográficas de clase** (resueltas en `load_data.py`): `achivemet`, `achivement`, `semelfactivo`, `semelfactico`, `semelfative` → todas normalizadas.
2. **3 verbos con clase conflictiva entre hojas**: `brillar` (Activity/Semelfactive), `escribir` (Activity/Accomplishment), `olvidar` (Semelfactive/State). Estrategia: conservar la entrada con mayor confianza (menor número en columna `confianza`).
3. **34 entradas multipalabra**: excluidas del entrenamiento Fase 1, guardadas en `multiword_cases.csv` para Fase 2.
4. **6 entradas ambiguas** (State/Activity): guardadas en `ambiguous_cases.csv`, excluidas del entrenamiento.

---

## 5. Implementación actual

### Archivos del módulo `aspect_classifier/`

```
aspect_classifier/
├── __init__.py
├── load_data.py        ✅ implementado y funcionando
├── extractor.py        ✅ implementado y funcionando
├── classifier.py       ✅ implementado y funcionando
├── decision_tree.py    ✅ implementado y funcionando
├── train.py            ✅ implementado y funcionando
├── predict.py          ✅ implementado — Fase 2 contextual ACTIVA
├── config.yaml         ✅ implementado — umbrales y pesos configurables
├── models/             ✅ contiene clasificadores entrenados (.pkl)
└── data/
    ├── conjunto_verbos_semilla_clase_aspectual.xlsx
    ├── dataset_clean.csv
    ├── ambiguous_cases.csv
    └── multiword_cases.csv
```

### `load_data.py`
Carga el Excel, aplica normalización de clases, resuelve conflictos por confianza, separa multipalabra y ambiguos. Exporta `dataset_clean.csv` y los CSVs auxiliares.

### `extractor.py`
Para cada lema construye una oración canónica controlada según `transitivo` y `pronominal`:
- Transitivo: `"El agente [LEMA] el objeto."`
- Intransitivo: `"El agente [LEMA]."`
- Pronominal: `"El agente se [LEMA]."`

Carga RoBERTa-BNE congelado, tokeniza, localiza el token verbal por alineación de offsets, extrae el hidden state de la **capa 8 de 12**. Si el verbo se tokeniza en subtokens, hace mean pooling. Guarda embeddings en `embeddings.npy` + `index.json`.

### `classifier.py`
4 `LogisticRegression` independientes de sklearn, uno por rasgo. Salida: P ∈ [0,1]. El rasgo `dyn` usa `predict_proba` continua para capturar el valor 0.5 de los casos ±dynamic.

### `decision_tree.py`
Árbol de decisión con umbrales configurables en `config.yaml`. Orden de nodos basado en ganancia de información sobre la matriz aspectual:

```
Nodo 1: stat ≥ θ₁  →  State (o State_Activity si dyn ≈ 0.5)
Nodo 2: pun ≥ θ₂   →  Achievement (si tel≥θ₃)  o  Semelfactive (si tel<θ₃)
Nodo 3: tel ≥ θ₃   →  Accomplishment (si dyn<θ₄)  o  Active_Accomplishment (si dyn≥θ₄)
Nodo 4: dyn ≥ θ₄   →  Activity
Default:            →  clase más cercana por distancia euclidiana al prototipo
```

### `predict.py` — Estado actual (Fase 2 implementada)

La función `predict` ahora acepta dos modos:

```python
# Fase 1: clasificación léxica (solo lema)
result = clf.predict("cocinar")

# Fase 2: clasificación contextual (lema + oración + span del verbo)
result = clf.predict("cocinar",
                     oracion="Juan se come la pizza",
                     span=(2, 4))
```

**Cómo funciona Fase 2:**
1. Extrae embedding léxico (oración canónica, igual que Fase 1).
2. Extrae embedding contextual: tokeniza la oración real, localiza el token verbal en el span dado, extrae hidden state de capa 8.
3. Combina ambas probabilidades con peso configurable: `P_final = (1 - peso_contextual) * P_léxica + peso_contextual * P_contextual`. El parámetro `fase2.peso_contextual: 0.5` vive en `config.yaml`.
4. El vector combinado pasa por el árbol de decisión.

**Antes** `predict` con `oracion=` lanzaba `NotImplementedError`. Ahora está completamente implementado.

### Cambios en `rrg_ls_mapper.py`

La cascada anterior `VERB_CLASSES → morph → LLM` fue eliminada de la clasificación aspectual. Ahora cada oración pasa el verbo con su span a `predict(lema, oracion=..., span=...)` y el árbol de decisión asigna la clase. `VERB_CLASSES` se conserva en el archivo solo como datos de referencia estáticos. Si los modelos no están entrenados, el sistema falla con mensaje claro en lugar de degradar silenciosamente.

### Cambios en `grrux_ai1.py`

La salida ahora incluye:
```
Clasificado por: 🧠 roBERTa (aspect_classifier)
Vector aspect.   stat=0.00 dyn=0.08 tel=0.00 pun=0.64 conf=0.72 (contextual)
```

---

## 6. Resultados de evaluación (estado actual)

Evaluación con cross-validation estratificada sobre `dataset_clean.csv`:

| Rasgo | Métrica | Valor |
|---|---|---|
| stat | F1 | ~0.90+ |
| dyn | F1 | ~0.85 |
| tel | F1 | ~0.83 |
| pun | F1 | ~0.78 |

| Clase | F1 aproximado |
|---|---|
| State | alto (~0.88) |
| Activity | alto (~0.85) |
| Achievement | medio-alto |
| Accomplishment | medio |
| Active_Accomplishment | medio (ver limitación 2) |
| **Semelfactive** | **bajo (~0.51) — clase más débil** |

---

## 7. Limitaciones conocidas (a resolver en pasos siguientes)

### Limitación 1 — Semelfactive sobredisparado (error conocido de Fase 1)
**Ejemplo:** "El hielo se derritió" → clasifica Semelfactive (debería ser Accomplishment)  
**Causa:** el rasgo `pun` se sobredispara con ciertos verbos de cambio de estado. Semelfactive es la clase con F1 más bajo (0.51).  
**Solución:** más datos semilla, no cambios de código. Se necesitan más ejemplos prototípicos de Semelfactive verdadero vs. verbos de cambio de estado.

### Limitación 2 — Active_Accomplishment casi nunca se activa en Fase 1
**Ejemplo:** "Juan corrió cinco kilómetros" → clasifica Activity, no Active_Accomplishment  
**Causa:** los 29 ejemplos de Active_Accomplishment en el dataset son todos multipalabra ("correr 5km", "leer el libro"), por lo que están excluidos del entrenamiento Fase 1. El regresor de telicidad no aprende a activar Active_Accomplishment para lemas simples.  
**Solución natural:** entrenar Fase 2 con `multiword_cases.csv` en contexto real. Cuando se pase la oración completa, el contexto ("cinco kilómetros", objeto definido) debería activar correctamente la telicidad.

### Limitación 3 — Verbos causativos sin clase propia
**Verbos afectados:** ~23 verbos causativos (matar, abrir, quemar, derretir, romper…)  
**Causa:** el dataset semilla no tiene categoría 'causative'. Estos verbos reciben una clase Vendler simple (típicamente Achievement o Accomplishment según el verbo).  
**Opciones:**  
  a) Añadir 'causative' como séptima clase al dataset semilla y reentrenar.  
  b) Detectar causatividad por separado (morfología + estructura argumental) y tratarla como modificador de la clase base.  
  c) Dejar como está si la granularidad actual es suficiente para la LS de RRG.

---

## 8. Pasos siguientes (en orden de prioridad)

### Paso 1 — Ampliar dataset para Semelfactive (inmediato)
Anotar 20-30 ejemplos adicionales de Semelfactive prototípico, asegurando contraste claro con verbos de cambio de estado. Usar la guía de anotación existente. Reentrenar tras añadir al Excel.

### Paso 2 — Implementar entrenamiento con multiword_cases para Fase 2
Usar `multiword_cases.csv` como ejemplos de entrenamiento contextual para Active_Accomplishment. El embedding se extrae de la frase completa, no del lema aislado. Esto debería subir significativamente el F1 de esa clase.

### Paso 3 — Integración con el parser de Stanza
El span del verbo que necesita `predict(..., span=...)` ya está disponible en el árbol de dependencias UD que produce Stanza. Hay que escribir la función que extrae el span del verbo + clíticos dependientes + núcleo del OD directamente desde el output CoNLL-U. Esto convierte Fase 2 en el flujo por defecto cuando el sistema tiene una oración completa.

### Paso 4 — Decisión sobre verbos causativos
Discutir con Julian qué nivel de granularidad necesita la LS de RRG para causativos antes de implementar.

### Paso 5 — Replicación en Windows 11 y macOS
El pipeline completo está desarrollado en Zorin OS (Linux). Verificar compatibilidad de dependencias en otros sistemas operativos para ampliar accesibilidad.

---

## 9. Interfaz completa del módulo

```python
from aspect_classifier import AspectClassifier

clf = AspectClassifier()
clf.load("models/")          # carga los 4 clasificadores .pkl entrenados

# --- Fase 1: clasificación léxica ---
result = clf.predict("cocinar")
# Devuelve:
# {
#   "clase": "Accomplishment",
#   "vector": {"stat": 0.03, "dyn": 0.12, "tel": 0.91, "pun": 0.08},
#   "confianza": 0.84,
#   "metodo": "lexical"
# }

# --- Fase 2: clasificación contextual ---
result = clf.predict("comer",
                     oracion="Juan se come la pizza",
                     span=(2, 4))          # índices de tokens en la oración
# Devuelve:
# {
#   "clase": "Active_Accomplishment",
#   "vector": {"stat": 0.01, "dyn": 0.87, "tel": 0.83, "pun": 0.06},
#   "confianza": 0.81,
#   "metodo": "contextual"
# }
```

---

## 10. Stack técnico y entorno

- **Python 3.10** (requerido — 3.12 incompatible con disco-dop, otra dependencia del proyecto)
- `transformers` — RoBERTa-BNE (HuggingFace)
- `scikit-learn` — LogisticRegression, cross-validation
- `torch` — solo para extracción de embeddings, no en inferencia
- `pandas`, `openpyxl` — manejo del dataset
- `numpy` — vectores de embeddings
- `pyyaml` — configuración de umbrales
- **Modelo:** `PlanTL-GOB-ES/roberta-base-bne` (~500MB, descarga automática de HuggingFace)
- **Entorno de desarrollo:** ThinkPad con Zorin OS (primario), Python 3.10 venv

---

## 11. Lo que este documento NO cubre

- El resto del pipeline `grrux`/`ud2rrg`: parsing UD con Stanza, conversión CoNLL-U → RRG, construcción completa de la LS. Eso está en documentación separada (`guia_ud2rrg_español.pdf`).
- La integración con ADESSE (Universidad de Vigo) como alternativa basada en argumentos verbales — fue considerada y descartada en favor del probing classifier, pero puede retomarse si los resultados del classifier son insuficientes.
- El módulo de anotación interactiva para estudiantes — existe como herramienta pedagógica separada.
```
