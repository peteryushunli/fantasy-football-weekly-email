import requests
import pandas as pd
import time 
from datetime import datetime
from timeout_decorator import timeout


########################################################################
#########################Sleeper Section################################
########################################################################

#Pip install sleeper-api-wrapper if you don't have it already
from sleeper_wrapper import League
from sleeper_wrapper import Players
from sleeper_wrapper import Stats

import json
# Load the configuration from config.json
with open('config.json') as config_file:
    config_data = json.load(config_file)

def get_NFL_week():
    #Get the current date
    today = datetime.today()
    #Set the NFL kickoff date
    kickoff = datetime(2023, 9, 7)
    #Calculate the number of days between today and kickoff
    days_since_kickoff = (today - kickoff).days
    #Calculate the number of weeks since kickoff
    weeks_since_kickoff = days_since_kickoff // 7
    
    #Return the current week in the NFL season
    return weeks_since_kickoff + 1

def owners(league):
    #Setup users_df
    users_df = pd.DataFrame(league.get_users())
    owners = config_data['sleeper']['owner_list']
    users_df['owner'] = owners

    #For loop through each row of the dataframe and extract the 'team_name' from the 'metadata' column
    team_names = []
    for index, row in users_df.iterrows():
        # Use get() method to safely access 'team_name' with a default value of 'None'
        team_name = row['metadata'].get('team_name', row['display_name'])
        team_names.append(team_name)

    #Add the 'team_name' column to the dataframe
    users_df['team_name'] = team_names
    owners_df = users_df[['owner', 'display_name','user_id', 'team_name']]
    return owners_df.rename(columns={'user_id': 'owner_id'})

def player_info(players):
    #Get all player information
    players_df = pd.DataFrame(players.get_all_players()).transpose()
    players_df = players_df.loc[(players_df['player_id'] != None) & (players_df['active'] == True)]
    players_df = players_df[['player_id', 'full_name', 'position', 'active', 'team']]
    players_df = players_df.reset_index(drop=True)
    #convert the columns 'player_id' and 'full_name' to a dictionary
    return players_df.set_index('player_id')['full_name'].to_dict()

def weekly_matchup(week, rosters_df, player_dict, league):
    matchups = league.get_matchups(week = week)
    matchups_df = pd.DataFrame(matchups)
    matchups_df = rosters_df[['roster_id', 'owner']].merge(matchups_df, on = 'roster_id').drop(columns = ['custom_points', 'players', 'players_points'])
    starters = matchups_df.starters.apply(pd.Series)
    starters.columns = ['QB', 'RB1', 'RB2', 'WR1', 'WR2', 'TE', 'SF','FLEX', 'K', 'DEF']
    #Get the starter points for each player
    starter_points = matchups_df.starters_points.apply(pd.Series)
    #Set starter_points column names as starter column names with _points appended
    starter_points.columns = [x + '_PTS' for x in starters.columns]
    matchups_df = pd.concat([matchups_df, starters, starter_points], axis = 1).drop(columns = ['roster_id', 'starters', 'starters_points'],axis = 1)

    #Replace player_id with player name
    columns_to_replace = ['QB', 'RB1', 'RB2', 'WR1', 'WR2', 'TE', 'SF', 'K']
    for column in columns_to_replace:
        matchups_df[column] = matchups_df[column].map(player_dict)

    matchups_df = matchups_df[['owner', 'matchup_id', 'points', 'QB', 'QB_PTS', 'RB1', 'RB1_PTS', 'RB2', 'RB2_PTS', 'WR1', 'WR1_PTS', 'WR2', 'WR2_PTS', 'TE', 'TE_PTS', 'SF', 'SF_PTS', 'FLEX', 'FLEX_PTS', 'K', 'K_PTS', 'DEF', 'DEF_PTS']]
    matchups_df.sort_values(by = 'matchup_id', inplace = True)
    #Rename the column 'points' to 'total_team_points'
    matchups_df.rename(columns={'points': 'total_team_points'}, inplace=True)
    return matchups_df

