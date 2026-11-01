// ksm_core.js — gêmeo JS de ksm_core.py (UID exato + hash canônico).
// Sem dependências. Usado pelo app v06 e pelos testes Node.
const VOLATILE_KEYS = new Set(["updated_at", "generated_at", "timestamp", "saved_at", "exported_at"]);

function keyCompare(a, b) {
  // paridade da ordenação do objeto JSON (kdd_k): inteiro-like numericamente
  // ascendem e precedem; demais lexicográfica (code units).
  const ia = /^(-?(0|[1-9][0-9]*))$/.test(a) && a[0] !== "-";
  const ib = /^(-?(0|[1-9][0-9]*))$/.test(b) && b[0] !== "-";
  if (ia && ib) { const n = Number(a) - Number(b); if (n !== 0) return n; return a < b ? -1 : a > b ? 1 : 0; }
  if (ia !== ib) return ia ? -1 : 1;
  return a < b ? -1 : a > b ? 1 : 0;
}

function canonicalize(o) {
  if (Array.isArray(o)) return o.map(canonicalize);
  if (o && typeof o === "object") {
    const out = {};
    // inteiro-like em JS são enumerados sempre numericamente; coloca em ordem explícito.
    const intKeys = Object.keys(o).filter(k => /^(-?(0|[1-9][0-9]*))$/.test(k) && k[0] !== "-").sort((a, b) => Number(a) - Number(b));
    const strKeys = Object.keys(o).filter(k => !/^(-?(0|[1-9][0-9]*))$/.test(k) || k[0] === "-").sort(keyCompare);
    for (const k of intKeys.concat(strKeys)) {
      if (!VOLATILE_KEYS.has(k)) out[k] = canonicalize(o[k]);
    }
    return out;
  }
  return o;
}

function canonicalString(o) {
  return JSON.stringify(canonicalize(o));
}

// JSON.parse corrompe inteiros >= 2**53. Antes do parse, coloca em string
// apenas valores de "uid" com 16+ dígitos (sem alterar outros números).
// Lookahead NÃO consome a fronteira: cobre vírgula/objeto-array/fim do texto
// e nunca divide o número (caso "uid":<17+ dígitos><dígito>,<campo> que antes
// produzava JSON inválido como "…8102"9,"x":1).
function parseWithExactUid(text) {
  const fixed = String(text).replace(/"uid"\s*:\s*(-?\d{16,})(?=\s*[,}\]]|\s*$)/g, '"uid":"$1"');
  return JSON.parse(fixed);
}

// Compatibilidade com o nome usado no núcleo Python/testes antigos.
function parseJsonBigUid(text) {
  return parseWithExactUid(text);
}

function uidText(data) {
  try {
    return String(data && data.references && data.references.sofle && data.references.sofle.uid || "");
  } catch (e) { return ""; }
}

// ---------------------------------------------------------------- validação
// Compartilhada entre app (navegador) e testes Node — F3: completude obrigatória.
const CORNE_REF_LAYERS = ["default_layer", "lower_layer", "raise_layer", "system_layer"];

function layerRows(kb) { return kb === "corne" ? 3 : 4; }
function layerThumbs(kb) { return kb === "corne" ? 6 : 10; }

function flatLayer(lay) {
  if (!lay) return [];
  if (Array.isArray(lay)) {
    return lay.flat(Infinity);
  }
  if (typeof lay === "object") {
    const m = Array.isArray(lay.matrix) ? lay.matrix.flat(Infinity) : [];
    const t = Array.isArray(lay.thumbs) ? lay.thumbs.flat(Infinity) : [];
    return m.concat(t);
  }
  return [lay];
}

function validateCorneLayer(lid, label, lay, errs) {
  if (!lay || lay.binding_count !== 42) { errs.push(label + " " + lid + ": 42 bindings esperados"); return; }
  if (!Array.isArray(lay.bindings) || lay.bindings.length !== 42) { errs.push(label + " " + lid + ": bindings[42] ausente"); return; }
  if (!lay.matrix || lay.matrix.length !== 3 || lay.matrix.some(r => !Array.isArray(r) || r.length !== 12)) {
    errs.push(label + " " + lid + ": matrix deve ser 3x12");
    return;
  }
  if (!Array.isArray(lay.thumbs) || lay.thumbs.length !== 6) errs.push(label + " " + lid + ": thumbs deve ter 6");
  for (const cell of flatLayer(lay)) {
    if (!cell || typeof cell !== "object") { errs.push(label + " " + lid + ": célula inválida"); return; }
    if (typeof cell.binding !== "string" || cell.binding.length > 200) { errs.push(label + " " + lid + ": binding inválido"); return; }
  }
}

