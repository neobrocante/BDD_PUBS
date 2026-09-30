'use strict';
/* BDD Pubs : interface web (aucune dépendance externe). */

// ===========================================================================
// Outils
// ===========================================================================
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ESC[c]);
const norm = s => String(s ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
const MARU = '○', BATSU = '×';
const TOUCH = matchMedia('(pointer: coarse)').matches;

function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}

function debounce(fn, ms = 250) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

function qs(obj) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(obj)) if (v !== '' && v != null) p.set(k, v);
  return p.toString();
}

const fmtPages = n => n == null || n === '' ? '' : String(n).replace('.', ',');
const plural = (n, s, p) => `${n} ${n > 1 ? (p || s + 's') : s}`;
const imgSrc = im => im.thumb_url || im.url;
const thumbImg = (url, cls = 'thumb-img') => url
  ? `<img class="${cls}" loading="lazy" src="${esc(url)}" alt="">`
  : `<div class="thumb-none" title="Pas d'image">▢</div>`;
const saleBtn = v => `<button type="button" class="sale ${v ? 'on' : 'off'}" data-act="sale" title="En vente : cliquer pour changer">${v ? MARU : BATSU}</button>`;
const adLabel = a => `#${a.id} · ${a.game_title}${a.platform_name ? ' · ' + a.platform_name : ''}${a.description ? ' — ' + a.description : ''}`;

// ===========================================================================
// API
// ===========================================================================
// Projet de cet onglet : /p/<id>/ dans l'adresse ; « / » = projet ouvert au lancement.
const PROJ = (location.pathname.match(/^\/p\/([a-z0-9-]+)/) || [])[1] || '';
const withProj = url => PROJ ? url + (url.includes('?') ? '&' : '?') + 'projet=' + encodeURIComponent(PROJ) : url;

async function api(method, url, body) {
  const opt = { method, headers: {} };
  if (PROJ) opt.headers['X-Projet'] = PROJ;
  if (body !== undefined) {
    opt.headers['Content-Type'] = 'application/json';
    opt.body = JSON.stringify(body);
  }
  const r = await fetch('/api/' + url, opt);
  let data = null;
  try { data = await r.json(); } catch (_) { /* pas de JSON */ }
  if (!r.ok) throw new Error((data && data.error) || `Erreur ${r.status}`);
  return data;
}
const GET = u => api('GET', u);
const POST = (u, b) => api('POST', u, b);
const PUT = (u, b) => api('PUT', u, b);
const DEL = u => api('DELETE', u);

// Petites listes gardées en mémoire, rechargées après chaque modification
const cache = {};
function invalidate() { for (const k of Object.keys(cache)) delete cache[k]; }
async function cached(key, loader) {
  if (!cache[key]) cache[key] = loader().catch(e => { delete cache[key]; throw e; });
  return cache[key];
}
const getMeta = () => cached('meta', () => GET('meta'));
const getGames = () => cached('games', () => GET('games'));
const getAds = () => cached('ads', () => GET('ads'));

// ===========================================================================
// Notifications, modales, confirmation
// ===========================================================================
function toast(msg, kind = 'ok') {
  const t = el('div', 'toast' + (kind === 'err' ? ' err' : ''));
  t.textContent = msg;
  $('#toasts').append(t);
  setTimeout(() => t.remove(), kind === 'err' ? 6000 : 2800);
}
window.addEventListener('unhandledrejection', e => toast(e.reason?.message || String(e.reason), 'err'));

const overlays = [];
function openModal(title, body, { wide = false, onClose } = {}) {
  const ov = el('div', 'overlay');
  ov.innerHTML = `<div class="modal ${wide ? 'wide' : ''}" role="dialog" aria-modal="true">
      <header><h2></h2><button type="button" class="icon" data-close title="Fermer (Échap)">✕</button></header>
      <div class="modal-body"></div></div>`;
  $('h2', ov).textContent = title;
  $('.modal-body', ov).append(body);
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    ov.remove();
    overlays.splice(overlays.indexOf(ov), 1);
    onClose && onClose();
  };
  ov._close = close;
  $('[data-close]', ov).addEventListener('click', close);
  document.body.append(ov);
  overlays.push(ov);
  return { el: ov, close };
}
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  if ($('.lightbox')) { $('.lightbox').remove(); return; }
  const top = overlays[overlays.length - 1];
  if (top) { e.preventDefault(); top._close(); }
});

function confirmBox(msg, okLabel = 'Supprimer') {
  return new Promise(resolve => {
    const body = el('div', null, `<p style="margin-top:0">${esc(msg)}</p>
      <div class="actions"><button type="button" data-no>Annuler</button>
      <button type="button" class="primary" data-yes>${esc(okLabel)}</button></div>`);
    let answered = false;
    const m = openModal('Confirmer', body, { onClose: () => { if (!answered) resolve(false); } });
    $('[data-no]', body).onclick = () => m.close();
    $('[data-yes]', body).onclick = () => { answered = true; m.close(); resolve(true); };
    setTimeout(() => $('[data-yes]', body).focus(), 20);
  });
}

// ===========================================================================
// Liste déroulante avec recherche (« combo ») + création à la volée
// ===========================================================================
function combo(opts) {
  const { source, label, render, extra, placeholder = '', onCreate, onChange = () => {} } = opts;
  const matchKeys = opts.match || (it => [label(it)]); // textes qui désignent exactement cet élément
  const createText = opts.createText || (t => `＋ Créer « ${t} »`);
  const wrap = el('div', 'combo', '<input type="text" autocomplete="off" spellcheck="false"><ul class="combo-list" hidden></ul>');
  const input = $('input', wrap), list = $('ul', wrap);
  input.placeholder = placeholder;
  let items = null, selected = null, shown = [], active = -1;

  const ensure = async force => { if (!items || force) items = await source(); return items; };
  const opts$ = () => $$('li[data-i],li[data-create]', list);
  const close = () => { list.hidden = true; active = -1; };

  let openSeq = 0;
  async function open() {
    const seq = ++openSeq;
    await ensure();
    if (seq !== openSeq) return; // une frappe plus récente a déjà relancé l'affichage
    const txt = input.value.trim();
    const words = norm(txt).split(/\s+/).filter(Boolean);
    const showAll = (selected && input.value === label(selected)) || !words.length;
    const q = norm(txt);
    const rank = it => {
      const l = norm(label(it));
      if (l.startsWith(q)) return 0;
      const starts = l.split(/[\s\-:·/()]+/);
      if (words.every(w => starts.some(x => x.startsWith(w)))) return 1;
      return 2;
    };
    shown = showAll ? items.slice(0, 300)
      : items.filter(it => {
        const t = norm(label(it) + ' ' + (extra ? extra(it) : ''));
        return words.every(w => t.includes(w));
      }).map((it, i) => [rank(it), i, it]).sort((a, b) => a[0] - b[0] || a[1] - b[1]).map(x => x[2]).slice(0, 150);
    const lis = shown.map((it, i) =>
      `<li data-i="${i}" class="${selected && it.id === selected.id ? 'sel' : ''}">${render ? render(it) : esc(label(it))}</li>`);
    const canCreate = onCreate && txt && !showAll && !items.some(it => norm(label(it)) === norm(txt));
    if (canCreate) lis.push(`<li data-create="1" class="create">${esc(createText(txt))}</li>`);
    if (!lis.length) lis.push('<li class="empty">Aucun résultat</li>');
    list.innerHTML = lis.join('');
    list.hidden = false;
    active = !showAll && (shown.length || canCreate) ? 0 : -1;
    highlight();
  }
  function highlight() {
    opts$().forEach((li, i) => li.classList.toggle('active', i === active));
    const a = opts$()[active];
    if (a) a.scrollIntoView({ block: 'nearest' });
  }
  function setItem(it, silent) {
    selected = it || null;
    input.value = it ? label(it) : '';
    wrap.classList.remove('invalid');
    if (!silent) onChange(selected);
  }
  async function choose(idx) {
    const li = opts$()[idx];
    if (!li) return;
    close();
    if (li.dataset.create) {
      const created = await onCreate(input.value.trim());
      if (created) { await ensure(true); setItem(items.find(x => x.id === created.id) || created); }
      if (!TOUCH) input.focus();
      return;
    }
    setItem(shown[+li.dataset.i]);
  }

  input.addEventListener('focus', () => { input.select(); ensure(); });
  input.addEventListener('mousedown', () => { if (list.hidden) open(); });
  input.addEventListener('input', () => {
    // Les claviers de téléphone renvoient parfois le texte déjà présent : on ne désélectionne
    // que si le texte a vraiment changé.
    if (selected && input.value !== label(selected)) { selected = null; onChange(null); }
    open();
  });
  input.addEventListener('keydown', e => {
    const n = opts$().length;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (list.hidden) open(); else { active = Math.min(n - 1, active + 1); highlight(); }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault(); active = Math.max(0, active - 1); highlight();
    } else if (e.key === 'Enter') {
      if (!list.hidden && active >= 0) { e.preventDefault(); e.stopPropagation(); choose(active); }
      else if (!selected && input.value.trim()) {
        // texte tapé mais liste pas encore affichée : on attend la liste puis on prend le 1er résultat
        e.preventDefault(); e.stopPropagation();
        open().then(() => { if (active >= 0) choose(active); });
      }
    } else if (e.key === 'Tab') {
      const li = opts$()[active];
      if (!list.hidden && li && !li.dataset.create && !selected) choose(active);
      close();
    } else if (e.key === 'Escape') {
      if (!list.hidden) { e.stopPropagation(); close(); }
    }
  });
  // mousedown : garder le focus dans le champ ; le choix se fait au « click » (doigt relevé),
  // sinon sur écran tactile le relâchement tombe sur la fenêtre qui vient de s'ouvrir.
  list.addEventListener('mousedown', e => { e.preventDefault(); });
  list.addEventListener('click', e => {
    const li = e.target.closest('li[data-i],li[data-create]');
    if (!li) return;
    e.preventDefault();
    choose(opts$().indexOf(li));
  });
  input.addEventListener('blur', () => setTimeout(() => {
    if (document.activeElement === input) return;
    close();
    wrap.classList.toggle('invalid', !selected && !!input.value.trim());
  }, 150));

  const c = {
    el: wrap, input,
    /* Texte tapé sans choisir dans la liste : s'il désigne exactement un élément, on le retient. */
    resolve() {
      if (selected || !items) return selected ? selected.id : null;
      const t = norm(input.value.trim());
      if (!t) return null;
      const hits = items.filter(it => matchKeys(it).some(k => norm(k).trim() === t));
      if (hits.length === 1) { setItem(hits[0]); return hits[0].id; }
      return null;
    },
    get text() { return input.value.trim(); },
    get value() { return selected ? selected.id : null; },
    get item() { return selected; },
    async set(id, silent) { await ensure(); setItem(items.find(it => it.id === id) || null, silent); },
    setItem, clear() { setItem(null); },
    async reload() { await ensure(true); if (selected) setItem(items.find(it => it.id === selected.id) || null, true); },
    focus() { input.focus(); },
  };
  if (opts.value != null) c.set(opts.value, true);
  return c;
}

// Combos prêts à l'emploi --------------------------------------------------
function magazineCombo(extraOpts = {}) {
  return combo({
    source: async () => (await getMeta()).magazines,
    label: m => m.name,
    placeholder: 'Famitsu, Dengeki…',
    onCreate: async name => {
      const m = await POST('magazines', { name });
      invalidate();
      toast(`Magazine « ${m.name} » créé`);
      return m;
    },
    ...extraOpts,
  });
}

function seriesCombo(extraOpts = {}) {
  return combo({
    source: async () => (await getMeta()).series,
    label: s => s.name,
    placeholder: 'Aucune',
    onCreate: async name => {
      const s = await POST('series', { name });
      invalidate();
      toast(`Série « ${s.name} » créée`);
      return s;
    },
    ...extraOpts,
  });
}

