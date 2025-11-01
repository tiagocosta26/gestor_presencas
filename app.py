from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, session, flash
import csv, os, re, json
from collections import defaultdict
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from flask_bcrypt import Bcrypt
import copy
import uuid
from icalendar import Calendar, Event
from flask import make_response

#MEGA ALTERAÇÂOOOOOOOOO

# --- IMPORTAÇÕES DE BASE DE DADOS ---
from flask_sqlalchemy import SQLAlchemy 
from sqlalchemy import JSON 
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy import event, DDL
# ------------------------------------------

import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

print("DEBUG DATABASE_URL:", os.environ.get('EXTERNAL_DATABASE_URL'))
"""
# Configurar Cloudinary
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True
)
"""
"""
def upload_para_cloudinary(file, pasta="clan"):
    
    Faz upload de um ficheiro para o Cloudinary
    
    Args:
        file: Ficheiro do request.files
        pasta: Nome da pasta no Cloudinary (ex: 'atas', 'receitas', 'comprovativos')
    
    Returns:
        URL pública do ficheiro ou None se falhar
    
    try:
        # Upload para Cloudinary
        resultado = cloudinary.uploader.upload(
            file,
            folder=f"clan/{pasta}",  # Organiza em pastas
            resource_type="auto"  # Aceita qualquer tipo de ficheiro
        )
        return resultado['secure_url']
    except Exception as e:
        print(f"Erro ao fazer upload para Cloudinary: {e}")
        return None
"""

app = Flask(__name__)
bcrypt = Bcrypt(app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'uma_chave_segura_para_as_sessoes')

# --- CONFIGURAÇÃO DE BASE DE DADOS ---
# --- CONFIGURAÇÃO DE BASE DE DADOS ---
database_url = os.environ.get('EXTERNAL_DATABASE_URL')

if database_url:
    # Produção: PostgreSQL
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    print("✅ Usando PostgreSQL externo")
else:
    # Desenvolvimento: SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clan_local.db'
    print("⚠️  Usando SQLite (teste local)")

print("URI da base de dados a ser usada:", app.config['SQLALCHEMY_DATABASE_URI'])

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Diretórios para ficheiros
DIRETORIO_PRESENCAS = "registos"
DIRETORIO_TESOURARIA = "tesouraria"
DIRETORIO_UPLOADS = "uploads" 
DIRETORIO_RECEITAS = os.path.join(DIRETORIO_UPLOADS, 'receitas')
DIRETORIO_UPLOADS_COZINHA = os.path.join(DIRETORIO_UPLOADS, 'cozinha')
DIRETORIO_ATAS = os.path.join(DIRETORIO_UPLOADS, 'atas')
DIRETORIO_OUTROS_DOCS = os.path.join(DIRETORIO_UPLOADS, 'outros')

# Criar diretórios
for dir_path in [DIRETORIO_PRESENCAS, DIRETORIO_TESOURARIA, DIRETORIO_UPLOADS, 
                 DIRETORIO_RECEITAS, DIRETORIO_ATAS, DIRETORIO_OUTROS_DOCS, 
                 DIRETORIO_UPLOADS_COZINHA]:
    os.makedirs(dir_path, exist_ok=True)

app.config['UPLOAD_FOLDER'] = DIRETORIO_UPLOADS



# --- MODELOS DE BASE DE DADOS ---


class Cargo(db.Model):
    __tablename__ = 'cargos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    cor = db.Column(db.String(7))

class PessoaCargo(db.Model):
    __tablename__ = 'pessoa_cargo'
    pessoa_id = db.Column(db.Integer, db.ForeignKey('pessoas.id'), primary_key=True)
    cargo_nome = db.Column(db.String(80), db.ForeignKey('cargos.nome'), primary_key=True)
    pessoa = db.relationship("Pessoa", back_populates="cargos")
    cargo = db.relationship("Cargo") 

class Tribo(db.Model):
    __tablename__ = 'tribos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    membros = db.relationship('Pessoa', backref='tribo', lazy=True, 
                             order_by='Pessoa.ordem', cascade="all, delete-orphan")  # ✅ MUDADO


class Pessoa(db.Model):
    __tablename__ = 'pessoas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    tribo_id = db.Column(db.Integer, db.ForeignKey('tribos.id'), nullable=False)
    ordem = db.Column(db.Integer, default=0)  # ✅ NOVO CAMPO
    cargos = db.relationship('PessoaCargo', back_populates='pessoa', 
                            cascade="all, delete-orphan")

class Utilizador(db.Model):
    __tablename__ = 'utilizadores'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

class FolhaCaixa(db.Model):
    __tablename__ = 'folha_caixa'
    id = db.Column(db.Integer, primary_key=True)
    entidade_nome = db.Column(db.String(100), nullable=False)
    data = db.Column(db.Date, nullable=False)
    descricao = db.Column(db.String(255))
    tipo = db.Column(db.String(10), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    comprovativo_url = db.Column(db.String(255), nullable=True)
    __table_args__ = (db.Index('idx_entidade_data', 'entidade_nome', 'data'),)

class Item(db.Model):
    __tablename__ = 'itens'
    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(50), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.String(50))
    localizacao = db.Column(db.String(100))
    tribo_clan = db.Column(db.String(100))
    observacoes = db.Column(db.Text)
    comprovativo = db.Column(db.String(255))

class CondicaoSaude(db.Model):
    __tablename__ = 'condicoes_saude'
    id = db.Column(db.Integer, primary_key=True)
    pessoa_nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    detalhe = db.Column(db.Text, nullable=False)

class Receita(db.Model):
    __tablename__ = 'receitas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    ingredientes = db.Column(JSON)
    instrucoes = db.Column(db.Text)
    imagem_url = db.Column(db.String(255))
    link_ficheiro = db.Column(db.String(255))
    tempo_preparacao = db.Column(db.String(50))
    dificuldade = db.Column(db.String(20))
    porcoes_base = db.Column(db.String(20))

class Atividade(db.Model):
    __tablename__ = 'atividades_calendario'
    id = db.Column(db.String(36), primary_key=True)
    titulo = db.Column(db.String(255), nullable=False)
    data_inicio = db.Column(db.DateTime, nullable=False)
    data_fim = db.Column(db.DateTime, nullable=False)
    descricao = db.Column(db.Text)
    tipo = db.Column(db.String(50))
    all_day = db.Column(db.Boolean, default=False)

class Conta(db.Model):
    __tablename__ = 'contas'
    id = db.Column(db.Integer, primary_key=True)
    pessoa_nome = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.Float, default=0.0)

class Progresso(db.Model):
    __tablename__ = 'progresso'
    id = db.Column(db.Integer, primary_key=True)  # ← NOVO: ID independente
    pessoa_id = db.Column(db.Integer, db.ForeignKey('pessoas.id', ondelete='CASCADE'), nullable=False)
    pessoa = db.relationship('Pessoa', backref='progresso_rel')
    dados_progresso = db.Column(JSON)
    
    # Índice único para garantir uma entrada por pessoa
    __table_args__ = (db.UniqueConstraint('pessoa_id', name='uq_pessoa_id'),)
    
class ProgressoModelo(db.Model):
    __tablename__ = 'progresso_modelo'
    id = db.Column(db.Integer, primary_key=True)
    modelo = db.Column(JSON)

# --- FUNÇÕES AUXILIARES ---

def limpar_nome(nome):
    nome_ficheiro = nome.replace('/', '-')
    nome_ficheiro = re.sub(r'[^A-Za-z0-9áéíóúãõàèùçÁÉÍÓÚÀÈÙÇ_\-@ ]', '_', nome_ficheiro)
    return nome_ficheiro

def get_cargos_list():
    cargos_obj = Cargo.query.all()
    return {c.nome: c.cor for c in cargos_obj}

def carregar_cargos():
    return get_cargos_list()

def get_tribos_e_membros():
    tribos_obj = Tribo.query.options(
        db.joinedload(Tribo.membros).joinedload(Pessoa.cargos).joinedload(PessoaCargo.cargo)
    ).all()
    tribos_dict = {}
    cargos_disponiveis = get_cargos_list()
    cargo_ordem = {cargo: i for i, cargo in enumerate(cargos_disponiveis)}

    for tribo in tribos_obj:
        membros_list = []
        for pessoa in tribo.membros:
            cargos_nomes = [pc.cargo.nome for pc in pessoa.cargos]
            cargos_nomes.sort(key=lambda c: cargo_ordem.get(c, float('inf')))
            membros_list.append({
                "nome": pessoa.nome, 
                "cargo": cargos_nomes,
                "id": pessoa.id
            })
        tribos_dict[tribo.nome] = membros_list
    return tribos_dict

def carregar_tribos():
    return get_tribos_e_membros()

def carregar_nomes():
    # Carrega nomes da base de dados, ordenados pelo ID para manter a ordem de inserção (não alfabética).
    # 💥 CORREÇÃO DE ORDENAÇÃO: Ordena explicitamente por ID para evitar a ordenação alfabética padrão da BD.
    pessoas = Pessoa.query.with_entities(Pessoa.nome).order_by(Pessoa.tribo_id, Pessoa.ordem).all()
    return [nome[0] for nome in pessoas]

def carregar_utilizadores():
    utilizadores_obj = Utilizador.query.all()
    return {u.username: {'password_hash': u.password_hash} for u in utilizadores_obj}

def carregar_folha_caixa(entidade):
    folha_caixa = FolhaCaixa.query.filter_by(entidade_nome=entidade).order_by(
        FolhaCaixa.data.desc()).all()
    transacoes_list = []
    for t in folha_caixa:
        transacoes_list.append({
            'id': t.id,
            'data': t.data.isoformat(),
            'descricao': t.descricao,
            'tipo': t.tipo,
            'valor': t.valor,
            'comprovativo': t.comprovativo_url
        })
    return transacoes_list

def carregar_material():
    itens = Item.query.filter_by(categoria='Material').all()
    return [{'nome': i.nome, 'quantidade': i.quantidade, 'localizacao': i.localizacao or '',
             'tribo_clan': i.tribo_clan or '', 'observacoes': i.observacoes or ''} for i in itens]

def carregar_farmacia():
    itens = Item.query.filter_by(categoria='Farmácia').all()
    return [{'nome': i.nome, 'quantidade': i.quantidade, 'localizacao': i.localizacao or '',
             'tribo_clan': i.tribo_clan or '', 'observacoes': i.observacoes or ''} for i in itens]

def carregar_inventario_cozinha():
    itens = Item.query.filter_by(categoria='Cozinha').all()
    result = []
    for i in itens:
        result.append({
            'nome': i.nome,
            'quantidade': i.quantidade or '',
            'unidade': i.localizacao or '',
            'categoria': i.tribo_clan or '',
            'comprovativo': i.comprovativo or ''
        })
    return result

