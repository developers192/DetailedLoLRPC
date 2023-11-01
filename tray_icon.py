from os import _exit, system, startfile, path as op
from PIL import Image
from pystray import Icon, Menu, MenuItem
from utilities import editConfig, fetchConfig, resourcePath, resetConfig, ISSUESURL, LOGDIR, VERSION

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

def rpbug(icon: Icon, query):
    system(f"start \"\" {ISSUESURL}")
    startfile(op.dirname(LOGDIR))

icon = Icon("DetailedLoLRPC", img, "DetailedLoLRPC", 
            Menu(
                MenuItem(f"DetailedLoLRPC {VERSION} - by Ria", None, enabled=False),
                Menu.SEPARATOR,
                MenuItem("Use Skin's splash and name", skinSplash, checked = lambda item: fetchConfig("useSkinSplash")),
                MenuItem('Show "View splash art" button', viewSplash, checked = lambda item: fetchConfig("showViewArtButton")),
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