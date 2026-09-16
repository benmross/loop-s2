# The rover's answer to one command. Without this the console can only show
# what it sent, not what arrived, which over a lossy link is not the same
# thing.

std_msgs/Header header
uint32 sequence
bool accepted
string detail        # why it was refused, or what it did
