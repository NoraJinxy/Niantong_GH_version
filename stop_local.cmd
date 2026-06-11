@echo off
cd /d "%~dp0"
echo Stopping ELYS local Docker containers...
docker compose -f docker-compose.local.yml stop
echo Done. (Data volume preserved — next start_local.cmd will reuse existing DB data.)
echo To wipe DB data: docker compose -f docker-compose.local.yml down -v
pause
