from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, session, flash
from flask_sqlalchemy import SQLAlchemy
import csv, os, re, json
from collections import defaultdict
from werkzeug.utils import secure_filename
from datetime import datetime, date
from flask_bcrypt import Bcrypt
import copy
import uuid 
from icalendar import Calendar, Event
from flask import make_response
from datetime import timedelta
from sqlalchemy import func

app = Flask(__name__)
bcrypt = Bcrypt(app)

#teste

# --- CONFIGURAÇÃO DO FLASK-SQLALCHEMY ---
# Usa um ficheiro SQLite como base de dados.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app_dados.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'uma_chave_segura_para_as_sessoes'
db = SQLAlchemy(app)

# Diretórios para guardar os ficheiros (Mantidos)
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

# Ficheiros JSON Remanescentes (Ainda usados para entidades não migradas)
FICHEIRO_CARGOS = "cargos.json"
FICHEIRO_MATERIAL = "material.json"
FICHEIRO_FARMACIA = "farmacia.json"
FICHEIRO_ALERGIAS = "alergias.json"
FICHEIRO_CONDICOES = "condicoes.json"
FICHEIRO_COZINHA = "inventario_cozinha.json"
FICHEIRO_RECEITAS = "receitas.json"
FICHEIRO_PROGRESSO_MODELO = "progresso_modelo.json"
FICHEIRO_CALENDARIO = "atividades_calendario.json"
FICHEIRO_CONTAS = "contas.json"

app.config['UPLOAD_FOLDER'] = DIRETORIO_UPLOADS


# --- MODELOS DE DADOS DO SQLALCHEMY ---

# Tabela de associação para a relação N:N entre Membro e Cargo
membro_cargo = db.Table('membro_cargo',
    db.Column('membro_id', db.Integer, db.ForeignKey('membro.id'), primary_key=True),
    db.Column('cargo_id', db.Integer, db.ForeignKey('cargo.id'), primary_key=True)
)

class Tribo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    # Garante que os membros são ordenados pelo campo 'ordem' por padrão
    membros = db.relationship('Membro', backref='tribo', lazy=True, 
                             order_by="Membro.ordem") 

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'membros': [m.to_dict() for m in self.membros]
        }

class Cargo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    cor = db.Column(db.String(7), nullable=False) # Ex: #bb2124

class Membro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), unique=True, nullable=False)
    tribo_id = db.Column(db.Integer, db.ForeignKey('tribo.id'), nullable=False)
    ordem = db.Column(db.Integer, default=0) # Novo campo para gerir a ordem dentro da tribo
    
    # Relação N:N com Cargo
    cargos = db.relationship('Cargo', secondary=membro_cargo, lazy='subquery',
        backref=db.backref('membros', lazy=True))

    def to_dict(self):
        return {
            'nome': self.nome,
            'cargo': [c.nome for c in self.cargos],
            'id': self.id,
            'ordem': self.ordem,
            'tribo_nome': self.tribo.nome if self.tribo else None
        }

class Atividade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date, nullable=False)
    tribos_selecionadas = db.Column(db.String(255), nullable=True) # Ex: "Tribo A,Tribo B"

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'data_inicio': self.data_inicio.isoformat(),
            'data_fim': self.data_fim.isoformat(),
            'tribos_selecionadas': self.tribos_selecionadas.split(',') if self.tribos_selecionadas else []
        }

class Utilizador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    nivel_acesso = db.Column(db.String(50), default='membro')

class Progresso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    membro_id = db.Column(db.Integer, db.ForeignKey('membro.id'), nullable=False, unique=True)
    dados_progresso_json = db.Column(db.Text, nullable=False) 

    membro = db.relationship('Membro', backref='progresso', lazy=True)
    
    def get_dados(self):
        return json.loads(self.dados_progresso_json)

    def set_dados(self, dados):
        self.dados_progresso_json = json.dumps(dados, ensure_ascii=False)


# --- FUNÇÕES AUXILIARES MIGRATÓRIAS (SQLAlchemy) ---

def carregar_tribos():
    """Carrega as tribos e membros da base de dados, ordenados por 'ordem'."""
    tribos_db = Tribo.query.all()
    # Garante que os membros são ordenados pela relação definida (Membro.ordem)
    tribos_dict = {t.nome: [m.to_dict() for m in t.membros] for t in tribos_db}
    return tribos_dict

def carregar_nomes():
    """Carrega os nomes dos membros da base de dados (Substitui carregar_nomes do JSON)."""
    membros = Membro.query.with_entities(Membro.nome).order_by(Membro.nome).all()
    return [m[0] for m in membros]

def guardar_tribos(tribos_dict):
    """(DEPRECATED/MIGRATION ONLY) As alterações devem ser feitas diretamente nas rotas agora."""
    pass 

def carregar_utilizadores():
    """Carrega os utilizadores da base de dados (Substitui carregar_utilizadores do JSON)."""
    utilizadores = Utilizador.query.all()
    return {u.username: {'password_hash': u.password_hash, 'nivel_acesso': u.nivel_acesso} for u in utilizadores}

def guardar_utilizadores(utilizadores_dict):
    """Guarda os utilizadores na base de dados (Para compatibilidade)."""
    for username, data in utilizadores_dict.items():
        utilizador = Utilizador.query.filter_by(username=username).first()
        if not utilizador:
            utilizador = Utilizador(username=username)
            db.session.add(utilizador)
        
        utilizador.password_hash = data['password_hash']
        utilizador.nivel_acesso = data.get('nivel_acesso', 'membro')
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao guardar utilizadores: {e}")

def carregar_progresso():
    """Carrega o progresso de todos os membros da base de dados (Substitui carregar_progresso do JSON)."""
    progressos = Progresso.query.join(Membro).all()
    progresso_dict = {}
    for p in progressos:
        progresso_dict[p.membro.nome] = p.get_dados()
    return progresso_dict

def guardar_progresso(dados):
    """Guarda o progresso no SQLAlchemy (Substitui guardar_progresso do JSON)."""
    for nome_membro, dados_progresso in dados.items():
        membro = Membro.query.filter_by(nome=nome_membro).first()
        if membro:
            progresso = Progresso.query.filter_by(membro_id=membro.id).first()
            if not progresso:
                progresso = Progresso(membro_id=membro.id)
                db.session.add(progresso)
            
            progresso.set_dados(dados_progresso)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao guardar progresso: {e}")

# --- FUNÇÕES AUXILIARES REMANESCENTES (JSON/CSV) ---

