import streamlit as st
import pandas as pd
import requests
import datetime
import os
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Ghost Bowl ATS", page_icon="👻", layout="centered", initial_sidebar_state="collapsed")

# --- CUSTOM UI CSS ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Hides the Streamlit Community Cloud floating viewer badges and developer buttons */
    .stAppDeployButton {display: none !important;}
    [data-testid="viewerBadge"] {display: none !important;}
    [data-testid="stStatusWidget"] {display: none !important;}
    [data-testid="manage-app-button"] {display: none !important;}
    div[class^="viewerBadge"] {display: none !important;}
    
    .block-container {padding-top: 0.5rem !important; padding-bottom: 1rem !important; padding-left: 0.5rem !important; padding-right: 0.5rem !important;}
    </style>
""", unsafe_allow_html=True)

def parse_spread(odds_str, team_abbr):
    if not odds_str or odds_str.upper() in ["EVEN", "PK"]:
        return 0.0
    parts = odds_str.split(" ")
    if len(parts) >= 2:
        favored_team = parts[0]
        try:
            spread_val = float(parts[1])
        except ValueError:
            return 0.0
        if favored_team == team_abbr:
            return spread_val
        else:
            return abs(spread_val) 
    return 0.0

@st.dialog("🏆 Weekly Winner Finalized!")
def flash_celebration(winner, week_num):
    st.balloons()
    if winner == "49ers":
        st.markdown(f"<h3 style='text-align: center; margin-bottom: 10px;'>⛏️ 49ers Win Week {week_num}!</h3>", unsafe_allow_html=True)
        if os.path.exists("1791158028631.jpg"):
            st.image("1791158028631.jpg", use_container_width=True)
    elif winner == "Raiders":
        st.markdown(f"<h3 style='text-align: center; margin-bottom: 10px;'>🏴‍☠️ Raiders Win Week {week_num}!</h3>", unsafe_allow_html=True)
        if os.path.exists("1791158149259.jpg"):
            st.image("1791158149259.jpg", use_container_width=True)
    else:
        st.markdown(f"<h3 style='text-align: center;'>⚖️ Week {week_num} Ended in a Tie!</h3>", unsafe_allow_html=True)

@st.cache_data(ttl=60)
def fetch_current_week():
    url = "http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    resp = requests.get(url)
    if resp.status_code != 200: 
        return None, None, 0
    data = resp.json()
    
    current_week_num = data.get('week', {}).get('number', 0)
    sf_data, lv_data = None, None
    
    for event in data.get('events', []):
        comp = event['competitions'][0]
        teams = comp['competitors']
        team_abbrs = [t['team']['abbreviation'] for t in teams]
        
        if 'SF' in team_abbrs or 'LV' in team_abbrs:
            state = comp['status']['type']['state']
            status_text = event['status']['type']['shortDetail']
            odds_str = comp.get('odds', [{}])[0].get('details', '') if comp.get('odds') else ''
            
            if not odds_str and state == 'post':
                game_id = event['id']
                summary_url = f"http://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}"
                try:
                    sum_resp = requests.get(summary_url)
                    if sum_resp.status_code == 200:
                        pickcenter = sum_resp.json().get('pickcenter', [])
                        if pickcenter:
                            odds_str = pickcenter[0].get('details', '')
                except:
                    pass 
                    
            if 'SF' in team_abbrs:
                my_team = next(t for t in teams if t['team']['abbreviation'] == 'SF')
                opp_team = next(t for t in teams if t['team']['abbreviation'] != 'SF')
                try: my_score = int(my_team.get('score', 0))
                except: my_score = 0
                try: opp_score = int(opp_team.get('score', 0))
                except: opp_score = 0
                
                spread_val = parse_spread(odds_str, 'SF')
                live_ats = (my_score - opp_score) + spread_val if state != 'pre' else None
                
                sf_data = {
                    'opp': opp_team['team']['abbreviation'], 'is_home': my_team['homeAway'] == 'home',
                    'state': state, 'status_text': status_text,
                    'my_score': my_score, 'opp_score': opp_score,
                    'spread': spread_val, 'live_ats': live_ats
                }
            
            if 'LV' in team_abbrs:
                my_team = next(t for t in teams if t['team']['abbreviation'] == 'LV')
                opp_team = next(t for t in teams if t['team']['abbreviation'] != 'LV')
                try: my_score = int(my_team.get('score', 0))
                except: my_score = 0
                try: opp_score = int(opp_team.get('score', 0))
                except: opp_score = 0
                
                spread_val = parse_spread(odds_str, 'LV')
                live_ats = (my_score - opp_score) + spread_val if state != 'pre' else None
                
                lv_data = {
                    'opp': opp_team['team']['abbreviation'], 'is_home': my_team['homeAway'] == 'home',
                    'state': state, 'status_text': status_text,
                    'my_score': my_score, 'opp_score': opp_score,
                    'spread': spread_val, 'live_ats': live_ats
                }
                
    return sf_data, lv_data, current_week_num

@st.cache_data(ttl=300)
def fetch_season_data():
    results = []
    now = datetime.datetime.now()
    year = now.year if now.month > 2 else now.year - 1
    
    for week in range(1, 19):
        url = f"http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={year}&week={week}&seasontype=2"
        resp = requests.get(url)
        if resp.status_code != 200: 
            continue
            
        data = resp.json()
        sf_data, lv_data = None, None
        
        for event in data.get('events', []):
            comp = event['competitions'][0]
            if comp['status']['type']['state'] != 'post': 
                continue
                
            teams = comp['competitors']
            team_abbrs = [t['team']['abbreviation'] for t in teams]
            
            if 'SF' in team_abbrs or 'LV' in team_abbrs:
                odds_str = comp.get('odds', [{}])[0].get('details', '') if comp.get('odds') else ''
                
                if not odds_str:
                    game_id = event['id']
                    summary_url = f"http://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}"
                    try:
                        sum_resp = requests.get(summary_url)
                        if sum_resp.status_code == 200:
                            pickcenter = sum_resp.json().get('pickcenter', [])
                            if pickcenter:
                                odds_str = pickcenter[0].get('details', '')
                    except:
                        pass 
                        
                if 'SF' in team_abbrs:
                    sf_team = next(t for t in teams if t['team']['abbreviation'] == 'SF')
                    opp_team = next(t for t in teams if t['team']['abbreviation'] != 'SF')
                    sf_data = {'score': int(sf_team['score']), 'opp_score': int(opp_team['score']), 'spread': parse_spread(odds_str, 'SF')}
                
                if 'LV' in team_abbrs:
                    lv_team = next(t for t in teams if t['team']['abbreviation'] == 'LV')
                    opp_team = next(t for t in teams if t['team']['abbreviation'] != 'LV')
                    lv_data = {'score': int(lv_team['score']), 'opp_score': int(opp_team['score']), 'spread': parse_spread(odds_str, 'LV')}
        
        if sf_data and lv_data:
            sf_ats = (sf_data['score'] - sf_data['opp_score']) + sf_data['spread']
            lv_ats = (lv_data['score'] - lv_data['opp_score']) + lv_data['spread']
            
            if sf_ats > lv_ats: winner = "49ers"
            elif lv_ats > sf_ats: winner = "Raiders"
            else: winner = "Tie"
            
            results.append({
                "Week": week,
                "49ers Spread": sf_data['spread'], "49ers ATS Margin": sf_ats,
                "Raiders Spread": lv_data['spread'], "Raiders ATS Margin": lv_ats,
                "Winner": winner
            })
            
    return pd.DataFrame(results)

def is_celebration_active(latest_completed_week, current_week_num, sf_live, lv_live):
    try:
        now_pt = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
    except Exception:
        now_pt = datetime.datetime.utcnow() - datetime.timedelta(hours=7)
        
    weekday = now_pt.weekday()
    if weekday in [4, 5]: return False
    if weekday == 3:
        if now_pt.hour > 17 or (now_pt.hour == 17 and now_pt.minute >= 15): return False
        if latest_completed_week not in [current_week_num, current_week_num - 1]: return False
        return True
    if weekday in [1, 2]:
        if latest_completed_week not in [current_week_num, current_week_num - 1]: return False
        return True
    if weekday in [0, 6]:
        if not sf_live or not lv_live: return False
        if sf_live.get('state') != 'post' or lv_live.get('state') != 'post': return False
        if latest_completed_week != current_week_num: return False
        return True
    return False

def build_live_card_html(team, bg_color, text_color, data, is_winning=False):
    if not data:
        return f"""<div style='background-color: {bg_color}; color: {text_color}; padding: 8px; border-radius: 8px; width: 49%; text-align: center; box-shadow: 1px 1px 4px rgba(0,0,0,0.2); border: 1px solid #444;'>
