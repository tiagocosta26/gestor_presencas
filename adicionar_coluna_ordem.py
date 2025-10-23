from app import app, db, Pessoa, Tribo

def adicionar_coluna_ordem():
    print("=" * 60)
    print("🔧 ADICIONANDO COLUNA 'ordem' À TABELA pessoas")
    print("=" * 60)
    
    with app.app_context():
        # Para SQLite, precisamos adicionar a coluna manualmente
        try:
            # Tentar adicionar a coluna
            with db.engine.connect() as conn:
                conn.execute(db.text("ALTER TABLE pessoas ADD COLUMN ordem INTEGER DEFAULT 0"))
                conn.commit()
            print("✅ Coluna 'ordem' adicionada com sucesso!")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("⚠️  Coluna 'ordem' já existe")
            else:
                print(f"❌ Erro ao adicionar coluna: {e}")
                return
        
        # Inicializar valores de ordem para todas as pessoas
        print("\n📊 Inicializando valores de ordem...")
        
        tribos = Tribo.query.all()
        count = 0
        
        for tribo in tribos:
            # Ordenar por ID (ordem atual)
            pessoas = Pessoa.query.filter_by(tribo_id=tribo.id).order_by(Pessoa.id).all()
            
            for index, pessoa in enumerate(pessoas):
                pessoa.ordem = index
                count += 1
        
        db.session.commit()
        
        print(f"✅ {count} pessoas ordenadas")
        print("\n" + "=" * 60)
        print("Concluído! Execute: python app.py")
        print("=" * 60)

if __name__ == '__main__':
    adicionar_coluna_ordem()