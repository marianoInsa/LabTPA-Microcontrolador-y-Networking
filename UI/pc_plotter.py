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
import numpy as np

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

        self.ser = serial.Serial(port, 115200, timeout=1)
        # self.ser = SimulatedSerial(port, 115200, timeout=1)
        self.running = True
        self.data_queue = deque(maxlen=100) # Add buffer
        print(f"Conectado al puerto: {port}")

    def run(self):
        while self.running:
            try:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    data = self.parse_data(line)
                    if data:
                        self.data_received.emit(data)
                # [SIMULADOR] Agrego un tiempo entre lecturas
                # time.sleep(DATA_COLLECTION_INTERVAL_MS / 1000.0)
            except serial.SerialException as e:
                print(f"Error de lectura serial: {e}")
                self.running = False
            except Exception as e:
                print(f"Error inesperado en lector serial: {e}")
                continue

    def stop(self):
        self.running = False
        self.ser.close()

    def parse_data(self, line):
        # Expresión regular para capturar todos los campos
        patron = r"P:([\d.-]+),T:([\d.-]+),MV:([\d.-]+),SH:([\d.-]+),F:(\w+),M:(\w+),ESD:(\w+),ESTADO:([\w\s]+),RELIEF:(\w+),PURGE:(\w+)"
        match = re.search(patron, line)
        if match:
            try:
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
            except ValueError as e:
                print(f"Error al convertir datos: {e}")
        return None

