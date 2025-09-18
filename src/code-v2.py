# code.py - VaporSur S.A. (CircuitPython)
# Sistema de Control y Supervisión para Plantas de Vapor
# Lógica de seguridad ESD (Emergency Shutdown) con control de retorno a valores iniciales

import board
import digitalio
import rotaryio
import pwmio
import time
import math
import sys

# =================================================================
# CONFIGURACIÓN DE PINES DEL MICROCONTROLADOR
# =================================================================

# --- ENCODER ROTATIVO (KY-040) ---
# Permite ajustar presión y temperatura según modo seleccionado
ENC_CLK = board.GP3   # CLK (señal A del encoder)
ENC_DT = board.GP4    # DT (señal B del encoder)  
ENC_SW = board.GP5    # SW (botón integrado para cambio de modo)

# --- BOTÓN DE PARO DE EMERGENCIA (KY-004) ---
# Activa/desactiva el sistema ESD
BTN_ESD_PIN = board.GP0

# --- SALIDAS DIGITALES SIMULADAS ---
# Representan actuadores del sistema de vapor
LED_FLUJO_PIN = board.GP8      # LED indicador de flujo de distribución
PIN_LASER = board.GP9          # Láser (indica activación de válvulas)
PIN_ALIVIO = board.GP10        # Válvula de alivio de presión (simulada)
PIN_PURGA_A = board.GP11       # Sistema de purga rama A (simulado)
PIN_PURGA_B = board.GP12       # Sistema de purga rama B (simulado)

# --- SALIDAS PWM PARA CONTROL ANALÓGICO ---
# Simulan señales de control para válvulas modulantes
PWM_VALVULA_MODULANTE_PIN = board.GP6    # Control de válvula modulante (presión)
PWM_SUPERCALENTADOR_PIN = board.GP7      # Control del supercalentador (temperatura)

# --- LED RGB PARA INDICACIÓN DE ESTADOS (KY-016) ---
# Señalización visual del estado del sistema
RGB_ROJO_PIN = board.GP13      # Canal rojo
RGB_VERDE_PIN = board.GP14     # Canal verde
RGB_AZUL_PIN = board.GP15      # Canal azul

# =================================================================
# INICIALIZACIÓN DE OBJETOS DE HARDWARE
# =================================================================

# --- CONFIGURACIÓN DEL ENCODER ROTATIVO ---
encoder = rotaryio.IncrementalEncoder(ENC_CLK, ENC_DT)
boton_encoder = digitalio.DigitalInOut(ENC_SW)
boton_encoder.direction = digitalio.Direction.INPUT
boton_encoder.pull = digitalio.Pull.UP

# --- CONFIGURACIÓN DEL BOTÓN ESD ---
boton_esd = digitalio.DigitalInOut(BTN_ESD_PIN)
boton_esd.direction = digitalio.Direction.INPUT
boton_esd.pull = digitalio.Pull.UP

# --- FUNCIÓN AUXILIAR PARA CREAR SALIDAS DIGITALES ---
def crear_salida_digital(pin):
    """Crea y configura una salida digital en estado bajo"""
    salida = digitalio.DigitalInOut(pin)
    salida.direction = digitalio.Direction.OUTPUT
    salida.value = False
    return salida

# --- CONFIGURACIÓN DE SALIDAS DIGITALES ---
led_flujo = crear_salida_digital(LED_FLUJO_PIN)
laser_indicador = crear_salida_digital(PIN_LASER)
valvula_alivio = crear_salida_digital(PIN_ALIVIO)
sistema_purga_a = crear_salida_digital(PIN_PURGA_A)
sistema_purga_b = crear_salida_digital(PIN_PURGA_B)

# --- CONFIGURACIÓN DE SALIDAS PWM ---
pwm_valvula_modulante = pwmio.PWMOut(PWM_VALVULA_MODULANTE_PIN, frequency=5000, duty_cycle=0)
pwm_supercalentador = pwmio.PWMOut(PWM_SUPERCALENTADOR_PIN, frequency=5000, duty_cycle=0)

