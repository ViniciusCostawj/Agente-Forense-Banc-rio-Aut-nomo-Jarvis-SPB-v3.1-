import sys
import asyncio
import threading
import re
from datetime import datetime

# Bibliotecas Visuais
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Input, RichLog, Static

# Biblioteca de Voz
import pyttsx3

# --- IMPORT DO BACKEND ---
try:
    from agente_spb import app as agente_graph
    BACKEND_ATIVO = True
except ImportError:
    BACKEND_ATIVO = False

# --- CONFIGURAÇÃO DE VOZ (Thread Segura) ---
def speak_system(text):
    def run_speech():
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 190)
            engine.setProperty('volume', 1.0)
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass 
    thread = threading.Thread(target=run_speech, daemon=True)
    thread.start()

# --- CSS ---
CSS = """
Screen { background: #0d1117; color: #e6edf3; }
Header { background: #161b22; color: #00ffaa; dock: top; height: 3; content-align: center middle; text-style: bold; border-bottom: solid #00ffaa; }
#sidebar { dock: left; width: 35; height: 100%; background: #0d1117; border-right: solid #333; padding: 1 2; }
#chat-area { background: #0d1117; border: heavy #00ffaa; margin: 1 1 1 1; height: 1fr; padding: 1; overflow-y: scroll; }
Input { dock: bottom; width: 100%; height: 3; margin: 0 1 1 1; padding: 0; border: solid #00ffaa; background: #262626; color: #ffffff; }
Input:focus { border: double #ffffff; background: #333333; }
.status-box { background: #161b22; border: solid #333; height: auto; margin-bottom: 2; padding: 1; }
.label { color: #888; text-style: bold; }
.value { color: #00ffaa; }
.value-error { color: #ff5555; }
.title-side { color: #00ffff; text-style: bold underline; margin-bottom: 1; text-align: center; }
"""

