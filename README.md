# Wiki2
Wiki2 is een iteratie op de hiervoor bestaande examenwiki. Ze is sneller, simpeler en modern gemaakt.

## TODO
### SSL/TLS
To configure SSL/TLS go to docker-compose, change the ports and configure nginx to server over https. Also visit the bottom of setting.py to see what configurationchanges are needed there.

### Login/LDAP
Make StuCard werkende enzo...

## Possible security concerns:
### LaTeX compiling
LaTeX is a very powerfull typesetting language. With the right knowledge, **remote code execution** can be achieved! To counteract this **some commands have been blacklisted** but this is **NOT a foolproof solution**. To fully secure ourselves, a docker enviroment with limited file-access and non-root running is advised.
> The entire application is dockerised and running as non-root. This should be as secure as needs (still not perfect, but the docker is inescapable)

## Create a .env file if you want to run the docker container and define the following variables:
```# Django Settings
DJANGO_SECRET_KEY='HAHAHA_HIER_KOMT_EEN_SECRETKEY'
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,10.1.1.224
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://10.1.1.224:8000

# Application Port (host side)
APP_PORT=8000

# PostgreSQL Settings
DB_ENGINE=django.db.backends.postgresql
DB_NAME=wikidb
DB_USER=wikiuser
DB_PASSWORD=wikipassword
DB_HOST=db # This is the service name from docker-compose.yml
DB_PORT=5432 # Default PostgreSQL port inside the container network

# Redis Settings
REDIS_HOST=redis # This is the service name from docker-compose.yml
REDIS_PORT=6379 # Default Redis port inside the container network

# Django Superuser Credentials
DJANGO_SUPERUSER_USERNAME=Webteam
DJANGO_SUPERUSER_EMAIL=Webteam@wina.be
DJANGO_SUPERUSER_PASSWORD=HAHAHA_HIER_KOMT_EEN_WACHTWOORD```