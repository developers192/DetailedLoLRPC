from ultilities import resourcePath
from os import _exit
from PIL import Image
from pystray import Icon, Menu, MenuItem

img = Image.open(resourcePath("icon.ico"))

def click(icon: Icon, query):
    icon.stop()
    _exit(0)

icon = Icon("DetailedLoLRPC", img, "DetailedLoLRPC", 
            Menu(MenuItem("Exit", click)))