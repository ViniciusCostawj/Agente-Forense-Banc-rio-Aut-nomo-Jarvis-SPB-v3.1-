import os
import re
import warnings
import pandas as pd
import psycopg2
from typing import TypedDict, Optional
from dotenv import load_dotenv

# LangChain / LangGraph imports
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END

# --- 0. CONFIGURAÇÃO GERAL ---
load_dotenv()
warnings.filterwarnings('ignore')

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "spb_database"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres")
}

# CTE Universal para SQL
CTE_UNIVERSAL = """
WITH view_universal AS (
    SELECT 
        'PIX' as origem, msgid, codmsg, nuop, statusop, 
        CAST(statusmsg AS INTEGER) as statusmsg, 
        COALESCE(sitlanc, 'N/A') as sitlanc, 
        ts_inclusao, msgop 
    FROM pix.operacao
    UNION ALL
    SELECT 
        'STR' as origem, msgid, codmsg, nuop, statusop, 
        CAST(statusmsg AS INTEGER) as statusmsg, 
        'N/A' as sitlanc, 
        ts_inclusao, msgop 
    FROM STR.operacao
)
"""



# --- 1. ESTADO DO AGENTE ---
class AgentState(TypedDict):
    input_usuario: str          
    historico: Optional[str]    
    tipo_fluxo: str             
    
    # Contexto SQL
    sql_query: Optional[str]    
    sql_erro: Optional[str]     
    sql_resultado: Optional[str]
    sql_executado: Optional[str] # Adicionado para debug na UI
    tentativas: int             
    
    # Contexto NUOP
    nuop_id: Optional[str]
    dados_nuop: Optional[pd.DataFrame] 
    relatorio_final: Optional[str]

# --- 2. CONEXÃO LLM & HELPERS ---

