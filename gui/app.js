/* GRRux GUI — Fase G1.2. JS plano, sin build, sin CDN. */
"use strict";

const API = "";
const SVG_NS = "http://www.w3.org/2000/svg";
const { confianzaNumerica, formatearConfianza } = globalThis.GrruxConfianza;

// Nodos que el árbol destaca visualmente (posiciones RRG relevantes).
const LABELS_DESTACADOS = new Set(["PrDP", "LDP", "PrCS"]);

// ─── estado global de la sesión (en memoria del navegador, nada persistente) ─
const estadoApp = {
  glosario: [],
  contratoGui: { tooltips: {}, rutas: [] },
  resultadoActual: null,
  subIdxActual: 0,
  verbose: false,
  tokenIdxAVar: {},    // token_id-1 -> x|y|z, repoblado por renderArgumentos
  corregirCtx: null,   // {analisis_id, sub_idx} de la (sub)oración en edición (G2 §3)
  elementoEnrutado: null,   // elemento elegido en la pestaña Enrutado (G2 §3)
  rutasEnrutado: [],
  operadorEnEdicion: null,  // operador elegido en la pestaña Operadores (OPERATORS_2 §2)
  // Etapa OPERATORS: la proyección de operadores arranca OCULTA para no
  // saturar la vista; con ella activa la pantalla muestra las TRES
  // representaciones de la RRG (constituyentes + operadores + EL) ancladas
  // entre sí — modo presentación.
  mostrarOperadores: false,
};

// ═══════════════════════════ arranque / sondeo de /estado ══════════════════
const $ = (sel) => document.querySelector(sel);

const btnAnalizar = $("#btn-analizar");
const inputOracion = $("#input-oracion");
const mensajeEstado = $("#mensaje-estado");

async function sondearEstado() {
  try {
    const r = await fetch(`${API}/estado`);
    const j = await r.json();
    if (j.listo) {
      btnAnalizar.disabled = false;
      btnAnalizar.textContent = "Analizar";
      mensajeEstado.textContent = "";
      return;
    }
  } catch (e) { /* servidor aún no responde — seguimos sondeando */ }
  btnAnalizar.disabled = true;
  btnAnalizar.textContent = "cargando modelos…";
  setTimeout(sondearEstado, 2000);
}

btnAnalizar.addEventListener("click", () => analizarOracion());
inputOracion.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && !btnAnalizar.disabled) analizarOracion();
});

async function analizarOracion() {
  const oracion = inputOracion.value.trim();
  if (!oracion) return;
  btnAnalizar.disabled = true;
  btnAnalizar.textContent = "analizando…";
  mensajeEstado.classList.remove("error");
  mensajeEstado.textContent = "";
  try {
    const r = await fetch(`${API}/analizar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ oracion }),
    });
    if (!r.ok) {
      const detalle = await r.json().catch(() => ({}));
      throw new Error(detalle.detail || `HTTP ${r.status}`);
    }
    const resultado = await r.json();
    if (resultado.error) {
      mensajeEstado.classList.add("error");
      mensajeEstado.textContent = `Error del análisis: ${resultado.error}`;
      return;
    }
    registrarEnHistorial(oracion, resultado);
    mostrarResultado(resultado);
  } catch (e) {
    mensajeEstado.classList.add("error");
    mensajeEstado.textContent = `No se pudo analizar: ${e.message}`;
  } finally {
    btnAnalizar.disabled = false;
    btnAnalizar.textContent = "Analizar";
  }
}

// ═══════════════════════ resúmenes compartidos (historial + lote) ══════════
// G3 §3/§6 — misma lectura de "clase"/"integridad" para una fila de tabla de
// lote y para una entrada de historial: una sola función, nunca duplicada.
function resumenClase(resultado) {
  const subs = (resultado && resultado.sub_oraciones) || [];
  if (subs.length === 0) return "—";
  if (subs.length === 1) return subs[0].el.tipo_legible || subs[0].el.tipo || "—";
  return `${subs.length} sub-oraciones`;
}

function resumenIntegridad(resultado) {
  const subs = (resultado && resultado.sub_oraciones) || [];
  const oks = subs.map((s) => s.integridad && s.integridad.ok);
  if (oks.some((o) => o === false)) return "⚠";
  if (oks.length && oks.every((o) => o === true)) return "✓";
  return "—";
}

function resumenAvisos(resultado) {
  const subs = (resultado && resultado.sub_oraciones) || [];
  const notas = subs.flatMap((s) => s.notas || []);
  if (notas.length === 0) return "";
  const cortas = notas.slice(0, 2).join(" · ");
  return notas.length > 2 ? `${cortas} …` : cortas;
}

function claseIntegridadChip(simbolo) {
  const mapa = { "✓": "ok", "⚠": "falta_en_arbol", "—": "sin_arbol" };
  return `chip ${mapa[simbolo] || "sin_arbol"}`;
}

// ═══════════════════════ historial persistente (G3 §6) ═════════════════════
// Persistido en localStorage (oración+fecha+clase+integridad, SIN el
// resultado completo -- el clic siempre RE-ANALIZA: los léxicos pueden
// haber cambiado desde entonces, resucitar el resultado viejo sería
// deshonesto). Nada de esto crea archivos nuevos del lado servidor.
const HISTORIAL_KEY = "grrux_historial_v1";
const HISTORIAL_MAX = 500;

function cargarHistorialPersistente() {
  try {
    const lista = JSON.parse(localStorage.getItem(HISTORIAL_KEY) || "[]");
    return Array.isArray(lista) ? lista : [];
  } catch (e) {
    return [];
  }
}

function guardarHistorialPersistente(lista) {
  try {
    localStorage.setItem(HISTORIAL_KEY, JSON.stringify(lista.slice(-HISTORIAL_MAX)));
  } catch (e) { /* localStorage lleno/deshabilitado -- el análisis sigue funcionando */ }
}

function registrarEnHistorial(oracion, resultado) {
  const lista = cargarHistorialPersistente();
  lista.push({ oracion, fecha: new Date().toISOString(),
              clase: resumenClase(resultado), integridad: resumenIntegridad(resultado) });
  guardarHistorialPersistente(lista);
  renderHistorial();
}

function renderHistorial() {
  const ul = $("#lista-historial");
  ul.innerHTML = "";
  const lista = cargarHistorialPersistente();
  [...lista].reverse().forEach((entrada) => {
    const li = document.createElement("li");
    const fecha = new Date(entrada.fecha);
    const fechaTxt = isNaN(fecha) ? "" : fecha.toLocaleString();
    li.innerHTML = `<span class="historial-oracion">${escapeHTML(entrada.oracion)}</span>` +
      `<span class="historial-meta">${escapeHTML(entrada.clase || "")} · ${entrada.integridad || ""} · ${fechaTxt}</span>`;
    if (estadoApp.resultadoActual && estadoApp.resultadoActual.oracion === entrada.oracion) {
      li.classList.add("activa");
    }
    // Clic = RE-ANALIZA (nunca resucita el resultado viejo: los léxicos
    // pueden haber cambiado desde que se guardó esta entrada).
    li.addEventListener("click", () => {
      inputOracion.value = entrada.oracion;
      analizarOracion();
    });
    ul.appendChild(li);
  });
}

$("#btn-limpiar-historial").addEventListener("click", () => {
  guardarHistorialPersistente([]);
  renderHistorial();
});

// ══════════════════════════ render de un resultado completo ════════════════
function mostrarResultado(resultado) {
  estadoApp.resultadoActual = resultado;
  estadoApp.subIdxActual = 0;
  inputOracion.value = resultado.oracion;
  renderHistorial();
  renderTabsSubOraciones(resultado);
  renderSubOracion(resultado.sub_oraciones[0]);
}

function renderTabsSubOraciones(resultado) {
  const nav = $("#tabs-suboraciones");
  const n = resultado.sub_oraciones.length;
  if (n <= 1) {
    nav.classList.add("oculto");
    nav.innerHTML = "";
    return;
  }
  nav.classList.remove("oculto");
  nav.innerHTML = "";
  for (let i = 0; i < n; i++) {
    const b = document.createElement("button");
    b.textContent = `Sub-oración ${i + 1}`;
    if (i === estadoApp.subIdxActual) b.classList.add("activa");
    b.addEventListener("click", () => {
      estadoApp.subIdxActual = i;
      [...nav.children].forEach((c) => c.classList.remove("activa"));
      b.classList.add("activa");
      renderSubOracion(resultado.sub_oraciones[i]);
    });
    nav.appendChild(b);
  }
}

// ═══════════════════════ render de UNA (sub)oración ═════════════════════════
function renderSubOracion(sub) {
  renderArbol(sub);
  renderEL(sub);
  renderTipo(sub);
  renderArgumentos(sub);
  renderRasgos(sub);
  renderIntegridad(sub);
  renderCausatividad(sub);
  renderLinking(sub);
  renderNotas(sub);
  renderCrudo(sub);
}

// ─── Árbol SVG ────────────────────────────────────────────────────────────
const LEAF_MIN_W = 70, NODE_H = 26, V_GAP = 56, H_GAP = 16, CHAR_W = 8;

function textoDeToken(tokens, idx) {
  const t = tokens[idx];
  return t ? t.texto : `#${idx}`;
}

function anchoNodo(texto) {
  return Math.max(LEAF_MIN_W, texto.length * CHAR_W + 22);
}

function medir(nodo, tokens) {
  if ("token" in nodo) return anchoNodo(textoDeToken(tokens, nodo.token));
  const hijos = nodo.hijos || [];
  if (hijos.length === 0) return anchoNodo(nodo.label || "");
  let suma = 0;
  hijos.forEach((h, i) => { if (i > 0) suma += H_GAP; suma += medir(h, tokens); });
  return Math.max(suma, anchoNodo(nodo.label || ""));
}

function ubicar(nodo, tokens, profundidad, xIni) {
  if ("token" in nodo) {
    const w = anchoNodo(textoDeToken(tokens, nodo.token));
    return { tipo: "hoja", x: xIni + w / 2, y: profundidad * V_GAP, w,
             texto: textoDeToken(tokens, nodo.token), tokenIdx: nodo.token };
  }
  const hijos = nodo.hijos || [];
  const w = medir(nodo, tokens);
  if (hijos.length === 0) {
    return { tipo: "nodo", label: nodo.label, x: xIni + w / 2, y: profundidad * V_GAP,
             w, hijos: [] };
  }
  const colocados = [];
  let cursor = xIni;
  hijos.forEach((h, i) => {
    if (i > 0) cursor += H_GAP;
    const p = ubicar(h, tokens, profundidad + 1, cursor);
    colocados.push(p);
    cursor += p.w;
  });
  const cx = (colocados[0].x + colocados[colocados.length - 1].x) / 2;
  return { tipo: "nodo", label: nodo.label, x: cx, y: profundidad * V_GAP,
           w, hijos: colocados };
}

function profundidadMax(nodo) {
  if ("token" in nodo) return 0;
  const hijos = nodo.hijos || [];
  if (hijos.length === 0) return 0;
  return 1 + Math.max(...hijos.map(profundidadMax));
}

function esPeri(label) { return typeof label === "string" && label.endsWith("-PERI"); }

function crearElemSVG(tag, attrs) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const k in attrs) el.setAttribute(k, attrs[k]);
  return el;
}

