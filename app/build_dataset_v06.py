#!/usr/bin/env python3
"""build_dataset_v06 — consolida a Fonte Única do Keyboard Split Manager.

Entrada  : Corne/keymap_data.json (v05, intocado), referência Corne extraída do
           devicetree real e SOFLE_FINAL_HOMOLOGADO_v01.vil (intocado).
Saída    : data/keymap_data_v06.json (novo, atômico, anti-sobrescrita).

Regras:
- UID Sofle em texto decimal exato no modelo (o Vial recebe int só na borda);
- referência Corne com as 4 camadas nativas, sem L0..L9 artificiais;
- referência Sofle com o .vil COMPLETO (16 camadas + encoders + macros + tap
  dances + combos + key overrides + settings), não apenas 580 posições;
- candidato L0..L9 espelhado em profiles.candidato_teste e validado == layers;
- nenhuma referência é rotulada com nome de camada do candidato;
- D1: combo Caps mantém posições 24+35 e recebe descrição correta;
- D2: MEDIA (L8) do Corne sem brilho;
- conflitos: lista explícita (vazia no dataset inicial);
- escrita atômica e recusa de sobrescrita sem --force.
"""
import argparse
import copy
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import corne_extractor  # noqa: E402
import ksm_core  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CORNE = os.path.join(ROOT, "Corne")
FIXTURES = os.path.join(HERE, "..", "data", "fixtures")
DEFAULT_V5 = os.path.join(FIXTURES, "keymap_data_v05.json") if os.path.exists(os.path.join(FIXTURES, "keymap_data_v05.json")) else os.path.join(CORNE, "keymap_data.json")
DEFAULT_V3 = os.path.join(CORNE, "keymap_data_v03_baseline.json")
DEFAULT_REF = os.path.join(HERE, "..", "data", "corne_reference_extracted.json")
DEFAULT_VIL = os.path.join(FIXTURES, "SOFLE_FINAL_HOMOLOGADO_v01.vil") if os.path.exists(os.path.join(FIXTURES, "SOFLE_FINAL_HOMOLOGADO_v01.vil")) else os.path.join(CORNE, "SOFLE_FINAL_HOMOLOGADO_v01.vil")
DEFAULT_OUT = os.path.join(HERE, "..", "data", "keymap_data_v06.json")


class BuildError(Exception):
    pass


def fail(msg):
    raise BuildError(msg)


def file_sha256(path):
    return ksm_core.file_hash(path)


def validate_candidate_layers(data):
    order = data["metadata"]["layers_order"]
    if order != [f"L{i}" for i in range(10)]:
        fail(f"layers_order inesperada: {order}")
    for lid in order:
        lay = data["layers"].get(lid)
        if not lay:
            fail(f"camada {lid} ausente")
        for kb, rows, thumbs in (("corne", 3, 6), ("sofle", 4, 10)):
            obj = lay.get(kb)
            if not obj:
                fail(f"{lid}/{kb} ausente")
            m = obj.get("matrix")
            t = obj.get("thumbs")
            if not isinstance(m, list) or len(m) != rows or any(len(r) != 12 for r in m):
                fail(f"{lid}/{kb} matrix deve ser {rows}x12")
            if not isinstance(t, list) or len(t) != thumbs:
                fail(f"{lid}/{kb} thumbs deve ter {thumbs}")
            for cell in [c for r in m for c in r] + t:
                for k in ("label", "impl_zmk", "impl_qmk"):
                    if k not in cell:
                        fail(f"{lid}/{kb} célula sem campo {k}")


def validate_mirror(data):
    order = data["metadata"]["layers_order"]
    for kb, rows, thumbs in (("corne", 3, 6), ("sofle", 4, 10)):
        prof = data["profiles"]["candidato_teste"][kb]["layers"]
        if list(prof.keys()) != order:
            fail(f"espelho {kb} não contém exatamente {order}")
        for lid in order:
            a = data["layers"][lid][kb]
            b = prof[lid]
            if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
                fail(f"espelho divergente em {lid}/{kb}")


