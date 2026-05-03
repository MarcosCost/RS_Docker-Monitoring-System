# RS Docker Monitor
Real-time Docker monitoring via MQTT. Academic project for the Networks and Services (RS) class.

## Agent

### Sidecar Pattern

The monitoring agent is designed as a Universal Sidecar. This means that no extra configuration is needed in the monitored services/containers. Instead the agent attaches itself to the target's network stack using Docker's network_mode.

By using network_mode, the agent:
- Shares the same IP address as the target service
- Operates within the same Network Namespace, allowing it to report telemetry that is identical to the target's perspective.
- Decouples monitoring logic from application logic

### Self-Discovery Mechanism
The agent has the ability to identify its "Parent" service and extract network coordinates dynamically.

Discovery Workflow:
    
    1 - The agent uses the MY_CONTAINER_NAME environment variable to find its own object in the Docker Engine
    2 - Identifies the main service's ID from the HostConfig.NetworkMode attribute.
    3 - Finds the main service's object in the Docker Engine and uses it to retrieve the proper network Coordinates

### Docker
To work properlly the agent needs to be correctly attatched to a service. Bellow follows an example:
```Yaml
services:

  nginx-service:
    image: nginx:alpine
      ...

  agent-nginx:
    build: ./agent
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    depends_on:
      - nginx-service
    network_mode: "service:nginx-service" # Must match the service this is depending on
    container_name: agent-nginx-1  # Must match the container name in the environment variable, cannot have duplicate names in the docker compose file
    environment:
      - MY_CONTAINER_NAME=agent-nginx-1


```
