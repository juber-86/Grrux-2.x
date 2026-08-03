# Checkpoint — Reentrenamiento `augment_habitual` (presente) + recalibración
# + segunda oportunidad del corroborador

Implementado según `prompt_opus48_reentrenamiento_habitual.md`. **NO se hizo
ningún commit** (orden vigente de Julian) — todo queda en el árbol de
trabajo. Backups completos del estado previo (embeddings, cabeza contextual,
config.yaml) en el scratchpad de esta sesión, por si se decide revertir.
**PARAR aquí** — hay una regresión real (ver §6) que necesita el visto
bueno de Julian antes de seguir.

## 1. Extracción (68 nuevas)

531/536 filas extraídas (5 excluidas por `revisar=True`: nadan/sanan/
hipan/palmea/eructa, exactamente las 5 de siempre, ninguna del lote nuevo).
**Las 68 nuevas (ids 469-536) se extrajeron TODAS limpias — 0 descartadas
por parse.** Verificado explícitamente que los pares con "se" agrupan bien
el complejo verbal (69 complejos con clítico en el total, consistente con
el diseño del lote). Complejos con núcleo de OD: 288/531.

## 2. CV antes/después (misma metodología, `train_contextual`,
   StratifiedGroupKFold(5) por lema — comparación limpia, no la del prompt
   que viene de otro script/held-out)

| | ANTES (n=463) | DESPUÉS (n=531) |
|---|---|---|
| F1 stat | 0.793 ± 0.083 | 0.794 ± 0.105 |
| F1 dyn | 0.788 ± 0.061 | 0.775 ± 0.073 |
| F1 tel | 0.856 ± 0.036 | 0.827 ± 0.036 |
| F1 pun | 0.703 ± 0.048 | 0.696 ± 0.102 |
| F1 clase Accomplishment | 0.37 | 0.32 |
| F1 clase Achievement | 0.59 | 0.57 |
| F1 clase Active_Accomplishment | 0.74 | 0.71 |
| F1 clase Activity | 0.69 | 0.68 |
| F1 clase Semelfactive | 0.50 | 0.49 |
| F1 clase State | 0.77 | **0.83** |
| macro-F1 / accuracy | 0.52 / 0.62 | 0.51 / 0.61 |

**Lectura honesta**: en agregado (CV sobre TODO el dataset, mezclando
tiempos), pun/dyn NO mejoran — de hecho dyn y tel bajan un poco, y std de
pun casi se duplica (0.048→0.102, más varianza). State mejora claramente
(los 10 casos de contrapeso hacen su trabajo). Esto es esperable: los 68
casos nuevos son específicamente los DIFÍCILES (presente habitual, el
punto ciego conocido) y ahora entran en el promedio agregado — la mejora
real no se ve aquí, se ve en las 5 dianas (§4) y en el daño colateral (§6).

## 3. Config recalibrada — guardarraíl demostrado

Held-out NUEVO (StratifiedGroupKFold fold 1, 112 oraciones/42 lemas —
cambió con el dataset, no comparable 1:1 con el 0.796 de Pre-Paso 4).

- Config vigente (w=0.5, dyn=0.40, pun=0.45, tel=0.35) en el held-out
  nuevo: **macro-F1 0.827**.
- Ganadora del barrido: **w=0.55, dyn=0.45, pun=0.40, tel=0.40 → macro-F1
  0.838** (Semelf 0.89, State 1.00, AA 0.70). Guardarraíl cumplido
  (0.838 ≥ 0.827). Aplicada en `config.yaml` (`fase2.peso_contextual` y
  `decision_tree`), documentada in situ igual que las calibraciones
  previas.

## 4. Las 5 dianas del bug de comer — antes/después/después-de-recalibrar