def highest_scoring_player_sleeper(matchup_df):
    df = matchup_df.copy()
    # List of columns to keep
    columns_to_keep = ['owner']

    # Create an empty list to store data
    transformed_data = []

    # Iterate through each row in the original DataFrame
    for _, row in df.iterrows():
        owner = row['owner']
        matchup_id = row['matchup_id']
        points = row['total_team_points']

        # Iterate through player columns (QB, RB1, RB2, etc.)
        for column in ['QB', 'RB1', 'RB2', 'WR1', 'WR2', 'TE', 'SF', 'FLEX', 'K', 'DEF']:
            player = row[column]
            player_points_col = f"{column}_PTS"
            player_points = row[player_points_col]

            # Append player data to the list
            transformed_data.append([owner, player, player_points])

    # Create a new DataFrame from the transformed data
    transformed_df = pd.DataFrame(transformed_data, columns=['owner', 'player', 'player_points'])

    #Identify the highest scoring player, their owner, and the points scored
    highest_scoring_player = transformed_df.loc[transformed_df['player_points'].idxmax()]
    highest_scoring_player_owner = highest_scoring_player['owner']
    highest_scoring_player_name = highest_scoring_player['player']
    highest_scoring_player_points = highest_scoring_player['player_points']
    return highest_scoring_player_owner, highest_scoring_player_name, highest_scoring_player_points

def highest_scoring_team_sleeper(matchups_df):
    #Find the owner with the highest score
    max_points_index = matchups_df['total_team_points'].idxmax()
    #Use the index to get the owner with the highest points
    owner_with_highest_points = matchups_df.loc[max_points_index, 'owner']
    highest_points = matchups_df.loc[max_points_index, 'total_team_points']
    return owner_with_highest_points, highest_points

def iterate_weeks(week, standings_df, weekly_matchup, rosters_df, player_dict, league):
    #Parse through each week and identify the lowest scoring team and calculate the median points scored
    for i in range(1, week + 1):
        matchup_df = weekly_matchup(i, rosters_df, player_dict, league)
        #Find the owner with the lowest score
        min_points_index = matchup_df['total_team_points'].idxmin()
        #Use the index to get the owner with the lowest points
        owner_with_lowest_points = matchup_df.loc[min_points_index, 'owner']
        #Add a one to the column 'lowest_scoring_team' for the owner with the lowest points
        standings_df.loc[standings_df['owner'] == owner_with_lowest_points, 'lowest_scoring_team'] += 1

        if i == 1:
            #Create a new empty dataframe called 'points_scored_df'
            points_scored_df = pd.DataFrame(columns = ['owner', 'week', 'points_scored'])
            #Add the 'owner' column to the dataframe
            points_scored_df['owner'] = matchup_df['owner']
            #Add the 'week' column to the dataframe
            points_scored_df['week'] = i
            #Add the 'points_scored' column to the dataframe
            points_scored_df['points_scored'] = matchup_df['total_team_points']
        else:
            #Add a new set of rows into the 'points_scored_df' dataframe
            points_scored_df = points_scored_df.append({'owner': matchup_df['owner'], 'week': i, 'points_scored': matchup_df['total_team_points']}, ignore_index=True)

    #Calculate the median points scored for each owner
    median_points_scored = points_scored_df.groupby('owner')['points_scored'].median().reset_index()
    #Rename the 'points_scored' column to 'median_points_scored'
    median_points_scored.rename(columns={'points_scored': 'median_weekly_score'}, inplace=True)
    #Add the 'median_weekly_score' column to the 'standings_df' dataframe
    return standings_df.merge(median_points_scored, on='owner').sort_values(by=['wins', 'points_scored'], ascending=False)



########################################################################
###########################ESPN Section#################################
########################################################################

headers  = {
    'Connection': 'keep-alive',
    'Accept': 'application/json, text/plain, */*',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
}

