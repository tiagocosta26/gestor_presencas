"""
Script de Debug: Testar migração de Utilizadores, Calendário e Progresso
"""

from app import app, db, Utilizador, Atividade, Progresso, ProgressoModelo, Pessoa
import json
import os
from datetime import datetime
import uuid

def debug_utilizadores():
    print("\n🔍 DEBUG: Utilizadores")
    print("-" * 40)
    
    if not os.path.exists('utilizadores.json'):
        print("❌ utilizadores.json não existe!")
        return
    
    with open('utilizadores.json', 'r', encoding='utf-8') as f:
        dados = json.load(f)
    
    print(f"📄 Conteúdo do ficheiro:")
    print(f"   Tipo: {type(dados)}")
    print(f"   Estrutura: {dados}")
    
    with app.app_context():
        print(f"\n💾 Na Base de Dados:")
        users = Utilizador.query.all()
        print(f"   Total: {len(users)}")
        for u in users:
            print(f"   - {u.username}")

def debug_calendario():
    print("\n🔍 DEBUG: Calendário")
    print("-" * 40)
    
    if not os.path.exists('calendario.json'):
        print("❌ calendario.json não existe!")
        return
    
    with open('calendario.json', 'r', encoding='utf-8') as f:
        dados = json.load(f)
    
    print(f"📄 Conteúdo do ficheiro:")
    print(f"   Tipo: {type(dados)}")
    print(f"   Total de atividades: {len(dados) if isinstance(dados, list) else 'não é lista'}")
    
    if isinstance(dados, list) and len(dados) > 0:
        print(f"\n   Primeira atividade:")
        primeira = dados[0]
        print(f"   - Chaves: {primeira.keys() if isinstance(primeira, dict) else 'não é dict'}")
        print(f"   - Conteúdo: {primeira}")
    
    with app.app_context():
        print(f"\n💾 Na Base de Dados:")
        atividades = Atividade.query.all()
        print(f"   Total: {len(atividades)}")
        for a in atividades[:3]:
            print(f"   - {a.titulo} ({a.data_inicio})")

def debug_progresso():
    print("\n🔍 DEBUG: Progresso")
    print("-" * 40)
    
    # Modelo
    if os.path.exists('progresso_modelo.json'):
        with open('progresso_modelo.json', 'r', encoding='utf-8') as f:
            modelo = json.load(f)
        print(f"📄 progresso_modelo.json:")
        print(f"   Tipo: {type(modelo)}")
        print(f"   Chaves: {list(modelo.keys()) if isinstance(modelo, dict) else 'não é dict'}")
    else:
        print("❌ progresso_modelo.json não existe!")
        modelo = None
    
    # Progresso individual
    if os.path.exists('progresso.json'):
        with open('progresso.json', 'r', encoding='utf-8') as f:
            progresso = json.load(f)
        print(f"\n📄 progresso.json:")
        print(f"   Tipo: {type(progresso)}")
        print(f"   Total de pessoas: {len(progresso) if isinstance(progresso, dict) else 'não é dict'}")
        if isinstance(progresso, dict):
            primeira_pessoa = list(progresso.keys())[0] if progresso else None
            if primeira_pessoa:
                print(f"   Exemplo ({primeira_pessoa}): {type(progresso[primeira_pessoa])}")
    else:
        print("❌ progresso.json não existe!")
    
    with app.app_context():
        print(f"\n💾 Na Base de Dados:")
        
        # Modelo
        modelo_db = ProgressoModelo.query.first()
        if modelo_db:
            print(f"   ✅ Modelo de progresso existe")
            print(f"      Tipo: {type(modelo_db.modelo)}")
        else:
            print(f"   ❌ Modelo de progresso NÃO existe")
        
        # Progresso individual
        progressos = Progresso.query.all()
        print(f"   Total de progressos: {len(progressos)}")
        for p in progressos[:3]:
            print(f"   - {p.pessoa.nome}: {type(p.dados_progresso)}")

def migrar_forcado_utilizadores():
    """Tenta migrar utilizadores de forma forçada"""
    print("\n🔧 Tentando migração forçada de utilizadores...")
    
    with app.app_context():
        if os.path.exists('utilizadores.json'):
            with open('utilizadores.json', 'r', encoding='utf-8') as f:
                dados = json.load(f)
            
            for username, info in dados.items():
                user_existe = Utilizador.query.filter_by(username=username).first()
                if not user_existe:
                    # Extrair password_hash
                    if isinstance(info, dict):
                        pwd_hash = info.get('password_hash') or info.get('password')
                    else:
                        pwd_hash = info
                    
                    if pwd_hash:
                        novo_user = Utilizador(username=username, password_hash=pwd_hash)
                        db.session.add(novo_user)
                        print(f"   ➕ {username}")
            
            db.session.commit()
            print("   ✅ Concluído")
        else:
            print("   ❌ Ficheiro não encontrado")

