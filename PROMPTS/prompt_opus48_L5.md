# Tarea: L5 — bucle de corrección del usuario + conciliación AGX + salida GRR legible + glosario

Proyecto grrux (repo `~/proyectos/ud2rrg`). Python: `./venv/bin/python` (3.10). Entry point:
`python3 gruxx_ai1.py`. Sigue al reentrenamiento habitual (CHECKPOINT_REENTRENAMIENTO_HABITUAL.md
— Julian ACEPTÓ el estado del árbol de trabajo: reentrenado + recalibrado w=0.55/dyn=0.45/
pun=0.40/tel=0.40 + corroborador apagado; NO revertir nada). NO hacer commits. ADVERTENCIA OOM:
no correr suites --slow con instancias interactivas de gruxx abiertas (12 GB).

**PROHIBIDO:** clasificador (`predict.py`, `classifier.py`, `decision_tree.py`, cabezas
`.joblib` — NO reentrenar nada aquí), corroborador MLM, `contextual_sentences.csv` (solo
lectura). `gruxx_ai1.py` libremente editable (condición: los 3 modos corren y generan EL +
árboles). `ud2rrg.py` tocable SOLO en §1 (régimen de siempre: gated `language=='es'`/MISC).
PUD intocado.

## §0. Estabilización post-reentrenamiento (veredictos de Julian, hacer PRIMERO)

1. **Gate nuevo G-AA-medida** (en el mapper, junto a los gates de L4.5): clase `activity` +
   sujeto agentivo + obj con **nummod/numeral de medida** ("cinco kilómetros", "tres manzanas",
   "dos piscinas") + clase LÉXICA del lema durativa → `active_accomplishment` con su plantilla.
   Nota `gate=obj_medida→AA`. Guarda del numeral: "empuja el carro" (sin nummod) NO dispara.
   Restaura la diana "Juan corrió cinco kilómetros"→AA (regresión del reentrenamiento: su tel
   cayó a 0.34, irreparable por umbral — este gate la protege estructuralmente).
2. **Verificar el no-disparo de G-atélico en "corrió vigorosamente"** (deriva
   activity→semelfactive del checkpoint): sin obj + `correr` durativo léxico → G-atélico DEBIÓ
   rescatarla. Diagnosticar si es bug del gate (arreglarlo) o si el informe reportaba clase
   cruda (documentarlo). Resultado final exigido: `activity`.
3. **Ídem "llueve"** (deriva activity→AA): es impersonal SIN delimitador nuclear — el gate
   AA-sin-delimitador debió degradarla. Diagnosticar y dejar en `activity`.
4. **"el pastel fue comido por Juan" → `active_accomplishment` es el GOLD** (veredicto
   lingüístico de Julian: la pasiva del AA agentivo es el mismo evento). Añadir assert de clase
   donde corresponda (hoy no tenía).
5. **Relajar la aserción desactualizada** de
   `test_telicidad_l4_5.test_slow_cinco_dianas_telicidad_composicional`: exigir la CLASE
   correcta, con nota de gate OPCIONAL (el clasificador ya acierta solo en 3/5 — el test fallaba
   por el propio éxito del reentrenamiento).

## §1. Conciliación AGX (hallazgo dominante de L4.5: 11/15 advertencias restantes)

El árbol a veces tiene MÁS nodos AGX que la LS: `ud2rrg.py` conserva un fallback propio de
clíticos que dispara sin MISC donde `nucleo_periferia._detectar_agx` no registra nada.
Principio híbrido: UNA sola fuente de verdad.

- **Completar `_detectar_agx`**: registrar también los átonos `me/te/nos/os` (dativos y
  acusativos/reflexivos no aspectuales) y las posiciones de `le/les` hoy no cubiertas.
  Fuentes nuevas en la lista agx: `'dativo'`, `'acusativo'`, `'reflexivo'` (además de las
  existentes se_pasivo/se_impersonal/se_aspectual). Los rasgos (persona/número/caso) salen de
  los feats como siempre.
