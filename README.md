# 🛡️ Jarvis SPB — Agente Forense Bancário (v3.1)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-orange?style=for-the-badge)
![Textual](https://img.shields.io/badge/Interface-TUI-green?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-Containerized-blue?style=for-the-badge&logo=docker)

> **Sistema Autônomo de Observabilidade e Forense Bancária** voltado para ambientes SPB/PIX, capaz de diagnosticar falhas transacionais, calcular SLA em tempo real e converter linguagem natural em SQL complexo de forma segura.

---

## 📌 Visão Geral

O **Jarvis SPB** não é um simples chatbot, mas sim uma **ferramenta de engenharia forense** projetada para ambientes bancários de missão crítica.  
Seu objetivo é reduzir drasticamente o tempo de investigação de incidentes, eliminando análise manual de logs XML, consultas repetitivas e fadiga operacional.

O sistema atua de forma **autônoma**, interpretando perguntas técnicas ou identificadores de transações (NUOP), investigando múltiplas tabelas, analisando mensagens ISO 20022 e entregando relatórios técnicos claros e auditáveis.

---

## 🚀 Principais Funcionalidades

### 🧠 Orquestração Inteligente com LangGraph
- Arquitetura baseada em **StateGraph**
- Fluxos determinísticos com loops de **auto-correção**
- Reexecução automática de SQL em caso de erro de sintaxe

### ⚡ Investigação Forense Automatizada
- Rastreamento de transações SPB/PIX via NUOP
- Cruzamento entre tabelas **real-time** e **legado**
- Consolidação de dados via CTEs

### 🧾 Parser XML ISO 20022
- Extração precisa com `lxml`
- Tratamento robusto de *Namespaces*
- Identificação de causas-raiz (`<RsnDesc>`, códigos e descrições)

### ⏱️ Cálculo de SLA Determinístico
- Cálculo preciso de latência (`ts_consumo - ts_entrega`)
- Alertas automáticos para violações (>10s)
- Independente de funções do banco

### 🖥️ Interface TUI + Feedback por Voz
- Interface de terminal desenvolvida com **Textual**
- Operação em servidores *headless*
- Alertas críticos com **pyttsx3**

---

## 🧩 Arquitetura do Sistema

O Jarvis opera através de um **grafo de decisão autônomo**:

```mermaid
graph TD;
    A[Input do Usuário] --> B{Router Inteligente};
    B -- Pergunta Genérica --> C[Gerador SQL Blindado];
    B -- NUOP --> D[Investigador Forense];
    C --> E[Executor SQL];
    E -- Erro --> C;
    E -- Sucesso --> F[Formatador];
    D --> G[Scanner Multi-Tabelas];
    G --> H[Extrator XML];
    H --> I[Cálculo SLA];
    I --> J[Auditor IA];

Componentes-chave

Router Node: Identifica se a entrada é uma consulta analítica ou investigação forense

Text-to-SQL Blindado: Injeta schema e regras de negócio para evitar alucinações

Investigador Forense: Consolida dados operacionais e legados em uma única visão

🛠️ Stack Tecnológico
Core

Python 3.10+

AsyncIO

IA & Agentes

LangChain

LangGraph

Ollama (Llama 3 Local)

Interface

Textual (TUI)

Pyttsx3 (Text-to-Speech)

Dados

PostgreSQL

Psycopg2

Pandas

lxml

Infraestrutura

Docker

Docker Compose

📦 Instalação e Execução
Pré-requisitos

Python 3.10+ ou Docker

Ollama rodando localmente:

ollama run llama3


Acesso a um banco PostgreSQL

🔹 Opção A — Execução Local

Clone o repositório:

git clone https://github.com/SeuUsuario/jarvis-spb.git
cd jarvis-spb


Crie o arquivo .env:

DB_HOST=localhost
DB_NAME=spb_database
DB_USER=postgres
DB_PASSWORD=sua_senha
OLLAMA_BASE_URL=http://localhost:11434


Instale as dependências:

pip install -r requirements.txt


Execute o sistema:

python Jarvis_ui.py

🔹 Opção B — Docker
docker-compose up --build

🧠 Exemplos de Uso
1️⃣ Investigação Forense (NUOP)

Entrada:

E000123456789...


Ações executadas:

Busca em múltiplas tabelas

Detecção de latência de 12s

Leitura do XML

Identificação de:

<RsnDesc>Saldo Insuficiente</RsnDesc>


Saída:

Relatório técnico indicando falha de negócio, apesar de degradação sistêmica.

2️⃣ Análise Analítica (SQL)

Entrada:

Quantas mensagens tiveram timeout nas últimas 2 horas?


Ação do Jarvis:

SELECT COUNT(*) 
FROM spi.operacao 
WHERE statusop = 205 
AND ts_inclusao >= now() - interval '2 hours';


Saída:

Tabela formatada

Execução segura (Read-Only)

📂 Estrutura do Projeto
.
├── agente_spb.py      # Core do LangGraph (nós, estados e regras)
├── Jarvis_ui.py       # Interface TUI (Textual + AsyncIO)
├── requirements.txt   # Dependências do projeto
├── .env               # Variáveis de ambiente (não versionado)
└── README.md          # Documentação

👨‍💻 Autor

Vinicius Costa
Engenheiro de Software & IA
Especialista em Automação, Observabilidade e Forense Bancária

🔗 GitHub: https://github.com/ViniciusCostawj
