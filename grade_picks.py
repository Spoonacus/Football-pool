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
            pick_logo = None
            if game['home'] in user_picks:
                pick_abbr = game['home']
                pick_logo = game['home_logo']
            elif game['away'] in user_picks:
                pick_abbr = game['away']
                pick_logo = game['away_logo']
                
            status_class = "pending"
            if game['state'] == 'post':
                if pick_abbr == game['winner']:
                    score += 1
                    status_class = "win"
                elif pick_abbr is not None:
                    status_class = "loss"
                else:
                    status_class = "missing"
                    
            player_picks.append({
                "pick": pick_abbr,
                "logo": pick_logo,
                "status": status_class
            })
                    
        week_scores.append({"Player": player_name, "Wins": score, "Picks": player_picks})
    
    # Sort leaderboard highest to lowest
    week_scores = sorted(week_scores, key=lambda x: x['Wins'], reverse=True)
    all_results[f"Week {week_num}"] = {
        "games": api_games,
        "scores": week_scores
    }

sorted_weeks = sorted(all_results.keys(), key=lambda x: int(x.replace("Week ", "")), reverse=True)

# Generate dropdown filter options
dropdown_options = ""
for w in sorted_weeks:
    w_id = w.replace(" ", "-")
    dropdown_options += f"<option value='{w_id}'>{w}</option>\n"
dropdown_options += "<option value='all'>Show All Weeks</option>"