function gameCombo(extraOpts = {}) {
  return combo({
    source: getGames,
    label: g => g.title,
    match: g => [g.title, g.original_title].filter(Boolean),
    extra: g => g.original_title,
    render: g => `<span style="flex:1">${esc(g.title)}</span><span class="opt-sub">${g.ads_count ? plural(g.ads_count, 'pub') : 'nouveau'}</span>`,
    placeholder: 'Tapez le titre…',
    onCreate: title => openGameForm({ title }),
    createText: t => `＋ Nouveau jeu « ${t} »`,
    ...extraOpts,
  });
}

function adCombo(extraOpts = {}) {
  return combo({
    source: getAds,
    label: adLabel,
    match: a => [adLabel(a), `#${a.id}`, String(a.id)],
    extra: a => `${a.original_title} ${a.series_name || ''} ${a.notes}`,
    render: a => `${a.thumb_url ? `<img class="opt-thumb" src="${esc(a.thumb_url)}" alt="">` : '<span class="opt-thumb"></span>'}
        <div><b>#${a.id}</b> ${esc(a.game_title)} <span class="opt-sub">${esc(a.platform_name || '')}</span>
        <div class="opt-sub">${esc(a.description || '—')} · vue ${plural(a.app_count, 'fois', 'fois')}</div></div>`,
    placeholder: 'Nom du jeu, description ou n° de pub…',
    onCreate: text => openAdForm({}, { gameText: text }),
    createText: t => `＋ Nouvelle pub « ${t} »`,
    ...extraOpts,
  });
}

// ===========================================================================
// Images : envoi, zone de dépôt, galerie, visionneuse
// ===========================================================================
function readDataURL(file) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(r.result);
    r.onerror = () => rej(new Error('Lecture du fichier impossible'));
    r.readAsDataURL(file);
  });
}

async function makeThumb(file, max = 520) {
  try {
    const bmp = await createImageBitmap(file);
    const k = Math.min(1, max / Math.max(bmp.width, bmp.height));
    const c = document.createElement('canvas');
    c.width = Math.round(bmp.width * k);
    c.height = Math.round(bmp.height * k);
    c.getContext('2d').drawImage(bmp, 0, 0, c.width, c.height);
    return c.toDataURL('image/jpeg', 0.82);
  } catch (_) {
    return null; // format non lisible par le navigateur (HEIC…) : pas de miniature
  }
}

const isImageFile = f => f.type.startsWith('image/') || /\.(jpe?g|png|gif|webp|bmp|tiff?|avif|heic)$/i.test(f.name);

async function uploadFiles(files, entity, entityId) {
  let n = 0;
  for (const f of files) {
    if (!isImageFile(f)) { toast(`${f.name} : ce n'est pas une image`, 'err'); continue; }
    let name = f.name || 'image.png';
    if (!/\.[a-z0-9]+$/i.test(name)) name += '.' + ((f.type.split('/')[1] || 'png').replace('jpeg', 'jpg'));
    const [data, thumb] = await Promise.all([readDataURL(f), makeThumb(f)]);
    await POST('images', { entity, entity_id: entityId, name, data, thumb });
    n++;
  }
  if (n) { invalidate(); toast(`${plural(n, 'image ajoutée', 'images ajoutées')}`); }
  return n;
}

function dropzone(onFiles, text = 'Déposer des images ici', { paste = true } = {}) {
  const dz = el('div', 'dropzone', `<b>${esc(text)}</b><br><small>glisser-déposer, cliquer pour choisir${paste ? ', ou coller (Ctrl+V)' : ''}</small>
      <input type="file" accept="image/*,.heic" multiple hidden>`);
  dz.tabIndex = 0;
  if (paste) dz.dataset.paste = '1';
  const input = $('input', dz);
  const handle = async files => {
    files = [...files];
    if (!files.length) return;
    dz.classList.add('busy');
    try { await onFiles(files); } catch (e) { toast(e.message, 'err'); } finally { dz.classList.remove('busy'); }
  };
  dz._onFiles = handle;
  dz.addEventListener('click', () => input.click());
  dz.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
  input.addEventListener('change', () => { handle(input.files); input.value = ''; });
  dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('over'); });
  dz.addEventListener('dragleave', () => dz.classList.remove('over'));
  dz.addEventListener('drop', e => { e.preventDefault(); dz.classList.remove('over'); handle(e.dataTransfer.files); });
  return dz;
}

// Ctrl+V d'une image : va dans la zone de dépôt de la fenêtre active (modale en priorité)
document.addEventListener('paste', e => {
  const files = [...(e.clipboardData?.files || [])].filter(isImageFile);
  if (!files.length) return;
  const scope = overlays[overlays.length - 1] || $('#main');
  const dz = $('.dropzone[data-paste]', scope);
  if (!dz || !dz._onFiles) return;
  e.preventDefault();
  dz._onFiles(files);
});

// Images choisies avant que l'élément n'existe (envoyées à l'enregistrement)
function pendingImages(text) {
  const files = [];
  const wrap = el('div');
  const prev = el('div', 'previews');
  const draw = () => {
    prev.innerHTML = '';
    files.forEach((f, i) => {
      const fig = el('figure');
      const img = el('img');
      img.src = URL.createObjectURL(f);
      img.onerror = () => img.replaceWith(el('div', 'file', esc(f.name)));
      const b = el('button', null, '✕');
      b.type = 'button';
      b.title = 'Retirer';
      b.onclick = () => { files.splice(i, 1); draw(); };
      fig.append(img, b);
      prev.append(fig);
    });
  };
  wrap.append(dropzone(fs => { files.push(...fs); draw(); }, text), prev);
  return { el: wrap, files, clear() { files.length = 0; draw(); } };
}

function lightbox(list, start = 0) {
  if (!list.length) return;
  let i = start;
  const lb = el('div', 'lightbox', `<img alt=""><div class="lb-bar"></div>
      <button type="button" class="lb-close" title="Fermer">✕</button>
      <button type="button" class="lb-prev" title="Précédente">‹</button>
      <button type="button" class="lb-next" title="Suivante">›</button>`);
  const draw = () => {
    const im = list[i];
    $('img', lb).src = im.url;
    $('.lb-bar', lb).innerHTML = `${esc(im.caption || '')} ${list.length > 1 ? `(${i + 1}/${list.length})` : ''}
        <a href="${esc(im.url)}" target="_blank" rel="noopener">ouvrir l'original</a>`;
    $('.lb-prev', lb).hidden = $('.lb-next', lb).hidden = list.length < 2;
  };
  const move = d => { i = (i + d + list.length) % list.length; draw(); };
  $('.lb-close', lb).onclick = () => lb.remove();
  $('.lb-prev', lb).onclick = e => { e.stopPropagation(); move(-1); };
  $('.lb-next', lb).onclick = e => { e.stopPropagation(); move(1); };
  lb.addEventListener('click', e => { if (e.target === lb) lb.remove(); });
  const onKey = e => {
    if (!document.body.contains(lb)) return document.removeEventListener('keydown', onKey);
    if (e.key === 'ArrowLeft') move(-1);
    if (e.key === 'ArrowRight') move(1);
  };
  document.addEventListener('keydown', onKey);
  draw();
  document.body.append(lb);
}

// Galerie des images d'un élément + zone d'ajout
function galleryBlock(images, { entity, entityId, onChange, dropText = 'Ajouter des images', big = false, paste = true }) {
  const wrap = el('div');
  if (images.length) {
    const g = el('div', 'gallery' + (big ? ' big' : ''));
    g.innerHTML = images.map((im, i) => `<figure data-i="${i}">
        <img loading="${big && i === 0 ? 'eager' : 'lazy'}" src="${esc(big && i === 0 ? im.url : imgSrc(im))}" alt="${esc(im.original_name)}"
             onerror="if(!this.dataset.f){this.dataset.f=1;this.src='${esc(imgSrc(im))}'}">
        <figcaption>${i === 0 ? '<span class="badge">principale</span>' : '<button type="button" class="icon" data-act="main" title="Mettre en image principale">★</button>'}
        <button type="button" class="icon" data-act="del" title="Supprimer l'image">🗑</button></figcaption></figure>`).join('');
    wrap.append(g);
    if (big && images.length > 1) {
      const strip = el('div', 'gallery');
      strip.innerHTML = images.slice(1).map((im, j) => `<figure data-i="${j + 1}"><img loading="lazy" src="${esc(imgSrc(im))}" alt="">
          <figcaption><button type="button" class="icon" data-act="main" title="Mettre en image principale">★</button>
          <button type="button" class="icon" data-act="del" title="Supprimer l'image">🗑</button></figcaption></figure>`).join('');
      wrap.append(strip);
    }
    wrap.addEventListener('click', async e => {
      const fig = e.target.closest('figure');
      if (!fig) return;
      const im = images[+fig.dataset.i];
      const act = e.target.closest('button')?.dataset.act;
      if (act === 'main') { await PUT(`images/${im.id}`, { principale: true }); invalidate(); onChange(); }
      else if (act === 'del') {
        if (await confirmBox('Supprimer cette image ? (le fichier sera effacé)')) {
          await DEL(`images/${im.id}`); invalidate(); onChange();
        }
      } else if (e.target.tagName === 'IMG') {
        lightbox(images.map(x => ({ url: x.url, caption: x.original_name })), +fig.dataset.i);
      }
    });
  }
  wrap.append(dropzone(async files => { if (await uploadFiles(files, entity, entityId)) onChange(); }, dropText, { paste }));
  return wrap;
}

// ===========================================================================
// Formulaires (modales)
// ===========================================================================
/* fields : [{ name, label, type, required, options, placeholder, help, wide, combo }] */
function formModal({ title, fields, values = {}, submitLabel = 'Enregistrer', onSubmit, extra, wide }) {
  return new Promise(resolve => {
    const form = el('form', 'form');
    form.noValidate = true;
    const ctrls = {};
    for (const f of fields) {
      const row = el(f.type === 'combo' || f.type === 'custom' ? 'div' : 'label', 'field' + (f.wide ? ' wide' : ''));
      row.innerHTML = `<span>${esc(f.label)}${f.required ? ' <b class="req">*</b>' : ''}</span>`;
      if (f.type === 'custom') {
        const c = f.custom(values[f.name]);
        row.append(c.el);
        ctrls[f.name] = { get: () => c.get(), focus: () => c.focus() };
      } else if (f.type === 'combo') {
        const c = f.combo(values[f.name]);
        row.append(c.el);
        ctrls[f.name] = { get: () => c.value ?? c.resolve(), focus: () => c.focus(), c };
      } else if (f.type === 'select') {
        const s = el('select');
        s.innerHTML = f.options.map(o => `<option value="${esc(o.value)}">${esc(o.label)}</option>`).join('');
        s.value = values[f.name] ?? '';
        row.append(s);
        ctrls[f.name] = { get: () => s.value, focus: () => s.focus() };
      } else {
        const i = el(f.type === 'textarea' ? 'textarea' : 'input');
        if (f.type !== 'textarea') i.type = f.type || 'text';
        if (f.step) i.step = f.step;
        if (f.type === 'number') i.inputMode = 'decimal';
        i.placeholder = f.placeholder || '';
        i.value = values[f.name] ?? '';
        row.append(i);
        ctrls[f.name] = { get: () => i.value.trim(), focus: () => i.focus() };
      }
      if (f.help) row.append(el('small', null, esc(f.help)));
      form.append(row);
    }
    const extraApi = extra ? extra(form) : null;
    const err = el('div', 'form-error');
    const actions = el('div', 'actions', `<button type="button" data-cancel>Annuler</button>
        <button type="submit" class="primary">${esc(submitLabel)}</button>`);
    form.append(err, actions);
    let done = false;
    const m = openModal(title, form, { wide, onClose: () => { if (!done) resolve(null); } });
    $('[data-cancel]', form).onclick = () => m.close();
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const data = {};
      for (const [k, c] of Object.entries(ctrls)) data[k] = c.get();
      const missing = fields.find(f => f.required && (data[f.name] === '' || data[f.name] == null));
      if (missing) {
        const c = ctrls[missing.name].c;
        err.textContent = c && c.text
          ? `${missing.label} : « ${c.text} » n'est pas encore choisi. Touchez-le dans la liste sous le champ, ou « ＋ Nouveau… » pour le créer.`
          : `Champ obligatoire : ${missing.label}`;
        ctrls[missing.name].focus();
        if (c && c.text) c.input.dispatchEvent(new Event('input'));
        return;
      }
      const btn = $('button[type=submit]', form);
      btn.disabled = true;
      err.textContent = '';
      try {
        const res = await onSubmit(data, extraApi);
        done = true;
        m.close();
        resolve(res);
      } catch (ex) {
        err.textContent = ex.message;
      } finally {
        btn.disabled = false;
      }
    });
    setTimeout(() => {
      const first = fields.find(f => !values[f.name]) || fields[0];
      ctrls[first.name].focus();
    }, 30);
  });
}

