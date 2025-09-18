import serial
import time
import random
import math
import threading
from serial.tools import list_ports

class VirtualSerialPort:
    """Puerto serial virtual que simula las respuestas del Raspberry Pi Pico 2 W"""
    
    def __init__(self, port_name="COM_VIRTUAL", baudrate=115200, timeout=1):
        self.port_name = port_name
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = True
        self.data_queue = []
        self.running = True
        
        # Parámetros de simulación
        self.time_counter = 0
        self.current_state = "Normal"
        self.current_flow = "A"
        self.current_mode = "Presión"
        
        # Variables base para simulación realista
        self.base_pressure = 320.0  # kPa
        self.base_temperature = 150.0  # °C
        self.base_mv = 45.0  # %
        self.base_sh = 15.0  # %
        
        # Estados del sistema
        self.esd_active = False
        self.relief_valve = False
        self.purge_valve = False
        
        # Patrones de simulación
        self.simulation_phase = "normal"  # normal, warning, emergency, recovery
        self.phase_timer = 0
        self.phase_duration = 300  # 30 segundos por fase
        
        # Iniciar hilo de generación de datos
        self.data_thread = threading.Thread(target=self._generate_data)
        self.data_thread.daemon = True
        self.data_thread.start()
    
    def _generate_data(self):
        """Genera datos de manera continua"""
        while self.running:
            # Actualizar fase de simulación
            self._update_simulation_phase()
            
            # Generar datos según la fase actual
            data = self._create_data_packet()
            
            # Formatear como string que enviaría el Pico
            data_string = self._format_data(data)
            self.data_queue.append(data_string)
            
            # Mantener cola limitada
            if len(self.data_queue) > 100:
                self.data_queue.pop(0)
            
            time.sleep(0.1)  # 10 Hz de frecuencia de datos
    
    def _update_simulation_phase(self):
        """Actualiza la fase de simulación para crear escenarios dinámicos"""
        self.phase_timer += 1
        
        if self.phase_timer >= self.phase_duration:
            self.phase_timer = 0
            phases = ["normal", "warning_high_p", "warning_high_t", "flow_change", "recovery"]
            self.simulation_phase = random.choice(phases)
            print(f"[SIMULADOR] Cambiando a fase: {self.simulation_phase}")
    
    def _create_data_packet(self):
        """Crea un paquete de datos realista según la fase actual"""
        self.time_counter += 0.1
        
        # Variaciones base con ruido
        noise_p = random.uniform(-5, 5)
        noise_t = random.uniform(-2, 2)
        noise_mv = random.uniform(-2, 2)
        noise_sh = random.uniform(-1, 1)
        
        # Variaciones sinusoidales para simular oscilaciones del sistema
        sin_variation = math.sin(self.time_counter * 0.1) * 10
        
        if self.simulation_phase == "normal":
            pressure = self.base_pressure + sin_variation + noise_p
            temperature = self.base_temperature + sin_variation * 0.5 + noise_t
            mv = self.base_mv + noise_mv
            sh = self.base_sh + noise_sh
            estado = "Normal"
            self.current_flow = "A" if pressure > 330 else "B"
            
        elif self.simulation_phase == "warning_high_p":
            pressure = 385 + sin_variation + noise_p  # Cerca del límite de advertencia
            temperature = self.base_temperature + noise_t
            mv = 65 + noise_mv
            sh = self.base_sh + noise_sh
            estado = "Advertencia Presión Alta"
            
        elif self.simulation_phase == "warning_high_t":
            pressure = self.base_pressure + noise_p
            temperature = 175 + sin_variation * 0.3 + noise_t  # Cerca del límite de advertencia
            mv = self.base_mv + noise_mv
            sh = 25 + noise_sh
            estado = "Advertencia Temperatura Alta"
            
        elif self.simulation_phase == "flow_change":
            # Simular cambio entre flujos
            if self.phase_timer % 60 < 30:  # Cada 6 segundos cambiar
                pressure = 280 + sin_variation + noise_p
                temperature = 165 + noise_t
                self.current_flow = "B"
            else:
                pressure = 340 + sin_variation + noise_p
                temperature = 145 + noise_t
                self.current_flow = "A"
            mv = self.base_mv + noise_mv
            sh = self.base_sh + noise_sh
            estado = f"Flujo {self.current_flow}"
            
        elif self.simulation_phase == "recovery":
            pressure = 225 + sin_variation + noise_p  # Presión de recuperación
            temperature = 115 + noise_t  # Temperatura de precalentamiento
            mv = 25 + noise_mv
            sh = 8 + noise_sh
            estado = "Recuperación"
            
        else:  # emergency
            pressure = 470 + noise_p  # Presión de emergencia
            temperature = 195 + noise_t  # Temperatura de emergencia
            mv = 85 + noise_mv
            sh = 40 + noise_sh
            estado = "Emergencia"
            self.esd_active = True
            self.relief_valve = True
        
        # Lógica de válvulas basada en condiciones
        if pressure > 460:
            self.esd_active = True
            self.relief_valve = True
            estado = "Alivio Activado"
        elif pressure < 230:
            self.purge_valve = random.choice([True, False])
            if self.purge_valve:
                estado = "Purga Activada"
        else:
            self.relief_valve = False
            self.purge_valve = False
            if pressure > 250:
                self.esd_active = False
        
        # Determinar modo de operación
        if temperature < 120:
            self.current_mode = "Precalentamiento"
        elif abs(pressure - self.base_pressure) > abs(temperature - self.base_temperature):
            self.current_mode = "Presión"
        else:
            self.current_mode = "Temperatura"
        
        return {
            'P': round(pressure, 1),
            'T': round(temperature, 1),
            'MV': round(mv, 1),
            'SH': round(sh, 1),
            'F': self.current_flow,
            'M': self.current_mode,
            'ESD': 'Activado' if self.esd_active else 'Desactivado',
            'ESTADO': estado,
            'RELIEF': 'Si' if self.relief_valve else 'No',
            'PURGE': 'Si' if self.purge_valve else 'No'
        }
    
    def _format_data(self, data):
        """Formatea los datos en el formato esperado por el plotter"""
        return f"P:{data['P']},T:{data['T']},MV:{data['MV']},SH:{data['SH']},F:{data['F']},M:{data['M']},ESD:{data['ESD']},ESTADO:{data['ESTADO']},RELIEF:{data['RELIEF']},PURGE:{data['PURGE']}\n"
    
    def readline(self):
        """Simula readline() del puerto serial"""
        while self.running and len(self.data_queue) == 0:
            time.sleep(0.01)
        
        if len(self.data_queue) > 0:
            data = self.data_queue.pop(0)
            return data.encode('utf-8')
        return b""
    
    def close(self):
        """Cierra el puerto virtual"""
        self.running = False
        self.is_open = False
        if self.data_thread.is_alive():
            self.data_thread.join()

