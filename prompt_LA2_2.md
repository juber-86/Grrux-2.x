# Tarea LA2.2: enrutado acotado a la oración activa

Proyecto **GRRux**. No renombrar todavía los archivos históricos `gruxx_*`.

Leer `CHECKPOINT_LA2.md` y `CHECKPOINT_LA2_1.md` antes de implementar. Esta es una corrección
puntual de la interfaz de enrutado posterior a LA2.1.

## Problema

En el modal **Corregir → Enrutado**, la lista de “¿Qué nodo/elemento está mal?” acumula o
reutiliza nodos de análisis u oraciones pasadas. El usuario puede ver y seleccionar nodos que
no pertenecen a la oración que está analizando ahora.

Eso es incorrecto: una corrección debe referirse exclusivamente a la suboración activa del
análisis activo.

## Decisión de producto

Hay dos listas conceptualmente distintas y LA2.2 solo restringe la primera:

| Control | Regla correcta |
|---|---|
| **Nodo/elemento a corregir** (origen) | Mostrar únicamente instancias reales de la **suboración activa** del **análisis activo**. Nunca nodos de historial, análisis anterior u otra suboración. |
| **Qué debería ser** (destino) | Conservar el inventario completo de rutas de la proyección acordado en LA2, incluidas las opciones ausentes y las rutas `solo_staging`. No filtrarlo según los nodos presentes. |

No revertir LA2 confundiendo “inventario completo de destinos” con “lista acumulada de nodos
origen”. El usuario conserva todas las alternativas teóricas de destino, pero solo puede mover
un elemento que pertenezca a la oración/suboración abierta.

## Contrato de alcance

La fuente de una selección de enrutado queda definida por la tupla:

```text
(analisis_id, sub_idx, elemento_id)
```

- `analisis_id` identifica el análisis actualmente mostrado.
- `sub_idx` identifica la suboración actualmente seleccionada dentro de ese análisis.
- `elemento_id` debe pertenecer a esa suboración. No basta con que exista en un resultado
  anterior o en otra suboración.

Al abrir el modal, cambiar de suboración, usar un análisis nuevo tras un reanálisis o seleccionar
una entrada del historial, la UI debe:

1. reconstruir desde cero la lista de origen a partir de la suboración activa;
2. vaciar cualquier selección previa de `elementoEnrutado`;
3. ocultar/desactivar el bloque de destino hasta que se seleccione una instancia válida de la
   nueva suboración;
4. eliminar listeners, nodos DOM o estado que apunten al análisis anterior;
5. no conservar texto, id ni etiqueta visual de una selección vieja.

No usar una lista global acumulativa de nodos, ni fusionar resultados de `historial`,
`resultadoActual`, diffs antes/después o suboraciones distintas.

## Implementación esperada

1. Localizar la estructura de estado que alimenta la pestaña Enrutado y hacer explícita la
   pertenencia al análisis/suboración actual.
2. Construir la lista origen solo desde los argumentos, periferias, AGX u otras instancias
   realmente serializadas para la suboración activa. No recorrer el historial de sesión.
3. Si la suboración no tiene instancias enrutables, mostrar el estado vacío honesto y no permitir
   aplicar una corrección de origen inventado.
4. Mantener la posibilidad acordada en LA2 de seleccionar una **ruta de destino ausente**. Eso
   no significa inventar un nodo origen ausente: el origen de una corrección de movimiento debe
   ser una instancia real de la suboración; la corrección de una ausencia estructural sigue el
   flujo `solo_staging` definido en LA2.1, con su contexto actual.
5. Hacer que el backend valide la tupla completa. Si llega un `elemento_id` que no pertenece a
   `(analisis_id, sub_idx)`, devolver un rechazo claro, sin escribir config, staging ni log.
6. La respuesta de reanálisis debe actualizar el `analisis_id` activo antes de permitir una nueva
   corrección. Una selección que pertenecía al análisis previo queda invalidada.

No tocar `ud2rrg.py`, el clasificador, BERTIN, `.joblib`, el corroborador, PUD ni
`contextual_sentences.csv`. No cambiar la semántica de causativas, Linking, logros, tooltips o
el inventario canónico de destinos de LA2.

## Casos de prueba obligatorios

### A. Dos análisis consecutivos

1. Analizar una oración A con nodos distinguibles.
2. Abrir Corrección → Enrutado y comprobar que solo aparecen los nodos de A.
3. Analizar una oración B con nodos distintos.
4. Abrir Corrección → Enrutado y comprobar que aparece solo B: ningún texto, id ni etiqueta de A
   permanece en la lista ni puede seleccionarse.

### B. Dos suboraciones del mismo análisis

1. Analizar una entrada con dos suboraciones.
2. Abrir el modal desde la primera: la lista contiene solo sus instancias.
3. Cambiar a la segunda y volver a abrir: la lista contiene solo sus instancias.
4. Verificar que un `elemento_id` válido para la primera se rechaza si se envía con el `sub_idx`
   de la segunda.

### C. Reanálisis y diff

1. Seleccionar una instancia válida y aplicar una corrección que produzca `analisis_nuevo`.
2. Elegir “Usar el nuevo análisis”.
3. Reabrir Enrutado: no queda la selección vieja y la lista procede exclusivamente del nuevo
   `analisis_id`/`sub_idx`.

### D. Destinos completos, origen actual

Con una oración mínima que tenga un único argumento, verificar simultáneamente:

- la lista origen tiene solo ese argumento real;
- la lista destino conserva todas las rutas de LA2, incluso periferias, PrDP/LDP, PrCS, AGX y
  rutas ausentes;
- escoger un destino `solo_staging` sigue registrando el contexto correcto de la oración actual.

### E. Seguridad de API

- `elemento_id` inexistente o perteneciente a otro análisis/suboración → rechazo claro;
- cero cambios en config, CSV de staging y log maestro;
- destino desconocido → rechazo claro;
- cancelación/cierre del modal → cero efectos.

## Validación y checkpoint

Ejecutar las pruebas rápidas pertinentes de motor, servidor y GUI. Ejecutar pruebas lentas solo
si son necesarias y respetando la advertencia OOM.

Crear `CHECKPOINT_LA2_2.md` y detenerse. Incluir:

1. causa concreta de la acumulación de nodos;
2. captura o evidencia DOM de A→B y de dos suboraciones;
3. tabla que distinga lista origen acotada frente a destinos completos;
4. validación del rechazo backend para ids de otro contexto;
5. suites ejecutadas, archivos modificados y commits de LA2.2.

No continuar con otra fase después del checkpoint.
