import sys
import os
import asyncio
import aiohttp
from time import time, sleep
from multiprocessing import Process
from subprocess import Popen, DEVNULL
from json import loads, JSONDecodeError

import nest_asyncio

from pypresence import Presence, exceptions as PyPresenceExceptions
from lcu_driver import Connector

try:
    from .utilities import (
        GITHUBURL, CLIENTID,
        fetchConfig, procPath, addLog, logger,
        register_config_changed_callback, release_lock
    )
    from .cdngen import mapIcon, rankedEmblem, availabilityImg, profileIcon, localeDiscordStrings, localeChatStrings
    from .disabler import disableNativePresence
    import src.tray_icon as tray_module
    from .modes import updateInProgressRPC
    from .lcu import LcuManager
    from . import gui as gui_module
    from . import updater 
except ImportError as e:
    print(f"CRITICAL: Failed to import necessary modules in DetailedLoLRPC: {e}")
    sys.exit(1)

import tkinter as tk
from tkinter import messagebox


RIOT_CLIENT_SERVICES_EXECUTABLE = "RiotClientServices.exe"
RIOT_CLIENT_UX_EXECUTABLE = "Riot Client.exe"
LEAGUE_CLIENT_EXECUTABLE = "LeagueClient.exe"
DEFAULT_LOCALE = "en_us"
INITIAL_SUMMONER_FETCH_TIMEOUT = 30  
INITIAL_SUMMONER_FETCH_RETRY_DELAY = 2
IDLE_STATE_CONFIRMATION_DELAY = 1.5
RCS_UX_WAIT_TIMEOUT = 30
LCU_DISCONNECT_SHUTDOWN_DELAY = 10

MAP_ICON_STYLE_TO_ASSET_KEY = {
    "Active": "game-select-icon-active",
    "Empty": "icon-empty",
    "Hover": "game-select-icon-hover",
    "Defeat": "icon-defeat",
    "Background": "gameflow-background"
}
DEFAULT_MAP_ICON_KEY = "game-select-icon-active"


