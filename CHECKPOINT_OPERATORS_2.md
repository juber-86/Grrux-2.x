# CHECKPOINT — Etapa OPERATORS_2 (EL ortodoxa + corrección de operadores + fix de export)

Implementa `prompt_OPERATORS_2.md`. **Sin commits.** `ud2rrg.py` intacto; clasificador,
corroborador MLM y `contextual_sentences.csv` sin tocar. PUD intocado.

---

## 1. Inventario de pseudo-predicados + tabla EL-vieja → EL-nueva

### Inventario COMPLETO (lo que se buscó y lo que apareció)

| # | Pseudo-predicado | Dónde se generaba | Operador que ya lo expresa | Acción |
|---|---|---|---|---|
| 1 | `complet(…)` | `build_ls`, vía `aux_asp` | `⟨ASP PERF⟩` | **eliminado** |
| 2 | `prog(…)` | `build_ls`, vía `aux_asp` | `⟨ASP PROG⟩` | **eliminado** |
| 3 | `no'(…)` | wrapper de periferia (tipo genérico) | `⟨NEG⟩` | **eliminado** |
| 4 | `maybe'` `probably'` `surely'` `possibly'` `obviously'` `evidently'` | wrapper `epistemicos` | `⟨STA IRR/REAL⟩` | **eliminado** |
| 5 | `tal'(…)` | wrapper epistémico sobre "tal vez" | `⟨STA IRR⟩` | **eliminado** (era además un bug: usaba el lema de "Tal" suelto, no la locución) |

**Buscados y descartados** (NO son pseudo-predicados — contenido léxico, se quedan):
`yesterday'`/`today'`/`last.night'`, `be-in'`/`be-on'`/…, `during'`/`for'`/`at'`/`before'`,
`despite'`/`because-of'`/`in-case-of'`, `every'`/`always'`/`often'`, la manera
(`lentamente'`), los aspectuales de fase/grado (`completely'`, `gradually'`), `apparently'`.

### Dos casos de frontera resueltos SIN perder información

- **`never'` ('nunca')** — Stanza le pone `Polarity=Neg`, así que ⟨NEG⟩ se le disparaba. Pero
  'nunca' FUSIONA negación con cuantificación de evento; reducirla a ⟨NEG⟩ perdería la parte
  cuantificacional, porque EVQ no está implementado. **Decisión:** ⟨NEG⟩ dispara solo con el
  negador puro ('no', lista `operadores.negadores`); 'nunca'/'jamás'/'tampoco' conservan su
  predicado léxico. TODO documentado: con EVQ deberían ser `⟨NEG ⟨EVQ …⟩⟩`.
- **`apparently'` ('aparentemente')** — es evidencial (EVID), no epistémico, y EVID no está
  implementado: no dispara operador, así que **conserva su wrapper**.

Esto se garantiza por CONSTRUCCIÓN, no por lista: la supresión se hace por **id de token**
(`operadores.tokens_cubiertos` → `componer_wrappers(..., cubiertos_por_operador)`). El criterio
es exactamente "¿este token disparó un operador?", así que nada puede desaparecer sin tener un
operador que lo represente.

### Tabla de auditoría — 25 dianas probadas, **12 EL cambiadas, 0 clases cambiadas**

| # | oración | EL ANTES | EL DESPUÉS |
|---|---------|----------|------------|
| 1 | Juan ha estudiado. | `complet(do'(Juan, [estudiar'(Juan)]))` | `do'(Juan, [estudiar'(Juan)])` |
| 2 | Juan está corriendo. | `prog(do'(Juan, [correr'(Juan)]))` | `do'(Juan, [correr'(Juan)])` |
| 3 | ¿Ha estado llorando Juan? | `complet(do'(Juan, [llorar'(Juan)]))` | `do'(Juan, [llorar'(Juan)])` |
| 4 | Juan había estudiado. | `complet(do'(Juan, [estudiar'(Juan)]))` | `do'(Juan, [estudiar'(Juan)])` |
| 5 | Juan ha comido la pizza. | `complet(do'(Juan, [comer'(Juan, pizza)]) & INGR consumed'(pizza))` | `do'(Juan, [comer'(Juan, pizza)]) & INGR consumed'(pizza)` |
| 6 | Juan no corrió. | `no'([do'(Juan, [correr'(Juan)])])` | `do'(Juan, [correr'(Juan)])` |
| 7 | Juan no ha estudiado. | `no'([complet(do'(Juan, [estudiar'(Juan)]))])` | `do'(Juan, [estudiar'(Juan)])` |
| 8 | Quizá venga María. | `maybe'([do'(María, [venir'(María)])])` | `do'(María, [venir'(María)])` |
| 9 | Tal vez Juan estudie. | `tal'([do'(Juan, [estudiar'(Juan)])])` | `do'(Juan, [estudiar'(Juan)])` |
| 10 | Probablemente Juan corrió. | `probably'([do'(Juan, [correr'(Juan)])])` | `do'(Juan, [correr'(Juan)])` |
| 11 | Seguramente Juan estudió. | `surely'([do'(Juan, [estudiar'(Juan)])])` | `do'(Juan, [estudiar'(Juan)])` |
| 12 | Obviamente Juan corrió. | `obviously'([do'(Juan, [correr'(Juan)])])` | `do'(Juan, [correr'(Juan)])` |