# 3. Generate the Static HTML Dashboard
html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Office Pick'em Pool</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 0; padding: 15px; background-color: #f0f2f6; color: #31333F; }}
        h1 {{ text-align: center; padding-bottom: 5px; font-size: 1.6rem; margin-bottom: 5px; }}
        
        .filter-container {{ text-align: center; margin-bottom: 20px; }}
        select#week-filter {{ padding: 8px 16px; font-size: 1rem; border-radius: 8px; border: 1px solid #ccc; font-weight: bold; background: #fff; outline: none; }}
        
        .warning-banner {{ background-color: #ffbd45; color: #000; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .warning-banner small {{ font-weight: normal; display: block; margin-top: 5px; }}
        
        .week-container {{ background: #ffffff; padding: 15px 0 0 0; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
        
        .week-header-bar {{ display: flex; justify-content: space-between; align-items: center; padding: 0 15px 10px 15px; border-bottom: 2px solid #f0f2f6; }}
        .week-header-bar h2 {{ margin: 0; color: #000; font-size: 1.3rem; }}
        .expand-btn {{ background: #e6f4ea; color: #137333; border: 1px solid #c3e6cb; padding: 6px 12px; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 0.85rem; outline: none; }}
        .instruction-text {{ font-size: 0.8rem; color: #888; padding: 10px 15px; font-style: italic; }}
        
        /* Horizontal Scroll Framework */
        .horizontal-scroll-area {{ overflow-x: auto; white-space: nowrap; padding-bottom: 15px; }}
        
        /* Flex Rows */
        .grid-row {{ display: flex; width: max-content; min-width: 100%; border-bottom: 1px solid #f0f2f6; cursor: pointer; background-color: #fff; transition: background-color 0.2s; }}
        .grid-row:hover {{ background-color: #f8f9fa; }}
        .header-row {{ background-color: #fafafa; cursor: default; border-bottom: 2px solid #e0e0e0; }}
        .header-row:hover {{ background-color: #fafafa; }}
        
        /* Sticky Left Columns */
        .locked-cols {{ position: sticky; left: 0; z-index: 2; display: flex; align-items: center; background-color: inherit; border-right: 2px solid #e0e0e0; }}
        .col-name {{ width: 110px; padding: 12px 10px; font-weight: bold; font-size: 0.95rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .col-wins {{ width: 45px; padding: 12px 10px; font-weight: 900; font-size: 1.1rem; text-align: center; }}
        .header-row .col-name, .header-row .col-wins {{ font-size: 0.8rem; color: #555; text-transform: uppercase; font-weight: normal; }}
        
        /* Scrolling Game Columns */
        .scroll-cols {{ display: flex; align-items: center; }}
        .player-row.collapsed .scroll-cols {{ display: none; }}
        
        .game-cell {{ width: 95px; padding: 8px 4px; display: flex; flex-direction: column; align-items: center; justify-content: center; }}
        
        /* Matchup Header Styling */
        .matchup-logos {{ display: flex; justify-content: center; align-items: center; gap: 4px; margin-bottom: 4px; }}
        .matchup-logos img {{ width: 24px; height: 24px; object-fit: contain; }}
        .matchup-text {{ color: #555; font-size: 0.75rem; font-weight: bold; }}
        
        /* Pick Pill Styling */
        .pick-box {{ display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 0.85rem; font-weight: 800; border-radius: 6px; padding: 6px 8px; width: 85px; box-sizing: border-box; }}
        .pick-box img {{ width: 22px; height: 22px; object-fit: contain; border-radius: 4px; }}
        
        .pick-box.win {{ background-color: #e6f4ea; color: #137333; border: 1px solid #137333; }}
        .pick-box.loss {{ background-color: #fce8e6; color: #c5221f; border: 1px solid #c5221f; }}
        .pick-box.pending {{ background-color: #f1f3f4; color: #5f6368; border: 1px solid #dadce0; }}
        .pick-box.missing {{ background-color: #ffffff; color: #ccc; border: 1px dashed #ccc; font-weight: normal; }}
    </style>
    
    <script>
        function toggleRow(row) {{
            row.classList.toggle('collapsed');
        }}
        
        function toggleWeek(btn) {{
            const container = btn.closest('.week-container');
            const rows = container.querySelectorAll('.player-row');
            const isExpanding = btn.innerText === "Expand All";
            
            rows.forEach(row => {{
                if (isExpanding) {{
                    row.classList.remove('collapsed');
                }} else {{
                    row.classList.add('collapsed');
                }}
            }});
            
            btn.innerText = isExpanding ? "Collapse All" : "Expand All";
            btn.style.backgroundColor = isExpanding ? "#fce8e6" : "#e6f4ea";
            btn.style.color = isExpanding ? "#c5221f" : "#137333";
            btn.style.borderColor = isExpanding ? "#f5c6cb" : "#c3e6cb";
        }}
        
        function filterWeek() {{
            const selected = document.getElementById('week-filter').value;
            const containers = document.querySelectorAll('.week-container');
            
            containers.forEach(container => {{
                if (selected === 'all' || container.id === selected) {{
                    container.style.display = 'block';
                }} else {{
                    container.style.display = 'none';
                }}
            }});
        }}
        
        // Run the filter automatically on page load to hide older weeks
        window.onload = function() {{
            filterWeek();
        }};
    </script>
</head>
<body>
    <h1>🏈 Office Pick'em</h1>
    <div class="filter-container">
        <select id="week-filter" onchange="filterWeek()">
            {dropdown_options}
        </select>
    </div>
"""

if warnings:
    html_content += "<div class='warning-banner'>⚠️ UPDATE THE OLDS DICTIONARY!"
    for w in warnings: html_content += f"<small>{w}</small>"
    html_content += "</div>"

for week_key in sorted_weeks:
    week_id = week_key.replace(" ", "-")
    week_data = all_results[week_key]
    api_games = week_data["games"]
    scores = week_data["scores"]
    
    html_content += f"""
    <div class='week-container' id="{week_id}">
        <div class="week-header-bar">
            <h2>{week_key}</h2>
            <button class="expand-btn" onclick="toggleWeek(this)">Expand All</button>
        </div>
        <div class="instruction-text">Tap any player's row to view their picks. Scroll right to see all games.</div>
        <div class="horizontal-scroll-area">
            
            <!-- Header Row with Matchups -->
            <div class="grid-row header-row">
                <div class="locked-cols">
                    <div class="col-name">Player</div>
                    <div class="col-wins">Wins</div>
                </div>
                <div class="scroll-cols">
    """
    
    for g in api_games:
        html_content += f"""
                    <div class="game-cell">
                        <div class="matchup-logos">
                            <img src="{g['away_logo']}" title="{g['away']}"> 
                            <span style="color: #888; font-size: 0.7rem;">@</span> 
                            <img src="{g['home_logo']}" title="{g['home']}">
                        </div>
                        <div class="matchup-text">{g['away']} @ {g['home']}</div>
                    </div>
        """
        
    html_content += """
                </div>
            </div>
    """
    
    # Player Rows (Collapsed by default)
    for s in scores:
        html_content += f"""
            <div class="grid-row player-row collapsed" onclick="toggleRow(this)">
                <div class="locked-cols">
                    <div class="col-name">{s['Player']}</div>
                    <div class="col-wins">{s['Wins']}</div>
                </div>
                <div class="scroll-cols">
        """
        
        for p in s['Picks']:
            if p['pick']:
                html_content += f"""
                    <div class="game-cell">
                        <div class="pick-box {p['status']}">
                            <img src="{p['logo']}"> <span>{p['pick']}</span>
                        </div>
                    </div>
                """
            else:
                html_content += """
                    <div class="game-cell">
                        <div class="pick-box missing">-</div>
                    </div>
                """
                
        html_content += """
                </div>
            </div>
        """
        
    html_content += """
        </div>
    </div>
    """

html_content += "</body></html>"

# Write the web page for GitHub Pages to host
with open("index.html", "w") as f:
    f.write(html_content)
    
