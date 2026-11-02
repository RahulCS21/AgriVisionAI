# Yield Model Training and Integration Report

## Outcome

**The recovered model was trained and integrated for internship demonstration
use only.** It is explicitly not production-grade. The original recovered
training script and CSV were used; no data was added or altered.

## Verified inputs and model path

- Dataset: `C:\Intership\AgriVionAI\recovery\crop_data.csv`
- Training script: `C:\Intership\AgriVionAI\recovery\train_model.py`
- Trained model: `C:\Intership\AgriVionAI\models\yield_model.pkl`
- Dataset structure: **10 rows**; columns are `temperature`, `rainfall`,
  `humidity`, and `yield`.
- The recovered CSV has no documented source, units, crop, location, season,
  or year. Therefore the model is clearly labeled as a demonstration and the
  output states that target yield units are undocumented.

The recovered script expects the relative input `dataset/crop_data.csv`.
Without changing the historical script, it was executed in a temporary
staging directory containing an exact copy of `recovery/crop_data.csv`; its
generated artifact was then saved to the requested model path. The model
expects features in this order: `temperature`, `rainfall`, `humidity`.

## Verification

- Model trained: **Yes**, using the recovered trainer and dataset.
- Model path: `C:\Intership\AgriVionAI\models\yield_model.pkl`
- Model SHA-256: `643c316eb4f7dad57bbee838b2e9f9b1f92d69f7be1caf1d78b5c21442609d5f`
- Prediction page: **Working**; successful output is labeled
  “Experimental Demonstration Prediction.” The page discloses that the model
  uses only 10 generic recovered rows and is not production-grade.
- SQLite persistence: **Working**; successful predictions are stored as
  `Crop Yield` records.
- History and Reports: **Working**; yield results and counts appear in both.
- End-to-end verification submitted one prediction to an isolated temporary
  SQLite database and confirmed that the same record appeared in History and
  Reports and incremented Dashboard/Reports yield statistics.
- The existing application database was checked read-only after testing: 7
  existing records, 0 yield records. It was not changed by test submissions.
- Full test suite: **44 tests passed** after the experimental label and
  10-row dataset disclaimer were applied.

## Limitations

This small, generic dataset cannot support reliable real-world yield
estimates. Obtain traceable agricultural data and independently evaluate a
model before using it for production decisions.