<div style='font-size: 0.85rem; font-weight: bold;'>{team}</div><div style='font-size: 1.1rem; padding: 10px 0;'>BYE WEEK</div></div>"""
    opp_prefix = "vs" if data['is_home'] else "@"
    spread_val = data['spread']
    spread_str = f"{spread_val:+.1f}" if spread_val != 0 else "PK"
    winning_banner = "<div style='background-color: #28a745; color: white; font-weight: 800; font-size: 0.72rem; padding: 3px 0; border-radius: 4px; margin-bottom: 6px; letter-spacing: 0.5px;'>🏆 WINNING</div>" if is_winning else "<div style='height: 22px; margin-bottom: 6px;'></div>"

    if data['state'] == 'pre':
        score_line = f"<div style='font-size: 0.95rem; font-weight: bold; margin: 8px 0;'>{data['status_text']}</div>"
        ats_line = "<div style='font-size: 0.75rem; color: #ccc; margin-top: 4px;'>ATS: Pre-Game</div>"
    else:
        ats_val = data['live_ats']
        ats_str = f"{ats_val:+.1f}" if ats_val is not None else "0.0"
        score_line = f"""<div style='font-size: 1.3rem; font-weight: 900; margin: 1px 0;'>{data['my_score']} - {data['opp_score']}</div><div style='font-size: 0.72rem; opacity: 0.9;'>{data['status_text']}</div>"""
        ats_line = f"""<div style='font-size: 0.82rem; font-weight: bold; margin-top: 5px; background-color: rgba(255,255,255,0.22); border-radius: 4px; padding: 2px 4px;'>ATS Margin: {ats_str}</div>"""
    return f"""<div style='background-color: {bg_color}; color: {text_color}; padding: 8px; border-radius: 8px; width: 49%; text-align: center; box-shadow: 1px 1px 4px rgba(0,0,0,0.2); border: 1px solid #444;'>
{winning_banner}<div style='font-size: 0.75rem; font-weight: bold; letter-spacing: 0.5px;'>{team} {opp_prefix} {data['opp']}</div>
{score_line}<div style='font-size: 0.72rem; margin-top: 4px; opacity: 0.85;'>Spread: {spread_str}</div>{ats_line}</div>"""


# --------------------------------------------------------------------------------
# GHOST BOWL TRACKER
# --------------------------------------------------------------------------------

if os.path.exists("1791152594772.jpg"):
    st.image("1791152594772.jpg", use_container_width=True)
elif os.path.exists("banner.jpg"):
    st.image("banner.jpg", use_container_width=True)
else:
    st.markdown("<h2 style='text-align: center;'>👻 Bay Bridge Ghost Bowl</h2>", unsafe_allow_html=True)

with st.spinner("Connecting to ESPN Live API..."):
    sf_live, lv_live, current_week_num = fetch_current_week()
    df = fetch_season_data()

sf_winning = False
lv_winning = False

if sf_live and lv_live:
    sf_ats, lv_ats = sf_live.get('live_ats'), lv_live.get('live_ats')
    if sf_ats is not None and lv_ats is not None:
        if sf_ats > lv_ats: sf_winning = True
        elif lv_ats > sf_ats: lv_winning = True
    elif sf_ats is not None and lv_ats is None and sf_ats > 0: sf_winning = True
    elif lv_ats is not None and sf_ats is None and lv_ats > 0: lv_winning = True

live_html = f"""<div style='display: flex; justify-content: space-between; gap: 6px; margin-top: 5px; margin-bottom: 15px;'>
{build_live_card_html("49ERS", "#AA0000", "#FFFFFF", sf_live, is_winning=sf_winning)}
{build_live_card_html("RAIDERS", "#000000", "#A5ACAF", lv_live, is_winning=lv_winning)}
</div>"""
st.markdown(live_html, unsafe_allow_html=True)

if not df.empty:
    latest_week = df.iloc[-1]
    if is_celebration_active(latest_week['Week'], current_week_num, sf_live, lv_live):
        if "celebration_shown" not in st.session_state:
            st.session_state.celebration_shown = True
            flash_celebration(latest_week['Winner'], latest_week['Week'])

    sf_wins = len(df[df["Winner"] == "49ers"])
    lv_wins = len(df[df["Winner"] == "Raiders"])
    ties = len(df[df["Winner"] == "Tie"])
    
    scoreboard_html = f"""<div style='display: flex; justify-content: space-between; gap: 8px; margin-top: 10px; margin-bottom: 12px;'>