def carregar_alergias():
    condicoes = CondicaoSaude.query.filter_by(tipo='Alergia').all()
    alergias_dict = {}
    for c in condicoes:
        if c.pessoa_nome not in alergias_dict:
            alergias_dict[c.pessoa_nome] = c.detalhe
        else:
            alergias_dict[c.pessoa_nome] += ',' + c.detalhe
    return alergias_dict

def carregar_condicoes():
    condicoes = CondicaoSaude.query.filter_by(tipo='Condição').all()
    condicoes_dict = {}
    for c in condicoes:
        if c.pessoa_nome not in condicoes_dict:
            condicoes_dict[c.pessoa_nome] = c.detalhe
        else:
            condicoes_dict[c.pessoa_nome] += ',' + c.detalhe
    return condicoes_dict

def carregar_receitas():
    receitas_obj = Receita.query.all()
    receitas_list = []
    for r in receitas_obj:
        receita_dict = {
            'nome': r.nome,
            'ingredientes': r.ingredientes or [],
            'instrucoes': r.instrucoes or '',
            'imagem_url': r.imagem_url,
            'link_ficheiro': r.link_ficheiro,
            'tempo_preparacao': r.tempo_preparacao,
            'dificuldade': r.dificuldade,
            'porcoes_base': r.porcoes_base
        }
        receitas_list.append(receita_dict)
    return receitas_list

def ler_contas():
    contas_obj = Conta.query.all()
    return {c.pessoa_nome: c.valor for c in contas_obj}

def carregar_progresso():
    """Carrega o progresso de todas as pessoas da BD."""
    progresso_obj = Progresso.query.join(Pessoa).all()
    
    dados_progresso = {}
    for p in progresso_obj:
        # Limpa o nome da pessoa
        nome_pessoa_limpo = p.pessoa.nome.strip()
        
        # ✅ CORREÇÃO: O PostgreSQL já devolve JSON como dict, não precisa json.loads()
        if p.dados_progresso:
            # Se já é um dicionário, usa diretamente
            if isinstance(p.dados_progresso, dict):
                dados_progresso[nome_pessoa_limpo] = p.dados_progresso
                print(f"✅ {nome_pessoa_limpo} - dados carregados (dict)")
            else:
                # Se for string, faz parse
                try:
                    dados_progresso[nome_pessoa_limpo] = json.loads(p.dados_progresso)
                    print(f"✅ {nome_pessoa_limpo} - dados carregados (JSON string)")
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"⚠️ {nome_pessoa_limpo} - erro ao desserializar: {e}")
                    dados_progresso[nome_pessoa_limpo] = {}
        else:
            # Dados vazios
            dados_progresso[nome_pessoa_limpo] = {}
            print(f"⚠️ {nome_pessoa_limpo} - sem dados, usando dict vazio")
    
    return dados_progresso

def carregar_progresso_modelo():
    modelo = ProgressoModelo.query.first()
    return modelo.modelo if modelo else {}

def carregar_atividades_calendario():
    atividades_obj = Atividade.query.order_by(Atividade.data_inicio).all()
    atividades_list = []
    for a in atividades_obj:
        atividades_list.append({
            'id': a.id,
            'title': a.titulo,
            'start': a.data_inicio.isoformat(),
            'end': a.data_fim.isoformat(),
            'details': a.descricao or '',
            'type': a.tipo or '',
            'allDay': a.all_day
        })
    return atividades_list

# Funções obsoletas
def guardar_tribos(tribos): pass
def guardar_utilizadores(utilizadores): pass
def guardar_folha_caixa(entidade, folha_caixa): pass
def guardar_material(material): pass
def guardar_farmacia(farmacia): pass
def guardar_inventario_cozinha(inventario): pass
def guardar_alergias(alergias): pass
def guardar_condicoes(condicoes): pass
def guardar_receitas(receitas): pass
def gravar_contas(contas): pass
def guardar_progresso(dados): pass
def guardar_atividades_calendario(atividades): pass

# --- FUNÇÕES DE PROGRESSO ---

@app.template_global()
def calcular_progresso_bool_do_dicionario(obj):
    """
    Converte um dicionário de progresso de "feito"/"pendente" para True/False.
    """
    if isinstance(obj, dict):
        # Percorre o dicionário recursivamente
        return {k: calcular_progresso_bool_do_dicionario(v) for k, v in obj.items()}
    elif isinstance(obj, str):
        # 🌟 CORREÇÃO DE LÓGICA: Reconhece 'concluído' E 'feito' como sucesso (True)
        return obj in ["concluído", "feito"]
    else:
        # CORREÇÃO: Devolve um dicionário vazio em vez de False para evitar o AttributeError no nível superior 
        # (se a função for chamada com None, por exemplo).
        return {} 
        
@app.template_global()
def calcular_nivel(dados_pessoa_bool, trilhos_por_area):

    # 🚨 CORREÇÃO CRÍTICA (Linha 346): Evita 'bool' object has no attribute 'get'
    if not isinstance(dados_pessoa_bool, dict):
        # Se os dados não forem um dicionário (ex: False ou None), assume-se o nível base para evitar o crash.
        return "Comunidade"
    
    try:
        trilhos_concluidos_por_area = {}
        
        # 1. Conta quantos trilhos foram concluídos em cada área
        for area_nome, trilhos_da_area in trilhos_por_area.items():
            count_trilhos_concluidos = 0
            
            # Itera sobre cada trilho da área
            for trilho_nome, objetivos_do_trilho in trilhos_da_area.items():
                trilho_completo = True
                
                # Acede aos dados da pessoa para este trilho. A verificação acima garante que dados_pessoa_bool é um dict.
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
        todos_concluidos = True
        for area in trilhos_por_area:
            total_trilhos = len(trilhos_por_area[area])
            if total_trilhos == 0 or trilhos_concluidos_por_area.get(area, 0) != total_trilhos:
                todos_concluidos = False
                break
                
        if todos_concluidos:
            return "Anilha de Mérito"
        
        # Condição para Etapa 'Partida': 2 trilhos concluídos em cada área.
        dois_por_area = all(trilhos_concluidos_por_area.get(area, 0) >= 2 for area in trilhos_por_area)
        if dois_por_area:
            return "Partida"
            
        # Condição para Etapa 'Serviço': 1 trilho concluído em cada área.
        um_por_area = all(trilhos_concluidos_por_area.get(area, 0) >= 1 for area in trilhos_por_area)
        if um_por_area:
            return "Serviço"
            
        # Se nenhuma das condições for satisfeita, o membro fica na Etapa 'Comunidade'
        return "Comunidade"

    except Exception as e:
        # Se ocorrer qualquer outro erro inesperado (KeyError, TypeError, etc.), 
        # impede que o template falhe com Internal Server Error.
        return "Comunidade"
    
def init_default_data():
    """Inicializa dados padrão (Tribos, Cargos) se estiverem vazios"""
    try:
        # Verifica se já existem cargos
        if Cargo.query.count() == 0:
            print("Criando cargos padrão...")
            cargos_padrão = [
                Cargo(nome='Guia', cor='#bb2124'),
                Cargo(nome='Sub-Guia', cor='#bb2124'),
                Cargo(nome='Tesoureiro', cor='#28a745'),
                Cargo(nome='Secretário', cor='#007bff'),
                Cargo(nome='Animador', cor='#ffa500'),
                Cargo(nome='Cozinheiro', cor='#ffde21'),
                Cargo(nome='Socorrista', cor='#ff0000'),
                Cargo(nome='Guarda-Material', cor='#7c3a00'),
                Cargo(nome='Relações Públicas', cor='#87cefa'),
            ]
            for cargo in cargos_padrão:
                db.session.add(cargo)
            db.session.commit()
            print("✅ Cargos padrão criados.")
            
    except Exception as e:
        print(f"⚠️ Erro ao inicializar dados padrão: {e}")
        db.session.rollback()

# --- INICIALIZAÇÃO ---

