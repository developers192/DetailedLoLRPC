<a name="readme-top"></a>

<div align="center">

  <img src="images/logo.png" alt="Logo" width="120" height="120">

  <h1 align="center">DetailedLoLRPC</h1>

  <p align="center">
    A better Discord Rich Presence for League of Legends.
    <br />
    Now with a brand new interface and more features!
  </p>
  
  <p align="center">
    <a href="https://github.com/developers192/DetailedLoLRPC/stargazers"><img alt="Stargazers" src="https://img.shields.io/github/stars/developers192/DetailedLoLRPC?style=for-the-badge&logo=star&color=C492B1&logoColor=D9E0EE&labelColor=302D41"></a>
    <a href="https://github.com/developers192/DetailedLoLRPC/releases/latest"><img alt="Downloads" src="https://img.shields.io/github/downloads/developers192/DetailedLoLRPC/total?style=for-the-badge&logo=github&color=A6E3A1&logoColor=D9E0EE&labelColor=302D41"></a>
    <a href="https://github.com/developers192/DetailedLoLRPC/issues"><img alt="Issues" src="https://img.shields.io/github/issues/developers192/DetailedLoLRPC?style=for-the-badge&logo=gitea&color=F38BA8&logoColor=D9E0EE&labelColor=302D41"></a>
    <a href="https://github.com/developers192/DetailedLoLRPC/blob/master/LICENSE"><img alt="License" src="https://img.shields.io/github/license/developers192/DetailedLoLRPC?style=for-the-badge&logo=apache&color=89B4FA&logoColor=D9E0EE&labelColor=302D41"></a>
  </p>

  <h3>
    <a href="https://github.com/developers192/DetailedLoLRPC/releases/latest"><strong>Download Latest Release »</strong></a>
  </h3>
  
  <p align="center">
    <a href="#-about-the-project">About</a>
    ·
    <a href="#-getting-started">Getting Started</a>
    ·
    <a href="https://github.com/developers192/DetailedLoLRPC/issues">Report Bug</a>
  </p>
</div>

## 📖 About The Project



![Screenshot1](images/screenshot.png) ![Screenshot2](images/screenshot2.png)

DetailedLoLRPC enhances your League of Legends experience on Discord by providing a much more detailed and customizable Rich Presence. It replaces the default, outdated LoL Rich Presence with accurate champion information, skin splashes, in-game stats, and much more.

With the release of **v5.0.0**, DetailedLoLRPC has been rebuilt from the ground up, featuring a modern graphical user interface (GUI) for easy configuration and a host of new capabilities.

## ✨ Features

DetailedLoLRPC is packed with features to make your LoL presence on Discord shine:

* **✨ Brand New GUI (v5.0.0):** A modern, intuitive interface for easy settings management.
* **🚀 One-Click In-App Updates (v5.0.0):** Update the application directly from the GUI.
* **🎨 Display Current Skin:** Shows the splash art and name of the skin you're using, not just the default.
* **🖼️ Updated & Proper Splash Arts:** Uses correct and up-to-date splash arts for all champions, including newer ones.
* **🎭 Animated Splash Arts:** Option to display animated splash arts for skins that have them (e.g., Ultimate skins).
* **📄 Detailed Mode Texts:** Accurately displays game modes like Ranked Solo/Duo/Flex, TFT Double Up, Arena, etc.
* **🎮 Full Game Mode Support:** Rich Presence is active for all modes, including Summoner's Rift, ARAM, TFT, and all rotating gamemodes.
* **⏳ Loading Screen RPC (v5.0.0):** Shows when you're on the loading screen.
* **🤫 Mute RPC Functionality (v5.0.0):** Temporarily mute/unmute Rich Presence via GUI or tray menu.
* **📍 Customizable Map Icons (v5.0.0):** Choose from 5 different styles for the map icon.
* **⚙️ Import/Export Settings (v5.0.0):** Easily backup and transfer your configurations.
* **📊 In-Game Stats:** Display KDA, CS, and Level.
* **🏆 Rank Display:** Show your rank for various modes (Solo, Flex, TFT, Double Up).
* **📈 Ranked Stats:** Option to display LP, Wins, and Losses.
* **🎉 Party Info:** Show the number of members in your party.
* **👤 Enhanced Idle Status Customization (v5.0.0):**
    * **Profile Info Mode:** Display Riot ID, Tagline, or Summoner Level.
    * **Custom Idle Status:** Set a custom image (via URL) and text, with optional availability status and time elapsed.
