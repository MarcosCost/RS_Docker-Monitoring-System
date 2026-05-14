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
            estado_rede[container_id] = {"ip": "N/A", "port": 0, "status": "UNKNOWN", "rtt": "N/A"}

        if msg_type == "meta":
            payload = json.loads(msg.payload.decode('utf-8'))
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

# TODO: rtt n pode ser medido no monitor, n da pra explicar aqui qualquer coisa mandem me msg q eu explico
def medir_rtt():
    while True:
        for container_id, dados in estado_rede.items():
            if dados["status"] == "UP" and dados["ip"] != "N/A" and dados["port"] != 0:
                try:
                    inicio = time.time()
                    s = socket.create_connection((dados["ip"], dados["port"]), timeout=1)
                    s.close()
                    fim = time.time()
                    rtt_ms = round((fim - inicio) * 1000, 2)
                    estado_rede[container_id]["rtt"] = f"{rtt_ms} ms"

                except (socket.timeout, ConnectionRefusedError, OSError):
                    estado_rede[container_id]["rtt"] = "Falha TCP"
        time.sleep(2)

def imprimir_dashboard():
    while True:

        os.system('cls' if os.name == 'nt' else 'clear')

        print("="*65)
        print(f"MAPA DE SAÚDE DA INFRAESTRUTURA DOCKER - {time.strftime('%H:%M:%S')}")
        print("="*65)
        print(f"{'CONTAINER ID':<15} | {'IP':<15} | {'PORTA':<6} | {'STATUS':<6} | {'RTT'}")
        print("-" * 65)

        if not estado_rede:
            print("A aguardar dados dos agentes...")
        else:
            for container_id, dados in estado_rede.items():
                print(f"{container_id:<15} | {dados['ip']:<15} | {dados['port']:<6} | {dados['status']:<6} | {dados['rtt']}")

        print("="*65)
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
