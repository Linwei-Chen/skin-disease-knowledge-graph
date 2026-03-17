# 皮肤病知识图谱 (Skin Disease Knowledge Graph)

## 项目概述

基于 ICD-11 构建的全面皮肤病知识图谱，整合了 8 个数据源，覆盖 6,811 个节点和 32,080 条边。设计目标：为 VLM（视觉语言模型）训练提供结构化知识支持，实现高度可解释性的皮肤病鉴别诊断。

---

## 1. 数据源详细说明

### 1.1 ICD-11 Foundation（核心骨架）

- **来源**: WHO ICD-11 Foundation Component，经 Biopragmatics 转换为 OBO 格式
- **下载地址**: `https://w3id.org/biopragmatics/resources/icd11/icd11.obo`
- **本地文件**: `data/icd11_foundation.obo` (15 MB, 71,175 个实体)
- **许可证**: CC-BY-ND-3.0-IGO
- **版本**: 2025-10-31 (PyOBO v0.12.13 生成)
- **贡献**:
  - 皮肤章节子树根节点: `icd11:1639304259` ("Diseases of the skin")
  - BFS 遍历后得到 **5,216 个皮肤相关实体**
  - 提供: 疾病名称、英文定义(3,207个)、同义词(2,194个)、is_a 层级关系、MMS 编码映射

**Foundation 的两层结构**:
- **Foundation（本体层）**: 多父节点 DAG，一个疾病可以同时归属多个分支
- **MMS（编码层）**: 单父节点树，每个疾病只编入一个章节

**重要发现**: Foundation 皮肤子树 (5,216 节点) 并未覆盖所有皮肤相关疾病。在 MMS 中散落于其他章节的 461 条皮肤相关条目中，只有 55% (255条) 在 Foundation 皮肤子树中。特别是 Chapter 02 (肿瘤) 的皮肤肿瘤覆盖率仅 34%。因此需要三重策略补充。

### 1.2 ICD-11 MMS（编码层）

- **来源**: WHO ICD-11 MMS Linearization
- **本地文件**: `data/ICD-11-MMS-with-PathID.xlsx` (5.8 MB, 37,052 条)
- **版本**: 2026 Jan 28
- **贡献**: ICD-11 编码 (如 EA90)、Path ID 层级、中文名称 (LLM 翻译)

**皮肤相关条目筛选**: 从 11 个目标章节 (01,02,03,04,05,13,14,19,20,21,22) 中提取，采用三重策略：

| 策略 | 方法 | 命中量 |
|------|------|--------|
| 策略A | Chapter 14 全量纳入 | 863 条 |
| 策略B | 非Ch14 条目的 Foundation URI 在皮肤子树中 | 689 条 |
| 策略C | 非Ch14 条目标题匹配皮肤关键词 | 513 条 |
| 合并（去重）| | **1,805 条** |

**各章节皮肤相关筛选结果**:

| 章节 | 总条目 | 皮肤相关 | 筛选率 | 主要内容 |
|------|--------|----------|--------|----------|
| 01 | 1,069 | 269 | 25% | 皮肤感染（结核、梅毒、疱疹、真菌等） |
| 02 | 1,290 | 156 | 12% | 皮肤肿瘤（黑色素瘤、BCC、SCC 等） |
| 03 | 276 | 14 | 5% | 紫癜、贫血相关皮肤表现 |
| 04 | 264 | 71 | 27% | 免疫性皮肤病（狼疮、血管炎等） |
| 05 | 663 | 32 | 5% | 内分泌相关皮肤表现 |
| 13 | 997 | 52 | 5% | 口腔黏膜、唇部疾病 |
| 14 | 863 | 863 | 100% | **皮肤病主章节** |
| 19 | 643 | 47 | 7% | 新生儿/围产期皮肤病 |
| 20 | 1,354 | 106 | 8% | 皮肤发育异常 |
| 21 | 1,289 | 61 | 5% | 皮肤相关症状/体征 |
| 22 | 2,013 | 95 | 5% | 皮肤烧伤/创伤 |
| **合计** | **10,721** | **1,766** | **16%** | |

