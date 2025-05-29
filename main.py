import asyncio
import sys
import os
from multiprocessing import freeze_support

import nest_asyncio
nest_asyncio.apply()

try:
    from src.utilities import (
        init as util_init, procPath, yesNoBox, logger, addLog, 
        LEAGUE_CLIENT_EXECUTABLE, fetchConfig, APPDATA_DIRNAME, LOCK_FILENAME,
        check_and_create_lock, release_lock,
        tk
    )
    from tkinter import messagebox
    from src.DetailedLoLRPC import DetailedLoLRPC
    import src.tray_icon as tray_module
    from src.gui import launch_settings_gui
    from src import updater
except ImportError as e:
    try:
        import logging
        startup_logger = logging.getLogger("startup_critical")
        startup_logger.addHandler(logging.StreamHandler(sys.stdout))
        startup_logger.setLevel(logging.CRITICAL)
        startup_logger.critical(f"CRITICAL: Failed to import necessary modules: {e}")
        startup_logger.critical("Ensure 'src' is a package (contains an __init__.py file) and all dependencies are installed.")
        startup_logger.critical("Application cannot start.")
    except:
        print(f"CRITICAL: Failed to import necessary modules: {e}")
        print("Ensure 'src' is a package (contains an __init__.py file) and all dependencies are installed.")
        print("Application cannot start.")
    
    try:
        input("Press Enter to exit.") 
    except:
        pass
    sys.exit(1)


async def main_application_runner():
    """
    Sets up and runs the DetailedLoLRPC application.
    Returns the intended exit code.
    """

    app_name_for_lock_check = os.path.basename(sys.executable if getattr(sys, 'frozen', False) else "DetailedLoLRPC.py") 
    if not check_and_create_lock():
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("DetailedLoLRPC", "DetailedLoLRPC is already running.", parent=root)
            root.destroy()
        except Exception as e_tk_mb:
            print(f"DetailedLoLRPC is already running. (Could not show dialog: {e_tk_mb})")
        return 1 # Indicate failure to start due to existing instance

    util_init()
    logger.info("Utilities initialized by main.py.")

    exit_code_to_return = 0 # Default to success
    rpc_app = None # Initialize to None

    try:
        if procPath(LEAGUE_CLIENT_EXECUTABLE):
            should_continue = False
            try:
                loop = asyncio.get_running_loop()
                should_continue = await loop.run_in_executor(None, 
                    lambda: yesNoBox(
                        "DetailedLoLRPC might not work optimally if opened after League of Legends. Continue?"
                    )
                )
            except RuntimeError: 
                logger.warning("No running asyncio loop for yesNoBox, attempting direct call.")
                should_continue = yesNoBox(
                    "DetailedLoLRPC might not work optimally if opened after League of Legends. Continue?"
                )
            except Exception as e:
                logger.error(f"Error during initial yesNoBox check: {e}")
                should_continue = True

            if not should_continue:
                logger.info("User chose to exit because League is already running. Program will now terminate.")
                return 0
        
        rpc_app = DetailedLoLRPC()
        if hasattr(tray_module, 'setup_rpc_app_reference'):
            tray_module.setup_rpc_app_reference(rpc_app)
            logger.info("rpc_app reference passed to tray_module.")
        else:
            logger.error("tray_module does not have setup_rpc_app_reference. Tray icon callbacks might not work as expected.")
        
        try:
            if fetchConfig("showWindowOnStartup"):
                logger.info("Configuration set to show settings window on startup.")
                launch_settings_gui(
                    current_status_getter=rpc_app.get_current_app_status_for_gui,
                    rpc_app_ref=rpc_app
                )
                logger.info("Attempted to launch settings GUI on startup.")
            else:
                logger.info("Configuration set to NOT show settings window on startup.")
        except Exception as e_gui_startup:
            logger.error(f"Error launching settings GUI on startup: {e_gui_startup}", exc_info=True)
            addLog(f"GUI Error: Failed to launch settings on startup: {str(e_gui_startup)}", level="ERROR")

        main_app_task = asyncio.create_task(rpc_app.run())
        await main_app_task 
        exit_code_to_return = rpc_app._final_exit_code 

    except asyncio.CancelledError:
        logger.info("Main application task was cancelled (likely during shutdown).")
        if rpc_app and hasattr(rpc_app, 'shutting_down') and not rpc_app.shutting_down:
            logger.warning("Main task cancelled but shutdown not in progress. Initiating shutdown.")
            await rpc_app.shutdown(exit_code=0) 
        if rpc_app: exit_code_to_return = rpc_app._final_exit_code
    except KeyboardInterrupt:
        logger.info("Ctrl+C received by main_application_runner. Initiating shutdown...")
        print("\nCtrl+C received. Shutting down...")
        addLog("App Info: KeyboardInterrupt received by main_application_runner.", level="INFO")
        if rpc_app and hasattr(rpc_app, 'shutting_down') and not rpc_app.shutting_down: 
            await rpc_app.shutdown(exit_code=0)
        if rpc_app: exit_code_to_return = rpc_app._final_exit_code
    except SystemExit as e: 
        logger.info(f"Application exited via SystemExit with code {e.code} in main_application_runner.")
        exit_code_to_return = e.code
        if rpc_app and hasattr(rpc_app, 'shutting_down') and not rpc_app.shutting_down and e.code != 0 : 
             logger.warning(f"SystemExit({e.code}) caught, attempting graceful shutdown.")
             await rpc_app.shutdown(exit_code=e.code)
             exit_code_to_return = rpc_app._final_exit_code 
    except Exception as e: 
        logger.critical(f"An unhandled error occurred in main_application_runner: {e}", exc_info=True)
        addLog(f"App Critical Error: Unhandled in main_application_runner: {str(e)}", level="CRITICAL")
        import traceback
        addLog(traceback.format_exc(), level="CRITICAL") 
        print(f"An unhandled error occurred: {e}")
        exit_code_to_return = 1
        if rpc_app and hasattr(rpc_app, 'shutdown') and hasattr(rpc_app, 'shutting_down') and not rpc_app.shutting_down: 
            await rpc_app.shutdown(exit_code=1)
            exit_code_to_return = rpc_app._final_exit_code
    finally:
        if os.path.exists(os.path.join(os.getenv("APPDATA"), APPDATA_DIRNAME, LOCK_FILENAME)):
            logger.info("Main_application_runner finally: Releasing lock as a safeguard.")
            release_lock()
        logger.info("Main_application_runner function exiting.")
    return exit_code_to_return 


