/* Keyboard Split Manager v06 — lógica do app (fonte modular, embutida no HTML pelo gerador). */
(function () {
  "use strict";

  const EMBEDDED = JSON.parse(document.getElementById("ksm-data").textContent);
  const DRAFT_KEY = "ksm_v06_draft";
  const DRAFT_V18_KEY = "ksm_v18_profiles_draft";
  const HISTORY_KEY = "ksm_v06_history";
  const HISTORY_V18_KEY = "ksm_v18_profiles_history";
  const LEGACY_KEYS = [
    ["ksm_v17_profiles_draft", "v17"],
    ["ksm_v16_profiles_draft", "v16"],
    ["keyboard_split_manager_data_v05", "v05"],
    ["keyboard_split_manager_data_v04", "v04"],
    ["keyboard_split_manager_data_v03", "v03"],
  ];
  const MAX_IMPORT_BYTES = 5 * 1024 * 1024;
  const MAX_HISTORY = 30;

  let appData = deepClone(EMBEDDED);
  let activeKeyboard = "corne";
  let activeProfile = "simple";
  let activeLayer = "L0";
  let editingTarget = null;
  let dirty = false;
  let fileBaselineString = canonicalString(appData);
  let sourceName = "keymap_data_v06.json (dataset embutido)";
  let fileStatus = "not_confirmed";
  let lastDraftAt = null;
  let lastDownloadAt = null;
  let pendingMigration = null;
  let history = [];
  let legacyFound = [];

  // Zoom & Teclas (copiar, mover, trocar)
  let currentZoom = 1.0;
  let copiedKeyData = null; // { kb, pos, layerId, data: { label, sub, behavior, impl_zmk, impl_qmk, key_type, status, top, binding } }

  // ------------------------------------------------------------ utilidades
  function $(id) { return document.getElementById(id); }
  function deepClone(o) { return JSON.parse(JSON.stringify(o)); }
  function nowISO() { return new Date().toISOString(); }
  function fmtDate(iso) {
    try { return new Date(iso).toLocaleString("pt-BR"); } catch (e) { return iso; }
  }
  function chip(el, text, cls) {
    el.textContent = text;
    el.className = "chip" + (cls ? " " + cls : "");
  }
  function cellText(cell, kb) {
    const v = kb === "corne" ? (cell && cell.impl_zmk) : (cell && cell.impl_qmk);
    return String(v || (cell && cell.label) || "").trim();
  }
  function cellKey(cell) {
    if (!cell) return "";
    return [cell.label || "", cell.sub || "", cell.behavior || "", cell.impl_zmk || "", cell.impl_qmk || "", cell.key_type || "", cell.status || ""].join("\u0001");
  }
  // validateDataset/layerRows/layerThumbs/flatLayer vivem em ksm_core.js (fonte única, testável em Node)

  function migrationBaseline(draft) {
    const legacy = (appData.metadata && appData.metadata.legacy_baselines) || (EMBEDDED.metadata && EMBEDDED.metadata.legacy_baselines) || {};
    const v = String((draft && draft.version) || "");
    if (draft && (draft.schema_version === 3 || v.indexOf("v03") === 0)) return legacy.v03 || null;
    if (draft && (draft.schema_version === 5 || v.indexOf("v05") === 0)) return legacy.v05 || null;
    return null;
  }

  // ------------------------------------------------------------ estado
  function markDirty() {
    dirty = canonicalString(appData) !== fileBaselineString;
    updateChips();
  }

  async function updateChips() {
    chip($("chipDirty"), dirty ? "Alterações NÃO salvas no arquivo" : "Sem alterações não salvas", dirty ? "warn" : "ok");
    chip($("chipSource"), "Fonte: " + sourceName, "ref");
    if (lastDraftAt) chip($("chipDirty"), (dirty ? "Alterações NÃO salvas no arquivo" : "Sem alterações não salvas") + " · rascunho " + fmtDate(lastDraftAt), dirty ? "warn" : "ok");
    const n = Array.isArray(appData.conflicts) ? appData.conflicts.length : 0;
    chip($("chipConflicts"), "Conflitos pendentes: " + n, n ? "bad" : "ok");
    chip($("chipFile"), fileStatus === "confirmed" ? "Arquivo em disco: confirmado" : "Arquivo em disco: não confirmado", fileStatus === "confirmed" ? "ok" : "warn");
    try {
      const h = await canonicalHashAsync(appData);
      chip($("chipHash"), "Hash canônico: " + h.slice(0, 12), "ok");
    } catch (e) {
      chip($("chipHash"), "Hash indisponível", "bad");
    }
  }

  function renderMeta() {
    $("metaDataset").textContent = (appData.project || "Keyboard Split Manager") + " · schema " + appData.schema_version;
    $("metaVersion").textContent = appData.version || "—";
    $("metaUid").textContent = uidText(appData) || "—";
    $("metaGenFile").textContent = activeProfile === "simple" ? "Corne_Simples_ZMK_v01/scripts/generate_keymap.py (no pacote)" : "ksm-work/data/keymap_data_v06.json";
  }

  function showBanner() {
    const b = $("banner");
    b.textContent = "";
    if (pendingMigration) {
      const d = document.createElement("div");
      d.className = "notice warn";
      d.appendChild(textP("Rascunho antigo detectado (" + (pendingMigration.label || "versão anterior") + "). Nada foi alterado no estado atual."));
      const row = document.createElement("div");
      row.className = "toolbar";
      row.appendChild(btn("Migrar com referência histórica", () => runMigration(), "warn"));
      row.appendChild(btn("Arquivar rascunho", () => archivePending(), ""));
      row.appendChild(btn("Baixar rascunho", () => downloadObject(pendingMigration.data, "rascunho_antigo.json"), ""));
      row.appendChild(btn("Manter estado atual", () => { pendingMigration = null; showBanner(); }, ""));
      d.appendChild(row);
      b.appendChild(d);
    }
    const n = Array.isArray(appData.conflicts) ? appData.conflicts.length : 0;
    if (n > 0) {
      const d = document.createElement("div");
      d.className = "notice bad";
      d.appendChild(textP(n + " conflito(s) de migração pendente(s). A geração e o download final ficam bloqueados até resolver cada um com uma alternativa independente."));
      d.appendChild(btn("Resolver conflitos", () => openConflicts(), "danger"));
      b.appendChild(d);
    }
    if (dirty) {
      const d = document.createElement("div");
      d.className = "notice warn";
      d.appendChild(textP("Existem alterações em memória/rascunho que NÃO foram confirmadas no arquivo do projeto. Use “Gravar no arquivo…” e confirme o nome do arquivo."));
      b.appendChild(d);
    }
    if (activeProfile === "simple") {
      const d = document.createElement("div"); d.className = "notice";
      d.textContent = "Corne Simples: perfil independente. O mapa antigo e o Sofle continuam salvos. Internacional informado: ç por Opt+C na Base; agudo por Opt+E e trema por Opt+U. Validar os dois acentos no Mac. BASE: Shift+Enter na lateral inferior esquerda. Em NAV/MOUSE, a mesma posição mantém o Lock de dois toques. O HTML não lê nem grava o teclado. Os UF2 v01 não incluem Shift+Enter; configure no Studio ou recompile. Validação física completa pendente.";
      b.appendChild(d);
    }
    if (appData.profiles && appData.profiles.corne_simples_anterior) {
      const d = document.createElement("div"); d.className = "notice";
      d.textContent = "O rascunho anterior do Corne Simples foi preservado. Ele está incluído no JSON exportado e disponível em Comparar como Simples anterior. O novo perfil usa a organização revisada por mão.";
      b.appendChild(d);
    }
    if (!b.children.length) b.textContent = "";
  }

  function textP(t) { const p = document.createElement("div"); p.className = "small"; p.textContent = t; return p; }
  function btn(label, fn, cls) {
    const b = document.createElement("button");
    b.textContent = label;
    if (cls) b.className = cls;
    b.addEventListener("click", fn);
    return b;
  }

  // ------------------------------------------------------------ dados de camada
  function simpleProfile(d) {
    const p = (d || appData).profiles;
    return p && p.corne_simples_v01;
  }

  function ensureSimpleProfile(d) {
    if (!d.profiles) d.profiles = {};
    const emb = simpleProfile(EMBEDDED);
    const embeddedRev = (emb && emb.design_revision) || 13;
    if (!d.profiles.corne_simples_v01) {
      if (emb) d.profiles.corne_simples_v01 = deepClone(emb);
    } else if ((d.profiles.corne_simples_v01.design_revision || 1) < embeddedRev) {
      if (d.profiles.corne_simples_anterior) {
        if (!Array.isArray(d.profiles.corne_simples_arquivados)) d.profiles.corne_simples_arquivados = [];
        d.profiles.corne_simples_arquivados.push(deepClone(d.profiles.corne_simples_anterior));
      }
      d.profiles.corne_simples_anterior = deepClone(d.profiles.corne_simples_v01);
      if (emb) d.profiles.corne_simples_v01 = deepClone(emb);
    }
    return d;
  }

  function profileInfo(lid) {
    return activeProfile === "simple" ? simpleProfile().layers_info[lid] : appData.layers_info && appData.layers_info[lid];
  }

  function renderProfiles() {
    if (activeKeyboard !== "corne" && activeProfile === "simple") activeProfile = "candidate";
    for (const b of $("profileGroup").children) {
      b.hidden = b.dataset.profile === "simple" && activeKeyboard !== "corne";
      b.classList.toggle("sel", b.dataset.profile === activeProfile);
      b.setAttribute("aria-pressed", String(b.dataset.profile === activeProfile));
    }
  }

  function candidateLayer(lid, kb, profile) {
    if ((profile || activeProfile) === "simple") return kb === "corne" ? simpleProfile().layers[lid] : null;
    const lay = appData.layers && appData.layers[lid];
    return lay && lay[kb] ? lay[kb] : null;
  }

  function vilToBoard(vil, idx) {
    const g = vil.layout[idx];
    const matrix = [];
    for (let r = 0; r < 4; r++) {
      matrix.push(g[r].slice(0, 6).concat(g[r + 5].slice(0, 6).reverse()));
    }
    const thumbs = g[4].slice(0, 5).concat(g[9].slice(0, 5).reverse());
    const mk = (v, pos) => ({
      top: "", label: String(v), sub: "", behavior: "binding cru do .vil", binding: String(v),
      impl_zmk: "", impl_qmk: String(v), key_type: "normal", status: "reference", position: pos, source: "reference",
    });
    return {
      matrix: matrix.map((row, r) => row.map((v, c) => mk(v, r * 12 + c))),
      thumbs: thumbs.map((v, i) => mk(v, 48 + i)),
      encoders: {
        left: { click: g[4][5], rot: vil.encoder_layout[idx] && vil.encoder_layout[idx][0] },
        right: { click: g[9][5], rot: vil.encoder_layout[idx] && vil.encoder_layout[idx][1] },
      },
    };
  }

  function referenceLayer(lid, kb) {
    if (kb === "corne") {
      const l = appData.references.corne.native_layers[lid];
      return l ? { matrix: l.matrix, thumbs: l.thumbs } : null;
    }
    const idx = parseInt(String(lid).replace(/^L/, ""), 10);
    return vilToBoard(appData.references.sofle.vil, idx);
  }

  function activeLayerData() {
    if (activeProfile === "reference") return referenceLayer(activeLayer, activeKeyboard);
    return candidateLayer(activeLayer, activeKeyboard);
  }

  function layerIds() {
    if (activeProfile === "reference") {
      return activeKeyboard === "corne"
        ? Object.keys(appData.references.corne.native_layers)
        : Array.from({ length: 16 }, (_, i) => "L" + i);
    }
    if (activeProfile === "simple") {
      const sp = simpleProfile();
      if (sp && sp.layers_order) return sp.layers_order.slice();
      activeProfile = "candidate";
    }
    return (appData.metadata && appData.metadata.layers_order) ? appData.metadata.layers_order.slice() : [];
  }

  // ------------------------------------------------------------ render
  function renderTabs() {
    const ids = layerIds();
    if (!ids.includes(activeLayer)) activeLayer = ids[0];
    const tabs = $("layerTabs");
    tabs.textContent = "";
    for (const lid of ids) {
      const b = document.createElement("button");
      b.className = "tab" + (lid === activeLayer ? " sel" : "");
      b.dataset.layer = lid;
      let label = lid;
      if (activeProfile !== "reference") {
        const info = profileInfo(lid);
        label = lid + " " + ((info && info.name) || "");
      } else if (activeKeyboard === "corne") {
        label = lid;
      }
      b.textContent = label;
      b.addEventListener("click", () => { activeLayer = lid; renderAll(); });
      tabs.appendChild(b);
    }
  }

  function renderInfo() {
    const info = $("layerInfo");
    info.textContent = "";
    if (activeProfile !== "reference") {
      const li = profileInfo(activeLayer) || {};
      info.appendChild(kv("Perfil", activeProfile === "simple" ? ((simpleProfile().name || "Corne Simples v13") + " (novo)") : "Mapa antigo"));
      info.appendChild(kv("Camada", activeLayer + " · " + (li.name || "")));
      info.appendChild(kv("Entrar", li.how_in || "—"));
      info.appendChild(kv("Sair", li.how_out || "—"));
      info.appendChild(kv("Tipo", li.type || "—"));
      if (activeProfile === "simple" && li.description) info.appendChild(kv("Organização", li.description));
    } else {
      info.appendChild(kv("Perfil", "Referência somente leitura"));
      info.appendChild(kv("Camada", activeLayer));
      info.appendChild(kv("Origem", activeKeyboard === "corne" ? "devicetree ZMK" : "SOFLE_FINAL_HOMOLOGADO_v01.vil"));
      info.appendChild(kv("Aviso", activeKeyboard === "corne" ? "Não comprova o mapa dinâmico ativo no ZMK Studio" : "16 camadas preservadas; não reduzir a 580 posições"));
    }
  }
  function kv(k, v) {
    const s = document.createElement("span");
    const b = document.createElement("b"); b.textContent = k + ": "; s.appendChild(b);
    s.appendChild(document.createTextNode(String(v)));
    return s;
  }

  function makeKey(cell, kb, type, r, c, pos) {
    const el = document.createElement("div");
    el.dataset.pos = String(pos);
    const kt = (cell && cell.key_type) || "normal";
    el.className = "key " + (["normal", "hold", "active", "warn", "disabled"].includes(kt) ? kt : "normal");
    if (cell && cell.status === "conflict") el.classList.add("conflict");
    const top = document.createElement("div"); top.className = "top"; top.textContent = (cell && cell.top) || "";
    const lbl = document.createElement("div"); lbl.className = "lbl"; lbl.textContent = (cell && cell.label) || "";
    const sub = document.createElement("div"); sub.className = "sub"; sub.textContent = (cell && cell.sub) || "";
    const code = document.createElement("div"); code.className = "code";
    code.textContent = (cell && (kb === "corne" ? cell.impl_zmk : cell.impl_qmk)) || "";
    const pin = document.createElement("div"); pin.className = "pin"; pin.textContent = String(pos);
    el.appendChild(pin); el.appendChild(top); el.appendChild(lbl); el.appendChild(sub); el.appendChild(code);
    el.title = "pos " + pos + "\n" + ((cell && cell.behavior) || "") + "\nZMK: " + ((cell && cell.impl_zmk) || "") + "\nQMK/Vial: " + ((cell && cell.impl_qmk) || "");
    el.addEventListener("click", () => {
      if (activeProfile === "reference") { alert("Perfil de referência é somente leitura."); return; }
      openEdit(kb, type, r, c, pos);
    });
    return el;
  }

  function renderBoard() {
    const lay = activeLayerData();
    const wrap = $("boardWrap");
    wrap.textContent = "";
    if (!lay) { wrap.appendChild(textP("Camada indisponível.")); return; }

    if (activeKeyboard === "sofle" && lay.encoders) wrap.appendChild(renderEncoders(lay.encoders));

    const board = document.createElement("div");
    board.className = "board";
    lay.matrix.forEach((row, r) => {
      const rowEl = document.createElement("div");
      rowEl.className = "row";
      row.forEach((cell, c) => {
        rowEl.appendChild(makeKey(cell, activeKeyboard, "matrix", r, c, r * 12 + c));
        if (c === 5) { const g = document.createElement("div"); g.className = "gap"; rowEl.appendChild(g); }
      });
      board.appendChild(rowEl);
    });
    const tEl = document.createElement("div");
    tEl.className = "thumbs";
    lay.thumbs.forEach((cell, i) => {
      tEl.appendChild(makeKey(cell, activeKeyboard, "thumbs", 0, i, (activeKeyboard === "corne" ? 36 : 48) + i));
      if (i === (activeKeyboard === "corne" ? 2 : 4)) { const g = document.createElement("div"); g.className = "gap"; tEl.appendChild(g); }
    });
    board.appendChild(tEl);
    wrap.appendChild(board);

    if (activeKeyboard === "sofle") {
      const n = document.createElement("div");
      n.className = "small";
      n.style.marginTop = "6px";
      n.textContent = "Posições 48–52 (esquerda) e 53–57 (direita) são os dez dedões; os cliques dos encoders ficam em (4,5) e (9,5), preservados do .vil.";
      wrap.appendChild(n);
    }
  }

  function renderEncoders(enc) {
    const box = document.createElement("div");
    box.className = "encoders";
    for (const side of ["left", "right"]) {
      const e = enc[side];
      if (!e) continue;
      const d = document.createElement("div");
      d.className = "enc";
      const rot = Array.isArray(e.rot) ? e.rot.join(" / ") : "—";
      d.textContent = (side === "left" ? "Encoder E" : "Encoder D") + " · clique: " + e.click + " · giro: " + rot;
      box.appendChild(d);
    }
    return box;
  }

  function renderAll() {
    renderProfiles();
    renderMeta();
    renderTabs();
    renderInfo();
    renderBoard();
    showBanner();
    updateChips();
  }

  // ------------------------------------------------------------ zoom
  function applyZoom(lvl) {
    currentZoom = Math.min(2.5, Math.max(0.6, Math.round(lvl * 100) / 100));
    document.documentElement.style.setProperty("--board-zoom", String(currentZoom));
    const txt = $("zoomLevelText");
    if (txt) txt.textContent = Math.round(currentZoom * 100) + "%";
    try {
      localStorage.setItem("ksm_board_zoom", String(currentZoom));
    } catch (e) { /* ignore */ }
  }

  function initZoom() {
    let saved = 1.0;
    try {
      const raw = localStorage.getItem("ksm_board_zoom");
      if (raw) {
        const p = parseFloat(raw);
        if (!isNaN(p) && p >= 0.5 && p <= 3.0) saved = p;
      }
    } catch (e) { /* ignore */ }
    applyZoom(saved);
  }

  // ------------------------------------------------------------ coordenadas / cópia / troca
  function posToCoords(pos, kb) {
    if (kb === "corne") {
      if (pos >= 0 && pos < 36) return { type: "matrix", r: Math.floor(pos / 12), c: pos % 12 };
      if (pos >= 36 && pos < 42) return { type: "thumbs", r: 0, c: pos - 36 };
    } else {
      if (pos >= 0 && pos < 48) return { type: "matrix", r: Math.floor(pos / 12), c: pos % 12 };
      if (pos >= 48 && pos < 58) return { type: "thumbs", r: 0, c: pos - 48 };
    }
    return null;
  }

  function getCellByPos(lay, pos, kb) {
    if (!lay) return null;
    const coords = posToCoords(pos, kb);
    if (!coords) return null;
    return coords.type === "matrix" ? lay.matrix[coords.r][coords.c] : lay.thumbs[coords.c];
  }

  function cloneCellData(src) {
    if (!src) return null;
    return JSON.parse(JSON.stringify(src));
  }

  function assignCellData(dest, src) {
    if (!dest || !src) return;
    // Remove todas as chaves do destino para evitar que campos opcionais (ex.: binding) permaneçam como resíduos
    for (const k of Object.keys(dest)) {
      delete dest[k];
    }
    // Copia todos os campos de src de maneira limpa
    for (const [k, v] of Object.entries(src)) {
      if (v !== undefined) {
        dest[k] = (typeof v === "object" && v !== null) ? JSON.parse(JSON.stringify(v)) : v;
      }
    }
    if (!dest.key_type) dest.key_type = "normal";
    if (!dest.status) dest.status = "candidato";
  }

  function swapCells(cellA, cellB) {
    const temp = cloneCellData(cellA);
    assignCellData(cellA, cellB);
    assignCellData(cellB, temp);
  }

  function updateClipboardUI() {
    const pill = $("clipboardPill");
    const lbl = $("clipKeyLabel");
    const btnPaste = $("btnPasteKey");
    if (copiedKeyData && copiedKeyData.data) {
      if (pill) pill.style.display = "inline-flex";
      if (lbl) {
        lbl.textContent = (copiedKeyData.data.label || "Tecla") + " (pos " + copiedKeyData.pos + ")";
        lbl.title = "Tecla copiada de " + copiedKeyData.kb.toUpperCase() + " · " + copiedKeyData.layerId + " · pos " + copiedKeyData.pos + "\n" +
          (copiedKeyData.data.behavior || "") + " | ZMK: " + (copiedKeyData.data.impl_zmk || "—") + " | QMK: " + (copiedKeyData.data.impl_qmk || "—");
      }
      if (btnPaste) btnPaste.disabled = false;
    } else {
      if (pill) pill.style.display = "none";
      if (btnPaste) btnPaste.disabled = true;
    }
  }

  function copyCurrentEditingKey() {
    if (!editingTarget) return;
    const t = editingTarget;
    const lay = candidateLayer(t.layerId, t.kb, t.profile);
    const cell = (t.type === "matrix" ? lay.matrix[t.r][t.c] : lay.thumbs[t.c]) || {};
    const keyData = {
      label: $("editLabel").value.trim(),
      sub: $("editSub").value.trim(),
      behavior: $("editBehavior").value.trim(),
      impl_zmk: $("editZmk").value.trim(),
      impl_qmk: $("editQmk").value.trim(),
      key_type: $("editType").value,
      status: $("editStatus").value,
    };
    if (cell.binding !== undefined || t.kb === "corne") keyData.binding = keyData.impl_zmk;
    if (cell.top !== undefined) keyData.top = keyData.label;
    copiedKeyData = {
      kb: t.kb,
      pos: t.pos,
      layerId: t.layerId,
      data: keyData
    };
    $("copyKeyFeedback").textContent = "✓ Copiada!";
    updateClipboardUI();
  }

  function pasteIntoCurrentEditingKey() {
    if (!editingTarget || !copiedKeyData || !copiedKeyData.data) return;
    const d = copiedKeyData.data;
    $("editLabel").value = d.label || "";
    $("editSub").value = d.sub || "";
    $("editBehavior").value = d.behavior || "";
    $("editZmk").value = d.impl_zmk || "";
    $("editQmk").value = d.impl_qmk || "";
    $("editType").value = d.key_type || "normal";
    $("editStatus").value = d.status || "candidato";
    $("copyKeyFeedback").textContent = "✓ Dados colados no formulário!";
  }

  function openMoveFromEdit() {
    if (!editingTarget) return;
    const srcPos = editingTarget.pos;
    $("dlgEdit").close();
    openMoveKeyDialog(srcPos);
  }

  function openMoveKeyDialog(defaultSrcPos) {
    if (activeProfile === "reference") {
      alert("Perfil de referência é somente leitura. Selecione um perfil editável para mover ou trocar teclas.");
      return;
    }
    const kb = activeKeyboard;
    const curLay = candidateLayer(activeLayer, kb, activeProfile);
    const totalKeys = kb === "corne" ? 42 : 58;

    const pName = activeProfile === "simple" ? "Corne Simples" : kb.toUpperCase();
    $("moveKeyTitle").textContent = "Mover / Trocar Teclas · " + pName;

    const makeOptions = (selEl) => {
      selEl.textContent = "";
      for (let p = 0; p < totalKeys; p++) {
        const cell = getCellByPos(curLay, p, kb);
        let posLabel = "Pos " + p;
        if (kb === "corne") {
          if (p >= 36) posLabel = "Dedão " + (p < 39 ? "E" : "D") + (p < 39 ? (p - 35) : (p - 38)) + " (pos " + p + ")";
        } else if (kb === "sofle") {
          if (p >= 48) posLabel = "Dedão " + (p < 53 ? "E" : "D") + (p < 53 ? (p - 47) : (p - 52)) + " (pos " + p + ")";
        }
        const lbl = (cell && cell.label) || "—";
        const sub = (cell && cell.sub) ? " · " + cell.sub : "";
        const code = (cell && (kb === "corne" ? cell.impl_zmk : cell.impl_qmk)) || "";
        const opt = document.createElement("option");
        opt.value = String(p);
        opt.textContent = posLabel + ": [" + lbl + "]" + sub + (code ? " · " + code : "");
        selEl.appendChild(opt);
      }
    };

    makeOptions($("moveKeySrc"));
    makeOptions($("moveKeyDest"));

    let sPos = (typeof defaultSrcPos === "number" && defaultSrcPos >= 0 && defaultSrcPos < totalKeys) ? defaultSrcPos : 0;
    let dPos = (sPos === 0 ? 1 : 0);
    $("moveKeySrc").value = String(sPos);
    $("moveKeyDest").value = String(dPos);

    updateMoveKeyInfo();
    $("dlgMoveKey").showModal();
  }

  function updateMoveKeyInfo() {
    const kb = activeKeyboard;
    const curLay = candidateLayer(activeLayer, kb, activeProfile);
    const srcPos = parseInt($("moveKeySrc").value, 10);
    const destPos = parseInt($("moveKeyDest").value, 10);
    const srcCell = getCellByPos(curLay, srcPos, kb);
    const destCell = getCellByPos(curLay, destPos, kb);

    const fmtCell = (c) => {
      if (!c) return "—";
      return "[" + (c.label || "—") + "] " + (c.sub ? "· " + c.sub : "") +
        " | ZMK: " + (c.impl_zmk || "—") + " | QMK: " + (c.impl_qmk || "—") +
        (c.behavior ? " | " + c.behavior : "");
    };

    $("moveKeySrcInfo").textContent = fmtCell(srcCell);
    $("moveKeyDestInfo").textContent = fmtCell(destCell);

    const mode = $("moveKeyMode").value;
    const scope = $("moveKeyScope").value;
    const summary = $("moveKeySummary");

    if (srcPos === destPos) {
      summary.className = "notice bad";
      summary.innerHTML = "⚠️ A origem e o destino são a mesma tecla (posição " + srcPos + "). Selecione posições diferentes.";
      return;
    }

    summary.className = "notice ok";
    let text = "";
    if (mode === "swap") {
      if (scope === "current") {
        text = "⇄ <b>Troca (Swap) na camada atual (" + activeLayer + "):</b> As posições <b>" + srcPos + "</b> e <b>" + destPos + "</b> inverterão seus atributos apenas nesta camada.";
      } else {
        text = "⇄ <b>Troca (Swap) em TODAS as camadas (L0 a L9):</b> As posições <b>" + srcPos + "</b> e <b>" + destPos + "</b> inverterão todas as suas funções, rótulos e comportamentos em todas as 10 camadas do " + kb.toUpperCase() + ".";
      }
    } else {
      if (scope === "current") {
        text = "📋 <b>Substituição / Cópia na camada atual (" + activeLayer + "):</b> A posição <b>" + destPos + "</b> receberá todos os atributos da posição <b>" + srcPos + "</b>. O conteúdo anterior de " + destPos + " será sobrescrito nesta camada.";
      } else {
        text = "📋 <b>Substituição / Cópia em TODAS as camadas (L0 a L9):</b> A posição <b>" + destPos + "</b> receberá todos os atributos e funções da posição <b>" + srcPos + "</b> em todas as 10 camadas do " + kb.toUpperCase() + ".";
      }
    }
    summary.innerHTML = text;
  }

  async function executeMoveKey() {
    const kb = activeKeyboard;
    const srcPos = parseInt($("moveKeySrc").value, 10);
    const destPos = parseInt($("moveKeyDest").value, 10);
    const mode = $("moveKeyMode").value;
    const scope = $("moveKeyScope").value;

    if (srcPos === destPos) {
      alert("Selecione duas posições diferentes para origem e destino.");
      return;
    }

    // REGISTRA O ESTADO ANTERIOR NO HISTÓRICO ANTES DA ALTERAÇÃO
    // Permite que "Restaurar" no Histórico desfaça a operação e retorne ao estado imediatamente anterior!
    const preSnapshot = deepClone(appData);
    const opDesc = (mode === "swap" ? "troca" : "cópia") + " pos " + srcPos + (mode === "swap" ? " ⇄ " : " → ") + destPos + " (" + (scope === "all" ? "todas as camadas" : activeLayer) + ")";
    const histOk = await pushHistory("antes de " + opDesc, preSnapshot);
    if (!histOk) {
      alert("Falha ao registrar ponto de restauração no histórico (armazenamento cheio ou indisponível). Operação cancelada para evitar perda do estado anterior.");
      return;
    }

    const order = activeProfile === "simple"
      ? simpleProfile().layers_order.slice()
      : ((appData.metadata && appData.metadata.layers_order) || Object.keys(appData.layers || {}));
    const targetLayers = scope === "all" ? order : [activeLayer];

    for (const lid of targetLayers) {
      const lay = candidateLayer(lid, kb, activeProfile);
      if (!lay) continue;
      const cellA = getCellByPos(lay, srcPos, kb);
      const cellB = getCellByPos(lay, destPos, kb);
      if (!cellA || !cellB) continue;

      if (mode === "swap") {
        swapCells(cellA, cellB);
      } else {
        assignCellData(cellB, cellA);
      }

      if (activeProfile === "simple") {
        simpleProfile().firmware_status = "modified_requires_rebuild";
      } else {
        const mirror = appData.profiles && appData.profiles.candidato_teste && appData.profiles.candidato_teste[kb] && appData.profiles.candidato_teste[kb].layers;
        if (mirror && mirror[lid]) {
          const ml = mirror[lid];
          const mcA = getCellByPos(ml, srcPos, kb);
          const mcB = getCellByPos(ml, destPos, kb);
          if (mcA && mcB) {
            if (mode === "swap") swapCells(mcA, mcB);
            else assignCellData(mcB, mcA);
          }
        }
      }
    }

    dirty = canonicalString(appData) !== fileBaselineString;
    saveDraft(opDesc);
    $("dlgMoveKey").close();
    renderAll();
  }

  // ------------------------------------------------------------ edição
  function openEdit(kb, type, r, c, pos) {
    const lay = candidateLayer(activeLayer, kb, activeProfile);
    if (!lay) return;
    const cell = type === "matrix" ? lay.matrix[r][c] : lay.thumbs[c];
    editingTarget = { kb, type, r, c, layerId: activeLayer, pos, profile: activeProfile };
    const pName = activeProfile === "simple" ? "Corne Simples" : kb.toUpperCase();
    $("editTitle").textContent = "Editar " + pName + " · " + activeLayer + " · posição " + pos;
    $("editLabel").value = cell.label || "";
    $("editSub").value = cell.sub || "";
    $("editBehavior").value = cell.behavior || "";
    $("editZmk").value = cell.impl_zmk || "";
    $("editQmk").value = cell.impl_qmk || "";
    $("editType").value = cell.key_type || "normal";
    $("editStatus").value = cell.status || "candidato";
    $("editMsg").textContent = "";
    $("copyKeyFeedback").textContent = "";
    updateClipboardUI();
    $("dlgEdit").showModal();
  }

  async function saveEdit() {
    if (!editingTarget) return;
    const t = editingTarget;
    const label = $("editLabel").value.trim();
    const zmk = $("editZmk").value.trim();
    const qmk = $("editQmk").value.trim();
    if (!label) { $("editMsg").textContent = "Rótulo não pode ficar vazio."; return; }
    if (zmk.length > 200 || qmk.length > 200) { $("editMsg").textContent = "Código excessivamente longo."; return; }

    if (t.kb === "corne") {
      if (!zmk.startsWith("&")) {
        $("editMsg").textContent = "No Corne, o binding ZMK deve começar com & (ex.: &kp S).";
        return;
      }
    } else if (t.kb === "sofle") {
      if (!qmk) {
        $("editMsg").textContent = "No Sofle, o código Vial/QMK não pode ficar vazio.";
        return;
      }
      if (zmk && !zmk.startsWith("&")) {
        $("editMsg").textContent = "Se informado no Sofle, o binding ZMK deve começar com &.";
        return;
      }
    }

    const preSnapshot = deepClone(appData);
    const opDesc = "edição pos " + t.pos + " [" + label + "] (" + (t.profile === "simple" ? "Corne Simples " : "") + t.layerId + ")";
    const histOk = await pushHistory("antes de " + opDesc, preSnapshot);
    if (!histOk) {
      alert("Falha ao registrar ponto de restauração no histórico (armazenamento cheio ou indisponível). Edição cancelada para evitar perda do estado anterior.");
      return;
    }

    const lay = candidateLayer(t.layerId, t.kb, t.profile);
    const cell = t.type === "matrix" ? lay.matrix[t.r][t.c] : lay.thumbs[t.c];
    const updates = {
      label, sub: $("editSub").value.trim(), behavior: $("editBehavior").value.trim(),
      impl_zmk: zmk, impl_qmk: qmk,
      key_type: $("editType").value, status: $("editStatus").value,
    };
    if (cell.binding !== undefined || t.kb === "corne") updates.binding = zmk;
    if (cell.top !== undefined) updates.top = label;
    Object.assign(cell, updates);

    if (t.profile === "simple") simpleProfile().firmware_status = "modified_requires_rebuild";
    // espelho derivado: atualiza SOMENTE a mesma posição
    const mirror = t.profile === "candidate" && appData.profiles && appData.profiles.candidato_teste && appData.profiles.candidato_teste[t.kb] && appData.profiles.candidato_teste[t.kb].layers;
    if (mirror && mirror[t.layerId]) {
      const ml = mirror[t.layerId];
      const mc = t.type === "matrix" ? ml.matrix[t.r][t.c] : ml.thumbs[t.c];
      if (mc) Object.assign(mc, cell);
    }
    editingTarget = null;
    $("dlgEdit").close();
    dirty = canonicalString(appData) !== fileBaselineString;
    saveDraft("edição de tecla");
    renderAll();
  }

  // ------------------------------------------------------------ rascunho/histórico
  function saveDraft(reason) {
    const errs = validateDataset(appData, false);
    if (errs.length) { alert("RASCUNHO NÃO GRAVADO: dataset inválido.\n• " + errs.join("\n• ")); return false; }
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(appData));
      try {
        if (localStorage.getItem(DRAFT_V18_KEY)) {
          localStorage.setItem(DRAFT_V18_KEY, JSON.stringify(appData));
        }
      } catch (e2) {
        console.warn("Falha ao sincronizar alias secundário de rascunho:", e2);
        return false;
      }
      lastDraftAt = nowISO();
      updateChips();
      return true;
    } catch (e) {
      alert("FALHA ao gravar o rascunho no navegador (armazenamento cheio).\nA edição continua em memória nesta sessão, mas NÃO foi persistida no navegador.\nRecomendado: utilize “Baixar JSON” para exportação de resgate.\n" + e);
      return false;
    }
  }

  function loadHistory() {
    try {
      const raw = localStorage.getItem(HISTORY_KEY) || localStorage.getItem(HISTORY_V18_KEY);
      if (!raw) return;
      const arr = JSON.parse(raw);
      if (!Array.isArray(arr)) return;
      // F8: arquivos de rascunho v05 (sem conflicts/references/profiles) são parte
      // legítima do histórico. A validação respeita o schema de CADA entrada;
      // antes o filtro só aceitava schema 6 e a versão sumia após recarregar.
      history = arr.filter(x => {
        if (!x || !x.data) return false;
        const errs = validateDataset(x.data, x.data.schema_version === 5);
        return errs.length === 0;
      }).slice(0, MAX_HISTORY);
    } catch (e) { history = []; }
  }

  async function persistHistoryArray(arr) {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(arr));
      return true;
    } catch (e) {
      // Política honesta: NÃO descarta versões antigas silenciosamente por falta de espaço.
      alert("FALHA ao gravar histórico no navegador (armazenamento cheio). O estado atual continua em memória.");
      return false;
    }
  }

  async function persistHistory() {
    return persistHistoryArray(history);
  }

  async function pushHistory(label, data) {
    let hash = "";
    try { hash = await canonicalHashAsync(data); } catch (e) { hash = "indisponível"; }
    const entry = { ts: nowISO(), label, hash, data: deepClone(data) };
    const candidateHistory = [entry, ...history].slice(0, MAX_HISTORY);
    const persisted = await persistHistoryArray(candidateHistory);
    if (persisted) {
      history = candidateHistory;
      return true;
    }
    return false;
  }

  async function archivePending() {
    if (!pendingMigration) return;
    const label = pendingMigration.label || "";
    const ok = await pushHistory("rascunho antigo " + label, pendingMigration.data);
    if (!ok) {
      // F9: sem confirmação falsa — o rascunho permanece disponível no banner.
      showBanner();
      alert("ARQUIVAMENTO NÃO CONFIRMADO: o histórico não pôde ser gravado no navegador (armazenamento). O rascunho antigo PERMANECE no banner de migração — nada foi perdido. Use “Baixar rascunho” como alternativa.");
      return;
    }
    pendingMigration = null;
    showBanner();
    alert("Rascunho antigo arquivado no histórico do navegador. O estado atual NÃO foi alterado.");
  }

  // ------------------------------------------------------------ importação
  async function importFile(file) {
    if (!file) return;
    if (file.size > MAX_IMPORT_BYTES) { alert("IMPORTAÇÃO RECUSADA: arquivo maior que 5 MB. Estado atual preservado."); return; }
    let text;
    try { text = await file.text(); } catch (e) { alert("Falha ao ler o arquivo. Nada foi alterado.\n" + e); return; }
    let parsed;
    try { parsed = parseWithExactUid(text); } catch (e) {
      alert("IMPORTAÇÃO RECUSADA: JSON inválido.\n" + e.message + "\n\nEstado anterior PRESERVADO; nada foi gravado no cache.");
      return;
    }
    if (parsed && parsed.schema_version === 5) {
      const errs = validateDataset(parsed, true);
      if (errs.length) { alert("IMPORTAÇÃO RECUSADA: schema 5 inválido.\n• " + errs.join("\n• ") + "\n\nEstado anterior PRESERVADO."); return; }
      pendingMigration = { data: parsed, label: "v05 importado: " + file.name };
      showBanner();
      alert("Rascunho v05 válido recebido. Nada foi aplicado ainda: escolha o caminho no banner de migração.");
      return;
    }
    const errs = validateDataset(parsed, false);
    if (errs.length) {
      alert("IMPORTAÇÃO RECUSADA: estrutura incompatível (" + errs.length + " problema(s)).\n• " + errs.join("\n• ") + "\n\nEstado anterior PRESERVADO; nada foi gravado no cache.");
      return;
    }
    if (appData) {
      const archivedOk = await pushHistory("antes da importação de " + file.name, appData);
      if (!archivedOk) {
        const rescue = confirm(
          "FALHA NO BACKUP DE HISTÓRICO: o armazenamento do navegador está cheio e o estado anterior NÃO pôde ser arquivado no histórico.\n\n" +
          "Deseja baixar uma cópia de resgate do estado atual antes de prosseguir com a importação?\n\n" +
          "[OK] Baixar resgate do estado atual e cancelar importação para evitar perda de dados.\n" +
          "[Cancelar] Cancelar importação sem baixar."
        );
        if (rescue) {
          downloadObject(appData, "resgate_estado_pre_importacao_" + nowISO().replace(/[:.]/g, "-") + ".json");
        }
        alert("IMPORTAÇÃO INTERROMPIDA: o estado anterior não pôde ser arquivado no histórico. O estado atual continua PRESERVADO em memória; nada foi alterado.");
        return;
      }
    }
    appData = parsed;
    fileBaselineString = canonicalString(appData);
    sourceName = file.name;
    fileStatus = "not_confirmed";
    dirty = false;
    activeLayer = "L0";
    saveDraft("importação");
    renderAll();
    alert("Arquivo válido importado.\nUID Sofle: " + (uidText(appData) || "—")
      + "\nEstado anterior arquivado com sucesso no histórico."
      + "\nAtenção: importar NÃO grava o arquivo do projeto em disco; use “Gravar no arquivo…” para consolidar.");
  }

  // ------------------------------------------------------------ gravação/download
  function conflictsPending() { return Array.isArray(appData.conflicts) && appData.conflicts.length > 0; }

  function downloadText(text, name, mimeType) {
    const filename = name || "download.txt";
    const mime = mimeType || "text/plain;charset=utf-8";
    if (typeof Blob !== "undefined" && typeof URL !== "undefined" && typeof URL.createObjectURL === "function") {
      const blob = new Blob([String(text != null ? text : "")], { type: mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      const target = document.body || document.documentElement;
      if (target && target.appendChild) {
        target.appendChild(a);
        if (typeof a.click === "function") a.click();
        if (typeof a.remove === "function") a.remove();
      } else if (typeof a.click === "function") {
        a.click();
      }
      setTimeout(() => {
        try { URL.revokeObjectURL(url); } catch (e) {}
      }, 1500);
      return true;
    }
    // Fallback para ambientes sem Blob/URL (ou com data URI)
    if (typeof document !== "undefined" && typeof document.createElement === "function") {
      const a = document.createElement("a");
      a.href = "data:" + mime + "," + encodeURIComponent(String(text != null ? text : ""));
      a.download = filename;
      const target = document.body || document.documentElement;
      if (target && target.appendChild) {
        target.appendChild(a);
        if (typeof a.click === "function") a.click();
        if (typeof a.remove === "function") a.remove();
      } else if (typeof a.click === "function") {
        a.click();
      }
      return true;
    }
    return false;
  }

  function downloadObject(obj, name) {
    downloadText(JSON.stringify(obj, null, 2), name, "application/json");
  }

  if (typeof window !== "undefined") {
    window.downloadText = downloadText;
    window.downloadObject = downloadObject;
  }

  let lastExportedFileName = null;

  function downloadJSON() {
    if (conflictsPending()) { alert("DOWNLOAD FINAL BLOQUEADO: existem conflitos pendentes. Resolva todos antes de exportar o candidato."); return; }
    const name = "keymap_data_v06_" + nowISO().replace(/[:.]/g, "-").slice(0, 19) + ".json";
    downloadObject(appData, name);
    lastExportedFileName = name;
    lastDownloadAt = nowISO();
    fileStatus = "not_confirmed";
    alert("DOWNLOAD SOLICITADO: " + name + "\n\nO arquivo exportado contém suas edições em memória.\nPara gerar o candidato usando este arquivo, use a Opção 2 no modal “Gerar Candidatos”:\n--dataset ~/Downloads/" + name);
    updateChips();
  }

  async function writeFile() {
    if (conflictsPending()) { alert("GRAVAÇÃO BLOQUEADA: existem conflitos pendentes. Resolva todos antes de gravar o candidato final."); return; }
    if (!("showSaveFilePicker" in window)) {
      downloadJSON();
      alert("Este navegador não oferece gravação direta. O arquivo foi BAIXADO; o arquivo do projeto NÃO foi atualizado.");
      return;
    }
    let handle;
    try {
      handle = await window.showSaveFilePicker({
        suggestedName: "keymap_data_v06.json",
        types: [{ description: "Dataset Keyboard Split Manager", accept: { "application/json": [".json"] } }],
      });
    } catch (e) {
      if (e && e.name === "AbortError") {
        alert("Gravação CANCELADA. NADA foi gravado e o arquivo do projeto permanece como estava.");
      } else {
        alert("FALHA ao abrir o seletor de arquivo. NADA foi gravado.\n" + (e && e.message ? e.message : e));
      }
      return;
    }
    try {
      // F7: cópia fixa — grava o SNAPSHOT do momento do clique. Edições feitas
      // durante a gravação NÃO entram no arquivo e permanecem marcadas como não salvas.
      const snapshot = deepClone(appData);
      const snapshotString = canonicalString(appData);
      const writable = await handle.createWritable();
      await writable.write(JSON.stringify(snapshot, null, 2));
      await writable.close();
      fileBaselineString = snapshotString;
      dirty = canonicalString(appData) !== snapshotString;
      fileStatus = dirty ? "not_confirmed" : "confirmed";
      sourceName = handle.name || "arquivo escolhido";
      saveDraft("gravação no arquivo");
      renderAll();
      alert("ARQUIVO GRAVADO E FECHADO: " + sourceName
        + (dirty ? "\n\nATENÇÃO: alteração(ões) feita(s) durante a gravação ficaram FORA do arquivo gravado — permanecem em memória/rascunho. O chip “Alterações NÃO salvas” continua ativo até nova gravação." : "")
        + "\n\nConfirme no terminal que é este arquivo que o gerador usará:\nksm-work/data/keymap_data_v06.json (ou o caminho escolhido).\nHash canônico exibido no cabeçalho.");
    } catch (e) {
      alert("FALHA DURANTE A GRAVAÇÃO. O arquivo pode não ter sido atualizado; NÃO trate como sucesso.\n" + (e && e.message ? e.message : e));
    }
  }

  // ------------------------------------------------------------ migração
  async function runMigration() {
    if (!pendingMigration) return;
    const draft = pendingMigration.data;
    const base = migrationBaseline(draft);
    if (!base) {
      alert("MIGRAÇÃO ABORTADA: referência histórica indisponível para este rascunho.\nVersão: " + (draft.version || "?") + " · schema: " + draft.schema_version + "\n\nNenhum merge automático foi feito. O rascunho continua preservado; use “Arquivar rascunho” ou “Baixar rascunho”.");
      return;
    }
    const legacyLayers = base.layers || {};
    const out = deepClone(appData);
    const conflicts = [];
    const order = out.metadata.layers_order;
    let applied = 0, conflictsCount = 0;

    for (const lid of order) {
      for (const kb of ["corne", "sofle"]) {
        const oldL = legacyLayers[lid] && legacyLayers[lid][kb];
        const draftL = draft.layers && draft.layers[lid] && draft.layers[lid][kb];
        const newL = out.layers[lid][kb];
        if (!draftL) continue;
        const positions = [];
        if (Array.isArray(draftL.matrix) && Array.isArray(newL.matrix)) {
          draftL.matrix.forEach((row, r) => row.forEach((_, c) => positions.push({ type: "matrix", r, c })));
        }
        if (Array.isArray(draftL.thumbs) && Array.isArray(newL.thumbs)) {
          draftL.thumbs.forEach((_, i) => positions.push({ type: "thumbs", r: 0, c: i }));
        }
        for (const p of positions) {
          const oldC = oldL ? (p.type === "matrix" ? oldL.matrix[p.r][p.c] : oldL.thumbs[p.c]) : null;
          const draftC = p.type === "matrix" ? draftL.matrix[p.r][p.c] : draftL.thumbs[p.c];
          const newC = p.type === "matrix" ? newL.matrix[p.r][p.c] : newL.thumbs[p.c];
          if (!draftC || !newC) continue;
          const oldK = oldC ? cellKey(oldC) : "<sem baseline>";
          const draftK = cellKey(draftC);
          const newK = cellKey(newC);
          if (!oldC) {
            if (draftK !== newK) {
              conflicts.push(mkConflict(lid, kb, p, null, draftC, newC));
              newC.status = "conflict";
              conflictsCount++;
            }
            continue;
          }
          if (draftK === oldK) continue; // usuário não mexeu: absorve o novo
          if (newK === oldK) { Object.assign(newC, draftC); applied++; continue; }
          if (draftK === newK) continue;
          conflicts.push(mkConflict(lid, kb, p, oldC, draftC, newC));
          newC.status = "conflict";
          conflictsCount++;
        }
      }
    }
    out.conflicts = conflicts;
    out.profiles.candidato_teste.corne.layers = {};
    out.profiles.candidato_teste.sofle.layers = {};
    for (const lid of order) {
      out.profiles.candidato_teste.corne.layers[lid] = deepClone(out.layers[lid].corne);
      out.profiles.candidato_teste.sofle.layers[lid] = deepClone(out.layers[lid].sofle);
    }
    const ok = await pushHistory("antes da migração de " + (draft.version || "rascunho"), appData);
    if (!ok) {
      const proceed = confirm(
        "FALHA NO BACKUP DE HISTÓRICO: o armazenamento do navegador está cheio e o estado atual NÃO pôde ser arquivado no histórico.\n\n" +
        "Deseja baixar uma cópia de resgate do estado atual agora?\n\n" +
        "[OK] Baixar resgate do estado atual e cancelar a migração para evitar perda de dados.\n" +
        "[Cancelar] Cancelar migração sem baixar."
      );
      if (proceed) {
        downloadObject(appData, "resgate_estado_pre_migracao_" + nowISO().replace(/[:.]/g, "-") + ".json");
      }
      alert("MIGRAÇÃO ABORTADA: o estado anterior não pôde ser arquivado com segurança no histórico. Nada foi alterado.");
      return;
    }
    appData = out;
    pendingMigration = null;
    dirty = true;
    saveDraft("migração");
    renderAll();
    if (conflictsCount) {
      openConflicts();
      alert("Migração concluída com " + applied + " personalizações absorvidas e " + conflictsCount + " conflito(s).\nNenhuma alternativa foi aplicada automaticamente nos conflitos; resolva um a um antes de gerar.");
    } else {
      alert("Migração concluída sem conflitos. " + applied + " personalizações absorvidas.");
    }
  }

  function mkConflict(lid, kb, p, oldC, draftC, newC) {
    const snap = c => c ? { label: c.label || "", sub: c.sub || "", behavior: c.behavior || "", impl_zmk: c.impl_zmk || "", impl_qmk: c.impl_qmk || "", key_type: c.key_type || "normal", status: c.status || "" } : null;
    return {
      id: lid + ":" + kb + ":" + p.type + ":" + p.r + ":" + p.c,
      layer: lid, keyboard: kb, type: p.type, r: p.r, c: p.c,
      position: p.type === "matrix" ? p.r * 12 + p.c : (kb === "corne" ? 36 : 48) + p.c,
      old: snap(oldC), draft: snap(draftC), new: snap(newC), resolution: null,
    };
  }

  function openConflicts() {
    const box = $("confOut");
    box.textContent = "";
    const list = appData.conflicts || [];
    if (!list.length) { box.appendChild(textP("Nenhum conflito pendente.")); $("dlgConflicts").showModal(); return; }
    for (const c of list) {
      const item = document.createElement("div");
      item.className = "item";
      const h = document.createElement("div"); h.className = "h";
      const t = document.createElement("div");
      t.innerHTML = "";
      t.appendChild(document.createTextNode(c.layer + " · " + c.keyboard.toUpperCase() + " · posição " + c.position + " (" + c.type + ")"));
      h.appendChild(t);
      const sel = document.createElement("select");
      for (const opt of [["old", "Instalado/antigo"], ["draft", "Rascunho"], ["new", "Novo (v06)"], ["custom", "Personalizado"]]) {
        const o = document.createElement("option"); o.value = opt[0]; o.textContent = opt[1]; sel.appendChild(o);
      }
      sel.value = "new";
      const apply = btn("Aplicar resolução", () => resolveConflict(c.id, sel.value, item), "ok");
      h.appendChild(sel); h.appendChild(apply);
      item.appendChild(h);
      for (const [name, val] of [["Antigo", c.old], ["Rascunho", c.draft], ["Novo", c.new]]) {
        const line = document.createElement("div");
        line.className = "small mono";
        const codeRep = val ? (c.keyboard === "sofle" ? (val.impl_qmk || val.impl_zmk) : (val.impl_zmk || val.impl_qmk)) : "<sem baseline>";
        line.textContent = name + ": " + (val ? (val.label + " | " + codeRep) : "<sem baseline>");
        item.appendChild(line);
      }
      const isSofle = c.keyboard === "sofle";
      const customWrap = document.createElement("div");
      customWrap.className = "grid2";
      const l1 = document.createElement("div"); l1.className = "field"; l1.innerHTML = "<label>Rótulo personalizado</label>";
      const i1 = document.createElement("input"); i1.type = "text"; i1.maxLength = 40; i1.placeholder = c.new ? c.new.label : ""; l1.appendChild(i1);
      const l2 = document.createElement("div"); l2.className = "field";
      l2.innerHTML = "<label>" + (isSofle ? "Código personalizado (Vial/QMK)" : "Binding personalizado (ZMK)") + "</label>";
      const i2 = document.createElement("input"); i2.type = "text"; i2.maxLength = 200;
      i2.placeholder = c.new ? (isSofle ? (c.new.impl_qmk || "") : (c.new.impl_zmk || "")) : "";
      l2.appendChild(i2);
      customWrap.appendChild(l1); customWrap.appendChild(l2); item.appendChild(customWrap);
      item._custom = { label: i1, code: i2, isSofle };
      box.appendChild(item);
    }
    $("dlgConflicts").showModal();
  }

  function resolveConflict(id, choice, item) {
    const idx = (appData.conflicts || []).findIndex(c => c.id === id);
    if (idx < 0) return;
    const c = appData.conflicts[idx];
    let value;
    if (choice === "custom") {
      const label = item._custom.label.value.trim() || (c.new && c.new.label) || "";
      const codeVal = item._custom.code.value.trim();
      if (item._custom.isSofle) {
        const qmk = codeVal || (c.new && c.new.impl_qmk) || "";
        if (!qmk) { alert("Código personalizado Vial/QMK não pode ficar vazio."); return; }
        value = Object.assign({}, c.new || {}, { label, impl_qmk: qmk, status: "candidato" });
      } else {
        const zmk = codeVal || (c.new && c.new.impl_zmk) || "";
        if (!zmk.startsWith("&")) { alert("Binding personalizado ZMK deve começar com &."); return; }
        value = Object.assign({}, c.new || {}, { label, impl_zmk: zmk, status: "candidato" });
      }
    } else {
      value = c[choice] ? Object.assign({}, c[choice]) : null;
    }
    if (!value) { alert("Alternativa indisponível."); return; }
    value.status = "candidato";
    const lay = appData.layers[c.layer][c.keyboard];
    const cell = c.type === "matrix" ? lay.matrix[c.r][c.c] : lay.thumbs[c.c];
    Object.assign(cell, value);
    const mirror = appData.profiles.candidato_teste[c.keyboard].layers[c.layer];
    const mc = c.type === "matrix" ? mirror.matrix[c.r][c.c] : mirror.thumbs[c.c];
    if (mc) Object.assign(mc, value);
    appData.conflicts.splice(idx, 1);
    dirty = true;
    saveDraft("resolução de conflito");
    renderAll();
    $("dlgConflicts").close();
    if ((appData.conflicts || []).length) openConflicts();
    else alert("Conflito resolvido. Nenhum conflito pendente; geração e gravação liberadas.");
  }

  // ------------------------------------------------------------ comparação
  function compareSources() {
    const opts = [];
    for (const lid of appData.metadata.layers_order) opts.push({ v: "cand:" + lid, label: "Mapa antigo " + lid, get: () => candidateLayer(lid, activeKeyboard, "candidate") });
    if (activeKeyboard === "corne") {
      for (const lid of simpleProfile().layers_order) opts.push({ v: "simple:" + lid, label: "Corne Simples " + lid + " " + simpleProfile().layers_info[lid].name, get: () => candidateLayer(lid, "corne", "simple") });
      const previous = appData.profiles.corne_simples_anterior;
      if (previous) for (const lid of previous.layers_order) opts.push({ v: "previous:" + lid, label: "Simples anterior " + lid, get: () => previous.layers[lid] });
    }
    if (activeKeyboard === "corne") {
      for (const n of Object.keys(appData.references.corne.native_layers)) opts.push({ v: "refc:" + n, label: "Referência Corne " + n, get: () => referenceLayer(n, "corne") });
    } else {
      for (let i = 0; i < 16; i++) opts.push({ v: "refs:L" + i, label: "Referência Sofle L" + i, get: () => referenceLayer("L" + i, "sofle") });
    }
    return opts;
  }

  function fillCompareSelectors() {
    const opts = compareSources();
    for (const id of ["cmpA", "cmpB"]) {
      const sel = $(id); sel.textContent = "";
      for (const o of opts) { const e = document.createElement("option"); e.value = o.v; e.textContent = o.label; sel.appendChild(e); }
    }
    $("cmpA").value = opts[0] ? opts[0].v : "";
    $("cmpB").value = opts.length > 1 ? opts[1].v : (opts[0] ? opts[0].v : "");
  }

  function cellRepresentation(cell, kb) {
    if (!cell) return "<ausente>";
    if (kb === "corne") {
      return String(cell.impl_zmk || cell.binding || cell.label || "").trim();
    } else {
      // Para o Sofle, o campo nativo é impl_qmk!
      return String(cell.impl_qmk || cell.binding || cell.label || "").trim();
    }
  }

  function runCompare() {
    const opts = compareSources();
    const a = opts.find(o => o.v === $("cmpA").value);
    const b = opts.find(o => o.v === $("cmpB").value);
    const out = $("cmpOut"); out.textContent = "";
    if (!a || !b) { out.appendChild(textP("Selecione os dois lados.")); return; }
    const A = a.get(), B = b.get();
    if (!A || !B) { out.appendChild(textP("Camada indisponível.")); return; }
    const fa = flatLayer(A), fb = flatLayer(B);
    const n = Math.max(fa.length, fb.length);
    const diffs = [];
    for (let i = 0; i < n; i++) {
      const ta = cellRepresentation(fa[i], activeKeyboard);
      const tb = cellRepresentation(fb[i], activeKeyboard);
      if (ta !== tb) diffs.push({ i, a: ta, b: tb });
    }
    out.appendChild(textP("A: " + a.label + " · B: " + b.label + " · " + diffs.length + " diferença(s) textual(is) em " + n + " posições (" + activeKeyboard.toUpperCase() + ")."));
    if (!diffs.length) { out.appendChild(textP("Nenhuma diferença textual no código nativo do teclado.")); return; }

    // Alerta ergonômico dedicado para modificadores em polegares (ex: Command / GUI no macOS)
    const thumbStart = activeKeyboard === "sofle" ? 48 : 36;
    const thumbEnd = activeKeyboard === "sofle" ? 58 : 42;
    const thumbCmdDiffs = [];
    for (const d of diffs) {
      if (d.i >= thumbStart && d.i < thumbEnd) {
        const hasGuiA = /GUI/i.test(d.a);
        const hasGuiB = /GUI/i.test(d.b);
        if (hasGuiA || hasGuiB) {
          const tIdx = d.i - thumbStart;
          const label = activeKeyboard === "sofle"
            ? (tIdx < 5 ? "Dedão Esquerdo #" + (tIdx + 1) : "Dedão Direito #" + (tIdx - 5 + 1))
            : (tIdx < 3 ? "Dedão Esquerdo #" + (tIdx + 1) : "Dedão Direito #" + (tIdx - 3 + 1));
          thumbCmdDiffs.push({ pos: d.i, label, a: d.a, b: d.b, hasGuiA, hasGuiB });
        }
      }
    }
    if (thumbCmdDiffs.length) {
      const w = document.createElement("div");
      w.className = "notice warn";
      w.style.marginBottom = "8px";
      const title = document.createElement("strong");
      title.textContent = "⚠️ ALERTA DE ERGONOMIA NOS POLEGARES (Command / macOS):";
      w.appendChild(title);
      w.appendChild(document.createElement("br"));
      const desc = document.createElement("span");
      desc.textContent = "Detectada divergência de modificador Command (GUI) nas teclas de polegar entre os perfis:";
      w.appendChild(desc);
      w.appendChild(document.createElement("br"));
      for (const t of thumbCmdDiffs) {
        const line = document.createElement("div");
        line.style.fontSize = "12px";
        line.style.marginTop = "2px";
        if (!t.hasGuiA && t.hasGuiB) {
          line.textContent = "• " + t.label + " (Pos " + t.pos + "): Command em B ('" + t.b + "') foi alterado em A para '" + t.a + "'";
        } else if (t.hasGuiA && !t.hasGuiB) {
          line.textContent = "• " + t.label + " (Pos " + t.pos + "): Command em A ('" + t.a + "') contra B ('" + t.b + "')";
        } else {
          line.textContent = "• " + t.label + " (Pos " + t.pos + "): A='" + t.a + "' vs B='" + t.b + "'";
        }
        w.appendChild(line);
      }
      const note = document.createElement("div");
      note.style.fontSize = "11px";
      note.style.fontStyle = "italic";
      note.style.marginTop = "4px";
      note.textContent = "Atenção: A preferência em macOS mantém Command no polegar de descanso natural. O Candidato B preserva a baseline L0 intacta (Commands nos polegares naturais). O Candidato C alinha os 6 seletores do Corne, deslocando Command para o polegar adjacente.";
      w.appendChild(note);
      out.appendChild(w);
    }

    const table = document.createElement("table");
    const head = document.createElement("tr");
    for (const h of ["Pos", "A", "B"]) { const th = document.createElement("th"); th.textContent = h; head.appendChild(th); }
    table.appendChild(head);
    for (const d of diffs.slice(0, 300)) {
      const tr = document.createElement("tr");
      for (const v of [d.i, d.a, d.b]) { const td = document.createElement("td"); td.textContent = v; tr.appendChild(td); }
      table.appendChild(tr);
    }
    out.appendChild(table);
    if (diffs.length > 300) out.appendChild(textP("Mostrando 300 de " + diffs.length + "."));
  }

  // ------------------------------------------------------------ histórico
  function openHistory() {
    const box = $("histOut"); box.textContent = "";
    if (legacyFound.length) {
      const t = document.createElement("div"); t.className = "notice warn";
      t.textContent = "Rascunhos antigos encontrados no navegador (recuperáveis):";
      box.appendChild(t);
      for (const l of legacyFound) {
        const item = document.createElement("div"); item.className = "item";
        const h = document.createElement("div"); h.className = "h";
        const s = document.createElement("div"); s.textContent = l.label + " · " + l.size + " B";
        const b1 = btn("Recuperar para migração", () => { pendingMigration = { data: l.data, label: l.label }; $("dlgHistory").close(); showBanner(); alert("Rascunho carregado no banner de migração. Nada foi aplicado."); }, "warn");
        const b2 = btn("Baixar", () => downloadObject(l.data, l.label + ".json"), "");
        h.appendChild(s); h.appendChild(b1); h.appendChild(b2); item.appendChild(h); box.appendChild(item);
      }
    }
    if (!history.length) { box.appendChild(textP("Nenhuma versão arquivada nesta sessão/navegador.")); }
    for (const h of history) {
      const item = document.createElement("div"); item.className = "item";
      const head = document.createElement("div"); head.className = "h";
      const s = document.createElement("div");
      s.textContent = fmtDate(h.ts) + " · " + h.label + " · hash " + String(h.hash).slice(0, 12);
      const b1 = btn("Restaurar", () => restoreHistory(h), "primary");
      const b2 = btn("Baixar", () => downloadObject(h.data, "ksm_versao_" + h.ts.replace(/[:.]/g, "-") + ".json"), "");
      head.appendChild(s); head.appendChild(b1); head.appendChild(b2); item.appendChild(head);
      box.appendChild(item);
    }
    $("dlgHistory").showModal();
  }

  async function restoreHistory(h) {
    // F8: versão v05 arquivada não pode ser aplicada direto (schema antigo);
    // vai para o banner de migração, que oferece caminhos seguros.
    if (h.data && h.data.schema_version === 5) {
      pendingMigration = { data: h.data, label: "versão arquivada v05 (" + fmtDate(h.ts) + ")" };
      $("dlgHistory").close();
      showBanner();
      alert("Versão v05 não é aplicada diretamente (schema antigo). Ela foi colocada no banner de migração — use “Migrar com referência histórica”, “Arquivar rascunho” ou “Baixar rascunho”. Nada foi alterado no estado atual.");
      return;
    }
    const errs = validateDataset(h.data, false);
    if (errs.length) { alert("RESTAURAÇÃO RECUSADA: versão inválida.\n• " + errs.join("\n• ")); return; }
    if (!confirm("Restaurar a versão de " + fmtDate(h.ts) + "? O estado atual será arquivado antes.")) return;
    const ok = await pushHistory("antes de restaurar " + h.ts, appData);
    if (!ok) {
      const rescue = confirm(
        "FALHA NO BACKUP DE HISTÓRICO: o armazenamento do navegador está cheio e o estado atual NÃO pôde ser arquivado no histórico.\n\n" +
        "Deseja baixar uma cópia de resgate do estado atual antes de prosseguir com a restauração?\n\n" +
        "[OK] Baixar resgate do estado atual e cancelar restauração para evitar perda de dados.\n" +
        "[Cancelar] Cancelar restauração sem baixar."
      );
      if (rescue) {
        downloadObject(appData, "resgate_estado_atual_" + nowISO().replace(/[:.]/g, "-") + ".json");
      }
      alert("RESTAURAÇÃO CANCELADA: estado atual preservado. Libere espaço ou use o arquivo de resgate.");
      return;
    }
    appData = deepClone(h.data);
    fileBaselineString = canonicalString(EMBEDDED);
    dirty = canonicalString(appData) !== fileBaselineString;
    sourceName = "versão restaurada " + h.ts;
    fileStatus = "not_confirmed";
    saveDraft("restauração de versão");
    renderAll();
    $("dlgHistory").close();
    alert("Versão restaurada em memória e como rascunho. Ainda NÃO é o arquivo do projeto; use “Gravar no arquivo…” para confirmar.");
  }

  // ------------------------------------------------------------ auditoria/funções
  function openAudit() {
    const simpleLines = [];
    if (appData.profiles && appData.profiles.corne_simples_v01) {
      const p = simpleProfile();
      const cells = p.layers_order.flatMap(lid => flatLayer(p.layers[lid]));
      const audit = auditLayerReachability(p.layers, "corne", { behaviors: p.behaviors, conditional_layers: [] });
      const pending = cells.filter(c => c.pending_reason === "host_layout").map(c => c.label);
      const firmwarePending = cells.filter(c => c.pending_reason && c.pending_reason !== "host_layout").map(c => c.label);
      const errors = validateDataset(appData, false);
      simpleLines.push(
        "PERFIL: " + (p.name || "Corne Simples v13") + " (independente)",
        "  • Camadas: " + p.layers_order.join(", "),
        "  • Posições: " + cells.length + " / 294",
        "  • Validação estrutural do conjunto: " + (errors.length ? errors.join("; ") : "OK"),
        "  • Camadas alcançáveis estaticamente: " + audit.reachable.length + " / 7",
        "  • Camadas órfãs: " + (audit.unreachable.join(", ") || "nenhuma"),
        "  • Pendências de layout do computador: " + (pending.join(", ") || "nenhuma posição marcada"),
        "  • Propostas sem comportamento de firmware: " + (firmwarePending.join(", ") || "nenhuma"),
        "  • Modificadores da Base real: A=Ctrl S=Alt D=Cmd F=Shift; J=Shift K=Cmd L=Alt ;=Ctrl.",
        "  • NAV: Espaço ativa; A=Ctrl S=Alt D=Cmd F=Shift; setas J/K/L/; = esquerda/baixo/cima/direita; Home/PgDn/PgUp/End em U/I/O/P.",
        "  • O Corne antigo, suas referências e o Sofle estão em estruturas separadas.",
        "  • Acentuação no Mac: Internacional informado; Opt+E e Opt+U atribuídos, resultado físico pendente.",
        "  • Estado: revisão 13, dedões agrupados e NAV com setas na direita. UF2 v01 não atualizado; editar o HTML não atualiza o teclado. Nova organização pendente de teste físico.",
        ""
      );
    }
    const order = appData.metadata.layers_order;
    let corneCount = 0, sofleCount = 0;
    let corneEmpty = 0, sofleEmpty = 0;
    let corneConflicts = 0, sofleConflicts = 0;
    let badCorneZmk = 0, badSofleQmk = 0;
    let placeholderCount = 0;
    const disabledNames = [];

    for (const lid of order) {
      for (const kb of ["corne", "sofle"]) {
        const lay = appData.layers[lid][kb];
        const cells = flatLayer(lay);
        if (kb === "corne") {
          corneCount += cells.length;
          for (const c of cells) {
            if (!c.label || !String(c.label).trim()) corneEmpty++;
            if (c.status === "conflito" || c.status === "conflict") corneConflicts++;
            const code = String(c.impl_zmk || "");
            if (!code.startsWith("&")) badCorneZmk++;
          }
        } else {
          sofleCount += cells.length;
          for (const c of cells) {
            if (!c.label || !String(c.label).trim()) sofleEmpty++;
            if (c.status === "conflito" || c.status === "conflict") sofleConflicts++;
            const q = String(c.impl_qmk || "").trim();
            if (!q) badSofleQmk++;
            const isPlaceholder = q.includes("process_record") || q.includes("pending_fn") || q.includes("user()") || q.includes("toggle()");
            if (isPlaceholder) {
              placeholderCount++;
              const desc = (c.label || q).replace(/\*/g, "").trim();
              if (!disabledNames.includes(desc)) disabledNames.push(desc);
            }
          }
        }
      }
    }

    const disabledDetail = placeholderCount
      ? " (" + placeholderCount + " função(ões) no .vil desativadas como KC_NO: " + disabledNames.join(", ") + ")"
      : " (nenhum)";

    // Auditoria de Acessibilidade das Camadas (Grafo de Navegação)
    const layersCorne = {};
    const layersSofle = {};
    for (const lid of (appData.metadata && appData.metadata.layers_order) || []) {
      if (appData.layers && appData.layers[lid]) {
        if (appData.layers[lid].corne) layersCorne[lid] = appData.layers[lid].corne;
        if (appData.layers[lid].sofle) layersSofle[lid] = appData.layers[lid].sofle;
      }
    }
    const sofleTapDance = (appData.profiles && appData.profiles.candidato_teste && appData.profiles.candidato_teste.sofle && appData.profiles.candidato_teste.sofle.tap_dance)
      || (appData.references && appData.references.sofle && appData.references.sofle.vil && appData.references.sofle.vil.tap_dance)
      || [];
    const auditCorne = typeof auditLayerReachability === "function" ? auditLayerReachability(layersCorne, "corne", {
      conditional_layers: appData.conditional_layers,
      behaviors: appData.behaviors
    }) : null;
    const auditSofle = typeof auditLayerReachability === "function" ? auditLayerReachability(layersSofle, "sofle", {
      tap_dance: sofleTapDance
    }) : null;

    const reachabilityLines = [];
    if (auditCorne && auditSofle) {
      reachabilityLines.push(
        "",
        "AUDITORIA DE ACESSIBILIDADE E GRAFO DE CAMADAS (Acessibilidade Estática):",
        "  • CORNE (ZMK nativo): " + auditCorne.reachable.length + " / " + auditCorne.layerIds.length + " camadas acessíveis estaticamente (" + (auditCorne.unreachable.length === 0 ? "100% conectadas no grafo" : "ALERTA: órfãs " + auditCorne.unreachable.join(", ")) + ")",
        "  • SOFLE (Candidato C QMK nativo): " + auditSofle.reachable.length + " / " + auditSofle.layerIds.length + " camadas acessíveis estaticamente (" + (auditSofle.unreachable.length === 0 ? "100% conectadas no grafo via seletores/TD resolvidos" : "ALERTA: órfãs " + auditSofle.unreachable.join(", ")) + ")",
        "  • SOFLE (Baseline / Cand B): L0..L6 conectadas; L7..L9 órfãs no grafo (0 transições a partir de L0..L6)",
        "  • Condicionais/Tri-layers comprovadas: " + (auditSofle.provenConditionals && auditSofle.provenConditionals.length ? auditSofle.provenConditionals.map(p => p.target + " (" + p.prerequisites.join("+") + ")").join(", ") : "nenhuma"),
        ...(auditSofle.unprovenConditionals && auditSofle.unprovenConditionals.length ? ["  ⚠️ ALERTA: Combinação condicional não comprovada: " + auditSofle.unprovenConditionals.map(u => u.target).join(", ")] : []),
        ...(auditSofle.toggleExitLayers && auditSofle.toggleExitLayers.length ? ["  • Saídas por alternância (TG): " + auditSofle.toggleExitLayers.join(", ")] : []),
        "  ℹ️ NOTA: Acessibilidade estática analisa a topologia do mapa; não substitui o teste dinâmico/físico de hardware."
      );
      if (auditSofle.trapLayers.length > 0) {
        reachabilityLines.push("  ⚠️ ALERTA: Camada(s) sem retorno a L0 (armadilha): " + auditSofle.trapLayers.join(", "));
      }
    }

    const lines = [
      ...simpleLines,
      "CORNE (ZMK): " + corneCount + " / 420 posições (" + (corneCount === 420 ? "OK" : "FALHA") + ")",
      "  • Células vazias: " + corneEmpty,
      "  • Células em conflito: " + corneConflicts,
      "  • Bindings ZMK sem '&': " + badCorneZmk,
      "",
      "SOFLE (Vial/QMK): " + sofleCount + " / 580 posições (" + (sofleCount === 580 ? "OK" : "FALHA") + ")",
      "  • Células vazias: " + sofleEmpty,
      "  • Células em conflito: " + sofleConflicts,
      "  • Códigos Vial/QMK vazios: " + badSofleQmk,
      "  • Placeholders identificados / funções desativadas: " + placeholderCount + disabledDetail,
      ...reachabilityLines,
      "",
      "Conflitos pendentes na lista: " + ((appData.conflicts || []).length),
      "UID Sofle: " + (uidText(appData) || "—"),
      "Referência Corne: " + Object.keys(appData.references.corne.native_layers).join(", "),
      "Referência Sofle: " + appData.references.sofle.layer_count + " camadas completas (.vil 16x10x6)",
      "",
      "Este relatório valida ESTRUTURA, NATIVIDADE e ACESSIBILIDADE ESTÁTICA por teclado.",
      "Não é homologação física e não afirma firmware gravado.",
    ];
    $("auditOut").textContent = lines.join("\n");
    $("dlgAudit").showModal();
  }

  function openFunctions() {
    const box = $("fnOut"); box.textContent = "";
    const list = appData.function_status || [];
    if (!list.length) box.appendChild(textP("Nenhum registro de função no dataset."));
    for (const f of list) {
      const d = document.createElement("div"); d.className = "item";
      const h = document.createElement("div"); h.className = "h";
      const t = document.createElement("div"); t.textContent = f.keyboard.toUpperCase() + " · " + f.function;
      const c = document.createElement("span");
      c.className = "chip " + (f.status === "implemented" ? "ok" : (f.status === "blocked" ? "bad" : "warn"));
      c.textContent = f.status;
      h.appendChild(t); h.appendChild(c); d.appendChild(h);
      const e = document.createElement("div"); e.className = "small"; e.textContent = f.evidence || "";
      d.appendChild(e);
      const p = document.createElement("div"); p.className = "small"; p.textContent = "Teste físico: " + (f.physical_test || "pending");
      d.appendChild(p);
      box.appendChild(d);
    }
    box.appendChild(textP("Um recurso com status pending_firmware não foi exportado como função funcional; o slot instalado foi preservado."));
    $("dlgFunctions").showModal();
  }

  // ------------------------------------------------------------ geração
  function openGenerate() {
    const blocked = conflictsPending();
    const n = blocked ? appData.conflicts.length : 0;
    const g = $("genBlock");
    g.className = "notice " + (blocked ? "bad" : "ok");
    g.textContent = blocked
      ? "GERAÇÃO BLOQUEADA: " + n + " conflito(s) pendente(s). Resolva em “Resolver conflitos” antes de gerar."
      : "Sem conflitos pendentes. Confirme o hash e o arquivo do dataset antes de executar.";
    const dlName = lastExportedFileName || "keymap_data_v06_export.json";
    const sofleOutDir = "ksm-work/generators/candidates/sofle_v06";

    if (activeKeyboard === "corne" && activeProfile === "simple") {
      const sp = simpleProfile();
      const pName = (sp && sp.name) || "Corne Simples v13";
      const pRev = (sp && sp.design_revision) || 13;
      const corneOut = "generators/candidates/corne_simples_v13.keymap";
      $("genCorne").value = "# PERFIL ATIVO: " + pName + " (revisão " + pRev + ", 7 camadas, 294 posições)\n\n"
        + "# OPÇÃO 1 — Gerar usando dataset oficial do repositório:\n"
        + "python3 generators/generate_corne_simples.py --dataset data/keymap_data_v06.json --out " + corneOut + "\n\n"
        + "# OPÇÃO 2 — Gerar usando arquivo exportado/baixado pelo navegador:\n"
        + "python3 generators/generate_corne_simples.py --dataset ~/Downloads/" + dlName + " --out " + corneOut + " --force";
    } else {
      const corneOut = "generators/candidates/corne_candidato_v06.keymap";
      $("genCorne").value = "# OPÇÃO 1 — Gerar usando dataset oficial do repositório (10 camadas):\n"
        + "python3 generators/generate_corne_candidato.py --dataset data/keymap_data_v06.json --out " + corneOut + "\n\n"
        + "# OPÇÃO 2 — Gerar usando arquivo exportado/baixado pelo navegador:\n"
        + "python3 generators/generate_corne_candidato.py --dataset ~/Downloads/" + dlName + " --out " + corneOut + " --force";
    }

    $("genSofle").value = "# OPÇÃO 1 — Gerar usando dataset oficial do repositório:\n"
      + "python3 generators/compose_sofle_candidato.py --dataset data/keymap_data_v06.json --outdir " + sofleOutDir + "\n\n"
      + "# OPÇÃO 2 — Gerar usando arquivo exportado/baixado pelo navegador:\n"
      + "python3 generators/compose_sofle_candidato.py --dataset ~/Downloads/" + dlName + " --outdir " + sofleOutDir + " --force\n\n"
      + "# Produz em " + sofleOutDir + "/:\n"
      + "#  • Cand A: sofle_candidato_v06_A_aprovado.vil (baseline homologada byte-exata)\n"
      + "#  • Cand B: sofle_candidato_v06_B_design_v03.vil (preserva L0..L6 baseline com Commands intactos nos polegares; adiciona L7..L9)\n"
      + "#  • Cand C: sofle_candidato_v06_C_conectado.vil (conectado L0..L9; seletores Media/Fun nos polegares; saídas TO(0) em L1 e L9)";
    $("genVerify").value = "python3 app/verify_ksm.py\n# (F11) sem argumentos: caminhos fixos internos (data/keymap_data_v06.json) e registro em reports/VERIFY_KSM_FASE3_C5.json";
    $("dlgGenerate").showModal();
  }

  // ------------------------------------------------------------ eventos/init
  function bind() {
    $("kbGroup").addEventListener("click", e => {
      const b = e.target.closest("button[data-kb]"); if (!b) return;
      activeKeyboard = b.dataset.kb;
      [...$("kbGroup").children].forEach(x => x.classList.toggle("sel", x === b));
      activeProfile = (activeKeyboard === "corne" ? "simple" : "candidate");
      activeLayer = layerIds()[0];
      [...$("profileGroup").children].forEach(x => x.classList.toggle("sel", x.dataset.profile === activeProfile));
      renderAll();
    });
    $("profileGroup").addEventListener("click", e => {
      const b = e.target.closest("button[data-profile]"); if (!b) return;
      activeProfile = b.dataset.profile;
      [...$("profileGroup").children].forEach(x => x.classList.toggle("sel", x === b));
      activeLayer = layerIds()[0];
      renderAll();
    });
    $("editSave").addEventListener("click", e => { e.preventDefault(); saveEdit(); });
    $("editCancel").addEventListener("click", e => { e.preventDefault(); editingTarget = null; $("dlgEdit").close(); });
    $("btnSaveDraft").addEventListener("click", () => {
      if (saveDraft("salvar rascunho manual")) {
        pushHistory("rascunho manual", appData);
        alert("Rascunho gravado no navegador em " + fmtDate(lastDraftAt) + ".\nIsto NÃO é o arquivo do projeto.");
      }
    });
    $("btnDownload").addEventListener("click", downloadJSON);
    $("btnWriteFile").addEventListener("click", writeFile);
    $("btnImport").addEventListener("click", () => $("fileImport").click());
    $("fileImport").addEventListener("change", e => { const f = e.target.files[0]; e.target.value = ""; importFile(f); });
    $("btnCompare").addEventListener("click", () => { fillCompareSelectors(); $("cmpOut").textContent = ""; $("dlgCompare").showModal(); });
    $("cmpRun").addEventListener("click", e => { e.preventDefault(); runCompare(); });
    $("btnHistory").addEventListener("click", openHistory);
    $("histClose").addEventListener("click", e => { e.preventDefault(); $("dlgHistory").close(); });
    $("btnGenerate").addEventListener("click", openGenerate);
    $("genClose").addEventListener("click", e => { e.preventDefault(); $("dlgGenerate").close(); });
    $("btnAudit").addEventListener("click", openAudit);
    $("auditClose").addEventListener("click", e => { e.preventDefault(); $("dlgAudit").close(); });
    $("btnFunctions").addEventListener("click", openFunctions);
    $("fnClose").addEventListener("click", e => { e.preventDefault(); $("dlgFunctions").close(); });
    $("btnHelp").addEventListener("click", () => $("dlgHelp").showModal());
    $("helpClose").addEventListener("click", e => { e.preventDefault(); $("dlgHelp").close(); });
    $("confClose").addEventListener("click", e => { e.preventDefault(); $("dlgConflicts").close(); });

    // Zoom do teclado
    $("btnZoomIn").addEventListener("click", () => applyZoom(currentZoom + 0.15));
    $("btnZoomOut").addEventListener("click", () => applyZoom(currentZoom - 0.15));
    $("btnZoomReset").addEventListener("click", () => applyZoom(1.0));

    // Ações de tecla no editor e toolbar
    $("btnCopyKey").addEventListener("click", copyCurrentEditingKey);
    $("btnPasteKey").addEventListener("click", pasteIntoCurrentEditingKey);
    $("btnSwapKey").addEventListener("click", openMoveFromEdit);
    $("btnClearClip").addEventListener("click", () => {
      copiedKeyData = null;
      updateClipboardUI();
    });
    $("btnOpenMoveKey").addEventListener("click", () => {
      if (activeProfile === "reference") {
        alert("Perfil de referência é somente leitura. Selecione um perfil editável.");
        return;
      }
      openMoveKeyDialog();
    });
    ["moveKeySrc", "moveKeyDest", "moveKeyMode", "moveKeyScope"].forEach(id => {
      const el = $(id);
      if (el) el.addEventListener("change", updateMoveKeyInfo);
    });
    $("moveKeyCancel").addEventListener("click", () => $("dlgMoveKey").close());
    $("moveKeyExec").addEventListener("click", executeMoveKey);

    // fecha dialogs ao clicar no backdrop (exceto edição com dados)
    document.querySelectorAll("dialog").forEach(d => d.addEventListener("click", ev => {
      if (ev.target === d) d.close();
    }));
  }

  async function init() {
    if (typeof window !== "undefined" && window.__forceInitError) {
      throw new Error(String(window.__forceInitError));
    }
    loadHistory();
    // rascunho recuperável: DRAFT_KEY canônico tem precedência absoluta sobre aliases
    let loadedDraft = false;
    try {
      const raw = localStorage.getItem(DRAFT_KEY) || localStorage.getItem(DRAFT_V18_KEY) || localStorage.getItem("ksm_v17_profiles_draft") || localStorage.getItem("ksm_v16_profiles_draft");
      if (raw) {
        const draft = parseWithExactUid(raw);
        const errs = validateDataset(draft, false);
        if (!errs.length) {
          appData = ensureSimpleProfile(draft);
          sourceName = "rascunho local (não confirmado no arquivo)";
          fileStatus = "not_confirmed";
          fileBaselineString = canonicalString(EMBEDDED);
          dirty = canonicalString(appData) !== fileBaselineString;
          lastDraftAt = null;
          loadedDraft = true;
        } else {
          try { localStorage.setItem("ksm_v06_draft_quarantine_" + Date.now(), raw); } catch (e2) { /* ignore */ }
          appData = deepClone(EMBEDDED);
        }
      }
    } catch (e) {
      try { localStorage.setItem("ksm_v06_draft_quarantine_" + Date.now(), localStorage.getItem(DRAFT_KEY)); } catch (e2) { /* ignore */ }
      appData = deepClone(EMBEDDED);
    }
    if (!loadedDraft) {
      fileBaselineString = canonicalString(EMBEDDED);
      dirty = false;
    }
    // rascunhos legados: valida antes de exibir; nunca aplica automaticamente
    for (const [key, label] of LEGACY_KEYS) {
      try {
        const raw = localStorage.getItem(key);
        if (!raw) continue;
        const parsed = parseWithExactUid(raw);
        const errs = validateDataset(parsed, true);
        if (!errs.length) legacyFound.push({ key, label, data: parsed, size: raw.length });
        else { try { localStorage.setItem(key + "_quarantine_" + Date.now(), raw); } catch (e2) { /* ignore */ } }
      } catch (e) { /* ignora cache corrompido, sem apagar */ }
    }
    if (legacyFound.length) {
      pendingMigration = { data: legacyFound[0].data, label: legacyFound[0].label + " (" + legacyFound[0].key + ")" };
    }
    bind();
    initZoom();
    updateClipboardUI();
    renderAll();
    await updateChips();
    window.__ksm = { getAppData: () => appData, swapCells, assignCellData, cloneCellData, candidateLayer, downloadText, downloadObject, safeInit };
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function safeInit() {
    init().catch(e => {
      console.error("Initialization error:", e);
      const b = $("banner") || document.body;
      const errDiv = document.createElement("div");
      errDiv.id = "initErrorNotice";
      errDiv.style.cssText = "background:#7f1d1d;color:#fee2e2;padding:16px;margin:12px;border-radius:10px;font-size:14px;line-height:1.5;";

      const title = document.createElement("div");
      title.innerHTML = "<strong>⚠️ Erro na inicialização do aplicativo:</strong>";
      errDiv.appendChild(title);

      const msg = document.createElement("div");
      msg.style.marginTop = "6px";
      msg.textContent = (e && e.message) ? e.message : String(e);
      errDiv.appendChild(msg);

      const btnGroup = document.createElement("div");
      btnGroup.style.cssText = "margin-top:12px;display:flex;gap:10px;flex-wrap:wrap;";

      // 1. Resgate do rascunho salvo do usuário (se existir no localStorage)
      let userDraftJson = null;
      try {
        userDraftJson = localStorage.getItem(DRAFT_KEY) || localStorage.getItem(DRAFT_V18_KEY);
      } catch (eStorage) { userDraftJson = null; }

      if (userDraftJson) {
        const btnDraft = document.createElement("button");
        btnDraft.type = "button";
        btnDraft.id = "btnRescueUserDraft";
        btnDraft.style.cssText = "padding:8px 14px;background:#22c55e;color:#052e16;border:none;border-radius:6px;font-weight:bold;cursor:pointer;";
        btnDraft.textContent = "Baixar Rascunho Local do Usuário (JSON)";
        btnDraft.onclick = () => {
          try {
            downloadObject(JSON.parse(userDraftJson), "ksm_rascunho_resgate_usuario.json");
          } catch (eParse) {
            downloadText(userDraftJson, "ksm_rascunho_bruto.json", "application/json");
          }
        };
        btnGroup.appendChild(btnDraft);
      }

      // 2. Resgate do estado em memória (appData) se válido e diferente do original
      if (typeof appData === "object" && appData !== null && appData !== EMBEDDED) {
        const btnState = document.createElement("button");
        btnState.type = "button";
        btnState.id = "btnRescueSession";
        btnState.style.cssText = "padding:8px 14px;background:#3b82f6;color:white;border:none;border-radius:6px;font-weight:bold;cursor:pointer;";
        btnState.textContent = "Baixar Estado da Sessão Atual (JSON)";
        btnState.onclick = () => downloadObject(appData, "ksm_sessao_resgate.json");
        btnGroup.appendChild(btnState);
      }

      // 3. Resgate do mapa padrão embutido
      const btnDefault = document.createElement("button");
      btnDefault.type = "button";
      btnDefault.id = "btnInitRescue";
      btnDefault.style.cssText = "padding:8px 14px;background:#fff;color:#991b1b;border:none;border-radius:6px;font-weight:bold;cursor:pointer;";
      btnDefault.textContent = "Baixar Mapa Padrão Embutido (JSON)";
      btnDefault.onclick = () => downloadObject(EMBEDDED, "ksm_padrao_embutido.json");
      btnGroup.appendChild(btnDefault);

      errDiv.appendChild(btnGroup);

      if (b.prepend) b.prepend(errDiv);
      else b.appendChild(errDiv);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", safeInit);
  else safeInit();
})();
