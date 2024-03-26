# Copyright (c) 2023-present CorEdge India Pvt. Ltd - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Parth Yadav <parth@coredge.io>, Oct 2023
# 
# visit https://coredge.io for more.

import socket
import os

import logging
logger = logging.getLogger("dstreamer_agent")

DEFAULT_SOCKET_PATH = '/run/dstreamer/agent.sock'

class DstreamerAgentClient:
    """Handles communication with dstreamer_agent running on workspace
    """
    def __init__(self, socket_path):
        self.socket_path = DEFAULT_SOCKET_PATH if not socket_path else socket_path

    def send_command(self, command):
        try:
            # Check if the socket file exists and is writable.
            if not os.path.exists(self.socket_path) or not os.access(self.socket_path, os.W_OK):
                logger.error(f"Socket file '{self.socket_path}' does not exist or insufficient permissions.")
                return False

            # Create a Unix domain socket
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

            # Connect to the socket
            sock.connect(self.socket_path)

            # Send the command to the socket
            sock.sendall(command.encode())

            # Close the socket connection
            sock.close()
        except Exception as e:
            logger.error(f"Error sending command to socket: {e}")
            return False

        return True

    def shutdown(self):
        self.send_command("shutdown")

# Example usage:
# client = DstreamerAgentClient("/run/dstreamer/agent.sock")
# client.send_command("some_message")
# client.shutdown()
