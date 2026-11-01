#!/usr/bin/env python3
"""T10+ — revisão de keymaps: correspondência FÍSICA slot-a-slot, macros Vial válidas,
classificação correta de brilho (KC_BRID/BRIU), e regra de slots protegidos.
Cobre o gap da rodada 1 (testes só estruturais) apontado no review do usuário.
"""
import json
import os
import re
import subprocess
import sys

from conftest import GEN, SOFLE_A, SOFLE_B, SOFLE_C, SOFLE_HOMOLOGADO, APP


def sha256(p):
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


# ---------------- fórmula de mapeamento INDEPENDENTE (redireve a regra, não importa o compositor)
def ds_to_electrical_expected(ds_layer):
    """(matrix 4x12, thumbs 10) → 10x6 (esq direto; dir reverso 11-c; thumbs dir→int esq; int→dir esq)."""
    mx, th = ds_layer["matrix"], ds_layer["thumbs"]
    out = [[None] * 6 for _ in range(10)]
    for r in range(4):
        for c in range(6):
            out[r][c] = mx[r][c]
            out[r + 5][c] = mx[r][11 - c]
    for c in range(5):
        out[4][c] = th[c]
        out[9][c] = th[9 - c]
    return out


def impl_to_vil_expected(impl, slot_index):
    """tradução mínima usada APENAS pelo oráculo do teste (mesma política do compositor)."""
    if not impl:
        return "KC_TRNS"
    if re.fullmatch(r"macro_strudel_[a-z_]+", impl):
        return f"M{slot_index[impl[len('macro_'):]]}"
    return impl  # demais formas: compositor repassa o string (a validação de validade é T11/T12)


def test_t10_sofle_b_correspondencia_fisica_slot_a_slot(dataset):
    """CADA slot exportado (58 posições × 3 camadas de design) tem origem registrada no dataset."""
    b = json.load(open(SOFLE_B, encoding="utf-8"))
    cand = dataset["profiles"]["candidato_teste"]["sofle"]["layers"]
    slot_index = {n: i + 1 for i, n in enumerate(sorted(
        m["name"] for m in dataset["macros"] if m["name"].startswith("strudel_")))}
    ds_lids = ["L7", "L8", "L9"]
    diffs = []
    for ds_lid, vil_slot in zip(ds_lids, (7, 8, 9)):
        esperado_sm = ds_to_electrical_expected(cand[ds_lid])
        for r in range(10):
            for c in range(6):
                if (r, c) in ((4, 5), (9, 5)):
                    continue  # proveniência de encoder: comparado em T12
                exp_cell = esperado_sm[r][c]
                exp = impl_to_vil_expected(exp_cell.get("impl_qmk"), slot_index)
                got = b["layout"][vil_slot][r][c]
                if got != exp:
                    diffs.append((ds_lid, [r, c], exp, got))
    assert not diffs, f"dispatch físico divergente em {len(diffs)} slots: {diffs[:6]}"


def test_t10_sofle_b_posicoes_anticas_agulha():
    """Posições críticas verificadas manualmente (F1..F12, navegação, média, strudel)."""
    b = json.load(open(SOFLE_B, encoding="utf-8"))
    L7, L8, L9 = b["layout"][7], b["layout"][8], b["layout"][9]
    assert L7[1][:6] == ["KC_F1", "KC_F2", "KC_F3", "KC_F4", "KC_F5", "KC_F6"]
    assert L7[6][:6] == ["KC_F12", "KC_F11", "KC_F10", "KC_F9", "KC_F8", "KC_F7"]
    assert L7[2][:6] == ["KC_TAB", "KC_PSCR", "KC_PAUS", "KC_INS", "KC_HOME", "KC_PGUP"]
    assert L7[7][:6] == ["KC_APP", "KC_RCTL", "KC_RALT", "KC_RGUI", "KC_RSFT", "KC_NO"]
    # L8 média: direita de brilho com KC_BRIGHTNESS (não KC_NO)
    assert L8[8][4] == "KC_BRIU" and L8[8][5] == "KC_BRID"
    assert L8[7][:5] == ["KC_NO", "KC_MSTP", "KC_MNXT", "KC_MPLY", "KC_MPRV"]
    assert L8[6][1:5] == ["KC_NO", "KC_VOLD", "KC_VOLU", "KC_MUTE"]
    # L9 strudel: apostilhas de macro nos botões do dataset (cada nome tem slot determinístico)
    slot_index = {"strudel_delay": 1, "strudel_fast": 2, "strudel_mute": 3, "strudel_note": 4,
                  "strudel_orbit": 5, "strudel_pat": 6, "strudel_room": 7, "strudel_s": 8,
                  "strudel_slow": 9, "strudel_stack": 10}
    assert L9[2][:6] == ["KC_TAB", "M8", "M4", "M3", "M6", "M10"]
    assert L9[3][:6] == ["KC_LSFT", "M9", "M2", "M7", "M1", "M5"]
    assert L9[1][:6] == ["LGUI(KC_SLSH)", "LCTL(KC_ENT)", "LCTL(KC_DOT)",
                         "LGUI(KC_MINS)", "LGUI(KC_PLUS)", "LGUI(KC_0)"]


