FROM python:3.9-slim
RUN apt-get update && apt-get install -y ffmpeg
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
#RUN python -c "import whisper; whisper.load_model('tiny')"
COPY . .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