function dibujarNodo(svg, colocado, padreColocado) {
  const grupo = crearElemSVG("g", { class: "arbol-nodo", transform: `translate(${colocado.x},${colocado.y})` });
  const esHoja = colocado.tipo === "hoja";
  const label = esHoja ? colocado.texto : colocado.label;

  if (esHoja) grupo.classList.add("hoja");
  if (!esHoja && label === "AGX") grupo.classList.add("agx");
  if (!esHoja && LABELS_DESTACADOS.has(label)) grupo.classList.add("destacado");
  if (!esHoja && esPeri(label)) grupo.classList.add("peri");
  if (esHoja) grupo.dataset.tokenIdx = colocado.tokenIdx;
  if (!esHoja) grupo.dataset.label = label;

  const anchoTexto = Math.max(LEAF_MIN_W, label.length * CHAR_W + 18);
  const rect = crearElemSVG("rect", {
    x: -anchoTexto / 2, y: -NODE_H / 2, width: anchoTexto, height: NODE_H, rx: 5,
  });
  const texto = crearElemSVG("text", { x: 0, y: 4, "text-anchor": "middle" });
  texto.textContent = label;

  grupo.appendChild(rect);
  grupo.appendChild(texto);
  if (!esHoja) {
    const tt = glosarioTooltipPara(label);
    if (tt) {
      const titulo = document.createElementNS(SVG_NS, "title");
      titulo.textContent = tt;
      grupo.appendChild(titulo);
    }
  }
  svg.appendChild(grupo);

  if (padreColocado) {
    const linea = crearElemSVG("line", {
      x1: padreColocado.x, y1: padreColocado.y + NODE_H / 2,
      x2: colocado.x, y2: colocado.y - NODE_H / 2,
      class: esPeri(label) ? "arbol-linea peri" : "arbol-linea",
    });
    svg.insertBefore(linea, svg.firstChild);
    // Convención de Van Valin (fallback 1ª iteración, ver docs/GUI.md): la
    // periferia se distingue por rama punteada + color; el ancla (el PADRE
    // del nodo -PERI: NUC/CORE/CLAUSE) se resalta con borde más grueso en
    // vez de una flecha curva lateral.
    if (esPeri(label) && padreColocado.tipo === "nodo") {
      padreColocado._esAncla = true;
    }
  }

  if (!esHoja) {
    colocado.hijos.forEach((h) => dibujarNodo(svg, h, colocado));
  }
  colocado._grupo = grupo;
  return grupo;
}

function marcarAnclas(colocado) {
  if (colocado._esAncla && colocado._grupo) colocado._grupo.classList.add("ancla-peri");
  if (colocado.hijos) colocado.hijos.forEach(marcarAnclas);
}

// ─── Etapa OPERATORS — proyección de operadores en espejo (fig. 5.2) ───────
// La proyección de operadores NO es parte del árbol de constituyentes: es una
// estructura APARTE, en espejo, que baja desde la V del predicado
// (V → NUC → CORE → CLAUSE → SENTENCE) y a la que se enganchan los operadores
// DETECTADOS por su estrato. Las dos proyecciones convergen visualmente SOLO
// en la V/NUC, como manda la teoría.
//
// Se dibuja en el MISMO <svg> que el árbol a propósito: así comparte sistema
// de coordenadas y la espina cae exactamente bajo la V (si viviera en otro
// SVG habría que replicar el layout y las dos vistas derivarían).
const ESPEJO_SEP = 40;      // hueco entre el fondo del árbol y la espina
const ESPEJO_GAP = 46;      // separación vertical entre estratos del espejo
const OP_OFFSET = 96;       // distancia horizontal de la espina a los operadores
const OP_SEP = 12;
const ESPINA = ["V", "NUC", "CORE", "CLAUSE", "SENTENCE"];
// A qué nodo de la espina se engancha cada estrato. La V no recibe
// operadores: es el punto de convergencia con la proyección de constituyentes.
const ESTRATO_A_NODO = { nuclear: "NUC", central: "CORE", clausular: "CLAUSE" };

function buscarNodoV(colocado) {
  if (colocado.tipo === "hoja") return null;
  if (colocado.label === "V") return colocado;
  for (const h of colocado.hijos || []) {
    const encontrado = buscarNodoV(h);
    if (encontrado) return encontrado;
  }
  return null;
}

function glosarioOperador(op) {
  // Coincidencia EXACTA de término primero: `glosarioTooltipPara` busca por
  // subcadena y "IF"/"MOD" son demasiado cortos para eso (matchearían
  // cualquier definición que los contenga).
  const exacto = estadoApp.glosario.find(
    (e) => normalizar(e.termino) === normalizar(op));
  return exacto ? exacto.definicion : glosarioTooltipPara(op);
}

function tooltipOperador(o) {
  const def = glosarioOperador(o.op);
  const señal = o.origen ? `\n\nSeñal: ${o.origen}` : "";
  return `${o.op} = ${o.valor}${def ? "\n\n" + def : ""}${señal}`;
}

// Espejo en JS de `operadores.etiqueta`: Van Valin escribe ⟨NEG …⟩, nunca
// ⟨NEG NEG …⟩ — cuando el valor repite el nombre del operador, se muestra
// solo el nombre. Lo usan por igual la caja del espejo y el marcado de la EL.
function etiquetaOperador(o) {
  return o.valor === o.op || !o.valor ? o.op : `${o.op} ${o.valor}`;
}

function anchoOperador(o) {
  return Math.max(LEAF_MIN_W, etiquetaOperador(o).length * CHAR_W + 18);
}

function dibujarProyeccionOperadores(svg, colocado, operadores, yBase) {
  const nodoV = buscarNodoV(colocado);
  if (!nodoV || !operadores || operadores.length === 0) return { alto: 0, ancho: 0 };

  const x = nodoV.x;
  const yDe = {};
  ESPINA.forEach((label, i) => { yDe[label] = yBase + i * ESPEJO_GAP; });

  // Convergencia con la proyección de constituyentes: la única línea que une
  // las dos estructuras, y va de la V real del árbol a la V del espejo.
  svg.appendChild(crearElemSVG("line", {
    x1: x, y1: nodoV.y + NODE_H / 2, x2: x, y2: yDe.V - NODE_H / 2,
    class: "espejo-convergencia",
  }));

  const anchoDe = {};
  ESPINA.forEach((label, i) => {
    if (i > 0) {
      svg.appendChild(crearElemSVG("line", {
        x1: x, y1: yDe[ESPINA[i - 1]] + NODE_H / 2,
        x2: x, y2: yDe[label] - NODE_H / 2, class: "espejo-linea",
      }));
    }
    const g = crearElemSVG("g", {
      class: "espejo-nodo", transform: `translate(${x},${yDe[label]})`,
    });
    g.dataset.estratoEspejo = label;
    const w = Math.max(LEAF_MIN_W, label.length * CHAR_W + 18);
    anchoDe[label] = w;
    g.appendChild(crearElemSVG("rect", {
      x: -w / 2, y: -NODE_H / 2, width: w, height: NODE_H, rx: 5,
    }));
    const t = crearElemSVG("text", { x: 0, y: 4, "text-anchor": "middle" });
    t.textContent = label;
    g.appendChild(t);
    const tt = glosarioTooltipPara(label);
    if (tt) {
      const titulo = document.createElementNS(SVG_NS, "title");
      titulo.textContent = tt;
      g.appendChild(titulo);
    }
    svg.appendChild(g);
  });

  // Operadores enganchados a su estrato. Los que comparten estrato se apilan
  // hacia la derecha en el orden de scope en que llegan del motor y se
  // ENCADENAN: el primero apunta al nodo de la espina y cada siguiente al
  // anterior. Si todos tiraran una línea hasta la espina, las líneas
  // atravesarían las cajas intermedias y tacharían sus etiquetas.
  const bordeDerechoPrevio = {};
  let anchoMax = 0;
  operadores.forEach((o) => {
    const nodo = ESTRATO_A_NODO[o.estrato];
    if (!nodo || yDe[nodo] === undefined) return;   // EVID/EVQ/DIR o estrato desconocido
    const w = anchoOperador(o);
    const previo = bordeDerechoPrevio[nodo];
    const xIzquierda = previo === undefined
      ? x + OP_OFFSET
      : previo + OP_SEP + 24;      // hueco visible para el conector
    const xOp = xIzquierda + w / 2;
    // destino de la flecha: el BORDE del nodo/caja anterior, nunca su centro
    const xDestino = previo === undefined ? x + anchoDe[nodo] / 2 : previo;
    bordeDerechoPrevio[nodo] = xOp + w / 2;
    anchoMax = Math.max(anchoMax, xOp + w / 2);

    svg.appendChild(crearElemSVG("line", {
      x1: xIzquierda, y1: yDe[nodo], x2: xDestino, y2: yDe[nodo],
      class: "espejo-flecha", "marker-end": "url(#flecha-op)",
    }));

    const g = crearElemSVG("g", {
      class: "op-nodo", transform: `translate(${xOp},${yDe[nodo]})`,
    });
    g.dataset.op = o.op;
    g.appendChild(crearElemSVG("rect", {
      x: -w / 2, y: -NODE_H / 2, width: w, height: NODE_H, rx: 5,
    }));
    const t = crearElemSVG("text", { x: 0, y: 4, "text-anchor": "middle" });
    t.textContent = etiquetaOperador(o);
    g.appendChild(t);
    const titulo = document.createElementNS(SVG_NS, "title");
    titulo.textContent = tooltipOperador(o);
    g.appendChild(titulo);
    svg.appendChild(g);
  });

  return { alto: (ESPINA.length - 1) * ESPEJO_GAP + ESPEJO_SEP + NODE_H,
           ancho: anchoMax };
}

