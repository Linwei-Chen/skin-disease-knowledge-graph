# Skin Disease Knowledge Graph

A comprehensive knowledge graph covering **6,811 skin disease and phenotype entities** with **32,080 relationships**, built by integrating 8 structured biomedical data sources around the ICD-11 backbone.

Designed to support Vision-Language Model (VLM) training for interpretable dermatological differential diagnosis.

## Quick Start

```bash
# 1. Download large data files (see docs/DATA_SOURCES.md for all URLs)
cd data
wget -O icd11_foundation.obo "https://w3id.org/biopragmatics/resources/icd11/icd11.obo"
wget -O hp.obo "http://purl.obolibrary.org/obo/hp.obo"
wget -O doid.obo "http://purl.obolibrary.org/obo/doid.obo"
# ... see docs/DATA_SOURCES.md for complete download commands

# 2. Build the knowledge graph
python3 scripts/build_v3_full.py

# 3. Visualize
cd visualization
python3 -m http.server 8765
# Open http://localhost:8765
```

## Knowledge Graph at a Glance

```
Nodes:  6,811
├── ICD-11 Disease nodes:     5,717  (Foundation skin subtree + MMS cross-chapter)
└── HPO Phenotype nodes:      1,094  (skin/hair/nail phenotypes)

Edges:  32,080
├── has_phenotype:             8,696  (disease → symptom/sign)
├── has_synonym:               7,425  (disease → alternate name)
├── is_a:                      7,204  (child → parent classification)
├── has_mms_code:              1,830  (disease → ICD-11 code)
├── mms_parent:                1,474  (MMS hierarchy link)
├── xref_snomed:               1,355  (→ SNOMED CT concept)
├── xref_dermo:                  866  (→ DermO concept)
├── also_in_chapter:             689  (cross-chapter marker)
├── xref_icd10:                  513  (→ ICD-10 code)
├── xref_umls:                   474  (→ UMLS CUI)
├── xref_orpha:                  450  (→ Orphanet code)
├── xref_doid:                   425  (→ Disease Ontology ID)
├── xref_omim:                   403  (→ OMIM ID)
└── xref_mesh:                   276  (→ MeSH descriptor)
```

### Node Coverage

| Attribute | Count | % of 6,811 |
|-----------|-------|------------|
| Has English definition | 4,174 | 61.3% |
| Has synonyms | 2,996 | 44.0% |
| Has ICD-11 MMS code | 1,830 | 26.9% |
| Has Chinese name | 1,805 | 26.5% |
| Has Derm1M images | 973 | 14.3% |
| Has DermO mapping | 866 | 12.7% |
| Has SNOMED CT ID | 730 | 10.7% |
| Has UMLS CUI | 441 | 6.5% |
| Has Orphanet code | 437 | 6.4% |
| Has DOID mapping | 425 | 6.2% |
| Has HPO phenotypes | 317 | 4.7% |
| Has OMIM ID | 316 | 4.6% |
| Has MeSH ID | 273 | 4.0% |

## Data Sources

Eight data sources are integrated. Each serves a distinct purpose:

### Core: ICD-11 (Backbone)

| Source | Role | Nodes contributed |
|--------|------|-------------------|
| **ICD-11 Foundation** | Disease hierarchy + definitions + synonyms | 5,216 (skin subtree) |
| **ICD-11 MMS** | Codes (EA90 etc.) + Chinese names + chapter assignment | 1,805 entries |

**ICD-11 has two layers:**
- **Foundation** = ontology layer with ~71K entities, multi-parent DAG. A disease can belong to multiple branches (e.g., "cutaneous tuberculosis" belongs to both infectious diseases AND skin diseases).
- **MMS** = coding layer with ~37K entries, single-parent tree. Each disease is assigned to exactly one chapter for statistical coding.

The Foundation skin subtree (5,216 nodes) does NOT cover all skin-related diseases. Skin cancers in Chapter 02, skin infections in Chapter 01, etc. are often missing from the Foundation skin branch. Our build script uses a **triple strategy** to compensate:

1. **Foundation BFS**: All 5,216 descendants of "Diseases of the skin" (icd11:1639304259)
2. **Foundation URI bridge**: Non-Ch14 MMS entries whose Foundation URI falls within the skin subtree (+689)
3. **Keyword matching**: Non-Ch14 MMS entries with skin-related terms in their title (+513)

See [docs/FILTERING_STRATEGY.md](docs/FILTERING_STRATEGY.md) for details on coverage gaps and improvement plans.

