import os
import glob
import json
import pandas as pd
import requests

def normalize_abbr(abbr):
    """Ensures ESPN's raw abbreviations match our dictionary standards."""
    abbr = abbr.upper()
    if abbr == 'WSH': return 'WAS'
    if abbr == 'OAK': return 'LV'
    if abbr == 'SD': return 'LAC'
    if abbr == 'STL': return 'LAR'
    return abbr

# 1. The "Olds" Dictionary
team_aliases = {
    "49ers": "SF", "Bears": "CHI", "Bengals": "CIN", "Bills": "BUF",
    "Broncos": "DEN", "Browns": "CLE", "Bucs": "TB", "Cardinals": "ARI", 
    "Chargers": "LAC", "Chiefs": "KC", "Colts": "IND", "Commanders": "WAS", 
    "Cowboys": "DAL", "Dolphins": "MIA", "Eagles": "PHI", "Falcons": "ATL",
    "Giants": "NYG", "Jaguars": "JAX", "Jets": "NYJ", "Lions": "DET",
    "Packers": "GB", "Panthers": "CAR", "Patriots": "NE", "Raiders": "LV",
    "Rams": "LAR", "Ravens": "BAL", "Saints": "NO", "Seahawks": "SEA",
    "Steelers": "PIT", "Texans": "HOU", "Titans": "TEN", "Vikings": "MIN",
    
    # Common Typos
    "Boncos": "DEN", "Commancers": "WAS", "Commanskins": "WAS", "Sehawks": "SEA"
}

warnings = []
all_results = {}

# Process every Excel file in the repository
excel_files = glob.glob("NFL Week *.xlsx")
for file in sorted(excel_files):
    week_str = file.replace("NFL Week ", "").replace(".xlsx", "")
    try:
        week_num = int(week_str)
    except ValueError:
        continue

    df = pd.read_excel(file)
    
    # Fetch ESPN Data for this specific week
    api_url = f"http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={week_num}"
    resp = requests.get(api_url)
    api_data = resp.json() if resp.status_code == 200 else {}
    expected_games = len(api_data.get('events', []))
    
    # Process ESPN Matchups to build dynamic game cards
    api_games = []
    for event in api_data.get('events', []):
        comp = event['competitions'][0]
        teams = comp['competitors']
        t_home = next((t for t in teams if t['homeAway'] == 'home'), teams[0])
        t_away = next((t for t in teams if t['homeAway'] == 'away'), teams[1])
        
        home_raw = t_home['team']['abbreviation']
        away_raw = t_away['team']['abbreviation']
        
        home_abbr = normalize_abbr(home_raw)
        away_abbr = normalize_abbr(away_raw)
        
        s_home = int(t_home.get('score', 0)) if t_home.get('score') else 0
        s_away = int(t_away.get('score', 0)) if t_away.get('score') else 0
        state = comp['status']['type']['state']
        
        winner = None
        if state == 'post':
            if s_home > s_away: winner = home_abbr
            elif s_away > s_home: winner = away_abbr
            else: winner = "TIE"
            
        api_games.append({
            "home": home_abbr,
            "away": away_abbr,
            "home_logo": f"https://a.espncdn.com/i/teamlogos/nfl/500/{home_raw.lower()}.png",
            "away_logo": f"https://a.espncdn.com/i/teamlogos/nfl/500/{away_raw.lower()}.png",
            "state": state,
            "winner": winner
        })
        
    mapped_teams = [c for c in df.columns if str(c).strip() in team_aliases]
    sheet_games = len(mapped_teams) // 2
    if sheet_games != expected_games and expected_games > 0:
        warnings.append(f"Week {week_num}: Excel has {sheet_games} games, but ESPN scheduled {expected_games}.")

    week_scores = []
    for index, row in df.iterrows():
        player_name = str(row.iloc[0]).strip()
        if pd.isna(player_name) or player_name.lower() in ['nan', 'tie breaker'] or player_name.lower().startswith('nfl week'):
            continue
            
        user_picks = set()
        for col in mapped_teams:
            cell_val = row[col]
            if pd.notna(cell_val) and str(cell_val).strip() != '':
                user_picks.add(team_aliases[str(col).strip()])

        score = 0
        player_picks = []
        for game in api_games:
            pick_abbr = None
            if game['home'] in user_picks:
                pick_abbr = game['home']
            elif game['away'] in user_picks:
                pick_abbr = game['away']
                
            status_class = "pending"
            if game['state'] == 'post':
                if pick_abbr == game['winner']:
                    score += 1
                    status_class = "win"
                elif pick_abbr is not None:
                    status_class = "loss"
                else:
                    status_class = "missing" # Treat missing picks as a loss (red) if game is over
                    
            player_picks.append({
                "home": game['home'],
                "away": game['away'],
                "home_logo": game['home_logo'],
                "away_logo": game['away_logo'],
                "pick": pick_abbr,
                "status": status_class
            })
                    
        week_scores.append({"Player": player_name, "Wins": score, "Picks": player_picks})
    
    # Sort leaderboard highest to lowest
    week_scores = sorted(week_scores, key=lambda x: x['Wins'], reverse=True)
    all_results[f"Week {week_num}"] = week_scores

