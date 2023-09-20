#Pip install sleeper-api-wrapper if you don't have it already
from sleeper_wrapper import League
from sleeper_wrapper import Players
from sleeper_wrapper import Stats

import requests
import pandas as pd
import time 
from datetime import datetime
import openai
from timeout_decorator import timeout
from tabulate import tabulate

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
    owners = config_data['sleeper']['owner_dict']
    #Replace the user_id with the owner name from the owners dictionary
    users_df['owner'] = users_df['user_id'].map(owners)

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

        #Create a new empty dataframe called 'points_scored_df'
        points_scored_df = pd.DataFrame(columns = ['owner', 'week', 'points_scored'])

        if i == 1:
            #Add the 'owner' column to the dataframe
            points_scored_df['owner'] = matchup_df['owner']
            #Add the 'week' column to the dataframe
            points_scored_df['week'] = i
            #Add the 'points_scored' column to the dataframe
            points_scored_df['points_scored'] = matchup_df['total_team_points']
        else:
            # Create a new dataframe with the new data
            new_data = pd.DataFrame({
                'owner': matchup_df['owner'],
                'week': i,
                'points_scored': matchup_df['total_team_points']
            })
            # Concatenate the new data with the existing 'points_scored_df'
            points_scored_df = pd.concat([points_scored_df, new_data], ignore_index=True)

        print('Week ' + str(i) + ' has been processed')

    #Calculate the median points scored for each owner
    median_points_scored = points_scored_df.groupby('owner')['points_scored'].median().reset_index()
    #Rename the 'points_scored' column to 'median_points_scored'
    median_points_scored.rename(columns={'points_scored': 'median_weekly_score'}, inplace=True)
    #Add the 'median_weekly_score' column to the 'standings_df' dataframe
    return standings_df.merge(median_points_scored, on='owner').sort_values(by=['wins', 'points_scored'], ascending=False)

def run_sleeper_weekly(week=None):
    """ 
    This is the main function that will run all of steps to fetch the league and weekly data, compute the scores, bounties and update the standings
    """
    if week is None:
        week = get_NFL_week()
    else:
        week = week
    
    ###Load the League data###
    league = League(config_data['sleeper']['league_id'])
    #Load the rosters
    rosters = league.get_rosters()
    #Load the players
    players = Players()
    #Load the owners
    owners_df = owners(league)
    player_dict = player_info(players)
    #Load the team rosters
    rosters_df = pd.DataFrame(rosters)
    rosters_df = rosters_df[['roster_id', 'owner_id', 'starters','players']]
    rosters_df = owners_df[['owner_id', 'owner']].merge(rosters_df, on='owner_id')
    
    #Set up initial standings
    standings = league.get_standings(league.get_rosters(), league.get_users())
    standings_df = pd.DataFrame(standings)
    #Add column names
    standings_df.columns = ['team_name', 'wins', 'losses', 'points_scored']
    standings_df = owners_df[['owner', 'team_name']].merge(standings_df, on='team_name')
    #Add an empty column called 'lowest_scoring_team'
    standings_df['lowest_scoring_team'] = 0
    print('Loaded the League Data from Sleeper')
    ###Process the weekly matchups, and update the standings###
    #Get the latest weekly matchup
    matchup_df = weekly_matchup(week, rosters_df, player_dict, league)
    updated_standings = iterate_weeks(week, standings_df, weekly_matchup, rosters_df, player_dict, league)
    updated_standings

    #Run the Bounty Functions
    HT_Owner, HT_Score = highest_scoring_team_sleeper(matchup_df)
    HP_Owner, HP_Player, HP_Score = highest_scoring_player_sleeper(matchup_df)
    print('Completed processing scores and updating standings')
    fname = 'weekly_scores/week{}_matchup_sleeper.csv'.format(week)
    matchup_df.to_csv(fname, index=False)
    print('Saved week {} matchup data'.format(week))
    return matchup_df, updated_standings, HT_Owner, HT_Score, HP_Owner, HP_Player, HP_Score

### GPT Summary Generation ###

week1_system_prompt = "You are an AI Fantasy Football commissioner tasked with writing a weekly summary to your league mates recapping the latest week of our Dynasty league\n\nI will provide you a table of the weekly matchups, which includes the owners, their matchup_ids (owners with the same matchup IDs are opponents for the week), their players and what they scored, and a standings table with everyone's records. \nUsing this information, I would like for you to write an email recapping the league in the style of Bill Simmons. Comment on individual match-ups, teams and players that scored well, and poke fun at the worst performing teams. Make the tone funny, light-hearted and slightly sarcastic. "

def generate_summary(week):
    
    #Convert tables 
    matchup_tabulate = tabulate(matchup_df, headers='keys', tablefmt='plain', showindex=False)
    standings_tabulate = tabulate(updated_standings, headers='keys', tablefmt='plain', showindex=False)