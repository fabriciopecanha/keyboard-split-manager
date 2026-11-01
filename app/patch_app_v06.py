#!/usr/bin/env python3
"""patch_app_v06.py — patches R1..R8 no build_manager_v06.py (cópia de v05).

Escapes JS nos replacements usam TOKENS (sem ambiguidade de decodificação):
~N~ -> \\n      (2 backslashes + n)     ~Q~ -> \\" (2 backslashes + quote)
~S~ -> \\s      ~D~ -> \\d              ~U2~ -> \\u0022
Âncoras únicas; falha = aborta SEM arquivo parcial."""
import sys

BS = chr(92)
TOK = {
    "~N~": BS*2 + "n",
    "~Q~": BS*2 + chr(34),
    "~S~": BS*2 + "s",
    "~D~": BS*2 + "d",
    "~U2~": BS*2 + "u0022",
}

import os
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_manager_v06.py")
text = open(SRC, encoding="utf-8").read()
orig_len = len(text)

def expand(s):
    for k, v in TOK.items():
        s = s.replace(k, v)
    return s

def rep(old, new, label):
    global text
    n = text.count(old)
    if n != 1:
        print(f"FALHA [{label}]: {n} xcntesperada"); sys.exit(1)
    text = text.replace(old, expand(new))
    print(f"OK {label}")

def region_replace(fn_open, fn_next, new_body, label):
    global text
    i = text.find(fn_open); j = text.find(fn_next, i)
    if i == -1 or j == -1 or j < i:
        print(f"FALHA [{label}]: região não localizada"); sys.exit(1)
    text = text[:i] + expand(new_body) + "\n\n    " + text[j:]
    print(f"OK {label}")

def line_replace(prefix, new_line, label):
    global text
    lines = text.split("\n")
    hits = [k for k, ln in enumerate(lines) if ln.strip().startswith(prefix)]
    if len(hits) != 1:
        print(f"FALHA [{label}]: {len(hits)} ocorrências de {prefix!r}"); sys.exit(1)
    lines[hits[0]] = expand(new_line)
    text = "\n".join(lines)
    print(f"OK {label}")
# ---------------- R6: schema 5 OU 6 + quarantine de cache corrompido (init)
rep(r"""          const parsed = JSON.parse(v05Cache);
          if (parsed.schema_version === 5) {{
            appData = parsed;
          }} else {{
            promptMigration(parsed, 'v05_incompativel');
          }}
        }} catch (e) {{
          appData = deepClone(defaultEmbeddedData);
        }}""",
r"""          const parsed = parseWithExactUid(v05Cache);
          if (parsed.schema_version === 5 || parsed.schema_version === 6) {{
            appData = parsed;
          }} else {{
            promptMigration(parsed, 'v05_incompativel');
          }}
        }} catch (e) {{
          try {{ localStorage.setItem('keyboard_split_manager_data_quarantine_' + Date.now(), v05Cache); }} catch (e2) {{}}
          appData = deepClone(defaultEmbeddedData);
        }}""", "R6a init schema+quarantine")

# v03/v04 caches: parse com uid exato
rep(r"          const oldData = JSON.parse(v04Cache || v03Cache);",
    r"          const oldData = parseWithExactUid(v04Cache || v03Cache);", "R6b parse uid caches")

# ---------------- R7: utilitários (parse uid exato + escapeHtml + validação de importação)
rep(r"""    function downloadDraftBackup(data) {{""",
r"""    function parseWithExactUid(text) {{
      let fixed = text;
      if (/"uid"~S~*:~S~*-?~D~{{17,}}/.test(fixed)) {{
        fixed = fixed.replace(/"uid"~S~*:~S~*(-?~D~{{17,}})(?!,)/g, '"uid":"$1"');
      }}
      return JSON.parse(fixed);
    }}

    function escapeHtml(s) {{
      return String(s == null ? "" : s)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/~U2~/g, "&quot;").replace(/'/g, "&#39;");
    }}

    function validateDatasetStructure(obj) {{
      const errs = [];
      if (!obj || typeof obj !== "object" || Array.isArray(obj)) return ["raiz não é um objeto JSON"];
      if (obj.schema_version !== 5 && obj.schema_version !== 6) errs.push("schema_version deve ser 5 ou 6 (recebido: " + JSON.stringify(obj.schema_version) + ")");
      if (!obj.metadata || !Array.isArray(obj.metadata.layers_order) || obj.metadata.layers_order.length === 0) errs.push("metadata.layers_order ausente ou vazio");
      if (!obj.layers || typeof obj.layers !== "object") errs.push("objeto layers ausente");
      else {{
        ((obj.metadata || {{}}).layers_order || []).forEach(lid => {{
          const lay = obj.layers[lid];
          if (!lay || !lay.corne || !lay.sofle) {{ errs.push("camada " + lid + " sem corne/sofle"); return; }}
          ["corne", "sofle"].forEach(kb => {{
            const m = lay[kb].matrix;
            const t = lay[kb].thumbs;
            if (!Array.isArray(m) || m.length === 0 || !Array.isArray(m[0]) || !Array.isArray(t)) errs.push("camada " + lid + "/" + kb + " sem matrix/thumbs válidos");
          }});
        }});
      }}
      return errs;
    }}

    function downloadDraftBackup(data) {{""", "R7 utils uid/escape/validate")

