"""
Script de Verificação Completa da Base de Dados
Mostra todos os dados armazenados em cada tabela
"""

from app import (app, db, Utilizador, Tribo, Pessoa, Cargo, Item, CondicaoSaude, 
                 Receita, Atividade, Conta, Progresso, ProgressoModelo, FolhaCaixa)
from datetime import datetime

def linha_separadora(titulo=""):
    if titulo:
        print(f"\n{'=' * 60}")
        print(f"  {titulo}")
        print('=' * 60)
    else:
        print("-" * 60)

def verificar_utilizadores():
    linha_separadora("👥 UTILIZADORES")
    users = Utilizador.query.all()
    print(f"Total: {len(users)}")
    for u in users:
        print(f"  • {u.username} (ID: {u.id})")

def verificar_tribos_e_pessoas():
    linha_separadora("🏕️  TRIBOS E PESSOAS")
    tribos = Tribo.query.all()
    print(f"Total de Tribos: {len(tribos)}\n")
    
    for tribo in tribos:
        pessoas = Pessoa.query.filter_by(tribo_id=tribo.id).order_by(Pessoa.ordem).all()
        print(f"📍 {tribo.nome} ({len(pessoas)} membros)")
        for p in pessoas:
            cargos = [pc.cargo.nome for pc in p.cargos]
            cargos_str = f" - {', '.join(cargos)}" if cargos else ""
            print(f"   {p.ordem}. {p.nome}{cargos_str}")
        print()

def verificar_cargos():
    linha_separadora("🎖️  CARGOS")
    cargos = Cargo.query.all()
    print(f"Total: {len(cargos)}")
    for c in cargos:
        print(f"  • {c.nome} (Cor: {c.cor})")

def verificar_calendario():
    linha_separadora("📅 CALENDÁRIO")
    atividades = Atividade.query.order_by(Atividade.data_inicio.desc()).all()
    print(f"Total: {len(atividades)}")
    
    if len(atividades) == 0:
        print("  ⚠️  Nenhuma atividade no calendário")
    else:
        print("\nÚltimas 10 atividades:")
        for a in atividades[:10]:
            data_str = a.data_inicio.strftime("%Y-%m-%d")
            tipo_str = f" [{a.tipo}]" if a.tipo else ""
            print(f"  • {data_str} - {a.titulo}{tipo_str}")
            if a.descricao:
                print(f"    Descrição: {a.descricao[:50]}...")

def verificar_material():
    linha_separadora("📦 MATERIAL")
    itens = Item.query.filter_by(categoria='Material').all()
    print(f"Total: {len(itens)}")
    
    if len(itens) == 0:
        print("  ⚠️  Nenhum item de material")
    else:
        # Agrupar por tribo/clan
        por_entidade = {}
        for item in itens:
            entidade = item.tribo_clan or 'Sem classificação'
            if entidade not in por_entidade:
                por_entidade[entidade] = []
            por_entidade[entidade].append(item)
        
        for entidade, items in sorted(por_entidade.items()):
            print(f"\n  📍 {entidade}:")
            for item in sorted(items, key=lambda x: x.nome):
                loc = f" ({item.localizacao})" if item.localizacao else ""
                obs = f" - {item.observacoes[:30]}..." if item.observacoes else ""
                print(f"     • {item.nome}: {item.quantidade}{loc}{obs}")

def verificar_farmacia():
    linha_separadora("🏥 FARMÁCIA")
    itens = Item.query.filter_by(categoria='Farmácia').all()
    print(f"Total: {len(itens)}")
    
    if len(itens) == 0:
        print("  ⚠️  Nenhum item de farmácia")
    else:
        por_entidade = {}
        for item in itens:
            entidade = item.tribo_clan or 'Sem classificação'
            if entidade not in por_entidade:
                por_entidade[entidade] = []
            por_entidade[entidade].append(item)
        
        for entidade, items in sorted(por_entidade.items()):
            print(f"\n  📍 {entidade}:")
            for item in sorted(items, key=lambda x: x.nome):
                loc = f" ({item.localizacao})" if item.localizacao else ""
                print(f"     • {item.nome}: {item.quantidade}{loc}")

def verificar_cozinha():
    linha_separadora("🍳 COZINHA - INVENTÁRIO")
    itens = Item.query.filter_by(categoria='Cozinha').all()
    print(f"Total de Itens: {len(itens)}")
    
    if len(itens) == 0:
        print("  ⚠️  Nenhum item de cozinha")
    else:
        # Agrupar por categoria (armazenada em tribo_clan)
        por_categoria = {}
        for item in itens:
            cat = item.tribo_clan or 'Outros'
            if cat not in por_categoria:
                por_categoria[cat] = []
            por_categoria[cat].append(item)
        
        for categoria, items in sorted(por_categoria.items()):
            print(f"\n  📍 {categoria}:")
            for item in sorted(items, key=lambda x: x.nome):
                unidade = item.localizacao or ''  # unidade está em localizacao
                print(f"     • {item.nome}: {item.quantidade} {unidade}")

