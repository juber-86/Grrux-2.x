#!/usr/bin/env bash
set -e
cd "$(dirname "$0")" 2>/dev/null || true
REPO="$HOME/mnt/ud2rrg"
cd "$REPO"

echo "=== 1) rename de archivos (git mv) ==="
declare -A RENAMES=(
  [gruxx_ai1.py]=grrux_ai1.py
  [gruxx_server.py]=grrux_server.py
  [gruxx_motor.py]=grrux_motor.py
  [test_gruxx_motor.py]=test_grrux_motor.py
  [test_gruxx_server.py]=test_grrux_server.py
  [gruxx-gui]=grrux-gui
  [gruxx.desktop]=grrux.desktop
  [docs/diagrama_gruxx.html]=docs/diagrama_grrux.html
  [docs/diagrama_gruxx.svg]=docs/diagrama_grrux.svg
  [aspect_classifier/data/glosario_gruxx.csv]=aspect_classifier/data/glosario_grrux.csv
)
for old in "${!RENAMES[@]}"; do
  new="${RENAMES[$old]}"
  if git ls-files --error-unmatch "$old" >/dev/null 2>&1; then
    git mv "$old" "$new"
    echo "git mv: $old -> $new"
  elif [ -e "$old" ]; then
    mv "$old" "$new"
    echo "mv (untracked): $old -> $new"
  else
    echo "AVISO: $old no existe, se omite"
  fi
done

# gruxx-gui.log: untracked, puede no existir todavia
if [ -e gruxx-gui.log ]; then
  mv gruxx-gui.log grrux-gui.log
  echo "mv: gruxx-gui.log -> grrux-gui.log"
fi

echo "=== 2) .gitignore: gruxx-gui.log -> grrux-gui.log, comentario ==="
sed -i 's#^/gruxx-gui\.log$#/grrux-gui.log#; s/# Salidas regenerables de gruxx/# Salidas regenerables de GRRux/' .gitignore

echo "=== 3) string interna: imports y referencias de modulo ==="
# archivos donde se hacen las sustituciones de codigo/prosa (ya renombrados donde aplica)
FILES_STRING="grrux_ai1.py grrux_server.py grrux_motor.py test_grrux_motor.py test_grrux_server.py \
grrux-gui grrux.desktop docs/diagrama_grrux.html README.md docs/GUI.md docs/DESARROLLO.md \
briefing_aspect_classifier.md gui/app.js gui/index.html instalar_comun.sh instalar_estudiantes.sh \
publicar_github_limpio.sh aspect_classifier/correccion.py aspect_classifier/display_grr.py \
aspect_classifier/glosario.py aspect_classifier/gui_contract.py aspect_classifier/kpi_linking.py \
aspect_classifier/linking.py aspect_classifier/misc_rrg.py aspect_classifier/operadores.py \
aspect_classifier/test_ditransitivas.py aspect_classifier/test_l5.py aspect_classifier/test_misc_rrg.py \
aspect_classifier/test_operadores.py aspect_classifier/test_ud2rrg_es.py \
rrg_ls_mapper.py"

for f in $FILES_STRING; do
  [ -f "$f" ] || { echo "AVISO: falta $f"; continue; }
  # orden: mas especifico primero (aunque los limites de palabra ya los separan)
  sed -i \
    -e 's/gruxx_ai1\.py/grrux_ai1.py/g' \
    -e 's/gruxx_ai1\.\([a-zA-Z_]\)/grrux_ai1.\1/g' \
    -e 's/\bgruxx_ai1\b/grrux_ai1/g' \
    -e 's/gruxx_server\.py/grrux_server.py/g' \
    -e 's/gruxx_server\.\([a-zA-Z_]\)/grrux_server.\1/g' \
    -e 's/gruxx_server:app/grrux_server:app/g' \
    -e 's/\bgruxx_server\b/grrux_server/g' \
    -e 's/gruxx_motor\.py/grrux_motor.py/g' \
    -e 's/gruxx_motor\.\([a-zA-Z_]\)/grrux_motor.\1/g' \
    -e 's/\bgruxx_motor\b/grrux_motor/g' \
    -e 's/test_gruxx_motor\.py/test_grrux_motor.py/g' \
    -e 's/test_gruxx_server\.py/test_grrux_server.py/g' \
    -e 's/glosario_gruxx\.csv/glosario_grrux.csv/g' \
    -e 's/diagrama_gruxx\.svg/diagrama_grrux.svg/g' \
    -e 's/diagrama_gruxx\.html/diagrama_grrux.html/g' \
    -e 's/gruxx-gui\.log/grrux-gui.log/g' \
    -e 's/gruxx-gui/grrux-gui/g' \
    -e 's/gruxx\.desktop/grrux.desktop/g' \
    -e 's/gruxx_gui_/grrux_gui_/g' \
    -e 's/gruxx_historial/grrux_historial/g' \
    -e 's/\bgruxx\b/GRRux/g' \
    "$f"