def test_t10_sofle_b_macros_formato_vial_valido():
    """M0 intocado; M1..10: [[op,arg]] só com TAP KC_* válidos (sem letras rasas tipo 'A')."""
    homolog = json.load(open(SOFLE_HOMOLOGADO, encoding="utf-8"))
    b = json.load(open(SOFLE_B, encoding="utf-8"))
    assert b["macro"][0] == homolog["macro"][0] == [["text", "!="]]
    bad = []
    for i, m in enumerate(b["macro"][1:11], start=1):
        for op in m:
            if not isinstance(op, list) or len(op) != 2 or op[0] != "tap":
                bad.append((i, op))
                continue
            if not re.fullmatch(r"KC_[A-Z0-9_]+|RGB_[A-Z0-9_]+", op[1]):
                bad.append((i, op))
    assert not bad, f"macro op inválida no formato Vial: {bad[:5]}"


def test_t10_sofle_b_sem_codigos_fantasma():
    raw = open(SOFLE_B, encoding="utf-8").read()
    for forbidden in ("KC_LPAREN", '"tap", "A"', '"tap", "C"', '"tap", "K"'):
        assert forbidden not in raw, f"código errado ainda presente: {forbidden}"


def test_t11_todo_keycode_em_valid_set(dataset):
    """Validação abrangente de 100% dos keycodes QMK:
    - Candidato B: células dos slots 7/8/9 e macros 1..10.
    - Candidato C: todas as 16 camadas (todas as 580 posições de L0..L9 e camadas extras) e macros 1..10.
    Todo keycode KC_*/RGB_* deve pertencer ao conjunto VALID_SET oficial QMK + homologado.
    """
    try:
        from compose_sofle_candidato import VALID_SET
    except ImportError:
        from generators.compose_sofle_candidato import VALID_SET

    # 1. Candidato B (slots de design 7, 8, 9 e macros)
    b = json.load(open(SOFLE_B, encoding="utf-8"))
    bad_b = []
    for s in (7, 8, 9):
        for row in b["layout"][s]:
            for c in row:
                for k in re.findall(r"(?:KC|RGB)_[A-Z0-9_]+", str(c)):
                    if k not in VALID_SET:
                        bad_b.append((s, k))
    for i, m in enumerate(b["macro"]):
        for op in m:
            if isinstance(op, list) and op[0] == "tap" and op[1] not in VALID_SET:
                bad_b.append(("macro_b", i, op[1]))
    assert not bad_b, f"Candidato B com keycodes fora do VALID_SET: {bad_b[:6]}"

    # 2. Candidato C (todas as 16 camadas / todas as 580 posições funcionais L0..L9 + macros)
    c = json.load(open(SOFLE_C, encoding="utf-8"))
    bad_c = []
    for li, lay in enumerate(c["layout"]):
        for row in lay:
            for cell in row:
                for k in re.findall(r"(?:KC|RGB)_[A-Z0-9_]+", str(cell)):
                    if k not in VALID_SET:
                        bad_c.append((li, k))
    for i, m in enumerate(c["macro"]):
        for op in m:
            if isinstance(op, list) and op[0] == "tap" and op[1] not in VALID_SET:
                bad_c.append(("macro_c", i, op[1]))
    assert not bad_c, f"Candidato C com keycodes fora do VALID_SET: {bad_c[:6]}"


def test_t12_slots_protegidos_e_uid_e_preservacao():
    a = json.load(open(SOFLE_A, encoding="utf-8"))
    b = json.load(open(SOFLE_B, encoding="utf-8"))
    homolog = json.load(open(SOFLE_HOMOLOGADO, encoding="utf-8"))
    uid = "12888985424971681029"
    assert str(b["uid"]) == str(a["uid"]) == str(homolog["uid"]) == uid
    assert type(b["uid"]) is type(homolog["uid"]), "tipo do uid deve preservar o homologado"
    # M0 e demais estruturas idênticas; encoders (4,5)/(9,5) intocados em toda camada
    for k in ("encoder_layout", "layout_options", "vial_protocol", "via_protocol",
              "tap_dance", "combo", "key_override", "alt_repeat_key", "settings"):
        assert b[k] == homolog[k], k
    for li in range(16):
        for slot in ((4, 5), (9, 5)):
            r, c = slot
            assert b["layout"][li][r][c] == homolog["layout"][li][r][c], (li, slot)
    # slots 0..6 e 10..15 e ids 3..6/10..15 byte-igual ao homologado
    for li in list(range(0, 7)) + list(range(10, 16)):
        assert b["layout"][li] == homolog["layout"][li], f"camada não-alvo {li} alterada"
    assert len(b["macro"]) == len(homolog["macro"]) == 16


