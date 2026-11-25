/* =====================================================================================
   KIT v2: procedural Irish buildings, vehicles and street furniture (shared by the town
   and the industrial zone). Everything is built in metres, front facing +z, floor at y=0.
   Level 1 = mid detail (merged per tile), level 2 = full detail (one building).
   All materials use vertex colours, so a tile merges into one mesh per material.
   ===================================================================================== */
const KIT = (() => {
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  function rng(seed){ let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  let LV = 2; /* current build level */

  /* ---------- textures ---------- */
  function canvasTex(size, draw, srgb = true){ const c = document.createElement('canvas'); c.width = c.height = size; draw(c.getContext('2d'), size);
    const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; if (srgb) t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t; }
  function speckle(x, s, n, cols, r0, r1, seed){ const r = rng(seed); for (let i = 0; i < n; i++){ x.fillStyle = cols[(r() * cols.length) | 0]; const rr = r0 + r() * (r1 - r0); x.beginPath(); x.arc(r() * s, r() * s, rr, 0, 7); x.fill(); } }
  function textTex(w, h, draw){ const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t; }
  const TEX = {
    brick: canvasTex(256, (x, s) => { const r = rng(3); x.fillStyle = '#b9ad9a'; x.fillRect(0, 0, s, s); const rows = 13, bh = s / rows, bl = s / 4.4;
      for (let i = 0; i < rows; i++){ const off = (i % 2) * bl / 2; for (let j = -1; j < 6; j++){ const h = 8 + r() * 10, li = 27 + r() * 12; x.fillStyle = `hsl(${h},${45 + r() * 15}%,${li}%)`; x.fillRect(j * bl + off + 1.5, i * bh + 1.5, bl - 3, bh - 3); } }
      speckle(x, s, 1600, ['rgba(0,0,0,.08)', 'rgba(255,240,220,.06)'], .4, 1.2, 4); }),
    dash: canvasTex(256, (x, s) => { x.fillStyle = '#e6e1d6'; x.fillRect(0, 0, s, s); speckle(x, s, 9000, ['rgba(90,84,74,.33)', 'rgba(140,130,115,.4)', 'rgba(255,252,244,.55)', 'rgba(60,55,50,.22)'], .5, 1.7, 5); }),
    render: canvasTex(256, (x, s) => { x.fillStyle = '#f6f4f0'; x.fillRect(0, 0, s, s); speckle(x, s, 3000, ['rgba(0,0,0,.035)', 'rgba(255,255,255,.08)'], .5, 2.2, 6); }),
    slate: canvasTex(256, (x, s) => { const r = rng(7); x.fillStyle = '#2b3036'; x.fillRect(0, 0, s, s); const rows = 9, rh = s / rows, sw = s / 6;
      for (let i = 0; i < rows; i++){ const off = (i % 2) * sw / 2; for (let j = -1; j < 7; j++){ const l = 30 + r() * 12; x.fillStyle = `hsl(212,${6 + r() * 6}%,${l}%)`; x.fillRect(j * sw + off + 1, i * rh + 1, sw - 2, rh - 2); } } }),
    ctile: canvasTex(256, (x, s) => { const r = rng(8); x.fillStyle = '#5a5452'; x.fillRect(0, 0, s, s); const rows = 7, rh = s / rows, tw = s / 5;
      for (let i = 0; i < rows; i++) for (let j = 0; j < 5; j++){ const g = x.createLinearGradient(j * tw, 0, (j + 1) * tw, 0); const l = 52 + r() * 10; g.addColorStop(0, `hsl(0,0%,${l - 10}%)`); g.addColorStop(.5, `hsl(0,0%,${l + 8}%)`); g.addColorStop(1, `hsl(0,0%,${l - 12}%)`); x.fillStyle = g; x.fillRect(j * tw, i * rh + 2, tw, rh - 3); } }),
    stone: canvasTex(256, (x, s) => { const r = rng(9); x.fillStyle = '#5d564d'; x.fillRect(0, 0, s, s); let y = 0; while (y < s){ const h = 14 + r() * 22; let xx = -r() * 30; while (xx < s){ const w = 22 + r() * 46, l = 52 + r() * 18; x.fillStyle = `hsl(${30 + r() * 15},${8 + r() * 10}%,${l}%)`; x.fillRect(xx + 2, y + 2, w - 4, h - 4); xx += w; } y += h; } }),
    paving: canvasTex(256, (x, s) => { const r = rng(11); const n = 3, w = s / n; for (let i = 0; i < n; i++) for (let j = 0; j < n; j++){ x.fillStyle = `hsl(45,4%,${72 + r() * 7}%)`; x.fillRect(i * w, j * w, w, w); } x.strokeStyle = 'rgba(70,70,65,.5)'; x.lineWidth = 2; for (let i = 0; i <= n; i++){ x.beginPath(); x.moveTo(i * w, 0); x.lineTo(i * w, s); x.moveTo(0, i * w); x.lineTo(s, i * w); x.stroke(); } }),
    block: canvasTex(256, (x, s) => { const r = rng(13); x.fillStyle = '#6f6660'; x.fillRect(0, 0, s, s); const rows = 8, h = s / rows, l = s / 4; for (let i = 0; i < rows; i++){ const off = (i % 2) * l / 2; for (let j = -1; j < 5; j++){ x.fillStyle = `hsl(${15 + r() * 15},${12 + r() * 10}%,${40 + r() * 12}%)`; x.fillRect(j * l + off + 1.5, i * h + 1.5, l - 3, h - 3); } } }),
    tarmac: canvasTex(256, (x, s) => { x.fillStyle = '#56595d'; x.fillRect(0, 0, s, s); speckle(x, s, 14000, ['rgba(0,0,0,.18)', 'rgba(255,255,255,.07)', 'rgba(120,120,125,.25)'], .4, 1.1, 10); }),
    gravel: canvasTex(256, (x, s) => { x.fillStyle = '#a49c8d'; x.fillRect(0, 0, s, s); speckle(x, s, 7000, ['#8d8577', '#c4bcad', '#776f62', '#b5ad9d'], .8, 2.2, 15); }),
    flowers: canvasTex(256, (x, s) => { x.fillStyle = '#3e5a2a'; x.fillRect(0, 0, s, s); speckle(x, s, 900, ['#c9324a', '#f2c94c', '#9b59b6', '#ffffff', '#e67e22', '#5a7d3a'], 2, 5, 16); }),
    tiles: canvasTex(256, (x, s) => { const n = 8, w = s / n; for (let i = 0; i < n; i++) for (let j = 0; j < n; j++){ x.fillStyle = (i + j) % 2 ? '#1c1c1c' : '#e9e4d8'; x.fillRect(i * w, j * w, w, w); } }),
    rib: canvasTex(256, (x, s) => { x.fillStyle = '#ffffff'; x.fillRect(0, 0, s, s); for (let i = 0; i < 8; i++){ const g = x.createLinearGradient(i * 32, 0, i * 32 + 32, 0); g.addColorStop(0, '#d8d8d8'); g.addColorStop(.18, '#ffffff'); g.addColorStop(.35, '#bdbdbd'); g.addColorStop(.5, '#f0f0f0'); g.addColorStop(1, '#e2e2e2'); x.fillStyle = g; x.fillRect(i * 32, 0, 32, s); } }),
    concrete: canvasTex(256, (x, s) => { x.fillStyle = '#b4b2ac'; x.fillRect(0, 0, s, s); speckle(x, s, 6000, ['rgba(0,0,0,.08)', 'rgba(255,255,255,.07)'], .5, 1.6, 22); x.strokeStyle = 'rgba(60,60,58,.3)'; x.lineWidth = 2; x.strokeRect(0, 0, s, s); }),
    curtainwall: canvasTex(256, (x, s) => { x.fillStyle = '#2a3846'; x.fillRect(0, 0, s, s); x.strokeStyle = '#9aa6b0'; x.lineWidth = 5; for (let i = 0; i <= 4; i++){ x.beginPath(); x.moveTo(i * s / 4, 0); x.lineTo(i * s / 4, s); x.stroke(); } for (let j = 0; j <= 2; j++){ x.beginPath(); x.moveTo(0, j * s / 2); x.lineTo(s, j * s / 2); x.stroke(); } }),
  };

  /* ---------- materials (vertex coloured, shared) ---------- */
  const mk = (o) => new THREE.MeshStandardMaterial(Object.assign({ vertexColors: true, roughness: .9, side: THREE.DoubleSide }, o));
  const M = {
    brick: mk({ map: TEX.brick }), dash: mk({ map: TEX.dash }), render: mk({ map: TEX.render }), stone: mk({ map: TEX.stone }),
    slate: mk({ map: TEX.slate, roughness: .7 }), ctile: mk({ map: TEX.ctile }), paving: mk({ map: TEX.paving }), block: mk({ map: TEX.block }),
    tarmac: mk({ map: TEX.tarmac }), gravel: mk({ map: TEX.gravel }), flowers: mk({ map: TEX.flowers }), tiles: mk({ map: TEX.tiles }),
    clad: mk({ map: TEX.rib, roughness: .55, metalness: .25 }), concrete: mk({ map: TEX.concrete }), curtain: mk({ map: TEX.curtainwall, metalness: .5, roughness: .15 }),
    paint: mk({ roughness: .5 }), metal: mk({ metalness: .55, roughness: .4 }), shiny: mk({ metalness: .35, roughness: .3 }),
    glass: mk({ metalness: .7, roughness: .12 }), glassLit: mk({ metalness: .4, roughness: .15, emissive: 0x3b3322, emissiveIntensity: .35 }),
    plant: mk({ roughness: 1, flatShading: true }), pv: mk({ metalness: .55, roughness: .25 }),
    lamp: mk({ emissive: 0xfff2c8, emissiveIntensity: .6 }), tail: mk({ emissive: 0x7a0b0b, emissiveIntensity: .5 }),
    tyre: mk({ roughness: .85 }), water: mk({ metalness: .4, roughness: .15 }),
    trans: new THREE.MeshStandardMaterial({ color: 0xbcd0d8, metalness: .3, roughness: .05, transparent: true, opacity: .35, side: THREE.DoubleSide }),
    plume: null,
  };
  const C = (c) => new THREE.Color(c);
  const COL = { white: C(0xf4f4f1), anth: C(0x3a3f45), black: C(0x1c1d1f), sill: C(0xd9d3c6), cap: C(0xcfc8b8), hedge: C(0x2f4f26), hedgeTop: C(0x3d6330), pot: C(0xa65a3c),
    brass: C(0xc8a24a), timber: C(0x7a5a3c), timberDark: C(0x4e3826), glass: C(0x223040), glassLit: C(0x8a98a3), pv: C(0x182740), shopGreen: C(0x1d4a37),
    doorRed: C(0x8a1c26), doorBlue: C(0x1f3d63), doorGrey: C(0x40464c), doorGreen: C(0x2c5a3c), doorYellow: C(0xc9a227), steel: C(0xe1e5e8), steelDark: C(0x5d666d), red: C(0xb33a2e), yellow: C(0xe8b323) };

  /* ---------- mesh helpers: every mesh carries a tint for its vertex colours ---------- */
  function tag(m, tint){ m.userData.tint = tint ? (tint.isColor ? tint : C(tint)) : null; m.castShadow = m.receiveShadow = true; return m; }
  function box(w, h, d, mat, x = 0, y = 0, z = 0, parent, tint){ const m = tag(new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat), tint); m.position.set(x, y, z); if (parent) parent.add(m); return m; }
  function cyl(r0, r1, h, mat, seg = 12, tint){ return tag(new THREE.Mesh(new THREE.CylinderGeometry(r0, r1, h, seg), mat), tint); }
  class GB {
    constructor(){ this.p = []; this.u = []; }
    poly(pts, tile = 1){ const p0 = pts[0], a = V().subVectors(pts[1], p0), c = V().subVectors(pts[2], p0);
      const n = V().crossVectors(a, c).normalize(), e1 = a.clone().normalize(), e2 = V().crossVectors(n, e1);
      for (let i = 1; i < pts.length - 1; i++) for (const q of [pts[0], pts[i], pts[i + 1]]){ this.p.push(q.x, q.y, q.z); const d = V().subVectors(q, p0); this.u.push(d.dot(e1) / tile, d.dot(e2) / tile); }
      return this; }
    mesh(mat, tint){ const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(this.p, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(this.u, 2)); g.computeVertexNormals(); return tag(new THREE.Mesh(g, mat), tint); }
    get empty(){ return !this.p.length; }
  }
  const quad = (gb, a, b, c, d, t) => gb.poly([a, b, c, d], t);
  function surface(g, mat, x0, x1, z0, z1, gy, tile = 1, tint){ const gb = new GB(); gb.poly([V(x0, gy(x0, z1), z1), V(x1, gy(x1, z1), z1), V(x1, gy(x1, z0), z0), V(x0, gy(x0, z0), z0)], tile); const m = gb.mesh(mat, tint); m.castShadow = false; g.add(m); return m; }

  /* ---------- finalise: write vertex colours; merge by material ---------- */
  function colourise(mesh){
    let g = mesh.geometry; if (g.userData.sharedKit){ g = g.clone(); mesh.geometry = g; }
    if (!g.attributes.normal) g.computeVertexNormals();
    if (!g.attributes.uv){ const n = g.attributes.position.count; g.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(n * 2), 2)); }
    const n = g.attributes.position.count, t = mesh.userData.tint || COL.white, a = new Float32Array(n * 3);
    for (let i = 0; i < n; i++){ a[i * 3] = t.r; a[i * 3 + 1] = t.g; a[i * 3 + 2] = t.b; }
    g.setAttribute('color', new THREE.BufferAttribute(a, 3));
  }
  function finish(group){ group.traverse(o => { if (o.isMesh && !o.isInstancedMesh && o.material && o.material.vertexColors) colourise(o); }); return group; }
  /* merge many building groups (already positioned in world) into one mesh per material; ranges let a single building be hidden later */
  function mergeTile(entries){
    const byMat = new Map();
    entries.forEach(({ group, id }) => { group.updateMatrixWorld(true);
      group.traverse(o => { if (!o.isMesh || o.isInstancedMesh || Array.isArray(o.material)) return; const mat = o.material; if (!mat.vertexColors) return;
        colourise(o); let g = o.geometry.index ? o.geometry.toNonIndexed() : o.geometry.clone(); g.applyMatrix4(o.matrixWorld);
        for (const k of Object.keys(g.attributes)) if (!['position', 'normal', 'uv', 'color'].includes(k)) g.deleteAttribute(k);
        let e = byMat.get(mat); if (!e){ e = { list: [], ids: [], shadow: o.castShadow }; byMat.set(mat, e); } e.list.push(g); e.ids.push(id); }); });
    const out = [];
    for (const [mat, e] of byMat){ const ranges = new Map(); let start = 0;
      e.list.forEach((g, i) => { const n = g.attributes.position.count; const r = ranges.get(e.ids[i]); if (r) r.push([start, n]); else ranges.set(e.ids[i], [[start, n]]); start += n; });
      const merged = BufferGeometryUtils.mergeGeometries(e.list, false); e.list.forEach(g => g.dispose());
      const m = new THREE.Mesh(merged, mat); m.castShadow = e.shadow; m.receiveShadow = true; m.userData.ranges = ranges; m.userData.orig = null; out.push(m); }
    return out;
  }
  function hideInTile(meshes, id, hide){
    for (const m of meshes){ const rs = m.userData.ranges.get(id); if (!rs) continue; const pos = m.geometry.attributes.position;
      if (!m.userData.orig) m.userData.orig = pos.array.slice();
      for (const [s, n] of rs){ if (hide) pos.array.fill(0, s * 3, (s + n) * 3); else pos.array.set(m.userData.orig.subarray(s * 3, (s + n) * 3), s * 3); }
      pos.needsUpdate = true; m.geometry.computeBoundingSphere(); }
  }

  /* ---------- walls and roofs ---------- */
  function walls(F, w, d, h, tile, y0 = 0){ const W = w / 2, D = d / 2;
    F.front && F.front.poly([V(-W, y0, D), V(W, y0, D), V(W, h, D), V(-W, h, D)], tile);
    F.back && F.back.poly([V(W, y0, -D), V(-W, y0, -D), V(-W, h, -D), V(W, h, -D)], tile);
    F.left && F.left.poly([V(-W, y0, -D), V(-W, y0, D), V(-W, h, D), V(-W, h, -D)], tile);
    F.right && F.right.poly([V(W, y0, D), V(W, y0, -D), V(W, h, -D), V(W, h, D)], tile); }
  function gableEnds(gL, gR, w, d, h, rh, tile){ const W = w / 2, D = d / 2;
    gL && gL.poly([V(-W, h, -D), V(-W, h, D), V(-W, h + rh, 0)], tile); gR && gR.poly([V(W, h, D), V(W, h, -D), V(W, h + rh, 0)], tile); }
  /* roof over w x d at eave height h, rise rh; hipL/hipR = hipped ends; ogL/ogR = gable overhang (0 at party walls) */
  function roof(gb, w, d, h, rh, { o = .35, hipL = false, hipR = false, ogL = .3, ogR = .3, tile = 1.1 } = {}){
    const D = d / 2 + o, e = o * rh / (d / 2), y = h - e, top = h + rh, run = d / 2;
    const xl = hipL ? -w / 2 + run : -w / 2 - ogL, xr = hipR ? w / 2 - run : w / 2 + ogR;
    const el = hipL ? -w / 2 - o : -w / 2 - ogL, er = hipR ? w / 2 + o : w / 2 + ogR;
    const rl = Math.min(xl, (xl + xr) / 2), rr = Math.max(xr, (xl + xr) / 2);
    gb.poly([V(el, y, D), V(er, y, D), V(rr, top, 0), V(rl, top, 0)], tile);
    gb.poly([V(er, y, -D), V(el, y, -D), V(rl, top, 0), V(rr, top, 0)], tile);
    if (hipR) gb.poly([V(er, y, D), V(er, y, -D), V(rr, top, 0)], tile);
    if (hipL) gb.poly([V(el, y, -D), V(el, y, D), V(rl, top, 0)], tile);
    return { eaveY: y, D, el, er, rl, rr, top };
  }
  function eaves(g, R, fascia, gutter){ for (const s of [1, -1]){ box(R.er - R.el, .2, .05, M.paint, (R.el + R.er) / 2, R.eaveY - .06, s * R.D, g, fascia);
    if (LV < 2) continue; const gt = cyl(.07, .07, R.er - R.el, M.paint, 8, gutter); gt.rotation.z = Math.PI / 2; gt.position.set((R.el + R.er) / 2, R.eaveY - .12, s * (R.D + .07)); g.add(gt);
    const dp = cyl(.045, .045, R.eaveY - .1, M.paint, 6, gutter); dp.position.set(R.er - .45, (R.eaveY - .1) / 2, s * (R.D - .2)); g.add(dp); } }

  /* ---------- openings ---------- */
  const CURT = [0xe8dcc2, 0x9e3b3b, 0x4c6a8a, 0xd9c7a1, 0x6f7d5c].map(C);
  function windowObj({ w, h, frame = COL.white, style = 'casement', sill = COL.sill, lit = false, head = null, curtain = 0 }){
    const g = new THREE.Group(), t = .07;
    const gl = tag(new THREE.Mesh(new THREE.PlaneGeometry(w - .06, h - .06), lit ? M.glassLit : M.glass), lit ? COL.glassLit : COL.glass); gl.position.z = -.05; g.add(gl);
    box(w, t, .08, M.paint, 0, h / 2 - t / 2, 0, g, frame); box(w, t, .08, M.paint, 0, -h / 2 + t / 2, 0, g, frame);
    box(t, h, .08, M.paint, -w / 2 + t / 2, 0, 0, g, frame); box(t, h, .08, M.paint, w / 2 - t / 2, 0, 0, g, frame);
    if (sill) box(w + .16, .06, .2, M.paint, 0, -h / 2 - .03, .07, g, sill);
    if (head) box(w + .24, .2, .06, M.paint, 0, h / 2 + .1, .02, g, head);
    if (LV >= 2){
      if (style === 'casement'){ if (w > .8) box(.05, h - .1, .06, M.paint, -w / 6, 0, 0, g, frame); box(w - .1, .05, .06, M.paint, 0, h / 2 - h * .28, 0, g, frame); }
      if (style === 'sash'){ box(w - .1, .06, .07, M.paint, 0, 0, .01, g, frame); box(.03, h - .1, .05, M.paint, 0, 0, 0, g, frame); box(w - .1, .03, .05, M.paint, 0, h / 4, 0, g, frame); box(w - .1, .03, .05, M.paint, 0, -h / 4, 0, g, frame); }
      if (style === 'picture'){ box(.05, h - .1, .06, M.paint, -w / 3, 0, 0, g, frame); box(.05, h - .1, .06, M.paint, w / 3, 0, 0, g, frame); }
      for (const sx of [-1, 1]){ const c = tag(new THREE.Mesh(new THREE.PlaneGeometry(w * .18, h - .12), M.paint), CURT[curtain % 5]); c.position.set(sx * (w / 2 - w * .09 - .04), 0, -.045); g.add(c); }
    }
    g.traverse(o => { if (o.isMesh) o.castShadow = false; }); return g;
  }
  function doorObj({ w = .95, h = 2.15, col = COL.doorRed, frame = COL.white, fanlight = false, side = 0 }){
    const g = new THREE.Group();
    box(w, h, .06, M.paint, 0, h / 2, -.04, g, col);
    box(w + .14, .07, .1, M.paint, 0, h + .035, 0, g, frame); box(.07, h, .1, M.paint, -w / 2 - .035, h / 2, 0, g, frame); box(.07, h, .1, M.paint, w / 2 + .035, h / 2, 0, g, frame);
    box(w + .5, .16, .45, M.paint, 0, .08, .22, g, COL.sill);
    if (fanlight){ const fl = tag(new THREE.Mesh(new THREE.CircleGeometry(w / 2, 16, 0, Math.PI), M.glass), COL.glass); fl.position.set(0, h + .07, -.03); g.add(fl); }
    if (side){ const sp = windowObj({ w: .45, h, frame, style: 'none', sill: null }); sp.position.set(side * (w / 2 + .3), h / 2, 0); g.add(sp); }
    if (LV >= 2){ const pane = tag(new THREE.Mesh(new THREE.PlaneGeometry(w * .35, h * .3), M.glass), COL.glass); pane.position.set(0, h * .72, 0); g.add(pane);
      for (const [px, py] of [[-.2, .55], [.2, .55], [-.2, 1.15], [.2, 1.15]]) box(w * .32, .42, .02, M.paint, px * w / .95, py, 0, g, col);
      box(.04, .14, .06, M.shiny, w * .36, h * .48, .03, g, COL.brass); box(.28, .06, .03, M.shiny, 0, h * .42, .02, g, COL.brass); }
    return g;
  }
  const FACES = { front: (w, d) => ({ z: d / 2, rot: 0 }), back: (w, d) => ({ z: -d / 2, rot: Math.PI }), left: (w, d) => ({ x: -w / 2, rot: -Math.PI / 2 }), right: (w, d) => ({ x: w / 2, rot: Math.PI / 2 }) };
  function place(parent, obj, face, bw, bd, u, y){ const f = FACES[face](bw, bd);
    if (face === 'front' || face === 'back') obj.position.set(face === 'front' ? u : -u, y, f.z); else obj.position.set(f.x, y, face === 'left' ? u : -u);
    obj.rotation.y = f.rot; parent.add(obj); return obj; }
  function chimney(g, x, z, yBase, h, w, d, mat, tint, aerial = false){
    box(w, h, d, mat, x, yBase + h / 2, z, g, tint); box(w + .12, .1, d + .12, M.paint, x, yBase + h + .05, z, g, COL.sill);
    if (LV < 2) return; const n = Math.max(1, Math.round(w / .45));
    for (let i = 0; i < n; i++){ const p = cyl(.1, .12, .45, M.paint, 8, COL.pot); p.position.set(x - w / 2 + (i + .5) * w / n, yBase + h + .32, z); g.add(p); }
    if (aerial){ const m = cyl(.02, .02, 1.6, M.metal, 5, COL.steelDark); m.position.set(x + w / 2 + .05, yBase + h * .5 + .8, z); g.add(m); box(1.1, .03, .03, M.metal, x + w / 2 + .25, yBase + h * .5 + 1.4, z, g, COL.steelDark); }
  }
  function pvArray(g, cx, cz, h, rh, d, cols, rows){ const a = Math.atan(rh / (d / 2)), arr = new THREE.Group();
    if (LV < 2) box(cols * 1.05, .04, rows * 1.7, M.pv, 0, 0, 0, arr, COL.pv);
    else for (let i = 0; i < cols; i++) for (let j = 0; j < rows; j++){ const x = (i - (cols - 1) / 2) * 1.05, z = (j - (rows - 1) / 2) * 1.7; box(1.0, .04, 1.65, M.pv, x, 0, z, arr, COL.pv); box(1.02, .045, .03, M.metal, x, 0, z + .82, arr, COL.steel); }
    arr.position.set(cx, h + rh * (1 - cz / (d / 2)) + .1, cz); arr.rotation.x = a; g.add(arr); return arr; }

  /* ---------- garden ---------- */
  function lowWall(g, x0, x1, z, gy, h = .85, mat = M.render, tint = C(0xf3e6c4)){ const len = Math.abs(x1 - x0); if (len < .1) return; const y = gy((x0 + x1) / 2, z);
    box(len, h, .22, mat, (x0 + x1) / 2, y + h / 2, z, g, tint); box(len + .04, .07, .3, M.paint, (x0 + x1) / 2, y + h + .035, z, g, COL.cap); }
  function pillar(g, x, z, gy, h = 1.1, tint = C(0xf3e6c4)){ const y = gy(x, z); box(.42, h, .42, M.render, x, y + h / 2, z, g, tint); box(.5, .08, .5, M.paint, x, y + h + .04, z, g, COL.cap); }
  function hedge(g, x0, x1, z0, z1, gy, h = 1.1){ const w = Math.abs(x1 - x0) || .6, d = Math.abs(z1 - z0) || .6, y = gy((x0 + x1) / 2, (z0 + z1) / 2); box(w, h, d, M.plant, (x0 + x1) / 2, y + h / 2, (z0 + z1) / 2, g, COL.hedge); if (LV >= 2) box(w + .06, .12, d + .06, M.plant, (x0 + x1) / 2, y + h + .02, (z0 + z1) / 2, g, COL.hedgeTop); }
  function bins(g, x, z, gy, rot = 0){ if (LV < 2) return; const b = new THREE.Group(), cols = [C(0x2c6b36), C(0x5b3a22), C(0x2b2e31)];
    cols.forEach((c, i) => { box(.58, .98, .72, M.paint, i * .66, .49, 0, b, c); box(.62, .06, .78, M.paint, i * .66, 1.0, -.02, b, c); });
    b.position.set(x, gy(x, z), z); b.rotation.y = rot; g.add(b); }
  function flowerBed(g, x0, x1, z, gy, depth = .7){ if (LV < 2) return; const len = Math.abs(x1 - x0); box(len, .18, depth, M.flowers, (x0 + x1) / 2, gy((x0 + x1) / 2, z) + .09, z, g); }
  function smallTree(g, x, z, gy, s, seed, autumn){ const r = rng(seed), t = new THREE.Group(); const tr = cyl(.12 * s, .18 * s, 2.6 * s, M.paint, 6, C(0x5a4636)); tr.position.y = 1.3 * s; t.add(tr);
    for (let i = 0; i < 4; i++){ const m = tag(new THREE.Mesh(new THREE.IcosahedronGeometry((1.1 + r() * .6) * s, 1), M.plant), autumn ? C().setHSL(.06 + r() * .07, .65, .4 + r() * .1) : C().setHSL(.25 + r() * .06, .45, .25 + r() * .1));
      m.position.set((r() - .5) * 1.4 * s, (3 + r() * 1.2) * s, (r() - .5) * 1.4 * s); t.add(m); }
    t.position.set(x, gy(x, z), z); g.add(t); }

  /* ---------- the parametric house ----------
     spec: kind (semi|terrace|detached|bungalow|rural|centre|apartment|civic|nzeb), w, d, storeys, color, roofColor, flat, chimney, shop,
           pv, hp, ev, setback, seed, partyL, partyR, rh, front, big, name; ctx.gy(lx,lz) local ground height relative to floor, ctx.plinth */
  const SHOPS = ['Ó DÁLAIGH · HARDWARE', "MURPHY'S PHARMACY", 'AN CHISTIN · CAFÉ', 'Ó SÉ · BUTCHER', 'THE HARBOUR BAR', 'NEWSAGENT · POST OFFICE', 'BAILE NUA BOOKS', 'KEANE · HAIR & BEAUTY', 'FLANAGAN FOODS', 'CROWLEY · OPTICIANS', 'THE SHIP INN', 'DESMOND · FLORIST', 'Ó MURCHÚ · BAKERY', 'BAILE NUA CREDIT UNION'];
  const FASCIA = [0x1d4a37, 0x6b1f2a, 0x1f3456, 0x2b2b2b, 0x5a3a24, 0x2f5d5a].map(C);
  const DOORS = [COL.doorRed, COL.doorBlue, COL.doorGrey, COL.doorGreen, COL.doorYellow];
  function house(spec, ctx){
    const r = rng(spec.seed || 1), g = new THREE.Group(), { w, d } = spec, st = spec.storeys || 2, H = st * 2.9, gy = ctx.gy || (() => 0);
    const kind = spec.kind, tint = C(spec.color || '#efe8d8'), roofT = C(spec.roofColor || '#4a4f56');
    const nzeb = !!spec.nzeb, flat = !!spec.flat, rh = flat ? 0 : (spec.rh || Math.min(d * .36, 4.4));
    /* wall finish */
    let wallM = M.render, wallT = tint, frontM = null;
    if (kind === 'semi' || kind === 'bungalow' || (kind === 'terrace' && !spec.old)) wallM = r() < .6 ? M.dash : M.render;
    if (kind === 'terrace' && spec.old && r() < .55){ frontM = M.brick; }
    if (kind === 'detached' && r() < .3) frontM = M.stone;
    if (nzeb){ wallM = M.render; wallT = C(spec.color || '#e9e6df'); }
    if (wallM === M.dash) wallT = tint.clone().lerp(C(0xffffff), .35);
    const roofM = (kind === 'centre' || spec.old) ? M.slate : M.ctile;
    const frame = nzeb || r() < .3 ? COL.anth : COL.white;
    /* plinth to the ground */
    if (ctx.plinth > .05) box(w, ctx.plinth, d, M.render, 0, -ctx.plinth / 2, 0, g, C(0x77736c));
    /* walls */
    const fw = new GB(), ow = new GB();
    walls({ front: frontM ? fw : ow }, w, d, H, frontM === M.brick ? 1 : 1.5);
    walls({ back: ow, left: spec.partyL ? null : ow, right: spec.partyR ? null : ow }, w, d, H, 1.5);
    if (!frontM) {} else g.add(fw.mesh(frontM, frontM === M.brick ? null : null));
    /* roof */
    if (flat){ const fr = new GB(); fr.poly([V(-w / 2, H, d / 2), V(w / 2, H, d / 2), V(w / 2, H, -d / 2), V(-w / 2, H, -d / 2)], 4); g.add(fr.mesh(M.concrete, C(0x9a9c9e)));
      for (const [ww, dd, x, z] of [[w + .3, .3, 0, d / 2], [w + .3, .3, 0, -d / 2], [.3, d, -w / 2, 0], [.3, d, w / 2, 0]]) box(ww, .6, dd, wallM, x, H + .3, z, g, wallT);
      if (LV >= 2 && (kind === 'apartment' || kind === 'civic')) for (let i = 0; i < Math.min(4, Math.floor(w / 9)); i++) box(2.2, 1.2, 1.4, M.metal, -w / 2 + 4 + i * 8, H + .6, -d / 4, g, COL.steel);
    } else {
      const semiHip = kind === 'semi' && (spec.seed % 3 !== 0);
      const hipL = semiHip && !spec.partyL, hipR = semiHip && !spec.partyR, bungHip = kind === 'bungalow' && spec.seed % 4 === 0;
      const rg = new GB();
      const R = roof(rg, w, d, H, rh, { hipL: hipL || bungHip, hipR: hipR || bungHip, ogL: spec.partyL ? 0 : .3, ogR: spec.partyR ? 0 : .3 });
      g.add(rg.mesh(roofM, roofT));
      const ge = new GB(); gableEnds((spec.partyL || hipL || bungHip) ? null : ge, (spec.partyR || hipR || bungHip) ? null : ge, w, d, H, rh, 1.5);
      if (!ge.empty) g.add(ge.mesh(frontM === M.brick ? M.render : wallM, frontM === M.brick ? C(0xbab5ab) : wallT));
      eaves(g, R, kind === 'centre' || spec.old ? COL.black : COL.white, kind === 'centre' || spec.old ? COL.black : COL.anth);
      box(R.rr - R.rl + .1, .16, .2, roofM, (R.rl + R.rr) / 2, H + rh + .04, 0, g, roofT.clone().multiplyScalar(.7));
      if (spec.chimney){ const cx = spec.partyR ? w / 2 - .4 : spec.partyL ? -w / 2 + .4 : (r() < .5 ? -1 : 1) * (w / 2 - .9); chimney(g, cx, 0, H + rh - .5, 1.5, kind === 'centre' ? .9 : .7, .7, frontM === M.brick ? M.brick : wallM, frontM === M.brick ? null : wallT, r() < .35); }
      if (spec.pv) pvArray(g, 0, d / 4 + .1, H, rh, d, Math.max(2, Math.min(6, Math.floor(w * .7 / 1.05))), w > 9 ? 2 : 2);
    }
    g.add(ow.mesh(wallM, wallT));
    /* facade */
    const lit = () => r() < (spec.litP || .4); let doorX = 0;
    const sashOld = kind === 'centre' || spec.old;
    if (kind === 'centre'){
      const sf = new THREE.Group(); sf.position.z = d / 2 + .06; g.add(sf);
      if (spec.shop){ const fc = FASCIA[(spec.seed >> 3) % FASCIA.length];
        box(.35, 3.1, .14, M.paint, -w / 2 + .22, 1.55, 0, sf, fc); box(.35, 3.1, .14, M.paint, w / 2 - .22, 1.55, 0, sf, fc);
        if (LV >= 2){ const name = SHOPS[spec.seed % SHOPS.length]; const tx = textTex(1024, 128, (x, Wd, Hd) => { x.fillStyle = '#' + fc.getHexString(); x.fillRect(0, 0, Wd, Hd); x.strokeStyle = '#c9a54b'; x.lineWidth = 6; x.strokeRect(10, 10, Wd - 20, Hd - 20); x.fillStyle = '#e1c272'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.font = `700 ${Math.min(64, 1500 / name.length)}px Georgia, serif`; x.fillText(name, Wd / 2, Hd / 2 + 4); });
          const fm = new THREE.Mesh(new THREE.PlaneGeometry(w - .2, .7), new THREE.MeshStandardMaterial({ map: tx, roughness: .5 })); fm.position.set(0, 3.25, .13); sf.add(fm); }
        box(w - .1, .72, .2, M.paint, 0, 3.25, .02, sf, fc); box(w + .1, .12, .36, M.paint, 0, 3.66, .08, sf, fc);
        box(w * .62, .55, .1, M.paint, -w * .14, .28, 0, sf, fc);
        const dg = tag(new THREE.Mesh(new THREE.PlaneGeometry(w * .6, 2.2), M.glassLit), COL.glassLit); dg.position.set(-w * .14, 1.68, -.02); sf.add(dg);
        if (LV >= 2) for (const x of [-w * .44, -w * .14, w * .16]) box(.07, 2.3, .1, M.paint, x, 1.7, 0, sf, fc);
        const dr = doorObj({ w: 1.0, h: 2.5, col: fc, frame: fc }); dr.position.set(w / 2 - 1.1, 0, -.2); sf.add(dr);
      } else { place(g, doorObj({ col: DOORS[spec.seed % 5], fanlight: true }), 'front', w, d, -w / 2 + 1.1, 0); const nw = Math.max(1, Math.round((w - 2.2) / 1.9));
        for (let k = 0; k < nw; k++) place(g, windowObj({ w: 1.0, h: 1.6, style: 'sash', head: C(0xe8e0cc), lit: lit(), curtain: k }), 'front', w, d, -w / 2 + 2.2 + (k + .5) * (w - 2.2) / nw, 1.55); }
      const nw = Math.max(1, Math.round(w / 2.4));
      for (let s = 1; s < st; s++) for (let k = 0; k < nw; k++) place(g, windowObj({ w: 1.0, h: 1.55, style: 'sash', head: C(0xe8e0cc), lit: lit(), curtain: s + k }), 'front', w, d, -w / 2 + (k + .5) * w / nw, s * 2.9 + 1.55);
    } else if (kind === 'apartment' || kind === 'civic'){
      const nw = Math.max(2, Math.round(w / (spec.big ? 3.6 : 3.0)));
      for (let s = 0; s < st; s++) for (let k = 0; k < nw; k++){ if (s === 0 && k === Math.floor(nw / 2)) continue; for (const face of ['front', 'back']) place(g, windowObj({ w: Math.min(2.2, w / nw * .6), h: 1.5, frame: COL.anth, style: 'casement', lit: lit(), curtain: k }), face, w, d, -w / 2 + (k + .5) * w / nw, s * (H / st) + 1.6); }
      const ent = new THREE.Group(); place(g, ent, 'front', w, d, 0, 0);
      const dg = tag(new THREE.Mesh(new THREE.PlaneGeometry(2.6, 2.5), M.glassLit), COL.glassLit); dg.position.set(0, 1.25, .02); ent.add(dg);
      box(4.2, .25, 2.2, M.paint, 0, 2.9, 1.1, ent, COL.anth); for (const sx of [-1.9, 1.9]) box(.12, 2.9, .12, M.paint, sx, 1.45, 2.1, ent, COL.anth);
      if (LV >= 2 && spec.name){ const tx = textTex(1024, 128, (x, Wd, Hd) => { x.clearRect(0, 0, Wd, Hd); x.fillStyle = '#1d2b24'; x.font = '700 72px Overpass, Arial'; x.textAlign = 'center'; x.fillText(spec.name.toUpperCase(), Wd / 2, 92); });
        const nm = new THREE.Mesh(new THREE.PlaneGeometry(Math.min(w * .7, 12), 1.0), new THREE.MeshStandardMaterial({ map: tx, transparent: true })); nm.position.set(0, 3.6, d / 2 + .05); g.add(nm); }
    } else {
      /* dwellings: door position by type */
      const nw = Math.max(1, Math.round(w / 2.7));
      doorX = kind === 'semi' ? (spec.partyR ? -w / 2 + 1.2 : spec.partyL ? w / 2 - 1.2 : -w / 2 + 1.2) : kind === 'terrace' ? (spec.seed % 2 ? -w / 2 + 1.0 : w / 2 - 1.0) : (kind === 'bungalow' || st === 1) ? -w * .12 : w * .08;
      const style = (kind === 'bungalow' || st === 1) && r() < .5 ? 'picture' : sashOld ? 'sash' : 'casement';
      place(g, doorObj({ col: DOORS[(spec.seed >> 2) % 5], frame, fanlight: sashOld, side: kind === 'detached' && !sashOld ? 1 : 0 }), 'front', w, d, doorX, 0);
      if (!sashOld && kind !== 'terrace' && r() < .6){ const dz = d / 2 + .5; box(1.7, .12, 1.0, M.paint, doorX, 2.55, dz, g, COL.anth); }
      if (kind === 'semi' && !spec.partyL && !spec.partyR) {}
      for (let s = 0; s < st; s++){ const slots = []; for (let k = 0; k < nw; k++){ const x = -w / 2 + (k + .5) * w / nw; if (s === 0 && Math.abs(x - doorX) < 1.2) continue; slots.push(x); }
        for (const x of slots) place(g, windowObj({ w: s === 0 ? Math.min(2.2, w / nw * .7) : Math.min(1.6, w / nw * .6), h: s === 0 ? 1.35 : 1.2, frame, style: s === 0 ? style : (sashOld ? 'sash' : 'casement'), lit: lit(), curtain: k0(x) }), 'front', w, d, x, s * 2.9 + 1.45);
        for (let k = 0; k < Math.max(1, nw - 1); k++) place(g, windowObj({ w: 1.2, h: 1.1, frame, style: 'casement', lit: lit() }), 'back', w, d, -w / 2 + (k + .5) * w / Math.max(1, nw - 1), s * 2.9 + 1.5);
      }
      if (!spec.partyR && kind !== 'terrace' && st > 1) place(g, windowObj({ w: .8, h: 1.0, frame, style: 'casement' }), 'right', w, d, -1, 2.9 + 1.5);
      if (frontM === M.brick && LV >= 2) box(w, .12, .08, M.paint, 0, 2.9 + .1, d / 2 + .04, g, COL.sill);
    }
    function k0(x){ return Math.abs(Math.round(x * 3)) % 5; }
    /* heat pump, EV charger */
    const drL = spec.drive || (kind === 'semi' ? (spec.partyR ? -1 : 1) : (spec.seed % 2 ? 1 : -1));
    if (spec.hp){ if (spec.partyL && spec.partyR){ box(1.0, .8, .4, M.paint, 0, gy(0, -d / 2 - .5) + .42, -d / 2 - .5, g, COL.white); }
      else { const sx = spec.partyR ? -1 : spec.partyL ? 1 : -drL; const hp = box(1.0, .8, .4, M.paint, sx * (w / 2 + .45), gy(sx * (w / 2 + .45), -1.2) + .42, -1.2, g, COL.white); hp.rotation.y = Math.PI / 2; } }
    if (spec.ev) box(.32, .45, .14, M.paint, drL * (w / 2 - .4), 1.1, d / 2 + .09, g, COL.anth);
    /* front garden: wall line 1.85 m back from the road edge leaves room for the footpath */
    const sb = spec.setback || 0, dwell = kind !== 'centre' && kind !== 'apartment' && kind !== 'civic';
    if (sb > 3.2 && dwell){
      const bz = d / 2 + sb - 1.85, hasDrive = kind !== 'terrace' && sb >= 5.5;
      const dx0 = drL > 0 ? w / 2 - 3.2 : -w / 2, dx1 = drL > 0 ? w / 2 : -w / 2 + 3.2, gaps = [];
      if (hasDrive){ const drM = r() < .4 ? M.gravel : r() < .5 ? M.block : M.tarmac;
        surface(g, drM, dx0, dx1, d / 2, bz + .1, (x, z) => gy(x, z) + .05, drM === M.tarmac ? 4 : 1.1, drM === M.tarmac ? C(0x9a9da0) : null); gaps.push([dx0 - .05, dx1 + .05]); }
      const dx = Math.max(-w / 2 + .6, Math.min(w / 2 - .6, doorX));
      if (!hasDrive || dx < dx0 - .3 || dx > dx1 + .3){ surface(g, M.paving, dx - .5, dx + .5, d / 2 + .2, bz, (x, z) => gy(x, z) + .06, .9); gaps.push([dx - .55, dx + .55]); if (LV >= 2 && !hasDrive) for (const x of [dx - .7, dx + .7]) pillar(g, x, bz, gy); }
      gaps.sort((p, q) => p[0] - q[0]); const segs = []; let x0 = -w / 2;
      for (const [p, q] of gaps){ if (p > x0 + .1) segs.push([x0, p]); x0 = Math.max(x0, q); } if (w / 2 > x0 + .1) segs.push([x0, w / 2]);
      const wallKind = r(), useWall = kind === 'terrace' ? wallKind < .8 : wallKind < .55;
      for (const [p, q] of segs){ if (useWall) lowWall(g, p, q, bz, gy); else hedge(g, p, q, bz - .3, bz + .3, gy, 1.0); }
      /* side boundary on the side away from the drive (party line for semis and terraces) */
      const bx = kind === 'terrace' ? w / 2 : kind === 'semi' ? (spec.partyR ? w / 2 : spec.partyL ? -w / 2 : -drL * w / 2) : -drL * (w / 2 + .6);
      if (useWall) { const y = gy(bx, (d / 2 + bz) / 2); box(.22, .85, bz - d / 2, M.render, bx, y + .42, (d / 2 + bz) / 2, g, C(0xf3e6c4)); }
      else hedge(g, bx - .3, bx + .3, d / 2 + .2, bz - .2, gy, 1.2);
      flowerBed(g, drL > 0 ? -w / 2 + .3 : dx1 + .3, drL > 0 ? dx0 - .3 : w / 2 - .3, d / 2 + .5, gy);
      if (hasDrive) bins(g, drL * (w / 2 + .6), d / 2 - 2.4, gy, drL > 0 ? -Math.PI / 2 : Math.PI / 2); else bins(g, drL * (w / 2 - .45), d / 2 + 1.0, gy, drL > 0 ? -Math.PI / 2 : Math.PI / 2);
      if (LV >= 2 && sb > 7 && r() < .5) smallTree(g, -drL * (w / 2 - 1.3), d / 2 + sb * .55, gy, .55, spec.seed, r() < .5);
    } else if (kind === 'terrace' && sb > 1.2 && LV >= 2 && spec.old){
      const bz = d / 2 + sb - .2; box(w, .5, .22, M.render, 0, gy(0, bz) + .25, bz, g, C(0xbab5ab));
    }
    return finish(g);
  }

  /* ---------- non-residential sheds and blocks (for the enterprise estate and industrial zone) ---------- */
  function wallsAt(g, mat, tint, x, z, w, d, h, tile = 3, y0 = 0){ const gb = new GB(), W = w / 2, D = d / 2;
    gb.poly([V(x - W, y0, z + D), V(x + W, y0, z + D), V(x + W, h, z + D), V(x - W, h, z + D)], tile); gb.poly([V(x + W, y0, z - D), V(x - W, y0, z - D), V(x - W, h, z - D), V(x + W, h, z - D)], tile);
    gb.poly([V(x - W, y0, z - D), V(x - W, y0, z + D), V(x - W, h, z + D), V(x - W, h, z - D)], tile); gb.poly([V(x + W, y0, z + D), V(x + W, y0, z - D), V(x + W, h, z - D), V(x + W, h, z + D)], tile); g.add(gb.mesh(mat, tint)); }
  function shed(g, x, z, w, d, h, tint, { rise = .08, lights = true } = {}){
    wallsAt(g, M.clad, tint, x, z, w, d, h, 3, -1);
    const rg = new GB(), rh = d / 2 * rise, o = .4;
    rg.poly([V(x - w / 2 - o, h, z + d / 2 + o), V(x + w / 2 + o, h, z + d / 2 + o), V(x + w / 2 + o, h + rh, z), V(x - w / 2 - o, h + rh, z)], 3); rg.poly([V(x + w / 2 + o, h, z - d / 2 - o), V(x - w / 2 - o, h, z - d / 2 - o), V(x - w / 2 - o, h + rh, z), V(x + w / 2 + o, h + rh, z)], 3);
    const ge = new GB(); ge.poly([V(x - w / 2, h, z - d / 2), V(x - w / 2, h, z + d / 2), V(x - w / 2, h + rh, z)], 3); ge.poly([V(x + w / 2, h, z + d / 2), V(x + w / 2, h, z - d / 2), V(x + w / 2, h + rh, z)], 3);
    g.add(rg.mesh(M.clad, C(0x9ea6aa)), ge.mesh(M.clad, tint));
    if (lights) for (let xi = x - w / 2 + 4; xi < x + w / 2 - 3; xi += 7) for (const s of [-1, 1]){ const rl = box(1.4, .05, d * .3, M.paint, xi, h + rh * .55 + .06, z + s * d * .25, g, C(0xc5d0d6)); rl.rotation.x = -s * Math.atan(rise); rl.castShadow = false; }
    box(w + .2, .25, .25, M.paint, x, .12, z + d / 2 + .05, g, COL.anth);
  }
  function flatBlock(g, x, z, w, d, h, mat, tint, { bands = 0, glazed = false } = {}){
    wallsAt(g, mat, tint, x, z, w, d, h, 3, -1);
    const fr = new GB(); fr.poly([V(x - w / 2, h, z + d / 2), V(x + w / 2, h, z + d / 2), V(x + w / 2, h, z - d / 2), V(x - w / 2, h, z - d / 2)], 4); g.add(fr.mesh(M.concrete, C(0x9a9c9e)));
    box(w + .3, .6, .3, mat, x, h + .3, z + d / 2, g, tint); box(w + .3, .6, .3, mat, x, h + .3, z - d / 2, g, tint); box(.3, .6, d, mat, x - w / 2, h + .3, z, g, tint); box(.3, .6, d, mat, x + w / 2, h + .3, z, g, tint);
    for (let i = 0; i < bands; i++){ const y = 2.2 + i * (h - 2) / bands; for (const s of [1, -1]){ const p = tag(new THREE.Mesh(new THREE.PlaneGeometry(w - 1.2, 1.3), M.glass), COL.glass); p.position.set(x, y, z + s * (d / 2 + .02)); if (s < 0) p.rotation.y = Math.PI; g.add(p); } }
    if (glazed){ const cw = new GB(); cw.poly([V(x - w / 2 + 1, .2, z + d / 2 + .05), V(x + w / 2 - 1, .2, z + d / 2 + .05), V(x + w / 2 - 1, h - .5, z + d / 2 + .05), V(x - w / 2 + 1, h - .5, z + d / 2 + .05)], 3); const m = cw.mesh(M.curtain); m.castShadow = false; g.add(m); }
  }
  function tank(g, x, z, r, h, tint, { cone = true, ladder = true } = {}){
    const t = cyl(r, r, h, M.shiny, 24, tint); t.position.set(x, h / 2, z); g.add(t);
    if (cone){ const c = tag(new THREE.Mesh(new THREE.ConeGeometry(r * 1.02, r * .35, 24), M.shiny), tint); c.position.set(x, h + r * .175, z); g.add(c); }
    if (LV >= 2){ if (ladder) box(.5, h, .06, M.metal, x, h / 2, z + r + .25, g, COL.steelDark);
      for (const y of [h * .33, h * .66]){ const rr = tag(new THREE.Mesh(new THREE.TorusGeometry(r + .02, .05, 4, 24), M.metal), COL.steelDark); rr.rotation.x = Math.PI / 2; rr.position.set(x, y, z); g.add(rr); } }
  }
  function stack(g, x, z, r, h){ const s = cyl(r * .8, r, h, M.metal, 14, COL.steelDark); s.position.set(x, h / 2, z); g.add(s); for (const y of [h - 1, h - 3]){ const b = cyl(r * .82, r * .82, .5, M.paint, 14, COL.red); b.position.set(x, y, z); g.add(b); } return V(x, h, z); }
  function pipeRack(g, x0, z0, x1, z1, y){ const L = Math.hypot(x1 - x0, z1 - z0), ang = Math.atan2(z1 - z0, x1 - x0), grp = new THREE.Group(); grp.position.set(x0, 0, z0); grp.rotation.y = -ang; g.add(grp);
    for (let s = 0; s <= L; s += 6){ box(.25, y, .25, M.metal, s, y / 2, -1, grp, COL.steelDark); box(.25, y, .25, M.metal, s, y / 2, 1, grp, COL.steelDark); box(.2, .2, 2.3, M.metal, s, y, 0, grp, COL.steelDark); }
    [0xd2d7db, 0x2d5e8f, 0x3e7a4a, 0xe8b323].forEach((c, i) => { const p = cyl(.16, .16, L, M.shiny, 8, C(c)); p.rotation.z = Math.PI / 2; p.position.set(L / 2, y + .3, -.75 + i * .5); grp.add(p); }); }
  function dockDoors(g, x, z, n, face){ for (let i = 0; i < n; i++){ const dx = x + (i - (n - 1) / 2) * 4.5;
    box(3.2, 3.4, .1, M.paint, dx, 2.9, z + face * .06, g, COL.anth); box(3.6, .25, .2, M.paint, dx, 4.7, z + face * .1, g, COL.yellow); if (LV >= 2) box(3.2, .15, 2.2, M.metal, dx, 1.15, z + face * 1.1, g, COL.steelDark); } }

  /* ---------- vehicles ---------- */
  const PLATE = textTex(320, 72, (x, W, H) => { x.fillStyle = '#ffffff'; x.fillRect(0, 0, W, H); x.fillStyle = '#1d3f9c'; x.fillRect(0, 0, 40, H);
    x.fillStyle = '#ffd23c'; for (let i = 0; i < 12; i++){ const a = i / 12 * Math.PI * 2; x.beginPath(); x.arc(20 + Math.cos(a) * 10, 24 + Math.sin(a) * 10, 1.8, 0, 7); x.fill(); }
    x.font = '700 15px Arial'; x.textAlign = 'center'; x.fillText('IRL', 20, 60); x.fillStyle = '#111'; x.font = '600 11px Arial'; x.fillText('CORCAIGH', 180, 16); x.font = '700 40px Arial'; x.fillText('231-C-4417', 180, 58); x.strokeStyle = '#111'; x.lineWidth = 3; x.strokeRect(1.5, 1.5, W - 3, H - 3); });
  const plateMat = mk({ map: PLATE, roughness: .4 });
  const CARS = {
    hatch: { top: [[0, .32], [0, .86], [.22, 1.04], [.62, 1.45], [2.3, 1.48], [2.95, 1.0], [3.88, .9], [4.1, .72], [4.1, .32]], wheels: [.8, 3.3], r: .33, win: [[.42, 1.06], [.72, 1.38], [2.24, 1.4], [2.78, 1.03]], front: [[2.3, 1.48], [2.95, 1.0]], rear: [[.22, 1.04], [.62, 1.45]], width: 1.66 },
    saloon: { top: [[0, .34], [0, .8], [.15, .95], [.95, 1.0], [1.35, 1.4], [2.75, 1.42], [3.35, 1.0], [4.35, .88], [4.6, .7], [4.6, .34]], wheels: [.95, 3.7], r: .33, win: [[1.15, 1.02], [1.42, 1.34], [2.7, 1.36], [3.22, 1.02]], front: [[2.75, 1.42], [3.35, 1.0]], rear: [[.95, 1.0], [1.35, 1.4]], width: 1.72 },
    suv: { top: [[0, .45], [0, 1.05], [.12, 1.62], [2.55, 1.68], [3.1, 1.16], [4.2, 1.04], [4.45, .82], [4.45, .45]], wheels: [.9, 3.55], r: .38, win: [[.3, 1.18], [.36, 1.56], [2.5, 1.6], [2.98, 1.18]], front: [[2.55, 1.68], [3.1, 1.16]], rear: [[0, 1.08], [.12, 1.62]], width: 1.82 },
    van: { top: [[0, .38], [0, 2.32], [3.55, 2.36], [4.3, 1.55], [5.1, 1.1], [5.35, .85], [5.35, .38]], wheels: [1.0, 4.35], r: .37, win: [[3.5, 1.6], [3.52, 2.18], [4.18, 1.62]], front: [[3.55, 2.36], [4.3, 1.55]], rear: null, width: 1.95 },
  };
  function wheel(p, x, y, z, r, w = .24){ const t = cyl(r, r, w, M.tyre, 18, C(0x18191b)); t.rotation.x = Math.PI / 2; t.position.set(x, y, z); p.add(t); const h = cyl(r * .58, r * .58, w + .01, M.metal, 12, C(0xb8bec4)); h.rotation.x = Math.PI / 2; h.position.set(x, y, z); p.add(h); }
  /* paint parts use tint 'PAINT' (white) and are recoloured per instance */
  const PAINT = C(0xffffff);
  function car(kind = 'hatch'){
    const T = CARS[kind], g = new THREE.Group(), inner = new THREE.Group(); g.add(inner);
    const s = new THREE.Shape(), y0 = T.top[0][1], L = T.top[T.top.length - 1][0], ar = T.r + .04;
    s.moveTo(...T.top[0]); for (const p of T.top.slice(1)) s.lineTo(...p);
    s.lineTo(T.wheels[1] + ar, y0); s.absarc(T.wheels[1], y0, ar, 0, Math.PI, false); s.lineTo(T.wheels[0] + ar, y0); s.absarc(T.wheels[0], y0, ar, 0, Math.PI, false); s.lineTo(0, y0);
    const body = tag(new THREE.Mesh(new THREE.ExtrudeGeometry(s, { depth: T.width, bevelEnabled: true, bevelThickness: .06, bevelSize: .05, bevelSegments: 2, curveSegments: 6 }), M.paint), PAINT); body.userData.paint = true; inner.add(body);
    const win = tag(new THREE.Mesh(new THREE.ExtrudeGeometry(new THREE.Shape(T.win.map(p => new THREE.Vector2(...p))), { depth: T.width + .14, bevelEnabled: false }), M.glass), COL.glass); win.position.z = -.07; inner.add(win);
    const pane = (P, Q) => { const dx = Q[0] - P[0], dy = Q[1] - P[1], len = Math.hypot(dx, dy), phi = Math.atan2(dy, dx); const pg = new THREE.PlaneGeometry(len * .92, T.width - .18); pg.rotateX(-Math.PI / 2);
      const m = tag(new THREE.Mesh(pg, M.glass), COL.glass); m.rotation.z = phi; m.position.set((P[0] + Q[0]) / 2 - Math.sin(phi) * .012, (P[1] + Q[1]) / 2 + Math.cos(phi) * .012, T.width / 2); inner.add(m); };
    pane(T.front[0], T.front[1]); if (T.rear) pane(T.rear[0], T.rear[1]);
    for (const x of T.wheels) for (const z of [-.02, T.width + .02]) wheel(inner, x, T.r, z, T.r);
    const fy = T.top[T.top.length - 2][1] - .1;
    box(.05, .14, .32, M.lamp, L + .02, fy, .2, inner, C(0xffffff)); box(.05, .14, .32, M.lamp, L + .02, fy, T.width - .2, inner, C(0xffffff));
    box(.05, .16, .3, M.tail, -.03, y0 + .45, .2, inner, C(0x9b1111)); box(.05, .16, .3, M.tail, -.03, y0 + .45, T.width - .2, inner, C(0x9b1111));
    box(.06, .14, T.width - .1, M.paint, L + .03, y0 + .12, T.width / 2, inner, COL.anth); box(.06, .14, T.width - .1, M.paint, -.04, y0 + .12, T.width / 2, inner, COL.anth);
    for (const [x, ry] of [[L + .065, Math.PI / 2], [-.075, -Math.PI / 2]]){ const p = tag(new THREE.Mesh(new THREE.PlaneGeometry(.52, .117), plateMat), C(0xffffff)); p.rotation.y = ry; p.position.set(x, y0 + .3, T.width / 2); inner.add(p); }
    inner.position.set(-L / 2, 0, -T.width / 2); g.userData.len = L; return finish(g);
  }
  function bus(){
    const g = new THREE.Group(), L = 12, W = 2.55, H = 3.15, y0 = .32;
    const b = box(L, H - y0, W, M.shiny, 0, y0 + (H - y0) / 2, 0, g, C(0xf4f4f0)); b.userData.paint = false;
    box(L + .02, .6, W + .02, M.paint, 0, y0 + .3, 0, g, C(0x1f3456)); box(L + .02, .1, W + .02, M.paint, 0, y0 + .66, 0, g, C(0xd9a52e));
    box(L - 1.3, 1.1, W + .03, M.glass, -.45, y0 + 1.75, 0, g, COL.glass); box(.06, 1.75, W - .2, M.glass, L / 2 + .01, y0 + 1.55, 0, g, COL.glass);
    box(3.2, .3, 1.7, M.shiny, -1.5, H + .15, 0, g, C(0xf4f4f0)); box(.04, .3, 2.0, M.lamp, L / 2 + .04, H - .28, 0, g, C(0xffb21e));
    for (const x of [L / 2 - 2.5, -L / 2 + 3.1]) for (const z of [-W / 2 + .12, W / 2 - .12]) wheel(g, x, .5, z, .5, .3);
    box(.06, .16, .7, M.lamp, L / 2 + .02, y0 + .55, -.85, g, C(0xffffff)); box(.06, .16, .7, M.lamp, L / 2 + .02, y0 + .55, .85, g, C(0xffffff));
    g.userData.len = L; return finish(g);
  }
  function lorry(paint = 0x1d4a37){
    const g = new THREE.Group(), L = 9.6, W = 2.5;
    const cab = box(2.1, 2.55, W, M.shiny, L / 2 - 1.05, 1.95, 0, g, C(0xf0efea)); box(.05, 1.0, W - .3, M.glass, L / 2 + .01, 2.55, 0, g, COL.glass);
    box(L, .3, 1.1, M.paint, 0, .75, 0, g, COL.black);
    const cg = box(7.0, 2.9, W, M.paint, -L / 2 + 3.5, 2.4, 0, g, PAINT); cg.userData.paint = true;
    for (const x of [L / 2 - 1.3, -L / 2 + 1.6, -L / 2 + 2.9]) for (const z of [-W / 2 + .14, W / 2 - .14]) wheel(g, x, .52, z, .52, .32);
    box(.06, .2, .4, M.lamp, L / 2 + .03, 1.2, -.95, g, C(0xffffff)); box(.06, .2, .4, M.lamp, L / 2 + .03, 1.2, .95, g, C(0xffffff));
    g.userData.len = L; return finish(g);
  }
  function artic(tanker = false){
    const g = new THREE.Group(), W = 2.5;
    box(2.3, 2.9, W, M.paint, 6.4, 2.1, 0, g, PAINT).userData.paint = true; box(.05, 1.1, W - .3, M.glass, 7.56, 2.75, 0, g, COL.glass); box(2.3, .5, W - .2, M.paint, 6.2, 3.8, 0, g, PAINT).userData.paint = true;
    box(14.5, .35, 1.1, M.paint, -1, .85, 0, g, COL.black);
    for (const x of [6.8, 4.8]) for (const z of [-W / 2 + .14, W / 2 - .14]) wheel(g, x, .52, z, .52, .3);
    for (const x of [-5.6, -6.9, -8.2]) for (const z of [-W / 2 + .14, W / 2 - .14]) wheel(g, x, .5, z, .5, .3);
    if (tanker){ const t = cyl(1.15, 1.15, 11.5, M.shiny, 24, COL.steel); t.rotation.z = Math.PI / 2; t.position.set(-1.8, 2.35, 0); g.add(t); }
    else box(13.4, 2.8, W, M.paint, -2.0, 2.65, 0, g, C(0xe9ecef));
    box(.06, .2, .4, M.lamp, 7.62, 1.25, -.95, g, C(0xffffff)); box(.06, .2, .4, M.lamp, 7.62, 1.25, .95, g, C(0xffffff));
    g.children.forEach(c => c.position.x -= .6); g.userData.len = 16.5; return finish(g);
  }
  /* turn a vehicle group into instancable parts: [{geometry, material, paint}] in vehicle space */
  function parts(group){
    group.updateMatrixWorld(true); const map = new Map();
    group.traverse(o => { if (!o.isMesh) return; const key = o.material.uuid + (o.userData.paint ? 'P' : ''); let g = o.geometry.index ? o.geometry.toNonIndexed() : o.geometry.clone(); g.applyMatrix4(o.matrixWorld);
      for (const k of Object.keys(g.attributes)) if (!['position', 'normal', 'uv', 'color'].includes(k)) g.deleteAttribute(k);
      let e = map.get(key); if (!e){ e = { mat: o.material, paint: !!o.userData.paint, list: [] }; map.set(key, e); } e.list.push(g); });
    return [...map.values()].map(e => ({ geometry: BufferGeometryUtils.mergeGeometries(e.list, false), material: e.paint ? mk({ roughness: .32, metalness: .45 }) : e.mat, paint: e.paint }));
  }

  /* ---------- street furniture as single geometries for instancing ---------- */
  function lampGeo(){ const g = new THREE.Group(); const p = cyl(.07, .1, 6, M.metal, 8, C(0x8d949a)); p.position.y = 3; g.add(p); box(.9, .07, .07, M.metal, .42, 5.95, 0, g, C(0x8d949a)); box(.55, .14, .26, M.paint, .9, 5.9, 0, g, COL.anth); finish(g); return parts(g); }
  function lampHeadGeo(){ const g = new THREE.PlaneGeometry(.45, .2); g.rotateX(Math.PI / 2); g.translate(.9, 5.82, 0); return g; }
  function poleGeo(h = 10.5, arm = 2.8){ const g = new THREE.Group(); const p = cyl(.13, .17, h, M.paint, 8, C(0x5b4532)); p.position.y = h / 2; g.add(p); box(arm, .12, .12, M.paint, 0, h - .35, 0, g, C(0x5b4532));
    for (const dx of [-arm / 2 + .12, 0, arm / 2 - .12]){ const ins = cyl(.05, .06, .22, M.paint, 6, COL.white); ins.position.set(dx, h - .17, 0); g.add(ins); } finish(g); return parts(g); }
  function treeGeo(seed = 1, lumps = 4, detail = 1){ const r = rng(seed), list = []; for (let i = 0; i < lumps; i++){ const ge = new THREE.IcosahedronGeometry(.62 + r() * .3, detail); ge.translate((r() - .5) * .8, 1.45 + r() * .55, (r() - .5) * .8); list.push(ge.index ? ge.toNonIndexed() : ge); }
    const m = BufferGeometryUtils.mergeGeometries(list, false); m.computeVertexNormals(); return m; }

  return { V, rng, TEX, M, COL, C, GB, box, cyl, surface, finish, mergeTile, hideInTile, house, shed, flatBlock, tank, stack, pipeRack, dockDoors, wallsAt,
    car, bus, lorry, artic, parts, lampGeo, lampHeadGeo, poleGeo, treeGeo, textTex, windowObj, doorObj, smallTree, hedge, lowWall, pillar, setLevel: (l) => { LV = l; }, get level(){ return LV; } };
})();
