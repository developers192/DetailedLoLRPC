import asyncio
import json # For JSONDecodeError
from typing import Dict, Any, Tuple, Callable
from time import time # Import time for actual_game_start_time

from pypresence import exceptions as PyPresenceExceptions # Import for specific exception handling

try:
    from .utilities import (
        fetchConfig, ANIMATEDSPLASHESIDS,
        addLog, logger 
    )
    from .cdngen import (
        rankedEmblem, assetsLink, defaultTileLink,
        tftImg, mapIcon, animatedSplashUrl
    )
    from .gamestats import getStats, API_NOT_READY_MARKER, get_current_game_time, get_active_player_champion_data
except ImportError as e:
    print(f"Critical Error: Failed to import modules in modes.py: {e}")
    raise 

async def _fetch_lcu_data(connection: Any, endpoint: str, description: str) -> Dict[str, Any] | None:
    try:
        response = await connection.request('get', endpoint)
        if response and response.status == 200:
            try:
                return await response.json()
            except json.JSONDecodeError as e:
                logger.error(f"JSONDecodeError fetching {description} from {endpoint}: {e}. Response text: {await response.text()[:200]}")
                addLog(f"LCU API Error: Failed to parse JSON for {description} from {endpoint}.", level="ERROR")
                return None
        else:
            status = response.status if response else "No Response"
            logger.warning(f"Failed to fetch {description} from {endpoint}. Status: {status}")
            addLog(f"LCU API Warning: Failed to fetch {description}. Status: {status}", level="WARNING")
            return None
    except Exception as e: 
        logger.error(f"Exception fetching {description} from {endpoint}: {e}", exc_info=True)
        addLog(f"LCU API Error: Exception fetching {description}: {str(e)}", level="ERROR")
        return None


