"""Tests de la exportación SVG/PNG — Etapa OPERATORS_2 §4.

BUG que motiva estos tests (reportado por Julian con imagen): los árboles
exportados desde la GUI se veían como CAJAS NEGRAS, VACÍAS y SIN LÍNEAS al
abrirlos fuera (visor de imágenes, LibreOffice). Dentro de la app el SVG lo
estila `gui/estilo.css`, que es un archivo EXTERNO: el export salía con solo
`class="arbol-nodo"` y el visor aplicaba los defaults del estándar SVG
(`fill:black`, sin stroke). Y el PNG pintaba un fondo BLANCO bajo el texto
claro del tema oscuro: invisible.

Se comprueban dos cosas complementarias:

  1. CONTRATO sobre un SVG exportado REAL (`fixture_export_arbol.svg`,
     generado por la propia GUI): ningún elemento depende de CSS externo.
     Y se rasteriza con inkscape —un motor EXTERNO de verdad, que es el
     escenario del bug— comprobando que no sale mayoritariamente negro.
  2. CABLEADO en `gui/app.js`: que las dos exportaciones pasen por
     `construirSvgExportable` y que el PNG no vuelva a fijar un fondo blanco.
     No hay runner de JS en el repo, así que esta parte es estática — su
     valor es impedir que alguien reintroduzca el bug editando el export.

Ejecutar:  python -m pytest test_export_svg.py
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import pytest

RAIZ = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(RAIZ, "fixture_export_arbol.svg")
APP_JS = os.path.join(RAIZ, "gui", "app.js")
SVG_NS = "{http://www.w3.org/2000/svg}"


def _arbol_fixture():
    return ET.parse(FIXTURE).getroot()


# ---------------------------------------------------------------------------
# 1. Contrato del SVG exportado
# ---------------------------------------------------------------------------
def test_export_no_depende_de_clases_css_externas():
    """Ni una sola `class=`: si quedara alguna, ese elemento se vería con los
    defaults del estándar en cualquier visor (que es justo el bug)."""
    xml = open(FIXTURE, encoding="utf-8").read()
    assert 'class="' not in xml, "el SVG exportado todavía depende de estilo.css"


def test_cada_rect_lleva_fill_y_stroke_inline():
    raiz = _arbol_fixture()
    rects = raiz.findall(f".//{SVG_NS}rect")
    assert len(rects) > 5
    for r in rects:
        assert r.get("fill"), f"rect sin fill inline: {r.attrib}"
    # el primero es el fondo (sin stroke); el resto son nodos y sí lo llevan
    for r in rects[1:]:
        assert r.get("stroke"), f"rect sin stroke inline: {r.attrib}"


def test_cada_linea_lleva_stroke_inline():
    """Las líneas de conexión eran lo PRIMERO que desaparecía: un <line> sin
    stroke no se dibuja en absoluto."""
    lineas = _arbol_fixture().findall(f".//{SVG_NS}line")
    assert len(lineas) > 5
    for l in lineas:
        assert l.get("stroke"), f"línea sin stroke inline: {l.attrib}"
        assert l.get("stroke") != "none"


def test_cada_texto_lleva_fill_y_fuente_inline():
    textos = _arbol_fixture().findall(f".//{SVG_NS}text")
    assert len(textos) > 5
    for t in textos:
        assert t.get("fill"), f"texto sin fill inline: {t.text}"
        assert t.get("font-family"), f"texto sin font-family inline: {t.text}"


def test_hay_rect_de_fondo_que_cubre_el_viewbox():
    """Sin fondo explícito, el texto claro del tema cae sobre el blanco o el
    transparente del visor y no se lee."""
    raiz = _arbol_fixture()
    vb = [float(v) for v in raiz.get("viewBox").split()]
    fondo = raiz.find(f"{SVG_NS}rect")           # debe ser el PRIMER hijo
    assert fondo is not None and fondo.get("fill")
    assert float(fondo.get("x")) == vb[0] and float(fondo.get("y")) == vb[1]
    assert float(fondo.get("width")) == vb[2] and float(fondo.get("height")) == vb[3]


def test_anchos_de_trazo_sin_unidades():
    """Los visores conservadores esperan números desnudos en atributos de
    presentación (`stroke-width="1.4"`, no `"1.4px"`)."""
    raiz = _arbol_fixture()
    for el in raiz.iter():
        sw = el.get("stroke-width")
        if sw is not None:
            assert not sw.endswith("px"), f"stroke-width con unidad: {sw}"
            float(sw)                    # debe ser numérico


def test_el_svg_declara_su_namespace():
    """Sin xmlns un archivo suelto no es un SVG válido para un visor."""
    assert _arbol_fixture().tag == f"{SVG_NS}svg"


def _magick():
    return shutil.which("magick") or shutil.which("convert")


def _pixeles(png: str) -> list[tuple[int, int, int]]:
    """Píxeles RGB vía ImageMagick (no hay Pillow en el venv). `-sample` hace
    muestreo por punto, SIN interpolar: si mezclara colores, el recuento de
    colores distintos subiría solo por el reescalado y la prueba mentiría."""
    salida = subprocess.run(
        [_magick(), png, "-sample", "120x120", "-depth", "8", "txt:-"],
        check=True, capture_output=True, timeout=120).stdout.decode("utf-8", "replace")
    # Se lee la tupla numérica `x,y: (r,g,b,a)` y no el hex: ImageMagick lo
    # emite con alfa (`#242832FF`), así que un patrón de 6 dígitos no casa.
    return [(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            for m in re.finditer(r"^\d+,\d+:\s*\((\d+),(\d+),(\d+)",
                                 salida, re.MULTILINE)]


@pytest.mark.skipif(shutil.which("inkscape") is None or _magick() is None,
                    reason="inkscape/ImageMagick no disponibles")
def test_rasterizado_externo_no_sale_negro():
    """La prueba de fuego: rasterizar con un motor EXTERNO (inkscape, que no
    sabe nada de estilo.css) y comprobar que la imagen tiene contenido y no es
    la mancha negra del bug. Medido en esta etapa: ANTES ~12% de píxeles
    negros puros y 8 colores distintos; DESPUÉS 0% y cientos."""
    with tempfile.TemporaryDirectory() as tmp:
        png = os.path.join(tmp, "salida.png")
        subprocess.run(["inkscape", FIXTURE, "-o", png, "-w", "420"],
                       check=True, capture_output=True, timeout=120)
        pixeles = _pixeles(png)

    assert pixeles, "no se pudo leer el PNG rasterizado"
    total = len(pixeles)
    negros = sum(1 for r, g, b in pixeles if r < 20 and g < 20 and b < 20)
    colores = len(set(pixeles))

    assert negros / total < 0.02, f"{100*negros/total:.1f}% de píxeles negros: el bug volvió"
    assert colores > 20, f"solo {colores} colores distintos: no se dibujaron trazos ni texto"


# ---------------------------------------------------------------------------
# 2. Cableado del export en gui/app.js (estático: no hay runner de JS)
# ---------------------------------------------------------------------------
def _app_js():
    return open(APP_JS, encoding="utf-8").read()


def test_ambas_exportaciones_pasan_por_construir_svg_exportable():
    js = _app_js()
    for fn in ("function exportarSvg", "function exportarPng"):
        i = js.index(fn)
        cuerpo = js[i:i + 900]
        assert "construirSvgExportable" in cuerpo, f"{fn} no usa el SVG estilado"


def test_el_png_no_vuelve_a_fijar_fondo_blanco():
    """Regresión exacta del bug: `ctx.fillStyle = "#ffffff"` bajo texto claro."""
    js = _app_js()
    i = js.index("function exportarPng")
    cuerpo = js[i:i + 1200]
    assert "#ffffff" not in cuerpo, "el PNG vuelve a pintar fondo blanco fijo"
    assert "colorFondoExport()" in cuerpo


def test_props_export_cubre_los_tres_tipos_criticos():
    js = _app_js()
    i = js.index("const PROPS_EXPORT")
    bloque = js[i:i + 500]
    for tag in ("rect:", "line:", "text:"):
        assert tag in bloque, f"PROPS_EXPORT no cubre {tag}"
    assert "stroke" in bloque and "fill" in bloque and "font-family" in bloque


def test_los_estilos_se_inlinan_antes_de_quitar_las_clases():
    """El orden importa y ya se rompió una vez: las reglas de estilo.css son
    DESCENDENTES (`.arbol-nodo rect`), así que quitar la clase del <g> antes
    de leer el estilo computado de sus hijos los dejaba en negro."""
    js = _app_js()
    i = js.index("function inlinarEstilos")
    cuerpo = js[i:js.index("function colorFondoExport")]
    pos_set = cuerpo.index("setAttribute(p,")
    pos_remove = cuerpo.index('removeAttribute("class")')
    assert pos_set < pos_remove, "se quitan las clases antes de volcar los estilos"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