custom_headers = {
 'Connection': 'keep-alive',
 'Accept': 'application/json, text/plain, */*',
 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
 'x-fantasy-filter': '{"filterActive":null}',
 'x-fantasy-platform': 'kona-PROD-1dc40132dc2070ef47881dc95b633e62cebc9913',
 'x-fantasy-source': 'kona'
}

owner_dict = {1: 'Tom Zhang', 
              2: 'Francis Jin', 
              3: 'Peter Li', 
              4: 'Richard Liang', 
              5: 'John Dong', 
              6: 'Dan Jiang', 
              7: 'Scott Lin', 
              9: 'John Qian', 
              10: 'Richie Kay',
              11: 'Justin Chen',
              12: 'John Choi', 
              13: 'Kai Shen',
              14: 'Andrew Kim',
              15: "Kyle O'Meara"}

position_mapping = {
 1: 'QB',
 2: 'RB',
 3: 'WR',
 4: 'TE',
 5: 'K',
 16: 'D/ST'
}

# we have a two qb league but QB2 is an OP incase you can roster 2 QBs in a week
eligible_positions = {
 0 : 'QB', 
 2 : 'RB', 
 4 : 'WR',
 6 : 'TE', 
 7 : 'OP',
 16: 'D/ST', 
 17: 'K',
 20: 'Bench', 
 23: 'Flex'
}


def load_league(year, league_id, espn_cookies):
    #Matchup Data
    team_url = 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{}/segments/0/leagues/{}?view=mDraftDetail&view=mSettings&view=mTeam&view=modular&view=mNav'
    url = team_url.format(year, league_id)
    r = requests.get(url,headers=headers,cookies=espn_cookies)
    return r.json()


def load_records(league_data):
    record_data = []
    for team in league_data['teams']:
        team_name = team['location'] + ' ' + team['nickname']
        team_list = [team['id'], team_name, team['record']['overall']['wins'], team['record']['overall']['losses'], team['record']['overall']['pointsFor'], team['record']['overall']['pointsAgainst']]
        record_data.append(team_list)

    record_df = pd.DataFrame(record_data, columns=['team_id', 'team_name', 'wins', 'losses', 'points_for', 'points_against'])
    record_df['owner'] = record_df['team_id'].map(owner_dict)
    return record_df[['team_id','owner', 'team_name','wins', 'losses', 'points_for', 'points_against']].sort_values(by=['wins', 'points_for'], ascending=False)

def fetch_espn_data(url, params, cookies):
    return requests.get(url, params=params, cookies=cookies)

def load_schedule(year, league_id, espn_cookies, week):
    url = 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{}/segments/0/leagues/{}?view=mMatchupScoreLite'.format(year, league_id)
    r = requests.get(url, cookies=espn_cookies)
    data = r.json()

    schedule = pd.DataFrame(data['schedule'])
    schedule = schedule.loc[schedule['matchupPeriodId'] == week].drop(columns = 'matchupPeriodId')
    away = pd.json_normalize(schedule['away']).drop(columns=['totalPoints']).rename(columns={'pointsByScoringPeriod.1':'points'})
    away.columns = 'away_' + away.columns
    home = pd.json_normalize(schedule['home']).drop(columns=['totalPoints']).rename(columns={'pointsByScoringPeriod.1':'points'})
    home.columns = 'home_' + home.columns
    schedule = pd.concat([schedule, away, home], axis=1).drop(columns=['away','home'])
    #change the column 'id' to 'matchup_id'
    schedule = schedule.rename(columns={'id':'matchup_id'})
    #transform the schedule dataframe so there are no home and away columns and each matchup_id has two rows
    schedule = pd.concat([schedule[['matchup_id','away_teamId','away_points','home_teamId','home_points']].rename(columns={'away_teamId':'teamId','away_points':'points'}),
                            schedule[['matchup_id','home_teamId','home_points','away_teamId','away_points']].rename(columns={'home_teamId':'teamId','home_points':'points'})])
    #if home_teamId or home_points are null, then paste the away_teamId and away_points in their place
    schedule['home_teamId'] = schedule['home_teamId'].fillna(schedule['away_teamId'])
    schedule['home_points'] = schedule['home_points'].fillna(schedule['away_points'])
    #sort the schedule by matchup_id
    schedule.sort_values(by=['matchup_id', 'teamId'], inplace=True, ignore_index=True)
    schedule.drop(columns=['home_teamId', 'home_points','away_teamId','away_points'], inplace=True)
    return schedule