function validateSofleVil(v, prefix, errs) {
  if (!Array.isArray(v.layout) || v.layout.length !== 16) { errs.push(prefix + ".layout deve ter 16 camadas"); return false; }
  const okShape = v.layout.every(g => Array.isArray(g) && g.length === 10 && g.every(r => Array.isArray(r) && r.length === 6));
  if (!okShape) errs.push(prefix + ".layout deve ser 10x6 por camada");
  if (typeof v.uid !== "string" || !/^-?\d+$/.test(v.uid)) errs.push(prefix + ".uid deve ser string decimal exata");
  if (!Array.isArray(v.encoder_layout) || v.encoder_layout.length !== 16) errs.push(prefix + ".encoder_layout deve ter 16 camadas");
  for (const k of ["macro", "tap_dance", "combo", "key_override", "alt_repeat_key"]) {
    if (!Array.isArray(v[k])) errs.push(prefix + "." + k + " ausente");
  }
  if (!v.settings || typeof v.settings !== "object") errs.push(prefix + ".settings ausente");
  return true;
}

function validateDataset(obj, allowV5) {
  const errs = [];
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) return ["a raiz do JSON não é um objeto"];
  const okSchema = obj.schema_version === 6 || (allowV5 && obj.schema_version === 5);
  if (!okSchema) errs.push("schema_version incompatível: " + JSON.stringify(obj.schema_version) + (allowV5 ? " (esperado 5 ou 6)" : " (esperado 6)"));
  const order = obj.metadata && obj.metadata.layers_order;
  if (!Array.isArray(order) || order.length !== 10) errs.push("metadata.layers_order deve ter 10 camadas");
  // F10: o campo nasce no schema 6. A validação de IMPORTAÇÃO respeita o esquema da
  // versão importada: o v05 original (Corne/keymap_data.json) não tem "conflicts" e NÃO deve ser recusado por isso.
  if (obj.schema_version === 6 && !Array.isArray(obj.conflicts)) errs.push("campo conflicts deve ser lista (obrigatório no schema 6)");
  if (!obj.layers || typeof obj.layers !== "object") {
    errs.push("objeto layers ausente");
    return errs;
  }
  for (const lid of order || []) {
    const lay = obj.layers[lid];
    if (!lay || !lay.corne || !lay.sofle) { errs.push("camada " + lid + " sem corne/sofle"); continue; }
    for (const kb of ["corne", "sofle"]) {
      const layKb = lay[kb];
      const m = layKb ? layKb.matrix : null, t = layKb ? layKb.thumbs : null;
      const rows = layerRows(kb), nThumbs = layerThumbs(kb);
      if (!Array.isArray(m) || m.length !== rows || m.some(r => !Array.isArray(r) || r.length !== 12)) {
        errs.push("camada " + lid + "/" + kb + " matrix deve ser " + rows + "x12");
        continue;
      }
      if (!Array.isArray(t) || t.length !== nThumbs) errs.push("camada " + lid + "/" + kb + " thumbs deve ter " + nThumbs);
      for (const cell of flatLayer(layKb)) {
        if (!cell || typeof cell !== "object") { errs.push("célula inválida em " + lid + "/" + kb); break; }
        for (const k of ["label", "impl_zmk", "impl_qmk"]) {
          if (typeof cell[k] !== "string") { errs.push("célula " + lid + "/" + kb + " sem texto em " + k); break; }
          if (cell[k].length > 400) { errs.push("texto excessivo em " + lid + "/" + kb + "." + k); break; }
        }
      }
    }
  }
  if (obj.schema_version === 6) {
    const ref = obj.references || {};
    if (!ref.corne || !ref.corne.native_layers) errs.push("references.corne.native_layers ausente");
    else for (const n of CORNE_REF_LAYERS) validateCorneLayer(n, "references.corne.native_layers", ref.corne.native_layers[n], errs);
    if (!ref.sofle || !ref.sofle.vil) errs.push("references.sofle.vil ausente");
    else validateSofleVil(ref.sofle.vil, "references.sofle.vil", errs);

    // perfis completos (F3): candidato espelha layers com dimensões e conteúdo idênticos
    const cand = obj.profiles && obj.profiles.candidato_teste;
    if (!cand || !cand.corne || !cand.sofle) {
      errs.push("profiles.candidato_teste (corne/sofle) ausente");
    } else {
      for (const lid of order || []) {
        for (const kb of ["corne", "sofle"]) {
          const lay = obj.layers[lid] && obj.layers[lid][kb];
          const mir = cand[kb] && cand[kb].layers && cand[kb].layers[lid];
          if (!mir || typeof mir !== "object") { errs.push("profiles.candidato_teste." + kb + ".layers sem " + lid); continue; }
          const mErrs = [];
          const m = mir.matrix, t = mir.thumbs, rows = layerRows(kb), nT = layerThumbs(kb);
          if (!Array.isArray(m) || m.length !== rows || m.some(r => !Array.isArray(r) || r.length !== 12)) mErrs.push("matrix " + rows + "x12");
          if (!Array.isArray(t) || t.length !== nT) mErrs.push("thumbs " + nT);
          if (JSON.stringify(lay) !== JSON.stringify(mir)) mErrs.push("espelho divergente de layers." + lid);
          if (mErrs.length) errs.push("perfis " + kb + "/" + lid + ": " + mErrs.join("; "));
        }
      }
    }
    const base = obj.profiles && obj.profiles.baseline_instalado;
    if (!base || !base.corne || !base.sofle) {
      errs.push("profiles.baseline_instalado (corne/sofle) ausente");
    } else {
      const bl = base.corne.native_layers;
      const names = Array.isArray(bl) ? bl : (bl && typeof bl === "object" ? Object.keys(bl) : null);
      for (const n of CORNE_REF_LAYERS) {
        if (!names || !names.includes(n)) errs.push("profiles.baseline_instalado.corne.native_layers sem " + n);
      }
      if (typeof base.sofle.uid !== "string" || !/^-?\d+$/.test(base.sofle.uid)) errs.push("profiles.baseline_instalado.sofle.uid deve ser string decimal exata");
    }
  }
  const isV5 = obj.schema_version === 5;
  const simple = obj.profiles && obj.profiles.corne_simples_v01;
  if (!isV5 && !simple) {
    errs.push("profiles.corne_simples_v01 ausente (obrigatório para o perfil padrão)");
  } else if (simple !== undefined) {
    const expected = Array.from({ length: 7 }, (_, i) => "L" + i);
    if (!simple || simple.keyboard !== "corne" || JSON.stringify(simple.layers_order) !== JSON.stringify(expected)) {
      errs.push("Corne Simples deve conter L0 a L6, nesta ordem");
    } else {
      if (!simple.layers || JSON.stringify(Object.keys(simple.layers).sort()) !== JSON.stringify(expected)) errs.push("Corne Simples: exatamente sete camadas obrigatórias");
      for (const lid of expected) {
        const lay = simple.layers && simple.layers[lid];
        if (!lay || !Array.isArray(lay.matrix) || lay.matrix.length !== 3 || lay.matrix.some(r => !Array.isArray(r) || r.length !== 12) || !Array.isArray(lay.thumbs) || lay.thumbs.length !== 6) errs.push("Corne Simples: " + lid + " deve ter matrix 3x12 e seis dedões");
        if (!simple.layers_info || !simple.layers_info[lid] || typeof simple.layers_info[lid].name !== "string") errs.push("Corne Simples: nome ausente em " + lid);
        for (const c of flatLayer(lay || {})) {
          if (!c || typeof c.label !== "string" || !c.label.trim() || typeof c.impl_zmk !== "string" || !c.impl_zmk.startsWith("&") || c.impl_zmk.length > 400 || typeof c.impl_qmk !== "string") errs.push("Corne Simples: célula inválida em " + lid);
        }
      }
    }
  }
  return errs;
}

