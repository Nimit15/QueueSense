#!/usr/bin/env python3
"""
Create a network with restricted outflow at out_east to cause spillback on art_east.
"""

import os
import subprocess
import sys

def create_network_files():
    sumo_net_dir = "D:/QueueSense/sumo/network_restricted"
    os.makedirs(sumo_net_dir, exist_ok=True)

    # Use the same node file as original
    node_file = "D:/QueueSense/sumo/network/corridor.nod.xml"
    # Copy node file to restricted directory
    import shutil
    shutil.copy(node_file, os.path.join(sumo_net_dir, "corridor.nod.xml"))

    # 2. Edges: Corridor connecting N0 -> N1 -> N2 with bottleneck on N1 -> N2 (single lane)
    # and restricted outflow on out_east
    edge_xml = '''<edges>
    <!-- Main arterial West to East -->
    <edge id="in_west" from="N0" to="N1" priority="2" numLanes="2" speed="13.9"/>
    <edge id="art_east" from="N1" to="N2" priority="2" numLanes="1" speed="13.9" friction="0.9"/> <!-- Bottleneck: 1 lane -->
    <edge id="out_east" from="N2" to="E1" priority="2" numLanes="1" speed="5.0"/> <!-- Restricted outflow: 1 lane, low speed -->

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
        f"--node-files={os.path.join(sumo_net_dir, 'corridor.nod.xml')}",
        f"--edge-files={edge_file}",
        f"--output-file={os.path.join(sumo_net_dir, 'corridor.net.xml')}"
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"Successfully generated network at {os.path.join(sumo_net_dir, 'corridor.net.xml')}")
    except FileNotFoundError:
        print("Warning: 'netconvert' not found in PATH. Ensure SUMO is installed and added to environment variables.")
    except Exception as e:
        print(f"Error running netconvert: {e}")

if __name__ == "__main__":
    create_network_files()