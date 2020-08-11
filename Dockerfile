FROM python:3-slim

RUN apt-get update -y && apt-get upgrade -y
RUN apt-get install -y zip

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "./server.py" ]