### 1.3 DermO（皮肤病专用本体）

- **来源**: Dermatological Disease Ontology
- **论文**: Fisher et al., 2016, Journal of Biomedical Semantics
- **下载地址**: `https://raw.githubusercontent.com/dermatology-ontology/dermatology/master/dermatology.obo`
- **本地文件**: `data/dermo.obo` (956 KB, 3,401 个概念)
- **许可证**: 未明确声明 (论文 CC BY)
- **贡献**:
  - 名称匹配到 ICD-11 节点: **889 个** (26.1%)
  - 新增交叉引用: 1,779 条 (SNOMED CT, OMIM, ICD-10, HPO, DOID)
  - 补充定义和同义词

**DermO 交叉引用来源**:
| 来源 | 引用数 |
|------|--------|
| SNOMED CT | 2,310 |
| DermLex | 1,050 |
| DOID | 663 |
| ICD-10 | 269 |
| HPO | 193 |
| OMIM | 165 |

### 1.4 HPO（人类表型本体 - 皮肤分支）

- **来源**: Human Phenotype Ontology
- **下载地址**: `http://purl.obolibrary.org/obo/hp.obo`
- **本地文件**: `data/hp.obo` (10 MB, 19,389 个表型)
- **许可证**: 学术免费使用
- **贡献**:
  - 皮肤/毛发/指甲表型分支 (根: HP:0001574 "Abnormality of the integument"): **1,094 个表型节点**
  - 子分支: 皮肤异常 808 + 毛发异常 167 + 指甲异常 102 + 其他 17
  - 作为独立节点层添加到图谱

### 1.5 DOID（疾病本体 - 皮肤病分支）

- **来源**: Human Disease Ontology
- **下载地址**: `http://purl.obolibrary.org/obo/doid.obo`
- **本地文件**: `data/doid.obo` (6.7 MB, 12,021 个疾病)
- **许可证**: CC0 1.0 (公有领域)
- **贡献**:
  - 皮肤病分支 (根: DOID:37 "skin disease"): 586 个疾病
  - 匹配到 ICD-11 节点: **234 个** (37.0%)
  - 新增交叉引用: 651 条 (UMLS CUI, MeSH, SNOMED, MIM)

### 1.6 RSDB（罕见皮肤病数据库）

- **来源**: Rare Skin Disease Database
- **论文**: Nature Scientific Data, 2022
- **下载地址**: `https://figshare.com/articles/dataset/Rare_Skin_Disease_Database/17704502`
- **本地文件**: `data/rsdb/` (21 个 CSV 文件, 222 MB)
- **许可证**: CC BY-NC-SA 4.0
- **贡献**:
  - 891 种罕见皮肤病，匹配到 ICD-11: **407 个** (45.7%)
  - 新增表型关联: **8,618 条**
  - 新增药物关联: **1,628 条**
  - 补充遗传模式、发病年龄、流行率信息

**RSDB 数据表**:
| 文件 | 内容 | 行数 |
|------|------|------|
| diseases.csv | 疾病实体 | 891 |
| genes.csv | 基因 | 28,077 |
| phenotypes.csv | 表型 | 9,732 |
| compounds.csv | 化合物/药物 | ~5,000 |
| disease_phenotype_relationships.csv | 疾病-表型关系 | 15,973 |
| compound_disease_relationships.csv | 药物-疾病关系 | 97,621 |

### 1.7 Orphanet（罕见病数据库）

- **来源**: Orphanet / Orphadata
- **下载地址**: `https://www.orphadata.com/`
- **本地文件**: `data/orphanet/` (8 个文件, 180 MB)
- **许可证**: CC BY 4.0
- **版本**: 2025-12-09
- **贡献**:
  - 罕见皮肤病分类 (en_product3_187.xml): **1,234 种**
  - 匹配到 ICD-11: **93 个** (来自分类) + 更多来自命名数据
  - 跨标准映射 (ICD-10, ICD-11, OMIM, UMLS, MeSH)

