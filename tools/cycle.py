#!/usr/bin/env python3
"""'사이클 점검' 탭의 자동 수치를 갱신합니다.

data/cycle.json 의 "auto" 부분만 다시 쓰고, Claude가 쓰는 "manual" 부분과
과거 기록("history")은 그대로 둡니다. API 키는 필요 없습니다.

  python3 tools/cycle.py          # 갱신 후 저장
  python3 tools/cycle.py --dry    # 저장하지 않고 결과만 출력

수집 항목
- 주가 위치: 최근 2년 고점 대비 낙폭, 과거 하락 사이클(2018~19, 2021~23) 최대 낙폭·기간 (Yahoo Finance)
- 밸류에이션: PER, 추정PER, PBR, 연말 PBR, 배당수익률 (네이버 증권, 마이크론은 Yahoo Finance)
- 마이크론 공매도: 유통주식 대비 공매도 비율, 잔고 주식 수, 커버 일수 (Yahoo Finance, 월 2회 집계)
- 컨센서스: 네이버(FnGuide) 평균 목표가·추정 EPS. 매일 한 번 history 에 쌓아 방향을 봅니다
- 수급: 최근 5거래일 외국인·기관·개인 순매수(주), 외국인 보유율 (네이버 증권)
- 현물가: DDR5 16Gb, DDR4 16Gb, DDR4 8Gb, NAND 512Gb TLC (DRAMeXchange 세션 평균)
- 대만 월매출: 난야·윈본드·매크로닉스 (대만증권거래소 공개 데이터)
"""
import json, re, sys, html, datetime as dt, urllib.request, urllib.parse, http.cookiejar
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "data" / "cycle.json"
UA = {"User-Agent": "Mozilla/5.0"}
KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime.now(KST)

STOCKS = [  # (Yahoo 심볼, 네이버 코드, 표시 이름, 통화)
    ("005930.KS", "005930", "삼성전자", "원"),
    ("000660.KS", "000660", "SK하이닉스", "원"),
    ("MU", None, "마이크론", "$"),
]
PAST = [("2018~19년", "2017-06-01", "2019-12-31"), ("2021~23년", "2020-06-01", "2023-12-31")]
SPOT = [("DDR5 16Gb (2Gx8) 4800/5600", "DDR5 16Gb"), ("DDR4 16Gb (2Gx8) 3200", "DDR4 16Gb"),
        ("DDR4 8Gb (1Gx8) 3200", "DDR4 8Gb"), ("512Gb TLC", "NAND 512Gb TLC")]
TW = [("2408", "난야(南亞科)"), ("2344", "윈본드(華邦電)"), ("2337", "매크로닉스(旺宏)")]


def get(url, timeout=25, tries=3):
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # 네트워크 일시 오류는 재시도
            last = e
    raise last


def jget(url):
    return json.loads(get(url).decode("utf-8"))


def num(s):
    if s is None:
        return None
    s = str(s).replace(",", "").replace("배", "").replace("%", "").replace("원", "").replace("+", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def yahoo(sym, rng, interval):
    q = urllib.parse.quote(sym)
    r = jget(f"https://query1.finance.yahoo.com/v8/finance/chart/{q}?range={rng}&interval={interval}")["chart"]["result"][0]
    out = []
    for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]):
        if c:
            out.append((dt.datetime.fromtimestamp(t, KST).date(), float(c)))
    return out, r["meta"]


def max_drawdown(series):
    """구간 안에서 고점→이후 저점의 최대 낙폭."""
    best = (0, None, None, None, None)
    peak_v, peak_d = None, None
    for d, v in series:
        if peak_v is None or v > peak_v:
            peak_v, peak_d = v, d
        dd = v / peak_v - 1
        if dd < best[0]:
            best = (dd, peak_d, peak_v, d, v)
    return best


