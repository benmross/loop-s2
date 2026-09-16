# One leg of the URC Autonomous Navigation Mission: a place the rover has to
# reach on its own. The mission uses GNSS-only waypoints, AR-tagged posts and
# unmarked ground objects, and the operator is told which kind each leg is
# because it changes what counts as arrival.

uint8 TYPE_GNSS=0      # coordinates only, nothing to see at the target
uint8 TYPE_POST=1      # AR-tagged post, coordinates are approximate
uint8 TYPE_OBJECT=2    # unmarked object on the ground, e.g. mallet or bottle

uint8 STATUS_PENDING=0
uint8 STATUS_ACTIVE=1
uint8 STATUS_REACHED=2
uint8 STATUS_SKIPPED=3
uint8 STATUS_FAILED=4

uint8 id
string label
uint8 type
uint8 status
float64 latitude
float64 longitude
float32 tolerance_m    # how close the rover has to get for this leg to count
