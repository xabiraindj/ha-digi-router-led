# DIGI Router LEDs

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)

Custom Home Assistant integration to switch the LED indicators on a **DIGI PE5301-01** router on or off through its local web interface.

> **Compatibility:** currently tested with the DIGI PE5301-01 firmware/router setup used by the author. Other DIGI models and firmware versions have not been verified.

## Features

- Configure the router IP address and administrator credentials in the Home Assistant UI.
- Turn the router LEDs on or off using a Home Assistant switch entity.
- Communicates locally with the router; no cloud service is used by this integration.

## Requirements

- Home Assistant with custom integrations support.
- A DIGI PE5301-01 router reachable from Home Assistant over the local network.
- The router's web administration username and password.
- HTTP access to the router's local web interface.

## Installation with HACS

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add `https://github.com/xabiraindj/ha-digi-router-led`.
4. Select **Integration** as the category and add the repository.
5. Find **DIGI Router LEDs** in HACS and install it.
6. Restart Home Assistant.
7. Go to **Settings → Devices & services → Add integration**.
8. Search for **DIGI Router LEDs** and enter the router IP, username and password.

## Manual installation

1. Copy the `custom_components/digi_led` directory into the `custom_components` directory of your Home Assistant configuration.
2. Restart Home Assistant.
3. Add **DIGI Router LEDs** from **Settings → Devices & services**.

## Security and privacy

- Credentials are entered in Home Assistant's integration configuration and are not meant to be committed to this repository.
- The integration connects to the router's local web interface over HTTP, as required by the router interface used during development. Use it only on a trusted local network.
- Do not expose the router administration interface directly to the internet.

## Troubleshooting

- Confirm that Home Assistant can reach the router's IP address.
- Confirm that the username and password work in the router's own web interface.
- Check **Settings → System → Logs** for messages from `custom_components.digi_led`.
- Firmware changes may alter the router's login or LED-control API and could require an integration update.

## Disclaimer

This is a community project and is not affiliated with or endorsed by DIGI. Use at your own risk. Router models and firmware versions other than the tested setup may not work.

## Licencia / License

MIT. See [LICENSE](LICENSE).