class SpbJarvisApp(App):
    CSS = CSS
    TITLE = "🛡️ SPB FORENSIC SYSTEM // v3.1 (Fixed)"
    
    # Memória de Curto Prazo
    chat_memory = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            # LATERAL
            with Container(id="sidebar"):
                yield Static("SYSTEM STATUS", classes="title-side")
                with Container(classes="status-box"):
                    yield Static("🔌 CONEXÃO DB", classes="label")
                    yield Static("ONLINE", classes="value") if BACKEND_ATIVO else Static("OFFLINE", classes="value-error")
                with Container(classes="status-box"):
                    yield Static("🧠 IA CORE", classes="label")
                    yield Static("Llama 3 (Local)", classes="value")
                with Container(classes="status-box"):
                    yield Static("⚡ STATUS", classes="label")
                    yield Static("AGUARDANDO", classes="value", id="st_action")
                yield Static("GUIDE:", classes="title-side")
                yield Static("• Digite NUOP para análise.\n• Perguntas SQL.", classes="label")

            # CHAT AREA
            with Container(): 
                self.log_widget = RichLog(id="chat-area", highlight=True, markup=True, wrap=True)
                yield self.log_widget
                self.input_widget = Input(placeholder="📝 COMANDO...", id="input_cmd")
                yield self.input_widget
        yield Footer()

    def on_mount(self):
        self.log_widget.write("[bold green]🔁 INICIANDO SISTEMA JARVIS...[/]")
        if BACKEND_ATIVO:
            speak_system("Sistema Online.")
            self.log_widget.write("[bold cyan]✅ SISTEMA DE VOZ ATIVO.[/]")
        self.input_widget.focus()

    async def on_input_submitted(self, message: Input.Submitted):
        user_msg = message.value
        if not user_msg: return

        self.input_widget.value = ""
        self.input_widget.focus() 

        self.log_widget.write(f"\n[bold white]👤 VOCÊ:[/]\n{user_msg}")
        self.query_one("#st_action").update("PROCESSANDO...")
        self.query_one("#st_action").classes = "value-error"

        if BACKEND_ATIVO:
            result = await asyncio.to_thread(self.processar_com_agente, user_msg)
            self.exibir_resultado(result)
        else:
            self.log_widget.write("[bold yellow]⚠️ MODO DEMO (SEM BACKEND).[/]")

        self.query_one("#st_action").update("AGUARDANDO")
        self.query_one("#st_action").classes = "value"

    def processar_com_agente(self, texto_usuario):
        try:
            # 1. Prepara o histórico
            # Aumentei para pegar as últimas 10 linhas para dar mais contexto
            contexto_str = "\n".join(self.chat_memory[-10:]) 
            
            inputs = {
                "input_usuario": texto_usuario,
                "historico": contexto_str
            }
            
            resultado = agente_graph.invoke(inputs)
            
            # --- ATUALIZAÇÃO DA MEMÓRIA (AQUI É A MÁGICA) ---
            # 1. Salva a pergunta do usuário
            self.chat_memory.append(f"User: {texto_usuario}")
            
            # 2. Salva a RESPOSTA REAL da IA (não apenas um placeholder)
            # Isso permite que a IA leia o NUOP ou o Erro que ela mesma citou antes
            
            if resultado.get('relatorio_final'):
                # Salva o relatório (pode ser grande, então salvamos ele todo para contexto)
                texto_limpo = str(resultado['relatorio_final']).replace('\n', ' ')
                self.chat_memory.append(f"AI Analysis: {texto_limpo[:500]}...") # Limita a 500 chars para não estourar o prompt
            
            elif resultado.get('sql_query'):
                # Salva a query (ajuda a IA a saber o que ela pesquisou antes)
                self.chat_memory.append(f"AI SQL Executed: {resultado['sql_query']}")
                
                # Opcional: Salvar que dados foram encontrados
                if resultado.get('sql_resultado'):
                    dados_resumo = str(resultado['sql_resultado']).replace('\n', ' ')
                    self.chat_memory.append(f"AI Data Result: {dados_resumo[:200]}...")

            return resultado
        except Exception as e:
            return {"erro_sistema": str(e)}

    def exibir_resultado(self, result):
        self.log_widget.write("\n[bold cyan]🤖 JARVIS:[/]")

        # 1. Debug SQL
        if result.get('sql_executado'):
            self.log_widget.write("[dim]🔍 QUERY EXECUTADA:[/]")
            self.log_widget.write(f"```sql\n{result['sql_executado']}\n```")

        # 2. Erros de Sistema
        if result.get('erro_sistema'):
            self.log_widget.write(f"[bold red]❌ ERRO CRÍTICO:[/]\n{result['erro_sistema']}")

        # 3. Relatório Final (Pode ser análise forense OU aviso de não encontrado)
        elif result.get('relatorio_final'):
            relatorio = result['relatorio_final']
            
            # Se for apenas aviso de não encontrado
            if "não encontrado" in relatorio.lower() or "⚠️" in relatorio:
                 self.log_widget.write(f"[bold orange3]{relatorio}[/]")
                 speak_system("Informação não localizada.")
            else:
                self.log_widget.write(relatorio)
                self.log_widget.write(f"\n[italic green]💾 Log salvo.[/]")
                speak_system("Análise concluída.")

        # 4. Resultado SQL
        elif result.get('sql_resultado'):
            self.log_widget.write("[bold blue]📊 DADOS:[/]")
            self.log_widget.write(f"```\n{result['sql_resultado']}\n```")
            speak_system("Dados recuperados.")

        # 5. Erro SQL Específico
        elif result.get('sql_erro'):
            self.log_widget.write("[bold red]❌ ERRO SQL:[/]")
            self.log_widget.write(result['sql_erro'])
            speak_system("Erro na query.")
        
        self.log_widget.write("---")

if __name__ == "__main__":
    app = SpbJarvisApp()
    app.run()