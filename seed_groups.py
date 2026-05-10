import sqlite3
import pandas as pd

DB = "database.db"

def seed():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("DELETE FROM matches")

    matches = pd.read_csv("matches.csv")
    teams = pd.read_csv("teams.csv")

    tmap = teams.set_index("id")["team_name"].to_dict()
    gmap = teams.set_index("id")["group_letter"].to_dict()

    matches = matches[matches["stage_id"] == 1].copy()

    matches["dt"] = pd.to_datetime(matches["kickoff_at"], utc=True)
    matches["dt"] = matches["dt"].dt.tz_convert("America/Argentina/Buenos_Aires")
    matches["dt"] = matches["dt"] - pd.Timedelta(hours=2)

    TRANSLATE = {
        "Iran": "Irán",
        "IR Iran": "Irán",
        "USA": "Estados Unidos",
        "United States": "Estados Unidos",
        "South Korea": "Corea del Sur",
        "Netherlands": "Países Bajos",
        "Ivory Coast": "Costa de Marfil",
        "Côte d'Ivoire": "Costa de Marfil",
        "DR Congo": "RD Congo",
        "Czechia": "Chequia",
        "Turkey": "Turquía",
        "Sweden": "Suecia",
        "Iraq": "Irak",
        "South Africa": "Sudáfrica",
        "Scotland": "Escocia",
        "Morocco": "Marruecos",
        "Brazil": "Brasil",
        "Tunisia": "Túnez",
        "Japan": "Japón",
        "Spain": "España",
        "Saudi Arabia": "Arabia Saudita",
        "Belgium": "Bélgica",
        "New Zealand": "Nueva Zelanda",
        "France": "Francia",
        "Norway": "Noruega",
        "Jordan": "Jordania",
        "Algeria": "Argelia",
        "England": "Inglaterra",
        "Croatia": "Croacia",
        "Qatar": "Catar",
        "Switzerland": "Suiza",
        "Germany": "Alemania",
        "Egypt": "Egipto",
        "Mexico": "México",
        "Canada":"Canadá",
        "Haiti":  "Haití",
        "Panama": "Panamá",
        "Uzbekistan":  "Uzbekistán"
    }

    PLAYOFF_FIX = {
        "Winner UEFA Playoff A": "Bosnia y Herzegovina",
        "Winner UEFA Playoff B": "Suecia",
        "Winner UEFA Playoff C": "Turquía",
        "Winner UEFA Playoff D": "Chequia",
        "Winner FIFA Playoff 1": "RD Congo",
        "Winner FIFA Playoff 2": "Irak",
    }

    rows = []

    for _, m in matches.iterrows():
        home = tmap.get(m["home_team_id"])
        away = tmap.get(m["away_team_id"])

        if not home or not away:
            continue

        # playoffs primero
        home = PLAYOFF_FIX.get(home, home)
        away = PLAYOFF_FIX.get(away, away)

        # traducción después
        home = TRANSLATE.get(home, home)
        away = TRANSLATE.get(away, away)

        group = gmap.get(m["home_team_id"]) or gmap.get(m["away_team_id"])

        dt = m["dt"].isoformat()

        rows.append((home, away, dt, group))

    rows.sort(key=lambda x: x[2])

    for r in rows:
        c.execute("""
            INSERT INTO matches (home, away, match_datetime, stage)
            VALUES (?, ?, ?, ?)
        """, r)

    conn.commit()
    conn.close()

    print(f"✅ Seed real cargado ({len(rows)} partidos)")


if __name__ == "__main__":
    seed()