**Orphanet 文件说明**:
| 文件 | 内容 |
|------|------|
| en_product1.json | 11,456 种罕见病 + 跨标准映射 |
| en_product3_187.xml | 罕见皮肤病层级分类 (1,234 种) |
| en_product4.xml | HPO 表型-疾病注释 (4,337 种病) |
| en_product6.xml | 基因-疾病关联 (4,128 种病, 8,374 基因) |

### 1.8 Derm1M（图像-文本数据集）

- **来源**: Derm1M v2 预训练数据集
- **本地文件**: `data/Derm1M_v2_pretrain.csv` (413,210 条)
- **贡献**:
  - 图像挂载到知识图谱: **207,941 张** → **973 个疾病节点**
  - 挂载率: 50.3%
  - 未映射标签: 19,137 个（保存在 `output/derm1m_unmapped_labels.txt`）

### 1.9 已下载但尚未深度整合的资源

| 资源 | 文件 | 说明 | 后续用途 |
|------|------|------|----------|
| DEVO | `data/devo.owl` (174KB) | 皮肤镜特征本体, 317 OWL classes | 标准化 skin_concept 列 |
| D3X | `data/d3x.owl` (73KB) | 皮肤镜鉴别诊断本体, ~1,519 classes | 生成鉴别诊断关系 |
| MONDO | `data/mondo.obo` (49MB) | 统一疾病本体, 52,555 概念 | 跨本体实体对齐枢纽 |

---

## 2. 构建方式

### 2.1 整体流水线

```
Phase 1: ICD-11 核心骨架
  icd11_foundation.obo → 解析 OBO → BFS 皮肤子树 (5,216 节点)
  ICD-11-MMS.xlsx → 筛选 11 章节 → 三重策略提取 (1,805 条)
  合并 → 5,717 核心节点 + 7,496 条 is_a/mms_parent 边

Phase 2: 外部本体语义丰富
  dermo.obo → 名称匹配 → 注入 SNOMED/OMIM/ICD10 映射 + 补充定义
  hp.obo → 提取皮肤分支 → 添加 1,094 表型节点
  doid.obo → 皮肤分支匹配 → 注入 UMLS/MeSH 映射

Phase 3: 罕见病数据
  RSDB CSVs → 名称/别名匹配 → 注入表型(8,618) + 药物(1,628)
  Orphanet XML → 名称匹配 → 注入 OrphaCode

Phase 4: 图像数据挂载
  Derm1M CSV → disease_label 名称匹配 + icd11_mapping 辅助 → 207,941 张图像挂载

Phase 5: 边构建 + 输出
  14 种边类型 → JSON + CSV + 统计
```

### 2.2 实体对齐方法

跨数据源的实体对齐采用**名称匹配**为主：

```python
1. 标准化: 小写 + 去标点 + 合并空格
   "Epidermolysis Bullosa, Simplex" → "epidermolysis bullosa simplex"

2. 构建名称索引:
   对每个 ICD-11 节点: 索引 (疾病名, 所有同义词) → node_id

3. 匹配优先级:
   a) 精确名称匹配
   b) 同义词匹配
   c) 别名/alias 匹配 (RSDB)
   d) 已有映射表 (disease_icd11_mapping.json)
```

**匹配率统计**:
| 数据源 | 总概念数 | 匹配数 | 匹配率 |
|--------|----------|--------|--------|
| DermO | 3,401 | 889 | 26.1% |
| DOID 皮肤分支 | 586 | 234 | 37.0% |
| RSDB | 891 | 407 | 45.7% |
| Orphanet 皮肤分类 | 1,234 | 93 | 7.5% |
| Derm1M | 413,210 图像 | 207,941 | 50.3% |