# ===============================================
#         INTERFAZ GRÁFICA PyQt5
# ===============================================
class PlotterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('VaporSur S.A. - Monitoreo del Sistema')
        self.resize(1200, 800)
        self.layout = QVBoxLayout(self)

        plt.style.use('fast')
        # Figura matplotlib con autoajuste
        self.fig = plt.figure(figsize=(12, 8), constrained_layout=True)
        self.fig.patch.set_facecolor('white')

        gs = gridspec.GridSpec(2, 1, height_ratios=[1, 1], figure=self.fig)
        self.ax1 = self.fig.add_subplot(gs[0])
        self.ax2 = self.fig.add_subplot(gs[1])

        self.canvas = FigureCanvas(self.fig)
        self.canvas.setParent(self)
        self.layout.addWidget(self.canvas, stretch=1)

        self.labels = {}
        self.setup_labels()

        # self.x_data = np.arange(MAX_POINTS, dtype=np.float32)
        # self.y1_data = np.zeros(MAX_POINTS, dtype=np.float32)
        # self.y2_data = np.zeros(MAX_POINTS, dtype=np.float32)
        # self.data_index = 0

        # self.line1, self.line2 = self.init_plot(self.ax1, self.ax2)

        # Configurar formato de tiempo en ejes
        from matplotlib.ticker import FuncFormatter
        
        def time_formatter(x, pos):
            """Formatea el tiempo en minutos:segundos"""
            total_seconds = int(x)
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes:02d}:{seconds:02d}"
        
        # Aplicar formateador a ambos ejes X
        self.ax1.xaxis.set_major_formatter(FuncFormatter(time_formatter))
        self.ax2.xaxis.set_major_formatter(FuncFormatter(time_formatter))
        
        # Datos optimizados con numpy y tiempo real
        self.start_time = time.time()
        self.x_data = np.zeros(MAX_POINTS, dtype=np.float32)  # Tiempo real
        self.y1_data = np.zeros(MAX_POINTS, dtype=np.float32)
        self.y2_data = np.zeros(MAX_POINTS, dtype=np.float32)
        self.data_index = 0
        self.current_time = 0
        
        # Inicialización de plots optimizada
        self.line1, self.line2 = self.init_plot(self.ax1, self.ax2)
        

        # timer para actualizar el plot
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plots)
        self.update_timer.start(GUI_UPDATE_INTERVAL_MS)

        # buffer de datos recientes
        self.recent_data = None
        self.plot_dirty = False

        self.serial_thread = None
        self.start_serial()

    def start_serial(self):
        # PARA SIMULADOR
        # port = "SIMULADO_COM3"
        # print(f"[SIMULADOR] Iniciando con puerto simulado: {port}")
        # self.serial_thread = SerialReader(port)
        # self.serial_thread.data_received.connect(self.receive_data)
        # self.serial_thread.start()
        
        port = self.find_port()
        if port:
            print(f"Conectado a {port}")
            self.serial_thread = SerialReader(port)
            self.serial_thread.data_received.connect(self.receive_data)
            self.serial_thread.start()
        else:
            print("No se encontró ningún dispositivo CircuitPython. Conéctalo y vuelve a intentar.")
            sys.exit(1)
    
    # DESCOMENTAR PARA PUERTO REAL 
    def find_port(self):
        ports = serial.tools.list_ports.comports()
        for p in ports:
            try:
                ser = serial.Serial(p.device, 115200, timeout=1)
                ser.close()
                return p.device
            except (serial.SerialException, OSError):
                continue
        return None

    def receive_data(self, data):
        """Recibe datos y los almacena para actualización posterior"""
        self.recent_data = data
        self.plot_dirty = True
        
        # Actualizar labels inmediatamente (más crítico para UX)
        self.update_labels_immediate(data)

        self.current_time = time.time() - self.start_time
        
        # Agregar datos al buffer circular
        p, t = data['P'], data['T']
        
        # Usar indexing circular para mejor rendimiento
        idx = self.data_index % MAX_POINTS
        self.x_data[idx] = self.current_time
        self.y1_data[idx] = p
        self.y2_data[idx] = t
        self.data_index += 1

    def update_plots(self):
        """Actualización optimizada de gráficos usando timer separado"""
        if not self.plot_dirty or self.recent_data is None:
            return
            
        try:
            # Calcular rango de datos válidos
            if self.data_index < MAX_POINTS:
                # Caso inicial: menos datos que el buffer completo
                valid_range = slice(0, self.data_index)
                x_data = self.x_data[:self.data_index]
                y1_data = self.y1_data[:self.data_index]
                y2_data = self.y2_data[:self.data_index]
            else:
                # Caso normal: buffer lleno, ordenar datos cronológicamente
                start_idx = self.data_index % MAX_POINTS

                # Reordenar datos para mantener orden cronológico
                if start_idx != 0:
                    x_data = np.concatenate([self.x_data[start_idx:], self.x_data[:start_idx]])
                    y1_data = np.concatenate([self.y1_data[start_idx:], self.y1_data[:start_idx]])
                    y2_data = np.concatenate([self.y2_data[start_idx:], self.y2_data[:start_idx]])
                else:
                    x_data = self.x_data.copy()
                    y1_data = self.y1_data.copy()
                    y2_data = self.y2_data.copy()

            # Actualizar líneas con tiempo real
            self.line1.set_data(x_data, y1_data)
            self.line2.set_data(x_data, y2_data)
            
            # Actualizar ventana de tiempo (últimos N segundos)
            if len(x_data) > 0:
                time_window = 60  # Mostrar últimos 60 segundos
                current_time = x_data[-1] if len(x_data) > 0 else self.current_time
                
                # Ventana deslizante de tiempo
                self.ax1.set_xlim(max(0, current_time - time_window), current_time + 5)
                self.ax2.set_xlim(max(0, current_time - time_window), current_time + 5)
            
            # Autoescalado inteligente (solo cuando sea necesario)
            if self.data_index % 20 == 0:  # Cada 20 puntos
                self.smart_autoscale(y1_data, y2_data)
            
            # Actualizar canvas de manera eficiente
            self.canvas.draw_idle()  # Más eficiente que draw()
            self.plot_dirty = False
            
        except Exception as e:
            print(f"Error actualizando gráficos: {e}")

    def smart_autoscale(self, y1_data, y2_data):
        """Autoescalado inteligente para mejor rendimiento"""
        if len(y1_data) > 10:
            # Usar percentiles para escalado robusto
            y1_valid = y1_data[y1_data > 0]
            y2_valid = y2_data[y2_data > 0]
            
            if len(y1_valid) > 0:
                y1_min, y1_max = np.percentile(y1_valid, [5, 95])
                margin1 = (y1_max - y1_min) * 0.1
                self.ax1.set_ylim(y1_min - margin1, y1_max + margin1)
            
            if len(y2_valid) > 0:
                y2_min, y2_max = np.percentile(y2_valid, [5, 95])
                margin2 = (y2_max - y2_min) * 0.1
                self.ax2.set_ylim(y2_min - margin2, y2_max + margin2)

    def update_labels_immediate(self, data):
        """Actualización inmediata y optimizada de labels"""
        try:
            p, t, mv, sh = data['P'], data['T'], data['MV'], data['SH']
            flow, mode, esd, estado = data['F'], data['M'], data['ESD'], data['ESTADO']
            relief, purge = data['RELIEF'], data['PURGE']
            
            # Calcular tiempo transcurrido
            elapsed = int(self.current_time)
            time_str = f"{elapsed//60:02d}:{elapsed%60:02d}"
            
            # Actualizar solo textos que han cambiado
            new_values_text = f"P: {p:.1f} kPa | T: {t:.1f} °C | MV: {mv:.1f}% | SH: {sh:.1f}% | Tiempo: {time_str}"
            if self.labels['values'].text() != new_values_text:
                self.labels['values'].setText(new_values_text)
            
            # Actualizar otros labels de manera similar
            self.labels['mode'].setText(f"Modo: {mode}")
            self.labels['flow'].setText(f"Estado del Flujo: {flow}")
            self.labels['esd'].setText(f"ESD: {esd}")
            self.labels['relief'].setText(f"Válvula de Alivio: {relief}")
            self.labels['purge'].setText(f"Válvula de Purga: {purge}")
            self.labels['status'].setText(f"Estado del Sistema: {estado}")

            # Actualización optimizada de estilos
            self.update_label_styles(esd, estado)
            
        except Exception as e:
            print(f"Error actualizando labels: {e}")

    def update_label_styles(self, esd, estado):
        """Actualización optimizada de estilos de labels"""
        if esd == 'Activado':
            self.labels['esd'].setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
            self.labels['status'].setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
        else:
            self.labels['esd'].setStyleSheet("font-size: 14px; font-weight: bold; color: green;")
            if any(word in estado for word in ["Advertencia", "Recuperación", "Precalentamiento"]):
                self.labels['status'].setStyleSheet("font-size: 14px; font-weight: bold; color: orange;")
            elif any(word in estado for word in ["Alivio", "Purga"]):
                self.labels['status'].setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
            else:
                self.labels['status'].setStyleSheet("font-size: 14px; font-weight: bold; color: green;")

    def setup_labels(self):
        """Setup optimizado de labels"""
        label_style = "font-size: 14px; font-weight: bold; color: #fff; padding: 2px;"
        labels_config = [
            ('status', "Estado del Sistema: Iniciando..."),
            ('mode', "Modo: --"),
            ('flow', "Estado del Flujo: --"),
            ('values', "P: -- kPa | T: -- °C | MV: --% | SH: --%"),
            ('esd', "ESD: --"),
            ('relief', "Válvula de Alivio: --"),
            ('purge', "Válvula de Purga: --")
        ]
        
        for key, text in labels_config:
            self.labels[key] = QLabel(text)
            self.labels[key].setStyleSheet(label_style)
            self.layout.addWidget(self.labels[key], stretch=0)

    # def update_data(self, data):
    #     p, t, mv, sh, flow, mode, esd, estado, relief, purge = data.values()

    #     self.x_data.append(self.x_data[-1] + 1)
    #     self.y1_data.append(p)
    #     self.y2_data.append(t)

    #     if len(self.x_data) > MAX_POINTS:
    #         self.x_data.popleft()
    #         self.y1_data.popleft()
    #         self.y2_data.popleft()

    #     self.line1.set_data(list(self.x_data), list(self.y1_data))
    #     self.line2.set_data(list(self.x_data), list(self.y2_data))

    #     self.ax1.set_xlim(self.x_data[0], self.x_data[-1])
    #     self.ax2.set_xlim(self.x_data[0], self.x_data[-1])
        
    #     self.update_labels(data)
    #     self.canvas.draw()

    # def update_labels(self, data):
    #     p, t, mv, sh, flow, mode, esd, estado, relief, purge = data.values()
        
    #     self.labels['values'].setText(f"P: {p:.1f} kPa | T: {t:.1f} °C | MV: {mv:.1f}% | SH: {sh:.1f}%")
    #     self.labels['mode'].setText(f"Modo: {mode}")
    #     self.labels['flow'].setText(f"Estado del Flujo: {flow}")
    #     self.labels['esd'].setText(f"ESD: {esd}")
    #     self.labels['relief'].setText(f"Válvula de Alivio: {relief}")
    #     self.labels['purge'].setText(f"Válvula de Purga: {purge}")
    #     self.labels['status'].setText(f"Estado del Sistema: {estado}")

    #     if esd == 'Activado':
    #         self.labels['esd'].setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
    #         self.labels['status'].setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
    #     else:
    #         self.labels['esd'].setStyleSheet("font-size: 14px; font-weight: bold; color: green;")
    #         if "Advertencia" in estado or "Recuperación" in estado or "Precalentamiento" in estado:
    #             self.labels['status'].setStyleSheet("font-size: 14px; font-weight: bold; color: orange;")
    #         elif "Alivio" in estado or "Purga" in estado:
    #             self.labels['status'].setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
    #         else:
    #             self.labels['status'].setStyleSheet("font-size: 14px; font-weight: bold; color: green;")

    def init_plot(self, ax1, ax2):
        """Inicialización optimizada de plots"""
        ax1.set_xlim(0, 60) # Ventana inicial de 60 segundos
        ax1.set_ylim(200, 400)
        ax1.set_title('Presión (kPa) vs Tiempo', fontsize=12, pad=10)
        ax1.set_xlabel('Tiempo (s)', fontsize=10)
        ax1.set_ylabel('Presión (kPa)', fontsize=10)
        ax1.grid(True, alpha=0.3)

        ax2.set_xlim(0, 60)
        ax2.set_ylim(100, 180)
        ax2.set_title('Temperatura (°C) vs Tiempo', fontsize=12, pad=10)
        ax2.set_xlabel('Tiempo (s)', fontsize=10)
        ax2.set_ylabel('Temperatura (°C)', fontsize=10)
        ax2.grid(True, alpha=0.3)

        line1, = ax1.plot([], [], lw=2, color='#2E86AB', alpha=0.8)
        line2, = ax2.plot([], [], lw=2, color='#F24236', alpha=0.8)

        # --- Áreas unificadas ---
        ax1.axhspan(FLOW_A_P_RANGE[0], FLOW_A_P_RANGE[1], facecolor=COLOR_FLOW_A, alpha=0.2, label='Flujo A')
        ax1.axhspan(FLOW_B_P_RANGE[0], FLOW_B_P_RANGE[1], facecolor=COLOR_FLOW_B, alpha=0.2, label='Flujo B')
        ax2.axhspan(FLOW_A_T_RANGE[0], FLOW_A_T_RANGE[1], facecolor=COLOR_FLOW_A, alpha=0.2, label='Flujo A')
        ax2.axhspan(FLOW_B_T_RANGE[0], FLOW_B_T_RANGE[1], facecolor=COLOR_FLOW_B, alpha=0.2, label='Flujo B')

        # Líneas de referencia
        ax1.axhline(P_EMERG_HIGH, color=COLOR_ALERT_LINE, linestyle='--', lw=1.5, alpha=0.7, label='Emergencia (Alta)')
        ax1.axhline(P_RECOVERY, color=COLOR_ALERT_LINE, linestyle='--', lw=1.5, alpha=0.7, label='Recuperación (Baja)')
        ax2.axhline(T_EMERG_HIGH, color=COLOR_ALERT_LINE, linestyle='--', lw=1.5, alpha=0.7, label='Emergencia (Alta)')
        ax2.axhline(T_PREHEAT, color=COLOR_ALERT_LINE, linestyle='--', lw=1.5, alpha=0.7, label='Precalentamiento (Baja)')

        ax1.legend(loc='upper right', fontsize=8, framealpha=0.8)
        ax2.legend(loc='upper right', fontsize=8, framealpha=0.8)

        return line1, line2

    def closeEvent(self, event):
        """Cierre"""
        print("Cerrando aplicación...")
        if self.update_timer:
            self.update_timer.stop()
        if self.serial_thread:
            self.serial_thread.stop()
            self.serial_thread.wait(3000)
        event.accept()

def main():
    print("=== VAPORSUR S.A. - SIMULADOR INTEGRADO ===")
    print("Iniciando interfaz con simulador de Raspberry Pi Pico 2 W")
    print("Los datos mostrados son simulados para pruebas")
    print("Configuración:")
    print(f"  - Actualización GUI: {GUI_UPDATE_INTERVAL_MS}ms ({1000//GUI_UPDATE_INTERVAL_MS} FPS)")
    print(f"  - Recolección datos: {DATA_COLLECTION_INTERVAL_MS}ms")
    print(f"  - Buffer de datos: {MAX_POINTS} puntos")
    print("=" * 50)


    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = PlotterApp()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()