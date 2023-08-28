from json import load, dump
from time import time
from psutil import process_iter as pi
from os import path as op
from utilities import procPath, fetchConfig

def disableNativePresence():
	path = op.join(fetchConfig("riotPath"), "League of Legends", "Plugins", "plugin-manifest.json")

	with open(path, "r") as f:
		content = load(f)
		for idx, val in enumerate(content["plugins"]):
			if val["name"] == "rcp-be-lol-discord-rp":
				del content["plugins"][idx]
				break

	t = time()
	# Constantly disabling Rich Presence
	while True:
		with open(path, "w") as f:
			dump(content, f)
			
		# Stops when the client opened (60 seconds timeout)
		if procPath("LeagueClient.exe") or time() - t > 60:
			break