**未匹配原因分析**:
- DermO (74% 未匹配): DermO 包含大量 ICD-11 未收录的细粒度概念 (1,773 个独有术语)
- Orphanet (92% 未匹配): 罕见病名称差异大，很多超罕见疾病在 ICD-11 中无对应
- Derm1M (50% 未匹配): 大量标签来自论坛/YouTube，是非标准文本

---

## 3. 节点类型

| 类型 | 来源 | 数量 | 说明 |
|------|------|------|------|
| `foundation` | ICD-11 Foundation 皮肤子树 | 3,912 | 只在 Foundation 中，MMS 未编码 |
| `foundation+mms` | Foundation + MMS 均有 | 1,304 | 最完整：有编码+定义+中文名 |
| `mms_only` | 仅在 MMS 中 | 462 | MMS 残余类别，Foundation 无对应 |
| `hpo` | HPO 皮肤表型分支 | 1,094 | 表型/症状节点（非疾病） |
| **合计** | | **6,811** | |

### 节点属性清单

```json
{
  "id":          "icd11:63698555",           // 唯一标识
  "name":        "Psoriasis",                // 英文名称
  "definition":  "Psoriasis is a common...", // 英文定义 (来自 Foundation/DermO/DOID/RSDB)
  "synonyms":    ["Psoriasis vulgaris"],     // 同义词列表
  "mms_code":    "EA90",                     // ICD-11 MMS 编码
  "cn_name":     "银屑病",                   // 中文名称 (来自 MMS)
  "chapter":     "14",                       // MMS 所在章节
  "path_id":     "14.2.2.1",               // MMS Path ID (层级位置)
  "is_leaf":     false,                      // 是否叶节点
  "source":      "foundation+mms",           // 数据来源
  "dermo_id":    "DERMO:0001234",           // DermO 概念 ID
  "doid_id":     "DOID:8893",               // Disease Ontology ID
  "orpha_codes": ["ORPHA:xxx"],             // Orphanet 编码
  "rsdb_id":     "123",                     // RSDB 数据库 ID
  "snomed":      ["9014002"],               // SNOMED CT 概念 ID
  "omim":        ["177900"],                // OMIM 基因/表型编号
  "umls":        ["C0033860"],              // UMLS CUI
  "mesh":        ["D011565"],               // MeSH 描述符 ID
  "icd10":       ["L40"],                   // ICD-10 编码
  "hpo_pheno":   ["HP:0001234", "瘙痒"],    // HPO 表型 ID 或 RSDB 表型名
  "genes":       [],                         // 关联基因符号 (来自 RSDB)
  "drugs":       [],                         // 关联药物名 (来自 RSDB)
  "image_count": 5432,                      // Derm1M 中的图像数量
  "data_sources": ["ISIC", "pubmed"]        // 图像数据来源
}
```

---

## 4. 边类型

| 边类型 | 数量 | 说明 | 来源 |
|--------|------|------|------|
| `has_phenotype` | 8,696 | 疾病→表型/症状 | RSDB + DermO + HPO |
| `has_synonym` | 7,425 | 节点→同义词文本 | Foundation + DermO + DOID |
| `is_a` | 7,204 | 子类→父类（分类层级） | Foundation is_a |
| `has_mms_code` | 1,830 | 节点→ICD-11编码 | MMS |
| `mms_parent` | 1,474 | MMS 层级父子关系 | MMS Path ID |
| `xref_snomed` | 1,355 | →SNOMED CT 概念 | DermO + DOID |
| `xref_dermo` | 866 | →DermO 概念 | DermO 匹配 |
| `also_in_chapter` | 689 | 跨章节标记 | Foundation+MMS 桥接 |
| `xref_icd10` | 513 | →ICD-10 编码 | DermO + RSDB |
| `xref_umls` | 474 | →UMLS CUI | DOID + RSDB |
| `xref_orpha` | 450 | →Orphanet 编码 | RSDB + Orphanet |
| `xref_doid` | 425 | →Disease Ontology ID | DermO + DOID |
| `xref_omim` | 403 | →OMIM 编号 | DermO + DOID + RSDB |
| `xref_mesh` | 276 | →MeSH 描述符 | DOID + RSDB |
| **合计** | **32,080** | | |

