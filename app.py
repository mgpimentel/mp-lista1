import streamlit as st
import io, sys, hashlib, textwrap, builtins

# ========== util ==========
def _h(txt: str) -> str:
    """sha256 do texto (usamos saída 'normalizada' .strip())."""
    return hashlib.sha256(txt.strip().encode("utf-8")).hexdigest()

def _run_user(code: str, input_text: str):
    """
    Executa o código do aluno(a) com entradas simuladas.
    Retorna (status, saida_ou_msg)
      - status 'ok'  -> saida do programa
      - status 'exc' -> mensagem de erro resumida
    """
    # Simula input() lendo das linhas fornecidas
    lines = input_text.splitlines(True)  # mantém \n
    it = iter(lines)
    def fake_input(prompt=""):
        try:
            return next(it).rstrip("\n")
        except StopIteration:
            raise EOFError("faltou entrada para input()")

    old_stdin, old_stdout = sys.stdin, sys.stdout
    old_input = builtins.input
    sys.stdin = io.StringIO(input_text)
    sys.stdout = io.StringIO()
    builtins.input = fake_input
    try:
        exec(code, {})  # sem variáveis externas
        saida = sys.stdout.getvalue()
        return "ok", saida
    except Exception as e:
        # mostra apenas o tipo e a mensagem
        return "exc", f"{type(e).__name__}: {e}"
    finally:
        sys.stdin, sys.stdout = old_stdin, old_stdout
        builtins.input = old_input

# ========== enunciados ==========
ENUNCIADOS = {
    "ex1": """Resultado da soma de dois números inteiros.
Exemplo:
Entrada:
3
4
Saída:
7""",
    "ex2": """Dados dois números inteiros (saldo e valor do item),
imprimir 'pode comprar' se saldo ≥ valor; caso contrário imprimir 'não pode comprar'."""
}

# ========== testes secretos (entradas + hash da saída) ==========
# OBS: Os hashes estão no repo, logo são visíveis para quem abrir o código,
# mas a interface não revela entradas/saídas.
TESTES = {
    "ex1": [
        # (entrada, hash_saida_normalizada)
        ("3\n4\n",  "7902699be42c8a8e46fbbb4501726517e86b22c56a189f7625a6da49081b2451"),  # 7
        ("0\n0\n",  "5feceb66ffc86f38d952786c6d696c79c2dbc239dd4e91b46729d73a27fb57e9"),  # 0
        ("-5\n10\n","ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d"),  # 5
        ("100\n200\n","983bd614bb5afece5ab3b6023f71147cd7b6bc2314f9d27af7422541c6558389"),# 300
        ("1\n-1\n", "5feceb66ffc86f38d952786c6d696c79c2dbc239dd4e91b46729d73a27fb57e9"),  # 0
    ],
    "ex2": [
        ("100\n50\n",  "ceae131cceccd695e1e35f65e1767cebb99c852598b7f5e1e5ff297b9c87c24b"),  # pode comprar
        ("50\n50\n",   "ceae131cceccd695e1e35f65e1767cebb99c852598b7f5e1e5ff297b9c87c24b"),  # pode
        ("49\n50\n",   "f8ef92bcb346dd482dda6cbaf1ff58d08a252d750eadcceaa9c48a2b6772c1cc"),  # não pode
        ("0\n0\n",     "ceae131cceccd695e1e35f65e1767cebb99c852598b7f5e1e5ff297b9c87c24b"),  # pode
        ("0\n10\n",    "f8ef92bcb346dd482dda6cbaf1ff58d08a252d750eadcceaa9c48a2b6772c1cc"),  # não pode
    ],
}

# ========== templates para o editor ==========
TEMPLATE = {
    "ex1": textwrap.dedent("""\
        #EXERCICIO: ex1
        a = int(input())
        b = int(input())
        print(a+b)
    """),
    "ex2": textwrap.dedent("""\
        #EXERCICIO: ex2
        saldo = int(input())
        preco = int(input())
        if saldo >= preco:
            print('pode comprar')
        else:
            print('não pode comprar')
    """),
}

# ========== UI ==========
st.set_page_config(page_title="Lista MP – Avaliação Automática (MVP)", page_icon="🧪", layout="centered")
st.title("Lista com Correção Automática — MVP (Streamlit)")

ex = st.selectbox("Escolha o exercício", options=["ex1","ex2"], format_func=lambda k: k.upper())
st.markdown(f"**Enunciado ({ex.upper()}):**")
st.code(ENUNCIADOS[ex])

code = st.text_area("Cole/edite seu código aqui (apenas input()/print())",
                    value=TEMPLATE[ex], height=220)

if st.button("Rodar avaliação"):
    testes = TESTES[ex]
    ok = 0
    for i, (entrada, saida_hash) in enumerate(testes, start=1):
        status, val = _run_user(code, entrada)
        if status == "exc":
            st.error(f"Teste {i}: **ERRO de execução** — {val}")
            continue
        saida = val
        if _h(saida) == saida_hash:
            ok += 1
            st.success(f"Teste {i}: OK")
        else:
            st.warning(f"Teste {i}: ERRO")  # sem revelar I/O
    st.info(f"**Resumo {ex.upper()}: {ok}/{len(testes)} OK**")

st.caption("Entradas e saídas dos testes permanecem ocultas. O feedback mostra apenas OK/ERRO e erros de execução.")
