#!/bin/bash
# Record a run of the console, driving it through the cases worth showing:
# start a leg, change the speed limit, ride out a scheduled link dropout,
# abort, hand back to manual, then take the rover off the air and watch the
# console notice.
#
# Clicks come from xdotool so the run is the same every time.
# Needs: ffmpeg, xdotool, and a built workspace on DISPLAY.
#
#   ./scripts/record_demo.sh /tmp/s2demo.mp4

set -e
OUT=${1:-/tmp/s2demo.mp4}
: "${DISPLAY:=:0}"
export DISPLAY

ros2 launch loop_s2_gui console.launch.py dropout_every_s:=26.0 dropout_duration_s:=7.0 \
    > /tmp/s2-demo.log 2>&1 < /dev/null &
sleep 16

WID=$(xdotool search --name "URC Operator Console" | head -1)
eval "$(xdotool getwindowgeometry --shell "$WID")"
xdotool windowactivate --sync "$WID"
px() { python3 -c "print(int($X + $1*$WIDTH))"; }
py() { python3 -c "print(int($Y + $1*$HEIGHT))"; }

ffmpeg -loglevel error -y -f x11grab -framerate 10 -video_size "${WIDTH}x${HEIGHT}" \
    -i ":0.0+${X},${Y}" -t 82 -c:v libx264 -preset ultrafast -qp 0 "$OUT" &
RECORDER=$!

sleep 4
xdotool mousemove "$(px 0.203)" "$(py 0.704)" click 1      # START SELECTED LEG
sleep 14
xdotool mousemove "$(px 0.174)" "$(py 0.769)" mousedown 1  # drag the speed limit down
sleep 1
xdotool mousemove "$(px 0.115)" "$(py 0.769)"
sleep 1
xdotool mouseup 1
sleep 22                                                   # a scheduled dropout lands here
xdotool windowactivate --sync "$WID"
xdotool key --clearmodifiers space                         # ABORT
sleep 5
xdotool mousemove "$(px 0.294)" "$(py 0.740)" click 1      # RESUME (MANUAL)
sleep 3
pkill -f "install/loop_s2_gui/lib/loop_s2_gui/rover_sim"   # the rover goes off the air
sleep 3
xdotool mousemove "$(px 0.203)" "$(py 0.704)" click 1      # a command with nobody listening
wait $RECORDER
echo "wrote $OUT"
