module.exports = {
  apps: [
    {
      name: "flickreels-bot",
      script: "/root/flxdl/venv/bin/python3",
      args: "main.py",
      cwd: "/root/flxdl",
      autorestart: true,
      watch: false,
      max_memory_restart: "1G",
      env: {
        NODE_ENV: "production",
      }
    }
  ]
};
