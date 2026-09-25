FROM python:3.11-slim

WORKDIR /app

# Copiamos primero solo requirements.txt para aprovechar el cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ahora copiamos el resto del codigo de la aplicacion
COPY . .

# Creamos un usuario sin privilegios de administrador (buena practica de seguridad)
RUN useradd --create-home --shell /bin/bash appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]