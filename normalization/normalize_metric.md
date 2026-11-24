# metric 文本归一化（STM / wer_ref）

用于生成 `stm`、`wer_ref` 。实现：`normalize_metric()`。

## 流程

```text
原始文本
-> 清洗标记
-> 删除结构标签
-> NFKC
-> 弯撇号转 ASCII
-> 百分号前置空格压缩
-> 按语种做 TN
-> 标点替换、空白压缩
-> 默认转大写
-> 分词
```

## 清洗标记

先处理会影响后续判断的源标记：

- `html.unescape`：`&amp;` -> `&`
- 删除不可见/控制字符
- 删除 `#`、`*` 等标注符号
- 百分号前的多余空格会在后续压缩

## 结构标签

成对的 `<...>`、`[...]`、`(...)`、`（...）` 一律删除，包括括号和内容，不区分已知/未知标签。

```text
a<b>c             -> ac
a[bc]d            -> ad
a(bc)d            -> ad
a（bc）d          -> ad
<sil> <pause>     -> ''
<When You're Down And Out> -> ''
```

支持嵌套；未匹配的开括号只删除括号本身，未匹配的闭括号保留。

## NFKC

`unicodedata.normalize('NFKC', text)` 做兼容分解再组合，主要作用是统一字符表面形式，方便后面做 TN 和分词：

- 全角字母数字 -> 半角：`ＡＢＣ１２３` -> `ABC123`
- 全角标点 -> 半角：`，` -> `,`，`？` -> `?`
- 兼容汉字统一：`郎` -> `郎`
- 连字/上标归一：`ﬁ` -> `fi`，`²` -> `2`
- 全角空格 -> 普通空格

NFKC 不负责删除标签，也不做数字口语化；这两步分别在前面和后面完成。

## 弯撇号

NFKC 后，把满足条件的弯撇号 `’` 转成 ASCII `'`，例如 `don’t` -> `don't`，避免英文 TN 和分词结果不一致。

## Text Normalization

- `lang=en`：`whisper-normalizer`
- `lang=zh`：`wetext` 的 `Normalizer(lang="zh", operator="tn")`
- `lang=auto`：含 CJK 走中文，含拉丁字母走英文，否则沿用前文语种
- `to_char` 默认：英文 `False`，其他语言 `True`
- 默认 `case_sensitive=False`

TN 会处理数字、时间、金额、缩写等口语化形式；STM 和 hypothesis 必须使用同一版本、同一参数。

## 标点、空白和分词

- 标点做统一替换，STM 不保留标识符连字符保护
- 连续空白压缩为单空格
- 默认转大写
- 最后按字符/词切成单空格分隔的 token 串

## 输出

单空格分隔的 token 串；默认大写。归一化后为空的 utterance 不写入 STM。
