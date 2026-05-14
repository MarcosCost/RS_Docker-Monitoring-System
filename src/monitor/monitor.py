import paho.mqtt.client as mqtt  # type: ignore
import json
import time
import socket
import os
from threading import Thread

estado_rede = {}

BROKER_IP = "127.0.0.1" # Both Monitor and broker are running in "network_mode: host" so they share localhost
BROKER_PORT = 1883
TOPIC_SUBSCRIBE = "monitor/services/#"

# 1. Função da thread q publica o seu Ip na rede a cada 5s
def publish_ip():
    BROADCAST_PORT = 9999
    MESSAGE = b"MQTT_BROKER_HERE"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    try:
        while True:
            # 255.255.255.255 is to broadcast to the network
            sock.sendto(MESSAGE, ('255.255.255.255', BROADCAST_PORT))
            time.sleep(5)
    except KeyboardInterrupt:
        print('\nKeyboard Shutdown, Stopping the Ip shouting!')

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
            estado_rede[container_id] = {"name": "N/A", "ip": "N/A", "port": 0, "status": "UNKNOWN", "rtt": "N/A"}

        if msg_type == "meta":
            payload = json.loads(msg.payload.decode('utf-8'))
            estado_rede[container_id]["name"] = payload.get("Parent_name", "N/A")
            estado_rede[container_id]["ip"] = payload.get("Ip", "N/A")
            # Extracting first port number from ports list string like "Host 9999 -> Container 9999/udp"
            ports = payload.get("Ports", [])
            if ports:
                try:
                    # Very simple parsing for the port number
                    port_str = ports[0].split('-> Container ')[1].split('/')[0]
                    estado_rede[container_id]["port"] = int(port_str)
                except (IndexError, ValueError):
                    pass
            estado_rede[container_id]["status"] = "UP"

        elif msg_type == "status":
            status = msg.payload.decode('utf-8')
            estado_rede[container_id]["status"] = status

    except Exception as e:
        # print(f"Error processing message: {e}")
        pass

def imprimir_dashboard():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')

        # Define headers and their initial minimum widths
        headers = {
            "ID": "ID",
            "NAME": "PARENT NAME",
            "IP": "IP",
            "PORTA": "PORTA",
            "STATUS": "STATUS",
            "RTT": "RTT"
        }
        
        # Calculate dynamic widths
        col_widths = {k: len(v) for k, v in headers.items()}
        
        for container_id, dados in estado_rede.items():
            short_id = container_id[:12]
            col_widths["ID"] = max(col_widths["ID"], len(short_id))
            col_widths["NAME"] = max(col_widths["NAME"], len(str(dados.get("name", ""))))
            col_widths["IP"] = max(col_widths["IP"], len(str(dados.get("ip", ""))))
            col_widths["PORTA"] = max(col_widths["PORTA"], len(str(dados.get("port", ""))))
            col_widths["STATUS"] = max(col_widths["STATUS"], len(str(dados.get("status", ""))))
            col_widths["RTT"] = max(col_widths["RTT"], len(str(dados.get("rtt", ""))))

        # Total width for separators
        total_width = sum(col_widths.values()) + (len(col_widths) * 3) - 1

        print("=" * total_width)
        print(f"MAPA DE SAÚDE DA INFRAESTRUTURA DOCKER - {time.strftime('%H:%M:%S')}")
        print("=" * total_width)
        
        # Print Header
        header_row = " | ".join([f"{headers[k]:<{col_widths[k]}}" for k in headers])
        print(header_row)
        print("-" * total_width)

        if not estado_rede:
            print("A aguardar dados dos agentes...")
        else:
            for container_id, dados in estado_rede.items():
                short_id = container_id[:12]
                row = [
                    f"{short_id:<{col_widths['ID']}}",
                    f"{str(dados.get('name', '')):<{col_widths['NAME']}}",
                    f"{str(dados.get('ip', '')):<{col_widths['IP']}}",
                    f"{str(dados.get('port', '')):<{col_widths['PORTA']}}",
                    f"{str(dados.get('status', '')):<{col_widths['STATUS']}}",
                    f"{str(dados.get('rtt', '')):<{col_widths['RTT']}}"
                ]
                print(" | ".join(row))

        print("=" * total_width)
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
    thread = Thread(target = publish_ip)
    thread.start()

    # Inicia a interface visual no terminal (bloqueia o script principal aqui)
    try:
        imprimir_dashboard()
    except KeyboardInterrupt:
        print("\nA encerrar o monitor...")
        client.loop_stop()
        client.disconnect()
        thread.join()
