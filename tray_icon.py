from os import _exit
from PIL import Image
from pystray import Icon, Menu, MenuItem
from utilities import editConfig, fetchConfig, resourcePath, resetConfig

img = Image.open(resourcePath("icon.ico"))

def exitp(icon: Icon, query):
    icon.stop()
    _exit(0)

def skinSplash(icon: Icon, query):
    state = fetchConfig("useSkinSplash")
    editConfig("useSkinSplash", not state)

def viewSplash(icon: Icon, query):
    state = fetchConfig("showViewArtButton")
    editConfig("showViewArtButton", not state)

def idleStatus(icon: Icon, query):
    if str(query) == "Disabled":
        val = 0
    elif str(query) == "Simple":
        val = 1
    else:
        val = 2
    editConfig("idleStatus", val)

icon = Icon("DetailedLoLRPC", img, "DetailedLoLRPC", 
            Menu(
                MenuItem("Use Skin's splash and name", skinSplash, checked = lambda item: fetchConfig("useSkinSplash")),
                MenuItem('Show "View splash art" button', viewSplash, checked = lambda item: fetchConfig("showViewArtButton")),
                MenuItem("Idle status", Menu(
                    MenuItem("Disabled", idleStatus, checked = lambda item: fetchConfig("idleStatus") == 0),
                    MenuItem("Simple", idleStatus, checked = lambda item: fetchConfig("idleStatus") == 1),
                    MenuItem("Detailed", idleStatus, checked = lambda item: fetchConfig("idleStatus") == 2)
                )),
                Menu.SEPARATOR,
                MenuItem("Reset preferences", resetConfig),
                MenuItem("Exit", exitp),
                ))