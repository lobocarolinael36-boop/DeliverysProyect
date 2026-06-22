# vista.py
import tkinter as tk
from tkinter import ttk, messagebox
import tkintermapview

C_BG, C_PANEL, C_DARK, C_ENTRY, C_BTN = "#1e2a3a", "#2c3e50", "#1a252f", "#34495e", "#2980b9"
C_GREEN, C_RED, C_ORANGE, C_TEXT, C_MUTED = "#16a085", "#e74c3c", "#e67e22", "#ecf0f1", "#7f8c8d"

class LogisticaVista(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Monitoreo y Gestión Logística de Despacho Seguro — CABA")
        self.geometry("1140x700")
        self.minsize(900, 580)
        self.configure(bg=C_BG)
        self._configurar_estilos()
        self._crear_componentes()

    def _configurar_estilos(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=C_PANEL, borderwidth=0, tabmargins=0)
        style.configure("TNotebook.Tab", background=C_DARK, foreground=C_MUTED, padding=[12, 5], font=("Arial", 9))
        style.map("TNotebook.Tab", background=[("selected", C_BTN)], foreground=[("selected", "white")])
        style.configure("TFrame", background=C_PANEL)

    def _crear_componentes(self):
        # Barra de estado
        self.bar_estado = tk.Frame(self, bg=C_DARK, height=22)
        self.bar_estado.pack(side=tk.BOTTOM, fill=tk.X)
        self.bar_estado.pack_propagate(False)
        self.lbl_estado = tk.Label(self.bar_estado, text="  Sistema listo", bg=C_DARK, fg=C_MUTED, font=("Arial", 8), anchor="w")
        self.lbl_estado.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(self.bar_estado, text="GCBA API  |  OSRM  |  Nominatim  |  Open-Meteo  ", bg=C_DARK, fg="#3d5166", font=("Arial", 8)).pack(side=tk.RIGHT)

        # Panel izquierdo
        fr_izq = tk.Frame(self, bg=C_PANEL, width=380)
        fr_izq.pack(side=tk.LEFT, fill=tk.Y)
        fr_izq.pack_propagate(False)

        tk.Label(fr_izq, text="DESPACHO SEGURO", bg=C_PANEL, fg=C_TEXT, font=("Arial", 13, "bold")).pack(pady=(14, 1))
        tk.Label(fr_izq, text="Sistema Logístico · Ciudad de Buenos Aires", bg=C_PANEL, fg=C_MUTED, font=("Arial", 8)).pack()
        tk.Frame(fr_izq, height=1, bg=C_ENTRY).pack(fill=tk.X, padx=10, pady=8)

        self.notebook = ttk.Notebook(fr_izq)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=0)

        # Tab 1: Planificador
        self.tab1 = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(self.tab1, text="  Planificador  ")

        self.entrada_salida = self._build_entry(self.tab1, "Punto de salida:")
        self.entrada_destino = self._build_entry(self.tab1, "Punto de destino:")
        self.entrada_hora = self._build_entry(self.tab1, "Hora de salida (HH:MM):")
        self.entrada_hora.insert(0, "12:00")

        self.btn_calcular = tk.Button(self.tab1, text="Calcular Recorrido", bg=C_BTN, fg="white", font=("Arial", 10, "bold"), relief="flat", cursor="hand2", pady=6)
        self.btn_calcular.pack(fill=tk.X, padx=14, pady=(10, 4))

        fr_res = tk.Frame(self.tab1, bg=C_DARK)
        fr_res.pack(fill=tk.X, padx=14, pady=6)
        _kw = dict(bg=C_DARK, fg=C_TEXT, font=("Courier", 9), anchor="w")
        self.lbl_dist = tk.Label(fr_res, text="  Distancia:  —", **_kw)
        self.lbl_tiempo = tk.Label(fr_res, text="  Tiempo est: —", **_kw)
        self.lbl_clima = tk.Label(fr_res, text="  Clima:  —", **_kw)
        self.lbl_trafico = tk.Label(fr_res, text="  Tráfico:  —", **_kw)
        for w in (self.lbl_dist, self.lbl_tiempo, self.lbl_clima, self.lbl_trafico): w.pack(fill=tk.X, pady=1)

        self.lbl_alerta = tk.Label(self.tab1, text="Ingrese origen y destino para calcular", bg=C_PANEL, fg=C_MUTED, font=("Arial", 9, "bold"), wraplength=340, justify="center")
        self.lbl_alerta.pack(pady=8, padx=14)

        tk.Frame(self.tab1, height=1, bg=C_ENTRY).pack(fill=tk.X, padx=10, pady=4)
        tk.Label(self.tab1, text="Historial de despachos:", bg=C_PANEL, fg="#bdc3c7", font=("Arial", 9, "bold")).pack(anchor="w", padx=14)

        self.lb_historial = tk.Listbox(self.tab1, height=5, bg=C_DARK, fg="#8899aa", font=("Courier", 7), relief="flat", bd=0, activestyle="none")
        self.lb_historial.pack(fill=tk.X, padx=14, pady=(2, 10))

        # Tab 2: Alertas
        self.tab2 = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(self.tab2, text="  Alertas GCBA  ")

        tk.Label(self.tab2, text="Alertas de Servicio en Tiempo Real", bg=C_PANEL, fg=C_TEXT, font=("Arial", 10, "bold")).pack(pady=(12, 2))
        self.btn_gcba = tk.Button(self.tab2, text="Actualizar alertas GCBA", bg=C_GREEN, fg="white", font=("Arial", 9, "bold"), relief="flat", cursor="hand2", pady=5)
        self.btn_gcba.pack(fill=tk.X, padx=14, pady=10)

        fr_lb = tk.Frame(self.tab2, bg=C_PANEL)
        fr_lb.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))
        self.lb_alertas = tk.Listbox(fr_lb, bg=C_DARK, fg=C_TEXT, font=("Arial", 8), relief="flat", bd=0, activestyle="none")
        self.lb_alertas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Panel derecho: Mapa
        fr_mapa = tk.Frame(self, bg=C_BG)
        fr_mapa.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.mapa = tkintermapview.TkinterMapView(fr_mapa, corner_radius=0)
        self.mapa.pack(fill=tk.BOTH, expand=True)
        self.mapa.set_position(-34.6037, -58.3816)
        self.mapa.set_zoom(12)

    def _build_entry(self, parent, text):
        tk.Label(parent, text=text, bg=C_PANEL, fg="#bdc3c7", font=("Arial", 9, "bold"), anchor="w").pack(fill=tk.X, padx=14, pady=(8, 1))
        e = tk.Entry(parent, font=("Arial", 10), bg=C_ENTRY, fg=C_TEXT, insertbackground=C_TEXT, relief="flat", bd=4)
        e.pack(fill=tk.X, padx=14, pady=(0, 2))
        return e

    def set_estado(self, msg):
        self.lbl_estado.config(text=f"  {msg}")