**13 dianas SIN cambio** (control de que no se llevó nada por delante): `never'`,
`apparently'`, `yesterday'(be-in'(…))`, `lentamente'`, `during'`, `every'`, `despite'`,
`completely'`, la ditransitiva CAUSE, y las oraciones simples/copulativas.

**Ninguna otra desviación de gold** fuera de este cambio (protocolo cumplido).

`completeness.py`: un elemento cubierto por operador se reporta `ok` con
`"no"↔operador ⟨NEG⟩`, no como advertencia nueva ni como "no verificable".

---

## 2. Demo de corrección de operadores (los 4 caminos)

Ejecutada con `config.yaml` y `data/` **temporales** — los reales quedaron intactos
(verificado: 0 filas `operador` en el log real, ninguna marca nueva en config).

| caso | qué se corrige | ruta elegida por gruxx | resultado |
|---|---|---|---|
| **(a)** | 'presumiblemente' no está en la lista de STA | **config EN VIVO** `adv_epistemicos_irreal` | `persistido_operador` ✓ re-análisis confirma: aparece `STA=IRR` |
| **(b)** | 'soler' no está en `operadores.modales` (MAPA) | **config EN VIVO** `modales` | `persistido_operador` ✓ re-análisis confirma: aparece `MOD=OBLG` |
| **(c)** | "Cómete la manzana." debería ser `IF=IMP` | **staging** (error de parse) | `staging_operador` + mensaje honesto |
| **(d)** | quitar un ⟨NEG⟩ que no debería estar | **staging** | `staging_operador` |
| **(e)** | `TNS = PLUSCUAM` | rechazo | `error: valor no válido para TNS` (sin tocar nada) |

Diff real escrito en config por (a) y (b):

```diff
+    soler: OBLG  # correccion_usuario
-                           probablemente, seguramente, a lo mejor]
+                           probablemente, seguramente, a lo mejor, presumiblemente]  # correccion_usuario
```

`correcciones_operadores.csv` (staging) guarda la **señal de origen**, sin la cual la fila no
serviría para diagnosticar:

```
fecha,oracion,operador,valor_predicho,valor_correcto,senal_origen,motivo,fuente
…,Cómete la manzana.,IF,DEC,IMP,declarativa (default),no hay lista de config donde quepa…
…,Juan no corrió.,NEG,NEG,,'no' advmod del verbo,no hay lista de config donde quepa…
```

**Bug encontrado y corregido al hacer la demo:** (b) fallaba al confirmar. Añadir un lema a
`operadores.modales` no servía de nada porque `_detectar_mod` solo miraba dependientes `aux`,
y Stanza analiza 'suele/quiere/va a + infinitivo' con el **modal como RAÍZ** y el infinitivo
como `xcomp`. La ruta "hueco léxico → config" para MOD era, literalmente, escribir en un sitio
que nadie leía. Se añadió ese patrón a la detección (con test).

**Terminal**: opción `4) Un operador (tiempo, aspecto, negación, modalidad, fuerza ilocutiva)`
con sub-flujo cambiar / quitar / añadir y `Esc` limpio en cada paso.
**GUI**: pestaña «Operadores» en el modal de corrección + endpoint `POST /corregir/operador`
(bajo el mismo `threading.Lock` que las demás correcciones que re-analizan). Lista los
detectados con su señal de origen y los ausentes añadibles; "Quitar" se deshabilita en los
ausentes; los valores se limitan a los que admite la teoría.

**TODO-OPERATORS-3** documentado en el código: un *override por oración* en vivo, que
arreglaría los casos de parse sin tocar ningún léxico, queda pendiente de diseño.

---

## 3. Los 2 fallos preexistentes del bucle — EN VERDE

1. **`test_l5::test_slow_correccion_ditransitiva_end_to_end`** — *diagnóstico*: `_lema_de`
   adivinaba el lema del verbo parseando la EL léxica (primer predicado primado que no fuera
   un primitivo). Con una ditransitiva la EL es solo `do'/have'/CAUSE`: no hay ningún predicado
   léxico, caía al fallback `ls_type` y la guardia lo mandaba a `staging_lema_no_identificable`.
   *Fix*: el mapper ya conoce el lema — ahora lo expone **explícitamente** en `ls["verb_lemma"]`
   (verbal y copulativa) en vez de que la corrección lo deduzca de la representación.
2. **`test_gruxx_server::test_slow_corregir_el_real_con_reanalisis`** — era **el mismo bug
   aguas arriba** (como sospechaba el prompt) más una constante de test desactualizada por mí
   en la etapa anterior (`_CLAVES_SUB` sin `operadores`). Ambas corregidas.
3. **Artefacto de orden de `test_estado_antes_de_cargar`** — `gm._nlp` es estado global; el test
   pasaba aislado y fallaba tras la suite de servidor. Ahora se aísla (guarda/restaura) en vez
   de asumir que nadie cargó el pipeline antes.