# ---------------- R1: uploadJSON seguro (importação validada, backup pré-estado)
rep(r"""    function uploadJSON(event) {{
      const file = event.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = function(e) {{
        try {{
          appData = JSON.parse(e.target.result);
          localStorage.setItem('keyboard_split_manager_data_v05', JSON.stringify(appData));
          renderTabs();
          switchLayer(currentLayer);
          updateDynamicHashBadge();
          alert("Arquivo JSON carregado com sucesso no gerenciador!");
        }} catch (err) {{
          alert("Erro ao ler o arquivo JSON: " + err.message);
        }}
      }};
      reader.readAsText(file);
    }}""",
r"""    function uploadJSON(event) {{
      const file = event.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = function(e) {{
        let parsed = null;
        try {{
          parsed = parseWithExactUid(e.target.result);
        }} catch (err) {{
          alert("ERRO: o arquivo não é JSON válido~N~" + err.message + "~N~~N~Estado anterior PRESERVADO. Nada foi alterado ou gravado.");
          event.target.value = "";
          return;
        }}
        const errs = validateDatasetStructure(parsed);
        if (errs.length > 0) {{
          alert("IMPORTAÇÃO RECUSADA: dados incompatíveis (" + errs.length + " problema(s)):~N~• " + errs.join("~N~• ") + "~N~~N~Estado anterior PRESERVADO. Nada foi gravado no cache.");
          event.target.value = "";
          return;
        }}
        try {{
          const backupKey = 'keyboard_split_manager_data_preimport_' + Date.now();
          if (appData) localStorage.setItem(backupKey, JSON.stringify(appData));
          appData = parsed;
          localStorage.setItem('keyboard_split_manager_data_v05', JSON.stringify(appData));
          renderTabs();
          switchLayer(currentLayer);
          updateDynamicHashBadge();
          alert("Arquivo JSON VÁLIDO importado e gravado como rascunho local.~N~Estado anterior arquivado em: " + backupKey + (parsed.schema_version === 6 ? "~N~(schema v6: UID como string decimal exata)" : ""));
        }} catch (storeErr) {{
          alert("FALHA ao gravar rascunho no cache local. Dados válidos aplicados apenas em memória:~N~" + storeErr);
        }}
      }};
      reader.readAsText(file);
    }}""", "R1 uploadJSON")

# ---------------- R2: saveDirectToDisk com 3 estados distintos, sem falso sucesso
# (região: de 'async function saveDirectToDisk() {{' até 'function copyFullJSON() {{')
new_save = r"""    async function saveDirectToDisk() {{
      if ('showSaveFilePicker' in window) {{
        let handle = null;
        try {{
          handle = await window.showSaveFilePicker({{
            suggestedName: 'keymap_data.json',
            types: [{{
              description: 'JSON Fonte Única de Verdade',
              accept: {{ 'application/json': ['.json'] }}
            }}]
          }});
        }} catch (err) {{
          if (err && err.name === 'AbortError') {{
            alert("Gravação CANCELADA pelo usuário.~N~NADA foi gravado no disco; o rascunho local permanece intocado.");
          }} else {{
            alert("FALHA na gravação direta ao disco:~N~" + (err && err.message ? err.message : String(err)) + "~N~~N~NADA foi gravado. Use o botão Baixar se quiser o arquivo mesmo assim (não é gravação confirmada).");
          }}
          return;
        }}
        try {{
          const writable = await handle.createWritable();
          await writable.write(JSON.stringify(appData, null, 2));
          await writable.close();
          showGeneratorPrompt();
          alert("ARQUIVO EFETIVAMENTE GRAVADO no disco (File System Access).~N~~N~Geração: python3 generators/generate_corne_candidato.py --dataset <arquivo> --out candidates/<versao>.keymap");
        }} catch (err) {{
          alert("FALHA DURANTE A GRAVAÇÃO (arquivo pode estar incompleto ou não gravado):~N~" + (err && err.message ? err.message : String(err)));
        }}
      }} else {{
        downloadJSON();
        showGeneratorPrompt();
        alert("Navegador sem suporte a gravação direta: ARQUIVO BAIXADO.~N~Isso NÃO é gravação confirmada no disco — é um arquivo baixado.");
      }}
    }}
"""
region_replace("    async function saveDirectToDisk() {{", "    function copyFullJSON() {{", new_save, "R2 saveDirectToDisk (região)")

