// 새 소식: date-by-date release notes from data/releases.json, opened from the title card and the pause menu.
// A red dot marks the buttons until the newest entry has been opened once (per browser).
import { $, safeGet, safeSet, versioned } from './util.js';

// items: string | { text, items: [...] } (sublists nest to any depth)
function renderItems(items) {
  const ul = document.createElement('ul');
  for (const it of items) {
    const li = document.createElement('li');
    if (typeof it === 'string') li.textContent = it;
    else { li.append(it.text || ''); if (it.items?.length) li.appendChild(renderItems(it.items)); }
    ul.appendChild(li);
  }
  return ul;
}

export async function setupNews(onOpen = () => {}, onClose = () => {}) {
  let notes = [];
  try { notes = await fetch(versioned('data/releases.json')).then((r) => r.json()); } catch { return; }
  if (!notes.length) return;
  const latest = notes[0].date;
  const dots = document.querySelectorAll('.newsbtn i');
  const mark = () => dots.forEach((d) => { d.hidden = safeGet('y97-news') === latest; });
  mark();
  const root = $('#news'), list = root.querySelector('.list');
  list.innerHTML = '';
  for (const n of notes) {
    const sec = document.createElement('section');
    const h = document.createElement('h3');
    const d = document.createElement('span');
    const [y, m, day] = n.date.split('-').map(Number);
    d.textContent = `${y}년 ${m}월 ${day}일`;
    h.append(d, n.title || '');
    const ul = renderItems(n.items);
    sec.id = n.date;
    sec.append(h, ul);
    for (const im of n.images || []) {
      const fig = document.createElement('figure');
      fig.className = 'shot';
      const img = document.createElement('img');
      img.src = versioned(im.src); img.alt = im.alt || ''; img.loading = 'lazy';
      const cap = document.createElement('figcaption');
      cap.textContent = im.alt || '';
      fig.append(img, cap);
      sec.appendChild(fig);
    }
    list.appendChild(sec);
  }
  const close = () => { root.hidden = true; onClose(); };
  document.querySelectorAll('.newsbtn').forEach((b) => b.addEventListener('click', (e) => {
    e.stopPropagation();
    b.blur();
    root.hidden = false;
    safeSet('y97-news', latest);
    mark();
    onOpen();
  }));
  root.querySelector('.close').addEventListener('click', close);
  root.addEventListener('click', (e) => { if (e.target === root) close(); });
  addEventListener('keydown', (e) => { if (!root.hidden && e.code === 'Escape') { e.stopImmediatePropagation(); close(); } }, true);
}