/* Plateformes à cocher (plusieurs possibles). Les plus utilisées apparaissent en premier. */
function platformPicker(initial = []) {
  const sel = new Set((initial || []).map(Number));
  const wrap = el('div', 'picker', `<input type="search" placeholder="Filtrer les plateformes…">
      <div class="chips"></div><div class="picked muted"></div>`);
  const input = $('input', wrap), box = $('.chips', wrap), picked = $('.picked', wrap);
  let list = [];
  const draw = () => {
    const words = norm(input.value).split(/\s+/).filter(Boolean);
    const shown = list.filter(p => sel.has(p.id) || words.every(w => norm(p.name + ' ' + p.maker).includes(w)));
    box.innerHTML = shown.map(p => `<button type="button" class="chip ${sel.has(p.id) ? 'on' : ''}" data-id="${p.id}">${sel.has(p.id) ? '✓ ' : ''}${esc(p.name)}</button>`).join('')
      + (input.value.trim() && !list.some(p => norm(p.name) === norm(input.value.trim()))
        ? `<button type="button" class="chip create" data-create="1">＋ Créer « ${esc(input.value.trim())} »</button>` : '');
    const names = list.filter(p => sel.has(p.id)).map(p => p.name);
    picked.textContent = names.length ? `Sélection : ${names.join(' / ')}` : 'Aucune plateforme cochée';
  };
  const load = async () => {
    const meta = await getMeta();
    list = [...meta.platforms].sort((a, b) => (b.ads_count - a.ads_count) || a.name.localeCompare(b.name, 'fr'));
    draw();
  };
  box.addEventListener('click', async e => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.create) {
      const pl = await POST('platforms', { name: input.value.trim() });
      invalidate();
      sel.add(pl.id);
      input.value = '';
      await load();
      return;
    }
    const id = +b.dataset.id;
    if (sel.has(id)) sel.delete(id); else sel.add(id);
    draw();
  });
  input.addEventListener('input', draw);
  input.addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const first = $('.chip:not(.on)', box);
    if (first && input.value.trim()) { first.click(); input.value = ''; draw(); }
  });
  load();
  return {
    el: wrap, get: () => [...sel], focus: () => input.focus(),
    set(ids) { sel.clear(); (ids || []).forEach(i => sel.add(+i)); draw(); },
    get size() { return sel.size; },
  };
}

async function openGameForm(values = {}) {
  const isNew = !values.id;
  return formModal({
    title: isNew ? 'Nouveau jeu' : 'Modifier le jeu',
    values,
    fields: [
      { name: 'title', label: 'Titre', required: true, wide: true, placeholder: 'Final Fantasy VII' },
      { name: 'original_title', label: 'Titre original', wide: true, placeholder: 'ファイナルファンタジーVII' },
      { name: 'series_id', label: 'Série', type: 'combo', combo: v => seriesCombo({ value: v }) },
      { name: 'publisher', label: 'Éditeur', placeholder: 'Square' },
      { name: 'year', label: 'Année de sortie', type: 'number', placeholder: '1997' },
      { name: 'notes', label: 'Remarques', type: 'textarea', wide: true },
    ],
    onSubmit: async data => {
      const g = isNew ? await POST('games', data) : await PUT(`games/${values.id}`, data);
      invalidate();
      toast(isNew ? `Jeu « ${g.title} » créé` : 'Jeu modifié');
      return g;
    },
  });
}

async function openAdForm(values = {}, { gameText } = {}) {
  const isNew = !values.id;
  let pending;
  let gameCtl;
  let picker;
  // Nouvelle pub : reprendre les plateformes de la dernière pub du même jeu
  const suggestPlatforms = async game => {
    if (!isNew || !game || !picker || picker.size) return;
    const last = (await getAds()).filter(a => a.game_id === game.id).sort((a, b) => b.id - a.id)[0];
    if (last && last.platform_ids.length) picker.set(last.platform_ids);
  };
  return formModal({
    title: isNew ? 'Nouvelle pub' : `Modifier la pub #${values.id}`,
    values: { pages: 1, ...values },
    fields: [
      {
        name: 'game_id', label: 'Jeu', type: 'combo', required: true, wide: true,
        combo: v => {
          gameCtl = gameCombo({ value: v, onChange: g => suggestPlatforms(g) });
          if (gameText && !v) {
            gameCtl.input.value = gameText;
          }
          return gameCtl;
        },
        help: 'Pas encore dans la liste ? Tapez le titre puis « Nouveau jeu ».',
      },
      {
        name: 'platform_ids', label: 'Plateformes annoncées sur la pub', type: 'custom', wide: true,
        custom: v => { picker = platformPicker(v); if (values.game_id) getGames().then(gs => suggestPlatforms(gs.find(g => g.id === values.game_id))); return picker; },
        help: 'Cliquer pour cocher / décocher. Plusieurs possibles (ex. PS4 + Switch).',
      },
      { name: 'description', label: 'Description / visuel', placeholder: 'Ce qui distingue cette pub : visuel, slogan…' },
      { name: 'pages', label: 'Nb de pages', type: 'number', step: '0.5', help: '1, 2 (double page), 0,5…' },
      { name: 'notes', label: 'Remarques', type: 'textarea', wide: true },
    ],
    extra: form => {
      if (!isNew) return null;
      pending = pendingImages('Image de la pub (photo ou scan)');
      const row = el('div', 'field wide');
      row.innerHTML = '<span>Image</span>';
      row.append(pending.el);
      form.append(row);
      return pending;
    },
    onSubmit: async data => {
      const a = isNew ? await POST('ads', data) : await PUT(`ads/${values.id}`, data);
      if (pending && pending.files.length) await uploadFiles(pending.files, 'ads', a.id);
      invalidate();
      toast(isNew ? `Pub #${a.id} créée` : 'Pub modifiée');
      return a;
    },
  });
}

async function openMagazineForm(values = {}) {
  const isNew = !values.id;
  return formModal({
    title: isNew ? 'Nouveau magazine' : 'Modifier le magazine',
    values,
    fields: [
      { name: 'name', label: 'Nom', required: true, wide: true, placeholder: 'Weekly Famitsu' },
      { name: 'publisher', label: 'Éditeur', placeholder: 'ASCII / Enterbrain' },
      { name: 'frequency', label: 'Périodicité', placeholder: 'Hebdomadaire, mensuel…' },
      { name: 'notes', label: 'Remarques', type: 'textarea', wide: true },
    ],
    onSubmit: async data => {
      const m = isNew ? await POST('magazines', data) : await PUT(`magazines/${values.id}`, data);
      invalidate();
      return m;
    },
  });
}

async function openIssueForm(values = {}) {
  const isNew = !values.id;
  return formModal({
    title: isNew ? 'Nouveau numéro' : 'Modifier le numéro',
    values,
    fields: [
      { name: 'magazine_id', label: 'Magazine', type: 'combo', required: true, wide: true, combo: v => magazineCombo({ value: v }) },
      { name: 'number', label: 'Numéro', required: true, placeholder: '425' },
      { name: 'date', label: 'Date de parution', placeholder: 'AAAA-MM-JJ (ou AAAA-MM)' },
      { name: 'notes', label: 'Remarques', type: 'textarea', wide: true },
    ],
    onSubmit: async data => {
      const i = isNew ? await POST('issues', data) : await PUT(`issues/${values.id}`, data);
      invalidate();
      return i;
    },
  });
}

async function openAppearanceForm(values = {}) {
  const isNew = !values.id;
  let pending;
  return formModal({
    title: isNew ? 'Nouvelle parution' : 'Modifier la parution',
    values: { ...values, issue_number: values.number || '', for_sale: values.for_sale ? '1' : '0' },
    fields: [
      { name: 'magazine_id', label: 'Magazine', type: 'combo', required: true, combo: v => magazineCombo({ value: v }) },
      { name: 'issue_number', label: 'Numéro', required: true, placeholder: '425' },
      { name: 'ad_id', label: 'Pub', type: 'combo', required: true, wide: true, combo: v => adCombo({ value: v }) },
      { name: 'page', label: 'Page', placeholder: '12, 表4…' },
      { name: 'for_sale', label: 'En vente', type: 'select', options: [{ value: '0', label: `${BATSU} Non` }, { value: '1', label: `${MARU} Oui` }] },
      { name: 'notes', label: 'Remarques', type: 'textarea', wide: true, placeholder: 'État, prix, scan fait…' },
    ],
    extra: form => {
      if (isNew) return;
      const row = el('div', 'field wide');
      row.innerHTML = `<span>Photo de VOTRE exemplaire (facultatif)</span>
        <small>Seulement pour garder une trace de votre page à vous : état, photo pour la vente…
        L'image de la pub elle-même se met sur la fiche de la pub.</small>`;
      {
        const holder = el('div');
        const draw = async () => {
          const d = await GET(`appearances/${values.id}`);
          holder.replaceChildren(galleryBlock(d.images, { entity: 'appearances', entityId: values.id, onChange: draw, dropText: 'Ajouter une photo' }));
        };
        draw();
        row.append(holder);
      }
      form.append(row);
    },
    onSubmit: async data => {
      const a = isNew ? await POST('appearances', data) : await PUT(`appearances/${values.id}`, data);
      if (pending && pending.files.length) await uploadFiles(pending.files, 'appearances', a.id);
      invalidate();
      toast(isNew ? 'Parution ajoutée' : 'Parution modifiée');
      return a;
    },
  });
}

