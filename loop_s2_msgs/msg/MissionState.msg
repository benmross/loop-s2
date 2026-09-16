# What the rover believes about the mission. Published at a low rate and
# latched, so a console that starts late, or reconnects after a dropout, has
# the whole leg list without asking for it.

uint8 MODE_IDLE=0
uint8 MODE_AUTONOMOUS=1
uint8 MODE_TELEOP=2
uint8 MODE_ABORTED=3

# The rules require an LED on the back of the rover, visible in bright
# daylight: red for autonomous, blue for teleoperation, flashing green on
# arrival at a target. This is what that LED is showing right now, so the
# operator sees the same signal as the judge standing at the course.
uint8 LIGHT_OFF=0
uint8 LIGHT_RED=1
uint8 LIGHT_BLUE=2
uint8 LIGHT_FLASHING_GREEN=3

std_msgs/Header header
uint8 mode
uint8 signal_light
int16 active_leg           # -1 when the rover is not driving a leg
float32 mission_elapsed_s
float32 mission_limit_s
float32 max_speed_mps      # the limit the operator has set
MissionLeg[] legs
