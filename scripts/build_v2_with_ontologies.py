#!/usr/bin/env python3
"""
皮肤病知识图谱 v2 — 整合全部外部本体
====================================
在 v1 (ICD-11 Foundation + MMS) 基础上，整合:
  - DermO:  3,401 个皮肤病概念 + SNOMED/DOID/ICD10/OMIM 交叉引用
  - HPO:    1,094 个皮肤/毛发/指甲表型（症状/体征）
  - DOID:   586 个皮肤病 + UMLS CUI + SNOMED + MeSH 映射
  - DEVO:   皮肤镜特征本体 (OWL, 待后续整合)
  - D3X:    皮肤镜鉴别诊断本体 (OWL, 待后续整合)
"""

import json
import re
import csv
import pandas as pd
from collections import defaultdict, deque
from pathlib import Path
from difflib import SequenceMatcher

BASE = Path("/Users/chenlinwei/Documents/PaperProject/baichuan")
OBO_PATH = BASE / "ICD-11" / "foundation" / "icd11.obo"
MMS_PATH = BASE / "ICD-11" / "ICD-11-with-PathID.xlsx"
EXT_DIR = BASE / "ICD-11" / "foundation" / "external_ontologies"
OUT_DIR = BASE / "dataset" / "skin_knowledge_graph"
OUT_DIR.mkdir(exist_ok=True)

TARGET_CHAPTERS = ['01', '02', '03', '04', '05', '13', '14', '19', '20', '21', '22']

SKIN_KEYWORDS = [
    r'\bskin\b', r'cutaneous', r'dermat', r'epider', r'subcutan',
    r'melanom', r'melanocyt', r'\bnevus\b', r'\bnaevus\b', r'\bnevi\b', r'\bnaevi\b',
    r'pigment', r'depigment', r'vitiligo', r'albinism',
    r'alopecia', r'hair loss', r'hirsut', r'hypertrichos',
    r'\bnail\b', r'onych', r'paronych',
    r'pemphig', r'urticaria', r'erythema\b', r'pruritus', r'prurigo',
    r'psoriasis', r'eczema', r'\bacne\b', r'rosacea', r'lichen',
    r'bullous', r'blister', r'\brash\b', r'exanthem',
    r'angioedema', r'vasculitis', r'purpura',
    r'lupus.*skin\b|cutaneous.*lupus', r'scleroderma', r'dermatomyositis', r'morphea',
    r'photosensit', r'photodermat',
    r'\bherpes\b', r'\btinea\b', r'\bscabies\b', r'cellulitis',
    r'\bwart\b', r'\bwarts\b', r'verruca', r'impetigo', r'follicul',
    r'mycosis.*skin|cutaneous.*mycosis', r'fungal.*skin|skin.*fungal',
    r'kaposi', r'basal cell', r'squamous cell.*skin|cutaneous.*squamous',
    r'\bmerkel\b', r"bowen", r'keratoacanthoma',
    r'burn of', r'burn.*skin', r'frostbite', r'sunburn', r'decubitus',
    r'pressure sore', r'pressure ulcer', r'wound.*skin|skin.*wound',
    r'\bscar\b', r'keloid', r'cicatri',
    r'sebaceous', r'sweat gland', r'eccrine', r'apocrine',
    r'ichthyosis', r'keratosis', r'xeroderma', r'epidermolysis',
    r'keratoderma', r'porokeratosis',
    r'birthmark', r'haemangioma', r'hemangioma', r'port.wine',
]
SKIN_PATTERN = re.compile('|'.join(SKIN_KEYWORDS), re.IGNORECASE)


