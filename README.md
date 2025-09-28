# Sistema de Monitoreo y Control VaporSur S.A.

## Descripción General

Sistema completo de monitoreo industrial compuesto por un microcontrolador Raspberry Pi Pico 2 W con CircuitPython y una interfaz gráfica en tiempo real desarrollada en PyQt5 con matplotlib.
Este sistema proporciona un control industrial robusto con monitoreo en tiempo real, ideal para aplicaciones que requieren supervisión continua y respuesta rápida a condiciones anómalas.

---

## Código del Microcontrolador (code.py)

### Funcionalidades Principales

#### **1. Control de Proceso Industrial**

- **Simulación de presión y temperatura**: Variables P_sim_kPa (150-500 kPa) y T_sim (80-220°C)
- **Control de válvula modulante**: PWM para MV_pct (0-100%)
- **Control de supercalentador**: PWM para SH_cmd (0-100%)
- **Dos modos de operación**: Presión y Temperatura, seleccionables por encoder

#### **2. Sistema de Seguridad Integrado**

**ESD (Emergency Shutdown):**

- Activación manual por botón físico
- Activación automática por condiciones críticas (P≥460 kPa o T≥190°C)
- Retorno controlado a valores seguros (P=300 kPa, T=150°C)
- Indicación de estado "Listo para Reinicio" cuando se alcanzan valores objetivo

**Rangos de Seguridad:**

```
PRESIÓN:
- Emergencia: ≥460 kPa (ESD automático)
- Advertencia Alta: ≥380 kPa
- Advertencia Baja: ≤250 kPa
- Recuperación: ≤220 kPa (control automático)

TEMPERATURA:
- Emergencia: ≥190°C (ESD automático)
- Advertencia Alta: ≥170°C
- Advertencia Baja: ≤120°C
- Precalentamiento: ≤110°C (control automático)
```

#### **3. Control de Flujo**

- **Flujo A**: P=310-350 kPa + T=140-160°C (LED parpadeante)
- **Flujo B**: P=260-300 kPa + T=160-170°C (LED sólido)
- Desactivación automática en modos de recuperación

#### **4. Interfaz de Usuario**

- **Encoder rotativo**: Ajuste de setpoints según modo activo
- **Botón del encoder**: Cambio entre modos con animación RGB
- **Botón ESD**: Parada de emergencia y reset del sistema

#### **5. Indicadores Visuales RGB**

Sistema de colores coherente con interfaz gráfica:

- **Verde**: Operación normal
- **Naranja**: Advertencias (presión/temperatura fuera de rango)
- **Rojo**: Estados críticos, emergencias, ESD activo
- **Cian**: Modos de recuperación y precalentamiento
- **Rojo parpadeante**: ESD en proceso de recuperación

#### **6. Conectividad IoT**

- **WiFi**: Conexión automática a red configurada
- **MQTT**: Publicación de datos cada 5 segundos
- **Topics**: `sensores/automatas/presión` y `sensores/automatas/temperatura`
- **Discovery**: Anuncio automático de capacidades del equipo

#### **7. Monitoreo y Logging**

- **Salida serial**: Datos formateados cada 100ms para interfaz gráfica
- **Formato**: `P:value,T:value,MV:value,SH:value,F:state,M:mode,ESD:state,ESTADO:description,RELIEF:state,PURGE:state`

#### **8. Estados del Sistema**

**Operación Normal:**

- Control manual por encoder según modo seleccionado
- Monitoreo continuo de condiciones de seguridad
- Indicación de flujo activo cuando las condiciones lo permiten

**Modo Recuperación:**

- Activación automática cuando P ≤ 220 kPa
- MV_pct = 0% (cierre de válvula modulante)
- Finalización automática cuando P > 240 kPa

**Modo Precalentamiento:**

- Activación automática cuando T ≤ 110°C
- SH_cmd = 100% (máximo calentamiento)
- Finalización automática cuando T > 130°C

**Modo ESD:**

- Control automático para retorno a valores iniciales
- Activación de válvulas de alivio/purga según necesidad
- Indicación visual de progreso hasta "Listo para Reinicio"

---

## Interfaz Gráfica (pc_plotter.py)

### Características Principales

#### **1. Visualización en Tiempo Real**

- Gráficos de presión y temperatura con ventana deslizante de 60 segundos
- Eje X en tiempo real (MM:SS) con actualización fluida
- Ejes Y fijos para referencia consistente
- Frecuencia de actualización: 20 FPS

#### **2. Indicadores de Estado**

- Labels con código de colores coherente al microcontrolador
- Información completa del sistema: P, T, MV, SH, Modo, ESD, Válvulas
- Tiempo transcurrido desde inicio de monitoreo

#### **3. Referencias Visuales**

- Áreas coloreadas para rangos de flujo A y B
- Líneas de referencia para límites críticos y de advertencia
- Leyendas informativas con valores específicos

#### **4. Optimizaciones de Rendimiento**

- Separación de hilos: adquisición de datos, procesamiento y visualización
- Buffer circular con numpy para manejo eficiente de datos
- Actualización condicional de elementos gráficos
- Simulador integrado para pruebas sin hardware

### Arquitectura del Software

- **Hilo de Datos**: Genera/lee datos del puerto serial cada 100ms
- **Timer GUI**: Actualiza interfaz cada 50ms
- **Buffer Numpy**: Almacenamiento eficiente de 200 puntos históricos
- **Parser Optimizado**: Procesamiento rápido del formato de datos

---

## Comunicación

### Protocolo Serial

- **Baudrate**: 115200
- **Frecuencia**: 10 Hz (cada 100ms)
- **Formato**: Campos separados por comas con identificadores

### Protocolo MQTT

- **Broker**: Mosquitto en PC local
- **QoS**: 0 (fire and forget)
- **Formato de datos**: Arrays JSON `[valor]`
- **Frecuencia**: 0.2 Hz (cada 5 segundos)

## Características de Seguridad

1. **Triple redundancia**: Monitoreo local, serial y MQTT
2. **Failsafe por defecto**: ESD automático ante condiciones críticas
3. **Estados bien definidos**: Sin ambigüedades en transiciones
4. **Realimentación visual**: RGB coherente con estado real del sistema
5. **Recuperación controlada**: Retorno gradual a condiciones seguras

## Parámetros Configurables

**Microcontrolador:**

- Umbrales de presión y temperatura
- Sensibilidades del encoder
- Intervalos de publicación MQTT
- Credenciales de red WiFi

**Interfaz Gráfica:**

- Ventana de tiempo visible (60s por defecto)
- Frecuencia de actualización GUI
- Rangos de visualización Y fijos
- Colores y estilos visuales

---

- Elaborado por el grupo 6 - "Automatas"
- En el marco del primper laboratorio de la materia Tecnologías para la Automatización de 4º año de ISI (2025)

---
