import json
import arista.tag.v2

# the debug boolean will dump data into the message of the day tag
#  on the switch.  this is a rough way to get debug text out while
#  development is happening.  do not enable this flag in production
debug = False

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

# this function will fetch and return a dictionary of all tags for a specified device within the workspace
#  the dictionary's keys are the tag label, the values are stored in a list - regardless as to how many
#  values for a given tag exist.   (if the tag exists with a single value you'll get a list with one item)
def getTagForDeviceByLabel(deviceID, workspaceID):
    result = {}
    defaultValues = {}
    workspaceValues = {}

    tagClient = ctx.getApiClient(arista.tag.v2.services.TagAssignmentServiceStub)
    get_all_req = arista.tag.v2.services.TagAssignmentStreamRequest()
    tag_filter = arista.tag.v2.models.TagAssignment()
    tag_filter.key.element_type = arista.tag.v2.models.ELEMENT_TYPE_DEVICE
    tag_filter.key.device_id.value = deviceID
    tag_filter.key.workspace_id.value = ""
    get_all_req.partial_eq_filter.append(tag_filter)

    tag_filter.key.workspace_id.value = workspaceID
    get_all_req.partial_eq_filter.append(tag_filter)
        
    for resp in tagClient.GetAll(get_all_req):
        label = resp.value.key.label.value
        value = resp.value.key.value.value
        #output(f'{label}:{value}:{resp.value.key.workspace_id.value}')
        if resp.value.key.workspace_id.value:
            if label in workspaceValues:
                workspaceValues[label].append(value)
            else:
                workspaceValues[label] = [value]
        else:
            if label in defaultValues:
                defaultValues[label].append(value)
            else:
                defaultValues[label] = [value]

    # we want to prefer any tags that come from the workspace over any key that comes from the default
    result = defaultValues

    for key, value in workspaceValues.items():
        result[key] = value

    return result

if debug:
    output("banner motd")

me=ctx.getDevice()
workspaceID=ctx.studio.workspaceId

deviceTags = getTagForDeviceByLabel(me.id, workspaceID)

output(deviceTags)

if debug:
    output("EOF")
