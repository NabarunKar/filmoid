# Use a standard Python image (safer than alpine/slim for compiling scikit-surprise C-extensions)
FROM python:3.10

# Set the root working directory
WORKDIR /app

# Copy only the requirements first to cache the pip install step
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your backend code
COPY backend/ ./backend/

# Switch the working directory to the backend folder 
# This ensures your Path(__file__).resolve().parents[1] logic finds the model correctly
WORKDIR /app/backend

# Expose the specific port Hugging Face Spaces requires
EXPOSE 7860

# Run Uvicorn on 0.0.0.0 and port 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]