# Definição da Solução – Monitor de Serviços

## 1. Dashboard

A biblioteca escolhida foi o `rich`, que permite criar dashboards directamente no terminal com actualização em tempo real — é simples de usar e o resultado visual é bastante decente para o que precisamos.

O dashboard está dividido em três partes principais: um cabeçalho com informação geral, uma tabela com uma linha por serviço, e um painel de eventos recentes.

A tabela mostra as seguintes colunas: `service_id`, `name`, `ip`, `port`, `state`, `rtt_ms`, `last_seen`, `heartbeat_age_s` e `uptime_s`. Cada serviço pode estar num de três estados:

- `UNKNOWN` — o serviço já foi registado, mas ainda não chegou heartbeat suficiente para confirmar o estado
- `UP` — está a enviar heartbeats dentro do tempo esperado
- `DOWN` — o heartbeat expirou, o serviço provavelmente caiu

No painel de eventos aparecem coisas como `REGISTERED`, `DOWN` e `RECOVERED`, e opcionalmente `RTT_HIGH` se a latência estiver alta. Visualmente, o `UP` aparece a verde, o `DOWN` a vermelho, e o `UNKNOWN` a amarelo, o que torna fácil perceber o estado geral de relance.

---

## 2. Contrato MQTT + JSON

A comunicação é feita via MQTT com mensagens em JSON. Os tópicos usados são:

- `monitor/services/<ID>/meta` — para registo de serviços
- `monitor/services/<ID>/health` — para os heartbeats periódicos
- `monitor/services/<ID>/status` — Status do container (Up Down Crashed)


Algumas regras gerais: os timestamps estão todos em ISO 8601 UTC, o `service_id` é uma string única por serviço, o `port` é inteiro e o `ip` é string.

### Mensagem de registo

Publicada no tópico `monitor/services/<ID>/meta`:

```json
{
  "Parent_id": "an id",
  "Parent_name": "name",
  "Ip":"ip_addr",
  "Ports":"list(ports)",
  "registered_at": "2026-04-02T14:30:00Z"
}
```

### Mensagem de heartbeat

Publicada no tópico `monitor/services/<ID>/healthcheck`:

```json
{
  "timestamp":"time"
}
```

### Mensagem de Status (opcional)

Gerada pelo monitor e publicada em `monitor/services/<ID>/status`:

String:
"UP", "DOWN", "CRASHED"

---

## 3. Como funciona o monitor

Quando chega uma mensagem de `register`, o monitor cria uma entrada no registry com o `service_id`, `name`, `ip`, `port` e `registered_at`. O estado inicial é `UNKNOWN`.

Quando chega um `heartbeat`, o monitor actualiza o `last_seen`. Se o serviço estava `DOWN`, gera automaticamente um evento `RECOVERED` e passa o estado para `UP`.

Se passar mais tempo do que o timeout desde o último heartbeat, o serviço é marcado como `DOWN` e é gerado um evento `DOWN`.

O RTT é calculado pelo próprio monitor — não é o agente que o mede. O monitor tenta ligar por TCP ao `ip:port` do serviço, mede o tempo que demora, e guarda esse valor em `rtt_ms`.

---

## 4. Configuração base

Os valores usados como ponto de partida são:

- `heartbeat_interval = 5s`
- `timeout = 12s`
- `rtt_check_interval = 5s`

---

## 5. Testes

### T1 – Registo inicial

Verificar se o serviço publica as suas coordenadas ao arrancar. Arranca-se o `service_a` e espera-se que apareça no monitor com `service_id`, `ip`, `port` e estado `UNKNOWN` ou `UP`.

### T2 – Heartbeat contínuo

Deixar o serviço activo durante 30 segundos e confirmar que o `last_seen` vai actualizando e o estado se mantém `UP`.

### T3 – Detecção de falha

Parar o container e verificar que, após o timeout, o estado muda para `DOWN`.

### T4 – Recuperação

Voltar a arrancar o container e confirmar que o serviço regressa a `UP` com um evento `RECOVERED`.

### T5 – RTT

Com os serviços activos e o RTT checker a correr, verificar que o campo `rtt_ms` aparece preenchido para serviços em `UP`.

### T6 – Vários serviços em simultâneo

Arrancar `service_a`, `service_b` e `service_c` ao mesmo tempo e confirmar que a tabela mostra todos sem conflitos.

### T7 – Comparação de configurações

Testar três combinações diferentes de heartbeat e timeout para perceber o equilíbrio entre rapidez de detecção e falsos alarmes:

- `heartbeat 2s / timeout 5s`
- `heartbeat 5s / timeout 12s`
- `heartbeat 10s / timeout 20s`

### T8 – Broker indisponível

Desligar o broker temporariamente. O sistema deixa de receber mensagens — o que mostra claramente que o broker é um ponto central de falha. É uma limitação conhecida desta abordagem.

---

## 6. Resumo da solução

O que ficou definido:

- Dashboard em terminal com `rich`, com tabela principal e painel de eventos
- Métricas visíveis: `state`, `rtt_ms`, `last_seen`, `heartbeat_age_s`, `ip`, `port`, `service_id`
- Contrato MQTT/JSON com três tipos de mensagem: `register`, `heartbeat` e `event`
- Plano de testes já estruturado para cobrir os cenários principais
