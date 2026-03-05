# Contributing to TermIndex Knowledge Base

## Adding a New Standard

Each standard lives as a self-contained module under `standards/{standard_id}/`. To add a new standard (e.g., VSME):

### 1. Create the directory

```
standards/vsme/
├── standard.json
├── scoring_rules.json
├── gap_analysis_rules.json
├── extraction_schema.json
├── glossary.json
└── corpus/
    ├── chunks/
    └── chunk_index.json
```

### 2. Required files

**`standard.json`** — Standard definition
- `standard_id`: unique identifier (lowercase, e.g., `"vsme"`)
- `name`: full name of the standard
- `version`: year or version string
- `parts`: array of standard parts/sections with `id`, `name`, `definition`, `applicability` (entity types), and `criteria`

**`scoring_rules.json`** — Scoring rubrics
- `criteria`: object with part-keyed arrays of criterion definitions
- Each criterion needs: `id`, `name`, `part`, `max_score`, `rubric` (0-N mapping)
- `weighting`: entity-type-specific part weights (must sum to 1.0)
- `maturity_levels`: array of score-to-maturity mappings

**`gap_analysis_rules.json`** — Gap identification logic
- `coverage_statuses`: define what "reported", "partial", "missing" mean
- `priority_classification`: conditions and timelines for critical/high/medium/low
- `materiality_by_entity_type`: which criteria are most material per entity type
- `gap_templates`: reusable gap descriptions and recommendations

**`extraction_schema.json`** — Data extraction schema
- Define all fields to extract from sustainability reports
- Each field needs: `type`, `required`, `description`, `expected_format`, `validation_rules`

**`glossary.json`** — Standard-specific glossary
- Bilingual (EN/FR) terms with: `id`, `term_en`, `term_fr`, `definition_en`, `definition_fr`, `synonyms_en`, `synonyms_fr`, `related_terms`

**`corpus/chunks/`** — Knowledge chunks for RAG
- Individual JSON files per chunk (~500 tokens each)
- Each chunk: `chunk_id`, `standard_id`, `section`, `topic`, `language`, `content`, `metadata`
- `corpus/chunk_index.json`: array of all chunk metadata (without content)

### 3. Pipeline compatibility

No changes to `pipeline/ingest.py` or `pipeline/analyze.py` are needed. The analysis script loads standard modules dynamically by ID:

```bash
python pipeline/analyze.py --input data.json --standard vsme
```

## Updating Scoring Rules

1. Edit `standards/{standard_id}/scoring_rules.json`
2. Modify the specific criterion's `rubric` object
3. If adding a new criterion, add it to the appropriate `part_X` array
4. If changing weights, update the `weighting` object (weights must sum to 1.0 per entity type)
5. Re-run analysis on affected institutions to update scores

## Adding New Institutions

1. Create `institutions/profiles/{institution_id}.json` using lowercase ID
2. Required fields:
   - `institution_id`: uppercase identifier
   - `name`: full legal name
   - `entity_type`: must match a type in `common/entity_types.json`
   - `country`: ISO 2-letter code
   - `standards.pcaf`: PCAF-specific assessment data
3. Update `institutions/compliance_matrix.json` with the new entry in the `institutions` array
4. Update `summary_statistics` counts

### Institution profile template

```json
{
  "institution_id": "EXAMPLE",
  "name": "Example Bank PLC",
  "entity_type": "bank",
  "country": "UK",
  "standards": {
    "pcaf": {
      "assessment_date": "2025-02-01",
      "pcaf_mentioned": true,
      "pcaf_signatory": false,
      "operational_emissions": {"scope1": null, "scope2_market": null},
      "financed_emissions": {"value": null, "unit": "unknown"},
      "part_status": {"A": "missing", "B": "missing", "C": "N/A"},
      "dqs": null,
      "asset_class_coverage": {
        "listed_equity_corporate_bonds": "missing",
        "business_loans_unlisted_equity": "missing",
        "project_finance": "missing",
        "commercial_real_estate": "missing",
        "residential_mortgages": "missing",
        "motor_vehicle_loans": "missing",
        "use_of_proceeds": "missing",
        "securitized_structured": "missing",
        "sovereign_debt": "missing",
        "sub_sovereign_debt": "missing"
      },
      "critical_gaps": [],
      "recommendation": ""
    }
  }
}
```

## Extending the Glossary

### Standard-specific glossary

Edit `standards/{standard_id}/glossary.json` and add a new entry to the `terms` array:

```json
{
  "id": "new_term",
  "term_en": "New Term",
  "term_fr": "Nouveau Terme",
  "definition_en": "English definition...",
  "definition_fr": "Définition française...",
  "synonyms_en": [],
  "synonyms_fr": [],
  "pcaf_part": null,
  "related_terms": []
}
```

### Common glossary

Edit `common/glossary_common.json` for terms shared across standards. Same structure but without `pcaf_part`.

## Adding Corpus Chunks

1. Create a new JSON file in `standards/{standard_id}/corpus/chunks/{chunk_id}.json`
2. Use the naming convention: `{standard_id}_{sequential_number}` (e.g., `pcaf_021`)
3. Target ~500 tokens of content per chunk
4. Include relevant metadata keywords for retrieval
5. Update `corpus/chunk_index.json` with the new chunk's metadata (all fields except `content`)

## JSON Schema Conventions

- Use `snake_case` for all JSON keys
- Use `null` for missing/unknown values (not empty strings)
- Enum values: `"reported"`, `"partial"`, `"missing"`, `"N/A"`
- Units: always specify (e.g., `"tCO2e"`, `"MtCO2e"`)
- Dates: ISO 8601 format (`"2025-02-01"`)
- IDs: lowercase with underscores for data keys, UPPERCASE for institution IDs
- All JSON files must be valid and properly indented (2 spaces)
