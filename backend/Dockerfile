FROM python:3.12-slim

# Establecemos el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos e instalamos dependencias primero (aprovecha la caché de Docker:
# si requirements.txt no cambia, esta capa no se reconstruye)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código
COPY . .

# Creamos el directorio donde vivirá la BD SQLite
# Este directorio se monta como volumen en docker-compose.yml
RUN mkdir -p /app/data

# Puerto que expone el contenedor
EXPOSE 8000

# Comando para arrancar el servidor
# --host 0.0.0.0 para que sea accesible desde fuera del contenedor
# --reload en desarrollo para recargar automáticamente (quitarlo en producción)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
