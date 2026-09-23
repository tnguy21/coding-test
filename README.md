# coding-test

# Setup
The frontend and backend have seperate docker containers used to containerize everything - So there is no hunting for dependencies.

On the root directory (This current directory) there is a `docker-compose.yml`, which can be used to setup the frontend and backend as such:

```bash
docker compose up
```

This spins up the frontend service `localhost:8080` and the backend service at `localhost:8000` (e.g. `http://127.0.0.1:8000/portfolios/PF-01/loss-experience`)

