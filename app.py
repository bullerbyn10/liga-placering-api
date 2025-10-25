from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import requests
import json
import os
from fastapi.middleware.cors import CORSMiddleware


# =============================
# CONFIG
# =============================
API_TOKEN = os.getenv("API_TOKEN")
BASE_URL = "https://api.football-data.org/v4"

app = FastAPI(title="Football Match Importance API",
              description="Calculates match importance based on standings from football-data.org",
              version="1.0.0")
# =============================
# CORS MIDDLEWARE
# =============================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # eller ["https://figma.com", "https://your-app.render.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# =============================
# HELPER FUNCTIONS
# =============================

def get_standings(competition_code: str):
    """Fetch standings and calculate season progress."""
    url = f"{BASE_URL}/competitions/{competition_code}/standings"
    headers = {"X-Auth-Token": API_TOKEN}
    response = requests.get(url, headers=headers)

    if not response.ok:
        raise Exception(f"API request failed: {response.status_code} - {response.text}")

    data = response.json()
    standings = data["standings"][0]["table"]

    total_teams = len(standings)
    avg_played = sum(team["playedGames"] for team in standings) / total_teams
    total_games_per_team = (total_teams - 1) * 2
    progress = avg_played / total_games_per_team

    table = {
        team["team"]["name"].lower(): {
            "position": team["position"],
            "played": team["playedGames"],
            "points": team["points"]
        }
        for team in standings
    }

    return table, total_teams, progress


def match_importance(pos1, pos2, total_teams, progress):
    """Determine match importance."""
    if progress < 0.33:
        stage = "early season"
    elif progress < 0.66:
        stage = "mid-season"
    else:
        stage = "end of the season"

    top_zone = max(3, round(total_teams * 0.2))
    bottom_zone = max(3, round(total_teams * 0.2))

    top_teams = pos1 <= top_zone and pos2 <= top_zone
    bottom_teams = pos1 > total_teams - bottom_zone and pos2 > total_teams - bottom_zone

    if top_teams:
        return f" Top clash ({stage})"
    elif bottom_teams:
        return f" Relegation battle ({stage})"
    elif (pos1 <= top_zone and pos2 > total_teams / 2) or (pos2 <= top_zone and pos1 > total_teams / 2):
        return f" Important for top team ({stage})"
    elif (pos1 > total_teams - bottom_zone and pos2 < total_teams / 2) or (pos2 > total_teams - bottom_zone and pos1 < total_teams / 2):
        return f" Important for bottom team ({stage})"
    else:
        return f" Regular match ({stage})"


def find_team(name, standings):
    """Find the matching team name (supports partial matches)."""
    name = name.lower()
    for t in standings.keys():
        if name in t:
            return t
    return None


# =============================
# API ROUTES
# =============================

@app.get("/matchinfo")
def get_match_info(
    league: str = Query(..., description="League code (e.g. PL, PD, SA, BL1)"),
    team1: str = Query(..., description="First team name"),
    team2: str = Query(..., description="Second team name")
):
    """
    Returns match importance between two teams in a given league.
    Example:
    /matchinfo?league=PL&team1=Arsenal&team2=Manchester%20City
    """
    try:
        standings, total_teams, progress = get_standings(league)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    t1 = find_team(team1, standings)
    t2 = find_team(team2, standings)

    if not t1 or not t2:
        return JSONResponse(
            status_code=404,
            content={
                "error": "One or both teams were not found.",
                "available_teams": list(standings.keys())
            }
        )

    pos1 = standings[t1]["position"]
    pos2 = standings[t2]["position"]
    points1 = standings[t1]["points"]
    points2 = standings[t2]["points"]

    importance = match_importance(pos1, pos2, total_teams, progress)

    return {
        "league": league,
        "team1": {"name": t1, "position": pos1, "points": points1},
        "team2": {"name": t2, "position": pos2, "points": points2},
        "importance": importance,
        "season_progress": f"{progress*100:.1f}%"
    }


# =============================
# ROOT ENDPOINT
# =============================

@app.get("/")
def root():
    return {
        "message": "Welcome to the Football Match Importance API ⚽",
        "usage": "/matchinfo?league=PL&team1=Arsenal&team2=Manchester City"
    }
