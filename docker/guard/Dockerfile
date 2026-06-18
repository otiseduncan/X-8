FROM python:3.12-slim
WORKDIR /repo
COPY scripts /repo/scripts
COPY . /repo
CMD ["python", "scripts/check_file_size.py", "."]
