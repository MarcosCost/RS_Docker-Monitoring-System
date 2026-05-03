import docker
import os

### Discovery phase

client = docker.from_env()
# Get agent's Id
container_name = os.environ.get('MY_CONTAINER_NAME')

try:
    me = client.containers.get(container_name)
    print(f"Agent Container ID: {me.short_id} , container named {container_name}")
except docker.errors.NotFound:
    print(f"Still can't find myself! Docker thinks I am not: {container_name}")


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

    print(f"Linked to Target: {target.name} ({target.short_id})")
    print(f"Shared IP Address: {ip_addr}")
    print(f"Shared Ports: {', '.join(ports)}")
else:
    print(f"Agent is not running in 'container' network mode. Current mode: {network_mode}")
