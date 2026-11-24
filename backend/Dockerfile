FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN python manage.py collectstatic --noinput

EXPOSE 8000
# Daphne serves both HTTP and the /mqtt/ WebSocket bridge (ASGI).
CMD ["sh", "-c", "python manage.py migrate --noinput && exec daphne -b 0.0.0.0 -p 8000 smartclass.asgi:application"]
