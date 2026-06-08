"""
批量筛选脚本 — HardGate + 公司分类 + L2 初筛 + Phase 4 财务保质
===============================================================
默认完整流程:
  Phase 1-3: stock_basic + daily_basic 快筛（~10s）→ 候选池
  Phase 4:   fina_indicator逐只拉取（仅对候选池，~3-6分钟）
             重打分后含 ROE/毛利率/负债率/经营CF，满分 20

用法:
    python scripts/run_screener.py                          # 完整流程（含Phase 4）
    python scripts/run_screener.py --fast                   # 快版（跳过Phase 4）
    python scripts/run_screener.py --fast --output out.csv  # 快版 + 自定义输出
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# 加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.core.data.tushare_client import TushareClient
from src.turtle.rules.loader import load_rules


# ══════════════════════════════════════════════════════════════
# 1. 数据拉取
# ══════════════════════════════════════════════════════════════

def fetch_all_stock_basic(client: TushareClient) -> pd.DataFrame:
    print("[1/3] 拉取 stock_basic ...", flush=True)
    df = client.stock_basic(list_status="L")
    mask = df["ts_code"].str.endswith(".SH", na=False) | df["ts_code"].str.endswith(".SZ", na=False)
    df = df[mask].copy()
    print(f"  → 共 {len(df)} 只上市 A 股", flush=True)
    return df


def fetch_latest_daily_basic(client: TushareClient, lookback_days: int = 10) -> pd.DataFrame:
    print("[2/3] 拉取 daily_basic (最新交易日) ...", flush=True)
    today = date.today()
    end_dt = today.strftime("%Y%m%d")
    start_dt = (today - timedelta(days=lookback_days)).strftime("%Y%m%d")

    try:
        df = client.daily_basic(start_date=start_dt, end_date=end_dt)
        if df is not None and not df.empty:
            df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
            df = df.sort_values("trade_date", ascending=False)
            df = df.drop_duplicates(subset=["ts_code"], keep="first")
            print(f"  → {len(df)} 只有效 daily_basic", flush=True)
            return df
    except Exception as e:
        print(f"  [WARN] daily_basic 失败: {e}", flush=True)
    return pd.DataFrame()


# ══════════════════════════════════════════════════════════════
# 2. HardGate
# ══════════════════════════════════════════════════════════════

def check_hard_gate_simple(row: pd.Series) -> tuple[bool, str]:
    name = str(row.get("name", ""))
    for pat in ["ST", "*ST"]:
        if pat in name:
            return False, f"{pat}股票"

    list_date_str = str(row.get("list_date", ""))
    if list_date_str and len(list_date_str) == 8:
        list_dt = date(int(list_date_str[:4]), int(list_date_str[4:6]), int(list_date_str[6:8]))
        years = (date.today() - list_dt).days / 365.25
        if years < 5:
            return False, f"上市仅{round(years,1)}年"
    return True, ""


# ══════════════════════════════════════════════════════════════
# 3. 公司分类
# ══════════════════════════════════════════════════════════════

FINANCIAL_KW = {"银行", "保险", "证券", "多元金融", "信托"}
CYCLICAL_KW = {"钢铁", "有色", "化工", "建材", "采掘", "煤炭", "石油", "航运", "海运", "航空", "造纸"}


def classify_company(row: pd.Series, db_row: pd.Series | None) -> tuple[str, bool, str]:
    ind = str(row.get("industry", ""))
    for kw in FINANCIAL_KW:
        if kw in ind:
            return "FINANCIAL", False, "金融类"
    for kw in CYCLICAL_KW:
        if kw in ind:
            return "CYCLICAL", False, "强周期"
    if db_row is not None:
        dv = db_row.get("dv_ratio")
        if dv is not None:
            try:
                if float(dv) == 0:
                    return "GROWTH_NO_DIVIDEND", False, "成长不分红"
            except (ValueError, TypeError):
                pass
    return "STANDARD_CONSUMER", True, ""


# ══════════════════════════════════════════════════════════════
# 4. L2 打分（支持可选 fina_indicator 财务数据）
# ══════════════════════════════════════════════════════════════

_RULES = None


def _rules():
    global _RULES
    if _RULES is None:
        _RULES = load_rules()
    return _RULES


def _sf(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _apply_ths(value: float, thresholds: list) -> float:
    for t in thresholds:
        mn, mx, sc = t.get("min"), t.get("max"), t.get("score", 0)
        if mn is not None and mx is not None:
            if mn <= value <= mx:
                return sc
        elif mn is not None and mx is None:
            if value >= mn:
                return sc
        elif mn is None and mx is not None:
            if value <= mx:
                return sc
    return 0.0


def _score_financial_quality(fina_data: dict | None) -> tuple[float, dict]:
    """从 fina_indicator 计算财务质量得分 (0-9pt)。

    Returns:
        (fq_score, detail_dict) — detail 包含各维度原始值 + 得分。
    """
    fq_rules = _rules().l2_screener.scoring["financial_quality"]
    detail = {"roe_raw": None, "roe_sc": 0, "gm_raw": None, "gm_sc": 0,
              "dr_raw": None, "dr_sc": 0, "ocf_raw": None, "ocf_sc": 0}

    if fina_data is None:
        return 1.0, detail  # 无数据 → 低保底 1 分

    total = 0.0

    # ROE (权重 3, hard_gate <5% 淘汰)
    roe = _sf(fina_data.get("roe"))
    detail["roe_raw"] = roe
    if roe is not None:
        hg = fq_rules["roe"].get("hard_gate")
        if hg is not None and roe < hg:
            return -1.0, detail  # 负数表示硬淘汰
        sc = _apply_ths(roe, fq_rules["roe"]["thresholds"])
        detail["roe_sc"] = sc
        total += sc

    # 毛利率 (权重 2)
    gm = _sf(fina_data.get("grossprofit_margin"))
    detail["gm_raw"] = gm
    if gm is not None:
        sc = _apply_ths(gm, fq_rules["gross_margin"]["thresholds"])
        detail["gm_sc"] = sc
        total += sc

    # 负债率 (权重 2)
    dr = _sf(fina_data.get("debt_to_assets"))
    detail["dr_raw"] = dr
    if dr is not None:
        sc = _apply_ths(dr, fq_rules["debt_ratio"]["thresholds"])
        detail["dr_sc"] = sc
        total += sc

    # 经营CF/净利润 (权重 2) — 用 cf_sales 近似
    cf_sales = _sf(fina_data.get("cf_sales"))
    detail["ocf_raw"] = cf_sales
    if cf_sales is not None and cf_sales > 0:
        sc = 1.0  # 有正经营现金流就给 1 分
        detail["ocf_sc"] = sc
        total += sc

    return round(total, 2), detail


def score_l2(db_row: pd.Series | None, basic_row: pd.Series,
             fina_data: dict | None = None, full_mode: bool = False) -> dict:
    """L2 打分。

    fast mode (full_mode=False): 满分 ~11，FQ=1.0 占位，阈值按 11/20 缩放。
    full mode (full_mode=True):  满分 20，FQ 从 fina_data 计算，阈值直接用 12/8。
    """
    s = _rules().l2_screener.scoring
    r = {"fq": 0.0, "val": 0.0, "liq": 0.0, "bon": 0.0, "total": 0.0,
         "pool": "", "elim": False, "reason": "",
         "fq_detail": {}}

    # ── 财务质量 ──
    if full_mode and fina_data is not None:
        fq_score, fq_detail = _score_financial_quality(fina_data)
        if fq_score < 0:  # ROE hard gate
            r["elim"] = True
            r["reason"] = f"ROE={fq_detail['roe_raw']}%<5%"
            r["fq"] = 0.0
            r["fq_detail"] = fq_detail
            return r
        r["fq"] = fq_score
        r["fq_detail"] = fq_detail
    else:
        r["fq"] = 1.0  # 低保底
        r["fq_detail"] = {}

    # ── 估值 (6pt) ──
    val = s["valuation"]
    if db_row is not None:
        pe = _sf(db_row.get("pe"))
        if pe is not None:
            if pe < val["pe"].get("hard_gate", 0):
                r["elim"] = True
                r["reason"] = f"PE={pe:.1f}<0"
                return r
            r["val"] += _apply_ths(pe, val["pe"]["thresholds"])
        pb = _sf(db_row.get("pb"))
        if pb is not None:
            r["val"] += _apply_ths(pb, val["pb"]["thresholds"])
        ps = _sf(db_row.get("ps"))
        if ps is not None:
            r["val"] += _apply_ths(ps, val["ps"]["thresholds"])

    # ── 流动性 (3pt) ──
    liq = s["liquidity"]
    if db_row is not None:
        dy = _sf(db_row.get("dv_ratio"))
        if dy is not None:
            if dy <= liq["dividend_yield"].get("hard_gate", 0.01):
                r["elim"] = True
                r["reason"] = f"股息率={dy:.2f}%≤0"
                return r
            r["liq"] += _apply_ths(dy, liq["dividend_yield"]["thresholds"])
        to = _sf(db_row.get("turnover_rate"))
        if to is not None:
            r["liq"] += _apply_ths(to, liq["avg_turnover"]["thresholds"])

    # ── 加分 (2pt) ──
    bon = s["bonus"]
    if "hsgt" in bon:
        if str(basic_row.get("is_hs", "")).upper() in ("H", "1"):
            r["bon"] += bon["hsgt"]["weight"]
    if "listing_over_10y" in bon:
        ld = str(basic_row.get("list_date", ""))
        if len(ld) == 8:
            dt = date(int(ld[:4]), int(ld[4:6]), int(ld[6:8]))
            if (date.today() - dt).days / 365.25 > 10:
                r["bon"] += bon["listing_over_10y"]["weight"]

    r["total"] = round(r["fq"] + r["val"] + r["liq"] + r["bon"], 2)

    # ── 股票池阈值 ──
    pt = _rules().l2_screener.pool_thresholds

    if full_mode:
        adj_candidate, adj_watch = pt.candidate, pt.watch
    else:
        max_possible = 11.0
        adj_candidate = pt.candidate * (max_possible / 20.0)
        adj_watch = pt.watch * (max_possible / 20.0)

    if r["total"] >= adj_candidate:
        r["pool"] = "候选池"
    elif r["total"] >= adj_watch:
        r["pool"] = "观察池"
    else:
        r["pool"] = "淘汰"
        r["elim"] = True
        r["reason"] = f"L2={r['total']}<{round(adj_watch,1)}"
    return r


# ══════════════════════════════════════════════════════════════
# 5. Phase 4: fina_indicator 批量拉取（仅对候选池）
# ══════════════════════════════════════════════════════════════

def _get_fina_periods() -> list[str]:
    """返回可能的最新年报期列表（从最新到最旧）。"""
    today = date.today()
    # 年报通常在次年4月底前出完；当前年份的年报最新、上一年最具确定性
    periods = []
    for offset in range(0, 3):  # 当前年、上年、前年
        y = today.year - offset
        periods.append(f"{y}1231")
    return periods


def fetch_fina_for_candidates(
    client: TushareClient, ts_codes: list[str], batch_size: int = 100
) -> dict[str, dict]:
    """Phase 4: 为候选池股票逐只拉取 fina_indicator 最新年报数据。

    返回 {ts_code: {roe, grossprofit_margin, debt_to_assets, cf_sales, period}}。
    """
    if not ts_codes:
        return {}

    print(f"\n{'='*60}")
    print(f"  Phase 4: 拉取 fina_indicator 财务指标")
    print(f"  候选池: {len(ts_codes)} 只，预计 {len(ts_codes)*0.3/60:.0f}~{len(ts_codes)*0.5/60:.0f} 分钟")
    print(f"{'='*60}")

    periods = _get_fina_periods()
    result: dict[str, dict] = {}
    t_start = time.time()
    success, empty = 0, 0

    for i, code in enumerate(ts_codes):
        fina_row = None
        for period in periods:
            try:
                df = client.fina_indicator(ts_code=code, period=period)
                if not df.empty:
                    # 取该期第一条（通常只有一条）
                    fina_row = df.iloc[0].to_dict()
                    fina_row["_period"] = period
                    break
            except Exception:
                continue

        if fina_row is not None:
            result[code] = {
                "roe": _sf(fina_row.get("roe")),
                "grossprofit_margin": _sf(fina_row.get("grossprofit_margin")),
                "debt_to_assets": _sf(fina_row.get("debt_to_assets")),
                "cf_sales": _sf(fina_row.get("cf_sales")),
                "period": fina_row.get("_period", ""),
            }
            success += 1
        else:
            empty += 1  # 无数据或全部失败

        # 进度报告
        if (i + 1) % batch_size == 0 or i + 1 == len(ts_codes):
            elapsed = time.time() - t_start
            pct = (i + 1) / len(ts_codes) * 100
            eta = elapsed / (i + 1) * (len(ts_codes) - i - 1) if i + 1 < len(ts_codes) else 0
            print(f"  进度: {i+1}/{len(ts_codes)} ({pct:.0f}%)  "
                  f"成功={success} 无数据={empty}  "
                  f"耗时={elapsed:.0f}s  ETA={eta:.0f}s", flush=True)

    t_total = time.time() - t_start
    print(f"  → 完成! {success}/{len(ts_codes)} 只有效数据, 总耗时 {t_total:.1f}s",
          flush=True)
    return result


# ══════════════════════════════════════════════════════════════
# 6. 主流程
# ══════════════════════════════════════════════════════════════

def run_screener(output_path: str = "output/screener_result.csv",
                 fast_mode: bool = False):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    t0 = time.time()

    client = TushareClient()
    basic = fetch_all_stock_basic(client)
    db = fetch_latest_daily_basic(client)

    if basic.empty:
        print("[ERROR] 无股票数据")
        return

    db_ix = {}
    if not db.empty:
        for _, row in db.iterrows():
            db_ix[str(row["ts_code"])] = row

    t1 = time.time()
    print(f"  数据拉取耗时: {round(t1-t0,1)}s", flush=True)

    # ── Phase 1-3: 快筛 ──
    print(f"[3/4] 快筛 ({len(basic)} 只) ...", flush=True)

    rows = []
    st = {"n": len(basic), "hg_p": 0, "hg_f": 0, "cl_p": 0,
          "cand": 0, "watch": 0, "elim": 0,
          "h_roe": 0, "h_pe": 0, "h_div": 0}
    cc = {}
    candidate_codes: list[str] = []

    for i, (_, r) in enumerate(basic.iterrows()):
        ts = str(r["ts_code"])
        nm = str(r.get("name", ""))
        if (i + 1) % 1000 == 0:
            print(f"  进度: {i+1}/{len(basic)} ...", flush=True)

        dr = db_ix.get(ts)
        rec = {
            "ts_code": ts, "name": nm,
            "industry": str(r.get("industry", "")),
            "list_date": str(r.get("list_date", "")),
            "hg": "PASS", "class": "", "class_ok": True,
            "l2_tot": 0.0, "l2_pool": "", "l2_fq": 1.0, "l2_val": 0.0,
            "l2_liq": 0.0, "l2_bon": 0.0, "elim_reason": "",
            "pe": _sf(dr.get("pe")) if dr is not None else None,
            "pb": _sf(dr.get("pb")) if dr is not None else None,
            "ps": _sf(dr.get("ps")) if dr is not None else None,
            "dv_ratio": _sf(dr.get("dv_ratio")) if dr is not None else None,
            "total_mv": _sf(dr.get("total_mv")) if dr is not None else None,
            # 财务指标列（Phase 4 后填充）
            "roe": None, "gross_margin": None, "debt_ratio": None, "ocf_sales": None,
            "fina_period": "",
        }

        # HardGate
        ok, reason = check_hard_gate_simple(r)
        if not ok:
            rec["hg"] = f"FAIL:{reason}"
            rec["elim_reason"] = f"HardGate:{reason}"
            st["hg_f"] += 1
            rows.append(rec)
            continue
        st["hg_p"] += 1

        # 分类
        cat, ok, reason = classify_company(r, dr)
        rec["class"] = cat
        rec["class_ok"] = ok
        cc[cat] = cc.get(cat, 0) + 1
        if not ok:
            rec["elim_reason"] = f"分类:{reason}"
            rows.append(rec)
            continue
        st["cl_p"] += 1

        # L2（fast: 无 fina 数据）
        l2 = score_l2(dr, r, full_mode=False)
        rec["l2_tot"] = l2["total"]
        rec["l2_pool"] = l2["pool"]
        rec["l2_val"] = l2["val"]
        rec["l2_liq"] = l2["liq"]
        rec["l2_bon"] = l2["bon"]
        rec["l2_fq"] = l2["fq"]

        if l2["elim"]:
            rec["elim_reason"] = l2["reason"]
            rs = l2["reason"]
            if "ROE" in rs: st["h_roe"] += 1
            elif "PE" in rs: st["h_pe"] += 1
            elif "股息" in rs: st["h_div"] += 1

        if l2["pool"] == "候选池":
            st["cand"] += 1
            candidate_codes.append(ts)
        elif l2["pool"] == "观察池":
            st["watch"] += 1
        else:
            st["elim"] += 1

        rows.append(rec)

    t2 = time.time()
    print(f"  快筛耗时: {round(t2-t1,1)}s", flush=True)

    # ── 打印快筛统计 ──
    print("\n" + "=" * 60)
    mode_label = "fast" if fast_mode else "Phase 1-3 快筛"
    print(f"  Turtle Strategy - A Share Screener ({mode_label})")
    print("=" * 60)
    print(f"  Total A-shares:            {st['n']:>6}")
    print(f"  HardGate passed:           {st['hg_p']:>6}  (rejected {st['hg_f']})")
    print(f"  Classify passed (STANDARD):{st['cl_p']:>6}")
    print()
    if cc:
        mx = max(cc.values())
        for c, n in sorted(cc.items(), key=lambda x: -x[1]):
            bar = "#" * min(30, int(n/mx*30))
            print(f"    {c:<25s} {n:>5}  {bar}")
    print()
    print(f"  * Candidate Pool (>=6.6/11): {st['cand']:>6}")
    print(f"    Watch Pool    (>=4.4/11):  {st['watch']:>6}")
    print(f"    Eliminated:                {st['elim']:>6}")
    print(f"      PE<0:                    {st['h_pe']:>6}")
    print(f"      Dividend<=0:             {st['h_div']:>6}")

    # ── Phase 4: fina_indicator 重打分 ──
    fina_map: dict[str, dict] = {}
    if not fast_mode and candidate_codes:
        fina_map = fetch_fina_for_candidates(client, candidate_codes)

        # 更新候选池记录：填入财务数据 + 重打分
        print(f"\n[4/4] 用 fina 数据重打分候选池 ({len(candidate_codes)} 只) ...", flush=True)
        rec_ix = {rec["ts_code"]: rec for rec in rows}

        new_cand, new_watch, new_elim, roe_elim = 0, 0, 0, 0

        for ts_code in candidate_codes:
            rec = rec_ix[ts_code]
            dr = db_ix.get(ts_code)
            fd = fina_map.get(ts_code)

            if fd:
                rec["roe"] = fd.get("roe")
                rec["gross_margin"] = fd.get("grossprofit_margin")
                rec["debt_ratio"] = fd.get("debt_to_assets")
                rec["ocf_sales"] = fd.get("cf_sales")
                rec["fina_period"] = fd.get("period", "")

            # 用 full_mode 重打分
            basic_row = basic[basic["ts_code"] == ts_code]
            br = basic_row.iloc[0] if not basic_row.empty else pd.Series()
            l2 = score_l2(dr, br, fina_data=fd, full_mode=True)

            rec["l2_fq"] = l2["fq"]
            rec["l2_tot"] = l2["total"]
            rec["l2_pool"] = l2["pool"]
            rec["elim_reason"] = l2["reason"] if l2["elim"] else ""

            if l2["pool"] == "候选池":
                new_cand += 1
            elif l2["pool"] == "观察池":
                new_watch += 1
            else:
                new_elim += 1
                if "ROE" in l2.get("reason", ""):
                    roe_elim += 1

        t3 = time.time()
        print(f"  重打分耗时: {round(t3-t2,1)}s", flush=True)
        print(f"\n  === Phase 4 重打分结果（满分20）===")
        print(f"    候选池 (>=12):  {new_cand:>6}")
        print(f"    观察池 (>=8):   {new_watch:>6}")
        print(f"    淘汰:           {new_elim:>6}  (其中 ROE<5%: {roe_elim})")
        print(f"    总耗时: {round(t3-t0,0)}s")

    # ── 保存 ──
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\n[OK] Saved: {output_path}  ({len(df)}rows)", flush=True)

    # ── 打印最终 Top 30 ──
    cand = df[df["l2_pool"] == "候选池"].sort_values("l2_tot", ascending=False)
    if not cand.empty:
        title = f"=== {'Final' if not fast_mode else 'Initial'} Candidate Pool Top 30 ==="
        print(f"\n  {title}")
        cols = ["ts_code", "name", "l2_tot", "l2_fq", "l2_val", "l2_liq", "l2_bon",
                "pe", "pb", "dv_ratio", "total_mv", "roe", "gross_margin",
                "debt_ratio", "industry"]
        for _, r in cand.head(30).iterrows():
            mv_str = f"{r['total_mv']/10000:.0f}yi" if r.get("total_mv") and r["total_mv"] == r["total_mv"] else "-"
            roe_str = f"ROE={r['roe']:.1f}%" if r.get("roe") and r["roe"] == r["roe"] else ""
            gm_str = f"GM={r['gross_margin']:.0f}%" if r.get("gross_margin") and r["gross_margin"] == r["gross_margin"] else ""
            extra = " ".join(filter(None, [roe_str, gm_str]))
            print(f"    {r['ts_code']:<12s} {str(r['name']):<8s}  "
                  f"L2={r['l2_tot']:.1f}  "
                  f"FQ={r['l2_fq']:.1f} V={r['l2_val']:.1f} L={r['l2_liq']:.1f} B={r['l2_bon']:.1f}  "
                  f"PE={r['pe']} PB={r['pb']} DY={r['dv_ratio']}  "
                  f"MV={mv_str}  {extra}  {r['industry']}")

    return df


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="全 A 股批量筛选（含财务保质校验）")
    p.add_argument("--output", "-o", default="output/screener_result.csv",
                   help="输出 CSV 路径")
    p.add_argument("--fast", action="store_true",
                   help="跳过 Phase 4，仅用 daily_basic 快筛（满分~11）")
    args = p.parse_args()
    run_screener(args.output, fast_mode=args.fast)
