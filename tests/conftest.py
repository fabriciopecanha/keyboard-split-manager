# conftest.py — paths compartilhados
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ksm-work/
APP = os.path.join(ROOT, "app")
GEN = os.path.join(ROOT, "generators")
KB = os.path.dirname(ROOT)

sys.path.insert(0, ROOT)
sys.path.insert(0, APP)
sys.path.insert(0, GEN)

DATA_V6 = os.path.join(ROOT, "data", "keymap_data_v06.json")
V05_FIXTURE = os.path.join(ROOT, "data", "fixtures", "keymap_data_v05.json")
V05_ORIGINAL = V05_FIXTURE if os.path.exists(V05_FIXTURE) else os.path.join(KB, "Corne", "keymap_data.json")
EXTRACTED = os.path.join(ROOT, "data", "corne_reference_extracted.json")
CAND_CORNE = os.path.join(GEN, "candidates", "corne_candidato_v05.keymap")
SOFLE_A = os.path.join(GEN, "candidates", "sofle_v06", "sofle_candidato_v06_A_aprovado.vil")
SOFLE_B = os.path.join(GEN, "candidates", "sofle_v06", "sofle_candidato_v06_B_design_v03.vil")
SOFLE_C = os.path.join(GEN, "candidates", "sofle_v06", "sofle_candidato_v06_C_conectado.vil")
SOFLE_FIXTURE = os.path.join(ROOT, "data", "fixtures", "SOFLE_FINAL_HOMOLOGADO_v01.vil")
SOFLE_HOMOLOGADO = SOFLE_FIXTURE if os.path.exists(SOFLE_FIXTURE) else os.path.join(KB, "Corne", "SOFLE_FINAL_HOMOLOGADO_v01.vil")

import pytest


@pytest.fixture(scope="session")
def dataset():
    import ksm_core
    return ksm_core.load_canonical(DATA_V6)
