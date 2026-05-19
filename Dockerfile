FROM quay.io/astronomer/astro-runtime:12.7.1

COPY requirements.txt /requirements.txt

RUN pip install --no-cache-dir -r /requirements.txt