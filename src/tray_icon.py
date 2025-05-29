import sys
import os
import webbrowser
import warnings
import asyncio 

from PIL import Image, UnidentifiedImageError
from pystray import Icon, Menu, MenuItem

from .utilities import (
    editConfig, fetchConfig, resourcePath, resetConfig,
    ISSUESURL, LOG_FILE_PATH,
    VERSION, addLog, logger
)

_current_status_text = "Status: Initializing..."
_tray_icon_instance = None
_rpc_app_ref = None 
_settings_gui_is_open = False 

def setup_rpc_app_reference(app_instance):
    global _rpc_app_ref
    _rpc_app_ref = app_instance
    if logger: logger.info("rpc_app_reference set in tray_icon module.")

def disable_tray_menu():
    global _settings_gui_is_open, _tray_icon_instance
    if logger: logger.info("Tray: Attempting to disable menu (GUI open).")
    _settings_gui_is_open = True
    if _tray_icon_instance:
        try:
            _tray_icon_instance.menu = get_menu() 
            _tray_icon_instance.update_menu() 
            if logger: logger.info("Tray: Menu reassigned and update called by disable_tray_menu.")
        except Exception as e:
            if logger: logger.error(f"Tray: Error reassigning/updating menu for disable: {e}", exc_info=True)
    elif not _tray_icon_instance:
        if logger: logger.warning("Tray: disable_tray_menu called but _tray_icon_instance is None.")


def enable_tray_menu():
    global _settings_gui_is_open, _tray_icon_instance
    if logger: logger.info("Tray: Attempting to enable menu (GUI closed).")
    _settings_gui_is_open = False
    if _tray_icon_instance:
        try:
            _tray_icon_instance.menu = get_menu()
            _tray_icon_instance.update_menu() 
            if logger: logger.info("Tray: Menu reassigned and update called by enable_tray_menu.")
        except Exception as e:
            if logger: logger.error(f"Tray: Error reassigning/updating menu for enable: {e}", exc_info=True)
    elif not _tray_icon_instance:
        if logger: logger.warning("Tray: enable_tray_menu called but _tray_icon_instance is None.")

try:
    icon_image_path = resourcePath("icon.ico")
    if not os.path.exists(icon_image_path):
        if logger: logger.error(f"Tray icon resource 'icon.ico' not found at {icon_image_path}.")
        img = Image.new('RGBA', (1, 1), (0,0,0,0)) 
    else:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Image was not the expected size",
                category=UserWarning,
                module='PIL.IcoImagePlugin' 
            )
            img = Image.open(icon_image_path)
            if logger: logger.debug(f"Loaded icon from {icon_image_path}")

except UnidentifiedImageError:
    if logger: logger.error(f"Could not identify or open image file at {icon_image_path}. Using a dummy icon.")
    img = Image.new('RGBA', (1, 1), (0,0,0,0)) 
except FileNotFoundError:
    if logger: logger.error(f"Icon file 'icon.ico' not found via resourcePath. Path: {icon_image_path}. Using a dummy icon.")
    img = Image.new('RGBA', (1, 1), (0,0,0,0)) 
except Exception as e:
    if logger: logger.error(f"An unexpected error occurred while loading tray icon: {e}. Using a dummy icon.")
    img = Image.new('RGBA', (1, 1), (0,0,0,0)) 


def _toggle_config_boolean(config_key):
    current_state = fetchConfig(config_key)
    new_state = not current_state
    editConfig(config_key, new_state) 

def _toggle_nested_config_boolean(main_key, sub_key):
    config_dict = fetchConfig(main_key)
    if isinstance(config_dict, dict): 
        current_sub_state = config_dict.get(sub_key, False) 
        new_config_dict_val = config_dict.copy() 
        new_config_dict_val[sub_key] = not current_sub_state
        editConfig(main_key, new_config_dict_val) 
    else:
        if logger: logger.error(f"Config key '{main_key}' is not a dictionary. Cannot toggle '{sub_key}'. Current value: {config_dict}")


