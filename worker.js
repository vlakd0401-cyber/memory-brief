// 시세 프록시: /api/quotes 요청만 처리하고 나머지는 정적 파일로 넘깁니다.
// 출처: Yahoo Finance 공개 차트 데이터(비공식). 60초 동안 캐시합니다.
const SYMBOLS = ["005930.KS", "000660.KS", "MU", "GOOGL", "SOXL", "^SOX", "^IXIC", "KRW=X"];
const TTL = 60;

async function fetchQuote(sym) {
  const url = "https://query1.finance.yahoo.com/v8/finance/chart/" + encodeURIComponent(sym) + "?range=1d&interval=5m";
  const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0 (compatible; brief-quotes/1.0)", "Accept": "application/json" } });
  if (!r.ok) throw new Error("HTTP " + r.status);
  const j = await r.json();
  const m = j && j.chart && j.chart.result && j.chart.result[0] && j.chart.result[0].meta;
  if (!m || typeof m.regularMarketPrice !== "number") throw new Error("no data");
  const prev = typeof m.chartPreviousClose === "number" ? m.chartPreviousClose : m.previousClose;
  return { price: m.regularMarketPrice, prev: typeof prev === "number" ? prev : null, time: m.regularMarketTime || null, currency: m.currency || "" };
}

async function quotes(ctx) {
  const cache = caches.default;
  const key = new Request("https://quotes.cache/v1");
  const hit = await cache.match(key);
  if (hit) return hit;
  const out = {};
  await Promise.all(SYMBOLS.map(async s => { try { out[s] = await fetchQuote(s); } catch (e) { out[s] = { error: String(e && e.message || e) }; } }));
  const res = new Response(JSON.stringify({ fetchedAt: Date.now(), quotes: out }), {
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "public, max-age=" + TTL }
  });
  ctx.waitUntil(cache.put(key, res.clone()));
  return res;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/api/quotes") {
      try { return await quotes(ctx); }
      catch (e) { return new Response(JSON.stringify({ error: "unavailable" }), { status: 502, headers: { "content-type": "application/json" } }); }
    }
    return env.ASSETS.fetch(request);
  }
};