def test_t14_corne_candidato_v06_cabecalho_atual(dataset):
    """candidato Corne regenerado: hash canônico do dataset atual no cabeçalho + descrição D1 corrigida."""
    import ksm_core
    CORNE_V6 = os.path.join(GEN, "candidates", "corne_candidato_v06.keymap")
    txt = open(CORNE_V6, encoding="utf-8").read()
    ch = ksm_core.canonical_hash(dataset)
    assert ch in txt, f"cabeçalho deve conter o hash canônico ATUAL {ch[:16]}…"
    assert "c63b70e4" not in txt, "hash obsoleto (pré-fix-parity) não pode reaparecer"
    assert "Shift esquerdo + Esc/L9" in txt, "descrição D1 corrigida do combo Caps ausente"
    assert "Ambos os Shifts" not in txt, "descrição antiga do combo Caps não pode reaparecer"
    assert "&kp CAPS" in txt and 'key-positions' in txt


def test_t13_determinismo_do_compositor(tmp_path):
    c1, c2 = str(tmp_path / "d1"), str(tmp_path / "d2")
    for o in (c1, c2):
        os.makedirs(o, exist_ok=True)
    p1 = subprocess.run(["python3", os.path.join(GEN, "compose_sofle_candidato.py"), "--outdir", c1],
                        capture_output=True, text=True, cwd=os.path.join(GEN, "..", ".."))
    p2 = subprocess.run(["python3", os.path.join(GEN, "compose_sofle_candidato.py"), "--outdir", c2],
                        capture_output=True, text=True, cwd=os.path.join(GEN, "..", ".."))
    assert p1.returncode == 0 and p2.returncode == 0, (p1.stderr, p2.stderr)
    for name in ("sofle_candidato_v06_A_aprovado.vil", "sofle_candidato_v06_B_design_v03.vil", "sofle_candidato_v06_C_conectado.vil"):
        assert sha256(os.path.join(c1, name)) == sha256(os.path.join(c2, name)), name


def test_t14_sofle_compositor_anti_sobrescrita(tmp_path):
    """O compositor deve RECUSAR sobrescrever arquivos existentes sem a flag --force."""
    out_dir = str(tmp_path / "target")
    os.makedirs(out_dir, exist_ok=True)
    p1 = subprocess.run(["python3", os.path.join(GEN, "compose_sofle_candidato.py"), "--outdir", out_dir],
                        capture_output=True, text=True, cwd=os.path.join(GEN, "..", ".."))
    assert p1.returncode == 0, p1.stderr
    # Segunda execução sem --force -> deve falhar com mensagem RECUSADO
    p2 = subprocess.run(["python3", os.path.join(GEN, "compose_sofle_candidato.py"), "--outdir", out_dir],
                        capture_output=True, text=True, cwd=os.path.join(GEN, "..", ".."))
    assert p2.returncode != 0
    assert "RECUSADO: arquivos de destino já existem" in (p2.stdout + p2.stderr)
    # Terceira execução com --force -> deve ter sucesso
    p3 = subprocess.run(["python3", os.path.join(GEN, "compose_sofle_candidato.py"), "--outdir", out_dir, "--force"],
                        capture_output=True, text=True, cwd=os.path.join(GEN, "..", ".."))
    assert p3.returncode == 0, p3.stderr


