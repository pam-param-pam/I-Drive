group "default" {
  targets = ["frontend", "backend"]
}

target "frontend" {
  context = "frontend"
  dockerfile = "frontend/Dockerfile"
  cache-from = ["type=local,src=/tmp/.buildx-cache"]
  cache-to = ["type=local,dest=/tmp/.buildx-cache,mode=max"]
  tags = ["ghcr.io/${github.repository_owner}/idrive-frontend:latest"]
  output = ["type=registry"]
}

target "backend" {
  context = "backend"
  dockerfile = "backend/Dockerfile"
  cache-from = ["type=local,src=/tmp/.buildx-cache"]
  cache-to = ["type=local,dest=/tmp/.buildx-cache,mode=max"]
  tags = ["ghcr.io/${github.repository_owner}/idrive-backend:latest"]
  output = ["type=registry"]
}
