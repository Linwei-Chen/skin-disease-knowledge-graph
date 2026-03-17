#!/usr/bin/env python3
"""
皮肤病知识图谱 v3 — 全面整合所有数据源
======================================
数据源:
  Core:  ICD-11 Foundation (5,216 皮肤节点) + MMS (11 章节, 1,766 条目)
  Onto:  DermO (3,401) + HPO 皮肤分支 (1,094) + DOID 皮肤分支 (586) + DEVO (317)
  Rare:  RSDB (891 罕见皮肤病 + 基因/表型/药物) + Orphanet (1,234 罕见皮肤病)
  Data:  Derm1M (417K 图像-文本对)
"""

import json, re, csv
import pandas as pd
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from pathlib import Path

BASE = Path("/Users/chenlinwei/Documents/PaperProject/baichuan")
OBO_PATH = BASE / "ICD-11" / "foundation" / "icd11.obo"
MMS_PATH = BASE / "ICD-11" / "ICD-11-with-PathID.xlsx"
EXT = BASE / "ICD-11" / "foundation" / "external_ontologies"
DERM1M_PATH = BASE / "dataset" / "Derm1M_v2_pretrain.csv"
OUT_DIR = BASE / "dataset" / "skin_knowledge_graph"
OUT_DIR.mkdir(exist_ok=True)

TARGET_CHAPTERS = ['01','02','03','04','05','13','14','19','20','21','22']
SKIN_PATTERN = re.compile(
    r'\bskin\b|cutaneous|dermat|epider|subcutan|melanom|melanocyt|\bnevus\b|\bnaevus\b'
    r'|pigment|depigment|vitiligo|alopecia|hirsut|\bnail\b|onych'
    r'|pemphig|urticaria|erythema\b|pruritus|psoriasis|eczema|\bacne\b|rosacea|lichen'
    r'|bullous|blister|\brash\b|angioedema|vasculitis|purpura'
    r'|lupus.*skin|scleroderma|dermatomyositis|morphea|photosensit'
    r'|\bherpes\b|\btinea\b|\bscabies\b|cellulitis|\bwart|verruca|impetigo|follicul'
    r'|kaposi|basal cell|squamous cell|\bmerkel\b|bowen|keratoacanthoma'
    r'|burn of|frostbite|sunburn|decubitus|pressure ulcer|\bscar\b|keloid'
    r'|sebaceous|sweat gland|ichthyosis|keratosis|xeroderma|epidermolysis'
    r'|haemangioma|hemangioma|birthmark', re.IGNORECASE)


def parse_obo(path):
    terms = {}; current = None
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            s = line.rstrip('\n').strip()
            if s == '[Term]': current = {}
            elif s == '' and current is not None:
                if 'id' in current: terms[current['id']] = current
                current = None
            elif current is not None:
                if s.startswith('id: '): current['id'] = s[4:]
                elif s.startswith('name: '): current['name'] = s[6:].replace('\\,',',').replace('\\(','(').replace('\\)',')')
                elif s.startswith('def: '):
                    m = re.match(r'def: "(.*)"', s)
                    if m: current['def'] = m.group(1).replace('\\,',',').replace('\\(','(').replace('\\)',')')
                elif s.startswith('is_a: '): current.setdefault('parents',[]).append(s[6:].split(' !')[0].strip())
                elif s.startswith('synonym: '):
                    m = re.match(r'synonym: "(.*?)"', s)
                    if m: current.setdefault('synonyms',[]).append(m.group(1).replace('\\,',','))
                elif s.startswith('xref: '): current.setdefault('xrefs',[]).append(s[6:])
                elif s.startswith('property_value: skos:exactMatch '): current['mms_code'] = s.split('skos:exactMatch ')[1].strip()
                elif s.startswith('is_obsolete: true'): current['obsolete'] = True
    if current and 'id' in current: terms[current['id']] = current
    return {k:v for k,v in terms.items() if not v.get('obsolete')}

def build_subtree(terms, root_id):
    cm = defaultdict(list)
    for tid,t in terms.items():
        for p in t.get('parents',[]): cm[p].append(tid)
    q = deque([root_id]); vis = set()
    while q:
        n = q.popleft()
        if n in vis: continue
        vis.add(n)
        for c in cm.get(n,[]): q.append(c)
    return vis, cm