def test_t15_sofle_c_conteudo_real_todas_camadas(dataset):
    """Verificação estática de conteúdo representativo crítico em todas as camadas L0..L9 do Candidato C.

    NOTA DE ESCOPO: Este teste audita posições-chave e representativas de cada camada
    (ex.: comandos Live em L1, setas/mouse em L3, numpad em L5, seletores em L6, etc.),
    e NÃO as 580 posições totais individualmente. A completude e validade sintática global
    de todas as 580 células são auditadas pelo test_t11 (VALID_SET).
    """
    c = json.load(open(SOFLE_C, encoding="utf-8"))
    assert len(c["layout"]) == 16, "Candidato C deve ter 16 camadas preservadas do .vil"
    assert str(c["uid"]) == "12888985424971681029", "UID exato preservado no candidato C"

    # L0 BASE: QWERTY + Esc/Strudel em (0,0) + Right Shift em (8,0)
    assert c["layout"][0][0][0] == "LT9(KC_ESC)", "Esc/Strudel em (0,0)"
    assert c["layout"][0][8][0] == "KC_RSFT", "Right Shift restaurado em (8,0)"
    assert c["layout"][0][1][:4] == ["KC_TAB", "KC_Q", "KC_W", "KC_E"]

    # L1 LIVE: contém comandos de Ableton Live (não símbolos/F-keys)
    assert c["layout"][1][1][:3] == ["KC_TAB", "LALT(LGUI(KC_B))", "KC_F10"], "Sess/Arr, Browser, VoltarArr em L1"
    assert c["layout"][1][2][:3] == ["KC_ESC", "KC_O", "KC_S"], "Esc, Metrônomo, Solo em L1"
    assert c["layout"][1][4][4] == "KC_SPC", "Play/Stop no dedão de L1"
    assert c["layout"][1][0][0] == "TO(0)", "SAIR para L0 em (0,0)"

    # L2 NAV: navegação e setas + abas colchetes validados + dual activation
    assert c["layout"][2][8][2] == "LGUI(LSFT(KC_RBRACKET))", "Aba Próxima em L2 row 8 col 2"
    assert c["layout"][2][8][3] == "LGUI(LSFT(KC_LBRACKET))", "Aba Anterior em L2 row 8 col 3"
    assert c["layout"][2][9][4] == "MO(6)", "Enter ativa L6 SYSTEM em L2 (dual activation)"

    # L3 MOUSE: contém comandos de mouse (não numpad)
    row_mouse = c["layout"][3][7]
    assert "KC_MS_UP" in row_mouse and "KC_MS_DOWN" in row_mouse and "KC_MS_LEFT" in row_mouse and "KC_MS_RIGHT" in row_mouse
    assert c["layout"][3][9][4] == "KC_BTN1", "Clique esquerdo no dedão L3"
    assert c["layout"][3][9][3] == "KC_BTN2", "Clique direito no dedão L3"
    assert c["layout"][3][9][2] == "KC_BTN3", "Clique meio no dedão L3"

    # L4 SYM: símbolos e ativação de SYSTEM
    assert c["layout"][4][4][4] == "MO(6)", "Space ativa L6 SYSTEM em L4 (dual activation)"

    # L5 NUM: teclado numérico
    assert c["layout"][5][2][2:5] == ["KC_P4", "KC_P5", "KC_P6"], "Numpad 4-5-6 em L5"

    # L6 SYSTEM: seletores LIVE TO(1) e STRUDEL TO(9)
    assert c["layout"][6][7][1] == "TO(1)", "TO(1) para LIVE na L6"
    assert c["layout"][6][7][0] == "TO(9)", "TO(9) para STRUDEL na L6"

    # L7 FUN: teclas F1..F12
    assert c["layout"][7][1][:6] == ["KC_F1", "KC_F2", "KC_F3", "KC_F4", "KC_F5", "KC_F6"]

    # L8 MEDIA: volume e controles de mídia
    assert c["layout"][8][6][2:5] == ["KC_VOLD", "KC_VOLU", "KC_MUTE"]

    # L9 STRUDEL: macros musicais
    assert c["layout"][9][2][1] == "M8" and c["layout"][9][2][2] == "M4"


