import requests
import urllib3
urllib3.disable_warnings()

def riotId():
    try:
        data = requests.get(f'https://127.0.0.1:2999/liveclientdata/activeplayername', verify=False, timeout=0.5)
        parsed_data = data.json()
    except:
        return False
    return str(parsed_data)

def getStats():
    try:
        riot_id = riotId()
        data = requests.get('https://127.0.0.1:2999/liveclientdata/playerlist', verify=False, timeout=0.5)
        parsed_data = data.json()
        for player in parsed_data:
            if player['riotId'] == riot_id:
                return {"kda": f"{player['scores']['kills']}/{player['scores']['deaths']}/{player['scores']['assists']}", \
                        "cs": str(player['scores']['creepScore']), \
                        "level": player['level']}
    except:
        pass
    return {"kda": None, "cs": None, "level": None}