'use strict';

// ---- 設定 ----------------------------------------------------------------

// TradingView 網站預設淺色主題的配色。
const TV = {
  up: '#089981',
  down: '#F23645',
  volUp: 'rgba(8, 153, 129, 0.5)',
  volDown: 'rgba(242, 54, 69, 0.5)',
  text: '#131722',
  grid: '#F0F3FA',
  font: "-apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, Ubuntu, sans-serif",
  fontSize: 12,
  legendFontSize: 13,
};

const LEVEL_STYLE = {
  KO: { color: '#16a34a', lineStyle: LightweightCharts.LineStyle.Solid },
  K: { color: '#2563eb', lineStyle: LightweightCharts.LineStyle.Solid },
  KI: { color: '#dc2626', lineStyle: LightweightCharts.LineStyle.Dashed },
};
const LINE_WIDTH = 2;

// 區間按鈕：月數，或 'YTD'。
const DEFAULT_RANGE = '12';

// 匯出圖：16:9；整張圖等比例放大 EXPORT_SCALE 倍（字級、圖例、logo），讓貼進 PPT 仍清楚。
const EXPORT = { width: 1600, height: 900 };
const EXPORT_SCALE = 4 / 3;

const STORAGE_KEY = 'fcn-chart:last-input';

// ---- 工具 ----------------------------------------------------------------

const $ = (sel, root = document) => root.querySelector(sel);

function splitSymbols(text) {
  const seen = new Set();
  return text.split(/[\s,，、;；]+/).filter((s) => {
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

function fmtVolume(v) {
  const units = [[1e9, 'B'], [1e6, 'M'], [1e3, 'K']];
  for (const [size, unit] of units) if (v >= size) return `${(v / size).toFixed(2)}${unit}`;
  return String(Math.round(v));
}

function displayTicker(data) {
  return data.symbol.replace(/\.T$/, '');
}

function pctValue(id) {
  const raw = $(`#${id}`).value.trim();
  return raw === '' ? null : Number(raw);
}

function loadLastInput() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (!saved) return;
    $('#symbols').value = saved.symbols ?? '';
    for (const id of ['ko', 'k', 'ki']) $(`#${id}`).value = saved[id] ?? '';
  } catch { /* 無痕模式等情況讀不到就算了 */ }
}

function saveLastInput() {
  try {
    const value = { symbols: $('#symbols').value };
    for (const id of ['ko', 'k', 'ki']) value[id] = $(`#${id}`).value;
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
    title: `${data.name} · 1D · ${data.exchange || displayTicker(data)}`,
    color: candle.close >= candle.open ? TV.up : TV.down,
    ohlc: [
      ['O', fmtPrice(candle.open, d)],
      ['H', fmtPrice(candle.high, d)],
      ['L', fmtPrice(candle.low, d)],
      ['C', fmtPrice(candle.close, d)],
    ],
    change: `${sign}${fmtPrice(Math.abs(change), d)} (${sign}${Math.abs(changePct).toFixed(2)}%)`,
    volume: fmtVolume(candle.volume),
  };
}

function renderLegendHtml(el, model) {
  const ohlc = model.ohlc.map(([k, v]) => `<span>${k}<b>${v}</b></span>`).join('');
  el.style.setProperty('--legend-color', model.color);
  el.innerHTML = `
    <div class="legend-row"><span class="legend-title"></span>${ohlc}<b>${model.change}</b></div>
    <div class="legend-row"><span>Vol</span><b>${model.volume}</b></div>`;
  // 名稱用 textContent，避免任何 HTML 字元被解讀。
  $('.legend-title', el).textContent = model.title;
}

function drawLegendCanvas(ctx, model, s) {
  const size = TV.legendFontSize * s;
  const lineH = 22 * s;
  const x0 = 12 * s;
  let y = 8 * s + size;
  ctx.textBaseline = 'alphabetic';

  const segment = (text, color, gapAfter, weight = 400) => {
    ctx.font = `${weight} ${size}px ${TV.font}`;
    ctx.fillStyle = color;
    ctx.fillText(text, x, y);
    x += ctx.measureText(text).width + gapAfter;
  };

  let x = x0;
  segment(model.title, TV.text, 10 * s, 500);
  for (const [k, v] of model.ohlc) {
    segment(k, TV.text, 2 * s);
    segment(v, model.color, 8 * s);
  }
  segment(model.change, model.color, 0);

  y += lineH;
  x = x0;
  segment('Vol', TV.text, 6 * s);
  segment(model.volume, model.color, 0);
}

// ---- 圖表 ----------------------------------------------------------------

function createChart(el, data) {
  const chart = LightweightCharts.createChart(el, {
    width: el.clientWidth,
    height: el.clientHeight,
    layout: {
      background: { type: 'solid', color: '#ffffff' },
      textColor: TV.text,
      fontSize: TV.fontSize,
      fontFamily: TV.font,
      attributionLogo: true,
    },
    grid: { vertLines: { color: TV.grid }, horzLines: { color: TV.grid } },
    rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.1, bottom: 0.08 } },
    timeScale: { borderVisible: false, rightOffset: 10, fixLeftEdge: true, minBarSpacing: 0.5 },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  });

  const minMove = 1 / 10 ** data.decimals;
  const levelPrices = data.levels.map((l) => l.price);

  const volume = chart.addHistogramSeries({
    priceScaleId: '',
    priceFormat: { type: 'volume' },
    priceLineVisible: false,
    lastValueVisible: false,
  });
  volume.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

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

  const priceLines = data.levels.map((level) =>
    candles.createPriceLine({
      price: level.price,
      color: LEVEL_STYLE[level.name].color,
      lineStyle: LEVEL_STYLE[level.name].lineStyle,
      lineWidth: LINE_WIDTH,
      axisLabelVisible: true,
      title: `${level.name} ${fmtPct(level.pct)}｜${fmtPrice(level.price, data.decimals)}`,
    }),
  );

  return { chart, candles, volume, priceLines };
}