| Frase | Crudo ANTES | Crudo tras retrain | Crudo tras recalibrar | Final (las 3 etapas) |
|---|---|---|---|---|
| Juan come | semelfactive (pun=0.51) | **activity** (pun=0.42) | semelfactive (pun=0.42, ahora sobre el umbral 0.40) | activity (gate obj_desnudo) |
| Juan come manzanas | semelfactive (pun=0.53) | **activity** (pun=0.33) | **activity** | activity, **sin gate** |
| Juan come manzanas siempre | semelfactive (pun=0.52) | **activity** (pun=0.10) | **activity** | activity, **sin gate** |
| Juan se come las manzanas | accomplishment (pun=0.39) | **active_accomplishment** (pun=0.05) | **active_accomplishment** | AA, **sin gate** |
| Juan come la manzana | achievement (pun=0.52) | **active_accomplishment** (pun=0.14) | **active_accomplishment** | AA, **sin gate** |

**Resultado: éxito ideal en 4/5 (sin gate), éxito aceptable en la 5ª**
("Juan come" vuelve a depender del gate tras bajar pun a 0.40 — ver
trade-off documentado en `config.yaml`; el gate la corrige igual, la
salida final nunca estuvo en riesgo). Las 5 salen bien en la clase FINAL,
las 5 con pun lejos del borde de 0.51-0.54 original. Esto es exactamente
lo que pedía el bug de campo.

## 5. Corroborador Van Valin — segunda oportunidad: NO gana

Held-out nuevo (112/42, tras retrain+recalibración):
- ANTES (probe-solo): macro-F1 = 0.838
- MEJOR del barrido: λ_stat=0.1, λ_tel=0.3 (pun y dyn se anulan a 0),
  bias_mask=2.5 → **macro-F1 = 0.843 (+0.005)**. Guardarraíl OK (mejora,
  no lo viola).
- **La hipótesis del prompt NO se confirma**: la ganancia no viene de
  λ_pun (que se anula a 0, igual que el 07-08) — P1/progresivo no termina
  "aplastando" el pun espurio de comer en el agregado del held-out. Viene
  de stat/tel.
- **Veredicto**: se deja **APAGADO** (λ=0), mismo criterio que Julian ya
  aplicó el 07-08 (+0.002 entonces, +0.005 ahora — mismo orden de
  magnitud, dentro del ruido para n=112, no compensa perder el fast path).
  El bug de comer ya se arregló con datos+recalibración; el corroborador
  no aporta nada específico a ESE problema.

## 6. Batería completa — el juez final: **una regresión real confirmada**

### 6a. Las 5 dianas nuevas: 5/5 correctas en clase final (ver §4).

### 6b. Dianas históricas / 26 de wrappers (`informe_pruebas_estructurales`,
`informe_wrappers_dianas`) — **3 cambios de clase nuevos, 1 es regresión
real, 1 es "regresión de test" (mejora real), 1 es deriva sin test**:

| Frase | Antes | Después | ¿Hay test que lo detecte? |
|---|---|---|---|
| **Juan corrió cinco kilómetros** | active_accomplishment | **activity** | Sí — 2 tests fallan (ver 6c) |
| el pastel fue comido por Juan | accomplishment | active_accomplishment | No (sin assert de clase) |
| llueve | activity | active_accomplishment | Test lo salta a propósito ("smoke-only") |
| corrió vigorosamente | activity | **semelfactive** | No (sin assert de clase) |

**"Juan corrió cinco kilómetros" es una regresión real y NO se puede
arreglar con umbrales**: tras el reentrenamiento su `tel` en el blend cae
a ~0.34, por debajo de CUALQUIER valor del barrido de calibración (mínimo
0.35). Ni siquiera manteniendo `tel=0.35` (el umbral viejo) se salva —
0.34 < 0.35 igual. Es una propiedad del reentrenamiento (la cabeza
contextual mueve el regresor de `tel` para frases de medida), no un error
de mi elección de umbral. **Reportado a Julian, NO corregido ad-hoc**
(prohibido tocar gold).

"el pastel fue comido por Juan" y "corrió vigorosamente" no rompen ningún
test existente pero son cambios de comportamiento reales que vale la pena
que Julian revise (pasiva perfectiva pasando a AA; adverbio de manera
disparando semelfactive en vez de activity).