class DetailedLoLRPC:
    def __init__(self):
        try:
            self._main_loop_ref = asyncio.get_event_loop()
        except RuntimeError:
            logger.warning("No running asyncio loop found during DetailedLoLRPC init.")
            self._main_loop_ref = None

        self.rpc = Presence(client_id=CLIENTID, loop=self._main_loop_ref)
        self.connector = Connector(loop=self._main_loop_ref) 
        self.lcu_manager = LcuManager(self.connector)

        self.lcu_connected = False
        self.rpc_connected = False
        self.shutting_down = False
        self.rpc_lock = asyncio.Lock()

        self.summoner_data = {}
        self.locale_strings = {}
        self.current_champ_selection = (0, 0)
        self.ingame_rpc_task = None
        self._delayed_idle_handler_task = None
        self._lcu_disconnect_shutdown_task = None
        self._final_exit_code = 0

        self.config_changed_event = asyncio.Event()
        self._config_watcher_task = None
        self.last_gameflow_event_data = None
        self.last_chat_event_data = None
        self.last_connection_obj_for_refresh = None
        self.current_map_icon_asset_key_name = MAP_ICON_STYLE_TO_ASSET_KEY.get(fetchConfig("mapIconStyle"), DEFAULT_MAP_ICON_KEY)

        self._register_lcu_handlers()
        register_config_changed_callback(self.schedule_presence_refresh)
        logger.info("DetailedLoLRPC initialized.")

    def get_current_app_status_for_gui(self):
        if hasattr(tray_module, '_current_status_text'):
            return tray_module._current_status_text
        return "Status: Unknown"

    async def open_settings_gui(self):
        logger.info("Settings GUI requested.")
        logger.debug("DetailedLoLRPC: open_settings_gui coroutine CALLED.")
        if self.shutting_down:
            logger.warning("DetailedLoLRPC: Attempted to open settings GUI during shutdown. Aborting.")
            return
        try:
            logger.debug("DetailedLoLRPC: Attempting to launch settings GUI...")
            gui_module.launch_settings_gui( 
                current_status_getter=self.get_current_app_status_for_gui,
                rpc_app_ref=self
            )
            logger.debug("DetailedLoLRPC: launch_settings_gui function call COMPLETED (GUI scheduled).")
        except Exception as e:
            logger.error(f"DetailedLoLRPC: Error launching settings GUI: {e}", exc_info=True)
            addLog(f"GUI Error: Failed to launch settings: {str(e)}", level="ERROR")

    def schedule_presence_refresh(self):
        if not self.shutting_down and self._main_loop_ref and self._main_loop_ref.is_running():
            self.config_changed_event.set()
        elif not self.shutting_down :
            logger.warning("Cannot schedule presence refresh: Main loop not available or not running.")

    async def _config_change_listener(self):
        logger.debug("Config change listener started.")
        while not self.shutting_down:
            try:
                await self.config_changed_event.wait()
                if self.shutting_down: break
                self.current_map_icon_asset_key_name = MAP_ICON_STYLE_TO_ASSET_KEY.get(
                    fetchConfig("mapIconStyle"), DEFAULT_MAP_ICON_KEY
                )
                
                # If RPC mute state changed, we might need to clear current presence
                if 'isRpcMuted' in self.config_changed_event._flag_name_for_debug if hasattr(self.config_changed_event, '_flag_name_for_debug') else True: # Heuristic
                    if fetchConfig("isRpcMuted") and self.rpc_connected:
                        logger.info("RPC Mute enabled, clearing presence.")
                        await self._update_rpc_presence(clear=True) # Ensure presence is cleared if muted
                    elif not fetchConfig("isRpcMuted"):
                         logger.info("RPC Unmuted, refreshing presence.")
                         # Refresh will be handled by the create_task below
                
                logger.info(f"Config change detected. Refreshing presence. Muted: {fetchConfig('isRpcMuted')}")
                asyncio.create_task(self.refresh_current_presence())
                self.config_changed_event.clear()
            except asyncio.CancelledError:
                logger.debug("Config change listener task cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in config change listener: {e}", exc_info=True)
                self.config_changed_event.clear()
                await asyncio.sleep(5)
        logger.debug("Config change listener stopped.")

    async def refresh_current_presence(self):
        logger.info("Attempting to refresh current presence...")
        if fetchConfig("isRpcMuted"):
            logger.info("RPC is muted. Clearing presence if connected, otherwise ensuring it stays clear.")
            if self.rpc_connected:
                await self._update_rpc_presence(clear=True)
            return

        if not self.lcu_connected or not self.lcu_manager.current_connection:
            logger.warning("Cannot refresh presence: LCU not connected or no active connection object.")
            await self._update_rpc_presence(clear=True)
            return

        connection = self.lcu_manager.current_connection
        if self.ingame_rpc_task and not self.ingame_rpc_task.done():
            logger.debug("In-game task is active; it will pick up config changes.")
            return

        gameflow_phase_resp = await connection.request('get', '/lol-gameflow/v1/gameflow-phase')
        live_phase_from_http = None
        if gameflow_phase_resp and gameflow_phase_resp.status == 200:
            try:
                live_phase_from_http_raw = await gameflow_phase_resp.json()
                live_phase_from_http = str(live_phase_from_http_raw).strip('"') if isinstance(live_phase_from_http_raw, (str, int, float, bool)) else "Unknown"
            except JSONDecodeError:
                logger.error("Refresh Presence: Error parsing gameflow phase JSON.")
                await self._update_rpc_presence(clear=True); return
        else:
            logger.warning("Refresh Presence: Could not get current gameflow phase. Clearing RPC.")
            await self._update_rpc_presence(clear=True); return
            
        logger.info(f"Refresh Presence: Live phase is '{live_phase_from_http}'.")

        actively_managed_by_gameflow = ("Lobby", "Matchmaking", "ChampSelect", "InProgress")
        idle_or_post_game_phases = ("None", "TerminatedInError", "WaitingForStats", "PreEndOfGame", "EndOfGame")
        
        phase_to_process = live_phase_from_http
        data_for_event = None
        last_event_phase = self.last_gameflow_event_data.get('phase') if self.last_gameflow_event_data else None

        if live_phase_from_http in actively_managed_by_gameflow and last_event_phase in idle_or_post_game_phases:
            logger.warning(f"Refresh Presence: HTTP phase '{live_phase_from_http}' conflicts with last event '{last_event_phase}'. Using last event.")
            phase_to_process = last_event_phase
            data_for_event = self.last_gameflow_event_data
        
        if phase_to_process in actively_managed_by_gameflow:
            if not data_for_event or data_for_event.get('phase') != phase_to_process:
                gameflow_session_resp = await connection.request('get', '/lol-gameflow/v1/session')
                if gameflow_session_resp and gameflow_session_resp.status == 200:
                    try: data_for_event = await gameflow_session_resp.json()
                    except JSONDecodeError: logger.error(f"Refresh: Error parsing session for '{phase_to_process}'."); await self._update_rpc_presence(clear=True); return
                else: logger.warning(f"Refresh: Failed to get session for '{phase_to_process}'."); await self._update_rpc_presence(clear=True); return
            
            if data_for_event: await self.on_gameflow_update(connection, type('Event', (), {'data': data_for_event})())
            else: logger.error(f"Refresh: Data for event '{phase_to_process}' is None."); await self._update_rpc_presence(clear=True)
        
        elif phase_to_process in idle_or_post_game_phases:
            mock_event_data = data_for_event if data_for_event else self.last_gameflow_event_data
            if not mock_event_data or mock_event_data.get('phase') not in idle_or_post_game_phases:
                mock_event_data = {'phase': phase_to_process}
            await self.on_gameflow_update(connection, type('Event', (), {'data': mock_event_data})())
        else:
            logger.info(f"Refresh Presence: Unknown gameflow phase '{phase_to_process}'. No RPC update made.")

        logger.info("Presence refresh attempt complete.")

    def _register_lcu_handlers(self):
        self.connector.ready(self.on_lcu_ready)
        self.connector.close(self.on_lcu_disconnect)
        self.connector.ws.register("/lol-gameflow/v1/session", event_types=("CREATE", "UPDATE", "DELETE"))(self.on_gameflow_update)
        self.connector.ws.register("/lol-chat/v1/me", event_types=("CREATE", "UPDATE", "DELETE"))(self.on_chat_update)
        self.connector.ws.register("/lol-champ-select/v1/session", event_types=("CREATE", "UPDATE"))(self.on_champ_select_update)

    async def _fetch_json_from_url(self, session, url, description="data"):
        try:
            tray_module.updateStatus(f"Status: Fetching {description}...")
            async with session.get(url) as resp:
                resp.raise_for_status()
                try: return await resp.json(encoding='utf-8-sig', content_type=None) 
                except JSONDecodeError as e:
                    logger.error(f"JSONDecodeError fetching {description} from {url}: {e}. Response: {await resp.text()[:200]}")
                    tray_module.updateStatus(f"Status: Error parsing {description}.")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"aiohttp.ClientError fetching {description} from {url}: {e}")
            tray_module.updateStatus(f"Status: Network error fetching {description}.")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in _fetch_json_from_url for {description}: {e}", exc_info=True)
            return None

    async def _initialize_lcu_data(self, connection):
        tray_module.updateStatus("Status: Initializing LCU Data...")
        summoner_data_fetched = False
        fetch_start_time = time()
        while not summoner_data_fetched and not self.shutting_down:
            if time() - fetch_start_time > INITIAL_SUMMONER_FETCH_TIMEOUT:
                logger.error(f"Timeout fetching summoner data after {INITIAL_SUMMONER_FETCH_TIMEOUT}s.")
                return False
            summoner_response = await connection.request('get', '/lol-summoner/v1/current-summoner')
            if summoner_response and summoner_response.status == 200:
                try:
                    self.summoner_data = await summoner_response.json()
                    if self.summoner_data and self.summoner_data.get('summonerId'):
                        logger.info(f"Summoner data fetched: {self.summoner_data.get('displayName')}")
                        summoner_data_fetched = True; break
                    else: logger.warning("Summoner data incomplete. Retrying...")
                except JSONDecodeError: logger.error("Failed to parse summoner data JSON. Retrying...")
            elif summoner_response and summoner_response.status == 404: logger.info("Summoner data not yet available (404). Retrying...")
            else: logger.warning(f"Failed to get summoner (Status: {summoner_response.status if summoner_response else 'N/A'}). Retrying...")
            if not summoner_data_fetched: await asyncio.sleep(INITIAL_SUMMONER_FETCH_RETRY_DELAY)
        if not summoner_data_fetched: logger.error("Could not fetch summoner data."); return False

        region_response = await connection.request('get', '/riotclient/region-locale')
        if region_response and region_response.status == 200:
            try: self.summoner_data['locale'] = (await region_response.json()).get('locale', DEFAULT_LOCALE).lower()
            except JSONDecodeError: logger.error("Failed to parse region/locale JSON."); self.summoner_data['locale'] = DEFAULT_LOCALE
        else: logger.warning(f"Failed to get region/locale. Using fallback."); self.summoner_data['locale'] = DEFAULT_LOCALE
        logger.info(f"Locale set to: {self.summoner_data['locale']}")

        async with aiohttp.ClientSession() as session:
            logger.debug(f"AIOHTTP session for locale strings created: {id(session)}")
            discord_strings = await self._fetch_json_from_url(session, localeDiscordStrings(self.summoner_data['locale']), "Discord strings")
            chat_strings = await self._fetch_json_from_url(session, localeChatStrings(self.summoner_data['locale']), "chat strings")
            
            if not discord_strings or not chat_strings:
                logger.warning("Failed to load locale strings. Using fallbacks.")
                
                def show_locale_fallback_warning_dialog():
                    try:
                        if gui_module._persistent_tk_root and gui_module._persistent_tk_root.winfo_exists():
                            messagebox.showwarning(
                                "Localization Error",
                                "Failed to fetch language files from the server.\n"
                                "The application will use default English text.",
                                parent=gui_module._persistent_tk_root 
                            )
                            logger.info("Locale fallback warning dialog shown.")
                        else:
                            logger.warning("Locale fallback warning dialog could not be shown: persistent Tk root no longer exists or not ready.")
                    except tk.TclError as e_tk: 
                        logger.error(f"TclError showing locale fallback warning: {e_tk}. App might be closing.")
                    except Exception as e_dialog:
                        logger.error(f"Error showing locale fallback warning dialog: {e_dialog}", exc_info=True)

                if gui_module._persistent_tk_root and \
                   hasattr(gui_module._persistent_tk_root, 'winfo_exists') and \
                   gui_module._persistent_tk_root.winfo_exists() and \
                   gui_module._tk_root_ready_event.is_set():
                    try:
                        gui_module._persistent_tk_root.after(0, show_locale_fallback_warning_dialog)
                        logger.info("Scheduled locale fallback warning dialog on GUI thread.")
                    except tk.TclError as e_schedule_tcl:
                         logger.warning(f"Failed to schedule locale fallback warning (Tk root likely destroyed during .after call): {e_schedule_tcl}")
                         logger.info("Proceeding with fallback strings without dialog (GUI thread/root issue).")
                    except Exception as e_schedule:
                         logger.error(f"Unexpected error scheduling locale fallback warning: {e_schedule}", exc_info=True)
                         logger.info("Proceeding with fallback strings without dialog (scheduling issue).")
                else:
                    logger.warning("GUI thread/root not ready or available. Locale fallback warning dialog will not be shown. Proceeding with fallback strings.")

                self.locale_strings = {"bot": "Bot Game", "champSelect": "Champion Select", "lobby": "In Lobby", "inGame": "In Game", "inQueue": "In Queue", "custom": "Custom Game", "practicetool": "Practice Tool", "away": "Away", "chat": "Online", "dnd": "Do Not Disturb"}
            else:
                practicetool_name = "Practice Tool"
                try:
                    map_info_resp = await connection.request('get', '/lol-maps/v2/map/11/PRACTICETOOL')
                    if map_info_resp and map_info_resp.status == 200:
                        api_mode_name = (await map_info_resp.json()).get("gameModeName")
                        if api_mode_name and api_mode_name.strip(): practicetool_name = api_mode_name.strip()
                        else: logger.warning("API returned empty gameModeName for Practice Tool.")
                except Exception as e: logger.warning(f"Could not fetch Practice Tool name: {e}.")
                self.locale_strings = {"bot": discord_strings.get("Disc_Pres_QueueType_BOT", "Bot Game"), "champSelect": discord_strings.get("Disc_Pres_State_championSelect", "Champion Select"), "lobby": discord_strings.get("Disc_Pres_State_hosting", "In Lobby"), "inGame": discord_strings.get("Disc_Pres_State_inGame", "In Game"), "inQueue": discord_strings.get("Disc_Pres_State_inQueue", "In Queue"), "custom": discord_strings.get("Disc_Pres_QueueType_CUSTOM", "Custom Game"), "practicetool": practicetool_name, "away": chat_strings.get("availability_away", "Away"), "chat": chat_strings.get("availability_chat", "Online"), "dnd": chat_strings.get("availability_dnd", "Do Not Disturb")}
        logger.info(f"Locale strings loaded: {len(self.locale_strings)} entries.")
        return True

    async def _update_rpc_presence(self, clear=False, **kwargs):
        async with self.rpc_lock:
            if not self.rpc_connected:
                logger.debug("RPC not connected. Skipping update/clear.")
                return

            is_muted = fetchConfig("isRpcMuted")

            if clear:
                await asyncio.to_thread(self.rpc.clear)
                logger.info("RPC cleared.")
                return

            if is_muted:
                logger.info("RPC is muted. Clearing presence instead of updating.")
                await asyncio.to_thread(self.rpc.clear)
                return
            
            try:
                valid_kwargs = {k: v for k, v in kwargs.items() if v is not None}
                if valid_kwargs:
                    await asyncio.to_thread(self.rpc.update, **valid_kwargs)
                    logger.debug(f"RPC updated: {valid_kwargs.get('details','')}, {valid_kwargs.get('state','')}")
                else:
                    logger.debug("RPC update called with no valid args and not clearing (and not muted).")
            except PyPresenceExceptions.InvalidPipe:
                logger.warning("Discord pipe closed. RPC disconnected.")
                self.rpc_connected = False
                asyncio.create_task(self.connect_discord_rpc(is_reconnect=True))
            except RuntimeError as e:
                logger.error(f"RuntimeError updating RPC: {e}", exc_info="read() called while another coroutine" not in str(e))
            except Exception as e:
                logger.error(f"Error updating RPC: {e}", exc_info=True)


    async def _cancel_task(self, task_attr_name: str, task_description: str):
        task = getattr(self, task_attr_name, None)
        if task and not task.done():
            logger.info(f"Cancelling {task_description} task.")
            task.cancel()
            try: await task
            except asyncio.CancelledError: logger.info(f"{task_description} task successfully cancelled.")
            except Exception as e: logger.error(f"Error during cancellation of {task_description} task: {e}", exc_info=True)
        setattr(self, task_attr_name, None)

    async def _cancel_ingame_task(self): await self._cancel_task('ingame_rpc_task', 'in-game RPC')
    async def _cancel_delayed_idle_task(self): await self._cancel_task('_delayed_idle_handler_task', 'delayed idle handler')
    async def _cancel_lcu_disconnect_shutdown_task(self): await self._cancel_task('_lcu_disconnect_shutdown_task', 'LCU disconnect shutdown')

    async def _handle_delayed_idle_state(self, original_phase_from_event, connection_at_event_time):
        try:
            await asyncio.sleep(IDLE_STATE_CONFIRMATION_DELAY)
            if self.shutting_down or not self.lcu_connected or connection_at_event_time != self.lcu_manager.current_connection: return
            
            if fetchConfig("isRpcMuted"): # Check mute status before proceeding
                logger.info("Delayed idle: RPC is muted. Not setting idle presence.")
                await self._update_rpc_presence(clear=True)
                return

            gameflow_phase_resp = await connection_at_event_time.request('get', '/lol-gameflow/v1/gameflow-phase')
            live_phase_from_http = None
            if gameflow_phase_resp and gameflow_phase_resp.status == 200:
                try: live_phase_from_http = str(await gameflow_phase_resp.json()).strip('"')
                except JSONDecodeError: logger.error("Delayed idle: Error parsing live gameflow phase."); await self._update_rpc_presence(clear=True); return
            
            logger.info(f"Delayed idle: Original '{original_phase_from_event}', Live '{live_phase_from_http}'.")
            idle_or_post_game_trigger_phases = ("None", "TerminatedInError", "WaitingForStats", "PreEndOfGame", "EndOfGame")
            if live_phase_from_http not in idle_or_post_game_trigger_phases: logger.info(f"Delayed idle: Phase changed to '{live_phase_from_http}'. Aborting."); return
            if live_phase_from_http in ("PreEndOfGame", "EndOfGame"): logger.info(f"Delayed idle: Phase '{live_phase_from_http}' is post-game. Clearing RPC."); await self._update_rpc_presence(clear=True); return

            idle_option = fetchConfig("idleStatus")
            if idle_option == 0: logger.info(f"Delayed idle: Disabled for '{live_phase_from_http}'. Clearing RPC."); await self._update_rpc_presence(clear=True); return
            
            chat_me_response = await connection_at_event_time.request('get', '/lol-chat/v1/me')
            if chat_me_response and chat_me_response.status == 200:
                try:
                    chat_data = await chat_me_response.json(); self.last_chat_event_data = chat_data
                    availability = chat_data.get("availability", "chat").lower(); status_message = chat_data.get("statusMessage")
                    rpc_payload_idle = {}
                    if idle_option == 1:
                        profile_display_config = fetchConfig("idleProfileInfoDisplay")
                        large_text_parts = []
                        if profile_display_config.get("showRiotId"):
                            large_text_parts.append(self.summoner_data.get('gameName', 'Player'))
                        if profile_display_config.get("showTagLine") and self.summoner_data.get('tagLine'):
                            if not large_text_parts or not profile_display_config.get("showRiotId"): 
                                large_text_parts.append(f"#{self.summoner_data.get('tagLine')}")
                            else: 
                                large_text_parts[-1] += f"#{self.summoner_data.get('tagLine')}"
                        
                        level_str = f"Lvl {self.summoner_data.get('summonerLevel', 'N/A')}"
                        if profile_display_config.get("showSummonerLevel"):
                            if large_text_parts and (profile_display_config.get("showRiotId") or profile_display_config.get("showTagLine")): 
                                large_text_parts.append("|") 
                            large_text_parts.append(level_str)
                        
                        final_large_text = " ".join(large_text_parts).replace(" | ", "|") 
                        if not final_large_text.strip():
                             final_large_text = "League of Legends"

                        rpc_payload_idle = {
                            "state": self.locale_strings.get(availability, chat_data.get("availability", "Online")), 
                            "large_image": profileIcon(chat_data.get("icon")) if self.summoner_data else availabilityImg("leagueIcon"), 
                            "large_text": final_large_text,
                            "small_image": availabilityImg(availability), 
                            "small_text": status_message if status_message else self.locale_strings.get(availability, chat_data.get("availability", "Online"))
                        }
                    elif idle_option == 2: 
                        rpc_payload_idle = {
                            "large_image": fetchConfig("idleCustomImageLink") or availabilityImg("leagueIcon"), 
                            "large_text": fetchConfig("idleCustomText") or "Idle", 
                            "details": fetchConfig("idleCustomText") or "Chilling...", 
                            "state": None, 
                            "small_image": availabilityImg(availability) if fetchConfig("idleCustomShowStatusCircle") else None, 
                            "small_text": (status_message or self.locale_strings.get(availability, chat_data.get("availability", "Online"))) if fetchConfig("idleCustomShowStatusCircle") else None, 
                            "start": int(time()) if fetchConfig("idleCustomShowTimeElapsed") else None
                        }
                    if rpc_payload_idle: await self._update_rpc_presence(**rpc_payload_idle)
                    else: await self._update_rpc_presence(clear=True)
                except JSONDecodeError: await self._update_rpc_presence(clear=True); logger.error("Delayed idle: Error parsing chat data.")
                except Exception as e_chat: await self._update_rpc_presence(clear=True); logger.error(f"Delayed idle: Error setting idle: {e_chat}")
            else: await self._update_rpc_presence(clear=True)
        except asyncio.CancelledError: logger.info("Delayed idle handler task was cancelled.")
        except Exception as e: logger.error(f"Error in _handle_delayed_idle_state: {e}", exc_info=True); await self._update_rpc_presence(clear=True)
        finally: self._delayed_idle_handler_task = None

    async def _delayed_shutdown_on_lcu_disconnect(self):
        try:
            logger.info(f"LCU disconnected. Starting {LCU_DISCONNECT_SHUTDOWN_DELAY}s timer for app shutdown...")
            await asyncio.sleep(LCU_DISCONNECT_SHUTDOWN_DELAY)
            if self.shutting_down: logger.info("App already shutting down. Delayed LCU disconnect shutdown aborted."); return
            if not self.lcu_connected: logger.info(f"LCU still disconnected after {LCU_DISCONNECT_SHUTDOWN_DELAY}s. Shutting down app."); await self.shutdown(exit_code=0)
            else: logger.info(f"LCU reconnected. Shutdown averted.")
        except asyncio.CancelledError: logger.info("Delayed shutdown task on LCU disconnect cancelled.")
        except Exception as e: logger.error(f"Error in _delayed_shutdown_on_lcu_disconnect: {e}", exc_info=True)
        finally: self._lcu_disconnect_shutdown_task = None

    async def on_lcu_ready(self, connection):
        logger.info("LCU Connected and Ready.")
        print("LCU Connected.")
        await self._cancel_lcu_disconnect_shutdown_task()
        tray_module.updateStatus("Status: LCU Connected. Initializing...")
        self.lcu_connected = True; self.last_connection_obj_for_refresh = connection
        if not await self._initialize_lcu_data(connection):
            tray_module.updateStatus("Status: Failed LCU data init."); logger.error("Failed LCU data init."); self.lcu_connected = False; return
        tray_module.updateStatus("Status: Ready"); logger.info("LCU Ready and Initialized.")
        asyncio.create_task(self.refresh_current_presence())

    async def on_lcu_disconnect(self, connection):
        logger.info(f"LCU Disconnected.")
        print("LCU Disconnected.")
        self.lcu_connected = False; self.last_connection_obj_for_refresh = None
        self.last_gameflow_event_data = None; self.last_chat_event_data = None
        await self._cancel_delayed_idle_task(); await self._cancel_ingame_task()
        await self._update_rpc_presence(clear=True)
        tray_module.updateStatus("Status: LCU Disconnected. App may close soon.")
        await self._cancel_lcu_disconnect_shutdown_task()
        if not self.shutting_down: self._lcu_disconnect_shutdown_task = asyncio.create_task(self._delayed_shutdown_on_lcu_disconnect())

    async def on_gameflow_update(self, connection, event):
        if not self.lcu_connected or not self.locale_strings: logger.debug("Gameflow update skipped, LCU not ready."); return
        
        if fetchConfig("isRpcMuted"):
            logger.info("Gameflow update: RPC is muted. Clearing presence.")
            await self._update_rpc_presence(clear=True)
            return

        data = event.data; self.last_gameflow_event_data = data; self.last_connection_obj_for_refresh = connection
        phase = data.get('phase'); logger.info(f"Gameflow update: Phase - {phase}")
        await self._cancel_delayed_idle_task()
        if phase not in ("InProgress", "PreEndOfGame", "EndOfGame", "WaitingForStats"): await self._cancel_ingame_task()

        actively_managed = ("Lobby", "Matchmaking", "ChampSelect", "InProgress")
        idle_post_game = ("None", "TerminatedInError", "WaitingForStats", "PreEndOfGame", "EndOfGame")

        if phase in actively_managed:
            game_data = data.get('gameData', {}); queue_data = game_data.get('queue', {}); map_data = data.get('map', {})
            map_asset_data = map_data.get("assets")
            map_icon_path = map_asset_data.get(self.current_map_icon_asset_key_name) if map_asset_data else None
            if not map_icon_path and map_asset_data: map_icon_path = map_asset_data.get(DEFAULT_MAP_ICON_KEY)
            if not map_icon_path and phase != "InProgress": logger.debug(f"No map icon for phase {phase}. Map: {map_data.get('name')}")
            
            lobby_members_count = 0
            if phase != "InProgress":
                lobby_resp = await connection.request('get', '/lol-lobby/v2/lobby/members')
                if lobby_resp and lobby_resp.status == 200:
                    try: lobby_members_count = len(await lobby_resp.json())
                    except JSONDecodeError: logger.error("Error parsing lobby members JSON.")
                elif lobby_resp and lobby_resp.status != 404: logger.warning(f"Failed to get lobby members (Status: {lobby_resp.status}).")

            queue_desc = queue_data.get('description', "Unknown Mode")
            if self.locale_strings:
                if queue_data.get("type") == "BOT": queue_desc = f"{self.locale_strings.get('bot', 'Bot')} {queue_desc}"
                if queue_data.get("category") == "Custom": queue_desc = self.locale_strings.get('custom', 'Custom Game')
                if queue_data.get('gameMode') == "PRACTICETOOL": queue_desc = self.locale_strings.get('practicetool', 'Practice Tool')
            
            rank_emblem_url, small_text_str = None, None
            if phase != "InProgress":
                current_queue_type = queue_data.get("type")
                show_ranks_config = fetchConfig("showRanks")
                if current_queue_type and isinstance(show_ranks_config, dict) and show_ranks_config.get(current_queue_type, False):
                    ranked_stats_resp = await connection.request('get', '/lol-ranked/v1/current-ranked-stats')
                    if ranked_stats_resp and ranked_stats_resp.status == 200:
                        try:
                            ranked_stats = await ranked_stats_resp.json()
                            queue_map = ranked_stats.get("queueMap", {})
                            if isinstance(queue_map, dict):
                                queue_rank_info = queue_map.get(current_queue_type)
                                if isinstance(queue_rank_info, dict) and queue_rank_info.get("tier", "") not in ("", "NONE", "UNRANKED"):
                                    tier = queue_rank_info['tier'].capitalize(); division = queue_rank_info['division']
                                    small_text_parts_temp = [f"{tier} {division}"]
                                    rank_emblem_url = rankedEmblem(queue_rank_info['tier'])
                                    ranked_stats_config = fetchConfig("rankedStats")
                                    if isinstance(ranked_stats_config, dict):
                                        if ranked_stats_config.get("lp"): small_text_parts_temp.append(f"{queue_rank_info.get('leaguePoints', 0)} LP")
                                        if ranked_stats_config.get("w"): small_text_parts_temp.append(f"{queue_rank_info.get('wins', 0)}W")
                                        if ranked_stats_config.get("l"): small_text_parts_temp.append(f"{queue_rank_info.get('losses', 0)}L")
                                    small_text_str = " • ".join(small_text_parts_temp)
                        except JSONDecodeError: logger.error("Error parsing ranked stats JSON for gameflow update.")


            rpc_base = {"details": f"{map_data.get('name', 'Unknown Map')} ({queue_desc})", "large_text": map_data.get('name'), "small_image": rank_emblem_url, "small_text": small_text_str, "large_image": mapIcon(map_icon_path) if map_icon_path else None}

            if phase == "Lobby":
                if queue_data.get("mapId") == 0 and not map_data.get('name'): await self._update_rpc_presence(clear=True); return
                tray_module.updateStatus("Status: In Lobby"); rpc_base["state"] = self.locale_strings.get('lobby', 'In Lobby')
                if fetchConfig("showPartyInfo") and queue_data.get("maximumParticipantListSize", 0) > 0: rpc_base["party_size"] = [lobby_members_count, queue_data["maximumParticipantListSize"]]
                await self._update_rpc_presence(**rpc_base)
            elif phase == "Matchmaking":
                tray_module.updateStatus("Status: In Queue"); rpc_base["state"] = self.locale_strings.get('inQueue', 'In Queue'); rpc_base["start"] = int(time())
                await self._update_rpc_presence(**rpc_base)
            elif phase == "ChampSelect":
                tray_module.updateStatus("Status: In Champ Select"); rpc_base["state"] = self.locale_strings.get('champSelect', 'Champion Select')
                await self._update_rpc_presence(**rpc_base)
            elif phase == "InProgress":
                tray_module.updateStatus("Status: In Game"); await self._cancel_ingame_task()
                self.ingame_rpc_task = asyncio.create_task(updateInProgressRPC(lambda: not self.lcu_connected or self.shutting_down, int(time()), self.current_champ_selection, map_data, map_icon_path, queue_data, game_data, self.summoner_data.get('internalName'), self.summoner_data.get('displayName'), connection, self.summoner_data.get('summonerId'), self.locale_strings, self.rpc, self.rpc_lock))
        
        elif phase in idle_post_game:
            logger.info(f"Gameflow phase '{phase}' received. Scheduling delayed idle/clear handler.")
            await self._cancel_ingame_task(); await self._cancel_delayed_idle_task()
            self._delayed_idle_handler_task = asyncio.create_task(self._handle_delayed_idle_state(phase, connection))
        else:
            logger.info(f"Gameflow phase '{phase}' is unknown. No RPC update made.")
        
    async def on_chat_update(self, connection, event):
        if not self.lcu_connected or not self.locale_strings or not self.summoner_data: logger.debug("Chat update skipped, LCU not ready."); return
        
        if fetchConfig("isRpcMuted"):
            logger.info("Chat update: RPC is muted. Clearing presence.")
            await self._update_rpc_presence(clear=True)
            return

        chat_data = event.data; self.last_chat_event_data = chat_data; self.last_connection_obj_for_refresh = connection
        gameflow_phase_resp = await connection.request('get', '/lol-gameflow/v1/gameflow-phase')
        current_gameflow_phase = None
        if gameflow_phase_resp and gameflow_phase_resp.status == 200:
            try: current_gameflow_phase = str(await gameflow_phase_resp.json()).strip('"')
            except JSONDecodeError: logger.error("Error parsing gameflow phase for chat update."); return
        
        active_phases = ("Lobby", "Matchmaking", "ChampSelect", "InProgress", "PreEndOfGame", "EndOfGame")
        if current_gameflow_phase in active_phases: logger.debug(f"Chat update in active phase '{current_gameflow_phase}'. Gameflow handles RPC."); return
        if self._delayed_idle_handler_task and not self._delayed_idle_handler_task.done(): logger.debug("Chat update for idle, but delayed handler pending."); return
        if self.ingame_rpc_task and not self.ingame_rpc_task.done(): logger.debug("Chat update for idle, in-game task running, cancelling."); await self._cancel_ingame_task()

        tray_module.updateStatus("Status: Ready (Idle)")
        availability = chat_data.get("availability", "chat").lower(); status_message = chat_data.get("statusMessage")
        idle_option = fetchConfig("idleStatus"); rpc_payload = {}
        if idle_option == 0: await self._update_rpc_presence(clear=True); logger.info("Idle status: RPC cleared (Disabled)."); return
        elif idle_option == 1: rpc_payload = {"state": self.locale_strings.get(availability, chat_data.get("availability", "Online")), "large_image": profileIcon(chat_data.get("icon")) if self.summoner_data else availabilityImg("leagueIcon"), "large_text": f"{self.summoner_data.get('displayName', 'Player')}#{self.summoner_data.get('tagLine','')} | Lvl {self.summoner_data.get('summonerLevel', 'N/A')}" if self.summoner_data else "League of Legends", "small_image": availabilityImg(availability), "small_text": status_message if status_message else self.locale_strings.get(availability, chat_data.get("availability", "Online"))}
        elif idle_option == 2: rpc_payload = {"large_image": fetchConfig("idleCustomImageLink") or availabilityImg("leagueIcon"), "large_text": fetchConfig("idleCustomText") or "Idle", "details": fetchConfig("idleCustomText") or "Chilling...", "state": None, "small_image": availabilityImg(availability) if fetchConfig("idleCustomShowStatusCircle") else None, "small_text": (status_message or self.locale_strings.get(availability, chat_data.get("availability", "Online"))) if fetchConfig("idleCustomShowStatusCircle") else None, "start": int(time()) if fetchConfig("idleCustomShowTimeElapsed") else None}
        if rpc_payload: await self._update_rpc_presence(**rpc_payload)
        logger.info(f"Chat status updated to: {availability}, idle option: {idle_option}")

    async def on_champ_select_update(self, connection, event):
        if not self.lcu_connected or not self.summoner_data: return
        my_team = event.data.get("myTeam", [])
        for player in my_team:
            if player.get("summonerId") == self.summoner_data.get("summonerId"):
                self.current_champ_selection = (player.get("championId", 0), player.get("selectedSkinId", 0))
                logger.info(f"Champ selection updated: ID {self.current_champ_selection[0]}, Skin {self.current_champ_selection[1]}")
                break

    async def connect_discord_rpc(self, is_reconnect=False):
        async with self.rpc_lock:
            if self.rpc_connected and not is_reconnect: logger.debug("RPC already connected."); return
            status_msg = "Reconnecting to Discord..." if is_reconnect else "Connecting to Discord..."
            logger.info(status_msg); tray_module.updateStatus(f"Status: {status_msg}")
            try:
                await asyncio.to_thread(self.rpc.connect); self.rpc_connected = True
                logger.info("RPC Connected to Discord."); print("RPC Connected to Discord."); tray_module.updateStatus("Status: Connected to Discord.")
                if fetchConfig("isRpcMuted"): # If muted on connect, clear presence
                    logger.info("RPC connected but is muted. Clearing initial presence.")
                    await self._update_rpc_presence(clear=True)
                else: # Refresh presence if not muted
                    asyncio.create_task(self.refresh_current_presence())

            except PyPresenceExceptions.InvalidPipe: logger.warning("Discord pipe closed. Is Discord running?"); tray_module.updateStatus("Status: Discord not found."); self.rpc_connected = False
            except RuntimeError as e: logger.error(f"RuntimeError connecting RPC: {e}", exc_info="event loop is already running" not in str(e)); tray_module.updateStatus("Status: Discord connection error."); self.rpc_connected = False
            except Exception as e: logger.error(f"Error connecting RPC: {e}", exc_info=True); tray_module.updateStatus("Status: Discord connection error."); self.rpc_connected = False

    async def _check_updates(self):
        logger.info("DetailedLoLRPC: Checking for updates via updater module...")
        update_initiated_and_requires_exit = False
        try:
            update_initiated_and_requires_exit = await asyncio.to_thread(
                updater.perform_update,
                show_messagebox_callback=None, 
                rpc_app_ref=self
            )
            
            if update_initiated_and_requires_exit:
                logger.info("DetailedLoLRPC: Update process initiated by updater.perform_update and requires app exit.")
            else:
                logger.info("DetailedLoLRPC: Update check completed. No update applied or no exit required.")

        except Exception as e:
            logger.error(f"DetailedLoLRPC: Error during _check_updates using updater module: {e}", exc_info=True)
        
        return update_initiated_and_requires_exit

    async def _launch_league_if_needed(self):
        if procPath(LEAGUE_CLIENT_EXECUTABLE): logger.debug(f"{LEAGUE_CLIENT_EXECUTABLE} already running."); return True
        tray_module.updateStatus("Status: Starting League..."); logger.info("League not detected. Launching...")
        try:
            riot_path = fetchConfig("riotPath")
            if not riot_path or not os.path.isdir(riot_path): logger.error(f"Invalid Riot path: '{riot_path}'."); tray_module.updateStatus("Status: Invalid Riot Path."); return False
            rcs_exe = os.path.join(riot_path, "Riot Client", RIOT_CLIENT_SERVICES_EXECUTABLE)
            if not os.path.exists(rcs_exe): rcs_exe = os.path.join(riot_path, RIOT_CLIENT_SERVICES_EXECUTABLE)
            if not os.path.exists(rcs_exe): logger.error(f"{RIOT_CLIENT_SERVICES_EXECUTABLE} not found from '{riot_path}'."); tray_module.updateStatus(f"Status: {RIOT_CLIENT_SERVICES_EXECUTABLE} not found."); return False

            logger.info(f"Launch Step 1: Running {RIOT_CLIENT_SERVICES_EXECUTABLE} (no args).")
            Popen([rcs_exe], stdout=DEVNULL, stderr=DEVNULL, stdin=DEVNULL, shell=False)
            
            logger.info(f"Launch Step 2: Waiting for {RIOT_CLIENT_UX_EXECUTABLE}...")
            rcs_ux_running = False; wait_start = time()
            while time() - wait_start < RCS_UX_WAIT_TIMEOUT:
                if procPath(RIOT_CLIENT_UX_EXECUTABLE): logger.info(f"{RIOT_CLIENT_UX_EXECUTABLE} detected."); rcs_ux_running = True; break
                await asyncio.sleep(1)
            if not rcs_ux_running: logger.warning(f"{RIOT_CLIENT_UX_EXECUTABLE} not detected after {RCS_UX_WAIT_TIMEOUT}s. Proceeding anyway.")
            
            logger.info("Launch Step 3: Waiting 1.5s.")
            await asyncio.sleep(1.5)
            
            logger.info(f"Launch Step 4: Running {RIOT_CLIENT_SERVICES_EXECUTABLE} with League args.")
            Popen([rcs_exe, '--launch-product=league_of_legends', '--launch-patchline=live'], stdout=DEVNULL, stderr=DEVNULL, stdin=DEVNULL, shell=False)
            logger.info("League launch command issued.")
            return True
        except Exception as e: logger.error(f"Failed to launch League: {e}", exc_info=True); tray_module.updateStatus("Status: Error launching League."); return False

    async def run(self):
        logger.info("DetailedLoLRPC application starting...")
        if fetchConfig("checkForUpdatesOnStartup"):
            if await self._check_updates():
                logger.info("Update found and initiated by startup check. Shutting down for update.")
                await self.shutdown(0)
                return
        
        try: tray_module.icon.run_detached(); logger.info("Tray icon started.")
        except Exception as e: logger.error(f"Failed to start tray icon: {e}", exc_info=True)
        self._config_watcher_task = asyncio.create_task(self._config_change_listener())
        logger.info("Attempting to disable native presence..."); Process(target=disableNativePresence, daemon=True).start()
        await self._launch_league_if_needed()
        await self.connect_discord_rpc()
        logger.info("Starting LCU Manager..."); lcu_manager_task = asyncio.create_task(self.lcu_manager.start())
        try: await lcu_manager_task
        except asyncio.CancelledError: logger.info("Main run task (LCU Manager) cancelled.")
        except Exception as e: logger.critical(f"Unhandled exception awaiting LCU Manager: {e}", exc_info=True); await self.shutdown(1)
        finally:
            logger.info("LCU Manager task ended or was cancelled.")
            if not self.shutting_down:
                if self.lcu_connected: logger.warning("LCU Manager task ended unexpectedly. Shutting down."); await self.shutdown(1)
                elif not self._lcu_disconnect_shutdown_task or self._lcu_disconnect_shutdown_task.done(): logger.info("LCU Manager task ended; LCU not connected, no disconnect shutdown active.")

    async def shutdown(self, exit_code=0):
        if self.shutting_down:
            logger.debug("Shutdown already in progress.")
            return
        self.shutting_down = True
        self._final_exit_code = exit_code 
        logger.info(f"Shutdown initiated (code {exit_code}).")
        print("Shutting down DetailedLoLRPC...")
        tray_module.updateStatus("Status: Shutting down...")

        # tasks_to_cancel = [
        #     self._config_watcher_task,
        #     self._lcu_disconnect_shutdown_task,
        #     self._delayed_idle_handler_task,
        #     self.ingame_rpc_task
        # ]
        # active_tasks_to_cancel = [task for task in tasks_to_cancel if task and not task.done()]

        # if active_tasks_to_cancel:
        #     logger.info(f"Cancelling {len(active_tasks_to_cancel)} application tasks...")
        #     for task in active_tasks_to_cancel:
        #         task.cancel()
        #     try:
        #         await asyncio.gather(*active_tasks_to_cancel, return_exceptions=True)
        #         logger.info("Application tasks cancelled/completed.")
        #     except Exception as e_gather:
        #         logger.error(f"Error during gather of cancelled tasks: {e_gather}", exc_info=True)


        # self._config_watcher_task = None
        # self._lcu_disconnect_shutdown_task = None
        # self._delayed_idle_handler_task = None
        # self.ingame_rpc_task = None

        if hasattr(self, 'lcu_manager') and self.lcu_manager:
            logger.info("Stopping LCU Manager...")
            await self.lcu_manager.stop() 
            logger.info("LCU Manager stopped.")
            
            if hasattr(self.lcu_manager, 'connector') and \
                hasattr(self.lcu_manager.connector, '_session') and \
                self.lcu_manager.connector._session and \
                not self.lcu_manager.connector._session.closed:
                try:
                    logger.info("Explicitly awaiting lcu_driver connector session close...")
                    await self.lcu_manager.connector._session.close()
                    logger.info("lcu_driver connector session explicitly closed.")
                except Exception as e_lcu_close:
                    logger.error(f"Error explicitly closing lcu_driver session: {e_lcu_close}", exc_info=True)
            else:
                logger.info("lcu_driver connector session was already closed or not present.")
        
        if self.rpc_connected:
            logger.info("Closing Discord RPC connection...")
            try:
                async with self.rpc_lock: 
                    await asyncio.to_thread(self.rpc.close)
                logger.info("RPC connection closed.")
            except Exception as e: logger.error(f"Error closing RPC: {e}", exc_info=True)
        self.rpc_connected = False
        self.lcu_connected = False 
        
        release_lock()
        logger.info("Instance lock released.")

        logger.info("DetailedLoLRPC shut down."); tray_module.updateStatus("Status: Offline.")
        if hasattr(tray_module.icon, 'stop'): 
            try:
                logger.debug("Attempting to stop tray icon thread...")
                tray_module.icon.stop()
                logger.info("Tray icon stop signal sent.")
            except Exception as e: logger.warning(f"Exception stopping tray icon: {e}")
        
        logger.info("Final brief sleep for any pending I/O before stopping event loop.")
        await asyncio.sleep(0.75)

        if self._main_loop_ref and self._main_loop_ref.is_running():
            logger.info(f"Stopping main event loop. Program will exit via main.py once loop stops.")
            self._main_loop_ref.stop()
        else:
            logger.warning(f"Main event loop not available or not running during shutdown.")

