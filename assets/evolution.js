(function () {
  var root = document.getElementById('evo');
  if (!root) return;
  var NS = 'http://www.w3.org/2000/svg';
  var SEC = JSON.parse(root.getAttribute('data-sections'));
  var MARKS = JSON.parse(root.getAttribute('data-marks'));
  var stage = root.querySelector('.evo-stage'), tip = root.querySelector('.evo-tip');
  var findBox = root.querySelector('.evo-find input'), findList = root.querySelector('.evo-find ul');
  var D = 8, P = 10, TIER = 146, BOXW = 138, AXIS = 52;
  var robots = [], byId = {}, cols = [], fam = {}, world, svg, gFam, gHover, current = null, pinned = null, TOP = 0, BASE = 0, W = 0, H = 0;
  var touch = false;

  function el(name, attrs, parent) {
    var n = document.createElementNS(NS, name);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  Promise.all([fetch('/assets/robots.json').then(function (r) { return r.json(); }), fetch('/assets/lineage.json').then(function (r) { return r.json(); })])
    .then(function (res) { draw(res[0], res[1]); });

  function draw(rows, links) {
    var markNote = {}; MARKS.forEach(function (m) { markNote[m[0]] = m[1]; });
    rows.forEach(function (r) {
      if (!r[7]) return;
      var o = { i: r[0], n: r[1], s: r[3], c: r[4], m: r[6], y: r[7], p: r[9], d: r[10], mark: markNote[r[0]] || null };
      robots.push(o); byId[o.i] = o;
    });
    links.forEach(function (l) {
      if (!byId[l[0]] || !byId[l[1]]) return;
      (fam[l[0]] = fam[l[0]] || []).push(l[1]); (fam[l[1]] = fam[l[1]] || []).push(l[0]);
    });
    // columns: years before 1950 sit close together, one column a year from 1950, two from 1990
    var byYear = {};
    robots.forEach(function (r) { (byYear[r.y] = byYear[r.y] || []).push(r); });
    var last = Math.max.apply(null, robots.map(function (r) { return r.y; }));
    var early = Object.keys(byYear).map(Number).filter(function (y) { return y < 1950; }).sort(function (a, b) { return a - b; });
    function columns(p) {
      var out = [], x = 3 * p;
      early.forEach(function (y) { out.push({ y: y, x: x, w: 1 }); x += 2.6 * p; });
      var brk = x + 0.2 * p; x += 3 * p;
      for (var y = 1950; y <= last; y++) { var w = y < 1990 ? 1 : 2; out.push({ y: y, x: x, w: w }); x += w === 1 ? 1.1 * p : 2.2 * p; }
      return { cols: out, brk: brk, w: x + 4 * p };
    }
    // fit the whole chart on wide screens; scroll sideways on narrow ones
    P = Math.max(7, Math.min(10, (stage.clientWidth - 8) / columns(1).w));
    D = P * 0.8;
    var lay = columns(P); cols = lay.cols; W = lay.w; var breakX = lay.brk;
    var maxRows = 1;
    cols.forEach(function (c) {
      c.list = (byYear[c.y] || []).slice().sort(function (a, b) { return (a.mark ? 1 : 0) - (b.mark ? 1 : 0) || a.s - b.s || (a.n < b.n ? -1 : 1); });
      maxRows = Math.max(maxRows, Math.ceil(c.list.length / c.w));
    });
    // landmark labels sit in two staggered rows above the chart, in order, so no line crosses another
    var marks = robots.filter(function (r) { return r.mark; });
    var colOf = {}; cols.forEach(function (c) { colOf[c.y] = c; });
    marks.forEach(function (r) { var c = colOf[r.y], k0 = c.list.indexOf(r); r.ax = c.x + (k0 % c.w) * P + D / 2; });
    marks.sort(function (a, b) { return a.ax - b.ax; });
    var perRow = Math.ceil(marks.length / 2), pitch = (W - 20) / (perRow + 0.5);
    BOXW = Math.max(96, Math.min(156, pitch - 16));
    marks.forEach(function (r, j) {
      r.row = j % 2; r.slot = Math.floor(j / 2);
      r.bc = 10 + pitch * (r.slot + 0.5) + (r.row ? pitch / 2 : 0); r.bx = r.bc - BOXW / 2;
    });
    var used = marks.length ? 2 : 0;
    TOP = used * TIER + (used ? 26 : 16);
    BASE = TOP + maxRows * P + 6;
    H = BASE + AXIS;
    cols.forEach(function (c) {
      c.list.forEach(function (r, k) {
        var row = Math.floor(k / c.w), cc = k % c.w;
        r.cx = c.x + cc * P + D / 2; r.cy = BASE - D / 2 - row * P; r.col = c;
      });
    });
    // world
    world = document.createElement('div'); world.className = 'evo-world'; world.style.width = W + 'px'; world.style.height = H + 'px';
    stage.insertBefore(world, tip);
    world.appendChild(tip);
    svg = el('svg', { width: W, height: H, viewBox: '0 0 ' + W + ' ' + H, 'class': 'evo-svg', 'aria-hidden': 'true' }, world);
    el('line', { x1: 10, x2: W - 10, y1: BASE + 0.5, y2: BASE + 0.5, 'class': 'axis' }, svg);
    el('path', { d: 'M' + (breakX + 4) + ',' + (BASE - 6) + 'l6,12M' + (breakX + 11) + ',' + (BASE - 6) + 'l6,12', 'class': 'brk' }, svg);
    var g = el('g', { 'class': 'years' }, svg), lastLabel = -1e9;
    cols.forEach(function (c, k) {
      var cx = c.x + (c.w === 2 ? P : D / 2);
      if (c.y < 1950) {
        var t = el('text', { x: cx, y: BASE + 20 + (k % 2) * 14 }, g); t.textContent = c.y;
      } else if (c.y % 10 === 0 || (c.y === last && c.y - lastLabel >= 4)) {
        el('line', { x1: cx, x2: cx, y1: BASE, y2: BASE + 6, 'class': 'tick' }, g);
        var t2 = el('text', { x: cx, y: BASE + 22, 'class': 'dec' }, g); t2.textContent = c.y; lastLabel = c.y;
      } else if (c.y % 5 === 0) {
        el('line', { x1: cx, x2: cx, y1: BASE, y2: BASE + 3, 'class': 'tick' }, g);
      }
    });
    gFam = el('g', { 'class': 'fam' }, svg);
    var dots = el('g', { 'class': 'dots' }, svg);
    robots.forEach(function (r) { r.el = el('circle', { cx: r.cx, cy: r.cy, r: D / 2, 'class': 's' + r.s }, dots); });
    gHover = el('g', { 'class': 'hover' }, svg);
    // landmark boxes and leader lines
    var lead = el('g', { 'class': 'leads' }, svg);
    var busY = used * TIER + 10;
    marks.forEach(function (r) {
      var boxTop = 6 + (1 - r.row) * TIER, boxBottom = boxTop + TIER - 14, top = r.cy - D / 2 - 3;
      // stay above the neighbouring columns on the way down
      var near = BASE, k = cols.indexOf(r.col);
      for (var j = Math.max(0, k - 2); j <= Math.min(cols.length - 1, k + 2); j++) near = Math.min(near, BASE - Math.ceil(cols[j].list.length / cols[j].w) * P);
      var knee = Math.max(busY + 6, Math.min(top - 6, near - 8));
      el('path', { d: 'M' + r.bc + ',' + boxBottom + 'L' + r.bc + ',' + busY + 'L' + r.ax + ',' + knee + 'L' + r.ax + ',' + top }, lead);
      el('circle', { cx: r.ax, cy: top, r: 1.7, 'class': 'end' }, lead);
      var a = document.createElement('a');
      a.className = 'evo-mark'; a.href = '/' + r.i + '/';
      a.style.left = r.bx + 'px'; a.style.top = boxTop + 'px'; a.style.width = BOXW + 'px'; a.style.height = (TIER - 14) + 'px';
      var img = r.p === 2 ? '<img src="/img/' + r.i + '.ct.webp" alt="" loading="lazy">' : r.p === 1 ? '<img class="ph" src="/img/' + r.i + '.t.webp" alt="" loading="lazy">' : '';
      a.innerHTML = img + '<b>' + esc(r.n) + ' <span>' + r.y + '</span></b><span class="note">' + esc(r.mark) + '</span>';
      a.addEventListener('mouseenter', function () { if (!pinned) hover(r); });
      a.addEventListener('mouseleave', function () { if (!pinned) hover(null); });
      world.appendChild(a);
    });
    wire();
    var start = location.hash.match(/^#([a-z0-9-]+)$/);
    if (start && byId[start[1]]) setTimeout(function () { goTo(byId[start[1]]); }, 300);
    root.classList.add('ready');
  }

  function at(x, y) {
    var c = null;
    for (var k = 0; k < cols.length; k++) {
      var cc = cols[k];
      if (x >= cc.x - 2 && x <= cc.x + cc.w * P) { c = cc; break; }
    }
    if (!c || !c.list.length || y > BASE + 4) return null;
    var row = Math.max(0, Math.floor((BASE - y) / P)), cl = Math.max(0, Math.min(c.w - 1, Math.floor((x - c.x) / P)));
    var k2 = row * c.w + cl;
    if (k2 < c.list.length) return c.list[k2];
    return row <= Math.ceil(c.list.length / c.w) + 1 ? c.list[c.list.length - 1] : null;
  }

  function hover(r) {
    if (current === r) return;
    current = r;
    gFam.innerHTML = ''; gHover.innerHTML = '';
    if (!r) { tip.hidden = true; return; }
    var seen = {}, queue = [[r.i, 0]], edges = [];
    seen[r.i] = 1;
    while (queue.length) {
      var cur = queue.shift();
      if (cur[1] >= 6) continue;
      (fam[cur[0]] || []).forEach(function (n) {
        edges.push([cur[0], n]);
        if (!seen[n]) { seen[n] = 1; queue.push([n, cur[1] + 1]); }
      });
    }
    var drawn = {};
    edges.forEach(function (e) {
      var key = e[0] < e[1] ? e[0] + '|' + e[1] : e[1] + '|' + e[0];
      if (drawn[key]) return; drawn[key] = 1;
      var a = byId[e[0]], b = byId[e[1]];
      if (a.cx > b.cx) { var t = a; a = b; b = t; }
      var lift = 24 + Math.min(90, Math.abs(b.cx - a.cx) * 0.25), my = Math.min(a.cy, b.cy) - lift;
      el('path', { d: 'M' + a.cx + ',' + a.cy + ' C' + a.cx + ',' + my + ' ' + b.cx + ',' + my + ' ' + b.cx + ',' + b.cy }, gFam);
    });
    Object.keys(seen).forEach(function (id) {
      var m = byId[id];
      el('circle', { cx: m.cx, cy: m.cy, r: id === r.i ? 7 : 5.5, 'class': id === r.i ? 'me' : 'kin' }, gHover);
    });
    showTip(r);
  }

  function showTip(r) {
    var sec = SEC[r.s];
    var img = r.p === 2 ? '<img src="/img/' + r.i + '.ct.webp" alt="">' : r.p === 1 ? '<img class="ph" src="/img/' + r.i + '.t.webp" alt="">' : '';
    var kin = (fam[r.i] || []).length;
    tip.innerHTML = img + '<b>' + esc(r.n) + '</b><span class="tm">' + esc([r.m, r.c, r.y].filter(Boolean).join(', ')) + '</span>' +
      (r.d ? '<span class="td">' + esc(r.d) + '</span>' : '') +
      '<span class="ts" style="--c:var(--' + sec[0] + ')">' + esc(sec[1]) + (kin ? '; family in red' : '') + '</span>' +
      (touch ? '<a class="open" href="/' + r.i + '/">Open the entry</a>' : '');
    tip.hidden = false;
    var sw = stage.clientWidth, sl = stage.scrollLeft, tw = tip.offsetWidth, th = tip.offsetHeight;
    var x = r.cx + 16, y = r.cy - th - 14;
    if (x + tw > sl + sw - 8) x = r.cx - tw - 16;
    if (x < sl + 8) x = sl + 8;
    if (y < 8) y = Math.min(H - th - 8, r.cy + 16);
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }

  function local(e) {
    var b = world.getBoundingClientRect();
    return { x: e.clientX - b.left, y: e.clientY - b.top };
  }

  function wire() {
    var drag = null;
    world.addEventListener('pointermove', function (e) {
      if (e.pointerType !== 'mouse' || drag || pinned) return;
      if (e.target.closest && (e.target.closest('.evo-mark') || e.target.closest('.evo-tip'))) return;
      var p = local(e), r = at(p.x, p.y);
      hover(r);
      world.style.cursor = r ? 'pointer' : '';
    });
    world.addEventListener('pointerleave', function () { if (!pinned) hover(null); });
    world.addEventListener('click', function (e) {
      if (e.target.closest && (e.target.closest('.evo-mark') || e.target.closest('.evo-tip'))) return;
      if (drag && drag.moved) return;
      var p = local(e), r = at(p.x, p.y);
      if (!r) { pinned = null; hover(null); return; }
      if (touch) {
        if (pinned === r) { location.href = '/' + r.i + '/'; return; }
        pinned = r; current = null; hover(r); return;
      }
      location.href = '/' + r.i + '/';
    });
    world.addEventListener('pointerdown', function (e) {
      if (e.pointerType === 'touch' || e.pointerType === 'pen') { touch = true; return; }
      touch = false;
      if (e.button !== 0 || (e.target.closest && e.target.closest('a'))) return;
      drag = { x: e.clientX, sl: stage.scrollLeft, moved: false };
    });
    window.addEventListener('pointermove', function (e) {
      if (!drag) return;
      var dx = e.clientX - drag.x;
      if (Math.abs(dx) > 4) { drag.moved = true; root.classList.add('dragging'); pinned = null; hover(null); }
      stage.scrollLeft = drag.sl - dx;
    });
    window.addEventListener('pointerup', function () { setTimeout(function () { drag = null; root.classList.remove('dragging'); }, 0); });
    stage.addEventListener('scroll', edges, { passive: true });
    window.addEventListener('resize', edges);
    edges();
    stage.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight') { stage.scrollBy({ left: 200, behavior: 'smooth' }); e.preventDefault(); }
      if (e.key === 'ArrowLeft') { stage.scrollBy({ left: -200, behavior: 'smooth' }); e.preventDefault(); }
      if (e.key === 'Escape') { pinned = null; hover(null); }
    });
    root.querySelectorAll('.evo-legend button').forEach(function (b) {
      b.addEventListener('click', function () {
        var s = b.getAttribute('data-s'), on = root.getAttribute('data-only') === s;
        root.querySelectorAll('.evo-legend button').forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
        if (on) root.removeAttribute('data-only'); else { root.setAttribute('data-only', s); b.setAttribute('aria-pressed', 'true'); }
      });
    });
    var cur = -1;
    function render() {
      var q = findBox.value.trim().toLowerCase(); cur = -1;
      if (!q) { findList.hidden = true; findList.innerHTML = ''; return; }
      var hits = robots.filter(function (r) { return r.n.toLowerCase().indexOf(q) >= 0; })
        .sort(function (a, b) { return a.n.toLowerCase().indexOf(q) - b.n.toLowerCase().indexOf(q) || a.n.length - b.n.length; }).slice(0, 8);
      findList.innerHTML = hits.map(function (r) { return '<li><button type="button" data-i="' + r.i + '">' + esc(r.n) + ' <span>' + r.y + '</span></button></li>'; }).join('') ||
        '<li class="none">Not on the chart. It may have no known year.</li>';
      findList.hidden = false;
    }
    findBox.addEventListener('input', render);
    findBox.addEventListener('keydown', function (e) {
      var b = findList.querySelectorAll('button');
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault(); if (!b.length) return;
        cur = (cur + (e.key === 'ArrowDown' ? 1 : -1) + b.length) % b.length;
        b.forEach(function (x, i) { x.classList.toggle('on', i === cur); });
      }
      if (e.key === 'Enter' && b.length) { e.preventDefault(); (b[cur] || b[0]).click(); }
      if (e.key === 'Escape') findList.hidden = true;
    });
    findList.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      var r = byId[b.getAttribute('data-i')];
      findList.hidden = true; findBox.value = r.n; goTo(r);
    });
    document.addEventListener('click', function (e) { if (!root.querySelector('.evo-find').contains(e.target)) findList.hidden = true; });
  }

  function edges() {
    var max = stage.scrollWidth - stage.clientWidth;
    root.classList.toggle('more-left', stage.scrollLeft > 4);
    root.classList.toggle('more-right', stage.scrollLeft < max - 4);
  }

  function goTo(r) {
    stage.scrollTo({ left: Math.max(0, r.cx - stage.clientWidth / 2), behavior: 'smooth' });
    var top = stage.getBoundingClientRect().top + window.scrollY - 90;
    if (Math.abs(window.scrollY - top) > 160) window.scrollTo({ top: top, behavior: 'smooth' });
    setTimeout(function () {
      pinned = r; current = null; hover(r);
      var ring = el('circle', { cx: r.cx, cy: r.cy, r: 7, 'class': 'pulse' }, gHover);
      setTimeout(function () { if (ring.parentNode) ring.parentNode.removeChild(ring); }, 2600);
    }, 650);
  }
})();
