FROM python:3.11-slim

WORKDIR /app

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

COPY requirements.txt .
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} --trusted-host ${PIP_TRUSTED_HOST} -r requirements.txt

COPY . .

ENV MCP_TRANSPORT=sse
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=8001

EXPOSE 8000
EXPOSE 8001

CMD ["python", "run_servers.py"]
