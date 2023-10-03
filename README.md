# fantasy-football-weekly-summary-email
Python functions and notebooks that sends automate weekly emails to your fantasy league for ESPN and Sleeper Leagues

## Overview
This project contains Python scripts and a Jupyter notebook that sends automated weekly emails to for ESPN and Sleeper Fantasy Football leagues. The main functionality is encapsulated in the espn_functions.py and sleeper.py files, which contains various functions for interacting with Sleeper and ESPN's Fantasy Football API, as well as OpenAI to for email generation. These functions are then used in a Jupyter notebook (espn_notebook.ipynb) to run specific analysis tasks, such as generating weekly summaries and matchups.

# Requirements & Setup
1. Custom Packages 
    - [OpenAI](https://github.com/openai/openai-python)
    - [Sleeper API Wrapper](https://github.com/SwapnikKatkoori/sleeper-api-wrapper/blob/master/README.md)
    - [Tabulate](https://pypi.org/project/tabulate/)
    - Timeout Decorator 

2. The current code requires the following information to be filled into the **config.json**, which is broken out in the following sections
    - Sleeper (do not fill out if you are playing in a ESPN league)
        - [league_id](https://support.sleeper.com/en/articles/4121798-how-do-i-find-my-league-id)
        - owner_dict: maps the [owner_id] (https://docs.sleeper.com/#getting-users-in-a-league) to the name of the team owner (I created this b/c our user and display names on Sleeper)
        - division_dict (optional and only applicable to leagues with divisions): maps owner names with division numbers. this dict is only used in customized playoff seeding
    - ESPN (vice versa for players on Sleeper leagues)
        - espn_s2: credentials for login. here is a [helpful YouTube video that shows how to obtain this and the swid](https://www.youtube.com/watch?v=tNcND9lVycA)
        - swid": see video above
        - league_id: can be found in your ESPN league URL
        - owner_dict: similar to the owner_dict in Sleeper, this maps the teamID to the name of the owner
    - OpenAi
        - API key: [Requires a registered OpenAI account](https://openai.com/blog/openai-api)
    - gmail
        - GMAIL_USER: your gmail address (if you are not using gmail, the SMTP code might require edits)
        - GMAIL_PW: this is your [Gmail APP password](https://support.google.com/accounts/answer/185833?hl=en) (not your regular login password)

# Code Process
The code runs in 3 main parts: **Data Ingestion, Summary Generation and Email Sending**

The Data Ingestion Part 
## 1A. ESPN Data Pull
The full ingestion and data manipulation can be run as:
~~~
from espn_functions import *
standings_df, matchup_df, HP_Owner, HP_Player, HP_Score, HT_Owner, HT_Score = run_espn_weekly(week = X, year = 2023)
~~~
The outputs for this function will all be used for the summary generation or included in the body of the email and they are:
- Standings Table
- Weekly Matchup and Performance Table 
- Highest Scoring Player, Owner and Score
- Highest Scoring Team and Score

## 1B. Sleeper Ingestion
Full ingestion and data manipulation can be run as:
~~~
from sleeper_functions import *
matchup_df, updated_standings, HT_Owner, HT_Score, HP_Owner, HP_Player, HP_Score = run_sleeper_weekly(week = 3)
~~~

Same outputs as that of the ESPN Section

## 2. Summary Generation
This is the system prompt used for the 

~~~
summary = generate_summary(week, matchup_df, standings_df, model = 'gpt-4')
~~~

## 3. Email Sending

~~~
send_email(user, week, summary, updated_standings.to_html(), HT_Owner, HT_Score, HP_Owner, HP_Player, HP_Score)
~~~

