# DetailedLoLRPC - Release Notes [v5.0.0]

This major update brings a completely revamped experience with a brand new GUI, exciting new features, and significant improvements to stability and performance!

## ✨ New GUI & Features

* **Completely New Graphical User Interface (GUI):**
    * The application now features a modern and intuitive settings interface, making it easier than ever to customize your Rich Presence.
* **One-Click In-App Updates (New!):**
    * Update DetailedLoLRPC directly from the GUI! The "Check for Updates" button now handles the entire update process, including download and installation (via a CMD helper).
* **Enhanced Idle Status Customization:**
    * **Profile Info Mode (New Options!):**
        * Choose to display your Riot ID (Summoner Name).
        * Choose to display your Tagline.
        * Choose to display your Summoner Level.
    * **Custom Idle Status (New!):**
        * Set a custom image (via URL) and custom text for your idle presence.
        * Optionally show your availability status circle and time elapsed.
* **Loading Screen RPC (New!):**
    * Your Rich Presence will now display that you're on the loading screen when a match starts.
* **Mute RPC Functionality (New!):**
    * Temporary mute and unmute Rich Presence via a new option in the tray icon menu and a dedicated button in the settings GUI.
* **Choose from 5 Map Icon Styles (New!):**
    * Customize the map icon displayed in your Rich Presence by selecting from five different styles.
* **Import/Export Settings (New!):**
    * Easily back up your DetailedLoLRPC configuration or transfer it to another installation using the new import and export settings feature.

## 🚀 Enhancements & Fixes

* **Improved Timer Syncing (New!):**
    * In-game timers displayed in Rich Presence are now accurately synchronized.
* **Immediate RPC Updates on Config Change:**
    * Any changes made to your configuration via the GUI or tray menu are now reflected in your Rich Presence instantly.
* **Reliable RPC Clearing:**
    * Fixed an issue where Rich Presence would sometimes not clear correctly after exiting a game lobby.
* **Instance Checking:**
    * Improved the mechanism to ensure only one instance of DetailedLoLRPC can run at a time.
* **Update Reliability:**
    * Resolved an issue that would cause the Riot client to get stuck in an update loop.

## 🛠️ Internal Improvements

* **Completely Rewritten Internal Code Structure:**
    * The application's core has been significantly refactored for better maintainability, scalability, and overall performance.
* **Better Logging for Debugging:**
    * Logging capabilities have been greatly enhanced, providing more detailed information for easier troubleshooting and issue diagnosis.
* **Comprehensive Error Handling:**
    * Implemented more robust error handling throughout the application to improve stability and prevent unexpected crashes.

---

Thank you for using DetailedLoLRPC! I'm excited for you to try out these new features and improvements.