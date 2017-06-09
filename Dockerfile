FROM python:3

WORKDIR /usr/src/app

COPY requirements.txt .

COPY *.py .

RUN mkdir config

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "/usr/src/app/main.py"]
