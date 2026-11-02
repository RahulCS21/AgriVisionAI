# AgriVision AI — Production Repair and Verification Report

**Audit scope:** live weather, yield and disease prediction availability, and
database/history/report/dashboard health.

## Status summary

| Area | Status | Verified result |
|---|---|---|
| Weather | Working at audit time | Open-Meteo geocoding and forecast returned live data for all four requested cities; each Weather Dashboard request returned HTTP 200 and rendered the live provider result. |
| Crop yield | Unavailable | No valid yield model or authentic training dataset is installed. The app does not generate or save yield predictions without a model. |
| Disease detection | Unavailable | The expected model and TensorFlow are both absent. The app does not produce a diagnosis without inference. |
| Database | Working | The active SQLite database is readable and contains seven existing records. The test suite verifies prediction writes and history/report/dashboard behavior using isolated temporary databases. |
| History and reports | Working | The full UI test suite passed its saved-record, pagination, statistics, and empty-state checks. |
| Dashboard counters | Working | The full UI test suite passed dashboard module, statistics, and quick-link checks. |
| Multilingual support | Working | Translation tests passed for supported languages, navigation, forms, weather guidance, and translated prediction output. |

## Weather

The application uses Open-Meteo's India-constrained geocoding endpoint and
forecast endpoint. A live call through the app's weather lookup function
returned:

| Search | Resolved location | Temperature | Humidity | Rain probability | Wind |
|---|---|---:|---:|---:|---:|
| Bengaluru | Bengaluru, Karnataka, India | 23.2 °C | 61% | 0% | 6.6 km/h |
| Mysuru | Mysuru, Karnataka, India | 20.6 °C | 91% | 0% | 8.7 km/h |
| Delhi | Delhi, National Capital Territory of Delhi, India | 19.2 °C | 95% | 2% | 1.9 km/h |
| Mumbai | Mumbai, Maharashtra, India | 25.5 °C | 85% | 49% | 7.0 km/h |

All four results were observed at `2026-10-30T23:45` according to the provider.
Separate requests through the `/weather` route returned HTTP 200 and rendered
the weather summary, temperature, and “Live data from Open-Meteo” for every
city.

**Finding:** No reproducible weather integration defect was observed during
this audit, so no weather code change was made. Live weather depends on network
access to Open-Meteo and can be temporarily unavailable if the provider or
network fails.

## Yield prediction

**Status: unavailable; no predictions were generated.**

- The active application has no working yield model loader or inference path.
  The yield page validates inputs but explicitly reports that no model is
  installed; it does not save a yield estimate.
- Missing legacy artifact path: `C:\Intership\AgriVionAI\models\yield_model.pkl`
- Missing original dataset path: `C:\Intership\AgriVionAI\dataset\crop_data.csv`
- Recovered historical files:
  - `C:\Intership\AgriVionAI\recovery\crop_data.csv`
  - `C:\Intership\AgriVionAI\recovery\train_model.py`
- The recovered CSV has 10 rows and columns `temperature`, `rainfall`,
  `humidity`, and `yield`. The prior realism audit identifies these generic
  rows as synthetic and unsuitable for genuine predictions. The recovered
  trainer is archival only; it has not been run and is not connected to the
  active app.
- VS Code history contains old source references to `models/yield_model.pkl`,
  but no serialized model artifact was recovered.

**Required to restore credible yield prediction:** a verified, permissioned
agricultural yield dataset with documented source, units, crop, location, and
season/year coverage; a reviewed training/evaluation pipeline; a validated
model artifact; and an inference path that matches the model's training
features. Until supplied and validated, leave yield estimates unavailable.

## Disease detection

**Status: unavailable; no diagnoses were generated.**

- Expected model path: `C:\Intership\AgriVionAI\models\disease_model.h5`
- The model file is absent.
- TensorFlow is not installed in
  `C:\Intership\AgriVionAI\.venv\Scripts\python.exe`.
- The app's disease inference expects a trained model compatible with its
  image preprocessing and 38 PlantVillage output classes. The app reports
  unavailable inference rather than inventing a diagnosis.
- No disease-model artifact or recovery snapshot was found in the searched
  project files and VS Code Local History.

**Required to restore disease inference:** the compatible trained model,
TensorFlow and its compatible dependencies in the project environment, plus
validation that model input preprocessing and all 38 output-class mappings
match the application's inference code.

## Database, history, reports, and dashboard

Active database inspected read-only:

`C:\Intership\AgriVionAI\instance\prediction_history.sqlite3`

Existing records at inspection:

| Feature | Records |
|---|---:|
| Crop Recommendation | 5 |
| Disease Detection | 1 |
| Fertilizer Recommendation | 1 |
| Yield Prediction | 0 |
| **Total** | **7** |

The existing database was queried read-only. The 41-test suite passed,
including tests for feature persistence, History and Reports pagination and
statistics, Dashboard statistics, and the unavailable-model behavior. Those
tests isolate database writes in temporary databases; they do not depend on
the seven production records.

## Verification run

- Command: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
- Result: **41 tests passed**
- Live weather function: four of four city lookups returned live values.
- Weather route: four of four requests returned HTTP 200 and rendered live
  weather output.
- Active database: opened with SQLite read-only mode; seven records read.
- Expected model files and TensorFlow: absent, verified in the project
  interpreter.
- No application source code was modified during this audit.

## Production actions

1. Keep yield inference disabled until a trustworthy dataset and validated
   model are provided; do not train from the recovered 10-row snapshot.
2. Provide the compatible disease model and install a compatible TensorFlow
   build before enabling disease inference.
3. Configure a persistent `AGRIVISION_SECRET_KEY` before deployment. The app
   currently emits a warning and uses a process-local key when it is unset.
4. Preserve the active SQLite database and current model-unavailable
   safeguards. No files or records were deleted or overwritten for this
   audit.