def limpar_nome(nome):
    """Limpa uma string para ser usada como nome de ficheiro seguro."""
    nome_ficheiro = nome.replace('/', '-')
    nome_ficheiro = re.sub(r'[^A-Za-z0-9áéíóúãõàèùçÁÉÍÓÚÀÈÙÇ_\-@ ]', '_', nome_ficheiro)
    return nome_ficheiro

def carregar_cargos():
    """Carrega os cargos do ficheiro JSON e garante que estão no modelo Cargo (Híbrido)."""
    cargos_padrao = {}
    if os.path.exists(FICHEIRO_CARGOS):
        with open(FICHEIRO_CARGOS, encoding="utf-8") as f:
            cargos_padrao = json.load(f)
    else:
        cargos_padrao = {
            "Guia": "#bb2124", "Sub-Guia": "#bb2124", "Secretário": "#007bff",
            "Tesoureiro": "#28a745", "Animador": "#ffa500", "Cozinheiro": "#ffde21",
            "Socorrista": "#ff0000", "Guarda-Material": "#7c3a00", "Relações Públicas": "#87cefa"
        }
        with open(FICHEIRO_CARGOS, "w", encoding="utf-8") as f:
            json.dump(cargos_padrao, f, indent=4, ensure_ascii=False)
    
    # Garante que os cargos existem na BD
    for nome, cor in cargos_padrao.items():
        if not Cargo.query.filter_by(nome=nome).first():
            db.session.add(Cargo(nome=nome, cor=cor))
    db.session.commit()
    return cargos_padrao

def carregar_folha_caixa(entidade):
    caminho = os.path.join(DIRETORIO_TESOURARIA, f"{limpar_nome(entidade)}.json")
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    return []

