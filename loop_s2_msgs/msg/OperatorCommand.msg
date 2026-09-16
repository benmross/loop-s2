# An instruction from the console. Sent reliably and carrying a sequence
# number, because the console resends anything the rover has not acknowledged
# and the rover has to be able to tell a resend from a second press.

uint8 START_LEG=0
uint8 SKIP_LEG=1
uint8 ABORT=2
uint8 RESUME_TELEOP=3
uint8 SET_MAX_SPEED=4

std_msgs/Header header
uint32 sequence
uint8 command
int16 leg_id         # for START_LEG and SKIP_LEG
float32 value        # for SET_MAX_SPEED, in m/s
string issued_by     # who sent it, for the mission log
                     # (not "operator": that is a C++ keyword, and the
                     #  generated message code will not compile with it)
