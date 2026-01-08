# 🛡️ Jarvis SPB — Agente Forense Bancário Autônomo (v3.1)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![LangGraph](https://img.shields.io/badge/LangGraph-State%20Machine-orange?style=for-the-badge)
![Textual](https://img.shields.io/badge/UI-TUI-green?style=for-the-badge)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-blue?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-Ready-blue?style=for-the-badge&logo=docker)

> **Sistema Autônomo de Investigação Forense Bancária (SPB / PIX)**  
> Projetado para diagnosticar falhas transacionais, analisar mensagens ISO 20022, calcular SLA determinístico e traduzir linguagem natural em SQL seguro.

---

## 📌 Visão Geral

O **Jarvis SPB** é um agente forense bancário baseado em **máquina de estados (LangGraph)**, criado para operar em ambientes críticos do Sistema de Pagamentos Brasileiro.

Ele elimina a necessidade de:
- análise manual de XML do Bacen
- consultas SQL repetitivas
- correlação humana entre sistemas SPI, SPB e Legado

O sistema decide **automaticamente** se o input do usuário é:
- uma **consulta analítica (SQL)**  
- ou uma **investigação forense por NUOP**

---

## 🚀 Funcionalidades Principais

### 🧠 Orquestração por Grafo de Estados (LangGraph)
- Fluxo determinístico e auditável
- Guard-clauses para evitar análises inválidas
- Auto-retry de SQL com correção sintática automática

### 🕵️ Investigação Forense por NUOP
- Varredura em:
  - `spi.operacao`
  - `spi.legado`
  - `spb.operacao`
- Consolidação cronológica
- Veredito técnico automatizado (sucesso, timeout, erro Bacen, erro de negócio)

### 🧾 Parser XML ISO 20022 (lxml)
- Remoção de namespaces
- Extração confiável de:
  - `RsnDesc`
  - `AddtlInf`
  - `StsRsnInf`
- Tolerância a XML malformado

### ⏱️ SLA Determinístico
- Cálculo direto em Python:

ts_consumo - ts_entrega

- Alerta automático para consumo > 10s
- Independente de funções do banco

### 🧮 Text-to-SQL Blindado
- SQL somente leitura
- Uso de CTE universal (`view_universal`)
- Regras de negócio explícitas (timeout, saldo, piloto, autorizador)
- Proteção contra alucinação do LLM

### 🖥️ Interface TUI + Voz
- Interface terminal com **Textual**
- Feedback em tempo real
- Alertas por voz com `pyttsx3`
- Ideal para servidores *headless*

---

## 🧩 Arquitetura do Sistema

### 🔁 Grafo de Decisão Autônomo


graph TD
    
    A[Entrada do Usuário] --> B[Roteador Inteligente]
    B -->|SQL| C[Gerar SQL]
    B -->|NUOP| D[Investigar NUOP]
    C --> E[Executar SQL]
    E -->|Erro| C
    E -->|Sucesso| F[Fim]
    D --> G{NUOP Encontrado?}
    G -->|Sim| H[Análise Forense]
    G -->|Não| F
    H --> F

Componentes Reais (do código)

Router: Regex + heurística semântica

Gerador SQL: Prompt híbrido com glossário SPB

Executor SQL: Read-only + Pandas

Investigador NUOP: União SPI / SPB / Legado

Perito IA: Llama 3 local via Ollama

🛠️ Stack Tecnológico
Core

Python 3.10+

AsyncIO

Pandas

IA & Agentes

LangChain

LangGraph

Ollama (Llama 3 local)

Interface

Textual (TUI)

Rich

pyttsx3 (voz)

Banco de Dados

PostgreSQL

psycopg2

SQL com CTEs

Parsing

lxml (ISO 20022)

📦 Instalação
Pré-requisitos

Python 3.10+

PostgreSQL

Ollama rodando localmente:

ollama run llama3

🔹 Execução Local

Clone o repositório:

git clone https://github.com/SeuUsuario/jarvis-spb.git
cd jarvis-spb


Crie o .env:

DB_HOST=localhost
DB_PORT=5432
DB_NAME=spb_database
DB_USER=postgres
DB_PASSWORD=senha
OLLAMA_BASE_URL=http://localhost:11434


Instale dependências:

pip install -r requirements.txt


Execute a interface:

python Jarvis_ui.py

🧠 Exemplos de Uso
🔍 Investigação Forense

Entrada

E000123456789ABCDEF


Resultado

Rastreamento completo da transação

Identificação de erro de negócio ou timeout

Relatório técnico em Markdown

SLA calculado automaticamente

📊 Consulta Analítica

Entrada

Quantas mensagens tiveram timeout nas últimas 2 horas?


Resultado

SQL gerado automaticamente

Execução segura

Tabela formatada no terminal

📂 Estrutura do Projeto
.
├── agente_spb.py        # Núcleo do agente (LangGraph)
├── Jarvis_ui.py         # Interface TUI + Voz
├── requirements.txt     # Dependências
├── .env                 # Configurações (não versionado)
└── README.md            # Documentação

👨‍💻 Autor

Vinicius Costa
Engenheiro de Software & IA
Especialista em Observabilidade, Automação e Forense Bancária

🔗 GitHub: https://github.com/ViniciusCostawj
