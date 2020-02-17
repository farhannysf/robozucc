FROM python

WORKDIR /app

RUN set -eux \
  && apt-get update \
  && apt-get install -y fonts-liberation 

RUN pip install requests

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . /app

EXPOSE 4444

CMD ["python", "main.py"]
