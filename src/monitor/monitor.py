import paho.mqtt.client as mqtt
import json
import time
import socket
import os
import threading

estado_rede = {}

# Configurações do Broker MQTT
BROKER_IP = "localhost"
BROKER_PORT = 1883
TOPIC_SUBSCRIBE = "infra/nodes/#"


# 2. Funções de Callback do MQTT
def on_connect(client, userdata, flags, rc):
    # rc == 0 significa ligação com sucesso
    if rc == 0:
        client.subscribe(TOPIC_SUBSCRIBE)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        container_id = msg.topic.split('/')[-1]

        if container_id not in estado_rede:
            estado_rede[container_id] = {"ip": "N/A", "port": 0, "status": "UNKNOWN", "rtt": "N/A"}

        if "ip" in payload:
            estado_rede[container_id]["ip"] = payload["ip"]
        if "port" in payload:
            estado_rede[container_id]["port"] = payload["port"]
        if "status" in payload:
            estado_rede[container_id]["status"] = payload["status"]

    except json.JSONDecodeError:
        pass

def medir_rtt():
    while True:
        for container_id, dados in estado_rede.items():
            if dados["status"] == "UP" and dados["ip"] != "N/A":
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
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    # Liga ao broker (Corre em background)
    client.connect(BROKER_IP, BROKER_PORT, 60)
    client.loop_start() 

    # Inicia a Thread que mede o RTT em background
    rtt_thread = threading.Thread(target=medir_rtt, daemon=True)
    rtt_thread.start()

    # Inicia a interface visual no terminal (bloqueia o script principal aqui)
    try:
        imprimir_dashboard()
    except KeyboardInterrupt:
        print("\nA encerrar o monitor...")
        client.loop_stop()
        client.disconnect()