def test_t16_sofle_c_modificadores_preservados():
    """Candidato C preserva RIGOROSAMENTE todos os modificadores físicos e dedicados em L0."""
    c = json.load(open(SOFLE_C, encoding="utf-8"))
    l0 = c["layout"][0]

    # Modificadores de canto / linhas principais
    assert l0[3][0] == "KC_LSFT", "Left Shift na linha 3 col 0"
    assert l0[8][0] == "KC_RSFT", "Right Shift restaurado na linha 8 col 0"
    assert l0[2][0] == "KC_LCTL", "Left Control na linha 2 col 0 (posição Caps/Ctrl)"

    # Dedões esquerdos: (4,0) Alt, (4,1) Cmd dedicado, (4,2) Media, (4,3) Delete/Mouse, (4,4) Space/Nav
    assert l0[4][0] == "KC_LALT", "Dedão esquerdo externo: Alt"
    assert l0[4][1] == "KC_LGUI", "Dedão esquerdo: CMD DEDICADO PRESERVADO"
    assert l0[4][2] == "MO(8)", "Dedão esquerdo: MEDIA hold"
    assert l0[4][3] == "LT3(KC_DEL)", "Dedão esquerdo: Delete/MOUSE"
    assert l0[4][4] == "LT2(KC_SPACE)", "Dedão esquerdo interno: Space/NAV"
    assert l0[4][5] == "KC_MUTE", "Encoder esquerdo preservado"

    # Dedões direitos: (9,4) Enter/Sym, (9,3) Bksp/Num, (9,2) Undo/Fun, (9,1) Cmd dedicado, (9,0) Ctrl
    assert l0[9][4] == "LT4(KC_ENTER)", "Dedão direito interno: Enter/SYM"
    assert l0[9][3] == "LT5(KC_BSPACE)", "Dedão direito: Bksp/NUM"
    assert l0[9][2] == "TD(1)", "Dedão direito: Tap Dance 1 (Undo tap / FUN hold)"
    assert l0[9][1] == "KC_RGUI", "Dedão direito: CMD DEDICADO PRESERVADO"
    assert l0[9][0] == "KC_RCTL", "Dedão direito externo: Ctrl"
    assert l0[9][5] == "KC_HOME", "Encoder direito preservado"

    # Home Row Mods
    hrm_expected = {
        (2, 1): "LCTL_T(KC_A)", (2, 2): "LALT_T(KC_S)", (2, 3): "LGUI_T(KC_D)", (2, 4): "LSFT_T(KC_F)",
        (7, 4): "RSFT_T(KC_J)", (7, 3): "RGUI_T(KC_K)", (7, 2): "RALT_T(KC_L)", (7, 1): "RCTL_T(KC_SCOLON)"
    }
    for (r, col), exp in hrm_expected.items():
        assert l0[r][col] == exp, f"HRM em ({r},{col}) divergiu: esperado {exp}, obtido {l0[r][col]}"


def test_t17_sofle_c_grafo_navegacao_camadas():
    """Verificação estática de keycodes de transição de camadas do candidato C (L0..L9).

    NOTA DE ESCOPO: Este teste confere keycodes em posições fixas de matriz (ex.: LT, MO, TO, TD).
    Ele NÃO simula dinamicamente a máquina de estados de firmware (pressionar, segurar,
    interromper e soltar teclas) e NÃO substitui a validação física e interativa de hardware.
    """
    c = json.load(open(SOFLE_C, encoding="utf-8"))

    # L0 -> L1 (via L6 SYSTEM TO(1)), L1 -> L0 via TO(0)
    assert c["layout"][6][7][1] == "TO(1)"
    assert c["layout"][1][0][0] == "TO(0)" and c["layout"][1][4][3] == "TO(0)"

    # L0 -> L2 (via LT2 no dedão esquerdo interno (4,4))
    assert c["layout"][0][4][4] == "LT2(KC_SPACE)"

    # L0 -> L3 (via LT3 no dedão esquerdo (4,3))
    assert c["layout"][0][4][3] == "LT3(KC_DEL)"

    # L0 -> L4 (via LT4 no dedão direito interno (9,4))
    assert c["layout"][0][9][4] == "LT4(KC_ENTER)"

    # L0 -> L5 (via LT5 no dedão direito (9,3))
    assert c["layout"][0][9][3] == "LT5(KC_BSPACE)"

    # L0 -> L6 SYSTEM via dupla ativação:
    # Segurar NAV (dedão 4,4) + Enter em L2 (dedão 9,4) -> MO(6)
    assert c["layout"][2][9][4] == "MO(6)"
    # Segurar SYM (dedão 9,4) + Space em L4 (dedão 4,4) -> MO(6)
    assert c["layout"][4][4][4] == "MO(6)"

    # L0 -> L7 (via TD1 no dedão direito (9,2))
    assert c["layout"][0][9][2] == "TD(1)"
    assert c["tap_dance"][1][:2] == ["LGUI(KC_Z)", "MO(7)"]

    # L0 -> L8 (via MO(8) no dedão esquerdo (4,2))
    assert c["layout"][0][4][2] == "MO(8)"

    # L0 -> L9 (via LT9 no Esc (0,0) ou TO(9) em L6 (7,0)); L9 -> L0 via TO(0)
    assert c["layout"][0][0][0] == "LT9(KC_ESC)"
    assert c["layout"][6][7][0] == "TO(9)"
    assert c["layout"][9][4][3] == "TO(0)" and c["layout"][9][8][0] == "TO(0)"
    assert c["layout"][9][0][0] == "TO(0)", "Esc físico na L9 retorna a L0 via TO(0)"


