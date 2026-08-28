# Cómo abrir la GUI de GRRux en Ubuntu / WSL

Guía corta para usar GRRux con su **interfaz gráfica** (GUI) en Ubuntu,
incluido Ubuntu sobre **WSL** (Windows). Supone que ya corriste el
instalador (`bash instalar_estudiantes.sh`) y que la terminal (CLI) ya
funciona.

## Los 3 pasos

```bash
cd ~/proyectos/ud2rrg
./grrux-gui
```

Esto arranca el servidor local (carga Stanza + BERTIN; la **primera vez
tarda varios minutos**). Cuando termina, la GUI queda disponible en:

```
http://localhost:8763/
```

Ahora abre esa dirección **en el navegador de Windows** (Chrome, Edge o
Firefox):

```
http://localhost:8763/
```

## Por qué hay que abrir el navegador a mano (WSL)

En WSL no hay un navegador de Linux, así que `./grrux-gui` **arranca el
servidor pero no puede abrir el navegador solo**. Por eso parece que "no
pasa nada": en realidad el servidor sí está corriendo. Solo falta que tú
abras `http://localhost:8763/` en el navegador de Windows.

WSL2 reenvía `localhost` automáticamente entre Windows y Ubuntu, así que
**no hay que configurar nada de red ni buscar ninguna IP**.

*(Opcional)* Para que el navegador se abra solo la próxima vez:

```bash
sudo apt install wslu
```

`wslu` añade el comando `wslview`, que abre el navegador de Windows desde
Ubuntu.

## Detener el servidor

Cuando termines, detén el servidor con:

```bash
pkill -f 'uvicorn grrux_server'
```

## Si algo falla

- **No se abre la página / "no se puede conectar":** espera un poco más
  (la primera carga de modelos es lenta) y refresca. Revisa que la
  terminal donde corriste `./grrux-gui` no muestre un error.
- **Dice que no encuentra `uvicorn` o el entorno:** vuelve a correr el
  instalador, que reutiliza el entorno y agrega lo que falte:
  ```bash
  bash instalar_estudiantes.sh
  ```
- **Ver el registro del servidor** (para diagnosticar):
  ```bash
  cat ~/proyectos/ud2rrg/grrux-gui.log
  ```
- **Poca RAM (4-8 GB):** usa una sola instancia a la vez y cierra
  pestañas pesadas del navegador antes de analizar.

## Comprobar que tienes la versión más nueva

Analiza una oración con pronombre **"le"**, por ejemplo:

```
Juan le dio un regalo a María
```

Si el análisis sale correcto, tienes los arreglos recientes. Si tu copia
es vieja, primero actualízala (ver el documento de instrucciones de
actualización) y vuelve a correr el instalador.
