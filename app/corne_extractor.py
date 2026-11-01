#!/usr/bin/env python3
"""corne_extractor — extrator robusto de camadas do corne.keymap (ZMK devicetree).

Correções exigidas pelo plano v02 (Fase 3.1):
- stripper lexical de comentários que preserva `//`, `/* */` e strings;
- localização do nó `keymap { compatible = "zmk,keymap"; ... }` com chaves
  balanceadas (não regex de linha) e parada no fechamento real do nó;
- filhos de camada identificados por nome nativo + corpo balanceado;
- bindings agrupados por `&ref` + TODOS os parâmetros, preservando ordem;
- 42 posições por camada real; NENHUM preenchimento artificial;
- saída com matrix 3x12 + thumbs 6 (mesma ordem física do Corne);
- nomes nativos preservados (default_layer, lower_layer, raise_layer,
  system_layer); nenhum nome do candidato é aplicado à referência.
"""
import hashlib
import json
import os
import re
import sys

EXPECTED_KEYS = 42
EXPECTED_LAYERS = ("default_layer", "lower_layer", "raise_layer", "system_layer")


class ExtractError(Exception):
    pass


# --------------------------------------------------------------- lexical

def strip_comments(text: str) -> str:
    """Remove /* */ e // preservando strings e o comprimento lógico.

    Substitui cada caractere removido por espaço (ou mantém '\n') para que
    números de linha permaneçam estáveis em mensagens de erro.
    """
    out = []
    i, n = 0, len(text)
    state = "code"
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state == "code":
            if c == '"':
                state = "str"
                out.append(c)
            elif c == "/" and nxt == "*":
                state = "block"
                out.append("  ")
                i += 2
                continue
            elif c == "/" and nxt == "/":
                state = "line"
                out.append("  ")
                i += 2
                continue
            else:
                out.append(c)
        elif state == "str":
            out.append(c)
            if c == "\\" and nxt:
                out.append(nxt)
                i += 2
                continue
            if c == '"':
                state = "code"
        elif state == "line":
            if c == "\n":
                state = "code"
                out.append(c)
            else:
                out.append(" ")
        elif state == "block":
            if c == "*" and nxt == "/":
                state = "code"
                out.append("  ")
                i += 2
                continue
            out.append("\n" if c == "\n" else " ")
        i += 1
    if state == "str":
        raise ExtractError("string não terminada ao fim do arquivo")
    if state == "block":
        raise ExtractError("comentário de bloco não terminado ao fim do arquivo")
    return "".join(out)


def _balanced_body(text: str, open_pos: int):
    """Retorna (body_start, body_end, after) para o '{' em open_pos."""
    depth = 0
    i = open_pos
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
            if depth == 1:
                body_start = i + 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return body_start, i, i + 1
        i += 1
    raise ExtractError("chaves não balanceadas")


# ---------------------------------------------------------------- nós

def find_keymap_body(clean: str) -> str:
    m = re.search(r'\bkeymap\s*\{', clean)
    if not m:
        raise ExtractError("nó 'keymap {' não encontrado")
    start, end, _ = _balanced_body(clean, m.end() - 1)
    body = clean[start:end]
    if 'compatible = "zmk,keymap"' not in body:
        raise ExtractError('nó keymap sem compatible = "zmk,keymap"')
    return body


def find_layer_nodes(keymap_body: str):
    """Varre filhos diretos do keymap. Só aceita nós com bindings = <...>;."""
    nodes = []
    i, n = 0, len(keymap_body)
    child_re = re.compile(r"([A-Za-z_][A-Za-z0-9_\-]*)\s*\{")
    while i < n:
        ch = keymap_body[i]
        if ch.isspace():
            i += 1
            continue
        m = child_re.match(keymap_body, i)
        if not m:
            i += 1
            continue
        name = m.group(1)
        start, end, after = _balanced_body(keymap_body, m.end() - 1)
        body = keymap_body[start:end]
        if re.search(r"\bbindings\s*=\s*<", body):
            nodes.append((name, body))
        i = after
    if not nodes:
        raise ExtractError("nenhuma camada com bindings encontrada no keymap")
    return nodes


