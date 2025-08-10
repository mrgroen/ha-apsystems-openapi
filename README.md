# APsystems OpenAPI – Home Assistant Custom Integration

This is a custom [Home Assistant](https://www.home-assistant.io/) integration for pulling **lifetime** and **daily** solar production data from the [APsystems OpenAPI](https://file.apsystemsema.com:8083/apsystems/resource/openapi/Apsystems_OpenAPI_User_Manual_End_User_EN.pdf). It is designed to integrate with the **Energy dashboard** and also provide today's production plus hourly production breakdowns.

---

## Features

- **Lifetime total kWh** (monotonic increasing) for use in the Energy dashboard
- **Today’s total kWh** (resets daily) for quick daily monitoring
- Hourly production values for the current day, exposed as attributes
- Configurable polling interval
- Uses **Home Assistant Config Flow** (no YAML required)
- Includes debug logging for easy troubleshooting

---

## Installation

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
- **Base URL**: Typically `https://api.apsystemsema.com:9282`
- **Scan interval**: Seconds between updates (default 1800 = 30 minutes)

6. Save and wait for the first update.

---

## Adding to the Energy Dashboard

1. Go to **Settings → Dashboards → Energy**.
2. Under **Solar production**, select **`sensor.apsystems_total_energy_kwh`**.
- This sensor has:
  - `device_class: energy`
  - `state_class: total_increasing`
  - Unit: `kWh`
3. Save changes.

> ⚠️ **Do not** use `sensor.apsystems_today_energy_kwh` in the Energy dashboard — it resets daily and will break the Energy graph.  
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

APS GET /user/api/v2/systems/summary/XXXX params=None s2s_preview=...
APS https://api.apsystemsema.com:9282/... → 200 {"code":0,"data":{...}}

### Recommended cleanup after successful setup

Leave debug logging calls in the code — it is harmless unless enabled in configuration.yaml.

In configuration.yaml, comment out the logger: section above once the integration is stable to reduce log noise.

If you want quieter code long-term, you can comment out specific _LOGGER.debug calls in:

api.py → request/response preview lines

__init__.py → coordinator refresh timings

But keeping them is fine; Home Assistant will not output them unless debug is enabled.

## Troubleshooting

| Symptom | Possible Cause | Fix |
| ------- | -------------- | --- |
| code:4000 in logs | Wrong signing string (RequestPath must be last segment), wrong App ID/Secret, or clock drift | Check that your HA host clock is correct; verify credentials; sign only last URL segment |
| code:5000 from hourly endpoint | No hourly data available yet or transient API error | Usually resolves on next update |
| Old APsystems integration causing conflicts | Old domain/folder still present | Remove the old folder in custom_components/, delete old integration entry, disble old items in Energy dashboard if present, restart HA |

## Credits

Based on the official [APsystems OpenAPI User Manual](https://file.apsystemsema.com:8083/apsystems/resource/openapi/Apsystems_OpenAPI_User_Manual_End_User_EN.pdf).

Built and tested with APsystems EMA accounts.

## Disclaimer

This is not an official APsystems integration. Use at your own risk. Be mindful of APsystems API request limits (default polling is set to 30 minutes to avoid hitting limits).