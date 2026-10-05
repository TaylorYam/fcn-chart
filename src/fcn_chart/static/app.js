'use strict';

// ---- 設定 ----------------------------------------------------------------

const LEVEL_STYLE = {
  KO: { color: '#16a34a', lineStyle: LightweightCharts.LineStyle.Solid },
  K: { color: '#2563eb', lineStyle: LightweightCharts.LineStyle.Solid },
  KI: { color: '#dc2626', lineStyle: LightweightCharts.LineStyle.Dashed },
};
const DEFAULT_BARS = 252; // 1Y
const SOURCE_NOTE = '資料來源：Yahoo Finance｜Chart: TradingView Lightweight Charts';
const FONT = '"Segoe UI", "Microsoft JhengHei", "Noto Sans TC", sans-serif';

// 匯出圖：16:9，上方標題、下方註腳，中間是圖表。
const EXPORT = { width: 1600, height: 900, header: 84, footer: 48, padX: 24, chartFontSize: 16 };

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

function fmtPrice(value, decimals) {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function fmtPct(pct) {
  return `${Number(pct.toFixed(4))}%`;
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

// ---- 圖表 ----------------------------------------------------------------

function createChart(el, data) {
  const chart = LightweightCharts.createChart(el, {
    width: el.clientWidth,
    height: el.clientHeight,
    layout: {
      background: { color: '#ffffff' },
      textColor: '#374151',
      fontSize: 12,
      fontFamily: FONT,
      attributionLogo: false, // 改以註腳標示（Apache 2.0 attribution）
    },
    grid: { vertLines: { color: '#eef1f4' }, horzLines: { color: '#eef1f4' } },
    rightPriceScale: { borderColor: '#d1d5db', scaleMargins: { top: 0.08, bottom: 0.08 } },
    timeScale: { borderColor: '#d1d5db', rightOffset: 4, minBarSpacing: 1 },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    localization: { priceFormatter: (p) => fmtPrice(p, data.decimals) },
  });

  const levelPrices = data.levels.map((l) => l.price);
  const candles = chart.addCandlestickSeries({
    upColor: '#26a69a',
    downColor: '#ef5350',
    borderUpColor: '#26a69a',
    borderDownColor: '#ef5350',
    wickUpColor: '#26a69a',
    wickDownColor: '#ef5350',
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
  candles.setData(data.candles);

  const priceLines = data.levels.map((level) =>
    candles.createPriceLine({
      price: level.price,
      color: LEVEL_STYLE[level.name].color,
      lineStyle: LEVEL_STYLE[level.name].lineStyle,
      lineWidth: 2,
      axisLabelVisible: true,
      title: `${level.name} ${fmtPct(level.pct)}｜${fmtPrice(level.price, data.decimals)}`,
    }),
  );

  return { chart, priceLines };
}

function setRange(chart, bars, total) {
  chart.timeScale().setVisibleLogicalRange({ from: Math.max(total - bars, 0) - 0.5, to: total + 3 });
}

// ---- 匯出 ----------------------------------------------------------------

function renderExportCanvas(card) {
  const { chart, priceLines, data, el } = card;
  const W = EXPORT.width;
  const H = EXPORT.height;
  const chartH = H - EXPORT.header - EXPORT.footer;
  const chartW = W - EXPORT.padX * 2;

  // 暫時把圖表放大成匯出尺寸、字放大，截圖後還原。
  const range = chart.timeScale().getVisibleLogicalRange();
  chart.applyOptions({ layout: { fontSize: EXPORT.chartFontSize } });
  priceLines.forEach((line) => line.applyOptions({ lineWidth: 3 }));
  chart.resize(chartW, chartH, true);
  if (range) chart.timeScale().setVisibleLogicalRange(range);
  const shot = chart.takeScreenshot();
  chart.applyOptions({ layout: { fontSize: 12 } });
  priceLines.forEach((line) => line.applyOptions({ lineWidth: 2 }));
  chart.resize(el.clientWidth, el.clientHeight, true);
  if (range) chart.timeScale().setVisibleLogicalRange(range);

  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, W, H);

  // 標題列
  const titleY = 54;
  ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = '#111827';
  ctx.font = `700 34px ${FONT}`;
  const ticker = displayTicker(data);
  ctx.fillText(ticker, EXPORT.padX, titleY);
  const tickerW = ctx.measureText(ticker).width;

  ctx.font = `600 22px ${FONT}`;
  const ref = `期初價 ${fmtPrice(data.ref_close, data.decimals)} ${data.currency}（${data.ref_date} 收盤）`;
  const refW = ctx.measureText(ref).width;
  ctx.textAlign = 'right';
  ctx.fillText(ref, W - EXPORT.padX, titleY);
  ctx.textAlign = 'left';

  ctx.fillStyle = '#6b7280';
  ctx.font = `400 22px ${FONT}`;
  const nameX = EXPORT.padX + tickerW + 14;
  const nameMax = W - EXPORT.padX - refW - 24 - nameX;
  if (data.name && data.name !== data.symbol && nameMax > 40) {
    ctx.fillText(truncate(ctx, data.name, nameMax), nameX, titleY);
  }

  // 圖表
  ctx.drawImage(shot, EXPORT.padX, EXPORT.header, chartW, chartH);

  // 註腳
  ctx.fillStyle = '#6b7280';
  ctx.font = `400 16px ${FONT}`;
  const footY = H - 18;
  ctx.fillText(SOURCE_NOTE, EXPORT.padX, footY);
  ctx.textAlign = 'right';
  const legend = data.levels.map((l) => `${l.name} ${fmtPct(l.pct)}`).join(' / ');
  ctx.fillText(legend, W - EXPORT.padX, footY);
  ctx.textAlign = 'left';

  return canvas;
}

function truncate(ctx, text, maxWidth) {
  if (ctx.measureText(text).width <= maxWidth) return text;
  let s = text;
  while (s.length > 1 && ctx.measureText(`${s}…`).width > maxWidth) s = s.slice(0, -1);
  return `${s}…`;
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
  $('.source', root).textContent = SOURCE_NOTE;
  root.classList.add('loading');
  $('#cards').append(root);
  const card = { root, el: $('.chart', root), symbol };
  setStatus(card, '讀取中…');
  return card;
}

function fillCard(card, data) {
  card.data = data;
  card.root.classList.remove('loading');
  $('.ticker', card.root).textContent = displayTicker(data);
  $('.name', card.root).textContent = data.name !== data.symbol ? data.name : '';
  $('.ref', card.root).textContent =
    `期初價 ${fmtPrice(data.ref_close, data.decimals)} ${data.currency}（${data.ref_date} 收盤）`;

  Object.assign(card, createChart(card.el, data));
  card.bars = DEFAULT_BARS;
  setRange(card.chart, card.bars, data.candles.length);

  // 改變寬度時 Lightweight Charts 會保留 barSpacing 而不是保留區間，所以要重設區間。
  card.observer = new ResizeObserver(() => {
    card.chart.resize(card.el.clientWidth, card.el.clientHeight);
    setRange(card.chart, card.bars, data.candles.length);
  });
  card.observer.observe(card.el);

  for (const btn of card.root.querySelectorAll('.ranges button')) {
    btn.addEventListener('click', () => {
      card.root.querySelectorAll('.ranges button').forEach((b) => b.classList.toggle('active', b === btn));
      card.bars = Number(btn.dataset.bars);
      setRange(card.chart, card.bars, data.candles.length);
    });
  }

  $('.download', card.root).addEventListener('click', async () => {
    downloadBlob(await canvasToBlob(renderExportCanvas(card)), fileName(data));
  });

  $('.copy', card.root).addEventListener('click', async () => {
    try {
      const blob = await canvasToBlob(renderExportCanvas(card));
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
    zip.file(fileName(card.data), await canvasToBlob(renderExportCanvas(card)));
  }
  const today = new Date().toISOString().slice(0, 10);
  downloadBlob(await zip.generateAsync({ type: 'blob' }), `FCN_charts_${today}.zip`);
});

loadLastInput();