print("🔌 Conectando ao Llama 3 local...")
try:
    llm = ChatOllama(model="llama3", temperature=0, base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
except Exception as e:
    print(f"❌ Erro ao conectar no Ollama: {e}")
    exit()

from lxml import etree

def extrair_motivo_xml_parser(xml_text):
    """
    Parser robusto para XML do SPB (ISO20022).
    Remove namespaces e busca tags de erro estruturadas.
    """
    if not xml_text or not isinstance(xml_text, str):
        return ""

    try:
        # 1. Tenta converter string para Objeto XML
        # O encode é necessário porque lxml espera bytes
        parser = etree.XMLParser(recover=True) # recover=True tenta ignorar pequenos erros de formatação
        root = etree.fromstring(xml_text.encode('utf-8'), parser=parser)

        # 2. Truque para limpar Namespaces (ns0, ns1...) que atrapalham a busca
        # Isso normaliza <ns1:RsnDesc> para apenas <RsnDesc>
        for elem in root.getiterator():
            if not hasattr(elem.tag, 'find'): continue
            i = elem.tag.find('}')
            if i >= 0:
                elem.tag = elem.tag[i+1:]

        # 3. Lista de Tags onde o Bacen costuma esconder o motivo do erro
        tags_prioridade = [
            'RsnDesc',       # Reason Description (Mais comum)
            'AddtlInf',      # Additional Information
            'StsRsnInf',     # Status Reason Information
            'RjctnRsn',      # Rejection Reason
            'Prtry',         # Proprietary Error Code
            'Ustrd'          # Unstructured info
        ]

        # 4. Busca a primeira tag que tiver conteúdo
        for tag in tags_prioridade:
            # .// significa "busque em qualquer profundidade"
            found = root.find(f".//{tag}")
            if found is not None and found.text and found.text.strip():
                return found.text.strip()

    except Exception:
        # Se falhar (não for XML ou estiver corrompido), retorna vazio silenciosamente
        pass
        
    return ""

def calcular_sla_unificado(df):
    if df is None or df.empty: return "Sem dados."
    relatorio = "📊 SLA & PERFORMANCE:\n"
    df_leg = df.dropna(subset=['ts_entrega', 'ts_consumo'])
    if not df_leg.empty:
        evt = df_leg.iloc[-1]
        delta = (pd.to_datetime(evt['ts_consumo']) - pd.to_datetime(evt['ts_entrega'])).total_seconds()
        relatorio += f"   ➤ TEMPO CONSUMO: {delta:.3f}s\n"
        if delta > 10: relatorio += "      ⚠️ ALERTA: Consumo Lento (>10s)!\n"
        else: relatorio += "      🏆 Performance: Imediata.\n"
    return relatorio

# --- 3. NÓS DO GRAFO ---

def node_router(state: AgentState):
    """
    Roteador Inteligente: 
    - Se tem NUOP + Palavras de Contagem/Lista -> SQL
    - Se tem NUOP + Pergunta de Diagnóstico -> Forense
    - Se não tem NUOP -> SQL
    """
    entrada_original = state['input_usuario'].strip()
    entrada_lower = entrada_original.lower()
    
    # Busca o NUOP (Regex mantido)
    match_nuop = re.search(r'\b[a-zA-Z0-9]{20,35}\b', entrada_original)
    
    if match_nuop:
        # Lista de palavras que indicam intenção de BANCO DE DADOS (SQL), não análise clínica
        intencao_sql = [
            'quantas', 'quantidade', 'total', 'count', 
            'quais', 'listar', 'existe', 'aparece', 
            'vezes', 'repetiu'
        ]
        
        # Se o usuário falou "quantas" ou "listar", forçamos o fluxo SQL mesmo tendo NUOP
        if any(palavra in entrada_lower for palavra in intencao_sql):
             return {"tipo_fluxo": "sql", "tentativas": 0}
        
        # Caso contrário (ex: "o que houve", "analise", ou só o código solto) -> Fluxo Forense
        else:
            return {"tipo_fluxo": "nuop", "nuop_id": match_nuop.group()}
            
    else:
        # Sem NUOP, assume que é pergunta genérica para o SQL
        return {"tipo_fluxo": "sql", "tentativas": 0}

def node_gerar_sql(state: AgentState):
    pergunta = state['input_usuario']
    historico = state.get('historico', '') or "Sem histórico."
    erro_anterior = state.get('sql_erro')
    
    # --- TEMPLATE HÍBRIDO (O MELHOR DOS DOIS MUNDOS) ---
    template = """
    Você é um Especialista em Banco de Dados SPB/PIX.
    Sua missão é traduzir linguagem natural para SQL.
    
    📚 DICIONÁRIO DE STATUS:
    {glossario}
    
    SCHEMA 'view_universal':
    - origem (Texto): VALORES: 'SPI' ou 'SPB'.
      ⚠️ REGRA: Se usuário disser "Pix" -> use 'SPI'. Se "STR/TED" -> use 'SPB'.
    - msgid, codmsg, nuop (Texto), statusop, statusmsg, ts_inclusao, msgop
    
    🚨 REGRAS DE NEGÓCIO:
    1. TIMEOUT: statusop=205 AND msgop LIKE '%Pagamento expirado por timeout%'
    2. SALDO/LIMITE: statusmsg=320 AND (msgop ILIKE '%Saldo%' OR msgop ILIKE '%Insuficiente%' OR msgop ILIKE '%Limite%')
    3. PILOTO REJEITOU: statusmsg=319
    4. AUTORIZADOR REJEITOU: statusmsg=320
    
    🧠 LÓGICA DE MEMÓRIA (MUITO IMPORTANTE):
    
    CASO 1: BUSCA NOVA (GLOBAL)
    Se o usuário perguntar "quais", "quantas", "últimas X", "listar erros" ou usar plural:
    -> IGNORAR qualquer NUOP do histórico. Fazer uma busca limpa na tabela.
    
    CASO 2: CONTEXTO (REFERÊNCIA)
    APENAS se o usuário usar palavras como "esse", "dessa", "o código", "aquele id" E não der o número:
    -> Buscar o último NUOP citado no histórico e usar no WHERE.
    
    ⚠️ ATENÇÃO COM DATAS (HOMOLOGAÇÃO):
    Os dados do banco são de 2024/2025.
    - Se o usuário pedir "hoje" ou "agora", considere que ele quer dizer "DEZEMBRO DE 2025" (ex: ts_inclusao >= '2025-12-01').
    - Se não especificar data, traga os últimos registros ordenados por data (DESC).
    
    EXEMPLOS:
    - User: "Quantas mensagens recusadas pelo piloto?" -> SELECT count(*) FROM view_universal WHERE statusmsg = 319; (SEM NUOP!)
    - User: "O que houve com ela?" (Histórico tem E5610...) -> SELECT * FROM view_universal WHERE nuop = 'E5610...';
    
    HISTÓRICO RECENTE: 
    {historico}
    
    PERGUNTA ATUAL: {pergunta}
    
    RESPOSTA (APENAS O SQL):
    """
    
    if erro_anterior:
        template += f"\n🚨 ERRO ANTERIOR: {erro_anterior}. Corrija a sintaxe."
    
    prompt = PromptTemplate(input_variables=["historico", "pergunta", "glossario"], template=template)
    chain = prompt | llm | StrOutputParser()
    
    sql_bruto = chain.invoke({
        "historico": historico, 
        "pergunta": pergunta,
        "glossario": GLOSSARIO_SPB 
    })
    
    # --- LIMPEZA SEGURA (MANTIDA DO CÓDIGO ANTIGO) ---
    # Remove marcação markdown
    sql_limpo = re.sub(r"```sql|```", "", sql_bruto).strip()
    
    # Garante que pegamos apenas a partir do SELECT (ignora conversas antes)
    inicio_comando = sql_limpo.upper().find("SELECT")
    if inicio_comando != -1:
        sql_limpo = sql_limpo[inicio_comando:]
    else:
        # Se o LLM não gerou SELECT, retornamos um erro seguro vazio
        return {"sql_query": "SELECT 1 WHERE 1=0;", "tentativas": state.get('tentativas', 0) + 1}

    # Garante ponto e vírgula no final
    if ";" in sql_limpo: 
        sql_limpo = sql_limpo.split(";")[0] + ";"
        
    return {"sql_query": sql_limpo, "tentativas": state.get('tentativas', 0) + 1}

def node_executar_sql(state: AgentState):
    query_final = f"{CTE_UNIVERSAL} {state['sql_query']}"
    print(f"\n🔍 DEBUG QUERY: {query_final}\n") 
    
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        df = pd.read_sql(query_final, conn)
        
        if df.empty:
            return {
                "sql_resultado": "⚠️ Nenhum registro encontrado.", 
                "sql_executado": query_final,
                "sql_erro": None
            }
        
        # Limpeza Visual
        if 'msgop' in df.columns: df = df.drop(columns=['msgop'])
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].apply(lambda x: (str(x)[:50] + '...') if len(str(x)) > 50 else x)
        
        return {
            "sql_resultado": df.to_markdown(index=False), 
            "sql_executado": query_final,
            "sql_erro": None
        }
    except Exception as e:
        return {"sql_erro": str(e), "sql_resultado": None}
    finally:
        conn.close()

