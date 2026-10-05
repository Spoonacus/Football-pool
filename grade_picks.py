import pandas as pd
import json
import glob
import os
import requests
import re

# Translation dictionary to map your custom spreadsheet names to ESPN's official names
TEAM_MAP = {
    "commanskins": "commanders",
    "bucs": "buccaneers",
    "niners": "49ers"
}

def normalize_name(name):
    """Converts a team name to lowercase and swaps out custom names."""
    name = str(name).lower().strip()
    return TEAM_MAP.get(name, name)

def get_espn_winners(week_num):
    """Fetches the actual winning teams for a specific week from the ESPN API."""
    # Using seasontype=2 for Regular Season
    url = f"http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={week_num}"
    response = requests.get(url)
    data = response.json()
    
    winners = []
    for event in data.get('events', []):
        for comp in event['competitions'][0]['competitors']:
            # If the team won the game, add them to our answer key
            if comp.get('winner') == True:
                # Add a few variations of their name just to be safe
                winners.append(comp['team']['name'].lower())
                winners.append(comp['team']['nickname'].lower())
                winners.append(comp['team'].get('displayName', '').lower())
    return winners

def process_picks():
    # 1. Find the newest Excel file in the repository
    excel_files = glob.glob('*.xlsx') + glob.glob('*.xls')
    if not excel_files:
        print("No Excel file found.")
        return
    
    latest_file = max(excel_files, key=os.path.getctime)
    print(f"Processing file: {latest_file}")
    
    # 2. Read the spreadsheet
    try:
        # Try to read the exact sheet name you use
        df = pd.read_excel(latest_file, sheet_name='Week (3)', header=None)
    except:
        # If the sheet name changes, just grab the first sheet available
        df = pd.read_excel(latest_file, header=None)

    # 3. Figure out which NFL week this is by reading Cell A2 (Row 1, Col 0)
    week_title = str(df.iloc[1, 0]).strip()
    if pd.isna(df.iloc[1, 0]) or week_title == 'nan':
        week_title = "NFL Week"
        
    # Extract the number from "NFL Week 3" so we know what to ask ESPN for
    match = re.search(r'\d+', week_title)
    week_num = int(match.group()) if match else 1
    
    # 4. Get the answer key from ESPN
    winners = get_espn_winners(week_num)
    print("ESPN Winners this week:", set(winners))

    # 5. Parse and Grade the players
    players = []
    team_row = df.iloc[0] # Row 0 holds the names of the teams playing
    
    # Player data starts on Row 2
    for index, row in df.iloc[2:].iterrows():
        name = row[0]
        if pd.isna(name):
            continue
            
        correct_picks = 0
        
        # Check every column from 1 to 47 for picks
        for col in range(1, 48):
            if not pd.isna(row[col]): # If the cell isn't empty, they picked this team
                picked_team = team_row[col]
                if pd.isna(picked_team):
                    continue
                    
                norm_team = normalize_name(picked_team)
                
                # Check if the team they picked is in the ESPN winners list
                if any(norm_team in w for w in winners) or any(w in norm_team for w in winners):
                    correct_picks += 1
                
        tie_breaker = row[48] if not pd.isna(row[48]) else 0
        
        players.append({
            "rank": 0,
            "name": str(name).strip(),
            "score": correct_picks,
            "tie_breaker": tie_breaker
        })

    # 6. Sort players by most correct picks
    players.sort(key=lambda x: x['score'], reverse=True)
    
    # 7. Assign final ranks
    for i, player in enumerate(players):
        player['rank'] = i + 1

    # 8. Save the data to JSON
    output_data = {
        "week": week_title,
        "standings": players
    }
    
    with open('standings.json', 'w') as f:
        json.dump(output_data, f, indent=4)
        
    print("Successfully generated standings.json")

if __name__ == "__main__":
    process_picks()
    
