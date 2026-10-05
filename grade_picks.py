import pandas as pd
import json
import glob
import os

def process_picks():
    # 1. Find the newest Excel file in the repository
    excel_files = glob.glob('*.xlsx')
    if not excel_files:
        print("No Excel file found.")
        return
    
    # Sort by modified time to get the latest upload
    latest_file = max(excel_files, key=os.path.getctime)
    print(f"Processing file: {latest_file}")
    
    # 2. Read the specific "Week (3)" sheet or the first sheet available
    try:
        df = pd.read_excel(latest_file, sheet_name='Week (3)', header=None)
    except:
        df = pd.read_excel(latest_file, header=None) # Fallback to first sheet

    # 3. Parse the players and their picks
    # Your names start on Row 2 (index 2). 
    players = []
    
    for index, row in df.iloc[2:].iterrows():
        name = row[0]
        if pd.isna(name):
            continue
            
        # In a real scenario, we would compare these against an ESPN API.
        # For the proof-of-concept pipeline, we will count how many games they picked
        # by counting the non-empty cells (where they put 'x', 'X', 'S', etc.)
        # Games are in columns 1 through 47. Tie-breaker is column 48.
        picks_made = 0
        for col in range(1, 48):
            if not pd.isna(row[col]):
                picks_made += 1
                
        tie_breaker = row[48] if not pd.isna(row[48]) else 0
        
        players.append({
            "rank": 0, # We will calculate this next
            "name": str(name).strip(),
            "score": picks_made, # This will eventually be "correct picks"
            "tie_breaker": tie_breaker
        })

    # 4. Sort the players by score (highest first)
    players.sort(key=lambda x: x['score'], reverse=True)
    
    # 5. Assign Ranks
    for i, player in enumerate(players):
        player['rank'] = i + 1

    # 6. Save the data for the website to read
    output_data = {
        "week": latest_file.split('.')[0],
        "standings": players
    }
    
    with open('standings.json', 'w') as f:
        json.dump(output_data, f, indent=4)
        
    print("Successfully generated standings.json")

if __name__ == "__main__":
    process_picks()
  
