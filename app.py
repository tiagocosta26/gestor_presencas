from flask import Flask, render_template, request, redirect, url_for, jsonify
import csv, os, re, json
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)

# Diretório para guardar os ficheiros
DIRETORIO_PRESENCAS = "registos"
os.makedirs(DIRETORIO_PRESENCAS, exist_ok=True)

# Ficheiro JSON para guardar as tribos
FICHEIRO_TRIBOS = "tribos.json"

# Função para carregar tribos do ficheiro JSON
def carregar_tribos():
    if os.path.exists(FICHEIRO_TRIBOS):
        with open(FICHEIRO_TRIBOS, encoding="utf-8") as f:
            return json.load(f)
    return {}

# Função para guardar tribos no ficheiro JSON
def guardar_tribos(tribos):
    with open(FICHEIRO_TRIBOS, "w", encoding="utf-8") as f:
        json.dump(tribos, f, indent=4, ensure_ascii=False)

# Função para limpar nomes (para criar nomes de ficheiros seguros)
def limpar_nome(nome):
    nome_limpo = re.sub(r'[^A-Za-z0-9áéíóúãõàèùçÁÉÍÓÚÀÈÙÇ_\-@ ]', '_', nome)
    return nome_limpo

@app.route("/", methods=["GET", "POST"])
def index():
    tribos = carregar_tribos()

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
    return render_template("index.html", hoje=hoje, tribos=tribos)

@app.route("/atividades")
def atividades():
    ficheiros = [f for f in os.listdir(DIRETORIO_PRESENCAS) if f.endswith(".csv")]
    atividades_agrupadas = defaultdict(list)

    for ficheiro in ficheiros:
        data_inicio = ficheiro.split('_')[1]
        mes_ano = data_inicio[:7]
        atividades_agrupadas[mes_ano].append(ficheiro)

    meses_ordenados = sorted(atividades_agrupadas.keys(), reverse=True)
    for mes in meses_ordenados:
        atividades_agrupadas[mes].sort(reverse=True)

    return render_template("atividades.html", atividades_agrupadas=atividades_agrupadas, meses_ordenados=meses_ordenados)

@app.route('/eliminar_atividade/<nome_ficheiro>', methods=['POST'])
def eliminar_atividade(nome_ficheiro):
    try:
        caminho_ficheiro = os.path.join(DIRETORIO_PRESENCAS, nome_ficheiro)
        if os.path.exists(caminho_ficheiro):
            os.remove(caminho_ficheiro)
    except:
        pass
    return redirect(url_for('atividades'))

@app.route("/gestao_tribos", methods=["GET", "POST"])
def gestao_tribos():
    tribos = carregar_tribos()

    if request.method == "POST":
        acao = request.form.get("acao")

        if acao == "criar_tribo":
            nome_tribo = request.form.get("nome_tribo").strip()
            if nome_tribo and nome_tribo not in tribos:
                tribos[nome_tribo] = []
                guardar_tribos(tribos)

        elif acao == "remover_tribo":
            nome_tribo = request.form.get("nome_tribo")
            if nome_tribo in tribos:
                del tribos[nome_tribo]
                guardar_tribos(tribos)

        elif acao == "adicionar_pessoa":
            tribo = request.form.get("tribo")
            nome_pessoa = request.form.get("nome_pessoa").strip()
            if tribo in tribos and nome_pessoa:
                tribos[tribo].append(nome_pessoa)
                guardar_tribos(tribos)

        elif acao == "remover_pessoa":
            tribo = request.form.get("tribo")
            nome_pessoa = request.form.get("nome_pessoa")
            if tribo in tribos and nome_pessoa in tribos[tribo]:
                tribos[tribo].remove(nome_pessoa)
                guardar_tribos(tribos)

        return redirect(url_for("gestao_tribos"))

    return render_template("gestao_tribos.html", tribos=tribos)

@app.route("/reordenar_pessoas", methods=["POST"])
def reordenar_pessoas():
    data = request.get_json()
    tribo = data.get("tribo")
    nova_ordem = data.get("nova_ordem")

    tribos = carregar_tribos()
    if tribo in tribos and isinstance(nova_ordem, list):
        tribos[tribo] = nova_ordem
        guardar_tribos(tribos)
        return jsonify({"status": "ok"})
    return jsonify({"status": "erro"}), 400

@app.route("/atividade/<ficheiro>")
def ver_atividade(ficheiro):
    tribos = carregar_tribos()
    caminho = os.path.join(DIRETORIO_PRESENCAS, ficheiro)
    dados = {tribo: [] for tribo in tribos}

    partes_ficheiro = ficheiro.split('_')
    data_inicio_dia = partes_ficheiro[1][8:10]
    data_inicio_mes = partes_ficheiro[1][5:7]
    data_inicio_ano = partes_ficheiro[1][:4]
    data_fim_dia = partes_ficheiro[3][8:10]
    data_fim_mes = partes_ficheiro[3][5:7]
    data_fim_ano = partes_ficheiro[3][:4]
    data_inicio = f"{data_inicio_dia}/{data_inicio_mes}/{data_inicio_ano}"
    data_fim = f"{data_fim_dia}/{data_fim_mes}/{data_fim_ano}"

    data_display = data_inicio if data_inicio == data_fim else f"{data_inicio} - {data_fim}"

    if os.path.exists(caminho):
        with open(caminho, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            cabecalho = next(reader)
            for linha in reader:
                if len(linha) == 5:
                    _, _, _, nome, presente = linha
                    for tribo, membros in tribos.items():
                        if nome in membros:
                            dados[tribo].append((nome, presente))
                            break

    return render_template("ver_atividade.html", ficheiro=ficheiro, cabecalho=cabecalho, dados=dados, data_display=data_display)

if __name__ == "__main__":
    app.run(debug=True)
