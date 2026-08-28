"""Contrato visual LA2.1, probado sin navegador ni modelos."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


NODE = shutil.which("node")
JS = Path(__file__).parent / "gui" / "contrato_confianza.js"


@pytest.mark.skipif(NODE is None, reason="Node no disponible")
def test_formatear_confianza_es_defensivo():
    programa = (
        f"require({json.dumps(str(JS))});"
        "const f=globalThis.GrruxConfianza.formatearConfianza;"
        "process.stdout.write(JSON.stringify([f(0.55),f('0.55'),f(null),"
        "f(undefined),f('alta'),f({}),f(NaN),f(Infinity)]));"
    )
    salida = subprocess.run(
        [NODE, "-e", programa], check=True, text=True, capture_output=True
    ).stdout
    assert json.loads(salida) == ["0.55", "0.55", "—", "—", "—", "—", "—", "—"]


def test_render_no_invoca_tofixed_sobre_confianza_cruda():
    fuente = (Path(__file__).parent / "gui" / "app.js").read_text(encoding="utf-8")
    assert ".confianza.toFixed" not in fuente
    assert "renderCausatividad(sub)" in fuente
    assert "renderLinking(sub)" in fuente
