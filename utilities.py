import sys
from psutil import process_iter as pi
from os import listdir, path as op, getenv, makedirs, _exit
from requests import get
from pickle import load, dump
from json import load as loadj, dump as dumpj
from easygui import enterbox

VERSION = "v2.7"
GITHUBURL = "https://github.com/developers192/DetailedLoLRPC/releases/latest"
ISSUESURL = "https://github.com/developers192/DetailedLoLRPC/issues/new"
DEFAULTCONFIG = {
	"useSkinSplash": True,
	"showViewArtButton": False,
	"idleStatus": 0,
	"riotPath": ""
}
CONFIGDIR = op.join(getenv("APPDATA"), "DetailedLoLRPC", "config.dlrpc")
LOGDIR = op.join(getenv("APPDATA"), "DetailedLoLRPC", "sessionlog.json")
CLIENTID = "1118062711687872593"

def resourcePath(relative_path):
	try:
		base_path = sys._MEIPASS
	except Exception:
		base_path = op.abspath(".")

	return op.join(base_path, relative_path)

def procPath(name):
	for proc in pi():
		if proc.name() == name:
			return proc.exe()
	return False

def checkRiotClientPath(path):
	try:
		for p in listdir(op.join(path, "League of Legends")):
			if p == "LeagueClient.exe":
				return True
	except:
		return False
	return False

def isOutdated():
	latestver = get(GITHUBURL).url.split(r"/")[-1]
	if latestver != VERSION:
		return latestver
	return False

def getRiotPath():
	path = procPath("RiotClientServices.exe")
	if path:
		path = op.dirname(op.dirname(path))
	else:
		path = enterbox(r'Riot Services process was not found. Please enter the path to the "Riot Games" folder below (E.g. C:\Riot Games)', "DetailedLoLRPC")
		while True:
			if path is None:
				_exit(0)
			if checkRiotClientPath(path):
				break
			path = enterbox(r'Invalid Path. Please enter the path to the "Riot Games" folder below (E.g. C:\Riot Games)', "DetailedLoLRPC")
	return path

def fetchConfig(entry):
	makedirs(op.dirname(CONFIGDIR), exist_ok = True)
	try:
		with open(CONFIGDIR, "rb") as f:
			data = load(f)
	except FileNotFoundError:
		DEFAULTCONFIG["riotPath"] = getRiotPath()
		with open(CONFIGDIR, "wb") as f:
			dump(DEFAULTCONFIG, f)
		data = DEFAULTCONFIG
	try: data = data[entry]
	except KeyError: 
		editConfig(entry, DEFAULTCONFIG[entry])
		data = DEFAULTCONFIG[entry]
	return data

def editConfig(entry, value):
	with open(CONFIGDIR, "rb") as f:
		data = load(f)
	data[entry] = value
	with open(CONFIGDIR, "wb") as f:
		dump(data, f)
	return

def resetConfig():
	DEFAULTCONFIG["riotPath"] = getRiotPath()
	with open(CONFIGDIR, "wb") as f:
		dump(DEFAULTCONFIG, f)
	return

def resetLog():
	makedirs(op.dirname(LOGDIR), exist_ok = True)
	with open(LOGDIR, "w") as f:
		dumpj([], f)
	return

def addLog(data):
	try:
		with open(LOGDIR, "r") as f:
			logs = loadj(f)
	except FileNotFoundError:
		resetLog()
		logs = []
	logs.append(data)
	with open(LOGDIR, "w") as f:
		dumpj(logs, f)