// ===========================================================================
// Tableau des parutions (réutilisé partout)
// ===========================================================================
function appTable(items, { hide = [], onChange = () => {}, emptyText = 'Aucune parution.' } = {}) {
  const wrap = el('div', 'table-wrap');
  if (!items.length) { wrap.innerHTML = `<p class="empty">${esc(emptyText)}</p>`; return wrap; }
  const show = c => !hide.includes(c);
  wrap.innerHTML = `<table class="data"><thead><tr><th></th>
      ${show('issue') ? '<th>Magazine / n°</th><th>Date</th>' : ''}
      <th>Page</th>${show('game') ? '<th>Jeu</th>' : ''}${show('ad') ? '<th>Pub</th>' : ''}
      ${show('platform') ? '<th>Plateforme</th>' : ''}<th title="En vente">Vente</th><th>Remarques</th><th></th></tr></thead>
    <tbody>${items.map((r, i) => `<tr data-i="${i}">
      <td class="thumb">${thumbImg(r.thumb_url)}</td>
      ${show('issue') ? `<td><a href="#/numeros/${r.issue_id}">${esc(r.magazine)} <b>n°${esc(r.number)}</b></a></td>
        <td class="nowrap">${esc(r.date || '—')}</td>` : ''}
      <td class="nowrap">${esc(r.page)}</td>
      ${show('game') ? `<td><a href="#/jeux/${r.game_id}">${esc(r.game)}</a></td>` : ''}
      ${show('ad') ? `<td><a href="#/pubs/${r.ad_id}">#${r.ad_id}</a> <span class="muted">${esc(r.description || '')}</span></td>` : ''}
      ${show('platform') ? `<td>${esc(r.platform || '')}</td>` : ''}
      <td>${saleBtn(r.for_sale)}</td>
      <td class="notes">${esc(r.notes)}</td>
      <td class="row-actions"><button type="button" class="icon" data-act="edit" title="Modifier">✎</button>
        <button type="button" class="icon" data-act="del" title="Supprimer">🗑</button></td></tr>`).join('')}</tbody></table>`;
  wrap.addEventListener('click', async e => {
    const tr = e.target.closest('tr[data-i]');
    if (!tr) return;
    const r = items[+tr.dataset.i];
    if (e.target.classList.contains('thumb-img')) return openThumb(r);
    const act = e.target.closest('button')?.dataset.act;
    if (act === 'sale') {
      const v = r.for_sale ? 0 : 1;
      await PUT(`appearances/${r.id}`, { for_sale: v });
      r.for_sale = v;
      e.target.closest('button').outerHTML = saleBtn(v);
      invalidate();
      onChange('sale');
    } else if (act === 'edit') {
      if (await openAppearanceForm(r)) onChange();
    } else if (act === 'del') {
      if (await confirmBox(`Supprimer la parution de « ${r.game} » dans ${r.magazine} n°${r.number} p.${r.page} ?`)) {
        await DEL(`appearances/${r.id}`);
        invalidate();
        toast('Parution supprimée');
        onChange();
      }
    }
  });
  return wrap;
}

// Clic sur une miniature de tableau : images d'origine de l'exemplaire puis de la pub
async function openThumb(r) {
  const [d, ad] = await Promise.all([GET(`appearances/${r.id}`), GET(`ads/${r.ad_id}`)]);
  const list = [...d.images, ...ad.images].map(im => ({ url: im.url, caption: im.original_name }));
  lightbox(list, 0);
}

function adCard(a) {
  return `<a class="ad-card" href="#/pubs/${a.id}">
    <div class="img">${a.thumb_url ? `<img loading="lazy" src="${esc(a.thumb_url)}" alt="">` : '<div class="none">Pas encore d\'image</div>'}</div>
    <div class="body"><div class="t">${esc(a.game_title)}</div>
      <div class="d">${esc(a.description || '—')}</div>
      <div class="meta"><span>#${a.id} · ${esc(a.platform_name || '')}</span><span>${plural(a.app_count, 'parution')}</span></div>
    </div></a>`;
}

// ===========================================================================
// Pages
// ===========================================================================
async function pageHome(view) {
  const d = await GET('dashboard');
  const c = d.counts;
  view.innerHTML = `
    <div class="page-head"><div><h1>Accueil</h1><div class="sub">Base de référencement des pubs de jeux vidéo dans les magazines</div></div>
      <div class="btns"><a class="btn primary big" href="#/saisie">＋ Saisie rapide</a></div></div>
    ${c.games === 0 ? `<div class="card welcome" style="margin-bottom:16px"><h2>Bienvenue !</h2>
      La base est vide. Le plus simple est de passer directement par la <a href="#/saisie">saisie rapide</a> :
      <ol><li>Choisir le magazine et taper le numéro (ils sont créés au passage).</li>
      <li>Taper la page, puis chercher la pub : si elle n'existe pas, « Nouvelle pub » (et « Nouveau jeu » si besoin).</li>
      <li>Ajouter une photo ou un scan de la pub (glisser-déposer ou Ctrl+V).</li>
      <li>Enregistrer, puis passer à la pub suivante du même numéro.</li></ol></div>` : ''}
    <div class="tiles">
      <a class="tile" href="#/recherche"><div class="n">${c.appearances}</div><div class="l">parutions référencées</div></a>
      <a class="tile" href="#/pubs"><div class="n">${c.ads}</div><div class="l">pubs différentes</div></a>
      <a class="tile" href="#/jeux"><div class="n">${c.games}</div><div class="l">jeux</div></a>
      <a class="tile" href="#/magazines"><div class="n">${c.issues}</div><div class="l">numéros · ${plural(c.magazines, 'magazine')}</div></a>
      <a class="tile" href="#/recherche?vente=1"><div class="n">${c.for_sale}</div><div class="l">en vente ${MARU}</div></a>
      <div class="tile"><div class="n">${c.week}</div><div class="l">saisies ces 7 derniers jours</div></div>
    </div>
    ${c.ads_without_image ? `<div class="notice">${plural(c.ads_without_image, 'pub n\'a', 'pubs n\'ont')} pas encore d'image.
      <a href="#/pubs?sans_image=1">Les voir</a></div>` : ''}
    <div class="grid-2 home">
      <div class="card"><h2>Dernières saisies</h2><div id="recent"></div></div>
      <div>
        <div class="card"><h2>Jeux les plus présents</h2>
          ${d.top_games.length ? `<ul class="rank">${d.top_games.map(g => `<li><a href="#/jeux/${g.id}">${esc(g.title)}</a>
            <span class="muted">${plural(g.n, 'parution')} · ${plural(g.ads, 'pub')}</span></li>`).join('')}</ul>` : '<p class="empty">—</p>'}</div>
        <div class="card"><h2>Magazines</h2>
          ${d.top_magazines.length ? `<ul class="rank">${d.top_magazines.map(m => `<li><a href="#/magazines/${m.id}">${esc(m.name)}</a>
            <span class="muted">${plural(m.n, 'parution')} · ${plural(m.issues, 'numéro')}</span></li>`).join('')}</ul>` : '<p class="empty">—</p>'}</div>
      </div>
    </div>`;
  $('#recent', view).append(appTable(d.recent, { hide: ['platform'], onChange: () => render(), emptyText: 'Rien pour l\'instant.' }));
}

