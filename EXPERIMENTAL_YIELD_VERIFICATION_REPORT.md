# Experimental Yield Model — Verification Report

## Result

The recovered training script was run against the recovered 10-row dataset.
The model is loaded by the Flask app and used for explicitly labeled
experimental demonstration predictions. This model is **not production-grade**
and must not be used for real agricultural planning.

## Model

- **Created:** Yes
- **Model path:** `C:\Intership\AgriVionAI\models\yield_model.pkl`
- **Training script:** `C:\Intership\AgriVionAI\recovery\train_model.py`
- **Dataset:** `C:\Intership\AgriVionAI\recovery\crop_data.csv`
- **Dataset size:** 10 generic rows
- **Input features:** `temperature`, `rainfall`, `humidity`
- **SHA-256:** `643c316eb4f7dad57bbee838b2e9f9b1f92d69f7be1caf1d78b5c21442609d5f`
- **Result label:** `Experimental Demonstration Prediction`

The page states that the recovered dataset contains only 10 generic rows and
that results are not production-grade. It also notes the dataset does not
document yield units.

## Functional verification

| Check | Result |
|---|---|
| Model artifact exists and loads with the expected feature schema | Passed |
| Yield form GET and prediction POST | HTTP 200 |
| Result carries the exact experimental label | Passed |
| 10-row and not-production-grade disclaimers appear | Passed |
| Successful prediction saved to SQLite | Passed in isolated verification database |
| History page displays the saved result | Passed |
| Reports page displays the saved result and increments yield counter | Passed |
| Dashboard shows demonstration model available | Passed |
| Full test suite | **44 tests passed** |
| Python syntax check | Passed |

End-to-end verification used an isolated temporary SQLite database, wrote one
yield result, and confirmed the same result appeared in History and Reports.
The active project database was not changed by the verification run.

## Limitations

The recovered dataset has no documented source, units, crop, location, season,
or year. The estimator is an internship demonstration only; no accuracy or
production suitability is claimed.
