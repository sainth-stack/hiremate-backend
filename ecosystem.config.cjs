const path = require('path');
const fs = require('fs');

const ROOT = __dirname;
const BACKEND = path.join(ROOT, 'backend');
const FRONTEND_ROOT = process.env.FRONTEND_ROOT || path.join(path.dirname(ROOT), 'hiremate-frontend');

function pythonBin() {
  const candidates = [
    path.join(ROOT, 'venv', 'bin', 'python3'),
    path.join(BACKEND, '.venv', 'bin', 'python3'),
    path.join(ROOT, 'venv', 'bin', 'python'),
    path.join(BACKEND, '.venv', 'bin', 'python'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  console.error('\nFATAL: Python venv not found.');
  console.error(`Expected one of:\n  ${candidates.join('\n  ')}`);
  console.error(`\nFix:\n  cd ${ROOT}`);
  console.error('  python3 -m venv venv');
  console.error('  source venv/bin/activate && pip install -r requirements.txt\n');
  process.exit(1);
}

const PY = pythonBin();
const ENV = {
  PYTHONPATH: ROOT,
  PYTHONUNBUFFERED: '1',
  PORT: '8000',
  FRONTEND_ROOT,
};

module.exports = {
  apps: [
    {
      name: 'hiremate-api',
      cwd: ROOT,
      script: path.join(ROOT, 'scripts/start-api.sh'),
      interpreter: 'bash',
      env: ENV,
      instances: 1,
      autorestart: true,
      max_restarts: 5,
      min_uptime: '10s',
      restart_delay: 5000,
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
      max_restarts: 5,
      min_uptime: '10s',
      restart_delay: 5000,
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
      max_restarts: 5,
      min_uptime: '10s',
      restart_delay: 5000,
      max_memory_restart: '256M',
    },
    {
      name: 'student-frontend',
      cwd: FRONTEND_ROOT,
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'development',
      },
      instances: 1,
      autorestart: true,
      max_restarts: 5,
      min_uptime: '10s',
      restart_delay: 5000,
      max_memory_restart: '512M',
    },
  ],
};
