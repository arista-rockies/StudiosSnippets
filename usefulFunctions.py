# the debug boolean will dump data into the message of the day tag
#  on the switch.  this is a rough way to get debug text out while
#  development is happening.  do not enable this flag in production
DEBUG = False

# this function uses the mako context to output a formatted string
#  for cvp to process the generated configuration it's important
#  that the string be newLine terminated.  rather than requiring
#  the user to specify that manually on every line we append it here
#  unless asked not to. this method of indenting will almost certainly
#  not behave as intended for complex types
def output(outStr, indent=2, level=0, flush=True):
    # if the input is not a string, let's just use the default converter
    #  for whatevever it is and hope for the best.
    if not isinstance(outStr, str):
        outStr = f'{outStr}'
    context.write(f'{outStr.rjust((indent*level)+len(outStr))}')
    if flush:
        context.write("\n")

# this next block of code will add a python decorator to the studio
#  which will allow you to time each function to see how long it takes
#  before the function prototype, add a line @benchmark.  This
#  will automatically be called and do some magic time collection
#  you'll never call benchmark() directly.  at the end of the studio
#  you can call dumpStats and pass in the stats structure to log the
#  results using the built in log system, not the banner
from time import perf_counter, process_time_ns
from collections.abc import Callable
from typing import Any

stats = {}

def benchmark(func: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        startTime = process_time_ns() #perf_counter()
        result = func(*args, **kwargs)
        timer = process_time_ns() - startTime
        if not func.__name__ in stats:
            stats[func.__name__] = {'sum': 0, 'count': 0, 'timings': []}
        stats[func.__name__]['count'] += 1
        stats[func.__name__]['sum'] += timer
        stats[func.__name__]['timings'].append(timer)
        return result
    if not DEBUG:
        return func
    else:
        return wrapper

def dumpStats(stats):
    from statistics import mean
    for fun, timings in stats.items():
        stats[fun]['average'] = timings['sum']/timings['count']/1e9
    for fun, timings in dict(sorted(stats.items(), key=lambda item: item[1]['average'], reverse=True)).items():
        ctx.info(f"{fun:<40}: {timings['average']:>25}s{timings['count']:>5} iteration(s)")

# this function will fetch and return a dictionary of all tags for a specified device within the workspace
#  the dictionary's keys are the tag label, the values are stored in a list - regardless as to how many
#  values for a given tag exist.   (if the tag exists with a single value you'll get a list with one item)
from arista.tag.v2.services import (
    TagAssignmentConfigServiceStub,
    TagAssignmentConfigStreamRequest,
    TagAssignmentServiceStub,
    TagAssignmentStreamRequest
)

from arista.tag.v2.tag_pb2 import (
    TagAssignmentConfig,
    TagAssignment,
    ELEMENT_TYPE_DEVICE,
    CREATOR_TYPE_USER
)

from copy import deepcopy

@benchmark
def getTagForDeviceByLabel(workspaceID, tagLabelList):
    result = {}
    initializer = {}

    workspaceTagClient = ctx.getApiClient(TagAssignmentConfigServiceStub)
    workspaceGetAllRequest = TagAssignmentConfigStreamRequest()
    workspaceTagFilter = TagAssignmentConfig()

    mainlineTagClient = ctx.getApiClient(TagAssignmentServiceStub)
    mainlineGetAllRequest = TagAssignmentStreamRequest()
    mainlineTagFilter = TagAssignment()

    workspaceTagFilter.key.element_type = mainlineTagFilter.key.element_type = ELEMENT_TYPE_DEVICE
    mainlineTagFilter.tag_creator_type = CREATOR_TYPE_USER

    # now let's set up all the filtering
    for tag in tagLabelList:
        mainlineTagFilter.key.workspace_id.value = ""
        workspaceTagFilter.key.workspace_id.value = workspaceID
        workspaceTagFilter.key.label.value = mainlineTagFilter.key.label.value = tag

        mainlineGetAllRequest.partial_eq_filter.append(mainlineTagFilter)
        workspaceGetAllRequest.partial_eq_filter.append(workspaceTagFilter)

        initializer[tag] = []

    # first thing to do is load up all the mainline tags
    for resp in mainlineTagClient.GetAll(mainlineGetAllRequest):
        label = resp.value.key.label.value
        value = resp.value.key.value.value
        deviceID = resp.value.key.device_id.value
        if deviceID not in result:
            result[deviceID] = deepcopy(initializer)
        result[deviceID][label].append(value)

    # now that i have all the mainline, let's add the workspace stuff in
    for resp in workspaceTagClient.GetAll(workspaceGetAllRequest):
        label = resp.value.key.label.value
        value = resp.value.key.value.value
        deviceID = resp.value.key.device_id.value

        if resp.value.remove.value == True:
            # this workspace entry is being removed from mainline
            try:
                result[deviceID][label].remove(value)
            except ValueError:
                pass
        else:
            # this is a new addition to from the workspace.  we need to append it
            if value not in result[deviceID][label]:
                result[deviceID][label].append(value)

    return result

if DEBUG:
    output("banner motd")

me=ctx.getDevice()
workspaceID=ctx.studio.workspaceId
interestingTagLabels = ['DC', 'Role', 'NodeId', 'Leaf-Number', 'Spine-Number', 'DC-Pod', 'Leaf-Domain', 'L2-Leaf-Domain', 'Super-Spine-Plane']
deviceTags = getTagForDeviceByLabel(workspace_id, interestingTagLabels)
output(deviceTags)

if DEBUG:
    output("EOF")
    dumpStats(stats)
