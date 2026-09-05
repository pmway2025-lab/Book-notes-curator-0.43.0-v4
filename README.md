# 理財長 AGENT — 個人投資理財與資產配置

一套給 Claude Code / Claude 使用的 **Skill 套件**：把個人的收入、負債、保障、
稅務與人生目標，轉成可執行的資產配置方案與再平衡紀律（台灣在地情境）。

> 本套件提供**分析框架與試算**，不構成投資建議、不推薦個股、不預測市場。

## 內容

```
skills/personal-wealth-allocation-agent/
├── SKILL.md                          # 主 skill：身分、四階段 SOP、輸出格式、IF...THEN 快查
├── references/
│   ├── asset-allocation-models.md    # 生命週期股債比、核心衛星、5/25 再平衡、報酬假設
│   ├── tw-investment-vehicles.md     # 台股 ETF、複委託、勞退自提、保險、房貸、稅制
│   ├── review-sop-and-templates.md   # 財務體檢問卷、JSON 範本、年度檢視議程、決策紀錄表
│   └── if-then-playbook.md           # 33 條情境應變清單
└── scripts/
    ├── portfolio.py                  # 試算 CLI（純標準函式庫）
    ├── test_portfolio.py             # 32 個單元測試
    └── examples/                     # profile.json / holdings.json 範例
```

## 核心設計

**財務安全順序**（不可跳階）：
緊急預備金 → 保障補洞 → 清高利負債 → 制度優惠額度（勞退自提） → 核心配置 → 衛星（≤20%）

**三條鐵則**：
1. 五年內要用的錢不進股市。
2. 風險屬性取「能力／意願／需求」三者中最保守者，不只看問卷。
3. 再平衡規則事前寫定（5/25 法則＋每年一次），優先用新資金補低配。

## 試算工具用法

```bash
cd skills/personal-wealth-allocation-agent/scripts

python3 portfolio.py emergency --expense 45000 --stability irregular --cash 300000
python3 portfolio.py target    --age 32 --profile moderate --total 1400000
python3 portfolio.py rebalance --file examples/holdings.json --cash 100000
python3 portfolio.py project   --initial 500000 --monthly 20000 --years 20
python3 portfolio.py fire      --annual-expense 720000 --current 1400000 --monthly 20000
python3 portfolio.py checkup   --file examples/profile.json
```

執行測試：

```bash
python3 -m unittest discover -s skills/personal-wealth-allocation-agent/scripts
```

需求：Python 3.10+（使用 `X | None` 型別語法），無第三方套件。

## 安裝為 Claude Skill

把 `skills/personal-wealth-allocation-agent/` 整個目錄放到 skill 目錄下
（個人層級 `~/.claude/skills/`，或專案層級 `.claude/skills/`）即可；
本 repo 亦附 `.claude-plugin/plugin.json`，可直接以 plugin 形式安裝。

## 與其他 skill 的協同

個股基本面 → `buffett-value-investing-framework`、`financial-ratio-analysis-toolkit`；
偏誤深查 → `investment-decision-bias-checklist`；保單 → `insurance-coverage-checkup`；
稅務 → `tw-tax-compliance-toolkit`；房產 → `tw-property-due-diligence`；
詐騙 → `scam-bayes-detection`；重大決策多視角辯論 → `wangyi-committee-protocol`。

## 免責

法規、稅率、給付條件會隨時間調整。文件中所有制度性數字皆須以財政部、勞動部、
金管會、衛福部及各金融機構的**最新公告**為準，決策前請自行查證或洽詢合格顧問。
