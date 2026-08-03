# Checkpoint — Fase LINKING, Etapa L3 (capa española de ud2rrg.py)

Implementado según `prompt_opus48_linking_L3.md`. **PARAR aquí** — L4
(checker de completeness + KPI final) espera esta revisión. Commit:
`L3: capa española de ud2rrg.py (XPOS, dativos/AGX, periferia por estrato)`.

Modificado: `ud2rrg.py` (todo cambio gated por `language=='es'` y/o MISC),
`nucleo_periferia.py` (guard "todos los días"), `ditransitivas.py` +
`misc_rrg.py` (rename Recipiente→Poseedor). Código nuevo:
`test_ud2rrg_es.py`. Actualizado (aserciones obsoletas que asumían que
ud2rrg ignoraba MISC — justo lo que L3 cambia adrede): `test_ditransitivas.py`,
`test_misc_rrg.py`, `test_nucleo_periferia.py`. Prohibiciones respetadas
(`gruxx_ai1.py`, clasificador, corroborador MLM, `pruebas_estructurales.py`,
`wrappers_ls.py`, `.joblib`, `contextual_sentences.csv` intactos).

## 1. KPI — antes (L0, `kpi_linking_baseline.json`) / después (L3, n=300,
   `kpi_linking_post_l3.json`)

| Métrica | Antes (L0) | Después (L3) |
|---|---|---|
| Conversión gold **crudo** (XPOS intacto) | 0.0% (0/300) | **87.0%** (261/300) |
| Conversión gold **limpiado** (XPOS→`_`) | 59.7% (179/300) | **87.0%** (261/300) — idéntico al crudo, confirma el fix |
| Acuerdo de periferia | 27.6% | 28.8%* |

\* **Ver pendiente crítico más abajo**: `kpi_linking.py` mide el acuerdo de
periferia corriendo `ud2rrg.transform` directamente sobre el `.conllu` gold
**sin nunca inyectarle MISC** (llama a `analizar_roles` solo como
referencia "correcta", no la vuelca al `.conllu` antes de convertir). Mi
anclaje por estrato es 100% MISC-gated (`RRGRole=Periphery`), así que esta
métrica **no lo ejercita**: el +1.2pp es ruido (más oraciones con árbol →
más comparaciones), no evidencia del fix. La evidencia real está en §2 y en
`test_slow_l3_fijaciones_ancladas` (que sí corre el pipeline completo con
MISC vía `gruxx_ai1.procesar_oracion`).

Conteos KPI3 sin cambios relevantes (doblado 9, clítico solo 27, obl:arg
total 126, periferia por tipo ~igual) — la muestra estructural del
treebank no cambia, solo cuánto de ella logra convertir.

## 2. Árboles ASCII de la suite nueva (pipeline real: Stanza + MISC + ud2rrg)

**(a) "Juan comió pizza ayer"** — `ADVP-PERI` hija de **CLAUSE**, no de CORE
(comparar contra el diagrama de referencia de Julian):

```
                │
              CLAUSE
         ┌──────┴────────────────┐
       CORE                      │
  ┌──────┼──────────────┐        │
  NP     │              NP   ADVP-PERI
  │      │              │        │
CORE_N   │            CORE_N CORE_ADV
  │      │              │        │
NUC_N   NUC           NUC_N   NUC_ADV
  │      │              │        │
N-PROP   V              N       ADV
  │      │              │        │
 Juan  comió          pizza    ayer
```

**(b) "Juan corrió en el parque"** — `PP-PERI` hija de **CORE** (locativo,
modifica el evento, no toda la cláusula):

```
                 │
               CLAUSE
                 │
                CORE
  ┌──────┬───────┴────────┐
  │      │             PP-PERI
  │      │                │
  │      │             CORE_P
  │      │       ┌────────┴─────┐
  NP     │       │             NP
  │      │       │        ┌─────┴────┐
CORE_N   │       │        │        CORE_N
  │      │       │        │          │
NUC_N   NUC    NUC_P      │        NUC_N
  │      │       │        │          │
N-PROP   V       P     OP-DEF        N
  │      │       │        │          │
 Juan  corrió    en      el        parque
```

**(c) "Le compró un regalo a María"** — el árbol **por fin existe** (antes
de L3, `obl:arg` no estaba en el dispatch y la oración entera fallaba).
`AGX` bajo `NUC` (hermano del `NUC` con `PRED>V`); doblado: "María" sigue
siendo `NP` argumento del `CORE` (vía `PP`, un solo argumento semántico,
dos materializaciones sintácticas):

```
                  │
                CLAUSE
                  │
                 CORE
     ┌────────────┴──────┬─────────────────┐
     │                   │                 PP
     │                   │                 │
     │                   │               CORE_P
     │                   │           ┌─────┴──────┐
     │                  NP           │            NP
     │            ┌──────┴────┐      │            │
    NUC           │         CORE_N   │          CORE_N
 ┌───┴────┐       │           │      │            │
 │       NUC      │         NUC_N  NUC_P        NUC_N
 │        │       │           │      │            │
AGX       V     OP-DEF        N      P          N-PROP
 │        │       │           │      │            │
Le      compró    un        regalo   a          María
```

**(d) "Le dije la verdad"** — `AGX` sin doblar: solo el clítico, sin `NP`/`PP`
pleno adicional (Completeness Constraint satisfecho morfológicamente):

```
                │
              CLAUSE
                │
               CORE
     ┌──────────┴─────────────┐
     │                       NP
     │                  ┌─────┴────┐
    NUC                 │        CORE_N
 ┌───┴───┐              │          │
 │      NUC             │        NUC_N
 │       │              │          │
AGX      V            OP-DEF       N
 │       │              │          │
Le      dije            la       verdad
```

