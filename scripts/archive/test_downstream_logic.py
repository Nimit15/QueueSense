#!/usr/bin/env python3
"""
Test the downstream eligibility logic in isolation.
"""

import xml.etree.ElementTree as ET

def build_downstream_edges(net_file):
    """Build downstream edges mapping from network file."""
    tree = ET.parse(net_file)
    root = tree.getroot()
    downstream_edges = {}  # map from edge_id to list of downstream edge_ids
    for conn in root.findall('.//connection'):
        tl_id = conn.get('tl')
        if tl_id and tl_id.strip():  # if there is a traffic light id
            from_edge = conn.get('from')
            to_edge = conn.get('to')
            if from_edge and to_edge:
                if from_edge not in downstream_edges:
                    downstream_edges[from_edge] = []
                downstream_edges[from_edge].append(to_edge)
    return downstream_edges

def test_downstream_logic():
    """Test downstream eligibility logic with mock occupancies."""
    net_file = "D:/QueueSense/sumo/network/corridor.net.xml"
    downstream_edges = build_downstream_edges(net_file)

    print("Downstream edges mapping:")
    for edge, downs in downstream_edges.items():
        print(f"  {edge} -> {downs}")

    # Test case 1: All downstream edges below threshold -> should be eligible
    occupancies = {
        "art_east": 0.5,
        "art_west": 0.3,
        "out_north": 0.4
    }
    threshold = 0.85

    for approach in ["in_north", "in_east", "in_west"]:
        if approach in downstream_edges:
            downstream_occs = [occupancies[edge] for edge in downstream_edges[approach]]
            eligible = any(occ < threshold for occ in downstream_occs)
            print(f"{approach}: downstream occs = {downstream_occs}, eligible = {eligible}")
            assert eligible == True, f"{approach} should be eligible when all downstream < threshold"

    # Test case 2: All downstream edges above threshold -> should NOT be eligible
    occupancies = {
        "art_east": 0.9,
        "art_west": 0.9,
        "out_north": 0.9
    }

    for approach in ["in_north", "in_east", "in_west"]:
        if approach in downstream_edges:
            downstream_occs = [occupancies[edge] for edge in downstream_edges[approach]]
            eligible = any(occ < threshold for occ in downstream_occs)
            print(f"{approach}: downstream occs = {downstream_occs}, eligible = {eligible}")
            assert eligible == False, f"{approach} should NOT be eligible when all downstream >= threshold"

    # Test case 3: Mixed occupancies -> should be eligible if ANY below threshold
    occupancies = {
        "art_east": 0.9,  # above threshold
        "art_west": 0.5,  # below threshold
        "out_north": 0.9  # above threshold
    }

    for approach in ["in_north", "in_east", "in_west"]:
        if approach in downstream_edges:
            downstream_occs = [occupancies[edge] for edge in downstream_edges[approach]]
            eligible = any(occ < threshold for occ in downstream_occs)
            print(f"{approach}: downstream occs = {downstream_occs}, eligible = {eligible}")
            assert eligible == True, f"{approach} should be eligible when at least one downstream < threshold"

    print("\nAll tests passed!")

if __name__ == "__main__":
    test_downstream_logic()