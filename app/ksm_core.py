#!/usr/bin/env python3
"""ksm_core — núcleo do modelo de dados Keyboard Split Manager (schema v6).

Fonte única de:
- uid Vial como string decimal exata (conversores de/para int nas fronteiras Vial);
- hash canônico (JSON canônico ordenado, campos voláteis excluídos) — gêmeo em ksm_core.js;
- migração v5->v6 (nunca sobrescreve; saída sempre nova, versionada).
"""
import hashlib
import json
import os
import re
import sys

JOINT = 2 ** 53  # Number.MAX_SAFE_INTEGER === 2**53 em JS (exato até 2**53)
VOLATILE_KEYS = {"updated_at", "generated_at", "timestamp", "saved_at", "exported_at"}

class KSMError(Exception):
    pass

# ---------------------------------------------------------------- UID Vial

def uid_is_unsafe_int(v):
    return isinstance(v, int) and (v >= JOINT or v == -JOINT)

def uid_int_to_string(n: int) -> str:
    """Representação decimal exata como texto (frontera Vial -> modelo)."""
    if isinstance(n, str):
        int(n)  # valida dígitos
        return n
    return str(int(n))

def uid_string_to_int(s: str) -> int:
    """Modelo -> Vial (int de 64 bits). Rejeita sufixos/lixo."""
    cleaned = s.strip()
    if not (cleaned.lstrip("-").isdigit()):
        raise KSMError(f"uid não decimal: {s!r}")
    return int(cleaned)

def unsafe_anyuid_walker(obj):
    """Retorna lista de caminhos dot com uid inteiro inseguro para JS."""
    out = []
    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "uid" and uid_is_unsafe_int(v):
                    out.append(path + ".uid")
                else:
                    walk(v, path + "." + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")
    walk(obj)
    return out


def uid_text_in_obj(obj):
    """Copia profunda convertendo QUALQUER campo 'uid' inteiro em string decimal exata."""
    def walk(o):
        if isinstance(o, dict):
            return {k: (str(v) if k == "uid" and isinstance(v, int) else walk(v)) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v) for v in o]
        return o
    return walk(obj)

# ------------------------------------------------------- hash canônico

def _int_like(k):
    return bool(re.fullmatch(r"-?(?:0|[1-9]\d*)", k)) and ("-" not in k or k != "0") and (k.lstrip("-").isdigit())

def _key_sort_key(k):
    # paridade com ordenação de objetos JS: chaves inteiro-like ascendem numericamente
    # e precedem as demais; não-inteiro-like ordem lexicográfica (code-unit).
    if _int_like(k):
        return (0, int(k))
    return (1, k)

def canonicalize(obj):
    """JSON canônico: PARIDADE JS (Object.keys: inteiro-like numeric-first, 
    demais em ordem de inserção... via lexicográfica), voláteis eliminados,
    sem espaços, ensure_ascii=False. Espelha ksm_core.js:canonicalize()."""
    def norm(o):
        if isinstance(o, dict):
            return {k: norm(v) for k, v in sorted(o.items(), key=lambda kv: _key_sort_key(kv[0]))
                    if k not in VOLATILE_KEYS}
        if isinstance(o, list):
            return [norm(v) for v in o]
        return o
    return norm(obj)

