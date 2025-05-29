import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import webbrowser
import os
import sys
from PIL import Image, ImageTk, ImageDraw
import re
import json
import requests
import asyncio
import threading

from .utilities import (
    fetchConfig, editConfig, resetConfig, ISSUESURL,
    LOG_FILE_PATH, VERSION, logger, resourcePath, CONFIG_FILE_PATH,
    REPOURL, GITHUBURL, checkRiotClientPath,
    register_config_changed_callback, unregister_config_changed_callback,
    DEFAULT_CONFIG as UTILS_DEFAULT_CONFIG
)
import src.tray_icon as tray_module
from . import updater

DISCORD_DARK_GRAY_BG = (49, 51, 56)
PREVIEW_FRAME_SIZE = 100
PREVIEW_IMAGE_MAX_SIZE = (96, 96)
PREVIEW_CORNER_RADIUS = 15

_tkinter_thread = None
_persistent_tk_root = None
_tk_root_ready_event = threading.Event()
_settings_window_instance = None


def _run_tkinter_mainloop():
    global _persistent_tk_root, _tk_root_ready_event
    if logger: logger.info("Tkinter thread: Starting.")
    try:
        _persistent_tk_root = tk.Tk()
        
        if sys.platform == "win32":
            try:
                import ctypes
                APP_USER_MODEL_ID = "Ria.DetailedLoLRPC.GUI.1" 
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
                if logger: logger.info(f"Tkinter thread: AppUserModelID set to '{APP_USER_MODEL_ID}'.")
            except Exception as e_appid:
                if logger: logger.warning(f"Tkinter thread: Failed to set AppUserModelID: {e_appid}")
        
        try:
            icon_path = resourcePath("icon.ico")
            if os.path.exists(icon_path):
                _persistent_tk_root.iconbitmap(icon_path)
                if logger: logger.debug("Tkinter thread: Persistent root icon bitmap set.")
            else:
                if logger: logger.warning("Tkinter thread: icon.ico not found for persistent root.")
        except Exception as e_root_icon:
            if logger: logger.warning(f"Tkinter thread: Could not set icon for persistent root: {e_root_icon}")

        _persistent_tk_root.withdraw()  
        _tk_root_ready_event.set()      
        if logger: logger.info("Tkinter thread: Root created and ready event set. Starting mainloop.")
        _persistent_tk_root.mainloop()
    except Exception as e:
        if logger: logger.error(f"Tkinter thread: Exception in mainloop: {e}", exc_info=True)
    finally:
        if logger: logger.info("Tkinter thread: Mainloop exited.")
        _persistent_tk_root = None 
        _tk_root_ready_event.clear()


def ensure_tkinter_thread_running():
    global _tkinter_thread, _tk_root_ready_event, _persistent_tk_root
    if _tkinter_thread is None or not _tkinter_thread.is_alive():
        if logger: logger.info("Tkinter thread not running or dead. Starting new Tkinter thread.")
        _tk_root_ready_event.clear()
        if _persistent_tk_root and _persistent_tk_root.winfo_exists(): 
            try: _persistent_tk_root.destroy()
            except: pass
            _persistent_tk_root = None

        _tkinter_thread = threading.Thread(target=_run_tkinter_mainloop, daemon=True)
        _tkinter_thread.start()
        if logger: logger.info("Tkinter thread: Waiting for root to be ready...")
        ready = _tk_root_ready_event.wait(timeout=10)  
        if not ready:
            logger.error("Tkinter thread: Timeout waiting for Tk root to become ready.")
            return False
        if logger: logger.info("Tkinter thread: Root is ready.")
    elif not _persistent_tk_root or not _persistent_tk_root.winfo_exists():
        logger.error("Tkinter thread is alive, but persistent root is not valid. This indicates an issue.")
        return False
    return True