def norm(name):
    n = name.lower().strip()
    n = re.sub(r'[,;()\[\]{}\'""]', '', n)
    return re.sub(r'\s+', ' ', n)


# ============================================================
print("=" * 60)
print("PHASE 1: ICD-11 Foundation + MMS 核心")
print("=" * 60)

icd11 = parse_obo(str(OBO_PATH))
skin_ids, icd11_cm = build_subtree(icd11, 'icd11:1639304259')
skin_ent_nums = {fid.replace('icd11:','') for fid in skin_ids}
print("Foundation 皮肤子树: %d 节点" % len(skin_ids))

mms_df = pd.read_excel(MMS_PATH)
mms_df['ent_num'] = mms_df['Foundation URI'].apply(
    lambda u: str(u).split('/entity/')[-1] if pd.notna(u) and '/entity/' in str(u) else None)
tdf = mms_df[mms_df['ChapterNo'].astype(str).isin(TARGET_CHAPTERS)].copy()
m1 = tdf['ChapterNo'].astype(str) == '14'
m2 = tdf['ent_num'].isin(skin_ent_nums) & ~m1
m3 = tdf['Title'].astype(str).apply(lambda x: bool(SKIN_PATTERN.search(x))) & ~m1
skin_mms = tdf[m1|m2|m3].copy()
print("MMS 皮肤相关: %d 条目" % len(skin_mms))

# Build nodes
nodes = {}; edges = []
for fid in skin_ids:
    t = icd11.get(fid, {})
    mc = t.get('mms_code','')
    if mc.startswith('icd11.code:'): mc = mc[11:]
    else: mc = ''
    nodes[fid] = {
        'id': fid, 'name': t.get('name',''), 'nn': norm(t.get('name','')),
        'definition': t.get('def',''), 'synonyms': list(t.get('synonyms',[])),
        'mms_code': mc, 'cn_name': '', 'chapter': '14', 'path_id': '',
        'is_leaf': len(icd11_cm.get(fid,[])) == 0,
        'source': 'foundation', 'parents': list(t.get('parents',[])),
        'dermo_id': '', 'doid_id': '', 'orpha_codes': [], 'rsdb_id': '',
        'snomed': [], 'omim': [], 'umls': [], 'mesh': [], 'icd10': [],
        'hpo_pheno': [], 'genes': [], 'drugs': [],
        'image_count': 0, 'data_sources': [],
    }

for _, row in skin_mms.iterrows():
    en = row.get('ent_num')
    nid = ('icd11:'+str(en)) if en else None
    title = str(row.get('Title','')).strip('" -').strip()
    code = str(row.get('Code','')) if pd.notna(row.get('Code')) else ''
    cn = str(row.get('中文名称','')) if pd.notna(row.get('中文名称')) else ''
    pid = str(row.get('Path ID','')) if pd.notna(row.get('Path ID')) else ''
    ch = str(row.get('ChapterNo',''))
    if nid and nid in nodes:
        n = nodes[nid]
        if code and not n['mms_code']: n['mms_code'] = code
        if cn: n['cn_name'] = cn
        if pid: n['path_id'] = pid
        n['chapter'] = ch; n['source'] = 'foundation+mms'
        if not n['name'] and title: n['name'] = title; n['nn'] = norm(title)
    else:
        new_id = nid if nid else ('mms:'+code if code else 'mms:p:'+pid)
        if new_id not in nodes:
            nodes[new_id] = {
                'id': new_id, 'name': title, 'nn': norm(title),
                'definition': '', 'synonyms': [], 'mms_code': code,
                'cn_name': cn, 'chapter': ch, 'path_id': pid,
                'is_leaf': True, 'source': 'mms_only', 'parents': [],
                'dermo_id': '', 'doid_id': '', 'orpha_codes': [], 'rsdb_id': '',
                'snomed': [], 'omim': [], 'umls': [], 'mesh': [], 'icd10': [],
                'hpo_pheno': [], 'genes': [], 'drugs': [],
                'image_count': 0, 'data_sources': [],
            }

# is_a edges
for nid,n in nodes.items():
    for pid in n['parents']:
        if pid in nodes: edges.append((nid,'is_a',pid))
# mms hierarchy
p2n = {n['path_id']:nid for nid,n in nodes.items() if n['path_id']}
for nid,n in nodes.items():
    p = n['path_id']
    if p and '.' in p:
        pp = '.'.join(p.split('.')[:-1])
        if pp in p2n and p2n[pp] != nid: edges.append((nid,'mms_parent',p2n[pp]))