- **Subordinar el fallback de ud2rrg al MISC** (gated es): si el token trae MISC con marcas RRG
  y NO trae `RRGRole=AGX` → ud2rrg NO crea AGX por su cuenta. Sin MISC en absoluto (conllu
  crudo de terceros) → el fallback actual se conserva.
- Aceptación: re-correr KPI4 (AnCora dev, mismas n=300) → el patrón `agx_arbol_gt_ls` debe
  prácticamente desaparecer del desglose; tasa de completeness sube desde 80.3% (reportar
  cifra); conversión se mantiene 98%.

## §2. Reorden de la salida (convención GRR, orden de Julian)

En `mostrar_resultado` (y el `.txt` guardado, y el modo `.conllu`): por cada (sub)oración,
PRIMERO el **árbol sintáctico**, INMEDIATAMENTE DEBAJO la **EL léxica** (las dos
representaciones juntas, comparables de un vistazo — así se presentan en los textos de GRR), y
debajo el resto: Tipo, EL formal, Argumentos, Rasgos (Vector), Integridad (Completeness),
CAUSE/fuente. Mismo contenido, nuevo orden.

## §3. Traducción user-friendly de Vector y Completeness

Usuario objetivo: lingüista competente en GRR que NO debe aprender los tecnicismos internos de
gruxx. Traducir las etiquetas EN la salida (la información se conserva, el delivery cambia):

- Línea Vector → `Rasgos: estático 0.02 · dinámico 0.75 · télico 0.40 · puntual 0.05 ·
  confianza 0.84`. Los apéndices técnicos se traducen:
  `gate=obj_desnudo→Activity` → `corrección: objeto sin determinante → Actividad`;
  `gate=se_aspectual→AA` → `corrección: "se" completivo → Realización activa`;
  `coercion=P4...` → `coerción: "durante X" fuerza lectura iterativa`;
  `ditrans=transferencia(léxico)` → `construcción: transferencia (léxico)`;
  wrappers ya son legibles (dejar). El detalle crudo actual completo queda disponible con
  `--verbose` (flag que ya existe en gruxx).
- Línea Completeness → `Integridad: ✓ x1 en la terminación verbal · x2 ↔ sintagma nominal ·
  x3 ↔ frase con "a" · concordancia (AGX) ✓` /
  `Integridad: ⚠ x2 ("participar") no aparece como constituyente en el árbol`.
  Estados: `falta_en_arbol` → "no aparece como constituyente en el árbol"; `falta_en_ls` → "el
  árbol tiene X que la EL no anticipa"; `no_verificable` → "no verificable (informativo)".
- Los TÉRMINOS traducidos y sus definiciones salen del glosario del §4 (una sola fuente).

## §4. Comando `-help` / `--help` / `-ayuda` / `--ayuda` (con argumento opcional)

- En el modo interactivo (y aceptado también como línea en el batch), el usuario escribe:
  - `-help` (cualquiera de las 4 formas, sin argumento) → gruxx imprime el GLOSARIO COMPLETO,
    estilo salida de ayuda de un programa de Linux, agrupado por categorías, paginado simple si
    excede la pantalla (imprimir por bloques).
  - `-help <término>` → imprime SOLO la(s) definición(es) de ese término. La búsqueda es
    tolerante: sin distinguir mayúsculas/acentos y por coincidencia parcial (`-help agx` →
    AGX; `-help telico` → télico (tel); `-help peri` → todas las entradas que contengan
    "peri"). Si no hay coincidencia: `término no encontrado — escribe "-help" para ver el
    glosario completo`.
- gruxx debe ANUNCIAR el comando donde el usuario lo vea (al arrancar el modo interactivo y en
  el pie de cada análisis o del menú): `escribe "-help" para mostrar el glosario completo o
  "-help término" para buscar un término específico`.
