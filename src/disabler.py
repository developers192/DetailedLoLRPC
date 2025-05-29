import json
import os
import time

from .utilities import fetchConfig, procPath, logger, addLog

# Hardcoded constants
LEAGUE_CLIENT_EXECUTABLE = "LeagueClient.exe"
PLUGIN_NAME_TO_DISABLE = "rcp-be-lol-discord-rp"
LOOP_TIMEOUT_SECONDS = 60

def disableNativePresence():
    """
    Attempts to disable League of Legends' native Discord Rich Presence
    by modifying the plugin-manifest.json file.
    This function is intended to be run in a separate process.
    """
    logger.info(f"Native Discord Presence Disabler process started. Target plugin: {PLUGIN_NAME_TO_DISABLE}")
    addLog(f"Disabler: Process started. Target: {PLUGIN_NAME_TO_DISABLE}", level="INFO")

    riot_path = fetchConfig("riotPath")
    if not riot_path or not os.path.isdir(riot_path):
        logger.error(f"Invalid Riot Games path from config: '{riot_path}'. Disabler cannot proceed.")
        addLog(f"Disabler Error: Invalid Riot Path '{riot_path}'. Cannot proceed.", level="ERROR")
        return

    plugins_dir = os.path.join(riot_path, "League of Legends", "Plugins")
    manifest_path = os.path.join(plugins_dir, "plugin-manifest.json")

    logger.debug(f"Plugin manifest path: {manifest_path}")

    if not os.path.exists(manifest_path):
        logger.warning(f"Plugin manifest file not found at {manifest_path}. Cannot disable native presence.")
        addLog(f"Disabler Warning: Manifest not found at {manifest_path}.", level="WARNING")
        if not os.path.exists(plugins_dir):
            try:
                os.makedirs(plugins_dir)
                logger.info(f"Created missing Plugins directory: {plugins_dir}")
            except OSError as e:
                logger.error(f"Failed to create Plugins directory {plugins_dir}: {e}")
        return

    modified_content = None
    try:
        with open(manifest_path, "r", encoding='utf-8') as f:
            content = json.load(f)
        
        if not isinstance(content, dict) or "plugins" not in content or not isinstance(content["plugins"], list):
            logger.error(f"Invalid plugin manifest format in {manifest_path}. 'plugins' key missing or not a list.")
            addLog(f"Disabler Error: Invalid manifest format in {manifest_path}.", level="ERROR")
            return

        original_plugins = content["plugins"]
        updated_plugins = [p for p in original_plugins if not (isinstance(p, dict) and p.get("name") == PLUGIN_NAME_TO_DISABLE)]

        if len(updated_plugins) < len(original_plugins):
            logger.info(f"Plugin '{PLUGIN_NAME_TO_DISABLE}' found and marked for removal from manifest.")
            addLog(f"Disabler: Plugin '{PLUGIN_NAME_TO_DISABLE}' found for removal.", level="INFO")
            content["plugins"] = updated_plugins
            modified_content = content
        else:
            logger.info(f"Plugin '{PLUGIN_NAME_TO_DISABLE}' not found in manifest or already removed.")
            addLog(f"Disabler: Plugin '{PLUGIN_NAME_TO_DISABLE}' not found or already removed.", level="INFO")
            modified_content = content 

    except FileNotFoundError:
        logger.error(f"Plugin manifest file not found at {manifest_path} during read attempt.")
        addLog(f"Disabler Error: Manifest not found at {manifest_path} (read).", level="ERROR")
        return
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from plugin manifest {manifest_path}: {e}")
        addLog(f"Disabler Error: JSON decode error in {manifest_path}: {str(e)}", level="ERROR")
        return
    except Exception as e: 
        logger.error(f"Unexpected error processing plugin manifest {manifest_path}: {e}", exc_info=True)
        addLog(f"Disabler Error: Unexpected error processing manifest: {str(e)}", level="ERROR")
        return

    if modified_content is None:
        logger.warning("No modified content to write. Exiting disabler process.")
        addLog("Disabler Warning: No modified content generated.", level="WARNING")
        return

    start_time = time.time()
    logger.info("Starting loop to continuously disable native presence (no sleep interval).")
    addLog("Disabler: Starting write loop (no sleep).", level="DEBUG")

    while True:
        try:
            if not os.path.exists(os.path.dirname(manifest_path)):
                os.makedirs(os.path.dirname(manifest_path))
                logger.info(f"Re-created directory for manifest: {os.path.dirname(manifest_path)}")

            with open(manifest_path, "w", encoding='utf-8') as f:
                json.dump(modified_content, f, indent=2) 
            logger.debug(f"Successfully wrote modified manifest to {manifest_path}")
        except PermissionError:
            logger.warning(f"Permission denied while trying to write to {manifest_path}. Retrying.")
            addLog(f"Disabler Warning: Permission denied writing to {manifest_path}.", level="WARNING")
        except FileNotFoundError: 
            logger.warning(f"Manifest file {manifest_path} disappeared before write. Retrying.")
            addLog(f"Disabler Warning: Manifest file disappeared before write at {manifest_path}.", level="WARNING")
        except Exception as e:
            logger.error(f"Error writing modified manifest to {manifest_path}: {e}", exc_info=True)
            addLog(f"Disabler Error: Writing manifest: {str(e)}", level="ERROR")

        if procPath(LEAGUE_CLIENT_EXECUTABLE):
            logger.info(f"{LEAGUE_CLIENT_EXECUTABLE} detected. Stopping disabler loop.")
            addLog("Disabler: LeagueClient.exe detected. Stopping.", level="INFO")
            break
        
        if time.time() - start_time > LOOP_TIMEOUT_SECONDS:
            logger.info(f"Disabler loop timed out after {LOOP_TIMEOUT_SECONDS} seconds.")
            addLog(f"Disabler: Loop timed out after {LOOP_TIMEOUT_SECONDS}s.", level="INFO")
            break

    logger.info("Native Discord Presence Disabler process finished.")
    addLog("Disabler: Process finished.", level="INFO")

if __name__ == '__main__':
    print("Running disabler.py directly for testing purposes.")
    disableNativePresence()
    print("Disabler test finished.")