def load_weekly_stats(year, league_id, espn_cookies, week):
    #Matchup Data
    url = 'https://fantasy.espn.com/apis/v3/games/ffl/seasons/{}/segments/0/leagues/{}?view=mMatchup&view=mMatchupScore'.format(year, league_id)
    # create an empty list to append data to
    projection_data = []
    # Define a timeout value in seconds
    timeout_value = 5 

    try:
        #Request data from ESPN
        r = requests.get(url,
                        params={'scoringPeriodId': week},
                        cookies=espn_cookies)
        espn_raw_data = r.json()
        time.sleep(1)
    except TimeoutError:
        # Handle the timeout (e.g., restart or report an error)
        print("Request timed out. Restarting")

    # loop over each team in the request
    for team in espn_raw_data['teams']:
        # get the team_id so we can map it to team_names
        team_id = team['id']
        # loop over every player on the teams roster
        for player in team['roster']['entries']:
            player_name = player['playerPoolEntry']['player']['fullName']
            lineup_slot = player['lineupSlotId']
            # create a new column with the position using the lineup_slot as the key
            #position = eligible_positions[lineup_slot]
            
            # get the projected and actual points
            projected = None, 
            actual = None
            # loop over the stats for each player
            for stats in player['playerPoolEntry']['player']['stats']:
                # skip the rows where the scoring period does not match up with the curren week
                if stats['scoringPeriodId'] != week:
                    continue
                # if the source id = 0 then these are actual stats
                if stats['statSourceId'] == 0:
                    actual = stats['appliedTotal']
                # if the source id = 1 then these are projected stats
                elif stats['statSourceId'] == 1:
                    projected = stats['appliedTotal']
            
            # append all the data to the empty list
            projection_data.append([
                week, 
                team_id, 
                player_name, 
                lineup_slot, 
                projected, 
                actual
                ])

    # convert the list to a dataframe with the following column names
    weekly_df = pd.DataFrame(projection_data)
    #Set column names
    weekly_df.columns = ['week', 'teamId', 'player', 'lineup_slot', 'projected', 'actual']
    #Map the team id to the owner name
    weekly_df['owner'] = weekly_df['teamId'].map(owner_dict)
    #Map the lineup slot to the position
    weekly_df['lineup_slot'] = weekly_df['lineup_slot'].map(eligible_positions)
    #Filter out the bench players
    weekly_df = weekly_df[weekly_df['lineup_slot'] != 'Bench']
    weekly_df = weekly_df[weekly_df['lineup_slot'].notna()]
    return weekly_df

def modify_positions(df):
    # Function to modify lineup_slot based on positions
    positions_to_modify = ['RB', 'WR']
    for position in positions_to_modify:
        count = 0
        for i, row in df.iterrows():
            if row['lineup_slot'] == position:
                count += 1
                df.at[i, 'lineup_slot'] = f'{position}{count}'
    return df

