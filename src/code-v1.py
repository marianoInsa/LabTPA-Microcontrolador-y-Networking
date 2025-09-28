# code.py - VaporSur S.A. (CircuitPython)
# Lógica de seguridad para ESD redefinida para control de retorno a valores iniciales.

import board
import digitalio
import rotaryio
import pwmio
import time
import math
import sys

# ----------------- PIN CONFIG -----------------
# Encoder
ENC_CLK = board.GP3   # CLK (A)
ENC_DT = board.GP4    # DT (B)
ENC_SW = board.GP5    # SW (encoder push) -> cambia modo

# E-Stop button (KY-004)
BTN_ESD_PIN = board.GP0

# Outputs
GP_FLOW_LED = board.GP8      # LED simple indicador de flujo
GP_LASER = board.GP9       # Laser control (via transistor)
GP_RELIEF = board.GP10      # Alivio (simulado como DO)
GP_PURGA_A = board.GP11      # Purga A (simulado)
GP_PURGA_B = board.GP12      # Purga B (simulado)

# PWM outputs
PWM_MV_PIN = board.GP6      # Válvula modulante (PWM AO simulado)
PWM_SH_PIN = board.GP7      # Superheater control (PWM)

# RGB LED (cátodo común a GND)
RGB_R_PIN = board.GP13
RGB_G_PIN = board.GP14
RGB_B_PIN = board.GP15

# ----------------- HARDWARE OBJECTS -----------------
encoder = rotaryio.IncrementalEncoder(ENC_CLK, ENC_DT)
enc_sw = digitalio.DigitalInOut(ENC_SW)
enc_sw.direction = digitalio.Direction.INPUT
enc_sw.pull = digitalio.Pull.UP

btn_esd = digitalio.DigitalInOut(BTN_ESD_PIN)
btn_esd.direction = digitalio.Direction.INPUT
btn_esd.pull = digitalio.Pull.UP

def make_do(pin):
    d = digitalio.DigitalInOut(pin)
    d.direction = digitalio.Direction.OUTPUT
    d.value = False
    return d

do_flow = make_do(GP_FLOW_LED)
do_laser = make_do(GP_LASER)
do_relief = make_do(GP_RELIEF)
do_purga_a = make_do(GP_PURGA_A)
do_purga_b = make_do(GP_PURGA_B)

pwm_mv = pwmio.PWMOut(PWM_MV_PIN, frequency=5000, duty_cycle=0)
pwm_sh = pwmio.PWMOut(PWM_SH_PIN, frequency=5000, duty_cycle=0)

rgb_r = pwmio.PWMOut(RGB_R_PIN, frequency=5000, duty_cycle=0)
rgb_g = pwmio.PWMOut(RGB_G_PIN, frequency=5000, duty_cycle=0)
rgb_b = pwmio.PWMOut(RGB_B_PIN, frequency=5000, duty_cycle=0)

# ----------------- COLORES RGB ESTANDARIZADOS -----------------
RGB_GREEN = (0, 255, 0)      # Verde: Estado Normal
RGB_ORANGE = (255, 165, 0)   # Naranja: Advertencias  
RGB_RED = (255, 0, 0)        # Rojo: Emergencias/Crítico
RGB_CYAN = (0, 255, 255)     # Cian: Recuperación/Precalentamiento
RGB_WHITE = (255, 255, 255)  # Blanco: Cambio de modo
RGB_BLUE = (0, 100, 255)     # Azul: Modo temperatura
RGB_OFF = (0, 0, 0)          # Apagado

# ----------------- SIMULATION & CONTROL PARAMETERS -----------------
# Valores iniciales y de destino en modo ESD
P_INITIAL = 300.0
T_INITIAL = 150.0

P_sim_kPa = P_INITIAL
T_sim = T_INITIAL

# Umbrales de Presión
P_WARN_HIGH = 380.0
P_EMERG_HIGH = 460.0
P_RELIEF_TARGET = 350

# Umbrales de seguridad para presión baja
P_WARN_LOW = 250.0  
P_RECOVERY = 220.0  

# Umbrales de Temperatura
T_WARN_HIGH = 170.0
T_EMERG_HIGH = 190.0
T_PURGE_TRIGGER = 180.0

