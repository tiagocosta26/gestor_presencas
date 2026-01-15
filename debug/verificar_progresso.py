from app import app, db, Progresso, Pessoa, calcular_progresso_bool_do_dicionario, calcular_nivel, carregar_progresso_modelo

def main():
    print("=" * 60)
    print("🔍 VERIFICAÇÃO DE PROGRESSO")
    print("=" * 60)
    
    with app.app_context():
        modelo = carregar_progresso_modelo()
        progressos = Progresso.query.join(Pessoa).all()
        
        print(f"\n📊 Total de pessoas: {len(progressos)}")
        print("\n🎖️  NÍVEIS:")
        
        niveis_count = {"Comunidade": 0, "Serviço": 0, "Partida": 0, "Anilha de Mérito": 0}
        
        for prog in progressos:
            dados_bool = calcular_progresso_bool_do_dicionario(prog.dados_progresso)
            nivel = calcular_nivel(dados_bool, modelo)
            niveis_count[nivel] += 1
            
            # Mostrar apenas os primeiros 5 e os que não são Comunidade
            if nivel != "Comunidade" or len([n for n in niveis_count.values()]) <= 5:
                print(f"   {prog.pessoa.nome:25} → {nivel}")
        
        print("\n📈 RESUMO:")
        for nivel, count in niveis_count.items():
            print(f"   {nivel:20}: {count}")
        
        print("\n" + "=" * 60)

if __name__ == '__main__':
    main()