# Demo1 发音修正层说明

## 目标

- 把“给人看”的语义文本和“给 TTS/VC 读”的发音文本拆开。
- 优先解决“字面没问题，但克隆音色读出来还是像普通话”的问题。

## 当前链路

- `semantic_text`
  - 用于页面展示
  - 追求可读性和语义自然度
- `pronunciation_text`
  - 用于 TTS / 音色克隆
  - 追求更稳定的目标方言发音

## 当前策略

- `pronunciation_mode = rule_first`
- 先走高频词规则修正
- 若高风险词仍未解决，可触发 LLM fallback
- RAG 检索位已预留，但默认关闭

## 当前输出字段

- `semantic_text`
- `pronunciation_text`
- `pronunciation_rule_hits`
- `pronunciation_fallback_used`
- `pronunciation_notes`

## 说明

- 首版不追求完整音标体系
- 首版重点解决高频歧义词和容易被读成普通话的字面形式
