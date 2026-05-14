import socket
import time

BROADCAST_PORT = 9999

MESSAGE = b"MQTT_BROKER_HERE"

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

print("Shouting IP to the network...")
while True:
    # 255.255.255.255 is to broadcast to the network
    sock.sendto(MESSAGE, ('255.255.255.255', BROADCAST_PORT))
    time.sleep(5)