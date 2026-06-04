FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY sporganize.py /app/
COPY config.yaml.dist /app/config.yaml.dist
COPY .build/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD []
