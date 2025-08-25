from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, session, flash
import csv, os, re, json
from collections import defaultdict
from werkzeug.utils import secure_filename
from datetime import datetime
from flask_bcrypt import Bcrypt

app = Flask(__name__)
bcrypt = Bcrypt(app)
app.config['SECRET_KEY'] = 'uma_chave_segura_para_as_sessoes'  # Mude isto para uma chave aleatória e forte

# Diretórios para guardar os ficheiros
DIRETORIO_PRESENCAS = "registos"
DIRETORIO_TESOURARIA = "tesouraria"
DIRETORIO_UPLOADS = "uploads" 
os.makedirs(DIRETORIO_PRESENCAS, exist_ok=True)
os.makedirs(DIRETORIO_TESOURARIA, exist_ok=True)
os.makedirs(DIRETORIO_UPLOADS, exist_ok=True)

# Ficheiros JSON para guardar os dados
FICHEIRO_TRIBOS = "tribos.json"
FICHEIRO_CARGOS = "cargos.json"
FICHEIRO_UTILIZADORES = "utilizadores.json"
FICHEIRO_MATERIAL = "material.json"
FICHEIRO_FARMACIA = "farmacia.json"

# Adicionar a pasta de uploads à configuração da aplicação
app.config['UPLOAD_FOLDER'] = DIRETORIO_UPLOADS

# --- FUNÇÕES AUXILIARES ---
def carregar_tribos():
    """Carrega as tribos do ficheiro JSON."""
    if os.path.exists(FICHEIRO_TRIBOS):
        with open(FICHEIRO_TRIBOS, encoding="utf-8") as f:
            return json.load(f)
    return {}

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
    """Limpa uma string para ser usada como nome de ficheiro seguro."""
    nome_limpo = re.sub(r'[^A-Za-z0-9áéíóúãõàèùçÁÉÍÓÚÀÈÙÇ_\-@ ]', '_', nome)
    return nome_limpo

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

def guardar_material(material):
    """Guarda o material no ficheiro JSON."""
    with open(FICHEIRO_MATERIAL, "w", encoding="utf-8") as f:
        json.dump(material, f, indent=4, ensure_ascii=False)

# --- Lógica de Proteção de Rotas ---
@app.before_request
def require_login():
    # Rotas que não precisam de login
    public_routes = ['index', 'login', 'static', 'assiduidade', 'atividades', 'ver_atividade']
    if request.endpoint not in public_routes and 'username' not in session:
        flash('Por favor, faça login para aceder a esta página.', 'info')
        return redirect(url_for('login'))

# --- ROTAS PRINCIPAIS ---
@app.route("/", methods=["GET", "POST"])
def index():
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
    return render_template("index.html", hoje=hoje, tribos=tribos)