<div style='background-color: #AA0000; color: #B3995D; padding: 8px; border-radius: 8px; width: 32%; text-align: center; box-shadow: 1px 1px 4px rgba(0,0,0,0.2);'><div style='font-size: 0.75rem; font-weight: bold; color: white;'>SF WINS</div><div style='font-size: 1.8rem; font-weight: 900;'>{sf_wins}</div></div>
<div style='background-color: #f0f2f6; color: black; padding: 8px; border-radius: 8px; width: 32%; text-align: center; box-shadow: 1px 1px 4px rgba(0,0,0,0.2);'><div style='font-size: 0.75rem; font-weight: bold; color: #555;'>TIES</div><div style='font-size: 1.8rem; font-weight: 900;'>{ties}</div></div>
<div style='background-color: #000000; color: #A5ACAF; padding: 8px; border-radius: 8px; width: 32%; text-align: center; box-shadow: 1px 1px 4px rgba(0,0,0,0.2);'><div style='font-size: 0.75rem; font-weight: bold; color: white;'>LV WINS</div><div style='font-size: 1.8rem; font-weight: 900;'>{lv_wins}</div></div></div>"""
    st.markdown(scoreboard_html, unsafe_allow_html=True)

    table_rows = ""
    for index, row in df.iterrows():
        sf_class = "win-sf" if row['Winner'] == '49ers' else ""
        lv_class = "win-lv" if row['Winner'] == 'Raiders' else ""
        win_badge = "🔴 SF" if row['Winner'] == '49ers' else "⚫ LV" if row['Winner'] == 'Raiders' else "Tie"
        table_rows += f"<tr><td style='font-weight: bold;'>{row['Week']}</td><td class='{sf_class}'>{row['49ers Spread']:+.1f}</td><td class='{sf_class}'>{row['49ers ATS Margin']:+.1f}</td><td class='{lv_class}'>{row['Raiders Spread']:+.1f}</td><td class='{lv_class}'>{row['Raiders ATS Margin']:+.1f}</td><td style='font-size: 0.75rem; font-weight: bold;'>{win_badge}</td></tr>"

    table_html = f"""<style>.ghost-table {{ width: 100%; border-collapse: collapse; text-align: center; font-size: 0.85rem; font-family: sans-serif; margin-top: 10px; }} .ghost-table th, .ghost-table td {{ padding: 6px 3px; border: 1px solid #ddd; }} .sf-head {{ background-color: #AA0000; color: #B3995D; font-weight: bold; border: 1px solid #770000 !important; }} .lv-head {{ background-color: #000000; color: #A5ACAF; font-weight: bold; border: 1px solid #333 !important; }} .sub-head {{ background-color: #f8f9fa; font-size: 0.7rem; color: #555; }} .win-sf {{ background-color: #fff0f0; font-weight: bold; color: #AA0000; }} .win-lv {{ background-color: #f0f0f0; font-weight: bold; color: black; }}</style><table class='ghost-table'><thead><tr><th rowspan="2" style="background-color: #f8f9fa;">Wk</th><th colspan="2" class="sf-head">49ERS</th><th colspan="2" class="lv-head">RAIDERS</th><th rowspan="2" style="background-color: #f8f9fa;">Win</th></tr><tr class="sub-head"><th>Spread</th><th>ATS</th><th>Spread</th><th>ATS</th></tr></thead><tbody>{table_rows}</tbody></table>"""
    st.markdown(table_html, unsafe_allow_html=True)
else:
    st.info("No completed head-to-head weeks found yet for this season.")

# --------------------------------------------------------------------------------
# OFFICE PICK'EM GRADER (NEW)
# --------------------------------------------------------------------------------

st.markdown("<br><hr>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center;'>📝 Office Pick'em Grader</h3>", unsafe_allow_html=True)

col1, col2 = st.columns([1, 2])
with col1:
    grade_week = st.number_input("Week to Grade", min_value=1, max_value=18, value=current_week_num)
with col2:
    uploaded_file = st.file_uploader("Upload Excel Sheet", type=["xlsx", "xls"])

if uploaded_file:
    # 1. The "Olds" Dictionary
    team_aliases = {
        # Standard Names
        "49ers": "SF", "Bears": "CHI", "Bengals": "CIN", "Bills": "BUF",
        "Broncos": "DEN", "Browns": "CLE", "Bucs": "TB", "Cardinals": "ARI", 
        "Chargers": "LAC", "Chiefs": "KC", "Colts": "IND", "Commanders": "WAS", 
        "Cowboys": "DAL", "Dolphins": "MIA", "Eagles": "PHI", "Falcons": "ATL",
        "Giants": "NYG", "Jaguars": "JAX", "Jets": "NYJ", "Lions": "DET",
        "Packers": "GB", "Panthers": "CAR", "Patriots": "NE", "Raiders": "LV",
        "Rams": "LAR", "Ravens": "BAL", "Saints": "NO", "Seahawks": "SEA",
        "Steelers": "PIT", "Texans": "HOU", "Titans": "TEN", "Vikings": "MIN",
        
        # Typos / Aliases
        "Boncos": "DEN",
        "Commancers": "WAS",
        "Commanskins": "WAS",
        "Sehawks": "SEA"
    }

    df_picks = pd.read_excel(uploaded_file)
    
    # Fetch API data for the selected week
    with st.spinner("Fetching official game results..."):
        api_url = f"http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={grade_week}"
        api_resp = requests.get(api_url)
        api_data = api_resp.json() if api_resp.status_code == 200 else {}
    
    expected_games = len(api_data.get('events', []))
    
    # Identify which columns are actual teams using the Olds Dictionary
    mapped_teams = [c for c in df_picks.columns if str(c).strip() in team_aliases]
    sheet_games = len(mapped_teams) // 2
    
    # The Warning Banner Fix
    if sheet_games != expected_games and expected_games > 0:
        st.warning(f"⚠️ **Update the Olds Dictionary!** The Excel sheet headers parsed {sheet_games} games, but ESPN shows {expected_games} scheduled for Week {grade_week}.")

    # Figure out the winners based on live/final ESPN scores
    api_winners = []
    for event in api_data.get('events', []):
        comp = event['competitions'][0]
        teams = comp['competitors']
        t1, t2 = teams[0], teams[1]
        
        try: s1 = int(t1.get('score', 0))
        except: s1 = 0
        try: s2 = int(t2.get('score', 0))
        except: s2 = 0
            
        if s1 > s2: api_winners.append(t1['team']['abbreviation'])
        elif s2 > s1: api_winners.append(t2['team']['abbreviation'])

    # Score the participants
    leaderboard = []
    for index, row in df_picks.iterrows():
        player_name = str(row.iloc[0]).strip()
        
        # Ignore empty rows, totals, or header repetitions
        if pd.isna(player_name) or player_name == 'nan' or player_name.lower().startswith('nfl week') or player_name == 'Tie Breaker':
            continue
            
        score = 0
        for col in mapped_teams:
            team_abbr = team_aliases[str(col).strip()]
            
