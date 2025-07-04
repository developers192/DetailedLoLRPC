# --- This file is part of the League of Legends Live Client API integration.

import requests
import json
import urllib3
from typing import Dict, Optional, Any

from .utilities import addLog, logger # Import logger and addLog

# --- Constants ---
LIVE_CLIENT_API_BASE_URL = "https://127.0.0.1:2999/liveclientdata"
REQUEST_TIMEOUT = 1.0 

# Suppress only the InsecureRequestWarning from urllib3 needed for verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Special marker to indicate API is not ready (e.g., loading screen 404 or connection error)
API_NOT_READY_MARKER = {"status": "api_not_ready"}

def _make_live_client_request(endpoint: str, description: str) -> Optional[Any]:
    """
    Helper function to make requests to the Live Client API.
    Handles common errors and JSON parsing. Returns API_NOT_READY_MARKER on 404 or connection issues.
    """
    url = f"{LIVE_CLIENT_API_BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, verify=False, timeout=REQUEST_TIMEOUT)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        
        if endpoint == "activeplayername": # This endpoint returns plain text
            try:
                # Try to parse as JSON first, as it might be a quoted string
                name_data = response.json() 
                if isinstance(name_data, str):
                    return name_data.strip('"') # Remove quotes if present
                else: 
                    # If it's not a simple string after JSON parsing, log and fallback to raw text
                    logger.warning(f"Unexpected JSON structure for {description} from {url}: {name_data}. Expected string.")
                    return response.text.strip() 
            except json.JSONDecodeError:
                # If not JSON, it's likely plain text
                logger.debug(f"{description} from {url} is not JSON, treating as plain text.")
                return response.text.strip() 

        return response.json() # For other endpoints that return JSON objects/lists
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.debug(f"Live Client API endpoint {url} returned 404 (Not Found) for {description}. Likely loading screen.")
            return API_NOT_READY_MARKER 
        logger.error(f"HTTPError fetching {description} from {url}: {e.response.status_code} - {e.response.text[:100]}", exc_info=False)
        addLog(f"Live Client API HTTPError: {description} {e.response.status_code}", level="ERROR")
        return None # For other HTTP errors
    except requests.exceptions.RequestException as e: # Catches ConnectionError, Timeout, etc.
        logger.warning(f"RequestException fetching {description} from {url}: {type(e).__name__}. Likely loading screen or client not in game.", exc_info=False)
        # Do not addLog here to avoid spamming if client is just not in game.
        return API_NOT_READY_MARKER # Treat connection errors also as API not ready
    except Exception as e: # Catch-all for other unexpected errors
        logger.error(f"Unexpected error in _make_live_client_request for {description} at {url}: {e}", exc_info=True)
        addLog(f"Live Client API Unexpected Error: {description} {str(e)}", level="ERROR")
        return None


def get_active_player_summoner_name() -> Optional[Any]: # Can return string or API_NOT_READY_MARKER
    """
    Fetches the summoner name of the active player from the Live Client API.
    Returns API_NOT_READY_MARKER if the API is not ready (404/connection error).
    """
    logger.debug("Fetching active player summoner name...")
    active_player_name_data = _make_live_client_request("activeplayername", "active player name")
    
    if active_player_name_data == API_NOT_READY_MARKER:
        return API_NOT_READY_MARKER # Propagate marker

    if active_player_name_data and isinstance(active_player_name_data, str):
        name = active_player_name_data # Already stripped in _make_live_client_request
        logger.debug(f"Active player summoner name: {name}")
        return name
    elif active_player_name_data: 
        logger.warning(f"Received non-string/non-marker data for active player name: {active_player_name_data}")
    return None

def get_current_game_time() -> Optional[Any]: # Can return float, API_NOT_READY_MARKER, or None
    """
    Fetches the current game time from /liveclientdata/gamestats.
    Returns the gameTime as float, API_NOT_READY_MARKER, or None if an error occurs.
    """
    logger.debug("Fetching current game time from API...")
    gamestats_data = _make_live_client_request("gamestats", "game time stats")

    if gamestats_data == API_NOT_READY_MARKER:
        return API_NOT_READY_MARKER
    
    if isinstance(gamestats_data, dict) and "gameTime" in gamestats_data:
        game_time = gamestats_data["gameTime"]
        if int(game_time) < 1: # If gameTime is less than 1 second, likely not started yet
            return API_NOT_READY_MARKER
        if isinstance(game_time, (float, int)):
            return float(game_time)
        else:
            logger.warning(f"gamestats API returned gameTime but it's not a number: {game_time}")
    elif gamestats_data is not None: # Data received but not in expected format
        logger.warning(f"gamestats API response did not contain 'gameTime' or was not a dict. Data: {str(gamestats_data)[:100]}")
    
    return None # If error, or gameTime not found/invalid type

