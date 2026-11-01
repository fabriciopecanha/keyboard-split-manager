#!/usr/bin/env python3
"""compose_sofle_candidato — candidatos Sofle v06 com classificação tripla (v02, revisão).

Correções da rodada de revisão (evidências em RELATORIO_REVISAO_KEYMAPS_2026-10-29.md):
 1) MAPEAMENTO FÍSICO CORRETO (matriz elétrica 10×6 do vial.json):
    dataset cand: matrix 4×12 (linha = esquerda 0..5 + direita 6..11 em ordem VISUAL) e thumbs 10.
    - .vil[l][r][c]  (r 0..3) = ds matrix[r][c]        (esquerda, direto)
    - .vil[l][r+5][c](r 0..3) = ds matrix[r][11-c]     (direita, REVERSO —
       calibrado no homologado: .vil L2 row5 [KC_MINS,KC_0,KC_9,KC_8,KC_7,KC_6]
       ⇔ ds L2 row5 [KC_6,KC_7,KC_8,KC_9,KC_0,KC_MINS])
    - .vil[l][4][c]  (c 0..4) = ds thumbs[c]           (esquerda, dir→int)
    - .vil[l][9][c]  (c 0..4) = ds thumbs[9-c]         (direita, REVERSO —
       calibrado no firmware keymap.c LAYOUT row física direita:
       [RCTL, RGUI, TD(1), LT(_NUM,BSPC), LT(_SYM,ENT)] = th[9..5])
    - .vil (4,5) e (9,5) = slots de encoder/ghost — SEMPRE preservados do aprovado.
 2) TRADUÇÃO COMPLETA DE MACROS: todo `&kp X` → ["tap","KC_*"] válido.
    Letras/dígitos com fallback sistemático ([A-Z],[0-9] → KC_<x>); nomes compostos
    calibrados no HOMOLOGADO (único conjunto comprovadamente aceito pelo Vial local):
    LPAR→KC_LPRN (KC_LPAREN NÃO EXISTE no QMK; homologado usa KC_LPRN),
    COLON→KC_COLN, EQUAL→KC_EQUAL, DQT→KC_DQUO, UNDER→KC_UNDS, DLLR→KC_DLR,
    EXCL→KC_EXLM, SPACE→KC_SPC, SQT→KC_QUOTE, TILD→KC_TILD etc.
    TODO keycode gerado (células OU macros) é validado contra VALID_SET
    (= nomes do homologado ∪ key canônicos QMK ∪ aliases QMK; repo pinnado de pesquisa).
    Inválido → KC_NO + pendência explícita (nunca código silenciosamente quebrado).
 3) BRILHO/LED SEM A LEGENDA ERRADA:
    - KC_BRID/KC_BRIU = KC_BRIGHTNESS_DOWN/UP (QMK keycodes_0.0.1_basic.hjson 0x00BE/0x00BD,
      group "media"): brilho do DISPLAY do computador (página consumer), NÃO família RGBLIGHT,
      não requer suporte de firmware. TRATAMENTO: keycode válido, aplicado direto;
      registrado como decisão prévia de layout do candidato (sem "incompatibilidade",
      D2 era decisão do Corne e continua isolada lá).
    - RGB_HUI/HUD/VAI/VAD/TOG/MOD/RMOD: processados por quantum/process_keycode/
      process_underglow.c sob `defined(RGB_MATRIX_ENABLE) && !defined(RGB_MATRIX_DISABLE_SHARED_KEYCODES)`
      — funcionam na matriz salvo define excludente. TRATAMENTO: aplicados direto,
      pendência informativa para conferir o define no custom v01.

Saída 1) candA: cópia BYTE-EXATA de SOFLE_FINAL_HOMOLOGADO_v01.vil (preservação por cópia).
Saída 2) candB: ESTADO A + camadas de design v03 (dataset candidatos L7/L8/L9) nos slots 7/8/9
   com o mapeamento físico correto; keycodes QMK validados; pendências → KC_NO catalogadas;
   macros strudel em M1..M10 no formato Vial [[op, arg]]; M0 ('!=') do homologado intocado;
   slots 0..6 e L10..L15 intocados; uid/encoder_layout/tap_dance/combo/key_override/settings intactos.
"""
import argparse
import copy
import glob
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import ksm_core  # noqa: E402

