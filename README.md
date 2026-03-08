# APsystems OpenAPI – Home Assistant Custom Integration

# FORKED FROM https://blackhole.nmrc.org/solar/apsystems-openapi

This is a custom [Home Assistant](https://www.home-assistant.io/) integration for pulling **lifetime** and **daily** solar production data from the [APsystems OpenAPI](https://file.apsystemsema.com:8083/apsystems/resource/openapi/Apsystems_OpenAPI_User_Manual_End_User_EN.pdf). It is designed to integrate with the **Energy dashboard** and also provide today's production plus hourly production breakdowns, pulling data into Home Assistant from your APsystems account on their [Energy Monitoring & Analysis (EMA) System](https://www.apsystemsema.com/ema/index.action).

A quick note: I was originally using a modified version of a similar tool but it had multiple bugs, seemed to work better in the EU for  some reason, and required a lot of modifications to make it work on my system, so I opted to rewrite the entire thing from scratch. So far all of the errors I was getting have gone away. Please note this was tested on Home Assistant 2025.8.0 so while it might work on different versions, some of the referenced menu items in HA might be different than what is referenced here.

---

## Features

- **Lifetime total kWh** (monotonic increasing) for use in the Energy dashboard
- **Today’s total kWh** (resets daily) for quick daily monitoring
- **Per-inverter AC power** (W) — each micro-inverter discovered automatically and exposed as its own device/sensor
- Per-inverter DC channel 1 & 2 power, peak values, and full hourly time series (exposed as sensor attributes)
- Hourly production values for the current day, exposed as attributes
- Configurable polling intervals (system and inverter data fetched on independent schedules)
- API budget awareness — logs monthly call estimates and warns when approaching the 1000/month limit
- Solar-hours-only polling with sunrise/sunset awareness to conserve API calls
- Uses **Home Assistant Config Flow** (no YAML required)
- Includes debug logging for easy troubleshooting

---

## Installation

0. _Prerequisties:_ Using your account on the [APsystems EMA](https://www.apsystemsema.com/ema/index.action) site, you will need to create an API account as you will need an APP ID, APP Secret, and System ID (SID) for this integration to work. While you can copy the custom code into Home Assistant using the File Editor dashboard, it is much easier if you've installed something like [Studio Code Server](https://github.com/hassio-addons/addon-vscode).

1. Copy the `apsystems_openapi` folder and its contents into:

config/custom_components/

Your structure should look like:

```
config/
	custom_components/
		apsystems_openapi/
			init.py
			api.py
			config_flow.py
			const.py
			manifest.json
			sensor.py
```

2. Restart Home Assistant.

3. Go to **Settings → Devices & Services → Add Integration**.

4. Search for **APsystems OpenAPI**.

5. Enter:
- **App ID**: Provided by APsystems after API access approval
- **App Secret**: Provided by APsystems
- **System ID (SID)**: Found in your EMA portal
- **Base URL**: Typically the default `https://api.apsystemsema.com:9282` will work, adjust for your region if needed
- **Scan interval**: Seconds between system-level updates (default 6000s). Controls how often lifetime/today/hourly system energy is fetched.
- **Inverter scan interval**: Seconds between per-inverter energy fetches (default 14400s = 4 hours, range 1h–24h). Each fetch makes one API call per inverter.
- **Sunrise/Sunset offsets**: Minutes to wait after sunrise/before stopping after sunset (default 30 each)

6. Save and wait for the first update.

---

## Inverter Sensors

On first startup the integration calls the APsystems inverter discovery endpoint and creates one **power sensor** per micro-inverter. Each inverter appears as its own device in Home Assistant, linked to the parent system.

| Entity | Description |
| ------ | ----------- |
| `sensor.inverter_<UID>_power` | Latest AC output power (W) |

Each inverter sensor also exposes the following **attributes**:

| Attribute | Description |
| --------- | ----------- |
| `dc_channel1_power_w` | Latest DC channel 1 power (W) |
| `dc_channel2_power_w` | Latest DC channel 2 power (W) |
| `dc_channel1_peak_w` | Peak DC channel 1 power today (W) |
| `dc_channel2_peak_w` | Peak DC channel 2 power today (W) |
| `ac_power_peak_w` | Peak AC output today (W) |
| `hourly_ac_power` | Full time series of AC power readings |
| `hourly_dc_p1` / `hourly_dc_p2` | Full time series of DC channel power |
| `hourly_times` | Timestamps for the time series |
| `inverter_type` | Model type reported by the API |
| `ecu_id` | ECU the inverter is connected to |

Inverter data is fetched on a slower schedule than system data to conserve your API budget. The inverter list itself is cached for 24 hours.

---

## Adding to the Energy Dashboard

1. Go to **Settings → Dashboards → Energy**.
2. Under **Solar production**, select **`sensor.apsystems_total_energy_kwh`**.
- This sensor has:
  - `device_class: energy`
  - `state_class: total_increasing`
  - Unit: `kWh`
3. Save changes.

> **WARNING:** Do not use `sensor.apsystems_today_energy_kwh` in the Energy dashboard — it resets daily and will break the Energy graph.  
> You *can* use it in Lovelace cards for at-a-glance daily totals.

---

## Debug Logging

This integration includes detailed debug logging in the code (`_LOGGER.debug` calls) for installation and troubleshooting.  
To enable:

```
# add to configuration.yaml
logger:
  default: warning
  logs:
    custom_components.apsystems_openapi: debug
    aiohttp.client: info
```

After restart, look for log lines like:

```
APS GET /user/api/v2/systems/summary/XXXX params=None s2s_preview=...
APS https://api.apsystemsema.com:9282/... → 200 {"code":0,"data":{...}}
```

## Recommended cleanup after successful setup

- Leave debug logging calls in the code — it is harmless unless enabled in configuration.yaml.
- In configuration.yaml, comment out the logger: section above once the integration is stable to reduce log noise.
- If you want quieter code long-term, you can comment out specific `_LOGGER.debug` calls, but keeping them is fine; Home Assistant will not output them unless debug is enabled. The `_LOGGER.debug` calls are in:
  - `api.py` → request/response preview lines
  - `__init__.py` → coordinator refresh timings


## Troubleshooting

| Symptom | Possible Cause | Fix |
| ------- | -------------- | --- |
| code:4000 in logs | Wrong signing string (RequestPath must be last segment), wrong App ID/Secret, or clock drift | Check that your HA host clock is correct; verify credentials; sign only last URL segment |
| code:5000 from hourly endpoint | No hourly data available yet or transient API error | Usually resolves on next update |
| Old APsystems integration causing conflicts | Old domain/folder still present | Remove the old folder in custom_components/, delete old integration entry, disble old items in Energy dashboard if present, restart HA |

You can also download and use `apsystems_testcreds.py` (you might have to `pip install aiohttp` first) to help with troubleshooting credential usage outside of Home Assistant. Simply edit it and add your credentials, or use the command line. It is located [here](apsystems_test_apps/apsystems_testcreds.py).

```
$ python3 apsystems_testcreds.py --help
usage: apsystems_testcreds.py [-h] [--app-id APP_ID] [--app-secret APP_SECRET]
                              [--sid SID] [--base-url BASE_URL] [--date DATE]

APsystems OpenAPI credential + endpoint test

options:
  -h, --help            show this help message and exit
  --app-id APP_ID
  --app-secret APP_SECRET
  --sid SID
  --base-url BASE_URL
  --date DATE           YYYY-MM-DD for hourly test (default: today)
```

## Credits

Based on the official [APsystems OpenAPI User Manual](https://file.apsystemsema.com:8083/apsystems/resource/openapi/Apsystems_OpenAPI_User_Manual_End_User_EN.pdf).

Built and tested with APsystems EMA accounts.

## API Budget

APsystems enforces a limit of **1000 API calls per month**. The integration makes the following calls during solar hours:

- **2 calls per system poll** (summary + hourly energy)
- **1 call per inverter per inverter poll** (per-inverter energy)
- **1 call per day** for inverter list discovery (cached 24h)

Estimated monthly usage (assuming ~11 solar hours/day, 30 days):

| Inverters | `scan_interval` | `inverter_scan_interval` | Est. calls/month |
|:---------:|:----------------:|:------------------------:|:-----------------:|
| 6 | 6000s (default) | 14400s (4h, default) | ~921 |
| 6 | 3600s (1h) | 28800s (8h) | ~937 |
| 10 | 6000s | 14400s (4h) | ~1070 — increase inverter interval |
| 10 | 6000s | 21600s (6h) | ~960 |

The integration logs an estimate after each inverter fetch and warns if the projection exceeds 900/month. Check your Home Assistant logs for lines like:

```
Estimated monthly API calls: ~921/1000 (6 inverters, system every 6000s, inverters every 14400s)
```

---

## Disclaimer

This is not an official APsystems integration. Use at your own risk. Be mindful of APsystems API request limits — the defaults are tuned to stay under 1000 calls/month for systems with up to 6 inverters.