#!/usr/bin/env python3
"""
全面皮肤病知识图谱构建脚本
=========================
数据来源:
  1. ICD-11 Foundation (OBO) — 提供定义、同义词、多父节点关系
  2. ICD-11 MMS (Excel)       — 提供编码、中文名称、章节归属

覆盖范围:
  - Chapter 14 (皮肤病) 全部条目
  - Chapter 01,02,03,04,05,13,19,20,21,22 中皮肤相关条目
  - Foundation 皮肤子树中未在 MMS 出现的深层概念

输出:
  - skin_kg_full.json          完整知识图谱 (nodes + edges + metadata)
  - skin_kg_triples.csv        三元组格式 (head, relation, tail)
  - skin_kg_nodes.csv          节点属性表 (可直接 pandas 读取)
  - skin_kg_stats.json         统计信息
"""

import json
import re
import csv
import pandas as pd
from collections import defaultdict, deque
from pathlib import Path

# ============================================================
# 配置
# ============================================================
BASE = Path("/Users/chenlinwei/Documents/PaperProject/baichuan")
OBO_PATH = BASE / "ICD-11" / "foundation" / "icd11.obo"
MMS_PATH = BASE / "ICD-11" / "ICD-11-with-PathID.xlsx"
OUT_DIR = BASE / "dataset" / "skin_knowledge_graph"
OUT_DIR.mkdir(exist_ok=True)

TARGET_CHAPTERS = ['01', '02', '03', '04', '05', '13', '14', '19', '20', '21', '22']

# 用于在非 Ch14 章节中捞取皮肤相关条目的关键词
SKIN_KEYWORDS = [
    # 核心皮肤术语
    r'\bskin\b', r'cutaneous', r'dermat', r'epider', r'subcutan',
    # 色素/毛发/指甲
    r'melanom', r'melanocyt', r'\bnevus\b', r'\bnaevus\b', r'\bnevi\b', r'\bnaevi\b',
    r'pigment', r'depigment', r'vitiligo', r'albinism',
    r'alopecia', r'hair loss', r'hirsut', r'hypertrichos',
    r'\bnail\b', r'onych', r'paronych',
    # 炎性/免疫
    r'pemphig', r'urticaria', r'erythema\b', r'pruritus', r'prurigo',
    r'psoriasis', r'eczema', r'\bacne\b', r'rosacea', r'lichen',
    r'bullous', r'blister', r'\brash\b', r'exanthem',
    r'angioedema', r'vasculitis', r'purpura',
    r'lupus.*skin\b|cutaneous.*lupus', r'scleroderma', r'dermatomyositis', r'morphea',
    r'photosensit', r'photodermat',
    # 感染
    r'\bherpes\b', r'\btinea\b', r'\bscabies\b', r'cellulitis',
    r'\bwart\b', r'\bwarts\b', r'verruca', r'impetigo', r'follicul',
    r'mycosis.*skin|cutaneous.*mycosis', r'fungal.*skin|skin.*fungal',
    # 肿瘤
    r'kaposi', r'basal cell', r'squamous cell.*skin|cutaneous.*squamous',
    r'\bmerkel\b', r"bowen", r'keratoacanthoma',
    # 损伤/物理
    r'burn of', r'burn.*skin', r'frostbite', r'sunburn', r'decubitus',
    r'pressure sore', r'pressure ulcer', r'wound.*skin|skin.*wound',
    r'\bscar\b', r'keloid', r'cicatri',
    # 附属器
    r'sebaceous', r'sweat gland', r'eccrine', r'apocrine',
    # 遗传/角化
    r'ichthyosis', r'keratosis', r'xeroderma', r'epidermolysis',
    r'keratoderma', r'porokeratosis',
    # 新生儿/先天
    r'birthmark', r'haemangioma', r'hemangioma', r'port.wine',
]
SKIN_PATTERN = re.compile('|'.join(SKIN_KEYWORDS), re.IGNORECASE)


# ============================================================
# Step 1: 解析 Foundation OBO 文件
# ============================================================
print("=" * 60)
print("Step 1: 解析 Foundation OBO ...")

terms = {}
current = None

