from app import app, db, Tribo, Pessoa

def verificar_ordem():
    print("=" * 60)
    print("🔍 VERIFICANDO ORDEM DAS PESSOAS")
    print("=" * 60)
    
    with app.app_context():
        tribos = Tribo.query.all()
        
        for tribo in tribos:
            print(f"\n🏕️  {tribo.nome}:")
            pessoas = Pessoa.query.filter_by(tribo_id=tribo.id).order_by(Pessoa.ordem).all()
            
            for pessoa in pessoas:
                print(f"   {pessoa.ordem}: {pessoa.nome}")
        
        print("\n" + "=" * 60)

if __name__ == '__main__':
    verificar_ordem()