if __name__ == "__main__":
    freeze_support()
    nest_asyncio.apply()
    
    final_exit_code = 0
    try:
        final_exit_code = asyncio.run(main_application_runner())
    except SystemExit as e: 
        final_exit_code = e.code
        logger.info(f"asyncio.run completed. SystemExit caught with code: {final_exit_code}")
    except KeyboardInterrupt:
        logger.info("asyncio.run interrupted by KeyboardInterrupt. Application will terminate.")
        final_exit_code = 0 # Or a specific code for Ctrl+C
    except Exception as e_run:
        logger.critical(f"Critical error during asyncio.run: {e_run}", exc_info=True)
        final_exit_code = 1 # General error
    finally:
        logger.info(f"Application process finalizing with exit code: {final_exit_code}")

        lock_file_full_path = os.path.join(os.getenv("APPDATA"), "DetailedLoLRPC", "detailedlolrpc.lock") # Reconstruct path
        if os.path.exists(lock_file_full_path):
            try:
                with open(lock_file_full_path, "r") as f:
                    pid_in_lock = f.read().strip()
                    if pid_in_lock == str(os.getpid()):
                        release_lock() 
                    else:
                        logger.warning(f"Lock file found but owned by PID {pid_in_lock}, not current PID {os.getpid()}. Not releasing in main.py finally.")
            except Exception as e_lock_final:
                logger.error(f"Error during final lock release check: {e_lock_final}")

        os._exit(final_exit_code)