done

echo "=== 4) gruxx.desktop ya renombrado: Name= y Exec= ya cubiertos arriba; verificar Exec explicito ==="
if [ -f grrux.desktop ]; then
  sed -i 's#Exec=.*gruxx-gui#Exec=/home/jbj86/proyectos/ud2rrg/grrux-gui#' grrux.desktop
fi

echo "=== 5) purga __pycache__ ==="
rm -rf __pycache__/ aspect_classifier/__pycache__/ 2>&1 || true

echo "=== 6) verificacion post-rename: nadie importa los nombres viejos ==="
FILES2=$(find . -maxdepth 2 -name "*.py" -not -path "./venv/*" -not -path "./legacy/*" -not -path "./.git/*" -not -path "./_to_delete/*")
for m in gruxx_ai1 gruxx_server gruxx_motor; do
  hits=$(grep -l "^\(from\|import\) $m\b" $FILES2 2>/dev/null)
  if [ -n "$hits" ]; then echo "PROBLEMA: $m todavia importado por: $hits"; fi
done

echo "=== 6b) sanity: _res_gruxx (identificador Python, NO debia tocarse) ==="
grep -n "_res_gruxx\|_res_grrux" aspect_classifier/test_l5.py | head -3

echo "=== 6c) sanity: compilar los .py tocados/renombrados ==="
./venv/bin/python -m py_compile grrux_ai1.py grrux_server.py grrux_motor.py \
  test_grrux_motor.py test_grrux_server.py \
  aspect_classifier/correccion.py aspect_classifier/display_grr.py aspect_classifier/glosario.py \
  aspect_classifier/gui_contract.py aspect_classifier/kpi_linking.py aspect_classifier/linking.py \
  aspect_classifier/misc_rrg.py aspect_classifier/operadores.py aspect_classifier/test_ditransitivas.py \
  aspect_classifier/test_l5.py aspect_classifier/test_misc_rrg.py aspect_classifier/test_operadores.py \
  aspect_classifier/test_ud2rrg_es.py rrg_ls_mapper.py 2>&1 && echo "py_compile OK"

echo "=== 7) verificacion final grep (debe estar vacio) ==="
grep -rl "gruxx" \
     --include="*.py" --include="*.md" --include="*.sh" \
     --include="*.desktop" --include="*.html" --include="*.js" --include="*.css" \
     --include="*.csv" --include="*.yaml" --include="*.yml" . 2>/dev/null \
  | grep -v -E "^\./(CHECKPOINTS|PROMPTS|legacy|venv|_to_delete)/|^\./ud2rrg\.py$|^\./ESTADO_DEL_ARTE_GRUXX|^\./PENDIENTES_GRRUX|GRUXX_oraciones" \
  | sort > /tmp/gruxx_residual.txt
echo "residuales (deberia estar vacio):"
cat /tmp/gruxx_residual.txt

echo "=== 8) git add -A (solo staging, NO commit) ==="
git add -A -- . ':!venv' ':!legacy' ':!_to_delete' ':!_deuda_infra_d.sh' 2>&1
echo "=== fin script ==="
