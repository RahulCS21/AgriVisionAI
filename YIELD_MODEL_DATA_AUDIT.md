# AgriVision AI — Yield Model and Dataset Audit

**Audit date:** 2026-10-30  
**Project root:** `C:\Intership\AgriVionAI`

## Result

**A genuine crop-yield model cannot be retrained from the files currently
present in the project.** The full project inventory found no yield dataset,
yield training script, or saved yield model. No fabricated data or predictions
were created, and no model was trained.

The existing application features, SQLite database, history, reports, and
dashboard were left intact.

## Search performed

Searched project files recursively while excluding virtual environments and
Python/cache directories. Looked for:

- Tabular and dataset formats: `.csv`, `.tsv`, `.xlsx`, `.xls`, `.jsonl`,
  `.parquet`, `.arff`, and `.data`
- Serialized/model formats: `.pkl`, `.pickle`, `.joblib`, `.sav`, `.h5`,
  `.hdf5`, `.keras`, and `.onnx`
- Python source and documentation for training code, data loading, model
  fitting, model inference, yield-model references, and the former 11-row
  model

## Relevant files found

| Exact path | Finding |
|---|---|
| `C:\Intership\AgriVionAI\app.py` | Contains yield form validation and the current informational notice that no yield model is installed. It contains no yield-model loader, yield inference call, or yield training code. It does contain optional TensorFlow disease inference. |
| `C:\Intership\AgriVionAI\agriculture.py` | Contains broad rules-based crop suitability and fertilizer guidance. It is not a crop-yield estimator and does not train a model. |
| `C:\Intership\AgriVionAI\REALISM_AUDIT.md` | Records that the former 11-row generic yield pickle, synthetic CSV, and naive training script were removed because they did not support credible India-specific estimates. |
| `C:\Intership\AgriVionAI\REPAIR_AUDIT_REPORT.md` | Previous project audit documenting the absent yield model/data and current database/history status. |
| `C:\Intership\AgriVionAI\tests\test_yield_prediction.py` | Tests input validation and confirms that no yield record is stored when there is no real model result. It is test code, not training data. |
| `C:\Intership\AgriVionAI\tests\test_ui_pages.py` | Tests database/history/report behavior using isolated test records. It is test code, not training data. |
| `C:\Intership\AgriVionAI\instance\prediction_history.sqlite3` | Existing SQLite prediction-history database; its saved application records are not a labeled yield-training dataset. |
| `C:\Intership\AgriVionAI\models\` | Directory exists but contains no model files. |
| `C:\Intership\AgriVionAI\dataset\` | Directory exists but contains no dataset files. |

No separate training script was found.

## Required files not present

These are the project paths searched for or expected locations; they are
**absent**, not generated:

1. `C:\Intership\AgriVionAI\dataset\yield_dataset.csv` — no yield training
   dataset was found in any supported tabular format.
2. `C:\Intership\AgriVionAI\train_yield_model.py` — no yield training script
   was found.
3. `C:\Intership\AgriVionAI\models\yield_model.pkl` — no saved yield model was
   found in any searched model format.
4. `C:\Intership\AgriVionAI\models\` — no yield model or other model artifact
   is currently present. This also includes the configured disease model
   location `C:\Intership\AgriVionAI\models\disease_model.h5`.

The source and trustworthy provenance for the historical 11-row dataset/model
are also unavailable. The audit documentation explicitly says those files
were removed.

## Can the database be used to train yield?

The active database is:

`C:\Intership\AgriVionAI\instance\prediction_history.sqlite3`

It currently contains historical application records, including crop
recommendation and disease entries. It does not contain a documented labeled
yield dataset or trustworthy yield targets and provenance. Existing history
must not be treated as ground-truth training data merely because it is stored
in SQLite.

## Final status

- **Yield model retraining:** Not possible from files currently available.
- **Yield inference:** Remains unavailable; no numeric result is generated or
  stored without a real model.
- **CSV/dataset files:** None found in the project.
- **Training scripts:** None found.
- **Saved yield model:** None found.
- **Disease model:** None found; expected location is
  `C:\Intership\AgriVionAI\models\disease_model.h5`.
- **Database/history/reporting:** Existing database retained; no database rows
  were modified by this audit.
- **Code changes:** None. This audit report is the only file created.

To restore genuine yield prediction, add an appropriately licensed,
traceable India-relevant labeled dataset and a reviewed training pipeline.
After evaluation and documentation of feature order, preprocessing, target
units, supported ranges, and validation metrics, the trained model can be
saved as `C:\Intership\AgriVionAI\models\yield_model.pkl` and explicitly
integrated into `app.py`.