class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, rpc_app_ref=None, current_status_getter=None): 
        self._initializing = True 
        if logger: logger.info("SettingsWindow.__init__ CALLED. _initializing = True")

        super().__init__(parent)
        if logger: logger.info("SettingsWindow: super().__init__(parent) COMPLETED.")

        self.title(f"DetailedLoLRPC Settings")
        self.resizable(False, False)
        self.logo_image_tk = None
        self.map_icon_preview_tk = None
        
        self.status_getter = current_status_getter 
        initial_status = "Status: Ready" 
        if self.status_getter:
            try:
                initial_status = self.status_getter()
            except Exception as e_getter:
                if logger: logger.error(f"Error getting initial status: {e_getter}")
                initial_status = "Status: Error"
        
        self.current_app_status = initial_status 
        self.status_label_var = tk.StringVar(value=self.current_app_status)
        
        self._changelog_loading_task = None
        self._update_check_task = None 
        self.rpc_app_ref = rpc_app_ref
        self.main_app_loop = None
        self._changelog_loaded_once = False

        if self.rpc_app_ref and hasattr(self.rpc_app_ref, '_main_loop_ref'):
            self.main_app_loop = self.rpc_app_ref._main_loop_ref
            if logger: logger.debug(f"SettingsWindow: Main app loop ref set: {self.main_app_loop}")


        try:
            icon_path = resourcePath("icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path) 
                if logger: logger.debug("SettingsWindow: Icon bitmap set for Toplevel.")
            else:
                if logger: logger.warning("SettingsWindow: icon.ico not found for Toplevel window.")
        except Exception as e:
            if logger: logger.warning(f"Could not set window icon for settings GUI (Toplevel): {e}")

        self.config_vars = {}
        self.string_vars = {}
        self.custom_idle_widgets = []
        self.profile_info_idle_widgets = [] 

        outer_frame = ttk.Frame(self, padding="10")
        outer_frame.pack(expand=True, fill=tk.BOTH)

        self.notebook = ttk.Notebook(outer_frame)

        tab_padding = "10"

        tab_general = ttk.Frame(self.notebook, padding=tab_padding)
        self.notebook.add(tab_general, text='General')
        self._populate_general_tab(tab_general)

        tab_live_stats = ttk.Frame(self.notebook, padding=tab_padding)
        self.notebook.add(tab_live_stats, text='Live Stats')
        self._populate_live_stats_tab(tab_live_stats)

        tab_ranked = ttk.Frame(self.notebook, padding=tab_padding)
        self.notebook.add(tab_ranked, text='Ranked')
        self._populate_ranked_tab(tab_ranked)

        tab_idle_status = ttk.Frame(self.notebook, padding=tab_padding)
        self.notebook.add(tab_idle_status, text='Idle Status')
        self._populate_idle_status_tab(tab_idle_status)

        tab_application = ttk.Frame(self.notebook, padding=tab_padding)
        self.notebook.add(tab_application, text='Application')
        self._populate_application_tab(tab_application)

        tab_about = ttk.Frame(self.notebook, padding=tab_padding)
        self.notebook.add(tab_about, text='About')
        self._populate_about_tab(tab_about)

        self.notebook.pack(expand=True, fill=tk.BOTH, pady=(0,10))
        if logger: logger.debug("SettingsWindow: Notebook and tabs populated and packed.")


        status_display_label = ttk.Label(outer_frame, textvariable=self.status_label_var, relief=tk.SUNKEN, anchor=tk.W, padding=5)
        status_display_label.pack(fill=tk.X, pady=5, side=tk.BOTTOM)

        ttk.Separator(outer_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5, side=tk.BOTTOM)

        bottom_button_frame = ttk.Frame(outer_frame)
        bottom_button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5,0))
        
        self.mute_rpc_button = ttk.Button(bottom_button_frame, command=self._on_mute_rpc_gui_clicked)
        self.mute_rpc_button.pack(side=tk.LEFT, padx=(0,5)) 
        self._update_mute_rpc_button_text() 

        ttk.Button(bottom_button_frame, text="Test Current Presence", command=self._on_test_presence).pack(side=tk.RIGHT, padx=5)


        if logger: logger.debug("SettingsWindow: UI elements (status bar, buttons) packed.")


        self.transient(parent)
        if logger: logger.debug("SettingsWindow: transient(parent) called.")

        self.grab_set()
        if logger: logger.debug("SettingsWindow: grab_set() called.")

        self.protocol("WM_DELETE_WINDOW", self._on_close_window_button)
        if logger: logger.debug("SettingsWindow: WM_DELETE_WINDOW protocol set.")

        self.focus_set()
        if logger: logger.debug("SettingsWindow: focus_set() called.")


        self._schedule_initial_changelog_load()
        if logger: logger.debug("SettingsWindow: Initial changelog load scheduled.")
        
        if tray_module and hasattr(tray_module, 'disable_tray_menu'):
            tray_module.disable_tray_menu()
            if logger: logger.info("SettingsWindow: Called disable_tray_menu.")

        try:
            register_config_changed_callback(self._refresh_ui_from_config) 
            if logger: logger.info("SettingsWindow: _refresh_ui_from_config (wrapper) registered for config changes.")
        except Exception as e_reg_gui:
            if logger: logger.error(f"SettingsWindow: Error registering GUI refresh callback: {e_reg_gui}")


        self._initializing = False 
        if logger: logger.info("SettingsWindow.__init__ COMPLETED (UI built). _initializing = False.")
        
        self.update_idletasks() 
        self.deiconify()        
        self.lift()             

        if self.status_getter:
            self._poll_status() 
            if logger: logger.info("SettingsWindow: Status polling started.")
        else:
            if logger: logger.warning("SettingsWindow: No status_getter provided, status bar will not update live.")

        if logger: logger.info("SettingsWindow: __init__ finished, window should be visible and non-blocking.")

    def _on_mute_rpc_gui_clicked(self):
        current_mute_state = fetchConfig("isRpcMuted")
        editConfig("isRpcMuted", not current_mute_state)
        self._update_mute_rpc_button_text()

    def _update_mute_rpc_button_text(self):
        if hasattr(self, 'mute_rpc_button') and self.mute_rpc_button.winfo_exists():
            is_muted = fetchConfig("isRpcMuted")
            button_text = "Unmute RPC" if is_muted else "Mute RPC"
            self.mute_rpc_button.config(text=button_text)


    def _poll_status(self):
        if not self.winfo_exists(): 
            if logger: logger.debug("SettingsWindow: _poll_status - window destroyed, stopping poll.")
            return

        if self.status_getter:
            try:
                new_status = self.status_getter()
                self.current_app_status = new_status 
                if new_status != self.status_label_var.get():
                    self.status_label_var.set(new_status)
                    if logger: logger.debug(f"SettingsWindow: Status bar updated to: {new_status}")
            except Exception as e:
                if logger: logger.error(f"SettingsWindow: Error calling status_getter or setting status_label_var: {e}", exc_info=False) 
        
        self.after(1000, self._poll_status) 


    def _refresh_ui_from_config(self):
        global _persistent_tk_root
        if _persistent_tk_root and _persistent_tk_root.winfo_exists():
            try:
                if self.winfo_exists():
                    _persistent_tk_root.after(0, self._perform_ui_refresh_thread_safe)
                    if logger: logger.debug("SettingsWindow: _perform_ui_refresh_thread_safe scheduled via _persistent_tk_root.after().")
                else:
                    if logger: logger.debug("SettingsWindow: _refresh_ui_from_config called on destroyed Toplevel. Skipping schedule.")
            except tk.TclError as e:
                if "application has been destroyed" in str(e):
                    if logger: logger.warning(f"SettingsWindow: Failed to schedule UI refresh, application/widget likely destroyed: {e}")
                else:
                    if logger: logger.error(f"SettingsWindow: TclError scheduling UI refresh: {e}", exc_info=True)
            except Exception as e:
                if logger: logger.error(f"SettingsWindow: Unexpected error scheduling UI refresh: {e}", exc_info=True)
        else:
            if logger: logger.warning("SettingsWindow: _refresh_ui_from_config called but _persistent_tk_root is not valid.")


    def _perform_ui_refresh_thread_safe(self):
        if not self.winfo_exists(): 
            if logger: logger.debug("SettingsWindow: _perform_ui_refresh_thread_safe called on destroyed window. Skipping.")
            return

        if logger: logger.info("SettingsWindow: _perform_ui_refresh_thread_safe CALLED (scheduled).")

        was_initializing = self._initializing
        self._initializing = True 

        try:
            for config_path_str, var in self.config_vars.items():
                current_config_value = fetchConfig(config_path_str) 
                
                if isinstance(var, tk.BooleanVar):
                    var.set(bool(current_config_value))
                elif isinstance(var, tk.IntVar):
                    try:
                        var.set(int(current_config_value))
                    except (ValueError, TypeError):
                        default_int_val = 0 
                        try:
                            temp_default = UTILS_DEFAULT_CONFIG 
                            for k_part in config_path_str.split('.'):
                                temp_default = temp_default[k_part]
                            default_int_val = int(temp_default)
                        except (KeyError, TypeError, ValueError) as e_default_lookup:
                            logger.error(f"Error retrieving/converting default int for {config_path_str} from UTILS_DEFAULT_CONFIG: {e_default_lookup}. Using 0.")
                        
                        var.set(default_int_val)
                        logger.warning(f"Could not convert '{current_config_value}' to int for {config_path_str}. Used default from UTILS_DEFAULT_CONFIG: {default_int_val}.")
                elif isinstance(var, tk.StringVar): 
                    var.set(str(current_config_value) if current_config_value is not None else "")
                else:
                    if logger: logger.warning(f"Unhandled var type for {config_path_str} in _perform_ui_refresh_thread_safe: {type(var)}")

            for key, str_var in self.string_vars.items():
                str_var.set(fetchConfig(key))
                if logger: logger.debug(f"Refreshed string_var '{key}' to '{str_var.get()}'")

            self._update_map_icon_preview()
            self._toggle_idle_options_state() # Updated to a more generic name
            self._update_mute_rpc_button_text() 

            if logger: logger.info("SettingsWindow: UI refreshed with current config values (thread-safe).")

        except Exception as e:
            if logger: logger.error(f"Error in _perform_ui_refresh_thread_safe: {e}", exc_info=True)
        finally:
            self._initializing = was_initializing 


    def _populate_general_tab(self, tab_frame):
        lf_padding = "10"
        general_frame = ttk.LabelFrame(tab_frame, text="General Presence Display", padding=lf_padding)
        general_frame.pack(fill=tk.X, pady=5, padx=5, anchor=tk.NW)
        self._create_checkbutton(general_frame, "useSkinSplash", "Use Champion's Skin Splash & Name")
        self._create_checkbutton(general_frame, "animatedSplash", "Use Animated Splash (if available)")
        self._create_checkbutton(general_frame, "showViewArtButton", 'Show "View Splash Art" Button')
        self._create_checkbutton(general_frame, "showPartyInfo", "Show Party Size Information")

        map_icon_style_frame_outer = ttk.LabelFrame(tab_frame, text="Map Icon Style", padding=lf_padding)
        map_icon_style_frame_outer.pack(fill=tk.X, pady=10, padx=5, anchor=tk.NW)
        map_icon_content_frame = ttk.Frame(map_icon_style_frame_outer)
        map_icon_content_frame.pack(fill=tk.X)
        radio_frame = ttk.Frame(map_icon_content_frame)
        radio_frame.pack(side=tk.LEFT, anchor=tk.NW, padx=(0, 20))
        self.config_vars["mapIconStyle"] = tk.StringVar(value=fetchConfig("mapIconStyle"))
        map_icon_styles = ["Active", "Empty", "Hover", "Defeat", "Background"]
        for style in map_icon_styles:
            rb = ttk.Radiobutton(radio_frame, text=style, variable=self.config_vars["mapIconStyle"], value=style, command=self._on_map_icon_style_change)
            rb.pack(anchor=tk.W, pady=2)
        preview_container = ttk.Frame(map_icon_content_frame, width=PREVIEW_FRAME_SIZE, height=PREVIEW_FRAME_SIZE)
        preview_container.pack(side=tk.LEFT, anchor=tk.CENTER, padx=5)
        preview_container.pack_propagate(False)
        self.map_icon_preview_label = ttk.Label(preview_container, relief=tk.GROOVE, anchor=tk.CENTER)
        self.map_icon_preview_label.pack(expand=True, fill=tk.BOTH)
        self._update_map_icon_preview()


    def _populate_live_stats_tab(self, tab_frame):
        lf_padding = "10"
        ingame_stats_frame = ttk.LabelFrame(tab_frame, text="In-Game Stats (Live Game)", padding=lf_padding)
        ingame_stats_frame.pack(fill=tk.X, pady=5, padx=5, anchor=tk.NW)
        self._create_checkbutton(ingame_stats_frame, "stats.kda", "Show KDA")
        self._create_checkbutton(ingame_stats_frame, "stats.cs", "Show CS")
        self._create_checkbutton(ingame_stats_frame, "stats.level", "Show Level")

    def _populate_ranked_tab(self, tab_frame):
        lf_padding = "10"
        ranks_frame = ttk.LabelFrame(tab_frame, text="Show Ranks For", padding=lf_padding)
        ranks_frame.pack(fill=tk.X, pady=5, padx=5, anchor=tk.NW)
        self._create_checkbutton(ranks_frame, "showRanks.RANKED_SOLO_5x5", "Ranked Solo/Duo")
        self._create_checkbutton(ranks_frame, "showRanks.RANKED_FLEX_SR", "Ranked Flex")
        self._create_checkbutton(ranks_frame, "showRanks.RANKED_TFT", "Ranked TFT")
        self._create_checkbutton(ranks_frame, "showRanks.RANKED_TFT_DOUBLE_UP", "Ranked TFT Double Up")

        ranked_stats_frame = ttk.LabelFrame(tab_frame, text="Show Ranked Stats Detail", padding=lf_padding)
        ranked_stats_frame.pack(fill=tk.X, pady=5, padx=5, anchor=tk.NW)
        self._create_checkbutton(ranked_stats_frame, "rankedStats.lp", "Show LP")
        self._create_checkbutton(ranked_stats_frame, "rankedStats.w", "Show Wins")
        self._create_checkbutton(ranked_stats_frame, "rankedStats.l", "Show Losses")

    def _toggle_idle_options_state(self):
        idle_status_val = self.config_vars["idleStatus"].get()
        
        is_profile_info_selected = (idle_status_val == 1)
        profile_info_state = tk.NORMAL if is_profile_info_selected else tk.DISABLED
        if hasattr(self, 'profile_info_idle_options_frame'):
            for widget in self.profile_info_idle_widgets:
                try: widget.config(state=profile_info_state)
                except tk.TclError: pass
            try: self.profile_info_idle_options_frame.config(text="Profile Info Display Options" + (" (Active)" if is_profile_info_selected else ""))
            except tk.TclError: pass


        is_custom_selected = (idle_status_val == 2)
        custom_state = tk.NORMAL if is_custom_selected else tk.DISABLED
        if hasattr(self, 'custom_idle_options_outer_frame'):
            for widget in self.custom_idle_widgets:
                try: widget.config(state=custom_state)
                except tk.TclError: pass
            try: self.custom_idle_options_outer_frame.config(text="Custom Idle Configuration" + (" (Active)" if is_custom_selected else ""))
            except tk.TclError: pass

        if is_custom_selected:
            self._enable_validate_button_if_text()
        else:
            if hasattr(self, 'validate_image_link_button'):
                self.validate_image_link_button.config(state=tk.DISABLED)


    def _populate_idle_status_tab(self, tab_frame):
        lf_padding = "10"
        idle_selection_frame = ttk.LabelFrame(tab_frame, text="Idle Status Mode", padding=lf_padding)
        idle_selection_frame.pack(fill=tk.X, pady=5, padx=5, anchor=tk.NW)

        self.config_vars["idleStatus"] = tk.IntVar(value=fetchConfig("idleStatus"))

        ttk.Radiobutton(idle_selection_frame, text="Disabled (No presence when idle)", variable=self.config_vars["idleStatus"], value=0, command=self._on_idle_status_or_custom_option_change).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(idle_selection_frame, text="Profile Info (Icon, Level, Status)", variable=self.config_vars["idleStatus"], value=1, command=self._on_idle_status_or_custom_option_change).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(idle_selection_frame, text="Custom", variable=self.config_vars["idleStatus"], value=2, command=self._on_idle_status_or_custom_option_change).pack(anchor=tk.W, pady=2)

        self.profile_info_idle_options_frame = ttk.LabelFrame(tab_frame, text="Profile Info Display Options", padding=lf_padding)
        self.profile_info_idle_options_frame.pack(fill=tk.X, pady=(10,5), padx=5, anchor=tk.NW)
        
        profile_info_inner_frame = ttk.Frame(self.profile_info_idle_options_frame)
        profile_info_inner_frame.pack(fill=tk.X, anchor=tk.W)

        cb_riot_id = self._create_checkbutton(profile_info_inner_frame, "idleProfileInfoDisplay.showRiotId", "Show Riot ID (Name)", is_profile_idle_option=True)
        cb_riot_id.pack(side=tk.LEFT, padx=(0,10))
        cb_tag = self._create_checkbutton(profile_info_inner_frame, "idleProfileInfoDisplay.showTagLine", "Show Tagline", is_profile_idle_option=True)
        cb_tag.pack(side=tk.LEFT, padx=(0,10))
        cb_level = self._create_checkbutton(profile_info_inner_frame, "idleProfileInfoDisplay.showSummonerLevel", "Show Level", is_profile_idle_option=True)
        cb_level.pack(side=tk.LEFT)


        self.custom_idle_options_outer_frame = ttk.LabelFrame(tab_frame, text="Custom Idle Configuration", padding=lf_padding)
        self.custom_idle_options_outer_frame.pack(fill=tk.X, pady=(10,5), padx=5, anchor=tk.NW)

        custom_idle_inner_frame = ttk.Frame(self.custom_idle_options_outer_frame, padding=(5, 5, 0, 0))
        custom_idle_inner_frame.pack(fill=tk.X, anchor=tk.W)

        img_link_frame = ttk.Frame(custom_idle_inner_frame)
        img_link_frame.pack(fill=tk.X, pady=2)
        img_link_label = ttk.Label(img_link_frame, text="Image Link (png, jpg, gif):")
        img_link_label.pack(side=tk.LEFT)
        self.string_vars["idleCustomImageLink"] = tk.StringVar(value=fetchConfig("idleCustomImageLink"))
        img_link_entry = ttk.Entry(img_link_frame, textvariable=self.string_vars["idleCustomImageLink"], width=25)
        img_link_entry.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        img_link_entry.bind("<KeyRelease>", self._on_image_link_entry_change)
        img_link_entry.bind("<FocusOut>", self._on_setting_change)
        img_link_entry.bind("<Return>", self._on_setting_change)
        self.validate_image_link_button = ttk.Button(img_link_frame, text="Validate", command=self._on_validate_image_link_clicked, state=tk.DISABLED)
        self.validate_image_link_button.pack(side=tk.LEFT)
        self.custom_idle_widgets.extend([img_link_label, img_link_entry, self.validate_image_link_button])

        custom_text_frame = ttk.Frame(custom_idle_inner_frame)
        custom_text_frame.pack(fill=tk.X, pady=2)
        custom_text_label = ttk.Label(custom_text_frame, text="Custom Text:")
        custom_text_label.pack(side=tk.LEFT)
        self.string_vars["idleCustomText"] = tk.StringVar(value=fetchConfig("idleCustomText"))
        custom_text_entry = ttk.Entry(custom_text_frame, textvariable=self.string_vars["idleCustomText"], width=30)
        custom_text_entry.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        custom_text_entry.bind("<FocusOut>", self._on_setting_change)
        custom_text_entry.bind("<Return>", self._on_setting_change)
        self.custom_idle_widgets.extend([custom_text_label, custom_text_entry])

        cb_status_circle = self._create_checkbutton(custom_idle_inner_frame, "idleCustomShowStatusCircle", "Show availability status circle", is_custom_idle_option=True)
        cb_time_elapsed = self._create_checkbutton(custom_idle_inner_frame, "idleCustomShowTimeElapsed", "Show time elapsed", is_custom_idle_option=True)

        self._toggle_idle_options_state()

    def _populate_application_tab(self, tab_frame):
        lf_padding = "10"
        app_behavior_frame = ttk.LabelFrame(tab_frame, text="Application Behavior", padding=lf_padding)
        app_behavior_frame.pack(fill=tk.X, pady=5, padx=5, anchor=tk.NW)

        self._create_checkbutton(app_behavior_frame, "showWindowOnStartup", "Show this settings window on startup")
        self._create_checkbutton(app_behavior_frame, "checkForUpdatesOnStartup", "Check for updates on startup")
        
        path_frame = ttk.LabelFrame(tab_frame, text="Game Path", padding=lf_padding)
        path_frame.pack(fill=tk.X, pady=10, padx=5, anchor=tk.NW)
        ttk.Label(path_frame, text="Riot Games Path:").pack(anchor=tk.W, pady=(0,2))
        path_entry_frame = ttk.Frame(path_frame)
        path_entry_frame.pack(fill=tk.X)
        self.string_vars["riotPath"] = tk.StringVar(value=fetchConfig("riotPath"))
        path_entry = ttk.Entry(path_entry_frame, textvariable=self.string_vars["riotPath"], width=35)
        path_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        path_entry.bind("<FocusOut>", self._on_setting_change)
        path_entry.bind("<Return>", self._on_setting_change)
        browse_button = ttk.Button(path_entry_frame, text="Browse...", command=self._on_browse_riot_path)
        browse_button.pack(side=tk.LEFT, padx=(5,0))

        data_actions_frame = ttk.LabelFrame(tab_frame, text="Application Data", padding=lf_padding)
        data_actions_frame.pack(fill=tk.X, pady=(10,5), padx=5, anchor=tk.NW)

        import_export_reset_frame = ttk.Frame(data_actions_frame)
        import_export_reset_frame.pack(fill=tk.X, pady=5)
        ttk.Button(import_export_reset_frame, text="Import Settings", command=self._on_import_settings).pack(side=tk.LEFT, padx=2)
        ttk.Button(import_export_reset_frame, text="Export Settings", command=self._on_export_settings).pack(side=tk.LEFT, padx=2)
        ttk.Button(import_export_reset_frame, text="Reset All Preferences", command=self._on_reset_config).pack(side=tk.LEFT, padx=2)


    def _populate_about_tab(self, tab_frame):
        about_main_frame = ttk.Frame(tab_frame)
        about_main_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        left_column_frame = ttk.Frame(about_main_frame)
        left_column_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15), pady=5, anchor=tk.NW, expand=False)

        try:
            logo_path = resourcePath("icon.ico")
            if os.path.exists(logo_path):
                pil_image = Image.open(logo_path)
                pil_image = pil_image.resize((48, 48), Image.Resampling.LANCZOS)
                self.logo_image_tk = ImageTk.PhotoImage(pil_image)
                logo_label = ttk.Label(left_column_frame, image=self.logo_image_tk)
                logo_label.pack(pady=(0,10))
            else:
                ttk.Label(left_column_frame, text="[Logo NF]").pack(pady=(0,10))
        except Exception as e:
            if logger: logger.warning(f"Could not load logo for About tab: {e}")
            else: print(f"Warning: Could not load logo for About tab: {e}")
            ttk.Label(left_column_frame, text="[Logo Err]").pack(pady=(0,10))

        ttk.Label(left_column_frame, text="DetailedLoLRPC", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)
        ttk.Label(left_column_frame, text=f"Version: {VERSION}", font=("Segoe UI", 9)).pack(pady=(0,10), anchor=tk.W)
        ttk.Label(left_column_frame, text="Created by: Ria").pack(pady=2, anchor=tk.W)

        links_frame = ttk.Frame(left_column_frame)
        links_frame.pack(pady=10, anchor=tk.W, fill=tk.X)
        ttk.Button(links_frame, text="GitHub Repository", command=lambda: webbrowser.open(REPOURL)).pack(fill=tk.X, pady=2)
        ttk.Button(links_frame, text="Report an Issue", command=lambda: webbrowser.open(ISSUESURL)).pack(fill=tk.X, pady=2)
        ttk.Button(links_frame, text="Open Logs Folder", command=self._on_open_logs).pack(fill=tk.X, pady=2)
        ttk.Button(links_frame, text="Check for Updates", command=self._on_check_for_updates_button).pack(fill=tk.X, pady=2)

        changelog_outer_frame = ttk.Frame(about_main_frame)
        changelog_outer_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(0,0), pady=0)

        changelog_frame = ttk.LabelFrame(changelog_outer_frame, text="Changelog", padding="5")
        changelog_frame.pack(fill=tk.BOTH, expand=True)

        self.changelog_text = scrolledtext.ScrolledText(changelog_frame, wrap=tk.WORD, height=6, width=35, state=tk.DISABLED, font=("Segoe UI", 8))
        self.changelog_text.pack(pady=5, fill=tk.BOTH, expand=True)
        self.changelog_text.insert(tk.END, "Click 'Load/Refresh Changelog' to fetch updates...\n")
        self.changelog_text.config(state=tk.DISABLED)

        ttk.Button(changelog_frame, text="Load/Refresh Changelog", command=self._schedule_changelog_load_from_button).pack(pady=5)


    def _on_close_window_button(self):
        global _settings_window_instance
        if logger: logger.info("SettingsWindow: Close button (WM_DELETE_WINDOW) clicked.")

        if self._changelog_loading_task and not self._changelog_loading_task.done():
            if logger: logger.debug("SettingsWindow: Attempting to cancel changelog task.")
            try:
                if self.main_app_loop and self.main_app_loop.is_running():
                    self.main_app_loop.call_soon_threadsafe(self._changelog_loading_task.cancel)
                    if logger: logger.debug("SettingsWindow: Changelog task cancellation scheduled via main_app_loop.")
                else:
                    self._changelog_loading_task.cancel()
                    if logger: logger.debug("SettingsWindow: Changelog task cancellation attempted directly.")
            except Exception as e_cancel:
                if logger: logger.error(f"SettingsWindow: Error cancelling changelog task: {e_cancel}", exc_info=True)
        
        try:
            if hasattr(self, '_refresh_ui_from_config'): 
                unregister_config_changed_callback(self._refresh_ui_from_config) 
                if logger: logger.info("SettingsWindow: _refresh_ui_from_config (wrapper) unregistered.")
            else:
                if logger: logger.warning("SettingsWindow: _refresh_ui_from_config method not found for unregistration.")
        except Exception as e_unreg_gui:
            if logger: logger.error(f"SettingsWindow: Error unregistering GUI refresh callback: {e_unreg_gui}")
        
        if tray_module and hasattr(tray_module, 'enable_tray_menu'):
            tray_module.enable_tray_menu()
            if logger: logger.info("SettingsWindow: Called enable_tray_menu.")

        _settings_window_instance = None 
        if logger: logger.info("SettingsWindow: Global _settings_window_instance has been set to None.") 
        
        try:
            self.destroy() 
            if logger: logger.info("SettingsWindow: self.destroy() called successfully.")
        except tk.TclError as e_destroy:
            if logger: logger.error(f"SettingsWindow: TclError during self.destroy(): {e_destroy}. Window might have already been destroyed.", exc_info=True)
        except Exception as e_destroy_other:
            if logger: logger.error(f"SettingsWindow: Unexpected error during self.destroy(): {e_destroy_other}", exc_info=True)


    def _on_minimize_window(self):
        self.iconify()
        if logger: logger.debug("Settings window minimized.")


    def _on_browse_riot_path(self):
        directory = filedialog.askdirectory(title="Select Riot Games Installation Folder")
        if directory:
            self.string_vars["riotPath"].set(directory)
            self._on_setting_change() 
        if logger: logger.info(f"Riot Games path browse selected: {directory}")
        else: print(f"Riot Games path browse selected: {directory}")

    def _on_open_logs(self):
        try:
            log_dir = os.path.dirname(LOG_FILE_PATH)
            if os.path.exists(log_dir):
                if sys.platform == "win32": os.startfile(log_dir)
                elif sys.platform == "darwin": os.system(f'open "{log_dir}"')
                else: os.system(f'xdg-open "{log_dir}"')
            else:
                if logger: logger.error(f"Log directory {log_dir} not found.")
                else: print(f"Log directory {log_dir} not found.")
        except Exception as e:
            if logger: logger.error(f"Failed to open logs folder: {e}")
            else: print(f"Error opening logs folder: {e}")

    def _on_import_settings(self):
        filepath = filedialog.askopenfilename(
            title="Import Settings",
            filetypes=(("DetailedLoLRPC Config JSON", "*.json"), ("All files", "*.*")),
            defaultextension=".json",
            parent=self
        )
        if filepath:
            if logger: logger.info(f"Import settings selected: {filepath}")
            else: print(f"Import settings selected: {filepath}")
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    imported_data = json.load(f)
                if not isinstance(imported_data, dict):
                    messagebox.showerror("Import Error", "Invalid file format. Expected a JSON object.", parent=self)
                    return

                for key, value in imported_data.items():
                    editConfig(key, value)

                messagebox.showinfo("Import Successful", "Settings imported successfully. RPC will refresh.", parent=self)
            except json.JSONDecodeError:
                messagebox.showerror("Import Error", "Failed to decode JSON file. Ensure it's a valid JSON.", parent=self)
            except Exception as e:
                messagebox.showerror("Import Error", f"An error occurred: {e}", parent=self)
                if logger: logger.error(f"Error importing settings: {e}", exc_info=True)

    def _on_export_settings(self):
        filepath = filedialog.asksaveasfilename(
            title="Export Settings",
            filetypes=(("DetailedLoLRPC Config JSON", "*.json"), ("All files", "*.*")),
            defaultextension=".json",
            initialfile="DetailedLoLRPC_config.json",
            parent=self
        )
        if filepath:
            if logger: logger.info(f"Export settings selected: {filepath}")
            else: print(f"Export settings selected: {filepath}")
            try:
                config_to_export = {}
                from .utilities import DEFAULT_CONFIG as ACTUAL_DEFAULT_CONFIG_FROM_UTILS 
                for key in ACTUAL_DEFAULT_CONFIG_FROM_UTILS.keys():
                    config_to_export[key] = fetchConfig(key)

                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(config_to_export, f, indent=4)
                messagebox.showinfo("Export Successful", f"Settings exported to:\n{filepath}", parent=self)
            except Exception as e:
                messagebox.showerror("Export Error", f"An error occurred: {e}", parent=self)
                if logger: logger.error(f"Error exporting settings: {e}", exc_info=True)

    def _on_validate_image_link_clicked(self):
        link_var = self.string_vars.get("idleCustomImageLink")
        if not link_var: return
        link = link_var.get().strip()

        if logger: logger.info(f"Validate Image Link clicked: {link}")
        else: print(f"Validate Image Link clicked: {link}")

        if not link:
            messagebox.showwarning("Validation", "Image link is empty.", parent=self)
            return

        original_button_text = "Validate"
        self.validate_image_link_button.config(text="Validating...")
        self.update_idletasks()

        is_valid = False
        try:
            with requests.get(link, stream=True, timeout=5) as r:
                r.raise_for_status() 
                content_type = r.headers.get('Content-Type', '').lower()
                if logger: logger.debug(f"Validation: URL '{link}' Content-Type: '{content_type}'")
                
                valid_content_types = ['image/png', 'image/jpeg', 'image/gif']
                if any(ct in content_type for ct in valid_content_types):
                    is_valid = True
                    messagebox.showinfo("Validation", "Link appears to be a valid image type (png, jpg, gif based on Content-Type).", parent=self)
                    self.validate_image_link_button.config(text="Validated ✔")
                else:
                    messagebox.showwarning("Validation", f"Link does not appear to be a direct image (png, jpg, gif).\nContent-Type: {content_type}", parent=self)
                    self.validate_image_link_button.config(text=original_button_text)
        except requests.exceptions.Timeout:
            messagebox.showerror("Validation Error", "Timeout while trying to validate the image link.", parent=self)
            self.validate_image_link_button.config(text=original_button_text)
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Validation Error", f"Could not validate image link:\n{e}", parent=self)
            self.validate_image_link_button.config(text=original_button_text)
            if logger: logger.error(f"Error validating image link '{link}': {e}")
        except Exception as e_val: 
            messagebox.showerror("Validation Error", f"An unexpected error occurred during validation:\n{e_val}", parent=self)
            self.validate_image_link_button.config(text=original_button_text)
            if logger: logger.error(f"Unexpected error validating image link '{link}': {e_val}", exc_info=True)

        
        if is_valid:
            self.after(2000, lambda: self.validate_image_link_button.config(text=original_button_text, state=tk.DISABLED if not self.string_vars["idleCustomImageLink"].get() else tk.NORMAL))
        else:
            self._enable_validate_button_if_text() 


    def _on_test_presence(self):
        if logger: logger.info("Test Current Presence button clicked.")
        if self.rpc_app_ref and hasattr(self.rpc_app_ref, 'schedule_presence_refresh'):
            self.rpc_app_ref.schedule_presence_refresh()
            messagebox.showinfo("Test Presence", "Presence refresh scheduled.", parent=self)
            logger.info("Presence refresh scheduled via Test button.")
        else:
            messagebox.showwarning("Test Presence", "Cannot trigger presence test.\n(Main application reference not available)", parent=self)
            logger.warning("Could not trigger presence test: rpc_app_ref missing or no schedule_presence_refresh method.")

    def _schedule_changelog_load_from_button(self):
        self._schedule_initial_changelog_load(force_refresh=True)

    def _schedule_initial_changelog_load(self, force_refresh=False):
        if not force_refresh and self._changelog_loaded_once:
            if logger: logger.debug("Changelog already loaded once, skipping initial auto-load.")
            return

        if self._changelog_loading_task and not self._changelog_loading_task.done():
            try:
                self._changelog_loading_task.cancel()
            except Exception as e:
                if logger: logger.debug(f"Error cancelling previous changelog task: {e}")

        if self.main_app_loop and self.main_app_loop.is_running():
            if logger: logger.debug("Scheduling _async_load_changelog on main_app_loop.")
            self._changelog_loading_task = asyncio.run_coroutine_threadsafe(self._async_load_changelog(), self.main_app_loop)
        else:
            logger.warning("Main asyncio loop not available for changelog. Attempting threaded sync load (may have limited functionality or cause issues).")
            threading.Thread(target=self._load_changelog_sync_fallback, daemon=True).start()


    def _load_changelog_sync_fallback(self):
        if logger: logger.info("Changelog: Starting synchronous fallback load.")
        if not hasattr(self, 'changelog_text') or not self.changelog_text.winfo_exists():
            logger.error("Changelog: Text widget not available for sync fallback load.")
            return

        _persistent_tk_root.after(0, lambda: self.changelog_text.config(state=tk.NORMAL))
        _persistent_tk_root.after(0, lambda: self.changelog_text.delete(1.0, tk.END))
        _persistent_tk_root.after(0, lambda: self.changelog_text.insert(tk.END, "Loading changelog (sync fallback)...\n"))
        
        changelog_content = ""
        error_content = ""
        try:
            releases_url = f"https://api.github.com/repos/{REPOURL.split('github.com/')[1].strip('/')}/releases"
            response = requests.get(releases_url, timeout=10)
            response.raise_for_status()
            releases = response.json()
            self._changelog_loaded_once = True 

            if releases:
                for release in releases[:3]:
                    changelog_content += f"{release.get('name', 'Unnamed Release')} ({release.get('published_at', '')[:10]})\n"
                    changelog_content += f"{release.get('body', 'No description.')}\n\n"
            else:
                error_content = "No changelog data found or failed to load."
        except Exception as e:
            logger.error(f"Changelog: Error during sync fallback load: {e}", exc_info=True)
            error_content = f"Error loading changelog (sync): {e}"

        def update_ui():
            if not self.changelog_text.winfo_exists(): return
            self.changelog_text.delete(1.0, tk.END)
            if error_content:
                self.changelog_text.insert(tk.END, error_content, "error")
            elif changelog_content:
                parts = changelog_content.split('\n\n')
                for part in parts:
                    if not part.strip(): continue
                    lines = part.split('\n')
                    if lines:
                        self.changelog_text.insert(tk.END, lines[0] + '\n', "h1")
                        if len(lines) > 1:
                            self.changelog_text.insert(tk.END, '\n'.join(lines[1:]) + '\n\n', "normal")
            else: 
                self.changelog_text.insert(tk.END, "Failed to load changelog content.", "error")

            self.changelog_text.config(state=tk.DISABLED)
            self.changelog_text.tag_config("h1", font=("Segoe UI", 10, "bold"))
            self.changelog_text.tag_config("normal", font=("Segoe UI", 9))
            self.changelog_text.tag_config("error", foreground="red")

        if _persistent_tk_root and _persistent_tk_root.winfo_exists():
            _persistent_tk_root.after(0, update_ui)
        logger.info("Changelog: Synchronous fallback load finished.")


    def _handle_changelog_load_error(self, error_message):
        if logger: logger.warning(f"Cannot schedule/load changelog: {error_message}")
        if hasattr(self, 'changelog_text') and self.changelog_text.winfo_exists():
            self.changelog_text.config(state=tk.NORMAL)
            self.changelog_text.delete(1.0, tk.END)
            self.changelog_text.insert(tk.END, f"Could not load changelog: {error_message}\nTry again when main application is active or click button.", "error")
            self.changelog_text.config(state=tk.DISABLED)


    async def _async_load_changelog(self):
        if logger: logger.info("Async Load Changelog task started.")
        if not hasattr(self, 'changelog_text') or not self.changelog_text.winfo_exists():
            if logger: logger.error("Changelog text widget not available for async load.")
            return

        _persistent_tk_root.after(0, lambda: self.changelog_text.config(state=tk.NORMAL))
        _persistent_tk_root.after(0, lambda: self.changelog_text.delete(1.0, tk.END))
        _persistent_tk_root.after(0, lambda: self.changelog_text.insert(tk.END, "Loading changelog...\n"))
        
        changelog_content = ""
        error_content = ""
        try:
            releases_url = f"https://api.github.com/repos/{REPOURL.split('github.com/')[1].strip('/')}/releases"

            loop = asyncio.get_event_loop() 
            response = await loop.run_in_executor(None, lambda: requests.get(releases_url, timeout=10))
            response.raise_for_status()
            releases = response.json()
            self._changelog_loaded_once = True

            if releases:
                for release in releases[:3]:
                    changelog_content += f"{release.get('name', 'Unnamed Release')} ({release.get('published_at', '')[:10]})\n" 
                    changelog_content += f"{release.get('body', 'No description.')}\n\n" 
            else:
                error_content = "No changelog data found or failed to load."
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error loading changelog: {e}")
            error_content = f"Error loading changelog (network): {e}"
        except json.JSONDecodeError as e:
            logger.error(f"JSON error parsing changelog: {e}")
            error_content = f"Error parsing changelog data."
        except Exception as e:
            logger.error(f"Failed to load changelog asynchronously: {e}", exc_info=True)
            error_content = f"Error loading changelog: {e}"

        def update_ui_after_async():
            if not self.changelog_text.winfo_exists(): return
            self.changelog_text.delete(1.0, tk.END)
            if error_content:
                self.changelog_text.insert(tk.END, error_content, "error")
            elif changelog_content:
                parts = changelog_content.split('\n\n')
                for part in parts:
                    if not part.strip(): continue
                    lines = part.split('\n')
                    if lines:
                        self.changelog_text.insert(tk.END, lines[0] + '\n', "h1")
                        if len(lines) > 1:
                            self.changelog_text.insert(tk.END, '\n'.join(lines[1:]) + '\n\n', "normal")
            else:
                self.changelog_text.insert(tk.END, "Failed to load changelog.", "error")

            self.changelog_text.config(state=tk.DISABLED)
            self.changelog_text.tag_config("h1", font=("Segoe UI", 10, "bold"))
            self.changelog_text.tag_config("normal", font=("Segoe UI", 9))
            self.changelog_text.tag_config("error", foreground="red")

        if _persistent_tk_root and _persistent_tk_root.winfo_exists():
            _persistent_tk_root.after(0, update_ui_after_async)
        if logger: logger.info("Async Load Changelog task finished.")


    def _create_checkbutton(self, parent_frame, config_path_str, text, is_custom_idle_option=False, is_profile_idle_option=False):
        keys = config_path_str.split('.')
        current_config_value = fetchConfig(keys[0])
        initial_state = False
        if len(keys) > 1:
            if isinstance(current_config_value, dict):
                initial_state = bool(current_config_value.get(keys[1], False))
        else:
            initial_state = bool(current_config_value)

        var = tk.BooleanVar(value=initial_state)
        self.config_vars[config_path_str] = var

        cmd = self._on_idle_status_or_custom_option_change if (is_custom_idle_option or is_profile_idle_option) else self._on_setting_change
        cb = ttk.Checkbutton(parent_frame, text=text, variable=var, command=cmd)
        
        if not is_profile_idle_option: # Profile idle options are packed differently (side by side)
            cb.pack(anchor=tk.W, pady=1)

        if is_custom_idle_option:
            self.custom_idle_widgets.append(cb)
        if is_profile_idle_option:
            self.profile_info_idle_widgets.append(cb)
        return cb


    def _on_setting_change(self, event=None):
        if self._initializing: 
            if logger: logger.debug("GUI setting change SKIPPED during initialization.")
            return

        if logger: logger.debug("GUI setting changed, applying immediately.")
        else: print("GUI setting changed, applying immediately.")
        self._apply_changes()

    def _on_image_link_entry_change(self, event=None):
        self._enable_validate_button_if_text()

    def _enable_validate_button_if_text(self):
        if hasattr(self, 'validate_image_link_button'):
            link_text = self.string_vars.get("idleCustomImageLink", tk.StringVar()).get()
            if link_text and link_text.strip():
                self.validate_image_link_button.config(state=tk.NORMAL)
            else:
                self.validate_image_link_button.config(state=tk.DISABLED)

    def _on_idle_status_or_custom_option_change(self):
        self._toggle_idle_options_state() # Updated to a more generic name
        self._on_setting_change()

    def _apply_changes(self):
        if self._initializing: 
            if logger: logger.debug("_apply_changes called but SKIPPED during initialization.")
            return

        if logger: logger.info("Applying settings due to change...")
        else: print("Applying settings due to change...")
        
        changed_configs = {}
        config_update_success = True 

        for config_path_str, var in self.config_vars.items():
            keys = config_path_str.split('.')
            value_to_save = var.get()
            
            current_val_in_config = fetchConfig(keys[0])
            if len(keys) > 1:
                if isinstance(current_val_in_config, dict):
                    current_val_in_config = current_val_in_config.get(keys[1])
                else: current_val_in_config = None
            
            if current_val_in_config == value_to_save: continue 

            if len(keys) == 1: 
                changed_configs[keys[0]] = value_to_save
            elif len(keys) == 2: 
                if keys[0] not in changed_configs: 
                    fetched_main_key_val = fetchConfig(keys[0])
                    if isinstance(fetched_main_key_val, dict):
                        changed_configs[keys[0]] = fetched_main_key_val.copy()
                    else: 
                        changed_configs[keys[0]] = {}
                
                if isinstance(changed_configs[keys[0]], dict):
                    changed_configs[keys[0]][keys[1]] = value_to_save
                else:
                    if logger: logger.error(f"Cannot apply nested config for {config_path_str}, parent is not a dict in changed_configs.")
                    config_update_success = False 
            else:
                if logger: logger.warning(f"Config path {config_path_str} too deep for simple apply logic.")
        
        for key, str_var in self.string_vars.items():
            new_val = str_var.get().strip() 
            current_val_from_config = fetchConfig(key)

            if key == "riotPath":
                if new_val != current_val_from_config: 
                    if not checkRiotClientPath(new_val):
                        messagebox.showerror(
                            "Invalid Riot Path",
                            f"The Riot Games path '{new_val}' does not appear to be a valid Riot Games installation folder. "
                            "Please ensure it points to your main 'Riot Games' folder, which should contain "
                            "a 'League of Legends' subfolder with 'LeagueClient.exe'.\n\n"
                            "The path has not been saved. Please correct it or use 'Browse...'.",
                            parent=self 
                        )
                        if logger: logger.warning(f"User attempted to set an invalid Riot Path: {new_val}. Reverted in UI.")
                        str_var.set(current_val_from_config) 
                        config_update_success = False 
                        continue 
                    else: 
                        changed_configs[key] = new_val

            elif new_val != current_val_from_config: 
                changed_configs[key] = new_val
        
        if not config_update_success:
            if logger: logger.warning("One or more settings were invalid and not saved. UI reverted for invalid fields.")
            self.status_label_var.set("Invalid setting(s) not saved.")
            self.after(4000, lambda: self.status_label_var.set(self.current_app_status))
            return 

        if changed_configs:
            for key_to_save, value_to_save in changed_configs.items():
                editConfig(key_to_save, value_to_save) 
            if logger: logger.info(f"Settings applied. Changes: {changed_configs}")
            self.status_label_var.set("Settings Applied!")
            self.after(3000, lambda: self.status_label_var.set(self.current_app_status))
        else:
            if logger: logger.info("No actual changes to apply to config.")


    def _revert_status_label(self):
        self.status_label_var.set(self.current_app_status)

    def _on_reset_config(self):
        if logger: logger.info("Reset Preferences button clicked.")
        else: print("Reset Preferences button clicked.")
        if messagebox.askyesno("Confirm Reset", "Are you sure you want to reset all preferences to their default values?", parent=self):
            resetConfig()
            self._refresh_ui_from_config() 
            if logger: logger.info("Preferences have been reset and UI refreshed.")
        else:
            if logger: logger.info("Preference reset cancelled by user.")

    def _on_map_icon_style_change(self):
        selected_style = self.config_vars["mapIconStyle"].get()
        if logger: logger.debug(f"Map icon style changed to: {selected_style}")
        self._update_map_icon_preview(selected_style)
        self._on_setting_change()

    def _update_map_icon_preview(self, style=None):
        if style is None:
            style = fetchConfig("mapIconStyle")
        preview_text = f"Preview:\n{style}"
        image_filename_map = {
            "Active": "active.png", "Empty": "empty.png", "Hover": "hover.png",
            "Defeat": "defeat.png", "Background": "background.jpg"
        }
        filename = image_filename_map.get(style)
        if not filename:
            if hasattr(self, 'map_icon_preview_label') and self.map_icon_preview_label.winfo_exists():
                self.map_icon_preview_label.config(image="", text="Preview N/A")
            if logger: logger.warning(f"No image filename defined for map icon style: {style}")
            return
        try:
            img_path = resourcePath(os.path.join("images", "previews", filename))
            if os.path.exists(img_path):
                pil_img_original = Image.open(img_path)
                bg_image = Image.new('RGB', PREVIEW_IMAGE_MAX_SIZE, DISCORD_DARK_GRAY_BG)
                pil_img_resized = pil_img_original.copy()
                pil_img_resized.thumbnail(PREVIEW_IMAGE_MAX_SIZE, Image.Resampling.LANCZOS)
                x_offset = (PREVIEW_IMAGE_MAX_SIZE[0] - pil_img_resized.width) // 2
                y_offset = (PREVIEW_IMAGE_MAX_SIZE[1] - pil_img_resized.height) // 2
                mask = Image.new('L', pil_img_resized.size, 0)
                draw = ImageDraw.Draw(mask)
                draw.rounded_rectangle((0, 0) + pil_img_resized.size, PREVIEW_CORNER_RADIUS, fill=255)
                if pil_img_resized.mode == 'RGBA':
                    bg_image.paste(pil_img_resized, (x_offset, y_offset), mask)
                else:
                    pil_img_rgba = pil_img_resized.convert("RGBA")
                    pil_img_rgba.putalpha(mask)
                    bg_image.paste(pil_img_rgba, (x_offset, y_offset), pil_img_rgba)
                self.map_icon_preview_tk = ImageTk.PhotoImage(bg_image)
                if hasattr(self, 'map_icon_preview_label') and self.map_icon_preview_label.winfo_exists():
                    self.map_icon_preview_label.config(image=self.map_icon_preview_tk, text="")
            else:
                if logger: logger.warning(f"Map icon preview image not found: {img_path}")
                if hasattr(self, 'map_icon_preview_label') and self.map_icon_preview_label.winfo_exists():
                    self.map_icon_preview_label.config(image="", text=preview_text)
        except FileNotFoundError:
            if logger: logger.warning(f"Map icon preview image file not found for style '{style}': {img_path}")
            if hasattr(self, 'map_icon_preview_label') and self.map_icon_preview_label.winfo_exists():
                self.map_icon_preview_label.config(image="", text="Img Not Found")
        except Exception as e:
            if logger: logger.warning(f"Could not update map icon preview for style '{style}': {e}", exc_info=True)
            if hasattr(self, 'map_icon_preview_label') and self.map_icon_preview_label.winfo_exists():
                self.map_icon_preview_label.config(image="", text="Preview Error")

    def _on_check_for_updates_button(self):
        if logger: logger.info("GUI: 'Check for Updates' button clicked, initiating update process via updater.py.")

        def gui_messagebox_callback(title, message, msg_type="info"):
            if not self.winfo_exists(): 
                logger.warning(f"GUI Messagebox Callback: SettingsWindow destroyed. Cannot show: {title} - {message}")
                if msg_type == "askyesno": return False 
                return True

            if msg_type == "askyesno":
                return messagebox.askyesno(title, message, parent=self)
            elif msg_type == "error":
                messagebox.showerror(title, message, parent=self)
            else: 
                messagebox.showinfo(title, message, parent=self)
            return True 

        update_thread = threading.Thread(
            target=updater.perform_update, 
            args=(gui_messagebox_callback, self.rpc_app_ref), 
            daemon=True
        )
        update_thread.start()
        if logger: logger.info("GUI: Updater thread started via 'Check for Updates' button.")


