# Guia do Projeto: RS Docker Monitor 🚀

Este documento serve como um guia completo para entender o funcionamento do projeto, focado nos conceitos de **Redes e Serviços**. Foi desenhado para que qualquer membro da equipa consiga apresentar o projeto com confiança, explicando desde a arquitetura até aos protocolos de comunicação.

---

## 1. Visão Geral do Projeto
O **RS Docker Monitor** é um sistema de monitorização distribuído que recolhe métricas de saúde e rede de containers Docker em tempo real. Utiliza uma arquitetura de microserviços e o padrão **Sidecar** para garantir que a monitorização é não-intrusiva.

### Objetivos Principais:
- Monitorizar a disponibilidade (Uptime) de serviços.
- Medir a latência de rede (RTT) entre o serviço e o monitor.
- Descobrir dinamicamente a infraestrutura sem configuração manual de IPs.
- Visualizar tudo num Dashboard centralizado no terminal.

---

## 2. Arquitetura: O Padrão Sidecar 🏎️
Em vez de instalar software de monitorização dentro do container da aplicação (ex: Nginx), criamos um container auxiliar — o **Agente** — que corre "ao lado" do alvo.

- **Shared Network Stack:** O Agente usa `network_mode: "service:nome-do-alvo"`. Isto significa que o Agente e o Alvo partilham o **mesmo endereço IP** e a mesma tabela de encaminhamento.
- **Vantagem:** O Agente vê a rede exatamente como a aplicação a vê. Se houver um problema de rede no container, o Agente reportará com precisão.

---

## 3. Comunicação e Protocolos (A "matéria" de Redes) 🌐
Este é o ponto mais importante para a disciplina de Redes e Serviços. O projeto utiliza três protocolos principais:

### A. MQTT (Message Queuing Telemetry Transport) - Camada de Aplicação
O MQTT é o coração da comunicação. Funciona num modelo **Publish/Subscribe**.
- **Broker (Mosquitto):** O hub central. Recebe mensagens e distribui para quem estiver interessado.
- **Tópicos:** Organizados de forma hierárquica: `monitor/services/<id>/<tipo>`.
- **Retain Flag:** Usada no tópico de metadados (`/meta`). O Broker guarda a última mensagem para que, se o Monitor ligar mais tarde, receba imediatamente os dados dos agentes já ativos.
- **Last Will and Testament (LWT):** Se um Agente perder a ligação abruptamente (crash), o Broker publica automaticamente a mensagem `CRASHED` no tópico de status. Isto garante fiabilidade na monitorização.

### B. UDP (User Datagram Protocol) - Descoberta de Serviços
Para evitar "hardcoding" do IP do Broker, implementámos um mecanismo de **Service Discovery** via UDP Broadcast.
1. O **Monitor** grita na rede (Porta 9999): *"O MQTT Broker está aqui: [MEU_IP]"*.
2. O **Agente**, ao iniciar, fica à escuta de pacotes UDP na porta 9999.
3. Assim que recebe o pacote, extrai o IP e liga-se ao Broker via TCP.
*Conceito:* Protocolo sem ligação (Connectionless), rápido e ideal para descoberta inicial.

### C. TCP (Transmission Control Protocol) - Fiabilidade e RTT
- O MQTT corre sobre TCP (porta 1883), garantindo que os dados chegam sem erros.
- **Cálculo de RTT:** O Agente simula um "ping" abrindo brevemente uma socket TCP para o IP do Broker e medindo o tempo de resposta em milissegundos.

---

## 4. Decisões de Design (O "Porquê" das Escolhas) 🧠

Durante o desenvolvimento, foram feitas escolhas técnicas específicas para maximizar a eficiência e a robustez do sistema. Abaixo estão as justificativas para as principais decisões:

### A. RTT medido no Agente (e não no Monitor)
**Escolha:** O cálculo da latência é feito pelo Agente enviando um pedido ao Broker.
**Justificativa:** 
1. **Ponto de Vista do Serviço:** Como o Agente partilha a stack de rede do container alvo, o RTT medido reflete exatamente a latência que o serviço (ex: Nginx) está a experienciar para chegar à infraestrutura central.
2. **Redução de Carga no Monitor:** Se o Monitor tivesse de fazer ping/check a 100 agentes, ele tornar-se-ia um gargalo (bottleneck). Ao distribuir essa tarefa pelos agentes (Edge Computing), o sistema escala muito melhor.

### B. Porquê o Padrão Sidecar?
**Escolha:** Um container separado para o Agente em vez de instalar o script no container da App.
**Justificativa:**
1. **Agnosticismo de Tecnologia:** Podemos monitorizar uma App em Java, Python ou Go sem alterar uma única linha de código dessa App.
2. **Ciclo de Vida Independente:** Se o Agente precisar de uma atualização ou crashar, o serviço principal (Nginx) continua a funcionar sem interrupções.
3. **Segurança:** O serviço principal não precisa de privilégios para falar com o Docker API; apenas o Agente (que é isolado) tem essa responsabilidade.