async def updateInProgressRPC(
    stop_condition_callable: Callable[[], bool],
    start_time: float, 
    current_champ_selection: Tuple[int, int], 
    map_data: Dict[str, Any],
    map_icon_asset_path: str | None, 
    queue_data: Dict[str, Any],
    game_data: Dict[str, Any], 
    internal_name: str, 
    display_name: str, 
    connection: Any, 
    summoner_id: int,
    locale_strings: Dict[str, str],
    rpc_presence_object: Any, 
    rpc_lock: asyncio.Lock 
):
    logger.info(f"In-progress RPC update loop started for {display_name} at {start_time}.")
    addLog(f"In-progress RPC loop started for {display_name}.", level="DEBUG")

    champ_id, selected_skin_id = current_champ_selection
    
    if not champ_id and map_data.get("mapStringId") != "TFT": 
        logger.error("updateInProgressRPC: No champion ID for non-TFT mode. Exiting loop.")
        addLog("Error: In-progress RPC: No champion ID for non-TFT mode.", level="ERROR")
        return

    while not stop_condition_callable():
        if fetchConfig("isRpcMuted"):
            logger.info(f"In-progress RPC: Muted. Clearing presence for {display_name}.")
            async with rpc_lock:
                try:
                    await asyncio.to_thread(rpc_presence_object.clear)
                except PyPresenceExceptions.InvalidPipe:
                    logger.warning("In-progress RPC (Muted): InvalidPipe during clear. Main app should handle reconnect.")
                    # The main DetailedLoLRPC._update_rpc_presence will handle setting rpc_connected to False
                except Exception as e_clear_mute:
                    logger.error(f"In-progress RPC (Muted): Error during clear: {e_clear_mute}")
            await asyncio.sleep(1.0) 
            continue

        rpc_payload = {}
        
        map_name_str = map_data.get('name', "Unknown Map")
        queue_desc_str = queue_data.get('description', "Unknown Mode")
        if queue_data.get('gameMode') == "PRACTICETOOL":
            queue_desc_str = locale_strings.get('practicetool', 'Practice Tool')
        elif queue_data.get("type") == "BOT":
            queue_desc_str = f"{locale_strings.get('bot', 'Bot')} {queue_desc_str}"
        elif queue_data.get("category") == "Custom" and queue_data.get('gameMode') != "PRACTICETOOL":
            queue_desc_str = locale_strings.get('custom', 'Custom Game')
        
        details_for_rpc = f"{map_name_str} ({queue_desc_str})"
        large_image_for_rpc = mapIcon(map_icon_asset_path) if map_icon_asset_path else "lol_icon"
        large_text_for_rpc = map_name_str
        
        live_game_stats_data = await asyncio.to_thread(getStats)
        current_game_time_from_api = await asyncio.to_thread(get_current_game_time)

        rpc_start_timestamp_to_use = int(start_time) 

        # Loading RPC
        if current_game_time_from_api == API_NOT_READY_MARKER or live_game_stats_data == API_NOT_READY_MARKER:
            rpc_payload = {
                "details": details_for_rpc, 
                "state": "Loading Match...", 
                "large_image": large_image_for_rpc,
                "large_text": large_text_for_rpc,
                "start": int(start_time), 
            }
        elif isinstance(current_game_time_from_api, float):
            rpc_start_timestamp_to_use = int(time() - current_game_time_from_api)
            logger.debug(f"Game time from API: {current_game_time_from_api:.2f}s. Calculated RPC start: {rpc_start_timestamp_to_use}")
            
            state_str = locale_strings.get("inGame", "In Game")
            game_stats_parts = [state_str] 
            
            # TFT
            if map_data.get("mapStringId") == "TFT":
                large_image_key_tft = large_image_for_rpc 
                large_text_tft = large_text_for_rpc
                buttons_list_tft = None
                if fetchConfig("useSkinSplash"):
                    cosmetics_data = await _fetch_lcu_data(connection, '/lol-cosmetics/v1/inventories/tft/companions', "TFT companion cosmetics")
                    if cosmetics_data:
                        comp_data = cosmetics_data.get("selectedLoadoutItem")
                        if comp_data and isinstance(comp_data, dict):
                            large_image_key_tft = tftImg(comp_data.get("loadoutsIcon")) 
                            large_text_tft = comp_data.get('name', map_name_str)
                            if fetchConfig("showViewArtButton") and comp_data.get("loadoutsIcon"):
                                buttons_list_tft = [{"label": "View Companion Art", "url": tftImg(comp_data.get("loadoutsIcon"))}]
                rpc_payload = {"details": details_for_rpc, "large_image": large_image_key_tft, "large_text": large_text_tft, "state": " • ".join(game_stats_parts), "start": rpc_start_timestamp_to_use, "buttons": buttons_list_tft}
            
            # Swarm
            elif map_data.get("id") == 33: 
                if not champ_id: actual_champ_id_for_name = 0; champ_name_for_display = "Swarm Survivor"
                else:
                    swarm_champ_map = {3147: 92, 3151: 222, 3152: 89, 3153: 147, 3156: 233, 3157: 157, 3159: 893, 3678: 420, 3947: 498}
                    actual_champ_id_for_name = swarm_champ_map.get(champ_id, champ_id) 
                    champ_name_for_display = "Champion" 
                    if actual_champ_id_for_name:
                        champ_details = await _fetch_lcu_data(connection, f'/lol-champions/v1/inventories/{summoner_id}/champions/{actual_champ_id_for_name}', "Swarm champion details")
                        if champ_details: champ_name_for_display = champ_details.get("name", "Champion")
                rpc_payload = {"details": f"{map_name_str} (PvE)", "large_image": defaultTileLink(actual_champ_id_for_name or champ_id), "large_text": champ_name_for_display, "state": " • ".join(game_stats_parts), "start": rpc_start_timestamp_to_use}
            
            # Arena
            elif map_data.get("gameMode") == "CHERRY":
                if live_game_stats_data and live_game_stats_data.get("kda") is not None: 
                    stats_display_config = fetchConfig("stats")
                    if isinstance(stats_display_config, dict):
                        if stats_display_config.get("kda") and live_game_stats_data.get("kda"):
                            game_stats_parts.append(live_game_stats_data['kda'])
                        if stats_display_config.get("level") and live_game_stats_data.get("level"):
                            game_stats_parts.append(f"Lvl {live_game_stats_data['level']}")

                if not champ_id: rpc_payload = { "details": details_for_rpc, "state": "In Game", "large_image": large_image_for_rpc, "start": rpc_start_timestamp_to_use }; logger.error("Standard game mode but champ_id is 0.")
                else:
                    skin_name_str = "Champion"; tile_image_key = defaultTileLink(champ_id); splash_art_url = None
                    actual_champ_id, actual_champ_skin_id = champ_id, selected_skin_id
                    
                    # Bravery
                    if champ_id == -3: 
                        actual_champ_data = await asyncio.to_thread(get_active_player_champion_data)
                        if actual_champ_data == API_NOT_READY_MARKER or actual_champ_data == (None, None):
                            logger.error("Bravery: Failed to fetch active player champion data.")                   
                        else:
                            actual_champ_name, actual_champ_skin_id = actual_champ_data

                            champ_list = await _fetch_lcu_data(connection, f'/lol-champions/v1/inventories/{summoner_id}/champions', "Bravery champion list")
                            if champ_list and isinstance(champ_list, list):
                                for champ_data in champ_list:
                                    if isinstance(champ_data, dict) and champ_data.get("name") == actual_champ_name:
                                        actual_champ_id = champ_data.get("id")
                                        actual_champ_skin_id = (actual_champ_id * 1000 + actual_champ_skin_id) if actual_champ_skin_id else actual_champ_id * 1000
                                        champ_skins_list = champ_data.get("skins", [])
                                        break                                                               
                    else:
                        champ_skins_list = await _fetch_lcu_data(connection, f'/lol-champions/v1/inventories/{summoner_id}/champions/{champ_id}/skins', "champion skins")

                    target_skin_id_to_use = actual_champ_skin_id if fetchConfig("useSkinSplash") else (actual_champ_id * 1000); found_skin_info = None
                    if champ_skins_list and isinstance(champ_skins_list, list):
                        for skin_info_iter in champ_skins_list:
                            if not isinstance(skin_info_iter, dict): continue
                            if skin_info_iter.get("id") == target_skin_id_to_use: found_skin_info = skin_info_iter; break
                            for chroma_info in skin_info_iter.get("chromas", []):
                                if isinstance(chroma_info, dict) and chroma_info.get("id") == target_skin_id_to_use: found_skin_info = skin_info_iter; break
                            if found_skin_info: break
                            for tier_info in skin_info_iter.get("questSkinInfo", {}).get("tiers", []):
                                if isinstance(tier_info, dict) and tier_info.get("id") == target_skin_id_to_use: found_skin_info = {**skin_info_iter, **tier_info}; break
                            if found_skin_info: break
                        if not found_skin_info:
                            for skin_info_iter in champ_skins_list: 
                                if isinstance(skin_info_iter, dict) and skin_info_iter.get("isBase"): found_skin_info = skin_info_iter; target_skin_id_to_use = skin_info_iter.get("id"); break
                        if not found_skin_info and champ_skins_list: found_skin_info = champ_skins_list[0] if isinstance(champ_skins_list[0], dict) else None; 
                        if found_skin_info: target_skin_id_to_use = found_skin_info.get("id")
                        
                        if found_skin_info and isinstance(found_skin_info, dict):
                            skin_name_str = found_skin_info.get("name", "Champion")
                            if found_skin_info.get("isBase"): tile_image_key = defaultTileLink(actual_champ_id)
                            elif found_skin_info.get("tilePath"): tile_image_key = assetsLink(found_skin_info["tilePath"])
                            if found_skin_info.get("uncenteredSplashPath"): splash_art_url = assetsLink(found_skin_info["uncenteredSplashPath"])
                            animated_video_path = found_skin_info.get("collectionSplashVideoPath")
                            current_skin_id_for_anim_check = target_skin_id_to_use if target_skin_id_to_use is not None else actual_champ_id * 1000
                            if animated_video_path and current_skin_id_for_anim_check in ANIMATEDSPLASHESIDS and fetchConfig("animatedSplash"):
                                tile_image_key = animatedSplashUrl(current_skin_id_for_anim_check)
                                if not splash_art_url and animated_video_path: splash_art_url = assetsLink(animated_video_path)
                    buttons_list = [{"label": "View Splash Art", "url": splash_art_url}] if fetchConfig("showViewArtButton") and splash_art_url else None
                    rpc_payload = {"details": details_for_rpc, "large_image": tile_image_key, "large_text": skin_name_str, "state": " • ".join(game_stats_parts), "start": rpc_start_timestamp_to_use, "buttons": buttons_list}

            # Standard game modes
            else:
                if live_game_stats_data and live_game_stats_data.get("kda") is not None: 
                    stats_display_config = fetchConfig("stats")
                    if isinstance(stats_display_config, dict):
                        if stats_display_config.get("kda") and live_game_stats_data.get("kda"):
                            game_stats_parts.append(live_game_stats_data['kda'])
                        if stats_display_config.get("cs") and live_game_stats_data.get("cs"):
                            game_stats_parts.append(f"{live_game_stats_data['cs']} CS")
                        if stats_display_config.get("level") and live_game_stats_data.get("level"):
                            game_stats_parts.append(f"Lvl {live_game_stats_data['level']}")
                            
                if not champ_id: rpc_payload = { "details": details_for_rpc, "state": "In Game", "large_image": large_image_for_rpc, "start": rpc_start_timestamp_to_use }; logger.error("Standard game mode but champ_id is 0.")
                else:
                    skin_name_str = "Champion"; tile_image_key = defaultTileLink(champ_id); splash_art_url = None
                    champ_skins_list = await _fetch_lcu_data(connection, f'/lol-champions/v1/inventories/{summoner_id}/champions/{champ_id}/skins', "champion skins")
                    target_skin_id_to_use = selected_skin_id if fetchConfig("useSkinSplash") else (champ_id * 1000); found_skin_info = None
                    if champ_skins_list and isinstance(champ_skins_list, list):
                        for skin_info_iter in champ_skins_list:
                            if not isinstance(skin_info_iter, dict): continue
                            if skin_info_iter.get("id") == target_skin_id_to_use: found_skin_info = skin_info_iter; break
                            for chroma_info in skin_info_iter.get("chromas", []):
                                if isinstance(chroma_info, dict) and chroma_info.get("id") == target_skin_id_to_use: found_skin_info = skin_info_iter; break
                            if found_skin_info: break
                            for tier_info in skin_info_iter.get("questSkinInfo", {}).get("tiers", []):
                                if isinstance(tier_info, dict) and tier_info.get("id") == target_skin_id_to_use: found_skin_info = {**skin_info_iter, **tier_info}; break
                            if found_skin_info: break
                        if not found_skin_info:
                            for skin_info_iter in champ_skins_list: 
                                if isinstance(skin_info_iter, dict) and skin_info_iter.get("isBase"): found_skin_info = skin_info_iter; target_skin_id_to_use = skin_info_iter.get("id"); break
                        if not found_skin_info and champ_skins_list: found_skin_info = champ_skins_list[0] if isinstance(champ_skins_list[0], dict) else None; 
                        if found_skin_info: target_skin_id_to_use = found_skin_info.get("id")
                        
                        if found_skin_info and isinstance(found_skin_info, dict):
                            skin_name_str = found_skin_info.get("name", "Champion")
                            if found_skin_info.get("isBase"): tile_image_key = defaultTileLink(champ_id)
                            elif found_skin_info.get("tilePath"): tile_image_key = assetsLink(found_skin_info["tilePath"])
                            if found_skin_info.get("uncenteredSplashPath"): splash_art_url = assetsLink(found_skin_info["uncenteredSplashPath"])
                            animated_video_path = found_skin_info.get("collectionSplashVideoPath")
                            current_skin_id_for_anim_check = target_skin_id_to_use if target_skin_id_to_use is not None else champ_id * 1000
                            if animated_video_path and current_skin_id_for_anim_check in ANIMATEDSPLASHESIDS and fetchConfig("animatedSplash"):
                                tile_image_key = animatedSplashUrl(current_skin_id_for_anim_check)
                                if not splash_art_url and animated_video_path: splash_art_url = assetsLink(animated_video_path)
                    buttons_list = [{"label": "View Splash Art", "url": splash_art_url}] if fetchConfig("showViewArtButton") and splash_art_url else None
                    rpc_payload = {"details": details_for_rpc, "large_image": tile_image_key, "large_text": skin_name_str, "state": " • ".join(game_stats_parts), "start": rpc_start_timestamp_to_use, "buttons": buttons_list}
        else:
            logger.warning(f"Game loaded for {display_name}, but current game time from API is unavailable ({current_game_time_from_api}). Using initial start time for timer.")
            rpc_start_timestamp_to_use = int(start_time) 
            state_str = locale_strings.get("inGame", "In Game")
            game_stats_parts = [state_str] 
            if live_game_stats_data and live_game_stats_data != API_NOT_READY_MARKER and live_game_stats_data.get("kda") is not None:
                stats_display_config = fetchConfig("stats")
                if isinstance(stats_display_config, dict):
                    if stats_display_config.get("kda") and live_game_stats_data.get("kda"): game_stats_parts.append(live_game_stats_data['kda'])
                    if stats_display_config.get("cs") and live_game_stats_data.get("cs"): game_stats_parts.append(f"{live_game_stats_data['cs']} CS")
                    if stats_display_config.get("level") and live_game_stats_data.get("level"): game_stats_parts.append(f"Lvl {live_game_stats_data['level']}")
            
            rpc_payload = {
                "details": details_for_rpc,
                "state": " • ".join(game_stats_parts),
                "large_image": large_image_for_rpc, 
                "large_text": large_text_for_rpc,   
                "start": rpc_start_timestamp_to_use,
            }
        
        final_rpc_payload = {k: v for k, v in rpc_payload.items() if v is not None}
        
        if final_rpc_payload:
            async with rpc_lock:
                try:
                    # Removed the "if rpc_presence_object.pipe:" check here
                    result = await asyncio.to_thread(rpc_presence_object.update, **final_rpc_payload)
                    if result is not None:
                        logger.debug(f"In-Game RPC updated (payload sent): {final_rpc_payload.get('details')}, {final_rpc_payload.get('state')}")
                    else:
                        logger.warning(f"In-Game RPC update: pypresence.update returned None. This might indicate a problem with the send operation even if pipe was thought to be active.")
                        # DetailedLoLRPC._update_rpc_presence will handle setting rpc_connected to False if pipe is truly dead
                except PyPresenceExceptions.InvalidPipe:
                    logger.error("In-Game RPC update: InvalidPipe exception during rpc.update call. Main app should handle reconnect.")
                    # DetailedLoLRPC._update_rpc_presence will handle setting rpc_connected to False
                except Exception as e_update:
                    logger.error(f"In-Game RPC update: Exception during rpc.update: {e_update}", exc_info=True)
        elif rpc_payload: 
            logger.debug("In-Game RPC: Payload was empty after filtering Nones. Clearing RPC.")
            async with rpc_lock:
                try:
                    await asyncio.to_thread(rpc_presence_object.clear)
                except PyPresenceExceptions.InvalidPipe:
                     logger.warning("In-Game RPC (Clear): InvalidPipe during clear. Main app should handle reconnect.")
                except Exception as e_clear:
                    logger.error(f"In-Game RPC (Clear): Error during clear: {e_clear}")
        else: 
            logger.warning("In-Game RPC: Payload was not constructed. No update/clear attempted.")

        await asyncio.sleep(1.0) 

    logger.info(f"In-progress RPC update loop stopped for {display_name}.")
    addLog(f"In-progress RPC loop stopped for {display_name}.", level="INFO")

