# GRRux 2.x

GRRux es un analizador experimental de Gramática del Papel y la Referencia
(RRG) para oraciones en español. Construye árbol RRG, Estructura Lógica (EL),
Aktionsart, macropapeles, operadores, Linking e informes de integridad.

El código conserva nombres históricos como `gruxx_server.py`; el nombre del
sistema es **GRRux**.

## Instalación rápida

Clona el repositorio privado y entra al directorio:

```bash
git clone git@github.com:juber-86/Grrux-2.x.git
cd Grrux-2.x
```

### Bazzite

Bazzite usa una base Fedora Atomic. El instalador crea un contenedor Distrobox
Fedora para aislar compiladores y dependencias sin modificar la imagen del
sistema anfitrión:

```bash
bash instalar_bazzite.sh
./grrux-bazzite gui
```

La GUI se sirve solo en la máquina local: <http://127.0.0.1:8763/>.

Otros comandos útiles:

```bash
./grrux-bazzite terminal
./grrux-bazzite modelos
```

### Arch Linux

```bash
bash instalar_arch.sh
./gruxx-gui
```

Para la interfaz de terminal:

```bash
./venv/bin/python gruxx_ai1.py
```

## Qué hace el instalador

Los instaladores crean `venv/`, instalan PyTorch **solo para CPU** y todas las
dependencias Python, obtienen y compilan la revisión fijada de
[`disco-dop`](https://github.com/andreasvc/disco-dop), y verifican las
importaciones centrales. No incluyen CUDA: el funcionamiento normal en equipos
AMD o Intel es por CPU.

La primera ejecución con análisis puede descargar los modelos de Stanza para
español y BERTIN. Para descargarlos de antemano:

```bash
bash instalar_comun.sh --modelos
```

Se requiere conexión a Internet durante la instalación y para esa descarga
inicial. Se recomienda Linux x86_64 y al menos 12 GB de RAM. El instalador
elige automáticamente un Python compatible entre 3.10 y 3.13; por ahora
no usa Python 3.14 porque varias dependencias científicas todavía no lo
soportan bien. En equipos con 12 GB, usa una sola instancia de GRRux:
cierra la GUI antes de lanzar pruebas lentas u otra sesión de análisis.

## Incluido y excluido

El repositorio incluye el núcleo, la GUI, modelos y recursos curados necesarios
para el análisis:

```text
gruxx_ai1.py                         entrada de terminal
gruxx_server.py → gruxx_motor.py → gui/   GUI web local
rrg_ls_mapper.py                     hub semántico y Linking
ud2rrg.py                            conversor UD → árbol RRG
aspect_classifier/                   Aktionsart y análisis RRG
```

Los treebanks UD no se distribuyen: son datos externos de evaluación y
entrenamiento, no un requisito de ejecución. Tampoco se versionan el entorno
virtual, cachés, `.deps/` ni el log local de la GUI.

## Publicación en GitHub

Para crear una historia Git nueva —sin el historial heredado ni sus treebanks—
y publicarla en el repositorio privado configurado:

```bash
gh auth login -h github.com
bash publicar_github_limpio.sh
```

Si el remoto ya contiene una rama `main` que se quiere sustituir
conscientemente por esta distribución limpia, el comando exige la confirmación
explícita:

```bash
bash publicar_github_limpio.sh --force
```

## Arquitectura

```text
Texto en español
  → Stanza / CoNLL-U
  → rrg_ls_mapper.py
  → aspect_classifier/
  → EL + MISC
  → ud2rrg.py
  → árbol RRG + Integridad + Linking
```

`rrg_ls_mapper.py` es el hub semántico. `ud2rrg.py` es el conversor
heredado con capa española; no debe modificarse sin decisión explícita y
pruebas que preserven sus gates de idioma/MISC.

## Pruebas y reglas del proyecto

```bash
./venv/bin/python -m pytest
```

No ejecutes las pruebas lentas con la GUI abierta. Antes de modificar la
semántica o el conversor, revisa
[`ESTADO_DEL_ARTE_GRUXX.md`](ESTADO_DEL_ARTE_GRUXX.md), los
`CHECKPOINT_*.md` y los prompts de fase. Los CSV curados en
`aspect_classifier/data/` son auditables; no deben convertirse
automáticamente en datos de entrenamiento.
