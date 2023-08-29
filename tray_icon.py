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

def reset(icon: Icon, query):
    resetConfig()
    fetchConfig("riotPath")

icon = Icon("DetailedLoLRPC", img, "DetailedLoLRPC", 
            Menu(
                MenuItem("Use Skin's splash and name", skinSplash, checked = lambda item: fetchConfig("useSkinSplash")),
                MenuItem('Show "View splash art" button', viewSplash, checked = lambda item: fetchConfig("showViewArtButton")),
                Menu.SEPARATOR,
                MenuItem("Reset preferences", reset),
                MenuItem("Exit", exitp),
                ))