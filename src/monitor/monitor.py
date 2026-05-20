import paho.mqtt.client as mqtt  # type: ignore
import json
import time
import socket
import re
from threading import Thread

from rich.console import Group # type: ignore
from rich.live import Live # type: ignore
from rich.panel import Panel # type: ignore
from rich.table import Table # type: ignore

estado_rede = {}
eventos = []

HEARTBEAT_TIMEOUT = 12
MAX_EVENTS = 6

BROKER_IP = "127.0.0.1" # Both Monitor and broker are running in "network_mode: host" so they share localhost
BROKER_PORT = 1883
TOPIC_SUBSCRIBE = "monitor/services/#"

def add_event(message):
    timestamp = time.strftime("%H:%M:%S")
    eventos.append(f"{timestamp} {message}")
    if len(eventos) > MAX_EVENTS:
        eventos.pop(0)

# 1. Função da thread q publica o seu Ip na rede a cada 5s
def publish_ip():

    # Get machine's public Ip
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        machine_ip = s.getsockname()[0]
    except Exception:
        machine_ip = "127.0.0.1"
    finally:
        s.close()

    BROADCAST_PORT = 9999
    MESSAGE = f"MQTT_BROKER_HERE:{machine_ip}".encode()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    try:
        while True:
            # 255.255.255.255 is to broadcast to the network
            sock.sendto(MESSAGE, ('255.255.255.255', BROADCAST_PORT))
            time.sleep(5)
    except KeyboardInterrupt:
        print('\nKeyboard Shutdown, Stopping the Ip shouting!')
    finally:
        sock.close()

# 2. Funções de Callback do MQTT
def on_connect(client, userdata, flags, reason_code, properties):
    # reason_code == 0 significa ligação com sucesso
    if reason_code == 0:
        client.subscribe(TOPIC_SUBSCRIBE)

def on_message(client, userdata, msg):
    try:
        parts = msg.topic.split('/')
        if len(parts) < 4:
            return
        
        container_id = parts[2]
        msg_type = parts[3]

        if container_id not in estado_rede:
            estado_rede[container_id] = {
                "name": "N/A",
                "ip": "N/A",
                "port": 0,
                "status": "UNKNOWN",
                "rtt": "N/A",
                "last_seen": None,
                "registered_at": None,
            }

        if msg_type == "meta":
            payload = json.loads(msg.payload.decode('utf-8'))
            estado_rede[container_id]["name"] = payload.get("Parent_name", "N/A")
            estado_rede[container_id]["ip"] = payload.get("Ip", "N/A")

            ports = payload.get("Ports", [])
            estado_rede[container_id]["port"] = extrair_porta_tcp(ports)

            if estado_rede[container_id]["registered_at"] is None:
                estado_rede[container_id]["registered_at"] = time.time()

            add_event(f"{container_id[:12]} REGISTERED")

        elif msg_type in {"health", "healthcheck", "heartbeat"}:
            try:
                payload = json.loads(msg.payload.decode('utf-8'))
                # Use the RTT provided by the agent in the payload
                rtt_val = payload.get("rtt") or payload.get("RTT")
                if rtt_val:
                    estado_rede[container_id]["rtt"] = f"{rtt_val} ms"
            except json.JSONDecodeError:
                pass

            previous_status = estado_rede[container_id]["status"]
            estado_rede[container_id]["last_seen"] = time.time()
            estado_rede[container_id]["status"] = "UP"

            if estado_rede[container_id]["registered_at"] is None:
                estado_rede[container_id]["registered_at"] = time.time()

            if previous_status == "DOWN":
                add_event(f"{container_id[:12]} RECOVERED")

        elif msg_type == "status":
            status = msg.payload.decode('utf-8').strip().upper()
            old_status = estado_rede[container_id]["status"]
            estado_rede[container_id]["status"] = status

            if old_status != status:
                add_event(f"{container_id[:12]} {status}")

    except Exception as e:
        # print(f"Error processing message: {e}")
        pass