def migrate_progresso_table():
    """
    Migra a tabela progresso do schema antigo (pessoa_id como PK)
    para o novo schema (id como PK, pessoa_id como FK normal)
    """
    from sqlalchemy import text
    
    try:
        with app.app_context():
            # Verifica se a coluna 'id' já existe
            result = db.session.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name='progresso' AND column_name='id'")
            )
            if result.fetchone():
                print("✅ Tabela progresso já tem coluna 'id'. Migration não necessária.")
                return
            
            print("🔄 Migrando tabela progresso...")
            
            # Se chegou aqui, precisa fazer a migração
            # Backup dos dados antigos
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS progresso_backup AS 
                SELECT * FROM progresso
            """))
            
            # Drop da tabela antiga
            db.session.execute(text("DROP TABLE IF EXISTS progresso CASCADE"))
            
            # Commit para aplicar as mudanças
            db.session.commit()
            
            print("✅ Tabela progresso migrada com sucesso. Será recriada com o novo schema.")
            
    except Exception as e:
        print(f"⚠️ Aviso durante migration: {e}")
        try:
            db.session.rollback()
        except:
            pass


def criar_modelo_padrao():
    """
    Cria um modelo de progresso padrão com áreas, trilhos e objetivos.
    """
    modelo = {
            "Físico": {
                "Desempenho": {
                "Exercício": "não"
                },
                "Auto-Conhecimento": {
                "Relação com o corpo": "não",
                "Diferenças fisiológicas": "não"
                },
                "Bem-estar físico": {
                "Equilíbrio": "não",
                "Higiene": "não",
                "Comportamentos de risco": "não"
                }
            },
            "Afetivo": {
                "Relacionamento e sensibilidade": {
                "Afetos": "não",
                "Respeito": "não",
                "Sexualidade e relação amorosa": "não"
                },
                "Emocional": {
                "Emoções": "não"
                },
                "Autoestima": {
                "Personalidade": "não",
                "Confiança": "não"
                }
            },
            "Caráter": {
                "Autonomia": {
                "Valores": "não",
                "Decisão": "não",
                "Aperfeiçoamento": "não"
                },
                "Responsabilidade": {
                "Compromisso": "não",
                "Perseverança": "não",
                "Responsabilidade": "não"
                },
                "Coerência": {
                "Consistência": "não",
                "Coerência": "não"
                }
            },
            "Espiritual": {
                "Descoberta": {
                "Pai/Felicidade": "não",
                "Filho/Amor": "não",
                "Espírito Santo/Igreja": "não"
                },
                "Aprofundamento": {
                "Oração": "não",
                "Transformação": "não",
                "Identidade": "não"
                },
                "Serviço": {
                "Unidade": "não",
                "Missão": "não"
                }
            },
            "Intelectual": {
                "Procura do Conhecimento": {
                "Aprendizagem": "não",
                "Filtrar": "não",
                "Rumo": "não"
                },
                "Resolução de Problemas": {
                "Adaptação": "não",
                "Estratégia": "não"
                },
                "Criatividade e Expressão": {
                "Criatividade": "não",
                "Expressividade": "não"
                }
            },
            "Social": {
                "Exercer ativamente a cidadania": {
                "Cidadania": "não",
                "Participação": "não",
                "Democracia": "não"
                },
                "Solidariedade e Tolerância": {
                "Serviço": "não",
                "Tolerância": "não"
                },
                "Interação e Cooperação": {
                "Espírito de Equipa": "não",
                "Liderança": "não"
                }
            }
            }
    return modelo


def init_db():
    """Cria todas as tabelas e inicializa dados padrão, se necessário."""
    db.create_all()

    # ✅ NOVO: Inicializar dados padrão (tribos, cargos)
    init_default_data()

    # ✅ NOVO: Verificar e criar modelo de progresso
    try:
        print("🔄 Verificando modelo de progresso...")
        
        # 1. Criar modelo se não existir
        if ProgressoModelo.query.count() == 0:
            print("  → Criando modelo de progresso...")
            modelo_padrao = criar_modelo_padrao()
            novo_modelo = ProgressoModelo(modelo=modelo_padrao)
            db.session.add(novo_modelo)
            db.session.commit()
            print("  ✅ Modelo criado")
        
        # 2. Preencher progresso de todas as pessoas
        modelo = ProgressoModelo.query.first()
        modelo_conteudo = modelo.modelo if modelo else criar_modelo_padrao()
        
        pessoas = Pessoa.query.all()
        for pessoa in pessoas:
            progresso = Progresso.query.filter_by(pessoa_id=pessoa.id).first()
            
            if progresso and (not progresso.dados_progresso or progresso.dados_progresso == {}):
                print(f"  → Preenchendo {pessoa.nome}...")
                progresso.dados_progresso = copy.deepcopy(modelo_conteudo)
                db.session.add(progresso)
        
        db.session.commit()
        print("✅ Modelo de progresso verificado/inicializado")
        
    except Exception as e:
        print(f"⚠️ Aviso ao inicializar modelo de progresso: {e}")
        db.session.rollback()

    # --- Garante utilizadores padrão ---
    utilizadores_a_eliminar = ['Chefe', 'Clan']
    for username in utilizadores_a_eliminar:
        u = Utilizador.query.filter_by(username=username).first()
        if u:
            db.session.delete(u)
    db.session.commit()

    hashed_chefe = bcrypt.generate_password_hash('Chefe').decode('utf-8')
    db.session.add(Utilizador(username='Chefe', password_hash=hashed_chefe))

    hashed_clan = bcrypt.generate_password_hash('Clan').decode('utf-8')
    db.session.add(Utilizador(username='Clan', password_hash=hashed_clan))

    db.session.commit()
    print("✅ Base de dados e utilizadores padrão inicializados.")


# --- Garantir criação da base de dados e init mesmo fora do __main__ ---
with app.app_context():
    try:
        # 1. Primeiro faz a migration (se necessário)
        migrate_progresso_table()
        
        # 2. Depois cria as tabelas com o novo schema
        db.create_all()
        
        # 3. Depois inicializa os dados padrão
        init_db()
        
        print("✅ Base de dados pronta para uso.")
    except Exception as e:
        import traceback
        print("❌ Erro ao criar/atualizar a base de dados:")
        traceback.print_exc()


# --- ROTAS ---

@app.route("/admin/fix_progresso")
def admin_fix_progresso():
    """
    Rota para corrigir o sistema de progresso.
    Só acessível ao Chefe.
    """
    if session.get('username') != 'Chefe':
        return "Acesso negado", 403
    
    try:
        print("\n" + "="*70)
        print("🔧 CORRIGINDO SISTEMA DE PROGRESSO")
        print("="*70)
        
        # 1. Eliminar modelo antigo se existir
        print("\n1️⃣ Limpando modelo antigo...")
        ProgressoModelo.query.delete()
        db.session.commit()
        print("   ✅ Modelo antigo removido")
        
        # 2. Criar modelo novo
        print("\n2️⃣ Criando modelo novo...")
        modelo_padrao = criar_modelo_padrao()
        novo_modelo = ProgressoModelo(modelo=modelo_padrao)
        db.session.add(novo_modelo)
        db.session.commit()
        print("   ✅ Modelo criado")
        print(f"   Áreas: {list(modelo_padrao.keys())}")
        
        # 3. Limpar progresso de todas as pessoas
        print("\n3️⃣ Limpando progresso antigo...")
        Progresso.query.delete()
        db.session.commit()
        print("   ✅ Progresso antigo removido")
        
        # 4. Recrear progresso para todas as pessoas com o modelo novo
        print("\n4️⃣ Criando novo progresso para cada pessoa...")
        pessoas = Pessoa.query.all()
        
        for pessoa in pessoas:
            novo_progresso = Progresso(
                pessoa_id=pessoa.id,
                dados_progresso=copy.deepcopy(modelo_padrao)
            )
            db.session.add(novo_progresso)
            print(f"   ✅ {pessoa.nome}")
        
        db.session.commit()
        print("\n" + "="*70)
        print(f"✅ SUCESSO! {len(pessoas)} pessoas inicializadas")
        print("="*70 + "\n")
        
        return f"""
        <h1>✅ Sistema de Progresso Corrigido!</h1>
        <p><strong>{len(pessoas)} pessoas</strong> foram inicializadas com o modelo de progresso.</p>
        <p><a href="/progresso"><button>Ver Progresso</button></a></p>
        """
    
    except Exception as e:
        db.session.rollback()
        import traceback
        erro = traceback.format_exc()
        print(f"\n❌ ERRO: {e}\n")
        return f"<h1>❌ Erro!</h1><pre>{erro}</pre>"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/gestao_presencas", methods=["GET", "POST"])
def presencas():
    """Gestão de presenças em atividades."""
    tribos = carregar_tribos()
    
    if request.method == "POST":
        try:
            atividade = request.form.get("atividade", "").strip()
            data_inicio = request.form.get("data_inicio", "").strip()
            data_fim = request.form.get("data_fim", "").strip()
            tribos_selecionadas = request.form.get("tribos_selecionadas", "").split(",")
            
            if not all([atividade, data_inicio, data_fim]):
                flash("Todos os campos são obrigatórios.", "danger")
                return redirect(url_for("presencas"))
            
            atividade_limpa = limpar_nome(atividade)
            caminho = os.path.join(
                DIRETORIO_PRESENCAS, 
                f"{atividade_limpa}_{data_inicio}_a_{data_fim}.csv"
            )
            
            # Criar diretório se não existir
            os.makedirs(DIRETORIO_PRESENCAS, exist_ok=True)
            
            with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Atividade", "Data Início", "Data Fim", "Tribo", 
                    "Elemento", "Cargos", "Presente"
                ])
                
                for tribo_nome in tribos_selecionadas:
                    if not tribo_nome.strip():
                        continue
                    
                    membros = tribos.get(tribo_nome.strip(), [])
                    for membro in membros:
                        nome = membro['nome']
                        cargos_list = membro.get('cargo', [])
                        cargos_str = ', '.join(cargos_list)
                        presente = "Sim" if request.form.get(f"presenca_{nome}") == "Sim" else "Não"
                        
                        writer.writerow([
                            atividade, data_inicio, data_fim, 
                            tribo_nome.strip(), nome, cargos_str, presente
                        ])
            
            print(f"✅ Atividade '{atividade}' criada com sucesso")
            flash(f"Atividade '{atividade}' registada com sucesso!", "success")
            return redirect(url_for("atividades"))
        
        except Exception as e:
            import traceback
            print(f"❌ Erro ao criar atividade: {e}")
            traceback.print_exc()
            flash(f"Erro ao criar atividade: {e}", "danger")
            return redirect(url_for("presencas"))
    
    from datetime import date
    hoje = date.today().isoformat()
    return render_template("gestao_presencas.html", hoje=hoje, tribos=tribos)


@app.route("/atividades")
def atividades():
    """Lista todas as atividades de presença."""
    try:
        ficheiros = [
            f for f in os.listdir(DIRETORIO_PRESENCAS) 
            if f.endswith(".csv")
        ]
    except FileNotFoundError:
        ficheiros = []
    
    atividades_agrupadas = defaultdict(list)

    def extrair_titulo_e_data(ficheiro):
        """Extrai título e data do nome do ficheiro."""
        nome_base = ficheiro.rsplit('.', 1)[0]
        partes = nome_base.split('_')
        data_atividade = None
        indice_data = -1
        
        for i in range(1, len(partes)):
            try:
                data_atividade = datetime.strptime(partes[i].strip(), "%Y-%m-%d")
                indice_data = i
                break
            except ValueError:
                continue
        
        if data_atividade and indice_data != -1:
            titulo_bruto_list = partes[0:indice_data]
            titulo_bruto = '_'.join(titulo_bruto_list).strip()
            titulo_limpo = (
                titulo_bruto.replace(' _ ', ' + ')
                .replace('_', ' ')
                .strip()
            )
            return data_atividade, titulo_limpo
        return None, None

    for ficheiro in ficheiros:
        data_inicio, titulo = extrair_titulo_e_data(ficheiro)
        if data_inicio and titulo:
            mes_ano = data_inicio.strftime("%Y-%m")
            atividades_agrupadas[mes_ano].append((data_inicio, ficheiro, titulo))

    meses_ordenados = sorted(atividades_agrupadas.keys(), reverse=True)
    for mes in meses_ordenados:
        atividades_agrupadas[mes].sort(key=lambda x: x[0], reverse=True)
        atividades_agrupadas[mes] = [(f[1], f[2]) for f in atividades_agrupadas[mes]]

    return render_template(
        "atividades.html", 
        atividades_agrupadas=atividades_agrupadas, 
        meses_ordenados=meses_ordenados
    )


@app.route('/eliminar_atividade/<nome_ficheiro>', methods=['POST'])
def eliminar_atividade(nome_ficheiro):
    """Elimina uma atividade."""
    if session.get('username') not in ['Chefe', 'Clan']:
        flash("Não tem permissão para eliminar atividades.", "danger")
        return redirect(url_for('atividades'))
    
    try:
        caminho_ficheiro = os.path.join(DIRETORIO_PRESENCAS, nome_ficheiro)
        if os.path.exists(caminho_ficheiro):
            os.remove(caminho_ficheiro)
            print(f"✅ Atividade '{nome_ficheiro}' eliminada")
            flash(f"Atividade eliminada com sucesso.", "success")
        else:
            flash("Ficheiro não encontrado.", "danger")
    except Exception as e:
        import traceback
        print(f"❌ Erro ao eliminar atividade: {e}")
        traceback.print_exc()
        flash(f"Erro ao eliminar: {e}", "danger")
    
    return redirect(url_for('atividades'))


@app.route("/atividade/<ficheiro>")
def ver_atividade(ficheiro):
    """Vê detalhes de uma atividade."""
    cargos_disponiveis = carregar_cargos()
    caminho = os.path.join(DIRETORIO_PRESENCAS, ficheiro)
    dados = defaultdict(list)
    
    if os.path.exists(caminho):
        try:
            with open(caminho, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for linha in reader:
                    if 'Tribo' in linha and 'Elemento' in linha:
                        tribo_nome = linha['Tribo']
                        nome = linha['Elemento']
                        cargos_str = linha.get('Cargos', '')
                        cargos_list = [
                            c.strip() for c in cargos_str.split(',')
                        ] if cargos_str else []
                        presente = linha['Presente']
                        dados[tribo_nome].append({
                            'nome': nome, 
                            'presente': presente, 
                            'cargos': cargos_list
                        })
        except Exception as e:
            print(f"❌ Erro ao ler atividade: {e}")
            flash("Erro ao carregar atividade.", "danger")
    
    match = re.search(
        r'(\d{4}-\d{2}-\d{2})_a_(\d{4}-\d{2}-\d{2})', 
        ficheiro
    )
    if match:
        data_inicio_format = match.group(1)
        data_fim_format = match.group(2)
        data_display = (
            data_inicio_format 
            if data_inicio_format == data_fim_format 
            else f"{data_inicio_format} - {data_fim_format}"
        )
    else:
        data_display = "Data desconhecida"
    
    return render_template(
        "ver_atividade.html", 
        ficheiro=ficheiro, 
        dados=dados,
        data_display=data_display, 
        cargos_disponiveis=cargos_disponiveis
    )


@app.route("/assiduidade", methods=["GET", "POST"])
def assiduidade():
    """Calcula assiduidade por pessoa."""
    ano_selecionado = request.form.get("ano_escutista")
    if ano_selecionado:
        ano_inicio = int(ano_selecionado.split('/')[0])
    else:
        hoje = datetime.now()
        ano_inicio = hoje.year
        if hoje.month < 10 or (hoje.month == 10 and hoje.day < 10):
            ano_inicio -= 1
    
    ano_fim = ano_inicio + 1
    data_inicio = datetime(ano_inicio, 10, 10)
    data_fim = datetime(ano_fim, 10, 9)
    assiduidade_por_tribo = defaultdict(
        lambda: defaultdict(lambda: {'presente': 0, 'total': 0})
    )
    atividades_do_ano = 0
    
    try:
        ficheiros = [
            f for f in os.listdir(DIRETORIO_PRESENCAS) 
            if f.endswith(".csv")
        ]
    except FileNotFoundError:
        ficheiros = []
    
    for ficheiro in ficheiros:
        try:
            data_atividade = None
            partes = ficheiro.split('_')
            for i in range(1, len(partes)):
                try:
                    data_atividade = datetime.strptime(
                        partes[i].strip(), "%Y-%m-%d"
                    )
                    break 
                except ValueError:
                    continue
            
            if data_atividade is None:
                continue
            
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
            print(f"⚠️ Erro ao processar {ficheiro}: {e}")
    
    # Calcular percentagens
    for tribo in assiduidade_por_tribo:
        for elemento in assiduidade_por_tribo[tribo]:
            dados = assiduidade_por_tribo[tribo][elemento]
            if dados['total'] > 0:
                dados['percentagem'] = (dados['presente'] / dados['total']) * 100
            else:
                dados['percentagem'] = 0
    
    # Encontrar anos disponíveis
    anos_disponiveis = set()
    for ficheiro in ficheiros:
        if len(ficheiro.split('_')) > 1:
            try:
                data_atividade = None
                partes = ficheiro.split('_')
                for i in range(1, len(partes)):
                    try:
                        data_atividade = datetime.strptime(
                            partes[i].strip(), "%Y-%m-%d"
                        )
                        break 
                    except ValueError:
                        continue
                
                if data_atividade:
                    ano_inicio_ficheiro = (
                        data_atividade.year 
                        if data_atividade.month >= 10 
                        else data_atividade.year - 1
                    )
                    anos_disponiveis.add(ano_inicio_ficheiro)
            except Exception:
                pass
    
    hoje = datetime.now()
    is_new_scout_year_today = (
        (hoje.month > 10) or (hoje.month == 10 and hoje.day >= 10)
    )
    ano_atual = hoje.year if is_new_scout_year_today else hoje.year - 1
    anos_disponiveis.add(ano_atual)
    anos_disponiveis = sorted(list(anos_disponiveis), reverse=True)
    anos_formatados = [f"{ano}/{ano+1}" for ano in anos_disponiveis]
    
    return render_template(
        "assiduidade.html", 
        assiduidade_por_tribo=assiduidade_por_tribo,
        atividades_do_ano=atividades_do_ano, 
        anos_disponiveis=anos_formatados,
        ano_selecionado=f"{ano_inicio}/{ano_inicio+1}"
    )

@app.route("/gestao_tribos", methods=["GET", "POST"])
def gestao_tribos():
    tribos_dict = carregar_tribos()
    cargos_disponiveis = carregar_cargos()
    cargo_ordem = {cargo: i for i, cargo in enumerate(cargos_disponiveis)}

    if request.method == "POST":
        acao = request.form.get("acao")
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        # ✅ AÇÃO 1: CRIAR TRIBO
        if acao == "criar_tribo":
            nome_tribo = request.form.get("nome_tribo").strip()
            if nome_tribo:
                if Tribo.query.filter_by(nome=nome_tribo).first():
                    flash("Tribo já existe.", "warning")
                else:
                    db.session.add(Tribo(nome=nome_tribo))
                    db.session.commit()
                    #flash(f"Tribo '{nome_tribo}' criada com sucesso!", "success")
            if not is_ajax:
                return redirect(url_for("gestao_tribos"))
            return jsonify({"status": "ok", "nome_tribo": nome_tribo})

        # ✅ AÇÃO 2: REMOVER TRIBO
        elif acao == "remover_tribo":
            nome_tribo = request.form.get("nome_tribo")
            tribo = Tribo.query.filter_by(nome=nome_tribo).first()
            if tribo:
                db.session.delete(tribo)
                db.session.commit()
                #flash(f"Tribo '{nome_tribo}' e todos os seus membros eliminados.", "warning")
            if not is_ajax:
                return redirect(url_for("gestao_tribos"))
            return jsonify({"status": "ok"})

        # ✅ AÇÃO 3: ADICIONAR PESSOA
        elif acao == "adicionar_pessoa":
            tribo_nome = request.form.get("tribo")
            nome_pessoa = request.form.get("nome_pessoa").strip()
            tribo = Tribo.query.filter_by(nome=tribo_nome).first()
            if tribo and nome_pessoa:
                if Pessoa.query.filter_by(nome=nome_pessoa).first():
                    flash(f"A pessoa '{nome_pessoa}' já existe.", "danger")
                else:
                    try:
                        # Cria a pessoa
                        nova_pessoa = Pessoa(nome=nome_pessoa, tribo_id=tribo.id)
                        db.session.add(nova_pessoa)
                        db.session.flush()  # Garante que pessoa.id é gerado
                        
                        # Cria o registo de progresso
                        modelo = carregar_progresso_modelo()
                        novo_progresso = Progresso(
                            pessoa_id=nova_pessoa.id, 
                            dados_progresso=copy.deepcopy(modelo)
                        )
                        db.session.add(novo_progresso)
                        
                        # Cria a conta
                        nova_conta = Conta(pessoa_nome=nome_pessoa, valor=0.0)
                        db.session.add(nova_conta)
                        
                        db.session.commit()
                        nova_pessoa_dict = {"nome": nova_pessoa.nome, "cargo": [], "id": nova_pessoa.id}
                        #flash(f"Pessoa '{nome_pessoa}' adicionada a {tribo_nome}.", "success")
                        if not is_ajax:
                            return redirect(url_for("gestao_tribos", tribo_id=tribo_nome))
                        return jsonify({"status": "ok", "pessoa": nova_pessoa_dict})
                    except Exception as e:
                        db.session.rollback()
                        print(f"ERRO ao adicionar pessoa: {e}")
                        if not is_ajax:
                            return redirect(url_for("gestao_tribos"))
                        return jsonify({"status": "error", "message": str(e)}), 500
            return jsonify({"status": "error", "message": "Tribo ou nome inválidos."}), 400

        # ✅ AÇÃO 4: REMOVER PESSOA (CORRIGIDA)
        elif acao == "remover_pessoa":
            tribo_nome = request.form.get("tribo")
            nome_pessoa = request.form.get("nome_pessoa")
            
            try:
                pessoa = Pessoa.query.filter_by(nome=nome_pessoa).first()
                if pessoa:
                    # 🔴 IMPORTANTE: Ordem de eliminação para evitar cascade errors
                    
                    # 1. Elimina o registo de Progresso PRIMEIRO (evita cascade conflict)
                    Progresso.query.filter_by(pessoa_id=pessoa.id).delete()
                    
                    # 2. Elimina a Conta
                    Conta.query.filter_by(pessoa_nome=nome_pessoa).delete()
                    
                    # 3. Elimina CondicaoSaude
                    CondicaoSaude.query.filter_by(pessoa_nome=nome_pessoa).delete()
                    
                    # 4. A Pessoa é eliminada (cascata automática para PessoaCargo por causa da FK)
                    db.session.delete(pessoa)
                    db.session.commit()
                    
                    #flash(f"Pessoa '{nome_pessoa}' removida.", "warning")
                    print(f"✅ Pessoa '{nome_pessoa}' removida com sucesso.")
                else:
                    print(f"⚠️ Pessoa '{nome_pessoa}' não encontrada.")
                    
            except Exception as e:
                db.session.rollback()
                import traceback
                print(f"❌ ERRO ao remover pessoa '{nome_pessoa}': {e}")
                traceback.print_exc()
                flash(f"Erro ao remover pessoa: {e}", "danger")
                if not is_ajax:
                    return redirect(url_for("gestao_tribos"))
                return jsonify({"status": "error", "message": str(e)}), 500
            
            if not is_ajax:
                return redirect(url_for("gestao_tribos"))
            return jsonify({"status": "ok", "nome_pessoa": nome_pessoa})
        
        # ✅ AÇÃO 5: ADICIONAR CARGO A PESSOA
        elif acao == "adicionar_cargo":
            pessoa_id = request.form.get("pessoa_id") 
            cargo_nome = request.form.get("cargo")
            
            try:
                pessoa = Pessoa.query.get(int(pessoa_id))
            except (TypeError, ValueError):
                pessoa = None
            
            cargo_obj = Cargo.query.filter_by(nome=cargo_nome).first()
            
            if pessoa and cargo_obj:
                try:
                    pessoa_cargo_link = PessoaCargo.query.filter_by(
                        pessoa_id=pessoa.id, 
                        cargo_nome=cargo_nome
                    ).first()
                    
                    if pessoa_cargo_link:
                        # Se já tem o cargo, remove
                        db.session.delete(pessoa_cargo_link)
                    else:
                        # Se não tem, adiciona
                        db.session.add(PessoaCargo(pessoa_id=pessoa.id, cargo_nome=cargo_nome))
                    
                    db.session.commit()
                    
                    # Se for AJAX, devolve o estado atualizado
                    if is_ajax:
                        db.session.refresh(pessoa)
                        cargos_atuais = [pc.cargo.nome for pc in pessoa.cargos]
                        cargos_atuais.sort(key=lambda c: cargo_ordem.get(c, float('inf')))
                        return jsonify({
                            "status": "ok", 
                            "cargos_atuais": cargos_atuais, 
                            "cargos_disponiveis": cargos_disponiveis
                        })
                except Exception as e:
                    db.session.rollback()
                    print(f"ERRO ao adicionar cargo: {e}")
                    if not is_ajax:
                        return redirect(url_for("gestao_tribos"))
                    return jsonify({"status": "error", "message": str(e)}), 500
            
            if not is_ajax:
                return redirect(url_for("gestao_tribos"))
            return jsonify({"status": "error", "message": "Pessoa ou Cargo inválidos."}), 400

        # ✅ AÇÃO 6: REORDENAR PESSOAS (CORRIGIDA)
        elif acao == 'ordenar':
            original_tribo_nome = request.form.get('original_tribo')
            nova_tribo_nome = request.form.get('nova_tribo')
            nome_pessoa = request.form.get('nome_pessoa')
            nova_ordem_nomes_str = request.form.get('nova_ordem')
            
            try:
                nova_ordem_nomes = json.loads(nova_ordem_nomes_str)
            except (TypeError, json.JSONDecodeError):
                return jsonify({'status': 'error', 'message': 'Formato de ordem inválido.'}), 400
            
            nova_tribo = Tribo.query.filter_by(nome=nova_tribo_nome).first()
            
            if not nova_tribo:
                return jsonify({'status': 'error', 'message': 'Tribo de destino não encontrada'}), 400

            try:
                # 1. Se a pessoa mudou de tribo (Drag-and-Drop entre listas)
                if original_tribo_nome != nova_tribo_nome:
                    original_tribo = Tribo.query.filter_by(nome=original_tribo_nome).first()
                    
                    if original_tribo:
                        # A. Mover a pessoa
                        pessoa_movida = Pessoa.query.filter_by(nome=nome_pessoa).first()
                        if pessoa_movida:
                            pessoa_movida.tribo_id = nova_tribo.id
                            db.session.add(pessoa_movida)

                        # B. Reordenar os membros remanescentes da tribo original
                        membros_origem = Pessoa.query.filter(
                            Pessoa.tribo_id == original_tribo.id
                        ).order_by(Pessoa.ordem).all()
                        
                        for index, pessoa in enumerate(membros_origem):
                            if pessoa.nome != nome_pessoa:
                                pessoa.ordem = index
                                db.session.add(pessoa)

                # 2. Reordenar *todos* os membros da tribo de destino
                for index, nome in enumerate(nova_ordem_nomes):
                    pessoa_to_update = Pessoa.query.filter_by(nome=nome).first()
                    if pessoa_to_update:
                        pessoa_to_update.ordem = index
                        # Garantir que a pessoa está na nova tribo
                        pessoa_to_update.tribo_id = nova_tribo.id 
                        db.session.add(pessoa_to_update)

                db.session.commit()
                return jsonify({'status': 'ok'})
                
            except Exception as e:
                db.session.rollback()
                print(f"ERRO ao reordenar pessoas: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({'status': 'error', 'message': str(e)}), 500
            
        # Fallback para não-AJAX
        if not is_ajax:
            return redirect(url_for("gestao_tribos"))
        return jsonify({"status": "ok"})

    # ✅ LÓGICA DE GET: Carregar dados para renderizar
    tribos_dict = carregar_tribos() 
    return render_template(
        "gestao_tribos.html", 
        tribos=tribos_dict, 
        cargos_disponiveis=cargos_disponiveis
    )

@app.route("/reordenar_pessoas", methods=["POST"])
def reordenar_pessoas():
    data = request.get_json()
    tribo_nome = data.get("tribo")
    nova_ordem_nomes = data.get("nova_ordem")
    return jsonify({"status": "ok"})

@app.route("/tesouraria", methods=["GET", "POST"])
def tesouraria():
    tribos_disponiveis = [t.nome for t in Tribo.query.with_entities(Tribo.nome).all()]
    entidades_permitidas = ["Clan"] + tribos_disponiveis
    username = session.get('username')
    if username == "Peter Benenson":
        entidades_permitidas = ["Peter Benenson"]
    elif username == "Henri Dunant":
        entidades_permitidas = ["Henri Dunant"]
    elif username == "Rainha D. Leonor":
        entidades_permitidas = ["Rainha D. Leonor"]
    elif username in tribos_disponiveis:
         entidades_permitidas = [username]
    tribos_permitidas = [e for e in entidades_permitidas if e != "Clan"]
    if "Clan" in entidades_permitidas and "Clan" not in tribos_permitidas:
        tribos_permitidas.insert(0, "Clan")
    entidade_ativa = request.args.get('entidade_ativa')
    if entidade_ativa not in tribos_permitidas:
         entidade_ativa = tribos_permitidas[0] if tribos_permitidas else "Clan"

    if request.method == "POST":
        acao = request.form.get('acao')
        entidade = request.form.get('entidade')
        if entidade not in entidades_permitidas:
            #flash("Não tem permissão para alterar esta folha de caixa.", "danger")
            return redirect(url_for('tesouraria'))
        if acao == 'adicionar':
            data_str = request.form.get('data')
            descricao = request.form.get('descricao')
            tipo = request.form.get('tipo')
            valor = float(request.form.get('valor'))
            comprovativo_url = None
            if 'comprovativo' in request.files:
                file = request.files['comprovativo']
                if file.filename != '':
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    unique_filename = f"{limpar_nome(entidade)}_{data_str}_{str(uuid.uuid4())[:8]}.{ext}"
                    caminho_ficheiro = os.path.join(DIRETORIO_UPLOADS, unique_filename)
                    file.save(caminho_ficheiro)  # ❌ Guarda localmente (apaga no Render)
                    comprovativo_url = unique_filename
            nova_transacao = FolhaCaixa(
                entidade_nome=entidade,
                data=datetime.strptime(data_str, '%Y-%m-%d').date(),
                descricao=descricao,
                tipo=tipo,
                valor=valor,
                comprovativo_url=comprovativo_url
            )
            db.session.add(nova_transacao)
            db.session.commit()
            #flash("Transação adicionada com sucesso!", "success")
        elif acao == 'remover':
            transacao_id = request.form.get('id_transacao')
            transacao = FolhaCaixa.query.get(transacao_id)
            if transacao and transacao.entidade_nome == entidade:
                if transacao.comprovativo_url:
                    caminho_ficheiro = os.path.join(DIRETORIO_UPLOADS, transacao.comprovativo_url)
                    try:
                        os.remove(caminho_ficheiro)
                    except OSError as e:
                        print(f"Erro ao tentar remover o ficheiro: {e}")
                db.session.delete(transacao)
                db.session.commit()
                #flash("Transação removida com sucesso!", "warning")
            else:
                flash("Transação não encontrada ou sem permissão.", "danger")
        return redirect(url_for('tesouraria', entidade_ativa=entidade))

    folhas_caixa = {}
    for entidade in tribos_permitidas:
        folhas_caixa[entidade] = carregar_folha_caixa(entidade)
    return render_template("tesouraria.html", tribos=tribos_permitidas, 
                         folhas_caixa=folhas_caixa, entidade_ativa=entidade_ativa)

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/login", methods=["GET", "POST"])
def login():
    # Se qualquer utilizador estiver na sessão, redireciona para a página principal
    if session.get('username'):
        return redirect(url_for('index'))
        
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        # 1. Tenta encontrar o utilizador na base de dados (qualquer utilizador)
        utilizador = Utilizador.query.filter_by(username=username).first()

        # 2. Se o utilizador existe E a senha está correta
        if utilizador and bcrypt.check_password_hash(utilizador.password_hash, password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            # 3. Se não existe ou a senha está errada, falha o login
            # Esta mensagem é mais segura e generalizada
            flash('Nome de utilizador ou palavra-passe inválidos.', 'danger')
            return render_template("login.html")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
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
        utilizador = Utilizador.query.filter_by(username=username).first()
        if not utilizador or not bcrypt.check_password_hash(utilizador.password_hash, password_atual):
            flash("A palavra-passe atual está incorreta.", "danger")
            return render_template("mudar_password.html")
        if nova_password != confirmar_password:
            flash("A nova palavra-passe e a confirmação não coincidem.", "danger")
            return render_template("mudar_password.html")
        if bcrypt.check_password_hash(utilizador.password_hash, nova_password):
            flash("A nova palavra-passe não pode ser igual à anterior.", "warning")
            return render_template("mudar_password.html")
        hashed_password = bcrypt.generate_password_hash(nova_password).decode('utf-8')
        utilizador.password_hash = hashed_password
        db.session.commit()
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
        if not username or not password or not confirm_password:
            flash('Por favor, preencha todos os campos.', 'danger')
            return render_template("admin_register.html")
        if password != confirm_password:
            flash('As palavras-passe não correspondem.', 'danger')
            return render_template("admin_register.html")
        if Utilizador.query.filter_by(username=username).first():
            flash('Nome de utilizador já existe.', 'danger')
            return render_template("admin_register.html")
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        db.session.add(Utilizador(username=username, password_hash=hashed_password))
        db.session.commit()
        flash(f'Utilizador "{username}" registado com sucesso!', 'success')
        return redirect(url_for('admin_register'))
    return render_template("admin_register.html")

@app.route("/material", methods=["GET", "POST"])
def material():
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
                return redirect(url_for('material'))
            try:
                quantidade = int(quantidade_str)
            except (ValueError, TypeError):
                return redirect(url_for('material'))
            item_existente = Item.query.filter_by(
                categoria='Material',
                nome=nome_item,
                localizacao=localizacao,
                tribo_clan=tribo_clan
            ).first()
            if item_existente:
                item_existente.quantidade = str(int(item_existente.quantidade) + quantidade)
            else:
                novo_item = Item(
                    categoria='Material',
                    nome=nome_item,
                    quantidade=str(quantidade),
                    localizacao=localizacao,
                    tribo_clan=tribo_clan,
                    observacoes=observacoes
                )
                db.session.add(novo_item)
            db.session.commit()
            return redirect(url_for('material'))

        elif acao == "remover_item":
            nome_item = request.form.get("nome_item")
            tribo_clan = request.form.get("tribo_clan")
            Item.query.filter_by(categoria='Material', nome=nome_item, tribo_clan=tribo_clan).delete()
            db.session.commit()
            return jsonify({'status': 'success', 'message': 'Item removido!'})

    filtro_nome = request.args.get('filtro_nome', '').strip().lower()
    filtro_quantidade_str = request.args.get('filtro_quantidade', '').strip()
    filtro_localizacao = request.args.get('filtro_localizacao', '').strip().lower()
    filtro_tribo_clan = request.args.get('filtro_tribo_clan', '').strip()
    
    material_itens = carregar_material()
    opcoes_nome = sorted(list(set(item['nome'] for item in material_itens)))
    opcoes_quantidade = sorted(list(set(item['quantidade'] for item in material_itens)))
    opcoes_localizacao = sorted(list(set(item['localizacao'] for item in material_itens)))

    material_filtrado = material_itens
    if filtro_nome:
        material_filtrado = [item for item in material_filtrado if filtro_nome in item['nome'].lower()]
    if filtro_quantidade_str:
        try:
            filtro_quantidade = int(filtro_quantidade_str)
            material_filtrado = [item for item in material_filtrado if int(item['quantidade']) == filtro_quantidade]
        except (ValueError, TypeError):
            pass
    if filtro_localizacao:
        material_filtrado = [item for item in material_filtrado if filtro_localizacao in item['localizacao'].lower()]
    if filtro_tribo_clan:
        material_filtrado = [item for item in material_filtrado if item['tribo_clan'] == filtro_tribo_clan]

    material_filtrado = sorted(material_filtrado, key=lambda x: x['nome'].lower())
    return render_template("material.html", material_filtrado=material_filtrado,
                         tribos_disponiveis=tribos_disponiveis, filtro_nome=filtro_nome,
                         filtro_quantidade=filtro_quantidade_str, filtro_localizacao=filtro_localizacao,
                         filtro_tribo_clan=filtro_tribo_clan, opcoes_nome=opcoes_nome,
                         opcoes_quantidade=opcoes_quantidade, opcoes_localizacao=opcoes_localizacao)

@app.route("/farmacia", methods=["GET", "POST"])
def farmacia():
    farmacia_itens = carregar_farmacia()
    alergias = carregar_alergias()
    condicoes = carregar_condicoes()
    tribos = carregar_tribos()
    tribos_disponiveis = list(tribos.keys())
    pessoas_disponiveis = []
    for membros in tribos.values():
        for pessoa in membros:
            if isinstance(pessoa, dict) and "nome" in pessoa:
                pessoas_disponiveis.append(pessoa["nome"])
            else:
                pessoas_disponiveis.append(pessoa)

    if request.method == "POST":
        acao = request.form.get("acao")
        if acao == "adicionar_item":
            nome_item = request.form.get("nome_item")
            quantidade_str = request.form.get("quantidade")
            localizacao = request.form.get("localizacao")
            tribo_clan = request.form.get("tribo_clan")
            observacoes = request.form.get("observacoes", "")
            if not all([nome_item, quantidade_str, tribo_clan]):
                return redirect(url_for('farmacia'))
            try:
                quantidade = int(quantidade_str)
            except (ValueError, TypeError):
                return redirect(url_for('farmacia'))
            item_existente = Item.query.filter_by(
                categoria='Farmácia',
                nome=nome_item,
                localizacao=localizacao,
                tribo_clan=tribo_clan
            ).first()
            if item_existente:
                item_existente.quantidade = str(int(item_existente.quantidade) + quantidade)
            else:
                novo_item = Item(
                    categoria='Farmácia',
                    nome=nome_item,
                    quantidade=str(quantidade),
                    localizacao=localizacao,
                    tribo_clan=tribo_clan,
                    observacoes=observacoes
                )
                db.session.add(novo_item)
            db.session.commit()
            return redirect(url_for('farmacia'))

        elif acao == "remover_item":
            nome_item = request.form.get("nome_item")
            tribo_clan = request.form.get("tribo_clan")
            Item.query.filter_by(categoria='Farmácia', nome=nome_item, tribo_clan=tribo_clan).delete()
            db.session.commit()
            return jsonify({'status': 'success', 'message': 'Item removido!'})

        elif acao == "guardar_saude":
            CondicaoSaude.query.delete()
            for pessoa in pessoas_disponiveis:
                alergia_raw = request.form.get(f"alergia-{pessoa}", "").strip()
                condicao_raw = request.form.get(f"condicao-{pessoa}", "").strip()
                if alergia_raw:
                    for alergia in alergia_raw.splitlines():
                        if alergia.strip():
                            db.session.add(CondicaoSaude(pessoa_nome=pessoa, tipo='Alergia', detalhe=alergia.strip()))
                if condicao_raw:
                    for condicao in condicao_raw.splitlines():
                        if condicao.strip():
                            db.session.add(CondicaoSaude(pessoa_nome=pessoa, tipo='Condição', detalhe=condicao.strip()))
            db.session.commit()
            return redirect(url_for("farmacia"))

    filtro_nome = request.args.get('filtro_nome', '').strip().lower()
    filtro_quantidade_str = request.args.get('filtro_quantidade', '').strip()
    filtro_localizacao = request.args.get('filtro_localizacao', '').strip().lower()
    filtro_tribo_clan = request.args.get('filtro_tribo_clan', '').strip()

    farmacia_itens = carregar_farmacia()
    opcoes_nome = sorted(list(set(item['nome'] for item in farmacia_itens)))
    opcoes_quantidade = sorted(list(set(item['quantidade'] for item in farmacia_itens)))
    opcoes_localizacao = sorted(list(set(item['localizacao'] for item in farmacia_itens)))

    farmacia_filtrado = farmacia_itens
    if filtro_nome:
        farmacia_filtrado = [item for item in farmacia_filtrado if filtro_nome in item['nome'].lower()]
    if filtro_quantidade_str:
        try:
            filtro_quantidade = int(filtro_quantidade_str)
            farmacia_filtrado = [item for item in farmacia_filtrado if int(item['quantidade']) == filtro_quantidade]
        except (ValueError, TypeError):
            pass
    if filtro_localizacao:
        farmacia_filtrado = [item for item in farmacia_filtrado if filtro_localizacao in item['localizacao'].lower()]
    if filtro_tribo_clan:
        farmacia_filtrado = [item for item in farmacia_filtrado if item['tribo_clan'] == filtro_tribo_clan]

    farmacia_filtrado = sorted(farmacia_filtrado, key=lambda x: x['nome'].lower())
    return render_template("farmacia.html", farmacia_filtrado=farmacia_filtrado,
                         tribos_disponiveis=tribos_disponiveis, pessoas_disponiveis=pessoas_disponiveis,
                         filtro_nome=filtro_nome, filtro_quantidade=filtro_quantidade_str,
                         filtro_localizacao=filtro_localizacao, filtro_tribo_clan=filtro_tribo_clan,
                         opcoes_nome=opcoes_nome, opcoes_quantidade=opcoes_quantidade,
                         opcoes_localizacao=opcoes_localizacao, alergias=alergias, condicoes=condicoes)

@app.route("/cozinha", methods=["GET", "POST"])
def cozinha():
    inventario = carregar_inventario_cozinha()
    receitas = carregar_receitas()
    tribos_disponiveis = list(carregar_tribos().keys())
    opcoes_unidade = ["unidades", "kg", "g", "l", "ml", "pacote", "rolo", "a gosto"]
    opcoes_categoria = ["Cereais", "Laticínios", "Carne", "Peixe", "Frutas", "Vegetais", "Especiarias", "Bebidas", "Outros"]
    opcoes_dificuldade = ["Fácil", "Médio", "Difícil"]

    if request.method == "POST":
        acao = request.form.get("acao")
        # NOVO DEBUG CRÍTICO 1: Confirma que o POST está a ser recebido e qual é a ação
        print(f"DEBUG FLUXO: Método POST recebido. Ação identificada: {acao}")

# --- LÓGICA PARA ADICIONAR ITEM AO INVENTÁRIO (DEBUG CRÍTICO) ---
        if acao == "adicionar_item_cozinha": # <-- CORRIGIDO: Agora espera 'adicionar_item_cozinha'
            nome_item = request.form.get("nome_item")
            quantidade_item_raw = request.form.get("quantidade_item")
            unidade_item = request.form.get("unidade_item")
            categoria_item = request.form.get("categoria_item")

            # *** NOVO DEBUG: Mostra o que o Flask recebeu ***
            print(f"DEBUG INPUTS: Nome='{nome_item}', Quantidade='{quantidade_item_raw}', Unidade='{unidade_item}'")
            # ************************************************

            if not nome_item or not quantidade_item_raw or not unidade_item:
                print("DEBUG FLUXO: Campos obrigatórios (Nome, Quantidade, Unidade) em falta no formulário.")
                return redirect(url_for('cozinha'))

            try:
                # Trata vírgulas e espaços e tenta converter para float
                quantidade_item_num = float(quantidade_item_raw.strip().replace(',', '.'))
            except ValueError:
                # flash("A quantidade deve ser um número válido.", "danger")
                print(f"ERRO: Quantidade '{quantidade_item_raw}' inválida para conversão.")
                return redirect(url_for('cozinha'))

            novo_item = Item(
                categoria='Cozinha',
                nome=nome_item.strip(),
                quantidade=quantidade_item_num,
                localizacao=unidade_item,  # Unidade de medida
                tribo_clan=categoria_item, # Categoria do alimento
            )

            try:
                # NOVO DEBUG CRÍTICO 2: Confirma que a execução chegou ao ponto de adição
                print(f"DEBUG FLUXO: A tentar adicionar item {nome_item} ao DB...")
                db.session.add(novo_item)
                db.session.commit()
                # Debug de sucesso, se chegar aqui
                print(f"SUCESSO: Item '{nome_item}' adicionado. Tentativa de commit OK.")
            except Exception as e:
                db.session.rollback()
                # *** CÓDIGO CRÍTICO DE DEBUG: É AQUI QUE O ERRO DEVE APARECER ***
                import traceback
                print("\n" + "="*70)
                print("FALHA CRÍTICA NO COMMIT DO INVENTÁRIO. CAUSA MAIS PROVÁVEL: CAMPO OBRIGATÓRIO (NULLABLE=FALSE) EM FALTA NO MODELO ITEM.")
                print(f"Item tentado: Nome={nome_item}, Qtd={quantidade_item_num}, Unidade={unidade_item}, Cat={categoria_item}")
                print("\n--- INÍCIO DO TRACEBACK ---")
                traceback.print_exc() # Imprime o stack trace completo
                print("--- FIM DO TRACEBACK ---\n")
                print("="*70 + "\n")
                # Fim do código crítico
                
                # Se estiver a usar um ambiente de produção (gunicorn/uwsgi), o print pode falhar.
                # Se não vir nada, o erro é 100% no modelo Item.
                return redirect(url_for('cozinha')) # Mantém o fluxo normal mesmo em caso de falha

            return redirect(url_for('cozinha'))

        if acao == "adicionar_receita":
            nome_receita = request.form.get("nome_receita")
            ingredientes_raw = request.form.get("ingredientes_raw")
            instrucoes = request.form.get("instrucoes")
            tempo_preparacao = request.form.get("tempo_preparacao")
            dificuldade = request.form.get("dificuldade")
            porcoes_base = request.form.get("porcoes_base")
            if not nome_receita:
                #flash("O nome da receita é obrigatório.", "danger")
                return redirect(url_for('cozinha'))
            link_ficheiro = None
            if 'comprovativo_receita' in request.files:
                file = request.files['comprovativo_receita']
                if file.filename != '':
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(DIRETORIO_RECEITAS, filename)
                    file.save(filepath)  # ❌ Guarda localmente
                    link_ficheiro = url_for('serve_receita', filename=filename)
            if link_ficheiro:
                nova_receita = Receita(nome=nome_receita.strip(), link_ficheiro=link_ficheiro)
            else:
                ingredientes_processados = []
                for linha in ingredientes_raw.splitlines():
                    if linha.strip():
                        ingredientes_processados.append(linha.strip())
                if not (ingredientes_processados and instrucoes):
                    #flash("Para receitas manuais, preencha Ingredientes e Instruções.", "danger")
                    return redirect(url_for('cozinha'))
                nova_receita = Receita(
                    nome=nome_receita.strip(),
                    ingredientes=ingredientes_processados,
                    instrucoes=instrucoes,
                    tempo_preparacao=tempo_preparacao,
                    dificuldade=dificuldade,
                    porcoes_base=porcoes_base
                )
            db.session.add(nova_receita)
            db.session.commit()
            #flash(f"Receita '{nome_receita}' arquivada com sucesso!", "success")
            return redirect(url_for('cozinha'))
        return redirect(url_for('cozinha'))

    filtro_categoria = request.args.get('categoria', 'Todos')
    inventario_ordenado = sorted(inventario, key=lambda x: x['nome'])
    if filtro_categoria == 'Todos':
        inventario_filtrado = inventario_ordenado
    else:
        inventario_filtrado = [item for item in inventario_ordenado if item.get('categoria') == filtro_categoria]
    receitas_ordenadas = sorted(receitas, key=lambda x: x['nome'])
    return render_template("cozinha.html", inventario=inventario_filtrado, receitas=receitas_ordenadas,
                          opcoes_unidade=opcoes_unidade, opcoes_categoria=opcoes_categoria,
                          opcoes_dificuldade=opcoes_dificuldade, tribos_disponiveis=tribos_disponiveis,
                          filtro_categoria_atual=filtro_categoria)

@app.route('/uploads/cozinha/<path:filename>')
def serve_upload_cozinha(filename):
    return send_from_directory(DIRETORIO_UPLOADS_COZINHA, filename)

@app.route('/receitas/<path:filename>')
def serve_receita(filename):
    return send_from_directory(DIRETORIO_RECEITAS, filename)

@app.route("/cozinha/receita/<string:nome_receita>", methods=["GET"])
def ver_receita(nome_receita):
    receitas = carregar_receitas()
    receita = next((r for r in receitas if r['nome'] == nome_receita), None)
    if not receita:
        #flash("Receita não encontrada.", "danger")
        return redirect(url_for('cozinha'))
    return render_template("ver_receita.html", receita=receita)

@app.route("/eliminar_receita", methods=["POST"])
def eliminar_receita():
    nome_receita = request.form.get("nome_receita")
    link_ficheiro = request.form.get("link_ficheiro")
    if not nome_receita:
        #flash("Nome da receita não fornecido.", "danger")
        return redirect(url_for('cozinha'))
    receita = Receita.query.filter_by(nome=nome_receita).first()
    if receita:
        if receita.link_ficheiro:
            caminho_ficheiro = os.path.join(DIRETORIO_RECEITAS, os.path.basename(receita.link_ficheiro))
            if os.path.exists(caminho_ficheiro):
                try:
                    os.remove(caminho_ficheiro)
                except OSError as e:
                    flash(f"Erro ao eliminar o ficheiro: {e}", "warning")
        db.session.delete(receita)
        db.session.commit()
        #flash(f"Receita '{nome_receita}' eliminada com sucesso.", "success")
    return redirect(url_for('cozinha'))

@app.route("/eliminar_item_inventario", methods=["POST"])
def eliminar_item_inventario():
    nome_item_raw = request.form.get("nome_item", "").strip()
    unidade_item_raw = request.form.get("unidade_item", "").strip()
    if not nome_item_raw or not unidade_item_raw:
        #flash("Nome ou unidade do item não fornecidos.", "danger")
        return redirect(url_for('cozinha'))
    Item.query.filter_by(categoria='Cozinha', nome=nome_item_raw).delete()
    db.session.commit()
    return redirect(url_for('cozinha'))

@app.route("/progresso")
def progresso():
    # IMPORTANTE: Adicione 'copy' se ainda não o tiver no topo do seu app.py: 
    # import copy
    
    pessoas = carregar_nomes()
    # A ordenação foi movida para a função carregar_nomes()
    
    progresso_por_pessoa = carregar_progresso()
    progresso_modelo = carregar_progresso_modelo()
    areas = []
    trilhos = {}

    # 🐛 DEPURADOR 1: O que a função carregar_nomes devolveu?
    print(f"DEBUG: Nomes de Pessoas Carregados: {pessoas}")
    # 🐛 DEPURADOR 2: O que a função carregar_progresso devolveu?
    # Imprime o primeiro registo de progresso completo para inspeção (se existir)
    primeiro_progresso = next(iter(progresso_por_pessoa.values()), "Nenhum dado de progresso carregado.")
    print(f"DEBUG: Dados de Progresso Carregados (chaves): {list(progresso_por_pessoa.keys())}")
    print(f"DEBUG: Primeiro Registo de Progresso: {primeiro_progresso}")
    # 🐛 DEPURADOR 3: O que a função carregar_progresso_modelo devolveu?
    print(f"DEBUG: Modelo de Progresso (chaves): {list(progresso_modelo.keys()) if isinstance(progresso_modelo, dict) else progresso_modelo}")


    if progresso_modelo:
        areas = list(progresso_modelo.keys())
        for area_nome, trilhos_area in progresso_modelo.items():
            trilhos[area_nome] = {}
            for trilho_nome, objetivos_trilho in trilhos_area.items():
                # Garante que 'objetivos_trilho' é um dicionário antes de usar .keys()
                if isinstance(objetivos_trilho, dict):
                    trilhos[area_nome][trilho_nome] = list(objetivos_trilho.keys())
                else:
                    trilhos[area_nome][trilho_nome] = []
    
    dados_para_tabela = {}
    for nome_pessoa in pessoas:
        dados_pessoa = progresso_por_pessoa.get(nome_pessoa)
        
        # 🐛 NOVO DEPURADOR FOCADO: Verifica o estado exato dos dados.
        estado = "VÁLIDO" if isinstance(dados_pessoa, dict) and dados_pessoa else "INVÁLIDO/VAZIO"
        print(f"DEBUG_LOOP: Progresso para {nome_pessoa} (estado): {estado}")
        
        # 🚨 DEBUG DE CONTRADIÇÃO: Imprime o valor real de progresso para a primeira pessoa
        # para verificar porque é que está a cair no fallback apesar de 'Primeiro Registo' ser válido.
        if nome_pessoa == pessoas[0]:
            print(f"DEBUG_CONTRADICAO: Valor de progresso para {nome_pessoa} (inside loop): {dados_pessoa}")
        
        # 🚨 CORREÇÃO ADICIONAL: Verifica se o dado carregado é um dicionário. 
        # Se não for, assume que é inválido e usa o modelo.
        if not isinstance(dados_pessoa, dict) or not dados_pessoa:
             # Se a pessoa não tiver dados de progresso OU os dados estiverem vazios/corrompidos (não é um dict), 
             # usamos uma CÓPIA profunda do modelo como estrutura.
             print(f"AVISO: Dados de progresso ausentes/inválidos para {nome_pessoa}. Usando o modelo como fallback.")
             try:
                 # Esta cópia profunda garante que não se modifica o modelo original
                 dados_pessoa = copy.deepcopy(progresso_modelo)
             except AttributeError:
                 # Caso o progresso_modelo não esteja carregado ou seja None/string
                 print("AVISO: O modelo de progresso não pôde ser copiado. Usando dict vazio.")
                 dados_pessoa = {}
        
        dados_para_tabela[nome_pessoa] = dados_pessoa
        
    # Verifica se os trilhos foram carregados corretamente (deve ser um dict aninhado)
    if not isinstance(trilhos, dict) or not trilhos:
         print("ERRO: O modelo de progresso (trilhos) não foi carregado corretamente.")
         # Evita falha do template se o modelo estiver vazio
         trilhos = {} 
         
    return render_template("progresso.html", progresso=dados_para_tabela,
                           areas=areas, trilhos=trilhos, progresso_modelo=progresso_modelo)

@app.route("/atualizar_objetivo", methods=["POST"])
def atualizar_objetivo():
    """Atualiza o estado de um objetivo e guarda na BD."""
    
    if session.get('username') != 'Chefe':
        return jsonify({"status": "error", "message": "Apenas o Chefe pode alterar o progresso."}), 403
    
    try:
        data = request.get_json()
        nome = data["nome"]
        area = data["area"]
        trilho = data["trilho"]
        objetivo = data["objetivo"]
        novo_estado = data["estado"]
        
        # Debug
        print(f"\n🔄 Atualizando objetivo:")
        print(f"   Nome: {nome}, Área: {area}, Trilho: {trilho}, Objetivo: {objetivo}")
        print(f"   Novo estado: {novo_estado}")
        
        # Procura a pessoa
        pessoa = Pessoa.query.filter_by(nome=nome).first()
        if not pessoa:
            print(f"   ❌ Pessoa '{nome}' não encontrada")
            return jsonify({"status": "error", "message": "Pessoa não encontrada"}), 404
        
        # Procura o registo de progresso
        progresso = Progresso.query.filter_by(pessoa_id=pessoa.id).first()
        if not progresso:
            modelo = carregar_progresso_modelo()
            progresso = Progresso(pessoa_id=pessoa.id, dados_progresso=copy.deepcopy(modelo))
            db.session.add(progresso)
            db.session.flush()
            print(f"   ✅ Progresso criado")
        
        # Inicializa estrutura se necessário
        if not progresso.dados_progresso:
            progresso.dados_progresso = {}
        
        if area not in progresso.dados_progresso:
            progresso.dados_progresso[area] = {}
        
        if trilho not in progresso.dados_progresso[area]:
            progresso.dados_progresso[area][trilho] = {}
        
        # Atualiza o objetivo
        progresso.dados_progresso[area][trilho][objetivo] = novo_estado
        
        # ✅ CRÍTICO: Marca a coluna JSON como modificada para o SQLAlchemy
        from sqlalchemy.orm import attributes
        attributes.flag_modified(progresso, "dados_progresso")
        
        # Guarda na BD
        db.session.add(progresso)
        db.session.commit()
        
        print(f"   ✅ Guardado com sucesso na BD")
        
        # Calcula o novo nível
        dados_pessoa_bool = calcular_progresso_bool_do_dicionario(progresso.dados_progresso)
        progresso_modelo = carregar_progresso_modelo()
        nivel = calcular_nivel(dados_pessoa_bool, progresso_modelo)
        
        print(f"   📈 Novo nível: {nivel}\n")
        
        return jsonify({
            "status": "ok", 
            "novo_estado": novo_estado, 
            "nivel": nivel
        })
    
    except Exception as e:
        db.session.rollback()
        import traceback
        print(f"\n❌ ERRO ao atualizar objetivo: {e}")
        traceback.print_exc()
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500


@app.route("/debug_progresso")
def debug_progresso():
    """Rota de debug para ver o estado do progresso na BD."""
    
    modelo = ProgressoModelo.query.first()
    pessoas = Pessoa.query.all()
    progressos = Progresso.query.all()
    
    debug_info = {
        "modelo_existe": modelo is not None,
        "modelo_conteudo": modelo.modelo if modelo else None,
        "num_pessoas": len(pessoas),
        "pessoas_nomes": [p.nome for p in pessoas],
        "num_progressos": len(progressos),
        "progressos_data": [
            {
                "pessoa_id": p.pessoa_id,
                "pessoa_nome": p.pessoa.nome if p.pessoa else "???",
                "tem_dados": p.dados_progresso is not None,
                "dados": p.dados_progresso
            }
            for p in progressos
        ]
    }
    
    return jsonify(debug_info)


@app.route("/secretaria", methods=["GET", "POST"])

def secretaria():

    if request.method == "POST":
        if 'ata' in request.files:
            data_ata = request.form.get('dataAta')
            file = request.files['ata']
            if file.filename == '' or not data_ata:
                flash("Nenhum arquivo ou data de Ata selecionados.", "danger")
                return redirect(request.url)

            if file:
                filename = secure_filename(file.filename)
                nome_com_data = f"{data_ata}_{filename}"
                try:
                    file.save(os.path.join(DIRETORIO_ATAS, nome_com_data))
                    flash("Ata arquivada com sucesso!", "success")
                except Exception as e:
                    flash(f"Erro ao arquivar Ata: {e}", "8danger")

        elif 'documento' in request.files:
            file = request.files['documento']
            if file.filename == '':
                flash("Nenhum arquivo de Documento selecionado.", "danger")
                return redirect(request.url)

            if file:
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
                nome_com_timestamp = f"{timestamp}_{filename}"
                try:
                    file.save(os.path.join(DIRETORIO_OUTROS_DOCS, nome_com_timestamp))
                    flash("Documento arquivado com sucesso!", "success")
                except Exception as e:
                    flash(f"Erro ao arquivar Documento: {e}", "danger")
        return redirect(url_for('secretaria'))


    atas = []
    for nome_ficheiro in os.listdir(DIRETORIO_ATAS):
        try:
            partes = nome_ficheiro.split('_', 1)
            data_str = partes[0]
            nome_original = partes[1]
            data_ata = datetime.strptime(data_str, "%Y-%m-%d")
            atas.append({'nome_completo': nome_ficheiro, 'nome_original': nome_original, 'data': data_ata})
        except (ValueError, IndexError):
            atas.append({'nome_completo': nome_ficheiro, 'nome_original': nome_ficheiro, 'data': None})
    atas.sort(key=lambda x: x['data'] if x['data'] else datetime.min, reverse=True)


    outros_documentos = []
    for nome_ficheiro in os.listdir(DIRETORIO_OUTROS_DOCS):
        try:
            partes = nome_ficheiro.split('_', 2)
            timestamp_str = f"{partes[0]}_{partes[1]}"
            nome_original = partes[2]
            data_doc = datetime.strptime(timestamp_str, "%Y-%m-%d_%H%M%S")
            outros_documentos.append({'nome_completo': nome_ficheiro, 'nome_original': nome_original, 'data': data_doc})
        except (ValueError, IndexError):
            outros_documentos.append({'nome_completo': nome_ficheiro, 'nome_original': nome_ficheiro, 'data': None})
    outros_documentos.sort(key=lambda x: x['data'] if x['data'] else datetime.min, reverse=True)
    return render_template("secretaria.html", atas=atas, outros_documentos=outros_documentos)



@app.route('/outros_documentos/<path:filename>')
def serve_outro_doc(filename):
    return send_from_directory(DIRETORIO_OUTROS_DOCS, filename)

@app.route("/eliminar_outro_doc", methods=["POST"])
def eliminar_outro_doc():
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
    return send_from_directory(DIRETORIO_ATAS, filename)

@app.route("/eliminar_ata", methods=["POST"])
def eliminar_ata():
    if session.get('username') not in ['Chefe', 'Clan']:
        flash("Não tem permissão para realizar esta ação.", "danger")
        return redirect(url_for('login'))
    nome_completo_ata = request.form.get("nome_completo_ata")
    if not nome_completo_ata:
        flash("Nome do ficheiro não fornecido.", "danger")
        return redirect(url_for('secretaria'))
    caminho_ficheiro = os.path.join(DIRETORIO_ATAS, nome_completo_ata)
    try:
        if os.path.exists(caminho_ficheiro):
            os.remove(caminho_ficheiro)
            flash(f"Ata '{nome_completo_ata}' eliminada com sucesso.", "success")
        else:
            flash("O ficheiro não foi encontrado.", "danger")
    except Exception as e:
        flash(f"Ocorreu um erro ao tentar eliminar a ata: {e}", "danger")
    return redirect(url_for('secretaria'))

@app.route("/atividades_calendario")
def atividades_calendario():
    pode_editar = session.get('username') in ['Chefe', 'Clan']
    return render_template("atividades_calendario.html", pode_editar=pode_editar)

@app.route("/api/atividades", methods=["GET", "POST"])
def api_atividades():
    cores_por_tipo = {
        'Clan': '#ff0000', 'Agrupamento': '#0000ff', 'Núcleo': '#ffff00',
        'Região': '#800080', 'Nacional': '#008000', 'Internacional': '#ffc0cb'
    }
    if request.method == "POST":
        if session.get('username') not in ['Chefe', 'Clan']:
            return jsonify({"error": "Não tem permissão para realizar esta ação."}), 403
        data = request.get_json()
        required_fields = ['title', 'start', 'type']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Dados incompletos."}), 400
        nova_atividade = Atividade(
            id=str(uuid.uuid4()),
            titulo=data['title'],
            data_inicio=datetime.fromisoformat(data['start']),
            tipo=data['type'],
            descricao=data.get('details', ''),
            all_day=data.get('allDay', False)
        )
        if not nova_atividade.all_day:
            if 'end' not in data:
                return jsonify({"error": "Dados incompletos. 'end' em falta."}), 400
            nova_atividade.data_fim = datetime.fromisoformat(data['end'])
        else:
            end_date = datetime.strptime(data['start'], '%Y-%m-%d') + timedelta(days=1)
            nova_atividade.data_fim = end_date
        db.session.add(nova_atividade)
        db.session.commit()
        return jsonify({
            'id': nova_atividade.id,
            'title': nova_atividade.titulo,
            'start': nova_atividade.data_inicio.isoformat(),
            'end': nova_atividade.data_fim.isoformat(),
            'color': cores_por_tipo.get(nova_atividade.tipo, '#000000'),
            'type': nova_atividade.tipo,
            'details': nova_atividade.descricao,
            'allDay': nova_atividade.all_day
        }), 201
    elif request.method == "GET":
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

@app.route("/api/atividades/<id>", methods=["PUT"])
def api_editar_atividade(id):
    if session.get('username') not in ['Chefe', 'Clan']:
        return jsonify({"error": "Não tem permissão para realizar esta ação."}), 403
    cores_por_tipo = {
        'Clan': '#ff0000', 'Agrupamento': '#0000ff', 'Núcleo': '#ffff00',
        'Região': '#800080', 'Nacional': '#008000', 'Internacional': '#ffc0cb'
    }
    try:
        data = request.get_json()
        atividade = Atividade.query.get(id)
        if not atividade:
            return jsonify({"error": "Atividade não encontrada."}), 404
        atividade.titulo = data.get('title', atividade.titulo)
        atividade.data_inicio = datetime.fromisoformat(data.get('start', atividade.data_inicio.isoformat()))
        atividade.tipo = data.get('type', atividade.tipo)
        atividade.descricao = data.get('details', atividade.descricao)
        atividade.all_day = data.get('allDay', atividade.all_day)
        if not atividade.all_day:
            atividade.data_fim = datetime.fromisoformat(data.get('end'))
        else:
            end_date = atividade.data_inicio + timedelta(days=1)
            atividade.data_fim = end_date
        db.session.commit()
        return jsonify({
            'id': atividade.id,
            'title': atividade.titulo,
            'start': atividade.data_inicio.isoformat(),
            'end': atividade.data_fim.isoformat(),
            'color': cores_por_tipo.get(atividade.tipo, '#000000'),
            'type': atividade.tipo,
            'details': atividade.descricao,
            'allDay': atividade.all_day
        }), 200
    except Exception as e:
        print(f"Erro ao editar a atividade: {e}")
        return jsonify({"error": f"Erro interno do servidor: {e}"}), 500

@app.route("/api/atividades/<id>", methods=["DELETE"])
def api_eliminar_atividade(id):
    if session.get('username') not in ['Chefe', 'Clan']:
        return jsonify({"error": "Não tem permissão para realizar esta ação."}), 403
    try:
        atividade = Atividade.query.get(id)
        if not atividade:
            return jsonify({"error": "Atividade não encontrada."}), 404
        db.session.delete(atividade)
        db.session.commit()
        return jsonify({"message": "Atividade eliminada com sucesso!"}), 200
    except Exception as e:
        print(f"Erro no servidor ao eliminar a atividade: {e}")
        return jsonify({"error": f"Erro interno do servidor: {e}"}), 500

@app.route("/contas")
def contas_individuais():
    nomes = carregar_nomes()
    contas = ler_contas()
    for nome in nomes:
        if nome not in contas:
            nova_conta = Conta(pessoa_nome=nome, valor=0.0)
            db.session.add(nova_conta)
    db.session.commit()
    contas = ler_contas()
    return render_template("contas.html", nomes=nomes, contas=contas)

@app.route("/atualizar_valor/<nome>", methods=["POST"])
def atualizar_valor(nome):
    if session.get("username") != "Chefe":
        return "Acesso negado", 403
    novo_valor = request.form.get("valor")
    if novo_valor:
        try:
            novo_valor = float(novo_valor)
            conta = Conta.query.filter_by(pessoa_nome=nome).first()
            if conta:
                conta.valor = novo_valor
            else:
                db.session.add(Conta(pessoa_nome=nome, valor=novo_valor))
            db.session.commit()
        except ValueError:
            pass
    return redirect(url_for("contas_individuais"))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)