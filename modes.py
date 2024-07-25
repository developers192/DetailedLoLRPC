from utilities import fetchConfig
from cdngen import assetsLink, defaultTileLink, tftImg, mapIcon, localeStrawberryStrings
from time import time
from aiohttp import request
from json import loads

async def updateInProgressRPC(locale, mapData, mapIconData, queueData, gameData, internalName, displayName, connection, summonerId, discStrings, RPC):
    # TFT
    if mapData["mapStringId"] == "TFT":
        if fetchConfig("useSkinSplash"):
            compData = (await (await connection.request('get', '/lol-cosmetics/v1/inventories/tft/companions')).json())["selectedLoadoutItem"]
            RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
                    large_image = tftImg(compData["loadoutsIcon"]), \
                    large_text = compData['name'], \
                    state = discStrings["inGame"], \
                    start = time(), \
                    buttons = ([{"label": "View Splash Art", "url": tftImg(compData["loadoutsIcon"])}] if fetchConfig("showViewArtButton") else None))
        else:
            RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
                    large_image = mapIcon(mapIconData), \
                    large_text = mapData['name'], \
                    state = discStrings["inGame"], \
                    start = time())
    
    # Swarm
    elif mapData["id"] == 33:

        champIdNames = {
            3147: 92,
            3151: 222,
            3152: 89,
            3153: 147,
            3156: 233,
            3157: 157,
            3159: 893,
            3678: 420,
            3947: 498
        }

        for summoner in gameData["playerChampionSelections"]:
            if summoner["summonerInternalName"] in (internalName, displayName):
                champId = summoner["championId"]
                break

        tileLink = defaultTileLink(champId)
        skinName = (await (await connection.request('get', f'/lol-champions/v1/inventories/{summonerId}/champions/{champIdNames[champId]}')).json())["name"]

        RPC.update(details = f"{mapData['name']} (PvE)", \
                large_image = tileLink, \
                large_text = skinName, \
                state = discStrings["inGame"], \
                start = time())
	
    # Others
    else:
        for summoner in gameData["playerChampionSelections"]:
            if summoner["summonerInternalName"] in (internalName, displayName):
                champId = summoner["championId"]
                skinId = champId * 1000 
                if fetchConfig("useSkinSplash"):
                    skinId += summoner["selectedSkinIndex"]
                break

        champSkins = await (await connection.request('get', f'/lol-champions/v1/inventories/{summonerId}/champions/{champId}/skins')).json()

        for champSkin in champSkins:
            if champSkin["id"] == skinId:
                skinName = champSkin["name"]
                if champSkin["isBase"]:
                    tileLink = defaultTileLink(champId)
                else:
                    tileLinkraw = champSkin["tilePath"]
                    tileLink = assetsLink(tileLinkraw)
                splashLink = assetsLink(champSkin["uncenteredSplashPath"])
                break

            _ok = False
        
            for skinTier in champSkin["questSkinInfo"]["tiers"]:
                if skinTier["id"] == skinId:
                    skinName = skinTier["name"]
                    if skinTier["isBase"]:
                        tileLink = defaultTileLink(champId)
                    else:
                        tileLinkraw = skinTier["tilePath"]
                        tileLink = assetsLink(tileLinkraw)
                    splashLink = assetsLink(skinTier["uncenteredSplashPath"])
                    _ok = True
                    break
            if _ok: break

            for chroma in champSkin["chromas"]:
                if chroma["id"] == skinId:
                    skinName = champSkin["name"]
                    skinId = champSkin["id"]
                    if champSkin["isBase"]:
                        tileLink = defaultTileLink(champId)
                    else:
                        tileLinkraw = champSkin["tilePath"]
                        tileLink = assetsLink(tileLinkraw)
                    splashLink = assetsLink(champSkin["uncenteredSplashPath"])
                    _ok = True
                    break
            if _ok: break
        
        RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
                large_image = tileLink, \
                large_text = skinName, \
                state = discStrings["inGame"], \
                start = time(), 
                buttons = ([{"label": "View Splash Art", "url": splashLink}] if fetchConfig("showViewArtButton") else None))