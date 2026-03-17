# 皮肤病条目筛选策略详解

## 核心问题

ICD-11 的 37,052 条 MMS 条目中，皮肤相关疾病散布在多个章节。本文档记录我们如何从中筛选，以及已知的漏洞和改进方向。

---

## 当前筛选策略（v3）

### 三重策略

```
策略 A: Chapter 14 全量纳入
  → 863 条 (100% 是皮肤病)

策略 B: Foundation URI 桥接
  → 对非 Ch14 条目，检查其 Foundation URI 是否在 Foundation 皮肤子树中
  → 原理: Foundation 允许多父节点，一个疾病可以同时属于感染病和皮肤病
  → 命中: 689 条

策略 C: 关键词匹配
  → 对非 Ch14 条目，检查标题是否包含皮肤相关关键词
  → 命中: 513 条

合并去重: 1,805 条
```

### 关键词列表（73 个模式）

```python
skin, cutaneous, dermat, epider, subcutan, melanom, melanocyt,
nevus, naevus, nevi, naevi, pigment, depigment, vitiligo, albinism,
alopecia, hair loss, hirsut, hypertrichos, nail, onych, paronych,
pemphig, urticaria, erythema, pruritus, prurigo, psoriasis, eczema,
acne, rosacea, lichen, bullous, blister, rash, exanthem, angioedema,
vasculitis, purpura, scleroderma, dermatomyositis, morphea,
photosensit, photodermat, herpes, tinea, scabies, cellulitis,
wart, verruca, impetigo, follicul, kaposi, basal cell, squamous cell,
merkel, bowen, keratoacanthoma, burn of, frostbite, sunburn,
decubitus, pressure ulcer, scar, keloid, sebaceous, sweat gland,
ichthyosis, keratosis, xeroderma, epidermolysis, haemangioma,
hemangioma, birthmark
```

---

## 已确认的遗漏（374 条潜在遗漏）

### 遗漏类型 1: 关键词未覆盖的疾病名

| 遗漏疾病 | 章节 | 原因 |
|----------|------|------|
| Leprosy (麻风) | Ch01 | 关键词列表缺少 "leprosy" |
| Erysipelas (丹毒) | Ch01 | 关键词列表缺少 "erysipelas" |
| Sporotrichosis (孢子丝菌病) | Ch01 | 关键词列表缺少 "sporotrich" |
| Gas gangrene (气性坏疽) | Ch01 | 关键词列表缺少 "gangrene" |
| Mycetoma (足菌肿) | Ch01 | 关键词列表缺少 "mycetoma" |
| Cutaneous diphtheria | Ch01 | Foundation 只归在 "白喉" 下 |

### 遗漏类型 2: Ch22 皮肤外伤 (333 条)

Ch22 中有大量 "Abrasion of scalp", "Contusion of eyelid" 等条目。
这些是皮肤外伤，但标题写的是 "abrasion of [body part]" 而非 "skin abrasion"。

### 遗漏类型 3: MMS 残余类别 (无 Foundation URI)

```
1B72.Z  Impetigo, unspecified
1B74.Z  Superficial bacterial folliculitis, unspecified
```
这些是 MMS 的 "未特指" 编码，Foundation 中没有对应实体，
且标题可能不含关键词（如 "Other specified pyogenic bacterial infection"）。

### 遗漏类型 4: Foundation 未归入皮肤子树

```
Ch02: 大部分皮肤肿瘤 (66% 未在皮肤子树中)
  → 原因: Foundation 将它们归在 "肿瘤" 分支而非 "皮肤" 分支
```

---

## 改进方案

### 方案 1: 扩展关键词（最小改动）

在现有关键词基础上增加:
```python
# 遗漏的感染病
r'leprosy', r'erysipelas', r'sporotrich', r'mycetoma', r'chromomycosis',
r'leishmani', r'pediculosis', r'myiasis', r'hookworm',
r'necrotizing fasciitis', r'carbuncle', r'furuncle',

# 遗漏的其他
r'gangrene', r'necrosis.*skin', r'bedsore',
r'xanthoma', r'amyloid.*skin', r'calcinosis',
r'lymphoedema', r'lymphedema',
r'graft.*skin', r'flap.*skin', r'skin substitute',

# Ch22 外伤
r'abrasion', r'contusion', r'laceration of skin',
r'wound.*head|wound.*neck|wound.*trunk|wound.*limb',
```

预计可额外捞回 ~200 条。

### 方案 2: 穷举法（最全面）

```python
# 将所有 11 章节 10,721 条全部纳入
# 为每个条目标注皮肤相关度:
#   - 'core': Ch14 全量
#   - 'high': Foundation 皮肤子树 + 关键词
#   - 'medium': 扩展关键词
#   - 'low': 仅因在目标章节而纳入
#   - 'none': 经人工审核确认无关

# 这样后续使用者可以自行决定用哪个级别
```

### 方案 3: LLM 辅助分类

对关键词未命中的 8,916 条，让 LLM 逐条判断 "这个疾病是否与皮肤相关"：
```python
prompt = f"""
ICD-11 条目: {title}
请判断: 这个疾病是否与皮肤/皮肤附属器(毛发、指甲、皮脂腺、汗腺)
或皮肤表面(黏膜、结膜)有直接关系?
回答: YES / NO / MAYBE
"""
```
可以在几小时内完成全部 ~9,000 条的分类。

---

## 验证方法

### 完整性检查

```python
# 检查已有映射表中的疾病是否都在图谱中
import json
with open('disease_icd11_mapping.json') as f:
    mapping = json.load(f)
for disease, info in mapping.items():
    code = info['code']
    # 在图谱中查找该编码
    if code not in kg_codes:
        print(f"MISSING: {disease} ({code})")
```

### 交叉验证

```python
# 用 Derm1M 的 disease_label 列表验证
# 如果一个 disease_label 在数据集中出现 >100 次但图谱中找不到
# 则说明该疾病很可能被遗漏了
unmapped = df.groupby('disease_label').size()
high_freq_unmapped = unmapped[unmapped > 100]
```