print("核心节点: %d, 核心边: %d" % (len(nodes), len(edges)))

# Name index
name_idx = {}
for nid,n in nodes.items():
    if n['nn']: name_idx[n['nn']] = nid
    for s in n['synonyms']: name_idx[norm(s)] = nid

# ============================================================
print("\n" + "=" * 60)
print("PHASE 2: 外部本体整合")
print("=" * 60)

# --- DermO ---
print("\n--- DermO ---")
dermo = parse_obo(str(EXT / "dermo.obo"))
dm = 0; dx = 0
for did,dt in dermo.items():
    dn = norm(dt.get('name',''))
    matched = name_idx.get(dn)
    if not matched:
        for s in dt.get('synonyms',[]):
            matched = name_idx.get(norm(s))
            if matched: break
    if matched:
        dm += 1; nodes[matched]['dermo_id'] = did
        for x in dt.get('xrefs',[]):
            if x.startswith('SNOMEDCT') and x.split(':')[-1] not in nodes[matched]['snomed']:
                nodes[matched]['snomed'].append(x.split(':')[-1]); dx += 1
            elif x.startswith('OMIM:') and x[5:] not in nodes[matched]['omim']:
                nodes[matched]['omim'].append(x[5:]); dx += 1
            elif x.startswith('ICD10:') and x[6:] not in nodes[matched]['icd10']:
                nodes[matched]['icd10'].append(x[6:]); dx += 1
            elif x.startswith('HP:') and x not in nodes[matched]['hpo_pheno']:
                nodes[matched]['hpo_pheno'].append(x); dx += 1
            elif x.startswith('DOID:') and not nodes[matched]['doid_id']:
                nodes[matched]['doid_id'] = x; dx += 1
        if not nodes[matched]['definition'] and dt.get('def'):
            nodes[matched]['definition'] = dt['def']
        for s in dt.get('synonyms',[]):
            if s not in nodes[matched]['synonyms']: nodes[matched]['synonyms'].append(s)
print("  DermO 匹配: %d / %d, 新引用: %d" % (dm, len(dermo), dx))

# --- HPO ---
print("\n--- HPO 皮肤表型 ---")
hpo = parse_obo(str(EXT / "hp.obo"))
integ_ids, hpo_cm = build_subtree(hpo, 'HP:0001574')
ha = 0
for hid in integ_ids:
    ht = hpo.get(hid, {})
    nid = 'hpo:' + hid
    if nid not in nodes:
        nodes[nid] = {
            'id': nid, 'name': ht.get('name',''), 'nn': norm(ht.get('name','')),
            'definition': ht.get('def',''), 'synonyms': list(ht.get('synonyms',[])),
            'mms_code': '', 'cn_name': '', 'chapter': 'HPO', 'path_id': '',
            'is_leaf': len(hpo_cm.get(hid,[])) == 0,
            'source': 'hpo', 'parents': [],
            'dermo_id': '', 'doid_id': '', 'orpha_codes': [], 'rsdb_id': '',
            'snomed': [], 'omim': [], 'umls': [], 'mesh': [], 'icd10': [],
            'hpo_pheno': [], 'genes': [], 'drugs': [],
            'image_count': 0, 'data_sources': [],
        }; ha += 1
        for pid in ht.get('parents',[]):
            pnid = 'hpo:'+pid
            if pnid in nodes or pid in integ_ids: edges.append((nid,'is_a',pnid))
        name_idx[norm(ht.get('name',''))] = nid
print("  HPO 新增: %d 表型节点" % ha)

