<a name="readme-top"></a>

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/developers192/DetailedLoLRPC">
    <img src="images/logo.png" alt="Logo" width="80" height="80">
  </a>
<h3 align="center">DetailedLoLRPC</h3>

  <p align="center">
    A better Discord Rich Presence for League of Legends.
    <br />
    <a href="https://github.com/developers192/DetailedLoLRPC/issues">Report Bug</a>
    ·
    <a href="https://github.com/developers192/DetailedLoLRPC/issues">Request Feature</a>
  </p>
</div>


<!-- ABOUT THE PROJECT -->
## About The Project

[![Product Name Screen Shot][product-screenshot]](https://example.com)

I've been playing League for quite some time now, and while using Discord's Rich Presence feature to show off my gaming activity, I noticed something that bothered me. Some champions still had outdated splash arts displayed, and some weren't even updated properly. Another time, I thought to myself, "Wouldn't it be awesome if I could showcase my current skin instead of the default splash art?" And that's when I decided to take matters into my own hands.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Features
- Display your current skin instead of default splash arts
- Updated spash arts for outdated ones
- Proper slash arts for newer champions
- More detailed mode texts (Ranked Solo/Duo/Flex, TFT Double Up, ...)

<!-- GETTING STARTED -->
## Getting Started

To start using DetailedLoLRPC, follow these steps.

### Prerequisites

- Windows 7 and above
- League of Legends
- Discord


### Installation

1. Download the latest [Release](https://github.com/developers192/DetailedLoLRPC/releases/latest)
2. Extract the two files `DetailedLoLRPC.exe` and `setup.exe` to a seperate folder
3. Run the `setup.exe` executable
4. If the Riot Client is not running, you'll have to manually specify the required path.
5. A `League of Legends` shortcut should now be created in the same folder.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

You may move the shortcut created anywhere you please. Running that shortcut will launch League of Legends with it's native Rich Presence replaced with DetailedLoLRPC.

Launching LoL from the Riot Client will use it's native Rich Presence implementation.

You can use the tray icon to close DetailedLoLRPC. Note that closing it will not re-enable the native Rich Presence until the next time you launch LoL using the Riot Client.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- Resource Usage -->
## Resource Usage
First minute or two from starting, DetailedLoLRPC could use up to 25% of your CPU because it has to keep looking for the LoL Client.

When it detects the LoL Client, CPU usage will drop to ~0%. Memory usage is ~50MB.


<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- To do -->
## To do

- [ ] Fix for KDA All Out Seraphine Skins
- [ ] Proper practice tool texts
- [ ] Update for upcoming Soul Fighter mode
- [ ] Option to toggle default splash arts

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Disclaimer
- I will not hold responsibility for any bans caused by DetailedLoLRPC. (In theory it won't happen because DetailedLoLRPC only uses the API provided by the Client itself. Although it does tamper with the `plugin-manifest.json` file to disable the native RPC, but I think it's [allowed](https://www.reddit.com/r/leagueoflegends/comments/awedjv/there_is_a_way_to_make_the_client/))
- DetailedLoLRPC is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc.


<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/developers192/DetailedLoLRPC.svg?style=for-the-badge
[contributors-url]: https://github.com/developers192/DetailedLoLRPC/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/developers192/DetailedLoLRPC.svg?style=for-the-badge
[forks-url]: https://github.com/developers192/DetailedLoLRPC/network/members
[stars-shield]: https://img.shields.io/github/stars/developers192/DetailedLoLRPC.svg?style=for-the-badge
[stars-url]: https://github.com/developers192/DetailedLoLRPC/stargazers
[issues-shield]: https://img.shields.io/github/issues/developers192/DetailedLoLRPC.svg?style=for-the-badge
[issues-url]: https://github.com/developers192/DetailedLoLRPC/issues
[license-shield]: https://img.shields.io/github/license/developers192/DetailedLoLRPC.svg?style=for-the-badge
[license-url]: https://github.com/developers192/DetailedLoLRPC/blob/master/LICENSE
[product-screenshot]: images/screenshot.png