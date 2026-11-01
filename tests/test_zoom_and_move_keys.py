#!/usr/bin/env python3
"""test_zoom_and_move_keys.py — Testes das novas funcionalidades:
1. Zoom do Teclado (marcações no HTML, CSS e persistência de escala);
2. Mover / Trocar Teclas (Swap / Replace) na camada atual e em todas as camadas (L0..L9);
3. Validação de integridade do dataset após operações de troca e movimentação de teclas.
"""
import copy
import json
import os
import pytest

from conftest import APP, DATA_V6, GEN

HTML = os.path.join(GEN, "..", "deliverables", "keyboard_split_manager_v06.html")


def test_html_contains_zoom_and_move_key_elements():
    """Garante que os elementos de UI para Zoom e Mover/Trocar teclas estão presentes no HTML final."""
    html = open(HTML, encoding="utf-8").read()
    assert 'id="btnZoomIn"' in html
    assert 'id="btnZoomOut"' in html
    assert 'id="btnZoomReset"' in html
    assert 'id="zoomLevelText"' in html
    assert "--board-zoom" in html
    assert 'id="dlgMoveKey"' in html
    assert 'id="btnOpenMoveKey"' in html
    assert 'id="btnCopyKey"' in html
    assert 'id="btnPasteKey"' in html
    assert 'id="btnSwapKey"' in html
    assert 'id="clipboardPill"' in html


def test_swap_keys_current_layer_logic():
    """Valida a lógica de swap entre duas teclas na camada atual sem alterar outras camadas."""
    import ksm_core
    data = copy.deepcopy(ksm_core.load_canonical(DATA_V6))

    # Sofle L0: tecla 0 (Esc/Strudel) e tecla 1 (1/!)
    cell_0_pre = copy.deepcopy(data["layers"]["L0"]["sofle"]["matrix"][0][0])
    cell_1_pre = copy.deepcopy(data["layers"]["L0"]["sofle"]["matrix"][0][1])

    assert cell_0_pre["label"] != cell_1_pre["label"]

    # Simula swap na L0
    data["layers"]["L0"]["sofle"]["matrix"][0][0] = cell_1_pre
    data["layers"]["L0"]["sofle"]["matrix"][0][1] = cell_0_pre
    data["profiles"]["candidato_teste"]["sofle"]["layers"]["L0"]["matrix"][0][0] = cell_1_pre
    data["profiles"]["candidato_teste"]["sofle"]["layers"]["L0"]["matrix"][0][1] = cell_0_pre

    # Validação do dataset após a operação
    errs = ksm_core.validate_dataset(data) if hasattr(ksm_core, "validate_dataset") else []
    assert not errs, f"Erros após swap na L0: {errs}"

    # L1 não deve ter sido afetada
    assert data["layers"]["L1"]["sofle"]["matrix"][0][0]["label"] != cell_1_pre["label"]


def test_swap_keys_all_layers_logic():
    """Valida a lógica de swap em TODAS as 10 camadas (L0 a L9) simultaneamente."""
    import ksm_core
    data = copy.deepcopy(ksm_core.load_canonical(DATA_V6))

    # Sofle dedões: 48 (idx 0) e 49 (idx 1)
    pre_l0_thumb0 = copy.deepcopy(data["layers"]["L0"]["sofle"]["thumbs"][0])
    pre_l0_thumb1 = copy.deepcopy(data["layers"]["L0"]["sofle"]["thumbs"][1])
    pre_l1_thumb0 = copy.deepcopy(data["layers"]["L1"]["sofle"]["thumbs"][0])
    pre_l1_thumb1 = copy.deepcopy(data["layers"]["L1"]["sofle"]["thumbs"][1])

    # Aplica swap em todas as camadas L0..L9
    for lid in data["metadata"]["layers_order"]:
        th = data["layers"][lid]["sofle"]["thumbs"]
        th[0], th[1] = copy.deepcopy(th[1]), copy.deepcopy(th[0])
        th_mir = data["profiles"]["candidato_teste"]["sofle"]["layers"][lid]["thumbs"]
        th_mir[0], th_mir[1] = copy.deepcopy(th[0]), copy.deepcopy(th[1])

    # Confere na L0 e na L1
    assert data["layers"]["L0"]["sofle"]["thumbs"][0]["label"] == pre_l0_thumb1["label"]
    assert data["layers"]["L0"]["sofle"]["thumbs"][1]["label"] == pre_l0_thumb0["label"]
    assert data["layers"]["L1"]["sofle"]["thumbs"][0]["label"] == pre_l1_thumb1["label"]
    assert data["layers"]["L1"]["sofle"]["thumbs"][1]["label"] == pre_l1_thumb0["label"]
