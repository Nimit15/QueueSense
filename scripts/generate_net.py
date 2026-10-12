# Script to generate a minimal 4-way intersection SUMO network
import os
import subprocess

def generate_network():
    # Define paths
    network_dir = "D:/QueueSense/sumo/network"
    os.makedirs(network_dir, exist_ok=True)

    # Create simple net.xml using netconvert
    # 4 approaches, 1 lane each for simplicity initially
    net_xml = os.path.join(network_dir, "intersection.net.xml")

    # Using netconvert command line
    # Generating a simple 4-way cross
    cmd = [
        "netconvert",
        "--grid.number=2",
        "--grid.width=100",
        "--grid.height=100",
        "-o", net_xml
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"Network generated at {net_xml}")
    except Exception as e:
        print(f"Error generating network: {e}")

if __name__ == "__main__":
    generate_network()
