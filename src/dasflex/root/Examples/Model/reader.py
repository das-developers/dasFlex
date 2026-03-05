# This file is free and unencumbered software released into the public domain.
# 
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
# 
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
# 
# For more information, please refer to <https://unlicense.org>

import sys
import math

import das2

def write(s):
	sys.stdout.buffer.write(s.encode('utf-8'))

# The conventional das2 argument order for model data is: 
#  
#   Interval Begin End [Ex_Param1 Ex_Param2 ...]
#
# DasFlex doesn't require this, but the DSDF format does,
# and we're going to import this reader as a legacy das2
# data source using it's DSDF file.

interval = int(sys.argv[1], 10) # <-- seconds
beg_time = das2.DasTime(sys.argv[2])
end_time = das2.DasTime(sys.argv[3])

header = '''<stream version="2.2">
  <properties 
    double:zFill="-1.0e+31"
    DatumRange:xRange="%s to %s UTC"
    String:title="Solar Longitude" 
  />
</stream>
'''%(str(beg_time), str(end_time))

write("[00]{:06d}{}".format(len(header), header))

packet = '''<packet>
  <x type="time27" units="t1970"></x>
  <y type="ascii8" name="mlt" units="h">
    <properties String:yLabel="MLT" />
  </y>
</packet>
'''
    
write("[01]{:06d}{}".format(len(packet), packet))

# It's good to flush stdout output right after sending headers. 
# For slow calculations this let's the client know we're alive.
sys.stdout.buffer.flush()

cur_time = beg_time
while cur_time < end_time:
	hours = cur_time.hour() + cur_time.minute() / 60.0 + cur_time.sec() / 3600.0
	val = math.sin((2 * math.pi / 24)*(hours + 12))
	write(":01:{} {:+7.3f}\n".format(cur_time,val))
	cur_time = cur_time + interval
