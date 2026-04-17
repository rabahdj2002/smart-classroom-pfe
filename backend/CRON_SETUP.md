# Cron Setup for Classroom Auto-Finish

By default, no external cron setup is required. The website starts an internal scheduler automatically, and the effective interval is controlled from the Settings page via "Cron check interval (minutes)".

Use external cron or Task Scheduler only as an optional fallback.

## Linux crontab

```bash
* * * * * /full/path/to/python /full/path/to/smart-classroom-pfe/backend/manage.py auto_finish_classrooms >> /full/path/to/smart-classroom-pfe/backend/cron_auto_finish.log 2>&1
```

## Example

```bash
* * * * * /home/user/smart-classroom-pfe/.venv/bin/python /home/user/smart-classroom-pfe/backend/manage.py auto_finish_classrooms >> /home/user/smart-classroom-pfe/backend/cron_auto_finish.log 2>&1
```

## Windows alternative (Task Scheduler)

Use Task Scheduler to run every 1 minute:

```powershell
C:\path\to\smart-classroom-pfe\.venv\Scripts\python.exe C:\path\to\smart-classroom-pfe\backend\manage.py auto_finish_classrooms
```