# --- DOID ---
print("\n--- DOID 皮肤病 ---")
doid = parse_obo(str(EXT / "doid.obo"))
sdoid, _ = build_subtree(doid, 'DOID:37')
ddm = 0; ddx = 0
for did in sdoid:
    dt = doid.get(did,{})
    dn = norm(dt.get('name',''))
    matched = name_idx.get(dn)
    if not matched:
        for s in dt.get('synonyms',[]):
            matched = name_idx.get(norm(s))
            if matched: break
    if matched:
        ddm += 1
        if not nodes[matched]['doid_id']: nodes[matched]['doid_id'] = did
        for x in dt.get('xrefs',[]):
            if x.startswith('UMLS_CUI:') and x[9:] not in nodes[matched]['umls']:
                nodes[matched]['umls'].append(x[9:]); ddx += 1
            elif x.startswith('MESH:') and x[5:] not in nodes[matched]['mesh']:
                nodes[matched]['mesh'].append(x[5:]); ddx += 1
            elif x.startswith('SNOMEDCT') and x.split(':')[-1] not in nodes[matched]['snomed']:
                nodes[matched]['snomed'].append(x.split(':')[-1]); ddx += 1
            elif x.startswith('MIM:') and x[4:] not in nodes[matched]['omim']:
                nodes[matched]['omim'].append(x[4:]); ddx += 1
        if not nodes[matched]['definition'] and dt.get('def'):
            nodes[matched]['definition'] = dt['def']
        for s in dt.get('synonyms',[]):
            if s not in nodes[matched]['synonyms']: nodes[matched]['synonyms'].append(s)
print("  DOID 匹配: %d / %d, 新引用: %d" % (ddm, len(sdoid), ddx))


# ============================================================
print("\n" + "=" * 60)
print("PHASE 3: RSDB 罕见皮肤病 (基因 + 表型 + 药物)")
print("=" * 60)

rsdb_d = pd.read_csv(str(EXT / "rsdb" / "diseases.csv"))
rsdb_dp = pd.read_csv(str(EXT / "rsdb" / "disease_phenotype_relationships.csv"))
rsdb_pheno = pd.read_csv(str(EXT / "rsdb" / "phenotypes.csv"))
rsdb_genes = pd.read_csv(str(EXT / "rsdb" / "genes.csv"))
# compound-disease for drug associations
rsdb_cd = pd.read_csv(str(EXT / "rsdb" / "compound_disease_relationships.csv"))
rsdb_compounds = pd.read_csv(str(EXT / "rsdb" / "compounds.csv"))

# Gene index (gene internal id → symbol)
gene_idx = {}
for _, g in rsdb_genes.iterrows():
    gene_idx[g['id']] = str(g.get('symbol', ''))

# Phenotype index
pheno_idx = {}
for _, p in rsdb_pheno.iterrows():
    pheno_idx[p['id']] = str(p.get('name', ''))

# Compound index
compound_idx = {}
for _, c in rsdb_compounds.iterrows():
    compound_idx[c['id']] = str(c.get('name', ''))

# RSDB uses compound_gene_relationships to link genes to diseases indirectly
# But disease_phenotype_relationships has direct disease_id
# For genes: diseases.csv has disease_gene_relationships_count but no direct table
# We use compound-disease as drug linkage instead

rm = 0; rp = 0; rd_drugs = 0
for _, rd in rsdb_d.iterrows():
    rname = norm(str(rd.get('orpha_name','') or ''))
    matched = name_idx.get(rname) if rname else None
    if not matched and pd.notna(rd.get('alias')):
        for alias in str(rd['alias']).split(','):
            matched = name_idx.get(norm(alias.strip()))
            if matched: break
    if not matched and pd.notna(rd.get('synonym')):
        for syn in str(rd['synonym']).split(','):
            matched = name_idx.get(norm(syn.strip()))
            if matched: break
    if not matched and pd.notna(rd.get('gard_name')):
        matched = name_idx.get(norm(str(rd['gard_name'])))

    if matched:
        rm += 1
        nodes[matched]['rsdb_id'] = str(rd['id'])
        if pd.notna(rd.get('orpha')):
            oc = str(rd['orpha'])
            if oc not in nodes[matched]['orpha_codes']: nodes[matched]['orpha_codes'].append(oc)
        if pd.notna(rd.get('omim')):
            try:
                ov = str(int(rd['omim']))
                if ov not in nodes[matched]['omim']: nodes[matched]['omim'].append(ov)
            except: pass
        if pd.notna(rd.get('umls')) and str(rd['umls']) not in nodes[matched]['umls']:
            nodes[matched]['umls'].append(str(rd['umls']))
        if pd.notna(rd.get('mesh')) and str(rd['mesh']) not in nodes[matched]['mesh']:
            nodes[matched]['mesh'].append(str(rd['mesh']))
        if pd.notna(rd.get('icd10')) and str(rd['icd10']) not in nodes[matched]['icd10']:
            nodes[matched]['icd10'].append(str(rd['icd10']))
        if not nodes[matched]['definition'] and pd.notna(rd.get('description')):
            nodes[matched]['definition'] = str(rd['description'])[:1000]
        if pd.notna(rd.get('inheritance')) and rd['inheritance']:
            nodes[matched].setdefault('inheritance', str(rd['inheritance']))

        # 表型关联
        dphenos = rsdb_dp[rsdb_dp['disease_id'] == rd['id']]
        for _, dp_row in dphenos.iterrows():
            pname = pheno_idx.get(dp_row.get('phenotype_id',''))
            if pname and pname not in nodes[matched]['hpo_pheno']:
                nodes[matched]['hpo_pheno'].append(pname); rp += 1

        # 药物关联
        ddrugs = rsdb_cd[rsdb_cd['disease_id'] == rd['id']]
        for _, dc_row in ddrugs.head(20).iterrows():  # top 20 drugs per disease
            cname = compound_idx.get(dc_row.get('compound_id',''))
            if cname and cname not in nodes[matched]['drugs']:
                nodes[matched]['drugs'].append(cname); rd_drugs += 1