# --- CONFIGURACIÓN DEL LED RGB ---
rgb_rojo = pwmio.PWMOut(RGB_ROJO_PIN, frequency=5000, duty_cycle=0)
rgb_verde = pwmio.PWMOut(RGB_VERDE_PIN, frequency=5000, duty_cycle=0)
rgb_azul = pwmio.PWMOut(RGB_AZUL_PIN, frequency=5000, duty_cycle=0)

# =================================================================
# PARÁMETROS DE SIMULACIÓN Y CONTROL DEL SISTEMA
# =================================================================

# --- VALORES INICIALES DEL SISTEMA ---
# Condiciones de operación estable según especificaciones VaporSur
PRESION_INICIAL = 300.0      # kPa - Presión de referencia
TEMPERATURA_INICIAL = 150.0  # °C - Temperatura de referencia

# Variables de simulación (valores actuales)
presion_simulada_kPa = PRESION_INICIAL
temperatura_simulada = TEMPERATURA_INICIAL

# --- UMBRALES DE PRESIÓN ---
# Límites operativos para el sistema de distribución de vapor
PRESION_ADVERTENCIA_ALTA = 380.0    # kPa - Umbral de advertencia
PRESION_EMERGENCIA_ALTA = 460.0     # kPa - Activación automática de ESD
PRESION_OBJETIVO_ALIVIO = 350       # kPa - Valor objetivo tras alivio

# Umbrales para presión baja (recuperación del sistema)
PRESION_ADVERTENCIA_BAJA = 250.0    # kPa - Advertencia por baja presión
PRESION_RECUPERACION = 220.0        # kPa - Activación de recuperación

# --- UMBRALES DE TEMPERATURA ---
# Límites térmicos para garantizar calidad del vapor
TEMPERATURA_ADVERTENCIA_ALTA = 170.0    # °C - Umbral de advertencia
TEMPERATURA_EMERGENCIA_ALTA = 190.0     # °C - Activación automática de ESD
TEMPERATURA_ACTIVACION_PURGA = 180.0    # °C - Activación de purga (no usado actualmente)

# Umbrales para temperatura baja (precalentamiento)
TEMPERATURA_ADVERTENCIA_BAJA = 120.0    # °C - Advertencia por baja temperatura
TEMPERATURA_PRECALENTAMIENTO = 110.0    # °C - Activación de precalentamiento

# --- TOLERANCIAS PARA MODO ESD ---
# Márgenes aceptables para considerar que se alcanzaron los valores iniciales
TOLERANCIA_PRESION_ESD = 5.0        # kPa - Tolerancia para presión
TOLERANCIA_TEMPERATURA_ESD = 3.0     # °C - Tolerancia para temperatura

# --- PARÁMETROS DE CONTROL ---
# Rangos y configuraciones para válvulas y supercalentador
VALVULA_MODULANTE_MIN = 0.0      # % - Apertura mínima válvula modulante
VALVULA_MODULANTE_MAX = 100.0    # % - Apertura máxima válvula modulante
porcentaje_valvula_modulante = 50.0  # % - Valor actual

SUPERCALENTADOR_MIN = 0.0        # % - Potencia mínima supercalentador
SUPERCALENTADOR_MAX = 100.0      # % - Potencia máxima supercalentador
comando_supercalentador = 50.0   # % - Valor actual

# Sensibilidades del encoder para ajuste de parámetros
SENSIBILIDAD_ENCODER_PRESION = 2.0       # Incremento por detent en modo presión
SENSIBILIDAD_ENCODER_TEMPERATURA = 1.0  # Incremento por detent en modo temperatura

# --- MODOS DE OPERACIÓN ---
# El encoder permite alternar entre control de presión y temperatura
modo_actual = 0  # 0 = Presión, 1 = Temperatura
NOMBRES_MODOS = ("PRESION", "TEMPERATURA")