def transform_weekly(weekly_df, schedule):
    #Merge with schedule
    weekly_df = schedule.merge(weekly_df, on=['teamId'], how='left')

    #Clean the positions
    weekly_df = weekly_df.groupby('owner').apply(modify_positions).reset_index(drop=True)
    
    #Transform the dataframe
    #Create pivot tables for each position
    pivot_tables = {}
    positions = weekly_df['lineup_slot'].unique()
    #remove nan from the list
    positions = positions[~pd.isnull(positions)]

    for position in positions:
        pivot_table = weekly_df[weekly_df['lineup_slot'] == position].pivot_table(
            values=['player', 'actual'],
            index=['teamId', 'owner'],
            columns=['lineup_slot'],
            aggfunc='first'
        )
        pivot_tables[position] = pivot_table

    # Merge pivot tables into one
    result_df = pd.concat(pivot_tables.values(), axis=1)
    # Reset column levels and rename columns
    result_df.columns = result_df.columns.map(lambda x: '_'.join(x))
    result_df.reset_index(inplace=True)

    #For every column that starts with 'player_', remove the 'player_' and for columns that start with 'actual_', remove the 'actual_' and add '_PTS' to the end
    result_df.columns = result_df.columns.map(lambda x: x.replace('player_', '').replace('actual_', '') + '_PTS' if x.startswith('actual_') else x.replace('player_', ''))
    matchup_df = schedule.merge(result_df, how='left', on='teamId')
    #rename the 'points' column to 'total_points'
    matchup_df.rename(columns={'points':'total_points'}, inplace=True)
    #Reorder the columns
    matchup_df = matchup_df[['matchup_id', 'teamId', 'owner', 'total_points', 'QB', 'QB_PTS', 'RB1', 'RB1_PTS', 'RB2', 'RB2_PTS', 'WR1', 'WR1_PTS', 'WR2', 'WR2_PTS', 'TE', 'TE_PTS', 'Flex', 'Flex_PTS', 'D/ST', 'D/ST_PTS', 'K', 'K_PTS']]
    return matchup_df


def highest_scoring_player_espn(weekly_df):
    #Find the highest scoring player
    highest_player = weekly_df.loc[weekly_df['actual'].idxmax()]
    return highest_player.owner, highest_player.player, highest_player.actual

def highest_scoring_team_espn(weekly_df):
    #Find the highest scoring team
    highest_team = weekly_df.groupby('owner').sum().sort_values(by='actual', ascending=False).head(1)
    return highest_team.index[0], highest_team['actual'][0]
    
def iterate_weeks_espn(year, week, standings_df, league_id, espn_cookies):
    #Lowest Scoring Team column and set it to 0
    standings_df['lowest_scoring_team'] = 0

    #Create points scored df
    points_scored_df = pd.DataFrame(columns = ['owner', 'week', 'points_scored'])
    
    #Parse through each week and identify the lowest scoring team and record the points scored
    for i in range(1, week + 1):
        weekly_df = load_weekly_stats(year, league_id, espn_cookies,i)
        weekly_df = weekly_df[weekly_df['lineup_slot'] != 'Bench']
        matchup_df = weekly_df.groupby('owner')['actual'].sum().reset_index()
        #Find the owner with the lowest score
        min_points_index = matchup_df['actual'].idxmin()
        #Use the index to get the owner with the lowest points
        owner_with_lowest_points = matchup_df.loc[min_points_index, 'owner']
        
        #Add a one to the column 'lowest_scoring_team' for the owner with the lowest points
        standings_df.loc[standings_df['owner'] == owner_with_lowest_points, 'lowest_scoring_team'] += 1

        #Update the points_scored_df
        append = pd.DataFrame({'owner': matchup_df['owner'], 'week': i, 'points_scored': matchup_df['actual']})
        points_scored_df = pd.concat([points_scored_df, append], ignore_index=True)
        print('Completed week: ' + str(i))

    #Calculate the median points scored
    median_points_scored = points_scored_df.groupby('owner')['points_scored'].median().reset_index()
    median_points_scored.rename(columns={'points_scored': 'median_weekly_score'}, inplace=True)
    #Add the 'median_weekly_score' column to the 'standings_df' dataframe
    return standings_df.merge(median_points_scored, on='owner').sort_values(by=['wins', 'points_for'], ascending=False)
