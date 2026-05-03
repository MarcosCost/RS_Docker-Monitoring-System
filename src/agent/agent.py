import docker
import os
import time
import json
import paho.mqtt.client as mqtt

### Discovery phase
metadata= dict()
 
client = docker.from_env()
# Get agent's Id
container_name = os.environ.get('MY_CONTAINER_NAME')

try:
    me = client.containers.get(container_name)
except docker.errors.NotFound:
    print(f"Can't find myself! Docker thinks I am not: {container_name}")

# Get parent container's Data
network_mode = me.attrs["HostConfig"]["NetworkMode"]

# Make sure the agent is running attachet to another container
if network_mode.startswith("container:"):
    target_id = network_mode.split(":")[1]
    target = client.containers.get(target_id)

    target.reload()

    # Data
    networks = target.attrs['NetworkSettings']['Networks']
    ip_addr = next(iter(networks.values()))['IPAddress']
    port_data = target.attrs['NetworkSettings']['Ports']
    # Wrap in a set {} to get rid of ipv4 and ipv6 duplicates
    ports = {f"Host {b['HostPort']} -> Container {p}" for p, bindings in port_data.items() if bindings  for b in bindings}

    metadata.update({"Parent_id":target_id})
    metadata.update({"Parent_name":target.name})
    metadata.update({"Ip":ip_addr})
    metadata.update({"Ports":list(ports)})

else:
    print(f"Agent is not running in 'container' network mode. Current mode: {network_mode}")
 

### Initiall publish of metadata

BROKER_IP = os.getenv("MQTT_BROKER_ADDR", "mosquitto-broker") # services running in a diff machine must have the brokers IP in a env variable on the compose

# Connect to broker and tell him who (agent) is talking
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"agent-{me.short_id}")
 
#Setup last will for tracked service
client.will_set(
    topic=f"monitor/services/{target_id}/status", 
    payload="CRASHED", 
    qos=1, 
    retain=True
)
 
while True:
    try:
        client.connect(BROKER_IP, 1883, keepalive=10)
        break
    except:
        print(f"Connecting to broker at {BROKER_IP}...")
        time.sleep(2)
 
client.loop_start()


client.publish(
    topic=f"monitor/services/{target_id}/meta", 
    payload=json.dumps(metadata), 
    retain=True
)

### Heartbeat

while True:
    target.reload()
    if target.status == "running":
        payload = {"timestamp":time.time()}

        client.publish(
            topic=f"monitor/services/{target_id}/health",
            payload=json.dumps(payload)
        )
    else:
        print(f"'{target.name}' is currently not running")
        break
    time.sleep(5)

### Gracefull shutdown

print("Clean shutdown initiated...")

client.publish(f"monitor/services/{target_id}/status", "SHUTDOWN", retain=True)
client.disconnect()