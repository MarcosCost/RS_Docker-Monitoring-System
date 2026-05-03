# RS Docker Monitor
Real-time Docker monitoring via MQTT. Academic project for the Networks and Services (RS) class.

## Architecture: The Sidecar Pattern

The monitoring agent is implemented as a Universal Sidecar. This architectural choice ensures that monitoring is non-intrusive; no modifications or extra configurations are required within the target services.

By using Docker's network_mode, the agent:
* **Shared Network Stack**: Operates within the same Network Namespace as the target, sharing the identical IP address and routing table.
* **Unified Perspective**: Reports telemetry (latency, connectivity, availability) exactly as the target service experiences it.
* **Logical Decoupling**: Separates monitoring concerns from application logic, allowing for independent updates and service agnosticism.

## Self-Discovery Mechanism

The agent performs dynamic service discovery to identify its "Parent" container without manual hardcoding of network parameters in the compose file.

### Discovery Workflow
1. **Identity Lookup**: The agent queries the Docker Engine API (via the mounted socket) using the MY_CONTAINER_NAME environment variable to find its own container object.
2. **Stack Inspection**: It inspects its own HostConfig.NetworkMode attribute to resolve the ID of the shared network stack (the "Target" service).
3. **Coordinate Extraction**: The agent retrieves the Target service object to extract real-time network metadata, including internal IP addresses and exposed port mappings.

## Deployment and Configuration

To function correctly, the agent must be granted read-only access to the Docker daemon and be explicitly attached to a target service's network stack.

### Docker Compose Example

```yaml
services:
  # The primary service to be monitored
  nginx-service:
    image: nginx:alpine
    restart: always

  # The monitoring service
  agent-nginx:
    build: ./agent
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro # Mandatory.
    depends_on:
      - nginx-service
    network_mode: "service:nginx-service" # Attach to the target network stack
    container_name: agent-nginx-1          # Must be unique across the infrastructure
    environment:
      - MY_CONTAINER_NAME=agent-nginx-1    # Used by the agent for self-lookup, must match container name