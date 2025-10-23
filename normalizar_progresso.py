from app import app, db, Progresso
import json

def normalizar_valor(valor):
    """Normaliza os valores de progresso"""
    if valor in ["feito", "concluído"]:
        return "concluído"
    elif valor in ["pendente", "não"]:
        return "não"
    elif valor == "em_progresso":
        return "em_progresso"
    else:
        return valor

def normalizar_dicionario(obj):
    """Normaliza recursivamente um dicionário de progresso"""
    if isinstance(obj, dict):
        return {k: normalizar_dicionario(v) for k, v in obj.items()}
    elif isinstance(obj, str):
        return normalizar_valor(obj)
    else:
        return obj

def main():
    print("=" * 60)
    print("🔄 NORMALIZANDO DADOS DE PROGRESSO")
    print("=" * 60)
    
    with app.app_context():
        progressos = Progresso.query.all()
        
        print(f"\n📊 Total de registos: {len(progressos)}")
        
        count_alterados = 0
        for prog in progressos:
            dados_originais = prog.dados_progresso.copy() if prog.dados_progresso else {}
            
            # Normalizar os dados
            prog.dados_progresso = normalizar_dicionario(prog.dados_progresso)
            
            # Verificar se houve alteração
            if dados_originais != prog.dados_progresso:
                count_alterados += 1
                print(f"   ✏️  {prog.pessoa.nome}")
        
        db.session.commit()
        
        print(f"\n✅ {count_alterados} registos normalizados")
        print("\n" + "=" * 60)
        print("Executar agora: python app.py")
        print("=" * 60)

if __name__ == '__main__':
    main()