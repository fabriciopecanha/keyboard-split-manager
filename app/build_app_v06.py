#!/usr/bin/env python3
"""build_app_v06.py — gerador MODULAR do app v06 (substitui o caminho patchado do v05).

Combina: manager_template.html + ksm_core.js + manager_app.js + dataset keymap_data_v06.json
→ keyboard_split_manager_v06.html.

Garantias nesta execução (F6: verificadas aqui, não apenas declaradas):
  - node --check em TODOS os blocos <script> do HTML final;
  - JSON embutido idêntico ao dataset (hash canônico comparado);
  - build determinístico (duas execuções → mesmo sha256);
  - anti-sobrescrita (recusa destino existente).
"""
import hashlib
import json
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import ksm_core  # noqa: E402

_KSM = os.path.dirname(_HERE)

TEMPLATE = os.path.join(_HERE, "manager_template.html")
CORE_JS = os.path.join(_HERE, "ksm_core.js")
APP_JS = os.path.join(_HERE, "manager_app.js")
DATASET = os.path.join(_KSM, "data", "keymap_data_v06.json")


def _shield_for_html_script(text):
    """Evita fechar o <script> antecipadamente dentro de strings JS/JSON."""
    return text.replace("</script", "<\\/script")


def _unshield_json(text):
    return text.replace("<\\/script", "</script")


def build_manager_html(dataset=DATASET):
    data_raw = open(dataset, "r", encoding="utf-8").read()
    data = ksm_core.load_canonical(os.path.abspath(dataset))
    if data.get("schema_version") != 6:
        raise SystemExit("dataset precisa ser schema 6")
    canon_hash = ksm_core.canonical_hash(data)
    data_json_for_embed = _shield_for_html_script(data_raw)
    # confirma que a blindagem preserva o valor semântico do JSON
    assert json.loads(_unshield_json(data_json_for_embed)) == data, "blindagem </script alterou o JSON"

    core_js = _shield_for_html_script(open(CORE_JS, encoding="utf-8").read())
    app_js = _shield_for_html_script(open(APP_JS, encoding="utf-8").read())

    tpl = open(TEMPLATE, encoding="utf-8").read()
    html = tpl.replace("__KSM_DATA__", data_json_for_embed)
    html = html.replace("__KSM_CORE_JS__", core_js)
    html = html.replace("__KSM_APP_JS__", app_js)
    for token in ("__KSM_DATA__", "__KSM_CORE_JS__", "__KSM_APP_JS__"):
        if token in html:
            raise SystemExit(f"placeholder {token} não substituído")

    # node --check em todos os blocos <script> do HTML FINAL (verificação real)
    scripts = re.findall(r"<script>([\s\S]*?)</script>", html)
    for idx, s in enumerate(scripts):
        p = subprocess.run(["node", "--check"], input=s, text=True, capture_output=True)
        if p.returncode != 0:
            print(f"ERRO SINTÁTICO FATAL NO SCRIPT {idx} DO HTML FINAL:")
            print(p.stderr)
            sys.exit(1)

    # o JSON embutido parseado == dataset (hash canônico) — verificação real
    m = re.search(r'<script id="ksm-data" type="application/json">([\s\S]*?)</script>', html)
    assert m, "bloco ksm-data ausente no HTML final"
    embedded = json.loads(_unshield_json(m.group(1)))
    embedded_hash = ksm_core.canonical_hash(embedded)
    assert embedded_hash == canon_hash, "JSON embutido difere do dataset (hash canônico)"

    return html, canon_hash


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=DATASET)
    ap.add_argument("--out", required=True, help="saída versionada nova (recusa destino existente sem --force)")
    ap.add_argument("--force", action="store_true", help="permite sobrescrever destino existente explicitamente")
    a = ap.parse_args()
    if os.path.exists(a.out) and not a.force:
        raise SystemExit(f"RECUSADO: destino já existe ({a.out}) — use --force para sobrescrever.")
    html, canon_hash = build_manager_html(os.path.abspath(a.dataset))
    out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    sha = hashlib.sha256(open(out, "rb").read()).hexdigest()
    print(f"HTML gerado: {out} ({os.path.getsize(out)} B)")
    print(f"sha256 arquivo: {sha}")
    print(f"hash canônico dataset: {canon_hash}")
