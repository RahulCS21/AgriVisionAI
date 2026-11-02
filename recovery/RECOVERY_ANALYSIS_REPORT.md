# AgriVision AI — Historical Dataset Recovery Analysis

## Result

The requested VS Code Local History snapshots are present in the recovery
folder. Each recovered file's SHA-256 hash matches its source snapshot. Since
the targets already existed and match exactly, neither file was overwritten.

| Recovered file | VS Code Local History source | SHA-256 |
|---|---|---|
| `recovery/crop_data.csv` | `C:\Users\Rahul Sharma\AppData\Roaming\Code\User\History\4efe825e\mXh1.csv` | `4B72CDA035EA8C534DB479ACEDD603448DBC6E440BDB214051EC552A4406BE18` |
| `recovery/train_model.py` | `C:\Users\Rahul Sharma\AppData\Roaming\Code\User\History\136a1ea1\6d3T.py` | `05A2B9BEB4667AAE988EB8A3999C53228245208AFF44F8221FA0112821D469BC` |

The Local History metadata identifies the original project paths as
`C:\Intership\AgriVionAI\dataset\crop_data.csv` and
`C:\Intership\AgriVionAI\train_model.py`.

## Dataset analysis

The recovered CSV was parsed from the recovered file using Python's CSV
reader.

- **Data rows:** 10 (header excluded)
- **Columns:** `temperature`, `rainfall`, `humidity`, `yield`
- **Column count:** 4
- **Rows:** all 10 are unique, have all four fields, and contain numeric values.
- **Provenance and scope:** The snapshot includes no source, units, crop,
  district/location, season, or year information.

## Is model retraining possible?

**Mechanically: yes. Suitable for a real production yield model: no.**

The recovered training script selects `temperature`, `rainfall`, and
`humidity` as features, selects `yield` as the target, fits scikit-learn
`LinearRegression`, and writes a pickle to `models/yield_model.pkl`. The
recovered CSV has those expected columns, so a basic estimator could be fit
from its rows.

That mechanical fit would not establish valid predictive performance or
credible crop-yield estimates. Ten generic rows without provenance, crop,
location, season, year, units, or independent evaluation data are insufficient
to support India-specific real-world use. The project realism audit also
identifies the historical generic data as synthetic and unsuitable for
production predictions.

The script is retained as a historical snapshot and was **not run**. Its
relative input path is `dataset/crop_data.csv`, which is not the recovered
file's path, and it writes into `models/`; it does not create that directory.
No model was trained, saved, or loaded by this recovery task, and no
predictions were generated.

## Verification and scope

- Both requested recovery files were already present.
- Both recovered files match their Local History sources byte-for-byte by
  SHA-256.
- The CSV was parsed and its row/column structure verified.
- No existing files were overwritten.
- No data was fabricated.
- No training or prediction was performed.

For a defensible production model, obtain traceable, appropriately licensed
yield records with defined units and crop, location, season, year, and relevant
management/weather context; then use a documented training and independent
evaluation process before enabling prediction output.