# ============================================================
# 通用 OBO 解析器
# ============================================================
def parse_obo(path):
    terms = {}
    current = None
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.rstrip('\n').strip()
            if stripped == '[Term]':
                current = {}
            elif stripped == '' and current is not None:
                if 'id' in current:
                    terms[current['id']] = current
                current = None
            elif current is not None:
                if stripped.startswith('id: '):
                    current['id'] = stripped[4:]
                elif stripped.startswith('name: '):
                    current['name'] = stripped[6:].replace('\\,', ',').replace('\\(', '(').replace('\\)', ')')
                elif stripped.startswith('def: '):
                    m = re.match(r'def: "(.*)"', stripped)
                    if m:
                        current['def'] = m.group(1).replace('\\,', ',').replace('\\(', '(').replace('\\)', ')')
                elif stripped.startswith('is_a: '):
                    parent = stripped[6:].split(' !')[0].strip()
                    current.setdefault('parents', []).append(parent)
                elif stripped.startswith('synonym: '):
                    m = re.match(r'synonym: "(.*?)"', stripped)
                    if m:
                        current.setdefault('synonyms', []).append(m.group(1).replace('\\,', ','))
                elif stripped.startswith('xref: '):
                    current.setdefault('xrefs', []).append(stripped[6:])
                elif stripped.startswith('property_value: skos:exactMatch '):
                    code = stripped.split('skos:exactMatch ')[1].strip()
                    current['mms_code'] = code
                elif stripped.startswith('is_obsolete: true'):
                    current['obsolete'] = True
    if current and 'id' in current:
        terms[current['id']] = current
    return {k: v for k, v in terms.items() if not v.get('obsolete')}


def build_subtree(terms, root_id):
    children_map = defaultdict(list)
    for tid, t in terms.items():
        for p in t.get('parents', []):
            children_map[p].append(tid)
    queue = deque([root_id])
    visited = set()
    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        for child in children_map.get(node, []):
            queue.append(child)
    return visited, children_map


def normalize_name(name):
    """标准化疾病名称用于匹配"""
    n = name.lower().strip()
    n = re.sub(r'[,;()\[\]{}\'"]', '', n)
    n = re.sub(r'\s+', ' ', n)
    return n


# ============================================================
# Step 1: 解析 ICD-11 Foundation
# ============================================================
print("=" * 60)
print("Step 1: 解析 ICD-11 Foundation ...")
icd11 = parse_obo(str(OBO_PATH))
print("  Foundation 总实体: %d" % len(icd11))

skin_ids, icd11_children = build_subtree(icd11, 'icd11:1639304259')
print("  皮肤子树: %d" % len(skin_ids))

skin_entity_numbers = set(fid.replace('icd11:', '') for fid in skin_ids)


# ============================================================
# Step 2: 解析 MMS
# ============================================================
print("\nStep 2: 解析 MMS ...")
mms_df = pd.read_excel(MMS_PATH)

def extract_entity_number(uri):
    if pd.isna(uri): return None
    uri = str(uri)
    return uri.split('/entity/')[-1] if '/entity/' in uri else None

mms_df['entity_number'] = mms_df['Foundation URI'].apply(extract_entity_number)
target_df = mms_df[mms_df['ChapterNo'].astype(str).isin(TARGET_CHAPTERS)].copy()

ch14_mask = target_df['ChapterNo'].astype(str) == '14'
foundation_bridge = target_df['entity_number'].isin(skin_entity_numbers) & ~ch14_mask
keyword_match = target_df['Title'].astype(str).apply(lambda x: bool(SKIN_PATTERN.search(x))) & ~ch14_mask
skin_mms_df = target_df[ch14_mask | foundation_bridge | keyword_match].copy()
print("  皮肤相关 MMS: %d" % len(skin_mms_df))


# ============================================================
# Step 3: 构建核心节点 (Foundation + MMS)
# ============================================================
print("\nStep 3: 构建核心节点 ...")
nodes = {}
edges = []