# ---------------- R3: relatório de conflito com 3 versões independentes
rep(r"""                  if (draftChangedFromOld && newChangedFromOld) {{
                    // Ambos alteraram
                    if (isSameCell(cDraft, cNew)) {{
                      // Alterações convergentes
                      continue;
                    }} else {{
                      // Conflito real: preserva a edição do usuário e marca status
                      Object.assign(cNew, cDraft);
                      cNew.status = 'conflito';
                      conflicts.push({{ lid, kb, pos: "Linha " + (r+1) + ", Col " + (c+1), draft: cDraft, newBase: cNew }});
                      appliedCount++;
                    }}
                  }}""",
r"""                  if (draftChangedFromOld && newChangedFromOld) {{
                    // Ambos alteraram
                    if (isSameCell(cDraft, cNew)) {{
                      // Alterações convergentes
                      continue;
                    }} else {{
                      // Conflito real: snapshot das 3 versões ANTES da composição
                      const preNewSnapshot = {{ label: cNew.label || '', impl_zmk: cNew.impl_zmk || '' }};
                      Object.assign(cNew, cDraft);
                      cNew.status = 'conflito';
                      conflicts.push({{ lid, kb, pos: "Linha " + (r+1) + ", Col " + (c+1), draft: cDraft, newBase: preNewSnapshot, old: {{ label: cOld.label || '', impl_zmk: cOld.impl_zmk || '' }} }});
                      appliedCount++;
                    }}
                  }}""", "R3a conflito matriz")

# thumbs
rep(r"""                if (draftChangedFromOld && newChangedFromOld) {{
                  if (isSameCell(cDraft, cNew)) {{
                    continue;
                  }} else {{
                    Object.assign(cNew, cDraft);
                    cNew.status = 'conflito';
                    conflicts.push({{ lid, kb, pos: "Dedão " + (idx+1), draft: cDraft, newBase: cNew }});
                    appliedCount++;
                  }}
                }}""",
r"""                if (draftChangedFromOld && newChangedFromOld) {{
                  if (isSameCell(cDraft, cNew)) {{
                    continue;
                  }} else {{
                    const preNewSnapshot = {{ label: cNew.label || '', impl_zmk: cNew.impl_zmk || '' }};
                    Object.assign(cNew, cDraft);
                    cNew.status = 'conflito';
                    conflicts.push({{ lid, kb, pos: "Dedão " + (idx+1), draft: cDraft, newBase: preNewSnapshot, old: {{ label: cOld.label || '', impl_zmk: cOld.impl_zmk || '' }} }});
                    appliedCount++;
                  }}
                }}""", "R3b conflito thumbs")

# ---------------- R3c: alert de relatório com 3 versões (instalado/rascunho/v05) — por linha
def line_replace(prefix, new_line, label):
    global text
    lines = text.split("\n")
    hits = [k for k, ln in enumerate(lines) if ln.strip().startswith(prefix)]
    if len(hits) != 1:
        print(f"FALHA [{label}]: {len(hits)} ocorrências de {prefix!r}")
        sys.exit(1)
    lines[hits[0]] = new_line
    text = "\n".join(lines)
    print(f"OK {label}")

line_replace('alert("Migração 3-Way concluída!',
             r'''        alert("Migração 3-Way concluída!~N~~N~• " + appliedCount + " personalizações incorporadas.~N~• " + conflicts.length + " conflitos marcados com status 'conflito' (NÃO entram em candidato até resolução explícita):~N~" + conflicts.map(c => "  - [" + c.lid + "] " + c.kb.toUpperCase() + " " + c.pos + "~N~      instalado: ~Q~" + c.old.label + "~Q~ (" + c.old.impl_zmk + ")~N~      rascunho:  ~Q~" + c.draft.label + "~Q~ (" + c.draft.impl_zmk + ")~N~      v05 novo:  ~Q~" + c.newBase.label + "~Q~ (" + c.newBase.impl_zmk + ")").join("~N~"));''',
             "R3c alert conflito (linha)")

# ---------------- R4: referência histórica por versão; sem referência => SEM merge automático
rep(r"""      let appliedCount = 0;
      let conflicts = [];""",
r"""      const draftVer = String((pendingMigrationData && pendingMigrationData.version) || "");
      const legacyRef = (legacyBaselineV03 && (draftVer.indexOf("v03") === 0 || pendingMigrationData.schema_version === 3)) ? legacyBaselineV03 : null;
      if (!legacyRef) {{
        const keep = confirm("Referência histórica INDISPONÍVEL para este rascunho (versão: " + draftVer + ", schema: " + pendingMigrationData.schema_version + ").~N~~N~A incorporação automática FOI ABORTADA para não sobrescrever dados sem referência verificável.~N~~N~OK = manter o rascunho local (recomendado)~N~Cancelar = não alterar nada agora");
        if (keep) {{ keepLocalDraft(); }}
        return;
      }}

      let appliedCount = 0;
      let conflicts = [];""", "R4a referência por versão")