def node_investigar_nuop(state: AgentState):
    nuop_safe = state['nuop_id'].strip().replace("'", "")
    print(f"🕵️ Investigando NUOP: {nuop_safe}...")
    
    query = f"""
    WITH 
    spi_op AS (
        SELECT 'PIX.operacao' as origem, msgid, nuop, codmsg, statusop, statusmsg, sitlanc, ts_inclusao, msgop, NULL::timestamp as ts_entrega, NULL::timestamp as ts_consumo
        FROM PIX.operacao WHERE nuop LIKE '%{nuop_safe}%'
    ),
    spi_leg AS (
        SELECT 'PIX.legado', L.msgid, O.nuop, O.codmsg, NULL::smallint, NULL::smallint, NULL, L.ts_inclusao, O.msgop, L.ts_entrega, L.ts_consumo
        FROM PIX.legado L JOIN spi.operacao O ON L.msgid = O.msgid WHERE O.nuop LIKE '%{nuop_safe}%'
    ),
    spb_op AS (
        SELECT 'spb.operacao', msgid, nuop, codmsg, statusop, statusmsg, NULL, ts_inclusao, msgop, NULL::timestamp, NULL::timestamp
        FROM spb.operacao WHERE nuop LIKE '%{nuop_safe}%'
    )
    SELECT * FROM spi_op UNION ALL SELECT * FROM spi_leg UNION ALL SELECT * FROM spb_op ORDER BY ts_inclusao ASC;
    """
    
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        df = pd.read_sql(query, conn)
        if not df.empty:
            df['hora'] = pd.to_datetime(df['ts_inclusao'])
            return {"dados_nuop": df, "relatorio_final": None} # Limpa relatório anterior se houver
        else:
            # AQUI ESTÁ A MENSAGEM QUE ESTAVA SENDO PERDIDA
            return {"relatorio_final": f"⚠️ O NUOP '{nuop_safe}' não foi encontrado em nenhuma tabela (SPI/SPB). Verifique se o código está correto."}
    except Exception as e:
        return {"relatorio_final": f"Erro de conexão DB: {e}"}
    finally:
        conn.close()