FIXTURE_BASE = os.path.abspath(os.path.join(HERE, "..", "data", "fixtures", "SOFLE_FINAL_HOMOLOGADO_v01.vil"))
EXTERNAL_BASE = os.path.abspath(os.path.join(HERE, "..", "..", "Corne", "SOFLE_FINAL_HOMOLOGADO_v01.vil"))
BASE = FIXTURE_BASE if os.path.exists(FIXTURE_BASE) else EXTERNAL_BASE

FIXTURE_VALID_SET = os.path.abspath(os.path.join(HERE, "..", "data", "fixtures", "qmk_valid_set.json"))
QMK_REPO = os.path.abspath(os.path.join(
    HERE, "..", "..", "sofle", "_research", "repos", "dinesh0430_full-hope-vial-qmk"))

# ---------------------------------------------------------------- mapa ZMK → QMK
# Convenção do HOMOLOGADO (comprovadamente aceita pelo Vial local).
ZKP_TO_QKC = {
    "LPAR": "KC_LPRN", "RPAR": "KC_RPRN", "DQT": "KC_DQUO", "SQT": "KC_QUOTE",
    "LEFT": "KC_LEFT", "RGHT": "KC_RGHT", "UP": "KC_UP", "DOWN": "KC_DOWN",
    "UNDER": "KC_UNDS", "DLLR": "KC_DLR", "DOLLAR": "KC_DLR", "COLON": "KC_COLN",
    "SEMI": "KC_SCOLON", "EQUAL": "KC_EQUAL", "SPACE": "KC_SPC", "DOT": "KC_DOT",
    "EXCL": "KC_EXLM", "EXLM": "KC_EXLM", "QUES": "KC_QUES", "SLASH": "KC_SLASH",
    "SLSH": "KC_SLASH", "SCAN": "KC_SCOLON", "MINUS": "KC_MINS", "PLUS": "KC_PLUS",
    "COMMA": "KC_COMMA", "COMM": "KC_COMMA", "TAB": "KC_TAB", "RET": "KC_ENTER",
    "ENTER": "KC_ENTER", "BSPC": "KC_BSPC", "DEL": "KC_DEL", "HOME": "KC_HOME",
    "END": "KC_END", "PGUP": "KC_PGUP", "PGDN": "KC_PGDN", "ESC": "KC_ESC",
    "GRAVE": "KC_GRAVE", "GRAV": "KC_GRAVE", "TILDE": "KC_TILD", "TILD": "KC_TILD",
    "LBRC": "KC_LBRACKET", "RBRC": "KC_RBRACKET", "LCBR": "KC_LCBR", "RCBR": "KC_RCBR",
    "PIPE": "KC_PIPE", "BSLH": "KC_BSLASH", "BSLS": "KC_BSLASH", "BQUO": "KC_BSLASH",
}

def zkp_key_to_qkc(tok):
    """token de binding &kp → nome QMK válido ou None."""
    tok = tok.strip()
    if re.fullmatch(r"[0-9]", tok):
        return "KC_" + tok
    if re.fullmatch(r"[A-Z]", tok):
        return "KC_" + tok
    return ZKP_TO_QKC.get(tok)