# Foundation 皮肤子树
for fid in skin_ids:
    t = icd11.get(fid, {})
    mms_code = t.get('mms_code', '').replace('icd11.code:', '') if t.get('mms_code', '').startswith('icd11.code:') else ''
    nodes[fid] = {
        'id': fid,
        'entity_number': fid.replace('icd11:', ''),
        'name': t.get('name', ''),
        'name_normalized': normalize_name(t.get('name', '')),
        'definition': t.get('def', ''),
        'synonyms': t.get('synonyms', []),
        'mms_code': mms_code,
        'cn_name': '',
        'chapter': '14',
        'path_id': '',
        'is_leaf_foundation': len(icd11_children.get(fid, [])) == 0,
        'source': 'foundation',
        'parents_foundation': t.get('parents', []),
        # 外部本体映射 (后续填充)
        'dermo_id': '',
        'dermo_name': '',
        'doid_id': '',
        'hpo_phenotypes': [],
        'snomed_ids': [],
        'omim_ids': [],
        'umls_cuis': [],
        'mesh_ids': [],
        'icd10_codes': [],
    }

# MMS 丰富 / 新增
for _, row in skin_mms_df.iterrows():
    ent_num = row.get('entity_number')
    node_id = ('icd11:' + str(ent_num)) if ent_num else None
    title = str(row.get('Title', '')).strip('" -').strip()
    code = str(row.get('Code', '')) if pd.notna(row.get('Code')) else ''
    cn_name = str(row.get('中文名称', '')) if pd.notna(row.get('中文名称')) else ''
    path_id = str(row.get('Path ID', '')) if pd.notna(row.get('Path ID')) else ''
    chapter = str(row.get('ChapterNo', ''))

    if node_id and node_id in nodes:
        n = nodes[node_id]
        if code and not n['mms_code']: n['mms_code'] = code
        if cn_name: n['cn_name'] = cn_name
        if path_id: n['path_id'] = path_id
        n['chapter'] = chapter
        n['source'] = 'foundation+mms'
        if not n['name'] and title: n['name'] = title
    else:
        new_id = node_id if node_id else ('mms:' + (code or 'path:' + path_id))
        if new_id not in nodes:
            nodes[new_id] = {
                'id': new_id, 'entity_number': ent_num or '',
                'name': title, 'name_normalized': normalize_name(title),
                'definition': '', 'synonyms': [], 'mms_code': code,
                'cn_name': cn_name, 'chapter': chapter, 'path_id': path_id,
                'is_leaf_foundation': True, 'source': 'mms_only',
                'parents_foundation': [],
                'dermo_id': '', 'dermo_name': '', 'doid_id': '',
                'hpo_phenotypes': [], 'snomed_ids': [], 'omim_ids': [],
                'umls_cuis': [], 'mesh_ids': [], 'icd10_codes': [],
            }

print("  核心节点: %d" % len(nodes))

# Foundation is_a 边
for nid, n in nodes.items():
    for pid in n.get('parents_foundation', []):
        if pid in nodes:
            edges.append((nid, 'is_a', pid))

# MMS 层级边
path_to_node = {n['path_id']: nid for nid, n in nodes.items() if n['path_id']}
for nid, n in nodes.items():
    pid = n['path_id']
    if pid and '.' in pid:
        parent_path = '.'.join(pid.split('.')[:-1])
        parent_nid = path_to_node.get(parent_path)
        if parent_nid and parent_nid != nid:
            edges.append((nid, 'mms_parent', parent_nid))

print("  核心边: %d" % len(edges))


# ============================================================
# Step 4: 整合 DermO
# ============================================================
print("\nStep 4: 整合 DermO (3,401 概念) ...")
dermo = parse_obo(str(EXT_DIR / "dermo.obo"))

# 构建 ICD-11 名称索引 (name → node_id)
name_to_icd = {}
for nid, n in nodes.items():
    nn = n['name_normalized']
    if nn:
        name_to_icd[nn] = nid
    for syn in n.get('synonyms', []):
        name_to_icd[normalize_name(syn)] = nid

# 匹配 DermO → ICD-11
dermo_matched = 0
dermo_xrefs_added = 0

