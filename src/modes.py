from src.utilities import fetchConfig, ANIMATEDSPLASHESIDS
from src.cdngen import rankedEmblem
from src.gamestats import getStats
from src.cdngen import assetsLink, defaultTileLink, tftImg, mapIcon, animatedSplashUrl
from asyncio import sleep

async def updateInProgressRPC(stopFlag, startTime, currentChamp, mapData, mapIconData, queueData, gameData, internalName, displayName, connection, summonerId, discStrings, RPC):
    while stopFlag["running"]:

        # Get ranks
        rankEmblem = None
        small_text = []
        try:
            if fetchConfig("showRanks")[queueData["type"]]:
                rank = await (await connection.request('get', f'/lol-ranked/v1/current-ranked-stats')).json()
                rank = rank["queueMap"][queueData["type"]]
                if rank["tier"] != "":
                    small_text.append(f"{rank['tier'].capitalize()} {rank['division']}")
                    rankEmblem = rankedEmblem(rank['tier'])
                    if fetchConfig("rankedStats")["lp"]:
                        small_text.append(f"{rank['leaguePoints']} LP")
                    if fetchConfig("rankedStats")["w"]:
                        small_text.append(f"{rank['wins']}W")
                    if fetchConfig("rankedStats")["l"]:
                        small_text.append(f"{rank['losses']}L")
        except KeyError:
            pass

        # TFT
        if mapData["mapStringId"] == "TFT":

            if fetchConfig("useSkinSplash"):
                compData = (await (await connection.request('get', '/lol-cosmetics/v1/inventories/tft/companions')).json())["selectedLoadoutItem"]
                RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
                        large_image = tftImg(compData["loadoutsIcon"]), \
                        large_text = compData['name'], \
                        small_image = rankEmblem, \
                        small_text = " • ".join(small_text) if small_text else None, \
                        state = discStrings["inGame"], \
                        start = startTime, \
                        buttons = ([{"label": "View Splash Art", "url": tftImg(compData["loadoutsIcon"])}] if fetchConfig("showViewArtButton") else None))
            else:
                RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
                        large_image = mapIcon(mapIconData), \
                        large_text = mapData['name'], \
                        small_image = rankEmblem, \
                        small_text = " • ".join(small_text) if small_text else None, \
                        state = discStrings["inGame"], \
                        start = startTime)
        
        # Swarm 2024
        elif mapData["id"] == 33:

            # Swarm 2024 champs
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

            champId = currentChamp[0]

            tileLink = defaultTileLink(champId)
            skinName = (await (await connection.request('get', f'/lol-champions/v1/inventories/{summonerId}/champions/{champIdNames[champId]}')).json())["name"]

            RPC.update(details = f"{mapData['name']} (PvE)", \
                    large_image = tileLink, \
                    large_text = skinName, \
                    state = discStrings["inGame"], \
                    start = startTime)
        
        # Others
        else:
            
            champId = currentChamp[0]
            skinId = currentChamp[1] if fetchConfig("useSkinSplash") else champId * 1000

            champSkins = await (await connection.request('get', f'/lol-champions/v1/inventories/{summonerId}/champions/{champId}/skins')).json()

            for champSkin in champSkins:

                _ok = False
            
                for skinTier in champSkin["questSkinInfo"]["tiers"]:
                    if skinTier["id"] == skinId:
                        skinName = skinTier["name"]
                        animatedSplashLink = skinTier["collectionSplashVideoPath"]
                        if skinTier["isBase"]:
                            tileLink = defaultTileLink(champId)
                        else:
                            tileLinkraw = skinTier["tilePath"]
                            tileLink = assetsLink(tileLinkraw)
                        splashLink = assetsLink(skinTier["uncenteredSplashPath"])
                        _ok = True
                        break
                if _ok: break

                if champSkin["id"] == skinId:
                    skinName = champSkin["name"]
                    animatedSplashLink = champSkin["collectionSplashVideoPath"]
                    if champSkin["isBase"]:
                        tileLink = defaultTileLink(champId)
                    else:
                        tileLinkraw = champSkin["tilePath"]
                        tileLink = assetsLink(tileLinkraw)
                    splashLink = assetsLink(champSkin["uncenteredSplashPath"])
                    break

                for chroma in champSkin["chromas"]:
                    if chroma["id"] == skinId:
                        skinName = champSkin["name"]
                        skinId = champSkin["id"]
                        animatedSplashLink = champSkin["collectionSplashVideoPath"]
                        if champSkin["isBase"]:
                            tileLink = defaultTileLink(champId)
                        else:
                            tileLinkraw = champSkin["tilePath"]
                            tileLink = assetsLink(tileLinkraw)
                        splashLink = assetsLink(champSkin["uncenteredSplashPath"])
                        _ok = True
                        break
                if _ok: break

            if animatedSplashLink and skinId in ANIMATEDSPLASHESIDS and fetchConfig("animatedSplash"):
                tileLink = animatedSplashUrl(skinId)
                splashLink = assetsLink(animatedSplashLink)
            
            state = [discStrings["inGame"]]
            stats = getStats()
            options = fetchConfig("stats")
            if options["kda"] and stats["kda"]:
                state.append(stats['kda'])
            if options["cs"] and stats["cs"]:
                state.append(f"{stats['cs']}cs")
            if options["level"] and stats["level"]:
                state.append(f"Lvl {stats['level']}")

            RPC.update(details = f"{mapData['name']} ({queueData['description']})", \
                    large_image = tileLink, \
                    large_text = skinName, \
                    small_image = rankEmblem, \
                    small_text = " • ".join(small_text) if small_text else None, \
                    state = " • ".join(state), \
                    start = startTime, 
                    buttons = ([{"label": "View Splash Art", "url": splashLink}] if fetchConfig("showViewArtButton") else None))
            
        await sleep(0.5)