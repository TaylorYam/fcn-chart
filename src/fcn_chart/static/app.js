'use strict';

// ---- 設定 ----------------------------------------------------------------

// TradingView 網站預設淺色主題的配色。
const TV = {
  up: '#089981',
  down: '#F23645',
  text: '#131722',
  grid: '#F0F3FA',
  font: "-apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, Ubuntu, sans-serif",
  fontSize: 12,
  legendFontSize: 13,
};

const LEVEL_STYLE = {
  KO: { color: '#16a34a', lineStyle: LightweightCharts.LineStyle.Solid },
  K1: { color: '#2563eb', lineStyle: LightweightCharts.LineStyle.Solid },
  K2: { color: '#7c3aed', lineStyle: LightweightCharts.LineStyle.Solid },
  KI: { color: '#dc2626', lineStyle: LightweightCharts.LineStyle.Dashed },
};
const LINE_WIDTH = 2;

// 區間按鈕：月數，或 'YTD'。
const DEFAULT_RANGE = '12';

// 匯出圖：PPT 圖片 32.2 × 14.4 公分。版面以 96 DPI（約 1217 × 544 px）排，
// 實際以 2 倍解析度輸出（192 DPI），並在 PNG 寫入 DPI，插入 PPT 時就是這個尺寸。
const PPT_CM = { width: 32.2, height: 14.4 };
const EXPORT_SCALE = 2;
const EXPORT_DPI = 96 * EXPORT_SCALE;
const EXPORT = {
  width: Math.round((PPT_CM.width / 2.54) * EXPORT_DPI),
  height: Math.round((PPT_CM.height / 2.54) * EXPORT_DPI),
};

const PCT_IDS = ['ko', 'k1', 'k2', 'ki'];
const STORAGE_KEY = 'fcn-chart:last-input';

// ---- 工具 ----------------------------------------------------------------

const $ = (sel, root = document) => root.querySelector(sel);

const symbolInputs = () => [...document.querySelectorAll('.sym')];

