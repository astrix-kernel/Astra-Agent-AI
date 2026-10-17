/* Astrix Settings v3 — AUTO-SAVE (no manual save needed) */
(function() {
  'use strict';
  
  const KEY = 'astrix_settings';
  
  const MODES = [
    { id: 'coding', icon: '👨‍💻', label_en: 'Coding Mode', label_id: 'Mode Coding',
      desc_en: 'Focus on clean code, low temp', desc_id: 'Fokus kode bersih, temp rendah',
      prompt_en: 'You are a Senior Software Engineer. Focus on clean, efficient code with inline comments. Explain briefly.',
      prompt_id: 'Kamu adalah Senior Software Engineer. Fokus pada kode bersih, efisien, dengan komentar inline. Jelaskan singkat.',
      temp: 0.3, maxTokens: 8192, compressHistory: false },
    { id: 'chat', icon: '💬', label_en: 'Chat Mode', label_id: 'Mode Chat',
      desc_en: 'Casual, creative, friendly', desc_id: 'Santai, kreatif, ramah',
      prompt_en: 'You are a friendly casual AI companion. Keep answers short, fun, and engaging. Match the user\'s tone.',
      prompt_id: 'Kamu adalah AI companion yang santai dan ramah. Jawab singkat, asyik, dan engaging. Ikutin tone user.',
      temp: 1.2, maxTokens: 4096, compressHistory: false },
    { id: 'saving', icon: '💰', label_en: 'Token Saving', label_id: 'Hemat Token',
      desc_en: 'Short answers, save tokens', desc_id: 'Jawab pendek, hemat token',
      prompt_en: 'You are a concise assistant. Keep answers brief, no fluff, no repetition. Max 80 words per reply unless explicitly asked for detail.',
      prompt_id: 'Kamu adalah asisten ringkas. Jawab pendek, tanpa basa-basi, tanpa pengulangan. Maks 80 kata per balasan kecuali diminta detail.',
      temp: 0.5, maxTokens: 1024, compressHistory: true },
    { id: 'medium', icon: '⚖️', label_en: 'Medium', label_id: 'Sedang',
      desc_en: 'Balanced detail & brevity', desc_id: 'Seimbang detail & ringkas',
      prompt_en: 'You are a helpful AI assistant. Balance detail and brevity. Answer clearly.',
      prompt_id: 'Kamu adalah asisten AI yang membantu. Seimbangkan detail dan ringkas. Jawab jelas.',
      temp: 0.7, maxTokens: 4096, compressHistory: false },
    { id: 'max', icon: '🔥', label_en: 'Maximum', label_id: 'Maksimal',
      desc_en: 'MAX temperature & tokens — full power', desc_id: 'Temperature & token MAKSIMAL — full power',
      prompt_en: 'You are an expert AI. Provide MAXIMUM detail, deep analysis, examples, edge cases, and code. Do not hold back. Be as thorough as possible.',
      prompt_id: 'Kamu adalah AI expert. Berikan detail MAKSIMAL, analisis mendalam, contoh, edge case, dan kode. Jangan ditahan. Se-tuntas mungkin.',
      temp: 2.0, maxTokens: 32768, compressHistory: false },
  ];
  const TAB_DEFS = [
    { id: 'general', icon: 'ph-globe', label: 'General & UI', label_id: 'Umum & UI' },
    { id: 'workspace', icon: 'ph-folder-open', label: 'Workspace', label_id: 'Workspace' },
    { id: 'provider', icon: 'ph-plugs-connected', label: 'LLM Provider', label_id: 'LLM Provider' },
    { id: 'model', icon: 'ph-sliders-horizontal', label: 'Model Params', label_id: 'Parameter Model' },
    { id: 'persona', icon: 'ph-user-circle', label: 'Persona & Prompt', label_id: 'Persona & Prompt' },
    { id: 'profiles', icon: 'ph-floppy-disk', label: 'Profiles', label_id: 'Profil' },
    { id: 'usage', icon: 'ph-chart-line', label: 'Usage Dashboard', label_id: 'Dashboard Pemakaian' },
    { id: 'memory', icon: 'ph-brain', label: 'Memory', label_id: 'Memori' },
    { id: 'history', icon: 'ph-clock-clockwise', label: 'Chat History', label_id: 'Riwayat Chat' },
    { id: 'security', icon: 'ph-shield-check', label: 'Security', label_id: 'Keamanan' },
    { id: 'notifications', icon: 'ph-bell', label: 'Notifications', label_id: 'Notifikasi' },
    { id: 'voice', icon: 'ph-speaker-high', label: 'Voice & TTS', label_id: 'Suara & TTS' },
    { id: 'developer', icon: 'ph-terminal-window', label: 'Developer', label_id: 'Developer' },
  ];
  
  let currentTab = 'general';
  let allSettings = {};
  
  function getLang() { return allSettings.language || 'id'; }
  function L(en, id) { return getLang() === 'en' ? en : id; }
  
  function loadSettings() {
    try { allSettings = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e) { allSettings = {}; }
    return allSettings;
  }
  
  function saveSettings(s) {
    allSettings = s;
    localStorage.setItem(KEY, JSON.stringify(s));
  }
  
  // === AUTO-SAVE: setiap field berubah, langsung save ===
  function autoSave(field, value) {
    const s = loadSettings();
    s[field] = value;
    saveSettings(s);
    // Flash indicator
    const indicator = document.getElementById('autosaveIndicator');
    if (indicator) {
      indicator.textContent = '✅ Tersimpan';
      indicator.style.opacity = '1';
      setTimeout(() => { indicator.style.opacity = '0'; }, 800);
    }
  }
  
  function renderNav() {
    const nav = document.getElementById('settingsNav');
    if (!nav) return;
    const lang = getLang();
    nav.innerHTML = TAB_DEFS.map(t => `
      <button class="settings-tab w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition mb-1 ${t.id === currentTab ? 'bg-blue-600/20 text-blue-400' : 'text-gray-400 hover:bg-white/5 hover:text-white'}" data-tab="${t.id}">
        <i class="ph ${t.icon} text-lg"></i><span>${lang === 'en' ? t.label : t.label_id}</span>
      </button>
    `).join('');
    nav.querySelectorAll('.settings-tab').forEach(b => {
      b.onclick = () => { currentTab = b.dataset.tab; renderNav(); renderContent(); };
    });
  }
  
  async function renderContent() {
    const el = document.getElementById('settingsContent');
    if (!el) return;
    const fn = renderers[currentTab];
    el.innerHTML = await (fn ? fn() : '<p class="text-gray-500">Tab belum tersedia</p>');
    bindEvents[currentTab]?.();
  }
  
  const renderers = {
    async general() {
      const s = loadSettings();
      return `
        <div class="space-y-6">
          <h2 class="text-2xl font-bold text-white">${L('General & UI', 'Umum & UI')}</h2>
          <div class="glass-card p-6 rounded-2xl space-y-6">
            <div>
              <label class="text-sm font-bold text-white mb-3 block">${L('Language', 'Bahasa')}</label>
              <div class="grid grid-cols-2 gap-3">
                <button class="lang-btn p-4 rounded-xl border-2 ${(s.language||'id')==='id'?'border-blue-500 bg-blue-600/10':'border-white/10'} text-left" data-lang="id"><div class="text-white font-bold">🇮🇩 Indonesia</div></button>
                <button class="lang-btn p-4 rounded-xl border-2 ${s.language==='en'?'border-blue-500 bg-blue-600/10':'border-white/10'} text-left" data-lang="en"><div class="text-white font-bold">🇬🇧 English</div></button>
              </div>
            </div>
            <div>
              <label class="text-sm font-bold text-white mb-3 block">${L('Accent Color', 'Warna Aksen')}</label>
              <div class="flex gap-3 flex-wrap">
                ${['#3b82f6','#a855f7','#22c55e','#f97316','#ef4444','#06b6d4','#eab308','#ec4899'].map(c => 
                  `<button class="accent-btn w-10 h-10 rounded-full border-2 ${(s.accentColor||'#3b82f6')===c?'border-white':'border-white/30'}" data-color="${c}" style="background:${c}"></button>`
                ).join('')}
              </div>
            </div>
            <div>
              <label class="text-sm font-bold text-white mb-3 block">${L('Font Size', 'Ukuran Font')}: <span id="fontSizeVal">${s.fontSize||14}px</span></label>
              <input type="range" id="autoFontSize" min="12" max="20" step="1" value="${s.fontSize||14}" class="w-full">
            </div>
          </div>
        </div>
      `;
    },
    
    async workspace() {
      const s = loadSettings();
      const currentWs = s.workspace || '';
      
      return `
        <div class="space-y-6">
          <h2 class="text-2xl font-bold text-white flex items-center gap-3">
            <i class="ph-fill ph-folder-open text-orange-400"></i> ${L('Workspace','Workspace')}
          </h2>
          <p class="text-gray-400 text-sm">${L('Select project folder that AI agent will work in','Pilih folder project yang bakal dikerjain AI agent')}</p>
          
          <!-- CURRENT WORKSPACE -->
          <div id="wsCurrentCard" class="glass-card p-6 rounded-2xl ${currentWs ? 'border-2 border-green-500/30' : 'border-2 border-yellow-500/30'}">
            <div class="flex items-center justify-between mb-3">
              <label class="text-sm font-bold text-white">${L('Current Workspace','Workspace Aktif')}</label>
              ${currentWs ? '<span class="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded-full">✅ ' + L('Active','Aktif') + '</span>' : '<span class="text-xs bg-yellow-500/20 text-yellow-400 px-2 py-1 rounded-full">⚠️ ' + L('Not Set','Belum Diatur') + '</span>'}
            </div>
            <div id="wsCurrentInfo" class="space-y-2">
              ${currentWs ? '<div class="font-mono text-sm text-blue-300 bg-[#050608] p-3 rounded-lg break-all">' + currentWs + '</div><div id="wsStats" class="text-xs text-gray-400">Loading stats...</div>' : '<div class="text-sm text-gray-500 italic">' + L('No workspace selected. Click "Change Folder" below.','Belum ada workspace. Klik "Ganti Folder" di bawah.') + '</div>'}
            </div>
            <div class="flex gap-2 mt-4">
              <button id="changeWorkspaceBtn" class="flex-1 bg-orange-600 hover:bg-orange-500 text-white px-4 py-3 rounded-xl text-sm font-bold flex items-center justify-center gap-2">
                <i class="ph ph-folder-open"></i> ${L('Change Folder','Ganti Folder')}
              </button>
              ${currentWs ? '<button id="clearWorkspaceBtn" class="bg-red-500/20 hover:bg-red-500/30 text-red-400 px-4 py-3 rounded-xl text-sm font-bold border border-red-500/30"><i class="ph ph-x"></i></button>' : ''}
            </div>
          </div>
          
          <!-- HOW IT WORKS -->
          <div class="glass-card p-4 rounded-xl border border-blue-500/20 bg-blue-500/5">
            <div class="flex gap-3">
              <i class="ph-fill ph-info text-blue-400 text-xl"></i>
              <div class="text-xs text-gray-300 space-y-1">
                <div class="font-bold text-white">${L('How It Works','Cara Kerja')}</div>
                <div>${L('AI agent will read/write only inside this folder','AI agent bakal baca/tulis cuma di dalam folder ini')}</div>
                <div>${L('Workspace info is injected into every chat','Info workspace otomatis masuk ke setiap chat')}</div>
                <div>${L('Safe mode: paths outside workspace blocked','Safe mode: path di luar workspace diblokir')}</div>
              </div>
            </div>
          </div>
          
          <!-- WORKSPACE STATS -->
          ${currentWs ? '<div id="wsStatsDetail" class="glass-card p-4 rounded-xl"></div>' : ''}
        </div>
      `;
    },
    
    async provider() {
      const s = loadSettings();
      const providers = { omniroute:'OmniRoute (Default)', openai:'OpenAI', openrouter:'OpenRouter', groq:'Groq', deepseek:'DeepSeek', ollama:'Ollama', custom:'Custom' };
      return `
        <div class="space-y-6">
          <h2 class="text-2xl font-bold text-white">LLM Provider</h2>
          <div class="glass-card p-6 rounded-2xl space-y-4">
            <div>
              <label class="text-sm font-bold text-white mb-2 block">Provider</label>
              <select id="autoProvider" class="w-full bg-[#050608] border border-white/10 text-gray-200 rounded-xl p-3 text-sm">
                ${Object.entries(providers).map(([k,v]) => `<option value="${k}" ${(s.provider||'omniroute')===k?'selected':''}>${v}</option>`).join('')}
              </select>
            </div>
            <div><label class="text-sm font-bold text-white mb-2 block">Base URL</label><input id="autoBaseUrl" value="${s.baseUrl||''}" class="w-full bg-[#050608] border border-white/10 text-gray-200 rounded-xl p-3 text-sm font-mono" placeholder="https://api.openai.com/v1"></div>
            <div><label class="text-sm font-bold text-white mb-2 block">API Key</label><div class="relative">
                <input type="password" id="autoApiKey" value="${s.apiKey||''}" class="w-full bg-[#050608] border border-white/10 text-gray-200 rounded-xl p-3 text-sm font-mono pr-12">
                <button type="button" id="toggleApiKeyBtn" class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition">
                  <i class="ph ph-eye text-lg"></i>
                </button>
              </div></div>
            <div>
              <label class="text-sm font-bold text-white mb-2 block">Model</label>
              <div class="flex gap-2">
                <select id="autoModel" class="flex-1 bg-[#050608] border border-white/10 text-gray-200 rounded-xl p-3 text-sm font-mono">
                  ${s.modelOverride ? `<option value="${s.modelOverride}" selected>${s.modelOverride}</option>` : '<option value="">-- Klik Deteksi --</option>'}
                </select>
                <button id="detectModelsBtn" class="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded-xl text-sm font-bold whitespace-nowrap flex items-center gap-2">
                  <i class="ph ph-magnifying-glass"></i> ${L('Detect','Deteksi')}
                </button>
              </div>
              <div id="detectStatus" class="text-xs mt-1 text-gray-500"></div>
            </div>
            <div>
              <label class="text-sm font-bold text-white mb-2 block">${L('Fallback Model','Model Cadangan')}</label>
              <select id="autoFallback" class="w-full bg-[#050608] border border-white/10 text-gray-200 rounded-xl p-3 text-sm font-mono">
                <option value="">${L('-- No fallback --','-- Tanpa cadangan --')}</option>
                ${s.fallbackModel ? `<option value="${s.fallbackModel}" selected>${s.fallbackModel}</option>` : ''}
              </select>
            </div>
          </div>
        </div>
      `;
    },
    
    async model() {
      const s = loadSettings();
      const sl = (id, field, label, val, min, max, step) => `
        <div class="glass-card p-6 rounded-2xl">
          <div class="flex justify-between text-sm font-bold text-white mb-3"><span>${label}</span><span id="val_${field}" class="text-purple-400 font-mono">${val}</span></div>
          <input type="range" id="auto${field}" data-field="${field}" min="${min}" max="${max}" step="${step}" value="${val}" class="w-full accent-purple-500">
        </div>
      `;
      return `
        <div class="space-y-6">
          <h2 class="text-2xl font-bold text-white">${L('Model Params','Parameter Model')}</h2>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            ${sl('Temp','temp','Temperature', s.temp ?? 0.7, 0, 2, 0.1)}
            ${sl('TopP','topP','Top P', s.topP ?? 0.9, 0.1, 1, 0.05)}
            ${sl('TopK','topK','Top K', s.topK ?? 40, 1, 100, 1)}
            ${sl('MaxTokens','maxTokens','Max Tokens', s.maxTokens ?? 4096, 512, 32768, 512)}
            ${sl('FreqPen','freqPen','Frequency Penalty', s.freqPen ?? 0, 0, 2, 0.1)}
            ${sl('PresPen','presPen','Presence Penalty', s.presPen ?? 0, 0, 2, 0.1)}
          </div>
        </div>
      `;
    },
    
    async persona() {
      const s = loadSettings();
      const currentMode = s.activeMode || 'medium';
      const lang = getLang();
      
      return `
        <div class="space-y-6">
          <h2 class="text-2xl font-bold text-white">${L('Persona & Prompt','Persona & Prompt')}</h2>
          
          <!-- QUICK MODES -->
          <div class="glass-card p-6 rounded-2xl">
            <div class="flex items-center justify-between mb-3">
              <label class="text-sm font-bold text-white">${L('Quick Mode','Mode Cepat')}</label>
              <span class="text-[10px] text-gray-500">${L('auto-configure all params','auto-konfigurasi semua parameter')}</span>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-5 gap-2">
              ${MODES.map(m => `
                <button class="mode-btn p-3 rounded-xl border-2 ${currentMode === m.id ? 'border-blue-500 bg-blue-600/20 ring-2 ring-blue-500/30' : 'border-white/10 bg-white/5 hover:bg-white/10'} text-xs text-white text-left transition" data-mode="${m.id}">
                  <div class="text-2xl mb-1">${m.icon}</div>
                  <div class="font-bold text-[11px]">${lang === 'en' ? m.label_en : m.label_id}</div>
                  <div class="text-[9px] text-gray-400 mt-0.5">${lang === 'en' ? m.desc_en : m.desc_id}</div>
                </button>
              `).join('')}
            </div>
            ${currentMode ? `
              <div class="mt-3 p-2 bg-blue-500/10 border border-blue-500/20 rounded-lg text-xs text-blue-300 flex items-center gap-2">
                <i class="ph ph-check-circle"></i>
                ${L('Active mode:','Mode aktif:')} <strong>${(MODES.find(m=>m.id===currentMode) || {}).label_en || 'Medium'}</strong>
              </div>
            ` : ''}
          </div>
          
          <!-- System Prompt -->
          <div class="glass-card p-6 rounded-2xl space-y-4">
            <div><label class="text-sm font-bold text-white mb-2 block">System Prompt</label>
              <textarea id="autoSystemPrompt" rows="5" class="w-full bg-[#050608] border border-white/10 text-gray-200 rounded-xl p-4 text-sm">${s.systemPrompt||'You are a helpful AI assistant.'}</textarea>
            </div>
            <div>
              <label class="text-sm font-bold text-white mb-3 block">${L('Quick Presets','Preset Cepat')}</label>
              <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
                ${['👨‍💻 Senior Dev|Kamu adalah Senior Software Engineer.|You are a Senior Software Engineer.',
                   '🕶️ Hacker|Kamu adalah Hacker elit.|You are an elite Hacker.',
                   '🏗️ Arsitek|Kamu adalah Arsitek Sistem.|You are a System Architect.',
                   '🐧 Kernel|Kamu adalah Linux Kernel Expert.|You are a Linux Kernel Expert.'].map(p => {
                  const [name, id, en] = p.split('|');
                  return `<button class="preset-btn p-3 rounded-lg bg-white/5 hover:bg-white/10 text-xs text-white text-left border border-white/10" data-id="${id}" data-en="${en}"><div class="font-bold">${name}</div></button>`;
                }).join('')}
              </div>
            </div>
          </div>
        </div>
      `;
    },
    
    async profiles() {
      const res = await fetch('/api/profiles').catch(()=>null);
      const profiles = res ? await res.json() : {};
      return `
        <div class="space-y-6">
          <h2 class="text-2xl font-bold text-white">Profiles</h2>
          <div class="glass-card p-6 rounded-2xl space-y-4">
            <div class="flex gap-2">
              <input id="profileName" placeholder="${L('Profile name','Nama profil')}" class="flex-1 bg-[#050608] border border-white/10 text-gray-200 rounded-xl p-3 text-sm">
              <button id="saveProfileBtn" class="bg-yellow-600 hover:bg-yellow-500 text-white px-4 py-2 rounded-xl text-sm font-bold">💾 Save</button>
            </div>
            <div id="profileList" class="space-y-2">
              ${Object.keys(profiles).map(name => `
                <div class="flex justify-between items-center p-3 bg-white/5 rounded-lg border border-white/10">
                  <span class="text-sm text-white">${name}</span>
                  <div class="flex gap-2">
                    <button class="load-profile-btn text-xs text-blue-400" data-name="${name}">Load</button>
                    <button class="del-profile-btn text-xs text-red-400" data-name="${name}">Hapus</button>
                  </div>
                </div>
              `).join('') || '<p class="text-xs text-gray-500 italic text-center py-4">Belum ada profile</p>'}
            </div>
          </div>
        </div>
      `;
    },
    
    async usage() {
      const res = await fetch('/api/usage').catch(()=>null);
      const data = res ? await res.json() : { totals:{}, week:[], today:{} };
      const t = data.totals || {};
      const today = data.today || {};
      const week = data.week || [];
      const maxTok = Math.max(...week.map(d => (d.prompt||0)+(d.completion||0)), 1);
      return `
        <div class="space-y-6">
          <h2 class="text-2xl font-bold text-white">${L('Usage Dashboard','Dashboard Pemakaian')}</h2>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="glass-card p-4 rounded-xl"><div class="text-xs text-gray-400">Today Requests</div><div class="text-2xl font-bold text-blue-400">${today.requests||0}</div></div>
            <div class="glass-card p-4 rounded-xl"><div class="text-xs text-gray-400">Today Tokens</div><div class="text-2xl font-bold text-green-400">${((today.prompt||0)+(today.completion||0)).toLocaleString()}</div></div>
            <div class="glass-card p-4 rounded-xl"><div class="text-xs text-gray-400">Total Tokens</div><div class="text-2xl font-bold text-purple-400">${((t.prompt||0)+(t.completion||0)).toLocaleString()}</div></div>
            <div class="glass-card p-4 rounded-xl"><div class="text-xs text-gray-400">Est. Cost</div><div class="text-2xl font-bold text-yellow-400">$${(t.cost||0).toFixed(4)}</div></div>
          </div>
          <div class="glass-card p-6 rounded-2xl">
            <h3 class="text-sm font-bold text-white mb-4">Last 7 Days</h3>
            <div class="flex items-end justify-between gap-2 h-40">
              ${week.map(d => {
                const total = (d.prompt||0)+(d.completion||0);
                const pct = (total / maxTok) * 100;
                return `<div class="flex-1 flex flex-col items-center gap-1">
                  <div class="text-[10px] text-gray-400">${total>0?total:''}</div>
                  <div class="w-full bg-blue-500 rounded-t" style="height:${Math.max(pct, 2)}%"></div>
                  <div class="text-[9px] text-gray-500">${d.date.slice(5)}</div>
                </div>`;
              }).join('')}
            </div>
          </div>
          <button id="resetUsageBtn" class="bg-red-500/20 hover:bg-red-500/30 text-red-400 px-4 py-2 rounded-xl text-sm font-bold border border-red-500/30">🗑️ Reset Stats</button>
        </div>
      `;
    },
    
async memory() {
      let memories = [];
      try {
        const res = await fetch('/api/memory/list');
        const data = await res.json();
        memories = data.memories || [];
      } catch(e) { console.warn('Memory load err:', e); }
      
      const grouped = {};
      memories.forEach(m => {
        if (!grouped[m.category]) grouped[m.category] = [];
        grouped[m.category].push(m);
      });
      
      const catIcons = { identity: '👤', project: '🚀', preference: '⭐', general: '📝', test: '🧪' };
      
      return `
        <div class="space-y-6">
          <div class="flex items-center justify-between">
            <h2 class="text-2xl font-bold text-white flex items-center gap-3"><i class="ph-fill ph-brain text-purple-400"></i> ${L('Memory','Memori')}</h2>
            <button id="clearAllMemoryBtn" class="bg-red-500/20 hover:bg-red-500/30 text-red-400 px-4 py-2 rounded-lg text-xs font-bold border border-red-500/30">🗑️ ${L('Clear All','Hapus Semua')}</button>
          </div>
          
          <p class="text-gray-400 text-sm">${L('Facts the AI remembers about you and your projects','Fakta yang diingat AI tentang lu dan project lu')}</p>
          
          <!-- Add memory form -->
          <div class="glass-card p-4 rounded-xl">
            <div class="text-sm font-bold text-white mb-3">➕ ${L('Add Fact Manually','Tambah Fakta Manual')}</div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
              <select id="memCat" class="bg-[#050608] border border-white/10 text-gray-200 rounded-lg p-2 text-sm">
                <option value="identity">👤 Identity</option>
                <option value="project">🚀 Project</option>
                <option value="preference">⭐ Preference</option>
                <option value="general">📝 General</option>
              </select>
              <input id="memKey" placeholder="key (e.g., name)" class="bg-[#050608] border border-white/10 text-gray-200 rounded-lg p-2 text-sm">
              <input id="memValue" placeholder="value (e.g., John)" class="bg-[#050608] border border-white/10 text-gray-200 rounded-lg p-2 text-sm">
            </div>
            <button id="addMemoryBtn" class="mt-2 w-full bg-purple-600 hover:bg-purple-500 text-white py-2 rounded-lg text-sm font-bold">💾 ${L('Save Fact','Simpan Fakta')}</button>
          </div>
          
          <!-- Stats -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="glass-card p-4 rounded-xl">
              <div class="text-xs text-gray-400">Total</div>
              <div class="text-2xl font-bold text-purple-400">${memories.length}</div>
            </div>
            <div class="glass-card p-4 rounded-xl">
              <div class="text-xs text-gray-400">Categories</div>
              <div class="text-2xl font-bold text-blue-400">${Object.keys(grouped).length}</div>
            </div>
          </div>
          
          <!-- Memory list by category -->
          ${Object.keys(grouped).length === 0 ? 
            '<div class="glass-card p-8 rounded-xl text-center text-gray-500 italic">' + L('No memories yet. Chat with AI to auto-extract facts.','Belum ada memori. Chat sama AI buat auto-extract fakta.') + '</div>'
          : Object.entries(grouped).map(([cat, items]) => `
            <div class="glass-card p-4 rounded-xl">
              <div class="flex items-center gap-2 mb-3">
                <span class="text-lg">${catIcons[cat] || '📝'}</span>
                <span class="text-sm font-bold text-white uppercase">${cat}</span>
                <span class="text-xs text-gray-500">(${items.length})</span>
              </div>
              <div class="space-y-1">
                ${items.map(m => `
                  <div class="flex items-center justify-between p-2 bg-white/5 rounded-lg group">
                    <div class="flex-1 min-w-0">
                      <span class="text-xs font-mono text-blue-300">${m.key}</span>
                      <span class="text-xs text-gray-500 mx-2">=</span>
                      <span class="text-xs text-white">${m.value}</span>
                    </div>
                    <button class="del-mem-btn opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-300 text-xs px-2" data-cat="${m.category}" data-key="${m.key}">✕</button>
                  </div>
                `).join('')}
              </div>
            </div>
          `).join('')}
        </div>
      `;
    },
    
    async history() {
      return `
        <div class="space-y-6">
          <h2 class="text-2xl font-bold text-white">${L('Chat History','Riwayat Chat')}</h2>
          <div class="glass-card p-6 rounded-2xl space-y-4">
            <button id="exportAllChatsBtn" class="w-full bg-blue-600 hover:bg-blue-500 text-white px-4 py-3 rounded-xl text-sm font-bold">📦 Export All Chats (JSON)</button>
            <input type="file" id="importChatsInput" accept=".json" class="w-full bg-[#050608] border border-white/10 text-gray-200 rounded-xl p-3 text-sm">
            <button id="importChatsBtn" class="w-full bg-green-600 hover:bg-green-500 text-white px-4 py-3 rounded-xl text-sm font-bold">📥 Import</button>
            <button id="clearAllChatsBtn" class="w-full bg-red-500/20 hover:bg-red-500/30 text-red-400 px-4 py-3 rounded-xl text-sm font-bold border border-red-500/30">🗑️ Delete All</button>
          </div>
        </div>
      `;
    },
    
    async security() {
      const s = loadSettings();
      return `
        <div class="space-y-6">
          <h2 class="text-2xl font-bold text-white">${L('Security','Keamanan')}</h2>
          <div class="glass-card p-6 rounded-2xl space-y-4">
            <div class="flex items-center justify-between p-3 bg-white/5 rounded-lg">
              <div><div class="text-sm text-white font-bold">Strict File Access</div></div>
              <input type="checkbox" id="autoStrictFile" ${s.strictFile!==false?'checked':''} class="w-10 h-5 rounded-full appearance-none bg-gray-700 checked:bg-red-500 cursor-pointer relative transition-all before:content-[''] before:absolute before:w-4 before:h-4 before:bg-white before:rounded-full before:top-0.5 before:left-0.5 before:transition-all checked:before:left-5">
            </div>
            <div class="flex items-center justify-between p-3 bg-white/5 rounded-lg">
              <div><div class="text-sm text-white font-bold">Auto-Backup</div></div>
              <input type="checkbox" id="autoBackup" ${s.backup!==false?'checked':''} class="w-10 h-5 rounded-full appearance-none bg-gray-700 checked:bg-blue-500 cursor-pointer relative transition-all before:content-[''] before:absolute before:w-4 before:h-4 before:bg-white before:rounded-full before:top-0.5 before:left-0.5 before:transition-all checked:before:left-5">
            </div>
            <div class="flex items-center justify-between p-3 bg-white/5 rounded-lg">
              <div><div class="text-sm text-white font-bold">Disable Telemetry</div></div>
              <input type="checkbox" id="autoTelemetry" ${s.disableTelemetry!==false?'checked':''} class="w-10 h-5 rounded-full appearance-none bg-gray-700 checked:bg-green-500 cursor-pointer relative transition-all before:content-[''] before:absolute before:w-4 before:h-4 before:bg-white before:rounded-full before:top-0.5 before:left-0.5 before:transition-all checked:before:left-5">
            </div>
          </div>
        </div>
      `;
    },
    
    async notifications() {
      const s = loadSettings();
      return `
        <div class="space-y-6">
          <h2 class="text-2xl font-bold text-white">Notifications</h2>
          <div class="glass-card p-6 rounded-2xl space-y-4">
            <div class="flex items-center justify-between p-3 bg-white/5 rounded-lg">
              <div><div class="text-sm text-white font-bold">Desktop Notification</div></div>
              <input type="checkbox" id="autoNotify" ${s.notifyDesktop?'checked':''} class="w-10 h-5 rounded-full appearance-none bg-gray-700 checked:bg-blue-500 cursor-pointer relative transition-all before:content-[''] before:absolute before:w-4 before:h-4 before:bg-white before:rounded-full before:top-0.5 before:left-0.5 before:transition-all checked:before:left-5">
            </div>
            <div class="flex items-center justify-between p-3 bg-white/5 rounded-lg">
              <div><div class="text-sm text-white font-bold">Sound Complete</div></div>
              <input type="checkbox" id="autoSoundComplete" ${s.soundComplete!==false?'checked':''} class="w-10 h-5 rounded-full appearance-none bg-gray-700 checked:bg-green-500 cursor-pointer relative transition-all before:content-[''] before:absolute before:w-4 before:h-4 before:bg-white before:rounded-full before:top-0.5 before:left-0.5 before:transition-all checked:before:left-5">
            </div>
            <button id="testNotificationBtn" class="w-full bg-blue-600 hover:bg-blue-500 text-white px-4 py-3 rounded-xl text-sm font-bold">🔔 Test</button>
          </div>
        </div>
      `;
    },
    
    async voice() {
      const s = loadSettings();
      return `
        <div class="space-y-6">
          <h2 class="text-2xl font-bold text-white">Voice & TTS</h2>
          <div class="glass-card p-6 rounded-2xl space-y-4">
            <div class="flex items-center justify-between p-3 bg-pink-500/10 border border-pink-500/20 rounded-lg">
              <div><div class="text-sm text-white font-bold">Enable TTS</div></div>
              <input type="checkbox" id="autoTTS" ${s.tts?'checked':''} class="w-10 h-5 rounded-full appearance-none bg-gray-700 checked:bg-pink-500 cursor-pointer relative transition-all before:content-[''] before:absolute before:w-4 before:h-4 before:bg-white before:rounded-full before:top-0.5 before:left-0.5 before:transition-all checked:before:left-5">
            </div>
            <div>
              <div class="flex justify-between text-sm font-bold text-white mb-2"><span>Speed</span><span id="val_ttsSpeed" class="text-pink-400 font-mono">${s.ttsSpeed||1}x</span></div>
              <input type="range" id="autoTtsSpeed" data-field="ttsSpeed" min="0.5" max="2" step="0.1" value="${s.ttsSpeed||1}" class="w-full accent-pink-500">
            </div>
            <button id="testTtsBtn" class="w-full bg-pink-600 hover:bg-pink-500 text-white px-4 py-3 rounded-xl text-sm font-bold">🔊 Test</button>
          </div>
        </div>
      `;
    },
    
    async developer() {
      const s = loadSettings();
      return `
        <div class="space-y-6">
          <h2 class="text-2xl font-bold text-white">Developer</h2>
          <div class="glass-card p-6 rounded-2xl space-y-4">
            <button id="exportConfigBtn" class="w-full bg-blue-600 hover:bg-blue-500 text-white px-4 py-3 rounded-xl text-sm font-bold">📤 Export Config</button>
            <input type="file" id="importConfigInput" accept=".json" class="w-full bg-[#050608] border border-white/10 text-gray-200 rounded-xl p-3 text-sm">
            <button id="importConfigBtn" class="w-full bg-green-600 hover:bg-green-500 text-white px-4 py-3 rounded-xl text-sm font-bold">📥 Import Config</button>
          </div>
        </div>
      `;
    },
  };
  
  const bindEvents = {
    general() {
      document.querySelectorAll('.lang-btn').forEach(b => b.onclick = () => { autoSave('language', b.dataset.lang); renderNav(); renderContent(); });
      document.querySelectorAll('.accent-btn').forEach(b => b.onclick = () => { 
        autoSave('accentColor', b.dataset.color); 
        document.documentElement.style.setProperty('--accent', b.dataset.color);
        renderContent(); 
      });
      const fs = document.getElementById('autoFontSize');
      if (fs) fs.oninput = () => {
        document.getElementById('fontSizeVal').textContent = fs.value + 'px';
        autoSave('fontSize', parseInt(fs.value));
        const cm = document.getElementById('chat-messages');
        if (cm) cm.style.fontSize = fs.value + 'px';
      };
    },
    workspace() {
      // Load stats kalau ada current workspace
      const s = loadSettings();
      if (s.workspace) {
        fetch('/api/workspace/validate', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({path: s.workspace})
        }).then(r => r.json()).then(data => {
          const el = document.getElementById('wsStats');
          const elDetail = document.getElementById('wsStatsDetail');
          if (el && data.valid) {
            el.innerHTML = `<span class="text-green-400">✅ ${data.total_files} files · ${data.size_human} · ${data.project_type}</span>`;
          }
          if (elDetail && data.valid) {
            elDetail.innerHTML = `
              <div class="grid grid-cols-2 gap-3 text-xs">
                <div><div class="text-gray-400">${L('Files','File')}</div><div class="text-white font-bold text-lg">${data.total_files.toLocaleString()}</div></div>
                <div><div class="text-gray-400">${L('Size','Ukuran')}</div><div class="text-white font-bold text-lg">${data.size_human}</div></div>
                <div><div class="text-gray-400">${L('Project Type','Tipe Project')}</div><div class="text-blue-400 font-bold">${data.project_type}</div></div>
                <div><div class="text-gray-400">${L('Name','Nama')}</div><div class="text-white font-bold">${data.name}</div></div>
              </div>
            `;
          }
        }).catch(e => console.warn('WS stats error:', e));
      }
      
      document.getElementById('changeWorkspaceBtn').onclick = () => {
        openWorkspaceBrowser(s.workspace || '~');
      };
      
      const clearBtn = document.getElementById('clearWorkspaceBtn');
      if (clearBtn) clearBtn.onclick = () => {
        if (!confirm(L('Remove workspace?','Hapus workspace?'))) return;
        const st = loadSettings();
        st.workspace = '';
        saveSettings(st);
        renderContent();
      };
    },
    
    provider() {
      document.getElementById('autoProvider').onchange = (e) => autoSave('provider', e.target.value);
      document.getElementById('autoBaseUrl').oninput = (e) => autoSave('baseUrl', e.target.value);
      document.getElementById('autoApiKey').oninput = (e) => autoSave('apiKey', e.target.value);
      
      // Toggle mata API key
      const toggleBtn = document.getElementById('toggleApiKeyBtn');
      if (toggleBtn) {
        toggleBtn.onclick = (e) => {
          e.preventDefault();
          const inp = document.getElementById('autoApiKey');
          const icon = toggleBtn.querySelector('i');
          if (inp.type === 'password') {
            inp.type = 'text';
            icon.className = 'ph ph-eye-slash text-lg text-green-400';
          } else {
            inp.type = 'password';
            icon.className = 'ph ph-eye text-lg';
          }
        };
      }
      document.getElementById('autoModel').oninput = (e) => autoSave('modelOverride', e.target.value);
      document.getElementById('autoFallback').oninput = (e) => autoSave('fallbackModel', e.target.value);
    },
    model() {
      const sliderMap = [
        { id: 'Temp', field: 'temp', isFloat: true },
        { id: 'TopP', field: 'topP', isFloat: true },
        { id: 'TopK', field: 'topK', isFloat: false },
        { id: 'MaxTokens', field: 'maxTokens', isFloat: false },
        { id: 'FreqPen', field: 'freqPen', isFloat: true },
        { id: 'PresPen', field: 'presPen', isFloat: true },
      ];
      sliderMap.forEach(({ id, field, isFloat }) => {
        const el = document.querySelector(`[data-field="${field}"]`);
        if (!el) {
          console.warn('[SETTINGS] Slider not found:', field);
          return;
        }
        el.oninput = () => {
          // Update display
          const disp = document.getElementById('val_' + id);
          if (disp) disp.textContent = el.value;
          // Save
          const v = isFloat ? parseFloat(el.value) : parseInt(el.value);
          autoSave(field, v);
        };
        // Trigger initial display
        const disp = document.getElementById('val_' + id);
        if (disp) disp.textContent = el.value;
      });
    },
    persona() {
      document.getElementById('autoSystemPrompt').oninput = (e) => autoSave('systemPrompt', e.target.value);
      document.querySelectorAll('.preset-btn').forEach(b => b.onclick = () => {
        const val = getLang() === 'en' ? b.dataset.en : b.dataset.id;
        document.getElementById('autoSystemPrompt').value = val;
        autoSave('systemPrompt', val);
      });
    },
    profiles() {
      document.getElementById('saveProfileBtn').onclick = async () => {
        const name = document.getElementById('profileName').value.trim();
        if (!name) return alert('Nama kosong');
        await fetch('/api/profiles', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name, config: loadSettings()}) });
        renderContent();
      };
      document.querySelectorAll('.load-profile-btn').forEach(b => b.onclick = async () => {
        const res = await fetch('/api/profiles');
        const data = await res.json();
        if (data[b.dataset.name]) { saveSettings(data[b.dataset.name].config); alert('Loaded: ' + b.dataset.name); renderContent(); }
      });
      document.querySelectorAll('.del-profile-btn').forEach(b => b.onclick = async () => {
        if (!confirm('Hapus ' + b.dataset.name + '?')) return;
        await fetch('/api/profiles/' + b.dataset.name, { method:'DELETE' });
        renderContent();
      });
    },
    usage() {
      document.getElementById('resetUsageBtn').onclick = async () => {
        if (!confirm('Reset usage stats?')) return;
        await fetch('/api/usage/reset', { method:'POST' });
        renderContent();
      };
    },
    memory() {
      const addBtn = document.getElementById('addMemoryBtn');
      if (addBtn) addBtn.onclick = async () => {
        const cat = document.getElementById('memCat').value;
        const key = document.getElementById('memKey').value.trim();
        const value = document.getElementById('memValue').value.trim();
        if (!key || !value) return alert('Key dan value harus diisi');
        await fetch('/api/memory/add', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify({category: cat, key, value})
        });
        renderContent();
      };
      
      document.querySelectorAll('.del-mem-btn').forEach(b => b.onclick = async () => {
        const cat = b.dataset.cat;
        const key = b.dataset.key;
        if (!confirm(`Delete [${cat}] ${key}?`)) return;
        await fetch(`/api/memory/${cat}/${key}`, {method: 'DELETE'});
        renderContent();
      });
      
      const clearBtn = document.getElementById('clearAllMemoryBtn');
      if (clearBtn) clearBtn.onclick = async () => {
        if (!confirm('Hapus SEMUA memori?')) return;
        await fetch('/api/memory/clear', {method: 'POST'});
        renderContent();
      };
    },
    
    history() {
      document.getElementById('exportAllChatsBtn').onclick = () => {
        const chats = localStorage.getItem('astrix_chats') || '{}';
        const blob = new Blob([chats], {type:'application/json'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = 'astrix-chats-' + Date.now() + '.json'; a.click();
      };
      document.getElementById('importChatsBtn').onclick = () => {
        const file = document.getElementById('importChatsInput').files[0];
        if (!file) return alert('Pilih file');
        const reader = new FileReader();
        reader.onload = (e) => {
          try {
            const existing = JSON.parse(localStorage.getItem('astrix_chats') || '{}');
            const imported = JSON.parse(e.target.result);
            localStorage.setItem('astrix_chats', JSON.stringify({...existing, ...imported}));
            alert('Imported ' + Object.keys(imported).length + ' chats');
          } catch(err) { alert('Error: ' + err.message); }
        };
        reader.readAsText(file);
      };
      document.getElementById('clearAllChatsBtn').onclick = () => {
        if (!confirm('Hapus SEMUA chat?')) return;
        localStorage.removeItem('astrix_chats');
        alert('Cleared'); window.location.reload();
      };
    },
    security() {
      document.getElementById('autoStrictFile').onchange = (e) => autoSave('strictFile', e.target.checked);
      document.getElementById('autoBackup').onchange = (e) => autoSave('backup', e.target.checked);
      document.getElementById('autoTelemetry').onchange = (e) => autoSave('disableTelemetry', e.target.checked);
    },
    notifications() {
      document.getElementById('autoNotify').onchange = (e) => autoSave('notifyDesktop', e.target.checked);
      document.getElementById('autoSoundComplete').onchange = (e) => autoSave('soundComplete', e.target.checked);
      document.getElementById('testNotificationBtn').onclick = () => {
        if ('Notification' in window) {
          Notification.requestPermission().then(p => {
            if (p === 'granted') new Notification('Astro AI', { body: 'Test berhasil! 🎉' });
          });
        }
      };
    },
    voice() {
      document.getElementById('autoTTS').onchange = (e) => autoSave('tts', e.target.checked);
      const ts = document.getElementById('autoTtsSpeed');
      if (ts) ts.oninput = () => { document.getElementById('val_ttsSpeed').textContent = ts.value + 'x'; autoSave('ttsSpeed', parseFloat(ts.value)); };
      document.getElementById('testTtsBtn').onclick = () => {
        if (!('speechSynthesis' in window)) return alert('No TTS');
        const u = new SpeechSynthesisUtterance(getLang() === 'en' ? 'This is a test.' : 'Ini adalah tes suara.');
        u.lang = getLang() === 'en' ? 'en-US' : 'id-ID';
        u.rate = parseFloat(document.getElementById('autoTtsSpeed').value) || 1;
        window.speechSynthesis.speak(u);
      };
    },
    developer() {
      document.getElementById('exportConfigBtn').onclick = () => {
        const exportData = { settings: loadSettings(), chats: JSON.parse(localStorage.getItem('astrix_chats')||'{}') };
        const blob = new Blob([JSON.stringify(exportData, null, 2)], {type:'application/json'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = 'astrix-config-' + Date.now() + '.json'; a.click();
      };
      document.getElementById('importConfigBtn').onclick = () => {
        const file = document.getElementById('importConfigInput').files[0];
        if (!file) return alert('Pilih file');
        const reader = new FileReader();
        reader.onload = (e) => {
          try {
            const data = JSON.parse(e.target.result);
            if (data.settings) saveSettings(data.settings);
            if (data.chats) localStorage.setItem('astrix_chats', JSON.stringify(data.chats));
            alert('Imported!'); window.location.reload();
          } catch(err) { alert('Error: ' + err.message); }
        };
        reader.readAsText(file);
      };
    },
  };
  
  // ==========================================
  // WORKSPACE FILE BROWSER
  // ==========================================
  window.openWorkspaceBrowser = function(startPath) {
    console.log('[WS] OPEN — startPath:', startPath);
    const lang = getLang();
    const T = (en, id) => lang === 'en' ? en : id;
    
    const old = document.getElementById('wsBrowserModal');
    if (old) old.remove();
    
    const modal = document.createElement('div');
    modal.id = 'wsBrowserModal';
    modal.style.cssText = 'position:fixed; inset:0; z-index:99999; display:flex; align-items:center; justify-content:center; background:rgba(0,0,0,0.85);';
    modal.innerHTML = `
      <div style="width:100%; max-width:720px; background:#0d1117; border-radius:16px; border:1px solid rgba(255,255,255,0.1); overflow:hidden; display:flex; flex-direction:column; max-height:90vh;">
        <div style="padding:16px; border-bottom:1px solid rgba(255,255,255,0.1); background:#161b22; display:flex; align-items:center; justify-content:space-between;">
          <div style="display:flex; align-items:center; gap:12px;">
            <span style="font-size:24px;">📁</span>
            <div>
              <div style="color:white; font-weight:bold; font-size:14px;">${T('Select Project Folder','Pilih Folder Project')}</div>
              <div id="wsBrowserPath" style="color:#60a5fa; font-family:monospace; font-size:11px; margin-top:2px;">Initializing...</div>
            </div>
          </div>
          <button id="wsBrowserClose" style="background:transparent; border:none; color:#9ca3af; font-size:20px; cursor:pointer; padding:4px 8px;">✕</button>
        </div>
        <div style="padding:8px; border-bottom:1px solid rgba(255,255,255,0.1); display:flex; gap:6px;">
          <input type="text" id="wsPathInput" placeholder="${T('Type path manually...','Ketik path manual...')}" style="flex:1; background:#050608; border:1px solid rgba(255,255,255,0.1); color:#e5e7eb; padding:6px 10px; border-radius:6px; font-family:monospace; font-size:11px; outline:none;">
          <button id="wsPathGo" style="background:#3b82f6; color:white; border:none; padding:6px 14px; border-radius:6px; font-size:11px; font-weight:bold; cursor:pointer;">Go</button>
        </div>
        <div id="wsFolderList" style="flex:1; overflow-y:auto; padding:8px; background:#0d1117; min-height:280px;"></div>
        <div style="padding:12px 16px; border-top:1px solid rgba(255,255,255,0.1); background:#161b22; display:flex; gap:8px;">
          <button id="wsBrowserCancel" style="padding:8px 16px; background:rgba(255,255,255,0.1); color:white; border:none; border-radius:6px; font-size:12px; cursor:pointer;">${T('Cancel','Batal')}</button>
          <button id="wsBrowserSelect" style="flex:1; padding:8px 16px; background:#22c55e; color:white; border:none; border-radius:6px; font-size:12px; font-weight:bold; cursor:pointer;">✓ ${T('Select This Folder','Pilih Folder Ini')}</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    
    const listEl = document.getElementById('wsFolderList');
    const pathEl = document.getElementById('wsBrowserPath');
    const inputEl = document.getElementById('wsPathInput');
    let currentPath = null;
    
    // GLOBAL CALLBACK — bisa dipanggil dari inline onclick
    window._wsNavigate = function(path) {
        console.log('[WS] _wsNavigate called:', path);
        if (typeof _wsInternalLoad === 'function') {
            _wsInternalLoad(path);
        }
    };
    
    async function _wsInternalLoad(path) {
        console.log('[WS] _wsInternalLoad:', path);
        listEl.innerHTML = '<div style="padding:16px; text-align:center; color:#9ca3af; font-size:12px;">⏳ Loading...</div>';
        
        try {
            const url = '/api/workspace/list' + (path ? '?path=' + encodeURIComponent(path) : '');
            const res = await fetch(url);
            const data = await res.json();
            console.log('[WS] Loaded:', data.current_path, '| items:', (data.items||[]).length);
            
            if (data.error) {
                listEl.innerHTML = '<div style="padding:16px; text-align:center; color:#ef4444; font-size:12px;">❌ ' + data.error + '</div>';
                return;
            }
            
            currentPath = data.current_path;
            pathEl.textContent = currentPath;
            inputEl.value = currentPath;
            listEl.innerHTML = '';
            
            // Parent button
            if (data.parent) {
                const escParent = data.parent.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
                listEl.insertAdjacentHTML('beforeend', `
                  <div onclick="window._wsNavigate('${escParent}')" 
                       style="padding:8px 10px; cursor:pointer; color:#93c5fd; display:flex; align-items:center; gap:8px; font-size:13px; border-bottom:1px solid rgba(255,255,255,0.1); margin-bottom:4px; border-radius:6px; user-select:none;"
                       onmouseover="this.style.background='rgba(255,255,255,0.1)'"
                       onmouseout="this.style.background='transparent'">
                    <span style="font-size:16px;">⬆</span> <span style="font-family:monospace;">.. parent</span>
                  </div>
                `);
            }
            
            const folders = (data.items || []).filter(i => i.is_dir);
            const files = (data.items || []).filter(i => !i.is_dir);
            
            if (folders.length === 0 && files.length === 0) {
                listEl.insertAdjacentHTML('beforeend', '<div style="padding:16px; text-align:center; color:#6b7280; font-size:12px; font-style:italic;">Folder kosong</div>');
            }
            
            // FOLDER BUTTONS — INLINE onclick
            folders.forEach(function(item) {
                const sep = currentPath.endsWith('/') ? '' : '/';
                const fullPath = currentPath + sep + item.name;
                // Escape path untuk inline JS string
                const escPath = fullPath.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
                const escName = item.name.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                
                listEl.insertAdjacentHTML('beforeend', `
                  <div onclick="window._wsNavigate('${escPath}')"
                       style="padding:8px 10px; cursor:pointer; color:#c9d1d9; display:flex; align-items:center; gap:8px; font-size:14px; border-radius:6px; user-select:none;"
                       onmouseover="this.style.background='rgba(255,255,255,0.1)'"
                       onmouseout="this.style.background='transparent'">
                    <span style="color:#eab308; font-size:18px;">📁</span>
                    <span style="truncate">${escName}</span>
                  </div>
                `);
            });
            
            // Files
            files.slice(0, 20).forEach(function(item) {
                const escName = item.name.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                listEl.insertAdjacentHTML('beforeend', `
                  <div style="padding:8px 10px; color:#6b7280; display:flex; align-items:center; gap:8px; font-size:11px; opacity:0.5;">
                    <span>📄</span>
                    <span>${escName}</span>
                    <span style="margin-left:auto; color:#4b5563;">${item.size_human || ''}</span>
                  </div>
                `);
            });
            
            if (files.length > 20) {
                listEl.insertAdjacentHTML('beforeend', '<div style="padding:8px; text-align:center; color:#4b5563; font-size:11px;">... +' + (files.length - 20) + ' files</div>');
            }
        } catch (err) {
            console.error('[WS] Error:', err);
            listEl.innerHTML = '<div style="padding:16px; text-align:center; color:#ef4444; font-size:12px;">❌ ' + err.message + '</div>';
        }
    }
    
    // Handlers
    document.getElementById('wsBrowserClose').onclick = () => { delete window._wsNavigate; modal.remove(); };
    document.getElementById('wsBrowserCancel').onclick = () => { delete window._wsNavigate; modal.remove(); };
    document.getElementById('wsPathGo').onclick = () => {
        const p = inputEl.value.trim();
        if (p) _wsInternalLoad(p);
    };
    inputEl.onkeydown = (e) => {
        if (e.key === 'Enter') document.getElementById('wsPathGo').click();
    };
    
    let selectArmed = false;
    setTimeout(() => { selectArmed = true; }, 500);
    document.getElementById('wsBrowserSelect').onclick = async () => {
        if (!selectArmed) return;
        if (!currentPath) { alert('No folder selected'); return; }
        
        console.log('[WS] SELECT:', currentPath);
        const btn = document.getElementById('wsBrowserSelect');
        btn.disabled = true;
        btn.textContent = '⏳ ' + T('Validating...','Memvalidasi...');
        
        try {
            const res = await fetch('/api/workspace/validate', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({path: currentPath})
            });
            const data = await res.json();
            console.log('[WS] Validate:', data);
            
            if (!data.valid) {
                alert('❌ ' + (data.error || 'Invalid'));
                btn.disabled = false;
                btn.textContent = '✓ ' + T('Select This Folder','Pilih Folder Ini');
                return;
            }
            
            const s = loadSettings();
            s.workspace = currentPath;
            saveSettings(s);
            delete window._wsNavigate;
            modal.remove();
            renderContent();
            console.log('[WORKSPACE] ✅ Saved:', currentPath);
        } catch (e) {
            alert('Error: ' + e.message);
            btn.disabled = false;
        }
    };
    
    const initialPath = (startPath && startPath !== '~') ? startPath : null;
    _wsInternalLoad(initialPath);
};
  
    function init() {
    loadSettings();
    
    // Open button
    const openBtn = document.getElementById('openSettingsBtn');
    if (openBtn) {
      const nb = openBtn.cloneNode(true);
      openBtn.parentNode.replaceChild(nb, openBtn);
      nb.onclick = () => {
        document.getElementById('settingsPanel').classList.remove('hidden');
        document.getElementById('settingsPanel').classList.add('flex');
        renderNav();
        renderContent();
      };
    }
    
    // Close button — cukup tutup, karena semua udah auto-save
    const closeBtn = document.getElementById('closeSettingsBtn');
    if (closeBtn) {
      const nb = closeBtn.cloneNode(true);
      closeBtn.parentNode.replaceChild(nb, closeBtn);
      nb.onclick = () => {
        document.getElementById('settingsPanel').classList.add('hidden');
        document.getElementById('settingsPanel').classList.remove('flex');
      };
    }
    
    // SIMPAN button — cukup tutup (auto-save udah handle)
    const saveBtn = document.getElementById('saveSettingsBtn');
    if (saveBtn) {
      const nb = saveBtn.cloneNode(true);
      saveBtn.parentNode.replaceChild(nb, saveBtn);
      nb.onclick = () => {
        nb.innerHTML = '✅ Tersimpan!';
        nb.style.background = '#22c55e';
        setTimeout(() => {
          nb.innerHTML = '<i class="ph-bold ph-floppy-disk"></i> SIMPAN';
          nb.style.background = '';
          document.getElementById('settingsPanel').classList.add('hidden');
          document.getElementById('settingsPanel').classList.remove('flex');
        }, 500);
      };
    }
    
    // [REMOVED] autosaveIndicator (selector error)
    
    // === EVENT DELEGATION (Anti-gagal) ===
    document.addEventListener('click', async (e) => {
      const btn = e.target.closest('#detectModelsBtn');
      if (!btn) return;
      
      e.preventDefault();
      e.stopPropagation();
      
      const baseUrl = (document.getElementById('autoBaseUrl') || {}).value?.trim();
      const apiKey = (document.getElementById('autoApiKey') || {}).value?.trim();
      const status = document.getElementById('detectStatus');
      const keyStatus = document.getElementById('keyStatus');
      
      if (!baseUrl) { 
        if (status) { status.textContent = '❌ Base URL kosong'; status.style.color = '#f87171'; } 
        return; 
      }
      
      if (status) { status.textContent = '⏳ Memuat model...'; status.style.color = '#fbbf24'; }
      if (keyStatus) { keyStatus.textContent = '⏳ Memvalidasi...'; keyStatus.style.color = '#fbbf24'; }
      btn.disabled = true;
      
      try {
        const res = await fetch('/api/fetch-models', { 
          method:'POST', 
          headers:{'Content-Type':'application/json'}, 
          body: JSON.stringify({base_url: baseUrl, api_key: apiKey}) 
        });
        const data = await res.json();
        
        if (data.error) {
          if (keyStatus) { keyStatus.textContent = `❌ ${data.error}`; keyStatus.style.color = '#f87171'; }
          if (status) { status.textContent = `❌ ${data.error}`; status.style.color = '#f87171'; }
          btn.disabled = false;
          return;
        }
        
        if (data.models && data.models.length) {
          if (keyStatus) { keyStatus.textContent = `✅ Valid (${data.models.length} model)`; keyStatus.style.color = '#4ade80'; }
          if (status) { status.textContent = `✅ ${data.models.length} model ditemukan!`; status.style.color = '#4ade80'; }
          
          const selMain = document.getElementById('autoModel');
          const selFall = document.getElementById('autoFallback');
          if (selMain) selMain.innerHTML = data.models.map(m => `<option value="${m}">${m}</option>`).join('');
          if (selFall) selFall.innerHTML = '<option value="">-- Tanpa cadangan --</option>' + data.models.map(m => `<option value="${m}">${m}</option>`).join('');
          
          localStorage.setItem('astrix_cached_models', JSON.stringify(data.models));
          autoSave('lastKeyValidation', true);
        } else {
          if (status) { status.textContent = '⚠️ 0 model'; status.style.color = '#fbbf24'; }
        }
      } catch(err) {
        if (status) { status.textContent = '❌ ' + err.message; status.style.color = '#f87171'; }
      } finally {
        btn.disabled = false;
      }
    });
    document.addEventListener('change', (e) => {
      if (e.target.id === 'autoModel') autoSave('modelOverride', e.target.value);
      if (e.target.id === 'autoFallback') autoSave('fallbackModel', e.target.value);
    });
    // event-delegation-settings
    
    // === EVENT DELEGATION: 5 MODE & PRESET (anti-gagal) ===
    document.addEventListener('click', (e) => {
      // Mode buttons
      const modeBtn = e.target.closest('.mode-btn');
      if (modeBtn) {
        e.preventDefault(); e.stopPropagation();
        const modeId = modeBtn.dataset.mode;
        const mode = MODES.find(m => m.id === modeId);
        if (!mode) return;
        
        const lang = getLang();
        const s = loadSettings();
        s.systemPrompt = lang === 'en' ? mode.prompt_en : mode.prompt_id;
        s.temp = mode.temp;
        s.maxTokens = mode.maxTokens;
        s.compressHistory = mode.compressHistory;
        s.activeMode = modeId;
        saveSettings(s);
        
        console.log('[SETTINGS] ✅ Mode applied:', modeId, {temp: mode.temp, maxTokens: mode.maxTokens});
        
        // Update UI langsung tanpa re-render (biar gak flicker)
        document.querySelectorAll('.mode-btn').forEach(b => {
          b.className = b.className.replace('border-blue-500 bg-blue-600/20 ring-2 ring-blue-500/30', 'border-white/10 bg-white/5 hover:bg-white/10');
        });
        modeBtn.className = modeBtn.className.replace('border-white/10 bg-white/5 hover:bg-white/10', 'border-blue-500 bg-blue-600/20 ring-2 ring-blue-500/30');
        
        // Update System Prompt textarea
        const sp = document.getElementById('autoSystemPrompt');
        if (sp) sp.value = s.systemPrompt;
        
        // Show toast
        showModeToast(lang === 'en' ? mode.label_en : mode.label_id);
        return;
      }
      
      // Preset buttons
      const presetBtn = e.target.closest('.preset-btn');
      if (presetBtn) {
        const val = getLang() === 'en' ? presetBtn.dataset.en : presetBtn.dataset.id;
        const sp = document.getElementById('autoSystemPrompt');
        if (sp) sp.value = val;
        autoSave('systemPrompt', val);
        const s = loadSettings();
        if (s.activeMode) { s.activeMode = null; saveSettings(s); }
        return;
      }
    });
    
    // Detect System Prompt manual edit → clear activeMode
    document.addEventListener('input', (e) => {
      if (e.target.id === 'autoSystemPrompt') {
        autoSave('systemPrompt', e.target.value);
        const s = loadSettings();
        if (s.activeMode) { s.activeMode = null; saveSettings(s); }
        document.querySelectorAll('.mode-btn').forEach(b => {
          b.className = b.className.replace('border-blue-500 bg-blue-600/20 ring-2 ring-blue-500/30', 'border-white/10 bg-white/5 hover:bg-white/10');
        });
      }
    });
    
    // Toast helper
    function showModeToast(text) {
      const old = document.getElementById('modeToast');
      if (old) old.remove();
      const toast = document.createElement('div');
      toast.id = 'modeToast';
      toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:linear-gradient(135deg,#3b82f6,#a855f7);color:white;padding:12px 24px;border-radius:12px;font-weight:bold;font-size:14px;box-shadow:0 10px 40px rgba(59,130,246,0.5);z-index:99999;animation:slideUp 0.3s ease;';
      toast.textContent = '✅ ' + text + ' active';
      document.body.appendChild(toast);
      setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.3s'; }, 1500);
      setTimeout(() => toast.remove(), 1900);
    }
    // event-delegation-modes
    
    // [global fallback removed]
    
    console.log('[SETTINGS] v3 AUTO-SAVE loaded');
  }
  
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
