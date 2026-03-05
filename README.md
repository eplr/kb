# TermIndex Knowledge Base

Multi-standard knowledge base for ESG/sustainability compliance analysis, powering the TermIndex RAG (Retrieval-Augmented Generation) pipeline.

## Architecture

```
termindex-kb/
├── standards/          # Standard-specific modules (pluggable)
│   └── pcaf/           # PCAF — first standard implemented
│       ├── standard.json
│       ├── scoring_rules.json
│       ├── gap_analysis_rules.json
│       ├── extraction_schema.json
│       ├── glossary.json
│       └── corpus/
│           ├── chunks/          # 20 methodology chunks
│           └── chunk_index.json
├── common/             # Cross-standard shared resources
│   ├── ghg_protocol.json
│   ├── glossary_common.json
│   └── entity_types.json
├── institutions/       # Institution data
│   ├── profiles/       # 23 institution profiles
│   └── compliance_matrix.json
├── templates/          # LLM prompt templates
│   ├── assessment_template.json
│   ├── extraction_prompt.md
│   └── analysis_prompt.md
├── pipeline/           # Processing scripts
│   ├── ingest.py
│   ├── analyze.py
│   └── config.yaml
├── README.md
└── CONTRIBUTING.md
```

The architecture is **standard-agnostic**. Each regulatory/voluntary standard (PCAF, VSME, CSRD, etc.) lives as a self-contained module under `standards/`. Adding a new standard means creating a new `standards/{id}/` directory with the same file structure — no pipeline changes needed.

## Quick Start

### Analyze an existing institution

```bash
# Run compliance analysis on Aviva's profile
python pipeline/analyze.py \
  --input institutions/profiles/aviva.json \
  --standard pcaf \
  --output aviva_assessment.json
```

### Ingest a new sustainability report

```bash
# Extract and chunk a PDF report
python pipeline/ingest.py \
  --input /path/to/report.pdf \
  --output /tmp/chunks/ \
  --standard pcaf

# Extract from XLSX
python pipeline/ingest.py \
  --input /path/to/data.xlsx \
  --output /tmp/chunks/ \
  --standard pcaf --chunk-size 300
```

### Prerequisites

- Python 3.10+
- For PDF ingestion: `pip install pdfplumber` or `pip install PyPDF2`
- For XLSX ingestion: `pip install openpyxl`

## Standards: PCAF

The PCAF (Partnership for Carbon Accounting Financials) module covers:

- **Part A** — Financed Emissions: 10 asset classes, 8 scoring criteria
- **Part B** — Facilitated Emissions: capital markets, 2 scoring criteria
- **Part C** — Insurance-Associated Emissions: 4 insurance lines, 8 scoring criteria

### Scoring

18 criteria scored on a 0-5 rubric, with entity-type-specific weighting:

- **Banks**: 70% Part A + 30% Part B
- **Insurers**: 50% Part A + 50% Part C
- **Asset Managers**: 100% Part A
- **Bancassurance**: 40% Part A + 20% Part B + 40% Part C

Alternative percentage-based scoring (0-100%) is also available for cross-institution comparison.

### Institutions

23 European financial institutions profiled with PCAF compliance data:
Admiral, Ageas, Allianz, Amundi, ASR Nederland, Aviva, AXA, Commerzbank, Crédit Agricole, Deutsche Börse, Eurazeo, GBL, KBC, Legal & General, NN Group, Nordea, Phoenix Group, Santander, Schroders, Société Générale, Swiss Re, UniCredit, Zurich.

## Adding a New Institution

1. Create a JSON file in `institutions/profiles/{institution_id}.json`
2. Follow the schema used by existing profiles (see `institutions/profiles/aviva.json` as a reference)
3. Update `institutions/compliance_matrix.json` with the new entry

## Adding a New Standard

See [CONTRIBUTING.md](CONTRIBUTING.md) for the complete guide. In brief:

1. Create `standards/{standard_id}/` with 6 required files
2. Add corpus chunks under `corpus/chunks/`
3. No pipeline changes needed — scripts auto-detect standards by ID

## Corpus

The PCAF corpus contains 20 chunked methodology documents covering:
overview, Part A/B/C definitions, asset classes, data quality scoring, attribution methodology, gap analysis, regulatory context, and more. Each chunk is ~500 tokens with full metadata for RAG retrieval.

## Glossaries

- **PCAF glossary**: ~65 bilingual (EN/FR) terms covering all asset classes, metrics, and methodology
- **Common glossary**: ~25 bilingual terms shared across standards (ESG, GHG, TCFD, CSRD, etc.)
