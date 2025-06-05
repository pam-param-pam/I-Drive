# Use the official Python image from the Docker Hub
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app/backend

# Include nano
RUN apt-get update && apt-get install -y nano && apt-get install -y g++

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

RUN chmod +x entrypoint.sh

# Command to run the Daphne server
ENTRYPOINT ["./entrypoint.sh"]