def extrair_porta_tcp(ports):
    if not isinstance(ports, list):
        return None

    for entry in ports:
        numbers = re.findall(r'\d+', entry)
        
        if len(numbers) == 2:
            host_port, container_port = numbers            
            if host_port == "9999" or container_port == "9999":
                continue
                
            return f"{host_port} -> {container_port}"

    return None

def verificar_timeouts():
    while True:
        now = time.time()

        for container_id, dados in estado_rede.items():
            last_seen = dados.get("last_seen")

            if last_seen is not None:
                age = now - last_seen
                if age > HEARTBEAT_TIMEOUT and dados["status"] == "UP":
                    dados["status"] = "DOWN"
                    add_event(f"{container_id[:12]} DOWN (heartbeat timeout)")

        time.sleep(1)
        
def format_last_seen(timestamp_value):
    if timestamp_value is None:
        return "--"
    return time.strftime("%H:%M:%S", time.localtime(timestamp_value))


def build_services_table():
    table = Table(title="Docker Health Monitor", expand=True)
    
    table.add_column("Service ID", style="cyan", overflow="fold", max_width=24)
    table.add_column("Name", overflow="fold", max_width=18)
    table.add_column("IP", style="magenta", no_wrap=True)
    table.add_column("Port", justify="right", no_wrap=True)
    table.add_column("State", justify="center", no_wrap=True)
    table.add_column("RTT", justify="right", no_wrap=True)
    table.add_column("Last Seen", justify="center", no_wrap=True)
    table.add_column("HB Age (s)", justify="right", no_wrap=True)
    table.add_column("Uptime (s)", justify="right", no_wrap=True)

    if not estado_rede:
        table.add_row("-", "A aguardar dados dos agentes...", "-", "-", "-", "-", "-", "-", "-")
        return table

    now = time.time()

    for container_id, dados in estado_rede.items():
        state = dados.get("status", "UNKNOWN")

        if state == "UP":
            state_text = "[green]UP[/green]"
        elif state == "DOWN":
            state_text = "[red]DOWN[/red]"
        elif state == "CRASHED":
            state_text = "[bold red]CRASHED[/bold red]"
        else:
            state_text = "[yellow]UNKNOWN[/yellow]"

        last_seen = dados.get("last_seen")
        hb_age = "--" if last_seen is None else f"{now - last_seen:.1f}"

        registered_at = dados.get("registered_at")
        uptime = "--" if registered_at is None else str(int(now - registered_at))

        table.add_row(
            container_id,
            str(dados.get("name", "")),
            str(dados.get("ip", "")),
            str(dados.get("port", "")),
            state_text,
            str(dados.get("rtt", "N/A")),
            format_last_seen(last_seen),
            hb_age,
            uptime,
        )

    return table


def build_events_panel():
    content = "No recent events" if not eventos else "\n".join(eventos[-MAX_EVENTS:])
    return Panel(content, title="Recent Events", border_style="blue")


def build_header():
    text = (
        f"Broker: mqtt://{BROKER_IP}:{BROKER_PORT} | "
        f"Topic: {TOPIC_SUBSCRIBE} | "
        f"Timeout: {HEARTBEAT_TIMEOUT}s"
    )
    return Panel(text, title="System Info", border_style="green")


def build_dashboard():
    return Group(
        build_header(),
        build_services_table(),
        build_events_panel(),
    )


def run_dashboard():
    with Live(build_dashboard(), refresh_per_second=2, screen=True) as live:
        while True:
            live.update(build_dashboard())
            time.sleep(1)

if __name__ == "__main__":
    # Configura o cliente MQTT
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="Monitor")
    client.on_connect = on_connect
    client.on_message = on_message

    # Liga ao broker (Corre em background)
    client.connect(BROKER_IP, BROKER_PORT, 60)
    client.loop_start() 

    # Thread the grita o seu Ip pro void
    thread = Thread(target=publish_ip, daemon=True)
    thread.start()

    timeout_thread = Thread(target=verificar_timeouts, daemon=True)
    timeout_thread.start()

    # Inicia a interface visual no terminal (bloqueia o script principal aqui)
    try:
        run_dashboard()
    except KeyboardInterrupt:
        print("\nA encerrar o monitor...")
    finally:
        client.loop_stop()
        client.disconnect()
