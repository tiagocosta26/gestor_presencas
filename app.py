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
import requests
from urllib.parse import urlparse

#MEGA ALTERAÇÂOOOOO0000

# --- IMPORTAÇÕES DE BASE DE DADOS ---
from flask_sqlalchemy import SQLAlchemy 
from sqlalchemy import JSON 
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy import event, DDL
# ------------------------------------------


print("DEBUG DATABASE_URL:", os.environ.get('EXTERNAL_DATABASE_URL'))


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


print(f"✅ Supabase URL: {SUPABASE_URL}")
print(f"✅ Supabase Key configurada: {bool(SUPABASE_KEY)}")

print("DEBUG: Todas as variáveis de ambiente:")
for key in os.environ:
    if 'SUPABASE' in key or 'DATABASE' in key:
        print(f"  {key} = {os.environ[key][:50]}...")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print(f"SUPABASE_URL final: {SUPABASE_URL}")
print(f"SUPABASE_KEY final: {bool(SUPABASE_KEY)}")

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
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 3,
    'max_overflow': 1,
    'pool_recycle': 300,
    'pool_pre_ping': True,
    'pool_timeout': 30
}
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
                             order_by='Pessoa.ordem', cascade="all, delete-orphan")


class Pessoa(db.Model):
    __tablename__ = 'pessoas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    tribo_id = db.Column(db.Integer, db.ForeignKey('tribos.id'), nullable=False)
    ordem = db.Column(db.Integer, default=0)
    cargos = db.relationship('PessoaCargo', back_populates='pessoa', 
                            cascade="all, delete-orphan")

class Utilizador(db.Model):
    __tablename__ = 'utilizadores'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

class AtividadePresenca(db.Model):
    """Modelo para guardar atividades de presença na BD."""
    __tablename__ = 'atividades_presenca'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date, nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    
    # Dados de presença em JSON
    dados = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f'<AtividadePresenca {self.nome}>'

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
    id = db.Column(db.Integer, primary_key=True)
    pessoa_id = db.Column(db.Integer, db.ForeignKey('pessoas.id', ondelete='CASCADE'), nullable=False)
    pessoa = db.relationship('Pessoa', backref='progresso_rel')
    dados_progresso = db.Column(JSON)
    
    # Índice único para garantir uma entrada por pessoa
    __table_args__ = (db.UniqueConstraint('pessoa_id', name='uq_pessoa_id'),)
    
class ProgressoModelo(db.Model):
    __tablename__ = 'progresso_modelo'
    id = db.Column(db.Integer, primary_key=True)
    modelo = db.Column(JSON)

class ItemCozinha(db.Model):
    """Modelo para itens do inventário de cozinha."""
    __tablename__ = 'itens_cozinha'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Float, nullable=False)  # Agora é Float em vez de String
    unidade = db.Column(db.String(50), nullable=False)  # Ex: "kg", "l", "unidades"
    categoria = db.Column(db.String(50), nullable=False)  # Ex: "Cereais", "Laticínios"
    observacoes = db.Column(db.Text, nullable=True)
    data_adicao = db.Column(db.DateTime, default=datetime.now)
    
    def __repr__(self):
        return f'<ItemCozinha {self.nome}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'quantidade': self.quantidade,
            'unidade': self.unidade,
            'categoria': self.categoria,
            'observacoes': self.observacoes or ''
        }


class ItemFarmacia(db.Model):
    """Modelo para itens do inventário de farmácia."""
    __tablename__ = 'itens_farmacia'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    localizacao = db.Column(db.String(100), nullable=True)  # Onde está guardado
    tribo_clan = db.Column(db.String(100), nullable=False)  # Qual tribo/responsável
    observacoes = db.Column(db.Text, nullable=True)
    data_adicao = db.Column(db.DateTime, default=datetime.now)
    
    def __repr__(self):
        return f'<ItemFarmacia {self.nome}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'quantidade': str(self.quantidade),
            'localizacao': self.localizacao or '',
            'tribo_clan': self.tribo_clan,
            'observacoes': self.observacoes or ''
        }

class Ata(db.Model):
    __tablename__ = 'atas'
    id = db.Column(db.Integer, primary_key=True)
    data_ata = db.Column(db.Date, nullable=False)
    nome_original = db.Column(db.String(255), nullable=False)
    url_supabase = db.Column(db.String(500), nullable=False)
    data_upload = db.Column(db.DateTime, default=datetime.now)

class Documento(db.Model):
    __tablename__ = 'documentos'
    id = db.Column(db.Integer, primary_key=True)
    nome_original = db.Column(db.String(255), nullable=False)
    url_supabase = db.Column(db.String(500), nullable=False)
    data_upload = db.Column(db.DateTime, default=datetime.now)

# --- FUNÇÕES AUXILIARES ---

def extract_storage_path(url_publica: str, bucket_name: str) -> str | None:
    """
    Extrai o caminho do ficheiro (path do storage) a partir do URL público.
    Ex: '.../public/bucket_name/path/to/file.pdf' -> 'path/to/file.pdf'
    """
    try:
        # Analisa o URL público
        parsed_url = urlparse(url_publica)
        
        # O caminho completo deve ser algo como: /storage/v1/object/public/bucket_name/path/to/file.pdf
        full_path = parsed_url.path
        
        # Regex para encontrar a parte 'public/bucket_name/' e capturar o resto
        # O padrão é: .../public/{bucket_name}/(caminho-do-ficheiro)
        pattern = re.compile(rf'/public/{re.escape(bucket_name)}/(.*)', re.IGNORECASE)
        match = pattern.search(full_path)
        
        if match:
            # Retorna o caminho do ficheiro dentro do bucket
            storage_path = match.group(1)
            return storage_path
        
        return None
    except Exception as e:
        print(f"❌ Erro ao extrair o caminho do storage do URL: {e}")
        return None

def delete_from_supabase(url_ficheiro, bucket):
    """Elimina ficheiro do Supabase Storage."""
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Supabase não configurado")
        return False

    try:
        # Extrai caminho completo (bucket + path)
        padrao = r"/object/public/(.+)"
        match = re.search(padrao, url_ficheiro)
        
        if not match:
            print(f"❌ URL inválido: {url_ficheiro}")
            return False

        caminho_completo = match.group(1)
        print(f"🗑️ Tentando eliminar: {caminho_completo}")

        endpoint = f"{SUPABASE_URL}/storage/v1/object/{caminho_completo}"
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }

        response = requests.delete(endpoint, headers=headers)

        if response.status_code in [200, 204]:
            print(f"✅ Ficheiro eliminado: {caminho_completo}")
            return True
        elif response.status_code == 404:
            print(f"⚠️ Ficheiro não encontrado (já eliminado): {caminho_completo}")
            return True
        else:
            print(f"❌ Erro ({response.status_code}): {response.text}")
            return False

    except Exception as e:
        print(f"❌ Erro: {e}")
        return False