def verificar_receitas():
    linha_separadora("🍳 COZINHA - RECEITAS")
    receitas = Receita.query.all()
    print(f"Total: {len(receitas)}")
    
    if len(receitas) == 0:
        print("  ⚠️  Nenhuma receita")
    else:
        for r in sorted(receitas, key=lambda x: x.nome):
            tipo = "📄 Ficheiro" if r.link_ficheiro else "📝 Manual"
            print(f"  {tipo} {r.nome}")
            if r.tempo_preparacao:
                print(f"     ⏱️  {r.tempo_preparacao}")
            if r.dificuldade:
                print(f"     🎯 {r.dificuldade}")
            if r.ingredientes and not r.link_ficheiro:
                print(f"     🥕 {len(r.ingredientes)} ingredientes")

def verificar_saude():
    linha_separadora("🏥 CONDIÇÕES DE SAÚDE")
    
    # Alergias
    alergias = CondicaoSaude.query.filter_by(tipo='Alergia').all()
    print(f"Alergias: {len(alergias)}")
    if len(alergias) > 0:
        alergias_por_pessoa = {}
        for a in alergias:
            if a.pessoa_nome not in alergias_por_pessoa:
                alergias_por_pessoa[a.pessoa_nome] = []
            alergias_por_pessoa[a.pessoa_nome].append(a.detalhe)
        
        for pessoa, detalhes in sorted(alergias_por_pessoa.items()):
            print(f"  🔴 {pessoa}: {', '.join(detalhes)}")
    
    print()
    
    # Condições
    condicoes = CondicaoSaude.query.filter_by(tipo='Condição').all()
    print(f"Condições Médicas: {len(condicoes)}")
    if len(condicoes) > 0:
        condicoes_por_pessoa = {}
        for c in condicoes:
            if c.pessoa_nome not in condicoes_por_pessoa:
                condicoes_por_pessoa[c.pessoa_nome] = []
            condicoes_por_pessoa[c.pessoa_nome].append(c.detalhe)
        
        for pessoa, detalhes in sorted(condicoes_por_pessoa.items()):
            print(f"  🟡 {pessoa}: {', '.join(detalhes)}")

def verificar_tesouraria():
    linha_separadora("💰 TESOURARIA")
    
    # Obter todas as entidades únicas
    entidades = db.session.query(FolhaCaixa.entidade_nome).distinct().all()
    entidades = [e[0] for e in entidades]
    
    print(f"Entidades com movimentos: {len(entidades)}")
    
    for entidade in sorted(entidades):
        transacoes = FolhaCaixa.query.filter_by(entidade_nome=entidade).order_by(
            FolhaCaixa.data.desc()).all()
        
        total_entradas = sum(t.valor for t in transacoes if t.tipo == 'Entrada')
        total_saidas = sum(t.valor for t in transacoes if t.tipo == 'Saída')
        saldo = total_entradas - total_saidas
        
        print(f"\n  📍 {entidade}:")
        print(f"     Transações: {len(transacoes)}")
        print(f"     Entradas: {total_entradas:.2f}€")
        print(f"     Saídas: {total_saidas:.2f}€")
        print(f"     Saldo: {saldo:.2f}€")

def verificar_contas():
    linha_separadora("💳 CONTAS INDIVIDUAIS")
    contas = Conta.query.all()
    print(f"Total: {len(contas)}")
    
    if len(contas) > 0:
        contas_ordenadas = sorted(contas, key=lambda x: x.valor, reverse=True)
        print("\nTop 10:")
        for c in contas_ordenadas[:10]:
            print(f"  • {c.pessoa_nome}: {c.valor:.2f}€")