print("RSDB 匹配: %d / %d" % (rm, len(rsdb_d)))
print("  新增表型关联: %d, 新增药物关联: %d" % (rp, rd_drugs))


# ============================================================
print("\n" + "=" * 60)
print("PHASE 4: Orphanet 罕见皮肤病")
print("=" * 60)

tree_o = ET.parse(str(EXT / "orphanet" / "en_product3_187.xml"))
orpha_disorders = tree_o.getroot().findall('.//Disorder')
om = 0
for d in orpha_disorders:
    ocode = d.find('OrphaCode')
    oname = d.find('Name')
    if ocode is None or oname is None: continue
    on = norm(oname.text)
    matched = name_idx.get(on)
    if matched:
        oc = 'ORPHA:' + ocode.text
        if oc not in nodes[matched]['orpha_codes']:
            nodes[matched]['orpha_codes'].append(oc); om += 1

# Also parse nomenclature JSON for cross-references
try:
    with open(str(EXT / "orphanet" / "en_product1.json"), 'r') as f:
        orpha_json = json.load(f)
    # Extract ICD-11 and other mappings
    orpha_xref = 0
    disorder_list = orpha_json.get('JDBOR', [{}])
    if isinstance(disorder_list, dict):
        disorder_list = disorder_list.get('DisorderList', {}).get('Disorder', [])
    for dis in disorder_list:
        ocode = dis.get('OrphaCode', '')
        dname = norm(dis.get('Name', {}).get('#text', '') if isinstance(dis.get('Name'), dict) else str(dis.get('Name', '')))
        matched = name_idx.get(dname)
        if matched:
            oc = 'ORPHA:' + str(ocode)
            if oc not in nodes[matched]['orpha_codes']:
                nodes[matched]['orpha_codes'].append(oc)
                orpha_xref += 1
    print("Orphanet JSON 额外匹配: %d" % orpha_xref)
except Exception as e:
    print("Orphanet JSON 解析跳过: %s" % str(e)[:80])

print("Orphanet 皮肤分类匹配: %d / %d" % (om, len(orpha_disorders)))


# ============================================================
print("\n" + "=" * 60)
print("PHASE 5: 挂载 Derm1M 数据集 (417K 图像)")
print("=" * 60)

derm1m = pd.read_csv(str(DERM1M_PATH))
print("Derm1M 总量: %d" % len(derm1m))

# 构建 disease_label → node 映射
derm_mapped = 0; derm_unmapped_labels = set()

# 已有的 disease→icd11 映射
mapping_file = BASE / "dataset" / "disease_icd11_mapping.json"
existing_map = {}
if mapping_file.exists():
    with open(mapping_file, 'r') as f:
        raw = json.load(f)
    for k, v in raw.items():
        existing_map[norm(k)] = v.get('code', '')

for _, row in derm1m.iterrows():
    dl = str(row.get('disease_label', ''))
    if dl in ('no definitive diagnosis', 'nan', '', 'clinical diagnosis'):
        continue

    # 多疾病拆分
    labels = [l.strip() for l in dl.split(',')]
    for label in labels:
        ln = norm(label)
        matched_nid = name_idx.get(ln)

        if not matched_nid:
            # 尝试已有映射
            code = existing_map.get(ln)
            if code:
                for nid, n in nodes.items():
                    if n['mms_code'] == code:
                        matched_nid = nid; break

        if matched_nid:
            nodes[matched_nid]['image_count'] += 1
            src = str(row.get('source', ''))
            if src and src not in nodes[matched_nid]['data_sources']:
                nodes[matched_nid]['data_sources'].append(src)
            derm_mapped += 1
        else:
            derm_unmapped_labels.add(label)

