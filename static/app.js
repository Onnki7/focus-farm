// ── State ─────────────────────────────────────────────────────────────────────
let state = {
  loggedIn: false, username: "", userId: null,
  running: false, sessionId: null, sLeft: 0, totalS: 0, dur: 25,
  sessions: 0, totalMins: 0, streak: 0, tiles: 0,
  interval: null, squadPoll: null,
  unlockedTiles: [], highlight: -1,
  chart: null,
  honestyChart: null,  // 成员3新增
};
const CIRC = 263.9;

// ── Tile data ─────────────────────────────────────────────────────────────────
const TILE_TYPES = [
  'soil','sprout','crop','wheat','fence','barn','well','pond',
  'silo','greenhouse','mill','orchard','stable','beehive','trough',
  'market','cottage','treeline','fountain','manor'
];
const TILE_NAMES = [
  "Soil patch cleared","Sprout appeared","Crop row planted","Wheat field grown",
  "Fence erected","Barn built","Well dug","Pond filled",
  "Silo raised","Greenhouse assembled","Windmill constructed","Orchard planted",
  "Stable completed","Beehive placed","Trough installed","Market stall opened",
  "Cottage built","Tree line planted","Fountain carved","Manor established"
];
const TILE_BG = [
  '#e8dcc8','#d4e8b8','#b8d890','#90c860','#f0e0a0','#e8c880','#c0d8f0','#a0c8e8',
  '#f0d0a8','#d8c0f0','#f8e0b0','#c8e8c8','#e8d0b0','#b0d8c0','#d0e0f8',
  '#f0c8c8','#c8d0e8','#e0f0d0','#d8e8f8','#f8f0c0'
];

// ── API helpers ───────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  return res.json();
}

// ── Auth ──────────────────────────────────────────────────────────────────────
let authMode = 'login';

function setAuthMode(mode) {
  authMode = mode;
  document.querySelectorAll('.auth-tab').forEach(t => t.classList.toggle('active', t.dataset.mode === mode));
  document.getElementById('auth-error').textContent = '';
}

async function submitAuth() {
  const username = document.getElementById('auth-username').value.trim();
  const password = document.getElementById('auth-password').value;
  const errEl = document.getElementById('auth-error');
  errEl.textContent = '';
  if (!username || !password) { errEl.textContent = 'Please fill in all fields.'; return; }
  const res = await api('POST', `/auth/${authMode}`, { username, password });
  if (!res.ok) { errEl.textContent = res.error; return; }
  state.username = res.username;
  state.userId = res.user_id;
  state.loggedIn = true;
  showApp();
}

async function logout() {
  await api('POST', '/auth/logout');
  state = { ...state, loggedIn: false, username: '', userId: null,
    running: false, sessionId: null, sLeft: 0, totalS: 0,
    sessions: 0, totalMins: 0, streak: 0, tiles: 0,
    unlockedTiles: [], highlight: -1 };
  clearInterval(state.interval);
  clearInterval(state.squadPoll);
  document.getElementById('app-screen').style.display = 'none';
  document.getElementById('auth-screen').style.display = 'flex';
  document.getElementById('auth-username').value = '';
  document.getElementById('auth-password').value = '';
}

// ── App init ──────────────────────────────────────────────────────────────────
async function showApp() {
  document.getElementById('auth-screen').style.display = 'none';
  document.getElementById('app-screen').style.display = 'block';
  document.getElementById('app-username').textContent = state.username;
  await refreshProfile();
  await refreshFarm();
  showTab('farm', document.querySelector('.nb'));
}

async function refreshProfile() {
  const d = await api('GET', '/api/profile');
  if (!d.ok) return;
  state.sessions = d.total_sessions;
  state.totalMins = d.total_minutes;
  state.streak = d.streak;
  state.tiles = d.tiles;
  updateHeaderStats();
  updateStatsGrid();
}

function updateHeaderStats() {
  const h = Math.floor(state.totalMins / 60), m = state.totalMins % 60;
  document.getElementById('hdr-ops').textContent = state.sessions;
  document.getElementById('hdr-time').textContent = h > 0 ? h + 'h ' + m + 'm' : m + 'm';
}

function updateStatsGrid() {
  document.getElementById('s-s').textContent = state.sessions;
  document.getElementById('s-m').textContent = state.totalMins;
  document.getElementById('s-k').textContent = state.streak;
  document.getElementById('s-t').textContent = state.tiles;
}