**Why 73% of nodes have no ICD-11 code?**
- 3,787 nodes come from Foundation only (no MMS code assigned) — these are fine-grained sub-concepts that MMS lumps into "Other specified" residual categories
- 1,094 nodes are HPO phenotypes (symptoms, not diseases)
- Only MMS-coded entries (1,830) receive codes like EA90

### External Ontologies (Semantic Enrichment)

| Source | What it adds that ICD-11 lacks | Matched | Added |
|--------|-------------------------------|---------|-------|
| **DermO** (Dermatological Disease Ontology) | SNOMED CT IDs, OMIM IDs, ICD-10 codes | 889 / 3,401 (26%) | 1,779 cross-refs |
| **HPO** (Human Phenotype Ontology) | Standardized skin/hair/nail phenotype vocabulary | 1,094 new nodes | Phenotype layer |
| **DOID** (Disease Ontology) | UMLS CUI, MeSH IDs | 234 / 586 (37%) | 651 cross-refs |

### Rare Disease Databases

| Source | What it adds | Matched | Added |
|--------|-------------|---------|-------|
| **RSDB** (Rare Skin Disease Database) | Phenotype associations + drug associations | 407 / 891 (46%) | 8,618 phenotypes + 1,628 drugs |
| **Orphanet** | OrphaCode identifiers for rare diseases | 93 / 1,234 (8%) | Orphanet mappings |

### Image Data

| Source | What it adds | Mapped |
|--------|-------------|--------|
| **Derm1M** | Image counts per disease node | 207,941 images → 973 nodes |

## Project Structure

```
skin_kg_project/
├── README.md                              ← You are here
├── .gitignore
│
├── docs/                                  ← Documentation
│   ├── README.md                          ← Detailed technical documentation
│   ├── DATA_SOURCES.md                    ← How to download every data file
│   └── FILTERING_STRATEGY.md             ← Filtering approach + known gaps
│
├── scripts/                               ← Build scripts (3 versions)
│   ├── build_v1_icd11_only.py            ← v1: ICD-11 Foundation + MMS only
│   ├── build_v2_with_ontologies.py       ← v2: + DermO + HPO + DOID
│   └── build_v3_full.py                  ← v3: + RSDB + Orphanet + Derm1M ★
│
├── data/                                  ← Data sources
│   ├── icd11_foundation.obo              ← ICD-11 Foundation (15MB, gitignored)
│   ├── ICD-11-MMS-with-PathID.xlsx       ← ICD-11 MMS (5.5MB, gitignored)
│   ├── dermo.obo                         ← DermO ontology (960KB, tracked)
│   ├── devo.owl                          ← DEVO dermoscopy ontology (176KB, tracked)
│   ├── d3x.owl                           ← D3X dermoscopy DDx ontology (76KB, tracked)
│   ├── hp.obo                            ← HPO (10MB, gitignored)
│   ├── doid.obo                          ← Disease Ontology (6.7MB, gitignored)
│   ├── mondo.obo                         ← MONDO (49MB, gitignored)
│   ├── rsdb/                             ← RSDB 21 CSV files (211MB, gitignored)
│   ├── orphanet/                         ← Orphanet XML/JSON (178MB, gitignored)
│   ├── Derm1M_v2_pretrain.csv            ← Derm1M dataset (308MB, gitignored)
│   ├── disease_icd11_mapping.json        ← Pre-built disease→ICD-11 mapping (592KB, tracked)
│   └── derm1m_original_ontology.json     ← Original Derm1M ontology (24KB, tracked)
│
├── output/                                ← Build outputs
│   ├── skin_kg_v3.json                   ← Full KG (9.3MB, gitignored, reproducible)
│   ├── skin_kg_nodes_v3.csv             ← Node attributes table (1.9MB)
│   ├── skin_kg_triples_v3.csv           ← Edge triples (1.6MB)
│   ├── skin_kg_stats_v3.json            ← Statistics
│   └── derm1m_unmapped_labels.txt        ← Labels not yet mapped (568KB)
│
└── visualization/                         ← Interactive HTML explorer
    ├── index.html                        ← Open in browser (needs local server)
    └── skin_kg_v3.json                   ← Data copy (gitignored)
```

## Node Schema

Every node (disease or phenotype) has these attributes:

