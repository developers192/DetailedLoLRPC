from ultilities import resourcePath
from os import _exit
from PIL import Image
from pystray import Icon, Menu, MenuItem
from ultilities import editConfig, fetchConfig

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

icon = Icon("DetailedLoLRPC", img, "DetailedLoLRPC", 
            Menu(
                MenuItem("Use Skin's splash and name", skinSplash, checked = lambda item: fetchConfig("useSkinSplash")),
                MenuItem('Show "View splash art" button', viewSplash, checked = lambda item: fetchConfig("showViewArtButton")),
                Menu.SEPARATOR,
                MenuItem("Exit", exitp),
                ))