class PicoSimulator:
    """Simulador principal que intercepta las conexiones seriales"""
    
    def __init__(self):
        self.virtual_ports = {}
        print("[SIMULADOR] Raspberry Pi Pico 2 W Simulator iniciado")
        print("[SIMULADOR] Este simulador interceptará las conexiones seriales")
        print("[SIMULADOR] Presiona Ctrl+C para detener")
    
    def create_virtual_port(self, port_name):
        """Crea un puerto serial virtual"""
        if port_name not in self.virtual_ports:
            self.virtual_ports[port_name] = VirtualSerialPort(port_name)
            print(f"[SIMULADOR] Puerto virtual creado: {port_name}")
        return self.virtual_ports[port_name]
    
    def cleanup(self):
        """Limpia todos los puertos virtuales"""
        for port in self.virtual_ports.values():
            port.close()
        print("[SIMULADOR] Puertos virtuales cerrados")

# Monkey patch para interceptar serial.Serial
original_serial_init = serial.Serial.__init__
original_list_ports = list_ports.comports

# Instancia global del simulador
simulator = PicoSimulator()

def patched_serial_init(self, port=None, baudrate=9600, **kwargs):
    """Versión patcheada de Serial.__init__ que devuelve nuestro puerto virtual"""
    print(f"[SIMULADOR] Interceptando conexión serial a: {port}")
    
    # Crear puerto virtual
    virtual_port = simulator.create_virtual_port(f"VIRTUAL_{port}")
    
    # Copiar atributos necesarios
    self.port = port
    self.baudrate = baudrate
    self.timeout = kwargs.get('timeout', 1)
    self._virtual_port = virtual_port
    
    # Redirigir métodos
    self.readline = virtual_port.readline
    self.close = virtual_port.close
    self.is_open = True

def patched_list_ports():
    """Versión patcheada que devuelve puertos simulados"""
    print("[SIMULADOR] Listando puertos simulados")
    
    class MockPort:
        def __init__(self, device):
            self.device = device
            self.description = "Simulador Raspberry Pi Pico 2 W"
            self.hwid = "USB VID:2E8A PID:0005"
    
    # Devolver algunos puertos simulados
    return [MockPort("COM3"), MockPort("COM4")]

# Aplicar los patches
serial.Serial.__init__ = patched_serial_init
list_ports.comports = patched_list_ports

def main():
    """Función principal para ejecutar el simulador de manera independiente"""
    try:
        print("[SIMULADOR] === SIMULADOR RASPBERRY PI PICO 2 W ===")
        print("[SIMULADOR] Generando datos de prueba cada 100ms")
        print("[SIMULADOR] Fases de simulación:")
        print("[SIMULADOR]   - Normal: Operación estándar")
        print("[SIMULADOR]   - Advertencias: Presión/Temperatura altas")
        print("[SIMULADOR]   - Cambios de flujo: Entre A y B")
        print("[SIMULADOR]   - Recuperación: Presión baja")
        print("[SIMULADOR] ")
        print("[SIMULADOR] Ejecuta tu aplicación pc_plotter.py en otra terminal")
        print("[SIMULADOR] Presiona Ctrl+C para detener")
        
        # Crear puerto de ejemplo
        virtual_port = simulator.create_virtual_port("COM_EXAMPLE")
        
        # Mantener el simulador corriendo
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n[SIMULADOR] Deteniendo simulador...")
        simulator.cleanup()
        print("[SIMULADOR] Simulador detenido")

if __name__ == "__main__":
    main()