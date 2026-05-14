import socket

UDP_IP = "0.0.0.0"
UDP_PORT = 9999 

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((UDP_IP, UDP_PORT))
print(f"Listening for UDP packets on port {UDP_PORT}...")

while True:
    print("Im inside the while")
    data, addr = sock.recvfrom(1024) # returns (data,addr) => (data,(ip,port))
    print("I got a message on port 9999")
    print(f"Recieved data:\n{data}\nAddress:{addr[0]}")
    if "MQTT_BROKER_HERE" in data.decode():
        print("Found the broker")
        break

sock.close()