// ---------------------------------------------------------------------------
async function pageEntry(view, params) {
  view.innerHTML = `
    <div class="page-head"><div><h1>Saisie rapide</h1>
      <div class="sub">Un numéro de magazine, puis les pubs qu'il contient, l'une après l'autre.</div></div></div>
    <div class="grid-entry">
      <form class="card" id="entry" autocomplete="off">
        <div class="step"><span class="num">1</span><h2>Numéro</h2></div>
        <div class="form">
          <div class="field wide"><span>Magazine <b class="req">*</b></span><div id="f-mag"></div></div>
          <label class="field"><span>Numéro <b class="req">*</b></span><input id="f-num" placeholder="425"></label>
          <label class="field"><span>Date de parution</span><input id="f-date" placeholder="AAAA-MM-JJ"></label>
        </div>
        <div class="issue-status" id="issue-status"></div>
        <hr style="border:none;border-top:1px solid var(--line);margin:14px 0">
        <div class="step"><span class="num">2</span><h2>Pub trouvée</h2></div>
        <div class="form">
          <div class="field wide"><span>Jeu <b class="req">*</b></span><div id="f-game"></div>
            <small>Tapez les premières lettres du jeu. S'il n'existe pas encore : « ＋ Nouveau jeu ».</small></div>
          <div class="field wide" id="ad-pick" hidden><span>Quelle pub ? <b class="req">*</b></span>
            <small>Touchez la pub si vous la reconnaissez (🔍 pour l'agrandir), sinon « ＋ Nouvelle pub ».</small>
            <div class="ad-grid" id="ad-grid"></div></div>
          <div class="wide" id="ad-preview"></div>
          <label class="field"><span>Page</span><input id="f-page" placeholder="12, 表4…"></label>
          <div class="field"><span>En vente</span>
            <div class="toggle-sale">
              <label class="no"><input type="radio" name="sale" value="0" checked>${BATSU} Non</label>
              <label class="yes"><input type="radio" name="sale" value="1">${MARU} Oui</label>
            </div></div>
          <label class="field wide"><span>Remarques</span><input id="f-notes" placeholder="État, prix, scan fait…"></label>
          <div class="form-error" id="f-err"></div>
          <div class="actions"><span class="kbd" style="margin-right:auto;align-self:center"><kbd>Entrée</kbd> ou <kbd>Ctrl</kbd>+<kbd>Entrée</kbd> pour enregistrer</span>
            <button type="submit" class="primary big">Enregistrer</button></div>
        </div>
      </form>
      <div>
        <div class="card"><div class="page-head" style="margin-bottom:8px"><h2 id="in-issue-title">Dans ce numéro</h2>
          <div class="btns" id="in-issue-links"></div></div><div id="in-issue"><p class="empty">Choisissez un magazine et un numéro.</p></div></div>
        <div class="card" id="cover-card" hidden><h2>Couverture</h2><div id="cover"></div></div>
      </div>
    </div>`;

  const form = $('#entry', view);
  const numI = $('#f-num', view), dateI = $('#f-date', view), pageI = $('#f-page', view), notesI = $('#f-notes', view);
  const status = $('#issue-status', view), err = $('#f-err', view);
  let issue = null; // numéro existant correspondant (ou null)

  const mag = magazineCombo({ onChange: () => refreshIssue() });
  $('#f-mag', view).append(mag.el);
  // Étape 2 : d'abord le jeu, puis la pub reconnue parmi les miniatures de ce jeu
  let selAd = null;
  let gameAds = [];
  const game = gameCombo({
    placeholder: 'Final Fantasy VII, Biohazard…',
    onChange: async g => {
      selAd = null; showAd(null);
      await drawAds();
      // sur téléphone, la grille apparaît sous le champ : on l'amène à l'écran
      if (g && TOUCH) $('#ad-pick', view).scrollIntoView({ block: 'start', behavior: 'smooth' });
    },
    onCreate: async title => {
      const g = await openGameForm({ title });
      if (g) setTimeout(() => newAdFor(g), 50); // nouveau jeu : forcément une nouvelle pub
      return g;
    },
  });
  $('#f-game', view).append(game.el);

  async function drawAds() {
    const box = $('#ad-pick', view), grid = $('#ad-grid', view);
    const g = game.item;
    if (!g) { box.hidden = true; grid.innerHTML = ''; return; }
    gameAds = (await getAds()).filter(a => a.game_id === g.id).sort((a, b) => b.app_count - a.app_count || a.id - b.id);
    if (game.item !== g) return;
    box.hidden = false;
    grid.innerHTML = gameAds.map(a => `<div class="ad-tile ${selAd && selAd.id === a.id ? 'sel' : ''}" data-id="${a.id}">
        <button type="button" class="pick" data-id="${a.id}" title="Choisir cette pub">
          <span class="im">${a.thumb_url ? `<img src="${esc(a.thumb_url)}" alt="" loading="lazy">` : '<span class="none">pas d\'image</span>'}</span>
          <span class="t">${esc(a.description || 'Sans description')}</span>
          <span class="s">${esc(a.platform_name || '')}</span>
          <span class="s">${plural(a.app_count, 'parution')}</span>
          ${selAd && selAd.id === a.id ? '<span class="ok">✓</span>' : ''}</button>
        ${a.thumb_url ? `<button type="button" class="zoom icon" data-zoom="${a.id}" tabindex="-1" title="Agrandir">🔍</button>` : ''}</div>`).join('')
      + `<button type="button" class="ad-tile new" data-new="1"><span class="plus">＋</span><span>Nouvelle pub<br>de ce jeu</span></button>`;
  }
  $('#ad-grid', view).addEventListener('click', async e => {
    const zoom = e.target.closest('[data-zoom]');
    if (zoom) {
      const a = await GET(`ads/${zoom.dataset.zoom}`);
      return lightbox(a.images.map(im => ({ url: im.url, caption: a.description })), 0);
    }
    if (e.target.closest('[data-new]')) return newAdFor(game.item);
    const pick = e.target.closest('.pick');
    if (!pick) return;
    selAd = gameAds.find(a => a.id === +pick.dataset.id) || null;
    drawAds();
    showAd(selAd);
    pageI.focus({ preventScroll: true });
  });
  async function newAdFor(g) {
    const a = await openAdForm({ game_id: g.id });
    if (!a) return;
    selAd = (await getAds()).find(x => x.id === a.id) || null;
    await drawAds();
    showAd(selAd);
  }
  // Interface commune utilisée plus bas (enregistrement, rafraîchissement)
  const ad = {
    get value() { return selAd ? selAd.id : null; },
    get item() { return selAd; },
    async reload() { await drawAds(); selAd = selAd && ((await getAds()).find(a => a.id === selAd.id) || null); },
    clear() { selAd = null; game.clear(); },
  };
  // Aperçu de la pub choisie. Si elle n'a pas encore d'image, une zone permet de l'ajouter
  // tout de suite (l'image est rattachée à la pub : elle vaudra pour toutes ses parutions).
  function showAd(a) {
    const box = $('#ad-preview', view);
    if (!a) { box.innerHTML = ''; return; }
    const dup = lastItems.filter(r => r.ad_id === a.id);
    box.innerHTML = `<div class="ad-preview">${a.thumb_url ? `<img src="${esc(a.thumb_url)}" alt="">` : '<div class="thumb-none">▢</div>'}
      <div style="flex:1;min-width:0"><b>${esc(a.game_title)}</b> <span class="muted">${esc(a.platform_name || '')}</span><br>
      ${esc(a.description || '')}<br>
      <small>Pub #${a.id} · ${fmtPages(a.pages) || '?'} p. · déjà vue ${plural(a.app_count, 'fois', 'fois')}</small>
      ${dup.length ? `<div class="warn">Déjà saisie dans ce numéro (p. ${dup.map(r => esc(r.page) || '?').join(', ')})</div>` : ''}
      <div style="margin-top:4px"><a href="#/pubs/${a.id}" target="_blank" tabindex="-1">ouvrir la fiche ↗</a></div>
      <div class="ad-img-slot" style="margin-top:8px"></div></div></div>`;
    if (!a.img_count) {
      const dz = dropzone(async files => {
        if (!await uploadFiles(files, 'ads', a.id)) return;
        await ad.reload();
        showAd(ad.item);
      }, 'Cette pub n\'a pas encore d\'image : ajouter la photo / le scan');
      dz.tabIndex = -1; // Tab passe directement à « Page »
      $('.ad-img-slot', box).append(dz);
    }
  }

  let lastItems = [];
  let reqId = 0;
  async function refreshIssue() {
    const id = ++reqId;
    const m = mag.item, num = numI.value.trim();
    issue = null;
    if (!m || !num) {
      status.textContent = '';
      $('#in-issue', view).innerHTML = '<p class="empty">Choisissez un magazine et un numéro.</p>';
      $('#in-issue-title', view).textContent = 'Dans ce numéro';
      $('#in-issue-links', view).innerHTML = '';
      $('#cover-card', view).hidden = true;
      lastItems = [];
      return;
    }
    try { localStorage.setItem(`bddpubs.saisie.${PROJ || 'defaut'}`, JSON.stringify({ magazine_id: m.id, number: num })); } catch (_) { /* ignoré */ }
    const found = await GET(`issues?${qs({ magazine_id: m.id, number: num })}`);
    if (id !== reqId) return;
    $('#in-issue-title', view).textContent = `${m.name} n°${num}`;
    if (found.length) {
      issue = await GET(`issues/${found[0].id}`);
      if (id !== reqId) return;
      if (!dateI.value && issue.date) dateI.value = issue.date;
      status.innerHTML = `<span class="badge gray">numéro existant</span> ${issue.date ? 'paru le ' + esc(issue.date) + ' · ' : ''}${plural(issue.app_count, 'pub référencée', 'pubs référencées')}`;
      lastItems = issue.appearances;
      $('#in-issue-links', view).innerHTML = `<a class="btn" href="#/numeros/${issue.id}">Fiche du numéro</a>`;
      const inIssue = $('#in-issue', view);
      inIssue.replaceChildren(appTable(issue.appearances, { hide: ['issue', 'platform'], onChange: () => refreshIssue(), emptyText: 'Aucune pub saisie pour l\'instant.' }));
      $('#cover-card', view).hidden = false;
      $('#cover', view).replaceChildren(galleryBlock(issue.images, { entity: 'issues', entityId: issue.id, onChange: refreshIssue, dropText: 'Ajouter la couverture', paste: false }));
    } else {
      status.innerHTML = '<span class="badge">nouveau numéro</span> il sera créé au premier enregistrement';
      lastItems = [];
      $('#in-issue-links', view).innerHTML = '';
      $('#in-issue', view).innerHTML = '<p class="empty">Aucune pub saisie pour l\'instant.</p>';
      $('#cover-card', view).hidden = true;
    }
    if (ad.item) showAd(ad.item);
  }
  numI.addEventListener('input', debounce(refreshIssue, 350));

  async function save() {
    err.textContent = '';
    if (!mag.value) mag.resolve();
    if (!game.value) { game.resolve(); if (game.value) await drawAds(); }
    if (!mag.value) { err.textContent = 'Choisissez un magazine.'; mag.focus(); return; }
    if (!numI.value.trim()) { err.textContent = 'Indiquez le numéro.'; numI.focus(); return; }
    if (!game.value) {
      err.textContent = game.text
        ? `« ${game.text} » : touchez le jeu dans la liste sous le champ, ou « ＋ Nouveau jeu » pour le créer.`
        : 'Indiquez le jeu.';
      game.focus();
      return;
    }
    if (!ad.value) {
      err.textContent = 'Touchez la pub correspondante dans les miniatures, ou « ＋ Nouvelle pub ».';
      $('#ad-pick', view).scrollIntoView({ block: 'center', behavior: 'smooth' });
      return;
    }
    const btn = $('button[type=submit]', form);
    btn.disabled = true;
    try {
      const saleVal = $('input[name=sale]:checked', form).value;
      const a = await POST('appearances', {
        magazine_id: mag.value, issue_number: numI.value.trim(), issue_date: dateI.value.trim(),
        ad_id: ad.value, page: pageI.value.trim(), for_sale: saleVal, notes: notesI.value.trim(),
      });
      invalidate();
      toast(`Enregistré : ${a.game} ${a.page ? 'p.' + a.page : ''}`);
      pageI.value = '';
      notesI.value = '';
      ad.clear();
      $('input[name=sale][value="0"]', form).checked = true;
      await refreshIssue();
      if (!TOUCH) game.focus();
    } catch (e) {
      err.textContent = e.message;
    } finally {
      btn.disabled = false;
    }
  }
  form.addEventListener('submit', e => { e.preventDefault(); save(); });
  form.addEventListener('keydown', e => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); save(); }
  });

  // Reprise : numéro passé dans l'adresse, sinon le dernier utilisé
  let start = null;
  if (params.issue) {
    const i = await GET(`issues/${params.issue}`);
    start = { magazine_id: i.magazine_id, number: i.number };
  } else {
    try { start = JSON.parse(localStorage.getItem(`bddpubs.saisie.${PROJ || 'defaut'}`) || 'null'); } catch (_) { start = null; }
  }
  if (start) {
    await mag.set(start.magazine_id, true);
    if (mag.value) { numI.value = start.number; await refreshIssue(); }
  }
  if (!TOUCH) setTimeout(() => (mag.value && numI.value ? game.input : mag.input).focus(), 50);
}

// ---------------------------------------------------------------------------
async function pageSearch(view, params) {
  const meta = await getMeta();
  const opt = (list, lbl = x => x.name) => '<option value="">Tous</option>' + list.map(x => `<option value="${x.id}">${esc(lbl(x))}</option>`).join('');
  view.innerHTML = `
    <div class="page-head"><div><h1>Recherche</h1><div class="sub">Tous les critères remplis doivent être vrais. Critère vide = ignoré.</div></div>
      <div class="btns"><button type="button" id="reset">Réinitialiser</button><a class="btn" id="export">⬇ Export CSV</a></div></div>
    <form class="card filters" id="filters" autocomplete="off">
      <label class="field"><span>Magazine</span><select name="magazine_id">${opt(meta.magazines)}</select></label>
      <label class="field"><span>Numéro</span><input name="numero" placeholder="425"></label>
      <label class="field"><span>Année de parution</span><input name="annee" placeholder="1997" inputmode="numeric"></label>
      <label class="field"><span>Jeu (contient)</span><input name="jeu" placeholder="final fantasy"></label>
      <label class="field"><span>Série</span><select name="series_id">${opt(meta.series)}</select></label>
      <label class="field"><span>Plateforme</span><select name="platform_id">${opt(meta.platforms)}</select></label>
      <label class="field"><span>N° de pub</span><input name="ad_id" placeholder="12"></label>
      <label class="field"><span>En vente</span><select name="vente"><option value="">Tous</option><option value="1">${MARU} Oui</option><option value="0">${BATSU} Non</option></select></label>
      <label class="field"><span>Mot-clé (description, remarques)</span><input name="q"></label>
      <label class="field"><span>Trier par</span><select name="tri"><option value="">Magazine puis numéro</option>
        <option value="date">Date de parution</option><option value="jeu">Jeu</option><option value="recent">Dernières saisies</option></select></label>
    </form>
    <div class="statbar" id="stats"></div>
    <div class="card"><div id="results"></div><div class="more" id="more"></div></div>`;
  const form = $('#filters', view);
  for (const [k, v] of Object.entries(params)) if (form.elements[k]) form.elements[k].value = v;
  const LIMIT = 200;
  let offset = 0, items = [];

  const current = () => {
    const o = {};
    for (const e of form.elements) if (e.name) o[e.name] = e.value.trim();
    return o;
  };
  async function run(append = false) {
    const f = current();
    history.replaceState(null, '', '#/recherche' + (qs(f) ? '?' + qs(f) : ''));
    $('#export', view).href = '/api/export/apparitions.csv?' + qs({ ...f, projet: PROJ });
    if (!append) { offset = 0; items = []; }
    const res = await GET('search?' + qs({ ...f, limit: LIMIT, offset }));
    items = items.concat(res.items);
    offset += res.items.length;
    const s = res.stats;
    $('#stats', view).innerHTML = `<span><b>${s.total}</b> parution${s.total > 1 ? 's' : ''}</span>
      <span><b>${s.ads}</b> pub${s.ads > 1 ? 's' : ''} différente${s.ads > 1 ? 's' : ''}</span>
      <span><b>${s.games}</b> jeu${s.games > 1 ? 'x' : ''}</span>
      <span><b>${s.issues}</b> numéro${s.issues > 1 ? 's' : ''} (${plural(s.magazines, 'magazine')})</span>
      <span><b>${s.for_sale}</b> en vente ${MARU}</span>
      <span><b>${fmtPages(s.pages)}</b> page${s.pages > 1 ? 's' : ''} de pub</span>`;
    $('#results', view).replaceChildren(appTable(items, { onChange: kind => { if (kind !== 'sale') run(); }, emptyText: 'Aucun résultat.' }));
    $('#more', view).innerHTML = offset < s.total ? `<button type="button">Afficher plus (${s.total - offset} restants)</button>` : '';
  }
  $('#more', view).addEventListener('click', e => { if (e.target.closest('button')) run(true); });
  form.addEventListener('input', debounce(() => run(), 300));
  form.addEventListener('change', () => run());
  form.addEventListener('submit', e => { e.preventDefault(); run(); });
  $('#reset', view).onclick = () => { form.reset(); run(); };
  await run();
}