print("Derm1M 图像映射: %d / %d" % (derm_mapped, len(derm1m)))
print("  未映射的唯一标签: %d" % len(derm_unmapped_labels))
print("  有图像的疾病节点: %d" % sum(1 for n in nodes.values() if n['image_count'] > 0))


# ============================================================
print("\n" + "=" * 60)
print("PHASE 6: 构建全部边")
print("=" * 60)

# 跨章节
for nid,n in nodes.items():
    if n['chapter'] not in ('14','HPO','') and n['source'] == 'foundation+mms':
        edges.append((nid, 'also_in_chapter', 'ch:'+n['chapter']))

# 同义词
for nid,n in nodes.items():
    for s in n['synonyms']: edges.append((nid, 'has_synonym', 'syn:'+s))

# MMS编码
for nid,n in nodes.items():
    if n['mms_code']: edges.append((nid, 'has_mms_code', 'code:'+n['mms_code']))

# 外部映射
for nid,n in nodes.items():
    for x in n['snomed']: edges.append((nid, 'xref_snomed', 'SCTID:'+x))
    for x in n['omim']: edges.append((nid, 'xref_omim', 'OMIM:'+x))
    for x in n['umls']: edges.append((nid, 'xref_umls', 'UMLS:'+x))
    for x in n['mesh']: edges.append((nid, 'xref_mesh', 'MeSH:'+x))
    for x in n['icd10']: edges.append((nid, 'xref_icd10', 'ICD10:'+x))
    if n['dermo_id']: edges.append((nid, 'xref_dermo', n['dermo_id']))
    if n['doid_id']: edges.append((nid, 'xref_doid', n['doid_id']))
    for x in n['orpha_codes']: edges.append((nid, 'xref_orpha', x))

# 基因关联
for nid,n in nodes.items():
    for g in n['genes']: edges.append((nid, 'associated_gene', 'gene:'+g))

# 表型关联 (HPO)
for nid,n in nodes.items():
    for hp in n['hpo_pheno']:
        if hp.startswith('HP:'):
            hp_nid = 'hpo:'+hp
            if hp_nid in nodes: edges.append((nid, 'has_phenotype', hp_nid))
            else: edges.append((nid, 'has_phenotype', hp))
        else:
            edges.append((nid, 'has_phenotype', 'pheno:'+hp))

et = defaultdict(int)
for e in edges: et[e[1]] += 1
print("总边数: %d" % len(edges))
for k,v in sorted(et.items(), key=lambda x:-x[1]): print("  %-25s %d" % (k,v))


# ============================================================
print("\n" + "=" * 60)
print("PHASE 7: 输出")
print("=" * 60)

stats = {
    'total_nodes': len(nodes),
    'total_edges': len(edges),
    'nodes_with_definition': sum(1 for n in nodes.values() if n['definition']),
    'nodes_with_synonyms': sum(1 for n in nodes.values() if n['synonyms']),
    'nodes_with_mms_code': sum(1 for n in nodes.values() if n['mms_code']),
    'nodes_with_cn_name': sum(1 for n in nodes.values() if n['cn_name']),
    'nodes_with_snomed': sum(1 for n in nodes.values() if n['snomed']),
    'nodes_with_omim': sum(1 for n in nodes.values() if n['omim']),
    'nodes_with_umls': sum(1 for n in nodes.values() if n['umls']),
    'nodes_with_mesh': sum(1 for n in nodes.values() if n['mesh']),
    'nodes_with_dermo': sum(1 for n in nodes.values() if n['dermo_id']),
    'nodes_with_doid': sum(1 for n in nodes.values() if n['doid_id']),
    'nodes_with_orpha': sum(1 for n in nodes.values() if n['orpha_codes']),
    'nodes_with_genes': sum(1 for n in nodes.values() if n['genes']),
    'nodes_with_hpo': sum(1 for n in nodes.values() if n['hpo_pheno']),
    'nodes_with_images': sum(1 for n in nodes.values() if n['image_count'] > 0),
    'total_image_mappings': sum(n['image_count'] for n in nodes.values()),
    'derm1m_unmapped_labels': len(derm_unmapped_labels),
    'edge_types': dict(et),
    'source_dist': {k: int(v) for k,v in pd.Series([n['source'] for n in nodes.values()]).value_counts().items()},
}

