# fantasy-football-weekly-summary-email
Python functions and notebooks that sends automate weekly emails to your fantasy league for ESPN and Sleeper Leagues

## Overview
This project contains Python scripts and a Jupyter notebook that sends automated weekly emails to for ESPN and Sleeper Fantasy Football leagues. The main functionality is encapsulated in the espn_functions.py and sleeper.py files, which contains various functions for interacting with Sleeper and ESPN's Fantasy Football API, as well as OpenAI to for email generation. These functions are then used in a Jupyter notebook (espn_notebook.ipynb) to run specific analysis tasks, such as generating weekly summaries and matchups.

# Requirements & Setup
1. Packages 
2. The current code requires the following information to be filled into the config.json, which is broken out in the following sections
- Sleeper (do not fill out if you are playing in a ESPN league)
    - [league_id](https://support.sleeper.com/en/articles/4121798-how-do-i-find-my-league-id)
    - Owner_Dict: maps the [owner_id] (https://docs.sleeper.com/#getting-users-in-a-league) to the name of the team owner (I created this b/c our user and display names on Sleeper)
    - Division_Dict (optional and only applicable to leagues with divisions): maps owner names with division numbers. this dict is only used in customized playoff seeding



