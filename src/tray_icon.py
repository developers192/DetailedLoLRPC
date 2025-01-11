from os import _exit, system, startfile, path as op, execv
import sys
from PIL import Image
from pystray import Icon, Menu, MenuItem
from src.utilities import editConfig, fetchConfig, resourcePath, resetConfig, ISSUESURL, LOGDIR, VERSION

img = Image.open(resourcePath("icon.ico"))

def exitp(icon, query):
    icon.stop()
    _exit(0)

def skinSplash(icon, query):
    state = fetchConfig("useSkinSplash")
    editConfig("useSkinSplash", not state)

def viewSplash(icon, query):
    state = fetchConfig("showViewArtButton")
    editConfig("showViewArtButton", not state)

def idleStatus(icon, query):
    if str(query) == "Disabled":
        val = 0
    elif str(query) == "Simple":
        val = 1
    else:
        val = 2
    editConfig("idleStatus", val)

def animatedSplash(icon, query):
    state = fetchConfig("animatedSplash")
    editConfig("animatedSplash", not state)

def rpbug(icon, query):
    system(f"start \"\" {ISSUESURL}")
    startfile(op.dirname(LOGDIR))

def showPartyInfo(icon, query):
    state = fetchConfig("showPartyInfo")
    editConfig("showPartyInfo", not state)

def kda(icon, query):
    state = fetchConfig("stats")
    state["kda"] = not state["kda"]
    editConfig("stats", state)

def cs(icon, query):
    state = fetchConfig("stats")
    state["cs"] = not state["cs"]
    editConfig("stats", state)

def level(icon, query):
    state = fetchConfig("stats")
    state["level"] = not state["level"]
    editConfig("stats", state)

def rankSolo(icon, query):
    state = fetchConfig("showRanks")
    state["RANKED_SOLO_5x5"] = not state["RANKED_SOLO_5x5"]
    editConfig("showRanks", state)

def rankFlex(icon, query):
    state = fetchConfig("showRanks")
    state["RANKED_FLEX_SR"] = not state["RANKED_FLEX_SR"]
    editConfig("showRanks", state)

def rankTFT(icon, query):
    state = fetchConfig("showRanks")
    state["RANKED_TFT"] = not state["RANKED_TFT"]
    editConfig("showRanks", state)

def rankDoubleUp(icon, query):
    state = fetchConfig("showRanks")
    state["RANKED_TFT_DOUBLE_UP"] = not state["RANKED_TFT_DOUBLE_UP"]
    editConfig("showRanks", state)

def rankStatsLp(icon, query):
    state = fetchConfig("rankedStats")
    state["lp"] = not state["lp"]
    editConfig("rankedStats", state)

def rankStatsW(icon, query):
    state = fetchConfig("rankedStats")
    state["w"] = not state["w"]
    editConfig("rankedStats", state)

def rankStatsL(icon, query):
    state = fetchConfig("rankedStats")
    state["l"] = not state["l"]
    editConfig("rankedStats", state)

currentStatus = "Status: Running"
def updateStatus(status):
    global currentStatus
    currentStatus = status
    icon.update_menu()

icon = Icon("DetailedLoLRPC", img, "DetailedLoLRPC", 
            Menu(
                MenuItem(f"DetailedLoLRPC {VERSION} - by Ria", None, enabled=False),
                MenuItem(lambda text: currentStatus, None, enabled=False),
                Menu.SEPARATOR,
                MenuItem("Use Skin's splash and name", skinSplash, checked = lambda item: fetchConfig("useSkinSplash")),
                MenuItem("Use animated splash if available", animatedSplash, checked = lambda item: fetchConfig("animatedSplash")),
                MenuItem('Show "View splash art" button', viewSplash, checked = lambda item: fetchConfig("showViewArtButton")),
                MenuItem('Show party info', showPartyInfo, checked = lambda item: fetchConfig("showPartyInfo")),
                Menu.SEPARATOR,
                MenuItem("Ingame stats", Menu(
                    MenuItem("KDA", kda, checked = lambda item: fetchConfig("stats")["kda"]),
                    MenuItem("CS", cs, checked = lambda item: fetchConfig("stats")["cs"]),
                    MenuItem("Level", level, checked = lambda item: fetchConfig("stats")["level"])
                )),
                MenuItem("Show ranks", Menu(
                    MenuItem("Solo", rankSolo, checked = lambda item: fetchConfig("showRanks")["RANKED_SOLO_5x5"]),
                    MenuItem("Flex", rankFlex, checked = lambda item: fetchConfig("showRanks")["RANKED_FLEX_SR"]),
                    MenuItem("TFT", rankTFT, checked = lambda item: fetchConfig("showRanks")["RANKED_TFT"]),
                    MenuItem("TFT Double up", rankDoubleUp, checked = lambda item: fetchConfig("showRanks")["RANKED_TFT_DOUBLE_UP"])
                )),
                MenuItem("Ranked stats", Menu(
                    MenuItem("LP", rankStatsLp, checked = lambda item: fetchConfig("rankedStats")["lp"]),
                    MenuItem("Wins", rankStatsW, checked = lambda item: fetchConfig("rankedStats")["w"]),
                    MenuItem("Losses", rankStatsL, checked = lambda item: fetchConfig("rankedStats")["l"])
                )),
                MenuItem("Idle status", Menu(
                    MenuItem("Disabled", idleStatus, checked = lambda item: fetchConfig("idleStatus") == 0),
                    MenuItem("Simple", idleStatus, checked = lambda item: fetchConfig("idleStatus") == 1),
                    MenuItem("Detailed", idleStatus, checked = lambda item: fetchConfig("idleStatus") == 2)
                )),
                Menu.SEPARATOR,
                MenuItem("Reset preferences", resetConfig),
                MenuItem("Report bug", rpbug),
                MenuItem("Exit", exitp),
                ))