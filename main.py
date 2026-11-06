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

        self.fondo = InstructionGroup()
        self.canvas.before.add(self.fondo)
        
        self.lbl_x = Label(text='x', color=(0.9, 0.9, 0.9, 1), size_hint=(None, None), size=(20, 20), bold=True, font_size="16sp")
        self.lbl_z = Label(text='z', color=(0.9, 0.9, 0.9, 1), size_hint=(None, None), size=(20, 20), bold=True, font_size="16sp")
        self.add_widget(self.lbl_x)
        self.add_widget(self.lbl_z)

        with self.canvas:
            Color(0, 0.5, 1, 1)  # azul :D
            self.linea_actual = Line(points=[], width=2.5)

        self.bind(pos=self.update_canvas, size=self.update_canvas)
        self.update_canvas()

    def update_canvas(self, *args):
        self.fondo.clear()
        ancho_util = self.width - self.m_izq - 10
        alto_util = self.height - self.m_abajo - 10

        if ancho_util <= 0 or alto_util <= 0:
            return

        # fondo
        self.fondo.add(Color(0.12, 0.12, 0.15, 1))
        self.fondo.add(Rectangle(pos=(0, 0), size=self.size))

        # rayitas
        self.fondo.add(Color(0.5, 0.5, 0.25, 0.6))
        step = 40

        z = self.m_izq
        while z < (self.m_izq + ancho_util):
            self.fondo.add(Line(points=[z, self.m_abajo, z, self.m_abajo + alto_util], width=1))
            z += step

        x = self.m_abajo
        while x < (self.m_abajo + alto_util):
            self.fondo.add(Line(points=[self.m_izq, x, self.m_izq + ancho_util, x], width=1))
            x += step

        # marco
        self.fondo.add(Color(0, 0.5, 1, 1))
        self.fondo.add(Line(rectangle=(self.m_izq, self.m_abajo, ancho_util, alto_util), width=3))

        # etiquetas fijas afuera
        self.lbl_x.pos = (self.m_izq + ancho_util - 10, self.m_abajo - 30)
        self.lbl_z.pos = (self.m_izq - 30, self.m_abajo + alto_util - 10)
    
    def on_touch_down(self, touch):
        lx, lz = self.to_local(*touch.pos)
        ancho_util = self.width - self.m_izq - 10
        alto_util = self.height - self.m_abajo - 10

        if not (self.m_izq <= lx <= self.m_izq + ancho_util and
                self.m_abajo <= lz <= self.m_abajo + alto_util):
            return False

        if self.active_touch != None:
            return False

        self.linea_actual.points = []
        self.raw = []

        self.active_touch = touch
        self.raw = [(time.perf_counter(), lx - self.m_izq, lz - self.m_abajo)]
        self.linea_actual.points = [lx, lz]
        return True

    def on_touch_move(self, touch):
        if touch != self.active_touch:
            return False

        ancho_util = self.width - self.m_izq - 10
        alto_util = self.height - self.m_abajo - 10
        lx= touch.x - self.x
        lz= touch.y - self.y

        if not (self.m_izq <= lx <= self.m_izq + ancho_util and
                self.m_abajo <= lz <= self.m_abajo + alto_util):
            self.active_touch = None
            return True

        self.raw.append((time.perf_counter(), lx - self.m_izq, lz - self.m_abajo))
        if hasattr(self, 'linea_actual'):
            self.linea_actual.points += [lx, lz]
        return True
    
    def on_touch_up(self, touch):
        if touch != self.active_touch:
            return False
        self.active_touch = None
        return True

    def terminar_trazo(self):
        self.guardar()

    def guardar(self):
        if len(self.raw)<2:
            return

        folder=App.get_running_app().user_data_dir
        os.makedirs(folder, exist_ok=True)
        name=os.path.join(folder, "line.csv")

        dpi=Metrics.dpi if Metrics.dpi>0 else 96
        t0 = self.raw[0][0]

        datam=[]
        for t,x_px,z_px in self.raw:
            x_m= x_px/dpi*0.0254
            z_m= z_px/dpi*0.0254
            datam.append((t-t0,x_m,z_m))

        with open(name,"w",newline="") as f:
            f.write(f"# width_px={self.width},height_px={self.height}," f"dpi={dpi},\n")
            w = csv.writer(f)
            w.writerow(["t","x_m","z_m"])
            for t,x,z in datam:
                w.writerow([f"{t:.6f}",f"{x:.4f}",f"{z:.4f}"])

        duracion=self.raw[-1][0]-t0
        self.label_info.text=f"{len(self.raw)} puntos | {duracion:.2f} s"

        meta={"width_px":self.width,"height_px":self.height,"dpi":dpi}
        threading.Thread(target=self.senddata,args=(meta,datam,name),daemon=True).start()

    def senddata(self,meta,sample,name):
        try:
            data = json.dumps({"meta": meta, "sample": sample}) + "\n"

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((HOST, PORT))
                s.sendall(data.encode('utf-8'))

            if not GUARDAR_LOCAL:
                if os.path.exists(name):
                    os.remove(name)
                print("enviado")
        except Exception as e:
            print(f"Error: {e}")
            
class AppDron(App):

    def build(self):
        layout = BoxLayout(orientation="vertical")
        self.label_info = Label(text="Draw", size_hint_y=0.1, font_size="18sp", bold=True)
        self.area_dibujo = AreaDibujo(label_info=self.label_info)

        btn_send=Button(text="Send", size_hint_y=0.1, font_size="18sp", bold=True)
        btn_send.bind(on_press=lambda x: self.area_dibujo.terminar_trazo())

        layout.add_widget(self.label_info)
        layout.add_widget(self.area_dibujo)
        layout.add_widget(btn_send)
        return layout


if __name__ == "__main__":
    AppDron().run()
