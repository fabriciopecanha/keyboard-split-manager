#!/usr/bin/env python3
"""T-1..T-3 — núcleo: UID exato, hash canônico Python≡JS, migração v5→v6 idempotente."""
import json
import os
import subprocess

import ksm_core
from conftest import DATA_V6, V05_ORIGINAL

KSM_JS = os.path.join(os.path.dirname(DATA_V6), "ksm-work-PLACEHOLDER")


def _ksm_js_path():
    base = os.path.dirname(os.path.abspath(__file__))  # ksm-work/tests
    return os.path.join(os.path.dirname(base), "app", "ksm_core.js")


KSM_JS = _ksm_js_path()


def test_t1_uid_2pow53_corrompe_em_js_e_string_salva():
    """UID Sofle ≥2^53: JS puro corrompe; parseWithExactUid preserva dígitos exatos."""
    uid = "12888985424971681029"
    p = subprocess.run(
        ["node", "-e",
         f"const ksm=require({KSM_JS!r});"
         f"const corrompido=String(JSON.parse(JSON.stringify({{uid: {uid}}})).uid);"
         f"const exato=String(ksm.parseWithExactUid('{{\"uid\": {uid}}}').uid);"
         f"console.log(corrompido!==\"{uid}\"&&exato===\"{uid}\");"],
        text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == "true"


def test_t1_migracao_v5_tem_uid_string():
    """v5 original: uid ≥2^53 como int. v6 migrado: STRING decimal exata."""
    m5 = json.load(open(V05_ORIGINAL, encoding="utf-8"))

    def find_int_uid(o):
        if isinstance(o, dict):
            if isinstance(o.get("uid"), int):
                return o["uid"]
            for v in o.values():
                r = find_int_uid(v)
                if r is not None:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = find_int_uid(v)
                if r is not None:
                    return r
        return None

    uid_int = find_int_uid(m5)
    assert uid_int is not None, "v5 deveria conter uid numérico"
    assert uid_int >= 2**53

    d6 = json.load(open(DATA_V6, encoding="utf-8"))

    def find_str_uid(o):
        if isinstance(o, dict):
            v = o.get("uid")
            if isinstance(v, str) and v.isdigit():
                return v
            for c in o.values():
                r = find_str_uid(c)
                if r is not None:
                    return r
        elif isinstance(o, list):
            for c in o:
                r = find_str_uid(c)
                if r is not None:
                    return r
        return None

    uid_str = find_str_uid(d6)
    assert uid_str is not None
    assert uid_str == str(uid_int)


def test_t2_hash_canonico_python_js_identicos(dataset):
    """canonical_hash: mesmo hex em Python e JS (canonicalHashAsync via crypto)."""
    py_hex = ksm_core.canonical_hash(dataset)
    p = subprocess.run(
        ["node", "--input-type=module", "-e",
         f"import * as ksm from 'file://{KSM_JS}';\n"
         "const d = JSON.parse(await new Promise(r=>{let s='';process.stdin.on('data',c=>s+=c).on('end',()=>r(s))}));\n"
         "console.log(await ksm.canonicalHashAsync(d));"],
        input=json.dumps(dataset), text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == py_hex


def test_t3_migracao_v5_v6_idempotente():
    """migração v5→v6 executada 2x sobre a MESMA fonte v5 → hash canônico idêntico."""
    v5 = json.load(open(V05_ORIGINAL, encoding="utf-8"))
    m1, _, _ = ksm_core.migrate_v5_to_v6(v5, "t3-1")
    m2, _, _ = ksm_core.migrate_v5_to_v6(v5, "t3-2")
    assert ksm_core.canonical_hash(m1) == ksm_core.canonical_hash(m2)
    # dataset v6 em produção ≠ migracão pré-D2: D2 aplicado post-migração e registrado em metadata.changes
    with open(DATA_V6, encoding="utf-8") as f:
        d6 = json.load(f)
    decisions = d6.get("metadata", {}).get("decisions", [])
    assert any("D2" in json.dumps(c, ensure_ascii=False) for c in decisions), \
        "D2 deveria estar registrado em metadata.decisions"


def test_t3_hash_exclui_volatile(dataset):
    a = ksm_core.canonical_hash(dataset)
    b = ksm_core.canonical_hash({**dataset, "updated_at": "2000-01-01T00:00:00Z"})
    assert a == b, "campos voláteis devem ser excluídos do hash canônico"