@app.route("/atividades")
def atividades():
    """Exibe a lista de atividades registadas."""
    ficheiros = [f for f in os.listdir(DIRETORIO_PRESENCAS) if f.endswith(".csv")]
    atividades_agrupadas = defaultdict(list)

    for ficheiro in ficheiros:
        data_inicio = ficheiro.split('_')[1]
        mes_ano = data_inicio[:7]
        atividades_agrupadas[mes_ano].append(ficheiro)

    meses_ordenados = sorted(atividades_agrupadas.keys(), reverse=True)
    for mes in meses_ordenados:
        atividades_agrupadas[mes].sort(reverse=True)

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

            # 1. Encontrar a pessoa a mover na tribo original
            pessoa_movida = None
            if original_tribo in tribos:
                for p in tribos[original_tribo]:
                    if p['nome'] == nome_pessoa:
                        pessoa_movida = p
                        tribos[original_tribo].remove(p)
                        break

            if not pessoa_movida:
                return jsonify({'status': 'error', 'message': 'Pessoa não encontrada na tribo original'}), 400

            # 2. Adicionar a pessoa à nova tribo na ordem correta
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
                    dados[tribo_nome].append({'nome': nome, 'presente': presente, 'cargos': cargos_list})

    partes_ficheiro = ficheiro.split('_')
    data_inicio_format = partes_ficheiro[1]
    data_fim_format = partes_ficheiro[3].replace('.csv', '')
    data_display = data_inicio_format if data_inicio_format == data_fim_format else f"{data_inicio_format} - {data_fim_format}"

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
            flash('Olá, Peter! Tem acesso restrito à tesouraria da sua tribo.', 'info')
        else:
            tribos_disponiveis = []  # Se a tribo não existir, ele não vê nada
            flash('A sua tribo de tesouraria não foi encontrada. Contacte um administrador.', 'danger')
    
    elif username == "Henri Dunant":
        tribo_henri = "Henri Dunant"
        if tribo_henri in tribos_disponiveis:
            tribos_disponiveis = [tribo_henri]
            flash('Olá, Henri! Tem acesso restrito à tesouraria da sua tribo.', 'info')
        else:
            tribos_disponiveis = []  # Se a tribo não existir, ele não vê nada
            flash('A sua tribo de tesouraria não foi encontrada. Contacte um administrador.', 'danger')

    elif username == "Rainha D. Leonor":
        tribo_rainha = "Rainha D. Leonor"
        if tribo_rainha in tribos_disponiveis:
            tribos_disponiveis = [tribo_rainha]
            flash('Olá, Rainha D. Leonor! Tem acesso restrito à tesouraria da sua tribo.', 'info')
        else:
            tribos_disponiveis = []  # Se a tribo não existir, ele não vê nada
            flash('A sua tribo de tesouraria não foi encontrada. Contacte um administrador.', 'danger')

    elif username == "Clan":
        tribos_disponiveis = []  # Remove todas as tribos, deixando apenas o Clan
        flash('Olá, Clan! Tem acesso restrito à tesouraria do Clan.', 'info')

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
    if not ano_selecionado:
        # Padrão: ano escutista atual (Outubro do ano anterior a Setembro do ano atual)
        hoje = datetime.now()
        ano_selecionado = hoje.year
        if hoje.month < 10:
            ano_selecionado -= 1
        ano_selecionado = str(ano_selecionado)

    # Definir o intervalo do ano escutista
    ano_inicio = int(ano_selecionado)
    ano_fim = ano_inicio + 1
    data_inicio = datetime(ano_inicio, 10, 1)
    data_fim = datetime(ano_fim, 9, 30)

    # Processar os ficheiros de atividades
    assiduidade_por_tribo = defaultdict(lambda: defaultdict(lambda: {'presente': 0, 'total': 0}))
    atividades_do_ano = 0

    ficheiros = [f for f in os.listdir(DIRETORIO_PRESENCAS) if f.endswith(".csv")]
    for ficheiro in ficheiros:
        try:
            data_str = ficheiro.split('_')[1]
            data_atividade = datetime.strptime(data_str, "%Y-%m-%d")

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

    # Obter anos escutistas para o seletor
    anos_disponiveis = set()
    for ficheiro in os.listdir(DIRETORIO_PRESENCAS):
        if len(ficheiro.split('_')) > 1:
            try:
                data_str = ficheiro.split('_')[1]
                data_atividade = datetime.strptime(data_str, "%Y-%m-%d")
                ano_escotista = data_atividade.year
                if data_atividade.month >= 10:
                    anos_disponiveis.add(str(ano_escotista))
                else:
                    anos_disponiveis.add(str(ano_escotista - 1))
            except Exception:
                pass
    
    anos_disponiveis = sorted(list(anos_disponiveis), reverse=True)

    return render_template("assiduidade.html", 
                           assiduidade_por_tribo=assiduidade_por_tribo,
                           atividades_do_ano=atividades_do_ano,
                           anos_disponiveis=anos_disponiveis,
                           ano_selecionado=ano_selecionado)

# --- Rota de Login ---

@app.route("/login", methods=["GET", "POST"])
def login():
    if 'username' in session:
        return redirect(url_for('index'))
        
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        utilizadores = carregar_utilizadores()
        stored_password_hash = utilizadores.get(username)
        
        if stored_password_hash and bcrypt.check_password_hash(stored_password_hash, password):
            session['username'] = username
            #flash('Login bem-sucedido!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Nome de utilizador ou palavra-passe inválidos.', 'danger')
            return render_template("login.html")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    #flash('Sessão terminada com sucesso.', 'info')
    return redirect(url_for('index'))