def test_t18_auditoria_acessibilidade_grafo_bfs_candidato_b_vs_c():
    """Auditoria estrita de acessibilidade de camadas baseada em BFS a partir de L0:
    - Constrói o grafo direcionado de transições entre camadas (incluindo TD dinâmico, combos e tri-layers).
    - Candidato B: preserva L0..L6 intactas, logo L7..L9 são órfãs (inacessíveis a partir de L0).
    - Candidato C: todas as 10 camadas de design (L0..L9) são alcançáveis a partir de L0 via BFS.
    - Saídas de camadas persistentes: nenhuma camada de L0..L9 é armadilha (trap layer).
    """
    from ksm_core import audit_layer_reachability

    cand_b = json.load(open(SOFLE_B, encoding="utf-8"))
    cand_c = json.load(open(SOFLE_C, encoding="utf-8"))

    # 1. Candidato B: L7, L8, L9 são comprovadamente inalcançáveis a partir de L0
    res_b = audit_layer_reachability(cand_b, "sofle")
    assert "L0" in res_b["reachable"]
    for lid in ("L7", "L8", "L9"):
        assert lid in res_b["unreachable"], f"Candidato B não deve alcançar {lid} a partir de L0"
        assert lid not in res_b["reachable"], f"{lid} não pode estar no conjunto alcançável do Candidato B"

    # 2. Candidato C: L0..L9 são 100% alcançáveis a partir de L0 via BFS
    res_c = audit_layer_reachability(cand_c, "sofle")
    for i in range(10):
        lid = f"L{i}"
        assert lid in res_c["reachable"], f"Candidato C deve alcançar {lid} a partir de L0 via BFS"
        assert lid not in res_c["unreachable"], f"{lid} não pode constar como inalcançável no Candidato C"

    # 3. Verificação de armadilhas (Trap Layers):
    # Nenhuma camada do Candidato C pode ser armadilha (todas que possuem entrada persistente têm saída para L0)
    assert len(res_c["trap_layers"]) == 0, f"Candidato C possui camadas armadilha sem retorno a L0: {res_c['trap_layers']}"


