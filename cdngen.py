def mapIdimg(mapid: int):
    conv = {
        11: "classic_sru",
        12: "aram",
        22: "tft",
        30: "gamemodex",
        21: "shared"
	}
    return f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/content/src/leagueclient/gamemodeassets/{conv[mapid]}/img/game-select-icon-active.png"

def mapIcon(data):
    return f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/" + "/".join(data.split("/")[2:]).lower()

def defaultTileLink(champId):
    return f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/{champId}.png"

def assetsLink(link):
    links = link.lower().split("/")[4:]
    return f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/assets/{'/'.join(links)}"

def tftImg(compDir):
    name = compDir.split("/")[-1].lower()
    return f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/assets/loadouts/companions/{name}"

def localeDiscordStrings(locale):
    if locale == "en_us":
        locale = "default"
    return f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/{locale}/v1/discord_strings.json"

def localeChatStrings(locale):
    if locale == "en_us":
        locale = "default"
    return f"https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-social/global/{locale}/trans.json"

def profileIcon(id):
    return f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/{id}.jpg"

def availabilityImg(a):
    conv = {
        "chat": "https://i.imgur.com/I2XxZ5y.png",
        "away": "https://i.imgur.com/X5YwSxs.png",
        "dnd": "https://i.imgur.com/5I4uDSL.png",
        "leagueIcon": "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/assets/splashscreens/lol_icon.png"
    }
    return conv[a]

from utilities import ANIMATEDSPLASHESURL
def animatedSplashUrl(skinId):
    return f"{ANIMATEDSPLASHESURL}/{skinId}.gif"