```json
{
  "id": "icd11:63698555",
  "name": "Psoriasis",
  "definition": "Psoriasis is a common, chronic, relapsing...",
  "synonyms": ["Psoriasis vulgaris", ...],
  "mms_code": "EA90",
  "cn_name": "银屑病",
  "chapter": "14",
  "path_id": "14.2.2.1",
  "is_leaf": false,
  "source": "foundation+mms",

  "dermo_id": "DERMO:0000124",
  "doid_id": "DOID:8893",
  "orpha_codes": [],
  "rsdb_id": "",
  "snomed": ["9014002"],
  "omim": ["PS177900"],
  "umls": ["C0033860"],
  "mesh": ["D011565"],
  "icd10": ["L40"],
  "hpo_pheno": ["HP:0003765"],
  "genes": [],
  "drugs": [],
  "image_count": 17026,
  "data_sources": ["youtube", "public", "ISIC", ...]
}
```

### Source field values

| source | Meaning | Count |
|--------|---------|-------|
| `foundation` | Only in ICD-11 Foundation (no MMS code) | 3,912 |
| `foundation+mms` | In both Foundation and MMS (has code + definition) | 1,304 |
| `mms_only` | Only in MMS (residual categories like "unspecified") | 462 |
| `hpo` | HPO phenotype node (not a disease) | 1,094 |

## Visualization

The interactive HTML explorer shows:

- **Top statistics bar**: Node/edge counts, coverage percentages
- **Left panel**: Searchable node list with chapter badges and image counts
  - Filter buttons: All / Has Definition / Has Images / Has Chinese / HPO Phenotypes
- **Right panel**: Full node detail including:
  - Definition text (from Foundation/DermO/DOID/RSDB)
  - Synonyms (merged from all sources)
  - Phenotypes/Symptoms (from RSDB + DermO HPO cross-refs)
  - Associated Drugs (from RSDB)
  - Cross-References grid (SNOMED, OMIM, UMLS, MeSH, DermO, DOID, Orphanet)
  - Parent/Child hierarchy (clickable navigation)
  - Image data sources
- **Overview dashboard**: Source distribution, chapter distribution, edge type charts, Chapter 14 top-level category cards

```bash
cd visualization
python3 -m http.server 8765
# Open http://localhost:8765
```

## Known Limitations

### 1. Filtering completeness (~374 potential misses)

The keyword-based filtering for non-Chapter-14 entries misses some diseases:
- Leprosy, erysipelas, sporotrichosis (missing keywords)
- Ch22 skin wounds described as "abrasion of [body part]"
- MMS residual categories without Foundation URIs

See [docs/FILTERING_STRATEGY.md](docs/FILTERING_STRATEGY.md) for the full gap analysis and 3 proposed improvement approaches.

### 2. Cross-ontology matching rate

Name-based matching has inherent limits:
- DermO: 26% matched (74% are unique DermO concepts not in ICD-11)
- Orphanet: 8% matched (rare disease naming differs significantly)
- Could be improved with embedding-based semantic matching

### 3. Not yet integrated

| Resource | File | Potential |
|----------|------|-----------|
| DEVO (dermoscopy features) | `data/devo.owl` | Standardize `skin_concept` column |
| D3X (dermoscopy DDx) | `data/d3x.owl` | Auto-generate differential diagnosis edges |
| MONDO | `data/mondo.obo` | Cross-ontology alignment hub via SSSOM |
| Orphanet gene-disease data | `data/orphanet/en_product6.xml` | Add gene associations |
| Orphanet HPO-disease data | `data/orphanet/en_product4.xml` | Add phenotype annotations |

## How to Extend

### Add a new data source

1. Download data to `data/`
2. In `scripts/build_v3_full.py`, add a new PHASE section
3. Match entities using `name_idx` (normalized name → node_id mapping)
4. Inject new attributes into matched nodes
5. Add new edge types if needed
6. Update documentation

### Improve entity matching

Current matching is name-based. To improve:
```python
# Use embedding similarity (e.g., BioBERT)
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb')
# Encode all ICD-11 names and external ontology names
# Match by cosine similarity > 0.85
```

### Generate VLM training data

The KG enables generating structured training pairs:
```python
# For CLIP: (image, text) pairs with KG-enriched descriptions
# For QwenVL: (image, instruction, response) with KG-sourced answers
# See docs/README.md Section 7-8 for detailed examples
```

## License

- ICD-11 data: CC-BY-ND-3.0-IGO (WHO)
- DermO: Open access
- HPO: Free for academic use
- DOID: CC0 1.0 (public domain)
- RSDB: CC BY-NC-SA 4.0
- Orphanet: CC BY 4.0
- Build scripts: MIT
