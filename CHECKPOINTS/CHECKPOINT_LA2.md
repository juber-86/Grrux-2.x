# CHECKPOINT LA2 — causativas, tooltips y enrutado

Fecha: 2026-07-23. Se detiene aquí la etapa; no se inicia LA3.

## 1. Diana `Se venden casas`

Antes (hallazgo de LA1):

```text
formal  [do'(Ø, Ø)] CAUSE [do'(casas, [vender'(casas)])]
léxica [do'(Ø, Ø)] CAUSE [do'(casas, [vender'(casas)])]
```

Después, en la ruta heurística `se`:

```text
formal  [do'(Ø, Ø)] CAUSE [BECOME vendido'(x2)]
léxica [do'(Ø, Ø)] CAUSE [BECOME vendido'(casas)]
```

`casas` ocupa `arg_estado`; el exterior conserva el causante `Ø`. Se conserva la clase
base en `ls_type`/`ls_type_clasificador` y se añade `causativo_clase_derivada`, con valor
`realizacion_causativa` o `logro_causativo`. La salida legible muestra “Realización
causativa” y la traza conserva la fuente `EL`.

El linking esperado es Actor no asignado a `Ø`, Undergoer/Padecedor=`casas`, PSA=Undergoer,
concordancia 3pl↔3pl e integridad coherente. En `Se vende casas` solo cambia la concordancia
a warning 3pl↔3sg; la EL y el rol semántico se conservan.

## 2. Transición y clase visible

| Operador derivado | Clase visible | Base conservada |
|---|---|---|
| `BECOME` | Realización causativa | `Activity`/`Accomplishment` según el clasificador |
| `INGR` | Logro causativo | `Achievement` |

La decisión reutiliza la clase aspectual ya recibida por `componer_cause`; no se cambian
modelos ni clases de BERTIN. Para la heurística resultativa se usa el participio español
regular o irregular conocido (`vendido'`, `roto'`, etc.).

## 3. Tooltips

El lookup de nodos es exacto y canónico; las definiciones siguen en
`aspect_classifier/data/glosario_gruxx.csv`.

| Nodo | Entrada |
|---|---|
| N, N-PROP | sustantivo |
| V | verbo |
| P | preposición |
| NUC | NUC |
| PRED | PRED |
| NP, PP, ADVP | PP / NP / ADVP |
| AGX | AGX |
| PrDP, LDP | PrDP / LDP |
| PrCS | PrCS |
| CORE, CLAUSE, SENTENCE | SENTENCE/CLAUSE/CORE/NUC |
| `X-PERI` | `PERI@NUC`, `PERI@CORE` o `PERI@CLAUSE` según ancla |

La prueba fría `test_mapa_tooltips_exactos_n_v_p_y_cobertura` verifica `N`/`V`/`P` y la
cobertura del mapa sin coincidencias parciales.

## 4. Inventario canónico de enrutado

La fuente única es `aspect_classifier/gui_contract.py`, servida por `/contrato/gui` y
consumida por el contrato de análisis y la GUI. Incluye argumento CORE, NUC/PRED, AGX, las
10 categorías de periferia (`temporal`, `locativo`, `manera`, `aspectual`, `frecuencia`,
`razon`, `concesion`, `condicion`, `epistemico`, `generico`) en NUC/CORE/CLAUSE, PrDP/LDP y
PrCS. Cada entrada lleva clave estable, etiqueta, estrato, subtipo y automatización.

Las instancias ausentes se serializan con `elemento_id=null` y `(ausente)`. Una selección
ausente, PrCS o no automatizable registra origen, destino, ausencia y motivo en staging;
no muta el árbol. Las rutas automatizables existentes conservan reanálisis confirmatorio y
rollback. La API acepta retrocompatiblemente `elemento_id` y `destino`, y además
`ruta_origen`, `ruta_destino`.

## 5. Pruebas

- Pasan las pruebas frías nuevas de LA2, `test_l5.py` y `test_gruxx_server.py`.
- `node --check gui/app.js` pasa.
- La prueba integrada lenta de Stanza no pudo ejecutarse: el entorno no permite escribir
  en la caché de recursos ni resolver `raw.githubusercontent.com`; no se alteraron modelos
  ni se inició servidor/GUI concurrente.
- No se ejecutó PUD ni se modificaron `ud2rrg.py`, clasificadores, corroborador,
  `contextual_sentences.csv` ni golds.
- Las capturas de GUI de LA2 quedan pendientes de una sesión interactiva con modelos
  disponibles; no se presenta una captura preexistente como evidencia nueva.

## 6. Archivos y commits

Archivos de LA2: `aspect_classifier/causatividad.py`, `rrg_ls_mapper.py`,
`aspect_classifier/display_grr.py`, `gruxx_motor.py`, `gruxx_server.py`, `gui/app.js`,
`aspect_classifier/correccion.py`, `aspect_classifier/gui_contract.py`,
`aspect_classifier/test_la2.py`, el glosario y este checkpoint.

El árbol ya contenía cambios staged de LA1 antes de comenzar; se preservaron y no se
reformatearon. Commit creado: `c3d21657` (`LA2: causativas resultativas y enrutado
completo`). El índice ya contenía cambios de LA1; por eso Git los incluyó en ese commit y
no se reescribió la historia ni se descartó ningún cambio ajeno.
