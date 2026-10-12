#!/usr/bin/env python3
"""
QueueSense Network Generation Script
Generates a 2-junction corridor network with a downstream bottleneck link
to enable proper spillback and queue propagation testing.
"""

import os
import subprocess
import sys

def create_network_files():
    sumo_net_dir = "D:/QueueSense/sumo/configs"
    os.makedirs(sumo_net_dir, exist_ok=True)

    net_dir = "D:/QueueSense/sumo/network"
    os.makedirs(net_dir, exist_ok=True)

    net_file = os.path.join(net_dir, "corridor.net.xml")

    # Using node and edge files for precise control over bottleneck
    node_file = os.path.join(net_dir, "corridor.nod.xml")
    edge_file = os.path.join(net_dir, "corridor.edg.xml")
    conn_file = os.path.join(net_dir, "corridor.con.xml")

    # 1. Nodes: J1 (Main junction), J2 (Downstream junction/bottleneck)
    node_xml = '''<nodes>
    <node id="N0" x="0.0" y="200.0" type="priority"/>
    <node id="N1" x="200.0" y="200.0" type="traffic_light"/>
    <node id="N2" x="400.0" y="200.0" type="priority"/>
    <node id="W1" x="0.0" y="0.0" type="priority"/>
    <node id="E1" x="400.0" y="0.0" type="priority"/>
</nodes>'''

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

    with open(edge_file, "w") as f:
        f.write(edge_xml)

    print(f"Generated node and edge files in {net_dir}")

    # Run netconvert
    cmd = [
        "netconvert",
        f"--node-files={node_file}",
        f"--edge-files={edge_file}",
        f"--output-file={net_file}"
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"Successfully generated network at {net_file}")
    except FileNotFoundError:
        print("Warning: 'netconvert' not found in PATH. Ensure SUMO is installed and added to environment variables.")
    except Exception as e:
        print(f"Error running netconvert: {e}")

if __name__ == "__main__":
    create_network_files()