def bindings_of(body: str):
    m = re.search(r"\bbindings\s*=\s*<([\s\S]*?)>\s*;", body)
    if not m:
        raise ExtractError("nó sem bloco bindings = <...>;")
    tokens = m.group(1).split()
    if not tokens:
        raise ExtractError("bloco bindings vazio")
    if not tokens[0].startswith("&"):
        raise ExtractError(f"primeiro token de bindings não é &ref: {tokens[0]!r}")
    positions = []
    cur = None
    for tok in tokens:
        if tok.startswith("&"):
            if cur is not None:
                positions.append(cur)
            cur = [tok]
        else:
            if cur is None:
                raise ExtractError(f"parâmetro sem &ref anterior: {tok!r}")
            cur.append(tok)
    if cur is not None:
        positions.append(cur)
    return positions


def display_name_of(body: str, fallback: str) -> str:
    m = re.search(r'\bdisplay-name\s*=\s*"((?:[^"\\]|\\.)*)"', body)
    return m.group(1) if m else fallback


# --------------------------------------------------------------- saída

def _cell(binding: str, index: int) -> dict:
    return {
        "top": "",
        "label": binding,
        "sub": "",
        "behavior": "binding cru da referência de firmware",
        "binding": binding,
        "impl_zmk": binding,
        "impl_qmk": "",
        "key_type": "normal",
        "status": "reference",
        "position": index,
        "source": "reference",
    }


def _matrix_thumbs(positions):
    flat = [" ".join(p) for p in positions]
    matrix = [flat[0:12], flat[12:24], flat[24:36]]
    thumbs = flat[36:42]
    return matrix, thumbs


def extract(path: str, check_expected_names: bool = True) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    clean = strip_comments(raw)
    keymap_body = find_keymap_body(clean)
    layers = {}
    for name, body in find_layer_nodes(keymap_body):
        positions = bindings_of(body)
        if len(positions) != EXPECTED_KEYS:
            raise ExtractError(
                f"camada '{name}' tem {len(positions)} posições (esperado {EXPECTED_KEYS}); "
                "recusando qualquer preenchimento artificial"
            )
        matrix, thumbs = _matrix_thumbs(positions)
        flat = [" ".join(p) for p in positions]
        layers[name] = {
            "native_name": name,
            "display_name": display_name_of(body, name),
            "binding_count": len(positions),
            "bindings": positions,
            "positions": flat,
            "matrix": [[_cell(b, r * 12 + c) for c, b in enumerate(row)] for r, row in enumerate(matrix)],
            "thumbs": [_cell(b, 36 + i) for i, b in enumerate(thumbs)],
            "source": "reference",
        }
    if check_expected_names:
        missing = [x for x in EXPECTED_LAYERS if x not in layers]
        if missing:
            raise ExtractError(f"camadas esperadas ausentes na referência: {missing}")
    return {
        "source_file": os.path.abspath(path),
        "source_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "schema": "ksm_reference_extractor_v2",
        "layer_count": len(layers),
        "layers": layers,
        "total_keys_expected": EXPECTED_KEYS,
        "notes": (
            "Nomes nativos preservados do devicetree. Nenhum rótulo do candidato "
            "aplicado por correspondência automática. Slots inexistentes não são "
            "preenchidos com transparentes."
        ),
    }


def main(argv=None):
    argv = argv or sys.argv[1:]
    default_src = os.path.join(os.path.dirname(__file__), "..", "generators", "candidates", "corne_simples_v13.keymap")
    src = argv[0] if len(argv) > 0 else default_src
    dst = argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "data", "corne_reference_extracted.json")
    force = "--force" in argv
    result = extract(src)
    payload = json.dumps(result, ensure_ascii=False, indent=1)
    if os.path.exists(dst) and not force:
        raise SystemExit(f"RECUSADO: destino existe ({dst}); use --force para substituir de forma explícita")
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    tmp = dst + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload)
    os.replace(tmp, dst)
    print(json.dumps({
        "dst": dst, "layers": list(result["layers"]),
        "counts": {k: v["binding_count"] for k, v in result["layers"].items()},
        "sha256": result["source_sha256"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