def validate_references(data):
    ref = data["references"]
    corne = ref["corne"]
    if list(corne["native_layers"].keys()) != list(corne_extractor.EXPECTED_LAYERS):
        fail(f"camadas da referência Corne inesperadas: {list(corne['native_layers'])}")
    for name, lay in corne["native_layers"].items():
        if lay.get("binding_count") != 42:
            fail(f"referência {name} sem 42 bindings")
        if len(lay.get("matrix", [])) != 3 or any(len(r) != 12 for r in lay["matrix"]):
            fail(f"referência {name} matrix inválida")
        if len(lay.get("thumbs", [])) != 6:
            fail(f"referência {name} thumbs inválidos")

    sofle = ref["sofle"]
    vil = sofle["vil"]
    required = ("version", "uid", "layout", "encoder_layout", "layout_options", "macro",
                "vial_protocol", "via_protocol", "tap_dance", "combo", "key_override",
                "alt_repeat_key", "settings")
    missing = [k for k in required if k not in vil]
    if missing:
        fail(f".vil de referência sem campos: {missing}")
    if not isinstance(vil["uid"], str) or not vil["uid"].isdigit():
        fail("UID Sofle de referência não é string decimal")
    if len(vil["layout"]) != 16:
        fail(f".vil de referência deveria ter 16 camadas, tem {len(vil['layout'])}")
    for i, lay in enumerate(vil["layout"]):
        if len(lay) != 10 or any(len(row) != 6 for row in lay):
            fail(f".vil referência L{i} não é 10x6")
    if len(vil["encoder_layout"]) != 16:
        fail("encoder_layout deveria ter 16 camadas")