def position():
    rows = []
    for sym, _, name, cur in STOCKS:
        try:
            daily, meta = yahoo(sym, "2y", "1d")
            weekly, _ = yahoo(sym, "10y", "1wk")
        except Exception as e:
            print("position 실패", sym, e, file=sys.stderr)
            continue
        price = float(meta.get("regularMarketPrice") or daily[-1][1])
        pd_, pv = max(daily, key=lambda x: x[1])
        row = {"name": name, "sym": sym, "unit": cur, "price": round(price, 2), "peak": round(pv, 2),
               "peakDate": pd_.isoformat(), "drawdown": round((price / pv - 1) * 100, 1),
               "daysFromPeak": (NOW.date() - pd_).days, "past": []}
        for label, a, b in PAST:
            seg = [(d, v) for d, v in weekly if a <= d.isoformat() <= b]
            if not seg:
                continue
            dd, p_d, p_v, t_d, t_v = max_drawdown(seg)
            row["past"].append({"label": label, "drawdown": round(dd * 100, 1), "peakDate": p_d.isoformat(),
                                "troughDate": t_d.isoformat(), "months": round((t_d - p_d).days / 30.4)})
        rows.append(row)
    return rows


def us_stats(sym="MU"):
    """마이크론 PER·PBR·공매도 비율 (Yahoo Finance, 쿠키+crumb 필요)."""
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", "Mozilla/5.0")]
    try:
        op.open("https://fc.yahoo.com", timeout=20)
    except Exception:
        pass  # 404여도 쿠키는 받음
    crumb = op.open("https://query2.finance.yahoo.com/v1/test/getcrumb", timeout=20).read().decode().strip()
    url = (f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}?modules=defaultKeyStatistics,summaryDetail"
           f"&crumb={urllib.parse.quote(crumb)}")
    r = json.loads(op.open(url, timeout=20).read().decode())["quoteSummary"]["result"][0]
    k, s = r["defaultKeyStatistics"], r["summaryDetail"]
    g = lambda d, x: (d.get(x) or {}).get("raw")
    sd = g(k, "dateShortInterest")
    val = {"per": round(g(s, "trailingPE"), 2) if g(s, "trailingPE") else None,
           "fper": round((g(s, "forwardPE") or g(k, "forwardPE")), 2) if (g(s, "forwardPE") or g(k, "forwardPE")) else None,
           "pbr": round(g(k, "priceToBook"), 2) if g(k, "priceToBook") else None, "bps": g(k, "bookValue"),
           "divYield": round(g(s, "dividendYield") * 100, 2) if g(s, "dividendYield") is not None else None, "annual": []}
    short = {"pctFloat": round(g(k, "shortPercentOfFloat") * 100, 2) if g(k, "shortPercentOfFloat") is not None else None,
             "shares": g(k, "sharesShort"), "prior": g(k, "sharesShortPriorMonth"), "daysToCover": g(k, "shortRatio"),
             "date": dt.datetime.fromtimestamp(sd, KST).strftime("%Y-%m-%d") if sd else ""}
    return val, short


def naver(code):
    d = jget(f"https://m.stock.naver.com/api/stock/{code}/integration")
    info = {t.get("code"): t.get("value") for t in d.get("totalInfos", [])}
    try:
        a = jget(f"https://m.stock.naver.com/api/stock/{code}/finance/annual")["financeInfo"]
        pbr_row = next((r for r in a["rowList"] if r["title"] == "PBR"), None)
        bps_row = next((r for r in a["rowList"] if r["title"] == "BPS"), None)
        est = {t["key"]: t.get("isConsensus") == "Y" for t in a.get("trTitleList", [])}
        annual = []
        for k in sorted((pbr_row or {}).get("columns", {})):
            annual.append({"year": k[:4], "pbr": num(pbr_row["columns"][k]["value"]),
                           "bps": num(bps_row["columns"][k]["value"]) if bps_row else None, "estimate": est.get(k, False)})
    except Exception as e:
        print("annual 실패", code, e, file=sys.stderr)
        annual = []
    flows = []
    for r in d.get("dealTrendInfos", [])[:5]:
        flows.append({"date": f"{r['bizdate'][4:6]}/{r['bizdate'][6:]}", "foreign": num(r.get("foreignerPureBuyQuant")),
                      "organ": num(r.get("organPureBuyQuant")), "individual": num(r.get("individualPureBuyQuant")),
                      "foreignHold": num(r.get("foreignerHoldRatio"))})
    c = d.get("consensusInfo") or {}
    return {
        "val": {"per": num(info.get("per")), "fper": num(info.get("cnsPer")), "pbr": num(info.get("pbr")),
                "bps": num(info.get("bps")), "eps": num(info.get("eps")), "feps": num(info.get("cnsEps")),
                "divYield": num(info.get("dividendYieldRatio")), "foreignRate": num(info.get("foreignRate")),
                "high52": num(info.get("highPriceOf52Weeks")), "low52": num(info.get("lowPriceOf52Weeks")),
                "annual": annual},
        "flows": flows,
        "cons": {"target": num(c.get("priceTargetMean")), "recomm": num(c.get("recommMean")), "date": c.get("createDate")},
    }


