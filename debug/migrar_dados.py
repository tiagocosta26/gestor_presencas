"""
Script de Migração: JSON → Base de Dados SQL
Execute este script UMA VEZ para migrar todos os dados dos ficheiros JSON para a BD
"""

from app import app, db
from app import (Cargo, Tribo, Pessoa, PessoaCargo, Utilizador, FolhaCaixa, 
                 Item, CondicaoSaude, Receita, Atividade, Conta, Progresso, ProgressoModelo)
import json
import os
from datetime import datetime
from collections import defaultdict
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt(app)

# Caminhos dos ficheiros JSON antigos
FICHEIRO_CARGOS = "cargos.json"
FICHEIRO_TRIBOS = "tribos.json"
FICHEIRO_UTILIZADORES = "utilizadores.json"
FICHEIRO_MATERIAL = "material.json"
FICHEIRO_FARMACIA = "farmacia.json"
FICHEIRO_ALERGIAS = "alergias.json"
FICHEIRO_CONDICOES = "condicoes.json"
FICHEIRO_COZINHA = "inventario_cozinha.json"
FICHEIRO_RECEITAS = "receitas.json"
FICHEIRO_CALENDARIO = "calendario.json"
FICHEIRO_CONTAS = "contas.json"
FICHEIRO_PROGRESSO = "progresso.json"
FICHEIRO_PROGRESSO_MODELO = "progresso_modelo.json"
DIRETORIO_TESOURARIA = "tesouraria"

def carregar_json(caminho, padrao=None):
    """Carrega um ficheiro JSON, retorna padrão se não existir"""
    if os.path.exists(caminho):
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️  Erro ao ler {caminho}, usando padrão")
            return padrao if padrao else {}
    return padrao if padrao else {}

def migrar_cargos():
    """Migra cargos.json → tabela cargos"""
    print("\n📋 Migrando Cargos...")
    cargos_data = carregar_json(FICHEIRO_CARGOS)
    
    if not cargos_data:
        print("   ⚠️  Nenhum cargo encontrado, criando cargos padrão...")
        cargos_data = {
            "Chefe": "#bb2124",
            "Subchefe": "#f37021",
            "Secretário": "#fdc82f",
            "Tesoureiro": "#8cc63f",
            "Guia": "#29abe2",
            "Subguia": "#662d91"
        }
    
    count = 0
    for nome, cor in cargos_data.items():
        if not Cargo.query.filter_by(nome=nome).first():
            db.session.add(Cargo(nome=nome, cor=cor))
            count += 1
    
    db.session.commit()
    print(f"   ✅ {count} cargos migrados")

def migrar_tribos_e_pessoas():
    """Migra tribos.json → tabelas tribos, pessoas, pessoa_cargo"""
    print("\n🏕️  Migrando Tribos e Pessoas...")
    tribos_data = carregar_json(FICHEIRO_TRIBOS)
    
    if not tribos_data:
        print("   ⚠️  Nenhuma tribo encontrada")
        return
    
    tribos_count = 0
    pessoas_count = 0
    
    for nome_tribo, membros in tribos_data.items():
        # Criar tribo
        tribo = Tribo.query.filter_by(nome=nome_tribo).first()
        if not tribo:
            tribo = Tribo(nome=nome_tribo)
            db.session.add(tribo)
            db.session.flush()
            tribos_count += 1
        
        # Criar pessoas
        for membro in membros:
            if isinstance(membro, dict):
                nome_pessoa = membro.get('nome')
                cargos_pessoa = membro.get('cargo', [])
            else:
                nome_pessoa = membro
                cargos_pessoa = []
            
            pessoa = Pessoa.query.filter_by(nome=nome_pessoa).first()
            if not pessoa:
                pessoa = Pessoa(nome=nome_pessoa, tribo_id=tribo.id)
                db.session.add(pessoa)
                db.session.flush()
                pessoas_count += 1
                
                # Adicionar cargos
                if isinstance(cargos_pessoa, list):
                    for cargo_nome in cargos_pessoa:
                        cargo = Cargo.query.filter_by(nome=cargo_nome).first()
                        if cargo:
                            pessoa_cargo = PessoaCargo(pessoa_id=pessoa.id, cargo_nome=cargo.nome)
                            db.session.add(pessoa_cargo)
    
    db.session.commit()
    print(f"   ✅ {tribos_count} tribos e {pessoas_count} pessoas migradas")

