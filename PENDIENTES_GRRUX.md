# Pendientes de GRRux

Estado de referencia: LA2.1 implementado. Este documento reúne el trabajo pendiente conocido antes de iniciar LA3 y conserva explícitamente las ideas aplazadas.

## Prioridad inmediata: LA3

### 1. Linking sintaxis → semántica (syn→sem)

Implementar el algoritmo de comprensión para transformar la representación sintáctica de una oración en una representación semántica RRG/LS.

Alcance mínimo:

- Identificar argumentos centrales, macrorroles y argumento sintáctico privilegiado.
- Recuperar o construir la LS del predicado del núcleo.
- Resolver el enlace de actor, undergoer y argumentos no macrorrol.
- Incorporar marcación de caso, orden, voz, `se`, preposiciones y posiciones pre-/postcore cuando sean relevantes para el español.
- Comprobar la completitud: todo argumento explícito debe enlazar con una posición de la LS y toda posición exigida por la LS debe tener realización sintáctica, salvo argumentos implícitos permitidos.
- Emitir diagnóstico explicable cuando el enlace sea ambiguo o incompleto.

### 2. Linking semántica → sintaxis (sem→syn)

Implementar el algoritmo de producción desde la LS hacia la estructura estratificada de la cláusula.

Alcance mínimo:

- Determinar actor y undergoer mediante la Actor–Undergoer Hierarchy.
- Seleccionar el argumento sintáctico privilegiado.
- Determinar codificación morfosintáctica: caso/adposición, concordancia y voz.
- Seleccionar una plantilla sintáctica compatible con el español.
- Asignar argumentos a posiciones de la cláusula, incluyendo núcleo, periferia y posiciones pre-/postcore cuando corresponda.
- Validar la salida con la completitud y reportar conflictos en lugar de ocultarlos.

### 3. Integración bidireccional

- Definir representaciones intermedias comunes para que syn→sem y sem→syn utilicen la misma LS y la misma estructura estratificada.
- Ejecutar comprobaciones de consistencia en ambos sentidos.
- Mostrar en la GUI qué regla produjo cada enlace y dónde existe incertidumbre.
- Evitar que la nueva capa reemplace silenciosamente el análisis vigente: debe conservar trazabilidad y permitir comparación.

## Robustez del análisis

### 4. Logros y realizaciones

- Ampliar las pruebas de `LOGRO`, especialmente con predicados de cambio puntual como «El globo explotó».
- Verificar la frontera entre actividad, realización y logro en verbos nuevos y en construcciones causativas.
- Añadir pares mínimos y contraejemplos al conjunto curado.
- Medir falsos positivos de actividad y falsos negativos de logro antes y después de LA3.

### 5. Causatividad y linking

- Verificar de extremo a extremo el linking de causativas como «Se venden casas» y «Juan rompió la ventana».
- Cubrir causativas léxicas, anticausativas/reflexivas con `se` y alternancias de valencia.
- Comprobar que la LS, los macrorroles y la realización sintáctica respeten la completitud.

### 6. Confianza y presentación

- Mantener el manejo robusto de valores de confianza numéricos y evitar errores de interfaz como `c.confianza.toFixed is not a function`.
- Definir una convención única para confianza, desacuerdo interno y evidencia de reglas.
- Mostrar incertidumbre de forma comprensible en la GUI, sin romper el renderizado cuando falte o cambie un valor.

## Pruebas y validación

- Crear una matriz de regresión para actividades, realizaciones, logros, estados y causativas.
- Probar oraciones con argumentos explícitos, implícitos, oblicuos, dativos, locativos y preposicionales.
- Validar voz activa, pasiva y construcciones con `se` relevantes para el español.
- Verificar que las opciones de corrección/enrutado se limiten a los nodos de la oración actual y no contaminen análisis anteriores.
- Añadir pruebas de ida y vuelta: syn→sem→syn y sem→syn→sem, con tolerancia explícita para alternancias legítimas.
- Registrar resultados, errores y ejemplos de decisión para cada fase.

## Deuda técnica e infraestructura

- Mantener separados los archivos activos del sedimento legacy y evitar nuevas dependencias sobre módulos muertos.
- Corregir progresivamente la nomenclatura `gruxx` → `GRRux`; el cambio de `gruxx_ai1.py` a `grrux_ai1.py` queda para una migración controlada.
- Definir una estrategia de pruebas de la GUI que no requiera mantener instancias adicionales de GRRux abiertas y reduzca el consumo de RAM.
- Documentar el acceso al servidor local de la GUI (`http://127.0.0.1:8763/`) para el modelo ejecutor y las pruebas aisladas.
- Mantener commits por fase y actualizar el checkpoint correspondiente al cerrar cada bloque.

## Aplazado deliberadamente

### ADESSE

No implementar todavía la consulta automática a ADESSE. Conservarla como posible respaldo léxico futuro para análisis de baja confianza o desacuerdo interno, siempre como corroboración explicable y nunca como sustitución silenciosa del análisis RRG.

### Inglés y otras extensiones

- La migración de predicados de la EL al inglés queda para una fase posterior; por ahora se mantienen los predicados en español.
- Wh + preposición continúa suspendido.
- No reactivar módulos legacy ni ampliar el alcance teórico hasta estabilizar LA3 y su batería de regresión.

## Criterio de cierre previo a la siguiente fase

LA3 podrá considerarse estable cuando los dos algoritmos de linking compartan representaciones, pasen las pruebas de completitud y causatividad, mantengan trazabilidad en la GUI y no introduzcan regresiones en la clasificación de logros, realizaciones y actividades.
