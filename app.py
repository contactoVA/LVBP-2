# app.py
from flask import Flask, render_template, jsonify
import json
import os
import re
from datetime import datetime

app = Flask(__name__)
CACHE_FILE = "standings_cache.json"

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

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

        # ==============================
        # Integración: Semanas/Series
        # ==============================
        try:
            data_dir = os.path.join(os.path.dirname(__file__), "data")
            semanas_path = os.path.join(data_dir, "semanas.json")
            if os.path.exists(semanas_path):
                semanas = load_json(semanas_path)

                # Normalizamos lista de juegos jugados desde cache
                games_today = data.get("games_today", []) or []
                parsed_games = []

                def split_last(txt):
                    txt = txt.strip()
                    i = txt.rfind(" ")
                    if i == -1:
                        return {"name": txt, "score": ""}
                    return {"name": txt[:i], "score": txt[i + 1 :]}

                for g in games_today:
                    if isinstance(g, str):
                        norm = (g or "").replace("\xa0", " ").strip()
                        parts = [p.strip() for p in norm.split(" - ")]
                        if len(parts) >= 4:
                            home = split_last(parts[0])
                            away = split_last(parts[1])
                            try:
                                hscore = int(re.sub(r"[^0-9-]", "", home["score"]))
                            except:
                                hscore = None
                            try:
                                ascore = int(re.sub(r"[^0-9-]", "", away["score"]))
                            except:
                                ascore = None
                            parsed_games.append(
                                {
                                    "home": home["name"],
                                    "away": away["name"],
                                    "home_score": hscore,
                                    "away_score": ascore,
                                }
                            )
                    elif isinstance(g, dict):
                        parsed_games.append(
                            {
                                "home": g.get("home_team"),
                                "away": g.get("away_team"),
                                "home_score": g.get("home_score"),
                                "away_score": g.get("away_score"),
                            }
                        )

                # === Actualizar semana actual con marcadores "JUGADO" ===
                semana_actual = str(semanas.get("semana_actual"))
                if semana_actual in semanas.get("semanas", {}):
                    used_games = []
                    for juego in semanas["semanas"][semana_actual]:
                        if juego.get("estado") == "Pendiente":
                            for g in parsed_games:
                                if g in used_games:
                                    continue
                                if (
                                    g["home"] == juego["local"]
                                    and g["away"] == juego["visitante"]
                                    and g["home_score"] is not None
                                    and g["away_score"] is not None
                                ):
                                    juego["estado"] = "JUGADO"
                                    juego["resultado"] = f"{g['home_score']}-{g['away_score']}"
                                    used_games.append(g)
                                    break

                # === SOLO DESPUÉS aplicar overrides ===
                # ###MARCA_OVERRIDES###
                try:
                    overrides_path = os.path.join(data_dir, "manual_overrides.json")
                    if os.path.exists(overrides_path):
                        overrides = load_json(overrides_path)
                        for key, val in overrides.items():
                            for juego in semanas["semanas"].get(semana_actual, []):
                                if (
                                    juego.get("local") == val.get("local")
                                    and juego.get("visitante") == val.get("visitante")
                                ):
                                    if "resultado" in val:
                                        juego["resultado"] = val["resultado"]
                                    if "estado" in val:
                                        juego["estado"] = val["estado"]
                except Exception as e:
                    data["overrides_error"] = str(e)

                # Agregar semanas al payload
                data["semana_actual"] = semanas.get("semana_actual")
                data["semanas"] = semanas.get("semanas")

        except Exception as _e:
            # No interrumpir /api/full si falla la parte de semanas
            data["semanas_error"] = str(_e)

        # Última actualización
        data["last_updated"] = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Failed to read cached data: {e}"}), 500

if __name__ == "__main__":
    app.run(debug=True)
