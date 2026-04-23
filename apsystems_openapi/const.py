DOMAIN = "apsystems_openapi"
DEFAULT_BASE_URL = "https://api.apsystemsema.com:9282"
PLATFORMS = ["sensor", "button"]

# Default to 60 minute intervals to stay under 1000 queries/month
DEFAULT_SCAN_INTERVAL = 3600  # seconds (hourly energy)

# Summary (lifetime/today/month/year) is fetched once per day near
# the end of solar hours.  "today" is already derived from the hourly
# series; the summary provides ground-truth lifetime/month/year.

# Inverter energy (minutely power/voltage/temperature) is fetched once
# per day at 12:30 when panels should be active and producing.

# Monthly budget estimate (11 solar hours/day, 30 days, 6 inverters):
#   Hourly energy:       11h × 1/h × 30                  = 330
#   Summary:             1/day × 30                       =  30
#   Inverter energy:     1/day × 6inv × 30                = 180
#   Inverter list:       manual button only               =   0
#   Total                                                 ≈ 540 / 1000