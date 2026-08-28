# Auditoría LA2.1 — logros canónicos

Fuente: correcciones de usuario ya existentes en `correcciones_clase.csv` y
`correcciones_el.csv`. No se promovió ninguna fila ni se modificaron datos curados.

## Causa demostrada

El clasificador no fue el origen del error. Para ambas oraciones produjo un vector
inequívocamente puntual y télico y una confianza alta. Después, el gate composicional
`obj_desnudo→Activity` interpretó el sujeto de un logro inacusativo como si fuera un
efectuador de una actividad transitiva sin objeto delimitador.

La corrección localizada exige que ese gate solo opere cuando la clase léxica de la base
sea durativa (`activity` o `active_accomplishment`). `explotar` figura como
`achievement`, por lo que conserva el resultado del clasificador.

## Parse y resultados

| Oración | Parse UD relevante | Complejo | Vector registrado | Clase léxica | Gate antes | Antes | Después | EL final | CAUSE |
|---|---|---|---|---|---|---|---|---|---|
| La bomba explotó. | `bomba —nsubj→ explotó(root)` | `{explotó(3)}` | stat 0.00, dyn 0.01, tel 0.97, pun 1.00, conf 0.98 | achievement | `obj_desnudo→Activity` | Activity | Achievement | `INGR explotar'(bomba)` | no |
| El globo explotó. | `globo —nsubj→ explotó(root)` | `{explotó(3)}` | stat 0.00, dyn 0.01, tel 0.99, pun 1.00, conf 0.99 | achievement | `obj_desnudo→Activity` | Activity | Achievement | `INGR explotar'(globo)` | no |

La ejecución integrada posterior a la corrección produjo para `El globo explotó`:
`stat=0.0006`, `dyn=0.0075`, `tel=0.9959`, `pun=0.9975`, confianza `0.9955`,
clase final `achievement`, sin coerciones, sin gates y sin `CAUSE`.

## Decisión

Se aplicó una corrección postclasificador localizada. No hacen falta cambios de pesos,
umbrales, BERTIN, modelos `.joblib` ni reentrenamiento para este defecto. Los fallos lentos
históricos de `el perro se sacudió`, `Juan llegó` y `blend_sube_pun` quedan fuera de alcance.
