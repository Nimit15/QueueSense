import xml.etree.ElementTree as ET

net_file = "D:/QueueSense/sumo/network/corridor.net.xml"
tree = ET.parse(net_file)
root = tree.getroot()

# Build mapping from linkIndex to (from_edge, to_edge, dir)
link_to_conn = {}
for conn in root.findall('.//connection'):
    lid_attr = conn.get('linkIndex')
    if lid_attr is None:
        continue  # skip connections without linkIndex (internal junctions)
    lid = int(lid_attr)
    frm = conn.get('from')
    to = conn.get('to')
    link_to_conn[lid] = (frm, to, conn.get('dir'))

# Get tlLogic N1
for tl in root.findall('.//tlLogic'):
    if tl.get('id') == 'N1':
        print("tlLogic N1 found")
        phases = []
        for phase_elem in tl.findall('phase'):
            state = phase_elem.get('state')
            duration = phase_elem.get('duration')
            phases.append((int(duration), state))
        break

# For each phase, determine which incoming edges get green
incoming_edges = set(['in_north', 'in_east', 'in_west'])  # we ignore out_north as it's exit
phase_idx = 0
for duration, state in phases:
    print(f"\nPhase {phase_idx}: duration={duration}, state={state}")
    # For each linkIndex, get state char
    green_links = []
    for lid, (frm, to, dir_attr) in link_to_conn.items():
        ch = state[lid] if lid < len(state) else '?'
        if ch in ('G', 'g'):
            green_links.append((lid, frm, to, dir_attr))
            # Determine if this link's from_edge is an incoming edge of interest
            if frm in incoming_edges:
                print(f"  Green for approach {frm} -> {to} (dir={dir_attr}) [linkIndex {lid}]")
        elif ch in ('y', 'Y'):
            # yellow
            pass
        elif ch in ('r', 'R'):
            # red
            pass
        else:
            print(f"  Unknown state '{ch}' for link {lid} ({frm}->{to})")
    phase_idx += 1

# Also compute which approaches get any green in each phase
print("\n=== Summary: Which approaches get green in each phase? ===")
for phase_idx, (duration, state) in enumerate(phases):
    approaches_green = set()
    for lid, (frm, to, dir_attr) in link_to_conn.items():
        ch = state[lid]
        if ch in ('G', 'g'):
            if frm in incoming_edges:
                approaches_green.add(frm)
    print(f"Phase {phase_idx} (duration {duration}): approaches with green: {approaches_green}")