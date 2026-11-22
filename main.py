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

Window.softinput_mode = 'below_target' # para que el teclado no tape el texto
HOST = "127.0.0.1"
PORT = 65432
GUARDAR_LOCAL = False

from kivy.base import EventLoop
from kivy.config import Config
from kivy.core.window import Window

print("=== WINDOW PROVIDER ===")
print(Window.__class__.__module__, Window.__class__.__name__)

print("=== INPUT PROVIDERS (Config) ===")
for k, v in Config.items("input"):
    print(f"  {k} = {v}")

print("=== ACTIVE INPUT PROVIDERS (EventLoop) ===")
for p in EventLoop.input_providers:
    print(" ", p.__class__.__module__, p.__class__.__name__, "->", getattr(p, "device", ""))

class AreaDibujo(RelativeLayout):

    def __init__(self, label_info, **kwargs):
        super().__init__(**kwargs)
        self.label_info = label_info
        self.raw = [] # la raw data se guarda aqui
        self.active_touch = None
        self.m_izq = 50
        self.m_abajo = 50
        self.ancho_util = 0
        self.alto_util = 0

        self.fondo = InstructionGroup() # grupo de instrucciones del canvas
        self.canvas.before.add(self.fondo)
 
        # etiquetas de los ejes 
        self.lbl_x = Label(text='X', color=(0.9, 0.9, 0.9, 1), size_hint=(None, None), size=(0, 0), bold=True, font_size="20sp")
        self.lbl_z = Label(text='Z', color=(0.9, 0.9, 0.9, 1), size_hint=(None, None), size=(0, 0), bold=True, font_size="20sp")
        self.add_widget(self.lbl_x)
        self.add_widget(self.lbl_z)
 
        with self.canvas:
            Color(0, 0.5, 1, 1) # azul :D
            self.linea_actual = Line(points=[], width=2.5)
            Color(1, 0.5, 0, 1) # naranja XD
            self.linea_kalman = Line(points=[], width=2.5)
 
        self.bind(pos=self.update_canvas, size=self.update_canvas) # conecta la pos y size con update_canvas para que se actualice si se cambia
        self.update_canvas()

    def on_touch_down(self, touch): # se ejecuta cuando se toca la pantalla
        lx, lz = self.to_local(*touch.pos) # convierte la posicion global en local
        dentro = (self.m_izq <= lx <= self.m_izq + self.ancho_util and # se fija que el trazo empiece dentro del margen
                  self.m_abajo <= lz <= self.m_abajo + self.alto_util)
        if not dentro or self.active_touch is not None: # se asegura que no haya otro toque
            return False
 
        # empieza un trazo nuevo
        self.active_touch = touch
        self.linea_actual.points = [lx, lz]
        self.linea_kalman.points = []
        self.raw = [(time.perf_counter(), lx - self.m_izq, lz - self.m_abajo)] # captura la raw data guardando el primer timestamp
        return True
    
    def on_touch_move(self, touch): # se ejecuta cuando el dedo se desliza por la pantalla
        if touch != self.active_touch: # verifica que pertenezca al toque activo
            return False
     
        lx, lz = self.to_local(*touch.pos)
        dentro = (self.m_izq <= lx <= self.m_izq + self.ancho_util and
                    self.m_abajo <= lz <= self.m_abajo + self.alto_util)
        if not dentro:  # si se sale del marco termina el trazo, si no se agregan los waypoints al trazo
            self.active_touch = None
            return True
     
        self.raw.append((time.perf_counter(), lx - self.m_izq, lz - self.m_abajo))
        self.linea_actual.points += [lx, lz] # actualiza linea azul
        return True
        
    def on_touch_up(self, touch): # se ejecuta al dejar de tocar la pantalla
        if touch != self.active_touch:
            return False
        self.active_touch = None # termina el trazo y ya se pueden hacer trazos nuevos
        return True

    def guardar(self, *args):
        if len(self.raw) < 2: # mas de 2 waypoints
            return
 
        dpi = Metrics.dpi if Metrics.dpi > 0 else 96 # sacar el dpi del dispositivo
        t0 = self.raw[0][0] # para tener el tiempo relativo
        datam = [(t - t0, x / dpi * 0.0254, z / dpi * 0.0254) for t, x, z in self.raw] # sacar los pixeles a metros
 
        self.label_info.text = f"{len(datam)} points | {datam[-1][0]:.2f} s" # info en la app puntos hechos y tiempo
 
        meta = {
            "width_px": self.width, 
            "height_px": self.height, 
            "dpi": dpi,
            "ancho_util_px": self.ancho_util, 
            "alto_util_px": self.alto_util
        } # prepara los metadatos y los envia 
        
        threading.Thread(target=self.senddata, args=(meta, datam), daemon=True).start() # lanza el hilo en segundo plano para el envio

    def senddata(self, meta, sample):
        try:
            mensaje = json.dumps({"meta": meta, "sample": sample}) + "\n" # empaqueta los metadatos y las muestras
 
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s: # abre un socket
                s.settimeout(5.0)
                s.connect((HOST, PORT))
                s.sendall(mensaje.encode("utf-8")) # envia todo el paquete con utf-8
                s.shutdown(socket.SHUT_WR) # cierra el envio
 
                buf = b"" # bucle para recibir la linea filtrada por kalman
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    buf += chunk

            dpi = meta["dpi"] # se pasa de metros a pixeles otra vez para mostrarlo en pantalla
            puntos = []
            for _, x_m, z_m in json.loads(buf.decode("utf-8"))["filtrado"]:
                puntos += [x_m / 0.0254 * dpi + self.m_izq, z_m / 0.0254 * dpi + self.m_abajo]
 
            # actualiza la ui con clock
            Clock.schedule_once(lambda dt: setattr(self.linea_kalman, 'points', puntos) or setattr(self.label_info, 'text', self.label_info.text + " | filtrado"))
            print("enviado")
 
        except Exception as e:
            print(f"Error: {e}")
    
    def gethost(self, instance): # para poder cambiar la ip
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        self.input_ip = TextInput( # campo de texto para la ip
            text=HOST,
            multiline=False,
            font_size=18,
            size_hint=(1, 0.5),
            input_type='number'
        )

        def on_text_change(instance, value): # reemplaza las comas por puntos
            if ',' in value:
                instance.text = value.replace(',', '.')

        self.input_ip.bind(text=on_text_change)
        layout.add_widget(self.input_ip)
        
        btn_ok = Button(text='ok', size_hint=(1, 0.8), bold=True)
        layout.add_widget(btn_ok)

        self.popup = Popup( # hace que aparezca el popup
            title="Write valid IP (X.X.X.X)",
            content=layout,
            size_hint=(0.8, 0.35),
            auto_dismiss=False,
            pos_hint={'center_x': 0.5, 'top': 0.8}
        )

        def guardar_y_cerrar(btn): # valida que la ip sea real
            global HOST
            ip_ingresada = self.input_ip.text.strip()
            
            import re
            patron_ip = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
            match = re.match(patron_ip, ip_ingresada)
            
            if match: # si la ip es correcta se guarda en HOST
                octetos = [int(g) for g in match.groups()]
                if all(0 <= o <= 255 for o in octetos):
                    HOST = ip_ingresada
                    print(f"New IP validada: {HOST}")
                    self.popup.dismiss() # cierra el popup
                    return

            print("invalid IP")
            self.input_ip.text = HOST # si falla se queda la ip anterior

        btn_ok.bind(on_press=guardar_y_cerrar)
        self.popup.open() # abre el popup

    def update_canvas(self, *args): # actualiza el canvas de tamaño
        self.ancho_util = self.width - self.m_izq - 10 # calcula el espacio util restando los margenes
        self.alto_util = self.height - self.m_abajo - 10

        self.fondo.clear() # limpia los trazos anteriores
        if self.ancho_util <= 0 or self.alto_util <= 0:
            return

        # color y forma del fondo
        self.fondo.add(Color(0, 0, 0, 0))  # negro
        self.fondo.add(Rectangle(pos=(0, 0), size=self.size))

        # rayitas de guia de dibujo
        self.fondo.add(Color(0.5, 0.5, 0.25, 1))  # como verde
        for gx in range(int(self.m_izq), int(self.m_izq + self.ancho_util), 50):
            self.fondo.add(Line(points=[gx, self.m_abajo, gx, self.m_abajo + self.alto_util], width=1))
        for gz in range(int(self.m_abajo), int(self.m_abajo + self.alto_util), 50):
            self.fondo.add(Line(points=[self.m_izq, gz, self.m_izq + self.ancho_util, gz], width=1))

        # marco exterior
        self.fondo.add(Color(0, 0.5, 1, 1))  # azul
        self.fondo.add(Line(rectangle=(self.m_izq, self.m_abajo, self.ancho_util, self.alto_util), width=3))

        # etiquetas X y Z
        self.lbl_x.pos = (self.m_izq + self.ancho_util - 10, self.m_abajo - 30)
        self.lbl_z.pos = (self.m_izq - 30, self.m_abajo + self.alto_util - 10)

class AppDron(App):

    def build(self):
        layout = BoxLayout(orientation="vertical")

        top_layout = BoxLayout(size_hint_y=0.1, orientation="horizontal")
        label_info = Label(text="Draw", font_size="18sp", bold=True)

        btn_config = Button(text="Configuration", size_hint_x=None, width=300, bold=True)
        
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
    Window.softinput_mode = 'resize'
    AppDron().run()
