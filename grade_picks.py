import os
import glob
import json
import pandas as pd
import requests

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
    
    # Determine actual game winners
    api_winners = []
    for event in api_data.get('events', []):
        comp = event['competitions'][0]
        teams = comp['competitors']
        t1, t2 = teams[0], teams[1]
        
        s1 = int(t1.get('score', 0)) if t1.get('score') else 0
        s2 = int(t2.get('score', 0)) if t2.get('score') else 0
        
        if s1 > s2: api_winners.append(t1['team']['abbreviation'])
        elif s2 > s1: api_winners.append(t2['team']['abbreviation'])

    # Map the columns using the Olds Dictionary
    mapped_teams = [c for c in df.columns if str(c).strip() in team_aliases]
    sheet_games = len(mapped_teams) // 2
    
    # Flag for the warning banner
    if sheet_games != expected_games and expected_games > 0:
        warnings.append(f"Week {week_num}: Excel has {sheet_games} games, but ESPN scheduled {expected_games}.")

    week_scores = []
    for index, row in df.iterrows():
        player_name = str(row.iloc[0]).strip()
        
        # Skip empty rows or header rows
        if pd.isna(player_name) or player_name.lower() in ['nan', 'tie breaker'] or player_name.lower().startswith('nfl week'):
            continue
            
        score = 0
        for col in mapped_teams:
            team_abbr = team_aliases[str(col).strip()]
            cell_val = row[col]
            
            # 2. "Anything Goes" Pick Detector
            if pd.notna(cell_val) and str(cell_val).strip() != '':
                if team_abbr in api_winners:
                    score += 1
                    
        week_scores.append({"Player": player_name, "Wins": score})
    
    # Sort leaderboard highest to lowest
    week_scores = sorted(week_scores, key=lambda x: x['Wins'], reverse=True)
    all_results[f"Week {week_num}"] = week_scores

# Save JSON data in the background
with open("standings.json", "w") as f:
    json.dump(all_results, f, indent=4)

# 3. Generate the Static HTML Dashboard
html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Office Pick'em Pool</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 0; padding: 20px; background-color: #f0f2f6; color: #31333F; }}
        h1 {{ text-align: center; padding-bottom: 10px; }}
        .warning-banner {{ background-color: #ffbd45; color: #000; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .warning-banner small {{ font-weight: normal; display: block; margin-top: 5px; }}
        .week-container {{ background: #ffffff; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
        h2 {{ margin-top: 0; color: #000; border-bottom: 2px solid #f0f2f6; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ padding: 12px 10px; text-align: left; border-bottom: 1px solid #f0f2f6; }}
        th {{ background-color: #fafafa; font-size: 0.85rem; color: #666; text-transform: uppercase; }}
        tr:hover {{ background-color: #f8f9fa; }}
        td:nth-child(2), th:nth-child(2) {{ text-align: right; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>🏈 Office Pick'em Leaderboard</h1>
"""

if warnings:
    html_content += "<div class='warning-banner'>⚠️ UPDATE THE OLDS DICTIONARY!"
    for w in warnings:
        html_content += f"<small>{w}</small>"
    html_content += "</div>"

# Display newest weeks at the top
for week, scores in reversed(list(all_results.items())):
    html_content += f"<div class='week-container'><h2>{week}</h2><table><tr><th>Player</th><th>Wins</th></tr>"
    for s in scores:
        html_content += f"<tr><td>{s['Player']}</td><td>{s['Wins']}</td></tr>"
    html_content += "</table></div>"

html_content += "</body></html>"

# Literally write the web page for GitHub Pages to host
with open("index.html", "w") as f:
    f.write(html_content)
    