# Umbrales de seguridad para temperatura baja
T_WARN_LOW = 120.0  
T_PREHEAT = 110.0  

# Margen para considerar que se ha alcanzado el valor inicial en modo ESD
ESD_P_TOLERANCE = 5.0
ESD_T_TOLERANCE = 3.0

MV_MIN = 0.0
MV_MAX = 100.0
MV_pct = 50.0

SH_MIN = 0.0
SH_MAX = 100.0
SH_cmd = 50.0

ENC_SENSITIVITY_P = 2.0
ENC_SENSITIVITY_T = 1.0

mode = 0
MODE_NAMES = ("PRESION", "TEMPERATURA")

# Nuevos estados de seguridad
pressure_recovery_active = False
preheat_active = False

last_enc_sw_state = enc_sw.value
last_enc_sw_time = time.monotonic()
SW_DEBOUNCE_MS = 120

esd_active = False
esd_btn_state_last = btn_esd.value
esd_ready_to_reset = False

last_update_time = time.monotonic()
last_log = time.monotonic()
standby_start_time = 0
standby_duration = 3.0
start_time = time.monotonic()

last_enc_pos = encoder.position

def pwm_set_pct(pwm_obj, pct):
    pct = max(0.0, min(100.0, pct))
    pwm_obj.duty_cycle = int(pct / 100.0 * 65535)

def set_rgb(r8, g8, b8):
    rgb_r.duty_cycle = int((r8 / 255.0) * 65535)
    rgb_g.duty_cycle = int((g8 / 255.0) * 65535)
    rgb_b.duty_cycle = int((b8 / 255.0) * 65535)

def set_rgb_color(color_tuple):
    set_rgb(color_tuple[0], color_tuple[1], color_tuple[2])

def determine_system_color(estado_sistema, P_sim_kPa, T_sim, mode, esd_active, esd_ready_to_reset, now):
    # Modo ESD
    if esd_active:
        if esd_ready_to_reset:
            return RGB_GREEN  # Verde: listo para reinicio
        else:
            # Parpadeo rojo en modo ESD
            if int(now * 2) % 2 == 0:
                return RGB_RED
            else:
                return RGB_OFF
    
    # Estados críticos
    if "Alivio" in estado_sistema or "Purga" in estado_sistema:
        return RGB_RED
    
    if "Emergencia" in estado_sistema:
        return RGB_RED
    
    # Estados de recuperación/precalentamiento
    if "Recuperación" in estado_sistema or "Precalentamiento" in estado_sistema:
        return RGB_CYAN
    
    # Estados de advertencia
    if "Advertencia" in estado_sistema:
        return RGB_ORANGE
    
    # Valores criticos
    if P_sim_kPa >= P_EMERG_HIGH:
        return RGB_RED
    
    if T_sim >= T_EMERG_HIGH:
        return RGB_RED
        
    # Advertencias
    if P_sim_kPa >= P_WARN_HIGH or P_sim_kPa <= P_WARN_LOW:
        return RGB_ORANGE
    
    if T_sim >= T_WARN_HIGH or T_sim <= T_WARN_LOW:
        return RGB_ORANGE
    
    # Estado normal
    return RGB_GREEN

print("VaporSur - Iniciando firmware")