sorted_weeks = sorted(all_results.keys(), key=lambda x: int(x.replace("Week ", "")), reverse=True)

# 3. Generate the Static HTML Dashboard with Expanding Accordions
html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Office Pick'em Pool</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, sans-serif; margin: 0; padding: 15px; background-color: #f0f2f6; color: #31333F; }
        h1 { text-align: center; padding-bottom: 10px; font-size: 1.6rem; }
        
        .warning-banner { background-color: #ffbd45; color: #000; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .warning-banner small { font-weight: normal; display: block; margin-top: 5px; }
        
        .week-container { margin-bottom: 30px; }
        h2 { margin: 0 0 15px 0; color: #000; padding-bottom: 10px; border-bottom: 2px solid #ddd; }
        
        /* Accordion (Details/Summary) Styling */
        details.player-card { background: #fff; border-radius: 8px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
        details.player-card summary { padding: 15px 20px; font-weight: bold; cursor: pointer; display: flex; justify-content: space-between; align-items: center; list-style: none; user-select: none; }
        details.player-card summary::-webkit-details-marker { display: none; }
        details.player-card summary:hover { background-color: #f8f9fa; }
        details.player-card[open] summary { border-bottom: 1px solid #eee; background-color: #fafafa; }
        
        /* Pick Grid */
        .picks-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 10px; padding: 15px; background: #fafafa; }
        
        /* Individual Game Cards */
        .pick-card { display: flex; flex-direction: column; align-items: center; padding: 10px; border-radius: 8px; border: 1px solid #ccc; text-align: center; }
        .pick-card .logos { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
        .pick-card .logos img { width: 28px; height: 28px; object-fit: contain; }
        .pick-card .teams { font-size: 0.8rem; color: #555; margin-bottom: 8px; font-weight: bold; }
        .pick-card .pick-text { font-size: 0.9rem; font-weight: 900; padding-top: 8px; border-top: 1px solid rgba(0,0,0,0.1); width: 100%; }
        
        /* Win / Loss / Pending Colors */
        .pick-card.win { background-color: #e6f4ea; border-color: #137333; }
        .pick-card.win .pick-text { color: #137333; }
        
        .pick-card.loss, .pick-card.missing { background-color: #fce8e6; border-color: #c5221f; }
        .pick-card.loss .pick-text, .pick-card.missing .pick-text { color: #c5221f; }
        
        .pick-card.pending { background-color: #fff; border-color: #dadce0; }
        .pick-card.pending .pick-text { color: #5f6368; }
    </style>
</head>
<body>
    <h1>🏈 Office Pick'em Leaderboard</h1>
"""

if warnings:
    html_content += "<div class='warning-banner'>⚠️ UPDATE THE OLDS DICTIONARY!"
    for w in warnings: html_content += f"<small>{w}</small>"
    html_content += "</div>"

for week_key in sorted_weeks:
    scores = all_results[week_key]
    
    html_content += f"<div class='week-container'><h2>{week_key}</h2>"
    
    for s in scores:
        html_content += f"""
        <details class="player-card">
            <summary>
                <span style="font-size: 1.1rem; color: #333;">{s['Player']}</span>
                <span style="font-size: 1.1rem; color: #000;">{s['Wins']} Wins</span>
            </summary>
            <div class="picks-grid">
        """
        
        for p in s['Picks']:
            pick_text = f"Picked: {p['pick']}" if p['pick'] else "NO PICK"
            status = p['status']
            
            html_content += f"""
                <div class="pick-card {status}">
                    <div class="logos">
                        <img src="{p['away_logo']}" title="{p['away']}"> 
                        <span style="font-size:0.8rem; color:#888;">@</span> 
                        <img src="{p['home_logo']}" title="{p['home']}">
                    </div>
                    <div class="teams">{p['away']} @ {p['home']}</div>
                    <div class="pick-text">{pick_text}</div>
                </div>
            """
            
        html_content += """
            </div>
        </details>
        """
        
    html_content += "</div>\n"

html_content += "</body></html>"

# Write the web page for GitHub Pages to host
with open("index.html", "w") as f:
    f.write(html_content)
        
