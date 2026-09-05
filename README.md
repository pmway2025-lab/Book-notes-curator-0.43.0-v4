# Book-notes-curator — Skills

以書籍與方法論為底座，整理成可被 Claude 直接調用的 skill 套件。

| Skill | 說明 |
|---|---|
| [`career-planner-agent`](./career-planner-agent/) | 生涯規劃師 agent。第一代知識底座為古典及其著作體系，內含五步諮詢 SOP、生涯三葉草、生涯四度、五類心智牆、躍遷式策略與三張輸出模板，並定義了逐代擴充的迭代規範。 |
| [`strategic-geography-analyst`](./strategic-geography-analyst/) | 戰略地理分析師 agent。第一代知識底座為饒勝文《布局天下》的概念架構，把地理讀成「山川（含天時流場）／軍事／政治／經濟／商業物流」五鏡疊合的分析模型，內含四角四邊區位骨架、樞紐六判準、通道存廢評分、七步分析 SOP、三張輸出模板、基地環境分析層（六階段調查程序、三大類調查清單與圖面八要素）與現代轉譯（選址、供應鏈、工程動線）。 |

## 安裝方式

把 skill 資料夾放進 `~/.claude/skills/`（個人層級）或專案的 `.claude/skills/`：

```bash
cp -r career-planner-agent ~/.claude/skills/
cp -r strategic-geography-analyst ~/.claude/skills/
```

## 內容性質聲明

各 skill 的章節架構參考自對應書籍的概念體系，**內容為 Claude 依自身知識所做的
獨立整理、延伸與操作化，不是書籍原文的摘錄或轉述**。書中的具體案例與原文論述
不予收錄；若需了解，請直接閱讀原書。

**例外**：使用者自行提供並要求保留的語料（自有文件、手稿、圖面），
會全文逐字收錄於該 skill 的 `references/` 之下，並標明來源與校勘註，
以便回溯校對——這與上述「不收錄第三方著作原文」的規範分屬兩件事。