## 3. Decisión: sufijo `-PERI` (no nodo `PERIPHERY` explícito)

`peri()` ya existía y solo añade el sufijo `-PERI` a la etiqueta del nodo
(intacto, no lo toqué). NO introduje un nodo `PERIPHERY` envolvente:
las operaciones de composición (`linkage.core_sub/core_cosub/core_coord`,
`NUC-SUB`, `attach_conjunct`, `trim`, `conflate`, `layer_priority`...) hacen
pattern-matching exacto contra las etiquetas fijas `SENTENCE/CLAUSE/CORE/NUC`
en decenas de sitios del archivo (3000 líneas); interponer un nodo
`PERIPHERY` entre `CLAUSE`/`CORE` y su hijo periférico rompería esos
matches sin ninguna ganancia semántica — el sufijo ya marca sin ambigüedad
"esto es periferia" conservando el padre correcto (CLAUSE o CORE según
estrato), que es exactamente lo que pedía la decisión 2 de Julian.

## 4. Evidencia del gating

`test_gating_lengua_no_es_ignora_misc` y `test_gating_es_sin_misc_no_cambia`
(en `test_ud2rrg_es.py`, rápidos, sin Stanza): fixture inglesa con
`RRGRole=Periphery` en MISC (igual que produciría la Etapa 1 para español)
da **exactamente el mismo árbol** que sin esas marcas — el anclaje por
estrato no dispara para `language != 'es'`. Verificado también
manualmente contra la copia pre-L3 de `ud2rrg.py` (commit `025c7005`) sobre
`prueba.conllu` (inglés) y un fixture con `obl`+`advmod`: **byte-idénticos**
en en/de/fr/ru/fa. `test_gold_ancora_crudo_convierte_igual_que_limpiado`
confirma además crudo==limpiado en 20 oraciones AnCora reales.

## 5. Guard "todos los días" — disparos

No disparó sobre datos reales en esta sesión (no se corrió sobre una
muestra masiva, solo sobre los 3 fixtures del prompt, ya cubiertos por
`test_guard_frecuencia_caso_a_otro_nsubj`,
`test_guard_frecuencia_caso_b_mismatch_pro_drop` y
`test_guard_frecuencia_control_no_degrada` en `test_nucleo_periferia.py`,
los tres verdes). **Hallazgo**: la oración original de Julian
("Todos los días yo como chocolates") NO reproduce el bug con la versión
actual de Stanza — el parser confunde "como" (1sg de comer) con la
conjunción homógrafa "como" (SCONJ) y da un parse totalmente distinto
(`yo` como root, `días`/`chocolates` como `nmod` de `yo`), no el patrón
"días como nsubj" que describía el reporte. El guard se implementó y
testeó "en frío" (tokens a mano, como el resto de `nucleo_periferia.py`)
replicando el patrón lógico exacto que describe el prompt, pero queda
pendiente confirmar con Stanza real si el guard dispara para la frase
original de Julian tal cual el parser la entrega hoy.

## 6. Pendientes acumulados

- **Wrapper de frecuencia**: sigue sin implementar (el guard solo degrada
  a periferia temporal, no envuelve) — como pedía el prompt.
- **KPI2 no mide el anclaje por estrato** (ver §1) — si se quiere una cifra
  de acuerdo de periferia que sí lo ejercite, `kpi_linking.py` necesitaría
  inyectar MISC (vía `misc_rrg`) antes de llamar a `ud2rrg.transform`, no
  solo comparar contra `analizar_roles` como referencia externa. No lo
  toqué (no estaba en el alcance de L3).
- **`obl:arg`/`obl:agent` bajo cabeza NOMINAL o ADJETIVAL** (no verbal):
  hallazgo nuevo corriendo gold AnCora crudo — 2/30 oraciones de una
  muestra fallan porque el argumento cuelga de un sustantivo/adjetivo
  (nominalización), y `transform_N`/`transform_A` no tienen el mismo
  dispatch que agregué en `transform_V`. Candidato para L3.5 o L4.
- **`expl:pass`/`expl:impers`**: sin manejo en el dispatch (4/30 en la
  misma muestra) — preexistente, el prompt solo pedía cuidar de no romper
  `expl`/`expl:pv`, no cubrir estos. Sigue fallando visiblemente (correcto
  por el punto 5 del prompt: sin rescate plano).
- **`test_lexicon_carga_54_verbos`** (`test_ditransitivas.py`) falla:
  `verbos_ditransitivos.xlsx` ya tiene 122 verbos, no 54 (Julian lo ha
  seguido curando) — desactualizado, ajeno a L3, no lo toqué.
- **`test_slow_blend_sube_pun`** (`test_pruebas_aspectuales.py`) falla:
  territorio del corroborador MLM/clasificador (prohibido tocar), no
  investigado a fondo — reportado tal cual se encontró.
- Heredados de L0-L2.5 sin resolver: compuestos "cerca de"/"delante de"
  (parseo inconsistente de Stanza), expansión de `_CASE_TEMPORAL`
  (por/antes/después/hasta/desde), forma plena de comunicación
  (`express(α).to.(β)...`), fallback con probe BERTIN, bucle de corrección
  del usuario.

## 7. Suites — 137 tests (fast+slow), 135 verdes

causatividad 9, complejo 6, ditransitivas 17 (**1 fail preexistente**,
lexicon), fase2_contextual 8, misc_rrg 19, nucleo_periferia 13 (+3 tests
nuevos del guard), pruebas_aspectuales 14 (**1 fail preexistente**, blend),
pruebas_estructurales 25, **ud2rrg_es 4 (nuevo)**, wrappers_ls 22. Los 2
fails están verificados como preexistentes (idénticos corriendo el mismo
test contra el commit `025c7005`, pre-L3) y ajenos al alcance de esta etapa.
