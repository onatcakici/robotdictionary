(function () {
  var root = document.getElementById('robodle');
  if (!root) return;
  var MAX = +root.getAttribute('data-max') || 8;
  var SEC = JSON.parse(root.getAttribute('data-sections'));
  var REG = JSON.parse(root.getAttribute('data-regions'));
  var STATUS = ['', 'In service', 'Experimental', 'Retired'];
  var STORE = 'robodle.v1';
  var q = function (s) { return root.querySelector(s); };
  var el = { sil: q('[data-sil]'), reveal: q('[data-reveal]'), input: q('[data-guess] input'), hits: q('[data-guess] .hits'),
    rows: q('[data-rows]'), left: q('[data-left]'), hint: q('[data-hint]'), done: q('[data-done]'), no: q('[data-no]'), date: q('[data-date]'),
    guess: q('[data-guess]'), shadow: q('.shadow') };
  var R = {}, list = [], game = null, data = null, store = load();

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function norm(s) { return (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, ' ').trim(); }
  function deobf(s, key) { var b = atob(s), o = ''; for (var i = 0; i < b.length; i++) o += String.fromCharCode(b.charCodeAt(i) ^ key.charCodeAt(i % key.length)); return o; }
  function iso(d) { return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2); }
  function fresh() { return { played: 0, won: 0, streak: 0, best: 0, lastWon: 0, dist: [0, 0, 0, 0, 0, 0, 0, 0], days: {} }; }
  function load() { try { var s = JSON.parse(localStorage.getItem(STORE)); return s && s.days ? s : fresh(); } catch (e) { return fresh(); } }
  function save() { try { localStorage.setItem(STORE, JSON.stringify(store)); } catch (e) {} }

  Promise.all([fetch('/assets/robots.json').then(function (r) { return r.json(); }), fetch('/assets/robodle.json').then(function (r) { return r.json(); })])
    .then(function (res) {
      res[0].forEach(function (r) {
        var o = { i: r[0], n: r[1], aka: r[2], s: r[3], c: r[4], g: r[5], m: r[6], y: r[7], st: r[8], p: r[9], d: r[10] };
        o.key = norm(o.n + ' ' + o.aka); o.nn = norm(o.n); R[o.i] = o; list.push(o);
      });
      data = res[1];
      var today = iso(new Date()), day = null;
      data.days.forEach(function (d) { if (d[1] <= today) day = d; });
      if (!day) day = data.days[0];
      begin({ mode: 'daily', n: day[0], date: day[1], id: deobf(day[2], 'robodle:' + day[1]), sil: day[3] });
      wireInput();
    }).catch(function () { el.left.textContent = 'The game could not load. Please reload the page.'; });

  function begin(g) {
    game = g; game.guesses = []; game.over = false; game.won = false;
    game.answer = R[g.id];
    el.rows.querySelectorAll('.row:not(.head)').forEach(function (r) { r.remove(); });
    el.done.hidden = true; el.done.innerHTML = ''; el.hint.hidden = true;
    el.reveal.hidden = true; el.reveal.classList.remove('shown'); el.reveal.removeAttribute('src');
    el.shadow.classList.remove('solved');
    el.sil.src = '/img/s/' + g.sil + '.webp';
    el.guess.hidden = false; el.input.value = ''; el.input.disabled = false;
    if (g.mode === 'daily') {
      el.no.textContent = 'No. ' + g.n;
      var d = new Date(g.date + 'T12:00:00');
      el.date.textContent = d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
      var past = store.days[g.n];
      if (past && past.g) past.g.forEach(function (id) { if (R[id] && !game.over) addGuess(R[id], true); });
      if (game.over) return;
      var how = document.querySelector('.how');
      if (how && !store.played && !(past && past.g && past.g.length)) how.open = true;
    } else {
      el.no.textContent = 'Practice round';
      el.date.textContent = '';
    }
    status();
  }

  function status() {
    var left = MAX - game.guesses.length;
    el.left.innerHTML = game.over ? '' : '<span class="pips">' + new Array(MAX + 1).join('.').split('').map(function (_, k) {
      return '<i class="' + (k < game.guesses.length ? 'used' : '') + '"></i>'; }).join('') + '</span>' +
      (left === 1 ? 'Last guess' : left + ' guesses left');
    var misses = game.guesses.length;
    if (!game.over && misses >= 5) { el.hint.hidden = false; el.hint.innerHTML = 'Hint: the name begins with <b>' + esc(game.answer.n.charAt(0)) + '</b>.'; }
  }

  function makerWords(m) {
    return norm(m).split(' ').filter(function (w) { return w.length > 2 && ['the', 'and', 'for', 'inc', 'ltd', 'university', 'institute', 'national', 'laboratory', 'company',
      'corporation', 'technology', 'technologies', 'robotics', 'research', 'center', 'centre', 'group', 'systems', 'space', 'agency', 'nasa', 'jet', 'propulsion'].indexOf(w) < 0; });
  }
  function compare(gu, an) {
    var t = [];
    t.push({ v: SEC[gu.s][1], k: gu.s === an.s ? 'hit' : 'miss' });
    t.push({ v: gu.c || 'Unknown', k: !gu.c ? 'miss' : gu.c === an.c ? 'hit' : (gu.g && gu.g === an.g ? 'near' : 'miss'), x: gu.c && gu.c !== an.c && gu.g && gu.g === an.g ? REG[gu.g] : '' });
    var mk = 'miss';
    if (gu.m && an.m) {
      if (norm(gu.m) === norm(an.m)) mk = 'hit';
      else { var a = makerWords(gu.m), b = makerWords(an.m); if (a.some(function (w) { return b.indexOf(w) >= 0; })) mk = 'near'; }
    }
    t.push({ v: gu.m || 'Unknown', k: mk });
    var yk = 'miss', arrow = '';
    if (gu.y && an.y) {
      if (gu.y === an.y) yk = 'hit';
      else { yk = Math.abs(gu.y - an.y) <= 5 ? 'near' : 'miss'; arrow = an.y > gu.y ? 'up' : 'down'; }
    }
    t.push({ v: gu.y || 'Unknown', k: yk, a: arrow });
    t.push({ v: STATUS[gu.st] || 'Unknown', k: gu.st && gu.st === an.st ? 'hit' : 'miss' });
    return t;
  }

  function addGuess(gu, quiet) {
    var t = compare(gu, game.answer);
    game.guesses.push({ id: gu.i, t: t });
    var row = document.createElement('div');
    row.className = 'row' + (quiet ? '' : ' new');
    var labels = ['Section', 'Country', 'Maker', 'Year', 'Status'];
    row.innerHTML = '<span class="nm">' + esc(gu.n) + '</span>' + t.map(function (x, k) {
      var arrow = x.a === 'up' ? '<i class="ar" aria-label="answer is later">↑</i>' : x.a === 'down' ? '<i class="ar" aria-label="answer is earlier">↓</i>' : '';
      return '<span class="t ' + x.k + '" style="--d:' + (k * 110) + 'ms" title="' + labels[k] + ': ' + esc(x.v) + (x.x ? ', same part of the world' : '') + '"><span>' + esc(x.v) + arrow + '</span></span>';
    }).join('');
    el.rows.insertBefore(row, el.rows.children[1] || null);
    if (gu.i === game.answer.i) return finish(true, quiet);
    if (game.guesses.length >= MAX) return finish(false, quiet);
    if (!quiet) persist();
    status();
  }

  function persist() {
    if (game.mode !== 'daily') return;
    store.days[game.n] = { g: game.guesses.map(function (x) { return x.id; }), over: game.over, won: game.won };
    save();
  }

  function finish(won, quiet) {
    game.over = true; game.won = won;
    el.guess.hidden = true; el.hint.hidden = true; el.hits.hidden = true; el.left.innerHTML = '';
    if (game.mode === 'daily' && !quiet && !(store.days[game.n] && store.days[game.n].over)) {
      store.played++;
      if (won) {
        store.won++; store.dist[game.guesses.length - 1]++;
        store.streak = store.lastWon === game.n - 1 ? store.streak + 1 : 1;
        store.lastWon = game.n; store.best = Math.max(store.best, store.streak);
      } else store.streak = 0;
      persist();
    }
    var an = game.answer;
    el.reveal.onload = function () { el.reveal.hidden = false; requestAnimationFrame(function () { el.reveal.classList.add('shown'); el.shadow.classList.add('solved'); }); };
    el.reveal.alt = an.n;
    el.reveal.src = '/img/' + an.i + '.c.webp';
    var origin = [an.m, an.c, an.y].filter(Boolean).join(', ');
    var html = '<p class="verdict">' + (won ? (game.guesses.length === 1 ? 'First guess. Remarkable.' : 'Got it in ' + game.guesses.length + '.') : 'Not this time. It was') + '</p>' +
      '<h2><a href="/' + an.i + '/">' + esc(an.n) + '</a></h2>' +
      '<p class="origin">' + esc(origin) + (origin ? '.' : '') + '</p>' +
      (an.d ? '<p class="def">' + esc(an.d) + '</p>' : '') +
      '<p class="actions"><button type="button" class="btn" data-share>Share your result</button> <a class="u" href="/' + an.i + '/">Read the entry</a></p>' +
      '<p class="copied" data-copied hidden>Copied. Paste it anywhere.</p>';
    if (game.mode === 'daily') {
      html += stats() + '<p class="next">Next robot in <b data-count></b>. <button type="button" class="linkish" data-practice>Play a practice round</button></p>';
    } else {
      html += '<p class="next"><button type="button" class="btn ghost" data-practice>Another practice round</button> <button type="button" class="linkish" data-today>Back to today\'s robot</button></p>';
    }
    el.done.innerHTML = html; el.done.hidden = false;
    var sh = el.done.querySelector('[data-share]');
    sh.addEventListener('click', share);
    var pr = el.done.querySelector('[data-practice]'); if (pr) pr.addEventListener('click', practice);
    var td = el.done.querySelector('[data-today]'); if (td) td.addEventListener('click', function () { location.reload(); });
    tick();
    if (!quiet) el.done.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function stats() {
    var pct = store.played ? Math.round(100 * store.won / store.played) : 0;
    var top = Math.max.apply(null, store.dist.concat([1]));
    var mine = game.won ? game.guesses.length - 1 : -1;
    return '<div class="stats"><dl><div><dt>' + store.played + '</dt><dd>Played</dd></div><div><dt>' + pct + '</dt><dd>Won, %</dd></div>' +
      '<div><dt>' + store.streak + '</dt><dd>Streak</dd></div><div><dt>' + store.best + '</dt><dd>Best streak</dd></div></dl>' +
      '<ol class="dist">' + store.dist.map(function (c, k) {
        return '<li' + (k === mine ? ' class="me"' : '') + '><span>' + (k + 1) + '</span><b style="width:' + Math.max(6, Math.round(100 * c / top)) + '%">' + c + '</b></li>';
      }).join('') + '</ol></div>';
  }

  function grid() {
    return game.guesses.map(function (g) {
      return g.t.map(function (x) { return x.k === 'hit' ? '🟩' : x.k === 'near' ? '🟨' : '⬛'; }).join('');
    }).join('\n');
  }
  function share() {
    var head = (game.mode === 'daily' ? 'Robodle No. ' + game.n : 'Robodle practice') + '  ' + (game.won ? game.guesses.length : 'X') + '/' + MAX;
    var text = head + '\n' + grid() + '\nrobotdictionary.com/play/';
    var done = function () { var c = el.done.querySelector('[data-copied]'); if (c) { c.hidden = false; setTimeout(function () { c.hidden = true; }, 2600); } };
    if (navigator.share && /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)) {
      navigator.share({ text: text }).catch(function () {});
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text); done(); });
    } else { fallbackCopy(text); done(); }
  }
  function fallbackCopy(text) {
    var ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); } catch (e) {} ta.remove();
  }

  var timer = null;
  function tick() {
    clearTimeout(timer);
    var c = el.done.querySelector('[data-count]');
    if (!c) return;
    var now = new Date(), mid = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1), s = Math.max(0, Math.floor((mid - now) / 1000));
    var hh = Math.floor(s / 3600), mm = Math.floor(s % 3600 / 60), ss = s % 60;
    c.textContent = hh + ':' + ('0' + mm).slice(-2) + ':' + ('0' + ss).slice(-2);
    timer = setTimeout(tick, 1000);
  }

  function practice() {
    var p = data.practice[Math.floor(Math.random() * data.practice.length)];
    var id = deobf(p[0], 'practice');
    if (!R[id]) return;
    begin({ mode: 'practice', id: id, sil: p[1] });
    window.scrollTo({ top: root.offsetTop - 10, behavior: 'smooth' });
    el.input.focus();
  }

  // ---- the guess box
  function wireInput() {
    var cur = -1, items = [];
    function rank(v) {
      var qn = norm(v); if (!qn) return [];
      var used = {}; game.guesses.forEach(function (g) { used[g.id] = 1; });
      var parts = qn.split(' '), out = [];
      for (var i = 0; i < list.length; i++) {
        var r = list[i]; if (used[r.i]) continue;
        var ok = true; for (var j = 0; j < parts.length; j++) if (r.key.indexOf(parts[j]) < 0) { ok = false; break; }
        if (!ok) continue;
        var s = r.nn === qn ? 0 : r.nn.indexOf(qn) === 0 ? 1 : (' ' + r.nn).indexOf(' ' + qn) >= 0 ? 2 : 3;
        out.push([s, r.n.length, r]);
      }
      out.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
      return out.slice(0, 8).map(function (x) { return x[2]; });
    }
    function show() {
      items = rank(el.input.value); cur = items.length ? 0 : -1;
      if (!el.input.value.trim()) { el.hits.hidden = true; return; }
      el.hits.innerHTML = items.length ? items.map(function (r, k) {
        return '<li><button type="button" data-k="' + k + '" class="' + (k === cur ? 'on' : '') + '">' + esc(r.n) + '<span>' + esc([r.m, r.y || ''].filter(Boolean).join(', ')) + '</span></button></li>';
      }).join('') : '<li class="none">No robot by that name in the dictionary</li>';
      el.hits.hidden = false;
    }
    function pick(k) {
      var r = items[k]; if (!r || game.over) return;
      el.input.value = ''; el.hits.hidden = true; items = [];
      addGuess(r, false);
      if (!game.over) el.input.focus();
    }
    el.input.addEventListener('input', show);
    el.input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault(); if (!items.length) return;
        cur = (cur + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
        el.hits.querySelectorAll('button').forEach(function (b, i) { b.classList.toggle('on', i === cur); });
      } else if (e.key === 'Enter') { e.preventDefault(); if (items.length) pick(cur < 0 ? 0 : cur); }
      else if (e.key === 'Escape') { el.hits.hidden = true; }
    });
    el.hits.addEventListener('mousedown', function (e) { e.preventDefault(); });
    el.hits.addEventListener('click', function (e) { var b = e.target.closest('button'); if (b) pick(+b.getAttribute('data-k')); });
    document.addEventListener('click', function (e) { if (!el.guess.contains(e.target)) el.hits.hidden = true; });
  }
})();