@app.route("/mudar_password", methods=["GET", "POST"])
def mudar_password():
    if 'username' not in session:
        flash("Por favor, faça login para aceder a esta página.", "info")
        return redirect(url_for('login'))

    if request.method == "POST":
        password_atual = request.form.get("password_atual")
        nova_password = request.form.get("nova_password")
        confirmar_password = request.form.get("confirmar_password")

        # 1. Validação inicial: Verifica se os campos estão vazios.
        if not password_atual or not nova_password or not confirmar_password:
            flash("Por favor, preencha todos os campos.", "danger")
            return render_template("mudar_password.html")
        
        username = session['username']
        utilizadores = carregar_utilizadores()
        stored_password_hash = utilizadores.get(username)

        # 2. Verificar se a palavra-passe atual está correta.
        if not stored_password_hash or not bcrypt.check_password_hash(stored_password_hash, password_atual):
            flash("A palavra-passe atual está incorreta.", "danger")
            return render_template("mudar_password.html")
        
        # 3. Verificar se a nova palavra-passe é igual à atual.
        if bcrypt.check_password_hash(stored_password_hash, nova_password):
            flash("A nova palavra-passe não pode ser igual à anterior.", "warning")
            return render_template("mudar_password.html")
            
        # 4. Verificar se a nova palavra-passe e a confirmação coincidem.
        if nova_password != confirmar_password:
            flash("A nova palavra-passe e a confirmação não coincidem.", "danger")
            return render_template("mudar_password.html")

        # 5. Alterar e guardar a nova palavra-passe.
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

    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        
        utilizadores = carregar_utilizadores()
        
        # Validação 1: Verificar se os campos estão preenchidos
        if not username or not password or not confirm_password:
            flash('Por favor, preencha todos os campos.', 'danger')
            return render_template("admin_register.html")
        
        # Validação 2: Verificar se as palavras-passe correspondem
        if password != confirm_password:
            flash('As palavras-passe não correspondem. Por favor, tente novamente.', 'danger')
            return render_template("admin_register.html")
            
        # Validação 3: Verificar se o nome de utilizador já existe
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
                    "tribo_clan": tribo_clan
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
            #flash("Item removido com sucesso.", "success")
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
    """Página para gerir o inventário da farmácia."""
    farmacia_itens = carregar_farmacia()
    tribos_disponiveis = list(carregar_tribos().keys())

    if request.method == "POST":
        acao = request.form.get("acao")

        if acao == "adicionar_item":
            nome_item = request.form.get("nome_item")
            quantidade_str = request.form.get("quantidade")
            localizacao = request.form.get("localizacao")
            tribo_clan = request.form.get("tribo_clan")

            if not all([nome_item, quantidade_str, tribo_clan]):
                flash("Por favor, preencha todos os campos obrigatórios.", "danger")
                return redirect(url_for('farmacia'))
            
            try:
                quantidade = int(quantidade_str)
            except (ValueError, TypeError):
                flash("A quantidade deve ser um número válido.", "danger")
                return redirect(url_for('farmacia'))
            
            localizacao_normalizada = localizacao.strip().lower()

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
                    "tribo_clan": tribo_clan
                }
                farmacia_itens.append(novo_item)
            
            guardar_farmacia(farmacia_itens)
            flash("Item adicionado com sucesso.", "success")
            
            return redirect(url_for('farmacia', 
                                    filtro_nome=request.args.get('filtro_nome', ''),
                                    filtro_quantidade=request.args.get('filtro_quantidade', ''),
                                    filtro_localizacao=request.args.get('filtro_localizacao', ''),
                                    filtro_tribo_clan=request.args.get('filtro_tribo_clan', '')))

        elif acao == "remover_item":
            nome_item = request.form.get("nome_item")
            tribo_clan = request.form.get("tribo_clan")
            
            farmacia_itens = [
                item for item in farmacia_itens 
                if not (item['nome'] == nome_item and item['tribo_clan'] == tribo_clan)
            ]
            
            guardar_farmacia(farmacia_itens)
            #flash("Item removido com sucesso.", "success")
            return jsonify({'status': 'success', 'message': 'Item removido com sucesso!'})

    # Lógica para filtrar e criar listas de opções para os dropdowns
    filtro_nome = request.args.get('filtro_nome', '').strip().lower()
    filtro_quantidade_str = request.args.get('filtro_quantidade', '').strip()
    filtro_localizacao = request.args.get('filtro_localizacao', '').strip().lower()
    filtro_tribo_clan = request.args.get('filtro_tribo_clan', '').strip()

    # Criação das listas de opções únicas
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

    return render_template("farmacia.html",
                           farmacia_filtrado=farmacia_filtrado,
                           tribos_disponiveis=tribos_disponiveis,
                           filtro_nome=filtro_nome,
                           filtro_quantidade=filtro_quantidade_str,
                           filtro_localizacao=filtro_localizacao,
                           filtro_tribo_clan=filtro_tribo_clan,
                           opcoes_nome=opcoes_nome,
                           opcoes_quantidade=opcoes_quantidade,
                           opcoes_localizacao=opcoes_localizacao)

if __name__ == "__main__":
    app.run(debug=True)