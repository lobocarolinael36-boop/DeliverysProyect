import requests
from datetime import datetime

GCBA_CLIENT_ID     = "09d5119087564abe95e0b062200f32ae"
GCBA_CLIENT_SECRET = "3Cb1AD4CFCd34100B2F7e4a3143A2a3C"
GCBA_BASE_URL      = "https://apitransporte.buenosaires.gob.ar"

class LogisticaModelo:
    def __init__(self):
        self.despachos_log = []

    def obtener_factor_trafico(self, hora_texto):
        hora = datetime.strptime(hora_texto, "%H:%M").time()
        h = hora.hour + hora.minute / 60.0
        if   7.0 <= h < 10.0: return 2.0,  "Hora pico mañana",  "alto"
        elif 16.0 <= h < 19.0: return 2.5, "Hora pico tarde",   "critico"
        elif 10.0 <= h < 16.0: return 1.2, "Tráfico normal",    "medio"
        else:                   return 1.0, "Tráfico fluido",    "bajo"

    def calcular_ruta_completa(self, salida, destino, hora_txt):
        factor, estado_tr, nivel_tr = self.obtener_factor_trafico(hora_txt)
        hdr = {"User-Agent": "LogisticaDespacho/2.0"}
        geo = "https://nominatim.openstreetmap.org/search"

        # Geocodificación Salida
        r = requests.get(geo, params={"format": "json", "q": f"{salida}, CABA, Argentina"}, headers=hdr, timeout=10).json()
        if not r: raise Exception("No se encontró la dirección de salida.")
        ls, lo = float(r[0]["lat"]), float(r[0]["lon"])

        # Geocodificación Destino
        r = requests.get(geo, params={"format": "json", "q": f"{destino}, CABA, Argentina"}, headers=hdr, timeout=10).json()
        if not r: raise Exception("No se encontró la dirección de destino.")
        ld, lo_d = float(r[0]["lat"]), float(r[0]["lon"])

        # OSRM Dirección Ruta
        ruta_url = f"https://router.project-osrm.org/route/v1/driving/{lo},{ls};{lo_d},{ld}?overview=full&geometries=geojson"
        ruta = requests.get(ruta_url, timeout=10).json()
        if "routes" not in ruta: raise Exception("Ruta no disponible (OSRM).")

        dist_km = ruta["routes"][0]["distance"] / 1000
        dur_min = int((ruta["routes"][0]["duration"] / 60) * factor)
        coords = ruta["routes"][0]["geometry"]["coordinates"]

        # Open-Meteo Clima
        clima_url = f"https://api.open-meteo.com/v1/forecast?latitude={ld}&longitude={lo_d}&current=temperature_2m,weather_code"
        cl = requests.get(clima_url, timeout=10).json()
        temp = cl["current"]["temperature_2m"]
        wcode = cl["current"]["weather_code"]

        if   51 <= wcode <= 67: cielo, riesgo_c = "Lluvioso",  "medio"
        elif wcode >= 95:       cielo, riesgo_c = "Tormenta",  "alto"
        else:                   cielo, riesgo_c = "Despejado", "bajo"

        return {
            "dist_km": dist_km, "dur_min": dur_min, "temp": temp, "cielo": cielo,
            "estado_tr": estado_tr, "nivel_tr": nivel_tr, "riesgo_c": riesgo_c,
            "coords": coords, "ls": ls, "lo": lo, "ld": ld, "lo_d": lo_d
        }

    def consultar_alertas_gcba(self):
        url = f"{GCBA_BASE_URL}/subtes/serviceAlerts"
        params = {"client_id": GCBA_CLIENT_ID, "client_secret": GCBA_CLIENT_SECRET, "json": 1}
        resp = requests.get(url, params=params, timeout=12)
        resp.raise_for_status()
        return resp.json()