// ---------------------------------------------------------------------------
async function pageAds(view, params) {
  const meta = await getMeta();
  view.innerHTML = `
    <div class="page-head"><div><h1>Pubs</h1><div class="sub">Chaque visuel publicitaire distinct. Un jeu peut en avoir plusieurs.</div></div>
      <div class="btns"><button type="button" class="primary" id="new">＋ Nouvelle pub</button></div></div>
    <div class="toolbar" id="tb">
      <input type="search" name="q" placeholder="Rechercher : jeu, description, n°…">
      <select name="platform_id"><option value="">Toutes plateformes</option>${meta.platforms.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('')}</select>
      <select name="series_id"><option value="">Toutes séries</option>${meta.series.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('')}</select>
      <select name="tri"><option value="">Tri : jeu</option><option value="recent">Tri : dernières créées</option></select>
      <label class="check"><input type="checkbox" name="sans_image" value="1"> sans image</label>
      <span class="muted" id="count"></span>
    </div>
    <div class="cards" id="cards"></div>`;
  const tb = $('#tb', view);
  for (const [k, v] of Object.entries(params)) {
    const e = tb.querySelector(`[name="${k}"]`);
    if (e) { if (e.type === 'checkbox') e.checked = v === '1'; else e.value = v; }
  }
  const current = () => {
    const o = {};
    $$('[name]', tb).forEach(e => { o[e.name] = e.type === 'checkbox' ? (e.checked ? '1' : '') : e.value.trim(); });
    return o;
  };
  async function load() {
    const f = current();
    history.replaceState(null, '', '#/pubs' + (qs(f) ? '?' + qs(f) : ''));
    const list = await GET('ads?' + qs(f));
    $('#count', view).textContent = plural(list.length, 'pub');
    $('#cards', view).innerHTML = list.length ? list.map(adCard).join('') : '<p class="empty">Aucune pub.</p>';
  }
  tb.addEventListener('input', debounce(load, 250));
  tb.addEventListener('change', load);
  $('#new', view).onclick = async () => { const a = await openAdForm(); if (a) location.hash = `#/pubs/${a.id}`; };
  await load();
}

async function pageAd(view, params, id) {
  async function load() {
    const a = await GET(`ads/${id}`);
    view.innerHTML = `
      <div class="page-head"><div><div class="crumbs"><a href="#/pubs">Pubs</a> › #${a.id}</div>
        <h1><a href="#/jeux/${a.game_id}">${esc(a.game_title)}</a> <span class="muted">· ${esc(a.platform_name || 'plateforme ?')}</span></h1>
        <div class="sub">${esc(a.description || 'Sans description')}</div></div>
        <div class="btns"><button type="button" id="edit">✎ Modifier</button><button type="button" class="danger" id="del">Supprimer</button></div></div>
      <div class="grid-detail">
        <div class="card"><h2>Images</h2><div id="imgs"></div></div>
        <div>
          <div class="card"><dl class="info">
            <dt>N° de pub</dt><dd><b>#${a.id}</b></dd>
            <dt>Jeu</dt><dd><a href="#/jeux/${a.game_id}">${esc(a.game_title)}</a> ${a.original_title ? `<span class="muted">${esc(a.original_title)}</span>` : ''}</dd>
            <dt>Série</dt><dd>${esc(a.series_name || '—')}</dd>
            <dt>Plateforme</dt><dd>${esc(a.platform_name || '—')}</dd>
            <dt>Nb de pages</dt><dd>${fmtPages(a.pages) || '—'}</dd>
            <dt>1re parution</dt><dd>${esc(a.first_date || '—')}</dd>
            <dt>Parutions</dt><dd>${a.app_count} (dont ${a.sale_count} en vente)</dd>
            ${a.notes ? `<dt>Remarques</dt><dd>${esc(a.notes)}</dd>` : ''}
          </dl></div>
          <div class="card"><div class="page-head" style="margin-bottom:8px"><h2>Où trouver cette pub</h2>
            <button type="button" class="primary" id="add-app">＋ Ajouter une parution</button></div><div id="apps"></div></div>
        </div>
      </div>`;
    $('#imgs', view).append(galleryBlock(a.images, { entity: 'ads', entityId: a.id, onChange: load, big: true, dropText: 'Ajouter des images de la pub' }));
    $('#apps', view).append(appTable(a.appearances, { hide: ['game', 'ad', 'platform'], onChange: load, emptyText: 'Pas encore repérée dans un magazine.' }));
    $('#edit', view).onclick = async () => { if (await openAdForm(a)) load(); };
    $('#add-app', view).onclick = async () => { if (await openAppearanceForm({ ad_id: a.id })) load(); };
    $('#del', view).onclick = async () => {
      if (!await confirmBox(`Supprimer la pub #${a.id} et ses images ?`)) return;
      await DEL(`ads/${a.id}`);
      invalidate();
      toast('Pub supprimée');
      location.hash = `#/jeux/${a.game_id}`;
    };
  }
  await load();
}

// ---------------------------------------------------------------------------
async function pageGames(view, params) {
  const meta = await getMeta();
  view.innerHTML = `
    <div class="page-head"><div><h1>Jeux</h1></div>
      <div class="btns"><button type="button" class="primary" id="new">＋ Nouveau jeu</button></div></div>
    <div class="toolbar" id="tb">
      <input type="search" name="q" placeholder="Titre, titre original, éditeur…">
      <select name="series_id"><option value="">Toutes séries</option>${meta.series.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('')}</select>
      <span class="muted" id="count"></span>
    </div>
    <div class="card"><div class="table-wrap" id="list"></div></div>`;
  const tb = $('#tb', view);
  for (const [k, v] of Object.entries(params)) { const e = tb.querySelector(`[name="${k}"]`); if (e) e.value = v; }
  let sortKey = 'title', sortDir = 1, list = [];
  function draw() {
    const cols = [['title', 'Titre'], ['series_name', 'Série'], ['platforms', 'Plateformes'], ['publisher', 'Éditeur'], ['year', 'Année', 'num'],
      ['ads_count', 'Pubs', 'num'], ['app_count', 'Parutions', 'num'], ['sale_count', 'En vente', 'num'], ['first_date', '1re parution']];
    const sorted = [...list].sort((a, b) => {
      const x = a[sortKey] ?? '', y = b[sortKey] ?? '';
      return (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), 'fr', { numeric: true })) * sortDir;
    });
    $('#list', view).innerHTML = list.length ? `<table class="data"><thead><tr><th></th>${cols.map(([k, l, c]) =>
      `<th class="${c || ''}" data-k="${k}" style="cursor:pointer">${l}${k === sortKey ? (sortDir > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr></thead>
      <tbody>${sorted.map(g => `<tr class="clickable" data-id="${g.id}"><td class="thumb">${thumbImg(g.thumb_url)}</td>
        <td><b>${esc(g.title)}</b><div class="muted">${esc(g.original_title)}</div></td><td>${esc(g.series_name || '')}</td>
        <td class="muted">${esc(g.platforms || '')}</td><td>${esc(g.publisher)}</td><td class="num">${g.year ?? ''}</td><td class="num">${g.ads_count}</td>
        <td class="num">${g.app_count}</td><td class="num">${g.sale_count}</td><td>${esc(g.first_date || '')}</td></tr>`).join('')}</tbody></table>`
      : '<p class="empty">Aucun jeu.</p>';
  }
  $('#list', view).addEventListener('click', e => {
    const th = e.target.closest('th[data-k]');
    if (th) { sortDir = th.dataset.k === sortKey ? -sortDir : 1; sortKey = th.dataset.k; return draw(); }
    const tr = e.target.closest('tr[data-id]');
    if (tr) location.hash = `#/jeux/${tr.dataset.id}`;
  });
  async function load() {
    const f = { q: $('[name=q]', tb).value.trim(), series_id: $('[name=series_id]', tb).value };
    history.replaceState(null, '', '#/jeux' + (qs(f) ? '?' + qs(f) : ''));
    list = await GET('games?' + qs(f));
    $('#count', view).textContent = plural(list.length, 'jeu', 'jeux');
    draw();
  }
  tb.addEventListener('input', debounce(load, 250));
  tb.addEventListener('change', load);
  $('#new', view).onclick = async () => { const g = await openGameForm(); if (g) location.hash = `#/jeux/${g.id}`; };
  await load();
}

