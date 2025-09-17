# Configuración de Visualización de la Salida del `code.py` de Raspberry Pi Pico 2 W en Arch Linux con mpremote

Este documento explica los pasos necesarios para ver la salida por consola del archivo `code.py` ejecutado en Raspberry Pi Pico 2 W con CircuitPython desde Arch Linux usando `mpremote`.

---

## 1. Instalar mpremote

```bash
pip install mpremote
```

---

## 2. Verificar conexión del dispositivo

Conectar el Pico por USB y verificar el puerto asignado:

```bash
ls /dev/ttyACM*
```

Debería devolver el puerto asignado, por ejemplo `/dev/ttyACM0`.

---

## 3. Configurar permisos

### Opción A: Permanente

Agregar el usuario actual al grupo `uucp`:

```bash
sudo usermod -aG uucp $USER
```

Cerrar sesión y volver a iniciar sesión. Verificar con:

```bash
groups
```

Debe aparecer `uucp` en la lista.

### Opción B: Temporal

Si no querés reiniciar:

```bash
sudo chmod a+rw /dev/ttyACM0
```

Este permiso se pierde al reconectar el dispositivo.

---

## 4. Conectarse al REPL del Pico

```bash
mpremote connect /dev/ttyACM0 repl
```

Esto mostrará en la terminal las salidas de `code.py`.

---

## 5. Salir de mpremote

- Terminar ejecución: `Ctrl+C`
- Reiniciar ejecución: `Ctrl+D`
- Salir: `Ctrl+X`

---

# Anexo: Aparición de errores

- `mpremote: failed to access /dev/ttyACM0 (it may be in use by another program)`

Lo que debes hacer si se presenta este error es controlar que posees los permisos `uucp` y/o `dialout` (este último sólo para Ubuntu/Debian).

```bash
sudo usermod -aG uucp $USER
sudo usermod -aG dialout $USER
```

Y luego de reiniciar la sesión, verificar los permisos correctos con:

```bash
groups
```

---
