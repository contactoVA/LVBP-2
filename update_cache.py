# update_cache.py
# Genera el cache usando compute_rows() y games_played_today_scl() del módulo standings_*
import json, os, sys, time
from datetime import datetime
from zoneinfo import ZoneInfo

# --- Import robusto del módulo principal ---
try:
    import standings_cascade_points_desc as standings
except Exception:
    import standings_cascade_points as standings  # fallback si el nombre no tiene _desc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, "standings_cache.json")
SEMANAS_FILE = os.path.join(BASE_DIR, "data", "semanas.json")
SCL = ZoneInfo("America/Santiago")

# --- Lista de exclusiones manuales ---
EXCLUDE_STRINGS = {
    "Yankees 0 - 0 Mets - 08-09-2025 - 9:40 pm (hora Chile)",
}

EXCLUDE_RULES = [
    {
        "home_team": "Yankees",
        "away_team": "Mets",
        "home_score": 0,
        "away_score": 0,
        "ended_at_local_contains": "08-09-2025 - 9:40"
    }
]

def _should_exclude_game(g):
    if isinstance(g, str):
        return g.strip() in EXCLUDE_STRINGS
    if isinstance(g, dict):
        for rule in EXCLUDE_RULES:
            ok = True
            for k, v in rule.items():
                if k == "ended_at_local_contains":
                    if v not in (g.get("ended_at_local") or ""):
                        ok = False
                        break
                else:
                    if g.get(k) != v:
                        ok = False
                        break
            if ok:
                return True
    return False

# ======================
# Normalización equipos
# ======================
TEAM_ALIASES = {
    "Boston Red Sox": "Red Sox",
    "New York Yankees": "Yankees",
    "Chicago Cubs": "Cubs",
    "Philadelphia Phillies": "Phillies",
    "Los Angeles Dodgers": "Dodgers",
    "Kansas City Royals": "Royals",
    "San Francisco Giants": "Giants",
    "New York Mets": "Mets",
    "St. Louis Cardinals": "Cardinals",
    "Toronto Blue Jays": "Blue Jays",
    "Detroit Tigers": "Tigers",
    "Arizona Diamondbacks": "Diamondbacks",
    "Houston Astros": "Astros",
    "San Diego Padres": "Padres"
}

def normalize_team(name: str) -> str:
    return TEAM_ALIASES.get(name, name)

def sync_semanas(semanas_json, resultados):
    """
    Marca juegos como JUGADO en semanas.json si aparecen en resultados.
    """
    for semana, juegos in semanas_json.get("semanas", {}).items():
        for juego in juegos:
            if juego["estado"] == "JUGADO":
                continue  # no tocar los que ya están jugados

            local = juego["local"]
            visitante = juego["visitante"]

            for r in resultados:
                team_home = normalize_team(r["home_team"])
                team_away = normalize_team(r["away_team"])
                score_home = r["home_score"]
                score_away = r["away_score"]

                # Match directo
                if team_home == local and team_away == visitante:
                    juego["resultado"] = f"{score_home}-{score_away}"
                    juego["estado"] = "JUGADO"
                    break

                # Match invertido
                if team_home == visitante and team_away == local:
                    juego["resultado"] = f"{score_away}-{score_home}"
                    juego["estado"] = "JUGADO"
                    break

    return semanas_json

# ======================
# Proceso principal
# ======================
def update_data_cache():
    ts = datetime.now(SCL).strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] Iniciando actualización del cache...")

    try:
        if not hasattr(standings, "compute_rows"):
            raise AttributeError("El módulo no define compute_rows()")
        if not hasattr(standings, "games_played_today_scl"):
            raise AttributeError("El módulo no define games_played_today_scl()")

        # 1) Tabla
        rows = standings.compute_rows()

        # 2) Juegos de HOY (hora Chile)
        games_today = standings.games_played_today_scl()
        games_today = [g for g in games_today if not _should_exclude_game(g)]

        # 3) Escribir standings_cache.json
        payload = {
            "standings": rows,
            "games_today": games_today,
            "last_updated": ts
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        # 4) Sincronizar semanas.json
        try:
            with open(SEMANAS_FILE, "r", encoding="utf-8") as f:
                semanas = json.load(f)
        except FileNotFoundError:
            semanas = {"semanas": {}}

        # games_today puede ser lista de strings u objetos.
        resultados = [g for g in games_today if isinstance(g, dict)]
        if resultados:
            semanas = sync_semanas(semanas, resultados)
            with open(SEMANAS_FILE, "w", encoding="utf-8") as f:
                json.dump(semanas, f, ensure_ascii=False, indent=2)

        print("Actualización completada exitosamente.")
        return True
    except Exception as e:
        print(f"ERROR durante la actualización del cache: {e}")
        return False

def _run_once_then_exit():
    ok = update_data_cache()
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    if "--once" in sys.argv or os.getenv("RUN_ONCE") == "1":
        _run_once_then_exit()

    UPDATE_INTERVAL_SECONDS = int(os.getenv("UPDATE_INTERVAL_SECONDS", "300"))
    while True:
        update_data_cache()
        print(f"Esperando {UPDATE_INTERVAL_SECONDS} segundos para la próxima actualización...")
        try:
            time.sleep(UPDATE_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("Detenido por el usuario.")
            break