def _create_or_show_settings_window_in_tk_thread(parent_tk_root, current_status_getter, rpc_app_ref):
    global _settings_window_instance
    if logger: logger.info("Tkinter thread: _create_or_show_settings_window_in_tk_thread CALLED.")

    window_is_open_and_valid = False
    if _settings_window_instance:
        try:
            if _settings_window_instance.winfo_exists():
                window_is_open_and_valid = True
        except tk.TclError: 
            _settings_window_instance = None

    if window_is_open_and_valid:
        if logger: logger.info("Tkinter thread: Settings window already exists. Lifting and focusing.")
        _settings_window_instance.lift()
        _settings_window_instance.focus_force()
        if hasattr(_settings_window_instance, '_refresh_ui_from_config'):
            _settings_window_instance._refresh_ui_from_config() 
    else:
        if logger: logger.info("Tkinter thread: No existing valid settings window, creating new one.")
        _settings_window_instance = SettingsWindow(parent_tk_root, rpc_app_ref=rpc_app_ref, current_status_getter=current_status_getter) 
        if logger: logger.info("Tkinter thread: SettingsWindow instance CREATED.")

    if _settings_window_instance and current_status_getter : 
        current_status = current_status_getter()
        if _settings_window_instance.current_app_status != current_status:
            _settings_window_instance.current_app_status = current_status
            _settings_window_instance.status_label_var.set(current_status)