def build(v5_path, v3_path, ref_path, vil_path):
    v5 = ksm_core.load_canonical(v5_path)
    if v5.get("schema_version") != 5:
        fail("dataset v05 de entrada não tem schema_version 5")
    v3 = ksm_core.load_canonical(v3_path)

    extracted = corne_extractor.extract(ref_path)
    with open(vil_path, "r", encoding="utf-8") as f:
        vil_raw = json.load(f)

    out = copy.deepcopy(v5)
    out["schema_version"] = 6
    out["version"] = "v06_consolidada"
    out.pop("updated_at", None)  # campo volátil fora do hash canônico
    out["metadata"] = dict(out.get("metadata") or {})
    out["metadata"]["description"] = (
        "Fonte Única v06: candidato L0-L9 editável, referência Corne nativa "
        "(4 camadas) e referência Sofle .vil completa (16 camadas)."
    )
    out["metadata"]["source_of_truth"] = "ksm-work/data/keymap_data_v06.json"
    out["metadata"]["reference_mapping_policy"] = (
        "Referências não são rotuladas com nomes de camadas do candidato. "
        "Comparações são explícitas e escolhidas pelo usuário; slots sem "
        "referência não recebem transparentes artificiais."
    )
    out["metadata"]["decisions"] = [
        {
            "id": "D1",
            "status": "CONFIRMADA",
            "decision": "Preservar o comportamento do combo Caps em 24+35; corrigir a descrição.",
            "evidence": "resposta direta do usuário em 2026-10-29; posição 35 no candidato L0 é Esc/hold L9 (não RShift).",
        },
        {
            "id": "D2",
            "status": "CONFIRMADA",
            "decision": "Remover brilho da camada MEDIA (L8) do candidato Corne.",
            "evidence": "resposta direta do usuário em 2026-10-29 ('Remover brilho (Recomendado)'); posições 30/31 de L8 Corne estão &none/KC_NO.",
        },
    ]
    out["metadata"]["legacy_baselines"] = {
        "v03": {
            "schema_version": 3,
            "version": v3.get("version"),
            "layers": v3.get("layers", {}),
        },
        "v05": {
            "schema_version": 5,
            "version": v5.get("version"),
            "layers": v5.get("layers", {}),
        },
    }

    # ------------------------- referências -------------------------
    out["references"] = {
        "corne": {
            "source": "reference",
            "read_only": True,
            "source_file": extracted["source_file"],
            "source_sha256": extracted["source_sha256"],
            "reference_commit": v5["profiles"]["baseline_instalado"]["corne"].get("reference_commit"),
            "reference_branch": v5["profiles"]["baseline_instalado"]["corne"].get("branch"),
            "layer_count": extracted["layer_count"],
            "native_layers": extracted["layers"],
            "note": (
                "Referência de firmware ZMK extraída do devicetree. Não comprova "
                "sozinha o mapa dinâmico atualmente ativo no ZMK Studio."
            ),
        },
        "sofle": {
            "source": "reference",
            "read_only": True,
            "source_file": os.path.abspath(vil_path),
            "source_sha256": file_sha256(vil_path),
            "layer_count": len(vil_raw["layout"]),
            "uid": str(vil_raw["uid"]),
            "vil": ksm_core.uid_text_in_obj(vil_raw) if hasattr(ksm_core, "uid_text_in_obj") else _uid_text(vil_raw),
            "note": (
                "Backup .vil completo preservado: 16 camadas, UID, encoder_layout, "
                "macros, tap dances, combos, key overrides, alt repeat e settings. "
                "Não reduzir a exportação às 580 posições visíveis."
            ),
        },
    }

    # ------------------------- perfis -------------------------
    out["profiles"] = {
        "candidato_teste": {
            "name": "Candidato editavel (Corne v05 / Sofle v06)",
            "description": "Perfil editavel. A fonte autoritativa e o objeto top-level 'layers'.",
            "editable": True,
            "source": "candidate",
            "corne": {
                "version": v5["profiles"]["candidato_teste"]["corne"].get("version"),
                "status": v5["profiles"]["candidato_teste"]["corne"].get("status"),
                "target_keymap": "corne_candidato_v01.keymap",
                "layers": copy.deepcopy(v5["profiles"]["candidato_teste"]["corne"]["layers"]),
            },
            "sofle": {
                "version": v5["profiles"]["candidato_teste"]["sofle"].get("version"),
                "status": v5["profiles"]["candidato_teste"]["sofle"].get("status"),
                "layers": copy.deepcopy(v5["profiles"]["candidato_teste"]["sofle"]["layers"]),
            },
        },
        "baseline_instalado": {
            "name": "Referencia preservada (somente leitura)",
            "description": (
                "Corne: 4 camadas nativas do devicetree. Sofle: .vil completo de 16 camadas. "
                "Nenhum rotulo de camada do candidato e aplicado automaticamente."
            ),
            "editable": False,
            "source": "reference",
            "corne": {
                "reference": "references.corne",
                "read_only": True,
                "native_layers": list(extracted["layers"].keys()),
                "status": v5["profiles"]["baseline_instalado"]["corne"].get("status"),
            },
            "sofle": {
                "reference": "references.sofle",
                "read_only": True,
                "uid": str(vil_raw["uid"]),
                "uid_representation": "decimal_string",
                "sha256": file_sha256(vil_path),
                "layer_count": len(vil_raw["layout"]),
                "status": v5["profiles"]["baseline_instalado"]["sofle"].get("status"),
            },
        },
    }

    # D1: descrição correta do combo Caps (comportamento preservado)
    for cb in out.get("combos", []):
        if cb.get("name") == "combo_caps":
            cb["display_name"] = "Caps Lock (Shift esquerdo + Esc/L9 nas posicoes 24 e 35)"
            cb["behavior_note"] = (
                "Comportamento preservado. A posicao 35 e Esc (tap) / hold L9 no candidato L0; "
                "nao e o Shift direito."
            )

    _apply_d2(out)

    out["conflicts"] = []
    out["function_status"] = _function_status()
    out["validation_state"] = {
        "dataset": "validado por build_dataset_v06",
        "app": "pendente de teste de navegador",
        "corne_generated": "pendente",
        "corne_firmware_built": "bloqueado: west/zephyr SDK ausentes neste ambiente",
        "sofle_generated": "pendente",
        "physical_test": "pendente: nenhum teclado foi tocado nesta execucao",
    }

    validate_candidate_layers(out)
    validate_mirror(out)
    validate_references(out)
    _validate_d1_d2(out)
    _validate_corne_bindings(out)
    return out



