curl https://raw.githubusercontent.com/pam-param-pam/I-Drive/master/docker-compose.yml > docker-compose.yml
curl https://raw.githubusercontent.com/pam-param-pam/I-Drive/master/nginx.conf > nginx.conf
docker compose up & 


while [[ $(docker inspect -f '{{.State.Status}}' idrive-backend) != 'running' ]]
do
   echo "waiting for idrive-backend to start"
   sleep 1s
done

docker exec idrive-backend echo "----------------I have been in the container -------------"
echo " ----------------------------------------- sleeping --------------------------------"
sleep 80s
echo "----------------------------------------STOPPING --------------------------------"
docker compose stop