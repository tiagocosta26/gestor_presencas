from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, session, flash
import csv, os, re, json
from collections import defaultdict
from werkzeug.utils import secure_filename
from datetime import datetime
from flask_bcrypt import Bcrypt
import copy
from datetime import datetime
import json
import uuid # Para gerar IDs únicos para as atividades
from icalendar import Calendar, Event
from flask import make_response
from datetime import datetime, timedelta

app = Flask(__name__)
bcrypt = Bcrypt(app)
app.config['SECRET_KEY'] = 'uma_chave_segura_para_as_sessoes'

# Diretórios para guardar os ficheiros
DIRETORIO_PRESENCAS = "registos"
DIRETORIO_TESOURARIA = "tesouraria"
DIRETORIO_UPLOADS = "uploads" 
DIRETORIO_RECEITAS = os.path.join(DIRETORIO_UPLOADS, 'receitas')
DIRETORIO_UPLOADS_COZINHA = os.path.join(DIRETORIO_UPLOADS, 'cozinha')
DIRETORIO_ATAS = os.path.join(DIRETORIO_UPLOADS, 'atas')
DIRETORIO_OUTROS_DOCS = os.path.join(DIRETORIO_UPLOADS, 'outros')
os.makedirs(DIRETORIO_PRESENCAS, exist_ok=True)
os.makedirs(DIRETORIO_TESOURARIA, exist_ok=True)
os.makedirs(DIRETORIO_UPLOADS, exist_ok=True)
os.makedirs(DIRETORIO_RECEITAS, exist_ok=True)
os.makedirs(DIRETORIO_ATAS, exist_ok=True)
os.makedirs(DIRETORIO_OUTROS_DOCS, exist_ok=True)
os.makedirs(DIRETORIO_UPLOADS_COZINHA, exist_ok=True)

# Ficheiros JSON para guardar os dados
FICHEIRO_TRIBOS = "tribos.json"
FICHEIRO_CARGOS = "cargos.json"
FICHEIRO_UTILIZADORES = "utilizadores.json"
FICHEIRO_MATERIAL = "material.json"
FICHEIRO_FARMACIA = "farmacia.json"
FICHEIRO_ALERGIAS = "alergias.json"
FICHEIRO_CONDICOES = "condicoes.json"
FICHEIRO_COZINHA = "inventario_cozinha.json"
FICHEIRO_RECEITAS = "receitas.json"
FICHEIRO_PROGRESSO = "progresso.json"
FICHEIRO_PROGRESSO_MODELO = "progresso_modelo.json"
FICHEIRO_CALENDARIO = "atividades_calendario.json"

# Adicionar a pasta de uploads à configuração da aplicação
app.config['UPLOAD_FOLDER'] = DIRETORIO_UPLOADS

# --- FUNÇÕES AUXILIARES ---
def carregar_tribos():
    """Carrega as tribos do ficheiro JSON."""
    if os.path.exists(FICHEIRO_TRIBOS):
        with open(FICHEIRO_TRIBOS, encoding="utf-8") as f:
            return json.load(f)
    return {}

