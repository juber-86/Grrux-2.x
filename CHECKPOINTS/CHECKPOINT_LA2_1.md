# CHECKPOINT LA2.1 — confianza, Linking causal y logros

Fecha: 2026-07-23. Se detiene aquí; no se inicia reentrenamiento ni otra fase.

## 1. Diagnóstico de `c.confianza.toFixed`

El contrato LA2 enviaba `causatividad.confianza="alta"|"baja"` y la GUI ejecutaba
`toFixed(2)` directamente sobre ese valor. La excepción ocurría en
`renderCausatividad` antes de `renderLinking`, por lo que un Linking válido quedaba oculto.

Garantía LA2.1:

- el motor normaliza toda `confianza` expuesta a `float` finito en `[0,1]` o `null`;
- la etiqueta cualitativa causal se conserva separada en `nivel_confianza`;
- la GUI convierte cadenas numéricas heredadas, muestra dos decimales y usa `—` para
  valores ausentes o inválidos;
- no existe ninguna llamada `.confianza.toFixed`;
- el formateador visual se prueba con `0.55`, `"0.55"`, `null`, ausente, `"alta"`,
  objeto, `NaN` e infinito.

## 2. Causativas de punta a punta

Ejecución real offline con Stanza y BERTIN locales:

| Diana | Tipo visible | EL léxica | Actor | Undergoer | PSA | Concordancia | Integridad |
|---|---|---|---|---|---|---|---|
| Se venden casas. | Realización causativa | `[do'(Ø, Ø)] CAUSE [BECOME vendido'(casas)]` | — | casas (`arg_estado`) | Undergoer | 3pl ✓ | ✓ |
| Juan rompió la ventana. | Logro causativo | `[do'(Juan, Ø)] CAUSE [INGR roto'(ventana)]` | Juan | ventana (`arg_estado`) | Actor | 3sg ✓ | ✓ |

El contrato real del motor contiene para ambas una línea compacta de Linking, traza de
cinco pasos, macropapeles, PSA y voz. La prueba de transporte API conserva conjuntamente
`confianza=null`, `nivel_confianza` y el bloque Linking.

La terminal usa la misma clase visible y la misma estructura Linking. Se añadió una
regresión fría específica.

La navegación visual embebida no pudo conectarse al proceso localhost del sandbox
(`ERR_CONNECTION_REFUSED` entre entornos aislados). No se fabricó una captura. La capa
visual se verificó mediante su módulo puro de formato, sintaxis JavaScript y contrato de
render; la evidencia real de datos proviene del motor/API.

## 3. Auditoría de logros canónicos

Diagnóstico completo en `INFORME_LOGROS_LA2_1.md`.

Antes:

```text
El globo explotó.
vector: stat=0.00 dyn=0.01 tel=0.99 pun=1.00 conf=0.99
gate=obj_desnudo→Activity
clase final: activity
```

Después:

```text
clase final: achievement
EL: INGR explotar'(globo)
CAUSE: no
```

El clasificador ya daba un logro inequívoco. El defecto estaba después: el gate de objeto
desnudo degradaba también bases léxicas `achievement`. La corrección localizada exige una
base léxicamente durativa antes de degradar. No se cambiaron pesos, umbrales, BERTIN,
`.joblib` ni datos de entrenamiento.

La auditoría cubre las dos correcciones manuales existentes: `La bomba explotó` y
`El globo explotó`. Ambas comparten parse `nsubj→explotó(root)`, complejo `{explotó(3)}`,
base léxica `achievement` y el mismo gate espurio anterior.

## 4. Validación

- Suite rápida completa `pytest -k 'not slow'`: sin fallos.
- Suite focal de confianza, motor, servidor, GUI, causativas y logros: sin fallos.
- Integración lenta LA2.1 offline: `1 passed`.
- Ejecución real del motor: las tres dianas cumplen clase, EL, Linking, PSA,
  concordancia e Integridad.
- Sintaxis de `gui/contrato_confianza.js` y `gui/app.js`: válida.
- PUD no se ejecutó.
- Sin cambios en `ud2rrg.py`, BERTIN, clasificadores, árboles/modelos `.joblib`,
  corroborador, `contextual_sentences.csv` ni golds.
- Los tres fallos lentos históricos siguen fuera de alcance.

## 5. Archivos y commits

Archivos de LA2.1:

- `gruxx_motor.py`, `gui/app.js`, `gui/index.html`, `gui/contrato_confianza.js`;
- `aspect_classifier/causatividad.py`, `rrg_ls_mapper.py`;
- pruebas de motor, servidor, GUI, causatividad, Linking y logros;
- `INFORME_LOGROS_LA2_1.md` y este checkpoint.

Commits:

- `c4e5856f` — `LA2.1: normalizar confianza para la GUI`
- `fc67f579` — `LA2.1: validar causativas y logros canónicos`
- `LA2.1: cerrar checkpoint de validación` — commit que contiene este checkpoint y la
  prueba final del transporte API.

Los CSV de correcciones y logs ya modificados antes de LA2.1 quedaron fuera de los
commits; no se promovió ni alteró ningún dato curado.