def on_exit_clicked(icon_instance_param, item): 
    if logger: logger.info("Exit requested from tray icon.")
    addLog("Tray icon: Exit action initiated.", level="INFO")
    
    if icon_instance_param: 
        if logger: logger.debug("Tray: Stopping pystray icon instance.")
        icon_instance_param.stop() 
        if logger: logger.debug("Tray: pystray icon instance stopped.")

    if _rpc_app_ref and hasattr(_rpc_app_ref, 'shutdown') and hasattr(_rpc_app_ref, '_main_loop_ref'):
        main_app_loop = getattr(_rpc_app_ref, '_main_loop_ref', None)
        if main_app_loop and main_app_loop.is_running():
            if logger: logger.info("Tray: Scheduling graceful shutdown of main application on its event loop.")
            asyncio.run_coroutine_threadsafe(_rpc_app_ref.shutdown(exit_code=0), main_app_loop)
            if logger: logger.info("Tray: Main application shutdown scheduled.")
        else:
            logger.warning("Tray: Main app loop not available or not running for graceful shutdown. This might lead to an unclean exit.")
    else:
        logger.warning("Tray: _rpc_app_ref or its shutdown method/main_loop_ref not available for graceful shutdown.")
    

def on_skin_splash_clicked(icon_instance, item):
    _toggle_config_boolean("useSkinSplash")

def on_view_splash_art_clicked(icon_instance, item):
    _toggle_config_boolean("showViewArtButton")

def on_animated_splash_clicked(icon_instance, item):
    _toggle_config_boolean("animatedSplash")

def on_show_party_info_clicked(icon_instance, item):
    _toggle_config_boolean("showPartyInfo")

def on_idle_status_selected(icon_instance, item_text):
    status_map = {"Disabled": 0, "Profile Info": 1, "Custom": 2} 
    selected_value = status_map.get(str(item_text))
    if selected_value is not None:
        editConfig("idleStatus", selected_value) 
    else:
        if logger: logger.warning(f"Unknown idle status selection: {item_text}")

def on_report_bug_clicked(icon_instance, item):
    if logger: logger.info("Report bug action initiated.")
    try:
        webbrowser.open(ISSUESURL) 
        log_dir = os.path.dirname(LOG_FILE_PATH) 
        if os.path.exists(log_dir):
            if sys.platform == "win32": os.startfile(log_dir)
            elif sys.platform == "darwin": os.system(f'open "{log_dir}"') 
            else: os.system(f'xdg-open "{log_dir}"') 
        else:
            if logger: logger.error(f"Log directory {log_dir} not found.")
    except Exception as e:
        if logger: logger.error(f"Error in on_report_bug_clicked: {e}")

def on_reset_config_clicked(icon_instance, item):
    if logger: logger.info("Reset preferences action initiated from tray.")
    addLog("Tray icon: Reset preferences action initiated.", level="INFO")
    resetConfig() 
    if logger: logger.info("Preferences have been reset via tray menu (refresh should be triggered by callback in utilities).")

def on_mute_rpc_clicked(icon_instance, item):
    _toggle_config_boolean("isRpcMuted")