// 讀取 5 個代號欄：去空白、去重複，保留順序。
function readSymbols() {
  const seen = new Set();
  return symbolInputs()
    .map((input) => input.value.trim())
    .filter((s) => {
      const key = s.toUpperCase();
      if (!s || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

// 與 TradingView 一致：不加千分位。
function fmtPrice(value, decimals) {
  return value.toFixed(decimals);
}

function fmtPct(pct) {
  return `${Number(pct.toFixed(4))}%`;
}

function pctValue(id) {
  const raw = $(`#${id}`).value.trim();
  return raw === '' ? null : Number(raw);
}

function loadLastInput() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (!saved) return;
    const symbols = Array.isArray(saved.symbols) ? saved.symbols : [];
    symbolInputs().forEach((input, i) => { input.value = symbols[i] ?? ''; });
    for (const id of PCT_IDS) if (id in saved) $(`#${id}`).value = saved[id];
  } catch { /* 無痕模式等情況讀不到就算了 */ }
}

function saveLastInput() {
  try {
    const value = { symbols: symbolInputs().map((input) => input.value) };
    for (const id of PCT_IDS) value[id] = $(`#${id}`).value;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch { /* ignore */ }
}

function rangeStart(lastTime, range) {
  const last = new Date(`${lastTime}T00:00:00Z`);
  if (range === 'YTD') return `${last.getUTCFullYear()}-01-01`;
  const start = new Date(last);
  start.setUTCMonth(start.getUTCMonth() - Number(range));
  return start.toISOString().slice(0, 10);
}

// ---- 圖例（TradingView 左上角的 OHLC） --------------------------------------

function legendModel(data, candle) {
  const idx = data.candles.indexOf(candle);
  const prev = idx > 0 ? data.candles[idx - 1] : null;
  const change = prev ? candle.close - prev.close : 0;
  const changePct = prev ? (change / prev.close) * 100 : 0;
  const sign = change >= 0 ? '+' : '−';
  const d = data.decimals;
  return {
    title: `${data.name} · 1D · ${data.exchange || data.ticker}`,
    color: candle.close >= candle.open ? TV.up : TV.down,
    ohlc: [
      ['O', fmtPrice(candle.open, d)],
      ['H', fmtPrice(candle.high, d)],
      ['L', fmtPrice(candle.low, d)],
      ['C', fmtPrice(candle.close, d)],
    ],
    change: `${sign}${fmtPrice(Math.abs(change), d)} (${sign}${Math.abs(changePct).toFixed(2)}%)`,
  };
}

function renderLegendHtml(el, model) {
  const ohlc = model.ohlc.map(([k, v]) => `<span>${k}<b>${v}</b></span>`).join('');
  el.style.setProperty('--legend-color', model.color);
  el.innerHTML = `<div class="legend-row"><span class="legend-title"></span>${ohlc}<b>${model.change}</b></div>`;
  // 名稱用 textContent，避免任何 HTML 字元被解讀。
  $('.legend-title', el).textContent = model.title;
}

function drawLegendCanvas(ctx, model, s) {
  const size = TV.legendFontSize * s;
  const y = 8 * s + size;
  let x = 12 * s;
  ctx.textBaseline = 'alphabetic';

  const segment = (text, color, gapAfter, weight = 400) => {
    ctx.font = `${weight} ${size}px ${TV.font}`;
    ctx.fillStyle = color;
    ctx.fillText(text, x, y);
    x += ctx.measureText(text).width + gapAfter;
  };

  segment(model.title, TV.text, 10 * s, 500);
  for (const [k, v] of model.ohlc) {
    segment(k, TV.text, 2 * s);
    segment(v, model.color, 8 * s);
  }
  segment(model.change, model.color, 0);
}

// ---- FCN 參數表格（圖例下方） ---------------------------------------------

function tableModel(data) {
  const d = data.decimals;
  const strikes = data.levels.filter((l) => l.name !== 'KO');
  return {
    headers: ['連結標的', '參考最新價', ...strikes.map((l) => `${l.label} (${fmtPct(l.pct)})`)],
    row: [data.ticker, fmtPrice(data.ref_close, d), ...strikes.map((l) => fmtPrice(l.price, d))],
  };
}

function renderTableHtml(table, model) {
  table.replaceChildren();
  const head = table.createTHead().insertRow();
  for (const text of model.headers) head.appendChild(document.createElement('th')).textContent = text;
  const body = table.createTBody().insertRow();
  for (const text of model.row) body.insertCell().textContent = text;
}

// 依畫面上表格的實際排版（CSS px）放大 s 倍畫到匯出圖，確保兩者一致。
function drawTableCanvas(ctx, table, origin, s) {
  const box = table.getBoundingClientRect();
  const X = (v) => (v - origin.left) * s;
  const Y = (v) => (v - origin.top) * s;
  ctx.fillStyle = '#fff';
  ctx.fillRect(X(box.left), Y(box.top), box.width * s, box.height * s);

  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  for (const cell of table.querySelectorAll('th, td')) {
    const r = cell.getBoundingClientRect();
    const style = getComputedStyle(cell);
    if (cell.tagName === 'TH') {
      ctx.fillStyle = style.backgroundColor;
      ctx.fillRect(X(r.left), Y(r.top), r.width * s, r.height * s);
    }
    ctx.fillStyle = style.color;
    ctx.font = `${style.fontWeight} ${parseFloat(style.fontSize) * s}px ${style.fontFamily}`;
    ctx.fillText(cell.textContent, X(r.left + r.width / 2), Y(r.top + r.height / 2));
  }
  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';

  const tableStyle = getComputedStyle(table);
  const top = parseFloat(tableStyle.borderTopWidth) * s;
  const bottom = parseFloat(tableStyle.borderBottomWidth) * s;
  ctx.fillStyle = '#000';
  ctx.fillRect(X(box.left), Y(box.top), box.width * s, top);
  ctx.fillRect(X(box.left), Y(box.bottom) - bottom, box.width * s, bottom);
}

// ---- 圖表 ----------------------------------------------------------------

// 左上角圖例＋表格是白底，讓價格軸上方預留它們的高度，K棒與價位線就不會被蓋住。
const OVERLAY_GAP = 10;
const BOTTOM_MARGIN = 0.08;

function reserveOverlaySpace(chart, overlay, chartHeight, s = 1) {
  const reserved = (overlay.offsetTop + overlay.offsetHeight + OVERLAY_GAP) * s;
  const top = Math.min(reserved / chartHeight, 0.6);
  chart.priceScale('right').applyOptions({ scaleMargins: { top, bottom: BOTTOM_MARGIN } });
}

// s：放大倍率（匯出用）。字級、線寬乘上 s。
function createChart(el, data, s = 1) {
  const chart = LightweightCharts.createChart(el, {
    width: el.clientWidth,
    height: el.clientHeight,
    layout: {
      background: { type: 'solid', color: '#ffffff' },
      textColor: TV.text,
      fontSize: TV.fontSize * s,
      fontFamily: TV.font,
      attributionLogo: true,
    },
    grid: { vertLines: { color: TV.grid }, horzLines: { color: TV.grid } },
    rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.1, bottom: BOTTOM_MARGIN } },
    timeScale: { borderVisible: false, rightOffset: 10, fixLeftEdge: true, minBarSpacing: 0.5 },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  });

  const minMove = 1 / 10 ** data.decimals;
  const levelPrices = data.levels.map((l) => l.price);

  const candles = chart.addCandlestickSeries({
    upColor: TV.up,
    downColor: TV.down,
    borderUpColor: TV.up,
    borderDownColor: TV.down,
    wickUpColor: TV.up,
    wickDownColor: TV.down,
    priceFormat: { type: 'price', precision: data.decimals, minMove },
    // KO 100% 線就是最後收盤價，隱藏內建的最新價線避免標籤重疊。
    priceLineVisible: false,
    lastValueVisible: false,
    // 確保 KO/K/KI 線即使超出K線高低點也在可視範圍內。
    autoscaleInfoProvider: (original) => {
      const res = original();
      if (!res || !levelPrices.length) return res;
      res.priceRange.minValue = Math.min(res.priceRange.minValue, ...levelPrices);
      res.priceRange.maxValue = Math.max(res.priceRange.maxValue, ...levelPrices);
      return res;
    },
  });

  for (const level of data.levels) {
    candles.createPriceLine({
      price: level.price,
      color: LEVEL_STYLE[level.name].color,
      lineStyle: LEVEL_STYLE[level.name].lineStyle,
      lineWidth: LINE_WIDTH * s,
      axisLabelVisible: true,
      title: `${level.label} ${fmtPct(level.pct)}｜${fmtPrice(level.price, data.decimals)}`,
    });
  }

  return { chart, candles };
}

// 只載入區間內的K棒並固定左邊界：Lightweight Charts 只有在左邊界固定時，
// 才會把貼邊的時間標籤往內推，否則最左邊的月份會被切掉一半。
function applyRange(card, range) {
  const { data } = card;
  const start = rangeStart(data.candles.at(-1).time, range);
  card.shown = data.candles.filter((c) => c.time >= start);
  card.candles.setData(card.shown);
  card.chart.timeScale().fitContent();
}

// ---- 匯出 ----------------------------------------------------------------

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('logo 載入失敗'));
    img.src = src;
  });
}

