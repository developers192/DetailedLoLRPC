import asyncio
import os
from lcu_driver.connection import Connection
from lcu_driver.utils import _return_ux_process # For finding LCU process

from .utilities import logger, addLog, procPath, LEAGUE_CLIENT_EXECUTABLE

class LcuManager:
    """
    Manages the connection to the League of Legends LCU.
    Handles finding the client, establishing connection, and reconnections.
    """
    def __init__(self, connector_instance):
        self.connector = connector_instance
        self.current_connection = None
        self._shutting_down = False
        self._main_loop_task = None
        logger.info("LcuManager initialized.")

    async def _find_lcu_process(self):
        """Continuously searches for the LCU process until found or shutdown."""
        lcu_process_obj = None
        logger.info("LcuManager: Searching for League Client UX process...")
        while not lcu_process_obj and not self._shutting_down:
            process_generator = _return_ux_process()
            try:
                lcu_process_obj = next(process_generator)
            except StopIteration:
                lcu_process_obj = None
            
            if not lcu_process_obj:
                if self._shutting_down:
                    logger.info("LcuManager: Shutdown signaled while searching for LCU process.")
                    break
                logger.debug("LcuManager: League Client UX process not found. Retrying in 3 seconds...")
                await asyncio.sleep(3)
            else:
                pid = getattr(lcu_process_obj, 'pid', 'N/A')
                logger.info(f"LcuManager: League Client UX process found (PID: {pid}).")
                addLog(f"LCU Manager: Client process found (PID: {pid}).", level="INFO")
        return lcu_process_obj

    async def manage_connection(self):
        """
        Main loop for managing the LCU connection.
        Attempts to connect and reconnect if the client closes.
        """
        logger.info("LcuManager: Starting connection management loop.")
        while not self._shutting_down:
            lcu_process = await self._find_lcu_process()

            if self._shutting_down:
                logger.info("LcuManager: Shutdown signaled, exiting connection management loop.")
                break
            if not lcu_process:
                logger.warning("LcuManager: Could not find LCU process after search loop (should not happen if not shutting down). Will retry.")
                await asyncio.sleep(5) # Wait before retrying the whole find process
                continue

            self.current_connection = None
            connection_object = None

            try:
                # Corrected instantiation: Connection(connector_instance, process_object)
                connection_object = Connection(self.connector, lcu_process)
                                
                self.connector.register_connection(connection_object) 
                self.current_connection = connection_object 

                logger.info(f"LcuManager: Initializing connection to LCU (PID: {getattr(lcu_process, 'pid', 'N/A')})...")
                await connection_object.init()
                
                logger.info(f"LcuManager: Connection (PID: {getattr(lcu_process, 'pid', 'N/A')}) init() completed. Client likely closed or connection lost.")
                addLog("LCU Manager: Connection init() completed (client closed or error).", level="INFO")

            except asyncio.CancelledError:
                logger.info("LcuManager: Connection management task was cancelled.")
                addLog("LCU Manager: Connection management task cancelled.", level="INFO")
                break 
            except Exception as e:
                pid_str = getattr(lcu_process, 'pid', 'N/A')
                logger.error(f"LcuManager: Error during LCU connection (PID: {pid_str}): {e}", exc_info=True)
                addLog(f"LCU Manager Error: Connection error (PID: {pid_str}): {str(e)}", level="ERROR")
            finally:
                if connection_object: 
                    self.connector.unregister_connection(getattr(lcu_process, 'pid', None))
                self.current_connection = None 
                
                if not self._shutting_down:
                    logger.info("LcuManager: Connection lost/closed. Will attempt to find LCU process again after a delay.")
                    await asyncio.sleep(5) 

        logger.info("LcuManager: Connection management loop has exited.")


    async def start(self):
        """Starts the LCU connection management in a background task."""
        if self._main_loop_task and not self._main_loop_task.done():
            logger.warning("LcuManager: Start called but already running.")
            return
        self._shutting_down = False
        self._main_loop_task = asyncio.create_task(self.manage_connection())
        logger.info("LcuManager: Started connection management task.")
        try:
            await self._main_loop_task 
        except asyncio.CancelledError:
            logger.info("LcuManager: Main loop task was cancelled during start().")
        except Exception as e:
            logger.error(f"LcuManager: Unhandled exception in main loop task: {e}", exc_info=True)


    async def stop(self):
        """Stops the LCU connection management."""
        logger.info("LcuManager: Stop requested.")
        self._shutting_down = True
        
        if self.current_connection and hasattr(self.current_connection, '_close'):
            logger.info("LcuManager: Attempting to close active LCU connection...")
            try:
                await self.current_connection._close()
                logger.info("LcuManager: Active LCU connection closed.")
            except Exception as e:
                logger.error(f"LcuManager: Error closing active LCU connection: {e}", exc_info=True)
        
        if self._main_loop_task and not self._main_loop_task.done():
            logger.info("LcuManager: Cancelling main connection management task...")
            self._main_loop_task.cancel()
            try:
                await self._main_loop_task
            except asyncio.CancelledError:
                logger.info("LcuManager: Main connection management task successfully cancelled.")
            except Exception as e: 
                logger.error(f"LcuManager: Exception while awaiting cancelled main loop task: {e}", exc_info=True)
        
        logger.info("LcuManager: Stopped.")