def test_t19_auditoria_acessibilidade_casos_negativos_e_falsos_positivos():
    """Validação contra os 5 casos críticos de falsos positivos apontados no review:
    1. Contraexemplo do revisor (10 camadas isoladas com self-loops e TO(0) para L0, mas L0 fechada):
       A condição len(incoming) > 0 passaria erroneamente; o BFS DEVE identificar L1..L9 como inalcançáveis!
    2. Ciclo isolado entre camadas (L3 <-> L4, desconectado de L0):
       Ambas possuem incoming > 0, mas o BFS DEVE marcar ambas como inalcançáveis!
    3. Cadeia isolada (L5 -> L6, onde L5 é inalcançável):
       L6 possui incoming > 0 de L5, mas o BFS DEVE marcar L5 e L6 como inalcançáveis!
    4. Resolução dinâmica de Tap Dance:
       TD(1) sem definição -> L7 inalcançável; TD(1) com MO(7) -> L7 alcançável.
    5. Isolamento nativo ZMK vs QMK:
       Corne com &none no ZMK e MO(1) no QMK -> L1 inalcançável (não vaza keycode do outro teclado).
    """
    from ksm_core import audit_layer_reachability

    # Caso 1: O contraexemplo exato do revisor (10 camadas com self-loop e TO(0))
    # L0 tem apenas teclas normais; L1..L9 têm TO(i) para si mesmas e TO(0) para L0.
    layers_contraexemplo = {
        "L0": {"matrix": [["KC_A"]], "thumbs": []}
    }
    for i in range(1, 10):
        layers_contraexemplo[f"L{i}"] = {
            "matrix": [[f"TO({i})", "TO(0)"]],
            "thumbs": []
        }
    res1 = audit_layer_reachability(layers_contraexemplo, "sofle")
    assert res1["reachable"] == ["L0"], "FALSO POSITIVO: Somente L0 pode ser alcançada no contraexemplo do revisor!"
    for i in range(1, 10):
        assert f"L{i}" in res1["unreachable"], f"L{i} deveria ser inalcançável no contraexemplo do revisor!"

    # Caso 2: Ciclo isolado entre camadas (L3 <-> L4), enquanto L0 alcança L1 e L2
    layers_ciclo = {
        "L0": {"matrix": [["MO(1)"]], "thumbs": []},
        "L1": {"matrix": [["MO(2)"]], "thumbs": []},
        "L2": {"matrix": [["KC_TRNS"]], "thumbs": []},
        "L3": {"matrix": [["MO(4)"]], "thumbs": []},
        "L4": {"matrix": [["MO(3)"]], "thumbs": []},
    }
    res2 = audit_layer_reachability(layers_ciclo, "sofle")
    assert set(res2["reachable"]) == {"L0", "L1", "L2"}
    assert set(res2["unreachable"]) == {"L3", "L4"}, "FALSO POSITIVO: Ciclo L3<->L4 isolado de L0 deve ser inalcançável!"

    # Caso 3: Cadeia isolada (L5 -> L6)
    layers_cadeia = {
        "L0": {"matrix": [["KC_A"]], "thumbs": []},
        "L5": {"matrix": [["MO(6)"]], "thumbs": []},
        "L6": {"matrix": [["KC_TRNS"]], "thumbs": []},
    }
    res3 = audit_layer_reachability(layers_cadeia, "sofle")
    assert res3["reachable"] == ["L0"]
    assert set(res3["unreachable"]) == {"L5", "L6"}, "FALSO POSITIVO: L6 não pode ser alcançada via L5 inalcançável!"

    # Caso 4: Resolução dinâmica de Tap Dance (Sofle)
    layers_td = {
        "L0": {"matrix": [["TD(1)"]], "thumbs": []},
        "L7": {"matrix": [["KC_TRNS"]], "thumbs": []},
    }
    # Sem definição de tap_dance -> inalcançável
    res4_vazio = audit_layer_reachability(layers_td, "sofle", {"tap_dance": []})
    assert "L7" in res4_vazio["unreachable"]
    assert "L7" not in res4_vazio["reachable"]
    # Com definição dinâmica de tap_dance -> alcançável
    res4_definido = audit_layer_reachability(layers_td, "sofle", {"tap_dance": [[], ["LGUI(KC_Z)", "MO(7)"]]})
    assert "L7" in res4_definido["reachable"]
    assert "L7" not in res4_definido["unreachable"]

    # Caso 5: Isolamento nativo ZMK vs QMK (Corne)
    layers_corne_isolamento = {
        "L0": {"matrix": [[{"impl_zmk": "&none", "impl_qmk": "MO(1)"}]], "thumbs": []},
        "L1": {"matrix": [[{"impl_zmk": "&none", "impl_qmk": "KC_TRNS"}]], "thumbs": []},
    }
    res5 = audit_layer_reachability(layers_corne_isolamento, "corne")
    assert "L1" in res5["unreachable"]
    assert "L1" not in res5["reachable"]

    # Caso 6: Tri-layer onde pré-requisitos usam TO() excludente (L2 e L4 entram por TO)
    # L0 -> TO(2) e TO(4). Ambas entram separadamente, mas TO() desliga as outras camadas.
    # A simultaneidade L2 + L4 é IMPOSSÍVEL -> L6 DEVE ser marcada como unproven_conditionals e NÃO alcançada!
    layers_tri_to = {
        "L0": {"matrix": [["TO(2)", "TO(4)"]], "thumbs": []},
        "L2": {"matrix": [["KC_A", "KC_B"]], "thumbs": []},
        "L4": {"matrix": [["KC_C", "KC_D"]], "thumbs": []},
        "L6": {"matrix": [["KC_SYSTEM"]], "thumbs": []},
    }
    res6 = audit_layer_reachability(layers_tri_to, "sofle", {"tri_layers": [{"lower": 2, "raise": 4, "adjust": 6}]})
    assert "L6" not in res6["reachable"], "FALSO POSITIVO: L6 não pode ser alcançada se L2 e L4 usam TO() excludente!"
    assert any(u["target"] == "L6" for u in res6["unproven_conditionals"]), "L6 deve constar em unproven_conditionals"

    # Caso 7: Tri-layer com acessos momentâneos MO() em posições distintas e transparência
    # L0 -> MO(2) na pos 0 e MO(4) na pos 1. Ambas coexistem -> L6 alcançada e comprovada!
    layers_tri_mo = {
        "L0": {"matrix": [["MO(2)", "MO(4)"]], "thumbs": []},
        "L2": {"matrix": [["KC_TRNS", "KC_TRNS"]], "thumbs": []},
        "L4": {"matrix": [["KC_TRNS", "KC_TRNS"]], "thumbs": []},
        "L6": {"matrix": [["KC_SYSTEM"]], "thumbs": []},
    }
    res7 = audit_layer_reachability(layers_tri_mo, "sofle", {"tri_layers": [{"lower": 2, "raise": 4, "adjust": 6}]})
    assert "L6" in res7["reachable"], "L6 deve ser alcançada quando L2 e L4 possuem ativação momentânea simultânea"
    assert any(p["target"] == "L6" for p in res7["proven_conditionals"]), "L6 deve constar em proven_conditionals"