---

## 5. 输出文件

| 文件 | 格式 | 大小 | 说明 |
|------|------|------|------|
| `output/skin_kg_v3.json` | JSON | 9.8 MB | 完整图谱 (metadata + nodes + edges) |
| `output/skin_kg_nodes_v3.csv` | CSV | ~2 MB | 节点属性表，pandas 可直接读取 |
| `output/skin_kg_triples_v3.csv` | CSV | ~1 MB | 三元组 (head, relation, tail) |
| `output/skin_kg_stats_v3.json` | JSON | ~2 KB | 统计信息 |
| `output/derm1m_unmapped_labels.txt` | TXT | ~500 KB | Derm1M 中未匹配的疾病标签 |

---

## 6. 构建脚本

| 脚本 | 说明 |
|------|------|
| `scripts/build_v1_icd11_only.py` | v1: 仅 ICD-11 Foundation + MMS |
| `scripts/build_v2_with_ontologies.py` | v2: + DermO + HPO + DOID |
| `scripts/build_v3_full.py` | **v3: 全量整合所有数据源（推荐使用）** |

运行方式：
```bash
cd /Users/chenlinwei/Documents/PaperProject/baichuan
python3 skin_kg_project/scripts/build_v3_full.py
```

---

## 7. 已知限制和改进方向

### 7.1 匹配率可提升
- DermO 匹配率只有 26%，可引入嵌入向量相似度匹配提升
- Derm1M 图像挂载率 50%，可用 `icd11_matcher_package` 工具提升
- Orphanet 匹配率 7.5%，可通过 OMIM/UMLS CUI 间接桥接

### 7.2 待整合资源
- **DEVO/D3X OWL**: 已下载，需 OWL 解析后整合皮肤镜特征
- **MONDO**: 可作为跨本体对齐枢纽，通过 SSSOM 映射补充
- **Orphanet 基因-疾病/HPO-疾病数据**: 已下载 (product4, product6)，可增加基因和表型关联
- **RSDB compound-gene**: 可通过间接关联补充基因信息
- **MeSH RDF**: 可增加 PubMed 文献关联

### 7.3 缺失的关系类型
当前图谱缺少以下对诊断至关重要的关系，可后续补充：
- `differential_diagnosis`: 鉴别诊断（可通过形态/部位重叠自动推理）
- `has_morphology`: 形态学表现（需标准化到 DEVO 术语）
- `has_site`: 好发部位（可从 Derm1M body_location 列提取）
- `has_etiology`: 病因分类
- `has_treatment`: 治疗方案（RSDB 药物关联是基础）

---

## 8. 使用示例

### 加载图谱

```python
import json, pandas as pd

# 方式1: 加载完整 JSON
with open('output/skin_kg_v3.json', 'r') as f:
    kg = json.load(f)
nodes = {n['id']: n for n in kg['nodes']}
edges = kg['edges']
print(f"节点: {len(nodes)}, 边: {len(edges)}")

# 方式2: 加载节点 CSV (轻量)
df = pd.read_csv('output/skin_kg_nodes_v3.csv')
# 查找银屑病
psoriasis = df[df['name'] == 'Psoriasis']

# 方式3: 加载三元组
triples = pd.read_csv('output/skin_kg_triples_v3.csv')
# 查找银屑病的所有关系
ps_edges = triples[triples['head'].str.contains('63698555')]
```

### 查询示例

```python
# 查找某疾病的所有表型
disease_id = 'icd11:63698555'  # Psoriasis
phenotypes = [e['target'] for e in edges if e['source'] == disease_id and e['relation'] == 'has_phenotype']

# 查找有图像数据的叶节点疾病
with_images = df[(df['image_count'] > 0) & (df['is_leaf'] == True)]

# 查找有 SNOMED 映射的疾病
with_snomed = df[df['snomed'].notna() & (df['snomed'] != '')]
```