def guardar_folha_caixa(entidade, folha_caixa):
    caminho = os.path.join(DIRETORIO_TESOURARIA, f"{limpar_nome(entidade)}.json")
    os.makedirs(DIRETORIO_TESOURARIA, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(folha_caixa, f, indent=4, ensure_ascii=False)

def carregar_material():
    if os.path.exists(FICHEIRO_MATERIAL):
        with open(FICHEIRO_MATERIAL, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def guardar_farmacia(farmacia):
    with open(FICHEIRO_FARMACIA, "w", encoding="utf-8") as f:
        json.dump(farmacia, f, indent=4, ensure_ascii=False)

def carregar_farmacia():
    if os.path.exists(FICHEIRO_FARMACIA):
        with open(FICHEIRO_FARMACIA, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def guardar_alergias(alergias):
    with open(FICHEIRO_ALERGIAS, "w", encoding="utf-8") as f:
        json.dump(alergias, f, indent=4, ensure_ascii=False)

def carregar_alergias():
    if os.path.exists(FICHEIRO_ALERGIAS):
        with open(FICHEIRO_ALERGIAS, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def guardar_condicoes(condicoes):
    with open(FICHEIRO_CONDICOES, "w", encoding="utf-8") as f:
        json.dump(condicoes, f, indent=4, ensure_ascii=False)

def carregar_condicoes():
    if os.path.exists(FICHEIRO_CONDICOES):
        with open(FICHEIRO_CONDICOES, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def guardar_material(material):
    with open(FICHEIRO_MATERIAL, "w", encoding="utf-8") as f:
        json.dump(material, f, indent=4, ensure_ascii=False)

def carregar_inventario_cozinha():
    if os.path.exists(FICHEIRO_COZINHA):
        with open(FICHEIRO_COZINHA, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def guardar_inventario_cozinha(inventario):
    with open(FICHEIRO_COZINHA, "w", encoding="utf-8") as f:
        json.dump(inventario, f, indent=4, ensure_ascii=False)

def carregar_receitas():
    if os.path.exists(FICHEIRO_RECEITAS):
        with open(FICHEIRO_RECEITAS, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def guardar_receitas(receitas):
    with open(FICHEIRO_RECEITAS, "w", encoding="utf-8") as f:
        json.dump(receitas, f, indent=4, ensure_ascii=False)

def ler_contas():
    if not os.path.exists(FICHEIRO_CONTAS):
        with open(FICHEIRO_CONTAS, "w") as f:
            json.dump({}, f)
        return {}
    with open(FICHEIRO_CONTAS, "r") as f:
        return json.load(f)

def gravar_contas(contas):
    with open(FICHEIRO_CONTAS, "w") as f:
        json.dump(contas, f, indent=4)
        
def carregar_progresso_modelo():
    if os.path.exists(FICHEIRO_PROGRESSO_MODELO):
        with open(FICHEIRO_PROGRESSO_MODELO, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

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
    if isinstance(obj, dict):
        return {k: calcular_progresso_bool_do_dicionario(v) for k, v in obj.items()}
    elif isinstance(obj, str):
        return obj == "concluído"
    else:
        return False
        
@app.template_global()
def calcular_nivel(dados_pessoa_bool, trilhos_por_area):
    trilhos_concluidos_por_area = {}
    
    for area_nome, trilhos_da_area in trilhos_por_area.items():
        count_trilhos_concluidos = 0
        for trilho_nome, objetivos_do_trilho in trilhos_da_area.items():
            trilho_completo = True
            dados_trilho = dados_pessoa_bool.get(area_nome, {}).get(trilho_nome, {})
            for objetivo in objetivos_do_trilho:
                if not dados_trilho.get(objetivo):
                    trilho_completo = False
                    break
            if trilho_completo:
                count_trilhos_concluidos += 1
        trilhos_concluidos_por_area[area_nome] = count_trilhos_concluidos

    todos_concluidos = all(trilhos_concluidos_por_area[area] == len(trilhos_por_area[area]) for area in trilhos_por_area)
    if todos_concluidos:
        return "Anilha de Mérito"
    
    dois_por_area = all(trilhos_concluidos_por_area[area] >= 2 for area in trilhos_concluidos_por_area)
    if dois_por_area:
        return "Partida"
        
    um_por_area = all(trilhos_concluidos_por_area[area] >= 1 for area in trilhos_concluidos_por_area)
    if um_por_area:
        return "Serviço"
        
    return "Comunidade"


# --- INICIALIZAÇÃO DA BASE DE DADOS ---
with app.app_context():
    db.create_all()
    carregar_cargos()


# --- ROTAS PRINCIPAIS (Migradas para SQLAlchemy) ---

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/gestao_presencas", methods=["GET", "POST"])
def presencas():
    """Rota para registar uma nova atividade na base de dados (Substitui CSV)."""
    tribos = carregar_tribos()
    
    if request.method == "POST":
        atividade_nome = request.form["atividade"]
        data_inicio_str = request.form["data_inicio"]
        data_fim_str = request.form["data_fim"]
        tribos_selecionadas_str = request.form["tribos_selecionadas"]

        try:
            data_inicio = datetime.strptime(data_inicio_str, "%Y-%m-%d").date()
            data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Erro no formato das datas.", 'danger')
            return redirect(url_for("presencas"))

        # Cria a nova atividade na BD
        nova_atividade = Atividade(
            nome=atividade_nome,
            data_inicio=data_inicio,
            data_fim=data_fim,
            tribos_selecionadas=tribos_selecionadas_str
        )
        db.session.add(nova_atividade)

        try:
            db.session.commit()
            flash(f"Atividade '{atividade_nome}' registada com sucesso na base de dados!", 'success')
            return redirect(url_for("atividades"))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao guardar atividade: {e}", 'danger')
            return redirect(url_for("presencas"))

    hoje = date.today().isoformat()
    return render_template("gestao_presencas.html", hoje=hoje, tribos=tribos)


@app.route("/atividades")
def atividades():
    """Exibe a lista de atividades registadas (da base de dados)."""
    
    # Busca todas as atividades, ordenadas pela data de início mais recente
    atividades_db = Atividade.query.order_by(Atividade.data_inicio.desc()).all()
    
    atividades_agrupadas = defaultdict(list)

    for atividade in atividades_db:
        # Agrupa pelo Mês/Ano
        mes_ano = atividade.data_inicio.strftime("%Y-%m")
        # Tuplo: (id, nome)
        atividades_agrupadas[mes_ano].append((atividade.id, atividade.nome))

    # Ordena os meses do mais recente para o mais antigo
    meses_ordenados = sorted(atividades_agrupadas.keys(), reverse=True)
    
    return render_template("atividades.html", atividades_agrupadas=atividades_agrupadas, meses_ordenados=meses_ordenados)


@app.route('/eliminar_atividade/<int:atividade_id>', methods=['POST'])
def eliminar_atividade(atividade_id):
    """Elimina uma atividade da base de dados."""
    try:
        atividade = Atividade.query.get_or_404(atividade_id)
        db.session.delete(atividade)
        db.session.commit()
        flash(f"Atividade '{atividade.nome}' eliminada com sucesso.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao eliminar atividade: {e}", 'danger')
    
    return redirect(url_for('atividades'))


@app.route("/gestao_tribos", methods=["GET", "POST"])
def gestao_tribos():
    """Página para gerir tribos e membros, utilizando a base de dados."""
    
    # Busca todas as tribos (com membros ordenados por Membro.ordem)
    tribos_db = Tribo.query.all()
    
    # Busca todos os cargos e cria um dicionário para a UI e ordem
    cargos_db = Cargo.query.all()
    cargos_disponiveis = {c.nome: c.cor for c in cargos_db}
    cargo_ordem = {cargo.nome: i for i, cargo in enumerate(cargos_db)}

    if request.method == "POST":
        acao = request.form.get("acao")
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if acao == "criar_tribo":
            nome_tribo = request.form.get("nome_tribo").strip()
            if not nome_tribo:
                flash("O nome da tribo não pode ser vazio.", 'warning')
                return jsonify({"status": "error", "message": "Nome vazio"}) if is_ajax else redirect(url_for("gestao_tribos"))

            # Verifica se já existe (case-insensitive)
            if Tribo.query.filter(func.lower(Tribo.nome) == func.lower(nome_tribo)).first():
                flash(f"A tribo '{nome_tribo}' já existe.", 'warning')
                return jsonify({"status": "error", "message": "Tribo já existe"}) if is_ajax else redirect(url_for("gestao_tribos"))

            nova_tribo = Tribo(nome=nome_tribo)
            db.session.add(nova_tribo)
            try:
                db.session.commit()
                flash(f"Tribo '{nome_tribo}' criada com sucesso!", 'success')
                return jsonify({"status": "ok", "tribo": nova_tribo.to_dict()}) if is_ajax else redirect(url_for("gestao_tribos"))
            except Exception as e:
                db.session.rollback()
                flash(f"Erro ao criar tribo: {e}", 'danger')
                return jsonify({"status": "error", "message": str(e)}) if is_ajax else redirect(url_for("gestao_tribos"))


        elif acao == "remover_tribo":
            tribo_id = request.form.get("tribo_id")
            tribo = Tribo.query.get(tribo_id)
            if tribo:
                # Remove o progresso e os membros associados
                for membro in tribo.membros:
                    Progresso.query.filter_by(membro_id=membro.id).delete()
                    db.session.delete(membro)
                
                db.session.delete(tribo)
                try:
                    db.session.commit()
                    flash(f"Tribo '{tribo.nome}' e seus membros eliminados com sucesso.", 'success')
                    return jsonify({"status": "ok"}) if is_ajax else redirect(url_for("gestao_tribos"))
                except Exception as e:
                    db.session.rollback()
                    flash(f"Erro ao remover tribo: {e}", 'danger')
                    return jsonify({"status": "error", "message": str(e)}) if is_ajax else redirect(url_for("gestao_tribos"))
            else:
                flash("Tribo não encontrada.", 'warning')
                return jsonify({"status": "error", "message": "Tribo não encontrada"}) if is_ajax else redirect(url_for("gestao_tribos"))

        elif acao == "adicionar_pessoa":
            tribo_id = request.form.get("tribo_id")
            nome_pessoa = request.form.get("nome_pessoa").strip()
            tribo = Tribo.query.get(tribo_id)
            
            if not tribo or not nome_pessoa:
                flash("Dados inválidos para adicionar pessoa.", 'warning')
                return jsonify({"status": "error", "message": "Dados inválidos"}) if is_ajax else redirect(url_for("gestao_tribos"))

            # Verifica se já existe (case-insensitive)
            if Membro.query.filter(func.lower(Membro.nome) == func.lower(nome_pessoa)).first():
                flash(f"A pessoa '{nome_pessoa}' já existe (a base de dados exige nomes únicos).", 'warning')
                return jsonify({"status": "error", "message": "Pessoa já existe"}) if is_ajax else redirect(url_for("gestao_tribos"))
            
            # Define a ordem como o próximo número
            max_ordem = db.session.query(func.max(Membro.ordem)).filter_by(tribo_id=tribo.id).scalar() or 0
            
            novo_membro = Membro(nome=nome_pessoa, tribo_id=tribo.id, ordem=max_ordem + 1)
            db.session.add(novo_membro)

            try:
                db.session.commit()
                flash(f"Pessoa '{nome_pessoa}' adicionada à tribo '{tribo.nome}'.", 'success')
                return jsonify({"status": "ok", "pessoa": novo_membro.to_dict()}) if is_ajax else redirect(url_for("gestao_tribos"))
            except Exception as e:
                db.session.rollback()
                flash(f"Erro ao adicionar pessoa: {e}", 'danger')
                return jsonify({"status": "error", "message": str(e)}) if is_ajax else redirect(url_for("gestao_tribos"))

        elif acao == "remover_pessoa":
            membro_id = request.form.get("membro_id")
            membro = Membro.query.get(membro_id)
            
            if membro:
                nome_membro = membro.nome
                tribo_nome = membro.tribo.nome
                
                # Remove Progresso associado se existir
                Progresso.query.filter_by(membro_id=membro.id).delete()
                
                db.session.delete(membro)
                try:
                    db.session.commit()
                    flash(f"Pessoa '{nome_membro}' removida da tribo '{tribo_nome}'.", 'success')
                    return jsonify({"status": "ok", "nome_pessoa": nome_membro}) if is_ajax else redirect(url_for("gestao_tribos"))
                except Exception as e:
                    db.session.rollback()
                    flash(f"Erro ao remover pessoa: {e}", 'danger')
                    return jsonify({"status": "error", "message": str(e)}) if is_ajax else redirect(url_for("gestao_tribos"))
            else:
                flash("Pessoa não encontrada.", 'warning')
                return jsonify({"status": "error", "message": "Pessoa não encontrada"}) if is_ajax else redirect(url_for("gestao_tribos"))
        
        elif acao == "adicionar_cargo":
            membro_id = request.form.get("membro_id")
            cargo_nome = request.form.get("cargo")
            
            membro = Membro.query.get(membro_id)
            cargo = Cargo.query.filter_by(nome=cargo_nome).first()

            if membro and cargo:
                if cargo in membro.cargos:
                    membro.cargos.remove(cargo)
                    status = "removido"
                else:
                    membro.cargos.append(cargo)
                    status = "adicionado"
                
                # Reordenar cargos para manter a ordem predefinida
                membro.cargos.sort(key=lambda c: cargo_ordem.get(c.nome, float('inf')))

                try:
                    db.session.commit()
                    flash(f"Cargo '{cargo_nome}' {status} para {membro.nome}.", 'success')
                    return jsonify({"status": "ok", "pessoa": membro.to_dict(), "cargos_disponiveis": cargos_disponiveis}) if is_ajax else redirect(url_for("gestao_tribos"))
                except Exception as e:
                    db.session.rollback()
                    flash(f"Erro ao atualizar cargo: {e}", 'danger')
                    return jsonify({"status": "error", "message": str(e)}) if is_ajax else redirect(url_for("gestao_tribos"))
            else:
                flash("Membro ou cargo não encontrado.", 'warning')
                return jsonify({"status": "error", "message": "Dados inválidos"}) if is_ajax else redirect(url_for("gestao_tribos"))
                
        # O drag and drop é tratado pela rota /reordenar_pessoas
        elif acao == 'ordenar':
            # Se a requisição for AJAX, retorna um erro ou um ok
            if is_ajax:
                 return jsonify({'status': 'ok'}) # Rota /reordenar_pessoas faz o trabalho pesado
            return redirect(url_for("gestao_tribos")) 
            

    return render_template("gestao_tribos.html", tribos=tribos_db, cargos_disponiveis=cargos_disponiveis)


@app.route("/reordenar_pessoas", methods=["POST"])
def reordenar_pessoas():
    """Rota para reordenar/mover membros entre tribos (Drag and Drop)."""
    data = request.get_json()
    nova_tribo_nome = data.get("nova_tribo")
    nova_ordem_ids = data.get("nova_ordem_ids") # Espera uma lista de IDs de membro

    if not nova_tribo_nome or not isinstance(nova_ordem_ids, list):
        return jsonify({"status": "erro", "message": "Dados em falta ou inválidos"}), 400

    tribo_destino = Tribo.query.filter_by(nome=nova_tribo_nome).first()
    if not tribo_destino:
        return jsonify({"status": "erro", "message": "Tribo de destino não encontrada"}), 404

    try:
        # 1. Atualizar o tribo_id e a ordem para todos os membros na nova ordem
        for index, membro_id_str in enumerate(nova_ordem_ids):
            try:
                membro_id = int(membro_id_str)
            except ValueError:
                continue

            membro = Membro.query.get(membro_id)
            if membro:
                # Altera a tribo e atualiza a ordem
                membro.tribo_id = tribo_destino.id
                membro.ordem = index + 1 
        
        db.session.commit()
        return jsonify({"status": "ok", "message": f"Membros atualizados na tribo '{nova_tribo_nome}'"})

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao reordenar pessoas: {e}")
        return jsonify({"status": "erro", "message": f"Erro ao atualizar base de dados: {str(e)}"}), 500

@app.route("/atividade/<ficheiro>")
def ver_atividade(ficheiro):
    """Exibe os detalhes de uma atividade registada (ainda usa o ficheiro CSV)."""
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
    username = session.get('username')
    
    # 1. Determina todas as tribos disponíveis na base de dados
    todas_tribos = list(carregar_tribos().keys())
    
    # 2. Determina as entidades (Clan + Tribos) que o utilizador tem permissão para ver/editar
    entidades_permitidas = ["Clan"] # Todos, mesmo sem permissão explícita, veem o Clan
    
    # Regras de permissão
    if username in ["Chefe", "Clan"]:
        # "Chefe" e "Clan" (Assumindo Tesoureiro Global) têm acesso total a todas as tribos
        entidades_permitidas.extend(todas_tribos)

    elif username == "Peter Benenson":
        # Tesoureiro da Tribo Peter Benenson (vê Clan + a sua tribo)
        if "Peter Benenson" in todas_tribos:
            entidades_permitidas.append("Peter Benenson")
            # flash('Olá, Peter! Tem acesso restrito à tesouraria da sua tribo.', 'info')
        
    elif username == "Henri Dunant":
        # Tesoureiro da Tribo Henri Dunant (vê Clan + a sua tribo)
        if "Henri Dunant" in todas_tribos:
            entidades_permitidas.append("Henri Dunant")
            # flash('Olá, Henri! Tem acesso restrito à tesouraria da sua tribo.', 'info')

    elif username == "Rainha D. Leonor":
        # Tesoureiro da Tribo Rainha D. Leonor (vê Clan + a sua tribo)
        if "Rainha D. Leonor" in todas_tribos:
            entidades_permitidas.append("Rainha D. Leonor")
            # flash('Olá, Rainha D. Leonor! Tem acesso restrito à tesouraria da sua tribo.', 'info')

    # Lista de tribos (apenas tribos, sem "Clan") para ser passada ao template
    tribos_disponiveis_template = [e for e in entidades_permitidas if e != "Clan"]

    # --- Tratamento de Pedidos POST (Adicionar/Remover) ---
    if request.method == "POST":
        acao = request.form.get('acao')
        entidade = request.form.get('entidade')
        
        # VERIFICAÇÃO DE SEGURANÇA: Garante que o utilizador tem permissão para modificar esta entidade
        if entidade not in entidades_permitidas:
            # flash("Não tem permissão para alterar esta folha de caixa.", "danger")
            return redirect(url_for('tesouraria'))
            
        try:
            folha_caixa = carregar_folha_caixa(entidade)
            
            if acao == 'adicionar':
                valor_str = request.form.get('valor')
                # Converte para float com fallback seguro
                valor = float(valor_str) if valor_str else 0.0 
                
                nova_transacao = {
                    'data': request.form.get('data'),
                    'descricao': request.form.get('descricao'),
                    'tipo': request.form.get('tipo'),
                    'valor': valor,
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
                # flash(f"Transação adicionada à folha de caixa de {entidade}.", "success")
            
            elif acao == 'remover':
                index_str = request.form.get('index')
                index = int(index_str) if index_str else -1
                
                if 0 <= index < len(folha_caixa):
                    transacao_a_remover = folha_caixa[index]
                    
                    # Remove o ficheiro comprovativo associado, se existir
                    if 'comprovativo' in transacao_a_remover and transacao_a_remover['comprovativo']:
                        caminho_ficheiro = os.path.join(DIRETORIO_UPLOADS, transacao_a_remover['comprovativo'])
                        try:
                            os.remove(caminho_ficheiro)
                        except OSError as e:
                            print(f"Erro ao tentar remover o ficheiro {caminho_ficheiro}: {e}")
                    
                    folha_caixa.pop(index)
                    # flash(f"Transação removida da folha de caixa de {entidade}.", "success")
            
            guardar_folha_caixa(entidade, folha_caixa)
            
        except ValueError:
            # flash("O valor da transação não é um número válido.", "danger")
            return redirect(url_for('tesouraria', entidade_ativa=entidade))
        except Exception as e:
            print(f"Erro ao processar a ação: {e}")
            # flash(f"Ocorreu um erro ao processar a transação: {e}", "danger")

        return redirect(url_for('tesouraria', entidade_ativa=entidade))

    # --- Tratamento de Pedidos GET (Carregar Dados) ---
    
    # Carrega os dados APENAS para as entidades que o utilizador pode ver
    folhas_caixa = {}
    for entidade in entidades_permitidas:
        # Carrega e ordena as transações pela data (mais recente primeiro)
        folhas_caixa[entidade] = sorted(carregar_folha_caixa(entidade), 
                                        key=lambda x: x.get('data', '0000-00-00'), 
                                        reverse=True)
                                        
    # Determina a entidade ativa a ser mostrada (da query string ou default)
    entidade_ativa_param = request.args.get('entidade_ativa')
    if entidade_ativa_param and entidade_ativa_param in entidades_permitidas:
        entidade_ativa = entidade_ativa_param
    elif "Clan" in entidades_permitidas:
        entidade_ativa = "Clan"
    elif tribos_disponiveis_template:
        entidade_ativa = tribos_disponiveis_template[0]
    else:
        entidade_ativa = "Clan" # Default se não houver permissão para nada


    return render_template("tesouraria.html", 
                           tribos=tribos_disponiveis_template, # Lista de tribos para os tabs/dropdown
                           folhas_caixa=folhas_caixa,          # Dados de todas as entidades permitidas
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
                # Adicionado encoding para lidar com ficheiros CSV gerados por Excel
                with open(caminho, newline="", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        tribo = row.get('Tribo')
                        elemento = row.get('Elemento')
                        presente = row.get('Presente')
                        
                        if tribo and elemento: # Garante que as chaves existem
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
        if username in ['Chefe', 'Clan', 'Peter Benenson', 'Henri Dunant', 'Rainha D. Leonor']:
            utilizadores = carregar_utilizadores()
            stored_password_hash = utilizadores.get(username)
            
            # Nota: O uso de MockBcrypt simula a verificação real da password.
            if stored_password_hash and bcrypt.check_password_hash(stored_password_hash, password):
                session['username'] = username
                # flash('Login bem-sucedido!', 'success')
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
    # flash('Sessão terminada com sucesso.', 'info')
    return redirect(url_for('index'))

@app.route("/mudar_password", methods=["GET", "POST"])
def mudar_password():
    # Permite que todos os utilizadores com acesso façam a alteração.
    if session.get('username') not in carregar_utilizadores().keys():
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
        
        if not all([username, password, confirm_password]):
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
    # Assume que todos os utilizadores autenticados podem aceder a esta rota, 
    # mas a edição deve ser restrita se necessário.
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
                # flash("Por favor, preencha todos os campos obrigatórios.", "danger")
                return redirect(url_for('material'))
            
            try:
                quantidade = int(quantidade_str)
            except (ValueError, TypeError):
                # flash("A quantidade deve ser um número válido.", "danger")
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
            # flash("Item adicionado com sucesso.", "success")

            return redirect(url_for('material',
                                    filtro_nome=request.args.get('filtro_nome', ''),
                                    filtro_quantidade=request.args.get('filtro_quantidade', ''),
                                    filtro_localizacao=request.args.get('filtro_localizacao', ''),
                                    filtro_tribo_clan=request.args.get('filtro_tribo_clan', '')))

        elif acao == "remover_item":
            nome_item = request.form.get("nome_item")
            tribo_clan = request.form.get("tribo_clan")

            # Cria uma nova lista excluindo o item a remover
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
    
    # Remove duplicados e ordena
    pessoas_disponiveis = sorted(list(set(pessoas_disponiveis)))

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
                if quantidade <= 0:
                    flash("A quantidade deve ser um número positivo.", "danger")
                    return redirect(url_for('farmacia'))
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
                flash(f"Quantidade de '{nome_item}' atualizada.", "success")
            else:
                novo_item = {
                    "nome": nome_item.strip(),
                    "quantidade": quantidade,
                    "localizacao": localizacao.strip(),
                    "tribo_clan": tribo_clan,
                    "observacoes": observacoes.strip()
                }
                farmacia_itens.append(novo_item)
                flash(f"Novo item '{nome_item}' adicionado.", "success")

            guardar_farmacia(farmacia_itens)
            return redirect(url_for('farmacia'))

        # ---------- REMOVER ITEM ----------
        elif acao == "remover_item":
            # Esta lógica assume que a remoção é feita por JS/AJAX, usando jsonify.
            nome_item = request.form.get("nome_item")
            tribo_clan = request.form.get("tribo_clan")

            # Removido item com base no nome e tribo
            # O nome do item no formulário POST deve ser o nome EXATO do item no inventário
            farmacia_itens_antes = len(farmacia_itens)
            
            # Novo filtro para remover itens, normalizando o nome para garantir correspondência robusta
            farmacia_itens = [
                item for item in farmacia_itens 
                if not (item['nome'].strip().lower() == nome_item.strip().lower() and item['tribo_clan'] == tribo_clan)
            ]

            guardar_farmacia(farmacia_itens)
            
            if len(farmacia_itens) < farmacia_itens_antes:
                return jsonify({'status': 'success', 'message': f'Item "{nome_item}" removido com sucesso!'})
            else:
                return jsonify({'status': 'error', 'message': f'Item "{nome_item}" não encontrado ou dados insuficientes.'}), 400


        # ---------- GUARDAR INFORMAÇÕES DE SAÚDE ----------
        elif acao == "guardar_saude":
            # Itera sobre todas as pessoas disponíveis para verificar os formulários
            for pessoa in pessoas_disponiveis:
                alergia_raw = request.form.get(f"alergia-{pessoa}", "").strip()
                condicao_raw = request.form.get(f"condicao-{pessoa}", "").strip()
                
                # Se for fornecido, guarda as alergias, separando por vírgula se houver várias linhas
                if alergia_raw:
                    alergias[pessoa] = ", ".join([linha.strip() for linha in alergia_raw.splitlines() if linha.strip()])
                else:
                    alergias.pop(pessoa, None) # Remove se estiver vazio

                # Se for fornecido, guarda as condições
                if condicao_raw:
                    condicoes[pessoa] = ", ".join([linha.strip() for linha in condicao_raw.splitlines() if linha.strip()])
                else:
                    condicoes.pop(pessoa, None) # Remove se estiver vazio

            guardar_alergias(alergias)
            guardar_condicoes(condicoes)
            flash("Informações de saúde atualizadas com sucesso.", "success")
            return redirect(url_for("farmacia"))

    # ---------- FILTROS (LÓGICA GET) ----------
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
            # Se o filtro não for um número válido, ignora o filtro de quantidade
            pass 
            
    if filtro_localizacao:
        # Usa .get('localizacao', '').lower() para lidar com itens que possam não ter o campo
        farmacia_filtrado = [item for item in farmacia_filtrado if filtro_localizacao in item.get('localizacao', '').lower()]
        
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
        condicoes=condicoes,
        messages=session.pop('messages', []) # Passa mensagens flash para o template
    )


@app.route("/cozinha", methods=["GET", "POST"])
def cozinha():
    """Página para gerir o inventário e receitas da cozinha."""
    
    inventario = carregar_inventario_cozinha()
    receitas = carregar_receitas()
    tribos_disponiveis = list(carregar_tribos().keys()) 

    opcoes_unidade = ["unidades", "kg", "g", "l", "ml", "pacote", "rolo", "a gosto"]
    opcoes_categoria = ["Cereais", "Laticínios", "Carne", "Peixe", "Frutas", "Vegetais", "Especiarias", "Bebidas", "Outros"]
    opcoes_dificuldade = ["Fácil", "Médio", "Difícil"]

    if request.method == "POST":
        acao = request.form.get("acao")

        # --- ARQUIVAR NOVA RECEITA ---
        if acao == "adicionar_receita":
            nome_receita = request.form.get("nome_receita")
            ingredientes_raw = request.form.get("ingredientes_raw", "")
            instrucoes = request.form.get("instrucoes", "")
            tempo_preparacao = request.form.get("tempo_preparacao", "")
            dificuldade = request.form.get("dificuldade", "")
            porcoes_base = request.form.get("porcoes_base", "")
            
            # Validação básica
            if not nome_receita:
                flash("O nome da receita é obrigatório.", "danger")
                return redirect(url_for('cozinha'))

            link_ficheiro = None
            
            # Lógica para ficheiro/comprovativo de receita
            if 'comprovativo_receita' in request.files:
                file = request.files['comprovativo_receita']
                if file.filename != '':
                    # A pasta já foi criada na inicialização da app
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(DIRETORIO_RECEITAS, filename)
                    file.save(filepath)
                    # A rota 'serve_receita' deve ser usada para servir este arquivo
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
                    "instrucoes": instrucoes.strip(),
                    "tempo_preparacao": tempo_preparacao.strip(),
                    "dificuldade": dificuldade.strip(),
                    "porcoes_base": porcoes_base.strip()
                }
            
            # Adicionar e guardar
            receitas.append(nova_receita)
            guardar_receitas(receitas)
            
            flash(f"Receita '{nome_receita}' arquivada com sucesso!", "success")
            return redirect(url_for('cozinha'))
            
        # --- GESTÃO DE STOCK: ADICIONAR/ATUALIZAR ---
        if acao == "adicionar_item_cozinha":
            # O código original desta secção estava incompleto. 
            # Assumimos que o formulário POST de adição de item de cozinha
            # traz nome, quantidade, unidade, categoria, etc., e atualiza o inventário.
            
            # Lógica de exemplo para ADICIONAR/ATUALIZAR um item do inventário
            nome_item = request.form.get("nome_item_estoque", "").strip()
            quantidade_str = request.form.get("quantidade_estoque", "").strip()
            unidade = request.form.get("unidade_estoque", "").strip()
            categoria = request.form.get("categoria_estoque", "").strip()
            
            if not all([nome_item, quantidade_str, unidade, categoria]):
                flash("Preencha todos os campos do item de estoque.", "danger")
                return redirect(url_for('cozinha'))

            try:
                quantidade = float(quantidade_str)
            except ValueError:
                flash("Quantidade do item de estoque deve ser um número.", "danger")
                return redirect(url_for('cozinha'))

            # Normalizar chaves para pesquisa
            nome_normalizado = nome_item.lower()
            unidade_normalizada = unidade.lower()

            item_existente = next((
                item for item in inventario 
                if item['nome'].lower() == nome_normalizado and item['unidade'].lower() == unidade_normalizada
            ), None)

            if item_existente:
                # Se for o mesmo item (nome+unidade), apenas atualiza
                item_existente['quantidade'] = quantidade
                item_existente['categoria'] = categoria # Atualiza a categoria
                flash(f"Estoque de '{nome_item}' atualizado.", "success")
            else:
                # Adiciona novo item
                novo_item = {
                    "nome": nome_item, 
                    "quantidade": quantidade, 
                    "unidade": unidade, 
                    "categoria": categoria,
                    "comprovativo": None # Campo comprovativo
                }
                inventario.append(novo_item)
                flash(f"Novo item '{nome_item}' adicionado ao estoque.", "success")
            
            guardar_inventario_cozinha(inventario)
            return redirect(url_for('cozinha'))

        # Se a ação não for reconhecida, redireciona sem erro grave.
        return redirect(url_for('cozinha'))

    # ---------- FILTROS (LÓGICA GET) ----------
    filtro_categoria = request.args.get('categoria', 'Todos') 
    
    inventario_ordenado = sorted(inventario, key=lambda x: x['nome'])
    
    inventario_filtrado = []
    if filtro_categoria == 'Todos':
        inventario_filtrado = inventario_ordenado
    else:
        # Filtra pelo nome da categoria que é passado no URL
        inventario_filtrado = [item for item in inventario_ordenado if item.get('categoria') == filtro_categoria]

    # Ordena receitas por nome
    receitas_ordenadas = sorted(receitas, key=lambda x: x['nome'])
    
    return render_template("cozinha.html",
                            inventario=inventario_filtrado, # Enviar a lista FILTRADA
                            receitas=receitas_ordenadas,
                            opcoes_unidade=opcoes_unidade,
                            opcoes_categoria=opcoes_categoria,
                            opcoes_dificuldade=opcoes_dificuldade,
                            tribos_disponiveis=tribos_disponiveis,
                            filtro_categoria_atual=filtro_categoria, # Enviar o filtro atual
                            messages=session.pop('messages', []))

# --- ROTAS DE SERVIÇO DE ARQUIVOS (UPLOADS) ---

@app.route('/uploads/cozinha/<path:filename>')
def serve_upload_cozinha(filename):
    """Serve os ficheiros de comprovativo de stock."""
    # Serve os ficheiros da pasta 'uploads/cozinha'
    return send_from_directory(DIRETORIO_UPLOADS_COZINHA, filename)


@app.route('/receitas/<path:filename>')
def serve_receita(filename):
    """Serve os ficheiros de receitas."""
    return send_from_directory(DIRETORIO_RECEITAS, filename)

# --- ROTAS DE DETALHE E ELIMINAÇÃO ---

@app.route("/cozinha/receita/<string:nome_receita>", methods=["GET"])
def ver_receita(nome_receita):
    """Exibe os detalhes de uma receita específica com a opção de alterar porções."""
    receitas = carregar_receitas()
    
    # Busca a receita pelo nome exato. É melhor usar um ID único em um projeto real.
    receita = next((r for r in receitas if r['nome'] == nome_receita), None)

    if not receita:
        flash("Receita não encontrada.", "danger")
        return redirect(url_for('cozinha'))
        
    return render_template("ver_receita.html", 
                           receita=receita, 
                           messages=session.pop('messages', []))


@app.route("/eliminar_receita", methods=["POST"])
def eliminar_receita():
    """Elimina uma receita, incluindo o ficheiro associado se existir."""
    nome_receita = request.form.get("nome_receita")
    link_ficheiro = request.form.get("link_ficheiro")

    if not nome_receita:
        flash("Nome da receita não fornecido.", "danger")
        return redirect(url_for('cozinha'))

    receitas = carregar_receitas()

    # 1. Lógica para remover o ficheiro, se existir
    if link_ficheiro:
        # Usa os.path.basename para extrair o nome do arquivo da URL (ex: '/receitas/bolo.pdf' -> 'bolo.pdf')
        caminho_ficheiro = os.path.join(DIRETORIO_RECEITAS, os.path.basename(link_ficheiro))
        if os.path.exists(caminho_ficheiro):
            try:
                os.remove(caminho_ficheiro)
            except OSError as e:
                flash(f"Erro ao eliminar o ficheiro: {e}", "warning")

    # 2. Eliminar a receita do JSON
    # Filtrar receitas: manter as que não correspondem ao nome E ao link_ficheiro (se fornecido)
    receitas_antes = len(receitas)
    
    # Normaliza a comparação do link para evitar erros se o campo 'link_ficheiro' não existir no JSON
    receitas = [
        r for r in receitas 
        if not (
            r['nome'] == nome_receita and 
            r.get('link_ficheiro', '') == (link_ficheiro if link_ficheiro else '')
        )
    ]
    
    guardar_receitas(receitas)
    
    if len(receitas) < receitas_antes:
        flash(f"Receita '{nome_receita}' eliminada com sucesso.", "success")
    else:
        flash(f"Erro: Receita '{nome_receita}' não encontrada para eliminação.", "danger")

    return redirect(url_for('cozinha'))

@app.route("/eliminar_item_inventario", methods=["POST"])
def eliminar_item_inventario():
    """Elimina um item específico do inventário, incluindo o ficheiro de comprovativo associado, se existir."""
    
    # Obter dados do formulário (nome e unidade são a chave única)
    nome_item_raw = request.form.get("nome_item", "").strip()
    unidade_item_raw = request.form.get("unidade_item", "").strip()
    
    # Normalizar para comparação com o JSON
    nome_item_normalizado = nome_item_raw.lower()
    unidade_item_normalizada = unidade_item_raw.lower()

    if not nome_item_normalizado or not unidade_item_normalizada:
        flash("Nome ou unidade do item não fornecidos para eliminação.", "danger")
        return redirect(url_for('cozinha'))

    inventario = carregar_inventario_cozinha()
    item_removido = None

    # 2. Encontrar o item a remover
    item_a_remover = next((i for i in inventario 
                            # Normaliza a comparação de nome e unidade
                           if i.get('nome', '').strip().lower() == nome_item_normalizado and 
                              i.get('unidade', '').strip().lower() == unidade_item_normalizada), None)

    if item_a_remover:
        item_removido = item_a_remover.get('nome') # Guarda o nome original para a mensagem Flash
        caminho_comprovativo = item_a_remover.get('comprovativo') # 'comprovativo' deve ser a URL

        # 3. Lógica para remover o ficheiro do comprovativo, se existir
        if caminho_comprovativo:
            try:
                filename = os.path.basename(caminho_comprovativo)
                # Assume que o caminho do arquivo é baseado no DIRETORIO_UPLOADS_COZINHA
                filepath = os.path.join(DIRETORIO_UPLOADS_COZINHA, filename) 
                
                if os.path.exists(filepath):
                    os.remove(filepath)
                # Se não existir, não é um erro grave, apenas uma limpeza falhada.
            except Exception as e:
                # Não bloqueia a remoção do registo, mas alerta para o erro do ficheiro
                print(f"Erro ao eliminar o comprovativo de stock ({caminho_comprovativo}): {e}")
                flash(f"Item eliminado, mas erro ao remover o comprovativo. Por favor, verifique o servidor.", "warning")

        # 4. Atualizar inventário (criando uma nova lista sem o item correspondente)
        inventario = [i for i in inventario 
                      if not (i.get('nome', '').strip().lower() == nome_item_normalizado and 
                              i.get('unidade', '').strip().lower() == unidade_item_normalizada)]
                              
        guardar_inventario_cozinha(inventario)
        
        flash(f"Item '{item_removido}' (Unidade: {unidade_item_raw}) eliminado com sucesso do inventário.", "success")
    else:
        flash(f"Item '{nome_item_raw}' (Unidade: {unidade_item_raw}) não encontrado no inventário.", "danger")

    return redirect(url_for('cozinha'))

# --- ROTAS DE PROGRESSO ---

@app.route("/progresso")
def progresso():
    """Renderiza a página com a tabela de progresso completa."""
    pessoas = carregar_nomes()
    progresso_por_pessoa = carregar_progresso()
    progresso_modelo = carregar_progresso_modelo()

    print("Conteúdo de progresso_modelo.json carregado:", progresso_modelo)

    areas = []
    trilhos = {} # {area: [trilho1, trilho2, ...]}

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
        # Se a pessoa ainda não tiver dados de progresso, inicializa com o modelo.
        # Usa deepcopy para garantir que alterações não afetem o modelo ou outras pessoas.
        if nome_pessoa not in progresso_por_pessoa:
            progresso_por_pessoa[nome_pessoa] = copy.deepcopy(progresso_modelo)
            
        dados_pessoa = progresso_por_pessoa[nome_pessoa]
        
        # Calcula o nível da pessoa
        dados_pessoa_bool = calcular_progresso_bool_do_dicionario(dados_pessoa)
        nivel_atual = calcular_nivel(dados_pessoa_bool, progresso_modelo)
        
        # Adiciona o nível calculado aos dados da pessoa para ser usado no template
        dados_pessoa['nivel'] = nivel_atual
        dados_para_tabela[nome_pessoa] = dados_pessoa
        
    # Salva o progresso inicializado se for a primeira vez
    guardar_progresso(progresso_por_pessoa)
    
    return render_template(
        "progresso.html",
        progresso=dados_para_tabela,
        areas=areas,
        trilhos=trilhos,
        progresso_modelo=progresso_modelo,
        messages=session.pop('messages', [])
    )

@app.route("/atualizar_objetivo", methods=["POST"])
def atualizar_objetivo():
    """Atualiza o estado de um objetivo de progresso (usado via AJAX)."""
    
    # Simulação de autenticação: Defina 'Chefe' na sessão para testar.
    # Ex: session['username'] = 'Chefe'
    if session.get('username') != 'Chefe':
        return jsonify({"status": "error", "message": "Apenas o Chefe pode alterar o progresso."}), 403

    data = request.get_json()
    nome = data.get("nome")
    area = data.get("area")
    trilho = data.get("trilho")
    objetivo = data.get("objetivo")
    novo_estado = data.get("estado") 

    if not all([nome, area, trilho, objetivo, novo_estado]):
        return jsonify({"status": "error", "message": "Dados incompletos."}), 400

    progresso_raw = carregar_progresso()
    progresso_modelo = carregar_progresso_modelo()

    # Garante que a pessoa existe e tem a sua própria cópia do modelo
    if nome not in progresso_raw:
        progresso_raw[nome] = copy.deepcopy(progresso_modelo)
    
    try:
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
    except KeyError:
        return jsonify({"status": "error", "message": "Estrutura de progresso inválida (Area, Trilho ou Objetivo não encontrado)."}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erro interno: {e}"}), 500


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

    # Nota: Assumimos que existe o template 'secretaria.html'
    return render_template("secretaria.html", atas=atas, outros_documentos=outros_documentos)

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
    # Nota: Assumimos que existe o template 'atividades_calendario.html'
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
    

# Rota para visualizar as contas individuais
@app.route("/contas")
def contas_individuais():
    nomes = carregar_nomes()  # Pega todos os nomes das tribos
    # Carrega valores do ficheiro contas.json
    if os.path.exists(FICHEIRO_CONTAS):
        with open(FICHEIRO_CONTAS, "r", encoding="utf-8") as f:
            try:
                contas = json.load(f)
            except json.JSONDecodeError:
                contas = {}
    else:
        contas = {}

    # Garante que todos os nomes têm um valor inicial (0.0)
    for nome in nomes:
        if nome not in contas:
            contas[nome] = 0.0

    # Nota: Assumimos que existe o template 'contas.html'
    return render_template("contas.html", nomes=nomes, contas=contas)


# Rota para atualizar o valor de uma conta (restrito ao 'Chefe')
@app.route("/atualizar_valor/<nome>", methods=["POST"])
def atualizar_valor(nome):
    if session.get("username") != "Chefe":
        flash("Acesso negado. Apenas o Chefe pode atualizar valores.", "danger")
        return redirect(url_for("contas_individuais"))

    novo_valor = request.form.get("valor")
    if novo_valor:
        try:
            # Tenta converter para float
            novo_valor = float(novo_valor)
            
            # Carrega o estado atual das contas
            if os.path.exists(FICHEIRO_CONTAS):
                with open(FICHEIRO_CONTAS, "r", encoding="utf-8") as f:
                    try:
                        contas = json.load(f)
                    except json.JSONDecodeError:
                        contas = {}
            else:
                contas = {}

            # Atualiza o valor
            contas[nome] = novo_valor

            # Salva no arquivo JSON
            with open(FICHEIRO_CONTAS, "w", encoding="utf-8") as f:
                json.dump(contas, f, indent=4, ensure_ascii=False)
            
            flash(f"Valor de {nome} atualizado com sucesso para {novo_valor:.2f}.", "success")
        except ValueError:
            flash("Valor inválido fornecido. Use apenas números.", "danger")
        except Exception as e:
            flash(f"Erro ao salvar o valor: {e}", "danger")
            
    else:
        flash("Nenhum valor fornecido.", "warning")

    return redirect(url_for("contas_individuais"))


# --- Bloco de Inicialização da Aplicação ---
if __name__ == '__main__':
    # Obtém o número da porta da variável de ambiente,
    # caso não exista, usa a porta 5000 por defeito.
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)