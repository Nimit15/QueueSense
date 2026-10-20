import xml.etree.ElementTree as ET

net_file = "D:/QueueSense/sumo/network/corridor.net.xml"
tree = ET.parse(net_file)
root = tree.getroot()

for edge in root.findall('.//edge'):
    edge_id = edge.get('id')
    if edge_id in ["art_east", "art_west", "out_east", "in_east", "in_west", "in_north", "out_north"]:
        length = None
        for lane in edge.findall('.//lane'):
            length = lane.get('length')
            break
        print(f"{edge_id}: length = {length} m")