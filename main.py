#code guarda datos x,y
import csv
import os
import time
import json
import threading
import socket
from kivy.app import App
from kivy.graphics import Color, Line, Rectangle, InstructionGroup
from kivy.metrics import Metrics
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.core.window import Window

# Permite que Kivy redimensione la ventana automáticamente cuando el teclado se despliegue
Window.softinput_mode = 'below_target' # O prueba con 'pan'


HOST = "172.21.198.84"
PORT = 65432
GUARDAR_LOCAL = False

class AreaDibujo(RelativeLayout):

    def __init__(self, label_info, **kwargs):
        super().__init__(**kwargs)
        self.label_info = label_info
        self.raw = []
        self.active_touch = None
        self.m_izq = 35
        self.m_abajo = 35
        self.ancho_util = 0
        self.alto_util = 0

        self.fondo = InstructionGroup()
        self.canvas.before.add(self.fondo)
 
        # etiquetas de los ejes
        self.lbl_x = Label(text='X', color=(0.9, 0.9, 0.9, 1), size_hint=(None, None), size=(30, 30), bold=True, font_size="16sp")
        self.lbl_z = Label(text='Z', color=(0.9, 0.9, 0.9, 1), size_hint=(None, None), size=(30, 30), bold=True, font_size="16sp")
        self.add_widget(self.lbl_x)
        self.add_widget(self.lbl_z)
 
        with self.canvas:
            Color(0, 0.5, 1, 1) #azul :D
            self.linea_actual = Line(points=[], width=2.5)
            Color(1, 0.5, 0, 1) #naranja XD
            self.linea_kalman = Line(points=[], width=2.5)
 
        self.bind(pos=self.update_canvas, size=self.update_canvas)
        self.update_canvas()

    def gethost(self, instance):
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        self.input_ip = TextInput(
            text=HOST,
            multiline=False,
            font_size=18,
            size_hint=(1,0.5),
            input_type='number'
        )

        def on_text_change(instance, value):
            if ',' in value:
                instance.text = value.replace(',', '.')

        self.input_ip.bind(text=on_text_change)
        layout.add_widget(self.input_ip)
        
        btn_ok = Button(text='ok', size_hint=(1, 0.4), bold=True)
        layout.add_widget(btn_ok)

        self.popup = Popup(
            title="Write valid IP (X.X.X.X)",
            content=layout,
            size_hint=(0.8, 0.35),
            auto_dismiss=False,
            pos_hint={'center_x': 0.5, 'top': 0.85}
        )

        def guardar_y_cerrar(btn):
            global HOST
            ip_ingresada = self.input_ip.text.strip()
            
            import re
            patron_ip = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
            match = re.match(patron_ip, ip_ingresada)
            
            if match:
                octetos = [int(g) for g in match.groups()]
                if all(0 <= o <= 255 for o in octetos):
                    HOST = ip_ingresada
                    print(f"New IP validada: {HOST}")
                    self.popup.dismiss()
                    return

            print("invalid IP")
            self.input_ip.text = HOST

        btn_ok.bind(on_press=guardar_y_cerrar)
        self.popup.open()


    def update_canvas(self, *args):
        self.ancho_util = self.width - self.m_izq - 10
        self.alto_util = self.height - self.m_abajo - 10
        self.fondo.clear()
        if self.ancho_util <= 0 or self.alto_util <= 0:
            return
 
        self.fondo.add(Color(0.12, 0.12, 0.15, 1))  # fondo
        self.fondo.add(Rectangle(pos=(0, 0), size=self.size))
 
        self.fondo.add(Color(0.5, 0.5, 0.25, 0.6))  # cuadricula cada 40 px
        for gx in range(int(self.m_izq), int(self.m_izq + self.ancho_util), 40):
            self.fondo.add(Line(points=[gx, self.m_abajo, gx, self.m_abajo + self.alto_util], width=1))
        for gz in range(int(self.m_abajo), int(self.m_abajo + self.alto_util), 40):
            self.fondo.add(Line(points=[self.m_izq, gz, self.m_izq + self.ancho_util, gz], width=1))
 
        self.fondo.add(Color(0, 0.5, 1, 1))  # marco
        self.fondo.add(Line(rectangle=(self.m_izq, self.m_abajo, self.ancho_util, self.alto_util), width=3))
 
        self.lbl_x.pos = (self.m_izq + self.ancho_util - 10, self.m_abajo - 30)
        self.lbl_z.pos = (self.m_izq - 30, self.m_abajo + self.alto_util - 10)
    
    def on_touch_down(self, touch):
        lx, lz = self.to_local(*touch.pos)
        dentro = (self.m_izq <= lx <= self.m_izq + self.ancho_util and
                  self.m_abajo <= lz <= self.m_abajo + self.alto_util)
        if not dentro or self.active_touch is not None:
            return False
 
        # empieza un trazo nuevo
        self.active_touch = touch
        self.linea_actual.points = [lx, lz]
        self.linea_kalman.points = []
        self.raw = [(time.perf_counter(), lx - self.m_izq, lz - self.m_abajo)]
        return True

    def on_touch_move(self, touch):
        if touch != self.active_touch:
            return False
 
        lx, lz = self.to_local(*touch.pos)
        dentro = (self.m_izq <= lx <= self.m_izq + self.ancho_util and
                  self.m_abajo <= lz <= self.m_abajo + self.alto_util)
        if not dentro:  # si se sale del marco, termina el trazo
            self.active_touch = None
            return True
 
        self.raw.append((time.perf_counter(), lx - self.m_izq, lz - self.m_abajo))
        self.linea_actual.points += [lx, lz]
        return True
    
    def on_touch_up(self, touch):
        if touch != self.active_touch:
            return False
        self.active_touch = None
        return True

    def guardar(self,*args):
        if len(self.raw) < 2:
            return
 
        dpi = Metrics.dpi if Metrics.dpi > 0 else 96
        t0 = self.raw[0][0]
        datam = [(t - t0, x / dpi * 0.0254, z / dpi * 0.0254) for t, x, z in self.raw]
 
        if GUARDAR_LOCAL:
            folder = App.get_running_app().user_data_dir
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, "line.csv"), "w", newline="") as f:
                f.write(f"# width_px={self.width},height_px={self.height},dpi={dpi}\n")
                w = csv.writer(f)
                w.writerow(["t", "x_m", "z_m"])
                for t, x, z in datam:
                    w.writerow([f"{t:.6f}", f"{x:.4f}", f"{z:.4f}"])
 
        self.label_info.text = f"{len(datam)} points | {datam[-1][0]:.2f} s"
 
        meta = {"width_px": self.width, "height_px": self.height, "dpi": dpi,
                "ancho_util_px": self.ancho_util, "alto_util_px": self.alto_util}
        threading.Thread(target=self.senddata, args=(meta, datam), daemon=True).start()

    def senddata(self,meta,sample):
        try:
            mensaje = json.dumps({"meta": meta, "sample": sample}) + "\n"
 
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5.0)
                s.connect((HOST, PORT))
                s.sendall(mensaje.encode("utf-8"))
                s.shutdown(socket.SHUT_WR)  # avisa que ya termino de enviar
 
                buf = b""
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
 
            # metros -> px del marco para poder dibujarlo
            dpi = meta["dpi"]
            puntos = []
            for _, x_m, z_m in json.loads(buf.decode("utf-8"))["filtrado"]:
                puntos += [x_m / 0.0254 * dpi + self.m_izq, z_m / 0.0254 * dpi + self.m_abajo]
 
            Clock.schedule_once(lambda dt: self.mostrar_filtrado(puntos))  # dibujar va en el hilo principal
            print(f"enviado")
 
        except Exception as e:
            print(f"Error: {e}")

    def mostrar_filtrado(self,puntos):
        self.linea_kalman.points = puntos
        self.label_info.text += " | filtrado"

class AppDron(App):

    def build(self):
        layout = BoxLayout(orientation="vertical")

        top_layout = BoxLayout(size_hint_y=0.1, orientation="horizontal")
        label_info = Label(text="Draw", font_size="18sp", bold=True)

        btn_config = Button(text="Configuration", size_hint_x=None, width=100, bold=True)
        
        area_dibujo = AreaDibujo(label_info=label_info)
        btn_config.bind(on_press=area_dibujo.gethost)

        top_layout.add_widget(label_info)
        top_layout.add_widget(btn_config)

        btn_send = Button(text="Send", size_hint_y=0.1, font_size="18sp", bold=True)
        btn_send.bind(on_press=area_dibujo.guardar)
 
        layout.add_widget(top_layout)
        layout.add_widget(area_dibujo)
        layout.add_widget(btn_send)
        return layout


if __name__ == "__main__":
    Window.softinput_mode = 'pan'
    AppDron().run()
