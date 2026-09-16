# The fast telemetry stream, sent best effort. Losing one of these is normal
# over a long wireless link, so nothing here is cumulative: every message
# stands alone and the newest one is the truth.

uint8 FIX_NONE=0
uint8 FIX_SINGLE=1
uint8 FIX_DGPS=2
uint8 FIX_RTK_FLOAT=3
uint8 FIX_RTK_FIXED=4

std_msgs/Header header

float64 latitude
float64 longitude
uint8 fix_type
uint8 satellites

float32 heading_deg              # compass degrees, 0 = north
float32 speed_mps
float32 east_m                   # position in the base station's local frame
float32 north_m

float32 distance_to_target_m     # -1 when no leg is active
float32 bearing_to_target_deg

float32 battery_pct
float32 battery_voltage
float32 link_rssi_dbm            # as measured at the rover