# JSON
nodes_out = []
for nid,n in nodes.items():
    o = {k:v for k,v in n.items() if k not in ('nn','parents')}
    nodes_out.append(o)

kg = {'metadata': stats, 'nodes': nodes_out,
      'edges': [{'source':e[0],'relation':e[1],'target':e[2]} for e in edges]}

out_j = OUT_DIR / "skin_kg_v3.json"
with open(out_j, 'w', encoding='utf-8') as f:
    json.dump(kg, f, ensure_ascii=False, indent=2)
print("%s (%.1f MB)" % (out_j.name, out_j.stat().st_size/1e6))

# Triples CSV
out_t = OUT_DIR / "skin_kg_triples_v3.csv"
with open(out_t, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['head','relation','tail'])
    for e in edges: w.writerow(e)
print("%s (%d)" % (out_t.name, len(edges)))

# Nodes CSV
out_n = OUT_DIR / "skin_kg_nodes_v3.csv"
rows = []
for nid,n in nodes.items():
    rows.append({
        'id': n['id'], 'name': n['name'],
        'definition': (n['definition'] or '')[:500],
        'synonyms': ' | '.join(n['synonyms'][:10]),
        'mms_code': n['mms_code'], 'cn_name': n['cn_name'],
        'chapter': n['chapter'], 'source': n['source'],
        'dermo_id': n['dermo_id'], 'doid_id': n['doid_id'],
        'orpha_codes': ';'.join(n['orpha_codes']),
        'rsdb_id': n['rsdb_id'],
        'snomed': ';'.join(n['snomed'][:5]),
        'omim': ';'.join(n['omim'][:5]),
        'umls': ';'.join(n['umls'][:5]),
        'mesh': ';'.join(n['mesh'][:5]),
        'genes': ';'.join(n['genes'][:10]),
        'num_hpo': len(n['hpo_pheno']),
        'image_count': n['image_count'],
        'num_synonyms': len(n['synonyms']),
        'has_def': bool(n['definition']),
        'is_leaf': n['is_leaf'],
    })
pd.DataFrame(rows).to_csv(out_n, index=False, encoding='utf-8')
print("%s (%d)" % (out_n.name, len(rows)))

# Unmapped labels
out_u = OUT_DIR / "derm1m_unmapped_labels.txt"
with open(out_u, 'w') as f:
    for l in sorted(derm_unmapped_labels): f.write(l + '\n')
print("%s (%d labels)" % (out_u.name, len(derm_unmapped_labels)))

# Stats
out_s = OUT_DIR / "skin_kg_stats_v3.json"
with open(out_s, 'w', encoding='utf-8') as f:
    json.dump(stats, f, ensure_ascii=False, indent=2)

# ============================================================
print("\n" + "=" * 60)
print("皮肤病知识图谱 v3 — 最终报告")
print("=" * 60)
print("\n节点: %d | 边: %d" % (stats['total_nodes'], stats['total_edges']))
items = [
    ('有定义文本', stats['nodes_with_definition']),
    ('有同义词', stats['nodes_with_synonyms']),
    ('有 MMS 编码', stats['nodes_with_mms_code']),
    ('有中文名称', stats['nodes_with_cn_name']),
    ('有 SNOMED', stats['nodes_with_snomed']),
    ('有 OMIM', stats['nodes_with_omim']),
    ('有 UMLS CUI', stats['nodes_with_umls']),
    ('有 MeSH', stats['nodes_with_mesh']),
    ('有 DermO 映射', stats['nodes_with_dermo']),
    ('有 DOID 映射', stats['nodes_with_doid']),
    ('有 Orphanet', stats['nodes_with_orpha']),
    ('有基因关联', stats['nodes_with_genes']),
    ('有 HPO 表型', stats['nodes_with_hpo']),
    ('有图像数据', stats['nodes_with_images']),
]
for label, val in items:
    pct = 100*val/stats['total_nodes']
    print("  %-15s %5d (%5.1f%%)" % (label, val, pct))
print("\nDerm1M 图像挂载: %d 张 → %d 个疾病节点" % (stats['total_image_mappings'], stats['nodes_with_images']))
