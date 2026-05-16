import docker # type: ignore
import socket
import os
import time
import json
import paho.mqtt.client as mqtt # pyright: ignore[reportMissingImports]

BROKER_PORT=1883

def find_broker_ip():
    UDP_IP = "0.0.0.0"
    UDP_PORT = 9999 

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"\nListening for UDP packets on port {UDP_PORT}...")

    while True:
        data, addr = sock.recvfrom(1024) # returns (data,addr) => (data,(ip,port))
        print(f"Recieved data:\n{data}\nAddress:{addr[0]}")
        if "MQTT_BROKER_HERE" in data.decode():
            print("Found the broker\n")
            break

    sock.close()
    return  addr[0]

def get_container_metadata(client, container_name):
    """
    Discovery phase: Get metadata about the container this agent is monitoring.
    """
    metadata = {}
    
    try:
        me = client.containers.get(container_name)
    except docker.errors.NotFound:
        print(f"Can't find myself! Docker thinks I am not: {container_name}")
        return None, None, None

    # Get parent container's Data
    network_mode = me.attrs["HostConfig"]["NetworkMode"]

    # Make sure the agent is running attached to another container
    if not network_mode.startswith("container:"):
        print(f"Agent is not running in 'container' network mode. Current mode: {network_mode}")
        return me, None, None

    target_id = network_mode.split(":")[1]
    target = client.containers.get(target_id)
    target.reload()

    # Gather network data
    networks = target.attrs['NetworkSettings']['Networks']
    ip_addr = next(iter(networks.values()))['IPAddress']
    port_data = target.attrs['NetworkSettings']['Ports']
    
    # Wrap in a set to remove duplicates, then convert to list
    ports = {f"Host {b['HostPort']} -> Container {p}" for p, bindings in port_data.items() if bindings for b in bindings}

    metadata.update({
        "Parent_id": target_id,
        "Parent_name": target.name,
        "Ip": ip_addr,
        "Ports": list(ports)
    })

    return me, target, metadata

def setup_mqtt_client(agent_id, target_id, broker_ip):
    """
    Connect to the MQTT broker and configure Last Will and Testament.
    """
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"agent-{agent_id}")
    
    # Setup last will for tracked service
    client.will_set(
        topic=f"monitor/services/{target_id}/status", 
        payload="CRASHED", 
        qos=1, 
        retain=True
    )
    
    while True:
        try:
            print(f"Connecting to broker at {broker_ip}...")
            client.connect(broker_ip, BROKER_PORT, keepalive=10)
            break
        except Exception as e:
            print(f"Failed to connect to broker: {e}. Retrying in 5s...")
            time.sleep(5)
    
    client.loop_start()
    return client

def run_heartbeat(client, target, target_id):
    """
    Main loop to publish health checks as long as the target container is running.
    """
    print(f"Starting heartbeat for target: {target_id}")
    try:
        while True:
            target.reload()
            if target.status == "running":
                payload = {"timestamp": time.time()}
                client.publish(
                    topic=f"monitor/services/{target_id}/health",
                    payload=json.dumps(payload)
                )
            else:
                print(f"Target '{target.name}' is no longer running (status: {target.status})")
                break
            time.sleep(5)
    except KeyboardInterrupt:
        print("Heartbeat interrupted by user.")

def get_rtt(ip):
    """
    Open a TCP socket to simulate the networks RTT from one machine to another
    Returns the time in Ms    
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)

    inicio = time.perf_counter()
    try:
        sock.connect((ip, BROKER_PORT))
        fim = time.perf_counter()

        rtt_ms = (fim - inicio) * 1000
        return round(rtt_ms, 2)
    except socket.error as e:
        print(f"Erro ao medir RTT por TCP: {e}")
        return "N/A"
    finally:
        sock.close()
        

def main():
    # 1. Initialization
    docker_client = docker.from_env()
    container_name = os.environ.get('MY_CONTAINER_NAME')
    broker_ip = find_broker_ip()

    # 2. Discovery
    me, target, metadata = get_container_metadata(docker_client, container_name)
    
    if not me or not target:
        print("Discovery failed. Exiting.")
        return
    print("\nGot valid container metadata\n")

    target_id = metadata["Parent_id"]

    # 3. MQTT Setup & Initial Publish
    mqtt_client = setup_mqtt_client(me.short_id, target_id, broker_ip)
    
    print(f"\nPublishing initial metadata for {target_id}")
    mqtt_client.publish(
        topic=f"monitor/services/{target_id}/meta", 
        payload=json.dumps(metadata), 
        retain=True
    )

    # 4. Heartbeat Loop
    run_heartbeat(mqtt_client, target, target_id)

    # 5. Graceful Shutdown
    print("Clean shutdown initiated...")
    mqtt_client.publish(f"monitor/services/{target_id}/status", "SHUTDOWN", retain=True)
    mqtt_client.disconnect()
    mqtt_client.loop_stop()

if __name__ == "__main__":
    main()