### 6c. Suites completas: **164 tests (159 rápidos + 5 lentos con
diferencias), 5 fallos** — desglose:

1. `test_fase2_contextual.test_slow_dianas_aa_y_controles`: **"Juan
   corrió cinco kilómetros"** — regresión confirmada (§6b).
2. `test_telicidad_l4_5.test_slow_guardarraíl_dianas_historicas_sin_regresion`:
   misma regresión, detectada por la suite L4.5 (otra sesión, gates
   compuestos).
3. `test_telicidad_l4_5.test_slow_cinco_dianas_telicidad_composicional`:
   **NO es una regresión real** — falla porque para 3/5 dianas ("Juan come
   manzanas", "...siempre", "Juan come la manzana") el test exige que
   aparezca la nota del gate (`obj_desnudo`/`obj_delimitado`) en
   `morph_note`, pero AHORA el clasificador acierta SOLO y el gate ni
   dispara (no hay nota que poner). Es la prueba objetiva de que el paso
   1-3 funcionó: el "cinturón de seguridad" ya no hace falta para estos 3
   casos. La aserción de esa prueba quedó desactualizada por el propio
   éxito de esta tarea — **no la toqué** (es de otra tarea/sesión, L4.5;
   dejo la decisión de relajarla a Julian).
4. `test_causatividad.test_slow_cause_por_clase_y_regresion` ("El perro se
   sacudió": esperado semelfactive, obtenido activity) — **PRE-EXISTENTE**,
   confirmado corriendo la batería ANTES de tocar nada. No relacionado con
   este lote.
5. `test_pruebas_aspectuales.test_slow_blend_sube_pun` — **PRE-EXISTENTE**
   (corroborador MLM, territorio prohibido, ya fallaba el 10-jul en la
   sesión de L3 también).

Los fallos 4 y 5 estaban ANTES de que yo tocara nada (verificado
explícitamente corriendo la batería completa antes del paso 1). El fallo 3
es deseable, no dañino. Los fallos 1-2 son la MISMA regresión real
("kilómetros"), detectada por dos suites distintas.

Suites sin cambios: `causatividad` (salvo el fallo pre-existente),
`complejo`, `completeness`, `ditransitivas` (18/18 con `--slow`, incluida
la batería de 26 dianas ditransitivas — sin regresión), `misc_rrg`,
`nucleo_periferia`, `pruebas_estructurales` (25/25), `ud2rrg_es`,
`wrappers_ls` (22/22) — **todas verdes**.

## Decisión pendiente de Julian

El estado actual del árbol de trabajo (embeddings + cabeza contextual +
`config.yaml` recalibrado, corroborador apagado) queda tal cual para que
Julian decida, con toda la evidencia arriba:

1. **Aceptar tal cual**: gana el bug de comer (4/5 sin gate, 5/5 en clase
   final) a cambio de una diana histórica rota ("cinco kilómetros",
   sin arreglo por umbral) + 2 derivas sin test (pastel, vigorosamente).
2. **Curar más datos**: el lote `augment_habitual` no tiene ninguna
   frase de medida ("cinco kilómetros", "tres horas") en presente — podría
   ser la causa de que el regresor de `tel` se desplace para ese patrón;
   un lote de contrapeso específico para medidas podría revertir la
   regresión sin perder la ganancia en presente. No implementado (no era
   parte del alcance de este prompt).
3. **Revertir**: hay backups completos (embeddings viejos, cabeza
   contextual vieja, `config.yaml` viejo) en el scratchpad de esta sesión;
   revertir es una copia de 3 archivos si Julian prefiere no arriesgar
   "cinco kilómetros" y esperar más datos.

No tomé ninguna de las tres decisiones por mi cuenta — dejo el árbol de
trabajo en el estado (2) de la tarea (reentrenado+recalibrado+corroborador
evaluado y apagado) porque es literalmente lo que pedían los pasos 1-5 del
prompt, pero el veredicto final de "¿se despliega?" es de Julian, tal como
pide el protocolo de "PARAR y reportar" del prompt.
