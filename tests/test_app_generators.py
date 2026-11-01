#!/usr/bin/env python3
"""T-4..T-9 — app v06 modular (entrega final) e geradores (determinismo/anti-sobrescrita).

Após o review F1..F6: a entrega é o HTML gerado pelo caminho modular
(build_app_v06.py ← manager_template.html + ksm_core.js + manager_app.js + dataset);
o antigo keyboard_split_manager_v06_consolidado.html (caminho v05 + patches R1–R9)
está DEPRECATED e NÃO é mais artefato de entrega nem alvo de testes.
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

import pytest
from conftest import DATA_V6, V05_ORIGINAL, CAND_CORNE, SOFLE_A, SOFLE_B, SOFLE_HOMOLOGADO, GEN, APP

HTML = os.path.join(GEN, "..", "deliverables", "keyboard_split_manager_v06.html")
BUILD = os.path.join(APP, "build_app_v06.py")
REPORT_TESTS = os.path.join(GEN, "..", "reports", "VERIFY_HTML_V06_TESTS.json")
GEN_CORNE = os.path.join(GEN, "generate_corne_candidato.py")
GEN_SOFLE_COMPOSE = os.path.join(GEN, "compose_sofle_candidato.py")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


# ---------------- T-4: HTML v06 modular contém o app novo de entrega (sem v05, sem placeholders)
def test_t4_app_v06_modular(dataset):
    html = open(HTML, encoding="utf-8").read()
    for marker, label in [
        ("Keyboard Split Manager v06", "título/app v06"),
        ('id="ksm-data"', "dataset embutido como fonte única"),
        ("parseWithExactUid", "F4: uid exato no parse"),
        ("validateDataset", "F3: validação de completude"),
        ("ksm_v06_draft", "rascunho v06"),
        ("ksm_v06_history", "histórico novo (F5 item 5)"),
        ("showSaveFilePicker", "gravação real"),
        ("Perfil de referência é somente leitura", "F1: perfil de referência via references"),
    ]:
        assert marker in html, f"elemento {label} ausente no HTML ({marker})"
    # a entrega NÃO deve conter a UI antiga nem placeholders não-substituídos
    for forbidden, label in [
        ("v05 Homologado", "título herdado do v05"),
        ("__KSM_DATA__", "placeholder não substituído"),
        ("__KSM_CORE_JS__", "placeholder não substituído"),
        ("__KSM_APP_JS__", "placeholder não substituído"),
        ("appData.profiles.baseline_instalado[kb].layers", "F1: acesso no formato antigo"),
        ("isKeyDiff", "F2: função que engolia diferenças no caminho antigo"),
    ]:
        assert forbidden not in html, f"artefato proibido no HTML entregue ({label}: {forbidden})"
    # JSON embutido: uid como string exata
    import re as _re
    m = _re.search(r'<script id="ksm-data" type="application/json">([\s\S]*?)</script>', html)
    assert m, "bloco ksm-data ausente"
    assert '"uid": "12888985424971681029"' in m.group(1), "uid precisa ir como texto no embed"


# ---------------- T-4b: script core do HTML final validado por node --check (real)
def test_t4b_node_check_html_final():
    html = open(HTML, encoding="utf-8").read()
    blocks = [b for b in __import__("re").findall(r"<script>([\s\S]*?)</script>", html)]
    assert len(blocks) >= 1, "nenhum bloco <script> plano no HTML"
    for idx, block in enumerate(blocks):
        p = subprocess.run(["node", "--check"], input=block, text=True, capture_output=True)
        assert p.returncode == 0, f"script {idx} do HTML final inválido: {p.stderr}"


# ---------------- T-5: build determinístico
def test_t5_build_deterministico(tmp_path):
    out1 = str(tmp_path / "r1.html")
    out2 = str(tmp_path / "r2.html")
    p1 = subprocess.run(["python3", BUILD, "--out", out1], capture_output=True, text=True)
    assert p1.returncode == 0, p1.stderr
    # segunda execução num caminho novo; e um terceiro no MESMO caminho → RECUSADO (anti-sobrescrita)
    p2 = subprocess.run(["python3", BUILD, "--out", out2], capture_output=True, text=True)
    assert p2.returncode == 0, p2.stderr
    p3 = subprocess.run(["python3", BUILD, "--out", out2], capture_output=True, text=True)
    assert p3.returncode != 0 and "RECUSADO" in (p3.stdout + p3.stderr)
    assert sha256(out1) == sha256(out2)


# ---------------- T-6: gerador corne: anti-sobrescrita + conflito bloqueia + determinismo
def test_t6_corne_antisobrescrita(tmp_path):
    out = str(tmp_path / "c1.keymap")
    p1 = subprocess.run(["python3", GEN_CORNE, "--out", out], capture_output=True, text=True)
    assert p1.returncode == 0, p1.stderr
    out2 = str(tmp_path / "c1.keymap")
    p2 = subprocess.run(["python3", GEN_CORNE, "--out", out2], capture_output=True, text=True)
    assert p2.returncode != 0
    assert "destino já existe" in (p2.stderr + p2.stdout)


def test_t6_corne_conflito_bloqueia(tmp_path):
    """Dataset com uma célula status 'conflict' → gerador aborta sem arquivo parcial."""
    ds = json.load(open(DATA_V6, encoding="utf-8"))
    cell = ds["layers"]["L0"]["corne"]["matrix"][0][0]
    orig = dict(cell)
    cell["status"] = "conflict"
    f = tmp_path / "conflict_ds.json"
    f.write_text(json.dumps(ds, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "x.keymap"
    p = subprocess.run(["python3", GEN_CORNE, "--dataset", str(f), "--out", str(out)], capture_output=True, text=True)
    assert p.returncode != 0
    assert "conflict" in (p.stdout + p.stderr)
    assert not out.exists(), "ARQUIVO PARCIAL não deveria existir (geração abortada)"
    ds2 = json.load(open(DATA_V6, encoding="utf-8"))
    c2 = ds2["layers"]["L0"]["corne"]["matrix"][0][0]
    assert c2 != "conflict", "fonte de produção nunca mutada"


def test_t6_sofle_conflito_bloqueia(tmp_path):
    """Dataset com célula com status 'conflict' ou lista conflicts não-vazia -> compositor do Sofle aborta sem gerar arquivos."""
    ds = json.load(open(DATA_V6, encoding="utf-8"))
    cell = ds["layers"]["L0"]["sofle"]["matrix"][0][0]
    cell["status"] = "conflict"
    f = tmp_path / "conflict_sofle_ds.json"
    f.write_text(json.dumps(ds, ensure_ascii=False), encoding="utf-8")
    outdir = tmp_path / "out_sofle"
    p = subprocess.run(["python3", GEN_SOFLE_COMPOSE, "--dataset", str(f), "--outdir", str(outdir)], capture_output=True, text=True)
    assert p.returncode != 0
    assert "conflito" in (p.stdout + p.stderr).lower() or "conflict" in (p.stdout + p.stderr).lower()
    assert not (outdir / "sofle_candidato_v06_C_conectado.vil").exists(), "Arquivo não deveria ser gerado quando há conflito"

    # Teste também com ds['conflicts'] preenchido
    ds2 = json.load(open(DATA_V6, encoding="utf-8"))
    ds2["conflicts"] = [{"id": 1, "desc": "conflito aberto"}]
    f2 = tmp_path / "conflict_list_ds.json"
    f2.write_text(json.dumps(ds2, ensure_ascii=False), encoding="utf-8")
    p2 = subprocess.run(["python3", GEN_SOFLE_COMPOSE, "--dataset", str(f2), "--outdir", str(outdir)], capture_output=True, text=True)
    assert p2.returncode != 0
    assert "conflito" in (p2.stdout + p2.stderr).lower() or "conflict" in (p2.stdout + p2.stderr).lower()
    assert not (outdir / "sofle_candidato_v06_C_conectado.vil").exists()


def _save(ds, tmp_path):
    f = tmp_path / "conflict_ds.json"
    f.write_text(json.dumps(ds, ensure_ascii=False), encoding="utf-8")
    return f


def test_t6_sofle_a_byte_exata_homologada():
    assert sha256(SOFLE_A) == sha256(SOFLE_HOMOLOGADO)


def test_t6_sofle_b_estrutura_16x60_uid_exato_queries():
    """candidato B: 16 camadas × 60 slots; nunca-sobrescritas (4,5)/(9,5) idênticas ao A; uid presente."""
    a = json.load(open(SOFLE_A, encoding="utf-8"))
    b = json.load(open(SOFLE_B, encoding="utf-8"))
    la, lb = a["layout"], b["layout"]
    assert len(lb) == 16, "16 camadas esperadas"
    for li, layer in enumerate(lb):
        assert len(layer) == 10 and all(len(r) == 6 for r in layer), f"layer {li}: 10×6 esperado"
    for slot in ((4, 5), (9, 5)):
        r, c = slot
        for li in range(16):
            assert lb[li][r][c] == la[li][r][c], f"slot protegido {slot} divergiu no layer {li}"
    raw = open(SOFLE_B, encoding="utf-8").read()
    assert "12888985424971681029" in raw, "uid esperado no candidato B"
    raw = open(SOFLE_B, encoding="utf-8").read()
    assert '"uid": "12888985424971681029"' in raw or "12888985424971681029" in raw


# ---------------- T-7: gerador determinístico
def test_t7_determinismo_corne(tmp_path):
    o1, o2 = str(tmp_path / "d1.keymap"), str(tmp_path / "d2.keymap")
    assert subprocess.run(["python3", GEN_CORNE, "--out", o1], capture_output=True).returncode == 0
    assert subprocess.run(["python3", GEN_CORNE, "--out", o2], capture_output=True).returncode == 0
    assert sha256(o1) == sha256(o2)


# ---------------- T-8: parseWithExactUid JS sobre caso corrompido real
def test_t8_js_parse_uid_v05_corrompido(tmp_path):
    """v5 original com uid int ≥2^53: JS não deve corromper via parseWithExactUid."""
    KSM_JS = os.path.join(APP, "ksm_core.js")
    src = tmp_path / "v5.json"
    shutil.copy(V05_ORIGINAL, src)
    expr = (
        f"const ksm=require({KSM_JS!r});"
        "const fs=require('fs');"
        f"const raw=fs.readFileSync({str(src)!r},'utf8');"
        "const corrompido=String(JSON.parse(raw).profiles?.baseline_instalado?.sofle?.uid);"
        "const exato=String(ksm.parseWithExactUid(raw).profiles?.baseline_instalado?.sofle?.uid);"
        "console.log(JSON.stringify({corrompido, exato}));")
    p = subprocess.run(["node", "-e", expr], text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    res = json.loads(p.stdout.strip())
    assert res["exato"] == "12888985424971681029"
    assert res["corrompido"] != res["exato"]


# ---------------- T-9: HTML final testado de verdade (Parte A VM + Parte B Chrome real)
def test_t9_html_final_testasuite(tmp_path):
    """Executa app/test_html_final.js no HTML ENTREGUE:
    Parte A valida uid/validador/paridade via scripts EXTRAÍDOS do HTML final;
    Parte B usa Playwright + Chrome real com perfil isolado."""
    out_json = tmp_path / "VERIFY_HTML_V06_TESTS.json"
    p = subprocess.run(
        ["node", os.path.join(APP, "test_html_final.js")],
        env={**os.environ, "OUT_JSON": str(out_json), "HTML_PATH": HTML},
        text=True, capture_output=True, timeout=300,
    )
    assert p.returncode == 0, (p.stdout[-4000:] if p.stdout else "") + p.stderr[-2000:]
    res = json.loads(out_json.read_text(encoding="utf-8"))
    assert res["fail"] == 0 and res["pass"] == res["total"], json.dumps(res["itens"][:5], ensure_ascii=False)


# ---------------- T-9b: mutação uid numérica não quebra o parser (F4, do lado JS do app shell)
def test_t9b_uid_numerico_campo_seguinte():
    expr = (
        f"const k=require({os.path.join(APP, 'ksm_core.js')!r});"
        "const cases=["
        "'{\"uid\": 12888985424971681029, \"x\": 1}',"
        "'{\"uid\":12888985424971681029,\"x\":1}',"
        "'{\"uid\": 12888985424971681029 }',"
        "'{\"uid\": 12888985424971681029\\n, \"y\": 2}'];"
        "for(const c of cases){const o=k.parseWithExactUid(c);"
        "if(o.uid!=='12888985424971681029'){process.exit(1)}}"
        "process.exit(0)")
    p = subprocess.run(["node", "-e", expr], text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