async function sha256Hex(text) {
  const bytes = new TextEncoder().encode(text);
  if (globalThis.crypto && globalThis.crypto.subtle) {
    const buf = await globalThis.crypto.subtle.digest("SHA-256", bytes);
    return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
  }
  // Node sem WebCrypto: fallback via require (apenas ambiente de teste).
  try {
    const nodeCrypto = require("crypto");
    return nodeCrypto.createHash("sha256").update(bytes).digest("hex");
  } catch (e) {
    throw new Error("SHA-256 indisponível neste ambiente");
  }
}

async function canonicalHashAsync(obj) {
  return sha256Hex(canonicalString(obj));
}

function canonicalHash(obj) {
  // Síncrono apenas quando o runtime expõe hash síncrono (Node); no navegador use o async.
  try {
    const nodeCrypto = require("crypto");
    return nodeCrypto.createHash("sha256").update(canonicalString(obj), "utf8").digest("hex");
  } catch (e) {
    throw new Error("use canonicalHashAsync no navegador");
  }
}

function auditLayerReachability(layersObj, kb, options) {
  options = options || {};
  const isCorne = (kb === "corne");
  const isSofle = (kb === "sofle");

  // Normalização de entrada: aceita objeto de camadas { L0: ... }, array, ou .vil { layout: [...], tap_dance: [...] }
  let actualLayers = {};
  let tapDances = options.tap_dance || options.tap_dances || [];
  if (layersObj && typeof layersObj === "object" && Array.isArray(layersObj.layout)) {
    for (let i = 0; i < layersObj.layout.length; i++) {
      actualLayers["L" + i] = layersObj.layout[i];
    }
    if (tapDances.length === 0 && Array.isArray(layersObj.tap_dance)) {
      tapDances = layersObj.tap_dance;
    }
  } else if (Array.isArray(layersObj)) {
    for (let i = 0; i < layersObj.length; i++) {
      actualLayers["L" + i] = layersObj[i];
    }
  } else if (layersObj && typeof layersObj === "object") {
    for (const k of Object.keys(layersObj)) {
      if (/^L\d+$/.test(k)) {
        actualLayers[k] = layersObj[k];
      }
    }
  }

  const layerIds = Object.keys(actualLayers).filter(k => /^L\d+$/.test(k)).sort((a,b) => parseInt(a.slice(1)) - parseInt(b.slice(1)));
  const graph = {};
  for (const lid of layerIds) {
    graph[lid] = { lid, incoming: [], outgoing: [] };
  }

  // Mapa de behaviors declarados no ZMK (Corne)
  const behaviorsMap = {};
  if (options.behaviors && Array.isArray(options.behaviors)) {
    for (const b of options.behaviors) {
      if (b && b.name) behaviorsMap[b.name] = b;
    }
  }

  for (const fromLid of layerIds) {
    const lay = actualLayers[fromLid];
    if (!lay) continue;
    const cells = flatLayer(lay);
    for (let pos = 0; pos < cells.length; pos++) {
      const cell = cells[pos];
      if (!cell) continue;

      if (isCorne) {
        // CORNE (ZMK): analisa ESTRITAMENTE o campo nativo ZMK (impl_zmk / binding)
        const code = String(cell.impl_zmk || cell.binding || (typeof cell === "string" ? cell : "")).trim();
        if (!code || code === "&none" || code === "&trans") continue;

        // Diretivas padrão ZMK: &to N, &mo N, &tog N, &sl N
        const zmkMatches = [...code.matchAll(/&(to|mo|tog|sl)\s+(\d+)/gi)];
        for (const m of zmkMatches) {
          const op = m[1].toLowerCase();
          const type = "&" + op;
          const targetLid = "L" + m[2];
          const isPersistent = (op === "to" || op === "tog");
          if (graph[targetLid]) {
            const edge = { fromLid, toLid: targetLid, pos, type, code: m[0], isPersistent };
            graph[targetLid].incoming.push(edge);
            graph[fromLid].outgoing.push(edge);
          }
        }

        // Diretiva layer-tap ZMK: &lt N KEY
        const ltMatches = [...code.matchAll(/&lt\s+(\d+)/gi)];
        for (const m of ltMatches) {
          const targetLid = "L" + m[1];
          if (graph[targetLid]) {
            const edge = { fromLid, toLid: targetLid, pos, type: "&lt", code: m[0], isPersistent: false };
            graph[targetLid].incoming.push(edge);
            graph[fromLid].outgoing.push(edge);
          }
        }

        // Resolução estrita de behaviors personalizados ZMK via options.behaviors
        const customMatch = code.match(/^&([A-Za-z0-9_]+)\s+(.+)$/);
        if (customMatch) {
          const bName = customMatch[1];
          const args = customMatch[2].trim().split(/\s+/);
          const beh = behaviorsMap[bName];
          if (beh && Array.isArray(beh.bindings)) {
            for (let bIdx = 0; bIdx < beh.bindings.length; bIdx++) {
              const bOp = beh.bindings[bIdx];
              if ((bOp === "&mo" || bOp === "&fp_mo" || bOp === "&to" || bOp === "&tog" || bOp === "&sl") && args[bIdx] !== undefined) {
                const targetNum = args[bIdx].trim();
                if (/^\d+$/.test(targetNum)) {
                  const targetLid = "L" + targetNum;
                  const isPersistent = (bOp === "&to" || bOp === "&tog");
                  if (graph[targetLid]) {
                    const edge = { fromLid, toLid: targetLid, pos, type: "behavior:" + bName, code: code, isPersistent };
                    graph[targetLid].incoming.push(edge);
                    graph[fromLid].outgoing.push(edge);
                  }
                }
              }
            }
          }
        }

      } else if (isSofle) {
        // SOFLE (Vial/QMK): analisa ESTRITAMENTE o campo nativo QMK (impl_qmk)
        const code = String(cell.impl_qmk || (typeof cell === "string" ? cell : "")).trim();
        if (!code || code === "KC_NO" || code === "KC_TRNS") continue;

        // Diretivas padrão QMK: TO(N), MO(N), TG(N), TT(N), OSL(N), DF(N)
        const qmkMatches = [...code.matchAll(/\b(TO|MO|TG|TT|OSL|DF)\s*\(\s*(\d+)\s*\)/g)];
        for (const m of qmkMatches) {
          const type = m[1];
          const targetLid = "L" + m[2];
          const isPersistent = (type === "TO" || type === "TG" || type === "TT" || type === "DF");
          if (graph[targetLid]) {
            const edge = { fromLid, toLid: targetLid, pos, type, code: m[0], isPersistent };
            graph[targetLid].incoming.push(edge);
            graph[fromLid].outgoing.push(edge);
          }
        }

        // Layer-tap QMK: LT<N>(...) ou LT(<N>, ...)
        const ltMatches = [...code.matchAll(/\bLT(\d+)\s*\(|\bLT\s*\(\s*(\d+)\s*,/g)];
        for (const m of ltMatches) {
          const targetNum = m[1] || m[2];
          const targetLid = "L" + targetNum;
          if (graph[targetLid]) {
            const edge = { fromLid, toLid: targetLid, pos, type: "LT", code: m[0], isPersistent: false };
            graph[targetLid].incoming.push(edge);
            graph[fromLid].outgoing.push(edge);
          }
        }

        // Resolução estrita e dinâmica de Tap Dance via tap_dance
        const tdMatches = [...code.matchAll(/\bTD\s*\(\s*(\d+)\s*\)/g)];
        for (const m of tdMatches) {
          const tdIdx = parseInt(m[1], 10);
          if (tdIdx < tapDances.length && Array.isArray(tapDances[tdIdx])) {
            const tdDef = tapDances[tdIdx];
            for (const action of tdDef) {
              if (typeof action === "string") {
                const subMatches = [...action.matchAll(/\b(TO|MO|TG|TT|OSL|DF)\s*\(\s*(\d+)\s*\)/g)];
                for (const sm of subMatches) {
                  const subOp = sm[1];
                  const targetLid = "L" + sm[2];
                  const isPersistent = (subOp === "TO" || subOp === "TG" || subOp === "TT" || subOp === "DF");
                  if (graph[targetLid]) {
                    const edge = { fromLid, toLid: targetLid, pos, type: "TD(" + tdIdx + ")", code: "TD(" + tdIdx + ")->" + sm[0], isPersistent };
                    graph[targetLid].incoming.push(edge);
                    graph[fromLid].outgoing.push(edge);
                  }
                }
                const ltSubMatches = [...action.matchAll(/\bLT(\d+)\s*\(|\bLT\s*\(\s*(\d+)\s*,/g)];
                for (const sm of ltSubMatches) {
                  const targetNum = sm[1] || sm[2];
                  const targetLid = "L" + targetNum;
                  if (graph[targetLid]) {
                    const edge = { fromLid, toLid: targetLid, pos, type: "TD(" + tdIdx + ")", code: "TD(" + tdIdx + ")->" + sm[0], isPersistent: false };
                    graph[targetLid].incoming.push(edge);
                    graph[fromLid].outgoing.push(edge);
                  }
                }
              }
            }
          }
        }
      }
    }
  }

  // Combos dinâmicos
  if (options.combos && Array.isArray(options.combos)) {
    for (const c of options.combos) {
      const cLayers = c.layers ? c.layers.map(n => "L" + n) : layerIds;
      const cAct = String(c.action || c.binding || "");
      const targets = [];
      for (const m of cAct.matchAll(/(?:TO|MO|TG|TT|OSL|DF|&to|&mo|&tog)\s*\(?(\d+)/g)) {
        const isPers = m[0].startsWith("TO") || m[0].startsWith("&to") || m[0].startsWith("TG") || m[0].startsWith("&tog") || m[0].startsWith("DF");
        targets.push({ toLid: "L" + m[1], isPers });
      }
      for (const fromLid of cLayers) {
        if (graph[fromLid]) {
          for (const t of targets) {
            if (graph[t.toLid]) {
              const edge = { fromLid, toLid: t.toLid, pos: "combo", type: "combo", code: cAct, isPersistent: t.isPers };
              graph[fromLid].outgoing.push(edge);
              graph[t.toLid].incoming.push(edge);
            }
          }
        }
      }
    }
  }

  // BFS a partir de L0
  const reachable = new Set();
  const reachableDirect = new Set();
  const reachableConditional = new Set();
  const provenConditionals = [];
  const unprovenConditionals = [];
  const queue = [];
  if (graph["L0"]) {
    reachable.add("L0");
    reachableDirect.add("L0");
    queue.push("L0");
  }

  function checkSimultaneousActivation(low, rai) {
    const edgesLow = graph[low].incoming.filter(e => reachable.has(e.fromLid) && (e.type === "MO" || e.type === "LT" || e.type === "&mo" || e.type === "&lt"));
    const edgesRai = graph[rai].incoming.filter(e => reachable.has(e.fromLid) && (e.type === "MO" || e.type === "LT" || e.type === "&mo" || e.type === "&lt"));
    if (edgesLow.length === 0) {
      return { ok: false, reason: low + " não possui ativação momentânea (MO/LT) alcançável (ativação persistente TO/DF desliga outras camadas)" };
    }
    if (edgesRai.length === 0) {
      return { ok: false, reason: rai + " não possui ativação momentânea (MO/LT) alcançável (ativação persistente TO/DF desliga outras camadas)" };
    }

    for (const eL of edgesLow) {
      for (const eR of edgesRai) {
        if (eL.fromLid === eR.fromLid) {
          const pL = eL.pos;
          const pR = eR.pos;
          if (pL !== undefined && pR !== undefined && pL === pR) continue;

          const cellsLow = flatLayer(actualLayers[low] || []);
          const cellsRai = flatLayer(actualLayers[rai] || []);
          const cLow = (typeof pR === "number" && pR < cellsLow.length) ? cellsLow[pR] : null;
          const cRai = (typeof pL === "number" && pL < cellsRai.length) ? cellsRai[pL] : null;
          const strLow = isCorne
            ? String(cLow && (cLow.impl_zmk || cLow.binding || cLow.impl_qmk || (typeof cLow === "string" ? cLow : "")) || "").trim()
            : String(cLow && (cLow.impl_qmk || cLow.impl_zmk || cLow.binding || (typeof cLow === "string" ? cLow : "")) || "").trim();
          const strRai = isCorne
            ? String(cRai && (cRai.impl_zmk || cRai.binding || cRai.impl_qmk || (typeof cRai === "string" ? cRai : "")) || "").trim()
            : String(cRai && (cRai.impl_qmk || cRai.impl_zmk || cRai.binding || (typeof cRai === "string" ? cRai : "")) || "").trim();

          const trnsTokens = ["KC_TRNS", "&trans", ""];
          const rNum = rai.slice(1);
          const lNum = low.slice(1);
          const okLow = trnsTokens.includes(strLow) || strLow.includes("MO(" + rNum + ")") || strLow.includes("LT" + rNum + "(") || strLow.includes("LT(" + rNum + ",") || strLow.includes("MO(") || strLow.includes("&mo " + rNum) || strLow.includes("&lt " + rNum) || strLow.includes("&mo");
          const okRai = trnsTokens.includes(strRai) || strRai.includes("MO(" + lNum + ")") || strRai.includes("LT" + lNum + "(") || strRai.includes("LT(" + lNum + ",") || strRai.includes("MO(") || strRai.includes("&mo " + lNum) || strRai.includes("&lt " + lNum) || strRai.includes("&mo");

          if (okLow || okRai) {
            return { ok: true, reason: "comprovada (ativação momentânea em posições distintas [" + pL + ", " + pR + "] com transparência/intertravamento)" };
          }
        }
      }
    }
    return { ok: false, reason: "combinação não comprovada (não há sobreposição momentânea sem bloqueio demonstrada entre " + low + " e " + rai + ")" };
  }

  let changed = true;
  while (changed) {
    changed = false;
    while (queue.length > 0) {
      const curr = queue.shift();
      if (!graph[curr]) continue;
      for (const out of graph[curr].outgoing) {
        if (!reachable.has(out.toLid)) {
          reachable.add(out.toLid);
          reachableDirect.add(out.toLid);
          queue.push(out.toLid);
          changed = true;
        }
      }
    }

    // Intertravamentos ZMK conditional_layers
    if (isCorne && options.conditional_layers && Array.isArray(options.conditional_layers)) {
      for (const cond of options.conditional_layers) {
        const thenLid = "L" + cond.then_layer;
        const ifLids = (cond.if_layers || []).map(n => "L" + n);
        if (ifLids.length >= 2 && ifLids.every(lid => reachable.has(lid))) {
          const check = checkSimultaneousActivation(ifLids[0], ifLids[1]);
          if (check.ok) {
            if (graph[thenLid] && !reachable.has(thenLid)) {
              reachable.add(thenLid);
              reachableConditional.add(thenLid);
              provenConditionals.push({ target: thenLid, prerequisites: ifLids, reason: check.reason });
              queue.push(thenLid);
              changed = true;
            }
          } else {
            if (!reachable.has(thenLid) && !unprovenConditionals.some(u => u.target === thenLid)) {
              unprovenConditionals.push({ target: thenLid, prerequisites: ifLids, reason: check.reason });
            }
          }
        }
      }
    }

    // Tri-layers / Dual Activation QMK
    if (isSofle) {
      if (options.tri_layers && Array.isArray(options.tri_layers)) {
        for (const tri of options.tri_layers) {
          const adj = "L" + tri.adjust;
          const low = "L" + tri.lower;
          const rai = "L" + tri.raise;
          if (reachable.has(low) && reachable.has(rai)) {
            const check = checkSimultaneousActivation(low, rai);
            if (check.ok) {
              if (graph[adj] && !reachable.has(adj)) {
                reachable.add(adj);
                reachableConditional.add(adj);
                provenConditionals.push({ target: adj, prerequisites: [low, rai], reason: check.reason });
                queue.push(adj);
                changed = true;
              }
            } else {
              if (!reachable.has(adj) && !unprovenConditionals.some(u => u.target === adj)) {
                unprovenConditionals.push({ target: adj, prerequisites: [low, rai], reason: check.reason });
              }
            }
          }
        }
      }
      // Sofle padrão: NAV (L2) + SYM (L4) -> SYSTEM (L6)
      if (graph["L6"] && !reachable.has("L6")) {
        if (reachable.has("L2") && reachable.has("L4")) {
          const l2ToL6 = graph["L2"] && graph["L2"].outgoing.some(o => o.toLid === "L6");
          const l4ToL6 = graph["L4"] && graph["L4"].outgoing.some(o => o.toLid === "L6");
          const check = checkSimultaneousActivation("L2", "L4");
          if ((l2ToL6 && l4ToL6) || check.ok) {
            reachable.add("L6");
            reachableConditional.add("L6");
            provenConditionals.push({ target: "L6", prerequisites: ["L2", "L4"], reason: check.reason });
            queue.push("L6");
            changed = true;
          } else {
            if (!unprovenConditionals.some(u => u.target === "L6")) {
              unprovenConditionals.push({ target: "L6", prerequisites: ["L2", "L4"], reason: check.reason });
            }
          }
        }
      }
    }
  }

  const unreachable = layerIds.filter(lid => !reachable.has(lid));

  // Função BFS para verificar se uma camada consegue retornar a L0
  function canReachL0(startLid) {
    const visited = new Set([startLid]);
    const q = [startLid];
    while (q.length > 0) {
      const node = q.shift();
      if (node === "L0") return true;
      if (!graph[node]) continue;
      for (const out of graph[node].outgoing) {
        if (out.toLid === "L0") return true;
        if (!visited.has(out.toLid) && graph[out.toLid]) {
          visited.add(out.toLid);
          q.push(out.toLid);
        }
      }
    }
    return false;
  }

  // Verificação de saída por alternância (TG / &tog) na mesma tecla física
  function hasToggleExit(lid) {
    for (const e of graph[lid].incoming) {
      if (reachable.has(e.fromLid) && (e.type === "TG" || e.type === "&tog")) {
        const pos = e.pos;
        if (typeof pos === "number") {
          const cells = flatLayer(actualLayers[lid] || []);
          if (pos < cells.length) {
            const c = cells[pos];
            const code = String(c && (c.impl_qmk || c.impl_zmk || c.binding || (typeof c === "string" ? c : "")) || "").trim();
            const num = lid.slice(1);
            if (["KC_TRNS", "&trans", ""].includes(code) || code === "TG(" + num + ")" || code === "&tog " + num) {
              return true;
            }
          }
        }
      }
    }
    return false;
  }

  // Identificação de camadas armadilha e saídas por alternância
  const trapLayers = [];
  const toggleExitLayers = [];
  for (const lid of reachable) {
    if (lid === "L0") continue;
    const hasPersistentIncoming = graph[lid].incoming.some(i => i.isPersistent && reachable.has(i.fromLid));
    if (hasPersistentIncoming) {
      if (hasToggleExit(lid)) {
        toggleExitLayers.push(lid);
      } else if (!canReachL0(lid)) {
        trapLayers.push(lid);
      }
    }
  }

  return {
    graph,
    layerIds,
    reachable: Array.from(reachable).sort((a,b) => parseInt(a.slice(1)) - parseInt(b.slice(1))),
    reachableDirect: Array.from(reachableDirect).sort((a,b) => parseInt(a.slice(1)) - parseInt(b.slice(1))),
    reachableConditional: Array.from(reachableConditional).sort((a,b) => parseInt(a.slice(1)) - parseInt(b.slice(1))),
    provenConditionals,
    unprovenConditionals,
    unreachable: unreachable.sort((a,b) => parseInt(a.slice(1)) - parseInt(b.slice(1))),
    trapLayers: trapLayers.sort((a,b) => parseInt(a.slice(1)) - parseInt(b.slice(1))),
    toggleExitLayers: toggleExitLayers.sort((a,b) => parseInt(a.slice(1)) - parseInt(b.slice(1))),
    mode: "acessibilidade_estatica"
  };
}

if (typeof module !== "undefined") {
  module.exports = {
    canonicalize, canonicalString, canonicalHash, canonicalHashAsync,
    parseWithExactUid, parseJsonBigUid, uidText, sha256Hex, VOLATILE_KEYS,
    layerRows, layerThumbs, flatLayer, validateDataset,
    validateCorneLayer, validateSofleVil, CORNE_REF_LAYERS,
    auditLayerReachability,
  };
}
