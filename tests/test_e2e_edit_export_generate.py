#!/usr/bin/env python3
"""test_e2e_edit_export_generate.py — O Teste Decisivo Solicitado no Review:

Verifica de ponta a ponta a cadeia:
1. Edição em memória (simulando alteração feita pelo usuário na interface do app);
2. Exportação para arquivo JSON novo (simulando "Baixar JSON" ou gravação em arquivo alternativo);
3. Execução dos geradores (compose_sofle_candidato.py e generate_corne_candidato.py)
   passando explicitamente o arquivo exportado via --dataset;
4. Verificação determinística de que os candidatos (.vil e .keymap) gerados a partir do
   arquivo exportado contêm a tecla editada naquela exata posição;
5. Verificação cruzada de que o candidato oficial (gerado a partir do dataset canônico)
   NÃO contém a tecla editada, comprovando que o gerador não usa dados cacheados ou mapa antigo.
"""
import copy
import json
import os
import subprocess
import sys

from conftest import APP, DATA_V6, GEN, ROOT


def test_decisive_e2e_sofle_edit_export_generate(tmp_path):
    import ksm_core

    # 1. Carrega dataset canônico
    orig_data = ksm_core.load_canonical(DATA_V6)
    data = copy.deepcopy(orig_data)

    # 2. Modifica uma tecla na camada L0 do Sofle:
    # matrix[1][1] (posição da letra Q no layout físico / elétrica (1,1))
    custom_cell = {
        "top": "TESTE_Q",
        "label": "CUSTOM_Q",
        "sub": "TESTE",
        "behavior": "Tecla de Teste Decisivo",
        "impl_zmk": "&kp F24",
        "impl_qmk": "KC_F24",
        "key_type": "normal",
        "status": "candidato",
    }
    data["layers"]["L0"]["sofle"]["matrix"][1][1] = custom_cell
    data["profiles"]["candidato_teste"]["sofle"]["layers"]["L0"]["matrix"][1][1] = custom_cell

    # 3. Exporta para um arquivo temporário em disco (simulando Baixar JSON)
    exported_json = tmp_path / "keymap_data_v06_usuario_editado.json"
    exported_bytes = json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8")
    ksm_core.atomic_write(str(exported_json), exported_bytes)
    assert os.path.exists(exported_json)

    # 4. Executa compose_sofle_candidato.py apontando --dataset para o arquivo exportado
    out_dir = tmp_path / "sofle_candidates_test"
    cmd = [
        sys.executable,
        os.path.join(GEN, "compose_sofle_candidato.py"),
        "--dataset", str(exported_json),
        "--outdir", str(out_dir),
        "--force",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Falha ao executar gerador Sofle: {res.stderr}"

    # 5. Confere a mesma posição no candidato gerado C:
    cand_c_path = out_dir / "sofle_candidato_v06_C_conectado.vil"
    assert os.path.exists(cand_c_path)
    cand_c = json.load(open(cand_c_path, encoding="utf-8"))

    # Na matriz elétrica do Sofle, matrix[1][1] da metade esquerda mapeia para (1,1)
    cell_gerada = cand_c["layout"][0][1][1]
    assert cell_gerada == "KC_F24", f"Esperado KC_F24 na posição (1,1) da L0, obtido: {cell_gerada}"

    # 6. Verificação cruzada com o candidato canônico oficial:
    oficial_c_path = os.path.join(GEN, "candidates", "sofle_v06", "sofle_candidato_v06_C_conectado.vil")
    oficial_c = json.load(open(oficial_c_path, encoding="utf-8"))
    assert oficial_c["layout"][0][1][1] == "KC_Q", "Candidato oficial deve manter KC_Q original"


def test_decisive_e2e_corne_edit_export_generate(tmp_path):
    import ksm_core

    orig_data = ksm_core.load_canonical(DATA_V6)
    data = copy.deepcopy(orig_data)

    # Modifica uma tecla na camada L0 do Corne: matrix[0][1] (letra Q em ZMK)
    custom_cell = {
        "top": "TESTE_CORNE",
        "label": "TESTE_Q",
        "sub": "",
        "behavior": "Tecla de Teste ZMK",
        "impl_zmk": "&kp F24",
        "impl_qmk": "KC_F24",
        "key_type": "normal",
        "status": "candidato",
    }
    data["layers"]["L0"]["corne"]["matrix"][0][1] = custom_cell
    data["profiles"]["candidato_teste"]["corne"]["layers"]["L0"]["matrix"][0][1] = custom_cell

    exported_json = tmp_path / "corne_data_editado.json"
    exported_bytes = json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8")
    ksm_core.atomic_write(str(exported_json), exported_bytes)

    out_keymap = tmp_path / "corne_editado.keymap"
    cmd = [
        sys.executable,
        os.path.join(GEN, "generate_corne_candidato.py"),
        "--dataset", str(exported_json),
        "--out", str(out_keymap),
        "--force",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Falha ao executar gerador Corne: {res.stderr}"

    # Confere no .keymap gerado se &kp F24 está presente
    txt = open(out_keymap, encoding="utf-8").read()
    assert "&kp F24" in txt, "Keycode editado &kp F24 deve estar presente no .keymap gerado a partir do export"

    # Confere que o candidato oficial NÃO tem &kp F24
    oficial_corne = os.path.join(GEN, "candidates", "corne_candidato_v06.keymap")
    txt_oficial = open(oficial_corne, encoding="utf-8").read()
    assert "&kp F24" not in txt_oficial, "Candidato oficial não deve ter a modificação de teste"


def test_browser_full_e2e_form_download_generator(tmp_path):
    """Comprova o fluxo integral a partir do formulário do navegador real:
    1. Abre keyboard_split_manager_v06.html no Chrome headless via Playwright;
    2. Clica na tecla física (posição 13 / letra Q no layout Sofle);
    3. Preenche o formulário do modal de edição com KC_F21 / F21;
    4. Clica em salvar no modal;
    5. Clica no botão 'Baixar JSON', capturando o evento real de download do navegador;
    6. Salva o arquivo baixado pelo Chrome em tmp_path;
    7. Executa compose_sofle_candidato.py apontando para esse arquivo baixado;
    8. Valida que o .vil resultante contém KC_F21 na posição (1,1).
    """
    runner_js = os.path.join(ROOT, "tests", "test_browser_e2e_runner.js")
    env = {**os.environ, "TMP_DIR": str(tmp_path)}
    res = subprocess.run(["node", runner_js], capture_output=True, text=True, env=env)
    assert res.returncode == 0, f"Falha no teste E2E de navegador: {res.stderr}\n{res.stdout}"