# ---------------------------------------------------------------- validação de keycodes
def _build_valid_set():
    """VALID_SET = nomes KC_/RGB_ do homologado (prova real do Vial local)
    ∪ "key" canônicos QMK ∪ aliases QMK (carregados da fixture qmk_valid_set.json
    ou inspecionados dinamicamente no repo QMK)."""
    valid = set()
    if os.path.exists(FIXTURE_VALID_SET):
        try:
            valid.update(json.load(open(FIXTURE_VALID_SET, encoding="utf-8")))
        except Exception:
            pass
    if os.path.exists(BASE):
        homolog = json.load(open(BASE, encoding="utf-8"))
        for layer in homolog.get("layout", []):
            for row in layer:
                for cell in row:
                    for t in re.findall(r"(?:KC|RGB)_[A-Z0-9_]+", str(cell)):
                        valid.add(t)
    if os.path.exists(QMK_REPO):
        for f in glob.glob(os.path.join(QMK_REPO, "data", "constants", "keycodes", "**", "*.hjson"),
                           recursive=True):
            try:
                txt = open(f, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for m in re.finditer(r'"key":\s*"(KC_[A-Z0-9_]+|RGB_[A-Z0-9_]+|RGB[A-Z_0-9]*|[A-Z]{2,}[A-Z0-9_]*)"', txt):
                valid.add(m.group(1))
            for m in re.finditer(r'"aliases":\s*\[([^\]]*)\]', txt):
                for al in re.findall(r'"([A-Z0-9_]+)"', m.group(1)):
                    valid.add(al)
    return valid

VALID_SET = _build_valid_set()

# formas estruturais aceitas em .vil (mesma classe usada no homologado):
#   TO(n) | MO(n) | DF(n) | nome QMK | mod-tap/lock/fnarg LGUI(...)/LSFT_T(...) | M<n>
CELL_TOK = (r"(?:KC_[A-Z0-9_]+|RGB_[A-Z0-9_]+|TO\(\d+\)|MO\(\d+\)|DF\(\d+\)|TG\(\d+\)|OSL\(\d+\)|TD\(\d+\)|"
            r"[LMCRS][A-Z0-9_]{0,6}(_T)?\([^()]*(\([^()]*\))?[^()]*\)|[ML]\d+|LT\d*\(.*?\))")

def keycode_names_in(expr):
    return re.findall(r"(?:KC|RGB)_[A-Z0-9_]+", expr)

def vial_cell_is_wellformed(expr):
    return bool(re.fullmatch(CELL_TOK, expr))


# ---------------------------------------------------------------- pendências (legendas corrigidas)
PENDING_EXPL = {
    "QK_REP": "Repeat Key exige REPEAT_KEY_ENABLE (custom v01 rules.mk:21) — firmware instalado não tem; REQUER flash; slot deixado KC_NO",
    "oled_toggle()": "KC_TG_OLED existe no custom v01; requer flash; slot KC_NO",
    "reset_user()": "QK_REBOOT nativo; slot KC_NO até decisão",
    "bootloader_user()": "QK_BOOT nativo; slot KC_NO até decisão",
    "MS_ACL0": "traduzido: KC_ACL0 (evidência rules.mk:27)",
    "MS_ACL1": "traduzido: KC_ACL1",
    "MS_ACL2": "traduzido: KC_ACL2",
}
# keycodes válidos que continuam ativos; nota informativa (não pendência de incompatibilidade):
NOTE_VALID = {
    "RGB_TOG": "RGB_* processado p/ RGB_MATRIX no QMK atual (process_underglow.c: RGB_MATRIX_ENABLE && !RGB_MATRIX_DISABLE_SHARED_KEYCODES) — conferir define no custom v01",
    "RGB_MOD": "idem RGB_TOG (process_underglow.c)",
    "RGB_RMOD": "idem RGB_TOG (process_underglow.c)",
    "RGB_HUI": "idem RGB_TOG (process_underglow.c)",
    "RGB_HUD": "idem RGB_TOG (process_underglow.c)",
    "RGB_VAI": "idem RGB_TOG (process_underglow.c)",
    "RGB_VAD": "idem RGB_TOG (process_underglow.c)",
    "KC_BRID": "KC_BRID = KC_BRIGHTNESS_DOWN (QMK keycodes_0.0.1_basic.hjson:0x00BE, group media): brilho do DISPLAY do host (página consumer) — não requer suporte de firmware e NÃO é família RGBLIGHT. Decisão de layout, mantido",
    "KC_BRIU": "KC_BRIU = KC_BRIGHTNESS_UP (QMK keycodes_0.0.1_basic.hjson:0x00BD, group media): idem KC_BRID",
}


# ---------------------------------------------------------------- macros
def expand_dataset_macro(name, mc):
    """dataset bindings ['&kp X', ...] -> [[op, arg], ...] com keycodes 100% validados; None se não coberto."""
    ops = []
    for b in mc.get("bindings", []):
        m = re.fullmatch(r"&kp ([A-Z0-9_]+)", b)
        if not m:
            return None
        q = zkp_key_to_qkc(m.group(1))
        if q is None or q not in VALID_SET:
            return None
        ops.append(["tap", q])
    return ops or None


# ---------------------------------------------------------------- mapeamento físico
def ds_layer_to_electrical(ds_layer):
    """(matrix 4×12 + thumbs 10) → elétrica .vil 10×6; retorna (celulas10x6, mapa_origem)."""
    mx = [row[:] for row in ds_layer["matrix"]]
    th = ds_layer["thumbs"]
    rows = [[None] * 6 for _ in range(10)]
    mapa = {}
    for r in range(4):
        for c in range(6):
            rows[r][c] = mx[r][c]
            mapa[(r, c)] = f"matrix[{r}][{c}]"
    for r in range(4):
        for c in range(6):
            rows[r + 5][c] = mx[r][11 - c]
            mapa[(r + 5, c)] = f"matrix[{r}][{11 - c}]"
    for c in range(5):
        rows[4][c] = th[c]
        mapa[(4, c)] = f"thumbs[{c}]"
    for c in range(5):
        rows[9][c] = th[9 - c]
        mapa[(9, c)] = f"thumbs[{9 - c}]"
    # (4,5)/(9,5) ficam None → preservados do aprovado (encoder/ghost slot)
    return rows, mapa


# ---------------------------------------------------------------- escrita de célula
def write_cell(rows, r, c, cell, layer_name, applied, pending, macro_slots, data):
    before = rows[r][c]
    q = (cell.get("impl_qmk") or "").strip()
    q = q.replace("KC_LBKT", "KC_LBRACKET").replace("KC_RBKT", "KC_RBRACKET")
    if q == "":
        rows[r][c] = "KC_TRNS"
        applied.append({"layer": layer_name, "pos": [r, c], "dataset": q,
                        "nivel": "placeholder (impl_qmk vazio)", "to": "KC_TRNS"})
        return
    if q == "macro_diff" or q == "M0":
        rows[r][c] = "M0"
        applied.append({"layer": layer_name, "pos": [r, c], "from": before, "to": "M0",
                        "nivel": "implementado (macro M0 '!=')", "evidencia": "M0"})
        return
    if q.startswith("MT(MOD_") or q.startswith("LT("):
        m_mt = re.fullmatch(r"MT\(MOD_([A-Z0-9_]+),\s*(KC_[A-Z0-9_]+)\)", q)
        if m_mt:
            mod, kc = m_mt.group(1), m_mt.group(2)
            if kc == "KC_SCLN": kc = "KC_SCOLON"
            q = f"{mod}_T({kc})"
        m_lt = re.fullmatch(r"LT\((\d+),\s*([A-Z0-9_]+)\)", q)
        if m_lt:
            lay, kc = m_lt.group(1), m_lt.group(2)
            if kc == "KC_SPC": kc = "KC_SPACE"
            elif kc == "KC_ENT": kc = "KC_ENTER"
            elif kc == "KC_BSPC": kc = "KC_BSPACE"
            q = f"LT{lay}({kc})"
    if q == "process_record_user(QK_REP/L8)":
        q = "MO(8)"
    elif q == "TapDance/process_record(Cmd+Z/L7)":
        q = "TD(1)"
    # --- macro strudel → M<slot> (só após validar a sequência inteira)
    if re.fullmatch(r"macro_strudel_[a-z_]+", q):
        name = q[len("macro_"):]
        mc = next((m for m in data["macros"] if m["name"] == name), None)
        ops = expand_dataset_macro(name, mc) if mc else None
        if ops is None:
            pending.append({"layer": layer_name, "pos": [r, c], "dataset": q,
                            "nivel": "pendente",
                            "por_que": f"macro {name}: sequência não traduzível automaticamente"})
            rows[r][c] = "KC_NO"
            return
        macro_slots[name] = ops
        rows[r][c] = f"@macro:{name}"  # token resolvido após índice definitivo (M1..M10)
        applied.append({"layer": layer_name, "pos": [r, c], "from": before, "to": None,
                        "nivel": "implementado (macro)",
                        "evidencia": f"macro '{name}' completa; keycodes validados QMK: "
                                     + ",".join(op[1] for op in ops)})
        return
    # --- pendências catalogadas
    if q in PENDING_EXPL:
        rule = PENDING_EXPL[q]
        if rule.startswith("traduzido:"):
            kc = rule.split(": ", 1)[1]
            rows[r][c] = kc
            applied.append({"layer": layer_name, "pos": [r, c], "from": before, "to": kc,
                            "nivel": "implementado", "evidencia": rule})
            return
        pending.append({"layer": layer_name, "pos": [r, c], "dataset": q,
                        "nivel": "pendente", "por_que": rule})
        rows[r][c] = "KC_NO"
        return
    # --- keycodes válidos com nota informativa (brilho/LED: classificação correta)
    if q in NOTE_VALID:
        valid = all(k in VALID_SET for k in keycode_names_in(q)) and vial_cell_is_wellformed(q)
        if valid:
            rows[r][c] = q
            applied.append({"layer": layer_name, "pos": [r, c], "from": before, "to": q,
                            "nivel": "implementado (decisão de layout)", "evidencia": NOTE_VALID[q]})
            return
        pending.append({"layer": layer_name, "pos": [r, c], "dataset": q,
                        "nivel": "pendente", "por_que": "validação de keycode falhou (inconsistência)"})
        rows[r][c] = "KC_NO"
        return
    # --- keycodes e binding estruturais com nomes QMK validados
    ks = keycode_names_in(q)
    if all(k in VALID_SET for k in ks) and vial_cell_is_wellformed(q):
        rows[r][c] = q
        applied.append({"layer": layer_name, "pos": [r, c], "from": before, "to": q,
                        "nivel": "implementado (keycode QMK validado)"})
        return
    # --- formato ainda não coberto / keycode fora do VALID_SET
    pending.append({"layer": layer_name, "pos": [r, c], "dataset": q,
                    "nivel": "pendente", "por_que": f"formato desconhecido ou keycode fora do VALID_SET: {q}"})
    rows[r][c] = "KC_NO"


def validate_sofle_dataset(data, src_path):
    if data.get("schema_version") != 6:
        print(f"GERAÇÃO ABORTADA: esperado schema 6; recebido {data.get('schema_version')!r} ({src_path})", file=sys.stderr)
        sys.exit(2)

    # Bloqueio total se houver conflito pendente na lista
    if data.get("conflicts"):
        print(f"GERAÇÃO ABORTADA: {len(data['conflicts'])} conflito(s) pendente(s) em data['conflicts']; resolva na Fonte Única.", file=sys.stderr)
        sys.exit(2)

    order = data.get("metadata", {}).get("layers_order", [f"L{i}" for i in range(10)])
    conflicts = []
    for lid in order:
        for loc, lay in (("layers", data.get("layers", {}).get(lid, {}).get("sofle")),
                         ("candidato_teste", data.get("profiles", {}).get("candidato_teste", {}).get("sofle", {}).get("layers", {}).get(lid))):
            if not lay:
                continue
            cells = [c for row in lay["matrix"] for c in row] + lay["thumbs"]
            for i, c in enumerate(cells):
                if str(c.get("status", "")).strip() == "conflict":
                    conflicts.append((loc, lid, i, c.get("label"), c.get("impl_qmk")))
    if conflicts:
        print(f"GERAÇÃO ABORTADA: {len(conflicts)} células status 'conflict' no Sofle (ex.: {conflicts[:3]}); resolva na Fonte Única.", file=sys.stderr)
        sys.exit(2)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=os.path.join(HERE, "..", "data", "keymap_data_v06.json"))
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--force", action="store_true", help="permite sobrescrever arquivos existentes com confirmação explícita")
    args = ap.parse_args()
    if not args.outdir and not args.out:
        ap.error("informe --outdir ou --out")
    outdir = args.outdir or os.path.dirname(os.path.abspath(args.out))

    data = ksm_core.load_canonical(args.dataset)
    validate_sofle_dataset(data, args.dataset)
    cand = data["profiles"]["candidato_teste"]["sofle"]["layers"]

    os.makedirs(outdir, exist_ok=True)
    a_path = os.path.join(outdir, "sofle_candidato_v06_A_aprovado.vil")
    b_path = os.path.join(outdir, "sofle_candidato_v06_B_design_v03.vil")
    c_path = os.path.join(outdir, "sofle_candidato_v06_C_conectado.vil")

    targets = [a_path, b_path, c_path]
    if args.out:
        targets.append(os.path.abspath(args.out))
    existing = [p for p in targets if os.path.exists(p)]
    if existing and not args.force:
        raise SystemExit(
            f"RECUSADO: arquivos de destino já existem ({', '.join(os.path.basename(p) for p in existing)}) "
            f"— use --force para sobrescrever."
        )

    # ---- candA: cópia byte-exata do aprovado
    shutil.copyfile(BASE, a_path)

    # ---- candB (parcial conservador: preserva L0..L6, incorpora L7..L9)
    base = json.loads(open(BASE, "r", encoding="utf-8").read())
    out = copy.deepcopy(base)
    out["macro"] = [[] for _ in range(16)]
    out["macro"][0] = base["macro"][0]  # M0 '!=' intocado
    pending, applied, macro_slots = [], [], {}

    for ds_lid, vil_slot in (("L7", 7), ("L8", 8), ("L9", 9)):
        if ds_lid not in cand:
            continue
        new_rows, mapa = ds_layer_to_electrical(cand[ds_lid])
        rows = out["layout"][vil_slot]
        for (r, c), origem in sorted(mapa.items()):
            cell = new_rows[r][c]
            if cell is None:
                continue
            write_cell(rows, r, c, cell, ds_lid, applied, pending, macro_slots, data)

    # macro slots determinísticos (ordem alfabética do nome do dataset → M1..M10)
    slot_index = {name: i + 1 for i, name in enumerate(sorted(macro_slots))}
    out["macro"] = [[] for _ in range(16)]
    out["macro"][0] = base["macro"][0]
    for name, i in slot_index.items():
        out["macro"][i] = [[op[0], op[1]] for op in macro_slots[name]]
    # resolve tokens @macro:<nome> → M<n> e fecha o registro aplicado
    for ap in applied:
        if ap.get("to") is None:  # macro refs
            for ds_lid in ("L7", "L8", "L9"):
                r, c = ap["pos"]
                cell = out["layout"][{"L7": 7, "L8": 8, "L9": 9}[ds_lid]][r][c]
                if isinstance(cell, str) and cell.startswith("@macro:"):
                    nm = cell[len("@macro:"):]
                    ap["to"] = f"M{slot_index[nm]}"
                    out["layout"][{"L7": 7, "L8": 8, "L9": 9}[ds_lid]][r][c] = f"M{slot_index[nm]}"

    text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    ksm_core.atomic_write(b_path, text.encode("utf-8"))

    # ---- candC (proposta conectada integral: camadas L0..L9 compostas DIRETAMENTE do dataset)
    out_c = copy.deepcopy(base)
    out_c["macro"] = [[] for _ in range(16)]
    out_c["macro"][0] = base["macro"][0]  # M0 '!=' intocado
    # 1. Tap dance 1: Undo no toque (LGUI(KC_Z)), Layer 7 (FUN) ao segurar
    out_c["tap_dance"][1] = ["LGUI(KC_Z)", "MO(7)", "KC_NO", "KC_NO", 175]

    pending_c, applied_c, macro_slots_c = [], [], {}
    for vil_slot in range(10):
        ds_lid = f"L{vil_slot}"
        if ds_lid not in cand:
            continue
        new_rows, mapa = ds_layer_to_electrical(cand[ds_lid])
        rows = out_c["layout"][vil_slot]
        for (r, c), origem in sorted(mapa.items()):
            cell = new_rows[r][c]
            if cell is None:
                continue
            write_cell(rows, r, c, cell, ds_lid, applied_c, pending_c, macro_slots_c, data)

    # macro slots determinísticos para candC (ordem alfabética do nome do dataset → M1..M10)
    slot_index_c = {name: i + 1 for i, name in enumerate(sorted(macro_slots_c))}
    for name, i in slot_index_c.items():
        out_c["macro"][i] = [[op[0], op[1]] for op in macro_slots_c[name]]
    for ap_item in applied_c:
        if ap_item.get("to") is None:
            for s_idx in range(10):
                r, c = ap_item["pos"]
                cell = out_c["layout"][s_idx][r][c]
                if isinstance(cell, str) and cell.startswith("@macro:"):
                    nm = cell[len("@macro:"):]
                    ap_item["to"] = f"M{slot_index_c[nm]}"
                    out_c["layout"][s_idx][r][c] = f"M{slot_index_c[nm]}"

    # preservação rigorosa de slots de encoder (4,5) e (9,5) em todas as 16 camadas
    for li in range(16):
        out_c["layout"][li][4][5] = base["layout"][li][4][5]
        out_c["layout"][li][9][5] = base["layout"][li][9][5]

    text_c = json.dumps(out_c, ensure_ascii=False, separators=(",", ":"))
    ksm_core.atomic_write(c_path, text_c.encode("utf-8"))

    if args.out:
        ksm_core.atomic_write(args.out, text_c.encode("utf-8"))

    # ---- preservação: campos não-alvo idênticos à base
    chk = {}
    for f in (a_path, b_path, c_path):
        d = json.load(open(f))
        chk[os.path.basename(f)] = all(
            json.dumps(d[k], ensure_ascii=False) == json.dumps(base[k], ensure_ascii=False)
            for k in ("uid", "encoder_layout", "layout_options", "vial_protocol", "via_protocol",
                      "combo", "key_override", "alt_repeat_key", "settings"))

    # ---- validação global: todo keycode escrito ∈ VALID_SET
    invalid = []
    for f_idx, vil_obj in enumerate((out, out_c)):
        tag = "candB" if f_idx == 0 else "candC"
        for li in range(len(vil_obj["layout"])):
            for row in vil_obj["layout"][li]:
                for cell in row:
                    for k in keycode_names_in(str(cell)):
                        if k not in VALID_SET:
                            invalid.append(f"{tag}:L{li}:{k}")
        for mi, m in enumerate(vil_obj["macro"]):
            for op in m:
                if isinstance(op, list) and op[0] == "tap":
                    if not re.fullmatch(r"(?:KC|RGB)_[A-Z0-9_]+", op[1]) or op[1] not in VALID_SET:
                        invalid.append(f"{tag}:macro{mi}:tap:{op[1]}")

    print(json.dumps({
        "candA": a_path, "candA_sha256": ksm_core.file_hash(a_path),
        "candB": b_path, "candB_sha256": ksm_core.file_hash(b_path),
        "candC": c_path, "candC_sha256": ksm_core.file_hash(c_path),
        "preservação": chk,
        "macro_slots": {i + 1: [o[1] for o in macro_slots[n]] for i, n in enumerate(sorted(macro_slots))},
        "invalid_keycodes": invalid,
        "aplicados": applied,
        "pendências_candB": pending,
        "pendências_candC": pending_c,
        "pendências": pending_c,
        "funções_desativadas_candC": [
            {"layer": p["layer"], "pos": p["pos"], "funcao": p["dataset"], "motivo": p["por_que"]}
            for p in pending_c
        ],
        "uid": out["uid"],
    }, ensure_ascii=False, indent=1))
    if invalid:
        sys.exit(2)


if __name__ == "__main__":
    main()