def migrar_forcado_calendario():
    """Tenta migrar calendário de forma forçada"""
    print("\n🔧 Tentando migração forçada de calendário...")
    
    with app.app_context():
        if os.path.exists('calendario.json'):
            with open('calendario.json', 'r', encoding='utf-8') as f:
                dados = json.load(f)
            
            count = 0
            for atividade in dados:
                if isinstance(atividade, dict):
                    try:
                        ativ_id = atividade.get('id', str(uuid.uuid4()))
                        
                        # Verificar se já existe
                        if Atividade.query.get(ativ_id):
                            continue
                        
                        # Parse de datas com diferentes formatos
                        start_str = atividade.get('start')
                        end_str = atividade.get('end', start_str)
                        
                        # Tentar vários formatos
                        for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S.%fZ']:
                            try:
                                data_inicio = datetime.strptime(start_str, fmt)
                                data_fim = datetime.strptime(end_str, fmt)
                                break
                            except:
                                continue
                        else:
                            # Formato ISO com fromisoformat
                            data_inicio = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                            data_fim = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                        
                        nova_ativ = Atividade(
                            id=ativ_id,
                            titulo=atividade.get('title', 'Sem título'),
                            data_inicio=data_inicio,
                            data_fim=data_fim,
                            descricao=atividade.get('details', '') or atividade.get('description', ''),
                            tipo=atividade.get('type', ''),
                            all_day=atividade.get('allDay', False)
                        )
                        db.session.add(nova_ativ)
                        count += 1
                        print(f"   ➕ {atividade.get('title')}")
                    except Exception as e:
                        print(f"   ❌ Erro em {atividade.get('title')}: {e}")
            
            db.session.commit()
            print(f"   ✅ {count} atividades migradas")
        else:
            print("   ❌ Ficheiro não encontrado")

def migrar_forcado_progresso():
    """Tenta migrar progresso de forma forçada"""
    print("\n🔧 Tentando migração forçada de progresso...")
    
    with app.app_context():
        # Modelo
        if os.path.exists('progresso_modelo.json'):
            with open('progresso_modelo.json', 'r', encoding='utf-8') as f:
                modelo = json.load(f)
            
            modelo_existe = ProgressoModelo.query.first()
            if not modelo_existe:
                db.session.add(ProgressoModelo(modelo=modelo))
                db.session.commit()
                print("   ✅ Modelo migrado")
            else:
                print("   ⚠️  Modelo já existe")
        
        # Progresso individual
        if os.path.exists('progresso.json'):
            with open('progresso.json', 'r', encoding='utf-8') as f:
                progresso_data = json.load(f)
            
            count = 0
            for nome_pessoa, dados_prog in progresso_data.items():
                pessoa = Pessoa.query.filter_by(nome=nome_pessoa).first()
                
                if pessoa:
                    prog_existe = Progresso.query.filter_by(pessoa_id=pessoa.id).first()
                    if not prog_existe:
                        db.session.add(Progresso(
                            pessoa_id=pessoa.id,
                            dados_progresso=dados_prog
                        ))
                        count += 1
                        print(f"   ➕ {nome_pessoa}")
                else:
                    print(f"   ⚠️  Pessoa '{nome_pessoa}' não encontrada")
            
            db.session.commit()
            print(f"   ✅ {count} progressos migrados")
        else:
            print("   ❌ Ficheiro não encontrado")

def main():
    print("=" * 60)
    print("🔍 DEBUG & MIGRAÇÃO FORÇADA")
    print("=" * 60)
    
    # 1. Debug
    debug_utilizadores()
    debug_calendario()
    debug_progresso()
    
    # 2. Perguntar se quer migrar
    print("\n" + "=" * 60)
    resposta = input("\n❓ Tentar migração forçada? (s/n): ").strip().lower()
    
    if resposta == 's':
        migrar_forcado_utilizadores()
        migrar_forcado_calendario()
        migrar_forcado_progresso()
        
        print("\n" + "=" * 60)
        print("✅ MIGRAÇÃO FORÇADA CONCLUÍDA")
        print("=" * 60)
        print("\n💡 Execute: python verificar_bd.py")
    else:
        print("\n❌ Migração cancelada")

if __name__ == '__main__':
    main()