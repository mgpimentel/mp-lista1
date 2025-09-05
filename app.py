import streamlit as st
import io, sys, hashlib, builtins, requests, re
import pandas as _pd

# =========================
# Execução isolada com timeout (1 processo por caso)
# =========================
TIME_LIMIT_SEC = float(st.secrets.get("TIME_LIMIT_SEC", 4.0))
OUTPUT_LIMIT   = int(st.secrets.get("OUTPUT_LIMIT", 10000))

try:
    import multiprocessing as _mp
    _mp.set_start_method("spawn", force=True)
except Exception:
    pass

def _worker_exec(code: str, input_text: str, queue):
    import io, sys, builtins
    lines = (input_text or "").splitlines(True)
    it = iter(lines)
    def fake_input(prompt=""):
        try:
            return next(it).rstrip("\n")
        except StopIteration:
            raise EOFError("faltou entrada para input()")
    old_stdin, old_stdout = sys.stdin, sys.stdout
    old_input = builtins.input
    sys.stdin = io.StringIO(input_text or "")
    sys.stdout = io.StringIO()
    builtins.input = fake_input
    try:
        exec(code or "", {})
        out = sys.stdout.getvalue()
        queue.put(("ok", out))
    except Exception as e:
        queue.put(("exc", f"{type(e).__name__}: {e}"))
    finally:
        sys.stdin, sys.stdout = old_stdin, old_stdout
        builtins.input = old_input

def run_user_code(code: str, input_text: str, time_limit: float = TIME_LIMIT_SEC, output_limit: int = OUTPUT_LIMIT):
    import multiprocessing as mp, time
    q = mp.Queue()
    p = mp.Process(target=_worker_exec, args=(code, input_text, q))
    p.start()

    deadline = time.time() + time_limit
    status_out = None
    while time.time() < deadline:
        if not p.is_alive():
            break
        try:
            status_out = q.get_nowait()
            break
        except Exception:
            pass
        time.sleep(0.02)

    if status_out is None:
        if not p.is_alive():
            try:
                status_out = q.get(timeout=0.05)
            except Exception:
                status_out = ("exc", "Sem saída (erro desconhecido)")
        else:
            p.terminate(); p.join(0.1)
            return "timeout", "Tempo esgotado (possível loop infinito)"

    status, out = status_out
    if isinstance(out, str) and len(out) > output_limit:
        out = out[:output_limit] + "\n... (truncado)"
    return status, out

# =========================
# Configurações do app
# =========================
st.set_page_config(page_title="Lista 1 — Meninas Programadoras", layout="centered")

# Onde estão os arquivos JSON (repo de testes)
GITHUB_RAW_BASE = st.secrets.get("GITHUB_RAW_BASE", "https://raw.githubusercontent.com/mgpimentel/xyzist3st3s/main/r")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", None)

# =========================
# Helpers
# =========================
def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _normalize(s: str, mode: str = "strip") -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    if mode == "strip":
        return s.strip()
    if mode == "rstrip":
        return s.rstrip()
    if mode == "lstrip":
        return s.lstrip()
    return s

@st.cache_data(show_spinner=False, ttl=600)
def fetch_enunciados():
    url = f"{GITHUB_RAW_BASE}/enunciados.json"
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
        headers["Accept"] = "application/vnd.github.raw+json"
    r = requests.get(url, timeout=20, headers=headers or None)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise RuntimeError("Formato inválido de enunciados.json (esperado dict).")
    return data

@st.cache_data(show_spinner=False, ttl=600)
def load_tests_from_github(tag: str):
    m = re.search(r'(\d+)', str(tag))
    n = m.group(1) if m else str(tag)
    url = f"{GITHUB_RAW_BASE}/ex{n}.json"
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
        headers["Accept"] = "application/vnd.github.raw+json"
    r = requests.get(url, timeout=20, headers=headers or None)
    r.raise_for_status()
    data = r.json()
    cases = data.get("cases", data if isinstance(data, list) else [])
    return {"cases": cases, "hash_alg": data.get("hash_alg", "sha256"), "normalizacao": data.get("normalizacao", "strip")}

# =========================
# Estado da UI
# =========================
if "codes" not in st.session_state:
    st.session_state["codes"] = {f"ex{i}": "" for i in range(1, 11)}