def on_open_settings_clicked(icon_instance=None, item=None): 
    global _settings_gui_is_open
    if logger: logger.info("Tray Icon: Open Settings action triggered.")
    
    if _settings_gui_is_open: 
        if logger: logger.info("Tray Icon: Settings GUI is already considered open by the flag. No new action taken to open.")
        if _rpc_app_ref and hasattr(_rpc_app_ref, 'focus_settings_gui') and callable(_rpc_app_ref.focus_settings_gui):
            asyncio.run_coroutine_threadsafe(_rpc_app_ref.focus_settings_gui(), _rpc_app_ref._main_loop_ref)
        return

    if not _rpc_app_ref:
        if logger: logger.error("Tray Icon: Cannot open settings - _rpc_app_ref is not set.")
        return

    if not hasattr(_rpc_app_ref, 'open_settings_gui') or not callable(_rpc_app_ref.open_settings_gui):
        if logger: logger.error("Tray Icon: Cannot open settings - open_settings_gui method is missing or not callable on _rpc_app_ref.")
        return

    if not hasattr(_rpc_app_ref, '_main_loop_ref') or _rpc_app_ref._main_loop_ref is None:
        if logger: logger.error("Tray Icon: Cannot open settings - _main_loop_ref is missing, not set, or None on _rpc_app_ref.")
        return

    main_app_loop = _rpc_app_ref._main_loop_ref
    if not main_app_loop.is_running():
        if logger: logger.error("Tray Icon: Cannot open settings - Main application event loop is not running.")
        return

    if logger: logger.debug("Tray Icon: All checks passed. Scheduling settings GUI launch on main event loop.")

    try:
        future = asyncio.run_coroutine_threadsafe(_rpc_app_ref.open_settings_gui(), main_app_loop)
        if logger: logger.info("Tray Icon: Settings GUI launch successfully scheduled.")
    except Exception as e:
        if logger: logger.error(f"Tray Icon: Error scheduling open_settings_gui: {e}", exc_info=True)


def on_kda_clicked(icon_instance, item): _toggle_nested_config_boolean("stats", "kda")
def on_cs_clicked(icon_instance, item): _toggle_nested_config_boolean("stats", "cs")
def on_level_clicked(icon_instance, item): _toggle_nested_config_boolean("stats", "level")

def on_rank_solo_clicked(icon_instance, item): _toggle_nested_config_boolean("showRanks", "RANKED_SOLO_5x5")
def on_rank_flex_clicked(icon_instance, item): _toggle_nested_config_boolean("showRanks", "RANKED_FLEX_SR")
def on_rank_tft_clicked(icon_instance, item): _toggle_nested_config_boolean("showRanks", "RANKED_TFT")
def on_rank_double_up_clicked(icon_instance, item): _toggle_nested_config_boolean("showRanks", "RANKED_TFT_DOUBLE_UP")

def on_rank_stats_lp_clicked(icon_instance, item): _toggle_nested_config_boolean("rankedStats", "lp")
def on_rank_stats_w_clicked(icon_instance, item): _toggle_nested_config_boolean("rankedStats", "w")
def on_rank_stats_l_clicked(icon_instance, item): _toggle_nested_config_boolean("rankedStats", "l")


def updateStatus(status_message: str):
    global _current_status_text
    _current_status_text = status_message
    if _tray_icon_instance and hasattr(_tray_icon_instance, 'update_menu'):
        try:
            _tray_icon_instance.update_menu() 
        except Exception as e:
            if logger: logger.warning(f"Could not update tray menu for status: {e}")
    if logger: logger.debug(f"Tray status text variable updated: {_current_status_text}")


