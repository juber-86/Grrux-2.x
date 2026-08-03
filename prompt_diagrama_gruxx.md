# Tarea: diagrama completo del funcionamiento de gruxx (para presentación)

Proyecto grrux (repo `~/proyectos/ud2rrg`). Tarea de DOCUMENTACIÓN VISUAL — no se toca ningún
código de producción, no se hacen commits. Entregable en una carpeta nueva `docs/`.

## Objetivo

Un diagrama que explique CÓMO FUNCIONA TODO EL PROYECTO a alguien que no lo conoce (uso:
presentación). Debe cubrir el flujo completo con flechas y anotaciones: desde que gruxx
arranca, pasando por el análisis de una oración, hasta el resultado desplegado — incluyendo la
interacción posterior (`-help` y el bucle de correcciones). Además, un apartado de **faltantes
y mejoras futuras**, visualmente SEPARADO del flujo real (panel aparte, borde punteado,
atenuado, rotulado "FUTURO — no implementado"): lo pendiente NO debe mezclarse con el diagrama
del sistema que existe hoy.

## Entregables

1. `docs/diagrama_gruxx.svg` — el diagrama principal, formato apaisado apto para proyectar
   (proporción ~16:9 o hasta 16:10; si el contenido lo exige, alto adicional antes que letra
   ilegible). Texto mínimo legible ~14px al tamaño natural.
2. `docs/diagrama_gruxx.html` — wrapper mínimo que muestra el SVG a pantalla completa (para
   abrirlo en el navegador durante la presentación).
3. VERIFICAR el flujo contra el código real antes de dibujar (los módulos y el orden de abajo
   son la referencia de la sesión de diseño; si el código difiere en algún detalle, manda el
   código y anótalo).

## Estilo

- Todo en ESPAÑOL, con la terminología user-friendly del glosario
  (`aspect_classifier/data/glosario_gruxx.csv`) — el público es un lingüista GRR, no un
  programador: "clasificador aspectual", "árbol sintáctico", "Estructura Lógica", no nombres de
  archivos (los nombres de módulo pueden ir como subtítulo pequeño en gris).
- Color por capa + leyenda: ① entrada/arranque, ② análisis semántico, ③ análisis sintáctico,
  ④ verificación, ⑤ interacción con el usuario, ⑥ datos/léxicos curados (cilindros o cajas con
  otra forma). El panel FUTURO en gris punteado.
- Flechas con sentido único del flujo; las flechas de "aprendizaje" (correcciones → léxicos →
  próximos análisis) marcadas distinto (punteadas o de color) porque cierran el ciclo.
- Sin solapamientos; revisar el render final (abrirlo) antes de dar por terminado.

## Contenido obligatorio del flujo REAL (referencia verificada por la sesión de diseño)

### ① Arranque
Carga de modelos (parser Stanza para español; clasificador aspectual roBERTa/BERTIN con dos
cabezas: léxica y contextual) + léxicos curados (semilla de verbos, oraciones contextuales,
ditransitivos, causativos, glosario, listas de config). Tres modos de entrada: oración
interactiva / archivo .txt en lote / archivo .conllu ya anotado. Anuncio del comando `-help`.

### ② Análisis semántico (por oración)
1. Stanza produce el análisis de dependencias (tokens, lemas, árbol UD).
2. Núcleo vs. periferia: qué es argumento (x1, x2, x3…) y qué es adjunto (temporal / locativo /
   modo / otro); recupera el sujeto omitido (pro-drop) de la morfología verbal; detecta los
   clíticos y los registra como índices de concordancia AGX (dativo "le", "se" pasivo /
   impersonal / aspectual, reflexivos), incluida la inespecificación del actor (Ø) en "se
   venden casas".
3. Clasificación aspectual: embeddings del complejo verbal (verbo + clíticos + objeto) → dos
   cabezas (léxica + contextual) combinadas → vector de 4 rasgos (estático, dinámico, télico,
   puntual) → árbol de decisión → clase de Vendler/Van Valin (Estado, Actividad, Realización,
   Logro, Semelfactivo, Realización activa).
4. Correcciones estructurales (gates): causatividad (léxico curado + heurística), telicidad
   composicional del objeto (objeto sin determinante → Actividad; objeto de medida → Realización
   activa; "se" completivo), pruebas de Van Valin detectadas en la oración ("durante una hora"
   fuerza lectura iterativa…), impersonales y pro-drop.
