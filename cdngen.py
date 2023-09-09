def mapIdimg(mapid: int):
    conv = {
        11: "classic_sru",
        12: "aram",
        22: "tft",
        30: "gamemodex"
	}
    return f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/content/src/leagueclient/gamemodeassets/{conv[mapid]}/img/game-select-icon-active.png"

def skinImg(champId, skinId):
    if skinId / 1000 == champId:
        return f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/{champId}.png"
    return f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-tiles/{champId}/{skinId}.jpg"

def splashLink(champId, skinId):
    return f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-splashes/{champId}/{skinId}.jpg"

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
        "leagueIcon": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2a/LoL_icon.svg/256px-LoL_icon.svg.png"
    }
    return conv[a]