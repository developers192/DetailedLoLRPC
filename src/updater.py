import sys
import os
import requests
import shutil
import subprocess
import logging
import tempfile
import json 
import asyncio 

from .utilities import logger, VERSION, REPOURL, GITHUBURL, yesNoBox, addLog, resourcePath

EXPECTED_ASSET_NAME = "DetailedLoLRPC.exe" 
CURL_EXE_NAME = "curl.exe"

def is_running_as_compiled():
    """Check if the application is running as a PyInstaller bundle."""
    return getattr(sys, 'frozen', False)

def get_latest_release_info():
    """Fetches the latest release information from GitHub."""
    repo_path = REPOURL.split('github.com/')[-1].strip('/')
    if not repo_path:
        logger.error("Updater: REPOURL is not in the expected format.")
        return None
        
    api_url = f"https://api.github.com/repos/{repo_path}/releases/latest"
    logger.info(f"Updater: Fetching latest release info from {api_url}")
    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Updater: Error fetching release info: {e}")
        return None
    except json.JSONDecodeError as e: 
        logger.error(f"Updater: Error parsing release info JSON: {e}")
        return None

def perform_update(show_messagebox_callback=None, rpc_app_ref=None):
    """
    Main function to check for updates, then hands off to a batch script for download and replacement.
    Returns True if an update process was started that requires app exit, False otherwise.
    """
    if not is_running_as_compiled():
        logger.error("Updater: Update feature is only available for the compiled application.")
        if show_messagebox_callback:
            show_messagebox_callback("Update Error", "Update feature is only available for the compiled application.")
        return False

    logger.info("Updater: Checking for updates...")

    release_info = get_latest_release_info()
    if not release_info:
        logger.error("Updater: Could not fetch latest release information.")
        if show_messagebox_callback:
            show_messagebox_callback("Update Error", "Could not fetch latest release information from GitHub.")
        return False

    latest_version_tag_name = release_info.get("tag_name")
    if not latest_version_tag_name:
        logger.error("Updater: 'tag_name' not found in release information.")
        if show_messagebox_callback:
            show_messagebox_callback("Update Error", "Could not determine latest version from GitHub.")
        return False

    latest_version_str = latest_version_tag_name.lstrip('v')
    current_version_str = VERSION.lstrip('v')

    logger.info(f"Updater: Current version: {current_version_str}, Latest GitHub version tag: {latest_version_tag_name} (parsed as {latest_version_str})")

    try:
        current_v_tuple = tuple(map(int, current_version_str.split('.')))
        latest_v_tuple = tuple(map(int, latest_version_str.split('.')))
        if latest_v_tuple <= current_v_tuple:
            logger.info("Updater: Application is up to date.")
            if show_messagebox_callback:
                show_messagebox_callback("Up to Date", f"You are running the latest version ({VERSION}).")
            return False
    except ValueError:
        logger.warning(f"Updater: Could not parse versions for numeric comparison ('{current_version_str}' vs '{latest_version_str}'). Falling back to string comparison.")
        if latest_version_str <= current_version_str:
            logger.info("Updater: Application is up to date (string comparison).")
            if show_messagebox_callback:
                show_messagebox_callback("Up to Date", f"You are running the latest version ({VERSION}).")
            return False
    except Exception as e_ver:
        logger.error(f"Updater: Error comparing versions ('{current_version_str}' vs '{latest_version_str}'): {e_ver}")
        if show_messagebox_callback:
            show_messagebox_callback("Update Error", "Could not compare versions. Please check manually.")
        return False

    if show_messagebox_callback:
        prompt_user_callback = show_messagebox_callback
    else:
        def fallback_prompt(title, msg, msg_type="info"):
            if msg_type == "askyesno":
                return yesNoBox(msg, title) 
            else: 
                log_level = logging.ERROR if msg_type == "error" else logging.INFO
                logger.log(log_level, f"Updater Fallback Prompt ({title}): {msg}")
                return True 
        prompt_user_callback = fallback_prompt

    if not prompt_user_callback(
        "Update Available",
        f"A new version ({latest_version_tag_name}) is available. Download and update now?\n\n"
        "The application will close to perform the update.",
        msg_type="askyesno"
    ):
        logger.info("Updater: User declined update.")
        return False
    
    asset_url = f"{REPOURL.rstrip('/')}/releases/download/{latest_version_tag_name}/{EXPECTED_ASSET_NAME}"
    logger.info(f"Updater: Constructed asset URL for batch script: {asset_url}")
    
    temp_download_dir = tempfile.mkdtemp(prefix="dlrpc_update_")
    downloaded_asset_temp_path = os.path.join(temp_download_dir, EXPECTED_ASSET_NAME)

    current_exe_path = sys.executable
    
    bundled_curl_path = ""
    try:
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_dir_for_curl = sys._MEIPASS
        else:
            base_dir_for_curl = os.path.dirname(os.path.abspath(__file__))
        
        potential_curl_path = os.path.join(base_dir_for_curl, "bin", CURL_EXE_NAME)
        if os.path.exists(potential_curl_path):
            bundled_curl_path = potential_curl_path
            logger.info(f"Updater: Found bundled curl at: {bundled_curl_path}")
        else:
            logger.warning(f"Updater: Bundled curl not found at {potential_curl_path}. Will rely on curl in PATH.")
            bundled_curl_path = "curl" 
    except Exception as e_curl_path:
        logger.error(f"Updater: Error determining curl path: {e_curl_path}. Falling back to 'curl' in PATH.")
        bundled_curl_path = "curl"

    if sys.platform == "win32":
        # PowerShell command to move a file to the Recycle Bin
        # Using Microsoft.VisualBasic.FileIO.FileSystem for better reliability
        ps_recycle_command = (
            f"Add-Type -AssemblyName Microsoft.VisualBasic; "
            f"[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("
            f"'{current_exe_path.replace("'", "''")}', "
            f"[Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs, "
            f"[Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin, "
            f"[Microsoft.VisualBasic.FileIO.UICancelOption]::DoNothing)"
        )

        updater_script_content = f"""@echo off
setlocal enabledelayedexpansion

echo DetailedLoLRPC Updater
echo =======================
echo.
echo Downloading update: {latest_version_tag_name}
echo From: {asset_url}
echo To: "{downloaded_asset_temp_path}"
echo.

set CURL_COMMAND=curl

%CURL_COMMAND% -L -o "{downloaded_asset_temp_path}" "{asset_url}" --progress-bar -f -S
if errorlevel 1 (
    echo.
    echo ERROR: Download failed.
    echo Please check your internet connection or try again later.
    echo You can also download manually from: {GITHUBURL}
    goto :cleanup_and_exit_error
)

echo.
echo Download complete.
echo.
echo Waiting for DetailedLoLRPC (PID: {os.getpid()}) to close...
:waitloop
tasklist /FI "PID eq {os.getpid()}" 2>NUL | find /I /N "{os.getpid()}">NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak > NUL
    goto waitloop
)

echo.
echo DetailedLoLRPC closed. Performing update...
echo Moving current application to Recycle Bin: "{current_exe_path}"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "{ps_recycle_command}"

rem Check if the file still exists after attempting to recycle
if exist "{current_exe_path}" (
    echo ERROR: Failed to move current application to Recycle Bin.
    echo It might still be in use, or a permissions issue occurred.
    echo Please check the Recycle Bin. Update aborted.
    echo You may need to manually remove or rename "{current_exe_path}"
    goto :cleanup_and_exit_error
)
echo Successfully moved current application to Recycle Bin.
echo.

echo Moving new version into place: "{downloaded_asset_temp_path}" to "{current_exe_path}"
move /Y "{downloaded_asset_temp_path}" "{current_exe_path}"
if errorlevel 1 (
    echo ERROR: Failed to move new version into place. 
    echo The original application should be in the Recycle Bin.
    echo Please restore it manually from the Recycle Bin and try updating again later.
    goto :cleanup_and_exit_error
)

echo.
echo Update complete. Starting new version...
start "" "{current_exe_path}"

goto :cleanup_and_exit_success

:cleanup_and_exit_error
echo.
echo Update process encountered an error.
if exist "{temp_download_dir}" (
    echo Cleaning up temporary download files...
    rd /s /q "{temp_download_dir}" >nul 2>&1
)
echo.
echo Press any key to close this window...
pause >nul
del "%~f0" >nul 2>&1
exit /b 1

:cleanup_and_exit_success
echo.
echo Cleaning up temporary download files...
if exist "{temp_download_dir}" (
    rd /s /q "{temp_download_dir}" >nul 2>&1
)
echo.
echo Update process finished. Press any key to close this window...
pause >nul
del "%~f0" >nul 2>&1
exit /b 0

"""
        script_path = os.path.join(tempfile.gettempdir(), "dlrpc_updater.bat")
        try:
            with open(script_path, "w", encoding='utf-8') as f: 
                f.write(updater_script_content)
            logger.info(f"Updater: Created updater batch script at {script_path}")
            
            subprocess.Popen([script_path], creationflags=subprocess.CREATE_NEW_CONSOLE, close_fds=True)
            logger.info("Updater: Launched updater script in new console. Main application should now exit.")
            
            if rpc_app_ref and hasattr(rpc_app_ref, 'shutdown'):
                logger.info("Updater: Signaling main application to shut down.")
                if asyncio.iscoroutinefunction(rpc_app_ref.shutdown): 
                    if rpc_app_ref._main_loop_ref and rpc_app_ref._main_loop_ref.is_running():
                        asyncio.run_coroutine_threadsafe(rpc_app_ref.shutdown(exit_code=0), rpc_app_ref._main_loop_ref)
                    else: 
                        logger.warning("Updater: Main asyncio loop not running for shutdown. Attempting direct run.")
                        try: asyncio.run(rpc_app_ref.shutdown(exit_code=0))
                        except RuntimeError as e_run: logger.error(f"Updater: Error running shutdown directly: {e_run}")
                else: 
                    rpc_app_ref.shutdown(exit_code=0) 
            return True 

        except Exception as e_script:
            logger.error(f"Updater: Failed to create or launch updater script: {e_script}", exc_info=True)
            if show_messagebox_callback:
                show_messagebox_callback("Update Error", f"Failed to initiate update process: {e_script}")
            shutil.rmtree(temp_download_dir, ignore_errors=True)
            return False

def download_asset(url, save_path, show_messagebox_callback=None):
    """Downloads an asset from a URL to a save path."""
    logger.info(f"Updater: (Python download_asset) Downloading asset from {url} to {save_path}")
    try:
        with requests.get(url, stream=True, timeout=300) as r: 
            r.raise_for_status()
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"Updater: (Python download_asset) Asset downloaded successfully to {save_path}")
            return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Updater: (Python download_asset) Error downloading asset: {e}")
        if os.path.exists(save_path): 
            os.remove(save_path)
        return False
    except Exception as e:
        logger.error(f"Updater: (Python download_asset) Unexpected error during download: {e}", exc_info=True)
        if os.path.exists(save_path):
            os.remove(save_path)
        return False