def migrar_utilizadores():
    """Migra utilizadores.json → tabela utilizadores"""
    print("\n👥 Migrando Utilizadores...")
    users_data = carregar_json(FICHEIRO_UTILIZADORES)
    
    count = 0
    for username, dados in users_data.items():
        if not Utilizador.query.filter_by(username=username).first():
            password_hash = dados.get('password_hash') if isinstance(dados, dict) else dados
            db.session.add(Utilizador(username=username, password_hash=password_hash))
            count += 1
    
    db.session.commit()
    print(f"   ✅ {count} utilizadores migrados")

def migrar_tesouraria():
    """Migra ficheiros JSON da tesouraria → tabela folha_caixa"""
    print("\n💰 Migrando Tesouraria...")
    
    if not os.path.exists(DIRETORIO_TESOURARIA):
        print("   ⚠️  Pasta tesouraria não encontrada")
        return
    
    count = 0
    for filename in os.listdir(DIRETORIO_TESOURARIA):
        if filename.endswith('.json'):
            entidade = filename.replace('.json', '')
            caminho = os.path.join(DIRETORIO_TESOURARIA, filename)
            
            transacoes = carregar_json(caminho, [])
            
            for t in transacoes:
                if isinstance(t, dict):
                    nova_transacao = FolhaCaixa(
                        entidade_nome=entidade,
                        data=datetime.strptime(t['data'], '%Y-%m-%d').date(),
                        descricao=t.get('descricao', ''),
                        tipo=t['tipo'],
                        valor=float(t['valor']),
                        comprovativo_url=t.get('comprovativo')
                    )
                    db.session.add(nova_transacao)
                    count += 1
    
    db.session.commit()
    print(f"   ✅ {count} transações migradas")

def migrar_inventarios():
    """Migra material.json, farmacia.json, inventario_cozinha.json → tabela itens"""
    print("\n📦 Migrando Inventários...")
    
    # Material
    material = carregar_json(FICHEIRO_MATERIAL, [])
    count_material = 0
    for item in material:
        if isinstance(item, dict):
            db.session.add(Item(
                categoria='Material',
                nome=item['nome'],
                quantidade=str(item.get('quantidade', '')),
                localizacao=item.get('localizacao', ''),
                tribo_clan=item.get('tribo_clan', ''),
                observacoes=item.get('observacoes', '')
            ))
            count_material += 1
    
    # Farmácia
    farmacia = carregar_json(FICHEIRO_FARMACIA, [])
    count_farmacia = 0
    for item in farmacia:
        if isinstance(item, dict):
            db.session.add(Item(
                categoria='Farmácia',
                nome=item['nome'],
                quantidade=str(item.get('quantidade', '')),
                localizacao=item.get('localizacao', ''),
                tribo_clan=item.get('tribo_clan', ''),
                observacoes=item.get('observacoes', '')
            ))
            count_farmacia += 1
    
    # Cozinha
    cozinha = carregar_json(FICHEIRO_COZINHA, [])
    count_cozinha = 0
    for item in cozinha:
        if isinstance(item, dict):
            db.session.add(Item(
                categoria='Cozinha',
                nome=item['nome'],
                quantidade=str(item.get('quantidade', '')),
                localizacao=item.get('unidade', ''),
                tribo_clan=item.get('categoria', ''),
                comprovativo=item.get('comprovativo', '')
            ))
            count_cozinha += 1
    
    db.session.commit()
    print(f"   ✅ {count_material} material, {count_farmacia} farmácia, {count_cozinha} cozinha migrados")

def migrar_saude():
    """Migra alergias.json e condicoes.json → tabela condicoes_saude"""
    print("\n🏥 Migrando Condições de Saúde...")
    
    # Alergias
    alergias = carregar_json(FICHEIRO_ALERGIAS)
    count_alergias = 0
    for pessoa, detalhes in alergias.items():
        if isinstance(detalhes, str):
            for alergia in detalhes.split(','):
                if alergia.strip():
                    db.session.add(CondicaoSaude(
                        pessoa_nome=pessoa,
                        tipo='Alergia',
                        detalhe=alergia.strip()
                    ))
                    count_alergias += 1
        elif isinstance(detalhes, list):
            for alergia in detalhes:
                db.session.add(CondicaoSaude(
                    pessoa_nome=pessoa,
                    tipo='Alergia',
                    detalhe=alergia
                ))
                count_alergias += 1
    
    # Condições
    condicoes = carregar_json(FICHEIRO_CONDICOES)
    count_condicoes = 0
    for pessoa, detalhes in condicoes.items():
        if isinstance(detalhes, str):
            for condicao in detalhes.split(','):
                if condicao.strip():
                    db.session.add(CondicaoSaude(
                        pessoa_nome=pessoa,
                        tipo='Condição',
                        detalhe=condicao.strip()
                    ))
                    count_condicoes += 1
        elif isinstance(detalhes, list):
            for condicao in detalhes:
                db.session.add(CondicaoSaude(
                    pessoa_nome=pessoa,
                    tipo='Condição',
                    detalhe=condicao
                ))
                count_condicoes += 1
    
    db.session.commit()
    print(f"   ✅ {count_alergias} alergias e {count_condicoes} condições migradas")

