def mapIdimg(mapid: int):
    conv = {
        11: "classic_sru",
        12: "aram",
        22: "tft"
	}
    return f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/content/src/leagueclient/gamemodeassets/{conv[mapid]}/img/game-select-icon-hover.png"

def skinImg(champId, skinId):
    return f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-tiles/{champId}/{skinId}.jpg"

def localeDiscordStrings(locale):
    return f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/{locale}/v1/discord_strings.json"