function defsFlecha() {
  const defs = document.createElementNS(SVG_NS, "defs");
  const marker = crearElemSVG("marker", {
    id: "flecha-op", viewBox: "0 0 8 8", refX: 7, refY: 4,
    markerWidth: 6, markerHeight: 6, orient: "auto",
  });
  marker.appendChild(crearElemSVG("path", { d: "M 0 0 L 8 4 L 0 8 z", class: "punta-flecha" }));
  defs.appendChild(marker);
  return defs;
}

function dibujarArbolEnSvg(svg, arbolJson, tokens, operadores = null) {
  svg.innerHTML = "";
  if (!arbolJson) {
    svg.setAttribute("width", 0);
    svg.setAttribute("height", 0);
    return null;
  }
  let ancho = medir(arbolJson, tokens);
  const profundidad = profundidadMax(arbolJson);
  let alto = (profundidad + 1) * V_GAP + NODE_H;

  const colocado = ubicar(arbolJson, tokens, 0, 0);
  dibujarNodo(svg, colocado, null);
  marcarAnclas(colocado);

  if (operadores && operadores.length) {
    svg.appendChild(defsFlecha());
    const extra = dibujarProyeccionOperadores(
      svg, colocado, operadores, (profundidad + 1) * V_GAP + ESPEJO_SEP);
    alto += extra.alto;
    ancho = Math.max(ancho, extra.ancho + 20);
  }

  svg.setAttribute("width", ancho + 20);
  svg.setAttribute("height", alto + 10);
  svg.setAttribute("viewBox", `-10 -${NODE_H} ${ancho + 20} ${alto + 10}`);
  return colocado;
}

function renderArbol(sub) {
  const svg = $("#arbol-svg");
  const vacio = $("#arbol-vacio");
  const ops = estadoApp.mostrarOperadores ? (sub.operadores || []) : null;
  const colocado = dibujarArbolEnSvg(svg, sub.arbol, sub.tokens, ops);
  vacio.classList.toggle("oculto", !!colocado);
  if (!colocado) return;

  // hover en hojas → resalta EL/argumentos
  svg.querySelectorAll(".arbol-nodo.hoja").forEach((g) => {
    const idx = Number(g.dataset.tokenIdx);
    g.addEventListener("mouseenter", () => resaltarPorTokenIdx(idx, true));
    g.addEventListener("mouseleave", () => resaltarPorTokenIdx(idx, false));
  });

  // hover en un operador del espejo → resalta el MISMO operador en la EL
  // envuelta (resaltado cruzado bidireccional, igual que argumento↔constituyente)
  svg.querySelectorAll(".op-nodo").forEach((g) => {
    const op = g.dataset.op;
    g.addEventListener("mouseenter", () => resaltarPorOperador(op, true));
    g.addEventListener("mouseleave", () => resaltarPorOperador(op, false));
  });
}

