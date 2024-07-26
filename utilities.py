import sys
from psutil import process_iter as pi
from os import listdir, path as op, getenv, makedirs, _exit
from requests import get
from pickle import load, dump
from json import load as loadj, dump as dumpj
import tkinter as tk
from tkinter import messagebox, ttk
from dotenv import load_dotenv
from base64 import b64decode

def resourcePath(relative_path):
	try:
		base_path = sys._MEIPASS
	except Exception:
		base_path = op.abspath(".")

	return op.join(base_path, relative_path)


load_dotenv(resourcePath(".env"))

VERSION = "v3.1.2"
REPOURL = "https://github.com/developers192/DetailedLoLRPC/"
GITHUBURL = REPOURL + "/releases/latest"
ISSUESURL = REPOURL + "/issues/new"
ANIMATEDSPLASHESURL = "https://raw.githubusercontent.com/developers192/DetailedLoLRPC/master/animatedSplashes/"
DEFAULTCONFIG = {
	"useSkinSplash": True,
	"showViewArtButton": False,
	"animatedSplash": True,
	"idleStatus": 0,
	"riotPath": ""
}
CONFIGDIR = op.join(getenv("APPDATA"), "DetailedLoLRPC", "config.dlrpc")
LOGDIR = op.join(getenv("APPDATA"), "DetailedLoLRPC", "sessionlog.json")
CLIENTID = b64decode(getenv("CLIENTID")).decode("utf-8")

def yesNoBox(msg):
	root = tk.Tk()
	root.withdraw()
	root.attributes('-topmost', True)
	root.iconbitmap(resourcePath("icon.ico"))

	result = messagebox.askyesno("DetailedLoLRPC", msg)
	return result

def inputBox(msg):
	root = tk.Tk()
	root.withdraw()
	root.attributes('-topmost', True)
		
	dialog = tk.Toplevel(root)
	dialog.title("DetailedLoLRPC")
	dialog.geometry("360x150")
	dialog.resizable(False, False)
	dialog.iconbitmap(resourcePath("icon.ico"))
	dialog.attributes('-topmost', True)

	label = tk.Label(dialog, text= msg, wraplength=300)
	label.pack(pady=10)

	entry = tk.Entry(dialog, width=50)
	entry.pack(pady=5)
	
	button_frame = tk.Frame(dialog)
	button_frame.pack(pady=10)

	def on_yes():
		global result
		result = "-1"
		result = entry.get()
		dialog.destroy()

	yes_button = ttk.Button(button_frame, text="Confirm", style="Windows.TButton", command=on_yes)
	yes_button.pack(side=tk.LEFT, padx=5)
	
	def on_no():
		global result
		result = None
		dialog.destroy()
	dialog.protocol("WM_DELETE_WINDOW", on_no)

	no_button = ttk.Button(button_frame, text="Cancel", style="Windows.TButton", command=on_no)
	no_button.pack(side=tk.LEFT, padx=5)

	dialog.wait_window(dialog)
	return result

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
		n = "\n"
		path = inputBox(rf'Riot Services process was not found. Please enter the path to the "Riot Games" folder below{n}(E.g. C:\Riot Games)')
		while True:
			if path is None:
				_exit(0)
			if checkRiotClientPath(path):
				break
			path = inputBox(r'Invalid Path. Please enter the path to the "Riot Games" folder below (E.g. C:\Riot Games)')
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