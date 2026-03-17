# 数据源获取指南

本文档记录所有数据源的原始获取方式，确保可复现。

---

## 1. ICD-11 Foundation (OBO 格式)

```bash
# 来源: Biopragmatics / Bioregistry 预构建文件
wget -O icd11_foundation.obo "https://w3id.org/biopragmatics/resources/icd11/icd11.obo"
wget -O icd11_foundation.json "https://w3id.org/biopragmatics/resources/icd11/icd11.json"

# 也可用 Python:
# pip install bioregistry
# import bioregistry as br
# print(br.get_obo_download("icd11"))
```

- 许可证: CC-BY-ND-3.0-IGO
- 备注: 此文件由 PyOBO 从 WHO ICD-API 自动转换生成，可能不是最新版
- 最新版获取: 需通过 WHO ICD-API (https://icd.who.int/icdapi)

## 2. ICD-11 MMS (Excel)

```
来源: WHO 官方下载页
URL: https://icd.who.int/dev11/downloads
需要: WHO 账号登录
文件: LinearizationMiniOutput-MMS-en.xlsx
后处理: 添加了 Path ID 列和中文名称列 → ICD-11-with-PathID.xlsx
```

## 3. DermO

```bash
# 来源: GitHub
wget -O dermo.obo "https://raw.githubusercontent.com/dermatology-ontology/dermatology/master/dermatology.obo"
# OWL 版本:
wget -O dermo.owl "https://raw.githubusercontent.com/dermatology-ontology/dermatology/master/dermatology.owl"
```

- GitHub: https://github.com/dermatology-ontology/dermatology
- 论文: Fisher et al. (2016), J Biomed Semantics, DOI:10.1186/s13326-016-0085-x
- 最后更新: 2016-05-27 (未维护)

## 4. HPO

```bash
wget -O hp.obo "http://purl.obolibrary.org/obo/hp.obo"
```

- 官网: https://hpo.jax.org/
- GitHub: https://github.com/obophenotype/human-phenotype-ontology
- 许可证: 学术免费

## 5. DOID

```bash
wget -O doid.obo "http://purl.obolibrary.org/obo/doid.obo"
```

- 官网: https://disease-ontology.org/
- GitHub: https://github.com/DiseaseOntology/HumanDiseaseOntology
- 许可证: CC0 1.0

## 6. MONDO

```bash
wget -O mondo.obo "http://purl.obolibrary.org/obo/mondo.obo"
```

- 官网: https://mondo.monarchinitiative.org/
- GitHub: https://github.com/monarch-initiative/mondo
- 许可证: CC BY 4.0

## 7. DEVO

```bash
wget -O devo.owl "https://raw.githubusercontent.com/UTHealth-Ontology/DEVO/main/devo.owl"
```

- GitHub: https://github.com/UTHealth-Ontology/DEVO
- 论文: Zhang et al. (2023), BMC Med Inform Decis Making, DOI:10.1186/s12911-023-02251-y

## 8. D3X

```bash
wget -O d3x.owl "https://raw.githubusercontent.com/UTHealth-Ontology/D3X/main/ontology/d3x.owl"
wget -O d3x_images.xlsx "https://raw.githubusercontent.com/UTHealth-Ontology/D3X/main/data/DDX_image_collection.xlsx"
```

- GitHub: https://github.com/UTHealth-Ontology/D3X
- 论文: Lin et al. (2024), JMIR Med Inform, DOI:10.2196/49613
- 注意: d3x.owl 存在 RDF/XML 兼容问题，rdflib 无法直接解析

## 9. RSDB

```bash
# 来源: Figshare
# URL: https://figshare.com/articles/dataset/Rare_Skin_Disease_Database/17704502
# 通过 Figshare API 下载全部 21 个 CSV 文件:
curl -s "https://api.figshare.com/v2/articles/17704502/files" | \
  python3 -c "import sys,json; [print(f['download_url']) for f in json.load(sys.stdin)]" | \
  xargs -I {} wget -P rsdb/ {}
```

- 论文: Nature Scientific Data (2022), DOI:10.1038/s41597-022-01654-2
- 许可证: CC BY-NC-SA 4.0
- GitHub: https://github.com/CMDM-Lab/rsdb_publication

## 10. Orphanet

```bash
mkdir -p orphanet && cd orphanet
# 罕见皮肤病分类
wget "https://www.orphadata.com/data/xml/en_product3_187.xml"
# 全部罕见病命名 + 跨标准映射
wget "https://www.orphadata.com/data/json/en_product1.json"
# HPO 疾病-表型注释
wget "https://www.orphadata.com/data/xml/en_product4.xml"
# 基因-疾病关联
wget "https://www.orphadata.com/data/xml/en_product6.xml"
# 流行病学/发病年龄
wget "https://www.orphadata.com/data/xml/en_product9_ages.xml"
# 遗传病分类
wget "https://www.orphadata.com/data/xml/en_product3_156.xml"
```

- 官网: https://www.orphadata.com/
- 许可证: CC BY 4.0
- 更新频率: 月度

## 11. Derm1M

```
来源: 项目内部数据集
文件: Derm1M_v2_pretrain.csv
行数: 413,210 条图像-文本对
列: filename, caption, disease_label, hierarchical_disease_label,
    skin_concept, body_location, symptoms, age, gender
```

- HuggingFace: https://huggingface.co/datasets/redlessone/Derm1M
- 论文: Yan et al. (2025), ICCV Highlight
- 许可证: CC BY-NC 4.0