async function pageGame(view, params, id) {
  async function load() {
    const g = await GET(`games/${id}`);
    view.innerHTML = `
      <div class="page-head"><div><div class="crumbs"><a href="#/jeux">Jeux</a></div>
        <h1>${esc(g.title)}</h1><div class="sub">${esc([g.original_title, g.series_name && 'série ' + g.series_name, g.publisher, g.year].filter(Boolean).join(' · '))}</div>
        ${g.platforms ? `<div class="sub">Plateformes (d'après ses pubs) : <b>${esc(g.platforms)}</b></div>` : ''}</div>
        <div class="btns"><button type="button" id="edit">✎ Modifier</button><button type="button" class="danger" id="del">Supprimer</button></div></div>
      <div class="tiles">
        <div class="tile"><div class="n">${g.ads_count}</div><div class="l">pub${g.ads_count > 1 ? 's' : ''} différente${g.ads_count > 1 ? 's' : ''}</div></div>
        <div class="tile"><div class="n">${g.app_count}</div><div class="l">parution${g.app_count > 1 ? 's' : ''}</div></div>
        <div class="tile"><div class="n">${new Set(g.appearances.map(r => r.magazine_id)).size}</div><div class="l">magazine(s)</div></div>
        <div class="tile"><div class="n">${g.sale_count}</div><div class="l">en vente ${MARU}</div></div>
        <div class="tile"><div class="n" style="font-size:18px">${esc(g.first_date || '—')}</div><div class="l">1re parution</div></div>
      </div>
      ${g.notes ? `<div class="card">${esc(g.notes)}</div>` : ''}
      <div class="card"><div class="page-head" style="margin-bottom:8px"><h2>Pubs de ce jeu</h2>
        <button type="button" class="primary" id="new-ad">＋ Nouvelle pub pour ce jeu</button></div>
        <div class="cards">${g.ads.length ? g.ads.map(adCard).join('') : '<p class="empty">Aucune pub pour l\'instant.</p>'}</div></div>
      <div class="card"><h2>Toutes les parutions</h2><div id="apps"></div></div>`;
    $('#apps', view).append(appTable(g.appearances, { hide: ['game'], onChange: load, emptyText: 'Pas encore repéré dans un magazine.' }));
    $('#edit', view).onclick = async () => { if (await openGameForm(g)) load(); };
    $('#new-ad', view).onclick = async () => { const a = await openAdForm({ game_id: g.id }); if (a) load(); };
    $('#del', view).onclick = async () => {
      if (!await confirmBox(`Supprimer le jeu « ${g.title} » ?`)) return;
      await DEL(`games/${g.id}`);
      invalidate();
      toast('Jeu supprimé');
      location.hash = '#/jeux';
    };
  }
  await load();
}

// ---------------------------------------------------------------------------
async function pageMagazines(view) {
  const list = await GET('magazines');
  view.innerHTML = `
    <div class="page-head"><div><h1>Magazines</h1></div>
      <div class="btns"><button type="button" class="primary" id="new">＋ Nouveau magazine</button></div></div>
    <div class="card"><div class="table-wrap">${list.length ? `<table class="data"><thead><tr><th>Magazine</th><th>Éditeur</th><th>Périodicité</th>
      <th class="num">Numéros</th><th class="num">Parutions</th><th class="num">En vente</th><th>Période</th></tr></thead>
      <tbody>${list.map(m => `<tr class="clickable" data-id="${m.id}"><td><b>${esc(m.name)}</b></td><td>${esc(m.publisher)}</td>
        <td>${esc(m.frequency)}</td><td class="num">${m.issues_count}</td><td class="num">${m.app_count}</td><td class="num">${m.sale_count}</td>
        <td class="muted">${m.first_date ? esc(m.first_date) + ' → ' + esc(m.last_date) : ''}</td></tr>`).join('')}</tbody></table>`
      : '<p class="empty">Aucun magazine. Ils peuvent aussi être créés directement depuis la saisie rapide.</p>'}</div></div>`;
  view.addEventListener('click', e => { const tr = e.target.closest('tr[data-id]'); if (tr) location.hash = `#/magazines/${tr.dataset.id}`; });
  $('#new', view).onclick = async () => { const m = await openMagazineForm(); if (m) location.hash = `#/magazines/${m.id}`; };
}

async function pageMagazine(view, params, id) {
  async function load() {
    const m = await GET(`magazines/${id}`);
    view.innerHTML = `
      <div class="page-head"><div><div class="crumbs"><a href="#/magazines">Magazines</a></div><h1>${esc(m.name)}</h1>
        <div class="sub">${esc([m.publisher, m.frequency].filter(Boolean).join(' · '))}</div></div>
        <div class="btns"><a class="btn" href="#/recherche?magazine_id=${m.id}">Toutes ses pubs</a>
          <button type="button" id="edit">✎ Modifier</button><button type="button" class="danger" id="del">Supprimer</button></div></div>
      <div class="tiles">
        <div class="tile"><div class="n">${m.issues_count}</div><div class="l">numéros répertoriés</div></div>
        <div class="tile"><div class="n">${m.app_count}</div><div class="l">parutions de pubs</div></div>
        <div class="tile"><div class="n">${m.sale_count}</div><div class="l">en vente ${MARU}</div></div>
      </div>
      ${m.notes ? `<div class="card">${esc(m.notes)}</div>` : ''}
      <div class="card"><div class="page-head" style="margin-bottom:8px"><h2>Numéros</h2>
        <button type="button" class="primary" id="new-issue">＋ Nouveau numéro</button></div>
        <div class="table-wrap">${m.issues.length ? `<table class="data"><thead><tr><th></th><th>Numéro</th><th>Date</th>
          <th class="num">Pubs</th><th class="num">En vente</th><th>Remarques</th></tr></thead>
          <tbody>${m.issues.map(i => `<tr class="clickable" data-id="${i.id}"><td class="thumb">${thumbImg(i.thumb_url)}</td>
            <td><b>n°${esc(i.number)}</b></td><td>${esc(i.date || '—')}</td><td class="num">${i.app_count}</td>
            <td class="num">${i.sale_count}</td><td class="notes">${esc(i.notes)}</td></tr>`).join('')}</tbody></table>`
          : '<p class="empty">Aucun numéro.</p>'}</div></div>`;
    $('.card .table-wrap', view)?.addEventListener('click', e => { const tr = e.target.closest('tr[data-id]'); if (tr) location.hash = `#/numeros/${tr.dataset.id}`; });
    $('#edit', view).onclick = async () => { if (await openMagazineForm(m)) load(); };
    $('#new-issue', view).onclick = async () => { const i = await openIssueForm({ magazine_id: m.id }); if (i) location.hash = `#/numeros/${i.id}`; };
    $('#del', view).onclick = async () => {
      if (!await confirmBox(`Supprimer le magazine « ${m.name} » ?`)) return;
      await DEL(`magazines/${m.id}`);
      invalidate();
      location.hash = '#/magazines';
    };
  }
  await load();
}

async function pageIssue(view, params, id) {
  async function load() {
    const i = await GET(`issues/${id}`);
    view.innerHTML = `
      <div class="page-head"><div><div class="crumbs"><a href="#/magazines">Magazines</a> › <a href="#/magazines/${i.magazine_id}">${esc(i.magazine_name)}</a></div>
        <h1>${esc(i.magazine_name)} n°${esc(i.number)}</h1><div class="sub">${i.date ? 'Paru le ' + esc(i.date) : 'Date inconnue'}
        · ${plural(i.app_count, 'pub référencée', 'pubs référencées')}</div></div>
        <div class="btns"><a class="btn primary" href="#/saisie?issue=${i.id}">＋ Saisir des pubs dans ce numéro</a>
          <button type="button" id="edit">✎ Modifier</button><button type="button" class="danger" id="del">Supprimer</button></div></div>
      <div class="grid-detail">
        <div class="card"><h2>Couverture</h2><div id="imgs"></div></div>
        <div class="card"><h2>Pubs dans ce numéro</h2><div id="apps"></div></div>
      </div>`;
    $('#imgs', view).append(galleryBlock(i.images, { entity: 'issues', entityId: i.id, onChange: load, big: true, dropText: 'Ajouter la couverture' }));
    $('#apps', view).append(appTable(i.appearances, { hide: ['issue'], onChange: load, emptyText: 'Aucune pub saisie.' }));
    $('#edit', view).onclick = async () => { if (await openIssueForm(i)) load(); };
    $('#del', view).onclick = async () => {
      if (!await confirmBox(`Supprimer ${i.magazine_name} n°${i.number} ?`)) return;
      await DEL(`issues/${i.id}`);
      invalidate();
      location.hash = `#/magazines/${i.magazine_id}`;
    };
  }
  await load();
}

// ---------------------------------------------------------------------------
async function pageLists(view) {
  const [series, platforms] = await Promise.all([GET('series'), GET('platforms')]);
  const block = (title, table, list, extraField) => `
    <div class="card"><h2>${title}</h2>
      <form class="toolbar" data-table="${table}"><input name="name" placeholder="Nom" required style="max-width:220px">
        ${extraField ? `<input name="${extraField[0]}" placeholder="${extraField[1]}" style="max-width:160px">` : ''}
        <button type="submit" class="primary">Ajouter</button></form>
      <div class="table-wrap"><table class="data"><thead><tr><th>Nom</th>${extraField ? `<th>${extraField[1]}</th>` : ''}
        ${table === 'series' ? '<th class="num">Jeux</th>' : ''}<th class="num">Pubs</th><th class="num">Parutions</th><th></th></tr></thead>
      <tbody>${list.map(x => `<tr data-id="${x.id}" data-table="${table}"><td><b>${esc(x.name)}</b></td>
        ${extraField ? `<td>${esc(x[extraField[0]])}</td>` : ''}${table === 'series' ? `<td class="num">${x.games_count}</td>` : ''}
        <td class="num">${x.ads_count}</td><td class="num"><a href="#/recherche?${table === 'series' ? 'series_id' : 'platform_id'}=${x.id}">${x.app_count}</a></td>
        <td class="row-actions"><button type="button" class="icon" data-act="edit" title="Renommer">✎</button>
        <button type="button" class="icon" data-act="del" title="Supprimer">🗑</button></td></tr>`).join('')}</tbody></table></div></div>`;
  view.innerHTML = `<div class="page-head"><div><h1>Séries &amp; plateformes</h1>
      <div class="sub">Listes utilisées par les jeux et les pubs.</div></div></div>
    <div class="grid-2">${block('Séries', 'series', series)}${block('Plateformes', 'platforms', platforms, ['maker', 'Constructeur'])}</div>`;
  view.addEventListener('submit', async e => {
    e.preventDefault();
    const f = e.target;
    const data = Object.fromEntries(new FormData(f));
    try {
      await POST(f.dataset.table, data);
      invalidate();
      toast('Ajouté');
      render();
    } catch (ex) { toast(ex.message, 'err'); }
  });
  view.addEventListener('click', async e => {
    const b = e.target.closest('button[data-act]');
    if (!b) return;
    const tr = b.closest('tr');
    const table = tr.dataset.table, id = tr.dataset.id;
    const list = table === 'series' ? series : platforms;
    const x = list.find(r => String(r.id) === id);
    if (b.dataset.act === 'del') {
      if (!await confirmBox(`Supprimer « ${x.name} » ? Les jeux / pubs concernés n'auront simplement plus de ${table === 'series' ? 'série' : 'plateforme'}.`)) return;
      await DEL(`${table}/${id}`);
    } else {
      const fields = [{ name: 'name', label: 'Nom', required: true, wide: true }];
      if (table === 'platforms') fields.push({ name: 'maker', label: 'Constructeur', wide: true });
      fields.push({ name: 'notes', label: 'Remarques', type: 'textarea', wide: true });
      const r = await formModal({ title: 'Modifier', fields, values: x, onSubmit: d => PUT(`${table}/${id}`, d) });
      if (!r) return;
    }
    invalidate();
    render();
  });
}

// ---------------------------------------------------------------------------
async function pageExport(view) {
  const exports = [['apparitions', 'Toutes les parutions (la liste complète, une ligne par pub trouvée)'],
    ['pubs', 'Pubs'], ['jeux', 'Jeux'], ['magazines', 'Magazines'], ['numeros', 'Numéros'],
    ['series', 'Séries'], ['plateformes', 'Plateformes']];
  view.innerHTML = `
    <div class="page-head"><div><h1>Export, sauvegarde &amp; téléphone</h1></div></div>
    <div class="grid-2">
      <div class="card"><h2>Exports Excel (CSV)</h2>
        <p class="muted">Fichiers CSV (séparateur « ; ») qui s'ouvrent directement dans Excel ou LibreOffice.
        Pour exporter une sélection précise, utilisez le bouton Export de la page <a href="#/recherche">Recherche</a>.</p>
        <ul class="list-mini">${exports.map(([k, l]) => `<li><span class="grow">${l}</span><a class="btn" href="${withProj(`/api/export/${k}.csv`)}">⬇ ${k}.csv</a></li>`).join('')}</ul></div>
      <div class="card"><h2>Sauvegarde complète</h2>
        <p>Un fichier ZIP avec la base et toutes les images. À faire régulièrement et à garder ailleurs (clé USB, cloud…).</p>
        <p><a class="btn primary" href="${withProj('/api/sauvegarde.zip')}">⬇ Télécharger la sauvegarde de ce projet</a></p>
        <p class="muted">Pour exporter ou importer un projet en particulier, ou créer le projet de démonstration :
        page <a href="#/projets">Projets</a> (menu 📁 en haut à gauche).</p>
        <h3 style="margin-top:18px">Où sont les données ?</h3>
        <p class="muted">Tout est dans le dossier <b>data</b> à côté de l'application : la base (<code>bdd_pubs.sqlite</code>),
        les images et leurs miniatures. Une copie de la base est aussi faite automatiquement à chaque démarrage
        dans <code>data/sauvegardes</code> (15 dernières).</p>
        <h3 style="margin-top:18px">Restaurer / changer d'ordinateur</h3>
        <p class="muted">Fermer l'application, dézipper la sauvegarde à côté de l'application (elle contient le dossier <b>data</b>)
        en remplaçant l'existant, puis relancer.</p></div>
      <div class="card"><h2>Accès depuis le téléphone</h2>
        <p class="muted">Pour saisir ou prendre les pubs en photo avec le téléphone, connecté au même Wi-Fi que l'ordinateur.
        Pas de mot de passe : à n'activer que sur un réseau de confiance (maison).</p>
        <label class="check" style="display:flex;gap:8px;align-items:center;font-weight:600">
          <input type="checkbox" id="net"> Rendre l'application accessible depuis le téléphone</label>
        <div id="net-info" style="margin-top:10px"></div></div>
    </div>`;
  const box = $('#net', view), info = $('#net-info', view);
  const show = st => {
    box.checked = st.actif;
    box.disabled = st.force;
    info.innerHTML = st.actif
      ? (st.url ? `Sur le téléphone, ouvrir : <b style="font-size:18px">${esc(st.url)}</b>
          <br><small class="muted">Si Windows demande l'autorisation du pare-feu, cliquer sur « Autoriser ».
          L'ordinateur doit rester allumé avec l'application ouverte.</small>` : 'Adresse réseau introuvable.')
      : '';
  };
  show(await GET('reseau'));
  box.addEventListener('change', async () => {
    try { show(await POST('reseau', { actif: box.checked })); }
    catch (e) { toast(e.message, 'err'); box.checked = false; }
  });
}

// ---------------------------------------------------------------------------
const openProject = id => { location.href = `/p/${encodeURIComponent(id)}/#/`; };

async function pageProjects(view) {
  const info = await GET('projets');
  const cur = info.projets.find(p => p.actuel);
  view.innerHTML = `
    <div class="page-head"><div><h1>Projets</h1>
      <div class="sub">Chaque projet est une base séparée (ses jeux, pubs, magazines et images).
      Au lancement, l'application ouvre toujours le projet marqué « ouvert au lancement ».</div></div>
      <div class="btns">
        <button type="button" class="primary" id="new">＋ Nouveau projet</button>
        <button type="button" id="demo">＋ Projet de démonstration</button>
        <button type="button" id="import">⬆ Importer un projet (.zip)</button>
        <input type="file" id="import-file" accept=".zip,application/zip" hidden>
      </div></div>
    <div class="card"><div class="table-wrap"><table class="data"><thead><tr><th>Projet</th><th>Contenu</th><th></th></tr></thead>
      <tbody>${info.projets.map(p => `<tr data-id="${esc(p.id)}">
        <td><b>${esc(p.nom)}</b>
          ${p.actuel ? '<span class="badge">projet affiché</span>' : ''}
          ${p.defaut ? '<span class="badge gray">ouvert au lancement</span>' : ''}</td>
        <td class="muted">${p.stats ? `${plural(p.stats.ads, 'pub')} · ${plural(p.stats.appearances, 'parution')} · ${plural(p.stats.games, 'jeu', 'jeux')}` : 'base illisible'}</td>
        <td class="row-actions">
          ${p.actuel ? '' : '<button type="button" class="primary" data-act="open">Ouvrir</button>'}
          <button type="button" data-act="rename">Renommer</button>
          ${p.defaut ? '' : '<button type="button" data-act="default" title="Ouvrir ce projet au lancement de l\'application">★ Au lancement</button>'}
          <a class="btn" href="/api/projets/${encodeURIComponent(p.id)}/export.zip" title="ZIP de ce projet seul (base + images)">⬇ Exporter</a>
          ${p.protege || p.defaut ? '' : '<button type="button" class="danger" data-act="del">Supprimer</button>'}
        </td></tr>`).join('')}</tbody></table></div></div>
    <div class="card"><h2>Bon à savoir</h2><ul class="muted" style="margin:0;padding-left:18px">
      <li><b>Exporter</b> crée un ZIP avec la base et les images du projet : pour le garder de côté, l'envoyer à quelqu'un,
        ou le retrouver sur un autre ordinateur avec <b>Importer</b>.</li>
      <li>Le <b>projet de démonstration</b> contient quelques exemples fictifs, pour essayer sans toucher à vos données.</li>
      <li>Le projet de base (${esc(info.projets.find(p => p.protege).nom)}) ne peut pas être supprimé, mais peut être renommé.</li>
      <li>Chaque onglet reste sur son projet : on peut en ouvrir deux côte à côte.</li></ul></div>`;

  const ask = (title, value = '') => formModal({
    title, values: { nom: value }, submitLabel: 'Valider',
    fields: [{ name: 'nom', label: 'Nom du projet', required: true, wide: true }],
    onSubmit: d => d,
  });
  $('#new', view).onclick = async () => {
    const d = await ask('Nouveau projet');
    if (!d) return;
    const p = await POST('projets', { nom: d.nom });
    toast(`Projet « ${p.nom} » créé`);
    openProject(p.id);
  };
  $('#demo', view).onclick = async () => {
    const existing = info.projets.filter(p => /^d[ée]mo/i.test(p.nom)).length;
    const p = await POST('projets', { nom: existing ? `Démo ${existing + 1}` : 'Démo', demo: true });
    toast(`Projet « ${p.nom} » créé`);
    openProject(p.id);
  };
  const fileI = $('#import-file', view);
  $('#import', view).onclick = () => fileI.click();
  fileI.onchange = async () => {
    const f = fileI.files[0];
    fileI.value = '';
    if (!f) return;
    toast('Import en cours…');
    const r = await fetch('/api/projets/import', { method: 'POST', headers: { 'Content-Type': 'application/zip' }, body: f });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return toast(data.error || `Erreur ${r.status}`, 'err');
    toast(`Projet « ${data.nom} » importé`);
    render();
  };
  view.addEventListener('click', async e => {
    const b = e.target.closest('button[data-act]');
    if (!b) return;
    const p = info.projets.find(x => x.id === b.closest('tr').dataset.id);
    const act = b.dataset.act;
    if (act === 'open') return openProject(p.id);
    if (act === 'rename') {
      const d = await ask('Renommer le projet', p.nom);
      if (!d) return;
      await PUT(`projets/${p.id}`, { nom: d.nom });
    } else if (act === 'default') {
      await PUT(`projets/${p.id}`, { defaut: true });
      toast(`« ${p.nom} » s'ouvrira au lancement`);
    } else if (act === 'del') {
      if (!await confirmBox(`Supprimer définitivement le projet « ${p.nom} », ses données et ses images ? Pensez à l'exporter avant si besoin.`)) return;
      await DEL(`projets/${p.id}`);
      toast('Projet supprimé');
    }
    await drawProjectSwitcher();
    render();
  });
}

// Sélecteur de projet dans l'en-tête
async function drawProjectSwitcher() {
  const box = $('#proj');
  let info;
  try { info = await GET('projets'); } catch (_) { return; }
  const cur = info.projets.find(p => p.actuel) || info.projets.find(p => p.defaut);
  if (PROJ && !info.projets.some(p => p.id === PROJ)) {
    box.innerHTML = '<a class="btn" href="/">Projet introuvable : revenir au projet principal</a>';
    return;
  }
  box.innerHTML = `<button type="button" class="proj-btn ${cur.defaut ? '' : 'other'}" title="Changer de projet">
      📁 <b>${esc(cur.nom)}</b> ▾</button>
    <div class="proj-menu" hidden>
      ${info.projets.map(p => `<button type="button" data-id="${esc(p.id)}" class="${p.actuel ? 'sel' : ''}">${p.actuel ? '✓ ' : ''}${esc(p.nom)}
        ${p.defaut ? '<small class="muted">(lancement)</small>' : ''}</button>`).join('')}
      <a href="#/projets">Gérer les projets…</a></div>`;
  document.title = cur.defaut ? 'BDD Pubs' : `BDD Pubs · ${cur.nom}`;
  const menu = $('.proj-menu', box);
  $('.proj-btn', box).onclick = e => { e.stopPropagation(); menu.hidden = !menu.hidden; };
  menu.onclick = e => {
    const b = e.target.closest('button[data-id]');
    menu.hidden = true;
    if (b && !b.classList.contains('sel')) openProject(b.dataset.id);
  };
}
document.addEventListener('click', () => { const m = $('.proj-menu'); if (m) m.hidden = true; });

// ===========================================================================
// Routeur
// ===========================================================================
const ROUTES = [
  [/^\/?$/, pageHome, 'accueil'],
  [/^\/saisie$/, pageEntry, 'saisie'],
  [/^\/recherche$/, pageSearch, 'recherche'],
  [/^\/pubs$/, pageAds, 'pubs'],
  [/^\/pubs\/(\d+)$/, pageAd, 'pubs'],
  [/^\/jeux$/, pageGames, 'jeux'],
  [/^\/jeux\/(\d+)$/, pageGame, 'jeux'],
  [/^\/magazines$/, pageMagazines, 'magazines'],
  [/^\/magazines\/(\d+)$/, pageMagazine, 'magazines'],
  [/^\/numeros\/(\d+)$/, pageIssue, 'magazines'],
  [/^\/listes$/, pageLists, 'listes'],
  [/^\/export$/, pageExport, 'export'],
  [/^\/projets$/, pageProjects, 'projets'],
];

let renderToken = 0;
async function render() {
  const token = ++renderToken;
  const raw = location.hash.slice(1) || '/';
  const [path, query] = raw.split('?');
  const params = Object.fromEntries(new URLSearchParams(query || ''));
  while (overlays.length) overlays[overlays.length - 1]._close();
  const main = $('#main');
  const route = ROUTES.find(([re]) => re.test(path));
  $$('#nav a').forEach(a => a.classList.toggle('active', !!route && a.dataset.nav === route[2]));
  if (!route) { main.innerHTML = '<div class="error-box">Page introuvable. <a href="#/">Retour à l\'accueil</a></div>'; return; }
  const view = el('div');
  try {
    await route[1](view, params, ...path.match(route[0]).slice(1));
    if (token !== renderToken) return;
    main.replaceChildren(view);
    window.scrollTo(0, 0);
  } catch (e) {
    if (token !== renderToken) return;
    main.innerHTML = `<div class="error-box">${esc(e.message)}</div>`;
  }
}
window.addEventListener('hashchange', render);
render();
drawProjectSwitcher();

// ===========================================================================
// Présence : vérifie régulièrement que l'application tourne (et si une nouvelle
// version a été lancée). Elle ne s'arrête qu'avec le bouton « Quitter ».
// ===========================================================================
const TAB_ID = Math.random().toString(36).slice(2) + Date.now().toString(36);
let stoppedShown = false;
let SERVER_BUILD = null;

let stoppedOverlay = null, reconnectTimer = null;
function showStopped(text) {
  if (stoppedShown) return;
  stoppedShown = true;
  stoppedOverlay = el('div', 'overlay stopped', `<div class="modal"><header><h2>BDD Pubs est arrêtée</h2></header>
    <div class="modal-body"><p style="margin-top:0">${esc(text)}</p>
    <p class="muted">Dès que l'application est relancée, cette page se reconnecte toute seule.</p>
    <div class="actions"><button type="button" class="primary" data-retry>Réessayer</button></div></div></div>`);
  $('[data-retry]', stoppedOverlay).onclick = () => heartbeat();
  document.body.append(stoppedOverlay);
  reconnectTimer = setInterval(() => heartbeat(), 5000); // reconnexion automatique
}
function hideStopped() {
  if (!stoppedShown) return;
  stoppedShown = false;
  clearInterval(reconnectTimer);
  stoppedOverlay.remove();
  invalidate();
  render();
  drawProjectSwitcher();
}

async function heartbeat() {
  try {
    const r = await fetch('/api/ping', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tab: TAB_ID }),
    });
    const info = await r.json().catch(() => ({})); // lire la réponse libère la connexion
    if (info.build) {
      if (!SERVER_BUILD) SERVER_BUILD = info.build;
      else if (info.build !== SERVER_BUILD && !$('.update-bar')) {
        const bar = el('div', 'update-bar', `Une nouvelle version de BDD Pubs a été lancée.
          <button type="button" class="primary">Recharger la page</button>`);
        $('button', bar).onclick = () => location.reload();
        document.body.prepend(bar);
      }
    }
    if (r.ok) hideStopped();
    return r.ok;
  } catch (_) {
    showStopped('Pour la relancer : double-clic sur « BDD Pubs ».');
    return false;
  }
}
heartbeat();
setInterval(() => { if (!stoppedShown) heartbeat(); }, 20000);
document.addEventListener('visibilitychange', () => { if (!document.hidden && !stoppedShown) heartbeat(); });
window.addEventListener('pagehide', () => {
  navigator.sendBeacon('/api/bye', new Blob([JSON.stringify({ tab: TAB_ID })], { type: 'text/plain' }));
});

$('#quit').addEventListener('click', async () => {
  if (!await confirmBox('Arrêter l\'application ? Vous pourrez la relancer d\'un double-clic sur « BDD Pubs ». '
    + '(Fermer l\'onglet ne l\'arrête pas : elle reste disponible sur cette adresse.)', 'Quitter')) return;
  try { await POST('quitter', {}); } catch (_) { /* déjà arrêtée */ }
  await new Promise(r => setTimeout(r, 400));
  showStopped('Vous l\'avez arrêtée avec « Quitter ». Vous pouvez fermer cet onglet.');
});