for did, dt in dermo.items():
    dname = normalize_name(dt.get('name', ''))
    matched_nid = None

    # 策略1: 精确名称匹配
    if dname in name_to_icd:
        matched_nid = name_to_icd[dname]
    else:
        # 策略2: DermO 同义词匹配
        for syn in dt.get('synonyms', []):
            sn = normalize_name(syn)
            if sn in name_to_icd:
                matched_nid = name_to_icd[sn]
                break

    if matched_nid:
        nodes[matched_nid]['dermo_id'] = did
        nodes[matched_nid]['dermo_name'] = dt.get('name', '')
        dermo_matched += 1

        # 提取 DermO 的交叉引用
        for xref in dt.get('xrefs', []):
            if xref.startswith('SNOMEDCT'):
                sctid = xref.split(':')[-1].strip()
                if sctid not in nodes[matched_nid]['snomed_ids']:
                    nodes[matched_nid]['snomed_ids'].append(sctid)
                    dermo_xrefs_added += 1
            elif xref.startswith('OMIM:'):
                omim_id = xref.split(':')[-1].strip()
                if omim_id not in nodes[matched_nid]['omim_ids']:
                    nodes[matched_nid]['omim_ids'].append(omim_id)
                    dermo_xrefs_added += 1
            elif xref.startswith('ICD10:'):
                icd10 = xref.split(':')[-1].strip()
                if icd10 not in nodes[matched_nid]['icd10_codes']:
                    nodes[matched_nid]['icd10_codes'].append(icd10)
                    dermo_xrefs_added += 1
            elif xref.startswith('HP:'):
                if xref not in nodes[matched_nid]['hpo_phenotypes']:
                    nodes[matched_nid]['hpo_phenotypes'].append(xref)
                    dermo_xrefs_added += 1
            elif xref.startswith('DOID:'):
                if not nodes[matched_nid]['doid_id']:
                    nodes[matched_nid]['doid_id'] = xref
                    dermo_xrefs_added += 1

        # DermO 的定义补充 (如果 ICD-11 没有)
        if not nodes[matched_nid]['definition'] and dt.get('def'):
            nodes[matched_nid]['definition'] = dt['def']

        # DermO 的同义词补充
        for syn in dt.get('synonyms', []):
            if syn not in nodes[matched_nid]['synonyms']:
                nodes[matched_nid]['synonyms'].append(syn)

print("  DermO→ICD-11 匹配: %d / %d (%.1f%%)" % (dermo_matched, len(dermo), 100*dermo_matched/len(dermo)))
print("  新增交叉引用: %d" % dermo_xrefs_added)


# ============================================================
# Step 5: 整合 HPO (皮肤表型)
# ============================================================
print("\nStep 5: 整合 HPO 皮肤表型 (1,094 个) ...")
hpo = parse_obo(str(EXT_DIR / "hp.obo"))
integument_ids, hpo_children = build_subtree(hpo, 'HP:0001574')

# 为每个 HPO 皮肤表型创建节点
hpo_added = 0
for hid in integument_ids:
    ht = hpo.get(hid, {})
    node_id = 'hpo:' + hid
    if node_id not in nodes:
        nodes[node_id] = {
            'id': node_id, 'entity_number': hid,
            'name': ht.get('name', ''), 'name_normalized': normalize_name(ht.get('name', '')),
            'definition': ht.get('def', ''), 'synonyms': ht.get('synonyms', []),
            'mms_code': '', 'cn_name': '', 'chapter': 'HPO', 'path_id': '',
            'is_leaf_foundation': len(hpo_children.get(hid, [])) == 0,
            'source': 'hpo',
            'parents_foundation': [],
            'dermo_id': '', 'dermo_name': '', 'doid_id': '',
            'hpo_phenotypes': [], 'snomed_ids': [], 'omim_ids': [],
            'umls_cuis': [], 'mesh_ids': [], 'icd10_codes': [],
        }
        hpo_added += 1
        # HPO 内部 is_a 边
        for pid in ht.get('parents', []):
            parent_nid = 'hpo:' + pid
            if parent_nid in nodes or pid in integument_ids:
                edges.append((node_id, 'is_a', parent_nid))

