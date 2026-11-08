(function () {
  var root = document.getElementById('world');
  if (!root) return;
  var cv = root.querySelector('.wcv'), ctx = cv.getContext('2d');
  var mini = root.querySelector('.wmini'), mctx = mini.getContext('2d');
  var SEC = JSON.parse(root.getAttribute('data-sections'));
  var HW = 32, HH = 16;
  var css = getComputedStyle(document.documentElement);
  function v(n) { return css.getPropertyValue(n).trim(); }
  var DARK = window.matchMedia('(prefers-color-scheme: dark)').matches;
  var C = { paper: v('--paper'), ink: v('--ink'), soft: v('--soft'), mark: v('--mark'), sheet: v('--sheet'), rule: v('--rule') };
  var SC = SEC.map(function (s) { return v('--' + s[0]); });
  var KIND = ['humanoid', 'quad', 'wheel', 'arm', 'rover', 'med', 'marine', 'other'];

  // ---------- colour and number helpers
  var RGB = {};
  function rgb(c) {
    if (RGB[c]) return RGB[c];
    var k = c;
    if (c.charAt(0) === 'r') { var m = c.match(/[\d.]+/g); return (RGB[k] = [+m[0], +m[1], +m[2]]); }
    c = c.replace('#', '').trim();
    if (c.length === 3) c = c.split('').map(function (x) { return x + x; }).join('');
    return (RGB[k] = [parseInt(c.slice(0, 2), 16), parseInt(c.slice(2, 4), 16), parseInt(c.slice(4, 6), 16)]);
  }
  function mix(a, b, t) { var A = rgb(a), B = rgb(b); return 'rgb(' + [0, 1, 2].map(function (i) { return Math.round(A[i] + (B[i] - A[i]) * t); }).join(',') + ')'; }
  function hash(s) { var h = 2166136261; for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
  function rng(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; var t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function iso(x, y) { return [(x - y) * HW, (x + y) * HH]; }

  var GROUND = {
    plaza: mix(C.paper, C.ink, DARK ? 0.10 : 0.07), humanoids: mix(C.paper, SC[0], 0.10), quadrupeds: mix(C.paper, '#6f8f3a', DARK ? 0.35 : 0.30),
    wheeled: mix(C.paper, SC[2], 0.12), arms: mix(C.paper, '#8a8478', DARK ? 0.30 : 0.24), rovers: mix(C.paper, SC[4], DARK ? 0.55 : 0.45),
    medical: mix(C.paper, DARK ? '#3a4448' : '#ffffff', 0.55), marine: mix(C.paper, SC[6], DARK ? 0.6 : 0.42), other: mix(C.paper, SC[7], 0.14)
  };
  var ROAD = mix(C.paper, C.ink, DARK ? 0.18 : 0.16), INK = C.ink, SHADOW = DARK ? 'rgba(0,0,0,.35)' : 'rgba(50,38,22,.16)';
  var GREEN = mix('#6f8f3a', C.paper, DARK ? 0.1 : 0.05), GREEN2 = mix('#4f6d2a', C.paper, DARK ? 0.05 : 0);

  // ---------- state
  var robots = [], byId = {}, props = [], flat = [], stand = [], districts = [], roads = [], WORLD = null;
  var W = 0, H = 0, dpr = 1, cam = { x: 0, y: 0, z: 0.7 }, fly = null, follow = true;
  var me = { x: 0, y: 0, tx: null, ty: null, path: null, moving: false, face: 1, step: 0 };
  var hover = null, selected = null, bubbles = [], keys = {}, boxes = [], lastWhere = null, imgs = {}, now = 0, last = 0;
  var met = {}, metN = 0, STILL = /[?&]still\b/.test(location.search);
  try { (JSON.parse(localStorage.getItem('rw-met') || '[]') || []).forEach(function (i) { met[i] = 1; }); } catch (e) {}
  var greeted = {}, solids = [], movers = [], WALK = { p: [], n: [] }, STEP = 0, nextChat = 0, plazaD = null;

  Promise.all([fetch('/assets/robots.json').then(function (r) { return r.json(); }), fetch('/assets/world.json').then(function (r) { return r.json(); })])
    .then(function (res) { init(res[0], res[1]); })
    .catch(function () { root.querySelector('.w-intro p').textContent = 'The world could not load. Please reload the page.'; });

  function init(rows, w) {
    WORLD = w;
    var info = {}; rows.forEach(function (r) { info[r[0]] = r; });
    w.robots.forEach(function (q) {
      var r = info[q[0]]; if (!r) return;
      var o = { i: r[0], n: r[1], s: r[3], c: r[4], m: r[6], yr: r[7], st: r[8], p: r[9], d: r[10], x: q[1], y: q[2], robot: true };
      o.seed = hash(o.i); o.ph = (o.seed % 6283) / 1000; o.kind = KIND[o.s] || 'other';
      o.hx = o.x; o.hy = o.y; o.face = o.seed % 2 ? 1 : -1; o.wait = 0;
      if (q[3] === 1) { o.stroll = true; o.sp = 0.95 + (o.seed % 100) / 220; }
      else if (o.i !== w.rod && (o.seed >>> 8) % 100 < 24 && FIDGET[o.kind]) { o.fid = true; o.rad = FIDGET[o.kind]; o.wait = (o.seed >>> 4) % 9000; }
      robots.push(o); byId[o.i] = o;
    });
    w.props.forEach(function (p) {
      var o = { t: p[0], x: p[1], y: p[2], a: p[3], b: p[4], c: p[5], e: p[6] };
      if (o.t === 'street' || o.t === 'pond' || o.t === 'crater' || o.t === 'conveyor' || o.t === 'dock') { flat.push(o); return; }
      var r0 = { dome: 2.5, wheel: 1.3, fountain: 1.5, pedestal: 0.6, tent: 0.7 }[o.t];
      if (['tower', 'factory', 'house', 'clinic', 'monument', 'museum', 'booth', 'kiosk'].indexOf(o.t) >= 0) { o.depth = o.x + o.a / 2 + o.y + o.b / 2; solids.push([o.x, o.y, o.x + o.a, o.y + o.b, o.depth]); }
      else if (r0) { o.depth = o.x + o.y; solids.push([o.x - r0, o.y - r0, o.x + r0, o.y + r0, o.depth]); }
      else o.point = true;
      stand.push(o);
    });
    districts = w.districts; roads = w.roads; WALK = w.walk || WALK;
    plazaD = districts.filter(function (d) { return d.k === 'plaza'; })[0];
    stand.forEach(function (o) { if (o.point) o.depth = fixDepth(o.x, o.y, solids); });
    robots.forEach(function (o) {
      o.near = o.stroll && plazaD ? solids.filter(function (b) { return b[2] > plazaD.x - 3 && b[0] < plazaD.x + plazaD.w + 3 && b[3] > plazaD.y - 3 && b[1] < plazaD.y + plazaD.h + 3; })
        : solids.filter(function (b) { return o.x > b[0] - 4 && o.x < b[2] + 4 && o.y > b[1] - 4 && o.y < b[3] + 4; });
      o.depth = fixDepth(o.x, o.y, o.near);
      if (o.stroll) { o.node = nearestNode(o.x, o.y); o.wait = 600 + (o.seed % 2500); }
      if (o.stroll || o.fid) movers.push(o);
    });
    stand = stand.concat(robots).sort(function (a, b) { return a.depth - b.depth; });
    me.x = w.start[0]; me.y = w.start[1];
    resize(); wire();
    var p = iso(me.x, me.y); cam.x = p[0]; cam.y = p[1] - 60; cam.z = W < 640 ? 0.42 : 0.5;
    root.classList.add('ready'); showMet(false);
    var h = decodeURIComponent(location.hash.slice(1));
    if (h && byId[h]) setTimeout(function () { goTo(byId[h], true); }, 250);
    else if (!STILL) setTimeout(function () { say({ x: me.x, y: me.y, me: true }, 'Welcome to Robot World. Click the ground to walk.', 4200); }, 600);
    requestAnimationFrame(frame);
  }

  function resize() {
    var top = root.getBoundingClientRect().top + window.scrollY;
    root.style.height = Math.max(460, window.innerHeight - top) + 'px';
    dpr = Math.min(2, window.devicePixelRatio || 1);
    W = root.clientWidth; H = root.clientHeight;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    cv.style.width = W + 'px'; cv.style.height = H + 'px';

  }

  // ---------- depth and movement
  var FIDGET = { humanoid: 0.45, quad: 0.8, wheel: 0.7, arm: 0, rover: 0.6, med: 0.35, marine: 0.7, other: 0.55 };
  // an object in front of a building (past its far x or y edge) is drawn after it, one behind is drawn before it
  function fixDepth(x, y, list) {
    var d = x + y;
    for (var i = 0; i < list.length; i++) {
      var b = list[i];
      if (x < b[0] - 3 || x > b[2] + 3 || y < b[1] - 3 || y > b[3] + 3) continue;
      if (x >= b[2] || y >= b[3]) { if (d <= b[4]) d = b[4] + 0.01; }
      else if (d >= b[4]) d = b[4] - 0.01;
    }
    return d;
  }
  function resort() {
    for (var i = 1; i < stand.length; i++) {
      var o = stand[i], d = o.depth, j = i - 1;
      if (stand[j].depth <= d) continue;
      while (j >= 0 && stand[j].depth > d) { stand[j + 1] = stand[j]; j--; }
      stand[j + 1] = o;
    }
  }
  function nearestNode(x, y) {
    var best = -1, bd = 1e9;
    for (var i = 0; i < WALK.p.length; i++) { var d = Math.hypot(WALK.p[i][0] - x, WALK.p[i][1] - y); if (d < bd) { bd = d; best = i; } }
    return best;
  }
  function route(a, b) {
    var n = WALK.p.length, prev = new Int32Array(n), seen = new Uint8Array(n), q = [a]; seen[a] = 1;
    for (var h = 0; h < q.length; h++) {
      var u = q[h]; if (u === b) break;
      var nb = WALK.n[u];
      for (var k = 0; k < nb.length; k++) { var v2 = nb[k]; if (!seen[v2]) { seen[v2] = 1; prev[v2] = u; q.push(v2); } }
    }
    if (!seen[b]) return null;
    var out = []; for (var x = b; x !== a; x = prev[x]) out.push(x);
    return out.reverse();
  }
  function updateMovers(dt) {
    var changed = false;
    for (var i = 0; i < movers.length; i++) {
      var o = movers[i];
      if (o === selected || o === hover || (o.stroll && Math.hypot(o.x - me.x, o.y - me.y) < 1.3)) { o.mv = false; continue; }
      var tx, ty;
      if (o.stroll) {
        if (!o.path || !o.path.length) {
          if (now < o.wait || o.node < 0) { o.mv = false; continue; }
          var dest = -1;
          for (var tries = 0; tries < 12 && dest < 0; tries++) {
            var c = Math.floor(Math.random() * WALK.p.length), P = WALK.p[c], far = Math.hypot(P[0] - o.x, P[1] - o.y);
            if (far < 3 || far > 13) continue;
            if (movers.some(function (m) { return m !== o && m.stroll && Math.hypot(m.x - P[0], m.y - P[1]) < 1.6; })) continue;
            dest = c;
          }
          o.path = dest >= 0 ? route(o.node, dest) : null;
          if (!o.path || !o.path.length) { o.wait = now + 800; o.mv = false; continue; }
        }
        tx = WALK.p[o.path[0]][0]; ty = WALK.p[o.path[0]][1];
      } else {
        if (o.tx == null) {
          if (now < o.wait) { o.mv = false; continue; }
          var ang = Math.random() * 6.283, rad = Math.random() < 0.35 ? 0 : o.rad * (0.4 + Math.random() * 0.6);
          o.tx = o.hx + Math.cos(ang) * rad; o.ty = o.hy + Math.sin(ang) * rad;
        }
        tx = o.tx; ty = o.ty;
      }
      var dx = tx - o.x, dy = ty - o.y, dist = Math.hypot(dx, dy), sp = (o.stroll ? o.sp : 0.6) * dt;
      if (dist <= sp) {
        o.x = tx; o.y = ty;
        if (o.stroll) { o.node = o.path.shift(); if (!o.path.length) { o.mv = false; o.wait = now + 1500 + Math.random() * 5000; } }
        else { o.tx = null; o.mv = false; o.wait = now + 2500 + Math.random() * 9000; }
      } else {
        o.x += dx / dist * sp; o.y += dy / dist * sp; o.mv = true;
        if (Math.abs(dx - dy) > 0.02) o.face = (dx - dy) >= 0 ? 1 : -1;
      }
      o.depth = fixDepth(o.x, o.y, o.near); changed = true;
    }
    if (changed) resort();
  }

  // ---------- drawing primitives (world pixels)
  var LW = 1;
  function path(pts) { ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]); for (var i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]); ctx.closePath(); }
  function fs(fill, stroke) { if (fill) { ctx.fillStyle = fill; ctx.fill(); } if (stroke !== false) { ctx.strokeStyle = stroke || INK; ctx.lineWidth = LW; ctx.stroke(); } }
  function rr(x, y, w, h, r) { r = Math.min(r, w / 2, h / 2); ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
  function circ(x, y, r) { ctx.beginPath(); ctx.arc(x, y, r, 0, 6.2832); }
  function ell(x, y, rx, ry) { ctx.beginPath(); ctx.ellipse(x, y, rx, ry, 0, 0, 6.2832); }
  function quad(x, y, w, h) { return [iso(x, y), iso(x + w, y), iso(x + w, y + h), iso(x, y + h)]; }
  function shadow(x, y, rx) { ell(x, y, rx, rx * 0.36); ctx.fillStyle = SHADOW; ctx.fill(); }

  // an iso box: footprint w by d tiles at (x, y), h pixels tall
  function box(x, y, w, d, h, top, left, right, deco) {
    var A = iso(x, y), B = iso(x + w, y), Cc = iso(x + w, y + d), D = iso(x, y + d);
    path([D, Cc, [Cc[0], Cc[1] - h], [D[0], D[1] - h]]); fs(left);
    path([Cc, B, [B[0], B[1] - h], [Cc[0], Cc[1] - h]]); fs(right);
    path([[A[0], A[1] - h], [B[0], B[1] - h], [Cc[0], Cc[1] - h], [D[0], D[1] - h]]); fs(top);
    if (deco) deco(A, B, Cc, D, h);
  }
  function windows(P, Q, h, rows, cols, col) {
    // windows on the face from P to Q (bottom edge), h tall
    ctx.fillStyle = col; ctx.beginPath();
    for (var r = 0; r < rows; r++) for (var c = 0; c < cols; c++) {
      var t0 = (c + 0.25) / cols, t1 = (c + 0.75) / cols, yb = h * (r + 0.3) / rows, yt = h * (r + 0.75) / rows;
      var p0 = [P[0] + (Q[0] - P[0]) * t0, P[1] + (Q[1] - P[1]) * t0], p1 = [P[0] + (Q[0] - P[0]) * t1, P[1] + (Q[1] - P[1]) * t1];
      ctx.moveTo(p0[0], p0[1] - yb); ctx.lineTo(p1[0], p1[1] - yb); ctx.lineTo(p1[0], p1[1] - yt); ctx.lineTo(p0[0], p0[1] - yt); ctx.closePath();
    }
    ctx.fill();
  }

  // ---------- the ground
  function drawGround(vb) {
    ctx.fillStyle = mix(C.paper, C.ink, 0.03);
    path(quad(1, 1, WORLD.W - 2, WORLD.H - 2)); fs(mix(C.paper, C.ink, 0.035), false);
    roads.forEach(function (r) { path(quad(r[0], r[1], r[2], r[3])); fs(ROAD, false); });
    // dashed centre lines
    ctx.setLineDash([10, 12]); ctx.strokeStyle = C.paper; ctx.lineWidth = 2;
    roads.forEach(function (r) {
      ctx.beginPath();
      if (r[2] > r[3]) { var a = iso(r[0], r[1] + r[3] / 2), b = iso(r[0] + r[2], r[1] + r[3] / 2); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); }
      else { var c = iso(r[0] + r[2] / 2, r[1]), d = iso(r[0] + r[2] / 2, r[1] + r[3]); ctx.moveTo(c[0], c[1]); ctx.lineTo(d[0], d[1]); }
      ctx.stroke();
    });
    ctx.setLineDash([]);
    districts.forEach(function (d) {
      path(quad(d.x, d.y, d.w, d.h)); fs(GROUND[d.k], INK);
      // a kerb on the two front edges
      var B = iso(d.x + d.w, d.y), Cc = iso(d.x + d.w, d.y + d.h), D = iso(d.x, d.y + d.h);
      ctx.beginPath(); ctx.moveTo(D[0], D[1]); ctx.lineTo(D[0], D[1] + 5); ctx.lineTo(Cc[0], Cc[1] + 5); ctx.lineTo(B[0], B[1] + 5); ctx.lineTo(B[0], B[1]); ctx.lineTo(Cc[0], Cc[1]); ctx.closePath();
      fs(mix(GROUND[d.k], C.ink, d.k === 'marine' ? 0.35 : 0.22), INK);
      if (cam.z > 0.32) texture(d, vb);
    });
  }
  function texture(d, vb) {
    var k = d.k, R = rng(hash('tex' + k)), n = Math.round(d.w * d.h / (k === 'marine' ? 5 : 7));
    if (k === 'plaza' || k === 'humanoids' || k === 'medical' || k === 'arms') {
      ctx.strokeStyle = mix(GROUND[k], C.ink, DARK ? 0.16 : 0.1); ctx.lineWidth = LW; ctx.beginPath();
      for (var gx = d.x + 2; gx < d.x + d.w; gx += 2) { var g0 = iso(gx, d.y), g1 = iso(gx, d.y + d.h); ctx.moveTo(g0[0], g0[1]); ctx.lineTo(g1[0], g1[1]); }
      for (var gy = d.y + 2; gy < d.y + d.h; gy += 2) { var h0 = iso(d.x, gy), h1 = iso(d.x + d.w, gy); ctx.moveTo(h0[0], h0[1]); ctx.lineTo(h1[0], h1[1]); }
      ctx.stroke();
      if (k !== 'arms') return;
    }
    var dots = { rovers: [mix(GROUND.rovers, C.ink, 0.25), 1, 1.6], other: [mix(GROUND.other, SC[7], 0.35), 1.6, 0], wheeled: [mix(GROUND.wheeled, C.ink, 0.1), 1.2, 0] }[k];
    ctx.lineWidth = LW; ctx.beginPath();
    for (var i = 0; i < n; i++) {
      var x = d.x + 0.5 + R() * (d.w - 1), y = d.y + 0.5 + R() * (d.h - 1), p = iso(x, y), r = R();
      if (p[0] < vb[0] - 40 || p[0] > vb[2] + 40 || p[1] < vb[1] - 40 || p[1] > vb[3] + 40) continue;
      if (k === 'marine') { var o = Math.sin(now / 900 + r * 6) * 4; ctx.moveTo(p[0] - 9 + o, p[1]); ctx.quadraticCurveTo(p[0] - 3 + o, p[1] - 4, p[0] + 3 + o, p[1]); }
      else if (k === 'quadrupeds') { ctx.moveTo(p[0] - 3, p[1]); ctx.lineTo(p[0] - 1, p[1] - 5); ctx.moveTo(p[0], p[1]); ctx.lineTo(p[0] + 1, p[1] - 6); ctx.moveTo(p[0] + 3, p[1]); ctx.lineTo(p[0] + 4, p[1] - 4); }
      else if (dots) { var rad = dots[1] + r * dots[2]; ctx.moveTo(p[0] + rad, p[1]); ctx.arc(p[0], p[1], rad, 0, 6.2832); }
    }
    if (k === 'marine') { ctx.strokeStyle = mix(GROUND.marine, C.paper, 0.55); ctx.stroke(); }
    else if (k === 'quadrupeds') { ctx.strokeStyle = GREEN2; ctx.stroke(); }
    else if (dots) { ctx.fillStyle = dots[0]; ctx.fill(); }
  }
  function drawFlat(o) {
    if (o.t === 'street') {
      path(quad(o.x, o.y, o.a, o.b)); fs(ROAD, false);
      ctx.setLineDash([8, 9]); ctx.strokeStyle = C.paper; ctx.lineWidth = 1.5; var a = iso(o.x, o.y + o.b / 2), b = iso(o.x + o.a, o.y + o.b / 2); ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); ctx.setLineDash([]);
    } else if (o.t === 'pond') {
      var c = iso(o.x + o.a / 2, o.y + o.b / 2); ell(c[0], c[1], o.a * HW * 0.9, o.b * HH * 1.6); fs(mix(C.paper, SC[6], 0.45), INK);
      ctx.strokeStyle = mix(C.paper, SC[6], 0.2); ctx.beginPath(); ctx.ellipse(c[0] - 10, c[1] - 3, 20, 5, 0, 3.6, 5.6); ctx.stroke();
    } else if (o.t === 'crater') {
      var p = iso(o.x, o.y), rx = o.a * HW * 1.1, ry = o.a * HH * 1.1;
      ell(p[0], p[1], rx, ry); fs(mix(GROUND.rovers, C.ink, 0.18), INK);
      ell(p[0] + rx * 0.08, p[1] + ry * 0.12, rx * 0.8, ry * 0.75); fs(mix(GROUND.rovers, C.ink, 0.06), false);
    } else if (o.t === 'conveyor') {
      path(quad(o.x, o.y, o.a, o.b)); fs(mix(C.paper, C.ink, 0.45), INK);
      ctx.strokeStyle = mix(C.paper, C.ink, 0.25); ctx.lineWidth = 2; var off = (now / 400) % 1;
      ctx.beginPath(); for (var i = off; i < o.a; i += 1) { var s0 = iso(o.x + i, o.y), s1 = iso(o.x + i, o.y + o.b); ctx.moveTo(s0[0], s0[1]); ctx.lineTo(s1[0], s1[1]); } ctx.stroke();
      // hazard stripes along the side
      var q0 = iso(o.x, o.y + o.b + 0.15), q1 = iso(o.x + o.a, o.y + o.b + 0.15);
      ctx.setLineDash([6, 6]); ctx.strokeStyle = '#d9a52b'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(q0[0], q0[1]); ctx.lineTo(q1[0], q1[1]); ctx.stroke(); ctx.setLineDash([]);
    } else if (o.t === 'dock') {
      path(quad(o.x, o.y, o.a, o.b)); fs(DARK ? '#6b5a44' : '#b89b72', INK);
      ctx.strokeStyle = DARK ? '#54473a' : '#9a7f5a'; ctx.lineWidth = 1;
      ctx.beginPath(); for (var j = 1; j < o.b * 2; j++) { var d0 = iso(o.x, o.y + j / 2), d1 = iso(o.x + o.a, o.y + j / 2); ctx.moveTo(d0[0], d0[1]); ctx.lineTo(d1[0], d1[1]); } ctx.stroke();
    }
  }

  // ---------- standing scenery
  function drawProp(o) {
    var p = iso(o.x, o.y), x = p[0], y = p[1], R;
    switch (o.t) {
      case 'tree':
        var tv = Math.min(3, Math.floor((o.a || 0) * 4)), tsc = Math.max(0.25, Math.pow(2, Math.round(Math.log(cam.z * dpr) / Math.LN2 * 2) / 2)), tc2 = treeSprite(tv, tsc);
        ctx.drawImage(tc2, x - 20, y - 46, 40, 52);
        break;
      case 'lamp':
        ctx.strokeStyle = INK; ctx.lineWidth = LW * 1.4; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y - 34); ctx.stroke();
        circ(x, y - 36, 4); fs(DARK ? '#f1d27a' : '#f6e3a8', INK); break;
      case 'tower':
        var tint = mix(SC[0], C.paper, 0.55 + (o.e || 0) * 0.25);
        box(o.x, o.y, o.a, o.b, o.c || 80, mix(tint, '#ffffff', 0.25), mix(tint, C.ink, 0.12), tint, function (A, B, Cc, D, h) {
          if (cam.z > 0.35) { windows(D, Cc, h, Math.round(h / 22), 3, mix(tint, C.ink, 0.45)); windows(Cc, B, h, Math.round(h / 22), 3, mix(tint, C.ink, 0.35)); }
        });
        break;
      case 'house':
        var ht = o.c || 40, hcol = mix(SC[2], C.paper, 0.5 + (o.e || 0) * 0.3);
        box(o.x, o.y, o.a, o.b, ht, mix(hcol, '#ffffff', 0.2), mix(hcol, C.ink, 0.15), hcol, function (A, B, Cc, D, h) {
          // pitched roof
          var m1 = [(A[0] + D[0]) / 2, (A[1] + D[1]) / 2 - h - 22], m2 = [(B[0] + Cc[0]) / 2, (B[1] + Cc[1]) / 2 - h - 22];
          path([[D[0], D[1] - h], [Cc[0], Cc[1] - h], m2, m1]); fs(mix(SC[4], C.paper, 0.25));
          path([[Cc[0], Cc[1] - h], [B[0], B[1] - h], m2]); fs(mix(SC[4], C.ink, 0.1));
          windows(D, Cc, h, 1, 2, mix(hcol, C.ink, 0.4));
        });
        break;
      case 'factory':
        var fc = mix('#8a8478', C.paper, 0.35);
        box(o.x, o.y, o.a, o.b, o.c || 46, mix(fc, '#ffffff', 0.2), mix(fc, C.ink, 0.15), fc, function (A, B, Cc, D, h) {
          // saw tooth roof along the length
          for (var i = 0; i < 4; i++) {
            var t0 = i / 4, t1 = (i + 1) / 4;
            var a0 = [A[0] + (D[0] - A[0]) * t0, A[1] + (D[1] - A[1]) * t0 - h], a1 = [A[0] + (D[0] - A[0]) * t1, A[1] + (D[1] - A[1]) * t1 - h];
            var b0 = [B[0] + (Cc[0] - B[0]) * t0, B[1] + (Cc[1] - B[1]) * t0 - h], b1 = [B[0] + (Cc[0] - B[0]) * t1, B[1] + (Cc[1] - B[1]) * t1 - h];
            path([a1, b1, [b0[0], b0[1] - 14], [a0[0], a0[1] - 14]]); fs(mix(fc, '#ffffff', 0.35));
            path([[b0[0], b0[1] - 14], b1, [b1[0], b1[1]]]); fs(mix(SC[3], C.paper, 0.35));
          }
          // chimney
          var ch = [A[0] + (B[0] - A[0]) * 0.75, A[1] + (B[1] - A[1]) * 0.75 - h];
          ctx.fillStyle = mix(fc, C.ink, 0.3); rr(ch[0] - 4, ch[1] - 30, 8, 30, 1); fs(mix(fc, C.ink, 0.25));
          windows(D, Cc, h, 2, 5, mix(SC[3], C.paper, 0.2));
        });
        break;
      case 'clinic':
        var cc = DARK ? '#d9dcd8' : '#ffffff';
        box(o.x, o.y, o.a, o.b, o.c || 54, cc, mix(cc, C.ink, 0.12), mix(cc, C.ink, 0.05), function (A, B, Cc, D, h) {
          windows(D, Cc, h, 2, 6, mix(SC[6], C.paper, 0.4)); windows(Cc, B, h, 2, 4, mix(SC[6], C.paper, 0.5));
          var m = [(A[0] + Cc[0]) / 2, (A[1] + Cc[1]) / 2 - h];
          ctx.fillStyle = SC[5]; ctx.fillRect(m[0] - 4, m[1] - 18, 8, 26); ctx.fillRect(m[0] - 13, m[1] - 9, 26, 8);
        });
        break;
      case 'dome':
        var dc = iso(o.x, o.y), rx = o.a * HW * 0.9;
        shadow(dc[0], dc[1], rx);
        ctx.beginPath(); ctx.ellipse(dc[0], dc[1], rx, rx * 0.5, 0, 0, 3.1416, false); ctx.ellipse(dc[0], dc[1], rx, rx * 0.95, 0, 3.1416, 6.2832, false); ctx.closePath();
        fs(DARK ? 'rgba(170,200,210,.35)' : 'rgba(210,232,236,.75)', INK);
        ctx.strokeStyle = mix(SC[6], C.paper, 0.3); ctx.lineWidth = LW; ctx.beginPath(); ctx.ellipse(dc[0], dc[1], rx * 0.55, rx * 0.95, 0, 3.1416, 6.2832); ctx.stroke();
        ctx.beginPath(); ctx.ellipse(dc[0] - rx * 0.4, dc[1] - rx * 0.55, rx * 0.18, rx * 0.08, -0.5, 0, 6.2832); ctx.fillStyle = 'rgba(255,255,255,.7)'; ctx.fill();
        break;
      case 'crate':
        R = rng(hash('crate' + o.x + o.y)); box(o.x - 0.3, o.y - 0.3, 0.6, 0.6, 14 + R() * 8, '#d4b483', '#b08f5c', '#c4a26f'); break;
      case 'rock':
        R = rng(hash('rock' + o.x + o.y)); var rs = 5 + R() * 7;
        path([[x - rs, y], [x - rs * 0.6, y - rs * 0.8], [x + rs * 0.2, y - rs], [x + rs, y - rs * 0.3], [x + rs * 0.8, y + 2]]); fs(mix(GROUND.rovers, C.ink, 0.3), INK); break;
      case 'buoy':
        var bb = Math.sin(now / 700 + (o.a || 0) * 6) * 2;
        ell(x, y + 2, 9, 3.5); ctx.fillStyle = mix(GROUND.marine, C.ink, 0.2); ctx.fill();
        rr(x - 4, y - 14 + bb, 8, 14, 3); fs((o.a || 0) > 0.5 ? C.mark : '#e8b03c', INK);
        ctx.fillStyle = '#fff'; ctx.fillRect(x - 4, y - 9 + bb, 8, 3); break;
      case 'balloon':
        R = rng(hash('bal' + o.x + o.y)); var cols = [C.mark, SC[2], '#e8b03c', SC[1], SC[7]], bob = Math.sin(now / 800 + R() * 6) * 2;
        ctx.strokeStyle = INK; ctx.lineWidth = LW; ctx.beginPath(); ctx.moveTo(x, y); ctx.quadraticCurveTo(x + 4, y - 14, x, y - 26 + bob); ctx.stroke();
        ell(x, y - 33 + bob, 6, 8); fs(cols[Math.floor(R() * cols.length)], INK); break;
      case 'tent':
        R = rng(hash('tent' + o.x + o.y)); var tc = [C.mark, SC[2], SC[7], SC[1]][Math.floor(R() * 4)];
        shadow(x, y, 26);
        path([[x - 26, y], [x, y - 44], [x + 26, y], [x, y + 9]]); fs(mix(tc, C.paper, 0.15), INK);
        path([[x, y - 44], [x + 26, y], [x, y + 9]]); fs(mix(tc, C.ink, 0.12), INK);
        ctx.strokeStyle = '#fff'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(x, y - 44); ctx.lineTo(x - 13, y + 4.5); ctx.moveTo(x, y - 44); ctx.lineTo(x + 13, y + 4.5); ctx.stroke();
        ctx.strokeStyle = INK; ctx.lineWidth = LW; ctx.beginPath(); ctx.moveTo(x, y - 44); ctx.lineTo(x, y - 54); ctx.stroke();
        path([[x, y - 54], [x + 9, y - 51], [x, y - 48]]); fs(C.mark, false); break;
      case 'wheel':
        var wc = iso(o.x, o.y), wr = o.a * 22, rot = now / 6000;
        ctx.strokeStyle = INK; ctx.lineWidth = LW * 2; ctx.beginPath(); ctx.moveTo(wc[0] - wr * 0.6, wc[1]); ctx.lineTo(wc[0], wc[1] - wr - 8); ctx.lineTo(wc[0] + wr * 0.6, wc[1]); ctx.stroke();
        circ(wc[0], wc[1] - wr - 8, wr); ctx.lineWidth = LW * 1.5; ctx.stroke();
        for (var k = 0; k < 10; k++) {
          var a = rot + k * 0.628, ex = wc[0] + Math.cos(a) * wr, ey = wc[1] - wr - 8 + Math.sin(a) * wr;
          ctx.lineWidth = LW * 0.8; ctx.beginPath(); ctx.moveTo(wc[0], wc[1] - wr - 8); ctx.lineTo(ex, ey); ctx.stroke();
          rr(ex - 5, ey, 10, 8, 2); fs([C.mark, SC[2], '#e8b03c', SC[1], SC[7]][k % 5], INK);
        }
        break;
      case 'monument':
        var mc = iso(o.x + o.a / 2, o.y + o.b / 2);
        box(o.x, o.y, o.a, o.b, 26, mix(C.paper, C.ink, 0.12), mix(C.paper, C.ink, 0.3), mix(C.paper, C.ink, 0.2));
        // an open book on the plinth
        var by = mc[1] - 26 - 6;
        ctx.save(); ctx.translate(mc[0], by);
        path([[-70, 0], [0, 18], [0, -46], [-70, -64]]); fs(DARK ? '#e8e2d4' : '#fffdf6', INK);
        path([[70, 0], [0, 18], [0, -46], [70, -64]]); fs(DARK ? '#d8d2c4' : '#f4efe3', INK);
        ctx.strokeStyle = mix(C.paper, C.ink, 0.4); ctx.lineWidth = LW;
        for (var l = 0; l < 6; l++) { ctx.beginPath(); ctx.moveTo(-60, -50 + l * 8); ctx.lineTo(-10, -32 + l * 8); ctx.moveTo(10, -32 + l * 8); ctx.lineTo(60, -50 + l * 8); ctx.stroke(); }
        ctx.fillStyle = C.mark; ctx.fillRect(-2, -52, 4, 64);
        ctx.restore();
        place(o, 'book', 110); o.label = 'The Dictionary';
        break;
      case 'museum':
        var mcol = DARK ? '#cfc8b8' : '#f4efe3';
        box(o.x, o.y, o.a, o.b, 8, mix(mcol, C.ink, 0.08), mix(mcol, C.ink, 0.25), mix(mcol, C.ink, 0.16));
        box(o.x + 0.5, o.y + 0.5, o.a - 1, o.b - 1, (o.c || 52) + 8, mix(mcol, '#ffffff', 0.35), mix(mcol, C.ink, 0.12), mix(mcol, C.ink, 0.05), function (A, B, Cc, D, h) {
          ctx.strokeStyle = mix(mcol, C.ink, 0.4); ctx.lineWidth = LW * 2.2;
          for (var i = 1; i < 8; i++) { var t = i / 8, px = D[0] + (Cc[0] - D[0]) * t, py = D[1] + (Cc[1] - D[1]) * t; ctx.beginPath(); ctx.moveTo(px, py - 10); ctx.lineTo(px, py - h + 14); ctx.stroke(); }
          var dt = [D[0], D[1] - h], ct = [Cc[0], Cc[1] - h], apex = [(dt[0] + ct[0]) / 2, (dt[1] + ct[1]) / 2 - 24];
          path([[dt[0], dt[1] + 10], [ct[0], ct[1] + 10], ct, dt]); fs(mix(mcol, C.ink, 0.1));
          path([dt, ct, apex]); fs(mix(mcol, '#ffffff', 0.3));
          circ(apex[0], apex[1] + 13, 4); fs(C.mark, false);
        });
        place(o, 'museum', 120); o.label = 'Museum'; break;
      case 'booth':
        box(o.x, o.y, o.a, o.b, o.c || 30, mix(C.paper, '#ffffff', 0.4), mix(SC[7], C.paper, 0.35), mix(SC[7], C.paper, 0.5), function (A, B, Cc, D, h) {
          // striped awning and a big question mark
          path([[D[0] - 4, D[1] - h + 2], [Cc[0] + 4, Cc[1] - h + 2], [Cc[0] + 4, Cc[1] - h + 12], [D[0] - 4, D[1] - h + 12]]); fs(C.mark);
          var mid = [(A[0] + Cc[0]) / 2, (A[1] + Cc[1]) / 2 - h];
          ctx.strokeStyle = INK; ctx.lineWidth = LW * 1.4; ctx.beginPath(); ctx.moveTo(mid[0], mid[1]); ctx.lineTo(mid[0], mid[1] - 18); ctx.stroke();
          circ(mid[0], mid[1] - 32, 15); fs(C.sheet, INK);
          ctx.fillStyle = C.mark; ctx.font = '700 22px "Young Serif", Georgia, serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('?', mid[0], mid[1] - 31);
        });
        place(o, 'play', 90); o.label = 'Robodle'; break;
      case 'kiosk':
        var kc = DARK ? '#cfc8b8' : '#f4efe3';
        box(o.x, o.y, o.a, o.b, o.c || 26, mix(kc, '#ffffff', 0.3), mix(kc, C.ink, 0.12), kc, function (A, B, Cc, D, h) {
          for (var i = 0; i < 3; i++) { var t0 = 0.18 + i * 0.27, px = D[0] + (Cc[0] - D[0]) * t0, py = D[1] + (Cc[1] - D[1]) * t0; path([[px, py - h * 0.25], [px + 9, py - h * 0.25 + 4.5], [px + 9, py - h * 0.72 + 4.5], [px, py - h * 0.72]]); fs(i === 1 ? mix(C.mark, C.paper, 0.2) : C.sheet, INK); }
          path([[A[0], A[1] - h - 6], [B[0] + 5, B[1] - h - 3], [Cc[0] + 5, Cc[1] - h + 3], [D[0], D[1] - h]]); fs(SC[2]);
        });
        place(o, 'news', 70); o.label = 'News'; break;
      case 'pedestal':
        box(o.x - 0.6, o.y - 0.6, 1.2, 1.2, 22, mix(C.paper, C.ink, 0.1), mix(C.paper, C.ink, 0.32), mix(C.paper, C.ink, 0.2));
        var star = byId[o.a];
        if (star) {
          sprite(star, now, x, y - 22, 1.5); o.label = 'Robot of the day';
        }
        break;
      case 'fountain':
        var fc2 = iso(o.x, o.y), fr = o.a * HW * 0.8;
        ell(fc2[0], fc2[1], fr, fr * 0.5); fs(mix(C.paper, C.ink, 0.2), INK);
        ell(fc2[0], fc2[1] - 4, fr * 0.86, fr * 0.43); fs(mix(C.paper, SC[6], 0.45), false);
        rr(fc2[0] - 4, fc2[1] - 30, 8, 26, 2); fs(mix(C.paper, C.ink, 0.18), INK);
        ctx.strokeStyle = mix(C.paper, SC[6], 0.25); ctx.lineWidth = LW * 1.4;
        for (var q = 0; q < 6; q++) { var ang = q / 6 * 6.283 + now / 1500, ex2 = fc2[0] + Math.cos(ang) * fr * 0.55, ey2 = fc2[1] - 4 + Math.sin(ang) * fr * 0.27; ctx.beginPath(); ctx.moveTo(fc2[0], fc2[1] - 30); ctx.quadraticCurveTo((fc2[0] + ex2) / 2, fc2[1] - 46, ex2, ey2); ctx.stroke(); }
        break;
      case 'bench':
        box(o.x - 0.5, o.y - 0.15, 1, 0.3, 7, DARK ? '#7a6650' : '#b89b72', DARK ? '#5d4d3c' : '#9a7f5a', DARK ? '#6b5a44' : '#a88b62'); break;
      case 'board':
        ctx.strokeStyle = INK; ctx.lineWidth = LW * 1.5; ctx.beginPath(); ctx.moveTo(x - 14, y); ctx.lineTo(x - 14, y - 34); ctx.moveTo(x + 14, y); ctx.lineTo(x + 14, y - 34); ctx.stroke();
        rr(x - 24, y - 50, 48, 18, 2); fs(C.sheet, INK);
        o.label = true; break;
    }
  }

  var trees = {};
  function treeSprite(v, scale) {
    var key = v + '@' + scale; if (trees[key]) return trees[key];
    var c3 = document.createElement('canvas'); c3.width = Math.ceil(40 * scale); c3.height = Math.ceil(52 * scale);
    var g = c3.getContext('2d'); g.setTransform(scale, 0, 0, scale, 20 * scale, 46 * scale);
    var keep = ctx; ctx = g; var s = 0.8 + (v + 0.5) / 4 * 0.5;
    shadow(0, 0, 12 * s);
    ctx.fillStyle = DARK ? '#6b5642' : '#8a6a48'; ctx.fillRect(-1.5 * s, -12 * s, 3 * s, 12 * s);
    circ(0, -20 * s, 11 * s); fs(GREEN, INK);
    circ(-4 * s, -23 * s, 5 * s); fs(mix(GREEN, '#ffffff', 0.18), false);
    ctx = keep; trees[key] = c3; return c3;
  }
  function place(o, kind, hgt) { var p = iso(o.x + (o.a || 0) / 2, o.y + (o.b || 0) / 2); boxes.push([p[0] - 60, p[1] - hgt - 40, p[0] + 60, p[1] + 10, { place: kind, x: o.x + (o.a || 0) / 2, y: o.y + (o.b || 0) / 2 }]); }

  // ---------- robots
  function drawRobot(o, t) { var p = iso(o.x, o.y); sprite(o, t, p[0], p[1], 1); }
  function sprite(o, t, x, y, sc) {
    var walking = o.mv && sc === 1, stp = walking ? Math.sin(t / 105 + o.ph) : 0;
    var bob = walking && o.kind !== 'marine' ? -Math.abs(stp) * 2.6 : o.kind === 'marine' ? Math.sin(t / 650 + o.ph) * 2.2 : Math.sin(t / 900 + o.ph) * 0.9;
    var lift = (hover === o || selected === o) ? -3 : 0;
    var dot = cam.z < 0.26 && sc === 1, photo = o.p === 2 && imgs[o.i] && imgs[o.i].ok;
    var cached = !dot && !photo && !(walking || sc !== 1 || (o.anim && cam.z >= 0.7));
    if (!dot && !cached) ground(o, x, y, sc);
    var bb;
    if (dot) {
      circ(x, y - 10, 8); fs(SC[o.s], false);
      bb = [x - 10, y - 20, x + 10, y];
    } else if (photo) {
      var im = imgs[o.i].img, mw = [56, 84, 80, 70, 92, 70, 96, 72][o.s] * sc, mh = [74, 54, 56, 70, 56, 64, 42, 62][o.s] * sc;
      var k = Math.min(mw / im.naturalWidth, mh / im.naturalHeight), w = im.naturalWidth * k, h = im.naturalHeight * k;
      var y0 = y - h + 4 + bob + lift + (o.kind === 'marine' && sc === 1 ? 8 : 0);
      ctx.drawImage(im, x - w / 2, y0, w, h);
      bb = [x - w / 2, y0, x + w / 2, y0 + h];
    } else {
      if (o.p === 2) load(o);
      var e;
      if (!cached) {
        ctx.save(); ctx.translate(x, y + bob + lift); ctx.scale(sc * (sc === 1 ? o.face || 1 : 1), sc);
        STEP = stp; e = picto(o); STEP = 0;
        ctx.restore();
      } else {
        // still pictograms come from a small cache drawn at the current zoom
        var scale = Math.max(0.25, Math.pow(2, Math.round(Math.log(cam.z * dpr) / Math.LN2 * 2) / 2)), pc = cachedPicto(o, scale);
        var dw = pc.w / scale, dh = pc.h / scale;
        ctx.drawImage(pc.cv, x - dw / 2, y + bob + lift - dh + PAD, dw, dh);
        e = pc.e;
      }
      bb = [x - e[0] * sc / 2, y - e[1] * sc + bob + lift, x + e[0] * sc / 2, y + 2];
    }
    if (hover === o || selected === o) { ctx.strokeStyle = C.mark; ctx.lineWidth = LW * 2; ell(x, y, 19 * sc, 7 * sc); ctx.stroke(); }
    boxes.push([bb[0], bb[1], bb[2], bb[3], o]);
  }
  var PBOX = { humanoid: [60, 88], quad: [76, 54], wheel: [56, 60], arm: [96, 84], rover: [60, 56], med: [70, 62], marine: [78, 50], other: [60, 52] }, PAD = 8;
  var pcache = new Map(), pixels = 0, PMAX = 9e6;
  function cachedPicto(o, scale) {
    var f = o.face || 1, key = o.i + (f < 0 ? '~' : '@') + scale, c = pcache.get(key);
    if (c) { pcache.delete(key); pcache.set(key, c); return c; }
    var bx = PBOX[o.kind] || PBOX.other, cw = Math.ceil(bx[0] * scale), ch = Math.ceil(bx[1] * scale);
    var cv2 = document.createElement('canvas'); cv2.width = cw; cv2.height = ch;
    var c2 = cv2.getContext('2d'); c2.setTransform(scale * f, 0, 0, scale, cw / 2, ch - PAD * scale);
    var keep = ctx; ctx = c2; ground(o, 0, 0, 1); var e = picto(o); ctx = keep;
    c = { cv: cv2, w: cw, h: ch, e: e, px: cw * ch };
    pcache.set(key, c); pixels += c.px;
    while (pixels > PMAX && pcache.size > 1) { var k0 = pcache.keys().next().value; pixels -= pcache.get(k0).px; pcache.delete(k0); }
    return c;
  }
  function ground(o, x, y, sc) {
    if (o.kind === 'marine' && sc === 1) { ell(x, y + 1, 22, 6); ctx.fillStyle = mix(GROUND.marine, C.paper, 0.35); ctx.fill(); }
    else shadow(x, y, 15 * sc);
  }
  function load(o) {
    if (imgs[o.i]) return;
    var im = new Image(); imgs[o.i] = { img: im, ok: false };
    im.onload = function () { imgs[o.i].ok = true; };
    im.src = '/img/' + o.i + '.ct.webp';
  }

  // pictogram robots for every entry without a cut out photo; each is shaped by its section and varied by its name
  var BODY = {
    humanoid: ['#f3f2ee', '#dcdedb', '#a3a9ad', '#43474c', '#e8e2d2', '#c8cdd2', '#f3f2ee', '#2f3236'],
    quad: ['#f2c230', '#2f3236', '#ecebe6', '#e47b31', '#a3a9ad', '#f3f2ee'],
    wheel: ['#f4f4f0', '#dcdcd6', '#e8752b', '#3d6fa5', '#8f9599', '#f4f4f0'],
    arm: ['#f08a24', '#f2c230', '#eef0ef', '#5b8fbf', '#a3a9ad', '#eef0ef'],
    rover: ['#e8e4da', '#d4b36a', '#bdb8ad', '#e8e4da'],
    med: ['#ffffff', '#eef2f4', '#f7f4ee'],
    marine: ['#f2c230', '#e8752b', '#f4f4f0', '#2f3236', '#f2c230'],
    other: ['#f4d35e', '#e8a0bf', '#9ccfd8', '#f4f4f0', '#c3b1e1', '#f08a5d', '#b8d8a8']
  };
  function picto(o) {
    var R = rng(o.seed), pal = BODY[o.kind] || BODY.other, base = pal[Math.floor(R() * pal.length)];
    if (DARK) base = mix(base, C.paper, 0.12);
    var col = base, light = mix(base, '#ffffff', 0.45), pale = mix(base, '#ffffff', 0.7), dark = mix(base, '#1c1b18', 0.38), acc = SC[o.s];
    var v = Math.floor(R() * 4), k = o.kind;
    ctx.lineJoin = 'round';
    if (k === 'humanoid') {
      var hgt = 44 + R() * 12, w = 15 + R() * 6, leg = hgt * 0.36, tor = hgt * 0.34, hd = hgt * 0.24;
      rr(-w * 0.36, -leg - Math.max(0, STEP) * 3.5, w * 0.28, leg, 2); fs(dark); rr(w * 0.08, -leg - Math.max(0, -STEP) * 3.5, w * 0.28, leg, 2); fs(dark);
      var wave = R() < 0.25, wv = Math.sin(now / 260 + o.ph) * 3; if (wave) o.anim = true;
      ctx.strokeStyle = INK; ctx.lineWidth = 3.4; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(-w / 2 - 1, -leg - tor + 4); ctx.lineTo(-w / 2 - 4, -leg - 3); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(w / 2 + 1, -leg - tor + 4); if (wave) ctx.lineTo(w / 2 + 7 + wv, -leg - tor - 9); else ctx.lineTo(w / 2 + 4, -leg - 3); ctx.stroke();
      ctx.strokeStyle = col; ctx.lineWidth = 1.8;
      ctx.beginPath(); ctx.moveTo(-w / 2 - 1, -leg - tor + 4); ctx.lineTo(-w / 2 - 4, -leg - 3); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(w / 2 + 1, -leg - tor + 4); if (wave) ctx.lineTo(w / 2 + 7 + wv, -leg - tor - 9); else ctx.lineTo(w / 2 + 4, -leg - 3); ctx.stroke();
      rr(-w / 2, -leg - tor, w, tor, 4); fs(col);
      rr(-w / 2 + 3, -leg - tor * 0.62, w - 6, 3, 1); fs(acc, false);
      var hw = w * (0.72 + R() * 0.2), hy = -leg - tor - hd - 1;
      if (v === 2) { circ(0, hy + hd / 2, hd / 2 + 1); fs(light); }
      else { rr(-hw / 2, hy, hw, hd, v === 0 ? 3 : hd / 2.5); fs(light); }
      if (v === 3 || v === 0) { rr(-hw / 2 + 2, hy + hd * 0.32, hw - 4, hd * 0.32, 2); fs(INK, false); }
      else { circ(-hw * 0.18, hy + hd * 0.48, 1.6); fs(INK, false); circ(hw * 0.18, hy + hd * 0.48, 1.6); fs(INK, false); }
      if (R() < 0.3) { ctx.strokeStyle = INK; ctx.lineWidth = LW; ctx.beginPath(); ctx.moveTo(0, hy); ctx.lineTo(0, hy - 6); ctx.stroke(); circ(0, hy - 7, 2); fs(C.mark, false); }
      return [w + 14, hgt + 8];
    }
    if (k === 'quad') {
      var bl = 30 + R() * 10, bh = 10 + R() * 4, lh = 13 + R() * 5, top = -lh - bh;
      ctx.strokeStyle = INK; ctx.lineWidth = 3.2; ctx.lineCap = 'round';
      [-bl / 2 + 4, -bl / 2 + 9, bl / 2 - 9, bl / 2 - 4].forEach(function (lx, j) { ctx.beginPath(); ctx.moveTo(lx, -lh); ctx.lineTo(lx + (j % 2 ? 3 : -3), -lh / 2); ctx.lineTo(lx + (j % 2 ? 1 : -1) * STEP * 4, 0); ctx.stroke(); });
      ctx.strokeStyle = dark; ctx.lineWidth = 1.6;
      [-bl / 2 + 4, -bl / 2 + 9, bl / 2 - 9, bl / 2 - 4].forEach(function (lx, j) { ctx.beginPath(); ctx.moveTo(lx, -lh); ctx.lineTo(lx + (j % 2 ? 3 : -3), -lh / 2); ctx.lineTo(lx + (j % 2 ? 1 : -1) * STEP * 4, 0); ctx.stroke(); });
      rr(-bl / 2, top, bl, bh, 4); fs(col); rr(-bl / 2 + 4, top + bh - 4, bl - 8, 2, 1); fs(acc, false);
      if (v !== 3) { rr(bl / 2 - 3, top - 6, 11, 9, 3); fs(light); circ(bl / 2 + 4, top - 2, 1.4); fs(INK, false); if (v === 1) { path([[bl / 2, top - 6], [bl / 2 + 2, top - 11], [bl / 2 + 4, top - 6]]); fs(light); } }
      else { rr(bl / 2 - 6, top + 1, 8, bh - 2, 2); fs(INK, false); }
      if (v === 2) { ctx.strokeStyle = INK; ctx.lineWidth = LW * 1.4; ctx.beginPath(); ctx.moveTo(-bl / 2, top + 2); ctx.quadraticCurveTo(-bl / 2 - 8, top - 4, -bl / 2 - 6, top - 10); ctx.stroke(); }
      return [bl + 16, lh + bh + 12];
    }
    if (k === 'wheel') {
      if (v === 0) { // delivery box on six wheels
        rr(-14, -24, 28, 18, 4); fs(col); rr(-14, -24, 28, 7, 3); fs(light); rr(-14, -12, 28, 2.5, 1); fs(acc, false);
        [-10, 0, 10].forEach(function (wx) { circ(wx, -4, 4); fs(INK, false); });
        if (R() < 0.6) { ctx.strokeStyle = INK; ctx.lineWidth = LW; ctx.beginPath(); ctx.moveTo(10, -24); ctx.lineTo(13, -46); ctx.stroke(); path([[13, -46], [22, -43], [13, -40]]); fs(C.mark, false); }
        return [32, 48];
      }
      if (v === 1) { // tall service robot
        var th = 36 + R() * 10;
        rr(-12, -th, 24, th - 4, 9); fs(pale);
        rr(-9, -th + 5, 18, 11, 3); fs(INK, false); circ(-4, -th + 10, 1.5); fs(light, false); circ(4, -th + 10, 1.5); fs(light, false);
        rr(-12, -th * 0.45, 24, 6, 2); fs(acc);
        ell(0, -2, 13, 4); fs(dark);
        return [28, th + 4];
      }
      if (v === 2) { // floor cleaner
        ell(0, -5, 16, 7); fs(col); ell(0, -8, 16, 7); fs(light); circ(0, -9, 3.2); fs(col, false);
        return [34, 18];
      }
      rr(-18, -14, 36, 8, 2); fs(col); rr(-12, -28, 24, 14, 2); fs(mix('#d4b483', C.paper, 0.2)); // cart with a load
      circ(-12, -4, 3.5); fs(INK, false); circ(12, -4, 3.5); fs(INK, false);
      return [38, 30];
    }
    if (k === 'arm') {
      var a1 = -1.2 - R() * 0.8, a2 = 0.8 + R() * 1.1, l1 = 22 + R() * 6, l2 = 18 + R() * 6, sway = Math.sin(now / 1400 + o.ph) * 0.12; o.anim = true;
      ell(0, -3, 12, 5); fs(mix('#43474c', C.paper, 0.1)); rr(-7, -14, 14, 11, 3); fs(col);
      var j1 = [Math.cos(a1 + sway) * l1, -14 + Math.sin(a1 + sway) * l1], j2 = [j1[0] + Math.cos(a1 + a2 + sway) * l2, j1[1] + Math.sin(a1 + a2 + sway) * l2];
      ctx.lineCap = 'round';
      ctx.strokeStyle = INK; ctx.lineWidth = 8.5; ctx.beginPath(); ctx.moveTo(0, -14); ctx.lineTo(j1[0], j1[1]); ctx.lineTo(j2[0], j2[1]); ctx.stroke();
      ctx.strokeStyle = col; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(0, -14); ctx.lineTo(j1[0], j1[1]); ctx.lineTo(j2[0], j2[1]); ctx.stroke();
      circ(0, -14, 3); fs(INK, false); circ(j1[0], j1[1], 3); fs(INK, false);
      ctx.strokeStyle = INK; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(j2[0] - 3, j2[1]); ctx.lineTo(j2[0] - 4, j2[1] + 6); ctx.moveTo(j2[0] + 3, j2[1]); ctx.lineTo(j2[0] + 4, j2[1] + 6); ctx.stroke();
      return [52, 52];
    }
    if (k === 'rover') {
      ctx.strokeStyle = INK; ctx.lineWidth = LW;
      [-13, 0, 13].forEach(function (wx) { circ(wx, -5, 5); fs(mix(C.ink, C.paper, 0.25)); circ(wx, -5, 1.6); fs(light, false); });
      rr(-17, -20, 34, 10, 2); fs(col); rr(-17, -13, 34, 2, 1); fs(acc, false);
      if (v !== 1) { path([[-20, -24], [12, -24], [17, -20], [-15, -20]]); fs(mix(SC[2], C.ink, 0.25)); }
      ctx.strokeStyle = INK; ctx.lineWidth = LW * 1.4; ctx.beginPath(); ctx.moveTo(9, -20); ctx.lineTo(9, -36); ctx.stroke();
      rr(4, -42, 11, 7, 2); fs(light); circ(13, -38.5, 1.4); fs(INK, false);
      return [42, 44];
    }
    if (k === 'med') {
      rr(-12, -40, 24, 36, 6); fs(col); ctx.fillStyle = acc; ctx.fillRect(-3, -31, 6, 16); ctx.fillRect(-8, -26, 16, 6);
      ell(0, -3, 14, 4.5); fs(pale);
      if (v % 2) { ctx.strokeStyle = INK; ctx.lineWidth = 6; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(10, -34); ctx.lineTo(22, -44); ctx.lineTo(28, -30); ctx.stroke(); ctx.strokeStyle = light; ctx.lineWidth = 3.6; ctx.stroke(); }
      return [40, 48];
    }
    if (k === 'marine') {
      if (v === 0 || v === 2) { // torpedo
        ell(0, -6, 24, 7); fs(col); path([[-22, -6], [-30, -14], [-30, 2]]); fs(dark); rr(-6, -12, 12, 2.5, 1); fs(acc, false);
        circ(10, -7, 2.6); fs(pale); ctx.fillStyle = light; ctx.fillRect(-8, -14, 3, 4);
        return [60, 18];
      }
      if (v === 1) { // ROV frame
        rr(-16, -22, 32, 18, 3); fs(mix(col, C.paper, 0.2)); rr(-12, -26, 24, 6, 2); fs('#e8b03c');
        circ(-8, -13, 3); fs(INK, false); circ(8, -13, 3); fs(INK, false);
        return [36, 30];
      }
      path([[-20, -6], [20, -6], [14, 2], [-14, 2]]); fs(col); // surface boat with a sail
      ctx.strokeStyle = INK; ctx.lineWidth = LW; ctx.beginPath(); ctx.moveTo(0, -6); ctx.lineTo(0, -34); ctx.stroke();
      path([[1, -32], [15, -9], [1, -9]]); fs(pale);
      return [42, 38];
    }
    // other forms
    if (v === 0 || v === 3) {
      ell(0, -16, 13, 15); fs(v === 3 ? light : col);
      circ(-5, -18, 3); fs('#fff'); circ(5, -18, 3); fs('#fff'); circ(-4.5, -18, 1.5); fs(INK, false); circ(5.5, -18, 1.5); fs(INK, false);
      if (R() < 0.5) { path([[-10, -27], [-13, -38], [-4, -30]]); fs(dark); path([[10, -27], [13, -38], [4, -30]]); fs(dark); }
      return [30, 40];
    }
    if (v === 1) { // modular snake
      o.anim = true;
      for (var s2 = 0; s2 < 5; s2++) { circ(-16 + s2 * 8, -6 - Math.sin(now / 500 + s2 + o.ph) * 3, 5); fs(s2 % 2 ? light : col); }
      return [44, 18];
    }
    rr(-10, -28, 20, 24, 4); fs(pale); rr(-7, -24, 14, 9, 2); fs(INK, false); circ(-3, -19.5, 1.5); fs(C.mark, false); circ(3, -19.5, 1.5); fs(C.mark, false);
    circ(0, -2, 3); fs(INK, false);
    return [24, 32];
  }

  // the visitor
  function drawMe(t) {
    var p = iso(me.x, me.y), x = p[0], y = p[1], step = me.moving ? Math.sin(t / 90) : 0, hop = me.moving ? Math.abs(step) * 2 : 0;
    var swim = inWater(me.x, me.y);
    if (swim) { ell(x, y, 16, 5); ctx.fillStyle = mix(GROUND.marine, C.paper, 0.4); ctx.fill(); }
    else shadow(x, y, 13);
    ctx.save(); ctx.translate(x, y - hop); ctx.scale(me.face * 1.2, 1.2);
    if (!swim) {
      ctx.strokeStyle = INK; ctx.lineWidth = 3; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(-4, -12); ctx.lineTo(-4 + step * 3, 0); ctx.moveTo(4, -12); ctx.lineTo(4 - step * 3, 0); ctx.stroke();
    }
    rr(-10, -30, 20, 20, 7); fs(DARK ? '#e9e4d8' : '#ffffff');
    circ(0, -38, 10); fs(DARK ? '#e9e4d8' : '#ffffff');
    rr(-4, -42, 13, 6, 3); fs(C.mark, false);
    ctx.strokeStyle = INK; ctx.lineWidth = LW; ctx.beginPath(); ctx.moveTo(0, -48); ctx.lineTo(-2, -55); ctx.stroke(); circ(-2, -56, 2.4); fs(C.mark, false);
    ctx.restore();
  }
  function inWater(x, y) {
    for (var i = 0; i < districts.length; i++) { var d = districts[i]; if (d.k === 'marine' && x > d.x && x < d.x + d.w && y > d.y && y < d.y + d.h) return true; }
    return false;
  }
  function districtAt(x, y) {
    for (var i = 0; i < districts.length; i++) { var d = districts[i]; if (x >= d.x && x <= d.x + d.w && y >= d.y && y <= d.y + d.h) return d; }
    return null;
  }

  // ---------- speech bubbles and names (screen pixels)
  function say(o, text, ms) { bubbles = bubbles.filter(function (b) { return b.o !== o && !(o.me && b.o.me); }); bubbles.push({ o: o, text: text, until: now + (ms || 4500) }); }
  function toScreen(x, y) { var p = iso(x, y); return [(p[0] - cam.x) * cam.z + W / 2, (p[1] - cam.y) * cam.z + H / 2]; }
  function wrap(text, maxw) {
    var words = text.split(' '), lines = [], line = '';
    words.forEach(function (w) { var t = line ? line + ' ' + w : w; if (ctx.measureText(t).width > maxw && line) { lines.push(line); line = w; } else line = t; });
    if (line) lines.push(line);
    return lines.slice(0, 4);
  }
  function drawOverlay() {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic'; ctx.lineJoin = 'round'; ctx.miterLimit = 2;
    // names
    var showAll = cam.z >= 1.25, showStars = cam.z >= 0.8;
    ctx.font = '600 12px "Source Serif 4", Georgia, serif';
    boxes.forEach(function (b) {
      var o = b[4];
      if (!(o === hover || o === selected || showAll || (showStars && o.p === 2))) return;
      var s = toScreen(o.x, o.y), y = s[1] + 16;
      if (s[0] < -60 || s[0] > W + 60 || y < 0 || y > H + 20) return;
      ctx.lineWidth = 3.5; ctx.strokeStyle = C.paper; ctx.strokeText(o.n, s[0], y);
      ctx.fillStyle = o === hover || o === selected ? C.mark : C.ink; ctx.fillText(o.n, s[0], y);
    });
    // labels for the places on the plaza
    if (cam.z >= 0.38) {
      ctx.font = 'italic 13px "Source Serif 4", Georgia, serif';
      stand.forEach(function (o) {
        if (!o.label || o.t === 'board') return;
        var cx2 = o.x + (o.t === 'pedestal' ? 0 : (o.a || 0) / 2), cy2 = o.y + (o.t === 'pedestal' ? 0 : (o.b || 0) / 2), s = toScreen(cx2, cy2), y = s[1] + 22;
        if (s[0] < -80 || s[0] > W + 80 || y < -20 || y > H + 20) return;
        ctx.lineWidth = 4; ctx.strokeStyle = C.paper; ctx.strokeText(o.label, s[0], y); ctx.fillStyle = C.mark; ctx.fillText(o.label, s[0], y);
      });
    }
    // entrance boards
    if (cam.z >= 0.42) {
      ctx.font = '13px "Young Serif", Georgia, serif'; ctx.fillStyle = C.ink;
      stand.forEach(function (o) {
        if (o.t !== 'board') return;
        var s = toScreen(o.x, o.y), y = s[1] - 41 * cam.z + 4;
        if (s[0] < -80 || s[0] > W + 80 || y < -20 || y > H + 20) return;
        var fz = Math.max(9, Math.min(15, 13 * cam.z / 0.8)); ctx.font = fz + 'px "Young Serif", Georgia, serif';
        var tw = ctx.measureText(o.a).width, bw = 48 * cam.z;
        if (tw > bw - 4) { ctx.lineWidth = 3; ctx.strokeStyle = C.sheet; ctx.strokeText(o.a, s[0], y); }
        ctx.fillText(o.a, s[0], y);
      });
    }
    // district names when looking from far away
    if (cam.z < 0.55) {
      districts.forEach(function (d) {
        if (d.k === 'plaza' && cam.z >= 0.3) return;
        var s = toScreen(d.x + d.w / 2, d.y + d.h / 2);
        ctx.font = (cam.z < 0.3 ? 17 : 22) + 'px "Young Serif", Georgia, serif';
        ctx.lineWidth = 5; ctx.strokeStyle = C.paper; ctx.strokeText(d.n, s[0], s[1]); ctx.fillStyle = C.ink; ctx.fillText(d.n, s[0], s[1]);
        if (d.count) { ctx.font = 'italic 13px "Source Serif 4", Georgia, serif'; var t = d.count + ' robots'; ctx.lineWidth = 4; ctx.strokeText(t, s[0], s[1] + 17); ctx.fillStyle = C.soft; ctx.fillText(t, s[0], s[1] + 17); }
      });
    }
    // bubbles
    ctx.font = '14px "Source Serif 4", Georgia, serif'; ctx.textAlign = 'left';
    bubbles = bubbles.filter(function (b) { return b.until > now; });
    bubbles.forEach(function (b) {
      var o = b.o, s = o.me ? toScreen(me.x, me.y) : toScreen(o.x, o.y), lines = wrap(b.text, 210);
      var bw = Math.max.apply(null, lines.map(function (l) { return ctx.measureText(l).width; })) + 22, bh = lines.length * 19 + 14;
      var head = o.me ? 64 : (o.p === 2 ? 80 : 62);
      var bx = Math.max(8, Math.min(W - bw - 8, s[0] - bw / 2)), by = s[1] - head * Math.max(0.6, Math.min(1.4, cam.z)) - bh - 8;
      if (by < 8) by = 8;
      var fade = Math.min(1, (b.until - now) / 300);
      ctx.globalAlpha = fade;
      ctx.beginPath(); rrS(bx, by, bw, bh, 9); ctx.fillStyle = C.sheet; ctx.fill(); ctx.strokeStyle = C.ink; ctx.lineWidth = 1.4; ctx.stroke();
      var tx = Math.max(bx + 14, Math.min(bx + bw - 14, s[0]));
      ctx.beginPath(); ctx.moveTo(tx - 7, by + bh - 0.5); ctx.lineTo(tx, by + bh + 9); ctx.lineTo(tx + 7, by + bh - 0.5); ctx.fillStyle = C.sheet; ctx.fill();
      ctx.beginPath(); ctx.moveTo(tx - 7, by + bh); ctx.lineTo(tx, by + bh + 9); ctx.lineTo(tx + 7, by + bh); ctx.stroke();
      ctx.fillStyle = C.ink; lines.forEach(function (l, i) { ctx.fillText(l, bx + 11, by + 22 + i * 19); });
      ctx.globalAlpha = 1;
    });
  }
  function rrS(x, y, w, h, r) { ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }

  // ---------- the frame
  function frame(t) {
    var dt = Math.min(0.05, (t - (last || t)) / 1000); last = t; now = t;
    if (!document.hidden) { update(dt); draw(t); }
    requestAnimationFrame(frame);
  }
  function update(dt) {
    // keys
    var kx = 0, ky = 0;
    if (keys.w || keys.arrowup) { kx -= 1; ky -= 1; }
    if (keys.s || keys.arrowdown) { kx += 1; ky += 1; }
    if (keys.a || keys.arrowleft) { kx -= 1; ky += 1; }
    if (keys.d || keys.arrowright) { kx += 1; ky -= 1; }
    if (kx || ky) {
      var l = Math.hypot(kx, ky); me.x += kx / l * 5 * dt; me.y += ky / l * 5 * dt; me.moving = true; me.path = null; follow = true;
      me.face = (kx - ky) >= 0 ? 1 : -1;
    } else if (me.path) {
      var dx = me.path[0] - me.x, dy = me.path[1] - me.y, dist = Math.hypot(dx, dy), sp = 5.5 * dt;
      if (dist <= sp) { me.x = me.path[0]; me.y = me.path[1]; me.path = null; me.moving = false; arrived(); }
      else { me.x += dx / dist * sp; me.y += dy / dist * sp; me.moving = true; me.face = (dx - dy) >= 0 ? 1 : -1; }
    } else me.moving = false;
    me.x = Math.max(1.2, Math.min(WORLD.W - 1.2, me.x)); me.y = Math.max(1.2, Math.min(WORLD.H - 1.2, me.y));
    updateMovers(dt); chatter();
    // camera
    if (fly) {
      var k = Math.min(1, (now - fly.t0) / fly.ms), e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      cam.x = fly.x0 + (fly.x1 - fly.x0) * e; cam.y = fly.y0 + (fly.y1 - fly.y0) * e; cam.z = fly.z0 + (fly.z1 - fly.z0) * e;
      if (k >= 1) { fly = null; if (fly_done) { var f = fly_done; fly_done = null; f(); } }
    } else if (follow && me.moving) {
      var p = iso(me.x, me.y), sx = (p[0] - cam.x) * cam.z, sy = (p[1] - 30 - cam.y) * cam.z;
      var mx = W * 0.18, my = H * 0.16;
      if (Math.abs(sx) > mx) cam.x += (sx - Math.sign(sx) * mx) / cam.z * Math.min(1, dt * 6);
      if (Math.abs(sy) > my) cam.y += (sy - Math.sign(sy) * my) / cam.z * Math.min(1, dt * 6);
    }
    // where am I
    var d = districtAt(me.x, me.y), key = d ? d.k : 'road';
    if (key !== lastWhere) {
      lastWhere = key;
      var el = root.querySelector('.w-where');
      if (d) { el.innerHTML = '<b>' + esc(d.n) + '</b>' + (d.count ? ' <span>' + d.count + ' ' + (SEC[d.s] ? SEC[d.s][1].toLowerCase() : 'robots') + ' live here</span>' : ' <span>The middle of everything</span>'); el.classList.add('on'); clearTimeout(el._t); el._t = setTimeout(function () { el.classList.remove('on'); }, 3800); }
    }
  }
  var fly_done = null;
  function arrived() {
    // greet the nearest robot within reach
    var best = null, bd = 2.6;
    robots.forEach(function (o) { var d = Math.hypot(o.x - me.x, o.y - me.y); if (d < bd) { bd = d; best = o; } });
    if (best && (!greeted[best.i] || now - greeted[best.i] > 20000)) { greeted[best.i] = now; say(best, line(best)); meet(best); }
  }
  // robots nearby say something true about themselves now and then
  function chatter() {
    if (STILL) return;
    if (!nextChat) nextChat = now + 5000;
    if (now < nextChat || cam.z < 0.45 || fly) return;
    nextChat = now + 3000 + Math.random() * 3500;
    if (bubbles.filter(function (b) { return !b.o.me; }).length >= 2) return;
    var rb = root.getBoundingClientRect(), cover = [root.querySelector('.w-intro'), root.querySelector('.w-card')].filter(function (el) { return el && !el.hidden; }).map(function (el) { var r = el.getBoundingClientRect(); return [r.left - rb.left - 20, r.top - rb.top - 60, r.right - rb.left + 20, r.bottom - rb.top + 120]; });
    var cand = [];
    for (var i = 0; i < robots.length; i++) {
      var o = robots[i]; if (o === selected) continue;
      var d = Math.hypot(o.x - me.x, o.y - me.y); if (d > 10 || d < 0.8) continue;
      var sc2 = toScreen(o.x, o.y); if (sc2[0] < 70 || sc2[0] > W - 70 || sc2[1] < 150 || sc2[1] > H - 30) continue;
      if (cover.some(function (c) { return sc2[0] > c[0] && sc2[0] < c[2] && sc2[1] > c[1] && sc2[1] < c[3]; })) continue;
      if (bubbles.some(function (b) { return b.o === o; })) continue;
      cand.push(o); if (o.p === 2) cand.push(o, o);
    }
    if (cand.length) { var pick = cand[Math.floor(Math.random() * cand.length)]; say(pick, chat(pick), 4800); }
  }
  var PLAIN = ('robotic autonomous small robot humanoid compact full wheeled self early open low animatronic modular surgical first industrial lightweight remotely research programmable '
    + 'educational battery solar powered collaborative social mobile interactive android commercial automated retrofit second palm large tethered toy experimental electric remote talking '
    + 'consumer uncrewed home companion female third untethered lifelike heavy lunar hydraulic hospital personal radio snake ball walking tiny swarm mechanical transformable chess medical '
    + 'high deep slim expressive omnidirectional bipedal domestic tracked very laser free soft hybrid telepresence dexterous single biomorphic giant submersible long warehouse underwater '
    + 'kitchen portable upper ultra prototype fourth fifth passive teleoperated ultralight desktop hobby outdoor spider indoor household fully agile tabletop miniature articulated floor '
    + 'inspection rescue electronic magnetic cordless huge medium unmanned conversational care singing tall cat cylindrical golf window ocean entertainment clockwork jumping planar '
    + 'therapeutic service humanlike scaled learning insect welding wireless sidewalk rideable advanced roaming wheel buildable character furry suitcase dual segmented larger twin kinetic '
    + 'benchtop minimalist laparoscopic tray capsule gripping general redesigned smallest gearless orthopedic half keyboard greenhouse picking hobbyist musculoskeletal squat outdoor ground '
    + 'classroom milking airport flight shoebox centaur cloud car tailed underactuated bear tendon disc coding electrically show buoyant anthropomorphic cart pipe radiation painting '
    + 'waterless semi terrestrial kit flat retrofitted spring navigation highly matchbox system biohybrid concept successor fast vending engineering all piano version fake hoax purported '
    + 'mars tracked rover vacuum delivery cleaning autonomous security agricultural farm lawn pool window').split(' ');
  var KEEP = 'Chinese Indian French Japanese Russian British Korean German Soviet Swiss Spanish Italian Portuguese Emirati Iranian Austrian European American Canadian Dutch Danish Swedish Norwegian Israeli Taiwanese Australian Finnish Belgian Polish Turkish'.split(' ');
  var NUMS = { two: 1, three: 1, four: 1, six: 1, seven: 1, eight: 1, twelve: 1 };
  function selfDef(d) {
    if (!d) return '';
    var cut = d.indexOf('. '); if (cut > 0) d = d.slice(0, cut + 1);
    var first = d.split(' ')[0].replace(/[,.;:]$/, ''), low = first.toLowerCase(), s;
    if (first === 'A' || first === 'An' || first === 'The') s = d.charAt(0).toLowerCase() + d.slice(1);
    else if (/^[A-Z][A-Za-z]+'s$/.test(first)) s = d;
    else if (KEEP.indexOf(first) >= 0) s = (/^[AEIOU]/.test(first) && !/^Eu/.test(first) ? 'an ' : 'a ') + d;
    else if (PLAIN.indexOf(low) >= 0 || (NUMS[low] && /^\w+ (legged|wheeled|axis|armed|jointed|fingered|tracked)\b/i.test(d))) s = (/^[aeiou]/.test(low) && !/^(uni|use|one|eu)/.test(low) ? 'an ' : 'a ') + d.charAt(0).toLowerCase() + d.slice(1);
    else return '';
    s = "I'm " + s;
    if (s.length > 112) { s = s.slice(0, 110); s = s.slice(0, s.lastIndexOf(' ')).replace(/[\s,;:]+$/, '').replace(/\s+(and|or|of|the|a|an|to|for|with|from|in|on|by|that|which|its|their|as|at)$/i, '') + '…'; }
    return s;
  }
  function chat(o) {
    var opts = [line(o)], self = selfDef(o.d);
    if (self) opts.push(self, self);
    if (o.yr) opts.push('I first showed up in ' + o.yr + '.' + (o.st === 3 ? ' My working days are over.' : o.st === 1 ? ' I am still at work.' : o.st === 2 ? ' I am still a work in progress.' : ''));
    if (o.c && !/,| and /.test(o.c)) opts.push('I come from ' + (/^(United |Netherlands|Soviet Union|Czech Republic|Philippines|European Union|Republic )/.test(o.c) ? 'the ' : '') + o.c + '.');
    if (o.stroll) opts.push('I like walking around the plaza.');
    return opts[Math.floor(Math.random() * opts.length)];
  }
  // the robots this visitor has met, kept in this browser only
  function meet(o) {
    if (!o || met[o.i]) return;
    met[o.i] = 1; showMet(true);
    try { localStorage.setItem('rw-met', JSON.stringify(Object.keys(met))); } catch (e) {}
  }
  function showMet(fresh) {
    metN = robots.filter(function (o) { return met[o.i]; }).length;
    var el = root.querySelector('.w-met'); if (!el) return;
    el.innerHTML = 'You have met <b>' + metN.toLocaleString('en-US') + '</b> of ' + robots.length.toLocaleString('en-US') + ' robots.';
    if (fresh) { el.classList.remove('pop'); void el.offsetWidth; el.classList.add('pop'); }
  }
  function line(o) {
    var who = [o.m, o.yr].filter(Boolean).join(', ').replace(/\.$/, '');
    return "Hi, I'm " + o.n.replace(/\.$/, '') + '.' + (who ? ' ' + who + '.' : '');
  }

  function draw(t) {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = C.paper; ctx.fillRect(0, 0, W, H);
    var z = cam.z; LW = 1.15 / Math.max(0.5, z) * (z < 0.5 ? 0.9 : 1);
    ctx.setTransform(dpr * z, 0, 0, dpr * z, dpr * (W / 2 - cam.x * z), dpr * (H / 2 - cam.y * z));
    var vb = [cam.x - W / 2 / z, cam.y - H / 2 / z, cam.x + W / 2 / z, cam.y + H / 2 / z];
    drawGround(vb);
    flat.forEach(function (o) { var p = iso(o.x, o.y); if (p[0] > vb[0] - 1600 && p[0] < vb[2] + 1600 && p[1] > vb[1] - 600 && p[1] < vb[3] + 600) drawFlat(o); });
    boxes = [];
    var meDrawn = false, meDepth = fixDepth(me.x, me.y, solids);
    for (var i = 0; i < stand.length; i++) {
      var o = stand[i];
      if (!meDrawn && o.depth > meDepth) { drawMe(t); meDrawn = true; }
      var p = iso(o.x, o.y), pad = o.robot ? 80 : 260;
      if (p[0] < vb[0] - pad || p[0] > vb[2] + pad || p[1] < vb[1] - 30 || p[1] > vb[3] + pad + 120) continue;
      if (o.robot) drawRobot(o, t);
      else if (z > 0.2 || o.t === 'tower' || o.t === 'monument' || o.t === 'factory' || o.t === 'clinic' || o.t === 'wheel') drawProp(o);
    }
    if (!meDrawn) drawMe(t);
    drawOverlay();
    drawMini();
  }

  var miniTick = 0;
  function drawMini() {
    if (now - miniTick < 120) return; miniTick = now;
    var mw = mini.width, mh = mini.height, k = Math.min(mw / ((WORLD.W + WORLD.H) * HW), mh / ((WORLD.W + WORLD.H) * HH)) * 0.96;
    var ox = mw / 2, oy = (mh - (WORLD.W + WORLD.H) * HH * k) / 2;
    function m(x, y) { var p = iso(x, y); return [ox + p[0] * k, oy + p[1] * k]; }
    mctx.setTransform(1, 0, 0, 1, 0, 0); mctx.clearRect(0, 0, mw, mh);
    districts.forEach(function (d) {
      var a = m(d.x, d.y), b = m(d.x + d.w, d.y), c = m(d.x + d.w, d.y + d.h), e = m(d.x, d.y + d.h);
      mctx.beginPath(); mctx.moveTo(a[0], a[1]); mctx.lineTo(b[0], b[1]); mctx.lineTo(c[0], c[1]); mctx.lineTo(e[0], e[1]); mctx.closePath();
      mctx.fillStyle = d.s >= 0 ? mix(C.paper, SC[d.s], 0.5) : mix(C.paper, C.ink, 0.15); mctx.fill();
    });
    var corners = [[0, 0], [W, 0], [W, H], [0, H]].map(function (s) { var wx = (s[0] - W / 2) / cam.z + cam.x, wy = (s[1] - H / 2) / cam.z + cam.y; return [ox + wx * k, oy + wy * k]; });
    mctx.strokeStyle = C.ink; mctx.lineWidth = 1.2; mctx.beginPath(); corners.forEach(function (c, i) { if (i) mctx.lineTo(c[0], c[1]); else mctx.moveTo(c[0], c[1]); }); mctx.closePath(); mctx.stroke();
    var me2 = m(me.x, me.y); mctx.fillStyle = C.mark; mctx.beginPath(); mctx.arc(me2[0], me2[1], 3.2, 0, 6.3); mctx.fill();
    mini._k = k; mini._ox = ox; mini._oy = oy;
  }

  // ---------- input
  function toWorld(sx, sy) {
    var wx = (sx - W / 2) / cam.z + cam.x, wy = (sy - H / 2) / cam.z + cam.y;
    return { px: wx, py: wy, x: (wx / HW + wy / HH) / 2, y: (wy / HH - wx / HW) / 2 };
  }
  function hit(sx, sy) {
    var w = toWorld(sx, sy);
    for (var i = boxes.length - 1; i >= 0; i--) { var b = boxes[i]; if (w.px >= b[0] - 3 && w.px <= b[2] + 3 && w.py >= b[1] - 3 && w.py <= b[3] + 6) return b[4]; }
    // small robots are forgiving: take the nearest one within a fingertip
    var best = null, bd = 22 / cam.z;
    for (var j = 0; j < boxes.length; j++) {
      var c = boxes[j]; if (!c[4].robot) continue;
      var d = Math.hypot(Math.max(c[0] - w.px, 0, w.px - c[2]), Math.max(c[1] - w.py, 0, w.py - c[3]));
      if (d < bd) { bd = d; best = c[4]; }
    }
    return best;
  }
  function zoomAt(sx, sy, f) {
    var before = toWorld(sx, sy);
    cam.z = Math.max(0.16, Math.min(2.4, cam.z * f));
    var after = toWorld(sx, sy);
    cam.x += before.px - after.px; cam.y += before.py - after.py;
    fly = null;
  }
  function walkTo(x, y) {
    me.path = [Math.max(1.2, Math.min(WORLD.W - 1.2, x)), Math.max(1.2, Math.min(WORLD.H - 1.2, y))]; follow = true;
  }
  function select(o, walk) {
    selected = o;
    var card = root.querySelector('.w-card'); card.hidden = false; root.classList.add('carded');
    var pic = card.querySelector('.w-pic'); pic.hidden = false;
    if (o.p === 2) pic.innerHTML = '<img src="/img/' + o.i + '.ct.webp" alt="">';
    else if (o.p === 1) pic.innerHTML = '<img class="ph" src="/img/' + o.i + '.t.webp" alt="">';
    else { pic.innerHTML = '<canvas width="160" height="140"></canvas>'; drawCardPicto(pic.querySelector('canvas'), o); }
    card.querySelector('h2').textContent = o.n;
    card.querySelector('.pos').innerHTML = '<span class="sw" style="--c:' + SC[o.s] + '"></span>' + esc(SEC[o.s][1]) + (o.m || o.c || o.yr ? '. ' + esc([o.m, o.c, o.yr].filter(Boolean).join(', ')) + '.' : '.');
    card.querySelector('.def').textContent = o.d || '';
    var a = card.querySelector('.w-acts a'); a.href = '/' + o.i + '/'; a.textContent = 'Open the entry';
    card.querySelector('[data-share]').hidden = false;
    card.querySelector('.copied').hidden = true;
    if (history.replaceState) history.replaceState(null, '', '#' + o.i);
    say(o, line(o), 5200); meet(o);
    if (walk) { walkTo(o.x + 1.6, o.y - 0.4); focus(o.x, o.y); }
  }
  var PLACES = {
    play: ['The Robodle booth', "Today's robot is hiding in a shadow. Name it in eight guesses; a new one arrives at midnight.", 'Play Robodle', '/play/'],
    museum: ['The Museum of Robot History', "Every dated robot on one chart, from a clockwork duck of 1739 to this year's humanoids.", 'Open the chart', '/evolution/'],
    news: ['The newsstand', "This morning's robotics headlines, each linked to the robots it mentions.", 'Read the news', '/news/'],
    book: ['The Dictionary', 'Every robot that lives in this city has an entry, with its maker, its dates and its sources.', 'Open the A to Z', '/a-z/']
  };
  function openPlace(o) {
    var P = PLACES[o.place]; if (!P) return;
    selected = null;
    var card = root.querySelector('.w-card'); card.hidden = false; root.classList.add('carded');
    card.querySelector('.w-pic').innerHTML = ''; card.querySelector('.w-pic').hidden = true;
    card.querySelector('h2').textContent = P[0];
    card.querySelector('.pos').textContent = '';
    card.querySelector('.def').textContent = P[1];
    var a = card.querySelector('.w-acts a'); a.href = P[3]; a.textContent = P[2];
    card.querySelector('[data-share]').hidden = true; card.querySelector('.copied').hidden = true;
    walkTo(o.x + 2, o.y + 2.5); focus(o.x, o.y);
  }
  function drawCardPicto(c, o) {
    var save = ctx; var c2 = c.getContext('2d'); c2.scale(1.6, 1.6); c2.translate(50, 80);
    ctx = c2; var lw = LW; LW = 1.2; picto(o); LW = lw; ctx = save;
  }
  // on a phone the card is a sheet over the lower half, so what it describes sits higher on the screen
  function sheetShift(z) { return W < 720 ? H * 0.2 / z : 0; }
  function focus(x, y) {
    if (W >= 720) return;
    var sc2 = toScreen(x, y); if (sc2[1] < H * 0.42 && sc2[1] > 120) return;
    var p = iso(x, y); follow = false;
    fly = { t0: now, ms: 700, x0: cam.x, y0: cam.y, z0: cam.z, x1: p[0], y1: p[1] - 40 + sheetShift(cam.z), z1: cam.z };
  }
  function goTo(o, open) {
    var p = iso(o.x, o.y), z1 = Math.max(cam.z, W < 640 ? 0.8 : 1.0);
    fly = { t0: now || performance.now(), ms: 1100, x0: cam.x, y0: cam.y, z0: cam.z, x1: p[0], y1: p[1] - 40 + sheetShift(z1), z1: z1 };
    me.x = o.x + 1.6; me.y = o.y - 0.4; me.path = null; follow = false; selected = o;
    fly_done = function () { if (open) select(o, false); };
  }

  function wire() {
    var ptrs = {}, drag = null, pinch = null;
    cv.addEventListener('pointerdown', function (e) {
      cv.setPointerCapture(e.pointerId); ptrs[e.pointerId] = [e.offsetX, e.offsetY];
      var ids = Object.keys(ptrs);
      if (ids.length === 2) { var a = ptrs[ids[0]], b = ptrs[ids[1]]; pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), z: cam.z }; drag = null; }
      else drag = { x: e.offsetX, y: e.offsetY, cx: cam.x, cy: cam.y, moved: false };
    });
    cv.addEventListener('pointermove', function (e) {
      if (ptrs[e.pointerId]) ptrs[e.pointerId] = [e.offsetX, e.offsetY];
      var ids = Object.keys(ptrs);
      if (pinch && ids.length === 2) {
        var a = ptrs[ids[0]], b = ptrs[ids[1]], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        var f = (pinch.z * d / pinch.d) / cam.z; zoomAt((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, f); return;
      }
      if (drag) {
        var dx = e.offsetX - drag.x, dy = e.offsetY - drag.y;
        if (Math.abs(dx) + Math.abs(dy) > 6) { drag.moved = true; follow = false; fly = null; root.classList.add('dragging'); }
        if (drag.moved) { cam.x = drag.cx - dx / cam.z; cam.y = drag.cy - dy / cam.z; }
      } else if (e.pointerType === 'mouse') {
        var h = hit(e.offsetX, e.offsetY); hover = h; cv.style.cursor = h ? 'pointer' : 'default';
      }
    });
    function up(e) {
      delete ptrs[e.pointerId];
      if (pinch) { if (Object.keys(ptrs).length < 2) pinch = null; drag = null; return; }
      if (drag && !drag.moved) {
        var o = hit(e.offsetX, e.offsetY);
        if (o && o.place) openPlace(o);
        else if (o) select(o, true);
        else { var w = toWorld(e.offsetX, e.offsetY); walkTo(w.x, w.y); }
      }
      drag = null; root.classList.remove('dragging');
    }
    cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
    cv.addEventListener('pointerleave', function () { hover = null; });
    cv.addEventListener('wheel', function (e) { e.preventDefault(); zoomAt(e.offsetX, e.offsetY, Math.exp(-e.deltaY * 0.0015)); }, { passive: false });
    window.addEventListener('keydown', function (e) {
      if (/input|textarea/i.test(document.activeElement.tagName)) return;
      var k = e.key.toLowerCase();
      if (['w', 'a', 's', 'd', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].indexOf(k) >= 0) { keys[k] = true; e.preventDefault(); }
      if (k === '+' || k === '=') zoomAt(W / 2, H / 2, 1.2);
      if (k === '-') zoomAt(W / 2, H / 2, 1 / 1.2);
      if (k === 'escape' && !root.querySelector('.w-card').hidden) root.querySelector('.w-card .w-x').click();
    });
    window.addEventListener('keyup', function (e) { keys[e.key.toLowerCase()] = false; if (!Object.keys(keys).some(function (k) { return keys[k]; })) arrived(); });
    window.addEventListener('resize', resize);
    window.addEventListener('hashchange', function () { var h = decodeURIComponent(location.hash.slice(1)); if (byId[h] && byId[h] !== selected) goTo(byId[h], true); });
    root.querySelectorAll('.w-zoom [data-z]').forEach(function (b) { b.addEventListener('click', function () { zoomAt(W / 2, H / 2, b.getAttribute('data-z') === '1' ? 1.35 : 1 / 1.35); }); });
    root.querySelector('.w-zoom [data-home]').addEventListener('click', function () {
      var p = iso(me.x, me.y); fly = { t0: now, ms: 700, x0: cam.x, y0: cam.y, z0: cam.z, x1: p[0], y1: p[1] - 30, z1: Math.max(0.7, cam.z) }; follow = true;
    });
    mini.addEventListener('click', function (e) {
      var r = mini.getBoundingClientRect(), sx = (e.clientX - r.left) * mini.width / r.width, sy = (e.clientY - r.top) * mini.height / r.height;
      fly = { t0: now, ms: 600, x0: cam.x, y0: cam.y, z0: cam.z, x1: (sx - mini._ox) / mini._k, y1: (sy - mini._oy) / mini._k, z1: cam.z }; follow = false;
    });
    root.querySelector('.w-card .w-x').addEventListener('click', function () { root.querySelector('.w-card').hidden = true; root.classList.remove('carded'); selected = null; if (history.replaceState) history.replaceState(null, '', location.pathname); });
    root.querySelector('.w-card [data-share]').addEventListener('click', function () {
      if (!selected) return;
      var url = location.origin + '/world/#' + selected.i, done = function () { root.querySelector('.w-card .copied').hidden = false; };
      if (navigator.share && /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)) navigator.share({ title: selected.n + ' in Robot World', url: url }).catch(function () {});
      else if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, done);
    });
    root.querySelector('.w-rand').addEventListener('click', function () {
      var pool = robots.filter(function (o) { return Math.random() < 0.5 ? o.p === 2 : true; });
      goTo(pool[Math.floor(Math.random() * pool.length)], true);
    });
    // find a robot
    var box_ = root.querySelector('.w-find input'), list = root.querySelector('.w-find ul'), cur = -1;
    function render() {
      var q = box_.value.trim().toLowerCase(); cur = -1;
      if (!q) { list.hidden = true; return; }
      var hits = robots.filter(function (o) { return o.n.toLowerCase().indexOf(q) >= 0 || (o.m || '').toLowerCase().indexOf(q) >= 0; })
        .sort(function (a, b) { return (a.n.toLowerCase().indexOf(q) < 0) - (b.n.toLowerCase().indexOf(q) < 0) || a.n.toLowerCase().indexOf(q) - b.n.toLowerCase().indexOf(q) || a.n.length - b.n.length; }).slice(0, 8);
      list.innerHTML = hits.map(function (o) { return '<li><button type="button" data-i="' + o.i + '">' + esc(o.n) + ' <span>' + esc([o.m, o.yr || ''].filter(Boolean).join(', ')) + '</span></button></li>'; }).join('') || '<li class="none">No robot by that name lives here yet</li>';
      list.hidden = false;
    }
    box_.addEventListener('input', render);
    box_.addEventListener('keydown', function (e) {
      var b = list.querySelectorAll('button');
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); if (!b.length) return; cur = (cur + (e.key === 'ArrowDown' ? 1 : -1) + b.length) % b.length; b.forEach(function (x, i) { x.classList.toggle('on', i === cur); }); }
      if (e.key === 'Enter' && b.length) { e.preventDefault(); (b[cur] || b[0]).click(); }
      if (e.key === 'Escape') list.hidden = true;
    });
    list.addEventListener('mousedown', function (e) { e.preventDefault(); });
    list.addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; list.hidden = true; box_.value = ''; box_.blur(); goTo(byId[b.getAttribute('data-i')], true); });
  }
})();