# --- ESTADOS DE SEGURIDAD DEL SISTEMA ---
# Flags para modos especiales de operación
recuperacion_presion_activa = False  # Modo de recuperación por baja presión
precalentamiento_activo = False      # Modo de precalentamiento por baja temperatura

# --- VARIABLES DE CONTROL DE INTERFAZ ---
# Manejo de botones y temporización
ultimo_estado_boton_encoder = boton_encoder.value
ultimo_tiempo_boton_encoder = time.monotonic()
TIEMPO_DEBOUNCE_MS = 120  # Tiempo de anti-rebote para botón

# Variables del sistema ESD
esd_activo = False                           # Estado del sistema de paro de emergencia
ultimo_estado_boton_esd = boton_esd.value   # Estado previo del botón ESD
esd_listo_para_reinicio = False             # Flag que indica si se puede reiniciar

# --- VARIABLES DE TEMPORIZACIÓN ---
ultimo_tiempo_actualizacion = time.monotonic()
ultimo_log = time.monotonic()
tiempo_inicio_standby = 0
duracion_standby = 3.0  # Segundos de pausa tras activación de válvulas
tiempo_inicio = time.monotonic()

ultima_posicion_encoder = encoder.position

# =================================================================
# FUNCIONES AUXILIARES
# =================================================================

def configurar_pwm_porcentaje(objeto_pwm, porcentaje):
    """
    Configura la salida PWM según un porcentaje (0-100%)
    
    Args:
        objeto_pwm: Objeto PWMOut a configurar
        porcentaje: Valor entre 0 y 100
    """
    porcentaje = max(0.0, min(100.0, porcentaje))
    objeto_pwm.duty_cycle = int(porcentaje / 100.0 * 65535)

def configurar_rgb(rojo, verde, azul):
    """
    Configura el color del LED RGB
    
    Args:
        rojo, verde, azul: Valores entre 0-255 para cada canal
    """
    rgb_rojo.duty_cycle = int((rojo / 255.0) * 65535)
    rgb_verde.duty_cycle = int((verde / 255.0) * 65535)
    rgb_azul.duty_cycle = int((azul / 255.0) * 65535)

# =================================================================
# INICIO DEL PROGRAMA PRINCIPAL
# =================================================================

print("VaporSur S.A. - Sistema de Control y Supervisión")
print("Iniciando firmware de control de vapor...")

# =================================================================
# BUCLE PRINCIPAL DEL SISTEMA
# =================================================================

