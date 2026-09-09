<p align="center">
  <img src="img/tg_bot_pfp.png" alt="USI Mensa Bot avatar" width="200">
</p>

# USI Mensa Bot

[![Send 1908 menu](https://github.com/kybeka/usi-mensa-bot-webhook/actions/workflows/send-channel.yml/badge.svg)](https://github.com/kybeka/usi-mensa-bot-webhook/actions/workflows/send-channel.yml)
[![Telegram](https://img.shields.io/badge/Telegram-@usi__mensa-26A5E4?logo=telegram&logoColor=white)](https://t.me/usi_mensa)
![1908](https://img.shields.io/badge/menu-1908-E76F51)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

An unofficial bot that publishes the current [1908 USI–SUPSI menu](https://menu.1908.ch/usi-supsi) every weekday morning.

> Is a menu missing or incorrect? [Leave an issue](https://github.com/kybeka/usi-mensa-bot-webhook/issues/new?template=menu-problem.yml) with the date and what went wrong.

## Follow the menu

Follow [@usi_mensa on Telegram](https://t.me/usi_mensa) to receive the menu from Monday to Friday.

On Monday, the bot first posts and pins a compact overview of the new week, then posts Monday's full menu. On the remaining weekdays, it posts that day's menu.

The source covers Campus Est USI–SUPSI Viganello, Campus Ovest USI Lugano and Campus SUPSI Mendrisio.

## About this project

This bot was created and is maintained by [@kybeka](https://github.com/kybeka). Its source is public for anyone curious about how it works or interested in running their own copy.

The bot reads the menu directly from 1908 and stays quiet when the page is unavailable, stale or malformed, rather than publishing potentially incorrect food information.

This is an independent community project and is not affiliated with USI, SUPSI or 1908.

## Run your own copy

Forks can publish to Telegram, Discord or both. Setup instructions and technical details are in the [maintainer guide](docs/OPERATIONS.md).

## License

MIT License. See [LICENSE](LICENSE).