def canonical_hash(obj) -> str:
    payload = json.dumps(canonicalize(obj), sort_keys=False,
                         separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def file_hash(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()

# ----------------------------------------------------- migração v5 -> v6

def migrate_v5_to_v6(data, src_name="<memória>"):
    if data.get("schema_version") != 5:
        raise KSMError(f"esperado schema_version 5, recebido {data.get('schema_version')!r} (fonte={src_name})")
    conflicts = []
    out = json.loads(json.dumps(data))  # cópia profunda via json (sem refs compartilhadas)
    out["schema_version"] = 6
    out["version"] = "v06_consolidada"

    # 1. UID -> string decimal exata
    base = out.get("profiles", {}).get("baseline_instalado", {}).get("sofle", {})
    uid = base.get("uid")
    if uid is not None:
        base["uid"] = uid_int_to_string(uid)
        base["uid_representation"] = "decimal_string"
        base.pop("uid_representation_unused", None)

    # 2. marcadores de fonte por perfis/camadas (ref vs proposal/candidate)
    profs = out.get("profiles", {})
    if "baseline_instalado" in profs:
        profs["baseline_instalado"]["source"] = "reference"
    if "candidato_teste" in profs:
        profs["candidato_teste"]["source"] = "candidate"

    # 3. status herdado de células banidas ('conflict') NUNCA entra em v6 silenciosamente
    def walk_conflicts(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk_conflicts(v, path + "." + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk_conflicts(v, f"{path}[{i}]")
        elif isinstance(o, str) and o.strip() == "conflict":
            conflicts.append(path)
    walk_conflicts(profs)
    return out, conflicts, unsafe_anyuid_walker(out)

def load_canonical(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def atomic_write(path, payload: bytes):
    """Escrita atômica: arquivo temporário + rename no mesmo diretório."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    if not os.path.isdir(d):
        raise KSMError(f"diretório inexistente: {d}")
    tmp = os.path.join(d, f".{os.path.basename(path)}.tmp")
    with open(tmp, "wb") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)  # atômico no mesmo FS

# ----------------------------------------------- Auditoria de Grafo de Camadas (BFS)

def flat_layer(lay):
    if not lay:
        return []
    if isinstance(lay, list):
        out = []
        for item in lay:
            if isinstance(item, list):
                out.extend(flat_layer(item))
            else:
                out.append(item)
        return out
    if isinstance(lay, dict):
        out = []
        if "matrix" in lay and isinstance(lay["matrix"], list):
            out.extend(flat_layer(lay["matrix"]))
        if "thumbs" in lay and isinstance(lay["thumbs"], list):
            out.extend(flat_layer(lay["thumbs"]))
        return out
    return [lay]

def audit_layer_reachability(layers_obj, kb, options=None):
    """Auditoria estrita de acessibilidade de camadas baseada em BFS a partir de L0.
    Identifica camadas alcançáveis, órfãs (inacessíveis) e armadilhas (sem saída para L0).
    Suporta dataset canônico e .vil nativo (layout + tap_dance).
    """
    import collections
    if options is None:
        options = {}
    is_corne = (kb.lower() == "corne")
    is_sofle = (kb.lower() == "sofle")

    actual_layers = {}
    tap_dances = options.get("tap_dance") or options.get("tap_dances") or []
    if isinstance(layers_obj, dict) and "layout" in layers_obj:
        for i, l_data in enumerate(layers_obj["layout"]):
            actual_layers[f"L{i}"] = l_data
        if not tap_dances and "tap_dance" in layers_obj:
            tap_dances = layers_obj["tap_dance"]
    elif isinstance(layers_obj, dict):
        for k, v in layers_obj.items():
            if re.fullmatch(r"L\d+", k):
                actual_layers[k] = v
    elif isinstance(layers_obj, list):
        for i, l_data in enumerate(layers_obj):
            actual_layers[f"L{i}"] = l_data

    layer_ids = sorted(actual_layers.keys(), key=lambda x: int(x[1:]))
    graph = {
        lid: {
            "lid": lid,
            "incoming": [],
            "outgoing": [],
        }
        for lid in layer_ids
    }

    behaviors_map = {}
    if options.get("behaviors") and isinstance(options["behaviors"], list):
        for b in options["behaviors"]:
            if isinstance(b, dict) and b.get("name"):
                behaviors_map[b["name"]] = b

    combos = options.get("combos") or []

    for from_lid in layer_ids:
        lay = actual_layers[from_lid]
        cells = flat_layer(lay)
        for pos, cell in enumerate(cells):
            if not cell:
                continue

            if is_corne:
                if isinstance(cell, dict):
                    code = str(cell.get("impl_zmk") or cell.get("binding") or "").strip()
                else:
                    code = str(cell).strip()
                if not code or code in ("&none", "&trans"):
                    continue

                # Diretivas ZMK: &to N, &mo N, &tog N, &sl N
                for m in re.finditer(r"&(to|mo|tog|sl)\s+(\d+)", code, re.IGNORECASE):
                    op = m.group(1).lower()
                    t_num = m.group(2)
                    t_lid = f"L{t_num}"
                    is_pers = op in ("to", "tog")
                    if t_lid in graph:
                        edge = {
                            "from": from_lid, "to": t_lid, "type": f"&{op}",
                            "code": m.group(0), "pos": pos, "is_persistent": is_pers,
                        }
                        graph[from_lid]["outgoing"].append(edge)
                        graph[t_lid]["incoming"].append(edge)

                # Layer-tap: &lt N KEY
                for m in re.finditer(r"&lt\s+(\d+)", code, re.IGNORECASE):
                    t_num = m.group(1)
                    t_lid = f"L{t_num}"
                    if t_lid in graph:
                        edge = {
                            "from": from_lid, "to": t_lid, "type": "&lt",
                            "code": m.group(0), "pos": pos, "is_persistent": False,
                        }
                        graph[from_lid]["outgoing"].append(edge)
                        graph[t_lid]["incoming"].append(edge)

                # Custom behaviors
                c_m = re.match(r"^&([A-Za-z0-9_]+)\s+(.+)$", code)
                if c_m:
                    b_name = c_m.group(1)
                    args = c_m.group(2).strip().split()
                    beh = behaviors_map.get(b_name)
                    if beh and isinstance(beh.get("bindings"), list):
                        for b_idx, b_op in enumerate(beh["bindings"]):
                            if b_op in ("&mo", "&to", "&tog", "&sl") and b_idx < len(args) and args[b_idx].isdigit():
                                t_num = args[b_idx]
                                t_lid = f"L{t_num}"
                                is_pers = b_op in ("&to", "&tog")
                                if t_lid in graph:
                                    edge = {
                                        "from": from_lid, "to": t_lid, "type": f"behavior:{b_name}",
                                        "code": code, "pos": pos, "is_persistent": is_pers,
                                    }
                                    graph[from_lid]["outgoing"].append(edge)
                                    graph[t_lid]["incoming"].append(edge)

            elif is_sofle:
                if isinstance(cell, dict):
                    code = str(cell.get("impl_qmk") or "").strip()
                else:
                    code = str(cell).strip()
                if not code or code in ("KC_NO", "KC_TRNS"):
                    continue

                # Diretivas QMK: TO(N), MO(N), TG(N), TT(N), OSL(N), DF(N)
                for m in re.finditer(r"\b(TO|MO|TG|TT|OSL|DF)\s*\(\s*(\d+)\s*\)", code):
                    op = m.group(1)
                    t_num = m.group(2)
                    t_lid = f"L{t_num}"
                    is_pers = op in ("TO", "TG", "TT", "DF")
                    if t_lid in graph:
                        edge = {
                            "from": from_lid, "to": t_lid, "type": op,
                            "code": m.group(0), "pos": pos, "is_persistent": is_pers,
                        }
                        graph[from_lid]["outgoing"].append(edge)
                        graph[t_lid]["incoming"].append(edge)

                # Layer-tap: LT<N>(...) ou LT(<N>, ...)
                for m in re.finditer(r"\bLT(\d+)\s*\(|\bLT\s*\(\s*(\d+)\s*,", code):
                    t_num = m.group(1) or m.group(2)
                    t_lid = f"L{t_num}"
                    if t_lid in graph:
                        edge = {
                            "from": from_lid, "to": t_lid, "type": "LT",
                            "code": m.group(0), "pos": pos, "is_persistent": False,
                        }
                        graph[from_lid]["outgoing"].append(edge)
                        graph[t_lid]["incoming"].append(edge)

                # Tap Dance: TD(N) - resolução dinâmica real a partir de tap_dance
                for m in re.finditer(r"\bTD\s*\(\s*(\d+)\s*\)", code):
                    td_idx = int(m.group(1))
                    if td_idx < len(tap_dances) and isinstance(tap_dances[td_idx], list):
                        td_def = tap_dances[td_idx]
                        for action in td_def:
                            if isinstance(action, str):
                                for sm in re.finditer(r"\b(TO|MO|TG|TT|OSL|DF)\s*\(\s*(\d+)\s*\)", action):
                                    sub_op = sm.group(1)
                                    t_num = sm.group(2)
                                    t_lid = f"L{t_num}"
                                    is_pers = sub_op in ("TO", "TG", "TT", "DF")
                                    if t_lid in graph:
                                        edge = {
                                            "from": from_lid, "to": t_lid, "type": f"TD({td_idx})",
                                            "code": f"TD({td_idx})->{sm.group(0)}", "pos": pos, "is_persistent": is_pers,
                                        }
                                        graph[from_lid]["outgoing"].append(edge)
                                        graph[t_lid]["incoming"].append(edge)
                                for sm in re.finditer(r"\bLT(\d+)\s*\(|\bLT\s*\(\s*(\d+)\s*,", action):
                                    t_num = sm.group(1) or sm.group(2)
                                    t_lid = f"L{t_num}"
                                    if t_lid in graph:
                                        edge = {
                                            "from": from_lid, "to": t_lid, "type": f"TD({td_idx})",
                                            "code": f"TD({td_idx})->{sm.group(0)}", "pos": pos, "is_persistent": False,
                                        }
                                        graph[from_lid]["outgoing"].append(edge)
                                        graph[t_lid]["incoming"].append(edge)

    # Combos dinâmicos
    if combos and isinstance(combos, list):
        for c in combos:
            c_layers = c.get("layers")
            applicable_layers = [f"L{n}" for n in c_layers] if c_layers is not None else list(layer_ids)
            c_act = str(c.get("action") or c.get("binding") or "")
            targets = []
            for m in re.finditer(r"(?:TO|MO|TG|TT|OSL|DF|&to|&mo|&tog)\s*\(?(\d+)", c_act):
                targets.append((f"L{m.group(1)}", m.group(0).startswith(("TO", "&to", "TG", "&tog", "DF"))))
            for from_lid in applicable_layers:
                if from_lid in graph:
                    for t_lid, is_pers in targets:
                        if t_lid in graph:
                            edge = {
                                "from": from_lid, "to": t_lid, "type": "combo",
                                "code": c_act, "pos": "combo", "is_persistent": is_pers,
                            }
                            graph[from_lid]["outgoing"].append(edge)
                            graph[t_lid]["incoming"].append(edge)

    # BFS a partir de L0
    reachable = set()
    reachable_direct = set()
    reachable_conditional = set()
    proven_conditionals = []
    unproven_conditionals = []
    queue = collections.deque()
    if "L0" in graph:
        reachable.add("L0")
        reachable_direct.add("L0")
        queue.append("L0")

    def check_simultaneous_activation(low, rai):
        """Comprova se duas camadas podem ser ativadas simultaneamente:
        - Devem possuir ativações momentâneas (MO/LT) a partir de uma origem comum alcançável.
        - Devem estar em posições físicas distintas (pos_low != pos_rai).
        - A posição de uma não pode estar bloqueada na camada da outra (deve ser KC_TRNS ou reativar).
        Se qualquer uma for ativada apenas por TO() ou DF(), a simultaneidade é impossível (TO desliga outras camadas).
        """
        edges_low = [e for e in graph[low]["incoming"] if e["from"] in reachable and e["type"] in ("MO", "LT", "&mo", "&lt")]
        edges_rai = [e for e in graph[rai]["incoming"] if e["from"] in reachable and e["type"] in ("MO", "LT", "&mo", "&lt")]
        if not edges_low:
            return False, f"{low} não possui ativação momentânea (MO/LT) alcançável (ativação persistente TO/DF desliga outras camadas)"
        if not edges_rai:
            return False, f"{rai} não possui ativação momentânea (MO/LT) alcançável (ativação persistente TO/DF desliga outras camadas)"

        for e_l in edges_low:
            for e_r in edges_rai:
                if e_l["from"] == e_r["from"]:
                    p_l = e_l.get("pos")
                    p_r = e_r.get("pos")
                    if p_l is not None and p_r is not None and p_l == p_r:
                        continue  # mesma tecla física não pode ser pressionada simultaneamente
                    
                    # Checagem de transparência/bloqueio na matriz das camadas alvo
                    cells_low = flat_layer(actual_layers.get(low, []))
                    cells_rai = flat_layer(actual_layers.get(rai, []))
                    c_low = cells_low[p_r] if isinstance(p_r, int) and p_r < len(cells_low) else None
                    c_rai = cells_rai[p_l] if isinstance(p_l, int) and p_l < len(cells_rai) else None
                    if is_corne:
                        str_low = str(c_low.get("impl_zmk") or c_low.get("binding") or c_low.get("impl_qmk") or "").strip() if isinstance(c_low, dict) else (str(c_low).strip() if c_low is not None else "")
                        str_rai = str(c_rai.get("impl_zmk") or c_rai.get("binding") or c_rai.get("impl_qmk") or "").strip() if isinstance(c_rai, dict) else (str(c_rai).strip() if c_rai is not None else "")
                    else:
                        str_low = str(c_low.get("impl_qmk") or c_low.get("impl_zmk") or c_low.get("binding") or "").strip() if isinstance(c_low, dict) else (str(c_low).strip() if c_low is not None else "")
                        str_rai = str(c_rai.get("impl_qmk") or c_rai.get("impl_zmk") or c_rai.get("binding") or "").strip() if isinstance(c_rai, dict) else (str(c_rai).strip() if c_rai is not None else "")

                    trns_tokens = ("KC_TRNS", "&trans", "")
                    r_num, l_num = rai[1:], low[1:]
                    ok_low = (str_low in trns_tokens) or f"MO({r_num})" in str_low or f"LT{r_num}(" in str_low or f"LT({r_num}," in str_low or "MO(" in str_low or f"&mo {r_num}" in str_low or f"&lt {r_num}" in str_low or "&mo" in str_low
                    ok_rai = (str_rai in trns_tokens) or f"MO({l_num})" in str_rai or f"LT{l_num}(" in str_rai or f"LT({l_num}," in str_rai or "MO(" in str_rai or f"&mo {l_num}" in str_rai or f"&lt {l_num}" in str_rai or "&mo" in str_rai
                    if ok_low or ok_rai:
                        return True, f"comprovada (ativação momentânea em posições distintas [{p_l}, {p_r}] com transparência/intertravamento)"
        return False, f"combinação não comprovada (não há sobreposição momentânea sem bloqueio demonstrada entre {low} e {rai})"

    changed = True
    while changed:
        changed = False
        while queue:
            curr = queue.popleft()
            for edge in graph[curr]["outgoing"]:
                to_lid = edge["to"]
                if to_lid in graph and to_lid not in reachable:
                    reachable.add(to_lid)
                    reachable_direct.add(to_lid)
                    queue.append(to_lid)
                    changed = True

        # Intertravamentos Corne (conditional_layers)
        if is_corne and options.get("conditional_layers"):
            for cond in options["conditional_layers"]:
                then_lid = f"L{cond['then_layer']}"
                if_lids = [f"L{n}" for n in cond.get("if_layers", [])]
                if len(if_lids) >= 2 and all(lid in reachable for lid in if_lids):
                    is_simul, reason = check_simultaneous_activation(if_lids[0], if_lids[1])
                    if is_simul:
                        if then_lid in graph and then_lid not in reachable:
                            reachable.add(then_lid)
                            reachable_conditional.add(then_lid)
                            proven_conditionals.append({"target": then_lid, "prerequisites": if_lids, "reason": reason})
                            queue.append(then_lid)
                            changed = True
                    else:
                        if then_lid not in reachable and not any(u["target"] == then_lid for u in unproven_conditionals):
                            unproven_conditionals.append({"target": then_lid, "prerequisites": if_lids, "reason": reason})

        # Tri-layers / Dual Activation Sofle
        if is_sofle:
            for tri in options.get("tri_layers", []):
                adj = f"L{tri['adjust']}"
                low = f"L{tri['lower']}"
                rai = f"L{tri['raise']}"
                if low in reachable and rai in reachable:
                    is_simul, reason = check_simultaneous_activation(low, rai)
                    if is_simul:
                        if adj in graph and adj not in reachable:
                            reachable.add(adj)
                            reachable_conditional.add(adj)
                            proven_conditionals.append({"target": adj, "prerequisites": [low, rai], "reason": reason})
                            queue.append(adj)
                            changed = True
                    else:
                        if adj not in reachable and not any(u["target"] == adj for u in unproven_conditionals):
                            unproven_conditionals.append({"target": adj, "prerequisites": [low, rai], "reason": reason})

            # Sofle padrão: NAV (L2) + SYM (L4) -> SYSTEM (L6)
            if "L6" in graph and "L6" not in reachable:
                if "L2" in reachable and "L4" in reachable:
                    # Verifica se L2 e L4 possuem intertravamento direto (MO(6)) ou simultaneidade comprovada
                    l2_to_l6 = any(e["to"] == "L6" for e in graph["L2"]["outgoing"])
                    l4_to_l6 = any(e["to"] == "L6" for e in graph["L4"]["outgoing"])
                    is_simul, reason = check_simultaneous_activation("L2", "L4")
                    if (l2_to_l6 and l4_to_l6) or is_simul:
                        reachable.add("L6")
                        reachable_conditional.add("L6")
                        proven_conditionals.append({"target": "L6", "prerequisites": ["L2", "L4"], "reason": reason})
                        queue.append("L6")
                        changed = True
                    else:
                        if not any(u["target"] == "L6" for u in unproven_conditionals):
                            unproven_conditionals.append({"target": "L6", "prerequisites": ["L2", "L4"], "reason": reason})

    unreachable = [lid for lid in layer_ids if lid not in reachable]

    # Verificação de saída de camadas persistentes para L0 (BFS reverso)
    def can_reach_l0(start_lid):
        visited = set([start_lid])
        q = collections.deque([start_lid])
        while q:
            node = q.popleft()
            if node == "L0":
                return True
            if node not in graph:
                continue
            for edge in graph[node]["outgoing"]:
                target = edge["to"]
                if target == "L0":
                    return True
                if target not in visited and target in graph:
                    visited.add(target)
                    q.append(target)
        return False

    # Verificação de saída por alternância (TG / &tog) na mesma tecla física
    def has_toggle_exit(lid):
        for e in graph[lid]["incoming"]:
            if e["from"] in reachable and e["type"] in ("TG", "&tog"):
                pos = e.get("pos")
                if isinstance(pos, int):
                    cells = flat_layer(actual_layers.get(lid, []))
                    if pos < len(cells):
                        c = cells[pos]
                        code = str(c.get("impl_qmk") or c.get("impl_zmk") or c.get("binding") or "").strip() if isinstance(c, dict) else str(c).strip()
                        num = lid[1:]
                        if code in ("KC_TRNS", "&trans", "") or code in (f"TG({num})", f"&tog {num}"):
                            return True
        return False

    trap_layers = []
    toggle_exit_layers = []
    for lid in reachable:
        if lid == "L0":
            continue
        has_pers_in = any(e["is_persistent"] for e in graph[lid]["incoming"] if e["from"] in reachable)
        if has_pers_in:
            if has_toggle_exit(lid):
                toggle_exit_layers.append(lid)
            elif not can_reach_l0(lid):
                trap_layers.append(lid)

    return {
        "graph": graph,
        "layer_ids": layer_ids,
        "reachable": sorted(list(reachable), key=lambda x: int(x[1:])),
        "reachable_direct": sorted(list(reachable_direct), key=lambda x: int(x[1:])),
        "reachable_conditional": sorted(list(reachable_conditional), key=lambda x: int(x[1:])),
        "proven_conditionals": proven_conditionals,
        "unproven_conditionals": unproven_conditionals,
        "unreachable": sorted(unreachable, key=lambda x: int(x[1:])),
        "trap_layers": sorted(trap_layers, key=lambda x: int(x[1:])),
        "toggle_exit_layers": sorted(toggle_exit_layers, key=lambda x: int(x[1:])),
        "mode": "acessibilidade_estatica",
    }

if __name__ == "__main__":
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _default_src = os.path.join(_root, "data", "fixtures", "keymap_data_v05.json")
    src = sys.argv[1] if len(sys.argv) > 1 else _default_src
    dst = sys.argv[2]
    if os.path.exists(dst):
        raise SystemExit(f"RECUSADO: destino já existe ({dst}) — política de sobrescrita da fonte única.")
    data = load_canonical(src)
    out, conflicts, unsafe = migrate_v5_to_v6(data, src)
    payload = json.dumps(out, ensure_ascii=False, indent=1).encode()
    atomic_write(dst, payload)
    print(json.dumps({
        "src": src, "dst": dst, "schema": 6,
        "uid_string": out["profiles"]["baseline_instalado"]["sofle"]["uid"],
        "uid_type": type(out["profiles"]["baseline_instalado"]["sofle"]["uid"]).__name__,
        "conflicts": len(conflicts), "unsafe_uid_js": unsafe,
        "canonical_hash_v6": canonical_hash(out),
        "file_hash_v6": file_hash(dst),
        "bytes": len(payload),
    }, indent=1, ensure_ascii=False))
