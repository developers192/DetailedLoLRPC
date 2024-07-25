from lcu_driver import Connector
from utilities import isOutdated, GITHUBURL, CLIENTID, fetchConfig, procPath, resetLog, addLog, yesNoBox
from cdngen import *
from disabler import disableNativePresence
from pypresence import Presence
from time import time, sleep
from aiohttp import request
from os import _exit, system, path as op
from tray_icon import icon
from multiprocessing import Process, freeze_support
from subprocess import Popen, PIPE
from nest_asyncio import apply
from json import loads
from asyncio import sleep as asyncSleep
from modes import updateInProgressRPC

if __name__ == "__main__":

	freeze_support()

	apply()

	resetLog()

	fetchConfig("riotPath")

	# Check for updates
	outdated = isOutdated()
	if outdated:
		choice = yesNoBox(f"A newer version of DetailedLoLRPC detected ({outdated}). Do you want to visit the download site?")
		if choice:
			system(f"start \"\" {GITHUBURL}")
			sleep(1)
			_exit(0)

	RPC = Presence(client_id = CLIENTID)

	connector = Connector()

	@connector.ready
	async def connect(connection):
		print("Inited")
		global internalName, summonerId, discStrings, displayName
		while True:
			summoner = await connection.request('get', '/lol-summoner/v1/current-summoner')
			if not summoner.status == 404:
				summoner = await summoner.json()
				break
		print("Logged in")

		internalName = summoner['internalName']
		summonerId = summoner['summonerId']
		displayName = summoner['displayName']
		region = await connection.request('get', '/riotclient/region-locale')
		global locale
		locale = (await region.json())['locale'].lower()
		
		addLog({"internalName": internalName, "displayName": displayName, "summonerId": summonerId, "locale": locale})

		async with request("GET", localeDiscordStrings(locale)) as resp:
			discord_strings = loads((await resp.text()).encode().decode('utf-8-sig'))
		async with request("GET", localeChatStrings(locale)) as resp:
			chat_strings = loads((await resp.text()).encode().decode('utf-8-sig'))

		discStrings = {
			"bot": discord_strings["Disc_Pres_QueueType_BOT"],
			"champSelect": discord_strings["Disc_Pres_State_championSelect"],
			"lobby": discord_strings["Disc_Pres_State_hosting"],
			"inGame": discord_strings["Disc_Pres_State_inGame"],
			"inQueue": discord_strings["Disc_Pres_State_inQueue"],
			"custom": discord_strings["Disc_Pres_QueueType_CUSTOM"],
			"practicetool": (await (await connection.request('get', '/lol-maps/v2/map/11/PRACTICETOOL')).json())["gameModeName"],

			"away": chat_strings["availability_away"],
			"chat": chat_strings["availability_chat"],
			"dnd": chat_strings["availability_dnd"]
		}
		print("Loaded Discord Strings")

	@connector.close
	async def disconnect(_):
		await asyncSleep(10)
		if not procPath("LeagueClient.exe"):
			_exit(0)

	@connector.ws.register("/lol-gameflow/v1/session", event_types = ("CREATE", "UPDATE", "DELETE"))
	async def gameFlow(connection, event):
		data = event.data
		phase = data['phase']

		if phase not in ("Lobby", "Matchmaking", "ChampSelect", "InProgress"): return
		
		gameData = data['gameData']
		queueData = gameData['queue']
		mapData = data['map']
		mapIconData = mapData["assets"]["game-select-icon-active"]
		
		lobbyData = (await connection.request('get', '/lol-lobby/v2/lobby/members'))
		if lobbyData.status == 404: return
		lobbyMem = len(await lobbyData.json())

		if queueData["type"] == "BOT":
			queueData['description'] = discStrings["bot"] + " " + queueData['description']
		if queueData["category"] == "Custom":
			queueData['description'] = discStrings["custom"]
		if queueData['gameMode'] == "PRACTICETOOL":
			queueData['description'] = discStrings["practicetool"]

		if phase == "Lobby":
			if queueData["mapId"] == 0: return
			RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
					large_image = mapIcon(mapIconData), \
					large_text = mapData['name'], \
					state = discStrings["lobby"], \
					party_size = [lobbyMem, queueData["maximumParticipantListSize"]])
			
		elif phase == "Matchmaking":
			RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
					large_image = mapIcon(mapIconData), \
					large_text = mapData['name'], \
					state = discStrings["inQueue"], \
					start = time())
			
		elif phase == "ChampSelect":
			RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
					large_image = mapIcon(mapIconData), \
					large_text = mapData['name'], \
					state = discStrings["champSelect"])
			
		elif phase == "InProgress":
			await updateInProgressRPC(locale, mapData, mapIconData, queueData, gameData, internalName, displayName, connection, summonerId, discStrings, RPC)
		
		addLog({"gameData": {"playerChampionSelections": gameData["playerChampionSelections"]}, 
		  "queueData": {"type": queueData["type"], 
				  "category": queueData["category"],
				  "description": queueData['description'],
				  "gameMode": queueData['gameMode'],
				  "mapId": queueData["mapId"],
				  "maximumParticipantListSize": queueData["maximumParticipantListSize"]},
		  "mapData": {"name": mapData['name'], 
				"mapStringId": mapData["mapStringId"],
				"game-select-icon-active": mapIconData}, 
		  "phase": phase, "lobbyMem": lobbyMem})

	@connector.ws.register("/lol-chat/v1/me", event_types = ("CREATE", "UPDATE", "DELETE"))
	async def chatUpdate(connection, event):
		data = event.data
		phase = (await (await connection.request('get', '/lol-gameflow/v1/gameflow-phase')).json())
		if phase in ("None", "WaitingForStats", "TerminatedInError"):
			availability = data["availability"]
			option = fetchConfig("idleStatus")
			if option == 0:
				RPC.clear()
			elif option == 1:
				RPC.update(state = discStrings[availability], 
	       					large_image = availabilityImg("leagueIcon"), 
							small_image = availabilityImg(availability),)
			elif option == 2:
				RPC.update(state = discStrings[availability], 
	       					large_image = profileIcon(data["icon"]), 
						    large_text = f"{data['gameName']}#{data['gameTag']} | Lvl {data['lol']['level']}",
							small_image = availabilityImg(availability),
							small_text = data["statusMessage"] if data["statusMessage"] else None)

	# Detect if game has started
	isLeagueOpened = procPath("LeagueClient.exe")
	choice = "NoStart"
	if isLeagueOpened:
		choice = yesNoBox("DetailedLoLRPC might not work properly if opened after League of Legends. Continue?")
		if not choice:
			_exit(0)

	# Tray Icon
	icon.run_detached()

	# Disable League's Native RPC
	p = Process(target = disableNativePresence)
	p.start()

	# Start the game
	if choice == "NoStart":
		Popen([op.join(fetchConfig("riotPath"), "Riot Client", "RiotClientServices.exe"), '--launch-product=league_of_legends', '--launch-patchline=live'], stdout = PIPE, stdin = PIPE, shell = True)
	p.join()

	# Connect the RPC to Discord
	RPC.connect()

	# Start the LCU API
	connector.start()
	
