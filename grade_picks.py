import glob
import time
import pandas as pd
import requests

def normalize_abbr(abbr):
    abbr = abbr.upper()
    if abbr == 'WSH': return 'WAS'
    if abbr == 'OAK': return 'LV'
    if abbr == 'SD': return 'LAC'
    if abbr == 'STL': return 'LAR'
    return abbr

team_aliases = {
    "49ers": "SF", "Bears": "CHI", "Bengals": "CIN", "Bills": "BUF",
    "Broncos": "DEN", "Browns": "CLE", "Bucs": "TB", "Cardinals": "ARI", 
    "Chargers": "LAC", "Chiefs": "KC", "Colts": "IND", "Commanders": "WAS", 
    "Cowboys": "DAL", "Dolphins": "MIA", "Eagles": "PHI", "Falcons": "ATL",
    "Giants": "NYG", "Jaguars": "JAX", "Jets": "NYJ", "Lions": "DET",
    "Packers": "GB", "Panthers": "CAR", "Patriots": "NE", "Raiders": "LV",
    "Rams": "LAR", "Ravens": "BAL", "Saints": "NO", "Seahawks": "SEA",
    "Steelers": "PIT", "Texans": "HOU", "Titans": "TEN", "Vikings": "MIN",
    "Boncos": "DEN", "Commancers": "WAS", "Commanskins": "WAS", 
    "Sehawks": "SEA"
}

warnings = []
all_results = {}

excel_files = glob.glob("NFL Week *.xlsx")
for file in sorted(excel_files):
    week_str = file.replace("NFL Week ", "").replace(".xlsx", "")
    try:
        week_num = int(week_str)
    except ValueError:
        continue

    df = pd.read_excel(file)
    tb_col = None
    for c in df.columns:
        cl = str(c).lower().strip()
        if 'tb' in cl or 'tie' in cl or 'total' in cl or 'points' in cl:
            tb_col = c
            break
    if tb_col is None and len(df.columns) > 0:
        valid_cols = [c for c in df.columns if not str(c).startswith('Unnamed')]
        if valid_cols:
            tb_col = valid_cols[-1]
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={week_num}"
    try:
        resp = requests.get(url)
        api_data = resp.json() if resp.status_code == 200 else {}
    except Exception:
        api_data = {}
        
    expected_games = len(api_data.get('events', []))
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
        
        s_h_str = t_home.get('score')
        s_home = int(s_h_str) if s_h_str else 0
            
        s_a_str = t_away.get('score')
        s_away = int(s_a_str) if s_a_str else 0
            
        state = comp['status']['type']['state']
        status_text = comp['status']['type'].get('shortDetail', '')
        
        if state == 'pre':
            score_str = "<span style='color:#888;font-size:0.75rem;'>@</span>"
            status_class = "status-pre"
        else:
            score_str = f"<span style='font-size:0.95rem;font-weight:900;'>{s_away} - {s_home}</span>"
            status_class = "status-in" if state == 'in' else "status-post"
            
        winner = None
        if state == 'post':
            if s_home > s_away: winner = home_abbr
            elif s_away > s_home: winner = away_abbr
            else: winner = "TIE"
            
        api_games.append({
            "date": event.get('date', ''),
            "home": home_abbr, "away": away_abbr,
            "home_logo": f"https://a.espncdn.com/i/teamlogos/nfl/500/{home_raw.lower()}.png",
            "away_logo": f"https://a.espncdn.com/i/teamlogos/nfl/500/{away_raw.lower()}.png",
            "state": state, "winner": winner, "total_score": s_home + s_away,
            "score_str": score_str, "status_text": status_text, 
            "status_class": status_class
        })
        
    mapped_teams = [c for c in df.columns if str(c).strip() in team_aliases]
    sheet_games = len(mapped_teams) // 2
    if sheet_games != expected_games and expected_games > 0:
        warnings.append(f"Week {week_num}: Excel has {sheet_games} games.")

    week_scores = []
    for index, row in df.iterrows():
        p_name = str(row.iloc[0]).strip()
        if pd.isna(p_name) or p_name.lower() in ['nan', 'tie breaker']:
            continue
        if p_name.lower().startswith('nfl week'):
            continue
            
        tb_val = row.get(tb_col, "N/A")
        if pd.notna(tb_val) and str(tb_val).strip() != '':
            try:
                tb_val = float(tb_val)
                if tb_val.is_integer(): tb_val = int(tb_val)
            except ValueError:
                tb_val = "N/A"
        else:
            tb_val = "N/A"
            
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
                "home": game['home'], "away": game['away'],
                "home_logo": game['home_logo'], "away_logo": game['away_logo'],
                "pick": pick_abbr, "logo": pick_logo, "status": status_class,
                "score_str": game['score_str'], 
                "status_text": game['status_text'],
                "game_state_class": game['status_class']
            })
                    
        week_scores.append({
            "Player": p_name, "Wins": score, "TB": tb_val, 
            "Picks": player_picks
        })
    
    week_scores = sorted(week_scores, key=lambda x: x['Wins'], reverse=True)
    last_game = sorted(api_games, key=lambda x: x['date'])[-1] if api_games else None
    actual_tb = last_game['total_score'] if last_game else 0
    all_final = all(g['state'] == 'post' for g in api_games) if api_games else False
    
    all_results[f"Week {week_num}"] = {
        "games": api_games, "scores": week_scores,
        "actual_tb": actual_tb, "all_final": all_final
    }