def get_menu():
    global _settings_gui_is_open
    if logger: logger.info(f"Tray: get_menu called. _settings_gui_is_open = {_settings_gui_is_open}")
    
    if _settings_gui_is_open:
        return Menu(
            MenuItem(f"DetailedLoLRPC {VERSION} - by Ria", None, enabled=False),
            MenuItem(lambda item_text: _current_status_text, None, enabled=False),
            Menu.SEPARATOR,
            MenuItem("Settings Window is Open", None, enabled=False),
            Menu.SEPARATOR,
            MenuItem("Exit", on_exit_clicked) 
        )
    else:
        interactive_enabled = True 
        if logger: logger.debug(f"Tray: get_menu - GUI not open, interactive_enabled = {interactive_enabled}")
        return Menu(
            MenuItem(f"DetailedLoLRPC {VERSION} - by Ria", None, enabled=False),
            MenuItem(lambda item_text: _current_status_text, None, enabled=False), 
            Menu.SEPARATOR,
            MenuItem("Use Skin's splash and name", on_skin_splash_clicked,
                        checked=lambda item: fetchConfig("useSkinSplash"), enabled=interactive_enabled),
            MenuItem("Use animated splash if available", on_animated_splash_clicked,
                        checked=lambda item: fetchConfig("animatedSplash"), enabled=interactive_enabled),
            MenuItem('Show "View splash art" button', on_view_splash_art_clicked,
                        checked=lambda item: fetchConfig("showViewArtButton"), enabled=interactive_enabled),
            MenuItem('Show party info', on_show_party_info_clicked,
                        checked=lambda item: fetchConfig("showPartyInfo"), enabled=interactive_enabled),
            Menu.SEPARATOR,
            MenuItem("Ingame stats", Menu(
                MenuItem("KDA", on_kda_clicked, checked=lambda item: fetchConfig("stats").get("kda", False)),
                MenuItem("CS", on_cs_clicked, checked=lambda item: fetchConfig("stats").get("cs", False)),
                MenuItem("Level", on_level_clicked, checked=lambda item: fetchConfig("stats").get("level", False))
            ), enabled=interactive_enabled),
            MenuItem("Show ranks", Menu(
                MenuItem("Solo", on_rank_solo_clicked, checked=lambda item: fetchConfig("showRanks").get("RANKED_SOLO_5x5", False)),
                MenuItem("Flex", on_rank_flex_clicked, checked=lambda item: fetchConfig("showRanks").get("RANKED_FLEX_SR", False)),
                MenuItem("TFT", on_rank_tft_clicked, checked=lambda item: fetchConfig("showRanks").get("RANKED_TFT", False)),
                MenuItem("TFT Double up", on_rank_double_up_clicked, checked=lambda item: fetchConfig("showRanks").get("RANKED_TFT_DOUBLE_UP", False))
            ), enabled=interactive_enabled),
            MenuItem("Ranked stats", Menu(
                MenuItem("LP", on_rank_stats_lp_clicked, checked=lambda item: fetchConfig("rankedStats").get("lp", False)),
                MenuItem("Wins", on_rank_stats_w_clicked, checked=lambda item: fetchConfig("rankedStats").get("w", False)),
                MenuItem("Losses", on_rank_stats_l_clicked, checked=lambda item: fetchConfig("rankedStats").get("l", False))
            ), enabled=interactive_enabled),
            MenuItem("Idle status", Menu(
                MenuItem("Disabled", lambda: on_idle_status_selected(None, "Disabled"),
                            radio=True, checked=lambda item: fetchConfig("idleStatus") == 0),
                MenuItem("Profile Info", lambda: on_idle_status_selected(None, "Profile Info"), 
                            radio=True, checked=lambda item: fetchConfig("idleStatus") == 1),
                MenuItem("Custom", lambda: on_idle_status_selected(None, "Custom"),
                            radio=True, checked=lambda item: fetchConfig("idleStatus") == 2)
            ), enabled=interactive_enabled),
            Menu.SEPARATOR,
            MenuItem("Mute RPC", on_mute_rpc_clicked, 
                        checked=lambda item: fetchConfig("isRpcMuted"), enabled=interactive_enabled),
            Menu.SEPARATOR,
            MenuItem("Reset preferences", on_reset_config_clicked, enabled=interactive_enabled), 
            MenuItem("Report bug / Open logs", on_report_bug_clicked, enabled=interactive_enabled), 
            MenuItem("Open Settings", on_open_settings_clicked, default=True), 
            MenuItem("Exit", on_exit_clicked) 
        )

try:
    icon = Icon("DetailedLoLRPC", img, "DetailedLoLRPC", menu=get_menu(), left_click=on_open_settings_clicked)
    _tray_icon_instance = icon 
except Exception as e:
    if logger: logger.critical(f"Failed to create pystray.Icon instance: {e}. Tray icon will not be available.")
    class DummyIcon:
        def run_detached(self): 
            if logger: logger.error("DummyIcon: run_detached called, but tray icon creation failed.")
        def stop(self): pass
        HAS_MENU = False 
        def update_menu(self): pass

    icon = DummyIcon()
    _tray_icon_instance = icon