def _apply_d2(data):
    """D2 CONFIRMADA: remove brilho da MEDIA (L8) no candidato Corne.

    Aplicado no dado editavel E no espelho do perfil; a referencia de firmware
    nao e alterada (o brilho continua existindo no hardware/referencia).
    """
    cell = {
        "top": "", "label": "\u2014", "sub": "",
        "behavior": "Liberado (D2: MEDIA sem brilho)",
        "impl_zmk": "&none", "impl_qmk": "KC_NO",
        "key_type": "normal", "status": "candidato",
    }
    targets = [
        data["layers"]["L8"]["corne"],
        data["profiles"]["candidato_teste"]["corne"]["layers"]["L8"],
    ]
    for lay in targets:
        flat = [c for row in lay["matrix"] for c in row] + lay["thumbs"]
        for idx in (30, 31):
            flat[idx].clear()
            flat[idx].update(copy.deepcopy(cell))

def _uid_text(obj):
    """Converte qualquer uid inteiro grande em string decimal, recursivamente."""
    def walk(o):
        if isinstance(o, dict):
            return {k: (str(v) if k == "uid" and isinstance(v, int) else walk(v)) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v) for v in o]
        return o
    return walk(obj)


def _validate_d1_d2(data):
    caps = [c for c in data["combos"] if c.get("name") == "combo_caps"]
    if len(caps) != 1 or caps[0]["key_positions"] != [24, 35]:
        fail("D1: combo_caps deve manter key_positions [24, 35]")
    flat = [c for row in data["layers"]["L0"]["corne"]["matrix"] for c in row]
    pos35 = flat[35]
    if pos35.get("impl_zmk") != "&lt 9 ESC":
        fail(f"D1: posição 35 deveria ser &lt 9 ESC, recebido {pos35.get('impl_zmk')!r}")
    m8 = data["layers"]["L8"]["corne"]
    bright = [c for c in [x for r in m8["matrix"] for x in r] + m8["thumbs"] if "BRI" in str(c.get("impl_zmk", ""))]
    if bright:
        fail(f"D2: L8 MEDIA contém brilho: {bright}")


def _validate_corne_bindings(data):
    """Valida referências a behaviors/macros no candidato Corne."""
    behaviors = {b["name"] for b in data.get("behaviors", [])}
    macros = {m["name"] for m in data.get("macros", [])}
    known = behaviors | macros
    # refs embutidas do ZMK não são nós locais
    builtin = {"kp", "trans", "none", "mo", "lt", "to", "tog", "bt", "mkp", "mmv", "msc",
               "sys_reset", "bootloader", "studio_unlock", "key_repeat", "out"}
    for lid in data["metadata"]["layers_order"]:
        corne = data["layers"][lid]["corne"]
        for cell in [c for r in corne["matrix"] for c in r] + corne["thumbs"]:
            expr = str(cell.get("impl_zmk", "")).strip()
            if not expr.startswith("&"):
                fail(f"{lid}/corne binding sem &: {expr!r}")
            ref = expr.split()[0][1:]
            if ref not in builtin and ref not in known:
                fail(f"{lid}/corne referencia behavior/macro inexistente: &{ref}")
    for bh in data.get("behaviors", []):
        for b in bh.get("bindings", []):
            r = str(b).lstrip("&")
            if r and r not in known and r not in builtin:
                fail(f"behavior {bh['name']} referencia {b!r} desconhecido")


