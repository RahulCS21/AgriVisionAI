# AgriVision AI — VS Code Snapshot Recovery Report

## Result

The two requested VS Code Local History snapshots have been restored into
`C:\Intership\AgriVionAI\recovery\`. No existing project files were
overwritten. The files are exact content copies of the saved snapshots.

## Recovered files

| Recovered path | VS Code Local History source | Details |
|---|---|---|
| `C:\Intership\AgriVionAI\recovery\crop_data.csv` | `C:\Users\Rahul Sharma\AppData\Roaming\Code\User\History\4efe825e\mXh1.csv` | 10 data rows (11 lines including header). |
| `C:\Intership\AgriVionAI\recovery\train_model.py` | `C:\Users\Rahul Sharma\AppData\Roaming\Code\User\History\136a1ea1\6d3T.py` | Reads `dataset/crop_data.csv`, fits scikit-learn `LinearRegression`, and writes `models/yield_model.pkl`. |

The VS Code history metadata identifies the original project resources as
`C:\Intership\AgriVionAI\dataset\crop_data.csv` and
`C:\Intership\AgriVionAI\train_model.py`.

## Dataset structure

- **Rows:** 10 data rows.
- **Columns, in file order:** `temperature`, `rainfall`, `humidity`, `yield`.
- **Geographic/crop/time labels:** None.
- **Data provenance:** No trustworthy source or provenance is present in the
  snapshot.

## Model recreation assessment

The recovered CSV has the columns expected by the recovered script, so the
same basic LinearRegression training procedure can be executed mechanically
from these files. That does **not** establish that the original serialized
pickle can be recovered byte-for-byte, nor that the resulting estimator is a
valid India-specific crop-yield model.

The project's `REALISM_AUDIT.md` explicitly identifies the historical data as
synthetic and says the former dataset, model, and naive training script were
removed because the 11 generic rows did not support credible India-specific
estimates. Ten rows without crop, district, season, year, units, or verified
provenance are not suitable for real-world model claims.

**Conclusion:** Technically retrainable as the same simple estimator; not
reproducible as the exact original model artifact from the two snapshots alone,
and not suitable for production predictions. No model was trained or saved,
and no predictions were generated during this recovery.

## Safety and scope

- No application code was changed.
- No files outside the new `recovery` folder were overwritten.
- No model artifact was created.
- No data was fabricated; the restored CSV is the original VS Code snapshot.
- The recovered script writes to relative `dataset/` and `models/` paths and
  is retained as historical code; it is not connected to the active app.