- El glosario vive en `aspect_classifier/data/glosario_gruxx.csv` (columnas:
  `categoria,termino,definicion`) — Julian lo edita; SEMBRARLO con el contenido de abajo
  (redactado por la sesión de diseño, tal cual, correcciones menores de formato permitidas):

```
categoria,termino,definicion
Clases aspectuales,State (Estado),"Situación estática sin dinámica interna: saber, amar, estar roto. No progresivo."
Clases aspectuales,Activity (Actividad),"Proceso dinámico sin final inherente: correr, estudiar, comer manzanas."
Clases aspectuales,Accomplishment (Realización),"Cambio de estado gradual con final: la ropa se secó, la herida cicatrizó."
Clases aspectuales,Achievement (Logro),"Cambio de estado instantáneo: romperse, llegar, morir."
Clases aspectuales,Semelfactive (Semelfactivo),"Evento puntual sin estado resultante: toser, parpadear, golpear."
Clases aspectuales,Active Accomplishment (Realización activa),"Actividad con culminación por objeto o meta delimitada: comerse la manzana, correr cinco kilómetros."
Rasgos,estático (stat),"0-1: cuánto se parece a un estado (sin dinámica interna)."
Rasgos,dinámico (dyn),"0-1: cuánta actividad/energía tiene la situación."
Rasgos,télico (tel),"0-1: si la situación tiene un punto final natural (culminación)."
Rasgos,puntual (pun),"0-1: si ocurre en un instante (sin duración interna)."
Rasgos,confianza,"Qué tan segura está la clasificación (0-1). Bajo 0.6: revisar."
Estructura Lógica,EL / LS,"Estructura Lógica: la representación semántica formal de la oración en RRG."
Estructura Lógica,EL formal,"Versión con variables (x1 x2): la plantilla abstracta."
Estructura Lógica,EL léxica,"Versión con las palabras reales de la oración."
Estructura Lógica,do',"Marca de actividad con efector: do'(x [correr'(x)])."
Estructura Lógica,CAUSE,"Une la causa con el efecto: [do'(x Ø)] CAUSE [BECOME roto'(y)]."
Estructura Lógica,BECOME,"Cambio de estado gradual (realizaciones)."
Estructura Lógica,INGR,"Cambio de estado instantáneo (logros)."
Estructura Lógica,SEML,"Evento semelfactivo (puntual sin resultado)."
Estructura Lógica,PURP,"Propósito: en benefactivas ('le compró X a Y' = obtiene X CON PROPÓSITO de que Y lo tenga)."
Estructura Lógica,Ø,"Argumento inespecificado: nadie en particular ('Se venden casas' → do'(Ø Ø))."
Estructura Lógica,have',"Posesión: have'(María regalo) = María tiene el regalo."
Participantes,Actor,"Macropapel del participante que ejecuta/origina (el 'sujeto lógico')."
Participantes,Undergoer (Padecedor),"Macropapel del participante afectado por la situación."
Participantes,NMR,"Argumento central sin macropapel: el dativo español ('a María' en 'le dio flores a María')."
Participantes,PSA,"Argumento Sintáctico Privilegiado: el que la sintaxis trata como sujeto (concordancia)."
Participantes,Efectuador,"El que hace la acción (primer argumento de do')."
Participantes,Tema,"Lo transferido/movido/poseído SIN cambio interno (segundo argumento de have' etc.)."
Participantes,Paciente,"El que sufre el cambio de estado (argumento único de pred'(x))."
Participantes,Poseedor,"El que pasa a tener algo (primer argumento de have') — el receptor de una transferencia."
Participantes,x1 x2 x3,"Las variables de los argumentos en la EL formal, por orden jerárquico."
Participantes,x(morf) / '3sg',"Argumento realizado solo en la morfología: sujeto pro-drop o clítico sin sintagma pleno."
Árbol sintáctico,SENTENCE/CLAUSE/CORE/NUC,"Los estratos de la cláusula RRG: oración > cláusula > centro > núcleo."
Árbol sintáctico,-PERI,"Marca de periferia: adjunto que modifica al estrato del que cuelga (temporal→CLAUSE local/modo→CORE)."
Árbol sintáctico,AGX,"Índice de concordancia bajo el núcleo: ahí se enlazan los clíticos (le/les/se) y la concordancia verbal."
Árbol sintáctico,PrDP / LDP,"Posición dislocada izquierda: elemento inicial destacado ('Ayer, ...')."
Árbol sintáctico,PrCS,"Posición precentral: pronombres interrogativos (qué quién cómo)."
Árbol sintáctico,PP / NP / ADVP,"Frase preposicional / nominal / adverbial."
Análisis,wrapper,"Predicado que envuelve la EL para un adjunto: be-in'(parque [EL]) for'(tres horas [EL]) yesterday'([EL])."
Análisis,gate / corrección,"Regla estructural que corrige la clase del clasificador con evidencia sintáctica (p.ej. objeto sin determinante → Actividad)."
Análisis,coerción,"Cambio de lectura aspectual forzado por el contexto ('tosió durante una hora' → actividad iterada)."
Análisis,Integridad (Completeness),"Chequeo de que todo argumento de la EL aparece en el árbol y viceversa (Restricción de Integridad de la RRG)."
Análisis,método léxico/contextual,"De dónde salió la clasificación: solo el verbo (léxico) o el verbo en su oración (contextual)."
Análisis,complejo verbal,"El verbo + sus clíticos + el núcleo del objeto: la unidad que lee el clasificador."
Análisis,transferencia/benefactiva/comunicación,"Las tres plantillas ditransitivas: dar (X pasa a Y) / comprar-hacer (obtiene X para Y) / decir (expresa X a Y)."
Notación de gruxx,x1(morf),"El argumento x1 está realizado solo en la morfología del verbo (no hay sintagma): sujeto pro-drop o clítico solo."
Notación de gruxx,pro-drop,"Sujeto omitido recuperado de la terminación verbal: 'estudié' → x1 = 1sg."
Notación de gruxx,1sg / 3sg / 3pl,"Etiquetas de persona y número: 1ª singular, 3ª singular, 3ª plural (de los rasgos morfológicos)."
Notación de gruxx,"x1:Juan,nsubj,Actor","Formato de los argumentos: variable : palabra , función sintáctica UD , papel semántico."
Notación de gruxx,nsubj / obj / obl:arg,"Funciones sintácticas UD: sujeto / objeto directo / argumento oblicuo (el dativo español)."
Notación de gruxx,PERI@CORE / PERI@CLAUSE,"Dónde ancla la periferia en el árbol: al centro (locativos y modo) o a la cláusula (temporales)."
Notación de gruxx,↔,"En la línea de Integridad: correspondencia verificada entre un elemento de la EL y un constituyente del árbol."
Notación de gruxx,conf,"Abreviatura de confianza de la clasificación (0-1)."
Notación de gruxx,metodo lexical/contextual,"Cómo se clasificó: 'lexical' = solo el verbo; 'contextual' = el verbo dentro de su oración (embeddings del complejo verbal)."
Notación de gruxx,complejo={...},"Los tokens que forman el complejo verbal leído por el clasificador (verbo + clíticos + núcleo del objeto), con su posición."
Notación de gruxx,gate=...,"Corrección estructural aplicada tras el clasificador; el texto indica la regla y la clase resultante (ver 'gate / corrección')."
Notación de gruxx,coercion=...,"Cambio de lectura aspectual forzado por el contexto detectado (ver 'coerción')."
Notación de gruxx,ditrans=...,"Plantilla ditransitiva aplicada y su fuente (léxico curado o default)."
Notación de gruxx,P1…P5 (pruebas),"Las pruebas de clase aspectual de Van Valin detectadas en la oración: P1 progresivo, P2 adverbio dinámico, P3 adverbio de ritmo, P4 expresión durativa ('durante X'), P5 expresión de término ('en X tiempo')."
Notación de gruxx,CAUSE[...],"Causatividad detectada: tipo (léxico/heurístico) y confianza."
Notación de gruxx,fuente=correccion_usuario,"Marca de una entrada añadida a un léxico por el bucle de corrección (auditable y reversible)."
Notación de gruxx,revisar=True,"Fila de un archivo curado marcada como dudosa: se excluye del entrenamiento hasta que Julian la revise."
```

