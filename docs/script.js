// =================================================
// fbchat-v2 · Editorial Docs — v3.0
// =================================================

// ---------- DOM ----------
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebarOverlay');
const menuBtn = document.getElementById('menuBtn');
const backToTop = document.getElementById('backToTop');
const searchInput = document.getElementById('searchInput');
const allSections = document.querySelectorAll('.doc-section');
const allLinks = document.querySelectorAll('.sidebar__link[data-section]');

// Star progress
const starProgressEl = document.getElementById('starProgress');
const starProgressFill = document.getElementById('starProgressFill');
const starProgressPercent = document.getElementById('starProgressPercent');
const starCountCurrent = document.getElementById('starCountCurrent');
const starCountTarget = document.getElementById('starCountTarget');
const starProgressTrack = document.querySelector('.star-progress__track');

const STAR_TARGET = 199;
const STAR_CACHE_KEY = 'fbchatv2:stars';
const STAR_CACHE_TTL = 10 * 60 * 1000; // 10 phút
const STAR_FETCH_TIMEOUT = 6000; // 6 giây
let githubStars = 0;

// Language
const langToggleBtn = document.getElementById('langToggle');
const currentLangText = document.getElementById('currentLang');
const fileTreeComments = document.querySelectorAll('.file-tree-comment');

let currentLang = localStorage.getItem('lang') || 'vi';
document.documentElement.lang = currentLang;

function updateLangUI() {
  document.documentElement.lang = currentLang;
  if (currentLang === 'vi') {
    currentLangText.textContent = 'VI';
    searchInput.placeholder = 'Tìm kiếm...';
  } else {
    currentLangText.textContent = 'EN';
    searchInput.placeholder = 'Search...';
  }
}

function updateFileTreeComments() {
  fileTreeComments.forEach((c) => {
    const text = currentLang === 'vi' ? c.dataset.vi : c.dataset.en;
    if (text) c.textContent = text;
  });
}

function formatCount(value) {
  const locale = currentLang === 'vi' ? 'vi-VN' : 'en-US';
  return new Intl.NumberFormat(locale).format(value);
}

let lastStarRendered = 0;
let starCountUpRAF = null;

function animateCountUp(el, fromVal, toVal, duration = 1100) {
  if (!el) return;
  if (starCountUpRAF) cancelAnimationFrame(starCountUpRAF);
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    el.textContent = formatCount(toVal);
    return;
  }
  const start = performance.now();
  const delta = toVal - fromVal;
  const easeOut = (t) => 1 - Math.pow(1 - t, 3);
  const step = (now) => {
    const t = Math.min(1, (now - start) / duration);
    const val = Math.round(fromVal + delta * easeOut(t));
    el.textContent = formatCount(val);
    if (t < 1) starCountUpRAF = requestAnimationFrame(step);
  };
  starCountUpRAF = requestAnimationFrame(step);
}

function renderStarProgress(stars) {
  if (!starProgressFill || !starProgressPercent || !starCountCurrent || !starCountTarget || !starProgressTrack) return;
  const safe = Number.isFinite(stars) ? Math.max(0, stars) : 0;
  const target = Math.max(STAR_TARGET, 1);
  const pct = Math.min((safe / target) * 100, 100);

  // Delay nhỏ để browser paint state cũ trước -> transition width mượt hơn
  requestAnimationFrame(() => {
    starProgressFill.style.width = `${pct.toFixed(2)}%`;
  });

  starProgressPercent.textContent = `${Math.round(pct)}%`;
  animateCountUp(starCountCurrent, lastStarRendered, safe, 1100);
  starCountTarget.textContent = formatCount(target);
  starProgressTrack.setAttribute('aria-valuemax', String(target));
  starProgressTrack.setAttribute('aria-valuenow', String(safe));

  if (starProgressEl) {
    starProgressEl.classList.remove('star-progress--offline');
    // Trigger pulse: remove rồi add lại để animation replay
    starProgressEl.classList.remove('star-progress--updated');
    // eslint-disable-next-line no-unused-expressions
    void starProgressEl.offsetWidth;
    starProgressEl.classList.add('star-progress--updated');
    setTimeout(() => {
      if (starProgressEl) starProgressEl.classList.remove('star-progress--updated');
    }, 650);
  }

  lastStarRendered = safe;
}

function markStarProgressOffline() {
  if (starProgressEl) starProgressEl.classList.add('star-progress--offline');
  if (starProgressPercent && starProgressPercent.textContent === '0%') {
    starProgressPercent.textContent = '—';
  }
}

function readStarCache() {
  try {
    const raw = localStorage.getItem(STAR_CACHE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || typeof data.stars !== 'number') return null;
    return data;
  } catch { return null; }
}

function writeStarCache(stars) {
  try {
    localStorage.setItem(STAR_CACHE_KEY, JSON.stringify({ stars, ts: Date.now() }));
  } catch { /* ignore quota / private mode */ }
}

