curl https://raw.githubusercontent.com/pam-param-pam/I-Drive/master/docker-compose.yml > docker-compose.yml
curl https://raw.githubusercontent.com/pam-param-pam/I-Drive/master/.env 
docker compose up
docker exec -it idrive-backend bash
ls
exit
          