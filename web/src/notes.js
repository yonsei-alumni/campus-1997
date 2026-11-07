// 새 소식 entries (data/releases.json) as DOM, shared by the in-game panel (news.js) and the news page (news.html).
// No imports: the news page loads only this file, not the game.

// items: string | { text, items: [...] } (sublists nest to any depth)
export function renderItems(items) {
  const ul = document.createElement('ul');
  for (const it of items) {
    const li = document.createElement('li');
    if (typeof it === 'string') li.textContent = it;
    else { li.append(it.text || ''); if (it.items?.length) li.appendChild(renderItems(it.items)); }
    ul.appendChild(li);
  }
  return ul;
}

// one dated entry: <section id="2026-11-06"><h3><span>2026년 11월 6일</span>title</h3><ul>…</ul><figure class="shot">…
// heading: the title's tag; link: the title is a #date link to itself; src: maps each capture's URL
export function noteSection(n, { heading = 'h3', link = false, src = (u) => u } = {}) {
  const sec = document.createElement('section');
  sec.id = n.date;
  const h = document.createElement(heading);
  const date = document.createElement('span');
  const [y, m, d] = n.date.split('-').map(Number);
  date.textContent = `${y}년 ${m}월 ${d}일`;
  const title = link ? h.appendChild(Object.assign(document.createElement('a'), { href: '#' + n.date })) : h;
  title.append(date, n.title || '');
  sec.append(h, renderItems(n.items));
  for (const im of n.images || []) {
    const fig = document.createElement('figure');
    fig.className = 'shot';
    const img = document.createElement('img');
    img.src = src(im.src); img.alt = im.alt || ''; img.loading = 'lazy';
    const cap = document.createElement('figcaption');
    cap.textContent = im.alt || '';
    fig.append(img, cap);
    sec.appendChild(fig);
  }
  return sec;
}
