import sys
import os
import json
import pickle 
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog
import logging 
import threading 
import psutil 
from psutil import process_iter, NoSuchProcess, AccessDenied, ZombieProcess
from requests import get, exceptions as requests_exceptions
from dotenv import load_dotenv
from base64 import b64decode

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)] 
)
logger = logging.getLogger(__name__)


def resourcePath(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError: 
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

env_path = resourcePath(".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
    logger.info(".env file loaded.")
else:
    logger.warning(f".env file not found at {env_path}. Some features might not work.")

VERSION = "v5.0.1"
REPOURL = "https://github.com/developers192/DetailedLoLRPC/"
GITHUBURL = REPOURL + "releases/latest"
ISSUESURL = REPOURL + "issues/new"
ANIMATEDSPLASHESURL = "https://raw.githubusercontent.com/developers192/DetailedLoLRPC/refs/heads/master/animatedSplashes/"
ANIMATEDSPLASHESIDS = [99007, 360030, 147001, 147002, 147003, 103086, 21016, 77003, 37006, 81005]

APPDATA_DIRNAME = "DetailedLoLRPC"
APPDATA_PATH = os.path.join(os.getenv("APPDATA"), APPDATA_DIRNAME)
CONFIG_FILENAME = "config.json"
LOG_FILENAME = "session.log"
LOCK_FILENAME = "detailedlolrpc.lock" 

CONFIG_FILE_PATH = os.path.join(APPDATA_PATH, CONFIG_FILENAME)
LOG_FILE_PATH = os.path.join(APPDATA_PATH, LOG_FILENAME)
LOCK_FILE_PATH = os.path.join(APPDATA_PATH, LOCK_FILENAME) 
OLD_CONFIG_PICKLE_PATH = os.path.join(APPDATA_PATH, "config.dlrpc") 


DEFAULT_CONFIG = {
    "useSkinSplash": True,
    "showViewArtButton": False,
    "animatedSplash": True,
    "showPartyInfo": True,
    "idleStatus": 0, 
    "mapIconStyle": "Active", 
    "stats": {"kda": True, "cs": True, "level": True},
    "showRanks": {
        "RANKED_SOLO_5x5": True,
        "RANKED_FLEX_SR": True,
        "RANKED_TFT": True,
        "RANKED_TFT_DOUBLE_UP": True
    },
    "rankedStats": {"lp": True, "w": True, "l": True},
    "showWindowOnStartup": True,
    "checkForUpdatesOnStartup": True,
    "riotPath": "", 
    "theme": "System", 
    "idleCustomImageLink": "",
    "idleCustomShowStatusCircle": True,
    "idleCustomText": "Chilling...",
    "idleCustomShowTimeElapsed": False,
    "isRpcMuted": False,
    "idleProfileInfoDisplay": { # New section for profile info idle display
        "showRiotId": True,
        "showTagLine": True,
        "showSummonerLevel": False
    },
}

try:
    CLIENTID_B64 = os.getenv("CLIENTID")
    if not CLIENTID_B64:
        logger.critical("CLIENTID is not set in .env file. Application cannot start.")
        try:
            root_err = tk.Tk()
            root_err.withdraw()
            messagebox.showerror("DetailedLoLRPC - Critical Error", "CLIENTID is missing in the .env file.\nPlease ensure it exists and is correctly base64 encoded.\nThe application will now exit.")
            root_err.destroy()
        except tk.TclError:
            print("CRITICAL ERROR: CLIENTID missing in .env and Tkinter is unavailable to show an error dialog.")
        sys.exit(1)
    CLIENTID = b64decode(CLIENTID_B64).decode("utf-8")
    if not CLIENTID:
        raise ValueError("Decoded CLIENTID is empty.")
except Exception as e:
    logger.critical(f"Error decoding CLIENTID from .env: {e}")
    try:
        root_err = tk.Tk()
        root_err.withdraw()
        messagebox.showerror("DetailedLoLRPC - Critical Error", f"Could not decode CLIENTID: {e}\nPlease check your .env file.\nThe application will now exit.")
        root_err.destroy()
    except tk.TclError:
        print(f"CRITICAL ERROR: Could not decode CLIENTID ({e}) and Tkinter is unavailable.")
    sys.exit(1)

_config_cache = None
_on_config_changed_callbacks = [] 

def _ensure_appdata_dir():
    os.makedirs(APPDATA_PATH, exist_ok=True)

def is_process_running(pid, name_check=None):
    try:
        proc = psutil.Process(pid)
        if name_check:
            exe_name = os.path.basename(sys.executable if getattr(sys, 'frozen', False) else __file__)
            if name_check.lower() in proc.name().lower() or \
               (proc.exe() and name_check.lower() in os.path.basename(proc.exe()).lower()):
                return True
            return False 
        return True 
    except (NoSuchProcess, AccessDenied, ZombieProcess):
        return False

def check_and_create_lock():
    _ensure_appdata_dir()
    current_pid = os.getpid()
    app_name_for_check = os.path.basename(sys.executable if getattr(sys, 'frozen', False) else "DetailedLoLRPC.py") 

    if os.path.exists(LOCK_FILE_PATH):
        try:
            with open(LOCK_FILE_PATH, "r") as f:
                locked_pid_str = f.read().strip()
                if locked_pid_str:
                    locked_pid = int(locked_pid_str)
                    if locked_pid != current_pid and is_process_running(locked_pid, name_check=app_name_for_check):
                        logger.warning(f"Another instance (PID: {locked_pid}) is already running. Lock file: {LOCK_FILE_PATH}")
                        return False 
                    else:
                        logger.info(f"Stale lock file found (PID: {locked_pid} not running or not this app). Overwriting.")
                else:
                    logger.info("Lock file was empty. Overwriting.")
        except (IOError, ValueError) as e:
            logger.warning(f"Error reading lock file {LOCK_FILE_PATH}: {e}. Assuming stale and attempting to overwrite.")
        
        try:
            os.remove(LOCK_FILE_PATH)
        except OSError as e:
            logger.error(f"Could not remove stale/corrupt lock file {LOCK_FILE_PATH}: {e}. This might prevent startup.")
            return False 

    try:
        with open(LOCK_FILE_PATH, "w") as f: 
            f.write(str(current_pid))
        logger.info(f"Lock file created successfully at {LOCK_FILE_PATH} with PID {current_pid}.")
        return True
    except IOError as e:
        logger.error(f"Could not create or write to lock file {LOCK_FILE_PATH}: {e}")
        try:
            with open(LOCK_FILE_PATH, "r") as f:
                locked_pid_str = f.read().strip()
                if locked_pid_str and int(locked_pid_str) != current_pid:
                    logger.warning(f"Lock file appeared after check, likely race condition. Another instance (PID: {locked_pid_str}) may be running.")
                    return False
        except: pass 
        return False


def release_lock():
    try:
        if os.path.exists(LOCK_FILE_PATH):
            current_pid = os.getpid()
            pid_in_file = -1
            try:
                with open(LOCK_FILE_PATH, "r") as f:
                    pid_in_file = int(f.read().strip())
            except (IOError, ValueError):
                logger.warning(f"Could not read PID from lock file {LOCK_FILE_PATH} during release attempt.")
            
            if pid_in_file == current_pid:
                os.remove(LOCK_FILE_PATH)
                logger.info(f"Lock file {LOCK_FILE_PATH} released by PID {current_pid}.")
            elif pid_in_file != -1: 
                logger.warning(f"Lock file {LOCK_FILE_PATH} owned by another PID ({pid_in_file}). Not releasing.")
            else: 
                logger.warning(f"Lock file {LOCK_FILE_PATH} exists but PID unreadable. Not releasing automatically.")
        else:
            logger.info(f"Lock file {LOCK_FILE_PATH} not found during release attempt (already released or never created).")

    except OSError as e:
        logger.error(f"Error releasing lock file {LOCK_FILE_PATH}: {e}")
    except Exception as e: 
        logger.error(f"Unexpected error during lock release: {e}", exc_info=True)


def _migrate_pickle_to_json():
    global _config_cache
    if os.path.exists(OLD_CONFIG_PICKLE_PATH) and not os.path.exists(CONFIG_FILE_PATH):
        logger.warning("Old .dlrpc config found. Attempting migration to .json...")
        try:
            with open(OLD_CONFIG_PICKLE_PATH, "rb") as pf:
                old_data = pickle.load(pf)
            
            migrated_config = DEFAULT_CONFIG.copy()
            migrated_config.update(old_data) 
            if "closeSettingsOnLeagueOpen" in migrated_config: 
                del migrated_config["closeSettingsOnLeagueOpen"]


            with open(CONFIG_FILE_PATH, "w", encoding='utf-8') as jf:
                json.dump(migrated_config, jf, indent=4)
            
            os.rename(OLD_CONFIG_PICKLE_PATH, f"{OLD_CONFIG_PICKLE_PATH}.migrated_to_json")
            logger.info("Configuration successfully migrated from pickle to JSON.")
            _config_cache = migrated_config
            return True
        except (pickle.UnpicklingError, IOError, OSError, AttributeError) as e:
            logger.error(f"Failed to migrate config from pickle to JSON: {e}. A new default config will be created.")
            try:
                os.rename(OLD_CONFIG_PICKLE_PATH, f"{OLD_CONFIG_PICKLE_PATH}.corrupted")
            except OSError:
                pass
    return False

def _load_config():
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    _ensure_appdata_dir()
    
    if not _migrate_pickle_to_json() and not os.path.exists(CONFIG_FILE_PATH):
        logger.info("Config file not found. Creating default config.")
        _config_cache = DEFAULT_CONFIG.copy()
        if not _config_cache.get("riotPath"): 
            _config_cache["riotPath"] = getRiotPath()
        _save_config_to_file()
        return _config_cache

    try:
        with open(CONFIG_FILE_PATH, "r", encoding='utf-8') as f:
            loaded_config = json.load(f)
        
        _config_cache = DEFAULT_CONFIG.copy() 
        _config_cache.update(loaded_config) 
        
        config_changed_by_cleanup = False
        if "closeSettingsOnLeagueOpen" in _config_cache:
            del _config_cache["closeSettingsOnLeagueOpen"]
            config_changed_by_cleanup = True

        # Ensure idleProfileInfoDisplay exists and has all keys
        if not isinstance(_config_cache.get("idleProfileInfoDisplay"), dict):
            _config_cache["idleProfileInfoDisplay"] = DEFAULT_CONFIG["idleProfileInfoDisplay"].copy()
            config_changed_by_cleanup = True
        else:
            for key, default_val in DEFAULT_CONFIG["idleProfileInfoDisplay"].items():
                if key not in _config_cache["idleProfileInfoDisplay"]:
                    _config_cache["idleProfileInfoDisplay"][key] = default_val
                    config_changed_by_cleanup = True


        current_riot_path = _config_cache.get("riotPath", "")
        if not current_riot_path or not checkRiotClientPath(current_riot_path):
            logger.warning("Riot path in config is missing or invalid. Re-fetching.")
            _config_cache["riotPath"] = getRiotPath()
            config_changed_by_cleanup = True 
        
        if config_changed_by_cleanup:
            _save_config_to_file()


        logger.info("Configuration loaded successfully.")
        return _config_cache
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading config file {CONFIG_FILE_PATH}: {e}. Backing up and using defaults.")
        try:
            corrupted_backup_path = f"{CONFIG_FILE_PATH}.corrupted_{int(os.path.getmtime(CONFIG_FILE_PATH) if os.path.exists(CONFIG_FILE_PATH) else 0)}"
            os.rename(CONFIG_FILE_PATH, corrupted_backup_path)
            logger.info(f"Corrupted config backed up to {corrupted_backup_path}")
        except OSError as bak_e:
            logger.error(f"Could not backup corrupted config file: {bak_e}")
        
        _config_cache = DEFAULT_CONFIG.copy()
        if not _config_cache.get("riotPath"):
            _config_cache["riotPath"] = getRiotPath()
        _save_config_to_file()
        return _config_cache

def _save_config_to_file():
    if _config_cache is None:
        logger.warning("Attempted to save config, but cache is None.")
        return False
    _ensure_appdata_dir()
    try:
        with open(CONFIG_FILE_PATH, "w", encoding='utf-8') as f:
            json.dump(_config_cache, f, indent=4, sort_keys=True)
        logger.info(f"Configuration saved to {CONFIG_FILE_PATH}")
        return True
    except IOError as e:
        logger.error(f"Failed to save configuration to {CONFIG_FILE_PATH}: {e}")
        return False

def register_config_changed_callback(callback):
    global _on_config_changed_callbacks
    if callback not in _on_config_changed_callbacks:
        _on_config_changed_callbacks.append(callback)
        logger.info(f"Config change callback registered: {callback}")
    else:
        logger.debug(f"Config change callback already registered: {callback}")

def unregister_config_changed_callback(callback):
    global _on_config_changed_callbacks
    try:
        _on_config_changed_callbacks.remove(callback)
        logger.info(f"Config change callback unregistered: {callback}")
    except ValueError:
        logger.warning(f"Attempted to unregister a callback that was not registered: {callback}")

def _execute_config_changed_callbacks():
    global _on_config_changed_callbacks
    if not _on_config_changed_callbacks:
        logger.debug("No config change callbacks to execute.")
        return
    
    logger.debug(f"Executing {_on_config_changed_callbacks} config change callbacks...")
    for callback in list(_on_config_changed_callbacks): 
        try:
            callback()
            logger.debug(f"Executed config change callback: {callback}")
        except Exception as e:
            logger.error(f"Error executing config changed callback {callback}: {e}", exc_info=True)


def fetchConfig(entry_key):
    config = _load_config() 
    
    if '.' in entry_key:
        keys = entry_key.split('.')
        main_key = keys[0]
        sub_key = keys[1]
        
        default_main_val = DEFAULT_CONFIG.get(main_key, {})
        config_main_val = config.get(main_key, {})

        if isinstance(default_main_val, dict) and isinstance(config_main_val, dict):
            return config_main_val.get(sub_key, default_main_val.get(sub_key))
        else: 
            # This case might happen if config_main_val is not a dict but default is.
            # Or if default_main_val itself is not a dict (though for idleProfileInfoDisplay it is)
            if isinstance(default_main_val, dict):
                return default_main_val.get(sub_key)
            return None # Should not happen for well-defined defaults
    
    return config.get(entry_key, DEFAULT_CONFIG.get(entry_key))


def editConfig(entry_key, value):
    global _config_cache
    _load_config() 
    
    changed = False
    if '.' in entry_key:
        keys = entry_key.split('.')
        main_key = keys[0]
        sub_key = keys[1]
        if main_key not in _config_cache or not isinstance(_config_cache[main_key], dict):
            _config_cache[main_key] = {} 
        
        if _config_cache[main_key].get(sub_key) != value:
            _config_cache[main_key][sub_key] = value
            changed = True
    else:
        if _config_cache.get(entry_key) != value:
            _config_cache[entry_key] = value
            changed = True

    if changed:
        if _save_config_to_file(): 
            _execute_config_changed_callbacks() 
    else:
        logger.debug(f"Config for '{entry_key}' not changed. Skipping save and callback.")


def resetConfig():
    global _config_cache
    _ensure_appdata_dir()
    _config_cache = DEFAULT_CONFIG.copy()
    _config_cache["riotPath"] = getRiotPath() 
    if _save_config_to_file():
        _execute_config_changed_callbacks() 
    logger.info("Configuration has been reset to defaults.")

_log_file_handler = None

def setup_file_logging():
    global _log_file_handler
    _ensure_appdata_dir()
    if _log_file_handler: 
        logging.getLogger().removeHandler(_log_file_handler)

    _log_file_handler = logging.FileHandler(LOG_FILE_PATH, mode='a', encoding='utf-8') 
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _log_file_handler.setFormatter(formatter)
    logging.getLogger().addHandler(_log_file_handler) 
    logger.info(f"File logging enabled at {LOG_FILE_PATH}")

def resetLog():
    _ensure_appdata_dir()
    try:
        global _log_file_handler
        if _log_file_handler:
            _log_file_handler.close()
            logging.getLogger().removeHandler(_log_file_handler)
            _log_file_handler = None

        with open(LOG_FILE_PATH, "w", encoding='utf-8') as f: 
            f.write(f"--- Log Session Started: {logging.Formatter().formatTime(logging.makeLogRecord({}))} ---\n")
        logger.info(f"Log file reset: {LOG_FILE_PATH}")
        setup_file_logging()
    except IOError as e:
        print(f"ERROR: Could not reset log file {LOG_FILE_PATH}: {e}")

def addLog(data, level="INFO"):
    log_message = json.dumps(data, indent=2) if isinstance(data, dict) else str(data)
    log_level_int = getattr(logging, level.upper(), logging.INFO)
    logger.log(log_level_int, log_message)

def yesNoBox(msg, title="DetailedLoLRPC"):
    if threading.current_thread() is not threading.main_thread():
        logger.warning("yesNoBox called from a non-main thread. This can lead to instability with Tkinter.")
    
    temp_root = None 
    result = False 
    try:
        temp_root = tk.Tk()
        temp_root.withdraw()
        temp_root.attributes('-topmost', True) 
        try:
            icon_path = resourcePath("icon.ico")
            if os.path.exists(icon_path):
                temp_root.iconbitmap(icon_path)
        except tk.TclError:
            logger.warning("Could not set icon for temporary Tk root in yesNoBox.")
            pass 
        
        temp_root.update_idletasks() 
        temp_root.update()        

        result = messagebox.askyesno(title, msg, parent=temp_root)
    except RuntimeError as e:
        if "main thread is not in main loop" in str(e) or "Calling Tcl from different appartment" in str(e):
            logger.error(f"Tkinter RuntimeError in yesNoBox (likely called from wrong thread): {e}")
        else:
            raise 
    except Exception as e:
        logger.error(f"Unexpected error in yesNoBox: {e}", exc_info=True)
    finally:
        if temp_root and isinstance(temp_root, tk.Tk):
            try:
                if temp_root.winfo_exists(): 
                    temp_root.destroy()
            except tk.TclError: 
                logger.warning("TclError during temp_root.destroy() in yesNoBox.")
    return result

def inputBox(prompt_msg, title="DetailedLoLRPC"):
    if threading.current_thread() is not threading.main_thread():
        logger.warning("inputBox called from a non-main thread. This can lead to instability with Tkinter.")
    
    temp_root = None 
    result = None 
    try:
        temp_root = tk.Tk()
        temp_root.withdraw()
        temp_root.attributes('-topmost', True)
        try:
            icon_path = resourcePath("icon.ico")
            if os.path.exists(icon_path):
                temp_root.iconbitmap(icon_path)
        except tk.TclError:
            logger.warning("Could not set icon for temporary Tk root in inputBox.")
            pass
        
        temp_root.update_idletasks()
        temp_root.update()

        result = simpledialog.askstring(title, prompt_msg, parent=temp_root)
    except RuntimeError as e:
        if "main thread is not in main loop" in str(e) or "Calling Tcl from different appartment" in str(e):
            logger.error(f"Tkinter RuntimeError in inputBox (likely called from wrong thread): {e}")
        else:
            raise
    except Exception as e:
        logger.error(f"Unexpected error in inputBox: {e}", exc_info=True)
    finally:
        if temp_root and isinstance(temp_root, tk.Tk):
            try:
                if temp_root.winfo_exists():
                    temp_root.destroy()
            except tk.TclError:
                logger.warning("TclError during temp_root.destroy() in inputBox.")
    return result

LEAGUE_CLIENT_EXECUTABLE = "LeagueClient.exe" 

def procPath(process_name):
    try:
        for proc in process_iter(['name', 'exe']):
            if proc.info['name'] and proc.info['name'].lower() == process_name.lower():
                if proc.info['exe']: 
                    return proc.info['exe']
    except (NoSuchProcess, AccessDenied, ZombieProcess, TypeError) as e: 
        logger.warning(f"Error iterating processes for '{process_name}': {e}")
    return None 

def checkRiotClientPath(path_to_check):
    if not path_to_check or not os.path.isdir(path_to_check):
        return False
    league_client_exe_path = os.path.join(path_to_check, "League of Legends", LEAGUE_CLIENT_EXECUTABLE)
    if os.path.exists(league_client_exe_path):
        return True
    if os.path.isdir(os.path.join(path_to_check, "League of Legends")) and \
       os.path.isdir(os.path.join(path_to_check, "Riot Client")):
        return True
    logger.debug(f"Path {path_to_check} failed Riot Client path check. Missing {league_client_exe_path} or Riot Client folder.")
    return False

def getRiotPath():
    riot_client_services_exe = procPath("RiotClientServices.exe")
    if riot_client_services_exe:
        potential_riot_games_path = os.path.dirname(os.path.dirname(riot_client_services_exe))
        if checkRiotClientPath(potential_riot_games_path):
            logger.info(f"Automatically detected Riot Games path: {potential_riot_games_path}")
            return potential_riot_games_path
        else:
            logger.warning(f"Found RiotClientServices.exe at {riot_client_services_exe}, but derived path {potential_riot_games_path} seems invalid.")

    logger.info("RiotClientServices.exe not found or path derived from it is invalid. Prompting user.")
    while True:
        user_path = inputBox(
            'Riot Client process was not found or its path is unusual.\n'
            'Please enter the path to your "Riot Games" installation folder.\n'
            r'(Example: C:\Riot Games)',
            title="DetailedLoLRPC - Riot Games Path"
        )
        if user_path is None: 
            logger.critical("User cancelled Riot Path input during setup. Application cannot continue.")
            try:
                root_err = tk.Tk()
                root_err.withdraw()
                messagebox.showerror("DetailedLoLRPC - Error", "Riot Games path is required.\nExiting application.")
                root_err.destroy()
            except: pass
            sys.exit(1) 
        
        user_path = user_path.strip().strip('"') 
        if checkRiotClientPath(user_path):
            logger.info(f"User provided valid Riot Games path: {user_path}")
            return user_path
        else:
            root_warn = tk.Tk(); root_warn.withdraw(); root_warn.attributes('-topmost', True)
            messagebox.showwarning(
                "DetailedLoLRPC - Invalid Path",
                f"The path '{user_path}' does not appear to be a valid Riot Games installation folder.\n\n"
                "It should typically contain a 'League of Legends' subfolder with 'LeagueClient.exe'.\n"
                "Please try again.",
                parent=root_warn 
            )
            root_warn.destroy()


def isOutdated():
    logger.info(f"Checking for updates. Current version: {VERSION}")
    try:
        api_url = f"https://api.github.com/repos/{REPOURL.split('github.com/')[1].strip('/')}/releases/latest"
        response = get(api_url, timeout=10) 
        response.raise_for_status() 
        release_data = response.json()
        latest_version_tag = release_data.get("tag_name")

        if not latest_version_tag:
            logger.warning("Could not determine latest version tag from GitHub API response. Trying redirect method.")
            response_redirect = get(GITHUBURL, timeout=10, allow_redirects=True)
            response_redirect.raise_for_status()
            latest_version_tag = response_redirect.url.split(r"/")[-1]

        if latest_version_tag and latest_version_tag.lstrip('v') != VERSION.lstrip('v'): 
            logger.info(f"Update available: Latest version is {latest_version_tag}, current is {VERSION}.")
            return latest_version_tag
        elif latest_version_tag:
            logger.info(f"Application is up to date. (Current: {VERSION}, Latest: {latest_version_tag})")
        else:
            logger.warning("Could not determine latest version from GitHub.")
        return False
    except requests_exceptions.Timeout:
        logger.error("Timeout while checking for updates.")
        return False
    except requests_exceptions.RequestException as e:
        logger.error(f"Could not check for updates due to a network or request error: {e}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON response from GitHub API: {e}")
        return False

_initialized = False
def init():
    global _initialized
    if _initialized:
        logger.debug("Utilities already initialized.")
        return

    _ensure_appdata_dir() 
    setup_file_logging() 
    resetLog() 

    logger.info(f"--- DetailedLoLRPC Utilities Initializing (Version: {VERSION}) ---")
    _load_config() 
    logger.info(f"Configuration loaded. Riot Path set to: {fetchConfig('riotPath')}")
    _initialized = True
    logger.info("--- DetailedLoLRPC Utilities Initialized Successfully ---")

