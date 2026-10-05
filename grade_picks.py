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

def get_espn_winners(week_num):
    url = f"http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={week_num}"
    response = requests.get(url)
    data = response.json()
    
    winners = []
    for event in data.get('events', []):
        for comp in event['competitions'][0]['competitors']:
            if comp.get('winner') == True:
                winners.append(comp['team']['name'].lower())
                winners.append(comp['team']['nickname'].lower())
                winners.append(comp['team'].get('displayName', '').lower())
    return winners

def process_picks():
    excel_files = glob.glob('*.xlsx') + glob.glob('*.xls')
    if not excel_files:
        print("No Excel file found.")
        return
    
    latest_file = max(excel_files, key=os.path.getctime)
    
    try:
        df = pd.read_excel(latest_file, sheet_name='Week (3)', header=None)
    except:
        df = pd.read_excel(latest_file, header=None)

    # Find the week number in Cell A2
    week_title = str(df.iloc[1, 0]).strip()
    match = re.search(r'\d+', week_title)
    
    # Fallback: check the filename for a number if A2 is blank
    if not match:
        match = re.search(r'\d+', latest_file)
        
    if match:
        week_num = int(match.group())
        week_title = f"NFL Week {week_num}"
    else:
        # Default to Week 1 if no number is found anywhere
        week_num = 1
        week_title = "NFL Week 1"
        
    winners = get_espn_winners(week_num)

    players = []
    team_row = df.iloc[0] 
    
    # Dynamically find the last column instead of hardcoding it
    max_col = df.shape[1] - 1
    
    for index, row in df.iloc[2:].iterrows():
        name = row[0]
        if pd.isna(name):
            continue
            
        correct_picks = 0
        
        # Check from the first game up to the Tie Breaker column
        for col in range(1, max_col):
            if not pd.isna(row[col]): 
                picked_team = team_row[col]
                if pd.isna(picked_team):
                    continue
                    
                norm_team = normalize_name(picked_team)
                
                if any(norm_team in w for w in winners) or any(w in norm_team for w in winners):
                    correct_picks += 1
                
        # Assume the very last column is the tie breaker
        tie_breaker = row[max_col] if not pd.isna(row[max_col]) else 0
        
        players.append({
            "rank": 0,
            "name": str(name).strip(),
            "score": correct_picks,
            "tie_breaker": tie_breaker
        })

    players.sort(key=lambda x: x['score'], reverse=True)
    
    for i, player in enumerate(players):
        player['rank'] = i + 1

    output_data = {
        "week": week_title,
        "standings": players
    }
    
    with open('standings.json', 'w') as f:
        json.dump(output_data, f, indent=4)
        
if __name__ == "__main__":
    process_picks()
    
