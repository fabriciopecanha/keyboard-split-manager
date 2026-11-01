#!/usr/bin/env python3
"""generate_corne_candidato — gerador ZMK a partir do dataset v6 (Fonte Única).

Correções vs. generate_corne_from_json.py (Problemas B/D/E + decisões D1/D2):
- hash CANÔNICO (campos voláteis excluídos); hash de ARQUIVO é distinto e pós-geração;
- caminho default resolvido a partir de __file__, não do CWD do terminal;
- saída SEMPRE nova em --out; recusa destino existente (anti-sobrescrita);
- células com status 'conflict' => ABORTA sem gerar arquivo parcial;
- L8 MEDIA com brilho => ABORTA (D2 exige dataset limpo — gerador não transforma dado);
- determinístico: nenhum timestamp no conteúdo funcional;
- escrita atômica.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import ksm_core  # noqa: E402

LAYER_NODE_PREFIX = "layer_"
BRIGHT_MARKS = ("BRI",)


def fail(msg):
    print(f"GERAÇÃO ABORTADA: {msg}", file=sys.stderr)
    sys.exit(2)


def _cells(lay, kind):
    cells = lay[kind]
    return [c for row in cells for c in row] if kind == "matrix" else cells


def validate(data, src_path):
    if data.get("schema_version") != 6:
        fail(f"esperado schema 6; recebido {data.get('schema_version')!r} ({src_path})")
    order = data["metadata"]["layers_order"]

    # conflito pendente => bloqueio total (nenhum candidato com conflito)
    conflicts = []
    for lid in order:
        for loc, lay in (("layers", data["layers"][lid]["corne"]),
                         ("candidato_teste", data["profiles"]["candidato_teste"]["corne"]["layers"][lid])):
            for i, c in enumerate(_cells(lay, "matrix") + _cells(lay, "thumbs")):
                if str(c.get("status", "")).strip() == "conflict":
                    conflicts.append((loc, lid, i, c.get("label"), c.get("impl_zmk")))
    if conflicts:
        fail(f"{len(conflicts)} células status 'conflict' (ex.: {conflicts[:3]}); resolva na Fonte Única.")

    # 42 posições por camada
    bad = [(l, sum(len(r) for r in data["layers"][l]["corne"]["matrix"]) +
            len(data["layers"][l]["corne"]["thumbs"])) for l in order]
    bad = [b for b in bad if b[1] != 42]
    if bad:
        fail(f"camadas com posições != 42: {bad}")

    # D2: MEDIA (L8) sem brilho no dataset
    m8 = data["layers"][order[8] if len(order) > 8 else None]["corne"] if len(order) > 8 else None
    if m8 is None:
        fail("L8 MEDIA ausente no dataset")
    bright = [(i, c["impl_zmk"]) for i, c in enumerate(_cells(m8, "matrix") + _cells(m8, "thumbs"))
              if "BRI" in c.get("impl_zmk", "")]
    if bright:
        fail(f"D2: L8 MEDIA contém brilho {bright} — corrija o dataset antes de gerar.")
    return order


def gen_behaviors(data, L):
    a = L.append
    a("    behaviors {")
    for bh in data.get("behaviors", []):
        node = bh.get("node_name", bh["name"])
        disp = bh.get("display_name", bh["name"]).replace('"', '\\"')
        a(f"        /* {disp} */")
        a(f"        {bh['name']}: {node} {{")
        a('            compatible = "zmk,behavior-hold-tap";')
        a("            #binding-cells = <2>;")
        a(f'            flavor = "{bh.get("flavor", "balanced")}";')
        a(f"            tapping-term-ms = <{bh.get('tapping_term_ms', 200)}>;")
        if "quick_tap_ms" in bh:
            a(f"            quick-tap-ms = <{bh['quick_tap_ms']}>;")
        if "require_prior_idle_ms" in bh:
            a(f"            require-prior-idle-ms = <{bh['require_prior_idle_ms']}>;")
        if "hold_trigger_key_positions" in bh:
            a(f"            hold-trigger-key-positions = <{' '.join(map(str, bh['hold_trigger_key_positions']))}>;")
        if bh.get("hold_trigger_on_release"):
            a("            hold-trigger-on-release;")
        a(f"            bindings = <{' '.join(bh.get('bindings', []))}>;")
        a(f'            display-name = "{disp}";')
        a("        };")
        a("")
    a("    };")
    a("")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=os.path.join(HERE, "..", "data", "keymap_data_v06.json"))
    ap.add_argument("--profile", choices=["candidate", "simple"], default="candidate",
                    help="Perfil do Corne a ser gerado: 'candidate' (10 camadas L0..L9) ou 'simple' (Corne Simples 7 camadas)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--force", action="store_true", help="permite sobrescrever destino existente explicitamente")
    args = ap.parse_args()
    src = os.path.abspath(args.dataset)
    dst = os.path.abspath(args.out)
    if os.path.exists(dst) and not args.force:
        fail(f"destino já existe ({dst}) — use --force para sobrescrever (política anti-sobrescrita)")
    data = ksm_core.load_canonical(src)
    chash = ksm_core.canonical_hash(data)

    L = []
    a = L.append

    if args.profile == "simple":
        simple = data.get("profiles", {}).get("corne_simples_v01")
        if not simple:
            fail("perfil 'corne_simples_v01' ausente no dataset")
        order = simple.get("layers_order", [f"L{i}" for i in range(7)])
        for lid in order:
            lay = simple["layers"].get(lid)
            if not lay:
                fail(f"camada {lid} ausente em corne_simples_v01")
            pos_cnt = sum(len(r) for r in lay["matrix"]) + len(lay["thumbs"])
            if pos_cnt != 42:
                fail(f"camada {lid} em corne_simples_v01 com {pos_cnt} posições (esperado 42)")

        p_name = simple.get("name", "Corne Simples v13")
        p_rev = simple.get("design_revision", 13)
        a("/*")
        a(f" * CORNE 42 (ZMK) — PERFIL: {p_name} (revisão {p_rev})")
        a(f" * Hash canônico do dataset: {chash}")
        a(f" * Versão: {data.get('version')} | Arquivo: {os.path.basename(src)}")
        a(f" * Camadas: L0 a L6 (7 camadas / 294 posições) | Gerador: ksm-work/generators/generate_corne_candidato.py --profile simple")
        a(" */")
        a("")
        a("#include <behaviors.dtsi>")
        a("#include <dt-bindings/zmk/keys.h>")
        a("#include <dt-bindings/zmk/bt.h>")
        a("#include <dt-bindings/zmk/outputs.h>")
        a("#include <dt-bindings/zmk/pointing.h>")
        a("")
        a("/* Keep the standard LT timing. Only its hold delegate is lock-aware. */")
        a("&lt { bindings = <&fp_mo>, <&kp>; };")
        a("")
        a("/ {")
        a("    behaviors {")
        a('        fp_mo: fp_layer_hold { compatible = "fp,behavior-layer-hold"; #binding-cells = <1>; display-name = "FP Layer Hold"; };')
        a('        fp_lock: fp_layer_lock { compatible = "fp,behavior-layer-lock"; #binding-cells = <1>; display-name = "FP Layer Lock"; };')

        b_list = simple.get("behaviors", data.get("behaviors", []))
        for bh in b_list:
            node = bh.get("node_name", bh["name"])
            disp = bh.get("display_name", bh["name"]).replace('"', '\\"')
            a(f"        /* {disp} */")
            a(f"        {bh['name']}: {node} {{")
            a('            compatible = "zmk,behavior-hold-tap";')
            a("            #binding-cells = <2>;")
            a(f'            flavor = "{bh.get("flavor", "balanced")}";')
            a(f"            tapping-term-ms = <{bh.get('tapping_term_ms', 200)}>;")
            if "quick_tap_ms" in bh:
                a(f"            quick-tap-ms = <{bh['quick_tap_ms']}>;")
            if "require_prior_idle_ms" in bh:
                a(f"            require-prior-idle-ms = <{bh['require_prior_idle_ms']}>;")
            if "hold_trigger_key_positions" in bh:
                a(f"            hold-trigger-key-positions = <{' '.join(map(str, bh['hold_trigger_key_positions']))}>;")
            if bh.get("hold_trigger_on_release"):
                a("            hold-trigger-on-release;")
            bindings = [b if b != "&mo" else "&fp_mo" for b in bh.get("bindings", [])]
            a(f"            bindings = <{' '.join(bindings)}>;")
            a(f'            display-name = "{disp}";')
            a("        };")
            a("")

        for name, layer_idx in (("mouse", 3), ("nav", 4)):
            a(f"        td_lock_{name}: tap_dance_lock_{name} {{")
            a('            compatible = "zmk,behavior-tap-dance";')
            a("            #binding-cells = <0>;")
            a(f'            display-name = "Lock {name.upper()} (2 taps)";')
            a("            tapping-term-ms = <200>;")
            a(f"            bindings = <&none>, <&fp_lock {layer_idx}>;")
            a("        };")
        a("    };")
        a("")

        macros_list = simple.get("macros", data.get("macros", []))
        if macros_list:
            a("    macros {")
            for mc in macros_list:
                disp = mc.get("display_name", mc["name"]).replace('"', '\\"')
                a(f"        {mc['name']}: {mc['name']} {{")
                a('            compatible = "zmk,behavior-macro";')
                a("            #binding-cells = <0>;")
                if "wait_ms" in mc:
                    a(f"            wait-ms = <{mc['wait_ms']}>;")
                if "tap_ms" in mc:
                    a(f"            tap-ms = <{mc['tap_ms']}>;")
                a(f'            display-name = "{disp}";')
                bindings_str = " ".join(mc.get("bindings", []))
                a(f"            bindings = <&macro_tap {bindings_str}>;")
                a("        };")
            a("    };")
            a("")

        node_names = ["base", "symbols", "num", "mouse", "nav", "system", "fun"]
        a(f"    /* KEYMAP CANÔNICO CORNE SIMPLES: 42 teclas × {len(order)} camadas (294 posições) */")
        a("    keymap {")
        a('        compatible = "zmk,keymap";')
        a("")
        for idx, lid in enumerate(order):
            info = simple["layers_info"].get(lid, {"name": lid})
            corne = simple["layers"][lid]
            node_id = f"{node_names[idx]}_layer" if idx < len(node_names) else f"{LAYER_NODE_PREFIX}{idx}"
            a(f"        /* {lid}: {info.get('name','')} */")
            a(f"        {node_id} {{")
            a(f'            display-name = "{info["name"].split()[0]}";')
            a("            bindings = <")
            for row in corne["matrix"]:
                left = " ".join(f"{k['impl_zmk']:<16}" for k in row[:6]).rstrip()
                right = " ".join(f"{k['impl_zmk']:<16}" for k in row[6:]).rstrip()
                a(f"                {left}    {right}")
            t = corne["thumbs"]
            lt = " ".join(f"{k['impl_zmk']:<16}" for k in t[:3]).rstrip()
            rt = " ".join(f"{k['impl_zmk']:<16}" for k in t[3:]).rstrip()
            a(f"                          {lt}    {rt}")
            a("            >;")
            a("        };")
            a("")
        a("    };")
        a("};")
        a("")
    else:
        order = validate(data, src)
        a("/*")
        a(" * CORNE 42 (ZMK) — CANDIDATO (ksm-work/generators/generate_corne_candidato.py)")
        a(f" * Hash canônico do dataset: {chash}")
        a(f" * Versão: {data.get('version')} | Arquivo: {os.path.basename(src)}")
        a(" * Precedência: alterações salvas no ZMK Studio prevalecem sobre mapa compilado.")
        a(" */")
        a("")
        a("#include <behaviors.dtsi>")
        a("#include <dt-bindings/zmk/keys.h>")
        a("#include <dt-bindings/zmk/bt.h>")
        a("#include <dt-bindings/zmk/outputs.h>")
        a("#include <dt-bindings/zmk/pointing.h>")
        a("")
        a("/ {")
        l_ = []
        gen_behaviors(data, l_)
        L.extend(l_)
        if data.get("combos"):
            a("    combos {")
            a('        compatible = "zmk,combos";')
            for cb in data["combos"]:
                pos = " ".join(str(p) for p in cb["key_positions"])
                lay = " ".join(str(l) for l in cb.get("layers", [0]))
                a(f"        {cb['name']} {{")
                a(f"            timeout-ms = <{cb.get('timeout_ms', 50)}>;")
                a(f"            key-positions = <{pos}>; /* {cb.get('display_name','')} */")
                a(f"            bindings = <{cb['bindings']}>;")
                a(f"            layers = <{lay}>;")
                a("        };")
            a("    };")
            a("")
        if data.get("macros"):
            a("    macros {")
            for mc in data["macros"]:
                disp = mc.get("display_name", mc["name"]).replace('"', '\\"')
                a(f"        {mc['name']}: {mc['name']} {{")
                a('            compatible = "zmk,behavior-macro";')
                a("            #binding-cells = <0>;")
                if "wait_ms" in mc:
                    a(f"            wait-ms = <{mc['wait_ms']}>;")
                if "tap_ms" in mc:
                    a(f"            tap-ms = <{mc['tap_ms']}>;")
                a(f'            display-name = "{disp}";')
                a(f"            bindings = <{' '.join(mc.get('bindings', []))}>;")
                a("        };")
            a("    };")
            a("")
        if data.get("conditional_layers"):
            a("    conditional_layers {")
            a('        compatible = "zmk,conditional-layers";')
            for cl in data["conditional_layers"]:
                a(f"        {cl['name']} {{")
                a(f"            if-layers = <{' '.join(str(l) for l in cl['if_layers'])}>; /* {cl.get('description','')} */")
                a(f"            then-layer = <{cl['then_layer']}>;")
                a("        };")
            a("    };")
            a("")
        a("    /* KEYMAP CANÔNICO: " + " x ".join(["42"]) + f" teclas × {len(order)} camadas */")
        a("    keymap {")
        a('        compatible = "zmk,keymap";')
        a("")
        for idx, lid in enumerate(order):
            info = data["layers_info"][lid]
            corne = data["layers"][lid]["corne"]
            a(f"        /* {lid}: {info.get('name','')} */")
            a(f"        {LAYER_NODE_PREFIX}{idx} {{")
            a(f'            display-name = "{info["name"].split()[0]}";')
            a("            bindings = <")
            for row in corne["matrix"]:
                left = " ".join(f"{k['impl_zmk']:<16}" for k in row[:6]).rstrip()
                right = " ".join(f"{k['impl_zmk']:<16}" for k in row[6:]).rstrip()
                a(f"                {left}    {right}")
            t = corne["thumbs"]
            lt = " ".join(f"{k['impl_zmk']:<16}" for k in t[:3]).rstrip()
            rt = " ".join(f"{k['impl_zmk']:<16}" for k in t[3:]).rstrip()
            a(f"                          {lt}    {rt}")
            a("            >;")
            a("        };")
            a("")
        a("    };")
        a("};")
        a("")

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    ksm_core.atomic_write(dst, "\n".join(L).encode("utf-8"))
    print(json.dumps({"out": dst, "canonical_hash": chash,
                      "file_hash_of_output": ksm_core.file_hash(dst),
                      "layers": order}, ensure_ascii=False))


if __name__ == "__main__":
    main()