// TV logo 是疊在圖上的 HTML 元素，takeScreenshot 不會包含，要自己畫上去。
async function logoImage(logoEl) {
  const svg = $('svg', logoEl);
  if (!svg) return null;
  const markup = svg.outerHTML.replaceAll('var(--fill)', TV.text).replaceAll('var(--stroke)', '#fff');
  return loadImage(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(markup)}`);
}

// 匯出時另建一張「一開始就是匯出尺寸與字級」的隱藏圖表再截圖。
// 不能把畫面上的圖表暫時放大：Lightweight Charts 會快取文字寬度，
// 改字級後邊緣的時間標籤會內縮不足而被切掉。
async function renderExportCanvas(card) {
  const { data, table } = card;
  const s = EXPORT_SCALE;
  const W = EXPORT.width;
  const H = EXPORT.height;
  const overlay = table.parentElement;

  const host = document.createElement('div');
  host.style.cssText = `position:fixed;left:${-W - 100}px;top:0;width:${W}px;height:${H}px;`;
  document.body.append(host);
  let shot;
  let logo = null;
  let logoBottom = H;
  const exp = createChart(host, data, s);
  try {
    exp.candles.setData(card.shown);
    reserveOverlaySpace(exp.chart, overlay, H, s);
    exp.chart.timeScale().fitContent();
    shot = exp.chart.takeScreenshot();
    const logoEl = $('#tv-attr-logo', host);
    if (logoEl) {
      // logo 的 CSS 是 left/bottom 10px；換算成「圖表區底部」再依倍率重新定位。
      logoBottom = logoEl.getBoundingClientRect().bottom - host.getBoundingClientRect().top + 10;
      logo = await logoImage(logoEl);
    }
  } finally {
    exp.chart.remove();
    host.remove();
  }

  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(shot, 0, 0, W, H);

  drawLegendCanvas(ctx, legendModel(data, card.shown.at(-1)), s);
  drawTableCanvas(ctx, table, overlay.parentElement.getBoundingClientRect(), s);
  if (logo) {
    const w = logo.width * s;
    const h = logo.height * s;
    ctx.drawImage(logo, 10 * s, logoBottom - 10 * s - h, w, h);
  }
  return canvas;
}

function canvasToBlob(canvas) {
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('PNG 產生失敗'))), 'image/png'),
  ).then((blob) => withDpi(blob, EXPORT_DPI));
}

// 在 PNG 的 IHDR 之後插入 pHYs（解析度）區塊，PPT 插入圖片時才會是 32.2 × 14.4 公分。
async function withDpi(blob, dpi) {
  const png = new Uint8Array(await blob.arrayBuffer());
  const ppm = Math.round(dpi / 0.0254);
  const chunk = new Uint8Array(21);
  const view = new DataView(chunk.buffer);
  view.setUint32(0, 9);
  chunk.set([0x70, 0x48, 0x59, 0x73], 4); // "pHYs"
  view.setUint32(8, ppm);
  view.setUint32(12, ppm);
  chunk[16] = 1; // 單位：公尺
  view.setUint32(17, crc32(chunk.subarray(4, 17)));
  const ihdrEnd = 8 + 25; // PNG 簽章 8 bytes + IHDR 區塊 25 bytes
  return new Blob([png.subarray(0, ihdrEnd), chunk, png.subarray(ihdrEnd)], { type: 'image/png' });
}

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(bytes) {
  let c = 0xffffffff;
  for (const b of bytes) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function fileName(data) {
  return `${data.ticker.replace(' ', '_')}_FCN_${data.ref_date}.png`;
}

function downloadBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ---- 卡片 ----------------------------------------------------------------

const cards = [];

function setStatus(card, text, isError = false) {
  const el = $('.status', card.root);
  el.textContent = text;
  el.classList.toggle('error', isError);
}

function buildCard(symbol) {
  const root = $('#card-template').content.firstElementChild.cloneNode(true);
  $('.ticker', root).textContent = symbol.toUpperCase();
  root.classList.add('loading');
  $('#cards').append(root);
  const card = {
    root,
    symbol,
    el: $('.chart', root),
    legend: $('.legend', root),
    table: $('.fcn-table', root),
  };
  setStatus(card, '讀取中…');
  return card;
}

function fillCard(card, data) {
  card.data = data;
  card.root.classList.remove('loading');
  $('.ticker', card.root).textContent = data.ticker;
  $('.ref', card.root).textContent =
    `期初價 ${fmtPrice(data.ref_close, data.decimals)} ${data.currency}（${data.ref_date} 收盤）`;

  Object.assign(card, createChart(card.el, data));
  applyRange(card, DEFAULT_RANGE);
  renderTableHtml(card.table, tableModel(data));
  const overlay = card.table.parentElement;
  reserveOverlaySpace(card.chart, overlay, card.el.clientHeight);

  const showLegend = (candle) => renderLegendHtml(card.legend, legendModel(data, candle));
  showLegend(card.shown.at(-1));
  card.chart.subscribeCrosshairMove((param) => {
    const bar = param.time && card.shown.find((c) => c.time === param.time);
    showLegend(bar || card.shown.at(-1));
  });

  card.observer = new ResizeObserver(() => {
    card.chart.resize(card.el.clientWidth, card.el.clientHeight);
    reserveOverlaySpace(card.chart, overlay, card.el.clientHeight);
    card.chart.timeScale().fitContent();
  });
  card.observer.observe(card.el);

  for (const btn of card.root.querySelectorAll('.ranges button')) {
    btn.addEventListener('click', () => {
      card.root.querySelectorAll('.ranges button').forEach((b) => b.classList.toggle('active', b === btn));
      applyRange(card, btn.dataset.range);
      showLegend(card.shown.at(-1));
    });
  }

  $('.download', card.root).addEventListener('click', async () => {
    downloadBlob(await canvasToBlob(await renderExportCanvas(card)), fileName(data));
  });

  $('.copy', card.root).addEventListener('click', async () => {
    try {
      // ClipboardItem 接受 Promise，讓寫入剪貼簿仍算在這次點擊的使用者操作內。
      const blob = renderExportCanvas(card).then(canvasToBlob);
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
      setStatus(card, '已複製，可直接在 PPT 按 Ctrl+V 貼上。');
    } catch (err) {
      setStatus(card, `複製失敗：${err.message}（請改用下載 PNG）`, true);
    }
  });

  setStatus(card, '');
}

function failCard(card, message) {
  card.root.classList.remove('loading');
  card.root.classList.add('failed');
  setStatus(card, message, true);
}

function clearCards() {
  for (const card of cards) {
    card.observer?.disconnect();
    card.chart?.remove();
  }
  cards.length = 0;
  $('#cards').replaceChildren();
}

async function loadCard(card, pcts) {
  const params = new URLSearchParams({ symbol: card.symbol });
  for (const [key, value] of Object.entries(pcts)) if (value !== null) params.set(key, value);
  try {
    const res = await fetch(`/api/chart?${params}`);
    const body = await res.json();
    if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : '參數錯誤');
    fillCard(card, body);
  } catch (err) {
    failCard(card, `${card.symbol}：${err.message}`);
  }
}

// ---- 事件 ----------------------------------------------------------------

$('#form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const symbols = readSymbols();
  if (!symbols.length) {
    symbolInputs()[0].focus();
    return;
  }
  saveLastInput();

  const pcts = Object.fromEntries(PCT_IDS.map((id) => [id, pctValue(id)]));
  clearCards();
  $('#download-all').disabled = true;
  const pending = symbols.map((symbol) => {
    const card = buildCard(symbol);
    cards.push(card);
    return loadCard(card, pcts);
  });
  await Promise.all(pending);
  $('#download-all').disabled = !cards.some((c) => c.data);
});

$('#download-all').addEventListener('click', async () => {
  const zip = new JSZip();
  for (const card of cards.filter((c) => c.data)) {
    zip.file(fileName(card.data), await canvasToBlob(await renderExportCanvas(card)));
  }
  const today = new Date().toISOString().slice(0, 10);
  downloadBlob(await zip.generateAsync({ type: 'blob' }), `FCN_charts_${today}.zip`);
});

loadLastInput();