with open(OBO_PATH, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.rstrip('\n')
        stripped = line.strip()
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
                    syn = m.group(1).replace('\\,', ',')
                    current.setdefault('synonyms', []).append(syn)
            elif stripped.startswith('property_value: skos:exactMatch '):
                code = stripped.split('skos:exactMatch ')[1].strip()
                current['mms_code'] = code  # e.g. "icd11.code:EA90"

if current and 'id' in current:
    terms[current['id']] = current

print("  Foundation 总实体数: %d" % len(terms))

# 构建 parent→children 索引
children_map = defaultdict(list)
for tid, t in terms.items():
    for p in t.get('parents', []):
        children_map[p].append(tid)


# ============================================================
# Step 2: BFS 构建 Foundation 皮肤子树
# ============================================================
print("\nStep 2: 构建 Foundation 皮肤子树 ...")

SKIN_ROOT = 'icd11:1639304259'
queue = deque([SKIN_ROOT])
skin_foundation_ids = set()
while queue:
    node = queue.popleft()
    if node in skin_foundation_ids:
        continue
    skin_foundation_ids.add(node)
    for child in children_map.get(node, []):
        queue.append(child)

print("  皮肤子树节点数: %d" % len(skin_foundation_ids))

# 提取 entity number 集合 (用于和 MMS 桥接)
skin_entity_numbers = set()
for fid in skin_foundation_ids:
    skin_entity_numbers.add(fid.replace('icd11:', ''))


# ============================================================
# Step 3: 解析 MMS Excel，提取多章节皮肤相关条目
# ============================================================
print("\nStep 3: 解析 MMS 数据 ...")

mms_df = pd.read_excel(MMS_PATH)
print("  MMS 总条目: %d" % len(mms_df))

# 提取 Foundation entity number
def extract_entity_number(uri):
    if pd.isna(uri):
        return None
    uri = str(uri)
    if '/entity/' in uri:
        return uri.split('/entity/')[-1]
    return None

mms_df['entity_number'] = mms_df['Foundation URI'].apply(extract_entity_number)

# 筛选目标章节
target_df = mms_df[mms_df['ChapterNo'].astype(str).isin(TARGET_CHAPTERS)].copy()

# 策略 A: Chapter 14 全部纳入
ch14_mask = target_df['ChapterNo'].astype(str) == '14'

# 策略 B: 非 Ch14 中 Foundation URI 在皮肤子树中的
foundation_bridge_mask = target_df['entity_number'].isin(skin_entity_numbers) & ~ch14_mask

# 策略 C: 非 Ch14 中关键词命中的
keyword_mask = target_df['Title'].astype(str).apply(lambda x: bool(SKIN_PATTERN.search(x))) & ~ch14_mask

# 合并三个策略
skin_mms_mask = ch14_mask | foundation_bridge_mask | keyword_mask
skin_mms_df = target_df[skin_mms_mask].copy()

print("  皮肤相关 MMS 条目: %d" % len(skin_mms_df))
print("    Chapter 14 全量: %d" % ch14_mask.sum())
print("    其他章节 Foundation 桥接: %d" % foundation_bridge_mask.sum())
print("    其他章节关键词命中: %d" % keyword_mask.sum())
print("    (去重后) 非 Ch14 合计: %d" % (skin_mms_mask & ~ch14_mask).sum())

# 按章节统计
print("\n  各章节皮肤相关条目:")
for ch in TARGET_CHAPTERS:
    cnt = (skin_mms_df['ChapterNo'].astype(str) == ch).sum()
    if cnt > 0:
        print("    Chapter %2s: %d 条" % (ch, cnt))


# ============================================================
# Step 4: 合并 Foundation + MMS → 构建节点
# ============================================================
print("\nStep 4: 合并 Foundation + MMS 构建节点 ...")

nodes = {}  # key: node_id, value: dict of attributes
edges = []  # list of (source, relation, target)

# --- 4a: 从 Foundation 皮肤子树添加节点 ---
for fid in skin_foundation_ids:
    t = terms.get(fid, {})
    node_id = fid  # e.g. "icd11:1639304259"

    # 解析 MMS code
    mms_code_raw = t.get('mms_code', '')
    mms_code = ''
    if mms_code_raw.startswith('icd11.code:'):
        mms_code = mms_code_raw.replace('icd11.code:', '')

    nodes[node_id] = {
        'id': node_id,
        'entity_number': fid.replace('icd11:', ''),
        'name': t.get('name', ''),
        'definition': t.get('def', ''),
        'synonyms': t.get('synonyms', []),
        'mms_code': mms_code,
        'cn_name': '',
        'chapter': '14',  # default, will be updated from MMS
        'path_id': '',
        'class_kind': '',
        'is_leaf_mms': False,
        'is_leaf_foundation': len(children_map.get(fid, [])) == 0,
        'source': 'foundation',
        'parents_foundation': t.get('parents', []),
    }

print("  Foundation 节点: %d" % len(nodes))

# --- 4b: 从 MMS 数据丰富节点 / 添加新节点 ---
mms_only_count = 0
mms_enriched_count = 0

for _, row in skin_mms_df.iterrows():
    ent_num = row.get('entity_number')
    node_id = ('icd11:' + str(ent_num)) if ent_num else None

    title = str(row.get('Title', '')).strip('" -').strip()
    code = str(row.get('Code', '')) if pd.notna(row.get('Code')) else ''
    cn_name = str(row.get('中文名称', '')) if pd.notna(row.get('中文名称')) else ''
    path_id = str(row.get('Path ID', '')) if pd.notna(row.get('Path ID')) else ''
    class_kind = str(row.get('ClassKind', '')) if pd.notna(row.get('ClassKind')) else ''
    is_leaf = bool(row.get('isLeaf', False))
    chapter = str(row.get('ChapterNo', ''))

    if node_id and node_id in nodes:
        # 已有 Foundation 节点 → 用 MMS 信息丰富
        n = nodes[node_id]
        if code and not n['mms_code']:
            n['mms_code'] = code
        if cn_name:
            n['cn_name'] = cn_name
        if path_id:
            n['path_id'] = path_id
        if class_kind:
            n['class_kind'] = class_kind
        n['is_leaf_mms'] = is_leaf
        n['chapter'] = chapter
        n['source'] = 'foundation+mms'
        # 如果 Foundation 名字为空但 MMS 有 title
        if not n['name'] and title:
            n['name'] = title
        mms_enriched_count += 1
    else:
        # MMS 独有条目 → 创建新节点
        new_id = node_id if node_id else ('mms:' + code if code else 'mms:path:' + path_id)
        if new_id not in nodes:
            nodes[new_id] = {
                'id': new_id,
                'entity_number': ent_num or '',
                'name': title,
                'definition': '',
                'synonyms': [],
                'mms_code': code,
                'cn_name': cn_name,
                'chapter': chapter,
                'path_id': path_id,
                'class_kind': class_kind,
                'is_leaf_mms': is_leaf,
                'is_leaf_foundation': True,  # 不在 Foundation 子树中
                'source': 'mms_only',
                'parents_foundation': [],
            }
            mms_only_count += 1

print("  MMS 丰富已有节点: %d" % mms_enriched_count)
print("  MMS 新增节点: %d" % mms_only_count)
print("  总节点数: %d" % len(nodes))


# ============================================================
# Step 5: 构建边 (关系)
# ============================================================
print("\nStep 5: 构建关系边 ...")

# --- 5a: Foundation is_a 关系 ---
foundation_is_a = 0
for node_id, node in nodes.items():
    for parent_id in node.get('parents_foundation', []):
        if parent_id in nodes:
            edges.append((node_id, 'is_a', parent_id))
            foundation_is_a += 1

print("  Foundation is_a 边: %d" % foundation_is_a)

# --- 5b: MMS Path ID 层级关系 (补充 Foundation 没覆盖的) ---
# 对 MMS-only 节点，从 Path ID 推导父子关系
path_to_node = {}
for nid, n in nodes.items():
    if n['path_id']:
        path_to_node[n['path_id']] = nid

mms_hierarchy_edges = 0
for nid, n in nodes.items():
    pid = n['path_id']
    if not pid or '.' not in pid:
        continue
    # 父 Path ID = 去掉最后一个 .xxx
    parent_path = '.'.join(pid.split('.')[:-1])
    parent_nid = path_to_node.get(parent_path)
    if parent_nid and parent_nid != nid:
        # 检查是否已有 Foundation is_a 边
        existing = any(e[0] == nid and e[2] == parent_nid and e[1] == 'is_a' for e in edges[-100:])
        if not existing:
            edges.append((nid, 'mms_parent', parent_nid))
            mms_hierarchy_edges += 1

print("  MMS 层级补充边: %d" % mms_hierarchy_edges)

# --- 5c: 跨章节关系 ---
# 如果一个 Foundation 皮肤子树节点的 MMS 编码在非 Ch14 章节，标记跨章节
cross_chapter_edges = 0
for nid, n in nodes.items():
    if n['chapter'] != '14' and n['chapter'] and n['source'] == 'foundation+mms':
        # 这个节点在 Foundation 皮肤子树中，但 MMS 编到了其他章节
        edges.append((nid, 'also_classified_in_chapter', 'chapter:' + n['chapter']))
        cross_chapter_edges += 1

print("  跨章节标记边: %d" % cross_chapter_edges)

# --- 5d: 同义词关系 ---
synonym_edges = 0
for nid, n in nodes.items():
    for syn in n.get('synonyms', []):
        edges.append((nid, 'has_synonym', 'syn:' + syn))
        synonym_edges += 1

print("  同义词边: %d" % synonym_edges)

# --- 5e: MMS 编码关系 ---
code_edges = 0
for nid, n in nodes.items():
    if n['mms_code']:
        edges.append((nid, 'has_mms_code', 'code:' + n['mms_code']))
        code_edges += 1

print("  编码关系边: %d" % code_edges)

total_edges = len(edges)
print("  总边数: %d" % total_edges)


# ============================================================
# Step 6: 计算统计信息
# ============================================================
print("\nStep 6: 统计 ...")

stats = {
    'total_nodes': len(nodes),
    'total_edges': total_edges,
    'foundation_nodes_in_skin_subtree': len(skin_foundation_ids),
    'mms_skin_entries': len(skin_mms_df),
    'nodes_with_definition': sum(1 for n in nodes.values() if n['definition']),
    'nodes_with_synonyms': sum(1 for n in nodes.values() if n['synonyms']),
    'nodes_with_mms_code': sum(1 for n in nodes.values() if n['mms_code']),
    'nodes_with_cn_name': sum(1 for n in nodes.values() if n['cn_name']),
    'leaf_nodes_foundation': sum(1 for n in nodes.values() if n['is_leaf_foundation']),
    'leaf_nodes_mms': sum(1 for n in nodes.values() if n['is_leaf_mms']),
    'source_distribution': {},
    'chapter_distribution': {},
    'edge_type_distribution': {
        'is_a': foundation_is_a,
        'mms_parent': mms_hierarchy_edges,
        'also_classified_in_chapter': cross_chapter_edges,
        'has_synonym': synonym_edges,
        'has_mms_code': code_edges,
    },
}

# source 分布
for n in nodes.values():
    src = n['source']
    stats['source_distribution'][src] = stats['source_distribution'].get(src, 0) + 1

# chapter 分布
for n in nodes.values():
    ch = n['chapter'] or 'no_chapter'
    stats['chapter_distribution'][ch] = stats['chapter_distribution'].get(ch, 0) + 1

# 19 个一级分类统计
top_categories = []
for child_id in children_map.get(SKIN_ROOT, []):
    t = terms.get(child_id, {})
    # 计算子树大小
    q = deque([child_id])
    visited = set()
    with_def = 0
    with_syn = 0
    with_code = 0
    while q:
        nd = q.popleft()
        if nd in visited:
            continue
        visited.add(nd)
        nt = nodes.get(nd, {})
        if nt.get('definition'):
            with_def += 1
        if nt.get('synonyms'):
            with_syn += 1
        if nt.get('mms_code'):
            with_code += 1
        for ch in children_map.get(nd, []):
            q.append(ch)

    top_categories.append({
        'id': child_id,
        'name': t.get('name', ''),
        'subtree_size': len(visited),
        'with_definition': with_def,
        'with_synonyms': with_syn,
        'with_mms_code': with_code,
    })

stats['top_level_categories'] = top_categories


# ============================================================
# Step 7: 输出文件
# ============================================================
print("\nStep 7: 输出文件 ...")

# --- 7a: 完整知识图谱 JSON ---
# 节点列表 (去掉 parents_foundation 这个临时字段)
nodes_list = []
for nid, n in nodes.items():
    node_out = {k: v for k, v in n.items() if k != 'parents_foundation'}
    # synonyms 转为 string (JSON 中保持 list)
    nodes_list.append(node_out)

kg_full = {
    'metadata': stats,
    'nodes': nodes_list,
    'edges': [{'source': e[0], 'relation': e[1], 'target': e[2]} for e in edges],
}

out_json = OUT_DIR / "skin_kg_full.json"
with open(out_json, 'w', encoding='utf-8') as f:
    json.dump(kg_full, f, ensure_ascii=False, indent=2)
print("  %s (%.1f MB)" % (out_json.name, out_json.stat().st_size / 1e6))

# --- 7b: 三元组 CSV ---
out_triples = OUT_DIR / "skin_kg_triples.csv"
with open(out_triples, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['head', 'relation', 'tail'])
    for e in edges:
        writer.writerow(e)
print("  %s (%d 行)" % (out_triples.name, len(edges)))

# --- 7c: 节点属性表 CSV ---
out_nodes = OUT_DIR / "skin_kg_nodes.csv"
rows = []
for nid, n in nodes.items():
    rows.append({
        'id': n['id'],
        'name': n['name'],
        'definition': n['definition'][:500] if n['definition'] else '',
        'synonyms': ' | '.join(n['synonyms']) if n['synonyms'] else '',
        'mms_code': n['mms_code'],
        'cn_name': n['cn_name'],
        'chapter': n['chapter'],
        'path_id': n['path_id'],
        'class_kind': n['class_kind'],
        'is_leaf_foundation': n['is_leaf_foundation'],
        'is_leaf_mms': n['is_leaf_mms'],
        'source': n['source'],
        'num_synonyms': len(n['synonyms']),
        'has_definition': bool(n['definition']),
    })
pd.DataFrame(rows).to_csv(out_nodes, index=False, encoding='utf-8')
print("  %s (%d 行)" % (out_nodes.name, len(rows)))

# --- 7d: 统计信息 JSON ---
out_stats = OUT_DIR / "skin_kg_stats.json"
with open(out_stats, 'w', encoding='utf-8') as f:
    json.dump(stats, f, ensure_ascii=False, indent=2)
print("  %s" % out_stats.name)

# --- 7e: 19 个一级分类的详细枚举 ---
out_categories = OUT_DIR / "skin_kg_top_categories.json"
with open(out_categories, 'w', encoding='utf-8') as f:
    json.dump(top_categories, f, ensure_ascii=False, indent=2)
print("  %s" % out_categories.name)


# ============================================================
# 打印最终统计
# ============================================================
print("\n" + "=" * 60)
print("皮肤病知识图谱构建完成!")
print("=" * 60)
print("节点统计:")
print("  总节点数:           %d" % stats['total_nodes'])
print("  有定义文本的:       %d (%.1f%%)" % (
    stats['nodes_with_definition'],
    100 * stats['nodes_with_definition'] / stats['total_nodes']))
print("  有同义词的:         %d (%.1f%%)" % (
    stats['nodes_with_synonyms'],
    100 * stats['nodes_with_synonyms'] / stats['total_nodes']))
print("  有 MMS 编码的:      %d (%.1f%%)" % (
    stats['nodes_with_mms_code'],
    100 * stats['nodes_with_mms_code'] / stats['total_nodes']))
print("  有中文名称的:       %d (%.1f%%)" % (
    stats['nodes_with_cn_name'],
    100 * stats['nodes_with_cn_name'] / stats['total_nodes']))
print("  Foundation 叶节点:  %d" % stats['leaf_nodes_foundation'])

print("\n来源分布:")
for src, cnt in sorted(stats['source_distribution'].items()):
    print("  %-20s %d" % (src, cnt))

print("\n章节分布:")
for ch, cnt in sorted(stats['chapter_distribution'].items()):
    print("  Chapter %-10s %d" % (ch, cnt))

print("\n边统计:")
print("  总边数:  %d" % stats['total_edges'])
for etype, cnt in stats['edge_type_distribution'].items():
    print("  %-30s %d" % (etype, cnt))

print("\n19 个一级分类:")
for cat in sorted(top_categories, key=lambda x: -x['subtree_size']):
    print("  %-55s 子树: %4d  定义: %4d  同义词: %4d  MMS编码: %4d" % (
        cat['name'][:55], cat['subtree_size'], cat['with_definition'],
        cat['with_synonyms'], cat['with_mms_code']))

print("\n输出目录: %s" % OUT_DIR)
print("完成!")
