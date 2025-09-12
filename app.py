from flask import Flask, render_template, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)
CACHE_FILE = "standings_cache.json"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/full")
def api_full():
    if not os.path.exists(CACHE_FILE):
        return jsonify({"error": "Data not available yet, please try again in a few minutes."}), 503

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Opcional: añadir la marca de tiempo de la última actualización
        # === Integración: Semanas/Series ===
        # Carga fixture semanal y cruza con juegos de hoy del cache (si existen)
        try:
            data_dir = os.path.join(os.path.dirname(__file__), "data")
            semanas_path = os.path.join(data_dir, "semanas.json")
            if os.path.exists(semanas_path):
                with open(semanas_path, "r", encoding="utf-8") as sf:
                    semanas = json.load(sf)
                # Parsear juegos del día desde cache: lista de strings "Home X - Away Y - dd-mm-aaaa - hh:mm ..."
                raw_games = data.get("games_today", []) or []
                parsed = []
                for s in raw_games:
                    norm = (s or "").replace("\xa0"," ").strip()
                    parts = [p.strip() for p in norm.split(" - ")]
                    # Esperado: ["Home X", "Away Y", "dd-mm-aaaa", "hh:mm am/pm (hora Chile)"]
                    if len(parts) >= 4:
                        def split_last(txt):
                            txt = txt.strip()
                            i = txt.rfind(" ")
                            if i == -1:
                                return {"name": txt, "score": ""}
                            return {"name": txt[:i], "score": txt[i+1:]}
                        home = split_last(parts[0])
                        away = split_last(parts[1])
                        # Validar scores numéricos
                        try:
                            hscore = int(re.sub(r"[^0-9-]", "", home["score"]))
                        except:
                            hscore = None
                        try:
                            ascore = int(re.sub(r"[^0-9-]", "", away["score"]))
                        except:
                            ascore = None
                        parsed.append({
                            "home": home["name"],
                            "away": away["name"],
                            "home_score": hscore,
                            "away_score": ascore,
                            "raw": s
                        })
                # Actualizar semana actual con marcadores "Jugado" (sin tocar los "Simulado")
                semana_actual = str(semanas.get("semana_actual"))
                if semana_actual in semanas.get("semanas", {}):
                    for juego in semanas["semanas"][semana_actual]:
                        if juego.get("estado") == "Pendiente":
                            for g in parsed:
                                if g["home"] == juego["local"] and g["away"] == juego["visitante"] and (g["home_score"] is not None and g["away_score"] is not None):
                                    juego["estado"] = "Jugado"
                                    juego["resultado"] = f"{g['home_score']} - {g['away_score']}"
                                    break
                data["semana_actual"] = semanas.get("semana_actual")
                data["semanas"] = semanas.get("semanas")
        except Exception as _e:
            # No interrumpir /api/full si falla la parte de semanas
            data["semanas_error"] = str(_e)
    
        data["last_updated"] = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE)).strftime("%Y-%m-%d %H:%M:%S")
        
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Failed to read cached data: {e}"}), 500

if __name__ == "__main__":
    app.run(debug=True)