def node_analise_forense(state: AgentState):
    """Analisa o DataFrame encontrado e gera o parecer."""
    df = state['dados_nuop']
    
    # 1. Pré-processamento: Extrair erros do XML com Parser Seguro
    df['evidencia_erro'] = df['msgop'].apply(lambda x: extrair_motivo_xml_parser(str(x)))
    sla = calcular_sla_unificado(df)
    
    # 2. Tabela para a IA ler
    cols_ia = ['origem', 'codmsg', 'statusop', 'statusmsg', 'evidencia_erro', 'ts_inclusao']
    tabela_para_ia = df[cols_ia].to_markdown(index=False)
    
    # 3. Prompt com a NOVA LÓGICA DE PRECISÃO
    template = """
    Você é um Perito Forense do Sistema Bancário (SPB/PIX).
    DADOS TÉCNICOS DA OPERAÇÃO (Histórico Completo):
    {tabela}
    
    PERFORMANCE:
    {sla}
    
    🧠 HIERARQUIA DE DECISÃO (SIGA NESTA ORDEM EXATA):
    
    1. **CHECAGEM DE SUCESSO (PRIORIDADE SUPREMA):**
       - Analise a coluna 'statusmsg'. Se encontrar **302** (OK) ou **108** (Liquidado) em *qualquer linha*, o Veredito FINAL é **SUCESSO**, independente de erros anteriores. O pagamento foi concluído.
       
    2. **CHECAGEM DE FALHA (Apenas se não houve sucesso):**
       - Se NÃO houver código 302/108, analise a coluna 'evidencia_erro' e 'statusop':
       
       A. **TIMEOUT CONFIRMADO:** Se o texto na coluna 'evidencia_erro' contiver a frase exata "pagamento expirado por timeout" -> Veredito: **TIMEOUT / FALHA TÉCNICA**.
       
       B. **ERRO DE CADASTRO:** Se o texto contiver "Identificação", "Agente", "Participante", "Conta Inexistente", "Saldo" -> Veredito: **ERRO OPERACIONAL / CADASTRO**.
       
       C. **ERRO DO BACEN (205):** Se 'statusop' for 205 mas o texto NÃO for timeout -> Veredito: **ERRO DE PROCESSAMENTO NO BACEN** (Cite o texto do erro encontrado).
       
       D. **REJEIÇÃO DE NEGÓCIO:** Se 'statusmsg' for 319 ou 320 -> Veredito: **REJEIÇÃO DE NEGÓCIO**.

    ⚠️ REGRA DE SILÊNCIO (LEGADO):
    - Se a origem for 'spi.legado', ignore colunas vazias. Foque apenas no texto de erro se houver.
    
    RELATÓRIO FINAL (Markdown):
    **Resumo do Caso:** (Ex: "Operação liquidada com sucesso" ou "Falha por timeout no Bacen")
    **Análise Técnica:** (Detalhe se foi erro 205 genérico ou se houve a mensagem explícita de timeout)
    **Veredito Final:** (SUCESSO / TIMEOUT / ERRO BACEN / ERRO OPERACIONAL)
    """
    
    prompt = PromptTemplate(input_variables=["tabela", "sla"], template=template)
    chain = prompt | llm | StrOutputParser()
    analise = chain.invoke({"tabela": tabela_para_ia, "sla": sla})
    
    return {"relatorio_final": analise}

# --- 4. FUNÇÕES DE CONTROLE DE FLUXO (NOVAS) ---

def check_nuop_found(state: AgentState):
    """Guarda de trânsito: Só deixa passar para IA se tiver dados."""
    if state.get("relatorio_final"):
        # Se já tem mensagem (ex: "Não encontrado"), encerra aqui.
        return "encerrar"
    if state.get("dados_nuop") is not None and not state["dados_nuop"].empty:
        return "analisar"
    return "encerrar"

def check_sql_status(state: AgentState):
    if state['sql_erro']:
        return "retry" if state['tentativas'] < 3 else "give_up"
    return "success"

# --- 5. MONTAGEM DO GRAFO ---

workflow = StateGraph(AgentState)

workflow.add_node("router", node_router)
workflow.add_node("gerar_sql", node_gerar_sql)
workflow.add_node("executar_sql", node_executar_sql)
workflow.add_node("investigar_nuop", node_investigar_nuop)
workflow.add_node("analise_forense", node_analise_forense)

workflow.set_entry_point("router")

# Rota inicial
workflow.add_conditional_edges(
    "router",
    lambda state: "investigar_nuop" if state['tipo_fluxo'] == "nuop" else "gerar_sql",
    {"investigar_nuop": "investigar_nuop", "gerar_sql": "gerar_sql"}
)

# Rota NUOP (AQUI ESTAVA O BUG - AGORA CORRIGIDO)
workflow.add_conditional_edges(
    "investigar_nuop",
    check_nuop_found,
    {
        "analisar": "analise_forense",
        "encerrar": END
    }
)
workflow.add_edge("analise_forense", END)

# Rota SQL
workflow.add_edge("gerar_sql", "executar_sql")
workflow.add_conditional_edges(
    "executar_sql",
    check_sql_status,
    {"retry": "gerar_sql", "success": END, "give_up": END}
)


app = workflow.compile()
