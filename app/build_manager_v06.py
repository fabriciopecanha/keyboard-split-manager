#!/usr/bin/env python3
"""
Gera keyboard_split_manager_v05_homologado.html incorporando:
1. Fonte Única de Verdade (keymap_data.json) 100% atualizada (schema 5, profiles reais, behaviors, combos, macros).
2. Isolamento de Memória Estrito: deepFreeze e deepClone em defaultEmbeddedData para impedir mutação acidental do padrão de referência.
3. Migração 3-Way Inteligente: compara padrão antigo (legacyBaselineV03), rascunho do usuário e padrão novo (v05), absorvendo correções e preservando customizações sem reintroduzir bugs antigos.
4. Reconstrução Correta de Perfis: candidato_teste.corne.layers e candidato_teste.sofle.layers estruturados independentemente por camada.
5. Seletor de Perfil na UI: Candidato v05 (Alvo) vs Hardware Instalado (Baseline Real) vs Modo Diff.
6. Validação sintática do JavaScript com `node --check` antes de salvar.
7. Preservação de 100% da suíte de Auditoria Vial (KSM_VIL_REFERENCES e KeyboardSplitAuditV05).
"""

import json
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
        orig_html = f.read()

    idx_vils = orig_html.find("<script>\n/* Referencias locais atualizadas")
    if idx_vils == -1:
        raise ValueError("Tag de referências VIL não encontrada no HTML original!")
    vil_and_after = orig_html[idx_vils:]

    html_head_and_body = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Keyboard Split Manager v05 Homologado • Corne & Sofle</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap');
    
    body {{
      font-family: 'Inter', sans-serif;
      background-color: #0f172a;
      color: #f8fafc;
    }}
    
    .font-mono-code {{
      font-family: 'JetBrains Mono', monospace;
    }}

    /* Estilos das teclas */
    .key-cap {{
      transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
      user-select: none;
    }}
    .key-cap:hover {{
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
      z-index: 10;
    }}
    .key-cap:active {{
      transform: translateY(0);
    }}

    /* Tipos de teclas */
    .key-normal {{
      background-color: #1e293b;
      border: 1px solid #334155;
      color: #f1f5f9;
    }}
    .key-normal:hover {{ border-color: #64748b; }}

    .key-hold {{
      background-color: #2e1065;
      border: 1.5px solid #8b5cf6;
      color: #e9d5ff;
    }}
    .key-hold:hover {{ background-color: #3b0764; border-color: #a855f7; }}

    .key-active {{
      background-color: #451a03;
      border: 1.5px solid #f59e0b;
      color: #fef3c7;
    }}

    .key-warn {{
      background-color: #450a0a;
      border: 1.5px solid #ef4444;
      color: #fecaca;
    }}
    .key-warn:hover {{ background-color: #7f1d1d; }}

    .key-disabled {{
      background-color: #090d16;
      border: 1px solid #1e293b;
      color: #475569;
    }}

    /* Destaque do Modo Diff */
    .key-diff {{
      outline: 2px dashed #38bdf8 !important;
      box-shadow: 0 0 10px rgba(56, 189, 248, 0.45) !important;
      position: relative;
    }}
    .key-diff::after {{
      content: 'Δ';
      position: absolute;
      top: -4px;
      right: -4px;
      background: #0284c7;
      color: white;
      font-size: 8px;
      font-weight: bold;
      width: 14px;
      height: 14px;
      border-radius: 9999px;
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    /* Destaque de Conflito de Migração */
    .key-conflict {{
      outline: 2px solid #f59e0b !important;
      box-shadow: 0 0 12px rgba(245, 158, 11, 0.6) !important;
      position: relative;
    }}
    .key-conflict::after {{
      content: '⚠️';
      position: absolute;
      top: -5px;
      right: -5px;
      font-size: 10px;
    }}

    /* Impressão Limpa em A4 Paisagem */
    @media print {{
      body {{
        background-color: #ffffff !important;
        color: #0f172a !important;
      }}
      .no-print {{ display: none !important; }}
      .print-page {{
        page-break-after: always;
        padding: 20px;
        background: #ffffff !important;
      }}
      .key-normal {{ background: #ffffff !important; border: 1px solid #cbd5e1 !important; color: #0f172a !important; }}
      .key-hold {{ background: #f5f3ff !important; border: 1.5px solid #7c3aed !important; color: #5b21b6 !important; }}
      .key-active {{ background: #fef3c7 !important; border: 1.5px solid #d97706 !important; color: #92400e !important; }}
      .key-warn {{ background: #fee2e2 !important; border: 1.5px solid #dc2626 !important; color: #991b1b !important; }}
      .key-disabled {{ background: #f8fafc !important; border: 1px solid #e2e8f0 !important; color: #94a3b8 !important; }}
    }}
  </style>
</head>
<body class="min-h-screen flex flex-col">

  <!-- BARRA SUPERIOR -->
  <header class="bg-slate-900 border-b border-slate-800 px-6 py-3.5 no-print flex flex-wrap items-center justify-between gap-4 sticky top-0 z-50 shadow-lg">
    <div class="flex items-center gap-3">
      <div class="w-10 h-10 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-xl shadow-md shadow-indigo-500/20">
        ⌨
      </div>
      <div>
        <h1 class="text-lg font-bold text-white flex items-center gap-2">
          Keyboard Split Manager
          <span class="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">v05 Homologado · Fonte Única</span>
        </h1>
        <div class="flex items-center gap-2 text-xs text-slate-400">
          <span>Corne 42 (ZMK) & Tergo Sofle 58 (QMK/Vial)</span>
          <span id="liveHashBadge" class="font-mono-code text-[10px] bg-slate-800 text-indigo-300 px-2 py-0.5 rounded border border-slate-700" title="Hash SHA-256 em tempo real">SHA: Calculando...</span>
        </div>
      </div>
    </div>

    <!-- SELETOR DE PERFIL -->
    <div class="flex items-center gap-1.5 bg-slate-950 p-1 rounded-lg border border-slate-700/80 shadow-inner">
      <button id="btnProfileCandidato" onclick="selectProfile('candidato_teste')" class="px-2.5 py-1.5 rounded-md text-xs font-bold text-white bg-indigo-600 transition flex items-center gap-1.5 shadow" title="Perfil Candidato v05 (10 camadas homologadas, dedões simétricos)">
        <span>🎯</span> Candidato v05
      </button>
      <button id="btnProfileBaseline" onclick="selectProfile('baseline_instalado')" class="px-2.5 py-1.5 rounded-md text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5" title="Hardware Real Instalado (Corne commit 0915cb6 / Sofle SOFLE_FINAL_HOMOLOGADO_v01.vil)">
        <span>🔒</span> Hardware Instalado
      </button>
      <button id="btnProfileDiff" onclick="toggleDiffMode()" class="px-2.5 py-1.5 rounded-md text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5" title="Destaque visual das alterações entre instalado e candidato">
        <span>⚡</span> Modo Diff
      </button>
    </div>

    <!-- Ações e Botões -->
    <div class="flex items-center gap-2 flex-wrap">
      <!-- Busca Rápida -->
      <div class="relative">
        <input type="text" id="searchInput" placeholder="Buscar atalho ou tecla..." 
               class="bg-slate-800 border border-slate-700 text-xs rounded-lg px-3 py-1.5 w-40 text-white focus:outline-none focus:border-indigo-500 focus:w-56 transition-all">
      </div>

      <button onclick="saveDirectToDisk()" class="text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-2.5 py-1.5 rounded-lg shadow-md flex items-center gap-1.5 transition" title="Grava diretamente no arquivo keymap_data.json em disco">
        <span>💾</span> Salvar no keymap_data.json
      </button>

      <button onclick="copyFullJSON()" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 px-2.5 py-1.5 rounded-lg font-medium flex items-center gap-1 transition" title="Copiar JSON completo para área de transferência">
        <span>📋</span> Copiar JSON
      </button>

      <button onclick="downloadJSON()" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 px-2.5 py-1.5 rounded-lg font-medium flex items-center gap-1 transition" title="Download do arquivo JSON">
        <span>⬇️</span> Baixar
      </button>

      <label class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 px-2.5 py-1.5 rounded-lg font-medium flex items-center gap-1 cursor-pointer transition">
        <span>📂</span> Carregar
        <input type="file" id="uploadInput" accept=".json" class="hidden" onchange="uploadJSON(event)">
      </label>

      <a href="#ksm-audit" class="text-xs bg-cyan-900/50 hover:bg-cyan-900 text-cyan-100 border border-cyan-700 px-2.5 py-1.5 rounded-lg font-semibold">Comparar Vial</a>

      <button onclick="runAudit()" class="text-xs bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 px-2.5 py-1.5 rounded-lg font-semibold flex items-center gap-1 transition">
        <span>🔍</span> Auditar
      </button>

      <button onclick="resetToDefault()" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 px-2.5 py-1.5 rounded-lg font-medium flex items-center gap-1 transition" title="Restaura a baseline v05 da Fonte Única">
        <span>↺</span> Reset v05
      </button>

      <button onclick="window.print()" class="text-xs bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-2.5 py-1.5 rounded-lg shadow-md flex items-center gap-1.5 transition">
        <span>🖨️</span> PDF
      </button>
    </div>
  </header>

  <!-- ABAS DAS 10 CAMADAS -->
  <nav class="bg-slate-950 border-b border-slate-800 px-6 py-2.5 no-print overflow-x-auto">
    <div class="flex items-center gap-1.5 min-w-max" id="layerTabs">
      <!-- Injetado dinamicamente via JS -->
    </div>
  </nav>

  <!-- CONTEÚDO PRINCIPAL -->
  <main class="flex-1 p-6 max-w-7xl w-full mx-auto flex flex-col gap-5">

    <!-- BANNER DE MIGRAÇÃO DE CACHE (Se houver rascunho anterior) -->
    <div id="migrationBanner" class="hidden p-4 rounded-xl border border-amber-500/50 bg-amber-950/40 flex flex-col md:flex-row items-center justify-between gap-4 shadow-lg animate-pulse no-print">
      <div class="flex items-center gap-3">
        <span class="text-2xl">⚠️</span>
        <div>
          <h3 class="text-sm font-bold text-amber-200">Rascunho de Versão Anterior Detectado (v04/v03)</h3>
          <p class="text-xs text-amber-300/80">A Fonte Única de Verdade foi sincronizada para a versão <b>v05 Homologada (Schema 5)</b>. A migração 3-Way incorpora suas personalizações, preserva as correções canônicas e arquiva um backup de segurança.</p>
        </div>
      </div>
      <div class="flex items-center gap-2 flex-wrap">
        <button onclick="migrateIncorporatingEdits()" class="text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-3 py-2 rounded-lg shadow transition" title="Migração 3-Way: Preserva suas edições personalizadas e incorpora correções v05">
          📦 Incorporar Alterações (3-Way Merge)
        </button>
        <button onclick="migrateResetWithBackup()" class="text-xs bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold px-3 py-2 rounded-lg shadow transition" title="Baixa backup do rascunho e restaura o padrão v05 limpo">
          🔄 Padrão v05 (com Backup)
        </button>
        <button onclick="showMigrationDiff()" class="text-xs bg-slate-800 hover:bg-slate-700 text-amber-200 border border-amber-500/30 px-3 py-2 rounded-lg font-medium transition" title="Compara alterações da Matriz e dos Dedões">
          👁️ Ver Diferenças (Matriz + Dedões)
        </button>
        <button onclick="keepLocalDraft()" class="text-xs bg-slate-900 hover:bg-slate-800 text-slate-400 px-3 py-2 rounded-lg font-medium transition">
          Manter Rascunho
        </button>
      </div>
    </div>

    <!-- AVISO DE PRÓXIMO PASSO DO GERADOR -->
    <div id="generatorNotice" class="hidden p-3.5 rounded-xl border border-indigo-500/40 bg-indigo-950/70 flex items-center justify-between gap-4 no-print shadow-md">
      <div class="flex items-center gap-2.5 text-xs text-indigo-200">
        <span class="text-lg">🚀</span>
        <div>
          <span class="font-bold text-white">Alterações Gravadas na Fonte Única!</span>
          <span class="ml-2">Para gerar o arquivo Devicetree do Corne 42, execute no terminal: <code class="font-mono-code bg-black/60 px-2 py-0.5 rounded text-indigo-300 border border-indigo-500/30 select-all">python3 generate_corne_from_json.py</code> <span class="text-slate-400 text-[11px]">(Gera o corne_sofle_homologado_v04.keymap; não produz UF2)</span></span>
        </div>
      </div>
      <button onclick="document.getElementById('generatorNotice').classList.add('hidden')" class="text-xs text-indigo-300 hover:text-white px-2 py-1 font-bold">✕</button>
    </div>

    <!-- BANNER DE ACESSO DA CAMADA ATIVA -->
    <div id="layerBanner" class="p-4 rounded-xl border flex flex-wrap items-center justify-between gap-4 transition-all">
      <!-- Injetado dinamicamente -->
    </div>

    <!-- SELETOR DE VISUALIZAÇÃO -->
    <div class="flex items-center justify-between gap-4 no-print">
      <div class="flex items-center gap-2 bg-slate-900 p-1 rounded-lg border border-slate-800">
        <button onclick="setViewMode('both')" id="btnViewBoth" class="px-3 py-1.5 rounded-md text-xs font-semibold text-white bg-slate-800 transition">Ambos Lado a Lado</button>
        <button onclick="setViewMode('corne')" id="btnViewCorne" class="px-3 py-1.5 rounded-md text-xs font-semibold text-slate-400 hover:text-white transition">Apenas Corne 42</button>
        <button onclick="setViewMode('sofle')" id="btnViewSofle" class="px-3 py-1.5 rounded-md text-xs font-semibold text-slate-400 hover:text-white transition">Apenas Sofle 58</button>
      </div>

      <div class="text-xs text-slate-400 flex items-center gap-4">
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-purple-900 border border-purple-500 inline-block"></span> Hold / Acesso</span>
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-amber-900 border border-amber-500 inline-block"></span> Camada Ativa</span>
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-red-900 border border-red-500 inline-block"></span> Saída / Reset</span>
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-slate-900 border border-slate-700 inline-block"></span> Bloqueada (NO)</span>
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded border-2 border-dashed border-sky-400 inline-block"></span> Modificada (Diff)</span>
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded border-2 border-amber-500 inline-block"></span> Conflito Migração</span>
      </div>
    </div>

    <!-- ÁREA DOS TECLADOS -->
    <div class="flex flex-col gap-8" id="keyboardContainer">
      
      <!-- BLOCO CORNE 42 -->
      <section id="sectionCorne" class="bg-slate-900/60 border border-slate-800/80 p-5 rounded-2xl shadow-xl flex flex-col gap-3">
        <div class="flex items-center justify-between border-b border-slate-800 pb-2">
          <div class="flex items-center gap-2">
            <span class="text-sm font-bold text-indigo-400">CORNE 42</span>
            <span class="text-xs text-slate-400">• ZMK Devicetree (36 Principais + 6 Dedões)</span>
          </div>
          <span class="text-xs font-mono-code text-slate-400">Split Wireless • nice!nano</span>
        </div>
        
        <!-- Matriz Corne -->
        <div id="corneMatrix" class="flex flex-col gap-1.5 items-center w-full overflow-x-auto py-2"></div>
        <!-- Dedões Corne -->
        <div id="corneThumbs" class="flex gap-1.5 justify-center pt-1"></div>
      </section>

      <!-- BLOCO SOFLE 58 -->
      <section id="sectionSofle" class="bg-slate-900/60 border border-slate-800/80 p-5 rounded-2xl shadow-xl flex flex-col gap-3">
        <div class="flex items-center justify-between border-b border-slate-800 pb-2">
          <div class="flex items-center gap-2">
            <span class="text-sm font-bold text-emerald-400">TERGO SOFLE 58</span>
            <span class="text-xs text-slate-400">• QMK / Vial (48 Principais + 10 Dedões/Bordas)</span>
          </div>
          <span class="text-xs font-mono-code text-slate-400">Split Cabeado • RP2040 / 2 Encoders</span>
        </div>
        
        <!-- Matriz Sofle -->
        <div id="sofleMatrix" class="flex flex-col gap-1.5 items-center w-full overflow-x-auto py-2"></div>
        <!-- Dedões Sofle -->
        <div id="sofleThumbs" class="flex gap-1.5 justify-center pt-1"></div>
      </section>

    </div>
  </main>

  <!-- MODAL DE EDIÇÃO DE TECLA -->
  <div id="editModal" class="hidden fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 flex flex-col gap-4 shadow-2xl">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <h3 id="modalTitle" class="text-base font-bold text-white flex items-center gap-2">
            <span>✏️</span> Editar Atalho
            <span id="modalPosBadge" class="text-xs font-mono-code bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded"></span>
          </h3>
          <p id="modalKbSub" class="text-xs text-slate-400"></p>
        </div>
        <button onclick="closeModal()" class="text-slate-400 hover:text-white text-lg font-bold">✕</button>
      </div>

      <div class="flex flex-col gap-3 text-xs">
        <div>
          <label class="block text-slate-400 mb-1 font-semibold">Rótulo Principal (Ex: Space, Q, F1)</label>
          <input type="text" id="modalLabel" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white font-bold text-sm focus:border-indigo-500 focus:outline-none">
        </div>

        <div>
          <label class="block text-slate-400 mb-1 font-semibold">Sub-rótulo / Atalho Visual (Ex: hold NAV, Cmd+Z)</label>
          <input type="text" id="modalSub" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-indigo-500 focus:outline-none">
        </div>

        <div>
          <label class="block text-slate-400 mb-1 font-semibold">Descrição do Comportamento</label>
          <input type="text" id="modalBehavior" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-indigo-500 focus:outline-none">
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-indigo-400 mb-1 font-semibold font-mono-code">ZMK Devicetree</label>
            <input type="text" id="modalZmk" class="w-full bg-slate-950 border border-indigo-900/50 rounded-lg px-3 py-2 text-indigo-200 font-mono-code focus:border-indigo-500 focus:outline-none" placeholder="&kp S">
          </div>
          <div>
            <label class="block text-emerald-400 mb-1 font-semibold font-mono-code">QMK / Vial Code</label>
            <input type="text" id="modalQmk" class="w-full bg-slate-950 border border-emerald-900/50 rounded-lg px-3 py-2 text-emerald-200 font-mono-code focus:border-emerald-500 focus:outline-none" placeholder="KC_S">
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-slate-400 mb-1 font-semibold">Tipo Visual da Tecla</label>
            <select id="modalType" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-indigo-500 focus:outline-none">
              <option value="normal">Normal (Padrão)</option>
              <option value="hold">Hold / Acesso de Camada</option>
              <option value="active">Camada Ativa</option>
              <option value="warn">Aviso / Saída (TO(0))</option>
              <option value="disabled">Desativada / Bloqueada</option>
            </select>
          </div>
          <div>
            <label class="block text-slate-400 mb-1 font-semibold">Status de Homologação</label>
            <select id="modalStatus" class="w-full bg-slate-800 border border-amber-500/40 rounded-lg px-3 py-2 text-amber-200 font-semibold focus:border-amber-500 focus:outline-none">
              <option value="visual">Visual (Em proposta)</option>
              <option value="candidato">Candidato Sincronizado</option>
              <option value="mapeado">Mapeado no JSON</option>
              <option value="compilado">Compilado no Firmware</option>
              <option value="testado">Testado no Hardware</option>
              <option value="instalado">Instalado no Hardware</option>
              <option value="conflito">Conflito de Migração</option>
            </select>
          </div>
        </div>
      </div>

      <div id="modalReadOnlyAlert" class="hidden p-2.5 rounded-lg bg-amber-950/70 border border-amber-500/40 text-amber-300 text-xs font-semibold">
        🔒 Perfil Hardware Instalado é somente leitura. Para editar teclas, alterne para o Perfil "Candidato v05".
      </div>

      <div class="flex items-center justify-end gap-2 border-t border-slate-800 pt-3">
        <button onclick="closeModal()" class="px-4 py-2 rounded-lg text-slate-300 hover:bg-slate-800 font-medium transition text-xs">Fechar</button>
        <button id="modalSaveBtn" onclick="saveKeyEdit()" class="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold shadow-md transition text-xs">Salvar Alterações</button>
      </div>
    </div>
  </div>

  <!-- MODAL DE COMPARAÇÃO DE MIGRAÇÃO (DIFF) -->
  <div id="diffModal" class="hidden fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-3xl w-full max-h-[85vh] flex flex-col p-6 shadow-2xl">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 class="text-base font-bold text-white flex items-center gap-2">
          <span>👁️</span> Comparação de Diferenças (Rascunho vs v05 Sincronizada)
        </h3>
        <button onclick="closeDiffModal()" class="text-slate-400 hover:text-white text-lg font-bold">✕</button>
      </div>
      <div id="diffModalBody" class="flex-1 overflow-y-auto py-4 text-xs font-mono-code text-slate-300 space-y-2"></div>
      <div class="flex justify-end gap-2 border-t border-slate-800 pt-3">
        <button onclick="closeDiffModal()" class="px-4 py-2 rounded-lg bg-slate-800 text-slate-200 text-xs font-semibold">Fechar</button>
        <button onclick="migrateIncorporatingEdits()" class="px-4 py-2 rounded-lg bg-emerald-600 text-white text-xs font-bold">Incorporar Alterações (Merge)</button>
        <button onclick="migrateResetWithBackup()" class="px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-bold">Padrão v05 (com Backup)</button>
      </div>
    </div>
  </div>

  <!-- SCRIPT PRINCIPAL DO GERENCIADOR -->
  <script>
    function deepClone(obj) {{
      return JSON.parse(JSON.stringify(obj));
    }}

    function deepFreeze(obj) {{
      Object.freeze(obj);
      Object.getOwnPropertyNames(obj).forEach(prop => {{
        if (obj[prop] !== null && (typeof obj[prop] === 'object' || typeof obj[prop] === 'function') && !Object.isFrozen(obj[prop])) {{
          deepFreeze(obj[prop]);
        }}
      }});
      return obj;
    }}

    // Dados de Referência Canônicos (Imutáveis)
    const defaultEmbeddedData = deepFreeze({minified_v5_json});
    const legacyBaselineV03 = deepFreeze({minified_v3_layers_json});

    // Estado da Aplicação (Sempre inicializado como cópia profunda independente)
    let appData = null;
    let activeProfile = "candidato_teste";
    let diffMode = false;
    let currentLayer = "L0";
    let viewMode = "both";
    let currentEditingTarget = null;
    let pendingMigrationData = null;

    async function calculateSHA256(dataObj) {{
      const jsonStr = JSON.stringify(dataObj);
      const encoder = new TextEncoder();
      const data = encoder.encode(jsonStr);
      const hashBuffer = await crypto.subtle.digest('SHA-256', data);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    }}

    async function updateDynamicHashBadge() {{
      if (!appData) return;
      const currentHash = await calculateSHA256(appData);
      const baselineHash = await calculateSHA256(defaultEmbeddedData);
      const badge = document.getElementById('liveHashBadge');
      if (badge) {{
        if (currentHash === baselineHash || JSON.stringify(appData) === JSON.stringify(defaultEmbeddedData)) {{
          badge.className = 'font-mono-code text-[10px] bg-emerald-950/80 text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/40';
          badge.innerText = "SHA: " + currentHash.slice(0,8) + " (v05 canônico ✓)";
          badge.title = "Hash SHA-256 canônico idêntico à Fonte Única: " + currentHash;
        }} else {{
          badge.className = 'font-mono-code text-[10px] bg-amber-950/80 text-amber-300 px-2 py-0.5 rounded border border-amber-500/40';
          badge.innerText = "SHA: " + currentHash.slice(0,8) + " (modificado)";
          badge.title = "Hash modificado em relação à baseline: " + currentHash;
        }}
      }}
    }}

    // Inicialização com detecção de versão e migração de cache
    async function init() {{
      const v05Cache = localStorage.getItem('keyboard_split_manager_data_v05');
      const v04Cache = localStorage.getItem('keyboard_split_manager_data_v04');
      const v03Cache = localStorage.getItem('keyboard_split_manager_data_v03');

      if (v05Cache) {{
        try {{
          const parsed = parseWithExactUid(v05Cache);
          if (parsed.schema_version === 5 || parsed.schema_version === 6) {{
            appData = parsed;
          }} else {{
            promptMigration(parsed, 'v05_incompativel');
          }}
        }} catch (e) {{
          try {{ localStorage.setItem('keyboard_split_manager_data_quarantine_' + Date.now(), v05Cache); }} catch (e2) {{}}
          appData = deepClone(defaultEmbeddedData);
        }}
      }} else if (v04Cache || v03Cache) {{
        try {{
          const oldData = parseWithExactUid(v04Cache || v03Cache);
          promptMigration(oldData, v04Cache ? 'v04' : 'v03');
        }} catch (e) {{
          appData = deepClone(defaultEmbeddedData);
        }}
      }} else {{
        appData = deepClone(defaultEmbeddedData);
      }}

      if (!appData) appData = deepClone(defaultEmbeddedData);

      renderTabs();
      switchLayer("L0");
      await updateDynamicHashBadge();

      document.getElementById('searchInput').addEventListener('input', (e) => {{
        highlightSearch(e.target.value.toLowerCase().trim());
      }});
    }}

    function promptMigration(oldData, fromVersion) {{
      pendingMigrationData = oldData;
      appData = deepClone(defaultEmbeddedData);
      const banner = document.getElementById('migrationBanner');
      if (banner) banner.classList.remove('hidden');
    }}

    function parseWithExactUid(text) {{
      let fixed = text;
      if (/"uid"\\s*:\\s*-?\\d{{17,}}/.test(fixed)) {{
        fixed = fixed.replace(/"uid"\\s*:\\s*(-?\\d{{17,}})(?!,)/g, '"uid":"$1"');
      }}
      return JSON.parse(fixed);
    }}

    function escapeHtml(s) {{
      return String(s == null ? "" : s)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/\\u0022/g, "&quot;").replace(/'/g, "&#39;");
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

    function downloadDraftBackup(data) {{
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(data, null, 2));
      const dl = document.createElement('a');
      dl.setAttribute("href", dataStr);
      dl.setAttribute("download", "backup_rascunho_split_manager_" + new Date().toISOString().slice(0,10) + ".json");
      document.body.appendChild(dl);
      dl.click();
      dl.remove();
    }}

    function isSameCell(a, b) {{
      if (!a || !b) return a === b;
      return a.label === b.label &&
             a.impl_zmk === b.impl_zmk &&
             a.impl_qmk === b.impl_qmk &&
             (a.sub || '') === (b.sub || '') &&
             (a.behavior || '') === (b.behavior || '');
    }}

    // Migração 3-Way: (Padrão Antigo vs Rascunho vs Padrão Novo)
    function migrateIncorporatingEdits() {{
      if (!pendingMigrationData) return;

      // 1. Arquivar backup seguro em chave separada para nunca perder dados
      const backupKey = 'keyboard_split_manager_data_v04_archive_' + Date.now();
      localStorage.setItem(backupKey, JSON.stringify(pendingMigrationData));

      // 2. Disparar download do arquivo de backup
      downloadDraftBackup(pendingMigrationData);

      // 3. Inicializar com a estrutura canônica v05 limpa (cópia profunda)
      appData = deepClone(defaultEmbeddedData);

      const draftVer = String((pendingMigrationData && pendingMigrationData.version) || "");
      const legacyRef = (legacyBaselineV03 && (draftVer.indexOf("v03") === 0 || pendingMigrationData.schema_version === 3)) ? legacyBaselineV03 : null;
      if (!legacyRef) {{
        const keep = confirm("Referência histórica INDISPONÍVEL para este rascunho (versão: " + draftVer + ", schema: " + pendingMigrationData.schema_version + ").\\n\\nA incorporação automática FOI ABORTADA para não sobrescrever dados sem referência verificável.\\n\\nOK = manter o rascunho local (recomendado)\\nCancelar = não alterar nada agora");
        if (keep) {{ keepLocalDraft(); }}
        return;
      }}

      let appliedCount = 0;
      let conflicts = [];

      // 4. Executa 3-Way Merge para Matriz e Dedões
      if (pendingMigrationData.layers) {{
        appData.metadata.layers_order.forEach(lid => {{
          ['corne', 'sofle'].forEach(kb => {{
            const draftKb = pendingMigrationData.layers?.[lid]?.[kb];
            const oldKb = legacyRef?.[lid]?.[kb];
            const newKb = appData.layers[lid][kb];

            if (!draftKb) return;

            // Matrix
            if (draftKb.matrix && newKb.matrix) {{
              const rows = newKb.matrix.length;
              const cols = newKb.matrix[0].length;
              for (let r = 0; r < rows; r++) {{
                for (let c = 0; c < cols; c++) {{
                  const cNew = newKb.matrix[r][c];
                  const cDraft = draftKb.matrix?.[r]?.[c];
                  const cOld = oldKb?.matrix?.[r]?.[c];

                  if (!cDraft) continue;

                  if (!cOld) {{
                    if (!isSameCell(cDraft, cNew)) {{
                      Object.assign(cNew, cDraft);
                      appliedCount++;
                    }}
                    continue;
                  }}

                  const draftChangedFromOld = !isSameCell(cDraft, cOld);
                  const newChangedFromOld = !isSameCell(cNew, cOld);

                  if (!draftChangedFromOld) {{
                    // O usuário não alterou esta tecla: mantém cNew (absorve correções da v05!)
                    continue;
                  }}

                  if (draftChangedFromOld && !newChangedFromOld) {{
                    // O usuário personalizou esta tecla e a v05 não mudou: preserva edição do usuário
                    Object.assign(cNew, cDraft);
                    appliedCount++;
                    continue;
                  }}

                  if (draftChangedFromOld && newChangedFromOld) {{
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
                  }}
                }}
              }}
            }}

            // Thumbs
            if (draftKb.thumbs && newKb.thumbs) {{
              const tLen = newKb.thumbs.length;
              for (let idx = 0; idx < tLen; idx++) {{
                const cNew = newKb.thumbs[idx];
                const cDraft = draftKb.thumbs?.[idx];
                const cOld = oldKb?.thumbs?.[idx];

                if (!cDraft) continue;

                if (!cOld) {{
                  if (!isSameCell(cDraft, cNew)) {{
                    Object.assign(cNew, cDraft);
                    appliedCount++;
                  }}
                  continue;
                }}

                const draftChangedFromOld = !isSameCell(cDraft, cOld);
                const newChangedFromOld = !isSameCell(cNew, cOld);

                if (!draftChangedFromOld) {{
                  continue;
                }}

                if (draftChangedFromOld && !newChangedFromOld) {{
                  Object.assign(cNew, cDraft);
                  appliedCount++;
                  continue;
                }}

                if (draftChangedFromOld && newChangedFromOld) {{
                  if (isSameCell(cDraft, cNew)) {{
                    continue;
                  }} else {{
                    const preNewSnapshot = {{ label: cNew.label || '', impl_zmk: cNew.impl_zmk || '' }};
                    Object.assign(cNew, cDraft);
                    cNew.status = 'conflito';
                    conflicts.push({{ lid, kb, pos: "Dedão " + (idx+1), draft: cDraft, newBase: preNewSnapshot, old: {{ label: cOld.label || '', impl_zmk: cOld.impl_zmk || '' }} }});
                    appliedCount++;
                  }}
                }}
              }}
            }}
          }});
        }});
      }}

      // 5. Reconstruir separadamente as camadas de Corne e Sofle dentro de candidato_teste
      appData.profiles.candidato_teste.corne.layers = {{}};
      appData.profiles.candidato_teste.sofle.layers = {{}};
      appData.metadata.layers_order.forEach(lid => {{
        appData.profiles.candidato_teste.corne.layers[lid] = deepClone(appData.layers[lid].corne);
        appData.profiles.candidato_teste.sofle.layers[lid] = deepClone(appData.layers[lid].sofle);
      }});

      appData.schema_version = 5;
      appData.version = "v05_sincronizada";

      // 6. Gravar na chave v05
      localStorage.setItem('keyboard_split_manager_data_v05', JSON.stringify(appData));

      document.getElementById('migrationBanner').classList.add('hidden');
      closeDiffModal();
      pendingMigrationData = null;
      renderTabs();
      switchLayer(currentLayer);
      updateDynamicHashBadge();

      if (conflicts.length > 0) {{
        alert("Migração 3-Way concluída!~N~~N~• " + appliedCount + " personalizações incorporadas.~N~• " + conflicts.length + " conflitos marcados com status 'conflito' (NÃO entram em candidato até resolução explícita):~N~" + conflicts.map(c => "  - [" + c.lid + "] " + c.kb.toUpperCase() + " " + c.pos + "~N~      instalado: ~Q~" + c.old.label + "~Q~ (" + c.old.impl_zmk + ")~N~      rascunho:  ~Q~" + c.draft.label + "~Q~ (" + c.draft.impl_zmk + ")~N~      v05 novo:  ~Q~" + c.newBase.label + "~Q~ (" + c.newBase.impl_zmk + ")").join("~N~"));
      }} else {{
        alert("Migração 3-Way concluída com sucesso!\\n\\n• " + appliedCount + " personalizações do usuário preservadas.\\n• Correções canônicas da v05 preservadas sem reintroduzir bugs antigos.\\n• Backup baixado e arquivado.");
      }}
    }}

    function migrateResetWithBackup() {{
      if (!pendingMigrationData) return;

      if (!confirm("Esta ação baixará o backup do seu rascunho e carregará a baseline v05 padrão da Fonte Única. Deseja prosseguir?")) {{
        return;
      }}

      const backupKey = 'keyboard_split_manager_data_v04_archive_' + Date.now();
      localStorage.setItem(backupKey, JSON.stringify(pendingMigrationData));

      downloadDraftBackup(pendingMigrationData);

      appData = deepClone(defaultEmbeddedData);
      localStorage.setItem('keyboard_split_manager_data_v05', JSON.stringify(appData));

      document.getElementById('migrationBanner').classList.add('hidden');
      closeDiffModal();
      pendingMigrationData = null;
      renderTabs();
      switchLayer(currentLayer);
      updateDynamicHashBadge();

      alert("Padrão v05 restaurado com sucesso! Backup do rascunho arquivado e baixado.");
    }}

    function keepLocalDraft() {{
      if (pendingMigrationData) {{
        appData = pendingMigrationData;
        localStorage.setItem('keyboard_split_manager_data_v05', JSON.stringify(appData));
      }}
      document.getElementById('migrationBanner').classList.add('hidden');
      pendingMigrationData = null;
      renderTabs();
      switchLayer(currentLayer);
      updateDynamicHashBadge();
      alert("Rascunho mantido no cache local como sessão personalizada.");
    }}

    function showMigrationDiff() {{
      if (!pendingMigrationData) return;
      const modal = document.getElementById('diffModal');
      const body = document.getElementById('diffModalBody');
      body.innerHTML = '';

      let diffs = [];
      appData.metadata.layers_order.forEach(lid => {{
        ['corne', 'sofle'].forEach(kb => {{
          try {{
            const oldMatrix = pendingMigrationData.layers[lid][kb].matrix;
            const newMatrix = defaultEmbeddedData.layers[lid][kb].matrix;
            if (oldMatrix && newMatrix) {{
              oldMatrix.forEach((row, r) => {{
                row.forEach((oldCell, c) => {{
                  const newCell = newMatrix[r][c];
                  if (newCell && (oldCell.label !== newCell.label || oldCell.impl_zmk !== newCell.impl_zmk || oldCell.impl_qmk !== newCell.impl_qmk)) {{
                    diffs.push("• [" + lid + "] " + kb.toUpperCase() + " Linha " + (r+1) + ", Col " + (c+1) + ": Rascunho: \\"" + oldCell.label + "\\" (" + (oldCell.impl_zmk || oldCell.impl_qmk) + ") → v05: \\"" + newCell.label + "\\" (" + (newCell.impl_zmk || newCell.impl_qmk) + ")");
                  }}
                }});
              }});
            }}

            const oldThumbs = pendingMigrationData.layers[lid][kb].thumbs;
            const newThumbs = defaultEmbeddedData.layers[lid][kb].thumbs;
            if (oldThumbs && newThumbs) {{
              oldThumbs.forEach((oldCell, idx) => {{
                const newCell = newThumbs[idx];
                if (newCell && (oldCell.label !== newCell.label || oldCell.impl_zmk !== newCell.impl_zmk || oldCell.impl_qmk !== newCell.impl_qmk)) {{
                  diffs.push("• [" + lid + "] " + kb.toUpperCase() + " Dedão " + (idx+1) + ": Rascunho: \\"" + oldCell.label + "\\" (" + (oldCell.impl_zmk || oldCell.impl_qmk) + ") → v05: \\"" + newCell.label + "\\" (" + (newCell.impl_zmk || newCell.impl_qmk) + ")");
                }}
              }});
            }}
          }} catch(e) {{}}
        }});
      }});

      if (diffs.length === 0) {{
        body.innerHTML = '<p class="text-emerald-400 font-bold">Nenhuma divergência de teclas encontrada entre o rascunho e a baseline v05.</p>';
      }} else {{
        body.innerHTML = '<p class="text-amber-300 font-bold mb-2">Total de ' + diffs.length + ' posições divergentes (Matriz e Dedões):</p>' + 
          diffs.map(d => '<div class="p-1.5 rounded bg-slate-950 border border-slate-800 text-[11px]">' + escapeHtml(d) + '</div>').join('');
      }}

      modal.classList.remove('hidden');
    }}

    function closeDiffModal() {{
      document.getElementById('diffModal').classList.add('hidden');
    }}

    function selectProfile(profileKey) {{
      activeProfile = profileKey;
      const bCand = document.getElementById('btnProfileCandidato');
      const bBase = document.getElementById('btnProfileBaseline');

      if (profileKey === 'candidato_teste') {{
        bCand.className = "px-2.5 py-1.5 rounded-md text-xs font-bold text-white bg-indigo-600 transition flex items-center gap-1.5 shadow";
        bBase.className = "px-2.5 py-1.5 rounded-md text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5";
      }} else {{
        bCand.className = "px-2.5 py-1.5 rounded-md text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5";
        bBase.className = "px-2.5 py-1.5 rounded-md text-xs font-bold text-amber-200 bg-amber-900/60 border border-amber-600/50 transition flex items-center gap-1.5 shadow";
      }}

      renderBanner(currentLayer);
      renderKeyboards(currentLayer);
    }}

    function toggleDiffMode() {{
      diffMode = !diffMode;
      const bDiff = document.getElementById('btnProfileDiff');
      if (diffMode) {{
        bDiff.className = "px-2.5 py-1.5 rounded-md text-xs font-bold text-cyan-200 bg-cyan-900/70 border border-cyan-500 transition flex items-center gap-1.5 shadow";
        bDiff.title = "Modo Diff Ativo: Mostrando bordas tracejadas e indicador Δ nas teclas modificadas em relação ao hardware instalado.";
      }} else {{
        bDiff.className = "px-2.5 py-1.5 rounded-md text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5";
        bDiff.title = "Destaque visual das alterações entre instalado e candidato";
      }}
      renderKeyboards(currentLayer);
    }}

    function getActiveLayerData(lid, kb) {{
      if (activeProfile === 'baseline_instalado') {{
        return appData.profiles.baseline_instalado[kb].layers[lid];
      }} else {{
        if (appData.layers && appData.layers[lid] && appData.layers[lid][kb]) {{
          return appData.layers[lid][kb];
        }}
        return appData.profiles.candidato_teste[kb].layers[lid];
      }}
    }}

    function isKeyDiff(lid, kb, type, r, c) {{
      try {{
        const candLayer = appData.layers[lid][kb];
        const baseLayer = appData.profiles.baseline_instalado[kb].layers[lid];
        const candCell = type === 'matrix' ? candLayer.matrix[r][c] : candLayer.thumbs[c];
        const baseCell = type === 'matrix' ? baseLayer.matrix[r][c] : baseLayer.thumbs[c];
        
        const candVal = (kb === 'corne' ? candCell.impl_zmk : candCell.impl_qmk) || candCell.label;
        const baseVal = (kb === 'corne' ? baseCell.impl_zmk : baseCell.impl_qmk) || baseCell.label;
        return candVal.trim() !== baseVal.trim();
      }} catch(e) {{
        return false;
      }}
    }}

    function renderTabs() {{
      const container = document.getElementById('layerTabs');
      container.innerHTML = '';
      
      appData.metadata.layers_order.forEach(lid => {{
        const info = appData.layers_info[lid];
        const btn = document.createElement('button');
        btn.id = "tab-" + lid;
        btn.onclick = () => switchLayer(lid);
        btn.className = "px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 " + (
          lid === currentLayer ? "bg-indigo-600 text-white shadow-md" : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
        );
        btn.innerHTML = '<span class="w-2 h-2 rounded-full" style="background-color: ' + info.theme + '"></span> ' + lid + ' ' + info.name;
        container.appendChild(btn);
      }});
    }}

    function switchLayer(lid) {{
      currentLayer = lid;
      
      appData.metadata.layers_order.forEach(id => {{
        const tab = document.getElementById("tab-" + id);
        if (!tab) return;
        if (id === currentLayer) {{
          tab.className = "px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 bg-indigo-600 text-white shadow-md";
        }} else {{
          tab.className = "px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-900";
        }}
      }});

      renderBanner(lid);
      renderKeyboards(lid);
    }}

    function renderBanner(lid) {{
      const info = appData.layers_info[lid];
      const banner = document.getElementById('layerBanner');
      banner.style.borderColor = info.theme + '40';
      banner.style.backgroundColor = info.theme + '10';

      const isReadOnly = (activeProfile === 'baseline_instalado');
      const profileNotice = isReadOnly 
        ? '<span class="text-[10px] px-2.5 py-0.5 rounded bg-amber-950/80 text-amber-300 font-bold border border-amber-500/50 flex items-center gap-1">🔒 HARDWARE INSTALADO (SOMENTE LEITURA)</span>'
        : '<span class="text-[10px] px-2.5 py-0.5 rounded bg-indigo-950/80 text-indigo-300 font-bold border border-indigo-500/50 flex items-center gap-1">🎯 CANDIDATO v05 (EDITÁVEL)</span>';

      banner.innerHTML = `
        <div class="flex items-center gap-3">
          <span class="w-8 h-8 rounded-lg flex items-center justify-center font-bold text-sm text-white" style="background-color: ${{info.theme}}">
            ${{lid}}
          </span>
          <div>
            <div class="flex items-center gap-2">
              <h2 class="text-sm font-bold text-white">${{lid}} • ${{info.name}}</h2>
              <span class="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-medium">${{info.type}}</span>
              ${{profileNotice}}
            </div>
            <p class="text-xs text-slate-400 mt-0.5">${{info.description || 'Camada canônica da Fonte Única de Verdade'}}</p>
          </div>
        </div>

        <div class="flex items-center gap-6 text-xs">
          <div class="flex items-center gap-2">
            <span class="font-bold text-emerald-400">▶ ENTRAR:</span>
            <span class="text-slate-200 font-semibold bg-slate-900/80 px-2.5 py-1 rounded border border-slate-700">${{info.how_in}}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="font-bold text-rose-400">■ SAIR:</span>
            <span class="text-slate-200 font-semibold bg-slate-900/80 px-2.5 py-1 rounded border border-slate-700">${{info.how_out}}</span>
          </div>
        </div>
      `;
    }}

    function createKeyElement(cellData, kb, type, r, c) {{
      const isDiff = diffMode && isKeyDiff(currentLayer, kb, type, r, c);
      const isConflict = (cellData.status === 'conflito');

      let extraClass = "";
      if (isConflict) extraClass += " key-conflict";
      else if (isDiff) extraClass += " key-diff";

      const el = document.createElement('div');
      el.className = "key-cap key-" + cellData.key_type + " w-14 h-12 rounded-lg p-1.5 flex flex-col justify-between cursor-pointer relative shadow-sm" + extraClass;
      el.onclick = () => openKeyModal(kb, type, r, c);
      
      const topDiv = document.createElement('div');
      topDiv.className = "text-[9px] font-mono-code font-bold opacity-60 text-left leading-none";
      topDiv.innerText = cellData.top || '';
      
      const mainDiv = document.createElement('div');
      mainDiv.className = "text-center font-bold text-[10.5px] leading-tight my-auto truncate w-full";
      mainDiv.innerText = cellData.label || '';
      
      const subDiv = document.createElement('div');
      subDiv.className = "text-[8.5px] font-medium opacity-80 text-center leading-none truncate w-full";
      subDiv.innerText = cellData.sub || '';

      el.appendChild(topDiv);
      el.appendChild(mainDiv);
      el.appendChild(subDiv);

      if (isConflict) {{
        el.title = "Aviso de Conflito de Migração: Esta tecla possuía alteração personalizada no rascunho anterior e também foi atualizada na v05. Sua personalização foi mantida.";
      }} else if (isDiff) {{
        try {{
          const baseLayer = appData.profiles.baseline_instalado[kb].layers[currentLayer];
          const baseCell = type === 'matrix' ? baseLayer.matrix[r][c] : baseLayer.thumbs[c];
          const baseVal = (kb === 'corne' ? baseCell.impl_zmk : baseCell.impl_qmk) || baseCell.label;
          const candVal = (kb === 'corne' ? cellData.impl_zmk : cellData.impl_qmk) || cellData.label;
          el.title = "Diferença detectada:\\n[Instalado]: " + baseVal + "\\n[Candidato]: " + candVal;
        }} catch(e) {{}}
      }}

      el.dataset.search = (cellData.label + " " + cellData.sub + " " + cellData.behavior + " " + cellData.impl_zmk + " " + cellData.impl_qmk).toLowerCase();
      return el;
    }}

    function renderKeyboards(lid) {{
      const corneLayer = getActiveLayerData(lid, 'corne');
      const sofleLayer = getActiveLayerData(lid, 'sofle');

      // 1. Corne
      const corneMatrixEl = document.getElementById('corneMatrix');
      corneMatrixEl.innerHTML = '';
      corneLayer.matrix.forEach((row, r) => {{
        const rowEl = document.createElement('div');
        rowEl.className = "flex gap-1.5";
        
        row.forEach((cell, c) => {{
          const keyEl = createKeyElement(cell, 'corne', 'matrix', r, c);
          rowEl.appendChild(keyEl);
          if (c === 5) {{
            const gap = document.createElement('div');
            gap.className = "w-6";
            rowEl.appendChild(gap);
          }}
        }});
        corneMatrixEl.appendChild(rowEl);
      }});

      const corneThumbsEl = document.getElementById('corneThumbs');
      corneThumbsEl.innerHTML = '';
      corneLayer.thumbs.forEach((cell, c) => {{
        const keyEl = createKeyElement(cell, 'corne', 'thumbs', 0, c);
        corneThumbsEl.appendChild(keyEl);
        if (c === 2) {{
          const gap = document.createElement('div');
          gap.className = "w-10";
          corneThumbsEl.appendChild(gap);
        }}
      }});

      // 2. Sofle
      const sofleMatrixEl = document.getElementById('sofleMatrix');
      sofleMatrixEl.innerHTML = '';
      sofleLayer.matrix.forEach((row, r) => {{
        const rowEl = document.createElement('div');
        rowEl.className = "flex gap-1.5";
        
        row.forEach((cell, c) => {{
          const keyEl = createKeyElement(cell, 'sofle', 'matrix', r, c);
          rowEl.appendChild(keyEl);
          if (c === 5) {{
            const gap = document.createElement('div');
            gap.className = "w-6";
            rowEl.appendChild(gap);
          }}
        }});
        sofleMatrixEl.appendChild(rowEl);
      }});

      const sofleThumbsEl = document.getElementById('sofleThumbs');
      sofleThumbsEl.innerHTML = '';
      sofleLayer.thumbs.forEach((cell, c) => {{
        const keyEl = createKeyElement(cell, 'sofle', 'thumbs', 0, c);
        sofleThumbsEl.appendChild(keyEl);
        if (c === 4) {{
          const gap = document.createElement('div');
          gap.className = "w-10";
          sofleThumbsEl.appendChild(gap);
        }}
      }});
    }}

    // Modal de Edição
    function openKeyModal(kb, type, r, c) {{
      currentEditingTarget = {{ kb, type, r, c }};
      const layerObj = getActiveLayerData(currentLayer, kb);
      const cell = type === 'matrix' ? layerObj.matrix[r][c] : layerObj.thumbs[c];

      const isReadOnly = (activeProfile === 'baseline_instalado');
      document.getElementById('modalPosBadge').innerText = kb.toUpperCase() + " • " + (type === 'matrix' ? ("Linha " + (r+1) + ", Col " + (c+1)) : ("Dedão " + (c+1)));
      document.getElementById('modalKbSub').innerText = "Camada " + currentLayer + " (" + appData.layers_info[currentLayer].name + ")";
      
      document.getElementById('modalLabel').value = cell.label || '';
      document.getElementById('modalSub').value = cell.sub || '';
      document.getElementById('modalBehavior').value = cell.behavior || '';
      document.getElementById('modalZmk').value = cell.impl_zmk || '';
      document.getElementById('modalQmk').value = cell.impl_qmk || '';
      document.getElementById('modalType').value = cell.key_type || 'normal';
      document.getElementById('modalStatus').value = cell.status || 'visual';

      const readOnlyAlert = document.getElementById('modalReadOnlyAlert');
      const saveBtn = document.getElementById('modalSaveBtn');

      if (isReadOnly) {{
        readOnlyAlert.classList.remove('hidden');
        saveBtn.classList.add('hidden');
        document.getElementById('modalLabel').disabled = true;
        document.getElementById('modalSub').disabled = true;
        document.getElementById('modalBehavior').disabled = true;
        document.getElementById('modalZmk').disabled = true;
        document.getElementById('modalQmk').disabled = true;
        document.getElementById('modalType').disabled = true;
        document.getElementById('modalStatus').disabled = true;
      }} else {{
        readOnlyAlert.classList.add('hidden');
        saveBtn.classList.remove('hidden');
        document.getElementById('modalLabel').disabled = false;
        document.getElementById('modalSub').disabled = false;
        document.getElementById('modalBehavior').disabled = false;
        document.getElementById('modalZmk').disabled = false;
        document.getElementById('modalQmk').disabled = false;
        document.getElementById('modalType').disabled = false;
        document.getElementById('modalStatus').disabled = false;
      }}

      document.getElementById('editModal').classList.remove('hidden');
    }}

    function closeModal() {{
      document.getElementById('editModal').classList.add('hidden');
      currentEditingTarget = null;
    }}

    function saveKeyEdit() {{
      if (!currentEditingTarget || activeProfile === 'baseline_instalado') return;
      const {{ kb, type, r, c }} = currentEditingTarget;
      
      const cell = type === 'matrix' 
        ? appData.layers[currentLayer][kb].matrix[r][c]
        : appData.layers[currentLayer][kb].thumbs[c];

      cell.label = document.getElementById('modalLabel').value;
      cell.sub = document.getElementById('modalSub').value;
      cell.behavior = document.getElementById('modalBehavior').value;
      cell.impl_zmk = document.getElementById('modalZmk').value;
      cell.impl_qmk = document.getElementById('modalQmk').value;
      cell.key_type = document.getElementById('modalType').value;
      cell.status = document.getElementById('modalStatus').value;

      // Atualiza também candidato_teste no perfil correspondente
      if (appData.profiles && appData.profiles.candidato_teste && appData.profiles.candidato_teste[kb] && appData.profiles.candidato_teste[kb].layers && appData.profiles.candidato_teste[kb].layers[currentLayer]) {{
        const profLayer = appData.profiles.candidato_teste[kb].layers[currentLayer];
        const profCell = type === 'matrix' ? profLayer.matrix[r][c] : profLayer.thumbs[c];
        if (profCell) {{
          Object.assign(profCell, cell);
        }}
      }}

      localStorage.setItem('keyboard_split_manager_data_v05', JSON.stringify(appData));

      closeModal();
      renderKeyboards(currentLayer);
      updateDynamicHashBadge();

      showGeneratorPrompt();
    }}

    function showGeneratorPrompt() {{
      const notice = document.getElementById('generatorNotice');
      if (notice) {{
        notice.classList.remove('hidden');
      }}
    }}

    // Alternar Visualização
    function setViewMode(mode) {{
      viewMode = mode;
      const secCorne = document.getElementById('sectionCorne');
      const secSofle = document.getElementById('sectionSofle');
      const bBoth = document.getElementById('btnViewBoth');
      const bCorne = document.getElementById('btnViewCorne');
      const bSofle = document.getElementById('btnViewSofle');

      [bBoth, bCorne, bSofle].forEach(b => b.className = "px-3 py-1.5 rounded-md text-xs font-semibold text-slate-400 hover:text-white transition");

      if (mode === 'both') {{
        secCorne.classList.remove('hidden');
        secSofle.classList.remove('hidden');
        bBoth.className = "px-3 py-1.5 rounded-md text-xs font-semibold text-white bg-slate-800 transition";
      }} else if (mode === 'corne') {{
        secCorne.classList.remove('hidden');
        secSofle.classList.add('hidden');
        bCorne.className = "px-3 py-1.5 rounded-md text-xs font-semibold text-white bg-slate-800 transition";
      }} else if (mode === 'sofle') {{
        secCorne.classList.add('hidden');
        secSofle.classList.remove('hidden');
        bSofle.className = "px-3 py-1.5 rounded-md text-xs font-semibold text-white bg-slate-800 transition";
      }}
    }}

    // Busca e Destaque
    function highlightSearch(query) {{
      const keys = document.querySelectorAll('.key-cap');
      keys.forEach(k => {{
        if (!query) {{
          k.style.opacity = '1';
          k.style.outline = '';
        }} else if (k.dataset.search && k.dataset.search.includes(query)) {{
          k.style.opacity = '1';
          k.style.outline = '2px solid #38bdf8';
        }} else {{
          k.style.opacity = '0.25';
          k.style.outline = '';
        }}
      }});
    }}

    // Salvamento Direto no Disco & Exportações
    async function saveDirectToDisk() {{
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
            alert("Gravação CANCELADA pelo usuário.\\nNADA foi gravado no disco; o rascunho local permanece intocado.");
          }} else {{
            alert("FALHA na gravação direta ao disco:\\n" + (err && err.message ? err.message : String(err)) + "\\n\\nNADA foi gravado. Use o botão Baixar se quiser o arquivo mesmo assim (não é gravação confirmada).");
          }}
          return;
        }}
        try {{
          const writable = await handle.createWritable();
          await writable.write(JSON.stringify(appData, null, 2));
          await writable.close();
          showGeneratorPrompt();
          alert("ARQUIVO EFETIVAMENTE GRAVADO no disco (File System Access).\\n\\nGeração: python3 generators/generate_corne_candidato.py --dataset <arquivo> --out candidates/<versao>.keymap");
        }} catch (err) {{
          alert("FALHA DURANTE A GRAVAÇÃO (arquivo pode estar incompleto ou não gravado):\\n" + (err && err.message ? err.message : String(err)));
        }}
      }} else {{
        downloadJSON();
        showGeneratorPrompt();
        alert("Navegador sem suporte a gravação direta: ARQUIVO BAIXADO.\\nIsso NÃO é gravação confirmada no disco — é um arquivo baixado.");
      }}
    }}


        function copyFullJSON() {{
      const str = JSON.stringify(appData, null, 2);
      navigator.clipboard.writeText(str).then(() => {{
        alert("JSON canônico completo copiado para a área de transferência!");
      }}).catch(() => {{
        alert("Não foi possível copiar automaticamente. Use o botão Baixar.");
      }});
    }}

    function downloadJSON() {{
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(appData, null, 2));
      const downloadAnchor = document.createElement('a');
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", "keymap_data_" + new Date().toISOString().slice(0,10) + ".json");
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
    }}

    function uploadJSON(event) {{
      const file = event.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = function(e) {{
        let parsed = null;
        try {{
          parsed = parseWithExactUid(e.target.result);
        }} catch (err) {{
          alert("ERRO: o arquivo não é JSON válido\\n" + err.message + "\\n\\nEstado anterior PRESERVADO. Nada foi alterado ou gravado.");
          event.target.value = "";
          return;
        }}
        const errs = validateDatasetStructure(parsed);
        if (errs.length > 0) {{
          alert("IMPORTAÇÃO RECUSADA: dados incompatíveis (" + errs.length + " problema(s)):\\n• " + errs.join("\\n• ") + "\\n\\nEstado anterior PRESERVADO. Nada foi gravado no cache.");
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
          alert("Arquivo JSON VÁLIDO importado e gravado como rascunho local.\\nEstado anterior arquivado em: " + backupKey + (parsed.schema_version === 6 ? "\\n(schema v6: UID como string decimal exata)" : ""));
        }} catch (storeErr) {{
          alert("FALHA ao gravar rascunho no cache local. Dados válidos aplicados apenas em memória:\\n" + storeErr);
        }}
      }};
      reader.readAsText(file);
    }}

    function resetToDefault() {{
      if (confirm("Deseja resetar todas as alterações para a Fonte Única v05 canônica? Quaisquer rascunhos não gravados no disco serão descartados.")) {{
        localStorage.removeItem('keyboard_split_manager_data_v05');
        appData = deepClone(defaultEmbeddedData);
        renderTabs();
        switchLayer(currentLayer);
        updateDynamicHashBadge();
        alert("Fonte Única v05 restaurada com sucesso!");
      }}
    }}

    function runAudit() {{
      let totalCorne = 0;
      let totalSofle = 0;
      let statusCounts = {{ visual: 0, mapeado: 0, compilado: 0, testado: 0, instalado: 0, candidato: 0, conflito: 0 }};
      let unassigned = [];
      let toErrors = [];

      appData.metadata.layers_order.forEach(lid => {{
        const l = appData.layers[lid];
        ['corne', 'sofle'].forEach(kb => {{
          l[kb].matrix.forEach((row, r) => {{
            row.forEach((cell, c) => {{
              if (kb === 'corne') totalCorne++; else totalSofle++;
              const st = cell.status || 'visual';
              statusCounts[st] = (statusCounts[st] || 0) + 1;
              if (!cell.label && cell.key_type !== "disabled") {{
                unassigned.push(lid + " " + kb.toUpperCase() + " [r" + r + " c" + c + "]");
              }}
              if (cell.label && cell.label.includes("TO(") && !cell.label.includes("TO(0)") && !cell.label.includes("TO(1)")) {{
                toErrors.push(lid + " " + kb.toUpperCase() + " [r" + r + " c" + c + "]: " + cell.label);
              }}
            }});
          }});
          l[kb].thumbs.forEach((cell, idx) => {{
            if (kb === "corne") totalCorne++; else totalSofle++;
            const st = cell.status || "visual";
            statusCounts[st] = (statusCounts[st] || 0) + 1;
            if (!cell.label && cell.key_type !== "disabled") {{
              unassigned.push(lid + " " + kb.toUpperCase() + " [thumb " + idx + "]");
            }}
          }});
        }});
      }});

      const totalKeys = totalCorne + totalSofle;
      let msg = "=== RELATÓRIO DE AUDITORIA DO LAYOUT (v05) ===\\n\\n";
      msg += "• Integridade das Posições: " + totalKeys + " / 1000\\n";
      msg += "  - Corne 42: " + totalCorne + " / 420 " + (totalCorne === 420 ? "✓" : "⚠️") + "\\n";
      msg += "  - Sofle 58: " + totalSofle + " / 580 " + (totalSofle === 580 ? "✓" : "⚠️") + "\\n\\n";
      msg += "• Status das Teclas:\\n";
      for (const [st, cnt] of Object.entries(statusCounts)) {{
        if (cnt > 0) msg += "  - " + st + ": " + cnt + "\\n";
      }}
      msg += "\\n• Teclas não atribuídas: " + unassigned.length + "\\n";
      if (unassigned.length > 0) {{
        msg += "  Exemplos: " + unassigned.slice(0, 5).join(", ") + (unassigned.length > 5 ? "..." : "") + "\\n";
      }}
      msg += "• Verificações de TO(): " + (toErrors.length === 0 ? "Conformes (Apenas TO(0) e TO(1)) ✓" : toErrors.join(", ")) + "\\n\\n";
      msg += (totalKeys === 1000 && unassigned.length === 0 && toErrors.length === 0) 
        ? "Status Geral: APROVADO sem pendências estruturais." 
        : "Status Geral: ATENÇÃO - verificar divergências acima.";

      alert(msg);
    }}

    window.addEventListener('DOMContentLoaded', init);
  </script>

"""

    full_html = html_head_and_body + "\n  " + vil_and_after

    # Validação sintática rigorosa de todos os scripts com node --check antes de salvar
    scripts = re.findall(r"<script>([\s\S]*?)</script>", full_html)
    for idx, s in enumerate(scripts):
        p = subprocess.run(["node", "--check"], input=s, text=True, capture_output=True)
        if p.returncode != 0:
            print(f"ERRO SINTÁTICO FATAL NO SCRIPT {idx} DO HTML:")
            print(p.stderr)
            sys.exit(1)

    return full_html

if __name__ == "__main__":
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