## §5. Bucle de corrección del usuario (la feature estrella — diseño CERRADO con Julian)

### Activación
En el prompt existente de guardado: `¿Guardar en .txt? (s/n) — o (c) para corregir el análisis`
(tecla `c`; `Esc` o vacío cancela la corrección en cualquier punto). Además, cuando la línea de
Integridad trae ⚠, mostrar la pista `¿Análisis incorrecto? Pulsa (c) para corregirlo`. En batch:
ofrecer la corrección al final, por oración seleccionada por número. Nunca interrumpe solo.

### Menú (qué está mal)
```
1) La clase aspectual (State/Activity/…)
2) La Estructura Lógica completa
3) El enrutado de un elemento (periferia↔argumento, tipo, posición, clítico/AGX)
Esc) Cancelar
```

### Flujos por opción
- **(1) Clase**: elegir de la lista de 6 clases (+ "causativa de X" si aplica). →
  **STAGING** (`data/correcciones_clase.csv`: fecha, oración, lema, clase_predicha,
  clase_correcta, vector, fuente=correccion_usuario). NO toca el clasificador ni sus datos:
  Julian promueve a mano a `contextual_sentences.csv` (protege el terreno del clasificador —
  decisión híbrida). ADEMÁS: si la clase corregida implica una plantilla ditransitiva o
  causativa que el léxico no tiene, ofrecer registrar el lema (flujo de la opción 2).
