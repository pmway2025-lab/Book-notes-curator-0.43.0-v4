#!/usr/bin/env python3
"""個人資產配置試算工具（personal-wealth-allocation-agent）。

純標準函式庫，無外部相依。所有輸出都是「規劃用試算」，不是預測，也不是投資建議。

子命令：
    emergency  緊急預備金目標與缺口
    target     依年齡與風險屬性推導目標股債比
    rebalance  依 5/25 法則計算再平衡下單金額
    project    複利推估（基準／悲觀兩情境）
    fire       退休目標數與缺口
    checkup    財務體檢（儲蓄率、淨值、負債、安全順序建議）
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass

# --- 規劃用假設（見 references/asset-allocation-models.md 第 6 節） ---
RETURN_ASSUMPTIONS = {
    "stocks": 0.065,
    "bonds": 0.035,
    "cash": 0.015,
}
PESSIMISTIC_STOCK_RETURN = 0.03
INFLATION = 0.02

RISK_RULES = {"conservative": 100, "moderate": 110, "aggressive": 120}
STABILITY_ADJUST = {"stable": 5, "variable": 0, "irregular": -10}
EMERGENCY_MONTHS = {"stable": 6, "variable": 9, "irregular": 12}
HIGH_RATE_DEBT = 0.06
EPS = 1e-9  # 浮點誤差容忍值，避免 0.30-0.25 算成 0.049999... 而漏掉門檻

DISCLAIMER = (
    "\n※ 以上為規劃用試算，非投資建議；報酬率為假設值，實際結果會不同。"
)


def _fmt(amount: float) -> str:
    return f"{amount:,.0f}"


# --------------------------------------------------------------------------
# 緊急預備金
# --------------------------------------------------------------------------
def emergency_fund(monthly_expense: float, months: int) -> float:
    """緊急預備金目標金額。"""
    if monthly_expense < 0 or months < 0:
        raise ValueError("月支出與月數不可為負數")
    return monthly_expense * months


def recommended_months(income_stability: str) -> int:
    return EMERGENCY_MONTHS.get(income_stability, 6)


# --------------------------------------------------------------------------
# 目標股債比
# --------------------------------------------------------------------------
def target_equity_weight(
    age: int,
    profile: str = "moderate",
    income_stability: str = "variable",
    dependents: int = 0,
    emergency_months_held: float | None = None,
    years_to_goal: int | None = None,
) -> float:
    """回傳目標股票權重（0–1）。

    以 100/110/120 法則為基準，再依收入穩定度、扶養人數、緊急金厚度與
    目標年限調整；總調整幅度限制在 ±20 個百分點內。
    """
    if not 0 < age < 120:
        raise ValueError("年齡需介於 1 到 119 之間")
    if profile not in RISK_RULES:
        raise ValueError(f"risk profile 需為 {sorted(RISK_RULES)} 之一")

    base = RISK_RULES[profile] - age

    adjust = STABILITY_ADJUST.get(income_stability, 0)
    if dependents >= 2:
        adjust -= 10
    elif dependents == 1:
        adjust -= 5
    if emergency_months_held is not None:
        if emergency_months_held >= 12:
            adjust += 5
        elif emergency_months_held < 6:
            adjust -= 10
    adjust = max(-20, min(20, adjust))

    weight = base + adjust

    # 五年內要用的錢不進股市；5–10 年逐步降載。
    if years_to_goal is not None:
        if years_to_goal < 5:
            return 0.0
        if years_to_goal < 10:
            weight = min(weight, 50)

    return max(0.0, min(95.0, weight)) / 100


def allocation_table(equity_weight: float, total: float | None = None) -> list[dict]:
    """把股票權重展開成股／債／現金三列（現金固定為防守用 10%）。"""
    cash = 0.10
    equity = min(equity_weight, 1 - cash)
    bonds = max(0.0, 1 - cash - equity)
    rows = [
        ("股票（全球分散為核心）", equity, "長期成長引擎"),
        ("債券／短債", bonds, "降低波動、危機緩衝"),
        ("現金與定存", cash, "流動性與機會準備"),
    ]
    return [
        {
            "asset": name,
            "weight": w,
            "amount": (total * w) if total is not None else None,
            "role": role,
        }
        for name, w, role in rows
    ]


# --------------------------------------------------------------------------
# 再平衡（5/25 法則）
# --------------------------------------------------------------------------
@dataclass
class RebalanceRow:
    asset: str
    current: float
    current_weight: float
    target_weight: float
    target_amount: float
    trade: float
    triggered: bool


def check_targets(targets: dict[str, float]) -> None:
    total = sum(targets.values())
    if abs(total - 1.0) > 0.005:
        raise ValueError(f"目標權重總和需為 1，目前為 {total:.4f}")
    if any(w < 0 for w in targets.values()):
        raise ValueError("目標權重不可為負數")


def is_triggered(current_weight: float, target_weight: float) -> bool:
    """5/25 法則：絕對偏離 5 個百分點或相對偏離 25%，先到先觸發。"""
    drift = abs(current_weight - target_weight)
    return drift >= 0.05 - EPS or (
        target_weight > 0 and drift >= target_weight * 0.25 - EPS
    )


def rebalance(
    holdings: dict[str, float], targets: dict[str, float], new_cash: float = 0.0
) -> list[RebalanceRow]:
    check_targets(targets)
    if new_cash < 0:
        raise ValueError("新增資金不可為負數")
    missing = set(targets) - set(holdings)
    holdings = {**{k: 0.0 for k in missing}, **holdings}

    current_total = sum(holdings.values())
    future_total = current_total + new_cash
    if future_total <= 0:
        raise ValueError("總資產需大於 0")

    rows = []
    for asset in sorted(set(holdings) | set(targets)):
        current = holdings.get(asset, 0.0)
        tw = targets.get(asset, 0.0)
        cw = current / current_total if current_total > 0 else 0.0
        target_amount = future_total * tw
        rows.append(
            RebalanceRow(
                asset=asset,
                current=current,
                current_weight=cw,
                target_weight=tw,
                target_amount=target_amount,
                trade=target_amount - current,
                triggered=is_triggered(cw, tw),
            )
        )
    return rows


# --------------------------------------------------------------------------
# 複利推估
# --------------------------------------------------------------------------
def project(
    initial: float, monthly: float, years: int, annual_return: float
) -> float:
    """月投入、月複利的期末名目金額。"""
    if years < 0:
        raise ValueError("年數不可為負數")
    r = (1 + annual_return) ** (1 / 12) - 1
    months = years * 12
    balance = initial
    for _ in range(months):
        balance = balance * (1 + r) + monthly
    return balance


def real_value(nominal: float, years: int, inflation: float = INFLATION) -> float:
    """折算成今日購買力。"""
    return nominal / ((1 + inflation) ** years)


# --------------------------------------------------------------------------
# FIRE / 退休缺口
# --------------------------------------------------------------------------
def fire_number(annual_expense: float, swr: float = 0.035) -> float:
    if not 0 < swr < 0.2:
        raise ValueError("提領率需介於 0 與 0.2 之間")
    if annual_expense < 0:
        raise ValueError("年支出不可為負數")
    return annual_expense / swr


# --------------------------------------------------------------------------
# 財務體檢
# --------------------------------------------------------------------------
def checkup(p: dict) -> dict:
    income = float(p["monthly_income"])
    expense = float(p["monthly_expense"])
    lumpy = float(p.get("annual_lumpy_expense", 0)) / 12
    stability = p.get("income_stability", "variable")
    cash = float(p.get("cash", 0))
    investments = float(p.get("investments", 0))
    other = float(p.get("other_assets", 0))
    debts = p.get("debts", []) or []
    debt_total = sum(float(d.get("balance", 0)) for d in debts)
    debt_payment = sum(float(d.get("monthly_payment", 0)) for d in debts)

    if income <= 0:
        raise ValueError("月收入需大於 0")

    total_expense = expense + lumpy
    savings = income - total_expense - debt_payment
    savings_rate = savings / income
    net_worth = cash + investments + other - debt_total
    months_held = cash / total_expense if total_expense > 0 else 0.0
    need_months = recommended_months(stability)
    target_cash = total_expense * need_months
    high_rate = [d for d in debts if float(d.get("rate", 0)) > HIGH_RATE_DEBT
                 and float(d.get("balance", 0)) > 0]

    actions = []
    if savings_rate < 0.10:
        actions.append(
            f"儲蓄率 {savings_rate:.1%} 偏低：先做支出結構分析與收入路徑，"
            "配置議題暫緩。"
        )
    if months_held < need_months:
        actions.append(
            f"緊急預備金 {months_held:.1f} 個月，未達建議的 {need_months} 個月"
            f"（缺口 {_fmt(max(0, target_cash - cash))} 元）：優先補足。"
        )
    for d in high_rate:
        actions.append(
            f"「{d.get('name', '負債')}」利率 {float(d['rate']):.2%} 高於 6%："
            f"清償是確定的無風險報酬，優先於投資。"
        )
    if float(p.get("insurance_annual_premium", 0)) > income * 12 * 0.15:
        actions.append("年繳保費超過年收入 15%：做保單體檢，確認是否被儲蓄型佔用預算。")
    if not actions:
        actions.append("安全順序已達標，可依目標配置表投入成長層部位。")

    eq = target_equity_weight(
        age=int(p.get("age", 35)),
        profile=p.get("risk_profile", "moderate"),
        income_stability=stability,
        dependents=int(p.get("dependents", 0)),
        emergency_months_held=months_held,
    )

    return {
        "savings_rate": savings_rate,
        "monthly_savings": savings,
        "net_worth": net_worth,
        "emergency_months_held": months_held,
        "emergency_target": target_cash,
        "debt_total": debt_total,
        "debt_payment_ratio": debt_payment / income,
        "target_equity_weight": eq,
        "allocation": allocation_table(eq, cash + investments),
        "actions": actions,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def cmd_emergency(a) -> None:
    months = a.months or recommended_months(a.stability)
    target = emergency_fund(a.expense, months)
    print(f"建議月數：{months} 個月（收入型態：{a.stability}）")
    print(f"目標金額：{_fmt(target)} 元")
    if a.cash is not None:
        gap = target - a.cash
        print(f"目前現金：{_fmt(a.cash)} 元（{a.cash / a.expense:.1f} 個月）")
        print("缺口：" + (f"{_fmt(gap)} 元，先補滿再談投資" if gap > 0 else "已達標"))


def cmd_target(a) -> None:
    eq = target_equity_weight(
        a.age, a.profile, a.stability, a.dependents,
        a.emergency_months, a.years_to_goal,
    )
    print(f"目標股票權重：{eq:.0%}（{a.profile}／{a.stability}／{a.age} 歲）")
    print(f"{'資產類別':<24}{'權重':>8}{'金額':>14}  功能")
    for row in allocation_table(eq, a.total):
        amt = _fmt(row["amount"]) if row["amount"] is not None else "-"
        print(f"{row['asset']:<24}{row['weight']:>8.0%}{amt:>14}  {row['role']}")
    if a.years_to_goal is not None and a.years_to_goal < 5:
        print("※ 目標在 5 年內：這筆錢不進股市。")
    print(DISCLAIMER)


def cmd_rebalance(a) -> None:
    data = _load(a.file)
    rows = rebalance(data["holdings"], data["targets"], a.cash)
    print(f"{'資產':<20}{'現值':>12}{'現權重':>9}{'目標':>8}{'調整':>12}  觸發")
    for r in rows:
        flag = "是" if r.triggered else "-"
        print(
            f"{r.asset:<20}{_fmt(r.current):>12}{r.current_weight:>9.1%}"
            f"{r.target_weight:>8.0%}{_fmt(r.trade):>12}  {flag}"
        )
    if a.cash:
        print(f"\n新增資金 {_fmt(a.cash)} 元已納入計算（優先用新資金補低配，減少賣出）。")
    if not any(r.triggered for r in rows):
        print("\n未觸發 5/25 門檻：本次可不調整，只投入新資金。")
    print(DISCLAIMER)


def cmd_project(a) -> None:
    base = project(a.initial, a.monthly, a.years, a.rate)
    pess = project(a.initial, a.monthly, a.years, PESSIMISTIC_STOCK_RETURN)
    invested = a.initial + a.monthly * 12 * a.years
    print(f"投入本金合計：{_fmt(invested)} 元")
    print(f"基準情境（年化 {a.rate:.1%}）：{_fmt(base)} 元"
          f"（今日購買力 {_fmt(real_value(base, a.years))} 元）")
    print(f"悲觀情境（年化 {PESSIMISTIC_STOCK_RETURN:.1%}）：{_fmt(pess)} 元"
          f"（今日購買力 {_fmt(real_value(pess, a.years))} 元）")
    print(DISCLAIMER)


def cmd_fire(a) -> None:
    number = fire_number(a.annual_expense, a.swr)
    print(f"年支出 {_fmt(a.annual_expense)} 元，提領率 {a.swr:.1%}")
    print(f"退休目標數：{_fmt(number)} 元")
    if a.current is not None:
        gap = number - a.current
        print(f"目前資產：{_fmt(a.current)} 元；缺口 {_fmt(max(0, gap))} 元")
        if a.monthly and gap > 0:
            for years in range(1, 61):
                if project(a.current, a.monthly, years, a.rate) >= number:
                    print(f"以每月投入 {_fmt(a.monthly)} 元、年化 {a.rate:.1%} 推估，"
                          f"約需 {years} 年")
                    break
            else:
                print("以目前投入金額，60 年內未達標：需提高投入、降低目標或延長年限。")
    print("※ 提領率建議採 3.0–3.5%（台灣情境較保守）。" + DISCLAIMER)


def cmd_checkup(a) -> None:
    r = checkup(_load(a.file))
    print("一、財務現況摘要")
    print(f"  儲蓄率：{r['savings_rate']:.1%}（每月可投入 {_fmt(r['monthly_savings'])} 元）")
    print(f"  淨值：{_fmt(r['net_worth'])} 元")
    print(f"  緊急金：{r['emergency_months_held']:.1f} 個月"
          f"（目標 {_fmt(r['emergency_target'])} 元）")
    print(f"  負債總額：{_fmt(r['debt_total'])} 元；月付佔收入 {r['debt_payment_ratio']:.1%}")
    print("\n二、目標配置")
    for row in r["allocation"]:
        print(f"  {row['asset']:<24}{row['weight']:>6.0%}  {_fmt(row['amount'] or 0)} 元")
    print("\n三、依財務安全順序的行動")
    for i, act in enumerate(r["actions"], 1):
        print(f"  {i}. {act}")
    print(DISCLAIMER)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="個人資產配置試算工具")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("emergency", help="緊急預備金")
    e.add_argument("--expense", type=float, required=True, help="月支出")
    e.add_argument("--months", type=int, help="自訂月數（預設依收入型態）")
    e.add_argument("--stability", default="variable",
                   choices=sorted(EMERGENCY_MONTHS))
    e.add_argument("--cash", type=float, help="目前可動用現金")
    e.set_defaults(func=cmd_emergency)

    t = sub.add_parser("target", help="目標股債比")
    t.add_argument("--age", type=int, required=True)
    t.add_argument("--profile", default="moderate", choices=sorted(RISK_RULES))
    t.add_argument("--stability", default="variable", choices=sorted(STABILITY_ADJUST))
    t.add_argument("--dependents", type=int, default=0)
    t.add_argument("--emergency-months", type=float, dest="emergency_months")
    t.add_argument("--years-to-goal", type=int, dest="years_to_goal")
    t.add_argument("--total", type=float, help="可配置總金額")
    t.set_defaults(func=cmd_target)

    rb = sub.add_parser("rebalance", help="再平衡（5/25 法則）")
    rb.add_argument("--file", required=True, help="holdings.json")
    rb.add_argument("--cash", type=float, default=0.0, help="本次新增投入資金")
    rb.set_defaults(func=cmd_rebalance)

    pr = sub.add_parser("project", help="複利推估")
    pr.add_argument("--initial", type=float, default=0.0)
    pr.add_argument("--monthly", type=float, default=0.0)
    pr.add_argument("--years", type=int, required=True)
    pr.add_argument("--rate", type=float, default=RETURN_ASSUMPTIONS["stocks"])
    pr.set_defaults(func=cmd_project)

    f = sub.add_parser("fire", help="退休目標數")
    f.add_argument("--annual-expense", type=float, required=True, dest="annual_expense")
    f.add_argument("--swr", type=float, default=0.035)
    f.add_argument("--current", type=float)
    f.add_argument("--monthly", type=float, default=0.0)
    f.add_argument("--rate", type=float, default=RETURN_ASSUMPTIONS["stocks"])
    f.set_defaults(func=cmd_fire)

    c = sub.add_parser("checkup", help="財務體檢")
    c.add_argument("--file", required=True, help="profile.json")
    c.set_defaults(func=cmd_checkup)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