while True:
    # --- ACTUALIZACIÓN DE TEMPORIZACIÓN ---
    tiempo_actual = time.monotonic()
    delta_tiempo = (tiempo_actual - ultimo_tiempo_actualizacion) / 2.0
    ultimo_tiempo_actualizacion = tiempo_actual

    # Pausa durante período de standby (tras activación de válvulas)
    if tiempo_actual < tiempo_inicio_standby + duracion_standby:
        time.sleep(0.05)
        continue

    # =============================================================
    # GESTIÓN DEL SISTEMA ESD (EMERGENCY SHUTDOWN)
    # =============================================================
    
    # Detección de pulsación del botón ESD
    estado_boton_esd = boton_esd.value
    if estado_boton_esd != ultimo_estado_boton_esd and not estado_boton_esd:
        # Flanco de bajada detectado (botón pulsado)
        if not esd_activo:
            # Activar ESD
            esd_activo = True
            esd_listo_para_reinicio = False
            print("[ALERTA] Sistema ESD activado manualmente.")
        elif esd_listo_para_reinicio:
            # Reiniciar sistema (solo si está listo)
            esd_activo = False
            print("[INFO] Sistema ESD reiniciado. Retornando a operación normal.")
    ultimo_estado_boton_esd = estado_boton_esd

    # =============================================================
    # LÓGICA DE OPERACIÓN NORMAL
    # =============================================================
    
    if not esd_activo:
        # --- LECTURA DEL ENCODER ROTATIVO ---
        posicion_encoder_actual = encoder.position
        delta_posicion = posicion_encoder_actual - ultima_posicion_encoder
        ultima_posicion_encoder = posicion_encoder_actual
        
        estado_sistema = "Normal"
        
        # --- VERIFICACIÓN DE CONDICIONES CRÍTICAS ---
        # Activación automática de ESD si se superan límites de emergencia
        if presion_simulada_kPa >= PRESION_EMERGENCIA_ALTA or temperatura_simulada >= TEMPERATURA_EMERGENCIA_ALTA:
            esd_activo = True
            esd_listo_para_reinicio = False
            print("[ALERTA] Condición crítica detectada. Activando ESD automáticamente.")
        
        # Solo continuar con operación normal si ESD no se activó automáticamente
        if not esd_activo:
            # --- GESTIÓN DE MODOS ESPECIALES DE SEGURIDAD ---
            
            # Activación del modo de recuperación de presión
            if presion_simulada_kPa <= PRESION_RECUPERACION and not recuperacion_presion_activa:
                recuperacion_presion_activa = True
                print("[INFO] Activando modo de recuperación de presión.")
            
            # Activación del modo de precalentamiento
            if temperatura_simulada <= TEMPERATURA_PRECALENTAMIENTO and not precalentamiento_activo:
                precalentamiento_activo = True
                print("[INFO] Activando modo de precalentamiento.")

            # Desactivación de modos especiales cuando se superan los umbrales
            if recuperacion_presion_activa and presion_simulada_kPa > PRESION_RECUPERACION + 20:
                recuperacion_presion_activa = False
                print("[INFO] Finalizando modo de recuperación de presión.")

            if precalentamiento_activo and temperatura_simulada > TEMPERATURA_PRECALENTAMIENTO + 20:
                precalentamiento_activo = False
                print("[INFO] Finalizando modo de precalentamiento.")
                
            # --- CONTROL MANUAL CON ENCODER ---
            # Solo permitir ajustes manuales si no hay modos especiales activos
            if not recuperacion_presion_activa and not precalentamiento_activo:
                if modo_actual == 0:  # Modo control de presión
                    porcentaje_valvula_modulante += delta_posicion * SENSIBILIDAD_ENCODER_PRESION
                    porcentaje_valvula_modulante = max(VALVULA_MODULANTE_MIN, 
                                                     min(VALVULA_MODULANTE_MAX, porcentaje_valvula_modulante))
                else:  # Modo control de temperatura
                    comando_supercalentador += delta_posicion * SENSIBILIDAD_ENCODER_TEMPERATURA
                    comando_supercalentador = max(SUPERCALENTADOR_MIN, 
                                                min(SUPERCALENTADOR_MAX, comando_supercalentador))

            # --- APLICACIÓN DE MODOS ESPECIALES ---
            
            # Modo recuperación de presión: cerrar válvula modulante
            if recuperacion_presion_activa:
                porcentaje_valvula_modulante = 0.0
                estado_sistema = "Recuperación Presión"
            
            # Modo precalentamiento: máxima potencia al supercalentador
            if precalentamiento_activo:
                comando_supercalentador = 100.0
                estado_sistema = "Precalentamiento"

            # --- APLICACIÓN DE COMANDOS A HARDWARE ---
            configurar_pwm_porcentaje(pwm_valvula_modulante, porcentaje_valvula_modulante)
            configurar_pwm_porcentaje(pwm_supercalentador, comando_supercalentador)

            # --- SIMULACIÓN DE LA FÍSICA DEL SISTEMA ---
            
            # Simulación de presión basada en posición de válvula modulante
            # Válvula cerrada (0%) aumenta presión, válvula abierta (>50%) la reduce
            if porcentaje_valvula_modulante < 50.0:
                presion_simulada_kPa += (50.0 - porcentaje_valvula_modulante) * delta_tiempo * 0.1
            elif porcentaje_valvula_modulante > 50.0:
                presion_simulada_kPa -= (porcentaje_valvula_modulante - 50.0) * delta_tiempo * 0.1
            
            # Simulación de temperatura basada en comando del supercalentador
            # Potencia alta (>50%) aumenta temperatura, potencia baja la reduce
            if comando_supercalentador > 50.0:
                temperatura_simulada += (comando_supercalentador - 50.0) * delta_tiempo * 0.1
            elif comando_supercalentador < 50.0:
                temperatura_simulada -= (50.0 - comando_supercalentador) * delta_tiempo * 0.1

            # Limitación de valores mínimos
            presion_simulada_kPa = max(presion_simulada_kPa, 0)
            temperatura_simulada = max(temperatura_simulada, 0)

            # --- GESTIÓN DEL CAMBIO DE MODO CON BOTÓN DEL ENCODER ---
            estado_boton = boton_encoder.value
            if estado_boton != ultimo_estado_boton_encoder:
                ultimo_tiempo_boton_encoder = tiempo_actual
                ultimo_estado_boton_encoder = estado_boton
            else:
                # Botón presionado y tiempo de debounce superado
                if (not estado_boton) and (tiempo_actual - ultimo_tiempo_boton_encoder) * 1000.0 > TIEMPO_DEBOUNCE_MS:
                    # Cambiar modo de control
                    modo_actual = 1 - modo_actual
                    
                    # Indicación visual del cambio de modo
                    if modo_actual == 0:  # Modo presión
                        for _ in range(2):
                            configurar_rgb(255, 255, 255); time.sleep(0.08)  # Blanco
                            configurar_rgb(0, 160, 0); time.sleep(0.06)      # Verde
                        print("[INFO] Cambiado a modo control de PRESIÓN")
                    else:  # Modo temperatura
                        for _ in range(2):
                            configurar_rgb(0, 120, 200); time.sleep(0.08)    # Azul
                            configurar_rgb(0, 160, 0); time.sleep(0.06)      # Verde
                        print("[INFO] Cambiado a modo control de TEMPERATURA")
                    
                    time.sleep(0.15)  # Pausa para evitar múltiples cambios
                    ultimo_tiempo_boton_encoder = tiempo_actual

            # --- GESTIÓN DE VÁLVULAS DE SEGURIDAD ---
            # Inicialización de estados
            valvula_alivio.value = False
            estado_alivio = "No"
            sistema_purga_a.value = False
            estado_purga = "No"
            
            # NOTA: La lógica original de activación automática de válvulas fue removida
            # para evitar reducciones forzadas de presión/temperatura
            # Las válvulas solo se activan en modo ESD
            
            # --- SEÑALIZACIÓN LUMINOSA SEGÚN ESTADO DEL SISTEMA ---
            
            if valvula_alivio.value or sistema_purga_a.value:
                # Rojo: Válvulas de emergencia activas
                configurar_rgb(200, 0, 0)
            elif recuperacion_presion_activa or precalentamiento_activo:
                # Cian: Modos especiales de seguridad activos
                configurar_rgb(0, 255, 255)
            elif modo_actual == 0:  # Modo control de presión
                if presion_simulada_kPa >= PRESION_ADVERTENCIA_ALTA or presion_simulada_kPa <= PRESION_ADVERTENCIA_BAJA:
                    # Ámbar: Advertencia de presión
                    configurar_rgb(200, 140, 0)
                    estado_sistema = "Advertencia Presión"
                else:
                    # Verde: Operación normal
                    configurar_rgb(0, 160, 0)
                    estado_sistema = "Normal"
            elif modo_actual == 1:  # Modo control de temperatura
                if temperatura_simulada >= TEMPERATURA_EMERGENCIA_ALTA or temperatura_simulada <= TEMPERATURA_ADVERTENCIA_BAJA:
                    # Rojo: Corrección crítica de temperatura
                    configurar_rgb(200, 0, 0)
                    estado_sistema = "Corrección Temperatura"
                elif temperatura_simulada >= TEMPERATURA_ADVERTENCIA_ALTA:
                    # Ámbar: Advertencia de temperatura
                    configurar_rgb(200, 140, 0)
                    estado_sistema = "Advertencia Temperatura"
                else:
                    # Verde: Operación normal
                    configurar_rgb(0, 160, 0)
                    estado_sistema = "Normal"

            # --- GESTIÓN DE FLUJOS DE DISTRIBUCIÓN ---
            # Determinación del tipo de flujo según condiciones de presión y temperatura
            
            estado_flujo = "None"
            led_flujo_encendido = False

            # Solo evaluar flujos si no hay modos especiales activos
            if not recuperacion_presion_activa and not precalentamiento_activo:
                # Flujo A: Procesos que requieren grandes volúmenes a presión constante
                if (presion_simulada_kPa >= 310 and presion_simulada_kPa <= 350) and \
                   (temperatura_simulada >= 140 and temperatura_simulada <= 160):
                    estado_flujo = "A"
                    # LED parpadeante para Flujo A
                    if int(tiempo_actual * 5) % 2 == 0:
                        led_flujo_encendido = True
                    else:
                        led_flujo_encendido = False
                        
                # Flujo B: Procesos sensibles que requieren vapor seco y temperatura regulada
                elif (presion_simulada_kPa >= 260 and presion_simulada_kPa <= 300) and \
                     (temperatura_simulada >= 160 and temperatura_simulada <= 170):
                    estado_flujo = "B"
                    led_flujo_encendido = True  # LED continuo para Flujo B
                else:
                    # Sin flujo: Condiciones no apropiadas para distribución
                    estado_flujo = "None"
                    led_flujo_encendido = False
            
            # Aplicar estado del LED de flujo
            led_flujo.value = led_flujo_encendido
            
            # El láser se enciende cuando hay válvulas de seguridad activas
            laser_indicador.value = valvula_alivio.value or sistema_purga_a.value

    # =============================================================
    # LÓGICA DEL MODO ESD (EMERGENCY SHUTDOWN)
    # =============================================================
    
    if esd_activo:
        # Obtener valores actuales para control
        presion_actual = presion_simulada_kPa
        temperatura_actual = temperatura_simulada
        estado_sistema = "No Listo para el Reinicio"
        estado_alivio = "No"
        estado_purga = "No"
        
        # --- CONTROL AUTOMÁTICO DE PRESIÓN EN MODO ESD ---
        # Objetivo: Retornar a la presión inicial (300 kPa)
        if abs(presion_actual - PRESION_INICIAL) > TOLERANCIA_PRESION_ESD:
            if presion_actual > PRESION_INICIAL:
                # Presión alta: Activar válvula de alivio
                valvula_alivio.value = True
                estado_alivio = "Si"
                porcentaje_valvula_modulante = 50.0  # Posición neutra
                # Reducción acelerada de presión
                presion_simulada_kPa -= (presion_actual - PRESION_INICIAL) * delta_tiempo * 0.2
            else:
                # Presión baja: Cerrar válvula modulante para aumentar presión
                valvula_alivio.value = False
                estado_alivio = "No"
                porcentaje_valvula_modulante = 0.0  # Válvula cerrada
        else:
            # Presión dentro de tolerancia: Estado normal
            valvula_alivio.value = False
            estado_alivio = "No"
            porcentaje_valvula_modulante = 50.0  # Posición neutra
            
        # --- CONTROL AUTOMÁTICO DE TEMPERATURA EN MODO ESD ---
        # Objetivo: Retornar a la temperatura inicial (150°C)
        if abs(temperatura_actual - TEMPERATURA_INICIAL) > TOLERANCIA_TEMPERATURA_ESD:
            if temperatura_actual > TEMPERATURA_INICIAL:
                # Temperatura alta: Activar purga y reducir supercalentador
                sistema_purga_a.value = True
                estado_purga = "Si"
                comando_supercalentador = 50.0  # Potencia neutra
                # Reducción acelerada de temperatura
                temperatura_simulada -= (temperatura_actual - TEMPERATURA_INICIAL) * delta_tiempo * 0.2
            else:
                # Temperatura baja: Aumentar potencia del supercalentador
                sistema_purga_a.value = False
                estado_purga = "No"
                comando_supercalentador = 100.0  # Máxima potencia
        else:
            # Temperatura dentro de tolerancia: Estado normal
            sistema_purga_a.value = False
            estado_purga = "No"
            comando_supercalentador = 50.0  # Potencia neutra

        # --- VERIFICACIÓN DE CONDICIONES PARA REINICIO ---
        # El sistema está listo para reinicio cuando ambas variables están en tolerancia
        if abs(presion_simulada_kPa - PRESION_INICIAL) <= TOLERANCIA_PRESION_ESD and \
           abs(temperatura_simulada - TEMPERATURA_INICIAL) <= TOLERANCIA_TEMPERATURA_ESD:
            esd_listo_para_reinicio = True
            estado_sistema = "Listo para el Reinicio"
            
        # --- CONTINUACIÓN DE LA SIMULACIÓN FÍSICA EN MODO ESD ---
        # La simulación continúa pero con control automático
        
        if porcentaje_valvula_modulante < 50.0:
            presion_simulada_kPa += (50.0 - porcentaje_valvula_modulante) * delta_tiempo * 0.1
        elif porcentaje_valvula_modulante > 50.0 and not valvula_alivio.value:
            presion_simulada_kPa -= (porcentaje_valvula_modulante - 50.0) * delta_tiempo * 0.1
        
        if comando_supercalentador > 50.0 and not sistema_purga_a.value:
            temperatura_simulada += (comando_supercalentador - 50.0) * delta_tiempo * 0.1
        elif comando_supercalentador < 50.0:
            temperatura_simulada -= (50.0 - comando_supercalentador) * delta_tiempo * 0.1

        # Limitación de valores mínimos
        presion_simulada_kPa = max(presion_simulada_kPa, 0)
        temperatura_simulada = max(temperatura_simulada, 0)

        # --- SEÑALIZACIÓN LUMINOSA EN MODO ESD ---
        if esd_listo_para_reinicio:
            # Verde sólido: Sistema listo para reinicio
            configurar_rgb(0, 160, 0)
        else:
            # Rojo parpadeante: Sistema en proceso de estabilización
            if int(tiempo_actual * 2) % 2 == 0:
                configurar_rgb(200, 0, 0)  # Rojo
            else:
                configurar_rgb(0, 0, 0)    # Apagado
        
        # En modo ESD no hay flujo de distribución
        led_flujo.value = False
        
        # El láser indica válvulas activas
        laser_indicador.value = valvula_alivio.value or sistema_purga_a.value

    # =============================================================
    # REGISTRO Y MONITOREO DEL SISTEMA
    # =============================================================
    
    # Envío periódico de datos al puerto serial para monitoreo
    if tiempo_actual - ultimo_log > 0.1:  # Cada 100ms
        datos_salida = "P:{:.1f},T:{:.1f},MV:{:.1f},SH:{:.1f},F:{},M:{},ESD:{},ESTADO:{},RELIEF:{},PURGE:{}".format(
            presion_simulada_kPa,           # Presión actual (kPa)
            temperatura_simulada,           # Temperatura actual (°C)
            porcentaje_valvula_modulante,   # Apertura válvula modulante (%)
            comando_supercalentador,        # Potencia supercalentador (%)
            estado_flujo if 'estado_flujo' in locals() else "None",  # Tipo de flujo activo
            NOMBRES_MODOS[modo_actual],     # Modo de control actual
            "Activado" if esd_activo else "Desactivado",  # Estado ESD
            estado_sistema,                 # Estado general del sistema
            estado_alivio,                  # Estado válvula de alivio
            estado_purga                    # Estado sistema de purga
        )
        print(datos_salida)
        ultimo_log = tiempo_actual
        
    # Pausa para no saturar el procesador
    time.sleep(0.01)