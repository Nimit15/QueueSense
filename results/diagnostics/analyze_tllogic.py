import xml.etree.ElementTree as ET
net_file = "D:/QueueSense/sumo/network/corridor.net.xml"
tree = ET.parse(net_file)
root = tree.getroot()

# find tlLogic with id N1
for tl in root.findall('.//tlLogic'):
    if tl.get('id') == 'N1':
        print("tlLogic N1 found")
        for i, phase in enumerate(tl.findall('phase')):
            state = phase.get('state')
            duration = phase.get('duration')
            print(f"Phase {i}: duration={duration}, state={state}")
            # we will later map connections
        break

# Now collect connections
print("\nConnections:")
for conn in root.findall('.//connection'):
    frm = conn.get('from')
    to = conn.get('to')
    tl = conn.get('tl')
    linkIndex = conn.get('linkIndex')
    state = conn.get('state')
    dir_attr = conn.get('dir')
    if tl == 'N1':
        print(f"  {frm} -> {to} (tl={tl}, linkIndex={linkIndex}, dir={dir_attr}, state={state})")