- **(2) EL completa**: el usuario escribe la EL correcta con los formalismos. VALIDACIÓN EN 3
  NIVELES, cada rechazo con explicación específica:
  1. *Sintaxis del formalismo*: mini-parser de EL (primitivos conocidos: do', CAUSE, BECOME,
     INGR, SEML, PURP, have', pred' léxicos con ', argumentos entre paréntesis, corchetes
     balanceados, wrappers conocidos). Error → señalar QUÉ no parsea y dónde.
  2. *Consistencia con la oración*: los argumentos deben ser tokens/lemas de la oración (o Ø, o
     etiquetas morfológicas '3sg'); el predicado principal debe corresponder al lema del verbo.
  3. *Plantilla reconocible*: la EL parseada debe corresponder a una plantilla que gruxx conoce
     (las 6 clases + causativa + las 3 ditransitivas + wrappers por fuera). Si no → rechazo
     listando las plantillas aceptadas.
  Aceptada → gruxx DERIVA automáticamente qué curar (el usuario NUNCA elige archivo —
  decisión de Julian): plantilla ditransitiva nueva/corregida para el lema →
  `verbos_ditransitivos.xlsx` DIRECTO con `fuente=correccion_usuario`; causatividad →
  `causative_lexicon.csv` DIRECTO con la misma marca; clase aspectual implícita distinta →
  staging de la opción 1. Registrar TODO también en un log maestro
  (`data/correcciones_log.csv`) para auditoría.
