from src.utilities import init
init()

from src.utilities import isOutdated, GITHUBURL, CLIENTID, fetchConfig, procPath, resetLog, addLog, yesNoBox
from src.cdngen import *
from src.disabler import disableNativePresence
from src.tray_icon import icon, updateStatus	
from src.modes import updateInProgressRPC

from pypresence import Presence
from lcu_driver import Connector	

from time import time, sleep
from aiohttp import request
from os import _exit, system, path as op
from multiprocessing import Process, freeze_support
from subprocess import Popen, PIPE
from nest_asyncio import apply
from asyncio import sleep as asyncSleep, create_task
from json import loads


if __name__ == "__main__":

	freeze_support()

	apply()

	resetLog()

	currentChamp = (1, 0)
	stopFlag = {"running": False}
	loopTask = None

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

		updateStatus("Status: Loading Discord strings...")
		async with request("GET", localeDiscordStrings(locale)) as resp:
			discord_strings = loads((await resp.text()).encode().decode('utf-8-sig'))
		updateStatus("Status: Loading locale strings...")
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

		updateStatus("Status: Ready")

	@connector.close
	async def disconnect(_):
		updateStatus("Status: Disconnected")
		await asyncSleep(10)
		if not procPath("LeagueClient.exe"):
			_exit(0)

	@connector.ws.register("/lol-gameflow/v1/session", event_types = ("CREATE", "UPDATE", "DELETE"))
	async def gameFlow(connection, event):
		global stopFlag, loopTask
		if stopFlag["running"]:
			stopFlag["running"] = False
			if loopTask:
				await loopTask

		data = event.data
		phase = data['phase']

		if phase not in ("Lobby", "Matchmaking", "ChampSelect", "InProgress"): return
		
		gameData = data['gameData']
		queueData = gameData['queue']
		mapData = data['map']
		mapIconData = mapData["assets"]
		if not mapIconData: return
		mapIconData = mapIconData["game-select-icon-active"]
		
		lobbyData = (await connection.request('get', '/lol-lobby/v2/lobby/members'))
		if lobbyData.status == 404 and phase != "InProgress": return
		lobbyMem = len(await lobbyData.json())

		if queueData["type"] == "BOT":
			queueData['description'] = discStrings["bot"] + " " + queueData['description']
		if queueData["category"] == "Custom":
			queueData['description'] = discStrings["custom"]
		if queueData['gameMode'] == "PRACTICETOOL":
			queueData['description'] = discStrings["practicetool"]


		rankEmblem = None
		small_text = []
		try:
			if fetchConfig("showRanks")[queueData["type"]]:
				rank = await (await connection.request('get', f'/lol-ranked/v1/current-ranked-stats')).json()
				rank = rank["queueMap"][queueData["type"]]
				if rank["tier"] != "":
					small_text.append(f"{rank['tier'].capitalize()} {rank['division']}")
					rankEmblem = rankedEmblem(rank['tier'])
					if fetchConfig("rankedStats")["lp"]:
						small_text.append(f"{rank['leaguePoints']} LP")
					if fetchConfig("rankedStats")["w"]:
						small_text.append(f"{rank['wins']}W")
					if fetchConfig("rankedStats")["l"]:
						small_text.append(f"{rank['losses']}L")
		except KeyError:
			pass

		if phase == "Lobby":
			if queueData["mapId"] == 0: return
			updateStatus("Status: In Lobby")

			RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
					large_image = mapIcon(mapIconData), \
					large_text = mapData['name'], \
					small_image = rankEmblem, \
					small_text = " • ".join(small_text) if small_text else None, \
					state = discStrings["lobby"], \
					party_size = [lobbyMem, queueData["maximumParticipantListSize"]] if fetchConfig("showPartyInfo") else None)
			
		elif phase == "Matchmaking":
			updateStatus("Status: In Queue")
			RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
					large_image = mapIcon(mapIconData), \
					large_text = mapData['name'], \
					small_image=rankEmblem, \
					small_text = " • ".join(small_text) if small_text else None, \
					state = discStrings["inQueue"], \
					start = time())
			
		elif phase == "ChampSelect":
			updateStatus("Status: In Champ Select")
			RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
					large_image = mapIcon(mapIconData), \
					large_text = mapData['name'], \
					small_image = rankEmblem, \
					small_text = " • ".join(small_text) if small_text else None, \
					state = discStrings["champSelect"])
			
		elif phase == "InProgress":
			if stopFlag["running"]: return
			updateStatus("Status: In Game")
			stopFlag["running"] = True
			loopTask = create_task(updateInProgressRPC(stopFlag, time(), currentChamp, mapData, mapIconData, queueData, gameData, internalName, displayName, connection, summonerId, discStrings, RPC))
			
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

			global stopFlag, loopTask
			if stopFlag["running"]:
				stopFlag["running"] = False
				if loopTask:
					await loopTask

			updateStatus("Status: Ready")
	
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
	
	@connector.ws.register("/lol-champ-select/v1/session", event_types = ("CREATE", "UPDATE"))
	async def champSelect(connection, event):
		data = event.data
		global currentChamp
		for player in data["myTeam"]:
			if player["summonerId"] == summonerId:
				currentChamp = (player["championId"], player["selectedSkinId"])

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
	updateStatus("Status: Starting League...")
	if choice == "NoStart":
		Popen([op.join(fetchConfig("riotPath"), "Riot Client", "RiotClientServices.exe"), '--launch-product=league_of_legends', '--launch-patchline=live'], stdout = PIPE, stdin = PIPE, shell = True)
	p.join()

	# Connect the RPC to Discord
	updateStatus("Status: Connecting to Discord...")
	RPC.connect()

	# Start the LCU API
	updateStatus("Status: Connecting to League Client...")
	connector.start()
	