def _function_status():
    return [
        {"keyboard": "corne", "function": "Dedões 36-41 (tap/hold)", "status": "implemented",
         "evidence": "bindings gerados a partir do dataset; behaviors ht_rep_media/ht_undo_fun validados", "physical_test": "pending"},
        {"keyboard": "corne", "function": "SYSTEM L6 (L2+L4 conditional_layers)", "status": "implemented",
         "evidence": "conditional_layers if-layers [2,4] then-layer 6 no gerador", "physical_test": "pending"},
        {"keyboard": "corne", "function": "Combo Caps 24+35", "status": "implemented",
         "evidence": "combo_caps preservado; descrição corrigida (D1)", "physical_test": "pending"},
        {"keyboard": "corne", "function": "MEDIA sem brilho (L8)", "status": "implemented",
         "evidence": "posições 30/31 de L8 são &none/KC_NO (D2)", "physical_test": "pending"},
        {"keyboard": "corne", "function": "Build ZMK/UF2", "status": "blocked",
         "evidence": "west e arm-zephyr-eabi-gcc ausentes; nenhum firmware gerado", "physical_test": "pending"},
        {"keyboard": "sofle", "function": "16 camadas + UID + encoders + macros + tap dances + combos", "status": "implemented",
         "evidence": "gerador parte de SOFLE_FINAL_HOMOLOGADO_v01.vil e preserva campos completos", "physical_test": "pending"},
        {"keyboard": "sofle", "function": "Repeat QK_REP (L8)", "status": "pending_firmware",
         "evidence": "firmware instalado sem REPEAT_KEY_ENABLE; slot instalado preservado", "physical_test": "pending"},
        {"keyboard": "sofle", "function": "TapDance Cmd+Z/L7", "status": "pending_firmware",
         "evidence": "TD1 do backup contém apenas LGUI(KC_Z); wiring exige decisão", "physical_test": "pending"},
        {"keyboard": "sofle", "function": "macro_diff / macro_strudel_*", "status": "pending_firmware",
         "evidence": "macros não implementadas no firmware instalado; slots preservados", "physical_test": "pending"},
        {"keyboard": "sofle", "function": "RGB por camada / OLED", "status": "pending_firmware",
         "evidence": "lógica no firmware custom v01; .vil sozinho não comprova comportamento", "physical_test": "pending"},
        {"keyboard": "app", "function": "Editar/salvar/importar/histórico/comparar", "status": "implemented",
         "evidence": "testes automatizados e navegador real nos relatórios", "physical_test": "n/a"},
    ]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--v5", default=DEFAULT_V5)
    ap.add_argument("--v3", default=DEFAULT_V3)
    ap.add_argument("--corne-ref", default=DEFAULT_REF)
    ap.add_argument("--vil", default=DEFAULT_VIL)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    out_path = os.path.abspath(args.out)
    if os.path.exists(out_path) and not args.force:
        raise SystemExit(f"RECUSADO: destino já existe ({out_path}); use --force para substituir de forma explícita")
    data = build(os.path.abspath(args.v5), os.path.abspath(args.v3),
                 os.path.abspath(args.corne_ref), os.path.abspath(args.vil))
    payload = json.dumps(data, ensure_ascii=False, indent=1)
    ksm_core.atomic_write(out_path, payload.encode("utf-8"))
    print(json.dumps({
        "out": out_path,
        "schema": data["schema_version"],
        "uid": data["references"]["sofle"]["uid"],
        "uid_type": type(data["references"]["sofle"]["uid"]).__name__,
        "corne_reference_layers": list(data["references"]["corne"]["native_layers"]),
        "sofle_reference_layers": data["references"]["sofle"]["layer_count"],
        "candidate_positions": {
            "corne": sum(len(r) for r in data["layers"]["L0"]["corne"]["matrix"]) + len(data["layers"]["L0"]["corne"]["thumbs"]),
            "sofle": sum(len(r) for r in data["layers"]["L0"]["sofle"]["matrix"]) + len(data["layers"]["L0"]["sofle"]["thumbs"]),
        },
        "canonical_hash": ksm_core.canonical_hash(data),
        "file_hash": file_sha256(out_path),
        "bytes": len(payload.encode("utf-8")),
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
