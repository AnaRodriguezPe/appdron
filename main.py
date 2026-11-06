import time
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import Metrics
from kivy.uix.label import Label


class Test(Label):
    activo = False
    raw = []

    def on_touch_down(self, touch):
        if self.activo:
            return True
        self.activo = True
        self.raw = [(time.perf_counter(), touch.x, touch.y)]
        self.text = "No muevas el dedo (10 s)..."
        Clock.schedule_once(self.calcular_r, 10)
        return True

    def on_touch_move(self, touch):
        self.raw.append((time.perf_counter(), touch.x, touch.y))
        return True

    def calcular_r(self, dt):
        self.activo = False
        t0 = self.raw[0][0]
        pts = [(x, z) for t, x, z in self.raw if t - t0 >= 1.0]
        n = len(pts)
        
        # Obtenemos el DPI de forma segura (por defecto 96 si no lo detecta)
        dpi = Metrics.dpi if Metrics.dpi > 0 else 96
        
        if n < 10:
            # Aquí calculamos r directamente usando el tamaño de 1 píxel
            r = 0.0254 / dpi
            self.text = f"Ruido menor a 1 px\nr = {r:.6f} m\nToca para repetir"
            print(f"r = {r:.6f} m (por 1 píxel)")
            return
            
        mx = sum(p[0] for p in pts) / n
        mz = sum(p[1] for p in pts) / n
        var = sum((x - mx)**2 + (z - mz)**2 for x, z in pts) / (2 * (n - 1))
        
        r = var**0.5 / dpi * 0.0254          # px -> metros
        self.text = f"r = {r:.6f} m\n({n} muestras)\nToca para repetir"
        print(f"r = {r:.6f} m")


class TestApp(App):
    def build(self):
        return Test(text="Pon un dedo y no lo muevas 10 s", font_size="22sp", halign="center")


if __name__ == "__main__":
    TestApp().run()
