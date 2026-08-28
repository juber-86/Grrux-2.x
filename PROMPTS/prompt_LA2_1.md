# Tarea LA2.1: contrato de confianza en GUI + linking causal visible + auditoría de logros canónicos

Proyecto **GRRux**. El código conserva temporalmente los nombres históricos `gruxx_*`; no renombrar archivos en esta etapa.

Lee primero `CHECKPOINT_LA2.md` y conserva sus decisiones, pruebas y contratos. Esta etapa corrige tres problemas reportados después de LA2:

1. La GUI aborta con `No se pudo analizar: c.confianza.toFixed is not a function`.
2. Las causativas no muestran el Linking correctamente en GUI para `"Se venden casas"` y `"Juan rompió la ventana"`.
3. Hay evidencia de que logros canónicos, por ejemplo `"El globo explotó"`, pueden clasificarse erróneamente como actividad.

**HACER COMMITS.** Revisar el árbol de trabajo antes de empezar, preservar cambios ajenos y hacer commits pequeños exclusivamente de LA2.1. El checkpoint final debe enumerarlos.

## Límites no negociables

- No tocar `ud2rrg.py`.
- No tocar BERTIN, `predict.py`, `classifier.py`, `decision_tree.py`, `.joblib`, corroborador MLM ni `contextual_sentences.csv`.
- No regenerar ni alterar golds, PUD o datos curados sin aprobación explícita.
- No reabrir LA2 salvo que una regresión demostrable exija un ajuste mínimo de integración.
- No cambiar la teoría de Wh+preposición/PrCS: sigue suspendida.
- No cambiar umbrales del clasificador para “forzar” logros. Si el diagnóstico demuestra que el origen está dentro del clasificador y exige reentrenamiento, detener esa subparte, documentarla y no alterar el modelo.
- Una sola instancia de GRRux/GUI a la vez. No correr pruebas lentas con GUI o servidor cargados.

---

## §1. Reparar el contrato de `confianza` sin ocultar resultados

### Problema

La GUI ejecuta `c.confianza.toFixed(...)`, pero al menos una respuesta recibe `confianza` con un tipo no numérico. Esto aborta el renderizado completo y puede ocultar bloques válidos, incluido Linking.

### Contrato nuevo

En el límite motor/API, cada valor de confianza expuesto a la GUI debe ser uno de:

- número finito entre `0` y `1`;
- `null` cuando no existe una confianza aplicable.

Nunca debe enviarse una cadena, diccionario, lista, `NaN` ni infinito como `confianza`.

La GUI debe ser defensiva incluso ante fixtures o respuestas antiguas:

- mostrar un número válido con formato fijo;
- aceptar una cadena numérica heredada convirtiéndola de forma segura;
- mostrar `—` para `null`, ausente o inválido;
- jamás llamar `toFixed()` sobre un valor no validado;
- jamás abortar el análisis completo por un dato de confianza inválido.

La normalización de datos pertenece al motor/serializador; la guardia visual pertenece a la GUI. No resolverlo únicamente con una conversión ciega en JavaScript.

### Pruebas obligatorias

Probar en el contrato de motor/servidor y en el renderizado GUI:

- `0.55` → formato numérico correcto;
- `"0.55"` heredado → se muestra correctamente sin excepción;
- `null` o campo ausente → `—`;
- valor inválido → `—`, sin error global;
- análisis completo con una confianza válida → árbol, EL, Integridad y Linking siguen visibles.

No silenciar excepciones globalmente: el error debe corregirse en el contrato concreto.

---

## §2. Causativas: verificar semántica, serialización y Linking de punta a punta

LA2 ya corrigió la EL de causativas resultativas. LA2.1 debe comprobar que esa información llega completa a terminal, motor, API y GUI, sin que el fallo de `confianza` la oculte.

### Diana A: `Se venden casas`

Resultado esperado:

```text
Tipo visible: Realización causativa
EL léxica: [do'(Ø, Ø)] CAUSE [BECOME vendido'(casas)]
```

Propiedades obligatorias:

- `vendido'` en español; nunca `sold'`;
- `casas` ocupa el argumento de estado, no el primer argumento de un `do'` embebido;
- Actor inespecífico `Ø`, nunca `casas`;
- Undergoer/Padecedor = `casas`;
- PSA = Undergoer;
- concordancia `casas 3pl ↔ venden 3pl` correcta;
- Linking, traza e Integridad llegan a la GUI y se renderizan.

