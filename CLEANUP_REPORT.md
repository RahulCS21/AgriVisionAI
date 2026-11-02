# AgriVision AI Cleanup Report

## Conclusion

`app.py` is the project's single Flask application entry point. It creates the
Flask app, defines the application routes, and calls `app.run()` when executed
directly. The tests also import the app from this file. Run the application
from the project directory with `python app.py`.

`app1.py` is not a Flask entry point: it only prints greeting text. No project
source, tests, or documentation reference it. It appears obsolete and is a
safe deletion candidate if nobody uses it as a standalone greeting script.

The helper modules are used by `app.py` and should be kept. Removing them would
break imports or remove application functionality.

## File decisions

| File | Status | Evidence / rationale |
|---|---|---|
| `app.py` | **Keep** | Defines `app = Flask(__name__)`, all application routes, and the direct-run `app.run()` block. Tests import the app from here. |
| `app1.py` | **Safe to delete** | Contains only greeting `print()` statements; no references were found in project source, tests, or documentation. Not a Flask startup file. |
| `agriculture.py` | **Keep** | `app.py` imports crop recommendation and fertilizer guidance functions and soil/season data from this module. |
| `disease_guidance.py` | **Keep** | `app.py` imports and uses `get_disease_guidance()` for disease advice. |
| `translations.py` | **Keep** | `app.py` imports language and translation helpers; tests also use this module. |

## Startup-file recommendation

Use `app.py` as the sole application startup file. `app1.py` does not start the
application, so it does not create a second Flask startup path. No code was
changed and no files were deleted as part of this review. Delete `app1.py`
manually only if its standalone greeting output is not needed.