// ─── EL léxica / formal (con hover bidireccional en x/y/z) ──────────────────
function escapeHTML(s) {
  return (s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// Etapa OPERATORS: envuelve en <span> cada etiqueta de operador de una EL ya
// escapada (`⟨IF INT ⟨TNS PRES ⟨…`), para poder resaltarla y darle tooltip.
// Se recorre la lista en ORDEN DE SCOPE y se reemplaza la PRIMERA aparición
// de cada etiqueta: es exactamente el orden en que `envolver_ls` las escribió,
// así que cada reemplazo cae en su propia capa.
function marcarOperadoresEnEL(html, operadores) {
  (operadores || []).forEach((o) => {
    const etiqueta = etiquetaOperador(o);
    const buscado = `⟨${etiqueta} `;
    const i = html.indexOf(buscado);
    if (i === -1) return;
    const span = `⟨<span class="op-el" data-op="${o.op}" title="${escapeHTML(tooltipOperador(o))}">` +
      `${escapeHTML(etiqueta)}</span> `;
    html = html.slice(0, i) + span + html.slice(i + buscado.length);
  });
  return html;
}

function conectarHoverOperadores(contenedor, sub) {
  contenedor.querySelectorAll(".op-el").forEach((span) => {
    const op = span.dataset.op;
    span.addEventListener("mouseenter", () => resaltarPorOperador(op, true));
    span.addEventListener("mouseleave", () => resaltarPorOperador(op, false));
  });
}

// Resaltado cruzado EL ↔ nodo del espejo (mismo patrón bidireccional que ya
// usa la GUI para argumento↔constituyente).
function resaltarPorOperador(op, on) {
  document.querySelectorAll(`.op-el[data-op="${op}"]`).forEach(
    (e) => e.classList.toggle("resaltado", on));
  document.querySelectorAll(`.op-nodo[data-op="${op}"]`).forEach(
    (e) => e.classList.toggle("resaltado", on));
}

function renderEL(sub) {
  // Se muestran las EL ENVUELTAS (`*_ops`): con los operadores, esa es la
  // representación RRG completa. Las crudas siguen en `sub.el.formal/lexical`
  // para el bucle de corrección, que no ha cambiado.
  const ops = sub.operadores || [];
  const lexicaHTML = marcarOperadoresEnEL(
    escapeHTML(sub.el.lexical_ops || sub.el.lexical || ""), ops);
  const contLexica = $("#el-lexica");
  contLexica.innerHTML = lexicaHTML;
  conectarHoverOperadores(contLexica, sub);

  // Solo variables argumentales completas; nunca letras dentro de palabras.
  const formalHTML = marcarOperadoresEnEL(
    escapeHTML(sub.el.formal_ops || sub.el.formal || "").replace(
      /(?<![\p{L}\p{N}_])([xyz])(?![\p{L}\p{N}_])/gu,
      (m, v) => `<span class="var-el" data-var="${v}">${v}</span>`
    ), ops);
  const contenedor = $("#el-formal");
  contenedor.innerHTML = formalHTML;
  conectarHoverOperadores(contenedor, sub);
  const argPorVar = {};
  (sub.argumentos || []).forEach((a) => { argPorVar[a.var] = a; });
  contenedor.querySelectorAll(".var-el").forEach((span) => {
    const v = span.dataset.var;
    const arg = argPorVar[v];
    span.addEventListener("mouseenter", () => {
      resaltarPorVar(v, true);
      if (arg && arg.token_id != null) resaltarPorTokenIdx(arg.token_id - 1, true);
      else if (arg) resaltarMorfologico(sub, true);
    });
    span.addEventListener("mouseleave", () => {
      resaltarPorVar(v, false);
      if (arg && arg.token_id != null) resaltarPorTokenIdx(arg.token_id - 1, false);
      else if (arg) resaltarMorfologico(sub, false);
    });
  });
}

function renderTipo(sub) {
  $("#badge-tipo").textContent = sub.el.tipo_legible || sub.el.tipo || "";
  const metodo = (sub.rasgos && sub.rasgos.metodo) ? `método: ${sub.rasgos.metodo}` +
    ` (confianza ${formatearConfianza(sub.rasgos.confianza)})` : "";
  $("#badge-metodo").textContent = metodo;
  $("#badge-metodo").classList.toggle("oculto", !metodo);
}

// ─── Argumentos ───────────────────────────────────────────────────────────
function renderArgumentos(sub) {
  const tbody = $("#tabla-argumentos tbody");
  tbody.innerHTML = "";
  estadoApp.tokenIdxAVar = {};
  (sub.argumentos || []).forEach((a) => {
    if (a.token_id != null) estadoApp.tokenIdxAVar[a.token_id - 1] = a.var;
    const tr = document.createElement("tr");
    tr.dataset.var = a.var;
    if (a.token_id != null) tr.dataset.tokenIdx = a.token_id - 1;
    else tr.dataset.morfologico = "1";
    tr.innerHTML = `<td>${escapeHTML(a.var)}</td>` +
      `<td>${escapeHTML(a.texto || "")}${a.token_id == null ? ' <em>(morfológico)</em>' : ""}</td>` +
      `<td>${escapeHTML(a.deprel || "—")}</td>` +
      `<td>${escapeHTML(a.papel || "—")}</td>`;
    tr.addEventListener("mouseenter", () => {
      resaltarPorVar(a.var, true);
      if (a.token_id != null) resaltarPorTokenIdx(a.token_id - 1, true);
      else resaltarMorfologico(sub, true);
    });
    tr.addEventListener("mouseleave", () => {
      resaltarPorVar(a.var, false);
      if (a.token_id != null) resaltarPorTokenIdx(a.token_id - 1, false);
      else resaltarMorfologico(sub, false);
    });
    tbody.appendChild(tr);
  });
}

function resaltarMorfologico(sub, on) {
  const svg = $("#arbol-svg");
  const tieneAgx = (sub.agx || []).length > 0;
  const label = tieneAgx ? "AGX" : "NUC";
  svg.querySelectorAll(".arbol-nodo").forEach((g) => {
    if (g.dataset.label === label) g.classList.toggle("resaltado", on);
  });
}

// ─── resaltado cruzado (hoja <-> var <-> fila de argumento) ─────────────────
function resaltarPorTokenIdx(idx, on) {
  $("#arbol-svg").querySelectorAll(`.arbol-nodo.hoja[data-token-idx="${idx}"]`)
    .forEach((g) => g.classList.toggle("resaltado", on));
  document.querySelectorAll(`#tabla-argumentos tr[data-token-idx="${idx}"]`)
    .forEach((tr) => tr.classList.toggle("resaltado", on));
  const v = estadoApp.tokenIdxAVar[idx];
  if (v) document.querySelectorAll(`.var-el[data-var="${v}"]`)
    .forEach((s) => s.classList.toggle("resaltado", on));
}

function resaltarPorVar(v, on) {
  document.querySelectorAll(`.var-el[data-var="${v}"]`)
    .forEach((s) => s.classList.toggle("resaltado", on));
  document.querySelectorAll(`#tabla-argumentos tr[data-var="${v}"]`)
    .forEach((tr) => tr.classList.toggle("resaltado", on));
}

// ─── Rasgos (barras 0-1) ────────────────────────────────────────────────────
// G3 §0 (fix visual, veredicto de Julian): etiqueta+valor JUNTOS y el riel
// COMPLETO siempre visible (fondo propio) para que el relleno proporcional
// se lea como "% lleno de la escala 0.00-1.00", nunca como espacio muerto.
// Única función que construye una fila -- la comparte cualquier otro lugar
// que dibuje barras de rasgos (nada duplicado).
function filaBarraRasgo(etiqueta, valor, clave) {
  const numero = confianzaNumerica(valor);
  const v = numero == null ? 0 : numero;
  const fila = document.createElement("div");
  fila.className = "barra-rasgo";
  fila.innerHTML =
    `<span class="nombre" data-tooltip="${etiqueta}">${etiqueta} ` +
    `<span class="valor-inline">${v.toFixed(2)}</span></span>` +
    `<span class="pista"><span class="relleno relleno-${clave}" style="width:${Math.round(v * 100)}%"></span></span>`;
  return fila;
}

function renderRasgos(sub) {
  const cont = $("#rasgos");
  cont.innerHTML = "";
  if (!sub.rasgos) {
    cont.innerHTML = '<p class="aviso">(sin vector aspectual)</p>';
    return;
  }
  const nombres = [["estatico", "estático"], ["dinamico", "dinámico"],
                   ["telico", "télico"], ["puntual", "puntual"]];
  nombres.forEach(([clave, etiqueta]) => {
    cont.appendChild(filaBarraRasgo(etiqueta, sub.rasgos[clave], clave));
  });
  if (sub.rasgos.confianza != null) {
    cont.appendChild(filaBarraRasgo("confianza", sub.rasgos.confianza, "confianza"));
  }
}

// ─── Integridad (chips) ─────────────────────────────────────────────────────
function renderIntegridad(sub) {
  const cont = $("#integridad");
  cont.innerHTML = "";
  const integridad = sub.integridad || {};
  if (integridad.ok === null) {
    cont.innerHTML = '<span class="chip sin_arbol">sin árbol — la oración no se convirtió</span>';
    return;
  }
  const checks = integridad.checks || [];
  if (checks.length === 0) {
    const chip = document.createElement("span");
    chip.className = `chip ${integridad.ok ? "ok" : "falta_en_arbol"}`;
    chip.textContent = integridad.ok ? "✓ integridad completa" : "⚠ ver detalle";
    cont.appendChild(chip);
    return;
  }
  checks.forEach((c) => {
    const chip = document.createElement("span");
    chip.className = `chip ${c.estado}`;
    chip.textContent = `${c.elemento}: ${c.detalle}`;
    cont.appendChild(chip);
  });
  if (integridad.ok === false) {
    const hint = document.createElement("div");
    hint.className = "hint-corregir";
    hint.textContent = "¿Análisis incorrecto? Corrígelo aquí";
    hint.addEventListener("click", abrirModalCorregir);
    cont.appendChild(hint);
  }
}

// ─── Causatividad ────────────────────────────────────────────────────────
function renderCausatividad(sub) {
  const bloque = $("#causatividad-bloque");
  if (!sub.causatividad) { bloque.classList.add("oculto"); return; }
  bloque.classList.remove("oculto");
  const c = sub.causatividad;
  const nivel = c.nivel_confianza ? `, nivel ${c.nivel_confianza}` : "";
  $("#causatividad").textContent =
    `${c.tipo || "—"} (${c.fuente || "—"}, confianza ${formatearConfianza(c.confianza)}${nivel})`;
}

// ─── Fase LINKING, Etapa LA1 — línea compacta + traza de 5 pasos ───────────
// Términos que se resaltan con hover→glosario dentro del texto de la traza
// (orden: más largos primero, para que "M-transitivo" no quede partido por
// una coincidencia parcial de otro término más corto).
const TERMINOS_LINKING = ["M-transitivo", "concordancia", "Undergoer", "nominativo",
  "acusativo", "atransitivo", "oblicuo", "Actor", "dativo", "NMR", "PSA", "AGX", "LDP"];

function resaltarTerminosLinking(texto) {
  let html = escapeHTML(texto);
  TERMINOS_LINKING.forEach((term) => {
    const def = glosarioTooltipPara(term);
    if (!def) return;
    // Evita volver a envolver texto ya dentro de un <span> (p.ej. "Actor"
    // dentro de "concordancia" ya resaltada) buscando solo fuera de tags.
    const re = new RegExp(`\\b${term}\\b(?![^<]*>)`, "g");
    html = html.replace(re,
      `<span class="linking-term" title="${escapeHTML(def)}">${term}</span>`);
  });
  return html;
}

function renderLinking(sub) {
  const bloque = $("#linking-bloque");
  const info = sub.linking;
  if (!info) { bloque.classList.add("oculto"); return; }
  bloque.classList.remove("oculto");
  $("#linking-linea").innerHTML = resaltarTerminosLinking(info.linea || "");
  const ol = $("#linking-traza");
  ol.innerHTML = "";
  (info.traza || []).forEach((paso) => {
    const li = document.createElement("li");
    // Los pasos ya vienen con el prefijo "Paso N — ..."; se recorta para
    // que el número lo aporte el propio <ol> (evita "1. Paso 1 — ...").
    const texto = paso.replace(/^Paso\s+\d+\s+—\s+/, "");
    li.innerHTML = resaltarTerminosLinking(texto);
    ol.appendChild(li);
  });
}

// ─── Notas ───────────────────────────────────────────────────────────────
function renderNotas(sub) {
  const bloque = $("#notas-bloque");
  const ul = $("#notas");
  ul.innerHTML = "";
  const notas = sub.notas || [];
  if (notas.length === 0) { bloque.classList.add("oculto"); return; }
  bloque.classList.remove("oculto");
  notas.forEach((n) => {
    const li = document.createElement("li");
    li.textContent = n;
    ul.appendChild(li);
  });
}

// ─── detalle técnico (--verbose) ────────────────────────────────────────────
function renderCrudo(sub) {
  $("#crudo-morph").textContent = (sub.crudo && sub.crudo.morph_note) || "";
  $("#crudo-completeness").textContent = (sub.crudo && sub.crudo.resumen_completeness) || "";
}

$("#toggle-verbose").addEventListener("change", (ev) => {
  estadoApp.verbose = ev.target.checked;
  $("#crudo").classList.toggle("oculto", !estadoApp.verbose);
});

// Etapa OPERATORS: la proyección se dibuja dentro del mismo SVG del árbol,
// así que alternarla es redibujar la (sub)oración actual.
$("#toggle-operadores").addEventListener("change", (ev) => {
  estadoApp.mostrarOperadores = ev.target.checked;
  const res = estadoApp.resultadoActual;
  const sub = res && res.sub_oraciones && res.sub_oraciones[estadoApp.subIdxActual];
  if (sub) renderArbol(sub);
});

// ═══════════════════════════════ glosario ═══════════════════════════════════
function normalizar(s) {
  return (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

async function cargarGlosario() {
  try {
    const r = await fetch(`${API}/glosario`);
    estadoApp.glosario = await r.json();
    try {
      const cr = await fetch(`${API}/contrato/gui`);
      if (cr.ok) estadoApp.contratoGui = await cr.json();
    } catch (e) { /* contrato opcional durante arranque offline */ }
    renderListaGlosario(estadoApp.glosario);
  } catch (e) { /* glosario opcional: la GUI sigue funcionando sin él */ }
}

function renderListaGlosario(entradas) {
  const cont = $("#lista-glosario");
  cont.innerHTML = "";
  entradas.forEach((e) => {
    const div = document.createElement("div");
    div.className = "entrada-glosario";
    div.innerHTML = `<div class="termino">${escapeHTML(e.termino)}</div>` +
      `<div class="categoria">${escapeHTML(e.categoria)}</div>` +
      `<div class="definicion">${escapeHTML(e.definicion)}</div>`;
    cont.appendChild(div);
  });
}

$("#buscar-glosario").addEventListener("input", (ev) => {
  const q = normalizar(ev.target.value);
  if (!q) { renderListaGlosario(estadoApp.glosario); return; }
  renderListaGlosario(estadoApp.glosario.filter((e) => normalizar(e.termino).includes(q)));
});

$("#btn-toggle-glosario").addEventListener("click", () => {
  const c = $("#glosario-contenido");
  const colapsado = c.classList.toggle("oculto");
  $("#btn-toggle-glosario").textContent = colapsado ? "▸" : "▾";
});

// término técnico -> primera definición que matchea tolerante (para tooltips
// del árbol: AGX, PrDP/LDP, -PERI, NUC/CORE/CLAUSE, etc.)
function glosarioTooltipPara(label) {
  if (!label) return null;
  const mapa = estadoApp.contratoGui.tooltips || {};
  // Las etiquetas de árbol solo admiten claves canónicas exactas. Las
  // definiciones siguen viniendo del CSV; nunca se usa includes aquí.
  if (esPeri(label)) {
    const ancla = label.slice(0, -5);
    const termino = (estadoApp.contratoGui.peri || {})[ancla] || `PERI@${ancla}`;
    const p = estadoApp.glosario.find((e) => normalizar(e.termino) === normalizar(termino));
    return p ? p.definicion : null;
  }
  const buscar = mapa[label];
  if (!buscar) return null;
  const encontrado = estadoApp.glosario.find((e) => normalizar(e.termino) === normalizar(buscar));
  return encontrado ? encontrado.definicion : null;
}

// ═══════════════════════ G2 §3 — bucle de corrección ════════════════════════
// Espejo en JS de las constantes de `aspect_classifier/correccion.py`
// (CLASES/CLASE_ES y _DESTINOS_ENRUTADO) -- no hay endpoint que las
// exponga; son 6 valores fijos de la teoría RRG, no datos del usuario.
const CLASES_ASPECTUALES = [
  ["state", "Estado (state)"], ["activity", "Actividad (activity)"],
  ["accomplishment", "Realización (accomplishment)"],
  ["achievement", "Logro (achievement)"],
  ["semelfactive", "Semelfactivo (semelfactive)"],
  ["active_accomplishment", "Realización activa (active_accomplishment)"],
];
const DESTINOS_ENRUTADO = [
  ["argumento_core", "argumento del core"], ["periferia_temporal", "periferia temporal"],
  ["periferia_locativo", "periferia locativa"], ["periferia_modo", "periferia de modo"],
  ["ldp", "posición destacada (LDP)"], ["agx", "clítico de concordancia (AGX)"],
];
const PALETA_EL = ["do'", "CAUSE", "BECOME", "INGR", "SEML", "PURP", "have'", "Ø", "[ ]"];
// Espejo de `PLANTILLA_A_CLASE` (aspect_classifier/correccion.py, G3 §2.3):
// plantilla reconocida por la validación en vivo -> clase sugerida.
const PLANTILLA_A_CLASE = {
  state: "state", activity: "activity", accomplishment: "accomplishment",
  achievement: "achievement", semelfactive: "semelfactive",
  causativa: "accomplishment", ditrans_transferencia: "accomplishment",
  ditrans_benefactiva: "accomplishment", ditrans_comunicacion: "accomplishment",
};
const CLASE_ES_POR_VALOR = Object.fromEntries(CLASES_ASPECTUALES);
let _claseElManual = false;

function subEnEdicion() {
  return estadoApp.resultadoActual.sub_oraciones[estadoApp.corregirCtx.sub_idx];
}

async function postJSON(ruta, cuerpo) {
  const r = await fetch(`${API}${ruta}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(j.detail || `HTTP ${r.status}`), { status: r.status });
  return j;
}

// ─── abrir / cerrar / pestañas ───────────────────────────────────────────
function abrirModalCorregir() {
  if (!estadoApp.resultadoActual) return;
  const aid = estadoApp.resultadoActual.analisis_id;
  if (!aid) {
    mensajeEstado.classList.add("error");
    mensajeEstado.textContent = "Este análisis no tiene id (¿vino de un fixture?) — no se puede corregir.";
    return;
  }
  estadoApp.corregirCtx = { analisis_id: aid, sub_idx: estadoApp.subIdxActual };
  estadoApp.elementoEnrutado = null;
  const sub = subEnEdicion();

  poblarSelectClase();
  $("#resultado-clase").classList.add("oculto");

  $("#editor-el").value = (sub.el && sub.el.lexical) || "";
  $("#validacion-el").textContent = "";
  $("#validacion-el").className = "validacion-el";
  $("#btn-aplicar-el").disabled = true;
  construirPaletaEl();
  _claseElManual = false;
  poblarSelectClaseEl();
  $("#clase-el-sugerencia").textContent = "";

  construirListaEnrutado(sub);
  $("#enrutado-destino-bloque").classList.add("oculto");

  construirListaOperadores(sub);
  $("#operador-accion-bloque").classList.add("oculto");

  $("#diff-corregir").classList.add("oculto");
  cambiarTabCorregir("clase");
  $("#modal-corregir").classList.remove("oculto");
}

function cerrarModalCorregir() {
  $("#modal-corregir").classList.add("oculto");
}

$("#btn-cerrar-corregir").addEventListener("click", cerrarModalCorregir);
$("#modal-corregir").addEventListener("click", (ev) => {
  if (ev.target.id === "modal-corregir") cerrarModalCorregir();   // clic fuera del panel
});

function cambiarTabCorregir(nombre) {
  document.querySelectorAll(".tab-corregir").forEach(
    (b) => b.classList.toggle("activa", b.dataset.tab === nombre));
  document.querySelectorAll(".panel-tab").forEach(
    (s) => s.classList.toggle("oculto", s.id !== `tab-${nombre}`));
  $("#diff-corregir").classList.add("oculto");
}
document.querySelectorAll(".tab-corregir").forEach((b) => {
  b.addEventListener("click", () => cambiarTabCorregir(b.dataset.tab));
});

// ─── pestaña Clase ────────────────────────────────────────────────────────
function poblarSelectClase() {
  const sel = $("#select-clase");
  sel.innerHTML = "";
  CLASES_ASPECTUALES.forEach(([valor, etiqueta]) => {
    const op = document.createElement("option");
    op.value = valor; op.textContent = etiqueta;
    sel.appendChild(op);
  });
}

$("#btn-aplicar-clase").addEventListener("click", async () => {
  const boton = $("#btn-aplicar-clase");
  boton.disabled = true;
  try {
    const { analisis_id, sub_idx } = estadoApp.corregirCtx;
    const clase = $("#select-clase").value;
    await postJSON("/corregir/clase", { analisis_id, sub_idx, clase });
    const banner = $("#resultado-clase");
    banner.className = "banner ambar";
    banner.textContent = "registrada en STAGING — el clasificador no se toca; "
      + "el curador la promueve a mano.";
    banner.classList.remove("oculto");
  } catch (e) {
    const banner = $("#resultado-clase");
    banner.className = "banner rojo";
    banner.textContent = `Error: ${e.message}`;
    banner.classList.remove("oculto");
  } finally {
    boton.disabled = false;
  }
});

// ─── pestaña Estructura Lógica (validación en vivo, debounce ~400ms) ──────
function construirPaletaEl() {
  const cont = $("#paleta-el");
  cont.innerHTML = "";
  PALETA_EL.forEach((tok) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = tok;
    b.addEventListener("click", () => insertarEnEditorEl(tok));
    cont.appendChild(b);
  });
}

function insertarEnEditorEl(txt) {
  const ta = $("#editor-el");
  const ini = ta.selectionStart ?? ta.value.length;
  const fin = ta.selectionEnd ?? ta.value.length;
  ta.value = ta.value.slice(0, ini) + txt + ta.value.slice(fin);
  ta.focus();
  ta.selectionStart = ta.selectionEnd = ini + txt.length;
  ta.dispatchEvent(new Event("input", { bubbles: true }));
}

// ─── G3 §2.3 — dropdown "Clase aspectual" de la pestaña Estructura Lógica ──
function poblarSelectClaseEl() {
  const sel = $("#select-clase-el");
  sel.innerHTML = "";
  const op0 = document.createElement("option");
  op0.value = "";
  op0.textContent = "(no cambiar)";
  sel.appendChild(op0);
  CLASES_ASPECTUALES.forEach(([valor, etiqueta]) => {
    const op = document.createElement("option");
    op.value = valor;
    op.textContent = etiqueta;
    sel.appendChild(op);
  });
}

$("#select-clase-el").addEventListener("change", () => { _claseElManual = true; });

// Llamada tras cada validación en vivo exitosa: sugiere la clase de la
// plantilla reconocida SIN pisar una elección manual del usuario (el
// listener de "change" de arriba solo se dispara con interacción real).
function sugerirClasePorPlantilla(plantilla) {
  const sugerida = PLANTILLA_A_CLASE[plantilla] || null;
  const hint = $("#clase-el-sugerencia");
  hint.textContent = sugerida ? `(la plantilla sugiere: ${CLASE_ES_POR_VALOR[sugerida]})` : "";
  if (!_claseElManual) $("#select-clase-el").value = sugerida || "";
}

let _debounceElTimer = null;
$("#editor-el").addEventListener("input", () => {
  $("#btn-aplicar-el").disabled = true;
  const div = $("#validacion-el");
  div.className = "validacion-el";
  div.textContent = "";
  clearTimeout(_debounceElTimer);
  _debounceElTimer = setTimeout(validarElEnVivo, 400);
});

async function validarElEnVivo() {
  const el = $("#editor-el").value.trim();
  const div = $("#validacion-el");
  if (!el) { div.className = "validacion-el"; div.textContent = ""; return; }
  const { analisis_id, sub_idx } = estadoApp.corregirCtx;
  try {
    const j = await postJSON("/corregir/validar-el", { analisis_id, sub_idx, el });
    if (j.ok) {
      div.className = "validacion-el ok";
      const spec = j.especificacion || {};
      const detalle = spec.subtipo_benefactivo
        ? ` · ${spec.subtipo_benefactivo}${spec.predicado_resultado ? ` · ${spec.predicado_resultado}` : ""}`
        : "";
      div.textContent = `✓ plantilla reconocida: ${j.plantilla}${detalle}`;
      $("#btn-aplicar-el").disabled = false;
      if (j.clase_sugerida && !_claseElManual) {
        $("#select-clase-el").value = j.clase_sugerida;
        $("#clase-el-sugerencia").textContent =
          `(la plantilla sugiere: ${CLASE_ES_POR_VALOR[j.clase_sugerida]})`;
      } else sugerirClasePorPlantilla(j.plantilla);
    } else {
      div.className = "validacion-el error";
      div.textContent = `✗ (nivel ${j.nivel}): ${j.error}`;
      $("#btn-aplicar-el").disabled = true;
      $("#clase-el-sugerencia").textContent = "";
    }
  } catch (e) {
    div.className = "validacion-el error";
    div.textContent = `Error: ${e.message}`;
    $("#btn-aplicar-el").disabled = true;
  }
}

$("#btn-aplicar-el").addEventListener("click", async () => {
  const boton = $("#btn-aplicar-el");
  boton.disabled = true;
  boton.textContent = "aplicando…";
  try {
    const { analisis_id, sub_idx } = estadoApp.corregirCtx;
    const el = $("#editor-el").value.trim();
    const clase = $("#select-clase-el").value;
    // G3 §2: con una clase elegida (sugerida o manual), EL + clase se
    // corrigen en UN solo paso (/corregir/todo, un solo re-análisis
    // compartido); "(no cambiar)" deja el flujo idéntico a G2.
    const j = clase
      ? await postJSON("/corregir/todo", { analisis_id, sub_idx, el, clase })
      : await postJSON("/corregir/el", { analisis_id, sub_idx, el });
    mostrarDiffCorreccion(j);
  } catch (e) {
    mostrarDiffCorreccion({ accion: "error", detalle: { error: e.message }, analisis_nuevo: null });
  } finally {
    boton.textContent = "Aplicar";
    boton.disabled = false;
  }
});

// ─── pestaña Enrutado ──────────────────────────────────────────────────────
function construirListaEnrutado(sub) {
  const ul = $("#lista-enrutado-elementos");
  ul.innerHTML = "";
  const rutas = sub.inventario_enrutado || [];
  estadoApp.rutasEnrutado = rutas;
  rutas.forEach((ruta) => {
    const cab = document.createElement("li");
    cab.className = "enrutado-categoria";
    cab.textContent = `${ruta.etiqueta}${ruta.automatizacion === "solo_staging" ? " · solo staging" : ""}`;
    ul.appendChild(cab);
    const instancias = ruta.instancias && ruta.instancias.length
      ? ruta.instancias : [{ elemento_id: null, texto: "(ausente)" }];
    instancias.forEach((inst) => {
      const it = { id: inst.elemento_id, texto: inst.texto || "(ausente)",
        ruta_origen: ruta.clave,
        donde: `${ruta.etiqueta}${inst.elemento_id == null ? " · ausente" : ""}` };
    const li = document.createElement("li");
    li.className = inst.elemento_id == null ? "ausente" : "";
    li.textContent = `"${it.texto}" (hoy: ${it.donde})`;
    li.addEventListener("click", () => {
      estadoApp.elementoEnrutado = it;
      [...ul.children].forEach((c) => c.classList.remove("seleccionado"));
      li.classList.add("seleccionado");
      poblarSelectDestino();
      $("#enrutado-destino-bloque").classList.remove("oculto");
    });
    ul.appendChild(li);
    });
  });
}

function poblarSelectDestino() {
  const sel = $("#select-destino");
  sel.innerHTML = "";
  const rutas = estadoApp.rutasEnrutado.length ? estadoApp.rutasEnrutado :
    DESTINOS_ENRUTADO.map(([clave, etiqueta]) => ({ clave, etiqueta }));
  rutas.forEach((ruta) => {
    const op = document.createElement("option");
    op.value = ruta.clave; op.textContent = ruta.etiqueta;
    sel.appendChild(op);
  });
}

$("#btn-aplicar-enrutado").addEventListener("click", async () => {
  if (!estadoApp.elementoEnrutado) return;
  const boton = $("#btn-aplicar-enrutado");
  boton.disabled = true;
  boton.textContent = "aplicando…";
  try {
    const { analisis_id, sub_idx } = estadoApp.corregirCtx;
    const destino = $("#select-destino").value;
    const j = await postJSON("/corregir/enrutado", {
      analisis_id, sub_idx, elemento_id: estadoApp.elementoEnrutado.id,
      ruta_origen: estadoApp.elementoEnrutado.ruta_origen,
      ruta_destino: destino,
    });
    mostrarDiffCorreccion(j);
  } catch (e) {
    mostrarDiffCorreccion({ accion: "error", detalle: { error: e.message }, analisis_nuevo: null });
  } finally {
    boton.textContent = "Aplicar";
    boton.disabled = false;
  }
});

// ─── OPERATORS_2 §2 — corrección de operadores ──────────────────────────────
// Espejo en JS de `correccion.VALORES_OPERADOR`: los valores que la teoría
// admite para cada operador (Van Valin 2.25). No es texto libre.
const VALORES_OPERADOR = {
  IF: ["DEC", "INT", "IMP"],
  TNS: ["PAST", "PRES", "FUT"],
  ASP: ["PERF", "PROG", "IMPF", "PERF PROG", "PERF IMPF", "PROG IMPF"],
  NEG: ["NEG"],
  MOD: ["OBLG", "ABIL"],
  STA: ["IRR", "REAL"],
};

function construirListaOperadores(sub) {
  const ul = $("#lista-operadores");
  ul.innerHTML = "";
  const detectados = sub.operadores || [];
  const presentes = new Set(detectados.map((o) => o.op));
  const items = [
    ...detectados.map((o) => ({
      op: o.op, presente: true,
      etiqueta: `${o.op} = ${o.valor}`, detalle: o.origen })),
    ...Object.keys(VALORES_OPERADOR).filter((op) => !presentes.has(op)).map((op) => ({
      op, presente: false, etiqueta: `${op} (ausente)`, detalle: "añadir este operador" })),
  ];
  items.forEach((it) => {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${escapeHTML(it.etiqueta)}</strong> — ` +
      `<span class="aviso-inline">${escapeHTML(it.detalle || "")}</span>`;
    li.addEventListener("click", () => {
      estadoApp.operadorEnEdicion = it;
      [...ul.children].forEach((c) => c.classList.remove("seleccionado"));
      li.classList.add("seleccionado");
      // "Quitar" solo tiene sentido en un operador que SÍ está.
      const selAccion = $("#select-operador-accion");
      selAccion.value = it.presente ? "cambiar" : "anadir";
      selAccion.querySelector('option[value="quitar"]').disabled = !it.presente;
      selAccion.querySelector('option[value="cambiar"]').textContent =
        it.presente ? "Cambiar su valor" : "Añadirlo con este valor";
      poblarSelectValorOperador(it.op);
      $("#operador-accion-bloque").classList.remove("oculto");
    });
    ul.appendChild(li);
  });
}

function poblarSelectValorOperador(op) {
  const sel = $("#select-operador-valor");
  sel.innerHTML = "";
  (VALORES_OPERADOR[op] || []).forEach((v) => {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = v;
    sel.appendChild(o);
  });
  sel.disabled = $("#select-operador-accion").value === "quitar";
}

$("#select-operador-accion").addEventListener("change", (ev) => {
  $("#select-operador-valor").disabled = ev.target.value === "quitar";
});

$("#btn-aplicar-operador").addEventListener("click", async () => {
  const it = estadoApp.operadorEnEdicion;
  if (!it) return;
  const boton = $("#btn-aplicar-operador");
  boton.disabled = true;
  boton.textContent = "aplicando…";
  try {
    const { analisis_id, sub_idx } = estadoApp.corregirCtx;
    const accion = $("#select-operador-accion").value;
    const j = await postJSON("/corregir/operador", {
      analisis_id, sub_idx, operador: it.op, accion,
      valor: accion === "quitar" ? null : $("#select-operador-valor").value,
    });
    mostrarDiffCorreccion(j);
  } catch (e) {
    mostrarDiffCorreccion({ accion: "error", detalle: { error: e.message }, analisis_nuevo: null });
  } finally {
    boton.textContent = "Aplicar";
    boton.disabled = false;
  }
});

// ─── diff confirmatorio (antes/después) ─────────────────────────────────────
const _BANNER_POR_ACCION = {
  persistido: ["verde", (d) => `✓ Corrección aplicada y verificada → «${_archivoLegible(d)}»`],
  insert: ["verde", (d) => `✓ Conocimiento añadido y verificado → «${_archivoLegible(d)}»`],
  update: ["verde", (d) => `✓ Conocimiento actualizado y verificado → «${_archivoLegible(d)}»`],
  "no-op": ["verde", (d) => `✓ Conocimiento ya vigente; verificación exacta superada → «${_archivoLegible(d)}»`],
  staging_conflicto: ["ambar", (d) =>
    `⚠ Lectura conflictiva enviada a staging: ${d.motivo || "falta discriminador suficiente"}.`],
  persistido_enrutado: ["verde", (d) => `✓ Corrección aplicada y verificada → «${_archivoLegible(d)}»`],
  staging_no_confirmado: ["ambar", () =>
    "⚠ Registrada para revisión (staging) — el análisis aún no la refleja."],
  staging_no_confirmado_enrutado: ["ambar", () =>
    "⚠ Registrada para revisión (staging) — el análisis aún no la refleja."],
  staging_clase: ["ambar", () => "registrada en STAGING — el curador la revisa a mano."],
  staging_el: ["ambar", () => "registrada en STAGING (implica una clase aspectual) — "
    + "el curador la revisa a mano."],
  staging_enrutado: ["ambar", () =>
    "⚠ registrada para revisión — esta corrección aún no puede automatizarse."],
  persistido_operador: ["verde", (d) => `✓ Corrección aplicada y verificada → «${_archivoLegible(d)}»`],
  staging_no_confirmado_operador: ["ambar", () =>
    "⚠ Registrada para revisión (staging) — el análisis aún no la refleja."],
  staging_operador: ["ambar", () =>
    "⚠ registrada para revisión — viene del análisis morfológico, no de un léxico, "
    + "así que todavía no puede automatizarse."],
  staging_lema_no_identificable: ["ambar", () =>
    "⚠ lema no identificable — se protegió el léxico vivo; queda en STAGING para revisión manual."],
  rechazado: ["rojo", (d) => `✗ Rechazada (nivel ${d.nivel}): ${d.error}`],
  cancelado: ["gris", (d) => d.error ? `Cancelado: ${d.error}` : "Cancelado, sin efectos."],
  error: ["rojo", (d) => `Error: ${d.error}`],
};

function _archivoLegible(detalle) {
  if (detalle.archivo) return detalle.archivo.split("/").pop();
  if (detalle.destino) return `config.yaml (${detalle.destino})`;
  return "—";
}

// G3 §2 — `/corregir/todo` devuelve una `accion` COMPUESTA
// ("<accion_clase>+<accion_el>", ver correccion.corregir_todo) con
// `detalle.clase_resultado`/`detalle.el_resultado`. Se arma un banner que
// muestra ambos resultados; el tono/color sigue al componente EL (la clase
// SIEMPRE es la misma staging no-sorpresa).
function bannerParaAccion(j) {
  const accion = j.accion || "";
  const detalle = j.detalle || {};
  if (accion.includes("+")) {
    const [accionClase, accionEl] = accion.split("+");
    const [, fnClase] = _BANNER_POR_ACCION[accionClase] || ["gris", () => accionClase];
    const [colorEl, fnEl] = _BANNER_POR_ACCION[accionEl] || ["gris", () => accionEl];
    const txtClase = fnClase(detalle.clase_resultado || {});
    const txtEl = fnEl(detalle.el_resultado || {});
    return [colorEl, `Clase → ${txtClase}  |  EL → ${txtEl}`];
  }
  const [color, fn] = _BANNER_POR_ACCION[accion] || ["gris", () => accion];
  return [color, fn(detalle)];
}

function mostrarDiffCorreccion(j) {
  const [clase, texto] = bannerParaAccion(j);
  const banner = $("#diff-banner");
  banner.className = `banner ${clase}`;
  banner.textContent = texto;

  const btnUsar = $("#btn-usar-nuevo");
  btnUsar.classList.add("oculto");
  btnUsar.onclick = null;

  const { sub_idx } = estadoApp.corregirCtx;
  const subAntes = subEnEdicion();
  const antesSvg = $("#arbol-antes"), despuesSvg = $("#arbol-despues");

  if (j.analisis_nuevo) {
    const subsD = j.analisis_nuevo.sub_oraciones;
    const subDespues = subsD[sub_idx] || subsD[0];
    dibujarArbolEnSvg(antesSvg, subAntes.arbol, subAntes.tokens);
    dibujarArbolEnSvg(despuesSvg, subDespues.arbol, subDespues.tokens);
    $("#el-antes").textContent = (subAntes.el && subAntes.el.lexical) || "";
    $("#el-despues").textContent = (subDespues.el && subDespues.el.lexical) || "";

    // en una accion compuesta ("staging_clase+persistido"), lo que importa
    // para habilitar "usar el nuevo análisis" es el componente EL.
    const accionEl = (j.accion || "").includes("+") ? j.accion.split("+")[1] : j.accion;
    if (["persistido", "insert", "update", "no-op", "persistido_enrutado"].includes(accionEl)) {
      btnUsar.classList.remove("oculto");
      btnUsar.onclick = () => usarNuevoAnalisis(j.analisis_nuevo);
    }
  } else {
    antesSvg.innerHTML = ""; despuesSvg.innerHTML = "";
    $("#el-antes").textContent = ""; $("#el-despues").textContent = "";
  }

  $("#diff-corregir").classList.remove("oculto");
}

function usarNuevoAnalisis(analisisNuevo) {
  cerrarModalCorregir();
  registrarEnHistorial(analisisNuevo.oracion, analisisNuevo);
  mostrarResultado(analisisNuevo);
}

$("#btn-corregir").addEventListener("click", abrirModalCorregir);

// ═══════════════════════════ navegación entre vistas (G3) ═══════════════════
function cambiarVista(nombre) {
  document.querySelectorAll(".nav-vista").forEach(
    (b) => b.classList.toggle("activa", b.dataset.vista === nombre));
  $("#cuerpo").classList.toggle("oculto", nombre !== "analizar");
  $("#vista-lote").classList.toggle("oculto", nombre !== "lote");
  $("#vista-curacion").classList.toggle("oculto", nombre !== "curacion");
  if (nombre === "curacion") cargarCuracion();
}
document.querySelectorAll(".nav-vista").forEach((b) => {
  b.addEventListener("click", () => cambiarVista(b.dataset.vista));
});

// ═══════════════════════════════ Exportaciones (G3 §4) ══════════════════════
function nombreArchivoExport(oracion, ext) {
  const palabras = (oracion || "").trim().replace(/[?¿!¡.]+$/g, "")
    .split(/\s+/).filter(Boolean).slice(0, 5);
  let nombre = palabras.join("_").toLowerCase();
  const acentos = { "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n" };
  nombre = nombre.replace(/[áéíóúüñ]/g, (ch) => acentos[ch] || ch);
  nombre = nombre.replace(/[^a-z0-9_]/g, "");
  return `analisis_${nombre || "oracion"}.${ext}`;
}

function descargarBlob(contenido, tipoMime, nombre) {
  const blob = new Blob([contenido], { type: tipoMime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  // el navegador puede descargar sin ninguna barra/notificación visible
  // (p.ej. chromium en modo --app) -- sin esto, "funcionó" es indistinguible
  // de "no pasó nada" para quien lo usa.
  mensajeEstado.classList.remove("error");
  mensajeEstado.classList.add("ok");
  mensajeEstado.textContent = `✓ descargado: ${nombre} (revisá tu carpeta de descargas)`;
  clearTimeout(descargarBlob._timer);
  descargarBlob._timer = setTimeout(() => {
    mensajeEstado.classList.remove("ok");
    mensajeEstado.textContent = "";
  }, 5000);
}

// SVG/PNG: se redibuja el árbol en un <svg> DESCONECTADO del documento (no
// depende de qué sub-oración esté visible ahora mismo) -- sirve igual para
// la vista de análisis que para una fila de lote nunca abierta.
// ─── OPERATORS_2 §4 — el SVG exportado debe ser AUTOCONTENIDO ─────────────
// BUG (reportado por Julian con imagen): los árboles exportados se veían como
// cajas NEGRAS y VACÍAS al abrirlos fuera de la GUI. Dentro de la app el SVG
// lo estila `estilo.css`, que es un archivo EXTERNO; el export salía con
// `class="arbol-nodo"` y nada más, así que el visor aplicaba los defaults del
// estándar SVG — `fill:black`, sin `stroke`, texto negro sobre fondo
// transparente. Además el PNG pintaba un fondo BLANCO bajo un texto de tema
// oscuro (casi blanco): invisible.
//
// FIX: al exportar se vuelcan los estilos COMPUTADOS a atributos de
// presentación inline (lo más compatible para visores conservadores) y se
// añade un rect de fondo. Se leen del DOM en vez de duplicar la paleta en JS:
// así el export no puede derivar de lo que se ve en pantalla.
// Qué propiedades tienen sentido en cada elemento. Volcarlas TODAS en todos
// (incluido `font-family` en una <line>, o `fill:black` en un <g>) engorda el
// archivo y, peor, deja un fill negro heredable colgando en los grupos.
const PROPS_EXPORT = {
  rect: ["fill", "stroke", "stroke-width", "stroke-dasharray", "opacity"],
  line: ["stroke", "stroke-width", "stroke-dasharray", "opacity"],
  path: ["fill", "stroke", "stroke-width", "opacity"],
  text: ["fill", "font-family", "font-size", "font-weight"],
};

// Los visores conservadores esperan NÚMEROS sin unidad en atributos de
// presentación (`stroke-width="1.4"`, no `"1.4px"`): `getComputedStyle`
// devuelve siempre px, así que se normaliza. `font-size` es la excepción
// habitual y se deja tal cual, que sí admite unidades.
function _sinPx(prop, valor) {
  return prop === "font-size" ? valor : valor.replace(/(\d)px\b/g, "$1");
}

function inlinarEstilos(svg) {
  // Debe estar EN el documento para que las reglas de estilo.css apliquen y
  // `getComputedStyle` devuelva algo distinto de los defaults.
  svg.style.position = "absolute";
  svg.style.left = "-99999px";
  svg.style.top = "0";
  document.body.appendChild(svg);
  try {
    // DOS PASADAS, y el orden importa: las reglas de estilo.css son
    // DESCENDENTES (`.arbol-nodo rect { fill: … }`). Si se quitara la clase
    // del <g> en la misma pasada, sus hijos —que se recorren DESPUÉS, en
    // orden de documento— ya no matchearían la regla y saldrían con el
    // default del estándar: negro. (Ocurrió: los rect y los text se
    // exportaban en rgb(0,0,0) mientras las líneas, estilizadas por una
    // clase propia, salían bien.)
    const elementos = [...svg.querySelectorAll("*")]
      .filter((el) => PROPS_EXPORT[el.tagName]);
    elementos.forEach((el) => {
      const cs = getComputedStyle(el);
      PROPS_EXPORT[el.tagName].forEach((p) => {
        const v = cs.getPropertyValue(p);
        if (v) el.setAttribute(p, _sinPx(p, v.trim()));
      });
    });
    [...svg.querySelectorAll("[class]")].forEach((el) => el.removeAttribute("class"));
    // Los hijos de <defs> NO se renderizan, así que su estilo computado puede
    // no resolver las reglas CSS: la punta de flecha se pinta explícitamente
    // desde la variable de tema (que sí resuelve en :root).
    const acento = getComputedStyle(document.documentElement)
      .getPropertyValue("--operador").trim() || "#4fd1c5";
    svg.querySelectorAll("marker path").forEach((p) => p.setAttribute("fill", acento));
  } finally {
    document.body.removeChild(svg);
    svg.removeAttribute("style");
  }
  return svg;
}

function colorFondoExport() {
  return getComputedStyle(document.documentElement)
    .getPropertyValue("--bg-panel").trim() || "#242832";
}

function construirSvgExportable(sub) {
  const svg = document.createElementNS(SVG_NS, "svg");
  // La exportación respeta el toggle: si el usuario está viendo la proyección
  // de operadores, se la lleva en el SVG/PNG (modo presentación).
  dibujarArbolEnSvg(svg, sub.arbol, sub.tokens,
                    estadoApp.mostrarOperadores ? (sub.operadores || []) : null);
  inlinarEstilos(svg);

  // Fondo explícito: sin él, el texto claro del tema cae sobre el fondo
  // (blanco o transparente) del visor y no se lee. Cubre exactamente el
  // viewBox, que empieza en coordenadas negativas.
  const vb = (svg.getAttribute("viewBox") || "0 0 0 0").split(/\s+/).map(Number);
  const fondo = crearElemSVG("rect", {
    x: vb[0], y: vb[1], width: vb[2], height: vb[3], fill: colorFondoExport(),
  });
  svg.insertBefore(fondo, svg.firstChild);

  svg.setAttribute("xmlns", SVG_NS);
  return svg;
}

function exportarSvg(resultado, subIdx = 0) {
  const sub = resultado.sub_oraciones[subIdx];
  if (!sub || !sub.arbol) return;
  const svgTmp = construirSvgExportable(sub);
  const xml = `<?xml version="1.0" encoding="UTF-8"?>\n${new XMLSerializer().serializeToString(svgTmp)}`;
  descargarBlob(xml, "image/svg+xml", nombreArchivoExport(resultado.oracion, "svg"));
}

function exportarPng(resultado, subIdx = 0) {
  const sub = resultado.sub_oraciones[subIdx];
  if (!sub || !sub.arbol) return;
  const svgTmp = construirSvgExportable(sub);
  const ancho = Number(svgTmp.getAttribute("width")) || 800;
  const alto = Number(svgTmp.getAttribute("height")) || 400;
  const xml = new XMLSerializer().serializeToString(svgTmp);
  const svgUrl = URL.createObjectURL(new Blob([xml], { type: "image/svg+xml" }));
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = ancho;
    canvas.height = alto;
    const ctx = canvas.getContext("2d");
    // MISMO fondo que el SVG (antes: blanco fijo, que dejaba el texto claro
    // del tema prácticamente invisible).
    ctx.fillStyle = colorFondoExport();
    ctx.fillRect(0, 0, ancho, alto);
    ctx.drawImage(img, 0, 0, ancho, alto);
    URL.revokeObjectURL(svgUrl);
    canvas.toBlob((blob) => {
      descargarBlob(blob, "image/png", nombreArchivoExport(resultado.oracion, "png"));
    }, "image/png");
  };
  img.src = svgUrl;
}

async function exportarServidor(resultado, ruta, ext) {
  const aid = resultado.analisis_id;
  if (!aid) return;
  try {
    const r = await fetch(`${API}${ruta}?analisis_id=${encodeURIComponent(aid)}`);
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      throw new Error(j.detail || `HTTP ${r.status}`);
    }
    const texto = await r.text();
    descargarBlob(texto, "text/plain;charset=utf-8", nombreArchivoExport(resultado.oracion, ext));
  } catch (e) {
    mensajeEstado.classList.add("error");
    mensajeEstado.textContent = `No se pudo exportar: ${e.message}`;
  }
}

const exportarTxt = (resultado) => exportarServidor(resultado, "/exportar/txt", "txt");
const exportarConllu = (resultado) => exportarServidor(resultado, "/exportar/conllu", "conllu");

$("#btn-exportar-svg").addEventListener("click", () => {
  if (estadoApp.resultadoActual) exportarSvg(estadoApp.resultadoActual, estadoApp.subIdxActual);
});
$("#btn-exportar-png").addEventListener("click", () => {
  if (estadoApp.resultadoActual) exportarPng(estadoApp.resultadoActual, estadoApp.subIdxActual);
});
$("#btn-exportar-txt").addEventListener("click", () => {
  if (estadoApp.resultadoActual) exportarTxt(estadoApp.resultadoActual);
});
$("#btn-exportar-conllu").addEventListener("click", () => {
  if (estadoApp.resultadoActual) exportarConllu(estadoApp.resultadoActual);
});

// ═══════════════════════════════ Modo lote (G3 §3) ══════════════════════════
const estadoLote = { filas: [] };   // [{oracion, resultado|null, error|null}]

$("#lote-archivo").addEventListener("change", async (ev) => {
  const file = ev.target.files[0];
  if (!file) return;
  $("#lote-textarea").value = await file.text();
});

function lineasDeLote(texto) {
  return texto.split("\n").map((l) => l.trim()).filter((l) => l && !l.startsWith("#"));
}

async function analizarLote() {
  const lineas = lineasDeLote($("#lote-textarea").value);
  if (lineas.length === 0) return;
  const boton = $("#btn-lote-analizar");
  boton.disabled = true;
  estadoLote.filas = [];
  renderTablaLote();
  try {
    for (let i = 0; i < lineas.length; i++) {
      const oracion = lineas[i];
      $("#lote-progreso").textContent = `${i + 1}/${lineas.length} — analizando: «${oracion}»`;
      try {
        const r = await fetch(`${API}/analizar`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ oracion }),
        });
        const j = await r.json();
        if (!r.ok || j.error) {
          estadoLote.filas.push({ oracion, resultado: null, error: j.error || j.detail || `HTTP ${r.status}` });
        } else {
          estadoLote.filas.push({ oracion, resultado: j, error: null });
          registrarEnHistorial(oracion, j);
        }
      } catch (e) {
        estadoLote.filas.push({ oracion, resultado: null, error: e.message });
      }
      renderTablaLote();
    }
    $("#lote-progreso").textContent = `Listo — ${lineas.length} oración(es) analizadas.`;
  } finally {
    boton.disabled = false;
  }
}

