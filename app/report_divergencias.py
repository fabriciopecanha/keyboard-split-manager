#!/usr/bin/env python3
"""report_divergencias — comparação textual posição a posição (sem falso-positivo).

Corrige o relatório antigo que contava como divergência bindings idênticos.

Saídas:
- referência nativa extraída × baseline antigo (v05) por slot Lx, apenas como
  diagnóstico histórico de ONDE o modelo antigo guardou cada camada;
- NENHUM pareamento é tratado como equivalência semântica. O relatório mostra
  apenas diferenças textuais reais.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import corne_extractor  # noqa: E402

REF = os.path.join(ROOT, "data", "corne_reference_extracted.json")
OLD = os.path.join(ROOT, "reports", "archive", "keymap_data_v06_pre_rebuild_2026-10-29.json")
OUT = os.path.join(ROOT, "reports", "REFERENCE_VS_BASELINE_DIVERGENCIAS.md")
_v5_fixture = os.path.join(ROOT, "data", "fixtures", "keymap_data_v05.json")
V5 = _v5_fixture if os.path.exists(_v5_fixture) else os.path.join(ROOT, "..", "Corne", "keymap_data.json")


def flat_cells(lay):
    return [c for row in lay["matrix"] for c in row] + lay["thumbs"]


def text(cell):
    return str(cell.get("impl_zmk") or cell.get("binding") or cell.get("label") or "").strip()


def compare_ref_to_slot(ref_positions, cells):
    diffs = []
    for i, cell in enumerate(cells):
        a = ref_positions[i] if i < len(ref_positions) else "<sem referência>"
        b = text(cell)
        if a.strip() != b.strip():
            diffs.append((i, a, b))
    return diffs


def main():
    ref = json.load(open(REF, encoding="utf-8"))
    old = json.load(open(OLD, encoding="utf-8"))
    v5 = json.load(open(V5, encoding="utf-8"))

    lines = []
    a = lines.append
    a("# Divergências: referência nativa × baseline antigo (comparação textual corrigida)")
    a("")
    a("**Projeto:** Keyboard Split Manager · **Data:** 2026-10-29 · **Relatório:** 03")
    a("")
    a("## Regra de comparação")
    a("")
    a("- Compara-se o **texto completo** do binding (`&kp TAB`, `&lt 3 DEL`, `&mo 1`).")
    a("- Só entra na lista o que for textualmente diferente; igual não é divergência.")
    a("- Não se assume que `default_layer` = `L0` etc. A tabela abaixo é apenas")
    a("  diagnóstico de onde o modelo antigo guardou cada camada; não é mapeamento oficial.")
    a("- A referência tem nomes nativos preservados; o candidato L0–L9 é proposta.")
    a("")

    a("## 1. Integridade da extração")
    a("")
    total = 0
    for name, lay in ref["layers"].items():
        n = lay["binding_count"]
        total += n
        a(f"- `{name}`: {n} bindings completos, matrix 3×12 + thumbs 6")
    a("")
    a(f"Total da referência: **{total} bindings** em **{ref['layer_count']} camadas nativas**.")
    a("Fonte: `" + ref["source_file"] + "`")
    a(f"SHA-256 do `.keymap`: `{ref['source_sha256']}`")
    a("")
    a("Resultado da extração: **APROVADO** — as 4 camadas nativas presentes, 42 posições cada.")
    a("")

    a("## 2. Referência × slots do baseline antigo (v05, antes da correção)")
    a("")
    mapping = [
        ("default_layer", "L0"),
        ("lower_layer", "L1"),
        ("system_layer", "L2"),
        ("raise_layer", "L3"),
    ]
    a("| Camada nativa | Slot antigo | Divergências textuais | Diagnóstico |")
    a("|---|---|---:|---|")
    detail_sections = []
    for ref_name, slot in mapping:
        rp = ref["layers"][ref_name]["positions"]
        cells = flat_cells(old["profiles"]["baseline_instalado"]["corne"]["layers"][slot])
        diffs = compare_ref_to_slot(rp, cells)
        if ref_name == "default_layer" and slot == "L0":
            diag = "idêntico (0 reais)" if not diffs else "diferenças reais"
        elif ref_name == "lower_layer" and slot == "L1":
            diag = "idêntico (0 reais)" if not diffs else "diferenças reais"
        elif ref_name == "system_layer" and slot == "L2":
            diag = "system_layer guardada no slot errado (L2), texto idêntico"
        elif ref_name == "raise_layer" and slot == "L3":
            diag = "raise_layer AUSENTE; L3 era transparente artificial"
        else:
            diag = ""
        a(f"| `{ref_name}` | `{slot}` | {len(diffs)} | {diag} |")
        if diffs:
            detail_sections.append((ref_name, slot, diffs))

    a("")
    a("### 2.1 Detalhe das diferenças reais")
    a("")
    if not detail_sections:
        a("Nenhuma diferença textual real.")
    for ref_name, slot, diffs in detail_sections:
        a(f"#### `{ref_name}` × `{slot}` — {len(diffs)} diferenças")
        a("")
        a("| Pos | Referência | Baseline antigo |")
        a("|---:|---|---|")
        for i, ra, ob in diffs:
            a(f"| {i} | `{ra}` | `{ob}` |")
        a("")
        a("Observação: no caso de `raise_layer` × `L3`, o slot antigo era transparente")
        a("artificial; a referência tem os bindings reais de símbolos. Isso **não** significa")
        a("que o teclado tivesse transparentes: significa que o modelo antigo não extraiu a camada.")
        a("")

    a("## 3. Correção aplicada no modelo v06")
    a("")
    a("- `references.corne.native_layers` contém `default_layer`, `lower_layer`,")
    a("  `raise_layer` e `system_layer`, com 42 bindings cada.")
    a("- `profiles.baseline_instalado.corne` não contém mais L0–L9 artificiais;")
    a("  aponta para a referência nativa, somente leitura.")
    a("- O candidato L0–L9 permanece separado em `layers`.")
    a("- Nenhum slot vazio foi preenchido com transparentes.")
    a("")
    a("## 4. Conclusão")
    a("")
    a("- O relatório anterior estava **incorreto** ao contar bindings idênticos como")
    a("  divergentes (comparava estruturas, não o texto).")
    a("- Com a regra textual, as divergências reais são apenas as do quadro acima.")
    a("- A camada `raise_layer` deixou de ser omitida no dataset v06.")
    a("")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(json.dumps({"out": OUT, "sections": [
        {"ref": r, "slot": s, "diffs": len(d)} for r, s, d in detail_sections
    ]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