def verificar_progresso():
    linha_separadora("📊 PROGRESSO")
    
    # Modelo
    modelo = ProgressoModelo.query.first()
    if modelo and modelo.modelo:
        areas = list(modelo.modelo.keys())
        print(f"Modelo de Progresso: ✅ Configurado ({len(areas)} áreas)")
        print(f"  Áreas: {', '.join(areas)}")
    else:
        print("Modelo de Progresso: ❌ Não configurado")
    
    print()
    
    # Progresso individual
    progressos = Progresso.query.join(Pessoa).all()
    print(f"Pessoas com progresso: {len(progressos)}")
    
    if len(progressos) > 0:
        print("\nAmostra (primeiros 5):")
        for p in progressos[:5]:
            if p.dados_progresso:
                # Contar objetivos concluídos
                total_concluidos = 0
                total_objetivos = 0
                
                if isinstance(p.dados_progresso, dict):
                    for area_data in p.dados_progresso.values():
                        if isinstance(area_data, dict):
                            for trilho_data in area_data.values():
                                if isinstance(trilho_data, dict):
                                    for estado in trilho_data.values():
                                        total_objetivos += 1
                                        if estado in ['concluído', 'feito']:
                                            total_concluidos += 1
                
                percentagem = (total_concluidos / total_objetivos * 100) if total_objetivos > 0 else 0
                print(f"  • {p.pessoa.nome}: {total_concluidos}/{total_objetivos} ({percentagem:.1f}%)")

def verificar_integridade():
    linha_separadora("🔍 VERIFICAÇÃO DE INTEGRIDADE")
    
    erros = []
    avisos = []
    
    # 1. Pessoas sem progresso
    pessoas = Pessoa.query.all()
    pessoas_sem_progresso = []
    for p in pessoas:
        if not Progresso.query.filter_by(pessoa_id=p.id).first():
            pessoas_sem_progresso.append(p.nome)
    
    if pessoas_sem_progresso:
        avisos.append(f"⚠️  {len(pessoas_sem_progresso)} pessoas sem progresso: {', '.join(pessoas_sem_progresso[:3])}")
    
    # 2. Pessoas sem conta
    pessoas_sem_conta = []
    for p in pessoas:
        if not Conta.query.filter_by(pessoa_nome=p.nome).first():
            pessoas_sem_conta.append(p.nome)
    
    if pessoas_sem_conta:
        avisos.append(f"⚠️  {len(pessoas_sem_conta)} pessoas sem conta: {', '.join(pessoas_sem_conta[:3])}")
    
    # 3. Verificar se o modelo de progresso existe
    if not ProgressoModelo.query.first():
        erros.append("❌ Modelo de progresso não configurado")
    
    # 4. Verificar cargos sem cor
    cargos_sem_cor = Cargo.query.filter_by(cor=None).count()
    if cargos_sem_cor > 0:
        avisos.append(f"⚠️  {cargos_sem_cor} cargos sem cor definida")
    
    # Mostrar resultados
    if erros:
        print("\n🔴 ERROS ENCONTRADOS:")
        for erro in erros:
            print(f"  {erro}")
    
    if avisos:
        print("\n🟡 AVISOS:")
        for aviso in avisos:
            print(f"  {aviso}")
    
    if not erros and not avisos:
        print("\n✅ Nenhum problema encontrado!")

def resumo_estatistico():
    linha_separadora("📈 RESUMO ESTATÍSTICO")
    
    stats = {
        "Utilizadores": Utilizador.query.count(),
        "Tribos": Tribo.query.count(),
        "Pessoas": Pessoa.query.count(),
        "Cargos": Cargo.query.count(),
        "Atividades Calendário": Atividade.query.count(),
        "Items Material": Item.query.filter_by(categoria='Material').count(),
        "Items Farmácia": Item.query.filter_by(categoria='Farmácia').count(),
        "Items Cozinha": Item.query.filter_by(categoria='Cozinha').count(),
        "Receitas": Receita.query.count(),
        "Condições Saúde": CondicaoSaude.query.count(),
        "Transações Tesouraria": FolhaCaixa.query.count(),
        "Contas": Conta.query.count(),
        "Registos Progresso": Progresso.query.count(),
    }
    
    for nome, valor in stats.items():
        print(f"  {nome:.<30} {valor:>5}")

def main():
    print("\n" + "=" * 60)
    print("  🔍 VERIFICAÇÃO COMPLETA DA BASE DE DADOS")
    print("=" * 60)
    print(f"  Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    with app.app_context():
        try:
            # Verificações individuais
            verificar_utilizadores()
            verificar_tribos_e_pessoas()
            verificar_cargos()
            verificar_calendario()
            verificar_material()
            verificar_farmacia()
            verificar_cozinha()
            verificar_receitas()
            verificar_saude()
            verificar_tesouraria()
            verificar_contas()
            verificar_progresso()
            
            # Verificações finais
            verificar_integridade()
            resumo_estatistico()
            
            print("\n" + "=" * 60)
            print("  ✅ VERIFICAÇÃO CONCLUÍDA")
            print("=" * 60 + "\n")
            
        except Exception as e:
            print(f"\n❌ ERRO durante verificação: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main()