def test_t20_auditoria_saidas_ativacoes_persistentes_e_trap_layers():
    """Validação contra camadas armadilha (trap layers):
    1. Camada ativada por TO(1) sem saída para L0 -> DEVE ser classificada como trap_layer.
    2. Camada com ciclo fechado entre camadas secundárias sem retorno para L0 -> DEVE ser trap_layer.
    3. Camada ativada por TO(1) com saída direta via TO(0) -> NÃO é trap_layer.
    4. Camada ativada por TO(1) com saída indireta (L1 -> TO(2) -> TO(0)) -> NÃO é trap_layer.
    5. Ativação momentânea MO(1) sem TO(0) -> NÃO é trap_layer (soltar a tecla retorna à base).
    """
    from ksm_core import audit_layer_reachability

    # 1. Armadilha direta: L0 entra em L1 via TO(1); L1 não possui saída para L0
    layers_trap1 = {
        "L0": {"matrix": [["TO(1)"]], "thumbs": []},
        "L1": {"matrix": [["KC_A", "KC_B"]], "thumbs": []},
    }
    res1 = audit_layer_reachability(layers_trap1, "sofle")
    assert "L1" in res1["reachable"]
    assert "L1" in res1["trap_layers"], "L1 deve ser detectada como trap_layer (sem saída para L0)"

    # 2. Armadilha em ciclo: L0 -> TO(1); L1 -> TO(2); L2 -> TO(1); nenhuma alcança L0
    layers_trap_ciclo = {
        "L0": {"matrix": [["TO(1)"]], "thumbs": []},
        "L1": {"matrix": [["TO(2)"]], "thumbs": []},
        "L2": {"matrix": [["TO(1)"]], "thumbs": []},
    }
    res2 = audit_layer_reachability(layers_trap_ciclo, "sofle")
    assert "L1" in res2["trap_layers"] and "L2" in res2["trap_layers"], "Ciclo isolado de L0 deve ser classificado como trap_layer"

    # 3. Saída direta válida: L1 possui TO(0)
    layers_ok_direto = {
        "L0": {"matrix": [["TO(1)"]], "thumbs": []},
        "L1": {"matrix": [["TO(0)"]], "thumbs": []},
    }
    res3 = audit_layer_reachability(layers_ok_direto, "sofle")
    assert len(res3["trap_layers"]) == 0, "L1 com TO(0) não pode ser classificada como trap_layer"

    # 4. Saída indireta válida: L1 -> TO(2) -> TO(0)
    layers_ok_indireto = {
        "L0": {"matrix": [["TO(1)"]], "thumbs": []},
        "L1": {"matrix": [["TO(2)"]], "thumbs": []},
        "L2": {"matrix": [["TO(0)"]], "thumbs": []},
    }
    res4 = audit_layer_reachability(layers_ok_indireto, "sofle")
    assert len(res4["trap_layers"]) == 0, "L1 com saída indireta para L0 não pode ser trap_layer"

    # 5. Ativação momentânea (MO): não prende o usuário
    layers_mo = {
        "L0": {"matrix": [["MO(1)"]], "thumbs": []},
        "L1": {"matrix": [["KC_A"]], "thumbs": []},
    }
    res5 = audit_layer_reachability(layers_mo, "sofle")
    assert len(res5["trap_layers"]) == 0, "Ativação momentânea MO() não constitui trap layer"

    # 6. Saída por alternância TG(1) com transparência na mesma tecla:
    # L0 entra em L1 via TG(1) na pos 0. Em L1, pos 0 é KC_TRNS -> pressionar desliga a camada!
    # NÃO deve produzir falso alerta de armadilha!
    layers_tg_trns = {
        "L0": {"matrix": [["TG(1)"]], "thumbs": []},
        "L1": {"matrix": [["KC_TRNS"]], "thumbs": []},
    }
    res6 = audit_layer_reachability(layers_tg_trns, "sofle")
    assert "L1" in res6["toggle_exit_layers"], "L1 com TG(1) e KC_TRNS deve ser reconhecida em toggle_exit_layers"
    assert "L1" not in res6["trap_layers"], "FALSO ALERTA: camada ativada por TG() com tecla transparente desliga por alternância!"

    # 7. Camada ativada por TG(1) com a tecla física bloqueada em L1 (sem KC_TRNS e sem TG) e sem TO(0):
    # O usuário não consegue alternar de volta nem sair -> DEVE ser classificada como trap_layer!
    layers_tg_bloqueado = {
        "L0": {"matrix": [["TG(1)"]], "thumbs": []},
        "L1": {"matrix": [["KC_NO"]], "thumbs": []},
    }
    res7 = audit_layer_reachability(layers_tg_bloqueado, "sofle")
    assert "L1" in res7["trap_layers"], "L1 com tecla de alternância bloqueada e sem TO(0) deve ser trap_layer"