def upload_para_supabase(file, bucket_name, pasta=""):
    """
    Faz upload para Supabase usando HTTP (SEM biblioteca).
    
    Args:
        file: FileStorage do Flask
        bucket_name: "atas" ou "documentos"
        pasta: subpasta (opcional)
    
    Returns:
        URL pública do ficheiro ou None se erro
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Supabase não configurado")
        return None
    
    try:
        # Gera nome único
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = secure_filename(file.filename)
        nome_ficheiro = f"{timestamp}_{filename}"
        
        # Define caminho no bucket
        if pasta:
            caminho = f"{pasta}/{nome_ficheiro}"
        else:
            caminho = nome_ficheiro
        
        print(f"📤 Upload: {bucket_name}/{caminho}")
        
        # URL para upload
        url = f"{SUPABASE_URL}/storage/v1/object/{bucket_name}/{caminho}"
        
        # Headers com autenticação
        headers = {
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": file.content_type
        }
        
        # Faz upload via HTTP
        response = requests.post(url, headers=headers, data=file.read())
        
        if response.status_code == 200:
            # Gera URL pública
            url_publica = f"{SUPABASE_URL}/storage/v1/object/public/{bucket_name}/{caminho}"
            print(f"✅ Upload bem-sucedido: {url_publica}")
            return url_publica
        else:
            print(f"❌ Erro no upload: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return None

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
    pessoas = Pessoa.query.with_entities(Pessoa.nome).order_by(Pessoa.tribo_id, Pessoa.ordem).all()
    return [nome[0] for nome in pessoas]

def carregar_utilizadores():
    utilizadores_obj = Utilizador.query.all()
    return {u.username: {'password_hash': u.password_hash} for u in utilizadores_obj}

def carregar_atividades_presenca_bd():
    """Carrega atividades de presença da BD."""
    atividades_obj = AtividadePresenca.query.order_by(
        AtividadePresenca.data_inicio.desc()
    ).all()
    
    atividades_agrupadas = defaultdict(list)
    
    for atv in atividades_obj:
        mes_ano = atv.data_inicio.strftime("%Y-%m")
        atividades_agrupadas[mes_ano].append({
            'id': atv.id,
            'nome': atv.nome,
            'data_inicio': atv.data_inicio.isoformat(),
            'data_fim': atv.data_fim.isoformat(),
            'data_criacao': atv.data_criacao.isoformat()
        })
    
    return atividades_agrupadas

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
    """Carrega todos os itens do inventário de farmácia."""
    try:
        itens = ItemFarmacia.query.order_by(ItemFarmacia.nome).all()
        return [i.to_dict() for i in itens]
    except Exception as e:
        print(f"❌ Erro ao carregar farmácia: {e}")
        return []

def carregar_inventario_cozinha():
    """Carrega todos os itens do inventário de cozinha."""
    try:
        itens = ItemCozinha.query.order_by(ItemCozinha.nome).all()
        return [i.to_dict() for i in itens]
    except Exception as e:
        print(f"❌ Erro ao carregar inventário de cozinha: {e}")
        return []

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
    """
    Carrega o modelo de progresso da BD e normaliza AGRESSIVAMENTE as chaves.
    Isto corrige o problema onde as chaves vêm como 'F\\u00edsico' em vez de 'Físico'.
    """
    modelo_obj = ProgressoModelo.query.first()
    
    if not modelo_obj or not modelo_obj.modelo:
        print("AVISO: Modelo de progresso não encontrado na BD.")
        return criar_modelo_padrao()
    
    progresso_modelo = modelo_obj.modelo
    
    try:
        print(f"DEBUG: Tipo do modelo na BD: {type(progresso_modelo)}")
        print(f"DEBUG: Primeiras chaves antes normalização: {list(progresso_modelo.keys())[:3]}")
        
        if isinstance(progresso_modelo, dict):
            progresso_modelo_normalizado = normalizar_chaves_dict_recursivo(progresso_modelo)
        else:
            # Se é string, faz parse primeiro
            progresso_modelo_normalizado = json.loads(progresso_modelo)
            progresso_modelo_normalizado = normalizar_chaves_dict_recursivo(progresso_modelo_normalizado)
        
        print(f"DEBUG: Primeiras chaves APÓS normalização: {list(progresso_modelo_normalizado.keys())[:3]}")
        print("✅ Modelo de progresso carregado e chaves NORMALIZADAS (aggressive).")
        
        return progresso_modelo_normalizado
        
    except Exception as e:
        print(f"🚨 ERRO ao normalizar modelo: {e}")
        import traceback
        traceback.print_exc()
        return criar_modelo_padrao()

def decodificar_unicode_escapado(texto):
    """
    Descodifica strings com escape Unicode literal.
    Exemplo: 'F\\u00edsico' -> 'Físico'
    """
    if isinstance(texto, str):
        try:
            # Tenta descodificar como se fosse uma string JSON
            return json.loads(f'"{texto}"')
        except:
            # Se falhar, tenta com o módulo codecs
            try:
                return texto.encode().decode('unicode-escape')
            except:
                return texto
    return texto

def normalizar_chaves_dict_recursivo(dados):
    """
    Normaliza recursivamente todas as chaves de um dicionário.
    Converte 'F\\u00edsico' para 'Físico', etc.
    """
    if not isinstance(dados, dict):
        return dados
    
    novo_dict = {}
    for chave, valor in dados.items():
        # Descodifica a chave
        chave_normalizada = decodificar_unicode_escapado(chave)
        
        # Normaliza recursivamente se o valor for um dicionário
        if isinstance(valor, dict):
            valor_normalizado = normalizar_chaves_dict_recursivo(valor)
        else:
            valor_normalizado = valor
        
        novo_dict[chave_normalizada] = valor_normalizado
    
    return novo_dict


def normalizar_chaves_dict(dados):
    """
    Função auxiliar que normaliza recursivamente as chaves de um dicionário.
    Converte 'F\\u00edsico' para 'Físico', etc.
    """
    if not isinstance(dados, dict):
        return dados
    
    novo_dict = {}
    for chave, valor in dados.items():
        try:
            # Tenta decodificar a chave como se fosse uma string JSON escapada
            chave_normalizada = json.loads(f'"{chave}"')
        except:
            # Se falhar, usa a chave como está
            chave_normalizada = chave
        
        # Normaliza recursivamente os valores se forem dicionários
        if isinstance(valor, dict):
            valor_normalizado = normalizar_chaves_dict(valor)
        else:
            valor_normalizado = valor
        
        novo_dict[chave_normalizada] = valor_normalizado
    
    return novo_dict


def garantir_progresso_pessoa(nome_pessoa, progresso_por_pessoa, progresso_modelo):
    """
    Função auxiliar que garante que cada pessoa tem dados de progresso válidos.
    Se não tiver, usa o modelo normalizado como fallback.
    """
    dados_pessoa = progresso_por_pessoa.get(nome_pessoa)
    
    # Se não tem dados ou dados inválidos, usa o modelo
    if not isinstance(dados_pessoa, dict) or not dados_pessoa:
        print(f"⚠️  Usando modelo para {nome_pessoa}")
        dados_pessoa = copy.deepcopy(progresso_modelo)
    else:
        dados_pessoa = normalizar_chaves_dict_recursivo(dados_pessoa)
    
    return dados_pessoa


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
        # Reconhece 'concluído' E 'feito' como sucesso (True)
        return obj in ["concluído", "feito"]
    else:
        # Devolve um dicionário vazio em vez de False para evitar o AttributeError no nível superior 
        # (se a função for chamada com None, por exemplo).
        return {} 
        
@app.template_global()
def calcular_nivel(dados_pessoa_bool, trilhos_por_area):

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

    init_default_data()

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


@app.route("/debug_atividades_completo")
def debug_atividades_completo():
    """Debug completo do sistema de atividades."""
    if session.get('username') != 'Chefe':
        return "Acesso negado", 403
    
    print("\n" + "="*70)
    print("🔍 DEBUG COMPLETO ATIVIDADES")
    print("="*70)
    
    try:
        # 1. Verificar modelo
        print("\n1️⃣ Verificando modelo AtividadePresenca...")
        print(f"   Colunas: {[c.name for c in AtividadePresenca.__table__.columns]}")
        
        # 2. Verificar tabela
        print("\n2️⃣ Consultando tabela...")
        atividades = AtividadePresenca.query.all()
        print(f"   Total de atividades: {len(atividades)}")
        
        # 3. Listar todas as atividades
        print("\n3️⃣ Lista completa:")
        atividades_list = []
        for atv in atividades:
            info = {
                "id": atv.id,
                "nome": atv.nome,
                "data_inicio": str(atv.data_inicio),
                "data_fim": str(atv.data_fim),
                "tem_dados": atv.dados is not None,
                "num_tribos": len(atv.dados) if atv.dados else 0
            }
            atividades_list.append(info)
            print(f"   {atv.id}: {atv.nome} ({atv.data_inicio})")
        
        # 4. Simular o que a rota /atividades faz
        print("\n4️⃣ Simulando rota /atividades...")
        atividades_agrupadas = defaultdict(list)
        for atv in atividades:
            mes_ano = atv.data_inicio.strftime("%Y-%m")
            nome_ficheiro = str(atv.id)
            titulo = atv.nome
            atividades_agrupadas[mes_ano].append((nome_ficheiro, titulo))
            print(f"   Adicionado: ({nome_ficheiro}, {titulo}) ao mês {mes_ano}")
        
        meses_ordenados = sorted(atividades_agrupadas.keys(), reverse=True)
        print(f"   Meses: {meses_ordenados}")
        
        # 5. Teste de leitura individual
        print("\n5️⃣ Teste de leitura individual...")
        if atividades:
            primeira = atividades[0]
            print(f"   Tentando carregar atividade ID: {primeira.id}")
            teste = AtividadePresenca.query.get(primeira.id)
            if teste:
                print(f"   ✅ Sucesso! Nome: {teste.nome}")
            else:
                print(f"   ❌ Falha ao carregar!")
        
        print("\n" + "="*70)
        
        resultado = {
            "total_atividades": len(atividades),
            "atividades": atividades_list,
            "meses": meses_ordenados,
            "agrupadas": dict(atividades_agrupadas)
        }
        
        return jsonify(resultado)
    
    except Exception as e:
        import traceback
        erro = traceback.format_exc()
        print(f"\n❌ ERRO: {e}")
        print(erro)
        print("="*70 + "\n")
        return jsonify({"error": str(e), "traceback": erro}), 500


@app.route("/gestao_presencas", methods=["GET", "POST"])
def presencas():
    """Gestão de presenças em atividades."""
    tribos = carregar_tribos()
    
    if request.method == "POST":
        try:
            atividade = request.form.get("atividade", "").strip()
            data_inicio = request.form.get("data_inicio", "").strip()
            data_fim = request.form.get("data_fim", "").strip()
            tribos_selecionadas = [t.strip() for t in request.form.get("tribos_selecionadas", "").split(",") if t.strip()]
            
            if not all([atividade, data_inicio, data_fim, tribos_selecionadas]):
                flash("Todos os campos são obrigatórios.", "danger")
                return redirect(url_for("presencas"))
            
            # Converter datas
            dt_inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date()
            dt_fim = datetime.strptime(data_fim, "%Y-%m-%d").date()
            
            # Preparar dados de presença
            dados_presenca = {}
            
            for tribo_nome in tribos_selecionadas:
                dados_presenca[tribo_nome] = {}
                
                membros = tribos.get(tribo_nome, [])
                for membro in membros:
                    nome = membro['nome']
                    presente = "Sim" if request.form.get(f"presenca_{nome}") == "Sim" else "Não"
                    dados_presenca[tribo_nome][nome] = presente
            
            # GUARDAR NA BD
            nova_atividade = AtividadePresenca(
                nome=atividade,
                data_inicio=dt_inicio,
                data_fim=dt_fim,
                dados=dados_presenca
            )
            
            db.session.add(nova_atividade)
            db.session.commit()
            
            print(f"✅ Atividade de presença '{atividade}' criada com sucesso na BD")
            flash(f"Atividade '{atividade}' registada com sucesso!", "success")
            return redirect(url_for("atividades"))
        
        except Exception as e:
            db.session.rollback()
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
    print("\n" + "="*70)
    print("📋 ROTA /atividades CHAMADA")
    print("="*70)
    
    try:
        print("\n1️⃣ Carregando atividades da BD...")
        atividades_obj = AtividadePresenca.query.order_by(
            AtividadePresenca.data_inicio.desc()
        ).all()
        print(f"   ✅ {len(atividades_obj)} atividades carregadas")
        
        print("\n2️⃣ Agrupando por mês...")
        atividades_agrupadas = defaultdict(list)
        
        for atv in atividades_obj:
            mes_ano = atv.data_inicio.strftime("%Y-%m")
            nome_ficheiro = str(atv.id)
            titulo = atv.nome
            atividades_agrupadas[mes_ano].append((nome_ficheiro, titulo))
            print(f"   ✅ ID:{atv.id} Nome:{atv.nome} Mês:{mes_ano}")
        
        meses_ordenados = sorted(atividades_agrupadas.keys(), reverse=True)
        print(f"\n3️⃣ Meses ordenados: {meses_ordenados}")
        
        print("\n4️⃣ Renderizando template...")
        print(f"   atividades_agrupadas: {dict(atividades_agrupadas)}")
        print(f"   meses_ordenados: {meses_ordenados}")
        
        resultado = render_template(
            "atividades.html", 
            atividades_agrupadas=atividades_agrupadas, 
            meses_ordenados=meses_ordenados
        )
        
        print("✅ TEMPLATE RENDERIZADO COM SUCESSO")
        print("="*70 + "\n")
        
        return resultado
    
    except Exception as e:
        db.session.rollback()
        import traceback
        erro = traceback.format_exc()
        print(f"\n❌ ERRO EM /atividades:")
        print(erro)
        print("="*70 + "\n")
        flash(f"Erro ao carregar atividades: {e}", "danger")
        return redirect(url_for("presencas"))



@app.route('/eliminar_atividade/<nome_ficheiro>', methods=['POST'])
def eliminar_atividade(nome_ficheiro):
    """Elimina uma atividade de presença."""
    if session.get('username') not in ['Chefe', 'Clan']:
        flash("Não tem permissão para eliminar atividades.", "danger")
        return redirect(url_for('atividades'))
    
    try:
        print(f"\n🗑️ Tentando eliminar atividade: {nome_ficheiro}")
        
        try:
            atividade_id = int(nome_ficheiro)
        except (ValueError, TypeError):
            print(f"❌ ID inválido: {nome_ficheiro}")
            flash("ID de atividade inválido.", "danger")
            return redirect(url_for('atividades'))
        
        atividade = AtividadePresenca.query.get(atividade_id)
        if atividade:
            nome = atividade.nome
            db.session.delete(atividade)
            db.session.commit()
            print(f"✅ Atividade '{nome}' (ID: {atividade_id}) eliminada")
            flash(f"Atividade '{nome}' eliminada com sucesso.", "success")
        else:
            print(f"❌ Atividade não encontrada com ID: {atividade_id}")
            flash("Atividade não encontrada.", "danger")
    except Exception as e:
        db.session.rollback()
        import traceback
        print(f"❌ Erro ao eliminar atividade: {e}")
        traceback.print_exc()
        flash(f"Erro ao eliminar: {e}", "danger")
    
    return redirect(url_for('atividades'))


@app.route("/atividade/<ficheiro>")
def ver_atividade(ficheiro):
    """Vê detalhes de uma atividade."""
    try:
        print(f"\n👁️ Carregando atividade: {ficheiro}")
        
        try:
            atividade_id = int(ficheiro)
        except (ValueError, TypeError):
            print(f"❌ ID inválido: {ficheiro}")
            flash("ID de atividade inválido.", "danger")
            return redirect(url_for("atividades"))
        
        atividade = AtividadePresenca.query.get(atividade_id)
        if not atividade:
            print(f"❌ Atividade não encontrada com ID: {atividade_id}")
            flash("Atividade não encontrada.", "danger")
            return redirect(url_for("atividades"))
        
        print(f"✅ Atividade encontrada: {atividade.nome}")
        
        cargos_disponiveis = carregar_cargos()
        
        # Reformatar dados para o template
        dados = defaultdict(list)
        if atividade.dados:
            for tribo_nome, membros in atividade.dados.items():
                for pessoa_nome, presente in membros.items():
                    # Procura os cargos da pessoa
                    pessoa = Pessoa.query.filter_by(nome=pessoa_nome).first()
                    cargos_list = []
                    if pessoa:
                        cargos_list = [pc.cargo.nome for pc in pessoa.cargos]
                    
                    dados[tribo_nome].append({
                        'nome': pessoa_nome,
                        'presente': presente,
                        'cargos': cargos_list
                    })
                    print(f"   ✅ {pessoa_nome} ({tribo_nome}): {presente}")
        
        data_display = (
            atividade.data_inicio.isoformat() 
            if atividade.data_inicio == atividade.data_fim 
            else f"{atividade.data_inicio.isoformat()} - {atividade.data_fim.isoformat()}"
        )
        
        print(f"✅ Renderizando template com {len(dados)} tribos\n")
        
        return render_template(
            "ver_atividade.html", 
            ficheiro=atividade.nome,
            atividade_id=atividade_id,
            dados=dados,
            data_display=data_display, 
            cargos_disponiveis=cargos_disponiveis
        )
    except Exception as e:
        import traceback
        print(f"❌ Erro ao carregar atividade: {e}")
        traceback.print_exc()
        flash("Erro ao carregar atividade.", "danger")
        return redirect(url_for("atividades"))


@app.route("/assiduidade", methods=["GET", "POST"])
def assiduidade():
    """Calcula assiduidade por pessoa usando dados da BD."""
    print("\n" + "="*70)
    print("📊 ROTA /assiduidade CHAMADA")
    print("="*70)
    
    try:
        ano_selecionado = request.form.get("ano_escutista")
        if ano_selecionado:
            ano_inicio = int(ano_selecionado.split('/')[0])
        else:
            hoje = datetime.now()
            ano_inicio = hoje.year
            if hoje.month < 10 or (hoje.month == 10 and hoje.day < 10):
                ano_inicio -= 1
        
        ano_fim = ano_inicio + 1
        data_inicio = datetime(ano_inicio, 10, 10).date()
        data_fim = datetime(ano_fim, 10, 9).date()
        
        print(f"\n📅 Período: {data_inicio} a {data_fim}")
        print(f"📅 Ano escutista: {ano_inicio}/{ano_fim}")
        
        assiduidade_por_tribo = defaultdict(
            lambda: defaultdict(lambda: {'presente': 0, 'total': 0})
        )
        atividades_do_ano = 0
        
        print("\n1️⃣ Carregando atividades da BD...")
        atividades = AtividadePresenca.query.filter(
            AtividadePresenca.data_inicio >= data_inicio,
            AtividadePresenca.data_inicio <= data_fim
        ).all()
        
        print(f"   ✅ {len(atividades)} atividades encontradas\n")
        
        for atividade in atividades:
            print(f"2️⃣ Processando: {atividade.nome} ({atividade.data_inicio})")
            atividades_do_ano += 1
            
            if not atividade.dados:
                print(f"   ⚠️  Sem dados de presença")
                continue
            
            # Processa cada tribo
            for tribo_nome, membros in atividade.dados.items():
                for pessoa_nome, presente in membros.items():
                    assiduidade_por_tribo[tribo_nome][pessoa_nome]['total'] += 1
                    if presente == "Sim":
                        assiduidade_por_tribo[tribo_nome][pessoa_nome]['presente'] += 1
                    print(f"   ✅ {pessoa_nome} ({tribo_nome}): {presente}")
        
        # Calcular percentagens
        print("\n3️⃣ Calculando percentagens...")
        for tribo in assiduidade_por_tribo:
            for elemento in assiduidade_por_tribo[tribo]:
                dados = assiduidade_por_tribo[tribo][elemento]
                if dados['total'] > 0:
                    dados['percentagem'] = (dados['presente'] / dados['total']) * 100
                else:
                    dados['percentagem'] = 0
        
        # Encontrar anos disponíveis da BD
        print("\n4️⃣ Encontrando anos disponíveis...")
        todas_atividades = AtividadePresenca.query.all()
        anos_disponiveis = set()
        
        for atv in todas_atividades:
            if atv.data_inicio:
                ano_inicio_atividade = atv.data_inicio.year
                if atv.data_inicio.month >= 10:
                    ano_escutista = ano_inicio_atividade
                else:
                    ano_escutista = ano_inicio_atividade - 1
                anos_disponiveis.add(ano_escutista)
                print(f"   ✅ {atv.nome}: {atv.data_inicio} -> ano escutista {ano_escutista}")
        
        hoje = datetime.now()
        is_new_scout_year_today = (
            (hoje.month > 10) or (hoje.month == 10 and hoje.day >= 10)
        )
        ano_atual = hoje.year if is_new_scout_year_today else hoje.year - 1
        anos_disponiveis.add(ano_atual)
        anos_disponiveis = sorted(list(anos_disponiveis), reverse=True)
        anos_formatados = [f"{ano}/{ano+1}" for ano in anos_disponiveis]
        
        print(f"\n5️⃣ Anos disponíveis: {anos_formatados}")
        print(f"   Total de atividades neste ano: {atividades_do_ano}")
        print("="*70 + "\n")
        
        return render_template(
            "assiduidade.html", 
            assiduidade_por_tribo=assiduidade_por_tribo,
            atividades_do_ano=atividades_do_ano, 
            anos_disponiveis=anos_formatados,
            ano_selecionado=f"{ano_inicio}/{ano_inicio+1}"
        )
    
    except Exception as e:
        db.session.rollback()
        import traceback
        erro = traceback.format_exc()
        print(f"\n❌ ERRO EM /assiduidade:")
        print(erro)
        print("="*70 + "\n")
        flash(f"Erro ao carregar assiduidade: {e}", "danger")
        return render_template(
            "assiduidade.html", 
            assiduidade_por_tribo={},
            atividades_do_ano=0, 
            anos_disponiveis=[],
            ano_selecionado="",
            erro="Erro ao carregar dados de assiduidade"
        )

@app.route("/gestao_tribos", methods=["GET", "POST"])
def gestao_tribos():
    tribos_dict = carregar_tribos()
    cargos_disponiveis = carregar_cargos()
    cargo_ordem = {cargo: i for i, cargo in enumerate(cargos_disponiveis)}

    if request.method == "POST":
        acao = request.form.get("acao")
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

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

        elif acao == "remover_pessoa":
            tribo_nome = request.form.get("tribo")
            nome_pessoa = request.form.get("nome_pessoa")
            
            try:
                pessoa = Pessoa.query.filter_by(nome=nome_pessoa).first()
                if pessoa:
                    # IMPORTANTE: Ordem de eliminação para evitar cascade errors
                    
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
    
    # Permissões por utilizador
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
        
        # Verifica permissões
        if entidade not in entidades_permitidas:
            flash("Não tem permissão para alterar esta folha de caixa.", "danger")
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
                    try:
                        # Cria pasta organizada: tesouraria/entidade/ano-mes
                        data_obj = datetime.strptime(data_str, '%Y-%m-%d')
                        pasta = f"tesouraria/{limpar_nome(entidade)}/{data_obj.strftime('%Y-%m')}"
                        
                        # Upload para Supabase
                        comprovativo_url = upload_para_supabase(file, "tesouraria", pasta)
                        
                        if not comprovativo_url:
                            flash("Erro ao fazer upload do comprovativo.", "warning")
                    except Exception as e:
                        print(f"❌ Erro no upload: {e}")
                        flash(f"Erro ao fazer upload: {e}", "danger")
            
            # Guarda na BD
            try:
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
                flash("Transação adicionada com sucesso!", "success")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Erro ao guardar transação: {e}")
                flash(f"Erro ao guardar transação: {e}", "danger")
        
        elif acao == 'remover':
            transacao_id = request.form.get('id_transacao')
            transacao = FolhaCaixa.query.get(transacao_id)
            
            if transacao and transacao.entidade_nome == entidade:
                try:
                    #Elimina ficheiro do Supabase (se existir)
                    if transacao.comprovativo_url:
                        delete_from_supabase(transacao.comprovativo_url, "tesouraria")
                    
                    # Elimina da BD
                    db.session.delete(transacao)
                    db.session.commit()
                    flash("Transação removida com sucesso!", "success")
                except Exception as e:
                    db.session.rollback()
                    print(f"❌ Erro ao eliminar transação: {e}")
                    #flash(f"Erro ao eliminar: {e}", "danger")
            else:
                flash("Transação não encontrada ou sem permissão.", "danger")
        
        return redirect(url_for('tesouraria', entidade_ativa=entidade))

    # GET - Carrega folhas de caixa
    folhas_caixa = {}
    for entidade in tribos_permitidas:
        folhas_caixa[entidade] = carregar_folha_caixa(entidade)
    
    return render_template("tesouraria.html", 
                         tribos=tribos_permitidas, 
                         folhas_caixa=folhas_caixa, 
                         entidade_ativa=entidade_ativa)

@app.route('/comprovativo/<int:transacao_id>')
def serve_comprovativo(transacao_id):
    """Redireciona para o comprovativo no Supabase."""
    try:
        transacao = FolhaCaixa.query.get(transacao_id)
        if transacao and transacao.comprovativo_url:
            # Se for URL do Supabase (começa com https://), redireciona
            if transacao.comprovativo_url.startswith('https://'):
                return redirect(transacao.comprovativo_url)
            # Se for ficheiro antigo (só nome), tenta servir localmente
            else:
                return send_from_directory(DIRETORIO_UPLOADS, transacao.comprovativo_url)
        else:
            flash("Comprovativo não encontrado.", "danger")
            return redirect(url_for('tesouraria'))
    except Exception as e:
        print(f"❌ Erro ao servir comprovativo: {e}")
        flash("Erro ao carregar comprovativo.", "danger")
        return redirect(url_for('tesouraria'))

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
    """Página de farmácia com inventário e informações de saúde."""
    farmacia_itens = carregar_farmacia()
    alergias = carregar_alergias()
    condicoes = carregar_condicoes()
    tribos = carregar_tribos()
    tribos_disponiveis = list(tribos.keys())
    
    # Coleta todas as pessoas disponíveis
    pessoas_disponiveis = []
    for membros in tribos.values():
        for pessoa in membros:
            if isinstance(pessoa, dict) and "nome" in pessoa:
                pessoas_disponiveis.append(pessoa["nome"])
            else:
                pessoas_disponiveis.append(str(pessoa))

    if request.method == "POST":
        acao = request.form.get("acao")
        print(f"DEBUG FLUXO: Ação de farmácia: {acao}")

        # --- ADICIONAR ITEM À FARMÁCIA ---
        if acao == "adicionar_item":
            nome_item = request.form.get("nome_item", "").strip()
            quantidade_str = request.form.get("quantidade", "").strip()
            localizacao = request.form.get("localizacao", "").strip()
            tribo_clan = request.form.get("tribo_clan", "").strip()
            observacoes = request.form.get("observacoes", "").strip()
            
            print(f"DEBUG INPUTS: Nome='{nome_item}', Qtd='{quantidade_str}', Local='{localizacao}', Tribo='{tribo_clan}'")
            
            if not all([nome_item, quantidade_str, tribo_clan]):
                print("DEBUG FLUXO: Campos obrigatórios em falta")
                return redirect(url_for('farmacia'))
            
            try:
                quantidade = int(quantidade_str)
            except (ValueError, TypeError):
                print(f"ERRO: Quantidade '{quantidade_str}' inválida")
                return redirect(url_for('farmacia'))
            
            try:
                # Verifica se já existe um item com o mesmo nome
                item_existente = ItemFarmacia.query.filter_by(
                    nome=nome_item,
                    localizacao=localizacao,
                    tribo_clan=tribo_clan
                ).first()
                
                if item_existente:
                    # Se existe, soma a quantidade
                    print(f"DEBUG FLUXO: Item já existe, atualizando quantidade")
                    item_existente.quantidade += quantidade
                else:
                    # Se não existe, cria novo
                    novo_item = ItemFarmacia(
                        nome=nome_item,
                        quantidade=quantidade,
                        localizacao=localizacao if localizacao else None,
                        tribo_clan=tribo_clan,
                        observacoes=observacoes if observacoes else None
                    )
                    db.session.add(novo_item)
                    print(f"DEBUG FLUXO: Novo item adicionado: {nome_item}")
                
                db.session.commit()
                print(f"SUCESSO: Item '{nome_item}' guardado/atualizado na BD")
            
            except Exception as e:
                db.session.rollback()
                import traceback
                print("\n" + "="*70)
                print("❌ ERRO AO GUARDAR ITEM DE FARMÁCIA")
                print(traceback.format_exc())
                print("="*70 + "\n")
            
            return redirect(url_for('farmacia'))

        # --- REMOVER ITEM DA FARMÁCIA ---
        elif acao == "remover_item":
            item_id = request.form.get("item_id")
            
            if not item_id:
                print("DEBUG FLUXO: ID do item vazio")
                return jsonify({'status': 'error', 'message': 'ID do item não fornecido'}), 400
            
            try:
                # Usa o ID para procurar o item na base de dados
                item = ItemFarmacia.query.get(int(item_id)) 
                if item:
                    nome = item.nome
                    db.session.delete(item)
                    db.session.commit()
                    print(f"✅ Item '{nome}' com ID {item_id} removido")
                    return jsonify({'status': 'success', 'message': f'Item {nome} removido!'})
                else:
                    print(f"❌ Item com ID {item_id} não encontrado")
                    return jsonify({'status': 'error', 'message': 'Item não encontrado'}), 404
            
            except Exception as e:
                db.session.rollback()
                print(f"❌ Erro ao remover item: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500

        # --- GUARDAR INFORMAÇÕES DE SAÚDE ---
        elif acao == "guardar_saude":
            print("DEBUG FLUXO: Guardando informações de saúde")
            try:
                # Limpa informações antigas
                CondicaoSaude.query.delete()
                
                # Adiciona novas informações
                for pessoa in pessoas_disponiveis:
                    alergia_raw = request.form.get(f"alergia-{pessoa}", "").strip()
                    condicao_raw = request.form.get(f"condicao-{pessoa}", "").strip()
                    
                    if alergia_raw:
                        for alergia in alergia_raw.splitlines():
                            if alergia.strip():
                                db.session.add(CondicaoSaude(
                                    pessoa_nome=pessoa,
                                    tipo='Alergia',
                                    detalhe=alergia.strip()
                                ))
                                print(f"   ✅ Alergia adicionada: {pessoa} -> {alergia.strip()}")
                    
                    if condicao_raw:
                        for condicao in condicao_raw.splitlines():
                            if condicao.strip():
                                db.session.add(CondicaoSaude(
                                    pessoa_nome=pessoa,
                                    tipo='Condição',
                                    detalhe=condicao.strip()
                                ))
                                print(f"   ✅ Condição adicionada: {pessoa} -> {condicao.strip()}")
                
                db.session.commit()
                print("SUCESSO: Informações de saúde guardadas")
            
            except Exception as e:
                db.session.rollback()
                import traceback
                print("\n" + "="*70)
                print("❌ ERRO AO GUARDAR INFORMAÇÕES DE SAÚDE")
                print(traceback.format_exc())
                print("="*70 + "\n")
            
            return redirect(url_for("farmacia"))

        return redirect(url_for('farmacia'))

    # --- GET REQUEST: APLICAR FILTROS ---
    filtro_nome = request.args.get('filtro_nome', '').strip().lower()
    filtro_quantidade_str = request.args.get('filtro_quantidade', '').strip()
    filtro_localizacao = request.args.get('filtro_localizacao', '').strip().lower()
    filtro_tribo_clan = request.args.get('filtro_tribo_clan', '').strip()

    farmacia_itens = carregar_farmacia()
    
    # Extrai opções únicas para os filtros
    opcoes_nome = sorted(list(set(item['nome'] for item in farmacia_itens if item['nome'])))
    opcoes_quantidade = sorted(list(set(item['quantidade'] for item in farmacia_itens if item['quantidade'])))
    opcoes_localizacao = sorted(list(set(item['localizacao'] for item in farmacia_itens if item['localizacao'])))

    # Aplica filtros
    farmacia_filtrado = farmacia_itens
    
    if filtro_nome:
        farmacia_filtrado = [
            item for item in farmacia_filtrado 
            if filtro_nome in item['nome'].lower()
        ]
    
    if filtro_quantidade_str:
        try:
            filtro_quantidade = int(filtro_quantidade_str)
            farmacia_filtrado = [
                item for item in farmacia_filtrado 
                if int(item['quantidade']) == filtro_quantidade
            ]
        except (ValueError, TypeError):
            pass
    
    if filtro_localizacao:
        farmacia_filtrado = [
            item for item in farmacia_filtrado 
            if filtro_localizacao in item['localizacao'].lower()
        ]
    
    if filtro_tribo_clan:
        farmacia_filtrado = [
            item for item in farmacia_filtrado 
            if item['tribo_clan'] == filtro_tribo_clan
        ]

    # Ordena por nome
    farmacia_filtrado = sorted(farmacia_filtrado, key=lambda x: x['nome'].lower())
    
    print(f"✅ Farmácia renderizada: {len(farmacia_filtrado)} itens após filtros")
    
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
    """Página de cozinha com inventário e receitas."""
    inventario = carregar_inventario_cozinha()
    receitas = carregar_receitas()
    tribos_disponiveis = list(carregar_tribos().keys())
    opcoes_unidade = ["unidades", "kg", "g", "l", "ml", "pacote"]
    opcoes_categoria = ["Material", "Cereais", "Laticínios", "Carne", "Peixe", "Frutas", "Vegetais", "Especiarias", "Bebidas", "Outros"]
    opcoes_dificuldade = ["Fácil", "Médio", "Difícil"]

    if request.method == "POST":
        acao = request.form.get("acao")
        print(f"DEBUG FLUXO: Método POST recebido. Ação: {acao}")

        # --- ADICIONAR ITEM AO INVENTÁRIO DE COZINHA ---
        if acao == "adicionar_item_cozinha":
            nome_item = request.form.get("nome_item", "").strip()
            quantidade_item_raw = request.form.get("quantidade_item", "").strip()
            unidade_item = request.form.get("unidade_item", "").strip()
            categoria_item = request.form.get("categoria_item", "").strip()
            observacoes = request.form.get("observacoes", "").strip()
            
            print(f"DEBUG INPUTS: Nome='{nome_item}', Qtd='{quantidade_item_raw}', Unidade='{unidade_item}', Categoria='{categoria_item}'")
            
            if not all([nome_item, quantidade_item_raw, unidade_item, categoria_item]):
                print("DEBUG FLUXO: Campos obrigatórios em falta")
                return redirect(url_for('cozinha'))
            
            try:
                quantidade_item_num = float(quantidade_item_raw.replace(',', '.'))
            except ValueError:
                print(f"ERRO: Quantidade '{quantidade_item_raw}' inválida")
                return redirect(url_for('cozinha'))
            
            try:
                # Verifica se já existe um item com o mesmo nome
                item_existente = ItemCozinha.query.filter_by(
                    nome=nome_item,
                    unidade=unidade_item,
                    categoria=categoria_item
                ).first()
                
                if item_existente:
                    # Se existe, soma a quantidade
                    print(f"DEBUG FLUXO: Item já existe, atualizando quantidade")
                    item_existente.quantidade += quantidade_item_num
                else:
                    # Se não existe, cria novo
                    novo_item = ItemCozinha(
                        nome=nome_item,
                        quantidade=quantidade_item_num,
                        unidade=unidade_item,
                        categoria=categoria_item,
                        observacoes=observacoes if observacoes else None
                    )
                    db.session.add(novo_item)
                    print(f"DEBUG FLUXO: Novo item adicionado: {nome_item}")
                
                db.session.commit()
                print(f"SUCESSO: Item '{nome_item}' guardado/atualizado na BD")
            
            except Exception as e:
                db.session.rollback()
                import traceback
                print("\n" + "="*70)
                print("❌ ERRO AO GUARDAR ITEM DE COZINHA")
                print(traceback.format_exc())
                print("="*70 + "\n")
            
            return redirect(url_for('cozinha'))

        # --- ADICIONAR RECEITA ---
        elif acao == "adicionar_receita":
            nome_receita = request.form.get("nome_receita", "").strip()
            ingredientes_raw = request.form.get("ingredientes_raw", "").strip()
            instrucoes = request.form.get("instrucoes", "").strip()
            tempo_preparacao = request.form.get("tempo_preparacao", "").strip()
            dificuldade = request.form.get("dificuldade", "Médio").strip()
            porcoes_base = request.form.get("porcoes_base", "").strip()
            
            print(f"DEBUG FLUXO: Adicionando receita: {nome_receita}")
            
            if not nome_receita:
                print("DEBUG FLUXO: Nome da receita vazio")
                flash("Nome da receita é obrigatório.", "danger")
                return redirect(url_for('cozinha'))
            
            try:
                link_ficheiro = None
                
                #Upload para Supabase (se há ficheiro anexado)
                if 'comprovativo_receita' in request.files:
                    file = request.files['comprovativo_receita']
                    if file.filename != '':
                        try:
                            # Upload para Supabase no bucket "receitas"
                            link_ficheiro = upload_para_supabase(file, "receitas", "receitas")
                            
                            if link_ficheiro:
                                print(f"✅ Ficheiro enviado para Supabase: {link_ficheiro}")
                            else:
                                print("❌ Erro no upload para Supabase")
                                flash("Erro ao fazer upload do ficheiro.", "warning")
                        except Exception as e:
                            print(f"❌ Erro no upload: {e}")
                            flash(f"Erro ao fazer upload: {e}", "danger")
                
                # Se há ficheiro, guarda com link
                if link_ficheiro:
                    nova_receita = Receita(
                        nome=nome_receita,
                        link_ficheiro=link_ficheiro
                    )
                    print(f"DEBUG FLUXO: Receita com ficheiro criada")
                else:
                    # Processa ingredientes
                    ingredientes_processados = []
                    for linha in ingredientes_raw.splitlines():
                        if linha.strip():
                            ingredientes_processados.append(linha.strip())
                    
                    if not (ingredientes_processados and instrucoes):
                        print("DEBUG FLUXO: Ingredientes ou instruções em falta")
                        flash("Ingredientes e instruções são obrigatórios.", "danger")
                        return redirect(url_for('cozinha'))
                    
                    nova_receita = Receita(
                        nome=nome_receita,
                        ingredientes=ingredientes_processados,
                        instrucoes=instrucoes,
                        tempo_preparacao=tempo_preparacao if tempo_preparacao else None,
                        dificuldade=dificuldade,
                        porcoes_base=porcoes_base if porcoes_base else None
                    )
                    print(f"DEBUG FLUXO: Receita manual criada")
                
                db.session.add(nova_receita)
                db.session.commit()
                print(f"✅ Receita '{nome_receita}' guardada na BD")
                flash(f"Receita '{nome_receita}' adicionada com sucesso!", "success")
            
            except Exception as e:
                db.session.rollback()
                import traceback
                print("\n" + "="*70)
                print("❌ ERRO AO GUARDAR RECEITA")
                print(traceback.format_exc())
                print("="*70 + "\n")
                flash(f"Erro ao guardar receita: {e}", "danger")
            
            return redirect(url_for('cozinha'))
        
        return redirect(url_for('cozinha'))

    # GET request - carrega filtros
    filtro_categoria = request.args.get('categoria', 'Todos')
    inventario_ordenado = sorted(inventario, key=lambda x: x['nome'])
    
    if filtro_categoria == 'Todos':
        inventario_filtrado = inventario_ordenado
    else:
        inventario_filtrado = [item for item in inventario_ordenado if item.get('categoria') == filtro_categoria]
    
    receitas_ordenadas = sorted(receitas, key=lambda x: x['nome'])
    
    return render_template(
        "cozinha.html",
        inventario=inventario_filtrado,
        receitas=receitas_ordenadas,
        opcoes_unidade=opcoes_unidade,
        opcoes_categoria=opcoes_categoria,
        opcoes_dificuldade=opcoes_dificuldade,
        tribos_disponiveis=tribos_disponiveis,
        filtro_categoria_atual=filtro_categoria
    )

@app.route('/uploads/cozinha/<path:filename>')
def serve_upload_cozinha(filename):
    return send_from_directory(DIRETORIO_UPLOADS_COZINHA, filename)

@app.route('/receitas/<int:receita_id>')
def serve_receita(receita_id):
    """Redireciona para o ficheiro da receita no Supabase."""
    try:
        receita = Receita.query.get(receita_id)
        if receita and receita.link_ficheiro:
            # Se for URL do Supabase (começa com https://), redireciona
            if receita.link_ficheiro.startswith('https://'):
                return redirect(receita.link_ficheiro)
            # Se for ficheiro antigo (path local), tenta servir localmente
            else:
                filename = os.path.basename(receita.link_ficheiro)
                return send_from_directory(DIRETORIO_RECEITAS, filename)
        else:
            flash("Ficheiro da receita não encontrado.", "danger")
            return redirect(url_for('cozinha'))
    except Exception as e:
        print(f"❌ Erro ao servir receita: {e}")
        flash("Erro ao carregar ficheiro da receita.", "danger")
        return redirect(url_for('cozinha'))

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
    """Elimina receita e ficheiro do Supabase."""
    nome_receita = request.form.get("nome_receita")
    
    if not nome_receita:
        flash("Nome da receita não fornecido.", "danger")
        return redirect(url_for('cozinha'))
    
    try:
        receita = Receita.query.filter_by(nome=nome_receita).first()
        
        if receita:
            #Elimina ficheiro do Supabase (se existir)
            if receita.link_ficheiro:
                if receita.link_ficheiro.startswith('https://'):
                    # Ficheiro no Supabase
                    delete_from_supabase(receita.link_ficheiro, "receitas")
                else:
                    # Ficheiro local antigo
                    caminho_ficheiro = os.path.join(DIRETORIO_RECEITAS, os.path.basename(receita.link_ficheiro))
                    if os.path.exists(caminho_ficheiro):
                        try:
                            os.remove(caminho_ficheiro)
                            print(f"✅ Ficheiro local eliminado: {caminho_ficheiro}")
                        except OSError as e:
                            print(f"⚠️ Erro ao eliminar ficheiro local: {e}")
            
            # Elimina da BD
            db.session.delete(receita)
            db.session.commit()
            flash(f"Receita '{nome_receita}' eliminada com sucesso.", "success")
            print(f"✅ Receita '{nome_receita}' eliminada")
        else:
            flash("Receita não encontrada.", "danger")
    
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao eliminar receita: {e}")
        flash(f"Erro ao eliminar receita: {e}", "danger")
    
    return redirect(url_for('cozinha'))

@app.route("/eliminar_item_inventario", methods=["POST"])
def eliminar_item_inventario():
    """Eliminar um item do inventário de cozinha."""
    item_id = request.form.get("item_id")
    
    if not item_id:
        print("DEBUG FLUXO: ID do item vazio")
        return redirect(url_for('cozinha'))
    
    try:
        item = ItemCozinha.query.get(int(item_id))
        if item:
            nome = item.nome
            db.session.delete(item)
            db.session.commit()
            print(f"✅ Item '{nome}' eliminado do inventário")
        else:
            print(f"❌ Item com ID {item_id} não encontrado")
    
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao eliminar item: {e}")
    
    return redirect(url_for('cozinha'))

@app.route("/progresso")
def progresso():
    pessoas = carregar_nomes()
    progresso_por_pessoa = carregar_progresso()
    progresso_modelo = carregar_progresso_modelo()  # Agora com normalização agressiva
    
    # Debug
    print(f"DEBUG: Nomes de Pessoas: {pessoas}")
    print(f"DEBUG: Progresso Carregado (chaves pessoa): {list(progresso_por_pessoa.keys())[:3]}")
    print(f"DEBUG: Modelo de Progresso (chaves): {list(progresso_modelo.keys())}")
    
    areas = []
    trilhos = {}
    
    if progresso_modelo and isinstance(progresso_modelo, dict):
        areas = list(progresso_modelo.keys())
        print(f"DEBUG: Áreas extraídas: {areas}")
        
        for area_nome in areas:
            trilhos_area = progresso_modelo.get(area_nome, {})
            if isinstance(trilhos_area, dict):
                trilhos[area_nome] = {}
                for trilho_nome, objetivos_trilho in trilhos_area.items():
                    if isinstance(objetivos_trilho, dict):
                        trilhos[area_nome][trilho_nome] = list(objetivos_trilho.keys())
                    else:
                        trilhos[area_nome][trilho_nome] = []
    
    dados_para_tabela = {}
    for nome_pessoa in pessoas:
        # Garante que tem dados válidos E normalizados
        dados_pessoa = garantir_progresso_pessoa(
            nome_pessoa, 
            progresso_por_pessoa, 
            progresso_modelo
        )
        dados_para_tabela[nome_pessoa] = dados_pessoa
        print(f"✅ {nome_pessoa} - progresso preparado (chaves: {list(dados_pessoa.keys())[:2]})")
    
    if not trilhos:
        print("ERRO: Trilhos vazios após carregamento do modelo.")
        trilhos = {}
    
    print(f"DEBUG FINAL: Areas para template: {areas}")
    print(f"DEBUG FINAL: Trilhos para template: {list(trilhos.keys())}")
    
    return render_template(
        "progresso.html", 
        progresso=dados_para_tabela,
        areas=areas, 
        trilhos=trilhos, 
        progresso_modelo=progresso_modelo
    )

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
    
    # Garante que os dados são decodificáveis antes de enviar para JSONIFY
    modelo_conteudo_seguro = modelo.modelo if modelo else None
    if isinstance(modelo_conteudo_seguro, dict):
        try:
            # Tenta normalizar para garantir que o output de debug é limpo
            modelo_conteudo_seguro = json.loads(json.dumps(modelo_conteudo_seguro))
        except:
            pass
            
    progressos_data_segura = []
    for p in progressos:
        dados_seguros = p.dados_progresso
        if isinstance(dados_seguros, dict):
            try:
                # Tenta normalizar os dados de progresso para o output de debug
                dados_seguros = json.loads(json.dumps(dados_seguros))
            except:
                pass

        progressos_data_segura.append({
            "pessoa_id": p.pessoa_id,
            "pessoa_nome": p.pessoa.nome if p.pessoa else "???",
            "tem_dados": p.dados_progresso is not None,
            "dados": dados_seguros
        })
    
    debug_info = {
        "modelo_existe": modelo is not None,
        "modelo_conteudo": modelo_conteudo_seguro,
        "num_pessoas": len(pessoas),
        "pessoas_nomes": [p.nome for p in pessoas],
        "num_progressos": len(progressos),
        "progressos_data": progressos_data_segura
    }
    
    return jsonify(debug_info)


@app.route("/secretaria", methods=["GET", "POST"])
def secretaria():
    """Página de secretaria com upload para Supabase."""
    
    if request.method == "POST":
        # --- UPLOAD DE ATA ---
        if 'ata' in request.files:
            data_ata = request.form.get('dataAta', '').strip()
            file = request.files['ata']
            
            if file.filename == '' or not data_ata:
                flash("Selecione ficheiro e data.", "danger")
                return redirect(request.url)
            
            try:
                data_ata_obj = datetime.strptime(data_ata, "%Y-%m-%d").date()
                
                # Upload para Supabase
                url_publica = upload_para_supabase(file, "atas", f"atas/{data_ata}")
                
                if url_publica:
                    # Guarda na BD
                    nova_ata = Ata(
                        data_ata=data_ata_obj,
                        nome_original=file.filename,
                        url_supabase=url_publica
                    )
                    db.session.add(nova_ata)
                    db.session.commit()
                    flash("Ata arquivada com sucesso!", "success")
                else:
                    flash("Erro no upload.", "danger")
            
            except Exception as e:
                db.session.rollback()
                print(f"❌ Erro: {e}")
                flash(f"Erro: {e}", "danger")

        # --- UPLOAD DE DOCUMENTO ---
        elif 'documento' in request.files:
            file = request.files['documento']
            
            if file.filename == '':
                flash("Selecione ficheiro.", "danger")
                return redirect(request.url)
            
            try:
                url_publica = upload_para_supabase(file, "documentos", "documentos")
                
                if url_publica:
                    novo_doc = Documento(
                        nome_original=file.filename,
                        url_supabase=url_publica
                    )
                    db.session.add(novo_doc)
                    db.session.commit()
                    flash("Documento arquivado com sucesso!", "success")
                else:
                    flash("Erro no upload.", "danger")
            
            except Exception as e:
                db.session.rollback()
                print(f"❌ Erro: {e}")
                flash(f"Erro: {e}", "danger")
        
        return redirect(url_for('secretaria'))

    # GET - Carrega ficheiros
    try:
        atas = Ata.query.order_by(Ata.data_ata.desc()).all()
        documentos = Documento.query.order_by(Documento.data_upload.desc()).all()
    except Exception as e:
        print(f"❌ Erro: {e}")
        atas = []
        documentos = []
    
    return render_template(
        "secretaria.html",
        atas=atas,
        outros_documentos=documentos
    )



@app.route('/documentos/<int:documento_id>')
def serve_documento(documento_id):
    """Redireciona para o ficheiro no Supabase."""
    try:
        doc = Documento.query.get(documento_id)
        if doc:
            return redirect(doc.url_supabase)
        else:
            flash("Documento não encontrado.", "danger")
            return redirect(url_for('secretaria'))
    except Exception as e:
        print(f"❌ Erro: {e}")
        return redirect(url_for('secretaria'))

@app.route("/eliminar_outro_doc", methods=["POST"])
def eliminar_outro_doc():
    """Eliminar documento e ficheiro do Supabase."""
    if session.get('username') not in ['Chefe', 'Clan']:
        flash("Sem permissão.", "danger")
        return redirect(url_for('login'))
    
    documento_id = request.form.get("documento_id") 
    
    try:
        doc = Documento.query.get(int(documento_id))
        if doc:
            url_ficheiro = doc.url_supabase
            nome_original = doc.nome_original
            
            # 1. TENTA ELIMINAR O FICHEIRO DO SUPABASE
            # Se a função retornar True, significa que o ficheiro foi removido ou não existia.
            storage_success = delete_from_supabase(url_ficheiro, "documentos") 
            
            # 2. ELIMINA O REGISTO DA BASE DE DADOS INDEPENDENTEMENTE DO SUCESSO DO STORAGE
            db.session.delete(doc)
            db.session.commit()
            
            if storage_success:
                flash(f"Documento '{nome_original}' eliminado com sucesso (BD e Storage).", "success")
            #else:
                #flash(f"Documento '{nome_original}' eliminado da BD. ATENÇÃO: Houve um erro ao eliminar o ficheiro no Supabase. Verifique o Storage.", "warning")
            else:
                flash("Documento não encontrado.", "danger")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao eliminar documento: {e}")
        flash(f"Erro: {e}", "danger")
    
    return redirect(url_for('secretaria'))
    
    return redirect(url_for('secretaria'))

@app.route('/atas/<int:ata_id>')
def serve_ata(ata_id):
    """Redireciona para o ficheiro no Supabase."""
    try:
        ata = Ata.query.get(ata_id)
        if ata:
            return redirect(ata.url_supabase)
        else:
            flash("Ata não encontrada.", "danger")
            return redirect(url_for('secretaria'))
    except Exception as e:
        print(f"❌ Erro: {e}")
        return redirect(url_for('secretaria'))

@app.route("/eliminar_ata", methods=["POST"])
def eliminar_ata():
    """Eliminar ata e ficheiro do Supabase."""
    if session.get('username') not in ['Chefe', 'Clan']:
        flash("Sem permissão.", "danger")
        return redirect(url_for('login'))
    
    ata_id = request.form.get("ata_id") 
    
    try:
        ata = Ata.query.get(int(ata_id))
        if ata:
            url_ficheiro = ata.url_supabase
            nome_original = ata.nome_original
            
            # 1. TENTA ELIMINAR O FICHEIRO DO SUPABASE
            storage_success = delete_from_supabase(url_ficheiro, "atas") 
            
            # 2. ELIMINA O REGISTO DA BASE DE DADOS
            db.session.delete(ata)
            db.session.commit()
            
            if storage_success:
                flash(f"Ata '{nome_original}' eliminada com sucesso (BD e Storage).", "success")
            #else:
                # flash(f"Ata '{nome_original}' eliminada da BD. ATENÇÃO: Houve um erro ao eliminar o ficheiro no Supabase. Verifique o Storage.", "warning")
            else:
                flash("Ata não encontrada.", "danger")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao eliminar ata: {e}")
        flash(f"Erro: {e}", "danger")
    
    return redirect(url_for('secretaria'))

@app.route("/atividades_calendario")
def atividades_calendario():
    pode_editar = session.get('username') in ['Chefe', 'Clan']
    return render_template("atividades_calendario.html", pode_editar=pode_editar)

@app.route("/api/atividades", methods=["GET", "POST"])
def api_atividades():
    cores_por_tipo = {
        'Clan': '#ff0000', 'Agrupamento': '#0000ff', 'Núcleo': '#f8da45', 'Cenáculo': "#97612B",
        'Região': '#800080', 'Nacional': '#008000', 'Internacional': '#ffc0cb'
    }
    
    if request.method == "POST":
        if session.get('username') not in ['Chefe', 'Clan']:
            return jsonify({"error": "Não tem permissão para realizar esta ação."}), 403
        
        data = request.get_json()
        required_fields = ['title', 'start', 'type']
        
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Dados incompletos. Faltam: 'title', 'start' ou 'type'."}), 400
        
        all_day = data.get('allDay', False)
        
        # 1. Tratar a data de início
        try:
            data_inicio_obj = datetime.fromisoformat(data['start'].replace('Z', '+00:00'))
        except ValueError as e:
            return jsonify({"error": f"Formato de data/hora 'start' inválido: {e}"}), 400
        
        data_fim_obj = None
        
        # 2. Tratar a data de fim (essencial para múltiplos dias)
        if 'end' in data and data['end']:
            try:
                # O FullCalendar envia a data de fim (end) exclusiva.
                data_fim_obj = datetime.fromisoformat(data['end'].replace('Z', '+00:00'))
            except ValueError as e:
                return jsonify({"error": f"Formato de data/hora 'end' inválido: {e}"}), 400
        elif all_day:
            # Se for allDay e 'end' não for fornecido, a atividade é de 1 dia. 
            # O 'end' deve ser o dia seguinte ao 'start' (comportamento FullCalendar).
            # Garante que funciona mesmo se data_inicio_obj for apenas uma data (sem hora).
            data_fim_obj = data_inicio_obj.date() + timedelta(days=1)
            data_fim_obj = datetime.combine(data_fim_obj, datetime.min.time())
        else:
            # Se não for allDay e 'end' não for fornecido, assume 1 hora de duração.
            data_fim_obj = data_inicio_obj + timedelta(hours=1)

        # 3. Criar e guardar a atividade
        nova_atividade = Atividade(
            id=str(uuid.uuid4()),
            titulo=data['title'],
            data_inicio=data_inicio_obj,
            data_fim=data_fim_obj, 
            tipo=data['type'],
            descricao=data.get('details', ''),
            all_day=all_day
        )
        
        db.session.add(nova_atividade)
        db.session.commit()
        
        # 4. Preparar a resposta JSON
        # Formata start/end para YYYY-MM-DD se for allDay (necessário para FullCalendar)
        def format_date_for_fc(dt, is_all_day):
            if is_all_day and isinstance(dt, datetime):
                return dt.isoformat().split('T')[0]
            if isinstance(dt, datetime):
                 return dt.isoformat()
            return dt # se já for string
        
        return jsonify({
            'id': nova_atividade.id,
            'title': nova_atividade.titulo,
            'start': format_date_for_fc(nova_atividade.data_inicio, nova_atividade.all_day),
            'end': format_date_for_fc(nova_atividade.data_fim, nova_atividade.all_day),
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
                'end': atv.get('end'), # Se a DB retornar None para 'end', o FullCalendar trata bem
                'color': cores_por_tipo.get(atv['type'], '#000000'),
                'type': atv['type'],
                'details': atv.get('details', ''),
                'allDay': atv.get('allDay', False)
            }
            eventos.append(evento)
        return jsonify(eventos)

@app.route("/api/atividades/<id>", methods=["PUT"])
def api_editar_atividade(id):
    """Edita uma atividade existente."""
    if session.get('username') not in ['Chefe', 'Clan']:
        return jsonify({"error": "Não tem permissão para realizar esta ação."}), 403
    
    try:
        atividade = Atividade.query.get(id)
        if not atividade:
            return jsonify({"error": "Atividade não encontrada."}), 404
        
        data = request.get_json()
        cores_por_tipo = {
            'Clan': '#ff0000', 'Agrupamento': '#0000ff', 'Núcleo': '#f8da45', 
            'Cenáculo': "#97612B", 'Região': '#800080', 'Nacional': '#008000', 
            'Internacional': '#ffc0cb'
        }
        
        # Atualiza os campos
        if 'title' in data:
            atividade.titulo = data['title']
        
        if 'start' in data:
            try:
                atividade.data_inicio = datetime.fromisoformat(data['start'].replace('Z', '+00:00'))
            except ValueError as e:
                return jsonify({"error": f"Formato de 'start' inválido: {e}"}), 400
        
        if 'end' in data:
            try:
                atividade.data_fim = datetime.fromisoformat(data['end'].replace('Z', '+00:00'))
            except ValueError as e:
                return jsonify({"error": f"Formato de 'end' inválido: {e}"}), 400
        
        if 'type' in data:
            atividade.tipo = data['type']
        
        if 'details' in data:
            atividade.descricao = data['details']
        
        if 'allDay' in data:
            atividade.all_day = data['allDay']
        
        db.session.commit()
        
        # Formata a resposta
        def format_date_for_fc(dt, is_all_day):
            if is_all_day and isinstance(dt, datetime):
                return dt.isoformat().split('T')[0]
            if isinstance(dt, datetime):
                return dt.isoformat()
            return dt
        
        return jsonify({
            'id': atividade.id,
            'title': atividade.titulo,
            'start': format_date_for_fc(atividade.data_inicio, atividade.all_day),
            'end': format_date_for_fc(atividade.data_fim, atividade.all_day),
            'color': cores_por_tipo.get(atividade.tipo, '#000000'),
            'type': atividade.tipo,
            'details': atividade.descricao,
            'allDay': atividade.all_day
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao editar atividade: {e}")
        import traceback
        traceback.print_exc()
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