# Wiki2
Wiki2 is een iteratie op de hiervoor bestaande wiki die geintegreerd was met de site. Ze is sneller, simpeler en modern gemaakt.

## TODO
### SSL/TLS
To configure SSL/TLS go to docker-compose, change the ports and configure nginx to server over https. Also visit the bottom of setting.py to see what configurationchanges are needed there.

### Test backup script en cron
There is a backupscript and folder, but it is unknown if it works because it needs the container to be running (at 3am) for it to try make a backup.

### Schrijf een deftige readme
Huidige readme is outdated en slecht.

## Create a .env file if you want to run the docker container and define the following variables:
```
# Django Settings
DJANGO_SECRET_KEY='HIHIII_HIER_KOMT_EEN_SECRETKEY'
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,10.1.1.224 # TODO:Add your actual domain for production
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://10.1.1.224:8000 # TODO:Add your actual domain for production

# Application Port (host side)
APP_PORT=80

# PostgreSQL Settings # FIXME: COMMENT IN/OUT FOR DOCKER
DB_ENGINE=django.db.backends.postgresql
DB_NAME=wikidb
DB_USER=wikiuser
DB_PASSWORD=wikipassword
DB_HOST=db # This is the service name from docker-compose.yml
DB_PORT=5432 # Default PostgreSQL port inside the container network

# Redis Settings
REDIS_HOST=redis # This is the service name from docker-compose.yml
REDIS_PORT=6379 # Default Redis port inside the container network
```