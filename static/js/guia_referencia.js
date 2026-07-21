/*!
 * MyFinance 2.0 — Aba Referência do Manual de Uso
 * Lê Docs/GUIA_DO_USUARIO_MYFINANCE.md via /api/guia, renderiza e permite busca.
 * Fonte única: editar o Markdown atualiza esta tela automaticamente.
 */
(function () {
  'use strict';

  var state = { loaded: false, loading: false, sections: [], query: '' };

  // ── Estilos ────────────────────────────────────────────────────────────────
  var CSS = [
    '.gref-toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:1rem}',
    '.gref-search{flex:1;min-width:220px;position:relative}',
    '.gref-search input{width:100%;padding:9px 12px 9px 34px;border-radius:8px;font-size:0.88rem;',
    'background:var(--glass-bg);border:1px solid var(--glass-border);color:var(--text-light)}',
    '.gref-search input:focus{outline:none;border-color:var(--primary)}',
    '.gref-search i{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--text-muted);font-size:0.85rem}',
    '.gref-count{font-size:0.8rem;color:var(--text-muted);white-space:nowrap}',
    '.gref-layout{display:flex;gap:1.25rem;align-items:flex-start}',
    '.gref-toc{width:250px;flex-shrink:0;position:sticky;top:12px;max-height:78vh;overflow-y:auto;',
    'background:var(--glass-bg);border:1px solid var(--glass-border);border-radius:12px;padding:12px}',
    '.gref-toc::-webkit-scrollbar{width:6px}',
    '.gref-toc::-webkit-scrollbar-thumb{background:rgba(99,102,241,0.5);border-radius:4px}',
    '.gref-toc-title{font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-muted);margin-bottom:8px}',
    '.gref-toc a{display:block;padding:5px 8px;border-radius:6px;font-size:0.82rem;color:var(--text-muted);',
    'text-decoration:none;line-height:1.35;cursor:pointer}',
    '.gref-toc a:hover{background:rgba(255,255,255,0.06);color:var(--text-light)}',
    '.gref-toc a.lvl2{padding-left:18px;font-size:0.78rem}',
    '.gref-body{flex:1;min-width:0;max-height:78vh;overflow-y:auto;padding-right:6px}',
    '.gref-body::-webkit-scrollbar{width:8px}',
    '.gref-body::-webkit-scrollbar-thumb{background:rgba(99,102,241,0.45);border-radius:4px}',
    '.gref-sec{background:var(--glass-bg);border:1px solid var(--glass-border);border-radius:12px;',
    'padding:16px 20px;margin-bottom:12px}',
    '.gref-sec h1,.gref-sec h2{font-size:1.12rem;color:var(--text-light);margin:0 0 10px}',
    '.gref-sec h3{font-size:0.98rem;color:var(--primary);margin:16px 0 8px}',
    '.gref-sec h4{font-size:0.88rem;color:var(--text-light);margin:12px 0 6px}',
    '.gref-sec p,.gref-sec li{font-size:0.87rem;line-height:1.65;color:#cbd5e1}',
    '.gref-sec ul,.gref-sec ol{padding-left:20px;margin:8px 0}',
    '.gref-sec li{margin-bottom:4px}',
    '.gref-sec strong{color:var(--text-light)}',
    '.gref-sec code{background:rgba(148,163,184,0.16);padding:1px 5px;border-radius:4px;font-size:0.82rem}',
    '.gref-sec pre{background:rgba(15,23,42,0.85);border:1px solid var(--glass-border);border-radius:8px;',
    'padding:12px;overflow-x:auto;margin:10px 0}',
    '.gref-sec pre code{background:none;padding:0;font-size:0.8rem;line-height:1.55;color:#a5b4fc}',
    '.gref-sec table{width:100%;border-collapse:collapse;font-size:0.82rem;margin:10px 0}',
    '.gref-sec th{text-align:left;padding:7px 9px;background:rgba(59,130,246,0.14);color:var(--text-light);',
    'border-bottom:1px solid var(--glass-border);font-weight:600}',
    '.gref-sec td{padding:7px 9px;border-bottom:1px solid rgba(255,255,255,0.06);vertical-align:top}',
    '.gref-sec blockquote{border-left:3px solid var(--primary);background:rgba(59,130,246,0.08);',
    'margin:10px 0;padding:9px 14px;border-radius:0 8px 8px 0}',
    '.gref-sec blockquote p{margin:0;font-size:0.85rem}',
    '.gref-sec hr{border:none;border-top:1px solid var(--glass-border);margin:14px 0}',
    '.gref-sec img{max-width:100%;border-radius:8px}',
    '.gref-hl{background:rgba(250,204,21,0.32);color:#fff;border-radius:3px;padding:0 2px}',
    '.gref-state{text-align:center;padding:2rem;color:var(--text-muted);font-size:0.9rem}',
    '@media(max-width:900px){.gref-layout{flex-direction:column}.gref-toc{width:100%;position:static;max-height:220px}',
    '.gref-body{max-height:none}}'
  ].join('');

  function injectCss() {
    if (document.getElementById('gref-styles')) return;
    var s = document.createElement('style');
    s.id = 'gref-styles';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  // ── Utilidades ─────────────────────────────────────────────────────────────
  function esc(t) {
    return String(t).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // Remove acentos e caixa — busca por "orcamento" acha "Orçamento"
  function norm(t) {
    return String(t).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }

  function slug(t) {
    return norm(t).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60);
  }

  /* Divide o Markdown em seções pelos títulos de nível 1 e 2.
     Cada seção vira um card independente — é a unidade de busca. */
  function splitSections(md) {
    var lines = md.split('\n');
    var out = [];
    var cur = null;
    var inFence = false;

    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (/^```/.test(line)) inFence = !inFence;

      var m = !inFence && line.match(/^(#{1,2})\s+(.*)$/);
      if (m) {
        if (cur) out.push(cur);
        cur = { level: m[1].length, title: m[2].trim(), id: '', lines: [line] };
        cur.id = 'gref-' + slug(cur.title) + '-' + out.length;
      } else if (cur) {
        cur.lines.push(line);
      }
    }
    if (cur) out.push(cur);

    return out.map(function (s) {
      s.md = s.lines.join('\n');
      s.haystack = norm(s.md);
      delete s.lines;
      return s;
    });
  }

  function renderMd(md) {
    if (window.marked) {
      var opts = { headerIds: false, mangle: false, breaks: false };
      return window.marked.parse ? window.marked.parse(md, opts) : window.marked(md, opts);
    }
    return '<pre>' + esc(md) + '</pre>'; // fallback se o CDN falhar
  }

  // Destaca o termo buscado sem quebrar as tags do HTML já renderizado
  function highlight(html, query) {
    if (!query || query.length < 2) return html;
    var q = norm(query).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    var parts = html.split(/(<[^>]*>)/g);
    for (var i = 0; i < parts.length; i++) {
      if (parts[i].charAt(0) === '<' || !parts[i].trim()) continue;
      parts[i] = parts[i].replace(new RegExp('(' + q + ')', 'gi'), function (mt) {
        return '<mark class="gref-hl">' + mt + '</mark>';
      });
    }
    return parts.join('');
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  function visibleSections() {
    if (!state.query || state.query.length < 2) return state.sections;
    var q = norm(state.query);
    return state.sections.filter(function (s) { return s.haystack.indexOf(q) !== -1; });
  }

  function draw() {
    var toc = document.getElementById('grefToc');
    var body = document.getElementById('grefBody');
    var count = document.getElementById('grefCount');
    if (!toc || !body) return;

    var secs = visibleSections();

    count.textContent = state.query.length >= 2
      ? secs.length + (secs.length === 1 ? ' seção encontrada' : ' seções encontradas')
      : state.sections.length + ' seções';

    if (!secs.length) {
      toc.innerHTML = '';
      body.innerHTML = '<div class="gref-state">Nenhum resultado para <strong>' +
        esc(state.query) + '</strong>.<br>Tente outro termo — por exemplo "budget", "NOK" ou "câmbio".</div>';
      return;
    }

    toc.innerHTML = '<div class="gref-toc-title">Conteúdo</div>' + secs.map(function (s) {
      return '<a class="' + (s.level === 2 ? 'lvl2' : '') + '" data-target="' + s.id + '">' +
        esc(s.title) + '</a>';
    }).join('');

    body.innerHTML = secs.map(function (s) {
      return '<div class="gref-sec" id="' + s.id + '">' +
        highlight(renderMd(s.md), state.query) + '</div>';
    }).join('');

    toc.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        var el = document.getElementById(a.dataset.target);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }

  function debounce(fn, ms) {
    var t;
    return function () {
      var args = arguments, ctx = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }

  function shell() {
    return '' +
      '<div class="gref-toolbar">' +
        '<div class="gref-search">' +
          '<i class="fa-solid fa-magnifying-glass"></i>' +
          '<input type="search" id="grefSearch" placeholder="Buscar no guia — ex.: NOK, budget, câmbio, patrimônio" autocomplete="off">' +
        '</div>' +
        '<span class="gref-count" id="grefCount"></span>' +
      '</div>' +
      '<div class="gref-layout">' +
        '<nav class="gref-toc" id="grefToc"></nav>' +
        '<div class="gref-body" id="grefBody"></div>' +
      '</div>';
  }

  // ── Carregamento ───────────────────────────────────────────────────────────
  function load() {
    var host = document.getElementById('guiaTab-referencia');
    if (!host || state.loading) return;

    if (state.loaded) { draw(); return; }

    state.loading = true;
    injectCss();
    host.innerHTML = '<div class="gref-state"><i class="fa-solid fa-spinner fa-spin"></i> A carregar o guia...</div>';

    fetch('/api/guia')
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.d.error || 'Falha ao carregar');
        state.sections = splitSections(res.d.content);
        state.loaded = true;
        host.innerHTML = shell();
        document.getElementById('grefSearch').addEventListener('input', debounce(function (e) {
          state.query = e.target.value.trim();
          draw();
          var b = document.getElementById('grefBody');
          if (b) b.scrollTop = 0;
        }, 180));
        draw();
      })
      .catch(function (err) {
        host.innerHTML = '<div class="gref-state" style="color:var(--error)">' +
          '<i class="fa-solid fa-triangle-exclamation"></i> ' + esc(err.message) +
          '<br><small>Verifique se o arquivo Docs/GUIA_DO_USUARIO_MYFINANCE.md existe no servidor.</small></div>';
      })
      .finally(function () { state.loading = false; });
  }

  window.initGuiaReferencia = load;
})();