# 尝试将 HPO 表型关联到疾病节点 (通过名称匹配)
hpo_linked = 0
for nid, n in list(nodes.items()):
    if n['source'] in ('hpo',):
        continue
    # 检查疾病节点的 hpo_phenotypes 列表
    for hp_id in n.get('hpo_phenotypes', []):
        hp_node = 'hpo:' + hp_id
        if hp_node in nodes:
            edges.append((nid, 'has_phenotype', hp_node))
            hpo_linked += 1

print("  新增 HPO 表型节点: %d" % hpo_added)
print("  疾病→表型关联边: %d" % hpo_linked)


# ============================================================
# Step 6: 整合 DOID (皮肤病分支)
# ============================================================
print("\nStep 6: 整合 DOID 皮肤病分支 ...")
doid = parse_obo(str(EXT_DIR / "doid.obo"))
skin_doid_ids, _ = build_subtree(doid, 'DOID:37')

doid_matched = 0
doid_xrefs_added = 0

for did in skin_doid_ids:
    dt = doid.get(did, {})
    dname = normalize_name(dt.get('name', ''))
    matched_nid = None

    if dname in name_to_icd:
        matched_nid = name_to_icd[dname]
    else:
        for syn in dt.get('synonyms', []):
            sn = normalize_name(syn)
            if sn in name_to_icd:
                matched_nid = name_to_icd[sn]
                break

    if matched_nid:
        doid_matched += 1
        if not nodes[matched_nid]['doid_id']:
            nodes[matched_nid]['doid_id'] = did

        for xref in dt.get('xrefs', []):
            if xref.startswith('UMLS_CUI:'):
                cui = xref.split(':')[-1].strip()
                if cui not in nodes[matched_nid]['umls_cuis']:
                    nodes[matched_nid]['umls_cuis'].append(cui)
                    doid_xrefs_added += 1
            elif xref.startswith('MESH:'):
                mesh = xref.split(':')[-1].strip()
                if mesh not in nodes[matched_nid]['mesh_ids']:
                    nodes[matched_nid]['mesh_ids'].append(mesh)
                    doid_xrefs_added += 1
            elif xref.startswith('SNOMEDCT'):
                sctid = xref.split(':')[-1].strip()
                if sctid not in nodes[matched_nid]['snomed_ids']:
                    nodes[matched_nid]['snomed_ids'].append(sctid)
                    doid_xrefs_added += 1
            elif xref.startswith('ICD10CM:') or xref.startswith('ICD9CM:'):
                icd = xref.split(':')[-1].strip()
                if icd not in nodes[matched_nid]['icd10_codes']:
                    nodes[matched_nid]['icd10_codes'].append(icd)
                    doid_xrefs_added += 1
            elif xref.startswith('MIM:'):
                omim = xref.split(':')[-1].strip()
                if omim not in nodes[matched_nid]['omim_ids']:
                    nodes[matched_nid]['omim_ids'].append(omim)
                    doid_xrefs_added += 1

        # 补充定义
        if not nodes[matched_nid]['definition'] and dt.get('def'):
            nodes[matched_nid]['definition'] = dt['def']
        # 补充同义词
        for syn in dt.get('synonyms', []):
            if syn not in nodes[matched_nid]['synonyms']:
                nodes[matched_nid]['synonyms'].append(syn)

print("  DOID→ICD-11 匹配: %d / %d (%.1f%%)" % (doid_matched, len(skin_doid_ids), 100*doid_matched/len(skin_doid_ids)))
print("  新增交叉引用: %d" % doid_xrefs_added)


# ============================================================
# Step 7: 补充边
# ============================================================
print("\nStep 7: 补充关系边 ...")

# 跨章节标记
cross_ch = 0
for nid, n in nodes.items():
    if n['chapter'] not in ('14', 'HPO', '') and n['source'] == 'foundation+mms':
        edges.append((nid, 'also_classified_in_chapter', 'chapter:' + n['chapter']))
        cross_ch += 1

