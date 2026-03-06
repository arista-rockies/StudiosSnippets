<%
import ipaddress, itertools
from time import process_time_ns
from collections.abc import Callable
from typing import Any

from cloudvision.cvlib.tags import Tag
from cloudvision.cvlib.device import Device

DEBUG = False
if DEBUG:
    ctx.benchmarkingOn()

# this is a convenience class to manage tags.  it's a dict with some special sauce
#   it inherits from dict and functions largely similarly with the exception of
#     a save function which will write to aeris -- this could have the load in it as well?
#     each key value is generally assumed to be a list of the tag values.
#       a get on a key will return the 0th item if there is only one item in the last.
#         else it will return
#       a set on a key will append a value to the list
#     setRaw() and getRaw() will get or set unconditionally the underlying value
#     setGenerated() will sets a flag to enable saving of new generated tags only
# some of this code borrowed from cvlib
class Tags(dict):
    def __init__(self):
        self._generated = list()
        self.tagsType = 'device'
        super().__init__()

    def setGenerated(self, key: str):
        if key in self.keys() and key not in self._generated:
            self._generated.append(key)

    def saveGenerated(self, device: Device):
        for key in self._generated:
            v = super().__getitem__(key)
            
            # depending on our type we have a different code path to save:
            if self.tagsType == 'interface':
                if DEBUG:
                    output(f"saving interfaceTag: {key} -> {v} on {device.id}")
                continue
            else:
                if DEBUG:
                    output(f"saving deviceTag: {key} -> {str(v[0])} on {device.id}")

                device._assignTag(ctx, Tag(str(key), str(v[0])), replaceValue=False)

    def setRaw(self, key: str, value: str):
        super().__setitem__(key, value)

    def getRaw(self, key: str):
        return super().get(key)

    def __setitem__(self, key: str, value: str):
        if key in self.keys():
            super().__getitem__(key).append(value)
        else:
            if isinstance(value, Tags):
                super().__setitem__(key, value)
            else:
                super().__setitem__(key, [value])

    def __getitem__(self, key: str) -> Any:
        if key in self.keys():
            k = super().__getitem__(key)
            if isinstance(k, Tags):
                return k

            l = len(k)
            if l > 1:
                return k
            elif l == 1:
                return k[0]
        return None

# this function uses the mako context to output a formatted string
#  for cvp to process the generated configuration it's important
#  that the string be newLine terminated.  rather than requiring
#  the user to specify that manually on every line we append it here
#  unless asked not to. this method of indenting will almost certainly
#  not behave as intended for complex types
def output(outStr: str, indent: int=2, level: int=0, flush: bool=True, isDebug: bool=False):
    if isDebug and not DEBUG:
        return

    # if the input is not a string, let's just use the default converter
    #  for whatevever it is and hope for the best.
    if not isinstance(outStr, str):
        outStr = f'{outStr}'
    if not outStr:
        return

    context.write(f'{outStr.rjust((indent*level)+len(outStr))}')
    if flush:
        context.write("\n")

# we could use the builtin stats dump, but formatting is a little funny so i'm overriding it here
def dumpStats(stats: dict):
    from statistics import mean
    for fun, timings in stats.items():
        stats[fun]['average'] = timings['sum']/timings['count']/1e9
    for fun, timings in dict(sorted(stats.items(), key=lambda item: item[1]['average'], reverse=True)).items():
        output(f"{fun:<40}: {timings['average']:>25.2f}s{timings['count']:>5} iteration(s)")

# this function will fetch and return a dictionary of all tags for a specified device within the workspace
#  the dictionary's keys are the tag label, the values are stored in a list - regardless as to how many
#  values for a given tag exist.   (if the tag exists with a single value you'll get a list with one item)
@ctx.benchmark
def getTagForDeviceByLabel(workspaceID: str, tagLabelList: list[str]) -> Tags:
    result = Tags()

    for device in ctx.topology.getDevices():
        result[device.id] = Tags()
        for tag in device.getTags(ctx):
            if tag.label in tagLabelList:
                result[device.id][tag.label] = tag.value

    return result

if DEBUG:
    output("banner motd")

me=ctx.getDevice()
workspaceID=ctx.studio.workspaceId
interestingTagLabels = ['DC', 'Role', 'NodeId', 'Leaf-Number', 'Spine-Number', 'DC-Pod', 'Leaf-Domain', 'L2-Leaf-Domain', 'Super-Spine-Plane']
deviceTags = getTagForDeviceByLabel(workspace_id, interestingTagLabels)
output(deviceTags)

if DEBUG:
    dumpStats(ctx.stats)
    output("EOF")
%>