if "results" not in st.session_state:
    st.session_state["results"] = {}

def render_dashboard(target_placeholder):
    rows = []
    for i in range(1, 11):
        k = f"ex{i}"
        res = st.session_state["results"].get(k)
        ok, tot = (res if res else (0, 0))
        status = "— não avaliado —" if tot==0 else ("✅ completo" if ok==tot else ("🔴 0 acertos" if ok==0 else "🟡 parcial"))
        rows.append({"Exercício": k.upper(), "Acertos": f"{ok}/{tot}" if tot else "", "%": round((ok/tot)*100,1) if tot else "", "Status": status})
    df = _pd.DataFrame(rows)[["Exercício","Acertos","%","Status"]]
    with target_placeholder.container():
        st.subheader("📊 Seu progresso na Lista 1")
        st.dataframe(df, hide_index=True, use_container_width=True)
        valid = [r for r in rows if r["%"] != ""]
        avg = sum(r["%"] for r in valid)/len(valid) if valid else 0.0
        st.progress(min(1.0, avg/100))
        st.caption(f"Progresso médio: {avg:.1f}% nos exercícios avaliados")

dash = st.empty()
render_dashboard(dash)

# =========================
# UI principal
# =========================
st.title("Lista 1 — Pré-correção Automática (MPM.PPM.T2)")
st.markdown("Selecione o exercício, escreva seu código e rode os testes.")

ex_list = [f"ex{i}" for i in range(1, 11)]
ex = st.selectbox("Exercício", ex_list, format_func=lambda k: k.upper())

# Enunciado 100% remoto
try:
    enuns = fetch_enunciados()
    st.markdown(enuns.get(ex, "_(enunciado não encontrado no enunciados.json)_"))
except Exception as e:
    st.error(f"Falha ao carregar enunciados.json: {e}")
    st.stop()

# Editor
try:
    from streamlit_ace import st_ace
    ACE = True
except Exception:
    ACE = False

if ACE:
    code = st_ace(value=st.session_state['codes'].get(ex,''), language="python", theme="chrome",
                  keybinding="vscode", font_size=14, tab_size=4, wrap=True, show_gutter=True,
                  show_print_margin=False, auto_update=True, placeholder="# Escreva seu código aqui (use input() e print())",
                  height=340, key=f"ace_{ex}")
    st.session_state["codes"][ex] = code or ""
else:
    code = st.text_area("Seu código (use input() e print())", value=st.session_state['codes'].get(ex,''),
                        height=260, key=f"code_{ex}", placeholder="# Escreva seu código aqui (use input() e print())")
    st.session_state["codes"][ex] = st.session_state[f"code_{ex}"]

col1, col2 = st.columns([1,1])
with col1: rodar = st.button("Rodar avaliação", type="primary")
with col2: reset = st.button("Limpar saída")

if reset:
    st.session_state["results"].pop(ex, None)
    render_dashboard(dash)

if rodar:
    with st.spinner("Carregando casos e executando testes..."):
        try:
            bundle = load_tests_from_github(ex)
            casos = bundle["cases"]
            ok = 0; total = len(casos)
            code_to_run = st.session_state["codes"][ex]
            for i, caso in enumerate(casos, start=1):
                entrada = caso.get("entrada","")
                saida_hash = caso.get("saida_hash","")
                normalizacao = caso.get("normalizacao", bundle.get("normalizacao","strip"))
                status, out = run_user_code(code_to_run, entrada)
                if status == "exc":
                    st.error(f"Teste {i}: ERRO — {out}")
                elif status == "timeout":
                    st.error(f"Teste {i}: ERRO — {out}")
                else:
                    out_norm = _normalize(out, normalizacao)
                    h = _sha256(out_norm)
                    if h == saida_hash:
                        ok += 1; st.success(f"Teste {i}: OK")
                    else:
                        st.warning(f"Teste {i}: ERRO")
            st.info(f"*Resumo {ex.upper()}: {ok}/{total} OK*")
            st.session_state["results"][ex] = (ok, total)
            render_dashboard(dash)
        except Exception as e:
            st.error(f"Falha ao carregar/rodar testes: {e}")