- **(3) Enrutado**: sub-menú guiado — elegir el elemento (listado numerado de los
  constituyentes/periferia del análisis) y qué debería ser: argumento del core / periferia
  (temporal|locativo|modo) / posición destacada (LDP) / clítico de concordancia (AGX). Dónde
  persiste (automático): si el caso corresponde a una lista de config existente
  (`verbos_movimiento`, `sustantivos_duracion`, `adv_dinamicos`, `adv_ritmo`, léxico que
  aplique) → añadir DIRECTO con comentario `# correccion_usuario`; si no hay lista donde quepa →
  staging `data/correcciones_enrutado.csv` + mensaje honesto ("registrado para revisión; esta
  corrección aún no puede automatizarse"). Las correcciones de enrutado SÍ cambian el árbol en
  el re-análisis (vía Etapa 1 → MISC) — es la forma indirecta y teóricamente correcta de
  "corregir el árbol".

### Cierre del ciclo (re-análisis de confirmación)
Tras aceptar una corrección persistible: aplicarla, RE-ANALIZAR la oración en el momento y
mostrar el resultado nuevo (árbol + EL, ya con el orden del §2). Si coincide con lo que el
usuario indicó → `✓ Corrección aplicada y verificada` y se persiste (si aún no). Si NO coincide
→ mensaje honesto (`la corrección se registró pero el análisis aún no la refleja — quedará para
revisión`) y la corrección va a staging en vez de al archivo vivo (NUNCA persistir en vivo algo
que el re-análisis no confirma). El usuario nunca debe creer que corrigió algo que no cambió.

### Anti-contaminación (resumen de reglas duras)
- Nada entra a un archivo vivo sin pasar la validación completa Y el re-análisis confirmatorio.
- `contextual_sentences.csv` JAMÁS se toca automáticamente (solo staging).
- Todo lo persistido lleva `fuente=correccion_usuario` (auditable/reversible) + fila en el log
  maestro.
- Esc cancela limpio en cualquier punto, sin efectos.

## Tests + validación

- §0: dianas — "Juan corrió cinco kilómetros"→AA (gate obj_medida), "empuja el carro" NO
  dispara, "corrió vigorosamente"→activity, "llueve"→activity, "el pastel fue comido por
  Juan"→AA (nuevo assert), test L4.5 relajado, batería completa + suites verdes (los 2
  preexistentes conocidos: sacudió y blend_sube_pun quedan documentados).
- §1: KPI4 re-corrido n=300 → `agx_arbol_gt_ls` ≈ 0, completeness > 80.3%, conversión 98%;
  fixture con me/te ("Me dio el libro" → agx dativo 1sg, un solo x3 morfológico).
- §2-§4: los 3 modos muestran el orden nuevo; `--verbose` conserva el detalle crudo; `-help`
  imprime el glosario completo desde el CSV; `-help agx`/`-help telico`/`-help peri` devuelven
  las entradas correctas (parcial, sin acentos/mayúsculas); término inexistente → mensaje con
  redirección al glosario; el anuncio del comando aparece al arrancar y tras cada análisis; el
  `.txt` guardado respeta el orden nuevo.
- §5 (unit + @slow interactivo simulado con monkeypatch de input): EL válida de cada plantilla
  aceptada y enrutada al archivo correcto; EL con paréntesis rotos / argumento ajeno a la
  oración / plantilla desconocida → 3 rechazos con su explicación; corrección de clase →
  staging (contextual_sentences intacto — assert por mtime); enrutado a lista de config;
  re-análisis confirmatorio en éxito Y en no-confirmación (→staging); Esc en cada punto del
  flujo sin efectos; log maestro completo.

## CHECKPOINT final — PARAR aquí

Informe: (1) §0 dianas restauradas con evidencia + diagnóstico de vigorosamente/llueve;
(2) KPI4 nuevo (completeness post-conciliación, desglose restante); (3) captura de la salida
reordenada y traducida de 2-3 oraciones (una con ⚠ traducida); (4) `-help` completo tal como se
imprime; (5) demo del bucle: una corrección de cada tipo aceptada (con su re-análisis) y una
rechazada por cada nivel de validación, mostrando adónde fue cada cosa; (6) pendientes que
siguen fuera: homógrafos, compuestas/xcomp, operadores (pragmático), impersonal refleja,
agente-por, wrapper de frecuencia, lote de contrapeso de medidas (opcional, si Julian quiere
reforzar tel por datos además del gate).
