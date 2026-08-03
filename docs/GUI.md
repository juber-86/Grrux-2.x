# gruxx GUI — uso

Interfaz web local para el analizador GRR. Complementa a la terminal
(`python3 gruxx_ai1.py`), no la reemplaza: los dos modos siguen soportados.

## Arrancar

```
./gruxx-gui
```

La primera vez levanta el servidor (`gruxx_server.py`, carga Stanza +
BERTIN — tarda; puede verse el progreso en `gruxx-gui.log`) y abre el
navegador en `http://127.0.0.1:8763/`. Invocaciones siguientes detectan el
servidor ya corriendo y solo abren una pestaña/ventana nueva — **nunca**
arrancan una segunda instancia (la máquina es de 12 GB; Stanza + BERTIN
residentes ocupan ~2 GB).

**No** correr `./gruxx-gui` (ni dejarlo abierto) al mismo tiempo que
`python3 gruxx_ai1.py` en modo interactivo o que las suites `--slow` —
ambos cargan su propia copia de los mismos modelos.

Para cerrar el servidor: `pkill -f "uvicorn gruxx_server:app"` (o matar el
proceso que quedó en `gruxx-gui.log`).

## Icono de escritorio (opcional, instalación manual)

El repo trae `gruxx.desktop` de ejemplo, ya con `Icon=` apuntando a
`grrux_logo.png` (raíz del repo, ruta absoluta — el mismo logo que aparece
en el favicon y la cabecera de la GUI). Para instalarlo en tu sesión:

```
cp gruxx.desktop ~/.local/share/applications/gruxx.desktop
chmod +x ~/.local/share/applications/gruxx.desktop
update-desktop-database ~/.local/share/applications 2>/dev/null || true
```

Ajusta la ruta de `Exec=` dentro del `.desktop` si copiaste el repo a otra
ubicación. Nada de esto se instala automáticamente — es manual, a criterio
de cada quien.

## Qué hace cada pieza

- `gruxx_motor.py` — el pipeline de análisis (Stanza → mapper → árbol RRG →
  completeness) como funciones Python, sin CLI. `PROHIBIDO tocar el motor`
  real (`rrg_ls_mapper.py`, `ud2rrg.py`, etc.) — esto es solo orquestación.
- `gruxx_server.py` — FastAPI, `127.0.0.1:8763`, un solo worker. Endpoints:
  `GET /estado`, `POST /analizar`, `GET /glosario[?termino=]`, estáticos de
  `gui/`.
- `gui/` — página única en JS plano (sin build, sin CDN): `index.html` +
  `app.js` + `estilo.css`. Copiable a otra máquina junto con el resto del
  repo y funciona offline (mientras el servidor esté arriba).

## Estado de la fase (G0–G3)

Implementado: ver la oración, árbol RRG dibujado (SVG), EL léxica/formal
con hover bidireccional hacia el árbol y la tabla de argumentos, rasgos
aspectuales (barras proporcionales, G3 §0), chips de Integridad,
causatividad, glosario con tooltips y panel de búsqueda, toggle de detalle
técnico; bucle de corrección completo (Clase / Estructura Lógica / Enrutado
/ **Corregir todo** — EL+clase en un paso, G3 §2) con diff antes/después;
modo **Lote** (textarea o `.txt`, tabla con filtro ⚠, G3 §3); exportar
**SVG/PNG/.txt/.conllu** por análisis y por fila de lote (G3 §4); panel de
**Curación** de solo lectura sobre los CSV de staging + log maestro (G3
§5); historial persistente en `localStorage` (G3 §6, clic = re-analiza,
nunca resucita el resultado viejo).

**Deuda conocida**: seleccionar el elemento a enrutar clicando su nodo en
el árbol SVG (stretch opcional de G3 §6.2) no entró — la lista clicable de
G2 sigue siendo el mecanismo vigente en la pestaña Enrutado.

## Periferia en el árbol — decisión de dibujo (1ª iteración)

La convención de Van Valin dibuja la periferia con una flecha lateral hacia
su estrato. Esta iteración usa el *fallback* explícitamente autorizado: el
nodo `-PERI` se dibuja en su posición normal del árbol (nunca se altera la
estructura) con borde punteado + color distintivo, y su padre (el estrato
ancla: NUC/CORE/CLAUSE) se resalta con un borde más grueso del mismo color.
La flecha curva queda para iterar con capturas en un checkpoint posterior.