def carregar_nomes():
    """Carrega as pessoas do ficheiro JSON e devolve uma lista de todas as pessoas."""
    if os.path.exists(FICHEIRO_TRIBOS):
        with open(FICHEIRO_TRIBOS, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                pessoas = []
                for tribo, membros in data.items():
                    for membro in membros:
                        pessoas.append(membro['nome'])
                return pessoas
            except json.JSONDecodeError:
                return []
    return []

def guardar_tribos(tribos):
    """Guarda as tribos no ficheiro JSON."""
    with open(FICHEIRO_TRIBOS, "w", encoding="utf-8") as f:
        json.dump(tribos, f, indent=4, ensure_ascii=False)

def carregar_cargos():
    """Carrega os cargos do ficheiro JSON ou cria um com cargos padrão."""
    if os.path.exists(FICHEIRO_CARGOS):
        with open(FICHEIRO_CARGOS, encoding="utf-8") as f:
            return json.load(f)
    cargos_padrao = {
        "Guia": "#bb2124",
        "Sub-Guia": "#bb2124",
        "Secretário": "#007bff",
        "Tesoureiro": "#28a745",
        "Animador": "#ffa500",
        "Cozinheiro": "#ffde21",
        "Socorrista": "#ff0000",
        "Guarda-Material": "#7c3a00",
        "Relações Públicas": "#87cefa"
    }
    with open(FICHEIRO_CARGOS, "w", encoding="utf-8") as f:
        json.dump(cargos_padrao, f, indent=4, ensure_ascii=False)
    return cargos_padrao

def carregar_utilizadores():
    """Carrega os utilizadores do ficheiro JSON."""
    if os.path.exists(FICHEIRO_UTILIZADORES):
        with open(FICHEIRO_UTILIZADORES, encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_utilizadores(utilizadores):
    """Guarda os utilizadores no ficheiro JSON."""
    with open(FICHEIRO_UTILIZADORES, "w", encoding="utf-8") as f:
        json.dump(utilizadores, f, indent=4, ensure_ascii=False)

def limpar_nome(nome):
    """Limpa uma string para ser usada como nome de ficheiro seguro, permitindo '/' no nome real da atividade."""
    nome_ficheiro = nome.replace('/', '-')
    nome_ficheiro = re.sub(r'[^A-Za-z0-9áéíóúãõàèùçÁÉÍÓÚÀÈÙÇ_\-@ ]', '_', nome_ficheiro)
    return nome_ficheiro


def carregar_folha_caixa(entidade):
    """Carrega a folha de caixa de uma entidade (Clan ou tribo)."""
    caminho = os.path.join(DIRETORIO_TESOURARIA, f"{limpar_nome(entidade)}.json")
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    return []

def guardar_folha_caixa(entidade, folha_caixa):
    """Guarda a folha de caixa de uma entidade."""
    caminho = os.path.join(DIRETORIO_TESOURARIA, f"{limpar_nome(entidade)}.json")
    os.makedirs(DIRETORIO_TESOURARIA, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(folha_caixa, f, indent=4, ensure_ascii=False)

def carregar_material():
    """Carrega o material do ficheiro JSON."""
    if os.path.exists(FICHEIRO_MATERIAL):
        with open(FICHEIRO_MATERIAL, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def guardar_farmacia(farmacia):
    """Guarda o material da farmácia no ficheiro JSON."""
    with open(FICHEIRO_FARMACIA, "w", encoding="utf-8") as f:
        json.dump(farmacia, f, indent=4, ensure_ascii=False)

def carregar_farmacia():
    """Carrega o material da farmácia do ficheiro JSON."""
    if os.path.exists(FICHEIRO_FARMACIA):
        with open(FICHEIRO_FARMACIA, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def guardar_alergias(alergias):
    """Guarda as alergias no ficheiro JSON."""
    with open(FICHEIRO_ALERGIAS, "w", encoding="utf-8") as f:
        json.dump(alergias, f, indent=4, ensure_ascii=False)

def carregar_alergias():
    """Carrega as alergias do ficheiro JSON."""
    if os.path.exists(FICHEIRO_ALERGIAS):
        with open(FICHEIRO_ALERGIAS, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def guardar_condicoes(condicoes):
    """Guarda as condições no ficheiro JSON."""
    with open(FICHEIRO_CONDICOES, "w", encoding="utf-8") as f:
        json.dump(condicoes, f, indent=4, ensure_ascii=False)

def carregar_condicoes():
    """Carrega as condições do ficheiro JSON."""
    if os.path.exists(FICHEIRO_CONDICOES):
        with open(FICHEIRO_CONDICOES, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def guardar_material(material):
    """Guarda o material no ficheiro JSON."""
    with open(FICHEIRO_MATERIAL, "w", encoding="utf-8") as f:
        json.dump(material, f, indent=4, ensure_ascii=False)

def carregar_inventario_cozinha():
    """Carrega o inventário da cozinha do ficheiro JSON."""
    if os.path.exists(FICHEIRO_COZINHA):
        with open(FICHEIRO_COZINHA, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def guardar_inventario_cozinha(inventario):
    """Guarda o inventário da cozinha no ficheiro JSON."""
    with open(FICHEIRO_COZINHA, "w", encoding="utf-8") as f:
        json.dump(inventario, f, indent=4, ensure_ascii=False)

def carregar_receitas():
    """Carrega as receitas do ficheiro JSON."""
    if os.path.exists(FICHEIRO_RECEITAS):
        with open(FICHEIRO_RECEITAS, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def guardar_receitas(receitas):
    """Guarda as receitas no ficheiro JSON."""
    with open(FICHEIRO_RECEITAS, "w", encoding="utf-8") as f:
        json.dump(receitas, f, indent=4, ensure_ascii=False)

def carregar_progresso():
    progresso = {}
    if not os.path.exists(FICHEIRO_PROGRESSO):
        return progresso
    with open(FICHEIRO_PROGRESSO, encoding="utf-8") as f:
        try:
            progresso = json.load(f)
        except json.JSONDecodeError:
            progresso = {}
    return progresso



def guardar_progresso(dados):
    """Guarda o progresso no ficheiro JSON."""
    with open(FICHEIRO_PROGRESSO, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def carregar_progresso_modelo():
    """Carrega o modelo de progresso do ficheiro JSON."""
    if os.path.exists(FICHEIRO_PROGRESSO_MODELO):
        with open(FICHEIRO_PROGRESSO_MODELO, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

# Cria o ficheiro JSON vazio se não existir
if not os.path.exists(FICHEIRO_CALENDARIO):
    with open(FICHEIRO_CALENDARIO, 'w') as f:
        json.dump([], f)

def carregar_atividades_calendario():
    with open(FICHEIRO_CALENDARIO, 'r') as f:
        return json.load(f)

def guardar_atividades_calendario(atividades):
    with open(FICHEIRO_CALENDARIO, 'w') as f:
        json.dump(atividades, f, indent=4)

@app.template_global()
def calcular_progresso_bool_do_dicionario(obj):
    """
    Converte um dicionário de progresso de "feito"/"pendente" para True/False.
    """
    if isinstance(obj, dict):
        return {k: calcular_progresso_bool_do_dicionario(v) for k, v in obj.items()}
    elif isinstance(obj, str):
        return obj == "concluído"
    else:
        return False
        
@app.template_global()
def calcular_nivel(dados_pessoa_bool, trilhos_por_area):
    """
    Calcula a etapa de um membro com base no progresso dos trilhos.

    Regras de Etapa:
    - 'a': Estado inicial.
    - 'b': 1 trilho concluído em cada área.
    - 'c': 2 trilhos concluídos em cada área.
    - 'd': Todos os trilhos concluídos em cada área.
    """
    trilhos_concluidos_por_area = {}
    
    # 1. Conta quantos trilhos foram concluídos em cada área
    for area_nome, trilhos_da_area in trilhos_por_area.items():
        count_trilhos_concluidos = 0
        
        # Itera sobre cada trilho da área
        for trilho_nome, objetivos_do_trilho in trilhos_da_area.items():
            trilho_completo = True
            
            # Acede aos dados da pessoa para este trilho
            dados_trilho = dados_pessoa_bool.get(area_nome, {}).get(trilho_nome, {})
            
            # Verifica se todos os objetivos do trilho foram concluídos
            for objetivo in objetivos_do_trilho:
                # Se algum objetivo não for "feito" (representado como True), o trilho não está completo
                if not dados_trilho.get(objetivo):
                    trilho_completo = False
                    break
            
            if trilho_completo:
                count_trilhos_concluidos += 1
        
        trilhos_concluidos_por_area[area_nome] = count_trilhos_concluidos

    # 2. Avalia a etapa com base na contagem de trilhos
    # Verifica primeiro a etapa mais alta para garantir a progressão correta.
    
    # Condição para Etapa 'Anilha de Mérito': todos os trilhos concluídos em cada área.
    todos_concluidos = all(trilhos_concluidos_por_area[area] == len(trilhos_por_area[area]) for area in trilhos_por_area)
    if todos_concluidos:
        return "Anilha de Mérito"
    
    # Condição para Etapa 'Partida': 2 trilhos concluídos em cada área.
    dois_por_area = all(trilhos_concluidos_por_area[area] >= 2 for area in trilhos_concluidos_por_area)
    if dois_por_area:
        return "Partida"
        
    # Condição para Etapa 'Serviço': 1 trilho concluído em cada área.
    um_por_area = all(trilhos_concluidos_por_area[area] >= 1 for area in trilhos_concluidos_por_area)
    if um_por_area:
        return "Serviço"
        
    # Se nenhuma das condições for satisfeita, o membro fica na Etapa 'Comunidade'
    return "Comunidade"



# --- ROTAS PRINCIPAIS ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/gestao_presencas", methods=["GET", "POST"])
def presencas():
    """Rota principal para registar uma nova atividade."""
    tribos = carregar_tribos()
    
    if request.method == "POST":
        atividade = request.form["atividade"]
        atividade_limpa = limpar_nome(atividade)
        data_inicio = request.form["data_inicio"]
        data_fim = request.form["data_fim"]
        tribos_selecionadas = request.form["tribos_selecionadas"].split(",")

        caminho = os.path.join(DIRETORIO_PRESENCAS, f"{atividade_limpa}_{data_inicio}_a_{data_fim}.csv")

        with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["Atividade", "Data Início", "Data Fim", "Tribo", "Elemento", "Cargos", "Presente"])
            
            for tribo_nome in tribos_selecionadas:
                membros = tribos.get(tribo_nome, [])
                for membro in membros:
                    nome = membro['nome']
                    cargos_list = membro.get('cargo', [])
                    cargos_str = ', '.join(cargos_list)
                    presente = "Sim" if request.form.get(f"presenca_{nome}") == "Sim" else "Não"
                    writer.writerow([atividade, data_inicio, data_fim, tribo_nome, nome, cargos_str, presente])

        return redirect(url_for("atividades"))

    from datetime import date
    hoje = date.today().isoformat()
    return render_template("gestao_presencas.html", hoje=hoje, tribos=tribos)


@app.route("/atividades")
def atividades():
    """Exibe a lista de atividades registadas."""
    ficheiros = [f for f in os.listdir(DIRETORIO_PRESENCAS) if f.endswith(".csv")]
    atividades_agrupadas = defaultdict(list)

    def extrair_titulo_e_data(ficheiro):
        """Tenta extrair a data e o título limpo de um nome de ficheiro."""
        
        # Remover a extensão .csv
        nome_base = ficheiro.rsplit('.', 1)[0]
        partes = nome_base.split('_')
        
        data_atividade = None
        indice_data = -1

        # Procurar a primeira parte que consiga ser convertida em data (YYYY-MM-DD)
        for i in range(1, len(partes)):
            try:
                # Tenta converter a parte atual do nome em data
                data_atividade = datetime.strptime(partes[i].strip(), "%Y-%m-%d")
                indice_data = i
                break # Se encontrar, sai do loop
            except ValueError:
                # Não é uma data, continua a procurar
                continue
        
        if data_atividade and indice_data != -1:
            
            # O título é a junção de todas as partes *antes* da data encontrada
            titulo_partes = partes[0:indice_data]
            
            # Rejuntar as partes do título *apenas* com um espaço para remover separadores _
            titulo_limpo = ' '.join(p.strip() for p in titulo_partes).strip()
            
            # Reconstituir o título *exatamente* como estava no ficheiro, antes da data.
            titulo_bruto_list = partes[0:indice_data]
            titulo_bruto = '_'.join(titulo_bruto_list).strip()
            titulo_limpo = titulo_bruto.replace(' _ ', ' + ').replace('_', ' ').strip()
            
            return data_atividade, titulo_limpo
        
        # Se não encontrar a data, retorna None
        return None, None


    for ficheiro in ficheiros:
        data_inicio, titulo = extrair_titulo_e_data(ficheiro)
        
        if data_inicio and titulo:
            mes_ano = data_inicio.strftime("%Y-%m")
            atividades_agrupadas[mes_ano].append((data_inicio, ficheiro, titulo))

    # Ordena os meses do mais recente para o mais antigo
    meses_ordenados = sorted(atividades_agrupadas.keys(), reverse=True)

    # Ordena as atividades dentro de cada mês da mais recente para a mais antiga
    for mes in meses_ordenados:
        atividades_agrupadas[mes].sort(key=lambda x: x[0], reverse=True)
        
        atividades_agrupadas[mes] = [(f[1], f[2]) for f in atividades_agrupadas[mes]]

    return render_template("atividades.html", atividades_agrupadas=atividades_agrupadas, meses_ordenados=meses_ordenados)


@app.route('/eliminar_atividade/<nome_ficheiro>', methods=['POST'])
def eliminar_atividade(nome_ficheiro):
    """Elimina um ficheiro de atividade."""
    try:
        caminho_ficheiro = os.path.join(DIRETORIO_PRESENCAS, nome_ficheiro)
        if os.path.exists(caminho_ficheiro):
            os.remove(caminho_ficheiro)
    except Exception:
        pass
    return redirect(url_for('atividades'))

@app.route("/gestao_tribos", methods=["GET", "POST"])
def gestao_tribos():
    """Página para gerir tribos e membros."""
    tribos = carregar_tribos()
    cargos_disponiveis = carregar_cargos()
    
    cargo_ordem = {cargo: i for i, cargo in enumerate(cargos_disponiveis)}

    if request.method == "POST":
        acao = request.form.get("acao")
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if acao == "criar_tribo":
            nome_tribo = request.form.get("nome_tribo").strip()
            if nome_tribo and nome_tribo not in tribos:
                tribos[nome_tribo] = []
                guardar_tribos(tribos)
            if not is_ajax:
                return redirect(url_for("gestao_tribos"))
            return jsonify({"status": "ok"})

        elif acao == "remover_tribo":
            nome_tribo = request.form.get("nome_tribo")
            if nome_tribo in tribos:
                del tribos[nome_tribo]
                guardar_tribos(tribos)
            if not is_ajax:
                return redirect(url_for("gestao_tribos"))
            return jsonify({"status": "ok"})

        elif acao == "adicionar_pessoa":
            tribo = request.form.get("tribo")
            nome_pessoa = request.form.get("nome_pessoa").strip()
            if tribo in tribos and nome_pessoa:
                nova_pessoa = {"nome": nome_pessoa, "cargo": []}
                tribos[tribo].append(nova_pessoa)
                guardar_tribos(tribos)
                if not is_ajax:
                    return redirect(url_for("gestao_tribos", tribo_id=tribo))
                return jsonify({"status": "ok", "pessoa": nova_pessoa})

        elif acao == "remover_pessoa":
            tribo = request.form.get("tribo")
            nome_pessoa = request.form.get("nome_pessoa")
            if tribo in tribos:
                tribos[tribo] = [p for p in tribos[tribo] if p["nome"] != nome_pessoa]
                guardar_tribos(tribos)
            if not is_ajax:
                return redirect(url_for("gestao_tribos"))
            return jsonify({"status": "ok", "nome_pessoa": nome_pessoa})
        
        elif acao == "adicionar_cargo":
            tribo = request.form.get("tribo")
            nome_pessoa = request.form.get("nome_pessoa")
            cargo = request.form.get("cargo")
            
            if tribo in tribos and nome_pessoa and cargo:
                for pessoa in tribos[tribo]:
                    if pessoa["nome"] == nome_pessoa:
                        if cargo in pessoa["cargo"]:
                            pessoa["cargo"].remove(cargo)
                        else:
                            pessoa["cargo"].append(cargo)
                        
                        pessoa["cargo"].sort(key=lambda c: cargo_ordem.get(c, float('inf')))
                        break
                guardar_tribos(tribos)
                if not is_ajax:
                    return redirect(url_for("gestao_tribos"))
                return jsonify({"status": "ok", "pessoa": pessoa, "cargos_disponiveis": cargos_disponiveis})
                
        elif acao == 'ordenar':
            original_tribo = request.form.get('original_tribo')
            nova_tribo = request.form.get('nova_tribo')
            nome_pessoa = request.form.get('nome_pessoa')
            ordem_json = request.form.get('ordem')
            
            # Validação básica
            if not all([original_tribo, nova_tribo, nome_pessoa, ordem_json]):
                return jsonify({'status': 'error', 'message': 'Dados em falta'}), 400

            try:
                ordem = json.loads(ordem_json)
            except json.JSONDecodeError:
                return jsonify({'status': 'error', 'message': 'Ordem inválida'}), 400

            # Encontrar a pessoa a mover na tribo original
            pessoa_movida = None
            if original_tribo in tribos:
                for p in tribos[original_tribo]:
                    if p['nome'] == nome_pessoa:
                        pessoa_movida = p
                        tribos[original_tribo].remove(p)
                        break

            if not pessoa_movida:
                return jsonify({'status': 'error', 'message': 'Pessoa não encontrada na tribo original'}), 400

            # Adicionar a pessoa à nova tribo na ordem correta
            if nova_tribo not in tribos:
                tribos[nova_tribo] = []
            
            nova_lista_ordenada = []
            for nome in ordem:
                if nome == nome_pessoa:
                    nova_lista_ordenada.append(pessoa_movida)
                else:
                    # Encontrar a pessoa existente na tribo de destino
                    for p_existente in tribos[nova_tribo]:
                        if p_existente['nome'] == nome:
                            nova_lista_ordenada.append(p_existente)
                            break
                            
            # Remover duplicados e garantir que a pessoa movida é incluída
            nomes_na_lista = {p['nome'] for p in nova_lista_ordenada}
            if nome_pessoa not in nomes_na_lista:
                nova_lista_ordenada.append(pessoa_movida)
            
            tribos[nova_tribo] = nova_lista_ordenada
            
            guardar_tribos(tribos)
            return jsonify({'status': 'ok'})

    return render_template("gestao_tribos.html", tribos=tribos, cargos_disponiveis=cargos_disponiveis)

@app.route("/reordenar_pessoas", methods=["POST"])
def reordenar_pessoas():
    """Rota para reordenar membros de uma tribo."""
    data = request.get_json()
    tribo = data.get("tribo")
    nova_ordem_nomes = data.get("nova_ordem")

    tribos = carregar_tribos()
    if tribo in tribos and isinstance(nova_ordem_nomes, list):
        pessoas_originais = tribos[tribo]
        pessoas_mapa = {p["nome"]: p for p in pessoas_originais}
        
        nova_lista_pessoas = []
        for nome in nova_ordem_nomes:
            if nome in pessoas_mapa:
                nova_lista_pessoas.append(pessoas_mapa[nome])
        
        tribos[tribo] = nova_lista_pessoas
        guardar_tribos(tribos)
        return jsonify({"status": "ok"})
    return jsonify({"status": "erro"}), 400

@app.route("/atividade/<ficheiro>")
def ver_atividade(ficheiro):
    """Exibe os detalhes de uma atividade registada."""
    cargos_disponiveis = carregar_cargos()
    caminho = os.path.join(DIRETORIO_PRESENCAS, ficheiro)
    dados = defaultdict(list)
    
    if os.path.exists(caminho):
        with open(caminho, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            
            for linha in reader:
                if 'Tribo' in linha and 'Elemento' in linha:
                    tribo_nome = linha['Tribo']
                    nome = linha['Elemento']
                    cargos_str = linha.get('Cargos', '')
                    cargos_list = [c.strip() for c in cargos_str.split(',')] if cargos_str else []
                    presente = linha['Presente']
                    dados[tribo_nome].append({
                        'nome': nome,
                        'presente': presente,
                        'cargos': cargos_list
                    })

    # Extrair as datas com regex
    match = re.search(r'(\d{4}-\d{2}-\d{2})_a_(\d{4}-\d{2}-\d{2})', ficheiro)
    if match:
        data_inicio_format = match.group(1)
        data_fim_format = match.group(2)
        data_display = data_inicio_format if data_inicio_format == data_fim_format else f"{data_inicio_format} - {data_fim_format}"
    else:
        data_display = "Data desconhecida"

    return render_template(
        "ver_atividade.html",
        ficheiro=ficheiro,
        dados=dados,
        data_display=data_display,
        cargos_disponiveis=cargos_disponiveis
    )


@app.route("/tesouraria", methods=["GET", "POST"])
def tesouraria():
    """Página de gestão da tesouraria do clã e das tribos."""
    tribos_disponiveis = list(carregar_tribos().keys())
    username = session.get('username')
    
    # Se o utilizador for "Peter Benenson", ajusta as tribos acessíveis
    if username == "Peter Benenson":
        tribo_peter = "Peter Benenson"
        if tribo_peter in tribos_disponiveis:
            tribos_disponiveis = [tribo_peter]
            #flash('Olá, Peter! Tem acesso restrito à tesouraria da sua tribo.', 'info')
        else:
            tribos_disponiveis = []  # Se a tribo não existir, ele não vê nada
            flash('A sua tribo de tesouraria não foi encontrada. Contacte um administrador.', 'danger')
    
    elif username == "Henri Dunant":
        tribo_henri = "Henri Dunant"
        if tribo_henri in tribos_disponiveis:
            tribos_disponiveis = [tribo_henri]
            #flash('Olá, Henri! Tem acesso restrito à tesouraria da sua tribo.', 'info')
        else:
            tribos_disponiveis = []  # Se a tribo não existir, ele não vê nada
            flash('A sua tribo de tesouraria não foi encontrada. Contacte um administrador.', 'danger')

    elif username == "Rainha D. Leonor":
        tribo_rainha = "Rainha D. Leonor"
        if tribo_rainha in tribos_disponiveis:
            tribos_disponiveis = [tribo_rainha]
            #flash('Olá, Rainha D. Leonor! Tem acesso restrito à tesouraria da sua tribo.', 'info')
        else:
            tribos_disponiveis = []  # Se a tribo não existir, ele não vê nada
            flash('A sua tribo de tesouraria não foi encontrada. Contacte um administrador.', 'danger')

    elif username == "Clan":
        tribos_disponiveis = []  # Remove todas as tribos, deixando apenas o Clan
        #flash('Olá, Clan! Tem acesso restrito à tesouraria do Clan.', 'info')

    entidade_ativa = "Clan"
    if request.method == "POST":
        acao = request.form.get('acao')
        entidade = request.form.get('entidade')
        
        # Garante que 'Peter' só pode editar a sua própria tribo
        if username == "Peter" and entidade != "Peter Benenson":
            flash("Não tem permissão para alterar esta folha de caixa.", "danger")
            return redirect(url_for('tesouraria'))
            
        folha_caixa = carregar_folha_caixa(entidade)
        
        if acao == 'adicionar':
            nova_transacao = {
                'data': request.form.get('data'),
                'descricao': request.form.get('descricao'),
                'tipo': request.form.get('tipo'),
                'valor': float(request.form.get('valor')),
                'comprovativo': None
            }
            
            if 'comprovativo' in request.files:
                file = request.files['comprovativo']
                if file.filename != '':
                    filename = secure_filename(file.filename)
                    caminho_ficheiro = os.path.join(DIRETORIO_UPLOADS, filename)
                    file.save(caminho_ficheiro)
                    nova_transacao['comprovativo'] = filename
            
            folha_caixa.append(nova_transacao)
        
        elif acao == 'remover':
            index = int(request.form.get('index'))
            if 0 <= index < len(folha_caixa):
                transacao_a_remover = folha_caixa[index]
                if 'comprovativo' in transacao_a_remover and transacao_a_remover['comprovativo']:
                    caminho_ficheiro = os.path.join(DIRETORIO_UPLOADS, transacao_a_remover['comprovativo'])
                    try:
                        os.remove(caminho_ficheiro)
                    except OSError as e:
                        print(f"Erro ao tentar remover o ficheiro: {e}")
                
                folha_caixa.pop(index)
        
        guardar_folha_caixa(entidade, folha_caixa)
        
        return redirect(url_for('tesouraria', entidade_ativa=entidade))

    # Garante que só carrega os dados das entidades permitidas
    folhas_caixa = {
        "Clan": sorted(carregar_folha_caixa("Clan"), key=lambda x: x['data'], reverse=True),
    }

    # Se o utilizador é "Clan", o código abaixo é executado, caso contrário, o código abaixo não é executado e o tribos_disponiveis está vazio
    if username == "Peter Benenson":
        tribos_disponiveis = ["Peter Benenson"]
    elif username == "Henri Dunant":
        tribos_disponiveis = ["Henri Dunant"]
    elif username == "Rainha D. Leonor":
        tribos_disponiveis = ["Rainha D. Leonor"]
    elif username == "Clan":
        tribos_disponiveis = list(carregar_tribos().keys())

    for tribo in tribos_disponiveis:
        folhas_caixa[tribo] = sorted(carregar_folha_caixa(tribo), key=lambda x: x['data'], reverse=True)

    entidade_ativa = request.args.get('entidade_ativa') or "Clan"
        
    return render_template("tesouraria.html", 
                        tribos=tribos_disponiveis, 
                        folhas_caixa=folhas_caixa,
                        entidade_ativa=entidade_ativa)

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    """Rota para servir ficheiros guardados no diretório de uploads."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/assiduidade", methods=["GET", "POST"])
def assiduidade():
    """Calcula e exibe a assiduidade por pessoa e tribo para um ano escutista."""
    ano_selecionado = request.form.get("ano_escotista")
    if ano_selecionado:
        # Recebe ano no formato "YYYY/YYYY+1", extrai apenas o ano de início
        ano_inicio = int(ano_selecionado.split('/')[0])
    else:
        # Padrão: ano escutista atual (Outubro do ano anterior a Setembro do ano atual)
        hoje = datetime.now()
        ano_inicio = hoje.year
        if hoje.month < 10:
            ano_inicio -= 1

    ano_fim = ano_inicio + 1
    data_inicio = datetime(ano_inicio, 10, 1)
    data_fim = datetime(ano_fim, 9, 30)

    # Processar os ficheiros de atividades
    assiduidade_por_tribo = defaultdict(lambda: defaultdict(lambda: {'presente': 0, 'total': 0}))
    atividades_do_ano = 0

    ficheiros = [f for f in os.listdir(DIRETORIO_PRESENCAS) if f.endswith(".csv")]
    for ficheiro in ficheiros:
        try:
            data_atividade = None
            partes = ficheiro.split('_')
            
            if len(partes) > 3:
                data_str = partes[3].strip()
                try:
                    data_atividade = datetime.strptime(data_str, "%Y-%m-%d")
                except ValueError:
                    # Se falhar, tenta outra posição
                    pass
            
            if data_atividade is None and len(partes) > 1:
                data_str = partes[1].strip()
                try:
                    data_atividade = datetime.strptime(data_str, "%Y-%m-%d")
                except ValueError:
                    # Se falhar, o ficheiro será ignorado no 'except' principal
                    pass
            
            if data_atividade is None:
                raise ValueError("Formato de data não reconhecido no nome do ficheiro.")

            if data_inicio <= data_atividade <= data_fim:
                atividades_do_ano += 1
                caminho = os.path.join(DIRETORIO_PRESENCAS, ficheiro)
                with open(caminho, newline="", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        tribo = row['Tribo']
                        elemento = row['Elemento']
                        presente = row['Presente']
                        
                        assiduidade_por_tribo[tribo][elemento]['total'] += 1
                        if presente == "Sim":
                            assiduidade_por_tribo[tribo][elemento]['presente'] += 1
        except Exception as e:
            print(f"Erro ao processar o ficheiro {ficheiro}: {e}")

    # Calcular as percentagens
    for tribo in assiduidade_por_tribo:
        for elemento in assiduidade_por_tribo[tribo]:
            dados = assiduidade_por_tribo[tribo][elemento]
            if dados['total'] > 0:
                dados['percentagem'] = (dados['presente'] / dados['total']) * 100
            else:
                dados['percentagem'] = 0

    # Obter anos escutistas disponíveis
    anos_disponiveis = set()
    for ficheiro in ficheiros:
        if len(ficheiro.split('_')) > 1:
            try:
                data_atividade = None
                partes = ficheiro.split('_')
                
                if len(partes) > 3:
                    data_str = partes[3].strip()
                    try:
                        data_atividade = datetime.strptime(data_str, "%Y-%m-%d")
                    except ValueError:
                        pass
                
                if data_atividade is None and len(partes) > 1:
                    data_str = partes[1].strip()
                    try:
                        data_atividade = datetime.strptime(data_str, "%Y-%m-%d")
                    except ValueError:
                        pass
                
                if data_atividade:
                    ano_inicio_ficheiro = data_atividade.year if data_atividade.month >= 10 else data_atividade.year - 1
                    anos_disponiveis.add(ano_inicio_ficheiro)
                
            except Exception:
                pass

    # Garante que o ano escutista atual aparece sempre
    hoje = datetime.now()
    ano_atual = hoje.year if hoje.month >= 10 else hoje.year - 1
    anos_disponiveis.add(ano_atual)

    # Ordena do mais recente para o mais antigo
    anos_disponiveis = sorted(list(anos_disponiveis), reverse=True)

    # Converte para formato "YYYY/YYYY+1"
    anos_formatados = [f"{ano}/{ano+1}" for ano in anos_disponiveis]

    return render_template(
        "assiduidade.html", 
        assiduidade_por_tribo=assiduidade_por_tribo,
        atividades_do_ano=atividades_do_ano,
        anos_disponiveis=anos_formatados,
        ano_selecionado=f"{ano_inicio}/{ano_inicio+1}"
    )


# --- Rota de Login ---

@app.route("/login", methods=["GET", "POST"])
def login():
    if 'username' in session and session['username'] in ['Chefe', 'Clan']:
        return redirect(url_for('index'))
        
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Permite o login do 'Chefe' e 'Clan'
        if username in ['Chefe', 'Clan']:
            utilizadores = carregar_utilizadores()
            stored_password_hash = utilizadores.get(username)
            
            if stored_password_hash and bcrypt.check_password_hash(stored_password_hash, password):
                session['username'] = username
                #flash('Login bem-sucedido!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Nome de utilizador ou palavra-passe inválidos.', 'danger')
                return render_template("login.html")
        else:
            flash('Não tem permissão de acesso.', 'danger')
            return render_template("login.html")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    #flash('Sessão terminada com sucesso.', 'info')
    return redirect(url_for('index'))

@app.route("/mudar_password", methods=["GET", "POST"])
def mudar_password():
    if session.get('username') not in ['Chefe', 'Clan']:
        flash("Não tem permissão para aceder a esta página.", "info")
        return redirect(url_for('login'))

    if request.method == "POST":
        password_atual = request.form.get("password_atual")
        nova_password = request.form.get("nova_password")
        confirmar_password = request.form.get("confirmar_password")
        
        username = session['username']
        utilizadores = carregar_utilizadores()
        stored_password_hash = utilizadores.get(username)

        if not stored_password_hash or not bcrypt.check_password_hash(stored_password_hash, password_atual):
            flash("A palavra-passe atual está incorreta.", "danger")
            return render_template("mudar_password.html")
        
        if nova_password != confirmar_password:
            flash("A nova palavra-passe e a confirmação não coincidem.", "danger")
            return render_template("mudar_password.html")

        if bcrypt.check_password_hash(stored_password_hash, nova_password):
            flash("A nova palavra-passe não pode ser igual à anterior.", "warning")
            return render_template("mudar_password.html")
            
        hashed_password = bcrypt.generate_password_hash(nova_password).decode('utf-8')
        utilizadores[username] = hashed_password
        guardar_utilizadores(utilizadores)
        
        flash("A sua palavra-passe foi alterada com sucesso!", "success")
        return redirect(url_for('index'))

    return render_template("mudar_password.html")

@app.route("/admin_register", methods=["GET", "POST"])
def admin_register():
    if session.get('username') != 'Chefe':
        flash('Não tem permissão para aceder a esta página.', 'danger')
        return redirect(url_for('index'))
    
    # O utilizador 'Chefe' não pode ser apagado
    # Apenas o utilizador 'Chefe' pode ser registado por ele
    utilizadores = carregar_utilizadores()
    
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        
        if not username or not password or not confirm_password:
            flash('Por favor, preencha todos os campos.', 'danger')
            return render_template("admin_register.html")
        
        if password != confirm_password:
            flash('As palavras-passe não correspondem. Por favor, tente novamente.', 'danger')
            return render_template("admin_register.html")
            
        if username in utilizadores:
            flash('Nome de utilizador já existe. Por favor, escolha outro.', 'danger')
            return render_template("admin_register.html")
            
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        utilizadores[username] = hashed_password
        guardar_utilizadores(utilizadores)
        
        flash(f'Utilizador "{username}" registado com sucesso!', 'success')
        return redirect(url_for('admin_register'))

    return render_template("admin_register.html")

@app.route("/material", methods=["GET", "POST"])
def material():
    """Página para gerir o material da farmácia."""
    material_itens = carregar_material()
    tribos_disponiveis = list(carregar_tribos().keys())

    if request.method == "POST":
        acao = request.form.get("acao")

        if acao == "adicionar_item":
            nome_item = request.form.get("nome_item")
            quantidade_str = request.form.get("quantidade")
            localizacao = request.form.get("localizacao")
            tribo_clan = request.form.get("tribo_clan")
            observacoes = request.form.get("observacoes", "")

            if not all([nome_item, quantidade_str, tribo_clan]):
                flash("Por favor, preencha todos os campos obrigatórios.", "danger")
                return redirect(url_for('material'))
            
            try:
                quantidade = int(quantidade_str)
            except (ValueError, TypeError):
                flash("A quantidade deve ser um número válido.", "danger")
                return redirect(url_for('material'))
            
            localizacao_normalizada = localizacao.strip().lower()

            item_existente = None
            for item in material_itens:
                if (item['nome'].lower() == nome_item.lower() and
                    item['localizacao'].strip().lower() == localizacao_normalizada and
                    item['tribo_clan'] == tribo_clan):
                    item_existente = item
                    break
            
            if item_existente:
                item_existente['quantidade'] += quantidade
            else:
                novo_item = {
                    "nome": nome_item,
                    "quantidade": quantidade,
                    "localizacao": localizacao,
                    "tribo_clan": tribo_clan,
                    "observacoes": observacoes
                }
                material_itens.append(novo_item)

            guardar_material(material_itens)
            flash("Item adicionado com sucesso.", "success")

            return redirect(url_for('material',
                                    filtro_nome=request.args.get('filtro_nome', ''),
                                    filtro_quantidade=request.args.get('filtro_quantidade', ''),
                                    filtro_localizacao=request.args.get('filtro_localizacao', ''),
                                    filtro_tribo_clan=request.args.get('filtro_tribo_clan', '')))

        elif acao == "remover_item":
            nome_item = request.form.get("nome_item")
            tribo_clan = request.form.get("tribo_clan")

            material_itens = [
                item for item in material_itens
                if not (item['nome'] == nome_item and item['tribo_clan'] == tribo_clan)
            ]

            guardar_material(material_itens)
            return jsonify({'status': 'success', 'message': 'Item removido com sucesso!'})

    # Lógica para filtrar e criar listas de opções para os dropdowns
    filtro_nome = request.args.get('filtro_nome', '').strip().lower()
    filtro_quantidade_str = request.args.get('filtro_quantidade', '').strip()
    filtro_localizacao = request.args.get('filtro_localizacao', '').strip().lower()
    filtro_tribo_clan = request.args.get('filtro_tribo_clan', '').strip()

    # Criação das listas de opções únicas
    opcoes_nome = sorted(list(set(item['nome'] for item in material_itens)))
    opcoes_quantidade = sorted(list(set(item['quantidade'] for item in material_itens)))
    opcoes_localizacao = sorted(list(set(item['localizacao'] for item in material_itens)))

    material_filtrado = material_itens

    if filtro_nome:
        material_filtrado = [item for item in material_filtrado if filtro_nome in item['nome'].lower()]

    if filtro_quantidade_str:
        try:
            filtro_quantidade = int(filtro_quantidade_str)
            material_filtrado = [item for item in material_filtrado if item['quantidade'] == filtro_quantidade]
        except (ValueError, TypeError):
            pass
            
    if filtro_localizacao:
        material_filtrado = [item for item in material_filtrado if filtro_localizacao in item['localizacao'].lower()]
        
    if filtro_tribo_clan:
        material_filtrado = [item for item in material_filtrado if item['tribo_clan'] == filtro_tribo_clan]

    material_filtrado = sorted(material_filtrado, key=lambda x: x['nome'].lower())

    return render_template("material.html",
                           material_filtrado=material_filtrado,
                           tribos_disponiveis=tribos_disponiveis,
                           filtro_nome=filtro_nome,
                           filtro_quantidade=filtro_quantidade_str,
                           filtro_localizacao=filtro_localizacao,
                           filtro_tribo_clan=filtro_tribo_clan,
                           opcoes_nome=opcoes_nome,
                           opcoes_quantidade=opcoes_quantidade,
                           opcoes_localizacao=opcoes_localizacao)


@app.route("/farmacia", methods=["GET", "POST"])
def farmacia():
    """Página para gerir o inventário da farmácia e as informações de saúde das pessoas."""
    farmacia_itens = carregar_farmacia()
    alergias = carregar_alergias()
    condicoes = carregar_condicoes()
    tribos = carregar_tribos()
    tribos_disponiveis = list(tribos.keys())

    # Lista de todas as pessoas existentes nas tribos
    pessoas_disponiveis = []
    for membros in tribos.values():
        for pessoa in membros:
            if isinstance(pessoa, dict) and "nome" in pessoa:
                pessoas_disponiveis.append(pessoa["nome"])
            else:
                pessoas_disponiveis.append(pessoa)

    if request.method == "POST":
        acao = request.form.get("acao")

        # ---------- ADICIONAR ITEM ----------
        if acao == "adicionar_item":
            nome_item = request.form.get("nome_item")
            quantidade_str = request.form.get("quantidade")
            localizacao = request.form.get("localizacao")
            tribo_clan = request.form.get("tribo_clan")
            observacoes = request.form.get("observacoes", "")

            if not all([nome_item, quantidade_str, tribo_clan]):
                flash("Por favor, preencha todos os campos obrigatórios.", "danger")
                return redirect(url_for('farmacia'))

            try:
                quantidade = int(quantidade_str)
            except (ValueError, TypeError):
                flash("A quantidade deve ser um número válido.", "danger")
                return redirect(url_for('farmacia'))

            localizacao_normalizada = localizacao.strip().lower() if localizacao else ""

            # Verificar se já existe
            item_existente = None
            for item in farmacia_itens:
                if (item['nome'].lower() == nome_item.lower() and
                    item['localizacao'].strip().lower() == localizacao_normalizada and
                    item['tribo_clan'] == tribo_clan):
                    item_existente = item
                    break

            if item_existente:
                item_existente['quantidade'] += quantidade
            else:
                novo_item = {
                    "nome": nome_item,
                    "quantidade": quantidade,
                    "localizacao": localizacao,
                    "tribo_clan": tribo_clan,
                    "observacoes": observacoes
                }
                farmacia_itens.append(novo_item)

            guardar_farmacia(farmacia_itens)
            flash("Item adicionado com sucesso.", "success")
            return redirect(url_for('farmacia'))

        # ---------- REMOVER ITEM ----------
        elif acao == "remover_item":
            nome_item = request.form.get("nome_item")
            tribo_clan = request.form.get("tribo_clan")
            farmacia_itens = [item for item in farmacia_itens if not (item['nome'] == nome_item and item['tribo_clan'] == tribo_clan)]
            guardar_farmacia(farmacia_itens)
            return jsonify({'status': 'success', 'message': 'Item removido com sucesso!'})

        # ---------- GUARDAR INFORMAÇÕES DE SAÚDE ----------
        elif acao == "guardar_saude":
            for pessoa in pessoas_disponiveis:
                alergia_raw = request.form.get(f"alergia-{pessoa}", "").strip()
                condicao_raw = request.form.get(f"condicao-{pessoa}", "").strip()

                if alergia_raw:
                    alergias[pessoa] = ",".join([linha.strip() for linha in alergia_raw.splitlines() if linha.strip()])
                else:
                    alergias.pop(pessoa, None)

                if condicao_raw:
                    condicoes[pessoa] = ",".join([linha.strip() for linha in condicao_raw.splitlines() if linha.strip()])
                else:
                    condicoes.pop(pessoa, None)

            guardar_alergias(alergias)
            guardar_condicoes(condicoes)
            flash("Informações de saúde atualizadas com sucesso.", "success")
            return redirect(url_for("farmacia"))

    # ---------- FILTROS ----------
    filtro_nome = request.args.get('filtro_nome', '').strip().lower()
    filtro_quantidade_str = request.args.get('filtro_quantidade', '').strip()
    filtro_localizacao = request.args.get('filtro_localizacao', '').strip().lower()
    filtro_tribo_clan = request.args.get('filtro_tribo_clan', '').strip()

    opcoes_nome = sorted(list(set(item['nome'] for item in farmacia_itens)))
    opcoes_quantidade = sorted(list(set(item['quantidade'] for item in farmacia_itens)))
    opcoes_localizacao = sorted(list(set(item['localizacao'] for item in farmacia_itens)))

    farmacia_filtrado = farmacia_itens
    if filtro_nome:
        farmacia_filtrado = [item for item in farmacia_filtrado if filtro_nome in item['nome'].lower()]
    if filtro_quantidade_str:
        try:
            filtro_quantidade = int(filtro_quantidade_str)
            farmacia_filtrado = [item for item in farmacia_filtrado if item['quantidade'] == filtro_quantidade]
        except (ValueError, TypeError):
            pass
    if filtro_localizacao:
        farmacia_filtrado = [item for item in farmacia_filtrado if filtro_localizacao in item['localizacao'].lower()]
    if filtro_tribo_clan:
        farmacia_filtrado = [item for item in farmacia_filtrado if item['tribo_clan'] == filtro_tribo_clan]

    farmacia_filtrado = sorted(farmacia_filtrado, key=lambda x: x['nome'].lower())

    return render_template(
        "farmacia.html",
        farmacia_filtrado=farmacia_filtrado,
        tribos_disponiveis=tribos_disponiveis,
        pessoas_disponiveis=pessoas_disponiveis,
        filtro_nome=filtro_nome,
        filtro_quantidade=filtro_quantidade_str,
        filtro_localizacao=filtro_localizacao,
        filtro_tribo_clan=filtro_tribo_clan,
        opcoes_nome=opcoes_nome,
        opcoes_quantidade=opcoes_quantidade,
        opcoes_localizacao=opcoes_localizacao,
        alergias=alergias,
        condicoes=condicoes
    )




@app.route("/cozinha", methods=["GET", "POST"])
def cozinha():
    """Página para gerir o inventário e receitas da cozinha."""
    
    inventario = carregar_inventario_cozinha()
    receitas = carregar_receitas()
    tribos_disponiveis = list(carregar_tribos().keys()) if 'carregar_tribos' in globals() else []

    opcoes_unidade = ["unidades", "kg", "g", "l", "ml", "pacote", "rolo", "a gosto"]
    opcoes_categoria = ["Cereais", "Laticínios", "Carne", "Peixe", "Frutas", "Vegetais", "Especiarias", "Bebidas", "Outros"]
    opcoes_dificuldade = ["Fácil", "Médio", "Difícil"]

    if request.method == "POST":
        acao = request.form.get("acao")

        # --- ARQUIVAR NOVA RECEITA ---
        if acao == "adicionar_receita":
            nome_receita = request.form.get("nome_receita")
            ingredientes_raw = request.form.get("ingredientes_raw")
            instrucoes = request.form.get("instrucoes")
            tempo_preparacao = request.form.get("tempo_preparacao")
            dificuldade = request.form.get("dificuldade")
            porcoes_base = request.form.get("porcoes_base")
            
            # Validação básica
            if not nome_receita:
                flash("O nome da receita é obrigatório.", "danger")
                return redirect(url_for('cozinha'))

            link_ficheiro = None
            
            # Lógica para ficheiro/comprovativo de receita (assume 'os.path', 'DIRETORIO_RECEITAS', 'secure_filename' e 'url_for')
            if 'comprovativo_receita' in request.files:
                file = request.files['comprovativo_receita']
                if file.filename != '':
                    if not os.path.exists(DIRETORIO_RECEITAS):
                        os.makedirs(DIRETORIO_RECEITAS)
                        
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(DIRETORIO_RECEITAS, filename)
                    file.save(filepath)
                    link_ficheiro = url_for('serve_receita', filename=filename)

            # Se houver ficheiro, a receita é baseada em ficheiro
            if link_ficheiro:
                nova_receita = {
                    "nome": nome_receita.strip(),
                    "link_ficheiro": link_ficheiro
                }
            # Caso contrário, é uma receita manual
            else:
                # Processar os ingredientes do texto
                ingredientes_processados = []
                for linha in ingredientes_raw.splitlines():
                    if linha.strip():
                        ingredientes_processados.append(linha.strip())
                        
                # Validação de campos manuais, se não houver ficheiro
                if not (ingredientes_processados and instrucoes):
                    flash("Para receitas manuais, preencha Ingredientes e Instruções.", "danger")
                    return redirect(url_for('cozinha'))

                nova_receita = {
                    "nome": nome_receita.strip(),
                    "ingredientes": ingredientes_processados,
                    "instrucoes": instrucoes,
                    "tempo_preparacao": tempo_preparacao,
                    "dificuldade": dificuldade,
                    "porcoes_base": porcoes_base
                }
            
            # Adicionar e guardar
            receitas.append(nova_receita)
            guardar_receitas(receitas)
            
            flash(f"Receita '{nome_receita}' arquivada com sucesso!", "success")
            return redirect(url_for('cozinha'))
            
        # --- GESTÃO DE STOCK: ADICIONAR/ATUALIZAR ---
        if acao == "adicionar_item_cozinha":
            guardar_inventario_cozinha(inventario)
            return redirect(url_for('cozinha'))

        # Se a ação não for reconhecida, redireciona sem erro grave.
        return redirect(url_for('cozinha'))

    filtro_categoria = request.args.get('categoria', 'Todos') 
    
    inventario_ordenado = sorted(inventario, key=lambda x: x['nome'])
    
    inventario_filtrado = []
    if filtro_categoria == 'Todos':
        inventario_filtrado = inventario_ordenado
    else:
        # Filtra pelo nome da categoria que é passado no URL
        inventario_filtrado = [item for item in inventario_ordenado if item.get('categoria') == filtro_categoria]

    receitas_ordenadas = sorted(receitas, key=lambda x: x['nome'])
    
    return render_template("cozinha.html",
                           inventario=inventario_filtrado, # Enviar a lista FILTRADA
                           receitas=receitas_ordenadas,
                           opcoes_unidade=opcoes_unidade,
                           opcoes_categoria=opcoes_categoria,
                           opcoes_dificuldade=opcoes_dificuldade,
                           tribos_disponiveis=tribos_disponiveis,
                           filtro_categoria_atual=filtro_categoria) # Enviar o filtro atual

@app.route('/uploads/cozinha/<path:filename>')
def serve_upload_cozinha(filename):
    """Serve os ficheiros de comprovativo de stock."""
    # Serve os ficheiros da pasta 'uploads/cozinha'
    return send_from_directory(DIRETORIO_UPLOADS_COZINHA, filename)


@app.route('/receitas/<path:filename>')
def serve_receita(filename):
    return send_from_directory(DIRETORIO_RECEITAS, filename)


@app.route("/cozinha/receita/<string:nome_receita>", methods=["GET"])
def ver_receita(nome_receita):
    """Exibe os detalhes de uma receita específica com a opção de alterar porções."""
    receitas = carregar_receitas()
    
    receita = next((r for r in receitas if r['nome'] == nome_receita), None)

    if not receita:
        flash("Receita não encontrada.", "danger")
        return redirect(url_for('cozinha'))
        
    return render_template("ver_receita.html", receita=receita)


@app.route("/eliminar_receita", methods=["POST"])
def eliminar_receita():
    """Elimina uma receita, incluindo o ficheiro associado se existir."""
    nome_receita = request.form.get("nome_receita")
    link_ficheiro = request.form.get("link_ficheiro")

    if not nome_receita:
        flash("Nome da receita não fornecido.", "danger")
        return redirect(url_for('cozinha'))

    receitas = carregar_receitas()

    if link_ficheiro:
        caminho_ficheiro = os.path.join(DIRETORIO_RECEITAS, os.path.basename(link_ficheiro))
        if os.path.exists(caminho_ficheiro):
            try:
                os.remove(caminho_ficheiro)
            except OSError as e:
                flash(f"Erro ao eliminar o ficheiro: {e}", "warning")

    receitas = [r for r in receitas if not (r['nome'] == nome_receita and r.get('link_ficheiro', '') == (link_ficheiro if link_ficheiro else ''))]
    guardar_receitas(receitas)

    flash(f"Receita '{nome_receita}' eliminada com sucesso.", "success")
    return redirect(url_for('cozinha'))

@app.route("/eliminar_item_inventario", methods=["POST"])
def eliminar_item_inventario():
    """Elimina um item específico do inventário, incluindo o ficheiro de comprovativo associado, se existir."""
    
    # Obter dados do formulário (nome e unidade são a chave única)
    nome_item_raw = request.form.get("nome_item", "").strip()
    unidade_item_raw = request.form.get("unidade_item", "").strip()
    
    # Normalizar para comparação com o JSON (tal como na lógica de remoção em /cozinha)
    nome_item_normalizado = nome_item_raw.lower()
    unidade_item_normalizada = unidade_item_raw.lower()

    if not nome_item_normalizado or not unidade_item_normalizada:
        flash("Nome ou unidade do item não fornecidos para eliminação.", "danger")
        return redirect(url_for('cozinha'))

    inventario = carregar_inventario_cozinha()
    item_removido = None

    # 2. Encontrar o item a remover
    item_a_remover = next((i for i in inventario 
                             if i['nome'].strip().lower() == nome_item_normalizado and 
                                i['unidade'].strip().lower() == unidade_item_normalizada), None)

    if item_a_remover:
        item_removido = item_a_remover.get('nome') # Guarda o nome original para a mensagem Flash
        caminho_comprovativo = item_a_remover.get('comprovativo')

        # 3. Lógica para remover o ficheiro do comprovativo, se existir
        if caminho_comprovativo:
            try:
                filename = os.path.basename(caminho_comprovativo)
                filepath = os.path.join(DIRETORIO_UPLOADS_COZINHA, filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                # Não bloqueia a remoção do registo, mas alerta para o erro do ficheiro
                print(f"Erro ao eliminar o comprovativo de stock ({caminho_comprovativo}): {e}")
                flash(f"Item eliminado, mas erro ao remover o comprovativo. Por favor, verifique o servidor.", "warning")

        # 4. Atualizar inventário (criando uma nova lista sem o item correspondente)
        inventario = [i for i in inventario 
                      if not (i['nome'].strip().lower() == nome_item_normalizado and 
                              i['unidade'].strip().lower() == unidade_item_normalizada)]
        guardar_inventario_cozinha(inventario)
        
        #flash(f"Item '{item_removido}' (Unidade: {unidade_item_raw}) eliminado com sucesso do inventário.", "success")
    else:
        flash(f"Item '{nome_item_raw}' (Unidade: {unidade_item_raw}) não encontrado no inventário.", "danger")

    return redirect(url_for('cozinha'))


@app.route("/progresso")
def progresso():
    """Renderiza a página com a tabela de progresso completa."""
    pessoas = carregar_nomes()
    progresso_por_pessoa = carregar_progresso()
    progresso_modelo = carregar_progresso_modelo()

    print("Conteúdo de progresso_modelo.json carregado:", progresso_modelo)

    areas = []
    trilhos = {}

    if progresso_modelo:
        areas = list(progresso_modelo.keys())
        for area_nome, trilhos_area in progresso_modelo.items():
            trilhos[area_nome] = {}
            for trilho_nome, objetivos_trilho in trilhos_area.items():
                if isinstance(objetivos_trilho, dict):
                    print(f"Área: {area_nome}, Trilho: {trilho_nome}, Objetivos: {list(objetivos_trilho.keys())}")
                    trilhos[area_nome][trilho_nome] = list(objetivos_trilho.keys())
                else:
                    trilhos[area_nome][trilho_nome] = []

    dados_para_tabela = {}
    for nome_pessoa in pessoas:
        dados_pessoa = progresso_por_pessoa.get(nome_pessoa, progresso_modelo)
        dados_para_tabela[nome_pessoa] = dados_pessoa
    
    return render_template(
        "progresso.html",
        progresso=dados_para_tabela,
        areas=areas,
        trilhos=trilhos,
        progresso_modelo=progresso_modelo
    )

@app.route("/atualizar_objetivo", methods=["POST"])
def atualizar_objetivo():
    # Adicionando a verificação de permissão
    if session.get('username') != 'Chefe':
        return jsonify({"status": "error", "message": "Apenas o Chefe pode alterar o progresso."}), 403

    data = request.get_json()
    nome = data["nome"]
    area = data["area"]
    trilho = data["trilho"]
    objetivo = data["objetivo"]
    novo_estado = data["estado"]  # Recebe o novo estado do front-end

    progresso_raw = carregar_progresso()
    progresso_modelo = carregar_progresso_modelo()

    # Garante que cada pessoa tem a sua própria cópia do modelo
    if nome not in progresso_raw:
        progresso_raw[nome] = copy.deepcopy(progresso_modelo)
    
    # Atualizar o estado do objetivo específico
    progresso_raw[nome][area][trilho][objetivo] = novo_estado

    # Guardar alteração
    guardar_progresso(progresso_raw)

    # Calcular o nível atualizado
    dados_pessoa_bool = calcular_progresso_bool_do_dicionario(progresso_raw[nome])
    nivel = calcular_nivel(dados_pessoa_bool, progresso_modelo)

    return jsonify({
        "status": "ok",
        "novo_estado": novo_estado,
        "nivel": nivel
    })


@app.route("/secretaria", methods=["GET", "POST"])
def secretaria():
    
    if request.method == "POST":
        
        # --- Lógica de Upload de ATAS ---
        if 'ata' in request.files:
            data_ata = request.form.get('dataAta')
            file = request.files['ata']

            if file.filename == '' or not data_ata:
                flash("Nenhum arquivo ou data de Ata selecionados.", "danger")
                return redirect(request.url)
            
            # Garante que o ficheiro não é "vazio"
            if file:
                filename = secure_filename(file.filename)
                nome_com_data = f"{data_ata}_{filename}"
                
                try:
                    file.save(os.path.join(DIRETORIO_ATAS, nome_com_data))
                    flash("Ata arquivada com sucesso!", "success")
                except Exception as e:
                    flash(f"Erro ao arquivar Ata: {e}", "danger")

        # --- Lógica de Upload de OUTROS DOCUMENTOS ---
        elif 'documento' in request.files:
            file = request.files['documento']

            if file.filename == '':
                flash("Nenhum arquivo de Documento selecionado.", "danger")
                return redirect(request.url)
            
            # Não é necessário data para outros documentos, mas vamos usar um timestamp para ordenação
            if file:
                filename = secure_filename(file.filename)
                
                # Usa um timestamp para garantir nomes únicos e ordenação por upload (opcional)
                timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
                nome_com_timestamp = f"{timestamp}_{filename}"
                
                try:
                    file.save(os.path.join(DIRETORIO_OUTROS_DOCS, nome_com_timestamp))
                    flash("Documento arquivado com sucesso!", "success")
                except Exception as e:
                    flash(f"Erro ao arquivar Documento: {e}", "danger")

        return redirect(url_for('secretaria'))


    # --- Processamento de ATAS (GET) ---
    atas = []
    for nome_ficheiro in os.listdir(DIRETORIO_ATAS):
        try:
            partes = nome_ficheiro.split('_', 1)
            data_str = partes[0]
            nome_original = partes[1]
            data_ata = datetime.strptime(data_str, "%Y-%m-%d")
            atas.append({
                'nome_completo': nome_ficheiro,
                'nome_original': nome_original,
                'data': data_ata
            })
        except (ValueError, IndexError):
            atas.append({
                'nome_completo': nome_ficheiro,
                'nome_original': nome_ficheiro,
                'data': None
            })
    atas.sort(key=lambda x: x['data'] if x['data'] else datetime.min, reverse=True)
    
    
    # --- Processamento de OUTROS DOCUMENTOS (GET) ---
    outros_documentos = []
    for nome_ficheiro in os.listdir(DIRETORIO_OUTROS_DOCS):
        try:
            # Apanha o timestamp no início do nome (usando o formato YYYY-MM-DD_HHMMSS)
            partes = nome_ficheiro.split('_', 2) # Divide em 3 partes: Data, Hora, Resto
            timestamp_str = f"{partes[0]}_{partes[1]}"
            nome_original = partes[2]
            data_doc = datetime.strptime(timestamp_str, "%Y-%m-%d_%H%M%S")
            
            outros_documentos.append({
                'nome_completo': nome_ficheiro,
                'nome_original': nome_original,
                'data': data_doc
            })
        except (ValueError, IndexError):
             # Lida com ficheiros que não seguem o padrão
            outros_documentos.append({
                'nome_completo': nome_ficheiro,
                'nome_original': nome_ficheiro,
                'data': None
            })
            
    # Ordena pelo timestamp de upload (mais recente primeiro)
    outros_documentos.sort(key=lambda x: x['data'] if x['data'] else datetime.min, reverse=True)

    return render_template("secretaria.html", atas=atas, outros_documentos=outros_documentos)

# --- NOVAS ROTAS ---

@app.route('/outros_documentos/<path:filename>')
def serve_outro_doc(filename):
    # Serve os ficheiros da pasta 'outros_documentos'
    return send_from_directory(DIRETORIO_OUTROS_DOCS, filename)


@app.route("/eliminar_outro_doc", methods=["POST"])
def eliminar_outro_doc():
    # Verifica a permissão do utilizador
    if session.get('username') not in ['Chefe', 'Clan']:
        flash("Não tem permissão para realizar esta ação.", "danger")
        return redirect(url_for('login'))

    nome_completo_doc = request.form.get("nome_completo_doc")
    if not nome_completo_doc:
        flash("Nome do ficheiro não fornecido.", "danger")
        return redirect(url_for('secretaria'))
    
    caminho_ficheiro = os.path.join(DIRETORIO_OUTROS_DOCS, nome_completo_doc)

    try:
        if os.path.exists(caminho_ficheiro):
            os.remove(caminho_ficheiro)
            flash(f"Documento '{nome_completo_doc}' eliminado com sucesso.", "success")
        else:
            flash("O ficheiro não foi encontrado.", "danger")
    except Exception as e:
        flash(f"Ocorreu um erro ao tentar eliminar o documento: {e}", "danger")

    return redirect(url_for('secretaria'))

@app.route('/atas/<path:filename>')
def serve_ata(filename):
    # Serve os ficheiros da pasta 'atas'
    return send_from_directory(DIRETORIO_ATAS, filename)

@app.route("/eliminar_ata", methods=["POST"])
def eliminar_ata():
    # Verifica a permissão do utilizador
    if session.get('username') not in ['Chefe', 'Clan']:
        flash("Não tem permissão para realizar esta ação.", "danger")
        return redirect(url_for('login'))

    nome_completo_ata = request.form.get("nome_completo_ata")
    if not nome_completo_ata:
        flash("Nome do ficheiro não fornecido.", "danger")
        return redirect(url_for('secretaria'))
    
    caminho_ficheiro = os.path.join(DIRETORIO_ATAS, nome_completo_ata)

    try:
        # Verifica se o ficheiro existe antes de tentar eliminá-lo
        if os.path.exists(caminho_ficheiro):
            os.remove(caminho_ficheiro)
            flash(f"Ata '{nome_completo_ata}' eliminada com sucesso.", "success")
        else:
            flash("O ficheiro não foi encontrado.", "danger")
    except Exception as e:
        flash(f"Ocorreu um erro ao tentar eliminar a ata: {e}", "danger")

    return redirect(url_for('secretaria'))

# Rota para a página do calendário, acessível por todos os utilizadores
@app.route("/atividades_calendario")
def atividades_calendario():
    pode_editar = session.get('username') in ['Chefe', 'Clan']
    return render_template("atividades_calendario.html", pode_editar=pode_editar)

# Rota para a API do calendário
@app.route("/api/atividades", methods=["GET", "POST"])
def api_atividades():
    cores_por_tipo = {
        'Clan': '#ff0000', 'Agrupamento': '#0000ff', 'Núcleo': '#ffff00',
        'Região': '#800080', 'Nacional': '#008000', 'Internacional': '#ffc0cb'
    }

    if request.method == "POST":
        # Protege a rota de adição de atividades
        if session.get('username') not in ['Chefe', 'Clan']:
            return jsonify({"error": "Não tem permissão para realizar esta ação."}), 403

        data = request.get_json()
        
        required_fields = ['title', 'start', 'type']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Dados incompletos. Faltam um ou mais campos."}), 400

        atividades = carregar_atividades_calendario()
        
        nova_atividade = {
            'id': str(uuid.uuid4()),
            'title': data['title'],
            'start': data['start'],
            'type': data['type'],
            'details': data.get('details', ''),
            'allDay': data.get('allDay', False)
        }
        
        if not nova_atividade['allDay']:
            if 'end' not in data:
                return jsonify({"error": "Dados incompletos. 'end' em falta para atividade não 'allDay'."}), 400
            nova_atividade['end'] = data['end']
        else:
            end_date = datetime.strptime(nova_atividade['start'], '%Y-%m-%d') + timedelta(days=1)
            nova_atividade['end'] = end_date.strftime('%Y-%m-%d')

        atividades.append(nova_atividade)
        guardar_atividades_calendario(atividades)
        
        nova_atividade['color'] = cores_por_tipo.get(nova_atividade['type'], '#000000')
        
        return jsonify(nova_atividade), 201
        
    elif request.method == "GET":
        # Permite que qualquer um aceda aos dados das atividades para visualização
        atividades = carregar_atividades_calendario()
        eventos = []
        for atv in atividades:
            evento = {
                'id': atv['id'], 
                'title': atv['title'], 
                'start': atv['start'],
                'end': atv.get('end'),
                'color': cores_por_tipo.get(atv['type'], '#000000'),
                'type': atv['type'],
                'details': atv.get('details', ''),
                'allDay': atv.get('allDay', False)
            }
            eventos.append(evento)
        return jsonify(eventos)

# Rota para editar uma atividade existente
@app.route("/api/atividades/<id>", methods=["PUT"])
def api_editar_atividade(id):
    # Protege a rota de edição de atividades
    if session.get('username') not in ['Chefe', 'Clan']:
        return jsonify({"error": "Não tem permissão para realizar esta ação."}), 403

    cores_por_tipo = {
        'Clan': '#ff0000', 'Agrupamento': '#0000ff', 'Núcleo': '#ffff00',
        'Região': '#800080', 'Nacional': '#008000', 'Internacional': '#ffc0cb'
    }

    try:
        data = request.get_json()
        atividades = carregar_atividades_calendario()
        atividade_encontrada = False
        
        for atv in atividades:
            if atv['id'] == id:
                atv['title'] = data.get('title', atv['title'])
                atv['start'] = data.get('start', atv['start'])
                atv['type'] = data.get('type', atv['type'])
                atv['details'] = data.get('details', atv['details'])
                atv['allDay'] = data.get('allDay', atv['allDay'])
                
                if not atv['allDay']:
                    atv['end'] = data.get('end')
                else:
                    end_date = datetime.strptime(atv['start'], '%Y-%m-%d') + timedelta(days=1)
                    atv['end'] = end_date.strftime('%Y-%m-%d')

                atividade_encontrada = True
                break
        
        if not atividade_encontrada:
            return jsonify({"error": "Atividade não encontrada."}), 404
        
        guardar_atividades_calendario(atividades)
        
        atv_atualizada = next(atv for atv in atividades if atv['id'] == id)
        atv_atualizada['color'] = cores_por_tipo.get(atv_atualizada['type'], '#000000')
        
        return jsonify(atv_atualizada), 200

    except Exception as e:
        print(f"Erro ao editar a atividade: {e}")
        return jsonify({"error": f"Erro interno do servidor: {e}"}), 500
        
# Rota para eliminar uma atividade
@app.route("/api/atividades/<id>", methods=["DELETE"])
def api_eliminar_atividade(id):
    # Protege a rota de eliminação de atividades
    if session.get('username') not in ['Chefe', 'Clan']:
        return jsonify({"error": "Não tem permissão para realizar esta ação."}), 403

    try:
        atividades = carregar_atividades_calendario()
        atividades_originais_count = len(atividades)
        atividades = [atv for atv in atividades if atv['id'] != id]
        
        if len(atividades) == atividades_originais_count:
            return jsonify({"error": "Atividade não encontrada."}), 404
            
        guardar_atividades_calendario(atividades)
        return jsonify({"message": "Atividade eliminada com sucesso!"}), 200
        
    except Exception as e:
        print(f"Erro no servidor ao eliminar a atividade: {e}")
        return jsonify({"error": f"Erro interno do servidor: {e}"}), 500
    




if __name__ == '__main__':
    # Obtém o número da porta da variável de ambiente,
    # caso não exista, usa a porta 5000 por defeito.
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)