while True:
    now = time.monotonic()
    dt = (now - last_update_time) / 2.0
    last_update_time = now

    if now < standby_start_time + standby_duration:
        time.sleep(0.05)
        continue

    # Lógica de detección de pulsación de ESD
    esd_btn_state = btn_esd.value
    if esd_btn_state != esd_btn_state_last and not esd_btn_state: # Detección de flanco de bajada (pulsación)
        if not esd_active:
            esd_active = True
            esd_ready_to_reset = False
            print("[ALERTA] ESD activado.")
        elif esd_ready_to_reset:
            esd_active = False
            print("[INFO] ESD reseteado.")
    esd_btn_state_last = esd_btn_state

    # ----------------- Lógica de operación normal (ahora con verificación de estado crítico) -----------------
    if not esd_active:
        current_enc_pos = encoder.position
        delta_pos = current_enc_pos - last_enc_pos
        last_enc_pos = current_enc_pos
        
        estado_sistema = "Normal"
        
        # Nueva lógica para activar ESD automáticamente
        if P_sim_kPa >= P_EMERG_HIGH or T_sim >= T_EMERG_HIGH:
            esd_active = True
            esd_ready_to_reset = False
            print("[ALERTA] Condición crítica detectada. Activando ESD automáticamente.")
        
        # Solo ejecutar la lógica de operación normal si el ESD no está activo
        if not esd_active:
            if P_sim_kPa <= P_RECOVERY and not pressure_recovery_active:
                pressure_recovery_active = True
            
            if T_sim <= T_PREHEAT and not preheat_active:
                preheat_active = True

            if pressure_recovery_active and P_sim_kPa > P_RECOVERY + 20:
                pressure_recovery_active = False

            if preheat_active and T_sim > T_PREHEAT + 20:
                preheat_active = False
                
            if not pressure_recovery_active and not preheat_active:
                if mode == 0:
                    MV_pct += delta_pos * ENC_SENSITIVITY_P
                    MV_pct = max(MV_MIN, min(MV_MAX, MV_pct))
                else:
                    SH_cmd += delta_pos * ENC_SENSITIVITY_T
                    SH_cmd = max(SH_MIN, min(SH_MAX, SH_cmd))

            if pressure_recovery_active:
                MV_pct = 0.0
                estado_sistema = "Recuperación Presión"
            
            if preheat_active:
                SH_cmd = 100.0
                estado_sistema = "Precalentamiento"

            pwm_set_pct(pwm_mv, MV_pct)
            pwm_set_pct(pwm_sh, SH_cmd)

            if MV_pct < 50.0:
                P_sim_kPa += (50.0 - MV_pct) * dt * 0.1
            elif MV_pct > 50.0:
                P_sim_kPa -= (MV_pct - 50.0) * dt * 0.1
            
            if SH_cmd > 50.0:
                T_sim += (SH_cmd - 50.0) * dt * 0.1
            elif SH_cmd < 50.0:
                T_sim -= (50.0 - SH_cmd) * dt * 0.1

            P_sim_kPa = max(P_sim_kPa, 0)
            T_sim = max(T_sim, 0)

            sw_state = enc_sw.value
            if sw_state != last_enc_sw_state:
                last_enc_sw_time = now
                last_enc_sw_state = sw_state
            else:
                if (not sw_state) and (now - last_enc_sw_time) * 1000.0 > SW_DEBOUNCE_MS:
                    mode = 1 - mode
                    if mode == 0: # Modo Presión
                        for _ in range(3):
                            set_rgb_color(RGB_WHITE)
                            time.sleep(0.08)
                            set_rgb_color(RGB_GREEN)
                            time.sleep(0.06)
                    else: # Modo Temperatura
                        for _ in range(3): 
                            set_rgb_color(RGB_BLUE)
                            time.sleep(0.08)
                            set_rgb_color(RGB_GREEN)
                            time.sleep(0.06)
                    time.sleep(0.15)
                    last_enc_sw_time = now

            do_relief.value = False
            relief_activo = "No"
            do_purga_a.value = False
            purga_activa = "No"

            if mode == 0:  # Modo Presión
                if P_sim_kPa >= P_WARN_HIGH:
                    estado_sistema = "Advertencia Presión Alta"
                elif P_sim_kPa <= P_WARN_LOW:
                    estado_sistema = "Advertencia Presión Baja"
                elif not pressure_recovery_active and not preheat_active:
                    estado_sistema = "Normal"
            else:  # Modo Temperatura
                if T_sim >= T_EMERG_HIGH:
                    estado_sistema = "Emergencia Temperatura"
                elif T_sim >= T_WARN_HIGH:
                    estado_sistema = "Advertencia Temperatura Alta"
                elif T_sim <= T_WARN_LOW:
                    estado_sistema = "Advertencia Temperatura Baja"
                elif not pressure_recovery_active and not preheat_active:
                    estado_sistema = "Normal"

            flow_state = "None"
            flow_led_on = False

            if not pressure_recovery_active and not preheat_active:
                if (P_sim_kPa >= 310 and P_sim_kPa <= 350) and (T_sim >= 140 and T_sim <= 160):
                    flow_state = "A"
                    if int(now * 5) % 2 == 0:
                        flow_led_on = True
                    else:
                        flow_led_on = False
                elif (P_sim_kPa >= 260 and P_sim_kPa <= 300) and (T_sim >= 160 and T_sim <= 170):
                    flow_state = "B"
                    flow_led_on = True
                else:
                    flow_state = "None"
                    flow_led_on = False
            
            do_flow.value = flow_led_on
            do_laser.value = do_relief.value or do_purga_a.value

    # ----------------- Lógica del modo ESD -----------------
    if esd_active:
        current_P = P_sim_kPa
        current_T = T_sim
        estado_sistema = "No Listo para el Reinicio"
        relief_activo = "No"
        purga_activa = "No"
        
        # Lógica de control de presión en modo ESD
        if abs(current_P - P_INITIAL) > ESD_P_TOLERANCE:
            if current_P > P_INITIAL:
                do_relief.value = True
                relief_activo = "Si"
                MV_pct = 50.0
                # Aumentamos la tasa de disminución de la presión
                P_sim_kPa -= (current_P - P_INITIAL) * dt * 0.2 
                estado_sistema = "ESD: Reduciendo Presión"
            else: 
                do_relief.value = False
                relief_activo = "No"
                MV_pct = 0.0
                estado_sistema = "ESD: Aumentando Presión"
        else:
            do_relief.value = False
            relief_activo = "No"
            MV_pct = 50.0
            
        # Lógica de control de temperatura en modo ESD
        if abs(current_T - T_INITIAL) > ESD_T_TOLERANCE:
            if current_T > T_INITIAL:
                do_purga_a.value = True
                purga_activa = "Si"
                SH_cmd = 50.0
                # Aumentamos la tasa de disminución de la temperatura
                T_sim -= (current_T - T_INITIAL) * dt * 0.2
                estado_sistema = "ESD: Reduciendo Temperatura"
            else: 
                do_purga_a.value = False
                purga_activa = "No"
                SH_cmd = 100.0
                estado_sistema = "ESD: Aumentando Temperatura"
        else:
            do_purga_a.value = False
            purga_activa = "No"
            SH_cmd = 50.0

        if abs(P_sim_kPa - P_INITIAL) <= ESD_P_TOLERANCE and abs(T_sim - T_INITIAL) <= ESD_T_TOLERANCE:
            esd_ready_to_reset = True
            estado_sistema = "ESD: Listo para el Reinicio"
            
        if MV_pct < 50.0:
            P_sim_kPa += (50.0 - MV_pct) * dt * 0.1
        elif MV_pct > 50.0 and not do_relief.value:
            P_sim_kPa -= (MV_pct - 50.0) * dt * 0.1
        
        if SH_cmd > 50.0 and not do_purga_a.value:
            T_sim += (SH_cmd - 50.0) * dt * 0.1
        elif SH_cmd < 50.0:
            T_sim -= (50.0 - SH_cmd) * dt * 0.1

        P_sim_kPa = max(P_sim_kPa, 0)
        T_sim = max(T_sim, 0)

        do_flow.value = False
        do_laser.value = do_relief.value or do_purga_a.value

    rgb_color = determine_system_color(estado_sistema, P_sim_kPa, T_sim, mode, esd_active, esd_ready_to_reset, now)
    
    set_rgb_color(rgb_color)

    if now - last_log > 0.1:
        flow_state_var = flow_state if 'flow_state' in locals() else "None"
        output_data = "P:{:.1f},T:{:.1f},MV:{:.1f},SH:{:.1f},F:{},M:{},ESD:{},ESTADO:{},RELIEF:{},PURGE:{}".format(
            P_sim_kPa, T_sim, MV_pct, SH_cmd,
            flow_state_var,
            MODE_NAMES[mode],
            "Activado" if esd_active else "Desactivado",
            estado_sistema,
            relief_activo,
            purga_activa
        )
        print(output_data)
        last_log = now
        
    time.sleep(0.01)