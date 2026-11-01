
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
          const parsed = JSON.parse(v05Cache);
          if (parsed.schema_version === 5) {{
            appData = parsed;
          }} else {{
            promptMigration(parsed, 'v05_incompativel');
          }}
        }} catch (e) {{
          appData = deepClone(defaultEmbeddedData);
        }}
      }} else if (v04Cache || v03Cache) {{
        try {{
          const oldData = JSON.parse(v04Cache || v03Cache);
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

      let appliedCount = 0;
      let conflicts = [];

      // 4. Executa 3-Way Merge para Matriz e Dedões
      if (pendingMigrationData.layers) {{
        appData.metadata.layers_order.forEach(lid => {{
          ['corne', 'sofle'].forEach(kb => {{
            const draftKb = pendingMigrationData.layers?.[lid]?.[kb];
            const oldKb = legacyBaselineV03?.[lid]?.[kb];
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
                      // Conflito real: preserva a edição do usuário e marca status
                      Object.assign(cNew, cDraft);
                      cNew.status = 'conflito';
                      conflicts.push({{ lid, kb, pos: "Linha " + (r+1) + ", Col " + (c+1), draft: cDraft, newBase: cNew }});
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
                    Object.assign(cNew, cDraft);
                    cNew.status = 'conflito';
                    conflicts.push({{ lid, kb, pos: "Dedão " + (idx+1), draft: cDraft, newBase: cNew }});
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
        alert("Migração 3-Way concluída!\\n\\n• " + appliedCount + " personalizações incorporadas.\\n• " + conflicts.length + " conflitos detectados (suas personalizações foram preservadas e sinalizadas):\\n" + conflicts.map(c => "  - [" + c.lid + "] " + c.kb.toUpperCase() + " " + c.pos + ": Rascunho \\"" + c.draft.label + "\\" vs v05 \\"" + c.newBase.label + "\\"").join("\\n"));
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
          diffs.map(d => '<div class="p-1.5 rounded bg-slate-950 border border-slate-800 text-[11px]">' + d + '</div>').join('');
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
      try {{
        if ('showSaveFilePicker' in window) {{
          const handle = await window.showSaveFilePicker({{
            suggestedName: 'keymap_data.json',
            types: [{{
              description: 'JSON Fonte Única de Verdade',
              accept: {{ 'application/json': ['.json'] }}
            }}]
          }});
          const writable = await handle.createWritable();
          await writable.write(JSON.stringify(appData, null, 2));
          await writable.close();
          showGeneratorPrompt();
          alert("Arquivo 'keymap_data.json' salvo diretamente no disco com sucesso!\\n\\nExecute no terminal para gerar o arquivo .keymap:\\npython3 generate_corne_from_json.py\\n(Nota: este comando gera o .keymap a partir da Fonte Única; não compila o firmware binário UF2).");
        }} else {{
          downloadJSON();
          showGeneratorPrompt();
        }}
      }} catch (err) {{
        if (err.name !== 'AbortError') {{
          downloadJSON();
          showGeneratorPrompt();
        }}
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
  