def spot():
    t = get("https://www.dramexchange.com/").decode("utf-8", "ignore")
    b = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
    b = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", b)))
    out = []
    for key, label in SPOT:
        m = re.search(re.escape(key) + r" ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) (-?[\d.]+) ?%", b)
        if m:
            out.append({"label": label, "avg": float(m.group(5)), "chg": float(m.group(6))})
    ups = re.findall(r"Last Update:\s*([A-Za-z]{3})\.(\d{1,2}) (\d{4}) (\d{2}:\d{2})", b)
    asof = ""
    if ups:
        mon, day, yr, hm = ups[0]
        m = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].index(mon) + 1
        asof = f"{int(m):02d}/{int(day):02d} {hm} (대만시간)"
    return {"items": out, "asOf": asof}


def taiwan():
    d = jget("https://openapi.twse.com.tw/v1/opendata/t187ap05_L")
    out = []
    for code, name in TW:
        r = next((x for x in d if x.get("公司代號") == code), None)
        if not r:
            continue
        ym = r["資料年月"]  # 민국 연도, 예: 11510 → 2026-10
        year, mon = int(ym[:-2]) + 1911, int(ym[-2:])
        out.append({"name": name, "month": f"{year}-{mon:02d}", "revenue": round(num(r["營業收入-當月營收"]) / 1e5, 1),
                    "mom": round(num(r["營業收入-上月比較增減(%)"]), 1), "yoy": round(num(r["營業收入-去年同月增減(%)"]), 1)})
    return out  # revenue 단위: 억 대만달러


def main():
    data = json.loads(PATH.read_text()) if PATH.exists() else {}
    auto = data.get("auto", {})
    hist = data.setdefault("history", {})

    def step(key, fn):
        try:
            auto[key] = fn()
        except Exception as e:
            print(key, "실패(직전 값 유지):", e, file=sys.stderr)

    step("position", position)
    kr = {}
    for _, code, name, _ in STOCKS:
        if code:
            try:
                kr[name] = naver(code)
            except Exception as e:
                print("naver 실패", name, e, file=sys.stderr)
    if kr:
        auto["valuation"] = {k: v["val"] for k, v in kr.items()}
        auto["flows"] = {k: v["flows"] for k, v in kr.items()}
        auto["consensus"] = {k: v["cons"] for k, v in kr.items()}
    try:
        mv, ms = us_stats("MU")
        auto.setdefault("valuation", {})["마이크론"] = mv
        auto["usShort"] = {"마이크론": ms}
    except Exception as e:
        print("마이크론 지표 실패(직전 값 유지):", e, file=sys.stderr)
    step("spot", spot)
    step("taiwan", taiwan)
    auto["updated"] = NOW.strftime("%Y-%m-%d %H:%M")

    # 하루 한 번 기록(같은 날이면 덮어씀): 컨센서스·추정EPS·PBR·현물가 방향을 보기 위함
    today = NOW.strftime("%Y-%m-%d")
    for name, v in kr.items():
        h = hist.setdefault(name, [])
        rec = {"date": today, "target": v["cons"]["target"], "feps": v["val"]["feps"], "pbr": v["val"]["pbr"],
               "foreignRate": v["val"]["foreignRate"]}
        if h and h[-1]["date"] == today:
            h[-1] = rec
        else:
            h.append(rec)
        hist[name] = h[-120:]
    if auto.get("spot", {}).get("items"):
        h = hist.setdefault("spot", [])
        rec = {"date": today, **{i["label"]: i["avg"] for i in auto["spot"]["items"]}}
        if h and h[-1]["date"] == today:
            h[-1] = rec
        else:
            h.append(rec)
        hist["spot"] = h[-120:]

    data["auto"] = auto
    out = json.dumps(data, ensure_ascii=False, indent=1)
    if "--dry" in sys.argv:
        print(out)
    else:
        PATH.write_text(out + "\n")
        print("저장:", PATH)


if __name__ == "__main__":
    main()