sorted_weeks = sorted(
    all_results.keys(), 
    key=lambda x: int(x.replace("Week ", "")), 
    reverse=True
)

dropdown_options = ""
for w in sorted_weeks:
    w_id = w.replace(" ", "-")
    dropdown_options += f"<option value='{w_id}'>{w}</option>\n"
dropdown_options += "<option value='all'>Show All Weeks</option>"

update_time_utc = time.strftime("%b %d, %I:%M %p UTC", time.gmtime())

html_parts = [
    "<!DOCTYPE html>",
    "<html><head>",
    "<title>Francis Fancy Bottoms Pickem Pool</title>",
    "<meta name='viewport' content='width=device-width, initial-scale=1'>",
    "<style>",
    "body{font-family:-apple-system,sans-serif;margin:0;padding:15px;",
    "background-color:#f0f2f6;color:#31333F;}",
    "h1{text-align:center;padding-bottom:2px;font-size:1.6rem;",
    "margin-bottom:2px;}",
    ".last-updated{text-align:center;font-size:0.72rem;color:#888;",
    "margin-bottom:15px;}",
    ".filter-container{text-align:center;margin-bottom:20px;}",
    "select#week-filter{padding:8px 16px;font-size:1rem;border-radius:8px;",
    "border:1px solid #ccc;font-weight:bold;background:#fff;outline:none;}",
    ".warning-banner{background-color:#ffbd45;color:#000;padding:15px;",
    "border-radius:8px;text-align:center;margin-bottom:20px;",
    "font-weight:bold;box-shadow:0 2px 4px rgba(0,0,0,0.1);}",
    ".warning-banner small{font-weight:normal;display:block;margin-top:5px;}",
    ".week-container{margin-bottom:30px;}",
    ".week-header-bar{display:flex;justify-content:space-between;",
    "align-items:center;padding:0 5px 10px 5px;border-bottom:2px solid #ddd;",
    "margin-bottom:15px;}",
    ".week-header-bar h2{margin:0;color:#000;font-size:1.4rem;}",
    ".expand-btn{background:#e6f4ea;color:#137333;border:1px solid #c3e6cb;",
    "padding:6px 12px;border-radius:6px;font-weight:bold;cursor:pointer;",
    "font-size:0.85rem;outline:none;}",
    ".winner-banner{background-color:#137333;color:white;padding:15px;",
    "border-radius:8px;text-align:center;margin:0 0 15px 0;",
    "box-shadow:0 2px 4px rgba(0,0,0,0.1);}",
    ".winner-banner.tie{background-color:#0d652d;}",
    ".winner-banner .title{font-size:0.85rem;font-weight:bold;",
    "letter-spacing:1px;text-transform:uppercase;margin-bottom:8px;",
    "opacity:0.9;}",
    ".winner-banner .players{font-size:1.15rem;font-weight:900;",
    "line-height:1.4;}",
    ".winner-banner .players span{font-weight:normal;font-size:0.95rem;",
    "opacity:0.9;}",
    ".winner-banner small{display:block;margin-top:8px;opacity:0.9;",
    "font-size:0.85rem;border-top:1px solid rgba(255,255,255,0.2);",
    "padding-top:8px;}",
    "details.player-card{background:#fff;border-radius:8px;",
    "margin-bottom:10px;box-shadow:0 1px 3px rgba(0,0,0,0.1);overflow:hidden;}",
    "details.player-card summary{padding:15px 20px;font-weight:bold;",
    "cursor:pointer;display:flex;justify-content:space-between;",
    "align-items:center;list-style:none;user-select:none;}",
    "details.player-card summary::-webkit-details-marker{display:none;}",
    "details.player-card summary:hover{background-color:#f8f9fa;}",
    "details.player-card[open] summary{border-bottom:1px solid #eee;",
    "background-color:#fafafa;}",
    ".picks-grid{display:grid;",
    "grid-template-columns:repeat(auto-fill, minmax(130px, 1fr));gap:10px;",
    "padding:15px;background:#fafafa;}",
    ".acc-card{display:flex;flex-direction:column;align-items:center;",
    "padding:10px;border-radius:8px;border:1px solid #ccc;",
    "text-align:center;background-color:#fff;}",
    ".acc-card .logos{display:flex;align-items:center;gap:6px;",
    "margin-bottom:2px;width:100%;justify-content:center;}",
    ".acc-card .logos img{width:26px;height:26px;object-fit:contain;}",
    ".acc-card .teams{font-size:0.75rem;color:#555;margin-bottom:2px;",
    "font-weight:bold;}",
    ".acc-card .pick-text{font-size:0.9rem;font-weight:900;padding-top:8px;",
    "border-top:1px solid rgba(0,0,0,0.1);width:100%;}",
    ".acc-card.win{background-color:#e6f4ea;border-color:#137333;}",
    ".acc-card.win .pick-text{color:#137333;}",
    ".acc-card.loss, .acc-card.missing{background-color:#fce8e6;",
    "border-color:#c5221f;}",
    ".acc-card.loss .pick-text, .acc-card.missing .pick-text{color:#c5221f;}",
    ".acc-card.pending{background-color:#fff;border-color:#dadce0;}",
    ".acc-card.pending .pick-text{color:#5f6368;}",
    ".table-view{background:#ffffff;padding:10px 0 0 0;border-radius:10px;",
    "box-shadow:0 2px 5px rgba(0,0,0,0.05);display:none;}",
    ".instruction-text{font-size:0.8rem;color:#888;padding:0 15px 10px;",
    "font-style:italic;}",
    ".horizontal-scroll-area{overflow-x:auto;white-space:nowrap;",
    "padding-bottom:15px;}",
    ".grid-row{display:flex;width:max-content;min-width:100%;",
    "border-bottom:1px solid #f0f2f6;background-color:#fff;}",
    ".grid-row:hover{background-color:#f8f9fa;}",
    ".header-row{background-color:#fafafa;border-bottom:2px solid #e0e0e0;}",
    ".locked-cols{position:sticky;left:0;z-index:2;display:flex;",
    "align-items:center;background-color:inherit;",
    "border-right:2px solid #e0e0e0;}",
    ".col-name{width:95px;padding:12px 8px;font-weight:bold;",
    "font-size:0.95rem;white-space:nowrap;overflow:hidden;",
    "text-overflow:ellipsis;}",
    ".col-wins{width:40px;padding:12px 4px;font-weight:900;",
    "font-size:1.05rem;text-align:center;}",
    ".col-tb{width:45px;padding:12px 4px;font-weight:bold;",
    "font-size:0.95rem;text-align:center;color:#666;}",
    ".header-row .col-name, .header-row .col-wins, .header-row .col-tb{",
    "font-size:0.75rem;color:#555;text-transform:uppercase;",
    "font-weight:normal;}",
    ".scroll-cols{display:flex;align-items:center;}",
    ".game-cell{width:110px;padding:8px 4px;display:flex;",
    "flex-direction:column;align-items:center;justify-content:center;}",
    ".matchup-logos{display:flex;justify-content:center;align-items:center;",
    "gap:4px;margin-bottom:2px;}",
    ".matchup-logos img{width:24px;height:24px;object-fit:contain;}",
    ".matchup-text{color:#555;font-size:0.75rem;font-weight:bold;}",
    ".pick-box{display:flex;align-items:center;justify-content:center;",
    "gap:6px;font-size:0.85rem;font-weight:80
    