5. Construcciones ditransitivas (recipiente): tres plantillas — transferencia (dar), benefactiva
   (comprar/hacer, con PURP), comunicación (decir) — desde el léxico curado.
6. Construcción de la Estructura Lógica (EL formal + léxica) + wrappers de la periferia
   (be-in' locativos, during'/for' temporales, yesterday' adverbios) anidados por fuera.

### ③ Análisis sintáctico
Las decisiones semánticas viajan DENTRO del archivo .conllu como marcas por palabra (canal
MISC) → el conversor ud2rrg (con su capa española) dibuja el árbol de constituyentes RRG:
estratos SENTENCE > CLAUSE > CORE > NUC; nodo AGX bajo el núcleo para los clíticos; periferia
anclada por estrato (temporal → cláusula; locativo/modo → centro); posición destacada LDP para
"Ayer, …".

### ④ Verificación (Integridad / Completeness Constraint)
El verificador compara EL ↔ árbol: cada argumento de la EL debe tener su constituyente (o
satisfacerse morfológicamente: pro-drop, clítico solo), cada wrapper su rama de periferia en el
estrato correcto, cada AGX su nodo. Métricas actuales (caja pequeña de cifras, buen material de
presentación): conversión 98% (AnCora) / 94% (PUD, examen a ciegas); Integridad 94.9%.

### ⑤ Resultado + interacción
- Salida en orden GRR: árbol sintáctico PRIMERO → EL léxica justo debajo → tipo, EL formal,
  argumentos (con papeles: Actor/Efectuador, Undergoer/Tema, NMR/Poseedor…), rasgos traducidos,
  línea de Integridad traducida. Detalle técnico con `--verbose`.
- `-help` / `-help término`: glosario (62 términos, 7 categorías) — disponible en todos los
  prompts del flujo.
- Guardar en .txt.
- (c) Corregir: menú (clase aspectual / EL completa / enrutado de un elemento) → validación en
  3 niveles (formalismo, consistencia con la oración, plantilla reconocible; rechazo explicado)
  → enrutado AUTOMÁTICO del destino (léxicos vivos con marca de auditoría, o staging para
  revisión del curador) → re-análisis de confirmación (si no confirma, se revierte) →
  **el ciclo se cierra**: las correcciones alimentan los léxicos que usará el próximo análisis
  (la flecha de aprendizaje que vuelve a ⑥/②).

### ⑥ Datos y léxicos curados (mostrarlos como almacenes conectados a las etapas que los usan)
Semilla de clases aspectuales · oraciones contextuales (curadas a mano, append-only) · léxico
ditransitivo · léxico causativo · listas de config (movimiento, duración, adverbios) · glosario
· archivos de staging de correcciones + log maestro.

## Panel APARTE: "Faltantes y mejoras futuras" (fuera del flujo, punteado, atenuado)

Agrupar en 3 bloques:
- **Sintaxis-semántica**: oraciones compuestas (teoría de juntura-nexo RRG, cadenas de xcomp);
  plantilla interna del se-pasivo (BECOME estado'); sintagmas completos en la EL ("casas
  baratas", no solo "casas"); depictivos a periferia ("duerme enroscado"); guardas
  anti-sobredisparo de causatividad; periferia tipo "otro" representada en la EL + mejor tipado
  ("los fines de semana" = frecuencia); wrapper de frecuencia; impersonal refleja por
  animacidad; complemento agente con "por" como cadena causal secundaria; migración de lo/la a
  AGX.
- **Nivel pragmático** (fase futura): operadores (<TNS> <ASP> <MOD> <FI>), estructura
  informativa (foco/tópico), homógrafos del parser.
- **Herramientas**: "corregir todo" (EL + clase juntas) en el bucle; lote de datos de medidas;
  fallback con probe para verbos desconocidos; forma plena de los verbos de comunicación.

## Aceptación

- El diagrama se entiende SIN conocer el proyecto (probarlo mentalmente: ¿alguien que solo sabe
  RRG puede seguir el flujo de "Juan le dio flores a María" de principio a fin?).
- El flujo real y el panel futuro están inequívocamente separados.
- El ciclo de aprendizaje (corrección → léxico → análisis) es visible como bucle.
- SVG legible proyectado; HTML abre bien; cero solapamientos.
