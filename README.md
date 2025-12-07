# Project Setup Guide

## Create Project Folder and Environment Setup

```bash
# Create uv environment
uv python list
uv python install cpython-3.10.18-macos-aarch64-none

uv venv .venv --python cpython-3.10.18-macos-aarch64-none

## Activate the virtual environment
source .venv/bin/activate # for macOS/Linux
source .venv/Scripts/activate   # for Windows

## Install required packages
uv pip install -r requirements.txt

## check installed packages versions
python3 get_lib_versions.py 

#### some other useful uv commands
uv python list          # list all python versions available
uv init ecomm-prod-assistant    # create a new uv project 
uv pip list            # list installed packages in the current environment


# rename .env.copy to .env and add your API keys
mv .env.copy .env

## Run the application
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload

## API docs available at: http://localhost:8080/docs
```


## Dockerize the Application

```bash
# create a docker image
docker build -t document-portal-system .

# run the docker image
docker run -d -p 8093:8080 --name document-portal-container document-portal-system
```