// ── Farm canvas ───────────────────────────────────────────────────────────────
async function refreshFarm() {
  const d = await api('GET', '/api/farm');
  if (!d.ok) return;
  state.unlockedTiles = d.tiles;
  drawFarm();
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function drawFarm() {
  const cv = document.getElementById('farm-canvas');
  if (!cv) return;
  const W = cv.offsetWidth || 488;
  cv.width = W; cv.height = 270;
  const ctx = cv.getContext('2d');
  const cols = 5, rows = 4;
  const pad = 6;
  const tw = Math.floor((W - pad * (cols + 1)) / cols);
  const th = Math.floor((270 - pad * (rows + 1)) / rows);
  const r = 10;

  const grassGrad = ctx.createLinearGradient(0, 0, 0, 270);
  grassGrad.addColorStop(0,   '#c8e6a0');
  grassGrad.addColorStop(0.5, '#b8d890');
  grassGrad.addColorStop(1,   '#a8c878');
  ctx.fillStyle = grassGrad;
  ctx.fillRect(0, 0, W, 270);

  ctx.fillStyle = 'rgba(60,120,30,0.07)';
  for (let gx = 4; gx < W; gx += 12) {
    for (let gy = 4; gy < 270; gy += 12) {
      ctx.beginPath();
      ctx.arc(gx + (Math.sin(gx * gy) * 3), gy + (Math.cos(gx + gy) * 2), 1.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  for (let i = 0; i < 20; i++) {
    const c = i % cols, row = Math.floor(i / cols);
    const x = pad + c * (tw + pad);
    const y = pad + row * (th + pad);
    const on = i < (state.unlockedTiles || []).length;

    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.18)';
    ctx.shadowBlur  = 6;
    ctx.shadowOffsetX = 0;
    ctx.shadowOffsetY = 3;

    if (on) {
      const bg = TILE_BG[Math.min(state.unlockedTiles[i], TILE_BG.length - 1)];
      const tileGrad = ctx.createLinearGradient(x, y, x, y + th);
      tileGrad.addColorStop(0, lighten(bg, 18));
      tileGrad.addColorStop(1, bg);
      ctx.fillStyle = tileGrad;
      roundRect(ctx, x, y, tw, th, r);
      ctx.fill();
    } else {
      roundRect(ctx, x, y, tw, th, r);
      ctx.fillStyle = 'rgba(210,205,195,0.85)';
      ctx.fill();
    }
    ctx.restore();

    if (on) {
      ctx.save();
      roundRect(ctx, x, y, tw, 4, r);
      ctx.fillStyle = 'rgba(255,255,255,0.35)';
      ctx.fill();
      ctx.restore();
    }

    ctx.save();
    roundRect(ctx, x, y, tw, th, r);
    ctx.clip();

    if (on) {
      drawDetail(ctx,
        TILE_TYPES[Math.min(state.unlockedTiles[i], TILE_TYPES.length - 1)],
        x, y, tw, th);
    } else {
      ctx.fillStyle = 'rgba(160,150,135,0.7)';
      ctx.font = `bold ${Math.floor(th * 0.38)}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('?', x + tw / 2, y + th / 2);
    }
    ctx.restore();

    if (i === state.highlight) {
      ctx.save();
      ctx.shadowColor = '#3db87a';
      ctx.shadowBlur  = 16;
      roundRect(ctx, x - 1, y - 1, tw + 2, th + 2, r + 1);
      ctx.strokeStyle = '#3db87a';
      ctx.lineWidth   = 2.5;
      ctx.stroke();
      ctx.fillStyle = 'rgba(61,184,122,0.10)';
      ctx.fill();
      ctx.restore();
    }
  }

  // 成员3修改：农场描述文字
  const FARM_STORIES = [
    "An empty field waits for its first farmer.",
    "The land stirs. Something is beginning to grow.",
    "A humble farm takes shape. Hard work pays off.",
    "Crops fill the fields. The farm is alive.",
    "Neighbours gather. A small community flourishes.",
    "A thriving estate - the manor stands complete. 🏰",
  ];
  const tileCount = (state.unlockedTiles || []).length;
  const story = FARM_STORIES[Math.min(tileCount, FARM_STORIES.length - 1)];
  document.getElementById('farm-cap').textContent = story;
  document.getElementById('farm-tile-count').textContent =
    tileCount + ' / 20 tiles cultivated';
}

function lighten(hex, amount) {
  const n = parseInt(hex.replace('#',''), 16);
  const r = Math.min(255, (n >> 16) + amount);
  const g = Math.min(255, ((n >> 8) & 0xff) + amount);
  const b = Math.min(255, (n & 0xff) + amount);
  return '#' + [r,g,b].map(v => v.toString(16).padStart(2,'0')).join('');
}

function drawDetail(ctx, type, x, y, tw, th) {
  const cx = x + tw / 2, cy = y + th / 2;
  ctx.save();
  if (type === 'soil') {
    for (let i = 0; i < 3; i++) { ctx.fillStyle = 'rgba(0,0,0,0.07)'; ctx.fillRect(x + 8, y + 18 + i * 10, tw - 16, 4); }
  } else if (type === 'sprout') {
    ctx.fillStyle = '#5aaa40'; ctx.fillRect(cx - 1, cy - 4, 2, 12);
    ctx.fillRect(cx - 6, cy - 2, 7, 2); ctx.fillRect(cx, cy - 6, 7, 2);
  } else if (type === 'crop') {
    for (let i = 0; i < 4; i++) {
      const sx = x + 10 + i * (tw - 20) / 3;
      ctx.fillStyle = '#60b040'; ctx.fillRect(sx - 1, cy, 2, th / 2 - 6);
      ctx.fillStyle = '#80c060'; ctx.fillRect(sx - 4, cy - 6, 8, 8);
    }
  } else if (type === 'wheat') {
    for (let i = 0; i < 5; i++) {
      const sx = x + 8 + i * (tw - 16) / 4;
      ctx.fillStyle = '#a08830'; ctx.fillRect(sx - 1, cy + 2, 2, th / 2 - 8);
      ctx.fillStyle = '#d4b040';
      for (let j = 0; j < 4; j++) ctx.fillRect(sx - 3 + j, cy - 8 + j * 4, 3, 4);
    }
  } else if (type === 'fence') {
    ctx.strokeStyle = '#a07840'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(x + 4, cy); ctx.lineTo(x + tw - 4, cy); ctx.stroke();
    for (let i = 0; i < 4; i++) { const fx = x + 8 + i * (tw - 16) / 3; ctx.beginPath(); ctx.moveTo(fx, cy - 8); ctx.lineTo(fx, cy + 8); ctx.stroke(); }
  } else if (type === 'barn') {
    ctx.fillStyle = '#c04030'; ctx.fillRect(cx - 12, cy - 2, 24, 14);
    ctx.fillStyle = '#8b2a20'; ctx.beginPath(); ctx.moveTo(cx - 14, cy - 2); ctx.lineTo(cx, cy - 16); ctx.lineTo(cx + 14, cy - 2); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#2d1000'; ctx.fillRect(cx - 4, cy + 4, 8, 10);
  } else if (type === 'well') {
    ctx.fillStyle = '#aaa'; ctx.beginPath(); ctx.arc(cx, cy + 4, 10, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#5aaad0'; ctx.beginPath(); ctx.arc(cx, cy + 4, 7, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#777'; ctx.fillRect(cx - 10, cy - 6, 2, 10); ctx.fillRect(cx + 8, cy - 6, 2, 10); ctx.fillRect(cx - 10, cy - 6, 20, 2);
  } else if (type === 'pond') {
    ctx.fillStyle = '#5aaad0'; ctx.beginPath(); ctx.ellipse(cx, cy + 2, 14, 8, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.35)'; ctx.beginPath(); ctx.ellipse(cx - 2, cy, 8, 4, 0, Math.PI * 2); ctx.fill();
  } else if (type === 'silo') {
    ctx.fillStyle = '#a0a0a0'; ctx.fillRect(cx - 6, cy - 10, 12, 20);
    ctx.fillStyle = '#b8b8b8'; ctx.beginPath(); ctx.ellipse(cx, cy - 10, 6, 3, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#555'; ctx.fillRect(cx - 2, cy + 4, 4, 6);
  } else if (type === 'greenhouse') {
    ctx.fillStyle = 'rgba(61,184,122,0.2)'; ctx.strokeStyle = '#3db87a'; ctx.lineWidth = 1.5;
    ctx.strokeRect(cx - 11, cy - 8, 22, 16); ctx.fillRect(cx - 11, cy - 8, 22, 16);
    ctx.beginPath(); ctx.moveTo(cx - 11, cy - 8); ctx.lineTo(cx, cy - 18); ctx.lineTo(cx + 11, cy - 8); ctx.stroke();
    ctx.fillStyle = 'rgba(61,184,122,0.15)'; ctx.beginPath(); ctx.moveTo(cx - 11, cy - 8); ctx.lineTo(cx, cy - 18); ctx.lineTo(cx + 11, cy - 8); ctx.closePath(); ctx.fill();
  } else if (type === 'mill') {
    ctx.fillStyle = '#e0c080'; ctx.fillRect(cx - 5, cy - 4, 10, 14);
    ctx.strokeStyle = '#c0a040'; ctx.lineWidth = 1.5;
    for (let a = 0; a < 4; a++) { ctx.save(); ctx.translate(cx, cy - 6); ctx.rotate(a * Math.PI / 2); ctx.fillStyle = '#d4b040'; ctx.fillRect(-1.5, -14, 3, 12); ctx.restore(); }
  } else if (type === 'orchard') {
    [[cx - 10, cy], [cx + 10, cy], [cx, cy - 8]].forEach(([tx, ty]) => {
      ctx.fillStyle = '#3a8830'; ctx.beginPath(); ctx.arc(tx, ty, 7, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#e04040'; ctx.beginPath(); ctx.arc(tx + 3, ty - 2, 2.5, 0, Math.PI * 2); ctx.fill();
    });
  } else if (type === 'stable') {
    ctx.fillStyle = '#a07840'; ctx.fillRect(cx - 13, cy - 4, 26, 14);
    ctx.fillStyle = '#805830'; ctx.beginPath(); ctx.moveTo(cx - 15, cy - 4); ctx.lineTo(cx, cy - 14); ctx.lineTo(cx + 15, cy - 4); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#604020'; ctx.fillRect(cx - 5, cy + 2, 4, 8); ctx.fillRect(cx + 1, cy + 2, 4, 8);
  } else if (type === 'beehive') {
    ctx.fillStyle = '#d4a020'; ctx.beginPath(); ctx.ellipse(cx, cy, 9, 11, 0, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = '#a07010'; ctx.lineWidth = 1;
    for (let i = 0; i < 4; i++) { ctx.beginPath(); ctx.moveTo(cx - 9, cy - 8 + i * 5); ctx.lineTo(cx + 9, cy - 8 + i * 5); ctx.stroke(); }
  } else {
    ctx.fillStyle = 'rgba(0,0,0,0.07)'; ctx.beginPath(); ctx.arc(cx, cy, 10, 0, Math.PI * 2); ctx.fill();
  }
  ctx.restore();
}

// ── Timer ─────────────────────────────────────────────────────────────────────
function fmt(s) { return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0'); }

function setRing(pct) {
  const el = document.getElementById('ring');
  if (!el) return;
  el.style.strokeDashoffset = CIRC * (1 - pct);
  el.style.stroke = pct > 0.4 ? '#3db87a' : pct > 0.15 ? '#e0a030' : '#e05050';
}

function onDur(v) {
  state.dur = parseInt(v);
  document.getElementById('dur-lbl').textContent = state.dur + ' min';
  if (!state.running) {
    state.sLeft = state.dur * 60;
    document.getElementById('timer-disp').textContent = fmt(state.sLeft);
    setRing(1);
  }
}

async function startOp() {
  if (state.running) return;
  const res = await api('POST', '/api/sessions/start', { duration_mins: state.dur });
  if (!res.ok) { alert(res.error); return; }
  state.running = true;
  state.sessionId = res.session_id;
  state.totalS = state.dur * 60;
  state.sLeft = state.totalS;
  document.getElementById('start-btn').disabled = true;
  document.getElementById('abort-btn').disabled = false;
  document.getElementById('dur-sl').disabled = true;
  document.getElementById('timer-st').textContent = 'active';
  document.getElementById('op-hint').textContent = 'Stay focused — your farm is waiting...';
  state.interval = setInterval(tick, 1000);
}

function tick() {
  state.sLeft--;
  document.getElementById('timer-disp').textContent = fmt(state.sLeft);
  setRing(state.sLeft / state.totalS);
  if (state.sLeft <= 0) completeOp();
}

async function completeOp() {
  clearInterval(state.interval);
  state.running = false;
  const res = await api('POST', '/api/sessions/complete', { session_id: state.sessionId });
  if (!res.ok) { resetTimer(); return; }

  if (res.tile_index !== null && res.tile_index !== undefined) {
    state.unlockedTiles.push(res.tile_index);
    state.highlight = state.unlockedTiles.length - 1;
    drawFarm();
    setTimeout(() => { state.highlight = -1; drawFarm(); }, 2500);
    showUnlockBanner(res.tile_index, res.tile_name);
  }
  await refreshProfile();
  resetTimer();
  document.getElementById('op-hint').textContent = 'Complete a session to unlock a farm tile';
  if (res.new_achievements && res.new_achievements.length) {
    setTimeout(() => showAchievementToasts(res.new_achievements), 800);
  }
}

async function abortOp() {
  clearInterval(state.interval);
  state.running = false;
  if (state.sessionId) await api('POST', '/api/sessions/abort', { session_id: state.sessionId });
  state.sessionId = null;
  resetTimer();
  await refreshProfile();
  document.getElementById('op-hint').textContent = 'Session abandoned. Try again when ready!';
}

function resetTimer() {
  state.sLeft = state.dur * 60;
  document.getElementById('timer-disp').textContent = fmt(state.sLeft);
  document.getElementById('timer-st').textContent = 'ready';
  document.getElementById('start-btn').disabled = false;
  document.getElementById('abort-btn').disabled = true;
  document.getElementById('dur-sl').disabled = false;
  setRing(1);
}

function showUnlockBanner(idx, name) {
  const icons = ['🌍','🌱','🌿','🌾','🪵','🏚','💧','🫧','🏛','🌿','⚙️','🍎','🐴','🍯','💧','🏪','🏡','🌲','⛲','🏰'];
  document.getElementById('upop-icon').textContent = icons[idx] || '🌿';
  document.getElementById('upop-title').textContent = name || 'New tile unlocked!';
  document.getElementById('upop-sub').textContent = `Tile ${idx + 1} of 20 cultivated`;
  const pop = document.getElementById('unlock-pop');
  pop.classList.add('show');
  setTimeout(() => pop.classList.remove('show'), 3500);
}

// ── Squad ─────────────────────────────────────────────────────────────────────
const AVATAR_COLORS = [
  ['#edf9f3','#2a9460'],['#edf0ff','#3a6acc'],['#fff8ed','#c07820'],
  ['#fdedf5','#b0408a'],['#edf5ff','#2060c0'],['#f5eeff','#7040c0']
];

async function refreshSquad() {
  const d = await api('GET', '/api/squads/status');
  const el = document.getElementById('squad-content');
  if (!d.ok || !d.in_squad) {
    el.innerHTML = `
      <div class="no-squad">You are not in a squad yet.</div>
      <div style="margin-top:12px">
        <div class="slabel">Create a squad</div>
        <input type="text" id="squad-name-input" placeholder="Squad name (optional)">
        <button class="primary" style="width:100%;margin-bottom:12px" onclick="createSquad()">Create squad</button>
        <div class="slabel">Join a squad</div>
        <input type="text" id="join-input" placeholder="Enter code (e.g. FARM-XK7Q)">
        <button class="primary" style="width:100%" onclick="joinSquad()">Join squad</button>
      </div>`;
    document.getElementById('squad-stats').innerHTML = '';
    return;
  }

  const members = d.members.map((m, i) => {
    const [bg, fg] = AVATAR_COLORS[i % AVATAR_COLORS.length];
    const initials = m.username.slice(0, 2).toUpperCase();
    const statusColor = m.status !== 'Idle' ? 'color:#3db87a' : '';
    const youBadge = m.is_you ? ' <span style="font-size:10px;color:#aaa">(you)</span>' : '';
    return `<div class="member-row">
      <div class="avatar" style="background:${bg};color:${fg}">${initials}</div>
      <div style="flex:1">
        <div class="mname">${m.username}${youBadge}</div>
        <div class="mstatus" style="${statusColor}">${m.status}</div>
      </div>
      <div class="mbar-wrap"><div class="mbar" style="width:${m.progress_pct}%;background:${fg}"></div></div>
      <div class="mtime">${m.elapsed_mins > 0 ? m.elapsed_mins + 'm' : '—'}</div>
    </div>`;
  }).join('');

  el.innerHTML = `
    <div class="squad-header">
      <div>
        <div class="squad-title">${d.squad_name}</div>
        <div class="squad-code-line">Code: <span>${d.squad_code}</span></div>
      </div>
    </div>
    ${members}
    <div style="margin-top:14px;padding-top:14px;border-top:1px solid #f0f0f0">
      <div class="slabel">Invite someone</div>
      <div style="font-size:12px;color:#aaa">Share your code: <strong style="color:#3db87a;letter-spacing:1px">${d.squad_code}</strong></div>
    </div>`;

  const rank = d.team_ops < 10 ? 'Lv 1' : d.team_ops < 30 ? 'Lv 2' : d.team_ops < 60 ? 'Lv 3' : 'Lv 4';
  document.getElementById('squad-stats').innerHTML = `
    <div class="stats-grid" style="margin:12px 0 0">
      <div class="sc"><div class="sv">${d.member_count}</div><div class="sl">Members</div></div>
      <div class="sc"><div class="sv">${d.team_ops}</div><div class="sl">Team ops</div></div>
      <div class="sc"><div class="sv">${d.team_mins}</div><div class="sl">Team min</div></div>
      <div class="sc"><div class="sv" style="color:#d4a040">${rank}</div><div class="sl">Rank</div></div>
    </div>`;
}

async function createSquad() {
  const name = (document.getElementById('squad-name-input')?.value || '').trim();
  const res = await api('POST', '/api/squads/create', { name });
  if (!res.ok) { alert(res.error); return; }
  await refreshSquad();
}

async function joinSquad() {
  const code = (document.getElementById('join-input')?.value || '').trim();
  if (!code) return;
  const res = await api('POST', '/api/squads/join', { code });
  if (!res.ok) { alert(res.error); return; }
  await refreshSquad();
}

// ── Log ───────────────────────────────────────────────────────────────────────
async function refreshLog() {
  const d = await api('GET', '/api/sessions/history');
  const el = document.getElementById('log-list');
  if (!d.ok || !d.sessions.length) {
    el.innerHTML = '<div style="font-size:12px;color:#bbb;padding:8px 0;text-align:center">No sessions yet.</div>';
    return;
  }
  el.innerHTML = d.sessions.map(s => {
    const col = s.status === 'completed' ? '#3db87a' : s.status === 'aborted' ? '#e05050' : '#ccc';
    const ts = s.completed_at || s.started_at || '';
    const timeStr = ts.length >= 16 ? ts.slice(11, 16) : '';
    const msg = s.status === 'completed'
      ? `${s.duration_mins}-min session complete${s.tile_unlocked !== null ? ' — ' + TILE_NAMES[s.tile_unlocked] : ''}`
      : s.status === 'aborted' ? `${s.duration_mins}-min session abandoned`
      : `${s.duration_mins}-min session expired`;
    return `<div class="log-row"><div class="dot" style="background:${col}"></div><span>${msg}</span><span class="log-t">${timeStr}</span></div>`;
  }).join('');
}

// ── Analysis chart ────────────────────────────────────────────────────────────
async function refreshChart() {
  const d = await api('GET', '/api/analysis');
  if (!d.ok) return;
  const labels = d.daily_minutes.map(x => x.date.slice(5));
  const data = d.daily_minutes.map(x => x.minutes);

  if (state.chart) { state.chart.destroy(); state.chart = null; }
  const ctx = document.getElementById('focus-chart')?.getContext('2d');
  if (!ctx) return;

  state.chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Focus minutes',
        data,
        backgroundColor: 'rgba(61,184,122,0.5)',
        borderColor: '#3db87a',
        borderWidth: 1.5,
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 }, color: '#aaa' } },
        y: { grid: { color: '#f0f0f0' }, ticks: { font: { size: 10 }, color: '#aaa' }, beginAtZero: true }
      }
    }
  });

  document.getElementById('streak-display').textContent =
    `Current streak: ${d.current_streak} day${d.current_streak !== 1 ? 's' : ''} · Longest: ${d.longest_streak}`;
}

// Quiet hours card
if (d.quiet_hours) {
  const card = document.getElementById('quiet-hours-card');
  const win = document.getElementById('quiet-window');
  const rec = document.getElementById('quiet-recommendation');

  if (card) card.style.display = 'block';
  if (win)
    win.textContent =
    '🕐 Best window: ' +
    d.quiet_hours.window_label;
  if (rec)
    rec.textContent =
    d.quiet_hours.recommendation;
}

// ── Navigation ────────────────────────────────────────────────────────────────
function showTab(name, btn) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.nb').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  if (btn) btn.classList.add('active');

  clearInterval(state.squadPoll);

  if (name === 'farm') { setTimeout(drawFarm, 50); }
  else if (name === 'ops') { setRing(state.running ? state.sLeft / state.totalS : 1); refreshChart(); }
  else if (name === 'squad') {
    refreshSquad();
    state.squadPoll = setInterval(refreshSquad, 10000);
  }
  else if (name === 'achievements') { refreshAchievements(); }
  else if (name === 'log') { refreshLog(); }
}

// ── Boot ──────────────────────────────────────────────────────────────────────
window.addEventListener('load', async () => {
  const me = await api('GET', '/auth/me');
  if (me.logged_in) {
    state.username = me.username;
    state.userId = me.user_id;
    state.loggedIn = true;
    showApp();
  }
  document.getElementById('auth-password').addEventListener('keydown', e => {
    if (e.key === 'Enter') submitAuth();
  });
});

window.addEventListener('resize', () => {
  if (document.getElementById('tab-farm')?.classList.contains('active')) drawFarm();
});

// ── Achievements ──────────────────────────────────────────────────────────────
const ACH_CAT_COLORS = {
  milestone: '#3db87a',
  streak:    '#e0a030',
  habit:     '#4a9eff',
  special:   '#c060c0',
  time:      '#e05050',
  squad:     '#3a6acc',
};

async function refreshAchievements() {
  const d = await api('GET', '/api/achievements');
  if (!d.ok) return;

  document.getElementById('ach-progress').textContent =
    `${d.unlocked} / ${d.total} unlocked (${d.completion}%)`;

  const list = document.getElementById('ach-list');
  if (!list) return;

  const categories = {};
  d.achievements.forEach(a => {
    if (!categories[a.category]) categories[a.category] = [];
    categories[a.category].push(a);
  });

  const catLabels = {
    milestone: '🏅 Milestones',
    streak:    '🔥 Streaks',
    habit:     '📆 Habits',
    special:   '✨ Special',
    time:      '⏱️ Time',
    squad:     '👥 Squad',
  };

  let html = '';
  for (const [cat, items] of Object.entries(categories)) {
    html += `<div style="margin-bottom:14px">
      <div style="font-size:10px;font-weight:600;color:${ACH_CAT_COLORS[cat]||'#aaa'};
        text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">
        ${catLabels[cat] || cat}
      </div>
      <div class="ach-grid">`;
    items.forEach(a => {
      const cls = a.unlocked ? 'unlocked' : 'locked';
      html += `<div class="ach-item ${cls}">
        <div class="ach-icon">${a.icon}</div>
        <div>
          <div class="ach-title">${a.title}</div>
          <div class="ach-desc">${a.description}</div>
          ${a.unlocked ? '<div class="ach-cat" style="color:#3db87a">✓ Unlocked</div>' : ''}
        </div>
      </div>`;
    });
    html += `</div></div>`;
  }
  list.innerHTML = html;
}

function showAchievementToast(achievement) {
  let pop = document.getElementById('ach-toast');
  if (!pop) {
    pop = document.createElement('div');
    pop.id = 'ach-toast';
    pop.className = 'ach-new-pop';
    document.body.appendChild(pop);
  }
  pop.innerHTML = `<span style="font-size:20px">${achievement.icon}</span>
    <div><div style="font-size:11px;opacity:0.8;margin-bottom:1px">Achievement unlocked!</div>
    <div>${achievement.title}</div></div>`;
  pop.classList.add('show');
  setTimeout(() => pop.classList.remove('show'), 4000);
}

function showAchievementToasts(newAchievements) {
  if (!newAchievements || !newAchievements.length) return;
  newAchievements.forEach((a, i) => {
    setTimeout(() => showAchievementToast(a), i * 4200);
  });
}