def launch_settings_gui(parent_root=None, current_status_getter=None, rpc_app_ref=None):
    global _persistent_tk_root
    if logger: logger.info("launch_settings_gui CALLED (scheduling on Tkinter thread).")

    if not ensure_tkinter_thread_running():
        logger.error("launch_settings_gui: Failed to ensure Tkinter thread is running. Cannot open GUI.")
        return None 

    if not _persistent_tk_root or not _persistent_tk_root.winfo_exists():
        logger.error("launch_settings_gui: Persistent Tk root is not available or destroyed. Cannot open GUI.")
        return None

    try:
        _persistent_tk_root.after(0, lambda: _create_or_show_settings_window_in_tk_thread(
            _persistent_tk_root, current_status_getter, rpc_app_ref
        ))
        if logger: logger.info("launch_settings_gui: Scheduled _create_or_show_settings_window_in_tk_thread.")
    except tk.TclError as e:
        logger.error(f"launch_settings_gui: TclError scheduling window creation (root likely destroyed): {e}", exc_info=True)
        global _tkinter_thread
        _tkinter_thread = None 
        if ensure_tkinter_thread_running() and _persistent_tk_root and _persistent_tk_root.winfo_exists():
            logger.info("launch_settings_gui: Retrying to schedule window creation after restarting Tkinter thread.")
            _persistent_tk_root.after(0, lambda: _create_or_show_settings_window_in_tk_thread(
                _persistent_tk_root, current_status_getter, rpc_app_ref
            ))
        else:
            logger.error("launch_settings_gui: Failed to restart Tkinter thread or root still invalid after retry.")
    except Exception as e:
        logger.error(f"launch_settings_gui: Unexpected error scheduling window creation: {e}", exc_info=True)

    return None 

def schedule_settings_window_close():
    global _settings_window_instance, _persistent_tk_root
    if logger: logger.info("schedule_settings_window_close CALLED.")

    if _persistent_tk_root and _persistent_tk_root.winfo_exists():
        if _settings_window_instance and _settings_window_instance.winfo_exists():
            if logger: logger.info("Scheduling SettingsWindow._on_close_window_button on Tkinter thread.")
            _persistent_tk_root.after(0, _settings_window_instance._on_close_window_button)
        else:
            if logger: logger.info("Settings window instance does not exist or already destroyed. No close action scheduled.")
    else:
        if logger: logger.warning("Persistent Tk root not available for scheduling window close.")

