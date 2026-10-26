#code guarda datos x,y
import csv
import os
import time
import json
import threading
import urllib.request
from kivy.app import App
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import Metrics
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.clock import Clock
SERVER_URL = "http://172.26.152.231:8000/stroke"
GUARDAR_LOCAL = False

class AreaDibujo(Widget):

    def __init__(self, label_info, **kwargs):
        super().__init__(**kwargs)
        self.label_info=label_info
        self.raw=[]             # raw data
        self.active_touch=None

        # fondo y marco
        with self.canvas.before:
            Color(0.12, 0.12, 0.15, 1) # gris oscuro
            self.rect_fondo=Rectangle(pos=self.pos, size=self.size)
            Color(0, 0.5, 1, 1) # azul :D
            self.marco=Line(rectangle=(self.x, self.y, self.width, self.height), width=3)
        self.bind(pos=self.update_marco, size=self.update_marco)

    def update_marco(self, *args):
        self.marco.rectangle=(self.x, self.y, self.width, self.height)
        self.rect_fondo.pos=self.pos
        self.rect_fondo.size=self.size

    def muestra(self, touch):
        # tiempo de Kivy
        return (time.perf_counter(),touch.x-self.x,touch.y-self.y)

    def on_touch_down(self, touch):
        if self.active_touch!=None or not self.collide_point(*touch.pos):
            return False
        self.canvas.clear()  # borra el dibujo anterior
        self.active_touch=touch
        self.raw=[self.muestra(touch)]

        with self.canvas:
            Color(0, 0.5, 1, 1) # azul :D
            touch.ud["linea"]=Line(points=(touch.x, touch.y), width=2.5)
        return True

    def on_touch_move(self, touch):
        if touch!=self.active_touch:
            return False

        # si el dedo sale del area termina
        if not self.collide_point(*touch.pos):
            self.terminar_trazo()
            return True

        self.raw.append(self.muestra(touch))
        touch.ud["linea"].points+=[touch.x, touch.y]
        return True

    def on_touch_up(self, touch):
        if touch!=self.active_touch:
            return False
        self.terminar_trazo()
        return True

    def terminar_trazo(self):
        self.active_touch=None
        self.guardar()

    def guardar(self):
        if len(self.raw)<2:
            return

        folder=App.get_running_app().user_data_dir
        os.makedirs(folder, exist_ok=True)
        name=os.path.join(folder, "line.csv")

        t0 = self.raw[0][0]
        with open(name,"w",newline="") as f:
            # convertir px -> cm -> m
            f.write(f"# width_px={self.width},height_px={self.height}," f"dpi={Metrics.dpi},\n")
            w = csv.writer(f)
            w.writerow(["t","x_px","y_px"])
            for t,x,y in self.raw:
                w.writerow([f"{t-t0:.6f}",f"{x:.3f}",f"{y:.3f}"])

        duracion=self.raw[-1][0]-t0
        self.label_info.text=f"{len(self.raw)} puntos | {duracion:.2f} s"

        meta={"width_px":self.width,"height_px":self.height,"dpi":Metrics.dpi}
        sample=[[t-t0,x,y] for t,x,y in self.raw]
        threading.Thread(target=self.senddata,args=(meta,sample,name),daemon=True).start()
        self.raw=[]

    def senddata(self,meta,sample,name):
            data=json.dumps({"meta":meta,"sample":sample}).encode()
            req=urllib.request.Request(SERVER_URL,data=data)
            urllib.request.urlopen(req,timeout=5)
            if not GUARDAR_LOCAL:
                os.remove(name)
            
class AppDron(App):

    def build(self):
        layout = BoxLayout(orientation="vertical")
        self.label_info = Label(text="draw", size_hint_y=0.1,
                                font_size="18sp", bold=True)
        self.area_dibujo = AreaDibujo(label_info=self.label_info)
        layout.add_widget(self.label_info)
        layout.add_widget(self.area_dibujo)
        return layout


if __name__ == "__main__":
    AppDron().run()