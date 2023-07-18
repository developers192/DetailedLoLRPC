from psutil import process_iter as pi
from os import listdir, path as op, getcwd
from win32com.client import Dispatch

def createShortcut(path, target='', wDir='', icon='', args=''):    
	shell = Dispatch('WScript.Shell')
	shortcut = shell.CreateShortCut(path)
	shortcut.Targetpath = target
	shortcut.WorkingDirectory = wDir
	shortcut.Arguments = args
	if icon == '':
		pass
	else:
		shortcut.IconLocation = icon
	shortcut.save()
	
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

path = procPath("RiotClientServices.exe")
if not path:
	print('Riot Services process was not found.')
	while True:
		print(r'Enter the path to the "Riot Games" folder below. (E.g. C:\Riot Games)')
		path = input(">> ")

		# Check path
		if checkRiotClientPath(path):
			break
		print('Invalid path.')
else:
	path = op.split(op.split(path)[0])[0]

with open("RiotGamesPath.txt", "w") as f:
	f.write(path)

launchBat = f"""@echo off
start DetailedLoLRPC.exe
timeout /t 6 /nobreak > NUL
"{path}\Riot Client\RiotClientServices.exe" --launch-product=league_of_legends --launch-patchline=live
exit
"""

with open("StartLoL.bat", "w") as f:
	f.write(launchBat)

createShortcut(".\\League of Legends.lnk", 'cmd', getcwd(), r"%SystemDrive%\ProgramData\Riot Games\Metadata\league_of_legends.live\league_of_legends.live.ico", f"/c START /MIN {op.join(getcwd(), 'StartLoL.bat')}")