rep(r"            const oldKb = legacyBaselineV03?.[lid]?.[kb];",
    r"            const oldKb = legacyRef?.[lid]?.[kb];", "R4b oldKb=legacyRef")

# ---------------- R5: escape em innerHTML do diff de migração
rep(r"""        body.innerHTML = '<p class="text-amber-300 font-bold mb-2">Total de ' + diffs.length + ' posições divergentes (Matriz e Dedões):</p>' + 
          diffs.map(d => '<div class="p-1.5 rounded bg-slate-950 border border-slate-800 text-[11px]">' + d + '</div>').join('');""",
r"""        body.innerHTML = '<p class="text-amber-300 font-bold mb-2">Total de ' + diffs.length + ' posições divergentes (Matriz e Dedões):</p>' + 
          diffs.map(d => '<div class="p-1.5 rounded bg-slate-950 border border-slate-800 text-[11px]">' + escapeHtml(d) + '</div>').join('');""", "R5 escape diff modal")

# ---------------- R8: build CWD-independente + dataset v6 + hash canônico (ksm_core)
rep(r"""import json
import hashlib
import subprocess
import re
import sys

def build_manager_html():
    with open("keymap_data.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    with open("keymap_data_v03_baseline.json", "r", encoding="utf-8") as f:
        v3_data = json.load(f)
    v3_layers = v3_data.get("layers", {})

    # Hash canônico
    raw_bytes = json.dumps(data, sort_keys=True, ensure_ascii=False).encode('utf-8')
    sha256_canonical = hashlib.sha256(raw_bytes).hexdigest()

    minified_v5_json = json.dumps(data, ensure_ascii=False)
    minified_v3_layers_json = json.dumps(v3_layers, ensure_ascii=False)

    with open("keyboard_split_manager_v05_homologado.html", "r", encoding="utf-8") as f:
        orig_html = f.read()""",
r"""import json
import os
import hashlib
import subprocess
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import ksm_core

def build_manager_html(dataset=None, v3ref=None, base_html=None):
    dataset = os.path.abspath(dataset or os.path.join(_HERE, "..", "data", "keymap_data_v06.json"))
    v3ref = os.path.abspath(v3ref or os.path.join(_HERE, "..", "backup_pre_fase2", "Corne", "keymap_data_v03_baseline.json"))
    base_html = os.path.abspath(base_html or os.path.join(_HERE, "..", "..", "Corne", "keyboard_split_manager_v05_homologado.html"))

    data = ksm_core.load_canonical(dataset)
    if data.get("schema_version") not in (5, 6):
        raise SystemExit("dataset precisa ser v5/v6")

    with open(v3ref, "r", encoding="utf-8") as f:
        v3_data = json.load(f)
    v3_layers = v3_data.get("layers", {})

    # Hash CANÔNICO (campos voláteis excluídos) — hash de arquivo é distinto e pós-geração
    sha256_canonical = ksm_core.canonical_hash(data)
    minified_v5_json = json.dumps(data, ensure_ascii=False)
    minified_v3_layers_json = json.dumps(v3_layers, ensure_ascii=False)

    with open(base_html, "r", encoding="utf-8") as f:
        orig_html = f.read()""", "R8 build head (ksm_core + paths)")

rep(r"""if __name__ == "__main__":
    build_manager_html()
""",
r'''if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset")
    ap.add_argument("--v3ref")
    ap.add_argument("--base-html")
    ap.add_argument("--out", required=True, help="saída versionada nova (recusa destino existente)")
    a = ap.parse_args()
    if os.path.exists(a.out):
        raise SystemExit(f"RECUSADO: destino já existe ({a.out}) — gere versão nova.")
    html = build_manager_html(a.dataset, a.v3ref, a.base_html)
    out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML gerado: {out} ({os.path.getsize(out)} B)")
''', "R8 main (argparse, saída versionada)")


rep(r'''    target_html = "keyboard_split_manager_v05_homologado.html"
    with open(target_html, "w", encoding="utf-8") as f:
        f.write(full_html)

    print(f"Sucesso! {target_html} gerado e 100% validado com 'node --check' ({len(full_html)} bytes).")''',
     r'''    return full_html''', "R9 build retorna html (main grava)")
print()
open(SRC, "w", encoding="utf-8").write(text)
print(f"patch concluído: {orig_len} -> {len(text)} bytes")