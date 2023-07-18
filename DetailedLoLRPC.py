from lcu_driver import Connector
from ultilities import *
from cdngen import *
from disabler import disableNativePresence
from pypresence import Presence
from time import time
from aiohttp import request
from os import _exit
from tray_icon import icon

RPC = Presence(client_id = clientId)

connector = Connector()

@connector.ready
async def connect(connection):
    print("Inited")
    global internalName, summonerId, discStrings
    while True:
        summoner = await connection.request('get', '/lol-summoner/v1/current-summoner')
        if not summoner.status == 404:
            summoner = await summoner.json()
            break
    internalName = summoner['internalName']
    summonerId = summoner['summonerId']
    region = await connection.request('get', '/riotclient/get_region_locale')
    locale = (await region.json())['locale'].lower()

    async with request("GET", localeDiscordStrings(locale)) as resp:
        discord_strings = await resp.json()
    discStrings = {
        "bot": discord_strings["Disc_Pres_QueueType_BOT"],
        "champSelect": discord_strings["Disc_Pres_State_championSelect"],
        "lobby": discord_strings["Disc_Pres_State_hosting"],
        "inGame": discord_strings["Disc_Pres_State_inGame"],
        "inQueue": discord_strings["Disc_Pres_State_inQueue"],
        "custom": discord_strings["Disc_Pres_QueueType_CUSTOM"]
    }

@connector.close
async def disconnect(_):
    _exit(0)

@connector.ws.register("/lol-gameflow/v1/session", event_types = ("CREATE", "UPDATE", "DELETE"))
async def gameFlow(connection, event):
    data = event.data
    gameData = data['gameData']
    queueData = gameData['queue']
    mapData = data['map']
    phase = data['phase']

    if phase == "None":
        RPC.clear()
        return

    lobbyMem = len(await (await connection.request('get', '/lol-lobby/v2/lobby/members')).json())

    if queueData["type"] == "BOT":
        queueData['description'] = discStrings["bot"] + " " + queueData['description']
    if queueData["category"] == "Custom":
        queueData['description'] = discStrings["custom"]

    if phase == "Lobby":
        RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
                large_image = mapIdimg(queueData["mapId"]), \
                large_text = mapData['name'], \
                state = discStrings["lobby"], \
                party_size = [lobbyMem, queueData["maximumParticipantListSize"]])
        
    elif phase == "Matchmaking":
        RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
                large_image = mapIdimg(queueData["mapId"]), \
                large_text = mapData['name'], \
                state = discStrings["inQueue"], \
                start = time())
        
    elif phase == "ChampSelect":
        RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
                large_image = mapIdimg(queueData["mapId"]), \
                large_text = mapData['name'], \
                state = discStrings["champSelect"])
        
    elif phase == "InProgress":
        # TFT handling (no skin images)
        if mapData["mapStringId"] == "TFT":
            RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
                    large_image = mapIdimg(queueData["mapId"]), \
                    large_text = mapData['name'], \
                    state = discStrings["inGame"], \
                    start = time())
            
        # Other modes (with champion skin images)
        else:
            for summoner in gameData["playerChampionSelections"]:
                if summoner["summonerInternalName"] == internalName:
                    champId = summoner["championId"]
                    skinId = champId * 1000 + summoner["selectedSkinIndex"]
                    break

            skinName = (await (await connection.request('get', f'/lol-champions/v1/inventories/{summonerId}/champions/{champId}/skins/{skinId}')).json())["name"]
                
            RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
                    large_image = skinImg(champId, skinId), \
                    large_text = skinName, \
                    state = discStrings["inGame"], \
                    start = time())

# Tray Icon
icon.run_detached()

# Disable League's Native RPC
disableNativePresence()

# Connect the RPC to Discord
RPC.connect()

# Start the LCU API
connector.start()