# 同义词边
syn_edges = 0
for nid, n in nodes.items():
    for syn in n.get('synonyms', []):
        edges.append((nid, 'has_synonym', 'syn:' + syn))
        syn_edges += 1

# 编码关系边
code_edges = 0
for nid, n in nodes.items():
    if n['mms_code']:
        edges.append((nid, 'has_mms_code', 'code:' + n['mms_code']))
        code_edges += 1

# 外部 ID 映射边
xref_edges = 0
for nid, n in nodes.items():
    for sid in n.get('snomed_ids', []):
        edges.append((nid, 'mapped_to_snomed', 'SCTID:' + sid))
        xref_edges += 1
    for oid in n.get('omim_ids', []):
        edges.append((nid, 'mapped_to_omim', 'OMIM:' + oid))
        xref_edges += 1
    for cui in n.get('umls_cuis', []):
        edges.append((nid, 'mapped_to_umls', 'UMLS:' + cui))
        xref_edges += 1
    for mid in n.get('mesh_ids', []):
        edges.append((nid, 'mapped_to_mesh', 'MeSH:' + mid))
        xref_edges += 1
    if n.get('dermo_id'):
        edges.append((nid, 'mapped_to_dermo', n['dermo_id']))
        xref_edges += 1
    if n.get('doid_id'):
        edges.append((nid, 'mapped_to_doid', n['doid_id']))
        xref_edges += 1

print("  跨章节: %d, 同义词: %d, 编码: %d, 外部映射: %d" % (cross_ch, syn_edges, code_edges, xref_edges))
print("  总边数: %d" % len(edges))


# ============================================================
# Step 8: 统计并输出
# ============================================================
print("\nStep 8: 输出 ...")

stats = {
    'total_nodes': len(nodes),
    'total_edges': len(edges),
    'nodes_with_definition': sum(1 for n in nodes.values() if n['definition']),
    'nodes_with_synonyms': sum(1 for n in nodes.values() if n['synonyms']),
    'nodes_with_mms_code': sum(1 for n in nodes.values() if n['mms_code']),
    'nodes_with_cn_name': sum(1 for n in nodes.values() if n['cn_name']),
    'nodes_with_snomed': sum(1 for n in nodes.values() if n.get('snomed_ids')),
    'nodes_with_omim': sum(1 for n in nodes.values() if n.get('omim_ids')),
    'nodes_with_umls_cui': sum(1 for n in nodes.values() if n.get('umls_cuis')),
    'nodes_with_mesh': sum(1 for n in nodes.values() if n.get('mesh_ids')),
    'nodes_with_dermo': sum(1 for n in nodes.values() if n.get('dermo_id')),
    'nodes_with_doid': sum(1 for n in nodes.values() if n.get('doid_id')),
    'nodes_with_hpo_phenotypes': sum(1 for n in nodes.values() if n.get('hpo_phenotypes')),
    'source_distribution': defaultdict(int),
    'chapter_distribution': defaultdict(int),
}
for n in nodes.values():
    stats['source_distribution'][n['source']] += 1
    stats['chapter_distribution'][n.get('chapter', 'none')] += 1
stats['source_distribution'] = dict(stats['source_distribution'])
stats['chapter_distribution'] = dict(stats['chapter_distribution'])

# 边类型统计
edge_types = defaultdict(int)
for e in edges:
    edge_types[e[1]] += 1
stats['edge_type_distribution'] = dict(edge_types)

# --- 输出 JSON ---
nodes_list = []
for nid, n in nodes.items():
    out = {k: v for k, v in n.items() if k not in ('parents_foundation', 'name_normalized')}
    nodes_list.append(out)

kg = {
    'metadata': stats,
    'nodes': nodes_list,
    'edges': [{'source': e[0], 'relation': e[1], 'target': e[2]} for e in edges],
}

