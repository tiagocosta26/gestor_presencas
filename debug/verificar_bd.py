from app import app, db, Utilizador, Tribo, Pessoa, Cargo, Item, Receita, Conta

def verificar():
    with app.app_context():
        print("🔍 Verificando Base de Dados...\n")
        
        users = Utilizador.query.all()
        print(f"👥 Utilizadores: {len(users)}")
        for u in users:
            print(f"   - {u.username}")
        
        tribos = Tribo.query.all()
        print(f"\n🏕️  Tribos: {len(tribos)}")
        for t in tribos:
            print(f"   - {t.nome} ({len(t.membros)} membros)")
        
        pessoas = Pessoa.query.all()
        print(f"\n👤 Pessoas: {len(pessoas)}")
        
        cargos = Cargo.query.all()
        print(f"\n🎖️  Cargos: {len(cargos)}")
        for c in cargos:
            print(f"   - {c.nome} ({c.cor})")
        
        material = Item.query.filter_by(categoria='Material').count()
        farmacia = Item.query.filter_by(categoria='Farmácia').count()
        cozinha = Item.query.filter_by(categoria='Cozinha').count()
        print(f"\n📦 Inventário: {material} material, {farmacia} farmácia, {cozinha} cozinha")
        
        receitas = Receita.query.count()
        print(f"\n🍳 Receitas: {receitas}")
        
        contas = Conta.query.count()
        print(f"\n💳 Contas: {contas}")
        
        print("\n✅ Verificação completa!")

if __name__ == '__main__':
    verificar()