$("#btn-lote-analizar").addEventListener("click", analizarLote);
$("#lote-filtro-alerta").addEventListener("change", renderTablaLote);

function botonExportMini(etiqueta, onClick) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "btn-export-mini";
  b.textContent = etiqueta;
  b.addEventListener("click", (ev) => { ev.stopPropagation(); onClick(); });
  return b;
}

function renderTablaLote() {
  const tbody = $("#tabla-lote tbody");
  tbody.innerHTML = "";
  const soloAlerta = $("#lote-filtro-alerta").checked;
  estadoLote.filas.forEach((fila) => {
    const integridad = fila.error ? "—" : resumenIntegridad(fila.resultado);
    // el filtro esconde las filas "aburridas" (✓); un error aislado es
    // justo el tipo de fila que el filtro debe DEJAR VER, nunca ocultar.
    if (soloAlerta && !fila.error && integridad !== "⚠") return;
    const tr = document.createElement("tr");
    if (fila.error) {
      tr.classList.add("fila-lote-error");
      const tdOracion = document.createElement("td");
      tdOracion.textContent = fila.oracion;
      const tdClase = document.createElement("td");
      tdClase.textContent = "—";
      const tdIntegridad = document.createElement("td");
      tdIntegridad.textContent = "—";
      const tdAviso = document.createElement("td");
      tdAviso.className = "aviso";
      tdAviso.textContent = `Error: ${fila.error}`;
      const tdExport = document.createElement("td");
      tr.append(tdOracion, tdClase, tdIntegridad, tdAviso, tdExport);
    } else {
      const tdOracion = document.createElement("td");
      tdOracion.textContent = fila.oracion;
      const tdClase = document.createElement("td");
      tdClase.textContent = resumenClase(fila.resultado);
      const tdIntegridad = document.createElement("td");
      tdIntegridad.innerHTML = `<span class="${claseIntegridadChip(integridad)}">${integridad}</span>`;
      const tdAviso = document.createElement("td");
      tdAviso.textContent = resumenAvisos(fila.resultado);
      const tdExport = document.createElement("td");
      tdExport.className = "celda-exportar";
      tdExport.append(
        botonExportMini("SVG", () => exportarSvg(fila.resultado)),
        botonExportMini("PNG", () => exportarPng(fila.resultado)),
        botonExportMini(".txt", () => exportarTxt(fila.resultado)),
        botonExportMini(".conllu", () => exportarConllu(fila.resultado)));
      tr.append(tdOracion, tdClase, tdIntegridad, tdAviso, tdExport);
      tr.addEventListener("click", () => {
        cambiarVista("analizar");
        mostrarResultado(fila.resultado);
      });
    }
    tbody.appendChild(tr);
  });
}

