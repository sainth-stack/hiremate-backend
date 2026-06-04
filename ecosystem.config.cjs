const path = require('path');

const ROOT = __dirname;
const BACKEND = path.join(ROOT, 'backend');

function pythonBin() {
  const venv = path.join(BACKEND, '.venv', 'bin', 'python3');
  const fs = require('fs');
  if (fs.existsSync(venv)) return venv;
  return 'python3';
}

const PY = pythonBin();
const ENV = {
  PYTHONPATH: ROOT,
  PYTHONUNBUFFERED: '1',
};

module.exports = {
  apps: [
    {
      name: 'hiremate-api',
      cwd: ROOT,
      script: PY,
      args: '-m uvicorn backend.main:app --host 0.0.0.0 --port 8000',
      env: ENV,
      instances: 1,
      autorestart: true,
      max_memory_restart: '1G',
      watch: false,
    },
    {
      name: 'celery-worker-ingest',
      cwd: ROOT,
      script: PY,
      args:
        '-m celery -A backend.celery.app worker -Q ingest --concurrency=2 --loglevel=info --hostname=ingest@%h',
      env: ENV,
      instances: 1,
      autorestart: true,
      max_memory_restart: '1G',
    },
    {
      name: 'celery-beat',
      cwd: ROOT,
      script: PY,
      args: '-m celery -A backend.celery.app beat --loglevel=info',
      env: ENV,
      instances: 1,
      autorestart: true,
      max_memory_restart: '256M',
    },
  ],
};
