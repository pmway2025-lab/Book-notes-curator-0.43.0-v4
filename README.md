# Book-notes-curator — Skills

以書籍與方法論為底座，整理成可被 Claude 直接調用的 skill 套件。

| Skill | 說明 |
|---|---|
| [`career-planner-agent`](./career-planner-agent/) | 生涯規劃師 agent。第一代知識底座為古典及其著作體系，內含五步諮詢 SOP、生涯三葉草、生涯四度、五類心智牆、躍遷式策略與三張輸出模板，並定義了逐代擴充的迭代規範。 |

## 安裝方式

把 skill 資料夾放進 `~/.claude/skills/`（個人層級）或專案的 `.claude/skills/`：

```bash
cp -r career-planner-agent ~/.claude/skills/
```

## 內容性質聲明

各 skill 的章節架構參考自對應書籍的概念體系，**內容為 Claude 依自身知識所做的
獨立整理、延伸與操作化，不是書籍原文的摘錄或轉述**。書中的具體案例與原文論述
不予收錄；若需了解，請直接閱讀原書。