---

## 4. Export SVG/PNG — antes y después

**Causa confirmada**: dentro de la GUI el SVG lo estilaba `gui/estilo.css` (externo); el export
salía solo con `class="arbol-nodo"` y cualquier visor aplicaba los defaults del estándar SVG
(`fill:black`, sin `stroke`) → cajas negras, sin líneas, texto invisible. El PNG además pintaba
un fondo **blanco** bajo el texto claro del tema oscuro.

**Fix**: `construirSvgExportable()` vuelca el estilo COMPUTADO como **atributos inline** (lo más
compatible con visores conservadores), añade un rect de fondo opaco y elimina las `class`. El
PNG se rasteriza de ese SVG ya estilado, con el fondo del propio SVG.

Medición sobre el mismo árbol, rasterizado con **inkscape** (motor externo, el escenario del bug):

| | píxeles negros puros | colores distintos |
|---|---|---|
| ANTES | **11.9 %** (las cajas) | 8 |
| DESPUÉS | **0 %** | 359 |

Capturas: `captura_export_antes.png` (cajas negras vacías — el bug de Julian reproducido) y
`captura_export_despues.png` (árbol completo y legible).

Dos detalles que se afinaron al validar: `stroke-width` sale **sin unidad** (`1.4`, no `1.4px`;
los visores estrictos rechazan la forma con unidad) y solo se vuelcan las propiedades que
tienen sentido en cada elemento — el archivo pasó de 19.5 KB a 6.7 KB y desaparecieron los
`fill:black` heredables en los `<g>`.

**Tests** (`test_export_svg.py`, 12): contrato sobre un fixture exportado REAL
(`fixture_export_arbol.svg`) — cero `class`, cada `rect`/`line`/`text` con su estilo embebido,
fondo que cubre el viewBox, medidas sin unidad — **más el rasterizado con inkscape** verificando
que no sale negro; y comprobaciones estáticas del cableado en `app.js` (que ambas exportaciones
pasen por `construirSvgExportable`, que el PNG no vuelva a fijar `#ffffff`, y que los estilos se
inlinen **antes** de quitar las clases, porque las reglas de `estilo.css` son descendentes y ese
orden ya se rompió una vez).

---

## 5. Estado de la batería

- **Suites rápidas: 323 passed, 28 skipped, 0 failed.**
- **`--slow`**: todo verde salvo los **3 conocidos que el prompt excluye explícitamente** —
  `test_causatividad::test_slow_cause_por_clase_y_regresion` (falla en `ls_type`:
  `activity` vs `semelfactive`), `test_fase2_contextual::test_slow_dianas_aa_y_controles`,
  `test_pruebas_aspectuales::test_slow_blend_sube_pun`. Los tres son de **clase aspectual**
  (clasificador), no de EL: la auditoría de §1 registra **0 cambios de clase**, así que esta
  etapa no los toca.
- Byte-idéntico: no aplica a §1 (cambia la EL por diseño aprobado). §2–§4 no alteran ninguna
  salida por caminos no ejercitados; con `operadores.enabled: false` no se añade ninguna clave
  nueva y **los wrappers vuelven a envolver la negación y los epistémicos** — el acoplamiento es
  deliberado: si los operadores están apagados, esa información tiene que vivir en algún sitio.

---

## 6. La EL quedó canónica para LA1

La EL ya no contiene ninguna capa que no sea contenido léxico: los operadores viven en ⟨ ⟩ por
fuera, y los predicados son solo predicados. Esto era precondición de LA1, que leerá
**posiciones** de la EL para asignar macropapeles por la jerarquía Actor-Padecedor — con
`complet(do'(x, …))` el argumento estaba un nivel más adentro de lo que la teoría dice, y la
lectura posicional habría sido incorrecta. Verificado en la tabla de §1: las EL resultantes son
exactamente las plantillas del libro (`do'(x, [pred'(x)])`, `INGR`, `BECOME`, `CAUSE`,
`& INGR consumed'`), con los wrappers léxicos por fuera y los operadores envolviéndolo todo.

Siguiente: `prompt_LA1.md`.

---

## 7. Archivos tocados

**Nuevos**: `test_export_svg.py`, `fixture_export_arbol.svg`, `captura_export_antes.png`,
`captura_export_despues.png`, `CHECKPOINT_OPERATORS_2.md`.
**Modificados**: `operadores.py` (`origen_ids`, `tokens_cubiertos`, NEG solo con negador puro,
MOD raíz+xcomp), `wrappers_ls.py` (`cubiertos_por_operador`), `rrg_ls_mapper.py` (fuera
prog/complet, operadores antes que wrappers, `verb_lemma` explícito), `completeness.py`,
`correccion.py` (flujo 4, `corregir_operador`, `stage_operador`, `anadir_a_mapa_config`,
`_aplicar_en_memoria_config` con mapas), `config.yaml` (`negadores`), `gruxx_server.py`
(`/corregir/operador`), `gui/{index.html,app.js}`, `test_operadores.py` (+21),
`test_gruxx_motor.py`, `test_gruxx_server.py`.
