from lcu_driver import Connector
from utilities import isOutdated, GITHUBURL, CLIENTID, fetchConfig, procPath
from cdngen import *
from disabler import disableNativePresence
from pypresence import Presence
from time import time, sleep
from aiohttp import request
from os import _exit, system, path as op
from tray_icon import icon
from easygui import buttonbox
from multiprocessing import Process, freeze_support
from subprocess import Popen, PIPE
from nest_asyncio import apply
from json import dump

if __name__ == "__main__":

	freeze_support()

	apply()

	# Check for updates
	outdated = isOutdated()
	if outdated:
		choice = buttonbox(f"A newer version of DetailedLoLRPC detected ({outdated}). Do you want to visit the download site?", "DetailedLoLRPC", ("Yes", "No"), cancel_choice = "No")
		if choice == "Yes":
			system(f"start \"\" {GITHUBURL}")
			sleep(1)
			_exit(0)

	RPC = Presence(client_id = CLIENTID)

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
		print("Logged in")

		internalName = summoner['internalName']
		summonerId = summoner['summonerId']
		region = await connection.request('get', '/riotclient/get_region_locale')
		locale = (await region.json())['locale'].lower()

		async with request("GET", localeDiscordStrings(locale)) as resp:
			discord_strings = await resp.json()
		async with request("GET", localeChatStrings(locale)) as resp:
			chat_strings = await resp.json()
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
		_exit(0)

	@connector.ws.register("/lol-gameflow/v1/session", event_types = ("CREATE", "UPDATE", "DELETE"))
	async def gameFlow(connection, event):
		data = event.data
		gameData = data['gameData']
		queueData = gameData['queue']
		mapData = data['map']
		phase = data['phase']

		lobbyMem = len(await (await connection.request('get', '/lol-lobby/v2/lobby/members')).json())

		if queueData["type"] == "BOT":
			queueData['description'] = discStrings["bot"] + " " + queueData['description']
		if queueData["category"] == "Custom":
			queueData['description'] = discStrings["custom"]
		if queueData['gameMode'] == "PRACTICETOOL":
			queueData['description'] = discStrings["practicetool"]

		if phase == "Lobby":
			if queueData["mapId"] == 0: return
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
			# TFT handling
			if mapData["mapStringId"] == "TFT":
				if fetchConfig("useSkinSplash"):
					compData = (await (await connection.request('get', '/lol-cosmetics/v1/inventories/tft/companions')).json())["selectedLoadoutItem"]
					RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
							large_image = tftImg(compData["loadoutsIcon"]), \
							large_text = compData['name'], \
							state = discStrings["inGame"], \
							start = time(), \
							buttons = ([{"label": "View Splash Art", "url": tftImg(compData["loadoutsIcon"])}] if fetchConfig("showViewArtButton") else None))
				else:
					RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
							large_image = mapIdimg(queueData["mapId"]), \
							large_text = mapData['name'], \
							state = discStrings["inGame"], \
							start = time())
				
			# Other modes
			else:
				for summoner in gameData["playerChampionSelections"]:
					if summoner["summonerInternalName"] == internalName:
						champId = summoner["championId"]
						skinId = champId * 1000 
						if fetchConfig("useSkinSplash"):
							skinId += summoner["selectedSkinIndex"]
						break

				champSkins = await (await connection.request('get', f'/lol-champions/v1/inventories/{summonerId}/champions/{champId}/skins')).json()
				for champSkin in champSkins:
					if champSkin["id"] == skinId:
						skinName = champSkin["name"]
						break

					_ok = False
				
					for skinTier in champSkin["questSkinInfo"]["tiers"]:
						if skinTier["id"] == skinId:
							skinName = skinTier["name"]
							_ok = True
							break
					if _ok: break

					for chroma in champSkin["chromas"]:
						if chroma["id"] == skinId:
							skinName = champSkin["name"]
							skinId = champSkin["id"]
							_ok = True
							break
					if _ok: break
				
				RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
						large_image = skinImg(champId, skinId), \
						large_text = skinName, \
						state = discStrings["inGame"], \
						start = time(), 
						buttons = ([{"label": "View Splash Art", "url": splashLink(champId, skinId)}] if fetchConfig("showViewArtButton") else None))

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
						    large_text = f"{data['name']} - Lvl {data['lol']['level']}",
							small_image = availabilityImg(availability),)

	# Detect if game has started
	isLeagueOpened = procPath("LeagueClient.exe")
	choice = "NoStart"
	if isLeagueOpened:
		choice = buttonbox(f"DetailedLoLRPC might not work properly if opened after League of Legends. Continue?", "DetailedLoLRPC", ("Yes", "No"), cancel_choice = "No")
		if choice == "No":
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