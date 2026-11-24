"""Enqueue closed MCAP segments from one ROS 2 recorder in one output folder."""
import argparse
from pathlib import Path
import rclpy
from rclpy.node import Node
from rosbag2_interfaces.msg import WriteSplitEvent
from gantry.source_receipts import enqueue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--folder", required=True, type=Path, help="Specific existing recording folder in the workspace")
    parser.add_argument("--topic", required=True, help="WriteSplitEvent topic of the enrolled recorder")
    parser.add_argument("--recorder", required=True, help="Fully qualified recorder node name")
    args = parser.parse_args()
    root = args.workspace.resolve(strict=True)
    folder = args.folder.resolve(strict=True)
    if root not in folder.parents:
        parser.error("Select one recording subdirectory inside the workspace")
    rclpy.init(args=[])
    node = Node("gantry_rosbag_completion")
    def receive(message):
        if getattr(message, "node_name", None) != args.recorder or not message.closed_file:
            return
        path = Path(message.closed_file)
        if path.parent != folder or path.suffix.lower() != ".mcap":
            return
        try:
            enqueue(root, "rosbag-closed", path.relative_to(root), path.name)
            node.get_logger().info("Queued closed MCAP segment")
        except (OSError, ValueError, KeyError) as exc:
            node.get_logger().error("Gantry receipt held: " + str(exc))
    node.create_subscription(WriteSplitEvent, args.topic, receive, 10)
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
