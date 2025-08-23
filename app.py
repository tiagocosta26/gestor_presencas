from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
import csv, os, re, json
from collections import defaultdict
from werkzeug.utils import secure_filename

app = Flask(__name__)

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
        "Guia": "#007bff",
        "Sub-Guia": "#28a745",
        "Secretário": "#dc3545"
    }
    with open(FICHEIRO_CARGOS, "w", encoding="utf-8") as f:
        json.dump(cargos_padrao, f, indent=4, ensure_ascii=False)
    return cargos_padrao

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
            reader = csv.reader(f)
            next(reader) 
            
            for linha in reader:
                if len(linha) == 7:
                    atividade_nome, data_inicio_str, data_fim_str, tribo_nome, nome, cargos_str, presente = linha
                    cargos_list = [c.strip() for c in cargos_str.split(',')] if cargos_str else []
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
    
    entidade_ativa = "Clan"
    if request.method == "POST":
        acao = request.form.get('acao')
        entidade = request.form.get('entidade')
        
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
        
        # Redirecionar para evitar o aviso de ressubmissão do formulário
        return redirect(url_for('tesouraria', entidade_ativa=entidade))

    # A partir daqui, a rota é tratada com GET
    folhas_caixa = {
        "Clan": sorted(carregar_folha_caixa("Clan"), key=lambda x: x['data']),
    }
    for tribo in tribos_disponiveis:
        folhas_caixa[tribo] = sorted(carregar_folha_caixa(tribo), key=lambda x: x['data'])
    
    entidade_ativa = request.args.get('entidade_ativa') or "Clan"
    
    return render_template("tesouraria.html", 
                           tribos=tribos_disponiveis, 
                           folhas_caixa=folhas_caixa,
                           entidade_ativa=entidade_ativa)

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    """Rota para servir ficheiros guardados no diretório de uploads."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == "__main__":
    app.run(debug=True)