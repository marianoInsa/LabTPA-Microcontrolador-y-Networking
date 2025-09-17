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

# --- Configuración ---
MAX_POINTS = 200
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

# --- Hilo para lectura serial ---
class SerialReader(QThread):
    data_received = pyqtSignal(dict)

    def __init__(self, port, parent=None):
        QThread.__init__(self, parent)
        self.ser = serial.Serial(port, 115200, timeout=1)
        self.running = True

    def run(self):
        while self.running:
            try:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                data = self.parse_data(line)
                if data:
                    self.data_received.emit(data)
            except serial.SerialException as e:
                print(f"Error de lectura serial: {e}")
                self.running = False
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
        port = self.find_port()
        if port:
            print(f"Conectado a {port}")
            self.serial_thread = SerialReader(port)
            self.serial_thread.data_received.connect(self.update_data)
            self.serial_thread.start()
        else:
            print("No se encontró ningún dispositivo CircuitPython. Conéctalo y vuelve a intentar.")
            sys.exit(1)

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
    app = QApplication(sys.argv)
    window = PlotterApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()