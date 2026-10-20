#!/usr/bin/env python3
"""
Create a network with N2 as a traffic light to enable proper spillback at the bottleneck.
"""

import os
import subprocess
import sys

def create_network_files():
    sumo_net_dir = "D:/QueueSense/sumo/network"
    os.makedirs(sumo_net_dir, exist_ok=True)

    # 1. Nodes: J1 (Main junction), J2 (Downstream junction/bottleneck - now a traffic light)
    node_xml = '''<nodes>
    <node id="N0" x="0.0" y="200.0" type="priority"/>
    <node id="N1" x="200.0" y="200.0" type="traffic_light"/>
    <node id="N2" x="400.0" y="200.0" type="traffic_light"/>  <!-- Now a traffic light -->
    <node id="W1" x="0.0" y="0.0" type="priority"/>
    <node id="E1" x="400.0" y="0.0" type="priority"/>
</nodes>'''

    node_file = os.path.join(sumo_net_dir, "corridor.nod.xml")
    with open(node_file, "w") as f:
        f.write(node_xml)

    # 2. Edges: Corridor connecting N0 -> N1 -> N2 with bottleneck on N1 -> N2 (single lane)
    edge_xml = '''<edges>
    <!-- Main arterial West to East -->
    <edge id="in_west" from="N0" to="N1" priority="2" numLanes="2" speed="13.9"/>
    <edge id="art_east" from="N1" to="N2" priority="2" numLanes="1" speed="13.9" friction="0.9"/> <!-- Bottleneck: 1 lane -->
    <edge id="out_east" from="N2" to="E1" priority="2" numLanes="2" speed="13.9"/>

    <!-- Return arterial East to West -->
    <edge id="in_east" from="N2" to="N1" priority="2" numLanes="2" speed="13.9"/>
    <edge id="art_west" from="N1" to="N0" priority="2" numLanes="2" speed="13.9"/>

    <!-- Cross street North-South on N1 -->
    <edge id="in_north" from="W1" to="N1" priority="1" numLanes="1" speed="11.1"/>
    <edge id="out_north" from="N1" to="W1" priority="1" numLanes="1" speed="11.1"/>
</edges>'''

    edge_file = os.path.join(sumo_net_dir, "corridor.edg.xml")
    with open(edge_file, "w") as f:
        f.write(edge_xml)

    print(f"Generated node and edge files in {sumo_net_dir}")

    # Run netconvert
    cmd = [
        "netconvert",
        f"--node-files={node_file}",
        f"--edge-files={edge_file}",
        f"--output-file={os.path.join(sumo_net_dir, 'corridor.net.xml')}"
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"Successfully generated network")
    except FileNotFoundError:
        print("Warning: 'netconvert' not found in PATH. Ensure SUMO is installed and added to environment variables.")
    except Exception as e:
        print(f"Error running netconvert: {e}")

if __name__ == "__main__":
    create_network_files()