### Diana B: `Juan rompió la ventana`

Resultado esperado:

```text
Tipo visible: Logro causativo
EL léxica: [do'(Juan, Ø)] CAUSE [INGR roto'(ventana)]
```

Propiedades obligatorias:

- `roto'` en español;
- Actor/PSA = `Juan`;
- Undergoer = `ventana`;
- transición `INGR`;
- Linking completo y visible en terminal y GUI;
- no confundir esta causativa léxica con una actividad simple ni perder la información causal al serializar.

No modificar reglas causativas que ya pasen estos contratos. Si el cálculo de Linking existe en `ls_data` pero no llega al JSON o a la GUI, corregir exclusivamente esa integración.

### Pruebas obligatorias

Para ambas dianas, verificar de extremo a extremo:

1. salida semántica estructurada;
2. serialización del motor;
3. respuesta API;
4. renderizado GUI sin error;
5. bloque Linking visible;
6. salida terminal coherente;
7. Integridad y concordancia coherentes.

Añadir una prueba de regresión que reproduzca exactamente el fallo anterior de `confianza` junto con una causativa: aunque una confianza sea inválida, el análisis y Linking deben seguir siendo visibles.

---

## §3. Auditoría y corrección localizada de logros canónicos

### Caso detonante

```text
El globo explotó.
```

Debe clasificarse como **Logro / Achievement**, no como Actividad, y no debe recibir `CAUSE` si la oración no expresa causación externa.

### Objetivo

Determinar de forma trazable por qué GRRux produce Actividad en los casos corregidos por el usuario y arreglar solo una causa demostrada que esté fuera del clasificador protegido.

Para cada oración auditada, registrar:

- parse UD relevante;
- complejo verbal detectado;
- vector `stat/dyn/tel/pun`;
- clase léxica;
- coerciones/gates aplicados y su justificación;
- clase final;
- EL resultante;
- existencia o ausencia de `CAUSE`;
- origen de la corrección manual, si existe.

Primero tomar `"El globo explotó"` y las correcciones de logros ya presentes en los CSV de corrección. Añadir una batería pequeña de logros canónicos solo cuando su análisis teórico sea inequívoco y quede documentado en el test.

### Regla de intervención

- Si el problema está en una coerción, gate, lectura morfológica o integración posterior al clasificador, implementar la corrección más localizada posible y cubrirla con tests.
- Si el problema exige cambiar pesos, umbrales internos del clasificador, BERTIN, `.joblib` o reentrenamiento, **no hacerlo**. Generar el informe diagnóstico y dejar una recomendación explícita para una futura fase de reentrenamiento.
- Las correcciones manuales no se convierten automáticamente en datos de entrenamiento ni modifican `contextual_sentences.csv`.

### Criterios de aceptación

- `"El globo explotó"` → Logro, sin `CAUSE`.
- El resultado debe conservarse con tests fríos y, si procede, un test end-to-end.
- Ninguna actividad, realización, realización activa o causativa previamente correcta cambia sin una justificación documentada.
- Los tres fallos lentos preexistentes siguen siendo solo referencia; no autorizan tocar el clasificador:
  - `"el perro se sacudió"`;
  - `"Juan llegó"`;
  - `blend_sube_pun`.

---

## §4. Validación final

Ejecutar pruebas frías completas y las pruebas lentas necesarias, respetando la advertencia OOM.

Deben quedar cubiertos:

1. normalización y renderizado seguro de `confianza`;
2. dos causativas con Linking visible de punta a punta;
3. `Se venden casas` como realización causativa;
4. `Juan rompió la ventana` como logro causativo;
5. `El globo explotó` como logro no causativo;
6. auditoría legible de los casos de logro corregidos manualmente;
7. invariantes: archivos prohibidos intactos, PUD sin ejecutar y datos curados sin alteración.

## CHECKPOINT — PARAR aquí

Crear `CHECKPOINT_LA2_1.md` y detenerse. Debe incluir:

1. diagnóstico exacto de `c.confianza.toFixed is not a function` y la garantía nueva de contrato;
2. evidencia de GUI para las dos causativas, con Linking visible;
3. antes/después de `"El globo explotó"` y tabla de auditoría de los logros revisados;
4. decisión explícita: corrección localizada aplicada o necesidad de fase de reentrenamiento;
5. resultados de pruebas, regresiones conocidas, archivos modificados y commits de LA2.1.

No continuar hacia reentrenamiento ni hacia otra fase sin aprobación explícita.
