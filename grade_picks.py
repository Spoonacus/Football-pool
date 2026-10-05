import pandas as pd
import json
import glob
import os
import requests
import re

TEAM_MAP = {
    "commanskins": "commanders",
    "bucs": "buccaneers",
    "niners": "49ers"
}

def normalize_name(name):
    name = str(name).lower().strip()
    return TEAM_MAP.get(name, name)

def get_espn_winners(week_num, cache={}):
    if week_num in cache:
        return cache[week_num]
        
    url = f"http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={week_num}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        winners = []
        for event in data.get('events', []):
            for comp in event.get('competitions', [{}])[0].get('competitors', []):
                if comp.get('winner') is True:
                    team = comp.get('team', {})
                    if team.get('name'): winners.append(team.get('name').lower())
                    if team.get('nickname'): winners.append(team.get('nickname').lower())
                    if team.get('displayName'): winners.append(team.get('displayName').lower())
        cache[week_num] = winners
        return winners
    except Exception as e:
        print(f"Error fetching ESPN data for week {week_num}: {e}")
        return []

def parse_single_file(file_path):
    try:
        df = pd.read_excel(file_path, sheet_name=0, header=None)
    except Exception as e:
        print(f"Could not read {file_path}: {e}")
        return None

    # Determine week number from cell A2 or filename
    week_title = str(df.iloc[1, 0]).strip()
    match = re.search(r'\d+', week_title)
    if not match:
        match = re.search(r'\d+', os.path.basename(file_path))
        
    week_num = int(match.group()) if match else 1
    display_title = f"NFL Week {week_num}"

    winners = get_espn_winners(week_num)
    team_row = df.iloc[0]
    
    # Locate tie breaker column
    tb_col = df.shape[1] - 1
    for col_idx in range(df.shape[1]):
        val = str(team_row[col_idx]).lower()
        if "tie" in val or "tb" in val:
            tb_col = col_idx
            break

    players = []
    for _, row in df.iloc[2:].iterrows():
        name = row[0]
        if pd.isna(name):
            continue

        correct_picks = 0
        player_picks = []

        for col in range(1, tb_col):
            if not pd.isna(row[col]):
                picked_team = str(team_row[col]).strip()
                if pd.isna(team_row[col]) or not picked_team or picked_team == "nan":
                    continue

                norm_team = normalize_name(picked_team)
                is_correct = any(norm_team in w for w in winners) or any(w in norm_team for w in winners)

                if is_correct:
                    correct_picks += 1

                player_picks.append({
                    "team": picked_team,
                    "correct": is_correct
                })

        tie_breaker = row[tb_col] if not pd.isna(row[tb_col]) else 0
        try:
            tie_breaker = int(float(tie_breaker))
        except (ValueError, TypeError):
            pass

        players.append({
            "rank": 0,
            "name": str(name).strip(),
            "score": correct_picks,
            "tie_breaker": tie_breaker,
            "picks": player_picks
        })

    players.sort(key=lambda x: x['score'], reverse=True)
    for i, player in enumerate(players):
        player['rank'] = i + 1

    return week_num, {
        "title": display_title,
        "week_num": week_num,
        "standings": players
    }

def process_picks():
    excel_files = glob.glob('*.xlsx') + glob.glob('*.xls')
    if not excel_files:
        print("No Excel files found.")
        return

    weeks_data = {}
    for f in excel_files:
        result = parse_single_file(f)
        if result:
            week_num, data = result
            weeks_data[str(week_num)] = data

    if not weeks_data:
        print("No valid week data could be parsed.")
        return

    latest_week = max([int(k) for k in weeks_data.keys()])

    output = {
        "latest_week": str(latest_week),
        "weeks": weeks_data
    }

    with open('standings.json', 'w') as f:
        json.dump(output, f, indent=4)
    print("standings.json successfully generated with all weeks.")

if __name__ == "__main__":
    process_picks()
    