// ═══════════════════════════════ Curación (G3 §5) ═══════════════════════════
function tablaCuracion(titulo, filas, total) {
  const wrap = document.createElement("div");
  wrap.className = "curacion-bloque";
  const h3 = document.createElement("h3");
  h3.textContent = `${titulo} — ${total} fila(s)`;
  wrap.appendChild(h3);
  if (filas.length === 0) {
    const p = document.createElement("p");
    p.className = "aviso";
    p.textContent = "(vacío)";
    wrap.appendChild(p);
    return wrap;
  }
  const tabla = document.createElement("table");
  tabla.className = "tabla-curacion";
  const columnas = Object.keys(filas[0]);
  const thead = document.createElement("thead");
  thead.innerHTML = `<tr>${columnas.map((col) => `<th>${escapeHTML(col)}</th>`).join("")}</tr>`;
  tabla.appendChild(thead);
  const tbody = document.createElement("tbody");
  filas.forEach((fila) => {
    const tr = document.createElement("tr");
    tr.innerHTML = columnas.map((col) => `<td>${escapeHTML(fila[col] || "")}</td>`).join("");
    tbody.appendChild(tr);
  });
  tabla.appendChild(tbody);
  wrap.appendChild(tabla);
  return wrap;
}

async function cargarCuracion() {
  const cont = $("#curacion-tablas");
  const resumen = $("#curacion-resumen");
  cont.innerHTML = '<p class="aviso">cargando…</p>';
  try {
    const r = await fetch(`${API}/curador/staging`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    cont.innerHTML = "";
    const TITULOS = {
      correcciones_clase: "Clase (correcciones_clase.csv)",
      correcciones_el: "Estructura Lógica (correcciones_el.csv)",
      correcciones_enrutado: "Enrutado (correcciones_enrutado.csv)",
    };
    Object.entries(TITULOS).forEach(([clave, titulo]) => {
      cont.appendChild(tablaCuracion(titulo, j[clave].filas, j[clave].total));
    });
    cont.appendChild(tablaCuracion("Log maestro (correcciones_log.csv)",
      j.log_maestro.filas, j.log_maestro.total));
    const porAccion = Object.entries(j.log_maestro.por_accion)
      .map(([accion, n]) => `${accion}: ${n}`).join(" · ");
    resumen.textContent = `Total en log maestro: ${j.log_maestro.total}` +
      (porAccion ? ` — ${porAccion}` : "");
  } catch (e) {
    cont.innerHTML = `<p class="aviso">No se pudo cargar la curación: ${e.message}</p>`;
  }
}

$("#btn-refrescar-curacion").addEventListener("click", cargarCuracion);

// ═══════════════════════════════ arranque ═══════════════════════════════════
sondearEstado();
cargarGlosario();
renderHistorial();
