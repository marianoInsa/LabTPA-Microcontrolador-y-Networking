import serial
import serial.tools.list_ports
import matplotlib.pyplot as plt
from collections import deque
import re
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# para simular datos
import threading
import time
import random
import math

# --- Configuración ---
MAX_POINTS = 200
GUI_UPDATE_INTERVAL_MS = 50
DATA_COLLECTION_INTERVAL_MS = 100
PLOT_UPDATE_INTERVAL_MS = 10

# Rangos y umbrales
P_WARN_HIGH = 380.0
P_EMERG_HIGH = 460.0
P_WARN_LOW = 250.0
P_RECOVERY = 220.0

T_WARN_HIGH = 170.0
T_EMERG_HIGH = 190.0
T_WARN_LOW = 120.0
T_PREHEAT = 110.0

FLOW_A_P_RANGE = [310, 350]
FLOW_A_T_RANGE = [140, 160]
FLOW_B_P_RANGE = [260, 300]
FLOW_B_T_RANGE = [160, 170]

# --- Colores unificados ---
COLOR_FLOW_A = '#4A90E2'  # Azul para Flujo A
COLOR_FLOW_B = '#9013FE'  # Violeta para Flujo B
COLOR_ALERT_LINE = 'red'

# ===============================================
#         CODIGO PARA SIMULAR DATOS
# ===============================================
class SimulatedSerial:
    """Puerto serial simulado que genera datos realistas"""
    
    def __init__(self, port, baudrate=115200, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = True
        
        # Generador de datos
        self.time_counter = 0
        self.phase = "normal"
        self.phase_timer = 0
        self.base_pressure = 320.0
        self.base_temperature = 150.0
        self.current_flow = "A"
        self.esd_active = False
        self.relief_valve = False
        self.purge_valve = False

        self.generator_thread = threading.Thread(target=self.generate_data, daemon=True)
        self.generator_running = True
        self.generator_thread.start()

        print(f"[SIMULADOR] Puerto simulado creado: {port}")
    
    def generate_data(self):
        """Genera datos realistas"""
        self.time_counter += 0.1
        self.phase_timer += 1
        
        # Cambiar fase cada 300 iteraciones (30 segundos a 100ms)
        if self.phase_timer >= 300:
            self.phase_timer = 0
            phases = ["normal", "warning_p", "warning_t", "flow_change", "recovery"]
            old_phase = self.phase
            self.phase = random.choice(phases)
            if self.phase != old_phase:
                print(f"[SIMULADOR] Nueva fase: {self.phase}")
        
        # Ruido y variaciones
        noise_p = random.uniform(-3, 3)
        noise_t = random.uniform(-1.5, 1.5)
        sin_wave = math.sin(self.time_counter * 0.05) * 8
        
        # Generar datos según fase actual
        if self.phase == "normal":
            pressure = self.base_pressure + sin_wave + noise_p
            temperature = self.base_temperature + sin_wave * 0.4 + noise_t
            mv = 45 + random.uniform(-3, 3)
            sh = 15 + random.uniform(-2, 2)
            estado = "Normal"
            self.current_flow = "A" if pressure > 330 else "B"
            
        elif self.phase == "warning_p":
            pressure = 385 + sin_wave * 0.3 + noise_p
            temperature = self.base_temperature + noise_t
            mv = 65 + random.uniform(-5, 5)
            sh = 20 + random.uniform(-3, 3)
            estado = "Advertencia Presión Alta"
            
        elif self.phase == "warning_t":
            pressure = self.base_pressure + noise_p
            temperature = 175 + sin_wave * 0.2 + noise_t
            mv = 50 + random.uniform(-3, 3)
            sh = 25 + random.uniform(-2, 2)
            estado = "Advertencia Temperatura Alta"
            
        elif self.phase == "flow_change":
            if self.phase_timer % 80 < 40:
                pressure = 280 + noise_p
                temperature = 165 + noise_t
                self.current_flow = "B"
            else:
                pressure = 340 + noise_p
                temperature = 145 + noise_t
                self.current_flow = "A"
            mv = 40 + random.uniform(-5, 5)
            sh = 12 + random.uniform(-2, 2)
            estado = f"Flujo {self.current_flow}"
            
        elif self.phase == "recovery":
            pressure = 230 + sin_wave * 0.5 + noise_p
            temperature = 118 + noise_t
            mv = 25 + random.uniform(-3, 3)
            sh = 8 + random.uniform(-1, 1)
            estado = "Recuperación"
        
        # Lógica de válvulas
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
        
        # Determinar modo
        if temperature < 120:
            mode = "Precalentamiento"
        elif abs(pressure - self.base_pressure) > abs(temperature - self.base_temperature):
            mode = "Presión"
        else:
            mode = "Temperatura"
        
        # Formatear datos
        data_dict = {
            'P': round(pressure, 1),
            'T': round(temperature, 1),
            'MV': round(mv, 1),
            'SH': round(sh, 1),
            'F': self.current_flow,
            'M': mode,
            'ESD': 'Activado' if self.esd_active else 'Desactivado',
            'ESTADO': estado,
            'RELIEF': 'Si' if self.relief_valve else 'No',
            'PURGE': 'Si' if self.purge_valve else 'No'
        }
        
        return f"P:{data_dict['P']},T:{data_dict['T']},MV:{data_dict['MV']},SH:{data_dict['SH']},F:{data_dict['F']},M:{data_dict['M']},ESD:{data_dict['ESD']},ESTADO:{data_dict['ESTADO']},RELIEF:{data_dict['RELIEF']},PURGE:{data_dict['PURGE']}\n"
    
    def readline(self):
        """Simula readline del puerto serial"""
        data = self.generate_data()
        return data.encode('utf-8')
    
    def close(self):
        """Simula el cierre del puerto"""
        self.generator_running = False
        self.is_open = False
        if self.generator_thread.is_alive():
            self.generator_thread.join(timeout=1)
        print("[SIMULADOR] Puerto simulado cerrado")

# ===============================================
#         FIN DEL CODIGO DEL SIMULADOR
# ===============================================


# ===============================================
#         LECTURA SERIAL
# ===============================================
class SerialReader(QThread):
    data_received = pyqtSignal(dict)

    def __init__(self, port, parent=None):
        QThread.__init__(self, parent)

        # self.ser = serial.Serial(port, 115200, timeout=1)
        self.ser = SimulatedSerial(port, 115200, timeout=1)
        self.running = True
        print(f"[SIMULADOR] Conectado al puerto simulado: {port}")

    def run(self):
        while self.running:
            try:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                data = self.parse_data(line)
                if data:
                    self.data_received.emit(data)
                # [SIMULADOR] Agrego un tiempo entre lecturas de 100ms
                time.sleep(0.1)
            # except serial.SerialException as e:
            #     print(f"Error de lectura serial: {e}")
            #     self.running = False
            except Exception as e:
                print(f"Error inesperado: {e}")
                continue

    def stop(self):
        self.running = False
        self.ser.close()

    def parse_data(self, line):
        # Expresión regular para capturar todos los campos
        match = re.search(r"P:([\d.-]+),T:([\d.-]+),MV:([\d.-]+),SH:([\d.-]+),F:(\w+),M:(\w+),ESD:(\w+),ESTADO:([\w\s]+),RELIEF:(\w+),PURGE:(\w+)", line)
        if match:
            return {
                'P': float(match.group(1)),
                'T': float(match.group(2)),
                'MV': float(match.group(3)),
                'SH': float(match.group(4)),
                'F': match.group(5),
                'M': match.group(6),
                'ESD': match.group(7),
                'ESTADO': match.group(8),
                'RELIEF': match.group(9),
                'PURGE': match.group(10)
            }
        return None

# --- Ventana PyQt5 ---
class PlotterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('VaporSur S.A. - Monitoreo del Sistema')
        self.layout = QVBoxLayout(self)

        # Figura matplotlib con autoajuste
        self.fig = plt.figure(figsize=(10, 8), constrained_layout=True)
        gs = gridspec.GridSpec(2, 1, height_ratios=[1, 1], figure=self.fig)

        self.ax1 = self.fig.add_subplot(gs[0])
        self.ax2 = self.fig.add_subplot(gs[1])

        self.canvas = FigureCanvas(self.fig)
        self.layout.addWidget(self.canvas, stretch=1)

        self.labels = {}
        self.setup_labels()
        self.setLayout(self.layout)

        self.x_data = deque([0])
        self.y1_data = deque([0])
        self.y2_data = deque([0])
        self.line1, self.line2 = self.init_plot(self.ax1, self.ax2)

        self.serial_thread = None
        self.start_serial()

    def start_serial(self):
        # PARA SIMULADOR
        port = "SIMULADO_COM3"
        print(f"[SIMULADOR] Iniciando con puerto simulado: {port}")
        self.serial_thread = SerialReader(port)
        self.serial_thread.data_received.connect(self.update_data)
        self.serial_thread.start()
        
        # port = self.find_port()
        # if port:
        #     print(f"Conectado a {port}")
        #     self.serial_thread = SerialReader(port)
        #     self.serial_thread.data_received.connect(self.update_data)
        #     self.serial_thread.start()
        # else:
        #     print("No se encontró ningún dispositivo CircuitPython. Conéctalo y vuelve a intentar.")
        #     sys.exit(1)
    
    # DESCOMENTAR PARA PUERTO REAL 
    # def find_port(self):
    #     ports = serial.tools.list_ports.comports()
    #     for p in ports:
    #         try:
    #             ser = serial.Serial(p.device, 115200, timeout=1)
    #             ser.close()
    #             return p.device
    #         except (serial.SerialException, OSError):
    #             continue
    #     return None

    def setup_labels(self):
        label_style = "font-size: 14px; font-weight: bold; color: #333;"
        for key, text in [
            ('status', "Estado del Sistema: OK"),
            ('mode', "Modo: Presión"),
            ('flow', "Estado del Flujo: None"),
            ('values', "P: 0.0 kPa | T: 0.0 °C | MV: 0.0% | SH: 0.0%"),
            ('esd', "ESD: Desactivado"),
            ('relief', "Válvula de Alivio: No"),
            ('purge', "Válvula de Purga: No")
        ]:
            self.labels[key] = QLabel(text)
            self.labels[key].setStyleSheet(label_style)
            self.layout.addWidget(self.labels[key], stretch=0)

    def update_data(self, data):
        p, t, mv, sh, flow, mode, esd, estado, relief, purge = data.values()

        self.x_data.append(self.x_data[-1] + 1)
        self.y1_data.append(p)
        self.y2_data.append(t)

        if len(self.x_data) > MAX_POINTS:
            self.x_data.popleft()
            self.y1_data.popleft()
            self.y2_data.popleft()

        self.line1.set_data(list(self.x_data), list(self.y1_data))
        self.line2.set_data(list(self.x_data), list(self.y2_data))

        self.ax1.set_xlim(self.x_data[0], self.x_data[-1])
        self.ax2.set_xlim(self.x_data[0], self.x_data[-1])
        
        self.update_labels(data)
        self.canvas.draw()

    def update_labels(self, data):
        p, t, mv, sh, flow, mode, esd, estado, relief, purge = data.values()
        
        self.labels['values'].setText(f"P: {p:.1f} kPa | T: {t:.1f} °C | MV: {mv:.1f}% | SH: {sh:.1f}%")
        self.labels['mode'].setText(f"Modo: {mode}")
        self.labels['flow'].setText(f"Estado del Flujo: {flow}")
        self.labels['esd'].setText(f"ESD: {esd}")
        self.labels['relief'].setText(f"Válvula de Alivio: {relief}")
        self.labels['purge'].setText(f"Válvula de Purga: {purge}")
        self.labels['status'].setText(f"Estado del Sistema: {estado}")

        if esd == 'Activado':
            self.labels['esd'].setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
            self.labels['status'].setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
        else:
            self.labels['esd'].setStyleSheet("font-size: 14px; font-weight: bold; color: green;")
            if "Advertencia" in estado or "Recuperación" in estado or "Precalentamiento" in estado:
                self.labels['status'].setStyleSheet("font-size: 14px; font-weight: bold; color: orange;")
            elif "Alivio" in estado or "Purga" in estado:
                self.labels['status'].setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
            else:
                self.labels['status'].setStyleSheet("font-size: 14px; font-weight: bold; color: green;")

    def init_plot(self, ax1, ax2):
        ax1.set_xlim(0, MAX_POINTS)
        ax1.set_ylim(100, 500)
        ax1.set_title('Presión (kPa) vs Tiempo')
        ax1.set_xlabel('Tiempo (s)')
        ax1.set_ylabel('Presión (kPa)')
        ax1.grid(True)

        ax2.set_xlim(0, MAX_POINTS)
        ax2.set_ylim(50, 200)
        ax2.set_title('Temperatura (°C) vs Tiempo')
        ax2.set_xlabel('Tiempo (s)')
        ax2.set_ylabel('Temperatura (°C)')
        ax2.grid(True)

        line1, = ax1.plot([], [], lw=2)
        line2, = ax2.plot([], [], lw=2, color='orange')

        # --- Áreas unificadas ---
        ax1.axhspan(FLOW_A_P_RANGE[0], FLOW_A_P_RANGE[1], facecolor=COLOR_FLOW_A, alpha=0.3, label='Flujo A')
        ax1.axhspan(FLOW_B_P_RANGE[0], FLOW_B_P_RANGE[1], facecolor=COLOR_FLOW_B, alpha=0.3, label='Flujo B')
        ax2.axhspan(FLOW_A_T_RANGE[0], FLOW_A_T_RANGE[1], facecolor=COLOR_FLOW_A, alpha=0.3, label='Flujo A')
        ax2.axhspan(FLOW_B_T_RANGE[0], FLOW_B_T_RANGE[1], facecolor=COLOR_FLOW_B, alpha=0.3, label='Flujo B')

        # Líneas de referencia
        ax1.axhline(P_EMERG_HIGH, color=COLOR_ALERT_LINE, linestyle='--', lw=2, label='Emergencia (Alta)')
        ax1.axhline(P_RECOVERY, color=COLOR_ALERT_LINE, linestyle='--', lw=2, label='Recuperación (Baja)')
        ax2.axhline(T_EMERG_HIGH, color=COLOR_ALERT_LINE, linestyle='--', lw=2, label='Emergencia (Alta)')
        ax2.axhline(T_PREHEAT, color=COLOR_ALERT_LINE, linestyle='--', lw=2, label='Precalentamiento (Baja)')

        ax1.legend(loc='upper left', bbox_to_anchor=(1, 1))
        ax2.legend(loc='upper left', bbox_to_anchor=(1, 1))

        return line1, line2

    def closeEvent(self, event):
        if self.serial_thread:
            self.serial_thread.stop()
            self.serial_thread.wait()
        event.accept()

def main():
    print("=== VAPORSUR S.A. - SIMULADOR INTEGRADO ===")
    print("Iniciando interfaz con simulador de Raspberry Pi Pico 2 W")
    print("Los datos mostrados son simulados para pruebas")
    print("=" * 50)


    app = QApplication(sys.argv)
    window = PlotterApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()