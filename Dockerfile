FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=0 \
    DJANGO_DATA_DIR=/data \
    PORT=8000

# LibreOffice turns the generated DOCX into PDF; Laksaman (fonts-thai-tlwg) stands in for TH SarabunPSK.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-writer-nogui fonts-thai-tlwg fontconfig \
    && rm -rf /var/lib/apt/lists/*
COPY deploy/fonts.conf /etc/fonts/local.conf
RUN fc-cache -f

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN DJANGO_SECRET_KEY=build python manage.py collectstatic --noinput

VOLUME ["/data"]
EXPOSE 8000
CMD ["sh", "deploy/start.sh"]
