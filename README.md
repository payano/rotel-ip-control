# Rotel IP Control (Home Assistant)


TCP-only custom integration for controlling Rotel integrated amplifiers over LAN (port 9590) using Rotel's ASCII protocol. Push updates are supported for real-time state sync (no polling).


> **Tested family**: Rotel A12/A14 and close siblings that expose the ASCII control set over TCP 9590. Other Rotel models with the same protocol may also work.


## Features
- `media_player` entity with: Power, Volume (0–96 normalized), Mute, Source select
- LAN/TCP transport only (no serial)
- Push updates: subscribes to unsolicited status lines so HA reflects front‑panel/IR changes immediately
- Config Flow (UI) setup: host & port, connection test, device info
- **Profiles & mapping table:** model-specific command maps so multiple Rotel devices can be supported even if commands diverge
- HACS-ready packaging


## Profiles & command mapping
This integration selects a **command profile** based on the model string reported by the amplifier (via `model?`). Each profile defines:
- Command strings (e.g., `power_on`, `mute_on`, `source_query`)
- Volume range and formatting (e.g., template `vol_{value:02d}!` with range 0..96)
- Source command map (e.g., `{"cd": "cd!", "pcusb": "pcusb!"}`)


Current profiles:
- `rotel_ascii_v1` — Rotel ASCII v1 (A12/A14 family). Default fallback.


If your unit uses different commands, you can add/adjust a profile in `custom_components/rotel_ip/profiles.py` and optionally extend the `MODEL_PATTERNS` list to auto-select it.


## Install (via HACS as a custom repository)
1. In Home Assistant, go to **HACS → Integrations → ⋯ → Custom repositories**.
2. Add your repo URL (e.g. `https://github.com/yourname/Rotel-ip-control`) and choose **Integration**.
3. Install **Rotel IP Control** from HACS.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → + Add Integration → Rotel IP Control** and enter the host (and port if not 9590).


## Usage
- On connect, the integration enables push updates and subscribes to status lines ending with `$`.
- Commands are ASCII without CR/LF; commands end with `!`. Status lines end with `$`.
- The selected profile determines which commands are sent and how volume/source are formatted.


## Troubleshooting
- Ensure the amp is connected to the network and TCP port **9590** is reachable.
- Some EU units may not wake from network standby via IP; power on the unit manually first.
- If connection drops, the integration auto-reconnects with backoff and re-enables push updates.


## Development
- Domain: `rotel_ip`
- IoT class: `local_push`
- Platforms: `media_player`
- Profiles live in `profiles.py`; `MODEL_PATTERNS` maps model strings to profile keys.


## License
MIT — see [LICENSE](LICENSE).
