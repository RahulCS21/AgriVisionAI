# AgriVision AI — Model and Dataset Recovery Report

**Audit date:** 2026-10-30  
**Project searched:** `C:\Intership\AgriVionAI`  
**Additional locations searched:** user profile files, VS Code local file
history/workspace storage and backups, and the accessible Recycle Bin.

## Executive result

- **Original yield model (`yield_model.pkl`): Not recovered.** No model
  artifact was found in the project, user-profile file search, VS Code file
  history, searched archives, or relevant Recycle Bin metadata.
- **A historical crop dataset snapshot: Recoverable from VS Code local
  history, but unsuitable for training.** It contains 10 data rows and only
  generic `temperature`, `rainfall`, `humidity`, and `yield` columns. The
  project's realism audit identifies the former CSV/model as synthetic and
  removed. It lacks crop, district, season, year, and trustworthy provenance.
- **Original disease model (`disease_model.h5`): Not recovered.**
- **No model was trained, no dataset was restored into the project, and no
  predictions were generated.** No files were restored or modified; this
  report is the only file created.

## Exact files and locations found

| Exact path | Status | Details |
|---|---|---|
| `C:\Users\Rahul Sharma\AppData\Roaming\Code\User\History\4efe825e\mXh1.csv` | **Snapshot recoverable** | VS Code Local History maps this snapshot to `C:\Intership\AgriVionAI\dataset\crop_data.csv`. It is 177 bytes with 10 data rows and columns `temperature,rainfall,humidity,yield`. |
| `C:\Users\Rahul Sharma\AppData\Roaming\Code\User\History\4efe825e\entries.json` | History metadata | Confirms the snapshot's original resource path was `file:///c%3A/Intership/AgriVionAI/dataset/crop_data.csv`. |
| `C:\Users\Rahul Sharma\AppData\Roaming\Code\User\History\136a1ea1\6d3T.py` | **Training-script snapshot recoverable** | VS Code Local History maps this file to `C:\Intership\AgriVionAI\train_model.py`. It reads `dataset/crop_data.csv`, fits `sklearn.linear_model.LinearRegression`, and writes `models/yield_model.pkl`. The script is very small and does not provide validation/evaluation. |
| `C:\Users\Rahul Sharma\AppData\Roaming\Code\User\History\136a1ea1\entries.json` | History metadata | Confirms the snapshot's original resource path was `file:///c%3A/Intership/AgriVionAI/train_model.py`. |
| `C:\Users\Rahul Sharma\AppData\Roaming\Code\User\History\19d2b052\KBG3.py` | **Old application-code snapshot** | Contains `pickle.load(open("models/yield_model.pkl", "rb"))`; it is source code referencing a model, not the model file. |
| `C:\Users\Rahul Sharma\AppData\Roaming\Code\User\History\19d2b052\tE2X.py` | **Old application-code snapshot** | Also references loading `models/yield_model.pkl`; it is not a model artifact. |
| `C:\Users\Rahul Sharma\AppData\Roaming\Code\User\History\19d2b052\62Qw.py` | **Old application-code snapshot** | Also references loading `models/yield_model.pkl`; it is not a model artifact. |
| `C:\Intership\AgriVionAI\REALISM_AUDIT.md` | Audit evidence | Says the former pickle, synthetic CSV, and naive training script were removed because the 11 generic records did not support credible India-specific estimates. |
| `C:\$Recycle.Bin\S-1-5-21-282436848-1224926293-1680335643-1001\$ITEFV0K.py` | **Deleted script metadata** | Original path recorded as `C:\Intership\AgriVionAI\train_model.py`; recorded deleted size is 0 bytes. The separately preserved VS Code history snapshot has the script contents. |

The CSV snapshot shown above has 10 data rows (11 lines including the header).
This matches the audit's description of an 11-row file if the header was
counted as a row.

## Exact expected artifacts not found

- `C:\Intership\AgriVionAI\models\yield_model.pkl`
- `C:\Intership\AgriVionAI\models\disease_model.h5`
- Any other serialized yield or disease model artifact in the searched
  project/user locations
- A current `C:\Intership\AgriVionAI\dataset\crop_data.csv`
- Any other India-focused yield dataset in the searched project/user
  locations
- A current training script in the project tree

The only yield training code found is the VS Code history snapshot above.

## Backup, archive, and history checks

- The project tree contains no model/data archive.
- No likely AgriVision/AgriVion, crop, yield, project-backup, or model archive
  was found in the searched user-profile and workspace archive locations.
- The user's VS Code Local History contains the CSV and Python source
  snapshots listed above, but no `yield_model.pkl` or disease-model snapshot
  was found.
- Recent local/cloud coding-session history queries did not return additional
  matching AgriVision sessions. VS Code's on-disk Local History did contain
  the snapshots.
- The accessible Recycle Bin metadata identifies a zero-byte deleted
  `train_model.py`; it does not identify a deleted yield model, dataset CSV,
  or disease model.
- Searches found no named old AgriVision project copy in the checked user
  locations. No relevant archive was available to inspect.

## Recovery assessment

The **historical files can be recovered as snapshots**, but this does not
recover a usable prediction system. The CSV's tiny size, generic features,
lack of geographic/crop/time labels, and the project's explicit synthetic-data
audit mean it must not be used to claim real India-focused yield predictions.
The historical training script's ability to fit a linear regression is not
evidence that its output is valid.

Accordingly:

- The original trained yield model is **not recoverable from locations
  checked**.
- The old CSV is **recoverable from VS Code Local History**, but is **not
  suitable as legitimate training data**.
- The disease model is **not recoverable from locations checked**.
- No fake model, synthetic data, or fabricated prediction has been created.