out_json = OUT_DIR / "skin_kg_full_v2.json"
with open(out_json, 'w', encoding='utf-8') as f:
    json.dump(kg, f, ensure_ascii=False, indent=2)
print("  %s (%.1f MB)" % (out_json.name, out_json.stat().st_size / 1e6))

# --- 三元组 CSV ---
out_triples = OUT_DIR / "skin_kg_triples_v2.csv"
with open(out_triples, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['head', 'relation', 'tail'])
    for e in edges:
        writer.writerow(e)
print("  %s (%d 行)" % (out_triples.name, len(edges)))

# --- 节点 CSV ---
out_nodes = OUT_DIR / "skin_kg_nodes_v2.csv"
rows = []
for nid, n in nodes.items():
    rows.append({
        'id': n['id'], 'name': n['name'],
        'definition': (n['definition'] or '')[:500],
        'synonyms': ' | '.join(n.get('synonyms', [])),
        'mms_code': n['mms_code'], 'cn_name': n['cn_name'],
        'chapter': n['chapter'], 'path_id': n['path_id'],
        'source': n['source'],
        'dermo_id': n.get('dermo_id', ''),
        'doid_id': n.get('doid_id', ''),
        'snomed_ids': ';'.join(n.get('snomed_ids', [])),
        'omim_ids': ';'.join(n.get('omim_ids', [])),
        'umls_cuis': ';'.join(n.get('umls_cuis', [])),
        'mesh_ids': ';'.join(n.get('mesh_ids', [])),
        'icd10_codes': ';'.join(n.get('icd10_codes', [])),
        'hpo_phenotypes': ';'.join(n.get('hpo_phenotypes', [])),
        'num_synonyms': len(n.get('synonyms', [])),
        'has_definition': bool(n['definition']),
        'is_leaf': n['is_leaf_foundation'],
    })
pd.DataFrame(rows).to_csv(out_nodes, index=False, encoding='utf-8')
print("  %s (%d 行)" % (out_nodes.name, len(rows)))

# --- Stats JSON ---
out_stats = OUT_DIR / "skin_kg_stats_v2.json"
with open(out_stats, 'w', encoding='utf-8') as f:
    json.dump(stats, f, ensure_ascii=False, indent=2)
print("  %s" % out_stats.name)

# ============================================================
# 最终报告
# ============================================================
print("\n" + "=" * 60)
print("皮肤病知识图谱 v2 构建完成!")
print("=" * 60)
print("\n节点统计 (总计 %d):" % stats['total_nodes'])
print("  有定义文本:    %5d (%.1f%%)" % (stats['nodes_with_definition'], 100*stats['nodes_with_definition']/stats['total_nodes']))
print("  有同义词:      %5d (%.1f%%)" % (stats['nodes_with_synonyms'], 100*stats['nodes_with_synonyms']/stats['total_nodes']))
print("  有 MMS 编码:   %5d" % stats['nodes_with_mms_code'])
print("  有中文名称:    %5d" % stats['nodes_with_cn_name'])
print("  有 SNOMED ID:  %5d" % stats['nodes_with_snomed'])
print("  有 OMIM ID:    %5d" % stats['nodes_with_omim'])
print("  有 UMLS CUI:   %5d" % stats['nodes_with_umls_cui'])
print("  有 MeSH ID:    %5d" % stats['nodes_with_mesh'])
print("  有 DermO 映射: %5d" % stats['nodes_with_dermo'])
print("  有 DOID 映射:  %5d" % stats['nodes_with_doid'])
print("  有 HPO 表型:   %5d" % stats['nodes_with_hpo_phenotypes'])

print("\n来源分布:")
for src, cnt in sorted(stats['source_distribution'].items()):
    print("  %-20s %d" % (src, cnt))

print("\n边类型分布 (总计 %d):" % len(edges))
for etype, cnt in sorted(edge_types.items(), key=lambda x: -x[1]):
    print("  %-30s %d" % (etype, cnt))

print("\n输出目录: %s" % OUT_DIR)
