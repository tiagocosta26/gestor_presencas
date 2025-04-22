from flask import Flask, render_template, request, redirect, url_for
import csv, os, re
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)

# Diretório para guardar os ficheiros
DIRETORIO_PRESENCAS = "registos"
os.makedirs(DIRETORIO_PRESENCAS, exist_ok=True)

def limpar_nome(nome):
    # Permite letras, números, espaços e alguns caracteres especiais como acentos
    nome_limpo = re.sub(r'[^A-Za-z0-9áéíóúãõàèùçÁÉÍÓÚÀÈÙÇ_\-@ ]', '_', nome)
    return nome_limpo

@app.route("/", methods=["GET", "POST"])
def index():
    tribos = {
        "benenson": ["Tiago Costa", "Filipa Moreno", "Inês Caetano", "Maria Farropas", "Ana Sofia Matos", "Rodrigo Morais"],
        "dunant": ["Diana Moreno", "Leonor Cera", "Filipe Mendes", "Gonçalo Silvestre", "Maria Canto", "Leandro Alberto", "Diogo Caetano" ],
        "leonor": ["António Faustino", "Rafael Ferreira", "Lara Serra", "Marta Mendes", "Mariana Quitério", "Joana Caetano"]
    }

    if request.method == "POST":
        atividade = request.form["atividade"]
        atividade_limpa = limpar_nome(atividade)
        data_inicio = request.form["data_inicio"]
        data_fim = request.form["data_fim"]
        tribos_selecionadas = request.form["tribos_selecionadas"].split(",")

        elementos = []
        for tribo in tribos_selecionadas:
            elementos.extend(tribos.get(tribo, []))

        presencas = {
            nome: "Sim" if request.form.get(f"presenca_{nome}") == "Sim" else "Não"
            for nome in elementos
        }

        nome_ficheiro = f"{atividade_limpa}_{data_inicio}_a_{data_fim}"
        caminho = os.path.join(DIRETORIO_PRESENCAS, f"{nome_ficheiro}.csv")

        with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["Atividade", "Data Início", "Data Fim", "Elemento", "Presente"])
            for nome, presente in presencas.items():
                writer.writerow([atividade, data_inicio, data_fim, nome, presente])

        return redirect(url_for("atividades"))

    from datetime import date
    hoje = date.today().isoformat()
    return render_template("index.html", hoje=hoje)


@app.route("/atividades")
def atividades():
    ficheiros = [f for f in os.listdir(DIRETORIO_PRESENCAS) if f.endswith(".csv")]
    
    # Dicionário para armazenar as atividades agrupadas por mês
    atividades_agrupadas = defaultdict(list)
    
    for ficheiro in ficheiros:
        # Extrair a data de início do nome do ficheiro
        data_inicio = ficheiro.split('_')[1]  # A data está no formato yyyy-mm-dd
        mes_ano = data_inicio[:7]  # Extrair apenas o mês e o ano (yyyy-mm)
        
        # Adicionar o ficheiro à lista correspondente ao mês
        atividades_agrupadas[mes_ano].append(ficheiro)
    
    # Ordenar as chaves (meses) em ordem crescente
    meses_ordenados = sorted(atividades_agrupadas.keys())
    
    return render_template("atividades.html", atividades_agrupadas=atividades_agrupadas, meses_ordenados=meses_ordenados)

@app.route("/atividade/<ficheiro>")
def ver_atividade(ficheiro):
    caminho = os.path.join(DIRETORIO_PRESENCAS, ficheiro)
    dados = {"benenson": [], "dunant": [], "leonor": []}

    if os.path.exists(caminho):
        with open(caminho, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            cabecalho = next(reader)
            
            for linha in reader:
                if len(linha) == 5:
                    atividade, data_inicio, data_fim, nome, presente = linha
                    if nome in ["Tiago Costa", "Filipa Moreno", "Inês Caetano", "Maria Farropas", "Ana Sofia Matos", "Rodrigo Morais"]:
                        tribo = "benenson"
                    elif nome in ["Diana Moreno", "Leonor Cera", "Filipe Mendes", "Gonçalo Silvestre", "Maria Canto", "Leandro Alberto", "Diogo Caetano" ]:
                        tribo = "dunant"
                    elif nome in ["António Faustino", "Rafael Ferreira", "Lara Serra", "Marta Mendes", "Mariana Quitério", "Joana Caetano"]:
                        tribo = "leonor"
                    else:
                        continue  # Se o nome não for de nenhuma tribo, ignoramos a linha
                    
                    dados[tribo].append((nome, presente))

    return render_template("ver_atividade.html", ficheiro=ficheiro, cabecalho=cabecalho, dados=dados)




if __name__ == "__main__":
    app.run(debug=True)
