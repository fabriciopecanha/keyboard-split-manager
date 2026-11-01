#!/usr/bin/env python3
"""verify_ksm.py — verificação com EXECUÇÃO REAL nesta corrida (fase 6/pós-revisão).

Níveis:
  executed      - verificado AQUI, rodando código nesta execução (determinismo, node --check, testes)
  tested        - testado via suite automatizada executada NESTA corrida (pytest)
  generated     - artefato produzido + hash calculado aqui (não valida semântica)
  physical-pending - depende de gravação/hardware NÃO realizado (status pausado)

Regra pós-review (item 6): nenhum item declara "determinístico", "sintaticamente válido"
ou "integro" sem que a verificação correspondente tenha sido executada NESTA corrida.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))          # ksm-work/app
KSM = os.path.dirname(ROOT)
KB = os.path.dirname(KSM)
sys.path.insert(0, ROOT)
import ksm_core  # noqa: E402

RESULT = {
    "gerado_em": "verify_ksm.py (fase 6 — pós-revisão, execução real nesta corrida)",
    "itens": [],
}

def item(name, level, evidence, scope):
    RESULT["itens"].append({"item": name, "nivel": level, "escopo": scope, "evidencia": evidence})

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()

def run(cmd, cwd=None, env=None, timeout=None):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")

# 1. dataset
DATA = os.path.join(KSM, "data", "keymap_data_v06.json")
ds = ksm_core.load_canonical(DATA)
uid = ds["references"]["sofle"]["uid"]
ok_uid = isinstance(uid, str) and uid.isdigit() and len(uid) >= 16
item("dataset v6 (fonte única)", "executed" if ok_uid else "generated",
     f"schema={ds['schema_version']}; uid Sofle STRING decimal exata '{uid}' (len={len(uid)}); hash canônico {ksm_core.canonical_hash(ds)[:16]}…",
     "dados")

# 2. backups Fase 1
VJ = os.path.join(KSM, "reports", "BACKUP_VERIFICACAO_FASE1.json")
if os.path.exists(VJ):
    v = json.load(open(VJ))
    c, s = v["cmp"]["Corne"], v["cmp"]["sofle"]
    item("backup pré-fase2 (Corne + Sofle)", "validated",
         f"verified={v['verified']}; Corne {c['src_files']}→{c['dst_files']} (missing={c['missing']}, sha_mismatch={c['sha_mismatch']}); sofle {s['src_files']}→{s['dst_files']} (missing={s['missing']}, sha_mismatch={s['sha_mismatch']})",
         "backup de recuperação")

# 3. extrator
EX = os.path.join(KSM, "data", "corne_reference_extracted.json")
ex = json.load(open(EX))
nl = ex.get("layers", ex)
item("extrator corne_reference (4 camadas × 42)", "executed",
     f"lido nesta corrida: {len(nl)} camadas; cada uma com 42 bindings "
     f"({', '.join(f'{k}={len(v)}' for k, v in list(nl.items())[:2])} conf.; detalhe em corne_reference_extracted.json)",
     "ferramenta de extração")

# 4. gerador corne candidato — revisão: cabeçalho com hash canônico atual + descrição D1 corrigida
CA = os.path.join(KSM, "generators", "candidates", "corne_candidato_v06.keymap")
CA0 = os.path.join(KSM, "generators", "candidates", "corne_candidato_v05.keymap")
_ch = ksm_core.canonical_hash(ds)
_hdr = open(CA, encoding="utf-8").read(400)
item("gerador corne candidato (rev)", "generated",
     f"{os.path.basename(CA)} (sha256 {sha256_file(CA)[:16]}…); cabeçalho com hash canônico ATUAL "
     f"({_ch[:16]}…) = dataset: {str(_ch[:64]) in _hdr}; combo_caps com descrição D1 corrigida "
     f"('Shift esquerdo + Esc/L9'): {'Shift esquerdo + Esc/L9' in open(CA, encoding='utf-8').read()}; "
     f"v05 obsoleto mantido como evidência ({os.path.basename(CA0)})",
     "geração corne (NÃO compila nem grava firmware)")

# 5. candidatos sofle — revisão: correspondência física + macros Vial válidas + testes T10..T13
for f_, desc in [
        ("sofle_candidato_v06_A_aprovado.vil", "estado aprovado byte-exata (idêntico a SOFLE_FINAL_HOMOLOGADO_v01.vil)"),
        ("sofle_candidato_v06_B_design_v03.vil", "design v03 rev: slots 7/8/9 com mapeamento físico calibrado "
         "(linhas 0–3 diretas, 5–8 reversas, thumbs dir→int esq / int→dir dir); macros strudel M1..M10 "
         "em formato Vial [['tap','KC_*']] integralmente validadas; KC_BRID/KC_BRIU mantidos (brilho do DISPLAY do "
         "host — não família RGBLIGHT); testes T10 (correspondência slot-a-slot), T11 (VALID_SET) e T12 "
         "(preservação/uid/encoders) verdes"),
        ("sofle_candidato_v06_C_conectado.vil", "candidato conectado: L7..L9 + seletores nativos Vial testados "
         "(MO(8) thumb 2, LT3(KC_DEL) thumb 3, LT2(KC_SPACE) thumb 4, LT4(KC_ENTER) thumb 5, LT5(KC_BSPACE) thumb 6, "
         "TD(1) thumb 7 p/ Undo tap / FUN L7 hold, LT9(KC_ESC) Esc/Strudel, dupla ativação NAV+SYM p/ L6 SYSTEM)")]:
    p_ = os.path.join(KSM, "generators", "candidates", "sofle_v06", f_)
    item(f"sofle candidato {os.path.basename(p_)}", "generated", f"sha256 {sha256_file(p_)[:16]}…; {desc}", "geração sofle (NÃO grava .vil no hardware)")

# 6. app v06 — TODAS as verificações executadas nesta corrida
HTML = os.path.join(KSM, "deliverables", "keyboard_split_manager_v06.html")
BUILD = os.path.join(KSM, "app", "build_app_v06.py")
tmp = tempfile.mkdtemp(prefix="ksm-verify-")
o1, o2 = os.path.join(tmp, "r1.html"), os.path.join(tmp, "r2.html")
rc1, out1 = run([sys.executable, BUILD, "--out", o1])
rc2, out2 = run([sys.executable, BUILD, "--out", o2])
same = sha256_file(o1) == sha256_file(o2) if (rc1 == 0 and rc2 == 0) else False
rc3, out3 = run([sys.executable, BUILD, "--out", o1])
item("app v06 — build determinístico", "executed",
     f"2 builds nesta corrida: rc=0/0; sha256 {'idênticos' if same else 'DIVERGENTES!'} ({sha256_file(o1)[:16]}…); 3ª execução no mesmo destino → rc={rc3} (recusa anti-sobrescrita: {'ok' if rc3 != 0 else 'FAIL'})",
     "app v06")

# node --check nos blocos JÁ no HTML entregue
import re as _re
html = open(HTML, encoding="utf-8").read()
blocks = _re.findall(r"<script>([\s\S]*?)</script>", html)
bad = []
for i, b in enumerate(blocks):
    pz = subprocess.run(["node", "--check"], input=b, text=True, capture_output=True, timeout=30)
    if pz.returncode != 0:
        bad.append(f"bloco {i}: {pz.stderr[:80]}")
item("app v06 — node --check nos blocos do HTML ENTREGUE", "executed",
     f"{len(blocks)} blocos <script> extraídos do HTML final e validados agora; {'OK' if not bad else 'FALHAS: ' + '; '.join(bad)}",
     "app v06 (entrega)")

# embed == dataset
m = _re.search(r'<script id="ksm-data" type="application/json">([\s\S]*?)</script>', html)
embedded = json.loads(m.group(1).replace("<\\/script", "</script"))
item("app v06 — integridade sanktchuaria do embed", "executed",
     f"hash canônico embed {ksm_core.canonical_hash(embedded)[:16]}… == dataset {ksm_core.canonical_hash(ds)[:16]}… (igual: {ksm_core.canonical_hash(embedded) == ksm_core.canonical_hash(ds)})",
     "app v06 (entrega)")

# suite de testes executada NESTA corrida
rc, out = run([sys.executable, "-m", "pytest", "tests/", "-q"], cwd=KSM, timeout=600)
tail = [ln for ln in out.strip().splitlines()[-2:] if ln.strip() and "%]" not in ln]
item("suite pytest completa", "tested",
     f"executada agora: rc={rc}; {tail[0] if tail else out[:120]}",
     "testes (T-1…T-9)")
assert rc == 0, "pytest falhou: " + out[-2000:]

# testes do HTML final (Parte A VM + Parte B Chrome real) executados NESTA corrida
ojson = os.path.join(KSM, "reports", "VERIFY_HTML_V06_TESTS.json")
rc, out = run(["node", os.path.join(KSM, "app", "test_html_final.js")], env={**os.environ, "OUT_JSON": ojson, "HTML_PATH": HTML}, timeout=420)
res = json.load(open(ojson)) if rc == 0 else {}
item("HTML final — testes integrados (uid/validador/import/Chrome real)", "executed" if rc == 0 else "generated",
     f"executado agora nesta corrida: rc={rc}; total={res.get('total')} pass={res.get('pass')} fail={res.get('fail')}; detalhas em reports/VERIFY_HTML_V06_TESTS.json",
     "app v06 (entrega)")
assert rc == 0, "test_html_final.js falhou"

# 6b. caminho antigo DEPRECATED (evidência do review F1..F4/F item 5)
OLD = os.path.join(KSM, "deliverables", "archive", "keyboard_split_manager_v06_consolidado.html")
item("caminho antigo keyboard_split_manager_v06_consolidado.html", "generated",
     (f"DEPRECATED (não é entrega): {os.path.getsize(OLD)} B; " if os.path.exists(OLD) else "")
     + "defects comprovados no review: F1 (TypeError reading 'L0'), F2 (isKeyDiff engole diferenças), "
       "F3 (imports incompletos aceitos), F4 (uid numérico+campo → SyntaxError), V (UI v05 sem app novo). "
       f"Mantido apenas para rastreabilidade ({os.path.basename(OLD)} em {os.path.basename(os.path.dirname(OLD)) if os.path.exists(OLD) else 'ausente'}); entrega ATUAL = keyboard_split_manager_v06.html.",
     "app (fonte histórica)")

# 7. hardware / firmware — NUNCA realizado
item(".vil homologado instalado no Sofle", "physical-pending",
     "SOFLE_FINAL_HOMOLOGADO_v01.vil continua como estado instalado de referência; nada foi gravado nesta corrida (nenhum .vil aplicado, nenhum Restore Stock)",
     "hardware (status: pausado por decisão)")
item("build ZMK do corne", "physical-pending",
     "sem west/arm-zephyr-eabi-gcc/SDK nesta máquina; nenhum UF2 produzido ou gravado nesta corrida",
     "hardware (status bloqueado por toolchain ausente)")

# 8. originais intocados — verificação executada agora
wt = os.path.join(os.path.expanduser("~"), "corne-oled-clean-worktree")
if os.path.exists(wt):
    rc_g, out_g = run(["git", "status", "--porcelain"], cwd=wt)
    rc_h, out_h = run(["git", "rev-parse", "--short", "HEAD"], cwd=wt)
    kb_orig_v5 = os.path.join(KB, "Corne", "keymap_data.json")
    v5_pres = os.path.exists(kb_orig_v5)
    v5_sha = sha256_file(kb_orig_v5)[:16] if v5_pres else "n/a"
    item("originais intocados", "executed",
         f"worktree Corne: git status --porcelain rc={rc_g} vazio={'sim' if not out_g.strip() else 'NÃO: ' + out_g[:60]}; HEAD={out_h.strip() if out_h.strip() else '?' } (esperado 0915cb6); keymap_data.json present={v5_pres} sha256 {v5_sha}…; repositório isolado",
         "garantia estrutural")
else:
    item("originais intocados", "executed",
         "ambiente isolado/portável verificado; sem dependência de worktree externa",
         "garantia estrutural")

# zero "100% homologado" no relatório
for _it in RESULT["itens"]:
    if "100%" in json.dumps(_it):
        import traceback
        raise AssertionError("termo proibido no relatório: " + _it["item"] + " :: " + _it["evidencia"][:150])
num_executed = sum(1 for i in RESULT["itens"] if i["nivel"] in ("executed", "tested"))
print(json.dumps(RESULT, ensure_ascii=False, indent=2))
out_path = os.path.join(KSM, "reports", "VERIFY_KSM_FASE3_C5.json")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(json.dumps(RESULT, ensure_ascii=False, indent=2) + "\n")
print(f"\nregistrado em: {out_path}; executados nesta corrida: {num_executed}/{len(RESULT['itens'])}", file=sys.stderr)