def getStats() -> Dict[str, Any]: # Return type can include the marker
    """
    Fetches KDA, CS, and level for the active player from the Live Client API.
    Returns a dictionary with "kda", "cs", "level" as keys, or API_NOT_READY_MARKER.
    """
    logger.debug("Attempting to fetch live game stats...")
    default_stats = {"kda": None, "cs": None, "level": None}

    active_summoner_name_result = get_active_player_summoner_name()
    if active_summoner_name_result == API_NOT_READY_MARKER:
        logger.debug("Active player name endpoint not ready (getStats). Indicating API loading state.")
        return API_NOT_READY_MARKER
    if not active_summoner_name_result: 
        logger.warning("Could not determine active player's summoner name (not a 404/conn error). Cannot fetch stats.")
        return default_stats
    active_summoner_name = active_summoner_name_result 

    player_list_data = _make_live_client_request("playerlist", "player list")
    if player_list_data == API_NOT_READY_MARKER:
        logger.debug("Player list endpoint not ready (getStats). Indicating API loading state.")
        return API_NOT_READY_MARKER
    
    if not player_list_data or not isinstance(player_list_data, list):
        logger.warning(f"Could not retrieve or parse player list. Data: {str(player_list_data)[:100]}")
        return default_stats

    for player_data in player_list_data:
        if isinstance(player_data, dict) and player_data.get("summonerName") == active_summoner_name:
            try:
                scores = player_data.get("scores", {})
                kda_str = f"{scores.get('kills', 0)}/{scores.get('deaths', 0)}/{scores.get('assists', 0)}"
                cs_str = str(scores.get('creepScore', 0))
                level_str = str(player_data.get('level', 0)) 

                logger.debug(f"Stats found for {active_summoner_name}: KDA {kda_str}, CS {cs_str}, Lvl {level_str}")
                return {"kda": kda_str, "cs": cs_str, "level": level_str}
            except KeyError as e:
                logger.error(f"Missing expected key in player data for {active_summoner_name}: {e}", exc_info=True)
                return default_stats 
            except Exception as e: 
                logger.error(f"Error processing player data for {active_summoner_name}: {e}", exc_info=True)
                return default_stats

    logger.warning(f"Active player '{active_summoner_name}' not found in player list or stats missing.")
    return default_stats

def get_active_player_champion_data() -> Optional[Any]:
    """
    Fetches champion data for the active player from the Live Client API.
    Returns API_NOT_READY_MARKER if the API is not ready, or a tuple (championName, skinId), or (None, None) on error.
    """
    logger.debug("Fetching active player champion data...")
    active_name = get_active_player_summoner_name()
    if active_name == API_NOT_READY_MARKER:
        return API_NOT_READY_MARKER
    if not active_name:
        logger.warning("Could not determine active player's summoner name. Cannot fetch champion data.")
        return (None, None)

    player_list = _make_live_client_request("playerlist", "player list")
    if player_list == API_NOT_READY_MARKER:
        logger.debug("Player list endpoint not ready (champion data). Indicating API loading state.")
        return API_NOT_READY_MARKER
    if not player_list or not isinstance(player_list, list):
        logger.warning(f"Could not retrieve or parse player list for champion data. Data: {player_list}")
        return (None, None)

    for player in player_list:
        if isinstance(player, dict) and player.get("riotId") == active_name:
            champion = player.get("championName")
            skin_id = player.get("skinID")
            logger.debug(f"Champion data for {active_name}: {champion}, skin ID: {skin_id}")
            return (champion, skin_id)

    logger.warning(f"Active player '{active_name}' not found in player list for champion data.")
    return (None, None)

if __name__ == '__main__':
    logger.info("Running gamestats.py directly for testing...")
    
    current_time = get_current_game_time()
    if current_time == API_NOT_READY_MARKER:
        logger.info("Test Game Time: API not ready.")
    elif isinstance(current_time, float):
        logger.info(f"Test Game Time: {current_time:.2f} seconds")
    else:
        logger.warning("Test Game Time: Could not retrieve game time.")

    stats = getStats()
    if stats == API_NOT_READY_MARKER:
        logger.info("Test Stats: API not ready.")
    elif stats.get("kda"): 
        logger.info(f"Test Player Stats: KDA: {stats['kda']}, CS: {stats['cs']}, Level: {stats['level']}")
    else:
        logger.warning("Test Stats: Could not retrieve player stats.")