async function fetchGithubStars() {
  // 1) Luôn render cache trước (nếu có) để UI không bao giờ đứng ở 0%
  const cached = readStarCache();
  if (cached) {
    githubStars = cached.stars;
    renderStarProgress(githubStars);
    // Nếu cache còn tươi, bỏ qua request mạng
    if (Date.now() - cached.ts < STAR_CACHE_TTL) return;
  }

  // 2) Bảo vệ bằng AbortController + timeout
  const ctrl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
  const timer = ctrl ? setTimeout(() => ctrl.abort(), STAR_FETCH_TIMEOUT) : null;

  try {
    if (typeof fetch !== 'function') throw new Error('fetch unsupported');
    const res = await fetch('https://api.github.com/repos/MinhHuyDev/fbchat-v2', {
      headers: { Accept: 'application/vnd.github+json' },
      signal: ctrl ? ctrl.signal : undefined,
      cache: 'no-store'
    });
    if (!res.ok) throw new Error(`GitHub API ${res.status}`);
    const data = await res.json();
    const count = Number(data.stargazers_count);
    if (!Number.isFinite(count)) throw new Error('invalid response');
    githubStars = count;
    writeStarCache(count);
    renderStarProgress(count);
  } catch (err) {
    // Giữ lại số cũ từ cache nếu có, không đặt về 0
    if (cached) {
      renderStarProgress(cached.stars);
    } else {
      renderStarProgress(0);
      markStarProgressOffline();
    }
    // Log nhẹ để dev thấy khi F12, không làm phiền user
    if (typeof console !== 'undefined' && console.warn) {
      console.warn('[star-progress] fetch failed:', err && err.message ? err.message : err);
    }
  } finally {
    if (timer) clearTimeout(timer);
  }
}

updateLangUI();
updateFileTreeComments();
renderStarProgress(githubStars);
fetchGithubStars();

langToggleBtn.addEventListener('click', () => {
  currentLang = currentLang === 'vi' ? 'en' : 'vi';
  localStorage.setItem('lang', currentLang);
  updateLangUI();
  updateFileTreeComments();
  renderStarProgress(githubStars);
});

// ---------- NAVIGATION ----------
function navigateTo(sectionId) {
  allSections.forEach(s => s.setAttribute('hidden', ''));
  const target = document.getElementById(sectionId);
  if (target) {
    target.removeAttribute('hidden');
    target.style.animation = 'none';
    target.offsetHeight;
    target.style.animation = '';
  }
  allLinks.forEach(l => l.classList.toggle('active', l.dataset.section === sectionId));
  window.scrollTo({ top: 0, behavior: 'smooth' });
  closeSidebar();
  history.replaceState(null, '', '#' + sectionId);
}

allLinks.forEach(link => {
  link.addEventListener('click', (e) => {
    e.preventDefault();
    navigateTo(link.dataset.section);
  });
});

// ---------- MOBILE SIDEBAR ----------
function openSidebar() {
  sidebar.classList.add('open');
  sidebarOverlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeSidebar() {
  sidebar.classList.remove('open');
  sidebarOverlay.classList.remove('open');
  document.body.style.overflow = '';
}
menuBtn.addEventListener('click', () => {
  sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
});
sidebarOverlay.addEventListener('click', closeSidebar);

// ---------- MODULE CARD TOGGLE ----------
document.querySelectorAll('.module-card').forEach(card => {
  card.addEventListener('click', (e) => {
    // Ignore clicks on copy buttons / links inside
    if (e.target.closest('.code-block__copy') || e.target.closest('a')) return;
    card.classList.toggle('active');
    const code = card.querySelector('.module-card__code');
    if (code) {
      card.classList.contains('active') ? code.removeAttribute('hidden') : code.setAttribute('hidden', '');
    }
  });
});

// ---------- SCROLL ----------
window.addEventListener('scroll', () => {
  backToTop.classList.toggle('visible', window.scrollY > 400);
}, { passive: true });

backToTop.addEventListener('click', () => {
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

// ---------- COPY CODE ----------
document.addEventListener('click', (e) => {
  const btn = e.target.closest('.code-block__copy');
  if (!btn) return;
  e.stopPropagation();
  const code = btn.closest('.code-block').querySelector('code');
  navigator.clipboard.writeText(code.textContent).then(() => {
    btn.textContent = '✓ Copied';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.textContent = 'Copy';
      btn.classList.remove('copied');
    }, 2000);
  });
});

// ---------- SEARCH ----------
searchInput.addEventListener('input', (e) => {
  const q = e.target.value.toLowerCase().trim();
  allLinks.forEach(link => {
    const text = link.textContent.toLowerCase();
    if (!q || text.includes(q)) {
      link.style.display = '';
    } else {
      link.style.display = 'none';
    }
  });
});

// ---------- INITIAL ROUTE ----------
function handleInitialRoute() {
  const hash = window.location.hash.slice(1);
  if (hash && document.getElementById(hash)) navigateTo(hash);
  else navigateTo('overview');
}

// ---------- KEYBOARD ----------
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    searchInput.focus();
  }
  if (e.key === 'Escape') {
    closeSidebar();
    searchInput.blur();
  }
});

document.addEventListener('DOMContentLoaded', handleInitialRoute);
window.addEventListener('hashchange', () => {
  const hash = window.location.hash.slice(1);
  if (hash && document.getElementById(hash)) navigateTo(hash);
});