def migrar_receitas():
    """Migra receitas.json → tabela receitas"""
    print("\n🍳 Migrando Receitas...")
    receitas = carregar_json(FICHEIRO_RECEITAS, [])
    
    count = 0
    for r in receitas:
        if isinstance(r, dict):
            db.session.add(Receita(
                nome=r['nome'],
                ingredientes=r.get('ingredientes'),
                instrucoes=r.get('instrucoes') or r.get('passos'),
                imagem_url=r.get('imagem_url'),
                link_ficheiro=r.get('link_ficheiro'),
                tempo_preparacao=r.get('tempo_preparacao'),
                dificuldade=r.get('dificuldade'),
                porcoes_base=r.get('porcoes_base')
            ))
            count += 1
    
    db.session.commit()
    print(f"   ✅ {count} receitas migradas")

def migrar_calendario():
    """Migra calendario.json → tabela atividades_calendario"""
    print("\n📅 Migrando Calendário...")
    atividades = carregar_json(FICHEIRO_CALENDARIO, [])
    
    count = 0
    for a in atividades:
        if isinstance(a, dict):
            db.session.add(Atividade(
                id=a.get('id', str(uuid.uuid4())),
                titulo=a['title'],
                data_inicio=datetime.fromisoformat(a['start']),
                data_fim=datetime.fromisoformat(a['end']) if a.get('end') else datetime.fromisoformat(a['start']),
                descricao=a.get('details', ''),
                tipo=a.get('type', ''),
                all_day=a.get('allDay', False)
            ))
            count += 1
    
    db.session.commit()
    print(f"   ✅ {count} atividades migradas")

def migrar_contas():
    """Migra contas.json → tabela contas"""
    print("\n💳 Migrando Contas...")
    contas = carregar_json(FICHEIRO_CONTAS)
    
    count = 0
    for nome, valor in contas.items():
        if not Conta.query.filter_by(pessoa_nome=nome).first():
            db.session.add(Conta(pessoa_nome=nome, valor=float(valor)))
            count += 1
    
    db.session.commit()
    print(f"   ✅ {count} contas migradas")

def migrar_progresso():
    """Migra progresso.json e progresso_modelo.json → tabelas progresso e progresso_modelo"""
    print("\n📊 Migrando Progresso...")
    
    # Modelo
    modelo = carregar_json(FICHEIRO_PROGRESSO_MODELO)
    if modelo and not ProgressoModelo.query.first():
        db.session.add(ProgressoModelo(modelo=modelo))
    
    # Progresso individual
    progresso_data = carregar_json(FICHEIRO_PROGRESSO)
    count = 0
    for nome, dados in progresso_data.items():
        pessoa = Pessoa.query.filter_by(nome=nome).first()
        if pessoa and not Progresso.query.filter_by(pessoa_id=pessoa.id).first():
            db.session.add(Progresso(pessoa_id=pessoa.id, dados_progresso=dados))
            count += 1
    
    db.session.commit()
    print(f"   ✅ Modelo e {count} progressos migrados")

def main():
    """Executa todas as migrações"""
    print("=" * 60)
    print("🚀 INICIANDO MIGRAÇÃO JSON → BASE DE DADOS")
    print("=" * 60)
    
    with app.app_context():
        # Criar tabelas se não existirem
        print("\n🔧 Criando estrutura da base de dados...")
        db.create_all()
        print("   ✅ Tabelas criadas")
        
        # Executar migrações na ordem correta
        try:
            migrar_cargos()
            migrar_tribos_e_pessoas()
            migrar_utilizadores()
            migrar_tesouraria()
            migrar_inventarios()
            migrar_saude()
            migrar_receitas()
            migrar_calendario()
            migrar_contas()
            migrar_progresso()
            
            print("\n" + "=" * 60)
            print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
            print("=" * 60)
            print("\n💡 Próximos passos:")
            print("   1. Verificar dados: python verificar_bd.py")
            print("   2. Testar aplicação: python app.py")
            print("   3. Fazer backup dos JSONs: mkdir backup && move *.json backup/")
            print("\n")
            
        except Exception as e:
            print(f"\n❌ ERRO durante migração: {e}")
            print("   A base de dados pode estar parcialmente migrada")
            db.session.rollback()
            raise

if __name__ == '__main__':
    main()