### C. UDP Broadcast vs. IP Estático
**Escolha:** Usar um "grito" UDP para achar o Broker em vez de escrever o IP nos ficheiros de configuração.
**Justificativa:**
1. **Plug-and-Play:** Em redes dinâmicas (como Wi-Fi ou ambientes Cloud), os IPs mudam. O UDP permite que o Agente seja movido para qualquer máquina e "ache" o Monitor automaticamente.
2. **Conceito de Redes:** Demonstra o uso prático de protocolos connectionless para descoberta de serviços (similar ao funcionamento do DHCP ou SSDP).

### D. MQTT vs. Outros Protocolos
**Escolha:** Protocolo de mensagens Pub/Sub (Requisito do Projeto).
**Justificativa:** 
Além de ser uma especificação obrigatória do trabalho, o MQTT provou ser a escolha ideal por:
1. **Estado em Tempo Real:** Mantém uma ligação persistente, permitindo atualizações instantâneas.
2. **Eficiência (Low Overhead):** O cabeçalho do MQTT tem apenas 2 bytes, poupando largura de banda em comparação com HTTP.
3. **Escalabilidade:** O modelo Pub/Sub permite que o sistema cresça sem que o Agente precise de conhecer os detalhes dos Monitores.

---

## 5. Componentes do Sistema

### 🛠️ O Agente (agent.py)
1. **Descoberta:** Ouve o broadcast UDP para achar o Broker.
2. **Auto-Inspeção:** Comunica com o `/var/run/docker.sock` para saber quem é o seu "pai" (o container que está a monitorizar) e recolher IPs e portas.
3. **Loop de Saúde:** A cada 5 segundos, verifica se o alvo está vivo, mede o RTT e publica no MQTT.

### 🖥️ O Monitor/Dashboard (monitor.py)
1. **Interface:** Usa a biblioteca `rich` para criar tabelas e painéis no terminal.
2. **Estado:** Mantém um dicionário interno com o estado de todos os containers conhecidos.
3. **Evento de Broadcast:** Gere a thread que anuncia a localização do Broker.

### 🔌 O Broker (Mosquitto)
- Configurado para permitir persistência de dados e logs.

---

## 5. Como Executar o Projeto 🚀
Para que o sistema funcione corretamente, siga estes passos:

1. **Broker e Monitor:** No diretório raiz, execute:
   ```bash
   docker-compose -f src/docker_composes/dockercompose.local.yaml up --build
   ```
   *Nota: O Monitor e o Broker correm em `network_mode: host` para facilitar o broadcast UDP na rede local.*

2. **Visualização:** O Dashboard aparecerá automaticamente no terminal onde correu o comando acima.

---

## 6. Fluxo de Trabalho (O que acontece "por baixo do capô")
1. O **Monitor** começa a emitir UDP Broadcasts.
2. O **Nginx** (ou outro serviço alvo) sobe.
3. O **Agente** sobe, ouve o UDP, descobre o IP do Monitor e liga-se ao Broker.
4. O **Agente** pergunta à Docker API: *"Quais são os detalhes do Nginx?"*.
5. O **Agente** publica os metadados no MQTT com a flag `Retain`.
6. O **Monitor** recebe, adiciona à tabela e começa a monitorizar a saúde e o RTT.

---

## 7. FAQ para a Apresentação (Possíveis perguntas do Professor) ❓

**Q: Porque usaram MQTT em vez de HTTP?**
*R:* O MQTT é mais leve (overhead de cabeçalho menor), ideal para sensores/agentes, e o modelo Pub/Sub permite que múltiplos monitores recebam dados sem que o agente tenha de enviar várias vezes a mesma info.

**Q: O que acontece se o Agente for abaixo de repente?**
*R:* Graças ao "Last Will and Testament" configurado no momento da ligação, o Broker detecta a queda da socket TCP e avisa o Monitor que o estado é `CRASHED`.

**Q: Porque é que o Agente precisa de acesso ao socket do Docker?**
*R:* Para poder interagir com a API do Docker Engine local e obter informações em tempo real sobre o container que está a monitorizar (ID, Portas expostas, etc.).

**Q: Qual a diferença entre o RTT medido e um comando Ping (ICMP)?**
*R:* O nosso RTT é medido na camada de transporte (TCP). É mais realista para aplicações web, pois testa se a stack TCP está a responder, não apenas se a interface de rede (ICMP) está ativa.

**Q: Como lidam com múltiplos containers?**
*R:* Cada Agente gera um Client ID único baseado no ID do container. No Monitor, usamos wildcards (`#`) na subscrição do MQTT para ouvir todos os serviços automaticamente.

---

## 8. Resumo da Stack de Redes (Cheat Sheet para Prova Oral) 📝

| Camada (OSI) | Protocolo | Função no Projeto |
| :--- | :--- | :--- |
| **Aplicação** | MQTT | Transporte de telemetria e eventos (Pub/Sub). |
| **Aplicação** | JSON | Formato de serialização dos dados. |
| **Transporte** | TCP | Canal fiável para MQTT e medição de RTT. |
| **Transporte** | UDP | Descoberta dinâmica de serviços (Broadcast). |
| **Rede** | IP | Endereçamento dos containers e hosts. |
| **Acesso à Rede** | Ethernet/Docker Bridge | Enlace de dados entre os containers. |

---
*Este guia foi gerado para auxiliar a equipa. Bons estudos e boa apresentação!* 🚀
