# 内容规范（Content Spec v1）

本文件是知识点内容文件的唯一契约。任何内容文件必须通过 `python tools/validate_content.py` 才算合格。

## 1. 目录与命名

```
content/
  _taxonomy.json                 # 三级骨架，唯一真源
  morph/nouns.json               # 一级目录 slug / 二级章节 slug
  tense_voice/passive.json
  ...
```

文件位置 = `content/{level1_id}/{chapter_slug}.json`。**文件名必须与 taxonomy 中的 slug 完全一致。**

文件内三级知识点标题**必须与 taxonomy 中该章节的 `points` 数组逐字相同、顺序一致、数量一致**。不得增删改。

## 2. 文件结构

```json
{
  "level1": "morph",
  "chapter": "nouns",
  "items": [ {知识点}, {知识点} ]
}
```

## 3. 知识点字段

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| id | string | 是 | `{level1}.{chapter}.{英文短横线slug}`，全局唯一 |
| title | string | 是 | 与 taxonomy 逐字相同 |
| brief | string | 是 | ≤ 30 字，说明这个点解决什么问题 |
| difficulty | int | 是 | 1–4，1=基础 2=常规 3=易错 4=难点 |
| tags | string[] | 是 | 从 `高频` `易错` `难点` `基础` `写作` 中选，1–3 个 |
| prereq | string[] | 是 | 前置知识点 id，可为空数组 |
| concept | object | 是 | 见 §4 |
| review | object | 是 | 见 §5 |
| drills | object[] | 是 | 见 §6，数量 4–7；高频点 ≥5 |

## 4. concept（讲解）

```json
{
  "summary": "2–4 句。必须先给判定标准或核心机制，不要写“本知识点很重要”这类空话。",
  "sections": [
    { "h": "小标题", "p": "讲解段落，可以多句。", "bullets": ["规则一", "规则二"] }
  ],
  "examples": [
    { "en": "English sentence.", "zh": "中文翻译", "ok": true, "note": "说明这条例句演示了哪条规则" },
    { "en": "Wrong sentence.", "zh": "中文", "ok": false, "note": "错在哪里，正确写法是什么" }
  ],
  "pitfalls": [
    { "wrong": "错误句", "right": "正确句", "why": "错因，必须点出机制而不是“习惯用法”" }
  ],
  "contrast": { "withTitle": "易混知识点名", "diff": "一句话说清区别" },
  "mnemonic": "记忆钩子，可为空字符串"
}
```

约束：
- `sections` 2–4 个；每个 section 至少 `p` 或 `bullets` 之一非空。
- `examples` 4–8 条，**至少 2 条 `ok:false`**。
- `pitfalls` 2–3 条。
- 例句必须自成一句、首字母大写、有句末标点。英文例句不得夹中文。
- 不得出现「容易混淆」「要注意」这类不解释机制的表述。

## 5. review（复习卡）

```json
{
  "core": ["3–6 条浓缩要点，能在 15 秒内扫完"],
  "trigger": "看到 X 就想到 Y（识别信号 → 反应动作）",
  "quickCheck": [ { "q": "自检问题", "a": "答案" } ]
}
```

`quickCheck` 2–3 条。用于复习时的主动回忆，不参与判分。

## 6. drills（训练题）

公共字段：`id`（`{kp_id}.d{n}`）、`type`、`stem`、`explain`、`difficulty`（1–4）。`explain` 必须解释「为什么」，不能只重复答案。

题型 5 种，一个知识点的 drills 必须**至少覆盖 3 种题型**，且第 1 题必须是 `choice`。

### choice
```json
{ "type": "choice", "stem": "空格用 ___ 表示", "options": ["选项1","选项2","选项3","选项4"],
  "answer": "选项1", "explain": "...", "trap": "主要干扰项的错因" }
```
- 恰好 4 个选项，互不重复，不带 A./B. 前缀。
- `answer` 必须与 options 中某一项**完全一致**。
- `trap` 必填，说明最强干扰项为什么错。

### fill
```json
{ "type": "fill", "stem": "He gave me two ___ (advice).", "answer": "pieces of advice",
  "accept": ["pieces of advice"], "hint": "提示，可为空字符串", "explain": "..." }
```
- `stem` 必须包含至少一个 `___`。
- `accept` 为可接受的全部写法（大小写差异无需列出，判分时会忽略大小写）。
- 答案必须是**唯一确定的**，不能出现「可以填 A 也可以填 B 且语义不同」的情况。

### correct（改错）
```json
{ "type": "correct", "stem": "含错误的完整句子", "answer": "改正后的完整句子",
  "accept": ["..."], "explain": "..." }
```
- `stem` 必须真的含错，且**只有一个错误**。
- `answer` 是完整句子，不是片段。

### order（句子重组）
```json
{ "type": "order", "stem": "把下列词组连成一句通顺的话", "tokens": ["was","the","book","written","by","him"],
  "answer": "The book was written by him.", "explain": "..." }
```
- `tokens` 打乱顺序，且必须能唯一还原出 `answer`。
- `answer` 首字母大写、有句末标点。

### translate（汉译英判定）
```json
{ "type": "translate", "stem": "他建议我们推迟会议。",
  "answer": "He suggested that we (should) put off the meeting.",
  "require": [["suggested"], ["put off", "postpone"], ["meeting"]],
  "forbid": ["suggested us to"],
  "explain": "..." }
```
- `require`：数组的数组，**外层每一组都必须命中**，内层是并列可接受写法（不区分大小写）。
- `forbid`：出现即判错的结构，用来抓典型中式错误。
- `answer` 为参考译文，仅展示，不参与完全比对。

## 7. 质量红线

1. **不准造伪规则**。写不出明确规则、举不出常见错误的，不要写成知识点（清单已锁定，若某点实在无内容，也要给出真实可考的规则，不得编造）。
2. **例句必须语法正确**。错误例句只允许出现在 `ok:false` 或 `pitfalls.wrong`。
3. **不得重复出题**。同一知识点内题干不得雷同，选项不得只换一个词。
4. **不得注水**。禁止「总之」「由此可见」「非常重要」等填充句。
5. **术语统一**：谓语动词、非谓语动词、先行词、关系代词、主句、从句、限定性、非限定性。
6. 中文用全角标点，英文用半角标点。

## 8. 自检

```bash
python tools/validate_content.py content/morph/nouns.json
```

该脚本会检查：JSON 合法性、taxonomy 对齐、id 唯一、字段完整、选项与答案一致、`___` 存在、题型覆盖、例句标点、答案可归一化等。**必须 0 error 才算完成。**