// 只載入區間內的K棒並固定左邊界：Lightweight Charts 只有在左邊界固定時，
// 才會把貼邊的時間標籤往內推，否則最左邊的月份會被切掉一半。
function applyRange(card, range) {
  const { data } = card;
  const start = rangeStart(data.candles.at(-1).time, range);
  const shown = data.candles.filter((c) => c.time >= start);
  card.shown = shown;
  card.candles.setData(shown);
  card.volume.setData(
    shown.map((c) => ({ time: c.time, value: c.volume, color: c.close >= c.open ? TV.volUp : TV.volDown })),
  );
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
async function logoImage(card) {
  const svg = $('#tv-attr-logo svg', card.el);
  if (!svg) return null;
  const markup = svg.outerHTML.replaceAll('var(--fill)', TV.text).replaceAll('var(--stroke)', '#fff');
  return loadImage(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(markup)}`);
}

async function renderExportCanvas(card) {
  const { chart, priceLines, data, el } = card;
  const s = EXPORT_SCALE;
  const W = EXPORT.width;
  const H = EXPORT.height;
  // 暫時把圖表放大到匯出尺寸、字級與線寬乘上 s，截圖後還原。
  // 匯出一律顯示所選區間的完整K棒（fitContent），左邊界的時間標籤才會正確內縮。
  chart.applyOptions({ layout: { fontSize: TV.fontSize * s } });
  priceLines.forEach((line) => line.applyOptions({ lineWidth: Math.round(LINE_WIDTH * s) }));
  chart.resize(W, H, true);
  chart.timeScale().fitContent();

  const shot = chart.takeScreenshot();
  const root = el.firstElementChild.getBoundingClientRect();
  const logoEl = $('#tv-attr-logo', el);
  const logoRect = logoEl ? logoEl.getBoundingClientRect() : null;

  chart.applyOptions({ layout: { fontSize: TV.fontSize } });
  priceLines.forEach((line) => line.applyOptions({ lineWidth: LINE_WIDTH }));
  chart.resize(el.clientWidth, el.clientHeight, true);
  chart.timeScale().fitContent();

  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(shot, 0, 0, W, H);

  drawLegendCanvas(ctx, legendModel(data, card.shown.at(-1)), s);

  const logo = await logoImage(card);
  if (logo && logoRect) {
    const w = logoRect.width * s;
    const h = logoRect.height * s;
    ctx.drawImage(logo, logoRect.left - root.left, logoRect.bottom - root.top - h, w, h);
  }
  return canvas;
}

function canvasToBlob(canvas) {
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('PNG 產生失敗'))), 'image/png'),
  );
}

function fileName(data) {
  return `${displayTicker(data)}_FCN_${data.ref_date}.png`;
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
  const card = { root, el: $('.chart', root), legend: $('.legend', root), symbol };
  setStatus(card, '讀取中…');
  return card;
}

function fillCard(card, data) {
  card.data = data;
  card.root.classList.remove('loading');
  $('.ticker', card.root).textContent = displayTicker(data);
  $('.ref', card.root).textContent =
    `期初價 ${fmtPrice(data.ref_close, data.decimals)} ${data.currency}（${data.ref_date} 收盤）`;

  Object.assign(card, createChart(card.el, data));
  applyRange(card, DEFAULT_RANGE);

  const showLegend = (candle) => renderLegendHtml(card.legend, legendModel(data, candle));
  showLegend(card.shown.at(-1));
  card.chart.subscribeCrosshairMove((param) => {
    const bar = param.time && card.shown.find((c) => c.time === param.time);
    showLegend(bar || card.shown.at(-1));
  });

  card.observer = new ResizeObserver(() => {
    card.chart.resize(card.el.clientWidth, card.el.clientHeight);
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
  const symbols = splitSymbols($('#symbols').value);
  if (!symbols.length) return;
  saveLastInput();

  const pcts = { ko: pctValue('ko'), k: pctValue('k'), ki: pctValue('ki') };
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