* **⏱️ Improved Timer Syncing (v5.0.0):** Accurate in-game timers in Rich Presence.
* **⚡ Immediate RPC Updates:** Changes to configuration apply instantly.

## 🚀 Getting Started

To get DetailedLoLRPC up and running:

### ✅ Prerequisites

* Windows 7 and above
* League of Legends client installed
* Discord desktop application running

### 🛠️ Installation & Usage

1.  **Download:** Grab the latest `DetailedLoLRPC.exe` from the [Releases page](https://github.com/developers192/DetailedLoLRPC/releases/latest).
    * *Note: Your browser or antivirus might flag the download. This is a false positive due to the application interacting with other processes (LoL and Discord). Please whitelist it if necessary.*
2.  **Initial Run:**
    * Ensure League of Legends is **not** running.
    * Run `DetailedLoLRPC.exe`.
3.  **Path Configuration:**
    * If the Riot Client path is not automatically detected, the application will prompt you to specify it through the new GUI.
4.  **Launch LoL:** DetailedLoLRPC will start the Riot Client for you. Once League of Legends is running, DetailedLoLRPC will automatically replace its native Rich Presence.
5.  **Customize:** Use the new settings GUI (accessible from the tray icon) to tailor your Rich Presence to your liking!

## ⚙️ Settings & Customization

As of v5.0.0, most settings are managed through the new **Graphical User Interface (GUI)**, which can be opened by selecting "Open Settings" from the DetailedLoLRPC tray icon menu. Some quick toggles may also be available directly in the tray menu.

Key customizable options include:

* **General Presence:**
    * `Use skin's splash and name`: Display the current skin's splash and name. (Default: Enabled)
    * `Use animated splash if available`: Use animated splash art for eligible skins.
    * `Show "View splash art" button`: Display a button on Discord to view the current skin's splash.
    * `Show party info`: Display party member count.
    * `Map Icon Style`: Choose from 5 different map icon designs.
* **Stats:**
    * `Ingame stats`: Select which stats to show (KDA, CS, Level).
    * `Show ranks`: Choose for which modes to display your rank (Solo, Flex, TFT, Double Up).
    * `Ranked stats`: Select which ranked stats to show (LP, Wins, Losses).
* **Idle Status:**
    * Configure what's shown when you're not in a game.
    * **Profile Info Mode:** Display Profile icon, Riot ID, Tagline, or Summoner Level.
    * **Custom Idle Status:** Set a custom image and text, and toggle availability/time elapsed.
* **Application Behavior:**
    * `Mute Rich Presence`: Temporarily disable RPC (toggle in GUI or tray).
    * `Import/Export Settings`: Manage your application configurations.
    * `Check for Updates`: Initiate the in-app update process.
* **Utilities:**
    * `Reset preferences`: Reset all settings to their default values. (Useful if you move your Riot Games folder).
    * `Report bug`: Opens the GitHub issues page and the folder containing necessary logs.
    * `Exit`: Close DetailedLoLRPC. (LoL's native RPC will not be re-enabled until the next time you start LoL through the Riot Client without DetailedLoLRPC running).

Settings changes are generally applied instantly or after a short delay.

## 💻 Resource Usage

* **CPU:** Approximately 1-3% during active game state processing. Can be lower when idle.
* **Memory:** Around 50MB.

Resource usage is minimal and optimized to not impact game performance.

## 📝 To Do

* [ ] Implement a "Join Lobby" button on Discord.
* [ ] More support for spectator mode.

Have an idea? [Request a Feature!](https://github.com/developers192/DetailedLoLRPC/issues)

## ⚠️ Will I get banned for using this?

Theoretically, **no**. DetailedLoLRPC primarily uses the local API provided by the League of Legends client itself, which is intended for third-party tools. While it does modify the `plugin-manifest.json` file to disable the native Rich Presence, this method has been generally considered safe by the community.

However, Riot Games' stance on any third-party application can change. While this tool is used by many (including me) without issue, **use it at your own discretion.** DetailedLoLRPC is designed to be as non-intrusive as possible.

## 📜 Changelog

For a detailed list of changes in each version, please see the [CHANGELOG.md](CHANGELOG.md) file.
**v5.0.0 is a major update!** Check out the changelog for all the exciting new features and improvements.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

## 📢 Disclaimer

DetailedLoLRPC was created under Riot Games' ["Legal Jibber Jabber"](https://www.riotgames.com/en/legal) policy using assets owned by Riot Games. This project is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc.

---

<p align="right">(<a href="#readme-top">back to top</a>)</p>