module.exports = {
  apps: [
    {
      name: "p096-backend",
      script: ".venv/bin/python",
      args: "-m uvicorn src.main:app --host 127.0.0.1 --port 8000 --workers 2",
      cwd: "./",
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_memory_restart: "1G",
      env: {
        APP_ENV: "production",
        PYTHONUNBUFFERED: "1",
      },
      error_file: "logs/backend-error.log",
      out_file: "logs/backend-out.log",
      merge_logs: true,
      time: true,
    },
  ],
};
