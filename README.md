# 🐳 RS Docker Monitor

[![Project Status](https://img.shields.io/badge/Project-Academic-blue.svg)](https://github.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue.svg)](https://www.docker.com/)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-orange.svg)](https://mosquitto.org/)

A real-time, non-intrusive Docker monitoring system built for the **Networks and Services (RS)** class. It leverages the **Sidecar Pattern** and **MQTT** to provide a centralized dashboard for service health and network metrics.

---

## 🛠️ Architecture & Networking Concepts

This project is a practical application of several fundamental networking and distributed systems concepts:

### 🏎️ The Sidecar Pattern
The monitoring agent is implemented as a **Universal Sidecar**. This architectural choice ensures that monitoring is completely decoupled from the application logic.
* **Shared Network Stack**: Using Docker's `network_mode`, the agent shares the identical Network Namespace, IP address, and routing table as the target service.
* **Transparent Monitoring**: It observes network conditions (like RTT) exactly as the target service experiences them.

### 📡 Communication Stack
- **MQTT (TCP/1883)**: The backbone of the telemetry system. Uses a **Publish/Subscribe** model for high scalability and real-time updates.
- **UDP Discovery (Port 9999)**: Zero-config setup. The Monitor broadcasts its location via UDP, allowing Agents to find the MQTT Broker dynamically without hardcoded IPs.
- **TCP Health Checks**: The Agent measures **Round-Trip Time (RTT)** by establishing lightweight TCP connections to the monitoring hub.

---

## 🔍 Self-Discovery Metadata Mechanism

The Agent autonomously identifies its "Parent" container via the Docker Engine API:
1. **Identity Lookup**: Queries the Docker API using the `MY_CONTAINER_NAME` env variable.
2. **Stack Inspection**: Resolves the shared network stack ID from its own `HostConfig.NetworkMode`.
3. **Metadata Extraction**: Retrieves real-time network metadata (Internal IP, Port mappings) from the Target service.

---

## 🚀 Quick Start

### 1. Prerequisites
- Docker & Docker Compose installed.

### 2. Launch the Infrastructure
To start the MQTT Broker, the Dashboard, and a sample Nginx service with its Agent:

```bash
docker-compose -f src/docker_composes/dockercompose.local.yaml up --build
```

### 3. Dashboard
Once the containers are up, the **Rich Terminal Dashboard** will launch automatically, displaying:
- **Service ID & Name**: Auto-discovered metadata.
- **State**: Real-time status (UP, DOWN, CRASHED).
- **RTT**: Network latency in milliseconds.
- **Uptime**: Tracking how long the service has been running.

---

## 📊 MQTT Topic Hierarchy

The system uses a structured topic hierarchy for granular monitoring and efficient wildcard filtering:

| Topic Structure | Payload Description | QOS |
| :--- | :--- | :--- |
| `monitor/services/<id>/meta` | **Static Metadata**: IP, Ports, Service Name. | 1 (Retained) |
| `monitor/services/<id>/health` | **Heartbeat**: Timestamp and RTT metrics. | 0 |
| `monitor/services/<id>/status` | **Lifecycle**: Reports `SHUTDOWN` or `CRASHED` (LWT). | 1 (Retained) |

---

## 📁 Project Structure

```text
├── src/
│   ├── agent/       # Sidecar Agent (Python + Docker API)
│   ├── monitor/     # Terminal Dashboard & UDP Broadcaster
│   ├── mosquitto/   # MQTT Broker configuration
│   └── docker_composes/ # Deployment manifests
├── docs/            # Documentation & Test plans
└── Guia.md          # Comprehensive Project Guide (Presentation focus)
```

---

## 🎓 Academic Context
Developed for the **Redes e Serviços** course. 
Focus: Network Protocols (TCP/UDP/MQTT), Containerization, and Distributed Monitoring.

---
*Developed by:*
- Marcos Costa 125882
- Keegan Azevedo ???
- Jamilly Vitorya 135849
