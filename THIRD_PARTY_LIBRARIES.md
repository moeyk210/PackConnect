# Third-party libraries

PackConnect uses the open-source libraries, model, data and tools below. Each
keeps its own license. This list covers the packages the project names
directly (and the extras it asks for); those packages bring further
dependencies of their own, under their own licenses.

Versions are the ranges the project requires, then the version installed when
this list was checked (November 24, 2026). Licenses are taken from each
package's own published metadata.

## Backend (Python)

From `backend/requirements.txt`, needed to run the app:

| Package | Required | Checked | License | Used for |
| --- | --- | --- | --- | --- |
| [Flask](https://flask.palletsprojects.com/) | >=3.1,<4 | 3.1.3 | BSD-3-Clause | Web API |
| [Flask-Cors](https://github.com/corydolphin/flask-cors) | >=6,<7 | 6.0.5 | MIT | Cross-origin requests |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | >=1,<2 | 1.2.4 | BSD-3-Clause | Reading `backend/.env` |
| [supabase](https://github.com/supabase/supabase-py) | >=2,<3 | 2.34.1 | MIT | Supabase Auth sign-in |
| [psycopg](https://www.psycopg.org/) | >=3.2,<4 | 3.3.9 | LGPL-3.0-only | PostgreSQL access |
| psycopg-binary (psycopg `binary` extra) | | 3.3.9 | LGPL-3.0-only | Prebuilt PostgreSQL driver |
| psycopg-pool (psycopg `pool` extra) | | 3.3.3 | LGPL-3.0-only | Connection pooling |
| [Flask-SocketIO](https://github.com/miguelgrinberg/flask-socketio) | >=5.7,<6 | 5.7.2 | MIT | Real-time messaging |
| [simple-websocket](https://github.com/miguelgrinberg/simple-websocket) | >=1.1,<2 | 1.1.0 | MIT | WebSocket transport |
| [fastembed](https://github.com/qdrant/fastembed) | >=0.9,<1 | 0.9.1 | Apache-2.0 | Topic fingerprints for meaning-based matching |

psycopg is LGPL-3.0. PackConnect uses it as an unmodified library installed
from PyPI, which the LGPL allows without changing PackConnect's own license.

From `backend/requirements-dev.txt`, only for the messaging benchmark:

| Package | Required | Checked | License | Used for |
| --- | --- | --- | --- | --- |
| [python-socketio](https://github.com/miguelgrinberg/python-socketio) (`client` extra) | >=5.18,<6 | 5.18.1 | MIT | Benchmark client |
| requests (python-socketio `client` extra) | | 2.34.2 | Apache-2.0 | Benchmark client |
| websocket-client (python-socketio `client` extra) | | 1.9.2 | Apache-2.0 | Benchmark client |

Installed by CI only, to measure test coverage:

| Package | License | Used for |
| --- | --- | --- |
| [coverage](https://github.com/nedbat/coveragepy) | Apache-2.0 | Backend coverage report |

## Frontend (JavaScript)

From `frontend/package.json`, shipped in the built website:

| Package | Required | Checked | License | Used for |
| --- | --- | --- | --- | --- |
| [react](https://github.com/facebook/react) | ^19.2.8 | 19.3.0 | MIT | User interface |
| [react-dom](https://github.com/facebook/react) | ^19.2.8 | 19.3.0 | MIT | Rendering in the browser |
| [socket.io-client](https://github.com/socketio/socket.io) | ^4.8.4 | 4.8.4 | MIT | Real-time messaging |

Development only (building, testing, linting and formatting):

| Package | Required | Checked | License |
| --- | --- | --- | --- |
| [vite](https://github.com/vitejs/vite) | ^8.3.0 | 8.3.4 | MIT |
| [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react) | ^6.1.1 | 6.1.2 | MIT |
| [vitest](https://github.com/vitest-dev/vitest) | ^5.0.5 | 5.0.5 | MIT |
| [jsdom](https://github.com/jsdom/jsdom) | ^29.1.1 | 29.1.1 | MIT |
| [@testing-library/react](https://github.com/testing-library/react-testing-library) | ^16.3.3 | 16.3.3 | MIT |
| [@testing-library/jest-dom](https://github.com/testing-library/jest-dom) | ^7.0.1 | 7.0.1 | MIT |
| [@testing-library/user-event](https://github.com/testing-library/user-event) | ^14.6.8 | 14.6.8 | MIT |
| [eslint](https://github.com/eslint/eslint) | ^10.10.0 | 10.12.0 | MIT |
| [@eslint/js](https://github.com/eslint/eslint) | ^10.0.1 | 10.0.1 | MIT |
| [eslint-plugin-react-hooks](https://github.com/facebook/react) | ^7.1.1 | 7.1.1 | MIT |
| [eslint-plugin-react-refresh](https://github.com/ArnaudBarre/eslint-plugin-react-refresh) | ^0.5.6 | 0.5.7 | MIT |
| [globals](https://github.com/sindresorhus/globals) | ^17.12.0 | 17.13.0 | MIT |
| [prettier](https://github.com/prettier/prettier) | 3.9.10 | 3.9.10 | MIT |
| [@types/react](https://github.com/DefinitelyTyped/DefinitelyTyped) | ^19.2.18 | 19.3.0 | MIT |
| [@types/react-dom](https://github.com/DefinitelyTyped/DefinitelyTyped) | ^19.2.7 | 19.3.0 | MIT |

## Language model

| Model | Source | License | Used for |
| --- | --- | --- | --- |
| BAAI/bge-small-en-v1.5 | Downloaded by fastembed from the Hugging Face model `Qdrant/bge-small-en-v1.5-onnx-Q` (about 67 MB) | MIT (as listed by fastembed) | Topic fingerprints; runs on the server, no outside service is called |

## Data

| Data | Source | License | Used for |
| --- | --- | --- | --- |
| `backend/data/nc_state_courses.csv` (162 CSC courses: code, title, department, description) | To be confirmed: added by Savanah Hendzel in `51f6d78` | To be confirmed | Course catalog, autocomplete and course pages |

## Database and services

| Software | License | Used for |
| --- | --- | --- |
| [PostgreSQL](https://www.postgresql.org/) 17 | PostgreSQL License | Database |
| [pgvector](https://github.com/pgvector/pgvector) (`pgvector/pgvector:pg17` Docker image) | PostgreSQL License | Storing and comparing topic fingerprints |
| [Supabase](https://supabase.com/) | Hosted service, used under Supabase's terms | Hosted PostgreSQL and Auth for the team's project |

To check licenses after dependencies change: for Python, read each installed
package's metadata, for example
`python -c "import importlib.metadata as m; print(m.metadata('flask')['License-Expression'])"`
(`pip show` leaves the license blank for packages that use this newer field;
older packages list theirs under `License` or `Classifier`). For the frontend,
read the `license` field in `frontend/node_modules/<package>/package.json`.
